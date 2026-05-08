from datetime import timedelta
from decimal import Decimal

from django.contrib.auth.models import User
from django.test import TestCase
from django.urls import reverse
from django.utils import timezone

from investments.models import InvestmentPlan, UserInvestment
from wallets.services import get_primary_wallet
from investments.services import get_investment_account


class AdminPlanCloneTests(TestCase):
    def setUp(self):
        self.staff = User.objects.create_user(
            username='admin',
            email='admin@example.com',
            password='pass12345',
            is_staff=True,
        )
        self.plan = InvestmentPlan.objects.create(
            name='Growth Plan',
            plan_tier='standard',
            min_amount=Decimal('100.00'),
            max_amount=Decimal('1000.00'),
            total_return=Decimal('30.00'),
            duration_days=3,
            description='Original plan',
            risk_level='moderate',
            payout_frequency='daily',
            liquidity_terms='locked',
            lock_period_days=0,
            management_fee_pct=Decimal('1.00'),
            capital_protection=True,
            early_withdrawal_fee_pct=Decimal('0.00'),
            is_active=True,
        )

    def test_clone_plan_creates_new_draft_version(self):
        self.client.force_login(self.staff)

        response = self.client.post(reverse('admin_plan_clone', args=[self.plan.id]))

        self.assertEqual(response.status_code, 302)
        cloned = InvestmentPlan.objects.exclude(pk=self.plan.pk).get(source_plan=self.plan)
        self.assertEqual(cloned.version_number, self.plan.version_number + 1)
        self.assertEqual(cloned.name, f'{self.plan.name} {cloned.version_number}')
        self.assertFalse(cloned.is_active)
        self.assertEqual(cloned.total_return, self.plan.total_return)
        self.assertEqual(cloned.daily_roi, self.plan.daily_roi)
        self.assertEqual(cloned.payout_frequency, self.plan.payout_frequency)
        self.assertIn(f'edit={cloned.id}', response.url)


class AdminInvestmentLedgerTests(TestCase):
    def setUp(self):
        self.staff = User.objects.create_user(
            username='staff',
            email='staff@example.com',
            password='pass12345',
            is_staff=True,
        )
        self.user = User.objects.create_user(
            username='investor',
            email='investor@example.com',
            password='pass12345',
        )
        self.wallet = get_primary_wallet(self.user)
        self.account = get_investment_account(self.user)
        self.plan = InvestmentPlan.objects.create(
            name='Ledger Plan',
            plan_tier='standard',
            min_amount=Decimal('100.00'),
            max_amount=Decimal('1000.00'),
            total_return=Decimal('30.00'),
            duration_days=3,
            description='Ledger test plan',
            risk_level='moderate',
            payout_frequency='daily',
            liquidity_terms='locked',
            lock_period_days=0,
            management_fee_pct=Decimal('1.00'),
            capital_protection=True,
            early_withdrawal_fee_pct=Decimal('0.00'),
            is_active=True,
        )
        active = UserInvestment.objects.create(
            user=self.user,
            wallet=self.wallet,
            account=self.account,
            plan=self.plan,
            amount=Decimal('100.00'),
            end_date=timezone.now() + timedelta(days=3),
            total_earned=Decimal('10.00'),
        )
        active.snapshot_plan_terms(self.plan)
        active.save(update_fields=[
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
        ])
        settled = UserInvestment.objects.create(
            user=self.user,
            wallet=self.wallet,
            account=self.account,
            plan=self.plan,
            amount=Decimal('50.00'),
            end_date=timezone.now() - timedelta(days=1),
            total_earned=Decimal('5.00'),
            is_completed=True,
            settled_at=timezone.now(),
        )
        settled.snapshot_plan_terms(self.plan)
        settled.save(update_fields=[
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
        ])

    def test_admin_can_view_investment_ledger(self):
        self.client.force_login(self.staff)

        response = self.client.get(reverse('admin_investment_ledger'))

        self.assertEqual(response.status_code, 200)
        self.assertContains(response, 'Investment Ledger')
        self.assertContains(response, 'investor')
        self.assertContains(response, '100.00')
        self.assertContains(response, '50.00')
        self.assertContains(response, '10.00')
        self.assertContains(response, '5.00')

    def test_admin_can_open_single_user_ledger_history(self):
        self.client.force_login(self.staff)

        response = self.client.get(reverse('admin_investment_ledger_user', args=[self.user.id]))

        self.assertEqual(response.status_code, 200)
        self.assertContains(response, 'investor ledger history')
        self.assertContains(response, 'Ledger Plan')
        self.assertContains(response, 'Settled')
        self.assertContains(response, 'Active')
