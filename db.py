"""SQLite bilan ishlash qatlami. Bitta foydalanuvchi uchun mo'ljallangan, lekin
user_id bo'yicha ajratilgan — kerak bo'lsa bir nechta odam ishlatishi mumkin."""

from __future__ import annotations

import math
import sqlite3
from contextlib import contextmanager
from datetime import date, datetime, timedelta, timezone
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
    amount_base  REAL,
    -- Jamg'arma qaysi maqsadga (goals.id). Bo'sh — asosiy maqsadga.
    goal_id      INTEGER,
    -- Qarzni qaytarish muddati (YYYY-MM-DD) — eslatma uchun.
    due_on       TEXT,
    -- Qaytarish yozuvi qaysi qarzni qaytaryapti (transactions.id).
    -- Bo'sh — ism bo'yicha avtomatik taqsimlanadi (open_debts).
    repays_id    INTEGER
);

CREATE INDEX IF NOT EXISTS shaxsiy.idx_tx_user_date
    ON transactions(user_id, occurred_on);
CREATE INDEX IF NOT EXISTS shaxsiy.idx_tx_user_kind
    ON transactions(user_id, kind);
CREATE INDEX IF NOT EXISTS shaxsiy.idx_tx_receipt
    ON transactions(user_id, receipt_id);

-- Jamg'arma maqsadlari (goals.py). Bir odamda bir nechta bo'lishi
-- mumkin; yig'ilgan summa saqlanmaydi, jamg'arma yozuvlaridan hisoblanadi.
CREATE TABLE IF NOT EXISTS shaxsiy.goals (
    id         INTEGER PRIMARY KEY AUTOINCREMENT,
    user_id    INTEGER NOT NULL,
    name       TEXT    NOT NULL,
    amount     REAL    NOT NULL,
    deadline   TEXT,
    created_at TEXT    NOT NULL DEFAULT (datetime('now')),
    reached_at TEXT,
    archived   INTEGER NOT NULL DEFAULT 0
);

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

-- Foydalanuvchi tuzatishlaridan o'rganilgan kategoriyalar (learning.py).
-- «suv» -> oziq-ovqat: keyingi «suv» yozuvlarida AI javobidan ustun.
CREATE TABLE IF NOT EXISTS shaxsiy.category_rules (
    user_id    INTEGER NOT NULL,
    keyword    TEXT    NOT NULL,
    kind       TEXT    NOT NULL,
    category   TEXT    NOT NULL,
    updated_at TEXT    NOT NULL DEFAULT (datetime('now')),
    PRIMARY KEY (user_id, keyword, kind)
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
    # 3-bosqich: bir nechta maqsad, qarz muddati.
    ("savings_profile", "primary_goal_id",
     "ALTER TABLE shaxsiy.savings_profile ADD COLUMN primary_goal_id INTEGER"),
    # Eski yagona maqsad goals jadvaliga nusxalanganmi (goals._import_legacy).
    ("savings_profile", "goals_imported",
     "ALTER TABLE shaxsiy.savings_profile ADD COLUMN goals_imported INTEGER NOT NULL DEFAULT 0"),
    ("transactions", "goal_id",
     "ALTER TABLE shaxsiy.transactions ADD COLUMN goal_id INTEGER"),
    ("transactions", "repays_id",
     "ALTER TABLE shaxsiy.transactions ADD COLUMN repays_id INTEGER"),
    ("transactions", "due_on",
     "ALTER TABLE shaxsiy.transactions ADD COLUMN due_on TEXT"),
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

-- Mahsulot analitikasi uchun hodisalar: start, birinchi yozuv, paywall
-- ko'rsatildi va hokazo. MOLIYAVIY MA'LUMOT YO'Q — faqat hodisa nomi va
-- qisqa izoh (masalan qaysi funksiyada paywall chiqdi). Shuning uchun
-- asosiy bazada: admin panel ham o'qishi mumkin.
CREATE TABLE IF NOT EXISTS events (
    id         INTEGER PRIMARY KEY AUTOINCREMENT,
    user_id    INTEGER NOT NULL,
    name       TEXT    NOT NULL,
    detail     TEXT    NOT NULL DEFAULT '',
    day        TEXT    NOT NULL,
    created_at TEXT    NOT NULL DEFAULT (datetime('now'))
);
CREATE INDEX IF NOT EXISTS idx_events_user ON events(user_id, name, day);
CREATE INDEX IF NOT EXISTS idx_events_name ON events(name, day);

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
    # Ega uchun «oddiy rejim»: o'zini obunasiz foydalanuvchidek ko'radi.
    ("users", "sim_free", "ALTER TABLE users ADD COLUMN sim_free INTEGER NOT NULL DEFAULT 0"),
    # Botni bloklagan (Telegram 403): avtomatik xabar yuborilmaydi. Odam
    # botga yana yozsa tozalanadi (get_or_create_user).
    ("users", "bot_blocked_at", "ALTER TABLE users ADD COLUMN bot_blocked_at TEXT"),
    # Kunlik eslatmani o'zi o'chirgan. Bepul darajada eslatma standart
    # holatda yoqilgan — «hali sozlamagan» va «o'chirgan» farqlanishi kerak.
    ("users", "reminder_off",
     "ALTER TABLE users ADD COLUMN reminder_off INTEGER NOT NULL DEFAULT 0"),
    # Reklama manbasi (/start src_<kanal> yoki «ref»). Faqat birinchi
    # kelganda yoziladi; bo'sh — to'g'ridan-to'g'ri kelgan.
    ("users", "source", "ALTER TABLE users ADD COLUMN source TEXT"),
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
                day = _now().date()
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
    goal_id: int | None = None,
    due_on: str | None = None,
    repays_id: int | None = None,
) -> int:
    # Toshkent sanasi — server boshqa mintaqada bo'lishi mumkin.
    occurred_on = occurred_on or _now().date().isoformat()
    rate, amount_base = _base_of(amount, currency, occurred_on)
    with get_conn() as conn:
        cur = conn.execute(
            """INSERT INTO transactions
               (user_id, kind, amount, category, note, person, occurred_on,
                raw_text, receipt_id, currency, rate, amount_base, goal_id, due_on,
                repays_id)
               VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)""",
            (user_id, kind, float(amount), category, note, person,
             occurred_on, raw_text, receipt_id, currency, rate, amount_base,
             goal_id, due_on, repays_id),
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


def set_due(user_id: int, tx_id: int, due: date | None) -> bool:
    """Qarzni qaytarish muddati (eslatma uchun). None — muddatsiz."""
    with get_conn() as conn:
        cur = conn.execute(
            "UPDATE transactions SET due_on = ? WHERE id = ? AND user_id = ? "
            "AND kind IN (?, ?)",
            (due.isoformat() if due else None, tx_id, user_id,
             config.KIND_QARZ_BERDIM, config.KIND_QARZ_OLDIM))
        return cur.rowcount > 0


def debts_due(days: tuple[date, ...]) -> list[dict]:
    """Muddati shu kunlarga to'g'ri kelgan OCHIQ qarzlar (eslatma uchun).

    Qoldiq open_debts bilan bir xil hisoblanadi: qisman qaytarilgan qarz
    uchun eslatmada qolgan summa aytiladi, to'liq qaytarilgani umuman
    chiqmaydi.
    """
    wanted = {d.isoformat() for d in days}
    with get_conn() as conn:
        users = [r["user_id"] for r in conn.execute(
            "SELECT DISTINCT user_id FROM transactions WHERE due_on IN (%s)"
            % ",".join("?" * len(wanted)), tuple(wanted)).fetchall()]
        # Botni bloklaganlar (Telegram 403) — eslatma yuborilmaydi.
        blocked = {r["user_id"] for r in conn.execute(
            "SELECT user_id FROM users WHERE blocked = 1 OR bot_blocked_at IS NOT NULL")}
    users = [u for u in users if u not in blocked]
    out = []
    for uid in users:
        for d in open_debts(uid):
            if d.get("due_on") in wanted:
                out.append(d)
    return out


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
    group_receipts: bool = False,
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
        totals = {
            r["currency"]: round(float(r["s"]), 2)
            for r in conn.execute(
                f"SELECT currency, SUM(amount) s FROM transactions "
                f"WHERE {clause} GROUP BY currency", params).fetchall()
        }
        if group_receipts:
            # Chek BITTA qator: mahsulotlar receipt_id bo'yicha yig'iladi.
            # Sahifalash ham guruhlar bo'yicha — chek ikki sahifaga
            # bo'linib ketmaydi.
            key = "CASE WHEN t.receipt_id IS NULL THEN 'tx' || t.id ELSE t.receipt_id END"
            source = f"(SELECT * FROM transactions WHERE {clause}) t"
            total = int(conn.execute(
                f"SELECT COUNT(DISTINCT {key}) FROM {source}", params).fetchone()[0])
            items = [dict(r) for r in conn.execute(
                f"""SELECT MAX(t.id) AS id, t.receipt_id, COUNT(*) AS n,
                           SUM(t.amount) AS amount, MAX(t.currency) AS currency,
                           MAX(t.occurred_on) AS occurred_on, MAX(t.kind) AS kind,
                           MAX(t.category) AS category, MAX(t.note) AS note,
                           MAX(t.person) AS person, MAX(t.settled) AS settled,
                           MAX(r.shop) AS shop
                    FROM {source}
                    LEFT JOIN receipts r
                      ON r.user_id = t.user_id AND r.receipt_id = t.receipt_id
                    GROUP BY {key}
                    ORDER BY MAX(t.occurred_on) DESC, MAX(t.id) DESC
                    LIMIT ? OFFSET ?""",
                params + [limit, offset]).fetchall()]
        else:
            total = int(conn.execute(
                f"SELECT COUNT(*) FROM transactions WHERE {clause}", params).fetchone()[0])
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


def person_key(name: str | None) -> str:
    """Qarzdagi shaxs ismini solishtirish uchun: «Akmal», «akmal»,
    «Akmal », «Акмал» — bitta odam. Apostrof turlari ham birlashtiriladi.

    Ism lotinda ham, kirillda ham yozilishi mumkin (qarz bir yozuvda
    berilib, boshqasida qaytarilishi mumkin) — shuning uchun solishtirish
    bitta yozuvga (kirill) keltirib qilinadi.
    """
    import translit
    raw = translit.to_cyrillic((name or "").strip()).casefold()
    for ch in "ʻʼ‘’`'":
        raw = raw.replace(ch, "")
    return " ".join(raw.split())


def debt_ledger(user_id: int) -> list[dict]:
    """Har bir (qo'lda yopilmagan) qarz: qoldig'i va unga tushgan to'lovlar.

    Qaytarish (qarz_qaytdi / qarz_qaytardim) qarzga uch bosqichda
    taqsimlanadi:
      1. `repays_id` bilan aniq bog'langan to'lov — aynan o'sha qarzdan
         («💸 Qisman to'lash» tugmasi yoki bot «qaysi qarz?» deb so'ragan).
         Qoldiqdan ortig'i boshqa qarzga o'tmaydi.
      2. Ismli to'lov — shu shaxsning eng eski ochiq qarziga, u yopilsa
         keyingisiga (FIFO).
      3. Ismsiz to'lov (kredit, «qarzimni qaytardim») — o'sha yo'nalish
         va valyutada BITTA ochiq ismsiz qarz bo'lsa, unga. Ilgari ismsiz
         to'lov hech qayerga tushmasdi va «noma'lum 10 mln» qarz hech
         qachon kamaymasdi.
    Umumiy qoidalar: yo'nalish mos (menga qaytarilgan pul men BERGAN
    qarzni yopadi), valyuta bir xil, qarz to'lovdan OLDIN olingan
    (2–3-bosqich), qo'lda yopilgan («settled») qarz qatnashmaydi.

    Qoldiq saqlanmaydi, har safar hisoblanadi: to'lov o'chirilsa qarz
    o'z-o'zidan qayta ochiladi.

    Har element — `transactions` qatori + `remaining`, `paid` va
    `payments` ([{id, date, amount}] — shu qarzga tushgan qism).
    """
    with get_conn() as conn:
        rows = conn.execute(
            """SELECT * FROM transactions
               WHERE user_id = ? AND kind IN (?, ?, ?, ?)
               ORDER BY occurred_on ASC, id ASC""",
            (user_id, config.KIND_QARZ_BERDIM, config.KIND_QARZ_OLDIM,
             config.KIND_QARZ_QAYTDI, config.KIND_QARZ_QAYTARDIM)).fetchall()

    debts = [dict(r) for r in rows
             if r["kind"] in config.DEBT_OPEN_KINDS and not r["settled"]]
    by_id = {d["id"]: d for d in debts}
    for d in debts:
        d["remaining"] = float(d["amount"])
        d["payments"] = []
    pays = [dict(r) for r in rows if r["kind"] in config.REPAYS]

    def apply(pay: dict, d: dict, left: float) -> float:
        used = round(min(left, d["remaining"]), 2)
        if used > 0:
            d["remaining"] = round(d["remaining"] - used, 2)
            d["payments"].append({"id": pay["id"], "date": pay["occurred_on"],
                                  "amount": used})
        return round(left - used, 2)

    def fits(pay: dict, d: dict) -> bool:
        return (d["kind"] == config.REPAYS[pay["kind"]]
                and d["currency"] == pay["currency"] and d["remaining"] > 0)

    # 1) Aniq bog'langanlar.
    for pay in pays:
        d = by_id.get(pay.get("repays_id") or 0)
        if d is not None and fits(pay, d):
            apply(pay, d, float(pay["amount"]))

    unlinked = [p for p in pays if not p.get("repays_id")]
    # 2) Ismli — FIFO.
    for pay in unlinked:
        key = person_key(pay["person"])
        if not key:
            continue
        left = float(pay["amount"])
        for d in debts:
            if left <= 0:
                break
            if (fits(pay, d) and person_key(d["person"]) == key
                    and d["occurred_on"] <= pay["occurred_on"]):
                left = apply(pay, d, left)

    # 3) Ismsiz — yagona ochiq ismsiz qarzga.
    for pay in unlinked:
        if person_key(pay["person"]):
            continue
        cands = [d for d in debts
                 if fits(pay, d) and not person_key(d["person"])
                 and d["occurred_on"] <= pay["occurred_on"]]
        if len(cands) == 1:
            apply(pay, cands[0], float(pay["amount"]))

    for d in debts:
        d["paid"] = round(float(d["amount"]) - d["remaining"], 2)
    return debts


def open_debts(user_id: int) -> list[dict]:
    """Ochiq qarzlar — qoldig'i bor, qaytarishlar ayirilgan (debt_ledger).

    Har element — `transactions` qatori + `remaining` (asl valyutada),
    `remaining_base` (asosiy valyutada), `paid` va `payments`.
    """
    result = []
    for d in debt_ledger(user_id):
        if d["remaining"] <= 0:
            continue
        amount = float(d["amount"]) or 1.0
        base = d["amount_base"]
        if base is None:
            # Kurs joriy etilishidan oldingi yozuv: dollar summasi so'mga
            # to'g'ridan-to'g'ri qo'shilib ketmasin.
            import rates
            base = rates.to_base(d["amount"], d["currency"])[0]
        d["remaining_base"] = round(float(base) * d["remaining"] / amount, 2)
        result.append(d)
    return result


def debt_detail(user_id: int, debt_id: int) -> dict | None:
    """Bitta qarz: asli, to'langan, qoldiq va to'lovlar tarixi. Qo'lda
    yopilgan yoki qarz bo'lmagan yozuv uchun None."""
    return next((d for d in debt_ledger(user_id) if d["id"] == debt_id), None)


def repay_kind_for(debt_kind: str) -> str:
    """Qarzni qaytarish yozuvining turi: men olgan qarzni men qaytaraman,
    men bergan qarzni menga qaytarishadi."""
    return (config.KIND_QARZ_QAYTARDIM if debt_kind == config.KIND_QARZ_OLDIM
            else config.KIND_QARZ_QAYTDI)


def add_debt_payment(user_id: int, debt_id: int, amount: float,
                     occurred_on: str | None = None) -> int | None:
    """Qarzga to'lov yozadi («💸 Qisman to'lash»): qaytarish yozuvi qarz
    bilan bir xil shaxs va valyutada, `repays_id` bilan aniq bog'langan.
    Qarz topilmasa yoki qo'lda yopilgan bo'lsa None."""
    debt = debt_detail(user_id, debt_id)
    if debt is None or amount <= 0:
        return None
    return add_transaction(
        user_id, repay_kind_for(debt["kind"]), round(float(amount), 2), "qarz",
        note="qisman to'lov", person=debt["person"],
        occurred_on=occurred_on or _now().date().isoformat(),
        raw_text="[qarzni qisman to'lash]", currency=debt["currency"],
        repays_id=debt_id)


def set_repays(user_id: int, tx_id: int, debt_id: int | None) -> bool:
    """Qaytarish yozuvini qarzga bog'laydi (None — bog'lanishni olib
    tashlaydi, shunda ism bo'yicha avtomatik taqsimlanadi)."""
    with get_conn() as conn:
        return conn.execute(
            "UPDATE transactions SET repays_id = ? WHERE id = ? AND user_id = ? "
            "AND kind IN (?, ?)",
            (debt_id, tx_id, user_id, config.KIND_QARZ_QAYTARDIM,
             config.KIND_QARZ_QAYTDI)).rowcount > 0


def debt_candidates(user_id: int, repay_kind: str, currency: str,
                    on_date: str, tx_id: int | None = None) -> list[dict]:
    """Shu to'lov qaytarishi mumkin bo'lgan qarzlar: yo'nalish va valyuta
    mos, to'lovdan oldin olingan, ochiq. Eng eskisi birinchi.

    `tx_id` — to'lovning o'zi allaqachon saqlangan bo'lsa: u qarzni to'liq
    yopib qo'ygan bo'lishi mumkin (yagona ismsiz qarzga avtomatik
    tushgan), shunda ham o'sha qarz nomzod bo'lib qoladi.
    """
    target = config.REPAYS.get(repay_kind)
    return [d for d in debt_ledger(user_id)
            if d["kind"] == target and d["currency"] == currency
            and d["occurred_on"] <= on_date
            and (d["remaining"] > 0
                 or any(p["id"] == tx_id for p in d["payments"]))]


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
            # Botga yozdi — demak bloklamagan (blokdan chiqargan bo'lsa ham).
            conn.execute(
                "UPDATE users SET first_name = ?, username = ?, last_seen_at = ?, "
                "bot_blocked_at = NULL WHERE user_id = ?",
                (first_name or row["first_name"], username, _now().isoformat(), user_id),
            )
        return row


def access_status(user_id: int, first_name: str = "", username: str | None = None) -> dict:
    """Foydalanuvchining kirish holati va darajasi.

    Qaytaradi: {"ok", "status", "tier", "until", "days_left"}
      status: owner | trial | subscribed | free | blocked | not_allowed
      tier:   "pro" (ega, sinov, obuna) yoki "free"

    Sinov va obuna tugagan odam endi YOPILMAYDI — Bepul darajaga o'tadi
    (`ok` True). Faqat bloklangan va yopiq rejimdagi begona kira olmaydi.

    Ega `/oddiy_rejim on` qilgan bo'lsa (`users.sim_free`), u oddiy,
    obunasiz, sinovi tugagan foydalanuvchidek ko'rinadi — paywall va
    sinov xabarlarini o'z ko'zi bilan tekshirishi uchun.
    """
    def result(ok, status, until=None, days_left=None):
        tier = "pro" if status in ("owner", "trial", "subscribed") else "free"
        return {"ok": ok, "status": status, "tier": tier, "until": until,
                "days_left": days_left}

    if user_id in config.OWNER_IDS:
        # Egaga muddat tekshirilmaydi, lekin tashrifi baribir yozilishi
        # kerak: aks holda admin paneldagi «oxirgi faollik» ustuni ega
        # uchun muzlab qoladi va statistikani buzadi.
        row = get_or_create_user(user_id, first_name, username)
        if row["sim_free"]:
            # Oddiy rejim: sinov tugagan oddiy foydalanuvchi. Haqiqiy obuna
            # esa hisobga olinadi — ega to'lov oqimini oxirigacha sinab
            # (admin tasdiqlagach) PRO ga o'tganini ko'ra olsin.
            sub = _parse_dt(row["subscribed_until"])
            now = _now()
            if sub and sub > now:
                return result(True, "subscribed", sub, max(0, (sub - now).days))
            return result(True, "free", None, 0)
        return result(True, "owner")

    # ALLOWED_USER_IDS to'ldirilgan bo'lsa — yopiq rejim (sinov guruhi uchun).
    if config.ALLOWED_USER_IDS and user_id not in config.ALLOWED_USER_IDS:
        return result(False, "not_allowed")

    row = get_or_create_user(user_id, first_name, username)
    if row["blocked"]:
        return result(False, "blocked")

    now = _now()
    sub = _parse_dt(row["subscribed_until"])
    if sub and sub > now:
        return result(True, "subscribed", sub, max(0, (sub - now).days))

    trial = _parse_dt(row["trial_ends_at"])
    if trial and trial > now:
        return result(True, "trial", trial, max(0, (trial - now).days))

    return result(True, "free", sub or trial, 0)


def is_privileged(user_id: int) -> bool:
    """Haqiqiy ega (limitsiz). Oddiy rejimdagi ega — oddiy foydalanuvchi."""
    if user_id not in config.OWNER_IDS:
        return False
    with get_conn() as conn:
        row = conn.execute("SELECT sim_free FROM users WHERE user_id = ?",
                           (user_id,)).fetchone()
    return not (row and row["sim_free"])


def set_sim_free(user_id: int, on: bool) -> None:
    get_or_create_user(user_id)
    with get_conn() as conn:
        conn.execute("UPDATE users SET sim_free = ? WHERE user_id = ?",
                     (1 if on else 0, user_id))


def founders_taken() -> int:
    """Asoschilar taklifi egallagan joylar: tasdiqlangan va chek yuborib
    tekshiruvda turgan so'rovlar. Sxema admin panel bilan umumiy.

    Egalarning so'rovlari sanalmaydi — oqimni sinash (/oddiy_rejim) 100
    ta joydan birini egallab qo'ymasin.
    """
    owners = sorted(config.OWNER_IDS)
    not_owner = (" AND user_id NOT IN (%s)" % ",".join("?" * len(owners))) if owners else ""
    with get_conn() as conn:
        return int(conn.execute(
            "SELECT COUNT(*) FROM subscription_requests "
            "WHERE plan_code = 'f12' AND status IN ('tasdiqlandi', 'tekshiruvda')"
            + not_owner, owners).fetchone()[0])


def grant_subscription(user_id: int, days: int) -> datetime:
    """Obunani uzaytiradi. Amaldagi obuna bor bo'lsa uning ustiga qo'shiladi.

    `warned_stage` nolga qaytariladi: yangi muddatning ogohlantirishlari
    (3 va 1 kun qolganda) qaytadan yuborilishi kerak. Ilgari u qolib
    ketardi va ikkinchi obunada «tugashiga 1 kun qoldi» xabari umuman
    kelmasdi (users_expiring eski darajani «allaqachon yuborilgan» deb
    hisoblardi). Admin panel ham xuddi shunday qiladi (store.py).
    """
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
        conn.execute("UPDATE users SET subscribed_until = ?, warned_stage = 0 "
                     "WHERE user_id = ?", (new_until.isoformat(), user_id))
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
            # Vaqt yangi so'rovdagidek mahalliy ISO bilan: datetime('now')
            # UTC beradi va admin panel/analitika sanani adashtirardi.
            conn.execute(
                "UPDATE subscription_requests SET plan_code = ?, price = ?, "
                "created_at = ? WHERE id = ?",
                (plan_code, price, _now_local(), row["id"]),
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


REQUEST_CANCELLED = "bekor qilindi"


def cancel_open_request(user_id: int, note: str = "foydalanuvchi bekor qildi",
                        by: str = "foydalanuvchi") -> int:
    """Foydalanuvchining chek YUBORILMAGAN so'rovini bekor qiladi.

    Faqat «kutilmoqda» — chek kelgan («tekshiruvda») so'rov admin qarorini
    kutadi: odam pul o'tkazgan bo'lishi mumkin, uni jimgina yopib
    bo'lmaydi. Ilgari «❌ Bekor qilish» faqat xotiradagi belgini olardi va
    so'rov admin navbatida abadiy «kutilmoqda» bo'lib qolardi.
    """
    with get_conn() as conn:
        return conn.execute(
            "UPDATE subscription_requests SET status = ?, decided_at = ?, "
            "decided_by = ?, note = ? WHERE user_id = ? AND status = 'kutilmoqda'",
            (REQUEST_CANCELLED, _now_local(), by, note, user_id)).rowcount


def expire_stale_requests(hours: int = 48) -> int:
    """`hours` soatdan beri chek kelmagan so'rovlarni yopadi.

    Admin ularni qo'lda rad etib o'tirmasin: tarif tanlab, to'lamay ketgan
    odamning so'rovi navbatni to'ldirib turardi. Vaqt Python'da
    solishtiriladi — `created_at` ham mahalliy ISO (+05:00), ham eski UTC
    ko'rinishida bo'lishi mumkin.
    """
    cutoff = _now() - timedelta(hours=hours)
    with get_conn() as conn:
        rows = conn.execute(
            "SELECT id, created_at FROM subscription_requests "
            "WHERE status = 'kutilmoqda'").fetchall()
        stale = []
        for r in rows:
            raw = str(r["created_at"] or "")
            created = _parse_dt(raw)
            if created and not ("+" in raw[10:] or raw.endswith("Z")):
                # Mintaqasiz qiymat SQLite datetime('now') dan — bu UTC.
                created = created.replace(tzinfo=timezone.utc)
            if created and created < cutoff:
                stale.append(r["id"])
        for rid in stale:
            conn.execute(
                "UPDATE subscription_requests SET status = ?, decided_at = ?, "
                "decided_by = 'bot', note = ? WHERE id = ? AND status = 'kutilmoqda'",
                (REQUEST_CANCELLED, _now_local(),
                 f"avtomatik: {hours} soatda to'lov cheki kelmadi", rid))
    return len(stale)


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
            # Muddat surildi — ogohlantirishlar yangi sana uchun qaytadan.
            conn.execute("UPDATE users SET subscribed_until = ?, bonus_days = ?, "
                         "warned_stage = 0 WHERE user_id = ?",
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


def user_exists(user_id: int) -> bool:
    with get_conn() as conn:
        return conn.execute("SELECT 1 FROM users WHERE user_id = ?",
                            (user_id,)).fetchone() is not None


def set_source(user_id: int, source: str) -> bool:
    """Reklama manbasini yozadi — faqat hali yozilmagan bo'lsa (birinchisi
    yutadi: keyin boshqa havolani bosish manbani o'zgartirmaydi)."""
    with get_conn() as conn:
        return conn.execute(
            "UPDATE users SET source = ? WHERE user_id = ? AND source IS NULL",
            (source, user_id)).rowcount > 0


def had_consent(user_id: int) -> bool:
    """Ilgari biror versiyaga rozilik berganmi (shartlar yangilangani
    haqidagi xabar uchun — yangi odamga tanishtiruv, eskisiga «nima
    o'zgardi» ko'rsatiladi)."""
    with get_conn() as conn:
        row = conn.execute("SELECT consent_at FROM users WHERE user_id = ?",
                           (user_id,)).fetchone()
    return bool(row and row["consent_at"])


def users_for_first_entry_nudge(min_hours: int = 2, max_hours: int = 48) -> list[dict]:
    """Rozilik berib, lekin bitta ham yozuv kiritmaganlar — bitta eslatma.

    Faqat rozilik berganlar: bermaganga yozish uning ma'lumotini
    roziliksiz ishlatish bo'lardi. Vaqt rozilikdan beri: kamida
    `min_hours` (darrov bezovta qilmaslik), ko'pi bilan `max_hours`
    (eskilarga birdan xabar yog'ilmasin). Har odamga bir marta —
    `events` dagi «onboard_nudge» bilan belgilanadi.
    """
    now = _now()
    with get_conn() as conn:
        rows = conn.execute(
            """SELECT u.user_id, u.consent_at, u.lang FROM users u
               WHERE u.consent_at IS NOT NULL AND u.blocked = 0
                 AND u.bot_blocked_at IS NULL
                 AND NOT EXISTS (SELECT 1 FROM entry_counts e
                                 WHERE e.user_id = u.user_id AND e.n > 0)
                 AND NOT EXISTS (SELECT 1 FROM events ev
                                 WHERE ev.user_id = u.user_id
                                   AND ev.name = 'onboard_nudge')""").fetchall()
    out = []
    for r in rows:
        if r["user_id"] in config.OWNER_IDS:
            continue
        at = _parse_dt(r["consent_at"])
        if at and timedelta(hours=min_hours) <= now - at <= timedelta(hours=max_hours):
            out.append({"user_id": r["user_id"], "lang": r["lang"] or "uz"})
    return out


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
               FROM users u WHERE u.blocked = 0 AND u.bot_blocked_at IS NULL""").fetchall()
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
        amount = r["remaining_base"]
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

    import notify
    with get_conn() as conn:
        profiles = {r["user_id"]: dict(r) for r in conn.execute(
            "SELECT * FROM savings_profile").fetchall()}

    out = []
    for c in notify_candidates():
        r = c["row"]
        uid = r["user_id"]
        # Bepul: faqat faol bo'lsa (14 kundan kam) — va matni boshqacha:
        # faqat maqsad progressi (buni vazifa hal qiladi).
        if c["tier"] == "free" and notify.MONTHLY not in notify.free_policy(
                c["inactive_days"]):
            continue
        prof = profiles.get(uid) or {}
        if (prof.get("reminded_month") or "") == month:
            continue                       # shu oy allaqachon yuborilgan

        income = income_in_period(uid, first, today_)
        saved = savings_in_period(uid, first, today_)
        # Qoidani bajargan odamga «jamg'ar» deb yozish eslatmani
        # shovqinga aylantiradi — unga eslatma emas, faqat maqsadi bo'lsa
        # oy xulosasi boradi («met»: True).
        rate = savings_rate(uid)
        met = income > 0 and saved >= income * rate
        out.append({
            "met": met,
            "tier": c["tier"],
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
    """Haftalik xulosa oluvchilar: PRO hammasi; Bepul — faollik qoidasi
    ruxsat bersa (30 kundan ko'p yozmaganga yuborilmaydi)."""
    import notify
    out = []
    for c in notify_candidates():
        if c["tier"] == "free" and notify.WEEKLY not in notify.free_policy(
                c["inactive_days"]):
            continue
        out.append({"user_id": c["user_id"], "streak": c["row"]["streak"] or 0,
                    "tier": c["tier"], "inactive_days": c["inactive_days"]})
    return out


def mark_winback(user_id: int) -> None:
    with get_conn() as conn:
        conn.execute("UPDATE users SET winback_at = ? WHERE user_id = ?",
                     (_now_local(), user_id))


def week_summary(user_id: int, today: date | None = None) -> dict:
    """Haftalik xulosa: oxirgi TUGAGAN hafta (dushanba–yakshanba) va undan
    oldingi hafta taqqoslamasi.

    Xulosa dushanba ertalab yuboriladi. Ilgari «shu hafta» olinardi —
    dushanba 09:30 da u bir necha soatlik bo'lib, xulosa deyarli doim bo'sh
    chiqardi va «o'tgan haftadan 95% kam» degan yolg'on solishtirish berardi.
    """
    today = today or datetime.now(config.TZ).date()
    current_monday = today - timedelta(days=today.weekday())
    this_start = current_monday - timedelta(days=7)
    end = current_monday - timedelta(days=1)
    prev_start = this_start - timedelta(days=7)
    prev_end = this_start - timedelta(days=1)

    def spent(start, end):
        with get_conn() as conn:
            return float(conn.execute(
                "SELECT COALESCE(SUM(amount_base), 0) FROM transactions "
                "WHERE user_id = ? AND kind = ? AND occurred_on BETWEEN ? AND ?",
                (user_id, config.KIND_CHIQIM, start.isoformat(), end.isoformat())
            ).fetchone()[0])

    now_spent = spent(this_start, end)
    was_spent = spent(prev_start, prev_end)
    top = by_category_unified(user_id, this_start, end, config.KIND_CHIQIM)
    with get_conn() as conn:
        count = int(conn.execute(
            "SELECT COUNT(*) FROM transactions WHERE user_id = ? "
            "AND occurred_on BETWEEN ? AND ?",
            (user_id, this_start.isoformat(), end.isoformat())).fetchone()[0])
    return {"spent": now_spent, "previous": was_spent, "count": count,
            "top": top[:3], "start": this_start, "end": end}


def get_lang(user_id: int) -> str:
    with get_conn() as conn:
        row = conn.execute("SELECT lang FROM users WHERE user_id = ?",
                           (user_id,)).fetchone()
        return (row["lang"] if row and row["lang"] else "uz")


def set_lang(user_id: int, lang: str) -> None:
    with get_conn() as conn:
        conn.execute("UPDATE users SET lang = ? WHERE user_id = ?", (lang, user_id))


def set_reminder_hour(user_id: int, hour: int | None) -> None:
    """Soat — yoqish; None — o'chirish (va «o'zi o'chirgan» deb belgilash)."""
    with get_conn() as conn:
        conn.execute("UPDATE users SET reminder_hour = ?, reminder_off = ? "
                     "WHERE user_id = ?", (hour, 0 if hour is not None else 1, user_id))


def mark_bot_blocked(user_id: int) -> None:
    with get_conn() as conn:
        conn.execute("UPDATE users SET bot_blocked_at = ? WHERE user_id = ?",
                     (_now_local(), user_id))


def _tier_of_row(r, now: datetime) -> str:
    """access_status bilan bir xil qoida, lekin bitta qatordan (vazifalar uchun)."""
    if r["user_id"] in config.OWNER_IDS:
        return "free" if r["sim_free"] else "pro"
    sub = _parse_dt(r["subscribed_until"])
    trial = _parse_dt(r["trial_ends_at"])
    return "pro" if (sub and sub > now) or (trial and trial > now) else "free"


def notify_candidates() -> list[dict]:
    """Avtomatik xabar oluvchi bo'lishi mumkin bo'lganlar: bloklanmagan
    (admin ham, Telegram 403 ham emas). Har biriga daraja va oxirgi
    yozuvdan beri o'tgan kunlar qo'shiladi.

    Oxirgi faollik — `entry_counts` dagi eng so'nggi kun (bot, chek va
    Mini App yozuvlari hammasi shu yerga tushadi) yoki `last_entry_day`;
    yozuv umuman bo'lmasa — ro'yxatdan o'tgan kun.
    """
    now = _now()
    today_ = now.date()
    with get_conn() as conn:
        rows = conn.execute(
            """SELECT u.*, (SELECT MAX(day) FROM entry_counts e
                            WHERE e.user_id = u.user_id AND e.n > 0) AS last_day
               FROM users u
               WHERE u.blocked = 0 AND u.bot_blocked_at IS NULL""").fetchall()
    out = []
    for r in rows:
        days = [d for d in (r["last_day"], r["last_entry_day"]) if d]
        last = max(days) if days else str(r["created_at"] or "")[:10]
        try:
            inactive = max(0, (today_ - date.fromisoformat(last[:10])).days)
        except ValueError:
            inactive = 0
        out.append({"row": r, "user_id": r["user_id"], "tier": _tier_of_row(r, now),
                    "inactive_days": inactive,
                    "wrote_today": last[:10] == today_.isoformat()})
    return out


def reminder_opted_out(user_id: int) -> bool:
    with get_conn() as conn:
        row = conn.execute("SELECT reminder_off FROM users WHERE user_id = ?",
                           (user_id,)).fetchone()
    return bool(row and row["reminder_off"])


def get_reminder_hour(user_id: int) -> int | None:
    with get_conn() as conn:
        row = conn.execute("SELECT reminder_hour FROM users WHERE user_id = ?",
                           (user_id,)).fetchone()
        return row["reminder_hour"] if row else None


def users_for_reminder(hour: int) -> list[dict]:
    """Shu soatdagi kunlik eslatma oluvchilar: [{"user_id", "mode"}].

      * PRO — o'zi /eslatma bilan yoqqan bo'lsa, «summary» (kun xulosasi).
      * Bepul — standart holatda YOQILGAN (config.DEFAULT_REMINDER_HOUR),
        /eslatma o'chir bilan o'chiriladi; faqat o'sha kuni hali yozuv
        kiritmaganga va faollik qoidasi ruxsat bersa (notify.free_policy),
        «nudge» (qisqa eslatma).
    """
    import notify
    out = []
    for c in notify_candidates():
        r = c["row"]
        if c["tier"] == "pro":
            if r["reminder_hour"] == hour:
                out.append({"user_id": c["user_id"], "mode": "summary"})
            continue
        if r["reminder_off"]:
            continue
        effective = (r["reminder_hour"] if r["reminder_hour"] is not None
                     else config.DEFAULT_REMINDER_HOUR)
        if (effective == hour and not c["wrote_today"]
                and notify.DAILY in notify.free_policy(c["inactive_days"])):
            out.append({"user_id": c["user_id"], "mode": "nudge"})
    return out


TRIAL_STAGE_DAY5 = 5    # warned_stage: «PRO yana 2 kun» xabari yuborilgan
TRIAL_STAGE_ENDED = 7   # warned_stage: «sinov tugadi» xabari yuborilgan


def trial_notices() -> list[dict]:
    """Sinov muddati xabarlari kerak bo'lganlar (4.4).

      * day5  — sinovga 2 kun yoki kamroq qoldi va hali xabar olmagan;
      * ended — sinov oxirgi 3 kun ichida tugagan, obuna yo'q va 5-kun
        xabarini olgan.

    «ended» faqat 5-kun xabarini olganlarga: bu xabarlar joriy etilishidan
    OLDIN sinovi tugaganlar hech qanday avtomatik xabar olmaydi — ular
    jimgina Bepul darajaga o'tadi.
    """
    now = datetime.now(config.TZ)
    out = []
    with get_conn() as conn:
        rows = conn.execute("SELECT * FROM users WHERE blocked = 0 AND bot_blocked_at IS NULL").fetchall()
    for r in rows:
        if r["user_id"] in config.OWNER_IDS:
            continue
        sub = _parse_dt(r["subscribed_until"])
        if sub and sub > now:
            continue                       # obunachi — unga obuna xabarlari
        trial = _parse_dt(r["trial_ends_at"])
        if not trial:
            continue
        stage = r["warned_stage"] or 0
        if trial > now:
            left = max(0, math.ceil((trial - now).total_seconds() / 86400))
            if left <= 2 and stage == 0:
                out.append({"user_id": r["user_id"], "kind": "day5",
                            "days_left": left})
        elif stage == TRIAL_STAGE_DAY5 and now - trial <= timedelta(days=3):
            out.append({"user_id": r["user_id"], "kind": "ended", "days_left": 0})
    return out


def activity_counts(user_id: int) -> dict:
    """Sinov xulosasi uchun: oddiy yozuvlar va cheklar soni."""
    with get_conn() as conn:
        row = conn.execute(
            """SELECT SUM(CASE WHEN receipt_id IS NULL THEN 1 ELSE 0 END) AS entries,
                      COUNT(DISTINCT receipt_id) AS receipts,
                      MIN(occurred_on) AS first_day
               FROM transactions WHERE user_id = ?""", (user_id,)).fetchone()
    return {"entries": int(row["entries"] or 0), "receipts": int(row["receipts"] or 0),
            "first_day": row["first_day"]}


def users_expiring(stages: tuple[int, ...] = (3, 1)) -> list[dict]:
    """OBUNASI tugashiga `stages` kun qolganlar. Har daraja bir marta.

    Sinov muddati bu yerda emas — uning o'z xabarlari bor (trial_notices).

    `warned_stage` — oxirgi yuborilgan ogohlantirish darajasi. Muddat
    uzaytirilsa nolga qaytariladi, shunda keyingi safar yana yuboriladi.
    """
    now = datetime.now(config.TZ)
    out = []
    with get_conn() as conn:
        for r in conn.execute("SELECT * FROM users WHERE blocked = 0 AND bot_blocked_at IS NULL").fetchall():
            if r["user_id"] in config.OWNER_IDS:
                continue
            sub = _parse_dt(r["subscribed_until"])
            if sub and sub > now:
                expires, kind = sub, "obuna"
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
        conn.execute("DELETE FROM category_rules WHERE user_id = ?", (user_id,))
        conn.execute("DELETE FROM goals WHERE user_id = ?", (user_id,))
        conn.execute("DELETE FROM subscription_requests WHERE user_id = ?", (user_id,))
        # Taklif qilganlar zanjiri uzilmasin — havola bo'sh qoladi.
        conn.execute("UPDATE users SET referred_by = NULL WHERE referred_by = ?",
                     (user_id,))
        conn.execute("DELETE FROM users WHERE user_id = ?", (user_id,))
        conn.execute("DELETE FROM entry_counts WHERE user_id = ?", (user_id,))
        conn.execute("DELETE FROM events WHERE user_id = ?", (user_id,))
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
            conn.execute("DELETE FROM category_rules WHERE user_id = ?", (uid,))
            conn.execute("DELETE FROM goals WHERE user_id = ?", (uid,))
            conn.execute("DELETE FROM entry_counts WHERE user_id = ?", (uid,))
            # Hodisalar ham iz: qachon start bosgani, qaysi paywall'ni
            # ko'rgani. erase_user ularni o'chiradi — bu yerda ham shunday.
            conn.execute("DELETE FROM events WHERE user_id = ?", (uid,))
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


def count_since(user_id: int, operation: str, since: date) -> int:
    """`since` kunidan beri shu amal necha marta bajarilgan (masalan Bepul
    darajadagi oylik chek chegarasi uchun)."""
    with get_conn() as conn:
        row = conn.execute(
            "SELECT COUNT(*) AS n FROM usage_log "
            "WHERE user_id = ? AND day >= ? AND operation = ?",
            (user_id, since.isoformat(), operation)).fetchone()
        return int(row["n"])


# --------------------------------------------------------------------------- #
# Hodisalar (analitika)
# --------------------------------------------------------------------------- #

def log_event(user_id: int, name: str, detail: str = "") -> None:
    """Hodisani yozadi. Xato bo'lsa jimgina o'tib ketadi — analitika
    asosiy javobni hech qachon buzmasligi kerak."""
    try:
        with get_conn() as conn:
            conn.execute(
                "INSERT INTO events (user_id, name, detail, day) VALUES (?, ?, ?, ?)",
                (user_id, name, detail[:64], _today_str()))
    except Exception:
        import logging
        logging.getLogger(__name__).info("Hodisa yozilmadi: %s %s", name, detail)


def event_today(user_id: int, name: str, detail: str = "") -> bool:
    with get_conn() as conn:
        return conn.execute(
            "SELECT 1 FROM events WHERE user_id = ? AND name = ? AND detail = ? "
            "AND day = ? LIMIT 1",
            (user_id, name, detail, _today_str())).fetchone() is not None


def event_count_detail(user_id: int, name: str, detail: str) -> int:
    with get_conn() as conn:
        return int(conn.execute(
            "SELECT COUNT(*) FROM events WHERE user_id = ? AND name = ? AND detail = ?",
            (user_id, name, detail)).fetchone()[0])


def event_count(user_id: int, name: str) -> int:
    with get_conn() as conn:
        return int(conn.execute(
            "SELECT COUNT(*) FROM events WHERE user_id = ? AND name = ?",
            (user_id, name)).fetchone()[0])


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


def user_month_cost(user_id: int) -> float:
    """Shu foydalanuvchining joriy kalendar oydagi AI sarfi ($) —
    kishi boshiga oylik chegara uchun (config.user_monthly_budget_usd)."""
    start = _now().date().replace(day=1).isoformat()
    with get_conn() as conn:
        return float(conn.execute(
            "SELECT COALESCE(SUM(cost_usd), 0) FROM usage_log "
            "WHERE user_id = ? AND day >= ?", (user_id, start)).fetchone()[0])


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


def broadcast_audience(days: int = 30) -> list[int]:
    """/xabar_yubor oluvchilari: oxirgi `days` kunda yozuv kiritgan,
    bloklanmagan va joriy shartlarga rozi bo'lganlar. Eng faoli (ko'p kun
    yozganlar) birinchi. Egalar kirmaydi — ular «Menga sinov» bilan ko'radi.

    Faqat `entry_counts` (sanoq) va `users` dan — moliyaviy ma'lumot
    o'qilmaydi.
    """
    since = (_now().date() - timedelta(days=days)).isoformat()
    with get_conn() as conn:
        rows = conn.execute(
            """SELECT e.user_id, COUNT(*) AS active_days
               FROM entry_counts e JOIN users u ON u.user_id = e.user_id
               WHERE e.day >= ? AND u.blocked = 0 AND u.bot_blocked_at IS NULL
                 AND u.consent_at IS NOT NULL
                 AND u.consent_version = ?
               GROUP BY e.user_id
               ORDER BY active_days DESC, e.user_id""",
            (since, config.CONSENT_VERSION)).fetchall()
    return [r["user_id"] for r in rows if r["user_id"] not in config.OWNER_IDS]


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


def monthly_totals(user_id: int, months: int = 12) -> list[dict]:
    """Oxirgi `months` oy bo'yicha tur va valyuta kesimidagi jamlar.

    AI savol-javobi uchun: xom yozuvlar ro'yxati QA_MAX_ROWS bilan
    cheklangan, oylik jamlar esa SQL'da to'liq hisoblanadi — «yanvarda
    qancha sarfladim» degan savolga javob yozuvlar soniga bog'liq
    bo'lmasin. Valyutalar aralashtirilmaydi.
    """
    first = _now().date().replace(day=1)
    for _ in range(max(0, months - 1)):
        first = (first - timedelta(days=1)).replace(day=1)
    with get_conn() as conn:
        rows = conn.execute(
            """SELECT substr(occurred_on, 1, 7) AS oy, kind, currency,
                      ROUND(SUM(amount), 2) AS total, COUNT(*) AS n
               FROM transactions
               WHERE user_id = ? AND occurred_on >= ?
               GROUP BY oy, kind, currency
               ORDER BY oy""",
            (user_id, first.isoformat())).fetchall()
    return [dict(r) for r in rows]


def rows_for_ai(user_id: int, limit: int) -> list[sqlite3.Row]:
    """Savolga javob berish uchun oxirgi yozuvlar (eng yangilari birinchi olinadi)."""
    with get_conn() as conn:
        cur = conn.execute(
            "SELECT * FROM transactions WHERE user_id = ? ORDER BY occurred_on DESC, id DESC LIMIT ?",
            (user_id, limit),
        )
        return list(reversed(cur.fetchall()))
