import express from "express";
import multer from "multer";
import fetch from "node-fetch";

const app = express();
const upload = multer({ storage: multer.memoryStorage() });

const CASE_EXTRACTOR_URL = process.env.CASE_EXTRACTOR_URL;
const INGESTION_URL = process.env.INGESTION_URL;

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

// ingestion run (date_range)
app.post("/api/ingestion/run", async (req, res) => {
  const date_range = req.query.date_range;
  if (!date_range) return res.status(400).json({ error: "date_range required" });

  const r = await fetch(`${INGESTION_URL}/run?date_range=${encodeURIComponent(date_range)}`, { method: "POST" });
  const txt = await r.text();
  res.status(r.status).send(txt);
});

app.listen(8081, () => console.log("ms_bff running on :8081"));
