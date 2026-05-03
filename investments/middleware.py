from django.core.cache import cache

from investments.services import sync_investment_profits


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
        if request.user.is_authenticated:
            self._maybe_sync()
        return self.get_response(request)

    def _maybe_sync(self):
        if not cache.add(self.cache_key, 1, timeout=self.throttle_seconds):
            return
        try:
            sync_investment_profits()
        except Exception:
            # Never block the user request if the profit sync has a transient failure.
            pass
