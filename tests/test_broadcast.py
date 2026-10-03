"""/xabar_yubor (4.6): tasdiqsiz hech narsa yuborilmaydi."""

import asyncio
from types import SimpleNamespace

import config
import db
import tiers

OWNER = 900


class FakeBot:
    def __init__(self):
        self.sent = []

    async def send_message(self, chat_id, text, **kw):
        self.sent.append((chat_id, text))


class FakeMessage:
    def __init__(self, text=""):
        self.text = text
        self.replies = []

    async def reply_text(self, text, **kw):
        self.replies.append((text, kw.get("reply_markup")))
        return self


class FakeQuery:
    def __init__(self, data, message):
        self.data = data
        self.message = message
        self.answers = []

    async def answer(self, text=None, **kw):
        self.answers.append(text)

    async def edit_message_reply_markup(self, markup):
        pass


def _ctx(bot):
    tasks = []
    app = SimpleNamespace(create_task=lambda coro: tasks.append(coro))
    return SimpleNamespace(bot=bot, bot_data={}, application=app, _tasks=tasks)


def _update(text="", data=None):
    msg = FakeMessage(text)
    return SimpleNamespace(effective_user=SimpleNamespace(id=OWNER),
                           effective_message=msg,
                           callback_query=FakeQuery(data, msg) if data else None)


def _active_user(uid, consent=True):
    db.get_or_create_user(uid)
    if consent:
        db.set_consent(uid, config.CONSENT_VERSION)
    db.add_transaction(uid, "chiqim", 1_000, "oziq-ovqat", "non",
                       occurred_on=tiers.today().isoformat())


def test_audience_is_recent_consented_unblocked(monkeypatch):
    monkeypatch.setattr(config, "OWNER_IDS", {OWNER})
    _active_user(1)
    _active_user(2, consent=False)
    _active_user(3)
    db.set_blocked(3, True)
    _active_user(OWNER)
    assert db.broadcast_audience() == [1]


def test_nothing_is_sent_until_double_confirmation(monkeypatch):
    import broadcast
    monkeypatch.setattr(config, "OWNER_IDS", {OWNER})
    for uid in (1, 2):
        _active_user(uid)
    bot = FakeBot()
    ctx = _ctx(bot)

    asyncio.run(broadcast.cmd_broadcast(_update("/xabar_yubor"), ctx))
    assert bot.sent == []                                  # faqat ko'rinish

    asyncio.run(broadcast.on_broadcast_callback(_update(data="bc:test"), ctx))
    assert [c for c, _ in bot.sent] == [OWNER]             # faqat egaga

    asyncio.run(broadcast.on_broadcast_callback(_update(data="bc:ask"), ctx))
    assert [c for c, _ in bot.sent] == [OWNER]             # hali yo'q
    assert ctx._tasks == []

    asyncio.run(broadcast.on_broadcast_callback(_update(data="bc:send"), ctx))
    asyncio.run(ctx._tasks[0])
    recipients = [c for c, _ in bot.sent]
    assert sorted(recipients[1:3]) == [1, 2]
    assert recipients[-1] == OWNER                         # hisobot
    assert "Asoschilar taklifi" in bot.sent[1][1]


def test_cancel_drops_draft(monkeypatch):
    import broadcast
    monkeypatch.setattr(config, "OWNER_IDS", {OWNER})
    _active_user(1)
    bot = FakeBot()
    ctx = _ctx(bot)
    asyncio.run(broadcast.cmd_broadcast(_update("/xabar_yubor Salom"), ctx))
    asyncio.run(broadcast.on_broadcast_callback(_update(data="bc:cancel"), ctx))
    asyncio.run(broadcast.on_broadcast_callback(_update(data="bc:send"), ctx))
    assert ctx._tasks == [] and bot.sent == []


def test_non_owner_cannot_trigger(monkeypatch):
    import broadcast
    monkeypatch.setattr(config, "OWNER_IDS", set())
    bot = FakeBot()
    ctx = _ctx(bot)
    ctx.bot_data["broadcast"] = {OWNER: {"custom": "x", "ids": [1], "created": 1e18,
                                         "sending": False}}
    asyncio.run(broadcast.on_broadcast_callback(_update(data="bc:send"), ctx))
    assert ctx._tasks == []
