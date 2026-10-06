"""Google Gemini mijozi: ulanish, chaqiruv, vaqt chegarasi, qayta urinish,
token sarfini hisoblash. Loyihadagi YAGONA joy, u AI xizmatiga murojaat qiladi.

API: Interactions API (`client.aio.interactions.create`, google-genai >= 2.3):
hujjatga ko'ra 2026-iyundan standart interfeys; `generateContent` esa eski
(legacy). Asinxron varianti o'rnatilgan SDK'da (2.28) bor, tuzilgan javob
(JSON sxema) ham, audio ham, PDF ham shu orqali ishlaydi.

Kalit faqat `config.GEMINI_API_KEY` dan (`.env`). Kalit, foydalanuvchi matni
va audio mazmuni logga YOZILMAYDI: faqat model nomi, xato turi va status.
"""

from __future__ import annotations

import asyncio
import base64
import json
import logging
import random
import re
from typing import Any

import config

log = logging.getLogger(__name__)


class GeminiError(Exception):
    """AI xizmati bilan ishlashdagi xato (qayta urinishlardan keyin ham)."""


class _Transient(GeminiError):
    """Vaqtincha xato (masalan javob «failed» holatda) — qayta uriniladi."""


# Vaqt chegarasi (soniya) — amal turi bo'yicha.
TIMEOUT_PARSE = 20
TIMEOUT_VOICE = 30
TIMEOUT_RECEIPT = 60
TIMEOUT_QA = 40

# 429, 5xx va tarmoq xatosida eksponensial kutish bilan qayta urinish.
RETRIES = 3
BACKOFF_SECONDS = (1.0, 2.0, 4.0)


async def _sleep(seconds: float) -> None:    # sinovlarda almashtiriladi
    await asyncio.sleep(seconds)


_client: Any = None


def client():
    """Bitta umumiy asinxron mijoz. `google.genai` import qilinishi kechiktirilgan:
    sinovlar soxta mijozni `_client` ga qo'yadi."""
    global _client
    if _client is None:
        if not config.GEMINI_API_KEY:
            raise GeminiError("GEMINI_API_KEY o'rnatilmagan")
        from google import genai
        _client = genai.Client(api_key=config.GEMINI_API_KEY)
    return _client


# --------------------------------------------------------------------------- #
# So'rov bo'laklari. Matn, rasm, PDF yoki audio; fayllar base64 matn sifatida.
# --------------------------------------------------------------------------- #

def text_part(text: str) -> dict[str, Any]:
    return {"type": "text", "text": text}


def _b64(data: bytes | str) -> str:
    return data if isinstance(data, str) else base64.b64encode(data).decode("ascii")


def image_part(data: bytes | str, mime_type: str) -> dict[str, Any]:
    return {"type": "image", "data": _b64(data), "mime_type": mime_type}


def document_part(data: bytes | str, mime_type: str = "application/pdf") -> dict[str, Any]:
    return {"type": "document", "data": _b64(data), "mime_type": mime_type}


def audio_part(data: bytes | str, mime_type: str = "audio/ogg") -> dict[str, Any]:
    return {"type": "audio", "data": _b64(data), "mime_type": mime_type}


# --------------------------------------------------------------------------- #
# Token sarfi
# --------------------------------------------------------------------------- #

def _n(value: Any) -> int:
    try:
        return max(0, int(value or 0))
    except (TypeError, ValueError):
        return 0


def usage_of(interaction: Any, model: str) -> dict[str, Any]:
    """Javobdagi token ma'lumotini loyiha lug'atiga o'tkazadi.

    * `input_tokens` — keshdan o'qilMAGAN kirish (audio ham shunga kiradi);
      `cache_read` — keshdan o'qilgani; `audio_tokens` — kirishdagi audio.
    * chiqish — «o'ylash» tokenlari bilan birga (ular chiqish narxida).
      Hisobotdagi `total_tokens` dan ham chiqarib ko'riladi va katta
      qiymat olinadi: kam hisoblab limitni chetlab o'tgandan ko'ra, ko'p
      hisoblab erta to'xtagan yaxshi.
    * `cache_write` Gemini'ning yashirin keshida yo'q — doim 0 (baza ustuni
      saqlangan).
    """
    u = getattr(interaction, "usage", None)
    total_in = _n(getattr(u, "total_input_tokens", 0))
    cached = min(_n(getattr(u, "total_cached_tokens", 0)), total_in)
    audio = 0
    for item in getattr(u, "input_tokens_by_modality", None) or []:
        if getattr(item, "modality", None) == "audio":
            audio += _n(getattr(item, "tokens", 0))
    output = _n(getattr(u, "total_output_tokens", 0)) + _n(getattr(u, "total_thought_tokens", 0))
    total = _n(getattr(u, "total_tokens", 0))
    if total and total_in:
        output = max(output, total - total_in)
    fresh = total_in - cached
    audio = min(audio, fresh)
    return {
        "model": model,
        "input_tokens": fresh,
        "output_tokens": output,
        "cache_read": cached,
        "cache_write": 0,
        "audio_tokens": audio,
        "cost_usd": config.cost_usd(model, fresh, output, cached, 0, audio),
    }


# --------------------------------------------------------------------------- #
# Chaqiruv
# --------------------------------------------------------------------------- #

def _status_of(exc: BaseException) -> int | None:
    for attr in ("status_code", "code"):
        value = getattr(exc, attr, None)
        if isinstance(value, int):
            return value
    return None


def _retryable(exc: BaseException) -> bool:
    status = _status_of(exc)
    if status is not None:
        return status in (408, 429) or status >= 500
    if isinstance(exc, (asyncio.TimeoutError, TimeoutError, ConnectionError, OSError)):
        return True
    try:
        import httpx
        return isinstance(exc, httpx.TransportError)
    except ImportError:                                  # pragma: no cover
        return False


def _describe(exc: BaseException) -> str:
    """Logga: xato turi va status. Xabar matni YOZILMAYDI — unda so'rov
    mazmuni yoki kalit bo'lishi mumkin."""
    status = _status_of(exc)
    return type(exc).__name__ + (f" (status {status})" if status is not None else "")


# «minimal» o'ylash darajasini qabul qilmaydigan modellar (jonli sinovda
# aniqlangan: gemini-3.8-flash 400 beradi, «low» dan boshlanadi). Ro'yxat
# ish paytida ham to'ldiriladi: noma'lum model 400 bersa — bir marta «low»
# bilan qayta uriniladi va eslab qolinadi.
_NO_MINIMAL: set[str] = {"gemini-3.8-flash"}


def _minimal_rejected(exc: BaseException) -> bool:
    text = str(getattr(exc, "body", "") or "")
    return _status_of(exc) == 400 and "THINKING_LEVEL_MINIMAL" in text


async def _create(model: str, system: str, parts: list[dict[str, Any]],
                  schema: dict[str, Any] | None, thinking: str, timeout: float):
    if thinking == "minimal" and model in _NO_MINIMAL:
        thinking = "low"
    kwargs: dict[str, Any] = {
        "model": model,
        "system_instruction": system,
        "input": parts,
        "generation_config": {"thinking_level": thinking},
        # Ma'lumot serverda saqlanmasin (suhbat holati bizga kerak emas).
        "store": False,
        "timeout": timeout,
    }
    if schema is not None:
        kwargs["response_format"] = {"type": "text", "mime_type": "application/json",
                                     "schema": schema}

    attempts = RETRIES + 1
    for attempt in range(attempts):
        try:
            # SDK'ning o'z timeout'iga qo'shimcha: osilib qolgan ulanish ham to'xtasin.
            interaction = await asyncio.wait_for(
                client().aio.interactions.create(**kwargs), timeout + 5)
            status = getattr(interaction, "status", None)
            if status in ("failed", "cancelled"):
                raise _Transient(f"interaction status: {status}")
            return interaction
        except Exception as exc:                          # noqa: BLE001
            if kwargs["generation_config"]["thinking_level"] == "minimal"                     and _minimal_rejected(exc):
                log.warning("Gemini [%s]: «minimal» o'ylash darajasi qabul qilinmadi — "
                            "«low» ishlatiladi", model)
                _NO_MINIMAL.add(model)
                kwargs["generation_config"] = {"thinking_level": "low"}
                continue
            retry = attempt < attempts - 1 and (
                isinstance(exc, _Transient) or _retryable(exc))
            if not retry:
                log.error("Gemini xatosi [%s]: %s", model, _describe(exc))
                if isinstance(exc, GeminiError):
                    raise
                raise GeminiError(_describe(exc)) from exc
            delay = BACKOFF_SECONDS[min(attempt, len(BACKOFF_SECONDS) - 1)]
            delay += random.uniform(0, delay / 4)
            log.warning("Gemini [%s]: %s — %d/%d qayta urinish %.1f s dan keyin",
                        model, _describe(exc), attempt + 1, RETRIES, delay)
            await _sleep(delay)
    raise GeminiError("qayta urinishlar tugadi")           # pragma: no cover


_FENCE = re.compile(r"^\s*```(?:json)?\s*(.*?)\s*```\s*$", re.S)


def _loads(raw: str | None) -> dict[str, Any] | None:
    """Model javobini JSON obyektga aylantiradi. Buzuq yoki lug'at bo'lmasa — None."""
    text = (raw or "").strip()
    if not text:
        return None
    m = _FENCE.match(text)
    if m:
        text = m.group(1)
    try:
        data = json.loads(text)
    except (ValueError, TypeError):
        log.warning("Gemini JSON javobi buzuq (uzunligi %d)", len(text))
        return None
    if not isinstance(data, dict):
        log.warning("Gemini JSON javobi obyekt emas")
        return None
    return data


async def generate_json(model: str, system: str, parts: list[dict[str, Any]],
                        schema: dict[str, Any], thinking: str,
                        timeout: float) -> tuple[dict[str, Any] | None, dict[str, Any]]:
    """Sxemaga mos JSON javob. Qaytaradi: (lug'at yoki None, token sarfi).
    None — javob bo'sh/buzuq; xato bo'lsa GeminiError ko'tariladi."""
    interaction = await _create(model, system, parts, schema, thinking, timeout)
    usage = usage_of(interaction, model)
    return _loads(getattr(interaction, "output_text", None)), usage


async def generate_text(model: str, system: str, content: str, thinking: str,
                        timeout: float) -> tuple[str, dict[str, Any]]:
    """Oddiy matnli javob. Qaytaradi: (matn, token sarfi)."""
    interaction = await _create(model, system, [text_part(content)], None, thinking, timeout)
    usage = usage_of(interaction, model)
    return (getattr(interaction, "output_text", None) or "").strip(), usage
