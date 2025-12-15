import hashlib

REQUIRED_FIELDS = ["instanta", "dosar", "data_pron", "pdf_url"]

def validate(event: dict) -> bool:
    """Validare minimă de schemă"""
    return all(event.get(f) for f in REQUIRED_FIELDS)

def normalize(event: dict) -> dict:
    """Normalizare câmpuri text"""
    for k, v in event.items():
        if isinstance(v, str):
            event[k] = v.strip()
    return event

def dedup_key(event: dict) -> str:
    """Cheie unică pentru deduplicare"""
    base = f"{event.get('pdf_url')}|{event.get('dosar')}|{event.get('data_pron')}"
    return hashlib.sha256(base.encode("utf-8")).hexdigest()
