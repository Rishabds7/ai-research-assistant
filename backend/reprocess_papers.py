import os
import django
import sys

# Setup Django environment
sys.path.append('/Users/rishabdarshanshylendra/Documents/Personal Project/research-assistant-mvp/backend')
os.environ.setdefault('DJANGO_SETTINGS_MODULE', 'core.settings')
django.setup()

from papers.models import Paper
from papers.tasks import process_pdf_task, extract_metadata_task, extract_all_sections_task

def reprocess_all_papers():
    papers = Paper.objects.all()
    print(f"Found {len(papers)} papers to re-process.")
    
    for paper in papers:
        print(f"Triggering re-processing for: {paper.filename} ({paper.id})")
        
        # 1. Re-process PDF (Extract text/sections with new logic)
        # We call .delay() to run it in Celery
        process_pdf_task.delay(str(paper.id))
        
        # 2. Re-extract Datasets
        extract_metadata_task.delay(str(paper.id), 'datasets')
        
        # 3. Re-extract Licenses
        extract_metadata_task.delay(str(paper.id), 'licenses')
        
        # 4. Re-generate Summaries (with improved section detection)
        extract_all_sections_task.delay(str(paper.id))

if __name__ == "__main__":
    reprocess_all_papers()
    print("All re-processing tasks have been queued in Celery.")
