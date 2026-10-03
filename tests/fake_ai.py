"""Anthropic mijozining soxta nusxasi — oflayn sinovlar uchun.

Model javobi qo'lda beriladi: sinov AI'ning o'zini emas, javobdan keyingi
butun yo'lni tekshiradi (normallashtirish, qoidalar, saqlash, jamlash).
Promptning sifatini faqat jonli test (pytest -m live) tekshiradi.
"""

from __future__ import annotations

from types import SimpleNamespace


def tool_response(name: str, payload: dict):
    usage = SimpleNamespace(input_tokens=100, output_tokens=20,
                            cache_read_input_tokens=0,
                            cache_creation_input_tokens=0)
    block = SimpleNamespace(type="tool_use", name=name, input=payload)
    return SimpleNamespace(content=[block], usage=usage, stop_reason="tool_use")


class FakeClient:
    def __init__(self, payloads: list[dict], tool: str = "yozuvlarni_qaytar"):
        self._payloads = list(payloads)
        self._tool = tool
        self.calls: list[dict] = []
        self.messages = self

    async def create(self, **kwargs):
        self.calls.append(kwargs)
        return tool_response(self._tool, self._payloads.pop(0))


def install(monkeypatch, payloads: list[dict], tool: str = "yozuvlarni_qaytar"):
    import ai
    fake = FakeClient(payloads, tool)
    monkeypatch.setattr(ai, "_client", fake)
    return fake


def record(turi, summa, kategoriya="", izoh="", shaxs="", sana="2026-10-02",
           valyuta="som"):
    return {"turi": turi, "summa": summa, "valyuta": valyuta,
            "kategoriya": kategoriya, "izoh": izoh, "shaxs": shaxs, "sana": sana}
