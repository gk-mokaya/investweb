from decimal import Decimal

from django.contrib.auth.models import User
from django.test import TestCase

from investments.services import can_withdraw
from wallets.services import credit_wallet, get_primary_wallet


class WithdrawalBonusRuleTests(TestCase):
    def setUp(self):
        self.user = User.objects.create_user(username='tester', email='tester@example.com', password='pass12345')
        self.wallet = get_primary_wallet(self.user)

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
