from django.urls import path

from adminpanel.views import (
    AdminDashboardView,
    AdminPlanCreateView,
    AdminPlanUpdateView,
    AdminPlanDeleteView,
    DepositApproveView,
    DepositRejectView,
    DepositVerifyView,
    KYCApproveView,
    KYCDownloadView,
    KYCRejectView,
    AdminOperationsView,
    InvestmentProfitSyncView,
    AdminSiteSettingsView,
    WalletApproveView,
    WalletRejectView,
    WithdrawalApproveView,
    WithdrawalPaidView,
    WithdrawalRejectView,
)


urlpatterns = [
    path('', AdminDashboardView.as_view(), name='admin_dashboard'),
    path('operations/', AdminOperationsView.as_view(), name='admin_operations'),
    path('investments/sync-profits/', InvestmentProfitSyncView.as_view(), name='admin_sync_profits'),
    path('plans/new/', AdminPlanCreateView.as_view(), name='admin_plan_create'),
    path('plans/<int:pk>/edit/', AdminPlanUpdateView.as_view(), name='admin_plan_edit'),
    path('plans/<int:pk>/delete/', AdminPlanDeleteView.as_view(), name='admin_plan_delete'),
    path('deposits/<int:pk>/approve/', DepositApproveView.as_view(), name='admin_deposit_approve'),
    path('deposits/<int:pk>/reject/', DepositRejectView.as_view(), name='admin_deposit_reject'),
    path('deposits/<int:pk>/verify/', DepositVerifyView.as_view(), name='admin_deposit_verify'),
    path('withdrawals/<int:pk>/approve/', WithdrawalApproveView.as_view(), name='admin_withdrawal_approve'),
    path('withdrawals/<int:pk>/reject/', WithdrawalRejectView.as_view(), name='admin_withdrawal_reject'),
    path('withdrawals/<int:pk>/paid/', WithdrawalPaidView.as_view(), name='admin_withdrawal_paid'),
    path('kyc/<int:pk>/approve/', KYCApproveView.as_view(), name='admin_kyc_approve'),
    path('kyc/<int:pk>/reject/', KYCRejectView.as_view(), name='admin_kyc_reject'),
    path('kyc/<int:pk>/download/', KYCDownloadView.as_view(), name='admin_kyc_download'),
    path('wallets/<uuid:pk>/approve/', WalletApproveView.as_view(), name='admin_wallet_approve'),
    path('wallets/<uuid:pk>/reject/', WalletRejectView.as_view(), name='admin_wallet_reject'),
    path('settings/site/', AdminSiteSettingsView.as_view(), name='admin_site_settings'),
]
