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


# --------------------------------------------------------------- Mini App --

from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
_JS_STR = r'"((?:[^"\\\n]|\\.)*)"'


def _js_dictionary(js: str) -> set[str]:
    block = js[js.index("const RU = {"):js.index("const MONTHS_UZ_SHORT")]
    return {m.group(1).replace('\\"', '"').replace("\\\\", "\\")
            for m in re.finditer(r'(?:^|[,{\s])' + _JS_STR + r'\s*:', block, re.M)}


def test_every_miniapp_text_has_a_russian_translation():
    js = (ROOT / "static" / "app.js").read_text(encoding="utf-8")
    known = _js_dictionary(js)
    assert len(known) > 100
    used = {m.group(1) for m in re.finditer(r'\bt\(' + _JS_STR, js)}
    assert used, "t() chaqiruvlari topilmadi"
    assert not (used - known), f"tarjimasiz: {sorted(used - known)}"
    html = (ROOT / "static" / "index.html").read_text(encoding="utf-8")
    attrs = {m.group(1) for m in re.finditer(r'data-i18n(?:-ph|-aria)?="([^"]*)"', html)}
    assert attrs and not (attrs - known), f"HTML da tarjimasiz: {sorted(attrs - known)}"


def test_no_uzbek_literals_left_outside_t_in_miniapp():
    """Foydalanuvchiga ko'rinadigan o'zbekcha matn t() dan o'tmay qolmasin."""
    js = (ROOT / "static" / "app.js").read_text(encoding="utf-8")
    body = js[js.index("const MONTHS_UZ_SHORT"):]
    leftovers = []
    for n, line in enumerate(body.splitlines(), 1):
        code = line.split("//")[0] if line.strip().startswith("//") else line
        if line.strip().startswith(("//", "*", "/*")):
            continue
        for lit in re.finditer(r"toast\(\"([^\"]+)\"\)|textContent = \"([A-Z][^\"]+)\"", code):
            leftovers.append((n, lit.group(0)))
    assert not leftovers, leftovers


def _init(uid):
    import hashlib, hmac, json, time
    from urllib.parse import urlencode
    pairs = {"auth_date": str(int(time.time())),
             "user": json.dumps({"id": uid, "first_name": "Иван"})}
    check = "\n".join(f"{k}={v}" for k, v in sorted(pairs.items()))
    secret = hmac.new(b"WebAppData", config.TELEGRAM_TOKEN.encode(), hashlib.sha256).digest()
    pairs["hash"] = hmac.new(secret, check.encode(), hashlib.sha256).hexdigest()
    return {"X-Telegram-Init-Data": urlencode(pairs)}


def test_miniapp_api_speaks_the_users_language():
    from fastapi.testclient import TestClient
    import webapp
    webapp._rate.clear()
    ru, uz = _ru_user(2101), 2102
    db.get_or_create_user(uz, "Ali", None)
    db.set_consent(uz, config.CONSENT_VERSION)
    client = TestClient(webapp.app)

    me = client.get("/api/me", headers=_init(ru)).json()
    assert me["lang"] == "ru"
    assert me["category_labels"]["oziq-ovqat"] == "продукты"
    assert me["kind_labels"]["qarz_berdim"] == "Дал в долг"
    assert me["currency_symbols"]["som"] == "сум"
    me_uz = client.get("/api/me", headers=_init(uz)).json()
    assert me_uz["lang"] == "uz" and me_uz["currency_symbols"]["som"] == "so'm"
    assert me_uz["category_labels"] == {"oylik": "ish haqi"}

    assert client.get("/api/summary?period=oy", headers=_init(ru)).json()["label"] \
        .split()[0] in [m.capitalize() for m in i18n.MONTHS_RU_NOM]
    week = client.get("/api/summary?period=hafta", headers=_init(ru)).json()["label"]
    assert re.search("[а-я]", week)

    bad = client.delete("/api/transactions/999999", headers=_init(ru))
    assert bad.status_code == 404 and bad.json()["detail"] == "Запись не найдена"
    bad = client.delete("/api/transactions/999999", headers=_init(uz))
    assert bad.json()["detail"] == "Yozuv topilmadi"
    bad = client.get("/api/summary?period=oy&ref=xx", headers=_init(ru))
    assert bad.status_code == 400 and "Неверная дата" in bad.json()["detail"]


def test_miniapp_rate_limit_message_is_russian(monkeypatch):
    from fastapi.testclient import TestClient
    import webapp
    webapp._rate.clear()
    monkeypatch.setattr(webapp, "RATE_LIMIT", 1)
    uid = _ru_user(2103)
    client = TestClient(webapp.app)
    client.get("/api/me", headers=_init(uid))
    r = client.get("/api/me", headers=_init(uid))
    assert r.status_code == 429 and "Слишком много запросов" in r.json()["detail"]


# ---------------------------------------------------- matn va chek oqimi --

def _text_run(monkeypatch, parsed, text="обед 45 тысяч", uid=2201, error=False):
    import ai

    async def fake_parse(t, today=None):
        if error:
            raise RuntimeError("boom")
        return parsed

    monkeypatch.setattr(ai, "parse_message", fake_parse)
    uid = _ru_user(uid)
    update, msg = _upd(uid)
    msg.text = text
    msg.chat_id = uid
    ctx = SimpleNamespace(bot=SimpleNamespace(send_chat_action=_noop, send_message=_noop2),
                          user_data={}, args=[], bot_data={})

    async def run():
        await bot._private_chat_guard(update, ctx)
        await bot._process_text(update, ctx, text)

    asyncio.run(run())
    return msg


async def _noop(*a, **k):
    return None


async def _noop2(*a, **k):
    return None


def test_text_entry_is_saved_and_answered_in_russian(monkeypatch):
    parsed = {"niyat": "yozuv", "izoh_matni": "", "_usage": None, "yozuvlar": [
        {"turi": "chiqim", "summa": 45_000, "valyuta": "som", "kategoriya": "kafe va restoran",
         "izoh": "обед", "shaxs": "", "sana": date.today().isoformat(), "maqsad": "",
         "muddat": None}]}
    msg = _text_run(monkeypatch, parsed)
    text = msg.replies[0][0]
    _no_uzbek(text)
    assert "Расход" in text and "сохранено" in text and "кафе и рестораны" in text
    assert "45 000 сум" in text and "Расходы сегодня" in text
    buttons = [b.text for row in msg.replies[0][1].inline_keyboard for b in row]
    assert "✏️ Категория" in buttons and "🗑 Удалить" in buttons


def test_multi_entry_message_in_russian(monkeypatch):
    day = date.today().isoformat()
    row = lambda amount, cat, note: {
        "turi": "chiqim", "summa": amount, "valyuta": "som", "kategoriya": cat,
        "izoh": note, "shaxs": "", "sana": day, "maqsad": "", "muddat": None}
    parsed = {"niyat": "yozuv", "izoh_matni": "", "_usage": None,
              "yozuvlar": [row(20_000, "transport", "такси"), row(25_000, "oziq-ovqat", "кофе")]}
    msg = _text_run(monkeypatch, parsed, uid=2202)
    text = msg.replies[0][0]
    _no_uzbek(text)
    assert "2 записи сохранены" in text and "Чтобы исправить" in text


def test_unclear_message_gives_russian_hint(monkeypatch):
    parsed = {"niyat": "tushunarsiz", "izoh_matni": "Summa aniq emas", "_usage": None,
              "yozuvlar": []}
    msg = _text_run(monkeypatch, parsed, text="привет как дела", uid=2203)
    assert "Не понял" in msg.replies[0][0] and "Summa" not in msg.replies[0][0]


def test_ai_failure_message_is_russian(monkeypatch):
    msg = _text_run(monkeypatch, {}, text="обед 45 тысяч", uid=2204, error=True)
    assert msg.replies[0][0] == "⚠️ Ошибка связи с AI. Попробуйте чуть позже."


def test_receipt_reading_status_and_errors_in_russian(monkeypatch):
    import ai
    uid = _ru_user(2205)

    async def failing(*a, **k):
        raise RuntimeError("boom")

    monkeypatch.setattr(ai, "parse_receipt", failing)
    update, msg = _upd(uid)
    msg.edit_log = []

    async def edit_text(text, **kw):
        msg.edit_log.append(text)

    msg.edit_text = edit_text
    ctx = SimpleNamespace(bot=SimpleNamespace(send_chat_action=_noop, send_message=_noop2),
                          user_data={}, args=[], bot_data={})

    async def run():
        await bot._private_chat_guard(update, ctx)
        await bot._process_receipt(update, ctx, [("x", "image/jpeg")] * 2, "")

    asyncio.run(run())
    assert msg.replies[0][0] == "🔍 Читаю чек (2 ч.)…"
    assert msg.edit_log == ["⚠️ Ошибка при чтении чека. Попробуйте чуть позже."]
