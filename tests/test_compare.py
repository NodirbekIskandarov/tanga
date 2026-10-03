"""Oylarni solishtirish (PRO)."""

from datetime import date, datetime, timedelta

import config
import db
import reports
import tiers


def test_compare_uses_same_days_of_previous_month():
    (cs, ce), (ps, pe) = reports.compare_ranges(date(2026, 10, 3))
    assert (cs, ce, ps, pe) == (date(2026, 10, 1), date(2026, 10, 3),
                                date(2026, 9, 1), date(2026, 9, 3))
    # O'tgan oy qisqaroq: 31-mart -> 28-fevral.
    (_, _), (ps, pe) = reports.compare_ranges(date(2027, 3, 31))
    assert (ps, pe) == (date(2027, 2, 1), date(2027, 2, 28))


def test_compare_text_totals_and_category_changes(user_id):
    day = date(2026, 10, 3)
    add = lambda kind, amount, cat, d: db.add_transaction(
        user_id, kind, amount, cat, "x", occurred_on=d.isoformat())
    add("chiqim", 500_000, "oziq-ovqat", date(2026, 10, 2))
    add("chiqim", 80_000, "transport", date(2026, 10, 1))
    add("chiqim", 380_000, "oziq-ovqat", date(2026, 9, 2))
    add("chiqim", 120_000, "transport", date(2026, 9, 3))
    add("chiqim", 999_000, "transport", date(2026, 9, 20))   # solishtirishga kirmaydi
    add("kirim", 8_000_000, "oylik", date(2026, 10, 1))

    text = reports.compare_text(user_id, day)
    assert "Oktabr va sentabr" in text
    assert "1–3 oktabr va 1–3 sentabr" in text
    chiqim = next(line for line in text.splitlines() if line.startswith("🔻"))
    assert "580 000" in chiqim and "▲ 16%" in chiqim and "+80 000" in chiqim
    food = next(line for line in text.splitlines() if "oziq-ovqat" in line)
    assert "▲" in food and "+120 000" in food
    taxi = next(line for line in text.splitlines() if "transport" in line)
    assert "▼" in taxi and "−40 000" in taxi


def test_compare_is_pro_only(user_id):
    past = (datetime.now(config.TZ) - timedelta(days=3)).isoformat()
    with db.get_conn() as conn:
        conn.execute("UPDATE users SET trial_ends_at = ? WHERE user_id = ?", (past, user_id))
    assert not tiers.allows(db.access_status(user_id), "history")


def test_monthly_report_offers_compare_button():
    import bot
    assert "solishtir" in [c for c, _ in bot.BOT_COMMANDS]
