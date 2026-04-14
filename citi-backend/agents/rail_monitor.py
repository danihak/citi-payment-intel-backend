import logging
from datetime import datetime, timezone
from config.celery import app
from adapters.mock_adapter import MockDataAdapter
from apps.rails.models import RailHealthSnapshot

logger = logging.getLogger(__name__)

adapter = MockDataAdapter()

ANOMALY_THRESHOLD = 95.0  # success rate below this triggers classification


@app.task(name='agents.rail_monitor.run', bind=True, max_retries=3)
def run(self):
    """
    Rail Monitor Agent.
    Polls all payment rails every 30 seconds via DataSourceAdapter.
    Persists snapshots to DB.
    Triggers Incident Classifier if anomaly detected.
    """
    try:
        rails_data = adapter.get_all_rails_health()
        anomalies = []

        for rail_data in rails_data:
            snapshot = RailHealthSnapshot.objects.create(
                rail_name=rail_data.rail_name,
                success_rate=rail_data.success_rate,
                latency_ms=rail_data.latency_ms,
                transactions_per_min=rail_data.transactions_per_min,
                status=_derive_status(rail_data.success_rate),
                error_rate=rail_data.error_rate,
                raw_data=rail_data.raw_data,
            )

            if rail_data.success_rate < ANOMALY_THRESHOLD:
                anomalies.append({
                    'snapshot_id': str(snapshot.id),
                    'rail_name': rail_data.rail_name,
                    'success_rate': float(rail_data.success_rate),
                    'latency_ms': rail_data.latency_ms,
                    'error_rate': float(rail_data.error_rate),
                })
                logger.warning(
                    f"ANOMALY: {rail_data.rail_name} at {rail_data.success_rate}% success rate"
                )

        # Push WebSocket update for live dashboard
        _broadcast_rail_update(rails_data)

        # Fire classifier for each anomaly (parallel)
        for anomaly in anomalies:
            from agents.incident_classifier import run as classify
            classify.delay(anomaly)

        return {
            'rails_polled': len(rails_data),
            'anomalies_found': len(anomalies),
            'timestamp': datetime.now(timezone.utc).isoformat(),
        }

    except Exception as exc:
        logger.error(f"Rail Monitor Agent failed: {exc}")
        raise self.retry(exc=exc, countdown=10)


def _derive_status(success_rate: float) -> str:
    if success_rate >= 98.0:
        return 'healthy'
    elif success_rate >= 90.0:
        return 'degraded'
    else:
        return 'down'


def _broadcast_rail_update(rails_data):
    """Push real-time rail health to all connected WebSocket clients."""
    try:
        from asgiref.sync import async_to_sync
        from channels.layers import get_channel_layer

        channel_layer = get_channel_layer()
        payload = {
            'type': 'rail.update',
            'data': [
                {
                    'rail_name': r.rail_name,
                    'success_rate': float(r.success_rate),
                    'latency_ms': r.latency_ms,
                    'status': _derive_status(r.success_rate),
                    'error_rate': float(r.error_rate),
                    'tpm': r.transactions_per_min,
                }
                for r in rails_data
            ],
            'timestamp': datetime.now(timezone.utc).isoformat(),
        }
        async_to_sync(channel_layer.group_send)('rail_updates', payload)
    except Exception as e:
        logger.warning(f"WebSocket broadcast failed (non-critical): {e}")
