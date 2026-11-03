#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""دروازه‌ی ضد-انباشت اسکن پیش‌قدم و تجمیع اعلان‌ها.

ریشه‌ی گزارش مشتری: اسکن هر ۳۰ ثانیه یک کانال ثبت و یک نوتیف
«کانال تازه پیدا شد — برای Join همین نوبت» می‌فرستاد، در حالی‌که خط لوله‌ی
Join به‌خاطر FloodWait یا صف شلوغ عملاً هیچ جوینی نمی‌زد. رکوردها بعد از
۵ دقیقه یکی‌یکی منقضی و هر کدام یک نوتیف «کانال قدیمی رد شد» جدا
می‌ساختند — طوفان پیام بدون هیچ تبادل واقعی.

این تست قفل می‌کند:
  ۱) scan_gate_reason: فلودِ صف یا بک‌لاگِ سقف‌دار → اسکن خودکار رد شود.
  ۲) اسکن دستی مشمول دروازه نباشد.
  ۳) format_stale_batch: رکوردهای منقضی در یک پیام خلاصه تجمیع شوند.
  ۴) اعلان «کانال تازه» ضداسپم و راستگو باشد (قول جوینِ همین نوبت وقتی
     صف بلاک است داده نشود).
"""
import os
import shutil
import subprocess
import sys
import tempfile

HERE = os.path.dirname(os.path.abspath(__file__))
REPO = os.path.dirname(HERE)
ROOT = os.path.join(tempfile.gettempdir(), "jafj_scan_gate_run")
APP = os.path.join(ROOT, "app")
DATA = os.path.join(ROOT, "data")

DRIVER = r"""
import importlib.util, os, sys, time
sys.path.insert(0, os.getcwd())
spec = importlib.util.spec_from_file_location("m95", "95.py")
m = importlib.util.module_from_spec(spec)
spec.loader.exec_module(m)
src = open("95.py", encoding="utf-8").read()

FAILS = []
def check(cond, label):
    print(("OK   " if cond else "FAIL "), label)
    if not cond:
        FAILS.append(label)

now = 1000.0

# ── ۱) scan_gate_reason ──
# فلودِ صف (blocked_until در آینده) مقدم بر هر چیز
check(m.scan_gate_reason(now + 50, 0, now) == "flood",
      "flood: صف بلاک‌شده با FloodWait رد می‌شود")
check(m.scan_gate_reason(now + 1, m.SCAN_JOIN_BACKLOG_LIMIT, now) == "flood",
      "flood: فلود بر بک‌لاگ اولویت دارد")
# زمان فلود گذشته → دیگر فلود نیست
check(m.scan_gate_reason(now - 1, 0, now) == "",
      "flood گذشته: صف آزاد است")
# بک‌لاگ به سقف رسید
check(m.scan_gate_reason(0, m.SCAN_JOIN_BACKLOG_LIMIT, now) == "backlog",
      "backlog: سقف رکورد معلق → اسکن رد")
check(m.scan_gate_reason(0, m.SCAN_JOIN_BACKLOG_LIMIT + 3, now) == "backlog",
      "backlog: بیشتر از سقف هم رد")
check(m.scan_gate_reason(0, m.SCAN_JOIN_BACKLOG_LIMIT - 1, now) == "",
      "backlog: زیر سقف مجاز است")
check(m.scan_gate_reason(None, None, now) == "", "ورودی خالی خطا نمی‌دهد")
print("DONE G1 gate reason")

# ── ۲) اسکن دستی از دروازه رد نمی‌شود (قفل سورسی) ──
sg = src.index("async def scan_groups(")
block = src[sg:sg + 4000]
gate_line = next((ln for ln in block.splitlines() if "scan_gate_reason(" in ln
                  and "def scan_gate_reason" not in ln), "")
manual_guard = src[sg:sg + 4500].find("if not manual:")
check(manual_guard > 0 and gate_line.strip().startswith("gate = scan_gate_reason"),
      "دروازه فقط برای اسکن خودکار است؛ اسکن دستی همیشه رد می‌شود")
print("DONE G2 manual bypass")

# ── ۳) format_stale_batch ──
links = ["@chan%d" % i for i in range(3)]
out = m.format_stale_batch(links, 300)
check(out.startswith("🕒 %s کانال قدیمی" % m.fa(3))
      and "@chan0" in out and "@chan2" in out
      and "5 دقیقه" in out,
      "خلاصه، شمارش و لینک‌ها را دارد:\n" + out)
many = ["@c%d" % i for i in range(m.STALE_NOTE_MAX_LINKS + 4)]
out2 = m.format_stale_batch(many, 300)
shown = out2.count("@c")
check(shown == m.STALE_NOTE_MAX_LINKS and "مورد دیگر" in out2,
      "بیشتر از سقف نمایش، جمع می‌شود (بود %d خط)" % shown)
check(m.format_stale_batch([], 300).startswith("🕒 %s" % m.fa(0)),
      "لیست خالی هم خطا نمی‌دهد")
print("DONE G3 stale batch")

# ── ۴) ضدفیلتر اعلان و راستگویی پیام ──
# اعلان «کانال تازه» باید فاصله‌ی زمانی داشته باشد و هنگام بلاکِ صف
# قول «همین نوبت» ندهد.
check("SCAN_FOUND_NOTE_GAP_SEC = 300" in src,
      "اعلام کانال تازه حداکثر هر ۵ دقیقه یک‌بار")
loop_i = src.index("async def scan_loop()")
# پنجره را «تا ابتدای بخش بعدی» می‌بریم، نه با طولِ ثابت: اسکن‌لوپ رشد
# می‌کند و با طولِ ثابت، متن‌های داخلش از پنجره بیرون می‌افتند.
_loop_next = src.find("    # ---------- کارگر بررسی عضویت", loop_i)
loop_block = src[loop_i:(_loop_next if _loop_next > loop_i else loop_i + 5000)]
check("found_buf" in loop_block and "last_found_note" in loop_block,
      "شمارش کانال‌های تازه تجمیع می‌شود")
check('state = ("صف تبادل به‌خاطر محدودیت تلگرام' in loop_block
      or "محدودیت تلگرام" in loop_block,
      "هنگام فلود، متن راستگو می‌گوید صف بسته است (نه «همین نوبت»)")
# کارگر جوین به‌جای نوتیف per رکورد از فلاش تجمیعی استفاده می‌کند
wi = src.index("async def exchange_worker()")
wblock = src[wi:wi + 6000]
check("format_stale_batch" in wblock and "flush_stale" in wblock,
      "کارگر، رکوردهای منقضی را تجمیع می‌گوید")
print("DONE G4 truthful throttled notes")

if FAILS:
    print("FAILED:", len(FAILS))
    for f in FAILS:
        print("  -", f)
    sys.exit(1)
print("DONE PASS")
"""


def reset():
    shutil.rmtree(ROOT, ignore_errors=True)
    os.makedirs(APP, exist_ok=True)
    os.makedirs(DATA, exist_ok=True)
    for f in ("95.py", "manager_82.py"):
        shutil.copy2(os.path.join(REPO, f), APP)


def run():
    env = dict(os.environ)
    env["DATA_DIR"] = DATA
    env["PORT"] = "8281"
    env["JAFJ_PORT"] = "8281"
    for k in ("RAILWAY_ENVIRONMENT", "RAILWAY_SERVICE_ID", "RAILWAY_PROJECT_ID",
              "RENDER", "RENDER_SERVICE_NAME", "JAFJ_HOSTED", "JAFJ_LOGIN_RETRY",
              "BOT_TOKEN", "API_ID", "API_HASH", "BACKUP_CHAT", "BACKUP_EVERY"):
        env.pop(k, None)
    p = subprocess.run([sys.executable, "-c", DRIVER], cwd=APP, env=env,
                       capture_output=True, text=True, timeout=300)
    return p.stdout, p.stderr, p.returncode


def main():
    print("--- scan backlog gate + note batching ---")
    reset()
    out, err, rc = run()
    if err.strip():
        print("--- driver stderr (tail) ---")
        print(err[-3000:])
    for line in out.splitlines():
        if line.startswith(("OK", "FAIL", "DONE", "FAILED", "  -")):
            print(line)
    if "DONE PASS" in out and "FAIL" not in out:
        print("ALL: PASS")
        return True
    print("ALL: FAIL")
    return False


if __name__ == "__main__":
    sys.exit(0 if main() else 1)
