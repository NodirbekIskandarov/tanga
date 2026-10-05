"""Valyuta kurslari.

Nima uchun kerak. Foydalanuvchining hamyoni bitta: dollarda to'lasa ham,
pul o'sha so'mdagi mablag'idan chiqadi. Shuning uchun har bir yozuv
kiritilgan paytdagi kurs bilan asosiy valyutaga (so'mga) o'girilib ham
saqlanadi.

Nega kursni yozuv bilan birga saqlaymiz. Kurs ertaga o'zgaradi. Agar
hisobotni har safar bugungi kurs bilan hisoblasak, o'tgan oy hisoboti
har kuni boshqacha chiqadi. To'g'risi — amaliyot bo'lgan kundagi kurs.

Manba: O'zbekiston Markaziy banki ochiq API'si (kalit talab qilmaydi).
Ishlamasa — oxirgi ma'lum kurs, u ham bo'lmasa .env dagi zaxira qiymat.
"""

from __future__ import annotations

import json
import logging
import urllib.error
import urllib.request
from datetime import date, datetime, timedelta

import config

log = logging.getLogger("tanga.rates")

CBU_URL = "https://cbu.uz/uz/arkhiv-kursov-valyut/json/{code}/{day}/"
TIMEOUT = 8

# Bir jarayon ichida takroriy so'rov bo'lmasin: {(kun, valyuta): kurs}
_memo: dict[tuple[str, str], float] = {}


def _fetch_cbu(currency: str, day: date) -> float | None:
    """Markaziy bankdan kursni oladi. Muvaffaqiyatsiz bo'lsa None."""
    code = currency.upper()
    url = CBU_URL.format(code=code, day=day.isoformat())
    try:
        request = urllib.request.Request(
            url, headers={"User-Agent": "tanga/1.0", "Accept": "application/json"})
        with urllib.request.urlopen(request, timeout=TIMEOUT) as response:
            payload = json.loads(response.read().decode("utf-8"))
    except (urllib.error.URLError, TimeoutError, json.JSONDecodeError, OSError) as exc:
        log.info("Kurs olinmadi (%s %s): %s", code, day, exc)
        return None

    if not isinstance(payload, list) or not payload:
        return None
    try:
        value = float(str(payload[0].get("Rate", "")).replace(",", "."))
    except (TypeError, ValueError):
        return None
    # Aql bovar qilmaydigan qiymatdan himoya: API buzilsa yoki format
    # o'zgarsa noto'g'ri son bilan butun hisobotni buzib qo'ymaylik.
    if not (1_000 <= value <= 1_000_000):
        log.warning("Kurs mantiqsiz: %s %s = %s", code, day, value)
        return None
    return value


def get(currency: str, day: date | None = None, *, allow_network: bool = True) -> float:
    """1 birlik `currency` necha so'm turishini qaytaradi.

    So'm uchun har doim 1. Qidirish tartibi: xotira → baza → tarmoq →
    oxirgi ma'lum kurs → zaxira qiymat.
    """
    currency = (currency or "som").lower()
    if currency == "som":
        return 1.0
    # Toshkent sanasi: server boshqa mintaqada bo'lsa date.today()
    # yarim tundan keyin kechagi kunni berardi.
    day = day or datetime.now(config.TZ).date()
    key = (day.isoformat(), currency)
    if key in _memo:
        return _memo[key]

    import db  # aylanma importdan qochish uchun shu yerda

    stored = db.get_rate(currency, day)
    if stored:
        _memo[key] = stored
        return stored

    if allow_network:
        # Dam olish kunlarida MB kurs e'lon qilmaydi — 4 kungacha orqaga qaraymiz.
        for back in range(4):
            fetched = _fetch_cbu(currency, day - timedelta(days=back))
            if fetched:
                db.set_rate(currency, day, fetched, "cbu")
                _memo[key] = fetched
                log.info("Kurs olindi: 1 %s = %s so'm (%s)", currency.upper(),
                         fetched, day)
                return fetched

    latest = db.latest_rate(currency)
    if latest:
        log.info("Bugungi kurs yo'q, oxirgi ma'lumi ishlatildi: %s", latest)
        _memo[key] = latest
        return latest

    log.warning("Kurs topilmadi — zaxira qiymat: %s", config.USD_RATE_FALLBACK)
    return float(config.USD_RATE_FALLBACK)


def clear_cache() -> None:
    """Kurs qo'lda o'zgartirilganda chaqiriladi."""
    _memo.clear()


def refresh(currencies=("usd",)) -> dict[str, float]:
    """Kunlik vazifa uchun: bugungi kursni oldindan yangilab qo'yadi."""
    _memo.clear()
    return {cur: get(cur) for cur in currencies}


def to_base(amount: float, currency: str, day: date | None = None) -> tuple[float, float]:
    """(asosiy valyutadagi summa, ishlatilgan kurs)."""
    rate = get(currency, day)
    return round(float(amount) * rate, 2), rate
