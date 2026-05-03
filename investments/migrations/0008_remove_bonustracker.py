from django.db import migrations


class Migration(migrations.Migration):

    dependencies = [
        ('investments', '0007_remove_userinvestment_goal_and_more'),
    ]

    operations = [
        migrations.DeleteModel(
            name='BonusTracker',
        ),
    ]
