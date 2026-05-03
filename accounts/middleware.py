from django.contrib.auth import logout
from django.shortcuts import redirect
from django.urls import reverse

from accounts.security import build_browser_fingerprint


class BrowserFingerprintMiddleware:
    """
    Bind an authenticated session to the browser fingerprint that created it.

    If the fingerprint changes, the session is cleared and the user is sent
    back to login.
    """

    session_key = 'browser_fingerprint'

    def __init__(self, get_response):
        self.get_response = get_response

    def __call__(self, request):
        if request.user.is_authenticated:
            current_fingerprint = build_browser_fingerprint(request)
            stored_fingerprint = request.session.get(self.session_key)

            if not stored_fingerprint:
                request.session[self.session_key] = current_fingerprint
                request.session.modified = True
            elif stored_fingerprint != current_fingerprint:
                logout(request)
                request.session.flush()
                if self._wants_json(request):
                    from django.http import JsonResponse

                    return JsonResponse({'detail': 'Session expired.'}, status=401)
                return redirect(reverse('login'))

        response = self.get_response(request)
        return response

    @staticmethod
    def _wants_json(request) -> bool:
        accept = request.headers.get('Accept', '')
        requested_with = request.headers.get('X-Requested-With', '')
        return 'application/json' in accept or requested_with == 'XMLHttpRequest'
