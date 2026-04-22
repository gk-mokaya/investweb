from django.db import migrations, models
import django.db.models.deletion


def populate_deposit_wallet(apps, schema_editor):
    Wallet = apps.get_model('wallets', 'Wallet')
    Deposit = apps.get_model('deposits', 'Deposit')
    for deposit in Deposit.objects.filter(wallet__isnull=True):
        wallet = (
            Wallet.objects.filter(user_id=deposit.user_id, is_primary=True).first()
            or Wallet.objects.filter(user_id=deposit.user_id).first()
        )
        if wallet:
            deposit.wallet_id = wallet.id
            deposit.save(update_fields=['wallet'])


class Migration(migrations.Migration):
    dependencies = [
        ('wallets', '0002_wallet_multi_and_transfer'),
        ('deposits', '0004_deposit_check_attempts_deposit_confirmations_and_more'),
    ]

    operations = [
        migrations.AddField(
            model_name='deposit',
            name='wallet',
            field=models.ForeignKey(blank=True, null=True, on_delete=django.db.models.deletion.PROTECT, to='wallets.wallet'),
        ),
        migrations.RunPython(populate_deposit_wallet, migrations.RunPython.noop),
        migrations.AlterField(
            model_name='deposit',
            name='wallet',
            field=models.ForeignKey(on_delete=django.db.models.deletion.PROTECT, to='wallets.wallet'),
        ),
    ]
