import express from "express";
import multer from "multer";
import fetch from "node-fetch";
import fs from "fs/promises";
import path from "path";

const app = express();
const upload = multer({ storage: multer.memoryStorage() });

const CASE_EXTRACTOR_URL = process.env.CASE_EXTRACTOR_URL;
const INGESTION_URL = process.env.INGESTION_URL;

const TXT_DIR = process.env.TXT_DIR || "/data/txt";
const ENRICHED_FILE = process.env.ENRICHED_FILE || "/data/enriched/cases.json";

app.get("/api/health", async (req, res) => {
  const targets = [
    { name: "case-extractor", url: `${CASE_EXTRACTOR_URL}/health` },
    { name: "ingestion", url: `${INGESTION_URL}/docs` } // dacă nu ai /health la ingestion, /docs e ok ca test
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

    // Opțional: filtrare și paginare
    const limit = parseInt(req.query.limit) || 1000;
    const offset = parseInt(req.query.offset) || 0;

    const filtered = cases.slice(offset, offset + limit);

    res.json({
      total: cases.length,
      limit,
      offset,
      cases: filtered
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
