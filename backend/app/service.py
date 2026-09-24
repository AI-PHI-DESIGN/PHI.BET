"""Motor de predicción: entrena los modelos y cruza sus probabilidades con las cuotas."""

from __future__ import annotations

from dataclasses import asdict

from app import betting
from app.data import Fixture, Match, load_fixtures, load_matches
from app.models.elo import EloModel
from app.models.poisson import PoissonModel

# Ventaja mínima (valor esperado) para marcar una apuesta como "de valor".
MIN_EDGE = 0.03


class PredictionEngine:
    def __init__(self, matches: list[Match], fixtures: list[Fixture]) -> None:
        self.matches = matches
        self.fixtures = {f.id: f for f in fixtures}
        self.poisson = PoissonModel().fit(matches)
        self.elo = EloModel().fit(matches)

    @classmethod
    def from_disk(cls) -> "PredictionEngine":
        return cls(load_matches(), load_fixtures())

    def predict(self, fixture: Fixture) -> dict:
        probs = self.poisson.predict(fixture.home_team, fixture.away_team)
        model_1x2 = {"home": probs.home, "draw": probs.draw, "away": probs.away}
        market_1x2 = betting.implied_probabilities(fixture.odds)

        markets = []
        for outcome, p in model_1x2.items():
            odds = fixture.odds[outcome]
            ev = betting.expected_value(p, odds)
            markets.append(
                {
                    "outcome": outcome,
                    "odds": odds,
                    "model_prob": round(p, 4),
                    "market_prob": round(market_1x2[outcome], 4),
                    "expected_value": round(ev, 4),
                    "kelly_stake": round(betting.kelly_fraction(p, odds), 4),
                    "is_value": ev >= MIN_EDGE,
                }
            )

        return {
            **asdict(fixture),
            "bookmaker_margin": round(betting.overround(fixture.odds), 4),
            "expected_goals": {"home": round(probs.home_xg, 2), "away": round(probs.away_xg, 2)},
            "most_likely_score": list(probs.most_likely_score),
            "over_2_5": round(probs.over_2_5, 4),
            "btts": round(probs.btts, 4),
            "elo": {
                "home": round(self.elo.rating(fixture.home_team), 1),
                "away": round(self.elo.rating(fixture.away_team), 1),
            },
            "markets": markets,
        }

    def predictions(self) -> list[dict]:
        return [self.predict(f) for f in self.fixtures.values()]

    def value_bets(self) -> list[dict]:
        bets = []
        for pred in self.predictions():
            for market in pred["markets"]:
                if market["is_value"]:
                    bets.append(
                        {
                            "fixture_id": pred["id"],
                            "date": pred["date"],
                            "match": f"{pred['home_team']} vs {pred['away_team']}",
                            **market,
                        }
                    )
        return sorted(bets, key=lambda b: b["expected_value"], reverse=True)

    def ratings(self) -> list[dict]:
        teams = sorted(self.elo.ratings, key=self.elo.rating, reverse=True)
        return [
            {
                "team": t,
                "elo": round(self.elo.rating(t), 1),
                "attack": round(self.poisson.strengths[t].attack, 3),
                "defense": round(self.poisson.strengths[t].defense, 3),
            }
            for t in teams
        ]
