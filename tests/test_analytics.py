"""/statistika (5-bosqich)."""

from datetime import date, timedelta

import analytics
import db

TODAY = date(2026, 10, 2)


def _user(uid, start: date, entry_days=(), seen: date | None = None):
    db.get_or_create_user(uid)
    with db.get_conn() as conn:
        conn.execute("UPDATE users SET created_at = ?, last_seen_at = ? WHERE user_id = ?",
                     (f"{start} 10:00:00", (seen or start).isoformat(), uid))
        for d in entry_days:
            conn.execute("INSERT INTO entry_counts (user_id, day, n) VALUES (?, ?, 1)",
                         (uid, (start + timedelta(days=d)).isoformat()))


def _event(uid, name, detail, day: date):
    with db.get_conn() as conn:
        conn.execute("INSERT INTO events (user_id, name, detail, day) VALUES (?, ?, ?, ?)",
                     (uid, name, detail, day.isoformat()))


def _request(uid, status, day: date, proof=True):
    with db.get_conn() as conn:
        conn.execute(
            "INSERT INTO subscription_requests (user_id, plan_code, status, created_at, proof_at) "
            "VALUES (?, '12m', ?, ?, ?)",
            (uid, status, f"{day}T12:00:00+05:00", f"{day}T13:00:00+05:00" if proof else None))


def test_active_and_retention():
    start = TODAY - timedelta(days=40)
    _user(1, start, entry_days=(0, 8, 31), seen=TODAY)          # 7 va 30 kunda faol
    _user(2, start, entry_days=(0, 8), seen=TODAY - timedelta(days=3))
    _user(3, start, entry_days=(0,), seen=start)                # birinchi kundan keyin yo'q
    _user(4, TODAY - timedelta(days=2), entry_days=(0,), seen=TODAY)  # hali erta

    data = analytics.report(TODAY)
    assert data["active"] == {"total": 4, "d1": 2, "d7": 3, "d30": 3}

    weeks = {r["week"]: r for r in data["retention"]}
    old = weeks[start - timedelta(days=start.weekday())]
    assert (old["n"], old["d7"], old["d30"]) == (3, 67, 33)
    new = weeks[(TODAY - timedelta(days=2)) - timedelta(days=(TODAY - timedelta(days=2)).weekday())]
    assert new["d7"] is None and new["d30"] is None


def test_funnel_uses_requests_for_payment_steps():
    start = TODAY - timedelta(days=10)
    _user(1, start, entry_days=(0, 8))
    _user(2, start, entry_days=(0,))
    _user(3, start)
    _event(1, "obuna_ochildi", "", TODAY)
    _event(2, "obuna_ochildi", "", TODAY)
    _request(1, "tasdiqlandi", TODAY)
    _request(2, "kutilmoqda", TODAY, proof=False)

    funnel = dict(analytics.report(TODAY)["funnel_30"])
    assert funnel == {"start": 3, "birinchi yozuv": 2, "7-kundan keyin ham faol": 1,
                      "obuna sahifasi ochildi": 2, "tarif tanlandi": 2,
                      "to'lov cheki yuborildi": 1, "obuna faollashdi": 1}


def test_paywall_attribution_goes_to_last_paywall_before_payment():
    start = TODAY - timedelta(days=10)
    _user(1, start)
    _user(2, start)
    _event(1, "paywall_korsatildi", "receipts", TODAY - timedelta(days=5))
    _event(1, "paywall_korsatildi", "app_history", TODAY - timedelta(days=2))
    _event(2, "paywall_korsatildi", "receipts", TODAY - timedelta(days=1))
    _event(2, "paywall_korsatildi", "receipts", TODAY - timedelta(days=1))
    _request(1, "tasdiqlandi", TODAY - timedelta(days=1))

    rows = {p["feature"]: p for p in analytics.report(TODAY)["paywalls"]}
    assert rows["receipts"]["times"] == 3 and rows["receipts"]["users"] == 2
    assert rows["history"]["paid"] == 1            # oxirgi paywall — Mini App tarixi
    assert rows["receipts"]["paid"] == 0


def test_owner_excluded_and_text_renders(monkeypatch):
    import config
    monkeypatch.setattr(config, "OWNER_IDS", {9})
    _user(9, TODAY)
    _user(1, TODAY)
    data = analytics.report(TODAY)
    assert data["active"]["total"] == 1
    text = analytics.report_text(data)
    assert "Voronka" in text and "Paywall" in text and "Saqlanish" in text
