from django.contrib import admin
from .models import RailHealthSnapshot

@admin.register(RailHealthSnapshot)
class RailHealthSnapshotAdmin(admin.ModelAdmin):
    list_display = ['rail_name', 'success_rate', 'status', 'latency_ms', 'snapshot_at']
    list_filter = ['rail_name', 'status']
    ordering = ['-snapshot_at']
