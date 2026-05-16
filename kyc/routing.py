from django.urls import path

from kyc.consumers import KYCVerificationConsumer


websocket_urlpatterns = [
    path('ws/kyc/verifications/<int:run_id>/', KYCVerificationConsumer.as_asgi(), name='kyc_verification_ws'),
]
