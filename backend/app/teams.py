"""Nombres de equipos: cada proveedor los escribe distinto, aquí se unifican.

`canonical()` devuelve el nombre que usa la app. Si un nombre no está en la tabla se busca el
más parecido; si tampoco hay ninguno parecido se deja tal cual (y se registra en el log).
"""

from __future__ import annotations

import difflib
import logging
import re
import unicodedata

log = logging.getLogger(__name__)

# Nombre en la app -> alias conocidos (football-data.co.uk, The Odds API, openfootball, nombres oficiales).
ALIASES: dict[str, tuple[str, ...]] = {
    # --- LaLiga ---
    "Alavés": ("Alaves", "Deportivo Alaves", "Deportivo Alavés"),
    "Almería": ("Almeria", "UD Almeria", "UD Almería"),
    "Athletic Club": ("Ath Bilbao", "Athletic Bilbao", "Athletic Club Bilbao"),
    "Atlético de Madrid": ("Ath Madrid", "Atletico Madrid", "Atlético Madrid", "Club Atletico de Madrid", "Club Atlético de Madrid"),
    "Barcelona": ("FC Barcelona", "Barça"),
    "Cádiz": ("Cadiz", "Cadiz CF", "Cádiz CF"),
    "Celta de Vigo": ("Celta", "Celta Vigo", "RC Celta", "RC Celta de Vigo"),
    "Elche": ("Elche CF",),
    "Espanyol": ("Espanol", "RCD Espanyol", "Espanyol Barcelona", "RCD Espanyol de Barcelona"),
    "Getafe": ("Getafe CF",),
    "Girona": ("Girona FC",),
    "Granada": ("Granada CF",),
    "Las Palmas": ("UD Las Palmas",),
    "Leganés": ("Leganes", "CD Leganes", "CD Leganés"),
    "Levante": ("Levante UD",),
    "Málaga": ("Malaga", "Malaga CF", "Málaga CF"),
    "Mallorca": ("RCD Mallorca",),
    "Osasuna": ("CA Osasuna",),
    "Real Oviedo": ("Oviedo",),
    "Rayo Vallecano": ("Vallecano", "Rayo Vallecano de Madrid"),
    "Real Betis": ("Betis", "Real Betis Balompié", "Real Betis Balompie"),
    "Real Madrid": ("Real Madrid CF",),
    "Real Sociedad": ("Sociedad", "Real Sociedad de Fútbol", "Real Sociedad de Futbol"),
    "Racing de Santander": ("Santander", "Racing Santander", "Real Racing Club de Santander", "Racing Club Santander"),
    "Sevilla": ("Sevilla FC",),
    "Sporting de Gijón": ("Sp Gijon", "Sporting Gijon"),
    "Valencia": ("Valencia CF",),
    "Valladolid": ("Real Valladolid", "Real Valladolid CF"),
    "Villarreal": ("Villarreal CF",),
    "Deportivo de La Coruña": ("La Coruna", "Deportivo La Coruna", "Deportivo", "RC Deportivo La Coruña", "RC Deportivo La Coruna"),
    "Eibar": ("SD Eibar",),
    "Huesca": ("SD Huesca",),
    # --- Premier League ---
    "Arsenal": ("Arsenal FC",),
    "Aston Villa": ("Aston Villa FC",),
    "Bournemouth": ("AFC Bournemouth",),
    "Brentford": ("Brentford FC",),
    "Brighton": ("Brighton & Hove Albion FC", "Brighton and Hove Albion", "Brighton & Hove Albion", "Brighton Hove"),
    "Burnley": ("Burnley FC",),
    "Chelsea": ("Chelsea FC",),
    "Coventry": ("Coventry City FC", "Coventry City"),
    "Crystal Palace": ("Crystal Palace FC",),
    "Everton": ("Everton FC",),
    "Fulham": ("Fulham FC",),
    "Hull City": ("Hull", "Hull City AFC"),
    "Ipswich": ("Ipswich Town FC", "Ipswich Town"),
    "Leeds": ("Leeds United FC", "Leeds United"),
    "Leicester": ("Leicester City FC", "Leicester City"),
    "Liverpool": ("Liverpool FC",),
    "Luton": ("Luton Town FC", "Luton Town"),
    "Manchester City": ("Man City", "Manchester City FC"),
    "Manchester United": ("Man United", "Man Utd", "Manchester United FC"),
    "Newcastle": ("Newcastle United FC", "Newcastle United"),
    "Nottingham Forest": ("Nott'm Forest", "Nottingham Forest FC", "Nottingham"),
    "Sheffield United": ("Sheffield United FC", "Sheffield Utd", "Sheffield Weds"),
    "Southampton": ("Southampton FC",),
    "Sunderland": ("Sunderland AFC",),
    "Tottenham": ("Tottenham Hotspur FC", "Tottenham Hotspur", "Spurs"),
    "West Ham": ("West Ham United FC", "West Ham United"),
    "Wolves": ("Wolverhampton Wanderers FC", "Wolverhampton Wanderers", "Wolverhampton"),
    # --- Serie A ---
    "Atalanta": ("Atalanta BC",),
    "Bologna": ("Bologna FC 1909", "Bologna FC"),
    "Cagliari": ("Cagliari Calcio",),
    "Como": ("Como 1907",),
    "Cremonese": ("US Cremonese",),
    "Empoli": ("Empoli FC",),
    "Fiorentina": ("ACF Fiorentina",),
    "Frosinone": ("Frosinone Calcio",),
    "Genoa": ("Genoa CFC",),
    "Inter de Milán": ("Inter", "Inter Milan", "FC Internazionale Milano", "Internazionale"),
    "Juventus": ("Juventus FC",),
    "Lazio": ("SS Lazio",),
    "Lecce": ("US Lecce",),
    "Milan": ("AC Milan",),
    "Monza": ("AC Monza",),
    "Napoli": ("SSC Napoli",),
    "Parma": ("Parma Calcio 1913", "Parma Calcio"),
    "Pisa": ("AC Pisa 1909", "Pisa SC"),
    "Roma": ("AS Roma",),
    "Salernitana": ("US Salernitana 1919",),
    "Sassuolo": ("US Sassuolo Calcio", "US Sassuolo"),
    "Torino": ("Torino FC",),
    "Udinese": ("Udinese Calcio",),
    "Venezia": ("Venezia FC",),
    "Verona": ("Hellas Verona FC", "Hellas Verona"),
    # --- Bundesliga ---
    "Augsburg": ("FC Augsburg",),
    "Bayern de Múnich": ("Bayern Munich", "FC Bayern München", "Bayern München", "Bayern Munchen"),
    "Bochum": ("VfL Bochum 1848", "VfL Bochum"),
    "Darmstadt": ("SV Darmstadt 98",),
    "Borussia Dortmund": ("Dortmund",),
    "Eintracht Fráncfort": ("Ein Frankfurt", "Eintracht Frankfurt"),
    "Elversberg": ("SV 07 Elversberg", "SV Elversberg"),
    "Colonia": ("FC Koln", "1. FC Köln", "1. FC Koln", "FC Cologne"),
    "Friburgo": ("Freiburg", "SC Freiburg"),
    "Hamburgo": ("Hamburg", "Hamburger SV"),
    "Heidenheim": ("1. FC Heidenheim 1846", "1. FC Heidenheim", "FC Heidenheim"),
    "Hoffenheim": ("TSG 1899 Hoffenheim", "TSG Hoffenheim"),
    "Holstein Kiel": ("Kiel",),
    "Bayer Leverkusen": ("Leverkusen", "Bayer 04 Leverkusen"),
    "Borussia Mönchengladbach": ("M'gladbach", "Borussia Monchengladbach", "Monchengladbach"),
    "Mainz": ("1. FSV Mainz 05", "FSV Mainz 05", "Mainz 05"),
    "Paderborn": ("SC Paderborn 07", "SC Paderborn"),
    "RB Leipzig": ("Leipzig", "RasenBallsport Leipzig"),
    "St. Pauli": ("St Pauli", "FC St. Pauli 1910", "FC St. Pauli"),
    "Schalke 04": ("Schalke", "FC Schalke 04"),
    "Stuttgart": ("VfB Stuttgart",),
    "Unión Berlín": ("Union Berlin", "1. FC Union Berlin"),
    "Werder Bremen": ("SV Werder Bremen",),
    "Wolfsburgo": ("Wolfsburg", "VfL Wolfsburg"),
    # --- Ligue 1 ---
    "Angers": ("Angers SCO",),
    "Auxerre": ("AJ Auxerre",),
    "Brest": ("Stade Brestois 29", "Stade Brestois"),
    "Clermont": ("Clermont Foot 63", "Clermont Foot"),
    "Le Havre": ("Le Havre AC",),
    "Le Mans": ("Le Mans FC",),
    "Lens": ("Racing Club de Lens", "RC Lens"),
    "Lille": ("Lille OSC",),
    "Lorient": ("FC Lorient",),
    "Lyon": ("Olympique Lyonnais",),
    "Marsella": ("Marseille", "Olympique de Marseille"),
    "Metz": ("FC Metz",),
    "Mónaco": ("Monaco", "AS Monaco FC", "AS Monaco"),
    "Montpellier": ("Montpellier HSC",),
    "Nantes": ("FC Nantes",),
    "Niza": ("Nice", "OGC Nice"),
    "Paris FC": (),
    "PSG": ("Paris SG", "Paris Saint-Germain FC", "Paris Saint Germain", "Paris Saint-Germain"),
    "Reims": ("Stade de Reims",),
    "Rennes": ("Stade Rennais FC 1901", "Stade Rennais", "Stade Rennais FC"),
    "Saint-Étienne": ("St Etienne", "AS Saint-Étienne", "Saint Etienne", "AS Saint-Etienne"),
    "Estrasburgo": ("Strasbourg", "RC Strasbourg Alsace", "RC Strasbourg"),
    "Toulouse": ("Toulouse FC",),
    "Troyes": ("ES Troyes AC", "ESTAC Troyes"),
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
