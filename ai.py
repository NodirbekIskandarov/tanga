"""AI qatlami: erkin matn va ovozni moliyaviy yozuvga aylantirish, chek
o'qish va foydalanuvchi savollariga javob. Google Gemini orqali (gemini.py).

Ochiq interfeys: parse_message, parse_voice, parse_receipt, answer_question.
Model faqat o'qiydi; barcha normallashtirish va arifmetika (summa, sana,
kategoriya, valyuta, chek jami) model javobidan KEYIN Python'da bajariladi —
summalarni AI emas, Python qo'shadi.
"""

from __future__ import annotations

import json
import logging
from datetime import date, datetime
from typing import Any

import ai_prompts
import ai_schemas
import config
import gemini

log = logging.getLogger(__name__)


def _today() -> date:
    """Toshkent bo'yicha bugun (server mintaqasidan qat'i nazar)."""
    return datetime.now(config.TZ).date()


# --------------------------------------------------------------------------- #
# Token sarfi — har bir chaqiruv narxi foydalanuvchi bo'yicha yoziladi; sarf
# gemini.usage_of dan keladi (haqiqiy hisobot, taxmin emas).
# --------------------------------------------------------------------------- #

def _merge_usage(*items: dict[str, Any] | None) -> dict[str, Any]:
    """Bir amal bir nechta API chaqiruvidan iborat bo'lsa (masalan chek qayta
    o'qilsa) — sarfni qo'shib yig'adi."""
    total = {"model": "", "input_tokens": 0, "output_tokens": 0,
             "cache_read": 0, "cache_write": 0, "audio_tokens": 0, "cost_usd": 0.0}
    for it in items:
        if not it:
            continue
        total["model"] = it["model"] or total["model"]
        for k in ("input_tokens", "output_tokens", "cache_read", "cache_write",
                  "audio_tokens", "cost_usd"):
            total[k] += it.get(k, 0)
    return total


# --------------------------------------------------------------------------- #
# 1-vazifa: matnni yozuvlarga ajratish
# --------------------------------------------------------------------------- #

def _parse_system_prompt() -> str:
    return ai_prompts.parse_system_prompt()


# Yozuv sanasi bugundan keyin yoki shundan eski bo'lsa — shubhali: model
# yilni adashtirgan bo'lishi mumkin (chekdagi «08.10.26», «1-noyabrda»).
# Bot bunday sanani jimgina saqlamaydi — matnda so'raydi, chekda bugunga
# almashtirib aytadi. Eski qarzni yozish kabi haqiqiy holat ham bor,
# shuning uchun rad etilmaydi, faqat tasdiqlanadi.
DATE_PAST_LIMIT_DAYS = 365


def date_suspicious(sana: str, today: date) -> bool:
    try:
        d = date.fromisoformat(sana)
    except (TypeError, ValueError):
        return True
    return d > today or (today - d).days > DATE_PAST_LIMIT_DAYS


def _coerce_date(raw: Any, today: date) -> str:
    if isinstance(raw, str) and len(raw) == 10:
        try:
            return date.fromisoformat(raw).isoformat()
        except ValueError:
            pass
    return today.isoformat()

def _normalize_parse(payload: dict[str, Any], today: date) -> dict[str, Any]:
    """Model javobini tekshiradi va loyiha tuzilmasiga keltiradi (matn va ovoz
    uchun umumiy). Qaytaradi: {"niyat", "yozuvlar", "izoh_matni"[, "kurs"]}."""
    niyat = payload.get("niyat", "tushunarsiz")
    cleaned: list[dict[str, Any]] = []

    items = payload.get("yozuvlar")
    for item in items if isinstance(items, list) else []:
        if not isinstance(item, dict):
            continue
        try:
            amount = float(item.get("summa", 0))
        except (TypeError, ValueError):
            continue
        if amount <= 0 or amount != amount or amount == float("inf"):
            continue

        kind = item.get("turi")
        if kind not in config.KINDS:
            kind = config.KIND_CHIQIM

        person = (str(item.get("shaxs") or "")).strip() or None
        if kind not in config.DEBT_KINDS:
            person = None

        sana = _coerce_date(item.get("sana"), today)
        # Maqsad nomi — faqat jamg'armada; qaytarish muddati — faqat ochiq
        # qarzda va yozuv sanasidan keyin bo'lsa (o'tgan sana eslatma emas).
        goal = (str(item.get("maqsad") or "")).strip()[:60] if kind == config.KIND_JAMGARMA else ""
        due = None
        if kind in config.DEBT_OPEN_KINDS and item.get("muddat"):
            raw_due = _coerce_date(item.get("muddat"), date.min)
            if raw_due != date.min.isoformat() and raw_due > sana:
                due = raw_due

        cleaned.append(
            {
                "turi": kind,
                "summa": round(amount, 2),
                "valyuta": config.normalize_currency(item.get("valyuta")),
                "kategoriya": config.normalize_category(kind, item.get("kategoriya")),
                "izoh": (str(item.get("izoh") or "")).strip()[:120],
                "shaxs": person,
                "sana": sana,
                "maqsad": goal or None,
                "muddat": due,
            }
        )

    if cleaned:
        niyat = "yozuv"
    elif niyat == "yozuv":
        niyat = "tushunarsiz"
    if niyat not in ("yozuv", "savol", "kurs", "tushunarsiz"):
        niyat = "tushunarsiz"

    result = {
        "niyat": niyat,
        "yozuvlar": cleaned,
        "izoh_matni": (str(payload.get("izoh_matni") or "")).strip(),
    }
    if niyat == "kurs":
        # Hisoblashni AI emas, bot qiladi (Markaziy bank kursi bilan).
        try:
            amount = float(payload.get("kurs_summa") or 1)
        except (TypeError, ValueError):
            amount = 1.0
        result["kurs"] = {"summa": amount if amount > 0 else 1.0,
                          "valyuta": config.normalize_currency(payload.get("kurs_valyuta"))}
    return result


async def parse_message(text: str, today: date | None = None) -> dict[str, Any]:
    """Xabarni tahlil qiladi.

    Qaytaradi: {"niyat": str, "yozuvlar": [ ... ], "izoh_matni": str}
    """
    today = today or _today()

    # Tizim prompti va sxema har chaqiruvda bir xil (kesh); o'zgaruvchan
    # qism — sana va matn — faqat foydalanuvchi qismida.
    payload, usage = await gemini.generate_json(
        model=config.PARSE_MODEL,
        system=ai_prompts.parse_system_prompt(),
        parts=[gemini.text_part(f"Bugungi sana: {today.isoformat()}"),
               gemini.text_part(text)],
        schema=ai_schemas.RECORD_SCHEMA,
        thinking=config.PARSE_THINKING,
        timeout=gemini.TIMEOUT_PARSE,
    )

    if not payload:
        log.warning("Gemini matn javobi bo'sh yoki buzuq")
        return {"niyat": "tushunarsiz", "yozuvlar": [], "izoh_matni": "", "_usage": usage}

    result = _normalize_parse(payload, today)
    result["_usage"] = usage
    return result


# --------------------------------------------------------------------------- #
# Ovozli xabar: bitta chaqiruvda transkripsiya va yozuvlar
# --------------------------------------------------------------------------- #

VOICE_LANGS = ("uz", "ru", "aralash", "boshqa")
VOICE_MAX_ITEMS_NO_CONFIRM = 5        # bundan ko'p yozuv — har doim tasdiq


def _needs_confirmation(records: list[dict[str, Any]]) -> bool:
    """Katta summa yoki ko'p yozuv: ovozdan xato eshitilsa zarari katta —
    model ishonchidan qat'i nazar foydalanuvchidan tasdiq so'raladi."""
    if len(records) > VOICE_MAX_ITEMS_NO_CONFIRM:
        return True
    for r in records:
        limit = (config.VOICE_CONFIRM_ABOVE_USD if r["valyuta"] == config.CURRENCY_USD
                 else config.VOICE_CONFIRM_ABOVE_SOM)
        if r["summa"] > limit:
            return True
    return False


async def parse_voice(audio: bytes, mime_type: str = "audio/ogg",
                      today: date | None = None) -> dict[str, Any]:
    """Ovozli xabarni tahlil qiladi: transkripsiya + yozuvlar BITTA chaqiruvda.

    Qaytaradi: parse_message natijasi + "transkripsiya", "ishonch"
    («yuqori» | «past») va "til". Ishonch «past» bo'lsa bot hech narsani
    saqlamaydi, avval foydalanuvchidan tasdiq so'raydi. Audio faqat xotirada.
    """
    today = today or _today()

    payload, usage = await gemini.generate_json(
        model=config.VOICE_MODEL,
        system=ai_prompts.voice_system_prompt(),
        parts=[gemini.text_part(f"Bugungi sana: {today.isoformat()}"),
               gemini.audio_part(audio, mime_type)],
        schema=ai_schemas.VOICE_SCHEMA,
        thinking=config.VOICE_THINKING,
        timeout=gemini.TIMEOUT_VOICE,
    )

    if not payload:
        log.warning("Gemini ovoz javobi bo'sh yoki buzuq")
        return {"niyat": "tushunarsiz", "yozuvlar": [], "izoh_matni": "",
                "transkripsiya": "", "ishonch": "past", "til": "boshqa",
                "_usage": usage}

    result = _normalize_parse(payload, today)
    result["transkripsiya"] = str(payload.get("transkripsiya") or "").strip()[:2000]
    til = payload.get("til")
    result["til"] = til if til in VOICE_LANGS else "boshqa"
    confidence = "yuqori" if payload.get("ishonch") == "yuqori" else "past"
    if result["niyat"] == "yozuv" and _needs_confirmation(result["yozuvlar"]):
        confidence = "past"
    result["ishonch"] = confidence
    result["_usage"] = usage
    return result


# --------------------------------------------------------------------------- #
# 2-vazifa: chek rasmini o'qish
# --------------------------------------------------------------------------- #

PDF_MEDIA_TYPE = "application/pdf"


def _receipt_parts(images: list[tuple[str, str]], today: date, caption: str,
                   note: str = "") -> list[dict[str, Any]]:
    """Rasm va PDF qismlaridan so'rov bo'laklarini yig'adi. Sana va qismlar
    soni BIRINCHI bo'lakda (tizim prompti o'zgarmas qoladi — kesh)."""
    parts_count = len(images)
    parts: list[dict[str, Any]] = [
        gemini.text_part(ai_prompts.receipt_user_note(today, parts_count))]
    for idx, (data, media_type) in enumerate(images, start=1):
        if parts_count > 1:
            parts.append(gemini.text_part(f"--- Chekning {idx}-qismi ---"))
        if media_type == PDF_MEDIA_TYPE:
            # Ichida matn qatlami bo'lsa to'g'ridan-to'g'ri o'qiladi (aniqroq),
            # skanerlangan bo'lsa sahifalar rasm sifatida ko'riladi.
            parts.append(gemini.document_part(data, PDF_MEDIA_TYPE))
        else:
            parts.append(gemini.image_part(data, media_type))

    tail = "Shu chekni o'qib, mahsulotlar ro'yxatini qaytar."
    if caption.strip():
        tail += f"\nFoydalanuvchi izohi: {caption.strip()}"
    if note:
        tail += f"\n\n{note}"
    parts.append(gemini.text_part(tail))
    return parts


async def _receipt_call(
    images: list[tuple[str, str]],
    today: date,
    caption: str,
    note: str = "",
    thinking: str | None = None,
) -> tuple[dict[str, Any] | None, dict[str, Any]]:
    # Odatda config.VISION_THINKING: o'ylash tokenlari chiqish narxida va
    # chekda yig'indini baribir Python tekshiradi.
    return await gemini.generate_json(
        model=config.VISION_MODEL,
        system=ai_prompts.receipt_system_prompt(),
        parts=_receipt_parts(images, today, caption, note),
        schema=ai_schemas.RECEIPT_SCHEMA,
        thinking=thinking or config.VISION_THINKING,
        timeout=gemini.TIMEOUT_RECEIPT,
    )




def _normalize_receipt(payload: dict[str, Any], today: date) -> dict[str, Any]:
    items: list[dict[str, Any]] = []
    for raw in payload.get("mahsulotlar") or []:
        if not isinstance(raw, dict):
            continue
        try:
            amount = float(raw.get("summa", 0))
        except (TypeError, ValueError):
            continue
        if amount <= 0:
            continue

        try:
            qty = raw.get("miqdori")
            qty = float(qty) if qty is not None else None
        except (TypeError, ValueError):
            qty = None

        items.append(
            {
                "nomi": (raw.get("nomi") or "").strip()[:120] or "nomsiz",
                "miqdori": qty,
                "summa": round(amount, 2),
                "kategoriya": config.normalize_category(
                    config.KIND_CHIQIM, raw.get("kategoriya")
                ),
            }
        )

    def _num(key: str) -> float | None:
        try:
            value = float(payload[key])
        except (KeyError, TypeError, ValueError):
            return None
        return value if value > 0 else None

    return {
        "oqildi": bool(payload.get("oqildi")) and bool(items),
        "dokon": (payload.get("dokon") or "").strip()[:80],
        "sana": _coerce_date(payload.get("sana"), today),
        "mahsulotlar": items,
        "chekdagi_jami": _num("chekdagi_jami"),
        "chegirma": _num("chegirma"),
        # Chekdagi valyuta. Ilgari hamma chek so'm deb olinardi — dollarli
        # chek noto'g'ri tushardi.
        "valyuta": config.normalize_currency(payload.get("valyuta")),
        "izoh_matni": (payload.get("izoh_matni") or "").strip(),
    }


def receipt_tolerance(total: float, currency: str = "som") -> float:
    """Chek jamini solishtirishdagi ruxsat etilgan farq.

    So'm uchun max(1 000 so'm, jamining 1 %). Yaxlitlash, tiyinlar va
    bitta-ikkita xira raqam shu oraliqqa sig'adi; undan kattasi haqiqiy
    o'qish xatosi.
    """
    floor = 1.0 if currency == "usd" else 1000.0
    return max(floor, abs(total) * 0.01)


def receipt_check(data: dict[str, Any]) -> dict[str, Any]:
    """Chekni tekshiradi: mahsulotlar yig'indisini Python hisoblab, chekdagi
    JAMI bilan solishtiradi. Arifmetika AI'ga ishonib topshirilmaydi.

    Chegirma bor chekda qator narxlari ikki xil yozilgan bo'lishi mumkin:
      * chegirmaGACHA — qatorlar yig'indisi minus chegirma = JAMI;
      * chegirmaDAN KEYIN — qatorlarda allaqachon arzonlashgan narx,
        chegirma qatori faqat ma'lumot uchun: yig'indi = JAMI.
    Ilgari faqat birinchisi tekshirilardi va ikkinchi turdagi chekda
    chegirma IKKI MARTA ayirilib, yolg'on «farq» ogohlantirishi chiqardi
    (va chek behuda qayta o'qilardi). Endi ikkalasi ham sinab ko'riladi;
    ogohlantirish faqat hech biri mos kelmaganda chiqadi.

    Qaytaradi: holat (mos | farqli | jami_yoq), hisoblangan (qatorlar
    yig'indisi), chekdagi, farq (eng yaqin talqindagi farq, ishorasi bilan)
    va narxlar (chegirmagacha | chegirmadan_keyin | None).
    """
    computed = round(sum(item["summa"] for item in data["mahsulotlar"]), 2)
    discount = data.get("chegirma") or 0.0
    printed = data.get("chekdagi_jami")

    if printed is None:
        return {"holat": "jami_yoq", "hisoblangan": computed,
                "chekdagi": None, "farq": None, "narxlar": None}

    tolerance = receipt_tolerance(printed, data.get("valyuta") or "som")
    # (farq, talqin) — qaysi biri JAMI ga yaqinroq bo'lsa o'sha olinadi.
    candidates = [(round(computed - printed, 2), "chegirmadan_keyin")]
    if discount:
        candidates.append((round(computed - discount - printed, 2), "chegirmagacha"))
    diff, mode = min(candidates, key=lambda c: abs(c[0]))

    holat = "mos" if abs(diff) <= tolerance else "farqli"
    return {"holat": holat, "hisoblangan": computed, "chekdagi": printed,
            "farq": diff, "narxlar": mode if holat == "mos" else None}


def fit_to_total(amounts: list[float], target: float,
                 currency: str = "som") -> list[float]:
    """Summalarni mutanosib o'zgartirib, yig'indisini AYNAN `target` ga
    tenglaydi.

    Chekdan saqlanadigan pul doim chekdagi yakuniy jamiga teng bo'lishi
    kerak — chegirma ham, yaxlitlash ham kategoriyalar o'rtasida ulushiga
    qarab taqsimlanadi. Yaxlitlashdan qolgan qoldiq eng katta qatorga
    qo'shiladi, shunda yig'indi bir so'mgacha aniq chiqadi.
    """
    total = sum(amounts)
    if not amounts or total <= 0 or target <= 0:
        return list(amounts)
    digits = 2 if currency == "usd" else 0
    scaled = [round(a * target / total, digits) for a in amounts]
    remainder = round(target - sum(scaled), digits)
    if remainder:
        biggest = max(range(len(scaled)), key=lambda i: scaled[i])
        scaled[biggest] = round(scaled[biggest] + remainder, digits)
    return scaled


def apply_receipt_total(data: dict[str, Any]) -> dict[str, Any]:
    """Mahsulot summalarini chekdagi yakuniy jamiga moslaydi.

    Chekda JAMI ko'rinmasa, boshqa ishonchli raqam yo'q — summalar
    o'qilganicha qoladi. Asl qator narxi `summa_asl` da saqlanadi
    (to'liq ro'yxatda ko'rsatish uchun).
    """
    target = data.get("chekdagi_jami")
    items = data["mahsulotlar"]
    if not target or not items:
        return data
    fitted = fit_to_total([i["summa"] for i in items], target,
                          data.get("valyuta") or "som")
    for item, amount in zip(items, fitted):
        item["summa_asl"] = item["summa"]
        item["summa"] = amount
    return data

async def parse_receipt(
    images: list[tuple[str, str]],
    today: date | None = None,
    caption: str = "",
) -> dict[str, Any]:
    """Chek rasm(lar)ini o'qiydi va tekshiradi.

    images: [(base64_data, media_type), ...] — uzun chek bo'lsa bir nechta qism.

    Aniqlik uchun ikki bosqich: agar mahsulotlar yig'indisi chekdagi JAMI bilan
    mos kelmasa, model rasmni farq haqida xabardor qilingan holda qayta o'qiydi.
    """
    today = today or _today()

    payload, usage = await _receipt_call(images, today, caption)
    if payload is None:
        # JSON bo'sh yoki buzuq — o'ylashsiz bir marta qayta urinamiz.
        log.warning("Chek: javob bo'sh yoki buzuq, o'ylashsiz qayta uriniladi")
        payload, usage2 = await _receipt_call(images, today, caption, thinking="minimal")
        usage = _merge_usage(usage, usage2)

    if payload is None:
        return {
            "oqildi": False, "dokon": "", "sana": today.isoformat(),
            "mahsulotlar": [], "chekdagi_jami": None, "chegirma": None,
            "izoh_matni": "Chekni o'qib bo'lmadi. Yorug'roq va aniqroq surat yuboring.",
            "tekshiruv": {"holat": "jami_yoq", "hisoblangan": 0.0,
                          "chekdagi": None, "farq": None},
            "_usage": usage,
        }

    data = _normalize_receipt(payload, today)
    check = receipt_check(data)

    # Tekshiruv: yig'indi chekdagi JAMI bilan mos kelmasa — qayta o'qish.
    if data["oqildi"] and check["holat"] == "farqli":
        log.info(
            "Chek nomuvofiqligi: hisoblangan=%s chekdagi=%s farq=%s — qayta o'qilmoqda",
            check["hisoblangan"], check["chekdagi"], check["farq"],
        )
        missing = -check["farq"]
        note = (
            "DIQQAT — tekshiruv xatosi topildi. Sen o'qigan mahsulotlar yig'indisi "
            f"{check['hisoblangan']:.0f}, lekin chekdagi JAMI {check['chekdagi']:.0f}. "
            f"Farq: {abs(check['farq']):.0f}.\n"
            + (
                "Yig'indi JAMI'dan KICHIK — demak bir yoki bir nechta qator "
                "tushib qolgan, yoki summa kam o'qilgan.\n"
                if missing > 0
                else "Yig'indi JAMI'dan KATTA — demak biror qator ikki marta "
                "yozilgan (qismlar takrorlanishi mumkin), yoki summa ortiq "
                "o'qilgan, yoki JAMI emas boshqa qator olingan.\n"
            )
            + "Rasmni QAYTADAN, qator-baqator diqqat bilan o'qi va to'g'rilangan "
            "to'liq ro'yxatni qaytar. Har bir raqamni chekdagi bilan solishtir."
        )
        retry, usage_retry = await _receipt_call(images, today, caption, note=note)
        usage = _merge_usage(usage, usage_retry)
        if retry is not None:
            data2 = _normalize_receipt(retry, today)
            check2 = receipt_check(data2)
            # Faqat yaxshiroq bo'lsa almashtiramiz.
            if data2["oqildi"] and (
                check2["holat"] == "mos"
                or (
                    check2["farq"] is not None
                    and check["farq"] is not None
                    and abs(check2["farq"]) < abs(check["farq"])
                )
            ):
                data, check = data2, check2

    data["tekshiruv"] = check
    apply_receipt_total(data)
    data["_usage"] = usage
    return data

# --------------------------------------------------------------------------- #
# 3-vazifa: ma'lumotlar asosida savolga javob
# --------------------------------------------------------------------------- #

QA_SYSTEM = ai_prompts.QA_SYSTEM


# Savol-javobda xom yozuvlar JSON emas, jadval bo'lib yuboriladi.
#
# Nega: savol eng qimmat amal (2026-10 da AI sarfining 80% i), uning
# kirishi esa asosan shu ro'yxat. JSON'da har bir qatorda yettita kalit
# («"sana":», «"kategoriya":» ...) va bo'sh «"shaxs": null» takrorlanardi.
# Jadvalda ustun nomlari BIR marta yoziladi — ma'lumot aynan o'sha
# (har bir maydon, har bir qator), faqat takror yo'q.
ROW_COLUMNS = "sana|turi|summa|valyuta|kategoriya|izoh|shaxs"


def _num(value) -> str:
    """45000.0 -> «45000», 12.5 -> «12.5» (aniqlik yo'qolmaydi)."""
    v = float(value)
    return str(int(v)) if v.is_integer() else repr(round(v, 2))


def _cell(text) -> str:
    """Jadval katagi: ajratgich «|» va qator ko'chishi bo'lmasin."""
    return " ".join(str(text or "").replace("|", "/").split())


def _rows_table(rows) -> str:
    lines = [ROW_COLUMNS]
    for r in rows:
        currency = r["currency"] if "currency" in r.keys() else "som"
        lines.append("|".join((r["occurred_on"], r["kind"], _num(r["amount"]), currency,
                               _cell(r["category"]), _cell(r["note"]), _cell(r["person"]))))
    return "\n".join(lines)


def _compact_json(data) -> str:
    """Bo'sh joysiz JSON: indent va «, » / «: » ham token — mazmun bir xil."""
    return json.dumps(data, ensure_ascii=False, separators=(",", ":"))


def _aggregate(rows) -> dict[str, Any]:
    """Jamlanmalarni Python hisoblaydi — AI arifmetikasiga tayanmaslik uchun.

    Valyutalar ALOHIDA jamlanadi (som va usd birlashtirilmaydi — kurs yo'q,
    aralashtirish noto'g'ri jamiga olib keladi)."""
    per_currency: dict[str, dict[str, Any]] = {}

    for r in rows:
        cur = r["currency"] if "currency" in r.keys() else "som"
        bucket = per_currency.setdefault(cur, {
            "by_kind": {}, "by_category": {}, "by_day": {}, "count_by_category": {},
        })
        kind, amount = r["kind"], float(r["amount"])
        bucket["by_kind"][kind] = round(bucket["by_kind"].get(kind, 0.0) + amount, 2)
        if kind == config.KIND_CHIQIM:
            cat = r["category"]
            bucket["by_category"][cat] = round(bucket["by_category"].get(cat, 0.0) + amount, 2)
            bucket["count_by_category"][cat] = bucket["count_by_category"].get(cat, 0) + 1
            day = r["occurred_on"]
            bucket["by_day"][day] = round(bucket["by_day"].get(day, 0.0) + amount, 2)

    valyutalar_boyicha = {
        cur: {
            "turlar_boyicha_jami": b["by_kind"],
            "chiqim_kategoriyalari_boyicha_jami": dict(
                sorted(b["by_category"].items(), key=lambda kv: kv[1], reverse=True)
            ),
            "chiqim_kategoriyalari_boyicha_soni": b["count_by_category"],
            "kunlar_boyicha_chiqim": dict(sorted(b["by_day"].items())),
        }
        for cur, b in per_currency.items()
    }

    dates = [r["occurred_on"] for r in rows]
    return {
        "yozuvlar_soni": len(rows),
        "davr": {"boshi": min(dates), "oxiri": max(dates)} if dates else None,
        "valyutalar_boyicha": valyutalar_boyicha,
    }


def _monthly_json(monthly: list[dict]) -> str:
    """{oy: {valyuta: {tur: summa}}} — oylik jamlar, valyutalar alohida."""
    out: dict[str, dict[str, dict[str, float]]] = {}
    for m in monthly:
        bucket = out.setdefault(m["oy"], {}).setdefault(m["currency"], {})
        bucket[m["kind"]] = float(m["total"])
    return _compact_json(out)


async def answer_question(
    question: str, rows, today: date | None = None,
    summary_rows=None, monthly: list[dict] | None = None,
) -> tuple[str, dict[str, Any] | None]:
    """Qaytaradi: (javob matni, token sarfi). Sarf None bo'lsa API chaqirilmagan.

    rows         — oxirgi xom yozuvlar (QA_MAX_ROWS bilan cheklangan);
    summary_rows — jamlanma hisoblanadigan davrning BARCHA yozuvlari
                   (o'tgan oy boshidan bugungacha). Ilgari jamlanma `rows`
                   dan olinardi va ko'p yozadigan odamda «bu oy qancha
                   sarfladim» degan savolga to'liq bo'lmagan son chiqardi;
    monthly      — oxirgi 12 oyning tur/valyuta bo'yicha jamlari (SQL).
    """
    today = today or _today()
    if not rows and not summary_rows:
        return "Hozircha bazada yozuv yo'q. Avval bir nechta xarajat yozing.", None

    agg_rows = summary_rows if summary_rows is not None else rows
    period = ""
    if summary_rows is not None:
        period = " — o'tgan oy boshidan bugungacha, BARCHA yozuvlar bo'yicha"
    parts = [
        f"Bugungi sana: {today.isoformat()}\n"
        f"Valyutalar: som ({config.CURRENCY}) va usd ($) — alohida-alohida.\n",
        f"Tayyor jamlanmalar (dastur aniq hisoblagan{period}):\n"
        f"{_compact_json(_aggregate(agg_rows))}\n",
    ]
    if monthly:
        parts.append("Oylar bo'yicha jamlar (oxirgi 12 oy, to'liq; "
                     "{oy: {valyuta: {turi: summa}}}):\n"
                     f"{_monthly_json(monthly)}\n")
    parts.append(f"Oxirgi yozuvlar (jadval: birinchi qator — ustunlar, «|» bilan "
                 f"ajratilgan, bo'sh katak — ma'lumot yo'q; eng ko'pi {len(rows)} ta — "
                 f"to'liq ro'yxat bo'lmasligi mumkin):\n{_rows_table(rows)}\n")
    parts.append(f"Savol: {question}")
    content = "\n".join(parts)

    # Javob uzunligi QA_SYSTEM bilan cheklanadi (6 qator).
    text, usage = await gemini.generate_text(
        model=config.CHAT_MODEL, system=QA_SYSTEM, content=content,
        thinking=config.CHAT_THINKING, timeout=gemini.TIMEOUT_QA)
    return text or "Javob tayyorlab bo'lmadi, qaytadan urinib ko'ring.", usage

