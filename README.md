# Shaxsiy tanga bot

Telegram bot: oddiy tilda yozasiz yoki chek rasmini yuborasiz — Claude (Anthropic API)
matnni/rasmni o'qib, undan summa, turi va kategoriyani ajratib oladi va SQLite bazaga yozadi.

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

1. Rasm(lar) Claude'ga yuboriladi. Model **faqat o'qiydi va kategoriyalaydi** — qo'shish
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
| `ai.py` | Anthropic API: matnni tahlil qilish + savolga javob |
| `db.py` | SQLite bilan ishlash |
| `reports.py` | Hisobotlarni matnga aylantirish |
| `config.py` | Sozlamalar va kategoriyalar ro'yxati |
| `tiers.py` | Bepul va PRO chegaralari |
| `webapp.py` + `static/` | Telegram Mini App (grafikli panel) |
| `i18n.py`, `i18n_extra.py`, `guide_ru.py` | Matnlar: o'zbek (lotin/kirill) va rus; hisobotlar `reports.py` da, Mini App tarjimasi `static/app.js` (`RU`) da |
| `scripts/` | Ma'lumot migratsiyalari (dry-run / `--apply` / `--rollback`) |

## O'rnatish

Kerak bo'ladi: **Python 3.10+**, Telegram akkaunt, Anthropic API kaliti.

### 1. Telegram bot tokenini olish

Telegramda [@BotFather](https://t.me/BotFather) ga yozing:
```
/newbot
```
Nom va username so'raydi. Oxirida `123456789:AAH...` ko'rinishidagi token beradi — saqlab qo'ying.

### 2. Anthropic API kalitini olish

[console.anthropic.com](https://console.anthropic.com) → ro'yxatdan o'ting → **API Keys** → **Create Key**.
Balansga oz miqdorda pul qo'shishingiz kerak bo'ladi (kredit kartasi orqali).

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
ANTHROPIC_API_KEY=sk-ant-...
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
| `PARSE_MODEL` | `claude-haiku-4-5-20251001` | Matn yozuvlarini ajratuvchi model — arzon va tez |
| `CHAT_MODEL` | `claude-sonnet-5` | Savollarga javob beruvchi model |
| `VISION_MODEL` | `claude-opus-5` | Chek rasmlarini o'qiydigan model — eng aniq |
| `CURRENCY` | `so'm` | Valyuta nomi |
| `TIMEZONE` | `Asia/Tashkent` | Vaqt mintaqasi |
| `SMALL_NUMBERS_ARE_THOUSANDS` | `true` | `obedga 50` → 50 000 so'm deb tushunilsinmi |
| `DB_PATH` | `tanga.db` | Baza fayli joyi |
| `QA_MAX_ROWS` | `500` | Savolga javob berishda AI ko'radigan yozuvlar soni |
| `MAX_RECEIPT_PARTS` | `8` | Bitta chek uchun maksimal rasm soni |
| `MAX_IMAGE_BYTES` | `4500000` | Bitta rasm uchun maksimal hajm |

### Kategoriyalarni o'zgartirish

`config.py` ichidagi `EXPENSE_CATEGORIES` va `INCOME_CATEGORIES` ro'yxatlarini
tahrirlang, `CATEGORY_ICONS` ga emoji qo'shing. Boshqa hech narsani o'zgartirish shart emas —
AI ro'yxatni avtomatik ravishda o'z sxemasidan oladi.

## Xarajat haqida

| Amal | Model | Taxminiy sarf |
|---|---|---|
| Matnli yozuv | Haiku 4.5 | ~700–900 kirish, 100–200 chiqish tokeni — juda arzon |
| Savolga javob | Sonnet 5 | yozuvlar soniga bog'liq |
| **Chek rasmi** | **Opus 5** | rasm bir necha ming token, eng qimmat amal |

Chek o'qish eng qimmat amal, chunki rasm ko'p token oladi va aniqlik uchun
kuchli model ishlatiladi. Tekshiruvda farq chiqsa chek ikkinchi marta o'qiladi —
bu holda sarf ikki barobar bo'ladi.

Aniq narxlarni [anthropic.com/pricing](https://www.anthropic.com/pricing) dan
tekshiring — narxlar o'zgarib turadi.

**Tejash uchun** `.env` da:

```env
VISION_MODEL=claude-sonnet-5   # chek o'qish arzonroq, aniqlik biroz pastroq
CHAT_MODEL=claude-haiku-4-5    # savol-javob arzonroq
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
