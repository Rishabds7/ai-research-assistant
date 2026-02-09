import os
import psycopg2
from datetime import datetime
from urllib.parse import urlparse

def patch_migrations():
    # Get DATABASE_URL from environment
    db_url = os.environ.get('DATABASE_URL')
    if not db_url:
        print("ERROR: DATABASE_URL environment variable not found.")
        return

    print(f"Connecting to database...")
    
    try:
        # Connect to the database
        conn = psycopg2.connect(db_url)
        conn.autocommit = True
        cur = conn.cursor()

        # 1. Check if the table exists
        cur.execute("SELECT to_regclass('public.django_migrations');")
        if not cur.fetchone()[0]:
            print("ERROR: django_migrations table not found.")
            return

        # 2. Insert the new consolidated migration record
        # We use ON CONFLICT DO NOTHING in case it's somehow already there
        print("Inserting 0007_delete_gapanalysis_and_clear_embeddings record...")
        cur.execute("""
            INSERT INTO django_migrations (app, name, applied)
            VALUES ('papers', '0007_delete_gapanalysis_and_clear_embeddings', %s)
            ON CONFLICT (app, name) DO NOTHING;
        """, (datetime.now(),))
        
        # 3. Clean up the old duplicate migration records that might be there
        print("Cleaning up old migration records if they exist...")
        old_migrations = ['0007_delete_gapanalysis', '0007_clear_embeddings']
        for old_name in old_migrations:
            cur.execute("DELETE FROM django_migrations WHERE app = 'papers' AND name = %s", (old_name,))
            print(f"Removed {old_name} (if it existed)")

        print("SUCCESS: Database migrations table patched successfully!")
        cur.close()
        conn.close()

    except Exception as e:
        print(f"ERROR: Failed to patch database: {e}")

if __name__ == "__main__":
    patch_migrations()
