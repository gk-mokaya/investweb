from django.urls import path

from finance.views import (
    AdminPlanCreateView,
    AdminPlanDeleteView,
    AdminPlanListView,
    AdminPlanUpdateView,
    AdminSiteSettingsView,
    DepositQueueView,
    DepositApproveView,
    DepositRejectView,
    DepositVerifyView,
    SiteSettingsPageView,
    WalletQueueView,
    WalletApproveView,
    WalletRejectView,
    WithdrawalQueueView,
    WithdrawalApproveView,
    WithdrawalPaidView,
    WithdrawalRejectView,
)


urlpatterns = [
    path('plans/', AdminPlanListView.as_view(), name='admin_plans'),
    path('plans/new/', AdminPlanCreateView.as_view(), name='admin_plan_create'),
    path('plans/<int:pk>/edit/', AdminPlanUpdateView.as_view(), name='admin_plan_edit'),
    path('plans/<int:pk>/delete/', AdminPlanDeleteView.as_view(), name='admin_plan_delete'),
    path('deposits/', DepositQueueView.as_view(), name='admin_pending_deposits'),
    path('deposits/<int:pk>/approve/', DepositApproveView.as_view(), name='admin_deposit_approve'),
    path('deposits/<int:pk>/reject/', DepositRejectView.as_view(), name='admin_deposit_reject'),
    path('deposits/<int:pk>/verify/', DepositVerifyView.as_view(), name='admin_deposit_verify'),
    path('withdrawals/', WithdrawalQueueView.as_view(), name='admin_pending_withdrawals'),
    path('withdrawals/<int:pk>/approve/', WithdrawalApproveView.as_view(), name='admin_withdrawal_approve'),
    path('withdrawals/<int:pk>/reject/', WithdrawalRejectView.as_view(), name='admin_withdrawal_reject'),
    path('withdrawals/<int:pk>/paid/', WithdrawalPaidView.as_view(), name='admin_withdrawal_paid'),
    path('wallets/', WalletQueueView.as_view(), name='admin_wallets'),
    path('wallets/<uuid:pk>/approve/', WalletApproveView.as_view(), name='admin_wallet_approve'),
    path('wallets/<uuid:pk>/reject/', WalletRejectView.as_view(), name='admin_wallet_reject'),
    path('settings/', SiteSettingsPageView.as_view(), name='admin_site_settings_page'),
    path('settings/site/', AdminSiteSettingsView.as_view(), name='admin_site_settings'),
]
