from django.urls import path

from kyc.views import KYCVerificationStatusView, KYCView


urlpatterns = [
    path('', KYCView.as_view(), name='kyc_verify'),
    path('verification/<int:run_id>/status/', KYCVerificationStatusView.as_view(), name='kyc_verification_status'),
]
