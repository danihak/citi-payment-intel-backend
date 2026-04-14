FROM python:3.12-slim

ENV PYTHONUNBUFFERED=1
ENV PYTHONDONTWRITEBYTECODE=1

WORKDIR /app

COPY requirements.txt .
RUN pip install --no-cache-dir -r requirements.txt

COPY . .

EXPOSE 8000

CMD ["sh", "-c", "python manage.py migrate && if [ $(python manage.py shell -c 'from apps.incidents.models import Incident; print(Incident.objects.count())') -lt 10 ]; then python manage.py seed_demo; fi && python manage.py runserver 0.0.0.0:${PORT:-8000}"]
