from typing import Dict, List
from .base import BaseDataSourceAdapter, RailHealthData, ComplianceData


class ProductionAdapter(BaseDataSourceAdapter):
    """
    Production data adapter — to be implemented by Citi's engineering team.

    This class is the ONLY file that changes when moving from demo to production.
    All agents, API endpoints, and database models remain identical.

    Implementation guide for Citi engineers:
    
    1. get_rail_health / get_all_rails_health:
       - Connect to Citi's internal NPCI PSP member API feeds
       - Pull from Citi's own transaction success rate counters (TPS dashboard)
       - Cross-reference with internal switch health metrics
       - Optionally subscribe to NPCI's direct member alerts (Debopama's team has access)
    
    2. get_compliance_metrics:
       - Read from Citi's API gateway rate limiter counters
       - Source: internal middleware that logs all outgoing NPCI API calls
       - OC-215 limits: Check Transaction Status = max 3 TPS, 90s minimum gap per txn
    
    3. get_historical_incidents:
       - Pull from this same database (incidents table)
       - Optionally pull from Citi's internal JIRA/ServiceNow incident log
    
    Estimated implementation effort: 2-3 sprints for a mid-level backend engineer.
    """

    def __init__(self):
        raise NotImplementedError(
            "ProductionAdapter is a stub. "
            "Citi engineering team implements this class. "
            "Use MockDataAdapter for demo. "
            "See implementation guide in docstring."
        )

    def get_rail_health(self, rail_name: str) -> RailHealthData:
        raise NotImplementedError

    def get_all_rails_health(self) -> List[RailHealthData]:
        raise NotImplementedError

    def get_compliance_metrics(self) -> List[ComplianceData]:
        raise NotImplementedError

    def get_historical_incidents(self, limit: int = 20) -> List[Dict]:
        raise NotImplementedError
