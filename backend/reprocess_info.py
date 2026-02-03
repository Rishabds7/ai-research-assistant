import os
import django
import sys

# Setup Django environment
sys.path.append('/Users/rishabdarshanshylendra/Documents/Personal Project/research-assistant-mvp/backend')
os.environ.setdefault('DJANGO_SETTINGS_MODULE', 'core.settings')
django.setup()

from papers.models import Paper, SectionSummary
from services.llm_service import LLMService

def reprocess_info():
    papers = Paper.objects.all()
    llm = LLMService()
    for paper in papers:
        print(f"Checking {paper.filename}...")
        updated = False
        
        # 1. Extract Title/Authors if missing
        if not paper.title or paper.title in ['Unknown', 'Not Available']:
            print(f"  Extracting Title/Authors...")
            info = llm.extract_paper_info(paper.full_text[:15000])
            paper.title = info.get('title', 'Unknown')
            paper.authors = info.get('authors', 'Unknown')
            print(f"    -> Title: {paper.title}")
            print(f"    -> Authors: {paper.authors}")
            updated = True
            
        # 2. Extract Global Summary if missing
        if not paper.global_summary:
            summaries = {}
            section_objs = SectionSummary.objects.filter(paper=paper).order_by('order_index')
            for s in section_objs:
                summaries[s.section_name] = s.summary
            
            if summaries:
                print(f"  Generating global summary...")
                global_sum = llm.generate_global_summary(summaries)
                paper.global_summary = global_sum
                updated = True
        
        if updated:
            paper.save()
            print(f"  Done: {paper.title}")
        else:
            print(f"  Already up to date.")

if __name__ == "__main__":
    reprocess_info()
