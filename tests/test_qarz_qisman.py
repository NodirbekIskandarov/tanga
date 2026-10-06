"""Qarzni qisman to'lash (QA hisoboti, 2-bo'lim).

Qabul mezoni: «noma'lum 10 mln» qarzga «kreditga 500 ming to'ladim»
yozilsa, /qarz da «qoldiq 9 500 000 (asli 10 000 000)» ko'rinadi.
"""

import asyncio
import hashlib
import hmac
import json
import sys
import time
from datetime import datetime, timedelta
from pathlib import Path
from types import SimpleNamespace
from urllib.parse import urlencode

import pytest

import config
import db
import reports
from tests import fake_ai

UID = 8181


class Message:
    def __init__(self, text=""):
        self.text, self.photo, self.document = text, None, None
        self.caption, self.media_group_id, self.chat_id = None, None, UID
        self.replies = []

    async def reply_text(self, text, **kw):
        self.replies.append((text, kw.get("reply_markup")))
        return self

    def buttons(self, i=-1):
        rows = getattr(self.replies[i][1], "inline_keyboard", None) or []
        return [b.callback_data for row in rows for b in row]

    @property
    def texts(self):
        return "\n".join(t for t, _ in self.replies)


class Query:
    def __init__(self, data, message):
        self.data, self.message, self.answers, self.edits = data, message, [], []

    async def answer(self, text=None, **kw):
        self.answers.append(text)

    async def edit_message_text(self, text, **kw):
        self.edits.append(text)

    async def edit_message_reply_markup(self, **kw):
        pass


class Bot:
    async def send_message(self, *a, **kw):
        pass

    async def send_chat_action(self, *a, **kw):
        pass


def _update(message=None, data=None):
    message = message or Message()
    user = SimpleNamespace(id=UID, first_name="Test", username=None)
    return SimpleNamespace(effective_user=user, effective_message=message,
                           effective_chat=SimpleNamespace(id=UID), message=message,
                           callback_query=Query(data, message) if data else None)


CTX = None


@pytest.fixture(autouse=True)
def consented_user():
    global CTX
    db.get_or_create_user(UID, "Test", None)
    db.set_consent(UID, config.CONSENT_VERSION)
    CTX = SimpleNamespace(bot=Bot(), user_data={}, args=[], bot_data={})
    yield


TODAY = datetime.now(config.TZ).date()
D1 = (TODAY - timedelta(days=30)).isoformat()


def _debt(kind="qarz_oldim", amount=10_000_000, person=None, currency="som", day=D1):
    return db.add_transaction(UID, kind, amount, "qarz", "qarz", person=person,
                              occurred_on=day, currency=currency)


def _remaining(debt_id):
    return db.debt_detail(UID, debt_id)["remaining"]


_MP = None


@pytest.fixture(autouse=True)
def _mp(monkeypatch):
    global _MP
    _MP = monkeypatch
    yield


def _say(text, payload):
    """Matnni bot orqali: AI javobi soxta, qolgan hamma yo'l haqiqiy."""
    import bot
    fake_ai.install(_MP, [payload])
    u = _update(Message(text))
    asyncio.run(bot.on_text(u, CTX))
    return u


def _repay(amount, person="", kind="qarz_qaytardim", currency="som"):
    return {"niyat": "yozuv", "yozuvlar": [fake_ai.record(
        kind, amount, "qarz", "qarz", shaxs=person, sana=TODAY.isoformat(),
        valyuta=currency)]}


# --------------------------------------------------------- qabul mezoni --

def test_acceptance_nameless_credit_payment():
    debt = _debt()
    u = _say("kreditga 500 ming to'ladim", _repay(500_000))
    assert _remaining(debt) == 9_500_000
    assert "qoldiq <b>9 500 000" in u.message.texts             # «qarzga yozildi»

    text = reports.debts_text(UID)
    assert "qoldiq <b>9 500 000 so'm</b>" in text
    assert "to'langan 500 000 so'm / 10 000 000 so'm" in text


# ------------------------------------------------------ tugma bilan --

def test_partial_payment_via_buttons():
    import bot
    debt = _debt(person="Akmal", kind="qarz_berdim", amount=2_000_000)
    u = _update()
    asyncio.run(bot.cmd_debts(u, CTX))
    assert f"dq:{debt}" in u.message.buttons() and f"dz:{debt}" in u.message.buttons()

    asyncio.run(bot.on_callback(_update(data=f"dq:{debt}"), CTX))
    u = _update(Message("500 ming"))
    asyncio.run(bot.on_text(u, CTX))
    assert _remaining(debt) == 1_500_000
    assert "Qoldiq: <b>1 500 000" in u.message.texts
    # Yozuv to'g'ri tur va shaxs bilan: menga qaytarildi, Akmal.
    pay = db.debt_detail(UID, debt)["payments"][0]
    row = db.get_transaction(UID, pay["id"])
    assert row["kind"] == "qarz_qaytdi" and row["person"] == "Akmal"
    assert row["repays_id"] == debt


def test_overpayment_asks_then_closes():
    import bot
    debt = _debt(amount=1_500_000)
    asyncio.run(bot.on_callback(_update(data=f"dq:{debt}"), CTX))
    u = _update(Message("2 mln"))
    asyncio.run(bot.on_text(u, CTX))
    assert _remaining(debt) == 1_500_000                         # hali yozilmadi
    assert f"dzf:{debt}" in u.message.buttons()

    u = _update(data=f"dzf:{debt}")
    asyncio.run(bot.on_callback(u, CTX))
    assert _remaining(debt) == 0
    assert "to'liq yopildi" in u.message.texts
    assert db.open_debts(UID) == []


def test_close_menu_forgive_settles_without_money():
    import bot
    debt = _debt(amount=300_000)
    asyncio.run(bot.on_callback(_update(data=f"dz:{debt}"), CTX))
    asyncio.run(bot.on_callback(_update(data=f"dzs:{debt}"), CTX))
    assert db.open_debts(UID) == []
    assert db.tx_count(UID) == 1                                  # to'lov yozilmadi


def test_bad_amount_keeps_waiting():
    import bot
    debt = _debt(amount=300_000)
    asyncio.run(bot.on_callback(_update(data=f"dq:{debt}"), CTX))
    asyncio.run(bot.on_text(_update(Message("bilmadim")), CTX))
    asyncio.run(bot.on_text(_update(Message("100 ming")), CTX))
    assert _remaining(debt) == 200_000


# ----------------------------------------------------- bir nechta qarz --

def test_two_open_debts_ask_which_one():
    import bot
    first = _debt(amount=10_000_000)
    second = _debt(person="Akmal", amount=2_000_000)
    u = _say("qarzimdan 1 mln to'ladim", _repay(1_000_000))
    btns = u.message.buttons()
    pay_id = int(btns[0].split(":")[1])
    assert btns == [f"dl:{pay_id}:{first}", f"dl:{pay_id}:{second}", f"dl:{pay_id}:0"]

    asyncio.run(bot.on_callback(_update(data=f"dl:{pay_id}:{second}"), CTX))
    assert _remaining(second) == 1_000_000 and _remaining(first) == 10_000_000


def test_single_named_debt_is_asked_not_auto_linked():
    """Bank krediti to'lovi yagona ismli qarzni kamaytirib qo'ymasin."""
    debt = _debt(person="Akmal", amount=2_000_000)
    u = _say("kreditga 500 ming to'ladim", _repay(500_000))
    assert u.message.buttons()[-1].endswith(":0")                # «hech biriga» bor
    assert _remaining(debt) == 2_000_000


def test_none_choice_blocks_auto_linking():
    import bot
    first = _debt()
    _debt(amount=5_000_000)                                      # ikkita ismsiz
    u = _say("kreditga 500 ming to'ladim", _repay(500_000))
    pay_id = int(u.message.buttons()[0].split(":")[1])
    asyncio.run(bot.on_callback(_update(data=f"dl:{pay_id}:0"), CTX))
    db.settle_debt(UID, first)                                   # endi ismsiz bitta qoldi
    assert all(d["remaining"] == d["amount"] for d in db.open_debts(UID))


# ------------------------------------------------------------ qoidalar --

def test_deleting_payment_reopens_debt():
    debt = _debt(amount=1_000_000)
    pay = db.add_debt_payment(UID, debt, 1_000_000)
    assert db.open_debts(UID) == []
    db.delete_transaction(UID, pay)
    assert _remaining(debt) == 1_000_000


def test_linked_payment_does_not_spill_to_other_debt():
    a = _debt(person="Ali", amount=100_000)
    b = _debt(person="Ali", amount=100_000)
    db.add_transaction(UID, "qarz_qaytardim", 150_000, "qarz", person="Ali",
                       occurred_on=TODAY.isoformat(), repays_id=a)
    assert _remaining(a) == 0 and _remaining(b) == 100_000


def test_currencies_do_not_mix_and_usd_amount_is_literal():
    import bot
    som = _debt(amount=1_000_000)
    usd = _debt(amount=500, currency="usd")
    _say("qarzimni qaytardim $100", _repay(100, currency="usd"))
    assert _remaining(som) == 1_000_000 and _remaining(usd) == 400

    asyncio.run(bot.on_callback(_update(data=f"dq:{usd}"), CTX))
    asyncio.run(bot.on_text(_update(Message("50")), CTX))         # $50, 50 000 emas
    assert _remaining(usd) == 350


def test_named_payment_still_uses_fifo():
    a = _debt(person="Sardor", amount=300_000, day=(TODAY - timedelta(days=20)).isoformat())
    b = _debt(person="Sardor", amount=300_000, day=(TODAY - timedelta(days=10)).isoformat())
    _say("Sardorga qarzimni qaytardim 400 ming", _repay(400_000, person="Sardor"))
    assert _remaining(a) == 0 and _remaining(b) == 200_000


def test_reminder_uses_remaining():
    debt = _debt(person="Akmal", kind="qarz_berdim", amount=1_000_000)
    db.set_due(UID, debt, TODAY)
    db.add_debt_payment(UID, debt, 400_000)
    due = db.debts_due((TODAY,))
    assert due[0]["remaining"] == 600_000


def test_debts_text_groups_by_person():
    _debt(person="Rozimbetov Sardor", amount=100_000)
    _debt(person="rozimbetov sardor", amount=200_000)
    text = reports.debts_text(UID)
    assert text.count("👤") == 1 and "(2 ta qarz)" in text
    assert "300 000 so'm" in text


# ------------------------------------------------------------ Mini App --

def _init_data(uid):
    pairs = {"auth_date": str(int(time.time())),
             "user": json.dumps({"id": uid, "first_name": "Test"})}
    check = "\n".join(f"{k}={v}" for k, v in sorted(pairs.items()))
    secret = hmac.new(b"WebAppData", config.TELEGRAM_TOKEN.encode(), hashlib.sha256).digest()
    pairs["hash"] = hmac.new(secret, check.encode(), hashlib.sha256).hexdigest()
    return {"X-Telegram-Init-Data": urlencode(pairs)}


def test_miniapp_partial_payment_and_history():
    from fastapi.testclient import TestClient
    import webapp
    webapp._rate.clear()
    client = TestClient(webapp.app)
    h = _init_data(UID)
    debt = _debt(amount=1_000_000)

    r = client.post(f"/api/debts/{debt}/pay", json={"amount": 250_000}, headers=h)
    assert r.status_code == 200 and r.json()["remaining"] == 750_000
    detail = client.get(f"/api/debts/{debt}", headers=h).json()
    assert detail["paid"] == 250_000 and len(detail["payments"]) == 1
    assert client.post(f"/api/debts/{debt}/pay", json={"amount": 900_000},
                       headers=h).status_code == 400              # qoldiqdan ko'p
    item = client.get("/api/debts", headers=h).json()["qarz_oldim"]["items"]["som"][0]
    assert item["amount"] == 750_000 and item["original"] == 1_000_000


# --------------------------------------------------------- migratsiya --

def test_migration_links_nameless_payments(tmp_path, monkeypatch):
    sys.path.insert(0, str(Path(__file__).resolve().parents[1] / "scripts"))
    import _common
    import link_debt_payments as script
    monkeypatch.setattr(_common, "BACKUP_DIR", tmp_path)
    debt = _debt()
    pays = [db.add_transaction(UID, "qarz_qaytardim", amt, "qarz",
                               occurred_on=TODAY.isoformat())
            for amt in (1_000_000, 50_000)]
    found = {c["id"]: c for c in script.find_candidates()}
    assert all(found[p]["debt_id"] == debt for p in pays)
    assert script.apply(list(found.values())) == 2
    assert all(db.get_transaction(UID, p)["repays_id"] == debt for p in pays)
    assert _remaining(debt) == 8_950_000                          # hisobotdagi #335

    backup = next(tmp_path.glob("debtlink-*.json"))
    script.rollback(str(backup))
    assert all(db.get_transaction(UID, p)["repays_id"] is None for p in pays)
