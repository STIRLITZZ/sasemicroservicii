import asyncio
import uuid
import os
import httpx
from fastapi import FastAPI, BackgroundTasks
from pydantic import BaseModel

from scraper_async import scrape_async
from producer import make_producer, send

app = FastAPI()

JOBS: dict[str, dict] = {}
KAFKA = os.getenv("KAFKA_BOOTSTRAP", "kafka:9092")
DWH_URL = os.getenv("DWH_URL", "http://ms_dwh:8000")
producer = make_producer(KAFKA)

class JobStart(BaseModel):
    date_range: str


def parse_date_range(date_range: str) -> tuple[str, str]:
    """Parsează string-ul de interval și returnează (start_date, end_date)"""
    # Format: "2024-01-01" sau "2024-01-01 - 2024-01-31"
    if " - " in date_range:
        parts = date_range.split(" - ")
        return parts[0].strip(), parts[1].strip()
    else:
        # Dată unică - folosește aceeași pentru start și end
        return date_range.strip(), date_range.strip()


@app.get("/health")
def health():
    return {"ok": True}

@app.post("/run")
async def run(date_range: str):
    """
    Verifică dacă perioada a fost procesată, apoi pornește job.
    """
    job_id = str(uuid.uuid4())
    JOBS[job_id] = {"status": "queued", "count": 0, "error": None, "scraping_id": None}

    async def worker():
        scraping_id = None
        try:
            # Parse date range
            start_date, end_date = parse_date_range(date_range)

            # Verifică dacă perioada a fost deja procesată
            async with httpx.AsyncClient(timeout=10.0) as client:
                check_response = await client.get(
                    f"{DWH_URL}/dwh/scraping/check",
                    params={"start_date": start_date, "end_date": end_date}
                )

                if check_response.status_code == 200:
                    check_data = check_response.json()

                    # Dacă a fost deja procesat complet, skip
                    if check_data.get("processed") and check_data.get("scraping_info", {}).get("status") == "completed":
                        JOBS[job_id]["status"] = "skipped"
                        JOBS[job_id]["message"] = f"Perioada {date_range} a fost deja procesată"
                        JOBS[job_id]["scraping_info"] = check_data.get("scraping_info")
                        return

                # Înregistrează începutul scraping-ului
                record_response = await client.post(
                    f"{DWH_URL}/dwh/scraping/start",
                    params={
                        "date_range": date_range,
                        "start_date": start_date,
                        "end_date": end_date
                    }
                )

                if record_response.status_code == 200:
                    record_data = record_response.json()
                    scraping_id = record_data.get("scraping_id")
                    JOBS[job_id]["scraping_id"] = scraping_id

            # Rulează scraping-ul
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

            # Marchează scraping-ul ca fiind complet în DWH
            if scraping_id:
                async with httpx.AsyncClient(timeout=10.0) as client:
                    await client.post(
                        f"{DWH_URL}/dwh/scraping/complete",
                        params={
                            "scraping_id": scraping_id,
                            "total_scraped": len(items),
                            "total_processed": len(items)  # Va fi actualizat de consumer
                        }
                    )

        except Exception as e:
            JOBS[job_id]["status"] = "error"
            JOBS[job_id]["error"] = str(e)

    # rulează în fundal (fără să blochezi requestul)
    asyncio.create_task(worker())

    return {"job_id": job_id, "status": "queued"}

@app.get("/jobs/{job_id}")
def job_status(job_id: str):
    return JOBS.get(job_id, {"status": "not_found"})
