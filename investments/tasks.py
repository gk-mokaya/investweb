from celery import shared_task
from django.utils import timezone

from investments.services import apply_daily_profits


@shared_task
def apply_daily_profits_task():
    return apply_daily_profits(process_date=timezone.now().date())
