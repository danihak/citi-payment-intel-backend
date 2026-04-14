import random
import math
from datetime import datetime, timezone
from typing import Dict, List
from .base import BaseDataSourceAdapter, RailHealthData, ComplianceData


class MockDataAdapter(BaseDataSourceAdapter):
    """
    Synthetic data adapter for demo purposes.
    
    Simulates realistic India payment rail behavior:
    - Normal operation: UPI 99.2-99.8% success, IMPS 98.5-99.5%
    - Periodic degradation events (mimics real NPCI patterns)
    - April 12-style cascade failure simulation
    - OC-215 compliant API call rates (with occasional near-violations)
    
    Replace this class with ProductionAdapter to connect
    Citi's internal NPCI PSP member feeds and transaction counters.
    """

    # Rail baseline configs
    RAIL_BASELINES = {
        'UPI':  {'success': 99.4, 'latency': 285,  'tpm': 14200, 'error': 0.6},
        'IMPS': {'success': 98.9, 'latency': 420,  'tpm': 3800,  'error': 1.1},
        'RTGS': {'success': 99.8, 'latency': 1200, 'tpm': 180,   'error': 0.2},
        'NEFT': {'success': 99.6, 'latency': 890,  'tpm': 620,   'error': 0.4},
        'NACH': {'success': 99.1, 'latency': 650,  'tpm': 290,   'error': 0.9},
    }

    # Historical incidents for RAG pattern matching
    HISTORICAL_INCIDENTS = [
        {
            'date': 'April 12, 2025',
            'rail': 'UPI',
            'classification': 'NPCI_SIDE',
            'duration_hours': 5,
            'success_rate_at_detection': 71.3,
            'root_cause': 'NPCI infrastructure overload caused by banks flooding Check Transaction Status API. OC-215 issued post-incident.',
            'signature': 'rapid success rate drop >20% within 10 minutes, latency spike >3x baseline, all banks affected simultaneously',
            'resolution': 'NPCI rolled back infrastructure update. Banks implemented rate limiting per OC-215.',
        },
        {
            'date': 'March 26, 2025',
            'rail': 'UPI',
            'classification': 'BANK_SIDE',
            'duration_hours': 1.5,
            'success_rate_at_detection': 88.2,
            'root_cause': 'Citi internal switch failover caused temporary routing failures. Other banks unaffected.',
            'signature': 'gradual success rate drop, Citi-specific transactions only, other PSP banks normal',
            'resolution': 'Failover to secondary switch completed.',
        },
        {
            'date': 'January 14, 2025',
            'rail': 'IMPS',
            'classification': 'NPCI_SIDE',
            'duration_hours': 2,
            'success_rate_at_detection': 82.1,
            'root_cause': 'NPCI IMPS settlement engine maintenance window ran over. All banks affected.',
            'signature': 'sudden onset during off-peak hours, all banks affected, NPCI advisory issued within 30 minutes',
            'resolution': 'NPCI maintenance completed. Service restored.',
        },
        {
            'date': 'November 22, 2024',
            'rail': 'UPI',
            'classification': 'FALSE_POSITIVE',
            'duration_hours': 0.25,
            'success_rate_at_detection': 91.4,
            'root_cause': 'Internal monitoring sensor false alarm. UPI health was normal. Citi internal metrics collection bug.',
            'signature': 'single data point drop, self-corrected within 2 minutes, NPCI status page showed normal',
            'resolution': 'No action needed. Monitoring bug patched.',
        },
        {
            'date': 'October 8, 2024',
            'rail': 'RTGS',
            'classification': 'NPCI_SIDE',
            'duration_hours': 3,
            'success_rate_at_detection': 94.2,
            'root_cause': 'RBI RTGS system upgrade caused intermittent settlement failures.',
            'signature': 'RTGS only affected, high-value transactions failing, RBI announced maintenance',
            'resolution': 'RBI upgrade completed successfully.',
        },
    ]

    def _get_time_factor(self) -> float:
        """Simulate diurnal patterns — lower success during peak hours."""
        hour = datetime.now(timezone.utc).hour + 5.5  # IST offset
        hour = hour % 24
        # Peak hours 10am-2pm and 4pm-8pm IST = lower success
        if 10 <= hour <= 14 or 16 <= hour <= 20:
            return random.uniform(-0.8, 0.2)
        return random.uniform(-0.2, 0.3)

    def _should_simulate_incident(self) -> bool:
        """5% chance of degradation event per poll cycle."""
        return random.random() < 0.05

    def _get_incident_factor(self) -> float:
        """Severity of a simulated degradation."""
        severity = random.choice(['minor', 'moderate', 'severe'])
        if severity == 'minor':
            return random.uniform(-8, -3)
        elif severity == 'moderate':
            return random.uniform(-18, -8)
        else:
            return random.uniform(-30, -18)

    def get_rail_health(self, rail_name: str) -> RailHealthData:
        baseline = self.RAIL_BASELINES.get(rail_name, self.RAIL_BASELINES['UPI'])
        time_factor = self._get_time_factor()

        success_rate = baseline['success'] + time_factor
        latency = baseline['latency'] + random.randint(-30, 80)
        tpm = baseline['tpm'] + random.randint(-200, 200)
        error_rate = baseline['error'] - time_factor * 0.5

        if self._should_simulate_incident():
            incident_factor = self._get_incident_factor()
            success_rate += incident_factor
            latency = int(latency * (1 + abs(incident_factor) / 20))
            error_rate += abs(incident_factor)

        success_rate = max(0.0, min(100.0, round(success_rate, 2)))
        error_rate = max(0.0, min(100.0, round(error_rate, 2)))
        latency = max(50, int(latency))
        tpm = max(0, int(tpm))

        if success_rate >= 98.0:
            status = 'healthy'
        elif success_rate >= 92.0:
            status = 'degraded'
        elif success_rate >= 70.0:
            status = 'degraded'
        else:
            status = 'down'

        return RailHealthData(
            rail_name=rail_name,
            success_rate=success_rate,
            latency_ms=latency,
            transactions_per_min=tpm,
            error_rate=error_rate,
            raw_data={
                'source': 'mock_adapter',
                'baseline_success': baseline['success'],
                'time_factor': round(time_factor, 3),
                'sampled_at': datetime.now(timezone.utc).isoformat(),
            }
        )

    def get_all_rails_health(self) -> List[RailHealthData]:
        return [self.get_rail_health(rail) for rail in self.RAIL_BASELINES.keys()]

    def get_compliance_metrics(self) -> List[ComplianceData]:
        apis = [
            ('check_transaction_status', 3.0),
            ('initiate_payment', 10.0),
            ('balance_enquiry', 5.0),
            ('validate_vpa', 8.0),
        ]
        metrics = []
        for api_name, limit in apis:
            # Normally well within limits, occasional near-violation
            if random.random() < 0.03:  # 3% chance of near-violation
                current_tps = round(limit * random.uniform(0.92, 1.05), 2)
            else:
                current_tps = round(limit * random.uniform(0.3, 0.75), 2)

            metrics.append(ComplianceData(
                api_name=api_name,
                tps_current=current_tps,
                tps_limit=limit,
                calls_last_minute=int(current_tps * 60),
                calls_last_hour=int(current_tps * 3600 * random.uniform(0.8, 1.0)),
            ))
        return metrics

    def get_historical_incidents(self, limit: int = 20) -> List[Dict]:
        return self.HISTORICAL_INCIDENTS[:limit]
