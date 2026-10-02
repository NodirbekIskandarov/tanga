"""Hisobotlarni matnga aylantirish va sana oraliqlarini hisoblash.

Telegram'ga HTML parse_mode bilan yuboriladi, shuning uchun foydalanuvchi
kiritgan har qanday matn esc() orqali o'tkaziladi.
"""

from __future__ import annotations

from datetime import date, datetime, timedelta
from html import escape

import config
import db

UZ_MONTHS = [
    "yanvar", "fevral", "mart", "aprel", "may", "iyun",
    "iyul", "avgust", "sentabr", "oktabr", "noyabr", "dekabr",
]


def esc(text) -> str:
    return escape(str(text or ""), quote=False)


def today() -> date:
    return datetime.now(config.TZ).date()


def fmt_money(value: float, currency: str = "som") -> str:
    """1250000 -> "1 250 000 so'm"; USD uchun 99.5 -> "$99.5" """
    if currency == config.CURRENCY_USD:
        v = round(float(value), 2)
        text = f"{v:,.2f}".rstrip("0").rstrip(".") if v % 1 else f"{int(v):,}"
        return f"${text.replace(',', ' ')}"
    rounded = round(float(value))
    return f"{rounded:,}".replace(",", " ") + f" {config.CURRENCY}"


def fmt_date(iso: str) -> str:
    try:
        d = date.fromisoformat(iso)
    except (ValueError, TypeError):
        return str(iso)
    return f"{d.day}-{UZ_MONTHS[d.month - 1]}"


def period_range(period: str, ref: date | None = None) -> tuple[date, date, str]:
    """period: bugun | kecha | hafta | oy | otgan_oy | yil"""
    ref = ref or today()
    if period == "bugun":
        return ref, ref, "Bugun"
    if period == "kecha":
        y = ref - timedelta(days=1)
        return y, y, "Kecha"
    if period == "hafta":
        start = ref - timedelta(days=ref.weekday())
        return start, ref, "Shu hafta"
    if period == "oy":
        return ref.replace(day=1), ref, f"{UZ_MONTHS[ref.month - 1].capitalize()} oyi"
    if period == "otgan_oy":
        last_day_prev = ref.replace(day=1) - timedelta(days=1)
        start = last_day_prev.replace(day=1)
        return start, last_day_prev, f"{UZ_MONTHS[start.month - 1].capitalize()} oyi"
    if period == "yil":
        return ref.replace(month=1, day=1), ref, f"{ref.year}-yil"
    return ref.replace(day=1), ref, "Davr"


def _bar(share: float, width: int = 10) -> str:
    filled = max(0, min(width, round(share * width)))
    return "█" * filled + "░" * (width - filled)


def debt_lines(t: dict, currency: str = "som") -> list[str]:
    """Davr ichidagi qarz harakati — kirim/chiqim va «Farq» dan ALOHIDA.

    Qarz berish va qaytarish pul harakati, lekin xarajat ham, daromad
    ham emas: shuning uchun yuqoridagi jamlarga qo'shilmaydi, faqat shu
    yerda ko'rinadi.
    """
    rows = [
        (config.KIND_QARZ_BERDIM, "Qarz berdim"),
        (config.KIND_QARZ_OLDIM, "Qarz oldim"),
        (config.KIND_QARZ_QAYTARDIM, "Qarzimni qaytardim"),
        (config.KIND_QARZ_QAYTDI, "Menga qaytarildi"),
    ]
    out = [f"{config.KIND_ICONS[k]} {label}: {fmt_money(t[k], currency)}"
           for k, label in rows if t.get(k)]
    if not out:
        return []
    return ["", "<b>Qarzlar</b> <i>(chiqimga kirmaydi)</i>"] + out


def _currency_block(user_id: int, start: date, end: date, currency: str, days: int) -> list[str]:
    """Bitta valyuta uchun kirim/chiqim/farq va kategoriyalar bloki."""
    t = db.totals(user_id, start, end, currency)
    kirim = t[config.KIND_KIRIM]
    chiqim = t[config.KIND_CHIQIM]
    balans = kirim - chiqim

    lines: list[str] = []
    lines.append(f"🔺 Kirim:  {fmt_money(kirim, currency)}")
    lines.append(f"🔻 Chiqim: {fmt_money(chiqim, currency)}")
    lines.append(f"{'🟢' if balans >= 0 else '🔴'} Farq:   {fmt_money(balans, currency)}")

    cats = db.by_category(user_id, start, end, config.KIND_CHIQIM, currency)
    if cats:
        lines.append("")
        lines.append("<b>Chiqim kategoriyalari:</b>")
        for name, total, cnt in cats[:8]:
            share = total / chiqim if chiqim else 0
            icon = config.CATEGORY_ICONS.get(name, "•")
            lines.append(f"{icon} {esc(config.category_label(name))} — "
                         f"{fmt_money(total, currency)} ({share * 100:.0f}%)")
            lines.append(f"   <code>{_bar(share)}</code> {cnt} ta")

    lines += debt_lines(t, currency)

    if chiqim and days >= 2:
        lines.append("")
        lines.append(f"<i>Kuniga o'rtacha: {fmt_money(chiqim / days, currency)}</i>")

    return lines


def summary_text(user_id: int, period: str) -> str:
    """Davr hisoboti — barcha valyutalar bitta jamlanmada.

    Odamning hamyoni bitta: dollarda to'lagan puli ham o'sha umumiy
    mablag'idan chiqadi. Shuning uchun jamlanma asosiy valyutada
    beriladi, chet el valyutasidagi ulush esa alohida eslatiladi.
    Har bir yozuv o'z kunidagi kurs bilan o'girilgan — kurs bugun
    o'zgarsa ham o'tgan oy hisoboti o'zgarmaydi.
    """
    start, end, label = period_range(period)
    days = (end - start).days + 1

    data = db.totals_unified(user_id, start, end)
    t, foreign = data["totals"], data["foreign"]
    kirim = t[config.KIND_KIRIM]
    chiqim = t[config.KIND_CHIQIM]
    balans = kirim - chiqim

    lines = [f"📊 <b>{esc(label)}</b>", ""]
    if not any(t.values()):
        lines.append("<i>Bu davrda yozuv yo'q.</i>")
        return "\n".join(lines)

    lines.append(f"🔺 Kirim:  {fmt_money(kirim)}")
    lines.append(f"🔻 Chiqim: {fmt_money(chiqim)}")
    lines.append(f"{'🟢' if balans >= 0 else '🔴'} Farq:   {fmt_money(balans)}")

    if foreign:
        parts = []
        for cur, info in foreign.items():
            parts.append(f"{fmt_money(info['orig'], cur)} ≈ {fmt_money(info['base'])}")
        lines.append("")
        lines.append(f"<i>Shundan chet el valyutasida: {' · '.join(parts)}</i>")

    cats = db.by_category_unified(user_id, start, end, config.KIND_CHIQIM)
    if cats:
        lines.append("")
        lines.append("<b>Chiqim kategoriyalari:</b>")
        for name, total, cnt in cats[:8]:
            share = total / chiqim if chiqim else 0
            icon = config.CATEGORY_ICONS.get(name, "•")
            lines.append(f"{icon} {esc(config.category_label(name))} — "
                         f"{fmt_money(total)} ({share * 100:.0f}%)")
            lines.append(f"   <code>{_bar(share)}</code> {cnt} ta")

    lines += debt_lines(t)

    # Jamg'arma ATAYLAB "Farq" dan tashqarida turadi: u sarflangan pul
    # emas, shuning uchun chiqimga qo'shilmaydi. Lekin daromadga nisbatan
    # ulushi ko'rsatiladi — kitobdagi 10 % qoidasi shu joyda ko'rinadi.
    jamgardim = t[config.KIND_JAMGARMA] - t[config.KIND_JAMGARMA_YECHDIM]
    if jamgardim:
        rate = db.savings_rate(user_id)
        lines.append("")
        share = f" — daromadning {jamgardim / kirim * 100:.0f}%i" if kirim > 0 else ""
        lines.append(f"🏦 Jamg'arma: {fmt_money(jamgardim)}{share}")
        if kirim > 0 and jamgardim >= kirim * rate:
            lines.append(f"<i>✅ {rate * 100:.0f}% qoidasi bajarildi</i>")

    if chiqim and days >= 2:
        lines.append("")
        lines.append(f"<i>Kuniga o'rtacha: {fmt_money(chiqim / days)}</i>")

    text = "\n".join(lines)
    # Hisobot matni bu faylda o'zbekcha yozilgan (butun fayl shunday),
    # shuning uchun quyidagi bo'limlar ham shu yerda turadi.
    if period in ("oy", "otgan_oy"):
        text += _monthly_score(t, db.savings_rate(user_id))
    elif period == "yil":
        text += _yearly_savings(user_id, start, end)
    return text


def _monthly_score(t: dict, rate: float) -> str:
    """Oylik uch savol: 10 % jamg'ardingmi, topganingdan kam
    sarfladingmi, qarzing ko'paymadimi.

    Baho ATAYLAB oddiy: uchta savol, uchta belgi. Murakkab ball tizimi
    o'qilmaydi.

    Foydalanuvchiga ko'rinadigan matnda manba (kitob) tilga olinmaydi —
    maslahat o'z-o'zidan tushunarli bo'lishi kerak.
    """
    kirim = t[config.KIND_KIRIM]
    chiqim = t[config.KIND_CHIQIM]
    saved = t[config.KIND_JAMGARMA] - t[config.KIND_JAMGARMA_YECHDIM]
    new_debt = t[config.KIND_QARZ_OLDIM]

    # Daromad yozilmagan oyda baho berish adolatsiz — birinchi ikki
    # savolning ma'nosi qolmaydi.
    if kirim <= 0:
        return ""

    rows = [
        (saved >= kirim * rate,
         f"Daromadning {rate * 100:.0f}% i jamg'arildi",
         f"{rate * 100:.0f}% jamg'arilmadi"),
        (chiqim < kirim,
         "Daromaddan kam sarflandi", "Daromaddan ko'p sarflandi"),
        (new_debt <= 0, "Qarz ko'paymadi", "Yangi qarz olindi"),
    ]
    score = sum(1 for ok, _, _ in rows if ok)
    body = "\n".join(f"{'✅' if ok else '❌'} {yes if ok else no}"
                     for ok, yes, no in rows)
    return f"\n\n📜 <b>Oylik baho: {score}/3</b>\n{body}"


def _yearly_savings(user_id: int, start: date, end: date) -> str:
    """Yillik hisobotga jamg'arma bo'limi."""
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
    share = (f" — daromadingizning {saved / income * 100:.0f}%i"
             if income > 0 else "")
    return (f"\n\n🏦 <b>Yil davomida jamg'arma</b>\n"
            f"Jami: <b>{fmt_money(saved)}</b>{share}\n"
            f"{rate * 100:.0f}% qoidasi bajarilgan oylar: "
            f"<b>{good} / {len(months)}</b>")


def transaction_line(row, with_id: bool = True) -> str:
    icon = config.KIND_ICONS.get(row["kind"], "•")
    cat_icon = config.CATEGORY_ICONS.get(row["category"], "")
    label = config.category_label(row["category"])
    person = f" — {esc(row['person'])}" if row["person"] else ""
    tail = f" <code>#{row['id']}</code>" if with_id else ""
    currency = row["currency"] if "currency" in row.keys() else "som"
    # Izoh bo'lsa kategoriya ham yonida ko'rinadi: «nonga · 🥦 oziq-ovqat».
    # Qarz turlarida kategoriya doim «qarz» — uning o'rnida shaxs turadi.
    if row["kind"] in config.DEBT_KINDS:
        body = esc(row["note"] or config.KIND_LABELS.get(row["kind"], label))
    elif row["note"]:
        body = f"{esc(row['note'])} · {cat_icon} {esc(label)}"
    else:
        body = f"{cat_icon} {esc(label)}"
    return (
        f"{icon} {fmt_money(row['amount'], currency)} · {body}{person}"
        f" · <i>{fmt_date(row['occurred_on'])}</i>{tail}"
    )


def receipt_line(entry: dict, with_id: bool = True) -> str:
    """Chek bitta qatorda: 🧾 Korzinka cheki — 260 800 so'm (15 mahsulot) · 1-oktabr"""
    shop = (entry.get("shop") or "").strip()
    name = f"{esc(shop)} cheki" if shop else "Chek"
    tail = f" <code>#{entry['id']}</code>" if with_id else ""
    return (
        f"🧾 {name} — {fmt_money(entry['amount'], entry.get('currency') or 'som')} "
        f"({entry['n']} mahsulot) · <i>{fmt_date(entry['occurred_on'])}</i>{tail}"
    )


def recent_text(user_id: int, limit: int = 12) -> str:
    entries = db.recent_entries(user_id, limit)
    if not entries:
        return "Hozircha yozuv yo'q."
    lines = [f"🧾 <b>Oxirgi {len(entries)} ta yozuv</b>", ""]
    for e in entries:
        lines.append(receipt_line(e) if e["receipt_id"] else transaction_line(e))
    lines.append("")
    lines.append("<i>O'chirish uchun:</i> <code>/ochir 12</code> "
                 "<i>(chek raqami butun chekni o'chiradi)</i>")
    return "\n".join(lines)


CSV_HEADER = ["id", "sana", "turi", "summa", "valyuta", "kategoriya", "izoh",
              "shaxs", "yopilgan", "chek_id", "dokon"]


def csv_bytes(user_id: int) -> tuple[bytes, int]:
    """Barcha yozuvlar CSV ko'rinishida (Excel uchun BOM bilan).

    Chek mahsulotlari alohida qator bo'lib qoladi va har birida o'z
    cheki identifikatori (`chek_id`) va do'koni turadi — chekni Excel'da
    qayta yig'ish mumkin bo'lsin.
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


def debts_text(user_id: int) -> str:
    rows = db.open_debts(user_id)
    if not rows:
        return "🤝 Ochiq qarz yo'q."

    berdim = [r for r in rows if r["kind"] == config.KIND_QARZ_BERDIM]
    oldim = [r for r in rows if r["kind"] == config.KIND_QARZ_OLDIM]

    lines = ["🤝 <b>Qarzlar</b>", ""]
    for title, group in (
        ("📤 <b>Menga qarzdorlar</b>", berdim),
        ("📥 <b>Men qarzdorman</b>", oldim),
    ):
        if not group:
            continue
        # Valyutalar aralashtirilmaydi — har biri uchun alohida jami.
        by_currency: dict[str, float] = {}
        for r in group:
            cur = r["currency"] if "currency" in r.keys() else "som"
            by_currency[cur] = by_currency.get(cur, 0.0) + r["remaining"]
        totals_str = " + ".join(
            fmt_money(v, c) for c, v in sorted(by_currency.items(), key=lambda kv: kv[0] != "som")
        )
        lines.append(f"{title} — {totals_str}")
        for r in group:
            who = esc(r["person"] or "noma'lum")
            cur = r["currency"] if "currency" in r.keys() else "som"
            # Qisman qaytarilgan bo'lsa — qoldiq va asl summa ikkalasi.
            paid = ""
            if r["remaining"] < float(r["amount"]):
                paid = f" <i>(qoldiq; asli {fmt_money(r['amount'], cur)})</i>"
            if r.get("due_on"):
                paid += f" ⏰ {fmt_date(r['due_on'])}"
            lines.append(
                f"   • {who}: {fmt_money(r['remaining'], cur)}{paid}"
                f" ({fmt_date(r['occurred_on'])}) <code>#{r['id']}</code>"
            )
        lines.append("")

    lines.append("<i>Yopish uchun:</i> <code>/yopdim 12</code>")
    return "\n".join(lines)


def receipt_text(data: dict, day_total: float | None = None) -> str:
    """Chek tahlili: kategoriyalar kesimi, tekshiruv natijasi, to'liq ro'yxat.

    Mahsulot summalari bu yerga kelganda chekdagi yakuniy jamiga
    moslangan (`ai.apply_receipt_total`): chegirma kategoriyalar o'rtasida
    taqsimlangan, ya'ni ulushlar va saqlangan summa bir xil hisobda.
    """
    items = data["mahsulotlar"]
    check = data["tekshiruv"]
    stored = round(sum(i["summa"] for i in items), 2)
    # Chek dollarda bo'lishi ham mumkin — summalar shu valyutada ko'rsatiladi.
    cur = data.get("valyuta") or "som"

    head = "🧾 <b>Chek qabul qilindi</b>"
    if data["dokon"]:
        head = f"🧾 <b>{esc(data['dokon'])}</b>"
    lines = [head, f"📅 {fmt_date(data['sana'])} · {len(items)} ta mahsulot", ""]

    # Kategoriyalar kesimi — foizli diagramma bilan.
    by_cat: dict[str, list[float]] = {}
    for item in items:
        by_cat.setdefault(item["kategoriya"], []).append(item["summa"])

    lines.append("<b>Kategoriyalar bo'yicha:</b>")
    for name, amounts in sorted(by_cat.items(), key=lambda kv: sum(kv[1]), reverse=True):
        subtotal = sum(amounts)
        share = subtotal / stored if stored else 0
        icon = config.CATEGORY_ICONS.get(name, "•")
        lines.append(
            f"{icon} {esc(config.category_label(name))} — "
            f"{fmt_money(subtotal, cur)} ({share * 100:.0f}%)"
        )
        lines.append(f"   <code>{_bar(share)}</code> {len(amounts)} ta")

    lines.append("")
    lines.append(f"💵 Mahsulotlar jami: {fmt_money(check['hisoblangan'], cur)}")

    if data.get("chegirma"):
        tail = (" <i>(narxlarda hisobga olingan)</i>"
                if check.get("narxlar") == "chegirmadan_keyin" else "")
        lines.append(f"🏷 Chegirma: −{fmt_money(data['chegirma'], cur)}{tail}")

    # Tekshiruv — chekdagi JAMI bilan solishtirish.
    if check["holat"] == "mos":
        lines.append(f"✅ <b>Chekdagi jami: {fmt_money(check['chekdagi'], cur)}</b> — mos")
    elif check["holat"] == "farqli":
        lines.append(f"⚠️ <b>Chekdagi jami: {fmt_money(check['chekdagi'], cur)}</b>")
        farq = check["farq"]
        yon = "ortiq" if farq > 0 else "kam"
        lines.append(
            f"   <i>Mahsulotlar {fmt_money(abs(farq), cur)} {yon} chiqdi — "
            f"ba'zi qatorlar noto'g'ri o'qilgan bo'lishi mumkin. "
            f"Saqlangan summa chekdagi jamiga tenglandi.</i>"
        )
    else:
        lines.append("<i>ℹ️ Chekda yakuniy summa ko'rinmadi — tekshirib bo'lmadi.</i>")

    # Eng qimmat mahsulot — tahlil uchun foydali (chekdagi narxi bilan).
    if len(items) > 1:
        top = max(items, key=lambda i: i.get("summa_asl", i["summa"]))
        lines.append(
            f"🔝 Eng qimmati: {esc(top['nomi'])} — "
            f"{fmt_money(top.get('summa_asl', top['summa']), cur)}"
        )

    if day_total:
        lines.append("")
        lines.append(f"<i>Bugungi umumiy chiqim: {fmt_money(day_total)}</i>")

    return "\n".join(lines)


def receipt_items_text(rows) -> str:
    """Chekdagi mahsulotlarning to'liq ro'yxati (alohida xabar uchun)."""
    if not rows:
        return "Bu chek uchun yozuv topilmadi."
    lines = [f"🧾 <b>To'liq ro'yxat</b> — {len(rows)} ta", ""]
    for r in rows:
        icon = config.CATEGORY_ICONS.get(r["category"], "•")
        cur = r["currency"] if "currency" in r.keys() else "som"
        lines.append(
            f"{icon} {esc(r['note'] or r['category'])} — {fmt_money(r['amount'], cur)}"
            f" <code>#{r['id']}</code>"
        )
    lines.append("")
    lines.append("<i>Bittasini o'chirish:</i> <code>/ochir 12</code>")
    return "\n".join(lines)


def saved_text(rows: list[dict]) -> str:
    """Saqlangandan keyin ko'rsatiladigan tasdiq matni."""
    if len(rows) == 1:
        r = rows[0]
        cur = r.get("valyuta", "som")
        icon = config.KIND_ICONS[r["turi"]]
        cat_icon = config.CATEGORY_ICONS.get(r["kategoriya"], "")
        body = [
            f"{icon} <b>{esc(config.KIND_LABELS[r['turi']])}</b> saqlandi",
            f"💵 {fmt_money(r['summa'], cur)}",
            f"{cat_icon} {esc(config.category_label(r['kategoriya']))}",
        ]
        if r.get("izoh"):
            body.append(f"📝 {esc(r['izoh'])}")
        if r.get("shaxs"):
            body.append(f"👤 {esc(r['shaxs'])}")
        body.append(f"📅 {fmt_date(r['sana'])}")
        return "\n".join(body)

    lines = [f"✅ <b>{len(rows)} ta yozuv saqlandi</b>", ""]
    lines += [saved_line(r) for r in rows]
    lines.append("")
    lines.append("<i>Tuzatish uchun pastdagi «✏️» tugmasini bosing.</i>")
    return "\n".join(lines)


def saved_line(r: dict) -> str:
    """Ko'p yozuvli xabardagi bitta qator — kategoriyasi bilan:
    🔻 8 000 so'm · nonga · 🥦 oziq-ovqat

    Qarz turlarida kategoriya o'rniga shaxs (yoki tur nomi) — ularning
    kategoriyasi doim «qarz» va hech narsa aytmaydi.
    """
    icon = config.KIND_ICONS[r["turi"]]
    money = fmt_money(r["summa"], r.get("valyuta", "som"))
    note = r.get("izoh") or ""
    if r["turi"] in config.DEBT_KINDS:
        tail = esc(r.get("shaxs") or config.KIND_LABELS[r["turi"]])
    else:
        cat = r["kategoriya"]
        tail = f"{config.CATEGORY_ICONS.get(cat, '')} {esc(config.category_label(cat))}".strip()
    parts = [money] + ([esc(note)] if note else []) + [tail]
    return f"{icon} " + " · ".join(parts)
