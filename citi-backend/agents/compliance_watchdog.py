import logging
from datetime import datetime, timezone
from config.celery import app
from adapters.mock_adapter import MockDataAdapter

logger = logging.getLogger(__name__)
adapter = MockDataAdapter()

# OC-215 limits (NPCI circular, post April 12 2025)
OC215_LIMITS = {
    'check_transaction_status': 3.0,
    'initiate_payment': 10.0,
    'balance_enquiry': 5.0,
    'validate_vpa': 8.0,
}

WARNING_THRESHOLD = 0.85  # warn at 85% of limit


@app.task(name='agents.compliance_watchdog.run', bind=True, max_retries=2)
def run(self, incident_id: str = None):
    """
    Compliance Watchdog Agent.
    Runs independently every 60s via Celery Beat AND
    in parallel with Rerouting Advisor after incident detection.

    Monitors Citi's own outgoing API call rates to NPCI.
    OC-215: Check Transaction Status max 3 TPS, 90s gap per transaction.
    Logs violations to ComplianceViolation audit table.
    """
    from apps.incidents.models import Incident, AgentRun
    from apps.compliance.models import ApiComplianceMetric, ComplianceViolation

    started_at = datetime.now(timezone.utc)
    violations_found = []
    metrics_saved = []

    try:
        compliance_data = adapter.get_compliance_metrics()

        for data in compliance_data:
            limit = OC215_LIMITS.get(data.api_name, data.tps_limit)
            is_compliant = data.tps_current <= limit
            is_warning = data.tps_current >= (limit * WARNING_THRESHOLD)

            metric = ApiComplianceMetric.objects.create(
                api_name=data.api_name,
                tps_current=data.tps_current,
                tps_limit=limit,
                calls_last_minute=data.calls_last_minute,
                calls_last_hour=data.calls_last_hour,
                violation_count=0 if is_compliant else 1,
                is_compliant=is_compliant,
            )
            metrics_saved.append(str(metric.id))

            if not is_compliant:
                violation = ComplianceViolation.objects.create(
                    metric=metric,
                    api_name=data.api_name,
                    tps_observed=data.tps_current,
                    tps_limit=limit,
                    severity='critical',
                    description=(
                        f"OC-215 VIOLATION: {data.api_name} at {data.tps_current} TPS "
                        f"exceeds limit of {limit} TPS. "
                        f"Immediate rate limiting required. "
                        f"This was the root cause of the April 12 NPCI outage."
                    ),
                )
                violations_found.append({
                    'api_name': data.api_name,
                    'tps_current': float(data.tps_current),
                    'tps_limit': float(limit),
                    'severity': 'critical',
                })
                logger.critical(
                    f"OC-215 VIOLATION: {data.api_name} at {data.tps_current} TPS (limit: {limit})"
                )

            elif is_warning:
                violation = ComplianceViolation.objects.create(
                    metric=metric,
                    api_name=data.api_name,
                    tps_observed=data.tps_current,
                    tps_limit=limit,
                    severity='warning',
                    description=(
                        f"OC-215 WARNING: {data.api_name} at {data.tps_current} TPS "
                        f"approaching limit of {limit} TPS ({round(data.tps_current/limit*100)}% utilised)."
                    ),
                )
                violations_found.append({
                    'api_name': data.api_name,
                    'tps_current': float(data.tps_current),
                    'tps_limit': float(limit),
                    'severity': 'warning',
                })

        duration = int((datetime.now(timezone.utc) - started_at).total_seconds() * 1000)

        # Log agent run (link to incident if called from classifier fork)
        incident = None
        if incident_id:
            try:
                incident = Incident.objects.get(id=incident_id)
            except Incident.DoesNotExist:
                pass

        output = {
            'metrics_checked': len(compliance_data),
            'violations': violations_found,
            'all_compliant': len(violations_found) == 0,
        }

        AgentRun.objects.create(
            incident=incident,
            agent_type='compliance_watchdog',
            status='completed',
            input_data={'incident_id': incident_id},
            output_data=output,
            duration_ms=duration,
            completed_at=datetime.now(timezone.utc),
        )

        _broadcast_compliance(output)
        return output

    except Exception as exc:
        logger.error(f"Compliance Watchdog failed: {exc}")
        raise self.retry(exc=exc, countdown=10)


def _broadcast_compliance(output: dict):
    try:
        from asgiref.sync import async_to_sync
        from channels.layers import get_channel_layer
        channel_layer = get_channel_layer()
        async_to_sync(channel_layer.group_send)('rail_updates', {
            'type': 'compliance.update',
            'data': output,
        })
    except Exception as e:
        logger.warning(f"WebSocket broadcast failed: {e}")
