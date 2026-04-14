from abc import ABC, abstractmethod
from dataclasses import dataclass
from typing import Dict, List


@dataclass
class RailHealthData:
    rail_name: str
    success_rate: float
    latency_ms: int
    transactions_per_min: int
    error_rate: float
    raw_data: dict


@dataclass
class ComplianceData:
    api_name: str
    tps_current: float
    tps_limit: float
    calls_last_minute: int
    calls_last_hour: int


class BaseDataSourceAdapter(ABC):
    """
    Abstract interface for all data sources.
    
    The entire agent system reads from this interface.
    Swap MockAdapter for ProductionAdapter at deploy time —
    zero changes required in agents, API, or database layer.
    
    Production implementation (Citi builds):
    - Connect to internal NPCI PSP member feeds
    - Pull from Citi's own transaction success rate counters
    - Source OC-215 API call metrics from internal rate limiters
    """

    @abstractmethod
    def get_rail_health(self, rail_name: str) -> RailHealthData:
        """Return current health snapshot for a single rail."""
        pass

    @abstractmethod
    def get_all_rails_health(self) -> List[RailHealthData]:
        """Return health snapshots for all monitored rails."""
        pass

    @abstractmethod
    def get_compliance_metrics(self) -> List[ComplianceData]:
        """Return current OC-215 API call rate metrics."""
        pass

    @abstractmethod
    def get_historical_incidents(self, limit: int = 20) -> List[Dict]:
        """Return recent historical incidents for RAG pattern matching."""
        pass
