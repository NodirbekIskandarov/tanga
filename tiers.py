"""Bepul va PRO chegaralari (4.3).

| Imkoniyat              | Bepul               | PRO                        |
|------------------------|---------------------|----------------------------|
| Matnli yozuv           | cheksiz*            | cheksiz*                   |
| Bugun/hafta/joriy oy   | ha                  | ha                         |
| Chek o'qish            | oyiga 3 ta          | kuniga 10 ta*; sinovda jami 10 ta |
| Tarix va tahlil        | joriy oy            | barcha davrlar             |
| Mini App               | joriy oy            | to'liq                     |
| Byudjet                | —                   | ha                         |
| AI savol-javob         | kuniga 3 ta         | cheksiz*                   |
| Ovozli xabar           | kuniga 5 ta         | kuniga 40 ta*              |
| CSV eksport            | ha**                | ha                         |

 *  «adolatli foydalanish» kunlik chegarasi bilan (config.LIMIT_*):
    oddiy odam yetmaydi, skript bilan cheksiz AI chaqiruvi to'xtaydi.
    Bepul va sinov darajasida yana kishi boshiga oylik AI chegarasi bor
    (config.user_monthly_budget_usd, bot._budget_ok).
 ** CSV hamma uchun bepul: o'z ma'lumotini olish — huquq, PRO
    imkoniyati emas (maxfiylik siyosatida shunday yozilgan).

Daraja `db.access_status()["tier"]` dan olinadi. Bu modul faqat qaror
qabul qiladi — xabar matni va tugmalar bot.py da.
"""

from __future__ import annotations

from datetime import date, datetime, timedelta

import config
import db

FREE = "free"
PRO = "pro"

# Faqat PRO da ochiq imkoniyatlar.
PRO_ONLY = {"history", "budget",
            "goals_many", "goals_forecast", "savings_auto", "debt_reminders"}


def is_pro(access: dict | None) -> bool:
    return bool(access) and access.get("tier") == PRO


def allows(access: dict | None, feature: str) -> bool:
    return is_pro(access) or feature not in PRO_ONLY


def today() -> date:
    return datetime.now(config.TZ).date()


def month_start(day: date | None = None) -> date:
    return (day or today()).replace(day=1)


def next_month_start(day: date | None = None) -> date:
    first = month_start(day)
    return (first.replace(day=28) + timedelta(days=4)).replace(day=1)


def history_allowed(access: dict | None, start: date) -> bool:
    """Bepul darajada faqat joriy oy (va unga tegib turgan hafta) ochiq."""
    return is_pro(access) or start >= month_start() - timedelta(days=6)


def check(user_id: int, access: dict | None, operation: str) -> dict | None:
    """AI amali bajarilishi mumkinmi. Mumkin bo'lsa None.

    Aks holda: {"type": "paywall" | "limit", "feature": ..., "limit": N,
    "resets": "tomorrow" | "next_month"}. «paywall» — Bepul daraja
    chegarasi (PRO yechadi), «limit» — adolatli foydalanish chegarasi
    (hamma uchun bir xil, ertaga yangilanadi).
    """
    pro = is_pro(access)
    if operation == "matn":
        if db.count_today(user_id, "matn") >= config.LIMIT_TEXT_PER_DAY:
            return {"type": "limit", "feature": "matn",
                    "limit": config.LIMIT_TEXT_PER_DAY, "resets": "tomorrow"}
        return None

    if operation == "chek":
        if not pro:
            used = db.count_since(user_id, "chek", month_start())
            if used >= config.FREE_RECEIPTS_PER_MONTH:
                return {"type": "paywall", "feature": "receipts",
                        "limit": config.FREE_RECEIPTS_PER_MONTH,
                        "resets": "next_month"}
            return None
        # Sinov — to'liq PRO, lekin cheklar soni butun sinov uchun
        # cheklangan: chek eng qimmat amal, sinovni esa yangi akkaunt
        # bilan qayta olish mumkin.
        if (access or {}).get("status") == "trial" and config.TRIAL_RECEIPTS_TOTAL > 0:
            used = db.count_since(user_id, "chek", date.min)
            if used >= config.TRIAL_RECEIPTS_TOTAL:
                return {"type": "paywall", "feature": "trial_receipts",
                        "limit": config.TRIAL_RECEIPTS_TOTAL, "resets": "never"}
        if db.count_today(user_id, "chek") >= config.LIMIT_RECEIPT_PER_DAY:
            return {"type": "limit", "feature": "chek",
                    "limit": config.LIMIT_RECEIPT_PER_DAY, "resets": "tomorrow"}
        return None

    if operation == "savol":
        limit = config.LIMIT_QA_PER_DAY if pro else config.FREE_QA_PER_DAY
        if db.count_today(user_id, "savol") >= limit:
            return {"type": "limit" if pro else "paywall", "feature": "qa",
                    "limit": limit, "resets": "tomorrow"}
        return None

    if operation == "ovoz":
        limit = config.LIMIT_VOICE_PER_DAY if pro else config.FREE_VOICE_PER_DAY
        if db.count_today(user_id, "ovoz") >= limit:
            return {"type": "limit" if pro else "paywall", "feature": "voice",
                    "limit": limit, "resets": "tomorrow"}
        return None

    return None


def receipts_left(user_id: int, access: dict | None) -> int | None:
    """Bepul darajada shu oy qolgan cheklar. PRO uchun None (cheklanmagan)."""
    if is_pro(access):
        return None
    used = db.count_since(user_id, "chek", month_start())
    return max(0, config.FREE_RECEIPTS_PER_MONTH - used)
