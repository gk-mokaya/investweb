from django.db import migrations, models
import django.db.models.deletion


def populate_investment_wallet(apps, schema_editor):
    Wallet = apps.get_model('wallets', 'Wallet')
    UserInvestment = apps.get_model('investments', 'UserInvestment')
    for investment in UserInvestment.objects.filter(wallet__isnull=True):
        wallet = (
            Wallet.objects.filter(user_id=investment.user_id, is_primary=True).first()
            or Wallet.objects.filter(user_id=investment.user_id).first()
        )
        if wallet:
            investment.wallet_id = wallet.id
            investment.save(update_fields=['wallet'])


class Migration(migrations.Migration):
    dependencies = [
        ('wallets', '0002_wallet_multi_and_transfer'),
        ('investments', '0005_investmentplan_plan_tier'),
    ]

    operations = [
        migrations.AddField(
            model_name='userinvestment',
            name='wallet',
            field=models.ForeignKey(blank=True, null=True, on_delete=django.db.models.deletion.PROTECT, to='wallets.wallet'),
        ),
        migrations.RunPython(populate_investment_wallet, migrations.RunPython.noop),
        migrations.AlterField(
            model_name='userinvestment',
            name='wallet',
            field=models.ForeignKey(on_delete=django.db.models.deletion.PROTECT, to='wallets.wallet'),
        ),
    ]
