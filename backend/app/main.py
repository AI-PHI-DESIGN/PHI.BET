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
        # La primera carga se hace en segundo plano: el servidor responde desde el primer segundo
        # (/api/health dice "loading" y la web espera) aunque descargar y entrenar tarde un rato.
        task = asyncio.create_task(runtime.run_forever())
    yield
    if task:
        task.cancel()


app = FastAPI(title="PHI.BET", description="IA de análisis deportivo", version="0.6.0", lifespan=lifespan)


LeagueParam = Query(None, description="Liga (ver /api/leagues); por defecto, la primera con datos")


def engine(league: str | None = None) -> PredictionEngine:
    if league is not None and league not in runtime.leagues:
        raise HTTPException(status_code=404, detail=f"Liga desconocida; disponibles: {', '.join(runtime.leagues)}")
    e = runtime.engine(league)
    if e is None:
        raise HTTPException(status_code=503, detail="Los datos todavía no están disponibles; mira /api/status")
    return e


@app.get("/api/health")
def health() -> dict:
    engines = [d.engine for d in runtime.leagues.values() if d.engine is not None]
    return {
        "status": "ok" if engines else "loading",
        "leagues_ready": len(engines),
        "matches_trained": sum(len(e.matches) for e in engines),
        "fixtures": sum(len(e.fixtures) for e in engines),
    }


@app.get("/api/leagues")
def leagues() -> list[dict]:
    return runtime.league_list()


@app.get("/api/status")
def status() -> dict:
    return runtime.status()


@app.get("/api/predictions")
def predictions(league: str | None = LeagueParam) -> list[dict]:
    return engine(league).predictions()


@app.get("/api/predictions/{fixture_id}")
def prediction(fixture_id: str, league: str | None = LeagueParam) -> dict:
    e = engine(league)
    fixture = e.fixtures.get(fixture_id)
    if fixture is None:
        raise HTTPException(status_code=404, detail="Partido no encontrado")
    return e.predict(fixture)


@app.get("/api/performance")
def performance(recent: int = Query(20, ge=0, le=500), league: str | None = LeagueParam) -> dict:
    return engine(league).performance(recent)


@app.get("/api/picks")
def picks(
    min_prob: float = Query(0.6, ge=0.05, le=0.99, description="Acierto mínimo (probabilidad de la IA, 0–1)"),
    risk: Literal["low", "medium", "high"] = "low",
    combine: int = Query(1, ge=1, le=3, description="Máximo de selecciones por pronóstico"),
    date: str | None = None,
    value_only: bool = False,
    limit: int = Query(10, ge=1, le=50),
    league: str | None = LeagueParam,
) -> dict:
    e = engine(league)
    if date is not None and date not in e.dates():
        raise HTTPException(status_code=404, detail="No hay partidos con cuotas ese día")
    return e.picks(date, min_prob, risk, combine, value_only, limit)


@app.get("/api/ratings")
def ratings(league: str | None = LeagueParam) -> list[dict]:
    return engine(league).ratings()


if WEB_DIR.exists():
    app.mount("/", StaticFiles(directory=WEB_DIR, html=True), name="web")
