from django.db import migrations, models
import django.db.models.deletion


def populate_withdrawal_wallet(apps, schema_editor):
    Wallet = apps.get_model('wallets', 'Wallet')
    Withdrawal = apps.get_model('withdrawals', 'Withdrawal')
    for withdrawal in Withdrawal.objects.filter(wallet__isnull=True):
        wallet = (
            Wallet.objects.filter(user_id=withdrawal.user_id, is_primary=True).first()
            or Wallet.objects.filter(user_id=withdrawal.user_id).first()
        )
        if wallet:
            withdrawal.wallet_id = wallet.id
            withdrawal.save(update_fields=['wallet'])


class Migration(migrations.Migration):
    dependencies = [
        ('wallets', '0002_wallet_multi_and_transfer'),
        ('withdrawals', '0003_withdrawal_cooldown_until_alter_withdrawal_status'),
    ]

    operations = [
        migrations.AddField(
            model_name='withdrawal',
            name='wallet',
            field=models.ForeignKey(blank=True, null=True, on_delete=django.db.models.deletion.PROTECT, to='wallets.wallet'),
        ),
        migrations.RunPython(populate_withdrawal_wallet, migrations.RunPython.noop),
        migrations.AlterField(
            model_name='withdrawal',
            name='wallet',
            field=models.ForeignKey(on_delete=django.db.models.deletion.PROTECT, to='wallets.wallet'),
        ),
    ]
