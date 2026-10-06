# Jonli chek namunalari

`pytest -m live tests/test_live_receipts.py` shu papkadagi rasmlar bilan ishlaydi.
Hozir `expected.json` bo'sh (`[]`): **haqiqiy chek rasmlari hali yig'ilmagan**,
test shu sababli o'tkazib yuboriladi.

## Nima kerak

**20 ta haqiqiy chek** (`.jpg`, `.png`, `.webp` yoki `.pdf`): turli do'konlar,
qisqa va uzun cheklar, xira va qiyshiq suratlar, chegirmali cheklar, dollar
cheki bo'lsa — o'sha ham. Shaxsiy ma'lumot (karta raqami, telefon, ism) bo'lsa
yopib qo'ying.

## expected.json

```json
[
  {"file": "01_korzinka.jpg", "jami": 260800, "valyuta": "som"},
  {"file": "02_dorixona.png", "jami": 87500, "valyuta": "som"}
]
```

`jami` — chekda bosilgan yakuniy summa (JAMI / ITOGO).

## Ko'rsatkich

«Jami bilan mos» ulushi: Python hisoblagan mahsulotlar yig'indisi chekdagi
jami bilan ruxsat etilgan farq ichida (`ai.receipt_tolerance`) bo'lgan cheklar
ulushi. Eski va yangi versiyada bir xil o'lchanadi
(`docs/gemini-baholash.md`).
