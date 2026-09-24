from datetime import datetime, timedelta, timezone

import httpx

from app.config import Settings, load_settings
from app.data import load_matches
from app.runtime import Runtime


def results_csv() -> str:
    """El histórico de ejemplo en el formato de football-data.co.uk."""
    rows = ["Div,Date,Time,HomeTeam,AwayTeam,FTHG,FTAG,FTR"]
    for m in load_matches():
        y, mo, d = m.date.split("-")
        rows.append(f"SP1,{d}/{mo}/{y},20:00,{m.home_team},{m.away_team},{m.home_goals},{m.away_goals},H")
    return "\n".join(rows)


def odds_json() -> list[dict]:
    kickoff = (datetime.now(timezone.utc) + timedelta(days=2)).replace(hour=18, minute=0, second=0, microsecond=0)
    h2h = [{"name": "Atlético Phi", "price": 1.7}, {"name": "CF Epsilon", "price": 5.5}, {"name": "Draw", "price": 3.9}]
    return [{"id": "ev1", "commence_time": kickoff.isoformat().replace("+00:00", "Z"), "home_team": "Atlético Phi",
             "away_team": "CF Epsilon", "bookmakers": [{"key": "b", "title": "Casa B", "markets": [{"key": "h2h", "outcomes": h2h}]}]}]


class FakeProviders:
    def __init__(self):
        self.calls: list[str] = []
        self.fail = False

    def __call__(self, request: httpx.Request) -> httpx.Response:
        self.calls.append(request.url.path)
        if self.fail:
            return httpx.Response(503)
        if request.url.host == "www.football-data.co.uk":
            if request.url.path.endswith("/2627/SP1.csv"):
                return httpx.Response(200, text=results_csv())
            return httpx.Response(404)
        headers = {"x-requests-remaining": "400", "x-requests-used": "100", "x-requests-last": "2"}
        if request.url.path.endswith("/odds"):
            return httpx.Response(200, json=odds_json(), headers=headers)
        if request.url.path.endswith("/scores"):
            return httpx.Response(200, json=[], headers=headers)
        return httpx.Response(404)


def make_runtime(tmp_path, providers, key="k"):
    settings = Settings(data_source="live", odds_api_key=key, cache_dir=tmp_path, history_seasons=2)
    return Runtime(settings, http=httpx.Client(transport=httpx.MockTransport(providers)))


def test_live_refresh_builds_engine_with_real_feeds(tmp_path):
    providers = FakeProviders()
    rt = make_runtime(tmp_path, providers)
    assert rt.engine is None
    rt.refresh_due()
    assert rt.engine is not None
    assert len(rt.engine.matches) == 168
    [fixture] = rt.engine.fixtures.values()
    assert fixture.odds["1"] == 1.7 and fixture.bookmakers["1"] == "Casa B"
    picks = rt.engine.picks(None, 0.3, "high")
    assert picks["picks"] and picks["date"] == fixture.date

    status = rt.status()
    assert status["ready"] and status["credits_remaining"] == 400
    assert status["feeds"]["odds"]["source"] == "The Odds API"
    assert status["feeds"]["odds"]["error"] is None
    # Con 400 créditos no se consulta cada 5 minutos: el siguiente turno queda más lejos.
    next_odds = datetime.fromisoformat(status["feeds"]["odds"]["next_update"])
    assert next_odds - datetime.now(timezone.utc) > timedelta(minutes=5)


def test_refresh_only_runs_due_feeds(tmp_path):
    providers = FakeProviders()
    rt = make_runtime(tmp_path, providers)
    rt.refresh_due()
    n = len(providers.calls)
    rt.refresh_due()  # nada vence todavía
    assert len(providers.calls) == n


def test_network_failure_keeps_serving_from_cache(tmp_path):
    providers = FakeProviders()
    rt = make_runtime(tmp_path, providers)
    rt.refresh_due()
    providers.fail = True
    rt.refresh_results()
    assert rt.feeds["results"].error is None  # se leyó la caché
    rt.refresh_odds()
    assert rt.feeds["odds"].error  # sin caché de cuotas: se informa del error...
    assert rt.engine is not None  # ...pero la app sigue funcionando


def test_without_api_key_uses_free_fixtures_file(tmp_path):
    providers = FakeProviders()
    rt = make_runtime(tmp_path, providers, key=None)
    rt.refresh_due()
    assert rt.feeds["odds"].source == "football-data.co.uk"
    assert "/fixtures.csv" in providers.calls
    assert not any("the-odds-api" in c or c.endswith("/odds") for c in providers.calls)


def test_settings_from_env():
    s = load_settings({"DATA_SOURCE": "live", "ODDS_API_KEY": "abc", "ODDS_MIN_INTERVAL_MINUTES": "10"})
    assert s.data_source == "live" and s.odds_api_key == "abc" and s.odds_min_interval == 10
    assert load_settings({}).data_source == "sample"
