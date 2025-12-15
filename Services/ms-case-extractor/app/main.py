from fastapi import FastAPI, UploadFile, File, HTTPException
from fastapi.responses import JSONResponse
from .extractor import extract_case

app = FastAPI(
    title="MS Case Extractor",
    version="0.1.0",
    description="Extrage metadate + indicatori din TXT-uri obținute din PDF-uri (hotărâri/sentințe)."
)

@app.get("/health")
def health():
    return {"status": "ok"}

@app.post("/extract")
async def extract(file: UploadFile = File(...)):
    if not file.filename:
        raise HTTPException(status_code=400, detail="Lipsește filename")

    # acceptă .txt; dacă vrei și .pdf, putem adăuga pdfplumber ulterior
    if not file.filename.lower().endswith(".txt"):
        raise HTTPException(status_code=415, detail="Doar .txt este acceptat (TXT extras din PDF).")

    content = await file.read()
    try:
        text = content.decode("utf-8", errors="ignore")
    except Exception:
        text = content.decode("latin-1", errors="ignore")

    result = extract_case(text, filename=file.filename)
    return JSONResponse(content=result.model_dump())
