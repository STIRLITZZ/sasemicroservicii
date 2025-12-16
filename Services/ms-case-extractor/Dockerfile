FROM python:3.11-slim

WORKDIR /app
COPY requirements.txt .
RUN pip install --no-cache-dir -r requirements.txt
# Adaugă aiofiles pentru async file I/O
RUN pip install --no-cache-dir aiofiles

COPY app ./app
COPY consumer.py .
COPY consumer_async.py .
EXPOSE 8000

CMD ["uvicorn", "app.main:app", "--host=0.0.0.0", "--port=8000"]
