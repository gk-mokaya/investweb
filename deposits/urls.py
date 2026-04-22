from django.urls import path

from deposits.views import DepositCreateView, DepositListView


urlpatterns = [
    path('', DepositListView.as_view(), name='deposit_list'),
    path('new/', DepositCreateView.as_view(), name='deposit_create'),
]
