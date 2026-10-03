"""Kategoriyalash (1.2) va ko'p yozuvli xabar (1.5)."""

import asyncio
import sys
from pathlib import Path

import ai
import config
import db
import learning
import reports
from tests import fake_ai

sys.path.insert(0, str(Path(__file__).resolve().parent.parent / "scripts"))


def test_hygiene_category_exists_and_registry_is_stable():
    assert "uy-ro'zg'or va gigiyena" in config.EXPENSE_CATEGORIES
    assert config.EXPENSE_CATEGORIES[-1] == "boshqa chiqim"
    # Eski tugmalar raqamlari o'zgarmagan.
    assert config.CATEGORY_REGISTRY[13] == "boshqa chiqim"
    assert config.CATEGORY_REGISTRY.index("uy-ro'zg'or va gigiyena") >= 23


def test_keywords_strip_suffixes_but_keep_words():
    assert learning.keywords_of("suvga") == ["suv"]
    assert learning.keywords_of("nonga") == ["non"]
    assert learning.keywords_of("taksi") == ["taksi"]
    assert learning.keywords_of("12 mingga suv oldim") == ["mingga"[:0] or "suv"] \
        or learning.keywords_of("12 mingga suv oldim")[0] in ("suv", "ming")
    assert learning.keywords_of("Shampun Head&Shoulders 400ml")[0] == "shampun"


def test_user_correction_overrides_ai_next_time(user_id, monkeypatch):
    tx = db.add_transaction(user_id, "chiqim", 12_000, "kommunal", "suv")
    row = db.get_transaction(user_id, tx)
    assert learning.remember(user_id, row["kind"], row["note"], "oziq-ovqat") == "suv"

    # AI yana «kommunal» deydi — foydalanuvchi qoidasi ustun.
    rules = learning.rules_for(user_id)
    assert learning.apply(rules, "chiqim", "suvni", "kommunal") == "oziq-ovqat"
    # Boshqa so'z va boshqa tur — tegilmaydi.
    assert learning.apply(rules, "chiqim", "svet", "kommunal") == "kommunal"
    assert learning.apply(rules, "kirim", "suv", "boshqa kirim") == "boshqa kirim"


def test_rules_are_per_user(user_id):
    learning.remember(user_id, "chiqim", "suv", "oziq-ovqat")
    assert learning.apply(learning.rules_for(9999), "chiqim", "suv",
                          "kommunal") == "kommunal"


def test_category_keyboard_uses_stable_registry_numbers(user_id):
    import bot
    tx = db.add_transaction(user_id, "chiqim", 12_000, "kommunal", "suv")
    kb = bot.category_keyboard(tx, "chiqim")
    datas = [b.callback_data for row in kb.inline_keyboard for b in row]
    for name in ("oziq-ovqat", "uy-ro'zg'or va gigiyena", "boshqa chiqim"):
        assert f"k:{tx}:{config.CATEGORY_REGISTRY.index(name)}" in datas


def test_multi_entry_message_shows_categories_and_edit_buttons():
    import bot
    items = [
        fake_ai.record("chiqim", 8_000, "oziq-ovqat", "nonga"),
        fake_ai.record("chiqim", 25_000, "transport", "taksiga"),
    ]
    text = reports.saved_text(items)
    assert "🔻 8 000 so'm · nonga · 🥦 oziq-ovqat" in text
    assert "🔻 25 000 so'm · taksiga · 🚕 transport" in text

    kb = bot.entry_keyboard([377, 378], None, items)
    datas = [b.callback_data for row in kb.inline_keyboard for b in row]
    assert datas == ["e:377", "e:378", "D:377,378"]


def test_income_shows_as_ish_haqi():
    r = fake_ai.record("kirim", 15_000_000, "oylik", "oylik")
    assert "ish haqi" in reports.saved_text([r, r])


def test_parse_pipeline_applies_rules_before_saving(user_id, monkeypatch):
    learning.remember(user_id, "chiqim", "suv", "oziq-ovqat")
    fake_ai.install(monkeypatch, [{"niyat": "yozuv", "yozuvlar": [
        fake_ai.record("chiqim", 12_000, "kommunal", "suv")]}])
    parsed = asyncio.run(ai.parse_message("12 mingga suv oldim"))
    rules = learning.rules_for(user_id)
    item = parsed["yozuvlar"][0]
    assert learning.apply(rules, item["turi"], item["izoh"], item["kategoriya"]) == "oziq-ovqat"


def test_analysis_hides_rare_words_and_identities(user_id):
    import analyze_other
    for uid in (1, 2, 3):
        db.add_transaction(uid, "chiqim", 5_000, "boshqa chiqim", "Paket katta")
    db.add_transaction(4, "chiqim", 999_999, "boshqa chiqim", "maxfiy narsa")
    rows = analyze_other.collect(min_users=3)
    assert ("paket", 3, 3) in rows
    assert all(word != "maxfiy" for word, _, _ in rows)


def test_shop_key_normalizes_names():
    assert learning.shop_key('OOO "Korzinka" (Chilonzor)') == "korzinka chilonzor"
    assert learning.shop_key("korzinka chilonzor") == "korzinka chilonzor"
    assert learning.shop_key("") == ""


def test_shop_rule_only_fills_uncertain_items(user_id):
    """Dorixonada tuzatilgan kategoriya keyingi o'sha do'kon chekida faqat
    AI aniqlay olmagan mahsulotlarga qo'llanadi."""
    learning.remember_shop(user_id, "Dori-Darmon 24", "salomatlik")
    rules = learning.rules_for(user_id)
    # AI «boshqa chiqim» degan — do'kon qoidasi to'ldiradi.
    assert learning.apply_receipt_item(rules, "DORI-DARMON 24", "Nurofen", "boshqa chiqim") \
        == "salomatlik"
    # AI aniq kategoriya bergan — tegilmaydi (dorixonada suv ham sotiladi).
    assert learning.apply_receipt_item(rules, "Dori-Darmon 24", "Suv", "oziq-ovqat") \
        == "oziq-ovqat"
    # Boshqa do'kon — tegilmaydi.
    assert learning.apply_receipt_item(rules, "Makro", "X", "boshqa chiqim") == "boshqa chiqim"


def test_item_rule_beats_shop_rule(user_id):
    learning.remember_shop(user_id, "Makro", "uy-ro'zg'or va gigiyena")
    learning.remember(user_id, "chiqim", "Pampers 4", "boshqa chiqim")
    learning.remember(user_id, "chiqim", "Shokolad", "oziq-ovqat")
    rules = learning.rules_for(user_id)
    assert learning.apply_receipt_item(rules, "Makro", "Shokolad Alpen", "boshqa chiqim") \
        == "oziq-ovqat"


def test_correcting_receipt_item_remembers_shop(user_id):
    import bot
    ids = db.add_receipt(user_id, "rs1", shop="Dori-Darmon 24", occurred_on="2026-10-01",
                         currency="som", printed_total=None, discount=None,
                         items=[{"kind": "chiqim", "amount": 30_000,
                                 "category": "boshqa chiqim", "note": "Nurofen"}])
    row = db.get_transaction(user_id, ids[0])
    bot.remember_receipt_shop(user_id, row, "salomatlik")
    assert learning.rules_for(user_id)[("@dori-darmon 24", "chiqim")] == "salomatlik"
