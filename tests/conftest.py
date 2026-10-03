"""Sinov muhiti.

`config` modul yuklanganda muhit o'zgaruvchilarini o'qiydi va
`load_dotenv()` haqiqiy `.env` ni ham yuklaydi. `load_dotenv` mavjud
o'zgaruvchini almashtirmaydi — shuning uchun sinov qiymatlari HAMMA
importdan oldin shu yerda o'rnatiladi va haqiqiy kalitlar (baza kaliti,
bot tokeni) sinovga umuman tushmaydi.

Har bir sinov o'z vaqtinchalik bazasida ishlaydi: shifrlanmagan oddiy
SQLite, ikkita fayl (asosiy va shaxsiy) — serverdagi tuzilma bilan bir xil.
"""

from __future__ import annotations

import os
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(ROOT))

# Jonli test haqiqiy kalitni ishlatadi — uni saqlab qolamiz, qolganini
# sinov qiymatlari bilan almashtiramiz.
_LIVE_KEY = os.environ.get("ANTHROPIC_API_KEY", "")

for name, value in {
    "TELEGRAM_TOKEN": "123:test",
    "ANTHROPIC_API_KEY": _LIVE_KEY or "sk-ant-test",
    "DB_ENCRYPTION_KEY": "",
    "PRIVATE_DB_KEY": "",
    "OWNER_IDS": "",
    "ALLOWED_USER_IDS": "",
    "WEBAPP_URL": "",
    "ADMIN_PANEL_URL": "",
    "TIMEZONE": "Asia/Tashkent",
    "SMALL_NUMBERS_ARE_THOUSANDS": "true",
}.items():
    os.environ[name] = value

import pytest  # noqa: E402

import config  # noqa: E402
import db  # noqa: E402


@pytest.fixture(autouse=True)
def fresh_db(tmp_path, monkeypatch):
    """Har bir sinov uchun bo'sh baza va tarmoqsiz kurs."""
    monkeypatch.setattr(config, "DB_PATH", str(tmp_path / "main.db"))
    monkeypatch.setattr(config, "PRIVATE_DB_PATH", str(tmp_path / "private.db"))
    monkeypatch.setattr(config, "OWNER_IDS", set())
    monkeypatch.setattr(config, "_settings_cache", None)

    import rates
    rates.clear_cache()
    monkeypatch.setattr(rates, "_fetch_cbu", lambda currency, day: 12_600.0)

    db.init()
    yield


@pytest.fixture
def user_id():
    """Rozilik bergan oddiy foydalanuvchi (sinov muddatida)."""
    uid = 1001
    db.get_or_create_user(uid, "Test", None)
    return uid


def pytest_terminal_summary(terminalreporter):
    """Jonli AI testidan keyin natijalar jadvali (pytest -m live)."""
    from tests import live_results
    if not live_results.RESULTS:
        return
    tr = terminalreporter
    tr.section("Jonli AI natijalari")
    tr.write_line("| # | Xabar | Kutilgan | Model javobi | Natija |")
    tr.write_line("|---|---|---|---|---|")
    for i, (group, text, want, got, ok) in enumerate(live_results.RESULTS, 1):
        mark = "✅" if ok else "❌"
        tag = "" if group == "jadval" else " *(qo'shimcha)*"
        tr.write_line(f"| {i} | {text}{tag} | {want} | {got} | {mark} |")
    passed = sum(1 for r in live_results.RESULTS if r[4])
    tr.write_line(f"\n{passed}/{len(live_results.RESULTS)} to'g'ri")
