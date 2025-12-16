#!/usr/bin/env python3
"""
DWH Engine - Motor pentru agregare și analiză date
Implementează schema dimensională și calcule statistice
"""

import sqlite3
import json
from datetime import datetime
from pathlib import Path
from typing import Dict, List, Optional


class DWHEngine:
    def __init__(self, db_path: str = "/data/dwh/warehouse.db"):
        self.db_path = db_path
        Path(db_path).parent.mkdir(parents=True, exist_ok=True)
        self.conn = sqlite3.connect(db_path, check_same_thread=False)
        self.conn.row_factory = sqlite3.Row
        self._init_schema()

    def _init_schema(self):
        """Inițializează schema warehouse (star schema)"""
        cursor = self.conn.cursor()

        # Fact Table: Cases
        cursor.execute("""
            CREATE TABLE IF NOT EXISTS fact_cases (
                case_id INTEGER PRIMARY KEY AUTOINCREMENT,
                dedup_key TEXT UNIQUE,
                dosar TEXT,
                court_id INTEGER,
                judge_id INTEGER,
                doc_type_id INTEGER,
                domain_id INTEGER,
                solution_id INTEGER,
                date_key INTEGER,
                article_count INTEGER DEFAULT 0,
                text_length INTEGER DEFAULT 0,
                created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
                FOREIGN KEY (court_id) REFERENCES dim_court(court_id),
                FOREIGN KEY (judge_id) REFERENCES dim_judge(judge_id),
                FOREIGN KEY (date_key) REFERENCES dim_date(date_key)
            )
        """)

        # Dimension: Courts
        cursor.execute("""
            CREATE TABLE IF NOT EXISTS dim_court (
                court_id INTEGER PRIMARY KEY AUTOINCREMENT,
                court_name TEXT UNIQUE,
                locality TEXT,
                court_type TEXT
            )
        """)

        # Dimension: Judges
        cursor.execute("""
            CREATE TABLE IF NOT EXISTS dim_judge (
                judge_id INTEGER PRIMARY KEY AUTOINCREMENT,
                judge_name TEXT UNIQUE
            )
        """)

        # Dimension: Date
        cursor.execute("""
            CREATE TABLE IF NOT EXISTS dim_date (
                date_key INTEGER PRIMARY KEY,
                full_date TEXT,
                year INTEGER,
                month INTEGER,
                quarter INTEGER,
                month_name TEXT
            )
        """)

        # Dimension: Document Types
        cursor.execute("""
            CREATE TABLE IF NOT EXISTS dim_doc_type (
                doc_type_id INTEGER PRIMARY KEY AUTOINCREMENT,
                doc_type_name TEXT UNIQUE
            )
        """)

        # Dimension: Domains
        cursor.execute("""
            CREATE TABLE IF NOT EXISTS dim_domain (
                domain_id INTEGER PRIMARY KEY AUTOINCREMENT,
                domain_name TEXT UNIQUE
            )
        """)

        # Dimension: Solutions
        cursor.execute("""
            CREATE TABLE IF NOT EXISTS dim_solution (
                solution_id INTEGER PRIMARY KEY AUTOINCREMENT,
                solution_name TEXT UNIQUE
            )
        """)

        # Aggregates: Monthly Stats
        cursor.execute("""
            CREATE TABLE IF NOT EXISTS agg_monthly_stats (
                stat_id INTEGER PRIMARY KEY AUTOINCREMENT,
                year INTEGER,
                month INTEGER,
                total_cases INTEGER DEFAULT 0,
                total_courts INTEGER DEFAULT 0,
                total_judges INTEGER DEFAULT 0,
                avg_articles REAL DEFAULT 0,
                condamnare_count INTEGER DEFAULT 0,
                achitare_count INTEGER DEFAULT 0,
                computed_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
            )
        """)

        # Aggregates: Court Performance
        cursor.execute("""
            CREATE TABLE IF NOT EXISTS agg_court_performance (
                perf_id INTEGER PRIMARY KEY AUTOINCREMENT,
                court_id INTEGER,
                total_cases INTEGER DEFAULT 0,
                avg_processing_days REAL DEFAULT 0,
                condamnare_rate REAL DEFAULT 0,
                last_updated TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
                FOREIGN KEY (court_id) REFERENCES dim_court(court_id)
            )
        """)

        # Create indexes
        cursor.execute("CREATE INDEX IF NOT EXISTS idx_fact_court ON fact_cases(court_id)")
        cursor.execute("CREATE INDEX IF NOT EXISTS idx_fact_judge ON fact_cases(judge_id)")
        cursor.execute("CREATE INDEX IF NOT EXISTS idx_fact_date ON fact_cases(date_key)")
        cursor.execute("CREATE INDEX IF NOT EXISTS idx_fact_domain ON fact_cases(domain_id)")

        self.conn.commit()

    def _get_or_create_dimension(self, table: str, name_col: str, name: str, extra_cols: Dict = None) -> int:
        """Helper pentru a obține sau crea o înregistrare de dimensiune"""
        if not name or name == "N/A":
            return None

        cursor = self.conn.cursor()
        cursor.execute(f"SELECT {table.replace('dim_', '')}_id FROM {table} WHERE {name_col} = ?", (name,))
        row = cursor.fetchone()

        if row:
            return row[0]

        # Create new dimension entry
        if extra_cols:
            cols = [name_col] + list(extra_cols.keys())
            vals = [name] + list(extra_cols.values())
            placeholders = ','.join(['?' for _ in cols])
            cursor.execute(
                f"INSERT INTO {table} ({','.join(cols)}) VALUES ({placeholders})",
                vals
            )
        else:
            cursor.execute(f"INSERT INTO {table} ({name_col}) VALUES (?)", (name,))

        self.conn.commit()
        return cursor.lastrowid

    def _get_or_create_date_dim(self, date_str: str) -> int:
        """Creează dimensiunea de dată"""
        if not date_str:
            return None

        try:
            date_obj = datetime.strptime(date_str, "%Y-%m-%d")
        except:
            return None

        date_key = int(date_str.replace("-", ""))
        cursor = self.conn.cursor()

        cursor.execute("SELECT date_key FROM dim_date WHERE date_key = ?", (date_key,))
        if cursor.fetchone():
            return date_key

        month_names = ["", "Ian", "Feb", "Mar", "Apr", "Mai", "Iun", "Iul", "Aug", "Sep", "Oct", "Noi", "Dec"]
        quarter = (date_obj.month - 1) // 3 + 1

        cursor.execute("""
            INSERT INTO dim_date (date_key, full_date, year, month, quarter, month_name)
            VALUES (?, ?, ?, ?, ?, ?)
        """, (date_key, date_str, date_obj.year, date_obj.month, quarter, month_names[date_obj.month]))

        self.conn.commit()
        return date_key

    def process_case(self, event: Dict):
        """Procesează un caz și îl adaugă în warehouse"""
        ext = event.get("extracted", {})
        dedup_key = event.get("dedup_key")

        # Skip dacă există deja
        cursor = self.conn.cursor()
        cursor.execute("SELECT case_id FROM fact_cases WHERE dedup_key = ?", (dedup_key,))
        if cursor.fetchone():
            return

        # Dimensiuni
        court_id = self._get_or_create_dimension(
            "dim_court", "court_name",
            ext.get("instanta") or event.get("instanta"),
            {"locality": ext.get("localitate") or event.get("localitate")}
        )

        judge_id = self._get_or_create_dimension(
            "dim_judge", "judge_name",
            ext.get("judecator")
        )

        doc_type_id = self._get_or_create_dimension(
            "dim_doc_type", "doc_type_name",
            ext.get("doc_type")
        )

        domain_id = self._get_or_create_dimension(
            "dim_domain", "domain_name",
            ext.get("domain")
        )

        solution_id = self._get_or_create_dimension(
            "dim_solution", "solution_name",
            ext.get("solutie")
        )

        date_key = self._get_or_create_date_dim(
            ext.get("data_pronuntarii") or event.get("data_pron")
        )

        # Insert fact
        article_count = len(ext.get("articole", []))
        text_length = event.get("text_chars", 0)

        cursor.execute("""
            INSERT INTO fact_cases
            (dedup_key, dosar, court_id, judge_id, doc_type_id, domain_id,
             solution_id, date_key, article_count, text_length)
            VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
        """, (dedup_key, ext.get("dosar_nr") or event.get("dosar"), court_id, judge_id,
              doc_type_id, domain_id, solution_id, date_key, article_count, text_length))

        self.conn.commit()

    def compute_aggregates(self):
        """Calculează agregări pentru rapoarte"""
        cursor = self.conn.cursor()

        # Monthly aggregates
        cursor.execute("""
            INSERT OR REPLACE INTO agg_monthly_stats
            (year, month, total_cases, total_courts, total_judges, avg_articles,
             condamnare_count, achitare_count)
            SELECT
                d.year,
                d.month,
                COUNT(DISTINCT f.case_id) as total_cases,
                COUNT(DISTINCT f.court_id) as total_courts,
                COUNT(DISTINCT f.judge_id) as total_judges,
                AVG(f.article_count) as avg_articles,
                SUM(CASE WHEN sol.solution_name LIKE '%condamn%' THEN 1 ELSE 0 END) as condamnare,
                SUM(CASE WHEN sol.solution_name LIKE '%achit%' THEN 1 ELSE 0 END) as achitare
            FROM fact_cases f
            LEFT JOIN dim_date d ON f.date_key = d.date_key
            LEFT JOIN dim_solution sol ON f.solution_id = sol.solution_id
            WHERE d.date_key IS NOT NULL
            GROUP BY d.year, d.month
        """)

        self.conn.commit()

    def get_kpi(self) -> Dict:
        """Returnează KPI-uri generale"""
        cursor = self.conn.cursor()

        # Total cases
        cursor.execute("SELECT COUNT(*) FROM fact_cases")
        total_cases = cursor.fetchone()[0]

        # Unique courts
        cursor.execute("SELECT COUNT(DISTINCT court_id) FROM fact_cases WHERE court_id IS NOT NULL")
        total_courts = cursor.fetchone()[0]

        # Unique judges
        cursor.execute("SELECT COUNT(DISTINCT judge_id) FROM fact_cases WHERE judge_id IS NOT NULL")
        total_judges = cursor.fetchone()[0]

        # Average articles per case
        cursor.execute("SELECT AVG(article_count) FROM fact_cases")
        avg_articles = cursor.fetchone()[0] or 0

        # Condamnare rate
        cursor.execute("""
            SELECT
                COUNT(CASE WHEN sol.solution_name LIKE '%condamn%' THEN 1 END) * 100.0 / COUNT(*) as rate
            FROM fact_cases f
            LEFT JOIN dim_solution sol ON f.solution_id = sol.solution_id
            WHERE sol.solution_id IS NOT NULL
        """)
        condamnare_rate = cursor.fetchone()[0] or 0

        return {
            "total_cases": total_cases,
            "total_courts": total_courts,
            "total_judges": total_judges,
            "avg_articles_per_case": round(avg_articles, 2),
            "condamnare_rate_percent": round(condamnare_rate, 2)
        }

    def get_monthly_trends(self, limit: int = 12) -> List[Dict]:
        """Returnează tendințe lunare"""
        cursor = self.conn.cursor()
        cursor.execute("""
            SELECT year, month, total_cases, avg_articles,
                   condamnare_count, achitare_count
            FROM agg_monthly_stats
            ORDER BY year DESC, month DESC
            LIMIT ?
        """, (limit,))

        return [dict(row) for row in cursor.fetchall()]

    def get_top_courts(self, limit: int = 10) -> List[Dict]:
        """Returnează top instanțe"""
        cursor = self.conn.cursor()
        cursor.execute("""
            SELECT c.court_name, c.locality, COUNT(f.case_id) as case_count
            FROM fact_cases f
            JOIN dim_court c ON f.court_id = c.court_id
            GROUP BY f.court_id
            ORDER BY case_count DESC
            LIMIT ?
        """, (limit,))

        return [dict(row) for row in cursor.fetchall()]

    def get_top_judges(self, limit: int = 10) -> List[Dict]:
        """Returnează top judecători"""
        cursor = self.conn.cursor()
        cursor.execute("""
            SELECT j.judge_name, COUNT(f.case_id) as case_count,
                   AVG(f.article_count) as avg_articles
            FROM fact_cases f
            JOIN dim_judge j ON f.judge_id = j.judge_id
            GROUP BY f.judge_id
            ORDER BY case_count DESC
            LIMIT ?
        """, (limit,))

        return [dict(row) for row in cursor.fetchall()]

    def get_insights(self) -> List[Dict]:
        """Generează insights automate"""
        insights = []
        cursor = self.conn.cursor()

        # Insight 1: Cel mai activ judecător
        cursor.execute("""
            SELECT j.judge_name, COUNT(f.case_id) as cnt
            FROM fact_cases f
            JOIN dim_judge j ON f.judge_id = j.judge_id
            GROUP BY f.judge_id
            ORDER BY cnt DESC LIMIT 1
        """)
        row = cursor.fetchone()
        if row:
            insights.append({
                "type": "top_judge",
                "message": f"Cel mai activ judecător: {row[0]} cu {row[1]} cazuri",
                "value": row[1]
            })

        # Insight 2: Instanța cu cele mai multe condamnări
        cursor.execute("""
            SELECT c.court_name, COUNT(f.case_id) as cnt
            FROM fact_cases f
            JOIN dim_court c ON f.court_id = c.court_id
            JOIN dim_solution sol ON f.solution_id = sol.solution_id
            WHERE sol.solution_name LIKE '%condamn%'
            GROUP BY f.court_id
            ORDER BY cnt DESC LIMIT 1
        """)
        row = cursor.fetchone()
        if row:
            insights.append({
                "type": "top_condamnare_court",
                "message": f"Instanța cu cele mai multe condamnări: {row[0]} cu {row[1]} cazuri",
                "value": row[1]
            })

        # Insight 3: Luna cu cele mai multe cazuri
        cursor.execute("""
            SELECT year, month, total_cases
            FROM agg_monthly_stats
            ORDER BY total_cases DESC LIMIT 1
        """)
        row = cursor.fetchone()
        if row:
            insights.append({
                "type": "peak_month",
                "message": f"Luna cu cele mai multe cazuri: {row[1]}/{row[0]} cu {row[2]} cazuri",
                "value": row[2]
            })

        return insights
