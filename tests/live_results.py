"""Jonli test natijalari — sessiya oxirida jadval qilib chiqariladi."""

RESULTS: list[tuple[str, str, str, str, bool]] = []

# Qo'shimcha ko'rsatkichlar (masalan {"chek_mos": 0.85}) — baholash
# hujjati uchun; LIVE_RESULTS_JSON o'rnatilsa shu fayl ham yoziladi.
SUMMARY: dict[str, float] = {}
