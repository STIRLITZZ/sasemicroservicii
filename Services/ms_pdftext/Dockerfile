FROM python:3.11-slim

WORKDIR /app
RUN pip install --no-cache-dir requests pypdf confluent-kafka

COPY . .

CMD ["python", "consumer.py"]
