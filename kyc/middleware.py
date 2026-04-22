from django.conf import settings
from django.contrib import messages
from django.shortcuts import redirect
from django.urls import reverse

from kyc.models import KYCProfile


class KYCRequiredMiddleware:
    def __init__(self, get_response):
        self.get_response = get_response

    def __call__(self, request):
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
