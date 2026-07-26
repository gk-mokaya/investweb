from django.db import migrations, models


class Migration(migrations.Migration):

    dependencies = [
        ('deposits', '0007_deposit_review_note_deposit_reviewed_at_and_more'),
    ]

    operations = [
        migrations.AddField(
            model_name='deposit',
            name='notes',
            field=models.TextField(blank=True, default=''),
        ),
    ]
