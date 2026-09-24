"""openfootball/football.json: resultados y calendario completo de la temporada (gratis, sin clave).

https://raw.githubusercontent.com/openfootball/football.json/master/<temporada>/<liga>.json
(p. ej. 2026-27/es.1.json). Se actualiza varias veces por semana. Se usa como respaldo si
football-data.co.uk no responde y para tener los partidos de la semana aunque aún no tengan cuotas.
"""

from __future__ import annotations

import json
import logging
from datetime import date, timedelta
from pathlib import Path

import httpx

from app import teams
from app.data import Fixture, Match
from app.providers.football_data import download, season_start

log = logging.getLogger(__name__)

BASE_URL = "https://raw.githubusercontent.com/openfootball/football.json/master"
SOURCE = "openfootball"


def season_label(start_year: int) -> str:
    return f"{start_year}-{(start_year + 1) % 100:02d}"


def _score(match: dict) -> list | None:
    # El marcador viene como {"ft": [2, 1], "ht": [...]} o directamente como [2, 1].
    score = match.get("score")
    ft = score.get("ft") if isinstance(score, dict) else score
    return ft if isinstance(ft, list) and len(ft) == 2 else None


def parse(text: str) -> tuple[list[Match], list[Fixture]]:
    """Partidos jugados (con marcador) y partidos por jugar (sin cuotas)."""
    matches, fixtures = [], []
    for m in json.loads(text).get("matches", []):
        if not m.get("date") or not m.get("team1") or not m.get("team2"):
            continue
        home, away = teams.canonical(m["team1"]), teams.canonical(m["team2"])
        ft = _score(m)
        if ft is not None:
            matches.append(Match(m["date"], home, away, int(ft[0]), int(ft[1])))
        else:
            time = (m.get("time") or "").strip()[:5]
            fixtures.append(
                Fixture(
                    id=f"{m['date']}-{teams.normalize(home).replace(' ', '-')}-{teams.normalize(away).replace(' ', '-')}",
                    date=m["date"],
                    home_team=home,
                    away_team=away,
                    # La web publica la hora local del partido; para las 5 grandes ligas coincide con la de Madrid.
                    kickoff=f"{m['date']}T{time}" if time else None,
                )
            )
    return matches, fixtures


def next_round(fixtures: list[Fixture], today: date, days: int = 7) -> list[Fixture]:
    """Los partidos desde el próximo que se juegue hasta `days` días después (la próxima jornada,
    aunque haya un parón de selecciones de por medio)."""
    ahead = sorted((f for f in fixtures if f.date >= today.isoformat()), key=lambda f: f.date)
    if not ahead:
        return []
    limit = (date.fromisoformat(ahead[0].date) + timedelta(days=days)).isoformat()
    return [f for f in ahead if f.date <= limit]


def fetch(
    client: httpx.Client, cache_dir: Path, code: str, seasons: int, today: date | None = None
) -> tuple[list[Match], list[Fixture]]:
    """Resultados de las últimas `seasons` temporadas y los partidos de la próxima jornada."""
    today = today or date.today()
    start = season_start(today)
    matches: list[Match] = []
    fixtures: list[Fixture] = []
    errors = []
    for year in range(start - seasons + 1, start + 1):
        label = season_label(year)
        try:
            text = download(client, f"{BASE_URL}/{label}/{code}.json", cache_dir / f"openfootball_{label}_{code}.json")
        except httpx.HTTPError as e:
            log.warning("openfootball %s %s no disponible: %s", label, code, e)
            errors.append(e)
            continue
        played, upcoming = parse(text)
        matches.extend(played)
        if year == start:
            fixtures = next_round(upcoming, today)
    if not matches and errors:
        raise errors[-1]
    return matches, fixtures
