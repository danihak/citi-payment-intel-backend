FROM python:3.11-slim

WORKDIR /app

COPY requirements.txt .
RUN pip install --no-cache-dir -r requirements.txt

COPY . .

EXPOSE 8000

CMD ["sh", "-c", "python manage.py migrate 2>&1 && echo 'MIGRATIONS DONE' && python manage.py check 2>&1 && echo 'CHECK DONE' && daphne -v 2 -b 0.0.0.0 -p ${PORT:-8000} config.asgi:application 2>&1"]# force rebuild 
