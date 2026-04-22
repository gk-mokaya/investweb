from django.db import migrations


def seed_settings(apps, schema_editor):
    SystemSetting = apps.get_model('settingsconfig', 'SystemSetting')
    defaults = {
        'WELCOME_BONUS': '50',
        'BONUS_PROFIT_MULTIPLIER': '3',
        'MIN_WITHDRAWAL_AMOUNT': '10',
        'CURRENCY': 'USD',
        'CRYPTO_PROVIDER': 'manual',
        'BLOCKCYPHER_TOKEN': '',
        'BLOCKCYPHER_CALLBACK_URL': '',
        'DESTINATION_BTC_ADDRESS': '',
        'DESTINATION_ETH_ADDRESS': '',
        'DESTINATION_USDT_ADDRESS': '',
    }

    for key, value in defaults.items():
        SystemSetting.objects.get_or_create(key=key, defaults={'value': value})


def unseed_settings(apps, schema_editor):
    SystemSetting = apps.get_model('settingsconfig', 'SystemSetting')
    SystemSetting.objects.filter(key__in=[
        'WELCOME_BONUS',
        'BONUS_PROFIT_MULTIPLIER',
        'MIN_WITHDRAWAL_AMOUNT',
        'CURRENCY',
        'CRYPTO_PROVIDER',
        'BLOCKCYPHER_TOKEN',
        'BLOCKCYPHER_CALLBACK_URL',
        'DESTINATION_BTC_ADDRESS',
        'DESTINATION_ETH_ADDRESS',
        'DESTINATION_USDT_ADDRESS',
    ]).delete()


class Migration(migrations.Migration):
    dependencies = [
        ('settingsconfig', '0001_initial'),
    ]

    operations = [
        migrations.RunPython(seed_settings, unseed_settings),
    ]
