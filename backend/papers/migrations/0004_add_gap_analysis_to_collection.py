# Generated manually for adding gap_analysis fields to Collection

from django.db import migrations, models


class Migration(migrations.Migration):

    dependencies = [
        ('papers', '0003_paper_task_ids'),
    ]

    operations = [
        migrations.AddField(
            model_name='collection',
            name='gap_analysis',
            field=models.TextField(blank=True),
        ),
        migrations.AddField(
            model_name='collection',
            name='gap_analysis_updated_at',
            field=models.DateTimeField(blank=True, null=True),
        ),
    ]
