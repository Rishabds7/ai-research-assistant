"""
DATABASE MODELS
Project: Research Assistant
File: backend/papers/models.py

This file defines the data structure of the application using Django Models.
It handles storage for:
1. Uploaded Paper PDFs and their raw text.
2. AI-extracted Methodology data (models, datasets, results).
3. Section-by-section AI summaries.
4. Vector Embeddings for semantic search.
5. Background task status tracking.
"""

import uuid
import os
from typing import Any, Dict, List, Optional
from django.db import models
from django.db.models.signals import post_delete
from django.dispatch import receiver
from pgvector.django import VectorField


class Paper(models.Model):
    """
    The core data model representing a Research Paper.

    Attributes:
        id (UUID): Primary key.
        session_id (str): Browser fingerprint for user isolation.
        filename (str): Original name of the uploaded file.
        file (FileField): Path to the stored PDF.
        uploaded_at (datetime): Timestamp of upload.
        processed (bool): extraction status flag.
        full_text (str): Raw text content of the PDF.
        sections (dict): JSON dict of section_name -> text content.
        metadata (dict): JSON dict of extracted metadata (datasets, licenses).
        task_ids (dict): Tracking IDs for background Celery tasks.
        title (str): AI-extracted title.
        authors (str): AI-extracted authors.
        year (str): Publication year.
        journal (str): Publication venue.
        notes (str): User-generated notes.
        global_summary (str): AI-generated TL;DR.
    """
    id = models.UUIDField(primary_key=True, default=uuid.uuid4, editable=False)
    # Session ID allows us to silo papers for different users based on their browser fingerprint
    session_id = models.CharField(max_length=100, blank=True, null=True, db_index=True)
    filename = models.CharField(max_length=255)
    file = models.FileField(upload_to='papers/') # Actual PDF file storage
    uploaded_at = models.DateTimeField(auto_now_add=True)
    
    # Processing Flags
    # True only after the initial PDF text extraction and sectioning is complete
    processed = models.BooleanField(default=False) # True when text extraction is done
    full_text = models.TextField(blank=True) # Entire text of the paper
    # 'sections' stores the raw text of each logical part (Abstract, Intro, etc.) for target-searching
    sections = models.JSONField(default=dict, blank=True) # Dict of {SectionTitle: Content}
    # 'metadata' stores auxiliary extraction results like Datasets and Licenses found in text
    metadata = models.JSONField(default=dict, blank=True) # Extracted fields like datasets/licenses
    # 'task_ids' tracks active Celery background tasks to prevent duplicate processing
    task_ids = models.JSONField(default=dict, blank=True) # Tracking Celery tasks for this paper
    
    # These are populated using LLM extraction to show a professional 'Title' instead of just filename
    title = models.TextField(blank=True) # Changed to TextField to support very long titles
    authors = models.TextField(blank=True)
    year = models.CharField(max_length=20, blank=True)
    journal = models.CharField(max_length=500, blank=True)
    # Personal notes field allow researchers to map their own thoughts alongside AI insights
    notes = models.TextField(blank=True)
    # Global Summary is the 'TL;DR' table-level summary for the Review tab
    global_summary = models.TextField(blank=True)
    
    # SWOT Analysis (NEW FEATURE)
    swot_analysis = models.TextField(blank=True)
    swot_analysis_updated_at = models.DateTimeField(null=True, blank=True)
    
    class Meta:
        ordering = ['-uploaded_at']
    
    def __str__(self) -> str:
        return str(self.filename)


class Collection(models.Model):
    """
    Named collections of papers for organization.
    
    Attributes:
        id (UUID): Primary key.
        session_id (str): Owner's session ID.
        name (str): Collection name.
        description (str): Optional description.
        papers (ManyToManyField): Papers in this collection.
    """
    id = models.UUIDField(primary_key=True, default=uuid.uuid4, editable=False)
    session_id = models.CharField(max_length=100, db_index=True)
    name = models.CharField(max_length=255)
    description = models.TextField(blank=True)
    papers = models.ManyToManyField(Paper, related_name='collections', blank=True)
    
    # Research Gap Analysis (NEW FEATURE)
    gap_analysis = models.TextField(blank=True)
    gap_analysis_updated_at = models.DateTimeField(null=True, blank=True)
    
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)
    
    class Meta:
        ordering = ['-created_at']
        unique_together = ['session_id', 'name']
    
    def __str__(self) -> str:
        return f"{self.name} ({self.papers.count()} papers)"


class Methodology(models.Model):
    """
    Detailed technical data extracted via LLM. One methodology per paper.
    
    Attributes:
        id (UUID): Primary key.
        paper (OneToOneField): Link to parent Paper.
        datasets (list): Extracted dataset names.
        model (dict): Model architecture details.
        metrics (list): Evaluation metrics.
        results (dict): Key findings.
        summary (str): Narrative summary.
    """
    id = models.UUIDField(primary_key=True, default=uuid.uuid4, editable=False)
    paper = models.OneToOneField(Paper, on_delete=models.CASCADE, related_name='methodology')
    datasets = models.JSONField(default=list, blank=True) # List of dataset names
    model = models.JSONField(default=dict, blank=True)   # Model architecture details
    metrics = models.JSONField(default=list, blank=True) # Evaluation metrics used
    results = models.JSONField(default=dict, blank=True) # Key findings/numbers
    summary = models.TextField(blank=True)               # Narrative methodology summary
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)
    
    class Meta:
        verbose_name_plural = 'Methodologies'
    
    def __str__(self) -> str:
        return f"Methodology for {self.paper.filename}"


class SectionSummary(models.Model):
    """
    Stores individual summaries for logical sections.
    
    Attributes:
        id (UUID): Primary key.
        paper (ForeignKey): Parent Paper.
        section_name (str): Name of the section (e.g., 'Introduction').
        summary (str): AI-generated summary content.
        order_index (int): For ordering sections correctly.
    """
    id = models.UUIDField(primary_key=True, default=uuid.uuid4, editable=False)
    paper = models.ForeignKey(Paper, on_delete=models.CASCADE, related_name='section_summaries')
    section_name = models.CharField(max_length=100)
    summary = models.TextField()
    order_index = models.IntegerField(default=0)
    created_at = models.DateTimeField(auto_now_add=True)
    
    class Meta:
        unique_together = ['paper', 'section_name']
        ordering = ['order_index', 'created_at']
    
    def __str__(self) -> str:
        return f"{self.paper.filename} - {self.section_name}"


class Embedding(models.Model):
    """
    Dense vector representations of paper segments.
    
    Attributes:
        id (UUID): Primary key.
        paper (ForeignKey): Parent Paper.
        section_name (str): Section source of the text.
        text (str): Raw text segment.
        embedding (VectorField): 768-dim vector.
    """
    id = models.UUIDField(primary_key=True, default=uuid.uuid4, editable=False)
    paper = models.ForeignKey(Paper, on_delete=models.CASCADE, related_name='embeddings')
    section_name = models.CharField(max_length=100, blank=True)
    text = models.TextField() # The raw text segment that was embedded
    embedding = VectorField(dimensions=768)  # 768-dim vector for Google text-embedding-004
    created_at = models.DateTimeField(auto_now_add=True)
    
    class Meta:
        indexes = [
            models.Index(fields=['paper', 'section_name']),
        ]
    
    def __str__(self) -> str:
        return f"Embedding for {self.paper.filename}"


class TaskStatus(models.Model):
    """
    A custom tracker for Celery background tasks.
    
    Attributes:
        id (UUID): Primary key.
        task_id (str): Celery task UUID.
        task_type (str): Name of the task (e.g., 'summarize').
        status (str): Current state (pending, running, completed, failed).
        result (dict): JSON output on completion.
        error (str): Error message if failed.
    """
    
    STATUS_CHOICES = [
        ('pending', 'Pending'),
        ('running', 'Running'),
        ('completed', 'Completed'),
        ('failed', 'Failed'),
    ]
    
    id = models.UUIDField(primary_key=True, default=uuid.uuid4, editable=False)
    task_id = models.CharField(max_length=255, unique=True, db_index=True)
    task_type = models.CharField(max_length=50)
    status = models.CharField(max_length=20, choices=STATUS_CHOICES, default='pending')
    result = models.JSONField(null=True, blank=True)
    error = models.TextField(blank=True)
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)
    
    class Meta:
        ordering = ['-created_at']
        verbose_name_plural = 'Task statuses'
    
    def __str__(self) -> str:
        return f"{self.task_type} - {self.status}"


@receiver(post_delete, sender=Paper)
def auto_delete_file_on_delete(sender: Any, instance: Paper, **kwargs: Any) -> None:
    """
    Deletes file from filesystem when corresponding `Paper` object is deleted.
    
    Args:
        sender: The model class.
        instance: The actual instance being deleted.
        **kwargs: Signal kwargs.
    """
    if instance.file:
        if os.path.isfile(instance.file.path):
            os.remove(instance.file.path)
