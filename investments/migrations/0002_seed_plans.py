from decimal import Decimal

from django.db import migrations


def seed_plans(apps, schema_editor):
    InvestmentPlan = apps.get_model('investments', 'InvestmentPlan')

    plans = [
        {
            'name': 'Starter Plan',
            'min_amount': Decimal('10'),
            'max_amount': Decimal('100'),
            'daily_roi': Decimal('2.00'),
            'duration_days': 7,
            'total_return': Decimal('14.00'),
            'is_active': True,
        },
        {
            'name': 'Silver Plan',
            'min_amount': Decimal('100'),
            'max_amount': Decimal('500'),
            'daily_roi': Decimal('2.50'),
            'duration_days': 14,
            'total_return': Decimal('35.00'),
            'is_active': True,
        },
        {
            'name': 'Gold Plan',
            'min_amount': Decimal('500'),
            'max_amount': Decimal('2000'),
            'daily_roi': Decimal('3.00'),
            'duration_days': 21,
            'total_return': Decimal('63.00'),
            'is_active': True,
        },
        {
            'name': 'Platinum Plan',
            'min_amount': Decimal('2000'),
            'max_amount': Decimal('10000'),
            'daily_roi': Decimal('3.50'),
            'duration_days': 30,
            'total_return': Decimal('105.00'),
            'is_active': True,
        },
        {
            'name': 'VIP Plan',
            'min_amount': Decimal('10000'),
            'max_amount': None,
            'daily_roi': Decimal('4.50'),
            'duration_days': 30,
            'total_return': Decimal('135.00'),
            'is_active': True,
        },
    ]

    for plan in plans:
        InvestmentPlan.objects.get_or_create(name=plan['name'], defaults=plan)


def unseed_plans(apps, schema_editor):
    InvestmentPlan = apps.get_model('investments', 'InvestmentPlan')
    InvestmentPlan.objects.filter(name__in=[
        'Starter Plan',
        'Silver Plan',
        'Gold Plan',
        'Platinum Plan',
        'VIP Plan',
    ]).delete()


class Migration(migrations.Migration):
    dependencies = [
        ('investments', '0001_initial'),
    ]

    operations = [
        migrations.RunPython(seed_plans, unseed_plans),
    ]
