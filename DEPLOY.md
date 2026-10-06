# Serverga joylashtirish

Bot 24/7 ishlashi uchun Linux (Ubuntu/Debian) serverga `systemd` xizmati
sifatida o'rnatiladi.

## Tez yo'l

Serverga SSH orqali kiring va bitta buyruq bilan o'rnating:

```bash
ssh root@SERVER_IP

curl -fsSL https://raw.githubusercontent.com/NodirbekIskandarov/tanga/main/deploy/setup.sh \
  -o setup.sh
bash setup.sh https://github.com/NodirbekIskandarov/tanga.git
```

Skript quyidagilarni bajaradi:

1. `python3`, `venv`, `git` paketlarini o'rnatadi
2. `tanga` nomli tizim foydalanuvchisini yaratadi (bot root sifatida ishlamaydi)
3. Loyihani `/opt/tanga` ga klonlaydi
4. Virtual muhit yaratib bog'liqliklarni o'rnatadi
5. `.env` faylini `.env.example` dan nusxalaydi (huquqlari `600`)
6. `systemd` xizmatini yoqadi

Keyin `.env` ni to'ldirasiz va xizmatni ishga tushirasiz:

```bash
nano /opt/tanga/.env      # TELEGRAM_TOKEN, GEMINI_API_KEY, ALLOWED_USER_IDS
systemctl start tanga
journalctl -u tanga -f    # loglarni kuzatish
```

> ⚠️ **Bir vaqtning o'zida bitta nusxa ishlashi kerak.** Telegram bitta tokenga
> faqat bitta `getUpdates` oqimini beradi. Serverda ishga tushirishdan oldin
> kompyuteringizdagi botni to'xtating, aks holda ikkalasi ham xabarlarni
> o'g'irlab, uzilib-uzilib ishlaydi.

## Yangilanishni chiqarish

Kodni o'zgartirib GitHub'ga yuborganingizdan keyin, serverda:

```bash
cd /opt/tanga
git pull
.venv/bin/pip install -q -r requirements.txt
systemctl restart tanga
```

Yoki shunchaki `setup.sh` ni qayta ishga tushiring — u mavjud `.env` va
bazaga tegmaydi.

## Gemini kaliti va AI xizmati

Bot AI uchun **Google Gemini API** dan foydalanadi (`gemini.py`).

- Kalit: [Google AI Studio](https://aistudio.google.com/apikey) yoki Google
  Cloud Console → **Gemini API** → API kaliti. Kalit faqat `.env` da
  (`GEMINI_API_KEY`), hech qachon gitga yoki chatga yozilmaydi.
- ⚠️ **Majburiy: billing yoqilgan (pullik) loyiha.** Bepul daraja kaliti
  yuborilgan kontentni Google mahsulotlarini yaxshilashga ishlatadi va
  odamlar uni ko'rib chiqishi mumkin; pullik darajada ishlatilmaydi. Bu
  maxfiylik siyosatidagi va'daning sharti — **bepul kalitni production'da
  ishlatmang.**
- Narx va modellar `config.py` da (`MODEL_PRICES`, sanaga bog'langan:
  `gemini-3.8-flash` 2027-01-01 dan ikki barobar qimmat).
- Xatolar: `journalctl -u tanga` da `Gemini xatosi [model]: <tur> (status N)`.
  `status 400/403` — kalit noto'g'ri yoki billing yoqilmagan; `429` — limit
  (bot o'zi 3 marta qayta uriladi); `5xx` — Google tomonida nosozlik.

## O'tish kuni: Claude → Gemini

Bir martalik tartib. **Baholash (`docs/gemini-baholash.md`) o'tmaguncha
bajarilmaydi.**

1. Bazaning zaxira nusxasi: `tanga-backup --local`.
2. Git tegi: `git tag oxirgi-claude` (allaqachon bor; qaytish nuqtasi).
3. `.env` da `GEMINI_API_KEY` va yangi model kalitlarini qo'ying
   (`.env.example` ga qarang), `ANTHROPIC_API_KEY` qatorini **o'chiring**.
   Avval `VOICE_ENABLED=false`.
4. `pip install -r requirements.txt`; eski paketni olib tashlang:
   `.venv/bin/pip uninstall -y anthropic`.
5. `systemctl restart tanga tanga-webapp`; loglarni kuzating.
6. Hamma foydalanuvchidan qayta rozilik so'raladi (`CONSENT_VERSION` oshgan:
   AI xizmat ko'rsatuvchisi almashdi).

Keyingi bosqichlar (ovoz): 2–3 kun kuzatish → `VOICE_ENABLED=true` va
`VOICE_BETA_USER_IDS=<ega va 5–10 sinovchi>` bir hafta → hammaga ochish
(`VOICE_BETA_USER_IDS` bo'sh, `/xabar_yubor` bilan o'zbek va rus tilida
e'lon). Muammosiz 2 hafta o'tgach Anthropic konsolida eski kalitni **ega
qo'lda bekor qiladi**.

### Qaytish yo'li (faqat git orqali)

```bash
cd /opt/tanga
git checkout oxirgi-claude
cp /root/env.claude-zaxira /opt/tanga/.env     # eski .env (ANTHROPIC_API_KEY bilan)
.venv/bin/pip install -q -r requirements.txt
systemctl restart tanga tanga-webapp
```

Eski `.env` nusxasini 3-qadamdan OLDIN saqlab qo'ying. Ikki provayderli
rejim va almashtirgich ATAYLAB yo'q.

## Mini App xizmati

Mini App backendi (`webapp.py`) alohida xizmat: `deploy/tanga-webapp.service`
(uvicorn, `172.30.0.1:8001`, Caddy konteyneri shu orqali kiradi). Deploy
skripti unit faylini KO'CHIRMAYDI — unit o'zgarsa qo'lda:

```bash
cp /opt/tanga/deploy/tanga-webapp.service /etc/systemd/system/
systemctl daemon-reload && systemctl restart tanga-webapp
```

## Ma'lumot migratsiyalari

Baza sxemasi (yangi jadval va ustunlar) bot ishga tushganda
**avtomatik** qo'shiladi — bu faqat qo'shadi, mavjud ma'lumotga
tegmaydi. Mavjud yozuvlarni o'zgartiradigan ishlar esa alohida
skriptlarda va hech qachon o'zidan ishlamaydi:

```bash
cd /opt/tanga
sudo -u tanga .venv/bin/python scripts/migrate_receipts.py           # dry-run
sudo -u tanga .venv/bin/python scripts/migrate_receipts.py --apply
sudo -u tanga .venv/bin/python scripts/migrate_debts.py              # dry-run
sudo -u tanga .venv/bin/python scripts/migrate_debts.py --apply --ids 12,40
sudo -u tanga .venv/bin/python scripts/link_debt_payments.py         # dry-run
sudo -u tanga .venv/bin/python scripts/link_debt_payments.py --apply
sudo -u tanga .venv/bin/python scripts/analyze_other.py              # faqat o'qiydi
```

- Standart rejim — **dry-run**: faqat nima o'zgarishini ko'rsatadi.
- `--apply` o'zgartirishdan oldin asl holatni `migration_backups/` ga
  yozadi; `--rollback FAYL` shu fayldan qaytaradi.
- `migrate_debts.py` turini aniqlay olmagan yozuvlarni «?» bilan
  ko'rsatadi va ularga hech qachon tegmaydi.

**Avval production NUSXASIDA tekshiring** — jonli bazaga tegmaydi:

```bash
sudo bash /opt/tanga/deploy/tanga-dryrun
```

U `tanga-backup --local` bilan izchil nusxa oladi, uni
`/var/tmp/tanga-dryrun/` ga ochadi va uchala skriptni shu nusxaga qarab
dry-run qiladi. Yozuv raqamlari production bilan bir xil, shuning uchun
`migrate_debts` ro'yxatidan tanlangan raqamlarni jonli bazada
`--apply --ids ...` bilan ishlatish mumkin. Ish tugagach:
`sudo rm -rf /var/tmp/tanga-dryrun`.

| Skript | Nima qiladi |
|---|---|
| `migrate_receipts.py` | eski cheklarga sarlavha (`receipts`); mahsulotlar o'zgarmaydi |
| `migrate_debts.py` | kirim/chiqim bo'lib tushgan qarz to'lovlarini qarz turlariga |
| `link_debt_payments.py` | ismsiz qarz to'lovlarini yagona ismsiz qarzga `repays_id` bilan bog'laydi |
| `analyze_other.py` | «boshqa chiqim» dagi so'zlar, kamida 3 odamda uchraganlari |

## PRO versiyasini chiqarish (tariflar, 2026-10)

Tartib muhim:

1. **Avval `tanga-admin`** (`feature/pro-tariflar`): unda asoschilar
   taklifi (`f12`) bor. Bot undan oldin chiqsa, `f12` so'rovini admin
   «Tarif topilmadi» deb tasdiqlay olmaydi.
2. **Admin panel → Sozlamalar:** oylik **19 000**, yillik **149 000**.
   Narx `app_settings` dan o'qiladi — u yerda eski narx tursa, bot ham
   eskisini ko'rsataveradi. `f12` narxi (99 000) kodda.
3. **Bot** — `git pull`, `systemctl restart tanga`. Sxema o'zi yangilanadi.
4. Yuqoridagi migratsiyalar: dry-run -> ko'rib chiqish -> `--apply`.
5. Tekshirish: `/oddiy_rejim on` -> 4-chek paywall -> tariflar -> `f12`
   -> chek -> adminda tasdiq. Keyin `/oddiy_rejim off`.

Sinov muddati tugagan eski foydalanuvchilar jimgina Bepul darajaga
o'tadi — ularga avtomatik xabar ketmaydi. Xabar faqat `/xabar_yubor`
orqali, ko'rish va ikki bosqichli tasdiq bilan.

## Sinovlar

```bash
.venv/bin/pip install -r requirements-dev.txt
.venv/bin/pytest                 # oflayn, tarmoqsiz, vaqtinchalik bazada
.venv/bin/pytest -m live         # haqiqiy AI bilan (pul turadi, faqat qo'lda)
```

`pytest -m live` standart ishga tushirishda va CI'da o'tkazib
yuboriladi; oxirida iboralar va model javoblari jadvali chiqadi.

## Foydali buyruqlar

| Buyruq | Vazifasi |
|---|---|
| `systemctl status tanga` | Holati |
| `systemctl restart tanga` | Qayta ishga tushirish |
| `systemctl stop tanga` | To'xtatish |
| `journalctl -u tanga -f` | Loglarni jonli kuzatish |
| `journalctl -u tanga --since "1 hour ago"` | Oxirgi 1 soatlik loglar |

## Ikkita baza va ikkita kalit

Ma'lumot **ikkita** faylda, **har xil** kalit bilan:

| Fayl | Ichida | Kalit | Kim ochadi |
|---|---|---|---|
| `/opt/tanga/tanga.db` | foydalanuvchilar, obuna, to'lov, AI sarfi | `DB_ENCRYPTION_KEY` | bot **va** admin panel |
| `/opt/tanga/tanga_shaxsiy.db` | moliyaviy yozuvlar, byudjetlar | `PRIVATE_DB_KEY` | **faqat bot** |

Ajratishning sababi: admin panel asosiy bazani bot bilan baham
ko'radi, chunki unga obuna va to'lov kerak. Yozuvlar o'sha faylda
bo'lsa panel ularni o'qiy olardi. Endi ololmaydi — kaliti yo'q.

**`PRIVATE_DB_KEY` ni `tanga-admin/.env` ga QO'YMANG.** Butun himoya
shunga tayanadi. Qo'yilsa hech qanday xato chiqmaydi — himoya jimgina
yo'qoladi.

Bot `DB_ENCRYPTION_KEY` bor-u `PRIVATE_DB_KEY` yo'q bo'lsa **ishga
tushmaydi**. Bu ataylab: bir marta zaxira yo'l asosiy kalitni olib,
butun bazani noto'g'ri kalit bilan shifrlab qo'ygan.

Yangi kalit:

```bash
python3 -c "import secrets; print(secrets.token_hex(32))"
```

## Bazani zaxiralash

`tanga-backup` skripti **ikkala** bazani ham nusxalaydi, tekshiradi,
AES-256 bilan shifrlaydi va egaga Telegramga yuboradi.

```bash
tanga-backup            # nusxa olib, egaga yuboradi
tanga-backup --local    # faqat serverda saqlaydi
```

Nusxalar `/var/backups/tanga/` da, 14 kun saqlanadi. Skriptning o'zi
repoda: `deploy/tanga-backup`.

> **Kalitlarsiz zaxira nusxa foydasiz.** Nusxalar shifrlangan, ochish
> uchun `/etc/tanga-backup.key` VA `.env` dagi ikkala baza kaliti
> kerak. Server butunlay yo'qolsa faqat nusxaning o'zi yetmaydi —
> uchalasini serverdan tashqarida ham saqlang.

## Xavfsizlik

- `.env` git'ga **hech qachon** yuborilmaydi (`.gitignore` da).
  Serverda uning huquqlari `600` — faqat egasi o'qiy oladi.
- Bot `root` sifatida emas, alohida `tanga` foydalanuvchisi ostida ishlaydi.
- `systemd` unitida `ProtectSystem=strict` va `NoNewPrivileges=true` yoqilgan —
  bot faqat o'z papkasiga yoza oladi.
- Serverga parol bilan emas, **SSH kalit** bilan kirishni yoqing va parol
  orqali kirishni o'chiring:

```bash
# Kompyuteringizda (bir marta)
ssh-keygen -t ed25519
ssh-copy-id root@SERVER_IP

# Serverda: /etc/ssh/sshd_config
#   PasswordAuthentication no
systemctl restart ssh
```

## Muammolarni bartaraf qilish

**Bot ishga tushmayapti**

```bash
journalctl -u tanga -n 50 --no-pager
```

- `.env faylida quyidagilar yo'q: ...` → `.env` to'ldirilmagan
- `Conflict: terminated by other getUpdates` → bot boshqa joyda ham ishlayapti
- `Gemini xatosi ... (status 400/403)` → `GEMINI_API_KEY` noto'g'ri yoki billing yoqilmagan
- `GEMINI_API_KEY o'rnatilmagan` → `.env` da kalit yo'q

**Vaqt mintaqasi noto'g'ri**

`.env` dagi `TIMEZONE=Asia/Tashkent` hisobotlar uchun ishlatiladi; serverning
o'z vaqti boshqa bo'lsa ham bot shu mintaqada hisoblaydi.
