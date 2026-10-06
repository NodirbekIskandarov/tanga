# Claude bazasi (Gemini'ga o'tishdan oldingi o'lchov)

**Holat: BAJARILMAGAN.** Bu hujjatda hech qanday raqam yo'q — o'lchov
o'tkazilmagan, shuning uchun to'qib yozilmadi.

## Nega bajarilmadi

O'lchash uchun kerak:

1. haqiqiy `ANTHROPIC_API_KEY` (Claude'ning jonli kaliti) — kodni yozgan
   agentda yo'q;
2. 20 ta haqiqiy chek rasmi (`tests/live_receipts/`) — yig'ilmagan.

Matn jadvali (`tests/test_live_ai.py`, 16 ta xabar) esa shu repoda bor, uni
faqat kalit bilan ishga tushirish kerak.

## Qanday o'lchanadi (egasi bajaradi)

Eski kod `oxirgi-claude` tegida saqlangan (Anthropic bilan ishlaydi):

```bash
git worktree add ../tanga-claude oxirgi-claude
cd ../tanga-claude
python -m venv .venv && .venv/bin/pip install -r requirements-dev.txt
# yangi test fayllarini (interfeys bir xil) eski versiyaga nusxalang:
cp ../tanga/tests/test_live_receipts.py ../tanga/tests/live_results.py tests/
cp -r ../tanga/tests/live_receipts tests/
# test_live_receipts.py dagi `real_key` fixturesini tests/test_live_ai.py dagisidek
# (ANTHROPIC_API_KEY bilan) almashtiring; conftest.py ning pytest_terminal_summary
# qismi ham kerak (natijalar jadvali uchun)
ANTHROPIC_API_KEY=sk-ant-... LIVE_RESULTS_JSON=/tmp/claude-baza.json \
  .venv/bin/pytest -m live tests/test_live_ai.py tests/test_live_receipts.py
```

Natijani shu yerga yozing:

| Ko'rsatkich | Claude bazasi |
|---|---|
| Matn jadvali (to'g'ri / jami) | — |
| Chek: «jami bilan mos» ulushi | — |
| Matnli yozuv o'rtacha narxi | — |
| Chek o'rtacha narxi | — |
| Savol o'rtacha narxi | — |

Keyin `docs/gemini-baholash.md` dagi qabul mezonlari shu raqamlarga nisbatan
tekshiriladi.
