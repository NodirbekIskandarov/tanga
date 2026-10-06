"""Obuna va tariflar (4-bosqich)."""

import importlib.util
from datetime import datetime, timedelta
from pathlib import Path

import pytest

import config
import db
import tiers


def _set_user(uid, *, trial_days=None, sub_days=None, warned=0):
    """Sinov/obuna muddatini hozirgi vaqtga nisbatan qo'yadi."""
    now = datetime.now(config.TZ)
    db.get_or_create_user(uid)
    trial = (now + timedelta(days=trial_days)).isoformat() if trial_days is not None else None
    sub = (now + timedelta(days=sub_days)).isoformat() if sub_days is not None else None
    with db.get_conn() as conn:
        conn.execute("UPDATE users SET trial_ends_at = ?, subscribed_until = ?, "
                     "warned_stage = ? WHERE user_id = ?", (trial, sub, warned, uid))


def _settings(**values):
    """Admin panel yozadigan app_settings jadvali (sinovda qo'lda)."""
    with db.get_conn() as conn:
        conn.execute("CREATE TABLE IF NOT EXISTS app_settings (key TEXT PRIMARY KEY, value TEXT)")
        for k, v in values.items():
            conn.execute("INSERT OR REPLACE INTO app_settings VALUES (?, ?)", (k, str(v)))
    config._settings_cache = None


def _requests(code, status, n):
    with db.get_conn() as conn:
        for _ in range(n):
            conn.execute("INSERT INTO subscription_requests (user_id, plan_code, status) "
                         "VALUES (1, ?, ?)", (code, status))


# ---------------------------------------------------------------- tariflar --

def test_public_plans_order_and_prices():
    plans = config.public_plans()
    assert [p["code"] for p in plans] == ["12m", "1m", "f12"]
    yearly = plans[0]
    assert yearly["price"] == 149_000 and yearly["best"]
    assert config.plan_monthly_price(yearly) == 12_400
    assert config.plan_discount_percent(yearly) == 35
    assert plans[1]["price"] == 19_000
    assert plans[2]["price"] == 99_000 and plans[2]["left"] == 100


def test_old_plans_hidden_but_known():
    assert config.purchasable_plan("3m") is None
    assert config.purchasable_plan("6m") is None
    # Eski so'rov va to'lov tarixi uchun nomi topiladi.
    assert config.plan_by_code("3m")["days"] == 90
    assert config.plan_by_code("6m")["days"] == 180


def test_prices_come_from_admin_settings():
    _settings(plan_price_1m="19 000", plan_price_12m=149000)
    assert config.plan_by_code("1m")["price"] == 19_000
    _settings(plan_price_1m=17_000)
    assert config.plan_by_code("1m")["price"] == 17_000


def test_founders_offer_counts_paid_and_closes_at_limit():
    _requests("f12", "kutilmoqda", 5)          # tanlagan, to'lamagan — hisoblanmaydi
    _requests("f12", "tasdiqlandi", 98)
    _requests("f12", "tekshiruvda", 1)
    assert config.founders_left() == 1
    assert config.purchasable_plan("f12") is not None

    _requests("f12", "tasdiqlandi", 1)
    assert config.founders_left() == 0
    assert config.purchasable_plan("f12") is None
    assert "f12" not in [p["code"] for p in config.public_plans()]


def test_bot_offers_only_codes_the_admin_panel_can_approve():
    """Admin panel so'rovni kod bo'yicha o'z ro'yxatidan topadi — bot
    taklif qiladigan har bir kod u yerda bo'lishi va muddati bir xil
    bo'lishi shart, aks holda tasdiqlash «Tarif topilmadi» bilan to'xtaydi.
    """
    path = Path(__file__).resolve().parents[2] / "tanga-admin" / "plans.py"
    if not path.exists():
        pytest.skip("tanga-admin yonida yo'q")
    spec = importlib.util.spec_from_file_location("admin_plans", path)
    admin = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(admin)
    admin_plans = {p["code"]: p for p in admin.DEFAULT_PLANS}
    for p in config.SUBSCRIPTION_PLANS:
        assert p["code"] in admin_plans, p["code"]
        assert admin_plans[p["code"]]["days"] == p["days"], p["code"]
        assert admin_plans[p["code"]]["price"] == p["price"], p["code"]


# ----------------------------------------------------------- daraja/kirish --

def test_trial_is_pro_and_expired_becomes_free_not_blocked(user_id):
    access = db.access_status(user_id)
    assert access["status"] == "trial" and access["tier"] == "pro"

    _set_user(user_id, trial_days=-10)
    access = db.access_status(user_id)
    assert access["ok"] is True
    assert access["status"] == "free" and access["tier"] == "free"

    _set_user(user_id, trial_days=-10, sub_days=20)
    assert db.access_status(user_id)["tier"] == "pro"

    db.set_blocked(user_id, True)
    assert db.access_status(user_id)["ok"] is False


def test_owner_simulation_mode(monkeypatch):
    monkeypatch.setattr(config, "OWNER_IDS", {7})
    assert db.access_status(7)["status"] == "owner"
    assert db.is_privileged(7)

    db.set_sim_free(7, True)
    access = db.access_status(7)
    assert access["status"] == "free" and access["tier"] == "free"
    assert not db.is_privileged(7)

    db.set_sim_free(7, False)
    assert db.access_status(7)["status"] == "owner"


def test_free_receipts_three_per_month(user_id):
    _set_user(user_id, trial_days=-1)
    access = db.access_status(user_id)
    for _ in range(3):
        assert tiers.check(user_id, access, "chek") is None
        db.usage_begin(user_id, "chek")
    verdict = tiers.check(user_id, access, "chek")
    assert verdict["type"] == "paywall" and verdict["feature"] == "receipts"
    assert verdict["resets"] == "next_month"
    assert tiers.receipts_left(user_id, access) == 0


def test_pro_receipts_fair_use_per_day(user_id):
    # Obunachi: sinovda kunlik chegaradan oldin sinovning jami chegarasi
    # ishlaydi (test_launch_critical.py).
    _set_user(user_id, trial_days=-1, sub_days=30)
    access = db.access_status(user_id)
    for _ in range(config.LIMIT_RECEIPT_PER_DAY):
        db.usage_begin(user_id, "chek")
    verdict = tiers.check(user_id, access, "chek")
    assert verdict["type"] == "limit" and verdict["resets"] == "tomorrow"


def test_text_entries_have_same_fair_limit_for_everyone(user_id):
    _set_user(user_id, trial_days=-1)
    access = db.access_status(user_id)
    for _ in range(config.LIMIT_TEXT_PER_DAY - 1):
        db.usage_begin(user_id, "matn")
    assert tiers.check(user_id, access, "matn") is None
    db.usage_begin(user_id, "matn")
    assert tiers.check(user_id, access, "matn")["type"] == "limit"


def test_free_questions_three_per_day(user_id):
    _set_user(user_id, trial_days=-1)
    access = db.access_status(user_id)
    for _ in range(3):
        db.usage_begin(user_id, "savol")
    assert tiers.check(user_id, access, "savol")["type"] == "paywall"


def test_pro_only_features():
    free = {"tier": "free"}
    pro = {"tier": "pro"}
    for feature in ("history", "budget", "csv"):
        assert not tiers.allows(free, feature)
        assert tiers.allows(pro, feature)
    assert tiers.allows(free, "debts")


def test_paywall_event_dedupes_per_day(user_id):
    assert not db.event_today(user_id, "paywall_korsatildi", "csv")
    db.log_event(user_id, "paywall_korsatildi", "csv")
    assert db.event_today(user_id, "paywall_korsatildi", "csv")
    assert not db.event_today(user_id, "paywall_korsatildi", "budget")


# --------------------------------------------------------- teskari sinov --

def test_trial_day5_then_ended_notices(user_id):
    _set_user(user_id, trial_days=1.5)
    assert db.trial_notices() == [{"user_id": user_id, "kind": "day5", "days_left": 2}]

    db.mark_warned(user_id, db.TRIAL_STAGE_DAY5)
    assert db.trial_notices() == []

    _set_user(user_id, trial_days=-0.5, warned=db.TRIAL_STAGE_DAY5)
    assert db.trial_notices()[0]["kind"] == "ended"

    db.mark_warned(user_id, db.TRIAL_STAGE_ENDED)
    assert db.trial_notices() == []


def test_long_expired_users_get_no_automatic_message(user_id):
    """Yangi tizimgacha sinovi tugaganlar jimgina Bepul darajaga o'tadi."""
    _set_user(user_id, trial_days=-30, warned=0)
    assert db.trial_notices() == []
    _set_user(user_id, trial_days=-1, warned=0)      # 5-kun xabarini olmagan
    assert db.trial_notices() == []
    assert db.users_expiring() == []


def test_trial_ended_text_is_personal(user_id):
    import bot
    month_start = tiers.month_start()
    db.add_transaction(user_id, "chiqim", 10_000, "oziq-ovqat", "non",
                       occurred_on=(month_start - timedelta(days=3)).isoformat())
    db.set_savings_goal(user_id, 300_000_000, "Uy")
    text = bot.trial_ended_text(user_id, "uz")
    assert "dan oldingi tahlilingiz" in text
    assert "«Uy» maqsadingiz bashorati" in text
    assert "oyiga 3 ta" in text


def test_plans_page_leads_with_benefit():
    import bot
    text = bot.plans_text(lang="uz")
    assert text.index("Pulingiz qayerga") < text.index("149 000")
    assert "⭐" in text and "12 400" in text and "35% tejash" in text
    assert "qolgan joylar: 100/100" in text
    assert "3 oylik" not in text
