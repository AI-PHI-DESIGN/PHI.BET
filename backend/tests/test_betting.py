import pytest

from app import betting


def test_implied_probabilities_remove_margin():
    probs = betting.implied_probabilities({"home": 2.0, "draw": 3.5, "away": 3.8})
    assert sum(probs.values()) == pytest.approx(1.0)
    assert probs["home"] > probs["away"]


def test_overround():
    assert betting.overround({"a": 1.9, "b": 1.9}) == pytest.approx(2 / 1.9 - 1)


def test_expected_value():
    assert betting.expected_value(0.5, 2.2) == pytest.approx(0.1)
    assert betting.expected_value(0.4, 2.0) == pytest.approx(-0.2)


def test_kelly_zero_without_edge():
    assert betting.kelly_fraction(0.4, 2.0) == 0.0


def test_kelly_fractional_and_capped():
    # Kelly completo = (0.55*2 - 1) / 1 = 0.10 -> 1/4 = 0.025
    assert betting.kelly_fraction(0.55, 2.0) == pytest.approx(0.025)
    assert betting.kelly_fraction(0.9, 2.0) == 0.05
