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
    assert {m["outcome"] for m in detail["markets"]} == {"home", "draw", "away"}


def test_unknown_fixture_404():
    assert client.get("/api/predictions/nope").status_code == 404


def test_value_bets_sorted_by_ev():
    bets = client.get("/api/value-bets").json()
    evs = [b["expected_value"] for b in bets]
    assert evs == sorted(evs, reverse=True)
    assert all(b["is_value"] for b in bets)


def test_ratings():
    ratings = client.get("/api/ratings").json()
    assert len(ratings) == 8
