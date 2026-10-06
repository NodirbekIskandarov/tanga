"""Gemini qatlamining soxta nusxasi — oflayn sinovlar uchun.

Model javobi qo'lda beriladi: sinov AI'ning o'zini emas, javobdan keyingi
butun yo'lni tekshiradi (normallashtirish, qoidalar, saqlash, jamlash).
Promptning sifatini faqat jonli test (pytest -m live) tekshiradi.

`gemini.generate_json` / `gemini.generate_text` almashtiriladi; har bir
chaqiruvning argumentlari (`model`, `system`, `parts`, `schema`, `thinking`,
`timeout`) `calls` ga yoziladi. Payload:
  * lug'at  — model shu JSON bilan javob beradi;
  * None    — javob bo'sh/buzuq (generate_json None qaytaradi);
  * Exception nusxasi — chaqiruv shu xato bilan tugaydi.
generate_text uchun payload — matn (str) yoki {"text": "..."}.
SDK darajasidagi soxta mijoz (qayta urinish, usage) — tests/test_gemini.py da.
"""

from __future__ import annotations

from typing import Any


def usage_for(model: str, inp: int = 100, out: int = 20, audio: int = 0) -> dict[str, Any]:
    import config
    return {"model": model, "input_tokens": inp, "output_tokens": out,
            "cache_read": 0, "cache_write": 0, "audio_tokens": audio,
            "cost_usd": config.cost_usd(model, inp, out, 0, 0, audio)}


class FakeGemini:
    def __init__(self, payloads: list[Any]):
        self._payloads = list(payloads)
        self.calls: list[dict[str, Any]] = []

    def _next(self, kind: str, **call) -> Any:
        self.calls.append({"kind": kind, **call})
        if not self._payloads:
            raise AssertionError("soxta Gemini: kutilmagan chaqiruv")
        payload = self._payloads.pop(0)
        if isinstance(payload, BaseException):
            raise payload
        return payload

    async def generate_json(self, model, system, parts, schema, thinking, timeout):
        payload = self._next("json", model=model, system=system, parts=parts,
                             schema=schema, thinking=thinking, timeout=timeout)
        return payload, usage_for(model)

    async def generate_text(self, model, system, content, thinking, timeout):
        payload = self._next("text", model=model, system=system, content=content,
                             parts=[{"type": "text", "text": content}], schema=None,
                             thinking=thinking, timeout=timeout)
        text = payload.get("text", "") if isinstance(payload, dict) else payload
        return str(text or ""), usage_for(model)


def install(monkeypatch, payloads: list[Any], tool: str | None = None):
    """`tool` — eski imzo bilan moslik uchun qabul qilinadi, e'tiborsiz."""
    import gemini
    fake = FakeGemini(payloads)
    monkeypatch.setattr(gemini, "generate_json", fake.generate_json)
    monkeypatch.setattr(gemini, "generate_text", fake.generate_text)
    return fake


def record(turi, summa, kategoriya="", izoh="", shaxs="", sana="2026-10-02",
           valyuta="som"):
    return {"turi": turi, "summa": summa, "valyuta": valyuta,
            "kategoriya": kategoriya, "izoh": izoh, "shaxs": shaxs, "sana": sana}


def voice(transkripsiya: str, yozuvlar: list[dict] | None = None, ishonch: str = "yuqori",
          til: str = "uz", niyat: str = "yozuv", **extra) -> dict[str, Any]:
    """Ovoz javobi: matn javobi + transkripsiya, ishonch va til."""
    return {"niyat": niyat, "yozuvlar": yozuvlar or [], "transkripsiya": transkripsiya,
            "ishonch": ishonch, "til": til, **extra}
