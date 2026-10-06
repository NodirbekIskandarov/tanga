#!/usr/bin/env bash
# Claude -> Gemini o'tishi: serverdagi /opt/tanga/.env ni tayyorlaydi.
#
# Ishlatish (serverda, root sifatida; kalit muhit o'zgaruvchisi orqali —
# skriptga, shell tarixiga yoki gitga yozilmaydi):
#
#   read -rs NEW_GEMINI_KEY && export NEW_GEMINI_KEY   # kalitni kiriting, Enter
#   bash /opt/tanga/deploy/gemini-otish.sh
#   unset NEW_GEMINI_KEY
#
# Skript IDEMPOTENT (qayta ishga tushirsa ham xavfsiz) va quyidagilarni qiladi:
#   1. .env ning zaxira nusxasi (ruxsat 600) — qaytish yo'li uchun;
#   2. GEMINI_API_KEY ni qo'yadi (bor bo'lsa almashtiradi);
#   3. eski Claude model qatorlarini (PARSE_MODEL/CHAT_MODEL/VISION_MODEL
#      claude-* nomlari bilan) va VISION_EFFORT ni olib tashlaydi — aks holda
#      ular Gemini standartlarini bosib, AI chaqiruvlari xato bergan bo'lardi;
#   4. ANTHROPIC_API_KEY qatorini olib tashlaydi (kod uni endi o'qimaydi;
#      qaytish kerak bo'lsa zaxira nusxadan);
#   5. ruxsatni 600 va egasini tanga:tanga qiladi.
# Faqat o'zgargan qator NOMLARI chop etiladi, qiymatlar hech qachon.

set -euo pipefail

ENV_FILE="${ENV_FILE:-/opt/tanga/.env}"
BACKUP="${BACKUP:-/root/env.claude-zaxira}"

if [[ -z "${NEW_GEMINI_KEY:-}" ]]; then
    echo "XATO: NEW_GEMINI_KEY o'rnatilmagan (yuqoridagi ko'rsatmaga qarang)." >&2
    exit 1
fi
if [[ ! -f "$ENV_FILE" ]]; then
    echo "XATO: $ENV_FILE topilmadi." >&2
    exit 1
fi

# 1. Zaxira — mavjud zaxiraning ustiga yozmaydi (birinchi nusxa eng asl).
if [[ ! -f "$BACKUP" ]]; then
    (umask 077; cp "$ENV_FILE" "$BACKUP")
    chmod 600 "$BACKUP"
    echo "zaxira: $BACKUP"
else
    echo "zaxira allaqachon bor: $BACKUP (tegilmadi)"
fi

TMP="$(mktemp)"
trap 'rm -f "$TMP"' EXIT

# 3-4. Eski qatorlarni tashlab, yangisini qo'shamiz.
removed=()
while IFS= read -r line || [[ -n "$line" ]]; do
    name="${line%%=*}"
    case "$name" in
        GEMINI_API_KEY) removed+=("GEMINI_API_KEY (eski qiymat)"); continue ;;
        ANTHROPIC_API_KEY) removed+=("ANTHROPIC_API_KEY"); continue ;;
        VISION_EFFORT) removed+=("VISION_EFFORT"); continue ;;
        PARSE_MODEL|CHAT_MODEL|VISION_MODEL)
            if [[ "${line#*=}" == *claude* ]]; then
                removed+=("$name (claude-* nomi)"); continue
            fi ;;
    esac
    printf '%s\n' "$line" >> "$TMP"
done < "$ENV_FILE"
printf 'GEMINI_API_KEY=%s\n' "$NEW_GEMINI_KEY" >> "$TMP"

cat "$TMP" > "$ENV_FILE"       # inode saqlanadi
chmod 600 "$ENV_FILE"
chown tanga:tanga "$ENV_FILE" 2>/dev/null || true

echo "olib tashlandi: ${removed[*]:-hech narsa}"
echo "qo'shildi: GEMINI_API_KEY"
echo "qolgan qator nomlari:"
cut -d= -f1 "$ENV_FILE" | grep -v '^#' | grep -v '^$' | sort | sed 's/^/  /'
echo
echo "Endi: main'ga push (webhook deploy qiladi) yoki qo'lda: systemctl restart tanga tanga-webapp"
