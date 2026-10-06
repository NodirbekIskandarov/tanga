"""K11: rus tili to'liq — hisobotlar, nomlar, sana va summa formatlari."""

import re
from datetime import date

import config
import db
import i18n
import reports

# Ruscha matnda qolib ketmasligi kerak bo'lgan o'zbekcha so'zlar.
UZ_LEFTOVERS = re.compile(
    r"\b(so'm|Kirim|Chiqim|Farq|Qarz|qoldiq|yozuv|mahsulot|Bugun|Kecha|oyi|"
    r"kategoriya|saqlandi|to'langan|jami|Chek qabul)\b", re.I)


def _no_uzbek(text: str) -> None:
    left = UZ_LEFTOVERS.findall(text)
    assert not left, f"o'zbekcha qoldiq: {left}\n{text}"


def _seed(user_id):
    d = date.today().isoformat()
    add = lambda kind, amount, cat, **kw: db.add_transaction(
        user_id, kind, amount, cat, kw.pop("note", "x"), occurred_on=d, **kw)
    add("chiqim", 500_000, "oziq-ovqat", note="non")
    add("chiqim", 80_000, "transport")
    add("kirim", 8_000_000, "oylik")
    add("jamgarma", 900_000, "jamg'arma")
    add("qarz_berdim", 200_000, "qarz", person="Akmal")
    add("qarz_oldim", 100_000, "qarz", person="Bobur")


# ------------------------------------------------------------ nomlar ----

def test_every_category_and_kind_has_a_russian_name():
    assert set(i18n.CATEGORY_RU) == set(config.ALL_CATEGORIES)
    assert set(i18n.KIND_RU) == set(config.KIND_LABELS)
    for name in config.ALL_CATEGORIES:
        assert re.search("[а-я]", i18n.category_name("ru", name)), name


def test_category_name_by_language():
    assert i18n.category_name("uz", "oziq-ovqat") == "oziq-ovqat"
    assert i18n.category_name("ru", "oziq-ovqat") == "продукты"
    assert i18n.category_name("uzc", "oziq-ovqat") == "озиқ-овқат"
    assert i18n.category_name("uz", "oylik") == "ish haqi"       # eski nom saqlanadi


def test_money_and_dates_follow_language():
    assert reports.fmt_money(1_250_000, lang="uz") == "1 250 000 so'm"
    assert reports.fmt_money(1_250_000, lang="ru") == "1 250 000 сум"
    assert reports.fmt_money(1_250_000, lang="uzc") == "1 250 000 сўм"
    assert reports.fmt_money(99.5, "usd", lang="ru") == "$99.5"
    assert reports.fmt_date("2026-10-06", "uz") == "6-oktabr"
    assert reports.fmt_date("2026-10-06", "ru") == "6 октября"
    assert reports.fmt_date("2026-10-06", "uzc") == "6-октабр"


def test_russian_plural():
    word = lambda n: reports._plural(n, "товар", "товара", "товаров")
    assert [word(n) for n in (1, 2, 5, 11, 12, 21, 22, 25, 111)] == [
        "товар", "товара", "товаров", "товаров", "товаров", "товар", "товара",
        "товаров", "товаров"]


def test_period_titles_in_russian():
    ref = date(2026, 10, 6)
    assert reports.period_range("bugun", ref, "ru")[2] == "Сегодня"
    assert reports.period_range("oy", ref, "ru")[2] == "Октябрь"
    assert reports.period_range("oy", ref, "uz")[2] == "Oktabr oyi"
    assert reports.period_range("yil", ref, "ru")[2] == "2026 год"
    assert reports.period_range("otgan_oy", ref, "ru")[2] == "Сентябрь"


# --------------------------------------------------------- hisobotlar ----

def test_summary_is_russian_for_ru_user(user_id):
    _seed(user_id)
    text = reports.summary_text(user_id, "oy", "ru")
    _no_uzbek(text)
    assert "Доход:" in text and "Расход:" in text and "Разница:" in text
    assert "продукты" in text and "сум" in text
    assert "Накопления" in text and "Долги" in text and "Дал в долг" in text
    assert "Оценка месяца" in text


def test_summary_keeps_uzbek_by_default(user_id):
    _seed(user_id)
    text = reports.summary_text(user_id, "oy")
    assert "Kirim:" in text and "oziq-ovqat" in text and "so'm" in text
    assert "Oylik baho" in text


def test_summary_cyrillic_uzbek_is_not_latin_any_more(user_id):
    _seed(user_id)
    text = reports.summary_text(user_id, "oy", "uzc")
    assert "Кирим:" in text and "Chiqim" not in text and "so'm" not in text


def test_empty_period_and_recent_in_russian(user_id):
    assert "записей нет" in reports.summary_text(user_id, "kecha", "ru")
    assert reports.recent_text(user_id, lang="ru") == "Записей пока нет."
    assert reports.debts_text(user_id, lang="ru") == "🤝 Открытых долгов нет."


def test_recent_and_debts_in_russian(user_id):
    _seed(user_id)
    recent = reports.recent_text(user_id, lang="ru")
    _no_uzbek(recent.replace("/ochir", ""))
    assert "Последние 6 записей" in recent
    debts = reports.debts_text(user_id, lang="ru")
    _no_uzbek(debts)
    assert "Должны мне" in debts and "Я должен" in debts and "остаток" in debts


def test_receipt_and_saved_text_in_russian():
    data = {
        "dokon": "Korzinka", "sana": "2026-10-05", "valyuta": "som", "chegirma": 0,
        "mahsulotlar": [
            {"nomi": "non", "summa": 10_000, "kategoriya": "oziq-ovqat"},
            {"nomi": "sovun", "summa": 20_000, "kategoriya": "uy-ro'zg'or va gigiyena"},
        ],
        "tekshiruv": {"holat": "farqli", "chekdagi": 31_000, "hisoblangan": 30_000,
                      "farq": -1_000},
    }
    text = reports.receipt_text(data, 55_000, "ru")
    _no_uzbek(text)
    assert "2 товара" in text and "Итого в чеке" in text and "меньше" in text
    assert "хозтовары и гигиена" in text

    rows = [{"turi": "chiqim", "summa": 8_000, "valyuta": "som",
             "kategoriya": "oziq-ovqat", "izoh": "nonga", "sana": "2026-10-05"}]
    one = reports.saved_text(rows, "ru")
    _no_uzbek(one)
    assert "Расход" in one and "сохранено" in one and "5 октября" in one
    many = reports.saved_text(rows * 3, "ru")
    _no_uzbek(many)
    assert "3 записи сохранены" in many


def test_user_text_is_never_transliterated():
    """Izoh va ism — foydalanuvchi matni: kirillga o'girilmaydi."""
    rows = [{"turi": "qarz_berdim", "summa": 8_000, "valyuta": "som",
             "kategoriya": "qarz", "izoh": "kitob uchun", "shaxs": "Akmal",
             "sana": "2026-10-05"}]
    text = reports.saved_text(rows, "uzc")
    assert "Akmal" in text and "kitob uchun" in text


def test_report_language_follows_context():
    reports.set_lang("ru")
    try:
        assert reports.fmt_money(1000) == "1 000 сум"
        assert reports.fmt_money(1000, lang="uz") == "1 000 so'm"   # aniq til ustun
    finally:
        reports.set_lang(None)
    assert reports.fmt_money(1000) == "1 000 so'm"


# ------------------------------------------------------------ bot qatlami --

import asyncio
from types import SimpleNamespace

import bot


def _ru_user(uid=2001):
    db.get_or_create_user(uid, "Иван", None)
    db.set_consent(uid, config.CONSENT_VERSION)
    db.set_lang(uid, "ru")
    return uid


class _Msg:
    def __init__(self):
        self.replies = []
        self.chat_id = 1

    async def reply_text(self, text, **kw):
        self.replies.append((text, kw.get("reply_markup")))
        return self


def _upd(uid, msg=None):
    msg = msg or _Msg()
    user = SimpleNamespace(id=uid, first_name="Иван", username=None)
    chat = SimpleNamespace(type="private", id=uid)
    return SimpleNamespace(effective_user=user, effective_message=msg, message=msg,
                           effective_chat=chat, callback_query=None), msg


def test_guard_sets_report_language_for_the_update():
    uid = _ru_user()
    update, _ = _upd(uid)
    ctx = SimpleNamespace(bot=None, user_data={}, args=[], bot_data={})
    async def run():
        await bot._private_chat_guard(update, ctx)
        return reports.fmt_money(1000)          # xuddi shu vazifa ichida

    assert asyncio.run(run()) == "1 000 сум"
    assert reports.fmt_money(1000) == "1 000 so'm"   # tashqariga sizib chiqmaydi


def test_keyboards_follow_language():
    reports.set_lang("ru")
    try:
        labels = [b.text for row in bot.entry_keyboard([5], "qarz_berdim").inline_keyboard
                  for b in row]
        assert "✏️ Категория" in labels and "🗑 Удалить" in labels
        assert "📅 Срок возврата" in labels
        cats = [b.text for row in bot.category_keyboard(5, "chiqim").inline_keyboard
                for b in row]
        assert any("продукты" in c for c in cats) and "⬅️ Отмена" in cats
        receipt = [b.text for row in bot.receipt_keyboard("abc").inline_keyboard
                   for b in row]
        assert receipt == ["📋 Полный список", "➕ Продолжение чека", "🗑 Удалить чек"]
        multi = bot.entry_keyboard([5, 6], None, [
            {"summa": 8000, "valyuta": "som", "izoh": "non", "kategoriya": "oziq-ovqat"},
            {"summa": 9000, "valyuta": "som", "izoh": "", "kategoriya": "transport"}])
        texts = [b.text for row in multi.inline_keyboard for b in row]
        assert "сум" in texts[0] and "транспорт" in texts[1]
    finally:
        reports.set_lang(None)
    labels = [b.text for row in bot.entry_keyboard([5], "chiqim").inline_keyboard
              for b in row]
    assert "✏️ Kategoriya" in labels and "🗑 O'chirish" in labels


def test_period_report_command_replies_in_russian():
    uid = _ru_user()
    _seed(uid)
    update, msg = _upd(uid)
    ctx = SimpleNamespace(bot=None, user_data={}, args=[], bot_data={})

    async def run():
        await bot._private_chat_guard(update, ctx)
        await bot._period_command("oy")(update, ctx)

    try:
        asyncio.run(run())
    finally:
        reports.set_lang(None)
    text = msg.replies[-1][0]
    _no_uzbek(text)
    assert "Доход:" in text and "сум" in text


def test_commands_list_and_menu_in_russian():
    assert all(name.isascii() for name, _ in bot.BOT_COMMANDS_RU)
    assert len(bot.BOT_COMMANDS_RU) == len(bot.BOT_COMMANDS)
    assert all(re.search("[а-яА-Я]", d) or name == "til"
               for name, d in bot.BOT_COMMANDS_RU)
    assert all(len(d) <= 256 for _, d in bot.BOT_COMMANDS_RU)
    uid = _ru_user()
    update, msg = _upd(uid)
    ctx = SimpleNamespace(bot=None, user_data={}, args=[], bot_data={})
    asyncio.run(bot.cmd_commands(update, ctx))
    text = msg.replies[-1][0]
    assert "КОМАНДЫ" in text and "Отчёты" in text and "Отчёт за сегодня" in text
    assert "Hisobotlar" not in text


def test_budget_accepts_russian_names_and_amounts():
    assert bot.match_expense_category("продукты") == "oziq-ovqat"
    assert bot.match_expense_category("Хозтовары и гигиена") == "uy-ro'zg'or va gigiyena"
    assert bot.split_budget_args(["продукты", "2", "млн"]) == ("продукты", 2_000_000)
    assert bot.split_budget_args(["транспорт", "500", "тысяч"]) == ("транспорт", 500_000)
    assert bot.split_budget_args(["такси", "1.5", "миллиона"])[1] == 1_500_000


def test_ai_hint_never_shows_uzbek_to_russian_user():
    reports.set_lang("ru")
    try:
        assert "Не понял" in bot._ai_hint("Summa aniq emas", "not_understood")
        assert bot._ai_hint("Сумма не видна", "not_understood") == "Сумма не видна"
        assert "<code>" in bot._ai_hint("", "not_understood")   # tayyor HTML buzilmaydi
    finally:
        reports.set_lang(None)
    assert bot._ai_hint("Summa aniq emas", "not_understood") == "Summa aniq emas"
    assert bot._ai_hint("a<b", "not_understood") == "a&lt;b"


def test_share_card_text_follows_language():
    import sharecard
    assert sharecard._money(2_500_000, "som", "ru") == "2.5 млн сум"
    assert sharecard._money(2_500_000, "som", "uz") == "2.5 mln so'm"
    assert sharecard._entries_label(3, "ru") == "3 записи"
    assert sharecard._entries_label(5, "ru") == "5 записей"
    assert sharecard._entries_label(3, "uz") == "3 ta yozuv"
    if sharecard.available():
        png = sharecard.build(title="Октябрь", kirim=8_000_000, chiqim=600_000,
                              categories=[("oziq-ovqat", 500_000, 3)], lang="ru")
        assert png and png[:4] == b"\x89PNG"
