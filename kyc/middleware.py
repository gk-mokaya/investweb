from django.conf import settings
from django.contrib import messages
from django.shortcuts import redirect
from django.urls import reverse, resolve, Resolver404

from kyc.models import KYCProfile


class KYCRequiredMiddleware:
    public_route_names = {
        'home',
        'plans',
        'login',
        'register',
        'password_reset',
        'password_reset_done',
        'password_reset_confirm',
        'password_reset_complete',
        'logout',
        'kyc_verify',
    }

    def __init__(self, get_response):
        self.get_response = get_response

    def __call__(self, request):
        if self._is_public_route(request):
            return self.get_response(request)

        if request.user.is_authenticated and not request.user.is_staff and not request.user.is_superuser:
            profile = KYCProfile.objects.filter(user=request.user).first()
            if not profile or profile.status != 'verified':
                allowed_paths = [
                    reverse('profile'),
                    reverse('logout'),
                ]
                if request.path.startswith('/admin/'):
                    return self.get_response(request)
                if request.path.startswith(settings.STATIC_URL) or request.path.startswith(settings.MEDIA_URL):
                    return self.get_response(request)
                if request.path not in allowed_paths:
                    messages.warning(request, "Please complete KYC verification to access the platform.")
                    return redirect('profile')

        return self.get_response(request)

    def _is_public_route(self, request) -> bool:
        if request.path.startswith('/admin/'):
            return False
        static_prefix = '/' + settings.STATIC_URL.lstrip('/')
        media_prefix = '/' + settings.MEDIA_URL.lstrip('/')
        if request.path.startswith(static_prefix) or request.path.startswith(media_prefix):
            return True

        try:
            resolved = resolve(request.path_info)
        except Resolver404:
            return False

        return resolved.url_name in self.public_route_names
