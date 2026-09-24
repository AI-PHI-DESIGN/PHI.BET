from fastapi.testclient import TestClient

from app.main import app

client = TestClient(app)


def test_health():
    r = client.get("/api/health")
    assert r.status_code == 200
    assert r.json()["status"] == "ok"


def test_predictions_and_detail():
    preds = client.get("/api/predictions").json()
    assert preds
    first = preds[0]
    detail = client.get(f"/api/predictions/{first['id']}").json()
    assert detail["id"] == first["id"]
    assert abs(sum(detail["probs"].values()) - 1) < 1e-3
    assert detail["pick"] in detail["probs"]
    assert set(detail["markets"]) >= {"1", "X", "2", "1X", "over25", "btts_yes"}


def test_unknown_fixture_404():
    assert client.get("/api/predictions/nope").status_code == 404


def test_performance():
    perf = client.get("/api/performance?recent=5").json()
    assert perf["evaluated"] > 0
    assert len(perf["recent"]) == 5
    assert perf["recent"][0]["date"] >= perf["recent"][-1]["date"]
    assert client.get("/api/performance?recent=0").json()["recent"] == []
    assert len(client.get("/api/performance?recent=500").json()["recent"]) == perf["evaluated"]


def test_no_money_endpoints():
    # La app muestra cuotas como información, pero no gestiona dinero ni registra apuestas.
    for path in ("/api/value-bets", "/api/accounting/summary"):
        assert client.get(path).status_code == 404


def test_picks():
    r = client.get("/api/picks?min_prob=0.5&risk=high&limit=5").json()
    assert r["date"] == r["dates"][0]
    assert r["historical"]["count"] > 0
    assert 0 < len(r["picks"]) <= 5
    odds = [p["odds"] for p in r["picks"]]
    assert odds == sorted(odds, reverse=True)
    assert all(p["prob"] >= 0.5 for p in r["picks"])


def test_picks_validation():
    assert client.get("/api/picks?risk=extremo").status_code == 422
    assert client.get("/api/picks?min_prob=1.5").status_code == 422
    assert client.get("/api/picks?combine=4").status_code == 422
    assert client.get("/api/picks?date=1999-01-01").status_code == 404


def test_performance_by_confidence():
    conf = client.get("/api/performance?recent=0").json()["by_confidence"]
    counts = [c["count"] for c in conf]
    assert counts == sorted(counts, reverse=True)  # umbral más alto, menos casos


def test_ratings():
    assert len(client.get("/api/ratings").json()) == 8


def test_leagues_endpoint_and_league_param():
    [league] = client.get("/api/leagues").json()
    assert league["key"] == "ejemplo" and league["ready"] and league["fixtures"] == 8
    assert client.get("/api/predictions", params={"league": "ejemplo"}).status_code == 200
    assert client.get("/api/predictions", params={"league": "inventada"}).status_code == 404
    status = client.get("/api/status").json()
    assert status["default_league"] == "ejemplo" and status["leagues"][0]["name"] == "Liga de ejemplo"
