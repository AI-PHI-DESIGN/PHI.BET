"""Modelo de Poisson (estilo Maher) para predecir goles y resultados 1X2.

Cada equipo tiene una fuerza de ataque y de defensa relativa a la media de la liga.
Los goles esperados de un partido son:
    λ_local     = ataque_local     * defensa_visitante * media_goles_local
    λ_visitante = ataque_visitante * defensa_local     * media_goles_visitante
"""

from __future__ import annotations

import math
from dataclasses import dataclass

from app.data import Match

MAX_GOALS = 10


@dataclass
class TeamStrength:
    attack: float
    defense: float


@dataclass
class MatchProbabilities:
    home_xg: float
    away_xg: float
    home: float
    draw: float
    away: float
    over_2_5: float
    btts: float
    most_likely_score: tuple[int, int]


def _poisson_pmf(k: int, lam: float) -> float:
    return math.exp(-lam) * lam**k / math.factorial(k)


class PoissonModel:
    def __init__(self) -> None:
        self.strengths: dict[str, TeamStrength] = {}
        self.avg_home_goals = 1.0
        self.avg_away_goals = 1.0

    def fit(self, matches: list[Match]) -> "PoissonModel":
        if not matches:
            raise ValueError("Se necesita al menos un partido para entrenar el modelo")

        n = len(matches)
        self.avg_home_goals = sum(m.home_goals for m in matches) / n
        self.avg_away_goals = sum(m.away_goals for m in matches) / n

        stats: dict[str, dict[str, float]] = {}
        for m in matches:
            h = stats.setdefault(m.home_team, {"hs": 0, "hc": 0, "hn": 0, "as": 0, "ac": 0, "an": 0})
            a = stats.setdefault(m.away_team, {"hs": 0, "hc": 0, "hn": 0, "as": 0, "ac": 0, "an": 0})
            h["hs"] += m.home_goals
            h["hc"] += m.away_goals
            h["hn"] += 1
            a["as"] += m.away_goals
            a["ac"] += m.home_goals
            a["an"] += 1

        for team, s in stats.items():
            # Normaliza local y visitante por separado para no penalizar la ventaja de campo.
            attack_parts, defense_parts = [], []
            if s["hn"]:
                attack_parts.append(s["hs"] / s["hn"] / self.avg_home_goals)
                defense_parts.append(s["hc"] / s["hn"] / self.avg_away_goals)
            if s["an"]:
                attack_parts.append(s["as"] / s["an"] / self.avg_away_goals)
                defense_parts.append(s["ac"] / s["an"] / self.avg_home_goals)
            self.strengths[team] = TeamStrength(
                attack=sum(attack_parts) / len(attack_parts),
                defense=sum(defense_parts) / len(defense_parts),
            )
        return self

    def expected_goals(self, home: str, away: str) -> tuple[float, float]:
        default = TeamStrength(1.0, 1.0)
        h = self.strengths.get(home, default)
        a = self.strengths.get(away, default)
        return (
            h.attack * a.defense * self.avg_home_goals,
            a.attack * h.defense * self.avg_away_goals,
        )

    def predict(self, home: str, away: str) -> MatchProbabilities:
        lam_h, lam_a = self.expected_goals(home, away)
        ph = [_poisson_pmf(i, lam_h) for i in range(MAX_GOALS + 1)]
        pa = [_poisson_pmf(j, lam_a) for j in range(MAX_GOALS + 1)]

        home_p = draw_p = away_p = over = btts = 0.0
        best, best_p = (0, 0), -1.0
        for i, p_i in enumerate(ph):
            for j, p_j in enumerate(pa):
                p = p_i * p_j
                if i > j:
                    home_p += p
                elif i == j:
                    draw_p += p
                else:
                    away_p += p
                if i + j > 2:
                    over += p
                if i > 0 and j > 0:
                    btts += p
                if p > best_p:
                    best, best_p = (i, j), p

        total = home_p + draw_p + away_p  # corrige la masa truncada en MAX_GOALS
        return MatchProbabilities(
            home_xg=lam_h,
            away_xg=lam_a,
            home=home_p / total,
            draw=draw_p / total,
            away=away_p / total,
            over_2_5=over / total,
            btts=btts / total,
            most_likely_score=best,
        )
