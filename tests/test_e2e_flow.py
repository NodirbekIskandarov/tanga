"""To'liq oqim: /oddiy_rejim on -> sinov -> paywall -> tarif -> to'lov cheki
-> admin tasdiqlashi -> PRO.

Haqiqiy bot handlerlari soxta Telegram obyektlari bilan chaqiriladi.
Admin tasdiqlashi admin panelning O'Z tarif ro'yxati (tanga-admin/plans.py)
bilan bajariladi — yangi `f12` kodi u yerda tanilishi shu yerda tekshiriladi.
Qo'lda tekshirish ro'yxati: docs/qolda-tekshirish.md.
"""

import asyncio
import importlib.util
from pathlib import Path
from types import SimpleNamespace

import pytest

import config
import db

OWNER = 777


class Bot:
    def __init__(self):
        self.messages, self.photos = [], []

    async def send_message(self, chat_id, text, **kw):
        self.messages.append((chat_id, text))

    async def send_photo(self, chat_id, photo, **kw):
        self.photos.append((chat_id, photo))

    async def send_document(self, chat_id, document, **kw):
        self.photos.append((chat_id, document))


class Message:
    def __init__(self, text="", photo=None):
        self.text, self.photo, self.document = text, photo, None
        self.caption, self.media_group_id, self.chat_id = None, None, OWNER
        self.replies = []

    async def reply_text(self, text, **kw):
        self.replies.append((text, kw.get("reply_markup")))
        return self

    @property
    def last(self):
        return self.replies[-1][0]

    @property
    def last_buttons(self):
        markup = self.replies[-1][1]
        return [b.callback_data for row in markup.inline_keyboard for b in row] if markup else []


class Query:
    def __init__(self, data, message):
        self.data, self.message, self.answers, self.edits = data, message, [], []

    async def answer(self, text=None, **kw):
        self.answers.append(text)

    async def edit_message_text(self, text, **kw):
        self.edits.append(text)


def _update(message=None, data=None):
    message = message or Message()
    user = SimpleNamespace(id=OWNER, first_name="Ega", username="ega")
    return SimpleNamespace(effective_user=user, effective_message=message,
                           message=message,
                           callback_query=Query(data, message) if data else None)


def _ctx(bot, args=None):
    return SimpleNamespace(bot=bot, user_data={}, args=args or [], bot_data={})


def _admin_plans():
    path = Path(__file__).resolve().parents[2] / "tanga-admin" / "plans.py"
    if not path.exists():
        pytest.skip("tanga-admin yonida yo'q")
    spec = importlib.util.spec_from_file_location("admin_plans_e2e", path)
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return module


def _admin_approve(request_id: int) -> dict:
    """tanga-admin/app.py: api_request_decide (qaror «tasdiq») bilan bir xil."""
    admin = _admin_plans()
    req = db.get_request(request_id)
    plan = admin.by_code(req["plan_code"])
    assert plan is not None, "admin panel tarifni tanimadi — «Tarif topilmadi»"
    db.grant_subscription(req["user_id"], plan["days"])
    with db.get_conn() as conn:
        conn.execute("UPDATE subscription_requests SET status = 'tasdiqlandi' WHERE id = ?",
                     (request_id,))
    return plan


def test_full_flow_sim_mode_to_pro(monkeypatch):
    import bot as b
    monkeypatch.setattr(config, "OWNER_IDS", {OWNER})
    monkeypatch.setattr(config, "CARD_NUMBER", "8600123412341234")
    monkeypatch.setattr(config, "CARD_HOLDER", "TEST")
    db.get_or_create_user(OWNER, "Ega", "ega")
    db.set_consent(OWNER, config.CONSENT_VERSION)
    tg = Bot()
    run = asyncio.run

    # 1. /oddiy_rejim on — ega oddiy, sinovi tugagan foydalanuvchi.
    u = _update()
    run(b.cmd_sim_mode(u, _ctx(tg, ["on"])))
    assert "Oddiy rejim yoqildi" in u.message.last
    u = _update()
    run(b.cmd_status(u, _ctx(tg)))
    assert "Bepul versiya" in u.message.last

    # 2. Sinov: oyning 3 ta bepul cheki ishlatilgan, 4-chek — paywall.
    for _ in range(config.FREE_RECEIPTS_PER_MONTH):
        db.usage_begin(OWNER, "chek")
    u = _update()
    assert run(b.check_quota(u, _ctx(tg), "chek")) is None
    assert "bepul chek ishlatildi" in u.message.last
    assert u.message.last_buttons == ["pro:receipts"]
    # O'sha kuni takror — bitta qisqa qator, tugmasiz.
    u = _update()
    run(b.check_quota(u, _ctx(tg), "chek"))
    assert u.message.last.startswith("🔒") and u.message.last_buttons == []

    # 3. «💎 PRO ga o'tish» -> tariflar sahifasi.
    u = _update(data="pro:receipts")
    run(b.on_callback(u, _ctx(tg)))
    assert "Tanga PRO" in u.message.last
    assert u.message.last_buttons == ["sub:12m", "sub:1m", "sub:f12"]

    # 4. Asoschilar taklifi -> karta rekvizitlari, egaga bildirishnoma.
    u = _update(data="sub:f12")
    run(b.on_callback(u, _ctx(tg)))
    assert u.callback_query.edits and "99 000" in u.callback_query.edits[-1]
    req = db.open_request_for(OWNER)
    assert req["plan_code"] == "f12" and req["status"] == "kutilmoqda"
    assert any("Yangi obuna so'rovi" in t for _, t in tg.messages)

    # 5. To'lov cheki (rasm).
    u = _update(message=Message(photo=[SimpleNamespace(file_id="CHEK-1")]))
    run(b.on_photo(u, _ctx(tg)))
    req = db.get_request(req["id"])
    assert req["status"] == "tekshiruvda" and req["proof_file_id"] == "CHEK-1"
    assert tg.photos == [(OWNER, "CHEK-1")]
    # Egalarning sinov so'rovi asoschilar joyini egallamaydi.
    assert config.founders_left() == config.FOUNDERS_LIMIT

    # 6. Admin tasdiqlaydi — f12 admin ro'yxatida tanilishi shart.
    plan = _admin_approve(req["id"])
    assert plan["days"] == 365
    u = _update()
    run(b.cmd_status(u, _ctx(tg)))
    assert "Obuna faol" in u.message.last          # oddiy rejimda ham PRO ko'rinadi

    # 7. /oddiy_rejim off — yana ega.
    u = _update()
    run(b.cmd_sim_mode(u, _ctx(tg, ["off"])))
    assert db.access_status(OWNER)["status"] == "owner"


def test_old_3m_button_cannot_start_new_purchase(monkeypatch):
    import bot as b
    monkeypatch.setattr(config, "OWNER_IDS", set())
    db.get_or_create_user(OWNER)
    db.set_consent(OWNER, config.CONSENT_VERSION)
    u = _update(data="sub:3m")
    asyncio.run(b.on_callback(u, _ctx(Bot())))
    assert db.open_request_for(OWNER) is None
    assert "mavjud emas" in (u.callback_query.answers[-1] or "")
