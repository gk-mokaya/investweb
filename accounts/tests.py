from decimal import Decimal

from django.contrib.auth.models import User
from django.test import TestCase

from accounts.models import Notification
from settingsconfig.models import SystemSetting
from kyc.models import KYCProfile
from wallets.models import Wallet


class WelcomeBonusSignalTests(TestCase):
    def test_new_user_receives_bonus_in_primary_wallet(self):
        SystemSetting.objects.update_or_create(key='WELCOME_BONUS', defaults={'value': '25'})
        SystemSetting.objects.update_or_create(key='CURRENCY', defaults={'value': 'USD'})

        user = User.objects.create_user(username='alpha', email='alpha@example.com', password='pass12345')
        wallet = Wallet.objects.get(user=user, wallet_type='primary')

        self.assertEqual(wallet.main_balance, Decimal('25'))
        self.assertTrue(Notification.objects.filter(user=user, title='Welcome bonus credited').exists())

    def test_profile_update_changes_personal_details_without_email(self):
        user = User.objects.create_user(username='bravo', email='bravo@example.com', password='pass12345')
        profile = KYCProfile.objects.get(user=user)
        self.client.force_login(user)

        response = self.client.post(
            '/accounts/profile/',
            {
                'action': 'profile_update',
                'first_name': 'Brian',
                'last_name': 'Stone',
                'phone_number': '+254700111222',
                'country': 'Kenya',
                'address_line': '123 Main Street',
                'city': 'Nairobi',
                'postal_code': '00100',
                'country_of_residence': 'Kenya',
            },
            follow=True,
        )

        user.refresh_from_db()
        profile.refresh_from_db()
        self.assertEqual(response.status_code, 200)
        self.assertEqual(user.email, 'bravo@example.com')
        self.assertEqual(user.first_name, 'Brian')
        self.assertEqual(user.last_name, 'Stone')
        self.assertEqual(profile.phone_number, '+254700111222')
        self.assertEqual(profile.country_of_residence, 'Kenya')
        self.assertEqual(profile.full_name, 'Brian Stone')
