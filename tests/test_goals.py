"""PRO imkoniyatlari (3-bosqich): maqsadlar, «avval o'zingizga to'lang»,
qarz eslatmalari."""

import asyncio
from datetime import date, datetime, timedelta

import pytest

import ai
import config
import db
import goals
import tiers
from tests import fake_ai


def _parse_amount(text):
    import bot
    return bot._parse_amount_uz(text)


def _save(uid, amount, days_ago=0, goal_id=None, kind="jamgarma"):
    day = (tiers.today() - timedelta(days=days_ago)).isoformat()
    return db.add_transaction(uid, kind, amount, "jamg'arma", "", occurred_on=day,
                              goal_id=goal_id)


def _free(uid):
    past = (datetime.now(config.TZ) - timedelta(days=3)).isoformat()
    with db.get_conn() as conn:
        conn.execute("UPDATE users SET trial_ends_at = ? WHERE user_id = ?", (past, uid))


# ------------------------------------------------------------ matn tahlili --

@pytest.mark.parametrize("text,name,amount,deadline", [
    ("Uy uchun boshlang'ich to'lov — 300 mln, 2028-yil mart",
     "Uy uchun boshlang'ich to'lov", 300_000_000, date(2028, 3, 31)),
    ("Mashina 120 mln 2027-12", "Mashina", 120_000_000, date(2027, 12, 31)),
    ("300 mln uy uchun", "uy uchun", 300_000_000, None),
    ("Ta'til 15 mln 01.06.2027", "Ta'til", 15_000_000, date(2027, 6, 1)),
    ("Квартира 300 млн март 2028", "Квартира", 300_000_000, date(2028, 3, 31)),
])
def test_parse_goal_text(text, name, amount, deadline):
    parsed = goals.parse_goal_text(text, _parse_amount)
    assert parsed == {"name": name, "amount": amount, "deadline": deadline}


def test_parse_goal_without_amount_fails():
    assert goals.parse_goal_text("Uy olish", _parse_amount) is None


# ------------------------------------------------------- maqsad va progress --

def test_single_goal_counts_all_savings_like_before(user_id):
    _save(user_id, 1_000_000)                       # maqsadsiz eski jamg'arma
    gid = goals.create(user_id, "Uy", 10_000_000, None)
    _save(user_id, 2_000_000, goal_id=gid)
    g = goals.primary(user_id)
    assert (g["id"], g["primary"], g["saved"], g["percent"]) == (gid, True, 3_000_000, 30)


def test_second_goal_has_its_own_progress(user_id):
    uy = goals.create(user_id, "Uy", 10_000_000, None)
    car = goals.create(user_id, "Mashina", 5_000_000, None)
    _save(user_id, 1_000_000)                       # bog'lanmagan — asosiyga
    _save(user_id, 500_000, goal_id=car)
    by_id = {g["id"]: g for g in goals.list_goals(user_id)}
    assert by_id[uy]["saved"] == 1_000_000 and by_id[uy]["primary"]
    assert by_id[car]["saved"] == 500_000 and not by_id[car]["primary"]

    goals.set_primary(user_id, car)
    assert goals.list_goals(user_id)[0]["id"] == car


def test_archiving_unlinks_money_but_keeps_it(user_id):
    goals.create(user_id, "Uy", 10_000_000, None)
    car = goals.create(user_id, "Mashina", 5_000_000, None)
    _save(user_id, 500_000, goal_id=car)
    goals.archive(user_id, car)
    assert [g["name"] for g in goals.list_goals(user_id)] == ["Uy"]
    assert goals.primary(user_id)["saved"] == 500_000
    assert db.savings_balance(user_id) == 500_000


def test_legacy_single_goal_is_copied_once(user_id):
    db.set_savings_goal(user_id, 20_000_000, "Zaxira fond")
    _save(user_id, 4_000_000)
    first = goals.list_goals(user_id)
    assert [(g["name"], g["amount"], g["percent"]) for g in first] == [
        ("Zaxira fond", 20_000_000, 20)]
    # Asl qiymat o'zgarmagan (qaytarish oson) va ikkinchi marta nusxa yo'q.
    assert db.savings_profile(user_id)["goal"] == 20_000_000
    goals.archive(user_id, first[0]["id"])
    assert goals.list_goals(user_id) == []


def test_match_goal_by_name_or_primary(user_id):
    uy = goals.create(user_id, "Uy uchun boshlang'ich to'lov", 300_000_000, None)
    car = goals.create(user_id, "Mashina", 120_000_000, None)
    assert goals.match(user_id, "mashinaga") == car
    assert goals.match(user_id, "uy") == uy
    assert goals.match(user_id, None) == uy
    assert goals.match(9999, "uy") is None


# ---------------------------------------------------------------- bashorat --

def test_forecast_from_last_three_months(user_id, monkeypatch):
    gid = goals.create(user_id, "Uy", 10_000_000, None)
    for days_ago in (90, 60, 30):                    # oyiga ~1 mln
        _save(user_id, 1_000_000, days_ago=days_ago, goal_id=gid)
    g = goals.get(user_id, gid)
    fc = goals.forecast(user_id, g)
    assert 900_000 < fc["pace"] < 1_100_000
    # 7 mln qoldi, oyiga ~1 mln -> ~7 oy.
    months = (fc["eta"] - tiers.today()).days / goals.MONTH_DAYS
    assert 6 < months < 8


def test_forecast_needs_two_weeks_of_history(user_id):
    gid = goals.create(user_id, "Uy", 10_000_000, None)
    _save(user_id, 5_000_000, days_ago=3, goal_id=gid)
    assert goals.forecast(user_id, goals.get(user_id, gid))["pace"] is None


def test_deadline_gives_required_monthly(user_id):
    deadline = tiers.today() + timedelta(days=round(goals.MONTH_DAYS * 10))
    gid = goals.create(user_id, "Ta'til", 10_000_000, deadline)
    need = goals.forecast(user_id, goals.get(user_id, gid))["need_monthly"]
    assert 990_000 < need < 1_010_000


def test_goal_block_shows_forecast_only_for_pro(user_id):
    import bot
    gid = goals.create(user_id, "Uy", 10_000_000, None)
    for days_ago in (60, 30):
        _save(user_id, 1_000_000, days_ago=days_ago, goal_id=gid)
    pro_text = bot._goal_block(user_id, "uz")
    assert "erishasiz" in pro_text
    _free(user_id)
    free_text = bot._goal_block(user_id, "uz")
    assert "erishasiz" not in free_text and "PRO" in free_text


def test_free_tier_one_goal(user_id):
    _free(user_id)
    access = db.access_status(user_id)
    assert not tiers.allows(access, "goals_many")
    assert not tiers.allows(access, "goals_forecast")


# ------------------------------------------------- matndan jamg'arma maqsadga --

def test_ai_goal_and_due_fields_are_normalized(monkeypatch):
    today = date(2026, 10, 2)
    fake_ai.install(monkeypatch, [{"niyat": "yozuv", "yozuvlar": [
        {**fake_ai.record("jamgarma", 3_000_000, "jamg'arma", "", sana="2026-10-02"),
         "maqsad": "mashina"},
        {**fake_ai.record("qarz_berdim", 200_000, "qarz", "qarz", "Akmal", "2026-10-02"),
         "muddat": "2026-10-15"},
        {**fake_ai.record("qarz_berdim", 100_000, "qarz", "qarz", "Ali", "2026-10-02"),
         "muddat": "2026-09-01"},                          # o'tgan sana
        {**fake_ai.record("chiqim", 5_000, "oziq-ovqat", "non"), "maqsad": "x",
         "muddat": "2026-12-01"},                          # boshqa tur — e'tiborsiz
    ]}])
    rows = asyncio.run(ai.parse_message("...", today=today))["yozuvlar"]
    assert [(r["maqsad"], r["muddat"]) for r in rows] == [
        ("mashina", None), (None, "2026-10-15"), (None, None), (None, None)]


# ------------------------------------------------------------- qarz muddati --

def test_due_reminders_only_for_open_debts(user_id):
    today_ = tiers.today()
    tomorrow = today_ + timedelta(days=1)
    a = db.add_transaction(user_id, "qarz_berdim", 200_000, "qarz", "", "Akmal",
                           occurred_on=(today_ - timedelta(days=10)).isoformat(),
                           due_on=tomorrow.isoformat())
    b = db.add_transaction(user_id, "qarz_oldim", 500_000, "qarz", "", "Sardor",
                           occurred_on=(today_ - timedelta(days=10)).isoformat(),
                           due_on=today_.isoformat())
    # Akmal qisman qaytardi — eslatmada qoldiq.
    db.add_transaction(user_id, "qarz_qaytdi", 50_000, "qarz", "", "Akmal",
                       occurred_on=(today_ - timedelta(days=1)).isoformat())
    due = {d["id"]: d for d in db.debts_due((today_, tomorrow))}
    assert set(due) == {a, b}
    assert due[a]["remaining"] == 150_000

    import bot
    text = bot.debt_reminder_text(due[a], "uz", "when_tomorrow")
    assert "Akmal" in text and "150 000" in text and "ertaga" in text
    text = bot.debt_reminder_text(due[b], "uz", "when_today")
    assert "qarzingizni" in text and "bugun" in text

    # To'liq qaytarilsa — eslatma yo'q.
    db.add_transaction(user_id, "qarz_qaytardim", 500_000, "qarz", "", "Sardor",
                       occurred_on=today_.isoformat())
    assert {d["id"] for d in db.debts_due((today_, tomorrow))} == {a}


def test_set_due_only_on_open_debt_kinds(user_id):
    debt = db.add_transaction(user_id, "qarz_berdim", 1_000, "qarz", "", "A")
    spend = db.add_transaction(user_id, "chiqim", 1_000, "oziq-ovqat", "non")
    day = tiers.today() + timedelta(days=7)
    assert db.set_due(user_id, debt, day)
    assert not db.set_due(user_id, spend, day)
    assert db.get_transaction(user_id, debt)["due_on"] == day.isoformat()


def test_debt_entry_has_due_button():
    import bot
    kb = bot.entry_keyboard([5], "qarz_berdim")
    datas = [b.callback_data for row in kb.inline_keyboard for b in row]
    assert "due:5" in datas
    kb = bot.entry_keyboard([5], "chiqim")
    assert "due:5" not in [b.callback_data for row in kb.inline_keyboard for b in row]


# ------------------------------------------------- avval o'zingizga to'lang --

def test_savings_rate_is_pro_feature(user_id):
    assert tiers.allows(db.access_status(user_id), "savings_auto")
    _free(user_id)
    assert not tiers.allows(db.access_status(user_id), "savings_auto")


def test_rate_keyboard_marks_current():
    import bot
    kb = bot._rate_keyboard(0.15)
    labels = [b.text for b in kb.inline_keyboard[0]]
    assert labels == ["10%", "✅ 15%", "20%", "30%"]
