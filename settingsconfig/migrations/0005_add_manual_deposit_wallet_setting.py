from django.db import migrations


def add_manual_deposit_wallet_setting(apps, schema_editor):
    SystemSetting = apps.get_model('settingsconfig', 'SystemSetting')
    SystemSetting.objects.get_or_create(
        key='MANUAL_DEPOSIT_WALLET_ADDRESS',
        defaults={'value': ''},
    )


def remove_manual_deposit_wallet_setting(apps, schema_editor):
    SystemSetting = apps.get_model('settingsconfig', 'SystemSetting')
    SystemSetting.objects.filter(key='MANUAL_DEPOSIT_WALLET_ADDRESS').delete()


class Migration(migrations.Migration):
    dependencies = [
        ('settingsconfig', '0004_add_gmail_settings'),
    ]

    operations = [
        migrations.RunPython(add_manual_deposit_wallet_setting, remove_manual_deposit_wallet_setting),
    ]
