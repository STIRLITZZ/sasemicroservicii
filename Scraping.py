import requests, time
from bs4 import BeautifulSoup

URL = "https://instante.justice.md/ro/hotaririle-instantei"

params = {
    "Instnace": "All",
    "date": "2025-12-06 TO 2025-12-12",
    "page": 1
}

s = requests.Session()
s.headers["User-Agent"] = "Mozilla/5.0"

while True:
    r = s.get(URL, params=params)
    soup = BeautifulSoup(r.text, "html.parser")
    table = soup.find("table")
    if not table:
        break

    rows = table.find_all("tr")[1:]
    if not rows:
        break

    for tr in rows:
        tds = tr.find_all("td")
        print({
            "instanta": tds[0].text.strip(),
            "dosar": tds[1].text.strip(),
            "denumire": tds[2].text.strip(),
            "data": tds[3].text.strip()
        })

    params["page"] += 1
    time.sleep(1)
