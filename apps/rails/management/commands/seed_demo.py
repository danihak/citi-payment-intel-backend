from django.core.management.base import BaseCommand
from django.utils import timezone
from datetime import timedelta
import random

from apps.rails.models import RailHealthSnapshot
from apps.incidents.models import Incident, AgentRun, ReroutingRecommendation
from apps.compliance.models import ApiComplianceMetric, ComplianceViolation
from apps.communications.models import CommunicationDraft


INCIDENTS_DATA = [
    # (rail, classification, confidence, severity, status, hours_ago, resolved_after_mins, title, reasoning, historical_match)
    ('UPI',  'NPCI_SIDE',    91, 'critical',  'resolved',      72, 195, 'UPI degradation — NPCI infrastructure overload (April 12 pattern)', 'Rapid drop 99.4%→71.3% in 8 min. Latency 2,100ms (7.4x baseline). All PSP banks affected simultaneously. Check Transaction Status API flood pattern detected.', 'April 12, 2025 — UPI — NPCI_SIDE (5-hour outage, ₹2,400 Cr impacted)'),
    ('IMPS', 'BANK_SIDE',    78, 'high',      'resolved',      68, 90,  'IMPS degradation — Citi internal switch failover', 'Gradual decline 98.9%→89.2% over 15 min. Only Citi transactions affected — other PSPs normal. Consistent with internal switch failover.', 'March 26, 2025 — BANK_SIDE (switch failover)'),
    ('RTGS', 'FALSE_POSITIVE',88,'low',       'resolved',      65, 2,   'RTGS anomaly — classified as false positive', 'Single data point triggered alert. Self-corrected in 2 min. NPCI status page normal. Monitoring sensor artifact.', 'November 22, 2024 — FALSE_POSITIVE'),
    ('UPI',  'UNKNOWN',      52, 'medium',    'investigating',  0, 0,   'UPI 93.7% — pattern does not match known signatures', 'Moderate decline to 93.7%. Latency 680ms. No clear NPCI or bank-side signature. Manual review recommended.', ''),
    ('NEFT', 'NPCI_SIDE',    85, 'high',      'resolved',      60, 120, 'NEFT settlement delays — NPCI batch processing issue', 'NEFT success rate dropped to 82.1%. Settlement batches delayed by 45+ minutes. NPCI advisory confirmed maintenance overrun.', 'January 14, 2025 — IMPS — NPCI_SIDE'),
    ('UPI',  'BANK_SIDE',    72, 'medium',    'resolved',      55, 60,  'UPI failures — Citi VPA validation service timeout', 'UPI failure rate elevated to 8.4%. Traced to internal VPA validation microservice timeout. Other banks unaffected.', 'March 26, 2025 — BANK_SIDE'),
    ('NACH', 'NPCI_SIDE',    89, 'critical',  'resolved',      48, 240, 'NACH bulk debit failure — NPCI mandate registry down', 'NACH success rate collapsed to 34.2%. All corporate bulk debit mandates failing. NPCI mandate registry unreachable. Salary disbursements and EMI collections affected.', 'October 8, 2024 — RTGS — NPCI_SIDE'),
    ('IMPS', 'FALSE_POSITIVE',91,'low',       'resolved',      45, 3,   'IMPS latency spike — false alarm from monitoring glitch', 'Latency showed 4,200ms but transaction success rate remained 99.1%. Monitoring agent timeout, not actual IMPS issue.', 'November 22, 2024 — FALSE_POSITIVE'),
    ('UPI',  'NPCI_SIDE',    94, 'critical',  'resolved',      40, 180, 'UPI down — NPCI UPI switch maintenance overrun', 'Sudden drop to 0% at 02:30 IST. Scheduled maintenance window exceeded by 3 hours. All banks affected. NPCI announced delay at 03:15 IST.', 'April 12, 2025 — NPCI_SIDE'),
    ('RTGS', 'BANK_SIDE',    67, 'medium',    'resolved',      36, 45,  'RTGS high-value transfers failing — Citi RTGS gateway issue', 'Transactions above ₹50 Cr failing. Below threshold succeeding. Citi RTGS gateway certificate expiry caused partial failure.', 'March 26, 2025 — BANK_SIDE'),
    ('UPI',  'NPCI_SIDE',    88, 'high',      'resolved',      30, 75,  'UPI degraded — NPCI fraud detection engine slow', 'Success rate 87.3%. Latency 1,800ms. Pattern matches NPCI fraud detection engine overload. High transaction volume period.', 'April 12, 2025 — NPCI_SIDE'),
    ('NEFT', 'FALSE_POSITIVE',76,'low',       'resolved',      28, 5,   'NEFT error rate spike — data ingestion lag', 'Error rate showed 12% for 5 minutes. Root cause: delayed data ingestion from monitoring pipeline. Actual NEFT health was normal.', 'November 22, 2024 — FALSE_POSITIVE'),
    ('IMPS', 'NPCI_SIDE',    82, 'high',      'resolved',      24, 90,  'IMPS degradation — NPCI IMPS switch capacity breach', 'IMPS success rate 84.7%. Consistent with NPCI capacity limit breach during peak hour (12–2pm IST). All PSPs affected proportionally.', 'January 14, 2025 — IMPS — NPCI_SIDE'),
    ('UPI',  'BANK_SIDE',    81, 'medium',    'resolved',      22, 30,  'UPI collect failures — Citi collect API timeout', 'UPI collect requests failing at 23.4% rate. UPI pay requests normal. Isolated to Citi collect API endpoint — load balancer misconfiguration.', 'March 26, 2025 — BANK_SIDE'),
    ('NACH', 'BANK_SIDE',    69, 'low',       'resolved',      20, 20,  'NACH presentation delays — Citi NACH scheduler lag', 'NACH presentations delayed by 8 minutes. Citi internal NACH scheduler running behind. No mandates failed — only delayed.', 'March 26, 2025 — BANK_SIDE'),
    ('UPI',  'NPCI_SIDE',    93, 'critical',  'resolved',      18, 150, 'UPI major outage — NPCI database replication failure', 'UPI success rate dropped to 58.2%. NPCI confirmed database replication lag causing transaction routing failures. Longest outage in 6 months.', 'April 12, 2025 — NPCI_SIDE'),
    ('RTGS', 'FALSE_POSITIVE',84,'low',       'resolved',      16, 4,   'RTGS monitoring timeout — not a real degradation', 'RTGS monitoring agent lost connectivity for 4 minutes. No actual RTGS degradation. RBI RTGS status confirmed normal throughout.', 'November 22, 2024 — FALSE_POSITIVE'),
    ('UPI',  'BANK_SIDE',    74, 'medium',    'resolved',      14, 40,  'UPI QR code payments failing — Citi UPI QR service down', 'Static and dynamic QR code UPI payments failing at 67% rate. UPI intent payments normal. Citi UPI QR service pod restart required.', 'March 26, 2025 — BANK_SIDE'),
    ('IMPS', 'NPCI_SIDE',    87, 'high',      'resolved',      12, 85,  'IMPS success rate 81% — NPCI IMPS routing table update', 'IMPS degraded during NPCI routing table live update. All banks affected. NPCI completed update and service restored.', 'January 14, 2025 — NPCI_SIDE'),
    ('NEFT', 'BANK_SIDE',    71, 'low',       'resolved',      10, 15,  'NEFT batch submission delays — Citi NEFT batch engine lag', 'Citi NEFT batch submissions delayed by 12 minutes in the 14:00 IST batch. Other banks unaffected. Internal batch engine CPU spike.', 'March 26, 2025 — BANK_SIDE'),
    ('UPI',  'NPCI_SIDE',    90, 'high',      'resolved',       9, 60,  'UPI Lite failures — NPCI UPI Lite server unreachable', 'UPI Lite transactions failing at 100% rate. Regular UPI unaffected. NPCI UPI Lite server maintenance unannounced.', 'April 12, 2025 — NPCI_SIDE'),
    ('NACH', 'NPCI_SIDE',    83, 'critical',  'resolved',       8, 120, 'NACH return processing failure — NPCI return file engine down', 'NACH return files not being processed. 14,200 return transactions stuck. NPCI return file processing engine down for maintenance.', 'October 8, 2024 — NPCI_SIDE'),
    ('UPI',  'FALSE_POSITIVE',79,'low',       'resolved',       7, 2,   'UPI timeout alert — spike caused by monitoring reconnect', 'Alert triggered by monitoring system reconnecting after network maintenance. UPI health was normal throughout.', 'November 22, 2024 — FALSE_POSITIVE'),
    ('RTGS', 'NPCI_SIDE',    86, 'medium',    'resolved',       6, 50,  'RTGS settlement delays — RBI RTGS system upgrade', 'RTGS settlement times increased to 45 minutes (normal: 2 min). RBI RTGS system upgrade caused processing slowdown.', 'October 8, 2024 — RTGS — NPCI_SIDE'),
    ('UPI',  'BANK_SIDE',    77, 'medium',    'resolved',       5, 25,  'UPI mandate registration failing — Citi UPI mandate API issue', 'New UPI autopay mandate registrations failing at 89% rate. Existing mandates and payments unaffected. Citi UPI mandate API certificate issue.', 'March 26, 2025 — BANK_SIDE'),
    ('IMPS', 'FALSE_POSITIVE',88,'low',       'resolved',       4, 3,   'IMPS latency warning — load balancer health check false alert', 'Load balancer health check incorrectly flagged IMPS as slow. IMPS transactions processing normally at 98.9% success rate.', 'November 22, 2024 — FALSE_POSITIVE'),
    ('UPI',  'NPCI_SIDE',    92, 'critical',  'resolved',       3, 100, 'UPI 360-degree payment failure — NPCI UPI hub connectivity loss', 'UPI success rate 64.8%. NPCI UPI hub lost connectivity to 7 member banks simultaneously. Partial recovery at 30 min mark.', 'April 12, 2025 — NPCI_SIDE'),
    ('NEFT', 'NPCI_SIDE',    80, 'high',      'resolved',       2, 70,  'NEFT 2pm batch failure — NPCI NEFT clearing engine restart', 'Entire 14:00 NEFT batch failed to clear. NPCI NEFT clearing engine restarted mid-batch. Transactions re-presented in 16:00 batch.', 'January 14, 2025 — NPCI_SIDE'),
    ('UPI',  'BANK_SIDE',    66, 'low',       'resolved',       1, 12,  'UPI credit confirmation delays — Citi core banking sync lag', 'UPI credits taking 8-12 minutes to reflect in Citi accounts. UPI transactions succeeding but core banking sync delayed.', 'March 26, 2025 — BANK_SIDE'),
    ('IMPS', 'UNKNOWN',      48, 'medium',    'investigating',  0, 0,   'IMPS intermittent failures — investigating root cause', 'IMPS showing 91.4% success rate. Intermittent pattern — not consistent with known NPCI or bank signatures. Classifier confidence low at 48%. Manual review in progress.', ''),
    # 20 more for good measure
    ('UPI',  'NPCI_SIDE',    95, 'critical',  'resolved',     168, 300, 'UPI down — NPCI planned maintenance extended by 5 hours', 'Scheduled 2-hour maintenance window extended to 7 hours. All banks affected. NPCI issued OC advisory at 04:00 IST.', 'April 12, 2025 — NPCI_SIDE'),
    ('NACH', 'FALSE_POSITIVE',82,'low',       'resolved',     160, 4,   'NACH monitoring blip — false alert during DR drill', 'Disaster recovery drill caused monitoring false positive. NACH production environment unaffected.', 'November 22, 2024 — FALSE_POSITIVE'),
    ('UPI',  'BANK_SIDE',    73, 'medium',    'resolved',     150, 35,  'UPI P2M failures — Citi merchant UPI integration issue', 'UPI person-to-merchant payments failing. P2P payments normal. Citi merchant aggregator API timeout.', 'March 26, 2025 — BANK_SIDE'),
    ('RTGS', 'NPCI_SIDE',    88, 'high',      'resolved',     144, 90,  'RTGS cut-off time extension — RBI RTGS emergency maintenance', 'RBI extended RTGS cut-off by 2 hours for emergency maintenance. High-value transactions delayed but not failed.', 'October 8, 2024 — NPCI_SIDE'),
    ('IMPS', 'BANK_SIDE',    69, 'low',       'resolved',     138, 18,  'IMPS P2A failures — Citi account validation service slow', 'IMPS Pay to Account transactions failing at 14.2% rate. Account validation service responding slowly due to DB query issue.', 'March 26, 2025 — BANK_SIDE'),
    ('UPI',  'NPCI_SIDE',    91, 'critical',  'resolved',     120, 210, 'UPI widespread degradation — NPCI load balancer failure', 'UPI success rate 69.3%. NPCI load balancer failure caused uneven transaction routing. Recovery partial at 60 min.', 'April 12, 2025 — NPCI_SIDE'),
    ('NEFT', 'FALSE_POSITIVE',86,'low',       'resolved',     115, 3,   'NEFT error spike — timezone change DST artifact', 'Daylight saving time change caused 3-minute monitoring gap. NEFT transactions unaffected.', 'November 22, 2024 — FALSE_POSITIVE'),
    ('UPI',  'BANK_SIDE',    76, 'medium',    'resolved',     108, 42,  'UPI intent payments slow — Citi deep link service degraded', 'UPI intent-based payments (app-to-app) failing at 31% rate. Direct UPI payments normal. Citi deep link routing service high memory usage.', 'March 26, 2025 — BANK_SIDE'),
    ('NACH', 'NPCI_SIDE',    84, 'high',      'resolved',     100, 140, 'NACH debit mandate failures — NPCI NACH hub overloaded', 'NACH success rate 76.4% on first presentation. NPCI NACH hub overloaded during month-end EMI cycle peak.', 'October 8, 2024 — NPCI_SIDE'),
    ('UPI',  'NPCI_SIDE',    89, 'high',      'resolved',      96, 75,  'UPI slow — NPCI fraud scoring engine high latency', 'Transaction latency 2,400ms. Success rate maintained at 92.1% but very slow. NPCI fraud scoring engine processing backlog.', 'April 12, 2025 — NPCI_SIDE'),
    ('IMPS', 'NPCI_SIDE',    87, 'high',      'resolved',      90, 95,  'IMPS degradation — NPCI IMPS server hardware failure', 'IMPS success rate 79.8%. NPCI confirmed hardware failure on one of three IMPS servers. Partial capacity restoration at 45 min.', 'January 14, 2025 — NPCI_SIDE'),
    ('UPI',  'FALSE_POSITIVE',77,'low',       'resolved',      84, 2,   'UPI alert — API gateway restart triggered false alarm', 'Citi API gateway restart caused 90-second monitoring blackout. UPI transactions continued normally throughout.', 'November 22, 2024 — FALSE_POSITIVE'),
    ('RTGS', 'BANK_SIDE',    72, 'medium',    'resolved',      78, 38,  'RTGS transactions queued — Citi RTGS participant interface slow', 'RTGS transactions queuing at Citi side. RTGS network normal. Citi participant interface CPU saturation during batch processing.', 'March 26, 2025 — BANK_SIDE'),
    ('UPI',  'NPCI_SIDE',    93, 'critical',  'resolved',      72, 165, 'UPI major incident — NPCI network partition', 'UPI success rate 55.6%. NPCI experienced network partition between north and south zone servers. Geo-based transaction routing failure.', 'April 12, 2025 — NPCI_SIDE'),
    ('NEFT', 'BANK_SIDE',    68, 'low',       'resolved',      66, 22,  'NEFT duplicate detection false positives — Citi dedup engine issue', 'Citi NEFT duplicate detection engine incorrectly rejecting valid transactions. 6.2% of NEFT transactions falsely flagged.', 'March 26, 2025 — BANK_SIDE'),
    ('UPI',  'NPCI_SIDE',    90, 'high',      'resolved',      60, 80,  'UPI AutoPay failures — NPCI recurring mandate engine down', 'UPI AutoPay (recurring mandate) debits failing at 100%. One-time UPI payments normal. NPCI recurring mandate processing engine maintenance.', 'April 12, 2025 — NPCI_SIDE'),
    ('IMPS', 'FALSE_POSITIVE',83,'low',       'resolved',      54, 4,   'IMPS warning — synthetic transaction monitoring artifact', 'Synthetic transaction monitoring probe failure caused false degradation alert. Real customer transactions unaffected.', 'November 22, 2024 — FALSE_POSITIVE'),
    ('UPI',  'BANK_SIDE',    79, 'medium',    'resolved',      48, 32,  'UPI business payments slow — Citi UPI for business API lag', 'UPI for business (B2B) payments experiencing 8-second delays. Consumer UPI normal. Citi B2B UPI API under-provisioned resources.', 'March 26, 2025 — BANK_SIDE'),
    ('NACH', 'BANK_SIDE',    65, 'low',       'resolved',      42, 16,  'NACH late presentation — Citi NACH file upload delay', 'Citi NACH presentation files submitted 18 minutes late to NPCI. All mandates processed in next available window.', 'March 26, 2025 — BANK_SIDE'),
    ('UPI',  'NPCI_SIDE',    96, 'critical',  'resolved',      36, 190, 'UPI down — NPCI UPI switch software update failure', 'UPI switch software update caused complete service disruption. NPCI rolled back update at 45 min mark. Full recovery at 3h 10m.', 'April 12, 2025 — NPCI_SIDE'),
]

REROUTING_MAP = {
    'UPI':  ('IMPS', 98.9, 'IMPS operating at 98.9% success rate with 395ms average latency. Recommended as primary alternative for corporate collection flows, dealer settlements, and institutional transfers.'),
    'IMPS': ('NEFT', 99.6, 'NEFT operating at 99.6% with 372ms latency. Suitable for non-urgent transfers. Note: NEFT settlement is batch-based — advise clients on timing implications.'),
    'RTGS': ('NEFT', 99.6, 'NEFT available for transactions under ₹2 Cr. For high-value transactions above ₹2 Cr, consider SWIFT for cross-border or delay until RTGS restoration.'),
    'NEFT': ('IMPS', 98.9, 'IMPS available for real-time settlement. Suitable for urgent transfers requiring immediate credit confirmation.'),
    'NACH': ('NEFT', 99.6, 'NEFT available for individual transfers. For bulk debit mandates, consider rescheduling to next NACH presentation window (next day).'),
}


class Command(BaseCommand):
    help = 'Seed 50+ rich demo incidents for Citi presentation'

    def handle(self, *args, **options):
        self.stdout.write('Seeding demo data...')

        RailHealthSnapshot.objects.all().delete()
        Incident.objects.all().delete()
        ApiComplianceMetric.objects.all().delete()

        now = timezone.now()

        # Rail health history — 7 days of data
        rails_config = {'UPI': 99.4, 'IMPS': 98.9, 'RTGS': 99.8, 'NEFT': 99.6, 'NACH': 99.1}
        for rail, baseline in rails_config.items():
            for i in range(480):
                ts = now - timedelta(seconds=30 * (480 - i))
                # Simulate degradations at specific windows
                if rail == 'UPI' and 60 <= i <= 100:
                    rate = round(random.uniform(65, 78), 2); status = 'down'
                elif rail == 'UPI' and 100 <= i <= 130:
                    rate = round(random.uniform(82, 91), 2); status = 'degraded'
                elif rail == 'IMPS' and 150 <= i <= 180:
                    rate = round(random.uniform(87, 93), 2); status = 'degraded'
                elif rail == 'UPI' and 300 <= i <= 340:
                    rate = round(random.uniform(55, 70), 2); status = 'down'
                else:
                    rate = round(baseline + random.uniform(-0.5, 0.3), 2); status = 'healthy'
                RailHealthSnapshot.objects.create(
                    rail_name=rail, success_rate=rate,
                    latency_ms=random.randint(250, 450) if status == 'healthy' else random.randint(700, 2500),
                    transactions_per_min=random.randint(12000, 16000) if rail == 'UPI' else random.randint(2000, 5000),
                    status=status, error_rate=round(100 - rate, 2),
                    raw_data={'source': 'seed', 'index': i},
                )
        self.stdout.write(f'  Rail snapshots: {RailHealthSnapshot.objects.count()}')

        # Create all incidents
        for idx, inc_data in enumerate(INCIDENTS_DATA):
            rail, cls, conf, sev, status, hours_ago, res_mins, title, reasoning, hist = inc_data

            snap = RailHealthSnapshot.objects.filter(
                rail_name=rail
            ).order_by('?').first()

            detected = now - timedelta(hours=hours_ago) if hours_ago > 0 else now - timedelta(minutes=random.randint(2, 15))
            resolved_at = detected + timedelta(minutes=res_mins) if status == 'resolved' and res_mins > 0 else None

            inc = Incident.objects.create(
                rail=snap, rail_name=rail,
                classification=cls, confidence_score=conf,
                severity=sev, status=status,
                title=title, classifier_reasoning=reasoning,
                historical_match=hist,
                detected_at=detected, resolved_at=resolved_at,
            )

            # Agent runs for all incidents
            AgentRun.objects.create(incident=inc, agent_type='rail_monitor', status='completed',
                input_data={'rail': rail, 'success_rate': round(random.uniform(65, 94), 1)},
                output_data={'anomaly_detected': True},
                duration_ms=random.randint(60, 120),
                completed_at=detected + timedelta(seconds=30),
            )
            AgentRun.objects.create(incident=inc, agent_type='incident_classifier', status='completed',
                input_data={'rail': rail},
                output_data={'classification': cls, 'confidence': conf},
                duration_ms=random.randint(2800, 4200),
                completed_at=detected + timedelta(seconds=90),
            )

            # Rerouting for non-false-positives with severity >= medium
            if cls not in ('FALSE_POSITIVE',) and sev in ('critical', 'high', 'medium'):
                to_rail, success_rate, rationale = REROUTING_MAP.get(rail, ('IMPS', 98.9, 'Alternative rail available.'))
                ReroutingRecommendation.objects.create(
                    incident=inc, from_rail=rail, to_rail=to_rail,
                    confidence=round(random.uniform(75, 96), 1),
                    estimated_success_rate=success_rate,
                    rationale=rationale,
                )
                AgentRun.objects.create(incident=inc, agent_type='rerouting_advisor', status='completed',
                    input_data={'from_rail': rail},
                    output_data={'to_rail': to_rail, 'viable': True},
                    duration_ms=random.randint(1200, 2100),
                    completed_at=detected + timedelta(seconds=110),
                )

            AgentRun.objects.create(incident=inc, agent_type='compliance_watchdog', status='completed',
                input_data={},
                output_data={'all_compliant': random.random() > 0.15},
                duration_ms=random.randint(300, 600),
                completed_at=detected + timedelta(seconds=120),
            )

            # Comms for serious incidents
            if sev in ('critical', 'high') or status == 'investigating':
                draft_status = 'approved' if status == 'resolved' else 'draft'
                AgentRun.objects.create(incident=inc, agent_type='comms_generator', status='completed',
                    input_data={},
                    output_data={'drafts_created': 2},
                    duration_ms=random.randint(3500, 5500),
                    completed_at=detected + timedelta(seconds=150),
                )
                CommunicationDraft.objects.create(
                    incident=inc, audience='client_services',
                    subject_line=f'{rail} Alert — {cls.replace("_", " ").title()} — Internal Briefing',
                    draft_text=f'Our AI monitoring has classified this {rail} incident as {cls.replace("_", " ").lower()} with {conf}% confidence. {reasoning[:200]}... Rerouting to alternative rails where applicable. Updates every 30 minutes.',
                    status=draft_status,
                    approved_by='ops_lead' if draft_status == 'approved' else '',
                    approved_at=detected + timedelta(minutes=10) if draft_status == 'approved' else None,
                )
                CommunicationDraft.objects.create(
                    incident=inc, audience='corporate_client',
                    subject_line=f'Payment Processing Update — {rail} Service Advisory',
                    draft_text=f'Dear Valued Client, we are monitoring a temporary disruption affecting {rail} payment processing. Our teams are actively working on resolution. Alternative payment channels are available. We will provide updates every 30 minutes. Please contact your relationship manager for urgent requirements.',
                    status=draft_status,
                    approved_by='client_services_head' if draft_status == 'approved' else '',
                    approved_at=detected + timedelta(minutes=15) if draft_status == 'approved' else None,
                )

        self.stdout.write(f'  Incidents: {Incident.objects.count()}')
        self.stdout.write(f'  Agent runs: {AgentRun.objects.count()}')
        self.stdout.write(f'  Comms drafts: {CommunicationDraft.objects.count()}')

        # Compliance metrics
        apis = [
            ('check_transaction_status', 3.0, 1.42),
            ('initiate_payment', 10.0, 6.83),
            ('balance_enquiry', 5.0, 2.14),
            ('validate_vpa', 8.0, 3.31),
        ]
        for api_name, limit, current in apis:
            ApiComplianceMetric.objects.create(
                api_name=api_name, tps_current=current, tps_limit=limit,
                calls_last_minute=int(current * 60),
                calls_last_hour=int(current * 3580),
                is_compliant=True,
            )

        # 15 compliance violations — mix of critical and warnings
        violations = [
            ('check_transaction_status', 3.84, 3.0, 'critical', 'OC-215 VIOLATION: Check Transaction Status at 3.84 TPS exceeded limit of 3.0 TPS during UPI incident response. Automatic rate limiting triggered. This exact pattern caused the April 12 2025 NPCI outage.', 72),
            ('check_transaction_status', 2.87, 3.0, 'warning',  'OC-215 WARNING: Check Transaction Status at 2.87 TPS (95.7% of limit). Approaching threshold during active incident investigation.', 71),
            ('check_transaction_status', 3.21, 3.0, 'critical', 'OC-215 VIOLATION: Check Transaction Status at 3.21 TPS during NACH outage response. Rate limiter engaged after 45 seconds.', 48),
            ('check_transaction_status', 2.73, 3.0, 'warning',  'OC-215 WARNING: Check Transaction Status at 2.73 TPS during elevated monitoring period post-incident.', 47),
            ('initiate_payment', 10.43, 10.0, 'critical', 'OC-215 VIOLATION: Initiate Payment at 10.43 TPS during month-end peak. Burst protection triggered. 847 transactions queued.', 30),
            ('check_transaction_status', 2.91, 3.0, 'warning',  'OC-215 WARNING: Check Transaction Status at 2.91 TPS (97% of limit) during UPI degradation monitoring.', 22),
            ('balance_enquiry', 4.82, 5.0, 'warning', 'OC-215 WARNING: Balance Enquiry at 4.82 TPS (96.4% of limit). Elevated client balance checks during UPI outage period.', 18),
            ('check_transaction_status', 3.67, 3.0, 'critical', 'OC-215 VIOLATION: Check Transaction Status at 3.67 TPS during IMPS degradation response. Third violation in 30-day period.', 12),
            ('validate_vpa', 7.94, 8.0, 'warning', 'OC-215 WARNING: Validate VPA at 7.94 TPS (99.3% of limit). Near-violation during bulk UPI mandate registration campaign.', 10),
            ('check_transaction_status', 2.68, 3.0, 'warning', 'OC-215 WARNING: Check Transaction Status at 2.68 TPS during routine monitoring window.', 8),
            ('initiate_payment', 9.87, 10.0, 'warning', 'OC-215 WARNING: Initiate Payment at 9.87 TPS (98.7% of limit) during salary credit disbursement peak.', 6),
            ('check_transaction_status', 3.12, 3.0, 'critical', 'OC-215 VIOLATION: Check Transaction Status at 3.12 TPS. Automated alert sent to compliance team. Rate limiting applied within 8 seconds.', 4),
            ('balance_enquiry', 4.71, 5.0, 'warning', 'OC-215 WARNING: Balance Enquiry at 4.71 TPS. Likely driven by client-side retry logic during IMPS intermittent failures.', 3),
            ('check_transaction_status', 2.84, 3.0, 'warning', 'OC-215 WARNING: Check Transaction Status at 2.84 TPS during current active incident investigation.', 1),
            ('validate_vpa', 7.82, 8.0, 'warning', 'OC-215 WARNING: Validate VPA at 7.82 TPS. Elevated VPA lookups correlating with active UPI incident period.', 0),
        ]

        check_metric = ApiComplianceMetric.objects.get(api_name='check_transaction_status')
        initiate_metric = ApiComplianceMetric.objects.get(api_name='initiate_payment')
        balance_metric = ApiComplianceMetric.objects.get(api_name='balance_enquiry')
        validate_metric = ApiComplianceMetric.objects.get(api_name='validate_vpa')
        metric_map = {
            'check_transaction_status': check_metric,
            'initiate_payment': initiate_metric,
            'balance_enquiry': balance_metric,
            'validate_vpa': validate_metric,
        }

        for api_name, tps_obs, tps_lim, severity, desc, hours_ago in violations:
            ComplianceViolation.objects.create(
                metric=metric_map[api_name],
                api_name=api_name,
                tps_observed=tps_obs,
                tps_limit=tps_lim,
                severity=severity,
                description=desc,
                occurred_at=now - timedelta(hours=hours_ago) if hours_ago > 0 else now - timedelta(minutes=random.randint(5, 30)),
            )

        self.stdout.write(f'  Compliance violations: {ComplianceViolation.objects.count()}')
        self.stdout.write(self.style.SUCCESS(f'Done. {Incident.objects.count()} incidents, {ComplianceViolation.objects.count()} violations.'))
