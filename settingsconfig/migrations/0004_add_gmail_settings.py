from django.db import migrations


def add_gmail_settings(apps, schema_editor):
    SystemSetting = apps.get_model('settingsconfig', 'SystemSetting')
    defaults = {
        'GMAIL_CLIENT_ID': '',
        'GMAIL_CLIENT_SECRET': '',
        'GMAIL_REFRESH_TOKEN': '',
        'GMAIL_SENDER_EMAIL': '',
    }

    for key, value in defaults.items():
        SystemSetting.objects.get_or_create(key=key, defaults={'value': value})


def remove_gmail_settings(apps, schema_editor):
    SystemSetting = apps.get_model('settingsconfig', 'SystemSetting')
    SystemSetting.objects.filter(
        key__in=['GMAIL_CLIENT_ID', 'GMAIL_CLIENT_SECRET', 'GMAIL_REFRESH_TOKEN', 'GMAIL_SENDER_EMAIL']
    ).delete()


class Migration(migrations.Migration):
    dependencies = [
        ('settingsconfig', '0003_add_crypto_settings'),
    ]

    operations = [
        migrations.RunPython(add_gmail_settings, remove_gmail_settings),
    ]
