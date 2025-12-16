#!/usr/bin/env python3
"""
Storage consumer - salvează datele enriched pentru a fi afișate în UI.
Citește din 'court.enriched' și salvează într-un JSON file.
"""

import json
import os
from confluent_kafka import Consumer
from pathlib import Path

KAFKA = os.getenv("KAFKA_BOOTSTRAP", "kafka:9092")
IN_TOPIC = "court.enriched"
STORAGE_FILE = "/data/enriched/cases.json"

# Asigură-te că directorul există
Path(STORAGE_FILE).parent.mkdir(parents=True, exist_ok=True)

consumer = Consumer({
    "bootstrap.servers": KAFKA,
    "group.id": "ms_storage",
    "auto.offset.reset": "earliest"
})

consumer.subscribe([IN_TOPIC])

print(f"[ms_storage consumer] Listening on {IN_TOPIC}...")
print(f"[ms_storage consumer] Storing to {STORAGE_FILE}")

# Încarcă datele existente
if os.path.exists(STORAGE_FILE):
    with open(STORAGE_FILE, "r", encoding="utf-8") as f:
        cases = json.load(f)
else:
    cases = []

# Index pentru deduplicare rapidă
seen_keys = {c.get("dedup_key") for c in cases if c.get("dedup_key")}

while True:
    msg = consumer.poll(1.0)
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

    # Adaugă la listă
    cases.append(event)
    if dedup_key:
        seen_keys.add(dedup_key)

    # Salvează (append-only, cu limite)
    # Păstrează doar ultimele 10000 de cazuri pentru a nu umple memoria
    if len(cases) > 10000:
        cases = cases[-10000:]
        seen_keys = {c.get("dedup_key") for c in cases if c.get("dedup_key")}

    # Scrie în fișier
    with open(STORAGE_FILE, "w", encoding="utf-8") as f:
        json.dump(cases, f, ensure_ascii=False, indent=2)

    print(f"[OK] Stored case: {event.get('dosar', '?')} (total: {len(cases)})")
