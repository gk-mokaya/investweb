from django.urls import path

from dashboard.views import AdminDashboardView, InvestmentProfitSyncView


urlpatterns = [
    path('', AdminDashboardView.as_view(), name='admin_dashboard'),
    path('investments/sync-profits/', InvestmentProfitSyncView.as_view(), name='admin_sync_profits'),
]
