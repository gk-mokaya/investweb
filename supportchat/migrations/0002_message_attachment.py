from django.db import migrations, models


class Migration(migrations.Migration):

    dependencies = [
        ('supportchat', '0001_initial'),
    ]

    operations = [
        migrations.AddField(
            model_name='message',
            name='attachment',
            field=models.FileField(blank=True, null=True, upload_to='supportchat/messages/'),
        ),
    ]
