"""football-data.co.uk: resultados históricos y próximos partidos con cuotas (gratis, sin clave).

- Resultados: https://www.football-data.co.uk/mmz4281/<temporada>/<división>.csv
  (p. ej. 2627/SP1.csv = LaLiga 2026/27; E0 Premier, I1 Serie A, D1 Bundesliga, F1 Ligue 1)
- Próximos partidos: https://www.football-data.co.uk/fixtures.csv  (todas las ligas en un fichero)
Los ficheros se actualizan un par de veces por semana. Cada descarga se guarda en caché para
seguir funcionando si la web no responde.
"""

from __future__ import annotations

import csv
import io
import logging
from datetime import date, datetime
from pathlib import Path
from zoneinfo import ZoneInfo

import httpx

from app import teams
from app.data import Fixture, Match

log = logging.getLogger(__name__)

BASE_URL = "https://www.football-data.co.uk"
DIVISION = "SP1"  # LaLiga (Primera División), la división por defecto
SOURCE = "football-data.co.uk"
LONDON, MADRID = ZoneInfo("Europe/London"), ZoneInfo("Europe/Madrid")

# Columnas de cuotas: (clave de selección, columna de la mejor cuota, columna de la cuota media)
ODDS_COLUMNS = [
    ("1", "MaxH", "AvgH"),
    ("X", "MaxD", "AvgD"),
    ("2", "MaxA", "AvgA"),
    ("over25", "Max>2.5", "Avg>2.5"),
    ("under25", "Max<2.5", "Avg<2.5"),
]


def season_start(today: date) -> int:
    """Año en que empezó la temporada en curso (la temporada empieza en julio)."""
    return today.year if today.month >= 7 else today.year - 1


def season_code(start_year: int) -> str:
    return f"{start_year % 100:02d}{(start_year + 1) % 100:02d}"


def _parse_date(value: str) -> str:
    for fmt in ("%d/%m/%Y", "%d/%m/%y"):
        try:
            return datetime.strptime(value.strip(), fmt).date().isoformat()
        except ValueError:
            continue
    raise ValueError(f"Fecha no reconocida: {value!r}")


def _rows(text: str) -> list[dict[str, str]]:
    return list(csv.DictReader(io.StringIO(text.lstrip("﻿"))))


def _float(value: str | None) -> float | None:
    try:
        v = float(value) if value not in (None, "") else None
    except ValueError:
        return None
    return v if v and v > 1 else None


def parse_results(text: str) -> list[Match]:
    matches = []
    for row in _rows(text):
        if not row.get("HomeTeam") or row.get("FTHG") in (None, "") or row.get("FTAG") in (None, ""):
            continue  # filas vacías o partidos sin jugar
        matches.append(
            Match(
                date=_parse_date(row["Date"]),
                home_team=teams.canonical(row["HomeTeam"]),
                away_team=teams.canonical(row["AwayTeam"]),
                home_goals=int(float(row["FTHG"])),
                away_goals=int(float(row["FTAG"])),
            )
        )
    return matches


def parse_fixtures(text: str, today: date | None = None, division: str = DIVISION) -> list[Fixture]:
    today = today or date.today()
    fixtures = []
    for row in _rows(text):
        if row.get("Div") != division or not row.get("HomeTeam"):
            continue
        day = _parse_date(row["Date"])
        time = (row.get("Time") or "").strip()
        kickoff = None
        if time:  # la web publica la hora del Reino Unido; se pasa a la de Madrid
            uk = datetime.fromisoformat(f"{day}T{time}").replace(tzinfo=LONDON)
            kickoff = uk.astimezone(MADRID)
            day = kickoff.date().isoformat()
        if day < today.isoformat():
            continue
        best, avg = {}, {}
        for key, best_col, avg_col in ODDS_COLUMNS:
            b, a = _float(row.get(best_col)), _float(row.get(avg_col))
            if b:
                best[key] = b
            if a:
                avg[key] = a
        home, away = teams.canonical(row["HomeTeam"]), teams.canonical(row["AwayTeam"])
        fixtures.append(
            Fixture(
                id=f"{day}-{teams.normalize(home).replace(' ', '-')}-{teams.normalize(away).replace(' ', '-')}",
                date=day,
                home_team=home,
                away_team=away,
                odds=best,
                odds_avg=avg,
                bookmakers={k: "Mejor cuota del mercado" for k in best},
                kickoff=kickoff.isoformat(timespec="minutes") if kickoff else None,
            )
        )
    return fixtures


def download(client: httpx.Client, url: str, cache: Path) -> str:
    """Descarga y guarda en caché; si falla, usa la última copia guardada."""
    try:
        r = client.get(url, timeout=30)
        r.raise_for_status()
        text = r.content.decode("utf-8-sig", errors="replace")
        cache.parent.mkdir(parents=True, exist_ok=True)
        cache.write_text(text, encoding="utf-8")
        return text
    except httpx.HTTPError as e:
        if cache.exists():
            log.warning("Fallo al descargar %s (%s); se usa la caché", url, e)
            return cache.read_text(encoding="utf-8")
        raise


def fetch_results(
    client: httpx.Client, cache_dir: Path, seasons: int, today: date | None = None, division: str = DIVISION
) -> list[Match]:
    """Resultados de las últimas `seasons` temporadas. Una temporada que falle (y no esté en caché)
    se salta con un aviso; solo es un error si no se consigue ninguna."""
    start = season_start(today or date.today())
    matches: list[Match] = []
    errors = []
    for year in range(start - seasons + 1, start + 1):
        code = season_code(year)
        try:
            text = download(client, f"{BASE_URL}/mmz4281/{code}/{division}.csv", cache_dir / f"{division}_{code}.csv")
        except httpx.HTTPError as e:
            log.warning("Temporada %s no disponible: %s", code, e)
            errors.append(e)
            continue
        matches.extend(parse_results(text))
    if not matches and errors:
        raise errors[-1]
    return matches


def fetch_fixtures_text(client: httpx.Client, cache_dir: Path) -> str:
    """El fichero de próximos partidos (todas las ligas): se descarga una vez y se filtra por liga."""
    return download(client, f"{BASE_URL}/fixtures.csv", cache_dir / "fixtures.csv")


def fetch_fixtures(client: httpx.Client, cache_dir: Path, today: date | None = None, division: str = DIVISION) -> list[Fixture]:
    return parse_fixtures(fetch_fixtures_text(client, cache_dir), today, division)
