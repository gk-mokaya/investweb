from decimal import Decimal

from django.db import migrations, models


def _effective_plan_values(plan):
    duration_days = plan.duration_days or 0
    total_return = plan.total_return or Decimal('0')
    daily_roi = plan.daily_roi or Decimal('0')

    if total_return > 0 and duration_days:
        daily_roi = (Decimal(total_return) / Decimal(duration_days)).quantize(Decimal('0.01'))
    elif daily_roi > 0 and duration_days:
        total_return = (Decimal(daily_roi) * Decimal(duration_days)).quantize(Decimal('0.01'))
    else:
        total_return = Decimal(total_return).quantize(Decimal('0.01'))
        daily_roi = Decimal(daily_roi).quantize(Decimal('0.01'))

    return {
        'name': plan.name or '',
        'tier': plan.plan_tier or 'standard',
        'daily_roi': daily_roi.quantize(Decimal('0.01')),
        'total_return': total_return.quantize(Decimal('0.01')),
        'duration_days': duration_days,
        'payout_frequency': plan.payout_frequency or 'daily',
        'liquidity_terms': plan.liquidity_terms or 'locked',
        'lock_period_days': plan.lock_period_days or 0,
        'management_fee_pct': (plan.management_fee_pct or Decimal('0')).quantize(Decimal('0.01')),
        'early_withdrawal_fee_pct': (plan.early_withdrawal_fee_pct or Decimal('0')).quantize(Decimal('0.01')),
        'risk_level': plan.risk_level or 'moderate',
        'capital_protection': bool(plan.capital_protection),
    }


def backfill_plan_snapshots(apps, schema_editor):
    InvestmentPlan = apps.get_model('investments', 'InvestmentPlan')
    UserInvestment = apps.get_model('investments', 'UserInvestment')

    for plan in InvestmentPlan.objects.all():
        values = _effective_plan_values(plan)
        InvestmentPlan.objects.filter(pk=plan.pk).update(
            total_return=values['total_return'],
            daily_roi=values['daily_roi'],
        )

    for investment in UserInvestment.objects.select_related('plan').all():
        plan = investment.plan
        values = _effective_plan_values(plan)
        UserInvestment.objects.filter(pk=investment.pk).update(
            plan_snapshot_name=values['name'],
            plan_snapshot_tier=values['tier'],
            plan_snapshot_daily_roi=values['daily_roi'],
            plan_snapshot_total_return=values['total_return'],
            plan_snapshot_duration_days=values['duration_days'],
            plan_snapshot_payout_frequency=values['payout_frequency'],
            plan_snapshot_liquidity_terms=values['liquidity_terms'],
            plan_snapshot_lock_period_days=values['lock_period_days'],
            plan_snapshot_management_fee_pct=values['management_fee_pct'],
            plan_snapshot_early_withdrawal_fee_pct=values['early_withdrawal_fee_pct'],
            plan_snapshot_risk_level=values['risk_level'],
            plan_snapshot_capital_protection=values['capital_protection'],
        )


class Migration(migrations.Migration):
    dependencies = [
        ('investments', '0009_remove_userinvestment_auto_reinvest'),
    ]

    operations = [
        migrations.AddField(
            model_name='userinvestment',
            name='plan_snapshot_name',
            field=models.CharField(blank=True, default='', max_length=100),
        ),
        migrations.AddField(
            model_name='userinvestment',
            name='plan_snapshot_tier',
            field=models.CharField(blank=True, default='standard', max_length=20),
        ),
        migrations.AddField(
            model_name='userinvestment',
            name='plan_snapshot_daily_roi',
            field=models.DecimalField(decimal_places=2, default=Decimal('0'), max_digits=5),
        ),
        migrations.AddField(
            model_name='userinvestment',
            name='plan_snapshot_total_return',
            field=models.DecimalField(decimal_places=2, default=Decimal('0'), max_digits=6),
        ),
        migrations.AddField(
            model_name='userinvestment',
            name='plan_snapshot_duration_days',
            field=models.IntegerField(default=0),
        ),
        migrations.AddField(
            model_name='userinvestment',
            name='plan_snapshot_payout_frequency',
            field=models.CharField(blank=True, default='daily', max_length=20),
        ),
        migrations.AddField(
            model_name='userinvestment',
            name='plan_snapshot_liquidity_terms',
            field=models.CharField(blank=True, default='locked', max_length=40),
        ),
        migrations.AddField(
            model_name='userinvestment',
            name='plan_snapshot_lock_period_days',
            field=models.IntegerField(default=0),
        ),
        migrations.AddField(
            model_name='userinvestment',
            name='plan_snapshot_management_fee_pct',
            field=models.DecimalField(decimal_places=2, default=Decimal('0'), max_digits=5),
        ),
        migrations.AddField(
            model_name='userinvestment',
            name='plan_snapshot_early_withdrawal_fee_pct',
            field=models.DecimalField(decimal_places=2, default=Decimal('0'), max_digits=5),
        ),
        migrations.AddField(
            model_name='userinvestment',
            name='plan_snapshot_risk_level',
            field=models.CharField(blank=True, default='moderate', max_length=20),
        ),
        migrations.AddField(
            model_name='userinvestment',
            name='plan_snapshot_capital_protection',
            field=models.BooleanField(default=True),
        ),
        migrations.RunPython(backfill_plan_snapshots, migrations.RunPython.noop),
    ]
