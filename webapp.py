"""Telegram Mini App uchun API server — grafik boshqaruv paneli.

bot.py bilan bir xil SQLite bazasini o'qiydi (db.py orqali), alohida
jarayon sifatida ishga tushiriladi: uvicorn webapp:app

Xavfsizlik: har bir so'rov Telegram'ning WebApp initData imzosini
tekshiradi (HMAC-SHA256, bot tokeni bilan) — shu orqali foydalanuvchi
Telegram ichidan haqiqiy kirganini va boshqa foydalanuvchi ma'lumotini
so'ramayotganini kafolatlaydi. Bot ALLOWED_USER_IDS ro'yxati bu yerda
ham qo'llanadi.
"""

from __future__ import annotations

import hashlib
import hmac
import json
import secrets
import time
from datetime import date, timedelta
from urllib.parse import parse_qsl

import io

from fastapi import Depends, FastAPI, Header, HTTPException, Query
from fastapi.responses import FileResponse, HTMLResponse, StreamingResponse
from fastapi.staticfiles import StaticFiles
from pydantic import BaseModel, Field

import config
import i18n
import db
import goals
import learning
import reports
import tiers

# /docs, /redoc va /openapi.json YOPIQ: ular butun API sxemasini hammaga
# ko'rsatardi (Mini App ularni ishlatmaydi).
app = FastAPI(title="Tanga — boshqaruv paneli",
              docs_url=None, redoc_url=None, openapi_url=None)


# --------------------------------------------------------------------------- #
# Xavfsizlik sarlavhalari
#
# Ilova o'zi qo'yadi — proksi (Caddy) sozlamasi o'zgarsa ham himoya
# qolsin. Mini App Telegram ichida (web.telegram.org da iframe) ochiladi,
# shuning uchun X-Frame-Options: DENY emas — frame-ancestors bilan
# faqat Telegram ruxsat etiladi. Tashqi skript — faqat telegram.org dagi
# WebApp SDK; inline skript yo'q. Uslublar: app.js elementlarga style=
# atributini qo'yadi, shuning uchun style-src da 'unsafe-inline'.
# --------------------------------------------------------------------------- #

CSP = (
    "default-src 'self'; "
    "script-src 'self' https://telegram.org; "
    "style-src 'self' 'unsafe-inline'; "
    "img-src 'self' data:; "
    "font-src 'self'; "
    "connect-src 'self'; "
    "object-src 'none'; "
    "base-uri 'none'; "
    "form-action 'none'; "
    "frame-ancestors https://telegram.org https://*.telegram.org"
)


@app.middleware("http")
async def security_headers(request, call_next):
    response = await call_next(request)
    response.headers.setdefault("Content-Security-Policy", CSP)
    response.headers.setdefault("X-Content-Type-Options", "nosniff")
    response.headers.setdefault("Referrer-Policy", "no-referrer")
    response.headers.setdefault("Permissions-Policy",
                                "geolocation=(), microphone=(), camera=()")
    if (request.url.scheme == "https"
            or request.headers.get("x-forwarded-proto") == "https"):
        response.headers.setdefault("Strict-Transport-Security", "max-age=31536000")
    return response

# initData 24 soatdan eski bo'lsa rad etiladi (Telegram tavsiyasi).
INIT_DATA_MAX_AGE = 24 * 3600


# --------------------------------------------------------------------------- #
# Telegram WebApp initData tekshiruvi
# --------------------------------------------------------------------------- #

def _validate_init_data(init_data: str) -> dict:
    """initData imzosini tekshiradi va ichidagi foydalanuvchi ma'lumotini qaytaradi.

    Noto'g'ri imzo yoki eskirgan bo'lsa HTTPException ko'taradi.
    Algoritm: https://core.telegram.org/bots/webapps#validating-data-received-via-the-mini-app
    """
    if not init_data:
        raise HTTPException(401, "initData yo'q")

    try:
        pairs = dict(parse_qsl(init_data, strict_parsing=True))
    except ValueError:
        raise HTTPException(401, "initData formati noto'g'ri")

    received_hash = pairs.pop("hash", None)
    if not received_hash:
        raise HTTPException(401, "hash yo'q")

    data_check_string = "\n".join(f"{k}={v}" for k, v in sorted(pairs.items()))
    secret_key = hmac.new(b"WebAppData", config.TELEGRAM_TOKEN.encode(), hashlib.sha256).digest()
    computed_hash = hmac.new(
        secret_key, data_check_string.encode(), hashlib.sha256
    ).hexdigest()

    if not hmac.compare_digest(computed_hash, received_hash):
        raise HTTPException(401, "imzo mos kelmadi")

    try:
        auth_date = int(pairs.get("auth_date", "0"))
    except ValueError:
        auth_date = 0
    if auth_date <= 0 or (time.time() - auth_date) > INIT_DATA_MAX_AGE:
        raise HTTPException(401, "initData eskirgan — Mini App'ni qayta oching")

    try:
        user = json.loads(pairs.get("user", "{}"))
    except json.JSONDecodeError:
        raise HTTPException(401, "foydalanuvchi ma'lumoti noto'g'ri")

    user_id = user.get("id")
    if not isinstance(user_id, int):
        raise HTTPException(401, "foydalanuvchi ID topilmadi")

    # Kirish huquqi bot bilan BIR XIL qoidada tekshiriladi: ega va PRO —
    # to'liq, Bepul daraja — joriy oy (tiers.py). Faqat bloklangan va
    # yopiq rejimdagi begona kira olmaydi.
    access = db.access_status(user_id, user.get("first_name", ""), user.get("username"))
    if not access["ok"]:
        key = {
            "blocked": "wa_blocked",
            "not_allowed": "wa_closed",
        }.get(access["status"], "err_no_access")
        raise _err({"lang": _app_lang(user_id)}, 403, key)

    # Botda har bir amal rozilikdan keyin. Mini App ham shunday: endi
    # Bepul daraja hammaga ochiq, rozilik bermagan odam panel orqali
    # ma'lumot qo'sha olmasin.
    if not db.has_consent(user_id, config.CONSENT_VERSION):
        raise _err({"lang": _app_lang(user_id)}, 403, "wa_consent")

    return {
        "user_id": user_id,
        "first_name": user.get("first_name", ""),
        "access": access,
        "lang": _app_lang(user_id),
    }


def _app_lang(user_id: int) -> str:
    """Mini App tili: «ru» yoki «uz». O'zbek kirill bu yerda lotin bo'lib
    qoladi — panelda kirill tarjimasi yo'q."""
    return "ru" if i18n.normalize(db.get_lang(user_id)) == "ru" else "uz"


def _err(user: dict | None, status: int, key: str, **kwargs) -> HTTPException:
    """Foydalanuvchi tilidagi xato (matn i18n jadvalidan)."""
    lang = (user or {}).get("lang", "uz")
    return HTTPException(status, i18n.t(lang, key, **kwargs))


def current_user(x_telegram_init_data: str = Header(default="")) -> dict:
    """FastAPI dependency: har bir himoyalangan endpoint shu orqali autentifikatsiya qiladi."""
    user = _validate_init_data(x_telegram_init_data)
    _check_rate(user["user_id"], user["lang"])
    return user


# --------------------------------------------------------------------------- #
# Bepul daraja chegarasi (paywall)
# --------------------------------------------------------------------------- #

def _paywall(user: dict, feature: str) -> None:
    """402 + botdagi bilan bir xil paywall matni. Mini App uni «PRO ga
    o'tish» tugmasi bilan ko'rsatadi; hodisa botdagidek yoziladi."""
    import re
    import i18n
    db.log_event(user["user_id"], "paywall_korsatildi", f"app_{feature}")
    lang = i18n.normalize(db.get_lang(user["user_id"]))
    text = i18n.t(lang, f"paywall_{feature}")
    raise HTTPException(402, {"paywall": feature,
                              "message": re.sub(r"<[^>]+>", "", text)})


_BOT_USERNAME: str | None = None


def _bot_username() -> str:
    """Mini App'dagi «PRO ga o'tish» tugmasi botga t.me/<bot>?start=pro
    havolasi bilan qaytaradi. Nom bir marta getMe orqali olinadi."""
    global _BOT_USERNAME
    if _BOT_USERNAME is None:
        import urllib.request
        try:
            url = f"https://api.telegram.org/bot{config.TELEGRAM_TOKEN}/getMe"
            with urllib.request.urlopen(url, timeout=5) as resp:
                _BOT_USERNAME = json.loads(resp.read())["result"]["username"]
        except Exception:
            _BOT_USERNAME = ""
    return _BOT_USERNAME


# --------------------------------------------------------------------------- #
# Eksport tokeni
#
# Ilgari CSV havolasi initData'ni URL parametrida olib yurar edi. Bunday
# havola brauzer tarixida va proxy loglarida 24 soat davomida amal qilib
# qolardi. Endi: avval POST bilan bir martalik token olinadi, u 60 soniya
# yashaydi va ishlatilgach darhol o'chadi.
# --------------------------------------------------------------------------- #

EXPORT_TOKEN_TTL = 60
# Havola brauzerda ochiladi — foydalanuvchi tili bu yerda noma'lum.
_LINK_EXPIRED = ("Havola eskirgan — panelni yangilab qayta urining / "
                 "Ссылка устарела — обновите панель и попробуйте снова")
_export_tokens: dict[str, tuple[int, float]] = {}


def _issue_export_token(user_id: int) -> str:
    now = time.time()
    for tok, (_, exp) in list(_export_tokens.items()):
        if exp < now:
            _export_tokens.pop(tok, None)
    token = secrets.token_urlsafe(32)
    _export_tokens[token] = (user_id, now + EXPORT_TOKEN_TTL)
    return token


def _consume_export_token(token: str) -> int:
    entry = _export_tokens.pop(token, None)
    if not entry:
        raise HTTPException(401, _LINK_EXPIRED)
    user_id, expires = entry
    if expires < time.time():
        raise HTTPException(401, _LINK_EXPIRED)
    return user_id


# --------------------------------------------------------------------------- #
# So'rov chegarasi — bitta foydalanuvchi serverni band qilib qo'ymasin
# --------------------------------------------------------------------------- #

RATE_LIMIT = 90          # daqiqasiga so'rov
_rate: dict[int, list[float]] = {}


def _check_rate(user_id: int, lang: str = "uz") -> None:
    now = time.time()
    hits = [t for t in _rate.get(user_id, []) if now - t < 60]
    if len(hits) >= RATE_LIMIT:
        raise _err({"lang": lang}, 429, "wa_rate_limit")
    hits.append(now)
    _rate[user_id] = hits
    # Xotira o'smasin: eskirgan yozuvlarni vaqti-vaqti bilan tozalaymiz.
    if len(_rate) > 2000:
        for uid in [u for u, ts in _rate.items() if not ts or now - ts[-1] > 300]:
            _rate.pop(uid, None)


# --------------------------------------------------------------------------- #
# Sana oralig'ini hisoblash (dashboard uchun — oldinga/orqaga navigatsiya)
# --------------------------------------------------------------------------- #

def _compute_range(period: str, ref: date, lang: str = "uz") -> tuple[date, date, str]:
    month = lambda d: i18n.month_name(lang, d.month)      # noqa: E731
    if period == "hafta":
        start = ref - timedelta(days=ref.weekday())
        end = start + timedelta(days=6)
        if start.month == end.month:
            label = f"{start.day}–{end.day} {month(start)}"
        else:
            label = f"{start.day} {month(start)} – {end.day} {month(end)}"
        return start, end, label
    if period == "oy":
        start = ref.replace(day=1)
        next_month = (start.replace(day=28) + timedelta(days=4)).replace(day=1)
        end = next_month - timedelta(days=1)
        name = i18n.month_name(lang, ref.month, nominative=True).capitalize()
        return start, end, f"{name} {ref.year}"
    if period == "yil":
        start = ref.replace(month=1, day=1)
        end = ref.replace(month=12, day=31)
        return start, end, (f"{ref.year} год" if lang == "ru" else f"{ref.year}-yil")
    # "kun"
    label = f"{ref.day} {month(ref)}" if lang == "ru" else f"{ref.day}-{month(ref)}"
    return ref, ref, label


def _parse_date(raw: str | None, default: date, lang: str = "uz") -> date:
    if not raw:
        return default
    try:
        return date.fromisoformat(raw)
    except ValueError:
        raise _err({"lang": lang}, 400, "wa_bad_date", raw=raw[:20])


# --------------------------------------------------------------------------- #
# API
# --------------------------------------------------------------------------- #

@app.get("/api/me")
def api_me(user: dict = Depends(current_user)):
    access = user.get("access") or {}
    until = access.get("until")
    lang = user["lang"]
    return {
        "user_id": user["user_id"],
        "first_name": user["first_name"],
        # Bepul darajada panel joriy oy bilan cheklangan (tiers.py).
        "tier": access.get("tier", "pro"),
        "history_from": (None if tiers.is_pro(access)
                         else tiers.month_start().isoformat()),
        "bot_username": _bot_username(),
        "subscription": {
            "status": access.get("status", "trial"),
            "days_left": access.get("days_left"),
            "until": until.isoformat() if until else None,
        },
        "lang": lang,
        "currency": config.CURRENCY,
        "categories": config.ALL_CATEGORIES,
        "category_icons": config.CATEGORY_ICONS,
        "currency_symbols": {**config.CURRENCY_SYMBOLS,
                             config.CURRENCY_SOM: i18n.money_unit(lang)},
        "kind_icons": config.KIND_ICONS,
        "kind_labels": {k: i18n.kind_label(lang, k) for k in config.KIND_LABELS},
        "kind_switches": config.KIND_SWITCHES,
        "category_labels": {c: i18n.category_name(lang, c)
                            for c in config.ALL_CATEGORIES
                            if i18n.category_name(lang, c) != c},
        "categories_by_kind": {
            config.KIND_CHIQIM: config.EXPENSE_CATEGORIES,
            config.KIND_KIRIM: config.INCOME_CATEGORIES,
            config.KIND_QARZ_BERDIM: config.DEBT_CATEGORIES,
            config.KIND_QARZ_OLDIM: config.DEBT_CATEGORIES,
            config.KIND_JAMGARMA: config.SAVINGS_CATEGORIES,
            config.KIND_JAMGARMA_YECHDIM: config.SAVINGS_CATEGORIES,
            config.KIND_QARZ_QAYTARDIM: config.DEBT_CATEGORIES,
            config.KIND_QARZ_QAYTDI: config.DEBT_CATEGORIES,
        },
    }


@app.get("/api/summary")
def api_summary(
    period: str = Query("oy", pattern="^(kun|hafta|oy|yil)$"),
    ref: str | None = None,
    user: dict = Depends(current_user),
):
    ref_date = _parse_date(ref, reports.today(), user["lang"])
    start, end, label = _compute_range(period, ref_date, user["lang"])
    if period == "yil" or not tiers.history_allowed(user["access"], start):
        if not tiers.is_pro(user["access"]):
            _paywall(user, "history")

    uid = user["user_id"]

    def block(kirim_cats, chiqim_cats, totals):
        return {
            "kirim": totals[config.KIND_KIRIM],
            "chiqim": totals[config.KIND_CHIQIM],
            "farq": totals[config.KIND_KIRIM] - totals[config.KIND_CHIQIM],
            "qarz_berdim": totals[config.KIND_QARZ_BERDIM],
            "qarz_oldim": totals[config.KIND_QARZ_OLDIM],
            # Qarz qaytarish — «farq» ga ham, kategoriyalarga ham KIRMAYDI.
            "qarz_qaytardim": totals[config.KIND_QARZ_QAYTARDIM],
            "qarz_qaytdi": totals[config.KIND_QARZ_QAYTDI],
            # Jamg'arma «farq» ga KIRMAYDI: u sarflangan pul emas.
            # Sof qiymati (qo'ygan minus yechgan) va ikkala tomoni ham
            # beriladi — «Jamg'arma» yorlig'i ularni alohida chizadi.
            "jamgarma": round(totals[config.KIND_JAMGARMA]
                              - totals[config.KIND_JAMGARMA_YECHDIM], 2),
            "jamgarma_qoygan": totals[config.KIND_JAMGARMA],
            "jamgarma_yechgan": totals[config.KIND_JAMGARMA_YECHDIM],
            "chiqim_kategoriyalari": [
                {"kategoriya": c, "summa": s, "soni": n} for c, s, n in chiqim_cats
            ],
            "kirim_kategoriyalari": [
                {"kategoriya": c, "summa": s, "soni": n} for c, s, n in kirim_cats
            ],
        }

    # «hammasi» — barcha valyuta asosiy valyutada birlashtirilgan. Foydalanuvchi
    # hamyoni bitta, shuning uchun standart ko'rinish shu.
    unified = db.totals_unified(uid, start, end)
    result = {
        config.CURRENCY_ALL: block(
            db.by_category_unified(uid, start, end, config.KIND_KIRIM),
            db.by_category_unified(uid, start, end, config.KIND_CHIQIM),
            unified["totals"],
        )
    }
    result[config.CURRENCY_ALL]["foreign"] = unified["foreign"]

    # Har bir valyuta alohida ham qoladi — kimdir faqat dollarli
    # yozuvlarini ko'rmoqchi bo'lsa.
    by_cur = db.totals_by_currency(uid, start, end)
    currencies = sorted(by_cur.keys(), key=lambda c: c != "som")
    for cur in currencies:
        result[cur] = block(
            db.by_category(uid, start, end, config.KIND_KIRIM, cur),
            db.by_category(uid, start, end, config.KIND_CHIQIM, cur),
            by_cur[cur],
        )

    return {
        "period": period,
        "ref": ref_date.isoformat(),
        "start": start.isoformat(),
        "end": end.isoformat(),
        "label": label,
        # Birinchisi standart tanlov bo'ladi.
        "currencies": ([config.CURRENCY_ALL] + currencies
                       if len(currencies) > 1 else currencies),
        "base_currency": config.CURRENCY,
        "by_currency": result,
    }


@app.get("/api/debts")
def api_debts(user: dict = Depends(current_user)):
    rows = db.open_debts(user["user_id"])

    def _group(kind: str) -> dict:
        items = [r for r in rows if r["kind"] == kind]
        by_cur: dict[str, list[dict]] = {}
        unified: list[dict] = []
        for r in items:
            cur = r["currency"]
            # `amount` — qaytarishlar ayirilgan QOLDIQ; asl summa alohida.
            by_cur.setdefault(cur, []).append({
                "id": r["id"], "person": r["person"] or "noma'lum",
                "amount": r["remaining"], "original": r["amount"],
                "paid": r.get("paid", 0),
                "date": r["occurred_on"], "note": r["note"],
                "due": r.get("due_on"),
            })
            # «Hammasi» ko'rinishi uchun asosiy valyutaga o'girilgan nusxa —
            # /api/summary dagi «hammasi» blok bilan bir xil mantiq.
            unified.append({
                "id": r["id"], "person": r["person"] or "noma'lum",
                "amount": r["remaining_base"], "date": r["occurred_on"],
                "note": r["note"], "original_currency": cur,
            })
        totals = {cur: round(sum(i["amount"] for i in lst), 2) for cur, lst in by_cur.items()}
        # «hammasi» HAR DOIM qo'shiladi: davr ichida ikki valyuta bo'lsa panel
        # shu tanlovda turadi, qarzlar esa bitta valyutada bo'lishi mumkin.
        by_cur[config.CURRENCY_ALL] = unified
        totals[config.CURRENCY_ALL] = round(sum(i["amount"] for i in unified), 2)
        return {"totals": totals, "items": by_cur}

    return {
        "qarz_berdim": _group(config.KIND_QARZ_BERDIM),
        "qarz_oldim": _group(config.KIND_QARZ_OLDIM),
    }


@app.get("/api/savings")
def api_savings(user: dict = Depends(current_user)):
    """Jamg'arma holati — DAVRGA bog'liq emas.

    Jamlanma (`/api/summary`) tanlangan davrni ko'rsatadi: «avgustda
    qancha qo'shildi». Bu esa umumiy holat: qoldiq, maqsad va unga
    qancha qolgani. Ikkalasi har xil savolga javob bergani uchun
    alohida turadi.
    """
    uid = user["user_id"]
    prof = db.savings_profile(uid)
    balance = db.savings_balance(uid)
    # Panel asosiy maqsadni ko'rsatadi (goals.py). Maydon nomlari avvalgidek —
    # Mini App o'zgarmasdan ishlaydi.
    primary = goals.primary(uid)
    goal = float(primary["amount"]) if primary else 0.0

    out = {
        "balance": balance,
        "rate": db.savings_rate(uid),
        "goal": goal,
        "goal_note": primary["name"] if primary else "",
        "streak": db.savings_streak(uid),
        "card": prof.get("card_state") or db.CARD_SORALMAGAN,
        "percent": None,
        "left": None,
    }
    if primary:
        out["percent"] = round(min(100.0, primary["saved"] / goal * 100), 1)
        out["left"] = primary["left"]
        out["goal_saved"] = primary["saved"]

    # Barcha maqsadlar — progress va (PRO'da) «qachon erishaman» bashorati.
    forecast_ok = tiers.allows(user["access"], "goals_forecast")
    out["goals"] = []
    for g in goals.list_goals(uid):
        item = {"id": g["id"], "name": g["name"], "amount": g["amount"],
                "saved": g["saved"], "left": g["left"], "percent": g["percent"],
                "deadline": g["deadline"], "primary": g["primary"],
                "forecast_locked": not forecast_ok,
                "eta": None, "pace": None, "need_monthly": None}
        if forecast_ok and g["left"] > 0:
            fc = goals.forecast(uid, g)
            item["eta"] = fc["eta"].isoformat() if fc["eta"] else None
            item["pace"] = round(fc["pace"], 2) if fc["pace"] is not None else None
            item["need_monthly"] = (round(fc["need_monthly"], 2)
                                    if fc["need_monthly"] else None)
        out["goals"].append(item)
    return out


@app.get("/api/transactions")
def api_transactions(
    start: str | None = None,
    end: str | None = None,
    currency: str | None = None,
    kind: str | None = None,
    search: str | None = None,
    receipt_id: str | None = None,
    group_receipts: bool = False,
    limit: int = Query(50, ge=1, le=200),
    offset: int = Query(0, ge=0),
    user: dict = Depends(current_user),
):
    start_d = _parse_date(start, date(2000, 1, 1), user["lang"])
    end_d = _parse_date(end, reports.today(), user["lang"])
    # Bepul daraja: ro'yxat joriy oydan boshlanadi (xato emas, jim cheklov —
    # qidiruv va «yana yuklash» ham shu chegarada ishlaydi).
    if not tiers.is_pro(user["access"]):
        start_d = max(start_d, tiers.month_start())
    # Vergul bilan bir nechta tur berilishi mumkin — «Jamg'arma»
    # yorlig'i qo'yilgan va yechilgan pulni birga ko'rsatadi.
    if kind and "," in kind:
        kinds = [k for k in kind.split(",") if k]
        if any(k not in config.KINDS for k in kinds):
            raise _err(user, 400, "wa_bad_kind")
        kind = kinds
    elif kind and kind not in config.KINDS:
        raise _err(user, 400, "wa_bad_kind")
    # «hammasi» — valyuta filtri yo'q degani. /api/summary uni valyutalar
    # ro'yxatiga qo'shadi, shuning uchun bu yerda ham qabul qilinishi shart.
    if currency == config.CURRENCY_ALL:
        currency = None
    if currency and currency not in config.SUPPORTED_CURRENCIES:
        raise _err(user, 400, "wa_bad_currency")

    # Filtrlash, tartiblash va sahifalash SQL tomonida — foydalanuvchida
    # bir necha yillik yozuv to'planganda ham tez ishlashi kerak.
    result = db.search_transactions(
        user["user_id"], start_d, end_d, kind=kind, currency=currency,
        search=search, receipt_id=receipt_id, limit=limit, offset=offset,
        group_receipts=group_receipts)

    return {
        "total_count": result["total_count"],
        "totals": result["totals"],
        "items": [_serialize_tx(r) for r in result["items"]],
    }


@app.delete("/api/transactions/{tx_id}")
def api_delete_transaction(tx_id: int, user: dict = Depends(current_user)):
    ok = db.delete_transaction(user["user_id"], tx_id)
    if not ok:
        raise _err(user, 404, "entry_not_found")
    return {"deleted": True}


def _serialize_tx(row) -> dict:
    out = {
        "id": row["id"], "date": row["occurred_on"], "kind": row["kind"],
        "amount": row["amount"], "currency": row["currency"],
        "category": row["category"], "note": row["note"],
        "person": row["person"], "receipt_id": row["receipt_id"],
        "settled": bool(row["settled"]),
        "due": row["due_on"] if "due_on" in row.keys() else None,
    }
    # group_receipts=1 da chek qatori: mahsulotlar soni va do'kon.
    if "n" in row.keys():
        out["items_count"] = row["n"]
        out["shop"] = row["shop"] or ""
    return out


@app.delete("/api/receipts/{receipt_id}")
def api_delete_receipt(receipt_id: str, user: dict = Depends(current_user)):
    """Butun chek: mahsulotlar va sarlavha bitta tranzaksiyada."""
    removed = db.delete_receipt(user["user_id"], receipt_id)
    if not removed:
        raise _err(user, 404, "wa_receipt_nf")
    return {"deleted": removed}


class TxUpdate(BaseModel):
    category: str | None = None
    # Faqat kirim<->chiqim almashtirish — bot.py'dagi "🔄 Turini almashtirish"
    # tugmasi bilan bir xil cheklov (qarz turlari shaxs maydoniga bog'liq,
    # bu yerda o'zgartirilmaydi).
    kind: str | None = None


@app.patch("/api/transactions/{tx_id}")
def api_update_transaction(tx_id: int, body: TxUpdate, user: dict = Depends(current_user)):
    row = db.get_transaction(user["user_id"], tx_id)
    if not row:
        raise _err(user, 404, "entry_not_found")

    if body.kind and body.kind != row["kind"]:
        # Ruxsat etilgan almashtirishlar config.KIND_SWITCHES da: kirim <->
        # chiqim va ular <-> qarz qaytarish. Jamg'arma va qarz berdim/oldim
        # ATAYLAB yo'q — qoldiqni jimgina buzardi. Kerak bo'lsa yozuvni
        # o'chirib, qaytadan yozish to'g'ri yo'l.
        if body.kind not in config.KIND_SWITCHES.get(row["kind"], []):
            raise _err(user, 400, "kind_locked")
        new_category = body.category or config.fallback_category(body.kind)
        if new_category not in config.categories_for(body.kind):
            raise _err(user, 400, "bad_category")
        db.update_kind(user["user_id"], tx_id, body.kind, new_category)
    elif body.category:
        if body.category not in config.categories_for(row["kind"]):
            raise _err(user, 400, "bad_category")
        db.update_category(user["user_id"], tx_id, body.category)
        # Botdagi tuzatish bilan bir xil: keyingi shunday yozuv o'zi
        # to'g'ri kategoriyaga tushadi.
        learning.remember(user["user_id"], row["kind"], row["note"], body.category)
        if row["receipt_id"] and row["kind"] == config.KIND_CHIQIM:
            receipt = db.get_receipt(user["user_id"], row["receipt_id"])
            if receipt and receipt.get("shop"):
                learning.remember_shop(user["user_id"], receipt["shop"], body.category)

    return _serialize_tx(db.get_transaction(user["user_id"], tx_id))


class DueBody(BaseModel):
    # 0 — muddatsiz; aks holda bugundan necha kun keyin.
    days: int = Field(ge=0, le=3650)


@app.post("/api/debts/{tx_id}/due")
def api_debt_due(tx_id: int, body: DueBody, user: dict = Depends(current_user)):
    """Qarzni qaytarish muddati — botdagi «📅» tugmasi bilan bir xil (PRO)."""
    if not tiers.allows(user["access"], "debt_reminders"):
        _paywall(user, "debt_reminders")
    due = tiers.today() + timedelta(days=body.days) if body.days else None
    if not db.set_due(user["user_id"], tx_id, due):
        raise _err(user, 404, "wa_open_debt_nf")
    return {"due": due.isoformat() if due else None}


@app.get("/api/debts/{tx_id}")
def api_debt_detail(tx_id: int, user: dict = Depends(current_user)):
    """Qarz kartasi: asli, to'langan, qoldiq va to'lovlar tarixi."""
    d = db.debt_detail(user["user_id"], tx_id)
    if d is None:
        raise _err(user, 404, "debt_not_found")
    return {"id": d["id"], "kind": d["kind"],
            "person": d["person"] or i18n.t(user["lang"], "debt_person_unknown"),
            "currency": d["currency"], "original": d["amount"], "paid": d["paid"],
            "remaining": d["remaining"], "date": d["occurred_on"],
            "payments": d["payments"]}


class DebtPayBody(BaseModel):
    amount: float = Field(gt=0, le=1e12)


@app.post("/api/debts/{tx_id}/pay")
def api_debt_pay(tx_id: int, body: DebtPayBody, user: dict = Depends(current_user)):
    """Qisman to'lash — botdagi «💸» bilan bir xil: qaytarish yozuvi shu
    qarzga aniq bog'lanadi. Qoldiqdan ko'p summa qabul qilinmaydi (ortig'i
    jimgina yo'qolmasin — interfeys «to'liq yopish» ni taklif qiladi)."""
    d = db.debt_detail(user["user_id"], tx_id)
    if d is None or d["remaining"] <= 0:
        raise _err(user, 404, "wa_open_debt_nf")
    if body.amount > d["remaining"] + 0.005:
        raise _err(user, 400, "wa_over_remaining", left=f"{d['remaining']:g}")
    db.add_debt_payment(user["user_id"], tx_id, body.amount)
    return api_debt_detail(tx_id, user)


@app.post("/api/debts/{tx_id}/settle")
def api_settle_debt(tx_id: int, user: dict = Depends(current_user)):
    ok = db.settle_debt(user["user_id"], tx_id)
    if not ok:
        raise _err(user, 404, "wa_open_debt_nf")
    return {"settled": True}


class TxCreate(BaseModel):
    kind: str
    # Yuqori chegara: xato yoki zararli kiritish (1e300) hisobotlarni
    # buzmasin. 10 mlrd — so'mda ham, dollarda ham real chegaradan yuqori.
    amount: float = Field(gt=0, le=10_000_000_000)
    currency: str = "som"
    category: str
    note: str = ""
    person: str | None = None
    date: str | None = None


@app.post("/api/transactions", status_code=201)
def api_create_transaction(body: TxCreate, user: dict = Depends(current_user)):
    if body.kind not in config.KINDS:
        raise _err(user, 400, "wa_bad_kind")
    currency = config.normalize_currency(body.currency)
    category = config.normalize_category(body.kind, body.category)
    person = (body.person or "").strip() or None
    # Qarz berish/olishda shaxs shart; qaytarishda ixtiyoriy (bank
    # krediti to'lovida shaxs yo'q).
    if body.kind in config.DEBT_OPEN_KINDS and not person:
        raise _err(user, 400, "wa_person_needed")
    if body.kind not in config.DEBT_KINDS:
        person = None
    occurred_on_d = _parse_date(body.date, reports.today(), user["lang"])
    # Kelajakdagi xarajat bo'lmaydi; bunday yozuv bugungi va oylik
    # hisobotdan «yo'qolib», byudjetni esa noto'g'ri oyda buzardi.
    if occurred_on_d > reports.today():
        raise _err(user, 400, "wa_future_date")
    occurred_on = occurred_on_d.isoformat()

    tx_id = db.add_transaction(
        user_id=user["user_id"], kind=body.kind, amount=body.amount,
        category=category, note=body.note.strip()[:120], person=person,
        occurred_on=occurred_on, raw_text="[boshqaruv panelidan qo'lda qo'shildi]",
        currency=currency,
    )
    return _serialize_tx(db.get_transaction(user["user_id"], tx_id))


@app.post("/api/export/token")
def api_export_token(user: dict = Depends(current_user)):
    """Bir martalik, 60 soniya yashaydigan yuklab olish tokeni."""
    # CSV hamma uchun bepul — o'z ma'lumotini olish huquq (botdagi /csv kabi).
    return {"token": _issue_export_token(user["user_id"]), "ttl": EXPORT_TOKEN_TTL}


@app.get("/api/export.csv")
def api_export_csv(token: str = Query(...)):
    user_id = _consume_export_token(token)
    content, _ = reports.csv_bytes(user_id)
    return StreamingResponse(
        io.BytesIO(content),
        media_type="text/csv",
        headers={"Content-Disposition": "attachment; filename=hisobot.csv"},
    )


# --------------------------------------------------------------------------- #
# Statik fayllar (frontend) — API'dan keyin ro'yxatga olinadi, aks holda
# "/" barcha "/api/*" so'rovlarini ham qamrab olib qo'yishi mumkin.
# --------------------------------------------------------------------------- #

app.mount("/static", StaticFiles(directory="static"), name="static")


def _asset_version(name: str) -> str:
    """Fayl mazmuniga qarab qisqa versiya belgisi.

    Telegram ichidagi WebView `app.js` ni juda qattiq keshlaydi va
    ETag bilan qayta so'ramaydi. Natijasi jimgina va chalkash bo'ladi:
    yangi `index.html` keladi (yangi tugma ko'rinadi), lekin eski
    JavaScript ishlaydi — tugma bosiladi, hech narsa o'zgarmaydi.
    Aynan shunday holat bir marta bo'ldi.

    Mazmun hashi bo'lsa yangi fayl YANGI manzilga tushadi va kesh
    o'zidan-o'zi chetlab o'tiladi.
    """
    try:
        with open(f"static/{name}", "rb") as f:
            return hashlib.sha1(f.read()).hexdigest()[:10]
    except OSError:
        return "0"


@app.get("/")
def index():
    """Mini App sahifasi.

    HTML ning O'ZI keshlanmaydi (`no-store`): u ichida asset
    versiyalarini olib yuradi, ya'ni eski HTML eski JS ni ushlab
    qolgan bo'lardi. Fayllarning o'zi esa bemalol keshlanadi —
    manzillari mazmun bilan birga o'zgaradi.
    """
    with open("static/index.html", encoding="utf-8") as f:
        html = f.read()
    for name in ("app.js", "style.css"):
        html = html.replace(f"/static/{name}",
                            f"/static/{name}?v={_asset_version(name)}")
    return HTMLResponse(html, headers={"Cache-Control": "no-store"})
