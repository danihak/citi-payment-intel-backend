from django.contrib import admin
from .models import CommunicationDraft

@admin.register(CommunicationDraft)
class CommunicationDraftAdmin(admin.ModelAdmin):
    list_display = ['incident', 'audience', 'status', 'approved_by', 'created_at']
    list_filter = ['audience', 'status']
