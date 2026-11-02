#!/usr/bin/env python3
# -*- coding: utf-8 -*-
# JAFJ — نصب‌کننده‌ی main.py
# این فایل را به‌جای main.py بگذار و ری‌استارت کن.
# خودش نسخه‌ی کامل و سالمِ main.py را از گیت می‌گیرد، چک می‌کند که
# HTML-escape و نصفه نباشد، نسخه‌ی قبلی را main.py.bak می‌کند و اجرا می‌کند.
import os
import sys
import urllib.request

REPO = (os.environ.get("JAFJ_REPO") or "abolfazleoy/jfjj").strip()
TOK = (os.environ.get("JAFJ_GIT_TOKEN") or "").strip()
HERE = os.path.dirname(os.path.abspath(__file__))
DST = os.path.join(HERE, "main.py")
P = "deploy/wispbyte/main.py"

URLS = [
    "https://raw.githubusercontent.com/%s/main/%s" % (REPO, P),
    "https://raw.githubusercontent.com/%s/arena/c48dbaed-jfjj/%s" % (REPO, P),
    "https://api.github.com/repos/%s/contents/%s?ref=main" % (REPO, P),
    "https://api.github.com/repos/%s/contents/%s?ref=arena/c48dbaed-jfjj"
    % (REPO, P),
]


def log(m):
    print("JAFJ-INSTALL: " + m, flush=True)


def get(url):
    h = {"User-Agent": "jafj-install"}
    if "api.github.com" in url:
        h["Accept"] = "application/vnd.github.raw"
    if TOK:
        h["Authorization"] = "Bearer " + TOK
    req = urllib.request.Request(url, headers=h)
    with urllib.request.urlopen(req, timeout=60) as r:
        return r.read().decode("utf-8", "replace")


def why_bad(src):
    """اگر فایل قابلِ استفاده نیست، دلیلش؛ وگرنه رشته‌ی خالی."""
    if not src or len(src) < 6000:
        return "خیلی کوتاه است (%d بایت)" % len(src)
    for ent in ("&lt;", "&gt;", "&amp;"):
        if ent in src:
            return "HTML-escape دارد (%s)" % ent
    if "def main(" not in src:
        return "ساختارِ main.py را ندارد"
    try:
        compile(src, "main.py", "exec")
    except SyntaxError as e:
        return "SyntaxError خط %s: %s" % (e.lineno, e.msg)
    return ""


def install(src):
    """نوشتنِ اتمیک + نگه‌داشتنِ نسخه‌ی قبلی."""
    if os.path.isfile(DST):
        try:
            with open(DST, encoding="utf-8", errors="ignore") as f:
                old = f.read()
            if "JAFJ-INSTALL" not in old:
                with open(DST + ".bak", "w", encoding="utf-8") as f:
                    f.write(old)
                log("نسخه‌ی قبلی → main.py.bak")
        except Exception as e:
            log("⚠️ پشتیبان‌گیری نشد: %s" % e)
    tmp = DST + ".tmp"
    with open(tmp, "w", encoding="utf-8") as f:
        f.write(src)
    os.replace(tmp, DST)


def main():
    log("dir=%s" % HERE)
    errs = []
    for u in URLS:
        host = u.split("/")[2]
        try:
            src = get(u)
        except Exception as e:
            errs.append("%s → %s: %s" % (host, type(e).__name__, e))
            log("⚠️ دانلود نشد از %s (%s)" % (host, type(e).__name__))
            continue
        bad = why_bad(src)
        if bad:
            errs.append("%s → %s" % (host, bad))
            log("⚠️ فایلِ دانلودشده سالم نیست: %s" % bad)
            continue
        install(src)
        log("✅ main.py به‌روز شد (%d بایت) — اجرا" % len(src))
        os.execv(sys.executable, [sys.executable, DST] + sys.argv[1:])
        return 0
    log("⛔ نصب نشد. علت‌ها:")
    for e in errs:
        log("   - " + e)
    log("   یعنی میزبان به github.com دسترسی ندارد یا JAFJ_REPO اشتباه است.")
    return 1


if __name__ == "__main__":
    sys.exit(main())
