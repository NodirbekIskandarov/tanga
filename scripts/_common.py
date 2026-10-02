"""Ma'lumot migratsiyalari uchun umumiy qism.

Qoidalar (hamma skriptga tegishli):
  * Standart rejim — `--dry-run`: hech narsa yozilmaydi, faqat nima
    o'zgarishi ko'rsatiladi. Yozish uchun `--apply` ochiq aytilishi shart.
  * `--apply` o'zgartirishdan OLDIN o'zgaradigan qatorlarning asl
    holatini `migration_backups/` ga JSON qilib yozadi.
  * `--rollback FAYL` shu JSON bo'yicha hammasini avvalgi holatiga
    qaytaradi.

Skriptlar loyiha ildizidan ishga tushiriladi va bot bilan bir xil `.env`
ni o'qiydi (baza kalitlari ham o'sha yerdan) — shifrlash va zaxira
tizimiga tegilmaydi.
"""

from __future__ import annotations

import argparse
import json
import os
import sys
from datetime import datetime
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(ROOT))
os.chdir(ROOT)

# Chiqishda o'zbekcha belgilar (', «», —) har qanday konsolda o'qilsin.
try:
    sys.stdout.reconfigure(encoding="utf-8")
except (AttributeError, ValueError):
    pass

BACKUP_DIR = ROOT / "migration_backups"


def parser(description: str) -> argparse.ArgumentParser:
    p = argparse.ArgumentParser(description=description)
    mode = p.add_mutually_exclusive_group()
    mode.add_argument("--dry-run", action="store_true", default=True,
                      help="faqat ko'rsatish (standart)")
    mode.add_argument("--apply", action="store_true",
                      help="o'zgarishlarni bazaga yozish")
    mode.add_argument("--rollback", metavar="FAYL",
                      help="--apply yaratgan zaxira fayl bo'yicha qaytarish")
    return p


def write_backup(name: str, payload: dict) -> Path:
    BACKUP_DIR.mkdir(exist_ok=True)
    path = BACKUP_DIR / f"{name}-{datetime.now():%Y%m%d-%H%M%S}.json"
    path.write_text(json.dumps(payload, ensure_ascii=False, indent=1),
                    encoding="utf-8")
    try:
        os.chmod(path, 0o600)
    except OSError:
        pass
    return path


def read_backup(path: str, name: str) -> dict:
    payload = json.loads(Path(path).read_text(encoding="utf-8"))
    if payload.get("migration") != name:
        raise SystemExit(f"Bu fayl '{name}' migratsiyasiga tegishli emas: {path}")
    return payload


def banner(dry: bool) -> None:
    print("=" * 60)
    print("DRY-RUN — bazaga hech narsa yozilmaydi" if dry
          else "APPLY — o'zgarishlar bazaga yoziladi")
    print("=" * 60)
