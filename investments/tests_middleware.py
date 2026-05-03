from django.contrib.auth.models import User
from django.contrib.auth.models import AnonymousUser
from django.core.cache import cache
from django.test import RequestFactory, TestCase
from unittest.mock import patch

from investments.middleware import InvestmentProfitSyncMiddleware


class InvestmentProfitSyncMiddlewareTests(TestCase):
    def setUp(self):
        self.user = User.objects.create_user(username='tester', email='tester@example.com', password='pass12345')
        self.factory = RequestFactory()

    def test_authenticated_requests_trigger_throttled_profit_sync(self):
        request = self.factory.get('/')
        request.user = self.user

        cache.delete(InvestmentProfitSyncMiddleware.cache_key)
        with patch('investments.middleware.sync_investment_profits') as sync_mock:
            middleware = InvestmentProfitSyncMiddleware(lambda req: None)
            middleware(request)
            middleware(request)

        self.assertEqual(sync_mock.call_count, 1)

    def test_unauthenticated_requests_do_not_trigger_profit_sync(self):
        request = self.factory.get('/')
        request.user = AnonymousUser()

        cache.delete(InvestmentProfitSyncMiddleware.cache_key)
        with patch('investments.middleware.sync_investment_profits') as sync_mock:
            middleware = InvestmentProfitSyncMiddleware(lambda req: None)
            middleware(request)

        sync_mock.assert_not_called()
