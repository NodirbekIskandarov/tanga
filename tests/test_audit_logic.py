"""Mantiqiy audit (2026-10-08) tuzatishlari — regressiya sinovlari.

Har biri avval xatoni isbotlagan sinovdan olingan; endi to'g'ri
xatti-harakatni talab qiladi.
"""

import asyncio
import time
from datetime import date, datetime, timedelta
from types import SimpleNamespace

import ai
import config
import db
import goals
import reports
import tiers


def _expire_trial(uid):
    past = (datetime.now(config.TZ) - timedelta(days=3)).isoformat()
    with db.get_conn() as conn:
        conn.execute("UPDATE users SET trial_ends_at = ? WHERE user_id = ?", (past, uid))


# --------------------------------------------------------------------------- #
# 1. Maqsad bashorati juda sekin sur'atda yiqilmaydi
# --------------------------------------------------------------------------- #

def _slow_goal(user_id):
    g_id = goals.create(user_id, "Uy", 300_000_000, None)
    day = reports.today()
    db.add_transaction(user_id, "jamgarma", 100_000, "jamg'arma", "x", goal_id=g_id,
                       occurred_on=(day - timedelta(days=40)).isoformat())
    db.add_transaction(user_id, "jamgarma_yechdim", 99_990, "jamg'arma", "x",
                       goal_id=g_id, occurred_on=(day - timedelta(days=5)).isoformat())
    return goals.get(user_id, g_id)


def test_tiny_savings_pace_gives_no_eta_instead_of_crash(user_id):
    goal = _slow_goal(user_id)
    fc = goals.forecast(user_id, goal)            # ilgari: OverflowError
    assert fc["pace"] > 0 and fc["eta"] is None


def test_goal_block_and_mini_app_survive_tiny_pace(user_id):
    import bot
    import i18n
    goal = _slow_goal(user_id)
    text = bot._goal_block(user_id, "uz", goal, with_forecast=True)
    assert i18n.t("uz", "goal_slow") in text


# --------------------------------------------------------------------------- #
# 2. Hisobni o'chirib qaytgan odam yangi sinov va taklif bonusini olmaydi
# --------------------------------------------------------------------------- #

def test_erase_and_return_starts_on_free_tier(user_id):
    _expire_trial(user_id)
    for _ in range(config.FREE_RECEIPTS_PER_MONTH):
        db.usage_begin(user_id, "chek")
    db.erase_user(user_id)

    access = db.access_status(user_id, "Test")     # qayta /start
    assert access["status"] == "free" and access["tier"] == "free"


def test_new_user_still_gets_trial():
    assert db.access_status(4242, "Yangi")["status"] == "trial"


def test_erase_marker_is_anonymous(user_id):
    db.erase_user(user_id)
    with db.get_conn() as conn:
        rows = [dict(r) for r in conn.execute("SELECT * FROM erased_accounts")]
        assert not conn.execute("SELECT 1 FROM users WHERE user_id = ?",
                                (user_id,)).fetchone()
    assert len(rows) == 1
    assert str(user_id) not in str(rows[0])
    assert len(rows[0]["erased_on"]) == 7           # faqat oy: 2026-10
    assert db.was_erased(user_id) and not db.was_erased(user_id + 1)


def test_returning_user_cannot_be_referred_again(user_id):
    ref = 5005
    db.get_or_create_user(ref, "Ref", None)
    assert db.set_referrer(user_id, ref)
    db.erase_user(user_id)
    db.get_or_create_user(user_id, "B", None)
    assert not db.set_referrer(user_id, ref)


# --------------------------------------------------------------------------- #
# 3. Kurs olish event loop'ni to'xtatmaydi
# --------------------------------------------------------------------------- #

def test_saving_dollar_entry_does_not_block_other_users(user_id, monkeypatch):
    import bot
    import rates
    rates.clear_cache()

    def slow_fetch(currency, day):                 # cbu.uz sekin
        time.sleep(0.3)
        return None
    monkeypatch.setattr(rates, "_fetch_cbu", slow_fetch)
    db.set_consent(user_id, config.CONSENT_VERSION)
    yesterday = (reports.today() - timedelta(days=1)).isoformat()
    parsed = ai._normalize_parse({"niyat": "yozuv", "yozuvlar": [
        {"turi": "chiqim", "summa": 50, "valyuta": "usd",
         "kategoriya": "transport", "sana": yesterday}]}, reports.today())
    msg = _Msg()
    upd = _update(user_id, msg)

    async def scenario():
        ticks = []

        async def heartbeat():
            for _ in range(30):
                ticks.append(time.monotonic())
                await asyncio.sleep(0.02)
        hb = asyncio.create_task(heartbeat())
        await asyncio.sleep(0.03)
        await bot._save_parsed(upd, _ctx(), parsed, "kecha 50 dollar", msg)
        await hb
        return max(b - a for a, b in zip(ticks, ticks[1:]))

    assert asyncio.run(scenario()) < 0.5           # ilgari: 4 × 0.3 = 1.2 s
    assert db.tx_count(user_id) == 1


# --------------------------------------------------------------------------- #
# 4. Byudjet hisobot bilan bir xil sanaydi
# --------------------------------------------------------------------------- #

def test_budget_counts_dollar_spending_like_the_report(user_id):
    day = reports.today()
    db.set_budget(user_id, "oziq-ovqat", 1_000_000)
    db.add_transaction(user_id, "chiqim", 600_000, "oziq-ovqat", "bozor")
    db.add_transaction(user_id, "chiqim", 50, "oziq-ovqat", "supermarket",
                       currency="usd")                # 50 × 12 600 = 630 000
    b = next(r for r in db.budget_status(user_id) if r["category"] == "oziq-ovqat")
    report = {c: s for c, s, _ in db.by_category_unified(
        user_id, day.replace(day=1), day, "chiqim")}
    assert b["spent"] == report["oziq-ovqat"] == 1_230_000
    assert b["percent"] >= 100


def test_budget_ignores_entries_dated_next_month(user_id):
    day = reports.today()
    next_month = (day.replace(day=28) + timedelta(days=4)).replace(day=1)
    db.set_budget(user_id, "transport", 100_000)
    db.add_transaction(user_id, "chiqim", 90_000, "transport", "x",
                       occurred_on=next_month.isoformat())
    b = next(r for r in db.budget_status(user_id) if r["category"] == "transport")
    assert b["spent"] == 0


# --------------------------------------------------------------------------- #
# 5. Shubhali sana jimgina saqlanmaydi
# --------------------------------------------------------------------------- #

def test_date_suspicious_bounds():
    today = date(2026, 10, 8)
    assert not ai.date_suspicious("2026-10-08", today)
    assert not ai.date_suspicious("2026-10-07", today)
    assert not ai.date_suspicious("2025-10-08", today)          # aynan bir yil
    assert ai.date_suspicious("2026-10-09", today)              # ertaga
    assert ai.date_suspicious("2025-10-07", today)              # bir yildan eski
    assert ai.date_suspicious("2062-10-08", today)
    assert ai.date_suspicious("buzuq", today)


def test_other_year_dates_show_the_year():
    this_year = reports.today().year
    assert str(this_year) not in reports.fmt_date(f"{this_year}-10-08", "uz")
    assert reports.fmt_date(f"{this_year + 1}-10-08", "uz").startswith(f"{this_year + 1}-yil")
    assert reports.fmt_date(f"{this_year - 1}-10-08", "ru").endswith(str(this_year - 1))


class _Msg:
    chat_id = 1001

    def __init__(self):
        self.replies = []

    async def reply_text(self, text, **kw):
        self.replies.append((text, kw.get("reply_markup")))
        return self

    @property
    def buttons(self):
        markup = self.replies[0][1]
        return [b.callback_data for row in markup.inline_keyboard for b in row]


class _Bot:
    async def send_message(self, *a, **kw):
        pass

    async def send_chat_action(self, *a, **kw):
        pass


def _update(user_id, msg, data=None):
    user = SimpleNamespace(id=user_id, first_name="Ali", username=None)
    query = None
    if data:
        query = SimpleNamespace(data=data, message=msg, answers=[])

        async def answer(text=None, **kw):
            query.answers.append(text)

        async def edit_markup(markup=None, **kw):
            pass
        query.answer, query.edit_message_reply_markup = answer, edit_markup
    return SimpleNamespace(effective_user=user, effective_message=msg, message=msg,
                           effective_chat=SimpleNamespace(type="private", id=user_id),
                           callback_query=query)


def _ctx():
    return SimpleNamespace(bot=_Bot(), user_data={}, args=[], bot_data={})


def _future_parsed():
    today = reports.today()
    return ai._normalize_parse({"niyat": "yozuv", "yozuvlar": [
        {"turi": "chiqim", "summa": 45_000, "valyuta": "som", "kategoriya": "transport",
         "izoh": "taksi", "sana": (today + timedelta(days=365)).isoformat()}]}, today)


def _ask(user_id):
    import bot
    db.set_consent(user_id, config.CONSENT_VERSION)
    msg = _Msg()
    asyncio.run(bot._dispatch_parsed(_update(user_id, msg), _ctx(), _future_parsed(),
                                     "taksi 45 ming", msg))
    return msg


def test_future_date_asks_and_saves_nothing(user_id):
    msg = _ask(user_id)
    assert db.tx_count(user_id) == 0
    assert str(reports.today().year + 1) in msg.replies[0][0]   # yil ko'rinadi
    assert [b.split(":")[1] for b in msg.buttons] == ["today", "keep", "no"]


def test_date_today_button_saves_with_today(user_id):
    import bot
    msg = _ask(user_id)
    token = msg.buttons[0].split(":", 2)[2]
    asyncio.run(bot.on_date_callback(_update(user_id, msg, f"dt:today:{token}"), _ctx()))
    rows = db.all_rows(user_id)
    assert len(rows) == 1 and rows[0]["occurred_on"] == reports.today().isoformat()


def test_date_keep_button_saves_as_given(user_id):
    import bot
    msg = _ask(user_id)
    token = msg.buttons[1].split(":", 2)[2]
    asyncio.run(bot.on_date_callback(_update(user_id, msg, f"dt:keep:{token}"), _ctx()))
    assert db.all_rows(user_id)[0]["occurred_on"].startswith(str(reports.today().year + 1))


def test_date_cancel_and_foreign_user_save_nothing(user_id):
    import bot
    msg = _ask(user_id)
    token = msg.buttons[2].split(":", 2)[2]
    other = _update(user_id + 1, msg, f"dt:today:{token}")      # begona tugmani bosdi
    asyncio.run(bot.on_date_callback(other, _ctx()))
    asyncio.run(bot.on_date_callback(_update(user_id, msg, f"dt:no:{token}"), _ctx()))
    assert db.tx_count(user_id) == 0 and db.tx_count(user_id + 1) == 0


def test_normal_date_is_saved_without_question(user_id):
    import bot
    db.set_consent(user_id, config.CONSENT_VERSION)
    parsed = ai._normalize_parse({"niyat": "yozuv", "yozuvlar": [
        {"turi": "chiqim", "summa": 45_000, "valyuta": "som", "kategoriya": "transport",
         "sana": reports.today().isoformat()}]}, reports.today())
    msg = _Msg()
    asyncio.run(bot._dispatch_parsed(_update(user_id, msg), _ctx(), parsed, "x", msg))
    assert db.tx_count(user_id) == 1


def test_mini_app_rejects_future_date(user_id, monkeypatch):
    from fastapi.testclient import TestClient
    import webapp
    db.set_consent(user_id, config.CONSENT_VERSION)
    app = webapp.app
    app.dependency_overrides[webapp.current_user] = lambda: {
        "user_id": user_id, "lang": "uz", "access": db.access_status(user_id)}
    try:
        client = TestClient(app)
        tomorrow = (reports.today() + timedelta(days=1)).isoformat()
        bad = client.post("/api/transactions", json={
            "kind": "chiqim", "amount": 1000, "category": "transport", "date": tomorrow})
        ok = client.post("/api/transactions", json={
            "kind": "chiqim", "amount": 1000, "category": "transport",
            "date": reports.today().isoformat()})
    finally:
        app.dependency_overrides.clear()
    assert bad.status_code == 400 and ok.status_code == 201


class _Status:
    text = None

    async def edit_text(self, text, **kw):
        self.text = text


class _ReceiptMsg(_Msg):
    photo = document = caption = media_group_id = None

    async def reply_text(self, text, **kw):
        self.statuses = getattr(self, "statuses", []) + [_Status()]
        return self.statuses[-1]


def test_receipt_with_misread_year_is_saved_today_and_says_so(user_id, monkeypatch):
    import bot
    db.set_consent(user_id, config.CONSENT_VERSION)
    misread = date(reports.today().year + 36, 10, 8).isoformat()   # «08.10.62»

    async def fake_parse(images, today=None, caption=""):
        return {"oqildi": True, "dokon": "Korzinka", "sana": misread,
                "mahsulotlar": [{"nomi": "Non", "miqdori": 1, "summa": 8_000,
                                 "kategoriya": "oziq-ovqat"}],
                "chekdagi_jami": 8_000, "chegirma": None, "valyuta": "som",
                "izoh_matni": "", "_usage": None,
                "tekshiruv": {"holat": "mos", "hisoblangan": 8_000, "chekdagi": 8_000,
                              "farq": 0, "narxlar": "chegirmadan_keyin"}}
    monkeypatch.setattr(ai, "parse_receipt", fake_parse)
    msg = _ReceiptMsg()
    asyncio.run(bot._process_receipt(_update(user_id, msg), _ctx(),
                                     [("x", "image/jpeg")], ""))
    rows = db.all_rows(user_id)
    assert rows and all(r["occurred_on"] == reports.today().isoformat() for r in rows)
    texts = [st.text for st in msg.statuses if st.text]
    assert any(str(reports.today().year + 36) in t for t in texts)   # asl sana aytilgan


# --------------------------------------------------------------------------- #
# 6. Savol-javob kirishi ixcham, lekin ma'lumot yo'qolmaydi
# --------------------------------------------------------------------------- #

def test_qa_rows_table_is_lossless_and_compact(user_id, monkeypatch):
    from tests import fake_ai
    day = reports.today()
    db.add_transaction(user_id, "chiqim", 45_000, "transport", "taksi | tun\nyo'l",
                       occurred_on=day.isoformat())
    db.add_transaction(user_id, "chiqim", 12.5, "aloqa va internet", "spotify",
                       occurred_on=day.isoformat(), currency="usd")
    db.add_transaction(user_id, "qarz_berdim", 500_000, "qarz", "", person="Akmal",
                       occurred_on=day.isoformat())
    rows = db.rows_for_ai(user_id, 150)
    fake = fake_ai.install(monkeypatch, [{}])
    asyncio.run(ai.answer_question("qancha?", rows, today=day,
                                   summary_rows=db.list_range(user_id, day, day),
                                   monthly=db.monthly_totals(user_id)))
    prompt = fake.calls[0]["content"]

    table = prompt.split(ai.ROW_COLUMNS + "\n", 1)[1].split("\n\n", 1)[0].splitlines()
    parsed = [line.split("|") for line in table]
    assert all(len(cells) == 7 for cells in parsed)             # «|» izohni buzmadi
    got = {(c[1], c[2], c[3], c[4], c[5], c[6]) for c in parsed}
    assert ("chiqim", "45000", "som", "transport", "taksi / tun yo'l", "") in got
    assert ("chiqim", "12.5", "usd", "aloqa va internet", "spotify", "") in got
    assert ("qarz_berdim", "500000", "som", "qarz", "", "Akmal") in got
    # Takrorlanuvchi JSON kalitlari va bo'sh joy endi yuborilmaydi.
    assert '"kategoriya":' not in prompt and '"shaxs": null' not in prompt
    assert "\n " not in prompt.split("Savol:")[0]                # indent yo'q
