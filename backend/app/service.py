"""Motor de predicción: entrena los modelos y genera el análisis de cada partido."""

from __future__ import annotations

from dataclasses import asdict

from app import evaluation
from app.data import Fixture, Match, load_fixtures, load_matches
from app.models.elo import EloModel
from app.models.poisson import PoissonModel


class PredictionEngine:
    def __init__(self, matches: list[Match], fixtures: list[Fixture]) -> None:
        self.matches = matches
        self.fixtures = {f.id: f for f in fixtures}
        self.poisson = PoissonModel().fit(matches)
        self.elo = EloModel().fit(matches)
        self._evaluated = evaluation.walk_forward(matches)
        ordered = sorted(matches, key=lambda m: m.date)
        self._performance = evaluation.summarize(self._evaluated, ordered[: evaluation.MIN_TRAINING])

    @classmethod
    def from_disk(cls) -> "PredictionEngine":
        return cls(load_matches(), load_fixtures())

    def predict(self, fixture: Fixture) -> dict:
        p = self.poisson.predict(fixture.home_team, fixture.away_team)
        probs = {"home": round(p.home, 4), "draw": round(p.draw, 4), "away": round(p.away, 4)}
        pick = max(probs, key=probs.get)
        return {
            **asdict(fixture),
            "probs": probs,
            "pick": pick,
            "confidence": probs[pick],
            "expected_goals": {"home": round(p.home_xg, 2), "away": round(p.away_xg, 2)},
            "most_likely_score": list(p.most_likely_score),
            "over_2_5": round(p.over_2_5, 4),
            "btts": round(p.btts, 4),
            "elo": {
                "home": round(self.elo.rating(fixture.home_team), 1),
                "away": round(self.elo.rating(fixture.away_team), 1),
            },
        }

    def predictions(self) -> list[dict]:
        return [self.predict(f) for f in self.fixtures.values()]

    def performance(self, recent: int = 20) -> dict:
        recent_rows = self._evaluated[max(0, len(self._evaluated) - recent) :] if recent else []
        return {**self._performance, "recent": list(reversed(recent_rows))}

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
