FROM python:3.11-slim

WORKDIR /app

COPY requirements.txt .
RUN pip install --no-cache-dir -r requirements.txt

COPY . .

EXPOSE 8000

SHELL ["/bin/sh", "-c"]

CMD python manage.py migrate && python manage.py seed_demo && daphne -b 0.0.0.0 -p ${PORT:-8000} config.asgi:application