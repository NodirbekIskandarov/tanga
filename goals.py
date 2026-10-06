"""Maqsadlar (3.1) va ularning bashorati.

Bir odamda bir nechta maqsad bo'lishi mumkin: «Uy uchun boshlang'ich
to'lov — 300 mln», «Mashina — 120 mln». Jamg'arma yozuvi (`transactions`,
tur «jamgarma» / «jamgarma_yechdim») `goal_id` orqali maqsadga bog'lanadi.

Asosiy maqsad (`savings_profile.primary_goal_id`) — maqsadga bog'lanmagan
jamg'arma va «avval o'zingizga to'lang» o'tkazmasi shunga tushadi. Shu
tufayli bitta maqsadli odamda hamma narsa avvalgidek: maqsad progressi =
butun jamg'arma qoldig'i.

Eski yagona maqsad (`savings_profile.goal`) birinchi murojaatda bu yerga
NUSXALANADI (`_import_legacy`) — asl qiymat o'zgarmaydi, qaytarish uchun
yangi qatorni o'chirish kifoya.

Bashorat: oxirgi 90 kundagi sof jamg'arma sur'ati (oyiga) bo'yicha
«shu sur'atda maqsadga qachon yetasiz». Muddat qo'yilgan bo'lsa —
«muddatga yetish uchun oyiga qancha kerak».
"""

from __future__ import annotations

import re
from datetime import date, datetime, timedelta

import config
import db

MONTH_DAYS = 30.44
FORECAST_WINDOW_DAYS = 90
# Bundan qisqa tarixdan sur'at chiqarilmaydi — bitta katta o'tkazma
# «oyiga 50 mln» degan yolg'on bashorat bermasin.
MIN_HISTORY_DAYS = 14

UZ_MONTHS = ["yanvar", "fevral", "mart", "aprel", "may", "iyun", "iyul",
             "avgust", "sentabr", "oktabr", "noyabr", "dekabr"]
# Qidirish uchun qo'shimcha yozilishlar (ruscha va kirill).
_MONTH_ALIASES = {
    **{m: i + 1 for i, m in enumerate(UZ_MONTHS)},
    "sentyabr": 9, "oktyabr": 10,
    "январ": 1, "феврал": 2, "март": 3, "апрел": 4, "май": 5, "мая": 5,
    "июн": 6, "июл": 7, "август": 8, "сентябр": 9, "октябр": 10,
    "ноябр": 11, "декабр": 12,
}


def today() -> date:
    return datetime.now(config.TZ).date()


# ------------------------------------------------------------------ baza --

def _import_legacy(conn, user_id: int) -> None:
    """Eski yagona maqsadni bir marta nusxalaydi (asl qiymat qoladi)."""
    prof = conn.execute(
        "SELECT goal, goal_note, goal_reached_at, goals_imported "
        "FROM savings_profile WHERE user_id = ?", (user_id,)).fetchone()
    if not prof or prof["goals_imported"]:
        return
    if float(prof["goal"] or 0) > 0:
        cur = conn.execute(
            "INSERT INTO goals (user_id, name, amount, reached_at) VALUES (?, ?, ?, ?)",
            (user_id, (prof["goal_note"] or "").strip() or "Jamg'arma maqsadi",
             float(prof["goal"]), prof["goal_reached_at"]))
        conn.execute("UPDATE savings_profile SET primary_goal_id = ? WHERE user_id = ?",
                     (cur.lastrowid, user_id))
    conn.execute("UPDATE savings_profile SET goals_imported = 1 WHERE user_id = ?",
                 (user_id,))


def list_goals(user_id: int) -> list[dict]:
    """Faol maqsadlar, asosiysi birinchi; har biri progressi bilan."""
    with db.get_conn() as conn:
        _import_legacy(conn, user_id)
        rows = [dict(r) for r in conn.execute(
            "SELECT * FROM goals WHERE user_id = ? AND archived = 0 ORDER BY id",
            (user_id,)).fetchall()]
        primary = _primary_id(conn, user_id, rows)
        for g in rows:
            g["primary"] = g["id"] == primary
            g["saved"] = _saved(conn, user_id, g["id"], g["primary"])
            g["left"] = round(max(0.0, g["amount"] - g["saved"]), 2)
            g["percent"] = (min(100, round(g["saved"] / g["amount"] * 100))
                            if g["amount"] > 0 else 0)
    rows.sort(key=lambda g: not g["primary"])
    return rows


def _primary_id(conn, user_id: int, rows: list[dict]) -> int | None:
    if not rows:
        return None
    row = conn.execute("SELECT primary_goal_id FROM savings_profile WHERE user_id = ?",
                       (user_id,)).fetchone()
    pid = row["primary_goal_id"] if row else None
    ids = {g["id"] for g in rows}
    return pid if pid in ids else rows[0]["id"]


def _saved(conn, user_id: int, goal_id: int, primary: bool) -> float:
    """Maqsadga yig'ilgan sof pul. Asosiy maqsadga bog'lanmagan jamg'arma ham kiradi."""
    where = "goal_id = ?" + (" OR goal_id IS NULL" if primary else "")
    row = conn.execute(
        f"""SELECT COALESCE(SUM(CASE WHEN kind = ? THEN COALESCE(amount_base, amount)
                                     ELSE -COALESCE(amount_base, amount) END), 0)
            FROM transactions
            WHERE user_id = ? AND kind IN (?, ?) AND ({where})""",
        (config.KIND_JAMGARMA, user_id, config.KIND_JAMGARMA,
         config.KIND_JAMGARMA_YECHDIM, goal_id)).fetchone()
    return round(float(row[0] or 0), 2)


def primary(user_id: int) -> dict | None:
    goals = list_goals(user_id)
    return goals[0] if goals else None


def get(user_id: int, goal_id: int) -> dict | None:
    return next((g for g in list_goals(user_id) if g["id"] == goal_id), None)


def create(user_id: int, name: str, amount: float, deadline: date | None) -> int:
    with db.get_conn() as conn:
        _import_legacy(conn, user_id)
        cur = conn.execute(
            "INSERT INTO goals (user_id, name, amount, deadline) VALUES (?, ?, ?, ?)",
            (user_id, name[:60], float(amount),
             deadline.isoformat() if deadline else None))
        goal_id = int(cur.lastrowid)
        # Birinchi maqsad — avtomatik asosiy.
        has_primary = conn.execute(
            "SELECT primary_goal_id FROM savings_profile WHERE user_id = ?",
            (user_id,)).fetchone()
        if not has_primary or not has_primary["primary_goal_id"]:
            db._upsert_profile(conn, user_id, primary_goal_id=goal_id, goals_imported=1)
    db.log_event(user_id, "maqsad_yaratildi")
    return goal_id


def set_primary(user_id: int, goal_id: int) -> bool:
    if not get(user_id, goal_id):
        return False
    with db.get_conn() as conn:
        db._upsert_profile(conn, user_id, primary_goal_id=goal_id)
    return True


def archive(user_id: int, goal_id: int) -> bool:
    """Maqsadni yopadi. Unga bog'langan jamg'arma o'chmaydi — bog'lanish
    uziladi va pul asosiy maqsadga (yoki umumiy jamg'armaga) qaytadi."""
    with db.get_conn() as conn:
        cur = conn.execute("UPDATE goals SET archived = 1 WHERE id = ? AND user_id = ?",
                           (goal_id, user_id))
        conn.execute("UPDATE transactions SET goal_id = NULL "
                     "WHERE user_id = ? AND goal_id = ?", (user_id, goal_id))
        conn.execute("UPDATE savings_profile SET primary_goal_id = NULL "
                     "WHERE user_id = ? AND primary_goal_id = ?", (user_id, goal_id))
        return cur.rowcount > 0


def mark_reached(user_id: int, goal_id: int) -> None:
    with db.get_conn() as conn:
        conn.execute("UPDATE goals SET reached_at = ? WHERE id = ? AND user_id = ?",
                     (datetime.now(config.TZ).isoformat(timespec="seconds"),
                      goal_id, user_id))


def match(user_id: int, name: str | None) -> int | None:
    """Jamg'arma yozuvidagi «maqsadga»/«uy uchun» ishorasi qaysi maqsad.

    Nom aytilmagan yoki topilmasa — asosiy maqsad (None emas, aniq id),
    maqsad umuman bo'lmasa None.
    """
    goals = list_goals(user_id)
    if not goals:
        return None
    words = {w for w in re.findall(r"[^\W\d_]{3,}", (name or "").casefold())}
    if words:
        for g in goals:
            gw = set(re.findall(r"[^\W\d_]{3,}", g["name"].casefold()))
            if any(a.startswith(b) or b.startswith(a) for a in words for b in gw):
                return g["id"]
    return goals[0]["id"]


# -------------------------------------------------------------- bashorat --

def monthly_pace(user_id: int, goal: dict) -> float | None:
    """Oxirgi 90 kundagi sof jamg'arma sur'ati, oyiga. Tarix qisqa bo'lsa None."""
    end = today()
    start = end - timedelta(days=FORECAST_WINDOW_DAYS - 1)
    where = "goal_id = ?" + (" OR goal_id IS NULL" if goal["primary"] else "")
    with db.get_conn() as conn:
        row = conn.execute(
            f"""SELECT MIN(occurred_on) AS first,
                       COALESCE(SUM(CASE WHEN kind = ? THEN COALESCE(amount_base, amount)
                                         ELSE -COALESCE(amount_base, amount) END), 0) AS net
                FROM transactions
                WHERE user_id = ? AND kind IN (?, ?) AND ({where})
                  AND occurred_on BETWEEN ? AND ?""",
            (config.KIND_JAMGARMA, user_id, config.KIND_JAMGARMA,
             config.KIND_JAMGARMA_YECHDIM, goal["id"],
             start.isoformat(), end.isoformat())).fetchone()
    if not row["first"]:
        return None
    first = max(start, date.fromisoformat(row["first"]))
    days = (end - first).days + 1
    if days < MIN_HISTORY_DAYS:
        return None
    return float(row["net"]) / days * MONTH_DAYS


def forecast(user_id: int, goal: dict) -> dict:
    """{"pace": oyiga, "eta": date|None, "need_monthly": float|None}"""
    pace = monthly_pace(user_id, goal)
    eta = None
    if pace and pace > 0 and goal["left"] > 0:
        eta = today() + timedelta(days=goal["left"] / pace * MONTH_DAYS)
    need = None
    if goal.get("deadline") and goal["left"] > 0:
        deadline = date.fromisoformat(goal["deadline"])
        months = max(1.0, (deadline - today()).days / MONTH_DAYS)
        need = goal["left"] / months
    return {"pace": pace, "eta": eta, "need_monthly": need}


def month_year(d: date, lang: str | None = None) -> str:
    """2028-yil mart / март 2028 (til berilmasa — joriy foydalanuvchi tili)."""
    import i18n
    import reports
    lang = reports.resolve_lang(lang)
    if i18n.normalize(lang) == "ru":
        return f"{i18n.month_name(lang, d.month, nominative=True)} {d.year}"
    return i18n.pick(lang, f"{d.year}-yil {UZ_MONTHS[d.month - 1]}")


# ---------------------------------------------------------------- matn --

_DEADLINE_PATTERNS = [
    # 2028-03, 2028-03-15
    (re.compile(r"\b(20\d{2})-(\d{1,2})(?:-(\d{1,2}))?\b"), "ymd"),
    # 15.03.2028, 03.2028
    (re.compile(r"\b(?:(\d{1,2})\.)?(\d{1,2})\.(20\d{2})\b"), "dmy"),
    # 2028-yil mart(gacha), 2028 mart
    (re.compile(r"\b(20\d{2})(?:-?\s*yil(?:i|ning)?)?\s+([^\W\d_]+)", re.I), "y_month"),
    # mart 2028
    (re.compile(r"\b([^\W\d_]+)\s+(20\d{2})\b", re.I), "month_y"),
]


def _month_of(word: str) -> int | None:
    w = word.casefold()
    return next((n for name, n in _MONTH_ALIASES.items() if w.startswith(name)), None)


def _end_of_month(year: int, month: int) -> date:
    first_next = date(year + (month == 12), month % 12 + 1, 1)
    return first_next - timedelta(days=1)


def parse_deadline(text: str) -> tuple[date | None, str]:
    """Matndan muddatni ajratadi. Qaytaradi: (sana yoki None, qolgan matn)."""
    for pattern, kind in _DEADLINE_PATTERNS:
        for m in pattern.finditer(text):
            try:
                if kind == "ymd":
                    y, mo, d = int(m.group(1)), int(m.group(2)), m.group(3)
                    day = date(y, mo, int(d)) if d else _end_of_month(y, mo)
                elif kind == "dmy":
                    d, mo, y = m.group(1), int(m.group(2)), int(m.group(3))
                    day = date(y, mo, int(d)) if d else _end_of_month(y, mo)
                elif kind == "y_month":
                    mo = _month_of(m.group(2))
                    if not mo:
                        continue
                    day = _end_of_month(int(m.group(1)), mo)
                else:
                    mo = _month_of(m.group(1))
                    if not mo:
                        continue
                    day = _end_of_month(int(m.group(2)), mo)
            except ValueError:
                continue
            rest = (text[:m.start()] + " " + text[m.end():]).strip()
            return day, rest
    return None, text


def parse_goal_text(text: str, parse_amount) -> dict | None:
    """«Uy uchun boshlang'ich to'lov — 300 mln, 2028-yil mart» ->
    {"name", "amount", "deadline"}. Summa bo'lmasa None.

    `parse_amount` — bot._parse_amount_uz (AI'siz, tekin).
    """
    deadline, rest = parse_deadline(text or "")
    amount = parse_amount(rest)
    if not amount or amount <= 0:
        return None
    m = re.search(r"\d", rest)
    name_part = rest[:m.start()] if m else rest
    if not name_part.strip(" —-:,."):
        # «300 mln uy uchun» — nom summadan keyin.
        tail = re.sub(r"^[\d\s.,]+(?:mln|million|mlrd|ming|k|tys|тыс|млн)?\.?", "",
                      rest.strip(), flags=re.I)
        name_part = tail
    name = re.sub(r"\s+", " ", name_part).strip(" —-:,.") or "Maqsad"
    return {"name": name[:60], "amount": amount, "deadline": deadline}
