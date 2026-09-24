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


def test_accounting_flow():
    assert client.post("/api/accounting/transactions", json={"type": "deposit", "amount": 500}).status_code == 201
    bet = client.post(
        "/api/accounting/bets",
        json={"event": "X vs Y", "selection": "home", "odds": 2.0, "stake": 50, "fixture_id": "f1"},
    ).json()
    assert client.get("/api/accounting/summary").json()["exposure"] == 50

    settled = client.post(f"/api/accounting/bets/{bet['id']}/settle", json={"result": "won"}).json()
    assert settled["profit"] == 50
    summary = client.get("/api/accounting/summary").json()
    assert summary["bankroll"] == 550 and summary["profit"] == 50

    assert client.get("/api/accounting/pnl?group=market").json()[0]["period"] == "1X2"
    assert len(client.get("/api/accounting/equity").json()) == 1
    csv_resp = client.get("/api/accounting/export.csv")
    assert csv_resp.headers["content-type"].startswith("text/csv")


def test_accounting_errors():
    assert client.post("/api/accounting/bets", json={"event": "a", "selection": "b", "odds": 1.0, "stake": 1}).status_code == 422
    assert client.post("/api/accounting/bets", json={"event": "a", "selection": "b", "odds": 2, "stake": 10**9}).status_code == 400
    assert client.post("/api/accounting/bets/9999/settle", json={"result": "won"}).status_code == 404
