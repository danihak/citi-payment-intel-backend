"""
Demo data refresh task.

Runs periodically via Celery beat to keep demo timestamps fresh — without this,
the seed runs once on first deploy and then every record is stamped with that
deploy date, producing the '19d ago' staleness on every dashboard surface.

This calls the existing seed_demo management command with --force, which wipes
and re-seeds with timestamps relative to the current `now`. The wipe + reseed
approach is chosen over in-place timestamp shifting because:
  1. It guarantees a known, coherent demo state every refresh window.
  2. It removes any drift from stray Simulate Incident clicks or test data.
  3. It's idempotent and easy to debug — same data every cycle.
"""
import logging
from io import StringIO
from django.core.management import call_command
from config.celery import app

logger = logging.getLogger(__name__)


@app.task(name='agents.demo_refresh.run')
def run():
    """Wipe and re-seed demo data so timestamps stay relative to `now`."""
    out = StringIO()
    try:
        call_command('seed_demo', '--force', stdout=out)
        output = out.getvalue()
        logger.info(f"Demo data refreshed: {output.strip()}")
        return {'status': 'refreshed', 'output': output}
    except Exception as e:
        logger.exception("Demo refresh failed")
        return {'status': 'failed', 'error': str(e)}
