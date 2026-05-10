import logging

from django.core.cache import cache
from django.conf import settings

from investments.services import sync_investment_profits


logger = logging.getLogger(__name__)


class InvestmentProfitSyncMiddleware:
    """
    Run a throttled profit catch-up on authenticated requests so missed Celery
    executions still get applied when the site is active.
    """

    cache_key = 'investment_profit_sync_last_run'
    throttle_seconds = 300

    def __init__(self, get_response):
        self.get_response = get_response

    def __call__(self, request):
        if request.user.is_authenticated and self._should_sync_request(request):
            self._maybe_sync()
        return self.get_response(request)

    def _should_sync_request(self, request) -> bool:
        path = request.path.split('?', 1)[0]
        static_prefix = '/' + settings.STATIC_URL.lstrip('/')
        media_prefix = '/' + settings.MEDIA_URL.lstrip('/')
        if path.startswith(static_prefix) or path.startswith(media_prefix):
            return False

        accept = request.headers.get('Accept', '')
        if request.headers.get('X-Requested-With') == 'XMLHttpRequest':
            return False
        if 'application/json' in accept:
            return False
        if not accept:
            return True
        return 'text/html' in accept or accept == '*/*'

    def _maybe_sync(self):
        if not cache.add(self.cache_key, 1, timeout=self.throttle_seconds):
            return
        try:
            sync_investment_profits()
        except Exception:
            # Never block the user request if the profit sync has a transient failure.
            logger.exception("Profit sync failed during request-time catch-up.")
