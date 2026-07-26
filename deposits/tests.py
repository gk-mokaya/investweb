from decimal import Decimal

from django.contrib.auth.models import User
from django.test import TestCase
from django.utils import timezone
from django.core.files.uploadedfile import SimpleUploadedFile

from deposits.forms import DepositCreateForm
from deposits.models import Deposit
from investments.models import InvestmentPlan
from investments.services import create_pending_investment_request
from payments.models import CryptoCurrency
from wallets.models import Wallet
from wallets.services import get_primary_wallet


class DepositManualFlowTests(TestCase):
    def setUp(self):
        self.user = User.objects.create_user(username='tester', email='tester@example.com', password='pass12345')
        self.staff = User.objects.create_user(
            username='reviewer',
            email='reviewer@example.com',
            password='pass12345',
            is_staff=True,
        )
        self.wallet = get_primary_wallet(self.user)
        self.crypto, _ = CryptoCurrency.objects.get_or_create(
            symbol='USDT',
            network='TRC20',
            defaults={'name': 'Tether', 'is_active': True},
        )

    def test_manual_deposit_form_limits_crypto_to_usdt_trc20(self):
        form = DepositCreateForm(user=self.user)
        primary_wallet = get_primary_wallet(self.user)
        crypto_choices = list(form.fields['crypto'].queryset.values_list('symbol', 'network'))

        self.assertEqual(crypto_choices, [('USDT', 'TRC20')])
        self.assertEqual(form.fields['crypto'].widget.__class__.__name__, 'Select')
        self.assertTrue(form.fields['wallet'].disabled)
        self.assertTrue(form.fields['crypto'].disabled)
        self.assertEqual(form.fields['wallet'].initial, primary_wallet.pk)
        self.assertEqual(form.fields['crypto'].initial, self.crypto.pk)
        self.assertEqual(form.fields['amount'].label, 'Amount withdrawn')
        self.assertEqual(form.fields['sender_address'].label, 'Sender email or Binance ID')
        self.assertEqual(form.fields['screenshot'].label, 'Transaction screenshot')
        self.assertTrue(form.fields['screenshot'].required)

    def test_manual_deposit_form_enforces_minimum_top_up(self):
        form = DepositCreateForm(
            data={
                'amount': '50.00',
                'sender_address': 'investor@example.com',
                'minimum_amount': '100.00',
            },
            user=self.user,
            minimum_amount='100.00',
        )

        self.assertFalse(form.is_valid())
        self.assertIn('Deposit amount must be at least', form.errors['amount'][0])

    def test_completing_manual_deposit_credits_wallet_once(self):
        deposit = Deposit.objects.create(
            user=self.user,
            wallet=self.wallet,
            amount=Decimal('100.00'),
            crypto=self.crypto,
            method='manual',
            transaction_hash='0xabc123',
            sender_address='TManualSender',
            screenshot=SimpleUploadedFile('deposit-proof.png', b'fake-image-bytes', content_type='image/png'),
            status='pending',
        )

        deposit.reviewed_by = self.staff
        deposit.reviewed_at = timezone.now()
        deposit.review_note = 'Approved after manual review.'
        deposit.status = 'completed'
        deposit.save()

        deposit.refresh_from_db()
        self.wallet.refresh_from_db()

        self.assertEqual(self.wallet.main_balance, Decimal('150.00'))
        self.assertEqual(self.wallet.total_balance, Decimal('150.00'))
        self.assertEqual(deposit.status, 'completed')
        self.assertIsNotNone(deposit.completed_at)
        self.assertEqual(deposit.reviewed_by, self.staff)

    def test_rejected_linked_deposit_restores_reserved_bonus(self):
        self.wallet.bonus_balance = Decimal('10.00')
        self.wallet.save(update_fields=['bonus_balance'])
        plan = InvestmentPlan.objects.create(
            name='Starter Growth',
            plan_tier='starter',
            min_amount=Decimal('10.00'),
            max_amount=Decimal('1000.00'),
            duration_days=7,
            total_return=Decimal('14.00'),
            description='Test plan.',
            risk_level='low',
            payout_frequency='daily',
            liquidity_terms='locked',
            lock_period_days=0,
            management_fee_pct=Decimal('0.00'),
            capital_protection=True,
            early_withdrawal_fee_pct=Decimal('0.00'),
            is_active=True,
        )
        pending = create_pending_investment_request(self.user, plan, Decimal('100.00'), wallet=self.wallet)
        self.wallet.refresh_from_db()
        self.assertEqual(self.wallet.bonus_balance, Decimal('0.00'))

        deposit = Deposit.objects.create(
            user=self.user,
            wallet=self.wallet,
            amount=Decimal('90.00'),
            crypto=self.crypto,
            method='manual',
            transaction_hash='0xabc999',
            sender_address='TManualSender',
            screenshot=SimpleUploadedFile('deposit-proof.png', b'fake-image-bytes', content_type='image/png'),
            investment_request=pending,
            status='pending',
        )
        deposit.reviewed_by = self.staff
        deposit.reviewed_at = timezone.now()
        deposit.review_note = 'Rejected after manual review.'
        deposit.status = 'rejected'
        deposit.save()

        deposit.refresh_from_db()
        pending.refresh_from_db()
        self.wallet.refresh_from_db()

        self.assertEqual(pending.status, 'cancelled')
        self.assertEqual(self.wallet.bonus_balance, Decimal('10.00'))
