# Mod Standalone - Procesare fără Docker/Kafka

Acest mod permite rularea întregului pipeline de procesare **direct din backend**, fără a depinde de Docker, Kafka sau microservicii.

## Cum funcționează

Pipeline-ul standalone face tot procesul într-un singur script Python:
1. **Scraping** - Colectează hotărâri de pe instante.justice.md
2. **Validare & Deduplicare** - Curăță și elimină duplicate
3. **Extragere Metadata** - Extrage informații structurate
4. **Salvare** - Stochează rezultatele în JSON

## Instalare

```bash
cd Services
pip install -r standalone_requirements.txt
```

## Utilizare

### Din CLI

```bash
python standalone_processor.py "2024-12-18" ./data/standalone/cases.json 50
```

Parametri:
- `date_range`: Data sau interval (ex: "2024-12-18" sau "2024-12-01 TO 2024-12-31")
- `output_file`: Fișier de ieșire (implicit: `./data/standalone/cases.json`)
- `max_pages`: Număr maxim de pagini de scraped (implicit: 50)

### Din UI Web

1. Deschide http://localhost:8080
2. Bifează **"Mod Standalone (fără Docker/Kafka)"**
3. Selectează data/intervalul
4. Click pe **"Start"**
5. Așteaptă procesarea și vizualizează rezultatele

## API Endpoints

### POST /api/standalone/run
Pornește procesare standalone

Query params:
- `date_range`: string (required)
- `max_pages`: integer (optional, default: 50)

Răspuns:
```json
{
  "job_id": "standalone-1234567890",
  "status": "running",
  "message": "Procesare pornită în background"
}
```

### GET /api/standalone/jobs/:job_id
Verifică statusul job-ului

Răspuns:
```json
{
  "status": "completed",
  "date_range": "2024-12-18",
  "started_at": "2024-12-18T10:00:00Z",
  "completed_at": "2024-12-18T10:05:00Z",
  "progress": "[standalone] Finalizat: total 150 hotărâri găsite",
  "result": {
    "total": 150,
    "cases": [...],
    "output_file": "/data/standalone/cases.json"
  }
}
```

### GET /api/standalone/cases
Listează toate cazurile procesate în mod standalone

Query params:
- `start_date`: string (optional)
- `end_date`: string (optional)
- `limit`: integer (optional, default: 1000)
- `offset`: integer (optional, default: 0)

Răspuns:
```json
{
  "total": 150,
  "total_unfiltered": 150,
  "limit": 1000,
  "offset": 0,
  "start_date": null,
  "end_date": null,
  "mode": "standalone",
  "cases": [...]
}
```

## Avantaje

✅ **Fără dependențe complexe** - Nu necesită Docker, Kafka, Zookeeper
✅ **Simplu de testat** - Rulează direct cu Python
✅ **Rapid de dezvoltat** - Modificări instantanee, fără rebuild
✅ **Portabil** - Funcționează pe orice sistem cu Python 3.11+
✅ **Debugging ușor** - Logging clar, tot într-un singur proces

## Limitări

⚠️ **Nu scalează** - Procesează secvențial, nu în paralel
⚠️ **Fără persistență** - Rezultatele se pierd la restart dacă nu sunt salvate
⚠️ **Memory-bound** - Toate datele în memorie
⚠️ **Single-threaded** - Nu folosește multiple core-uri CPU

## Când să folosești fiecare mod

**Mod Standalone:**
- Dezvoltare și testare
- Volume mici de date (<1000 cazuri)
- Demonstrații și prototipuri
- Când Docker nu este disponibil

**Mod Microservicii:**
- Producție
- Volume mari de date (>1000 cazuri)
- Procesare continuă
- Scalabilitate și fault tolerance

## Fișiere generate

```
Services/
  data/
    standalone/
      cases.json        # Toate cazurile procesate
    pdf/                # PDF-uri descărcate (dacă activat)
    txt/                # Text extras din PDF-uri
```

## Arhitectură

```
Web UI (index.html)
    ↓
ms_bff (server.js)
    ↓
standalone_processor.py
    ↓
    ├─ scrape_all()        # Scraping hotărâri
    ├─ validate_and_dedup() # Validare și deduplicare
    ├─ process_pdfs()      # Download și extract PDF (opțional)
    ├─ enrich_cases()      # Extragere metadata
    └─ save to JSON        # Salvare rezultate
```

## Troubleshooting

### Eroare: "Module not found"
```bash
pip install -r standalone_requirements.txt
```

### Eroare: "Permission denied"
```bash
chmod +x standalone_processor.py
```

### Scraping eșuează
- Verifică conexiunea la internet
- Verifică că site-ul instante.justice.md este disponibil
- Verifică că nu există proxy-uri care blochează

### Processing lent
- Reduce `max_pages` pentru teste rapide
- Comentează `process_pdfs()` pentru a sări peste download-ul PDF-urilor
