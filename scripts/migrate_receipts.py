"""Eski cheklarni chek sarlavhasiga bog'laydi (1.4).

Avval chek mahsulotlari `transactions` da alohida qator bo'lib turardi
va ularni faqat umumiy `receipt_id` bog'lardi. Endi har bir chekning
`receipts` jadvalida sarlavhasi bor (do'kon, sana, valyuta). Bu skript
sarlavhasi yo'q eski cheklar uchun sarlavha yaratadi.

Mahsulot qatorlariga TEGILMAYDI — faqat sarlavha QO'SHILADI. Shuning
uchun qaytarish ham oddiy: yaratilgan sarlavhalar o'chiriladi.

    python scripts/migrate_receipts.py              # dry-run
    python scripts/migrate_receipts.py --apply
    python scripts/migrate_receipts.py --rollback migration_backups/receipts-....json
"""

from __future__ import annotations

import _common  # noqa: F401  (yo'l va ish papkasini sozlaydi)
from _common import banner, parser, read_backup, write_backup

import db

NAME = "receipts"


def _shop(raw_text: str | None) -> str:
    """Eski qatorlarda do'kon nomi faqat `raw_text` da: «chek: Korzinka»."""
    raw = (raw_text or "").strip()
    if raw.lower().startswith("chek:"):
        return raw[5:].strip()[:80]
    return ""


def find_missing() -> list[dict]:
    with db.get_conn() as conn:
        rows = conn.execute(
            """SELECT t.user_id, t.receipt_id, MIN(t.occurred_on) AS occurred_on,
                      MAX(t.currency) AS currency, MAX(t.raw_text) AS raw_text,
                      COUNT(*) AS n
               FROM transactions t
               WHERE t.receipt_id IS NOT NULL
                 AND NOT EXISTS (SELECT 1 FROM receipts r
                                 WHERE r.user_id = t.user_id
                                   AND r.receipt_id = t.receipt_id)
               GROUP BY t.user_id, t.receipt_id""").fetchall()
    return [{"user_id": r["user_id"], "receipt_id": r["receipt_id"],
             "occurred_on": r["occurred_on"], "currency": r["currency"] or "som",
             "shop": _shop(r["raw_text"]), "n": r["n"]} for r in rows]


def apply(found: list[dict]) -> None:
    path = write_backup(NAME, {
        "migration": NAME,
        "created": [[f["user_id"], f["receipt_id"]] for f in found],
    })
    print(f"Zaxira (qaytarish uchun): {path}")
    with db.get_conn() as conn:
        for f in found:
            conn.execute(
                """INSERT OR IGNORE INTO receipts
                   (user_id, receipt_id, shop, occurred_on, currency)
                   VALUES (?, ?, ?, ?, ?)""",
                (f["user_id"], f["receipt_id"], f["shop"], f["occurred_on"],
                 f["currency"]))
    print(f"Yaratildi: {len(found)} ta sarlavha.")


def rollback(path: str) -> None:
    payload = read_backup(path, NAME)
    with db.get_conn() as conn:
        n = 0
        for user_id, receipt_id in payload["created"]:
            n += conn.execute(
                "DELETE FROM receipts WHERE user_id = ? AND receipt_id = ?",
                (user_id, receipt_id)).rowcount
    print(f"Qaytarildi: {n} ta sarlavha o'chirildi. Mahsulotlarga tegilmadi.")


def main() -> None:
    args = parser(__doc__.splitlines()[0]).parse_args()
    db.init()
    if args.rollback:
        rollback(args.rollback)
        return

    found = find_missing()
    banner(not args.apply)
    print(f"Sarlavhasi yo'q cheklar: {len(found)}")
    print(f"Ulardagi mahsulot qatorlari: {sum(f['n'] for f in found)} "
          "(o'zgarmaydi)")
    print(f"Do'kon nomi aniqlanganlar: {sum(1 for f in found if f['shop'])}")
    for f in found[:5]:
        print(f"  namuna: chek {f['receipt_id']} · {f['n']} ta mahsulot · "
              f"do'kon {'bor' if f['shop'] else 'yoq'}")

    if args.apply and found:
        apply(found)
    elif found:
        print("\nYozish uchun: --apply")


if __name__ == "__main__":
    main()
