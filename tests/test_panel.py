"""«📱 Panel» tugmasi: Mini App hammaga initData bilan ochilishi kerak.

Telegram klaviatura (reply keyboard) tugmasidan ochilgan Mini App'ga
initData bermaydi, webapp.py esa har so'rovni shu imzo bilan tekshiradi.
Shuning uchun panel faqat pastki menyu tugmasidan ochadigan egada
ishlardi. Endi klaviatura tugmasi oddiy matn, bot inline web_app tugmasini
yuboradi (u initData beradi).
"""

import asyncio
from types import SimpleNamespace

import config
import db
import i18n

URL = "https://panel.example.uz"


class Message:
    def __init__(self, text="", web_app_data=None):
        self.text, self.web_app_data, self.chat_id = text, web_app_data, 1001
        self.replies = []

    async def reply_text(self, text, **kw):
        self.replies.append((text, kw.get("reply_markup")))
        return self


def _update(user_id, message):
    user = SimpleNamespace(id=user_id, first_name="Ali", username=None)
    return SimpleNamespace(effective_user=user, effective_message=message,
                           message=message, callback_query=None)


def _ctx():
    return SimpleNamespace(bot=None, user_data={}, args=[], bot_data={})


def _consent(user_id):
    db.set_consent(user_id, config.CONSENT_VERSION)


def test_keyboard_has_no_web_app_button(monkeypatch):
    """Klaviaturada web_app tugma bo'lmasligi shart — u initData'siz ochiladi."""
    import bot
    monkeypatch.setattr(config, "WEBAPP_URL", URL)
    for lang in ("uz", "uzc", "ru"):
        buttons = [b for row in bot.main_menu(lang).keyboard for b in row]
        assert all(b.web_app is None for b in buttons), lang
        assert i18n.btn(lang, "panel") in [b.text for b in buttons]


def test_panel_button_text_is_routed_in_every_language():
    import bot
    for lang in ("uz", "ru"):
        assert bot.MENU_ACTIONS[i18n.btn(lang, "panel")] is bot.cmd_open_panel


def test_panel_button_replies_with_inline_web_app(monkeypatch, user_id):
    import bot
    monkeypatch.setattr(config, "WEBAPP_URL", URL)
    _consent(user_id)
    msg = Message(i18n.btn("uz", "panel"))
    asyncio.run(bot.on_text(_update(user_id, msg), _ctx()))

    text, markup = msg.replies[-1]
    assert text == i18n.t("uz", "panel_open")
    button = markup.inline_keyboard[0][0]
    assert button.web_app is not None and button.web_app.url == URL


def test_panel_button_works_for_free_tier_user(monkeypatch, user_id):
    """Sinov muddati tugagan oddiy foydalanuvchi ham panelni ochadi
    (Bepul daraja panelda joriy oyni ko'radi)."""
    from datetime import datetime, timedelta
    import bot
    monkeypatch.setattr(config, "WEBAPP_URL", URL)
    _consent(user_id)
    past = (datetime.now(config.TZ) - timedelta(days=3)).isoformat()
    with db.get_conn() as conn:
        conn.execute("UPDATE users SET trial_ends_at = ? WHERE user_id = ?",
                     (past, user_id))
    assert db.access_status(user_id)["tier"] == "free"

    msg = Message(i18n.btn("uz", "panel"))
    asyncio.run(bot.on_text(_update(user_id, msg), _ctx()))
    assert msg.replies[-1][1].inline_keyboard[0][0].web_app.url == URL


def test_old_keyboard_web_app_data_refreshes_keyboard(monkeypatch, user_id):
    """Ekranida hali eski klaviatura qolgan odam: panel sendData("panel")
    yuboradi — bot klaviaturani yangilaydi va ishlaydigan tugmani beradi."""
    import bot
    monkeypatch.setattr(config, "WEBAPP_URL", URL)
    _consent(user_id)
    msg = Message(web_app_data=SimpleNamespace(data="panel"))
    asyncio.run(bot.on_web_app_data(_update(user_id, msg), _ctx()))

    (first, keyboard), (_, inline) = msg.replies
    assert first == i18n.t("uz", "panel_kb_updated")
    assert all(b.web_app is None for row in keyboard.keyboard for b in row)
    assert inline.inline_keyboard[0][0].web_app.url == URL


def test_unknown_web_app_data_is_ignored(monkeypatch, user_id):
    import bot
    monkeypatch.setattr(config, "WEBAPP_URL", URL)
    _consent(user_id)
    msg = Message(web_app_data=SimpleNamespace(data="boshqa"))
    asyncio.run(bot.on_web_app_data(_update(user_id, msg), _ctx()))
    assert msg.replies == []


def test_frontend_asks_bot_when_opened_without_init_data():
    """app.js: Telegram ichida initData bo'lmasa sendData("panel")."""
    from pathlib import Path
    js = (Path(__file__).resolve().parent.parent / "static" / "app.js").read_text("utf-8")
    assert 'tg.sendData("panel")' in js
