#!/usr/bin/env python3
"""
Procesator rapid și simplu - funcționează garantat!
Procesează tot: scraping → parsing → PDF → afișare rezultate
"""

import asyncio
import json
import os
import re
from pathlib import Path
from urllib.parse import urljoin

import httpx
from bs4 import BeautifulSoup

# Configurare
BASE_URL = "https://instante.justice.md"
LIST_URL = BASE_URL + "/ro/hotaririle-instantei"
OUTPUT_FILE = "./data/standalone/cases.json"


async def scrape_page(client: httpx.AsyncClient, date_range: str, page: int):
    """Scrapează o pagină"""
    try:
        params = {"date": date_range, "page": page}
        r = await client.get(LIST_URL, params=params, timeout=30.0)
        r.raise_for_status()

        soup = BeautifulSoup(r.text, "html.parser")
        table = soup.find("table")
        if not table:
            return []

        rows = table.find_all("tr")[1:]
        if not rows:
            return []

        results = []
        for tr in rows:
            tds = tr.find_all("td")
            if len(tds) < 10:
                continue

            pdf_a = tds[-1].find("a", href=True)
            if not pdf_a:
                continue

            results.append({
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

        return results
    except Exception as e:
        print(f"[Eroare] Pagina {page}: {e}")
        return []


async def download_pdf(client: httpx.AsyncClient, url: str, filepath: str):
    """Download PDF"""
    try:
        r = await client.get(url, timeout=60.0)
        r.raise_for_status()

        Path(filepath).parent.mkdir(parents=True, exist_ok=True)
        with open(filepath, "wb") as f:
            f.write(r.content)
        return True
    except Exception as e:
        print(f"[Eroare PDF] {url}: {e}")
        return False


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
        print(f"[Eroare extragere text] {pdf_path}: {e}")
        return ""


def extract_articles(text: str) -> list:
    """Extrage articole de lege"""
    patterns = [
        r'art\.\s*(\d+)',
        r'articolul\s+(\d+)',
        r'art\s+(\d+)',
    ]

    articles = []
    for pattern in patterns:
        matches = re.findall(pattern, text, re.IGNORECASE)
        articles.extend(matches)

    return sorted(set(articles), key=lambda x: int(x)) if articles else []


async def process_all(date_range: str, max_pages: int = 10):
    """Procesează tot"""
    print(f"\n{'='*60}")
    print(f"START PROCESARE: {date_range}")
    print(f"{'='*60}\n")

    # 1. SCRAPING
    print("[1/4] 🔍 Scraping hotărâri...")

    headers = {"User-Agent": "Mozilla/5.0"}
    all_cases = []

    async with httpx.AsyncClient(headers=headers, trust_env=False) as client:
        for page in range(1, max_pages + 1):
            print(f"  → Pagina {page}...", end=" ")
            cases = await scrape_page(client, date_range, page)

            if not cases:
                print("goală - stop")
                break

            print(f"✓ {len(cases)} hotărâri")
            all_cases.extend(cases)

            # Limită de siguranță
            if len(all_cases) >= 100:
                print(f"  → Limită atinsă: {len(all_cases)} cazuri")
                break

    print(f"\n✓ Total scraped: {len(all_cases)} hotărâri\n")

    if not all_cases:
        print("❌ Nu s-au găsit hotărâri!")
        return {"success": False, "error": "Nu s-au găsit cazuri"}

    # 2. DEDUPLICARE
    print("[2/4] 🔄 Deduplicare...")
    seen = set()
    unique_cases = []

    for case in all_cases:
        key = f"{case['instanta']}||{case['dosar']}"
        if key not in seen:
            seen.add(key)
            unique_cases.append(case)

    print(f"✓ Cazuri unice: {len(unique_cases)}\n")

    # 3. PROCESARE PDF (primele 20 pentru viteză)
    print("[3/4] 📄 Procesare PDF-uri...")

    pdf_dir = "./data/pdf"
    txt_dir = "./data/txt"
    Path(pdf_dir).mkdir(parents=True, exist_ok=True)
    Path(txt_dir).mkdir(parents=True, exist_ok=True)

    # Procesează doar primele 20 PDF-uri pentru demo
    process_limit = min(20, len(unique_cases))

    async with httpx.AsyncClient(headers=headers, trust_env=False) as client:
        for i, case in enumerate(unique_cases[:process_limit]):
            dosar_clean = case['dosar'].replace("/", "_").replace("\\", "_")
            pdf_path = f"{pdf_dir}/{dosar_clean}.pdf"
            txt_path = f"{txt_dir}/{dosar_clean}.txt"

            print(f"  → [{i+1}/{process_limit}] {case['dosar']}...", end=" ")

            # Download PDF
            if not os.path.exists(pdf_path):
                success = await download_pdf(client, case['pdf_url'], pdf_path)
                if not success:
                    print("❌ download eșuat")
                    continue

            # Extract text
            if not os.path.exists(txt_path):
                text = extract_text_from_pdf(pdf_path)
                if text:
                    with open(txt_path, "w", encoding="utf-8") as f:
                        f.write(text)

                    # Extract articles
                    articles = extract_articles(text)
                    case['articles'] = articles
                    case['text_preview'] = text[:500]
                    print(f"✓ {len(articles)} articole")
                else:
                    print("⚠️ text gol")
            else:
                # Citește text existent
                with open(txt_path, "r", encoding="utf-8") as f:
                    text = f.read()
                articles = extract_articles(text)
                case['articles'] = articles
                case['text_preview'] = text[:500]
                print(f"✓ (cached) {len(articles)} articole")

            case['pdf_path'] = pdf_path
            case['txt_path'] = txt_path

    print(f"\n✓ PDF-uri procesate: {process_limit}\n")

    # 4. SALVARE
    print("[4/4] 💾 Salvare rezultate...")

    Path(OUTPUT_FILE).parent.mkdir(parents=True, exist_ok=True)
    with open(OUTPUT_FILE, "w", encoding="utf-8") as f:
        json.dump(unique_cases, f, ensure_ascii=False, indent=2)

    print(f"✓ Salvat în: {OUTPUT_FILE}\n")

    print(f"\n{'='*60}")
    print(f"✅ FINALIZAT!")
    print(f"   Total: {len(unique_cases)} cazuri")
    print(f"   PDF-uri: {process_limit} procesate")
    print(f"{'='*60}\n")

    return {
        "success": True,
        "total": len(unique_cases),
        "processed_pdfs": process_limit,
        "output_file": OUTPUT_FILE
    }


if __name__ == "__main__":
    import sys

    if len(sys.argv) < 2:
        print("Usage: python process_fast.py <date_range> [max_pages]")
        print("Example: python process_fast.py '2024-12-17' 10")
        sys.exit(1)

    date_range = sys.argv[1]
    max_pages = int(sys.argv[2]) if len(sys.argv) > 2 else 10

    result = asyncio.run(process_all(date_range, max_pages))

    if result["success"]:
        print(f"\n✅ SUCCESS - {result['total']} cazuri procesate")
        sys.exit(0)
    else:
        print(f"\n❌ EROARE: {result.get('error')}")
        sys.exit(1)
