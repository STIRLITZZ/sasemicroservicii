"""
Async PDF download și text extraction
"""
import httpx
from pypdf import PdfReader
from pathlib import Path


async def download_pdf_async(url: str, path: str):
    """Download PDF asincron cu httpx"""
    timeout = httpx.Timeout(120.0, connect=30.0)
    headers = {"User-Agent": "Mozilla/5.0"}

    async with httpx.AsyncClient(timeout=timeout, headers=headers) as client:
        async with client.stream("GET", url) as response:
            response.raise_for_status()

            # Creează directorul dacă nu există
            Path(path).parent.mkdir(parents=True, exist_ok=True)

            with open(path, "wb") as f:
                async for chunk in response.aiter_bytes(chunk_size=128 * 1024):
                    if chunk:
                        f.write(chunk)


def extract_text(pdf_path: str) -> str:
    """Extrage text din PDF (sync, PyPDF nu suportă async)"""
    reader = PdfReader(pdf_path)
    return "\n".join(page.extract_text() or "" for page in reader.pages)
