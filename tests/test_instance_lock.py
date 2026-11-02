#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""«دو نسخه روی یک اکانت» — همان چیزی که پنل را بی‌جواب می‌کند.

نشانه‌ای که این تست می‌گیرد: پروسه «روشن» است (لاگ می‌گوید وصل شدم)، ولی
پیام‌های Saved Messages جواب نمی‌گیرند. علتش این است که دو اتصال با یک سشن
باز است و تلگرام آپدیت‌ها را بینِ آن‌ها پخش می‌کند. قفلِ قبلی
(`jafj.run.lock`) فقط هم‌پوشه را می‌دید؛ نسخه‌ی دوم از پوشه‌ی دیگر
(ریشه‌ی اپ، پوشه‌ی مشتری، کانتینرِ دوم روی همان دیسک) آزادانه وصل می‌شد.

قفلِ تازه بر اساسِ **شناسه‌ی اکانت** و در `$DATA_DIR/.jafj_instances/`
نوشته می‌شود که بینِ همه‌ی پوشه‌های همان میزبان مشترک است.

اجرا: python3 tests/test_instance_lock.py
"""
import importlib.util
import io
import json
import os
import shutil
import subprocess
import sys
import tempfile
import time

HERE = os.path.dirname(os.path.abspath(__file__))
ROOT = os.path.dirname(HERE)
SRC = os.path.join(ROOT, "95.py")

FAILS = []


def check(name, ok, extra=""):
    if ok:
        print("PASS", name)
    else:
        FAILS.append(name)
        print("FAIL", name, "" if extra == "" else "→ %r" % (str(extra)[:300],))


spec = importlib.util.spec_from_file_location("m95i", SRC)
m = importlib.util.module_from_spec(spec)
m.__file__ = SRC
spec.loader.exec_module(m)

TMP = tempfile.mkdtemp(prefix="jafj_inst_")
os.environ["DATA_DIR"] = TMP

UID = 987654321


def reap(pid):
    try:
        os.kill(pid, 9)
    except Exception:
        pass
    try:
        os.waitpid(pid, 0)
    except Exception:
        pass


# ── T1: قفلِ تازه ──
ok, pid, cwd, why = m.claim_instance(UID)
f = m._instance_path(UID)
check("T1: اولین نسخه آزاد است", ok is True, (ok, pid, why))
check("T1: فایلِ قفل در DATA_DIR ساخته می‌شود",
      os.path.isfile(f) and f.startswith(os.path.abspath(TMP)), f)
rec = json.load(io.open(f, encoding="utf-8"))
check("T1: pid و پوشه ثبت شده",
      rec.get("pid") == os.getpid() and rec.get("cwd") == os.getcwd(), rec)
check("T1: نامِ سشن هم ثبت شده", "session" in rec, rec)

# ── T2: نسخه‌ی دوم از پوشه‌ی دیگر با pidِ زنده → رد ──
other = subprocess.Popen([sys.executable, "-c",
                          "import time; time.sleep(30)", "95.py"])
time.sleep(0.4)
try:
    json.dump({"pid": other.pid, "cwd": "/some/other/folder",
               "ts": time.time(), "session": "/some/other/folder/jafj.session"},
              io.open(f, "w", encoding="utf-8"))
    ok2, pid2, cwd2, why2 = m.claim_instance(UID)
    check("T2: نسخه‌ی دوم رد می‌شود", ok2 is False, (ok2, why2))
    check("T2: pidِ نسخه‌ی دیگر برگردانده می‌شود", pid2 == other.pid, pid2)
    check("T2: پوشه‌ی نسخه‌ی دیگر برگردانده می‌شود",
          cwd2 == "/some/other/folder", cwd2)
    check("T2: دلیلش فارسی و روشن است", "پوشه‌ی دیگری" in why2, why2)
    check("T2: قفلِ نسخه‌ی دیگر دست نمی‌خورد",
          json.load(io.open(f, encoding="utf-8")).get("pid") == other.pid)
finally:
    reap(other.pid)

# ── T3: pidِ مرده → آزاد ──
ok3, _, _, _ = m.claim_instance(UID)
check("T3: قفلِ pidِ مرده مانع نیست", ok3 is True)

# ── T4: همان پوشه (پروسه‌ی خودم) → آزاد ──
json.dump({"pid": os.getpid(), "cwd": os.getcwd(), "ts": time.time()},
          io.open(f, "w", encoding="utf-8"))
ok4, _, _, _ = m.claim_instance(UID)
check("T4: قفلِ خودم دوباره قابلِ گرفتن است", ok4 is True)

# ── T5: قفلِ کهنه (بیش از ۱۵ دقیقه) → آزاد ──
old = subprocess.Popen([sys.executable, "-c",
                        "import time; time.sleep(30)", "95.py"])
time.sleep(0.4)
try:
    json.dump({"pid": old.pid, "cwd": "/stale/folder",
               "ts": time.time() - m.INSTANCE_STALE_SEC - 60},
              io.open(f, "w", encoding="utf-8"))
    ok5, _, _, _ = m.claim_instance(UID)
    check("T5: قفلِ کهنه خودش آزاد می‌شود", ok5 is True)
finally:
    reap(old.pid)

# ── T6: heartbeat قفل را تازه نگه می‌دارد ──
json.dump({"pid": os.getpid(), "cwd": "/x", "ts": 1.0},
          io.open(f, "w", encoding="utf-8"))
m.start_instance_heartbeat(UID, every=0.01)
time.sleep(0.25)
rec6 = json.load(io.open(f, encoding="utf-8"))
check("T6: heartbeat زمانِ قفل را جلو می‌برد", (rec6.get("ts") or 0) > 1.0, rec6)
# رشته را ببند: با تغییرِ pid، حلقه خودش برمی‌گردد
json.dump({"pid": 1, "cwd": "/x", "ts": time.time()},
          io.open(f, "w", encoding="utf-8"))
time.sleep(0.1)

# ── T7: آزادکردن فقط برای صاحبش ──
json.dump({"pid": os.getpid(), "cwd": os.getcwd(), "ts": time.time()},
          io.open(f, "w", encoding="utf-8"))
m.release_instance(UID)
check("T7: release فایل را پاک می‌کند", not os.path.exists(f))
json.dump({"pid": 999999, "cwd": "/y", "ts": time.time()},
          io.open(f, "w", encoding="utf-8"))
m.release_instance(UID)
check("T7: قفلِ پروسه‌ی دیگر را پاک نمی‌کند", os.path.exists(f))

# ── T8: پوشه‌ی غیرقابلِ‌نوشتن نباید بوت را ببندد ──
os.environ["DATA_DIR"] = "/proc/nonexistent"
ok8, _, _, _ = m.claim_instance(UID)
check("T8: اگر قفل نوشته نشود، بوت ادامه می‌یابد", ok8 is True)
os.environ["DATA_DIR"] = TMP

# ── T9: سیم‌کشی در ۹۵.py ──
src = open(SRC, encoding="utf-8").read()
check("T9: مسیرِ dup_instance در run_bot هست",
      'if r == "dup_instance":' in src and "return EXIT_DUP" in src)
check("T9: بعد از ورود، قفل گرفته می‌شود",
      "claim_instance(me.id)" in src)
check("T9: آزادسازی در پایانِ پروسه ثبت می‌شود",
      "atexit.register(release_instance, me.id)" in src)
check("T9: پیامِ باگ به پنل/لاگ می‌رود",
      "پنل جواب نمی‌دهد" in src)
check("T9: قفلِ هم‌پوشه هم سر جایش هست", "jafj.run.lock" in src)

# ── T10: کلیدِ خاموش‌کن ──
json.dump({"pid": os.getpid() + 1, "cwd": "/elsewhere", "ts": time.time()},
          io.open(f, "w", encoding="utf-8"))
os.environ["JAFJ_ALLOW_DUPLICATE_INSTANCE"] = "1"
try:
    ok10, _, _, _ = m.claim_instance(UID)
finally:
    os.environ.pop("JAFJ_ALLOW_DUPLICATE_INSTANCE", None)
check("T10: JAFJ_ALLOW_DUPLICATE_INSTANCE=1 قفل را رد می‌کند",
      ok10 is True, ok10)

shutil.rmtree(TMP, ignore_errors=True)
print()
if FAILS:
    print("FAILED:", FAILS)
    sys.exit(1)
print("ALL PASS")
