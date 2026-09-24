"""Genera una liga sintética de ejemplo (histórico de partidos + próximas jornadas con cuotas).

Uso: python scripts/generate_sample_data.py   (desde backend/)
Es determinista (semilla fija). Sustituir por datos reales cuando haya proveedor.
"""

from __future__ import annotations

import csv
import json
import math
import random
import sys
from datetime import date, timedelta
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))
from app.markets import GROUP_TOTAL, SELECTIONS, model_probabilities  # noqa: E402
from app.models.poisson import MAX_GOALS, MatchProbabilities  # noqa: E402

SEED = 42
SEASONS = 3
UPCOMING_MATCHDAYS = 2
DATA_DIR = Path(__file__).resolve().parent.parent / "data"

# (equipo, ataque, defensa) — fuerzas "reales" ocultas que el modelo debe descubrir.
TEAMS = [
    ("Atlético Phi", 1.45, 0.70),
    ("Real Sigma", 1.35, 0.80),
    ("Deportivo Delta", 1.15, 0.95),
    ("Unión Omega", 1.05, 1.00),
    ("CD Lambda", 0.95, 1.05),
    ("Racing Gamma", 0.90, 1.15),
    ("Sporting Beta", 0.80, 1.20),
    ("CF Epsilon", 0.70, 1.35),
]
HOME_GOALS, AWAY_GOALS = 1.55, 1.15
MARGIN = 1.06  # margen de la casa ficticia (6%)
NOISE = 0.10  # error del "mercado" respecto a la probabilidad real (±10%)


def poisson(rng: random.Random, lam: float) -> int:
    limit, k, p = math.exp(-lam), 0, 1.0
    while True:
        p *= rng.random()
        if p <= limit:
            return k
        k += 1


def true_probabilities(lam_h: float, lam_a: float) -> MatchProbabilities:
    pmf = lambda k, lam: math.exp(-lam) * lam**k / math.factorial(k)  # noqa: E731
    home = draw = away = over = btts = 0.0
    for x in range(MAX_GOALS + 1):
        for y in range(MAX_GOALS + 1):
            p = pmf(x, lam_h) * pmf(y, lam_a)
            home += p * (x > y)
            draw += p * (x == y)
            away += p * (x < y)
            over += p * (x + y > 2)
            btts += p * (x > 0 and y > 0)
    total = home + draw + away
    return MatchProbabilities(lam_h, lam_a, home / total, draw / total, away / total, over / total, btts / total, (1, 1))


def bookmaker_odds(rng: random.Random, probs: dict[str, float]) -> dict[str, float]:
    """Cuotas de una casa ficticia: probabilidad real con ruido, normalizada por grupo y con margen."""
    noisy = {k: max(0.02, p * rng.uniform(1 - NOISE, 1 + NOISE)) for k, p in probs.items()}
    odds = {}
    for group, total in GROUP_TOTAL.items():
        keys = [k for k in SELECTIONS if SELECTIONS[k][2] == group]
        scale = total / sum(noisy[k] for k in keys)
        for k in keys:
            odds[k] = max(1.01, round(1 / (noisy[k] * scale * MARGIN), 2))
    return odds


def round_robin(names: list[str]) -> list[list[tuple[str, str]]]:
    """Calendario de ida y vuelta por el método del círculo: una lista de partidos por jornada."""
    teams = names[:]
    rounds = []
    for r in range(len(teams) - 1):
        pairs = [(teams[i], teams[-1 - i]) for i in range(len(teams) // 2)]
        rounds.append([(a, b) if r % 2 == 0 else (b, a) for a, b in pairs])
        teams = [teams[0], teams[-1], *teams[1:-1]]
    return rounds + [[(b, a) for a, b in rnd] for rnd in rounds]


def main() -> None:
    rng = random.Random(SEED)
    strength = {t: (a, d) for t, a, d in TEAMS}
    names = [t for t, _, _ in TEAMS]

    # Una jornada por semana, temporadas consecutivas.
    rows, day = [], date(2025, 12, 6)
    for _ in range(SEASONS):
        for matchday in round_robin(names):
            for home, away in matchday:
                lam_h = strength[home][0] * strength[away][1] * HOME_GOALS
                lam_a = strength[away][0] * strength[home][1] * AWAY_GOALS
                rows.append([day.isoformat(), home, away, poisson(rng, lam_h), poisson(rng, lam_a)])
            day += timedelta(days=7)

    with (DATA_DIR / "matches.csv").open("w", newline="", encoding="utf-8") as f:
        w = csv.writer(f)
        w.writerow(["date", "home_team", "away_team", "home_goals", "away_goals"])
        w.writerows(rows)

    # Próximas jornadas (sin resultado), una por semana, con cuotas.
    fixtures = []
    for week in range(UPCOMING_MATCHDAYS):
        shuffled = names[:]
        rng.shuffle(shuffled)
        for i in range(0, len(shuffled), 2):
            home, away = shuffled[i], shuffled[i + 1]
            lam_h = strength[home][0] * strength[away][1] * HOME_GOALS
            lam_a = strength[away][0] * strength[home][1] * AWAY_GOALS
            probs = model_probabilities(true_probabilities(lam_h, lam_a))
            fixtures.append(
                {
                    "id": f"f{len(fixtures) + 1}",
                    "date": (day + timedelta(days=7 * week)).isoformat(),
                    "home_team": home,
                    "away_team": away,
                    "odds": bookmaker_odds(rng, probs),
                }
            )

    with (DATA_DIR / "fixtures.json").open("w", encoding="utf-8") as f:
        json.dump(fixtures, f, ensure_ascii=False, indent=2)

    print(f"{len(rows)} partidos y {len(fixtures)} próximos partidos generados en {DATA_DIR}")


if __name__ == "__main__":
    main()
