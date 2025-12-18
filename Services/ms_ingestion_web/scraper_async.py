import asyncio
from urllib.parse import urljoin

import httpx
from bs4 import BeautifulSoup

BASE_URL = "https://instante.justice.md"
LIST_URL = BASE_URL + "/ro/hotaririle-instantei"


async def fetch_page(client: httpx.AsyncClient, date_range: str, page: int) -> list[dict]:
    params = {"date": date_range, "page": page}
    r = await client.get(LIST_URL, params=params)
    r.raise_for_status()

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

        # Parsează toate cele 10 coloane din tabel:
        # 0: Instanță, 1: Dosar, 2: Denumire, 3: Data pronunțării, 4: Data înregistrării
        # 5: Data publicării, 6: Tip dosar, 7: Tematica, 8: Judecător, 9: PDF
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


async def scrape_async(date_range: str, max_pages: int = 200, concurrency: int = 6) -> list[dict]:
    """
    - Concurrency = câte pagini în paralel.
    - max_pages = limită de siguranță (ca să nu ruleze infinit).
    """
    limits = httpx.Limits(max_connections=concurrency, max_keepalive_connections=concurrency)
    timeout = httpx.Timeout(60.0)
    headers = {"User-Agent": "Mozilla/5.0"}

    sem = asyncio.Semaphore(concurrency)
    results: list[dict] = []

    async with httpx.AsyncClient(headers=headers, timeout=timeout, limits=limits) as client:

        async def guarded(page: int):
            async with sem:
                return await fetch_page(client, date_range, page)

        page = 1
        while page <= max_pages:
            batch_pages = list(range(page, min(page + concurrency, max_pages + 1)))
            batch = await asyncio.gather(*(guarded(p) for p in batch_pages))

            # oprește când prima pagină “goală” apare în batch
            stop = False
            for items in batch:
                if not items:
                    stop = True
                else:
                    results.extend(items)

            if stop:
                break

            page += concurrency

    return results
