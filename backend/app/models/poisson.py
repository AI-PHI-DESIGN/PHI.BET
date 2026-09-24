"""Modelo de Poisson (estilo Maher) para predecir goles y resultados 1X2.

Cada equipo tiene una fuerza de ataque y de defensa relativa a la media de la liga.
Los goles esperados de un partido son:
    λ_local     = ataque_local     * defensa_visitante * media_goles_local
    λ_visitante = ataque_visitante * defensa_local     * media_goles_visitante

Mejoras sobre el modelo básico (todas ajustables, ver `PoissonModel.__init__`):
- Ponderación temporal: cada partido pesa 0,5^(días de antigüedad / half_life_days), así la
  forma reciente cuenta más que la de hace dos temporadas.
- Regresión a la media: se suman `prior_weight` partidos "ficticios" de un equipo medio, para
  que con pocos partidos (equipos recién ascendidos, inicio de temporada) la IA no se confíe.
- Corrección de Dixon-Coles (`rho`): el Poisson independiente se queda corto en empates a
  pocos goles (0-0, 1-1); rho < 0 ajusta los marcadores 0-0, 1-0, 0-1 y 1-1.
"""

from __future__ import annotations

import math
from dataclasses import dataclass, field
from datetime import date

from app.data import Match

MAX_GOALS = 10
MIN_AVG_GOALS = 0.1
MIN_STRENGTH = 0.05  # evita λ = 0 (probabilidad cero de marcar) con pocos datos

# Valores elegidos con la evaluación walk-forward sobre 3.659 partidos reales de LaLiga, Premier,
# Serie A, Bundesliga y Ligue 1 (2023/24–2026/27). Frente al modelo sin ajustes: Brier
# 0,5986 → 0,5921, log-loss 1,0067 → 0,9926, error de calibración 1,7 → 0,4 puntos, y cuando
# la IA da ≥80 % acierta el 86,4 % (antes 82,2 %). Ver docs/PLAYBOOK.md, sección 1e.
HALF_LIFE_DAYS = 365
PRIOR_WEIGHT = 2.0
RHO = -0.08


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
    # El marcador más probable dentro del resultado pronosticado (1, X o 2): el exacto más probable
    # casi siempre es 1-1 o 1-0 (~12 %), aunque un equipo sea claro favorito.
    pick_score: tuple[int, int] = (0, 0)
    pick_score_prob: float = 0.0
    top_scores: list[tuple[int, int, float]] = field(default_factory=list)  # los 3 más probables


def _poisson_pmf(k: int, lam: float) -> float:
    return math.exp(-lam) * lam**k / math.factorial(k)


class PoissonModel:
    def __init__(
        self, half_life_days: float | None = HALF_LIFE_DAYS, prior_weight: float = PRIOR_WEIGHT, rho: float = RHO
    ) -> None:
        self.half_life_days = half_life_days
        self.prior_weight = prior_weight
        self.rho = rho
        self.strengths: dict[str, TeamStrength] = {}
        self.avg_home_goals = 1.0
        self.avg_away_goals = 1.0

    def _weights(self, matches: list[Match]) -> list[float]:
        if not self.half_life_days:
            return [1.0] * len(matches)
        last = max(date.fromisoformat(m.date) for m in matches)
        return [0.5 ** ((last - date.fromisoformat(m.date)).days / self.half_life_days) for m in matches]

    def fit(self, matches: list[Match]) -> "PoissonModel":
        if not matches:
            raise ValueError("Se necesita al menos un partido para entrenar el modelo")

        weights = self._weights(matches)
        n = sum(weights)
        # Suelo mínimo para no dividir entre cero con muestras sin goles (p. ej. ningún gol visitante).
        self.avg_home_goals = max(sum(w * m.home_goals for w, m in zip(weights, matches)) / n, MIN_AVG_GOALS)
        self.avg_away_goals = max(sum(w * m.away_goals for w, m in zip(weights, matches)) / n, MIN_AVG_GOALS)

        stats: dict[str, dict[str, float]] = {}
        for w, m in zip(weights, matches):
            h = stats.setdefault(m.home_team, {"hs": 0, "hc": 0, "hn": 0, "as": 0, "ac": 0, "an": 0})
            a = stats.setdefault(m.away_team, {"hs": 0, "hc": 0, "hn": 0, "as": 0, "ac": 0, "an": 0})
            h["hs"] += w * m.home_goals
            h["hc"] += w * m.away_goals
            h["hn"] += w
            a["as"] += w * m.away_goals
            a["ac"] += w * m.home_goals
            a["an"] += w

        k = self.prior_weight
        ah, aa = self.avg_home_goals, self.avg_away_goals
        for team, s in stats.items():
            # Normaliza local y visitante por separado para no penalizar la ventaja de campo.
            # Con k > 0, cada media incluye k partidos de un equipo medio (fuerza 1).
            attack_parts, defense_parts = [], []
            if s["hn"] or k:
                attack_parts.append((s["hs"] + k * ah) / (s["hn"] + k) / ah)
                defense_parts.append((s["hc"] + k * aa) / (s["hn"] + k) / aa)
            if s["an"] or k:
                attack_parts.append((s["as"] + k * aa) / (s["an"] + k) / aa)
                defense_parts.append((s["ac"] + k * ah) / (s["an"] + k) / ah)
            self.strengths[team] = TeamStrength(
                attack=max(sum(attack_parts) / len(attack_parts), MIN_STRENGTH),
                defense=max(sum(defense_parts) / len(defense_parts), MIN_STRENGTH),
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

    def _dixon_coles(self, i: int, j: int, lam_h: float, lam_a: float) -> float:
        if not self.rho or i > 1 or j > 1:
            return 1.0
        if i == 0 and j == 0:
            return max(1 - lam_h * lam_a * self.rho, 0.0)
        if i == 0 and j == 1:
            return max(1 + lam_h * self.rho, 0.0)
        if i == 1 and j == 0:
            return max(1 + lam_a * self.rho, 0.0)
        return max(1 - self.rho, 0.0)

    def predict(self, home: str, away: str) -> MatchProbabilities:
        lam_h, lam_a = self.expected_goals(home, away)
        ph = [_poisson_pmf(i, lam_h) for i in range(MAX_GOALS + 1)]
        pa = [_poisson_pmf(j, lam_a) for j in range(MAX_GOALS + 1)]

        home_p = draw_p = away_p = over = btts = 0.0
        best, best_p = (0, 0), -1.0
        grid: dict[tuple[int, int], float] = {}
        for i, p_i in enumerate(ph):
            for j, p_j in enumerate(pa):
                p = p_i * p_j * self._dixon_coles(i, j, lam_h, lam_a)
                grid[(i, j)] = p
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
        pick = max((home_p, 1), (draw_p, 0), (away_p, -1))[1]  # 1 local, 0 empate, -1 visitante
        in_pick = {k: v for k, v in grid.items() if (k[0] > k[1]) - (k[0] < k[1]) == pick}
        pick_score = max(in_pick, key=in_pick.get)
        top = sorted(grid.items(), key=lambda kv: kv[1], reverse=True)[:3]
        return MatchProbabilities(
            home_xg=lam_h,
            away_xg=lam_a,
            home=home_p / total,
            draw=draw_p / total,
            away=away_p / total,
            over_2_5=over / total,
            btts=btts / total,
            most_likely_score=best,
            pick_score=pick_score,
            pick_score_prob=in_pick[pick_score] / total,
            top_scores=[(i, j, p / total) for (i, j), p in top],
        )
