"""API de PHI.BET."""

from __future__ import annotations

from pathlib import Path
from typing import Literal

from fastapi import FastAPI, HTTPException, Query
from fastapi.staticfiles import StaticFiles

from app.service import PredictionEngine

WEB_DIR = Path(__file__).resolve().parent.parent.parent / "web"

app = FastAPI(title="PHI.BET", description="IA de análisis deportivo", version="0.4.0")
engine = PredictionEngine.from_disk()


@app.get("/api/health")
def health() -> dict:
    return {"status": "ok", "matches_trained": len(engine.matches), "fixtures": len(engine.fixtures)}


@app.get("/api/predictions")
def predictions() -> list[dict]:
    return engine.predictions()


@app.get("/api/predictions/{fixture_id}")
def prediction(fixture_id: str) -> dict:
    fixture = engine.fixtures.get(fixture_id)
    if fixture is None:
        raise HTTPException(status_code=404, detail="Partido no encontrado")
    return engine.predict(fixture)


@app.get("/api/performance")
def performance(recent: int = Query(20, ge=0, le=500)) -> dict:
    return engine.performance(recent)


@app.get("/api/picks")
def picks(
    min_prob: float = Query(0.6, ge=0.05, le=0.99, description="Acierto mínimo (probabilidad de la IA, 0–1)"),
    risk: Literal["low", "medium", "high"] = "low",
    combine: int = Query(1, ge=1, le=3, description="Máximo de selecciones por pronóstico"),
    date: str | None = None,
    value_only: bool = False,
    limit: int = Query(10, ge=1, le=50),
) -> dict:
    if date is not None and date not in engine.dates():
        raise HTTPException(status_code=404, detail="No hay partidos con cuotas ese día")
    return engine.picks(date, min_prob, risk, combine, value_only, limit)


@app.get("/api/ratings")
def ratings() -> list[dict]:
    return engine.ratings()


if WEB_DIR.exists():
    app.mount("/", StaticFiles(directory=WEB_DIR, html=True), name="web")
