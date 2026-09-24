"""Genera una liga sintética de ejemplo (histórico + próximos partidos con cuotas).

Uso: python scripts/generate_sample_data.py   (desde backend/)
Es determinista (semilla fija). Sustituir por datos reales cuando haya proveedor.
"""

from __future__ import annotations

import csv
import itertools
import json
import math
import random
from datetime import date, timedelta
from pathlib import Path

SEED = 42
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


def poisson(rng: random.Random, lam: float) -> int:
    limit, k, p = math.exp(-lam), 0, 1.0
    while True:
        p *= rng.random()
        if p <= limit:
            return k
        k += 1


def main() -> None:
    rng = random.Random(SEED)
    strength = {t: (a, d) for t, a, d in TEAMS}
    names = [t for t, _, _ in TEAMS]

    # Dos temporadas de ida y vuelta.
    rows, day = [], date(2025, 8, 16)
    for _ in range(2):
        for home, away in itertools.permutations(names, 2):
            lam_h = strength[home][0] * strength[away][1] * HOME_GOALS
            lam_a = strength[away][0] * strength[home][1] * AWAY_GOALS
            rows.append([day.isoformat(), home, away, poisson(rng, lam_h), poisson(rng, lam_a)])
            day += timedelta(days=1)

    with (DATA_DIR / "matches.csv").open("w", newline="", encoding="utf-8") as f:
        w = csv.writer(f)
        w.writerow(["date", "home_team", "away_team", "home_goals", "away_goals"])
        w.writerows(rows)

    # Próxima jornada: cuotas con margen del 6% y algo de ruido del "mercado".
    shuffled = names[:]
    rng.shuffle(shuffled)
    fixtures, kickoff = [], date(2026, 10, 3)
    for i in range(0, len(shuffled), 2):
        home, away = shuffled[i], shuffled[i + 1]
        lam_h = strength[home][0] * strength[away][1] * HOME_GOALS
        lam_a = strength[away][0] * strength[home][1] * AWAY_GOALS
        ph = pd = pa = 0.0
        for x in range(11):
            for y in range(11):
                p = (math.exp(-lam_h) * lam_h**x / math.factorial(x)) * (
                    math.exp(-lam_a) * lam_a**y / math.factorial(y)
                )
                if x > y:
                    ph += p
                elif x == y:
                    pd += p
                else:
                    pa += p
        noisy = [max(0.05, p * rng.uniform(0.85, 1.15)) for p in (ph, pd, pa)]
        total = sum(noisy)
        odds = [round(1 / (p / total * 1.06), 2) for p in noisy]
        fixtures.append(
            {
                "id": f"f{i // 2 + 1}",
                "date": kickoff.isoformat(),
                "home_team": home,
                "away_team": away,
                "odds": {"home": odds[0], "draw": odds[1], "away": odds[2]},
            }
        )

    with (DATA_DIR / "fixtures.json").open("w", encoding="utf-8") as f:
        json.dump(fixtures, f, ensure_ascii=False, indent=2)

    print(f"{len(rows)} partidos y {len(fixtures)} próximos partidos generados en {DATA_DIR}")


if __name__ == "__main__":
    main()
