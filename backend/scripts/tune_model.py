"""Ajuste del modelo con datos reales: prueba combinaciones de parámetros del Poisson con la
evaluación walk-forward sobre las 5 grandes ligas y las ordena por Brier.

Datos: repositorio público openfootball/football.json (resultados en JSON).
    git clone --depth 1 https://github.com/openfootball/football.json /tmp/football.json
    cd backend && ../.venv/bin/python scripts/tune_model.py /tmp/football.json
"""

from __future__ import annotations

import json
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

from app.data import Match  # noqa: E402
from app.evaluation import hit_rate_at, summarize, walk_forward  # noqa: E402
from app.models.poisson import PoissonModel  # noqa: E402

SEASONS = ["2023-24", "2024-25", "2025-26", "2026-27"]
LEAGUES = ["es.1", "en.1", "it.1", "de.1", "fr.1"]
GRID = [{"half_life_days": None, "prior_weight": 0.0, "rho": 0.0}] + [
    {"half_life_days": h, "prior_weight": k, "rho": r}
    for h in (180, 270, 365, 540, 730)
    for k in (0.0, 2.0, 3.0, 5.0)
    for r in (0.0, -0.05, -0.08, -0.12)
]


def load(root: Path, code: str) -> list[Match]:
    out = []
    for season in SEASONS:
        path = root / season / f"{code}.json"
        if not path.exists():
            continue
        for m in json.loads(path.read_text(encoding="utf-8"))["matches"]:
            score = m.get("score")
            ft = score.get("ft") if isinstance(score, dict) else score
            if ft:
                out.append(Match(m["date"], m["team1"], m["team2"], int(ft[0]), int(ft[1])))
    return sorted(out, key=lambda m: m.date)


def evaluate(leagues: dict[str, list[Match]], params: dict) -> dict:
    rows = []
    for matches in leagues.values():
        rows += walk_forward(matches, len(matches) // 3, lambda: PoissonModel(**params))
    s = summarize(rows)
    cases = sum(b["count"] for b in s["calibration"])
    s["calibration_error"] = sum(abs(b["predicted"] - b["observed"]) * b["count"] for b in s["calibration"]) / cases
    s["hit_80"] = hit_rate_at(rows, 0.8)
    return s


def main() -> None:
    root = Path(sys.argv[1])
    leagues = {code: load(root, code) for code in LEAGUES}
    results = [(params, evaluate(leagues, params)) for params in GRID]
    for params, s in sorted(results, key=lambda r: r[1]["brier"]):
        h = s["hit_80"]
        print(
            f"{params}  partidos={s['evaluated']} acierto={s['accuracy']:.4f} brier={s['brier']:.4f} "
            f"log-loss={s['log_loss']:.4f} calibración={s['calibration_error']:.4f} "
            f"≥80%: {h['hit_rate']:.3f} ({h['count']})"
        )


if __name__ == "__main__":
    main()
