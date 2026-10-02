"""Sozlamalar. Barcha maxfiy qiymatlar .env faylidan o'qiladi."""

from __future__ import annotations

import os
import time
from zoneinfo import ZoneInfo

from dotenv import load_dotenv

load_dotenv()


def _bool(name: str, default: bool) -> bool:
    raw = os.getenv(name)
    if raw is None:
        return default
    return raw.strip().lower() in {"1", "true", "yes", "ha", "on"}


def _ids(name: str) -> set[int]:
    raw = os.getenv(name, "")
    out: set[int] = set()
    for chunk in raw.replace(";", ",").split(","):
        chunk = chunk.strip()
        if chunk.lstrip("-").isdigit():
            out.add(int(chunk))
    return out


TELEGRAM_TOKEN = os.getenv("TELEGRAM_TOKEN", "").strip()
ANTHROPIC_API_KEY = os.getenv("ANTHROPIC_API_KEY", "").strip()

# Grafik boshqaruv paneli (Telegram Mini App) manzili. Bo'sh bo'lsa
# tegishli tugma ko'rsatilmaydi — webapp.py alohida joylashtirilishi kerak,
# HTTPS bilan (Telegram Mini App talabi).
WEBAPP_URL = os.getenv("WEBAPP_URL", "").strip()

# Yozuvlarni ajratish uchun arzon va tez model yetarli.
PARSE_MODEL = os.getenv("PARSE_MODEL", "claude-haiku-4-5-20251001").strip()
# Savollarga javob berish uchun kuchliroq model.
CHAT_MODEL = os.getenv("CHAT_MODEL", "claude-sonnet-5").strip()
# Chek rasmlarini o'qish uchun — eng aniq model. Arzonroq variant: claude-sonnet-5.
VISION_MODEL = os.getenv("VISION_MODEL", "claude-opus-5").strip()

# Model narxlari ($ / 1M token): (kirish, chiqish). Keshdan o'qish kirish
# narxining ~0.1 barobari, keshga yozish ~1.25 barobari (5 daqiqalik TTL).
# Narxlar o'zgarsa shu yerdan yangilanadi — hisob-kitob avtomatik moslashadi.
MODEL_PRICES = {
    "claude-haiku-4-5-20251001": (1.00, 5.00),
    "claude-haiku-4-5": (1.00, 5.00),
    "claude-sonnet-5": (3.00, 15.00),
    "claude-opus-5": (5.00, 25.00),
    "claude-opus-4-8": (5.00, 25.00),
}
CACHE_READ_MULTIPLIER = 0.10
CACHE_WRITE_MULTIPLIER = 1.25


def cost_usd(model: str, input_tokens: int, output_tokens: int,
             cache_read: int = 0, cache_write: int = 0) -> float:
    """Bitta API chaqiruvining narxi. Noma'lum model uchun 0 qaytaradi —
    hisob past ko'rsatilishi jimgina xato ko'rsatishdan yaxshiroq emas,
    shuning uchun noma'lum model loglarda ko'rinadi."""
    price = MODEL_PRICES.get(model)
    if not price:
        return 0.0
    pin, pout = price
    return (
        input_tokens / 1e6 * pin
        + output_tokens / 1e6 * pout
        + cache_read / 1e6 * pin * CACHE_READ_MULTIPLIER
        + cache_write / 1e6 * pin * CACHE_WRITE_MULTIPLIER
    )


DB_PATH = os.getenv("DB_PATH", "tanga.db")

# Bazani shifrlash kaliti — 64 ta o'n oltilik belgi (32 bayt).
# Bo'sh bo'lsa baza oddiy SQLite sifatida ochiladi (mahalliy ishlab chiqish
# va sinovlar uchun). To'ldirilgan bo'lsa SQLCipher ishlatiladi.
#
# DIQQAT: kalit yo'qolsa baza BUTUNLAY ochilmay qoladi. Uni serverdan
# tashqarida ham saqlang.
DB_ENCRYPTION_KEY = os.getenv("DB_ENCRYPTION_KEY", "").strip().lower()


# --------------------------------------------------------------------------- #
# Shaxsiy baza
# --------------------------------------------------------------------------- #
#
# Foydalanuvchining moliyaviy yozuvlari (`transactions`) va byudjetlari
# ALOHIDA faylda, ALOHIDA kalit bilan saqlanadi.
#
# Nima uchun ikkita baza. Admin panel bitta bazani bot bilan baham
# ko'radi: unga obuna, to'lov va AI sarfi kerak. Yozuvlar ham o'sha
# faylda bo'lsa, panel ularni istagan vaqtda o'qiy olardi — himoya
# faqat "kod so'ramaydi" degan va'daga tayanardi. Endi panelda bu
# kalit YO'Q: yozuvlarni ko'rmaslik va'da emas, imkonsizlik.
#
# DIQQAT: bu kalit yo'qolsa foydalanuvchilarning yozuvlari BUTUNLAY
# tiklanmaydi. Uni serverdan tashqarida ham saqlang.
PRIVATE_DB_PATH = os.getenv("PRIVATE_DB_PATH", "tanga_shaxsiy.db")
PRIVATE_DB_KEY = os.getenv("PRIVATE_DB_KEY", "").strip().lower()


def _key_pragma(key: str, name: str) -> str:
    """Kalitni SQLCipher tushunadigan ko'rinishga keltiradi.

    SQLCipher x'...' shaklini XOM kalit deb qabul qiladi va kalit hosil
    qilish bosqichini o'tkazib yuboradi. Hex ishlatishimizning sababi:
    PRAGMA bog'langan parametrni qabul qilmaydi, hex esa qo'shtirnoq
    qochirish muammosini butunlay yo'q qiladi.
    """
    if len(key) != 64 or any(ch not in "0123456789abcdef" for ch in key):
        raise SystemExit(
            f"{name} 64 ta o'n oltilik belgidan iborat bo'lishi kerak "
            f"(hozir {len(key)} ta). Yangi kalit: python -c "
            "\"import secrets; print(secrets.token_hex(32))\""
        )
    return f"\"x'{key}'\""


def db_key_pragma() -> str:
    return _key_pragma(DB_ENCRYPTION_KEY, "DB_ENCRYPTION_KEY")


def private_key_pragma() -> str:
    """Shaxsiy bazaning kaliti.

    Bu yerda ATAYLAB zaxira yo'l YO'Q. Avval "ko'rsatilmagan bo'lsa
    asosiy kalitni ishlat" degan qulaylik bor edi va u jonli serverda
    aynan bir marta zarar keltirdi: kod kalit qo'shilishidan oldin
    ishga tushdi, zaxira yo'l jimgina asosiy kalitni oldi va butun
    baza NOTO'G'RI kalit bilan shifrlandi. Xato o'sha zahoti emas,
    keyingi ishga tushishda "file is not a database" bo'lib chiqdi.

    Endi noto'g'ri sozlama darrov va ochiq to'xtatadi: yarim to'g'ri
    ishlashdan ko'ra ishga tushmagani afzal.
    """
    if DB_ENCRYPTION_KEY and not PRIVATE_DB_KEY:
        raise SystemExit(
            "DB_ENCRYPTION_KEY bor, lekin PRIVATE_DB_KEY yo'q.\n"
            "Foydalanuvchilarning moliyaviy yozuvlari ALOHIDA kalit bilan "
            "shifrlanadi — asosiy kalit bu yerda ishlatilmaydi, aks holda "
            "admin panel ularni ocholardi.\n"
            "Yangi kalit: python -c "
            "\"import secrets; print(secrets.token_hex(32))\"")
    return _key_pragma(PRIVATE_DB_KEY, "PRIVATE_DB_KEY")
CURRENCY = os.getenv("CURRENCY", "so'm")
TZ = ZoneInfo(os.getenv("TIMEZONE", "Asia/Tashkent"))

# Qo'llab-quvvatlanadigan valyutalar. Har bir yozuv o'z valyutasida saqlanadi
# va hisobotlarda ALOHIDA ko'rsatiladi — kurs orqali birlashtirilmaydi
# (kurs vaqt bilan o'zgaradi, taxminiy konvertatsiya chalkashlik keltirib chiqaradi).
CURRENCY_SOM = "som"
CURRENCY_USD = "usd"
SUPPORTED_CURRENCIES = [CURRENCY_SOM, CURRENCY_USD]
# «Hammasi» — haqiqiy valyuta emas, balki panel filtridagi «barcha valyuta»
# tanlovi. Yozuvlar ro'yxatida u «valyuta bo'yicha filtrlamaslik» degani.
CURRENCY_ALL = "hammasi"
CURRENCY_SYMBOLS = {CURRENCY_SOM: CURRENCY, CURRENCY_USD: "$"}


def normalize_currency(value: str | None) -> str:
    v = (value or "").strip().lower()
    return v if v in SUPPORTED_CURRENCIES else CURRENCY_SOM

# --------------------------------------------------------------------------- #
# Kirish huquqi
# --------------------------------------------------------------------------- #

# Bot egalari — obunasiz, limitsiz, cheksiz foydalanadi va admin buyruqlariga
# ega. Bo'sh bo'lsa hech kim admin emas.
OWNER_IDS = _ids("OWNER_IDS")

# Eskirgan: yopiq rejim uchun oq ro'yxat. Bo'sh bo'lsa bot HAMMAGA ochiq
# (obuna/sinov muddati bo'yicha tekshiriladi). To'ldirilgan bo'lsa faqat shu
# ID'lar kiradi — yopiq sinovdan o'tkazish uchun qulay.
ALLOWED_USER_IDS = _ids("ALLOWED_USER_IDS")

# --------------------------------------------------------------------------- #
# Admin panelda o'zgartiriladigan qiymatlar
#
# Ular bazadagi `app_settings` jadvalida turadi. Bot ularni shu yerdan
# o'qiydi — narx yoki karta rekvizitini o'zgartirish uchun serverga kirib
# .env tahrirlash va botni qayta ishga tushirish shart emas.
#
# Kesh qisqa: o'zgarish yarim daqiqada yetib boradi, lekin har bir xabar
# uchun bazaga murojaat qilinmaydi.
# --------------------------------------------------------------------------- #

_settings_cache: tuple[float, dict] | None = None
_SETTINGS_TTL = 30.0


def runtime_settings() -> dict:
    global _settings_cache
    now = time.monotonic()
    if _settings_cache and now - _settings_cache[0] < _SETTINGS_TTL:
        return _settings_cache[1]
    try:
        import db
        values = db.app_settings()
    except Exception:
        # Baza hali tayyor bo'lmasligi mumkin (birinchi ishga tushirish).
        values = _settings_cache[1] if _settings_cache else {}
    _settings_cache = (now, values)
    return values


# Yangi foydalanuvchi uchun bepul sinov muddati (kun).
TRIAL_DAYS = int(os.getenv("TRIAL_DAYS", "7"))


def trial_days() -> int:
    try:
        value = int(str(runtime_settings().get("trial_days", "")).strip())
        return value if 1 <= value <= 365 else TRIAL_DAYS
    except (TypeError, ValueError):
        return TRIAL_DAYS
# Do'st taklif qilgan uchun ikkala tomonga qo'shiladigan bepul kunlar
REFERRAL_BONUS_DAYS = int(os.getenv("REFERRAL_BONUS_DAYS", "7"))

# Necha kun yozmagan odamga «qaytish» eslatmasi yuboriladi. Bitta odamga
# oyiga bir martadan ko'p yuborilmaydi — bezdirmaslik uchun.
WINBACK_DAYS = int(os.getenv("WINBACK_DAYS", "7"))

# Valyuta kursi Markaziy bank API'sidan olinadi va bazada saqlanadi.
# Bu — tarmoq ishlamay qolgan holat uchun zaxira qiymat.
USD_RATE_FALLBACK = float(os.getenv("USD_RATE_FALLBACK", "12600"))

# Oylik AI sarfi chegarasi ($). Chegaraga yetganda bot AI amallarini
# to'xtatadi va egaga xabar beradi. Kalit oshkor bo'lsa yoki kutilmagan
# yuk kelsa hisobdan cheksiz pul ketishining oldini oladi.
# 0 — chegarasiz (tavsiya etilmaydi).
MONTHLY_BUDGET_USD = float(os.getenv("MONTHLY_BUDGET_USD", "50"))


def monthly_budget_usd() -> float:
    try:
        value = float(str(runtime_settings().get("ai_monthly_budget_usd", "")).strip())
        return value if value > 0 else MONTHLY_BUDGET_USD
    except (TypeError, ValueError):
        return MONTHLY_BUDGET_USD

# Obuna bo'lish uchun murojaat manzili (masalan @username).
SUPPORT_CONTACT = os.getenv("SUPPORT_CONTACT", "").strip()

# Xizmatni ko'rsatuvchi shaxs (ommaviy oferta va maxfiylik siyosatida
# ko'rsatiladi). Ro'yxatdan o'tgandan keyin to'ldiriladi — bo'sh bo'lsa
# hujjatlarda bu bo'lim umuman ko'rsatilmaydi.
OPERATOR_NAME = os.getenv("OPERATOR_NAME", "").strip()
OPERATOR_STATUS = os.getenv("OPERATOR_STATUS", "").strip()   # masalan: YaTT
OPERATOR_TAX_ID = os.getenv("OPERATOR_TAX_ID", "").strip()   # STIR


def operator_line() -> str:
    """Oferta oxirida ko'rsatiladigan rekvizitlar. To'ldirilmagan bo'lsa bo'sh."""
    if not OPERATOR_NAME:
        return ""
    parts = [OPERATOR_NAME]
    if OPERATOR_STATUS:
        parts.insert(0, OPERATOR_STATUS)
    line = " ".join(parts)
    if OPERATOR_TAX_ID:
        line += f", STIR: {OPERATOR_TAX_ID}"
    return line

# Admin web paneli manzili — egaga bildirishnomada ko'rsatiladi.
ADMIN_PANEL_URL = os.getenv("ADMIN_PANEL_URL", "").strip().rstrip("/")

# --- To'lov rekvizitlari ---
# Hozircha to'lov kartaga o'tkazma orqali: foydalanuvchi pul o'tkazadi,
# chek skrinshotini yuboradi, admin panelda tasdiqlaydi. Click/Payme
# integratsiyasi shartnoma tuzilgach qo'shiladi.
CARD_NUMBER = os.getenv("CARD_NUMBER", "").strip()
CARD_HOLDER = os.getenv("CARD_HOLDER", "").strip()
CARD_BANK = os.getenv("CARD_BANK", "").strip()


def card_number() -> str:
    return str(runtime_settings().get("card_number") or CARD_NUMBER)


def card_holder() -> str:
    return str(runtime_settings().get("card_holder") or CARD_HOLDER)


def card_ready() -> bool:
    return bool(card_number() and card_holder())


def card_pretty() -> str:
    """Karta raqamini 4 talab ajratib ko'rsatadi."""
    number = card_number()
    digits = "".join(ch for ch in number if ch.isdigit())
    if len(digits) == 16:
        return " ".join(digits[i:i + 4] for i in range(0, 16, 4))
    return number

# --------------------------------------------------------------------------- #
# Obuna tariflari
#
# Narxni o'zgartirish uchun shu ro'yxatni tahrirlang — bot matnlari, tejash
# foizi va oylik narx avtomatik qayta hisoblanadi.
# Uzoq muddatli obuna ataylab arzonroq: AI xarajati past, shuning uchun
# obunachini uzoq muddatga "qulflash" foydali.
# --------------------------------------------------------------------------- #

SUBSCRIPTION_PLANS = [
    {"code": "1m",  "days": 30,  "months": 1,  "price": 37_000,  "label": "Oylik"},
    {"code": "3m",  "days": 90,  "months": 3,  "price": 99_000,  "label": "3 oylik"},
    {"code": "6m",  "days": 180, "months": 6,  "price": 179_000, "label": "6 oylik"},
    {"code": "12m", "days": 365, "months": 12, "price": 289_000, "label": "Yillik"},
]


def plans() -> list[dict]:
    """Joriy tariflar.

    Narx admin panelning «Sozlamalar» ekranida o'zgartiriladi va bazadagi
    `app_settings` jadvaliga tushadi. Bot shu jadvalni o'qiydi, ya'ni narx
    bir joyda turadi — ilgari ro'yxat ikki loyihada takrorlanardi va
    o'zgartirishda biri unutilib qolishi mumkin edi.
    """
    overrides = runtime_settings()
    result = []
    for base in SUBSCRIPTION_PLANS:
        plan = dict(base)
        raw = overrides.get(f"plan_price_{plan['code']}")
        digits = "".join(ch for ch in str(raw or "") if ch.isdigit())
        if digits and int(digits) > 0:
            plan["price"] = int(digits)
        result.append(plan)
    return result


def plan_by_code(code: str) -> dict | None:
    return next((p for p in plans() if p["code"] == code), None)


def plan_monthly_price(plan: dict) -> int:
    return round(plan["price"] / plan["months"])


def plan_discount_percent(plan: dict) -> int:
    """Oylik tarifga nisbatan necha foiz tejaladi."""
    base = plans()[0]["price"] * plan["months"]
    if base <= 0 or plan["price"] >= base:
        return 0
    return round((base - plan["price"]) / base * 100)

# --------------------------------------------------------------------------- #
# Kunlik limitlar — suiiste'moldan himoya. Egalarga qo'llanmaydi.
# Bitta foydalanuvchi cheksiz so'rov yuborib katta xarajat keltirmasligi uchun.
# --------------------------------------------------------------------------- #
LIMIT_TEXT_PER_DAY = int(os.getenv("LIMIT_TEXT_PER_DAY", "120"))
LIMIT_RECEIPT_PER_DAY = int(os.getenv("LIMIT_RECEIPT_PER_DAY", "25"))
LIMIT_QA_PER_DAY = int(os.getenv("LIMIT_QA_PER_DAY", "30"))

# Bir vaqtda qayta ishlanadigan yangilanishlar soni. AI chaqiruvi sekin
# bo'lgani uchun foydalanuvchilar bir-birini kutmasligi kerak.
MAX_CONCURRENT_UPDATES = int(os.getenv("MAX_CONCURRENT_UPDATES", "64"))

# "obedga 50" -> 50 000 so'm deb tushunilsinmi?
SMALL_NUMBERS_ARE_THOUSANDS = _bool("SMALL_NUMBERS_ARE_THOUSANDS", True)

# Savolga javob berishda AI'ga beriladigan maksimal XOM yozuvlar soni.
# 500 da bitta savol ~42 000 token = ~$0.14 turardi. Jamlanmalar (kategoriya,
# kun va tur bo'yicha jamilar) baribir Python'da aniq hisoblanib alohida
# yuboriladi, shuning uchun modelga barcha xom yozuvlar kerak emas —
# 150 da narx ~$0.05 ga tushadi, javob sifati esa saqlanadi.
QA_MAX_ROWS = int(os.getenv("QA_MAX_ROWS", "150"))

# Bitta chek uchun maksimal rasm (uzun chekni bo'lib suratga olish uchun).
MAX_RECEIPT_PARTS = int(os.getenv("MAX_RECEIPT_PARTS", "8"))
# Bitta rasm uchun maksimal hajm (Anthropic API chegarasi ~5 MB).
MAX_IMAGE_BYTES = int(os.getenv("MAX_IMAGE_BYTES", str(4_500_000)))
# Bitta PDF uchun maksimal hajm. Telegram botlar 20 MB gacha yuklab oladi,
# base64 esa hajmni ~33% oshiradi (API so'rovi chegarasi 32 MB).
MAX_PDF_BYTES = int(os.getenv("MAX_PDF_BYTES", str(15_000_000)))

KIND_CHIQIM = "chiqim"
KIND_KIRIM = "kirim"
KIND_QARZ_BERDIM = "qarz_berdim"   # men birovga qarz berdim
KIND_QARZ_OLDIM = "qarz_oldim"     # men birovdan qarz oldim
# Qarzni qaytarish — ikki yo'nalish. Ikkalasi ham pul harakati, lekin
# XARAJAT ham, DAROMAD ham EMAS: qarzni qaytarish yangi sarf emas, eski
# majburiyatning yopilishi. Kredit to'lovi ham shu turga kiradi.
# Ilgari bunday yozuv kirim yoki «boshqa chiqim» bo'lib tushardi va
# oylik chiqimning katta qismini egallab, statistikani buzardi.
KIND_QARZ_QAYTARDIM = "qarz_qaytardim"  # men qarzimni qaytardim (pul chiqdi)
KIND_QARZ_QAYTDI = "qarz_qaytdi"        # menga qarz qaytarildi (pul kirdi)

# Shaxsiy jamg'arma. ATAYLAB chiqim EMAS: jamg'armaga qo'yilgan pul
# sarflanmagan, u hamon odamning o'ziniki — faqat boshqa cho'ntakka
# o'tdi. Chiqim deb yozilsa "bu oy qancha sarfladim?" degan savolga
# noto'g'ri javob chiqadi va odam ko'p sarflagandek ko'rinadi.
#
# Yechish alohida tur: jamg'arma faqat o'sib boradigan bo'lsa, birinchi
# marta pul olingan kuniyoq ko'rsatkich yolg'onga aylanadi.
KIND_JAMGARMA = "jamgarma"                  # jamg'armaga qo'ydim
KIND_JAMGARMA_YECHDIM = "jamgarma_yechdim"  # jamg'armadan oldim

KINDS = [KIND_CHIQIM, KIND_KIRIM, KIND_QARZ_BERDIM, KIND_QARZ_OLDIM,
         KIND_JAMGARMA, KIND_JAMGARMA_YECHDIM,
         KIND_QARZ_QAYTARDIM, KIND_QARZ_QAYTDI]
# Qarz bilan bog'liq hamma tur — kundalik kirim/chiqim statistikasiga
# KIRMAYDI ("Bugungi chiqim", kategoriya foizlari, "Farq").
DEBT_KINDS = [KIND_QARZ_BERDIM, KIND_QARZ_OLDIM,
              KIND_QARZ_QAYTARDIM, KIND_QARZ_QAYTDI]
# Ochiq qolishi mumkin bo'lgan qarzlar (qaytarilishi kutiladi).
DEBT_OPEN_KINDS = [KIND_QARZ_BERDIM, KIND_QARZ_OLDIM]
# Qaytarish qaysi qarzni yopadi: men qaytarsam — men olgan qarzni,
# menga qaytarilsa — men bergan qarzni.
REPAYS = {KIND_QARZ_QAYTARDIM: KIND_QARZ_OLDIM, KIND_QARZ_QAYTDI: KIND_QARZ_BERDIM}
SAVINGS_KINDS = [KIND_JAMGARMA, KIND_JAMGARMA_YECHDIM]

KIND_LABELS = {
    KIND_CHIQIM: "Chiqim",
    KIND_KIRIM: "Kirim",
    KIND_QARZ_BERDIM: "Qarz berdim",
    KIND_QARZ_OLDIM: "Qarz oldim",
    KIND_JAMGARMA: "Jamg'armaga",
    KIND_JAMGARMA_YECHDIM: "Jamg'armadan yechdim",
    KIND_QARZ_QAYTARDIM: "Qarzimni qaytardim",
    KIND_QARZ_QAYTDI: "Qarz qaytdi",
}

KIND_ICONS = {
    KIND_CHIQIM: "🔻",
    KIND_KIRIM: "🔺",
    KIND_QARZ_BERDIM: "📤",
    KIND_QARZ_OLDIM: "📥",
    KIND_JAMGARMA: "🏦",
    KIND_JAMGARMA_YECHDIM: "🏧",
    KIND_QARZ_QAYTARDIM: "↩️",
    KIND_QARZ_QAYTDI: "↪️",
}

# Yozuv turini qo'lda tuzatish: qaysi turdan qaysiga o'tish mumkin.
# Qarz berdim/oldim ATAYLAB yo'q — ular shaxsga bog'liq va noto'g'ri
# almashtirilsa ochiq qarzlar ro'yxati buziladi. Jamg'arma ham yo'q —
# qoldiqni jimgina buzardi.
KIND_SWITCHES = {
    KIND_CHIQIM: [KIND_KIRIM, KIND_QARZ_QAYTARDIM],
    KIND_KIRIM: [KIND_CHIQIM, KIND_QARZ_QAYTDI],
    KIND_QARZ_QAYTARDIM: [KIND_CHIQIM],
    KIND_QARZ_QAYTDI: [KIND_KIRIM],
}

# «Avval o'zingga to'la» — daromadning kamida shuncha qismi jamg'armaga.
# Manba: George S. Clason, "Vavilonlik eng boy odam", 1-davo.
SAVINGS_RATE = 0.10

EXPENSE_CATEGORIES = [
    "oziq-ovqat",
    "kafe va restoran",
    "transport",
    "uy-joy",
    "kommunal",
    "aloqa va internet",
    "salomatlik",
    "kiyim-kechak",
    "ta'lim",
    "dam olish",
    "sovg'a",
    "xizmatlar",
    "biznes xarajat",
    "boshqa chiqim",
]

INCOME_CATEGORIES = [
    "oylik",
    "biznes daromadi",
    "qo'shimcha ish",
    "sotuvdan",
    "sovg'a olindi",
    "investitsiya",
    "boshqa kirim",
]

DEBT_CATEGORIES = ["qarz"]
SAVINGS_CATEGORIES = ["jamg'arma"]

ALL_CATEGORIES = (EXPENSE_CATEGORIES + INCOME_CATEGORIES + DEBT_CATEGORIES
                  + SAVINGS_CATEGORIES)

CATEGORY_ICONS = {
    "oziq-ovqat": "🥦",
    "kafe va restoran": "🍽",
    "transport": "🚕",
    "uy-joy": "🏠",
    "kommunal": "💡",
    "aloqa va internet": "📶",
    "salomatlik": "💊",
    "kiyim-kechak": "👕",
    "ta'lim": "📚",
    "dam olish": "🎬",
    "sovg'a": "🎁",
    "xizmatlar": "🛠",
    "biznes xarajat": "💼",
    "boshqa chiqim": "📦",
    "oylik": "💰",
    "biznes daromadi": "📈",
    "qo'shimcha ish": "🧰",
    "sotuvdan": "🏷",
    "sovg'a olindi": "🎀",
    "investitsiya": "🪙",
    "boshqa kirim": "📥",
    "qarz": "🤝",
    "jamg'arma": "🏦",
}


# Foydalanuvchiga ko'rinadigan nom. Kodda va bazada kategoriya o'z nomi
# bilan qoladi: eski yozuvlar, byudjetlar va o'rganilgan qoidalar shu
# nomga bog'langan — qayta nomlash ularning hammasini ko'chirishni
# talab qilardi. Faqat ko'rinish o'zgaradi.
CATEGORY_LABELS = {
    "oylik": "ish haqi",
}


def category_label(name: str) -> str:
    return CATEGORY_LABELS.get(name, name)


def fallback_category(kind: str) -> str:
    if kind == KIND_KIRIM:
        return "boshqa kirim"
    if kind in DEBT_KINDS:
        return "qarz"
    if kind in SAVINGS_KINDS:
        return "jamg'arma"
    return "boshqa chiqim"


def normalize_category(kind: str, category: str | None) -> str:
    """AI qaytargan kategoriyani tekshiradi va turiga mos kelmasa tuzatadi."""
    cat = (category or "").strip().lower()
    if kind in DEBT_KINDS:
        return "qarz"
    if kind in SAVINGS_KINDS:
        return "jamg'arma"
    if kind == KIND_KIRIM:
        return cat if cat in INCOME_CATEGORIES else "boshqa kirim"
    return cat if cat in EXPENSE_CATEGORIES else "boshqa chiqim"


def categories_for(kind: str) -> list[str]:
    if kind == KIND_KIRIM:
        return INCOME_CATEGORIES
    if kind in DEBT_KINDS:
        return DEBT_CATEGORIES
    if kind in SAVINGS_KINDS:
        return SAVINGS_CATEGORIES
    return EXPENSE_CATEGORIES


def missing_settings() -> list[str]:
    missing = []
    if not TELEGRAM_TOKEN:
        missing.append("TELEGRAM_TOKEN")
    if not ANTHROPIC_API_KEY:
        missing.append("ANTHROPIC_API_KEY")
    return missing
