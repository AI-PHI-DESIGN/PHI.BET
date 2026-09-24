"""Nombres de equipos de LaLiga: cada proveedor los escribe distinto, aquí se unifican.

`canonical()` devuelve el nombre que usa la app. Si un nombre no está en la tabla se busca el
más parecido; si tampoco hay ninguno parecido se deja tal cual (y se registra en el log).
"""

from __future__ import annotations

import difflib
import logging
import re
import unicodedata

log = logging.getLogger(__name__)

# Nombre en la app -> alias conocidos (football-data.co.uk, The Odds API, nombres oficiales).
ALIASES: dict[str, tuple[str, ...]] = {
    "Alavés": ("Alaves", "Deportivo Alaves", "Deportivo Alavés"),
    "Almería": ("Almeria", "UD Almeria", "UD Almería"),
    "Athletic Club": ("Ath Bilbao", "Athletic Bilbao", "Athletic Club Bilbao"),
    "Atlético de Madrid": ("Ath Madrid", "Atletico Madrid", "Atlético Madrid", "Club Atletico de Madrid"),
    "Barcelona": ("FC Barcelona", "Barça"),
    "Cádiz": ("Cadiz", "Cadiz CF", "Cádiz CF"),
    "Celta de Vigo": ("Celta", "Celta Vigo", "RC Celta"),
    "Elche": ("Elche CF",),
    "Espanyol": ("Espanol", "RCD Espanyol", "Espanyol Barcelona"),
    "Getafe": ("Getafe CF",),
    "Girona": ("Girona FC",),
    "Granada": ("Granada CF",),
    "Las Palmas": ("UD Las Palmas",),
    "Leganés": ("Leganes", "CD Leganes", "CD Leganés"),
    "Levante": ("Levante UD",),
    "Mallorca": ("RCD Mallorca",),
    "Osasuna": ("CA Osasuna",),
    "Real Oviedo": ("Oviedo",),
    "Rayo Vallecano": ("Vallecano",),
    "Real Betis": ("Betis",),
    "Real Madrid": ("Real Madrid CF",),
    "Real Sociedad": ("Sociedad",),
    "Racing de Santander": ("Santander", "Racing Santander"),
    "Sevilla": ("Sevilla FC",),
    "Sporting de Gijón": ("Sp Gijon", "Sporting Gijon"),
    "Valencia": ("Valencia CF",),
    "Valladolid": ("Real Valladolid",),
    "Villarreal": ("Villarreal CF",),
    "Deportivo de La Coruña": ("La Coruna", "Deportivo La Coruna", "Deportivo"),
    "Eibar": ("SD Eibar",),
    "Huesca": ("SD Huesca",),
}

_NOISE = re.compile(r"\b(cf|fc|ud|cd|rcd|sd|ca|club|de|del|la)\b")


def normalize(name: str) -> str:
    """Minúsculas, sin tildes, sin siglas tipo CF/UD y sin signos."""
    s = unicodedata.normalize("NFKD", name).encode("ascii", "ignore").decode().lower()
    s = re.sub(r"[^a-z0-9 ]", " ", s)
    s = _NOISE.sub(" ", s)
    return " ".join(s.split())


_LOOKUP: dict[str, str] = {}
for _canon, _aliases in ALIASES.items():
    for _alias in (_canon, *_aliases):
        _LOOKUP[normalize(_alias)] = _canon


def canonical(name: str) -> str:
    key = normalize(name)
    if key in _LOOKUP:
        return _LOOKUP[key]
    close = difflib.get_close_matches(key, list(_LOOKUP), n=1, cutoff=0.85)
    if close:
        _LOOKUP[key] = _LOOKUP[close[0]]
        return _LOOKUP[key]
    log.warning("Equipo sin mapear: %r (se usa tal cual)", name)
    _LOOKUP[key] = name.strip()
    return _LOOKUP[key]
