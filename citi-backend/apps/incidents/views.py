from rest_framework.views import APIView
from rest_framework.response import Response
from rest_framework import status
from django.utils import timezone
from .models import Incident
from .serializers import IncidentListSerializer, IncidentDetailSerializer


class IncidentListView(APIView):
    """GET /api/v1/incidents/ — paginated incident list with filters."""

    def get(self, request):
        qs = Incident.objects.all()

        status_filter = request.query_params.get('status')
        rail_filter = request.query_params.get('rail')
        severity_filter = request.query_params.get('severity')

        if status_filter:
            qs = qs.filter(status=status_filter)
        if rail_filter:
            qs = qs.filter(rail_name=rail_filter.upper())
        if severity_filter:
            qs = qs.filter(severity=severity_filter)

        qs = qs.order_by('-detected_at')[:100]
        serializer = IncidentListSerializer(qs, many=True)
        return Response(serializer.data)


class IncidentDetailView(APIView):
    """GET /api/v1/incidents/{id}/ — full incident detail with agent runs and rerouting."""

    def get(self, request, pk):
        try:
            incident = Incident.objects.prefetch_related(
                'agent_runs', 'rerouting', 'communications'
            ).get(id=pk)
        except Incident.DoesNotExist:
            return Response({'error': 'Incident not found'}, status=status.HTTP_404_NOT_FOUND)
        serializer = IncidentDetailSerializer(incident)
        return Response(serializer.data)


class IncidentResolveView(APIView):
    """POST /api/v1/incidents/{id}/resolve/ — mark incident as resolved."""

    def post(self, request, pk):
        try:
            incident = Incident.objects.get(id=pk)
        except Incident.DoesNotExist:
            return Response({'error': 'Not found'}, status=404)
        incident.status = 'resolved'
        incident.resolved_at = timezone.now()
        incident.save()
        return Response({'status': 'resolved', 'resolved_at': incident.resolved_at.isoformat()})


class SimulateIncidentView(APIView):
    """POST /api/v1/incidents/simulate/ — trigger a synthetic incident (demo only)."""

    def post(self, request):
        rail = request.data.get('rail', 'UPI')
        success_rate = float(request.data.get('success_rate', 71.3))

        from apps.rails.models import RailHealthSnapshot
        snapshot = RailHealthSnapshot.objects.create(
            rail_name=rail,
            success_rate=success_rate,
            latency_ms=1850,
            transactions_per_min=3200,
            status='down' if success_rate < 80 else 'degraded',
            error_rate=round(100 - success_rate, 2),
            raw_data={'source': 'demo_simulation', 'note': 'April 12-style synthetic incident'},
        )

        from agents.incident_classifier import run as classify
        task = classify.delay({
            'snapshot_id': str(snapshot.id),
            'rail_name': rail,
            'success_rate': success_rate,
            'latency_ms': 1850,
            'error_rate': round(100 - success_rate, 2),
        })

        return Response({
            'status': 'incident_triggered',
            'rail': rail,
            'success_rate': success_rate,
            'task_id': task.id,
            'note': 'Classification will appear on dashboard within ~10 seconds',
        })
