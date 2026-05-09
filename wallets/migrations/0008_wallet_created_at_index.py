from django.db import migrations, models


class Migration(migrations.Migration):

    dependencies = [
        ('wallets', '0007_fix_wallet_uuid_and_type'),
    ]

    operations = [
        migrations.AlterField(
            model_name='wallet',
            name='created_at',
            field=models.DateTimeField(auto_now_add=True, db_index=True),
        ),
    ]
