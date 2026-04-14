# India Payment Intelligence Hub — Backend

Django 5 + Celery + Django Channels + Claude API

## What this is

Agentic platform that monitors India payment rail health (UPI, IMPS, RTGS, NEFT, NACH),
classifies incidents using Claude API, recommends rerouting, monitors OC-215 compliance,
and generates banking-grade communication drafts — all in under 2 minutes from anomaly detection.

Built as a product demo for Citi TTS (Treasury & Trade Solutions), Pune.

## Architecture

```
DataSourceAdapter (swappable)
    └── MockAdapter ships with this repo
    └── ProductionAdapter — Citi builds this using internal NPCI PSP feeds

5 Celery Agents
    Rail Monitor     → polls every 30s
    Classifier       → Claude API, root cause in <2 min
    Rerouting        → parallel fork, best alternative rail
    Compliance       → OC-215 API rate monitoring
    Comms Generator  → Claude API, banking-grade drafts
```

## Local setup

```bash
# 1. Clone and install
pip install -r requirements.txt

# 2. Environment
cp .env.example .env
# Fill in ANTHROPIC_API_KEY

# 3. Start Redis (required for Celery)
docker run -d -p 6379:6379 redis:alpine
# or: brew services start redis

# 4. Migrate and seed
python manage.py migrate
python manage.py seed_demo

# 5. Start all services (4 terminals)
python manage.py runserver          # Django API
daphne config.asgi:application      # WebSocket (Channels)
celery -A config.celery worker -l info   # Agent workers
celery -A config.celery beat -l info     # Scheduler (triggers rail monitor every 30s)
```

API available at: http://localhost:8000
WebSocket at: ws://localhost:8000/ws/rail-updates/

## Key endpoints

| Method | Endpoint | Description |
|--------|----------|-------------|
| GET | /api/v1/rails/status/ | Current health of all 5 rails |
| GET | /api/v1/rails/{name}/history/ | Last 50 snapshots for sparkline |
| POST | /api/v1/rails/poll/ | Manually trigger a rail poll |
| GET | /api/v1/incidents/ | Incident list with filters |
| GET | /api/v1/incidents/{id}/ | Full incident with agent runs + drafts |
| POST | /api/v1/incidents/simulate/ | Trigger synthetic April 12-style incident |
| POST | /api/v1/incidents/{id}/resolve/ | Mark incident resolved |
| GET | /api/v1/compliance/dashboard/ | OC-215 metrics for all APIs |
| GET | /api/v1/compliance/violations/ | Audit log |
| GET | /api/v1/communications/ | All communication drafts |
| POST | /api/v1/communications/{id}/approve/ | Human approval gate |
| POST | /api/v1/communications/{id}/reject/ | Reject for revision |
| WS | /ws/rail-updates/ | Real-time WebSocket stream |

## Railway deployment

1. Push to GitHub: `danihak/citi-payment-intel-backend`
2. New project on railway.app → Deploy from GitHub repo
3. Add services: PostgreSQL + Redis (Railway provides both)
4. Set environment variables:
   ```
   SECRET_KEY=<generate with: python -c "import secrets; print(secrets.token_hex(32))">
   DEBUG=False
   ALLOWED_HOSTS=your-railway-domain.railway.app
   DATABASE_URL=<auto-set by Railway PostgreSQL>
   REDIS_URL=<auto-set by Railway Redis>
   ANTHROPIC_API_KEY=sk-ant-...
   CORS_ALLOWED_ORIGINS=https://your-vercel-app.vercel.app
   ```
5. Add two more Railway services from same repo:
   - Worker: `celery -A config.celery worker -l info`
   - Beat: `celery -A config.celery beat -l info`

## DataSourceAdapter swap (for Citi production)

The only file that changes for production:
`adapters/production_adapter.py` — implement the 4 methods using Citi's internal feeds.
All agents, APIs, and models remain identical.
