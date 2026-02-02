"""
Django models for research papers and related data.
"""

import uuid
import os
from django.db import models
from django.db.models.signals import post_delete
from django.dispatch import receiver
from pgvector.django import VectorField


class Paper(models.Model):
    """Represents an uploaded research paper PDF."""
    
    id = models.UUIDField(primary_key=True, default=uuid.uuid4, editable=False)
    filename = models.CharField(max_length=255)
    file = models.FileField(upload_to='papers/')
    uploaded_at = models.DateTimeField(auto_now_add=True)
    processed = models.BooleanField(default=False)
    full_text = models.TextField(blank=True)
    sections = models.JSONField(default=dict, blank=True)
    metadata = models.JSONField(default=dict, blank=True)
    task_ids = models.JSONField(default=dict, blank=True) # {"summarize": "...", "datasets": "...", "licenses": "..."}
    
    class Meta:
        ordering = ['-uploaded_at']
    
    def __str__(self):
        return self.filename


class Methodology(models.Model):
    """Extracted methodology information from a paper."""
    
    id = models.UUIDField(primary_key=True, default=uuid.uuid4, editable=False)
    paper = models.OneToOneField(Paper, on_delete=models.CASCADE, related_name='methodology')
    datasets = models.JSONField(default=list, blank=True)
    model = models.JSONField(default=dict, blank=True)
    metrics = models.JSONField(default=list, blank=True)
    results = models.JSONField(default=dict, blank=True)
    summary = models.TextField(blank=True)
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)
    
    class Meta:
        verbose_name_plural = 'Methodologies'
    
    def __str__(self):
        return f"Methodology for {self.paper.filename}"


class SectionSummary(models.Model):
    """Summaries of individual sections within a paper."""
    
    id = models.UUIDField(primary_key=True, default=uuid.uuid4, editable=False)
    paper = models.ForeignKey(Paper, on_delete=models.CASCADE, related_name='section_summaries')
    section_name = models.CharField(max_length=100)
    summary = models.TextField()
    order_index = models.IntegerField(default=0)
    created_at = models.DateTimeField(auto_now_add=True)
    
    class Meta:
        unique_together = ['paper', 'section_name']
        ordering = ['order_index', 'created_at']
    
    def __str__(self):
        return f"{self.paper.filename} - {self.section_name}"


class Embedding(models.Model):
    """Vector embeddings for semantic search using pgvector."""
    
    id = models.UUIDField(primary_key=True, default=uuid.uuid4, editable=False)
    paper = models.ForeignKey(Paper, on_delete=models.CASCADE, related_name='embeddings')
    section_name = models.CharField(max_length=100, blank=True)
    text = models.TextField()
    embedding = VectorField(dimensions=384)  # all-MiniLM-L6-v2 dimension
    created_at = models.DateTimeField(auto_now_add=True)
    
    class Meta:
        indexes = [
            models.Index(fields=['paper', 'section_name']),
        ]
    
    def __str__(self):
        return f"Embedding for {self.paper.filename}"


class TaskStatus(models.Model):
    """Track status of asynchronous Celery tasks."""
    
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
    
    def __str__(self):
        return f"{self.task_type} - {self.status}"


class GapAnalysis(models.Model):
    """Research gap analysis results for a set of papers."""
    
    id = models.UUIDField(primary_key=True, default=uuid.uuid4, editable=False)
    papers = models.ManyToManyField(Paper, related_name='gap_analyses')
    methodological_gaps = models.JSONField(default=list)
    dataset_limitations = models.JSONField(default=list)
    evaluation_gaps = models.JSONField(default=list)
    novel_directions = models.JSONField(default=list)
    created_at = models.DateTimeField(auto_now_add=True)
    
    class Meta:
        verbose_name_plural = 'Gap analyses'
        ordering = ['-created_at']
    
    def __str__(self):
        return f"Gap Analysis - {self.created_at.strftime('%Y-%m-%d %H:%M')}"

@receiver(post_delete, sender=Paper)
def auto_delete_file_on_delete(sender, instance, **kwargs):
    """
    Deletes file from filesystem
    when corresponding `Paper` object is deleted.
    """
    if instance.file:
        if os.path.isfile(instance.file.path):
            os.remove(instance.file.path)
