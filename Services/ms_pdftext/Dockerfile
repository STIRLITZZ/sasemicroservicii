FROM python:3.11-slim

WORKDIR /app
RUN pip install --no-cache-dir httpx pypdf confluent-kafka

COPY . .

# Use async consumer by default
CMD ["python", "consumer_async.py"]
