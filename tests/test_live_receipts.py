"""Jonli chek testi — 20 ta haqiqiy chek rasmi bilan.

STANDART ISHGA TUSHIRISHDA O'TKAZIB YUBORILADI (pytest.ini). Faqat qo'lda:

    GEMINI_API_KEY=... pytest -m live tests/test_live_receipts.py

Rasmlar `tests/live_receipts/` da (README.md): har biri `expected.json` da
chekdagi yakuniy JAMI bilan. Ko'rsatkich — «jami bilan mos» ulushi:
mahsulotlar yig'indisi (Python hisoblagan) chekdagi jami bilan ruxsat
etilgan farq (`ai.receipt_tolerance`) ichida bo'lgan cheklar ulushi.

Bu fayl eski (Gemini'gacha bo'lgan) versiyada ham ishlaydi — `ai.parse_receipt` interfeysi
bir xil — shuning uchun bazani o'sha usul bilan o'lchab, Gemini bilan
solishtirish mumkin (docs/gemini-baholash.md).
"""

from __future__ import annotations

import asyncio
import base64
import json
import os
from pathlib import Path

import pytest
from dotenv import dotenv_values

import ai
import config
from tests import live_results

pytestmark = pytest.mark.live

FOLDER = Path(__file__).parent / "live_receipts"
MIN_SAMPLES = 20
MEDIA = {".jpg": "image/jpeg", ".jpeg": "image/jpeg", ".png": "image/png",
         ".webp": "image/webp", ".pdf": "application/pdf"}


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
    try:
        import gemini
        monkeypatch.setattr(gemini, "_client", None)
    except ImportError:                       # Gemini'gacha bo'lgan versiya
        pass


def test_live_receipts_total_matches():
    if len(SAMPLES) < MIN_SAMPLES:
        pytest.skip(f"kamida {MIN_SAMPLES} ta haqiqiy chek kerak "
                    f"(hozir {len(SAMPLES)}): tests/live_receipts/README.md")
    matched = 0
    for s in SAMPLES:
        path = FOLDER / s["file"]
        image = (base64.b64encode(path.read_bytes()).decode(),
                 MEDIA.get(path.suffix.lower(), "image/jpeg"))
        data = asyncio.run(ai.parse_receipt([image]))
        want = float(s["jami"])
        check = data["tekshiruv"]
        ok = (data["oqildi"] and check["chekdagi"] is not None
              and abs(check["chekdagi"] - want) <= ai.receipt_tolerance(want)
              and check["holat"] == "mos")
        matched += ok
        shown = (f"o'qildi={data['oqildi']} chek jami={check['chekdagi']} "
                 f"hisoblangan={check['hisoblangan']} holat={check['holat']}")
        live_results.RESULTS.append(("chek", s["file"], f"jami {want:g}", shown, ok))
    share = matched / len(SAMPLES)
    print(f"\nCHEK: {matched}/{len(SAMPLES)} jami bilan mos ({share:.0%})")
    live_results.SUMMARY["chek_mos"] = share
