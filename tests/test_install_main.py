#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""نصب‌کننده‌ی main.py برای میزبانی که فقط «ویرایشِ فایل» دارد.

چرا این تست: کانالِ «مرورگر → ادیتورِ میزبان» فایل را HTML-escape می‌کند و
نتیجه SyntaxError است (همان اتفاقی که برای کاربر افتاد). نصب‌کننده باید
همین را قبل از نوشتن بگیرد و نسخه‌ی قبلی را هم از دست ندهد.

اجرا: python3 tests/test_install_main.py
"""
import importlib.util
import io
import os
import shutil
import sys
import tempfile

HERE = os.path.dirname(os.path.abspath(__file__))
ROOT = os.path.dirname(HERE)
INST = os.path.join(ROOT, "deploy", "wispbyte", "install_main.py")
GOOD_MAIN = os.path.join(ROOT, "deploy", "wispbyte", "main.py")

FAILS = []


def check(name, ok, extra=""):
    if ok:
        print("PASS", name)
    else:
        FAILS.append(name)
        print("FAIL", name, "" if extra == "" else "→ %r" % (str(extra)[:300],))


spec = importlib.util.spec_from_file_location("inst", INST)
m = importlib.util.module_from_spec(spec)
m.__file__ = INST
spec.loader.exec_module(m)

good = io.open(GOOD_MAIN, encoding="utf-8").read()

# ── T1: اعتبارسنجی ──
check("T1: فایلِ سالم قبول می‌شود", m.why_bad(good) == "", m.why_bad(good))
esc = good.replace("<div", "&lt;div")
check("T1: HTML-escape رد می‌شود", "HTML-escape" in m.why_bad(esc),
      m.why_bad(esc))
esc2 = good.replace(">=", "&gt;=")
check("T1: «&gt;» هم رد می‌شود", "HTML-escape" in m.why_bad(esc2),
      m.why_bad(esc2))
check("T1: فایلِ کوتاه رد می‌شود", "کوتاه" in m.why_bad(good[:300]),
      m.why_bad(good[:300]))
check("T1: محتوای بی‌ربط رد می‌شود", m.why_bad("x" * 7000) != "",
      m.why_bad("x" * 7000))
broken = good.replace("def main():", "def main(:", 1)
check("T1: SyntaxError رد می‌شود", "SyntaxError" in m.why_bad(broken),
      m.why_bad(broken))

# ── T2: نصب + پشتیبان ──
tmp = tempfile.mkdtemp(prefix="jafj_inst_")
old_dst = m.DST
m.DST = os.path.join(tmp, "main.py")
io.open(m.DST, "w", encoding="utf-8").write("# main.py قدیمی\n")
m.install(good)
check("T2: فایل نوشته شد", io.open(m.DST, encoding="utf-8").read() == good)
check("T2: نسخه‌ی قبلی در main.py.bak هست",
      os.path.isfile(m.DST + ".bak") and
      "قدیمی" in io.open(m.DST + ".bak", encoding="utf-8").read())
check("T2: فایلِ موقت باقی نمی‌ماند", not os.path.exists(m.DST + ".tmp"))

# اگر خودِ محتوای فعلی نصب‌کننده باشد، بکاپِ بی‌معنی نوشته نشود
io.open(m.DST, "w", encoding="utf-8").write("# JAFJ-INSTALL ...\n")
os.remove(m.DST + ".bak")
m.install(good)
check("T2: روی نسخه‌ی نصب‌کننده بکاپِ بی‌معنی نمی‌سازد",
      not os.path.exists(m.DST + ".bak"))

# ── T3: زنجیره‌ی منابع ──
calls = []


def fake_get_fail(url):
    calls.append(url)
    raise OSError("no net")


m.get = fake_get_fail
buf = io.StringIO()
from contextlib import redirect_stdout
with redirect_stdout(buf):
    rc = m.main()
check("T3: وقتی هیچ منبعی نیست کدِ ۱ می‌دهد", rc == 1, rc)
check("T3: همه‌ی منابع امتحان می‌شوند", len(calls) == len(m.URLS), len(calls))
check("T3: پیامِ ⛔ و علت‌ها چاپ می‌شود", "⛔" in buf.getvalue(),
      buf.getvalue()[-300:])

calls.clear()
seen = {"n": 0}


def fake_get_second(url):
    calls.append(url)
    seen["n"] += 1
    if seen["n"] == 1:
        raise OSError("first source down")
    return good


m.get = fake_get_second
execd = {}


def fake_execv(path, argv):
    execd["path"], execd["argv"] = path, list(argv)


m.os.execv = fake_execv
io.open(m.DST, "w", encoding="utf-8").write("# قبلی\n")
buf = io.StringIO()
with redirect_stdout(buf):
    rc = m.main()
check("T3: منبعِ دوم وقتی اولی خطا داد کار می‌کند", rc == 0 and
      len(calls) == 2, (rc, len(calls)))
check("T3: فایلِ نصب‌شده همان نسخه‌ی سالم است",
      io.open(m.DST, encoding="utf-8").read() == good)
check("T3: بعد از نصب اجرا می‌شود", execd.get("path") and
      m.DST in execd["argv"], execd)

calls.clear()
seen["n"] = 0


def fake_get_escaped(url):
    calls.append(url)
    seen["n"] += 1
    return esc if seen["n"] < 3 else good


m.get = fake_get_escaped
execd.clear()
buf = io.StringIO()
with redirect_stdout(buf):
    rc = m.main()
check("T3: فایلِ escape‌شده نصب نمی‌شود و منبعِ بعدی امتحان می‌شود",
      rc == 0 and len(calls) == 3, (rc, len(calls)))
check("T3: همان سالم است که نوشته شد",
      io.open(m.DST, encoding="utf-8").read() == good)

shutil.rmtree(tmp, ignore_errors=True)
m.DST = old_dst

print()
if FAILS:
    print("FAILED:", FAILS)
    sys.exit(1)
print("ALL PASS")
