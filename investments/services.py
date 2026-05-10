from __future__ import annotations

from dataclasses import dataclass
from datetime import timedelta
from decimal import Decimal
import logging
import uuid

from django.db import DatabaseError, connection, transaction
from django.core.cache import cache
from django.utils import timezone

from investments.models import DailyProfit, InvestmentAccount, InvestmentPlan, ProfitSyncState, UserInvestment
from settingsconfig.utils import get_setting_decimal
from wallets.models import Wallet
from wallets.services import credit_wallet, debit_wallet, get_primary_wallet
from adminpanel.utils import log_action


PROFIT_SYNC_SUMMARY_CACHE_KEY = 'investment_profit_sync_last_summary'
PROFIT_SYNC_SUMMARY_CACHE_TTL = 7 * 24 * 60 * 60
PROFIT_SYNC_LOCK_KEY = 'investment_profit_sync_lock'
PROFIT_SYNC_LOCK_TTL = 300
PROFIT_SYNC_LOCK_NAME = 'investment_profit_sync'

logger = logging.getLogger(__name__)


@dataclass(frozen=True)
class ProfitSyncLock:
    """
    Represents a held profit-sync lock.

    The cache token keeps the request-throttle lock releaseable, while the
    database row lock is what makes the lock safe across processes.
    """

    token: str
    mode: str


def get_investment_account(user) -> InvestmentAccount:
    account, _ = InvestmentAccount.objects.get_or_create(user=user)
    return account


def _plan_snapshot_kwargs(plan: InvestmentPlan) -> dict:
    return {
        'plan_snapshot_name': plan.name,
        'plan_snapshot_tier': plan.plan_tier,
        'plan_snapshot_daily_roi': plan.effective_daily_roi,
        'plan_snapshot_total_return': plan.effective_total_return,
        'plan_snapshot_duration_days': plan.duration_days,
        'plan_snapshot_payout_frequency': plan.payout_frequency,
        'plan_snapshot_liquidity_terms': plan.liquidity_terms,
        'plan_snapshot_lock_period_days': plan.lock_period_days,
        'plan_snapshot_management_fee_pct': plan.management_fee_pct,
        'plan_snapshot_early_withdrawal_fee_pct': plan.early_withdrawal_fee_pct,
        'plan_snapshot_risk_level': plan.risk_level,
        'plan_snapshot_capital_protection': plan.capital_protection,
    }


@transaction.atomic
def create_investment(
    user,
    plan: InvestmentPlan,
    amount: Decimal,
    *,
    wallet: Wallet | None = None,
    risk_acknowledged: bool = False,
) -> UserInvestment:
    if wallet is None:
        raise ValueError("Select a wallet for investments.")
    if wallet.user_id != user.id:
        raise ValueError("Selected wallet does not belong to this user.")
    wallet = Wallet.objects.select_for_update().get(pk=wallet.pk)
    if wallet.wallet_type != 'primary':
        raise ValueError("Investments can only be funded from the primary wallet.")
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
    investment_account = get_investment_account(user)
    investment = UserInvestment.objects.create(
        user=user,
        wallet=wallet,
        account=investment_account,
        plan=plan,
        amount=amount,
        end_date=end_date,
        risk_acknowledged=risk_acknowledged,
        **_plan_snapshot_kwargs(plan),
    )
    log_action(user, 'investment_created', 'investment', investment.id, {'plan': plan.name, 'amount': str(amount)})
    return investment


def _interval_days(payout_frequency: str) -> int:
    if payout_frequency == 'weekly':
        return 7
    if payout_frequency == 'monthly':
        return 30
    return 1


def _daily_profit_rate(investment: UserInvestment) -> Decimal:
    duration_days = investment.effective_duration_days
    if not duration_days:
        return Decimal('0')
    total_return = investment.effective_total_return
    if total_return and total_return > 0:
        return Decimal(total_return) / Decimal(duration_days)
    if investment.effective_daily_roi:
        return Decimal(investment.effective_daily_roi)
    return Decimal('0')


def _release_investment_to_primary_wallet(investment: UserInvestment) -> None:
    if investment.settled_at:
        return
    primary_wallet = get_primary_wallet(investment.user)
    if not primary_wallet:
        raise ValueError("Primary wallet not available for settlement.")
    credit_wallet(
        primary_wallet,
        investment.amount,
        'main',
        'investment',
        {'investment_id': investment.id, 'reason': 'principal_return'},
    )
    if investment.total_earned > 0:
        credit_wallet(
            primary_wallet,
            investment.total_earned,
            'profit',
            'profit',
            {'investment_id': investment.id, 'reason': 'profit_release'},
        )
    investment.settled_at = timezone.now()


def _acquire_profit_sync_lock() -> ProfitSyncLock | None:
    """
    Use a cache throttle for fast request skipping and a database row lock for
    real cross-process exclusion when the backend supports it.
    """
    lock_token = uuid.uuid4().hex
    if not cache.add(PROFIT_SYNC_LOCK_KEY, lock_token, timeout=PROFIT_SYNC_LOCK_TTL):
        return None

    if not connection.features.has_select_for_update:
        return ProfitSyncLock(token=lock_token, mode='cache')

    lock_state, _ = ProfitSyncState.objects.get_or_create(name=PROFIT_SYNC_LOCK_NAME)
    lock_kwargs = {}
    if getattr(connection.features, 'has_select_for_update_nowait', False):
        lock_kwargs['nowait'] = True

    try:
        ProfitSyncState.objects.select_for_update(**lock_kwargs).get(pk=lock_state.pk)
    except DatabaseError:
        if cache.get(PROFIT_SYNC_LOCK_KEY) == lock_token:
            cache.delete(PROFIT_SYNC_LOCK_KEY)
        return None

    return ProfitSyncLock(token=lock_token, mode='db')


def _release_profit_sync_lock(lock_handle: ProfitSyncLock | None) -> None:
    if not lock_handle:
        return
    lock_token = lock_handle.token
    if lock_token and cache.get(PROFIT_SYNC_LOCK_KEY) == lock_token:
        cache.delete(PROFIT_SYNC_LOCK_KEY)


def _quantize_money(value: Decimal) -> Decimal:
    return value.quantize(Decimal('0.01'))


def _build_due_schedule(investment: UserInvestment, cutoff_date):
    start_date = investment.start_date.date()
    end_date = investment.end_date.date()
    if cutoff_date <= start_date:
        return []

    interval = _interval_days(investment.effective_payout_frequency)
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

    lock_handle = _acquire_profit_sync_lock()
    if not lock_handle:
        logger.debug("Profit sync skipped because another run is already in progress.")
        return {
            'investments_checked': 0,
            'payouts_created': 0,
            'investments_completed': 0,
            'payouts_skipped': 0,
            'skipped_lock': True,
        }

    summary = {
        'investments_checked': 0,
        'payouts_created': 0,
        'investments_completed': 0,
        'payouts_skipped': 0,
    }
    try:
        investments = (
            UserInvestment.objects.select_related('plan', 'user', 'wallet', 'account')
            .filter(start_date__date__lte=process_date, is_completed=False)
            .order_by('pk')
        )

        for investment in investments.iterator(chunk_size=200):
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

                gross_profit = investment.amount * (_daily_profit_rate(investment) / Decimal('100')) * Decimal(period_days)
                fee_pct = investment.effective_management_fee_pct or Decimal('0')
                fee_amount = gross_profit * (fee_pct / Decimal('100'))
                net_profit = _quantize_money(gross_profit - fee_amount)
                if net_profit <= 0:
                    continue

                DailyProfit.objects.create(
                    investment=investment,
                    date=due_date,
                    amount=net_profit,
                )

                investment.total_earned += net_profit
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

            if investment.is_completed and not investment.settled_at:
                _release_investment_to_primary_wallet(investment)

            if created_any or should_be_completed:
                update_fields = ['total_earned', 'is_completed']
                if investment.settled_at:
                    update_fields.append('settled_at')
                investment.save(update_fields=update_fields)

        cache.set(
            PROFIT_SYNC_SUMMARY_CACHE_KEY,
            {
                'ran_at': timezone.now(),
                'process_date': process_date,
                **summary,
            },
            PROFIT_SYNC_SUMMARY_CACHE_TTL,
        )
        logger.info(
            "Profit sync complete checked=%s payouts=%s completed=%s date=%s",
            summary['investments_checked'],
            summary['payouts_created'],
            summary['investments_completed'],
            process_date,
        )
        return summary
    finally:
        _release_profit_sync_lock(lock_handle)


@transaction.atomic
def apply_daily_profits(process_date=None) -> int:
    summary = sync_investment_profits(process_date=process_date)
    return summary['payouts_created']


def can_withdraw(user, amount: Decimal, *, wallet=None) -> tuple[bool, str]:
    min_amount = get_setting_decimal('MIN_WITHDRAWAL_AMOUNT', default='10')
    if amount < min_amount:
        return False, f"Minimum withdrawal is {min_amount}."

    if wallet is not None and not wallet.has_non_bonus_credit:
        return False, "You cannot withdraw welcome bonus only. Invest first in order to be able to withdraw."

    if wallet is not None and getattr(wallet, 'wallet_type', '') != 'primary':
        return False, "Withdrawals are only allowed from the primary wallet."

    return True, "OK"
