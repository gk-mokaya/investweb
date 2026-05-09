from django.db import migrations, models


def backfill_ledger_codes(apps, schema_editor):
    InvestmentAccount = apps.get_model('investments', 'InvestmentAccount')
    accounts = InvestmentAccount.objects.all().order_by('created_at', 'id')
    counters = {}

    for account in accounts:
        created_at = account.created_at
        if created_at is None:
            continue
        prefix = created_at.strftime('%y-%m')
        counters[prefix] = counters.get(prefix, 0) + 1
        account.ledger_code = f"{prefix}-{counters[prefix]:04d}"
        account.save(update_fields=['ledger_code'])


class Migration(migrations.Migration):

    dependencies = [
        ('investments', '0012_userinvestment_settled_at_investmentaccount_and_more'),
    ]

    operations = [
        migrations.AddField(
            model_name='investmentaccount',
            name='ledger_code',
            field=models.CharField(blank=True, default='', editable=False, max_length=10),
        ),
        migrations.RunPython(backfill_ledger_codes, migrations.RunPython.noop),
        migrations.AlterField(
            model_name='investmentaccount',
            name='ledger_code',
            field=models.CharField(blank=False, default='', editable=False, max_length=10, unique=True),
        ),
    ]
