from django.contrib import admin
from .models import Incident, AgentRun, ReroutingRecommendation

@admin.register(Incident)
class IncidentAdmin(admin.ModelAdmin):
    list_display = ['rail_name', 'classification', 'confidence_score', 'severity', 'status', 'detected_at']
    list_filter = ['classification', 'severity', 'status', 'rail_name']
    ordering = ['-detected_at']

@admin.register(AgentRun)
class AgentRunAdmin(admin.ModelAdmin):
    list_display = ['agent_type', 'status', 'duration_ms', 'started_at']
    list_filter = ['agent_type', 'status']
