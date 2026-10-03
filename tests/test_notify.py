"""Bepul foydalanuvchiga avtomatik xabarlar, bloklanganlar va tezlik."""

import asyncio
import time
from datetime import datetime, timedelta

import pytest
from telegram.error import Forbidden, RetryAfter

import config
import db
import goals
import notify
import tiers

TODAY = tiers.today()


def _user(uid, *, free=True, last_entry_days_ago=None, created_days_ago=0):
    db.get_or_create_user(uid)
    now = datetime.now(config.TZ)
    trial = (now - timedelta(days=1) if free else now + timedelta(days=5)).isoformat()
    created = (TODAY - timedelta(days=created_days_ago)).isoformat() + " 08:00:00"
    with db.get_conn() as conn:
        conn.execute("UPDATE users SET trial_ends_at = ?, created_at = ? WHERE user_id = ?",
                     (trial, created, uid))
    if last_entry_days_ago is not None:
        day = (TODAY - timedelta(days=last_entry_days_ago)).isoformat()
        db.add_transaction(uid, "chiqim", 10_000, "oziq-ovqat", "non", occurred_on=day)


def _ids(rows, key="user_id"):
    return sorted(r[key] for r in rows)


# --------------------------------------------------------------- qoidalar --

@pytest.mark.parametrize("days,expected", [
    (0, {"daily", "weekly", "monthly"}),
    (13, {"daily", "weekly", "monthly"}),
    (14, {"weekly"}),
    (29, {"weekly"}),
    (30, set()),
    (90, set()),
])
def test_free_policy_thresholds(days, expected):
    assert notify.free_policy(days) == expected


# ------------------------------------------------------- kunlik eslatma --

def test_daily_reminder_free_default_on_only_without_entry_today():
    hour = config.DEFAULT_REMINDER_HOUR
    _user(1, last_entry_days_ago=2)                     # faol, bugun yozmagan
    _user(2, last_entry_days_ago=0)                     # bugun yozgan
    _user(3, last_entry_days_ago=15)                    # 14 kundan ko'p — faqat xulosa
    _user(4, last_entry_days_ago=1)
    db.set_reminder_hour(4, None)                       # o'zi o'chirgan
    _user(5, last_entry_days_ago=1)
    db.set_reminder_hour(5, 20)                         # soatni o'zgartirgan
    _user(6, free=False, last_entry_days_ago=1)         # PRO, yoqmagan

    rows = db.users_for_reminder(hour)
    assert rows == [{"user_id": 1, "mode": "nudge"}]
    assert db.users_for_reminder(20) == [{"user_id": 5, "mode": "nudge"}]


def test_pro_reminder_unchanged_opt_in_summary():
    _user(7, free=False, last_entry_days_ago=0)
    db.set_reminder_hour(7, 22)
    assert db.users_for_reminder(22) == [{"user_id": 7, "mode": "summary"}]


def test_returning_user_gets_normal_mode_back():
    _user(8, last_entry_days_ago=40)
    assert db.users_for_digest() == []
    db.add_transaction(8, "chiqim", 5_000, "transport", "taksi",
                       occurred_on=(TODAY - timedelta(days=1)).isoformat())
    assert _ids(db.users_for_reminder(config.DEFAULT_REMINDER_HOUR)) == [8]


# ------------------------------------------------------- haftalik xulosa --

def test_digest_audience_by_activity():
    _user(10, last_entry_days_ago=3)
    _user(11, last_entry_days_ago=20)                   # faqat xulosa oladi
    _user(12, last_entry_days_ago=31)                   # hech narsa
    _user(13, created_days_ago=40)                      # umuman yozmagan, eski
    _user(14, free=False, last_entry_days_ago=60)       # PRO — qoida qo'llanmaydi
    assert _ids(db.users_for_digest()) == [10, 11, 14]


def test_week_summary_is_last_completed_week():
    _user(15, last_entry_days_ago=0)
    s = db.week_summary(15)
    assert s["end"].weekday() == 6 and s["start"].weekday() == 0
    assert s["end"] < TODAY and (s["end"] - s["start"]).days == 6


def test_free_digest_is_short_with_monthly_pro_hint():
    import bot
    _user(16)
    s = db.week_summary(16)
    for i, (cat, amount) in enumerate([("oziq-ovqat", 50_000), ("transport", 40_000),
                                       ("kommunal", 30_000), ("dam olish", 10_000)]):
        db.add_transaction(16, "chiqim", amount, cat, "x",
                           occurred_on=(s["start"] + timedelta(days=i)).isoformat())
    row = {"user_id": 16, "tier": "free", "streak": 9}
    text = bot.digest_text(16, "uz", row)
    assert "130 000" in text
    assert text.count("\n• ") == 3                      # eng katta 3 kategoriya
    assert "Ketma-ket" not in text and "Yozuvlar" not in text   # qisqa
    assert "💎 PRO" in text
    assert "💎 PRO" not in bot.digest_text(16, "uz", row)       # oyiga bir marta


def test_digest_empty_week():
    import bot
    _user(17, last_entry_days_ago=20)
    assert "yozuv kiritilmadi" in bot.digest_text(17, "uz", {"tier": "free", "streak": 0})
    assert bot.digest_text(17, "uz", {"tier": "pro", "streak": 0}) is None


# ------------------------------------------------- oy oxiri: jamg'arma --

def test_free_savings_month_end_goal_only():
    import bot
    _user(20, last_entry_days_ago=2)
    _user(21, last_entry_days_ago=20)                   # 14 kundan ko'p — yo'q
    goals.create(20, "Uy", 10_000_000, None)
    db.add_transaction(20, "jamgarma", 2_000_000, "jamg'arma", "",
                       occurred_on=TODAY.isoformat())
    rows = {r["user_id"]: r for r in db.users_for_savings_reminder()}
    assert 21 not in rows and rows[20]["tier"] == "free"
    text = bot.goal_month_free_text(goals.primary(20), "uz")
    assert "«Uy» — <b>20%</b>" in text and "erishasiz" not in text


# ------------------------------------------------- bloklanganlar va tezlik --

class FakeBot:
    def __init__(self, error=None, fail_times=1):
        self.error, self.fail_times, self.sent = error, fail_times, []

    async def send_message(self, chat_id, text, **kw):
        if self.error and self.fail_times > 0:
            self.fail_times -= 1
            raise self.error
        self.sent.append(chat_id)


def test_forbidden_marks_user_and_excludes_everywhere():
    _user(30, last_entry_days_ago=1)
    bot = FakeBot(Forbidden("bot was blocked by the user"))
    assert asyncio.run(notify.send(bot, 30, "salom")) is False
    assert db.users_for_digest() == []
    assert db.users_for_reminder(config.DEFAULT_REMINDER_HOUR) == []

    # Odam botga qaytib yozdi — belgi tozalanadi.
    db.access_status(30)
    assert _ids(db.users_for_digest()) == [30]


def test_retry_after_waits_and_retries():
    bot = FakeBot(RetryAfter(0.01))
    assert asyncio.run(notify.send(bot, 31, "salom")) is True
    assert bot.sent == [31]


def test_rate_limiter_spacing():
    limiter = notify.RateLimiter(100)

    async def burst():
        for _ in range(11):
            await limiter.wait()
    started = time.monotonic()
    asyncio.run(burst())
    assert time.monotonic() - started >= 0.095          # 10 oraliq × 10 ms


def test_global_limit_is_25_per_second():
    assert notify.MAX_PER_SECOND <= 25
