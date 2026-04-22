from django.db import migrations, models
import django.db.models.deletion


def approve_existing_wallets(apps, schema_editor):
    Wallet = apps.get_model('wallets', 'Wallet')
    Wallet.objects.filter(approval_status='').update(approval_status='approved')
    Wallet.objects.update(is_active=True)


class Migration(migrations.Migration):
    dependencies = [
        ('wallets', '0002_wallet_multi_and_transfer'),
    ]

    operations = [
        migrations.AddField(
            model_name='wallet',
            name='approval_status',
            field=models.CharField(choices=[('pending', 'Pending'), ('approved', 'Approved'), ('rejected', 'Rejected')], default='approved', max_length=20),
        ),
        migrations.AddField(
            model_name='wallet',
            name='reason',
            field=models.CharField(blank=True, default='', max_length=200),
        ),
        migrations.AddField(
            model_name='wallet',
            name='notes',
            field=models.TextField(blank=True, default=''),
        ),
        migrations.AddField(
            model_name='wallet',
            name='approved_by',
            field=models.ForeignKey(blank=True, null=True, on_delete=django.db.models.deletion.SET_NULL, related_name='approved_wallets', to='auth.user'),
        ),
        migrations.AddField(
            model_name='wallet',
            name='approved_at',
            field=models.DateTimeField(blank=True, null=True),
        ),
        migrations.RunPython(approve_existing_wallets, migrations.RunPython.noop),
    ]
