"""Contabilidad: banca, movimientos, registro de apuestas y pérdidas y ganancias (P&L).

Persistencia en SQLite (librería estándar). La ruta sale de la variable PHIBET_DB.
"""

from __future__ import annotations

import csv
import io
import sqlite3
import threading
from datetime import datetime, timezone
from pathlib import Path

RESULTS = ("won", "lost", "void")

SCHEMA = """
CREATE TABLE IF NOT EXISTS transactions (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    date TEXT NOT NULL,
    type TEXT NOT NULL CHECK (type IN ('deposit', 'withdrawal')),
    amount REAL NOT NULL CHECK (amount > 0),
    note TEXT NOT NULL DEFAULT ''
);
CREATE TABLE IF NOT EXISTS bets (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    placed_at TEXT NOT NULL,
    fixture_id TEXT,
    event TEXT NOT NULL,
    market TEXT NOT NULL,
    selection TEXT NOT NULL,
    odds REAL NOT NULL CHECK (odds > 1),
    stake REAL NOT NULL CHECK (stake > 0),
    bookmaker TEXT NOT NULL DEFAULT '',
    model_prob REAL,
    status TEXT NOT NULL DEFAULT 'pending' CHECK (status IN ('pending', 'won', 'lost', 'void')),
    settled_at TEXT,
    profit REAL
);
"""


class LedgerError(ValueError):
    """Operación contable no válida (saldo insuficiente, apuesta ya liquidada...)."""


def _now() -> str:
    return datetime.now(timezone.utc).isoformat(timespec="seconds")


def bet_profit(result: str, stake: float, odds: float) -> float:
    if result == "won":
        return round(stake * (odds - 1), 2)
    if result == "lost":
        return -stake
    return 0.0


class Ledger:
    def __init__(self, path: str | Path) -> None:
        if str(path) != ":memory:":
            Path(path).parent.mkdir(parents=True, exist_ok=True)
        self._db = sqlite3.connect(str(path), check_same_thread=False)
        self._db.row_factory = sqlite3.Row
        self._lock = threading.Lock()
        with self._lock:
            self._db.executescript(SCHEMA)

    def _query(self, sql: str, params: tuple = ()) -> list[dict]:
        with self._lock:
            return [dict(r) for r in self._db.execute(sql, params).fetchall()]

    def _write(self, sql: str, params: tuple = ()) -> int:
        with self._lock, self._db:
            return self._db.execute(sql, params).lastrowid

    # --- Movimientos de banca -------------------------------------------------

    def add_transaction(self, type: str, amount: float, note: str = "", date: str | None = None) -> dict:
        if type not in ("deposit", "withdrawal"):
            raise LedgerError("Tipo de movimiento no válido")
        if amount <= 0:
            raise LedgerError("El importe debe ser positivo")
        if type == "withdrawal" and amount > self.balance()["available"] + 1e-9:
            raise LedgerError("Saldo disponible insuficiente para retirar")
        tx_id = self._write(
            "INSERT INTO transactions (date, type, amount, note) VALUES (?, ?, ?, ?)",
            (date or _now(), type, round(amount, 2), note),
        )
        return self._query("SELECT * FROM transactions WHERE id = ?", (tx_id,))[0]

    def transactions(self) -> list[dict]:
        return self._query("SELECT * FROM transactions ORDER BY date DESC, id DESC")

    # --- Apuestas -------------------------------------------------------------

    def place_bet(
        self,
        event: str,
        market: str,
        selection: str,
        odds: float,
        stake: float,
        fixture_id: str | None = None,
        bookmaker: str = "",
        model_prob: float | None = None,
        placed_at: str | None = None,
    ) -> dict:
        if odds <= 1:
            raise LedgerError("La cuota debe ser mayor que 1")
        if stake <= 0:
            raise LedgerError("El importe apostado debe ser positivo")
        if stake > self.balance()["available"] + 1e-9:
            raise LedgerError("Saldo disponible insuficiente para esta apuesta")
        bet_id = self._write(
            """INSERT INTO bets (placed_at, fixture_id, event, market, selection, odds, stake, bookmaker, model_prob)
               VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?)""",
            (placed_at or _now(), fixture_id, event, market, selection, odds, round(stake, 2), bookmaker, model_prob),
        )
        return self.bet(bet_id)

    def bet(self, bet_id: int) -> dict:
        rows = self._query("SELECT * FROM bets WHERE id = ?", (bet_id,))
        if not rows:
            raise KeyError(bet_id)
        return rows[0]

    def bets(self, status: str | None = None) -> list[dict]:
        if status:
            return self._query("SELECT * FROM bets WHERE status = ? ORDER BY placed_at DESC, id DESC", (status,))
        return self._query("SELECT * FROM bets ORDER BY placed_at DESC, id DESC")

    def settle_bet(self, bet_id: int, result: str, settled_at: str | None = None) -> dict:
        if result not in RESULTS:
            raise LedgerError("Resultado no válido (won, lost o void)")
        bet = self.bet(bet_id)
        if bet["status"] != "pending":
            raise LedgerError("La apuesta ya está liquidada")
        self._write(
            "UPDATE bets SET status = ?, settled_at = ?, profit = ? WHERE id = ?",
            (result, settled_at or _now(), bet_profit(result, bet["stake"], bet["odds"]), bet_id),
        )
        return self.bet(bet_id)

    def delete_bet(self, bet_id: int) -> None:
        bet = self.bet(bet_id)
        if bet["status"] != "pending":
            raise LedgerError("Solo se pueden borrar apuestas pendientes")
        self._write("DELETE FROM bets WHERE id = ?", (bet_id,))

    # --- Informes -------------------------------------------------------------

    def balance(self) -> dict:
        tx = self._query(
            """SELECT COALESCE(SUM(CASE WHEN type = 'deposit' THEN amount END), 0) AS deposits,
                      COALESCE(SUM(CASE WHEN type = 'withdrawal' THEN amount END), 0) AS withdrawals
               FROM transactions"""
        )[0]
        bets = self._query(
            """SELECT COALESCE(SUM(profit), 0) AS profit,
                      COALESCE(SUM(CASE WHEN status = 'pending' THEN stake END), 0) AS exposure
               FROM bets"""
        )[0]
        bankroll = tx["deposits"] - tx["withdrawals"] + bets["profit"]
        return {
            "deposits": round(tx["deposits"], 2),
            "withdrawals": round(tx["withdrawals"], 2),
            "bankroll": round(bankroll, 2),
            "exposure": round(bets["exposure"], 2),
            "available": round(bankroll - bets["exposure"], 2),
        }

    def summary(self) -> dict:
        settled = self._query("SELECT * FROM bets WHERE status != 'pending' ORDER BY settled_at, id")
        decided = [b for b in settled if b["status"] != "void"]
        staked = sum(b["stake"] for b in decided)
        profit = sum(b["profit"] for b in settled)
        wins = sum(1 for b in decided if b["status"] == "won")

        # Máxima caída (drawdown) sobre la curva de beneficio acumulado.
        peak = cum = max_dd = 0.0
        for b in settled:
            cum += b["profit"]
            peak = max(peak, cum)
            max_dd = max(max_dd, peak - cum)

        return {
            **self.balance(),
            "bets_total": len(settled) + len(self.bets("pending")),
            "bets_pending": len(self.bets("pending")),
            "bets_settled": len(settled),
            "won": wins,
            "lost": sum(1 for b in decided if b["status"] == "lost"),
            "void": len(settled) - len(decided),
            "staked": round(staked, 2),
            "profit": round(profit, 2),
            "yield": round(profit / staked, 4) if staked else 0.0,
            "hit_rate": round(wins / len(decided), 4) if decided else 0.0,
            "avg_odds": round(sum(b["odds"] for b in decided) / len(decided), 2) if decided else 0.0,
            "max_drawdown": round(max_dd, 2),
        }

    def pnl(self, group: str = "month") -> list[dict]:
        """P&L de apuestas liquidadas, agrupado por 'month', 'day' o 'market'."""
        keys = {"month": "substr(settled_at, 1, 7)", "day": "substr(settled_at, 1, 10)", "market": "market"}
        if group not in keys:
            raise LedgerError("Agrupación no válida (month, day o market)")
        rows = self._query(
            f"""SELECT {keys[group]} AS period,
                       COUNT(*) AS bets,
                       SUM(CASE WHEN status = 'won' THEN 1 ELSE 0 END) AS won,
                       SUM(CASE WHEN status != 'void' THEN stake ELSE 0 END) AS staked,
                       SUM(profit) AS profit
                FROM bets WHERE status != 'pending'
                GROUP BY period ORDER BY period"""
        )
        for r in rows:
            r["staked"] = round(r["staked"], 2)
            r["profit"] = round(r["profit"], 2)
            r["yield"] = round(r["profit"] / r["staked"], 4) if r["staked"] else 0.0
        return rows

    def equity_curve(self) -> list[dict]:
        """Beneficio acumulado tras cada apuesta liquidada."""
        cum, points = 0.0, []
        for b in self._query("SELECT id, settled_at, event, profit FROM bets WHERE status != 'pending' ORDER BY settled_at, id"):
            cum += b["profit"]
            points.append({"bet_id": b["id"], "date": b["settled_at"], "event": b["event"], "profit": b["profit"], "cumulative": round(cum, 2)})
        return points

    def export_csv(self) -> str:
        """Libro contable: movimientos y apuestas en un único CSV, en orden cronológico."""
        rows = [
            [t["date"], "deposito" if t["type"] == "deposit" else "retirada", t["note"], "", "", "",
             t["amount"] if t["type"] == "deposit" else -t["amount"]]
            for t in self._query("SELECT * FROM transactions")
        ]
        for b in self._query("SELECT * FROM bets"):
            rows.append([b["placed_at"], "apuesta", b["event"], b["selection"], b["odds"], b["stake"], ""])
            if b["status"] != "pending":
                rows.append([b["settled_at"], f"liquidacion:{b['status']}", b["event"], b["selection"], b["odds"], b["stake"], b["profit"]])
        rows.sort(key=lambda r: r[0])
        out = io.StringIO()
        w = csv.writer(out)
        w.writerow(["fecha", "concepto", "evento", "seleccion", "cuota", "stake", "importe"])
        w.writerows(rows)
        return out.getvalue()
