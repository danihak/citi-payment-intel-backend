from rest_framework import serializers
from .models import RailHealthSnapshot


class RailHealthSnapshotSerializer(serializers.ModelSerializer):
    class Meta:
        model = RailHealthSnapshot
        fields = '__all__'


class RailCurrentStatusSerializer(serializers.Serializer):
    """Aggregated current status — latest snapshot per rail."""
    rail_name = serializers.CharField()
    success_rate = serializers.DecimalField(max_digits=5, decimal_places=2)
    latency_ms = serializers.IntegerField()
    transactions_per_min = serializers.IntegerField()
    status = serializers.CharField()
    error_rate = serializers.DecimalField(max_digits=5, decimal_places=2)
    snapshot_at = serializers.DateTimeField()
