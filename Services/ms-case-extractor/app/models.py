from pydantic import BaseModel, Field
from typing import Optional, List, Dict

class CaseExtractResult(BaseModel):
    source_filename: Optional[str] = None

    # Identificare
    dosar_nr: Optional[str] = None
    pigd_id: Optional[str] = None  # apare uneori: "PIGD 1-...."
    doc_type: Optional[str] = None  # SENTINȚĂ / HOTĂRÂRE / ÎNCHEIERE etc.
    domain: Optional[str] = None    # penal / administrativ / civil (heuristic)

    # Instanță / locație / timp
    instanta: Optional[str] = None
    sediu: Optional[str] = None
    localitate: Optional[str] = None
    data_pronuntarii: Optional[str] = None  # ISO "YYYY-MM-DD" dacă o detectăm

    # Actori
    judecator: Optional[str] = None
    grefier: Optional[str] = None
    procuror: Optional[str] = None
    avocat: Optional[str] = None

    # Legal
    articole: List[str] = Field(default_factory=list)  # ex: ["art.361 alin.(1) Cod penal"]
    procedura: Optional[str] = None  # generală / simplificată etc.

    # Rezultat (heuristic)
    solutie: Optional[str] = None  # condamnare / achitare / prescripție / anulare act etc.

    # Debug / calitate
    confidence: Dict[str, float] = Field(default_factory=dict)
    warnings: List[str] = Field(default_factory=list)
