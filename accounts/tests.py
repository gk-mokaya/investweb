from decimal import Decimal

from django.contrib.auth.models import User
from django.contrib.sessions.middleware import SessionMiddleware
from django.http import HttpResponse
from django.test import RequestFactory, TestCase
from django.urls import reverse

from accounts.models import Notification
from accounts.middleware import BrowserFingerprintMiddleware
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
        self.assertTrue(hasattr(user, 'investment_account'))

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


class AuthRedirectTests(TestCase):
    def test_authenticated_users_are_redirected_away_from_login(self):
        user = User.objects.create_user(
            username='stafflogin',
            email='stafflogin@example.com',
            password='pass12345',
            is_staff=True,
        )
        self.client.force_login(user)

        response = self.client.get(reverse('login'))

        self.assertEqual(response.status_code, 302)
        self.assertEqual(response.url, reverse('dashboard'))

    def test_authenticated_users_are_redirected_away_from_register(self):
        user = User.objects.create_user(
            username='staffregister',
            email='staffregister@example.com',
            password='pass12345',
            is_staff=True,
        )
        self.client.force_login(user)

        response = self.client.get(reverse('register'))

        self.assertEqual(response.status_code, 302)
        self.assertEqual(response.url, reverse('dashboard'))


class BrowserFingerprintMiddlewareTests(TestCase):
    def setUp(self):
        self.user = User.objects.create_user(username='fingerprint', email='fingerprint@example.com', password='pass12345')
        self.factory = RequestFactory()

    def _attach_session(self, request):
        middleware = SessionMiddleware(lambda req: HttpResponse())
        middleware.process_request(request)
        request.session.save()
        return request

    def test_header_drift_does_not_log_user_out(self):
        middleware = BrowserFingerprintMiddleware(lambda req: HttpResponse('ok'))

        request1 = self.factory.get(
            '/dashboard/',
            HTTP_ACCEPT='text/html,application/xhtml+xml,application/xml;q=0.9',
            HTTP_ACCEPT_LANGUAGE='en-US,en;q=0.9',
            HTTP_ACCEPT_ENCODING='gzip, deflate, br',
            HTTP_USER_AGENT='Mozilla/5.0',
        )
        self._attach_session(request1)
        request1.user = self.user

        response1 = middleware(request1)
        self.assertEqual(response1.status_code, 200)
        first_fingerprint = request1.session.get('browser_fingerprint')
        self.assertTrue(first_fingerprint)

        request2 = self.factory.get(
            '/plans/',
            HTTP_ACCEPT='text/html,application/xhtml+xml',
            HTTP_ACCEPT_LANGUAGE='en-US,en;q=0.9',
            HTTP_ACCEPT_ENCODING='gzip, deflate, br',
            HTTP_USER_AGENT='Mozilla/5.0',
        )
        request2.session = request1.session
        request2.user = self.user

        response2 = middleware(request2)
        self.assertEqual(response2.status_code, 200)
        self.assertTrue(request2.user.is_authenticated)
        self.assertTrue(request2.session.get('browser_fingerprint'))
