"""O'zbek lotin → kirill transliteratsiyasi.

Nima uchun jadval emas, o'girish: o'zbek lotin va kirill yozuvlari deyarli
1:1 mos keladi. Shu sabab interfeys matnlarini ikki marta yozib chiqish
o'rniga bittasidan ikkinchisi hosil qilinadi — matn o'zgarganda ikkala
yozuv ham avtomatik yangilanadi.

Tegmaydigan joylar: HTML teglari, HTML belgilari (&#39;), buyruqlar
(/obuna), havolalar, raqamlar va lotincha qisqartmalar (CSV, AI, USD).
"""

from __future__ import annotations

import re

# Ko'p harfli birikmalar birinchi tekshiriladi — tartib muhim.
DIGRAPHS = [
    # «yo'» eng oldin: aks holda «yo» → ё bo'lib, apostrof alohida ъ ga
    # aylanadi va «yo'q» → «ёъқ» chiqadi. To'g'risi «йўқ».
    ("yo'", "йў"), ("yoʻ", "йў"), ("yo‘", "йў"),
    ("o'", "ў"), ("oʻ", "ў"), ("o‘", "ў"), ("ō", "ў"),
    ("g'", "ғ"), ("gʻ", "ғ"), ("g‘", "ғ"),
    ("sh", "ш"), ("ch", "ч"),
    ("ya", "я"), ("yo", "ё"), ("yu", "ю"), ("ye", "е"),
    ("ts", "ц"),
]

SINGLE = {
    "a": "а", "b": "б", "d": "д", "e": "е", "f": "ф", "g": "г", "h": "ҳ",
    "i": "и", "j": "ж", "k": "к", "l": "л", "m": "м", "n": "н", "o": "о",
    "p": "п", "q": "қ", "r": "р", "s": "с", "t": "т", "u": "у", "v": "в",
    "w": "в", "x": "х", "y": "й", "z": "з", "c": "к",
    "ʼ": "ъ", "'": "ъ", "’": "ъ",
}

# O'girilmaydigan lotincha so'zlar — atamalar va qisqartmalar.
KEEP = {
    "csv", "ai", "usd", "uzs", "pdf", "png", "html", "id", "ok", "sms",
    "telegram", "google", "gemini", "payme", "click", "visa", "humo",
    "uzcard", "mastercard", "excel", "instagram",
}

_WORD = re.compile(r"[A-Za-zʼ'’‘ʻ]+")


def _apply_case(source: str, converted: str) -> str:
    if source.isupper() and len(source) > 1:
        return converted.upper()
    if source[:1].isupper():
        return converted[:1].upper() + converted[1:]
    return converted


def _word(word: str) -> str:
    if word.lower() in KEEP:
        return word

    low = word.lower()
    out = []
    i = 0
    at_start = True
    while i < len(low):
        for latin, cyr in DIGRAPHS:
            if low.startswith(latin, i):
                # So'z boshidagi «ye» → «е», qolgan joyda ham «е».
                out.append(cyr)
                i += len(latin)
                at_start = False
                break
        else:
            ch = low[i]
            # So'z boshidagi «e» kirillda «э» bo'ladi: eslatma → эслатма.
            if ch == "e" and at_start:
                out.append("э")
            else:
                out.append(SINGLE.get(ch, ch))
            i += 1
            at_start = False
    return _apply_case(word, "".join(out))


# HTML teglari, &belgilari;, /buyruqlar, havolalar va <code> ichidagi
# buyruqlar — o'girilmaydi.
_SKIP = re.compile(
    r"(<[^>]+>"                     # HTML teglari
    r"|&[a-zA-Z#0-9]+;"             # HTML belgilari
    r"|https?://\S+"                # havolalar
    r"|/[a-zA-Z_]+"                 # buyruqlar
    r"|@[A-Za-z0-9_]+"              # username
    r"|\{[a-z_]+\})"                # format o'rinlari: {days}
)


def to_cyrillic(text: str) -> str:
    """Matnni o'zbek kirill yozuviga o'giradi."""
    if not text:
        return text
    parts = _SKIP.split(text)
    out = []
    for part in parts:
        if not part:
            continue
        if _SKIP.fullmatch(part):
            out.append(part)                 # tegmaymiz
        else:
            out.append(_WORD.sub(lambda m: _word(m.group(0)), part))
    return "".join(out)
