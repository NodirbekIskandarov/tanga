# Gemini baholash hisoboti

**Holat: JONLI BAHOLASH O'TKAZILMAGAN → production'ga CHIQARILMAYDI.**
Kod va oflayn testlar tayyor (317 ta o'tadi), lekin quyidagi qabul mezonlari
hali o'lchanmagan. Jadvalda bo'sh joylar — haqiqatan o'lchanmagan
ko'rsatkichlar; ular to'qib yozilmagan.

## Nima tayyor, nima yo'q

| | Holat |
|---|---|
| `gemini.py` (Interactions API, qayta urinish, timeout, usage), sxemalar, promptlar | ✅ yozilgan, SDK turlariga qarshi tekshirilgan, oflayn testlar yashil |
| Narx jadvali (sanaga bog'langan), `cost_usd` | ✅ hujjatdan (2026-10-06) tasdiqlangan, testlangan |
| Ovozli kiritish (handler, tasdiq, limit, bayroq) | ✅ oflayn testlar yashil |
| **Jonli SDK/API chaqiruvi** | ❌ bajarilmagan (pastdagi 1-bo'lim) |
| **Claude bazasi** (`docs/ai-baseline-claude.md`) | ❌ Claude kaliti va chek namunalari yo'q |
| **30+ ovoz namunasi, 20 chek** | ❌ yig'ilmagan (`tests/live_voice/`, `tests/live_receipts/`) |

## 1. Birinchi jonli tekshiruv (har qanday baholashdan oldin)

Kod hujjat va SDK turlariga tayanib yozilgan, lekin quyidagilar **haqiqiy
chaqiruvda tasdiqlanmagan** — bittadan sinab ko'ring
(`GEMINI_API_KEY` — faqat billing yoqilgan kalit):

- [ ] `pytest -m live tests/test_live_ai.py` ishlaydi: so'rov shakli
      (`response_format`, `generation_config.thinking_level`, `input` bo'laklari)
      qabul qilinadi.
- [ ] `thinking_level="minimal"` ikkala modelda (`gemini-3.5-flash-lite`,
      `gemini-3.8-flash`) rad etilmaydi. Rad etilsa — `PARSE_THINKING=low`.
- [ ] **Usage ma'nosi:** `total_output_tokens` «o'ylash» tokenlarini o'z ichiga
      oladimi? Kod xavfsiz tomonga og'adi (`max(chiqish + o'ylash, jami − kirish)`),
      ya'ni narxni bir oz KO'P hisoblashi mumkin. Haqiqiy javobdagi sonlarni
      Google Cloud billing bilan solishtiring va `gemini.usage_of` ni aniqlang.
- [ ] `VOICE_SCHEMA` (~4.4 KB) rad etilmaydi (juda chuqur sxema xatosi bo'lsa —
      sxemani soddalashtiring).
- [ ] Telegram ovozi (`audio/ogg`, Opus) qabul qilinadi.
- [ ] Kesh ishlaydi: ikkinchi bir xil so'rovda `total_cached_tokens > 0`.
- [ ] PDF (`document` bo'lagi) va rasm (`image/jpeg`) o'qiladi.

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
