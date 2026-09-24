import pytest

from app import evaluation
from app.data import Match, load_matches


def test_outcome():
    assert evaluation.outcome(2, 1) == "home"
    assert evaluation.outcome(1, 1) == "draw"
    assert evaluation.outcome(0, 3) == "away"


def test_brier_bounds():
    assert evaluation.brier({"home": 1, "draw": 0, "away": 0}, "home") == 0
    assert evaluation.brier({"home": 1, "draw": 0, "away": 0}, "away") == 2
    assert evaluation.brier({"home": 1 / 3, "draw": 1 / 3, "away": 1 / 3}, "draw") == pytest.approx(2 / 3)


def test_walk_forward_uses_only_past_matches():
    matches = [Match(f"2026-01-{d:02d}", "A", "B", 2, 0) for d in range(1, 11)]
    # Tras 5 victorias locales de A, el modelo debe preferir a A en el 6º partido...
    rows = evaluation.walk_forward(matches, min_training=5)
    assert len(rows) == 5
    assert all(r["pick"] == "home" and r["correct"] for r in rows)
    # ...y el primer partido evaluado no puede haber visto su propio resultado ni los siguientes.
    changed = matches[:5] + [Match("2026-01-06", "A", "B", 0, 5)] + matches[6:]
    assert evaluation.walk_forward(changed, min_training=5)[0]["probs"] == rows[0]["probs"]


def test_summary_on_sample_data():
    matches = sorted(load_matches(), key=lambda m: m.date)
    rows = evaluation.walk_forward(matches)
    s = evaluation.summarize(rows, matches[: evaluation.MIN_TRAINING])
    assert s["evaluated"] == len(matches) - evaluation.MIN_TRAINING
    assert 0 <= s["accuracy"] <= 1
    # La IA debe mejorar a la referencia ingenua (frecuencias históricas).
    assert s["brier"] < s["baseline_brier"]
    assert sum(m["matches"] for m in s["by_month"]) == s["evaluated"]
    assert sum(b["count"] for b in s["calibration"]) == 3 * s["evaluated"]


def test_summary_empty():
    assert evaluation.summarize([])["evaluated"] == 0
