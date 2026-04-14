from django.contrib import admin
from .models import ApiComplianceMetric, ComplianceViolation

@admin.register(ApiComplianceMetric)
class ApiComplianceMetricAdmin(admin.ModelAdmin):
    list_display = ['api_name', 'tps_current', 'tps_limit', 'is_compliant', 'measured_at']
    list_filter = ['api_name', 'is_compliant']

@admin.register(ComplianceViolation)
class ComplianceViolationAdmin(admin.ModelAdmin):
    list_display = ['api_name', 'tps_observed', 'tps_limit', 'severity', 'occurred_at']
