from django.db import migrations, models
from django.db.models import deletion


class Migration(migrations.Migration):
    dependencies = [
        ('investments', '0010_userinvestment_plan_snapshot'),
    ]

    operations = [
        migrations.AddField(
            model_name='investmentplan',
            name='source_plan',
            field=models.ForeignKey(blank=True, null=True, on_delete=deletion.SET_NULL, related_name='derived_versions', to='investments.investmentplan'),
        ),
        migrations.AddField(
            model_name='investmentplan',
            name='version_number',
            field=models.PositiveIntegerField(default=1),
        ),
    ]
