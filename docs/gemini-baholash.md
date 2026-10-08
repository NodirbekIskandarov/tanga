# Gemini baholash hisoboti

**Holat: production'da 2026-10-06 dan.** To'liq jonli baholash (30+ ovoz,
20 chek namunasi) hali o'tkazilmagan. Jadvalda bo'sh joylar — haqiqatan
o'lchanmagan ko'rsatkichlar; ular to'qib yozilmagan.

## Nima tayyor, nima yo'q

| | Holat |
|---|---|
| `gemini.py` (Interactions API, qayta urinish, timeout, usage), sxemalar, promptlar | ✅ yozilgan, SDK turlariga qarshi tekshirilgan, oflayn testlar yashil |
| Narx jadvali (sanaga bog'langan), `cost_usd` | ✅ hujjatdan (2026-10-06) tasdiqlangan, testlangan |
| Ovozli kiritish (handler, tasdiq, limit, bayroq) | ✅ oflayn testlar yashil |
| Jonli SDK/API chaqiruvi | ✅ 2026-10-06 bajarildi (1-bo'lim; faqat kesh ochiq) |
| **Claude bazasi** | ❌ o'lchanmadi va endi o'lchab bo'lmaydi: Claude olib tashlangan |
| **30+ ovoz namunasi, 20 chek** | ❌ yig'ilmagan (`tests/live_voice/`, `tests/live_receipts/`) |

## 1. Birinchi jonli tekshiruv (2026-10-06, haqiqiy kalit, pullik daraja)

Natijalar (yengil sinov: `pytest -m live tests/test_live_ai.py` va qo'lda tekshiruv):

- [x] **So'rov shakli qabul qilinadi** (`response_format`, `generation_config`,
      `input` bo'laklari, `system_instruction`): matn jadvali **18/18 to'g'ri**
      (12 jadval + 6 qo'shimcha; Claude bazasi bilan solishtirish hali yo'q).
- [x] **`thinking_level`:** `gemini-3.5-flash-lite` — `minimal/low/medium/high`
      hammasi ishlaydi. **`gemini-3.8-flash` `minimal` ni RAD ETADI** (400,
      «THINKING_LEVEL_MINIMAL is not supported»), `low` dan boshlanadi. Kod
      buni hal qiladi: bu model uchun `minimal` avtomatik `low` ga tushadi,
      noma'lum model 400 bersa — bir marta `low` bilan qayta uriniladi.
- [x] **Usage ma'nosi tasdiqlandi:** `total_tokens = kirish + chiqish + o'ylash`
      (masalan 22 + 104 + 638 = 764); `total_output_tokens` o'ylashni O'Z ICHIGA
      OLMAYDI, shuning uchun narx (chiqish + o'ylash) to'g'ri, ortiqcha
      hisoblanmaydi.
- [x] **`RECORD_SCHEMA`, `RECEIPT_SCHEMA`, `VOICE_SCHEMA` rad etilmadi.**
- [x] **Audio qabul qilinadi** (sintez qilingan WAV, `audio/wav`): transkripsiya
      va ikkita yozuv ajratildi, audio tokenlar alohida hisoblandi.
- [x] **Rasm o'qiladi** (sintetik chek, `image/jpeg`).
- [x] **Telegram ovozi `audio/ogg` (Opus)** qabul qilinadi (ffmpeg bilan
      OGG/Opus, mono 48 kHz ga o'girilgan ruscha sintez): transkripsiya, ikki
      yozuv, kategoriyalar to'g'ri. Ovozli savol (inglizcha sintez) ham
      `niyat=savol` deb tanildi. Haqiqiy odam ovozi bilan sinov — namunalar
      yig'ilgach.
- [x] **PDF** (`document` bo'lagi) o'qiladi: sintetik chek, jami bilan mos.
- [ ] **Kesh ishlamadi:** 3 ta ketma-ket bir xil matn so'rovida (5 s oraliq)
      `total_cached_tokens` = 0. Tizim prompti + sxema ~3 460 token — yashirin
      keshning minimal hajmidan (taxminan 4 096) kichik bo'lishi mumkin;
      tasdiqlanmagan. Narx kesh HISOBGA OLINMAGAN holda yozilgan (ehtiyotkor),
      shuning uchun haqiqiy sarf bundan past bo'lishi mumkin.

Birinchi o'lchangan narxlar (sintetik, kichik namunalar — haqiqiy cheklar
kattaroq):

| Amal | Model | Sarf |
|---|---|---|
| Matnli yozuv («obedga 45 ming») | flash-lite, minimal | ~$0.0013 (3 455 kirish, ~120 chiqish) |
| Ovozli yozuv (~7 s sintez) | flash-lite, minimal | ~$0.0019 (4 489 kirish, shundan 125 audio) |
| Chek (4 qatorli sintetik rasm) | 3.8-flash, medium | ~$0.0036 (1 986 kirish, 573 chiqish+o'ylash) |
| Chek (xuddi shu, PDF) | 3.8-flash, medium | ~$0.0030 |
| Ovozli yozuv (OGG/Opus, ~5 s) | flash-lite, minimal | ~$0.0020 (4 472 kirish, shundan 108 audio) |

## 1a. Production sarfi va savol-javobni ixchamlashtirish (2026-10-08)

Birinchi 2 kun (6–8-oktabr, 5 foydalanuvchi), `usage_log` dan. Google
konsolidagi $0.27 bilan mos: $0.20 production + ~$0.07 6-oktabrdagi jonli
sinovlar (ular `usage_log` ga yozilmaydi).

| Amal | Soni | Bir amal | Jami | Ulushi |
|---|---|---|---|---|
| Savol-javob (3.8-flash) | 11 | $0.0145 | $0.160 | 80% |
| Ovoz (3.5-flash-lite) | 13 | $0.0015 | $0.019 | 9% |
| Matn (3.5-flash-lite) | 14 | $0.0011 | $0.016 | 8% |
| Chek (3.8-flash) | 1 | $0.0066 | $0.007 | 3% |

Savolning kirishi ~13 950 token, uning 83% i xom yozuvlar ro'yxati edi
(har qatorda takrorlanuvchi JSON kalitlari). Yozuvlar jadvalga, jamlanmalar
bo'sh joysiz JSON'ga o'tkazildi — ma'lumot aynan o'sha:

- `count_tokens` (bepul, sintetik 150 yozuv): 13 227 → 6 853 token (−48%);
- jonli A/B, 5 ta javobi aniq ma'lum savol (jamlanma va jadvaldan qidirish):
  eski 5/5, yangi 5/5; kirish 13 920 → 7 550 token. Savol narxi
  ~$0.0146 → ~$0.0094 (−35%; qolgani — o'ylash tokenlari).

## 2. Qabul mezonlari (7-bo'lim)

| Mezon | Talab | Natija |
|---|---|---|
| Matn: to'g'ri javoblar soni | Claude bazasi yo'q — mutlaq natija | 18/18 (2026-10-06) |
| Chek: «jami bilan mos» ulushi | Claude bazasi yo'q — mutlaq natija | — |
| Ovoz: tur va summa (30+ namuna) | ≥ 90% | — |
| Ovoz: jimgina noto'g'ri summa | 0 ta | — |
| Narx: matn / ovoz / chek / savol (o'rtacha) | yozib olinadi, README yangilanadi | — |

Mezonlardan biri bajarilmasa: o'sha vazifa uchun kuchliroq modelni sinang
(`VOICE_MODEL=gemini-3.8-flash`, `PARSE_MODEL=gemini-3.8-flash`, yoki
`VISION_THINKING=high`). Baribir bajarilmasa — deploy qilinmaydi, egadan
qaror so'raladi.

## 3. Qanday o'lchanadi

```bash
export GEMINI_API_KEY=...            # faqat billing yoqilgan kalit
LIVE_RESULTS_JSON=/tmp/gemini.json pytest -m live \
  tests/test_live_ai.py tests/test_live_voice.py tests/test_live_receipts.py
```

Ovoz va chek uchun namunalar kerak (README'lar ularning tuzilishini
tushuntiradi). Narx: har bir `usage_log` qatori `cost_usd` ni saqlaydi —
sinovdan keyin `SELECT operation, AVG(cost_usd) FROM usage_log GROUP BY operation`.

## 4. Tavsiya etilgan modellar

Hujjatdan (2026-10-06): `gemini-3.5-flash-lite` (barqaror) — matn va ovoz;
`gemini-3.8-flash` (barqaror) — chek va savol. 3.8 Flash narxi 2027-01-01 dan
ikki barobar oshadi — shu sanadan oldin xarajatni qayta baholang.
Yakuniy tavsiya jonli natijalardan keyin yoziladi.
