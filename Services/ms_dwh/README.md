# MS Data Warehouse (DWH)

Microserviciu pentru agregare date și analiză avansată în sistem juridic.

## 📊 Ce face?

DWH implementează un **Data Warehouse dimensional** (star schema) pentru:
- Agregări statistice complexe
- Analiza tendințelor în timp
- Comparații și benchmarking
- Generare insights automate
- Rapoarte pentru management și analiză BI

## 🏗️ Arhitectură

### Star Schema (OLAP)

**Fact Table:**
- `fact_cases` - cazuri individuale cu foreign keys către dimensiuni

**Dimension Tables:**
- `dim_court` - instanțe judecătorești
- `dim_judge` - judecători
- `dim_date` - dimensiune temporală (an, lună, trimestru)
- `dim_doc_type` - tipuri documente (HOTĂRÂRE, SENTINȚĂ, etc.)
- `dim_domain` - domenii juridice (penal, civil, administrativ)
- `dim_solution` - soluții (condamnare, achitare, etc.)

**Aggregate Tables:**
- `agg_monthly_stats` - statistici agregate pe luni
- `agg_court_performance` - performanța instanțelor

## 🔄 Flux de date

```
[court.enriched] → DWH Consumer → SQLite Warehouse
                                        ↓
                                   DWH API → BFF → UI
```

## 🚀 API Endpoints

### 1. KPI-uri Generale
```bash
GET /dwh/kpi
```
Returnează:
- Total cazuri
- Total instanțe unice
- Total judecători
- Media articole per caz
- Rata de condamnare (%)

### 2. Tendințe Lunare
```bash
GET /dwh/trends/monthly?limit=12
```
Returnează ultimele N luni cu:
- Total cazuri
- Media articole
- Număr condamnări/achitări

### 3. Top Instanțe
```bash
GET /dwh/courts/top?limit=10
```
Returnează top instanțe după număr cazuri.

### 4. Top Judecători
```bash
GET /dwh/judges/top?limit=10
```
Returnează top judecători după număr cazuri + media articole.

### 5. Insights Automate
```bash
GET /dwh/insights
```
Generează insights precum:
- Cel mai activ judecător
- Instanța cu cele mai multe condamnări
- Luna cu cele mai multe cazuri

### 6. Rezumat Complet
```bash
GET /dwh/stats/summary
```
Returnează toate statisticile într-un singur răspuns.

### 7. Recompute Aggregates
```bash
POST /dwh/compute
```
Trigger manual pentru recalculare agregări.

## 📦 Instalare & Rulare

### Docker Compose
```yaml
ms_dwh:
  build: ./ms_dwh
  environment:
    KAFKA_BOOTSTRAP: kafka:9092
  volumes:
    - ./data/dwh:/data/dwh
  ports:
    - "8020:8000"
```

### Standalone
```bash
# Install dependencies
pip install confluent-kafka fastapi uvicorn sqlalchemy pandas

# Run consumer + API
python consumer.py & uvicorn api:app --host 0.0.0.0 --port 8000
```

## 💡 Use Cases

### 1. Rapoarte Management
- Evoluție număr cazuri în timp
- Performanța instanțelor
- Rata de succes pe domenii

### 2. Analiza Tendințelor
- Identificare pattern-uri sezoniere
- Creștere/scădere volum cazuri
- Schimbări în tipuri soluții

### 3. Benchmarking
- Comparație între instanțe
- Performanță judecători
- Distribuție pe domenii

### 4. Business Intelligence
- KPI-uri pentru dashboards
- Export date pentru Power BI / Tableau
- Predictive analytics (viitor)

## 🔧 Configurare

### Environment Variables
- `KAFKA_BOOTSTRAP` - Kafka connection string
- `DB_PATH` - Cale către SQLite database (default: `/data/dwh/warehouse.db`)

### Performance
- **Auto-aggregation**: La fiecare 50 de cazuri procesate
- **Indexes**: Pe toate foreign keys pentru queries rapide
- **Batch processing**: Consumer optimizat

## 📈 Metrici Capturate

- Total cazuri procesate
- Distribuție pe instanțe
- Distribuție pe judecători
- Distribuție pe domenii juridice
- Distribuție temporală (an, lună, trimestru)
- Rate de condamnare/achitare
- Media articole de lege menționate

## 🔮 Dezvoltări Viitoare

- [ ] Machine Learning pentru predicții
- [ ] Anomaly detection (identificare cazuri neobișnuite)
- [ ] Natural Language Processing pe texte
- [ ] Export în Excel/CSV
- [ ] PostgreSQL pentru producție (scalabilitate)
- [ ] Cache Redis pentru query performance
- [ ] Grafice embedded în API responses

## 📝 Exemplu Răspuns

```json
{
  "kpi": {
    "total_cases": 477,
    "total_courts": 12,
    "total_judges": 45,
    "avg_articles_per_case": 8.5,
    "condamnare_rate_percent": 34.2
  },
  "insights": [
    {
      "type": "top_judge",
      "message": "Cel mai activ judecător: Ion Popescu cu 23 cazuri",
      "value": 23
    }
  ]
}
```

## 🎯 Beneficii

✅ **Separare concerns** - DWH independent de serviciile de procesare
✅ **Performance** - Queries rapide prin agregări pre-calculate
✅ **Scalabilitate** - Schema optimizată pentru analiza OLAP
✅ **Flexibilitate** - Ușor de extins cu noi metrici
✅ **Insights** - Generează automat informații valoroase

---

**Port**: 8020 (external), 8000 (internal)
**Database**: SQLite (pentru dezvoltare), PostgreSQL (recomandat pentru producție)
**Dependencies**: Kafka, FastAPI, SQLAlchemy, Pandas
