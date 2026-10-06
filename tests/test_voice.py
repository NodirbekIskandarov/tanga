"""Ovozli kiritish: handler, darvozalar, limitlar, tasdiq oqimi, maxfiylik.

Haqiqiy handlerlar soxta Telegram obyektlari va soxta Gemini (tests/fake_ai.py)
bilan chaqiriladi. Audio sifati — jonli test (tests/live_voice/).
"""

import asyncio
import builtins
import pathlib
import tempfile
from datetime import date
from types import SimpleNamespace

import pytest

import ai
import bot
import config
import db
import i18n
import reports
from tests import fake_ai

UID = 3001
OWNER = 3999
TODAY = date.today().isoformat()


class Msg:
    def __init__(self):
        self.replies = []
        self.chat_id = UID
        self.text = ""

    async def reply_text(self, text, **kw):
        self.replies.append((text, kw.get("reply_markup")))
        return self

    @property
    def last(self):
        return self.replies[-1][0]

    @property
    def main(self):
        """Asosiy javob — birinchi xabar (keyingilari: nishonlash, taklif)."""
        return self.replies[0][0]

    @property
    def buttons(self):
        markup = self.replies[0][1]
        return [b.callback_data for row in markup.inline_keyboard for b in row] if markup else []


class Telegram:
    """context.bot: get_file va download_as_bytearray; yuklab olingan baytlar."""

    def __init__(self, data=b"OGG-AUDIO-BAYTLARI"):
        self.data = data
        self.downloaded = 0
        self.messages = []

    async def get_file(self, file_id):
        outer = self

        class F:
            async def download_as_bytearray(self):
                outer.downloaded += 1
                return bytearray(outer.data)
        return F()

    async def send_chat_action(self, *a, **kw):
        pass

    async def send_message(self, chat_id, text, **kw):
        self.messages.append((chat_id, text))


def voice_media(duration=5, size=20_000, mime="audio/ogg"):
    return SimpleNamespace(file_id="f1", duration=duration, file_size=size, mime_type=mime)


def update_for(uid=UID, voice=None, audio=None, data=None):
    msg = Msg()
    msg.voice, msg.audio = voice, audio
    user = SimpleNamespace(id=uid, first_name="Ali", username=None)
    query = None
    if data:
        query = SimpleNamespace(data=data, message=msg, answers=[],
                                edits=[], markup_cleared=0)

        async def answer(text=None, **kw):
            query.answers.append(text)

        async def edit_markup(markup=None, **kw):
            query.markup_cleared += 1

        async def edit_text(text, **kw):
            query.edits.append(text)

        query.answer, query.edit_message_reply_markup = answer, edit_markup
        query.edit_message_text = edit_text
    upd = SimpleNamespace(effective_user=user, effective_message=msg, message=msg,
                          effective_chat=SimpleNamespace(type="private", id=uid),
                          callback_query=query)
    return upd, msg


def context(tg=None):
    return SimpleNamespace(bot=tg or Telegram(), user_data={}, args=[], bot_data={})


@pytest.fixture(autouse=True)
def setup(monkeypatch):
    monkeypatch.setattr(config, "VOICE_ENABLED", True)
    monkeypatch.setattr(config, "VOICE_BETA_USER_IDS", set())
    monkeypatch.setattr(config, "OWNER_IDS", {OWNER})
    bot._voice_pending._data.clear()
    bot._collect._data.clear()
    bot._erase_typed._data.clear()
    for uid in (UID, OWNER):
        db.get_or_create_user(uid, "Ali", None)
        db.set_consent(uid, config.CONSENT_VERSION)
    yield
    reports.set_lang(None)


def run_voice(monkeypatch, payloads, *, uid=UID, voice=None, ctx=None, lang=None):
    if lang:
        db.set_lang(uid, lang)
    fake = fake_ai.install(monkeypatch, payloads)
    upd, msg = update_for(uid, voice=voice or voice_media())
    ctx = ctx or context()
    asyncio.run(bot.on_voice(upd, ctx))
    return fake, msg, upd, ctx


def record(kind="chiqim", amount=45_000, cat="kafe va restoran", note="obed", **kw):
    return fake_ai.record(kind, amount, cat, note, sana=TODAY, **kw)


# ----------------------------------------------------------- yuqori ishonch --

def test_confident_voice_saves_entries_and_shows_transcript(monkeypatch):
    fake, msg, _, _ = run_voice(monkeypatch, [fake_ai.voice(
        "obedga 45 ming, taksiga 20 ming",
        [record(), record(amount=20_000, cat="transport", note="taksi")])])
    text = msg.main
    assert text.startswith("🎤 <i>«obedga 45 ming, taksiga 20 ming»</i>")
    assert "2 ta yozuv saqlandi" in text
    assert db.tx_count(UID) == 2
    rows = db.recent_entries(UID, 5)
    assert all(db.get_transaction(UID, r["id"])["raw_text"]
               == "🎤 obedga 45 ming, taksiga 20 ming" for r in rows)
    assert fake.calls[0]["model"] == config.VOICE_MODEL
    assert fake.calls[0]["parts"][-1]["type"] == "audio"
    assert fake.calls[0]["parts"][-1]["mime_type"] == "audio/ogg"
    assert db.count_today(UID, "ovoz") == 1


def test_confident_single_entry_has_same_buttons_as_text(monkeypatch):
    _, msg, _, _ = run_voice(monkeypatch, [fake_ai.voice("obedga 45 ming", [record()])])
    assert any(b.startswith("c:") for b in msg.buttons)      # ✏️ Kategoriya
    assert any(b.startswith("d:") for b in msg.buttons)      # 🗑 O'chirish
    assert "Bugungi chiqim" in msg.main


def test_voice_text_is_html_escaped(monkeypatch):
    _, msg, _, _ = run_voice(monkeypatch, [fake_ai.voice("<b>45</b> & ming", [record()])])
    assert "&lt;b&gt;45&lt;/b&gt; &amp; ming" in msg.main


# ------------------------------------------------------------- past ishonch --

def test_low_confidence_asks_confirmation_and_saves_nothing(monkeypatch):
    _, msg, _, _ = run_voice(monkeypatch, [fake_ai.voice(
        "obedga qirq... ming", [record()], ishonch="past")])
    assert db.tx_count(UID) == 0
    assert "Shunday tushundim" in msg.main and "45 000" in msg.main
    assert [b.split(":")[1] for b in msg.buttons] == ["ok", "no", "txt"]
    assert len(bot._voice_pending._data) == 1


def _pending_token(msg):
    return msg.buttons[0].split(":")[2]


def test_confirm_saves_once_cancel_and_text_do_not(monkeypatch):
    for action, saved in (("ok", 1), ("no", 0), ("txt", 0)):
        db.erase_user(UID)
        db.get_or_create_user(UID, "Ali", None)
        db.set_consent(UID, config.CONSENT_VERSION)
        _, msg, _, ctx = run_voice(monkeypatch, [fake_ai.voice(
            "obedga 45 ming", [record()], ishonch="past")])
        token = _pending_token(msg)
        upd, cmsg = update_for(data=f"vs:{action}:{token}")
        asyncio.run(bot.on_voice_callback(upd, ctx))
        assert db.tx_count(UID) == saved, action
        assert upd.callback_query.markup_cleared == 1
        if action == "ok":
            assert "saqlandi" in cmsg.last.lower()
            # Ikkinchi bosish — token ishlatilgan
            upd2, _ = update_for(data=f"vs:ok:{token}")
            asyncio.run(bot.on_voice_callback(upd2, ctx))
            assert upd2.callback_query.answers[-1] == i18n.t("uz", "voice_expired")
            assert db.tx_count(UID) == 1
        elif action == "no":
            assert "Hech narsa saqlanmadi" in cmsg.last
        else:
            assert "obedga 45 ming" in cmsg.last          # misol ko'rsatildi


def test_expired_or_foreign_token_is_rejected(monkeypatch):
    ctx = context()
    upd, _ = update_for(data="vs:ok:yoq-token")
    asyncio.run(bot.on_voice_callback(upd, ctx))
    assert upd.callback_query.answers[-1] == i18n.t("uz", "voice_expired")
    assert db.tx_count(UID) == 0

    _, msg, _, _ = run_voice(monkeypatch, [fake_ai.voice(
        "obedga 45 ming", [record()], ishonch="past")])
    token = _pending_token(msg)
    db.get_or_create_user(OWNER + 1, "Boshqa", None)
    upd2, _ = update_for(uid=OWNER + 1, data=f"vs:ok:{token}")
    asyncio.run(bot.on_voice_callback(upd2, ctx))
    assert db.tx_count(UID) == 0 and db.tx_count(OWNER + 1) == 0


def test_large_amount_forces_confirmation(monkeypatch):
    big = record(kind="kirim", amount=config.VOICE_CONFIRM_ABOVE_SOM + 1, cat="oylik",
                 note="oylik")
    _, msg, _, _ = run_voice(monkeypatch, [fake_ai.voice("oylik 6 mln", [big])])
    assert db.tx_count(UID) == 0 and "Shunday tushundim" in msg.main


def test_large_usd_and_many_entries_force_confirmation(monkeypatch):
    usd = fake_ai.record("chiqim", config.VOICE_CONFIRM_ABOVE_USD + 1, "boshqa chiqim",
                         "x", sana=TODAY, valyuta="usd")
    _, msg, _, _ = run_voice(monkeypatch, [fake_ai.voice("600 dollar", [usd])])
    assert db.tx_count(UID) == 0

    many = [record(amount=1_000 + i) for i in range(6)]
    _, msg, _, _ = run_voice(monkeypatch, [fake_ai.voice("ko'p", many)])
    assert db.tx_count(UID) == 0 and "Shunday tushundim" in msg.main


def test_ai_layer_forces_low_confidence_itself(monkeypatch):
    """Majburiy tasdiq model javobiga emas, ai.parse_voice ga bog'liq."""
    fake_ai.install(monkeypatch, [fake_ai.voice(
        "x", [record(amount=9_000_000)], ishonch="yuqori")])
    out = asyncio.run(ai.parse_voice(b"a", "audio/ogg", today=date.today()))
    assert out["ishonch"] == "past"
    fake_ai.install(monkeypatch, [fake_ai.voice("x", [record(amount=9_000)])])
    assert asyncio.run(ai.parse_voice(b"a", "audio/ogg"))["ishonch"] == "yuqori"


# ------------------------------------------------------------- savol, kurs --

def test_voice_question_goes_through_qa(monkeypatch):
    db.add_transaction(UID, "chiqim", 10_000, "transport", "taksi", occurred_on=TODAY)
    fake, msg, _, _ = run_voice(monkeypatch, [
        fake_ai.voice("bu oy qancha sarfladim?", niyat="savol"),
        {"text": "Bu oy 10 000 so'm sarfladingiz."}])
    assert msg.main.startswith("🎤 <i>«bu oy qancha sarfladim?»</i>")
    assert "10 000 so'm sarfladingiz" in msg.main
    assert fake.calls[1]["kind"] == "text"
    assert "Savol: bu oy qancha sarfladim?" in fake.calls[1]["content"]
    assert db.count_today(UID, "savol") == 1 and db.count_today(UID, "ovoz") == 1


def test_unclear_voice_shows_hint_and_saves_nothing(monkeypatch):
    _, msg, _, _ = run_voice(monkeypatch, [fake_ai.voice(
        "", niyat="tushunarsiz", izoh_matni="Ovoz juda past eshitildi")])
    assert "Ovoz juda past eshitildi" in msg.main and db.tx_count(UID) == 0
    _, msg, _, _ = run_voice(monkeypatch, [fake_ai.voice("hmm", niyat="tushunarsiz")])
    assert "Ovozni tushunib bo'lmadi" in msg.main


def test_voice_goal_text_is_used_for_pending_goal(monkeypatch):
    calls = []

    async def fake_goal(update, ctx, text):
        calls.append(text)

    monkeypatch.setattr(bot, "create_goal_from_text", fake_goal)
    ctx = context()
    ctx.user_data["await_goal"] = True
    run_voice(monkeypatch, [fake_ai.voice("uy uchun 300 mln 2028 mart", niyat="tushunarsiz")],
              ctx=ctx)
    assert calls == ["uy uchun 300 mln 2028 mart"]
    assert "await_goal" not in ctx.user_data and db.tx_count(UID) == 0


# ---------------------------------------------------------------- darvozalar --

def test_too_long_voice_is_not_downloaded(monkeypatch):
    tg = Telegram()
    fake, msg, _, _ = run_voice(monkeypatch, [], voice=voice_media(duration=61),
                                ctx=context(tg))
    assert tg.downloaded == 0 and fake.calls == []
    assert "60 soniyadan oshmasin" in msg.main
    assert db.count_today(UID, "ovoz") == 0


def test_too_big_voice_is_not_downloaded(monkeypatch):
    tg = Telegram()
    fake, msg, _, _ = run_voice(monkeypatch, [], voice=voice_media(size=3_000_000),
                                ctx=context(tg))
    assert tg.downloaded == 0 and "soniyadan oshmasin" in msg.main


def test_disabled_flag_and_beta_list(monkeypatch):
    monkeypatch.setattr(config, "VOICE_ENABLED", False)
    fake, msg, _, _ = run_voice(monkeypatch, [])
    assert "tez orada" in msg.main and fake.calls == []

    monkeypatch.setattr(config, "VOICE_ENABLED", True)
    monkeypatch.setattr(config, "VOICE_BETA_USER_IDS", {12345})
    fake, msg, _, _ = run_voice(monkeypatch, [])
    assert "tez orada" in msg.main                          # beta ro'yxatda yo'q
    _, msg, _, _ = run_voice(monkeypatch, [fake_ai.voice("obed 45 ming", [record()])],
                             uid=OWNER)
    assert "saqlandi" in msg.main                           # ega har doim kiradi
    monkeypatch.setattr(config, "VOICE_BETA_USER_IDS", {UID})
    _, msg, _, _ = run_voice(monkeypatch, [fake_ai.voice("obed 45 ming", [record()])])
    assert "saqlandi" in msg.main


def test_no_consent_asks_consent_and_does_not_call_ai(monkeypatch):
    db.get_or_create_user(UID + 7, "Yangi", None)           # rozilik yo'q
    fake, msg, _, _ = run_voice(monkeypatch, [], uid=UID + 7)
    assert fake.calls == [] and db.tx_count(UID + 7) == 0
    assert db.count_today(UID + 7, "ovoz") == 0


def test_erase_confirmation_cannot_be_given_by_voice(monkeypatch):
    bot._erase_typed.set(UID, True)
    fake, msg, _, _ = run_voice(monkeypatch, [])
    assert "ovoz bilan tasdiqlanmaydi" in msg.main and fake.calls == []
    assert bot._erase_typed.get(UID)                        # holat saqlanadi


def test_long_receipt_mode_rejects_voice(monkeypatch):
    bot._collect.set(UID, {"images": [], "caption": ""})
    fake, msg, _, _ = run_voice(monkeypatch, [])
    assert "Uzun chek rejimida ovoz qabul qilinmaydi" in msg.main and fake.calls == []


def test_audio_file_and_unsupported_format(monkeypatch):
    upd, msg = update_for(audio=voice_media(mime="audio/mpeg"))
    fake = fake_ai.install(monkeypatch, [fake_ai.voice("obed 45 ming", [record()])])
    asyncio.run(bot.on_voice(upd, context()))
    assert fake.calls[0]["parts"][-1]["mime_type"] == "audio/mpeg"

    upd, msg = update_for(audio=voice_media(mime="video/x-matroska"))
    fake = fake_ai.install(monkeypatch, [])
    asyncio.run(bot.on_voice(upd, context()))
    assert "formati qo'llab-quvvatlanmaydi" in msg.main and fake.calls == []


def test_video_note_is_politely_declined():
    upd, msg = update_for()
    asyncio.run(bot.on_video_note(upd, context()))
    assert msg.main == i18n.t("uz", "voice_video_note")


# ----------------------------------------------------------------- limitlar --

def _spend(uid, n):
    for _ in range(n):
        db.usage_finish(db.usage_begin(uid, "ovoz"), fake_ai.usage_for(config.VOICE_MODEL))


def test_free_user_daily_limit_shows_paywall(monkeypatch):
    with db.get_conn() as conn:                            # sinov tugagan: Bepul
        conn.execute("UPDATE users SET trial_ends_at = ? WHERE user_id = ?",
                     ("2000-01-01T00:00:00+05:00", UID))
    assert db.access_status(UID)["tier"] == "free"
    _spend(UID, config.FREE_VOICE_PER_DAY)
    fake, msg, _, _ = run_voice(monkeypatch, [])
    assert fake.calls == []
    assert "bepul ovozli xabar ishlatildi" in msg.main
    assert any(b.startswith("pro:") for b in msg.buttons)


def test_pro_daily_limit_is_fair_use_message(monkeypatch):
    assert db.access_status(UID)["tier"] == "pro"           # sinov — to'liq PRO
    _spend(UID, config.LIMIT_VOICE_PER_DAY)
    fake, msg, _, _ = run_voice(monkeypatch, [])
    assert fake.calls == [] and "kunlik chegara" in msg.main
    assert "ovozli xabar yuborildi" in msg.main


def test_owner_has_no_voice_limit(monkeypatch):
    _spend(OWNER, config.LIMIT_VOICE_PER_DAY + 5)
    _, msg, _, _ = run_voice(monkeypatch, [fake_ai.voice("obed 45 ming", [record()])],
                             uid=OWNER)
    assert "saqlandi" in msg.main


# ---------------------------------------------------------- xato va maxfiylik --

def test_ai_failure_cancels_usage_and_reports(monkeypatch):
    fake, msg, _, _ = run_voice(monkeypatch, [RuntimeError("boom")])
    assert "Birozdan keyin" in msg.main
    assert db.count_today(UID, "ovoz") == 0                 # joy qaytarildi
    assert db.tx_count(UID) == 0


def test_download_failure_cancels_usage(monkeypatch):
    class Broken(Telegram):
        async def get_file(self, file_id):
            raise RuntimeError("tarmoq")

    fake, msg, _, _ = run_voice(monkeypatch, [], ctx=context(Broken()))
    assert fake.calls == [] and db.count_today(UID, "ovoz") == 0
    assert "yuklab olishda xatolik" in msg.main


def test_usage_is_recorded_with_audio_tokens(monkeypatch):
    run_voice(monkeypatch, [fake_ai.voice("obed 45 ming", [record()])])
    with db.get_conn() as conn:
        row = conn.execute("SELECT model, input_tokens, cost_usd FROM usage_log "
                           "WHERE operation = 'ovoz'").fetchone()
    assert row["model"] == config.VOICE_MODEL and row["input_tokens"] == 100
    assert row["cost_usd"] > 0


def test_events_are_logged(monkeypatch):
    run_voice(monkeypatch, [fake_ai.voice("obed", [record()], ishonch="past")])
    run_voice(monkeypatch, [], voice=voice_media(duration=999))
    with db.get_conn() as conn:
        names = [r["name"] for r in conn.execute(
            "SELECT name FROM events WHERE user_id = ?", (UID,)).fetchall()]
    assert {"ovoz_yuborildi", "ovoz_tasdiq_soraldi", "ovoz_rad"} <= set(names)


def test_audio_bytes_never_touch_disk_or_database(monkeypatch, tmp_path):
    secret = b"MAXFIY-OVOZ-BAYTLARI-0123456789"
    writes = []
    real_open = builtins.open

    def spy_open(file, mode="r", *a, **kw):
        if any(c in mode for c in "wax+"):
            writes.append(str(file))
        return real_open(file, mode, *a, **kw)

    monkeypatch.setattr(builtins, "open", spy_open)
    monkeypatch.setattr(pathlib.Path, "write_bytes",
                        lambda self, data: writes.append(("write_bytes", str(self))))
    monkeypatch.setattr(tempfile, "NamedTemporaryFile",
                        lambda *a, **k: (_ for _ in ()).throw(AssertionError("temp fayl")))
    fake, msg, _, _ = run_voice(
        monkeypatch, [fake_ai.voice("obed 45 ming", [record()])],
        ctx=context(Telegram(data=secret)))
    assert [w for w in writes if "tanga" in str(w).lower() or "voice" in str(w).lower()] == []
    # Baza va javob matnida audio yo'q; faqat transkripsiya yozilgan.
    with db.get_conn() as conn:
        dump = " ".join(str(tuple(r)) for r in conn.execute(
            "SELECT raw_text, note FROM transactions").fetchall())
    assert "MAXFIY" not in dump and "🎤 obed 45 ming" in dump
    assert "MAXFIY" not in msg.main
    # Gemini'ga audio base64 sifatida ketdi (xotiradan)
    import base64
    assert fake.calls[0]["parts"][-1]["data"] == base64.b64encode(secret).decode()


def test_voice_audio_not_in_logs(monkeypatch, caplog):
    import logging
    caplog.set_level(logging.DEBUG)
    run_voice(monkeypatch, [RuntimeError("xato")], ctx=context(Telegram(data=b"MAXFIY-BAYT")))
    assert "MAXFIY" not in caplog.text


# --------------------------------------------------------------------- ruscha --

def test_russian_user_gets_russian_texts_everywhere(monkeypatch):
    db.set_lang(UID, "ru")
    ctx = context()

    async def run():
        upd, msg = update_for(voice=voice_media(duration=999))
        await bot._private_chat_guard(upd, ctx)
        await bot.on_voice(upd, ctx)
        return msg

    msg = asyncio.run(run())
    assert "не должно быть длиннее 60 секунд" in msg.main

    _, msg, _, ctx2 = run_voice(monkeypatch, [fake_ai.voice(
        "обед 45 тысяч", [record()], ishonch="past", til="ru")], lang="ru")
    assert "Я понял так" in msg.main
    labels = [b.text for row in msg.replies[0][1].inline_keyboard for b in row]
    assert labels == ["✅ Сохранить", "❌ Отмена", "✏️ Напишу текстом"]

    monkeypatch.setattr(config, "VOICE_ENABLED", False)
    _, msg, _, _ = run_voice(monkeypatch, [], lang="ru")
    assert msg.main == "Голосовой ввод скоро появится. Пока пишите текстом."


def test_every_voice_text_exists_in_both_languages():
    keys = [k for k in i18n.T if k.startswith("voice_") or k in (
        "what_ovoz", "feature_voice", "paywall_voice", "welcome_voice")]
    assert len(keys) >= 17
    for k in keys:
        assert i18n.T[k].get("uz") and i18n.T[k].get("ru"), k


def test_welcome_mentions_voice_only_when_available(monkeypatch):
    assert bot.voice_available(UID)
    monkeypatch.setattr(config, "VOICE_ENABLED", False)
    assert not bot.voice_available(UID) and not bot.voice_available(OWNER)
    monkeypatch.setattr(config, "VOICE_ENABLED", True)
    monkeypatch.setattr(config, "VOICE_BETA_USER_IDS", {5})
    assert not bot.voice_available(UID) and bot.voice_available(5) and bot.voice_available(OWNER)


def test_handlers_are_registered():
    from telegram.ext import Application, MessageHandler
    app = Application.builder().token("123:test").build()
    bot.register_handlers(app)
    callbacks = [h.callback for hs in app.handlers.values() for h in hs
                 if isinstance(h, MessageHandler)]
    assert bot.on_voice in callbacks and bot.on_video_note in callbacks
