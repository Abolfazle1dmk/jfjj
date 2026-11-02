#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""پاکسازی دسته‌ای سقف عضویت (فرایند لفت موقع پر شدن ۵۰۰).

رفتار قدیمی: ChannelsTooMuch → فقط یک لفت + یک ریتری؛ اگر تلگرام هنوز
پر می‌گرفت، جوین برای یک ساعت کامل بلاک می‌شد. رفتار جدید: یک «دور
پاکسازی» تا سقف تنظیم‌شده (پیش‌فرض ۳۰) از قدیمی‌ترین کانال‌های جفج‌زده‌ی
امن لفت می‌زند، بعد جوین معلق را دوباره می‌زند و فقط یک پیام خلاصه می‌رود.

این تست قفل می‌کند:
  G1  clamp ظرفیت (۱..۱۰۰، پیش‌فرض ۳۰ برای ورودی نامعتبر)
  G2  لیست خالی/رکوردهای غیر joined → دسته‌ی خالی
  G3  ترتیب قدیمی‌ترین-اول و احترام به سقف دسته
  G4  قواعد امنیت: کانال خود کاربر، outbound متقابل‌نشده، یادآور فعال،
      رکورد بدون peer_id و کانال تکراری حذف می‌شوند
  G5  exclude_id (رکوردِ در حال جوین لفت نمی‌شود)
  G6  پیام خلاصه: حالت صفر، شمارش/لینک‌ها، جمع‌کردن مازاد، دلیل توقف
  G7  قفل‌های سورسی: پیش‌فرض ۳۰، اتصال به هندلر ChannelsTooMuch،
      فقط یک نوتیف در کل دور، ریتری یک‌باره، توقف روی FloodWait
"""
import os
import shutil
import subprocess
import sys
import tempfile

HERE = os.path.dirname(os.path.abspath(__file__))
REPO = os.path.dirname(HERE)
ROOT = os.path.join(tempfile.gettempdir(), "jafj_capacity_cleanup_run")
APP = os.path.join(ROOT, "app")
DATA = os.path.join(ROOT, "data")

DRIVER = r"""
import importlib.util, os, sys
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

def rec(rid, **kw):
    d = {"id": rid, "status": "joined", "peer_id": 1000 + rid,
         "direction": "in", "peer_joined_at": 0, "next_reminder": 0,
         "link": "@chan%d" % rid, "chat_id": 2000 + rid,
         "joined_at": 1000 + rid, "created_at": 900 + rid}
    d.update(kw)
    return d

# ── G1 clamp ──
check(m.clamp_capacity_batch(0) == 1, "clamp: صفر → کف ۱")
check(m.clamp_capacity_batch(-5) == 1, "clamp: منفی → کف ۱")
check(m.clamp_capacity_batch(999) == 100, "clamp: بزرگ → سقف ۱۰۰")
check(m.clamp_capacity_batch(30) == 30, "clamp: ۳۰ دست‌نخورده")
check(m.clamp_capacity_batch(None) == m.CAPACITY_CLEANUP_BATCH_DEFAULT,
      "clamp: None → پیش‌فرض")
check(m.clamp_capacity_batch("abc") == m.CAPACITY_CLEANUP_BATCH_DEFAULT,
      "clamp: رشته‌ی نامعتبر → پیش‌فرض")
print("DONE G1 clamp")

# ── G2 ورودی خالی ──
check(m.select_capacity_leave_batch([], limit=5) == [], "لیست خالی → []")
check(m.select_capacity_leave_batch(
    [rec(1, status="left"), rec(2, status="approved")], limit=5) == [],
    "رکوردهای غیر joined وارد دسته نمی‌شوند")
print("DONE G2 empty")

# ── G3 ترتیب و سقف ──
seven = [rec(i) for i in range(1, 8)]
batch = m.select_capacity_leave_batch(seven, limit=3)
check([r["id"] for r in batch] == [1, 2, 3],
      "قدیمی‌ترین‌ها اول، حداکثر سقف دسته: %s" % [r["id"] for r in batch])
batch_all = m.select_capacity_leave_batch(seven, limit=30)
check([r["id"] for r in batch_all] == [1, 2, 3, 4, 5, 6, 7],
      "سقف بزرگ‌تر از استخر → همه‌ی کاندیدها")
# ترتیب واقعاً بر اساس joined_at است نه id
shuffled = [rec(2, joined_at=5000), rec(1, joined_at=1000), rec(3, joined_at=3000)]
check([r["id"] for r in m.select_capacity_leave_batch(shuffled, limit=3)]
      == [1, 3, 2], "ترتیب بر اساس سن (joined_at)، نه ترتیب ورودی/id")
print("DONE G3 order/limit")

# ── G4 قواعد امنیت ──
own = m.select_capacity_leave_batch(
    [rec(1, link="@mychan"), rec(2)], own_channels=("@mychan",), limit=5)
check([r["id"] for r in own] == [2], "کانال خود کاربر هرگز لفت نمی‌شود")

out_pending = rec(1, direction="out", peer_joined_at=0)
out_done = rec(2, direction="out", peer_joined_at=1234)
out_batch = m.select_capacity_leave_batch([out_pending, out_done], limit=5)
check([r["id"] for r in out_batch] == [2],
      "outboundِ متقابل‌نشده (طرف هنوز جوین نزده) حذف می‌شود")

rem = m.select_capacity_leave_batch(
    [rec(1, next_reminder=999999), rec(2, next_reminder=0)], limit=5)
check([r["id"] for r in rem] == [2], "رکورد با یادآور فعال حذف می‌شود")

nopeer = m.select_capacity_leave_batch(
    [rec(1, peer_id=None), rec(2, peer_id=0)], limit=5)
check(nopeer == [], "رکورد بدون peer_id کاندید نیست")

# قواعد قدیمی: رکوردهای تکراریِ یک کانال (chat_id یکسان) عمداً هر دو
# دست‌نخورده می‌مانند تا لفتِ اشتباه رخ ندهد؛ فقط کانال غیرتکراری برمی‌آید.
dup = [rec(1, chat_id=777), rec(2, chat_id=777), rec(3, chat_id=888)]
dup_batch = m.select_capacity_leave_batch(dup, limit=5)
check([r["id"] for r in dup_batch] == [3],
      "رکوردهای تکراریِ یک کانال هر دو کنار گذاشته می‌شوند (قاعده‌ی محافظه‌کارانه)")
# رکورد برداشته‌شده در دورهای بعدی پلنر دوباره انتخاب نمی‌شود (باگ استخر
# کوچک‌شونده: حذف از استخر تشخیص تکراری را می‌شکست)
five = [rec(i, chat_id=5000 + i) for i in range(1, 6)]
round1 = m.select_capacity_leave_candidate(five)
round2 = m.select_capacity_leave_candidate(
    five, exclude_ids={round1["id"]})
check(round2 is not None and round2["id"] != round1["id"],
      "exclude_ids: دور بعد کاندیدِ قبلی را دوباره برنمی‌دارد")
full_batch = m.select_capacity_leave_batch(five, limit=5)
check(len({r["id"] for r in full_batch}) == len(full_batch) == 5,
      "هیچ رکوردی در یک دور دو بار برداشته نمی‌شود")
print("DONE G4 safety rules")

# ── G5 exclude_id ──
ex = m.select_capacity_leave_batch(
    [rec(i) for i in range(1, 5)], limit=5, exclude_id=1)
check(1 not in [r["id"] for r in ex] and [r["id"] for r in ex] == [2, 3, 4],
      "رکوردِ در حال جوین (exclude_id) لفت نمی‌شود")
print("DONE G5 exclude")

# ── G6 پیام خلاصه ──
note0 = m.format_capacity_cleanup_note([], 30)
check("هیچ تبادل" in note0 and "ریست" in note0,
      "حالت بدون کاندید، پیام راهنمای آزادسازی دستی دارد")
note3 = m.format_capacity_cleanup_note(["@chan1", "@chan2", "@chan3"], 30)
check(m.fa(3) in note3 and "کانالِ جفج‌زده" in note3
      and "@chan1" in note3 and "@chan3" in note3
      and "مورد دیگر" not in note3 and "دوباره تلاش" in note3,
      "خلاصه‌ی عادی: شمارش، لینک‌ها و وعده ریتری:\n" + note3)
many = ["@c%d" % i for i in range(12)]
note12 = m.format_capacity_cleanup_note(many, 30)
check(note12.count("@c") == m.STALE_NOTE_MAX_LINKS and "مورد دیگر" in note12,
      "بیشتر از سقف نمایش در پیام جمع می‌شود")
note_stop = m.format_capacity_cleanup_note(["@chan1"], 30, stopped="FloodWait 100s")
check("FloodWait" in note_stop and "زودتر تمام شد" in note_stop,
      "دلیل توقف زودهنگام در خلاصه دیده می‌شود")
print("DONE G6 summary note")

# ── G7 قفل‌های سورسی ──
dflt = next(v for k, v in m.DEFAULTS.items() if isinstance(v, dict)
            and "capacity_cleanup_batch" in v)
check(dflt["capacity_cleanup_batch"] == m.CAPACITY_CLEANUP_BATCH_DEFAULT,
      "پیش‌فرض تنظیمات = ثابتِ CAPACITY_CLEANUP_BATCH_DEFAULT")
check(1 <= m.CAPACITY_CLEANUP_BATCH_DEFAULT <= 5,
      "پیش‌فرضِ دور پاکسازی کوچک است (دورِ بلند صفِ تبادل را قفل می‌کرد): %r"
      % m.CAPACITY_CLEANUP_BATCH_DEFAULT)
check("leave_completed_exchange_for_slot" not in src,
      "تابع قدیمی تک‌لفت کاملاً حذف شده")
check("_after_capacity_cleanup" not in src,
      "ریتری درون‌تابعی حذف شده (پاکسازی دیگر داخل wait_for جوین اجرا نمی‌شود)")
handler_i = src.index("except ChannelsTooMuchError:")
handler = src[handler_i:handler_i + 2200]
check('cfg["_capacity_cleanup_pending"] = True' in handler,
      "هندلر ChannelsTooMuch فقط فلگ دور پاکسازی را می‌زند (نه لفتِ داخل جوین)")
check("CAPACITY_REBLOCK_SEC" in handler and "_last_capacity_cleanup_at" in handler,
      "بعد از پاکسازی اخیر، به‌جای لفت پشت‌سرهم مکث کوتاه می‌شود")
# مرحله‌ی پاکسازی در worker، بیرون از wait_for ۱۸۰ ثانیه‌ای جوین
wi = src.index("async def exchange_worker()")
wblock = src[wi:wi + 9000]
stage_i = wblock.index("_capacity_cleanup_pending")
stage = wblock[stage_i:stage_i + 1500]
check("await cleanup_capacity_for_slots()" in stage,
      "دور پاکسازی در ابتدای حلقه‌ی worker و بیرون از timeout جوین اجرا می‌شود")
check("block_joins_for_capacity(" in stage and "continue" in stage,
      "نبودِ کاندید → بلاک + توقف همان دور تا رکورد approved دست‌نخورده بماند")

# ── G8 کارایی: انتخابِ کاندید باید خطی باشد، نه O(n²) ──
# باگِ واقعی: روی ۱۰۰۰ رکوردِ joined، نسخه‌ی قبلی ۶۱ ثانیه CPU می‌گرفت و
# چون sync است کلِ event loop را قفل می‌کرد → اکانت «آفلاین» می‌شد.
import time as _t
_big = [rec(i, chat_id=5000 + i, link="@chan%d" % i) for i in range(1, 1001)]
_t0 = _t.perf_counter()
_b = m.select_capacity_leave_batch(_big, limit=30)
_ms = (_t.perf_counter() - _t0) * 1000
check(len(_b) == 30, "روی ۱۰۰۰ رکورد، ۳۰ کاندید برمی‌گردد")
check(_ms < 200, "انتخابِ ۳۰ کاندید روی ۱۰۰۰ رکورد سریع است: %.1f ms" % _ms)

check(m.capacity_round_exhausted(0, 10, 5) is True, "سقفِ زمانی: گذشته → True")
check(m.capacity_round_exhausted(0, 4, 5) is False, "سقفِ زمانی: نگذشته → False")
check(m.capacity_round_exhausted(None, 10, 5) is False, "سقفِ زمانی: ورودی خراب → False")
check("capacity_round_exhausted(" in src and "CAPACITY_CLEANUP_MAX_SEC" in src,
      "دورِ پاکسازی سقفِ زمانی دارد و نیمه‌کاره رها نمی‌شود")
check('cfg["_capacity_cleanup_pending"] = True' in
      src[src.index("async def cleanup_capacity_for_slots("):
          src.index("async def reply_joined")],
      "دورِ نیمه‌کاره برای ادامه در حلقه‌ی بعد دوباره فلگ می‌شود")
check("LOOP_LAG_WARN_SEC" in src and '"loop_lag"' in src,
      "قفل‌شدنِ event loop در لاگ/status ثبت می‌شود")
check("min(backoff * 2, 90)" in src,
      "سقفِ انتظارِ اتصالِ دوباره ۹۰ ثانیه است (نه ۵ دقیقه آفلاین)")
_w = src[src.index("async def exchange_worker()"):]
_w = _w[:_w.index("async def sender_loop()")]
check(_w.index("capacity_blocked_until") > _w.index("# ۱) لفت‌های دستی"),
      "گیتِ سقفِ عضویت فقط جلوی جوین است، نه کلِ حلقه")
print("DONE G8 performance/no-lock")

ci = src.index("async def cleanup_capacity_for_slots(")
cf = src.index("async def ", ci + 40)
cleanup_src = src[ci:cf]
check(cleanup_src.count("await note(format_capacity_cleanup_note") == 2,
      "هر دو مسیرِ نوتیف (بی‌کاندید و پایان دور) فقط پیام خلاصه می‌فرستند")
loop_i = cleanup_src.index("for cand in candidates:")
loop_end = cleanup_src.index('eng.log("info", "ex_capacity_cleanup"')
loop_body = cleanup_src[loop_i:loop_end]
check("await note(" not in loop_body,
      "داخل حلقه‌ی لفت هیچ نوتیف per-record نمی‌رود (فقط یک خلاصه در پایان)")
check(('isinstance(err, str) and "FloodWait" in err' in cleanup_src)
      and "break" in cleanup_src,
      "FloodWait وسط دور → توقف حلقه (نه لفت‌زدن زیر فشار تلگرام)")
check("select_capacity_leave_batch(" in cleanup_src
      and 'status="left"' in cleanup_src,
      "انتخاب کاندید خالص و ثبت وضعیت left بعد هر لفت موفق")
cmd_i = src.index("if sub in (\"capacity_leave\", \"leave_completed\"):")
cmd_src = src[cmd_i:cmd_i + 1800]
check("capacity_cleanup_batch" in cmd_src and "تعداد" in cmd_src,
      "دستور تغییر تعداد هر دور در پنل پیام ذخیره‌شده هست")
print("DONE G7 source locks")

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
    env["PORT"] = "8282"
    env["JAFJ_PORT"] = "8282"
    for k in ("RAILWAY_ENVIRONMENT", "RAILWAY_SERVICE_ID", "RAILWAY_PROJECT_ID",
              "RENDER", "RENDER_SERVICE_NAME", "JAFJ_HOSTED", "JAFJ_LOGIN_RETRY",
              "BOT_TOKEN", "API_ID", "API_HASH", "BACKUP_CHAT", "BACKUP_EVERY"):
        env.pop(k, None)
    p = subprocess.run([sys.executable, "-c", DRIVER], cwd=APP, env=env,
                       capture_output=True, text=True, timeout=300)
    return p.stdout, p.stderr, p.returncode


def main():
    print("--- capacity cleanup batch ---")
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
