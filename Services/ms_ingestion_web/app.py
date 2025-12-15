import os
from fastapi import FastAPI
from scraper import scrape
from producer import make_producer, send

KAFKA_BOOTSTRAP = os.getenv("KAFKA_BOOTSTRAP", "kafka:9092")
TOPIC_RAW = "court.raw"

app = FastAPI(title="MS Ingestion Web")

producer = make_producer(KAFKA_BOOTSTRAP)


@app.post("/run")
def run(date_range: str):
    """
    Exemple:
    date_range = "2025-12-06 TO 2025-12-12"
    """
    sent = 0
    for event in scrape(date_range):
        send(producer, TOPIC_RAW, event)
        sent += 1

    producer.flush()
    return {
        "status": "OK",
        "events_sent": sent,
        "topic": TOPIC_RAW
    }
