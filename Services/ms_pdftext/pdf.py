import requests
from pypdf import PdfReader

def download_pdf(session, url: str, path: str):
    with session.get(url, stream=True, timeout=60) as r:
        r.raise_for_status()
        with open(path, "wb") as f:
            for ch in r.iter_content(1024 * 128):
                if ch:
                    f.write(ch)

def extract_text(pdf_path: str) -> str:
    reader = PdfReader(pdf_path)
    return "\n".join(page.extract_text() or "" for page in reader.pages)
