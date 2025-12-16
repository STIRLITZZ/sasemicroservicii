import asyncio
import uuid
import os
from fastapi import FastAPI, BackgroundTasks
from pydantic import BaseModel

from scraper_async import scrape_async
from producer import make_producer, send

app = FastAPI()

JOBS: dict[str, dict] = {}
KAFKA = os.getenv("KAFKA_BOOTSTRAP", "kafka:9092")
producer = make_producer(KAFKA)

class JobStart(BaseModel):
    date_range: str

@app.get("/health")
def health():
    return {"ok": True}

@app.post("/run")
async def run(date_range: str):
    """
    Nu mai procesează aici “greu”.
    Pornește job și întoarce imediat job_id.
    """
    job_id = str(uuid.uuid4())
    JOBS[job_id] = {"status": "queued", "count": 0, "error": None}

    async def worker():
        try:
            JOBS[job_id]["status"] = "running"
            items = await scrape_async(date_range=date_range, concurrency=6)

            # Publică fiecare item în Kafka pentru procesare
            for item in items:
                send(producer, "court.raw", item)

            # Asigură-te că toate mesajele sunt trimise
            producer.flush()

            JOBS[job_id]["status"] = "done"
            JOBS[job_id]["count"] = len(items)
            JOBS[job_id]["result"] = items[:500]  # limită pentru UI
        except Exception as e:
            JOBS[job_id]["status"] = "error"
            JOBS[job_id]["error"] = str(e)

    # rulează în fundal (fără să blochezi requestul)
    asyncio.create_task(worker())

    return {"job_id": job_id, "status": "queued"}

@app.get("/jobs/{job_id}")
def job_status(job_id: str):
    return JOBS.get(job_id, {"status": "not_found"})
