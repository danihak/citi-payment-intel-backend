from rest_framework.views import APIView
from rest_framework.response import Response
from rest_framework import status
from django.db.models import Subquery, OuterRef
from .models import RailHealthSnapshot
from .serializers import RailHealthSnapshotSerializer


class RailCurrentStatusView(APIView):
    """GET /api/v1/rails/status/ — latest snapshot per rail."""

    def get(self, request):
        rails = ['UPI', 'IMPS', 'RTGS', 'NEFT', 'NACH']
        result = []
        for rail in rails:
            latest = RailHealthSnapshot.objects.filter(
                rail_name=rail
            ).order_by('-snapshot_at').first()
            if latest:
                result.append({
                    'rail_name': latest.rail_name,
                    'success_rate': float(latest.success_rate),
                    'latency_ms': latest.latency_ms,
                    'transactions_per_min': latest.transactions_per_min,
                    'status': latest.status,
                    'error_rate': float(latest.error_rate),
                    'snapshot_at': latest.snapshot_at.isoformat(),
                })
        return Response(result)


class RailHistoryView(APIView):
    """GET /api/v1/rails/{rail_name}/history/ — last 50 snapshots for sparkline."""

    def get(self, request, rail_name):
        snapshots = RailHealthSnapshot.objects.filter(
            rail_name=rail_name.upper()
        ).order_by('-snapshot_at')[:50]
        serializer = RailHealthSnapshotSerializer(snapshots, many=True)
        return Response(serializer.data)


class TriggerPollView(APIView):
    """POST /api/v1/rails/poll/ — manually trigger a rail poll (for demo)."""

    def post(self, request):
        from agents.rail_monitor import run
        task = run.delay()
        return Response({'task_id': task.id, 'status': 'triggered'})


class SeedDataView(APIView):
    """POST /api/v1/rails/seed/ — reseed demo data on demand."""

    def post(self, request):
        from django.core.management import call_command
        from io import StringIO
        out = StringIO()
        call_command('seed_demo', stdout=out)
        return Response({'status': 'seeded', 'output': out.getvalue()})
