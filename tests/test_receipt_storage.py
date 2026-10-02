"""Chek bitta yozuv sifatida (1.4)."""

import sys
from pathlib import Path

import db
import reports

sys.path.insert(0, str(Path(__file__).resolve().parent.parent / "scripts"))


def _save_receipt(uid, rid="r1", shop="Korzinka", n=15):
    items = [{"kind": "chiqim", "amount": 10_000 + i, "category": "oziq-ovqat",
              "note": f"mahsulot {i}", "raw_text": f"chek: {shop}"} for i in range(n)]
    return db.add_receipt(uid, rid, shop=shop, occurred_on="2026-10-01",
                          currency="som", printed_total=None, discount=None,
                          items=items)


def test_receipt_is_one_line_in_recent(user_id):
    ids = _save_receipt(user_id)
    db.add_transaction(user_id, "chiqim", 25_000, "transport", "taksi",
                       occurred_on="2026-10-01")

    entries = db.recent_entries(user_id)
    assert len(entries) == 2
    receipt = next(e for e in entries if e["receipt_id"])
    assert receipt["n"] == 15
    assert receipt["id"] == max(ids)

    text = reports.recent_text(user_id)
    assert "🧾 Korzinka cheki — " in text
    assert "(15 mahsulot) · <i>1-oktabr</i>" in text
    assert text.count("mahsulot 1") == 0     # mahsulotlar alohida chiqmaydi


def test_delete_receipt_removes_header_and_items(user_id):
    _save_receipt(user_id)
    assert db.get_receipt(user_id, "r1")["n"] == 15

    removed = db.delete_receipt(user_id, "r1")
    assert removed == 15
    assert db.rows_by_receipt(user_id, "r1") == []
    with db.get_conn() as conn:
        assert conn.execute("SELECT COUNT(*) FROM receipts").fetchone()[0] == 0


def test_bot_delete_by_item_id_removes_whole_receipt(user_id):
    import bot
    ids = _save_receipt(user_id, n=3)
    assert bot.delete_entry(user_id, ids[0]) == 3
    assert db.rows_by_receipt(user_id, "r1") == []


def test_category_analysis_stays_item_level(user_id):
    from datetime import date
    db.add_receipt(user_id, "r2", shop="Makro", occurred_on="2026-10-01",
                   currency="som", printed_total=None, discount=None, items=[
                       {"kind": "chiqim", "amount": 30_000, "category": "oziq-ovqat",
                        "note": "non"},
                       {"kind": "chiqim", "amount": 20_000,
                        "category": "uy-ro'zg'or va gigiyena", "note": "sovun"},
                   ])
    cats = dict((c, s) for c, s, _ in db.by_category_unified(
        user_id, date(2026, 10, 1), date(2026, 10, 31), "chiqim"))
    assert cats == {"oziq-ovqat": 30_000, "uy-ro'zg'or va gigiyena": 20_000}


def test_csv_has_receipt_id_on_every_item(user_id):
    _save_receipt(user_id, n=2)
    content, count = reports.csv_bytes(user_id)
    lines = content.decode("utf-8-sig").strip().splitlines()
    assert count == 2
    assert lines[0].endswith("chek_id,dokon")
    assert all(line.endswith(",r1,Korzinka") for line in lines[1:])


def test_migration_links_old_receipts(user_id, tmp_path, monkeypatch):
    import _common
    import migrate_receipts as m
    monkeypatch.setattr(_common, "BACKUP_DIR", tmp_path / "backups")

    # Eski uslubdagi chek: sarlavhasiz, faqat receipt_id bilan.
    db.add_many([{"user_id": user_id, "kind": "chiqim", "amount": 5_000,
                  "category": "oziq-ovqat", "note": "non",
                  "occurred_on": "2026-09-30", "raw_text": "chek: Havas",
                  "receipt_id": "old1"}] * 3)

    found = m.find_missing()
    assert [(f["receipt_id"], f["shop"], f["n"]) for f in found] == [("old1", "Havas", 3)]

    m.apply(found)
    assert m.find_missing() == []
    assert db.get_receipt(user_id, "old1")["shop"] == "Havas"

    backup = next((tmp_path / "backups").glob("receipts-*.json"))
    m.rollback(str(backup))
    assert len(m.find_missing()) == 1
    assert len(db.rows_by_receipt(user_id, "old1")) == 3   # mahsulotlar joyida
