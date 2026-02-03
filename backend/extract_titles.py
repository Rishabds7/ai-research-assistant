import os
import django
import sys

# Setup Django environment
sys.path.append('/Users/rishabdarshanshylendra/Documents/Personal Project/research-assistant-mvp/backend')
os.environ.setdefault('DJANGO_SETTINGS_MODULE', 'core.settings')
django.setup()

from papers.models import Paper
from services.llm_service import LLMService

def extract_info():
    papers = Paper.objects.all()
    llm = LLMService()
    for paper in papers:
        if not paper.title or paper.title == 'Unknown':
            print(f"Extracting info for {paper.filename}...")
            info = llm.extract_paper_info(paper.full_text[:10000])
            paper.title = info.get('title', 'Unknown')
            paper.authors = info.get('authors', 'Unknown')
            paper.save(update_fields=['title', 'authors'])
            print(f"Done: {paper.title}")

if __name__ == "__main__":
    extract_info()
