FROM python:3.12-slim

ENV PYTHONUNBUFFERED=1
ENV PYTHONDONTWRITEBYTECODE=1

WORKDIR /app

COPY requirements.txt .
RUN pip install --no-cache-dir -r requirements.txt

COPY . .

EXPOSE 8000

CMD ["sh", "-c", "python manage.py migrate && python -c \"import django; django.setup(); from apps.incidents.models import Incident; exit(0 if Incident.objects.count() >= 10 else 1)\" 2>/dev/null || python manage.py seed_demo && python manage.py runserver 0.0.0.0:${PORT:-8000}"]
