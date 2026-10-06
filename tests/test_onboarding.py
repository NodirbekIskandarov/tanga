"""Faollashtirish va rozilik (QA hisoboti K5–K7, 2026-10).

K5  Maxfiylik matni haqiqatga mos; /csv hamma uchun bepul.
K6  Qisqa rozilik ekrani; eski roziligi borga «siyosat yangilandi».
K7  /start dan keyin «Sinab ko'ring» tugmasi; 2 soatdan keyin bitta eslatma.
"""

import asyncio
from datetime import datetime, timedelta
from types import SimpleNamespace

import config
import db
import i18n
from tests import fake_ai

UID = 6161


class Bot:
    def __init__(self):
        self.messages = []

    async def send_message(self, chat_id, text, **kw):
        self.messages.append((chat_id, text, kw.get("reply_markup")))

    async def send_chat_action(self, *a, **kw):
        pass


class Message:
    def __init__(self, text=""):
        self.text, self.photo, self.document = text, None, None
        self.caption, self.media_group_id, self.chat_id = None, None, UID
        self.replies, self.documents = [], []

    async def reply_text(self, text, **kw):
        self.replies.append((text, kw.get("reply_markup")))
        return self

    async def reply_document(self, document=None, **kw):
        self.documents.append(document)

    def buttons(self, i=-1):
        rows = getattr(self.replies[i][1], "inline_keyboard", None) or []
        return [b.callback_data for row in rows for b in row]


class Query:
    def __init__(self, data, message):
        self.data, self.message, self.answers, self.edits = data, message, [], []

    async def answer(self, text=None, **kw):
        self.answers.append(text)

    async def edit_message_text(self, text, **kw):
        self.edits.append(text)

    async def edit_message_reply_markup(self, **kw):
        pass


def _update(message=None, data=None, args=None):
    message = message or Message()
    user = SimpleNamespace(id=UID, first_name="Test", username=None)
    return SimpleNamespace(effective_user=user, effective_message=message,
                           effective_chat=SimpleNamespace(id=UID), message=message,
                           callback_query=Query(data, message) if data else None)


def _ctx(bot=None, args=None):
    return SimpleNamespace(bot=bot or Bot(), user_data={}, args=args or [], bot_data={})


# ---------------------------------------------------------------- K6 --

def test_new_user_sees_short_consent():
    import bot
    u = _update()
    asyncio.run(bot.cmd_start(u, _ctx()))
    text = u.message.replies[-1][0]
    assert len(text.splitlines()) <= 10            # ilgari ~30 qator edi
    assert "/maxfiylik" in text and "/shartlar" in text
    assert u.message.buttons() == ["ok:yes", "ok:privacy", "ok:terms"]
    assert "Boshlash" in u.message.replies[-1][1].inline_keyboard[0][0].text


def test_returning_user_sees_what_changed():
    import bot
    db.get_or_create_user(UID, "Test", None)
    db.set_consent(UID, "2026-08-1")               # eski versiya
    u = _update()
    asyncio.run(bot.cmd_start(u, _ctx()))
    assert "yangilandi" in u.message.replies[-1][0]
    assert "Davom etish" in u.message.replies[-1][1].inline_keyboard[0][0].text


# ---------------------------------------------------------------- K5 --

def test_privacy_has_no_false_promises():
    for lang in ("uz", "ru"):
        text = i18n.t(lang, "privacy", contact="@x")
        assert "30" in text                          # Anthropic: 30 kungacha
        assert "Telegram" in text                    # zaxira Telegram'da ham
        assert "Contabo" in text
    uz = i18n.t("uz", "privacy", contact="@x")
    assert "parol bilan kirish o'chirilgan" not in uz
    assert "darhol o'chadi" not in uz
    assert "sizdan boshqa hech kim" not in uz.lower()
    assert "Adminга" not in uz                       # kirill harf aralashmasin


def test_consent_version_bumped():
    assert config.CONSENT_VERSION > "2026-08-1"


def test_free_user_gets_csv():
    import bot
    db.get_or_create_user(UID, "Test", None)
    db.set_consent(UID, config.CONSENT_VERSION)
    past = (datetime.now(config.TZ) - timedelta(days=3)).isoformat()
    with db.get_conn() as conn:
        conn.execute("UPDATE users SET trial_ends_at = ? WHERE user_id = ?", (past, UID))
    db.add_transaction(UID, "chiqim", 10_000, "transport", "taksi")
    u = _update()
    asyncio.run(bot.cmd_csv(u, _ctx()))
    assert len(u.message.documents) == 1


# ---------------------------------------------------------------- K7 --

def test_new_user_gets_try_button_and_it_saves_entry(monkeypatch):
    import bot
    db.get_or_create_user(UID, "Test", None)
    db.set_consent(UID, config.CONSENT_VERSION)
    u = _update()
    asyncio.run(bot.cmd_start(u, _ctx()))
    assert u.message.buttons() == ["try:ex"]

    fake_ai.install(monkeypatch, [{"niyat": "yozuv", "yozuvlar": [
        fake_ai.record("chiqim", 45000, "kafe va restoran", "obed",
                       sana=datetime.now(config.TZ).date().isoformat())]}])
    u = _update(data="try:ex")
    asyncio.run(bot.on_callback(u, _ctx()))
    assert db.tx_count(UID) == 1


def test_try_example_follows_language():
    import bot
    assert bot.try_example("uz") == "obedga 45 ming"
    assert bot.try_example("ru") == "обед 45 тысяч"
    assert bot.try_example("uzc") == "обедга 45 минг"


def _consented_hours_ago(uid, hours):
    db.get_or_create_user(uid, "Test", None)
    at = (datetime.now(config.TZ) - timedelta(hours=hours)).isoformat(timespec="seconds")
    with db.get_conn() as conn:
        conn.execute("UPDATE users SET consent_at = ?, consent_version = ? "
                     "WHERE user_id = ?", (at, config.CONSENT_VERSION, uid))


def test_first_entry_nudge_targets_and_runs_once():
    import bot
    _consented_hours_ago(1, 3)        # kerak
    _consented_hours_ago(2, 1)        # hali erta
    _consented_hours_ago(3, 72)       # juda eski
    _consented_hours_ago(4, 3)        # yozuvi bor
    db.add_transaction(4, "chiqim", 5000, "transport")
    db.get_or_create_user(5, "Test", None)   # rozilik yo'q
    assert [r["user_id"] for r in db.users_for_first_entry_nudge()] == [1]

    tg = Bot()
    asyncio.run(bot.job_first_entry_nudge(_ctx(tg)))
    assert [m[0] for m in tg.messages] == [1]
    markup = tg.messages[0][2]
    assert markup.inline_keyboard[0][0].callback_data == "try:ex"

    asyncio.run(bot.job_first_entry_nudge(_ctx(tg)))      # ikkinchi marta — yo'q
    assert len(tg.messages) == 1
