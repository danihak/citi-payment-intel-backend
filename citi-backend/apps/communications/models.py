import uuid
from django.db import models
from apps.incidents.models import Incident


class CommunicationDraft(models.Model):
    AUDIENCE_CHOICES = [
        ('client_services', 'Client Services (internal)'),
        ('corporate_client', 'Corporate Client (external)'),
        ('relationship_manager', 'Relationship Manager'),
        ('management', 'Management / MD'),
    ]

    STATUS_CHOICES = [
        ('draft', 'Draft'),
        ('approved', 'Approved'),
        ('sent', 'Sent'),
        ('rejected', 'Rejected — needs revision'),
    ]

    id = models.UUIDField(primary_key=True, default=uuid.uuid4, editable=False)
    incident = models.ForeignKey(Incident, on_delete=models.CASCADE, related_name='communications')
    audience = models.CharField(max_length=30, choices=AUDIENCE_CHOICES, default='client_services')
    subject_line = models.CharField(max_length=200, blank=True)
    draft_text = models.TextField()
    tone_notes = models.TextField(blank=True)
    status = models.CharField(max_length=30, choices=STATUS_CHOICES, default='draft')
    approved_by = models.CharField(max_length=100, blank=True)
    approved_at = models.DateTimeField(null=True, blank=True)
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)

    class Meta:
        ordering = ['-created_at']

    def __str__(self):
        return f"Draft for {self.incident.rail_name} incident — {self.audience} [{self.status}]"
