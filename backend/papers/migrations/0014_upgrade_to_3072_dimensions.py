# Generated manually for 3072 dimension upgrade
from django.db import migrations
import pgvector.django

def clear_embeddings(apps, schema_editor):
    """
    Clears all existing embeddings because changing dimensions is a breaking 
    change for the pgvector column. Data must be regenerated.
    """
    Embedding = apps.get_model('papers', 'Embedding')
    Embedding.objects.all().delete()

class Migration(migrations.Migration):

    dependencies = [
        ('papers', '0013_add_swot_analysis'),
    ]

    operations = [
        migrations.RunPython(clear_embeddings),
        migrations.AlterField(
            model_name='embedding',
            name='embedding',
            field=pgvector.django.VectorField(dimensions=3072),
        ),
    ]
