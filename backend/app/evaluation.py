"""Rendimiento de la IA: evaluación "walk-forward" sobre partidos ya jugados.

Cada partido se predice entrenando el modelo solo con los partidos anteriores a su fecha,
como si la predicción se hubiera hecho antes de jugarse. Luego se compara con el resultado.
"""

from __future__ import annotations

import math
from collections import defaultdict
from typing import Callable

from app import markets
from app.data import Match
from app.models.poisson import PoissonModel

OUTCOMES = ("home", "draw", "away")
MIN_TRAINING = 56  # una temporada completa de 8 equipos antes de empezar a evaluar
CALIBRATION_BINS = 5
CONFIDENCE_THRESHOLDS = (0.5, 0.55, 0.6, 0.65, 0.7, 0.75, 0.8, 0.85, 0.9)


def outcome(home_goals: int, away_goals: int) -> str:
    if home_goals > away_goals:
        return "home"
    if home_goals == away_goals:
        return "draw"
    return "away"


def brier(probs: dict[str, float], actual: str) -> float:
    """Brier multiclase: 0 es perfecto, 2 es el peor posible."""
    return sum((probs[o] - (1.0 if o == actual else 0.0)) ** 2 for o in OUTCOMES)


def walk_forward(
    matches: list[Match], min_training: int = MIN_TRAINING, make_model: Callable[[], PoissonModel] = PoissonModel
) -> list[dict]:
    ordered = sorted(matches, key=lambda m: m.date)
    rows, model, trained_until = [], None, None
    for i, m in enumerate(ordered):
        if i < min_training:
            continue
        past = [p for p in ordered[:i] if p.date < m.date]
        if model is None or trained_until != len(past):  # reentrena una vez por jornada
            model, trained_until = make_model().fit(past), len(past)
        p = model.predict(m.home_team, m.away_team)
        probs = {"home": p.home, "draw": p.draw, "away": p.away}
        pick = max(probs, key=probs.get)
        actual = outcome(m.home_goals, m.away_goals)
        hits = markets.outcomes(m.home_goals, m.away_goals)
        rows.append(
            {
                "date": m.date,
                "home_team": m.home_team,
                "away_team": m.away_team,
                "home_goals": m.home_goals,
                "away_goals": m.away_goals,
                "probs": {o: round(v, 4) for o, v in probs.items()},
                "expected_goals": {"home": round(p.home_xg, 2), "away": round(p.away_xg, 2)},
                "pick": pick,
                "actual": actual,
                "correct": pick == actual,
                "brier": round(brier(probs, actual), 4),
                "log_loss": round(-math.log(max(probs[actual], 1e-12)), 4),
                "markets": {k: {"prob": round(v, 4), "hit": hits[k]} for k, v in markets.model_probabilities(p).items()},
            }
        )
    return rows


def hit_rate_at(rows: list[dict], threshold: float) -> dict:
    """De todas las selecciones (todos los mercados) a las que la IA dio >= threshold, cuántas acertaron."""
    hits = [sel["hit"] for r in rows for sel in r["markets"].values() if sel["prob"] >= threshold]
    return {
        "threshold": threshold,
        "count": len(hits),
        "hit_rate": round(sum(hits) / len(hits), 4) if hits else None,
    }


def summarize(rows: list[dict], training: list[Match] | None = None) -> dict:
    n = len(rows)
    if not n:
        return {"evaluated": 0, "accuracy": 0.0, "brier": 0.0, "log_loss": 0.0, "goals_mae": 0.0,
                "baseline_accuracy": 0.0, "baseline_brier": 0.0, "by_month": [], "calibration": []}

    # Referencia ingenua: predecir siempre las frecuencias históricas de 1/X/2.
    ref = training or []
    counts = defaultdict(int)
    for m in ref:
        counts[outcome(m.home_goals, m.away_goals)] += 1
    total = sum(counts.values())
    base = {o: counts[o] / total for o in OUTCOMES} if total else {o: 1 / 3 for o in OUTCOMES}
    base_pick = max(base, key=base.get)

    by_month: dict[str, list[dict]] = defaultdict(list)
    for r in rows:
        by_month[r["date"][:7]].append(r)

    # Calibración: de los resultados a los que la IA dio ~X% de probabilidad, ¿cuántos ocurrieron?
    bins = [{"predicted": 0.0, "hits": 0, "count": 0} for _ in range(CALIBRATION_BINS)]
    for r in rows:
        for o in OUTCOMES:
            p = r["probs"][o]
            b = bins[min(int(p * CALIBRATION_BINS), CALIBRATION_BINS - 1)]
            b["predicted"] += p
            b["count"] += 1
            b["hits"] += r["actual"] == o

    return {
        "evaluated": n,
        "accuracy": round(sum(r["correct"] for r in rows) / n, 4),
        "brier": round(sum(r["brier"] for r in rows) / n, 4),
        "log_loss": round(sum(r["log_loss"] for r in rows) / n, 4),
        "goals_mae": round(
            sum(abs(r["expected_goals"]["home"] - r["home_goals"]) + abs(r["expected_goals"]["away"] - r["away_goals"]) for r in rows)
            / (2 * n),
            3,
        ),
        "baseline_accuracy": round(sum(r["actual"] == base_pick for r in rows) / n, 4),
        "baseline_brier": round(sum(brier(base, r["actual"]) for r in rows) / n, 4),
        "by_month": [
            {
                "month": month,
                "matches": len(rs),
                "accuracy": round(sum(r["correct"] for r in rs) / len(rs), 4),
                "brier": round(sum(r["brier"] for r in rs) / len(rs), 4),
            }
            for month, rs in sorted(by_month.items())
        ],
        "by_confidence": [hit_rate_at(rows, t) for t in CONFIDENCE_THRESHOLDS],
        "calibration": [
            {
                "range": [i / CALIBRATION_BINS, (i + 1) / CALIBRATION_BINS],
                "count": b["count"],
                "predicted": round(b["predicted"] / b["count"], 4),
                "observed": round(b["hits"] / b["count"], 4),
            }
            for i, b in enumerate(bins)
            if b["count"]
        ],
    }
