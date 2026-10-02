"""Mini App API: Bepul daraja chegarasi va rozilik."""

import hashlib
import hmac
import json
import time
from datetime import datetime, timedelta
from urllib.parse import urlencode

import pytest
from fastapi.testclient import TestClient

import config
import db
import tiers


def _init_data(uid: int) -> str:
    """Telegram imzolagan initData (sinov tokeni bilan)."""
    pairs = {"auth_date": str(int(time.time())),
             "user": json.dumps({"id": uid, "first_name": "Test"})}
    check = "\n".join(f"{k}={v}" for k, v in sorted(pairs.items()))
    secret = hmac.new(b"WebAppData", config.TELEGRAM_TOKEN.encode(), hashlib.sha256).digest()
    pairs["hash"] = hmac.new(secret, check.encode(), hashlib.sha256).hexdigest()
    return urlencode(pairs)


@pytest.fixture
def client(monkeypatch):
    import webapp
    monkeypatch.setattr(webapp, "_BOT_USERNAME", "tanga_bot")
    webapp._rate.clear()
    return TestClient(webapp.app)


def _user(uid, *, consent=True, free=False):
    db.get_or_create_user(uid, "Test")
    if consent:
        db.set_consent(uid, config.CONSENT_VERSION)
    if free:
        past = (datetime.now(config.TZ) - timedelta(days=3)).isoformat()
        with db.get_conn() as conn:
            conn.execute("UPDATE users SET trial_ends_at = ? WHERE user_id = ?", (past, uid))
    return {"X-Telegram-Init-Data": _init_data(uid)}


def test_no_consent_no_access(client):
    h = _user(50, consent=False)
    r = client.get("/api/me", headers=h)
    assert r.status_code == 403
    assert "rozilik" in r.json()["detail"]


def test_free_user_gets_current_month_only(client):
    h = _user(51, free=True)
    me = client.get("/api/me", headers=h).json()
    assert me["tier"] == "free"
    assert me["history_from"] == tiers.month_start().isoformat()
    assert me["bot_username"] == "tanga_bot"

    assert client.get("/api/summary?period=oy", headers=h).status_code == 200

    r = client.get("/api/summary?period=yil", headers=h)
    assert r.status_code == 402
    assert r.json()["detail"]["paywall"] == "history"
    assert "<b>" not in r.json()["detail"]["message"]

    prev = (tiers.month_start() - timedelta(days=20)).isoformat()
    assert client.get(f"/api/summary?period=oy&ref={prev}", headers=h).status_code == 402


def test_free_user_transaction_list_starts_this_month(client):
    h = _user(52, free=True)
    old = (tiers.month_start() - timedelta(days=40)).isoformat()
    db.add_transaction(52, "chiqim", 1_000, "oziq-ovqat", "eski", occurred_on=old)
    db.add_transaction(52, "chiqim", 2_000, "oziq-ovqat", "yangi",
                       occurred_on=tiers.today().isoformat())
    items = client.get("/api/transactions?start=2000-01-01", headers=h).json()["items"]
    assert [i["note"] for i in items] == ["yangi"]


def test_free_user_csv_is_pro(client):
    h = _user(53, free=True)
    r = client.post("/api/export/token", headers=h)
    assert r.status_code == 402 and r.json()["detail"]["paywall"] == "csv"


def test_pro_user_sees_everything(client):
    h = _user(54)
    assert client.get("/api/summary?period=yil", headers=h).status_code == 200
    assert client.post("/api/export/token", headers=h).status_code == 200


def test_csv_export_has_receipt_id(client):
    h = _user(55)
    db.add_receipt(55, "rc1", shop="Korzinka", occurred_on=tiers.today().isoformat(),
                   currency="som", printed_total=None, discount=None,
                   items=[{"kind": "chiqim", "amount": 5_000, "category": "oziq-ovqat",
                           "note": "non"}])
    token = client.post("/api/export/token", headers=h).json()["token"]
    body = client.get(f"/api/export.csv?token={token}").content.decode("utf-8-sig")
    assert body.splitlines()[1].endswith(",rc1,Korzinka")


def test_debt_repayment_switch_from_expense(client):
    h = _user(56)
    tx = db.add_transaction(56, "chiqim", 1_000_000, "boshqa chiqim", "qarz to'lovi")
    r = client.patch(f"/api/transactions/{tx}", headers=h, json={"kind": "qarz_qaytardim"})
    assert r.status_code == 200 and r.json()["kind"] == "qarz_qaytardim"
    r = client.patch(f"/api/transactions/{tx}", headers=h, json={"kind": "jamgarma"})
    assert r.status_code == 400


def test_receipt_is_one_row_in_mini_app_and_deletes_whole(client):
    h = _user(57)
    day = tiers.today().isoformat()
    db.add_receipt(57, "rc2", shop="Makro", occurred_on=day, currency="som",
                   printed_total=None, discount=None,
                   items=[{"kind": "chiqim", "amount": a, "category": "oziq-ovqat",
                           "note": f"m{a}"} for a in (1_000, 2_000, 3_000)])
    db.add_transaction(57, "chiqim", 25_000, "transport", "taksi", occurred_on=day)

    data = client.get("/api/transactions?group_receipts=1", headers=h).json()
    assert data["total_count"] == 2
    receipt = next(i for i in data["items"] if i["receipt_id"])
    assert (receipt["items_count"], receipt["amount"], receipt["shop"]) == (3, 6_000, "Makro")

    # Guruhlanmagan so'rov (kategoriya filtri, chek tafsiloti) — mahsulotlar.
    assert client.get("/api/transactions", headers=h).json()["total_count"] == 4

    assert client.delete("/api/receipts/rc2", headers=h).json()["deleted"] == 3
    assert db.get_receipt(57, "rc2") is None
    assert client.delete("/api/receipts/rc2", headers=h).status_code == 404
