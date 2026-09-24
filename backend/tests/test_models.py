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
