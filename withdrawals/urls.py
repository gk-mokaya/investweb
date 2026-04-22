from django.urls import path

from withdrawals.views import WithdrawalCreateView, WithdrawalListView


urlpatterns = [
    path('', WithdrawalListView.as_view(), name='withdrawal_list'),
    path('new/', WithdrawalCreateView.as_view(), name='withdrawal_create'),
]
