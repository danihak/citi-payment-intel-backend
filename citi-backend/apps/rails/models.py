import uuid
from django.db import models
from django.utils import timezone


class RailHealthSnapshot(models.Model):
    RAIL_CHOICES = [
        ('UPI', 'Unified Payments Interface'),
        ('IMPS', 'Immediate Payment Service'),
        ('RTGS', 'Real Time Gross Settlement'),
        ('NEFT', 'National Electronic Funds Transfer'),
        ('NACH', 'National Automated Clearing House'),
    ]

    STATUS_CHOICES = [
        ('healthy', 'Healthy'),
        ('degraded', 'Degraded'),
        ('down', 'Down'),
        ('maintenance', 'Maintenance'),
    ]

    id = models.UUIDField(primary_key=True, default=uuid.uuid4, editable=False)
    rail_name = models.CharField(max_length=10, choices=RAIL_CHOICES)
    success_rate = models.DecimalField(max_digits=5, decimal_places=2)  # 0.00 to 100.00
    latency_ms = models.IntegerField(default=0)
    transactions_per_min = models.IntegerField(default=0)
    status = models.CharField(max_length=20, choices=STATUS_CHOICES, default='healthy')
    error_rate = models.DecimalField(max_digits=5, decimal_places=2, default=0.00)
    snapshot_at = models.DateTimeField(default=timezone.now)
    raw_data = models.JSONField(default=dict)

    class Meta:
        ordering = ['-snapshot_at']
        indexes = [
            models.Index(fields=['rail_name', '-snapshot_at']),
            models.Index(fields=['status']),
        ]

    def __str__(self):
        return f"{self.rail_name} — {self.success_rate}% @ {self.snapshot_at}"
