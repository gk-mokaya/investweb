from django.db import migrations, models
import django.db.models.deletion
from django.utils import timezone
from secrets import token_hex


def populate_wallet_metadata(apps, schema_editor):
    Wallet = apps.get_model('wallets', 'Wallet')
    existing = set(
        addr for addr in Wallet.objects.values_list('address', flat=True) if addr
    )
    seen_users = set()
    for wallet in Wallet.objects.all().order_by('id'):
        if not wallet.address:
            address = None
            for _ in range(10):
                candidate = token_hex(6).upper()
                if candidate not in existing:
                    address = candidate
                    existing.add(candidate)
                    break
            wallet.address = address or token_hex(7).upper()
        if not wallet.name:
            wallet.name = 'Main Wallet'
        if wallet.user_id in seen_users:
            wallet.is_primary = False
        else:
            wallet.is_primary = True
            seen_users.add(wallet.user_id)
        wallet.save(update_fields=['address', 'name', 'is_primary'])


class Migration(migrations.Migration):
    dependencies = [
        ('wallets', '0001_initial'),
    ]

    operations = [
        migrations.AlterField(
            model_name='wallet',
            name='user',
            field=models.ForeignKey(on_delete=django.db.models.deletion.CASCADE, related_name='wallets', to='auth.user'),
        ),
        migrations.AddField(
            model_name='wallet',
            name='name',
            field=models.CharField(default='Main Wallet', max_length=60),
        ),
        migrations.AddField(
            model_name='wallet',
            name='address',
            field=models.CharField(blank=True, max_length=24, null=True, unique=True),
        ),
        migrations.AddField(
            model_name='wallet',
            name='is_primary',
            field=models.BooleanField(default=False),
        ),
        migrations.AddField(
            model_name='wallet',
            name='is_active',
            field=models.BooleanField(default=True),
        ),
        migrations.AddField(
            model_name='wallet',
            name='created_at',
            field=models.DateTimeField(default=timezone.now),
            preserve_default=False,
        ),
        migrations.CreateModel(
            name='WalletTransfer',
            fields=[
                ('id', models.BigAutoField(auto_created=True, primary_key=True, serialize=False, verbose_name='ID')),
                ('amount', models.DecimalField(decimal_places=2, max_digits=12)),
                ('bucket', models.CharField(default='main', max_length=12)),
                ('note', models.CharField(blank=True, default='', max_length=200)),
                ('status', models.CharField(choices=[('completed', 'Completed'), ('failed', 'Failed')], default='completed', max_length=20)),
                ('created_at', models.DateTimeField(auto_now_add=True)),
                ('from_wallet', models.ForeignKey(on_delete=django.db.models.deletion.PROTECT, related_name='transfers_out', to='wallets.wallet')),
                ('to_wallet', models.ForeignKey(on_delete=django.db.models.deletion.PROTECT, related_name='transfers_in', to='wallets.wallet')),
                ('user', models.ForeignKey(on_delete=django.db.models.deletion.CASCADE, to='auth.user')),
            ],
        ),
        migrations.RunPython(populate_wallet_metadata, migrations.RunPython.noop),
        migrations.AlterField(
            model_name='wallet',
            name='address',
            field=models.CharField(max_length=24, unique=True),
        ),
    ]
