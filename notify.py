"""Avtomatik xabarlar: yuborish tezligi, bloklanganlar va kimga nima boradi.

Hamma rejalashtirilgan va ommaviy xabar shu yerdagi `send()` orqali
ketadi:

  * **Tezlik.** Telegram botga umumiy ~30 xabar/soniya beradi. Bir
    vaqtda bir nechta vazifa ishlashi mumkin (soatlik eslatma va
    dushanbadagi xulosa bir paytga tushadi), shuning uchun chegara
    vazifa ichida emas, JARAYON bo'yicha umumiy: soniyasiga ko'pi bilan
    `MAX_PER_SECOND`. 429 (RetryAfter) kelsa — aytilgan vaqt kutiladi.
  * **Bloklanganlar.** 403 (Forbidden) — odam botni bloklagan. U
    `users.bot_blocked_at` bilan belgilanadi va hech bir vazifa unga
    qayta urinmaydi. Odam botga yana yozsa belgi o'zi olinadi
    (`db.get_or_create_user`).

Bepul foydalanuvchilar uchun qoidalar (`free_policy`):

  * oxirgi yozuvdan 14 kun o'tgan bo'lsa — faqat haftalik xulosa;
  * 30 kun o'tgan bo'lsa — hech qanday avtomatik xabar;
  * yana yozuv kiritsa — odatiy rejim o'zi tiklanadi (hisob har safar
    oxirgi yozuv sanasidan qilinadi).

PRO (sinov, obuna) foydalanuvchilarga bu qoidalar qo'llanmaydi — ular
avvalgidek xabar oladi; faqat bloklanganlar hamma uchun chiqariladi.
"""

from __future__ import annotations

import asyncio
import logging
import time

from telegram.error import Forbidden, RetryAfter

import db

log = logging.getLogger("tanga.notify")

MAX_PER_SECOND = 25

# Bepul foydalanuvchi uchun faollik chegaralari (kun).
QUIET_AFTER_DAYS = 14      # bundan keyin faqat haftalik xulosa
SILENT_AFTER_DAYS = 30     # bundan keyin hech narsa

DAILY = "daily"
WEEKLY = "weekly"
MONTHLY = "monthly"


class RateLimiter:
    """Jarayon bo'yicha umumiy: ketma-ket ikki xabar orasida kamida 1/N soniya."""

    def __init__(self, per_second: float):
        self.interval = 1.0 / per_second
        self._lock = asyncio.Lock()
        self._next = 0.0

    async def wait(self) -> None:
        async with self._lock:
            now = time.monotonic()
            if self._next > now:
                await asyncio.sleep(self._next - now)
                now = self._next
            self._next = now + self.interval


limiter = RateLimiter(MAX_PER_SECOND)


async def send(bot, user_id: int, text: str, **kwargs) -> bool:
    """Xabar yuboradi. Qaytaradi: yetdimi.

    Forbidden — odam botni bloklagan: belgilanadi, qayta urinilmaydi.
    RetryAfter — Telegram aytgan vaqt kutilib, bir marta qayta uriladi.
    Boshqa xatolar yuqoriga chiqariladi (vazifa o'zi log qiladi).
    """
    for attempt in (1, 2):
        await limiter.wait()
        try:
            await bot.send_message(user_id, text, **kwargs)
            return True
        except Forbidden:
            db.mark_bot_blocked(user_id)
            log.info("Botni bloklagan: %s — belgilandi", user_id)
            return False
        except RetryAfter as exc:
            if attempt == 2:
                raise
            delay = exc.retry_after
            seconds = delay.total_seconds() if hasattr(delay, "total_seconds") else float(delay)
            log.warning("Telegram tezlik chegarasi: %.1f s kutilmoqda", seconds)
            await asyncio.sleep(seconds)
    return False


def free_policy(inactive_days: int | None) -> set[str]:
    """Bepul foydalanuvchiga qaysi avtomatik xabarlar boradi.

    `inactive_days` — oxirgi yozuvdan beri o'tgan kunlar (yozuv umuman
    bo'lmasa — ro'yxatdan o'tgandan beri).
    """
    days = inactive_days or 0
    if days >= SILENT_AFTER_DAYS:
        return set()
    if days >= QUIET_AFTER_DAYS:
        return {WEEKLY}
    return {DAILY, WEEKLY, MONTHLY}
