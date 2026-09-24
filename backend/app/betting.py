"""Matemática de apuestas: cuotas, probabilidades implícitas, valor esperado y Kelly."""

from __future__ import annotations


def implied_probabilities(odds: dict[str, float]) -> dict[str, float]:
    """Probabilidades implícitas de las cuotas, sin el margen de la casa (normalizadas)."""
    raw = {k: 1.0 / v for k, v in odds.items()}
    total = sum(raw.values())
    return {k: p / total for k, p in raw.items()}


def overround(odds: dict[str, float]) -> float:
    """Margen de la casa de apuestas (0.05 = 5%)."""
    return sum(1.0 / v for v in odds.values()) - 1.0


def expected_value(prob: float, odds: float) -> float:
    """Valor esperado por unidad apostada: p * cuota - 1."""
    return prob * odds - 1.0


def kelly_fraction(prob: float, odds: float, fraction: float = 0.25, cap: float = 0.05) -> float:
    """Stake recomendado como fracción del bankroll (Kelly fraccional con tope).

    Devuelve 0 si la apuesta no tiene valor esperado positivo.
    """
    b = odds - 1.0
    if b <= 0:
        return 0.0
    full = (prob * odds - 1.0) / b
    if full <= 0:
        return 0.0
    return min(full * fraction, cap)
