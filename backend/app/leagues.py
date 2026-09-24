"""Ligas que analiza PHI.BET y su código en cada proveedor de datos."""

from __future__ import annotations

from dataclasses import dataclass


@dataclass(frozen=True)
class League:
    key: str  # identificador en la API y en la web (?league=premier)
    name: str
    country: str
    football_data: str  # división en football-data.co.uk (SP1, E0…)
    odds_api: str  # deporte en The Odds API
    openfootball: str  # fichero en openfootball/football.json (es.1, en.1…)


LEAGUES: dict[str, League] = {
    lg.key: lg
    for lg in (
        League("laliga", "LaLiga", "España", "SP1", "soccer_spain_la_liga", "es.1"),
        League("premier", "Premier League", "Inglaterra", "E0", "soccer_epl", "en.1"),
        League("seriea", "Serie A", "Italia", "I1", "soccer_italy_serie_a", "it.1"),
        League("bundesliga", "Bundesliga", "Alemania", "D1", "soccer_germany_bundesliga", "de.1"),
        League("ligue1", "Ligue 1", "Francia", "F1", "soccer_france_ligue_one", "fr.1"),
    )
}
DEFAULT_LEAGUE = "laliga"
SAMPLE = League("ejemplo", "Liga de ejemplo", "—", "", "", "")


def parse_keys(value: str | None, default: tuple[str, ...]) -> tuple[str, ...]:
    """'laliga, premier' -> ('laliga', 'premier'); 'all' = todas. Claves desconocidas: error."""
    if value is None or not value.strip():
        return default
    if value.strip().lower() in ("all", "todas"):
        return tuple(LEAGUES)
    keys = tuple(k.strip().lower() for k in value.split(",") if k.strip())
    unknown = [k for k in keys if k not in LEAGUES]
    if unknown:
        raise ValueError(f"Liga desconocida: {', '.join(unknown)} (válidas: {', '.join(LEAGUES)})")
    return keys
