#!/usr/bin/env python3
"""
Async PDF consumer - procesează multiple PDF-uri în paralel
"""
import json
import os
import asyncio
from pathlib import Path
from confluent_kafka import Consumer
from pdf_async import download_pdf_async, extract_text
from storage import pdf_path, txt_path
from producer import make_producer, send

KAFKA = os.getenv("KAFKA_BOOTSTRAP", "kafka:9092")
CONCURRENCY = int(os.getenv("PDF_CONCURRENCY", "5"))  # Procesează 5 PDF-uri în paralel

consumer = Consumer({
    "bootstrap.servers": KAFKA,
    "group.id": "ms_pdftext",
    "auto.offset.reset": "earliest"
})

producer = make_producer(KAFKA)
consumer.subscribe(["court.validated"])

print(f"[ms_pdftext] Starting with concurrency={CONCURRENCY}")

# Queue pentru batch processing
pending_tasks = []
semaphore = asyncio.Semaphore(CONCURRENCY)


async def process_event(event: dict):
    """Procesează un eveniment: download PDF + extract text + publish"""
    async with semaphore:
        try:
            pdf_file = pdf_path(event)

            # Creează directorul dacă nu există
            Path(pdf_file).parent.mkdir(parents=True, exist_ok=True)

            # Download PDF dacă nu există
            if not os.path.exists(pdf_file):
                await download_pdf_async(event["pdf_url"], pdf_file)

            # Extract text (sync, dar rapid)
            text = extract_text(pdf_file)

            # Salvează text
            txt_file = txt_path(event)
            Path(txt_file).parent.mkdir(parents=True, exist_ok=True)

            async with asyncio.Lock():  # Prevent race conditions on file writes
                with open(txt_file, "w", encoding="utf-8") as f:
                    f.write(text)

            # Publică rezultatul - păstrează TOATE datele din event original
            out = {
                **event,  # Include tot: instanta, dosar, denumire, tematica, judecator, tip_dosar, etc.
                "pdf_path": pdf_file,
                "txt_path": txt_file,
                "text_chars": len(text),
                "status": "text_extracted"
            }

            send(producer, "court.text", out)
            producer.poll(0)  # Trigger callbacks

            print(f"[OK] Processed: {event.get('dosar', '?')}")

        except Exception as e:
            print(f"[ERROR] Failed to process {event.get('dosar', '?')}: {e}")


async def worker():
    """Worker async care procesează evenimente din Kafka"""
    global pending_tasks

    while True:
        # Poll Kafka
        msg = consumer.poll(0.1)

        if msg is None:
            # Dacă avem tasks pending, așteaptă-le
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

        # Parsează eveniment
        event = json.loads(msg.value().decode("utf-8"))

        # Creează task pentru procesare
        task = asyncio.create_task(process_event(event))
        pending_tasks.append(task)

        # Limitează dimensiunea queue-ului
        if len(pending_tasks) >= CONCURRENCY * 2:
            done, pending_tasks = await asyncio.wait(
                pending_tasks,
                return_when=asyncio.FIRST_COMPLETED
            )
            pending_tasks = list(pending_tasks)


if __name__ == "__main__":
    asyncio.run(worker())
