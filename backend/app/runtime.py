"""Actualizador 24/7: mantiene resultados, cuotas y modelo al día mientras la app está encendida.

- Resultados (football-data.co.uk) cada `results_interval` minutos.
- Resultados recientes (The Odds API, si hay clave) cada `scores_interval` minutos.
- Cuotas: con The Odds API, tan a menudo como permitan los créditos que quedan en el mes
  (ver `paced_interval`); sin clave, el fichero de football-data.co.uk cada pocas horas.
Tras cada actualización se reentrena el modelo y se sustituye de golpe (sin cortar la app).
"""

from __future__ import annotations

import asyncio
import logging
import threading
from dataclasses import asdict, dataclass
from datetime import date, datetime, timedelta, timezone
from zoneinfo import ZoneInfo

import httpx

from app.config import Settings
from app.data import Fixture, Match
from app.providers import football_data, odds_api
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
) -> float:
    """Minutos hasta la próxima consulta de cuotas para no agotar los créditos antes de fin de mes.

    Reserva los créditos que necesitarán las consultas de resultados (/scores) del resto del mes.
    """
    if remaining is None or not cost:
        return 60.0  # aún no se conoce la cuota: ritmo prudente
    minutes_left = minutes_until_month_end(now)
    reserved = SCORES_COST * minutes_left / scores_interval if scores_interval else 0
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

    def ok(self, count: int, interval: float) -> None:
        now = _now()
        self.updated_at, self.count, self.error = now.isoformat(timespec="seconds"), count, None
        self.next_update = (now + timedelta(minutes=interval)).isoformat(timespec="seconds")

    def failed(self, error: Exception, retry: float) -> None:
        self.error = str(error)[:300]
        self.next_update = (_now() + timedelta(minutes=retry)).isoformat(timespec="seconds")

    def due(self, now: datetime) -> bool:
        return self.next_update is None or datetime.fromisoformat(self.next_update) <= now


def merge_matches(*sources: list[Match]) -> list[Match]:
    """Une resultados de varias fuentes; si un partido está repetido, gana la última fuente."""
    merged: dict[tuple[str, str, str], Match] = {}
    for matches in sources:
        for m in matches:
            merged[(m.date, m.home_team, m.away_team)] = m
    return sorted(merged.values(), key=lambda m: m.date)


class Runtime:
    def __init__(self, settings: Settings, http: httpx.Client | None = None) -> None:
        self.settings = settings
        self.live = settings.data_source == "live"
        self.http = http or httpx.Client(headers={"User-Agent": "PHI.BET/0.5 (analisis deportivo)"}, follow_redirects=True)
        self.odds_client = (
            odds_api.OddsApiClient(self.http, settings.odds_api_key, settings.odds_regions, settings.odds_markets)
            if self.live and settings.odds_api_key
            else None
        )
        self._lock = threading.Lock()
        self.history: list[Match] = []
        self.recent: list[Match] = []
        self.fixtures: list[Fixture] = []
        self.engine: PredictionEngine | None = None
        self.feeds = {
            "results": Feed(football_data.SOURCE),
            "scores": Feed(odds_api.SOURCE if self.odds_client else "—"),
            "odds": Feed(odds_api.SOURCE if self.odds_client else football_data.SOURCE),
        }
        if not self.live:
            self.engine = PredictionEngine.from_disk()
            for feed in self.feeds.values():
                feed.source = "Datos de ejemplo"
            self.feeds["results"].count = len(self.engine.matches)
            self.feeds["odds"].count = len(self.engine.fixtures)

    # --- Actualizaciones --------------------------------------------------------

    def refresh_results(self) -> None:
        feed = self.feeds["results"]
        try:
            self.history = football_data.fetch_results(self.http, self.settings.cache_dir, self.settings.history_seasons)
            feed.ok(len(self.history), self.settings.results_interval)
        except Exception as e:  # noqa: BLE001 - un fallo de red no debe tumbar la app
            log.exception("Error actualizando resultados")
            feed.failed(e, retry=30)
        self._rebuild()

    def refresh_scores(self) -> None:
        feed = self.feeds["scores"]
        try:
            self.recent = self.odds_client.fetch_scores(days_from=3)
            feed.ok(len(self.recent), self.settings.scores_interval)
        except Exception as e:  # noqa: BLE001
            log.exception("Error actualizando resultados recientes")
            feed.failed(e, retry=60)
        self._rebuild()

    def refresh_odds(self) -> None:
        feed = self.feeds["odds"]
        try:
            if self.odds_client:
                self.fixtures = self.odds_client.fetch_odds()
                q = self.odds_client.quota
                interval = paced_interval(
                    q.remaining, q.last_cost, _now(), self.settings.odds_min_interval, self.settings.scores_interval
                )
            else:
                self.fixtures = football_data.fetch_fixtures(self.http, self.settings.cache_dir)
                interval = self.settings.fallback_odds_interval
            feed.ok(len(self.fixtures), interval)
        except Exception as e:  # noqa: BLE001
            log.exception("Error actualizando cuotas")
            feed.failed(e, retry=15)
        self._rebuild()

    def _rebuild(self) -> None:
        matches = merge_matches(self.history, self.recent)
        if not matches:
            return
        today = datetime.now(MADRID).date().isoformat()
        played = {(m.home_team, m.away_team) for m in matches if m.date >= _days_ago(7)}
        upcoming = [f for f in self.fixtures if f.date >= today and (f.home_team, f.away_team) not in played]
        try:
            engine = PredictionEngine(matches, upcoming)
        except Exception:  # noqa: BLE001 - si falla, se sigue sirviendo el modelo anterior
            log.exception("Error reentrenando el modelo")
            return
        with self._lock:
            self.engine = engine

    def refresh_due(self) -> None:
        """Ejecuta las actualizaciones que tocan ahora (bloqueante)."""
        now = _now()
        if self.feeds["results"].due(now):
            self.refresh_results()
        if self.odds_client and self.feeds["scores"].due(now):
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

    def status(self) -> dict:
        q = self.odds_client.quota if self.odds_client else None
        return {
            "data_source": self.settings.data_source,
            "league": "LaLiga" if self.live else "Liga de ejemplo",
            "ready": self.engine is not None,
            "feeds": {k: asdict(v) for k, v in self.feeds.items() if self.odds_client or k != "scores"},
            "credits_remaining": q.remaining if q else None,
            "credits_used": q.used if q else None,
        }


def _days_ago(days: int) -> str:
    return (date.today() - timedelta(days=days)).isoformat()
