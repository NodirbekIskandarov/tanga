"""Qarz to'lovi bo'lib kirim yoki chiqimga tushib qolgan eski yozuvlarni
qarz turlariga o'tkazadi (1.1).

Masalan «1 mln qarzim uchun to'landi» avval kirim, keyin qo'lda «boshqa
chiqim» bo'lib saqlangan — oylik chiqimning katta qismini egallab
statistikani buzgan. Bu skript izoh va asl matndagi qarz iboralarini
qidirib, har bir nomzod uchun yangi turni TAKLIF qiladi.

Bu evristika — shuning uchun avval ro'yxatni ko'rib chiqing:

    python scripts/migrate_debts.py                    # dry-run: nomzodlar
    python scripts/migrate_debts.py --apply            # hamma aniq nomzodlar
    python scripts/migrate_debts.py --apply --ids 12,40  # faqat tanlanganlar
    python scripts/migrate_debts.py --rollback migration_backups/debts-....json

Turini aniqlab bo'lmagan yozuvlar ro'yxatda «?» bilan ko'rsatiladi va
HECH QACHON avtomatik o'zgartirilmaydi. Chiqarishda summa, sana va
foydalanuvchi ko'rsatilmaydi — faqat yozuv raqami, tur o'zgarishi va
topilgan ibora.
"""

from __future__ import annotations

import re

import _common  # noqa: F401  (yo'l va ish papkasini sozlaydi)
from _common import banner, parser, read_backup, write_backup

import config
import db

NAME = "debts"

# (naqsh, taklif qilinadigan tur). Tartib muhim: aniqroq ibora oldinda.
# Hammasi kichik harflarda, lotin/kirill/rus.
PATTERNS: list[tuple[str, str]] = [
    # Menga qaytarildi — uchinchi shaxs qaytardi.
    (r"qarz\w* qaytardi\b|qaytarib berdi\b|qarzini berdi\b|qarz qaytdi\b"
     r"|қарзини қайтарди|вернул(а)? (мне )?долг|долг вернули", config.KIND_QARZ_QAYTDI),
    # Men qaytardim / kredit to'ladim.
    (r"qarzim\w*|qarzni qaytardim|qarz qaytimi|kredit\w*|nasiya\w*"
     r"|қарзим\w*|кредит\w*|вернул долг|отдал долг|погасил", config.KIND_QARZ_QAYTARDIM),
    # Qarz olish va berish.
    (r"qarz(ga)? oldim|qarzga olindi|қарз олдим|взял в долг|занял", config.KIND_QARZ_OLDIM),
    (r"qarz(ga)? berdim|қарз бердим|дал в долг|одолжил", config.KIND_QARZ_BERDIM),
]
# Qarzga aloqador, lekin yo'nalishi noaniq — faqat ko'rsatiladi.
LOOSE = r"qarz|қарз|долг"


def classify(text: str) -> tuple[str | None, str | None]:
    """(taklif qilingan tur yoki None, topilgan ibora yoki None)."""
    low = (text or "").casefold()
    for pattern, kind in PATTERNS:
        m = re.search(pattern, low)
        if m:
            return kind, m.group(0)
    m = re.search(LOOSE, low)
    return (None, m.group(0)) if m else (None, None)


def find_candidates() -> list[dict]:
    """Chek mahsulotlari tekshirilmaydi — ular qarz bo'lishi mumkin emas."""
    with db.get_conn() as conn:
        rows = conn.execute(
            """SELECT id, user_id, kind, category, person, note, raw_text
               FROM transactions
               WHERE kind IN (?, ?) AND receipt_id IS NULL""",
            (config.KIND_CHIQIM, config.KIND_KIRIM)).fetchall()
    out = []
    for r in rows:
        kind, match = classify(f"{r['note'] or ''} {r['raw_text'] or ''}")
        if match:
            out.append({"id": r["id"], "user_id": r["user_id"], "kind": r["kind"],
                        "category": r["category"], "person": r["person"],
                        "new_kind": kind, "match": match})
    return out


def apply(candidates: list[dict], ids: set[int] | None) -> int:
    chosen = [c for c in candidates if c["new_kind"]
              and (ids is None or c["id"] in ids)]
    if not chosen:
        print("O'zgartiriladigan yozuv yo'q.")
        return 0
    path = write_backup(NAME, {
        "migration": NAME,
        "rows": [{"id": c["id"], "user_id": c["user_id"], "kind": c["kind"],
                  "category": c["category"]} for c in chosen],
    })
    print(f"Zaxira (qaytarish uchun): {path}")
    with db.get_conn() as conn:
        for c in chosen:
            conn.execute(
                "UPDATE transactions SET kind = ?, category = ? "
                "WHERE id = ? AND user_id = ? AND kind = ?",
                (c["new_kind"], config.fallback_category(c["new_kind"]),
                 c["id"], c["user_id"], c["kind"]))
    print(f"O'zgartirildi: {len(chosen)} ta yozuv.")
    return len(chosen)


def rollback(path: str) -> None:
    payload = read_backup(path, NAME)
    with db.get_conn() as conn:
        for r in payload["rows"]:
            conn.execute(
                "UPDATE transactions SET kind = ?, category = ? "
                "WHERE id = ? AND user_id = ?",
                (r["kind"], r["category"], r["id"], r["user_id"]))
    print(f"Qaytarildi: {len(payload['rows'])} ta yozuv avvalgi turiga.")


def main() -> None:
    p = parser(__doc__.splitlines()[0])
    p.add_argument("--ids", help="faqat shu yozuvlar: 12,40,41")
    args = p.parse_args()
    db.init()
    if args.rollback:
        rollback(args.rollback)
        return

    ids = {int(x) for x in args.ids.split(",") if x.strip()} if args.ids else None
    found = find_candidates()
    banner(not args.apply)
    sure = [c for c in found if c["new_kind"]]
    print(f"Nomzodlar: {len(found)} (aniq: {len(sure)}, "
          f"noaniq: {len(found) - len(sure)})")
    for c in found:
        target = c["new_kind"] or "?  (qo'lda hal qilinadi)"
        print(f"  #{c['id']}: {c['kind']} -> {target}   «{c['match']}»")

    if args.apply:
        apply(found, ids)
    elif sure:
        print("\nYozish uchun: --apply  (yoki tanlab: --apply --ids 12,40)")


if __name__ == "__main__":
    main()
