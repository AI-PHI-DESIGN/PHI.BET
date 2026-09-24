"""Mercados analizados por partido y sus probabilidades según el modelo.

Cada selección tiene una clave estable (la misma que usan las cuotas en fixtures.json).
"""

from __future__ import annotations

from app.models.poisson import MatchProbabilities

# clave -> (mercado, etiqueta, grupo). Las selecciones de un grupo se reparten el 100%
# (la doble oportunidad suma 200% porque cada resultado entra en dos selecciones).
SELECTIONS: dict[str, tuple[str, str, str]] = {
    "1": ("Resultado", "Gana local", "1x2"),
    "X": ("Resultado", "Empate", "1x2"),
    "2": ("Resultado", "Gana visitante", "1x2"),
    "1X": ("Doble oportunidad", "Local o empate", "dc"),
    "X2": ("Doble oportunidad", "Empate o visitante", "dc"),
    "12": ("Doble oportunidad", "Local o visitante", "dc"),
    "over25": ("Goles", "Más de 2,5", "ou"),
    "under25": ("Goles", "Menos de 2,5", "ou"),
    "btts_yes": ("Ambos marcan", "Sí", "btts"),
    "btts_no": ("Ambos marcan", "No", "btts"),
}
GROUP_TOTAL = {"1x2": 1.0, "dc": 2.0, "ou": 1.0, "btts": 1.0}


def model_probabilities(p: MatchProbabilities) -> dict[str, float]:
    return {
        "1": p.home,
        "X": p.draw,
        "2": p.away,
        "1X": p.home + p.draw,
        "X2": p.draw + p.away,
        "12": p.home + p.away,
        "over25": p.over_2_5,
        "under25": 1.0 - p.over_2_5,
        "btts_yes": p.btts,
        "btts_no": 1.0 - p.btts,
    }


def outcomes(home_goals: int, away_goals: int) -> dict[str, bool]:
    """Qué selecciones se cumplieron con un resultado final."""
    return {
        "1": home_goals > away_goals,
        "X": home_goals == away_goals,
        "2": home_goals < away_goals,
        "1X": home_goals >= away_goals,
        "X2": home_goals <= away_goals,
        "12": home_goals != away_goals,
        "over25": home_goals + away_goals > 2,
        "under25": home_goals + away_goals <= 2,
        "btts_yes": home_goals > 0 and away_goals > 0,
        "btts_no": home_goals == 0 or away_goals == 0,
    }


def implied_probabilities(odds: dict[str, float]) -> dict[str, float]:
    """Probabilidad que da la casa a cada selección, sin su margen (normalizada por grupo)."""
    result = {}
    for group, total in GROUP_TOTAL.items():
        keys = [k for k in odds if SELECTIONS[k][2] == group]
        raw = sum(1.0 / odds[k] for k in keys)
        for k in keys:
            result[k] = (1.0 / odds[k]) / raw * total
    return result
