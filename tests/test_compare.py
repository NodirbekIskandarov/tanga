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


# --------------------------------------------------------------------------- #
# Grafik ko'rinishi
# --------------------------------------------------------------------------- #

def _seed(user_id):
    add = lambda kind, amount, cat, d: db.add_transaction(
        user_id, kind, amount, cat, "x", occurred_on=d.isoformat())
    add("chiqim", 500_000, "oziq-ovqat", date(2026, 10, 2))
    add("chiqim", 80_000, "transport", date(2026, 10, 2))
    add("chiqim", 380_000, "oziq-ovqat", date(2026, 9, 2))
    add("kirim", 8_000_000, "oylik", date(2026, 10, 1))


def test_daily_totals_add_up_to_report_total(user_id):
    """Grafikdagi kunlar yig'indisi matndagi jamiga teng bo'lishi shart."""
    _seed(user_id)
    start, end = date(2026, 10, 1), date(2026, 10, 3)
    daily = db.daily_unified(user_id, start, end, "chiqim")
    assert daily == {date(2026, 10, 2): 580_000}
    assert sum(daily.values()) == db.totals_unified(user_id, start, end)["totals"]["chiqim"]


def test_single_day_span_is_not_written_as_range(user_id):
    text = reports.compare_text(user_id, date(2026, 10, 1))
    assert "1 oktabr va 1 sentabr" in text and "1–1" not in text


def test_compare_chart_is_skipped_without_entries(user_id):
    assert reports.compare_chart(user_id, date(2026, 10, 3)) is None


def test_compare_chart_renders_png(user_id):
    import pytest
    import sharecard
    if not sharecard.available():
        pytest.skip("Pillow yoki DejaVu shrifti yo'q (serverda bor)")
    _seed(user_id)
    for lang, day in (("uz", date(2026, 10, 3)), ("ru", date(2026, 10, 3)),
                      ("uz", date(2026, 10, 1))):           # 1-kun: chiziqsiz
        png = reports.compare_chart(user_id, day, lang=lang, bot_username="tanga_bot")
        assert png and png.startswith(b"\x89PNG"), (lang, day)


class _Msg:
    chat_id = 1001

    def __init__(self):
        self.sent = []

    async def reply_text(self, text, **kw):
        self.sent.append(("text", text))

    async def reply_photo(self, photo, caption=None, **kw):
        self.sent.append(("photo", caption))


class _Bot:
    username = "tanga_bot"

    async def send_chat_action(self, *a, **kw):
        pass


def _send(monkeypatch, user_id, png):
    import asyncio
    from types import SimpleNamespace
    import bot
    import sharecard
    monkeypatch.setattr(sharecard, "available", lambda: True)
    monkeypatch.setattr(reports, "compare_chart", lambda *a, **kw: png)
    msg = _Msg()
    asyncio.run(bot.send_compare(msg, SimpleNamespace(bot=_Bot()), user_id))
    return msg.sent


def test_compare_is_sent_as_chart_with_text_caption(monkeypatch, user_id):
    _seed(user_id)
    sent = _send(monkeypatch, user_id, b"\x89PNG fake")
    assert len(sent) == 1 and sent[0][0] == "photo"
    assert "📊" in sent[0][1]                      # matn izoh sifatida


def test_compare_falls_back_to_text_without_chart(monkeypatch, user_id):
    sent = _send(monkeypatch, user_id, None)
    assert [kind for kind, _ in sent] == ["text"]


def test_long_text_goes_after_the_chart(monkeypatch, user_id):
    import bot
    monkeypatch.setattr(reports, "compare_text", lambda *a, **kw: "x" * 1500)
    sent = _send(monkeypatch, user_id, b"\x89PNG fake")
    assert [kind for kind, _ in sent] == ["photo", "text"]
    assert sent[0][1] is None and bot._visible_len("<b>a&amp;</b>") == 2
