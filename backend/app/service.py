"""Motor de predicción: entrena los modelos y genera el análisis de cada partido."""

from __future__ import annotations

from dataclasses import asdict

from app import evaluation, markets, picks
from app.data import Fixture, Match, load_fixtures, load_matches
from app.models.elo import EloModel
from app.models.poisson import PoissonModel


class PredictionEngine:
    def __init__(self, matches: list[Match], fixtures: list[Fixture], base: "PredictionEngine | None" = None) -> None:
        self.matches = matches
        self.fixtures = {f.id: f for f in fixtures}
        if base is not None and base.matches == matches:
            # Mismos resultados (solo cambian cuotas o calendario): se reutiliza lo ya entrenado,
            # que es lo caro (la evaluación reentrena el modelo una vez por jornada).
            self.poisson, self.elo = base.poisson, base.elo
            self._evaluated, self._performance = base._evaluated, base._performance
            return
        self.poisson = PoissonModel().fit(matches)
        self.elo = EloModel().fit(matches)
        # Se evalúan los dos últimos tercios del histórico (como mínimo, tras una temporada de ejemplo).
        min_training = max(evaluation.MIN_TRAINING, len(matches) // 3)
        self._evaluated = evaluation.walk_forward(matches, min_training)
        ordered = sorted(matches, key=lambda m: m.date)
        self._performance = evaluation.summarize(self._evaluated, ordered[:min_training])

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
            "pick_score": {"score": list(p.pick_score), "prob": round(p.pick_score_prob, 4)},
            "top_scores": [{"score": [i, j], "prob": round(q, 4)} for i, j, q in p.top_scores],
            "over_2_5": round(p.over_2_5, 4),
            "btts": round(p.btts, 4),
            "markets": {k: round(v, 4) for k, v in markets.model_probabilities(p).items()},
            "elo": {
                "home": round(self.elo.rating(fixture.home_team), 1),
                "away": round(self.elo.rating(fixture.away_team), 1),
            },
        }

    def predictions(self) -> list[dict]:
        return [self.predict(f) for f in self.fixtures.values()]

    def dates(self) -> list[str]:
        return sorted({f.date for f in self.fixtures.values() if f.odds})

    def picks(
        self, date: str | None, min_prob: float, risk: str, combine: int = 1, value_only: bool = False, limit: int = 10
    ) -> dict:
        dates = self.dates()
        date = date or (dates[0] if dates else None)
        day = [self.predict(f) for f in self.fixtures.values() if f.date == date]
        candidates = picks.candidate_selections(day, self.fixtures)
        return {
            "dates": dates,
            # Primer partido pendiente (tenga cuotas o no): la web lo usa para explicar por qué no hay cuotas.
            "next_match": min((f.date for f in self.fixtures.values()), default=None),
            "date": date,
            "min_prob": min_prob,
            "risk": risk,
            "max_gap": picks.RISK_LEVELS[risk],
            "combine": combine,
            "candidates": len(candidates),
            # Cómo le fue a la IA en el histórico con selecciones de al menos esta probabilidad.
            "historical": evaluation.hit_rate_at(self._evaluated, min_prob),
            "picks": picks.best_picks(candidates, min_prob, risk, combine, value_only, limit),
        }

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
