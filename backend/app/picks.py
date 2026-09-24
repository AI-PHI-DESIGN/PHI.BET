"""Buscador de cuotas: las mejores cuotas del día que cumplen un acierto mínimo y un nivel de riesgo.

- Acierto mínimo: probabilidad mínima que la IA da al pronóstico (a la combinada entera, si lo es).
- Riesgo: cuánto se confía en la IA cuando discrepa de la casa de apuestas. Con la misma
  probabilidad según la IA, una cuota más alta solo existe si la casa lo ve menos probable;
  cuanto mayor la discrepancia, mayor la cuota y mayor el riesgo de que el error sea de la IA.
- Combinar: máximo de selecciones (de partidos distintos) por pronóstico. Ojo: el margen de la
  casa se acumula en cada selección, así que combinar rara vez mejora la cuota a igual acierto.
"""

from __future__ import annotations

from itertools import combinations, product

from app import markets

# nivel de riesgo -> máxima ventaja (prob. IA − prob. casa) permitida en cada selección
RISK_LEVELS: dict[str, float | None] = {"low": 0.05, "medium": 0.12, "high": None}
MAX_COMBINE = 3


def candidate_selections(predictions: list[dict], fixtures: dict) -> list[dict]:
    """Todas las selecciones con cuota de los partidos dados, con la probabilidad de la IA y la de la casa."""
    out = []
    for pred in predictions:
        odds = fixtures[pred["id"]].odds
        if not odds:
            continue
        implied = markets.implied_probabilities(odds)
        for key, prob in pred["markets"].items():
            if key not in odds:
                continue
            market, label, _ = markets.SELECTIONS[key]
            out.append(
                {
                    "fixture_id": pred["id"],
                    "match": f"{pred['home_team']} vs {pred['away_team']}",
                    "date": pred["date"],
                    "key": key,
                    "market": market,
                    "label": label,
                    "odds": odds[key],
                    "prob": prob,
                    "implied_prob": round(implied[key], 4),
                }
            )
    return out


def best_picks(
    candidates: list[dict],
    min_prob: float,
    risk: str,
    combine: int = 1,
    value_only: bool = False,
    limit: int = 10,
) -> list[dict]:
    """Pronósticos (simples o combinados) con probabilidad >= min_prob, ordenados por cuota."""
    if risk not in RISK_LEVELS:
        raise ValueError("Riesgo no válido (low, medium o high)")
    if not 1 <= combine <= MAX_COMBINE:
        raise ValueError(f"Combinar debe estar entre 1 y {MAX_COMBINE}")
    max_gap = RISK_LEVELS[risk]
    # Una selección por debajo del mínimo nunca puede formar parte de una combinada que lo cumpla.
    pool = [
        c
        for c in candidates
        if c["prob"] >= min_prob and (max_gap is None or c["prob"] - c["implied_prob"] <= max_gap)
    ]
    by_fixture: dict[str, list[dict]] = {}
    for c in pool:
        by_fixture.setdefault(c["fixture_id"], []).append(c)

    picks = []
    for size in range(1, combine + 1):
        # Solo una selección por partido: así las probabilidades son independientes y se multiplican.
        for fixture_ids in combinations(sorted(by_fixture), size):
            for sels in product(*(by_fixture[f] for f in fixture_ids)):
                prob = odds = implied = 1.0
                for s in sels:
                    prob *= s["prob"]
                    odds *= s["odds"]
                    implied *= s["implied_prob"]
                if prob < min_prob:
                    continue
                edge = prob * odds - 1.0
                if value_only and edge <= 0:
                    continue
                picks.append(
                    {
                        "selections": list(sels),
                        "size": size,
                        "odds": round(odds, 2),
                        "prob": round(prob, 4),
                        "implied_prob": round(implied, 4),
                        "edge": round(edge, 4),
                    }
                )
    picks.sort(key=lambda p: (p["odds"], p["prob"]), reverse=True)
    return picks[:limit]
