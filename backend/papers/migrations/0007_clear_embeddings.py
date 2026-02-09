from django.db import migrations

def delete_existing_embeddings(apps, schema_editor):
    Embedding = apps.get_model('papers', 'Embedding')
    Embedding.objects.all().delete()

class Migration(migrations.Migration):

    dependencies = [
        ('papers', '0007_delete_gapanalysis'),
    ]

    operations = [
        migrations.RunPython(delete_existing_embeddings),
    ]
