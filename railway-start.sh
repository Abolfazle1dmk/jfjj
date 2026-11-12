#!/bin/sh
# ═══════════════════════════════════════════════════════════════════════════
#  Railway entrypoint for the JAFJ manager.
#
#  Two failure modes this script exists to prevent:
#
#  1) STALE CODE.  A Railway Volume mounted at /app hides everything the image
#     put in /app and keeps whatever the Volume already held. The container
#     then boots the OLD manager_82.py from the Volume on every redeploy, so a
#     fix never arrives and each self start still fails with
#     "به‌روزرسانی فایل سلف نشد: فایل 95.py پیدا نشد".
#     /opt/jafj is part of the image and cannot be shadowed by a Volume, so the
#     code is ALWAYS executed from there; the Volume only stores data.
#
#  2) CRASH LOOP.  Every manager exit used to exit the container, Railway
#     restarted it, and the same failure (Telegram login, FloodWait, leftover
#     lock file, empty Volume) repeated forever. The manager is supervised
#     here now: it is restarted in place, and only repeated instant crashes are
#     handed back to Railway's own restart policy.
# ═══════════════════════════════════════════════════════════════════════════
set -eu

IMAGE_DIR="${JAFJ_IMAGE_DIR:-/opt/jafj}"     # immutable, inside the image
APP_DIR="${JAFJ_APP_DIR:-/app}"              # usually where the Volume is
MANAGER_NAME="manager_82.py"
SELF_NAME="95.py"

log() { echo "SELFBOOT: $*"; }

# آیا این پوشه‌ی داده، یک نسخه‌ی قابل‌اجرا از کد را نگه داشته است؟
# (دیسک/Volume مانت‌شده روی مسیرِ کد = هر دیپلوی بی‌اثر)
_code_shadow() {
    _d="$1"
    [ -n "$_d" ] || return 1
    [ -f "$_d/$MANAGER_NAME" ] || return 1
    [ "$_d" = "$IMAGE_DIR" ] && return 1
    [ -f "$IMAGE_DIR/$MANAGER_NAME" ] || return 1
    return 0
}

pick_python() {
    # ۱) env 변수 PYTHON
    if [ -n "${PYTHON:-}" ] && command -v "$PYTHON" >/dev/null 2>&1; then
        echo "$PYTHON"
        return
    fi
    # ۲) venv یا .venv کنار کد (تصمیم‌گیری‌ی مهم: telethon در venv نصب است)
    for base in "$IMAGE_DIR" "$APP_DIR" "." "$HOME"; do
        for name in venv .venv; do
            v="$base/$name/bin/python"
            if [ -x "$v" ]; then
                echo "$v"
                return
            fi
        done
    done
    # ۳) پایتون سیستمی
    for c in python3 python; do
        if command -v "$c" >/dev/null 2>&1; then
            echo "$c"
            return
        fi
    done
    echo python3
}
PY="$(pick_python)"

# ── 1) where does the data live? (Volume wins, image dir is a last resort) ──
if [ -z "${DATA_DIR:-}" ]; then
    if [ -d "$APP_DIR" ] && [ -w "$APP_DIR" ] && ! _code_shadow "$APP_DIR"; then
        DATA_DIR="$APP_DIR"
    else
        if [ -d "$APP_DIR" ] && _code_shadow "$APP_DIR"; then
            log "WARNING: $APP_DIR holds a copy of $MANAGER_NAME — a disk mounted over the code makes every deploy look useless; prefer DATA_DIR=/data"
        fi
        DATA_DIR="${JAFJ_DATA_MOUNT:-/data}"
        if ! mkdir -p "$DATA_DIR" 2>/dev/null || [ ! -w "$DATA_DIR" ]; then
            if [ -d "$APP_DIR" ] && [ -w "$APP_DIR" ]; then
                DATA_DIR="$APP_DIR"
            else
                DATA_DIR="$IMAGE_DIR"
            fi
        fi
    fi
elif _code_shadow "${DATA_DIR:-}"; then
    log "WARNING: DATA_DIR=$DATA_DIR holds a copy of $MANAGER_NAME — that copy is NEVER executed. If redeploys look useless, move the disk: DATA_DIR=/data"
fi
# manager_82.py resolves DATA_DIR against cwd; make it absolute so a relative
# value keeps meaning the same place it did when the code ran from /app.
mkdir -p "$DATA_DIR" 2>/dev/null || true
_abs="$(cd "$DATA_DIR" 2>/dev/null && pwd)" && DATA_DIR="$_abs"
export DATA_DIR

# ── 2) the code always comes from the image ──────────────────────────────────
MANAGER="$IMAGE_DIR/$MANAGER_NAME"
SELF="$IMAGE_DIR/$SELF_NAME"
export JAFJ_SELFBOT_REF="${JAFJ_SELFBOT_REF:-$SELF}"

if [ ! -f "$MANAGER" ]; then
    # Old image without /opt/jafj: fall back to a surviving copy instead of
    # dying in a restart loop.
    if [ -f "$DATA_DIR/$MANAGER_NAME" ]; then
        MANAGER="$DATA_DIR/$MANAGER_NAME"
        log "WARNING: $IMAGE_DIR/$MANAGER_NAME missing — running the copy in $DATA_DIR (rebuild the image)"
    else
        echo "ERROR: no $MANAGER_NAME in $IMAGE_DIR or $DATA_DIR — image is broken or too old, redeploy." >&2
        exit 1
    fi
fi
if [ ! -s "$SELF" ]; then
    log "WARNING: $SELF is missing from the image — self bots cannot start until the image is rebuilt"
fi
# A stale copy in the Volume is not used; say so, because that is exactly what
# made previous redeploys look like they did nothing.
if [ "$DATA_DIR" != "$IMAGE_DIR" ] && [ -f "$DATA_DIR/$MANAGER_NAME" ] \
        && ! cmp -s "$MANAGER" "$DATA_DIR/$MANAGER_NAME" 2>/dev/null; then
    log "note: $DATA_DIR/$MANAGER_NAME differs from the image copy and is NOT executed"
fi

log "code=$IMAGE_DIR data=$DATA_DIR python=$PY self=$([ -s "$SELF" ] && echo ok || echo MISSING)"

# چه چیزی دارد اجرا می‌شود؟ بعد از مرج، تنها سؤالِ واقعی این است که «دیپلوی شد
# یا نه». کامیت را از متغیرهای خودِ میزبان (Render/Railway) یا از gitِ محلی
# می‌خوانیم، صادر می‌کنیم (تا manager_82.py و /version همان را بگویند) و در
# لاگِ بوت هم می‌نویسیم — دیگر لازم نیست برای فهمیدنِ نسخه، لاگ‌ها را بگردی.
if [ -z "${JAFJ_COMMIT:-}" ]; then
    for _k in RENDER_GIT_COMMIT RAILWAY_GIT_COMMIT HEROKU_SLUG_COMMIT SOURCE_COMMIT; do
        eval "_v=\${$_k:-}"
        if [ -n "$_v" ]; then JAFJ_COMMIT="$(printf '%s' "$_v" | cut -c1-12)"; break; fi
    done
fi
if [ -z "${JAFJ_COMMIT:-}" ] && command -v git >/dev/null 2>&1; then
    JAFJ_COMMIT="$(git -C "$IMAGE_DIR" rev-parse --short HEAD 2>/dev/null | cut -c1-12)"
fi
if [ -z "${JAFJ_COMMIT:-}" ]; then JAFJ_COMMIT="unknown"; fi
export JAFJ_COMMIT
# اثرانگشتِ محتوای کد (بدونِ نیاز به git): با هر تغییرِ کد عوض می‌شود، پس اگر
# دیپلوی بی‌اثر مانده باشد همان عددِ قبلی می‌ماند و فوراً دیده می‌شود.
if command -v sha256sum >/dev/null 2>&1; then
    JAFJ_CODE_ID="$(cat "$MANAGER" "$SELF" 2>/dev/null | sha256sum | cut -c1-8)"
elif command -v shasum >/dev/null 2>&1; then
    JAFJ_CODE_ID="$(cat "$MANAGER" "$SELF" 2>/dev/null | shasum -a 256 | cut -c1-8)"
fi
if [ -z "${JAFJ_CODE_ID:-}" ]; then JAFJ_CODE_ID="unknown"; fi
export JAFJ_CODE_ID
log "build=$(grep -m1 '^BUILD_VERSION' "$MANAGER" 2>/dev/null | cut -d'"' -f2) commit=$JAFJ_COMMIT code=$JAFJ_CODE_ID manager=$MANAGER (GET /version on the service URL shows the same)"

# ── 2.5) GitHub data sync: اطلاعات مشتری‌ها از/به گیت‌هاب ────────────────────
# اگر DATA_GITHUB_TOKEN تنظیم نشده باشد، هیچ اتفاقی نمی‌افتد (اختیاری است).
SYNC="$IMAGE_DIR/tools/gh_data_sync.py"
SYNC_PID=0
stop_sync() {
    if [ "$SYNC_PID" -gt 0 ]; then
        kill -TERM "$SYNC_PID" 2>/dev/null || true
        _i=0
        while [ "$_i" -lt 5 ] && kill -0 "$SYNC_PID" 2>/dev/null; do
            sleep 1
            _i=$((_i + 1))
        done
        kill -KILL "$SYNC_PID" 2>/dev/null || true
        SYNC_PID=0
    fi
}
# ذخیره‌ی دوره‌ای + ذخیره‌ی پایانی هنگام خاموشی — یک تابع، تا بعد از هر
# کرش هم دوباره راه بیفتد (وگرنه بعد از یک بار pushِ نجات، سینکِ دوره‌ای
# تا آخرِ عمرِ کانتینر خاموش می‌ماند).
start_sync() {
    if [ -z "${DATA_GITHUB_TOKEN:-}" ] || [ ! -f "$SYNC" ]; then
        return 0
    fi
    if [ "${SYNC_PID:-0}" -gt 0 ] && kill -0 "$SYNC_PID" 2>/dev/null; then
        return 0
    fi
    "$PY" "$SYNC" loop &
    SYNC_PID=$!
    log "gh_data_sync: ذخیره‌ی دوره‌یی شروع شد (pid=$SYNC_PID)"
    return 0
}

if [ -n "${DATA_GITHUB_TOKEN:-}" ] && [ -f "$SYNC" ]; then
    # قبل از بوت: اطلاعات را از ریپوی گیت‌هاب برگردان (دیپلوی → wipe → بازیابی)
    if "$PY" "$SYNC" pull; then
        log "gh_data_sync: بازیابی از گیت‌هاب انجام شد"
    else
        log "WARNING: gh_data_sync pull ناموفق بود — با داده‌های فعلی ادامه می‌دهیم"
    fi
    start_sync
fi

# ── 3) run it ───────────────────────────────────────────────────────────────
if [ "${JAFJ_SUPERVISE:-1}" = "0" ]; then
    cd "$DATA_DIR" 2>/dev/null || true
    exec "$PY" "$MANAGER"
fi

CHILD=0
STOPPING=0
forward() {
    STOPPING=1
    if [ "$CHILD" -gt 0 ]; then
        kill -TERM "$CHILD" 2>/dev/null || true
    fi
    return 0
}
trap forward TERM INT

crashes=0
MAX_CRASHES="${JAFJ_MAX_CRASHES:-5}"      # پشت‌سرهم → تحویل به Railway
NAP_BASE="${JAFJ_NAP_BASE:-5}"            # ثانیه، هر کرش ۵ تا بیشتر
CRASH_WINDOW="${JAFJ_CRASH_WINDOW:-20}"   # کمتر از این = کرش سریع

# ── never give up: روی میزبانی که خودش ری‌استارت نمی‌کند ───────────────────
# «تسلیم شدن» روی Railway/Render درست است (پلتفرم خودش ری‌استارت می‌دهد و
# دیپلوی بد را برمی‌گرداند). روی Wispbyte/hostless/blitz معنی‌اش این است:
# پروسه می‌میرد، پنل «Offline» می‌ماند و هیچ‌کس دوباره استارتش نمی‌کند —
# همان «بعد از مدتی استفاده آفلاین شد». با JAFJ_NEVER_GIVE_UP=1 (پیش‌فرضِ
# بوت‌استرپِ همین ریپو روی Wispbyte) به‌جای مردن، خوابِ کوتاه می‌کنیم و
# دوباره از صفر شروع می‌کنیم.
_num_or() { case "$1" in ''|*[!0-9]*) printf '%s' "$2" ;; *) printf '%s' "$1" ;; esac; }
NEVER_GIVE_UP="${JAFJ_NEVER_GIVE_UP:-0}"
case "$(printf '%s' "$NEVER_GIVE_UP" | tr '[:upper:]' '[:lower:]')" in
    1|true|yes|on) NEVER_GIVE_UP=1 ;;
    *)             NEVER_GIVE_UP=0 ;;
esac
COOL_DOWN="$(_num_or "${JAFJ_COOL_DOWN:-300}" 300)"

# خوابِ تکه‌تکه: با SIGTERM فوراً برمی‌گردیم. `sleep 300` یک‌تکه، خاموشیِ
# دیپلوی را تا آخرِ خواب عقب می‌انداخت و میزبان با SIGKILL می‌بست.
nap_wait() {
    _left="$(_num_or "${1:-0}" 0)"
    while [ "$_left" -gt 0 ] && [ "$STOPPING" != 1 ]; do
        sleep 1
        _left=$((_left - 1))
    done
    return 0
}

# ── keep-alive: «خروجِ تمیز» هم نباید سرویس را بخواباند ────────────────────
# روی میزبان، مردنِ پروسه = سرویسِ مرده. اگر مدیر با کد ۰ تمام شود (مثلاً
# اتصالِ تلگرام قطع شود و نسخه‌ی قدیمیِ کد مستقیم return 0 کند)، میزبان پیامِ
# گمراه‌کننده‌ی «The process stopped soon after it started · Exit code 0»
# را نشان می‌دهد و ربات خاموش می‌مانَد. پس روی میزبان (JAFJ_HOSTED=1 که در
# Dockerfile ست شده) خروجِ ۰ هم مثل کرش شمرده و ری‌استارت می‌شود.
# روی اجرای دستی می‌شود با JAFJ_KEEP_ALIVE=0 به رفتارِ قبلی برگشت.
KEEP_ALIVE="${JAFJ_KEEP_ALIVE:-}"
if [ -z "$KEEP_ALIVE" ]; then
    case "$(printf '%s' "${JAFJ_HOSTED:-0}" | tr '[:upper:]' '[:lower:]')" in
        1|true|yes|on) KEEP_ALIVE=1 ;;
        *)             KEEP_ALIVE=0 ;;
    esac
fi
while :; do
    # اگر وسطِ خواب سیگنالِ خاموشی آمد، مدیر را دوباره بالا نیاور.
    if [ "$STOPPING" = 1 ]; then
        stop_sync
        exit 0
    fi
    cd "$DATA_DIR" 2>/dev/null || true
    "$PY" "$MANAGER" &
    CHILD=$!
    started=$(date +%s)
    set +e
    wait "$CHILD"
    code=$?
    # a trapped signal interrupts wait; keep waiting while the child lives
    while [ "$code" -gt 128 ] && kill -0 "$CHILD" 2>/dev/null; do
        wait "$CHILD"
        code=$?
    done
    set -e
    CHILD=0

    if [ "$STOPPING" = 1 ]; then
        stop_sync
        exit "$code"
    fi
    if [ "$code" = 0 ]; then
        if [ "$KEEP_ALIVE" != "1" ]; then
            log "manager exited cleanly"
            stop_sync
            exit 0
        fi
        # روی میزبان: خروجِ ۰ هم یعنی سرویس مرده. متغیر را برای مسیرِ کرش
        # نگه می‌داریم تا لاگ بگوید «۰ بود، به‌عنوان کرش شمرده شد».
        clean_code=0
        log "manager exited with code 0 — a bot service must keep running, so this counts as a crash (JAFJ_KEEP_ALIVE=0 to allow a clean stop)"
        code=75
    fi

    # ── خروجِ غیرصفر = کرش ────────────────────────────────────────────
    # ۱) دلیلش را جایی بنویس که بوتِ بعدی بتواند به مدیر نشان دهد
    #    (/diag و پیامِ «بالا آمد» از همین .jafj_last_exit و crash.log می‌خوانند).
    # ۲) داده‌های چند ثانیه‌ی آخر را بیرون بفرست: خودِ manager هم موقع مرگ
    #    تلاش می‌کند، ولی اگر OOM/SIGKILL بوده هیچ کدی اجرا نمی‌شود و این
    #    تنها شانسِ نجاتِ داده است.
    ran=$(( $(date +%s) - started ))
    # کدِ واقعیِ مدیر را ثبت کن؛ اگر خروجِ ۰ «کرش» شمرده شد، همان ۰ ثبت شود
    # تا /diag و پیامِ «بالا آمد» چیزِ گمراه‌کننده‌ای (۷۵) نشان ندهند.
    noted_code="$code"
    if [ -n "${clean_code:-}" ]; then noted_code="$clean_code"; fi
    {
        printf '{"code": %s, "uptime": %s, "ts": %s, "note": "supervisor", "build": "shell"}\n' \
            "$noted_code" "$ran" "$(date +%s)" > "$DATA_DIR/.jafj_last_exit.tmp" 2>/dev/null \
            && mv "$DATA_DIR/.jafj_last_exit.tmp" "$DATA_DIR/.jafj_last_exit" 2>/dev/null
    } || true
    {
        printf '\n===== %s [supervisor] exit=%s after %ss =====\n' \
            "$(date '+%Y-%m-%d %H:%M:%S')" "$noted_code" "$ran" \
            >> "$DATA_DIR/crash.log"
    } 2>/dev/null || true

    clean_code=
    if [ -n "${DATA_GITHUB_TOKEN:-}" ] && [ -f "$SYNC" ]; then
        log "کرش — ذخیره‌ی نجاتِ داده در گیت‌هاب…"
        # ناظرِ سینک را متوقف کن تا با push تداخل نکند (قفل فایل ندارد).
        stop_sync
        if command -v timeout >/dev/null 2>&1; then
            if timeout 90 "$PY" "$SYNC" push; then
                log "ذخیره‌ی نجات انجام شد"
            else
                log "WARNING: ذخیره‌ی نجات ناموفق بود"
            fi
        else
            if "$PY" "$SYNC" push; then
                log "ذخیره‌ی نجات انجام شد"
            else
                log "WARNING: ذخیره‌ی نجات ناموفق بود"
            fi
        fi
        start_sync          # سینکِ دوره‌ای دوباره راه بیفتد
    fi

    if [ "$ran" -lt "$CRASH_WINDOW" ]; then
        crashes=$((crashes + 1))
    else
        crashes=0
    fi
    if [ "$crashes" -ge "$MAX_CRASHES" ]; then
        if [ "$NEVER_GIVE_UP" = "1" ]; then
            log "manager crashed $crashes times in a row — NOT giving up (JAFJ_NEVER_GIVE_UP=1): nobody on this host would start it again, so the panel would just say Offline; cooling down ${COOL_DOWN}s then starting fresh"
            crashes=0
            nap_wait "$COOL_DOWN"
            continue
        fi
        log "manager crashed $crashes times in a row — giving up so Railway reports it"
        stop_sync
        exit "$code"
    fi
    nap=$(( NAP_BASE * (crashes + 1) ))
    if [ "$nap" -gt 60 ]; then
        nap=60
    fi
    log "manager exited with code $code after ${ran}s — restarting in ${nap}s"
    nap_wait "$nap"
done
