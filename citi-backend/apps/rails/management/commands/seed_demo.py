from django.core.management.base import BaseCommand
from django.utils import timezone
from datetime import timedelta
import random

from apps.rails.models import RailHealthSnapshot
from apps.incidents.models import Incident, AgentRun, ReroutingRecommendation
from apps.compliance.models import ApiComplianceMetric, ComplianceViolation
from apps.communications.models import CommunicationDraft


class Command(BaseCommand):
    help = 'Seed the database with realistic demo data for Citi presentation'

    def handle(self, *args, **options):
        self.stdout.write('Seeding demo data...')

        # Clear existing
        RailHealthSnapshot.objects.all().delete()
        Incident.objects.all().delete()
        ApiComplianceMetric.objects.all().delete()

        # --- 1. Rail health history (last 2 hours, every 30s) ---
        rails = ['UPI', 'IMPS', 'RTGS', 'NEFT', 'NACH']
        baselines = {
            'UPI': 99.4, 'IMPS': 98.9,
            'RTGS': 99.8, 'NEFT': 99.6, 'NACH': 99.1,
        }
        now = timezone.now()

        for rail in rails:
            baseline = baselines[rail]
            for i in range(240):  # 240 × 30s = 2 hours
                ts = now - timedelta(seconds=30 * (240 - i))
                # Simulate April 12-style incident at 90min ago for UPI
                if rail == 'UPI' and 60 <= i <= 100:
                    rate = round(random.uniform(68, 82), 2)
                    status = 'down' if rate < 75 else 'degraded'
                else:
                    rate = round(baseline + random.uniform(-0.8, 0.4), 2)
                    status = 'healthy'

                RailHealthSnapshot.objects.create(
                    rail_name=rail,
                    success_rate=rate,
                    latency_ms=random.randint(250, 450) if status == 'healthy' else random.randint(900, 2200),
                    transactions_per_min=random.randint(12000, 16000) if rail == 'UPI' else random.randint(3000, 5000),
                    status=status,
                    error_rate=round(100 - rate, 2),
                    raw_data={'source': 'demo_seed', 'index': i},
                )

        self.stdout.write(f'  Created {RailHealthSnapshot.objects.count()} rail snapshots')

        # --- 2. The April 12-style incident (resolved) ---
        upi_snap = RailHealthSnapshot.objects.filter(
            rail_name='UPI', status='down'
        ).order_by('snapshot_at').first()

        inc1 = Incident.objects.create(
            rail=upi_snap,
            rail_name='UPI',
            classification='NPCI_SIDE',
            confidence_score=91,
            severity='critical',
            status='resolved',
            title='UPI degradation — NPCI infrastructure issue detected',
            classifier_reasoning=(
                'Rapid success rate drop from 99.4% to 71.3% within 8 minutes. '
                'Latency spike to 2100ms (7x baseline). Pattern matches April 12 2025 incident signature. '
                'All PSP banks affected simultaneously — confirms NPCI-side root cause, not bank-specific.'
            ),
            historical_match='April 12, 2025 — UPI — NPCI_SIDE (5-hour outage)',
            detected_at=now - timedelta(minutes=90),
            resolved_at=now - timedelta(minutes=45),
        )

        ReroutingRecommendation.objects.create(
            incident=inc1,
            from_rail='UPI',
            to_rail='IMPS',
            confidence=94.5,
            rationale=(
                'IMPS currently operating at 98.9% success rate with 395ms average latency. '
                'Recommended as primary alternative for corporate collection flows '
                'and dealer payment settlements during UPI degradation window.'
            ),
            estimated_success_rate=98.9,
        )

        CommunicationDraft.objects.create(
            incident=inc1,
            audience='client_services',
            subject_line='UPI Degradation Alert — Briefing for Client-Facing Teams',
            draft_text=(
                'Our monitoring systems have detected degradation in UPI payment rails, '
                'classified as an NPCI infrastructure issue with 91% confidence. '
                'If clients report UPI payment failures, advise them this is a platform-wide issue '
                'affecting all banks — not specific to Citi. '
                'IMPS is available as an alternative rail for urgent transactions. '
                'We will provide an update every 30 minutes until resolution.'
            ),
            status='approved',
            approved_by='ops_lead',
        )

        CommunicationDraft.objects.create(
            incident=inc1,
            audience='corporate_client',
            subject_line='Payment Processing Update — UPI Service Disruption',
            draft_text=(
                'Dear Valued Client, we are writing to inform you of a temporary disruption '
                'affecting UPI payment processing across the India payments network. '
                'This is a platform-level issue currently being addressed by NPCI. '
                'Your transactions remain secure, and IMPS is available as an alternative. '
                'We anticipate resolution within the next 60 minutes and will keep you updated. '
                'Please contact your relationship manager for any urgent requirements.'
            ),
            status='approved',
            approved_by='client_services_head',
        )

        # --- 3. Active incident (ongoing, for live demo) ---
        upi_snap2 = RailHealthSnapshot.objects.create(
            rail_name='UPI', success_rate=88.4, latency_ms=920,
            transactions_per_min=9200, status='degraded', error_rate=11.6,
            raw_data={'source': 'demo_seed', 'note': 'active incident trigger'},
        )
        inc2 = Incident.objects.create(
            rail=upi_snap2,
            rail_name='UPI',
            classification='UNKNOWN',
            confidence_score=45,
            severity='high',
            status='investigating',
            title='UPI success rate below threshold — under investigation',
            classifier_reasoning='Pattern does not match known historical signatures. Manual review recommended.',
            detected_at=now - timedelta(minutes=3),
        )

        AgentRun.objects.create(
            incident=inc2,
            agent_type='rail_monitor',
            status='completed',
            input_data={'rail_name': 'UPI', 'success_rate': 88.4},
            output_data={'anomaly_detected': True},
            duration_ms=120,
            completed_at=now - timedelta(minutes=3),
        )
        AgentRun.objects.create(
            incident=inc2,
            agent_type='incident_classifier',
            status='completed',
            input_data={'rail_name': 'UPI'},
            output_data={'classification': 'UNKNOWN', 'confidence': 45},
            duration_ms=3400,
            completed_at=now - timedelta(minutes=2, seconds=55),
        )

        # --- 4. Compliance metrics ---
        apis = [
            ('check_transaction_status', 3.0, 1.42),
            ('initiate_payment', 10.0, 6.8),
            ('balance_enquiry', 5.0, 2.1),
            ('validate_vpa', 8.0, 3.3),
        ]
        for api_name, limit, current in apis:
            ApiComplianceMetric.objects.create(
                api_name=api_name,
                tps_current=current,
                tps_limit=limit,
                calls_last_minute=int(current * 60),
                calls_last_hour=int(current * 3580),
                is_compliant=True,
            )

        self.stdout.write(f'  Created {Incident.objects.count()} incidents')
        self.stdout.write(f'  Created {CommunicationDraft.objects.count()} communication drafts')
        self.stdout.write(f'  Created {ApiComplianceMetric.objects.count()} compliance metrics')
        self.stdout.write(self.style.SUCCESS('Demo data seeded successfully.'))
        self.stdout.write('Run: python manage.py runserver')
