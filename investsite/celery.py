import os

from celery import Celery
from celery.schedules import crontab

os.environ.setdefault('DJANGO_SETTINGS_MODULE', 'investsite.settings')

app = Celery('investsite')
app.config_from_object('django.conf:settings', namespace='CELERY')
app.autodiscover_tasks()

app.conf.beat_schedule = {
    'apply-daily-profits': {
        'task': 'investments.tasks.apply_daily_profits_task',
        'schedule': crontab(hour=0, minute=0),
    },
    'check-deposit-confirmations': {
        'task': 'deposits.tasks.check_deposit_confirmations',
        'schedule': 60 * 15,
    },
}
