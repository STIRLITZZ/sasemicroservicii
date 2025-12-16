# Arhitectura Microserviciilor - Sistem Procesare Date Juridice

## Diagrama Arhitecturală Completă

```mermaid
graph TB
    subgraph "External"
        USER[👤 Utilizator Web]
        PORTAL[🌐 Portal Instanțe<br/>portal.just.ro]
    end

    subgraph "Frontend Layer"
        UI[🖥️ Web UI<br/>port 8080<br/>Dashboard + Grafice]
    end

    subgraph "API Gateway Layer"
        BFF[🔌 BFF<br/>port 8081<br/>Backend-for-Frontend<br/>Express.js]
    end

    subgraph "Message Broker"
        KAFKA[📨 Kafka<br/>port 9092<br/>Message Bus]
    end

    subgraph "Ingestion Layer"
        INGEST[🕷️ ms_ingestion_web<br/>port 8000<br/>Web Scraper<br/>Selenium]
    end

    subgraph "Data Quality Layer"
        DQ[✅ ms_dataquality<br/>Validare + Deduplicare<br/>Bounded Cache]
    end

    subgraph "Processing Layer"
        PDF[📄 ms_pdftext<br/>Extragere Text PDF<br/>5x Async Parallel<br/>pdfplumber]
        EXTRACT[⚖️ ms-case-extractor<br/>port 8010<br/>Extragere Metadata<br/>10x Async Parallel<br/>Regex + NLP]
    end

    subgraph "Storage Layer"
        STORE[💾 ms_storage<br/>Persistență Date<br/>Batch Writing<br/>JSON Files]
    end

    subgraph "Analytics Layer"
        DWH[📊 ms_dwh<br/>port 8020<br/>Data Warehouse<br/>Star Schema<br/>SQLite/PostgreSQL]
    end

    subgraph "Kafka Topics"
        T1[court.raw]
        T2[court.validated]
        T3[court.text]
        T4[court.enriched]
    end

    %% User interactions
    USER -->|HTTP GET/POST| UI
    UI -->|REST API| BFF

    %% Ingestion flow
    INGEST -->|scrape| PORTAL
    INGEST -->|publish| T1

    %% Data flow through Kafka topics
    T1 -->|consume| DQ
    DQ -->|publish| T2

    T2 -->|consume| PDF
    PDF -->|publish| T3

    T3 -->|consume| EXTRACT
    EXTRACT -->|publish| T4

    T4 -->|consume| STORE
    T4 -->|consume| DWH

    %% BFF connections
    BFF -->|/api/scrape| INGEST
    BFF -->|/api/extract| EXTRACT
    BFF -->|/api/cases| STORE
    BFF -->|/api/dwh/*| DWH

    %% Styling
    classDef frontend fill:#61dafb,stroke:#333,stroke-width:2px,color:#000
    classDef gateway fill:#68a063,stroke:#333,stroke-width:2px,color:#fff
    classDef ingestion fill:#f9a825,stroke:#333,stroke-width:2px,color:#000
    classDef processing fill:#7e57c2,stroke:#333,stroke-width:2px,color:#fff
    classDef storage fill:#26a69a,stroke:#333,stroke-width:2px,color:#fff
    classDef analytics fill:#ef5350,stroke:#333,stroke-width:2px,color:#fff
    classDef kafka fill:#000,stroke:#333,stroke-width:3px,color:#fff
    classDef topic fill:#231f20,stroke:#fff,stroke-width:1px,color:#fff

    class UI frontend
    class BFF gateway
    class INGEST ingestion
    class DQ,PDF,EXTRACT processing
    class STORE storage
    class DWH analytics
    class KAFKA kafka
    class T1,T2,T3,T4 topic
```

## Fluxul Complet de Date

```mermaid
sequenceDiagram
    participant U as 👤 Utilizator
    participant UI as 🖥️ Web UI
    participant BFF as 🔌 BFF
    participant ING as 🕷️ Ingestion
    participant K as 📨 Kafka
    participant DQ as ✅ DataQuality
    participant PDF as 📄 PDF Text
    participant EXT as ⚖️ Extractor
    participant STR as 💾 Storage
    participant DWH as 📊 DWH

    U->>UI: Introduce dată (2024-01-15)
    UI->>BFF: POST /api/scrape {date}
    BFF->>ING: POST /scrape {date}

    ING->>ING: Scrape portal.just.ro
    ING->>K: Publish → court.raw (100 cazuri)

    K->>DQ: Consume court.raw
    DQ->>DQ: Validare schema
    DQ->>DQ: Deduplicare (bounded cache)
    DQ->>K: Publish → court.validated (95 cazuri unice)

    K->>PDF: Consume court.validated
    PDF->>PDF: Download PDF (5 parallel)
    PDF->>PDF: Extract text cu pdfplumber
    PDF->>K: Publish → court.text (95 texte)

    K->>EXT: Consume court.text
    EXT->>EXT: Extract metadata (10 parallel)
    EXT->>EXT: Regex: instanță, judecător, domeniu
    EXT->>K: Publish → court.enriched (95 enriched)

    par Parallel Storage
        K->>STR: Consume court.enriched
        STR->>STR: Batch write (la fiecare 10)
        STR->>STR: Salvare JSON
    and Parallel Analytics
        K->>DWH: Consume court.enriched
        DWH->>DWH: Insert in star schema
        DWH->>DWH: Auto-aggregate (la 50 cazuri)
        DWH->>DWH: Generate insights
    end

    U->>UI: Click "Încarcă Date"
    UI->>BFF: GET /api/cases
    BFF->>STR: GET /cases
    STR-->>BFF: JSON (95 cazuri)
    BFF-->>UI: JSON
    UI->>UI: Render tabele + 6 grafice

    UI->>BFF: GET /api/dwh/insights
    BFF->>DWH: GET /dwh/insights
    DWH->>DWH: Query fact + dimension tables
    DWH-->>BFF: Insights JSON
    BFF-->>UI: Insights
    UI->>UI: Display insights pills
```

## Structura Kafka Topics

```mermaid
graph LR
    subgraph "Kafka Topics Pipeline"
        R[court.raw<br/>📥 Raw scraped data<br/>Schema: url, pdf_url, date]
        V[court.validated<br/>✅ Validated + deduplicated<br/>Schema: + dedup_key]
        T[court.text<br/>📝 PDF text extracted<br/>Schema: + text, txt_path]
        E[court.enriched<br/>⭐ Full metadata<br/>Schema: + extracted fields]
    end

    R -->|DataQuality| V
    V -->|PDFText| T
    T -->|Extractor| E
    E -->|Storage| S1[💾 JSON Files]
    E -->|DWH| S2[📊 Analytics DB]

    style R fill:#ffeb3b,stroke:#333,color:#000
    style V fill:#8bc34a,stroke:#333,color:#000
    style T fill:#03a9f4,stroke:#333,color:#fff
    style E fill:#e91e63,stroke:#333,color:#fff
```

## Star Schema - Data Warehouse

```mermaid
erDiagram
    fact_cases ||--o{ dim_court : "court_id"
    fact_cases ||--o{ dim_judge : "judge_id"
    fact_cases ||--o{ dim_date : "date_key"
    fact_cases ||--o{ dim_doc_type : "doc_type_id"
    fact_cases ||--o{ dim_domain : "domain_id"
    fact_cases ||--o{ dim_solution : "solution_id"

    fact_cases {
        int case_id PK
        string dedup_key UK
        int court_id FK
        int judge_id FK
        int date_key FK
        int doc_type_id FK
        int domain_id FK
        int solution_id FK
        int article_count
    }

    dim_court {
        int court_id PK
        string court_name
        string court_type
    }

    dim_judge {
        int judge_id PK
        string judge_name
    }

    dim_date {
        int date_key PK
        date full_date
        int year
        int month
        int day
    }

    dim_doc_type {
        int doc_type_id PK
        string doc_type_name
    }

    dim_domain {
        int domain_id PK
        string domain_name
    }

    dim_solution {
        int solution_id PK
        string solution_name
    }

    agg_monthly_stats {
        int stat_id PK
        int year
        int month
        int total_cases
        int unique_courts
        int unique_judges
        float condamnare_rate
    }

    agg_court_performance {
        int perf_id PK
        int court_id FK
        int total_cases
        int civil_cases
        int penal_cases
    }
```

## Porturile Serviciilor

| Microserviciu | Port | Protocol | Acces |
|---------------|------|----------|-------|
| **web_ui** | 8080 | HTTP | Public - UI utilizator |
| **ms_bff** | 8081 | HTTP | Public - API Gateway |
| **ms_ingestion_web** | 8000 | HTTP | Intern - Scraping API |
| **ms-case-extractor** | 8010 | HTTP | Intern - Extraction API |
| **ms_dwh** | 8020 | HTTP | Intern - Analytics API |
| **kafka** | 9092 | TCP | Intern - Message Broker |
| **zookeeper** | 2181 | TCP | Intern - Kafka coordination |

## Tech Stack pe Microserviciu

```mermaid
graph TB
    subgraph "ms_ingestion_web"
        I1[Python 3.11]
        I2[Selenium]
        I3[confluent-kafka]
        I4[Flask]
    end

    subgraph "ms_dataquality"
        D1[Python 3.11]
        D2[jsonschema]
        D3[confluent-kafka]
        D4[collections.deque]
    end

    subgraph "ms_pdftext"
        P1[Python 3.11]
        P2[pdfplumber]
        P3[asyncio]
        P4[httpx]
    end

    subgraph "ms-case-extractor"
        E1[Python 3.11]
        E2[re regex]
        E3[asyncio]
        E4[FastAPI]
    end

    subgraph "ms_storage"
        S1[Python 3.11]
        S2[JSON]
        S3[confluent-kafka]
        S4[Batch writes]
    end

    subgraph "ms_dwh"
        W1[Python 3.11]
        W2[SQLAlchemy]
        W3[pandas]
        W4[FastAPI]
    end

    subgraph "ms_bff"
        B1[Node.js 20]
        B2[Express.js]
        B3[node-fetch]
    end

    subgraph "web_ui"
        U1[HTML5]
        U2[Chart.js 4.4]
        U3[Vanilla JS]
        U4[CSS3]
    end
```

## Optimizări Implementate

| Layer | Optimizare | Impact | Configurare |
|-------|-----------|---------|-------------|
| **PDF Processing** | Async 5x parallel downloads | 5x mai rapid | `PDF_CONCURRENCY=5` |
| **Extraction** | Async 10x parallel processing | 10x mai rapid | `EXTRACT_CONCURRENCY=10` |
| **Storage** | Batch writing (10 msgs) | 90% mai puține I/O | `STORAGE_BATCH_SIZE=10` |
| **Kafka** | LZ4 compression + batching | 60% mai puțin bandwidth | `linger.ms=100` |
| **DWH** | Pre-aggregated tables | Query speed 100x | Auto-compute la 50 cazuri |
| **DataQuality** | Bounded cache (10k) | Memory safe | `MAX_DEDUP_SIZE=10000` |

## Performanță Globală

**Benchmark: Procesare 100 cazuri**

| Versiune | Timp Total | Throughput |
|----------|-----------|------------|
| Sincron (v1.0) | ~210 secunde | 0.48 cazuri/s |
| Async (v2.0) | ~40 secunde | 2.5 cazuri/s |
| **Îmbunătățire** | **5.25x mai rapid** | **5.2x throughput** |

## Scalabilitate

```mermaid
graph LR
    subgraph "Scaling Strategy"
        H[Horizontal Scaling]
        V[Vertical Scaling]
        P[Partitioning]
    end

    H -->|Docker replicas| S1[ms_pdftext x3]
    H -->|Docker replicas| S2[ms-case-extractor x2]
    V -->|More memory| S3[ms_dwh: 16GB RAM]
    P -->|Kafka partitions| S4[court.text: 4 partitions]

    S1 --> R1[15x parallel PDFs]
    S2 --> R2[20x parallel extractions]
    S3 --> R3[Faster aggregations]
    S4 --> R4[Load balancing]
```

## Securitate & Producție

### Recomandări pentru Producție:

1. **Database**: SQLite → PostgreSQL cu connection pooling
2. **Message Broker**: Kafka replication factor = 3
3. **Authentication**: JWT tokens în BFF
4. **Rate Limiting**: 100 req/min per user în BFF
5. **Monitoring**: Prometheus + Grafana
6. **Logging**: ELK Stack (Elasticsearch, Logstash, Kibana)
7. **Secrets**: Vault sau AWS Secrets Manager
8. **TLS**: HTTPS pentru toate serviciile publice
9. **Backup**: Daily backups DWH + JSON storage
10. **CI/CD**: GitHub Actions cu automated testing

## Use Cases Business

### 1. Cercetare Juridică
- Găsește precedente similare după domeniu/instanță/judecător
- Analizează tendințe în legislație

### 2. Business Intelligence
- KPIs: rata de condamnare, durata medie procese
- Benchmarking între instanțe

### 3. Monitorizare Transparență
- Verifică activitatea judecătorilor
- Identifică anomalii în volumul de cazuri

### 4. Jurnalism Investigativ
- Corelează date din multiple surse
- Generează insights automate

## Roadmap Viitor

- [ ] GraphQL API în loc de REST
- [ ] Real-time WebSocket updates
- [ ] Machine Learning pentru predicții
- [ ] Elasticsearch pentru full-text search
- [ ] Export PDF/Excel din UI
- [ ] Multi-tenant support
- [ ] Mobile app (React Native)
- [ ] Advanced caching (Redis)
