#!/usr/bin/env python3
"""
Kafka consumer pentru ms-case-extractor.
Citește evenimente din 'court.text' și extrage metadate din text.
Publică rezultate în 'court.enriched'.
"""

import json
import os
from confluent_kafka import Consumer, Producer

from app.extractor import extract_case


KAFKA = os.getenv("KAFKA_BOOTSTRAP", "kafka:9092")
IN_TOPIC = "court.text"
OUT_TOPIC = "court.enriched"


def make_producer(bootstrap_servers: str):
    return Producer({"bootstrap.servers": bootstrap_servers})


def send(producer: Producer, topic: str, event: dict):
    producer.produce(
        topic,
        json.dumps(event, ensure_ascii=False).encode("utf-8")
    )
    producer.poll(0)


consumer = Consumer({
    "bootstrap.servers": KAFKA,
    "group.id": "ms_case_extractor",
    "auto.offset.reset": "earliest"
})

producer = make_producer(KAFKA)
consumer.subscribe([IN_TOPIC])

print(f"[ms-case-extractor consumer] Listening on {IN_TOPIC}...")

while True:
    msg = consumer.poll(1.0)
    if msg is None:
        continue
    if msg.error():
        print(f"[ERROR] {msg.error()}")
        continue

    event = json.loads(msg.value().decode("utf-8"))

    # Citește textul din fișierul txt
    txt_path = event.get("txt_path")
    if not txt_path or not os.path.exists(txt_path):
        print(f"[SKIP] Missing txt_path or file not found: {txt_path}")
        continue

    try:
        with open(txt_path, "r", encoding="utf-8") as f:
            text = f.read()
    except Exception as e:
        print(f"[ERROR] Could not read {txt_path}: {e}")
        continue

    # Extrage metadate
    try:
        result = extract_case(text, filename=txt_path)
        extracted = result.model_dump()
    except Exception as e:
        print(f"[ERROR] Extraction failed for {txt_path}: {e}")
        continue

    # Combină cu informații din event anterior
    enriched = {
        **event,  # păstrează instanta, dosar, dedup_key, pdf_path, txt_path
        "extracted": extracted,
        "status": "enriched"
    }

    send(producer, OUT_TOPIC, enriched)
    producer.flush()

    print(f"[OK] Enriched: {event.get('dosar', '?')} -> {OUT_TOPIC}")
