from datetime import datetime, timedelta
from decimal import Decimal
from django.core.files.uploadedfile import SimpleUploadedFile

from django.contrib.auth.models import User
from django.core.cache import cache
from django.db import transaction
from django.test import TestCase
from django.utils import timezone
from django.urls import reverse

from deposits.models import Deposit
from investments.forms import CreateInvestmentForm
from investments.models import DailyProfit, InvestmentPlan, UserInvestment
from investments.services import (
    PROFIT_SYNC_SUMMARY_CACHE_KEY,
    _acquire_profit_sync_lock,
    _release_profit_sync_lock,
    apply_daily_profits,
    create_pending_investment_request,
    sync_investment_profits,
)
from payments.models import CryptoCurrency
from kyc.models import KYCProfile
from wallets.models import Wallet
from wallets.services import get_primary_wallet


class InvestmentProfitSyncTests(TestCase):
    def setUp(self):
        self.user = User.objects.create_user(username='alice', email='alice@example.com', password='pass12345')
        self.wallet = get_primary_wallet(self.user)
        self.account = self.user.investment_account
        self.crypto, _ = CryptoCurrency.objects.get_or_create(
            symbol='USDT',
            network='TRC20',
            defaults={
                'name': 'Tether',
                'is_active': True,
            },
        )
        kyc_profile, _ = KYCProfile.objects.get_or_create(user=self.user)
        kyc_profile.status = 'verified'
        kyc_profile.save(update_fields=['status'])
        self.wallet.main_balance = Decimal('0')
        self.wallet.bonus_balance = Decimal('0')
        self.wallet.profit_balance = Decimal('0')
        self.wallet.is_active = True
        self.wallet.save(update_fields=['main_balance', 'bonus_balance', 'profit_balance', 'is_active'])

    def _create_plan(self, *, payout_frequency='daily', duration_days=3, total_return='30.00'):
        return InvestmentPlan.objects.create(
            name=f'{payout_frequency.title()} Plan',
            plan_tier='standard',
            min_amount=Decimal('10'),
            max_amount=Decimal('100000'),
            total_return=Decimal(total_return),
            duration_days=duration_days,
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
            account=self.account,
            plan=plan,
            amount=Decimal(amount),
            end_date=start_dt + timedelta(days=plan.duration_days),
        )
        investment.snapshot_plan_terms(plan)
        investment.save(
            update_fields=[
                'plan_snapshot_name',
                'plan_snapshot_tier',
                'plan_snapshot_daily_roi',
                'plan_snapshot_total_return',
                'plan_snapshot_duration_days',
                'plan_snapshot_payout_frequency',
                'plan_snapshot_liquidity_terms',
                'plan_snapshot_lock_period_days',
                'plan_snapshot_management_fee_pct',
                'plan_snapshot_early_withdrawal_fee_pct',
                'plan_snapshot_risk_level',
                'plan_snapshot_capital_protection',
            ]
        )
        UserInvestment.objects.filter(pk=investment.pk).update(start_date=start_dt)
        return UserInvestment.objects.get(pk=investment.pk)

    def test_daily_profits_are_credited_and_investment_completes(self):
        plan = self._create_plan(payout_frequency='daily', duration_days=3, total_return='30.00')
        investment = self._create_investment(plan, amount='100.00')

        summary = sync_investment_profits(process_date=investment.end_date.date())

        self.wallet.refresh_from_db()
        investment.refresh_from_db()
        self.account.refresh_from_db()
        self.assertEqual(summary['payouts_created'], 3)
        self.assertEqual(DailyProfit.objects.filter(investment=investment).count(), 3)
        self.assertEqual(self.wallet.main_balance, Decimal('100.00'))
        self.assertEqual(self.wallet.profit_balance, Decimal('30.00'))
        self.assertEqual(investment.total_earned, Decimal('30.00'))
        self.assertTrue(investment.is_completed)
        self.assertIsNotNone(investment.settled_at)
        self.assertEqual(self.account.current_balance, Decimal('0'))
        self.assertEqual(plan.daily_roi, Decimal('10.00'))

    def test_weekly_schedule_handles_final_partial_period(self):
        plan = self._create_plan(payout_frequency='weekly', duration_days=10, total_return='50.00')
        investment = self._create_investment(plan, amount='100.00')

        sync_investment_profits(process_date=investment.end_date.date())

        payouts = list(DailyProfit.objects.filter(investment=investment).order_by('date').values_list('amount', flat=True))
        self.assertEqual(len(payouts), 2)
        self.assertEqual(payouts[0], Decimal('35.00'))
        self.assertEqual(payouts[1], Decimal('15.00'))

    def test_existing_investments_keep_their_snapshot_when_plan_changes(self):
        plan = self._create_plan(payout_frequency='daily', duration_days=3, total_return='30.00')
        investment = self._create_investment(plan, amount='100.00')

        plan.total_return = Decimal('70.00')
        plan.duration_days = 7
        plan.payout_frequency = 'weekly'
        plan.save()

        summary = sync_investment_profits(process_date=investment.end_date.date())

        investment.refresh_from_db()
        self.assertEqual(summary['payouts_created'], 3)
        self.assertEqual(investment.plan_snapshot_total_return, Decimal('30.00'))
        self.assertEqual(investment.plan_snapshot_duration_days, 3)
        self.assertEqual(investment.plan_snapshot_payout_frequency, 'daily')
        self.assertEqual(investment.total_earned, Decimal('30.00'))

    def test_monthly_schedule_uses_monthly_interval(self):
        plan = self._create_plan(payout_frequency='monthly', duration_days=45, total_return='45.00')
        investment = self._create_investment(plan, amount='100.00')

        sync_investment_profits(process_date=investment.end_date.date())

        payouts = list(DailyProfit.objects.filter(investment=investment).order_by('date').values_list('amount', flat=True))
        self.assertEqual(len(payouts), 2)
        self.assertEqual(payouts[0], Decimal('30.00'))
        self.assertEqual(payouts[1], Decimal('15.00'))

    def test_repeated_sync_is_idempotent(self):
        plan = self._create_plan(payout_frequency='daily', duration_days=2, total_return='20.00')
        investment = self._create_investment(plan, amount='100.00')

        first = apply_daily_profits(process_date=investment.end_date.date())
        second = apply_daily_profits(process_date=investment.end_date.date())

        self.wallet.refresh_from_db()
        self.assertEqual(first, 2)
        self.assertEqual(second, 0)
        self.assertEqual(DailyProfit.objects.filter(investment=investment).count(), 2)
        self.assertEqual(self.wallet.profit_balance, Decimal('20.00'))

    def test_sync_summary_is_cached_for_admin_dashboard(self):
        plan = self._create_plan(payout_frequency='daily', duration_days=1, total_return='10.00')
        investment = self._create_investment(plan, amount='100.00')

        cache.delete(PROFIT_SYNC_SUMMARY_CACHE_KEY)
        sync_investment_profits(process_date=investment.end_date.date())

        summary = cache.get(PROFIT_SYNC_SUMMARY_CACHE_KEY)
        self.assertIsNotNone(summary)
        self.assertEqual(summary['payouts_created'], 1)
        self.assertEqual(summary['investments_completed'], 1)

    def test_second_sync_skips_when_lock_is_held(self):
        plan = self._create_plan(payout_frequency='daily', duration_days=1, total_return='10.00')
        investment = self._create_investment(plan, amount='100.00')

        with transaction.atomic():
            lock_handle = _acquire_profit_sync_lock()
            self.assertIsNotNone(lock_handle)
            try:
                summary = sync_investment_profits(process_date=investment.end_date.date())
            finally:
                _release_profit_sync_lock(lock_handle)

        self.wallet.refresh_from_db()
        investment.refresh_from_db()
        self.assertTrue(summary['skipped_lock'])
        self.assertEqual(summary['payouts_created'], 0)
        self.assertEqual(DailyProfit.objects.filter(investment=investment).count(), 0)
        self.assertEqual(self.wallet.profit_balance, Decimal('0'))
        self.assertFalse(investment.is_completed)

    def test_dashboard_page_renders_for_logged_in_user(self):
        from kyc.models import KYCProfile

        KYCProfile.objects.filter(user=self.user).update(status='verified')
        self.client.force_login(self.user)

        response = self.client.get(reverse('dashboard'))

        self.assertEqual(response.status_code, 200)
        self.assertContains(response, 'A compact control center for balances, investment flow, and plan health.')

    def test_investment_form_rejects_amount_below_plan_minimum(self):
        plan = self._create_plan(payout_frequency='daily', duration_days=3, total_return='30.00')
        form = CreateInvestmentForm(
            data={
                'plan': str(plan.id),
                'amount': '5.00',
                'wallet': str(self.wallet.id),
            },
            user=self.user,
        )

        self.assertFalse(form.is_valid())
        self.assertIn('Amount must be at least', form.errors['amount'][0])

    def test_pending_investment_reserves_bonus_balance(self):
        self.wallet.bonus_balance = Decimal('10.00')
        self.wallet.save(update_fields=['bonus_balance'])
        plan = self._create_plan(payout_frequency='daily', duration_days=3, total_return='30.00')

        pending = create_pending_investment_request(self.user, plan, Decimal('100.00'), wallet=self.wallet)

        self.wallet.refresh_from_db()
        pending.refresh_from_db()

        self.assertEqual(self.wallet.bonus_balance, Decimal('0.00'))
        self.assertEqual(pending.status, 'pending')
        self.assertEqual(pending.reserved_bonus_amount, Decimal('10.00'))

    def test_shortfall_redirects_to_deposit_without_creating_investment(self):
        self.wallet.main_balance = Decimal('10.00')
        self.wallet.save(update_fields=['main_balance'])
        plan = self._create_plan(payout_frequency='daily', duration_days=3, total_return='30.00')
        self.client.force_login(self.user)

        response = self.client.post(
            reverse('create_investment'),
            {
                'plan': str(plan.id),
                'amount': '100.00',
                'wallet': str(self.wallet.id),
            },
        )

        self.assertEqual(response.status_code, 302)
        self.assertIn(reverse('deposit_list'), response['Location'])
        self.assertEqual(UserInvestment.objects.count(), 0)

    def test_deposit_completion_creates_deposit_and_investment_together(self):
        self.wallet.main_balance = Decimal('10.00')
        self.wallet.save(update_fields=['main_balance'])
        plan = self._create_plan(payout_frequency='daily', duration_days=3, total_return='30.00')
        self.client.force_login(self.user)

        invest_response = self.client.post(
            reverse('create_investment'),
            {
                'plan': str(plan.id),
                'amount': '100.00',
                'wallet': str(self.wallet.id),
            },
        )
        self.assertEqual(invest_response.status_code, 302)
        self.assertIn(reverse('deposit_list'), invest_response['Location'])
        self.assertEqual(UserInvestment.objects.count(), 0)

        deposit_response = self.client.post(
            reverse('deposit_create'),
            {
                'wallet': str(self.wallet.id),
                'crypto': str(self.crypto.id),
                'amount': '100.00',
                'sender_address': 'tester@example.com',
                'screenshot': SimpleUploadedFile('proof.png', b'fake-image-bytes', content_type='image/png'),
                'source': 'investment',
                'deposit_step': '2',
                'minimum_amount': '90.00',
                'investment_plan': str(plan.id),
                'investment_amount': '100.00',
                'investment_wallet': str(self.wallet.id),
            },
        )

        self.assertEqual(deposit_response.status_code, 302)
        self.assertEqual(Deposit.objects.count(), 1)
        self.assertEqual(UserInvestment.objects.count(), 1)
        investment = UserInvestment.objects.first()
        deposit = Deposit.objects.first()
        self.assertEqual(investment.status, 'pending')
        self.assertEqual(deposit.investment_request_id, investment.id)


class PublicMarketingPagesTests(TestCase):
    def setUp(self):
        InvestmentPlan.objects.create(
            name='Starter Growth',
            plan_tier='starter',
            min_amount=Decimal('10.00'),
            max_amount=Decimal('100.00'),
            duration_days=7,
            total_return=Decimal('14.00'),
            description='A simple entry plan for new investors.',
            risk_level='low',
            payout_frequency='daily',
            liquidity_terms='flexible',
            lock_period_days=0,
            management_fee_pct=Decimal('0.00'),
            capital_protection=True,
            early_withdrawal_fee_pct=Decimal('0.00'),
            is_active=True,
        )

    def test_public_home_page_is_accessible(self):
        response = self.client.get(reverse('home'))

        self.assertEqual(response.status_code, 200)
        self.assertContains(response, 'How it works')

    def test_public_plans_page_is_accessible(self):
        response = self.client.get(reverse('plans'))

        self.assertEqual(response.status_code, 200)
        self.assertContains(response, 'Starter Growth')

    def test_authenticated_user_can_still_open_public_plans_page(self):
        user = User.objects.create_user(username='publicuser', email='public@example.com', password='pass12345')
        self.client.force_login(user)

        response = self.client.get(reverse('plans'))

        self.assertEqual(response.status_code, 200)
        self.assertNotContains(response, 'Preview mode')
        self.assertContains(response, 'New Investment')
        self.assertContains(response, 'Dashboard')

    def test_authenticated_verified_user_can_open_investments_page(self):
        user = User.objects.create_user(username='investor', email='investor@example.com', password='pass12345')
        from kyc.models import KYCProfile

        KYCProfile.objects.filter(user=user).update(status='verified')
        self.client.force_login(user)

        response = self.client.get(reverse('my_investments'))

        self.assertEqual(response.status_code, 200)
        self.assertContains(response, 'Investment history')
