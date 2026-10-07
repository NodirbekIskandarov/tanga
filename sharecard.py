"""Hisobotlarni rasmga aylantiradi: ulashish kartasi va oylar solishtirmasi.

Maqsad — foydalanuvchi o'z natijasini do'stlariga ko'rsatsin. Rasm pastida
bot nomi turadi, ya'ni har bir ulashish bepul reklama bo'ladi.

Pillow yoki shrift topilmasa — None qaytaradi, chaqiruvchi matnli
hisobotga qaytadi. Rasm yo'qligi xato emas.
"""

from __future__ import annotations

import io
import os
import logging
from pathlib import Path

import config

log = logging.getLogger("tanga.sharecard")

W, H = 1080, 1350          # Telegram va Instagram uchun qulay nisbat (4:5)

# Ranglar — Mini App palitrasi bilan bir xil oila.
BG_TOP = (16, 22, 34)
BG_BOTTOM = (28, 38, 56)
INK = (238, 242, 248)
INK_2 = (150, 165, 187)
ACCENT = (86, 170, 232)
GOOD = (95, 200, 140)
BAD = (240, 130, 118)
CARD = (26, 35, 51)

FONT_CANDIDATES = [
    "/usr/share/fonts/truetype/dejavu/DejaVuSans.ttf",
    "/usr/share/fonts/truetype/dejavu/DejaVuSans-Bold.ttf",
    "/usr/share/fonts/TTF/DejaVuSans.ttf",
    "C:/Windows/Fonts/segoeui.ttf",
    "C:/Windows/Fonts/arial.ttf",
]
BOLD_CANDIDATES = [
    "/usr/share/fonts/truetype/dejavu/DejaVuSans-Bold.ttf",
    "/usr/share/fonts/TTF/DejaVuSans-Bold.ttf",
    "C:/Windows/Fonts/segoeuib.ttf",
    "C:/Windows/Fonts/arialbd.ttf",
]


def _find(candidates: list[str]) -> str | None:
    for path in candidates:
        if Path(path).exists():
            return path
    return None



_MARK_CACHE: dict[int, "Image.Image | None"] = {}


def _brand_mark(size: int):
    """Loyiha ikonkasi (tilla tanga) — ulashish rasmining pastida.

    Fayl topilmasa None qaytaradi va rasm ikonkasiz chiziladi: brend
    belgisi yo'qligi uchun butun hisobot yaratilmay qolmasligi kerak.
    """
    if size in _MARK_CACHE:
        return _MARK_CACHE[size]
    # Pillow shu modulda ATAYLAB kech import qilinadi (u o'rnatilmagan
    # bo'lsa ham bot ishga tushishi kerak), shuning uchun bu yerda ham
    # funksiya ichida import qilamiz.
    from PIL import Image, ImageDraw

    path = os.path.join(os.path.dirname(os.path.abspath(__file__)),
                        "static", "icons", "icon.png")
    try:
        mark = Image.open(path).convert("RGBA").resize((size, size), Image.LANCZOS)
        # Ikonkada tilla fon butun kvadratni to'ldiradi. Qorong'i kartada
        # kvadrat g'alati ko'rinadi — tanganing o'zi dumaloq bo'lgani uchun
        # chetlarini aylana bo'yicha kesamiz (silliq chet uchun 4x katta
        # niqob chizib, keyin kichraytiramiz).
        big = size * 4
        circle = Image.new("L", (big, big), 0)
        ImageDraw.Draw(circle).ellipse((0, 0, big - 1, big - 1), fill=255)
        mark.putalpha(circle.resize((size, size), Image.LANCZOS))
    except FileNotFoundError:
        log.info("Brend ikonkasi topilmadi: %s", path)
        mark = None
    except Exception:
        log.exception("Brend ikonkasini o'qib bo'lmadi: %s", path)
        mark = None
    _MARK_CACHE[size] = mark
    return mark

def available() -> bool:
    try:
        import PIL  # noqa: F401
    except ImportError:
        return False
    return _find(FONT_CANDIDATES) is not None


def _money(value: float, currency: str = "som", lang: str | None = None) -> str:
    """Rasmda joy kam — katta sonlarni qisqartiramiz."""
    import i18n
    if currency == "usd":
        return f"${value:,.2f}".replace(",", " ")
    v = abs(value)
    if v >= 1_000_000:
        text = f"{value / 1_000_000:.1f} {i18n.pick(lang, 'mln', 'млн')}".replace(".0 ", " ")
    elif v >= 1_000:
        text = f"{value / 1_000:.0f} {i18n.pick(lang, 'ming', 'тыс.')}"
    else:
        text = f"{value:.0f}"
    return f"{text} {i18n.money_unit(lang)}"


def _entries_label(n: int, lang: str | None) -> str:
    import i18n
    if i18n.normalize(lang) == "ru":
        word = ("запись" if n % 10 == 1 and n % 100 != 11 else
                "записи" if 2 <= n % 10 <= 4 and not 12 <= n % 100 <= 14 else
                "записей")
        return f"{n} {word}"
    return i18n.pick(lang, f"{n} ta yozuv")


def build(*, title: str, kirim: float, chiqim: float, categories: list[tuple],
          currency: str = "som", entries: int = 0,
          bot_username: str = "", lang: str | None = None) -> bytes | None:
    """Oylik natijani PNG qilib qaytaradi. Muvaffaqiyatsiz bo'lsa None."""
    try:
        from PIL import Image, ImageDraw, ImageFont
    except ImportError:
        log.info("Pillow yo'q — ulashish rasmi tayyorlanmadi")
        return None
    import i18n
    pick = lambda uz, ru: i18n.pick(lang, uz, ru)   # noqa: E731

    regular_path = _find(FONT_CANDIDATES)
    bold_path = _find(BOLD_CANDIDATES) or regular_path
    if not regular_path:
        log.info("Shrift topilmadi — ulashish rasmi tayyorlanmadi")
        return None

    def font(size: int, bold: bool = False):
        return ImageFont.truetype(bold_path if bold else regular_path, size)

    img = Image.new("RGB", (W, H), BG_TOP)
    draw = ImageDraw.Draw(img)

    # Yumshoq vertikal gradient — tekis fon yassi ko'rinadi.
    for y in range(H):
        t = y / H
        draw.line(
            [(0, y), (W, y)],
            fill=tuple(int(a + (b - a) * t) for a, b in zip(BG_TOP, BG_BOTTOM)))

    pad = 72
    y = 96

    draw.text((pad, y), pick("MOLIYAVIY HISOBOT", "ФИНАНСОВЫЙ ОТЧЁТ"),
              font=font(30, True), fill=ACCENT)
    y += 52
    draw.text((pad, y), title, font=font(66, True), fill=INK)
    y += 108

    # Kirim / chiqim kartalari
    card_w = (W - pad * 2 - 28) // 2
    for i, (label, value, color) in enumerate(
            [(pick("Kirim", "Доход"), kirim, GOOD),
             (pick("Chiqim", "Расход"), chiqim, BAD)]):
        x = pad + i * (card_w + 28)
        draw.rounded_rectangle([x, y, x + card_w, y + 168], radius=22, fill=CARD)
        draw.text((x + 30, y + 28), label.upper(), font=font(26, True), fill=INK_2)
        draw.text((x + 30, y + 74), _money(value, currency, lang), font=font(44, True),
                  fill=color)
    y += 210

    # Farq
    diff = kirim - chiqim
    draw.rounded_rectangle([pad, y, W - pad, y + 132], radius=22, fill=CARD)
    draw.text((pad + 30, y + 26), pick("FARQ", "РАЗНИЦА"), font=font(26, True),
              fill=INK_2)
    draw.text((pad + 30, y + 66), _money(diff, currency, lang), font=font(48, True),
              fill=GOOD if diff >= 0 else BAD)
    if entries:
        label = _entries_label(entries, lang)
        box = draw.textbbox((0, 0), label, font=font(28))
        draw.text((W - pad - 30 - (box[2] - box[0]), y + 78), label,
                  font=font(28), fill=INK_2)
    y += 186

    # Kategoriyalar
    if categories:
        draw.text((pad, y), pick("ENG KO'P XARAJAT", "КРУПНЕЙШИЕ РАСХОДЫ"),
                  font=font(28, True), fill=INK_2)
        y += 56
        biggest = max(amount for _, amount, *_ in categories[:5]) or 1
        for name, amount, *rest in categories[:5]:
            share = amount / biggest
            draw.text((pad, y), i18n.category_name(lang, name).capitalize(),
                      font=font(34), fill=INK)
            value_text = _money(amount, currency, lang)
            box = draw.textbbox((0, 0), value_text, font=font(34, True))
            draw.text((W - pad - (box[2] - box[0]), y), value_text,
                      font=font(34, True), fill=INK)
            y += 50
            bar_w = int((W - pad * 2) * share)
            draw.rounded_rectangle([pad, y, W - pad, y + 16], radius=8, fill=CARD)
            if bar_w > 16:
                draw.rounded_rectangle([pad, y, pad + bar_w, y + 16], radius=8,
                                       fill=ACCENT)
            y += 52

    # Pastki qism — brend
    foot = H - 108
    draw.line([(pad, foot - 34), (W - pad, foot - 34)], fill=(52, 66, 88), width=2)
    text_x = pad
    mark = _brand_mark(56)
    if mark is not None:
        img.paste(mark, (pad, foot - 6), mark)
        text_x = pad + 56 + 16
    draw.text((text_x, foot), "Tanga", font=font(38, True), fill=INK)
    handle = f"@{bot_username}" if bot_username else "Telegram bot"
    box = draw.textbbox((0, 0), handle, font=font(32))
    draw.text((W - pad - (box[2] - box[0]), foot + 6), handle, font=font(32),
              fill=ACCENT)

    buf = io.BytesIO()
    img.save(buf, format="PNG", optimize=True)
    return buf.getvalue()


# --------------------------------------------------------------------------- #
# Oylarni solishtirish grafigi (/solishtir)
# --------------------------------------------------------------------------- #

PREV = (112, 128, 152)      # o'tgan oy — sokin kulrang-ko'k, joriy oy — ACCENT
GRID = (44, 57, 78)
# Solishtirish rasmining balandligi: asosiy qism + har bir kategoriya.
CMP_BASE_H = 1150
CMP_LINE_H = 418     # chiziqli grafik bo'limi (sarlavha + grafik + kunlar)
CMP_CAT_HEAD = 60
CMP_CAT_ROW = 124


def _delta_label(now: float, was: float, lang: str | None) -> str:
    """«▲ 12%» / «▼ 8%»; o'tgan oyda 0 bo'lsa foiz ma'nosiz — «yangi»."""
    import i18n
    if abs(now - was) < 0.5:
        return "="
    if was <= 0:
        return i18n.pick(lang, "yangi", "новое")
    pct = abs(now - was) / was * 100
    return f"{'▲' if now > was else '▼'} {pct:.0f}%"


def _delta_color(now: float, was: float, more_is_good: bool):
    if abs(now - was) < 0.5:
        return INK_2
    return GOOD if (now > was) == more_is_good else BAD


def _cumulative(daily: dict, start, days: int) -> list[float]:
    from datetime import timedelta
    out, run = [], 0.0
    for i in range(days):
        run += daily.get(start + timedelta(days=i), 0.0)
        out.append(run)
    return out


def build_compare(*, title: str, subtitle: str, cur_label: str, prev_label: str,
                  cur_start, prev_start, days: int,
                  cur_daily: dict, prev_daily: dict,
                  now: dict, was: dict, categories: list[tuple[str, float, float]],
                  bot_username: str = "", lang: str | None = None) -> bytes | None:
    """Joriy oy va o'tgan oyning bir xil kunlarini PNG grafik qiladi.

    1) jamlangan chiqim chizig'i kun bo'yicha (ikki oy ustma-ust);
    2) kirim / chiqim juft ustunlari; 3) eng ko'p o'zgargan kategoriyalar.
    `now`/`was` — {"kirim": .., "chiqim": ..}; `categories` —
    (nom, joriy, o'tgan). Muvaffaqiyatsiz bo'lsa None (matn baribir boradi).
    """
    try:
        from PIL import Image, ImageDraw, ImageFont
    except ImportError:
        log.info("Pillow yo'q — solishtirish grafigi tayyorlanmadi")
        return None
    import i18n
    pick = lambda uz, ru: i18n.pick(lang, uz, ru)   # noqa: E731

    regular_path = _find(FONT_CANDIDATES)
    bold_path = _find(BOLD_CANDIDATES) or regular_path
    if not regular_path:
        log.info("Shrift topilmadi — solishtirish grafigi tayyorlanmadi")
        return None

    def font(size: int, bold: bool = False):
        return ImageFont.truetype(bold_path if bold else regular_path, size)

    def text_w(text: str, f) -> int:
        box = draw.textbbox((0, 0), text, font=f)
        return box[2] - box[0]

    # Balandlik mazmunga qarab: 4:5 karta 4 ta kategoriyaga sig'maydi,
    # kategoriyasiz holatda esa pastda bo'sh joy qolardi.
    cats = categories[:4]
    cur = _cumulative(cur_daily, cur_start, days)
    prev = _cumulative(prev_daily, prev_start, days)
    # Bitta kun yoki ikkala oyda ham chiqim yo'q — chiziq ma'nosiz (bitta
    # nuqta yoki «0 so'm» shkalasi), bu bo'lim tushib qoladi.
    show_line = days >= 2 and max(cur + prev + [0.0]) > 0
    height = (CMP_BASE_H - (0 if show_line else CMP_LINE_H)
              + (CMP_CAT_HEAD + CMP_CAT_ROW * len(cats) if cats else 0))
    img = Image.new("RGB", (W, height), BG_TOP)
    draw = ImageDraw.Draw(img)
    for y in range(height):
        t = y / height
        draw.line([(0, y), (W, y)],
                  fill=tuple(int(a + (b - a) * t) for a, b in zip(BG_TOP, BG_BOTTOM)))

    pad = 72
    y = 80
    draw.text((pad, y), pick("OYLARNI SOLISHTIRISH", "СРАВНЕНИЕ МЕСЯЦЕВ"),
              font=font(30, True), fill=ACCENT)
    y += 50
    draw.text((pad, y), title, font=font(58, True), fill=INK)
    y += 82
    draw.text((pad, y), subtitle, font=font(28), fill=INK_2)
    y += 58

    # Belgilar (legend)
    x = pad
    for label, color in ((cur_label, ACCENT), (prev_label, PREV)):
        draw.rounded_rectangle([x, y + 6, x + 34, y + 26], radius=6, fill=color)
        draw.text((x + 46, y), label, font=font(28, True), fill=INK)
        x += 46 + text_w(label, font(28, True)) + 44
    y += 60

    # ---- 1. Jamlangan chiqim chizig'i ----------------------------------- #
    if show_line:
        draw.text((pad, y), pick("CHIQIM KUN SAYIN (JAMLANGAN)",
                                 "РАСХОД ПО ДНЯМ (НАКОПИТЕЛЬНО)"),
                  font=font(26, True), fill=INK_2)
        y += 56
        top = max(cur + prev + [1.0])
        chart_l, chart_r = pad + 6, W - pad - 6
        chart_t, chart_b = y + 10, y + 300
        for i in range(4):                                  # yordamchi chiziqlar
            gy = chart_b - (chart_b - chart_t) * i / 3
            draw.line([(chart_l, gy), (chart_r, gy)], fill=GRID, width=2)
            if i:
                draw.text((chart_l + 4, gy + 6), _money(top * i / 3, lang=lang),
                          font=font(22), fill=INK_2)

        def points(series: list[float]) -> list[tuple[float, float]]:
            span = max(days - 1, 1)
            return [(chart_l + (chart_r - chart_l) * i / span,
                     chart_b - (chart_b - chart_t) * v / top)
                    for i, v in enumerate(series)]

        for series, color, width in ((prev, PREV, 6), (cur, ACCENT, 8)):
            pts = points(series)
            if len(pts) > 1:
                draw.line(pts, fill=color, width=width, joint="curve")
            ex, ey = pts[-1]
            r = width + 3
            draw.ellipse([ex - r, ey - r, ex + r, ey + r], fill=color)
        # Kun belgilari: 1-kun va oxirgi kun
        draw.text((chart_l, chart_b + 12), "1", font=font(22), fill=INK_2)
        last = str(days)
        draw.text((chart_r - text_w(last, font(22)), chart_b + 12), last,
                  font=font(22), fill=INK_2)
        y = chart_b + 62

    # ---- 2. Kirim / chiqim juft ustunlari ------------------------------- #
    rows = [(pick("Chiqim", "Расход"), "chiqim", False),
            (pick("Kirim", "Доход"), "kirim", True)]
    biggest = max([now.get(k, 0) for _, k, _ in rows]
                  + [was.get(k, 0) for _, k, _ in rows] + [1.0])
    bar_l, bar_r = pad, W - pad - 190
    for label, key, more_is_good in rows:
        n, w_ = now.get(key, 0), was.get(key, 0)
        draw.text((pad, y), label, font=font(30, True), fill=INK)
        delta = _delta_label(n, w_, lang)
        draw.text((W - pad - text_w(delta, font(30, True)), y), delta,
                  font=font(30, True), fill=_delta_color(n, w_, more_is_good))
        y += 46
        for value, color in ((n, ACCENT), (w_, PREV)):
            length = int((bar_r - bar_l) * value / biggest)
            draw.rounded_rectangle([bar_l, y, bar_r, y + 22], radius=11, fill=CARD)
            if length > 22:
                draw.rounded_rectangle([bar_l, y, bar_l + length, y + 22],
                                       radius=11, fill=color)
            draw.text((bar_r + 18, y - 4), _money(value, lang=lang),
                      font=font(24), fill=INK if color == ACCENT else INK_2)
            y += 34
        y += 18

    # ---- 3. Eng ko'p o'zgargan kategoriyalar ---------------------------- #
    foot = height - 108
    if cats:
        draw.text((pad, y), pick("KATEGORIYALAR — ENG KATTA O'ZGARISH",
                                 "КАТЕГОРИИ — САМЫЕ БОЛЬШИЕ ИЗМЕНЕНИЯ"),
                  font=font(26, True), fill=INK_2)
        y += 52
        top_cat = max([max(a, b) for _, a, b in cats] + [1.0])
        for name, n, w_ in cats:
            label = i18n.category_name(lang, name).capitalize()
            draw.text((pad, y), label, font=font(28), fill=INK)
            delta = _delta_label(n, w_, lang)
            draw.text((W - pad - text_w(delta, font(28, True)), y), delta,
                      font=font(28, True), fill=_delta_color(n, w_, False))
            y += 44
            for value, color in ((n, ACCENT), (w_, PREV)):
                length = int((bar_r - bar_l) * value / top_cat)
                draw.rounded_rectangle([bar_l, y, bar_r, y + 14], radius=7, fill=CARD)
                if length > 14:
                    draw.rounded_rectangle([bar_l, y, bar_l + length, y + 14],
                                           radius=7, fill=color)
                draw.text((bar_r + 18, y - 7), _money(value, lang=lang),
                          font=font(22), fill=INK if color == ACCENT else INK_2)
                y += 30
            y += CMP_CAT_ROW - 44 - 60

    # Pastki qism — brend (build() dagi bilan bir xil)
    draw.line([(pad, foot - 34), (W - pad, foot - 34)], fill=(52, 66, 88), width=2)
    text_x = pad
    mark = _brand_mark(56)
    if mark is not None:
        img.paste(mark, (pad, foot - 6), mark)
        text_x = pad + 56 + 16
    draw.text((text_x, foot), "Tanga", font=font(38, True), fill=INK)
    handle = f"@{bot_username}" if bot_username else "Telegram bot"
    draw.text((W - pad - text_w(handle, font(32)), foot + 6), handle,
              font=font(32), fill=ACCENT)

    buf = io.BytesIO()
    img.save(buf, format="PNG", optimize=True)
    return buf.getvalue()
