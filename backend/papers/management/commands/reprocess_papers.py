from django.core.management.base import BaseCommand
from papers.models import Paper
from papers.tasks import process_pdf_task, extract_metadata_task, extract_all_sections_task

class Command(BaseCommand):
    help = 'Reprocess all papers with new extraction logic'

    def handle(self, *args, **options):
        papers = Paper.objects.all()
        self.stdout.write(self.style.SUCCESS(f"Found {len(papers)} papers to re-process."))
        
        for paper in papers:
            self.stdout.write(f"Queuing re-processing for: {paper.filename} ({paper.id})")
            
            # 1. Re-process PDF (Extract text/sections with new logic)
            process_pdf_task.delay(str(paper.id))
            
            # 2. Re-extract Datasets
            extract_metadata_task.delay(str(paper.id), 'datasets')
            
            # 3. Re-extract Licenses
            extract_metadata_task.delay(str(paper.id), 'licenses')
            
            # 4. Re-generate Summaries
            extract_all_sections_task.delay(str(paper.id))

        self.stdout.write(self.style.SUCCESS("All re-processing tasks have been queued in Celery."))
