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
    assert "odds" not in detail


def test_unknown_fixture_404():
    assert client.get("/api/predictions/nope").status_code == 404


def test_performance():
    perf = client.get("/api/performance?recent=5").json()
    assert perf["evaluated"] > 0
    assert len(perf["recent"]) == 5
    assert perf["recent"][0]["date"] >= perf["recent"][-1]["date"]
    assert client.get("/api/performance?recent=0").json()["recent"] == []
    assert len(client.get("/api/performance?recent=500").json()["recent"]) == perf["evaluated"]


def test_no_betting_endpoints():
    for path in ("/api/value-bets", "/api/accounting/summary"):
        assert client.get(path).status_code == 404


def test_ratings():
    assert len(client.get("/api/ratings").json()) == 8
