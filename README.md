# Shaxsiy tanga bot

Telegram bot: oddiy tilda yozasiz, ovozli xabar yuborasiz yoki chek rasmini yuborasiz —
Google Gemini matnni/ovozni/rasmni o'qib, undan summa, turi va kategoriyani ajratib oladi va SQLite bazaga yozadi.

```
Siz:  obedga 45 ming, taksi 20k
Bot:  ✅ 2 ta yozuv saqlandi
      🔻 45 000 so'm · tushlik
      🔻 20 000 so'm · taksi
      Bugungi chiqim: 65 000 so'm
```

```
Siz:  [chek surati]
Bot:  🧾 MAXSULOT SAVDO MARKAZI
      📅 2-avgust · 15 ta mahsulot

      Kategoriyalar bo'yicha:
      🥦 oziq-ovqat — 304 500 so'm (74%)
         ███████░░░ 11 ta
      📦 boshqa chiqim — 95 500 so'm (23%)
         ██░░░░░░░░ 3 ta
      💊 salomatlik — 13 000 so'm (3%)
         ░░░░░░░░░░ 1 ta

      💵 Mahsulotlar jami: 413 000 so'm
      ✅ Chekdagi jami bilan mos: 413 000 so'm
      🔝 Eng qimmati: Guruch Lazer 1kg — 54 000 so'm
```

## Nima qila oladi

- **Erkin matnni tushunadi** — `obedga 45 ming`, `1.5 mln kompyuterga`, `kecha dorixonaga 90 ming`
- **Ikki valyutani qo'llab-quvvatlaydi** — so'm (standart) va AQSH dollari (`$100`, `50 dollar`); har bir yozuv o'sha kundagi Markaziy bank kursi bilan so'mga o'giriladi va umumiy hisobotga qo'shiladi (chet el ulushi alohida ko'rsatiladi)
- **Chek rasmini o'qiydi** — chek bitta yozuv (do'kon, jami), mahsulotlar uning ichida kategoriyaga ajratilgan; chegirma kategoriyalar o'rtasida taqsimlanadi, saqlangan summa doim chekdagi jamiga teng
- **Uzun chekni qismlab qabul qiladi** — chek kadrga sig'masa, bir nechta rasm qilib yuborasiz; ustma-ust tushgan qatorlar bir marta hisoblanadi
- **Chekni tekshiradi** — mahsulotlar yig'indisini Python hisoblab, chekdagi "JAMI" bilan solishtiradi; farq chiqsa chekni avtomatik qayta o'qiydi
- **Bitta xabardan bir nechta yozuv** — `taksi 20k, kofe 25 ming, non 8 ming`
- **Avtomatik kategoriyalash** — 15 ta chiqim, 7 ta kirim kategoriyasi; «✏️ Kategoriya» tuzatishi eslab qolinadi va keyingi safar AI'dan ustun
- **Kirim va chiqim** — `oylik tushdi 8 mln` → kirim
- **Qarz hisobi** — berdim/oldim/qaytardim/qaytdi (`Akmal 200 mingni qaytardi`, `kreditga to'ladim`); qarz harakati xarajat ham, daromad ham emas; qaytarish muddati va eslatma
- **Sanani tushunadi** — "kecha", "1-avgustda" kabi so'zlarni sanaga aylantiradi
- **Hisobotlar** — kun, hafta, oy, o'tgan oy, yil kesimida foizli diagramma bilan
- **AI'dan savol so'rash** — `bu oy eng ko'p nimaga pul ketdi?` (jamlanmalar Python'da hisoblanadi, AI faqat tushuntiradi)
- **Xatoni tuzatish** — har bir yozuv ostida "Kategoriya" va "O'chirish" tugmalari
- **Tugmalar menyusi** — buyruqlarni eslash shart emas
- **Maqsadlar** — bir nechta maqsad, «shu sur'atda qachon erishaman» bashorati
- **«Avval o'zingizga to'lang»** — kirim yozilganda ulushni jamg'armaga taklif qiladi
- **Ichki qo'llanma** — `/yordam` (bo'limlar tugmalar bilan)
- **CSV eksport** — `/csv`
- **Bepul va PRO** — 7 kun to'liq PRO, keyin Bepul daraja (chegaralar `tiers.py` da);
  `ALLOWED_USER_IDS` to'ldirilsa — yopiq sinov rejimi

## Chek qanday o'qiladi

1. Rasm(lar) Gemini'ga yuboriladi. Model **faqat o'qiydi va kategoriyalaydi** — qo'shish
   vazifasi unga berilmaydi.
2. Mahsulotlar yig'indisini **Python hisoblaydi** va chekdagi "JAMI" bilan solishtiradi.
   Chekning o'zida yakuniy summa borligi — tekshiruv summasi vazifasini bajaradi.
3. Farq chiqsa, model farq haqida xabardor qilinib chek **qayta o'qiladi**; natija
   faqat yaxshilangan taqdirdagina almashtiriladi.
4. Har bir mahsulot alohida yozuv bo'lib bazaga tushadi, hammasi bitta `receipt_id`
   bilan bog'lanadi — shuning uchun butun chekni bitta tugma bilan o'chirish mumkin.

Uzun chekni yuborishning ikki usuli:

- **Albom** — qismlarni suratga oling va galereyadan hammasini birdan yuboring.
- **`/chek` rejimi** — «🧾 Uzun chek» tugmasi → qismlarni bitta-bitta yuborasiz → «✅ Tayyor».

Eng aniq natija uchun rasmni **Fayl** sifatida yuboring — Telegram uni siqmaydi.

## Fayllar

| Fayl | Vazifasi |
|---|---|
| `bot.py` | Telegram handlerlari, ishga tushirish nuqtasi |
| `ai.py` | AI qatlami: matn, ovoz, chek, savol (normallashtirish va chek tekshiruvi Python'da) |
| `gemini.py` | Google Gemini mijozi: Interactions API, vaqt chegarasi, qayta urinish, token sarfi |
| `ai_prompts.py`, `ai_schemas.py` | Tizim promptlari va JSON sxemalar |
| `db.py` | SQLite bilan ishlash |
| `reports.py` | Hisobotlarni matnga aylantirish |
| `config.py` | Sozlamalar va kategoriyalar ro'yxati |
| `tiers.py` | Bepul va PRO chegaralari |
| `webapp.py` + `static/` | Telegram Mini App (grafikli panel) |
| `i18n.py`, `i18n_extra.py`, `guide_ru.py` | Matnlar: o'zbek (lotin/kirill) va rus; hisobotlar `reports.py` da, Mini App tarjimasi `static/app.js` (`RU`) da |
| `scripts/` | Ma'lumot migratsiyalari (dry-run / `--apply` / `--rollback`) |

## O'rnatish

Kerak bo'ladi: **Python 3.10+**, Telegram akkaunt, Google Gemini API kaliti (**billing yoqilgan**).

### 1. Telegram bot tokenini olish

Telegramda [@BotFather](https://t.me/BotFather) ga yozing:
```
/newbot
```
Nom va username so'raydi. Oxirida `123456789:AAH...` ko'rinishidagi token beradi — saqlab qo'ying.

### 2. Gemini API kalitini olish

[Google AI Studio](https://aistudio.google.com/apikey) → **Create API key**, so'ng
loyihada **billing yoqing**. ⚠️ Faqat pullik darajadagi kalit ishlatiladi: bepul
daraja yuborilgan kontentni Google mahsulotlarini yaxshilashga ishlatadi.

**Nega Interactions API:** Google hujjatiga ko'ra 2026-iyundan standart interfeys
`interactions` (`client.aio.interactions.create`), `generateContent` esa eski
(legacy, lekin qo'llab-quvvatlanadi). O'rnatilgan SDK (`google-genai` 2.28)da asinxron
varianti, JSON sxemali javob, audio va PDF ishlaydi — shuning uchun shu tanlandi.

### 3. Loyihani tayyorlash

```bash
cd tanga_bot

python3 -m venv .venv
source .venv/bin/activate          # Windows: .venv\Scripts\activate

pip install -r requirements.txt

cp .env.example .env
```

`.env` faylini ochib to'ldiring:

```env
TELEGRAM_TOKEN=123456789:AAH...
GEMINI_API_KEY=...
ALLOWED_USER_IDS=
```

### 4. O'z Telegram ID'ingizni bilib olish

```bash
python bot.py
```

Botni Telegramdan toping va `/id` yozing (bu buyruq faqat OWNER_IDS bo'sh bo'lganda yoki egaga ishlaydi) — u sizga raqamingizni aytadi.
Shu raqamni `.env` dagi `ALLOWED_USER_IDS` ga yozing, botni to'xtatib (`Ctrl+C`) qayta ishga tushiring.

Tayyor. Endi botga xarajatlaringizni yozavering.

## Buyruqlar

| Buyruq | Vazifasi |
|---|---|
| `/start` | Qisqa salomlashish va tugmalar menyusi |
| `/yordam` (`/qollanma`) | Bo'limlarga ajratilgan qo'llanma |
| `/chek` | Uzun chekni qismlab yuborish rejimi |
| `/tayyor` | Yig'ilgan chek qismlarini tahlil qilish |
| `/bekor` | Chek yig'ishni bekor qilish |
| `/bugun` `/kecha` `/hafta` `/oy` `/otganoy` `/yil` | Hisobotlar |
| `/oxirgi` | Oxirgi 12 ta yozuv |
| `/qarz` | Ochiq qarzlar |
| `/ochir 12` | 12-raqamli yozuvni o'chirish |
| `/yopdim 12` | Qarzni yopilgan deb belgilash |
| `/csv` | Barcha yozuvlarni CSV fayl qilib olish |
| `/obuna` | Tanga PRO tariflari va to'lov |
| `/holat` | Daraja (Bepul/PRO), muddat va qolgan limitlar |
| `/maqsadlar` | Maqsadlar, progress va bashorat |
| `/maqsad Uy 300 mln 2028-mart` | Yangi maqsad |
| `/foiz` | «Avval o'zingizga to'lang» ulushi (PRO) |
| `/byudjet` | Kategoriyaga oylik chegara qo'yish |
| `/eslatma 21` | Kunlik eslatmani soat 21:00 ga sozlash |
| `/kurs` | Bugungi dollar kursi (Markaziy bank; qo'lda o'zgartirib bo'lmaydi) |
| `/taklif` | Do'st taklif qilib bepul kun olish |
| `/til` | Interfeys tili: o'zbek lotin / kirill / rus |
| `/maxfiylik` | Maxfiylik siyosati |
| `/shartlar` | Xizmat shartlari (ommaviy oferta) |
| `/ochirish` | Hisobni va butun tarixni o'chirish |

Faqat ega uchun: `/panel`, `/statistika` (faollik, saqlanish, voronka,
paywall), `/xabar_yubor` (ko'rish va ikki bosqichli tasdiq bilan),
`/oddiy_rejim on|off` (o'zini obunasiz foydalanuvchidek sinash).

## Sinovlar

```bash
pip install -r requirements-dev.txt
pytest              # oflayn: AI soxtalashtiriladi, vaqtinchalik bazada
pytest -m live      # haqiqiy AI bilan (faqat qo'lda, pul turadi)
```

Migratsiya skriptlari va chiqarish tartibi — `DEPLOY.md` da.

## Sozlamalar (`.env`)

| O'zgaruvchi | Standart | Izoh |
|---|---|---|
| `GEMINI_API_KEY` | — | Gemini kaliti (majburiy, billing yoqilgan) |
| `PARSE_MODEL` | `gemini-3.5-flash-lite` | Matn yozuvlarini ajratuvchi model — arzon va tez |
| `VOICE_MODEL` | `gemini-3.5-flash-lite` | Ovozli xabar (transkripsiya + ajratish bitta chaqiruvda) |
| `CHAT_MODEL` | `gemini-3.8-flash` | Savollarga javob beruvchi model |
| `VISION_MODEL` | `gemini-3.8-flash` | Chek rasmlarini o'qiydigan model — aniqlik muhim |
| `PARSE_THINKING`, `VOICE_THINKING` | `minimal` | «O'ylash» darajasi: `minimal` / `low` / `medium` / `high` |
| `VISION_THINKING`, `CHAT_THINKING` | `medium` | O'ylash tokenlari chiqish narxida hisoblanadi |
| `VOICE_ENABLED` | `false` | Ovozli kiritish bayrog'i |
| `VOICE_BETA_USER_IDS` | bo'sh | Bo'sh bo'lmasa — ovoz faqat shu ID'lar va egalar uchun |
| `VOICE_MAX_SECONDS` / `VOICE_MAX_BYTES` | `60` / `2000000` | Ovoz davomiyligi va hajmi chegarasi |
| `VOICE_CONFIRM_ABOVE_SOM` / `_USD` | `5000000` / `500` | Shundan katta summa ovozdan aniqlansa — tasdiq so'raladi |
| `LIMIT_VOICE_PER_DAY` / `FREE_VOICE_PER_DAY` | `40` / `5` | Kunlik ovoz limiti: PRO / Bepul (biznes qarori) |
| `CURRENCY` | `so'm` | Valyuta nomi |
| `TIMEZONE` | `Asia/Tashkent` | Vaqt mintaqasi |
| `SMALL_NUMBERS_ARE_THOUSANDS` | `true` | `obedga 50` → 50 000 so'm deb tushunilsinmi |
| `DB_PATH` | `tanga.db` | Baza fayli joyi |
| `QA_MAX_ROWS` | `150` | Savolga javob berishda AI ko'radigan yozuvlar soni |
| `MAX_RECEIPT_PARTS` | `8` | Bitta chek uchun maksimal rasm soni |
| `MAX_IMAGE_BYTES` | `8000000` | Bitta rasm uchun maksimal hajm (xom bayt) |
| `MAX_PDF_BYTES` | `12000000` | Bitta PDF uchun maksimal hajm |
| `MAX_RECEIPT_TOTAL_BYTES` | `13000000` | Bitta chek barcha qismlarining yig'indisi (Gemini so'rovi jami 20 MB) |

### Kategoriyalarni o'zgartirish

`config.py` ichidagi `EXPENSE_CATEGORIES` va `INCOME_CATEGORIES` ro'yxatlarini
tahrirlang, `CATEGORY_ICONS` ga emoji qo'shing. Boshqa hech narsani o'zgartirish shart emas —
AI ro'yxatni avtomatik ravishda o'z sxemasidan oladi.

## Xarajat haqida

> ⚠️ Quyidagi sonlar **hisob-kitob** (token soni × hujjatdagi narx), jonli
> o'lchov emas. Jonli baholash (`docs/gemini-baholash.md`) o'tgach haqiqiy
> o'rtacha qiymatlar shu yerga yoziladi.

| Amal | Model | Taxminiy sarf (bir amal) |
|---|---|---|
| Matnli yozuv | `gemini-3.5-flash-lite` | ~4 000 kirish (prompt + sxema; keshdan ~10 baravar arzon), ~150–250 chiqish: **~$0.001–0.002** |
| Ovozli yozuv (10 s) | `gemini-3.5-flash-lite` | + ~320 audio token (32 tok/s): **~$0.001–0.002** |
| Savolga javob | `gemini-3.8-flash` | 150 yozuvli foydalanuvchida **~$0.009** (2026-10-08 gacha JSON formatda ~$0.015 edi — production o'lchovi, `docs/gemini-baholash.md`) |
| **Chek rasmi** | `gemini-3.8-flash` | rasm bir necha ming token + o'ylash: **~$0.015** (2027-01-01 dan **~$0.03**) |

Narxlar (pullik daraja, 1M token, [hujjat](https://ai.google.dev/gemini-api/docs/pricing)):
`gemini-3.5-flash-lite` — kirish $0.30 (matn, rasm, audio), chiqish $2.50, keshdan o'qish
$0.03. `gemini-3.8-flash` — kirish $0.75, chiqish $3.75, kesh $0.075 **2026-12-31 gacha**;
**2027-01-01 dan** $1.50 / $7.50 / $0.15 (ikki barobar). «O'ylash» tokenlari chiqish
narxida hisoblanadi. Hisob-kitob `config.cost_usd` da, narx sanaga bog'langan.

Tekshiruvda farq chiqsa chek ikkinchi marta o'qiladi — bu holda chek sarfi ikki barobar.

**Tejash uchun** `.env` da:

```env
VISION_THINKING=low            # chek o'qish arzonroq, aniqlik biroz pastroq
CHAT_MODEL=gemini-3.5-flash-lite   # savol-javob arzonroq
```

## 24/7 ishlashi uchun (serverda)

Kompyuteringizni o'chirsangiz bot ham to'xtaydi. Doimiy ishlashi uchun arzon VPS
oling va `systemd` xizmati sifatida ishga tushiring:

`/etc/systemd/system/tanga.service`:

```ini
[Unit]
Description=Tanga bot
After=network-online.target

[Service]
Type=simple
User=ubuntu
WorkingDirectory=/home/ubuntu/tanga_bot
ExecStart=/home/ubuntu/tanga_bot/.venv/bin/python bot.py
Restart=always
RestartSec=10

[Install]
WantedBy=multi-user.target
```

```bash
sudo systemctl daemon-reload
sudo systemctl enable --now tanga
sudo journalctl -u tanga -f     # loglarni ko'rish
```

## Xavfsizlik

- `.env` faylini hech kimga bermang va git'ga yuklamang (`.gitignore` da allaqachon bor).
- Baza (`tanga.db`) oddiy fayl — vaqti-vaqti bilan nusxasini oling.
- `ALLOWED_USER_IDS` bo'sh bo'lsa bot hech kimga javob bermaydi. Bu ataylab shunday.

## Ma'lum cheklovlar

- Bot AI javobiga tayanadi, shuning uchun goh-goh kategoriyani noto'g'ri tanlashi mumkin —
  shuning uchun har bir yozuv ostida "Kategoriya" tugmasi bor.
- Chekda yakuniy "JAMI" summasi ko'rinmasa, tekshiruvni bajarib bo'lmaydi — bot bu
  haqda ogohlantiradi, lekin summalar to'g'riligiga kafolat bermaydi.
- Chek qismlari yig'ilayotgan paytdagi rasmlar xotirada saqlanadi; bot qayta ishga
  tushsa yig'ilgan qismlar yo'qoladi.
- Ovozli xabar qo'shilmagan. Kerak bo'lsa transkripsiya xizmati orqali qo'shsa bo'ladi.
- Ikki valyuta (so'm, dollar) qo'llab-quvvatlanadi; dollar yozuvi kiritilgan
  kundagi Markaziy bank kursi bilan so'mga o'giriladi (kurs tarmoqdan olinmasa —
  oxirgi ma'lum kurs, u ham bo'lmasa `USD_RATE_FALLBACK`). Qarz va kategoriya
  kesimlari valyutalar bo'yicha alohida saqlanadi.
