from django.urls import path

from investments.views import (
    CreateInvestmentView,
    DashboardView,
    InvestmentListView,
    LandingView,
    PlanListView,
)


urlpatterns = [
    path('', LandingView.as_view(), name='home'),
    path('dashboard/', DashboardView.as_view(), name='dashboard'),
    path('plans/', PlanListView.as_view(), name='plans'),
    path('invest/', CreateInvestmentView.as_view(), name='create_investment'),
    path('my-investments/', InvestmentListView.as_view(), name='my_investments'),
]
