import json
import logging
from datetime import datetime, timezone
from django.conf import settings
from config.celery import app
from adapters.mock_adapter import MockDataAdapter

logger = logging.getLogger(__name__)
adapter = MockDataAdapter()

PROMPT_TEMPLATE = """You are an expert India payment systems analyst at Citi, specialising in NPCI infrastructure.

CURRENT INCIDENT DATA:
Rail: {rail_name}
Success Rate: {success_rate}%
Latency: {latency_ms}ms
Error Rate: {error_rate}%
Detected At: {detected_at}

HISTORICAL INCIDENT PATTERNS FOR REFERENCE:
{historical_context}

CLASSIFICATION TASK:
Based on the incident data and historical patterns, classify this incident.

OC-215 CONTEXT: The April 12, 2025 outage was caused by banks flooding NPCI's Check Transaction Status API (NPCI_SIDE). A bank-side failure typically affects only Citi's transactions while other PSPs remain normal.

Respond ONLY with this JSON (no preamble, no markdown):
{{
  "classification": "NPCI_SIDE | BANK_SIDE | FALSE_POSITIVE | UNKNOWN",
  "confidence_score": 0-100,
  "severity": "low | medium | high | critical",
  "title": "brief incident title under 80 chars",
  "reasoning": "2-3 sentences explaining your classification",
  "historical_match": "which historical incident this most resembles or empty string",
  "recommended_immediate_action": "one sentence for ops analyst"
}}"""


@app.task(name='agents.incident_classifier.run', bind=True, max_retries=2)
def run(self, anomaly_data: dict):
    """
    Incident Classifier Agent.
    Uses Claude API with RAG-style historical context injection.
    Classifies root cause: NPCI_SIDE vs BANK_SIDE vs FALSE_POSITIVE.
    On completion, fires Rerouting Advisor and Compliance Watchdog in parallel.
    """
    from apps.rails.models import RailHealthSnapshot
    from apps.incidents.models import Incident, AgentRun

    started_at = datetime.now(timezone.utc)
    agent_run = None

    try:
        # Fetch historical incidents for context (RAG)
        historical = adapter.get_historical_incidents(limit=5)
        historical_context = _format_historical_context(historical)

        prompt = PROMPT_TEMPLATE.format(
            rail_name=anomaly_data['rail_name'],
            success_rate=anomaly_data['success_rate'],
            latency_ms=anomaly_data['latency_ms'],
            error_rate=anomaly_data['error_rate'],
            detected_at=datetime.now(timezone.utc).strftime('%Y-%m-%d %H:%M IST'),
            historical_context=historical_context,
        )

        # Call Claude API
        result = _call_claude(prompt)

        # Create incident record
        snapshot = RailHealthSnapshot.objects.get(id=anomaly_data['snapshot_id'])
        incident = Incident.objects.create(
            rail=snapshot,
            rail_name=anomaly_data['rail_name'],
            classification=result['classification'],
            confidence_score=result['confidence_score'],
            severity=result['severity'],
            title=result['title'],
            classifier_reasoning=result['reasoning'],
            historical_match=result.get('historical_match', ''),
            status='active',
        )

        duration = int((datetime.now(timezone.utc) - started_at).total_seconds() * 1000)

        AgentRun.objects.create(
            incident=incident,
            agent_type='incident_classifier',
            status='completed',
            input_data=anomaly_data,
            output_data=result,
            duration_ms=duration,
            completed_at=datetime.now(timezone.utc),
        )

        # Broadcast new incident via WebSocket
        _broadcast_new_incident(incident, result)

        # Fork: fire Rerouting Advisor and Compliance Watchdog in parallel
        from agents.rerouting_advisor import run as advise
        from agents.compliance_watchdog import run as watchdog
        from agents.comms_generator import run as generate_comms

        incident_id = str(incident.id)
        advise.delay(incident_id, anomaly_data)
        watchdog.delay(incident_id)

        # Comms generator waits for advisor — chain via generate_comms after short delay
        # In production: use Celery chord for proper join pattern
        generate_comms.apply_async(
            args=[incident_id],
            countdown=15  # give advisor 15s to complete
        )

        logger.info(f"Incident {incident_id} classified: {result['classification']} ({result['confidence_score']}%)")

        return {
            'incident_id': incident_id,
            'classification': result['classification'],
            'confidence_score': result['confidence_score'],
        }

    except Exception as exc:
        logger.error(f"Incident Classifier failed: {exc}")
        raise self.retry(exc=exc, countdown=5)


def _format_historical_context(incidents: list) -> str:
    lines = []
    for i, inc in enumerate(incidents, 1):
        lines.append(
            f"{i}. {inc['date']} — {inc['rail']} — {inc['classification']} "
            f"(success rate at detection: {inc['success_rate_at_detection']}%)\n"
            f"   Signature: {inc['signature']}\n"
            f"   Root cause: {inc['root_cause']}"
        )
    return '\n\n'.join(lines)


def _call_claude(prompt: str) -> dict:
    """Call Claude API. Returns structured classification dict."""
    try:
        import anthropic
        client = anthropic.Anthropic(api_key=settings.ANTHROPIC_API_KEY)
        message = client.messages.create(
            model='claude-sonnet-4-6',
            max_tokens=1000,
            messages=[{'role': 'user', 'content': prompt}]
        )
        response_text = message.content[0].text.strip()
        # Strip markdown fences if present
        if response_text.startswith('```'):
            response_text = response_text.split('```')[1]
            if response_text.startswith('json'):
                response_text = response_text[4:]
        return json.loads(response_text)
    except Exception as e:
        logger.error(f"Claude API call failed: {e}")
        # Fallback classification
        return {
            'classification': 'UNKNOWN',
            'confidence_score': 0,
            'severity': 'medium',
            'title': 'Payment rail degradation — classification failed',
            'reasoning': f'AI classification unavailable: {str(e)}',
            'historical_match': '',
            'recommended_immediate_action': 'Manual investigation required.',
        }


def _broadcast_new_incident(incident, result: dict):
    try:
        from asgiref.sync import async_to_sync
        from channels.layers import get_channel_layer
        channel_layer = get_channel_layer()
        async_to_sync(channel_layer.group_send)('rail_updates', {
            'type': 'incident.new',
            'data': {
                'incident_id': str(incident.id),
                'rail_name': incident.rail_name,
                'classification': incident.classification,
                'confidence_score': float(incident.confidence_score),
                'severity': incident.severity,
                'title': incident.title,
                'reasoning': result.get('reasoning', ''),
                'recommended_action': result.get('recommended_immediate_action', ''),
                'detected_at': incident.detected_at.isoformat(),
            }
        })
    except Exception as e:
        logger.warning(f"WebSocket broadcast failed: {e}")
