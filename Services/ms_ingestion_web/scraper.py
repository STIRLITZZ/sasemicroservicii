import time
from urllib.parse import urljoin
import requests
from bs4 import BeautifulSoup

BASE_URL = "https://instante.justice.md"
LIST_URL = BASE_URL + "/ro/hotaririle-instantei"


def scrape(date_range: str):
    session = requests.Session()
    session.headers["User-Agent"] = "Mozilla/5.0"

    page = 1
    while True:
        params = {
            "date": date_range,
            "page": page
        }

        r = session.get(LIST_URL, params=params, timeout=60)
        r.raise_for_status()

        soup = BeautifulSoup(r.text, "html.parser")
        table = soup.find("table")
        if not table:
            break

        rows = table.find_all("tr")[1:]
        if not rows:
            break

        for tr in rows:
            tds = tr.find_all("td")
            if len(tds) < 4:
                continue

            pdf_a = tds[-1].find("a", href=True)
            if not pdf_a:
                continue

            yield {
                "source": "instante.justice.md",
                "instanta": tds[0].get_text(strip=True),
                "dosar": tds[1].get_text(strip=True),
                "denumire": tds[2].get_text(" ", strip=True),
                "data_pron": tds[3].get_text(strip=True),
                "pdf_url": urljoin(BASE_URL + "/", pdf_a["href"].strip())
            }

        page += 1
        time.sleep(1)
