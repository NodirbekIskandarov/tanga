"""«Boshqa chiqim» ga qanday nomlar tushayotganini ko'rsatadi (1.2).

FAQAT O'QIYDI — bazaga hech narsa yozmaydi.

Maxfiylik: natijada foydalanuvchi, summa va sana CHIQMAYDI. Faqat so'z
o'zagi, u nechta foydalanuvchida va necha marta uchragani ko'rsatiladi.
Kamida `--min-users` (standart 3) ta har xil foydalanuvchida uchramagan
so'z umuman chiqarilmaydi — bitta odamning o'ziga xos xaridi shu yerda
ko'rinib qolmasin.

Natija promptni yaxshilash uchun: ro'yxatdagi so'zlar qaysi kategoriyaga
tegishli ekanini promptga misol qilib qo'shish kerak.

    python scripts/analyze_other.py
    python scripts/analyze_other.py --min-users 5 --limit 100
"""

from __future__ import annotations

import argparse
from collections import defaultdict

import _common  # noqa: F401  (yo'l va ish papkasini sozlaydi)

import db
import learning


def collect(min_users: int) -> list[tuple[str, int, int]]:
    """[(so'z o'zagi, foydalanuvchilar soni, uchrashlar soni)]"""
    users: dict[str, set[int]] = defaultdict(set)
    hits: dict[str, int] = defaultdict(int)
    with db.get_conn() as conn:
        cur = conn.execute(
            "SELECT user_id, note FROM transactions "
            "WHERE kind = 'chiqim' AND category = 'boshqa chiqim'")
        for row in cur:
            for word in learning.keywords_of(row["note"]):
                users[word].add(row["user_id"])
                hits[word] += 1
    result = [(w, len(u), hits[w]) for w, u in users.items() if len(u) >= min_users]
    return sorted(result, key=lambda r: (-r[1], -r[2], r[0]))


def main() -> None:
    p = argparse.ArgumentParser(description=__doc__.splitlines()[0])
    p.add_argument("--min-users", type=int, default=3)
    p.add_argument("--limit", type=int, default=60)
    args = p.parse_args()
    if args.min_users < 3:
        raise SystemExit("--min-users 3 dan kam bo'lmasligi kerak (maxfiylik).")

    rows = collect(args.min_users)
    print(f"«boshqa chiqim» dagi so'zlar (kamida {args.min_users} ta "
          f"foydalanuvchida): {len(rows)} ta")
    print(f"{'so`z':<24}{'odam':>6}{'marta':>8}")
    for word, n_users, n_hits in rows[: args.limit]:
        print(f"{word:<24}{n_users:>6}{n_hits:>8}")


if __name__ == "__main__":
    main()
