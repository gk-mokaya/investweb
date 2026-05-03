from django.urls import path

from users.views import (
    KYCApproveView,
    KYCDownloadView,
    KYCRejectView,
    KYCReviewListView,
    UserAdminCreateView,
    UserAdminDetailView,
    UserAdminListView,
    UserSendResetLinkView,
    UserToggleActiveView,
    UserToggleStaffView,
)


urlpatterns = [
    path('users/', UserAdminListView.as_view(), name='admin_user_list'),
    path('users/new/', UserAdminCreateView.as_view(), name='admin_user_create'),
    path('users/<int:pk>/', UserAdminDetailView.as_view(), name='admin_user_detail'),
    path('users/<int:pk>/toggle-active/', UserToggleActiveView.as_view(), name='admin_user_toggle_active'),
    path('users/<int:pk>/toggle-staff/', UserToggleStaffView.as_view(), name='admin_user_toggle_staff'),
    path('users/<int:pk>/send-reset-link/', UserSendResetLinkView.as_view(), name='admin_user_send_reset_link'),
    path('kyc/', KYCReviewListView.as_view(), name='admin_kyc_reviews'),
    path('kyc/<int:pk>/approve/', KYCApproveView.as_view(), name='admin_kyc_approve'),
    path('kyc/<int:pk>/reject/', KYCRejectView.as_view(), name='admin_kyc_reject'),
    path('kyc/<int:pk>/download/', KYCDownloadView.as_view(), name='admin_kyc_download'),
]
