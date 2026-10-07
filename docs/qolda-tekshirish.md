# Qo'lda tekshirish (Telegram'da)

Bu oqim avtomatik ham tekshiriladi (`tests/test_e2e_flow.py`). Lekin
haqiqiy Telegram ilovasida bir marta ko'rib chiqish kerak: tugmalar
ko'rinishi, matnlar va admin panel bilan bog'lanish.

Bot egasi akkauntidan bajariladi. Taxminan 10 daqiqa.

## Oldindan bilib qo'ying

- 6-qadamda admin tasdiqlasa, admin panelning **Moliya** bo'limiga 99 000 so'mlik to'lov yozuvi tushadi. Moliya hisobotini toza saqlamoqchi bo'lsangiz, oxirgi qadamda **Rad etish** ni bosing: oqim baribir to'liq tekshiriladi.
- Egalarning sinov so'rovi **asoschilar joyini egallamaydi** (100 tadan).
- Tasdiqlansa, egaga 365 kunlik obuna yoziladi. Oddiy rejim o'chirilgach, ega baribir cheksiz bo'lgani uchun buning ta'siri yo'q.

## Qadamlar

| # | Nima qilasiz | Nima ko'rinishi kerak |
|---|---|---|
| 1 | `/oddiy_rejim on` | «🧪 Oddiy rejim yoqildi» |
| 2 | `/holat` | «🆓 Bepul versiya», «Bu oy chek: N/3 qoldi» |
| 3 | `/start` | Qisqa salomlashish (3–4 qator); menyu: Bugun, Oy, Maqsadlar, Qarzlar, Panel, PRO, ⚙️ Yana |
| 4 | Chek rasmini yuboring (oyiga 3 tadan oshguncha) | 4-chekda: «🧾 Bu oygi 3 ta bepul chek ishlatildi…» va «💎 PRO ga o'tish» tugmasi |
| 5 | Yana bitta chek | Bitta qisqa qator: «🔒 Chek o'qish… — PRO imkoniyati» (tugmasiz) |
| 6 | `/yil`, `/byudjet`, `/csv`, `/solishtir` | Har biri — paywall |
| 7 | 📱 Panel → «Yil» yorlig'i yoki o'tgan oyga «‹» | «💎 Tanga PRO» oynasi, «PRO ga o'tish» botga qaytaradi |
| 8 | «💎 PRO ga o'tish» | Tariflar: ⭐ Yillik 149 000 (oyiga 12 400, 35% tejash), Oylik 19 000, 🎁 Asoschilar taklifi 99 000 (qolgan joylar: N/100) |
| 9 | «🎁 Asoschilar taklifi» | Karta rekvizitlari, «To'lov summasi: 99 000» |
| 10 | Istalgan rasmni (yoki PDF) yuboring | «Bu rasm nima?» va ikki tugma: «💳 To'lov cheki» / «🧾 Xarid cheki» |
| 10a | «💳 To'lov cheki» | «Chek qabul qilindi», sizga (egaga) chek nusxasi keladi |
| 11 | Admin panel → So'rovlar | `f12` so'rovi «tekshiruvda», chek rasmi ko'rinadi |
| 12 | **Tasdiqlash** (yoki Rad etish) | Botda «🎉 Obunangiz faollashtirildi» (yoki «To'lov tasdiqlanmadi») |
| 13 | `/holat` | Tasdiqlangan bo'lsa — «✅ Obuna faol» |
| 14 | `/oddiy_rejim off` | «👑 Oddiy rejim o'chirildi» |

## Xatolar tuzatilganini tekshirish

| Yozing | Kutilgan |
|---|---|
| `1 mln qarzim uchun to'landi` | ↩️ «Qarzimni qaytardim», bugungi chiqim o'zgarmaydi |
| `nonga 8 ming, taksiga 25 ming` | Har qatorda kategoriya, har yozuv uchun «✏️» |
| `12 mingga suv oldim` / `suv puliga 45 ming to'ladim` | oziq-ovqat / kommunal |
| Chegirmali chek (jami = mahsulotlar yig'indisi) | Ogohlantirishsiz; «Oxirgi» da bitta qator |
| Chek mahsulotini «✏️ Kategoriya» bilan tuzating | Javobda «Eslab qoldim: …»; o'sha do'konning keyingi chekida aniqlanmagan mahsulotlar shu kategoriyaga tushadi |
| `/oy` → «📊 O'tgan oy bilan solishtirish» | Grafik (jamlangan chiqim chizig'i, kirim/chiqim, kategoriyalar) va ostida matn; bir xil kunlar, ▲/▼ bilan |
| **Ega bo'lmagan** akkauntdan klaviaturadagi «📱 Panel» | Bot «📱 Panelni ochish» inline tugmasini yuboradi; u bosilganda panel ma'lumot bilan ochiladi |
| `/maqsad Uy 300 mln 2028-mart` → `uy uchun 1 mln qo'ydim` | Maqsad progressi; 🎯 Maqsadlar da bashorat |

## Telegram profili

Bot profilini (chat ro'yxatida) oching. Qisqa tavsif oxirida
«Bepul, 7 kun PRO sovg'a» turishi kerak, ruscha Telegram'da —
«Бесплатно, 7 дней PRO в подарок».
