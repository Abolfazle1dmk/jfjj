#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""ردیِ بوت، فایلِ خطای بوت، و دکترِ «چرا بالا نمی‌آید؟».

مشکلی که این تست می‌گیرد
────────────────────────
کاربر بعد از آپدیت گفت: «نه پنل جواب می‌دهد نه پیامِ آنلاین‌شدن می‌آید».
در آن حالت هیچ اثری از *کجا* ماندنِ بوت نمی‌ماند، چون خطا فقط به stderr
می‌رفت و بسیاری از میزبان‌ها stderr را نشان نمی‌دهند. حالا:
  • هر مرحله‌ی بوت یک خط در `jafj_boot.log` می‌نویسد،
  • هر خطای بوت در `jafj_boot_error.txt` می‌نشیند و کدِ خروج ۷۰ می‌دهد،
  • `tools/doctor_fa.py` همه‌ی چیزهایی که «بالا نیامدن» را می‌سازند
    (نبودِ telethon، پوشه‌ی غیرقابلِ‌نوشتن، قفلِ مرده، دو نسخه، …) را
    یک‌جا گزارش می‌کند.

اجرا: python3 tests/test_boot_diagnostics.py
"""
import importlib.util
import os
import shutil
import subprocess
import sys
import tempfile

HERE = os.path.dirname(os.path.abspath(__file__))
ROOT = os.path.dirname(HERE)
SRC = os.path.join(ROOT, "95.py")
DOCTOR = os.path.join(ROOT, "tools", "doctor_fa.py")

FAILS = []


def check(name, ok, extra=""):
    if ok:
        print("PASS", name)
    else:
        FAILS.append(name)
        print("FAIL", name, "" if extra == "" else "→ %r" % (extra,))


spec = importlib.util.spec_from_file_location("m95b", SRC)
m = importlib.util.module_from_spec(spec)
m.__file__ = SRC
spec.loader.exec_module(m)

work = tempfile.mkdtemp(prefix="jafj_boot_")
old_cwd = os.getcwd()


def in_tmp(fn):
    """تابع را با cwd برابرِ پوشه‌ی موقت اجرا کن (فایل‌های بوت همان‌جا)."""
    def wrapper():
        os.chdir(work)
        try:
            return fn()
        finally:
            os.chdir(old_cwd)
    return wrapper


# ── T1/T2: ردیِ بوت ──
@in_tmp
def _t1():
    log = os.path.join(work, "jafj_boot.log")
    m._BOOT_SEEN.clear()
    m._BOOT_LAST["step"] = ""
    m._boot_step("اجرا شد", "python=test")
    m._boot_step("اجرا شد", "python=test")     # تکراری نباید دوباره بنشیند
    m._boot_step("ورود انجام شد")
    with open(log, encoding="utf-8") as f:
        lines = [ln for ln in f.read().splitlines() if ln.strip()]
    return lines


lines = _t1()
check("T1: هر مرحله یک خط در jafj_boot.log",
      len(lines) == 2, lines)
check("T1: خطِ مرحله pid و زمان دارد",
      all("pid=" in ln and ln[:4].isdigit() for ln in lines), lines)
check("T1: مرحله‌ی تکراری دوباره ثبت نمی‌شود",
      sum(1 for ln in lines if "اجرا شد" in ln) == 1, lines)
check("T1: جزئیاتِ اضافه در همان خط می‌آید",
      any("python=test" in ln for ln in lines), lines)
check("T2: آخرین مرحله از حافظه برمی‌گردد",
      m.boot_last_step() == "ورود انجام شد", m.boot_last_step())


# ── T3: فایلِ خطای بوت ──
@in_tmp
def _t3():
    crash = os.path.join(work, "jafj_boot_error.txt")
    if os.path.exists(crash):
        os.remove(crash)
    try:
        raise ValueError("boom-42")
    except ValueError as e:
        path = m.record_boot_crash(e)
    with open(path, encoding="utf-8") as f:
        return path, f.read()


path, txt = _t3()
check("T3: فایلِ خطا ساخته می‌شود", os.path.isfile(path), path)
check("T3: نوع و متنِ خطا داخلش هست", "ValueError: boom-42" in txt, txt[:200])
check("T3: مسیرِ اجرا و pid ثبت می‌شود",
      "cwd=" in txt and "pid=" in txt, txt[:200])
check("T3: آخرین مرحله‌ی بوت هم نوشته می‌شود",
      "آخرین مرحله‌ی بوت: ورود انجام شد" in txt, txt[:300])
check("T3: Traceback کامل هست", "Traceback (most recent call last)" in txt)


# ── T4: main() خطا را می‌بلعد و ثبت می‌کند (کدِ خروج ۷۰) ──
@in_tmp
def _t4():
    crash = os.path.join(work, "jafj_boot_error.txt")
    lock = os.path.join(work, "jafj.run.lock")
    for p in (crash, lock):
        if os.path.exists(p):
            os.remove(p)
    m._BOOT_SEEN.clear()
    real = m.run_bot

    def boom():
        raise RuntimeError("boot-blew-up")

    m.run_bot = boom
    try:
        rc = m.main()
    finally:
        m.run_bot = real
    body = ""
    if os.path.isfile(crash):
        with open(crash, encoding="utf-8") as f:
            body = f.read()
    return rc, body, os.path.exists(lock)


rc, body, lock_left = _t4()
check("T4: خطای بوت کدِ خروج ۷۰ می‌دهد (نه مرگِ خاموش)", rc == 70, rc)
check("T4: متنِ خطا در فایل ذخیره شده", "boot-blew-up" in body, body[:200])
check("T4: قفلِ اجرا بعد از خطا آزاد می‌شود", lock_left is False)


# ── T5: سیم‌کشی در ۹۵.py ──
src = open(SRC, encoding="utf-8").read()
check("T5: main() خطا را به record_boot_crash می‌دهد",
      "except Exception as e:\n        # بدونِ این" in src
      and "record_boot_crash(e)" in src)
check("T5: مرزِ «کار می‌کند» در ردیِ بوت هست",
      "_boot_step(BOOT_OK_STEP" in src)
check("T5: مراحلِ اتصال ثبت می‌شوند",
      src.count("_boot_step(") >= 8, src.count("_boot_step("))
for step in ("telethon بارگذاری شد", "کلاینتِ تلگرام ساخته شد",
             "شروعِ اتصال به تلگرام", "ورود انجام شد",
             "هندلرها و حلقه‌ها ثبت شدند"):
    check(f"T5: مرحله‌ی «{step}» دارد", step in src)


# ── T9: تشخیصِ پروسه‌ی سلف ──
d = importlib.util.spec_from_file_location("doctor", DOCTOR)
doc = importlib.util.module_from_spec(d)
d.loader.exec_module(doc)
check("T9: python3 95.py → سلف است",
      doc.looks_like_selfbot_proc("python3 95.py"))
check("T9: مسیرِ کامل با فلگ هم سلف است",
      doc.looks_like_selfbot_proc("/usr/bin/python3 -u /app/95.py"))
check("T9: شل که فقط اسمِ فایل را دارد سلف نیست",
      not doc.looks_like_selfbot_proc("/bin/bash -c 'rm 95.py'"))
check("T9: vim 95.py سلف نیست",
      not doc.looks_like_selfbot_proc("vim 95.py"))
check("T9: فایلِ دیگر با پایتون سلف نیست",
      not doc.looks_like_selfbot_proc("python3 doctor_fa.py"))


# ── T6/T7/T8: دکتر ──
def run_doctor(folder):
    env = dict(os.environ)
    env["JAFJ_SELFBOT_REF"] = os.path.join(folder, "none")
    for k in list(env):
        if k.startswith("JAFJ_"):
            env.pop(k, None)
    return subprocess.run([sys.executable, DOCTOR], cwd=folder, env=env,
                          capture_output=True, text=True, timeout=180)


# T6: پوشه‌ی خالی → «95.py نیست» و کدِ خروج ۱
empty = tempfile.mkdtemp(prefix="jafj_doc_empty_")
r = run_doctor(empty)
check("T6: بدونِ 95.py گزارش می‌دهد", "95.py در این پوشه نیست" in r.stdout,
      r.stdout[-300:])
check("T6: در این حالت کدِ خروج ۱ است", r.returncode == 1, r.returncode)
check("T6: می‌گوید هیچ پروسه‌ی 95.py نیست",
      "هیچ پروسه‌ی 95.py در حال اجرا نیست" in r.stdout)

# T7: 95.py خراب → SyntaxError
broken = tempfile.mkdtemp(prefix="jafj_doc_broken_")
with open(os.path.join(broken, "95.py"), "w", encoding="utf-8") as f:
    f.write("def x(:\n    pass\n")
r = run_doctor(broken)
check("T7: SyntaxError تشخیص داده می‌شود",
      "کامپایل نمی‌شود" in r.stdout and "SyntaxError" in r.stdout,
      r.stdout[-400:])

# T8: 95.py سالم (کپیِ همین فایل) → کامپایل سالم
good = tempfile.mkdtemp(prefix="jafj_doc_good_")
shutil.copy2(SRC, os.path.join(good, "95.py"))
r = run_doctor(good)
check("T8: 95.py سالم کامپایل می‌شود", "بدونِ خطا" in r.stdout,
      r.stdout[-400:])
check("T8: هشِ فایل گزارش می‌شود", "هش " in r.stdout)
check("T8: درباره‌ی telethon نظر می‌دهد",
      ("telethon" in r.stdout) and ("نصب است" in r.stdout
                                   or "نصب نیست" in r.stdout))

for folder in (empty, broken, good, work):
    shutil.rmtree(folder, ignore_errors=True)

print()
if FAILS:
    print("FAILED:", FAILS)
    sys.exit(1)
print("ALL PASS")
