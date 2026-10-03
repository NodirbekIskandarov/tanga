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
