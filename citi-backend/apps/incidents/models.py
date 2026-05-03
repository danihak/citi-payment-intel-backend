import uuid
from django.db import models
from django.utils import timezone
from apps.rails.models import RailHealthSnapshot


class Incident(models.Model):
    CLASSIFICATION_CHOICES = [
        ('NPCI_SIDE', 'NPCI Infrastructure Issue'),
        ('BANK_SIDE', 'Bank-side Failure'),
        ('FALSE_POSITIVE', 'False Positive'),
        ('UNKNOWN', 'Under Investigation'),
    ]

    SEVERITY_CHOICES = [
        ('low', 'Low'),
        ('medium', 'Medium'),
        ('high', 'High'),
        ('critical', 'Critical'),
    ]

    STATUS_CHOICES = [
        ('active', 'Active'),
        ('investigating', 'Investigating'),
        ('resolved', 'Resolved'),
        ('false_positive', 'False Positive'),
    ]

    id = models.UUIDField(primary_key=True, default=uuid.uuid4, editable=False)
    rail = models.ForeignKey(RailHealthSnapshot, on_delete=models.SET_NULL, null=True, related_name='incidents')
    rail_name = models.CharField(max_length=10, default='UPI')
    classification = models.CharField(max_length=20, choices=CLASSIFICATION_CHOICES, default='UNKNOWN')
    confidence_score = models.DecimalField(max_digits=5, decimal_places=2, default=0.00)
    severity = models.CharField(max_length=10, choices=SEVERITY_CHOICES, default='medium')
    status = models.CharField(max_length=20, choices=STATUS_CHOICES, default='active')
    title = models.CharField(max_length=200, default='Payment rail degradation detected')
    classifier_reasoning = models.TextField(blank=True)
    historical_match = models.CharField(max_length=200, blank=True)
    detected_at = models.DateTimeField(default=timezone.now)
    resolved_at = models.DateTimeField(null=True, blank=True)

    class Meta:
        ordering = ['-detected_at']
        indexes = [
            models.Index(fields=['status']),
            models.Index(fields=['rail_name', '-detected_at']),
        ]

    def __str__(self):
        return f"{self.rail_name} — {self.classification} ({self.severity}) @ {self.detected_at}"


class AgentRun(models.Model):
    AGENT_CHOICES = [
        ('rail_monitor', 'Rail Monitor'),
        ('incident_classifier', 'Incident Classifier'),
        ('rerouting_advisor', 'Rerouting Advisor'),
        ('compliance_watchdog', 'Compliance Watchdog'),
        ('comms_generator', 'Communication Generator'),
    ]

    STATUS_CHOICES = [
        ('running', 'Running'),
        ('completed', 'Completed'),
        ('failed', 'Failed'),
    ]

    id = models.UUIDField(primary_key=True, default=uuid.uuid4, editable=False)
    incident = models.ForeignKey(Incident, on_delete=models.CASCADE, related_name='agent_runs', null=True, blank=True)
    agent_type = models.CharField(max_length=30, choices=AGENT_CHOICES)
    status = models.CharField(max_length=20, choices=STATUS_CHOICES, default='running')
    input_data = models.JSONField(default=dict)
    output_data = models.JSONField(default=dict)
    duration_ms = models.IntegerField(default=0)
    error_message = models.TextField(blank=True)
    started_at = models.DateTimeField(default=timezone.now)
    completed_at = models.DateTimeField(null=True, blank=True)

    class Meta:
        ordering = ['-started_at']

    def __str__(self):
        return f"{self.agent_type} — {self.status} @ {self.started_at}"


class ReroutingRecommendation(models.Model):
    id = models.UUIDField(primary_key=True, default=uuid.uuid4, editable=False)
    incident = models.ForeignKey(Incident, on_delete=models.CASCADE, related_name='rerouting')
    from_rail = models.CharField(max_length=10)
    to_rail = models.CharField(max_length=10)
    confidence = models.DecimalField(max_digits=5, decimal_places=2, default=0.00)
    rationale = models.TextField()
    estimated_success_rate = models.DecimalField(max_digits=5, decimal_places=2, default=0.00)
    created_at = models.DateTimeField(default=timezone.now)

    class Meta:
        ordering = ['-created_at']

    def __str__(self):
        return f"{self.from_rail} → {self.to_rail} for incident {self.incident_id}"
