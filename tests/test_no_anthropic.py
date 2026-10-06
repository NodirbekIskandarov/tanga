"""Loyihada Anthropic/Claude qolmagani: kod, bog'liqlik, sozlama, matn.

Istisnolar (o'zgartirilmaydi): .git tarixi; bazadagi eski `usage_log`
qatorlari (kodda emas); `docs/` dagi tarixiy audit hisobotlari; DEPLOY.md
dagi «O'tish kuni» bo'limi va deploy/gemini-otish.sh (u eski kalitni o'chirishni aynan shu nom bilan
tushuntiradi).
"""

import ast
import re
import subprocess
from pathlib import Path

import pytest

import config

ROOT = Path(__file__).resolve().parents[1]
# «opus» faqat model nomi sifatida (Opus 5): audio/opus — Telegram ovozining kodek nomi.
PATTERN = re.compile(r"anthropic|claude|haiku|sonnet|sk-ant|\bopus[- ]?\d", re.I)


def _tracked_files() -> list[Path]:
    try:
        out = subprocess.run(["git", "ls-files"], cwd=ROOT, capture_output=True,
                             text=True, check=True).stdout
    except (OSError, subprocess.CalledProcessError):
        pytest.skip("git yo'q")
    files = []
    for name in out.splitlines():
        path = ROOT / name
        if path.is_file():
            files.append(path)
    return files


def test_no_module_imports_anthropic():
    for path in _tracked_files():
        if path.suffix != ".py":
            continue
        tree = ast.parse(path.read_text(encoding="utf-8"), filename=str(path))
        for node in ast.walk(tree):
            names = []
            if isinstance(node, ast.Import):
                names = [a.name for a in node.names]
            elif isinstance(node, ast.ImportFrom):
                names = [node.module or ""]
            assert not any(n.split(".")[0] == "anthropic" for n in names), \
                f"{path.name}: anthropic import qilingan"


def test_requirements_have_no_anthropic():
    for path in ROOT.glob("requirements*.txt"):
        assert "anthropic" not in path.read_text(encoding="utf-8").lower(), path.name
    assert "google-genai" in (ROOT / "requirements.txt").read_text(encoding="utf-8")


def test_config_has_no_anthropic_leftovers():
    for name in ("ANTHROPIC_API_KEY", "CACHE_READ_MULTIPLIER", "CACHE_WRITE_MULTIPLIER",
                 "VISION_EFFORT"):
        assert not hasattr(config, name), name
    assert hasattr(config, "GEMINI_API_KEY")
    for model in list(config.MODEL_PRICES) + [config.PARSE_MODEL, config.VOICE_MODEL,
                                              config.CHAT_MODEL, config.VISION_MODEL]:
        assert model.startswith("gemini-"), model


def _deploy_without_migration_section(text: str) -> str:
    a = text.index("## O'tish kuni")
    b = text.index("\n## ", a + 5)
    return text[:a] + text[b:]


def test_repository_text_has_no_anthropic_words():
    offenders = []
    for path in _tracked_files():
        rel = path.relative_to(ROOT).as_posix()
        # gemini-otish.sh eski kalit va modellarni serverdan olib tashlaydi —
        # ularni aynan nomi bilan aytishi kerak.
        if rel.startswith("docs/") or rel in ("tests/test_no_anthropic.py",
                                              "deploy/gemini-otish.sh"):
            continue
        if path.suffix.lower() in (".png", ".ico", ".jpg", ".jpeg", ".gif", ".webp",
                                   ".woff", ".woff2", ".ttf", ".db", ".ogg", ".pdf"):
            continue
        try:
            text = path.read_text(encoding="utf-8")
        except UnicodeDecodeError:
            continue
        if rel == "DEPLOY.md":
            text = _deploy_without_migration_section(text)
        for n, line in enumerate(text.splitlines(), 1):
            if PATTERN.search(line):
                offenders.append(f"{rel}:{n}: {line.strip()[:80]}")
    assert not offenders, "\n".join(offenders)


def test_user_texts_name_google_not_anthropic():
    import i18n
    for lang in ("uz", "ru"):
        for key in ("consent", "privacy"):
            text = i18n.t(lang, key, contact="@x")
            assert "Google" in text and not PATTERN.search(text), (lang, key)
