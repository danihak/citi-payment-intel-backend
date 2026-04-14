import logging
from datetime import datetime, timezone
from config.celery import app
from adapters.mock_adapter import MockDataAdapter

logger = logging.getLogger(__name__)
adapter = MockDataAdapter()

RAIL_ALTERNATIVES = {
    'UPI':  ['IMPS', 'NEFT'],
    'IMPS': ['UPI', 'NEFT'],
    'RTGS': ['NEFT'],
    'NEFT': ['IMPS', 'UPI'],
    'NACH': ['NEFT'],
}


@app.task(name='agents.rerouting_advisor.run', bind=True, max_retries=2)
def run(self, incident_id: str, anomaly_data: dict):
    """
    Rerouting Advisor Agent.
    Runs in parallel with Compliance Watchdog after Incident Classifier fires.
    Evaluates alternative rails and recommends the best rerouting option.
    """
    from apps.incidents.models import Incident, AgentRun, ReroutingRecommendation

    started_at = datetime.now(timezone.utc)

    try:
        incident = Incident.objects.get(id=incident_id)
        affected_rail = incident.rail_name
        alternatives = RAIL_ALTERNATIVES.get(affected_rail, [])

        best_recommendation = None
        best_success_rate = 0.0

        for alt_rail in alternatives:
            health = adapter.get_rail_health(alt_rail)
            if health.success_rate > best_success_rate:
                best_success_rate = float(health.success_rate)
                best_recommendation = {
                    'rail': alt_rail,
                    'success_rate': float(health.success_rate),
                    'latency_ms': health.latency_ms,
                    'rationale': _build_rationale(affected_rail, alt_rail, health),
                }

        if best_recommendation and best_success_rate >= 92.0:
            reco = ReroutingRecommendation.objects.create(
                incident=incident,
                from_rail=affected_rail,
                to_rail=best_recommendation['rail'],
                confidence=min(best_success_rate, 98.0),
                rationale=best_recommendation['rationale'],
                estimated_success_rate=best_success_rate,
            )
            output = {
                'recommendation': best_recommendation,
                'rerouting_id': str(reco.id),
                'viable': True,
            }
        else:
            output = {
                'recommendation': None,
                'viable': False,
                'reason': 'No alternative rail with sufficient health available.',
            }

        duration = int((datetime.now(timezone.utc) - started_at).total_seconds() * 1000)

        AgentRun.objects.create(
            incident=incident,
            agent_type='rerouting_advisor',
            status='completed',
            input_data=anomaly_data,
            output_data=output,
            duration_ms=duration,
            completed_at=datetime.now(timezone.utc),
        )

        _broadcast_rerouting(incident_id, output)
        logger.info(f"Rerouting Advisor completed for incident {incident_id}: viable={output['viable']}")
        return output

    except Exception as exc:
        logger.error(f"Rerouting Advisor failed: {exc}")
        raise self.retry(exc=exc, countdown=5)


def _build_rationale(from_rail: str, to_rail: str, health) -> str:
    return (
        f"{to_rail} is currently operating at {health.success_rate}% success rate "
        f"with {health.latency_ms}ms average latency. "
        f"Recommended as primary alternative to {from_rail} for corporate collection flows "
        f"and dealer payment settlements during this degradation window."
    )


def _broadcast_rerouting(incident_id: str, output: dict):
    try:
        from asgiref.sync import async_to_sync
        from channels.layers import get_channel_layer
        channel_layer = get_channel_layer()
        async_to_sync(channel_layer.group_send)('rail_updates', {
            'type': 'rerouting.update',
            'data': {'incident_id': incident_id, **output},
        })
    except Exception as e:
        logger.warning(f"WebSocket broadcast failed: {e}")
