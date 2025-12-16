#!/usr/bin/env python3
"""
Async Kafka consumer pentru ms-case-extractor.
Procesează multiple fișiere în paralel pentru performanță mai bună.
"""

import json
import os
import asyncio
from confluent_kafka import Consumer

from app.extractor import extract_case


KAFKA = os.getenv("KAFKA_BOOTSTRAP", "kafka:9092")
IN_TOPIC = "court.text"
OUT_TOPIC = "court.enriched"
CONCURRENCY = int(os.getenv("EXTRACTOR_CONCURRENCY", "10"))  # 10 fișiere în paralel


def make_producer(bootstrap_servers: str):
    from confluent_kafka import Producer
    return Producer({"bootstrap.servers": bootstrap_servers})


def send(producer, topic: str, event: dict):
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

print(f"[ms-case-extractor] Listening on {IN_TOPIC}")
print(f"[ms-case-extractor] Concurrency: {CONCURRENCY}")

semaphore = asyncio.Semaphore(CONCURRENCY)
pending_tasks = []


async def process_event(event: dict):
    """Procesează un eveniment: citește text + extrage metadate"""
    async with semaphore:
        txt_path = event.get("txt_path")
        if not txt_path or not os.path.exists(txt_path):
            print(f"[SKIP] Missing txt_path or file not found: {txt_path}")
            return

        try:
            # Citire async cu aiofiles
            try:
                import aiofiles
                async with aiofiles.open(txt_path, "r", encoding="utf-8") as f:
                    text = await f.read()
            except ImportError:
                # Fallback la sync dacă aiofiles nu e instalat
                with open(txt_path, "r", encoding="utf-8") as f:
                    text = f.read()

            # Extracție metadate (sync, dar rapid - doar regex)
            result = extract_case(text, filename=txt_path)
            extracted = result.model_dump()

            # Combină cu informații din event anterior
            enriched = {
                **event,
                "extracted": extracted,
                "status": "enriched"
            }

            send(producer, OUT_TOPIC, enriched)
            producer.flush()

            print(f"[OK] Enriched: {event.get('dosar', '?')}")

        except Exception as e:
            print(f"[ERROR] Extraction failed for {txt_path}: {e}")


async def worker():
    """Worker async care procesează evenimente din Kafka"""
    global pending_tasks

    while True:
        msg = consumer.poll(0.1)

        if msg is None:
            # Așteaptă tasks pending
            if pending_tasks:
                done, pending_tasks = await asyncio.wait(
                    pending_tasks,
                    timeout=1.0,
                    return_when=asyncio.FIRST_COMPLETED
                )
                pending_tasks = list(pending_tasks)
            else:
                await asyncio.sleep(0.1)
            continue

        if msg.error():
            print(f"[ERROR] {msg.error()}")
            continue

        event = json.loads(msg.value().decode("utf-8"))

        # Creează task
        task = asyncio.create_task(process_event(event))
        pending_tasks.append(task)

        # Limitează queue
        if len(pending_tasks) >= CONCURRENCY * 2:
            done, pending_tasks = await asyncio.wait(
                pending_tasks,
                return_when=asyncio.FIRST_COMPLETED
            )
            pending_tasks = list(pending_tasks)


if __name__ == "__main__":
    asyncio.run(worker())
