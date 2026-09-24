"""Ratings Elo de los equipos, actualizados partido a partido."""

from __future__ import annotations

from app.data import Match


class EloModel:
    def __init__(self, k: float = 20.0, home_advantage: float = 60.0, initial: float = 1500.0) -> None:
        self.k = k
        self.home_advantage = home_advantage
        self.initial = initial
        self.ratings: dict[str, float] = {}

    def rating(self, team: str) -> float:
        return self.ratings.get(team, self.initial)

    def expected_home(self, home: str, away: str) -> float:
        """Puntuación esperada del local (victoria=1, empate=0.5)."""
        diff = self.rating(home) + self.home_advantage - self.rating(away)
        return 1.0 / (1.0 + 10 ** (-diff / 400.0))

    def fit(self, matches: list[Match]) -> "EloModel":
        for m in sorted(matches, key=lambda m: m.date):
            expected = self.expected_home(m.home_team, m.away_team)
            if m.home_goals > m.away_goals:
                actual = 1.0
            elif m.home_goals == m.away_goals:
                actual = 0.5
            else:
                actual = 0.0
            delta = self.k * (actual - expected)
            self.ratings[m.home_team] = self.rating(m.home_team) + delta
            self.ratings[m.away_team] = self.rating(m.away_team) - delta
        return self
