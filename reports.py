"""Hisobotlarni matnga aylantirish va sana oraliqlarini hisoblash.

Telegram'ga HTML parse_mode bilan yuboriladi, shuning uchun foydalanuvchi
kiritgan har qanday matn esc() orqali o'tkaziladi.

Hamma matn-quruvchi funksiya `lang` oladi (standart «uz»): o'zbekcha matn
shu yerda yoziladi, ruscha varianti yonida turadi, kirill yozuvi esa
lotinchadan avtomatik o'giriladi (`i18n.pick`). Foydalanuvchi kiritgan
qiymatlar (ism, izoh, do'kon) `pick` ga KIRMAYDI — ular o'zgarmay qoladi.
"""

from __future__ import annotations

from datetime import date, datetime, timedelta
from html import escape

import contextvars
import logging

import config
import db
import i18n
from i18n import pick

log = logging.getLogger("tanga.reports")

UZ_MONTHS = i18n.MONTHS_UZ

# «Joriy foydalanuvchi tili». Bot har bir yangilanishda uni o'rnatadi
# (`set_lang`), shuning uchun summa/sana formatlovchilar (bot.py da 70 dan
# ortiq joyda) `lang` ni qo'lda olib yurmaydi. Aniq `lang` berilsa u
# ustun turadi. Yangilanishsiz ishlaydigan joylar (rejali vazifalar)
# qiymatni o'zi o'rnatadi; o'rnatilmasa — o'zbekcha (avvalgi xatti-harakat).
_ctx_lang: contextvars.ContextVar[str | None] = contextvars.ContextVar(
    "reports_lang", default=None)


def set_lang(lang: str | None) -> None:
    _ctx_lang.set(lang)


def _L(lang: str | None) -> str | None:
    return lang if lang is not None else _ctx_lang.get()


resolve_lang = _L      # bot.py va boshqa modullar uchun ochiq nom


def esc(text) -> str:
    return escape(str(text or ""), quote=False)


def today() -> date:
    return datetime.now(config.TZ).date()


def _is_ru(lang: str | None) -> bool:
    return i18n.normalize(lang) == "ru"


def _plural(n: int, one: str, few: str, many: str) -> str:
    """Rus tilida son bilan so'z shakli: 1 товар, 2 товара, 5 товаров."""
    n = abs(int(n))
    if n % 10 == 1 and n % 100 != 11:
        return one
    if 2 <= n % 10 <= 4 and not 12 <= n % 100 <= 14:
        return few
    return many


def fmt_money(value: float, currency: str = "som", lang: str | None = None) -> str:
    """1250000 -> "1 250 000 so'm"; USD uchun 99.5 -> "$99.5" """
    lang = _L(lang)
    if currency == config.CURRENCY_USD:
        v = round(float(value), 2)
        text = f"{v:,.2f}".rstrip("0").rstrip(".") if v % 1 else f"{int(v):,}"
        return f"${text.replace(',', ' ')}"
    rounded = round(float(value))
    return f"{rounded:,}".replace(",", " ") + f" {i18n.money_unit(lang)}"


def fmt_date(iso: str, lang: str | None = None) -> str:
    lang = _L(lang)
    try:
        d = date.fromisoformat(iso)
    except (ValueError, TypeError):
        return str(iso)
    # Boshqa yildagi sana yil bilan: ilgari «8-oktabr» ko'rinardi va AI
    # yilni adashtirgani (2027 yoki 2016) tasdiq xabaridan bilinmasdi.
    other_year = d.year != today().year
    if _is_ru(lang):
        text = f"{d.day} {i18n.month_name(lang, d.month)}"
        return f"{text} {d.year}" if other_year else text
    if other_year:
        return pick(lang, f"{d.year}-yil {d.day}-{UZ_MONTHS[d.month - 1]}")
    return pick(lang, f"{d.day}-{UZ_MONTHS[d.month - 1]}")


def period_range(period: str, ref: date | None = None,
                 lang: str | None = None) -> tuple[date, date, str]:
    """period: bugun | kecha | hafta | oy | otgan_oy | yil"""
    lang = _L(lang)
    ref = ref or today()

    def month_title(d: date) -> str:
        if _is_ru(lang):
            return i18n.month_name(lang, d.month, nominative=True).capitalize()
        return pick(lang, f"{UZ_MONTHS[d.month - 1].capitalize()} oyi")

    if period == "bugun":
        return ref, ref, pick(lang, "Bugun", "Сегодня")
    if period == "kecha":
        y = ref - timedelta(days=1)
        return y, y, pick(lang, "Kecha", "Вчера")
    if period == "hafta":
        start = ref - timedelta(days=ref.weekday())
        return start, ref, pick(lang, "Shu hafta", "Эта неделя")
    if period == "oy":
        return ref.replace(day=1), ref, month_title(ref)
    if period == "otgan_oy":
        last_day_prev = ref.replace(day=1) - timedelta(days=1)
        start = last_day_prev.replace(day=1)
        return start, last_day_prev, month_title(start)
    if period == "yil":
        return (ref.replace(month=1, day=1), ref,
                pick(lang, f"{ref.year}-yil", f"{ref.year} год"))
    return ref.replace(day=1), ref, pick(lang, "Davr", "Период")


def _bar(share: float, width: int = 10) -> str:
    filled = max(0, min(width, round(share * width)))
    return "█" * filled + "░" * (width - filled)


def _count(n: int, lang: str | None) -> str:
    """«3 ta» / «3 шт.»"""
    return f"{n} " + pick(lang, "ta", "шт.")


def debt_lines(t: dict, currency: str = "som", lang: str | None = None) -> list[str]:
    """Davr ichidagi qarz harakati — kirim/chiqim va «Farq» dan ALOHIDA.

    Qarz berish va qaytarish pul harakati, lekin xarajat ham, daromad
    ham emas: shuning uchun yuqoridagi jamlarga qo'shilmaydi, faqat shu
    yerda ko'rinadi.
    """
    lang = _L(lang)
    kinds = (config.KIND_QARZ_BERDIM, config.KIND_QARZ_OLDIM,
             config.KIND_QARZ_QAYTARDIM, config.KIND_QARZ_QAYTDI)
    out = [f"{config.KIND_ICONS[k]} {i18n.kind_label(lang, k)}: "
           f"{fmt_money(t[k], currency, lang)}"
           for k in kinds if t.get(k)]
    if not out:
        return []
    return ["", pick(lang, "<b>Qarzlar</b> <i>(chiqimga kirmaydi)</i>",
                     "<b>Долги</b> <i>(в расходы не входят)</i>")] + out


def _currency_block(user_id: int, start: date, end: date, currency: str, days: int,
                    lang: str | None = None) -> list[str]:
    """Bitta valyuta uchun kirim/chiqim/farq va kategoriyalar bloki."""
    lang = _L(lang)
    t = db.totals(user_id, start, end, currency)
    kirim = t[config.KIND_KIRIM]
    chiqim = t[config.KIND_CHIQIM]
    balans = kirim - chiqim

    lines: list[str] = []
    lines.append(f"🔺 {pick(lang, 'Kirim:', 'Доход:')}  {fmt_money(kirim, currency, lang)}")
    lines.append(f"🔻 {pick(lang, 'Chiqim:', 'Расход:')} {fmt_money(chiqim, currency, lang)}")
    lines.append(f"{'🟢' if balans >= 0 else '🔴'} {pick(lang, 'Farq:', 'Разница:')}   "
                 f"{fmt_money(balans, currency, lang)}")

    cats = db.by_category(user_id, start, end, config.KIND_CHIQIM, currency)
    if cats:
        lines.append("")
        lines.append(pick(lang, "<b>Chiqim kategoriyalari:</b>",
                          "<b>Категории расходов:</b>"))
        for name, total, cnt in cats[:8]:
            share = total / chiqim if chiqim else 0
            icon = config.CATEGORY_ICONS.get(name, "•")
            lines.append(f"{icon} {esc(i18n.category_name(lang, name))} — "
                         f"{fmt_money(total, currency, lang)} ({share * 100:.0f}%)")
            lines.append(f"   <code>{_bar(share)}</code> {_count(cnt, lang)}")

    lines += debt_lines(t, currency, lang)

    if chiqim and days >= 2:
        lines.append("")
        lines.append("<i>" + pick(lang, "Kuniga o'rtacha:", "В среднем в день:")
                     + f" {fmt_money(chiqim / days, currency, lang)}</i>")

    return lines


def compare_ranges(today: date) -> tuple[tuple[date, date], tuple[date, date]]:
    """Joriy oy boshidan bugungacha va o'tgan oyning XUDDI SHU kunlari.

    Oyning 3-kunini o'tgan oyning to'liq 30 kuni bilan solishtirish
    «90% kam sarfladingiz» degan yolg'on xulosa beradi. O'tgan oy
    qisqaroq bo'lsa (31-mart -> 28-fevral) uning oxirigacha olinadi.
    """
    cur_start = today.replace(day=1)
    prev_end_of_month = cur_start - timedelta(days=1)
    prev_start = prev_end_of_month.replace(day=1)
    prev_end = prev_start.replace(day=min(today.day, prev_end_of_month.day))
    return (cur_start, today), (prev_start, prev_end)


def _delta(now: float, was: float, currency: str = "som",
           lang: str | None = None) -> str:
    lang = _L(lang)
    diff = now - was
    if abs(diff) < 0.5:
        return pick(lang, "<i>o'zgarmadi</i>", "<i>без изменений</i>")
    arrow = "▲" if diff > 0 else "▼"
    sign = "+" if diff > 0 else "−"
    pct = f" {abs(diff) / was * 100:.0f}%" if was > 0 else ""
    return f"{arrow}{pct} ({sign}{fmt_money(abs(diff), currency, lang)})"


def _category_changes(user_id: int, cur: tuple[date, date],
                      prev: tuple[date, date]) -> list[tuple[str, float, float]]:
    """Chiqim kategoriyalari (nom, joriy, o'tgan) — eng katta o'zgarish
    birinchi. Matn ham, grafik ham shu tartibni ishlatadi."""
    now = {c: s for c, s, _ in db.by_category_unified(user_id, *cur, config.KIND_CHIQIM)}
    was = {c: s for c, s, _ in db.by_category_unified(user_id, *prev, config.KIND_CHIQIM)}
    names = sorted(set(now) | set(was),
                   key=lambda c: abs(now.get(c, 0) - was.get(c, 0)), reverse=True)
    return [(c, now.get(c, 0), was.get(c, 0)) for c in names]


def _day_span(start: date, end: date, lang: str | None) -> str:
    """«1–3 oktabr», bitta kun bo'lsa «1 oktabr» («1–1» emas)."""
    days = f"{start.day}" if start == end else f"{start.day}–{end.day}"
    return f"{days} {i18n.month_name(lang, start.month)}"


def compare_text(user_id: int, day: date | None = None, lang: str | None = None) -> str:
    """Oylarni solishtirish (PRO): jamlar va kategoriyalar bo'yicha o'zgarish.

    Barcha valyuta asosiy valyutada (yozuv kunidagi kurs bilan) —
    «hammasi» ko'rinishi bilan bir xil.
    """
    lang = _L(lang)
    (cs, ce), (ps, pe) = compare_ranges(day or today())
    now = db.totals_unified(user_id, cs, ce)["totals"]
    was = db.totals_unified(user_id, ps, pe)["totals"]
    # Sarlavhada oy nomi bosh kelishikda («Октябрь и сентябрь»), sanada esa
    # qaratqich kelishigida («1–6 октября»).
    cur_m = i18n.month_name(lang, cs.month, nominative=True)
    prev_m = i18n.month_name(lang, ps.month, nominative=True)
    and_ = pick(lang, "va", "и")

    lines = [
        f"📊 <b>{cur_m.capitalize()} {and_} {prev_m}</b>",
        "<i>" + pick(lang, "Bir xil kunlar:", "Одинаковые дни:")
        + f" {_day_span(cs, ce, lang)} {and_} {_day_span(ps, pe, lang)}</i>",
        "",
    ]
    for kind, icon, label in (
            (config.KIND_CHIQIM, "🔻", pick(lang, "Chiqim", "Расход")),
            (config.KIND_KIRIM, "🔺", pick(lang, "Kirim", "Доход"))):
        lines.append(f"{icon} {label}: <b>{fmt_money(now[kind], lang=lang)}</b>  "
                     f"{_delta(now[kind], was[kind], lang=lang)}")
    if now[config.KIND_KIRIM] or was[config.KIND_KIRIM]:
        farq_now = now[config.KIND_KIRIM] - now[config.KIND_CHIQIM]
        farq_was = was[config.KIND_KIRIM] - was[config.KIND_CHIQIM]
        lines.append(f"⚖️ {pick(lang, 'Farq', 'Разница')}: "
                     f"<b>{fmt_money(farq_now, lang=lang)}</b>  "
                     f"{_delta(farq_now, farq_was, lang=lang)}")

    changes = _category_changes(user_id, (cs, ce), (ps, pe))
    if changes:
        lines += ["", pick(lang, "<b>Chiqim kategoriyalari — eng katta o'zgarish:</b>",
                           "<b>Категории расходов — самые большие изменения:</b>")]
        for name, amount, before in changes[:6]:
            icon = config.CATEGORY_ICONS.get(name, "•")
            lines.append(f"{icon} {esc(i18n.category_name(lang, name))} — "
                         f"{fmt_money(amount, lang=lang)}  "
                         f"{_delta(amount, before, lang=lang)}")
    if not any(now.values()) and not any(was.values()):
        lines += ["", pick(lang, "<i>Bu davrlarda yozuv yo'q.</i>",
                           "<i>За эти периоды записей нет.</i>")]
    return "\n".join(lines)


def compare_chart(user_id: int, day: date | None = None, lang: str | None = None,
                  bot_username: str = "") -> bytes | None:
    """compare_text ning grafik ko'rinishi (PNG). Ikkala davrda ham yozuv
    bo'lmasa yoki rasm chizib bo'lmasa None — chaqiruvchi faqat matn yuboradi."""
    import sharecard
    lang = _L(lang)
    (cs, ce), (ps, pe) = compare_ranges(day or today())
    now = db.totals_unified(user_id, cs, ce)["totals"]
    was = db.totals_unified(user_id, ps, pe)["totals"]
    if not any(now.values()) and not any(was.values()):
        return None
    cur_m = i18n.month_name(lang, cs.month, nominative=True)
    prev_m = i18n.month_name(lang, ps.month, nominative=True)
    and_ = pick(lang, "va", "и")
    subtitle = (pick(lang, "Bir xil kunlar:", "Одинаковые дни:")
                + f" {_day_span(cs, ce, lang)} {and_} {_day_span(ps, pe, lang)}")
    try:
        return sharecard.build_compare(
            title=f"{cur_m.capitalize()} {and_} {prev_m}",
            subtitle=subtitle,
            cur_label=cur_m.capitalize(), prev_label=prev_m.capitalize(),
            cur_start=cs, prev_start=ps,
            # O'tgan oy qisqaroq bo'lsa (31-mart / 28-fevral) chiziq joriy
            # oy uzunligida, o'tgan oyniki oxirgi kunidan keyin tekis qoladi.
            days=(ce - cs).days + 1,
            cur_daily=db.daily_unified(user_id, cs, ce, config.KIND_CHIQIM),
            prev_daily=db.daily_unified(user_id, ps, pe, config.KIND_CHIQIM),
            now={"kirim": now[config.KIND_KIRIM], "chiqim": now[config.KIND_CHIQIM]},
            was={"kirim": was[config.KIND_KIRIM], "chiqim": was[config.KIND_CHIQIM]},
            categories=_category_changes(user_id, (cs, ce), (ps, pe)),
            bot_username=bot_username, lang=lang)
    except Exception:
        log.exception("Solishtirish grafigini chizib bo'lmadi")
        return None


def _income_share(pct: str, lang: str | None) -> str:
    """«daromadning 12%i» / «12% от дохода»."""
    if _is_ru(lang):
        return f"{pct}% от дохода"
    return pick(lang, f"daromadning {pct}%i")


def summary_text(user_id: int, period: str, lang: str | None = None) -> str:
    """Davr hisoboti — barcha valyutalar bitta jamlanmada.

    Odamning hamyoni bitta: dollarda to'lagan puli ham o'sha umumiy
    mablag'idan chiqadi. Shuning uchun jamlanma asosiy valyutada
    beriladi, chet el valyutasidagi ulush esa alohida eslatiladi.
    Har bir yozuv o'z kunidagi kurs bilan o'girilgan — kurs bugun
    o'zgarsa ham o'tgan oy hisoboti o'zgarmaydi.
    """
    lang = _L(lang)
    start, end, label = period_range(period, lang=lang)
    days = (end - start).days + 1

    data = db.totals_unified(user_id, start, end)
    t, foreign = data["totals"], data["foreign"]
    kirim = t[config.KIND_KIRIM]
    chiqim = t[config.KIND_CHIQIM]
    balans = kirim - chiqim

    lines = [f"📊 <b>{esc(label)}</b>", ""]
    if not any(t.values()):
        lines.append(pick(lang, "<i>Bu davrda yozuv yo'q.</i>",
                          "<i>За этот период записей нет.</i>"))
        return "\n".join(lines)

    lines.append(f"🔺 {pick(lang, 'Kirim:', 'Доход:')}  {fmt_money(kirim, lang=lang)}")
    lines.append(f"🔻 {pick(lang, 'Chiqim:', 'Расход:')} {fmt_money(chiqim, lang=lang)}")
    lines.append(f"{'🟢' if balans >= 0 else '🔴'} {pick(lang, 'Farq:', 'Разница:')}   "
                 f"{fmt_money(balans, lang=lang)}")

    if foreign:
        parts = []
        for cur, info in foreign.items():
            parts.append(f"{fmt_money(info['orig'], cur, lang)} ≈ "
                         f"{fmt_money(info['base'], lang=lang)}")
        lines.append("")
        lines.append("<i>" + pick(lang, "Shundan chet el valyutasida:",
                                  "Из них в иностранной валюте:")
                     + f" {' · '.join(parts)}</i>")

    cats = db.by_category_unified(user_id, start, end, config.KIND_CHIQIM)
    if cats:
        lines.append("")
        lines.append(pick(lang, "<b>Chiqim kategoriyalari:</b>",
                          "<b>Категории расходов:</b>"))
        for name, total, cnt in cats[:8]:
            share = total / chiqim if chiqim else 0
            icon = config.CATEGORY_ICONS.get(name, "•")
            lines.append(f"{icon} {esc(i18n.category_name(lang, name))} — "
                         f"{fmt_money(total, lang=lang)} ({share * 100:.0f}%)")
            lines.append(f"   <code>{_bar(share)}</code> {_count(cnt, lang)}")

    lines += debt_lines(t, lang=lang)

    # Jamg'arma ATAYLAB "Farq" dan tashqarida turadi: u sarflangan pul
    # emas, shuning uchun chiqimga qo'shilmaydi. Lekin daromadga nisbatan
    # ulushi ko'rsatiladi — kitobdagi 10 % qoidasi shu joyda ko'rinadi.
    jamgardim = t[config.KIND_JAMGARMA] - t[config.KIND_JAMGARMA_YECHDIM]
    if jamgardim:
        rate = db.savings_rate(user_id)
        lines.append("")
        share = (" — " + _income_share(f"{jamgardim / kirim * 100:.0f}", lang)
                 if kirim > 0 else "")
        savings_label = pick(lang, "Jamg'arma", "Накопления")
        lines.append(f"🏦 {savings_label}: "
                     f"{fmt_money(jamgardim, lang=lang)}{share}")
        if kirim > 0 and jamgardim >= kirim * rate:
            lines.append("<i>✅ " + pick(lang, f"{rate * 100:.0f}% qoidasi bajarildi",
                                         f"правило {rate * 100:.0f}% выполнено") + "</i>")

    if chiqim and days >= 2:
        lines.append("")
        lines.append("<i>" + pick(lang, "Kuniga o'rtacha:", "В среднем в день:")
                     + f" {fmt_money(chiqim / days, lang=lang)}</i>")

    text = "\n".join(lines)
    if period in ("oy", "otgan_oy"):
        text += _monthly_score(t, db.savings_rate(user_id), lang)
    elif period == "yil":
        text += _yearly_savings(user_id, start, end, lang)
    return text


def _monthly_score(t: dict, rate: float, lang: str | None = None) -> str:
    """Oylik uch savol: 10 % jamg'ardingmi, topganingdan kam
    sarfladingmi, qarzing ko'paymadimi.

    Baho ATAYLAB oddiy: uchta savol, uchta belgi. Murakkab ball tizimi
    o'qilmaydi.

    Foydalanuvchiga ko'rinadigan matnda manba (kitob) tilga olinmaydi —
    maslahat o'z-o'zidan tushunarli bo'lishi kerak.
    """
    lang = _L(lang)
    kirim = t[config.KIND_KIRIM]
    chiqim = t[config.KIND_CHIQIM]
    saved = t[config.KIND_JAMGARMA] - t[config.KIND_JAMGARMA_YECHDIM]
    new_debt = t[config.KIND_QARZ_OLDIM]

    # Daromad yozilmagan oyda baho berish adolatsiz — birinchi ikki
    # savolning ma'nosi qolmaydi.
    if kirim <= 0:
        return ""

    pct = f"{rate * 100:.0f}"
    rows = [
        (saved >= kirim * rate,
         pick(lang, f"Daromadning {pct}% i jamg'arildi",
              f"Отложено {pct}% дохода"),
         pick(lang, f"{pct}% jamg'arilmadi", f"{pct}% не отложено")),
        (chiqim < kirim,
         pick(lang, "Daromaddan kam sarflandi", "Расходы меньше дохода"),
         pick(lang, "Daromaddan ko'p sarflandi", "Расходы больше дохода")),
        (new_debt <= 0,
         pick(lang, "Qarz ko'paymadi", "Долг не вырос"),
         pick(lang, "Yangi qarz olindi", "Взят новый долг")),
    ]
    score = sum(1 for ok, _, _ in rows if ok)
    body = "\n".join(f"{'✅' if ok else '❌'} {yes if ok else no}"
                     for ok, yes, no in rows)
    title = pick(lang, f"Oylik baho: {score}/3", f"Оценка месяца: {score}/3")
    return f"\n\n📜 <b>{title}</b>\n{body}"


def _yearly_savings(user_id: int, start: date, end: date,
                    lang: str | None = None) -> str:
    """Yillik hisobotga jamg'arma bo'limi."""
    lang = _L(lang)
    lo, hi = start.isoformat()[:7], end.isoformat()[:7]
    months = [m for m in db.savings_by_month(user_id, months=24)
              if lo <= m["oy"] <= hi]
    saved = sum(m["jamgarma"] for m in months)
    if saved <= 0:
        return ""
    income = sum(m["kirim"] for m in months)
    rate = db.savings_rate(user_id)
    good = sum(1 for m in months
               if m["kirim"] > 0
               and m["jamgarma"] >= m["kirim"] * rate)
    if income > 0:
        pct = f"{saved / income * 100:.0f}"
        share = " — " + (f"{pct}% от вашего дохода" if _is_ru(lang)
                         else pick(lang, f"daromadingizning {pct}%i"))
    else:
        share = ""
    heading = pick(lang, "Yil davomida jamg'arma", "Накопления за год")
    return (f"\n\n🏦 <b>{heading}</b>\n"
            f"{pick(lang, 'Jami', 'Всего')}: <b>{fmt_money(saved, lang=lang)}</b>{share}\n"
            + pick(lang, f"{rate * 100:.0f}% qoidasi bajarilgan oylar:",
                   f"Месяцев с выполненным правилом {rate * 100:.0f}%:")
            + f" <b>{good} / {len(months)}</b>")


def transaction_line(row, with_id: bool = True, lang: str | None = None) -> str:
    lang = _L(lang)
    icon = config.KIND_ICONS.get(row["kind"], "•")
    cat_icon = config.CATEGORY_ICONS.get(row["category"], "")
    label = i18n.category_name(lang, row["category"])
    person = f" — {esc(row['person'])}" if row["person"] else ""
    tail = f" <code>#{row['id']}</code>" if with_id else ""
    currency = row["currency"] if "currency" in row.keys() else "som"
    # Izoh bo'lsa kategoriya ham yonida ko'rinadi: «nonga · 🥦 oziq-ovqat».
    # Qarz turlarida kategoriya doim «qarz» — uning o'rnida shaxs turadi.
    if row["kind"] in config.DEBT_KINDS:
        body = esc(row["note"] or i18n.kind_label(lang, row["kind"]))
    elif row["note"]:
        body = f"{esc(row['note'])} · {cat_icon} {esc(label)}"
    else:
        body = f"{cat_icon} {esc(label)}"
    return (
        f"{icon} {fmt_money(row['amount'], currency, lang)} · {body}{person}"
        f" · <i>{fmt_date(row['occurred_on'], lang)}</i>{tail}"
    )


def _items_word(n: int, lang: str | None) -> str:
    if _is_ru(lang):
        return f"{n} " + _plural(n, "товар", "товара", "товаров")
    return pick(lang, f"{n} mahsulot")


def receipt_line(entry: dict, with_id: bool = True, lang: str | None = None) -> str:
    """Chek bitta qatorda: 🧾 Korzinka cheki — 260 800 so'm (15 mahsulot) · 1-oktabr"""
    lang = _L(lang)
    shop = (entry.get("shop") or "").strip()
    if shop:
        name = f"Чек {esc(shop)}" if _is_ru(lang) else f"{esc(shop)} {pick(lang, 'cheki')}"
    else:
        name = pick(lang, "Chek", "Чек")
    tail = f" <code>#{entry['id']}</code>" if with_id else ""
    return (
        f"🧾 {name} — {fmt_money(entry['amount'], entry.get('currency') or 'som', lang)} "
        f"({_items_word(entry['n'], lang)}) · "
        f"<i>{fmt_date(entry['occurred_on'], lang)}</i>{tail}"
    )


def recent_text(user_id: int, limit: int = 12, lang: str | None = None) -> str:
    lang = _L(lang)
    entries = db.recent_entries(user_id, limit)
    if not entries:
        return pick(lang, "Hozircha yozuv yo'q.", "Записей пока нет.")
    n = len(entries)
    title = (f"Последние {n} " + _plural(n, "запись", "записи", "записей")
             if _is_ru(lang) else pick(lang, f"Oxirgi {n} ta yozuv"))
    lines = [f"🧾 <b>{title}</b>", ""]
    for e in entries:
        lines.append(receipt_line(e, lang=lang) if e["receipt_id"]
                     else transaction_line(e, lang=lang))
    lines.append("")
    lines.append(pick(lang,
                      "<i>O'chirish uchun:</i> <code>/ochir 12</code> "
                      "<i>(chek raqami butun chekni o'chiradi)</i>",
                      "<i>Чтобы удалить:</i> <code>/ochir 12</code> "
                      "<i>(номер чека удалит весь чек)</i>"))
    return "\n".join(lines)


CSV_HEADER = ["id", "sana", "turi", "summa", "valyuta", "kategoriya", "izoh",
              "shaxs", "yopilgan", "chek_id", "dokon"]


def csv_bytes(user_id: int) -> tuple[bytes, int]:
    """Barcha yozuvlar CSV ko'rinishida (Excel uchun BOM bilan).

    Chek mahsulotlari alohida qator bo'lib qoladi va har birida o'z
    cheki identifikatori (`chek_id`) va do'koni turadi — chekni Excel'da
    qayta yig'ish mumkin bo'lsin.

    Sarlavha va turlar ATAYLAB tilga bog'lanmagan: fayl boshqa dasturlarga
    yuklanadi, ustun nomlari barqaror bo'lishi kerak.
    """
    import csv
    import io

    rows = db.export_rows(user_id)
    buf = io.StringIO()
    writer = csv.writer(buf)
    writer.writerow(CSV_HEADER)
    for r in rows:
        writer.writerow([
            r["id"], r["occurred_on"], r["kind"], r["amount"], r["currency"],
            r["category"], r["note"], r["person"] or "", r["settled"],
            r["receipt_id"] or "", r["shop"] or "",
        ])
    return buf.getvalue().encode("utf-8-sig"), len(rows)


def _sum_by_currency(rows, key: str = "remaining", lang: str | None = None) -> str:
    """«1 500 000 so'm + $200» — valyutalar aralashtirilmaydi."""
    lang = _L(lang)
    by_currency: dict[str, float] = {}
    for r in rows:
        cur = r.get("currency") or "som"
        by_currency[cur] = by_currency.get(cur, 0.0) + float(r[key])
    return " + ".join(fmt_money(v, c, lang) for c, v in
                      sorted(by_currency.items(), key=lambda kv: kv[0] != "som"))


def debt_progress_line(d: dict, lang: str | None = None) -> str:
    """«▓▓▓░░░░░░░ 30% · to'langan 300 000 / 1 000 000»."""
    lang = _L(lang)
    cur = d.get("currency") or "som"
    amount = float(d["amount"]) or 1.0
    share = max(0.0, min(1.0, float(d["paid"]) / amount))
    paid = pick(lang, "to'langan", "выплачено")
    return (f"<code>{_bar(share)}</code> {share * 100:.0f}% · {paid} "
            f"{fmt_money(d['paid'], cur, lang)} / {fmt_money(d['amount'], cur, lang)}")


def debts_text(user_id: int, lang: str | None = None) -> str:
    """Ochiq qarzlar: bir odamning qarzlari bitta guruhda, jami bilan.

    Har bir qarzda qoldiq, sana, muddat va (qisman to'langan bo'lsa)
    progress: asli / to'langan. Valyutalar aralashtirilmaydi.
    """
    lang = _L(lang)
    rows = db.open_debts(user_id)
    if not rows:
        return pick(lang, "🤝 Ochiq qarz yo'q.", "🤝 Открытых долгов нет.")

    lines = [pick(lang, "🤝 <b>Qarzlar</b>", "🤝 <b>Долги</b>"), ""]
    for kind, title in (
            (config.KIND_QARZ_BERDIM,
             pick(lang, "📤 <b>Menga qarzdorlar</b>", "📤 <b>Должны мне</b>")),
            (config.KIND_QARZ_OLDIM,
             pick(lang, "📥 <b>Men qarzdorman</b>", "📥 <b>Я должен</b>"))):
        group = [r for r in rows if r["kind"] == kind]
        if not group:
            continue
        lines.append(f"{title} — {_sum_by_currency(group, lang=lang)}")
        people: dict[str, list[dict]] = {}
        for r in group:
            people.setdefault(db.person_key(r["person"]), []).append(r)
        for debts in people.values():
            who = esc(debts[0]["person"] or pick(lang, "noma'lum", "не указан"))
            head = f"👤 <b>{who}</b> — {_sum_by_currency(debts, lang=lang)}"
            if len(debts) > 1:
                n = len(debts)
                count = (f"{n} " + _plural(n, "долг", "долга", "долгов")
                         if _is_ru(lang) else pick(lang, f"{n} ta qarz"))
                head += f" <i>({count})</i>"
            lines.append(head)
            for r in debts:
                cur = r.get("currency") or "som"
                due = (f" · ⏰ {fmt_date(r['due_on'], lang)}" if r.get("due_on") else "")
                note = f" · {esc(r['note'])}" if r.get("note") and r["note"] != "qarz" else ""
                lines.append(f"   <code>#{r['id']}</code> {fmt_date(r['occurred_on'], lang)}"
                             f"{note}{due} · {pick(lang, 'qoldiq', 'остаток')} "
                             f"<b>{fmt_money(r['remaining'], cur, lang)}</b>")
                if r.get("paid"):
                    lines.append("   " + debt_progress_line(r, lang))
        lines.append("")

    lines.append(pick(lang,
                      "<i>Pastdagi tugmalar: 💸 qisman to'lash, ✅ to'liq yopish.</i>",
                      "<i>Кнопки ниже: 💸 частичная оплата, ✅ закрыть полностью.</i>"))
    return "\n".join(lines)


def receipt_text(data: dict, day_total: float | None = None,
                 lang: str | None = None) -> str:
    """Chek tahlili: kategoriyalar kesimi, tekshiruv natijasi, to'liq ro'yxat.

    Mahsulot summalari bu yerga kelganda chekdagi yakuniy jamiga
    moslangan (`ai.apply_receipt_total`): chegirma kategoriyalar o'rtasida
    taqsimlangan, ya'ni ulushlar va saqlangan summa bir xil hisobda.
    """
    lang = _L(lang)
    items = data["mahsulotlar"]
    check = data["tekshiruv"]
    stored = round(sum(i["summa"] for i in items), 2)
    # Chek dollarda bo'lishi ham mumkin — summalar shu valyutada ko'rsatiladi.
    cur = data.get("valyuta") or "som"

    def money(value: float, currency: str | None = None) -> str:
        return fmt_money(value, currency or cur, lang)

    head = pick(lang, "🧾 <b>Chek qabul qilindi</b>", "🧾 <b>Чек принят</b>")
    if data["dokon"]:
        head = f"🧾 <b>{esc(data['dokon'])}</b>"
    lines = [head,
             f"📅 {fmt_date(data['sana'], lang)} · {_items_word(len(items), lang)}",
             ""]

    # Kategoriyalar kesimi — foizli diagramma bilan.
    by_cat: dict[str, list[float]] = {}
    for item in items:
        by_cat.setdefault(item["kategoriya"], []).append(item["summa"])

    lines.append(pick(lang, "<b>Kategoriyalar bo'yicha:</b>",
                      "<b>По категориям:</b>"))
    for name, amounts in sorted(by_cat.items(), key=lambda kv: sum(kv[1]), reverse=True):
        subtotal = sum(amounts)
        share = subtotal / stored if stored else 0
        icon = config.CATEGORY_ICONS.get(name, "•")
        lines.append(
            f"{icon} {esc(i18n.category_name(lang, name))} — "
            f"{money(subtotal)} ({share * 100:.0f}%)"
        )
        lines.append(f"   <code>{_bar(share)}</code> {_count(len(amounts), lang)}")

    lines.append("")
    lines.append(f"💵 {pick(lang, 'Mahsulotlar jami', 'Итого по товарам')}: "
                 f"{money(check['hisoblangan'])}")

    if data.get("chegirma"):
        tail = (pick(lang, " <i>(narxlarda hisobga olingan)</i>",
                     " <i>(учтена в ценах)</i>")
                if check.get("narxlar") == "chegirmadan_keyin" else "")
        lines.append(f"🏷 {pick(lang, 'Chegirma', 'Скидка')}: −{money(data['chegirma'])}{tail}")

    # Tekshiruv — chekdagi JAMI bilan solishtirish.
    total_label = pick(lang, "Chekdagi jami", "Итого в чеке")
    if check["holat"] == "mos":
        lines.append(f"✅ <b>{total_label}: {money(check['chekdagi'])}</b> — "
                     + pick(lang, "mos", "совпадает"))
    elif check["holat"] == "farqli":
        lines.append(f"⚠️ <b>{total_label}: {money(check['chekdagi'])}</b>")
        farq = check["farq"]
        if _is_ru(lang):
            lines.append(
                f"   <i>Товаров получилось на {money(abs(farq))} "
                f"{'больше' if farq > 0 else 'меньше'} — "
                f"некоторые строки могли быть прочитаны неверно. "
                f"Сохранённая сумма приравнена к итогу в чеке.</i>")
        else:
            yon = "ortiq" if farq > 0 else "kam"
            lines.append(pick(
                lang,
                f"   <i>Mahsulotlar {money(abs(farq))} {yon} chiqdi — "
                f"ba'zi qatorlar noto'g'ri o'qilgan bo'lishi mumkin. "
                f"Saqlangan summa chekdagi jamiga tenglandi.</i>"))
    else:
        lines.append(pick(
            lang,
            "<i>ℹ️ Chekda yakuniy summa ko'rinmadi — tekshirib bo'lmadi.</i>",
            "<i>ℹ️ Итоговая сумма в чеке не видна — проверить не удалось.</i>"))

    # Eng qimmat mahsulot — tahlil uchun foydali (chekdagi narxi bilan).
    if len(items) > 1:
        top = max(items, key=lambda i: i.get("summa_asl", i["summa"]))
        lines.append(
            f"🔝 {pick(lang, 'Eng qimmati', 'Самый дорогой')}: {esc(top['nomi'])} — "
            f"{money(top.get('summa_asl', top['summa']))}"
        )

    if day_total:
        lines.append("")
        lines.append("<i>" + pick(lang, "Bugungi umumiy chiqim:",
                                  "Всего расходов сегодня:")
                     + f" {fmt_money(day_total, lang=lang)}</i>")

    return "\n".join(lines)


def receipt_items_text(rows, lang: str | None = None) -> str:
    """Chekdagi mahsulotlarning to'liq ro'yxati (alohida xabar uchun)."""
    lang = _L(lang)
    if not rows:
        return pick(lang, "Bu chek uchun yozuv topilmadi.",
                    "Для этого чека записей не найдено.")
    n = len(rows)
    count = (f"{n} " + _plural(n, "позиция", "позиции", "позиций")
             if _is_ru(lang) else pick(lang, f"{n} ta"))
    heading = pick(lang, "To'liq ro'yxat", "Полный список")
    lines = [f"🧾 <b>{heading}</b> — {count}", ""]
    for r in rows:
        icon = config.CATEGORY_ICONS.get(r["category"], "•")
        cur = r["currency"] if "currency" in r.keys() else "som"
        name = r["note"] or i18n.category_name(lang, r["category"])
        lines.append(
            f"{icon} {esc(name)} — {fmt_money(r['amount'], cur, lang)}"
            f" <code>#{r['id']}</code>"
        )
    lines.append("")
    lines.append(pick(lang,
                      "<i>Bittasini o'chirish:</i> <code>/ochir 12</code>",
                      "<i>Удалить одну позицию:</i> <code>/ochir 12</code>"))
    return "\n".join(lines)


def saved_text(rows: list[dict], lang: str | None = None) -> str:
    """Saqlangandan keyin ko'rsatiladigan tasdiq matni."""
    lang = _L(lang)
    if len(rows) == 1:
        r = rows[0]
        cur = r.get("valyuta", "som")
        icon = config.KIND_ICONS[r["turi"]]
        cat_icon = config.CATEGORY_ICONS.get(r["kategoriya"], "")
        cat_name = i18n.category_name(lang, r["kategoriya"])
        saved = pick(lang, "saqlandi", "сохранено")
        body = [
            f"{icon} <b>{esc(i18n.kind_label(lang, r['turi']))}</b> {saved}",
            f"💵 {fmt_money(r['summa'], cur, lang)}",
            f"{cat_icon} {esc(cat_name)}",
        ]
        # Izoh kategoriyaning o'zi bo'lsa takrorlanmaydi: qarz yozuvida
        # «qarz | qarz» ikki marta chiqardi.
        shown = {r["kategoriya"].casefold(),
                 config.category_label(r["kategoriya"]).casefold(),
                 cat_name.casefold()}
        if r.get("izoh") and r["izoh"].strip().casefold() not in shown:
            body.append(f"📝 {esc(r['izoh'])}")
        if r.get("shaxs"):
            body.append(f"👤 {esc(r['shaxs'])}")
        body.append(f"📅 {fmt_date(r['sana'], lang)}")
        return "\n".join(body)

    n = len(rows)
    title = (f"{n} " + _plural(n, "запись сохранена", "записи сохранены", "записей сохранено")
             if _is_ru(lang) else pick(lang, f"{n} ta yozuv saqlandi"))
    lines = [f"✅ <b>{title}</b>", ""]
    lines += [saved_line(r, lang) for r in rows]
    lines.append("")
    lines.append(pick(lang, "<i>Tuzatish uchun pastdagi «✏️» tugmasini bosing.</i>",
                      "<i>Чтобы исправить, нажмите кнопку «✏️» ниже.</i>"))
    return "\n".join(lines)


def saved_line(r: dict, lang: str | None = None) -> str:
    """Ko'p yozuvli xabardagi bitta qator — kategoriyasi bilan:
    🔻 8 000 so'm · nonga · 🥦 oziq-ovqat

    Qarz turlarida kategoriya o'rniga shaxs (yoki tur nomi) — ularning
    kategoriyasi doim «qarz» va hech narsa aytmaydi.
    """
    lang = _L(lang)
    icon = config.KIND_ICONS[r["turi"]]
    money = fmt_money(r["summa"], r.get("valyuta", "som"), lang)
    note = r.get("izoh") or ""
    if r["turi"] in config.DEBT_KINDS:
        tail = esc(r.get("shaxs") or i18n.kind_label(lang, r["turi"]))
    else:
        cat = r["kategoriya"]
        tail = (f"{config.CATEGORY_ICONS.get(cat, '')} "
                f"{esc(i18n.category_name(lang, cat))}").strip()
    parts = [money] + ([esc(note)] if note else []) + [tail]
    return f"{icon} " + " · ".join(parts)
