import uuid
from django.db import models
from django.utils import timezone


class ApiComplianceMetric(models.Model):
    """Tracks OC-215 compliance: Citi's outgoing API call rate to NPCI."""

    API_CHOICES = [
        ('check_transaction_status', 'Check Transaction Status'),
        ('initiate_payment', 'Initiate Payment'),
        ('balance_enquiry', 'Balance Enquiry'),
        ('validate_vpa', 'Validate VPA'),
    ]

    id = models.UUIDField(primary_key=True, default=uuid.uuid4, editable=False)
    api_name = models.CharField(max_length=50, choices=API_CHOICES)
    tps_current = models.DecimalField(max_digits=8, decimal_places=2, default=0.00)
    tps_limit = models.DecimalField(max_digits=8, decimal_places=2, default=3.00)
    calls_last_minute = models.IntegerField(default=0)
    calls_last_hour = models.IntegerField(default=0)
    violation_count = models.IntegerField(default=0)
    is_compliant = models.BooleanField(default=True)
    measured_at = models.DateTimeField(default=timezone.now)

    class Meta:
        ordering = ['-measured_at']
        indexes = [
            models.Index(fields=['api_name', '-measured_at']),
            models.Index(fields=['is_compliant']),
        ]

    def __str__(self):
        status = "COMPLIANT" if self.is_compliant else "VIOLATION"
        return f"{self.api_name} — {self.tps_current} TPS [{status}]"


class ComplianceViolation(models.Model):
    """Audit log of OC-215 violations."""

    SEVERITY_CHOICES = [
        ('warning', 'Warning'),
        ('violation', 'Violation'),
        ('critical', 'Critical'),
    ]

    id = models.UUIDField(primary_key=True, default=uuid.uuid4, editable=False)
    metric = models.ForeignKey(ApiComplianceMetric, on_delete=models.CASCADE, related_name='violations')
    api_name = models.CharField(max_length=50)
    tps_observed = models.DecimalField(max_digits=8, decimal_places=2)
    tps_limit = models.DecimalField(max_digits=8, decimal_places=2)
    severity = models.CharField(max_length=10, choices=SEVERITY_CHOICES)
    description = models.TextField()
    occurred_at = models.DateTimeField(default=timezone.now)

    class Meta:
        ordering = ['-occurred_at']

    def __str__(self):
        return f"OC-215 {self.severity}: {self.api_name} at {self.tps_observed} TPS"
