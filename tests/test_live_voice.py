"""Jonli ovoz testi — haqiqiy Gemini va haqiqiy ovoz namunalari bilan.

STANDART ISHGA TUSHIRISHDA O'TKAZIB YUBORILADI (pytest.ini). Faqat qo'lda:

    GEMINI_API_KEY=... pytest -m live tests/test_live_voice.py

Namunalar `tests/live_voice/` da (README.md): har biri `.ogg` (yoki mp3/m4a/
wav) fayl va `expected.json` dagi yozuv. Kamida 30 ta haqiqiy namuna kerak:
erkak va ayol ovozi, Toshkent va boshqa viloyat talaffuzi, shovqinli ko'cha,
o'zbek lotin / rus / aralash gaplar, bir xabarda 2–3 yozuv, qarz
(berdim/oldim/qaytardim), dollar, «kecha», jamg'arma, savol, moliyaga
aloqasiz gap, jim yoki bo'sh audio.

QABUL MEZONI (7-bo'lim): tur va summa kamida 90% to'g'ri; NOTO'G'RI SUMMA
JIMGINA SAQLANGAN HOLAT 0 ta — xato bo'lsa, u «past ishonch» bilan tasdiqqa
tushishi shart. Natijalar jadvali oxirida chiqadi (conftest).
"""

from __future__ import annotations

import asyncio
import json
import os
from pathlib import Path

import pytest
from dotenv import dotenv_values

import ai
import config
import gemini
import reports
from tests import live_results

pytestmark = pytest.mark.live

FOLDER = Path(__file__).parent / "live_voice"
MIN_SAMPLES = 30
MIME = {".ogg": "audio/ogg", ".oga": "audio/ogg", ".opus": "audio/ogg",
        ".mp3": "audio/mpeg", ".m4a": "audio/m4a", ".wav": "audio/wav"}
TODAY = reports.today()


def _samples() -> list[dict]:
    path = FOLDER / "expected.json"
    if not path.exists():
        return []
    return [s for s in json.loads(path.read_text(encoding="utf-8"))
            if (FOLDER / s["file"]).exists()]


SAMPLES = _samples()


@pytest.fixture(autouse=True)
def real_key(monkeypatch):
    key = (os.environ.get("GEMINI_API_KEY")
           or dotenv_values(".env").get("GEMINI_API_KEY") or "").strip()
    if not key or key == "gemini-test-key":
        pytest.skip("haqiqiy GEMINI_API_KEY yo'q (muhit yoki .env)")
    monkeypatch.setattr(config, "GEMINI_API_KEY", key)
    monkeypatch.setattr(gemini, "_client", None)


def _matches(got: list[dict], want: list[dict]) -> bool:
    """Tur, summa va valyuta (va berilgan bo'lsa shaxs, kategoriya) mos keladimi."""
    if len(got) != len(want):
        return False
    for r, w in zip(got, want):
        if r["turi"] != w["turi"] or abs(r["summa"] - w["summa"]) > 0.01:
            return False
        if r["valyuta"] != w.get("valyuta", "som"):
            return False
        if w.get("shaxs") and (r["shaxs"] or "").casefold() != w["shaxs"].casefold():
            return False
        if w.get("kategoriya") and r["kategoriya"] not in w["kategoriya"]:
            return False
    return True


def _run(sample: dict) -> dict:
    path = FOLDER / sample["file"]
    audio = path.read_bytes()
    return asyncio.run(ai.parse_voice(audio, MIME.get(path.suffix.lower(), "audio/ogg"),
                                      today=TODAY))


def _expected_str(sample: dict) -> str:
    want = sample["expected"]
    rows = "; ".join(f"{w['turi']} {w['summa']:g} {w.get('valyuta', 'som')}"
                     + (f" ({w['shaxs']})" if w.get("shaxs") else "")
                     for w in want.get("yozuvlar", []))
    return rows or f"({want['niyat']})"


def _shown(parsed: dict) -> str:
    rows = "; ".join(f"{r['turi']} {r['summa']:g} {r['valyuta']}"
                     + (f" ({r['shaxs']})" if r["shaxs"] else "")
                     for r in parsed["yozuvlar"])
    return f"{rows or '(' + parsed['niyat'] + ')'} [{parsed['ishonch']}]"


def test_live_voice_acceptance():
    if len(SAMPLES) < MIN_SAMPLES:
        pytest.skip(f"kamida {MIN_SAMPLES} ta haqiqiy namuna kerak "
                    f"(hozir {len(SAMPLES)}): tests/live_voice/README.md")
    correct = silent_wrong = 0
    for s in SAMPLES:
        parsed = _run(s)
        want = s["expected"]
        if want["niyat"] == "yozuv":
            ok = parsed["niyat"] == "yozuv" and _matches(parsed["yozuvlar"],
                                                        want["yozuvlar"])
        else:
            ok = parsed["niyat"] == want["niyat"]
        # Jimgina noto'g'ri saqlash: yozuv chiqdi, noto'g'ri, lekin «yuqori ishonch».
        silent = (not ok) and parsed["niyat"] == "yozuv" and bool(parsed["yozuvlar"]) \
            and parsed["ishonch"] == "yuqori"
        correct += ok
        silent_wrong += silent
        live_results.RESULTS.append(("ovoz", s["file"], _expected_str(s), _shown(parsed), ok))
    accuracy = correct / len(SAMPLES)
    print(f"\nOVOZ: {correct}/{len(SAMPLES)} to'g'ri ({accuracy:.0%}); "
          f"jimgina noto'g'ri: {silent_wrong}")
    assert silent_wrong == 0, "noto'g'ri summa jimgina saqlangan namunalar bor"
    assert accuracy >= 0.90, f"aniqlik {accuracy:.0%} < 90%"
