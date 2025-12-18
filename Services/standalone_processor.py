#!/usr/bin/env python3
"""
Standalone processor - rulează tot pipeline-ul local fără Kafka/Docker.
Scraping → Parsing → Extraction → Storage, tot în memorie.
"""

import asyncio
import json
import os
import re
from pathlib import Path
from typing import Optional
from urllib.parse import urljoin

import httpx
from bs4 import BeautifulSoup


# ============= SCRAPING (din ms_ingestion_web) =============

BASE_URL = "https://instante.justice.md"
LIST_URL = BASE_URL + "/ro/hotaririle-instantei"


async def scrape_page(client: httpx.AsyncClient, date_range: str, page: int) -> list[dict]:
    """Scrapează o pagină de hotărâri"""
    params = {"date": date_range, "page": page}
    try:
        r = await client.get(LIST_URL, params=params)
        r.raise_for_status()
    except Exception as e:
        print(f"[scraper] Eroare la pagina {page}: {e}")
        return []

    soup = BeautifulSoup(r.text, "html.parser")
    table = soup.find("table")
    if not table:
        return []

    rows = table.find_all("tr")[1:]
    if not rows:
        return []

    out = []
    for tr in rows:
        tds = tr.find_all("td")
        if len(tds) < 10:
            continue

        pdf_a = tds[-1].find("a", href=True)
        if not pdf_a:
            continue

        out.append({
            "source": "instante.justice.md",
            "instanta": tds[0].get_text(strip=True),
            "dosar": tds[1].get_text(strip=True),
            "denumire": tds[2].get_text(" ", strip=True),
            "data_pron": tds[3].get_text(strip=True),
            "data_inreg": tds[4].get_text(strip=True),
            "data_publ": tds[5].get_text(strip=True),
            "tip_dosar": tds[6].get_text(strip=True),
            "tematica": tds[7].get_text(strip=True),
            "judecator": tds[8].get_text(strip=True),
            "pdf_url": urljoin(BASE_URL + "/", pdf_a["href"].strip())
        })

    return out


async def scrape_all(date_range: str, max_pages: int = 20) -> list[dict]:
    """Scrapează toate paginile pentru un interval de date (paralel pentru viteză)"""
    print(f"[standalone] Start scraping RAPID pentru {date_range}")

    headers = {"User-Agent": "Mozilla/5.0"}
    timeout = httpx.Timeout(30.0)  # Reduced timeout
    limits = httpx.Limits(max_connections=10, max_keepalive_connections=10)

    results = []
    concurrency = 5  # Procesează 5 pagini simultan

    async with httpx.AsyncClient(headers=headers, timeout=timeout, limits=limits, trust_env=False) as client:
        page = 1
        while page <= max_pages:
            # Procesează 5 pagini în paralel
            batch_pages = list(range(page, min(page + concurrency, max_pages + 1)))

            # Fetch toate paginile din batch simultan
            tasks = [scrape_page(client, date_range, p) for p in batch_pages]
            batch_results = await asyncio.gather(*tasks)

            # Verifică dacă am găsit pagini goale
            has_empty = False
            for page_num, items in zip(batch_pages, batch_results):
                if not items:
                    print(f"[standalone] Pagina {page_num} goală - stop")
                    has_empty = True
                    break
                else:
                    print(f"[standalone] Pagina {page_num}: {len(items)} hotărâri")
                    results.extend(items)

            if has_empty:
                break

            page += concurrency

    print(f"[standalone] Total scraped: {len(results)} hotărâri")
    return results


# ============= VALIDATION & DEDUPLICATION (din ms_dataquality) =============

def validate(event: dict) -> bool:
    """Validează că evenimentul are câmpurile necesare"""
    required = ["dosar", "pdf_url"]
    return all(event.get(k) for k in required)


def normalize(event: dict) -> dict:
    """Normalizează datele"""
    # Curăță spații
    for key in ["dosar", "instanta", "denumire", "judecator"]:
        if key in event and event[key]:
            event[key] = " ".join(event[key].split())
    return event


def dedup_key(event: dict) -> str:
    """Generează cheie unică pentru deduplicare"""
    dosar = event.get("dosar", "").strip().lower()
    instanta = event.get("instanta", "").strip().lower()
    return f"{instanta}||{dosar}"


def validate_and_dedup(cases: list[dict]) -> list[dict]:
    """Validare și deduplicare"""
    print(f"[standalone] Validare și deduplicare...")

    valid = []
    seen = set()

    for case in cases:
        if not validate(case):
            continue

        case = normalize(case)
        key = dedup_key(case)

        if key in seen:
            continue

        seen.add(key)
        case["dedup_key"] = key
        valid.append(case)

    print(f"[standalone] După validare: {len(valid)}/{len(cases)} cazuri")
    return valid


# ============= PDF TEXT EXTRACTION (din ms_pdftext) =============

async def download_pdf(client: httpx.AsyncClient, url: str, filepath: str):
    """Download PDF"""
    try:
        r = await client.get(url)
        r.raise_for_status()

        Path(filepath).parent.mkdir(parents=True, exist_ok=True)
        with open(filepath, "wb") as f:
            f.write(r.content)
    except Exception as e:
        print(f"[standalone] Eroare download PDF {url}: {e}")
        raise


def extract_text_from_pdf(pdf_path: str) -> str:
    """Extrage text din PDF"""
    try:
        from pypdf import PdfReader
        reader = PdfReader(pdf_path)
        text = ""
        for page in reader.pages:
            text += page.extract_text() + "\n"
        return text
    except Exception as e:
        print(f"[standalone] Eroare extragere text din {pdf_path}: {e}")
        return ""


async def process_pdfs(cases: list[dict], pdf_dir: str = "./data/pdf", txt_dir: str = "./data/txt") -> list[dict]:
    """Download și extrage text din toate PDF-urile"""
    print(f"[standalone] Procesare PDF-uri...")

    headers = {"User-Agent": "Mozilla/5.0"}
    timeout = httpx.Timeout(120.0)

    async with httpx.AsyncClient(headers=headers, timeout=timeout, trust_env=False) as client:
        for i, case in enumerate(cases):
            dosar = case.get("dosar", "unknown").replace("/", "_")
            pdf_path = f"{pdf_dir}/{dosar}.pdf"
            txt_path = f"{txt_dir}/{dosar}.txt"

            try:
                # Download PDF dacă nu există
                if not os.path.exists(pdf_path):
                    await download_pdf(client, case["pdf_url"], pdf_path)

                # Extract text
                text = extract_text_from_pdf(pdf_path)

                # Salvează text
                Path(txt_path).parent.mkdir(parents=True, exist_ok=True)
                with open(txt_path, "w", encoding="utf-8") as f:
                    f.write(text)

                case["pdf_path"] = pdf_path
                case["txt_path"] = txt_path
                case["text_chars"] = len(text)

                if (i + 1) % 10 == 0:
                    print(f"[standalone] Procesat {i + 1}/{len(cases)} PDF-uri")

            except Exception as e:
                print(f"[standalone] Eroare procesare PDF pentru {case.get('dosar')}: {e}")
                case["pdf_error"] = str(e)

    print(f"[standalone] PDF-uri procesate: {len(cases)}")
    return cases


# ============= CASE EXTRACTION (din ms-case-extractor) =============

def extract_articles(text: str) -> list[str]:
    """Extrage articole de lege din text"""
    articles = []

    # Pattern pentru articole (ex: "art. 123", "art.123", "articolul 45")
    patterns = [
        r'art\.\s*(\d+)',
        r'articolul\s+(\d+)',
        r'art\s+(\d+)',
    ]

    for pattern in patterns:
        matches = re.findall(pattern, text, re.IGNORECASE)
        articles.extend(matches)

    # Deduplicare și sortare
    return sorted(set(articles), key=int)


def extract_metadata(case: dict) -> dict:
    """Extrage metadata din caz"""
    result = {
        "instanta": case.get("instanta", ""),
        "dosar": case.get("dosar", ""),
        "denumire": case.get("denumire", ""),
        "data_pronuntare": case.get("data_pron", ""),
        "data_inregistrare": case.get("data_inreg", ""),
        "data_publicare": case.get("data_publ", ""),
        "tip_dosar": case.get("tip_dosar", ""),
        "tematica": case.get("tematica", ""),
        "judecator": case.get("judecator", ""),
        "articole": []
    }

    # Extrage articole din text dacă există
    if case.get("txt_path") and os.path.exists(case["txt_path"]):
        try:
            with open(case["txt_path"], "r", encoding="utf-8") as f:
                text = f.read()
            result["articole"] = extract_articles(text)
        except Exception as e:
            print(f"[standalone] Eroare citire text pentru {case.get('dosar')}: {e}")

    return result


def enrich_cases(cases: list[dict]) -> list[dict]:
    """Enriched cases cu metadata extrasă"""
    print(f"[standalone] Extragere metadata...")

    enriched = []
    for case in cases:
        extracted = extract_metadata(case)

        enriched_case = {
            **case,
            "extracted": extracted,
            "status": "enriched"
        }
        enriched.append(enriched_case)

    print(f"[standalone] Metadata extrasă: {len(enriched)} cazuri")
    return enriched


# ============= MAIN PIPELINE =============

async def process_standalone(date_range: str, output_file: str = "./data/standalone/cases.json", max_pages: int = 20) -> dict:
    """
    Rulează tot pipeline-ul standalone:
    1. Scraping
    2. Validare & dedup
    3. Download PDF + extract text
    4. Extract metadata
    5. Salvează rezultate

    Returns: statistici despre procesare
    """
    try:
        # 1. Scraping
        cases = await scrape_all(date_range, max_pages)
        if not cases:
            return {
                "success": False,
                "error": "Nu s-au găsit cazuri pentru perioada specificată",
                "stats": {"scraped": 0, "validated": 0, "processed": 0, "enriched": 0}
            }

        # 2. Validare & dedup
        cases = validate_and_dedup(cases)
        validated_count = len(cases)

        # 3. PDF processing - DEZACTIVAT pentru viteză (foarte lent!)
        # Dacă vrei să procesezi și PDF-urile, decomentează linia de jos:
        # cases = await process_pdfs(cases)

        # 4. Extract metadata RAPID (folosește doar datele din tabel, NU PDF)
        cases = enrich_cases(cases)

        # 5. Salvează rezultate
        Path(output_file).parent.mkdir(parents=True, exist_ok=True)
        with open(output_file, "w", encoding="utf-8") as f:
            json.dump(cases, f, ensure_ascii=False, indent=2)

        stats = {
            "scraped": len(cases),
            "validated": validated_count,
            "processed": len(cases),
            "enriched": len(cases),
            "date_range": date_range,
            "output_file": output_file
        }

        print(f"[standalone] Procesare completă! Salvat în {output_file}")
        print(f"[standalone] Stats: {stats}")

        return {
            "success": True,
            "stats": stats,
            "cases": cases
        }

    except Exception as e:
        print(f"[standalone] EROARE în procesare: {e}")
        import traceback
        traceback.print_exc()
        return {
            "success": False,
            "error": str(e),
            "stats": {"scraped": 0, "validated": 0, "processed": 0, "enriched": 0}
        }


# ============= CLI =============

if __name__ == "__main__":
    import sys

    if len(sys.argv) < 2:
        print("Usage: python standalone_processor.py <date_range> [output_file] [max_pages]")
        print("Example: python standalone_processor.py '2024-12-18' ./data/standalone/cases.json 50")
        sys.exit(1)

    date_range = sys.argv[1]
    output_file = sys.argv[2] if len(sys.argv) > 2 else "./data/standalone/cases.json"
    max_pages = int(sys.argv[3]) if len(sys.argv) > 3 else 20  # Default 20 pagini pentru viteză

    result = asyncio.run(process_standalone(date_range, output_file, max_pages))

    if result["success"]:
        print(f"\n✓ SUCCESS! Procesate {result['stats']['enriched']} cazuri")
        sys.exit(0)
    else:
        print(f"\n✗ EROARE: {result.get('error', 'Unknown error')}")
        sys.exit(1)
