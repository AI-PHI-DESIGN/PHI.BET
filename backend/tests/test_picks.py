import pytest

from app import markets, picks
from app.models.poisson import MatchProbabilities


def test_model_probabilities_are_consistent():
    p = markets.model_probabilities(MatchProbabilities(1.5, 1.0, 0.5, 0.3, 0.2, 0.55, 0.45, (1, 1)))
    assert p["1X"] == pytest.approx(0.8)
    assert p["over25"] + p["under25"] == pytest.approx(1)
    assert p["btts_yes"] + p["btts_no"] == pytest.approx(1)


def test_outcomes():
    o = markets.outcomes(2, 1)
    assert o["1"] and o["1X"] and o["12"] and o["over25"] and o["btts_yes"]
    assert not (o["X"] or o["2"] or o["X2"] or o["under25"] or o["btts_no"])


def test_implied_probabilities_remove_margin_per_group():
    odds = {"1": 2.0, "X": 3.4, "2": 3.8, "1X": 1.25, "X2": 1.75, "12": 1.3,
            "over25": 1.9, "under25": 1.9, "btts_yes": 1.8, "btts_no": 2.0}
    imp = markets.implied_probabilities(odds)
    assert imp["1"] + imp["X"] + imp["2"] == pytest.approx(1)
    assert imp["1X"] + imp["X2"] + imp["12"] == pytest.approx(2)
    assert imp["over25"] == pytest.approx(0.5)


def sel(fixture, key, prob, odds, implied):
    return {"fixture_id": fixture, "match": fixture, "date": "d", "key": key, "market": "m",
            "label": key, "odds": odds, "prob": prob, "implied_prob": implied}


CANDIDATES = [
    sel("a", "1", 0.70, 1.60, 0.60),   # la IA ve 10 puntos más que la casa
    sel("a", "X", 0.20, 4.00, 0.24),
    sel("b", "1", 0.65, 1.45, 0.66),   # IA y casa de acuerdo
    sel("c", "2", 0.62, 2.10, 0.45),   # gran discrepancia
]


def test_min_prob_and_order():
    res = picks.best_picks(CANDIDATES, 0.6, "high")
    assert [p["selections"][0]["fixture_id"] for p in res] == ["c", "a", "b"]
    assert all(p["prob"] >= 0.6 for p in res)


def test_risk_limits_disagreement_with_market():
    assert [p["selections"][0]["fixture_id"] for p in picks.best_picks(CANDIDATES, 0.6, "low")] == ["b"]
    assert [p["selections"][0]["fixture_id"] for p in picks.best_picks(CANDIDATES, 0.6, "medium")] == ["a", "b"]


def test_combinations_use_distinct_matches_and_multiply():
    res = picks.best_picks(CANDIDATES, 0.4, "high", combine=2)
    combo = next(p for p in res if p["size"] == 2 and {s["fixture_id"] for s in p["selections"]} == {"a", "c"})
    assert combo["odds"] == pytest.approx(1.60 * 2.10, abs=0.01)
    assert combo["prob"] == pytest.approx(0.70 * 0.62, abs=1e-4)
    assert all(len({s["fixture_id"] for s in p["selections"]}) == p["size"] for p in res)


def test_value_only():
    res = picks.best_picks(CANDIDATES, 0.6, "high", value_only=True)
    assert all(p["prob"] * p["odds"] > 1 for p in res)


def test_invalid_arguments():
    with pytest.raises(ValueError):
        picks.best_picks(CANDIDATES, 0.6, "extremo")
    with pytest.raises(ValueError):
        picks.best_picks(CANDIDATES, 0.6, "low", combine=4)


def test_picks_without_odds_reports_next_match():
    from app.data import Fixture, load_matches
    from app.service import PredictionEngine

    engine = PredictionEngine(load_matches(), [Fixture("f1", "2026-10-09", "Atlético Phi", "CF Epsilon")])
    r = engine.picks(None, 0.6, "low")
    assert r["date"] is None and r["picks"] == [] and r["next_match"] == "2026-10-09"
