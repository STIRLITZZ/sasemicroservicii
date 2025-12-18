#!/usr/bin/env python3
"""
Server Python simplu care înlocuiește ms_bff pentru modul standalone.
Servește UI-ul și rulează procesarea standalone.
"""

import json
import os
import subprocess
import threading
import time
from datetime import datetime
from http.server import HTTPServer, SimpleHTTPRequestHandler
from pathlib import Path
from urllib.parse import parse_qs, urlparse

# Configurare
PORT = 8081
WEB_UI_DIR = "./web_ui"
STANDALONE_FILE = "./data/standalone/cases.json"

# Storage in-memory pentru jobs
jobs = {}


class StandaloneHandler(SimpleHTTPRequestHandler):
    """HTTP Handler pentru API-uri standalone"""

    def do_GET(self):
        parsed_path = urlparse(self.path)
        path = parsed_path.path
        query = parse_qs(parsed_path.query)

        # Servește fișiere statice din web_ui
        if not path.startswith('/api/'):
            # Schimbă directorul pentru static files
            if path == '/':
                path = '/index.html'

            file_path = os.path.join(WEB_UI_DIR, path.lstrip('/'))

            if os.path.exists(file_path) and os.path.isfile(file_path):
                self.send_response(200)

                # Determină content type
                if file_path.endswith('.html'):
                    self.send_header('Content-type', 'text/html')
                elif file_path.endswith('.js'):
                    self.send_header('Content-type', 'application/javascript')
                elif file_path.endswith('.css'):
                    self.send_header('Content-type', 'text/css')
                elif file_path.endswith('.json'):
                    self.send_header('Content-type', 'application/json')
                else:
                    self.send_header('Content-type', 'text/plain')

                self.end_headers()

                with open(file_path, 'rb') as f:
                    self.wfile.write(f.read())
            else:
                self.send_error(404, f"File not found: {path}")
            return

        # API Endpoints
        if path.startswith('/api/standalone/jobs/'):
            job_id = path.split('/')[-1]
            self.handle_job_status(job_id)
        elif path == '/api/standalone/cases':
            self.handle_get_cases(query)
        elif path == '/api/health':
            self.handle_health()
        else:
            self.send_error(404, "API endpoint not found")

    def do_POST(self):
        parsed_path = urlparse(self.path)
        path = parsed_path.path
        query = parse_qs(parsed_path.query)

        if path == '/api/standalone/run':
            self.handle_run_standalone(query)
        else:
            self.send_error(404, "API endpoint not found")

    def handle_health(self):
        """Health check endpoint"""
        self.send_json_response({
            "status": "ok",
            "mode": "standalone",
            "timestamp": datetime.now().isoformat()
        })

    def handle_run_standalone(self, query):
        """Pornește procesare standalone"""
        date_range = query.get('date_range', [None])[0]

        if not date_range:
            self.send_json_response({"error": "date_range required"}, status=400)
            return

        max_pages = int(query.get('max_pages', ['20'])[0])  # Default 20 pentru viteză
        job_id = f"standalone-{int(time.time() * 1000)}"

        # Inițializează job
        jobs[job_id] = {
            "status": "running",
            "date_range": date_range,
            "started_at": datetime.now().isoformat(),
            "progress": "Starting...",
            "result": None,
            "error": None
        }

        # Pornește procesarea în background
        def run_processing():
            try:
                # Rulează scriptul Python
                result = subprocess.run(
                    ['python', 'standalone_processor.py', date_range, STANDALONE_FILE, str(max_pages)],
                    capture_output=True,
                    text=True,
                    cwd=os.path.dirname(os.path.abspath(__file__))
                )

                job = jobs[job_id]

                if result.returncode == 0:
                    # Success - citește rezultatele
                    try:
                        with open(STANDALONE_FILE, 'r', encoding='utf-8') as f:
                            cases = json.load(f)

                        job["status"] = "completed"
                        job["result"] = {
                            "total": len(cases),
                            "output_file": STANDALONE_FILE
                        }
                        job["completed_at"] = datetime.now().isoformat()
                        job["progress"] = f"Finalizat: {len(cases)} cazuri procesate"
                    except Exception as e:
                        job["status"] = "error"
                        job["error"] = f"Eroare citire rezultate: {str(e)}"
                else:
                    job["status"] = "error"
                    job["error"] = result.stderr or "Procesare eșuată"

            except Exception as e:
                jobs[job_id]["status"] = "error"
                jobs[job_id]["error"] = str(e)

        # Start thread pentru procesare
        thread = threading.Thread(target=run_processing, daemon=True)
        thread.start()

        self.send_json_response({
            "job_id": job_id,
            "status": "running",
            "message": "Procesare pornită în background"
        })

    def handle_job_status(self, job_id):
        """Verifică statusul unui job"""
        if job_id not in jobs:
            self.send_json_response({"error": "Job not found"}, status=404)
            return

        self.send_json_response(jobs[job_id])

    def handle_get_cases(self, query):
        """Returnează cazurile procesate"""
        try:
            with open(STANDALONE_FILE, 'r', encoding='utf-8') as f:
                cases = json.load(f)

            # Filtrare pe date
            start_date = query.get('start_date', [None])[0]
            end_date = query.get('end_date', [None])[0]

            filtered = cases
            if start_date or end_date:
                filtered = []
                for case in cases:
                    case_date = case.get('data_inreg') or case.get('data_publ', '')
                    if not case_date:
                        continue

                    case_date_str = case_date.split(' ')[0]

                    if start_date and case_date_str < start_date:
                        continue
                    if end_date and case_date_str > end_date:
                        continue

                    filtered.append(case)

            # Paginare
            limit = int(query.get('limit', ['1000'])[0])
            offset = int(query.get('offset', ['0'])[0])

            paginated = filtered[offset:offset + limit]

            self.send_json_response({
                "total": len(filtered),
                "total_unfiltered": len(cases),
                "limit": limit,
                "offset": offset,
                "start_date": start_date,
                "end_date": end_date,
                "cases": paginated,
                "mode": "standalone"
            })

        except FileNotFoundError:
            self.send_json_response({
                "total": 0,
                "cases": [],
                "mode": "standalone"
            })
        except Exception as e:
            self.send_json_response({
                "error": "Could not read cases",
                "details": str(e)
            }, status=500)

    def send_json_response(self, data, status=200):
        """Helper pentru a trimite răspuns JSON"""
        self.send_response(status)
        self.send_header('Content-type', 'application/json')
        self.send_header('Access-Control-Allow-Origin', '*')
        self.end_headers()
        self.wfile.write(json.dumps(data, ensure_ascii=False).encode('utf-8'))

    def log_message(self, format, *args):
        """Override pentru logging mai curat"""
        print(f"[{datetime.now().strftime('%H:%M:%S')}] {format % args}")


def main():
    # Creează directoare necesare
    Path("./data/standalone").mkdir(parents=True, exist_ok=True)

    # Verifică că web_ui există
    if not os.path.exists(WEB_UI_DIR):
        print(f"EROARE: Directorul {WEB_UI_DIR} nu există!")
        print(f"Rulează scriptul din directorul Services/")
        return

    # Pornește serverul
    server_address = ('', PORT)
    httpd = HTTPServer(server_address, StandaloneHandler)

    print(f"=" * 60)
    print(f"🚀 Server Python pornit!")
    print(f"=" * 60)
    print(f"📍 Web UI:  http://localhost:{PORT}")
    print(f"📍 API:     http://localhost:{PORT}/api/")
    print(f"📁 Data:    {os.path.abspath('./data/standalone/')}")
    print(f"=" * 60)
    print(f"🎯 Deschide browser la: http://localhost:{PORT}")
    print(f"✅ Bifează 'Mod Standalone' și apasă 'Start'")
    print(f"=" * 60)
    print(f"\nServer rulează... (Ctrl+C pentru oprire)\n")

    try:
        httpd.serve_forever()
    except KeyboardInterrupt:
        print("\n\n👋 Server oprit.")


if __name__ == "__main__":
    main()
