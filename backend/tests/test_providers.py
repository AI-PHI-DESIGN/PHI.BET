from datetime import date, datetime, timezone

import httpx
import pytest

from app import teams
from app.providers import football_data, odds_api
from app.runtime import merge_matches, minutes_until_month_end, paced_interval
from app.data import Match

RESULTS_CSV = """﻿Div,Date,Time,HomeTeam,AwayTeam,FTHG,FTAG,FTR,B365H,MaxH,AvgH
SP1,15/08/2025,18:30,Girona,Vallecano,1,3,A,2.1,2.2,2.1
SP1,16/08/2025,20:00,Ath Madrid,Espanol,2,1,H,1.5,1.55,1.5
SP1,17/08/25,21:00,Sociedad,Betis,0,0,D,2.4,2.5,2.4
SP1,20/08/2025,21:00,Barcelona,Real Madrid,,,,,,
,,,,,,,,,,
"""

FIXTURES_CSV = """Div,Date,Time,HomeTeam,AwayTeam,MaxH,MaxD,MaxA,AvgH,AvgD,AvgA,Max>2.5,Max<2.5,Avg>2.5,Avg<2.5
E0,26/09/2026,15:00,Arsenal,Chelsea,2.0,3.5,4.0,1.9,3.4,3.8,1.8,2.1,1.75,2.05
SP1,26/09/2026,20:00,Ath Bilbao,Celta,1.9,3.6,4.5,1.85,3.45,4.2,2.2,1.75,2.1,1.7
SP1,20/09/2026,20:00,Getafe,Sevilla,2.5,3.0,3.1,2.4,2.9,3.0,,,,
"""

ODDS_JSON = [
    {
        "id": "ev1",
        "sport_key": "soccer_spain_la_liga",
        "commence_time": "2026-09-26T19:00:00Z",
        "home_team": "Athletic Bilbao",
        "away_team": "Celta Vigo",
        "bookmakers": [
            {"key": "pinnacle", "title": "Pinnacle", "markets": [
                {"key": "h2h", "outcomes": [{"name": "Athletic Bilbao", "price": 1.95}, {"name": "Celta Vigo", "price": 4.3}, {"name": "Draw", "price": 3.5}]},
                {"key": "totals", "outcomes": [{"name": "Over", "price": 2.1, "point": 2.5}, {"name": "Under", "price": 1.8, "point": 2.5},
                                               {"name": "Over", "price": 1.4, "point": 1.5}]},
            ]},
            {"key": "bet365", "title": "Bet365", "markets": [
                {"key": "h2h", "outcomes": [{"name": "Athletic Bilbao", "price": 1.85}, {"name": "Celta Vigo", "price": 4.5}, {"name": "Draw", "price": 3.4}]},
            ]},
        ],
    },
    {"id": "ev2", "commence_time": "2026-09-27T22:30:00Z", "home_team": "Real Madrid", "away_team": "Barcelona", "bookmakers": []},
]

SCORES_JSON = [
    {"id": "s1", "commence_time": "2026-09-20T19:00:00Z", "completed": True, "home_team": "Getafe", "away_team": "Sevilla",
     "scores": [{"name": "Getafe", "score": "2"}, {"name": "Sevilla", "score": "1"}]},
    {"id": "s2", "commence_time": "2026-09-26T19:00:00Z", "completed": False, "home_team": "Athletic Bilbao", "away_team": "Celta Vigo", "scores": None},
]


def test_team_names_are_unified_across_providers():
    assert teams.canonical("Ath Madrid") == teams.canonical("Atlético Madrid") == "Atlético de Madrid"
    assert teams.canonical("Sociedad") == teams.canonical("Real Sociedad")
    assert teams.canonical("Vallecano") == "Rayo Vallecano"
    assert teams.canonical("Celta Vigo") == teams.canonical("Celta") == "Celta de Vigo"
    assert teams.canonical("Equipo Nuevo CF") == "Equipo Nuevo CF"  # desconocido: se deja igual


def test_season_codes():
    assert football_data.season_start(date(2026, 9, 24)) == 2026
    assert football_data.season_start(date(2027, 3, 1)) == 2026
    assert football_data.season_code(2026) == "2627"
    assert football_data.season_code(1999) == "9900"


def test_parse_results():
    matches = football_data.parse_results(RESULTS_CSV)
    assert len(matches) == 3  # sin la fila vacía ni el partido sin jugar
    assert matches[1] == Match("2025-08-16", "Atlético de Madrid", "Espanyol", 2, 1)
    assert matches[2].date == "2025-08-17"  # año con dos cifras


def test_parse_fixtures_filters_league_and_past_and_converts_time():
    fx = football_data.parse_fixtures(FIXTURES_CSV, today=date(2026, 9, 24))
    assert len(fx) == 1
    f = fx[0]
    assert (f.home_team, f.away_team) == ("Athletic Club", "Celta de Vigo")
    assert f.odds == {"1": 1.9, "X": 3.6, "2": 4.5, "over25": 2.2, "under25": 1.75}
    assert f.odds_avg["1"] == 1.85
    assert f.kickoff == "2026-09-26T21:00+02:00"  # 20:00 en Londres = 21:00 en Madrid


def test_parse_odds_best_and_average():
    fx = odds_api.parse_odds(ODDS_JSON)
    assert len(fx) == 1  # el evento sin casas se descarta
    f = fx[0]
    assert (f.home_team, f.away_team) == ("Athletic Club", "Celta de Vigo")
    assert f.date == "2026-09-26" and f.kickoff == "2026-09-26T21:00+02:00"
    assert f.odds == {"1": 1.95, "2": 4.5, "X": 3.5, "over25": 2.1, "under25": 1.8}
    assert f.bookmakers["1"] == "Pinnacle" and f.bookmakers["2"] == "Bet365"
    assert f.odds_avg["1"] == pytest.approx(1.9)


def test_parse_scores_only_completed():
    assert odds_api.parse_scores(SCORES_JSON) == [Match("2026-09-20", "Getafe", "Sevilla", 2, 1)]


def test_merge_matches_prefers_latest_source():
    a = [Match("2026-09-20", "Getafe", "Sevilla", 0, 0), Match("2026-09-13", "A", "B", 1, 0)]
    b = [Match("2026-09-20", "Getafe", "Sevilla", 2, 1)]
    merged = merge_matches(a, b)
    assert [m.date for m in merged] == ["2026-09-13", "2026-09-20"]
    assert merged[1].home_goals == 2


def test_paced_interval_spreads_credits_over_month():
    now = datetime(2026, 9, 1, tzinfo=timezone.utc)  # 30 días = 43 200 min hasta el reinicio
    assert minutes_until_month_end(now) == pytest.approx(43200)
    # Plan gratuito: 500 créditos, 2 por consulta, resultados cada 12 h (120 créditos reservados)
    assert paced_interval(500, 2, now, 5, 720) == pytest.approx(43200 * 2 / 380)
    # Plan grande: se respeta el mínimo
    assert paced_interval(20000, 2, now, 5, 720) == 5
    # Sin créditos: esperar al mes siguiente
    assert paced_interval(1, 2, now, 5) == pytest.approx(43200)
    # Sin datos de cuota todavía
    assert paced_interval(None, None, now, 5) == 60


def test_odds_client_reads_quota_headers():
    def handler(request: httpx.Request) -> httpx.Response:
        assert request.url.params["apiKey"] == "k" and request.url.params["markets"] == "h2h,totals"
        return httpx.Response(200, json=ODDS_JSON, headers={"x-requests-remaining": "480", "x-requests-used": "20", "x-requests-last": "2"})

    client = odds_api.OddsApiClient(httpx.Client(transport=httpx.MockTransport(handler)), "k")
    assert len(client.fetch_odds()) == 1
    assert (client.quota.remaining, client.quota.used, client.quota.last_cost) == (480, 20, 2)


def test_odds_client_errors_never_leak_the_key():
    client = odds_api.OddsApiClient(httpx.Client(transport=httpx.MockTransport(lambda r: httpx.Response(401))), "SECRETO")
    with pytest.raises(httpx.HTTPStatusError) as err:
        client.fetch_odds()
    assert "SECRETO" not in str(err.value)
