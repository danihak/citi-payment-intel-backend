import json
import logging
from datetime import datetime, timezone
from django.conf import settings
from config.celery import app

logger = logging.getLogger(__name__)

COMMS_PROMPT = """You are a senior communications specialist at Citi India, writing for the institutional banking division.

INCIDENT CONTEXT:
Rail Affected: {rail_name}
Classification: {classification}
Confidence: {confidence_score}%
Severity: {severity}
Incident Title: {title}
Classifier Reasoning: {reasoning}
Rerouting Available: {rerouting_info}
OC-215 Status: {compliance_status}
Time Detected: {detected_at}

Write TWO communication drafts. Both must be:
- Factually accurate (do not state certainty where classification is not 100%)
- Appropriately cautious (banking-grade language)
- Free of internal system names or technical jargon
- Compliant with RBI communication guidelines

Respond ONLY with this JSON (no markdown, no preamble):
{{
  "client_services_draft": {{
    "subject": "subject line for internal Slack/email",
    "body": "internal message for Client Services team, 3-4 sentences, tells them what to say to corporate clients right now"
  }},
  "corporate_client_draft": {{
    "subject": "subject line for corporate client email",
    "body": "external email to corporate treasury clients, formal banking tone, 4-5 sentences, acknowledges issue without over-committing on resolution time"
  }}
}}"""


@app.task(name='agents.comms_generator.run', bind=True, max_retries=2)
def run(self, incident_id: str):
    """
    Communication Generator Agent.
    Joins outputs from Rerouting Advisor and Compliance Watchdog.
    Uses Claude API to generate banking-grade communication drafts.
    Stores drafts for human approval before any client communication goes out.
    Human-in-the-loop: drafts require approval via POST /api/v1/communications/{id}/approve/
    """
    from apps.incidents.models import Incident, AgentRun, ReroutingRecommendation
    from apps.communications.models import CommunicationDraft

    started_at = datetime.now(timezone.utc)

    try:
        incident = Incident.objects.get(id=incident_id)

        # Gather context from parallel agents
        rerouting = ReroutingRecommendation.objects.filter(incident=incident).first()
        rerouting_info = (
            f"Yes — {rerouting.from_rail} → {rerouting.to_rail} "
            f"({rerouting.estimated_success_rate}% estimated success rate)"
            if rerouting else "No viable alternative rail available."
        )

        from apps.compliance.models import ApiComplianceMetric
        latest_compliance = ApiComplianceMetric.objects.filter(
            is_compliant=True
        ).count()
        total_metrics = ApiComplianceMetric.objects.count()
        compliance_status = (
            "All monitored APIs within OC-215 limits."
            if total_metrics > 0 and latest_compliance == total_metrics
            else "One or more API metrics near/over OC-215 threshold — review required."
        )

        prompt = COMMS_PROMPT.format(
            rail_name=incident.rail_name,
            classification=incident.get_classification_display(),
            confidence_score=float(incident.confidence_score),
            severity=incident.severity,
            title=incident.title,
            reasoning=incident.classifier_reasoning,
            rerouting_info=rerouting_info,
            compliance_status=compliance_status,
            detected_at=incident.detected_at.strftime('%d %b %Y, %H:%M IST'),
        )

        result = _call_claude(prompt)

        # Save both drafts — status='draft', requires human approval
        cs_draft = CommunicationDraft.objects.create(
            incident=incident,
            audience='client_services',
            subject_line=result['client_services_draft']['subject'],
            draft_text=result['client_services_draft']['body'],
            tone_notes='Internal briefing. Not for external distribution.',
            status='draft',
        )

        corp_draft = CommunicationDraft.objects.create(
            incident=incident,
            audience='corporate_client',
            subject_line=result['corporate_client_draft']['subject'],
            draft_text=result['corporate_client_draft']['body'],
            tone_notes='External communication. Requires approval before sending.',
            status='draft',
        )

        duration = int((datetime.now(timezone.utc) - started_at).total_seconds() * 1000)

        output = {
            'drafts_created': 2,
            'client_services_draft_id': str(cs_draft.id),
            'corporate_client_draft_id': str(corp_draft.id),
            'status': 'awaiting_approval',
        }

        AgentRun.objects.create(
            incident=incident,
            agent_type='comms_generator',
            status='completed',
            input_data={'incident_id': incident_id},
            output_data=output,
            duration_ms=duration,
            completed_at=datetime.now(timezone.utc),
        )

        _broadcast_comms_ready(incident_id, output, result)
        logger.info(f"Communication drafts created for incident {incident_id} — awaiting approval")
        return output

    except Exception as exc:
        logger.error(f"Communication Generator failed: {exc}")
        raise self.retry(exc=exc, countdown=10)


def _call_claude(prompt: str) -> dict:
    try:
        import anthropic
        client = anthropic.Anthropic(api_key=settings.ANTHROPIC_API_KEY)
        message = client.messages.create(
            model='claude-sonnet-4-6',
            max_tokens=1200,
            messages=[{'role': 'user', 'content': prompt}]
        )
        text = message.content[0].text.strip()
        if text.startswith('```'):
            text = text.split('```')[1]
            if text.startswith('json'):
                text = text[4:]
        return json.loads(text)
    except Exception as e:
        logger.error(f"Claude API call failed: {e}")
        return {
            'client_services_draft': {
                'subject': f'Payment Rail Alert — Manual Review Required',
                'body': (
                    'Our monitoring system has detected a payment rail degradation. '
                    'AI-generated communication is temporarily unavailable. '
                    'Please manually assess the situation and draft client communication. '
                    'Contact the ops team for the latest status.'
                ),
            },
            'corporate_client_draft': {
                'subject': 'Important: Payment Processing Update',
                'body': (
                    'Dear Valued Client, we are currently investigating a technical issue '
                    'affecting payment processing. Our teams are working to resolve this. '
                    'We will provide an update within 30 minutes. '
                    'Please contact your relationship manager for urgent queries.'
                ),
            },
        }


def _broadcast_comms_ready(incident_id: str, output: dict, drafts: dict):
    try:
        from asgiref.sync import async_to_sync
        from channels.layers import get_channel_layer
        channel_layer = get_channel_layer()
        async_to_sync(channel_layer.group_send)('rail_updates', {
            'type': 'comms.ready',
            'data': {
                'incident_id': incident_id,
                'drafts': drafts,
                **output,
            },
        })
    except Exception as e:
        logger.warning(f"WebSocket broadcast failed: {e}")
