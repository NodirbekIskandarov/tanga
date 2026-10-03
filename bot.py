"""Shaxsiy moliya boti — Telegram + Anthropic Claude.

Ishga tushirish:  python bot.py
"""

from __future__ import annotations

import asyncio
import base64
import io
import logging
import time
import uuid
from datetime import date, datetime, timedelta
from functools import wraps
from urllib.parse import quote

from telegram import (
    InlineKeyboardButton,
    InlineKeyboardMarkup,
    KeyboardButton,
    MenuButtonDefault,
    MenuButtonWebApp,
    ReplyKeyboardMarkup,
    Update,
    WebAppInfo,
)
from telegram.constants import ChatAction, ParseMode
from telegram.ext import (
    Application,
    CallbackQueryHandler,
    CommandHandler,
    ContextTypes,
    MessageHandler,
    filters,
)

import ai
import analytics
import broadcast
import config
import db
import goals
import notify
import profile_texts
import guide_ru
import i18n
import learning
import tiers
import rates
import reports
import sharecard

logging.basicConfig(
    format="%(asctime)s | %(levelname)-8s | %(name)s | %(message)s",
    level=logging.INFO,
)
logging.getLogger("httpx").setLevel(logging.WARNING)
log = logging.getLogger("tanga")

# Anthropic API qo'llaydigan rasm turlari.
SUPPORTED_IMAGE_TYPES = {"image/jpeg", "image/png", "image/gif", "image/webp"}
PDF_TYPE = "application/pdf"

# Albom (bir vaqtda yuborilgan bir nechta rasm) to'planishini kutish vaqti.
ALBUM_WAIT_SECONDS = 3.0

GUIDE_TEXT = """\U0001F4D6 <b>FOYDALANISH YO'RIQNOMASI</b>

Tanga \u2014 moliyaviy yozuvlaringizni yuritadigan bot. Xarajat va
kirimni oddiy tilda yozasiz, qolganini bot qiladi.

<i>Bu yo'riqnoma uzun. Kerakli bo'limni qidirib o'qing \u2014
buyruqlar ro'yxati uchun /buyruqlar, boshidan boshlash uchun
/start. Bu matnni istalgan vaqtda /qollanma bilan ochasiz.</i>

\u2501\u2501\u2501\u2501\u2501\u2501\u2501\u2501\u2501\u2501\u2501\u2501\u2501\u2501\u2501
\U0001F4DD <b>1. YOZISH</b>

Shunchaki oddiy tilda yozing \u2014 bot summani, turini va
kategoriyani o'zi aniqlaydi.

<b>Sonlarni qanday yozish mumkin:</b>
\u2022 <code>ming</code> yoki <code>k</code> = 1 000 \u2192 <code>45 ming</code>, <code>20k</code>
\u2022 <code>mln</code>, <code>million</code>, <code>lim</code> = 1 000 000 \u2192 <code>1.5 mln</code>
\u2022 Bo'sh joy bilan \u2192 <code>1 200 000</code>
\u2022 Birliksiz kichik son ming deb olinadi \u2192 <code>obedga 50</code> = 50 000

<b>Chiqim va kirim:</b>
<code>obedga 45 ming</code>
<code>oylik tushdi 8 mln</code>
<code>sotuvdan 500 ming kirdi</code>

<b>Qarz:</b>
<code>Aliga 500 ming qarz berdim</code>
<code>akamdan 1 mln qarz oldim</code>
\u2192 kim kimga qarzdorligi alohida kuzatiladi

<b>Shaxsiy jamg'arma:</b>
<code>jamg'armaga 500 ming o'tkazdim</code>
<code>omonatga 1 mln qo'ydim</code>
<code>jamg'armadan 200 ming oldim</code>
\u2192 Jamg'arma <b>chiqim emas</b>: bu pul sarflanmadi, sizda
qoldi. Shuning uchun \u00abFarq\u00bb ga qo'shilmaydi va hisobotda
alohida turadi.

<b>Bitta xabarda bir nechta yozuv:</b>
<code>taksi 20k, kofe 25 ming, non 8 ming</code>
\u2192 3 ta alohida yozuv saqlanadi

<b>Sanani ko'rsatish:</b>
<code>kecha dorixonaga 90 ming</code>
<code>1-avgustda benzin 100 ming</code>
Sana aytilmasa \u2014 bugungi kun.

<b>Dollarda yozish:</b>
<code>$100</code>, <code>50 dollar</code>, <code>200 dollar oylik berdim</code>
\u2192 bu yerda ming qoidasi qo'llanmaydi, son aynan yoziladi.

Dollardagi yozuv <b>o'sha kundagi rasmiy kurs</b> bilan so'mga
o'girilib, umumiy jamlanmaga qo'shiladi \u2014 hamyoningiz bitta.
Hisobot pastida \u00abShundan chet el valyutasida\u00bb qatori
qancha qismi dollarda bo'lganini ko'rsatadi.

Kurs har bir yozuvda <b>o'sha kunga muhrlanadi</b>: ertaga kurs
o'zgarsa ham o'tgan oy hisoboti o'zgarmaydi. Bugungi kursni
/kurs ko'rsatadi (u Markaziy bankdan olinadi, qo'lda
o'zgartirilmaydi \u2014 aks holda hisobot ishonchsiz bo'lardi).

\u2501\u2501\u2501\u2501\u2501\u2501\u2501\u2501\u2501\u2501\u2501\u2501\u2501\u2501\u2501
\U0001F4F7 <b>2. CHEK RASMINI YUBORISH</b>

Chek suratini yuborsangiz, bot undagi <b>har bir mahsulotni</b>
o'qib, kategoriyalarga ajratib bazaga yozadi.

<b>Oddiy chek:</b> shunchaki rasmni yuboring.

<b>Uzun chek (kadrga sig'masa) \u2014 2 ta usul:</b>

<i>A) Albom qilib yuborish (eng qulay)</i>
Chekni qismlarga bo'lib suratga oling \u2192 galereyadan
hammasini belgilang \u2192 birdan yuboring. Bot ularni
bitta chek deb qabul qiladi.

<i>B) Bitta-bitta yuborish</i>
/chek buyrug'ini yuboring yoki \u00ab\U0001F9FE Uzun chek\u00bb
tugmasini bosing \u2192 qismlarni ketma-ket yuboring \u2192
/tayyor bosing. Bekor qilish uchun /bekor.

Chek natijasidan keyin \u00ab\u2795 Chek davomi bor\u00bb tugmasi
ham bor \u2014 qism esdan chiqsa, o'shani bosib qo'shasiz.

\u26a0\ufe0f <b>Qismlar bir-birini takrorlasa ham bo'ladi</b> \u2014 bir xil
qator ikki rasmda ko'rinsa, bir marta hisoblanadi.

\u2501\u2501\u2501\u2501\u2501\u2501\u2501\u2501\u2501\u2501\u2501\u2501\u2501\u2501\u2501
\u2705 <b>3. ANIQLIK VA TEKSHIRUV</b>

Bot mahsulotlar summasini <b>o'zi hisoblaydi</b> (AI emas) va
chekdagi \u00abJAMI\u00bb bilan solishtiradi:

\u2705 <b>Mos</b> \u2014 summa to'g'ri o'qilgan, ishonch yuqori
\u26a0\ufe0f <b>Farqli</b> \u2014 nomuvofiqlik bor. Bunda bot chekni
   avtomatik <b>qayta o'qiydi</b>. Baribir farq qolsa,
   sizga farq miqdori ko'rsatiladi \u2014 \u00ab\U0001F4CB To'liq ro'yxat\u00bb
   dan tekshiring.
\u2139\ufe0f <b>Jami ko'rinmadi</b> \u2014 chekda yakuniy summa yo'q,
   tekshirib bo'lmadi.

<b>Rasm sifati uchun maslahatlar:</b>
\u2022 Rasmni <b>Fayl</b> sifatida yuboring (Telegram siqmaydi)
\u2022 Yorug' joyda, to'g'ridan-to'g'ri suratga oling
\u2022 Chek tekis yotsin, burchaklari ko'rinsin
\u2022 Soyalar va yorqin nur tushmasin

\u2501\u2501\u2501\u2501\u2501\u2501\u2501\u2501\u2501\u2501\u2501\u2501\u2501\u2501\u2501
\U0001F527 <b>4. XATONI TUZATISH</b>

Har bir yozuv ostida tugmalar bor:
\u2022 <b>\u270f\ufe0f Kategoriya</b> \u2014 kategoriyani almashtirish.
  Bot buni <b>eslab qoladi</b>: bir marta "suv" ni
  oziq-ovqatga o'zgartirsangiz, keyingi "suv" o'zi shu yerga tushadi
\u2022 <b>\U0001F504 Turini almashtirish</b> \u2014 masalan chiqimni
  "qarzimni qaytardim" ga
\u2022 <b>\U0001F5D1 O'chirish</b> \u2014 yozuvni o'chirish

Bitta xabarda bir nechta yozuv bo'lsa \u2014 har biri uchun
alohida <b>\u270f\ufe0f</b> tugmasi chiqadi.

Chek uchun:
\u2022 <b>\U0001F4CB To'liq ro'yxat</b> \u2014 barcha mahsulotlar raqami bilan
\u2022 <b>\U0001F5D1 Chekni o'chirish</b> \u2014 butun chekni bir bosishda

Raqam bo'yicha o'chirish: <code>/ochir 12</code>
Oxirgi yozuvlarni ko'rish: /oxirgi

\u2501\u2501\u2501\u2501\u2501\u2501\u2501\u2501\u2501\u2501\u2501\u2501\u2501\u2501\u2501
\U0001F4CA <b>5. HISOBOTLAR</b>

/bugun /kecha /hafta /oy /otganoy /yil

Har birida: kirim, chiqim, farq, kategoriyalar foizli
diagramma bilan va kunlik o'rtacha.

Oylik hisobot oxirida <b>oylik baho</b> ham bor \u2014 uchta
savol: jamg'arma foizingizni bajardingizmi, daromaddan kam
sarfladingizmi, qarz ko'paymadimi.

Yillik hisobotda esa yil davomida qancha jamg'arganingiz va
necha oyda foizni bajarganingiz ko'rsatiladi.

\u2501\u2501\u2501\u2501\u2501\u2501\u2501\u2501\u2501\u2501\u2501\u2501\u2501\u2501\u2501
\U0001F3E6 <b>6. JAMG'ARMA</b>

Bu bo'lim bitta oddiy qoidaga tayanadi:
<b>topganingizning bir qismi o'zingizga qolishi kerak</b>.

Standart foiz \u2014 10%. PRO'da uni o'zingizga moslaysiz
(/foiz \u2014 10, 15, 20 yoki 30%) va o'tkazma asosiy maqsadga
bog'lanadi. Muhimi muntazamlik, miqdor emas.

/jamgarma \u2014 qoldiq, alohida karta holati va maslahat
/foiz \u2014 jamg'arma foizi (PRO)
\U0001F3AF Maqsadlar (/maqsadlar) \u2014 har bir maqsad progressi va
   <b>\u00abqachon erishaman\u00bb bashorati</b> (PRO)
/maqsad \u2014 yangi maqsad:
   <code>/maqsad Uy uchun boshlang'ich to'lov 300 mln 2028-mart</code>
   Jamg'armani maqsadga yozing: <i>"mashina uchun 3 mln qo'ydim"</i>
/holatim \u2014 <b>sof qiymat</b>: jamg'arma + sizga qarzdorlar
   \u2212 sizning qarzingiz. Bu oqim emas, <b>holat</b>.

<b>Bot o'zi nima qiladi:</b>
\u2022 Kirim yozsangiz \u2014 o'z foizingizni hisoblab, bitta
  tugma bilan jamg'armaga o'tkazishni taklif qiladi
\u2022 Oyning oxirgi kuni 18:00 da \u2014 jamg'arma haqida eslatma
  (agar o'sha oy foizni bajargan bo'lsangiz, bezovta
  qilmaydi)
\u2022 Ketma-ket necha oy foizni bajarganingizni sanaydi
\u2022 Jamg'armangiz o'rtacha oylik chiqimingizga necha oyga
  yetishini ko'rsatadi

<b>Alohida karta:</b> jamg'armani kundalik kartada
saqlamang. Bitta hisobda turgan pul \u00abbor\u00bb bo'lib ko'rinadi
va sezilmasdan sarflanadi. Bot sizdan bir marta so'raydi
va ochmagan bo'lsangiz eslatib turadi.

\u2501\u2501\u2501\u2501\u2501\u2501\u2501\u2501\u2501\u2501\u2501\u2501\u2501\u2501\u2501
\U0001F91D <b>7. QARZLAR</b>

/qarz \u2014 ochiq qarzlar ro'yxati, kim kimga qarzdorligi
<code>/yopdim 12</code> \u2014 qarzni yopilgan deb belgilash

Qaytarishni ham oddiy yozing \u2014 bot o'zi tushunadi:
<i>"Akmal 200 mingni qaytardi"</i>, <i>"qarzimni qaytardim 1 mln"</i>,
<i>"kreditga 2,5 mln to'ladim"</i>. Ism aytilsa, shu odamning qarzi
kamayadi. Qarz harakati <b>xarajat ham, daromad ham emas</b> \u2014
kunlik chiqim va kategoriya foizlariga kirmaydi.

<b>\U0001F4C5 Qaytarish muddati</b> (PRO) \u2014 qarz yozuvi ostidagi tugma
yoki matnda: <i>"Akmalga 200 ming berdim, 2 haftada qaytaradi"</i>.
Bir kun oldin va o'sha kuni eslataman.

/reja \u2014 <b>qarzdan chiqish rejasi</b>. Daromadingizni uchga
bo'ladi: 70% yashashga, 20% qarzni uzishga, 10% baribir
jamg'armaga. Shu tartibda necha oyda qarzdan chiqishingizni
hisoblab beradi.

Nega qarz bo'lsa ham jamg'ariladi: hammasini qarzga
bersangiz, kutilmagan xarajat chiqqan kuni yana qarz olasiz
va aylana yopilmaydi.

\u2501\u2501\u2501\u2501\u2501\u2501\u2501\u2501\u2501\u2501\u2501\u2501\u2501\u2501\u2501
\U0001F4B0 <b>8. BYUDJET VA ESLATMA</b>

<b>Byudjet</b> \u2014 kategoriyaga oylik chegara qo'yasiz, oshib
ketsa bot ogohlantiradi:
<code>/byudjet oziq-ovqat 2 mln</code>
<code>/byudjet transport 500 ming</code>
<code>/byudjet transport o'chir</code> \u2014 olib tashlash

/byudjet \u2014 hozirgi chegaralar va qancha sarflanganini
ko'rsatadi. Ogohlantirish <b>80%</b> va <b>100%</b> da
bir martadan keladi.

<b>Kunlik eslatma</b> \u2014 /eslatma bilan soatni tanlaysiz.
Har kuni o'sha soatda bot bugungi xulosani yuboradi va
yozishni eslatadi. Kerak bo'lmasa o'chirib qo'yasiz.

/kurs \u2014 bugungi dollar kursi.

\u2501\u2501\u2501\u2501\u2501\u2501\u2501\u2501\u2501\u2501\u2501\u2501\u2501\u2501\u2501
\U0001F4F1 <b>9. MINI APP (grafikli panel)</b>

Klaviaturadagi <b>«📱 Panel»</b> tugmasini bosing. Xabar
yozish maydoni yonidagi menyu tugmasidan ham ochiladi. Bu
botning ichidagi to'liq ilova:

\u2022 <b>Doira diagramma</b> \u2014 kirim/chiqim nisbati va farqi
\u2022 <b>Davrlar</b> \u2014 kun, hafta, oy, yil; oldinga va
  orqaga yurish mumkin
\u2022 <b>Yorliqlar</b> \u2014 Hammasi, Kirim, Chiqim, Qarz,
  Jamg'arma
\u2022 <b>Valyuta</b> \u2014 hammasi, so'm yoki dollar alohida
\u2022 <b>Kategoriyalar</b> \u2014 foizi va soni bilan; bosilsa
  o'sha kategoriyaning yozuvlari chiqadi
\u2022 <b>Qidiruv</b> \u2014 izoh, kategoriya yoki ism bo'yicha
\u2022 <b>Yozuv qo'shish</b> \u2014 pastdagi \u00ab+\u00bb tugmasi
\u2022 <b>Jamg'arma bo'limi</b> \u2014 qoldiq, har bir maqsad
  progressi va (PRO'da) \u00abqachon erishaman\u00bb bashorati
\u2022 <b>Qarz</b> \u2014 kim kimga qarzdor, qoldiq va qaytarish muddati
\u2022 <b>Chek</b> \u2014 bitta qator; bosilsa mahsulotlari ochiladi

Bepul versiyada panel joriy oy bilan cheklangan.

\u2501\u2501\u2501\u2501\u2501\u2501\u2501\u2501\u2501\u2501\u2501\u2501\u2501\u2501\u2501
\U0001F4AC <b>10. SAVOL BERISH</b>

Shunchaki savol yozing:
<code>bu oy eng ko'p nimaga pul ketdi?</code>
<code>o'tgan haftaga nisbatan qancha ko'p sarfladim?</code>
<code>kuniga o'rtacha qancha ketyapti?</code>
<code>kimga qancha qarzim bor?</code>

Jamlanmalarni dastur aniq hisoblaydi, AI faqat
tushuntiradi \u2014 shuning uchun sonlar to'g'ri bo'ladi.

\u2501\u2501\u2501\u2501\u2501\u2501\u2501\u2501\u2501\u2501\u2501\u2501\u2501\u2501\u2501
\U0001F48E <b>11. BEPUL VA PRO</b>

Birinchi 7 kun \u2014 <b>to'liq PRO</b>. Keyin bot ishlashda
davom etadi, Bepul versiyada:
\u2022 matn bilan yozuv \u2014 cheksiz
\u2022 bugun, hafta va joriy oy hisobotlari
\u2022 oyiga 3 ta chek, kuniga 3 ta AI savol
\u2022 qarzlar ro'yxati

PRO'da: cheksiz chek va savol, barcha oylar tahlili,
yillik hisobot, byudjet, CSV eksport.

/obuna \u2014 tariflar va to'lov. To'lovdan keyin chek
suratini yuborasiz, admin tasdiqlaydi.

/holat \u2014 darajangiz, PRO qachon tugashi va
qolgan limitlar.

/taklif \u2014 do'stingizni taklif qiling. U bot bilan
ishlashni boshlasa, <b>ikkalangizga ham +7 kun PRO</b>
qo'shiladi.

\u2501\u2501\u2501\u2501\u2501\u2501\u2501\u2501\u2501\u2501\u2501\u2501\u2501\u2501\u2501
\U0001F514 <b>12. BOT O'ZI YUBORADIGAN XABARLAR</b>

So'ramasangiz ham keladigan xabarlar \u2014 bilib turing:

\u2022 <b>Kunlik xulosa</b> \u2014 /eslatma da tanlagan soatingizda
\u2022 <b>Haftalik xulosa</b> \u2014 dushanba ertalab, o'tgan hafta
\u2022 <b>Jamg'arma eslatmasi</b> \u2014 oyning oxirgi kuni 18:00 da
\u2022 <b>Byudjet ogohlantirishi</b> \u2014 80% va 100% ga yetganda
\u2022 <b>Qarz muddati</b> \u2014 bir kun oldin va o'sha kuni (PRO)
\u2022 <b>PRO sinov</b> \u2014 tugashiga 2 kun qolganda va tugagan kuni
\u2022 <b>Obuna tugashi</b> \u2014 tugashiga bir necha kun qolganda
\u2022 <b>Ketma-ket kunlar</b> \u2014 7, 30 va 100 kunlik
  to'xtovsiz yozuvda tabrik

<b>Bepul versiyada:</b> kunlik eslatma soat 21:00 da (faqat o'sha
kuni hali yozmagan bo'lsangiz), qisqa haftalik xulosa va oy
oxirida maqsad progressi. 14 kun yozmasangiz — faqat haftalik
xulosa, 30 kundan keyin hech narsa kelmaydi.

Ortiqcha tuyulsa /eslatma dan kunlik xabarni o'chiring.

\u2501\u2501\u2501\u2501\u2501\u2501\u2501\u2501\u2501\u2501\u2501\u2501\u2501\u2501\u2501
\U0001F512 <b>13. MA'LUMOT, MAXFIYLIK VA SOZLAMALAR</b>

/csv \u2014 barcha yozuvlar Excel'da ochiladigan fayl
ko'rinishida (PRO). Har bir chek mahsulotida \u00abchek_id\u00bb va
do'kon nomi bor \u2014 chekni Excel'da qayta yig'ish mumkin.
Hisobni o'chirishdan oldin CSV hamma uchun bepul.

<b>Yozuvlaringizni sizdan boshqa hech kim ko'rmaydi.</b>
Summalar, kategoriyalar va izohlar alohida shifrlangan
bazada saqlanadi va uning kaliti admin panelda umuman
yo'q \u2014 ya'ni bu va'da emas, texnik to'siq.

/til \u2014 til almashtirish (o'zbekcha / ruscha)
/buyruqlar \u2014 barcha buyruqlar bo'limlari bilan
/maxfiylik \u2014 to'liq maxfiylik siyosati
/shartlar \u2014 xizmat shartlari va to'lov qoidalari
/ochirish \u2014 hisobni va butun tarixni butunlay o'chirish
   (tasdiq so'raladi, qaytarib bo'lmaydi)"""


# --------------------------------------------------------------------------- #
# Ruxsat
# --------------------------------------------------------------------------- #

def _support_contact() -> str:
    return config.SUPPORT_CONTACT or "administrator"


def lang_of(user_id: int, context: ContextTypes.DEFAULT_TYPE | None = None) -> str:
    """Foydalanuvchi tili. Bir so'rov ichida keshlanadi — har bir matn uchun
    bazaga borish shart emas."""
    if context is not None:
        cached = context.user_data.get("_lang")
        if cached:
            return cached
    value = i18n.normalize(db.get_lang(user_id))
    if context is not None:
        context.user_data["_lang"] = value
    return value


async def _deny(msg, user, access) -> None:
    """Kirishi yopiq foydalanuvchiga sababini tushuntiradi."""
    if msg is None:
        return
    lang = lang_of(user.id)
    # Sinov yoki obuna tugashi endi kirishni YOPMAYDI — odam Bepul
    # darajaga o'tadi. Rad etish faqat shu ikki holatda.
    if access["status"] == "blocked":
        await msg.reply_text(i18n.t(lang, "blocked"))
    elif access["status"] == "not_allowed":
        log.info("Yopiq rejim: id=%s username=%s", user.id, user.username)
        await msg.reply_text(i18n.t(lang, "closed_beta", id=user.id))


def skip_consent(func):
    """Rozilik olinmagan bo'lsa ham ishlaydigan buyruqlar uchun.

    Maxfiylik, shartlar, til va hisobni o'chirish — rozilikdan oldin ham
    ochiq bo'lishi shart, aks holda odam nimaga rozi bo'layotganini
    o'qiy olmaydi va fikridan qayta olmaydi.
    """
    func._skip_consent = True
    return func


def consent_keyboard(lang: str = "uz") -> InlineKeyboardMarkup:
    return InlineKeyboardMarkup([
        [InlineKeyboardButton(i18n.t(lang, "consent_yes"), callback_data="ok:yes")],
        [InlineKeyboardButton(i18n.t(lang, "consent_privacy"),
                              callback_data="ok:privacy"),
         InlineKeyboardButton(i18n.t(lang, "consent_terms"),
                              callback_data="ok:terms")],
    ])


async def _consent_ok(update: Update, context: ContextTypes.DEFAULT_TYPE) -> bool:
    """Rozilik olinmagan bo'lsa so'raydi va False qaytaradi.

    Shaxsiy ma'lumotni qayta ishlashdan OLDIN chaqiriladi.
    """
    user = update.effective_user
    if db.has_consent(user.id, CONSENT_VERSION):
        return True
    msg = update.effective_message
    if msg is not None:
        lang = lang_of(user.id, context)
        await msg.reply_text(i18n.cyr(lang, i18n.t(lang, "consent")),
                             parse_mode=ParseMode.HTML,
                             reply_markup=consent_keyboard(lang))
    return False


def private_only(func):
    """Kirish nazorati: ega — cheksiz; boshqalar — bepul sinov yoki obuna.

    Kirish huquqidan keyin roziligi ham tekshiriladi.
    """
    @wraps(func)
    async def wrapper(update: Update, context: ContextTypes.DEFAULT_TYPE):
        user = update.effective_user
        if user is None:
            return
        access = db.access_status(user.id, user.first_name or "", user.username)
        context.user_data["access"] = access

        if not access["ok"]:
            await _deny(update.effective_message, user, access)
            return

        if not getattr(func, "_skip_consent", False) \
                and not await _consent_ok(update, context):
            return

        return await func(update, context)

    return wrapper


def owner_only(func):
    """Faqat bot egalari uchun (admin buyruqlari)."""
    @wraps(func)
    async def wrapper(update: Update, context: ContextTypes.DEFAULT_TYPE):
        user = update.effective_user
        if user is None or user.id not in config.OWNER_IDS:
            return
        return await func(update, context)

    return wrapper


# --------------------------------------------------------------------------- #
# Limitlar — Bepul/PRO chegaralari va adolatli foydalanish (tiers.py).
# Egalarga qo'llanmaydi.
# --------------------------------------------------------------------------- #

# Oylik sarf ogohlantirishi oyiga bir marta yuborilsin.
_budget_warned: dict[str, bool] = {}


async def _budget_ok(update: Update, context: ContextTypes.DEFAULT_TYPE) -> bool:
    """Oylik AI sarfi chegaradan oshmaganini tekshiradi.

    Nega kerak: API kaliti oshkor bo'lsa yoki kutilmagan yuk kelsa,
    hisobdan cheksiz pul ketishi mumkin. Bot har bir chaqiruv narxini
    allaqachon yozib boradi — shu bilan o'zini o'zi to'xtata oladi.

    Chegara HAMMAGA, shu jumladan egaga ham qo'llanadi: bu pul masalasi,
    imtiyoz masalasi emas.
    """
    cap = config.monthly_budget_usd()
    if cap <= 0:
        return True

    spent = db.month_cost()
    month = datetime.now(config.TZ).strftime("%Y-%m")

    # 80% da egani bir marta ogohlantiramiz — to'xtab qolishdan oldin
    # xabari bo'lsin.
    if spent >= cap * 0.8 and not _budget_warned.get(month):
        # Faqat joriy oyni saqlaymiz — eskisi kerak emas.
        _budget_warned.clear()
        _budget_warned[month] = True
        for owner in config.OWNER_IDS:
            try:
                await context.bot.send_message(
                    owner,
                    f"⚠️ <b>Oylik AI sarfi chegaraga yaqinlashdi</b>\n\n"
                    f"Sarflandi: <b>${spent:.2f}</b> / ${cap:.2f} "
                    f"({100 * spent / cap:.0f}%)\n\n"
                    f"Chegaraga yetganda bot AI amallarini to'xtatadi. "
                    f"Oshirish: <code>.env</code> dagi "
                    f"<code>MONTHLY_BUDGET_USD</code>",
                    parse_mode=ParseMode.HTML)
            except Exception:
                log.info("Byudjet ogohlantirishi yuborilmadi: %s", owner)

    if spent < cap:
        return True

    log.warning("Oylik AI byudjeti tugadi: $%.2f / $%.2f", spent, cap)
    msg = update.effective_message
    if msg:
        await msg.reply_text(
            "⏸ <b>Bot vaqtincha to'xtatildi</b>\n\n"
            "Oylik xizmat chegarasi tugadi. Administrator xabardor "
            "qilindi — tez orada tiklanadi.\n\n"
            "<i>Yozuvlaringiz saqlanib turibdi.</i>",
            parse_mode=ParseMode.HTML)
    return False


async def check_quota(update: Update, context: ContextTypes.DEFAULT_TYPE,
                      operation: str) -> int | None:
    """Limitni tekshiradi va joy band qiladi.

    Qaytaradi: usage_log qatorining id'si (amal tugagach yozish uchun),
    yoki limit tugagan bo'lsa None."""
    user_id = update.effective_user.id

    # Oylik pul chegarasi kunlik limitlardan oldin tekshiriladi.
    if not await _budget_ok(update, context):
        return None

    if db.is_privileged(user_id):
        return db.usage_begin(user_id, operation)

    access = db.access_status(user_id)
    verdict = tiers.check(user_id, access, operation)
    if verdict is None:
        return db.usage_begin(user_id, operation)

    lang = lang_of(user_id, context)
    if verdict["type"] == "paywall":
        date_text = reports.fmt_date(tiers.next_month_start().isoformat())
        await show_paywall(update, context, verdict["feature"],
                           limit=verdict["limit"], date=date_text)
    else:
        what = {"matn": "what_matn", "chek": "what_chek", "qa": "what_qa"}[verdict["feature"]]
        await update.effective_message.reply_text(
            i18n.t(lang, "fair_limit", limit=verdict["limit"], what=i18n.t(lang, what)))
    return None


async def show_paywall(update: Update, context: ContextTypes.DEFAULT_TYPE,
                       feature: str, **fmt) -> None:
    """PRO imkoniyatga urilganda: nima qulflangan, PRO nima beradi va
    bitta tugma.

    Bir xil paywall kuniga BIR marta to'liq ko'rinishda chiqadi; shu kuni
    takrorlansa — bitta qisqa qator, tugmasiz. Har biri hodisa sifatida
    yoziladi: qaysi funksiya ko'proq PRO ga undashini /statistika ko'rsatadi.
    """
    user_id = update.effective_user.id
    lang = lang_of(user_id, context)
    first_today = not db.event_today(user_id, "paywall_korsatildi", feature)
    db.log_event(user_id, "paywall_korsatildi", feature)

    msg = update.effective_message
    if update.callback_query and not first_today:
        await update.callback_query.answer(
            i18n.t(lang, "paywall_short", feature=i18n.t(lang, f"feature_{feature}")),
            show_alert=True)
        return
    if not first_today:
        await msg.reply_text(
            i18n.t(lang, "paywall_short", feature=i18n.t(lang, f"feature_{feature}")))
        return
    if update.callback_query:
        await update.callback_query.answer()
    await msg.reply_text(
        i18n.t(lang, f"paywall_{feature}", **fmt),
        parse_mode=ParseMode.HTML,
        reply_markup=InlineKeyboardMarkup([[InlineKeyboardButton(
            i18n.t(lang, "pro_btn"), callback_data=f"pro:{feature}")]]))


# --------------------------------------------------------------------------- #
# Klaviaturalar
# --------------------------------------------------------------------------- #

def main_menu(lang: str = "uz") -> ReplyKeyboardMarkup:
    """Har chaqiruvda quriladi — WEBAPP_URL ishga tushirilgandan keyin
    qo'shilsa, botni qayta ishga tushirmasdan ham tugma paydo bo'ladi."""
    # Asosiy oltita tugma; qolganlari «⚙️ Yana» ichida (MORE_MENU).
    rows = [["today", "month"], ["goals", "debts"]]
    keyboard = [[KeyboardButton(i18n.btn(lang, key)) for key in row] for row in rows]
    if config.WEBAPP_URL:
        keyboard.append([
            KeyboardButton(i18n.btn(lang, "panel"),
                           web_app=WebAppInfo(url=config.WEBAPP_URL)),
            KeyboardButton(i18n.btn(lang, "pro")),
        ])
        keyboard.append([KeyboardButton(i18n.btn(lang, "more"))])
    else:
        keyboard.append([KeyboardButton(i18n.btn(lang, "pro")),
                         KeyboardButton(i18n.btn(lang, "more"))])
    return ReplyKeyboardMarkup(
        keyboard,
        resize_keyboard=True,
        input_field_placeholder="Xarajat yozing yoki chek rasmini yuboring…",
    )

# «⚙️ Yana» — kamroq ishlatiladigan bo'limlar, xabar ichidagi tugmalar.
MORE_MENU = ["week", "year", "recent", "longbill", "csv", "budget", "referral", "guide"]


def more_keyboard(lang: str = "uz") -> InlineKeyboardMarkup:
    buttons = [InlineKeyboardButton(i18n.btn(lang, key), callback_data=f"m:{key}")
               for key in MORE_MENU]
    return InlineKeyboardMarkup([buttons[i:i + 2] for i in range(0, len(buttons), 2)])


async def cmd_more(update: Update, context: ContextTypes.DEFAULT_TYPE):
    lang = lang_of(update.effective_user.id, context)
    await update.effective_message.reply_text(
        i18n.t(lang, "more_menu"), parse_mode=ParseMode.HTML,
        reply_markup=more_keyboard(lang))


async def on_more_callback(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """«⚙️ Yana» ichidagi tugma — oddiy menyu tugmasi bilan bir xil handler."""
    query = update.callback_query
    key = (query.data or "m:").split(":", 1)[1]
    handler = MENU_HANDLERS.get(key)
    await query.answer()
    if handler and key in MORE_MENU:
        await handler(update, context)


def collect_menu(lang: str = "uz") -> ReplyKeyboardMarkup:
    return ReplyKeyboardMarkup(
        [[i18n.btn(lang, "ready"), i18n.btn(lang, "cancel")]],
        resize_keyboard=True,
        input_field_placeholder="…",
    )


def entry_keyboard(tx_ids: list[int], kind: str | None = None,
                   items: list[dict] | None = None) -> InlineKeyboardMarkup | None:
    if len(tx_ids) == 1:
        tx = tx_ids[0]
        row = [
            InlineKeyboardButton("✏️ Kategoriya", callback_data=f"c:{tx}"),
            InlineKeyboardButton("🗑 O'chirish", callback_data=f"d:{tx}"),
        ]
        buttons = [row]
        buttons += kind_switch_rows(tx, kind)
        if kind in config.DEBT_OPEN_KINDS:
            buttons.append([InlineKeyboardButton("📅 Qaytarish muddati",
                                                 callback_data=f"due:{tx}")])
        return InlineKeyboardMarkup(buttons)
    if not tx_ids:
        return None
    # Ko'p yozuvli xabar: har bir yozuv uchun alohida «✏️» tugmasi — u
    # o'sha yozuvni o'z tugmalari (kategoriya, tur, o'chirish) bilan
    # alohida xabarda ochadi.
    buttons = []
    for i, tx in enumerate(tx_ids):
        label = f"✏️ {i + 1}-yozuv"
        if items and i < len(items):
            it = items[i]
            note = (it.get("izoh") or config.category_label(it["kategoriya"]))[:18]
            label = f"✏️ {reports.fmt_money(it['summa'], it.get('valyuta', 'som'))} · {note}"
        buttons.append([InlineKeyboardButton(label, callback_data=f"e:{tx}")])
    payload = "D:" + ",".join(map(str, tx_ids))
    # Telegram callback_data uchun chegara — 64 bayt.
    if len(payload.encode()) <= 64:
        buttons.append([InlineKeyboardButton("🗑 Hammasini o'chirish",
                                             callback_data=payload)])
    return InlineKeyboardMarkup(buttons)


def kind_switch_rows(tx: int, kind: str | None) -> list[list[InlineKeyboardButton]]:
    """Turini tuzatish tugmalari: config.KIND_SWITCHES bo'yicha.

    Masalan chiqim -> «Kirim» yoki «Qarzimni qaytardim». Qarz berdim/oldim
    va jamg'arma bu yerda almashtirilmaydi (shaxs maydoni va qoldiqqa
    bog'liq). Callback'da tur nomi emas, `config.KINDS` dagi tartib
    raqami — ro'yxat faqat oxiridan to'ldiriladi, raqamlar o'zgarmaydi.
    """
    return [[InlineKeyboardButton(
        f"🔄 {config.KIND_ICONS[other]} {config.KIND_LABELS[other]}",
        callback_data=f"T:{tx}:{config.KINDS.index(other)}")]
        for other in config.KIND_SWITCHES.get(kind or "", [])]


# CATEGORY_REGISTRY dagi birinchi shuncha kategoriya eski «s:» tugmalari
# yaratilgan paytda mavjud edi.
LEGACY_CATEGORY_COUNT = 23


def receipt_keyboard(receipt_id: str) -> InlineKeyboardMarkup:
    return InlineKeyboardMarkup(
        [
            [InlineKeyboardButton("📋 To'liq ro'yxat", callback_data=f"L:{receipt_id}")],
            [InlineKeyboardButton("➕ Chek davomi bor", callback_data=f"A:{receipt_id}")],
            [InlineKeyboardButton("🗑 Chekni o'chirish", callback_data=f"R:{receipt_id}")],
        ]
    )


def category_keyboard(tx_id: int, kind: str) -> InlineKeyboardMarkup:
    cats = config.categories_for(kind)
    buttons, row = [], []
    for name in cats:
        icon = config.CATEGORY_ICONS.get(name, "•")
        # Raqam config.CATEGORY_REGISTRY dan — u o'zgarmaydi.
        idx = config.CATEGORY_REGISTRY.index(name)
        row.append(InlineKeyboardButton(f"{icon} {config.category_label(name)}",
                                        callback_data=f"k:{tx_id}:{idx}"))
        if len(row) == 2:
            buttons.append(row)
            row = []
    if row:
        buttons.append(row)
    buttons.append([InlineKeyboardButton("⬅️ Bekor", callback_data=f"x:{tx_id}")])
    return InlineKeyboardMarkup(buttons)


# --------------------------------------------------------------------------- #
# Buyruqlar
# --------------------------------------------------------------------------- #


FIRST_STEPS = [
    ("obedga 45 ming", "Birinchi yozuv"),
    ("taksi 20k, kofe 25 ming", "Bitta xabarda ikkita"),
    ("oylik tushdi 8 mln", "Kirim yozish"),
]


async def cmd_start(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """Birinchi tanishuv — qisqa. To'liq qo'llanma /qollanma da."""
    user = update.effective_user
    if user is None:
        return

    access = db.access_status(user.id, user.first_name or "", user.username)
    context.user_data["access"] = access

    if not access["ok"]:
        await _deny(update.effective_message, user, access)
        return

    # Rozilik olinmaguncha hech narsa qayta ishlanmaydi — taklif bonusi ham.
    payload = (context.args or [""])[0] if context.args else ""
    if not db.has_consent(user.id, CONSENT_VERSION):
        if payload:
            context.user_data["pending_ref"] = payload
        await _consent_ok(update, context)
        return

    if payload == "pro":                   # Mini App'dagi «PRO ga o'tish»
        await send_plans(update, context)
        return
    if payload:                            # taklif havolasi: /start ref12345
        await _apply_referral(update, context, payload)
        access = db.access_status(user.id)

    lang = lang_of(user.id, context)
    is_new = db.tx_count(user.id) == 0
    name = f", {reports.esc(user.first_name)}" if user.first_name else ""

    if is_new:
        # 3–4 qator: salom, uchta misol, (PRO sinov) va bitta chaqiruv.
        # Teskari sinov: odam PRO ichida boshlaydi va buni aniq bilsin.
        db.log_event(user.id, "start")
        trial = (i18n.t(lang, "trial_active", days=config.trial_days()) + "\n"
                 if access["status"] == "trial" else "")
        await update.effective_message.reply_text(
            i18n.t(lang, "welcome", name=name, trial=trial),
            parse_mode=ParseMode.HTML,
            reply_markup=main_menu(lang),
        )
        return

    status = {
        "trial": i18n.t(lang, "start_trial", days=access["days_left"]),
        "subscribed": i18n.t(lang, "start_pro", days=access["days_left"]),
        "free": i18n.t(lang, "start_free"),
    }.get(access["status"], "")
    await update.effective_message.reply_text(
        i18n.t(lang, "welcome_back", name=name,
               status=(status + "\n") if status else ""),
        parse_mode=ParseMode.HTML, reply_markup=main_menu(lang))


async def on_consent_callback(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """«Roziman» / «Maxfiylik» / «Shartlar» tugmalari."""
    query = update.callback_query
    user = update.effective_user
    lang = lang_of(user.id, context)
    action = (query.data or "ok:").split(":", 1)[1]

    if action == "privacy":
        await query.answer()
        await query.message.reply_text(
            i18n.t(lang, "privacy", contact=reports.esc(_support_contact())),
            parse_mode=ParseMode.HTML, disable_web_page_preview=True)
        return

    if action == "terms":
        await query.answer()
        await query.message.reply_text(
            _terms_text(lang), parse_mode=ParseMode.HTML,
            disable_web_page_preview=True)
        return

    if action != "yes":
        await query.answer()
        return

    db.set_consent(user.id, CONSENT_VERSION)
    log.info("Rozilik olindi: id=%s versiya=%s", user.id, CONSENT_VERSION)
    await query.answer(i18n.t(lang, "consent_done"))
    try:
        await query.edit_message_reply_markup(reply_markup=None)
    except Exception:
        pass

    # Rozilikdan oldin kelgan taklif havolasi endi qo'llanadi.
    payload = context.user_data.pop("pending_ref", "")
    if payload:
        await _apply_referral(update, context, payload)

    context.args = []
    await cmd_start(update, context)


async def on_try_callback(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """Onboarding tugmasi — misolni haqiqiy yozuvga aylantiradi."""
    query = update.callback_query
    try:
        index = int((query.data or "try:0").split(":")[1])
        example = FIRST_STEPS[index][0]
    except (ValueError, IndexError):
        await query.answer("Misol topilmadi")
        return
    await query.answer(example)
    await query.edit_message_text(f"✍️ <i>{reports.esc(example)}</i>",
                                  parse_mode=ParseMode.HTML)
    # Xabarni foydalanuvchi o'zi yozgandek qayta ishlaymiz.
    await _process_text(update, context, example)


# Qo'llanma bo'limlari: GUIDE_TEXT ajratuvchi chiziq bo'yicha bo'linadi.
# Bitta uzun xabar o'rniga — bo'limlar ro'yxati va har biri tugma bilan.
GUIDE_SEPARATOR = "━" * 15
GUIDE_BUTTONS = [
    "Yozish", "Chek rasmi", "Aniqlik", "Xatoni tuzatish", "Hisobotlar",
    "Jamg'arma", "Qarzlar", "Byudjet", "Mini App", "Savol berish",
    "Bepul va PRO", "Bot xabarlari", "Maxfiylik",
]


def _guide_sections(text: str, buttons: list[str]) -> list[tuple[str, str]]:
    """[(tugma matni, bo'lim matni)] — kirish qismi (birinchi bo'lak) tashlanadi."""
    parts = [p.strip() for p in text.split(GUIDE_SEPARATOR)[1:]]
    if len(parts) != len(buttons):
        raise RuntimeError("Qo'llanma bo'limlari va tugmalar soni mos emas")
    return [(f"{body.split()[0]} {label}", body)
            for label, body in zip(buttons, parts)]


GUIDE_SECTIONS = _guide_sections(GUIDE_TEXT, GUIDE_BUTTONS)
# Ruscha — alohida matn (guide_ru.py); kirill o'zbekcha esa lotinchadan
# avtomatik o'giriladi (i18n.cyr).
GUIDE_SECTIONS_RU = _guide_sections(guide_ru.GUIDE_TEXT_RU, guide_ru.GUIDE_BUTTONS_RU)


def _sections_for(lang: str) -> list[tuple[str, str]]:
    return GUIDE_SECTIONS_RU if lang == "ru" else GUIDE_SECTIONS


def guide_menu_keyboard(lang: str = "uz") -> InlineKeyboardMarkup:
    rows, row = [], []
    for i, (label, _) in enumerate(_sections_for(lang)):
        if lang == "uzc":
            label = i18n.cyr(lang, label)
        row.append(InlineKeyboardButton(label, callback_data=f"g:{i}"))
        if len(row) == 2:
            rows.append(row)
            row = []
    if row:
        rows.append(row)
    return InlineKeyboardMarkup(rows)


@private_only
async def cmd_guide(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """/yordam — bo'limlar ro'yxati; bo'lim tugma bilan ochiladi."""
    lang = lang_of(update.effective_user.id, context)
    await update.effective_message.reply_text(
        i18n.t(lang, "guide_menu"), parse_mode=ParseMode.HTML,
        reply_markup=guide_menu_keyboard(lang))


async def on_guide_callback(update: Update, context: ContextTypes.DEFAULT_TYPE):
    query = update.callback_query
    lang = lang_of(update.effective_user.id, context)
    key = (query.data or "g:menu").split(":", 1)[1]
    await query.answer()
    sections = _sections_for(lang)
    if key == "menu" or not key.isdigit() or int(key) >= len(sections):
        await query.edit_message_text(i18n.t(lang, "guide_menu"),
                                      parse_mode=ParseMode.HTML,
                                      reply_markup=guide_menu_keyboard(lang))
        return
    _, body = sections[int(key)]
    await query.edit_message_text(
        i18n.cyr(lang, body), parse_mode=ParseMode.HTML,
        reply_markup=InlineKeyboardMarkup([[InlineKeyboardButton(
            i18n.t(lang, "guide_back"), callback_data="g:menu")]]))


async def cmd_commands(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """/buyruqlar — barcha buyruqlar bo'limlarga ajratilgan holda.

    Telegram menyusi guruhlashni qo'llab-quvvatlamaydi, shuning uchun
    to'liq va tartibli ro'yxat shu yerda beriladi: odam /maqsad qaysi
    bo'limga tegishligini bir qarashda ko'radi.
    """
    lines = ["\U0001F4CB <b>BUYRUQLAR</b>"]
    for icon, title, items in COMMAND_SECTIONS:
        lines.append("")
        lines.append(f"{icon} <b>{title}</b>")
        for name, desc in items:
            lines.append(f"/{name} \u2014 {desc}")
    lines.append("")
    lines.append("<i>Yozuv qo\'shish uchun buyruq kerak emas \u2014 "
                 "shunchaki yozing: <code>obedga 45 ming</code></i>")
    await update.effective_message.reply_text(
        "\n".join(lines), parse_mode=ParseMode.HTML)


async def cmd_id(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """Faqat bot egasi uchun. OWNER_IDS hali bo'sh bo'lsa — birinchi
    sozlash uchun ochiq qoladi, aks holda egani aniqlab bo'lmaydi."""
    user = update.effective_user
    if user is None:
        return
    if config.OWNER_IDS and user.id not in config.OWNER_IDS:
        return  # oddiy foydalanuvchiga buyruq umuman mavjud emasdek
    await update.message.reply_text(
        f"Telegram ID: {user.id}\n"
        f"Uni .env faylidagi OWNER_IDS ga yozing."
    )


PRO_PERIODS = ("otgan_oy", "yil")


def _period_command(period: str):
    @private_only
    async def handler(update: Update, context: ContextTypes.DEFAULT_TYPE):
        # O'tgan oy va yil — PRO. Bugun, kecha, hafta, joriy oy — hamma uchun.
        if period in PRO_PERIODS and not tiers.allows(
                context.user_data.get("access"), "history"):
            await show_paywall(update, context, "history")
            return
        text = reports.summary_text(update.effective_user.id, period)
        # Oy va yil hisobotini rasm qilib ulashsa bo'ladi — do'stlarga
        # ko'rsatiladigan natija botni o'zi reklama qiladi.
        markup = None
        if period in ("oy", "otgan_oy", "yil") and sharecard.available():
            markup = InlineKeyboardMarkup([[
                InlineKeyboardButton(
                    i18n.t(lang_of(update.effective_user.id, context), "share_btn"),
                    callback_data=f"share:{period}")
            ]])
        await update.effective_message.reply_text(
            text, parse_mode=ParseMode.HTML, reply_markup=markup)

    return handler


async def on_share_callback(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """Davr hisobotini PNG qilib yuboradi."""
    query = update.callback_query
    user_id = update.effective_user.id
    period = (query.data or "share:oy").split(":", 1)[1]
    if period in PRO_PERIODS and not tiers.allows(db.access_status(user_id), "history"):
        await show_paywall(update, context, "history")
        return

    await query.answer("🖼")
    start, end, label = reports.period_range(period)
    data = db.totals_unified(user_id, start, end)
    totals = data["totals"]
    currency = "som"
    cats = db.by_category_unified(user_id, start, end, config.KIND_CHIQIM)
    entries = len(db.list_range(user_id, start, end))

    me = await context.bot.get_me()
    png = await asyncio.to_thread(
        sharecard.build,
        title=label.capitalize(),
        kirim=totals.get(config.KIND_KIRIM, 0),
        chiqim=totals.get(config.KIND_CHIQIM, 0),
        categories=cats,
        currency=currency,
        entries=entries,
        bot_username=me.username or "",
    )
    if not png:
        await query.answer("Rasm tayyorlab bo'lmadi", show_alert=True)
        return

    data = io.BytesIO(png)
    data.name = "hisobot.png"
    await context.bot.send_photo(
        query.message.chat_id, data,
        caption=i18n.t(lang_of(user_id, context), "share_caption"))


@private_only
async def cmd_recent(update: Update, context: ContextTypes.DEFAULT_TYPE):
    await update.effective_message.reply_text(
        reports.recent_text(update.effective_user.id, 12), parse_mode=ParseMode.HTML
    )


@private_only
async def cmd_debts(update: Update, context: ContextTypes.DEFAULT_TYPE):
    await update.effective_message.reply_text(
        reports.debts_text(update.effective_user.id), parse_mode=ParseMode.HTML
    )


@private_only
async def cmd_delete(update: Update, context: ContextTypes.DEFAULT_TYPE):
    if not context.args or not context.args[0].lstrip("#").isdigit():
        await update.message.reply_text("Foydalanish: /ochir 12")
        return
    tx_id = int(context.args[0].lstrip("#"))
    removed = delete_entry(update.effective_user.id, tx_id)
    if removed is None:
        await update.message.reply_text(f"#{tx_id} topilmadi.")
    elif removed > 1:
        await update.message.reply_text(
            f"🗑 Chek o'chirildi ({removed} ta mahsulot).")
    else:
        await update.message.reply_text(f"🗑 #{tx_id} o'chirildi.")


def delete_entry(user_id: int, tx_id: int) -> int | None:
    """Botdagi o'chirish: yozuv chekka tegishli bo'lsa BUTUN chek o'chadi.

    «Oxirgi» ro'yxatida chek bitta qator bo'lib ko'rinadi, demak uning
    raqami chekning o'zini anglatadi. Qaytaradi: o'chgan qatorlar soni
    yoki yozuv topilmasa None.
    """
    row = db.get_transaction(user_id, tx_id)
    if not row:
        return None
    if row["receipt_id"]:
        _last_receipt.pop(user_id, None)
        return db.delete_receipt(user_id, row["receipt_id"])
    return 1 if db.delete_transaction(user_id, tx_id) else None


@private_only
async def cmd_settle(update: Update, context: ContextTypes.DEFAULT_TYPE):
    if not context.args or not context.args[0].lstrip("#").isdigit():
        await update.message.reply_text("Foydalanish: /yopdim 12")
        return
    tx_id = int(context.args[0].lstrip("#"))
    ok = db.settle_debt(update.effective_user.id, tx_id)
    await update.message.reply_text(
        f"✅ #{tx_id} qarzi yopildi." if ok else f"#{tx_id} ochiq qarzlar orasida topilmadi."
    )


@private_only
@skip_consent            # o'z ma'lumotini olish — rozilikka bog'liq bo'lmagan huquq
async def cmd_csv(update: Update, context: ContextTypes.DEFAULT_TYPE):
    # CSV — PRO. /ochirish oldidagi «avval CSV» tugmasi esa _send_csv ni
    # to'g'ridan-to'g'ri chaqiradi va hamma uchun ochiq qoladi.
    if not tiers.allows(context.user_data.get("access"), "csv"):
        await show_paywall(update, context, "csv")
        return
    await _send_csv(update, context, update.effective_user.id)


async def _send_csv(update: Update, context: ContextTypes.DEFAULT_TYPE,
                    user_id: int) -> None:
    """CSV faylni yuboradi. /csv va hisobni o'chirishdan oldin ishlatiladi."""
    content, count = reports.csv_bytes(user_id)
    if not count:
        await update.effective_message.reply_text("Eksport qilish uchun yozuv yo'q.")
        return

    data = io.BytesIO(content)
    data.name = "hisobot.csv"
    await update.effective_message.reply_document(
        document=data, filename="hisobot.csv", caption=f"{count} ta yozuv."
    )


# --------------------------------------------------------------------------- #
# Chek: rasm yuklash va tahlil
# --------------------------------------------------------------------------- #

class TTLStore:
    """Muddati bilan o'zini tozalaydigan lug'at.

    Chek rasmlari base64 ko'rinishida xotirada turadi (bittasi bir necha MB).
    Oddiy dict bilan 1000 foydalanuvchida bu gigabaytlarga o'sib, serverni
    xotirasiz qoldirardi. Bu yerda har bir yozuv muddati o'tgach o'chiriladi
    va umumiy soni ham cheklangan."""

    def __init__(self, ttl_seconds: int, max_items: int):
        self._data: dict = {}
        self._ttl = ttl_seconds
        self._max = max_items

    def _purge(self) -> None:
        now = time.monotonic()
        for key in [k for k, (exp, _) in self._data.items() if exp < now]:
            self._data.pop(key, None)
        # Chegaradan oshsa — eng eskisidan boshlab chiqaramiz.
        while len(self._data) > self._max:
            oldest = min(self._data, key=lambda k: self._data[k][0])
            self._data.pop(oldest, None)

    def get(self, key, default=None):
        self._purge()
        item = self._data.get(key)
        if item is None:
            return default
        # Foydalanilgan yozuvning muddati yangilanadi.
        self._data[key] = (time.monotonic() + self._ttl, item[1])
        return item[1]

    def set(self, key, value) -> None:
        self._data[key] = (time.monotonic() + self._ttl, value)
        self._purge()

    def setdefault(self, key, default):
        existing = self.get(key)
        if existing is not None:
            return existing
        self.set(key, default)
        return default

    def pop(self, key, default=None):
        item = self._data.pop(key, None)
        return default if item is None else item[1]

    def __contains__(self, key) -> bool:
        return self.get(key) is not None

    def __len__(self) -> int:
        self._purge()
        return len(self._data)


# Albom bo'lib kelayotgan rasmlar: media_group_id -> {"images", "caption", "task"}
_albums = TTLStore(ttl_seconds=300, max_items=200)
# «Uzun chek» rejimi: user_id -> {"images": [...], "caption": str}
_collect = TTLStore(ttl_seconds=1800, max_items=200)
# Oxirgi chek — «davomi bor» tugmasi uchun: user_id -> {"receipt_id", "images", "caption"}
# Qisqa muddat: bu faqat "davomi bor" tugmasi uchun kerak, uzoq saqlash shart emas.
_last_receipt = TTLStore(ttl_seconds=900, max_items=100)
# To'lov cheki kutilayotgan foydalanuvchilar: user_id -> so'rov ID.
# 2 soat — odam kartaga o'tkazib, chekni topib yuborishga yetadi.
_awaiting_proof = TTLStore(ttl_seconds=7200, max_items=500)
# Hisobni o'chirishni tasdiqlash kutilmoqda: user_id -> True (5 daqiqa)
_awaiting_erase = TTLStore(ttl_seconds=300, max_items=100)
# Oxirgi bosqich: foydalanuvchi o'chirish so'zini yozishi kutilmoqda.
_erase_typed = TTLStore(ttl_seconds=300, max_items=100)
# «10 % ni jamg'armaga o'tkazamizmi?» taklifi: user_id -> summa.
# Tugma bosilganda qaysi summa nazarda tutilgani shu yerdan olinadi.
# Bot qayta ishga tushsa taklif yo'qoladi va bu joiz: eski xabardagi
# tugma baribir dolzarb emas.
_savings_offer = TTLStore(ttl_seconds=6 * 3600, max_items=500)


class ImageError(Exception):
    """Faylni yuklab bo'lmadi — sabab foydalanuvchiga ko'rsatiladi."""


def _guess_pdf(document) -> bool:
    """Ba'zi mijozlar PDF'ni noto'g'ri MIME turi bilan yuboradi."""
    name = (document.file_name or "").lower()
    return (document.mime_type or "").lower() == PDF_TYPE or name.endswith(".pdf")


async def _download_receipt_file(context, message) -> tuple[str, str]:
    """Xabardan chek faylini (base64, media_type) ko'rinishida oladi.

    Rasm ham, PDF ham qabul qilinadi.
    """
    if message.photo:
        # photo[-1] — eng katta o'lchamdagi nusxa.
        tg_file = await context.bot.get_file(message.photo[-1].file_id)
        media_type = "image/jpeg"
        limit = config.MAX_IMAGE_BYTES
    elif message.document:
        doc = message.document
        if _guess_pdf(doc):
            media_type, limit = PDF_TYPE, config.MAX_PDF_BYTES
        else:
            media_type = (doc.mime_type or "").lower()
            limit = config.MAX_IMAGE_BYTES
            if media_type not in SUPPORTED_IMAGE_TYPES:
                raise ImageError(
                    "Bu fayl turi qo'llab-quvvatlanmaydi.\n"
                    "Chekni rasm (JPG/PNG) yoki PDF ko'rinishida yuboring."
                )
        if (doc.file_size or 0) > limit:
            raise ImageError(
                f"Fayl juda katta ({(doc.file_size or 0) // 1_000_000} MB, "
                f"chegara {limit // 1_000_000} MB)."
            )
        tg_file = await context.bot.get_file(doc.file_id)
    else:
        raise ImageError("Chek fayli topilmadi.")

    raw = bytes(await tg_file.download_as_bytearray())
    if len(raw) > limit:
        raise ImageError(
            f"Fayl juda katta ({len(raw) // 1_000_000} MB, "
            f"chegara {limit // 1_000_000} MB)."
        )
    return base64.standard_b64encode(raw).decode(), media_type


async def _process_receipt(update: Update, context, images: list, caption: str):
    """Chek rasm(lar)ini o'qib, mahsulotlarni bazaga yozadi va tahlil qaytaradi."""
    message = update.effective_message
    user_id = update.effective_user.id

    if len(images) > config.MAX_RECEIPT_PARTS:
        await message.reply_text(
            f"Bitta chek uchun ko'pi bilan {config.MAX_RECEIPT_PARTS} ta rasm "
            f"yuborish mumkin (siz {len(images)} ta yubordingiz)."
        )
        return

    usage_id = await check_quota(update, context, "chek")
    if usage_id is None:
        return

    qism = f" ({len(images)} ta qism)" if len(images) > 1 else ""
    status = await message.reply_text(f"🔍 Chek o'qilmoqda{qism}…")
    await context.bot.send_chat_action(message.chat_id, ChatAction.TYPING)

    try:
        data = await ai.parse_receipt(images, today=reports.today(), caption=caption)
    except Exception:
        log.exception("Chekni o'qishda xatolik")
        db.usage_cancel(usage_id)
        await status.edit_text(
            "⚠️ Chekni o'qishda xatolik yuz berdi. Birozdan keyin urinib ko'ring."
        )
        return

    db.usage_finish(usage_id, data.get("_usage"))

    if not data["oqildi"]:
        hint = data["izoh_matni"] or (
            "Chekni o'qib bo'lmadi. Yorug'roq, to'g'ridan-to'g'ri tushirilgan "
            "surat yuboring."
        )
        await status.edit_text(f"🤔 {reports.esc(hint)}", parse_mode=ParseMode.HTML)
        return

    db.log_event(user_id, "chek_yuborildi")
    rules = learning.rules_for(user_id)
    for item in data["mahsulotlar"]:
        item["kategoriya"] = learning.apply(rules, config.KIND_CHIQIM,
                                            item["nomi"], item["kategoriya"])

    receipt_id = uuid.uuid4().hex[:10]
    shop = data["dokon"]
    currency = data.get("valyuta") or "som"
    db.add_receipt(
        user_id, receipt_id, shop=shop, occurred_on=data["sana"],
        currency=currency, printed_total=data.get("chekdagi_jami"),
        discount=data.get("chegirma"),
        items=[
            {
                "kind": config.KIND_CHIQIM,
                "amount": item["summa"],
                "category": item["kategoriya"],
                "note": item["nomi"],
                "raw_text": f"chek: {shop}" if shop else "chek",
            }
            for item in data["mahsulotlar"]
        ])

    start, end, _ = reports.period_range("bugun")
    day_total = db.totals_unified(user_id, start, end)["totals"][config.KIND_CHIQIM]

    _last_receipt.set(user_id, {
        "receipt_id": receipt_id,
        "images": images,
        "caption": caption,
    })

    await status.edit_text(
        reports.receipt_text(data, day_total),
        parse_mode=ParseMode.HTML,
        reply_markup=receipt_keyboard(receipt_id),
    )

    await _celebrate(update, context, message, len(data["mahsulotlar"]))


async def _flush_album(key: str, update: Update, context):
    """Albomdagi barcha rasmlar kelib bo'lgach, ularni birgalikda tahlil qiladi."""
    try:
        await asyncio.sleep(ALBUM_WAIT_SECONDS)
    except asyncio.CancelledError:
        return
    bucket = _albums.pop(key, None)
    if not bucket or not bucket["images"]:
        return
    await _process_receipt(update, context, bucket["images"], bucket["caption"])


async def on_photo(update: Update, context: ContextTypes.DEFAULT_TYPE):
    message = update.effective_message
    user = update.effective_user
    if user is None or message is None:
        return
    user_id = user.id
    caption = message.caption or ""

    # To'lov cheki kirish chegarasidan OLDIN tekshiriladi: muddati tugagan
    # foydalanuvchi ham to'lovni tasdiqlay olishi kerak.
    if await handle_payment_proof(update, context):
        return

    # Limit _process_receipt ichida hisoblanadi — bu yerda faqat kirish.
    access = db.access_status(user_id, user.first_name or "", user.username)
    context.user_data["access"] = access
    if not access["ok"]:
        await _deny(message, user, access)
        return
    if not await _consent_ok(update, context):
        return

    try:
        image = await _download_receipt_file(context, message)
    except ImageError as exc:
        await message.reply_text(f"⚠️ {exc}")
        return
    except Exception:
        log.exception("Chek faylini yuklab olishda xatolik")
        await message.reply_text("⚠️ Faylni yuklab olishda xatolik yuz berdi.")
        return

    # 1) «Uzun chek» rejimi — qismlarni yig'amiz.
    if user_id in _collect:
        bucket = _collect.get(user_id)
        bucket["images"].append(image)
        if caption and not bucket["caption"]:
            bucket["caption"] = caption
        await message.reply_text(
            f"✅ {len(bucket['images'])}-qism qabul qilindi.\n"
            "Yana yuboring yoki «✅ Tayyor» bosing.",
            reply_markup=collect_menu(lang_of(update.effective_user.id, context)),
        )
        return

    # 2) Albom — bir vaqtda yuborilgan bir nechta rasm bitta chek deb qaraladi.
    if message.media_group_id:
        key = str(message.media_group_id)
        bucket = _albums.setdefault(key, {"images": [], "caption": "", "task": None})
        bucket["images"].append(image)
        if caption and not bucket["caption"]:
            bucket["caption"] = caption
        if bucket["task"]:
            bucket["task"].cancel()
        bucket["task"] = asyncio.create_task(_flush_album(key, update, context))
        return

    # 3) Bitta rasm.
    await _process_receipt(update, context, [image], caption)


@private_only
async def cmd_collect_start(update: Update, context: ContextTypes.DEFAULT_TYPE):
    _collect.set(update.effective_user.id, {"images": [], "caption": ""})
    await update.effective_message.reply_text(
        "🧾 <b>Uzun chek rejimi</b>\n\n"
        "Chekni qismlarga bo'lib suratga oling va ketma-ket yuboring "
        "(yuqoridan pastga). Qismlar bir-birini biroz takrorlasa ham "
        "bo'ladi — takroriy qatorlar bir marta hisoblanadi.\n\n"
        "Hammasi tayyor bo'lgach «✅ Tayyor» bosing.",
        parse_mode=ParseMode.HTML,
        reply_markup=collect_menu(lang_of(update.effective_user.id, context)),
    )


@private_only
async def cmd_collect_done(update: Update, context: ContextTypes.DEFAULT_TYPE):
    bucket = _collect.pop(update.effective_user.id, None)
    if not bucket or not bucket["images"]:
        await update.effective_message.reply_text(
            "Hech qanday rasm yuborilmadi.", reply_markup=main_menu(lang_of(update.effective_user.id, context))
        )
        return
    await update.effective_message.reply_text(
        f"📥 {len(bucket['images'])} ta qism qabul qilindi.", reply_markup=main_menu(lang_of(update.effective_user.id, context))
    )
    await _process_receipt(update, context, bucket["images"], bucket["caption"])


@private_only
async def cmd_collect_cancel(update: Update, context: ContextTypes.DEFAULT_TYPE):
    _collect.pop(update.effective_user.id, None)
    await update.effective_message.reply_text("Bekor qilindi.", reply_markup=main_menu(lang_of(update.effective_user.id, context)))


# --------------------------------------------------------------------------- #
# Asosiy matn handleri
# --------------------------------------------------------------------------- #

# Menyu tugmalari matn sifatida keladi — shu yerda tegishli handlerga
# yo'naltiriladi. Lug'at fayl OXIRIDA to'ldiriladi (build_menu_actions),
# chunki bu yerda hali hamma handler e'lon qilinmagan.
MENU_ACTIONS: dict = {}
# Tugma kaliti -> handler («⚙️ Yana» ichidagi tugmalar ham shundan oladi).
MENU_HANDLERS: dict = {}


@private_only
async def on_text(update: Update, context: ContextTypes.DEFAULT_TYPE):
    message = update.message
    text = (message.text or "").strip()
    if not text:
        return

    action = MENU_ACTIONS.get(text)
    if action:
        await action(update, context)
        return

    await _process_text(update, context, text, message)


async def _process_text(update: Update, context: ContextTypes.DEFAULT_TYPE,
                        text: str, message=None) -> None:
    """Matnli yozuvni tahlil qilib saqlaydi.

    `message` — javob yoziladigan xabar. Onboarding tugmasidan
    chaqirilganda bu callback xabari bo'ladi.
    """
    message = message or update.effective_message
    user_id = update.effective_user.id

    # Hisobni o'chirishning oxirgi bosqichi. Bu tekshiruv HAMMASIDAN
    # oldin turadi: kutilayotgan matn yozuv sifatida tahlil qilinib
    # ketmasin.
    if _erase_typed.get(user_id):
        _erase_typed.pop(user_id, None)
        lang = lang_of(user_id, context)
        if text.strip().casefold() == i18n.t(lang, "erase_word").casefold():
            stats = db.erase_user(user_id)
            await message.reply_text(
                i18n.t(lang, "erase_done", n=stats["transactions"]),
                parse_mode=ParseMode.HTML)
            log.info("Foydalanuvchi o'z hisobini o'chirdi: %s", user_id)
        else:
            await message.reply_text(i18n.t(lang, "erase_wrong_word"))
        return

    # «➕ Yangi maqsad» bosilgan bo'lsa — bu xabar maqsadning o'zi.
    if context.user_data.pop("await_goal", False):
        await create_goal_from_text(update, context, text)
        return

    # «Uzun chek» rejimida yozilgan matn — chek uchun izoh.
    if user_id in _collect:
        _collect.get(user_id)["caption"] = text
        await message.reply_text(
            "📝 Izoh saqlandi. Chek qismlarini yuborishda davom eting.",
            reply_markup=collect_menu(lang_of(update.effective_user.id, context)),
        )
        return

    usage_id = await check_quota(update, context, "matn")
    if usage_id is None:
        return

    await context.bot.send_chat_action(message.chat_id, ChatAction.TYPING)

    try:
        parsed = await ai.parse_message(text, today=reports.today())
    except Exception:
        log.exception("AI tahlilida xatolik")
        db.usage_cancel(usage_id)
        await message.reply_text("⚠️ AI bilan bog'lanishda xatolik. Birozdan keyin urinib ko'ring.")
        return

    db.usage_finish(usage_id, parsed.get("_usage"))
    niyat = parsed["niyat"]

    if niyat == "savol":
        # Savol alohida (qimmatroq) amal — o'z limiti va o'z hisobi bor.
        qa_id = await check_quota(update, context, "savol")
        if qa_id is None:
            return
        try:
            rows = db.rows_for_ai(user_id, config.QA_MAX_ROWS)
            answer, qa_usage = await ai.answer_question(text, rows, today=reports.today())
        except Exception:
            log.exception("AI javobida xatolik")
            db.usage_cancel(qa_id)
            await message.reply_text("⚠️ Javob tayyorlashda xatolik yuz berdi.")
            return
        if qa_usage:
            db.usage_finish(qa_id, qa_usage)
        else:
            db.usage_cancel(qa_id)  # yozuv yo'q edi, API chaqirilmadi
        await message.reply_text(answer)
        return

    if niyat != "yozuv" or not parsed["yozuvlar"]:
        hint = parsed.get("izoh_matni") or (
            "Tushunmadim. Summani aniq yozing, masalan: <code>obedga 45 ming</code>"
        )
        await message.reply_text(f"🤔 {reports.esc(hint)}", parse_mode=ParseMode.HTML)
        return

    # Foydalanuvchining o'z tuzatishlaridan o'rganilgan qoidalar AI
    # javobidan ustun turadi.
    rules = learning.rules_for(user_id)
    for item in parsed["yozuvlar"]:
        item["kategoriya"] = learning.apply(rules, item["turi"], item["izoh"],
                                            item["kategoriya"])

    saved_ids: list[int] = []
    for item in parsed["yozuvlar"]:
        # Jamg'arma — aytilgan maqsadga («uy uchun»), aytilmasa asosiy
        # maqsadga. Qarz — aytilgan qaytarish muddati bilan.
        goal_id = (goals.match(user_id, item.get("maqsad"))
                   if item["turi"] == config.KIND_JAMGARMA else None)
        tx_id = db.add_transaction(
            user_id=user_id,
            kind=item["turi"],
            amount=item["summa"],
            category=item["kategoriya"],
            note=item["izoh"],
            person=item["shaxs"],
            occurred_on=item["sana"],
            raw_text=text,
            currency=item["valyuta"],
            goal_id=goal_id,
            due_on=item.get("muddat"),
        )
        saved_ids.append(tx_id)

    body = reports.saved_text(parsed["yozuvlar"])

    # Bugungi umumiy chiqim — qisqa kontekst uchun, har bir valyuta alohida
    start, end, _ = reports.period_range("bugun")
    day_total = db.totals_unified(user_id, start, end)["totals"][config.KIND_CHIQIM]
    if day_total:
        body += f"\n\n<i>Bugungi chiqim: {reports.fmt_money(day_total)}</i>"

    single_kind = parsed["yozuvlar"][0]["turi"] if len(saved_ids) == 1 else None
    await message.reply_text(
        body, parse_mode=ParseMode.HTML,
        reply_markup=entry_keyboard(saved_ids, single_kind, parsed["yozuvlar"]),
    )

    # Byudjet oshdimi? Faqat shu yozuvga tegishli kategoriyalarni tekshiramiz.
    touched = {item["kategoriya"] for item in parsed["yozuvlar"]
               if item["turi"] == config.KIND_CHIQIM}
    if touched:
        await check_budget_alerts(context, user_id, touched)

    # Jamg'arma yozilgan bo'lsa — maqsad va seriya haqida javob.
    if any(i["turi"] in config.SAVINGS_KINDS for i in parsed["yozuvlar"]):
        await after_savings_entry(context, user_id, message)
    else:
        # Kirim yozilgan bo'lsa — «avval o'zingga to'la» eslatmasi.
        await offer_savings_split(context, user_id, message,
                                  parsed["yozuvlar"])

    await _celebrate(update, context, message, len(saved_ids))


# Nishonlanadigan bosqichlar. Har kuni emas — kamdan-kam bo'lgani uchun
# quvontiradi; har safar bo'lsa bezdiradi.
STREAK_MILESTONES = {7: "streak_7", 30: "streak_30", 100: "streak_100"}
ENTRY_MILESTONES = (10, 50, 100, 500, 1000)


async def _celebrate(update: Update, context: ContextTypes.DEFAULT_TYPE,
                     message, added: int) -> None:
    """Zanjir va bosqichlarni nishonlaydi.

    Marketing emas — odat shakllantirish: odam nima uchun davom
    etayotganini ko'rib tursa, tashlab ketmaydi. Xato bo'lsa ham asosiy
    javobga ta'sir qilmasligi kerak.
    """
    user_id = update.effective_user.id
    lang = lang_of(user_id, context)
    try:
        streak = db.touch_streak(user_id)
        lines = []

        key = STREAK_MILESTONES.get(streak["streak"])
        if streak["grew"] and key:
            lines.append(i18n.t(lang, key))
        elif streak["grew"] and streak["streak"] >= 3:
            if streak["streak"] == streak["best"] and streak["streak"] > 3:
                lines.append(i18n.t(lang, "streak_record", n=streak["streak"]))
            else:
                lines.append(i18n.t(lang, "streak_grew", n=streak["streak"]))

        total = db.tx_count(user_id)
        if total == added:
            db.log_event(user_id, "birinchi_yozuv")
            # Birinchi yozuvdan keyin — maqtov va keyingi bitta qadam.
            lines.append(i18n.t(lang, "first_entry"))
        # Bitta xabarda bir nechta yozuv bo'lishi mumkin — bosqichdan
        # «sakrab o'tib ketmasligi» uchun oraliqni tekshiramiz.
        for mark in ENTRY_MILESTONES:
            if total - added < mark <= total:
                lines.append(i18n.t(lang, "entries_milestone", n=mark,
                                    btn=i18n.btn(lang, "month")))
                break

        if lines:
            await message.reply_text("\n\n".join(lines), parse_mode=ParseMode.HTML)
    except Exception:
        log.exception("Zanjir/bosqich xabarida xatolik")


# --------------------------------------------------------------------------- #
# Tugmalar
# --------------------------------------------------------------------------- #

def _split_message(text: str, limit: int = 3900) -> list[str]:
    """Uzun xabarni Telegram chegarasiga sig'adigan bo'laklarga bo'ladi."""
    if len(text) <= limit:
        return [text]
    chunks, current = [], ""
    for line in text.split("\n"):
        if len(current) + len(line) + 1 > limit:
            chunks.append(current)
            current = line
        else:
            current = f"{current}\n{line}" if current else line
    if current:
        chunks.append(current)
    return chunks


async def on_callback(update: Update, context: ContextTypes.DEFAULT_TYPE):
    query = update.callback_query
    user = update.effective_user
    user_id = user.id
    data = query.data or ""

    # Obuna va hisobni o'chirish tugmalari kirish chegarasidan OLDIN keladi —
    # muddati tugagan foydalanuvchi ham to'lov qila olishi va ma'lumotini
    # o'chira olishi kerak.
    if data.startswith("g:"):
        await on_guide_callback(update, context)
        return
    if data.startswith("bc:"):
        await broadcast.on_broadcast_callback(update, context)
        return
    if data.startswith("pro:"):
        # Paywall'dagi «💎 PRO ga o'tish» — tariflar sahifasi.
        await query.answer()
        await send_plans(update, context)
        return
    if data.startswith(("sub:", "subok:", "subno:")):
        await on_subscription_callback(update, context)
        return
    if data.startswith("erase:"):
        await on_erase_callback(update, context)
        return
    if data.startswith("lang:"):
        await on_lang_callback(update, context)
        return
    # Rozilik tugmalari — rozilik darvozasining o'zi, undan oldin keladi.
    if data.startswith("ok:"):
        await on_consent_callback(update, context)
        return

    # Boshqa hamma tugma uchun bot bilan bir xil kirish qoidasi.
    access = db.access_status(user_id, user.first_name or "", user.username)
    if not access["ok"]:
        await query.answer("Ruxsat yo'q.", show_alert=True)
        return

    if not db.has_consent(user_id, CONSENT_VERSION):
        await query.answer(i18n.t(lang_of(user_id, context), "consent_needed"),
                           show_alert=True)
        return

    if data.startswith("m:"):
        await on_more_callback(update, context)
        return
    if data.startswith("rem:"):
        await on_reminder_callback(update, context)
        return
    if data.startswith("share:"):
        await on_share_callback(update, context)
        return
    if data.startswith("try:"):
        await on_try_callback(update, context)
        return

    if data.startswith("d:"):
        tx_id = int(data[2:])
        db.delete_transaction(user_id, tx_id)
        await query.answer("O'chirildi")
        await query.edit_message_text("🗑 Yozuv o'chirildi.")
        return

    if data.startswith("e:"):
        # Ko'p yozuvli xabardan bitta yozuvni ochish.
        tx_id = int(data[2:])
        row = db.get_transaction(user_id, tx_id)
        if not row:
            await query.answer("Yozuv topilmadi (o'chirilgan bo'lishi mumkin)",
                               show_alert=True)
            return
        await query.answer()
        await query.message.reply_text(
            reports.transaction_line(row), parse_mode=ParseMode.HTML,
            reply_markup=entry_keyboard([tx_id], row["kind"]))
        return

    if data.startswith("D:"):
        ids = [int(x) for x in data[2:].split(",") if x.isdigit()]
        for tx_id in ids:
            db.delete_transaction(user_id, tx_id)
        await query.answer("O'chirildi")
        await query.edit_message_text(f"🗑 {len(ids)} ta yozuv o'chirildi.")
        return

    # --- Chek tugmalari ---

    if data.startswith("R:"):
        receipt_id = data[2:]
        removed = db.delete_receipt(user_id, receipt_id)
        _last_receipt.pop(user_id, None)
        await query.answer("O'chirildi")
        await query.edit_message_text(f"🗑 Chek o'chirildi ({removed} ta yozuv).")
        return

    if data.startswith("L:"):
        receipt_id = data[2:]
        rows = db.rows_by_receipt(user_id, receipt_id)
        await query.answer()
        for chunk in _split_message(reports.receipt_items_text(rows)):
            await query.message.reply_text(chunk, parse_mode=ParseMode.HTML)
        return

    if data.startswith("A:"):
        receipt_id = data[2:]
        last = _last_receipt.get(user_id)
        if not last or last["receipt_id"] != receipt_id:
            await query.answer(
                "Bu chek rasmlari saqlanmagan. «🧾 Uzun chek» bilan qaytadan yuboring.",
                show_alert=True,
            )
            return
        # Eski yozuvlar olib tashlanadi — chek to'liq holda qayta o'qiladi.
        db.delete_receipt(user_id, receipt_id)
        _collect.set(user_id, {"images": list(last["images"]), "caption": last["caption"]})
        await query.answer()
        await query.edit_message_text(
            f"➕ Chekning qolgan qismlarini yuboring "
            f"({len(last['images'])} ta qism allaqachon bor).\n"
            "Tugagach «✅ Tayyor» bosing — chek boshidan qayta hisoblanadi."
        )
        await query.message.reply_text(
            "Qolgan qismlarni kutyapman…", reply_markup=COLLECT_MENU
        )
        return

    if data.startswith(("gl:", "glp:", "gla:")):
        await on_goal_callback(update, context)
        return
    if data.startswith("rate:"):
        await on_rate_callback(update, context)
        return
    if data.startswith(("due:", "dueset:")):
        await on_due_callback(update, context)
        return
    if data.startswith("jam:"):
        await on_savings_callback(update, context)
        return
    if data == "jamqoy":
        await on_savings_add_callback(update, context)
        return

    # --- Kategoriya tugmalari ---

    if data.startswith("c:"):
        tx_id = int(data[2:])
        row = db.get_transaction(user_id, tx_id)
        if not row:
            await query.answer("Yozuv topilmadi", show_alert=True)
            return
        await query.answer()
        await query.edit_message_reply_markup(category_keyboard(tx_id, row["kind"]))
        return

    if data.startswith(("k:", "s:")):
        prefix, raw_id, raw_idx = data.split(":")
        tx_id, idx = int(raw_id), int(raw_idx)
        row = db.get_transaction(user_id, tx_id)
        if not row:
            await query.answer("Yozuv topilmadi", show_alert=True)
            return
        if prefix == "k":
            names = config.CATEGORY_REGISTRY
        else:
            # Eski xabardagi tugma: raqam o'sha paytdagi ro'yxatda edi —
            # keyin qo'shilgan kategoriyalarsiz.
            names = [c for c in config.categories_for(row["kind"])
                     if config.CATEGORY_REGISTRY.index(c) < LEGACY_CATEGORY_COUNT]
        category = names[idx] if 0 <= idx < len(names) else None
        if category not in config.categories_for(row["kind"]):
            await query.answer("Noto'g'ri kategoriya", show_alert=True)
            return
        db.update_category(user_id, tx_id, category)
        learned = learning.remember(user_id, row["kind"], row["note"], category)
        await query.answer(f"Eslab qoldim: «{learned}» → {config.category_label(category)}"
                           if learned else "Yangilandi")
        row = db.get_transaction(user_id, tx_id)
        await query.edit_message_text(
            "✏️ Kategoriya yangilandi\n\n" + reports.transaction_line(row),
            parse_mode=ParseMode.HTML,
            reply_markup=entry_keyboard([tx_id], row["kind"]),
        )
        return

    if data.startswith("x:"):
        tx_id = int(data[2:])
        row = db.get_transaction(user_id, tx_id)
        await query.answer()
        await query.edit_message_reply_markup(
            entry_keyboard([tx_id], row["kind"] if row else None)
        )
        return

    # --- Turini almashtirish ---

    if data.startswith("T:"):
        _, raw_id, raw_kind = data.split(":")
        tx_id, kind_idx = int(raw_id), int(raw_kind)
        row = db.get_transaction(user_id, tx_id)
        new_kind = config.KINDS[kind_idx] if 0 <= kind_idx < len(config.KINDS) else None
        if not row or new_kind not in config.KIND_SWITCHES.get(row["kind"], []):
            await query.answer("Bu yozuv turini almashtirib bo'lmaydi", show_alert=True)
            return
        db.update_kind(user_id, tx_id, new_kind, config.fallback_category(new_kind))
        await query.answer("Turi yangilandi")
        row = db.get_transaction(user_id, tx_id)
        hint = ("\n\n<i>Kategoriyani ham to'g'rilash uchun «✏️ Kategoriya» bosing.</i>"
                if new_kind in (config.KIND_CHIQIM, config.KIND_KIRIM) else
                "\n\n<i>Qarz to'lovi kundalik chiqim va kirimga kirmaydi.</i>")
        await query.edit_message_text(
            f"🔄 {config.KIND_LABELS[new_kind]}\n\n" + reports.transaction_line(row) + hint,
            parse_mode=ParseMode.HTML,
            reply_markup=entry_keyboard([tx_id], new_kind),
        )
        return

    # Eski xabarlardagi tugma (faqat kirim <-> chiqim).
    if data.startswith("t:"):
        tx_id = int(data[2:])
        row = db.get_transaction(user_id, tx_id)
        if not row or row["kind"] not in (config.KIND_CHIQIM, config.KIND_KIRIM):
            await query.answer("Bu yozuv turini almashtirib bo'lmaydi", show_alert=True)
            return
        new_kind = config.KIND_KIRIM if row["kind"] == config.KIND_CHIQIM else config.KIND_CHIQIM
        new_category = config.fallback_category(new_kind)
        db.update_kind(user_id, tx_id, new_kind, new_category)
        await query.answer("Turi yangilandi")
        row = db.get_transaction(user_id, tx_id)
        await query.edit_message_text(
            f"🔄 {config.KIND_LABELS[new_kind]}ga almashtirildi\n\n"
            + reports.transaction_line(row)
            + "\n\n<i>Kategoriyani ham to'g'rilash uchun «✏️ Kategoriya» bosing.</i>",
            parse_mode=ParseMode.HTML,
            reply_markup=entry_keyboard([tx_id], new_kind),
        )
        return

    await query.answer()


# --------------------------------------------------------------------------- #
# Obuna holati (hamma uchun) va admin buyruqlari (faqat ega uchun)
# --------------------------------------------------------------------------- #

def _fmt_dt(dt) -> str:
    return dt.strftime("%d.%m.%Y") if dt else "—"


# --------------------------------------------------------------------------- #
# Obuna tariflari
# --------------------------------------------------------------------------- #

def _fmt_price(amount: int) -> str:
    return f"{amount:,}".replace(",", " ") + " so'm"


def _plan_label(plan: dict, lang: str) -> str:
    key = f"plan_label_{plan['code']}"
    label = i18n.t(lang, key)
    return plan["label"] if label == key else label


def plans_keyboard(lang: str = "uz") -> InlineKeyboardMarkup:
    """Yangi xarid uchun tariflar: yillik birinchi («⭐ Eng foydali»)."""
    rows = []
    for p in config.public_plans():
        label = _plan_label(p, lang)
        if p.get("best"):
            label = f"⭐ {label}"
        elif p.get("founders"):
            label = f"🎁 {label}"
        rows.append([InlineKeyboardButton(
            f"{label} — {_fmt_price(p['price'])}", callback_data=f"sub:{p['code']}")])
    return InlineKeyboardMarkup(rows)


def plans_text(access: dict | None = None, lang: str = "uz") -> str:
    """Tariflar sahifasi (4.5): foyda bilan boshlanadi, keyin narxlar."""
    lines = [i18n.t(lang, "pro_title"), "", i18n.t(lang, "pro_pitch"), "",
             i18n.t(lang, "pro_features"), ""]

    for p in config.public_plans():
        label = _plan_label(p, lang)
        price = _fmt_price(p["price"])
        if p.get("best"):
            lines.append(i18n.t(lang, "plan_best_line", label=label, price=price,
                                monthly=_fmt_price(config.plan_monthly_price(p)),
                                pct=config.plan_discount_percent(p)))
        elif p.get("founders"):
            lines.append(i18n.t(lang, "plan_founders_line", label=label, price=price,
                                left=p["left"], total=config.FOUNDERS_LIMIT))
        else:
            lines.append(i18n.t(lang, "plan_line", label=label, price=price))

    status = (access or {}).get("status")
    if status == "trial":
        lines += ["", i18n.t(lang, "pro_status_trial", days=access["days_left"])]
    elif status == "subscribed":
        lines += ["", i18n.t(lang, "pro_status_sub", days=access["days_left"])]
    lines += ["", i18n.t(lang, "pro_pick")]
    return "\n".join(lines)


async def send_plans(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    user = update.effective_user
    access = db.access_status(user.id, user.first_name or "", user.username)
    lang = lang_of(user.id, context)
    db.log_event(user.id, "obuna_ochildi")

    if access["status"] == "owner":
        await update.effective_message.reply_text(
            i18n.t(lang, "owner_no_sub") + "\n\n" + plans_text(lang=lang),
            parse_mode=ParseMode.HTML,
        )
        return

    await update.effective_message.reply_text(
        plans_text(access, lang), parse_mode=ParseMode.HTML,
        reply_markup=plans_keyboard(lang)
    )


async def cmd_plans(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """Tariflarni ko'rsatadi. ATAYLAB kirish chegarasidan tashqarida."""
    if update.effective_user is None:
        return
    await send_plans(update, context)


def payment_text(plan: dict, lang: str = "uz") -> str:
    """Karta rekvizitlari va to'lov yo'riqnomasi."""
    contact = reports.esc(_support_contact())
    price = _fmt_price(plan["price"])
    if not config.card_ready():
        return i18n.t(lang, "pay_no_card", plan=plan["label"], price=price,
                      contact=contact)
    bank = f"\n🏦 {reports.esc(config.CARD_BANK)}" if config.CARD_BANK else ""
    return (i18n.t(lang, "pay_title") + "\n\n"
            + i18n.t(lang, "pay_body", plan=plan["label"], price=price,
                     card=reports.esc(config.card_pretty()),
                     holder=reports.esc(config.card_holder()), bank=bank,
                     contact=contact))


async def on_subscription_callback(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """Foydalanuvchi tarif tanladi — karta rekvizitlari ko'rsatiladi.

    Tasdiqlash bot ichida emas, admin web panelda amalga oshiriladi.
    """
    query = update.callback_query
    user = update.effective_user
    data = query.data or ""

    lang = lang_of(user.id, context)

    if data == "sub:bekor":
        _awaiting_proof.pop(user.id, None)
        await query.answer("OK")
        await query.edit_message_text(i18n.t(lang, "pay_cancelled"))
        return

    if not data.startswith("sub:"):
        await query.answer("Bu tugma endi ishlamaydi. /obuna dan qayta boshlang.",
                           show_alert=True)
        return

    # Faqat hozir sotilayotgan tarif: eski xabardagi 3/6 oylik tugmasi yoki
    # joylari tugagan asoschilar taklifi qayta ochilmaydi.
    plan = config.purchasable_plan(data[4:])
    if not plan:
        await query.answer(i18n.t(lang, "plan_unavailable"), show_alert=True)
        return

    # To'lov so'rovi ham shaxsiy ma'lumot — rozilikdan oldin yaratilmaydi.
    if not db.has_consent(user.id, CONSENT_VERSION):
        await query.answer(i18n.t(lang, "consent_needed"), show_alert=True)
        await _consent_ok(update, context)
        return

    request_id = db.add_subscription_request(user.id, plan["code"], plan["price"])
    # Endi shu foydalanuvchidan keladigan rasm chek deb qabul qilinadi.
    _awaiting_proof.set(user.id, request_id)

    await query.answer("💳")
    await query.edit_message_text(
        payment_text(plan, lang),
        parse_mode=ParseMode.HTML,
        reply_markup=InlineKeyboardMarkup([[
            InlineKeyboardButton(i18n.t(lang, "erase_btn_no"),
                                 callback_data="sub:bekor")
        ]]),
    )

    uname = f"@{user.username}" if user.username else "(username yo'q)"
    note = (
        "🔔 <b>Yangi obuna so'rovi</b>\n\n"
        f"👤 {reports.esc(user.first_name or '')} {reports.esc(uname)}\n"
        f"🆔 <code>{user.id}</code>\n"
        f"💎 {plan['label']} — {_fmt_price(plan['price'])}\n\n"
        f"<i>To'lov cheki kutilmoqda.</i>\n"
        f"{config.ADMIN_PANEL_URL or 'admin panel'}/sorovlar"
    )
    for owner in config.OWNER_IDS:
        try:
            await context.bot.send_message(owner, note, parse_mode=ParseMode.HTML,
                                           disable_web_page_preview=True)
        except Exception:
            log.warning("Adminga bildirishnoma yuborilmadi: %s", owner)


async def handle_payment_proof(update: Update, context: ContextTypes.DEFAULT_TYPE) -> bool:
    """Kutilayotgan to'lov chekini qabul qiladi. Qabul qilinsa True qaytaradi.

    Kirish chegarasidan TASHQARIDA chaqiriladi — muddati tugagan
    foydalanuvchi ham to'lov chekini yubora olishi kerak.
    """
    user = update.effective_user
    message = update.effective_message
    request_id = _awaiting_proof.get(user.id)
    if request_id is None:
        return False

    # Chek rasm (skrinshot) yoki PDF ko'rinishida kelishi mumkin —
    # bank ilovalari ko'pincha PDF kvitansiya beradi.
    kind = "rasm"
    if message.photo:
        file_id = message.photo[-1].file_id
    elif message.document:
        doc = message.document
        mime = (doc.mime_type or "").lower()
        name = (doc.file_name or "").lower()
        if mime == PDF_TYPE or name.endswith(".pdf"):
            kind = "pdf"
        elif not mime.startswith("image/"):
            await message.reply_text(
                "⚠️ Chekni <b>rasm</b> (JPG/PNG) yoki <b>PDF</b> ko'rinishida "
                "yuboring.",
                parse_mode=ParseMode.HTML)
            return True
        file_id = doc.file_id
    else:
        return False

    req = db.get_request(request_id)
    if req is None or req["status"] not in ("kutilmoqda", "tekshiruvda"):
        _awaiting_proof.pop(user.id, None)
        await message.reply_text(i18n.t(lang_of(user.id, context), "proof_stale"))
        return True

    db.attach_payment_proof(request_id, file_id, kind)
    _awaiting_proof.pop(user.id, None)

    plan = config.plan_by_code(req["plan_code"])
    label = plan["label"] if plan else req["plan_code"]
    await message.reply_text(
        i18n.t(lang_of(user.id, context), "proof_received", plan=label,
               price=_fmt_price(req["price"])),
        parse_mode=ParseMode.HTML,
    )

    uname = f"@{user.username}" if user.username else "(username yo'q)"
    caption = (
        "💳 <b>To'lov cheki keldi</b>\n\n"
        f"👤 {reports.esc(user.first_name or '')} {reports.esc(uname)}\n"
        f"🆔 <code>{user.id}</code>\n"
        f"💎 {label} — {_fmt_price(req['price'])}\n\n"
        f"Tasdiqlash: {config.ADMIN_PANEL_URL or 'admin panel'}/sorovlar"
    )
    for owner in config.OWNER_IDS:
        try:
            if kind == "pdf":
                await context.bot.send_document(owner, file_id, caption=caption,
                                                parse_mode=ParseMode.HTML)
            else:
                await context.bot.send_photo(owner, file_id, caption=caption,
                                             parse_mode=ParseMode.HTML)
        except Exception:
            log.warning("Adminga chek yuborilmadi: %s", owner)
    return True


# --------------------------------------------------------------------------- #
# Ma'lumot huquqlari: maxfiylik va hisobni o'chirish
# --------------------------------------------------------------------------- #

# Shartlar o'zgarsa config.CONSENT_VERSION oshiriladi.
CONSENT_VERSION = config.CONSENT_VERSION

def _terms_text(lang: str) -> str:
    """Ommaviy oferta matni. Rekvizitlar .env da to'ldirilgan bo'lsa
    qo'shiladi — ro'yxatdan o'tmaguncha yolg'on ma'lumot yozilmaydi."""
    text = i18n.t(lang, "terms", trial=config.trial_days(),
                  contact=reports.esc(_support_contact()),
                  version=CONSENT_VERSION)
    line = config.operator_line()
    if line:
        text += "\n" + i18n.t(lang, "terms_operator",
                              operator=reports.esc(line))
    return text


@skip_consent
async def cmd_terms(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """/shartlar — ommaviy oferta. Kirish chegarasidan tashqarida."""
    lang = lang_of(update.effective_user.id, context)
    await update.effective_message.reply_text(
        _terms_text(lang), parse_mode=ParseMode.HTML,
        disable_web_page_preview=True)


@private_only
async def cmd_rate(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """/kurs — bugungi rasmiy kurs. FAQAT o'qish uchun.

    Kursni qo'lda o'rnatish imkoni ATAYLAB yo'q. Har bir valyutali
    yozuv kiritilgan kundagi kurs bilan so'mga o'giriladi va
    `amount_base` ustunida saqlanadi — barcha jamlanmalar, byudjet
    ogohlantirishlari va hisobotlar o'shanga tayanadi. Foydalanuvchi
    kursni o'zi qo'ysa, bu raqamlar hisobot bo'lishdan to'xtaydi.

    Kurs Markaziy bankdan olinadi va har kuni ertalab yangilanadi.
    """
    msg = update.effective_message
    today = reports.today()

    rate = await asyncio.to_thread(rates.get, "usd", today)
    source = db.rate_source("usd", today) or ""
    manba = "Markaziy bank" if source.startswith("cbu") else "Markaziy bank"
    await msg.reply_text(
        f"\U0001F4B1 <b>Valyuta kursi</b>\n\n"
        f"1 $ = <b>{reports.fmt_money(rate)}</b>\n"
        f"<i>Manba: {manba} \u2014 har kuni ertalab yangilanadi</i>\n\n"
        f"Dollarda yozgan yozuvlaringiz shu kurs bilan umumiy hisobga "
        f"qo\'shiladi. Har bir yozuv o\'z kunidagi kursni saqlab qoladi "
        f"\u2014 kurs o\'zgarsa ham eski hisobot o\'zgarmaydi.",
        parse_mode=ParseMode.HTML)


async def job_refresh_rates(context: ContextTypes.DEFAULT_TYPE) -> None:
    """Har kuni ertalab kursni yangilaydi — kun davomida tarmoqqa
    chiqmasdan ishlash uchun."""
    try:
        result = await asyncio.to_thread(rates.refresh)
        log.info("Kurslar yangilandi: %s", result)
    except Exception:
        log.warning("Kursni yangilab bo'lmadi", exc_info=True)


async def cmd_lang(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """Interfeys tilini tanlash. Kirish chegarasidan tashqarida —
    muddati tugagan foydalanuvchi ham tilni o'zgartira olishi kerak."""
    user = update.effective_user
    if user is None:
        return
    db.get_or_create_user(user.id, user.first_name or "", user.username)
    lang = lang_of(user.id, context)
    await update.effective_message.reply_text(
        i18n.t(lang, "lang_choose"),
        parse_mode=ParseMode.HTML,
        reply_markup=InlineKeyboardMarkup([
            [InlineKeyboardButton(label, callback_data=f"lang:{code}")]
            for code, label in i18n.LANGS.items()
        ]),
    )


async def on_lang_callback(update: Update, context: ContextTypes.DEFAULT_TYPE):
    query = update.callback_query
    user = update.effective_user
    code = i18n.normalize((query.data or "lang:uz").split(":")[1])
    db.set_lang(user.id, code)
    context.user_data["_lang"] = code
    await query.answer(i18n.LANGS[code])
    await query.edit_message_text(i18n.t(code, "lang_set"))
    # Klaviatura yangi tilda qayta chiziladi.
    await context.bot.send_message(
        query.message.chat_id, i18n.btn(code, "guide") + " · /qollanma",
        reply_markup=main_menu(code))


@skip_consent
async def cmd_privacy(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """Maxfiylik siyosati — kirish chegarasidan tashqarida."""
    lang = lang_of(update.effective_user.id, context)
    await update.effective_message.reply_text(
        i18n.t(lang, "privacy", contact=reports.esc(_support_contact())),
        parse_mode=ParseMode.HTML, disable_web_page_preview=True)


async def cmd_erase(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """Hisobni o'chirish — ikki bosqichli tasdiqlash bilan."""
    user = update.effective_user
    if user is None:
        return
    rows = len(db.all_rows(user.id))
    lang = lang_of(user.id, context)
    # Oldingi tugallanmagan urinish qolgan bo'lsa tozalaymiz.
    _erase_typed.pop(user.id, None)
    _awaiting_erase.set(user.id, True)
    await update.effective_message.reply_text(
        i18n.t(lang, "erase_confirm", n=rows),
        parse_mode=ParseMode.HTML,
        reply_markup=InlineKeyboardMarkup([
            [InlineKeyboardButton(i18n.t(lang, "erase_btn_csv"),
                                  callback_data="erase:csv")],
            [InlineKeyboardButton(i18n.t(lang, "erase_btn_yes"),
                                  callback_data="erase:ha")],
            [InlineKeyboardButton(i18n.t(lang, "erase_btn_no"),
                                  callback_data="erase:yoq")],
        ]),
    )


async def on_erase_callback(update: Update, context: ContextTypes.DEFAULT_TYPE):
    query = update.callback_query
    user = update.effective_user
    data = query.data or ""

    lang = lang_of(user.id, context)

    if data == "erase:yoq":
        _awaiting_erase.pop(user.id, None)
        _erase_typed.pop(user.id, None)
        await query.answer("OK")
        await query.edit_message_text(i18n.t(lang, "erase_cancelled"))
        return

    if data == "erase:csv":
        await query.answer("CSV")
        await _send_csv(update, context, user.id)
        await query.edit_message_text("📤 /ochirish")
        _awaiting_erase.pop(user.id, None)
        return

    if data == "erase:ha":
        if not _awaiting_erase.get(user.id):
            await query.answer(i18n.t(lang, "erase_expired"), show_alert=True)
            return
        # Tugma bosildi — lekin hali o'chirmaymiz. Bexosdan bosib
        # yuborish oson, shuning uchun oxirgi tasdiq yozma bo'ladi:
        # foydalanuvchi so'zni o'zi terishi kerak.
        _awaiting_erase.pop(user.id, None)
        rows = len(db.all_rows(user.id))
        _erase_typed.set(user.id, True)
        await query.answer()
        await query.edit_message_text(
            i18n.t(lang, "erase_type", n=rows, word=i18n.t(lang, "erase_word")),
            parse_mode=ParseMode.HTML)
        return


# --------------------------------------------------------------------------- #
# Referal — do'st taklif qilish
# --------------------------------------------------------------------------- #

@private_only
async def cmd_referral(update: Update, context: ContextTypes.DEFAULT_TYPE):
    user = update.effective_user
    lang = lang_of(user.id, context)
    stats = db.referral_stats(user.id)
    me = await context.bot.get_me()
    link = f"https://t.me/{me.username}?start=ref{user.id}"

    share = quote(i18n.t(lang, "referral_share_text"))
    share_url = f"https://t.me/share/url?url={quote(link)}&text={share}"

    await update.effective_message.reply_text(
        i18n.t(lang, "referral", bonus=config.REFERRAL_BONUS_DAYS, link=link,
               invited=stats["invited"], bonus_days=stats["bonus_days"]),
        parse_mode=ParseMode.HTML,
        disable_web_page_preview=True,
        reply_markup=InlineKeyboardMarkup([[
            InlineKeyboardButton(i18n.t(lang, "referral_share_btn"), url=share_url)
        ]]),
    )


async def _apply_referral(update: Update, context: ContextTypes.DEFAULT_TYPE,
                          payload: str) -> None:
    """/start ref<id> — taklif qilganni qayd etadi va ikkalasiga bonus beradi."""
    user = update.effective_user
    if not payload.startswith("ref"):
        return
    raw = payload[3:]
    if not raw.isdigit():
        return
    referrer_id = int(raw)
    if not db.set_referrer(user.id, referrer_id):
        return

    bonus = config.REFERRAL_BONUS_DAYS
    db.add_bonus_days(user.id, bonus)
    db.add_bonus_days(referrer_id, bonus)
    log.info("Referal: %s -> %s (+%s kun)", referrer_id, user.id, bonus)

    await update.effective_message.reply_text(
        i18n.t(lang_of(user.id, context), "referral_welcome", bonus=bonus),
        parse_mode=ParseMode.HTML)
    try:
        await context.bot.send_message(
            referrer_id,
            i18n.t(lang_of(referrer_id), "referral_thanks",
                   name=reports.esc(user.first_name or "?"), bonus=bonus),
            parse_mode=ParseMode.HTML)
    except Exception:
        log.info("Referal xabari yuborilmadi: %s", referrer_id)


# --------------------------------------------------------------------------- #
# Byudjet
# --------------------------------------------------------------------------- #

_MULTIPLIERS = {
    "ming": 1_000, "k": 1_000, "минг": 1_000,
    "mln": 1_000_000, "million": 1_000_000, "mil": 1_000_000,
    "lim": 1_000_000, "m": 1_000_000, "млн": 1_000_000,
    "mlrd": 1_000_000_000, "milliard": 1_000_000_000,
}


def _parse_amount_uz(text: str) -> float | None:
    """«2 mln», «500 ming», «1 200 000», «20k» → son.

    AI'ga murojaat qilmaydi — byudjet buyrug'i tez va tekin bo'lishi kerak.
    """
    raw = (text or "").lower().replace(" ", " ").strip()
    if not raw:
        return None
    # Sonni va undan keyingi birlikni ajratamiz.
    number = ""
    rest = ""
    for i, ch in enumerate(raw):
        if ch.isdigit() or ch in ".,":
            number += "." if ch == "," else ch
        elif ch == " " and number and raw[i + 1:i + 2].isdigit():
            continue          # «1 200 000» ichidagi bo'sh joy
        elif number:
            rest = raw[i:].strip()
            break
    if not number:
        return None
    try:
        value = float(number)
    except ValueError:
        return None

    # «300 mln,» — birlikdan keyingi tinish belgisi birlikka kirmaydi.
    unit = rest.split()[0].strip(".,;:—-") if rest else ""
    if unit in _MULTIPLIERS:
        return value * _MULTIPLIERS[unit]
    # Birliksiz kichik son ming deb olinadi — matn yozuvlaridagi qoida bilan bir xil.
    if config.SMALL_NUMBERS_ARE_THOUSANDS and value < 1000:
        return value * 1000
    return value


@private_only
async def cmd_budget(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """/byudjet — ro'yxat; /byudjet <kategoriya> <summa> — o'rnatish."""
    if not tiers.allows(context.user_data.get("access"), "budget"):
        await show_paywall(update, context, "budget")
        return
    user_id = update.effective_user.id
    args = context.args or []
    msg = update.effective_message

    if args:
        if args[-1].lower() in ("o'chir", "ochir", "0"):
            category = config.normalize_category(
                config.KIND_CHIQIM, " ".join(args[:-1]))
            ok = db.delete_budget(user_id, category)
            await msg.reply_text(
                f"🗑 «{category}» byudjeti o'chirildi." if ok
                else f"«{category}» uchun byudjet yo'q edi.")
            return

        amount = _parse_amount_uz(args[-1])
        category = config.normalize_category(config.KIND_CHIQIM, " ".join(args[:-1]))
        if not amount or amount <= 0:
            await msg.reply_text(
                "Summani tushunmadim.\n\n"
                "Masalan: <code>/byudjet oziq-ovqat 2 mln</code>",
                parse_mode=ParseMode.HTML)
            return
        db.set_budget(user_id, category, amount)
        await msg.reply_text(
            f"✅ <b>{category}</b> uchun oylik byudjet: "
            f"<b>{reports.fmt_money(amount, 'som')}</b>\n\n"
            f"80% va 100% ga yetganda ogohlantiraman.",
            parse_mode=ParseMode.HTML)
        return

    rows = db.budget_status(user_id)
    if not rows:
        cats = ", ".join(config.EXPENSE_CATEGORIES[:6])
        await msg.reply_text(
            "💰 <b>Oylik byudjet</b>\n\n"
            "Kategoriyaga oylik chegara qo'ying — oshib ketsa ogohlantiraman.\n\n"
            "<b>O'rnatish:</b>\n"
            "<code>/byudjet oziq-ovqat 2 mln</code>\n"
            "<code>/byudjet transport 500 ming</code>\n\n"
            "<b>O'chirish:</b>\n"
            "<code>/byudjet transport o'chir</code>\n\n"
            f"<i>Kategoriyalar: {cats} …</i>",
            parse_mode=ParseMode.HTML)
        return

    lines = ["💰 <b>Shu oylik byudjet</b>", ""]
    for r in rows:
        pct = r["percent"]
        bar_len = 10
        filled = min(bar_len, int(round(pct / 100 * bar_len)))
        bar = "█" * filled + "░" * (bar_len - filled)
        icon = "🔴" if pct >= 100 else ("🟡" if pct >= 80 else "🟢")
        lines.append(f"{icon} <b>{r['category']}</b>")
        lines.append(
            f"    {bar} {pct:.0f}%\n"
            f"    {reports.fmt_money(r['spent'], r['currency'])} / "
            f"{reports.fmt_money(r['limit'], r['currency'])}")
        if r["left"] >= 0:
            lines.append(f"    qoldi: {reports.fmt_money(r['left'], r['currency'])}")
        else:
            lines.append(f"    ⚠️ oshib ketdi: "
                         f"{reports.fmt_money(-r['left'], r['currency'])}")
        lines.append("")
    lines.append("<i>O'zgartirish: /byudjet &lt;kategoriya&gt; &lt;summa&gt;</i>")
    await msg.reply_text("\n".join(lines), parse_mode=ParseMode.HTML)


# --------------------------------------------------------------------------- #
# Shaxsiy jamg'arma
# --------------------------------------------------------------------------- #

def _card_keyboard(lang: str) -> InlineKeyboardMarkup:
    return InlineKeyboardMarkup([
        [InlineKeyboardButton(i18n.t(lang, "savings_card_yes"), callback_data="jam:bor")],
        [InlineKeyboardButton(i18n.t(lang, "savings_card_no"), callback_data="jam:yoq")],
    ])


def _cushion_line(user_id: int, lang: str, balance: float) -> str:
    """«Bu jamg'arma necha oyga yetadi» — kitobning 6-davosi.

    O'rtacha oylik chiqim oxirgi 90 kundan olinadi. Chiqimi yo'q odamda
    hisoblab bo'lmaydi — bunda qator umuman ko'rsatilmaydi, taxminiy
    raqam o'ylab topilmaydi.
    """
    if balance <= 0:
        return ""
    end = datetime.now(config.TZ).date()
    start = end - timedelta(days=89)
    spent = db.totals_unified(user_id, start, end)["totals"][config.KIND_CHIQIM]
    monthly = spent / 3
    if monthly < 1:
        return ""
    months = balance / monthly
    if months < 1:
        text = f"{months * 30:.0f} kun" if lang == "uz" else f"{months * 30:.0f} дней"
    else:
        text = f"{months:.1f} oy" if lang == "uz" else f"{months:.1f} мес."
    return i18n.t(lang, "savings_cushion",
                  monthly=reports.fmt_money(monthly, "som"), months=text)


@private_only
async def cmd_savings(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """/jamgarma — qoldiq, alohida karta holati va maslahat."""
    user_id = update.effective_user.id
    lang = lang_of(user_id, context)
    msg = update.effective_message

    prof = db.savings_profile(user_id)
    # Hali so'ralmagan bo'lsa — avval kartani so'raymiz. Bu bir marta
    # bo'ladi va javob eslab qolinadi.
    if prof["card_state"] == db.CARD_SORALMAGAN:
        db.mark_card_asked(user_id)
        await msg.reply_text(i18n.t(lang, "savings_card_ask"),
                             parse_mode=ParseMode.HTML,
                             reply_markup=_card_keyboard(lang))
        return

    now = datetime.now(config.TZ).date()
    balance = db.savings_balance(user_id)
    month = db.savings_in_period(user_id, now.replace(day=1), now)
    has_card = prof["card_state"] == db.CARD_BOR

    advice = _cushion_line(user_id, lang, balance)
    if not has_card:
        # Kartasi yo'q odamga eng foydali gap — o'sha karta haqida.
        advice = i18n.t(lang, "savings_card_nudge",
                        balance=reports.fmt_money(balance, "som"))

    await msg.reply_text(
        i18n.t(lang, "savings_status",
               balance=reports.fmt_money(balance, "som"),
               month=reports.fmt_money(month, "som"),
               card=i18n.t(lang, "savings_card_state_yes" if has_card
                           else "savings_card_state_no"),
               advice=advice or ""),
        parse_mode=ParseMode.HTML,
        reply_markup=None if has_card else _card_keyboard(lang))


async def on_savings_callback(update: Update, context: ContextTypes.DEFAULT_TYPE):
    query = update.callback_query
    user_id = update.effective_user.id
    lang = lang_of(user_id, context)
    answer = (query.data or "").split(":", 1)[1]

    state = db.CARD_BOR if answer == "bor" else db.CARD_YOQ
    db.set_savings_card(user_id, state)
    await query.answer()
    await query.edit_message_text(
        i18n.t(lang, "savings_card_done" if state == db.CARD_BOR
               else "savings_card_later"),
        parse_mode=ParseMode.HTML)


def _pct(rate: float) -> str:
    """0.10 -> "10", 0.125 -> "12.5". Matnlarda foiz shu ko'rinishda."""
    value = rate * 100
    return f"{value:.0f}" if abs(value - round(value)) < 0.05 else f"{value:.1f}"


def _goal_bar(share: float, width: int = 12) -> str:
    filled = max(0, min(width, round(share * width)))
    return "█" * filled + "░" * (width - filled)


def _goal_block(user_id: int, lang: str, goal: dict | None = None,
                with_forecast: bool | None = None) -> str:
    """Maqsad qatori (progress, bashorat, muddat). Maqsad bo'lmasa bo'sh."""
    goal = goal or goals.primary(user_id)
    if not goal:
        return ""
    if with_forecast is None:
        with_forecast = tiers.allows(db.access_status(user_id), "goals_forecast")
    share = min(1.0, goal["saved"] / goal["amount"]) if goal["amount"] > 0 else 0
    lines = [i18n.t(lang, "goal_line",
                    star="⭐ " if goal.get("primary") else "",
                    name=reports.esc(goal["name"]), percent=goal["percent"],
                    bar=_goal_bar(share),
                    saved=reports.fmt_money(goal["saved"], "som"),
                    amount=reports.fmt_money(goal["amount"], "som"))]
    if goal["left"] <= 0:
        lines.append(i18n.t(lang, "goal_done_line"))
        return "\n".join(lines)
    if not with_forecast:
        lines.append(i18n.t(lang, "goal_forecast_locked"))
        return "\n".join(lines)
    fc = goals.forecast(user_id, goal)
    if fc["pace"] is None:
        lines.append(i18n.t(lang, "goal_no_pace"))
    elif fc["eta"] is None:
        lines.append(i18n.t(lang, "goal_slow"))
    else:
        lines.append(i18n.t(lang, "goal_eta", when=goals.month_year(fc["eta"]),
                            pace=reports.fmt_money(fc["pace"], "som")))
    if fc["need_monthly"]:
        lines.append(i18n.t(lang, "goal_need",
                            deadline=goals.month_year(date.fromisoformat(goal["deadline"])),
                            need=reports.fmt_money(fc["need_monthly"], "som")))
    return "\n".join(lines)


async def offer_savings_split(context: ContextTypes.DEFAULT_TYPE, user_id: int,
                              message, items: list[dict]) -> None:
    """Kirim yozilganda bir ulushni jamg'armaga ajratishni taklif qiladi.

    Kitobning mag'zi «avval o'zingga to'la». Pul kelgan ON eng kuchli
    payt: odam uni hali sarflamagan.

    Bepul darajada — standart foiz (config.SAVINGS_RATE). PRO'da — odam
    o'zi tanlagan foiz (/foiz) va o'tkazma asosiy maqsadga bog'lanadi.

    Taklif shu oyda ulushni allaqachon jamg'argan odamga ko'rsatilmaydi —
    bajarilgan ishni qayta so'rash eslatmani shovqinga aylantiradi.
    """
    income = sum(float(i["summa"]) for i in items
                 if i["turi"] == config.KIND_KIRIM and i["valyuta"] == "som")
    if income <= 0:
        return

    now = datetime.now(config.TZ).date()
    first = now.replace(day=1)
    try:
        month_income = await asyncio.to_thread(
            db.income_in_period, user_id, first, now)
        month_saved = await asyncio.to_thread(
            db.savings_in_period, user_id, first, now)
    except Exception:
        return
    pro = tiers.allows(db.access_status(user_id), "savings_auto")
    rate = (await asyncio.to_thread(db.savings_rate, user_id)
            if pro else config.SAVINGS_RATE)
    if month_income > 0 and month_saved >= month_income * rate:
        return                             # bu oy qoida allaqachon bajarilgan

    ten = round(income * rate)
    if ten < 1000:
        return                             # arzimas summa uchun bezovta qilmaymiz

    lang = lang_of(user_id, context)
    goal = goals.primary(user_id) if pro else None
    _savings_offer.set(user_id, {"amount": ten,
                                 "goal_id": goal["id"] if goal else None})
    money = reports.fmt_money(ten, "som")
    tail = (i18n.t(lang, "savings_goal_tail", name=reports.esc(goal["name"]))
            if goal else "")
    await message.reply_text(
        i18n.t(lang, "savings_nudge_now", pct=_pct(rate),
               income=reports.fmt_money(income, "som"), ten=money) + tail,
        parse_mode=ParseMode.HTML,
        reply_markup=InlineKeyboardMarkup([[InlineKeyboardButton(
            i18n.t(lang, "savings_nudge_button", ten=money),
            callback_data="jamqoy")]]))


async def after_savings_entry(context: ContextTypes.DEFAULT_TYPE, user_id: int,
                              message) -> None:
    """Jamg'arma yozuvidan keyin: maqsad progressi, seriya va yetib borilgani."""
    lang = lang_of(user_id, context)
    active = await asyncio.to_thread(goals.list_goals, user_id)

    # Maqsadga yangi yetilgan bo'lsa — bir marta tabriklaymiz.
    for g in active:
        if g["left"] <= 0 and not g.get("reached_at"):
            await asyncio.to_thread(goals.mark_reached, user_id, g["id"])
            await message.reply_text(
                i18n.t(lang, "goal_reached", amount=reports.fmt_money(g["amount"], "som"),
                       note=f" — {reports.esc(g['name'])}",
                       balance=reports.fmt_money(g["saved"], "som")),
                parse_mode=ParseMode.HTML)
            return

    parts = []
    if active:
        parts.append(await asyncio.to_thread(_goal_block, user_id, lang, active[0]))
    streak = await asyncio.to_thread(db.savings_streak, user_id)
    if streak >= 2:
        parts.append(i18n.t(lang, "savings_streak", n=streak,
                            pct=_pct(await asyncio.to_thread(
                                db.savings_rate, user_id))).strip())
    if parts:
        await message.reply_text("\n\n".join(parts), parse_mode=ParseMode.HTML)


async def on_savings_add_callback(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """«Ha, o'tkazdim» tugmasi — jamg'arma yozuvini o'zi qo'shadi va
    (PRO'da) asosiy maqsadga bog'laydi."""
    query = update.callback_query
    user_id = update.effective_user.id
    lang = lang_of(user_id, context)

    offer = _savings_offer.pop(user_id)
    if not offer:
        await query.answer("Taklif eskirdi. Summani o'zingiz yozing.",
                           show_alert=True)
        return
    # Eski (bot qayta ishga tushmasdan oldingi) taklif — faqat summa edi.
    if not isinstance(offer, dict):
        offer = {"amount": offer, "goal_id": None}
    amount = offer["amount"]

    await asyncio.to_thread(
        lambda: db.add_transaction(
            user_id, config.KIND_JAMGARMA, float(amount), "jamg'arma", "",
            raw_text="avval o'zingizga to'lang", currency="som",
            goal_id=offer["goal_id"]))
    balance = await asyncio.to_thread(db.savings_balance, user_id)
    streak = await asyncio.to_thread(db.savings_streak, user_id)

    await query.answer()
    await query.edit_message_text(
        i18n.t(lang, "savings_nudge_saved",
               amount=reports.fmt_money(amount, "som"),
               balance=reports.fmt_money(balance, "som"),
               streak=i18n.t(lang, "savings_streak", n=streak,
                             pct=_pct(await asyncio.to_thread(
                                 db.savings_rate, user_id)))
               if streak >= 2 else ""),
        parse_mode=ParseMode.HTML)
    # Maqsad progressi yangilandi — darrov ko'rsatamiz.
    if offer["goal_id"]:
        goal = await asyncio.to_thread(goals.get, user_id, offer["goal_id"])
        if goal:
            await query.message.reply_text(
                await asyncio.to_thread(_goal_block, user_id, lang, goal),
                parse_mode=ParseMode.HTML)


# --------------------------------------------------------------------------- #
# Maqsadlar (3.1)
# --------------------------------------------------------------------------- #

def goals_text(user_id: int, lang: str) -> str:
    active = goals.list_goals(user_id)
    if not active:
        return i18n.t(lang, "goals_title") + "\n\n" + i18n.t(lang, "goals_empty")
    forecast = tiers.allows(db.access_status(user_id), "goals_forecast")
    blocks = [_goal_block(user_id, lang, g, forecast) for g in active]
    return i18n.t(lang, "goals_title") + "\n\n" + "\n\n".join(blocks)


def goals_keyboard(user_id: int, lang: str) -> InlineKeyboardMarkup:
    rows = [[InlineKeyboardButton(f"⚙️ {g['name'][:30]}", callback_data=f"gl:{g['id']}")]
            for g in goals.list_goals(user_id)]
    rows.append([InlineKeyboardButton(i18n.t(lang, "goal_new_btn"),
                                      callback_data="gl:new")])
    return InlineKeyboardMarkup(rows)


@private_only
async def cmd_goals(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """🎯 Maqsadlar — barcha maqsadlar progressi va bashorati bilan."""
    user_id = update.effective_user.id
    lang = lang_of(user_id, context)
    await update.effective_message.reply_text(
        goals_text(user_id, lang), parse_mode=ParseMode.HTML,
        reply_markup=goals_keyboard(user_id, lang))


async def create_goal_from_text(update: Update, context: ContextTypes.DEFAULT_TYPE,
                                text: str) -> None:
    """«Uy uchun boshlang'ich to'lov 300 mln 2028-mart» -> maqsad."""
    user_id = update.effective_user.id
    lang = lang_of(user_id, context)
    msg = update.effective_message
    access = db.access_status(user_id)
    if goals.list_goals(user_id) and not tiers.allows(access, "goals_many"):
        await show_paywall(update, context, "goals")
        return
    parsed = goals.parse_goal_text(text, _parse_amount_uz)
    if not parsed:
        await msg.reply_text(i18n.t(lang, "goal_parse_fail"), parse_mode=ParseMode.HTML)
        return
    goal_id = goals.create(user_id, parsed["name"], parsed["amount"], parsed["deadline"])
    deadline = (f" · {goals.month_year(parsed['deadline'])}"
                if parsed["deadline"] else "")
    goal = goals.get(user_id, goal_id)
    await msg.reply_text(
        i18n.t(lang, "goal_created", name=reports.esc(parsed["name"]),
               amount=reports.fmt_money(parsed["amount"], "som"), deadline=deadline)
        + "\n\n" + _goal_block(user_id, lang, goal),
        parse_mode=ParseMode.HTML)


@private_only
async def cmd_goal(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """/maqsad <nom summa [muddat]> — yangi maqsad; argumentsiz — ro'yxat."""
    raw = (update.effective_message.text or "").split(maxsplit=1)
    text = raw[1].strip() if len(raw) > 1 else ""
    if not text or text.lower() in ("o'chir", "ochir", "удалить", "0"):
        await cmd_goals(update, context)
        return
    await create_goal_from_text(update, context, text)


async def on_goal_callback(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """gl:<id> — maqsad tafsiloti; gl:new — yangi; glp:/gla: — asosiy/yopish."""
    query = update.callback_query
    user_id = update.effective_user.id
    lang = lang_of(user_id, context)
    prefix, _, arg = (query.data or "").partition(":")

    if prefix == "gl" and arg == "new":
        if goals.list_goals(user_id) and not tiers.allows(
                db.access_status(user_id), "goals_many"):
            await show_paywall(update, context, "goals")
            return
        context.user_data["await_goal"] = True
        await query.answer()
        await query.message.reply_text(i18n.t(lang, "goal_ask"), parse_mode=ParseMode.HTML)
        return
    if prefix == "gl" and arg == "list":
        await query.answer()
        await query.edit_message_text(goals_text(user_id, lang), parse_mode=ParseMode.HTML,
                                      reply_markup=goals_keyboard(user_id, lang))
        return

    goal = goals.get(user_id, int(arg)) if arg.isdigit() else None
    if not goal:
        await query.answer("Maqsad topilmadi", show_alert=True)
        return

    if prefix == "glp":
        goals.set_primary(user_id, goal["id"])
        await query.answer("⭐")
        await query.edit_message_text(
            i18n.t(lang, "goal_primary_set", name=reports.esc(goal["name"])),
            parse_mode=ParseMode.HTML)
        return
    if prefix == "gla":
        goals.archive(user_id, goal["id"])
        await query.answer("🗑")
        await query.edit_message_text(
            i18n.t(lang, "goal_archived", name=reports.esc(goal["name"])))
        return

    rows = []
    if not goal["primary"]:
        rows.append([InlineKeyboardButton(i18n.t(lang, "goal_primary_btn"),
                                          callback_data=f"glp:{goal['id']}")])
    rows.append([InlineKeyboardButton(i18n.t(lang, "goal_archive_btn"),
                                      callback_data=f"gla:{goal['id']}")])
    rows.append([InlineKeyboardButton(i18n.t(lang, "goal_back_btn"),
                                      callback_data="gl:list")])
    await query.answer()
    await query.edit_message_text(_goal_block(user_id, lang, goal),
                                  parse_mode=ParseMode.HTML,
                                  reply_markup=InlineKeyboardMarkup(rows))


# --------------------------------------------------------------------------- #
# «Avval o'zingizga to'lang» foizi (3.2)
# --------------------------------------------------------------------------- #

RATE_CHOICES = (10, 15, 20, 30)


def _rate_keyboard(current: float) -> InlineKeyboardMarkup:
    pct = round(current * 100)
    return InlineKeyboardMarkup([[
        InlineKeyboardButton(f"{'✅ ' if pct == n else ''}{n}%", callback_data=f"rate:{n}")
        for n in RATE_CHOICES]])


def _rate_text(user_id: int, lang: str) -> str:
    goal = goals.primary(user_id)
    part = i18n.t(lang, "rate_goal_part", name=reports.esc(goal["name"])) if goal else ""
    return i18n.t(lang, "rate_pick", pct=_pct(db.savings_rate(user_id)), goal=part)


@private_only
async def cmd_savings_rate(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """/foiz — «avval o'zingizga to'lang» ulushi: 10/15/20/30 % tugmalari
    yoki /foiz 12 (1–90 %). PRO imkoniyati."""
    user_id = update.effective_user.id
    lang = lang_of(user_id, context)
    msg = update.effective_message
    if not tiers.allows(db.access_status(user_id), "savings_auto"):
        await show_paywall(update, context, "savings_auto")
        return
    args = context.args or []

    if not args:
        await msg.reply_text(_rate_text(user_id, lang), parse_mode=ParseMode.HTML,
                             reply_markup=_rate_keyboard(db.savings_rate(user_id)))
        return

    raw = args[0].replace("%", "").replace(",", ".").strip()
    try:
        value = float(raw)
    except ValueError:
        await msg.reply_text(i18n.t(lang, "rate_bad"), parse_mode=ParseMode.HTML)
        return

    # Yuqori chegara ataylab 90: 100 % jamg'arish real emas va bunday
    # qiymat deyarli har doim xato kiritishdan chiqadi.
    if not 1 <= value <= 90:
        await msg.reply_text(i18n.t(lang, "rate_bad"), parse_mode=ParseMode.HTML)
        return
    await msg.reply_text(_apply_rate(user_id, lang, value / 100),
                         parse_mode=ParseMode.HTML)


def _apply_rate(user_id: int, lang: str, rate: float) -> str:
    """Foizni saqlaydi va uni odamning O'Z raqamida tushuntiradi."""
    db.set_savings_rate(user_id, rate)
    example = ""
    now = datetime.now(config.TZ).date()
    income = db.income_in_period(user_id, now.replace(day=1), now)
    if income <= 0:
        prev_end = now.replace(day=1) - timedelta(days=1)
        income = db.income_in_period(user_id, prev_end.replace(day=1), prev_end)
    if income > 0:
        example = i18n.t(lang, "rate_example",
                         amount=reports.fmt_money(income * rate, "som"))
    return i18n.t(lang, "rate_set", pct=_pct(rate), example=example)


async def on_rate_callback(update: Update, context: ContextTypes.DEFAULT_TYPE):
    query = update.callback_query
    user_id = update.effective_user.id
    lang = lang_of(user_id, context)
    if not tiers.allows(db.access_status(user_id), "savings_auto"):
        await show_paywall(update, context, "savings_auto")
        return
    value = int((query.data or "rate:10").split(":")[1])
    if value not in RATE_CHOICES:
        await query.answer()
        return
    await query.answer(f"{value}%")
    await query.edit_message_text(_apply_rate(user_id, lang, value / 100),
                                  parse_mode=ParseMode.HTML)


# --------------------------------------------------------------------------- #
# Qarz muddati va eslatmalari (3.3)
# --------------------------------------------------------------------------- #

DUE_CHOICES = (1, 7, 14, 30, 0)


async def on_due_callback(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """due:<tx> — muddat tanlash; dueset:<tx>:<kun> — saqlash (0 — muddatsiz)."""
    query = update.callback_query
    user_id = update.effective_user.id
    lang = lang_of(user_id, context)
    if not tiers.allows(db.access_status(user_id), "debt_reminders"):
        await show_paywall(update, context, "debt_reminders")
        return
    parts = (query.data or "").split(":")
    tx_id = int(parts[1])
    row = db.get_transaction(user_id, tx_id)
    if not row or row["kind"] not in config.DEBT_OPEN_KINDS:
        await query.answer("Qarz topilmadi", show_alert=True)
        return

    if parts[0] == "due":
        await query.answer()
        await query.edit_message_reply_markup(InlineKeyboardMarkup(
            [[InlineKeyboardButton(i18n.t(lang, f"due_{d}"),
                                   callback_data=f"dueset:{tx_id}:{d}")
              for d in DUE_CHOICES[:3]],
             [InlineKeyboardButton(i18n.t(lang, f"due_{d}"),
                                   callback_data=f"dueset:{tx_id}:{d}")
              for d in DUE_CHOICES[3:]]]))
        return

    days = int(parts[2])
    due = (tiers.today() + timedelta(days=days)) if days else None
    db.set_due(user_id, tx_id, due)
    await query.answer("📅")
    text = (i18n.t(lang, "due_set", date=reports.fmt_date(due.isoformat()))
            if due else i18n.t(lang, "due_cleared"))
    await query.edit_message_text(
        reports.transaction_line(db.get_transaction(user_id, tx_id)) + "\n\n" + text,
        parse_mode=ParseMode.HTML,
        reply_markup=entry_keyboard([tx_id], row["kind"]))


@private_only
async def cmd_net_worth(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """/holatim — sof qiymat: jamg'arma + qarzdorlar − qarzim."""
    user_id = update.effective_user.id
    lang = lang_of(user_id, context)
    w = db.net_worth(user_id)
    await update.effective_message.reply_text(
        i18n.t(lang, "net_worth",
               savings=reports.fmt_money(w["savings"], "som"),
               owed=reports.fmt_money(w["owed_to_me"], "som"),
               iowe=reports.fmt_money(w["i_owe"], "som"),
               icon="🟢" if w["total"] >= 0 else "🔴",
               total=reports.fmt_money(w["total"], "som")),
        parse_mode=ParseMode.HTML)


@private_only
async def cmd_debt_plan(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """/reja — 70/20/10 bo'yicha qarzdan chiqish rejasi."""
    user_id = update.effective_user.id
    lang = lang_of(user_id, context)
    msg = update.effective_message

    plan = db.debt_plan(user_id)
    if plan is None:
        owed = db.net_worth(user_id)["i_owe"]
        if owed <= 0:
            await msg.reply_text(
                i18n.t(lang, "debt_plan_none",
                       pct=_pct(db.savings_rate(user_id))),
                                 parse_mode=ParseMode.HTML)
        else:
            await msg.reply_text(
                i18n.t(lang, "debt_plan_no_income",
                       debt=reports.fmt_money(owed, "som")),
                parse_mode=ParseMode.HTML)
        return

    await msg.reply_text(
        i18n.t(lang, "debt_plan",
               debt=reports.fmt_money(plan["debt"], "som"),
               income=reports.fmt_money(plan["income"], "som"),
               monthly=reports.fmt_money(plan["monthly"], "som"),
               months=plan["months"]),
        parse_mode=ParseMode.HTML)


async def check_budget_alerts(context: ContextTypes.DEFAULT_TYPE, user_id: int,
                              categories: set[str]) -> None:
    """Yozuv qo'shilgandan keyin byudjet oshganini tekshiradi.

    Har daraja (80% va 100%) oyiga bir marta ogohlantiradi — aks holda
    har yozuvda xabar kelib bezdirardi.
    """
    # Byudjet ogohlantirishi — PRO. Sinov tugaganda qo'yilgan byudjetlar
    # o'chirilmaydi, faqat jim turadi; obuna bo'lsa yana ishlaydi.
    if not tiers.allows(db.access_status(user_id), "budget"):
        return
    month = datetime.now(config.TZ).strftime("%Y-%m")
    for r in db.budget_status(user_id):
        if r["category"] not in categories:
            continue
        level = 100 if r["percent"] >= 100 else (80 if r["percent"] >= 80 else 0)
        if not level:
            continue
        tag = f"{month}:{level}"
        already = r["notified"]
        if already == tag or (already.startswith(month) and
                              already.endswith(":100")):
            continue
        db.mark_budget_notified(user_id, r["category"], r["currency"], tag)
        if level == 100:
            text = (f"🔴 <b>{r['category']}</b> byudjeti oshib ketdi!\n\n"
                    f"Sarflandi: {reports.fmt_money(r['spent'], r['currency'])}\n"
                    f"Chegara: {reports.fmt_money(r['limit'], r['currency'])}\n"
                    f"Oshgan: {reports.fmt_money(-r['left'], r['currency'])}")
        else:
            text = (f"🟡 <b>{r['category']}</b> byudjetining "
                    f"{r['percent']:.0f}% i sarflandi.\n\n"
                    f"Qoldi: {reports.fmt_money(r['left'], r['currency'])}")
        try:
            await context.bot.send_message(user_id, text, parse_mode=ParseMode.HTML)
        except Exception:
            log.info("Byudjet ogohlantirishi yuborilmadi: %s", user_id)


# --------------------------------------------------------------------------- #
# Eslatma sozlamasi
# --------------------------------------------------------------------------- #

@private_only
async def cmd_reminder(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """/eslatma 21 — har kuni soat 21:00 da; /eslatma o'chir — bekor."""
    user_id = update.effective_user.id
    args = context.args or []
    msg = update.effective_message

    lang = lang_of(user_id, context)

    if args:
        raw = args[0].lower()
        if raw in ("o'chir", "ochir", "yoq", "0", "выкл", "off"):
            db.set_reminder_hour(user_id, None)
            await msg.reply_text(i18n.t(lang, "reminder_off"))
            return
        digits = "".join(ch for ch in raw if ch.isdigit())
        if digits and 0 <= int(digits) <= 23:
            hour = int(digits)
            db.set_reminder_hour(user_id, hour)
            await msg.reply_text(i18n.t(lang, "reminder_on", hour=f"{hour:02d}"),
                                 parse_mode=ParseMode.HTML)
            return
        await msg.reply_text(i18n.t(lang, "reminder_bad_hour"))
        return

    current = db.get_reminder_hour(user_id)
    # Bepul darajada eslatma standart holatda yoqilgan (o'zi o'chirmagan bo'lsa).
    if (current is None and not db.reminder_opted_out(user_id)
            and not tiers.is_pro(db.access_status(user_id))):
        await msg.reply_text(
            i18n.t(lang, "reminder_default_on", hour=f"{config.DEFAULT_REMINDER_HOUR:02d}"),
            parse_mode=ParseMode.HTML)
        return
    if current is None:
        await msg.reply_text(
            i18n.t(lang, "reminder_intro"),
            parse_mode=ParseMode.HTML,
            reply_markup=InlineKeyboardMarkup([[
                InlineKeyboardButton("🔔 20:00", callback_data="rem:20"),
                InlineKeyboardButton("🔔 21:00", callback_data="rem:21"),
                InlineKeyboardButton("🔔 22:00", callback_data="rem:22"),
            ]]))
    else:
        await msg.reply_text(i18n.t(lang, "reminder_on", hour=f"{current:02d}"),
                             parse_mode=ParseMode.HTML)


async def on_reminder_callback(update: Update, context: ContextTypes.DEFAULT_TYPE):
    query = update.callback_query
    arg = (query.data or "rem:21").split(":")[1]
    if arg == "off":
        # Bepul eslatma ostidagi «🔕 O'chirish» — bir bosishda.
        db.set_reminder_hour(update.effective_user.id, None)
        await query.answer("🔕")
        await query.edit_message_text(
            i18n.t(lang_of(update.effective_user.id, context), "reminder_off"))
        return
    hour = int(arg)
    db.set_reminder_hour(update.effective_user.id, hour)
    await query.answer("🔔")
    await query.edit_message_text(
        i18n.t(lang_of(update.effective_user.id, context), "reminder_on",
               hour=f"{hour:02d}"),
        parse_mode=ParseMode.HTML)


async def cmd_panel(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """Egaga admin panel havolasini beradi."""
    user = update.effective_user
    if user is None or user.id not in config.OWNER_IDS:
        return
    url = config.ADMIN_PANEL_URL
    if not url:
        await update.effective_message.reply_text(
            "ADMIN_PANEL_URL sozlanmagan (.env faylida).")
        return
    pending = db.pending_request_count()
    text = [f"🛠 <b>Admin boshqaruv paneli</b>\n\n{url}"]
    if pending:
        text.append(f"\n\n⏳ {pending} ta obuna so'rovi javob kutmoqda.")
    await update.effective_message.reply_text(
        "".join(text), parse_mode=ParseMode.HTML, disable_web_page_preview=True)


@owner_only
async def cmd_stats(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """/statistika — faollik, saqlanish, voronka va paywall'lar (faqat ega)."""
    data = await asyncio.to_thread(analytics.report)
    for chunk in _split_message(analytics.report_text(data)):
        await update.effective_message.reply_text(chunk, parse_mode=ParseMode.HTML)


@owner_only
async def cmd_sim_mode(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """/oddiy_rejim on|off — ega o'zini obunasiz, sinovi tugagan
    foydalanuvchidek ko'radi: limitlar, paywall, tariflar va /holat oddiy
    odamdagidek. Faqat ko'rinish: to'lov tasdiqlash mantig'iga tegilmaydi.
    """
    user_id = update.effective_user.id
    lang = lang_of(user_id, context)
    arg = (context.args or [""])[0].lower()
    if arg in ("on", "yoq", "ha", "1"):
        db.set_sim_free(user_id, True)
        await update.effective_message.reply_text(i18n.t(lang, "sim_on"),
                                                  parse_mode=ParseMode.HTML)
    elif arg in ("off", "ochir", "yo'q", "0"):
        db.set_sim_free(user_id, False)
        await update.effective_message.reply_text(i18n.t(lang, "sim_off"))
    else:
        state = "on" if not db.is_privileged(user_id) else "off"
        await update.effective_message.reply_text(
            i18n.t(lang, "sim_usage", state=state), parse_mode=ParseMode.HTML)


@private_only
async def cmd_status(update: Update, context: ContextTypes.DEFAULT_TYPE):
    user_id = update.effective_user.id
    access = context.user_data.get("access") or db.access_status(user_id)

    lang = lang_of(user_id, context)

    status = access["status"]
    if status == "owner":
        head = i18n.t(lang, "status_owner")
    elif status == "subscribed":
        head = i18n.t(lang, "status_sub", until=_fmt_dt(access["until"]),
                      days=access["days_left"])
    elif status == "trial":
        head = i18n.t(lang, "status_trial", until=_fmt_dt(access["until"]),
                      days=access["days_left"])
    else:
        head = i18n.t(lang, "status_free")

    lines = [head, ""]

    if status == "free":
        lines.append(i18n.t(
            lang, "status_free_limits",
            left=tiers.receipts_left(user_id, access),
            total=config.FREE_RECEIPTS_PER_MONTH,
            qa_left=max(0, config.FREE_QA_PER_DAY - db.count_today(user_id, "savol")),
            qa_total=config.FREE_QA_PER_DAY))
        lines += [i18n.t(lang, "status_free_hint"), ""]

    lines.append(i18n.t(lang, "status_rows", n=db.tx_count(user_id)))

    # Ega bo'lmaganlarga tariflar shu yerdan ham ochiladi — sinov davri
    # faol bo'lsa ham obuna sotib olish mumkin.
    kb = None
    if status in ("trial", "subscribed"):
        lines += ["", i18n.t(lang, "status_extend_hint")]
    if status != "owner":
        kb = plans_keyboard(lang)

    await update.effective_message.reply_text(
        "\n".join(lines), parse_mode=ParseMode.HTML, reply_markup=kb)


# Admin boshqaruvi bot ichidan OLIB TASHLANDI — hammasi alohida web
# panelda: https://tanga.niskandarov.uz
# Sabab: statistikani, foydalanuvchilarni va to'lovlarni chat oynasida
# boshqarish noqulay va xatoga moyil edi.


async def on_error(update: object, context: ContextTypes.DEFAULT_TYPE):
    log.exception("Handler xatoligi", exc_info=context.error)


# --------------------------------------------------------------------------- #
# Rejalashtirilgan vazifalar
# --------------------------------------------------------------------------- #

async def job_daily_reminder(context: ContextTypes.DEFAULT_TYPE) -> None:
    """Har soatda ishlaydi: shu soatdagi kunlik eslatma oluvchilarga.

    PRO — o'zi yoqqan bo'lsa kun xulosasi. Bepul — standart holatda
    yoqilgan qisqa eslatma, faqat o'sha kuni hali yozuv bo'lmasa va
    «🔕 O'chirish» tugmasi bilan (db.users_for_reminder, notify.free_policy).
    """
    hour = datetime.now(config.TZ).hour
    users = db.users_for_reminder(hour)
    if not users:
        return
    today = reports.today()
    sent = 0
    for item in users:
        user_id = item["user_id"]
        try:
            lang = lang_of(user_id)
            markup = None
            s = db.day_summary(user_id, today) if item["mode"] == "summary" else None
            if s and s["count"]:
                parts = []
                for cur, amount in s["chiqim"].items():
                    parts.append("−" + reports.fmt_money(amount, cur))
                for cur, amount in s["kirim"].items():
                    parts.append("+" + reports.fmt_money(amount, cur))
                text = i18n.t(lang, "daily_summary", n=s["count"],
                              parts=" · ".join(parts))
            else:
                text = i18n.t(lang, "daily_empty")
                if item["mode"] == "nudge":
                    markup = InlineKeyboardMarkup([[InlineKeyboardButton(
                        i18n.t(lang, "reminder_off_btn"), callback_data="rem:off")]])
            if await notify.send(context.bot, user_id, text,
                                 parse_mode=ParseMode.HTML, reply_markup=markup):
                sent += 1
        except Exception:
            log.info("Eslatma yuborilmadi: %s", user_id)
    log.info("Kunlik eslatma: %s ta yuborildi (soat %s)", sent, hour)


async def job_expiry_warning(context: ContextTypes.DEFAULT_TYPE) -> None:
    """Obunasi tugayotganlarni ogohlantiradi. Sinov muddatining o'z
    xabarlari bor — job_trial_notices."""
    rows = db.users_expiring((3, 1))
    if not rows:
        return
    sent = 0
    for r in rows:
        user_id = r["user_id"]
        try:
            lang = lang_of(user_id)
            head = (i18n.t(lang, "expiry_sub", days=r["days_left"])
                    if r["days_left"] > 0
                    else i18n.t(lang, "expiry_sub_today"))
            body = i18n.t(lang, "expiry_sub_body")
            if not await notify.send(
                    context.bot, user_id, f"{head}\n\n{body}",
                    parse_mode=ParseMode.HTML, reply_markup=plans_keyboard(lang)):
                continue
            db.mark_warned(user_id, r["stage"])
            sent += 1
        except Exception:
            log.info("Ogohlantirish yuborilmadi: %s", user_id)
    log.info("Muddat ogohlantirishi: %s ta yuborildi", sent)


def trial_summary_text(user_id: int, lang: str, days_left: int) -> str:
    """5-kun xabari: «PRO yana 2 kun faol. Shu vaqtgacha: X ta yozuv,
    Y ta chek, maqsadingizning Z%»."""
    counts = db.activity_counts(user_id)
    goal_part = ""
    goal = goals.primary(user_id)
    if goal:
        goal_part = i18n.t(lang, "trial_goal_part", pct=goal["percent"])
    return i18n.t(lang, "trial_day5", days=max(1, days_left),
                  entries=counts["entries"], receipts=counts["receipts"],
                  goal=goal_part)


def trial_ended_text(user_id: int, lang: str) -> str:
    """Sinov tugadi: nima qoladi va SHU odam uchun aniq nima qulflanadi."""
    locks = []
    counts = db.activity_counts(user_id)
    month_start = tiers.month_start()
    if counts["first_day"] and counts["first_day"] < month_start.isoformat():
        month = reports.UZ_MONTHS[month_start.month - 1]
        locks.append(i18n.t(lang, "lock_history", month=month))
    goal = goals.primary(user_id)
    if goal:
        locks.append(i18n.t(lang, "lock_goal", goal=reports.esc(goal["name"])))
    locks.append(i18n.t(lang, "lock_receipts", n=config.FREE_RECEIPTS_PER_MONTH))
    if db.list_budgets(user_id):
        locks.append(i18n.t(lang, "lock_budget"))
    return i18n.t(lang, "trial_ended", locks="\n".join(locks))


async def job_trial_notices(context: ContextTypes.DEFAULT_TYPE) -> None:
    """Teskari sinov xabarlari (4.4): 5-kun va sinov tugagan kun.

    Bu xabarlar joriy etilishidan oldin sinovi tugaganlar hech narsa
    olmaydi (db.trial_notices) — ularga yozish faqat /xabar_yubor orqali
    va ega tasdig'i bilan.
    """
    sent = 0
    for r in db.trial_notices():
        user_id = r["user_id"]
        try:
            lang = lang_of(user_id)
            if r["kind"] == "day5":
                text = trial_summary_text(user_id, lang, r["days_left"])
                if not await notify.send(context.bot, user_id, text,
                                         parse_mode=ParseMode.HTML,
                                         reply_markup=plans_keyboard(lang)):
                    continue
                db.mark_warned(user_id, db.TRIAL_STAGE_DAY5)
            else:
                text = trial_ended_text(user_id, lang) + "\n\n" + plans_text(lang=lang)
                if not await notify.send(context.bot, user_id, text,
                                         parse_mode=ParseMode.HTML,
                                         reply_markup=plans_keyboard(lang)):
                    continue
                db.mark_warned(user_id, db.TRIAL_STAGE_ENDED)
                db.log_event(user_id, "sinov_tugadi")
            sent += 1
        except Exception:
            log.info("Sinov xabari yuborilmadi: %s", user_id)
    if sent:
        log.info("Sinov xabarlari: %s ta yuborildi", sent)


def debt_reminder_text(debt: dict, lang: str, when_key: str) -> str:
    """«Akmal 200 ming qarzini ertaga qaytarishi kerak.» — qoldiq bilan."""
    person = reports.esc(debt["person"] or "Qarz")
    amount = reports.fmt_money(debt["remaining"], debt["currency"] or "som")
    key = "debt_due_them" if debt["kind"] == config.KIND_QARZ_BERDIM else "debt_due_me"
    return i18n.t(lang, key, person=person, amount=amount, when=i18n.t(lang, when_key))


async def job_debt_reminders(context: ContextTypes.DEFAULT_TYPE) -> None:
    """Qarz muddatidan bir kun oldin va o'sha kuni eslatma (3.3). PRO.

    Har bir qarz va bosqich uchun bir marta (hodisa bilan belgilanadi):
    bot qayta ishga tushsa ham takrorlanmaydi.
    """
    today_ = tiers.today()
    tomorrow = today_ + timedelta(days=1)
    sent = 0
    for debt in db.debts_due((today_, tomorrow)):
        user_id = debt["user_id"]
        stage = "today" if debt["due_on"] == today_.isoformat() else "tomorrow"
        tag = f"{debt['id']}:{stage}"
        try:
            if db.event_count_detail(user_id, "qarz_eslatma", tag):
                continue
            if not tiers.allows(db.access_status(user_id), "debt_reminders"):
                continue
            lang = lang_of(user_id)
            if not await notify.send(
                    context.bot, user_id, debt_reminder_text(debt, lang, f"when_{stage}"),
                    parse_mode=ParseMode.HTML):
                continue
            db.log_event(user_id, "qarz_eslatma", tag)
            sent += 1
        except Exception:
            log.info("Qarz eslatmasi yuborilmadi: %s", user_id)
    if sent:
        log.info("Qarz eslatmalari: %s ta yuborildi", sent)


def digest_text(user_id: int, lang: str, row: dict) -> str | None:
    """Haftalik xulosa matni. None — yuborilmaydi.

    PRO — to'liq (yozuvlar soni, zanjir, byudjet maslahati). Bepul —
    qisqa: jami chiqim, o'tgan hafta bilan farq, eng katta 3 kategoriya;
    oxirida PRO haqida bitta qator, oyiga ko'pi bilan bir marta.
    Bo'sh hafta: PRO ga yuborilmaydi; Bepulga — bitta qisqa eslatma
    (14 kundan keyin unga boradigan yagona xabar shu).
    """
    s = db.week_summary(user_id)
    free = row.get("tier") == "free"
    text = i18n.t(lang, "digest_head", start=s["start"].strftime("%d.%m"),
                  end=s["end"].strftime("%d.%m"))
    if not s["count"]:
        if not free:
            return None
        return text + i18n.t(lang, "digest_free_empty")

    if free:
        text += f"\n\n💸 <b>{reports.fmt_money(s['spent'])}</b>"
    else:
        text += i18n.t(lang, "digest_body", spent=reports.fmt_money(s["spent"]),
                       count=s["count"])
    if s["previous"] > 0:
        diff = (s["spent"] - s["previous"]) / s["previous"] * 100
        if diff <= -5:
            text += i18n.t(lang, "digest_less", pct=abs(round(diff)))
        elif diff >= 5:
            text += i18n.t(lang, "digest_more", pct=round(diff))
    if s["top"]:
        text += i18n.t(lang, "digest_top")
        for name, total, _ in s["top"][:3]:
            text += (f"\n• {reports.esc(config.category_label(name))} — "
                     f"{reports.fmt_money(total)}")

    if free:
        month = datetime.now(config.TZ).strftime("%Y-%m")
        if not db.event_count_detail(user_id, "digest_pro_hint", month):
            text += i18n.t(lang, "digest_pro_hint")
            db.log_event(user_id, "digest_pro_hint", month)
        return text

    if row["streak"] >= 3:
        text += i18n.t(lang, "digest_streak", n=row["streak"])
    if not db.list_budgets(user_id):
        text += i18n.t(lang, "digest_tip")
    return text


async def job_weekly_digest(context: ContextTypes.DEFAULT_TYPE) -> None:
    """Dushanba ertalab — o'tgan (tugagan) hafta xulosasi.

    Botni eslatadigan, lekin foydali xabar: reklama emas, o'z sonlaringiz.
    """
    sent = 0
    for row in db.users_for_digest():
        user_id = row["user_id"]
        try:
            lang = lang_of(user_id)
            text = digest_text(user_id, lang, row)
            if text and await notify.send(context.bot, user_id, text,
                                          parse_mode=ParseMode.HTML):
                sent += 1
        except Exception:
            log.info("Haftalik xulosa yuborilmadi: %s", user_id)
    log.info("Haftalik xulosa: %s ta yuborildi", sent)


async def job_winback(context: ContextTypes.DEFAULT_TYPE) -> None:
    """Bir hafta yozmaganlarga bitta eslatma — oyiga bir martadan ko'p emas."""
    rows = db.users_for_winback(config.WINBACK_DAYS)
    if not rows:
        return
    today = datetime.now(config.TZ).date()
    sent = 0
    for r in rows:
        try:
            lang = lang_of(r["user_id"])
            try:
                gap = (today - date.fromisoformat(r["last_tx"])).days
            except (TypeError, ValueError):
                gap = config.WINBACK_DAYS
            text = i18n.t(lang, "winback", days=gap)
            if r["streak"] >= 3:
                text += i18n.t(lang, "winback_best", n=r["streak"])
            if not await notify.send(context.bot, r["user_id"], text,
                                     parse_mode=ParseMode.HTML):
                continue
            db.mark_winback(r["user_id"])
            sent += 1
        except Exception:
            log.info("Qaytarish xabari yuborilmadi: %s", r["user_id"])
    log.info("Qaytarish xabari: %s ta yuborildi", sent)


def goal_month_free_text(goal: dict, lang: str) -> str:
    """Bepul foydalanuvchiga oy oxirida: maqsad progressi, bashoratsiz."""
    share = min(1.0, goal["saved"] / goal["amount"]) if goal["amount"] > 0 else 0
    return i18n.t(lang, "goal_month_free", name=reports.esc(goal["name"]),
                  percent=goal["percent"], bar=_goal_bar(share),
                  saved=reports.fmt_money(goal["saved"], "som"),
                  amount=reports.fmt_money(goal["amount"], "som"))


async def job_savings_monthly(context: ContextTypes.DEFAULT_TYPE) -> None:
    """Oyning OXIRGI kunida 18:00 da jamg'arma eslatmasi.

    Vazifa har kuni 18:00 da uyg'onadi va oxirgi kun emasligini ko'rsa
    darrov chiqib ketadi. Sababi: oyning oxirgi kuni 28, 29, 30 yoki 31
    bo'ladi — buni cron ifodasi bilan to'g'ri yozib bo'lmaydi.

    Matn har bir odamga MOSLAB yuboriladi: umumiy "jamg'aring" degan
    gap allaqachon jamg'arayotgan odam uchun shovqin, jamg'armagan odam
    uchun esa juda mavhum. Shuning uchun har kimga o'z raqami ko'rsatiladi.
    """
    today_ = datetime.now(config.TZ).date()
    tomorrow = today_ + timedelta(days=1)
    if tomorrow.month == today_.month:
        return                                  # hali oyning oxiri emas

    month = today_.strftime("%Y-%m")
    rows = db.users_for_savings_reminder()
    if not rows:
        return

    sent = 0
    for r in rows:
        user_id = r["user_id"]
        lang = r["lang"]
        income, saved = r["income"], r["saved"]
        balance = r["balance"]
        rate = r.get("rate") or config.SAVINGS_RATE
        target = income * rate

        if r.get("tier") == "free":
            # Bepul: faqat maqsad progressi, bashoratsiz. Maqsad bo'lmasa —
            # hech narsa (umumiy «jamg'aring» eslatmasi bepulga ketmaydi).
            try:
                goal = await asyncio.to_thread(goals.primary, user_id)
                if goal and await notify.send(
                        context.bot, user_id, goal_month_free_text(goal, lang),
                        parse_mode=ParseMode.HTML):
                    await asyncio.to_thread(db.mark_month_reminded, user_id, month)
                    sent += 1
            except Exception:
                log.info("Jamg'arma eslatmasi yuborilmadi: %s", user_id)
            continue

        goal = None
        if tiers.allows(db.access_status(user_id), "goals_forecast"):
            goal = await asyncio.to_thread(goals.primary, user_id)
        goal_line = ""
        if goal and saved > 0:
            goal_line = i18n.t(lang, "goal_month", name=reports.esc(goal["name"]),
                               left_pct=max(0, 100 - goal["percent"]))

        try:
            if r.get("met"):
                # Qoidani bajarganlarga eslatma emas — PRO'da maqsadi bo'lsa
                # qisqa oy xulosasi, aks holda hech narsa.
                if not goal_line:
                    continue
                text = i18n.t(lang, "goal_month_summary",
                              saved=reports.fmt_money(saved, "som"), goal=goal_line)
            elif income <= 0:
                text = i18n.t(lang, "savings_month_no_income",
                              pct=_pct(rate),
                              balance=reports.fmt_money(balance, "som"))
            elif saved <= 0:
                text = i18n.t(lang, "savings_month_none",
                              pct=_pct(rate),
                              income=reports.fmt_money(income, "som"),
                              ten=reports.fmt_money(target, "som"),
                              ten_plain=f"{int(target):,}".replace(",", " "))
            else:
                # 10 % ni allaqachon bajarganlar bu ro'yxatga umuman
                # tushmaydi (db.users_for_savings_reminder), shuning
                # uchun bu yerga faqat kam jamg'arganlar keladi.
                text = i18n.t(lang, "savings_month_low",
                              pct=_pct(rate),
                              income=reports.fmt_money(income, "som"),
                              saved=reports.fmt_money(saved, "som"),
                              percent=f"{saved / income * 100:.0f}",
                              balance=reports.fmt_money(balance, "som"),
                              gap=reports.fmt_money(target - saved, "som"))
            if not r.get("met"):
                text += goal_line

            # Kartasi hali so'ralmagan bo'lsa — shu xabarga tugma ilashtiramiz.
            markup = (_card_keyboard(lang)
                      if r["card_state"] == db.CARD_SORALMAGAN else None)
            if not await notify.send(context.bot, user_id, text,
                                     parse_mode=ParseMode.HTML, reply_markup=markup):
                continue
            if markup is not None:
                await asyncio.to_thread(db.mark_card_asked, user_id)
            await asyncio.to_thread(db.mark_month_reminded, user_id, month)
            sent += 1
        except Exception:
            log.info("Jamg'arma eslatmasi yuborilmadi: %s", user_id)
    log.info("Jamg'arma eslatmasi: %s ta yuborildi", sent)


async def job_erase_queue(context: ContextTypes.DEFAULT_TYPE) -> None:
    """Admin panel so'ragan shaxsiy yozuvlarni o'chiradi.

    Panel foydalanuvchini o'chirganda uning moliyaviy yozuvlariga
    yeta olmaydi — shaxsiy bazaning kaliti unda yo'q. Shu vazifa
    o'sha ishni bajaradi.
    """
    try:
        n = await asyncio.to_thread(db.drain_erase_queue)
    except Exception:
        log.warning("O'chirish navbatini bo'shatib bo'lmadi", exc_info=True)
        return
    if n:
        log.info("O'chirish navbati: %s ta foydalanuvchi yozuvlari o'chirildi", n)


def schedule_jobs(app: Application) -> None:
    """Vaqtga bog'liq vazifalarni ro'yxatga oladi."""
    jq = app.job_queue
    if jq is None:
        log.warning("JobQueue yo'q — eslatmalar ishlamaydi. "
                    "pip install 'python-telegram-bot[job-queue]'")
        return
    # Har soatning boshida: o'sha soatga eslatma buyurganlarga.
    jq.run_custom(job_daily_reminder,
                  job_kwargs={"trigger": "cron", "minute": 0, "timezone": config.TZ},
                  name="kunlik-eslatma")
    # Har kuni 10:00 da: muddati tugayotganlarga.
    jq.run_custom(job_expiry_warning,
                  job_kwargs={"trigger": "cron", "hour": 10, "minute": 0,
                              "timezone": config.TZ},
                  name="muddat-ogohlantirishi")
    # 09:00 da: qarz muddati eslatmalari (bir kun oldin va o'sha kuni).
    jq.run_custom(job_debt_reminders,
                  job_kwargs={"trigger": "cron", "hour": 9, "minute": 0,
                              "timezone": config.TZ},
                  name="qarz-eslatmasi")
    # 10:05 da: sinov muddati xabarlari (5-kun va tugagan kun).
    jq.run_custom(job_trial_notices,
                  job_kwargs={"trigger": "cron", "hour": 10, "minute": 5,
                              "timezone": config.TZ},
                  name="sinov-xabarlari")
    # Kursni ertalab yangilaymiz — kun davomida yozuvlar tarmoqqa
    # chiqmasdan, bazadagi kurs bilan hisoblanadi.
    jq.run_custom(job_refresh_rates,
                  job_kwargs={"trigger": "cron", "hour": 8, "minute": 5,
                              "timezone": config.TZ},
                  name="kurs-yangilash")
    jq.run_once(job_refresh_rates, when=5, name="kurs-boshlangich")
    # Dushanba ertalab — o'tgan hafta xulosasi.
    jq.run_custom(job_weekly_digest,
                  job_kwargs={"trigger": "cron", "day_of_week": "mon",
                              "hour": 9, "minute": 30, "timezone": config.TZ},
                  name="haftalik-xulosa")
    # Har kuni tushda — bir hafta yozmaganlarga bitta eslatma.
    jq.run_custom(job_winback,
                  job_kwargs={"trigger": "cron", "hour": 12, "minute": 0,
                              "timezone": config.TZ},
                  name="qaytarish")
    # Admin panel so'ragan o'chirishlar. Panelda shaxsiy bazaning kaliti
    # yo'q, shuning uchun yozuvlarni faqat bot o'chira oladi. Ishga
    # tushishda darrov, keyin har 10 daqiqada — o'chirish so'rovi uzoq
    # kutib turmasin.
    jq.run_once(job_erase_queue, when=10, name="ochirish-boshlangich")
    jq.run_repeating(job_erase_queue, interval=600, first=600,
                     name="ochirish-navbati")
    # Jamg'arma eslatmasi — oyning OXIRGI kuni 18:00 da. Har kuni 18:00
    # da uyg'onadi va oxirgi kun emasligini ko'rsa darrov chiqadi: oyning
    # oxirgi kuni 28/29/30/31 bo'lgani uchun cron bilan yozib bo'lmaydi.
    jq.run_custom(job_savings_monthly,
                  job_kwargs={"trigger": "cron", "hour": 18, "minute": 0,
                              "timezone": config.TZ},
                  name="jamgarma-eslatmasi")
    log.info("Rejalashtirilgan vazifalar yoqildi: eslatma (har soat), "
             "muddat ogohlantirishi (10:00), haftalik xulosa (dushanba 9:30), "
             "qaytarish (12:00), o'chirish navbati (har 10 daqiqa), "
             "jamg'arma eslatmasi (oy oxiri 18:00)")


# --------------------------------------------------------------------------- #
# Ishga tushirish
# --------------------------------------------------------------------------- #

# Buyruqlar bo'limlar bo'yicha: (belgi, bo'lim nomi, [(buyruq, tavsif)]).
#
# Telegram menyusi guruhlashni qo'llab-quvvatlamaydi — hamma buyruq
# bitta ro'yxatda ko'rinadi. Shuning uchun tartib va tavsif oldidagi
# belgi guruhning o'rnini bosadi: bir xil belgili buyruqlar yonma-yon
# turadi va foydalanuvchi qaysi buyruq nimaga tegishligini ko'radi.
COMMAND_SECTIONS = [
    ("\U0001F4DD", "Yozish", [
        ("chek", "Uzun chekni qismlab yuborish"),
        ("ochir", "Yozuvni o'chirish: /ochir 12"),
        ("oxirgi", "Oxirgi yozuvlar"),
    ]),
    ("\U0001F4CA", "Hisobotlar", [
        ("bugun", "Bugungi hisobot"),
        ("kecha", "Kechagi hisobot"),
        ("hafta", "Shu haftalik hisobot"),
        ("oy", "Shu oylik hisobot"),
        ("otganoy", "O'tgan oylik hisobot"),
        ("yil", "Yillik hisobot"),
        ("csv", "Barcha yozuvlarni fayl qilib olish"),
    ]),
    ("\U0001F3E6", "Jamg'arma", [
        ("jamgarma", "Qoldiq va jamg'arma holati"),
        ("foiz", "Jamg'arma foizini belgilash: /foiz 10"),
        ("maqsadlar", "Maqsadlar va bashorat"),
        ("maqsad", "Yangi maqsad: /maqsad Uy 300 mln 2028-mart"),
        ("holatim", "Sof qiymat: jamg'arma va qarzlar"),
    ]),
    ("\U0001F91D", "Qarzlar", [
        ("qarz", "Ochiq qarzlar ro'yxati"),
        ("yopdim", "Qarzni yopish: /yopdim 12"),
        ("reja", "Qarzdan chiqish rejasi"),
    ]),
    ("\U0001F4B0", "Rejalashtirish", [
        ("byudjet", "Kategoriyaga oylik chegara"),
        ("eslatma", "Kunlik eslatmani sozlash"),
        ("kurs", "Bugungi dollar kursi"),
    ]),
    ("\U0001F48E", "Obuna", [
        ("obuna", "Tariflar va to'lov"),
        ("holat", "Obuna holati va bugungi limitlar"),
        ("taklif", "Do'st taklif qiling — ikkalangizga +7 kun PRO"),
    ]),
    ("\u2699\ufe0f", "Sozlamalar", [
        ("buyruqlar", "Barcha buyruqlar bo'limlar bilan"),
        ("qollanma", "To'liq foydalanish yo'riqnomasi"),
        ("til", "Til / \u042f\u0437\u044b\u043a"),
        ("maxfiylik", "Maxfiylik siyosati"),
        ("shartlar", "Xizmat shartlari"),
        ("ochirish", "Hisobni butunlay o'chirish"),
    ]),
]

# Telegram menyusi uchun yassi ro'yxat. /start eng boshida turadi,
# qolganlari bo'lim tartibida va tavsifi bo'lim belgisi bilan.
BOT_COMMANDS = [("start", "Boshlash va yordam")] + [
    (name, f"{icon} {desc}")
    for icon, _, items in COMMAND_SECTIONS
    for name, desc in items
]

# Profil matnlari (tavsif, qisqa tavsif) — profile_texts.py da, har bir
# til uchun; _post_init ularni o'rnatadi.

# Faqat bot egasining «/» menyusida ko'rinadigan buyruqlar.
# Admin boshqaruvi web panelga ko'chirildi — bu yerda faqat /panel qoldi.
OWNER_COMMANDS = BOT_COMMANDS + [
    ("id", "Telegram ID'ingiz"),
    ("panel", "Admin boshqaruv paneli"),
    ("oddiy_rejim", "Oddiy foydalanuvchi sifatida sinash: on/off"),
    ("xabar_yubor", "Foydalanuvchilarga xabar (ko'rish va tasdiq bilan)"),
    ("statistika", "Faollik, saqlanish, voronka, paywall"),
]


async def _post_init(app: Application) -> None:
    """Telegramdagi «/» menyusini to'ldiradi — buyruqlarni eslash shart emas."""
    from telegram import (
        BotCommand,
        BotCommandScopeAllPrivateChats,
        BotCommandScopeChat,
        BotCommandScopeDefault,
    )

    # Nega bitta emas, ikkita ko'lam (scope) va til tozalash:
    #
    # Telegram «/» ro'yxatini ko'lam bo'yicha tanlaydi va eng aniqrog'i
    # yutadi:  chat  >  all_private_chats  >  default. Har birining
    # ustiga yana foydalanuvchi ILOVASINING tili qo'yiladi: ruscha
    # Telegram avval "ru" ro'yxatini qidiradi, topmasa umumiysini oladi.
    #
    # Muhimi: bir marta yozilgan ro'yxat Telegram serverida QOLADI —
    # kod o'zgargani bilan o'chmaydi. Shuning uchun eski (yoki bo'sh)
    # all_private_chats ro'yxati yangi default ro'yxatni soya qilib
    # qo'yishi mumkin. Ega buni sezmaydi: unda o'z chat ko'lami bor va
    # u hammasidan ustun turadi. Natijada buyruqlar faqat egada
    # ko'rinadi, oddiy foydalanuvchida esa yo'q — aynan shu holat
    # jonli botda yuz berdi.
    #
    # Yechim: bir xil ro'yxatni ikkala ko'lamga ham yozamiz va tilga
    # bog'langan eski nusxalarni o'chiramiz, toki umumiy ro'yxat
    # hammaga yetib borsin.
    commands = [BotCommand(c, d) for c, d in BOT_COMMANDS]
    for scope in (BotCommandScopeDefault(), BotCommandScopeAllPrivateChats()):
        await app.bot.set_my_commands(commands, scope=scope)
        for code in ("en", "ru", "uz"):
            try:
                await app.bot.delete_my_commands(scope=scope, language_code=code)
            except Exception as exc:
                log.warning("Eski «%s» ro'yxatini o'chirib bo'lmadi: %s", code, exc)
    log.info("«/» menyusi hammaga o'rnatildi: %d ta buyruq", len(commands))

    # Profil matnlari — har bir til uchun (standart, «uz», «ru»). Telegram
    # foydalanuvchiga avval o'z tilidagisini ko'rsatadi, shuning uchun
    # faqat standartni yangilash yetmaydi. Faqat o'zgargani yuboriladi.
    for code in profile_texts.LANGS:
        try:
            short = profile_texts.SHORT[code]
            desc = profile_texts.DESCRIPTION[code]
            if (await app.bot.get_my_description(language_code=code)).description != desc:
                await app.bot.set_my_description(desc, language_code=code)
                log.info("Bot tavsifi yangilandi [%s]", code or "standart")
            current = (await app.bot.get_my_short_description(
                language_code=code)).short_description
            if current != short:
                await app.bot.set_my_short_description(short, language_code=code)
                log.info("Bot qisqa tavsifi yangilandi [%s]", code or "standart")
        except Exception as exc:
            log.warning("Bot tavsifini o'rnatib bo'lmadi [%s]: %s", code, exc)

    # Egaga qo'shimcha buyruqlar ko'rinadi (/id va admin buyruqlari).
    owner_cmds = [BotCommand(c, d) for c, d in OWNER_COMMANDS]
    for owner in config.OWNER_IDS:
        try:
            await app.bot.set_my_commands(owner_cmds,
                                          scope=BotCommandScopeChat(chat_id=owner))
        except Exception as exc:
            log.warning("Ega buyruqlarini o'rnatib bo'lmadi (%s): %s", owner, exc)

    # Pastki chap burchakdagi doimiy menyu tugmasi — Mini App'ni bir bosishda ochadi.
    if config.WEBAPP_URL:
        await app.bot.set_chat_menu_button(
            menu_button=MenuButtonWebApp(
                text="Panel",
                web_app=WebAppInfo(url=config.WEBAPP_URL),
            )
        )
        log.info("Mini App menyu tugmasi yoqildi: %s", config.WEBAPP_URL)
    else:
        await app.bot.set_chat_menu_button(menu_button=MenuButtonDefault())


def build_menu_actions() -> None:
    """Menyu tugmalarini handlerlarga bog'laydi. Barcha handlerlar e'lon
    qilingandan keyin chaqiriladi."""
    handlers = MENU_HANDLERS
    handlers.update({
        "today": _period_command("bugun"),
        "week": _period_command("hafta"),
        "month": _period_command("oy"),
        "year": _period_command("yil"),
        "recent": cmd_recent,
        "debts": cmd_debts,
        "csv": cmd_csv,
        "guide": cmd_guide,
        "subs": cmd_plans,
        "budget": cmd_budget,
        "referral": cmd_referral,
        "longbill": cmd_collect_start,
        "ready": cmd_collect_done,
        "cancel": cmd_collect_cancel,
        "goals": cmd_goals,
        "pro": cmd_plans,
        "more": cmd_more,
    })
    # Ikkala tildagi tugma matni ham qabul qilinadi: foydalanuvchi tilni
    # almashtirsa, eski klaviatura hali ekranda turgan bo'lishi mumkin.
    for text, key in i18n.menu_lookup().items():
        if key in handlers:
            MENU_ACTIONS[text] = handlers[key]


build_menu_actions()


def main() -> None:
    missing = config.missing_settings()
    if missing:
        raise SystemExit(
            ".env faylida quyidagilar yo'q: " + ", ".join(missing)
        )
    if not config.OWNER_IDS:
        log.warning(
            "OWNER_IDS bo'sh — admin buyruqlari hech kimga ishlamaydi. "
            "Botga /id yozib, ID'ingizni .env dagi OWNER_IDS ga qo'shing."
        )
    if config.ALLOWED_USER_IDS:
        log.info(
            "YOPIQ rejim: faqat %d ta ID kiritiladi. Hammaga ochish uchun "
            ".env dagi ALLOWED_USER_IDS ni bo'shating.", len(config.ALLOWED_USER_IDS)
        )
    else:
        log.info(
            "OCHIQ rejim: yangi foydalanuvchilar %d kunlik bepul sinov oladi.",
            config.trial_days(),
        )

    db.init()

    app = (
        Application.builder()
        .token(config.TELEGRAM_TOKEN)
        .post_init(_post_init)
        # MUHIM (1000 foydalanuvchi uchun): standart holatda python-telegram-bot
        # yangilanishlarni BIRIN-KETIN qayta ishlaydi. AI chaqiruvi 2–16 soniya
        # davom etgani uchun bitta sekin chek butun navbatni to'xtatib qo'yardi.
        # concurrent_updates bilan foydalanuvchilar bir-birini kutmaydi.
        .concurrent_updates(config.MAX_CONCURRENT_UPDATES)
        .build()
    )

    register_handlers(app)

    log.info("Bot ishga tushdi. To'xtatish: Ctrl+C")
    app.run_polling(drop_pending_updates=True)


def register_handlers(app) -> None:
    """Barcha buyruq va tugma ishlovchilarini ro'yxatga oladi.

    main() dan ATAYLAB ajratilgan: shu ko'rinishda uni sinovdan
    o'tkazish mumkin. Sababi amaliy — Telegram buyruq nomi faqat ASCII
    harf, raqam va pastki chiziqdan iborat bo'la oladi va noto'g'ri nom
    faqat SHU bosqichda ValueError beradi. Bir marta shunday xato
    jonli serverga chiqib, bot umuman ishga tushmay qolgan.
    """
    app.add_handler(CommandHandler("start", cmd_start))
    app.add_handler(CommandHandler(["yordam", "help", "qollanma", "guide"], cmd_guide))
    app.add_handler(CommandHandler(["buyruqlar", "commands"], cmd_commands))
    app.add_handler(CommandHandler(["obuna", "tarif"], cmd_plans))
    app.add_handler(CommandHandler("holat", cmd_status))
    app.add_handler(CommandHandler("id", cmd_id))
    app.add_handler(CommandHandler("panel", cmd_panel))
    app.add_handler(CommandHandler("oddiy_rejim", cmd_sim_mode))
    app.add_handler(CommandHandler("statistika", cmd_stats))
    app.add_handler(CommandHandler("xabar_yubor", owner_only(broadcast.cmd_broadcast)))
    app.add_handler(CommandHandler(["til", "lang", "yazyk"], cmd_lang))
    app.add_handler(CommandHandler(["maxfiylik", "privacy"], cmd_privacy))
    app.add_handler(CommandHandler(["shartlar", "oferta", "terms"], cmd_terms))
    app.add_handler(CommandHandler(["ochirish", "hisobniochir"], cmd_erase))
    app.add_handler(CommandHandler(["taklif", "referal"], cmd_referral))
    app.add_handler(CommandHandler(["byudjet", "budjet"], cmd_budget))
    # Diqqat: Telegram buyruq nomi faqat ASCII harf, raqam va pastki
    # chiziqdan iborat bo'la oladi. «jamgʻarma» kabi apostrofli variant
    # ValueError beradi va bot umuman ishga tushmaydi.
    app.add_handler(CommandHandler(["jamgarma", "omonat"], cmd_savings))
    app.add_handler(CommandHandler(["maqsad", "goal"], cmd_goal))
    app.add_handler(CommandHandler(["maqsadlar", "goals"], cmd_goals))
    app.add_handler(CommandHandler(["foiz", "percent"], cmd_savings_rate))
    app.add_handler(CommandHandler(["holatim", "sofqiymat"], cmd_net_worth))
    app.add_handler(CommandHandler(["reja", "qarzreja"], cmd_debt_plan))
    app.add_handler(CommandHandler("eslatma", cmd_reminder))
    app.add_handler(CommandHandler(["kurs", "valyuta"], cmd_rate))
    app.add_handler(CommandHandler("bugun", _period_command("bugun")))
    app.add_handler(CommandHandler("kecha", _period_command("kecha")))
    app.add_handler(CommandHandler("hafta", _period_command("hafta")))
    app.add_handler(CommandHandler("oy", _period_command("oy")))
    app.add_handler(CommandHandler("otganoy", _period_command("otgan_oy")))
    app.add_handler(CommandHandler("yil", _period_command("yil")))
    app.add_handler(CommandHandler("oxirgi", cmd_recent))
    app.add_handler(CommandHandler("qarz", cmd_debts))
    app.add_handler(CommandHandler("ochir", cmd_delete))
    app.add_handler(CommandHandler("yopdim", cmd_settle))
    app.add_handler(CommandHandler("csv", cmd_csv))
    app.add_handler(CommandHandler("chek", cmd_collect_start))
    app.add_handler(CommandHandler("tayyor", cmd_collect_done))
    app.add_handler(CommandHandler("bekor", cmd_collect_cancel))
    app.add_handler(CallbackQueryHandler(on_callback))
    app.add_handler(MessageHandler(filters.PHOTO | filters.Document.IMAGE, on_photo))
    app.add_handler(MessageHandler(filters.TEXT & ~filters.COMMAND, on_text))
    app.add_error_handler(on_error)
    schedule_jobs(app)


if __name__ == "__main__":
    main()
