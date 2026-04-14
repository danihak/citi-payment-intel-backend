from rest_framework import serializers
from .models import Incident, AgentRun, ReroutingRecommendation


class ReroutingSerializer(serializers.ModelSerializer):
    class Meta:
        model = ReroutingRecommendation
        fields = '__all__'


class AgentRunSerializer(serializers.ModelSerializer):
    class Meta:
        model = AgentRun
        fields = '__all__'


class IncidentListSerializer(serializers.ModelSerializer):
    class Meta:
        model = Incident
        fields = [
            'id', 'rail_name', 'classification', 'confidence_score',
            'severity', 'status', 'title', 'detected_at', 'resolved_at',
        ]


class IncidentDetailSerializer(serializers.ModelSerializer):
    agent_runs = AgentRunSerializer(many=True, read_only=True)
    rerouting = ReroutingSerializer(many=True, read_only=True)

    class Meta:
        model = Incident
        fields = '__all__'
