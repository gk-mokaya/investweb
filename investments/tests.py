from datetime import datetime, timedelta
from decimal import Decimal

from django.contrib.auth.models import User
from django.test import TestCase
from django.utils import timezone

from investments.models import DailyProfit, InvestmentPlan, UserInvestment
from investments.services import apply_daily_profits, sync_investment_profits
from wallets.models import Wallet
from wallets.services import get_primary_wallet


class InvestmentProfitSyncTests(TestCase):
    def setUp(self):
        self.user = User.objects.create_user(username='alice', email='alice@example.com', password='pass12345')
        self.wallet = get_primary_wallet(self.user)
        self.wallet.main_balance = Decimal('0')
        self.wallet.bonus_balance = Decimal('0')
        self.wallet.profit_balance = Decimal('0')
        self.wallet.is_active = True
        self.wallet.save(update_fields=['main_balance', 'bonus_balance', 'profit_balance', 'is_active'])

    def _create_plan(self, *, payout_frequency='daily', duration_days=3, daily_roi='10.00'):
        return InvestmentPlan.objects.create(
            name=f'{payout_frequency.title()} Plan',
            plan_tier='standard',
            min_amount=Decimal('10'),
            max_amount=Decimal('100000'),
            daily_roi=Decimal(daily_roi),
            duration_days=duration_days,
            total_return=Decimal('0'),
            payout_frequency=payout_frequency,
            liquidity_terms='locked',
            lock_period_days=0,
            management_fee_pct=Decimal('0'),
            capital_protection=True,
            early_withdrawal_fee_pct=Decimal('0'),
            is_active=True,
        )

    def _create_investment(self, plan, *, amount='100.00', start_dt=None):
        start_dt = start_dt or timezone.make_aware(datetime(2026, 1, 1, 10, 0, 0))
        investment = UserInvestment.objects.create(
            user=self.user,
            wallet=self.wallet,
            plan=plan,
            amount=Decimal(amount),
            end_date=start_dt + timedelta(days=plan.duration_days),
        )
        UserInvestment.objects.filter(pk=investment.pk).update(start_date=start_dt)
        return UserInvestment.objects.get(pk=investment.pk)

    def test_daily_profits_are_credited_and_investment_completes(self):
        plan = self._create_plan(payout_frequency='daily', duration_days=3, daily_roi='10.00')
        investment = self._create_investment(plan, amount='100.00')

        summary = sync_investment_profits(process_date=investment.end_date.date())

        self.wallet.refresh_from_db()
        investment.refresh_from_db()
        self.assertEqual(summary['payouts_created'], 3)
        self.assertEqual(DailyProfit.objects.filter(investment=investment).count(), 3)
        self.assertEqual(self.wallet.profit_balance, Decimal('30.00'))
        self.assertEqual(investment.total_earned, Decimal('30.00'))
        self.assertTrue(investment.is_completed)

    def test_weekly_schedule_handles_final_partial_period(self):
        plan = self._create_plan(payout_frequency='weekly', duration_days=10, daily_roi='5.00')
        investment = self._create_investment(plan, amount='100.00')

        sync_investment_profits(process_date=investment.end_date.date())

        payouts = list(DailyProfit.objects.filter(investment=investment).order_by('date').values_list('amount', flat=True))
        self.assertEqual(len(payouts), 2)
        self.assertEqual(payouts[0], Decimal('35.00'))
        self.assertEqual(payouts[1], Decimal('15.00'))

    def test_repeated_sync_is_idempotent(self):
        plan = self._create_plan(payout_frequency='daily', duration_days=2, daily_roi='10.00')
        investment = self._create_investment(plan, amount='100.00')

        first = apply_daily_profits(process_date=investment.end_date.date())
        second = apply_daily_profits(process_date=investment.end_date.date())

        self.wallet.refresh_from_db()
        self.assertEqual(first, 2)
        self.assertEqual(second, 0)
        self.assertEqual(DailyProfit.objects.filter(investment=investment).count(), 2)
        self.assertEqual(self.wallet.profit_balance, Decimal('20.00'))
