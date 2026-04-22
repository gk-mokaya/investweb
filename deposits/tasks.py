from celery import shared_task
from django.utils import timezone

from deposits.models import Deposit
from deposits.services import refresh_confirmations, ProviderError


@shared_task
def check_deposit_confirmations():
    pending = Deposit.objects.filter(method='automated', status__in=['pending', 'confirming'])
    checked = 0
    for deposit in pending:
        if deposit.next_check_at and deposit.next_check_at > timezone.now():
            continue
        try:
            refresh_confirmations(deposit)
            checked += 1
        except ProviderError:
            continue
    return checked
