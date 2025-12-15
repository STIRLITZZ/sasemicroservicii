import re
from datetime import datetime
from typing import Tuple, Optional, List
from .models import CaseExtractResult

RO_MONTHS = {
    "ianuarie": 1, "februarie": 2, "martie": 3, "aprilie": 4, "mai": 5, "iunie": 6,
    "iulie": 7, "august": 8, "septembrie": 9, "octombrie": 10, "noiembrie": 11, "decembrie": 12
}

def _norm_spaces(s: str) -> str:
    s = s.replace("\u00a0", " ")
    s = re.sub(r"[ \t]+", " ", s)
    s = re.sub(r"\n{3,}", "\n\n", s)
    return s.strip()

def _parse_ro_date(text: str) -> Optional[str]:
    """
    Acceptă:
      - "15 decembrie 2025"
      - "17 octombrie 2025"
      - "12.01.2024" (mai rar în antet)
    Returnează ISO YYYY-MM-DD sau None.
    """
    m = re.search(r"\b(\d{1,2})\s+(ianuarie|februarie|martie|aprilie|mai|iunie|iulie|august|septembrie|octombrie|noiembrie|decembrie)\s+(\d{4})\b",
                  text, flags=re.IGNORECASE)
    if m:
        d = int(m.group(1))
        mo = RO_MONTHS[m.group(2).lower()]
        y = int(m.group(3))
        return datetime(y, mo, d).date().isoformat()

    m2 = re.search(r"\b(\d{2})\.(\d{2})\.(\d{4})\b", text)
    if m2:
        d, mo, y = int(m2.group(1)), int(m2.group(2)), int(m2.group(3))
        try:
            return datetime(y, mo, d).date().isoformat()
        except ValueError:
            return None
    return None

def _find_first(patterns: List[str], text: str, flags=0) -> Optional[str]:
    for p in patterns:
        m = re.search(p, text, flags)
        if m:
            val = m.group(1).strip()
            return re.sub(r"\s{2,}", " ", val)
    return None

def extract_case(text: str, filename: Optional[str] = None) -> CaseExtractResult:
    raw = text or ""
    t = _norm_spaces(raw)

    res = CaseExtractResult(source_filename=filename)

    # Doc type
    doc_type = _find_first(
        [r"\b(HOTĂRÂRE|SENTINȚĂ|ÎNCHEIERE)\b"],
        t,
        flags=re.IGNORECASE
    )
    if doc_type:
        res.doc_type = doc_type.upper()
        res.confidence["doc_type"] = 0.95
    else:
        res.warnings.append("Nu am găsit tipul documentului (SENTINȚĂ/HOTĂRÂRE/ÎNCHEIERE).")
        res.confidence["doc_type"] = 0.2

    # Dosar nr
    res.dosar_nr = _find_first(
        [
            r"\bDosar(?:ul)?\s+(?:judiciar\s+)?nr\.\s*([0-9]+[-–][0-9]+/[0-9]{4})\b",
            r"\bDosarul\s+nr\.\s*([0-9]+[-–][0-9]+/[0-9]{4})\b",
        ],
        t,
        flags=re.IGNORECASE
    )
    res.confidence["dosar_nr"] = 0.9 if res.dosar_nr else 0.3

    # PIGD id (uneori apare explicit)
    res.pigd_id = _find_first(
        [r"\bPIGD\s+([0-9]+[-–][0-9]+[-–][0-9]+[-–][0-9]+[-–][0-9]+)\b"],
        t,
        flags=re.IGNORECASE
    )
    if res.pigd_id:
        res.confidence["pigd_id"] = 0.9

    # Instanța + sediu
    res.instanta = _find_first(
        [
            r"\b(Judecătoria\s+[A-ZĂÂÎȘȚa-zăâîșț\- ]+)\b",
            r"\b(Curtea\s+de\s+Apel\s+[A-ZĂÂÎȘȚa-zăâîșț\- ]+)\b",
        ],
        t
    )
    res.sediu = _find_first(
        [r"\(\s*sediul\s+([A-ZĂÂÎȘȚa-zăâîșț\- ]+)\s*\)"],
        t,
        flags=re.IGNORECASE
    )

    # Localitate (în antet apare: "mun. Chișinău", "or. Căușeni", "orașul Sângerei")
    res.localitate = _find_first(
        [
            r"\b(mun\.\s*[A-ZĂÂÎȘȚ][A-Za-zĂÂÎȘȚăâîșț\- ]+)\b",
            r"\b(or\.\s*[A-ZĂÂÎȘȚ][A-Za-zĂÂÎȘȚăâîșț\- ]+)\b",
            r"\b(orașul\s+[A-ZĂÂÎȘȚ][A-Za-zĂÂÎȘȚăâîșț\- ]+)\b",
        ],
        t,
        flags=re.IGNORECASE
    )

    # Data pronunțării: caută întâi în primele ~1200 caractere (antet)
    head = t[:1200]
    res.data_pronuntarii = _parse_ro_date(head) or _parse_ro_date(t)
    res.confidence["data_pronuntarii"] = 0.85 if res.data_pronuntarii else 0.2

    # Judecător / grefier (forme comune)
    res.judecator = _find_first(
        [
            r"\bjudecător(?:ul)?\s+([A-ZĂÂÎȘȚ][A-Za-zĂÂÎȘȚăâîșț\-]+(?:\s+[A-ZĂÂÎȘȚ][A-Za-zĂÂÎȘȚăâîșț\-]+)*)\b",
            r"\bPreședintele\s+ședinței,\s*judecător(?:ul)?\s*,?\s*([A-ZĂÂÎȘȚ][A-Za-zĂÂÎȘȚăâîșț\-]+(?:\s+[A-ZĂÂÎȘȚ][A-Za-zĂÂÎȘȚăâîșț\-]+)*)\b",
        ],
        t,
        flags=re.IGNORECASE
    )
    res.grefier = _find_first(
        [r"\bGrefier(?:i)?\s+([A-ZĂÂÎȘȚ][A-Za-zĂÂÎȘȚăâîșț\-]+(?:\s+[A-ZĂÂÎȘȚ][A-Za-zĂÂÎȘȚăâîșț\-]+)*)\b"],
        t,
        flags=re.IGNORECASE
    )

    # Procuror / avocat
    res.procuror = _find_first(
        [
            r"\bprocurorului\s+([A-ZĂÂÎȘȚ][A-Za-zĂÂÎȘȚăâîșț\-]+(?:\s+[A-ZĂÂÎȘȚ][A-Za-zĂÂÎȘȚăâîșț\-]+)*)\b",
            r"\bAcuzatorilor\s+de\s+stat\s+([A-ZĂÂÎȘȚ][A-Za-zĂÂÎȘȚăâîșț\-]+(?:\s+[A-ZĂÂÎȘȚ][A-Za-zĂÂÎȘȚăâîșț\-]+)*)\b",
        ],
        t,
        flags=re.IGNORECASE
    )
    res.avocat = _find_first(
        [
            r"\bAvocatului\s+([A-ZĂÂÎȘȚ][A-Za-zĂÂÎȘȚăâîșț\-]+(?:\s+[A-ZĂÂÎȘȚ][A-Za-zĂÂÎȘȚăâîșț\-]+)*)\b",
            r"\bApărătorului\s+([A-ZĂÂÎȘȚ][A-Za-zĂÂÎȘȚăâîșț\-]+(?:\s+[A-ZĂÂÎȘȚ][A-Za-zĂÂÎȘȚăâîșț\-]+)*)\b",
        ],
        t,
        flags=re.IGNORECASE
    )

    # Articole de lege (colectăm toate aparițiile relevante)
    arts = re.findall(r"\bart\.\s*\d+(?:\s*[\^]?\s*\d+)?(?:\s*alin\.\s*\([0-9]+\))?(?:\s*lit\.\s*[a-z]\))?\s*(?:Cod penal|CP|Cod administrativ|CPC|CPP)?\b",
                      t, flags=re.IGNORECASE)
    # Curățăm / deduplicăm păstrând ordinea
    seen = set()
    cleaned = []
    for a in arts:
        a2 = re.sub(r"\s{2,}", " ", a.strip())
        if a2.lower() not in seen:
            seen.add(a2.lower())
            cleaned.append(a2)
    res.articole = cleaned[:40]
    res.confidence["articole"] = 0.8 if res.articole else 0.25

    # Procedură (simplificată / generală / contencios administrativ)
    if re.search(r"\bprocedura\s+simplificată\b|\bart\.\s*364\s*1\b", t, flags=re.IGNORECASE):
        res.procedura = "simplificată"
    elif re.search(r"\bprocedură\s+generală\b", t, flags=re.IGNORECASE):
        res.procedura = "generală"
    elif re.search(r"\bcontencios(?:ului)?\s+administrativ\b", t, flags=re.IGNORECASE):
        res.procedura = "contencios administrativ"
    if res.procedura:
        res.confidence["procedura"] = 0.75

    # Domeniu (heuristic)
    if re.search(r"\bCauza\s+penală\b|\bCod penal\b|\binculpat", t, flags=re.IGNORECASE):
        res.domain = "penal"
    elif re.search(r"\bCod administrativ\b|\bcontencios administrativ\b|\bactului administrativ\b", t, flags=re.IGNORECASE):
        res.domain = "administrativ"
    else:
        res.domain = None

    # Soluție (heuristic, se rafinează cu set de reguli)
    sol = None
    if re.search(r"\bachit", t, flags=re.IGNORECASE):
        sol = "achitare"
    if re.search(r"\bcondamn", t, flags=re.IGNORECASE):
        sol = "condamnare"
    if re.search(r"\bprescrip", t, flags=re.IGNORECASE):
        sol = "prescripție"
    if re.search(r"\banulare(a)?\s+actului\s+administrativ\b|\banularea\s+pct\.\b", t, flags=re.IGNORECASE):
        sol = "anulare act administrativ"
    res.solutie = sol
    res.confidence["solutie"] = 0.55 if sol else 0.2

    return res
