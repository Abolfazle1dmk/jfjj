#!/usr/bin/env python3
# -*- coding: utf-8 -*-
# ═══════════════════════════════════════════════════════════════════════
#  JAFJ — نصب‌کننده‌ی خودکارِ main.py   (برای میزبانی که فقط «ویرایشِ فایل»
#  دارد و ترمینال ندارد)
#
#  چرا این فایل: کپی‌کردنِ یک فایلِ ۷۰۰ خطی از صفحه‌ی مرورگر، همان دامِ
#  همیشگی را می‌سازد — «&lt;» و «&gt;» و «&amp;» داخلِ کد می‌نشیند و فایل
#  با SyntaxError می‌میرد. این‌جا فقط ۳۰ خط دستی می‌گذاری، و خودش نسخه‌ی
#  کامل و سالمِ main.py را از گیت می‌گیرد، اعتبارسنجی می‌کند، نسخه‌ی قبلی
#  را در main.py.bak نگه می‌دارد و اجرا می‌کند.
#
#  نصب:
#   ۱) کلِ این فایل را در `main.py`ِ ریشه‌ی اپ بگذار (به‌جای محتوای قبلی).
#   ۲) ری‌استارت کن.
#   ۳) آدرسِ اپ را در مرورگر باز کن → صفحه‌ی وضعیت.
#
#  اگر ریپو خصوصی است، JAFJ_GIT_TOKEN را هم ست کن (همین متغیر برای clone
#  هم استفاده می‌شود).
# ═══════════════════════════════════════════════════════════════════════
import os
import sys
import urllib.request

REPO = (os.environ.get("JAFJ_REPO") or "abolfazleoy/jfjj").strip()
BRANCH = (os.environ.get("JAFJ_BRANCH") or "main").strip() or "main"
TOKEN = (os.environ.get("JAFJ_GIT_TOKEN") or "").strip()

HERE = os.path.dirname(os.path.abspath(__file__))
TARGET = os.path.join(HERE, "main.py")
BACKUP = TARGET + ".bak"

# اول شاخه‌ی خودِ ریپو، بعد شاخه‌ای که نسخه‌ی تازه‌ی این فایل رویش هست
# (اگر merge نشده باشد، نصب باز هم کار می‌کند).
REF_PATH = "deploy/wispbyte/main.py"
# چند منبع، به ترتیب: raw شاخه‌ی ریپو → همان مسیر روی شاخه‌ای که این نسخه
# را دارد → APIِ گیت‌هاب (برای ریپوی خصوصی، با توکن).
SOURCES = [
    (f"https://raw.githubusercontent.com/{REPO}/{BRANCH}/{REF_PATH}", {}),
    ("https://raw.githubusercontent.com/"
     f"{REPO}/arena/c48dbaed-jfjj/{REF_PATH}", {}),
    (f"https://api.github.com/repos/{REPO}/contents/{REF_PATH}?ref={BRANCH}",
     {"Accept": "application/vnd.github.raw"}),
]


def log(msg):
    print(f"JAFJ-INSTALL: {msg}", flush=True)


def fetch(url, extra=None):
    hdrs = {"User-Agent": "jafj-install/1"}
    hdrs.update(extra or {})
    req = urllib.request.Request(url, headers=hdrs)
    if TOKEN:
        req.add_header("Authorization", f"Bearer {TOKEN}")
    with urllib.request.urlopen(req, timeout=60) as r:
        return r.read().decode("utf-8", "replace")


def looks_sane(src):
    """فایلِ سالم است؟ (نه HTML-escape، نه نصفه، و main دارد)"""
    if not src or len(src) < 6000:
        return False, f"خیلی کوتاه است ({len(src)} بایت)"
    for ent in ("&lt;", "&gt;", "&amp;"):
        if ent in src:
            return False, f"موجودیتِ HTML داخلِ فایل هست ({ent})"
    if "def main(" not in src or "status_html" not in src:
        return False, "ساختارِ فایلِ main.py نیست"
    try:
        compile(src, "main.py", "exec")
    except SyntaxError as e:
        return False, f"SyntaxError خط {e.lineno}: {e.msg}"
    return True, ""


def save(src):
    """نسخه‌ی قبلی را نگه دار، بعد بنویس (نوشتنِ اتمیک)."""
    try:
        if os.path.isfile(TARGET):
            with open(TARGET, encoding="utf-8", errors="ignore") as f:
                old = f.read()
            if old.strip() and "JAFJ-INSTALL" not in old:
                with open(BACKUP, "w", encoding="utf-8") as f:
                    f.write(old)
                log(f"نسخه‌ی قبلی در {os.path.basename(BACKUP)} ذخیره شد")
    except Exception as e:
        log(f"⚠️ پشتیبان‌گیری نشد ({type(e).__name__}: {e}) — ادامه می‌دهم")
    tmp = TARGET + ".tmp"
    with open(tmp, "w", encoding="utf-8") as f:
        f.write(src)
    os.replace(tmp, TARGET)


def main():
    log(f"repo={REPO} branch={BRANCH} dir={HERE}")
    errors = []
    for url, extra in SOURCES:
        if not url:
            continue
        short = url.split("//", 1)[-1][:90]
        try:
            src = fetch(url, extra)
        except Exception as e:
            errors.append(f"{short} → {type(e).__name__}: {e}")
            log(f"⚠️ دانلود نشد: {short} ({type(e).__name__})")
            continue
        ok, why = looks_sane(src)
        if not ok:
            errors.append(f"{short} → {why}")
            log(f"⚠️ فایلِ دانلودشده سالم نیست: {short} — {why}")
            continue
        save(src)
        log(f"✅ main.py از {short} به‌روز شد ({len(src)} بایت)")
        os.execv(sys.executable, [sys.executable, TARGET] + sys.argv[1:])
        return 0

    log("⛔ نصبِ main.py انجام نشد. علت‌ها:")
    for e in errors:
        log(f"   - {e}")
    log("   راهِ حل: دسترسی به github.com (یا صفر بودنِ JAFJ_REPO) را چک کن؛ "
        "اگر ریپو خصوصی است JAFJ_GIT_TOKEN را بده.")
    # نسخه‌ی قبلی اگر وجود دارد، لااقل همان اجرا شود
    if os.path.isfile(BACKUP):
        log(f"↩️ اجرای نسخه‌ی قبلی از {os.path.basename(BACKUP)}")
        try:
            with open(BACKUP, encoding="utf-8", errors="ignore") as f:
                old = f.read()
            compile(old, "main.py", "exec")
            with open(TARGET, "w", encoding="utf-8") as f:
                f.write(old)
            os.execv(sys.executable, [sys.executable, TARGET] + sys.argv[1:])
        except Exception as e:
            log(f"⚠️ نسخه‌ی قبلی هم اجرا نشد: {type(e).__name__}: {e}")
    return 1


if __name__ == "__main__":
    sys.exit(main())
