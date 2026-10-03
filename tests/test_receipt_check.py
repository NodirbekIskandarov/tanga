"""Chek tekshiruvi va chegirma (1.3)."""

import ai
import reports


def _receipt(items, total=None, discount=None, currency="som"):
    return {
        "oqildi": True, "dokon": "Korzinka", "sana": "2026-10-01",
        "mahsulotlar": [{"nomi": f"m{i}", "miqdori": 1, "summa": a,
                         "kategoriya": "oziq-ovqat"} for i, a in enumerate(items)],
        "chekdagi_jami": total, "chegirma": discount, "valyuta": currency,
        "izoh_matni": "",
    }


def test_discount_already_in_line_prices_is_not_subtracted_twice():
    # Jonli sinovdagi aniq holat: qatorlar 260 800, chegirma 50 000,
    # chekdagi jami 260 800 — qatorlarda chegirma allaqachon bor.
    data = _receipt([200_000, 60_800], total=260_800, discount=50_000)
    check = ai.receipt_check(data)
    assert check["holat"] == "mos"
    assert check["narxlar"] == "chegirmadan_keyin"

    data["tekshiruv"] = check
    ai.apply_receipt_total(data)
    assert sum(i["summa"] for i in data["mahsulotlar"]) == 260_800

    text = reports.receipt_text(data)
    assert "⚠️" not in text and "Farq" not in text and "kam chiqdi" not in text
    assert "(narxlarda hisobga olingan)" in text


def test_discount_before_line_prices_is_distributed_proportionally():
    # Qatorlar chegirmagacha: 310 800 − 50 000 = 260 800.
    data = _receipt([210_000, 100_800], total=260_800, discount=50_000)
    check = ai.receipt_check(data)
    assert check["holat"] == "mos"
    assert check["narxlar"] == "chegirmagacha"

    data["tekshiruv"] = check
    ai.apply_receipt_total(data)
    amounts = [i["summa"] for i in data["mahsulotlar"]]
    assert sum(amounts) == 260_800
    # Ulush saqlanadi: 210 000 / 310 800 ≈ 67.6 %.
    assert abs(amounts[0] / 260_800 - 210_000 / 310_800) < 0.001
    assert data["mahsulotlar"][0]["summa_asl"] == 210_000


def test_real_mismatch_still_warns_but_total_is_receipt_total():
    data = _receipt([100_000, 50_000], total=260_800, discount=None)
    check = ai.receipt_check(data)
    assert check["holat"] == "farqli"
    data["tekshiruv"] = check
    ai.apply_receipt_total(data)
    assert sum(i["summa"] for i in data["mahsulotlar"]) == 260_800
    assert "⚠️" in reports.receipt_text(data)


def test_tolerance_is_one_percent_or_1000_som():
    assert ai.receipt_tolerance(50_000) == 1000
    assert ai.receipt_tolerance(260_800) == 2608
    # 2 000 so'm farq 260 800 da — 1 % ichida, ogohlantirish yo'q.
    data = _receipt([258_800], total=260_800)
    assert ai.receipt_check(data)["holat"] == "mos"
    # 5 000 so'm farq — haqiqiy xato.
    data = _receipt([255_800], total=260_800)
    assert ai.receipt_check(data)["holat"] == "farqli"


def test_no_printed_total_keeps_amounts():
    data = _receipt([10_000, 5_000])
    check = ai.receipt_check(data)
    assert check["holat"] == "jami_yoq"
    data["tekshiruv"] = check
    ai.apply_receipt_total(data)
    assert [i["summa"] for i in data["mahsulotlar"]] == [10_000, 5_000]


def test_fit_to_total_is_exact():
    fitted = ai.fit_to_total([3333, 3333, 3334], 9_999)
    assert sum(fitted) == 9_999
    fitted = ai.fit_to_total([10.10, 5.05], 13.00, "usd")
    assert round(sum(fitted), 2) == 13.00
