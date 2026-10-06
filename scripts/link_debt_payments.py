"""Ismsiz qarz to'lovlarini yagona ismsiz qarzga bog'laydi (2-bo'lim).

Avval ismsiz qaytarish («qarzimni qaytardim», «kreditga to'ladim») hech
bir qarzga tushmasdi va «noma'lum 10 mln» qarz hech qachon kamaymasdi.
Endi bot hisoblashda bunday to'lovni yagona ochiq ismsiz qarzga o'zi
yozadi (db.debt_ledger, 3-bosqich). Bu skript o'sha bog'lanishni bazaga
`repays_id` bilan YOZIB qo'yadi: keyin ikkinchi ismsiz qarz paydo bo'lsa
ham eski to'lovlar o'z qarzida qoladi.

Faqat aniq holatlar: to'lov bilan bir xil yo'nalish va valyutada, to'lovdan
OLDIN olingan, qo'lda yopilmagan ismsiz qarz BITTA bo'lsa. Bir nechta
bo'lsa — «?» bilan ko'rsatiladi va tegilmaydi (botda «qaysi qarz?» deb
so'raladi).

    python scripts/link_debt_payments.py              # dry-run
    python scripts/link_debt_payments.py --apply
    python scripts/link_debt_payments.py --rollback migration_backups/debtlink-....json

Chiqarishda summa va foydalanuvchi ko'rsatilmaydi — faqat yozuv raqamlari.
"""

from __future__ import annotations

import _common  # noqa: F401  (yo'l va ish papkasini sozlaydi)
from _common import banner, parser, read_backup, write_backup

import config
import db

NAME = "debtlink"


def find_candidates() -> list[dict]:
    with db.get_conn() as conn:
        rows = [dict(r) for r in conn.execute(
            """SELECT id, user_id, kind, currency, person, occurred_on, settled
               FROM transactions WHERE kind IN (?, ?, ?, ?)
               ORDER BY occurred_on, id""",
            (config.KIND_QARZ_BERDIM, config.KIND_QARZ_OLDIM,
             config.KIND_QARZ_QAYTARDIM, config.KIND_QARZ_QAYTDI)).fetchall()]
        linked = {r[0] for r in conn.execute(
            "SELECT id FROM transactions WHERE repays_id IS NOT NULL")}
    debts = [r for r in rows if r["kind"] in config.DEBT_OPEN_KINDS
             and not r["settled"] and not db.person_key(r["person"])]
    out = []
    for pay in rows:
        if (pay["kind"] not in config.REPAYS or pay["id"] in linked
                or db.person_key(pay["person"])):
            continue
        cands = [d for d in debts
                 if d["user_id"] == pay["user_id"]
                 and d["kind"] == config.REPAYS[pay["kind"]]
                 and d["currency"] == pay["currency"]
                 and d["occurred_on"] <= pay["occurred_on"]]
        out.append({"id": pay["id"], "user_id": pay["user_id"],
                    "debt_id": cands[0]["id"] if len(cands) == 1 else None,
                    "options": len(cands)})
    return out


def apply(candidates: list[dict]) -> int:
    chosen = [c for c in candidates if c["debt_id"]]
    if not chosen:
        print("Bog'lanadigan to'lov yo'q.")
        return 0
    path = write_backup(NAME, {
        "migration": NAME,
        "rows": [{"id": c["id"], "user_id": c["user_id"]} for c in chosen],
    })
    print(f"Zaxira (qaytarish uchun): {path}")
    with db.get_conn() as conn:
        for c in chosen:
            conn.execute(
                "UPDATE transactions SET repays_id = ? "
                "WHERE id = ? AND user_id = ? AND repays_id IS NULL",
                (c["debt_id"], c["id"], c["user_id"]))
    print(f"Bog'landi: {len(chosen)} ta to'lov.")
    return len(chosen)


def rollback(path: str) -> None:
    payload = read_backup(path, NAME)
    with db.get_conn() as conn:
        for r in payload["rows"]:
            conn.execute("UPDATE transactions SET repays_id = NULL "
                         "WHERE id = ? AND user_id = ?", (r["id"], r["user_id"]))
    print(f"Qaytarildi: {len(payload['rows'])} ta to'lov bog'lanmagan holatga.")


def main() -> None:
    args = parser(__doc__.splitlines()[0]).parse_args()
    db.init()
    if args.rollback:
        rollback(args.rollback)
        return
    found = find_candidates()
    banner(not args.apply)
    sure = [c for c in found if c["debt_id"]]
    print(f"Ismsiz to'lovlar: {len(found)} (bog'lanadi: {len(sure)}, "
          f"noaniq yoki qarzsiz: {len(found) - len(sure)})")
    for c in found:
        target = (f"-> qarz #{c['debt_id']}" if c["debt_id"]
                  else f"?  ({c['options']} ta nomzod — tegilmaydi)")
        print(f"  to'lov #{c['id']} {target}")
    if args.apply:
        apply(found)
    elif sure:
        print("\nYozish uchun: --apply")


if __name__ == "__main__":
    main()
