"""Jonli AI testi — haqiqiy model bilan (1.6).

STANDART ISHGA TUSHIRISHDA VA CI DA O'TKAZIB YUBORILADI (pytest.ini).
Faqat qo'lda:

    pytest -m live

Kalit GEMINI_API_KEY muhit o'zgaruvchisidan yoki `.env` dan olinadi
(faqat billing yoqilgan, PULLIK daraja kaliti). Narxi: ~16 ta qisqa
so'rov PARSE_MODEL da (bir necha sent). Oxirida natijalar jadvali
chiqadi (conftest.py, pytest_terminal_summary).

Bu test promptning SIFATINI tekshiradi — oflayn testlar esa AI javobidan
keyingi yo'lni. Ikkalasi ham kerak.
"""

from __future__ import annotations

import asyncio
import os
from datetime import date, timedelta

import pytest
from dotenv import dotenv_values

import ai
import config
import gemini
import reports
from tests import live_results

pytestmark = pytest.mark.live

TODAY = reports.today()
YESTERDAY = (TODAY - timedelta(days=1)).isoformat()

# (xabar, [(tur, summa, valyuta, kategoriyalar yoki None, shaxs, sana)])
# Kategoriya None — tekshirilmaydi (qarz turlarida doim «qarz»).
TABLE = [
    ("12 mingga suv oldim",
     [("chiqim", 12_000, "som", {"oziq-ovqat"}, None, None)]),
    ("suv puliga 45 ming to'ladim",
     [("chiqim", 45_000, "som", {"kommunal"}, None, None)]),
    ("1 mln qarzim uchun to'landi",
     [("qarz_qaytardim", 1_000_000, "som", None, None, None)]),
    ("Akmalga 200 ming qarz berdim",
     [("qarz_berdim", 200_000, "som", None, "Akmal", None)]),
    ("Akmal 200 mingni qaytardi",
     [("qarz_qaytdi", 200_000, "som", None, "Akmal", None)]),
    ("kreditga 2,5 mln to'ladim",
     [("qarz_qaytardim", 2_500_000, "som", None, None, None)]),
    ("oylik 15 mln tushdi",
     [("kirim", 15_000_000, "som", {"oylik"}, None, None)]),
    ("50$ ga kitob oldim",
     [("chiqim", 50, "usd", {"ta'lim"}, None, None)]),
    ("nonga 8 ming, taksiga 25 ming",
     [("chiqim", 8_000, "som", {"oziq-ovqat"}, None, None),
      ("chiqim", 25_000, "som", {"transport"}, None, None)]),
    ("kecha kechki ovqatga 42 ming",
     [("chiqim", 42_000, "som", {"kafe va restoran", "oziq-ovqat"}, None, YESTERDAY)]),
    ("shampun va sovunga 60 ming",
     [("chiqim", 60_000, "som", {"uy-ro'zg'or va gigiyena"}, None, None)]),
    ("yigirma besh mingga taksi",
     [("chiqim", 25_000, "som", {"transport"}, None, None)]),
]

# Qarz iboralarining kirill va rus variantlari (1.1 talabi).
EXTRA = [
    ("Sardordan 500 ming qarz oldim",
     [("qarz_oldim", 500_000, "som", None, "Sardor", None)]),
    ("қарзимни қайтардим 300 минг",
     [("qarz_qaytardim", 300_000, "som", None, None, None)]),
    # Ism doim lotinda saqlanadi — kirillda berilgan qarz bilan ham
    # bog'lanadi (db.person_key ikkala yozuvni birlashtiradi).
    ("Акмал вернул долг 200 тысяч",
     [("qarz_qaytdi", 200_000, "som", None, "Akmal", None)]),
    ("заплатил за кредит 1,2 млн",
     [("qarz_qaytardim", 1_200_000, "som", None, None, None)]),
]


@pytest.fixture(autouse=True)
def real_key(monkeypatch):
    key = (os.environ.get("GEMINI_API_KEY")
           or dotenv_values(".env").get("GEMINI_API_KEY") or "").strip()
    if not key or key == "gemini-test-key":
        pytest.skip("haqiqiy GEMINI_API_KEY yo'q (muhit yoki .env)")
    monkeypatch.setattr(config, "GEMINI_API_KEY", key)
    monkeypatch.setattr(gemini, "_client", None)


def _check(text: str, expected: list[tuple]) -> tuple[bool, str]:
    parsed = asyncio.run(ai.parse_message(text, today=TODAY))
    got = parsed["yozuvlar"]
    shown = "; ".join(
        f"{r['turi']} {r['summa']:g} {r['valyuta']} {config.category_label(r['kategoriya'])}"
        + (f" ({r['shaxs']})" if r["shaxs"] else "")
        + (f" [{r['sana']}]" if r["sana"] != TODAY.isoformat() else "")
        for r in got) or f"(yozuv yo'q: {parsed['niyat']})"

    ok = len(got) == len(expected)
    for r, (kind, amount, cur, cats, person, day) in zip(got, expected):
        ok &= r["turi"] == kind and abs(r["summa"] - amount) < 0.01 and r["valyuta"] == cur
        if cats is not None:
            ok &= r["kategoriya"] in cats
        if person is not None:
            ok &= (r["shaxs"] or "").casefold() == person.casefold()
        if day is not None:
            ok &= r["sana"] == day
    return ok, shown


def _expected_str(expected):
    return "; ".join(
        f"{k} {a:g} {c}" + (f" {'/'.join(config.category_label(x) for x in sorted(cats))}"
                            if cats else "")
        + (f" ({p})" if p else "") + (" [kecha]" if d else "")
        for k, a, c, cats, p, d in expected)


@pytest.mark.parametrize("text,expected", TABLE + EXTRA, ids=[t for t, _ in TABLE + EXTRA])
def test_live_parse(text, expected):
    ok, shown = _check(text, expected)
    group = "jadval" if (text, expected) in TABLE else "qo'shimcha"
    live_results.RESULTS.append((group, text, _expected_str(expected), shown, ok))
    assert ok, f"{text!r}: kutilgan {_expected_str(expected)}, olindi {shown}"


# 3-bosqich: jamg'arma maqsadi va qarz muddati maydonlari.
FIELDS = [
    ("mashina uchun 3 mln jamg'armaga qo'ydim",
     "jamgarma", 3_000_000, "maqsad", "mashina"),
    ("Akmalga 200 ming qarz berdim, 2 haftada qaytaradi",
     "qarz_berdim", 200_000, "muddat", (TODAY + timedelta(days=14)).isoformat()),
]


@pytest.mark.parametrize("text,kind,amount,field,want", FIELDS, ids=[f[0] for f in FIELDS])
def test_live_fields(text, kind, amount, field, want):
    parsed = asyncio.run(ai.parse_message(text, today=TODAY))
    rows = parsed["yozuvlar"]
    got = rows[0] if rows else {}
    value = got.get(field)
    if field == "maqsad":
        ok = bool(value) and want in value.casefold()
    else:
        # «2 haftada» — 13–15 kun oralig'i qabul qilinadi.
        ok = bool(value) and abs((date.fromisoformat(value) -
                                  date.fromisoformat(want)).days) <= 1
    ok = ok and got.get("turi") == kind and abs(got.get("summa", 0) - amount) < 0.01
    shown = f"{got.get('turi')} {got.get('summa', 0):g} {field}={value}"
    live_results.RESULTS.append(("qo'shimcha", text, f"{kind} {amount:g} {field}={want}",
                                 shown, ok))
    assert ok, shown
