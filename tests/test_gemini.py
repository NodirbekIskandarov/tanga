"""gemini.py: qayta urinish, vaqt chegarasi, JSON tekshiruvi, usage va narx.

SDK'ning o'rniga soxta mijoz (`client().aio.interactions.create`) qo'yiladi:
tarmoq va kalit kerak emas. Jonli tekshiruv — tests/test_live_ai.py.
"""

import asyncio
import logging
from datetime import date
from types import SimpleNamespace

import pytest

import config
import gemini

MODEL = "gemini-3.5-flash-lite"
SECRET = "gemini-test-key"


class HttpError(Exception):
    def __init__(self, status):
        super().__init__(f"HTTP {status} maxfiy so'rov matni")
        self.status_code = status


def interaction(text='{"niyat": "yozuv", "yozuvlar": []}', *, inp=100, out=20, thought=0,
                cached=0, total=None, audio=0, status="completed"):
    usage = SimpleNamespace(
        total_input_tokens=inp, total_output_tokens=out, total_thought_tokens=thought,
        total_cached_tokens=cached,
        total_tokens=total if total is not None else inp + out + thought,
        input_tokens_by_modality=[SimpleNamespace(modality="text", tokens=inp - audio),
                                  SimpleNamespace(modality="audio", tokens=audio)])
    return SimpleNamespace(output_text=text, usage=usage, status=status)


class FakeSdk:
    def __init__(self, script):
        self.script = list(script)
        self.calls = []
        self.aio = SimpleNamespace(interactions=SimpleNamespace(create=self._create))

    async def _create(self, **kwargs):
        self.calls.append(kwargs)
        item = self.script.pop(0)
        if isinstance(item, BaseException):
            raise item
        if callable(item):
            return await item()
        return item


@pytest.fixture
def sdk(monkeypatch):
    sleeps = []

    async def no_sleep(seconds):
        sleeps.append(seconds)

    monkeypatch.setattr(gemini, "_sleep", no_sleep)

    def install(*script):
        fake = FakeSdk(script)
        monkeypatch.setattr(gemini, "_client", fake)
        fake.sleeps = sleeps
        return fake
    return install


def run(coro):
    return asyncio.run(coro)


SCHEMA = {"type": "object", "properties": {"niyat": {"type": "string"}}}


def call_json():
    return run(gemini.generate_json(MODEL, "tizim", [gemini.text_part("salom")],
                                    SCHEMA, "minimal", 20))


# ------------------------------------------------------------ so'rov shakli --

def test_request_shape(sdk):
    fake = sdk(interaction())
    payload, usage = call_json()
    assert payload == {"niyat": "yozuv", "yozuvlar": []}
    sent = fake.calls[0]
    assert sent["model"] == MODEL and sent["system_instruction"] == "tizim"
    assert sent["input"] == [{"type": "text", "text": "salom"}]
    assert sent["generation_config"] == {"thinking_level": "minimal"}
    assert sent["response_format"] == {"type": "text", "mime_type": "application/json",
                                       "schema": SCHEMA}
    assert sent["store"] is False and sent["timeout"] == 20


def test_text_call_has_no_schema(sdk):
    fake = sdk(interaction("Javob matni  "))
    text, usage = run(gemini.generate_text(MODEL, "tizim", "savol?", "medium", 40))
    assert text == "Javob matni"
    assert "response_format" not in fake.calls[0]
    assert fake.calls[0]["generation_config"] == {"thinking_level": "medium"}


def test_parts_helpers_encode_files_as_base64():
    assert gemini.audio_part(b"\x00\x01", "audio/ogg") == {
        "type": "audio", "data": "AAE=", "mime_type": "audio/ogg"}
    assert gemini.image_part("QUJD", "image/png")["data"] == "QUJD"      # tayyor base64
    assert gemini.document_part(b"%PDF")["mime_type"] == "application/pdf"


# ---------------------------------------------------------- qayta urinish --

@pytest.mark.parametrize("status", [429, 500, 503])
def test_retries_on_429_and_5xx_then_succeeds(sdk, status):
    fake = sdk(HttpError(status), HttpError(status), interaction())
    payload, _ = call_json()
    assert payload is not None and len(fake.calls) == 3
    assert len(fake.sleeps) == 2
    assert fake.sleeps[0] < fake.sleeps[1]                        # eksponensial kutish


def test_gives_up_after_three_retries(sdk):
    fake = sdk(*[HttpError(503) for _ in range(4)])
    with pytest.raises(gemini.GeminiError):
        call_json()
    assert len(fake.calls) == 1 + gemini.RETRIES                  # 3 marta qayta urinildi
    assert len(fake.sleeps) == gemini.RETRIES


def test_client_errors_are_not_retried(sdk):
    fake = sdk(HttpError(400))
    with pytest.raises(gemini.GeminiError):
        call_json()
    assert len(fake.calls) == 1 and fake.sleeps == []


def test_network_errors_are_retried(sdk):
    fake = sdk(ConnectionError("uzildi"), interaction())
    assert call_json()[0] is not None and len(fake.calls) == 2


def test_failed_interaction_is_retried(sdk):
    fake = sdk(interaction(status="failed"), interaction())
    assert call_json()[0] is not None and len(fake.calls) == 2


def test_timeout_is_enforced_and_retried(sdk, monkeypatch):
    async def hang():
        await asyncio.sleep(3600)

    monkeypatch.setattr(gemini, "RETRIES", 1)
    fake = sdk(hang, hang)
    real_wait_for = asyncio.wait_for

    async def fast_wait_for(coro, timeout):
        return await real_wait_for(coro, 0.01)

    monkeypatch.setattr(asyncio, "wait_for", fast_wait_for)
    with pytest.raises(gemini.GeminiError):
        call_json()
    assert len(fake.calls) == 2                                   # vaqt chegarasi ham qayta uriniladi


# ------------------------------------------------------------- JSON tekshiruvi --

@pytest.mark.parametrize("raw", ["", "bu JSON emas", "{buzuq", "[1, 2]", '"matn"', "null"])
def test_bad_json_gives_none(sdk, raw):
    sdk(interaction(raw))
    payload, usage = call_json()
    assert payload is None and usage["model"] == MODEL           # sarf baribir hisoblanadi


def test_json_inside_code_fence_is_accepted(sdk):
    sdk(interaction('```json\n{"niyat": "savol"}\n```'))
    assert call_json()[0] == {"niyat": "savol"}


# -------------------------------------------------------------------- usage --

def test_usage_text_only():
    u = gemini.usage_of(interaction(inp=1000, out=200), MODEL)
    assert u == {"model": MODEL, "input_tokens": 1000, "output_tokens": 200,
                 "cache_read": 0, "cache_write": 0, "audio_tokens": 0,
                 "cost_usd": pytest.approx(1000 / 1e6 * 0.30 + 200 / 1e6 * 2.50)}


def test_usage_thinking_tokens_are_billed_as_output():
    u = gemini.usage_of(interaction(inp=1000, out=200, thought=800), MODEL)
    assert u["output_tokens"] == 1000
    assert u["cost_usd"] == pytest.approx(1000 / 1e6 * 0.30 + 1000 / 1e6 * 2.50)


def test_usage_output_never_below_total_minus_input():
    """total_tokens kattaroq chiqish ko'rsatsa — kam hisoblanmaydi."""
    u = gemini.usage_of(interaction(inp=1000, out=200, thought=0, total=1500), MODEL)
    assert u["output_tokens"] == 500


def test_usage_audio_and_cache():
    u = gemini.usage_of(interaction(inp=2000, out=100, cached=500, audio=640), MODEL)
    assert u["input_tokens"] == 1500                  # keshdan o'qilmagani
    assert u["cache_read"] == 500 and u["audio_tokens"] == 640
    assert u["cost_usd"] == pytest.approx(
        860 / 1e6 * 0.30 + 640 / 1e6 * 0.30 + 100 / 1e6 * 2.50 + 500 / 1e6 * 0.03)


def test_usage_missing_data_is_zero_not_crash():
    u = gemini.usage_of(SimpleNamespace(usage=None), MODEL)
    assert u["input_tokens"] == u["output_tokens"] == u["cost_usd"] == 0


def test_cost_follows_the_date_for_flash_38():
    m = "gemini-3.8-flash"
    inp = gemini.usage_of(interaction(inp=1_000_000, out=0), m)["cost_usd"]
    expected = 0.75 if date.today() <= date(2026, 12, 31) else 1.50
    assert inp == pytest.approx(expected)


# ------------------------------------------------------------ kalit va loglar --

def test_missing_key_is_reported(monkeypatch):
    monkeypatch.setattr(gemini, "_client", None)
    monkeypatch.setattr(config, "GEMINI_API_KEY", "")
    assert "GEMINI_API_KEY" in config.missing_settings()
    with pytest.raises(gemini.GeminiError):
        gemini.client()
    monkeypatch.setattr(config, "GEMINI_API_KEY", SECRET)
    assert "GEMINI_API_KEY" not in config.missing_settings()


def test_logs_never_contain_key_or_request_text(sdk, caplog):
    sdk(HttpError(500), HttpError(400))
    caplog.set_level(logging.DEBUG)
    with pytest.raises(gemini.GeminiError) as info:
        run(gemini.generate_json(MODEL, "tizim", [gemini.text_part("MAXFIY-MATN-45000")],
                                 SCHEMA, "minimal", 20))
    logged = caplog.text + str(info.value)
    assert "MAXFIY" not in logged and SECRET not in logged
    assert "HttpError" in logged and "status 500" in logged       # tashxis uchun yetarli
