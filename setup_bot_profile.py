"""Bot profilini Telegram API orqali sozlaydi.

Nima o'rnatiladi (har biri o'zbek va rus tillari uchun alohida):
  setMyName              — bot nomi (64 belgigacha)
  setMyShortDescription  — chat ro'yxatida va qidiruvda (120 belgigacha)
  setMyDescription       — «Start» tugmasi ustidagi matn (512 belgigacha)
  («/» menyusi — bot o'zi o'rnatadi, bu skript tegmaydi)

Ishlatish:
    python setup_bot_profile.py --dry-run    # faqat ko'rsatadi, yubormaydi
    python setup_bot_profile.py              # haqiqatan o'rnatadi
    python setup_bot_profile.py --show       # Telegramdagi hozirgi holatni o'qiydi

Token .env faylidagi TELEGRAM_TOKEN dan olinadi. U hech qachon ekranga
chiqarilmaydi va logga yozilmaydi — xatolik matnida ham niqoblanadi.
"""

from __future__ import annotations

import sys

import httpx

import config

API = "https://api.telegram.org/bot{token}/{method}"

# Matnlar profile_texts.py da — bot ham ishga tushganda shulardan o'rnatadi.
from profile_texts import DESCRIPTION, LANGS, LIMITS, NAME, SHORT  # noqa: E402

# «/» menyusini bu skript O'RNATMAYDI: uni bot o'zi boshqaradi
# (bot._post_init — bot.BOT_COMMANDS, har ishga tushishda; tilga xos eski
# ro'yxatlarni o'chiradi). Ilgari bu yerda alohida, eskirib qolgan ro'yxat
# bor edi.


def _mask(text: str, token: str) -> str:
    """Token xato matniga tushib qolsa — niqoblaymiz."""
    return text.replace(token, "<TOKEN>") if token else text


def call(client: httpx.Client, token: str, method: str, payload: dict) -> dict:
    r = client.post(API.format(token=token, method=method), json=payload, timeout=30)
    try:
        data = r.json()
    except ValueError:
        raise SystemExit(f"{method}: javob JSON emas (HTTP {r.status_code})")
    if not data.get("ok"):
        raise SystemExit(
            f"{method} XATO: {_mask(str(data.get('description', data)), token)}")
    return data["result"]


def check_lengths() -> list[str]:
    """Telegram chegaralarini oldindan tekshiradi — API xatosini kutmasdan."""
    problems = []
    for lang in LANGS:
        for field, table in (("name", NAME), ("short_description", SHORT),
                             ("description", DESCRIPTION)):
            value = table.get(lang, table[""])
            if len(value) > LIMITS[field]:
                problems.append(
                    f"{field} [{lang or 'standart'}]: {len(value)} belgi, "
                    f"chegara {LIMITS[field]}")
    return problems


def show(client: httpx.Client, token: str) -> None:
    print("Telegramdagi HOZIRGI holat:\n")
    me = call(client, token, "getMe", {})
    print(f"  bot        : @{me['username']}  (id {me['id']})")
    for lang in LANGS:
        p = {"language_code": lang} if lang else {}
        label = lang or "standart"
        name = call(client, token, "getMyName", p)["name"]
        short = call(client, token, "getMyShortDescription", p)["short_description"]
        desc = call(client, token, "getMyDescription", p)["description"]
        cmds = call(client, token, "getMyCommands", p)
        print(f"\n  [{label}]")
        print(f"    nom          : {name}")
        print(f"    qisqa tavsif : {short[:70]}{'…' if len(short) > 70 else ''}")
        print(f"    tavsif       : {desc[:70].replace(chr(10), ' ')}"
              f"{'…' if len(desc) > 70 else ''}")
        print(f"    buyruqlar    : {len(cmds)} ta")


def apply(client: httpx.Client, token: str, dry: bool) -> None:
    me = call(client, token, "getMe", {})
    print(f"Bot: @{me['username']}  (id {me['id']})\n")

    for lang in LANGS:
        label = lang or "standart"
        base = {"language_code": lang} if lang else {}
        name = NAME.get(lang, NAME[""])
        short = SHORT.get(lang, SHORT[""])
        desc = DESCRIPTION.get(lang, DESCRIPTION[""])

        print(f"[{label}]")
        print(f"  setMyName             {len(name):>3} belgi  {name}")
        print(f"  setMyShortDescription {len(short):>3} belgi")
        print(f"  setMyDescription      {len(desc):>3} belgi")

        if dry:
            print()
            continue

        call(client, token, "setMyName", {**base, "name": name})
        call(client, token, "setMyShortDescription",
             {**base, "short_description": short})
        call(client, token, "setMyDescription", {**base, "description": desc})
        print("  -> o'rnatildi\n")

    if dry:
        print("(--dry-run: hech narsa yuborilmadi)")


def main() -> None:
    token = config.TELEGRAM_TOKEN
    if not token:
        raise SystemExit(".env faylida TELEGRAM_TOKEN yo'q.")

    problems = check_lengths()
    if problems:
        print("Chegaradan oshgan matnlar:")
        for p in problems:
            print("  -", p)
        raise SystemExit(1)

    with httpx.Client() as client:
        if "--show" in sys.argv:
            show(client, token)
        else:
            apply(client, token, dry="--dry-run" in sys.argv)


if __name__ == "__main__":
    main()
