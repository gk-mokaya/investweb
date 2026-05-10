from django.db import migrations, models


class Migration(migrations.Migration):

    dependencies = [
        ('investments', '0013_investmentaccount_ledger_code'),
    ]

    operations = [
        migrations.CreateModel(
            name='ProfitSyncState',
            fields=[
                ('id', models.BigAutoField(auto_created=True, primary_key=True, serialize=False, verbose_name='ID')),
                ('name', models.CharField(max_length=64, unique=True)),
                ('updated_at', models.DateTimeField(auto_now=True)),
            ],
        ),
    ]
