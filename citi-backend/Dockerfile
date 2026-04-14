FROM python:3.11-slim 
 
WORKDIR /app 
 
COPY requirements.txt . 
RUN pip install --no-cache-dir -r requirements.txt 
 
COPY . . 
 
EXPOSE 8000 
CMD python manage.py migrate && python manage.py seed_demo && daphne config.asgi:application --port $PORT --bind 0.0.0.0 
