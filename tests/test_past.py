"""QA hisoboti, 4-bo'lim (past ustuvorlik) va M12 — bot repozitoriysi."""

import asyncio
import importlib.machinery
import importlib.util
from pathlib import Path
from types import SimpleNamespace

import pytest
from fastapi.testclient import TestClient

import config
import db
import i18n
import reports

ROOT = Path(__file__).resolve().parents[1]


# ------------------------------------------------ «qarz | qarz» takrori --

def test_debt_confirmation_does_not_repeat_category():
    row = {"turi": "qarz_qaytardim", "summa": 500_000, "valyuta": "som",
           "kategoriya": "qarz", "izoh": "qarz", "shaxs": "Akmal", "sana": "2026-10-05"}
    text = reports.saved_text([row])
    assert "📝" not in text and "Akmal" in text

    row["izoh"] = "kreditga"
    assert "📝 kreditga" in reports.saved_text([row])             # haqiqiy izoh qoladi


# --------------------------------------------- ega uchun /obuna matni --

def test_owner_plans_page_has_no_pick_line():
    import bot
    with_pick = bot.plans_text(lang="uz")
    without = bot.plans_text(lang="uz", with_pick=False)
    assert "Tarifni tanlang" in with_pick and "Tarifni tanlang" not in without


# --------------------------------------------- ruscha yordamchi matn --

def test_menu_placeholder_follows_language():
    import bot
    assert bot.main_menu("uz").input_field_placeholder.startswith("Xarajat")
    assert bot.main_menu("ru").input_field_placeholder.startswith("Напишите")


# --------------------------------------------------- Mini App chegarasi --

def test_miniapp_rejects_absurd_amount():
    import hashlib, hmac, json, time
    from urllib.parse import urlencode
    import webapp
    webapp._rate.clear()
    db.get_or_create_user(31, "T", None)
    db.set_consent(31, config.CONSENT_VERSION)
    pairs = {"auth_date": str(int(time.time())), "user": json.dumps({"id": 31, "first_name": "T"})}
    check = "\n".join(f"{k}={v}" for k, v in sorted(pairs.items()))
    secret = hmac.new(b"WebAppData", config.TELEGRAM_TOKEN.encode(), hashlib.sha256).digest()
    pairs["hash"] = hmac.new(secret, check.encode(), hashlib.sha256).hexdigest()
    h = {"X-Telegram-Init-Data": urlencode(pairs)}
    client = TestClient(webapp.app)
    body = {"kind": "chiqim", "amount": 1e300, "category": "transport"}
    assert client.post("/api/transactions", json=body, headers=h).status_code == 422
    body["amount"] = 50_000
    assert client.post("/api/transactions", json=body, headers=h).status_code == 201


# ------------------------------------------------------ M12 zaxira skripti --

def _backup_module():
    path = ROOT / "deploy" / "tanga-backup"
    loader = importlib.machinery.SourceFileLoader("tanga_backup", str(path))
    spec = importlib.util.spec_from_loader("tanga_backup", loader)
    module = importlib.util.module_from_spec(spec)
    loader.exec_module(module)
    return module


class _Enc:
    name = "shaxsiy-test.db.enc"

    def __init__(self, size):
        self._size = size

    def stat(self):
        return SimpleNamespace(st_size=self._size)

    def read_bytes(self):
        return b"x" * 10


@pytest.fixture
def backup(monkeypatch):
    module = _backup_module()
    monkeypatch.setattr(module, "env", lambda name: {"TELEGRAM_TOKEN": "123:t",
                                                     "OWNER_IDS": "777"}.get(name, ""))
    module.texts, module.uploads = [], []
    monkeypatch.setattr(module, "send_text_to_owners", lambda t: module.texts.append(t))

    class Resp:
        def read(self):
            return b'{"ok":true}'

        def __enter__(self):
            return self

        def __exit__(self, *a):
            return False

    def fake_urlopen(req, timeout=0):
        module.uploads.append(req.data)
        return Resp()

    monkeypatch.setattr("urllib.request.urlopen", fake_urlopen)
    return module


def test_small_backup_is_uploaded_without_warning(backup):
    backup.send_to_telegram(_Enc(150_000), "Zaxira")
    assert len(backup.uploads) == 1 and backup.texts == []
    assert b"chegarasi" not in backup.uploads[0]


def test_large_backup_warns_in_caption(backup):
    backup.send_to_telegram(_Enc(40_000_000), "Zaxira")
    assert len(backup.uploads) == 1
    assert "50 MB" in backup.uploads[0].decode("utf-8", "ignore")


def test_oversized_backup_is_not_silently_dropped(backup):
    backup.send_to_telegram(_Enc(60_000_000), "Zaxira")
    assert backup.uploads == []                                  # yuborishga urinilmaydi
    assert len(backup.texts) == 1 and "YUBORILMADI" in backup.texts[0]


# ------------------------------------------------ albomning kech rasmi --

class _Msg:
    def __init__(self, group):
        self.text, self.photo, self.document = "", [SimpleNamespace(file_id="LATE")], None
        self.caption, self.media_group_id, self.chat_id = None, group, 77
        self.replies = []

    async def reply_text(self, text, **kw):
        self.replies.append(text)
        return self


def _album_update(group):
    msg = _Msg(group)
    user = SimpleNamespace(id=77, first_name="T", username=None)
    return SimpleNamespace(effective_user=user, effective_message=msg, message=msg,
                           effective_chat=SimpleNamespace(id=77, type="private"),
                           callback_query=None)


def test_late_album_photo_is_not_read_as_separate_receipt(monkeypatch):
    import bot
    db.get_or_create_user(77, "T", None)
    db.set_consent(77, config.CONSENT_VERSION)

    async def must_not_download(context, message):
        raise AssertionError("kech rasm yuklab olinmasligi / o'qilmasligi kerak")

    monkeypatch.setattr(bot, "_download_receipt_file", must_not_download)
    bot._done_albums.set("G9", True)
    u = _album_update("G9")
    ctx = SimpleNamespace(bot=None, user_data={}, args=[], bot_data={})
    asyncio.run(bot.on_photo(u, ctx))
    assert u.message.replies and "Uzun chek" in u.message.replies[0]


def test_flushed_album_is_remembered(monkeypatch):
    import ai
    import bot

    async def fake_process(update, context, images, caption, replaces=None):
        return None

    monkeypatch.setattr(bot, "_process_receipt", fake_process)
    monkeypatch.setattr(bot, "ALBUM_WAIT_SECONDS", 0)
    bot._albums.set("G10", {"images": [("x", "image/jpeg")], "caption": "", "task": None})
    asyncio.run(bot._flush_album("G10", _album_update("G10"), SimpleNamespace()))
    assert "G10" in bot._done_albums


def test_russian_is_no_longer_marked_beta():
    """K11: rus tili to'liq (tests/test_russian.py) — «beta» belgisi olib tashlandi."""
    assert "beta" not in i18n.LANGS["ru"].lower()
    assert "beta" not in i18n.LANGS["uz"].lower()
