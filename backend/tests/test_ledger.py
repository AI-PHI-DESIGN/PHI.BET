import pytest

from app.ledger import Ledger, LedgerError


@pytest.fixture
def ledger(tmp_path):
    lg = Ledger(tmp_path / "t.db")
    lg.add_transaction("deposit", 1000, date="2026-01-01")
    return lg


def test_balance_after_deposit(ledger):
    b = ledger.balance()
    assert b["bankroll"] == 1000 and b["available"] == 1000 and b["exposure"] == 0


def test_pending_bet_reduces_available_not_bankroll(ledger):
    ledger.place_bet("A vs B", "1X2", "home", 2.0, 100)
    b = ledger.balance()
    assert b["bankroll"] == 1000 and b["exposure"] == 100 and b["available"] == 900


def test_settlement_profit(ledger):
    won = ledger.place_bet("A vs B", "1X2", "home", 2.5, 100)
    lost = ledger.place_bet("C vs D", "1X2", "away", 3.0, 50)
    void = ledger.place_bet("E vs F", "1X2", "draw", 3.2, 20)
    assert ledger.settle_bet(won["id"], "won", "2026-02-01")["profit"] == 150
    assert ledger.settle_bet(lost["id"], "lost", "2026-02-02")["profit"] == -50
    assert ledger.settle_bet(void["id"], "void", "2026-03-01")["profit"] == 0

    s = ledger.summary()
    assert s["bankroll"] == 1100
    assert s["profit"] == 100
    assert s["staked"] == 150  # las nulas no cuentan como apostado
    assert s["yield"] == pytest.approx(100 / 150, abs=1e-4)
    assert s["hit_rate"] == 0.5
    assert (s["won"], s["lost"], s["void"]) == (1, 1, 1)

    months = {r["period"]: r["profit"] for r in ledger.pnl("month")}
    assert months == {"2026-02": 100, "2026-03": 0}


def test_max_drawdown(ledger):
    for i, (result, settled) in enumerate([("won", "01"), ("lost", "02"), ("lost", "03"), ("won", "04")]):
        bet = ledger.place_bet(f"P{i}", "1X2", "home", 2.0, 100)
        ledger.settle_bet(bet["id"], result, f"2026-05-{settled}")
    # +100, 0, -100, 0 -> caída máxima desde el pico (100) hasta -100 = 200
    assert ledger.summary()["max_drawdown"] == 200
    assert [p["cumulative"] for p in ledger.equity_curve()] == [100, 0, -100, 0]


def test_rejects_invalid_operations(ledger):
    with pytest.raises(LedgerError):
        ledger.place_bet("A vs B", "1X2", "home", 2.0, 5000)  # saldo insuficiente
    with pytest.raises(LedgerError):
        ledger.add_transaction("withdrawal", 5000)
    bet = ledger.place_bet("A vs B", "1X2", "home", 2.0, 10)
    ledger.settle_bet(bet["id"], "lost")
    with pytest.raises(LedgerError):
        ledger.settle_bet(bet["id"], "won")  # ya liquidada
    with pytest.raises(LedgerError):
        ledger.delete_bet(bet["id"])


def test_export_csv(ledger):
    bet = ledger.place_bet("A vs B", "1X2", "home", 2.0, 10, placed_at="2026-01-02")
    ledger.settle_bet(bet["id"], "won", "2026-01-03")
    lines = ledger.export_csv().strip().splitlines()
    assert lines[0].startswith("fecha,concepto")
    assert len(lines) == 4  # cabecera + depósito + apuesta + liquidación
    assert lines[-1].endswith(",10.0")
