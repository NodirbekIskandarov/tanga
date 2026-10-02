"""/xabar_yubor — mavjud foydalanuvchilarga bir martalik xabar (4.6).

HECH NARSA AVTOMATIK YUBORILMAYDI. Oqim:

  1. /xabar_yubor            — standart matn (har kim o'z tilida) yoki
     /xabar_yubor <matn>     — o'z matningiz (HTML, hammaga bir xil).
     Bot oluvchilar sonini va xabarni AYNAN qanday ko'rinishini ko'rsatadi.
  2. «👁 Menga sinov»        — xabar egaga yuboriladi (HTML xatosi shu
                               yerda chiqadi, foydalanuvchilarga emas).
  3. «✅ Yuborish» -> «Ha, N ta odamga yuborish» — ikki bosqichli tasdiq.
  4. Yuborish fonda, Telegram tezlik chegarasidan past (soniyasiga ~20);
     oxirida hisobot: yetdi / botni bloklagan / boshqa xato.

Loyiha 1 soat yashaydi. Bir vaqtda faqat bitta yuborish.
"""

from __future__ import annotations

import asyncio
import logging
import time

from telegram import InlineKeyboardButton, InlineKeyboardMarkup, Update
from telegram.constants import ParseMode
from telegram.error import Forbidden
from telegram.ext import ContextTypes

import config
import db
import i18n
import reports

log = logging.getLogger("tanga.broadcast")

DRAFT_TTL = 3600
SEND_DELAY = 0.05


def _price(value: int) -> str:
    return reports.fmt_money(value, "som")


def default_text(lang: str) -> str:
    """Standart matn foydalanuvchi tilida; asoschilar taklifi joy bo'lsa."""
    founders = ""
    offer = config.purchasable_plan("f12")
    yearly = config.plan_by_code("12m")
    if offer and yearly:
        founders = i18n.t(lang, "broadcast_founders", price=_price(offer["price"]),
                          yearly=_price(yearly["price"]),
                          total=config.FOUNDERS_LIMIT, left=offer["left"])
    return i18n.t(lang, "broadcast_default", founders=founders)


def text_for(draft: dict, user_id: int) -> str:
    if draft["custom"] is not None:
        return draft["custom"]
    return default_text(i18n.normalize(db.get_lang(user_id)))


def _keyboard(n: int) -> InlineKeyboardMarkup:
    return InlineKeyboardMarkup([
        [InlineKeyboardButton("👁 Menga sinov", callback_data="bc:test")],
        [InlineKeyboardButton(f"✅ Yuborish ({n} ta)", callback_data="bc:ask")],
        [InlineKeyboardButton("❌ Bekor", callback_data="bc:cancel")],
    ])


def _plans_button() -> InlineKeyboardMarkup:
    return InlineKeyboardMarkup([[InlineKeyboardButton(
        "💎 Tanga PRO", callback_data="pro:broadcast")]])


def _draft(context, owner_id: int) -> dict | None:
    draft = context.bot_data.setdefault("broadcast", {}).get(owner_id)
    if draft and time.time() - draft["created"] > DRAFT_TTL:
        context.bot_data["broadcast"].pop(owner_id, None)
        return None
    return draft


async def cmd_broadcast(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """Faqat ega uchun (bot.py dagi owner_only bilan o'raladi)."""
    owner_id = update.effective_user.id
    raw = update.effective_message.text or ""
    parts = raw.split(maxsplit=1)
    custom = parts[1].strip() if len(parts) > 1 else None

    audience = db.broadcast_audience()
    context.bot_data.setdefault("broadcast", {})[owner_id] = {
        "custom": custom, "ids": audience, "created": time.time(), "sending": False,
    }
    lang = i18n.normalize(db.get_lang(owner_id))
    kind = "o'z matningiz (hammaga bir xil)" if custom else \
        "standart matn (har kim o'z tilida: lotin, kirill yoki rus)"
    await update.effective_message.reply_text(
        f"📣 <b>Xabar loyihasi</b>\n\n"
        f"Oluvchilar: <b>{len(audience)}</b> ta — oxirgi 30 kunda yozuv "
        f"kiritgan, bloklanmagan, shartlarga rozi bo'lganlar.\n"
        f"Matn: {kind}.\n\n"
        f"Quyida — foydalanuvchi ko'radigan ko'rinish. Hech narsa hali "
        f"yuborilmadi.",
        parse_mode=ParseMode.HTML)
    try:
        await update.effective_message.reply_text(
            custom if custom is not None else default_text(lang),
            parse_mode=ParseMode.HTML, reply_markup=_keyboard(len(audience)))
    except Exception as exc:
        context.bot_data["broadcast"].pop(owner_id, None)
        await update.effective_message.reply_text(
            f"⚠️ Matnni ko'rsatib bo'lmadi (HTML xatosi bo'lishi mumkin): {exc}\n"
            "Tuzatib, /xabar_yubor ni qayta yuboring.")


async def on_broadcast_callback(update: Update, context: ContextTypes.DEFAULT_TYPE):
    query = update.callback_query
    owner_id = update.effective_user.id
    if owner_id not in config.OWNER_IDS:
        await query.answer()
        return
    action = (query.data or "").split(":", 1)[1]
    draft = _draft(context, owner_id)
    if draft is None:
        await query.answer("Loyiha eskirgan. /xabar_yubor ni qayta yuboring.",
                           show_alert=True)
        return

    if action == "cancel":
        context.bot_data["broadcast"].pop(owner_id, None)
        await query.answer("Bekor qilindi")
        await query.edit_message_reply_markup(None)
        return

    if action == "test":
        await query.answer("Sizga yuborildi")
        await context.bot.send_message(owner_id, text_for(draft, owner_id),
                                       parse_mode=ParseMode.HTML,
                                       reply_markup=_plans_button())
        return

    if action == "ask":
        await query.answer()
        await query.message.reply_text(
            f"⚠️ Rostdan <b>{len(draft['ids'])}</b> ta foydalanuvchiga "
            f"yuborilsinmi? Yuborilgan xabarni qaytarib bo'lmaydi.",
            parse_mode=ParseMode.HTML,
            reply_markup=InlineKeyboardMarkup([
                [InlineKeyboardButton(f"Ha, {len(draft['ids'])} ta odamga yuborish",
                                      callback_data="bc:send")],
                [InlineKeyboardButton("Yo'q", callback_data="bc:cancel")],
            ]))
        return

    if action == "send":
        if draft["sending"]:
            await query.answer("Yuborish allaqachon ketyapti", show_alert=True)
            return
        draft["sending"] = True
        await query.answer("Yuborilmoqda…")
        await query.edit_message_reply_markup(None)
        context.application.create_task(_send_all(context, owner_id, draft))


async def _send_all(context, owner_id: int, draft: dict) -> None:
    ok = blocked = failed = 0
    for user_id in draft["ids"]:
        try:
            await context.bot.send_message(user_id, text_for(draft, user_id),
                                           parse_mode=ParseMode.HTML,
                                           reply_markup=_plans_button())
            db.log_event(user_id, "xabar_olindi")
            ok += 1
        except Forbidden:
            blocked += 1
        except Exception:
            failed += 1
            log.info("Xabar yuborilmadi: %s", user_id, exc_info=True)
        await asyncio.sleep(SEND_DELAY)
    context.bot_data.get("broadcast", {}).pop(owner_id, None)
    log.info("Xabar yuborildi: %s ta, bloklagan %s, xato %s", ok, blocked, failed)
    await context.bot.send_message(
        owner_id,
        f"📣 <b>Yuborish tugadi</b>\n\n✅ Yetdi: {ok}\n🚫 Botni bloklagan: {blocked}"
        f"\n⚠️ Boshqa xato: {failed}",
        parse_mode=ParseMode.HTML)
