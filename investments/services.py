from __future__ import annotations

from datetime import timedelta
from decimal import Decimal

from django.db import transaction
from django.utils import timezone

from investments.models import BonusTracker, DailyProfit, InvestmentPlan, UserInvestment
from settingsconfig.utils import get_setting_decimal
from wallets.models import Wallet
from wallets.services import credit_wallet, debit_wallet, get_primary_wallet
from adminpanel.utils import log_action


def _update_bonus_progress(user, amount: Decimal) -> None:
    try:
        tracker = BonusTracker.objects.select_for_update().get(user=user)
    except BonusTracker.DoesNotExist:
        return

    if tracker.is_unlocked:
        return

    tracker.achieved_profit += amount
    if tracker.achieved_profit >= tracker.required_profit:
        tracker.is_unlocked = True
    tracker.save(update_fields=['achieved_profit', 'is_unlocked'])


@transaction.atomic
def create_investment(
    user,
    plan: InvestmentPlan,
    amount: Decimal,
    *,
    wallet: Wallet | None = None,
    auto_reinvest: bool = False,
    risk_acknowledged: bool = False,
) -> UserInvestment:
    if wallet is None:
        raise ValueError("Select a wallet for investments.")
    if wallet.user_id != user.id:
        raise ValueError("Selected wallet does not belong to this user.")
    wallet = Wallet.objects.select_for_update().get(pk=wallet.pk)
    if wallet.wallet_type not in {'primary', 'trading'}:
        raise ValueError("Investments can only be funded from a primary or trading wallet.")
    if amount > wallet.total_balance:
        raise ValueError("Insufficient available wallet balance.")

    if amount < plan.min_amount:
        raise ValueError("Amount below plan minimum.")
    if plan.max_amount and amount > plan.max_amount:
        raise ValueError("Amount above plan maximum.")

    remaining = amount
    for bucket in ('main', 'bonus', 'profit'):
        bucket_balance = getattr(wallet, f'{bucket}_balance')
        if remaining <= 0:
            break
        deduction = min(bucket_balance, remaining)
        if deduction > 0:
            debit_wallet(
                wallet,
                deduction,
                bucket,
                'investment',
                {'plan': plan.name, 'bucket': bucket},
            )
            remaining -= deduction

    if remaining > 0:
        raise ValueError("Insufficient available wallet balance.")

    end_date = timezone.now() + timedelta(days=plan.duration_days)
    investment = UserInvestment.objects.create(
        user=user,
        wallet=wallet,
        plan=plan,
        amount=amount,
        end_date=end_date,
        auto_reinvest=auto_reinvest,
        risk_acknowledged=risk_acknowledged,
    )
    log_action(user, 'investment_created', 'investment', investment.id, {'plan': plan.name, 'amount': str(amount)})
    return investment


def _interval_days(plan: InvestmentPlan) -> int:
    if plan.payout_frequency == 'weekly':
        return 7
    if plan.payout_frequency == 'monthly':
        return 30
    return 1


def _quantize_money(value: Decimal) -> Decimal:
    return value.quantize(Decimal('0.01'))


def _build_due_schedule(investment: UserInvestment, cutoff_date):
    start_date = investment.start_date.date()
    end_date = investment.end_date.date()
    if cutoff_date <= start_date:
        return []

    interval = _interval_days(investment.plan)
    final_cutoff = min(cutoff_date, end_date)
    due_dates = []
    next_due = start_date + timedelta(days=interval)
    while next_due <= final_cutoff:
        due_dates.append(next_due)
        next_due += timedelta(days=interval)

    if final_cutoff == end_date and (not due_dates or due_dates[-1] != end_date):
        due_dates.append(end_date)

    schedule = []
    period_start = start_date
    for due_date in due_dates:
        period_days = (due_date - period_start).days
        if period_days <= 0:
            continue
        schedule.append((due_date, period_days))
        period_start = due_date
    return schedule


@transaction.atomic
def sync_investment_profits(process_date=None) -> dict:
    if process_date is None:
        process_date = timezone.now().date()

    summary = {
        'investments_checked': 0,
        'payouts_created': 0,
        'investments_completed': 0,
    }

    investments = (
        UserInvestment.objects.select_for_update()
        .select_related('plan', 'user', 'wallet')
        .filter(start_date__date__lte=process_date)
    )

    for investment in investments:
        summary['investments_checked'] += 1
        schedule = _build_due_schedule(investment, process_date)
        if not schedule:
            continue

        existing_dates = set(
            DailyProfit.objects.filter(investment=investment, date__in=[item[0] for item in schedule]).values_list('date', flat=True)
        )
        created_any = False

        for due_date, period_days in schedule:
            if due_date in existing_dates:
                continue

            gross_profit = investment.amount * (investment.plan.daily_roi / Decimal('100')) * Decimal(period_days)
            fee_pct = investment.plan.management_fee_pct or Decimal('0')
            fee_amount = gross_profit * (fee_pct / Decimal('100'))
            net_profit = _quantize_money(gross_profit - fee_amount)
            if net_profit <= 0:
                continue

            DailyProfit.objects.create(
                investment=investment,
                date=due_date,
                amount=net_profit,
            )

            payout_wallet = investment.wallet or get_primary_wallet(investment.user)
            if payout_wallet:
                payout_wallet = Wallet.objects.select_for_update().get(pk=payout_wallet.pk)
                credit_wallet(
                    payout_wallet,
                    net_profit,
                    'profit',
                    'profit',
                    {'investment_id': investment.id, 'payout_date': due_date.isoformat()},
                )

            investment.total_earned += net_profit
            _update_bonus_progress(investment.user, net_profit)
            log_action(
                None,
                'profit_applied',
                'investment',
                investment.id,
                {'amount': str(net_profit), 'date': due_date.isoformat()},
            )
            summary['payouts_created'] += 1
            created_any = True

        should_be_completed = False
        if process_date >= investment.end_date.date():
            expected_all_dates = {item[0] for item in _build_due_schedule(investment, investment.end_date.date())}
            paid_all_dates = set(
                DailyProfit.objects.filter(investment=investment, date__in=expected_all_dates).values_list('date', flat=True)
            )
            should_be_completed = expected_all_dates.issubset(paid_all_dates)

        if should_be_completed and not investment.is_completed:
            investment.is_completed = True
            summary['investments_completed'] += 1

        if created_any or should_be_completed:
            investment.save(update_fields=['total_earned', 'is_completed'])

    return summary


@transaction.atomic
def apply_daily_profits(process_date=None) -> int:
    summary = sync_investment_profits(process_date=process_date)
    return summary['payouts_created']


def can_withdraw(user, amount: Decimal) -> tuple[bool, str]:
    min_amount = get_setting_decimal('MIN_WITHDRAWAL_AMOUNT', default='10')
    if amount < min_amount:
        return False, f"Minimum withdrawal is {min_amount}."

    try:
        profile = user.userprofile
        if profile.has_withdrawn:
            return True, "OK"
    except Exception:
        pass

    try:
        tracker = BonusTracker.objects.get(user=user)
    except BonusTracker.DoesNotExist:
        tracker = None

    if tracker and not tracker.is_unlocked:
        return False, "Bonus requirements not met yet."

    return True, "OK"
