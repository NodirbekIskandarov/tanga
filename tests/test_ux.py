"""Foydalanuvchi tajribasi (2-bosqich): /start, qo'llanma, menyu."""

import re

import pytest

import config
import i18n


def _plain_lines(html: str) -> list[str]:
    return [line for line in re.sub(r"<[^>]+>", "", html).splitlines() if line.strip()]


@pytest.mark.parametrize("lang", ["uz", "uzc", "ru"])
def test_start_is_at_most_four_lines(lang):
    trial = i18n.t(lang, "trial_active", days=7) + "\n"
    text = i18n.t(lang, "welcome", name=", Ali", trial=trial)
    lines = _plain_lines(text)
    assert len(lines) <= 4
    assert "25" in text and "8" in text             # misollar
    assert lines[-1].endswith("👇")                 # bitta chaqiruv


def test_returning_user_start_is_short():
    text = i18n.t("uz", "welcome_back", name="", status=i18n.t("uz", "start_free") + "\n")
    assert len(_plain_lines(text)) <= 3


def test_main_menu_has_six_buttons_and_more(monkeypatch):
    import bot
    monkeypatch.setattr(config, "WEBAPP_URL", "https://example.uz")
    kb = bot.main_menu("uz")
    labels = [b.text for row in kb.keyboard for b in row]
    assert labels == ["📊 Bugun", "🗓 Oy", "🎯 Maqsadlar", "🤝 Qarzlar",
                      "📱 Panel", "💎 PRO", "⚙️ Yana"]

    monkeypatch.setattr(config, "WEBAPP_URL", "")
    labels = [b.text for row in bot.main_menu("uz").keyboard for b in row]
    assert "📱 Panel" not in labels and "⚙️ Yana" in labels


def test_every_menu_button_has_a_handler():
    import bot
    for key in ["today", "month", "goals", "debts", "pro", "more", *bot.MORE_MENU]:
        assert key in bot.MENU_HANDLERS, key
        for lang in ("uz", "ru"):
            assert i18n.btn(lang, key) in bot.MENU_ACTIONS


def test_more_menu_contains_the_rest():
    import bot
    assert set(bot.MORE_MENU) == {"week", "year", "recent", "longbill", "csv",
                                  "budget", "referral", "guide"}


def test_guide_is_sectioned():
    import bot
    assert len(bot.GUIDE_SECTIONS) == 14
    kb = bot.guide_menu_keyboard()
    datas = [b.callback_data for row in kb.inline_keyboard for b in row]
    assert datas == [f"g:{i}" for i in range(14)]
    for label, body in bot.GUIDE_SECTIONS:
        assert len(body) < 4000
        assert body.split()[0] == label.split()[0]   # emoji mos


def test_russian_guide_mirrors_uzbek():
    """Ruscha qo'llanma o'zbekcha bilan bir xil tuzilishda: bo'limlar soni,
    tartibi (emoji) va har bir bo'limdagi buyruqlar."""
    import re
    import bot
    assert len(bot.GUIDE_SECTIONS_RU) == len(bot.GUIDE_SECTIONS)
    for (_, uz), (label, ru) in zip(bot.GUIDE_SECTIONS, bot.GUIDE_SECTIONS_RU):
        assert uz.split()[0] == ru.split()[0] == label.split()[0]
        assert len(ru) < 4000
        # Haqiqiy buyruq: oldida harf yoki «<» yo'q («kirim/chiqim», «</b>» emas).
        cmds = lambda t: set(re.findall(r"(?<![\w<])/[a-z_]+", t))
        assert cmds(uz) <= cmds(ru), cmds(uz) - cmds(ru)
    assert "Запись" in bot.guide_menu_keyboard("ru").inline_keyboard[0][0].text
    # Kirill o'zbekcha tugmalari ham o'giriladi.
    assert bot.guide_menu_keyboard("uzc").inline_keyboard[0][0].text.endswith("Ёзиш")


def test_profile_texts_fit_telegram_limits_and_say_pro():
    """Tavsiflar Telegram chegarasiga sig'adi va «bepul + 7 kun PRO» deydi
    (bot doim bepul — «7 kun bepul» endi noto'g'ri)."""
    import profile_texts as p
    for code in p.LANGS:
        assert len(p.SHORT[code]) <= p.LIMITS["short_description"]
        assert len(p.DESCRIPTION[code]) <= p.LIMITS["description"]
        assert "PRO" in p.SHORT[code] and "PRO" in p.DESCRIPTION[code]
        assert "7 kun bepul" not in p.SHORT[code]
