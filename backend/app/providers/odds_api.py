"""The Odds API: cuotas de LaLiga de muchas casas y resultados recientes, casi en tiempo real.

Necesita una clave (ODDS_API_KEY). Cada consulta gasta créditos del plan mensual:
- /odds: nº de mercados × nº de regiones (h2h + totals en "eu" = 2 créditos).
- /scores con daysFrom: 2 créditos.
La API devuelve en cabeceras los créditos usados y restantes; el actualizador los usa para
repartir las consultas a lo largo del mes sin pasarse.
"""

from __future__ import annotations

import logging
from dataclasses import dataclass
from datetime import datetime
from statistics import mean
from zoneinfo import ZoneInfo

import httpx

from app import teams
from app.data import Fixture, Match

log = logging.getLogger(__name__)

BASE_URL = "https://api.the-odds-api.com/v4"
SPORT = "soccer_spain_la_liga"
SOURCE = "The Odds API"
MADRID = ZoneInfo("Europe/Madrid")


@dataclass
class Quota:
    remaining: int | None = None
    used: int | None = None
    last_cost: int | None = None

    def update(self, headers: httpx.Headers) -> None:
        for attr, header in (("remaining", "x-requests-remaining"), ("used", "x-requests-used"), ("last_cost", "x-requests-last")):
            try:
                setattr(self, attr, int(float(headers[header])))
            except (KeyError, ValueError):
                pass  # cabecera ausente: se mantiene el último valor conocido


def _kickoff(commence_time: str) -> datetime:
    return datetime.fromisoformat(commence_time.replace("Z", "+00:00")).astimezone(MADRID)


def parse_odds(events: list[dict]) -> list[Fixture]:
    """Por selección: mejor cuota (y su casa) y cuota media entre todas las casas."""
    fixtures = []
    for ev in events:
        home_raw, away_raw = ev["home_team"], ev["away_team"]
        prices: dict[str, list[tuple[float, str]]] = {}
        for bm in ev.get("bookmakers", []):
            for market in bm.get("markets", []):
                for out in market.get("outcomes", []):
                    key = None
                    if market["key"] == "h2h":
                        key = {home_raw: "1", away_raw: "2", "Draw": "X"}.get(out["name"])
                    elif market["key"] == "totals" and float(out.get("point", 0)) == 2.5:
                        key = {"Over": "over25", "Under": "under25"}.get(out["name"])
                    elif market["key"] == "btts":
                        key = {"Yes": "btts_yes", "No": "btts_no"}.get(out["name"])
                    if key and out.get("price", 0) > 1:
                        prices.setdefault(key, []).append((float(out["price"]), bm.get("title", bm.get("key", ""))))
        if not prices:
            continue
        kickoff = _kickoff(ev["commence_time"])
        best = {k: max(v) for k, v in prices.items()}
        fixtures.append(
            Fixture(
                id=ev["id"],
                date=kickoff.date().isoformat(),
                home_team=teams.canonical(home_raw),
                away_team=teams.canonical(away_raw),
                odds={k: p for k, (p, _) in best.items()},
                odds_avg={k: round(mean(p for p, _ in v), 3) for k, v in prices.items()},
                bookmakers={k: b for k, (_, b) in best.items()},
                kickoff=kickoff.isoformat(timespec="minutes"),
            )
        )
    return fixtures


def parse_scores(events: list[dict]) -> list[Match]:
    matches = []
    for ev in events:
        if not ev.get("completed") or not ev.get("scores"):
            continue
        score = {s["name"]: s["score"] for s in ev["scores"]}
        try:
            hg, ag = int(score[ev["home_team"]]), int(score[ev["away_team"]])
        except (KeyError, ValueError, TypeError):
            continue
        matches.append(
            Match(
                date=_kickoff(ev["commence_time"]).date().isoformat(),
                home_team=teams.canonical(ev["home_team"]),
                away_team=teams.canonical(ev["away_team"]),
                home_goals=hg,
                away_goals=ag,
            )
        )
    return matches


class OddsApiClient:
    def __init__(self, client: httpx.Client, api_key: str, regions: str = "eu", markets: str = "h2h,totals") -> None:
        self.client = client
        self.api_key = api_key
        self.regions = regions
        self.markets = markets
        self.quota = Quota()

    def _get(self, path: str, **params) -> list[dict]:
        r = self.client.get(f"{BASE_URL}{path}", params={"apiKey": self.api_key, **params}, timeout=30)
        self.quota.update(r.headers)
        if r.status_code >= 400:
            # Mensaje propio: el de httpx incluye la URL, y con ella la clave.
            reason = "clave no válida o sin créditos" if r.status_code in (401, 429) else f"error HTTP {r.status_code}"
            raise httpx.HTTPStatusError(f"The Odds API: {reason}", request=r.request, response=r)
        return r.json()

    def fetch_odds(self) -> list[Fixture]:
        return parse_odds(
            self._get(f"/sports/{SPORT}/odds", regions=self.regions, markets=self.markets, oddsFormat="decimal", dateFormat="iso")
        )

    def fetch_scores(self, days_from: int = 3) -> list[Match]:
        return parse_scores(self._get(f"/sports/{SPORT}/scores", daysFrom=days_from, dateFormat="iso"))
