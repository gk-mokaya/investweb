from django.db import migrations


def add_crypto_settings(apps, schema_editor):
    SystemSetting = apps.get_model('settingsconfig', 'SystemSetting')
    defaults = {
        'CRYPTO_PROVIDER': 'manual',
        'BLOCKCYPHER_TOKEN': '',
        'BLOCKCYPHER_CALLBACK_URL': '',
        'DESTINATION_BTC_ADDRESS': '',
        'DESTINATION_ETH_ADDRESS': '',
        'DESTINATION_USDT_ADDRESS': '',
    }

    for key, value in defaults.items():
        SystemSetting.objects.get_or_create(key=key, defaults={'value': value})


def remove_crypto_settings(apps, schema_editor):
    SystemSetting = apps.get_model('settingsconfig', 'SystemSetting')
    SystemSetting.objects.filter(key__in=[
        'CRYPTO_PROVIDER',
        'BLOCKCYPHER_TOKEN',
        'BLOCKCYPHER_CALLBACK_URL',
        'DESTINATION_BTC_ADDRESS',
        'DESTINATION_ETH_ADDRESS',
        'DESTINATION_USDT_ADDRESS',
    ]).delete()


class Migration(migrations.Migration):
    dependencies = [
        ('settingsconfig', '0002_seed_settings'),
    ]

    operations = [
        migrations.RunPython(add_crypto_settings, remove_crypto_settings),
    ]
