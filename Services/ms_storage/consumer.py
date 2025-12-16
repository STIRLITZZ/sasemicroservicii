#!/usr/bin/env python3
"""
Storage consumer - salvează datele enriched pentru a fi afișate în UI.
Citește din 'court.enriched' și salvează într-un JSON file.
Optimizat cu batching pentru a reduce scrierea pe disc.
"""

import json
import os
import time
from confluent_kafka import Consumer
from pathlib import Path

KAFKA = os.getenv("KAFKA_BOOTSTRAP", "kafka:9092")
IN_TOPIC = "court.enriched"
STORAGE_FILE = "/data/enriched/cases.json"

# Batching parameters
BATCH_SIZE = int(os.getenv("STORAGE_BATCH_SIZE", "10"))  # Scrie după 10 mesaje
BATCH_TIMEOUT = int(os.getenv("STORAGE_BATCH_TIMEOUT", "5"))  # sau după 5 secunde

# Asigură-te că directorul există
Path(STORAGE_FILE).parent.mkdir(parents=True, exist_ok=True)

consumer = Consumer({
    "bootstrap.servers": KAFKA,
    "group.id": "ms_storage",
    "auto.offset.reset": "earliest"
})

consumer.subscribe([IN_TOPIC])

print(f"[ms_storage] Listening on {IN_TOPIC}...")
print(f"[ms_storage] Storing to {STORAGE_FILE}")
print(f"[ms_storage] Batch size: {BATCH_SIZE}, timeout: {BATCH_TIMEOUT}s")

# Încarcă datele existente
if os.path.exists(STORAGE_FILE):
    with open(STORAGE_FILE, "r", encoding="utf-8") as f:
        cases = json.load(f)
else:
    cases = []

# Index pentru deduplicare rapidă
seen_keys = {c.get("dedup_key") for c in cases if c.get("dedup_key")}

# Batching state
pending_count = 0
last_flush_time = time.time()


def flush_to_disk():
    """Scrie datele pe disc"""
    global pending_count, last_flush_time

    if pending_count == 0:
        return

    with open(STORAGE_FILE, "w", encoding="utf-8") as f:
        json.dump(cases, f, ensure_ascii=False, indent=2)

    print(f"[FLUSH] Wrote {pending_count} cases to disk (total: {len(cases)})")
    pending_count = 0
    last_flush_time = time.time()


while True:
    msg = consumer.poll(1.0)

    # Check pentru timeout flush
    if time.time() - last_flush_time >= BATCH_TIMEOUT and pending_count > 0:
        flush_to_disk()

    if msg is None:
        continue

    if msg.error():
        print(f"[ERROR] {msg.error()}")
        continue

    event = json.loads(msg.value().decode("utf-8"))
    dedup_key = event.get("dedup_key")

    # Evită duplicate
    if dedup_key and dedup_key in seen_keys:
        continue

    # Adaugă la listă (în memorie)
    cases.append(event)
    if dedup_key:
        seen_keys.add(dedup_key)

    pending_count += 1

    # Păstrează doar ultimele 10000 de cazuri pentru a nu umple memoria
    if len(cases) > 10000:
        cases = cases[-10000:]
        seen_keys = {c.get("dedup_key") for c in cases if c.get("dedup_key")}

    # Flush dacă am atins batch size
    if pending_count >= BATCH_SIZE:
        flush_to_disk()
