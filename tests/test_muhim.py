"""QA hisoboti, 3-bo'lim (M-bandlar) — bot tomoni.

M6  «Chek davomi bor» eski chekni darhol o'chirmaydi.
M7  /byudjet summasi oxirgi 1–2 so'zdan; topilmagan kategoriya — tugmalar.
M8  Referal bonusi do'st faol bo'lgachgina; yillik chegara.
M11 Kutilmagan xato: foydalanuvchiga javob, egaga (cheklangan) xabar.
M13 Bot faqat shaxsiy chatda.
M14 «400$ so'mda qancha» — kurs bilan javob.
M15 «salom» — AI'siz.
M16 Asoschilar taklifi: «100/100» emas.
"""

import asyncio
from datetime import datetime, timedelta, timezone
from types import SimpleNamespace

import pytest
from telegram.ext import ApplicationHandlerStop

import config
import db
from tests import fake_ai

UID, FRIEND, OWNER = 9191, 9292, 777


class Bot:
    def __init__(self):
        self.messages, self.left = [], []

    async def send_message(self, chat_id, text, **kw):
        self.messages.append((chat_id, text))

    async def send_chat_action(self, *a, **kw):
        pass

    async def leave_chat(self, chat_id):
        self.left.append(chat_id)


class Status:
    async def edit_text(self, text, **kw):
        self.text = text


class Message:
    def __init__(self, text="", uid=UID):
        self.text, self.photo, self.document = text, None, None
        self.caption, self.media_group_id, self.chat_id = None, None, uid
        self.replies = []

    async def reply_text(self, text, **kw):
        self.replies.append((text, kw.get("reply_markup")))
        return Status()

    async def edit_text(self, text, **kw):
        self.replies.append((text, None))

    def buttons(self, i=-1):
        rows = getattr(self.replies[i][1], "inline_keyboard", None) or []
        return [b.callback_data for row in rows for b in row]

    @property
    def last(self):
        return self.replies[-1][0]


class Query:
    def __init__(self, data, message):
        self.data, self.message, self.answers, self.edits = data, message, [], []

    async def answer(self, text=None, **kw):
        self.answers.append(text)

    async def edit_message_text(self, text, **kw):
        self.edits.append(text)

    async def edit_message_reply_markup(self, **kw):
        pass


def _update(message=None, data=None, uid=UID, chat_type="private"):
    message = message or Message(uid=uid)
    user = SimpleNamespace(id=uid, first_name="Test", username=None)
    return SimpleNamespace(effective_user=user, effective_message=message,
                           effective_chat=SimpleNamespace(id=uid, type=chat_type),
                           message=message, my_chat_member=None,
                           callback_query=Query(data, message) if data else None)


def _ctx(bot=None, args=None):
    return SimpleNamespace(bot=bot or Bot(), user_data={}, args=args or [],
                           bot_data={}, error=None)


@pytest.fixture(autouse=True)
def user():
    import bot
    db.get_or_create_user(UID, "Test", None)
    db.set_consent(UID, config.CONSENT_VERSION)
    for store in (bot._collect, bot._last_receipt):
        store._data.clear()
    # getattr: eski kodda bu o'zgaruvchi yo'q — testlar fixture'da emas,
    # o'zida yiqilsin (har bir test xatoni ushlashini tekshirish uchun).
    getattr(bot, "_error_notified", {}).clear()
    yield


# ---------------------------------------------------------------- M6 --

def _receipt_data(total):
    return {"oqildi": True, "dokon": "Korzinka", "sana": datetime.now(config.TZ).date().isoformat(),
            "mahsulotlar": [{"nomi": "Non", "miqdori": 1, "summa": total,
                             "kategoriya": "oziq-ovqat"}],
            "chekdagi_jami": total, "chegirma": None, "valyuta": "som", "izoh_matni": "",
            "tekshiruv": {"holat": "mos", "hisoblangan": total, "chekdagi": total,
                          "farq": 0, "narxlar": "chegirmadan_keyin"}, "_usage": None}


def _old_receipt():
    import bot
    db.add_receipt(UID, "old1", shop="Korzinka", occurred_on=datetime.now(config.TZ).date().isoformat(),
                   currency="som", printed_total=None, discount=None,
                   items=[{"kind": "chiqim", "amount": 5000, "category": "oziq-ovqat",
                           "note": "non"}])
    bot._last_receipt.set(UID, {"receipt_id": "old1", "images": [("x", "image/jpeg")],
                                "caption": ""})


def test_continue_receipt_keeps_old_until_cancel():
    import bot
    _old_receipt()
    asyncio.run(bot.on_callback(_update(data="A:old1"), _ctx()))
    assert db.get_receipt(UID, "old1") is not None              # darhol o'chmadi
    asyncio.run(bot.cmd_collect_cancel(_update(), _ctx()))
    assert db.get_receipt(UID, "old1") is not None              # bekor — chek joyida


def test_continue_receipt_replaces_after_successful_read(monkeypatch):
    import ai
    import bot

    async def fake_parse(images, today=None, caption=""):
        return _receipt_data(12_000)

    monkeypatch.setattr(ai, "parse_receipt", fake_parse)
    _old_receipt()
    asyncio.run(bot.on_callback(_update(data="A:old1"), _ctx()))
    asyncio.run(bot.cmd_collect_done(_update(), _ctx()))
    assert db.get_receipt(UID, "old1") is None
    assert db.tx_count(UID) == 1                                 # faqat yangi chek


def test_continue_receipt_failed_read_keeps_old(monkeypatch):
    import ai
    import bot

    async def fake_parse(images, today=None, caption=""):
        return {"oqildi": False, "izoh_matni": "xira", "_usage": None}

    monkeypatch.setattr(ai, "parse_receipt", fake_parse)
    _old_receipt()
    asyncio.run(bot.on_callback(_update(data="A:old1"), _ctx()))
    asyncio.run(bot.cmd_collect_done(_update(), _ctx()))
    assert db.get_receipt(UID, "old1") is not None


# ---------------------------------------------------------------- M7 --

def test_budget_args_and_category_matching():
    import bot
    assert bot.split_budget_args(["oziq-ovqat", "2", "mln"]) == ("oziq-ovqat", 2_000_000)
    assert bot.split_budget_args(["transport", "500k"]) == ("transport", 500_000)
    assert bot.split_budget_args(["2", "mln"]) == ("", 2_000_000)
    assert bot.match_expense_category("oziq-ovqat") == "oziq-ovqat"
    assert bot.match_expense_category("Kafe") == "kafe va restoran"
    assert bot.match_expense_category("gigiyena") == "uy-ro'zg'or va gigiyena"
    assert bot.match_expense_category("uy") is None               # ikkitasiga mos
    assert bot.match_expense_category("mashina") is None


def test_budget_example_from_guide_works():
    import bot
    u = _update()
    asyncio.run(bot.cmd_budget(u, _ctx(args=["oziq-ovqat", "2", "mln"])))
    budgets = {r["category"]: r["amount"] for r in db.list_budgets(UID)}
    assert budgets == {"oziq-ovqat": 2_000_000}


def test_unknown_category_asks_instead_of_other():
    import bot
    u = _update()
    asyncio.run(bot.cmd_budget(u, _ctx(args=["mashina", "1", "mln"])))
    assert db.list_budgets(UID) == []                             # «boshqa chiqim» ga yozilmadi
    data = next(b for b in u.message.buttons() if b.startswith("bset:"))
    idx = config.CATEGORY_REGISTRY.index("transport")
    asyncio.run(bot.on_callback(_update(data=f"bset:{idx}:1000000"), _ctx()))
    assert {r["category"]: r["amount"] for r in db.list_budgets(UID)} == {"transport": 1_000_000}
    assert data.endswith(":1000000")


# ---------------------------------------------------------------- M8 --

def _friend(created_hours_ago=1):
    db.get_or_create_user(FRIEND, "Do'st", None)
    created = (datetime.now(timezone.utc) - timedelta(hours=created_hours_ago)).strftime("%Y-%m-%d %H:%M:%S")
    with db.get_conn() as conn:
        conn.execute("UPDATE users SET created_at = ? WHERE user_id = ?", (created, FRIEND))
    assert db.set_referrer(FRIEND, UID)


def _until(uid):
    with db.get_conn() as conn:
        row = conn.execute("SELECT trial_ends_at, subscribed_until FROM users WHERE user_id = ?",
                           (uid,)).fetchone()
    return row["subscribed_until"] or row["trial_ends_at"]


def _reward(bot_):
    asyncio.run(bot_.maybe_reward_referral(_ctx(), FRIEND, Message(uid=FRIEND), "Do'st"))


def test_referral_bonus_only_after_activity():
    import bot
    _friend()
    before_ref, before_friend = _until(UID), _until(FRIEND)
    _reward(bot)                                                  # hali yozuv yo'q
    assert _until(UID) == before_ref

    for _ in range(config.REFERRAL_MIN_ENTRIES):
        db.add_transaction(FRIEND, "chiqim", 10_000, "transport")
    _reward(bot)
    assert _until(UID) > before_ref and _until(FRIEND) > before_friend
    once = _until(UID)
    _reward(bot)                                                  # ikkinchi marta — yo'q
    assert _until(UID) == once


def test_referral_window_expired_gives_nothing():
    import bot
    _friend(created_hours_ago=24 * (config.REFERRAL_WINDOW_DAYS + 1))
    for _ in range(config.REFERRAL_MIN_ENTRIES):
        db.add_transaction(FRIEND, "chiqim", 10_000, "transport")
    before = _until(UID)
    _reward(bot)
    assert _until(UID) == before


def test_referral_yearly_cap():
    import bot
    db.log_event(UID, "referral_bonus", str(config.REFERRAL_YEARLY_CAP_DAYS - 2))
    _friend()
    for _ in range(config.REFERRAL_MIN_ENTRIES):
        db.add_transaction(FRIEND, "chiqim", 10_000, "transport")
    _reward(bot)
    assert db.referral_days_this_year(UID) == config.REFERRAL_YEARLY_CAP_DAYS


# --------------------------------------------------------------- M11 --

def test_error_handler_replies_and_notifies_owner_once(monkeypatch):
    import bot
    monkeypatch.setattr(config, "OWNER_IDS", {OWNER})
    tg = Bot()
    try:
        raise ValueError("sinov xatosi")
    except ValueError as exc:
        err = exc
    for _ in range(2):
        u = _update()
        ctx = _ctx(tg)
        ctx.error = err
        asyncio.run(bot.on_error(u, ctx))
        assert "Xatolik yuz berdi" in u.message.last
    to_owner = [t for chat, t in tg.messages if chat == OWNER]
    assert len(to_owner) == 1 and "ValueError" in to_owner[0]


# --------------------------------------------------------------- M13 --

def test_group_updates_are_stopped_and_bot_leaves():
    import bot
    with pytest.raises(ApplicationHandlerStop):
        asyncio.run(bot._private_chat_guard(_update(chat_type="group"), _ctx()))
    tg = Bot()
    u = _update(chat_type="supergroup")
    u.my_chat_member = object()
    with pytest.raises(ApplicationHandlerStop):
        asyncio.run(bot._private_chat_guard(u, _ctx(tg)))
    assert tg.left == [UID]
    assert asyncio.run(bot._private_chat_guard(_update(), _ctx())) is None


# --------------------------------------------------------- M14 / M15 --

def test_currency_question_answered_with_rate(monkeypatch):
    import bot
    fake_ai.install(monkeypatch, [{"niyat": "kurs", "yozuvlar": [],
                                   "kurs_summa": 400, "kurs_valyuta": "usd"}])
    u = _update(Message("400$ so'mda qancha bo'ladi"))
    asyncio.run(bot.on_text(u, _ctx()))
    assert "5 040 000" in u.message.last                         # 400 × 12 600
    assert db.tx_count(UID) == 0


def test_greeting_needs_no_ai(monkeypatch):
    import bot
    fake = fake_ai.install(monkeypatch, [])
    u = _update(Message("Salom!"))
    asyncio.run(bot.on_text(u, _ctx()))
    assert fake.calls == [] and "Salom" in u.message.last
    assert db.count_today(UID, "matn") == 0                       # limit sarflanmadi
    assert not bot.is_greeting("salom, taksi 20k")


# --------------------------------------------------------------- M16 --

def test_founders_line_shows_left_only_after_sales():
    import bot
    assert "faqat 100 ta joy" in bot.plans_text(lang="uz")
    with db.get_conn() as conn:
        conn.execute("INSERT INTO subscription_requests (user_id, plan_code, status) "
                     "VALUES (1, 'f12', 'tasdiqlandi')")
    text = bot.plans_text(lang="uz")
    assert "99 ta joy qoldi" in text and "100/100" not in text
