import os
import django
import sys
from django.db import connection

# Setup Django environment
sys.path.append('/Users/rishabdarshanshylendra/Documents/Personal Project/research-assistant-mvp/backend')
os.environ.setdefault('DJANGO_SETTINGS_MODULE', 'core.settings')
django.setup()

def check_columns():
    with connection.cursor() as cursor:
        cursor.execute("SELECT column_name FROM information_schema.columns WHERE table_name = 'papers_paper'")
        columns = [row[0] for row in cursor.fetchall()]
        print(f"Columns in papers_paper: {columns}")
        
        needed = ['title', 'authors', 'notes', 'global_summary']
        missing = [c for c in needed if c not in columns]
        if missing:
            print(f"Missing columns: {missing}")
            # Try to add them manually!
            for col in missing:
                print(f"Attempting to add column {col}...")
                try:
                    if col == 'title':
                        cursor.execute("ALTER TABLE papers_paper ADD COLUMN title character varying(500) NOT NULL DEFAULT ''")
                    else:
                        cursor.execute(f"ALTER TABLE papers_paper ADD COLUMN {col} text NOT NULL DEFAULT ''")
                    print(f"Successfully added {col}")
                except Exception as e:
                    print(f"Failed to add {col}: {e}")
        else:
            print("All columns present!")

if __name__ == "__main__":
    try:
        check_columns()
    except Exception as e:
        print(f"Connection failed: {e}")
