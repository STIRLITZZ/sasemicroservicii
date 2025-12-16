#!/usr/bin/env python3
"""
DWH Consumer - procesează date enriched și le agregă în warehouse
"""

import json
import os
from datetime import datetime
from confluent_kafka import Consumer
from dwh_engine import DWHEngine

KAFKA = os.getenv("KAFKA_BOOTSTRAP", "kafka:9092")
IN_TOPIC = "court.enriched"

consumer = Consumer({
    "bootstrap.servers": KAFKA,
    "group.id": "ms_dwh",
    "auto.offset.reset": "earliest"
})

consumer.subscribe([IN_TOPIC])
dwh = DWHEngine()

print(f"[DWH Consumer] Listening on {IN_TOPIC}...")
print(f"[DWH] Database initialized at {dwh.db_path}")

processed_count = 0

while True:
    msg = consumer.poll(1.0)
    if msg is None:
        continue
    if msg.error():
        print(f"[ERROR] {msg.error()}")
        continue

    try:
        event = json.loads(msg.value().decode("utf-8"))

        # Procesează cazul în DWH
        dwh.process_case(event)
        processed_count += 1

        # Log periodic
        if processed_count % 10 == 0:
            print(f"[DWH] Processed {processed_count} cases")

        # Calculează agregări la fiecare 50 de cazuri
        if processed_count % 50 == 0:
            dwh.compute_aggregates()
            print(f"[DWH] Computed aggregates at {processed_count} cases")

    except Exception as e:
        print(f"[ERROR] Failed to process message: {e}")
