from decimal import Decimal

from django.contrib.auth.models import User
from django.test import TestCase
from django.utils import timezone

from deposits.forms import DepositCreateForm
from deposits.models import Deposit
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
        crypto_choices = list(form.fields['crypto'].queryset.values_list('symbol', 'network'))

        self.assertEqual(crypto_choices, [('USDT', 'TRC20')])
        self.assertEqual(form.fields['crypto'].empty_label, 'USDT (TRC20)')

    def test_completing_manual_deposit_credits_wallet_once(self):
        deposit = Deposit.objects.create(
            user=self.user,
            wallet=self.wallet,
            amount=Decimal('100.00'),
            crypto=self.crypto,
            method='manual',
            transaction_hash='0xabc123',
            sender_address='TManualSender',
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
