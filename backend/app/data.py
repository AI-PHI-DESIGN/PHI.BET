"""Carga de datos: histórico de partidos y próximos partidos."""

from __future__ import annotations

import csv
import json
from dataclasses import dataclass
from pathlib import Path

DATA_DIR = Path(__file__).resolve().parent.parent / "data"


@dataclass(frozen=True)
class Match:
    date: str
    home_team: str
    away_team: str
    home_goals: int
    away_goals: int


@dataclass(frozen=True)
class Fixture:
    id: str
    date: str
    home_team: str
    away_team: str


def load_matches(path: Path = DATA_DIR / "matches.csv") -> list[Match]:
    with path.open(newline="", encoding="utf-8") as f:
        return [
            Match(
                date=row["date"],
                home_team=row["home_team"],
                away_team=row["away_team"],
                home_goals=int(row["home_goals"]),
                away_goals=int(row["away_goals"]),
            )
            for row in csv.DictReader(f)
        ]


def load_fixtures(path: Path = DATA_DIR / "fixtures.json") -> list[Fixture]:
    with path.open(encoding="utf-8") as f:
        return [Fixture(**item) for item in json.load(f)]
