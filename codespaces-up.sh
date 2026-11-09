#!/bin/sh
# ═══════════════════════════════════════════════════════════════════════════
#  codespaces را بالا بیاور.
#
#  این اسکریپت روی لپ‌تاپ/کامپیوتر خودت اجرا می‌شود (نه داخل codespace) و
#  با gh CLI سه کار می‌کند:
#
#    ۱) codespace را می‌سازد (اگر نبود) یا روشن می‌کند (اگر خاموش بود)؛
#    ۲) پورتِ سلامت (۸۰۸۰) را public می‌کند تا از بیرون هم دیده شود؛
#    ۳) آدرسِ آنلاین را چاپ می‌کند.
#
#  استفاده:
#      sh codespaces-up.sh
#
#  متغیرهای اختیاری:
#      JAFJ_REPO=abolfazleoy/jfjj   JAFJ_BRANCH=main
#      JAFJ_CODESPACE_NAME=jafj     JAFJ_CODESPACE_MACHINE=standardLinux
#      JAFJ_CODESPACE_IDLE=4h       (حداکثرِ بی‌کاری قبل از خاموشی)
# ═══════════════════════════════════════════════════════════════════════════
set -eu

REPO="${JAFJ_REPO:-Abolfazle1dmk/jfjj}"
BRANCH="${JAFJ_BRANCH:-main}"
DISPLAY="${JAFJ_CODESPACE_NAME:-jafj}"
MACHINE="${JAFJ_CODESPACE_MACHINE:-standardLinux}"
IDLE="${JAFJ_CODESPACE_IDLE:-4h}"
PORT="${PORT:-8080}"

log() { echo "CODESPACES-UP: $*"; }
die() { echo "ERROR: $*" >&2; exit 1; }

command -v gh >/dev/null 2>&1 || die "gh CLI نصب نیست — https://cli.github.com"
gh auth status >/dev/null 2>&1 || die "با gh login وارد گیت‌ساب نشده‌ای"

state_of() {
    gh codespace list --json name,state --jq \
        ".[] | select(.name == \"$1\") | .state" 2>/dev/null | head -1 || true
}

# ── ۱) codespace موجود داریم؟ ─────────────────────────────────────────────
CS="$(gh codespace list -R "$REPO" --json name,displayName --jq \
      ".[] | select(.displayName == \"$DISPLAY\") | .name" 2>/dev/null | head -1 || true)"

if [ -n "$CS" ]; then
    log "codespace از قبل هست: $CS"
    st="$(state_of "$CS")"
    if [ "$st" != "Running" ]; then
        if gh codespace start -c "$CS" >/dev/null 2>&1; then
            log "روشن شد"
        else
            log "می‌شود روشن نشد — در پنلِ Codespaces دکمهٔ Start را بزن"
        fi
    fi
else
    log "در حال ساخت codespace روی $REPO@$BRANCH — چند دقیقه طول می‌کشد…"
    out="$(gh codespace create -R "$REPO" -b "$BRANCH" -m "$MACHINE" \
            --display-name "$DISPLAY" --idle-timeout "$IDLE" 2>&1)" || {
        echo "$out" >&2
        die "ساخت codespace ناموفق بود — به دسترسیِ Codespaces (توکن/اکانت) نیاز دارد"
    }
    CS="$(printf '%s\n' "$out" | tail -1 | tr -d '[:space:]')"
    [ -n "$CS" ] || die "نامِ codespace از خروجی درنیامد: $out"
    log "ساخته شد: $CS"
fi

# ── ۲) منتظرِ Running شدن ─────────────────────────────────────────────────
i=0
while [ "$i" -lt 90 ]; do
    st="$(state_of "$CS")"
    [ "$st" = "Running" ] && break
    sleep 5
    i=$((i + 1))
done
[ "$(state_of "$CS")" = "Running" ] || log "هنوز Running نشده — کمی بعد وضعیت را ببین"
log "وضعیت: $(state_of "$CS")"

# ── ۳) پورتِ سلامت را public کن ───────────────────────────────────────────
if gh codespace ports visibility "${PORT}:public" -c "$CS" >/dev/null 2>&1; then
    log "پورت $PORT عمومی شد"
else
    log "پورت را از پنلِ Ports در codespace خودت روی Public بگذار"
fi

echo
echo "─────────────────────────────────────────────"
echo " آدرسِ آنلاین:"
echo "   https://${CS}-${PORT}.app.github.dev/healthz"
echo "   https://${CS}-${PORT}.app.github.dev/version"
echo
echo " بعدش:"
echo "   • اسکریت‌ها را در terminal بگذار (BOT_TOKEN و DATA_GITHUB_TOKEN):"
echo "       gh secret set BOT_TOKEN --user"
echo "       gh secret set DATA_GITHUB_TOKEN --user"
echo "   • لاگ:  gh codespace ssh -c $CS -- cat ~/jafj-data/bot.log"
echo "─────────────────────────────────────────────"
