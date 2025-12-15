import os
import re
import time
from urllib.parse import urljoin

import requests
from bs4 import BeautifulSoup

# pip install pypdf
from pypdf import PdfReader

BASE_URL = "https://instante.justice.md"
LIST_URL = BASE_URL + "/ro/hotaririle-instantei"

params = {
    "date": "2025-12-06 TO 2025-12-12",
    "page": 1
}

OUT_PDF = "hotariri_pdf"
OUT_TXT = "hotariri_txt"
os.makedirs(OUT_PDF, exist_ok=True)
os.makedirs(OUT_TXT, exist_ok=True)

s = requests.Session()
s.headers["User-Agent"] = "Mozilla/5.0"


def safe_name(x: str) -> str:
    x = re.sub(r"[^\w\s\-\.]", "_", x, flags=re.UNICODE)
    x = re.sub(r"\s+", " ", x).strip()
    return x[:180]


def download_file(url: str, path: str) -> None:
    with s.get(url, stream=True, timeout=60) as r:
        r.raise_for_status()
        with open(path, "wb") as f:
            for chunk in r.iter_content(chunk_size=1024 * 128):
                if chunk:
                    f.write(chunk)


def extract_text_from_pdf(pdf_path: str) -> str:
    reader = PdfReader(pdf_path)
    parts = []
    for page in reader.pages:
        parts.append(page.extract_text() or "")
    return "\n".join(parts).strip()


def get_pdf_url_from_row(tr) -> str | None:
    tds = tr.find_all("td")
    if not tds:
        return None

    # ultima coloană = "Act judecătoresc" (PDF)
    last_td = tds[-1]
    a = last_td.find("a", href=True)
    if not a:
        return None

    href = a["href"].strip()
    return urljoin(BASE_URL + "/", href)  # important: BASE_URL + "/"


page = 1
seen = set()

while True:
    params["page"] = page
    r = s.get(LIST_URL, params=params, timeout=60)
    r.raise_for_status()

    soup = BeautifulSoup(r.text, "html.parser")
    table = soup.find("table")
    if not table:
        print("Nu am găsit tabelul. Stop.")
        break

    rows = table.find_all("tr")[1:]
    if not rows:
        print("Nu mai sunt rânduri. Stop.")
        break

    print(f"\n=== Page {page} ===")

    for tr in rows:
        tds = tr.find_all("td")
        if len(tds) < 4:
            continue

        instanta = tds[0].get_text(strip=True)
        dosar = tds[1].get_text(strip=True)
        denumire = tds[2].get_text(" ", strip=True)
        data_pron = tds[3].get_text(strip=True)

        pdf_url = get_pdf_url_from_row(tr)
        print(f"- {instanta} | {dosar} | {data_pron} | pdf_url={pdf_url}")

        if not pdf_url or pdf_url in seen:
            continue
        seen.add(pdf_url)

        pdf_filename = safe_name(f"{data_pron}__{instanta}__{dosar}.pdf")
        pdf_path = os.path.join(OUT_PDF, pdf_filename)

        if not os.path.exists(pdf_path):
            download_file(pdf_url, pdf_path)
            time.sleep(0.5)

        text = extract_text_from_pdf(pdf_path)
        txt_filename = safe_name(f"{data_pron}__{instanta}__{dosar}.txt")
        txt_path = os.path.join(OUT_TXT, txt_filename)

        with open(txt_path, "w", encoding="utf-8") as f:
            f.write(text)

        print(f"  -> saved: {pdf_path}")
        print(f"  -> text chars: {len(text)} -> {txt_path}")

    # trece la următoarea pagină
    page += 1
    time.sleep(1)

print("\nGata.")
