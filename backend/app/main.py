"""API de PHI.BET."""

from __future__ import annotations

import asyncio
import contextlib
import logging
from pathlib import Path
from typing import Literal

from fastapi import FastAPI, HTTPException, Query
from fastapi.staticfiles import StaticFiles

from app.config import load_settings
from app.runtime import Runtime
from app.service import PredictionEngine

logging.basicConfig(level=logging.INFO, format="%(asctime)s %(levelname)s %(name)s: %(message)s")
# httpx registra cada URL completa, y la de The Odds API lleva la clave: no debe acabar en los logs.
logging.getLogger("httpx").setLevel(logging.WARNING)
WEB_DIR = Path(__file__).resolve().parent.parent.parent / "web"

runtime = Runtime(load_settings())


@contextlib.asynccontextmanager
async def lifespan(_: FastAPI):
    task = None
    if runtime.live:
        await asyncio.to_thread(runtime.refresh_due)  # primera carga antes de aceptar peticiones
        task = asyncio.create_task(runtime.run_forever())
    yield
    if task:
        task.cancel()


app = FastAPI(title="PHI.BET", description="IA de análisis deportivo", version="0.5.0", lifespan=lifespan)


def engine() -> PredictionEngine:
    if runtime.engine is None:
        raise HTTPException(status_code=503, detail="Los datos todavía no están disponibles; mira /api/status")
    return runtime.engine


@app.get("/api/health")
def health() -> dict:
    e = runtime.engine
    return {
        "status": "ok" if e else "loading",
        "matches_trained": len(e.matches) if e else 0,
        "fixtures": len(e.fixtures) if e else 0,
    }


@app.get("/api/status")
def status() -> dict:
    return runtime.status()


@app.get("/api/predictions")
def predictions() -> list[dict]:
    return engine().predictions()


@app.get("/api/predictions/{fixture_id}")
def prediction(fixture_id: str) -> dict:
    e = engine()
    fixture = e.fixtures.get(fixture_id)
    if fixture is None:
        raise HTTPException(status_code=404, detail="Partido no encontrado")
    return e.predict(fixture)


@app.get("/api/performance")
def performance(recent: int = Query(20, ge=0, le=500)) -> dict:
    return engine().performance(recent)


@app.get("/api/picks")
def picks(
    min_prob: float = Query(0.6, ge=0.05, le=0.99, description="Acierto mínimo (probabilidad de la IA, 0–1)"),
    risk: Literal["low", "medium", "high"] = "low",
    combine: int = Query(1, ge=1, le=3, description="Máximo de selecciones por pronóstico"),
    date: str | None = None,
    value_only: bool = False,
    limit: int = Query(10, ge=1, le=50),
) -> dict:
    e = engine()
    if date is not None and date not in e.dates():
        raise HTTPException(status_code=404, detail="No hay partidos con cuotas ese día")
    return e.picks(date, min_prob, risk, combine, value_only, limit)


@app.get("/api/ratings")
def ratings() -> list[dict]:
    return engine().ratings()


if WEB_DIR.exists():
    app.mount("/", StaticFiles(directory=WEB_DIR, html=True), name="web")
