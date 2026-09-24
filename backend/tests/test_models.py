import pytest

from app.data import Match
from app.models.elo import EloModel
from app.models.poisson import PoissonModel

MATCHES = [
    Match("2025-01-01", "Fuerte", "Debil", 3, 0),
    Match("2025-01-02", "Debil", "Fuerte", 0, 2),
    Match("2025-01-03", "Fuerte", "Medio", 2, 1),
    Match("2025-01-04", "Medio", "Debil", 2, 1),
    Match("2025-01-05", "Debil", "Medio", 1, 1),
    Match("2025-01-06", "Medio", "Fuerte", 1, 1),
]


def test_poisson_probabilities_sum_to_one():
    p = PoissonModel().fit(MATCHES).predict("Fuerte", "Debil")
    assert p.home + p.draw + p.away == pytest.approx(1.0)
    assert 0 <= p.over_2_5 <= 1 and 0 <= p.btts <= 1


def test_poisson_favours_stronger_team():
    model = PoissonModel().fit(MATCHES)
    assert model.predict("Fuerte", "Debil").home > model.predict("Debil", "Fuerte").home


def test_poisson_requires_data():
    with pytest.raises(ValueError):
        PoissonModel().fit([])


def test_elo_ranks_teams():
    elo = EloModel().fit(MATCHES)
    assert elo.rating("Fuerte") > elo.rating("Medio") > elo.rating("Debil")
    assert sum(elo.ratings.values()) == pytest.approx(1500 * 3)


def test_poisson_handles_no_away_goals():
    only_home = [Match(f"2025-01-0{d}", "A", "B", 2, 0) for d in range(1, 4)]
    p = PoissonModel().fit(only_home).predict("A", "B")
    assert p.home + p.draw + p.away == pytest.approx(1.0)
    assert p.away > 0


def _raw(**kw) -> PoissonModel:
    """Modelo sin ajustes, salvo los que se pasen."""
    return PoissonModel(**{"half_life_days": None, "prior_weight": 0.0, "rho": 0.0, **kw})


def test_time_decay_gives_more_weight_to_recent_form():
    # A goleaba hace dos años y ahora no marca: con ponderación temporal su ataque baja.
    old = [Match(f"2024-0{d}-01", "A", "B", 4, 0) for d in range(1, 6)]
    new = [Match(f"2026-0{d}-01", "A", "B", 0, 0) for d in range(1, 6)] + [Match("2026-06-01", "B", "A", 1, 1)]
    ms = old + new
    assert _raw(half_life_days=180).fit(ms).strengths["A"].attack < _raw().fit(ms).strengths["A"].attack


def test_prior_weight_pulls_strengths_towards_average():
    ms = [Match("2026-01-01", "A", "B", 5, 0), Match("2026-01-08", "B", "A", 0, 3), Match("2026-01-15", "C", "D", 1, 1)]
    plain, shrunk = _raw().fit(ms).strengths["A"], _raw(prior_weight=4).fit(ms).strengths["A"]
    assert 1 < shrunk.attack < plain.attack
    assert plain.defense < shrunk.defense < 1


def test_dixon_coles_raises_low_scoring_draws():
    ms = [Match("2026-01-01", "A", "B", 1, 1), Match("2026-01-08", "B", "A", 2, 0)]
    base, dc = _raw().fit(ms).predict("A", "B"), _raw(rho=-0.1).fit(ms).predict("A", "B")
    assert dc.draw > base.draw
    assert abs(dc.home + dc.draw + dc.away - 1) < 1e-9


def test_pick_score_matches_predicted_outcome():
    # Un favorito claro: el marcador "del pronóstico" es una victoria suya, aunque el exacto más probable no lo sea.
    ms = [Match(f"2026-01-{d:02d}", "Fuerte", "Debil", 2, 0) for d in range(1, 10)]
    ms += [Match(f"2026-02-{d:02d}", "Debil", "Fuerte", 0, 1) for d in range(1, 10)]
    p = PoissonModel().fit(ms).predict("Fuerte", "Debil")
    assert p.home > p.draw and p.home > p.away
    assert p.pick_score[0] > p.pick_score[1]
    assert len(p.top_scores) == 3 and p.top_scores[0][2] >= p.top_scores[1][2] >= p.top_scores[2][2]
    assert 0 < p.pick_score_prob <= p.home
