import requests
from bs4 import BeautifulSoup

URL = "https://instante.justice.md/ro/hotaririle-instantei"
params = {"date": "2025-12-06 TO 2025-12-12", "page": 1}

s = requests.Session()
s.headers["User-Agent"] = "Mozilla/5.0"

r = s.get(URL, params=params, timeout=60)
r.raise_for_status()

print("Final URL:", r.url)
print("Status:", r.status_code)
print("HTML length:", len(r.text))

soup = BeautifulSoup(r.text, "html.parser")
table = soup.find("table")
print("Table found:", bool(table))

tr = table.find_all("tr")[1]
tds = tr.find_all("td")
print("TD count:", len(tds))

last_td = tds[-1]
print("\n--- LAST TD (raw html) ---")
print(last_td.prettify())

print("\n--- LINKS IN ROW ---")
for a in tr.find_all("a", href=True):
    print("a.text=", a.get_text(strip=True), " href=", a["href"])

