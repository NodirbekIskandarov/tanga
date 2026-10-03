"""Handlerlar ro'yxatga olinishi.

Telegram buyruq nomi faqat ASCII harf, raqam va pastki chiziqdan iborat
bo'la oladi; noto'g'ri nom faqat ro'yxatga olish paytida ValueError
beradi. Bir marta shunday xato jonli serverni ishga tushirmay qo'ygan.
"""

from telegram.ext import Application

import bot


def test_register_handlers_builds():
    app = Application.builder().token("123:test").build()
    bot.register_handlers(app)
    assert app.handlers


def test_bot_commands_are_ascii():
    for name, _ in bot.OWNER_COMMANDS:
        assert name.isascii() and name.replace("_", "").isalnum(), name


def test_post_init_survives_telegram_timeouts(monkeypatch):
    """Ishga tushishdagi menyu/tavsif sozlamasida Telegram javob bermasa
    (TimedOut) bot yiqilmaydi — bir marta jonli botda shunday bo'lgan."""
    import asyncio
    from types import SimpleNamespace
    from telegram.error import TimedOut

    import config

    async def fail(*args, **kwargs):
        raise TimedOut()

    fake_bot = SimpleNamespace(
        set_my_commands=fail, delete_my_commands=fail, get_my_description=fail,
        set_my_description=fail, get_my_short_description=fail,
        set_my_short_description=fail, set_chat_menu_button=fail)
    monkeypatch.setattr(config, "WEBAPP_URL", "https://example.uz")
    monkeypatch.setattr(config, "OWNER_IDS", {1})
    asyncio.run(bot._post_init(SimpleNamespace(bot=fake_bot)))
