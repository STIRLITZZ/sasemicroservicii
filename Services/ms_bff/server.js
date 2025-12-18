import express from "express";
import multer from "multer";
import fetch from "node-fetch";
import fs from "fs/promises";
import path from "path";
import { spawn } from "child_process";

const app = express();
const upload = multer({ storage: multer.memoryStorage() });

const CASE_EXTRACTOR_URL = process.env.CASE_EXTRACTOR_URL;
const INGESTION_URL = process.env.INGESTION_URL;
const DWH_URL = process.env.DWH_URL;

const TXT_DIR = process.env.TXT_DIR || "/data/txt";
const ENRICHED_FILE = process.env.ENRICHED_FILE || "/data/enriched/cases.json";
const STANDALONE_FILE = process.env.STANDALONE_FILE || "/data/standalone/cases.json";

// In-memory job storage pentru standalone processing
const standaloneJobs = new Map();

app.get("/api/health", async (req, res) => {
  const targets = [
    { name: "case-extractor", url: `${CASE_EXTRACTOR_URL}/health` },
    { name: "ingestion", url: `${INGESTION_URL}/docs` },
    { name: "dwh", url: `${DWH_URL}/health` }
  ];

  const out = {};
  await Promise.all(targets.map(async (t) => {
    try {
      const r = await fetch(t.url);
      out[t.name] = { ok: r.ok, status: r.status };
    } catch (e) {
      out[t.name] = { ok: false, error: String(e) };
    }
  }));

  res.json(out);
});

// TXT -> extractor
app.post("/api/extract/txt", upload.single("file"), async (req, res) => {
  if (!req.file) return res.status(400).json({ error: "No file uploaded" });

  const fd = new FormData();
  fd.append("file", new Blob([req.file.buffer], { type: "text/plain" }), req.file.originalname);

  const r = await fetch(`${CASE_EXTRACTOR_URL}/extract`, { method: "POST", body: fd });
  const txt = await r.text();
  res.status(r.status).send(txt);
});

    function safeName(s) {
  return String(s).replace(/[^\w\-.]/g, "_").slice(0, 180);
}

// ingestion run (date_range)
app.post("/api/ingestion/run", async (req, res) => {
  const date_range = req.query.date_range;
  if (!date_range) return res.status(400).json({ error: "date_range required" });

  const r = await fetch(`${INGESTION_URL}/run?date_range=${encodeURIComponent(date_range)}`, { method: "POST" });
  const txt = await r.text();
  res.status(r.status).send(txt);
});

// job status/result
app.get("/api/ingestion/jobs/:job_id", async (req, res) => {
  const jobId = req.params.job_id;
  try {
    const r = await fetch(`${INGESTION_URL}/jobs/${encodeURIComponent(jobId)}`);
    const txt = await r.text();
    res.status(r.status).send(txt);
  } catch (e) {
    res.status(500).json({ error: String(e) });
  }
});

// Endpoint pentru a obține date PDF extrase
app.get("/api/pdfdata/:job_id", async (req, res) => {
  const jobId = req.params.job_id;
  try {
    // Presupunem că ms_pdftext expune un endpoint
    const r = await fetch(`http://ms_pdftext:8000/results/${jobId}`);
    if (!r.ok) {
      return res.status(r.status).json({ error: "Eroare la ms_pdftext" });
    }
    const data = await r.json();
    res.json(data);
  } catch (e) {
    res.status(500).json({ error: String(e) });
  }
});

// DWH Endpoints - proxy pentru Data Warehouse API
app.get("/api/dwh/kpi", async (req, res) => {
  try {
    const r = await fetch(`${DWH_URL}/dwh/kpi`);
    const data = await r.json();
    res.json(data);
  } catch (e) {
    res.status(500).json({ error: "DWH KPI error", details: String(e) });
  }
});

app.get("/api/dwh/trends", async (req, res) => {
  try {
    const limit = req.query.limit || 12;
    const r = await fetch(`${DWH_URL}/dwh/trends/monthly?limit=${limit}`);
    const data = await r.json();
    res.json(data);
  } catch (e) {
    res.status(500).json({ error: "DWH trends error", details: String(e) });
  }
});

app.get("/api/dwh/courts/top", async (req, res) => {
  try {
    const limit = req.query.limit || 10;
    const r = await fetch(`${DWH_URL}/dwh/courts/top?limit=${limit}`);
    const data = await r.json();
    res.json(data);
  } catch (e) {
    res.status(500).json({ error: "DWH courts error", details: String(e) });
  }
});

app.get("/api/dwh/judges/top", async (req, res) => {
  try {
    const limit = req.query.limit || 10;
    const r = await fetch(`${DWH_URL}/dwh/judges/top?limit=${limit}`);
    const data = await r.json();
    res.json(data);
  } catch (e) {
    res.status(500).json({ error: "DWH judges error", details: String(e) });
  }
});

app.get("/api/dwh/insights", async (req, res) => {
  try {
    const r = await fetch(`${DWH_URL}/dwh/insights`);
    const data = await r.json();
    res.json(data);
  } catch (e) {
    res.status(500).json({ error: "DWH insights error", details: String(e) });
  }
});

app.get("/api/dwh/summary", async (req, res) => {
  try {
    const r = await fetch(`${DWH_URL}/dwh/stats/summary`);
    const data = await r.json();
    res.json(data);
  } catch (e) {
    res.status(500).json({ error: "DWH summary error", details: String(e) });
  }
});

// ============= STANDALONE PROCESSING =============
// Procesare completă fără Kafka/Docker - tot în backend

app.post("/api/standalone/run", async (req, res) => {
  const dateRange = req.query.date_range;
  if (!dateRange) {
    return res.status(400).json({ error: "date_range required" });
  }

  const maxPages = parseInt(req.query.max_pages) || 50;
  const jobId = `standalone-${Date.now()}`;

  // Inițializează job
  standaloneJobs.set(jobId, {
    status: "running",
    date_range: dateRange,
    started_at: new Date().toISOString(),
    progress: "Starting...",
    result: null,
    error: null
  });

  // Rulează procesarea în background
  const pythonScript = path.join(path.dirname(new URL(import.meta.url).pathname), "..", "standalone_processor.py");
  const outputFile = STANDALONE_FILE;

  const proc = spawn("python3", [pythonScript, dateRange, outputFile, maxPages.toString()]);

  let stdout = "";
  let stderr = "";

  proc.stdout.on("data", (data) => {
    stdout += data.toString();
    const lastLine = stdout.split("\n").filter(l => l.trim()).pop();
    if (lastLine) {
      standaloneJobs.get(jobId).progress = lastLine;
    }
  });

  proc.stderr.on("data", (data) => {
    stderr += data.toString();
  });

  proc.on("close", async (code) => {
    const job = standaloneJobs.get(jobId);

    if (code === 0) {
      // Success - citește rezultatele
      try {
        const data = await fs.readFile(outputFile, "utf-8");
        const cases = JSON.parse(data);

        job.status = "completed";
        job.result = {
          total: cases.length,
          cases: cases,
          output_file: outputFile
        };
        job.completed_at = new Date().toISOString();
      } catch (e) {
        job.status = "error";
        job.error = `Eroare citire rezultate: ${e.message}`;
      }
    } else {
      job.status = "error";
      job.error = stderr || "Procesare eșuată";
    }
  });

  res.json({
    job_id: jobId,
    status: "running",
    message: "Procesare pornită în background"
  });
});

// Status job standalone
app.get("/api/standalone/jobs/:job_id", async (req, res) => {
  const jobId = req.params.job_id;
  const job = standaloneJobs.get(jobId);

  if (!job) {
    return res.status(404).json({ error: "Job not found" });
  }

  res.json(job);
});

// Lista toate cazurile standalone (cu filtrare)
app.get("/api/standalone/cases", async (req, res) => {
  try {
    const data = await fs.readFile(STANDALONE_FILE, "utf-8");
    const cases = JSON.parse(data);

    // Filtrare pe interval de date (dacă e specificat)
    let filtered = cases;
    const startDate = req.query.start_date;
    const endDate = req.query.end_date;

    if (startDate || endDate) {
      filtered = cases.filter(c => {
        const caseDate = c.data_inreg || c.data_publ;
        if (!caseDate) return false;

        const caseDateStr = caseDate.split(' ')[0];

        if (startDate && caseDateStr < startDate) return false;
        if (endDate && caseDateStr > endDate) return false;

        return true;
      });
    }

    // Paginare
    const limit = parseInt(req.query.limit) || 1000;
    const offset = parseInt(req.query.offset) || 0;

    const paginated = filtered.slice(offset, offset + limit);

    res.json({
      total: filtered.length,
      total_unfiltered: cases.length,
      limit,
      offset,
      start_date: startDate || null,
      end_date: endDate || null,
      cases: paginated,
      mode: "standalone"
    });
  } catch (e) {
    if (e.code === "ENOENT") {
      res.json({ total: 0, cases: [], mode: "standalone" });
    } else {
      res.status(500).json({ error: "Could not read standalone cases", details: String(e) });
    }
  }
});

app.listen(8081, () => console.log("ms_bff running on :8081"));

app.get("/api/text/by-dosar", async (req, res) => {
  const dosar = req.query.dosar;
  if (!dosar) return res.status(400).json({ error: "dosar required" });

  try {
    const filePath = path.join(TXT_DIR, `${safeName(dosar)}.txt`);
    const text = await fs.readFile(filePath, "utf-8");
    res.json({ dosar, chars: text.length, preview: text.slice(0, 3000), path: filePath });
  } catch (e) {
    // dacă încă nu a fost procesat de ms_pdftext (Kafka), o să pice aici
    res.status(404).json({ error: "text not ready / file not found", details: String(e) });
  }
});

// Endpoint pentru date enriched (procesate complet)
app.get("/api/cases", async (req, res) => {
  try {
    const data = await fs.readFile(ENRICHED_FILE, "utf-8");
    const cases = JSON.parse(data);

    // Filtrare pe interval de date (dacă e specificat)
    let filtered = cases;
    const startDate = req.query.start_date;
    const endDate = req.query.end_date;

    if (startDate || endDate) {
      filtered = cases.filter(c => {
        // Verifică dacă cazul are dată de înregistrare
        const caseDate = c.data_inregistrare || c.data_publicare;
        if (!caseDate) return false;

        // Convertește datele în format comparabil (YYYY-MM-DD)
        const caseDateStr = caseDate.split(' ')[0]; // Ia doar data, fără oră

        // Verifică dacă se încadrează în interval
        if (startDate && caseDateStr < startDate) return false;
        if (endDate && caseDateStr > endDate) return false;

        return true;
      });
    }

    // Paginare
    const limit = parseInt(req.query.limit) || 1000;
    const offset = parseInt(req.query.offset) || 0;

    const paginated = filtered.slice(offset, offset + limit);

    res.json({
      total: filtered.length,
      total_unfiltered: cases.length,
      limit,
      offset,
      start_date: startDate || null,
      end_date: endDate || null,
      cases: paginated
    });
  } catch (e) {
    if (e.code === "ENOENT") {
      // Fișierul nu există încă
      res.json({ total: 0, cases: [] });
    } else {
      res.status(500).json({ error: "Could not read cases", details: String(e) });
    }
  }
});
