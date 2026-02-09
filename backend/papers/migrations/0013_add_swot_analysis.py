# Generated for SWOT Analysis feature
# Migration created manually

from django.db import migrations, models


class Migration(migrations.Migration):

    dependencies = [
        ('papers', '0012_add_gap_analysis_to_collection'),
    ]

    operations = [
        migrations.AddField(
            model_name='paper',
            name='swot_analysis',
            field=models.TextField(blank=True),
        ),
        migrations.AddField(
            model_name='paper',
            name='swot_analysis_updated_at',
            field=models.DateTimeField(blank=True, null=True),
        ),
    ]
