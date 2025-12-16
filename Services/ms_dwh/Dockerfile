FROM python:3.11-slim

WORKDIR /app

RUN pip install --no-cache-dir \
    confluent-kafka \
    fastapi \
    uvicorn[standard] \
    sqlalchemy \
    pandas

COPY . .

# Run both consumer (background) and API server
CMD ["sh", "-c", "python consumer.py & uvicorn api:app --host 0.0.0.0 --port 8000"]
