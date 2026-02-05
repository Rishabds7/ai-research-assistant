"""
DJANGO ADMIN CONFIGURATION
Project: Research Assistant
File: backend/papers/admin.py

Defines the Look and Feel of the '/admin' dashboard.
Allows you to view, filter, and search your uploaded papers and AI results in a GUI.
"""
from django.contrib import admin

# Register your models here.

from .models import Paper, Methodology, SectionSummary, TaskStatus

@admin.register(Paper)
class PaperAdmin(admin.ModelAdmin):
    list_display = ('title', 'authors', 'processed', 'uploaded_at')
    list_filter = ('processed', 'uploaded_at')
    search_fields = ('title', 'authors', 'full_text')
    readonly_fields = ('uploaded_at',)

@admin.register(Methodology)
class MethodologyAdmin(admin.ModelAdmin):
    list_display = ('paper', 'summary')
    list_filter = ('paper__processed',)
    search_fields = ('paper__title', 'summary')

@admin.register(SectionSummary)
class SectionSummaryAdmin(admin.ModelAdmin):
    list_display = ('paper', 'section_name', 'summary')
    list_filter = ('paper__processed', 'section_name')
    search_fields = ('paper__title', 'section_name', 'summary')


@admin.register(TaskStatus)
class TaskStatusAdmin(admin.ModelAdmin):
    list_display = ('task_id', 'task_type', 'status', 'created_at', 'updated_at')
    list_filter = ('task_type', 'status', 'created_at')
    search_fields = ('task_id', 'task_type', 'status', 'error')
    readonly_fields = ('created_at', 'updated_at')
    date_hierarchy = 'created_at'