# 📊 Sistem Microservicii - Date Juridice Moldova

Platformă de procesare, analiză și vizualizare hotărâri judecătorești din Republica Moldova.

## 🏗️ Arhitectură Completă

```
┌─────────────────────────────────────────────────────────────────┐
│                         WEB UI (Port 8080)                       │
│                    Dashboard interactiv + Charts                 │
└────────────────────────────┬────────────────────────────────────┘
                             │
┌────────────────────────────┴────────────────────────────────────┐
│                      BFF Gateway (Port 8081)                     │
│              API Gateway pentru toate serviciile                 │
└─────┬────────┬────────┬────────┬────────┬──────────────────────┘
      │        │        │        │        │
      ▼        ▼        ▼        ▼        ▼
┌──────────┐ ┌───────┐ ┌──────┐ ┌───────┐ ┌──────────────────┐
│Ingestion │ │Extract│ │Cases │ │Storage│ │  DWH (8020)      │
│  (8000)  │ │(8010) │ │      │ │       │ │  Analytics       │
└────┬─────┘ └───────┘ └──────┘ └───────┘ └────────┬─────────┘
     │                                               │
     └───────────────────┬───────────────────────────┘
                         ▼
           ┌─────────────────────────┐
           │    KAFKA MESSAGE BUS    │
           │  (Zookeeper + Kafka)    │
           └──┬──────┬──────┬────┬───┘
              │      │      │    │
              ▼      ▼      ▼    ▼
         ┌─────┐ ┌────┐ ┌────┐ ┌────┐
         │Raw  │ │Val │ │Text│ │Enr │
         │     │ │    │ │    │ │    │
         └─────┘ └────┘ └────┘ └────┘

Topics: court.raw → court.validated → court.text → court.enriched
```

## 🎯 Microservicii

### 1. **ms_ingestion_web** (Port 8000)
**Scop**: Scraping date de pe instante.justice.md

**Features**:
- Scraping asincron paralel (6 pagini simultan)
- Input: date range (single sau interval)
- Output: Kafka topic `court.raw`
- Job-based processing cu status tracking

**Tech**: FastAPI, httpx, BeautifulSoup4, Kafka Producer

---

### 2. **ms_dataquality** (Consumer only)
**Scop**: Validare și deduplicare date

**Features**:
- Validare structură date
- Normalizare câmpuri
- Deduplicare cu bounded cache (10K entries)
- Memory-safe (fix pentru memory leak)

**Input**: `court.raw`
**Output**: `court.validated`
**Tech**: Python, Kafka Consumer/Producer

---

### 3. **ms_pdftext** (Consumer only)
**Scop**: Download PDF-uri și extracție text

**Features**:
- ✨ **Async parallel downloads** (5 PDFs simultan)
- Text extraction cu PyPDF
- Salvare în `/data/txt/`
- **Performance**: 5x mai rapid decât versiunea sync

**Input**: `court.validated`
**Output**: `court.text`
**Tech**: Python, httpx (async), PyPDF, Kafka

---

### 4. **ms-case-extractor** (Port 8010 + Consumer)
**Scop**: Extracție metadate din text (NLP simplu)

**Features**:
- **API**: Upload manual TXT → metadate JSON
- **Consumer**: Procesare automată din Kafka (10 fișiere paralel)
- Extrage: instanță, dosar, judecător, avocat, articole, soluție, etc.
- Regex-based extraction cu confidence scores

**Input**: `court.text`
**Output**: `court.enriched`
**Tech**: FastAPI, Python regex, Pydantic, aiofiles

---

### 5. **ms_storage** (Consumer only)
**Scop**: Persistență date enriched

**Features**:
- **Batching**: Scrie la fiecare 10 mesaje (90% mai puțin I/O)
- Timeout flush: 5 secunde
- Salvare în JSON (`/data/enriched/cases.json`)
- Bounded storage (max 10K cazuri)

**Input**: `court.enriched`
**Output**: File storage
**Tech**: Python, JSON, Kafka Consumer

---

### 6. **ms_dwh** ⭐ (Port 8020 + Consumer)
**Scop**: Data Warehouse pentru analiză avansată

**Features**:
- **Star Schema**: Dimensional modeling (OLAP)
- **Fact table**: fact_cases
- **Dimensions**: court, judge, date, doc_type, domain, solution
- **Aggregates**: monthly_stats, court_performance
- **API Endpoints**:
  - `/dwh/kpi` - KPI-uri generale
  - `/dwh/trends/monthly` - Tendințe temporale
  - `/dwh/courts/top` - Top instanțe
  - `/dwh/judges/top` - Top judecători
  - `/dwh/insights` - Insights automate
  - `/dwh/stats/summary` - Rezumat complet
- **Auto-aggregation**: La fiecare 50 cazuri

**Use Cases**:
- Rapoarte management
- Trend analysis
- Benchmarking instanțe/judecători
- Business Intelligence
- Viitor: ML predictions

**Input**: `court.enriched`
**Storage**: SQLite (`/data/dwh/warehouse.db`)
**Tech**: FastAPI, SQLAlchemy, SQLite, Pandas

---

### 7. **ms_bff** (Port 8081)
**Scop**: Backend-for-Frontend Gateway

**Features**:
- Proxy pentru toate microserviciile
- Health check aggregat
- Upload TXT pentru extracție
- Scraping job management
- **DWH endpoints** proxy
- Servire date procesate

**Tech**: Node.js, Express, node-fetch

---

### 8. **web_ui** (Port 8080)
**Scop**: Dashboard interactiv

**Features**:
- ✨ **6 grafice profesionale** (Chart.js):
  - Top 15 Instanțe (bar horizontal)
  - Domenii Juridice (doughnut)
  - Tipuri Documente (pie)
  - Soluții Pronunțate (doughnut)
  - Distribuție Temporală (line chart)
  - Top 10 Judecători (bar)
- ✨ **Constructor Grafic Personalizat**:
  - Selectare tip: Bare, Pie, Doughnut, Linie
  - Grupare după: Instanță, Domeniu, Soluție, etc.
  - Limită: Top 5/10/15/20/Toate
- **DWH Insights** automate
- Statistici rezumative
- Tabel detaliat cu sticky headers
- Dark theme profesional

**Tech**: HTML, CSS, JavaScript, Chart.js

---

## 🚀 Instalare & Rulare

### Prerequisites
```bash
docker
docker-compose
```

### Quick Start
```bash
cd Services
docker-compose up --build -d
```

### Accesare
- **Web UI**: http://localhost:8080
- **BFF API**: http://localhost:8081
- **DWH API**: http://localhost:8020
- **Case Extractor**: http://localhost:8010
- **Ingestion**: http://localhost:8000

### Testare Fluxul Complet

1. **Scraping date noi**:
   - Accesează http://localhost:8080
   - Selectează o dată
   - Click "▶️ Start"
   - Așteaptă procesarea (vizibil în Output)

2. **Vizualizare rezultate**:
   - Click "📥 Încarcă Date"
   - Vezi statistici, grafice, tabel
   - Scroll jos pentru Constructor Grafic
   - Vezi DWH Insights automate

3. **API Direct**:
   ```bash
   # Health check
   curl http://localhost:8081/api/health

   # DWH KPIs
   curl http://localhost:8081/api/dwh/kpi

   # DWH Insights
   curl http://localhost:8081/api/dwh/insights

   # Cases
   curl http://localhost:8081/api/cases?limit=10
   ```

---

## 📊 Performanță

### Pipeline Speed (100 cazuri)
- **Înainte**: ~210 secunde (~3.5 minute)
- **După optimizări**: ~40 secunde
- **Îmbunătățire**: **5x mai rapid** 🚀

### Optimizări Implementate
1. ✅ **ms_pdftext**: Async parallel (5 PDFs simultan) - 5x speedup
2. ✅ **ms-case-extractor**: Async parallel (10 files) - 10x speedup
3. ✅ **ms_storage**: Batching (10x mai puțin I/O)
4. ✅ **Kafka producers**: Batching + LZ4 compression (40-60% bandwidth)
5. ✅ **ms_dataquality**: Bounded cache (fix memory leak)

---

## 🔧 Configurare

### Environment Variables

**Kafka**:
- `KAFKA_BOOTSTRAP=kafka:9092`

**Concurrency (Performance)**:
```yaml
PDF_CONCURRENCY=5          # ms_pdftext
EXTRACTOR_CONCURRENCY=10   # ms-case-extractor
STORAGE_BATCH_SIZE=10      # ms_storage
STORAGE_BATCH_TIMEOUT=5    # ms_storage
```

---

## 📂 Structură Date

### Volumes
```
./data/
├── pdf/         # PDF-uri descărcate
├── txt/         # Texte extrase
├── enriched/    # JSON cu date procesate
└── dwh/         # SQLite warehouse
```

### Kafka Topics
1. **court.raw** - Date scraped brute
2. **court.validated** - Date validate + deduplicat
3. **court.text** - Text extras din PDF
4. **court.enriched** - Metadate extrase + text

---

## 🎯 Use Cases

### 1. Cercetare Juridică
- Căutare hotărâri după instanță, judecător, articole
- Analiza soluțiilor (condamnare/achitare)
- Identificare precedente

### 2. Statistici & Rapoarte
- Evoluție număr cazuri în timp
- Performanță instanțe/judecători
- Distribuție pe domenii (penal/civil/admin)

### 3. Business Intelligence
- KPI-uri pentru management
- Trend analysis
- Benchmarking între instanțe
- Insights automate

### 4. Analytics Avansată
- Top judecători după volum
- Rate de condamnare pe instanță
- Articole cele mai citate
- Distribuție temporală

---

## 🔮 Dezvoltări Viitoare

### Short-term
- [ ] Export Excel/CSV din dashboard
- [ ] Filtre avansate în UI (by court, judge, date range)
- [ ] Căutare full-text în hotărâri
- [ ] Notificări email pentru noi cazuri

### Mid-term
- [ ] PostgreSQL în loc de SQLite pentru DWH
- [ ] Redis cache pentru query performance
- [ ] Elasticsearch pentru search
- [ ] User authentication & authorization

### Long-term
- [ ] Machine Learning pentru predicții
- [ ] NLP avansat pentru clasificare automată
- [ ] Anomaly detection
- [ ] Recommendation system pentru cazuri similare

---

## 🛠️ Tech Stack

**Backend**:
- Python 3.11 (FastAPI, Kafka)
- Node.js 18 (Express)
- SQLite / PostgreSQL (viitor)

**Frontend**:
- HTML5, CSS3, JavaScript
- Chart.js 4.4.0

**Infrastructure**:
- Docker & Docker Compose
- Apache Kafka + Zookeeper
- Nginx (web_ui server)

**Libraries**:
- confluent-kafka (Kafka client)
- httpx (async HTTP)
- BeautifulSoup4 (scraping)
- PyPDF (PDF extraction)
- Pydantic (validation)
- SQLAlchemy (ORM)
- Pandas (data processing)

---

## 📝 Contribuție

1. Fork repository
2. Create feature branch
3. Commit changes
4. Push to branch
5. Create Pull Request

---

## 📄 Licență

MIT License

---

## 👥 Contact

Pentru întrebări sau sugestii, deschide un Issue pe GitHub.

---

**Version**: 2.0.0
**Last Updated**: December 2025
**Microservicii**: 8
**Kafka Topics**: 4
**API Endpoints**: 20+
**Dashboard Charts**: 6+ customizable

🚀 **Production-ready microservices architecture for legal data analytics!**
