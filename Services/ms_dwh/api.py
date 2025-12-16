#!/usr/bin/env python3
"""
DWH API - Expune date din warehouse pentru rapoarte și analiză
"""

from fastapi import FastAPI, HTTPException
from fastapi.responses import JSONResponse
from dwh_engine import DWHEngine

app = FastAPI(
    title="MS Data Warehouse",
    version="1.0.0",
    description="Microserviciu pentru agregare date și rapoarte analitice"
)

dwh = DWHEngine()

@app.get("/health")
def health():
    return {"status": "ok", "service": "ms_dwh"}


@app.get("/dwh/kpi")
def get_kpi():
    """Returnează KPI-uri generale ale sistemului"""
    try:
        kpi = dwh.get_kpi()
        return JSONResponse(content=kpi)
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))


@app.get("/dwh/trends/monthly")
def get_monthly_trends(limit: int = 12):
    """Returnează tendințe lunare (ultimele N luni)"""
    try:
        trends = dwh.get_monthly_trends(limit=limit)
        return JSONResponse(content={"trends": trends})
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))


@app.get("/dwh/courts/top")
def get_top_courts(limit: int = 10):
    """Returnează top instanțe după număr de cazuri"""
    try:
        courts = dwh.get_top_courts(limit=limit)
        return JSONResponse(content={"courts": courts})
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))


@app.get("/dwh/judges/top")
def get_top_judges(limit: int = 10):
    """Returnează top judecători după număr de cazuri"""
    try:
        judges = dwh.get_top_judges(limit=limit)
        return JSONResponse(content={"judges": judges})
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))


@app.get("/dwh/insights")
def get_insights():
    """Returnează insights automate generate din date"""
    try:
        insights = dwh.get_insights()
        return JSONResponse(content={"insights": insights})
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))


@app.get("/dwh/stats/summary")
def get_summary():
    """Returnează un rezumat complet cu toate statisticile"""
    try:
        kpi = dwh.get_kpi()
        trends = dwh.get_monthly_trends(limit=6)
        courts = dwh.get_top_courts(limit=5)
        judges = dwh.get_top_judges(limit=5)
        insights = dwh.get_insights()

        return JSONResponse(content={
            "kpi": kpi,
            "monthly_trends": trends,
            "top_courts": courts,
            "top_judges": judges,
            "insights": insights
        })
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))


@app.post("/dwh/compute")
def trigger_compute():
    """Trigger manual pentru a recomputa agregările"""
    try:
        dwh.compute_aggregates()
        return {"status": "success", "message": "Aggregates recomputed"}
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))
