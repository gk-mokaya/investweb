from django.urls import path

from kyc.views import KYCView


urlpatterns = [
    path('', KYCView.as_view(), name='kyc_verify'),
]
