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


class IncidentSnapshotHistoryView(APIView):
    """GET /api/v1/incidents/{id}/snapshot-history/ — snapshots in the incident's time window.

    Unlike the generic /api/v1/rails/{rail}/history/ endpoint (which returns the
    last 50 snapshots regardless of incident timing), this one returns snapshots
    specifically around the incident in question:
      - From detected_at - 6 minutes (to show baseline before the dip)
      - To resolved_at + 6 minutes if resolved, or 'now' if still active

    The chart on IncidentDetail uses this so a resolved incident from 2 hours
    ago shows its actual dip pattern, not whatever the rail is doing right now.
    """

    def get(self, request, pk):
        from datetime import timedelta
        from django.utils import timezone
        from apps.rails.models import RailHealthSnapshot

        try:
            incident = Incident.objects.get(id=pk)
        except Incident.DoesNotExist:
            return Response({'error': 'Not found'}, status=status.HTTP_404_NOT_FOUND)

        start = incident.detected_at - timedelta(minutes=6)
        end = (incident.resolved_at + timedelta(minutes=6)) if incident.resolved_at else timezone.now()

        snapshots = RailHealthSnapshot.objects.filter(
            rail_name=incident.rail_name,
            snapshot_at__gte=start,
            snapshot_at__lte=end,
        ).order_by('snapshot_at')

        # Cap at 120 to avoid pathological cases
        snapshot_data = [
            {
                'rail_name': s.rail_name,
                'success_rate': float(s.success_rate),
                'latency_ms': s.latency_ms,
                'transactions_per_min': s.transactions_per_min,
                'status': s.status,
                'error_rate': float(s.error_rate),
                'snapshot_at': s.snapshot_at.isoformat(),
            }
            for s in snapshots[:120]
        ]

        return Response({
            'incident_id': str(incident.id),
            'rail_name': incident.rail_name,
            'detected_at': incident.detected_at.isoformat(),
            'resolved_at': incident.resolved_at.isoformat() if incident.resolved_at else None,
            'window_start': start.isoformat(),
            'window_end': end.isoformat(),
            'snapshots': snapshot_data,
        })


class SimulateIncidentView(APIView):
    """POST /api/v1/incidents/simulate/ — trigger a synthetic incident (demo only).

    For a demo button that might be clicked live during a recording, we cannot
    depend on Celery being healthy or the Claude API key being valid. So this
    endpoint creates the full incident record synchronously — snapshot, incident,
    all five agent runs, rerouting recommendation, both comms drafts — and
    returns the incident_id so the frontend can navigate to it immediately.

    The async classifier path is still kicked off in parallel as a 'real' flow
    demonstration, but the UI commits the incident the moment this returns 200.
    Idempotent within a 60-second window so spamming the button does not
    pollute the queue.
    """

    def post(self, request):
        from datetime import timedelta
        from django.utils import timezone
        import random
        from apps.rails.models import RailHealthSnapshot
        from .models import Incident, AgentRun, ReroutingRecommendation
        from apps.communications.models import CommunicationDraft

        rail = request.data.get('rail', 'UPI').upper()
        success_rate = float(request.data.get('success_rate', 71.3))
        now = timezone.now()

        # Templates per rail — deterministic so the demo always tells the same story
        TEMPLATES = {
            'UPI': {
                'classification': 'NPCI_SIDE',
                'confidence': 93,
                'severity': 'critical',
                'title': 'UPI down — NPCI Check Transaction Status API overload (simulated)',
                'reasoning': (
                    f'Rapid success-rate drop to {success_rate}% within 8 minutes. '
                    f'Latency at 1,850ms (6.5x baseline). Pattern matches April 12 2025 '
                    f'NPCI infrastructure overload — multiple PSPs flooding Check Transaction '
                    f'Status API. Rerouting to IMPS recommended for non-time-sensitive flows.'
                ),
                'historical_match': 'April 12, 2025 — UPI — NPCI_SIDE (5-hour outage, ₹2,400 Cr impacted)',
                'rerouting': ('IMPS', 98.9, 'IMPS operating at 98.9% with 395ms latency. Recommended for corporate collection flows, dealer settlements, institutional transfers.'),
            },
            'IMPS': {
                'classification': 'BANK_SIDE',
                'confidence': 81,
                'severity': 'high',
                'title': 'IMPS degradation — Citi internal switch failover (simulated)',
                'reasoning': f'IMPS at {success_rate}%. Only Citi transactions affected, other PSPs normal. Internal switch failover signature.',
                'historical_match': 'March 26, 2025 — IMPS — BANK_SIDE (switch failover)',
                'rerouting': ('NEFT', 99.6, 'NEFT operating at 99.6% with 372ms latency. Suitable for non-urgent transfers.'),
            },
            'RTGS': {
                'classification': 'NPCI_SIDE',
                'confidence': 86,
                'severity': 'medium',
                'title': 'RTGS settlement delays — RBI RTGS system upgrade (simulated)',
                'reasoning': f'RTGS at {success_rate}%. RBI RTGS system upgrade causing intermittent settlement failures.',
                'historical_match': 'October 8, 2024 — RTGS — NPCI_SIDE',
                'rerouting': ('NEFT', 99.6, 'NEFT available for sub-₹2 Cr transactions. SWIFT for cross-border.'),
            },
            'NEFT': {
                'classification': 'NPCI_SIDE',
                'confidence': 82,
                'severity': 'high',
                'title': 'NEFT batch failure — NPCI clearing engine restart (simulated)',
                'reasoning': f'NEFT at {success_rate}%. NPCI NEFT clearing engine restarted mid-batch.',
                'historical_match': 'January 14, 2025 — NEFT — NPCI_SIDE',
                'rerouting': ('IMPS', 98.9, 'IMPS available for real-time settlement. Suitable for urgent transfers.'),
            },
            'NACH': {
                'classification': 'NPCI_SIDE',
                'confidence': 87,
                'severity': 'critical',
                'title': 'NACH bulk debit failure — NPCI mandate registry down (simulated)',
                'reasoning': f'NACH at {success_rate}%. All corporate bulk debit mandates failing.',
                'historical_match': 'October 8, 2024 — RTGS — NPCI_SIDE',
                'rerouting': ('NEFT', 99.6, 'NEFT available for individual transfers. Reschedule bulk to next NACH window.'),
            },
        }
        tpl = TEMPLATES.get(rail, TEMPLATES['UPI'])

        # Idempotency: if a simulated incident was created on this rail in the last
        # 60 seconds, just bump its timestamp instead of creating a duplicate.
        recent = Incident.objects.filter(
            rail_name=rail,
            status='active',
            title__icontains='(simulated)',
            detected_at__gte=now - timedelta(seconds=60),
        ).order_by('-detected_at').first()

        if recent:
            recent.detected_at = now
            recent.save(update_fields=['detected_at'])
            return Response({
                'status': 'incident_refreshed',
                'incident_id': str(recent.id),
                'rail': rail,
                'note': 'Existing simulated incident refreshed (clicked within 60s).',
            })

        # Fresh snapshot
        snapshot = RailHealthSnapshot.objects.create(
            rail_name=rail,
            success_rate=success_rate,
            latency_ms=1850,
            transactions_per_min=3200,
            status='down' if success_rate < 80 else 'degraded',
            error_rate=round(100 - success_rate, 2),
            snapshot_at=now,
            raw_data={'source': 'demo_simulation', 'note': 'April 12-style synthetic incident'},
        )

        # Create the incident inline (no Celery, no Claude dependency)
        incident = Incident.objects.create(
            rail=snapshot,
            rail_name=rail,
            classification=tpl['classification'],
            confidence_score=tpl['confidence'],
            severity=tpl['severity'],
            status='active',
            title=tpl['title'],
            classifier_reasoning=tpl['reasoning'],
            historical_match=tpl['historical_match'],
            detected_at=now,
        )

        # All 5 agent runs marked completed with realistic timings
        agent_specs = [
            ('rail_monitor', 92, {'rail': rail, 'success_rate': success_rate}, {'anomaly_detected': True}, 30),
            ('incident_classifier', 3450, {'rail': rail}, {'classification': tpl['classification'], 'confidence': tpl['confidence']}, 90),
            ('rerouting_advisor', 1280, {'from_rail': rail}, {'to_rail': tpl['rerouting'][0], 'viable': True}, 110),
            ('compliance_watchdog', 480, {}, {'all_compliant': True}, 120),
            ('comms_generator', 4720, {}, {'drafts_created': 2}, 150),
        ]
        for agent_type, duration_ms, input_data, output_data, completed_offset_s in agent_specs:
            AgentRun.objects.create(
                incident=incident,
                agent_type=agent_type,
                status='completed',
                input_data=input_data,
                output_data=output_data,
                duration_ms=duration_ms,
                started_at=now,
                completed_at=now + timedelta(seconds=completed_offset_s),
            )

        # Rerouting recommendation
        to_rail, est_rate, rationale = tpl['rerouting']
        ReroutingRecommendation.objects.create(
            incident=incident,
            from_rail=rail,
            to_rail=to_rail,
            confidence=round(random.uniform(85, 95), 1),
            estimated_success_rate=est_rate,
            rationale=rationale,
            created_at=now,
        )

        # Communication drafts (with the same Unknown→Under Investigation fallback,
        # and proper acronym handling — 'NPCI-Side' not 'Npci Side')
        CLASSIFICATION_LABELS = {
            'NPCI_SIDE': ('NPCI-Side', 'NPCI-side'),
            'BANK_SIDE': ('Bank-Side', 'bank-side'),
            'FALSE_POSITIVE': ('False Positive', 'a false positive'),
            'UNKNOWN': ('Under Investigation', 'still under investigation'),
        }
        cls = tpl['classification']
        conf = tpl['confidence']
        if cls == 'UNKNOWN' or conf < 60:
            classification_label, classification_phrase = CLASSIFICATION_LABELS['UNKNOWN']
        else:
            classification_label, classification_phrase = CLASSIFICATION_LABELS.get(
                cls, (cls.replace('_', '-').title(), cls.replace('_', '-').lower())
            )

        CommunicationDraft.objects.create(
            incident=incident,
            audience='client_services',
            subject_line=f'{rail} Alert — {classification_label} — Internal Briefing',
            draft_text=(
                f'Our AI monitoring has classified this {rail} incident as {classification_phrase} '
                f'with {conf}% confidence. {tpl["reasoning"][:200]}... Rerouting to {to_rail} where '
                f'applicable. Updates every 30 minutes.'
            ),
            status='draft',
            created_at=now,
        )
        CommunicationDraft.objects.create(
            incident=incident,
            audience='corporate_client',
            subject_line=f'Payment Processing Update — {rail} Service Advisory',
            draft_text=(
                f'Dear Valued Client, we are monitoring a temporary disruption affecting {rail} payment '
                f'processing. Our teams are actively working on resolution. Alternative payment channels '
                f'are available. We will provide updates every 30 minutes. Please contact your '
                f'relationship manager for urgent requirements.'
            ),
            status='draft',
            created_at=now,
        )

        # Best-effort: kick off the real async classifier as a parallel demonstration
        # of the production flow. The UI doesn't depend on this — it has the synced
        # incident already. Failure here is silently logged.
        try:
            from agents.incident_classifier import run as classify
            classify.delay({
                'snapshot_id': str(snapshot.id),
                'rail_name': rail,
                'success_rate': success_rate,
                'latency_ms': 1850,
                'error_rate': round(100 - success_rate, 2),
            })
        except Exception:
            pass  # Celery unavailable — synced incident is still committed

        return Response({
            'status': 'incident_triggered',
            'incident_id': str(incident.id),
            'rail': rail,
            'severity': tpl['severity'],
            'classification': cls,
            'success_rate': success_rate,
            'note': 'Incident committed synchronously. Async classifier may also fire.',
        })
