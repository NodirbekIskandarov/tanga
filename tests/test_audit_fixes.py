"""Audit (2026-10) topgan xatolar — har biri qaytib kelmasligi uchun.

1. PDF hujjat (to'lov cheki ham, do'kon cheki ham) handlerga yetib
   bormasdi: filtr faqat rasmni o'tkazardi.
2. «➕ Chek davomi bor» tugmasi NameError berardi (COLLECT_MENU).
3. Rozilik bermagan odam hisobini o'chira olmasdi: tasdiq so'zi rozilik
   darvozasiga urilardi.
4. Obuna uzaytirilganda warned_stage qolib ketardi — ikkinchi obunada
   muddat ogohlantirishi kelmasdi.
5. Chek byudjet ogohlantirishini tekshirmasdi.
6. AI savol-javobida jamlanma faqat oxirgi QA_MAX_ROWS yozuvdan olinardi.
"""

import asyncio
from datetime import datetime, timedelta
from types import SimpleNamespace

import pytest
from telegram import Chat, Document, Message as TgMessage, ReplyKeyboardMarkup, Update
from telegram.ext import Application, MessageHandler

import config
import db
import i18n
import reports
from tests import fake_ai

UID = 4242


class Bot:
    def __init__(self):
        self.messages = []

    async def send_message(self, chat_id, text, **kw):
        self.messages.append((chat_id, text))

    async def send_chat_action(self, *a, **kw):
        pass


class Status:
    def __init__(self):
        self.text = None

    async def edit_text(self, text, **kw):
        self.text = text


class Message:
    def __init__(self, text=""):
        self.text, self.photo, self.document = text, None, None
        self.caption, self.media_group_id, self.chat_id = None, None, UID
        self.replies = []

    async def reply_text(self, text, **kw):
        self.replies.append((text, kw.get("reply_markup")))
        return Status()


class Query:
    def __init__(self, data, message):
        self.data, self.message = data, message
        self.answers, self.edits = [], []

    async def answer(self, text=None, **kw):
        self.answers.append(text)

    async def edit_message_text(self, text, **kw):
        self.edits.append(text)


def _update(message=None, data=None):
    message = message or Message()
    user = SimpleNamespace(id=UID, first_name="Test", username=None)
    return SimpleNamespace(effective_user=user, effective_message=message,
                           message=message,
                           callback_query=Query(data, message) if data else None)


def _ctx(bot=None):
    return SimpleNamespace(bot=bot or Bot(), user_data={}, args=[], bot_data={})


@pytest.fixture
def consented():
    db.get_or_create_user(UID, "Test", None)
    db.set_consent(UID, config.CONSENT_VERSION)
    return UID


# --------------------------------------------------------------- 1. PDF --

def _photo_handler():
    import bot
    app = Application.builder().token("123:test").build()
    bot.register_handlers(app)
    return next(h for group in app.handlers.values() for h in group
                if isinstance(h, MessageHandler) and h.callback is bot.on_photo)


def _document_update(mime: str, name: str) -> Update:
    doc = Document(file_id="F1", file_unique_id="U1", mime_type=mime,
                   file_name=name)
    msg = TgMessage(message_id=1, date=datetime.now(),
                    chat=Chat(id=UID, type="private"), document=doc)
    return Update(update_id=1, message=msg)


@pytest.mark.parametrize("mime,name", [
    ("application/pdf", "kvitansiya.pdf"),
    ("application/octet-stream", "chek.PDF"),      # noto'g'ri MIME, to'g'ri nom
    ("image/jpeg", "chek.jpg"),
])
def test_receipt_documents_reach_on_photo(mime, name):
    assert _photo_handler().check_update(_document_update(mime, name))


def test_other_documents_still_ignored():
    assert not _photo_handler().check_update(
        _document_update("application/zip", "arxiv.zip"))


# ------------------------------------------------- 2. Chek davomi bor --

def test_continue_receipt_button_shows_collect_keyboard(consented):
    import bot
    db.add_receipt(UID, "r1", shop="Korzinka", occurred_on=reports.today().isoformat(),
                   currency="som", printed_total=None, discount=None,
                   items=[{"kind": "chiqim", "amount": 5000, "category": "oziq-ovqat",
                           "note": "non"}])
    bot._last_receipt.set(UID, {"receipt_id": "r1", "images": [("x", "image/jpeg")],
                                "caption": ""})
    u = _update(data="A:r1")
    asyncio.run(bot.on_callback(u, _ctx()))

    text, markup = u.message.replies[-1]
    assert isinstance(markup, ReplyKeyboardMarkup)
    assert bot._collect.get(UID)["images"] == [("x", "image/jpeg")]
    bot._collect.pop(UID, None)


# ------------------------------------------ 3. O'chirish rozilisiz --

def test_erase_completes_without_consent():
    import bot
    db.get_or_create_user(UID, "Test", None)        # rozilik YO'Q
    assert not db.has_consent(UID, config.CONSENT_VERSION)
    ctx = _ctx()

    asyncio.run(bot.cmd_erase(_update(), ctx))
    asyncio.run(bot.on_callback(_update(data="erase:ha"), ctx))
    word = i18n.t("uz", "erase_word")
    u = _update(Message(word))
    asyncio.run(bot.on_text(u, ctx))

    with db.get_conn() as conn:
        assert conn.execute("SELECT 1 FROM users WHERE user_id = ?",
                            (UID,)).fetchone() is None
    # Rozilik so'ralmadi — o'chirish natijasi yozildi.
    assert u.message.replies and "consent" not in u.message.replies[-1][0].lower()


def test_wrong_erase_word_keeps_account():
    import bot
    db.get_or_create_user(UID, "Test", None)
    bot._erase_typed.set(UID, True)
    asyncio.run(bot.on_text(_update(Message("yo'q")), _ctx()))
    assert db.get_or_create_user(UID) is not None
    assert bot._erase_typed.get(UID) is None


# ------------------------------------------------ 4. warned_stage --

def test_renewal_resets_expiry_warnings():
    db.get_or_create_user(UID, "Test", None)
    db.grant_subscription(UID, 1)
    stage = next(r for r in db.users_expiring() if r["user_id"] == UID)["stage"]
    db.mark_warned(UID, stage)                      # «1 kun qoldi» yuborildi

    db.grant_subscription(UID, 1)                   # uzaytirildi: 2 kun qoldi
    again = [r for r in db.users_expiring() if r["user_id"] == UID]
    assert again, "uzaytirilgan obunaga ogohlantirish yana kelishi kerak"


def test_bonus_on_subscription_resets_warnings():
    db.get_or_create_user(UID, "Test", None)
    db.grant_subscription(UID, 1)
    db.mark_warned(UID, 1)
    db.add_bonus_days(UID, 1)
    with db.get_conn() as conn:
        assert conn.execute("SELECT warned_stage FROM users WHERE user_id = ?",
                            (UID,)).fetchone()[0] == 0


# ------------------------------------------------ 5. Chek va byudjet --

def test_receipt_triggers_budget_alert(consented, monkeypatch):
    import ai
    import bot
    today = reports.today().isoformat()
    data = {
        "oqildi": True, "dokon": "Korzinka", "sana": today,
        "mahsulotlar": [{"nomi": "Guruch", "miqdori": 1, "summa": 300_000,
                         "kategoriya": "oziq-ovqat"}],
        "chekdagi_jami": 300_000, "chegirma": None, "valyuta": "som",
        "izoh_matni": "",
        "tekshiruv": {"holat": "mos", "hisoblangan": 300_000, "chekdagi": 300_000,
                      "farq": 0, "narxlar": "chegirmadan_keyin"},
        "_usage": None,
    }

    async def fake_parse(images, today=None, caption=""):
        return dict(data)

    monkeypatch.setattr(ai, "parse_receipt", fake_parse)
    db.set_budget(UID, "oziq-ovqat", 200_000)
    tg = Bot()
    asyncio.run(bot._process_receipt(_update(), _ctx(tg), [("x", "image/jpeg")], ""))

    assert any(uid == UID and "byudjeti oshib ketdi" in text
               for uid, text in tg.messages)


# ------------------------------------------------ 6. AI jamlanmasi --

def test_qa_aggregates_cover_all_rows_not_just_latest(monkeypatch):
    import ai
    db.get_or_create_user(UID, "Test", None)
    today = reports.today()
    for i in range(30):
        db.add_transaction(UID, "chiqim", 10_000, "transport", "taksi",
                           occurred_on=today.isoformat())
    fake = fake_ai.install(monkeypatch, [{}])

    rows = db.rows_for_ai(UID, 5)                   # xom ro'yxat cheklangan
    summary = db.list_range(UID, today.replace(day=1), today)
    asyncio.run(ai.answer_question("bu oy qancha?", rows, today=today,
                                   summary_rows=summary,
                                   monthly=db.monthly_totals(UID)))

    prompt = fake.calls[0]["content"]
    assert '"chiqim":300000.0' in prompt             # 30 ta yozuvning hammasi
    assert today.strftime("%Y-%m") in prompt         # oylik jamlar ham bor


def test_monthly_totals_keep_currencies_apart():
    db.get_or_create_user(UID, "Test", None)
    day = reports.today().isoformat()
    db.add_transaction(UID, "chiqim", 50_000, "transport", occurred_on=day)
    db.add_transaction(UID, "chiqim", 20, "transport", occurred_on=day, currency="usd")
    got = {(m["currency"], m["kind"]): m["total"] for m in db.monthly_totals(UID)}
    assert got[("som", "chiqim")] == 50_000 and got[("usd", "chiqim")] == 20


# ------------------------------------------------ Mayda tuzatishlar --

def test_default_date_is_tashkent(monkeypatch):
    fixed = datetime(2026, 10, 6, 1, 30, tzinfo=config.TZ)   # server hali 5-oktabrda
    monkeypatch.setattr(db, "_now", lambda: fixed)
    db.get_or_create_user(UID, "Test", None)
    tx = db.add_transaction(UID, "jamgarma", 10_000, "jamg'arma")
    assert db.get_transaction(UID, tx)["occurred_on"] == "2026-10-06"


def test_erase_queue_removes_events():
    db.get_or_create_user(UID, "Test", None)
    db.log_event(UID, "start")
    with db.get_conn() as conn:
        conn.execute("INSERT INTO private_erase_queue (user_id) VALUES (?)", (UID,))
    db.drain_erase_queue()
    assert db.event_count(UID, "start") == 0


def test_cushion_line_cyrillic_is_uzbek():
    import bot
    db.get_or_create_user(UID, "Test", None)
    db.add_transaction(UID, "chiqim", 3_000_000, "transport",
                       occurred_on=reports.today().isoformat())
    line = bot._cushion_line(UID, "uzc", 5_000_000)
    assert "мес." not in line and "дней" not in line
    assert "ой" in line or "кун" in line
