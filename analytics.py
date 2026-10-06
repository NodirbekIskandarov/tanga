"""/statistika uchun hisob-kitob (5-bosqich).

Faqat asosiy bazadan o'qiydi: `users`, `entry_counts` (kunlik yozuvlar
SONI), `events` va `subscription_requests`. Summa, kategoriya, izoh —
hech qanday moliyaviy ma'lumot ishlatilmaydi.

Voronkaning to'lov qismi `subscription_requests` dan olinadi (tarif
tanlandi = so'rov yaratildi, to'lov cheki = proof_at, faollashdi =
status «tasdiqlandi»): to'lov oqimiga hodisa yozish uchun tegilmadi va
bu jadval o'sha qadamlarni allaqachon aniq saqlaydi — eski
foydalanuvchilar uchun ham.

`start` va `birinchi_yozuv` ham hodisa kutmaydi: start = users.created_at,
birinchi yozuv = entry_counts dagi eng birinchi kun. Shu tufayli voronka
bu kod joriy etilishidan oldingi foydalanuvchilar uchun ham to'g'ri.
`obuna_ochildi` esa faqat hodisadan bor — undan oldingi davrda nol.
"""

from __future__ import annotations

from collections import defaultdict
from datetime import date, datetime, timedelta

import config
import db


def _day(raw: str | None) -> date | None:
    try:
        return date.fromisoformat(str(raw)[:10])
    except (TypeError, ValueError):
        return None


def _users(conn) -> list[dict]:
    rows = conn.execute("SELECT user_id, created_at, last_seen_at FROM users").fetchall()
    return [{"id": r["user_id"], "start": _day(r["created_at"]),
             "seen": _day(r["last_seen_at"])} for r in rows
            if r["user_id"] not in config.OWNER_IDS]


def _entry_days(conn) -> dict[int, list[date]]:
    out: dict[int, list[date]] = defaultdict(list)
    for r in conn.execute("SELECT user_id, day FROM entry_counts WHERE n > 0"):
        d = _day(r["day"])
        if d:
            out[r["user_id"]].append(d)
    return out


def active_counts(users: list[dict], today: date) -> dict:
    def since(days):
        return sum(1 for u in users if u["seen"] and (today - u["seen"]).days < days)
    return {"total": len(users), "d1": since(1), "d7": since(7), "d30": since(30)}


def retention(users: list[dict], entries: dict[int, list[date]], today: date,
              weeks: int = 8) -> list[dict]:
    """Start haftasi bo'yicha: shu haftada boshlaganlardan necha foizi 7 va
    30 kundan KEYIN ham yozuv kiritgan. Vaqti yetmagan guruhda None."""
    by_week: dict[date, list[dict]] = defaultdict(list)
    for u in users:
        if u["start"]:
            monday = u["start"] - timedelta(days=u["start"].weekday())
            by_week[monday].append(u)
    out = []
    for monday in sorted(by_week, reverse=True)[:weeks]:
        group = by_week[monday]
        row = {"week": monday, "n": len(group)}
        for days in (7, 30):
            ready = [u for u in group if (today - u["start"]).days >= days]
            if not ready:
                row[f"d{days}"] = None
                continue
            kept = sum(1 for u in ready
                       if any(d >= u["start"] + timedelta(days=days)
                              for d in entries.get(u["id"], [])))
            row[f"d{days}"] = round(kept / len(ready) * 100)
        out.append(row)
    return out


def funnel(conn, users: list[dict], entries: dict[int, list[date]],
           since: date | None = None) -> list[tuple[str, int]]:
    """Voronka. `since` — faqat shu kundan keyin boshlaganlar (None — hamma)."""
    group = [u for u in users if u["start"] and (since is None or u["start"] >= since)]
    ids = {u["id"] for u in group}
    first = [u for u in group if entries.get(u["id"])]
    week = [u for u in group
            if any(d >= u["start"] + timedelta(days=7) for d in entries.get(u["id"], []))]
    opened = {r["user_id"] for r in conn.execute(
        "SELECT DISTINCT user_id FROM events WHERE name = 'obuna_ochildi'")}
    reqs = conn.execute(
        "SELECT user_id, proof_at, status FROM subscription_requests").fetchall()
    chose = {r["user_id"] for r in reqs}
    proof = {r["user_id"] for r in reqs if r["proof_at"]}
    paid = {r["user_id"] for r in reqs if r["status"] == "tasdiqlandi"}
    return [
        ("start", len(group)),
        ("birinchi yozuv", len(first)),
        ("7-kundan keyin ham faol", len(week)),
        ("obuna sahifasi ochildi", len(ids & opened)),
        ("tarif tanlandi", len(ids & chose)),
        ("to'lov cheki yuborildi", len(ids & proof)),
        ("obuna faollashdi", len(ids & paid)),
    ]


def paywalls(conn, since: date) -> list[dict]:
    """Qaysi paywall necha marta va necha odamga ko'rsatildi, va qaysi biri
    obunaga olib keldi.

    Obuna shu odamning tasdiqlangan so'rovidan OLDINGI eng oxirgi paywall'ga
    yoziladi (so'rov kuni bilan solishtiriladi).
    """
    shown: dict[str, dict] = defaultdict(lambda: {"times": 0, "users": set(), "paid": 0})
    events = conn.execute(
        "SELECT user_id, detail, day, id FROM events WHERE name = 'paywall_korsatildi' "
        "AND day >= ? ORDER BY id", (since.isoformat(),)).fetchall()
    per_user: dict[int, list] = defaultdict(list)
    for e in events:
        feature = e["detail"].removeprefix("app_")   # Mini App va bot birga
        shown[feature]["times"] += 1
        shown[feature]["users"].add(e["user_id"])
        per_user[e["user_id"]].append((e["day"], feature))

    for r in conn.execute(
            "SELECT user_id, created_at FROM subscription_requests "
            "WHERE status = 'tasdiqlandi'").fetchall():
        req_day = str(r["created_at"])[:10]
        before = [f for d, f in per_user.get(r["user_id"], []) if d <= req_day]
        if before:
            shown[before[-1]]["paid"] += 1

    return sorted(({"feature": f, "times": v["times"], "users": len(v["users"]),
                    "paid": v["paid"]} for f, v in shown.items()),
                  key=lambda r: (-r["times"], r["feature"]))


def report(today: date | None = None) -> dict:
    today = today or datetime.now(config.TZ).date()
    with db.get_conn() as conn:
        users = _users(conn)
        entries = _entry_days(conn)
        return {
            "active": active_counts(users, today),
            "retention": retention(users, entries, today),
            "funnel_30": funnel(conn, users, entries, today - timedelta(days=30)),
            "funnel_all": funnel(conn, users, entries),
            "paywalls": paywalls(conn, today - timedelta(days=30)),
        }


FEATURE_NAMES = {
    "receipts": "chek (oylik 3 ta)", "qa": "AI savol (kunlik 3 ta)",
    "history": "o'tgan davrlar", "budget": "byudjet", "csv": "CSV",
    "goals": "2-maqsad", "savings_auto": "foiz sozlash",
    "debt_reminders": "qarz eslatmasi",
    "trial_receipts": "chek (sinovdagi 10 ta)",
}


def report_text(data: dict) -> str:
    a = data["active"]
    lines = [
        "📈 <b>Statistika</b>", "",
        f"👥 Foydalanuvchilar: <b>{a['total']}</b>",
        f"Faol: bugun {a['d1']} · 7 kun {a['d7']} · 30 kun {a['d30']}",
        "",
        "<b>Saqlanish</b> (start haftasi bo'yicha, 7 va 30 kundan keyin ham yozganlar):",
    ]
    for r in data["retention"]:
        d7 = "—" if r["d7"] is None else f"{r['d7']}%"
        d30 = "—" if r["d30"] is None else f"{r['d30']}%"
        lines.append(f"<code>{r['week']:%d.%m}</code> · {r['n']} odam · 7k: {d7} · 30k: {d30}")
    if not data["retention"]:
        lines.append("<i>hali ma'lumot yo'q</i>")

    lines += ["", "<b>Voronka</b> (oxirgi 30 kunda boshlaganlar / hammasi):"]
    top30 = data["funnel_30"][0][1] or 1
    for (name, n30), (_, nall) in zip(data["funnel_30"], data["funnel_all"]):
        lines.append(f"• {name}: <b>{n30}</b> ({n30 / top30 * 100:.0f}%) / {nall}")

    lines += ["", "<b>Paywall</b> (30 kun): ko'rsatildi · odam · obunaga olib keldi"]
    for p in data["paywalls"]:
        name = FEATURE_NAMES.get(p["feature"], p["feature"])
        lines.append(f"• {name}: {p['times']} · {p['users']} · <b>{p['paid']}</b>")
    if not data["paywalls"]:
        lines.append("<i>hali ko'rsatilmagan</i>")
    lines += ["", "<i>«obuna sahifasi ochildi» hodisasi shu versiyadan beri yoziladi.</i>"]
    return "\n".join(lines)
