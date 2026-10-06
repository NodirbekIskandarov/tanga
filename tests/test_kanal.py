"""Reklama kanallarini o'lchash (QA hisoboti K8): /start src_<kanal>."""

import asyncio
from types import SimpleNamespace

import db

UID = 7171


class Message:
    def __init__(self):
        self.text, self.chat_id, self.replies = "", UID, []

    async def reply_text(self, text, **kw):
        self.replies.append(text)
        return self


def _start(payload: str, uid: int = UID):
    import bot
    msg = Message()
    update = SimpleNamespace(
        effective_user=SimpleNamespace(id=uid, first_name="T", username=None),
        effective_message=msg, message=msg, callback_query=None)
    ctx = SimpleNamespace(bot=None, user_data={}, args=[payload] if payload else [],
                          bot_data={})
    asyncio.run(bot.cmd_start(update, ctx))


def _source(uid: int = UID):
    with db.get_conn() as conn:
        return conn.execute("SELECT source FROM users WHERE user_id = ?",
                            (uid,)).fetchone()[0]


def test_start_source_parsing():
    import bot
    assert bot.start_source("src_insta_reels") == "insta_reels"
    assert bot.start_source("src_Kanal-1") == "kanal-1"
    assert bot.start_source("src_<b>x</b>") == "bxb"              # faqat xavfsiz belgilar
    assert bot.start_source("src_" + "a" * 50) == "a" * 32
    assert bot.start_source("ref12345") == "ref"
    assert bot.start_source("pro") is None
    assert bot.start_source("src_") is None
    assert bot.start_source("") is None


def test_first_visit_records_source_before_consent():
    _start("src_tg_moliya")
    assert _source() == "tg_moliya"                 # rozilik hali yo'q
    _start("src_boshqa")                             # keyingi havola o'zgartirmaydi
    assert _source() == "tg_moliya"


def test_existing_user_is_not_attributed():
    db.get_or_create_user(UID, "T", None)            # avvaldan bor
    _start("src_reklama")
    assert _source() is None


def test_referral_marks_source_ref():
    _start("ref999")
    assert _source() == "ref"
