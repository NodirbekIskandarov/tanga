# Gemini baholash hisoboti

**Holat: JONLI BAHOLASH O'TKAZILMAGAN → production'ga CHIQARILMAYDI.**
Kod va oflayn testlar tayyor (321 ta o'tadi), lekin quyidagi qabul mezonlari
hali o'lchanmagan. Jadvalda bo'sh joylar — haqiqatan o'lchanmagan
ko'rsatkichlar; ular to'qib yozilmagan.

## Nima tayyor, nima yo'q

| | Holat |
|---|---|
| `gemini.py` (Interactions API, qayta urinish, timeout, usage), sxemalar, promptlar | ✅ yozilgan, SDK turlariga qarshi tekshirilgan, oflayn testlar yashil |
| Narx jadvali (sanaga bog'langan), `cost_usd` | ✅ hujjatdan (2026-10-06) tasdiqlangan, testlangan |
| Ovozli kiritish (handler, tasdiq, limit, bayroq) | ✅ oflayn testlar yashil |
| Jonli SDK/API chaqiruvi | ✅ 2026-10-06 bajarildi (1-bo'lim; `audio/ogg`, PDF, kesh ochiq) |
| **Claude bazasi** (`docs/ai-baseline-claude.md`) | ❌ Claude kaliti va chek namunalari yo'q |
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
- [ ] **Telegram ovozi `audio/ogg` (Opus)** — alohida tekshirilmagan: OGG namuna
      yo'q (SDK turida `audio/ogg` bor). Birinchi haqiqiy ovozli xabarda tekshiring.
- [ ] **PDF** (`document` bo'lagi) — tekshirilmagan.
- [ ] **Kesh:** ikki bir xil matn so'rovida `total_cached_tokens` = 0 chiqdi
      (prompt ~3 460 token). Yashirin kesh ishlamadi yoki minimal hajm/vaqt
      shartiga yetmadi — tasdiqlanmagan. Narx kesh HISOBGA OLINMAGAN holda
      yozilgan (ehtiyotkor).

Birinchi o'lchangan narxlar (sintetik, kichik namunalar — haqiqiy cheklar
kattaroq):

| Amal | Model | Sarf |
|---|---|---|
| Matnli yozuv («obedga 45 ming») | flash-lite, minimal | ~$0.0013 (3 455 kirish, ~120 chiqish) |
| Ovozli yozuv (~7 s sintez) | flash-lite, minimal | ~$0.0019 (4 489 kirish, shundan 125 audio) |
| Chek (4 qatorli sintetik rasm) | 3.8-flash, medium | ~$0.0036 (1 986 kirish, 573 chiqish+o'ylash) |

## 2. Qabul mezonlari (7-bo'lim)

| Mezon | Talab | Natija |
|---|---|---|
| Matn: to'g'ri javoblar soni | Claude bazasidan kam emas | — |
| Chek: «jami bilan mos» ulushi | Claude bazasidan kam emas | — |
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
