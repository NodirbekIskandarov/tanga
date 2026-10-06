"""Telegramdagi bot profili matnlari — bitta joyda.

Bot ishga tushganda (`bot._post_init`) shu matnlarni har bir til uchun
o'rnatadi (faqat o'zgarganini), `setup_bot_profile.py` ham shu yerdan
oladi. Ilgari matn ikki faylda takrorlanardi va tilga xos nusxasi
(«uz», «ru») yangilanmay qolardi — Telegram esa foydalanuvchiga
standartdan oldin o'z tilidagi matnni ko'rsatadi.

Kalit — Telegram til kodi; bo'sh satr — standart (til aniqlanmaganda).
Telegram o'zbek lotin/kirillni ajratmaydi, ikkalasi ham «uz».
"""

import config

LANGS = ["", "uz", "ru"]

NAME = {"": "Tanga", "uz": "Tanga", "ru": "Tanga"}

# Chat ro'yxatida va qidiruvda (120 belgigacha).
SHORT = {
    "": ("Xarajatlaringizni oddiy tilda yozing — men hisoblab, hisobot "
         "qilib beraman. Bepul, 7 kun PRO sovg'a."),
    "ru": ("Пишите расходы обычным текстом — я посчитаю и составлю отчёт. "
           "Бесплатно, 7 дней PRO в подарок."),
}
SHORT["uz"] = SHORT[""]

# «Start» tugmasi ustida (512 belgigacha).
DESCRIPTION = {
    "": (
        "Xarajatlaringizni oddiy tilda yozing — qolganini men qilaman.\n\n"
        "«obedga 45 ming» deb yozsangiz kifoya: summani ajrataman, "
        "kategoriyaga qo'yaman va istalgan payt hisobot beraman.\n\n"
        "• Chek suratini yuborsangiz — har bir mahsulotni o'qib chiqaman\n"
        "• Kunlik, haftalik va oylik hisobot\n"
        "• Maqsad qo'ying — qachon erishishingizni hisoblayman\n"
        "• Qarzlar — kimga qancha, kim qaytardi, esdan chiqmaydi\n"
        "• So'm va dollar bitta hisobda birlashadi\n\n"
        "Asosiy hisob bepul, birinchi 7 kun — to'liq PRO.\n"
        "Boshlash uchun «Start» bosing."
    ),
    "ru": (
        "Пишите расходы обычным текстом — остальное сделаю я.\n\n"
        "Достаточно написать «обед 45 тысяч»: выделю сумму, определю "
        "категорию и в любой момент покажу отчёт.\n\n"
        "• Пришлите фото чека — распознаю каждую позицию\n"
        "• Отчёты за день, неделю и месяц\n"
        "• Поставьте цель — посчитаю, когда вы её достигнете\n"
        "• Долги: кому и сколько, кто вернул — ничего не забудется\n"
        "• Сумы и доллары объединяются в одном учёте\n\n"
        "Основной учёт — бесплатно. Первые 7 дней — полный PRO в подарок.\n"
        "Нажмите «Start», чтобы начать."
    ),
}
DESCRIPTION["uz"] = DESCRIPTION[""]

# Ovoz haqidagi qator FAQAT hammaga ochilganda (VOICE_ENABLED va beta
# ro'yxat bo'sh): tavsifda va'da qilingan narsa ishlab turishi kerak.
if config.VOICE_ENABLED and not config.VOICE_BETA_USER_IDS:
    # Tavsif 512 belgidan oshmasligi kerak: ovoz qatori chek qatori bilan
    # birlashtiriladi (alohida qator sig'maydi).
    _VOICE_LINES = {
        "": ("• Chek suratini yuborsangiz — har bir mahsulotni o'qib chiqaman\n",
             "• Chek surati yoki ovozli xabar — o'zim o'qib chiqaman\n"),
        "ru": ("• Пришлите фото чека — распознаю каждую позицию\n",
               "• Фото чека или голосовое сообщение — распознаю сам\n"),
    }
    for _key, (_anchor, _line) in _VOICE_LINES.items():
        DESCRIPTION[_key] = DESCRIPTION[_key].replace(_anchor, _line)
    DESCRIPTION["uz"] = DESCRIPTION[""]

LIMITS = {"name": 64, "short_description": 120, "description": 512}
