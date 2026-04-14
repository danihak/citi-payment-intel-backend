from django.core.management.base import BaseCommand
from django.utils import timezone
from datetime import timedelta
import random

from apps.rails.models import RailHealthSnapshot
from apps.incidents.models import Incident, AgentRun, ReroutingRecommendation
from apps.compliance.models import ApiComplianceMetric, ComplianceViolation
from apps.communications.models import CommunicationDraft


class Command(BaseCommand):
    help = 'Seed rich demo data for Citi presentation'

    def handle(self, *args, **options):
        self.stdout.write('Seeding demo data...')

        RailHealthSnapshot.objects.all().delete()
        Incident.objects.all().delete()
        ApiComplianceMetric.objects.all().delete()

        now = timezone.now()
        rails = ['UPI', 'IMPS', 'RTGS', 'NEFT', 'NACH']
        baselines = {'UPI': 99.4, 'IMPS': 98.9, 'RTGS': 99.8, 'NEFT': 99.6, 'NACH': 99.1}

        # Rail health history — 4 hours of data
        for rail in rails:
            baseline = baselines[rail]
            for i in range(480):
                ts = now - timedelta(seconds=30 * (480 - i))
                if rail == 'UPI' and 180 <= i <= 240:
                    rate = round(random.uniform(68, 78), 2)
                    status = 'down'
                elif rail == 'UPI' and 240 <= i <= 270:
                    rate = round(random.uniform(82, 91), 2)
                    status = 'degraded'
                elif rail == 'IMPS' and 300 <= i <= 330:
                    rate = round(random.uniform(88, 93), 2)
                    status = 'degraded'
                else:
                    rate = round(baseline + random.uniform(-0.6, 0.3), 2)
                    status = 'healthy'
                RailHealthSnapshot.objects.create(
                    rail_name=rail, success_rate=rate,
                    latency_ms=random.randint(250, 450) if status == 'healthy' else random.randint(800, 2400),
                    transactions_per_min=random.randint(12000, 16000) if rail == 'UPI' else random.randint(2000, 5000),
                    status=status, error_rate=round(100 - rate, 2),
                    raw_data={'source': 'demo_seed', 'index': i},
                )

        self.stdout.write(f'  Created {RailHealthSnapshot.objects.count()} rail snapshots')

        # --- INCIDENT 1: April 12-style — resolved ---
        snap1 = RailHealthSnapshot.objects.filter(rail_name='UPI', status='down').order_by('snapshot_at').first()
        inc1 = Incident.objects.create(
            rail=snap1, rail_name='UPI',
            classification='NPCI_SIDE', confidence_score=91,
            severity='critical', status='resolved',
            title='UPI degradation — NPCI infrastructure overload detected',
            classifier_reasoning=(
                'Rapid success rate drop from 99.4% to 71.3% within 8 minutes. '
                'Latency spike to 2,100ms (7.4x baseline). Pattern matches April 12 2025 incident signature exactly. '
                'All PSP banks affected simultaneously — confirms NPCI-side root cause. '
                'Check Transaction Status API flood pattern detected in OC-215 watchdog.'
            ),
            historical_match='April 12, 2025 — UPI — NPCI_SIDE (5-hour outage, ₹2,400 Cr impacted)',
            detected_at=now - timedelta(hours=3),
            resolved_at=now - timedelta(hours=1, minutes=45),
        )
        ReroutingRecommendation.objects.create(
            incident=inc1, from_rail='UPI', to_rail='IMPS',
            confidence=94.5, estimated_success_rate=98.9,
            rationale='IMPS operating at 98.9% success rate with 395ms average latency. Recommended as primary alternative for corporate collection flows, dealer payment settlements, and high-value institutional transfers during UPI degradation window.',
        )
        AgentRun.objects.create(incident=inc1, agent_type='rail_monitor', status='completed', input_data={'rail': 'UPI'}, output_data={'anomaly': True, 'success_rate': 71.3}, duration_ms=89, completed_at=now - timedelta(hours=3))
        AgentRun.objects.create(incident=inc1, agent_type='incident_classifier', status='completed', input_data={'rail': 'UPI', 'rate': 71.3}, output_data={'classification': 'NPCI_SIDE', 'confidence': 91}, duration_ms=3240, completed_at=now - timedelta(hours=2, minutes=57))
        AgentRun.objects.create(incident=inc1, agent_type='rerouting_advisor', status='completed', input_data={'from': 'UPI'}, output_data={'to': 'IMPS', 'confidence': 94.5}, duration_ms=1820, completed_at=now - timedelta(hours=2, minutes=55))
        AgentRun.objects.create(incident=inc1, agent_type='compliance_watchdog', status='completed', input_data={}, output_data={'violations': 1}, duration_ms=420, completed_at=now - timedelta(hours=2, minutes=54))
        AgentRun.objects.create(incident=inc1, agent_type='comms_generator', status='completed', input_data={}, output_data={'drafts': 2}, duration_ms=4100, completed_at=now - timedelta(hours=2, minutes=50))
        CommunicationDraft.objects.create(
            incident=inc1, audience='client_services',
            subject_line='UPI Degradation Alert — Briefing for Client-Facing Teams',
            draft_text='Our monitoring system has detected a degradation in UPI payment rails, classified as an NPCI infrastructure issue with 91% confidence. If clients report UPI payment failures, advise them this is a platform-wide issue affecting all PSP banks — not specific to Citi. IMPS is available as a high-confidence alternative (98.9% success rate). We will provide status updates every 30 minutes until full resolution.',
            status='approved', approved_by='ops_lead',
            approved_at=now - timedelta(hours=2, minutes=45),
        )
        CommunicationDraft.objects.create(
            incident=inc1, audience='corporate_client',
            subject_line='Important: UPI Payment Processing Disruption — Action Required',
            draft_text='Dear Valued Client, we are writing to inform you of a temporary disruption affecting UPI payment processing across the India payments network. This is a platform-level issue currently being addressed by NPCI and is not specific to Citi. Your transactions remain secure. IMPS is available as an alternative channel for urgent payment requirements. We anticipate full resolution within 60 minutes and will provide a follow-up communication. Please contact your dedicated relationship manager for any time-sensitive requirements.',
            status='approved', approved_by='client_services_head',
            approved_at=now - timedelta(hours=2, minutes=40),
        )

        # --- INCIDENT 2: IMPS degradation — resolved ---
        snap2 = RailHealthSnapshot.objects.filter(rail_name='IMPS', status='degraded').order_by('snapshot_at').first()
        inc2 = Incident.objects.create(
            rail=snap2, rail_name='IMPS',
            classification='BANK_SIDE', confidence_score=78,
            severity='high', status='resolved',
            title='IMPS success rate below threshold — Citi switch failover detected',
            classifier_reasoning=(
                'Gradual success rate decline from 98.9% to 89.2% over 15 minutes. '
                'Latency increased to 1,240ms. Critically, Citi-specific transactions are affected '
                'while other PSP banks show normal IMPS performance — strongly indicates bank-side issue. '
                'Pattern consistent with internal switch failover event.'
            ),
            historical_match='March 26, 2025 — UPI — BANK_SIDE (1.5-hour, internal switch failover)',
            detected_at=now - timedelta(hours=1, minutes=30),
            resolved_at=now - timedelta(minutes=45),
        )
        ReroutingRecommendation.objects.create(
            incident=inc2, from_rail='IMPS', to_rail='NEFT',
            confidence=82.0, estimated_success_rate=99.6,
            rationale='NEFT operating at 99.6% with 372ms latency. Suitable for non-urgent transfers during IMPS maintenance window. Note: NEFT settlement is batch-based — advise clients on timing implications.',
        )
        AgentRun.objects.create(incident=inc2, agent_type='rail_monitor', status='completed', input_data={'rail': 'IMPS'}, output_data={'anomaly': True}, duration_ms=92, completed_at=now - timedelta(hours=1, minutes=30))
        AgentRun.objects.create(incident=inc2, agent_type='incident_classifier', status='completed', input_data={}, output_data={'classification': 'BANK_SIDE', 'confidence': 78}, duration_ms=2890, completed_at=now - timedelta(hours=1, minutes=27))
        AgentRun.objects.create(incident=inc2, agent_type='rerouting_advisor', status='completed', input_data={}, output_data={'to': 'NEFT'}, duration_ms=1540, completed_at=now - timedelta(hours=1, minutes=25))
        CommunicationDraft.objects.create(
            incident=inc2, audience='client_services',
            subject_line='IMPS Degradation — Internal Issue, NEFT Available',
            draft_text='Our AI monitoring has classified this as a bank-side issue (78% confidence) — not NPCI infrastructure. NEFT is available as alternative. Internal teams have been notified. Estimated resolution: 30-45 minutes. Do not escalate to NPCI at this stage.',
            status='approved', approved_by='ops_lead',
            approved_at=now - timedelta(hours=1, minutes=20),
        )

        # --- INCIDENT 3: False positive — auto-resolved ---
        snap3 = RailHealthSnapshot.objects.create(
            rail_name='RTGS', success_rate=96.2, latency_ms=1380,
            transactions_per_min=165, status='degraded', error_rate=3.8,
            raw_data={'source': 'demo_seed'},
        )
        inc3 = Incident.objects.create(
            rail=snap3, rail_name='RTGS',
            classification='FALSE_POSITIVE', confidence_score=88,
            severity='low', status='resolved',
            title='RTGS anomaly detected — classified as false positive',
            classifier_reasoning=(
                'Single data point showing 96.2% success rate triggered threshold alert. '
                'Self-corrected within 2 minutes. NPCI status page showed normal. '
                'Pattern matches known monitoring sensor artifact — not a real degradation event. '
                'No client impact detected. Monitoring bug logged for engineering review.'
            ),
            historical_match='November 22, 2024 — UPI — FALSE_POSITIVE (monitoring sensor artifact)',
            detected_at=now - timedelta(hours=1),
            resolved_at=now - timedelta(minutes=58),
        )
        AgentRun.objects.create(incident=inc3, agent_type='rail_monitor', status='completed', input_data={'rail': 'RTGS'}, output_data={'anomaly': True}, duration_ms=78, completed_at=now - timedelta(hours=1))
        AgentRun.objects.create(incident=inc3, agent_type='incident_classifier', status='completed', input_data={}, output_data={'classification': 'FALSE_POSITIVE', 'confidence': 88}, duration_ms=2100, completed_at=now - timedelta(minutes=57))

        # --- INCIDENT 4: Active investigation ---
        snap4 = RailHealthSnapshot.objects.create(
            rail_name='UPI', success_rate=93.7, latency_ms=680,
            transactions_per_min=11200, status='degraded', error_rate=6.3,
            raw_data={'source': 'demo_seed', 'note': 'active'},
        )
        inc4 = Incident.objects.create(
            rail=snap4, rail_name='UPI',
            classification='UNKNOWN', confidence_score=52,
            severity='medium', status='investigating',
            title='UPI success rate 93.7% — pattern does not match known signatures',
            classifier_reasoning=(
                'Moderate success rate decline to 93.7%. Latency elevated at 680ms (2.4x baseline). '
                'Pattern does not clearly match NPCI-side or bank-side signatures. '
                'Could be intermittent network issue or partial NPCI maintenance. '
                'Rerouting not recommended until classification confidence improves. Manual review suggested.'
            ),
            historical_match='',
            detected_at=now - timedelta(minutes=8),
        )
        AgentRun.objects.create(incident=inc4, agent_type='rail_monitor', status='completed', input_data={'rail': 'UPI'}, output_data={'anomaly': True, 'rate': 93.7}, duration_ms=95, completed_at=now - timedelta(minutes=8))
        AgentRun.objects.create(incident=inc4, agent_type='incident_classifier', status='completed', input_data={}, output_data={'classification': 'UNKNOWN', 'confidence': 52}, duration_ms=3180, completed_at=now - timedelta(minutes=4))
        AgentRun.objects.create(incident=inc4, agent_type='rerouting_advisor', status='completed', input_data={}, output_data={'viable': False, 'reason': 'Low confidence classification'}, duration_ms=1200, completed_at=now - timedelta(minutes=3))
        CommunicationDraft.objects.create(
            incident=inc4, audience='client_services',
            subject_line='UPI Performance Alert — Under Investigation',
            draft_text='Our monitoring has detected UPI performing below normal parameters (93.7% success rate). Root cause classification is ongoing — confidence currently 52%. Advise clients experiencing failures to retry in 5-10 minutes. Do not recommend alternative rails until classification is confirmed. Update to follow within 15 minutes.',
            status='draft',
        )

        self.stdout.write(f'  Created {Incident.objects.count()} incidents with agent runs and comms drafts')

        # --- COMPLIANCE METRICS ---
        apis = [
            ('check_transaction_status', 3.0, 1.42),
            ('initiate_payment', 10.0, 6.83),
            ('balance_enquiry', 5.0, 2.14),
            ('validate_vpa', 8.0, 3.31),
        ]
        for api_name, limit, current in apis:
            metric = ApiComplianceMetric.objects.create(
                api_name=api_name, tps_current=current, tps_limit=limit,
                calls_last_minute=int(current * 60),
                calls_last_hour=int(current * 3580),
                is_compliant=True,
            )

        # Create historical violation during the April 12 style incident
        check_metric = ApiComplianceMetric.objects.get(api_name='check_transaction_status')
        ComplianceViolation.objects.create(
            metric=check_metric, api_name='check_transaction_status',
            tps_observed=3.84, tps_limit=3.0, severity='critical',
            description='OC-215 VIOLATION: Check Transaction Status API at 3.84 TPS exceeded limit of 3.0 TPS during UPI incident response. Automatic rate limiting triggered. This pattern contributed to the April 12 2025 NPCI outage.',
            occurred_at=now - timedelta(hours=2, minutes=55),
        )
        ComplianceViolation.objects.create(
            metric=check_metric, api_name='check_transaction_status',
            tps_observed=2.87, tps_limit=3.0, severity='warning',
            description='OC-215 WARNING: Check Transaction Status API at 2.87 TPS (95.7% of limit). Approaching OC-215 threshold during incident investigation period.',
            occurred_at=now - timedelta(hours=2, minutes=48),
        )
        ComplianceViolation.objects.create(
            metric=check_metric, api_name='check_transaction_status',
            tps_observed=2.71, tps_limit=3.0, severity='warning',
            description='OC-215 WARNING: Check Transaction Status API at 2.71 TPS (90.3% of limit). Elevated query rate observed during active incident monitoring.',
            occurred_at=now - timedelta(hours=1, minutes=25),
        )

        self.stdout.write(f'  Created {ApiComplianceMetric.objects.count()} compliance metrics')
        self.stdout.write(f'  Created {ComplianceViolation.objects.count()} compliance violations')
        self.stdout.write(self.style.SUCCESS('Demo data seeded successfully.'))
