"""API de PHI.BET."""

from __future__ import annotations

import os
from pathlib import Path
from typing import Literal

from fastapi import FastAPI, HTTPException, Response
from fastapi.staticfiles import StaticFiles
from pydantic import BaseModel, Field

from app.data import DATA_DIR
from app.ledger import Ledger, LedgerError
from app.service import PredictionEngine

WEB_DIR = Path(__file__).resolve().parent.parent.parent / "web"

app = FastAPI(title="PHI.BET", description="IA para análisis de apuestas deportivas", version="0.2.0")
engine = PredictionEngine.from_disk()
ledger = Ledger(os.environ.get("PHIBET_DB", DATA_DIR / "phibet.db"))


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


@app.get("/api/value-bets")
def value_bets() -> list[dict]:
    return engine.value_bets()


@app.get("/api/ratings")
def ratings() -> list[dict]:
    return engine.ratings()


# --- Contabilidad y P&L -------------------------------------------------------


class TransactionIn(BaseModel):
    type: Literal["deposit", "withdrawal"]
    amount: float = Field(gt=0)
    note: str = ""
    date: str | None = None


class BetIn(BaseModel):
    event: str = Field(min_length=1)
    market: str = "1X2"
    selection: str = Field(min_length=1)
    odds: float = Field(gt=1)
    stake: float = Field(gt=0)
    fixture_id: str | None = None
    bookmaker: str = ""
    model_prob: float | None = Field(default=None, ge=0, le=1)
    placed_at: str | None = None


class SettleIn(BaseModel):
    result: Literal["won", "lost", "void"]
    settled_at: str | None = None


def _ledger_call(fn, *args, **kwargs):
    try:
        return fn(*args, **kwargs)
    except LedgerError as e:
        raise HTTPException(status_code=400, detail=str(e))
    except KeyError:
        raise HTTPException(status_code=404, detail="Apuesta no encontrada")


@app.get("/api/accounting/summary")
def accounting_summary() -> dict:
    return ledger.summary()


@app.get("/api/accounting/transactions")
def list_transactions() -> list[dict]:
    return ledger.transactions()


@app.post("/api/accounting/transactions", status_code=201)
def create_transaction(tx: TransactionIn) -> dict:
    return _ledger_call(ledger.add_transaction, **tx.model_dump())


@app.get("/api/accounting/bets")
def list_bets(status: Literal["pending", "won", "lost", "void"] | None = None) -> list[dict]:
    return ledger.bets(status)


@app.post("/api/accounting/bets", status_code=201)
def create_bet(bet: BetIn) -> dict:
    return _ledger_call(ledger.place_bet, **bet.model_dump())


@app.post("/api/accounting/bets/{bet_id}/settle")
def settle_bet(bet_id: int, body: SettleIn) -> dict:
    return _ledger_call(ledger.settle_bet, bet_id, body.result, body.settled_at)


@app.delete("/api/accounting/bets/{bet_id}", status_code=204)
def delete_bet(bet_id: int) -> Response:
    _ledger_call(ledger.delete_bet, bet_id)
    return Response(status_code=204)


@app.get("/api/accounting/pnl")
def pnl(group: Literal["month", "day", "market"] = "month") -> list[dict]:
    return ledger.pnl(group)


@app.get("/api/accounting/equity")
def equity() -> list[dict]:
    return ledger.equity_curve()


@app.get("/api/accounting/export.csv")
def export_csv() -> Response:
    return Response(
        content=ledger.export_csv(),
        media_type="text/csv; charset=utf-8",
        headers={"Content-Disposition": 'attachment; filename="phibet-contabilidad.csv"'},
    )


if WEB_DIR.exists():
    app.mount("/", StaticFiles(directory=WEB_DIR, html=True), name="web")
