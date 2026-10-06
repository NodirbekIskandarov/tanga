"""Ikki tilli interfeys: o'zbek (uz) va rus (ru).

Matnlar shu yerda — kodning ichida emas. Yangi til qo'shish uchun
har bir kalitga uchinchi qiymat qo'shilsa yetadi.

Kalit topilmasa o'zbekchasi qaytariladi, ya'ni tarjima yetishmasa ham
bot ishlaydi. Uzun qo'llanma (/qollanma) hozircha faqat o'zbekcha.
"""

from __future__ import annotations

import translit

# uzc — o'zbek kirill. Uning matnlari alohida yozilmaydi: lotinchasidan
# avtomatik o'giriladi (translit.py), shunda matn o'zgarganda ikkala
# yozuv ham birdan yangilanadi.
LANGS = {
    "uz": "🇺🇿 O'zbekcha (lotin)",
    "uzc": "🇺🇿 Ўзбекча (кирилл)",
    "ru": "🇷🇺 Русский",
}
DEFAULT = "uz"


def normalize(lang: str | None) -> str:
    lang = (lang or "").lower().strip().replace("-", "").replace("_", "")
    if lang in ("uzcyrl", "cyr", "kirill"):
        lang = "uzc"
    return lang if lang in LANGS else DEFAULT


# --------------------------------------------------------------------------- #
# Tugmalar. Menyu matn sifatida keladi, shuning uchun ikkala tilning
# tugmalari ham handlerga bog'lanadi (pastdagi menu_lookup).
# --------------------------------------------------------------------------- #

BUTTONS = {
    "today":    {"uz": "📊 Bugun",       "ru": "📊 Сегодня"},
    "week":     {"uz": "📅 Hafta",       "ru": "📅 Неделя"},
    "month":    {"uz": "🗓 Oy",          "ru": "🗓 Месяц"},
    "year":     {"uz": "📈 Yil",         "ru": "📈 Год"},
    "recent":   {"uz": "🧾 Oxirgi",      "ru": "🧾 Последние"},
    "debts":    {"uz": "🤝 Qarzlar",     "ru": "🤝 Долги"},
    "longbill": {"uz": "🧾 Uzun chek",   "ru": "🧾 Длинный чек"},
    "csv":      {"uz": "📤 CSV",         "ru": "📤 CSV"},
    "guide":    {"uz": "📖 Qo'llanma",   "ru": "📖 Инструкция"},
    "budget":   {"uz": "💰 Byudjet",     "ru": "💰 Бюджет"},
    "referral": {"uz": "🎁 Taklif",      "ru": "🎁 Пригласить"},
    "subs":     {"uz": "💎 Obuna",       "ru": "💎 Подписка"},
    "panel":    {"uz": "📱 Panel",       "ru": "📱 Панель"},
    "goals":    {"uz": "🎯 Maqsadlar",   "ru": "🎯 Цели"},
    "pro":      {"uz": "💎 PRO",         "ru": "💎 PRO"},
    "more":     {"uz": "⚙️ Yana",        "ru": "⚙️ Ещё"},
    "ready":    {"uz": "✅ Tayyor",      "ru": "✅ Готово"},
    "cancel":   {"uz": "❌ Bekor",       "ru": "❌ Отмена"},
}


T = {
    # ---- Kirish va umumiy ----
    # /start — 3–4 qator: salom, uchta misol, (sinov) va bitta chaqiruv.
    "welcome": {
        "uz": ("👋 <b>Salom{name}!</b> Men Tanga — pulingiz hisobini yuritaman.\n"
               "Masalan: <i>«Taksiga 25 ming»</i>, <i>«Oylik 8 mln tushdi»</i> "
               "yoki chek rasmi.\n"
               "{trial}"
               "<b>Birinchi xarajatingizni yozing 👇</b>"),
        "ru": ("👋 <b>Здравствуйте{name}!</b> Я Tanga — веду учёт ваших денег.\n"
               "Например: <i>«Такси 25 тысяч»</i>, <i>«Зарплата 8 млн»</i> "
               "или фото чека.\n"
               "{trial}"
               "<b>Напишите свой первый расход 👇</b>"),
    },
    "welcome_back": {
        "uz": ("👋 <b>Xush kelibsiz{name}!</b> Yozishda davom eting — "
               "masalan <i>«Taksiga 25 ming»</i>.\n"
               "{status}"
               "Barcha imkoniyatlar: /yordam"),
        "ru": ("👋 <b>С возвращением{name}!</b> Продолжайте записывать — "
               "например <i>«Такси 25 тысяч»</i>.\n"
               "{status}"
               "Все возможности: /yordam"),
    },
    "start_trial": {"uz": "🎁 PRO sinov: {days} kun qoldi.",
                    "ru": "🎁 Пробный PRO: осталось {days} дн."},
    "start_pro": {"uz": "✅ PRO faol: {days} kun qoldi.",
                  "ru": "✅ PRO активен: осталось {days} дн."},
    "start_free": {"uz": "🆓 Bepul versiya · PRO: /obuna",
                   "ru": "🆓 Бесплатная версия · PRO: /obuna"},
    "first_entry": {
        "uz": ("🎉 <b>Ajoyib!</b> Birinchi yozuv saqlandi.\n"
               "Endi oylik kirimingizni yozing (<i>«oylik 8 mln tushdi»</i>) "
               "yoki maqsad qo'ying: 🎯 Maqsadlar."),
        "ru": ("🎉 <b>Отлично!</b> Первая запись сохранена.\n"
               "Теперь запишите доход (<i>«зарплата 8 млн»</i>) "
               "или поставьте цель: 🎯 Цели."),
    },
    "guide_menu": {
        "uz": ("📖 <b>Qo'llanma</b>\n\nKerakli bo'limni tanlang.\n"
               "<i>Tez boshlash: shunchaki yozing — «taksiga 25 ming».</i>"),
        "ru": ("📖 <b>Инструкция</b>\n\nВыберите раздел.\n"
               "<i>Быстрый старт: просто напишите — «такси 25 тысяч».</i>"),
    },
    "guide_back": {"uz": "⬅️ Bo'limlar", "ru": "⬅️ Разделы"},
    "more_menu": {"uz": "⚙️ <b>Yana</b>", "ru": "⚙️ <b>Ещё</b>"},
    "blocked": {
        "uz": "🚫 Hisobingiz bloklangan.",
        "ru": "🚫 Ваш аккаунт заблокирован.",
    },
    "closed_beta": {
        "uz": "Bot hozircha yopiq sinovda.\nSizning ID: {id}",
        "ru": "Бот пока в закрытом тестировании.\nВаш ID: {id}",
    },
    "ai_error": {
        "uz": "⚠️ AI bilan bog'lanishda xatolik. Birozdan keyin urinib ko'ring.",
        "ru": "⚠️ Ошибка связи с AI. Попробуйте чуть позже.",
    },
    "not_understood": {
        "uz": "Tushunmadim. Summani aniq yozing, masalan: <code>obedga 45 ming</code>",
        "ru": "Не понял. Укажите сумму, например: <code>обед 45 тысяч</code>",
    },

    # ---- Til ----
    "lang_choose": {
        "uz": "🌐 <b>Til</b>\n\nInterfeys tilini tanlang:",
        "ru": "🌐 <b>Язык</b>\n\nВыберите язык интерфейса:",
    },
    "lang_set": {
        "uz": "✅ Til o'zbekchaga o'zgartirildi.",
        "ru": "✅ Язык изменён на русский.",
    },

    # ---- Obuna va to'lov ----
    "owner_no_sub": {
        "uz": "👑 Siz bot egasisiz — obuna kerak emas, cheksiz foydalanasiz.",
        "ru": "👑 Вы владелец бота — подписка не нужна, доступ без ограничений.",
    },

    "pay_title": {"uz": "💳 <b>To'lov</b>", "ru": "💳 <b>Оплата</b>"},
    "pay_body": {
        "uz": ("Tarif: <b>{plan}</b>\n"
               "To'lov summasi: <b>{price}</b>\n\n"
               "━━━━━━━━━━━━━━━━━━\n"
               "<b>Karta raqami</b>\n"
               "<code>{card}</code>\n"
               "👤 {holder}{bank}\n"
               "━━━━━━━━━━━━━━━━━━\n\n"
               "<b>Keyingi qadam:</b>\n"
               "1️⃣ Yuqoridagi kartaga <b>{price}</b> o'tkazing\n"
               "2️⃣ To'lov chekini shu yerga yuboring — <b>skrinshot rasm "
               "yoki PDF</b>\n"
               "3️⃣ Admin tekshirib tasdiqlaydi — obunangiz darhol faollashadi\n\n"
               "<i>Karta raqamini bosib nusxa olishingiz mumkin.</i>\n"
               "Savol bo'lsa: {contact}"),
        "ru": ("Тариф: <b>{plan}</b>\n"
               "Сумма к оплате: <b>{price}</b>\n\n"
               "━━━━━━━━━━━━━━━━━━\n"
               "<b>Номер карты</b>\n"
               "<code>{card}</code>\n"
               "👤 {holder}{bank}\n"
               "━━━━━━━━━━━━━━━━━━\n\n"
               "<b>Что дальше:</b>\n"
               "1️⃣ Переведите <b>{price}</b> на карту выше\n"
               "2️⃣ Отправьте чек сюда — <b>скриншот или PDF</b>\n"
               "3️⃣ Администратор проверит — подписка активируется сразу\n\n"
               "<i>Нажмите на номер карты, чтобы скопировать.</i>\n"
               "Вопросы: {contact}"),
    },
    "pay_no_card": {
        "uz": ("📨 <b>So'rovingiz qabul qilindi</b>\n\n"
               "Tarif: <b>{plan}</b> — {price}\n\n"
               "To'lov bo'yicha {contact} ga yozing."),
        "ru": ("📨 <b>Заявка принята</b>\n\n"
               "Тариф: <b>{plan}</b> — {price}\n\n"
               "По оплате напишите {contact}."),
    },
    "pay_cancelled": {
        "uz": "To'lov bekor qilindi. Tariflar: /obuna",
        "ru": "Оплата отменена. Тарифы: /obuna",
    },
    "proof_received": {
        "uz": ("✅ <b>Chek qabul qilindi</b>\n\n"
               "Tarif: <b>{plan}</b> — {price}\n\n"
               "Admin tekshirib chiqadi va tasdiqlangach sizga xabar keladi. "
               "Odatda bu bir necha soat ichida bo'ladi.\n\n"
               "Holatni ko'rish: /holat"),
        "ru": ("✅ <b>Чек получен</b>\n\n"
               "Тариф: <b>{plan}</b> — {price}\n\n"
               "Администратор проверит и вы получите уведомление. Обычно это "
               "занимает несколько часов.\n\n"
               "Статус: /holat"),
    },
    "proof_stale": {
        "uz": "Bu so'rov allaqachon hal qilingan. Yangi tarif tanlash: /obuna",
        "ru": "Эта заявка уже обработана. Выбрать тариф заново: /obuna",
    },

    # ---- Holat ----
    "status_owner": {
        "uz": "👑 <b>Bot egasi</b> — cheksiz foydalanish",
        "ru": "👑 <b>Владелец бота</b> — без ограничений",
    },
    "status_sub": {
        "uz": "✅ <b>Obuna faol</b>\nTugash sanasi: {until} ({days} kun qoldi)",
        "ru": "✅ <b>Подписка активна</b>\nДействует до: {until} (осталось {days} дн.)",
    },
    "status_trial": {
        "uz": "🎁 <b>Bepul sinov</b>\nTugash sanasi: {until} ({days} kun qoldi)",
        "ru": "🎁 <b>Пробный период</b>\nДействует до: {until} (осталось {days} дн.)",
    },
    "status_limits": {"uz": "<b>Bugungi limitlar:</b>", "ru": "<b>Лимиты на сегодня:</b>"},
    "status_rows": {"uz": "📒 Bazangizda {n} ta yozuv bor.",
                    "ru": "📒 В вашей базе {n} записей."},
    "status_extend_hint": {
        "uz": ("<i>Obunani hoziroq uzaytirsangiz, qolgan kunlar yo'qolmaydi — "
               "ustiga qo'shiladi.</i>"),
        "ru": ("<i>Продлите сейчас — оставшиеся дни не пропадут, они "
               "прибавятся к новому сроку.</i>"),
    },

    # ---- Byudjet ----
    "budget_intro": {
        "uz": ("💰 <b>Oylik byudjet</b>\n\n"
               "Kategoriyaga oylik chegara qo'ying — oshib ketsa ogohlantiraman.\n\n"
               "<b>O'rnatish:</b>\n"
               "<code>/byudjet oziq-ovqat 2 mln</code>\n"
               "<code>/byudjet transport 500 ming</code>\n\n"
               "<b>O'chirish:</b>\n"
               "<code>/byudjet transport o'chir</code>"),
        "ru": ("💰 <b>Месячный бюджет</b>\n\n"
               "Задайте лимит по категории — предупрежу при превышении.\n\n"
               "<b>Установить:</b>\n"
               "<code>/byudjet oziq-ovqat 2 mln</code>\n"
               "<code>/byudjet transport 500 ming</code>\n\n"
               "<b>Удалить:</b>\n"
               "<code>/byudjet transport o'chir</code>"),
    },
    "budget_title": {"uz": "💰 <b>Shu oylik byudjet</b>", "ru": "💰 <b>Бюджет на месяц</b>"},
    "budget_set": {
        "uz": ("✅ <b>{cat}</b> uchun oylik byudjet: <b>{amount}</b>\n\n"
               "80% va 100% ga yetganda ogohlantiraman."),
        "ru": ("✅ Бюджет на месяц для <b>{cat}</b>: <b>{amount}</b>\n\n"
               "Предупрежу при 80% и 100%."),
    },
    "budget_deleted": {"uz": "🗑 «{cat}» byudjeti o'chirildi.",
                       "ru": "🗑 Бюджет «{cat}» удалён."},
    "budget_bad_amount": {
        "uz": "Summani tushunmadim.\n\nMasalan: <code>/byudjet oziq-ovqat 2 mln</code>",
        "ru": "Не понял сумму.\n\nНапример: <code>/byudjet oziq-ovqat 2 mln</code>",
    },
    "budget_left": {"uz": "qoldi: {amount}", "ru": "осталось: {amount}"},
    "budget_over": {"uz": "⚠️ oshib ketdi: {amount}", "ru": "⚠️ превышено: {amount}"},
    "budget_alert_80": {
        "uz": "🟡 <b>{cat}</b> byudjetining {pct}% i sarflandi.\n\nQoldi: {left}",
        "ru": "🟡 Использовано {pct}% бюджета «{cat}».\n\nОсталось: {left}",
    },
    "budget_alert_100": {
        "uz": ("🔴 <b>{cat}</b> byudjeti oshib ketdi!\n\n"
               "Sarflandi: {spent}\nChegara: {limit}\nOshgan: {over}"),
        "ru": ("🔴 Бюджет «{cat}» превышен!\n\n"
               "Потрачено: {spent}\nЛимит: {limit}\nПревышение: {over}"),
    },

    # ---- Eslatma ----
    "reminder_intro": {
        "uz": ("🔔 <b>Kunlik eslatma</b>\n\n"
               "Har kuni belgilangan vaqtda kunlik xulosangizni yuboraman — "
               "yozishni unutmaslik uchun.\n\n"
               "<b>Yoqish:</b> <code>/eslatma 21</code> (soat 21:00)\n"
               "<b>O'chirish:</b> <code>/eslatma o'chir</code>"),
        "ru": ("🔔 <b>Ежедневное напоминание</b>\n\n"
               "Каждый день в выбранное время буду присылать итог дня — "
               "чтобы вы не забывали записывать.\n\n"
               "<b>Включить:</b> <code>/eslatma 21</code> (21:00)\n"
               "<b>Выключить:</b> <code>/eslatma o'chir</code>"),
    },
    "reminder_on": {
        "uz": ("🔔 Har kuni soat <b>{hour}:00</b> da eslataman.\n\n"
               "O'chirish: <code>/eslatma o'chir</code>"),
        "ru": ("🔔 Буду напоминать каждый день в <b>{hour}:00</b>.\n\n"
               "Выключить: <code>/eslatma o'chir</code>"),
    },
    "reminder_off": {"uz": "🔕 Kunlik eslatma o'chirildi.",
                     "ru": "🔕 Ежедневное напоминание выключено."},
    "reminder_bad_hour": {
        "uz": "Soatni 0 dan 23 gacha kiriting. Masalan: /eslatma 21",
        "ru": "Укажите час от 0 до 23. Например: /eslatma 21",
    },
    "daily_summary": {
        "uz": "🌙 <b>Bugungi xulosa</b>\n\n{n} ta yozuv · {parts}\n\nYana qo'shadigan narsa bormi?",
        "ru": "🌙 <b>Итог дня</b>\n\nЗаписей: {n} · {parts}\n\nЕсть что добавить?",
    },
    "daily_empty": {
        "uz": ("🌙 Bugun hali hech narsa yozmadingiz.\n\n"
               "Esingizga tushgan xarajatni yozib qo'ying — masalan "
               "<code>obedga 45 ming</code>"),
        "ru": ("🌙 Сегодня вы ещё ничего не записали.\n\n"
               "Запишите расход, который вспомните — например "
               "<code>обед 45 тысяч</code>"),
    },

    # ---- Muddat ogohlantirishi ----
    "expiry_sub": {
        "uz": "⏳ <b>Obunangizga {days} kun qoldi</b>",
        "ru": "⏳ <b>До конца подписки {days} дн.</b>",
    },
    "expiry_sub_today": {
        "uz": "⏳ <b>Obunangiz bugun tugaydi</b>",
        "ru": "⏳ <b>Подписка заканчивается сегодня</b>",
    },
    "expiry_sub_body": {
        "uz": "Uzaytirsangiz, yangi muddat mavjudining ustiga qo'shiladi — bir kun ham yo'qolmaydi.",
        "ru": "При продлении новый срок добавится к текущему — ни один день не пропадёт.",
    },
    "sub_activated": {
        "uz": ("🎉 <b>Obunangiz faollashtirildi!</b>\n\n"
               "Tarif: {plan}\nAmal qilish muddati: <b>{until}</b>\n\n"
               "Rahmat! Holatni ko'rish: /holat"),
        "ru": ("🎉 <b>Подписка активирована!</b>\n\n"
               "Тариф: {plan}\nДействует до: <b>{until}</b>\n\n"
               "Спасибо! Статус: /holat"),
    },

    # ---- Referal ----
    "referral": {
        "uz": ("🎁 <b>Do'stingizni taklif qiling</b>\n\n"
               "Havolangiz orqali kelgan har bir do'st uchun "
               "<b>ikkalangizga {bonus} kundan</b> bepul foydalanish qo'shiladi.\n\n"
               "<b>Sizning havolangiz:</b>\n<code>{link}</code>\n\n"
               "📊 Taklif qilganingiz: <b>{invited} ta</b>\n"
               "🎁 Yig'ilgan bonus: <b>{bonus_days} kun</b>"),
        "ru": ("🎁 <b>Пригласите друга</b>\n\n"
               "За каждого друга по вашей ссылке <b>вам обоим по {bonus} дней</b> "
               "бесплатного доступа.\n\n"
               "<b>Ваша ссылка:</b>\n<code>{link}</code>\n\n"
               "📊 Приглашено: <b>{invited}</b>\n"
               "🎁 Накоплено бонусов: <b>{bonus_days} дн.</b>"),
    },
    "referral_share_btn": {"uz": "📨 Do'stga yuborish", "ru": "📨 Отправить другу"},
    "referral_share_text": {
        "uz": ("Men xarajatlarimni shu bot bilan yuritaman — oddiy tilda "
               "yozasiz, u o'zi kategoriyaga ajratadi. Chek rasmini ham o'qiydi."),
        "ru": ("Веду расходы в этом боте — пишешь обычным текстом, он сам "
               "раскладывает по категориям. И чеки по фото распознаёт."),
    },
    "referral_welcome": {
        "uz": "🎁 Taklif havolasi orqali kirdingiz — bepul muddatingizga <b>{bonus} kun</b> qo'shildi!",
        "ru": "🎁 Вы пришли по приглашению — к бесплатному периоду добавлено <b>{bonus} дн.</b>!",
    },
    "referral_thanks": {
        "uz": ("🎉 <b>{name}</b> sizning havolangiz orqali qo'shildi!\n\n"
               "Sizga <b>{bonus} kun</b> bepul foydalanish qo'shildi. Rahmat!"),
        "ru": ("🎉 <b>{name}</b> присоединился по вашей ссылке!\n\n"
               "Вам добавлено <b>{bonus} дн.</b> бесплатного доступа. Спасибо!"),
    },

    # ---- Hisobni o'chirish ----
    "erase_confirm": {
        "uz": ("⚠️ <b>Hisobni butunlay o'chirish</b>\n\n"
               "O'chiriladi:\n• {n} ta moliyaviy yozuv\n"
               "• Byudjetlar va qarz tarixi\n• Obuna va sarf tarixi\n• Hisobingiz\n\n"
               "<b>Bu amalni qaytarib bo'lmaydi.</b>\n\n"
               "Avval ma'lumotingizni saqlab olishni tavsiya qilaman."),
        "ru": ("⚠️ <b>Полное удаление аккаунта</b>\n\n"
               "Будет удалено:\n• {n} финансовых записей\n"
               "• Бюджеты и история долгов\n• История подписки и расходов\n• Аккаунт\n\n"
               "<b>Отменить это будет невозможно.</b>\n\n"
               "Рекомендую сначала сохранить свои данные."),
    },
    "erase_btn_csv": {"uz": "📤 Avval CSV yuklab olaman",
                      "ru": "📤 Сначала скачаю CSV"},
    "erase_btn_yes": {"uz": "🗑 Ha, hammasini o'chir",
                      "ru": "🗑 Да, удалить всё"},
    "erase_btn_no": {"uz": "❌ Bekor qilish", "ru": "❌ Отмена"},
    "erase_cancelled": {"uz": "✅ Bekor qilindi — hech narsa o'chirilmadi.",
                        "ru": "✅ Отменено — ничего не удалено."},
    # Ikkinchi bosqich: tugmani bexosdan bosib yuborish oson, so'zni
    # ataylab yozish esa qiyin. Shuning uchun oxirgi tasdiq — yozma.
    "erase_word": {"uz": "O'CHIRISH", "ru": "УДАЛИТЬ"},
    "erase_type": {
        "uz": ("🛑 <b>Oxirgi tasdiq</b>\n\n"
               "{n} ta yozuv va butun hisobingiz o'chiriladi. Buni "
               "qaytarib bo'lmaydi.\n\n"
               "Rostdan xohlasangiz — javob sifatida shu so'zni yozing:\n"
               "<code>{word}</code>\n\n"
               "Boshqa har qanday xabar — bekor qilish. 5 daqiqadan keyin "
               "so'rov o'z-o'zidan bekor bo'ladi."),
        "ru": ("🛑 <b>Последнее подтверждение</b>\n\n"
               "{n} записей и весь аккаунт будут удалены. Это необратимо.\n\n"
               "Если действительно хотите — отправьте в ответ это слово:\n"
               "<code>{word}</code>\n\n"
               "Любое другое сообщение — отмена. Через 5 минут запрос "
               "отменится сам."),
    },
    "erase_wrong_word": {
        "uz": ("✅ Bekor qilindi — hech narsa o'chirilmadi.\n\n"
               "So'z mos kelmadi. Yozuvlaringiz joyida."),
        "ru": ("✅ Отменено — ничего не удалено.\n\n"
               "Слово не совпало. Ваши записи на месте."),
    },
    "erase_done": {
        "uz": ("🗑 <b>Hisobingiz o'chirildi</b>\n\n"
               "{n} ta yozuv va butun tarix bazadan olib tashlandi.\n\n"
               "Yana foydalanmoqchi bo'lsangiz — /start bosing.\n\nRahmat!"),
        "ru": ("🗑 <b>Аккаунт удалён</b>\n\n"
               "{n} записей и вся история удалены из базы.\n\n"
               "Захотите вернуться — нажмите /start.\n\nСпасибо!"),
    },
    "erase_expired": {
        "uz": "Muddat o'tdi. /ochirish ni qaytadan yuboring.",
        "ru": "Время истекло. Отправьте /ochirish заново.",
    },

    # ---- Ulashish ----
    "share_btn": {"uz": "🖼 Rasm qilib ulashish", "ru": "🖼 Поделиться картинкой"},
    "share_caption": {
        "uz": "📊 Hisobotingiz. Do'stlaringizga ulashsangiz bo'ladi!",
        "ru": "📊 Ваш отчёт. Можете поделиться с друзьями!",
    },

    # ---- Rozilik (shaxsiy ma'lumotni qayta ishlashdan oldin) ----
    "consent": {
        "uz": ("👋 <b>Boshlashdan oldin</b>\n\n"
               "Men sizning moliyaviy yozuvlaringizni saqlayman va tahlil "
               "qilaman. Qonun talabiga ko'ra buni boshlashdan oldin "
               "roziligingizni olishim kerak.\n\n"
               "<b>Nima saqlanadi</b>\n"
               "Telegram ID va ismingiz, siz yozgan summalar, kategoriyalar, "
               "izohlar, qarzdorlar ismi, shaxsiy jamg'armangiz, obuna va "
               "to'lov tarixi.\n\n"
               "<b>Qayerda saqlanadi</b>\n"
               "Yevropadagi ijaraga olingan serverda (Fransiya). Summalar, "
               "kategoriyalar va izohlar <b>alohida shifrlangan bazada</b> "
               "turadi — uning kaliti admin panelda yo'q, ya'ni ularni "
               "sizdan boshqa hech kim ochib ko'ra olmaydi. Har kuni "
               "shifrlangan zaxira nusxa olinadi.\n\n"
               "<b>Kimga uzatiladi</b>\n"
               "Yozganingizni tushunish uchun matn va chek rasmi "
               "<b>Anthropic</b> (AQSh) xizmatiga yuboriladi. U yerda "
               "saqlanmaydi va modelni o'qitishga ishlatilmaydi. Boshqa hech "
               "kimga berilmaydi va sotilmaydi.\n\n"
               "<b>Sizning huquqlaringiz</b>\n"
               "• /csv — barcha ma'lumotingizni yuklab olish\n"
               "• /ochirish — hisobni va butun tarixni butunlay o'chirish\n"
               "• /maxfiylik — to'liq siyosat\n"
               "• /shartlar — xizmat shartlari va to'lov qoidalari\n\n"
               "<b>Muhim:</b> men moliyaviy maslahat bermayman — faqat "
               "sizning yozuvlaringizni hisoblab beraman.\n\n"
               "Davom etish uchun roziligingizni bildiring 👇"),
        "ru": ("👋 <b>Перед началом</b>\n\n"
               "Я храню и анализирую ваши финансовые записи. По закону я "
               "обязан получить ваше согласие до начала обработки.\n\n"
               "<b>Что хранится</b>\n"
               "Telegram ID и имя, введённые вами суммы, категории, "
               "комментарии, имена должников, ваши накопления, история "
               "подписки и оплат.\n\n"
               "<b>Где хранится</b>\n"
               "На арендованном сервере в Европе (Франция). Суммы, "
               "категории и комментарии хранятся в <b>отдельной "
               "зашифрованной базе</b> — ключа от неё нет в админ-панели, "
               "то есть открыть их не может никто, кроме вас. Каждый день "
               "создаётся зашифрованная резервная копия.\n\n"
               "<b>Кому передаётся</b>\n"
               "Чтобы понять написанное, текст и фото чека отправляются в "
               "сервис <b>Anthropic</b> (США). Там они не сохраняются и не "
               "используются для обучения модели. Больше никому не "
               "передаются и не продаются.\n\n"
               "<b>Ваши права</b>\n"
               "• /csv — скачать все свои данные\n"
               "• /ochirish — полностью удалить аккаунт и всю историю\n"
               "• /maxfiylik — полная политика\n"
               "• /shartlar — условия сервиса и правила оплаты\n\n"
               "<b>Важно:</b> я не даю финансовых советов — только считаю "
               "ваши записи.\n\n"
               "Чтобы продолжить, подтвердите согласие 👇"),
    },
    "consent_yes": {"uz": "✅ Roziman, davom etamiz",
                    "ru": "✅ Согласен, продолжим"},
    "consent_privacy": {"uz": "🔒 Maxfiylik", "ru": "🔒 Конфиденциальность"},
    "consent_terms": {"uz": "📄 Shartlar", "ru": "📄 Условия"},
    "consent_done": {"uz": "Rahmat! Endi boshlaymiz.",
                     "ru": "Спасибо! Теперь начнём."},
    "consent_needed": {
        "uz": "Avval roziligingiz kerak — /start bosing.",
        "ru": "Сначала нужно ваше согласие — нажмите /start.",
    },

    # ---- Xizmat shartlari (ommaviy oferta) ----
    "terms": {
        "uz": ("📄 <b>XIZMAT SHARTLARI</b>\n\n"
               "<b>1. Xizmat nima</b>\n"
               "«Tanga» — shaxsiy xarajatlarni yozib borish va hisobot "
               "olish uchun Telegram boti. Xizmat «bor holicha» taqdim "
               "etiladi.\n\n"
               "<b>2. Bepul sinov</b>\n"
               "Har bir yangi foydalanuvchi {trial} kun bepul foydalanadi. "
               "Sinov davrida hech qanday to'lov talab qilinmaydi.\n\n"
               "<b>3. Obuna va to'lov</b>\n"
               "• Tariflar: /obuna\n"
               "• To'lov karta o'tkazmasi orqali amalga oshiriladi\n"
               "• To'lovdan so'ng chek (rasm yoki PDF) yuboriladi\n"
               "• Administrator tasdiqlagach obuna faollashadi\n"
               "• Yangi muddat mavjud muddat ustiga qo'shiladi\n"
               "• To'lov <b>avtomatik yangilanmaydi</b> — har safar o'zingiz "
               "qaror qilasiz\n\n"
               "<b>4. Pulni qaytarish</b>\n"
               "Obuna faollashganidan keyin <b>3 kun ichida</b> xizmatdan "
               "foydalanmagan bo'lsangiz, to'liq qaytariladi. Undan keyin "
               "foydalanilmagan kunlar uchun qisman qaytarish ko'rib "
               "chiqiladi. Murojaat: {contact}\n\n"
               "<b>5. Xizmat to'xtatilishi</b>\n"
               "Botni suiiste'mol qilish (avtomatlashtirilgan spam, tizimga "
               "zarar yetkazishga urinish) aniqlansa, hisob bloklanishi "
               "mumkin. Bunda qolgan obuna kunlari qaytariladi.\n\n"
               "<b>6. Aniqlik va javobgarlik</b>\n"
               "Bot summalarni <b>dastur bilan</b> hisoblaydi, AI faqat "
               "matnni o'qiydi va kategoriyaga ajratadi. Shunga qaramay xato "
               "bo'lishi mumkin — muhim qarorlardan oldin sonlarni o'zingiz "
               "tekshiring. Bot moliyaviy, investitsiya yoki soliq maslahati "
               "<b>bermaydi</b>. Xizmat ma'lumotlariga tayanib qilingan "
               "qarorlar uchun javobgarlik foydalanuvchida.\n\n"
               "<b>7. Ma'lumot va maxfiylik</b>\n"
               "/maxfiylik da to'liq yozilgan. Istalgan paytda /ochirish "
               "bilan hammasini o'chira olasiz.\n\n"
               "<b>8. Shartlar o'zgarishi</b>\n"
               "Shartlar o'zgarsa, botda xabar beriladi va roziligingiz "
               "qaytadan so'raladi.\n\n"
               "<b>Aloqa:</b> {contact}\n"
               "<i>Versiya: {version}</i>"),
        "ru": ("📄 <b>УСЛОВИЯ СЕРВИСА</b>\n\n"
               "<b>1. Что это за сервис</b>\n"
               "«Tanga» — Telegram-бот для учёта личных расходов и "
               "получения отчётов. Сервис предоставляется «как есть».\n\n"
               "<b>2. Бесплатный период</b>\n"
               "Каждый новый пользователь получает {trial} дней бесплатно. "
               "В пробный период оплата не требуется.\n\n"
               "<b>3. Подписка и оплата</b>\n"
               "• Тарифы: /obuna\n"
               "• Оплата производится переводом на карту\n"
               "• После оплаты отправляется чек (фото или PDF)\n"
               "• Подписка активируется после подтверждения администратором\n"
               "• Новый срок добавляется к текущему\n"
               "• Оплата <b>не продлевается автоматически</b> — вы решаете "
               "каждый раз сами\n\n"
               "<b>4. Возврат средств</b>\n"
               "Если в течение <b>3 дней</b> после активации вы не "
               "пользовались сервисом — возврат в полном объёме. После "
               "этого рассматривается частичный возврат за неиспользованные "
               "дни. Обращение: {contact}\n\n"
               "<b>5. Прекращение обслуживания</b>\n"
               "При злоупотреблении (автоматизированный спам, попытки "
               "навредить системе) аккаунт может быть заблокирован. "
               "Оставшиеся дни подписки при этом возвращаются.\n\n"
               "<b>6. Точность и ответственность</b>\n"
               "Суммы считает <b>программа</b>, ИИ только читает текст и "
               "распределяет по категориям. Тем не менее ошибки возможны — "
               "проверяйте цифры перед важными решениями. Бот <b>не даёт</b> "
               "финансовых, инвестиционных или налоговых советов. "
               "Ответственность за решения, принятые на основе данных "
               "сервиса, лежит на пользователе.\n\n"
               "<b>7. Данные и конфиденциальность</b>\n"
               "Подробно в /maxfiylik. В любой момент можете удалить всё "
               "через /ochirish.\n\n"
               "<b>8. Изменение условий</b>\n"
               "При изменении условий бот сообщит об этом и заново запросит "
               "ваше согласие.\n\n"
               "<b>Контакт:</b> {contact}\n"
               "<i>Версия: {version}</i>"),
    },

    "terms_operator": {
        "uz": "<b>Xizmat ko'rsatuvchi:</b> {operator}",
        "ru": "<b>Исполнитель:</b> {operator}",
    },

    # ---- Maxfiylik siyosati ----
    "privacy": {
        "uz": ("🔒 <b>MAXFIYLIK SIYOSATI</b>\n\n"
               "<b>Qanday ma'lumot saqlanadi</b>\n"
               "• Telegram ID, ismingiz va username\n"
               "• Siz yozgan xarajat/kirim yozuvlari: summa, kategoriya, "
               "izoh, sana\n"
               "• Qarz yozuvlarida siz ko'rsatgan shaxs ismi\n"
               "• Shaxsiy jamg'arma yozuvlari, maqsadingiz va "
               "jamg'arma uchun alohida kartangiz bor-yo'qligi\n"
               "• Obuna muddati va to'lov tarixi\n\n"
               "<b>Qanday saqlanadi \u2014 shifrlangan</b>\n"
               "Hamma ma'lumot diskda <b>shifrlangan</b> holda yotadi. "
               "Baza fayli o'g'irlansa ham kalitisiz ochilmaydi \u2014 "
               "ichida faqat tushunarsiz belgilar ko'rinadi.\n\n"
               "Moliyaviy yozuvlaringiz \u2014 summa, kategoriya, izoh \u2014 "
               "bundan tashqari <b>alohida faylda, alohida kalit</b> bilan "
               "saqlanadi. O'sha kalit admin panelda umuman yo'q, ya'ni "
               "ularni sizdan boshqa hech kim ochib ko'ra olmaydi.\n\n"
               "Har kunlik zaxira nusxa ham shifrlangan (AES-256).\n\n"
               "<b>Chek rasmlari</b>\n"
               "Chek suratini yuborsangiz, u <b>faqat o'qish uchun</b> "
               "Anthropic (AQSh) serveriga yuboriladi. Rasm bizda ham, u "
               "yerda ham saqlanmaydi — o'qilgandan keyin darhol o'chadi. "
               "Faqat undan chiqqan <b>matnli yozuvlar</b> sizning "
               "bazangizda qoladi.\n\n"
               "Yozgan matnlaringiz ham xuddi shu tarzda tahlil uchun "
               "yuboriladi. Anthropic bu ma'lumotni modelni o'qitishga "
               "ishlatmaydi.\n\n"
               "<b>Kim ko'ra oladi</b>\n"
               "• <b>Faqat siz</b> — bot va boshqaruv paneli orqali\n"
               "• Administrator sizning summalaringiz, kategoriyalaringiz "
               "va izohlaringizni <b>ko'ra olmaydi</b>. Bu va'da emas, "
               "texnik to'siq: yozuvlar alohida shifrlangan bazada "
               "saqlanadi va uning kaliti admin panelda umuman yo'q. "
               "Adminга faqat yozuvlar SONI ko'rinadi — obuna va limitni "
               "hal qilish uchun shu yetadi.\n"
               "• Boshqa foydalanuvchilar sizning ma'lumotingizni "
               "<b>hech qachon</b> ko'rmaydi. Har bir yozuv Telegram ID "
               "bo'yicha ajratilgan.\n\n"
               "<b>Qayerda saqlanadi</b>\n"
               "Fransiyadagi ijaraga olingan serverda (Contabo). Kirish "
               "faqat SSH kaliti orqali, parol bilan kirish o'chirilgan. "
               "Baza diskda shifrlangan holda yotadi (SQLCipher), "
               "moliyaviy yozuvlar esa alohida fayl va alohida kalit "
               "bilan. Har kuni AES-256 bilan shifrlangan zaxira nusxa "
               "olinadi.\n\n"
               "<b>Qancha saqlanadi</b>\n"
               "Siz o'chirmaguningizcha. /ochirish bosilganda darhol va "
               "butunlay o'chiriladi; zaxira nusxalar 14 kun ichida "
               "almashib ketadi.\n\n"
               "<b>Sizning huquqlaringiz</b>\n"
               "• /csv — barcha ma'lumotingizni fayl qilib olish\n"
               "• /ochirish — hisobni va butun tarixni butunlay o'chirish "
               "(darhol va qaytarib bo'lmaydigan tarzda)\n"
               "• Roziligingizni istalgan paytda qaytarib olishingiz "
               "mumkin — buning uchun /ochirish bosing\n\n"
               "<b>To'lov</b>\n"
               "Karta ma'lumotlaringiz bizga kelmaydi. Siz o'zingiz "
               "o'tkazma qilasiz va faqat chek skrinshotini yuborasiz.\n\n"
               "Savol: {contact}"),
        "ru": ("🔒 <b>ПОЛИТИКА КОНФИДЕНЦИАЛЬНОСТИ</b>\n\n"
               "<b>Какие данные хранятся</b>\n"
               "• Telegram ID, имя и username\n"
               "• Ваши записи расходов/доходов: сумма, категория, "
               "комментарий, дата\n"
               "• Имя человека, указанное в записях о долге\n"
               "• Записи о накоплениях, ваша цель и наличие отдельной "
               "карты для накоплений\n"
               "• Срок подписки и история оплат\n\n"
               "<b>Как хранится \u2014 в зашифрованном виде</b>\n"
               "Все данные лежат на диске <b>зашифрованными</b>. "
               "Даже если файл базы украдут, "
               "без ключа его не открыть.\n\n"
               "Ваши финансовые записи \u2014 сумма, "
               "категория, комментарий \u2014 кроме того "
               "хранятся <b>в отдельном файле с отдельным "
               "ключом</b>. Этого ключа нет в админ-панели "
               "вообще \u2014 открыть их не может никто, "
               "кроме вас.\n\n"
               "Ежедневная резервная копия тоже "
               "зашифрована (AES-256).\n\n"
               "<b>Фото чеков</b>\n"
               "Отправленное фото чека передаётся на сервер Anthropic (США) "
               "<b>только для распознавания</b>. Изображение не хранится ни "
               "у нас, ни там — удаляется сразу после прочтения. В вашей "
               "базе остаются только полученные <b>текстовые записи</b>.\n\n"
               "Ваши текстовые сообщения передаются на анализ так же. "
               "Anthropic не использует эти данные для обучения модели.\n\n"
               "<b>Кто может видеть</b>\n"
               "• <b>Только вы</b> — через бот и панель управления\n"
               "• Администратор <b>не может видеть</b> ваши суммы, "
               "категории и комментарии. Это не обещание, а техническое "
               "препятствие: записи лежат в отдельной зашифрованной базе, "
               "и ключа от неё в админ-панели нет вообще. Администратору "
               "видно только КОЛИЧЕСТВО записей — этого достаточно для "
               "решений по подписке и лимитам.\n"
               "• Другие пользователи <b>никогда</b> не видят ваши данные. "
               "Все записи разделены по Telegram ID.\n\n"
               "<b>Где хранится</b>\n"
               "На арендованном сервере во Франции (Contabo). Доступ только "
               "по SSH-ключу, вход по паролю отключён. База на диске "
               "зашифрована (SQLCipher), а финансовые записи — отдельным "
               "файлом с отдельным ключом. Каждый день создаётся резервная "
               "копия с шифрованием AES-256.\n\n"
               "<b>Сколько хранится</b>\n"
               "Пока вы сами не удалите. По команде /ochirish данные "
               "удаляются немедленно и полностью; резервные копии "
               "перезаписываются в течение 14 дней.\n\n"
               "<b>Ваши права</b>\n"
               "• /csv — выгрузить все свои данные файлом\n"
               "• /ochirish — полностью удалить аккаунт и всю историю "
               "(сразу и безвозвратно)\n"
               "• Вы можете отозвать согласие в любой момент — для этого "
               "нажмите /ochirish\n\n"
               "<b>Оплата</b>\n"
               "Данные вашей карты к нам не попадают. Перевод вы делаете "
               "сами и присылаете только скриншот чека.\n\n"
               "Вопросы: {contact}"),
    },

    # ---- Shaxsiy jamg'arma ----
    #
    # Matnlar «Vavilonlik eng boy odam» (G. Clason, 1926) g'oyalariga
    # tayanadi, lekin kitobni maqtash uchun emas: har bir xabar odamning
    # O'Z raqamini ko'rsatadi. Mavhum nasihat o'qilmaydi.

    # Oy oxiri — hech narsa jamg'armaganlarga
    "savings_month_none": {
        "uz": ("🏦 <b>Oy tugayapti — bir daqiqa gaplashamiz</b>\n\n"
               "Bu oy daromadingiz: <b>{income}</b>\n"
               "Jamg'armaga qo'yganingiz: <b>0</b>\n\n"
               "Oddiy qoida: <b>topganingizning kamida {pct} % i "
               "o'zingizga qolishi kerak</b>. Sizda bu — <b>{ten}</b>.\n\n"
               "Ko'pchilik «oyning oxirida ortsa jamg'araman» deydi. "
               "Hech qachon ortmaydi — xarajat topilaveradi. Shuning "
               "uchun tartib teskari: <b>avval o'zingizga to'lang</b>, "
               "qolganiga yashang.\n\n"
               "O'tkazgan bo'lsangiz shunchaki yozing:\n"
               "<code>jamg'armaga {ten_plain} o'tkazdim</code>"),
        "ru": ("🏦 <b>Месяц заканчивается — на минуту о важном</b>\n\n"
               "Ваш доход за месяц: <b>{income}</b>\n"
               "Отложено в накопления: <b>0</b>\n\n"
               "Простое правило: <b>минимум {pct} % заработанного должно "
               "оставаться вам</b>. У вас это — <b>{ten}</b>.\n\n"
               "Многие говорят «отложу, если останется в конце месяца». "
               "Не остаётся никогда — расходы найдутся. Поэтому порядок "
               "обратный: <b>сначала заплатите себе</b>, живите на "
               "остальное.\n\n"
               "Если уже перевели — просто напишите:\n"
               "<code>в накопления {ten_plain}</code>"),
    },
    # Oy oxiri — jamg'argan, lekin 10 % dan kam
    "savings_month_low": {
        "uz": ("🏦 <b>Oylik jamg'arma xulosasi</b>\n\n"
               "Daromad: <b>{income}</b>\n"
               "Jamg'arma: <b>{saved}</b> — daromadingizning <b>{percent}%</b> i\n"
               "Umumiy jamg'armangiz: <b>{balance}</b>\n\n"
               "Boshladingiz — eng qiyini shu edi. {pct} % ga yetish uchun "
               "yana <b>{gap}</b> kerak.\n\n"
               "Nega aynan {pct} %: bu miqdor turmushni sezilarli "
               "o'zgartirmaydi, lekin bir yilda bir oylik daromadga "
               "aylanadi."),
        "ru": ("🏦 <b>Итог накоплений за месяц</b>\n\n"
               "Доход: <b>{income}</b>\n"
               "Отложено: <b>{saved}</b> — это <b>{percent}%</b> дохода\n"
               "Всего накоплений: <b>{balance}</b>\n\n"
               "Вы начали — это было самым трудным. До {pct} % не хватает "
               "<b>{gap}</b>.\n\n"
               "Почему именно {pct} %: эта доля почти не меняет образ "
               "жизни, но за год превращается в месячный доход."),
    },
    # Daromadi yo'q oy
    "savings_month_no_income": {
        "uz": ("🏦 <b>Oy tugayapti</b>\n\n"
               "Bu oy daromad yozmagansiz, shuning uchun {pct} % ni "
               "hisoblay olmadim.\n\n"
               "Umumiy jamg'armangiz: <b>{balance}</b>\n\n"
               "Daromad kelganda uni yozib qo'ying — men {pct} % ni o'zim "
               "hisoblab, eslatib turaman."),
        "ru": ("🏦 <b>Месяц заканчивается</b>\n\n"
               "В этом месяце вы не записывали доход, поэтому {pct} % "
               "посчитать не удалось.\n\n"
               "Всего накоплений: <b>{balance}</b>\n\n"
               "Запишите доход, когда он появится — я сам посчитаю {pct} % "
               "и напомню."),
    },

    # ---- Alohida karta ----
    "savings_card_ask": {
        "uz": ("💳 <b>Bitta savol</b>\n\n"
               "Jamg'armangiz uchun <b>alohida bank kartangiz</b> bormi?\n\n"
               "Nega so'rayapman: bitta hisobda turgan pul «bor» bo'lib "
               "ko'rinadi va sezilmasdan sarflanadi. Alohida kartadagi "
               "pulga qo'l urish uchun ongli harakat kerak — shuning "
               "o'zi uni saqlab qoladi."),
        "ru": ("💳 <b>Один вопрос</b>\n\n"
               "Есть ли у вас <b>отдельная банковская карта</b> для "
               "накоплений?\n\n"
               "Зачем спрашиваю: деньги на одном счёте выглядят как "
               "«есть» и тратятся незаметно. Чтобы тронуть деньги на "
               "отдельной карте, нужно осознанное действие — это само по "
               "себе их сохраняет."),
    },
    "savings_card_yes": {"uz": "✅ Ha, alohida kartam bor",
                         "ru": "✅ Да, есть отдельная карта"},
    "savings_card_no": {"uz": "❌ Yo'q, hali ochmaganman",
                        "ru": "❌ Нет, ещё не открыл"},
    "savings_card_done": {
        "uz": ("👍 Zo'r. Endi jamg'armani <b>o'sha kartaga</b> o'tkazing va "
               "menga yozib qo'ying:\n\n"
               "<code>jamg'armaga 500 ming o'tkazdim</code>\n\n"
               "Men qoldiqni hisoblab boraman."),
        "ru": ("👍 Отлично. Теперь переводите накопления <b>на эту карту</b> "
               "и пишите мне:\n\n"
               "<code>в накопления 500 тысяч</code>\n\n"
               "Я буду считать остаток."),
    },
    "savings_card_later": {
        "uz": ("Tushunarli. Shoshilinch ish emas, lekin <b>eng arzon "
               "moliyaviy qadam</b> — bepul va bir marta qilinadi.\n\n"
               "Har qanday bankda ikkinchi karta ochsangiz bo'ladi. "
               "Muhimi: <b>kartasi qo'lingizda yurmasin</b> va unga "
               "to'lov ilovalari ulanmasin.\n\n"
               "Ochganingizda menga ayting — <code>/jamgarma</code>"),
        "ru": ("Понятно. Дело не срочное, но это <b>самый дешёвый "
               "финансовый шаг</b> — бесплатно и делается один раз.\n\n"
               "Подойдёт вторая карта в любом банке. Главное: "
               "<b>не носите её с собой</b> и не привязывайте к платёжным "
               "приложениям.\n\n"
               "Когда откроете — скажите мне: <code>/jamgarma</code>"),
    },
    "savings_card_nudge": {
        "uz": ("💳 Eslatma: jamg'armangiz uchun hali <b>alohida karta</b> "
               "ochmagansiz.\n\n"
               "Hozirgi jamg'armangiz — <b>{balance}</b>. U kundalik "
               "kartada tursa, sarflanib ketishi ehtimoli katta.\n\n"
               "Ochdingizmi? <code>/jamgarma</code>"),
        "ru": ("💳 Напоминание: для накоплений вы ещё не открыли "
               "<b>отдельную карту</b>.\n\n"
               "Сейчас накоплено <b>{balance}</b>. Если эти деньги лежат "
               "на повседневной карте, шанс их потратить велик.\n\n"
               "Открыли? <code>/jamgarma</code>"),
    },

    # ---- /jamgarma buyrug'i ----
    "savings_status": {
        "uz": ("🏦 <b>Shaxsiy jamg'armangiz</b>\n\n"
               "Joriy qoldiq: <b>{balance}</b>\n"
               "Bu oy qo'shildi: <b>{month}</b>\n"
               "Alohida karta: {card}\n\n"
               "{advice}\n\n"
               "Qo'shish: <code>jamg'armaga 200 ming o'tkazdim</code>\n"
               "Yechish: <code>jamg'armadan 50 ming oldim</code>"),
        "ru": ("🏦 <b>Ваши накопления</b>\n\n"
               "Текущий остаток: <b>{balance}</b>\n"
               "Добавлено за месяц: <b>{month}</b>\n"
               "Отдельная карта: {card}\n\n"
               "{advice}\n\n"
               "Пополнить: <code>в накопления 200 тысяч</code>\n"
               "Снять: <code>из накоплений 50 тысяч</code>"),
    },
    "savings_card_state_yes": {"uz": "✅ bor", "ru": "✅ есть"},
    "savings_card_state_no": {"uz": "❌ yo'q", "ru": "❌ нет"},
    # Zaxira fond: jamg'arma necha oylik chiqimga yetadi
    "savings_cushion": {
        "uz": ("🛡 Bu jamg'arma o'rtacha oylik chiqimingizga "
               "(<b>{monthly}</b>) taxminan <b>{months}</b> yetadi."),
        "ru": ("🛡 Этих накоплений хватит примерно на <b>{months}</b> "
               "при среднем месячном расходе <b>{monthly}</b>."),
    },

    # ---- Daromad yozilgan ONDA 10 % eslatmasi ----
    #
    # Kitobning mag'zi «avval o'zingga to'la». Pul kelgan ON eng kuchli
    # payt: odam uni hali sarflamagan va qaror qabul qilish oson.
    "savings_nudge_now": {
        "uz": ("💰 <b>{income}</b> kirim yozildi.\n\n"
               "Undan <b>{pct} % — {ten}</b>.\n\n"
               "«Avval o'zingizga to'lang»: shu qismni hoziroq "
               "jamg'armaga o'tkazsangiz, qolganiga yashash sezilmaydi. "
               "Oy oxirida esa hech narsa ortmaydi — xarajat topilaveradi."),
        "ru": ("💰 Записан доход <b>{income}</b>.\n\n"
               "{pct} % от него — <b>{ten}</b>.\n\n"
               "«Сначала заплатите себе»: если переведёте эту часть в "
               "накопления прямо сейчас, жизнь на остальное не изменится. "
               "А в конце месяца не остаётся ничего — расходы найдутся."),
    },
    "savings_nudge_button": {"uz": "🏦 Ha, {ten} o'tkazdim",
                             "ru": "🏦 Да, отложил {ten}"},
    "savings_nudge_saved": {
        "uz": ("✅ <b>{amount}</b> jamg'armaga yozildi.\n\n"
               "Jamg'armangiz: <b>{balance}</b>{streak}"),
        "ru": ("✅ <b>{amount}</b> записано в накопления.\n\n"
               "Ваши накопления: <b>{balance}</b>{streak}"),
    },

    # ---- Jamg'arma seriyasi ----
    "savings_streak": {
        "uz": "\n\n🔥 Ketma-ket <b>{n} oy</b> {pct} % qoidasini bajaryapsiz.",
        "ru": "\n\n🔥 <b>{n} мес.</b> подряд выполняете правило {pct} %.",
    },

    # ---- Jamg'arma foizi ----
    #
    # Foiz har kimda o'zi bo'ladi: kimdir 5 % dan boshlaydi, kimdir
    # 20 % ajrata oladi. Qat'iy 10 % ni majburlash foydasiz — bajara
    # olmagan odam butun eslatmani o'chirib qo'yadi.
    "rate_set": {
        "uz": ("\u2705 Jamg'arma foizi: <b>{pct}%</b>\n\n"
               "Endi barcha hisob-kitob va eslatmalar shu foizga "
               "qarab bo'ladi.{example}"),
        "ru": ("\u2705 \u041f\u0440\u043e\u0446\u0435\u043d\u0442 "
               "\u043d\u0430\u043a\u043e\u043f\u043b\u0435\u043d\u0438\u0439: "
               "<b>{pct}%</b>\n\n"
               "\u0422\u0435\u043f\u0435\u0440\u044c \u0432\u0441\u0435 "
               "\u0440\u0430\u0441\u0447\u0451\u0442\u044b \u0438 "
               "\u043d\u0430\u043f\u043e\u043c\u0438\u043d\u0430\u043d\u0438\u044f "
               "\u0431\u0443\u0434\u0443\u0442 \u043f\u043e \u044d\u0442\u043e\u043c\u0443 "
               "\u043f\u0440\u043e\u0446\u0435\u043d\u0442\u0443.{example}"),
    },
    "rate_example": {
        "uz": "\n\nOxirgi oylik daromadingizdan bu \u2014 <b>{amount}</b>.",
        "ru": ("\n\n\u041e\u0442 \u0434\u043e\u0445\u043e\u0434\u0430 \u0437\u0430 "
               "\u043f\u043e\u0441\u043b\u0435\u0434\u043d\u0438\u0439 "
               "\u043c\u0435\u0441\u044f\u0446 \u044d\u0442\u043e \u2014 "
               "<b>{amount}</b>."),
    },
    "rate_bad": {
        "uz": ("Foiz <b>1</b> dan <b>90</b> gacha bo'lishi kerak.\n\n"
               "Masalan: <code>/foiz 10</code>"),
        "ru": ("\u041f\u0440\u043e\u0446\u0435\u043d\u0442 \u0434\u043e\u043b\u0436\u0435\u043d "
               "\u0431\u044b\u0442\u044c \u043e\u0442 <b>1</b> \u0434\u043e <b>90</b>.\n\n"
               "\u041d\u0430\u043f\u0440\u0438\u043c\u0435\u0440: <code>/foiz 10</code>"),
    },

    # ---- Jamg'arma maqsadi ----
    "goal_reached": {
        "uz": ("🎉 <b>Maqsadga yetdingiz!</b>\n\n"
               "Maqsad: <b>{amount}</b>{note}\n"
               "Jamg'armangiz: <b>{balance}</b>\n\n"
               "Eng qiyini birinchi qadam edi — uni bosib o'tdingiz. "
               "Yangi maqsad qo'yasizmi?\n"
               "<code>/maqsad 20 mln</code>"),
        "ru": ("🎉 <b>Цель достигнута!</b>\n\n"
               "Цель: <b>{amount}</b>{note}\n"
               "Накопления: <b>{balance}</b>\n\n"
               "Труднее всего первый шаг — вы его сделали. Поставим "
               "новую цель?\n"
               "<code>/maqsad 20 млн</code>"),
    },

    # ---- Sof qiymat ----
    "net_worth": {
        "uz": ("⚖️ <b>Sof qiymatingiz</b>\n\n"
               "🏦 Jamg'arma: <b>{savings}</b>\n"
               "📤 Sizga qarzdorlar: <b>{owed}</b>\n"
               "📥 Sizning qarzingiz: <b>−{iowe}</b>\n"
               "───────────────\n"
               "{icon} <b>Jami: {total}</b>\n\n"
               "<i>Bu — oqim emas, holat. Kirim/chiqim har oy "
               "o'zgaradi, bu raqam esa qayerga borayotganingizni "
               "ko'rsatadi.</i>"),
        "ru": ("⚖️ <b>Ваш капитал</b>\n\n"
               "🏦 Накопления: <b>{savings}</b>\n"
               "📤 Вам должны: <b>{owed}</b>\n"
               "📥 Ваш долг: <b>−{iowe}</b>\n"
               "───────────────\n"
               "{icon} <b>Итого: {total}</b>\n\n"
               "<i>Это не поток, а состояние. Доходы и расходы меняются "
               "каждый месяц, а эта цифра показывает, куда вы идёте.</i>"),
    },

    # ---- Qarzdan chiqish rejasi (70/20/10) ----
    "debt_plan": {
        "uz": ("📋 <b>Qarzdan chiqish rejasi</b>\n\n"
               "Ochiq qarzingiz: <b>{debt}</b>\n"
               "Oylik o'rtacha daromadingiz: <b>{income}</b>\n\n"
               "Daromadingizni uchga bo'ling:\n"
               "• <b>70 %</b> — yashashga\n"
               "• <b>20 %</b> — qarzni uzishga (<b>{monthly}</b>)\n"
               "• <b>10 %</b> — jamg'armaga (qarz bo'lsa ham!)\n\n"
               "Shu tartibda <b>{months} oyda</b> qarzdan chiqasiz.\n\n"
               "<i>Nega qarz bo'lsa ham jamg'ariladi: hammasini qarzga "
               "bersangiz, kutilmagan xarajat chiqqan kuni yana qarz "
               "olasiz va aylana yopilmaydi.</i>"),
        "ru": ("📋 <b>План выхода из долгов</b>\n\n"
               "Открытый долг: <b>{debt}</b>\n"
               "Средний месячный доход: <b>{income}</b>\n\n"
               "Разделите доход на три части:\n"
               "• <b>70 %</b> — на жизнь\n"
               "• <b>20 %</b> — на погашение долга (<b>{monthly}</b>)\n"
               "• <b>10 %</b> — в накопления (даже с долгом!)\n\n"
               "В таком темпе вы закроете долг за <b>{months} мес.</b>\n\n"
               "<i>Почему копить нужно даже с долгом: если отдавать всё, "
               "то при первом же непредвиденном расходе вы снова "
               "занимаете — и круг не разрывается.</i>"),
    },
    "debt_plan_none": {
        "uz": ("✅ Ochiq qarzingiz yo'q.\n\n"
               "Qarzsiz odam daromadining {pct} % ini emas, imkoni boricha "
               "ko'proq qismini jamg'armaga yo'naltirishi mumkin."),
        "ru": ("✅ Открытых долгов нет.\n\n"
               "Без долгов можно откладывать не {pct} %, а столько, "
               "сколько позволяет доход."),
    },
    "debt_plan_no_income": {
        "uz": ("📋 Ochiq qarzingiz: <b>{debt}</b>\n\n"
               "Reja tuzish uchun daromadingizni bilishim kerak. "
               "Daromad kelganda yozib qo'ying — men 70/20/10 bo'yicha "
               "aniq muddat hisoblab beraman."),
        "ru": ("📋 Открытый долг: <b>{debt}</b>\n\n"
               "Чтобы построить план, мне нужен ваш доход. Запишите его, "
               "когда он появится — я рассчитаю срок по правилу 70/20/10."),
    },

    # Oylik baho va yillik jamg'arma matnlari bu yerda EMAS: ular
    # hisobot matnining bir qismi va reports.py da turadi — o'sha
    # faylning qolgan hamma matni ham o'sha yerda.

    # ---- Ketma-ket kunlar (streak) ----
    "streak_grew": {
        "uz": "🔥 Ketma-ket {n} kun yozyapsiz!",
        "ru": "🔥 {n} дней подряд ведёте учёт!",
    },
    "streak_record": {
        "uz": "🏆 Yangi rekord: ketma-ket {n} kun!",
        "ru": "🏆 Новый рекорд: {n} дней подряд!",
    },
    "streak_7": {
        "uz": ("🎉 <b>Bir hafta to'xtovsiz!</b>\n"
               "Odat shakllanishi shu yerdan boshlanadi. Davom eting."),
        "ru": ("🎉 <b>Неделя без пропусков!</b>\n"
               "Именно так формируется привычка. Продолжайте."),
    },
    "streak_30": {
        "uz": ("🏅 <b>30 kun ketma-ket!</b>\n"
               "Endi bu odat. /oy bosib bir oylik manzarani ko'ring."),
        "ru": ("🏅 <b>30 дней подряд!</b>\n"
               "Теперь это привычка. Нажмите /oy и посмотрите картину "
               "за месяц."),
    },
    "streak_100": {
        "uz": "💎 <b>100 kun!</b> Bu allaqachon jiddiy natija. Tabriklayman!",
        "ru": "💎 <b>100 дней!</b> Это уже серьёзный результат. Поздравляю!",
    },
    "entries_milestone": {
        "uz": ("✨ <b>{n}-yozuv!</b> Endi ma'lumot yetarli — "
               "«{btn}» bosib manzarani ko'ring."),
        "ru": ("✨ <b>{n}-я запись!</b> Данных уже достаточно — "
               "нажмите «{btn}» и посмотрите картину."),
    },

    # ---- Haftalik xulosa ----
    "digest_head": {
        "uz": "📬 <b>Haftalik xulosa</b>\n<i>{start} — {end}</i>",
        "ru": "📬 <b>Итоги недели</b>\n<i>{start} — {end}</i>",
    },
    "digest_body": {
        "uz": "\n\n💸 Chiqim: <b>{spent}</b>\n🧾 Yozuvlar: {count} ta",
        "ru": "\n\n💸 Расходы: <b>{spent}</b>\n🧾 Записей: {count}",
    },
    "digest_less": {
        "uz": "\n📉 O'tgan haftadan <b>{pct}% kam</b> — barakalla!",
        "ru": "\n📉 На <b>{pct}% меньше</b>, чем на прошлой неделе — отлично!",
    },
    "digest_more": {
        "uz": "\n📈 O'tgan haftadan <b>{pct}% ko'p</b>.",
        "ru": "\n📈 На <b>{pct}% больше</b>, чем на прошлой неделе.",
    },
    "digest_top": {"uz": "\n\n<b>Eng ko'p sarflangan:</b>",
                   "ru": "\n\n<b>Больше всего потрачено:</b>"},
    "digest_streak": {
        "uz": "\n\n🔥 Ketma-ket {n} kun. Zanjirni uzmang!",
        "ru": "\n\n🔥 {n} дней подряд. Не прерывайте цепочку!",
    },
    "digest_tip": {
        "uz": "\n\n💡 Byudjet qo'ysangiz, chegaraga yaqinlashganda "
              "ogohlantiraman: /byudjet",
        "ru": "\n\n💡 Поставьте бюджет — предупрежу при приближении "
              "к лимиту: /byudjet",
    },

    # ---- Qaytarish xabari ----
    "winback": {
        "uz": ("👋 Ancha vaqtdan beri yozmadingiz — {days} kun bo'ldi.\n\n"
               "Yozilmagan xarajat — ko'rinmaydigan xarajat. Bugungisini "
               "bitta xabar bilan tiklab qo'ying:\n\n"
               "<code>obedga 45 ming</code>\n\n"
               "Obunangiz hali faol, bemalol foydalaning."),
        "ru": ("👋 Вы давно не записывали — прошло {days} дней.\n\n"
               "Незаписанный расход — незаметный расход. Восстановите "
               "сегодняшний одним сообщением:\n\n"
               "<code>обед 45 тысяч</code>\n\n"
               "Подписка ещё активна, пользуйтесь спокойно."),
    },
    "winback_best": {
        "uz": "\n\n🔥 Eng uzun zanjiringiz — {n} kun. Yangisini boshlaymizmi?",
        "ru": "\n\n🔥 Ваша лучшая серия — {n} дней. Начнём новую?",
    },
}


# --------------------------------------------------------------------------- #
# Tanga PRO: tariflar, paywall, sinov va chegaralar (4-bosqich)
# --------------------------------------------------------------------------- #

T.update({
    # ---- Tariflar sahifasi (4.5) — funksiya ro'yxati emas, foyda ----
    "pro_title": {"uz": "💎 <b>Tanga PRO</b>", "ru": "💎 <b>Tanga PRO</b>"},
    "pro_pitch": {
        "uz": ("Pulingiz qayerga ketayotganini ko'rish — bepul.\n"
               "Uni maqsadga yo'naltirish — PRO."),
        "ru": ("Видеть, куда уходят деньги, — бесплатно.\n"
               "Направить их к цели — PRO."),
    },
    "pro_features": {
        "uz": ("✅ Maqsadlar va «qachon erishaman» bashorati\n"
               "✅ Cheksiz chek o'qish\n"
               "✅ Barcha oylar tahlili va solishtirish\n"
               "✅ Qarz va byudjet eslatmalari\n"
               "✅ «Avval o'zingizga to'lang» avtomatik rejasi"),
        "ru": ("✅ Цели и прогноз «когда достигну»\n"
               "✅ Безлимитное распознавание чеков\n"
               "✅ Анализ всех месяцев и сравнение\n"
               "✅ Напоминания о долгах и бюджете\n"
               "✅ Автоплан «Сначала заплати себе»"),
    },
    "plan_best_line": {
        "uz": "⭐ <b>{label} — {price}</b> (oyiga {monthly}, {pct}% tejash)",
        "ru": "⭐ <b>{label} — {price}</b> ({monthly} в месяц, экономия {pct}%)",
    },
    "plan_line": {"uz": "   {label} — {price}", "ru": "   {label} — {price}"},
    "plan_founders_line": {
        "uz": "🎁 <b>{label}: birinchi yil {price}</b> (qolgan joylar: {left}/{total})",
        "ru": "🎁 <b>{label}: первый год {price}</b> (осталось мест: {left}/{total})",
    },
    "plan_label_12m": {"uz": "Yillik", "ru": "Годовой"},
    "plan_label_1m": {"uz": "Oylik", "ru": "Месячный"},
    "plan_label_f12": {"uz": "Asoschilar taklifi", "ru": "Предложение основателям"},
    "plan_best_badge": {"uz": "⭐ Eng foydali", "ru": "⭐ Самый выгодный"},
    "pro_status_trial": {
        "uz": "🎁 PRO sinov faol — <b>{days} kun</b> qoldi. Hoziroq to'lasangiz, qolgan kunlar yo'qolmaydi.",
        "ru": "🎁 Пробный PRO активен — осталось <b>{days} дн.</b> Оплатите сейчас — оставшиеся дни сохранятся.",
    },
    "pro_status_sub": {
        "uz": "✅ PRO faol — <b>{days} kun</b> qoldi. Uzaytirsangiz, yangi muddat ustiga qo'shiladi.",
        "ru": "✅ PRO активен — осталось <b>{days} дн.</b> При продлении срок добавится к текущему.",
    },
    "pro_pick": {
        "uz": "<i>Tarifni tanlang — keyin to'lov rekvizitlari chiqadi.</i>",
        "ru": "<i>Выберите тариф — затем появятся реквизиты для оплаты.</i>",
    },
    "plan_unavailable": {
        "uz": "Bu tarif endi mavjud emas. /obuna dan joriy tariflarni ko'ring.",
        "ru": "Этот тариф больше недоступен. Актуальные тарифы: /obuna",
    },

    # ---- Paywall (4.3): nima qulflangan, PRO nima beradi, bitta tugma ----
    "pro_btn": {"uz": "💎 PRO ga o'tish", "ru": "💎 Перейти на PRO"},
    "pro_continue_btn": {"uz": "💎 PRO ni davom ettirish", "ru": "💎 Продолжить PRO"},
    "paywall_receipts": {
        "uz": ("🧾 <b>Bu oygi {limit} ta bepul chek ishlatildi.</b>\n\n"
               "Keyingi bepul cheklar {date} da ochiladi. Hozircha xarajatni "
               "matn bilan yozishingiz mumkin — bu cheksiz.\n\n"
               "PRO'da chek o'qish cheksiz: har bir mahsulot o'z kategoriyasiga "
               "tushadi."),
        "ru": ("🧾 <b>{limit} бесплатных чека в этом месяце использованы.</b>\n\n"
               "Следующие откроются {date}. Пока можно записывать расходы "
               "текстом — это без ограничений.\n\n"
               "В PRO чеки без ограничений: каждый товар попадает в свою категорию."),
    },
    "paywall_history": {
        "uz": ("📊 <b>Bepul versiyada joriy oy tahlili ochiq.</b>\n\n"
               "O'tgan oylar, yillik hisobot va oylarni solishtirish — PRO'da. "
               "Yozuvlaringiz saqlanib turibdi, hech biri yo'qolmagan."),
        "ru": ("📊 <b>В бесплатной версии доступен текущий месяц.</b>\n\n"
               "Прошлые месяцы, годовой отчёт и сравнение месяцев — в PRO. "
               "Все ваши записи сохранены."),
    },
    "paywall_budget": {
        "uz": ("💰 <b>Byudjet — PRO imkoniyati.</b>\n\n"
               "Kategoriyaga oylik chegara qo'yasiz, yaqinlashganda ogohlantiraman."),
        "ru": ("💰 <b>Бюджет — функция PRO.</b>\n\n"
               "Задайте лимит на категорию — предупрежу, когда приблизитесь."),
    },
    "paywall_csv": {
        "uz": ("📤 <b>CSV eksport — PRO imkoniyati.</b>\n\n"
               "Barcha yozuvlaringiz Excel'da ochiladigan faylda."),
        "ru": ("📤 <b>Экспорт в CSV — функция PRO.</b>\n\n"
               "Все записи в файле, который открывается в Excel."),
    },
    "paywall_qa": {
        "uz": ("💬 <b>Bugungi {limit} ta bepul savol ishlatildi.</b>\n\n"
               "Ertaga yana {limit} ta ochiladi. PRO'da savollar cheksiz."),
        "ru": ("💬 <b>{limit} бесплатных вопроса на сегодня использованы.</b>\n\n"
               "Завтра откроются ещё {limit}. В PRO — без ограничений."),
    },
    # Bir kunda ikkinchi marta — qisqa, tugmasiz.
    "paywall_short": {
        "uz": "🔒 {feature} — PRO imkoniyati. Batafsil: /obuna",
        "ru": "🔒 {feature} — функция PRO. Подробнее: /obuna",
    },
    "feature_receipts": {"uz": "Chek o'qish (bu oy limit tugadi)",
                         "ru": "Распознавание чеков (лимит месяца исчерпан)"},
    "feature_history": {"uz": "O'tgan davrlar tahlili", "ru": "Анализ прошлых периодов"},
    "feature_budget": {"uz": "Byudjet", "ru": "Бюджет"},
    "feature_csv": {"uz": "CSV eksport", "ru": "Экспорт в CSV"},
    "feature_qa": {"uz": "AI savollar (bugungi limit tugadi)",
                   "ru": "Вопросы AI (дневной лимит исчерпан)"},
    "paywall_trial_receipts": {
        "uz": ("🧾 <b>Sinov davridagi {limit} ta chek ishlatildi.</b>\n\n"
               "Xarajatni matn bilan yozishda davom etishingiz mumkin. "
               "PRO'da chek o'qish har kuni ochiq."),
        "ru": ("🧾 <b>{limit} чеков пробного периода использованы.</b>\n\n"
               "Записывать расходы текстом можно и дальше. "
               "В PRO распознавание чеков доступно каждый день."),
    },
    "feature_trial_receipts": {"uz": "Chek o'qish (sinov limiti tugadi)",
                               "ru": "Распознавание чеков (лимит пробного периода)"},

    # ---- AI sarfi chegaralari (umumiy va kishi boshiga) ----
    "ai_paused": {
        "uz": ("⏸ <b>Bot vaqtincha to'xtatildi</b>\n\n"
               "Bepul va sinov foydalanuvchilari uchun oylik xizmat chegarasi "
               "tugadi. Administrator xabardor qilindi.\n\n"
               "<i>Yozuvlaringiz saqlanib turibdi.</i>"),
        "ru": ("⏸ <b>Бот временно приостановлен</b>\n\n"
               "Месячный лимит сервиса для бесплатных и пробных пользователей "
               "исчерпан. Администратор уведомлён.\n\n"
               "<i>Ваши записи сохранены.</i>"),
    },
    "ai_user_limit": {
        "uz": ("⏸ <b>Bu oygi bepul AI limiti tugadi.</b>\n\n"
               "Yangi oy boshida ({date}) yana ochiladi. Hisobotlar, qarzlar "
               "va Mini App ishlashda davom etadi.\n\n"
               "PRO'da bu chegara yo'q."),
        "ru": ("⏸ <b>Бесплатный лимит AI на этот месяц исчерпан.</b>\n\n"
               "Откроется снова в начале месяца ({date}). Отчёты, долги "
               "и Mini App продолжают работать.\n\n"
               "В PRO этого ограничения нет."),
    },

    # ---- To'lov cheki yoki xarid cheki ----
    "proof_ask": {
        "uz": ("🤔 Sizda <b>{plan}</b> tarifi bo'yicha to'lov kutilmoqda.\n\n"
               "Bu rasm nima?"),
        "ru": ("🤔 У вас ожидается оплата по тарифу <b>{plan}</b>.\n\n"
               "Что это за изображение?"),
    },
    "proof_btn_pay": {"uz": "💳 To'lov cheki", "ru": "💳 Чек об оплате"},
    "proof_btn_buy": {"uz": "🧾 Xarid cheki (xarajat)", "ru": "🧾 Чек покупки (расход)"},
    "proof_choice_expired": {
        "uz": "Bu so'rov eskirdi. Rasmni qaytadan yuboring.",
        "ru": "Запрос устарел. Отправьте изображение ещё раз.",
    },
    "receipt_parts_max": {
        "uz": ("Bitta chek uchun ko'pi bilan {limit} ta qism. «✅ Tayyor» ni "
               "bosing — yuborilganlari o'qiladi."),
        "ru": ("Не больше {limit} частей на один чек. Нажмите «✅ Готово» — "
               "отправленные части будут распознаны."),
    },

    # ---- Adolatli foydalanish chegarasi — muloyim, qachon yangilanishi bilan ----
    "fair_limit": {
        "uz": ("⏸ Bugun {limit} ta {what} — bu kunlik chegara.\n"
               "Ertaga soat 00:00 da (Toshkent vaqti) yangilanadi. Kiritilgan "
               "hamma narsa saqlangan."),
        "ru": ("⏸ Сегодня {limit} {what} — это дневной лимит.\n"
               "Обновится завтра в 00:00 (по Ташкенту). Всё введённое сохранено."),
    },
    "what_matn": {"uz": "yozuv kiritildi", "ru": "записей"},
    "what_chek": {"uz": "chek o'qildi", "ru": "чеков"},
    "what_qa": {"uz": "savol berildi", "ru": "вопросов"},

    # ---- Teskari sinov (4.4) ----
    "trial_active": {
        "uz": "🎁 <b>{days} kunlik PRO sizda faol</b> — barcha imkoniyatlar ochiq.",
        "ru": "🎁 <b>У вас активен PRO на {days} дн.</b> — все возможности открыты.",
    },
    "trial_day5": {
        "uz": ("⏳ <b>PRO yana {days} kun faol.</b>\n\n"
               "Shu vaqtgacha: {entries} ta yozuv, {receipts} ta chek{goal}.\n\n"
               "Hozir davom ettirsangiz, qolgan kunlar yo'qolmaydi."),
        "ru": ("⏳ <b>PRO активен ещё {days} дн.</b>\n\n"
               "За это время: {entries} записей, {receipts} чеков{goal}.\n\n"
               "Продлите сейчас — оставшиеся дни сохранятся."),
    },
    "trial_goal_part": {"uz": ", maqsadingizning {pct}%", "ru": ", {pct}% цели"},
    "trial_ended": {
        "uz": ("🔔 <b>PRO sinov tugadi.</b>\n\n"
               "<b>Bepul versiyada qoladi:</b>\n"
               "• matn bilan cheksiz yozuv\n"
               "• bugun, hafta va joriy oy hisobotlari\n"
               "• qarzlar ro'yxati\n\n"
               "<b>Qulflanadi:</b>\n{locks}"),
        "ru": ("🔔 <b>Пробный PRO закончился.</b>\n\n"
               "<b>Бесплатно остаётся:</b>\n"
               "• безлимитные записи текстом\n"
               "• отчёты за сегодня, неделю и текущий месяц\n"
               "• список долгов\n\n"
               "<b>Закроется:</b>\n{locks}"),
    },
    "lock_history": {"uz": "• {month}dan oldingi tahlilingiz",
                     "ru": "• анализ до {month}"},
    "lock_goal": {"uz": "• «{goal}» maqsadingiz bashorati",
                  "ru": "• прогноз цели «{goal}»"},
    "lock_receipts": {"uz": "• chek o'qish (oyiga {n} ta)",
                      "ru": "• распознавание чеков ({n} в месяц)"},
    "lock_budget": {"uz": "• byudjet ogohlantirishlari",
                    "ru": "• уведомления о бюджете"},

    # ---- /holat ----
    "status_free": {
        "uz": "🆓 <b>Bepul versiya</b>",
        "ru": "🆓 <b>Бесплатная версия</b>",
    },
    "status_free_limits": {
        "uz": "Bu oy chek: {left}/{total} qoldi · Bugun savol: {qa_left}/{qa_total} qoldi",
        "ru": "Чеков в этом месяце: осталось {left}/{total} · Вопросов сегодня: {qa_left}/{qa_total}",
    },
    "status_free_hint": {
        "uz": "<i>PRO: cheksiz chek, barcha oylar tahlili, byudjet va CSV.</i>",
        "ru": "<i>PRO: безлимитные чеки, анализ всех месяцев, бюджет и CSV.</i>",
    },

    # ---- Ega uchun oddiy rejim (2.4) ----
    "sim_on": {
        "uz": ("🧪 <b>Oddiy rejim yoqildi.</b>\n\nEndi bot sizni obunasiz, sinovi "
               "tugagan foydalanuvchi sifatida ko'radi: limitlar, paywall va "
               "tariflar oddiy odamdagidek. To'lov tasdiqlash o'zgarmaydi.\n\n"
               "O'chirish: /oddiy_rejim off"),
        "ru": ("🧪 <b>Обычный режим включён.</b>\n\nБот видит вас как пользователя "
               "без подписки с закончившимся пробным периодом. Подтверждение "
               "оплаты не меняется.\n\nВыключить: /oddiy_rejim off"),
    },
    "sim_off": {
        "uz": "👑 Oddiy rejim o'chirildi — yana bot egasisiz.",
        "ru": "👑 Обычный режим выключен — вы снова владелец.",
    },
    # ---- Maqsadlar (3.1) ----
    "goals_title": {"uz": "🎯 <b>Maqsadlar</b>", "ru": "🎯 <b>Цели</b>"},
    "goals_empty": {
        "uz": ("Hali maqsad yo'q. Maqsad qo'ysangiz, har o'tkazmada qancha "
               "qolganini va qachon yetishingizni ko'rsatib boraman.\n\n"
               "Masalan:\n<code>/maqsad Uy uchun boshlang'ich to'lov 300 mln 2028-mart</code>"),
        "ru": ("Целей пока нет. Поставьте цель — покажу, сколько осталось и "
               "когда вы её достигнете.\n\n"
               "Например:\n<code>/maqsad Квартира 300 млн 2028-март</code>"),
    },
    "goal_line": {
        "uz": "{star}<b>{name}</b> — {percent}%\n{bar}\n{saved} / {amount}",
        "ru": "{star}<b>{name}</b> — {percent}%\n{bar}\n{saved} / {amount}",
    },
    "goal_eta": {
        "uz": "📈 Shu sur'atda maqsadga <b>{when}</b>da erishasiz (oyiga ~{pace}).",
        "ru": "📈 В таком темпе цель будет достигнута <b>{when}</b> (~{pace} в месяц).",
    },
    "goal_no_pace": {
        "uz": "📈 Bashorat uchun kamida 2 haftalik jamg'arma tarixi kerak.",
        "ru": "📈 Для прогноза нужна история накоплений хотя бы за 2 недели.",
    },
    "goal_slow": {
        "uz": "📈 Oxirgi 3 oyda jamg'arma o'smagan — hozirgi sur'atda bashorat yo'q.",
        "ru": "📈 За 3 месяца накопления не росли — прогноза при текущем темпе нет.",
    },
    "goal_need": {
        "uz": "📅 Muddat — {deadline}: oyiga <b>{need}</b> yig'ish kerak.",
        "ru": "📅 Срок — {deadline}: нужно откладывать <b>{need}</b> в месяц.",
    },
    "goal_done_line": {"uz": "🎉 Maqsadga yetildi!", "ru": "🎉 Цель достигнута!"},
    "goal_forecast_locked": {
        "uz": "🔒 «Qachon erishaman» bashorati — PRO.",
        "ru": "🔒 Прогноз «когда достигну» — в PRO.",
    },
    "goal_new_btn": {"uz": "➕ Yangi maqsad", "ru": "➕ Новая цель"},
    "goal_back_btn": {"uz": "⬅️ Maqsadlar", "ru": "⬅️ Цели"},
    "goal_primary_btn": {"uz": "⭐ Asosiy qilish", "ru": "⭐ Сделать основной"},
    "goal_archive_btn": {"uz": "🗑 Yopish", "ru": "🗑 Закрыть"},
    "goal_ask": {
        "uz": ("Maqsad nomi, summasi va (ixtiyoriy) muddatini bitta xabarda yozing:\n"
               "<code>Uy uchun boshlang'ich to'lov 300 mln 2028-mart</code>"),
        "ru": ("Напишите название, сумму и (необязательно) срок одним сообщением:\n"
               "<code>Квартира 300 млн 2028-март</code>"),
    },
    "goal_created": {
        "uz": "🎯 Maqsad qo'yildi: <b>{name}</b> — {amount}{deadline}",
        "ru": "🎯 Цель создана: <b>{name}</b> — {amount}{deadline}",
    },
    "goal_parse_fail": {
        "uz": "Summani topa olmadim. Masalan: <code>/maqsad Mashina 120 mln 2027-dekabr</code>",
        "ru": "Не нашёл сумму. Например: <code>/maqsad Машина 120 млн 2027-декабрь</code>",
    },
    "goal_primary_set": {
        "uz": ("⭐ Asosiy maqsad: <b>{name}</b>. Maqsad ko'rsatilmagan jamg'arma va "
               "«avval o'zingizga to'lang» o'tkazmalari shunga tushadi."),
        "ru": ("⭐ Основная цель: <b>{name}</b>. Накопления без указанной цели и "
               "переводы «сначала заплати себе» идут сюда."),
    },
    "goal_archived": {
        "uz": "🗑 «{name}» yopildi. Unga yig'ilgan pul jamg'armangizda qoladi.",
        "ru": "🗑 «{name}» закрыта. Накопленные деньги остаются в накоплениях.",
    },
    "goal_month": {
        "uz": "\n\n🎯 «{name}» maqsadiga <b>{left_pct}%</b> qoldi.",
        "ru": "\n\n🎯 До цели «{name}» осталось <b>{left_pct}%</b>.",
    },
    "goal_month_summary": {
        "uz": "🏦 <b>Oy xulosasi</b>\n\nBu oy <b>{saved}</b> jamg'ardingiz.{goal}",
        "ru": "🏦 <b>Итог месяца</b>\n\nВ этом месяце вы отложили <b>{saved}</b>.{goal}",
    },
    "paywall_goals": {
        "uz": ("🎯 <b>Bepul versiyada 1 ta maqsad.</b>\n\n"
               "PRO'da cheksiz maqsad va har biri uchun «qachon erishaman» bashorati."),
        "ru": ("🎯 <b>В бесплатной версии — 1 цель.</b>\n\n"
               "В PRO — сколько угодно целей и прогноз «когда достигну» для каждой."),
    },
    "feature_goals": {"uz": "Bir nechta maqsad", "ru": "Несколько целей"},

    # ---- «Avval o'zingizga to'lang» (3.2) ----
    "rate_pick": {
        "uz": ("⚖️ <b>«Avval o'zingizga to'lang»</b>\n\n"
               "Kirim yozilganda shu ulushni jamg'armaga o'tkazishni taklif "
               "qilaman{goal}.\n\nHozir: <b>{pct}%</b>"),
        "ru": ("⚖️ <b>«Сначала заплати себе»</b>\n\n"
               "Когда записывается доход, предложу отложить эту долю{goal}.\n\n"
               "Сейчас: <b>{pct}%</b>"),
    },
    "rate_goal_part": {"uz": " va uni «{name}» maqsadiga bog'layman",
                       "ru": " и привяжу к цели «{name}»"},
    "paywall_savings_auto": {
        "uz": ("⚖️ <b>Foizni sozlash va maqsadga bog'lash — PRO.</b>\n\n"
               "Bepul versiyada kirim yozilganda 10% taklifi chiqaveradi."),
        "ru": ("⚖️ <b>Настройка доли и привязка к цели — PRO.</b>\n\n"
               "В бесплатной версии остаётся предложение отложить 10%."),
    },
    "feature_savings_auto": {"uz": "Jamg'arma foizini sozlash",
                             "ru": "Настройка доли накоплений"},
    "savings_goal_tail": {"uz": " → «{name}»", "ru": " → «{name}»"},

    # ---- Qarz eslatmalari (3.3) ----
    "due_btn": {"uz": "📅 Qaytarish muddati", "ru": "📅 Срок возврата"},
    "due_pick": {"uz": "Qarz qachon qaytarilishi kerak?", "ru": "Когда нужно вернуть долг?"},
    "due_1": {"uz": "Ertaga", "ru": "Завтра"},
    "due_7": {"uz": "1 hafta", "ru": "1 неделя"},
    "due_14": {"uz": "2 hafta", "ru": "2 недели"},
    "due_30": {"uz": "1 oy", "ru": "1 месяц"},
    "due_0": {"uz": "Muddatsiz", "ru": "Без срока"},
    "due_set": {
        "uz": "📅 Muddat: <b>{date}</b>. Bir kun oldin va o'sha kuni eslataman.",
        "ru": "📅 Срок: <b>{date}</b>. Напомню за день и в этот день.",
    },
    "due_cleared": {"uz": "Muddat olib tashlandi.", "ru": "Срок убран."},
    "debt_due_them": {
        "uz": "⏰ <b>{person}</b> {amount} qarzini <b>{when}</b> qaytarishi kerak.",
        "ru": "⏰ <b>{person}</b> должен вернуть {amount} <b>{when}</b>.",
    },
    "debt_due_me": {
        "uz": "⏰ <b>{person}</b> — {amount} qarzingizni <b>{when}</b> qaytarishingiz kerak.",
        "ru": "⏰ <b>{person}</b> — вам нужно вернуть {amount} <b>{when}</b>.",
    },
    "when_today": {"uz": "bugun", "ru": "сегодня"},
    "when_tomorrow": {"uz": "ertaga", "ru": "завтра"},
    "paywall_debt_reminders": {
        "uz": ("⏰ <b>Qarz eslatmalari — PRO.</b>\n\n"
               "Muddat qo'yasiz — bir kun oldin va o'sha kuni eslataman."),
        "ru": ("⏰ <b>Напоминания о долгах — PRO.</b>\n\n"
               "Укажите срок — напомню за день и в этот день."),
    },
    "feature_debt_reminders": {"uz": "Qarz eslatmalari", "ru": "Напоминания о долгах"},

    # ---- Bepul foydalanuvchiga avtomatik xabarlar ----
    "reminder_off_btn": {"uz": "🔕 Eslatmani o'chirish", "ru": "🔕 Выключить напоминание"},
    "reminder_default_on": {
        "uz": ("🔔 Kunlik eslatma yoqilgan: soat <b>{hour}:00</b> da, faqat o'sha "
               "kuni hali hech narsa yozmagan bo'lsangiz.\n\n"
               "Soatni o'zgartirish: <code>/eslatma 20</code>\n"
               "O'chirish: <code>/eslatma o'chir</code>"),
        "ru": ("🔔 Ежедневное напоминание включено: в <b>{hour}:00</b>, только если "
               "за день ещё ничего не записано.\n\n"
               "Сменить час: <code>/eslatma 20</code>\n"
               "Выключить: <code>/eslatma o'chir</code>"),
    },
    "digest_free_empty": {
        "uz": ("\n\nO'tgan hafta yozuv kiritilmadi. Bir daqiqa — esingizdagi "
               "xarajatlarni yozib qo'ying, masalan <code>taksiga 25 ming</code>."),
        "ru": ("\n\nНа прошлой неделе записей не было. Минута — запишите, что "
               "помните, например <code>такси 25 тысяч</code>."),
    },
    "digest_pro_hint": {
        "uz": "\n\n💎 PRO: barcha oylar tahlili, maqsad bashorati va cheksiz chek — /obuna",
        "ru": "\n\n💎 PRO: анализ всех месяцев, прогноз целей и безлимитные чеки — /obuna",
    },
    "goal_month_free": {
        "uz": "🎯 <b>Oy yakuni</b>\n\n«{name}» — <b>{percent}%</b>\n{bar}\n{saved} / {amount}",
        "ru": "🎯 <b>Итог месяца</b>\n\n«{name}» — <b>{percent}%</b>\n{bar}\n{saved} / {amount}",
    },

    # ---- /xabar_yubor: mavjud foydalanuvchilarga bir martalik xabar ----
    "broadcast_default": {
        "uz": ("🪙 <b>Tanga'da yangiliklar</b>\n\n"
               "• Qarz to'lovlari endi xarajatga qo'shilmaydi — oylik "
               "statistikangiz aniqroq\n"
               "• Chek bitta yozuv bo'lib saqlanadi, chegirma to'g'ri hisoblanadi\n"
               "• Kategoriyani bir marta tuzatsangiz, bot uni eslab qoladi\n"
               "{founders}\n\n"
               "Tariflar: /obuna"),
        "ru": ("🪙 <b>Новое в Tanga</b>\n\n"
               "• Платежи по долгам больше не считаются расходами — "
               "статистика точнее\n"
               "• Чек сохраняется одной записью, скидка учитывается правильно\n"
               "• Исправьте категорию один раз — бот запомнит\n"
               "{founders}\n\n"
               "Тарифы: /obuna"),
    },
    "broadcast_founders": {
        "uz": ("\n🎁 <b>Asoschilar taklifi:</b> PRO birinchi yil — {price} "
               "(odatda {yearly}). Faqat birinchi {total} kishi uchun, qolgan "
               "joylar: {left}."),
        "ru": ("\n🎁 <b>Предложение основателям:</b> PRO на первый год — {price} "
               "(обычно {yearly}). Только для первых {total}, осталось мест: {left}."),
    },
    "sim_usage": {
        "uz": "Foydalanish: <code>/oddiy_rejim on</code> yoki <code>/oddiy_rejim off</code>\nHozir: {state}",
        "ru": "Использование: <code>/oddiy_rejim on</code> или <code>/oddiy_rejim off</code>\nСейчас: {state}",
    },
})


def _resolve(entry: dict, lang: str, fallback: str) -> str:
    """Kerakli tildagi matnni beradi. Kirill uchun lotinchasidan o'giradi."""
    if lang == "uzc":
        return translit.to_cyrillic(entry.get("uz") or fallback)
    return entry.get(lang) or entry.get(DEFAULT) or fallback


def t(lang: str | None, key: str, **kwargs) -> str:
    """Kalit bo'yicha matn. Tarjima topilmasa o'zbekchasi qaytariladi."""
    entry = T.get(key)
    if entry is None:
        return key
    text = _resolve(entry, normalize(lang), key)
    # O'rin egallovchilar o'girishdan keyin to'ldiriladi — ichidagi qiymat
    # (sana, summa) transliteratsiyaga tushmasligi kerak.
    return text.format(**kwargs) if kwargs else text


def btn(lang: str | None, key: str) -> str:
    return _resolve(BUTTONS.get(key, {}), normalize(lang), key)


def cyr(lang: str | None, text: str) -> str:
    """Tarjima jadvalidan tashqaridagi o'zbekcha matnni kerak bo'lsa o'giradi.

    Uzun qo'llanma va hisobot sarlavhalari kabi joylar uchun.
    """
    return translit.to_cyrillic(text) if normalize(lang) == "uzc" else text


def menu_lookup() -> dict[str, str]:
    """Barcha tildagi tugma matnlarini kalitga bog'laydi.

    Foydalanuvchi tilni almashtirsa, eski klaviatura hali ekranda turgan
    bo'lishi mumkin — shuning uchun ikkala til ham qabul qilinadi.
    """
    out: dict[str, str] = {}
    for key, variants in BUTTONS.items():
        for text in variants.values():
            out[text] = key
        # Kirill yozuvidagi variant ham qabul qilinsin.
        out[translit.to_cyrillic(variants.get("uz", ""))] = key
    out.pop("", None)
    return out
