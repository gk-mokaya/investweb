from django.conf import settings

from accounts.security import build_browser_fingerprint


class BrowserFingerprintMiddleware:
    """
    Record a lightweight browser fingerprint for authenticated sessions.

    We keep the fingerprint in the session for observability, but we do not
    hard-kill the session on mismatch because real browsers can vary headers
    across requests and cause false logouts.
    """

    session_key = 'browser_fingerprint'

    def __init__(self, get_response):
        self.get_response = get_response

    def __call__(self, request):
        if request.user.is_authenticated:
            if not self._should_bind_fingerprint(request):
                return self.get_response(request)

            current_fingerprint = build_browser_fingerprint(request)
            stored_fingerprint = request.session.get(self.session_key)

            if not stored_fingerprint:
                request.session[self.session_key] = current_fingerprint
                request.session.modified = True
            elif stored_fingerprint != current_fingerprint:
                # Update the recorded fingerprint instead of invalidating the session.
                # This keeps legitimate users logged in across normal browser/header drift.
                request.session[self.session_key] = current_fingerprint
                request.session.modified = True

        response = self.get_response(request)
        return response

    def _should_bind_fingerprint(self, request) -> bool:
        accept = request.headers.get('Accept', '')
        path = request.path.split('?', 1)[0]
        static_prefix = '/' + settings.STATIC_URL.lstrip('/')
        media_prefix = '/' + settings.MEDIA_URL.lstrip('/')

        if path.startswith(static_prefix) or path.startswith(media_prefix):
            return False
        if request.headers.get('X-Requested-With') == 'XMLHttpRequest':
            return False
        if 'application/json' in accept:
            return False
        return 'text/html' in accept or accept == '*/*'
