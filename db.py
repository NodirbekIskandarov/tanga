"""SQLite bilan ishlash qatlami. Bitta foydalanuvchi uchun mo'ljallangan, lekin
user_id bo'yicha ajratilgan — kerak bo'lsa bir nechta odam ishlatishi mumkin."""

from __future__ import annotations

import math
import sqlite3
from contextlib import contextmanager
from datetime import date, datetime, timedelta
from typing import Iterable

import config

# Shaxsiy baza: FAQAT foydalanuvchining o'z moliyasi.
#
# Bu jadvallar ataylab asosiy bazada emas. Asosiy bazani admin panel
# ham ochadi (unga obuna, to'lov, AI sarfi kerak) — yozuvlar o'sha
# yerda bo'lsa panel ularni o'qiy olardi. Alohida fayl va alohida
# kalit buni imkonsiz qiladi. Izoh config.PRIVATE_DB_PATH yonida.
#
# `shaxsiy.` prefiksi ATTACH qilingan bazani bildiradi. Qolgan
# so'rovlar jadval nomini prefikssiz yozadi va SQLite uni o'zi shu
# yerdan topadi: nom asosiy bazada yo'q, keyingi o'ringa qaraydi.
PRIVATE_SCHEMA = """
CREATE TABLE IF NOT EXISTS shaxsiy.transactions (
    id           INTEGER PRIMARY KEY AUTOINCREMENT,
    user_id      INTEGER NOT NULL,
    kind         TEXT    NOT NULL,
    amount       REAL    NOT NULL,
    category     TEXT    NOT NULL,
    note         TEXT    NOT NULL DEFAULT '',
    person       TEXT,
    occurred_on  TEXT    NOT NULL,
    raw_text     TEXT    NOT NULL DEFAULT '',
    settled      INTEGER NOT NULL DEFAULT 0,
    receipt_id   TEXT,
    currency     TEXT    NOT NULL DEFAULT 'som',
    created_at   TEXT    NOT NULL DEFAULT (datetime('now')),
    rate         REAL    NOT NULL DEFAULT 1,
    amount_base  REAL
);

CREATE INDEX IF NOT EXISTS shaxsiy.idx_tx_user_date
    ON transactions(user_id, occurred_on);
CREATE INDEX IF NOT EXISTS shaxsiy.idx_tx_user_kind
    ON transactions(user_id, kind);
CREATE INDEX IF NOT EXISTS shaxsiy.idx_tx_receipt
    ON transactions(user_id, receipt_id);

-- Chek sarlavhasi. Mahsulotlar hamon `transactions` da alohida qator
-- bo'lib turadi (kategoriya tahlili, byudjet va AI savollari mahsulot
-- darajasida ishlaydi) — sarlavha ularni `receipt_id` orqali bitta
-- chekka birlashtiradi: do'kon nomi, chekdagi jami va chegirma.
--
-- Chek summasi bu yerda SAQLANMAYDI, har safar mahsulotlardan
-- hisoblanadi: Mini App'da bitta mahsulot o'chirilsa ham sarlavha
-- eskirib qolmaydi. `printed_total` — chekda yozilgan jami, faqat
-- ma'lumot uchun.
CREATE TABLE IF NOT EXISTS shaxsiy.receipts (
    user_id       INTEGER NOT NULL,
    receipt_id    TEXT    NOT NULL,
    shop          TEXT    NOT NULL DEFAULT '',
    occurred_on   TEXT    NOT NULL,
    currency      TEXT    NOT NULL DEFAULT 'som',
    printed_total REAL,
    discount      REAL,
    created_at    TEXT    NOT NULL DEFAULT (datetime('now')),
    PRIMARY KEY (user_id, receipt_id)
);

-- Kategoriya bo'yicha oylik byudjet. Bu ham shaxsiy moliya: odam nimaga
-- qancha ajratgani uning daromadi haqida ham gapiradi.
CREATE TABLE IF NOT EXISTS shaxsiy.budgets (
    user_id   INTEGER NOT NULL,
    category  TEXT    NOT NULL,
    amount    REAL    NOT NULL,
    currency  TEXT    NOT NULL DEFAULT 'som',
    notified  TEXT    NOT NULL DEFAULT '',
    PRIMARY KEY (user_id, category, currency)
);

-- Jamg'arma odati. `card_state` — odamda jamg'arma uchun ALOHIDA bank
-- kartasi bormi:
--   soralmagan — hali so'ralmagan
--   yoq        — yo'q deb javob bergan (vaqti-vaqti bilan eslatiladi)
--   bor        — ochgan
--
-- Nima uchun alohida karta muhim: bitta hisobda turgan pul "bor" bo'lib
-- ko'rinadi va oxirigacha sarflanadi. Kitobning 4-qonuni ("pulni
-- yo'qotishdan asra") amalda aynan shu — jamg'armani qo'l yetmaydigan
-- joyga qo'yish.
--
-- Bu jadval ATAYLAB shaxsiy bazada: odamning bank tuzilishi ham uning
-- moliyasi, admin panel buni bilishi shart emas.
CREATE TABLE IF NOT EXISTS shaxsiy.savings_profile (
    user_id       INTEGER PRIMARY KEY,
    card_state    TEXT NOT NULL DEFAULT 'soralmagan',
    asked_at      TEXT,
    answered_at   TEXT,
    -- Oxirgi eslatma: bir odamga tez-tez aytilmasin.
    nudged_at     TEXT,
    -- Oy oxiridagi eslatma qaysi oy uchun yuborilgani: "YYYY-MM".
    -- Bir oyda ikki marta yuborilib qolmasin.
    reminded_month TEXT NOT NULL DEFAULT '',
    -- Foydalanuvchining O'Z jamg'arma foizi (0.10 = 10 %).
    -- 0 bo'lsa umumiy standart (config.SAVINGS_RATE) ishlatiladi:
    -- shu tufayli standart o'zgarsa, uni ataylab o'zgartirmaganlarga
    -- yangi qiymat o'zi tegadi.
    savings_rate  REAL NOT NULL DEFAULT 0,
    -- Jamg'arma maqsadi (asosiy valyutada). 0 — maqsad qo'yilmagan.
    goal          REAL NOT NULL DEFAULT 0,
    goal_note     TEXT NOT NULL DEFAULT '',
    -- Maqsadga yetilgani bir marta tabriklanadi.
    goal_reached_at TEXT
);
"""

CARD_SORALMAGAN = "soralmagan"
CARD_YOQ = "yoq"
CARD_BOR = "bor"

# Shaxsiy bazadagi jadvallarga keyin qo'shilgan ustunlar:
# (jadval, ustun, SQL). Sxemadagi ta'rif bilan MOS bo'lishi shart.
PRIVATE_TABLE_MIGRATIONS = [
    ("savings_profile", "savings_rate",
     "ALTER TABLE shaxsiy.savings_profile ADD COLUMN savings_rate REAL NOT NULL DEFAULT 0"),
    ("savings_profile", "goal",
     "ALTER TABLE shaxsiy.savings_profile ADD COLUMN goal REAL NOT NULL DEFAULT 0"),
    ("savings_profile", "goal_note",
     "ALTER TABLE shaxsiy.savings_profile ADD COLUMN goal_note TEXT NOT NULL DEFAULT ''"),
    ("savings_profile", "goal_reached_at",
     "ALTER TABLE shaxsiy.savings_profile ADD COLUMN goal_reached_at TEXT"),
]

SCHEMA = """
-- Foydalanuvchilar: kirish huquqi, bepul sinov va obuna muddati.
CREATE TABLE IF NOT EXISTS users (
    user_id          INTEGER PRIMARY KEY,
    first_name       TEXT    NOT NULL DEFAULT '',
    username         TEXT,
    created_at       TEXT    NOT NULL DEFAULT (datetime('now')),
    trial_ends_at    TEXT,
    subscribed_until TEXT,
    blocked          INTEGER NOT NULL DEFAULT 0,
    last_seen_at     TEXT
);

-- Har bir AI chaqiruvining haqiqiy token sarfi va narxi.
-- Kunlik limit ham shu jadvaldagi qatorlar soni bo'yicha hisoblanadi.
CREATE TABLE IF NOT EXISTS usage_log (
    id            INTEGER PRIMARY KEY AUTOINCREMENT,
    user_id       INTEGER NOT NULL,
    day           TEXT    NOT NULL,
    operation     TEXT    NOT NULL,
    model         TEXT    NOT NULL DEFAULT '',
    input_tokens  INTEGER NOT NULL DEFAULT 0,
    output_tokens INTEGER NOT NULL DEFAULT 0,
    cache_read    INTEGER NOT NULL DEFAULT 0,
    cache_write   INTEGER NOT NULL DEFAULT 0,
    cost_usd      REAL    NOT NULL DEFAULT 0,
    created_at    TEXT    NOT NULL DEFAULT (datetime('now'))
);

CREATE INDEX IF NOT EXISTS idx_usage_user_day ON usage_log(user_id, day);
CREATE INDEX IF NOT EXISTS idx_usage_day ON usage_log(day);

-- Obuna so'rovlari. Bot bu yerga yozadi, admin web panel o'qib hal qiladi.
-- Sxema admin panel bilan bir xil bo'lishi shart (tanga-admin/store.py).
CREATE TABLE IF NOT EXISTS subscription_requests (
    id          INTEGER PRIMARY KEY AUTOINCREMENT,
    user_id     INTEGER NOT NULL,
    plan_code   TEXT    NOT NULL,
    price       INTEGER NOT NULL DEFAULT 0,
    status      TEXT    NOT NULL DEFAULT 'kutilmoqda',
    created_at  TEXT    NOT NULL DEFAULT (datetime('now')),
    decided_at  TEXT,
    decided_by  TEXT    NOT NULL DEFAULT '',
    note        TEXT    NOT NULL DEFAULT ''
);
CREATE INDEX IF NOT EXISTS idx_req_status ON subscription_requests(status, created_at DESC);

-- Valyuta kurslari. Har kun uchun bir marta saqlanadi, shunda o'tgan
-- oylardagi hisobot kurs o'zgarganda ham o'zgarmaydi.
CREATE TABLE IF NOT EXISTS rates (
    day      TEXT NOT NULL,
    currency TEXT NOT NULL,
    rate     REAL NOT NULL,
    source   TEXT NOT NULL DEFAULT '',
    PRIMARY KEY (day, currency)
);

-- Kunlik yozuvlar SONI. Admin panel uchun yagona ko'prik.
--
-- Panelга «bu odam botdan foydalanyaptimi» degan savolga javob kerak:
-- obunani uzaytirish, sinov berish va limitni hal qilish shunga
-- tayanadi. Sonning o'zi moliyaviy ma'lumot emas — «340 ta yozuv»
-- odamning nimaga pul sarflaganini aytmaydi. Summa, kategoriya va
-- izoh esa shu yerga UMUMAN chiqmaydi: ular shaxsiy bazada qoladi.
CREATE TABLE IF NOT EXISTS entry_counts (
    user_id INTEGER NOT NULL,
    day     TEXT    NOT NULL,
    n       INTEGER NOT NULL DEFAULT 0,
    PRIMARY KEY (user_id, day)
);
CREATE INDEX IF NOT EXISTS idx_entry_day ON entry_counts(day);

-- Admin panel foydalanuvchini o'chirganda uning shaxsiy yozuvlarini
-- O'ZI o'chira olmaydi — shaxsiy bazaning kaliti unda yo'q. Shuning
-- uchun u shu yerga so'rov qoldiradi, bot esa uni bajaradi.
CREATE TABLE IF NOT EXISTS private_erase_queue (
    user_id  INTEGER PRIMARY KEY,
    asked_at TEXT NOT NULL DEFAULT (datetime('now')),
    done_at  TEXT
);
"""

# Eski bazalarga keyin qo'shilgan ustunlar. CREATE TABLE IF NOT EXISTS mavjud
# jadvalni o'zgartirmaydi, shuning uchun qo'lda tekshiramiz.
MIGRATIONS = [
    ("receipt_id", "ALTER TABLE transactions ADD COLUMN receipt_id TEXT"),
    ("currency", "ALTER TABLE transactions ADD COLUMN currency TEXT NOT NULL DEFAULT 'som'"),
]

# Boshqa jadvallarga keyin qo'shilgan ustunlar: (jadval, ustun, SQL)
TABLE_MIGRATIONS = [
    ("subscription_requests", "proof_file_id",
     "ALTER TABLE subscription_requests ADD COLUMN proof_file_id TEXT"),
    ("subscription_requests", "proof_at",
     "ALTER TABLE subscription_requests ADD COLUMN proof_at TEXT"),
    # Chek rasm ham, PDF ham bo'lishi mumkin — admin panel qaysi
    # ko'rinishda chizishni shu ustundan biladi.
    ("subscription_requests", "proof_kind",
     "ALTER TABLE subscription_requests ADD COLUMN proof_kind TEXT NOT NULL DEFAULT 'rasm'"),
    ("users", "referred_by", "ALTER TABLE users ADD COLUMN referred_by INTEGER"),
    ("users", "bonus_days",
     "ALTER TABLE users ADD COLUMN bonus_days INTEGER NOT NULL DEFAULT 0"),
    ("users", "reminder_hour", "ALTER TABLE users ADD COLUMN reminder_hour INTEGER"),
    ("users", "warned_stage",
     "ALTER TABLE users ADD COLUMN warned_stage INTEGER NOT NULL DEFAULT 0"),
    ("users", "lang", "ALTER TABLE users ADD COLUMN lang TEXT NOT NULL DEFAULT 'uz'"),
    # Shartlar va maxfiylik siyosatiga rozilik. Qonun bo'yicha shaxsga
    # doir ma'lumotni ishlashdan OLDIN rozilik olinishi shart.
    ("users", "consent_at", "ALTER TABLE users ADD COLUMN consent_at TEXT"),
    ("users", "consent_version",
     "ALTER TABLE users ADD COLUMN consent_version TEXT NOT NULL DEFAULT ''"),
    # Marketing: ketma-ket faol kunlar va oxirgi yozuv kuni.
    ("users", "streak", "ALTER TABLE users ADD COLUMN streak INTEGER NOT NULL DEFAULT 0"),
    ("users", "best_streak",
     "ALTER TABLE users ADD COLUMN best_streak INTEGER NOT NULL DEFAULT 0"),
    ("users", "last_entry_day", "ALTER TABLE users ADD COLUMN last_entry_day TEXT"),
    ("users", "winback_at", "ALTER TABLE users ADD COLUMN winback_at TEXT"),
    # Yozuv kiritilgan paytdagi kurs va asosiy valyutadagi qiymati.
    # Shu ikkisi bo'lgani uchun so'm va dollar bitta jamlanmada qo'shiladi.
    ("transactions", "rate", "ALTER TABLE transactions ADD COLUMN rate REAL NOT NULL DEFAULT 1"),
    ("transactions", "amount_base", "ALTER TABLE transactions ADD COLUMN amount_base REAL"),
]


def _open(path: str, timeout: int):
    """Bazaga ulanadi. Kalit sozlangan bo'lsa — SQLCipher orqali.

    Kalit bo'lmasa oddiy sqlite3 ishlatiladi: mahalliy ishlab chiqish va
    sinovlar shifrlanmagan baza bilan ishlaydi. Serverda kalit doim bor.

    Kalit noto'g'ri bo'lsa SQLCipher birinchi so'rovdayoq xato beradi —
    jimgina bo'sh baza yaratilib qolmaydi.
    """
    if not config.DB_ENCRYPTION_KEY:
        conn = sqlite3.connect(path, timeout=timeout)
        conn.row_factory = sqlite3.Row
        conn.execute("ATTACH DATABASE ? AS shaxsiy", (config.PRIVATE_DB_PATH,))
        return conn

    from sqlcipher3 import dbapi2 as sqlcipher

    conn = sqlcipher.connect(path, timeout=timeout)
    conn.execute(f"PRAGMA key = {config.db_key_pragma()}")
    # Row sinfi modulga bog'liq — sqlite3.Row ni bu yerga qo'yib bo'lmaydi.
    conn.row_factory = sqlcipher.Row
    # Shaxsiy baza — alohida fayl, alohida kalit. ATTACH dagi KEY asosiy
    # kalitdan mustaqil: shu tufayli asosiy kalitni biladigan (masalan
    # admin panel) shaxsiy bazani ocholmaydi.
    conn.execute(f"ATTACH DATABASE ? AS shaxsiy KEY {config.private_key_pragma()}",
                 (config.PRIVATE_DB_PATH,))
    return conn


@contextmanager
def get_conn():
    # timeout: boshqa jarayon (bot yoki webapp) yozayotgan bo'lsa kutadi,
    # darhol "database is locked" bermaydi.
    conn = _open(config.DB_PATH, timeout=10)
    conn.execute("PRAGMA foreign_keys = ON")
    # WAL: bot.py va webapp.py bir vaqtda o'qishi/yozishi mumkin — o'qish
    # yozishni bloklamaydi. Bir marta o'rnatiladi, keyingi ulanishlarga ham tegishli.
    #
    # Ikkala baza uchun alohida qo'yiladi — WAL har bir faylning o'z
    # xossasi. Eslatma: WAL da ikki bazaga tegadigan bitta tranzaksiya
    # global atomik emas. Bizda bunday joy bittagina — yozuv qo'shilganda
    # `entry_counts` ham yangilanadi — va u yerda eng yomoni sanoq bir
    # birlikka adashishi, ya'ni ko'rinishga taalluqli, pulga emas.
    conn.execute("PRAGMA journal_mode = WAL")
    conn.execute("PRAGMA shaxsiy.journal_mode = WAL")
    try:
        yield conn
        conn.commit()
    finally:
        conn.close()


def _cols(conn, table: str, schema: str = "") -> list[str]:
    """Jadval ustunlari. `schema` — 'main' yoki 'shaxsiy'.

    Diqqat: PRAGMA da baza nomi qavs ICHIDA emas, PRAGMA nomining
    OLDIDA yoziladi — `PRAGMA main.table_info(t)`, `table_info(main.t)`
    emas. Ikkinchisi sintaksis xatosi beradi.
    """
    prefix = f"{schema}." if schema else ""
    return [r["name"] for r in conn.execute(f"PRAGMA {prefix}table_info({table})")]


def _move_to_private(conn, table: str) -> int:
    """Jadvalni asosiy bazadan shaxsiy bazaga ko'chiradi. Bir martalik.

    Ko'chirish va o'chirish BITTA tranzaksiyada bo'lishi kerak edi, lekin
    WAL da ikki baza orasida bu kafolatlanmaydi. Shuning uchun tartib
    shunday: avval nusxa olinadi, nusxa TEKSHIRILADI, keyingina asl
    o'chiriladi. Yarim yo'lda uzilsa eng yomoni nusxa ikki joyda qoladi
    va keyingi ishga tushishda qayta urinib ko'riladi — ma'lumot
    yo'qolmaydi.
    """
    if table not in {r["name"] for r in conn.execute(
            "SELECT name FROM main.sqlite_master WHERE type='table'")}:
        return 0

    src = _cols(conn, table, "main")
    dst = _cols(conn, table, "shaxsiy")
    shared = [c for c in src if c in dst]
    cols = ", ".join(shared)

    n = int(conn.execute(f"SELECT COUNT(*) FROM main.{table}").fetchone()[0])
    if n:
        conn.execute(f"INSERT OR REPLACE INTO shaxsiy.{table} ({cols}) "
                     f"SELECT {cols} FROM main.{table}")
        moved = int(conn.execute(
            f"SELECT COUNT(*) FROM shaxsiy.{table}").fetchone()[0])
        if moved < n:
            raise RuntimeError(
                f"{table}: {n} ta yozuvdan {moved} tasi ko'chdi — "
                "asl nusxa o'chirilmaydi")
    conn.execute(f"DROP TABLE main.{table}")
    return n


def init() -> None:
    with get_conn() as conn:
        conn.executescript(SCHEMA)
        conn.executescript(PRIVATE_SCHEMA)

        # Eski bazada `transactions` hali asosiy faylda bo'lishi mumkin.
        # Ko'chirishdan OLDIN unga yetishmayotgan ustunlarni qo'shamiz,
        # aks holda nusxada `rate`/`amount_base` tushib qolardi.
        main_tables = {r["name"] for r in conn.execute(
            "SELECT name FROM main.sqlite_master WHERE type='table'")}
        if "transactions" in main_tables:
            existing = set(_cols(conn, "transactions", "main"))
            for column, sql in MIGRATIONS:
                if column not in existing:
                    conn.execute(sql.replace("transactions",
                                             "main.transactions", 1))
            for table, column, sql in TABLE_MIGRATIONS:
                if table == "transactions" and column not in existing:
                    conn.execute(sql.replace("transactions",
                                             "main.transactions", 1))
            moved = _move_to_private(conn, "transactions")
            if moved:
                log_moved("transactions", moved)
        if "budgets" in main_tables:
            moved = _move_to_private(conn, "budgets")
            if moved:
                log_moved("budgets", moved)

        for table, column, sql in TABLE_MIGRATIONS:
            if table == "transactions":
                continue      # shaxsiy bazada, sxemada allaqachon bor
            cols = set(_cols(conn, table))
            if cols and column not in cols:
                conn.execute(sql)

        # Shaxsiy bazadagi jadvallarga keyin qo'shilgan ustunlar.
        # `CREATE TABLE IF NOT EXISTS` mavjud jadvalni o'zgartirmaydi,
        # shuning uchun bu yerda qo'lda tekshiriladi.
        for table, column, sql in PRIVATE_TABLE_MIGRATIONS:
            cols = set(_cols(conn, table, "shaxsiy"))
            if cols and column not in cols:
                conn.execute(sql)

        # Eski yozuvlarda amount_base bo'sh: so'mlilarini darhol to'ldiramiz,
        # valyutalilarini backfill_base() tarmoq orqali kurs olib to'ldiradi.
        conn.execute(
            "UPDATE transactions SET amount_base = amount, rate = 1 "
            "WHERE amount_base IS NULL AND currency = 'som'")

        _rebuild_entry_counts(conn)


def log_moved(table: str, n: int) -> None:
    import logging
    logging.getLogger(__name__).warning(
        "%s: %s ta yozuv shaxsiy bazaga ko'chirildi", table, n)


def _rebuild_entry_counts(conn) -> None:
    """Admin panel ko'radigan sanoqni shaxsiy bazadan qayta yig'adi.

    Faqat SON ko'chadi. Ko'chirishdan keyin va har ishga tushishda
    chaqiriladi: sanoq surilib qolgan bo'lsa (masalan yozuv qo'shilgan
    payt uzilish bo'lgan) shu yerda tuzaladi.
    """
    rows = conn.execute(
        "SELECT user_id, occurred_on AS day, COUNT(*) AS n "
        "FROM transactions GROUP BY user_id, occurred_on").fetchall()
    conn.execute("DELETE FROM entry_counts")
    conn.executemany(
        "INSERT INTO entry_counts (user_id, day, n) VALUES (?, ?, ?)",
        [(r["user_id"], r["day"], r["n"]) for r in rows])


def _bump_entries(conn, user_id: int, day: str, delta: int) -> None:
    """Yozuvlar sanog'ini o'zgartiradi (admin panel uchun).

    Sanoq noldan pastga tushmaydi va nol bo'lgan qator o'chiriladi —
    jadval kerakmas qatorlar bilan o'smasin.
    """
    conn.execute(
        "INSERT INTO entry_counts (user_id, day, n) VALUES (?, ?, ?) "
        "ON CONFLICT(user_id, day) DO UPDATE SET n = MAX(0, n + ?)",
        (user_id, day, max(0, delta), delta))
    conn.execute("DELETE FROM entry_counts WHERE user_id = ? AND day = ? AND n <= 0",
                 (user_id, day))


def app_settings() -> dict[str, str]:
    """Admin panelda o'zgartirilgan qiymatlar.

    Jadval admin panel tomonidan yaratiladi. Bot uni faqat o'qiydi va
    jadval hali yo'q bo'lsa bo'sh lug'at qaytaradi — bot admin paneldan
    oldin ishga tushishi mumkin.
    """
    try:
        with get_conn() as conn:
            rows = conn.execute("SELECT key, value FROM app_settings").fetchall()
        return {r["key"]: r["value"] for r in rows}
    except Exception:
        return {}


def backfill_base(default_rate: float | None = None) -> int:
    """amount_base bo'sh qolgan valyutali yozuvlarni to'ldiradi.

    Har bir yozuv uchun O'SHA KUNDAGI kurs olinadi — bugungisi emas.
    """
    import rates as rates_module

    with get_conn() as conn:
        rows = conn.execute(
            "SELECT id, amount, currency, occurred_on FROM transactions "
            "WHERE amount_base IS NULL").fetchall()
        filled = 0
        for r in rows:
            try:
                day = date.fromisoformat(r["occurred_on"])
            except (TypeError, ValueError):
                day = date.today()
            try:
                rate = rates_module.get(r["currency"], day)
            except Exception:
                rate = default_rate or config.USD_RATE_FALLBACK
            conn.execute(
                "UPDATE transactions SET rate = ?, amount_base = ? WHERE id = ?",
                (rate, round(float(r["amount"]) * rate, 2), r["id"]))
            filled += 1
    return filled


# --------------------------------------------------------------------------- #
# Kurslar
# --------------------------------------------------------------------------- #

def get_rate(currency: str, day: date) -> float | None:
    with get_conn() as conn:
        row = conn.execute(
            "SELECT rate FROM rates WHERE day = ? AND currency = ?",
            (day.isoformat(), currency.lower())).fetchone()
        return float(row["rate"]) if row else None


def set_rate(currency: str, day: date, rate: float, source: str = "") -> None:
    with get_conn() as conn:
        conn.execute(
            "INSERT INTO rates (day, currency, rate, source) VALUES (?,?,?,?) "
            "ON CONFLICT(day, currency) DO UPDATE SET rate = excluded.rate, "
            "source = excluded.source",
            (day.isoformat(), currency.lower(), float(rate), source))


def rate_source(currency: str, day: date) -> str | None:
    with get_conn() as conn:
        row = conn.execute(
            "SELECT source FROM rates WHERE day = ? AND currency = ?",
            (day.isoformat(), currency.lower())).fetchone()
        return row["source"] if row else None


def latest_rate(currency: str) -> float | None:
    with get_conn() as conn:
        row = conn.execute(
            "SELECT rate FROM rates WHERE currency = ? ORDER BY day DESC LIMIT 1",
            (currency.lower(),)).fetchone()
        return float(row["rate"]) if row else None


# --------------------------------------------------------------------------- #
# Yozish
# --------------------------------------------------------------------------- #

def _base_of(amount: float, currency: str, occurred_on: str) -> tuple[float, float]:
    """(kurs, asosiy valyutadagi summa). So'm uchun kurs 1.

    Kurs olishda tarmoq xatosi bo'lsa ham yozuv yo'qolmasligi kerak —
    shuning uchun har qanday xatolikda zaxira qiymatga tushamiz.
    """
    if (currency or "som").lower() == "som":
        return 1.0, round(float(amount), 2)
    try:
        import rates as rates_module
        day = date.fromisoformat(occurred_on)
        rate = rates_module.get(currency, day)
    except Exception:                       # tarmoq, format yoki boshqa xato
        rate = float(config.USD_RATE_FALLBACK)
    return rate, round(float(amount) * rate, 2)


def add_transaction(
    user_id: int,
    kind: str,
    amount: float,
    category: str,
    note: str = "",
    person: str | None = None,
    occurred_on: str | None = None,
    raw_text: str = "",
    receipt_id: str | None = None,
    currency: str = "som",
) -> int:
    occurred_on = occurred_on or date.today().isoformat()
    rate, amount_base = _base_of(amount, currency, occurred_on)
    with get_conn() as conn:
        cur = conn.execute(
            """INSERT INTO transactions
               (user_id, kind, amount, category, note, person, occurred_on,
                raw_text, receipt_id, currency, rate, amount_base)
               VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)""",
            (user_id, kind, float(amount), category, note, person,
             occurred_on, raw_text, receipt_id, currency, rate, amount_base),
        )
        _bump_entries(conn, user_id, occurred_on, +1)
        return int(cur.lastrowid)


def _insert_many(conn, rows: list[dict]) -> list[int]:
    ids: list[int] = []
    # Kurs bitta chek uchun bir marta hisoblanadi — hamma qator bir kunda
    # va bir valyutada bo'ladi.
    prepared = [
        (r, *_base_of(r["amount"], r.get("currency", "som"), r["occurred_on"]))
        for r in rows
    ]
    for r, rate, amount_base in prepared:
        cur = conn.execute(
            """INSERT INTO transactions
               (user_id, kind, amount, category, note, person, occurred_on,
                raw_text, receipt_id, currency, rate, amount_base)
               VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)""",
            (r["user_id"], r["kind"], float(r["amount"]), r["category"],
             r.get("note", ""), r.get("person"), r["occurred_on"],
             r.get("raw_text", ""), r.get("receipt_id"),
             r.get("currency", "som"), rate, amount_base),
        )
        ids.append(int(cur.lastrowid))
        _bump_entries(conn, r["user_id"], r["occurred_on"], +1)
    return ids


def add_many(rows: list[dict]) -> list[int]:
    """Bir nechta yozuvni bitta tranzaksiyada saqlaydi."""
    with get_conn() as conn:
        return _insert_many(conn, rows)


def add_receipt(user_id: int, receipt_id: str, *, shop: str, occurred_on: str,
                currency: str, printed_total: float | None,
                discount: float | None, items: list[dict]) -> list[int]:
    """Chekni saqlaydi: sarlavha va mahsulot qatorlari BITTA tranzaksiyada.

    Ikkalasi ham shaxsiy bazada — yarim saqlangan chek (sarlavhasiz
    mahsulotlar yoki mahsulotsiz sarlavha) bo'lib qolmaydi.
    """
    with get_conn() as conn:
        conn.execute(
            """INSERT INTO receipts (user_id, receipt_id, shop, occurred_on,
                                     currency, printed_total, discount)
               VALUES (?, ?, ?, ?, ?, ?, ?)""",
            (user_id, receipt_id, shop or "", occurred_on, currency,
             printed_total, discount))
        return _insert_many(conn, [
            {**item, "user_id": user_id, "receipt_id": receipt_id,
             "occurred_on": occurred_on, "currency": currency}
            for item in items
        ])


def get_receipt(user_id: int, receipt_id: str) -> dict | None:
    """Chek sarlavhasi + mahsulotlardan hisoblangan jami va soni."""
    with get_conn() as conn:
        row = conn.execute(
            """SELECT t.receipt_id, COUNT(*) AS n, SUM(t.amount) AS total,
                      MIN(t.occurred_on) AS occurred_on, MAX(t.currency) AS currency,
                      r.shop, r.printed_total, r.discount
               FROM transactions t
               LEFT JOIN receipts r
                 ON r.user_id = t.user_id AND r.receipt_id = t.receipt_id
               WHERE t.user_id = ? AND t.receipt_id = ?
               GROUP BY t.receipt_id""",
            (user_id, receipt_id)).fetchone()
    return dict(row) if row else None


def delete_transaction(user_id: int, tx_id: int) -> bool:
    with get_conn() as conn:
        # Sanoqni kamaytirish uchun qaysi kun ekanini oldindan bilish kerak.
        row = conn.execute(
            "SELECT occurred_on, receipt_id FROM transactions "
            "WHERE id = ? AND user_id = ?",
            (tx_id, user_id)).fetchone()
        cur = conn.execute(
            "DELETE FROM transactions WHERE id = ? AND user_id = ?", (tx_id, user_id)
        )
        if cur.rowcount and row:
            _bump_entries(conn, user_id, row["occurred_on"], -1)
            # Chekning oxirgi mahsuloti o'chirilsa — sarlavha ham ketadi.
            if row["receipt_id"] and not conn.execute(
                    "SELECT 1 FROM transactions WHERE user_id = ? AND receipt_id = ?",
                    (user_id, row["receipt_id"])).fetchone():
                conn.execute(
                    "DELETE FROM receipts WHERE user_id = ? AND receipt_id = ?",
                    (user_id, row["receipt_id"]))
        return cur.rowcount > 0


def update_category(user_id: int, tx_id: int, category: str) -> bool:
    with get_conn() as conn:
        cur = conn.execute(
            "UPDATE transactions SET category = ? WHERE id = ? AND user_id = ?",
            (category, tx_id, user_id),
        )
        return cur.rowcount > 0


def update_kind(user_id: int, tx_id: int, kind: str, category: str) -> bool:
    """Yozuv turini (kirim/chiqim) almashtiradi va kategoriyani shu turga mos
    boshlang'ich qiymatga qaytaradi — eski kategoriya yangi turga to'g'ri kelmasligi mumkin."""
    with get_conn() as conn:
        cur = conn.execute(
            "UPDATE transactions SET kind = ?, category = ? WHERE id = ? AND user_id = ?",
            (kind, category, tx_id, user_id),
        )
        return cur.rowcount > 0


def settle_debt(user_id: int, tx_id: int) -> bool:
    with get_conn() as conn:
        cur = conn.execute(
            "UPDATE transactions SET settled = 1 WHERE id = ? AND user_id = ? AND kind IN (?, ?)",
            (tx_id, user_id, config.KIND_QARZ_BERDIM, config.KIND_QARZ_OLDIM),
        )
        return cur.rowcount > 0


# --------------------------------------------------------------------------- #
# O'qish
# --------------------------------------------------------------------------- #

def get_transaction(user_id: int, tx_id: int) -> sqlite3.Row | None:
    with get_conn() as conn:
        cur = conn.execute(
            "SELECT * FROM transactions WHERE id = ? AND user_id = ?", (tx_id, user_id)
        )
        return cur.fetchone()


def list_range(
    user_id: int,
    start: date,
    end: date,
    kinds: Iterable[str] | None = None,
) -> list[sqlite3.Row]:
    kinds = list(kinds) if kinds else config.KINDS
    placeholders = ",".join("?" * len(kinds))
    with get_conn() as conn:
        cur = conn.execute(
            f"""SELECT * FROM transactions
                WHERE user_id = ? AND occurred_on BETWEEN ? AND ?
                  AND kind IN ({placeholders})
                ORDER BY occurred_on ASC, id ASC""",
            (user_id, start.isoformat(), end.isoformat(), *kinds),
        )
        return cur.fetchall()


def totals(user_id: int, start: date, end: date, currency: str = "som") -> dict[str, float]:
    """Bitta valyutadagi turlar bo'yicha jami — orqaga moslik uchun saqlangan."""
    return totals_by_currency(user_id, start, end).get(
        currency, {k: 0.0 for k in config.KINDS}
    )


def totals_by_currency(user_id: int, start: date, end: date) -> dict[str, dict[str, float]]:
    """{valyuta: {turi: summa}} — valyutalar birlashtirilmaydi (kurs yo'q)."""
    with get_conn() as conn:
        cur = conn.execute(
            """SELECT kind, currency, COALESCE(SUM(amount), 0) AS total
               FROM transactions
               WHERE user_id = ? AND occurred_on BETWEEN ? AND ?
               GROUP BY kind, currency""",
            (user_id, start.isoformat(), end.isoformat()),
        )
        result: dict[str, dict[str, float]] = {
            "som": {k: 0.0 for k in config.KINDS}
        }
        for row in cur.fetchall():
            bucket = result.setdefault(row["currency"], {k: 0.0 for k in config.KINDS})
            bucket[row["kind"]] = float(row["total"])
        return result


def totals_unified(user_id: int, start: date, end: date) -> dict:
    """Barcha valyutalarni asosiy valyutaga o'girib jamlaydi.

    Odamning hamyoni bitta: dollarda to'lasa ham pul o'sha umumiy
    mablag'idan chiqadi. `amount_base` — yozuv kiritilgan kundagi kurs
    bilan hisoblangan so'mdagi qiymat.
    """
    with get_conn() as conn:
        rows = conn.execute(
            """SELECT kind, currency,
                      COALESCE(SUM(amount_base), 0) AS base,
                      COALESCE(SUM(amount), 0) AS orig,
                      COUNT(*) AS n
               FROM transactions
               WHERE user_id = ? AND occurred_on BETWEEN ? AND ?
               GROUP BY kind, currency""",
            (user_id, start.isoformat(), end.isoformat()),
        ).fetchall()

    totals = {k: 0.0 for k in config.KINDS}
    # Chet el valyutasidagi ulush — hisobotda alohida eslatib o'tiladi.
    foreign: dict[str, dict[str, float]] = {}
    for r in rows:
        totals[r["kind"]] = round(totals[r["kind"]] + float(r["base"]), 2)
        if r["currency"] != "som":
            bucket = foreign.setdefault(r["currency"], {"orig": 0.0, "base": 0.0,
                                                        "count": 0})
            bucket["orig"] = round(bucket["orig"] + float(r["orig"]), 2)
            bucket["base"] = round(bucket["base"] + float(r["base"]), 2)
            bucket["count"] += r["n"]
    return {"totals": totals, "foreign": foreign}


def by_category_unified(
    user_id: int, start: date, end: date, kind: str
) -> list[tuple[str, float, int]]:
    """Kategoriyalar kesimi — valyutalar asosiy valyutada birlashtirilgan."""
    with get_conn() as conn:
        cur = conn.execute(
            """SELECT category, SUM(amount_base) AS total, COUNT(*) AS cnt
               FROM transactions
               WHERE user_id = ? AND kind = ? AND occurred_on BETWEEN ? AND ?
               GROUP BY category ORDER BY total DESC""",
            (user_id, kind, start.isoformat(), end.isoformat()),
        )
        return [(r["category"], float(r["total"] or 0), int(r["cnt"]))
                for r in cur.fetchall()]


def by_category(
    user_id: int, start: date, end: date, kind: str, currency: str = "som"
) -> list[tuple[str, float, int]]:
    with get_conn() as conn:
        cur = conn.execute(
            """SELECT category, SUM(amount) AS total, COUNT(*) AS cnt
               FROM transactions
               WHERE user_id = ? AND kind = ? AND currency = ?
                 AND occurred_on BETWEEN ? AND ?
               GROUP BY category
               ORDER BY total DESC""",
            (user_id, kind, currency, start.isoformat(), end.isoformat()),
        )
        return [(r["category"], float(r["total"]), int(r["cnt"])) for r in cur.fetchall()]


def search_transactions(
    user_id: int,
    start: date,
    end: date,
    kind: str | None = None,
    currency: str | None = None,
    search: str | None = None,
    receipt_id: str | None = None,
    limit: int = 50,
    offset: int = 0,
) -> dict:
    """Filtrlash, jamlash va sahifalash — hammasi SQL tomonida.

    Ilgari butun tarix Python'ga tortilib, u yerda filtrlanardi. Bir necha
    yillik yozuv to'planganda bu sezilarli yuk beradi.
    """
    where = ["user_id = ?", "occurred_on BETWEEN ? AND ?"]
    params: list = [user_id, start.isoformat(), end.isoformat()]

    if kind:
        # `kind` bitta tur ham, ro'yxat ham bo'lishi mumkin. Ro'yxat
        # kerak bo'ladigan joy — Mini App dagi «Qarz» va «Jamg'arma»
        # yorliqlari: ular ikkitadan turni birga ko'rsatadi.
        kinds = [kind] if isinstance(kind, str) else list(kind)
        where.append("kind IN (%s)" % ", ".join("?" for _ in kinds))
        params += kinds
    if currency:
        where.append("currency = ?")
        params.append(currency)
    if receipt_id:
        where.append("receipt_id = ?")
        params.append(receipt_id)
    if search and search.strip():
        needle = f"%{search.strip().lower()}%"
        where.append(
            "(LOWER(COALESCE(note,'')) LIKE ? OR LOWER(COALESCE(category,'')) LIKE ? "
            "OR LOWER(COALESCE(person,'')) LIKE ? OR LOWER(COALESCE(raw_text,'')) LIKE ?)")
        params += [needle] * 4

    clause = " AND ".join(where)
    with get_conn() as conn:
        total = int(conn.execute(
            f"SELECT COUNT(*) FROM transactions WHERE {clause}", params).fetchone()[0])
        totals = {
            r["currency"]: round(float(r["s"]), 2)
            for r in conn.execute(
                f"SELECT currency, SUM(amount) s FROM transactions "
                f"WHERE {clause} GROUP BY currency", params).fetchall()
        }
        items = conn.execute(
            f"""SELECT * FROM transactions WHERE {clause}
                ORDER BY occurred_on DESC, id DESC LIMIT ? OFFSET ?""",
            params + [limit, offset]).fetchall()

    return {"total_count": total, "totals": totals, "items": items}


def recent(user_id: int, limit: int = 10) -> list[sqlite3.Row]:
    with get_conn() as conn:
        cur = conn.execute(
            "SELECT * FROM transactions WHERE user_id = ? ORDER BY id DESC LIMIT ?",
            (user_id, limit),
        )
        return cur.fetchall()


def open_debts(user_id: int) -> list[sqlite3.Row]:
    with get_conn() as conn:
        cur = conn.execute(
            """SELECT * FROM transactions
               WHERE user_id = ? AND kind IN (?, ?) AND settled = 0
               ORDER BY occurred_on ASC, id ASC""",
            (user_id, config.KIND_QARZ_BERDIM, config.KIND_QARZ_OLDIM),
        )
        return cur.fetchall()


def all_rows(user_id: int) -> list[sqlite3.Row]:
    with get_conn() as conn:
        cur = conn.execute(
            "SELECT * FROM transactions WHERE user_id = ? ORDER BY occurred_on ASC, id ASC",
            (user_id,),
        )
        return cur.fetchall()


def rows_by_receipt(user_id: int, receipt_id: str) -> list[sqlite3.Row]:
    with get_conn() as conn:
        cur = conn.execute(
            """SELECT * FROM transactions
               WHERE user_id = ? AND receipt_id = ?
               ORDER BY id ASC""",
            (user_id, receipt_id),
        )
        return cur.fetchall()


def delete_receipt(user_id: int, receipt_id: str) -> int:
    """Butun chekni o'chiradi: mahsulotlar va sarlavha bitta tranzaksiyada."""
    with get_conn() as conn:
        days = conn.execute(
            "SELECT occurred_on, COUNT(*) n FROM transactions "
            "WHERE user_id = ? AND receipt_id = ? GROUP BY occurred_on",
            (user_id, receipt_id)).fetchall()
        cur = conn.execute(
            "DELETE FROM transactions WHERE user_id = ? AND receipt_id = ?",
            (user_id, receipt_id),
        )
        conn.execute("DELETE FROM receipts WHERE user_id = ? AND receipt_id = ?",
                     (user_id, receipt_id))
        for d in days:
            _bump_entries(conn, user_id, d["occurred_on"], -d["n"])
        return cur.rowcount


def recent_entries(user_id: int, limit: int = 12) -> list[dict]:
    """«Oxirgi» ro'yxati: oddiy yozuvlar va cheklar aralash, eng yangisi
    birinchi. Chek mahsulotlari BITTA qatorga yig'iladi.

    Har bir element: oddiy yozuv uchun `receipt_id` bo'sh va qolgan
    maydonlar `transactions` dagidek; chek uchun esa `n` (mahsulotlar
    soni), `amount` (jami), `shop` va `id` (chekdagi eng katta id —
    `/ochir` shu raqam bilan butun chekni o'chiradi).
    """
    with get_conn() as conn:
        rows = conn.execute(
            """SELECT MAX(t.id) AS id, t.receipt_id, COUNT(*) AS n,
                      SUM(t.amount) AS amount, MAX(t.currency) AS currency,
                      MAX(t.occurred_on) AS occurred_on,
                      MAX(t.kind) AS kind, MAX(t.category) AS category,
                      MAX(t.note) AS note, MAX(t.person) AS person,
                      MAX(t.settled) AS settled, r.shop
               FROM transactions t
               LEFT JOIN receipts r
                 ON r.user_id = t.user_id AND r.receipt_id = t.receipt_id
               WHERE t.user_id = ?
               GROUP BY CASE WHEN t.receipt_id IS NULL
                             THEN 'tx' || t.id ELSE t.receipt_id END
               ORDER BY MAX(t.id) DESC
               LIMIT ?""",
            (user_id, limit)).fetchall()
    return [dict(r) for r in rows]


def export_rows(user_id: int) -> list[sqlite3.Row]:
    """CSV uchun: har bir mahsulot qatori o'z cheki identifikatori va
    do'koni bilan."""
    with get_conn() as conn:
        return conn.execute(
            """SELECT t.*, COALESCE(r.shop, '') AS shop
               FROM transactions t
               LEFT JOIN receipts r
                 ON r.user_id = t.user_id AND r.receipt_id = t.receipt_id
               WHERE t.user_id = ?
               ORDER BY t.occurred_on ASC, t.id ASC""",
            (user_id,)).fetchall()


# --------------------------------------------------------------------------- #
# Foydalanuvchilar, obuna va kirish huquqi
# --------------------------------------------------------------------------- #

def _now() -> datetime:
    return datetime.now(config.TZ)


def _today_str() -> str:
    """Kunlik limitlar mahalliy yarim tunda yangilanishi uchun Toshkent sanasi."""
    return _now().date().isoformat()


def _parse_dt(raw: str | None) -> datetime | None:
    if not raw:
        return None
    try:
        dt = datetime.fromisoformat(raw)
    except ValueError:
        return None
    # Bazada mintaqasiz saqlanadi — solishtirish uchun mintaqa qo'shamiz.
    return dt if dt.tzinfo else dt.replace(tzinfo=config.TZ)


def get_or_create_user(user_id: int, first_name: str = "", username: str | None = None) -> sqlite3.Row:
    """Foydalanuvchini qaytaradi; birinchi marta ko'rilsa bepul sinov muddati
    bilan yaratadi."""
    with get_conn() as conn:
        row = conn.execute("SELECT * FROM users WHERE user_id = ?", (user_id,)).fetchone()
        if row is None:
            trial_ends = _now() + timedelta(days=config.trial_days())
            conn.execute(
                """INSERT INTO users (user_id, first_name, username, trial_ends_at, last_seen_at)
                   VALUES (?, ?, ?, ?, ?)""",
                (user_id, first_name or "", username, trial_ends.isoformat(), _now().isoformat()),
            )
            row = conn.execute("SELECT * FROM users WHERE user_id = ?", (user_id,)).fetchone()
        else:
            # Ism/username o'zgargan bo'lishi mumkin — yangilab turamiz.
            conn.execute(
                "UPDATE users SET first_name = ?, username = ?, last_seen_at = ? WHERE user_id = ?",
                (first_name or row["first_name"], username, _now().isoformat(), user_id),
            )
        return row


def access_status(user_id: int, first_name: str = "", username: str | None = None) -> dict:
    """Foydalanuvchining kirish holati.

    Qaytaradi: {"ok": bool, "status": str, "until": datetime|None, "days_left": int|None}
    status: owner | trial | subscribed | expired | blocked | not_allowed
    """
    if user_id in config.OWNER_IDS:
        # Egaga muddat tekshirilmaydi, lekin tashrifi baribir yozilishi
        # kerak: aks holda admin paneldagi «oxirgi faollik» ustuni ega
        # uchun muzlab qoladi va statistikani buzadi.
        get_or_create_user(user_id, first_name, username)
        return {"ok": True, "status": "owner", "until": None, "days_left": None}

    # ALLOWED_USER_IDS to'ldirilgan bo'lsa — yopiq rejim (sinov guruhi uchun).
    if config.ALLOWED_USER_IDS and user_id not in config.ALLOWED_USER_IDS:
        return {"ok": False, "status": "not_allowed", "until": None, "days_left": None}

    row = get_or_create_user(user_id, first_name, username)
    if row["blocked"]:
        return {"ok": False, "status": "blocked", "until": None, "days_left": None}

    now = _now()
    sub = _parse_dt(row["subscribed_until"])
    if sub and sub > now:
        return {"ok": True, "status": "subscribed", "until": sub,
                "days_left": max(0, (sub - now).days)}

    trial = _parse_dt(row["trial_ends_at"])
    if trial and trial > now:
        return {"ok": True, "status": "trial", "until": trial,
                "days_left": max(0, (trial - now).days)}

    return {"ok": False, "status": "expired", "until": sub or trial, "days_left": 0}


def grant_subscription(user_id: int, days: int) -> datetime:
    """Obunani uzaytiradi. Amaldagi obuna bor bo'lsa uning ustiga qo'shiladi."""
    with get_conn() as conn:
        row = conn.execute("SELECT subscribed_until FROM users WHERE user_id = ?",
                           (user_id,)).fetchone()
        if row is None:
            conn.execute("INSERT INTO users (user_id) VALUES (?)", (user_id,))
            base = _now()
        else:
            current = _parse_dt(row["subscribed_until"])
            base = current if current and current > _now() else _now()
        new_until = base + timedelta(days=days)
        conn.execute("UPDATE users SET subscribed_until = ? WHERE user_id = ?",
                     (new_until.isoformat(), user_id))
        return new_until


def _now_local() -> str:
    """Mahalliy vaqtdagi ISO muhri.

    SQLite'ning `datetime('now')` UTC beradi — admin panel bilan bir xil
    bo'lishi uchun vaqtni ochiq yozamiz.
    """
    return datetime.now(config.TZ).isoformat(timespec="seconds")


def add_subscription_request(user_id: int, plan_code: str, price: int) -> int:
    """Foydalanuvchi tarif tanlaganda chaqiriladi. Admin web panelda ko'rinadi.

    Takroriy bosishdan himoya: shu foydalanuvchining hal qilinmagan so'rovi
    bo'lsa, yangisi ochilmaydi — mavjudining tarifi yangilanadi."""
    with get_conn() as conn:
        row = conn.execute(
            "SELECT id FROM subscription_requests "
            "WHERE user_id = ? AND status = 'kutilmoqda' ORDER BY id DESC LIMIT 1",
            (user_id,),
        ).fetchone()
        if row:
            conn.execute(
                "UPDATE subscription_requests SET plan_code = ?, price = ?, "
                "created_at = datetime('now') WHERE id = ?",
                (plan_code, price, row["id"]),
            )
            return int(row["id"])
        cur = conn.execute(
            "INSERT INTO subscription_requests (user_id, plan_code, price, created_at) "
            "VALUES (?,?,?,?)",
            (user_id, plan_code, price, _now_local()),
        )
        return int(cur.lastrowid)


def attach_payment_proof(request_id: int, file_id: str, kind: str = "rasm") -> bool:
    """Foydalanuvchi yuborgan to'lov chekini so'rovga biriktiradi.

    kind: 'rasm' yoki 'pdf' — admin panel chekni qanday ko'rsatishini
    shundan biladi.
    """
    with get_conn() as conn:
        cur = conn.execute(
            """UPDATE subscription_requests
               SET proof_file_id = ?, proof_at = ?, proof_kind = ?,
                   status = 'tekshiruvda'
               WHERE id = ? AND status IN ('kutilmoqda', 'tekshiruvda')""",
            (file_id, _now_local(), kind, request_id),
        )
        return cur.rowcount > 0


def get_request(request_id: int) -> sqlite3.Row | None:
    with get_conn() as conn:
        return conn.execute(
            "SELECT * FROM subscription_requests WHERE id = ?", (request_id,)
        ).fetchone()


def open_request_for(user_id: int) -> sqlite3.Row | None:
    """Foydalanuvchining hal qilinmagan oxirgi so'rovi."""
    with get_conn() as conn:
        return conn.execute(
            """SELECT * FROM subscription_requests
               WHERE user_id = ? AND status IN ('kutilmoqda', 'tekshiruvda')
               ORDER BY id DESC LIMIT 1""",
            (user_id,),
        ).fetchone()


def pending_request_count() -> int:
    with get_conn() as conn:
        return int(conn.execute(
            "SELECT COUNT(*) FROM subscription_requests "
            "WHERE status IN ('kutilmoqda', 'tekshiruvda')"
        ).fetchone()[0])


# --------------------------------------------------------------------------- #
# Referal — do'st taklif qilish
# --------------------------------------------------------------------------- #

def set_referrer(user_id: int, referrer_id: int) -> bool:
    """Yangi foydalanuvchini taklif qilgan odamni belgilaydi.

    Faqat bir marta va faqat yangi (yozuvi yo'q) foydalanuvchi uchun —
    aks holda o'zini o'zi taklif qilish yoki qayta hisoblash mumkin bo'lardi.
    """
    if user_id == referrer_id:
        return False
    with get_conn() as conn:
        row = conn.execute(
            "SELECT referred_by, created_at FROM users WHERE user_id = ?",
            (user_id,)).fetchone()
        if row is None or row["referred_by"] is not None:
            return False
        if not conn.execute("SELECT 1 FROM users WHERE user_id = ?",
                            (referrer_id,)).fetchone():
            return False
        has_data = conn.execute(
            "SELECT 1 FROM transactions WHERE user_id = ? LIMIT 1", (user_id,)).fetchone()
        if has_data:
            return False
        conn.execute("UPDATE users SET referred_by = ? WHERE user_id = ?",
                     (referrer_id, user_id))
        return True


def add_bonus_days(user_id: int, days: int) -> datetime:
    """Bonus kunlarni amaldagi muddat ustiga qo'shadi (sinov yoki obuna)."""
    now = datetime.now(config.TZ)
    with get_conn() as conn:
        row = conn.execute(
            "SELECT trial_ends_at, subscribed_until, bonus_days FROM users "
            "WHERE user_id = ?", (user_id,)).fetchone()
        if row is None:
            return now
        sub = _parse_dt(row["subscribed_until"])
        if sub and sub > now:
            until = sub + timedelta(days=days)
            conn.execute("UPDATE users SET subscribed_until = ?, bonus_days = ? "
                         "WHERE user_id = ?",
                         (until.isoformat(timespec="seconds"),
                          (row["bonus_days"] or 0) + days, user_id))
        else:
            trial = _parse_dt(row["trial_ends_at"])
            base = trial if trial and trial > now else now
            until = base + timedelta(days=days)
            conn.execute("UPDATE users SET trial_ends_at = ?, bonus_days = ?, "
                         "warned_stage = 0 WHERE user_id = ?",
                         (until.isoformat(timespec="seconds"),
                          (row["bonus_days"] or 0) + days, user_id))
        return until


def referral_stats(user_id: int) -> dict:
    with get_conn() as conn:
        invited = int(conn.execute(
            "SELECT COUNT(*) FROM users WHERE referred_by = ?", (user_id,)).fetchone()[0])
        bonus = conn.execute(
            "SELECT bonus_days FROM users WHERE user_id = ?", (user_id,)).fetchone()
    return {"invited": invited, "bonus_days": (bonus["bonus_days"] if bonus else 0) or 0}


# --------------------------------------------------------------------------- #
# Byudjet
# --------------------------------------------------------------------------- #

def set_budget(user_id: int, category: str, amount: float, currency: str = "som") -> None:
    with get_conn() as conn:
        conn.execute(
            """INSERT INTO budgets (user_id, category, amount, currency)
               VALUES (?, ?, ?, ?)
               ON CONFLICT(user_id, category, currency)
               DO UPDATE SET amount = excluded.amount, notified = ''""",
            (user_id, category, float(amount), currency))


def delete_budget(user_id: int, category: str, currency: str = "som") -> bool:
    with get_conn() as conn:
        cur = conn.execute(
            "DELETE FROM budgets WHERE user_id = ? AND category = ? AND currency = ?",
            (user_id, category, currency))
        return cur.rowcount > 0


def list_budgets(user_id: int) -> list[sqlite3.Row]:
    with get_conn() as conn:
        return conn.execute(
            "SELECT * FROM budgets WHERE user_id = ? ORDER BY category", (user_id,)
        ).fetchall()


def budget_status(user_id: int) -> list[dict]:
    """Har bir byudjet bo'yicha shu oyda qancha sarflanganini qaytaradi."""
    today = datetime.now(config.TZ).date()
    start = today.replace(day=1).isoformat()
    out = []
    with get_conn() as conn:
        for b in conn.execute("SELECT * FROM budgets WHERE user_id = ?",
                              (user_id,)).fetchall():
            spent = float(conn.execute(
                """SELECT COALESCE(SUM(amount), 0) FROM transactions
                   WHERE user_id = ? AND kind = ? AND category = ? AND currency = ?
                     AND occurred_on >= ?""",
                (user_id, config.KIND_CHIQIM, b["category"], b["currency"], start)
            ).fetchone()[0])
            limit = float(b["amount"])
            out.append({
                "category": b["category"], "limit": limit, "spent": spent,
                "currency": b["currency"],
                "percent": round(100 * spent / limit, 1) if limit else 0.0,
                "left": limit - spent,
                "notified": b["notified"] or "",
            })
    return sorted(out, key=lambda x: -x["percent"])


def mark_budget_notified(user_id: int, category: str, currency: str, tag: str) -> None:
    with get_conn() as conn:
        conn.execute(
            "UPDATE budgets SET notified = ? WHERE user_id = ? AND category = ? "
            "AND currency = ?", (tag, user_id, category, currency))


# --------------------------------------------------------------------------- #
# Eslatmalar va muddat ogohlantirishi
# --------------------------------------------------------------------------- #

def has_consent(user_id: int, version: str) -> bool:
    """Foydalanuvchi shartlarning shu versiyasiga rozi bo'lganmi."""
    with get_conn() as conn:
        row = conn.execute(
            "SELECT consent_at, consent_version FROM users WHERE user_id = ?",
            (user_id,)).fetchone()
    return bool(row and row["consent_at"] and row["consent_version"] == version)


def set_consent(user_id: int, version: str) -> None:
    with get_conn() as conn:
        conn.execute(
            "UPDATE users SET consent_at = ?, consent_version = ? WHERE user_id = ?",
            (_now_local(), version, user_id))


def tx_count(user_id: int) -> int:
    """Foydalanuvchining jami yozuvlari soni — barcha qatorni o'qimasdan."""
    with get_conn() as conn:
        return int(conn.execute(
            "SELECT COUNT(*) FROM transactions WHERE user_id = ?",
            (user_id,)).fetchone()[0])


def touch_streak(user_id: int) -> dict:
    """Yozuv qo'shilganda ketma-ket kunlar hisobini yangilaydi.

    Qaytaradi: {"streak", "best", "grew"} — `grew` bugun birinchi yozuv
    bo'lgani va zanjir uzunlashganini bildiradi.
    """
    today = datetime.now(config.TZ).date()
    with get_conn() as conn:
        row = conn.execute(
            "SELECT streak, best_streak, last_entry_day FROM users WHERE user_id = ?",
            (user_id,)).fetchone()
        if row is None:
            return {"streak": 0, "best": 0, "grew": False}

        last = row["last_entry_day"]
        streak = row["streak"] or 0
        best = row["best_streak"] or 0

        if last == today.isoformat():
            return {"streak": streak, "best": best, "grew": False}

        yesterday = (today - timedelta(days=1)).isoformat()
        # Kecha ham yozgan bo'lsa zanjir davom etadi, aks holda yangidan boshlanadi.
        streak = streak + 1 if last == yesterday else 1
        best = max(best, streak)
        conn.execute(
            "UPDATE users SET streak = ?, best_streak = ?, last_entry_day = ? "
            "WHERE user_id = ?", (streak, best, today.isoformat(), user_id))
    return {"streak": streak, "best": best, "grew": True}


def users_for_winback(days: int = 7) -> list[dict]:
    """Bir muddat yozmagan, lekin kirish huquqi bor foydalanuvchilar.

    Har bir odamga oyiga bir martadan ko'p yozmaymiz — bezdirmaslik uchun.
    """
    now = datetime.now(config.TZ)
    cutoff = (now - timedelta(days=days)).date().isoformat()
    month_ago = (now - timedelta(days=30)).isoformat()
    out = []
    with get_conn() as conn:
        rows = conn.execute(
            """SELECT u.*, (SELECT MAX(occurred_on) FROM transactions t
                            WHERE t.user_id = u.user_id) AS last_tx
               FROM users u WHERE u.blocked = 0""").fetchall()
    for r in rows:
        if r["user_id"] in config.OWNER_IDS:
            continue
        sub = _parse_dt(r["subscribed_until"])
        trial = _parse_dt(r["trial_ends_at"])
        if not ((sub and sub > now) or (trial and trial > now)):
            continue                      # muddati tugaganlarga alohida xabar bor
        if not r["last_tx"] or r["last_tx"] > cutoff:
            continue                      # yaqinda yozgan
        if r["winback_at"] and r["winback_at"] > month_ago:
            continue                      # yaqinda eslatilgan
        out.append({"user_id": r["user_id"], "first_name": r["first_name"],
                    "last_tx": r["last_tx"], "streak": r["best_streak"] or 0})
    return out


# --------------------------------------------------------------------------- #
# Shaxsiy jamg'arma
# --------------------------------------------------------------------------- #

def savings_balance(user_id: int) -> float:
    """Jamg'armadagi joriy qoldiq: qo'yilgani minus yechilgani.

    Asosiy valyutada (`amount_base`) — dollarda qo'yib so'mda yechilgan
    bo'lsa ham bitta sonda ko'rinsin.
    """
    with get_conn() as conn:
        row = conn.execute(
            """SELECT COALESCE(SUM(CASE WHEN kind = ? THEN COALESCE(amount_base, amount)
                                        ELSE -COALESCE(amount_base, amount) END), 0)
               FROM transactions WHERE user_id = ? AND kind IN (?, ?)""",
            (config.KIND_JAMGARMA, user_id,
             config.KIND_JAMGARMA, config.KIND_JAMGARMA_YECHDIM)).fetchone()
    return round(float(row[0] or 0), 2)


def savings_in_period(user_id: int, start: date, end: date) -> float:
    """Shu oraliqda jamg'armaga QO'SHILGAN sof summa."""
    with get_conn() as conn:
        row = conn.execute(
            """SELECT COALESCE(SUM(CASE WHEN kind = ? THEN COALESCE(amount_base, amount)
                                        ELSE -COALESCE(amount_base, amount) END), 0)
               FROM transactions
               WHERE user_id = ? AND kind IN (?, ?)
                 AND occurred_on BETWEEN ? AND ?""",
            (config.KIND_JAMGARMA, user_id,
             config.KIND_JAMGARMA, config.KIND_JAMGARMA_YECHDIM,
             start.isoformat(), end.isoformat())).fetchone()
    return round(float(row[0] or 0), 2)


def income_in_period(user_id: int, start: date, end: date) -> float:
    with get_conn() as conn:
        row = conn.execute(
            """SELECT COALESCE(SUM(COALESCE(amount_base, amount)), 0)
               FROM transactions
               WHERE user_id = ? AND kind = ? AND occurred_on BETWEEN ? AND ?""",
            (user_id, config.KIND_KIRIM,
             start.isoformat(), end.isoformat())).fetchone()
    return round(float(row[0] or 0), 2)


def savings_by_month(user_id: int, months: int = 24) -> list[dict]:
    """Oylar kesimida daromad va sof jamg'arma, yangisidan eskisiga.

    Seriya (ketma-ket necha oy 10 % jamg'argan) va yillik xulosa shu
    yerdan chiqadi — ikkalasi uchun alohida so'rov yozishning hojati yo'q.
    """
    with get_conn() as conn:
        rows = conn.execute(
            """SELECT substr(occurred_on, 1, 7) AS oy,
                      COALESCE(SUM(CASE WHEN kind = ?
                                        THEN COALESCE(amount_base, amount) END), 0) AS kirim,
                      COALESCE(SUM(CASE WHEN kind = ?
                                        THEN COALESCE(amount_base, amount)
                                        WHEN kind = ?
                                        THEN -COALESCE(amount_base, amount) END), 0) AS jamgarma
               FROM transactions
               WHERE user_id = ? AND kind IN (?, ?, ?)
               GROUP BY oy ORDER BY oy DESC LIMIT ?""",
            (config.KIND_KIRIM, config.KIND_JAMGARMA, config.KIND_JAMGARMA_YECHDIM,
             user_id, config.KIND_KIRIM, config.KIND_JAMGARMA,
             config.KIND_JAMGARMA_YECHDIM, months)).fetchall()
    return [{"oy": r["oy"], "kirim": float(r["kirim"] or 0),
             "jamgarma": float(r["jamgarma"] or 0)} for r in rows]


def savings_streak(user_id: int) -> int:
    """Ketma-ket necha oy 10 % qoidasi bajarilgan.

    Joriy oy hali tugamagani uchun u seriyani UZMAYDI: bajarilgan
    bo'lsa qo'shiladi, bajarilmagan bo'lsa shunchaki e'tiborga
    olinmaydi. Aks holda har oyning 1-sanasida seriya nolga tushib,
    butun mexanika ma'nosini yo'qotardi.

    Daromadi bo'lmagan oy ham uzmaydi: daromad kelmagan oyda 10 %
    jamg'ara olmaslik odamning aybi emas.
    """
    this_month = datetime.now(config.TZ).strftime("%Y-%m")
    rate = savings_rate(user_id)
    streak = 0
    for row in savings_by_month(user_id):
        ok = row["kirim"] > 0 and row["jamgarma"] >= row["kirim"] * rate
        if row["oy"] == this_month:
            if ok:
                streak += 1
            continue                      # tugamagan oy seriyani uzmaydi
        if row["kirim"] <= 0:
            continue                      # daromadsiz oy ham uzmaydi
        if not ok:
            break
        streak += 1
    return streak


def net_worth(user_id: int) -> dict:
    """Sof qiymat: jamg'arma + menga qarzdorlar − mening qarzim.

    Bot boshqa hamma joyda OQIM ko'rsatadi (bu oy qancha kirdi/chiqdi).
    Bu esa TO'PLANMA — «hozir qanday holatdaman» degan savolga javob.
    Kitobning butun mavzusi aynan shu.
    """
    saving = savings_balance(user_id)
    berdim = oldim = 0.0
    for r in open_debts(user_id):
        amount = float(r["amount_base"] if r["amount_base"] is not None else r["amount"])
        if r["kind"] == config.KIND_QARZ_BERDIM:
            berdim += amount              # menga qaytariladi — aktiv
        else:
            oldim += amount               # men qaytaraman — passiv
    return {"savings": saving, "owed_to_me": round(berdim, 2),
            "i_owe": round(oldim, 2),
            "total": round(saving + berdim - oldim, 2)}


def debt_plan(user_id: int) -> dict | None:
    """Qarzdan chiqish rejasi — kitobdagi Dabasir usuli (70/20/10).

    Daromadning 20 % i qarzga ajratilsa necha oyda uziladi. Daromad yoki
    ochiq qarz bo'lmasa reja ham bo'lmaydi (None) — o'ylab topilgan
    raqam berilmaydi.

    Daromad oxirgi 90 kunning o'rtachasidan olinadi: bitta oyning
    tasodifiy katta yoki kichik daromadi rejani buzmasin.
    """
    worth = net_worth(user_id)
    debt = worth["i_owe"]
    if debt <= 0:
        return None

    end = datetime.now(config.TZ).date()
    start = end - timedelta(days=89)
    income = income_in_period(user_id, start, end) / 3
    if income <= 0:
        return None

    monthly = income * 0.20
    return {"debt": debt, "income": round(income, 2),
            "monthly": round(monthly, 2),
            "months": max(1, math.ceil(debt / monthly))}


def savings_profile(user_id: int) -> dict:
    """Jamg'arma odati holati. Yozuv bo'lmasa bo'sh holat qaytadi."""
    with get_conn() as conn:
        row = conn.execute(
            "SELECT * FROM savings_profile WHERE user_id = ?", (user_id,)).fetchone()
    if row:
        return dict(row)
    return {"user_id": user_id, "card_state": CARD_SORALMAGAN, "asked_at": None,
            "answered_at": None, "nudged_at": None, "reminded_month": "",
            "savings_rate": 0.0, "goal": 0.0, "goal_note": "",
            "goal_reached_at": None}


def savings_rate(user_id: int) -> float:
    """Shu odamning jamg'arma foizi (0.10 = 10 %).

    Sozlanmagan bo'lsa umumiy standart qaytadi. Nol saqlash «standart»
    degani: keyin standart o'zgarsa, uni ataylab o'zgartirmaganlarga
    yangi qiymat o'zi tegadi.
    """
    with get_conn() as conn:
        row = conn.execute(
            "SELECT savings_rate FROM savings_profile WHERE user_id = ?",
            (user_id,)).fetchone()
    value = float(row[0]) if row and row[0] else 0.0
    return value if value > 0 else config.SAVINGS_RATE


def set_savings_rate(user_id: int, rate: float) -> None:
    """Foizni saqlaydi. 0 — standartga qaytarish."""
    with get_conn() as conn:
        _upsert_profile(conn, user_id, savings_rate=float(rate))


def set_savings_goal(user_id: int, amount: float, note: str = "") -> None:
    with get_conn() as conn:
        _upsert_profile(conn, user_id, goal=float(amount), goal_note=note,
                        goal_reached_at=None)


def mark_goal_reached(user_id: int) -> None:
    now = datetime.now(config.TZ).isoformat(timespec="seconds")
    with get_conn() as conn:
        _upsert_profile(conn, user_id, goal_reached_at=now)


def _upsert_profile(conn, user_id: int, **fields) -> None:
    cols = ", ".join(fields)
    marks = ", ".join("?" for _ in fields)
    sets = ", ".join(f"{k} = excluded.{k}" for k in fields)
    conn.execute(
        f"INSERT INTO savings_profile (user_id, {cols}) VALUES (?, {marks}) "
        f"ON CONFLICT(user_id) DO UPDATE SET {sets}",
        (user_id, *fields.values()))


def set_savings_card(user_id: int, state: str) -> None:
    """Alohida karta bor/yo'q javobini yozadi."""
    if state not in (CARD_SORALMAGAN, CARD_YOQ, CARD_BOR):
        raise ValueError(state)
    now = datetime.now(config.TZ).isoformat(timespec="seconds")
    with get_conn() as conn:
        _upsert_profile(conn, user_id, card_state=state, answered_at=now,
                        nudged_at=now)


def mark_card_asked(user_id: int) -> None:
    now = datetime.now(config.TZ).isoformat(timespec="seconds")
    with get_conn() as conn:
        _upsert_profile(conn, user_id, asked_at=now, nudged_at=now)


def mark_month_reminded(user_id: int, month: str) -> None:
    with get_conn() as conn:
        _upsert_profile(conn, user_id, reminded_month=month)


def users_for_savings_reminder() -> list[dict]:
    """Oy oxiridagi jamg'arma eslatmasi kimlarga ketadi.

    Kirish huquqi borlar olinadi. Har biriga o'sha oydagi daromadi,
    jamg'armasi va karta holati qo'shiladi — xabar shaxsiy bo'lsin.
    Umumiy «jamg'aring» degan matn jamg'arayotgan odam uchun shovqin,
    jamg'armayotgan odam uchun esa juda mavhum.
    """
    now = datetime.now(config.TZ)
    first = now.date().replace(day=1)
    today_ = now.date()
    month = now.strftime("%Y-%m")

    with get_conn() as conn:
        rows = conn.execute("SELECT * FROM users WHERE blocked = 0").fetchall()
        profiles = {r["user_id"]: dict(r) for r in conn.execute(
            "SELECT * FROM savings_profile").fetchall()}

    out = []
    for r in rows:
        uid = r["user_id"]
        sub = _parse_dt(r["subscribed_until"])
        trial = _parse_dt(r["trial_ends_at"])
        if uid not in config.OWNER_IDS and not (
                (sub and sub > now) or (trial and trial > now)):
            continue
        prof = profiles.get(uid) or {}
        if (prof.get("reminded_month") or "") == month:
            continue                       # shu oy allaqachon yuborilgan

        income = income_in_period(uid, first, today_)
        saved = savings_in_period(uid, first, today_)
        # Qoidani bajargan odamga «jamg'ar» deb yozish eslatmani
        # shovqinga aylantiradi — u chetda qoladi. Bajarilganini u
        # oylik hisobotdagi «Bobil bahosi» dan ko'radi.
        rate = savings_rate(uid)
        if income > 0 and saved >= income * rate:
            continue
        out.append({
            "user_id": uid,
            "lang": r["lang"] or "uz",
            "card_state": prof.get("card_state") or CARD_SORALMAGAN,
            "income": income,
            "saved": saved,
            "rate": rate,
            "balance": savings_balance(uid),
        })
    return out


def users_for_digest() -> list[dict]:
    """Haftalik xulosa yuboriladiganlar: kirish huquqi bor, bloklanmaganlar.

    Yozuvi bo'lmaganlarga xulosa yuborilmaydi — buni chaqiruvchi
    `week_summary` natijasi bo'yicha hal qiladi.
    """
    now = datetime.now(config.TZ)
    out = []
    with get_conn() as conn:
        rows = conn.execute("SELECT * FROM users WHERE blocked = 0").fetchall()
    for r in rows:
        sub = _parse_dt(r["subscribed_until"])
        trial = _parse_dt(r["trial_ends_at"])
        if r["user_id"] in config.OWNER_IDS or (sub and sub > now) \
                or (trial and trial > now):
            out.append({"user_id": r["user_id"], "streak": r["streak"] or 0})
    return out


def mark_winback(user_id: int) -> None:
    with get_conn() as conn:
        conn.execute("UPDATE users SET winback_at = ? WHERE user_id = ?",
                     (_now_local(), user_id))


def week_summary(user_id: int) -> dict:
    """Haftalik xulosa: shu hafta va o'tgan hafta taqqoslamasi."""
    today = datetime.now(config.TZ).date()
    this_start = today - timedelta(days=today.weekday())
    prev_start = this_start - timedelta(days=7)
    prev_end = this_start - timedelta(days=1)

    def spent(start, end):
        with get_conn() as conn:
            return float(conn.execute(
                "SELECT COALESCE(SUM(amount_base), 0) FROM transactions "
                "WHERE user_id = ? AND kind = ? AND occurred_on BETWEEN ? AND ?",
                (user_id, config.KIND_CHIQIM, start.isoformat(), end.isoformat())
            ).fetchone()[0])

    now_spent = spent(this_start, today)
    was_spent = spent(prev_start, prev_end)
    top = by_category_unified(user_id, this_start, today, config.KIND_CHIQIM)
    with get_conn() as conn:
        count = int(conn.execute(
            "SELECT COUNT(*) FROM transactions WHERE user_id = ? "
            "AND occurred_on BETWEEN ? AND ?",
            (user_id, this_start.isoformat(), today.isoformat())).fetchone()[0])
    return {"spent": now_spent, "previous": was_spent, "count": count,
            "top": top[:3], "start": this_start, "end": today}


def get_lang(user_id: int) -> str:
    with get_conn() as conn:
        row = conn.execute("SELECT lang FROM users WHERE user_id = ?",
                           (user_id,)).fetchone()
        return (row["lang"] if row and row["lang"] else "uz")


def set_lang(user_id: int, lang: str) -> None:
    with get_conn() as conn:
        conn.execute("UPDATE users SET lang = ? WHERE user_id = ?", (lang, user_id))


def set_reminder_hour(user_id: int, hour: int | None) -> None:
    with get_conn() as conn:
        conn.execute("UPDATE users SET reminder_hour = ? WHERE user_id = ?",
                     (hour, user_id))


def get_reminder_hour(user_id: int) -> int | None:
    with get_conn() as conn:
        row = conn.execute("SELECT reminder_hour FROM users WHERE user_id = ?",
                           (user_id,)).fetchone()
        return row["reminder_hour"] if row else None


def users_for_reminder(hour: int) -> list[int]:
    """Shu soatga eslatma buyurgan va kirish huquqi bor foydalanuvchilar."""
    now = datetime.now(config.TZ)
    out = []
    with get_conn() as conn:
        for r in conn.execute(
                "SELECT * FROM users WHERE reminder_hour = ? AND blocked = 0",
                (hour,)).fetchall():
            if r["user_id"] in config.OWNER_IDS:
                out.append(r["user_id"])
                continue
            sub = _parse_dt(r["subscribed_until"])
            trial = _parse_dt(r["trial_ends_at"])
            if (sub and sub > now) or (trial and trial > now):
                out.append(r["user_id"])
    return out


def users_expiring(stages: tuple[int, ...] = (3, 1)) -> list[dict]:
    """Muddati tugashiga `stages` kun qolganlar. Har daraja bir marta.

    `warned_stage` — oxirgi yuborilgan ogohlantirish darajasi. Muddat
    uzaytirilsa nolga qaytariladi, shunda keyingi safar yana yuboriladi.
    """
    now = datetime.now(config.TZ)
    out = []
    with get_conn() as conn:
        for r in conn.execute("SELECT * FROM users WHERE blocked = 0").fetchall():
            if r["user_id"] in config.OWNER_IDS:
                continue
            sub = _parse_dt(r["subscribed_until"])
            trial = _parse_dt(r["trial_ends_at"])
            if sub and sub > now:
                expires, kind = sub, "obuna"
            elif trial and trial > now:
                expires, kind = trial, "sinov"
            else:
                continue
            # Yuqoriga yaxlitlaymiz: 1 kun 23 soat qolgan bo'lsa bu «2 kun»,
            # «1 kun» emas. Aks holda aynan 2 kunda 3 kunlik ogohlantirish
            # o'tkazib yuborilib, 1 kunligi erta ketardi.
            seconds = (expires - now).total_seconds()
            left = max(0, math.ceil(seconds / 86400))
            stage = next((s for s in sorted(stages) if left <= s), None)
            if stage is None:
                continue
            already = r["warned_stage"] or 0
            # Kichikroq daraja = shoshilinchroq. Faqat yangi darajada yuboramiz.
            if already and stage >= already:
                continue
            out.append({"user_id": r["user_id"], "first_name": r["first_name"],
                        "kind": kind, "days_left": left, "stage": stage,
                        "expires_at": expires})
    return out


def mark_warned(user_id: int, stage: int) -> None:
    with get_conn() as conn:
        conn.execute("UPDATE users SET warned_stage = ? WHERE user_id = ?",
                     (stage, user_id))


def day_summary(user_id: int, day: date) -> dict:
    """Kunlik eslatma uchun qisqa jamlanma."""
    with get_conn() as conn:
        rows = conn.execute(
            """SELECT kind, currency, COUNT(*) n, COALESCE(SUM(amount), 0) s
               FROM transactions WHERE user_id = ? AND occurred_on = ?
               GROUP BY kind, currency""",
            (user_id, day.isoformat())).fetchall()
    total = {"count": 0, "chiqim": {}, "kirim": {}}
    for r in rows:
        total["count"] += r["n"]
        if r["kind"] == config.KIND_CHIQIM:
            total["chiqim"][r["currency"]] = float(r["s"])
        elif r["kind"] == config.KIND_KIRIM:
            total["kirim"][r["currency"]] = float(r["s"])
    return total


# --------------------------------------------------------------------------- #
# Foydalanuvchi ma'lumotini butunlay o'chirish (M-2)
# --------------------------------------------------------------------------- #

def erase_user(user_id: int) -> dict:
    """Foydalanuvchining butun izini o'chiradi. Qaytarib bo'lmaydi."""
    with get_conn() as conn:
        tx = conn.execute("DELETE FROM transactions WHERE user_id = ?",
                          (user_id,)).rowcount
        usage = conn.execute("DELETE FROM usage_log WHERE user_id = ?",
                             (user_id,)).rowcount
        conn.execute("DELETE FROM budgets WHERE user_id = ?", (user_id,))
        conn.execute("DELETE FROM savings_profile WHERE user_id = ?", (user_id,))
        conn.execute("DELETE FROM receipts WHERE user_id = ?", (user_id,))
        conn.execute("DELETE FROM subscription_requests WHERE user_id = ?", (user_id,))
        # Taklif qilganlar zanjiri uzilmasin — havola bo'sh qoladi.
        conn.execute("UPDATE users SET referred_by = NULL WHERE referred_by = ?",
                     (user_id,))
        conn.execute("DELETE FROM users WHERE user_id = ?", (user_id,))
        conn.execute("DELETE FROM entry_counts WHERE user_id = ?", (user_id,))
        conn.execute("DELETE FROM private_erase_queue WHERE user_id = ?", (user_id,))
    return {"transactions": tx, "usage": usage}


def drain_erase_queue() -> int:
    """Admin panel so'ragan o'chirishlarni bajaradi.

    Panelda shaxsiy bazaning kaliti yo'q, shuning uchun u foydalanuvchini
    o'chirganda yozuvlarini o'zi o'chira olmaydi — navbatga qo'yadi.
    Botning soatlik vazifasi va har ishga tushishi shu navbatni bo'shatadi.

    Qaytaradi: nechta foydalanuvchi tozalangani.
    """
    with get_conn() as conn:
        ids = [r["user_id"] for r in conn.execute(
            "SELECT user_id FROM private_erase_queue WHERE done_at IS NULL")]
        for uid in ids:
            conn.execute("DELETE FROM transactions WHERE user_id = ?", (uid,))
            conn.execute("DELETE FROM budgets WHERE user_id = ?", (uid,))
            conn.execute("DELETE FROM savings_profile WHERE user_id = ?", (uid,))
            conn.execute("DELETE FROM receipts WHERE user_id = ?", (uid,))
            conn.execute("DELETE FROM entry_counts WHERE user_id = ?", (uid,))
        # Navbat qatorining o'zi ham qoldirilmaydi: unda foydalanuvchi
        # id si turadi, ya'ni u ham iz.
        conn.execute("DELETE FROM private_erase_queue WHERE done_at IS NULL")
    return len(ids)


def set_blocked(user_id: int, blocked: bool) -> bool:
    with get_conn() as conn:
        cur = conn.execute("UPDATE users SET blocked = ? WHERE user_id = ?",
                           (1 if blocked else 0, user_id))
        return cur.rowcount > 0


def list_users(limit: int = 50) -> list[sqlite3.Row]:
    with get_conn() as conn:
        return conn.execute(
            "SELECT * FROM users ORDER BY last_seen_at DESC NULLS LAST LIMIT ?",
            (limit,),
        ).fetchall()


# --------------------------------------------------------------------------- #
# Token sarfi va kunlik limitlar
# --------------------------------------------------------------------------- #

def usage_begin(user_id: int, operation: str) -> int:
    """Amaldan OLDIN joy band qiladi va qator id'sini qaytaradi.

    Limit shu jadval bo'yicha sanalgani uchun band qilish chaqiruvdan oldin
    bo'lishi kerak — aks holda bir vaqtda yuborilgan ko'p so'rov limitni
    aylanib o'tib ketardi."""
    with get_conn() as conn:
        cur = conn.execute(
            "INSERT INTO usage_log (user_id, day, operation) VALUES (?, ?, ?)",
            (user_id, _today_str(), operation),
        )
        return int(cur.lastrowid)


def usage_finish(usage_id: int, usage: dict | None) -> None:
    """Chaqiruv tugagach haqiqiy token sarfini yozadi."""
    if not usage:
        return
    with get_conn() as conn:
        conn.execute(
            """UPDATE usage_log SET model = ?, input_tokens = ?, output_tokens = ?,
                   cache_read = ?, cache_write = ?, cost_usd = ?
               WHERE id = ?""",
            (usage.get("model", ""), usage.get("input_tokens", 0),
             usage.get("output_tokens", 0), usage.get("cache_read", 0),
             usage.get("cache_write", 0), usage.get("cost_usd", 0.0), usage_id),
        )


def usage_cancel(usage_id: int) -> None:
    """Amal bajarilmagan bo'lsa (xatolik, tushunarsiz xabar) bandlikni bekor
    qiladi — foydalanuvchi bekorga limitini yo'qotmasin."""
    with get_conn() as conn:
        conn.execute("DELETE FROM usage_log WHERE id = ? AND cost_usd = 0", (usage_id,))


def count_today(user_id: int, operation: str) -> int:
    with get_conn() as conn:
        row = conn.execute(
            "SELECT COUNT(*) AS n FROM usage_log WHERE user_id = ? AND day = ? AND operation = ?",
            (user_id, _today_str(), operation),
        ).fetchone()
        return int(row["n"])


def month_cost() -> float:
    """Shu oyning boshidan beri butun tizim bo'yicha AI sarfi ($).

    Kalendar oy bo'yicha — Anthropic hisobi ham shunday hisoblanadi,
    shuning uchun panel va konsoldagi son bir-biriga mos keladi.
    """
    start = _now().date().replace(day=1).isoformat()
    with get_conn() as conn:
        return float(conn.execute(
            "SELECT COALESCE(SUM(cost_usd), 0) FROM usage_log WHERE day >= ?",
            (start,)).fetchone()[0])


def usage_summary(user_id: int | None = None, days: int = 30) -> dict:
    """Sarf hisoboti. user_id berilmasa — butun tizim bo'yicha."""
    since = (_now() - timedelta(days=days)).date().isoformat()
    where = "day >= ?"
    params: list = [since]
    if user_id is not None:
        where += " AND user_id = ?"
        params.append(user_id)
    with get_conn() as conn:
        total = conn.execute(
            f"""SELECT COUNT(*) AS calls, COALESCE(SUM(cost_usd),0) AS cost,
                       COALESCE(SUM(input_tokens),0) AS inp,
                       COALESCE(SUM(output_tokens),0) AS out,
                       COALESCE(SUM(cache_read),0) AS cread
                FROM usage_log WHERE {where}""",
            params,
        ).fetchone()
        by_op = conn.execute(
            f"""SELECT operation, COUNT(*) AS calls, COALESCE(SUM(cost_usd),0) AS cost
                FROM usage_log WHERE {where} GROUP BY operation ORDER BY cost DESC""",
            params,
        ).fetchall()
        return {
            "days": days,
            "calls": int(total["calls"]),
            "cost_usd": float(total["cost"]),
            "input_tokens": int(total["inp"]),
            "output_tokens": int(total["out"]),
            "cache_read": int(total["cread"]),
            "by_operation": [
                {"operation": r["operation"], "calls": int(r["calls"]), "cost_usd": float(r["cost"])}
                for r in by_op
            ],
        }


def top_spenders(days: int = 30, limit: int = 10) -> list[dict]:
    since = (_now() - timedelta(days=days)).date().isoformat()
    with get_conn() as conn:
        rows = conn.execute(
            """SELECT u.user_id, u.first_name, u.username,
                      COUNT(*) AS calls, COALESCE(SUM(l.cost_usd),0) AS cost
               FROM usage_log l LEFT JOIN users u ON u.user_id = l.user_id
               WHERE l.day >= ? GROUP BY l.user_id ORDER BY cost DESC LIMIT ?""",
            (since, limit),
        ).fetchall()
        return [
            {"user_id": r["user_id"], "first_name": r["first_name"] or "",
             "username": r["username"], "calls": int(r["calls"]), "cost_usd": float(r["cost"])}
            for r in rows
        ]


def user_count() -> dict:
    with get_conn() as conn:
        now_iso = _now().isoformat()
        r = conn.execute(
            """SELECT COUNT(*) AS total,
                      SUM(CASE WHEN blocked = 1 THEN 1 ELSE 0 END) AS blocked,
                      SUM(CASE WHEN subscribed_until > ? THEN 1 ELSE 0 END) AS subscribed,
                      SUM(CASE WHEN (subscribed_until IS NULL OR subscribed_until <= ?)
                                AND trial_ends_at > ? THEN 1 ELSE 0 END) AS trial
               FROM users""",
            (now_iso, now_iso, now_iso),
        ).fetchone()
        return {"total": int(r["total"] or 0), "blocked": int(r["blocked"] or 0),
                "subscribed": int(r["subscribed"] or 0), "trial": int(r["trial"] or 0)}


def rows_for_ai(user_id: int, limit: int) -> list[sqlite3.Row]:
    """Savolga javob berish uchun oxirgi yozuvlar (eng yangilari birinchi olinadi)."""
    with get_conn() as conn:
        cur = conn.execute(
            "SELECT * FROM transactions WHERE user_id = ? ORDER BY occurred_on DESC, id DESC LIMIT ?",
            (user_id, limit),
        )
        return list(reversed(cur.fetchall()))
