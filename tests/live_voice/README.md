# Jonli ovoz namunalari

`pytest -m live tests/test_live_voice.py` shu papkadagi fayllar bilan ishlaydi.
Hozir `expected.json` bo'sh (`[]`): **haqiqiy ovoz yozuvlari hali yig'ilmagan**,
test shu sababli o'tkazib yuboriladi.

## Nima kerak

**Kamida 30 ta haqiqiy namuna** (`.ogg` — Telegram ovozli xabari; `.mp3`, `.m4a`,
`.wav` ham bo'ladi), har biri 3–30 soniya:

- erkak va ayol ovozi;
- Toshkent va boshqa viloyat talaffuzi;
- shovqinli ko'cha, mashina ichi;
- o'zbek lotin (o'zbekcha gap), rus va aralash gaplar;
- bitta xabarda 2–3 yozuv;
- qarz berdim / oldim / qaytardim;
- dollar; «kecha»; jamg'arma maqsadi bilan; savol («bu oy qancha sarfladim?»);
- moliyaga aloqasiz gap; jim yoki bo'sh audio.

Yozuvchilarning roziligi bilan oling: ovoz — shaxsiy ma'lumot. Haqiqiy
ismlar o'rniga to'qilgan ismlardan foydalaning (Akmal, Sardor...).

## expected.json

```json
[
  {
    "file": "01_taksi_obed_uz.ogg",
    "expected": {
      "niyat": "yozuv",
      "yozuvlar": [
        {"turi": "chiqim", "summa": 45000, "valyuta": "som", "kategoriya": ["kafe va restoran", "oziq-ovqat"]},
        {"turi": "chiqim", "summa": 20000, "valyuta": "som", "kategoriya": ["transport"]}
      ]
    }
  },
  {
    "file": "02_qarz_aralash.ogg",
    "expected": {"niyat": "yozuv", "yozuvlar": [
      {"turi": "qarz_berdim", "summa": 500000, "valyuta": "som", "shaxs": "Akmal"}]}
  },
  {"file": "03_savol.ogg", "expected": {"niyat": "savol"}},
  {"file": "04_bosh.ogg", "expected": {"niyat": "tushunarsiz"}}
]
```

- `turi`, `summa`, `valyuta` majburiy (valyuta berilmasa `som`); `shaxs` va
  `kategoriya` (ro'yxat — qaysi biri ham to'g'ri) ixtiyoriy.
- Yozuvlar aytilgan tartibda yoziladi.

## Qabul mezoni

tur + summa (+ valyuta, shaxs) kamida **90%** to'g'ri **va jimgina noto'g'ri
saqlangan holat 0 ta**: xato chiqqan namuna «past ishonch» bilan tasdiqqa
tushishi shart (`ishonch == "past"`). Natijalar `docs/gemini-baholash.md` ga
yoziladi.
