"""Launchdan oldingi kritik tuzatishlar (QA hisoboti, 2026-10-05).

K1  AI limiti: kishi boshiga (bepul/sinov), obunachi umumiy limitga
    urilmaydi, 100% da egaga xabar.
K2  Matn promptida kesh; chek effort; noma'lum model narxi; sinovdagi
    chek chegarasi.
K3  To'lov cheki holati bazada; «to'lov / xarid cheki» tugmalari;
    bekor qilish bazada; 48 soatda avtomatik yopish.
K4  /chek rejimi va albomda qismlar soni yuklab olishdan oldin cheklanadi.
K10 Mini App: /docs yopiq, xavfsizlik sarlavhalari.
M1  Restartda kutib turgan yangilanishlar tashlanmaydi.
"""

import asyncio
import inspect
from datetime import datetime, timedelta
from types import SimpleNamespace

import pytest

import config
import db
import tiers
from tests import fake_ai

UID, OTHER, OWNER = 5151, 5252, 777


class Bot:
    def __init__(self):
        self.messages, self.photos = [], []

    async def send_message(self, chat_id, text, **kw):
        self.messages.append((chat_id, text))

    async def send_photo(self, chat_id, photo, **kw):
        self.photos.append((chat_id, photo))

    async def send_document(self, chat_id, document, **kw):
        self.photos.append((chat_id, document))

    async def send_chat_action(self, *a, **kw):
        pass


class Status:
    async def edit_text(self, text, **kw):
        self.text = text


class Message:
    def __init__(self, text="", photo=None, media_group_id=None, uid=UID):
        self.text, self.photo, self.document = text, photo, None
        self.caption, self.media_group_id, self.chat_id = None, media_group_id, uid
        self.replies = []

    async def reply_text(self, text, **kw):
        self.replies.append((text, kw.get("reply_markup")))
        return Status()

    @property
    def last(self):
        return self.replies[-1][0]

    @property
    def last_buttons(self):
        markup = self.replies[-1][1]
        rows = getattr(markup, "inline_keyboard", None) or []
        return [b.callback_data for row in rows for b in row]


class Query:
    def __init__(self, data, message):
        self.data, self.message, self.answers, self.edits = data, message, [], []

    async def answer(self, text=None, **kw):
        self.answers.append(text)

    async def edit_message_text(self, text, **kw):
        self.edits.append(text)

    async def edit_message_reply_markup(self, **kw):
        pass


def _update(message=None, data=None, uid=UID):
    message = message or Message(uid=uid)
    user = SimpleNamespace(id=uid, first_name="Test", username=None)
    return SimpleNamespace(effective_user=user, effective_message=message,
                           effective_chat=SimpleNamespace(id=uid), message=message,
                           callback_query=Query(data, message) if data else None)


def _ctx(bot=None):
    return SimpleNamespace(bot=bot or Bot(), user_data={}, args=[], bot_data={})


def _user(uid, *, trial_days=7, sub_days=None):
    now = datetime.now(config.TZ)
    db.get_or_create_user(uid, "Test", None)
    db.set_consent(uid, config.CONSENT_VERSION)
    with db.get_conn() as conn:
        conn.execute(
            "UPDATE users SET trial_ends_at = ?, subscribed_until = ? WHERE user_id = ?",
            ((now + timedelta(days=trial_days)).isoformat(),
             (now + timedelta(days=sub_days)).isoformat() if sub_days else None, uid))
    return uid


def _spend(uid, usd):
    usage_id = db.usage_begin(uid, "matn")
    db.usage_finish(usage_id, {"model": "gemini-3.5-flash-lite", "cost_usd": usd})


@pytest.fixture(autouse=True)
def _clean_state():
    import bot
    bot._budget_warned.clear()
    for name in ("_proof_choice", "_collect", "_albums"):
        store = getattr(bot, name, None)
        if store is not None:
            store._data.clear()
    yield


# ---------------------------------------------------------------- K1 --

def test_free_user_over_personal_cap_stops_only_him(monkeypatch):
    import bot
    monkeypatch.setattr(config, "USER_MONTHLY_BUDGET_USD", 0.5)
    _user(UID, trial_days=-1)                 # bepul
    _user(OTHER, trial_days=-1)
    _spend(UID, 0.6)

    u = _update()
    assert asyncio.run(bot.check_quota(u, _ctx(), "matn")) is None
    assert "bepul AI limiti" in u.message.last
    assert u.message.last_buttons == ["pro:ai_limit"]

    assert asyncio.run(bot.check_quota(_update(uid=OTHER), _ctx(), "matn")) is not None


def test_trial_user_has_personal_cap_subscriber_does_not(monkeypatch):
    import bot
    monkeypatch.setattr(config, "USER_MONTHLY_BUDGET_USD", 0.5)
    _user(UID)                                # sinovda
    _spend(UID, 0.6)
    assert asyncio.run(bot.check_quota(_update(), _ctx(), "matn")) is None

    _user(OTHER, trial_days=-1, sub_days=30)  # obunachi
    _spend(OTHER, 5.0)
    assert asyncio.run(bot.check_quota(_update(uid=OTHER), _ctx(), "matn")) is not None


def test_global_cap_spares_subscribers_and_notifies_owner_at_100(monkeypatch):
    import bot
    monkeypatch.setattr(config, "OWNER_IDS", {OWNER})
    monkeypatch.setattr(config, "MONTHLY_BUDGET_USD", 1.0)
    monkeypatch.setattr(config, "USER_MONTHLY_BUDGET_USD", 0)
    _user(UID, trial_days=-1)                 # bepul
    _user(OTHER, trial_days=-1, sub_days=30)  # obunachi
    _spend(OTHER, 1.2)
    tg = Bot()

    u = _update()
    assert asyncio.run(bot.check_quota(u, _ctx(tg), "matn")) is None
    assert "to'xtatildi" in u.message.last
    assert asyncio.run(bot.check_quota(_update(uid=OTHER), _ctx(tg), "matn")) is not None

    to_owner = [t for chat, t in tg.messages if chat == OWNER]
    assert len(to_owner) == 1 and "chegarasi tugadi" in to_owner[0]


def test_unknown_model_is_not_free_and_gemini_prices():
    from datetime import date
    lite = "gemini-3.5-flash-lite"
    assert config.cost_usd(lite, 1_000_000, 0) == pytest.approx(0.30)
    assert config.cost_usd(lite, 0, 1_000_000) == pytest.approx(2.50)
    assert config.cost_usd(lite, 0, 0, cache_read=1_000_000) == pytest.approx(0.03)
    # Noma'lum model tekin emas: eng qimmat ma'lum narx olinadi.
    assert config.cost_usd("model-yoq-9", 1_000_000, 0, day=date(2026, 10, 6)) \
        == pytest.approx(0.75)
    assert config.cost_usd("model-yoq-9", 0, 1_000_000, day=date(2026, 10, 6)) \
        == pytest.approx(3.75)


def test_flash_38_price_depends_on_the_date():
    from datetime import date
    m = "gemini-3.8-flash"
    # 2026-12-31 gacha chegirmali, 2027-01-01 dan to'liq narx.
    assert config.cost_usd(m, 1_000_000, 1_000_000, day=date(2026, 12, 31)) \
        == pytest.approx(0.75 + 3.75)
    assert config.cost_usd(m, 1_000_000, 1_000_000, day=date(2027, 1, 1)) \
        == pytest.approx(1.50 + 7.50)
    assert config.cost_usd(m, 0, 0, cache_read=1_000_000, day=date(2027, 1, 1)) \
        == pytest.approx(0.15)
    # Noma'lum model uchun ham sana hisobga olinadi.
    assert config.cost_usd("model-yoq-9", 0, 1_000_000, day=date(2027, 3, 1)) \
        == pytest.approx(7.50)


def test_audio_tokens_use_the_audio_price():
    m = "gemini-3.5-flash-lite"
    # 1M kirish tokenining yarmi audio — ikkalasi ham shu modelda $0.30.
    assert config.cost_usd(m, 1_000_000, 0, audio=500_000) == pytest.approx(0.30)
    # Audio kirishdan oshib ketmaydi (xato ma'lumot ortiqcha hisoblamasin).
    assert config.cost_usd(m, 100, 0, audio=10**9) == pytest.approx(100 / 1e6 * 0.30)


# ---------------------------------------------------------------- K2 --

def test_parse_prompt_is_stable_and_date_free(monkeypatch):
    """Gemini'ning yashirin keshi prefiks bo'yicha ishlaydi: tizim prompti va
    sxema har chaqiruvda bir xil, sana va matn faqat foydalanuvchi qismida."""
    import ai
    fake = fake_ai.install(monkeypatch, [{"niyat": "tushunarsiz", "yozuvlar": []},
                                         {"niyat": "tushunarsiz", "yozuvlar": []}])
    asyncio.run(ai.parse_message("salom", today=datetime(2026, 10, 6).date()))
    asyncio.run(ai.parse_message("boshqa matn", today=datetime(2027, 2, 1).date()))

    first, second = fake.calls
    assert first["system"] == second["system"]               # kunlar o'zgarsa ham
    assert first["schema"] == second["schema"]
    assert "2026-10-06" not in first["system"] and "2027-02-01" not in first["system"]
    parts = first["parts"]
    assert parts[0] == {"type": "text", "text": "Bugungi sana: 2026-10-06"}
    assert parts[-1] == {"type": "text", "text": "salom"}      # foydalanuvchi matni oxirgi
    assert ai._parse_system_prompt() == first["system"]
    assert first["model"] == config.PARSE_MODEL
    assert first["thinking"] == config.PARSE_THINKING


def test_receipt_system_prompt_has_no_date_or_part_count(monkeypatch):
    import ai
    fake = fake_ai.install(monkeypatch, [{"oqildi": False, "mahsulotlar": []},
                                         {"oqildi": False, "mahsulotlar": []}])
    day = datetime(2026, 10, 6).date()
    asyncio.run(ai.parse_receipt([("eA==", "image/jpeg")], today=day))
    asyncio.run(ai.parse_receipt([("eA==", "image/jpeg")] * 3, today=day))
    one, three = fake.calls
    assert one["system"] == three["system"]                  # qismlar soni keshni buzmasin
    assert "2026-10-06" not in one["system"]
    assert "Bugungi sana: 2026-10-06" in one["parts"][0]["text"]
    assert "3 ta rasm" in three["parts"][0]["text"]


def test_thinking_level_comes_from_config(monkeypatch):
    import ai
    monkeypatch.setattr(config, "VISION_THINKING", "high")
    fake = fake_ai.install(monkeypatch, [{"oqildi": False, "mahsulotlar": []}])
    asyncio.run(ai.parse_receipt([("eA==", "image/jpeg")]))
    assert fake.calls[0]["thinking"] == "high"
    assert fake.calls[0]["model"] == config.VISION_MODEL


def test_thinking_setting_ignores_garbage(monkeypatch):
    monkeypatch.setenv("VISION_THINKING", "juda-chuqur")
    monkeypatch.setenv("PARSE_THINKING", " LOW ")
    assert config._thinking("VISION_THINKING", "medium") == "medium"   # noto'g'ri — standart
    assert config._thinking("PARSE_THINKING", "minimal") == "low"
    assert config._thinking("YOQ_SOZLAMA", "high") == "high"


def test_trial_receipts_total_cap():
    _user(UID)                                # sinovda
    access = db.access_status(UID)
    for _ in range(config.TRIAL_RECEIPTS_TOTAL):
        assert tiers.check(UID, access, "chek") is None
        db.usage_begin(UID, "chek")
    verdict = tiers.check(UID, access, "chek")
    assert verdict["type"] == "paywall" and verdict["feature"] == "trial_receipts"


# ---------------------------------------------------------------- K3 --

def _open_request(uid=UID, code="12m"):
    return db.add_subscription_request(uid, code, 149_000)


def _photo(uid=UID, file_id="IMG-1"):
    return Message(photo=[SimpleNamespace(file_id=file_id)], uid=uid)


def test_after_restart_photo_asks_payment_or_purchase():
    import bot
    _user(UID)
    rid = _open_request()                       # xotirada hech narsa yo'q
    u = _update(_photo())
    asyncio.run(bot.on_photo(u, _ctx()))
    assert u.message.last_buttons == ["pf:pay", "pf:buy"]
    assert db.get_request(rid)["status"] == "kutilmoqda"


def test_payment_button_attaches_proof_and_notifies_owner(monkeypatch):
    import bot
    monkeypatch.setattr(config, "OWNER_IDS", {OWNER})
    _user(UID)
    rid = _open_request()
    tg = Bot()
    asyncio.run(bot.on_photo(_update(_photo(file_id="PAY-1")), _ctx(tg)))
    u = _update(data="pf:pay")
    asyncio.run(bot.on_callback(u, _ctx(tg)))
    req = db.get_request(rid)
    assert req["status"] == "tekshiruvda" and req["proof_file_id"] == "PAY-1"
    assert tg.photos == [(OWNER, "PAY-1")]
    assert "Chek qabul qilindi" in u.callback_query.edits[-1]


def test_purchase_button_reads_receipt_and_keeps_request(monkeypatch):
    import ai
    import bot
    _user(UID)
    rid = _open_request()

    async def fake_download(context, message):
        assert message.photo[-1].file_id == "SHOP-1"
        return ("eA==", "image/jpeg")

    read = []

    async def fake_parse(images, today=None, caption=""):
        read.append(images)
        return {"oqildi": False, "izoh_matni": "test", "_usage": None}

    monkeypatch.setattr(bot, "_download_receipt_file", fake_download)
    monkeypatch.setattr(ai, "parse_receipt", fake_parse)

    asyncio.run(bot.on_photo(_update(_photo(file_id="SHOP-1")), _ctx()))
    asyncio.run(bot.on_callback(_update(data="pf:buy"), _ctx()))
    assert read == [[("eA==", "image/jpeg")]]
    req = db.get_request(rid)
    assert req["status"] == "kutilmoqda" and not req["proof_file_id"]


def test_expired_choice_asks_to_resend():
    import bot
    _user(UID)
    u = _update(data="pf:pay")
    asyncio.run(bot.on_callback(u, _ctx()))
    assert "eskirdi" in (u.callback_query.answers[-1] or "")


def test_cancel_button_cancels_request_in_db():
    import bot
    _user(UID)
    rid = _open_request()
    asyncio.run(bot.on_callback(_update(data="sub:bekor"), _ctx()))
    assert db.get_request(rid)["status"] == db.REQUEST_CANCELLED
    assert db.open_request_for(UID) is None


def test_cancel_does_not_touch_request_with_proof():
    _user(UID)
    rid = _open_request()
    db.attach_payment_proof(rid, "PAY-1")
    assert db.cancel_open_request(UID) == 0
    assert db.get_request(rid)["status"] == "tekshiruvda"


def test_stale_requests_close_after_48h():
    _user(UID)
    _user(OTHER)
    old, fresh = _open_request(), _open_request(OTHER)
    utc_old = db.add_subscription_request(6363, "1m", 19_000)
    proof = db.add_subscription_request(6464, "1m", 19_000)
    db.attach_payment_proof(proof, "PAY")
    three_days = (datetime.now(config.TZ) - timedelta(days=3))
    with db.get_conn() as conn:
        conn.execute("UPDATE subscription_requests SET created_at = ? WHERE id = ?",
                     (three_days.isoformat(timespec="seconds"), old))
        # Eski yozuvlar: mintaqasiz UTC (SQLite datetime('now')).
        conn.execute("UPDATE subscription_requests SET created_at = "
                     "datetime('now', '-50 hours') WHERE id = ?", (utc_old,))
        conn.execute("UPDATE subscription_requests SET created_at = ? WHERE id = ?",
                     (three_days.isoformat(timespec="seconds"), proof))

    assert db.expire_stale_requests(48) == 2
    assert db.get_request(old)["status"] == db.REQUEST_CANCELLED
    assert db.get_request(utc_old)["status"] == db.REQUEST_CANCELLED
    assert db.get_request(fresh)["status"] == "kutilmoqda"
    assert db.get_request(proof)["status"] == "tekshiruvda"   # chek kelgan — tegilmaydi


def test_long_receipt_mode_photo_is_not_taken_as_payment(monkeypatch):
    import bot
    _user(UID)
    _open_request()

    async def fake_download(context, message):
        return ("eA==", "image/jpeg")

    monkeypatch.setattr(bot, "_download_receipt_file", fake_download)
    bot._collect.set(UID, {"images": [], "caption": ""})
    u = _update(_photo())
    asyncio.run(bot.on_photo(u, _ctx()))
    assert "1-qism qabul qilindi" in u.message.last


# ---------------------------------------------------------------- K4 --

def test_long_receipt_mode_caps_parts(monkeypatch):
    import bot
    _user(UID)

    async def must_not_download(context, message):
        raise AssertionError("chegaradan keyin fayl yuklab olinmasligi kerak")

    monkeypatch.setattr(bot, "_download_receipt_file", must_not_download)
    full = [("x", "image/jpeg")] * config.MAX_RECEIPT_PARTS
    bot._collect.set(UID, {"images": list(full), "caption": ""})
    u = _update(_photo())
    asyncio.run(bot.on_photo(u, _ctx()))
    assert len(bot._collect.get(UID)["images"]) == config.MAX_RECEIPT_PARTS
    assert f"{config.MAX_RECEIPT_PARTS} ta qism" in u.message.last


def test_album_caps_parts_and_refuses(monkeypatch):
    import bot
    _user(UID)

    async def must_not_download(context, message):
        raise AssertionError("chegaradan keyin fayl yuklab olinmasligi kerak")

    monkeypatch.setattr(bot, "_download_receipt_file", must_not_download)
    full = [("x", "image/jpeg")] * config.MAX_RECEIPT_PARTS
    bot._albums.set("G1", {"images": list(full), "caption": "", "task": None})
    asyncio.run(bot.on_photo(_update(Message(photo=[SimpleNamespace(file_id="A")],
                                             media_group_id="G1")), _ctx()))
    assert bot._albums.get("G1")["too_many"] is True

    monkeypatch.setattr(bot, "ALBUM_WAIT_SECONDS", 0)
    u = _update()
    asyncio.run(bot._flush_album("G1", u, _ctx()))
    assert "ko'pi bilan" in u.message.last


# ---------------------------------------------------------------- K10 --

def test_miniapp_hides_api_docs_and_sends_security_headers():
    from fastapi.testclient import TestClient
    import webapp
    client = TestClient(webapp.app, base_url="https://testserver")
    for path in ("/docs", "/redoc", "/openapi.json"):
        assert client.get(path).status_code == 404, path
    r = client.get("/")
    assert r.status_code == 200
    assert "frame-ancestors https://telegram.org" in r.headers["content-security-policy"]
    assert r.headers["x-content-type-options"] == "nosniff"
    assert "strict-transport-security" in r.headers


# ---------------------------------------------------------------- M1 --

def test_pending_updates_are_not_dropped():
    import bot
    source = inspect.getsource(bot.main)
    assert "drop_pending_updates=False" in source
