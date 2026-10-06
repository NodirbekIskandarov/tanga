"""Oylik hisobotni ulashsa bo'ladigan rasmga aylantiradi.

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
