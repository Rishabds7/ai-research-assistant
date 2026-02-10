# Generated manually for 768 dimension downgrade
from django.db import migrations
import pgvector.django


class Migration(migrations.Migration):
    """
    Downgrades embeddings from 3072 to 768 dimensions.
    Clears all existing embeddings because changing dimensions is a breaking 
    change in pgvector.
    
    After this migration, papers will need to be re-embedded.
    """
    dependencies = [
        ('papers', '0014_upgrade_to_3072_dimensions'),
    ]

    operations = [
        # Delete all embeddings (required for dimension change)
        migrations.RunSQL(
            "DELETE FROM papers_embedding;",
            reverse_sql=migrations.RunSQL.noop
        ),
        # Alter the field to 768 dimensions
        migrations.AlterField(
            model_name='embedding',
            name='embedding',
            field=pgvector.django.VectorField(dimensions=768),
        ),
    ]
