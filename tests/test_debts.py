"""Qarz turlari (1.1): statistikaga kirmaydi, qaytarish qarzni yopadi."""

import asyncio
import sys
from pathlib import Path

import ai
import config
import db
import reports
from tests import fake_ai

sys.path.insert(0, str(Path(__file__).resolve().parent.parent / "scripts"))

# Hisobotlar «bugun» ni tizim soatidan oladi — sinov ham shundan.
TODAY = reports.today()


def _add(uid, kind, amount, person=None, day=None, category=None, note=""):
    return db.add_transaction(uid, kind, amount,
                              category or config.fallback_category(kind),
                              note, person, occurred_on=day or TODAY.isoformat())


def test_debt_kinds_do_not_change_todays_spending(user_id):
    _add(user_id, "chiqim", 50_000, category="oziq-ovqat")
    before = db.totals_unified(user_id, TODAY, TODAY)["totals"]["chiqim"]

    _add(user_id, "qarz_qaytardim", 1_000_000)
    _add(user_id, "qarz_berdim", 200_000, "Akmal")
    _add(user_id, "qarz_qaytdi", 200_000, "Akmal")
    _add(user_id, "qarz_oldim", 500_000, "Sardor")

    totals = db.totals_unified(user_id, TODAY, TODAY)["totals"]
    assert totals["chiqim"] == before == 50_000
    assert totals["kirim"] == 0
    assert totals["qarz_qaytardim"] == 1_000_000
    # Kategoriya foizlari faqat chiqimdan: «qarz» ulushi yo'q.
    cats = db.by_category_unified(user_id, TODAY, TODAY, "chiqim")
    assert [c for c, _, _ in cats] == ["oziq-ovqat"]


def test_report_shows_debts_separately_from_spending(user_id):
    _add(user_id, "chiqim", 50_000, category="oziq-ovqat")
    _add(user_id, "qarz_qaytardim", 1_000_000)
    text = reports.summary_text(user_id, "bugun")
    assert "Chiqim:" in text
    assert "1 000 000" in text and "Qarzimni qaytardim" in text
    assert "(chiqimga kirmaydi)" in text
    chiqim_line = next(line for line in text.splitlines() if "Chiqim:" in line)
    assert "50 000" in chiqim_line


def test_repayment_reduces_debt_by_person_fifo(user_id):
    _add(user_id, "qarz_berdim", 200_000, "Akmal", day="2026-09-01")
    _add(user_id, "qarz_berdim", 100_000, "Akmal", day="2026-09-10")

    _add(user_id, "qarz_qaytdi", 250_000, "akmal ", day="2026-10-01")
    debts = db.open_debts(user_id)
    assert [(d["amount"], d["remaining"]) for d in debts] == [(100_000, 50_000)]

    _add(user_id, "qarz_qaytdi", 50_000, "AKMAL", day="2026-10-02")
    assert db.open_debts(user_id) == []


def test_repayment_does_not_close_later_debt_or_other_direction(user_id):
    _add(user_id, "qarz_qaytdi", 100_000, "Akmal", day="2026-09-01")
    _add(user_id, "qarz_berdim", 100_000, "Akmal", day="2026-09-05")
    _add(user_id, "qarz_oldim", 100_000, "Akmal", day="2026-08-01")
    debts = db.open_debts(user_id)
    assert {(d["kind"], d["remaining"]) for d in debts} == {
        ("qarz_berdim", 100_000), ("qarz_oldim", 100_000)}


def test_net_worth_uses_remaining(user_id):
    _add(user_id, "qarz_oldim", 1_000_000, "Sardor", day="2026-09-01")
    _add(user_id, "qarz_qaytardim", 400_000, "Sardor", day="2026-09-20")
    assert db.net_worth(user_id)["i_owe"] == 600_000


def test_parse_keeps_debt_kinds_and_drops_person_suffixes(monkeypatch):
    fake_ai.install(monkeypatch, [{"niyat": "yozuv", "yozuvlar": [
        fake_ai.record("qarz_qaytardim", 1_000_000, "boshqa chiqim", "qarz to'lovi"),
        fake_ai.record("qarz_qaytdi", 200_000, "", "qarz", "Akmal"),
    ]}])
    parsed = asyncio.run(ai.parse_message("...", today=TODAY))
    kinds = [(r["turi"], r["kategoriya"], r["shaxs"]) for r in parsed["yozuvlar"]]
    assert kinds == [("qarz_qaytardim", "qarz", None), ("qarz_qaytdi", "qarz", "Akmal")]


def test_kind_switches_allow_fixing_misclassified_repayment(user_id):
    assert "qarz_qaytardim" in config.KIND_SWITCHES["chiqim"]
    assert "qarz_qaytdi" in config.KIND_SWITCHES["kirim"]
    assert "qarz_berdim" not in config.KIND_SWITCHES["chiqim"]


def test_migration_reclassifies_old_debt_payments(user_id, tmp_path, monkeypatch):
    import _common
    import migrate_debts as m
    monkeypatch.setattr(_common, "BACKUP_DIR", tmp_path / "b")

    a = _add(user_id, "kirim", 1_000_000, note="qarz to'lovi",
             category="boshqa kirim")
    db.add_transaction(user_id, "chiqim", 1_000_000, "boshqa chiqim",
                       "qarz qaytimi", raw_text="1 mln qarzim uchun tolandi")
    c = _add(user_id, "kirim", 300_000, note="Akmal qarzini qaytardi")
    _add(user_id, "chiqim", 20_000, note="taksi", category="transport")

    found = {f["id"]: f["new_kind"] for f in m.find_candidates()}
    assert len(found) == 3
    assert found[c] == "qarz_qaytdi"
    assert found[a] is None                    # yo'nalish noaniq — tegilmaydi

    assert m.apply(m.find_candidates(), None) == 2
    assert db.get_transaction(user_id, a)["kind"] == "kirim"
    assert db.get_transaction(user_id, c)["kind"] == "qarz_qaytdi"
    assert db.totals_unified(user_id, TODAY, TODAY)["totals"]["chiqim"] == 20_000

    m.rollback(str(next((tmp_path / "b").glob("debts-*.json"))))
    assert db.get_transaction(user_id, c)["kind"] == "kirim"
    assert db.get_transaction(user_id, c)["category"] == "boshqa kirim"
