"""Bot xabarlari: tugmalar, xato va holat matnlari, buyruqlar tavsifi.

`i18n.T` ga qo'shiladi (i18n.py oxirida). Kirill o'zbekchasi bu yerda
yozilmaydi — lotinchadan avtomatik o'giriladi. Foydalanuvchi kiritgan
qiymatlar (ism, izoh) `{...}` o'rin egallovchisi orqali, tarjimadan
KEYIN qo'yiladi.
"""

from __future__ import annotations

TEXTS = {
    # ---- Inline tugmalar ----
    "btn_category": {"uz": "✏️ Kategoriya", "ru": "✏️ Категория"},
    "btn_delete": {"uz": "🗑 O'chirish", "ru": "🗑 Удалить"},
    "btn_due": {"uz": "📅 Qaytarish muddati", "ru": "📅 Срок возврата"},
    "btn_entry_n": {"uz": "✏️ {n}-yozuv", "ru": "✏️ Запись {n}"},
    "btn_delete_all": {"uz": "🗑 Hammasini o'chirish", "ru": "🗑 Удалить все"},
    "btn_full_list": {"uz": "📋 To'liq ro'yxat", "ru": "📋 Полный список"},
    "btn_receipt_more": {"uz": "➕ Chek davomi bor", "ru": "➕ Продолжение чека"},
    "btn_receipt_delete": {"uz": "🗑 Chekni o'chirish", "ru": "🗑 Удалить чек"},
    "btn_back": {"uz": "⬅️ Bekor", "ru": "⬅️ Отмена"},
    "btn_compare": {"uz": "📊 O'tgan oy bilan solishtirish",
                    "ru": "📊 Сравнить с прошлым месяцем"},

    # ---- Umumiy qisqa javoblar ----
    "err_no_access": {"uz": "Ruxsat yo'q.", "ru": "Нет доступа."},
    "bad_choice": {"uz": "Noto'g'ri tanlov", "ru": "Неверный выбор"},
    "example_missing": {"uz": "Misol topilmadi", "ru": "Пример не найден"},
    "cancelled": {"uz": "Bekor qilindi.", "ru": "Отменено."},
    "old_button": {
        "uz": "Bu tugma endi ishlamaydi. /obuna dan qayta boshlang.",
        "ru": "Эта кнопка больше не работает. Начните заново с /obuna.",
    },
    "offer_expired": {
        "uz": "Taklif eskirdi. Summani o'zingiz yozing.",
        "ru": "Предложение устарело. Напишите сумму сами.",
    },
    "goal_not_found": {"uz": "Maqsad topilmadi", "ru": "Цель не найдена"},
    "debt_not_found": {"uz": "Qarz topilmadi", "ru": "Долг не найден"},
    "debt_person_default": {"uz": "Qarz", "ru": "Долг"},
    "debt_person_unknown": {"uz": "noma'lum", "ru": "не указан"},
    "answer_error": {
        "uz": "⚠️ Javob tayyorlashda xatolik yuz berdi.",
        "ru": "⚠️ Не удалось подготовить ответ.",
    },
    "today_expense": {
        "uz": "<i>Bugungi chiqim: {amount}</i>",
        "ru": "<i>Расходы сегодня: {amount}</i>",
    },

    # ---- Yozuvni o'chirish va tuzatish ----
    "toast_deleted": {"uz": "O'chirildi", "ru": "Удалено"},
    "entry_deleted": {"uz": "🗑 Yozuv o'chirildi.", "ru": "🗑 Запись удалена."},
    "entries_deleted": {"uz": "🗑 {n} ta yozuv o'chirildi.",
                        "ru": "🗑 Удалено записей: {n}."},
    "receipt_deleted": {"uz": "🗑 Chek o'chirildi ({n} ta yozuv).",
                        "ru": "🗑 Чек удалён (записей: {n})."},
    "entry_gone": {
        "uz": "Yozuv topilmadi (o'chirilgan bo'lishi mumkin)",
        "ru": "Запись не найдена (возможно, удалена)",
    },
    "entry_not_found": {"uz": "Yozuv topilmadi", "ru": "Запись не найдена"},
    "bad_category": {"uz": "Noto'g'ri kategoriya", "ru": "Неверная категория"},
    "learned_toast": {"uz": "Eslab qoldim: «{word}» → {category}",
                      "ru": "Запомнил: «{word}» → {category}"},
    "updated_toast": {"uz": "Yangilandi", "ru": "Обновлено"},
    "category_updated": {"uz": "✏️ Kategoriya yangilandi",
                         "ru": "✏️ Категория обновлена"},
    "kind_locked": {"uz": "Bu yozuv turini almashtirib bo'lmaydi",
                    "ru": "Тип этой записи изменить нельзя"},
    "kind_updated": {"uz": "Turi yangilandi", "ru": "Тип обновлён"},
    "hint_fix_category": {
        "uz": "\n\n<i>Kategoriyani ham to'g'rilash uchun «✏️ Kategoriya» bosing.</i>",
        "ru": "\n\n<i>Чтобы исправить и категорию, нажмите «✏️ Категория».</i>",
    },
    "hint_debt_payment": {
        "uz": "\n\n<i>Qarz to'lovi kundalik chiqim va kirimga kirmaydi.</i>",
        "ru": "\n\n<i>Выплата долга не входит в ежедневные расходы и доходы.</i>",
    },
    "kind_switched": {"uz": "🔄 {kind}ga almashtirildi",
                      "ru": "🔄 Тип изменён: {kind}"},
    "usage_delete": {"uz": "Foydalanish: /ochir 12", "ru": "Использование: /ochir 12"},
    "usage_settle": {"uz": "Foydalanish: /yopdim 12", "ru": "Использование: /yopdim 12"},
    "entry_nf": {"uz": "#{id} topilmadi.", "ru": "#{id} не найдена."},
    "entry_removed": {"uz": "🗑 #{id} o'chirildi.", "ru": "🗑 #{id} удалена."},
    "receipt_removed": {"uz": "🗑 Chek o'chirildi ({n} ta mahsulot).",
                        "ru": "🗑 Чек удалён (товаров: {n})."},
    "debt_closed": {"uz": "✅ #{id} qarzi yopildi.", "ru": "✅ Долг #{id} закрыт."},
    "debt_closed_nf": {"uz": "#{id} ochiq qarzlar orasida topilmadi.",
                       "ru": "#{id} среди открытых долгов не найден."},
    "csv_empty": {"uz": "Eksport qilish uchun yozuv yo'q.",
                  "ru": "Нет записей для экспорта."},
    "csv_caption": {"uz": "{n} ta yozuv.", "ru": "Записей: {n}."},
    "share_failed": {"uz": "Rasm tayyorlab bo'lmadi",
                     "ru": "Не удалось подготовить картинку"},

    # ---- Chek ----
    "err_file_type": {
        "uz": ("Bu fayl turi qo'llab-quvvatlanmaydi.\n"
               "Chekni rasm (JPG/PNG) yoki PDF ko'rinishida yuboring."),
        "ru": ("Этот тип файла не поддерживается.\n"
               "Отправьте чек как фото (JPG/PNG) или PDF."),
    },
    "err_file_missing": {"uz": "Chek fayli topilmadi.", "ru": "Файл чека не найден."},
    "err_file_big": {
        "uz": "Fayl juda katta ({size} MB, chegara {limit} MB).",
        "ru": "Файл слишком большой ({size} МБ, лимит {limit} МБ).",
    },
    "err_total_big": {
        "uz": ("Chek fayllari jami hajmi juda katta (chegara {mb} MB). "
               "Kamroq yoki kichikroq rasm yuboring."),
        "ru": ("Общий размер файлов чека слишком большой (лимит {mb} МБ). "
               "Отправьте меньше или более лёгких фото."),
    },
    "err_download": {
        "uz": "⚠️ Faylni yuklab olishda xatolik yuz berdi.",
        "ru": "⚠️ Не удалось загрузить файл.",
    },
    "err_parts_max": {
        "uz": ("Bitta chek uchun ko'pi bilan {max} ta rasm yuborish mumkin "
               "(siz {n} ta yubordingiz)."),
        "ru": ("Для одного чека можно отправить не больше {max} фото "
               "(вы отправили {n})."),
    },
    "err_album_max": {
        "uz": ("Bitta chek uchun ko'pi bilan {max} ta rasm yuborish mumkin. "
               "Chekni kamroq qismga bo'lib qayta yuboring."),
        "ru": ("Для одного чека можно отправить не больше {max} фото. "
               "Разделите чек на меньшее число частей и отправьте снова."),
    },
    "receipt_reading": {"uz": "🔍 Chek o'qilmoqda{parts}…",
                        "ru": "🔍 Читаю чек{parts}…"},
    "receipt_parts": {"uz": " ({n} ta qism)", "ru": " ({n} ч.)"},
    "receipt_error": {
        "uz": "⚠️ Chekni o'qishda xatolik yuz berdi. Birozdan keyin urinib ko'ring.",
        "ru": "⚠️ Ошибка при чтении чека. Попробуйте чуть позже.",
    },
    "receipt_unreadable": {
        "uz": ("Chekni o'qib bo'lmadi. Yorug'roq, to'g'ridan-to'g'ri tushirilgan "
               "surat yuboring."),
        "ru": ("Не удалось прочитать чек. Отправьте более светлое фото, "
               "снятое прямо сверху."),
    },
    "receipt_images_gone": {
        "uz": "Bu chek rasmlari saqlanmagan. «🧾 Uzun chek» bilan qaytadan yuboring.",
        "ru": "Фото этого чека не сохранены. Отправьте заново через «🧾 Длинный чек».",
    },
    "receipt_more_prompt": {
        "uz": ("➕ Chekning qolgan qismlarini yuboring "
               "({n} ta qism allaqachon bor).\n"
               "Tugagach «✅ Tayyor» bosing — chek boshidan qayta hisoblanadi."),
        "ru": ("➕ Отправьте остальные части чека "
               "(уже есть частей: {n}).\n"
               "Закончив, нажмите «✅ Готово» — чек будет пересчитан заново."),
    },
    "receipt_more_wait": {"uz": "Qolgan qismlarni kutyapman…",
                          "ru": "Жду остальные части…"},
    "part_accepted": {
        "uz": "✅ {n}-qism qabul qilindi.\nYana yuboring yoki «✅ Tayyor» bosing.",
        "ru": "✅ Часть {n} принята.\nОтправьте ещё или нажмите «✅ Готово».",
    },
    "collect_intro": {
        "uz": ("🧾 <b>Uzun chek rejimi</b>\n\n"
               "Chekni qismlarga bo'lib suratga oling va ketma-ket yuboring "
               "(yuqoridan pastga). Qismlar bir-birini biroz takrorlasa ham "
               "bo'ladi — takroriy qatorlar bir marta hisoblanadi.\n\n"
               "Hammasi tayyor bo'lgach «✅ Tayyor» bosing."),
        "ru": ("🧾 <b>Режим длинного чека</b>\n\n"
               "Сфотографируйте чек по частям и отправляйте подряд "
               "(сверху вниз). Части могут немного перекрываться — "
               "повторяющиеся строки посчитаются один раз.\n\n"
               "Когда всё отправлено, нажмите «✅ Готово»."),
    },
    "collect_none": {"uz": "Hech qanday rasm yuborilmadi.",
                     "ru": "Не отправлено ни одного фото."},
    "collect_got": {"uz": "📥 {n} ta qism qabul qilindi.",
                    "ru": "📥 Принято частей: {n}."},
    "collect_caption_saved": {
        "uz": "📝 Izoh saqlandi. Chek qismlarini yuborishda davom eting.",
        "ru": "📝 Заметка сохранена. Продолжайте отправлять части чека.",
    },

    # ---- Byudjet (bot.py dagi matnlar; qolganlari i18n.py da) ----
    "budget_which_off": {
        "uz": "Qaysi kategoriya? Masalan: <code>/byudjet transport o'chir</code>",
        "ru": "Какая категория? Например: <code>/byudjet transport o'chir</code>",
    },
    "budget_which_set": {
        "uz": "Qaysi kategoriyaga <b>{amount}</b> oylik byudjet qo'yamiz?",
        "ru": "На какую категорию установить месячный бюджет <b>{amount}</b>?",
    },
    "budget_none": {"uz": "«{cat}» uchun byudjet yo'q edi.",
                    "ru": "Для «{cat}» бюджета не было."},
    "budget_cats": {"uz": "<i>Kategoriyalar: {cats} …</i>",
                    "ru": "<i>Категории: {cats} …</i>"},
    "budget_change": {
        "uz": "<i>O'zgartirish: /byudjet &lt;kategoriya&gt; &lt;summa&gt;</i>",
        "ru": "<i>Изменить: /byudjet &lt;категория&gt; &lt;сумма&gt;</i>",
    },

    # ---- Ovozli kiritish ----
    "voice_heard": {"uz": "🎤 <i>«{text}»</i>", "ru": "🎤 <i>«{text}»</i>"},
    "voice_too_long": {
        "uz": ("Ovoz {sec} soniyadan oshmasin. Bir nechta xarajatni bitta "
               "qisqa xabarda aytsangiz bo'ladi."),
        "ru": ("Голосовое сообщение не должно быть длиннее {sec} секунд. "
               "Несколько расходов можно сказать в одном коротком сообщении."),
    },
    "voice_disabled": {
        "uz": "Ovozli kiritish tez orada. Hozircha matn bilan yozing.",
        "ru": "Голосовой ввод скоро появится. Пока пишите текстом.",
    },
    "voice_not_understood": {
        "uz": "Ovozni tushunib bo'lmadi. Aniqroq ayting yoki yozing: «obedga 45 ming»",
        "ru": "Не удалось понять голос. Скажите чётче или напишите: «обед 45 тысяч»",
    },
    "voice_bad_format": {
        "uz": "Bu audio formati qo'llab-quvvatlanmaydi. Ovozli xabar yuboring.",
        "ru": "Этот формат аудио не поддерживается. Отправьте голосовое сообщение.",
    },
    "voice_confirm_title": {
        "uz": "🎤 <i>«{text}»</i>\n\nShunday tushundim:",
        "ru": "🎤 <i>«{text}»</i>\n\nЯ понял так:",
    },
    "voice_btn_save": {"uz": "✅ Saqlash", "ru": "✅ Сохранить"},
    "voice_btn_cancel": {"uz": "❌ Bekor", "ru": "❌ Отмена"},
    "voice_btn_text": {"uz": "✏️ Matn bilan yozaman", "ru": "✏️ Напишу текстом"},
    "voice_saved": {"uz": "✅ Saqlandi", "ru": "✅ Сохранено"},
    "voice_cancelled": {"uz": "Bekor qilindi. Hech narsa saqlanmadi.",
                        "ru": "Отменено. Ничего не сохранено."},
    "voice_expired": {
        "uz": "Bu taklif eskirdi, qaytadan ayting yoki yozing.",
        "ru": "Это предложение устарело — скажите или напишите ещё раз.",
    },
    "voice_text_prompt": {"uz": "Yozib yuboring, masalan «obedga 45 ming»",
                          "ru": "Напишите, например: «обед 45 тысяч»"},
    "voice_in_collect_mode": {
        "uz": ("Uzun chek rejimida ovoz qabul qilinmaydi. «✅ Tayyor» yoki "
               "«❌ Bekor» bosing."),
        "ru": ("В режиме длинного чека голос не принимается. Нажмите "
               "«✅ Готово» или «❌ Отмена»."),
    },
    "voice_in_erase_mode": {
        "uz": ("Tasdiq so'zini yozib yuboring — hisobni o'chirish ovoz bilan "
               "tasdiqlanmaydi."),
        "ru": ("Напишите слово подтверждения текстом — удаление аккаунта "
               "голосом не подтверждается."),
    },
    "voice_video_note": {"uz": "Hozircha faqat ovozli xabar qabul qilinadi.",
                         "ru": "Пока принимаются только голосовые сообщения."},
    "welcome_voice": {"uz": "🎤 Ovozli xabar ham yuborishingiz mumkin.\n",
                      "ru": "🎤 Можно отправить и голосовое сообщение.\n"},
    "what_ovoz": {"uz": "ovozli xabar yuborildi", "ru": "голосовых сообщений"},
    "feature_voice": {"uz": "Ovozli xabarlar (bugungi limit tugadi)",
                      "ru": "Голосовые сообщения (дневной лимит исчерпан)"},
    "paywall_voice": {
        "uz": ("🎤 <b>Bugungi {limit} ta bepul ovozli xabar ishlatildi.</b>\n\n"
               "Ertaga yana {limit} ta ochiladi. Hozircha xarajatni matn bilan "
               "yozishingiz mumkin — bu cheksiz. PRO'da kuniga ancha ko'p "
               "ovozli xabar."),
        "ru": ("🎤 <b>{limit} бесплатных голосовых на сегодня использованы.</b>\n\n"
               "Завтра откроются ещё {limit}. Пока можно писать расходы "
               "текстом — это без ограничений. В PRO голосовых намного больше."),
    },

    # ---- Mini App (webapp.py) xatolari ----
    "wa_blocked": {"uz": "Hisobingiz bloklangan.", "ru": "Ваш аккаунт заблокирован."},
    "wa_closed": {"uz": "Bot hozircha yopiq sinovda.",
                  "ru": "Бот пока на закрытом тестировании."},
    "wa_consent": {
        "uz": "Avval botda shartlarga rozilik bering: /start",
        "ru": "Сначала согласитесь с условиями в боте: /start",
    },
    "wa_rate_limit": {
        "uz": "Juda ko'p so'rov. Bir daqiqadan keyin urinib ko'ring.",
        "ru": "Слишком много запросов. Попробуйте через минуту.",
    },
    "wa_bad_date": {"uz": "Noto'g'ri sana: {raw}", "ru": "Неверная дата: {raw}"},
    "wa_bad_kind": {"uz": "Noto'g'ri turi", "ru": "Неверный тип"},
    "wa_bad_currency": {"uz": "Noto'g'ri valyuta", "ru": "Неверная валюта"},
    "wa_receipt_nf": {"uz": "Chek topilmadi", "ru": "Чек не найден"},
    "wa_open_debt_nf": {"uz": "Ochiq qarz topilmadi",
                        "ru": "Открытый долг не найден"},
    "wa_over_remaining": {"uz": "Qoldiqdan ko'p: qoldiq {left}",
                          "ru": "Больше остатка: остаток {left}"},
    "wa_person_needed": {"uz": "Qarz uchun shaxs ismi kerak",
                         "ru": "Для долга нужно имя человека"},

    # ---- Valyuta kursi ----
    "fx_rate_page": {
        "uz": ("\U0001F4B1 <b>Valyuta kursi</b>\n\n"
               "1 $ = <b>{rate}</b>\n"
               "<i>Manba: Markaziy bank — har kuni ertalab yangilanadi</i>\n\n"
               "Dollarda yozgan yozuvlaringiz shu kurs bilan umumiy hisobga "
               "qo'shiladi. Har bir yozuv o'z kunidagi kursni saqlab qoladi "
               "— kurs o'zgarsa ham eski hisobot o'zgarmaydi."),
        "ru": ("\U0001F4B1 <b>Курс валюты</b>\n\n"
               "1 $ = <b>{rate}</b>\n"
               "<i>Источник: Центральный банк — обновляется каждое утро</i>\n\n"
               "Записи в долларах попадают в общий учёт по этому курсу. "
               "Каждая запись сохраняет курс своего дня — "
               "старые отчёты не меняются при смене курса."),
    },

    # ---- /buyruqlar ----
    "commands_title": {"uz": "\U0001F4CB <b>BUYRUQLAR</b>",
                       "ru": "\U0001F4CB <b>КОМАНДЫ</b>"},
    "commands_footer": {
        "uz": ("<i>Yozuv qo'shish uchun buyruq kerak emas — "
               "shunchaki yozing: <code>obedga 45 ming</code></i>"),
        "ru": ("<i>Чтобы добавить запись, команда не нужна — "
               "просто напишите: <code>обед 45 тысяч</code></i>"),
    },
}

# Buyruqlar ro'yxati (o'zbekchasi bot.py da COMMAND_SECTIONS) uchun rus tavsiflari.
SECTION_RU = {
    "Yozish": "Записи",
    "Hisobotlar": "Отчёты",
    "Jamg'arma": "Накопления",
    "Qarzlar": "Долги",
    "Rejalashtirish": "Планирование",
    "Obuna": "Подписка",
    "Sozlamalar": "Настройки",
}

COMMAND_RU = {
    "start": "Начало и помощь",
    "chek": "Отправить длинный чек по частям",
    "ochir": "Удалить запись: /ochir 12",
    "oxirgi": "Последние записи",
    "bugun": "Отчёт за сегодня",
    "kecha": "Отчёт за вчера",
    "hafta": "Отчёт за неделю",
    "oy": "Отчёт за месяц",
    "otganoy": "Отчёт за прошлый месяц",
    "yil": "Отчёт за год",
    "solishtir": "Сравнить месяц с прошлым",
    "csv": "Выгрузить все записи в файл",
    "jamgarma": "Остаток и состояние накоплений",
    "foiz": "Задать процент накоплений: /foiz 10",
    "maqsadlar": "Цели и прогноз",
    "maqsad": "Новая цель: /maqsad Uy 300 mln 2028-mart",
    "holatim": "Чистая стоимость: накопления и долги",
    "qarz": "Список открытых долгов",
    "yopdim": "Закрыть долг: /yopdim 12",
    "reja": "План выхода из долгов",
    "byudjet": "Месячный лимит по категории",
    "eslatma": "Настроить ежедневное напоминание",
    "kurs": "Курс доллара на сегодня",
    "obuna": "Тарифы и оплата",
    "holat": "Статус подписки и лимиты на сегодня",
    "taklif": "Пригласите друга — вам обоим +7 дней PRO",
    "buyruqlar": "Все команды по разделам",
    "qollanma": "Полная инструкция",
    "til": "Til / Язык",
    "maxfiylik": "Политика конфиденциальности",
    "shartlar": "Условия сервиса",
    "ochirish": "Полностью удалить аккаунт",
}
