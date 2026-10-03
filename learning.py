"""Foydalanuvchining kategoriya tuzatishlaridan o'rganish.

Odam «✏️ Kategoriya» orqali yozuvni tuzatsa, izohdagi kalit so'z (masalan
«suv») va tanlangan kategoriya SHU foydalanuvchi uchun eslab qolinadi.
Keyingi safar shu so'z uchragan yozuvda bu qoida AI javobidan ustun
turadi: bir marta «suv» ni oziq-ovqatga o'zgartirgan odamning keyingi
«suv oldim» yozuvlari o'zi oziq-ovqatga tushadi.

Qoidalar shaxsiy bazada turadi: kim nimani qaysi kategoriyaga qo'yishi
ham odamning moliyaviy odati.

Kalit so'z — izohdagi BIRINCHI ma'noli so'zning o'zagi. O'zbek tilida
qisqa izohning birinchi so'zi deyarli doim narsaning o'zi bo'ladi
(«suv», «non», «taksi», chekda «Shampun ...»). Qo'shimchalar soddalashtirib
olib tashlanadi: «nonga», «nonni» — «non».
"""

from __future__ import annotations

import re

import config
import db

# Uzunidan qisqasiga: avval «larga», keyin «ga». Bitta harfli qo'shimcha
# ATAYLAB yo'q — «taksi» dan «i» ni olib tashlash so'zni buzadi.
_SUFFIXES = (
    "lariga", "larini", "larning", "lardan", "larda", "larga", "larni",
    "ning", "dagi", "dan", "lar", "ga", "ka", "qa", "ni", "da",
    "ларга", "ларни", "лардан", "нинг", "даги", "дан", "лар", "га", "ни", "да",
)
_STOPWORDS = {
    "uchun", "oldim", "sotib", "toladim", "berdim", "qildim", "ming", "mln",
    "million", "som", "sum", "va", "bilan", "kecha", "bugun", "ertalab",
    "kechqurun", "pul", "puli", "pulini", "narsa", "xarid", "dona", "kg",
    "учун", "олдим", "тўладим", "минг", "сўм", "ва", "кеча", "бугун",
    "за", "на", "и", "в", "тысяч", "купил", "купила", "оплатил",
}
_MIN_STEM = 3


def _stem(token: str) -> str:
    for suffix in _SUFFIXES:
        if token.endswith(suffix) and len(token) - len(suffix) >= _MIN_STEM:
            return token[: -len(suffix)]
    return token


def keywords_of(text: str | None) -> list[str]:
    """Izohdagi ma'noli so'zlar o'zagi, tartib bilan, takrorsiz."""
    raw = (text or "").casefold()
    for ch in "ʻʼ‘’`'":
        raw = raw.replace(ch, "")
    out: list[str] = []
    for token in re.findall(r"[^\W\d_]+", raw):
        if len(token) < _MIN_STEM or token in _STOPWORDS:
            continue
        stem = _stem(token)
        if stem not in _STOPWORDS and stem not in out:
            out.append(stem)
    return out


def remember(user_id: int, kind: str, note: str | None, category: str) -> str | None:
    """Tuzatishni eslab qoladi. Qaytaradi: saqlangan kalit so'z yoki None."""
    if kind not in (config.KIND_CHIQIM, config.KIND_KIRIM):
        return None
    if category not in config.categories_for(kind):
        return None
    words = keywords_of(note)
    if not words:
        return None
    keyword = words[0]
    with db.get_conn() as conn:
        conn.execute(
            """INSERT INTO category_rules (user_id, keyword, kind, category)
               VALUES (?, ?, ?, ?)
               ON CONFLICT(user_id, keyword, kind) DO UPDATE SET
                 category = excluded.category, updated_at = datetime('now')""",
            (user_id, keyword, kind, category))
    return keyword


# --------------------------------------------------------------------------- #
# Do'kon bo'yicha qoida
#
# Odam chekdagi mahsulot kategoriyasini tuzatsa, o'sha DO'KON ham eslab
# qolinadi: «Dori-Darmon 24» -> salomatlik. Lekin u faqat AI aniqlay
# olmagan («boshqa chiqim») mahsulotlarga qo'llanadi: supermarketda har
# xil narsa sotiladi va bitta tuzatish butun chekni bir kategoriyaga
# o'tkazib yubormasligi kerak. Mahsulot nomi bo'yicha qoida undan ustun.
# Bazada kalit so'z o'rnida «@<do'kon>» turadi (category_rules jadvali).
# --------------------------------------------------------------------------- #

_SHOP_NOISE = ("mchj", "ooo", "xk", "ok", "llc", "ип", "ооо", "чп", "yatt", "magazin",
               "do'kon", "dokon", "market")


def shop_key(shop: str | None) -> str:
    """«OOO "Korzinka" (Chilonzor)» va «korzinka» — bitta do'kon."""
    raw = (shop or "").casefold()
    for ch in "ʻʼ‘’`'\"«»“”()[],.":
        raw = raw.replace(ch, " ")
    words = [w for w in raw.split() if w not in _SHOP_NOISE]
    return " ".join(words[:3])


def remember_shop(user_id: int, shop: str | None, category: str) -> str | None:
    """Chek mahsulotini tuzatishda do'konni eslab qoladi. Qaytaradi: kalit."""
    key = shop_key(shop)
    if not key or category not in config.EXPENSE_CATEGORIES:
        return None
    with db.get_conn() as conn:
        conn.execute(
            """INSERT INTO category_rules (user_id, keyword, kind, category)
               VALUES (?, ?, ?, ?)
               ON CONFLICT(user_id, keyword, kind) DO UPDATE SET
                 category = excluded.category, updated_at = datetime('now')""",
            (user_id, "@" + key, config.KIND_CHIQIM, category))
    return key


def apply_receipt_item(rules: dict, shop: str | None, name: str | None,
                       category: str) -> str:
    """Chek mahsuloti: avval mahsulot nomi qoidasi, keyin — faqat AI
    «boshqa chiqim» degan bo'lsa — do'kon qoidasi."""
    category = apply(rules, config.KIND_CHIQIM, name, category)
    if category == "boshqa chiqim":
        learned = rules.get(("@" + shop_key(shop), config.KIND_CHIQIM))
        if learned and learned in config.EXPENSE_CATEGORIES:
            return learned
    return category


def rules_for(user_id: int) -> dict[tuple[str, str], str]:
    """{(kalit so'z, tur): kategoriya} — bitta xabar uchun bir marta o'qiladi."""
    with db.get_conn() as conn:
        rows = conn.execute(
            "SELECT keyword, kind, category FROM category_rules WHERE user_id = ?",
            (user_id,)).fetchall()
    return {(r["keyword"], r["kind"]): r["category"] for r in rows}


def apply(rules: dict, kind: str, note: str | None, category: str) -> str:
    """AI tanlagan kategoriyani foydalanuvchi qoidasi bilan almashtiradi.

    Izohdagi so'zlar tartib bilan tekshiriladi — birinchi mos kelgan
    qoida yutadi. Qoida bo'lmasa AI javobi o'zgarmaydi.
    """
    if not rules:
        return category
    for word in keywords_of(note):
        learned = rules.get((word, kind))
        if learned and learned in config.categories_for(kind):
            return learned
    return category
