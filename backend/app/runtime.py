"""Actualizador 24/7: mantiene resultados, cuotas y modelos al día mientras la app está encendida.

Para cada liga (app.leagues):
- Resultados de football-data.co.uk cada `results_interval` minutos; si no responde, de
  openfootball. openfootball aporta además los partidos de los próximos días (sin cuotas).
- Resultados recientes de The Odds API (si hay clave) cada `scores_interval` minutos.
- Cuotas: The Odds API para las ligas de `odds_api_leagues`, tan a menudo como permitan los
  créditos del mes (ver `paced_interval`); el resto, del fichero de football-data.co.uk.
Tras cada actualización se reentrena el modelo de cada liga y se sustituye de golpe (sin cortar
la app). Si solo cambian las cuotas, se reutiliza el modelo ya entrenado.
"""

from __future__ import annotations

import asyncio
import logging
import threading
from dataclasses import asdict, dataclass, field
from datetime import date, datetime, timedelta, timezone
from zoneinfo import ZoneInfo

import httpx

from app.config import Settings
from app.data import Fixture, Match
from app.leagues import LEAGUES, SAMPLE, League
from app.providers import football_data, odds_api, openfootball
from app.service import PredictionEngine

log = logging.getLogger(__name__)
MADRID = ZoneInfo("Europe/Madrid")
SCORES_COST = 2  # créditos de /scores con daysFrom


def _now() -> datetime:
    return datetime.now(timezone.utc)


def minutes_until_month_end(now: datetime) -> float:
    first_next = (now.replace(day=1, hour=0, minute=0, second=0, microsecond=0) + timedelta(days=32)).replace(day=1)
    return (first_next - now).total_seconds() / 60


def paced_interval(
    remaining: int | None,
    cost: int | None,
    now: datetime,
    min_minutes: float,
    scores_interval: float | None = None,
    scores_cost: int = SCORES_COST,
) -> float:
    """Minutos hasta la próxima consulta de cuotas para no agotar los créditos antes de fin de mes.

    `cost` es lo que gasta una ronda completa de cuotas. Reserva los créditos que necesitarán las
    consultas de resultados (/scores) del resto del mes (`scores_cost` por ronda).
    """
    if remaining is None or not cost:
        return 60.0  # aún no se conoce la cuota: ritmo prudente
    minutes_left = minutes_until_month_end(now)
    reserved = scores_cost * minutes_left / scores_interval if scores_interval else 0
    usable = remaining - reserved
    if usable < cost:
        return minutes_left  # sin créditos: esperar al reinicio mensual
    return max(min_minutes, minutes_left * cost / usable)


@dataclass
class Feed:
    source: str
    updated_at: str | None = None
    next_update: str | None = None
    count: int = 0
    error: str | None = None

    def ok(self, count: int, interval: float, error: str | None = None) -> None:
        now = _now()
        self.updated_at, self.count, self.error = now.isoformat(timespec="seconds"), count, error
        self.next_update = (now + timedelta(minutes=interval)).isoformat(timespec="seconds")

    def failed(self, error: Exception | str, retry: float) -> None:
        self.error = str(error)[:300]
        self.next_update = (_now() + timedelta(minutes=retry)).isoformat(timespec="seconds")

    def due(self, now: datetime) -> bool:
        return self.next_update is None or datetime.fromisoformat(self.next_update) <= now


@dataclass
class LeagueData:
    league: League
    history: list[Match] = field(default_factory=list)
    recent: list[Match] = field(default_factory=list)
    odds: list[Fixture] = field(default_factory=list)  # próximos partidos con cuotas
    calendar: list[Fixture] = field(default_factory=list)  # próximos partidos sin cuotas (openfootball)
    results_source: str | None = None
    error: str | None = None
    engine: PredictionEngine | None = None


def merge_matches(*sources: list[Match]) -> list[Match]:
    """Une resultados de varias fuentes; si un partido está repetido, gana la última fuente."""
    merged: dict[tuple[str, str, str], Match] = {}
    for matches in sources:
        for m in matches:
            merged[(m.date, m.home_team, m.away_team)] = m
    return sorted(merged.values(), key=lambda m: m.date)


def merge_fixtures(with_odds: list[Fixture], calendar: list[Fixture]) -> list[Fixture]:
    """Partidos con cuotas + los del calendario que no estén ya (mismo día y mismo local o visitante,
    por si un proveedor escribe distinto uno de los dos equipos)."""
    taken = {(f.date, f.home_team) for f in with_odds} | {(f.date, f.away_team) for f in with_odds}
    extra = [f for f in calendar if (f.date, f.home_team) not in taken and (f.date, f.away_team) not in taken]
    return sorted([*with_odds, *extra], key=lambda f: (f.date, f.kickoff or "", f.home_team))


def _errors(errors: dict[str, str]) -> str | None:
    """{'LaLiga': 'x', 'Serie A': 'x', 'Premier': 'y'} -> 'LaLiga, Serie A: x · Premier: y'."""
    grouped: dict[str, list[str]] = {}
    for league, message in errors.items():
        grouped.setdefault(message, []).append(league)
    return " · ".join(f"{', '.join(names)}: {msg}" for msg, names in grouped.items())[:300] or None


class Runtime:
    def __init__(self, settings: Settings, http: httpx.Client | None = None) -> None:
        self.settings = settings
        self.live = settings.data_source == "live"
        self.http = http or httpx.Client(headers={"User-Agent": "PHI.BET/0.6 (analisis deportivo)"}, follow_redirects=True)
        self.odds_client = (
            odds_api.OddsApiClient(self.http, settings.odds_api_key, settings.odds_regions, settings.odds_markets)
            if self.live and settings.odds_api_key
            else None
        )
        self._lock = threading.Lock()
        keys = settings.leagues if self.live else ()
        self.leagues: dict[str, LeagueData] = {k: LeagueData(LEAGUES[k]) for k in keys}
        self.api_leagues = [k for k in keys if self.odds_client and k in settings.odds_api_leagues]
        self.feeds = {
            "results": Feed(football_data.SOURCE),
            "scores": Feed(odds_api.SOURCE if self.api_leagues else "—"),
            "odds": Feed(self._odds_source()),
        }
        if not self.live:
            engine = PredictionEngine.from_disk()
            self.leagues = {SAMPLE.key: LeagueData(SAMPLE, engine=engine)}
            for feed in self.feeds.values():
                feed.source = "Datos de ejemplo"
            self.feeds["results"].count = len(engine.matches)
            self.feeds["odds"].count = len(engine.fixtures)

    def _odds_source(self) -> str:
        if not self.api_leagues:
            return football_data.SOURCE
        if len(self.api_leagues) == len(self.leagues):
            return odds_api.SOURCE
        return f"{odds_api.SOURCE} + {football_data.SOURCE}"

    # --- Acceso ------------------------------------------------------------------

    @property
    def default_league(self) -> str:
        """La primera liga con datos (o la primera configurada)."""
        for key, data in self.leagues.items():
            if data.engine is not None:
                return key
        return next(iter(self.leagues))

    def engine(self, league: str | None = None) -> PredictionEngine | None:
        data = self.leagues.get(league or self.default_league)
        return data.engine if data else None

    # --- Actualizaciones --------------------------------------------------------

    def refresh_results(self) -> None:
        feed, s = self.feeds["results"], self.settings
        errors: dict[str, str] = {}
        sources = set()
        for data in self.leagues.values():
            lg = data.league
            history: list[Match] = []
            try:
                history = football_data.fetch_results(self.http, s.cache_dir, s.history_seasons, division=lg.football_data)
                data.results_source = football_data.SOURCE
            except Exception as e:  # noqa: BLE001 - un fallo de red no debe tumbar la app
                log.warning("football-data.co.uk sin resultados de %s: %s", lg.name, e)
            try:
                backup, data.calendar = openfootball.fetch(self.http, s.cache_dir, lg.openfootball, s.history_seasons)
                if not history:
                    history, data.results_source = backup, openfootball.SOURCE
            except Exception as e:  # noqa: BLE001
                log.warning("openfootball sin datos de %s: %s", lg.name, e)
            if history:
                data.history, data.error = history, None
                sources.add(data.results_source)
            else:
                data.error = errors[lg.name] = "sin resultados (ninguna fuente respondió)"
            self._rebuild(data)
        feed.source = " + ".join(sorted(sources)) or football_data.SOURCE
        total = sum(len(d.history) for d in self.leagues.values())
        if total:
            feed.ok(total, s.results_interval, _errors(errors))
        else:
            feed.failed(_errors(errors) or "sin resultados", retry=30)

    def refresh_scores(self) -> None:
        feed = self.feeds["scores"]
        errors: dict[str, str] = {}
        for key in self.api_leagues:
            data = self.leagues[key]
            try:
                data.recent = self.odds_client.fetch_scores(days_from=3, sport=data.league.odds_api)
            except Exception as e:  # noqa: BLE001
                log.exception("Error actualizando resultados recientes de %s", data.league.name)
                errors[data.league.name] = str(e)
            self._rebuild(data)
        count = sum(len(self.leagues[k].recent) for k in self.api_leagues)
        if len(errors) == len(self.api_leagues):
            feed.failed(_errors(errors), retry=60)
        else:
            feed.ok(count, self.settings.scores_interval, _errors(errors))

    def refresh_odds(self) -> None:
        feed, s = self.feeds["odds"], self.settings
        errors: dict[str, str] = {}
        round_cost = 0
        text: str | Exception | None = None  # fichero de football-data: se descarga una vez por ronda
        for key, data in self.leagues.items():
            lg = data.league
            try:
                if key in self.api_leagues:
                    data.odds = self.odds_client.fetch_odds(lg.odds_api)
                    round_cost += self.odds_client.quota.last_cost or 0
                else:
                    if text is None:
                        try:
                            text = football_data.fetch_fixtures_text(self.http, s.cache_dir)
                        except Exception as e:  # noqa: BLE001
                            text = e
                    if isinstance(text, Exception):
                        raise text
                    data.odds = football_data.parse_fixtures(text, division=lg.football_data)
            except Exception as e:  # noqa: BLE001
                log.warning("Sin cuotas de %s: %s", lg.name, e)
                errors[lg.name] = str(e)[:120]
            self._rebuild(data)
        if self.api_leagues:
            q = self.odds_client.quota
            scores_cost = SCORES_COST * len(self.api_leagues)
            interval = paced_interval(q.remaining, round_cost, _now(), s.odds_min_interval, s.scores_interval, scores_cost)
        else:
            interval = s.fallback_odds_interval
        count = sum(len(d.odds) for d in self.leagues.values())
        if len(errors) == len(self.leagues):
            feed.failed(_errors(errors), retry=15)
        else:
            feed.ok(count, interval, _errors(errors))

    def _rebuild(self, data: LeagueData) -> None:
        matches = merge_matches(data.history, data.recent)
        if not matches:
            return
        today = datetime.now(MADRID).date().isoformat()
        played = {(m.home_team, m.away_team) for m in matches if m.date >= _days_ago(7)}
        upcoming = [
            f for f in merge_fixtures(data.odds, data.calendar) if f.date >= today and (f.home_team, f.away_team) not in played
        ]
        try:
            engine = PredictionEngine(matches, upcoming, base=data.engine)
        except Exception:  # noqa: BLE001 - si falla, se sigue sirviendo el modelo anterior
            log.exception("Error reentrenando el modelo de %s", data.league.name)
            return
        with self._lock:
            data.engine = engine

    def refresh_due(self) -> None:
        """Ejecuta las actualizaciones que tocan ahora (bloqueante)."""
        now = _now()
        if self.feeds["results"].due(now):
            self.refresh_results()
        if self.api_leagues and self.feeds["scores"].due(now):
            self.refresh_scores()
        if self.feeds["odds"].due(now):
            self.refresh_odds()

    async def run_forever(self) -> None:
        while True:
            try:
                await asyncio.to_thread(self.refresh_due)
            except Exception:  # noqa: BLE001
                log.exception("Error en el ciclo de actualización")
            await asyncio.sleep(60)

    # --- Estado -----------------------------------------------------------------

    def league_list(self) -> list[dict]:
        out = []
        for key, d in self.leagues.items():
            e = d.engine
            out.append(
                {
                    "key": key,
                    "name": d.league.name,
                    "country": d.league.country,
                    "ready": e is not None,
                    "matches": len(e.matches) if e else 0,
                    "fixtures": len(e.fixtures) if e else 0,
                    "with_odds": sum(1 for f in e.fixtures.values() if f.odds) if e else 0,
                    "results_source": d.results_source,
                    "error": d.error,
                }
            )
        return out

    def status(self) -> dict:
        q = self.odds_client.quota if self.odds_client else None
        default = self.default_league
        return {
            "data_source": self.settings.data_source,
            "league": self.leagues[default].league.name,  # compatibilidad: liga por defecto
            "default_league": default,
            "leagues": self.league_list(),
            "ready": any(d.engine is not None for d in self.leagues.values()),
            "feeds": {k: asdict(v) for k, v in self.feeds.items() if self.api_leagues or k != "scores"},
            "credits_remaining": q.remaining if q else None,
            "credits_used": q.used if q else None,
        }


def _days_ago(days: int) -> str:
    return (date.today() - timedelta(days=days)).isoformat()
