from decimal import Decimal

from django.contrib.auth.models import User
from django.test import TestCase

from withdrawals.forms import WithdrawalCreateForm
from investments.services import can_withdraw
from payments.models import CryptoCurrency
from wallets.services import credit_wallet, get_primary_wallet


class WithdrawalBonusRuleTests(TestCase):
    def setUp(self):
        self.user = User.objects.create_user(username='tester', email='tester@example.com', password='pass12345')
        self.wallet = get_primary_wallet(self.user)
        self.crypto, _ = CryptoCurrency.objects.get_or_create(
            symbol='USDT',
            network='TRC20',
            defaults={'name': 'Tether', 'is_active': True},
        )

    def test_bonus_only_wallet_cannot_withdraw(self):
        self.wallet.refresh_from_db()
        self.assertFalse(self.wallet.has_non_bonus_credit)
        self.assertEqual(self.wallet.withdrawable_balance, Decimal('0'))

        allowed, reason = can_withdraw(self.user, Decimal('10.00'), wallet=self.wallet)
        self.assertFalse(allowed)
        self.assertIn('welcome bonus only', reason.lower())

    def test_deposit_plus_bonus_can_withdraw_total_balance(self):
        credit_wallet(self.wallet, Decimal('100.00'), 'main', 'deposit', {'reason': 'bank_deposit'})
        self.wallet.refresh_from_db()

        self.assertTrue(self.wallet.has_non_bonus_credit)
        self.assertEqual(self.wallet.withdrawable_balance, self.wallet.total_balance)

        allowed, reason = can_withdraw(self.user, Decimal('50.00'), wallet=self.wallet)
        self.assertTrue(allowed, reason)

    def test_withdrawal_form_hides_optional_routing_fields(self):
        form = WithdrawalCreateForm(user=self.user)
        crypto_choices = list(form.fields['crypto'].queryset.values_list('symbol', 'network'))

        self.assertEqual(form.fields['method'].widget.__class__.__name__, 'HiddenInput')
        self.assertEqual(form.fields['destination_network'].widget.__class__.__name__, 'HiddenInput')
        self.assertEqual(form.fields['memo_tag'].widget.__class__.__name__, 'HiddenInput')
        self.assertEqual(form.fields['crypto'].widget.__class__.__name__, 'Select')
        self.assertEqual(crypto_choices, [('USDT', 'TRC20')])
        self.assertEqual(form.fields['crypto'].empty_label, 'Select crypto')
        self.assertEqual(form.fields['crypto'].initial, self.crypto.pk)
        self.assertIn('Payout wallet address', form.fields['wallet_address'].widget.attrs.get('placeholder', ''))
        self.assertIn('TRC20 is the current network', form.fields['crypto'].help_text)
