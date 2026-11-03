#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""دستورهای دستیِ تبادل + تلاشِ دوباره‌ی «لفتِ دستی».

باگ‌هایی که این تست می‌گیرد
──────────────────────────
۱) `تبادل رد ۵` و `تبادل حذف ۵` روی رکوردی که **جوین شده‌ایم** بدونِ هیچ
   لفتی رکورد را rejected/حذف می‌کرد. یعنی اکانت تا ابد عضوِ کانالِ طرف
   می‌ماند؛ هر یک از این‌ها یکی از ۵۰۰ جای حساب را می‌گیرد و آخرش به
   `ChannelsTooMuch` می‌رسیم.
۲) در حلقه‌ی «لفت‌های دستی»، هر شکستی — حتی یک FloodWait یا تایم‌اوتِ
   شبکه — رکورد را مستقیم `failed` می‌کرد؛ بعد از آن هیچ تلاشی نمی‌شد و
   دستورِ `تبادل خروج ۵` عملاً بی‌اثر می‌شد.

اجرا: python3 tests/test_manual_cmds.py
"""
import importlib.util
import os
import shutil
import sys
import tempfile
import time

HERE = os.path.dirname(os.path.abspath(__file__))
ROOT = os.path.dirname(HERE)

TMP = tempfile.mkdtemp(prefix="jafj_manual_cmds_")
os.chdir(TMP)                       # فایل‌های jafj_* داخلِ پوشه‌ی موقت
sys.path.insert(0, ROOT)

_src = os.path.join(ROOT, "95.py")
spec = importlib.util.spec_from_file_location("m95", _src)
m = importlib.util.module_from_spec(spec)
m.__file__ = _src
spec.loader.exec_module(m)

FAILS = []


def check(name, ok, extra=""):
    if ok:
        print("PASS", name)
    else:
        FAILS.append(name)
        print("FAIL", name, "" if extra == "" else "→ %r" % (extra,))


eng = m.Engine()


def new_rec(link, status="joined", **kw):
    rec, _new = eng.db.ex_add(None, "طرف", link)
    eng.db.ex_set(rec["id"], status=status, **kw)
    return eng.db.ex_get(rec["id"])


def fresh():
    """دیتابیس تازه برای هر سناریو (بدونِ نشتیِ رکورد)."""
    for row in eng.db.ex_list(None, 1000) or []:
        eng.db.ex_delete(row["id"])


# ── T1: «رد» روی رکوردِ جوین‌شده → نوبتِ لفت (نه rejected) ──
fresh()
rec = new_rec("https://t.me/+t1", chat_id=-10001, chat_hash=7)
msg = eng.exchange_cmd("رد %d" % rec["id"])
row = eng.db.ex_get(rec["id"])
check("T1: رد روی رکوردِ جوین‌شده → وضعیت leaving",
      row["status"] == "leaving", row["status"])
check("T1: پیام می‌گوید از کانالش خارج می‌شوم", "لفت" in msg, msg)

# ── T2: «رد» روی رکوردِ در صف → rejected (لفتی لازم نیست) ──
fresh()
rec = new_rec("https://t.me/+t2", status="pending")
eng.exchange_cmd("رد %d" % rec["id"])
row = eng.db.ex_get(rec["id"])
check("T2: رد روی رکوردِ در صف → rejected",
      row["status"] == "rejected", row["status"])

# ── T3: «حذف» روی رکوردِ جوین‌شده → رد می‌شود (راهِ لفت از دست نرود) ──
fresh()
rec = new_rec("https://t.me/+t3", chat_id=-10003, chat_hash=9)
msg = eng.exchange_cmd("حذف %d" % rec["id"])
row = eng.db.ex_get(rec["id"])
check("T3: حذفِ رکوردِ جوین‌شده انجام نمی‌شود", row is not None)
check("T3: راهنمایی می‌کند اول «تبادل خروج» بده",
      "خروج" in msg and "جوین" in msg, msg)

# ── T4: «حذف» روی رکوردِ در صف → حذف می‌شود ──
fresh()
rec = new_rec("https://t.me/+t4", status="pending")
eng.exchange_cmd("حذف %d" % rec["id"])
check("T4: حذفِ رکوردِ غیرجوین انجام می‌شود",
      eng.db.ex_get(rec["id"]) is None)

# ── T5: «خروج» → نوبتِ لفت ──
fresh()
rec = new_rec("https://telegram.me/joinchat/t5abcdef/", chat_id=-10005, chat_hash=11)
msg = eng.exchange_cmd("خروج %d" % rec["id"])
row = eng.db.ex_get(rec["id"])
check("T5: خروج → وضعیت leaving", row["status"] == "leaving", row["status"])

# دستور صریح باید عقب‌نشینیِ قبلی را پاک کند تا وارد صفِ همین دور شود.
eng.db.ex_set(rec["id"], leave_fail=3, leave_blocked_until=int(time.time()) + 3600)
msg = eng.exchange_cmd("خروج https://t.me/+t5abcdef")
row = eng.db.ex_get(rec["id"])
check("T5b: لینک joinchat رکوردِ دعوت +hash را پیدا می‌کند",
      row is not None and row["id"] == rec["id"], msg)
check("T5b: خروجِ مجدد عقب‌نشینی و شکست‌های قبلی را پاک می‌کند",
      row["status"] == "leaving" and row["leave_fail"] == 0
      and row["leave_blocked_until"] == 0 and row["next_check"] == 0, row)

# ── T6: برنامه‌ی تلاشِ دوباره‌ی لفتِ دستی ──
now = int(time.time())
plan = m.manual_leave_retry_plan({"leave_fail": 0}, now, "FloodWait 300s")
check("T6: FloodWait → رکورد در نوبتِ لفت می‌ماند",
      plan["status"] == "leaving", plan)
check("T6: عقب‌نشینی ۶۰ ثانیه‌ای ست می‌شود",
      plan["leave_blocked_until"] == now + 60, plan)
check("T6: شمارنده‌ی شکست بالا می‌رود", plan["leave_fail"] == 1, plan)

plan2 = m.manual_leave_retry_plan({"leave_fail": 1}, now, "TimeoutError: x")
check("T6: شکستِ دوم → عقب‌نشینی ۵ دقیقه‌ای",
      plan2["leave_blocked_until"] == now + 300, plan2)

plan3 = m.manual_leave_retry_plan({"leave_fail": 2}, now, "FloodWait 60s")
check("T6: شکستِ سوم → failed (دیگر تلاش نمی‌کنیم)",
      plan3["status"] == "failed", plan3)

plan4 = m.manual_leave_retry_plan(
    {"leave_fail": 0}, now,
    "لینک طرف منقضی/باطل شده و آیدیِ کانال هم ذخیره نشده بود — لفت نشد؛ "
    "یک لینک تازه از طرف بگیر یا دستی از کانال خارج شو")
check("T6: خطای قطعی (لینکِ غیرقابلِ حل) → failed بی‌درنگ",
      plan4["status"] == "failed", plan4)

plan5 = m.manual_leave_retry_plan({"leave_fail": 0}, now, "ValueError: weird")
check("T6: خطای ناشناخته → failed (تکرارِ بی‌فایده نکن)",
      plan5["status"] == "failed", plan5)

# ── T7: تشخیصِ موقتی/قطعی ──
check("T7: FloodWait موقتی است", m.leave_error_is_transient("FloodWait 60s"))
check("T7: OSError موقتی است", m.leave_error_is_transient("OSError: boom"))
check("T7: پیامِ «منقضی» قطعی است",
      not m.leave_error_is_transient("لینک طرف منقضی/باطل شده است"))
check("T7: پیامِ خالی قطعی است", not m.leave_error_is_transient(""))
check("T7: خطای ناشناخته قطعی است", not m.leave_error_is_transient("ValueError: x"))

# ── T8: سیم‌کشیِ حلقه (منبع‌پین) ──
src = open(_src, encoding="utf-8").read()
check("T8: حلقه‌ی لفتِ دستی به عقب‌نشینی احترام می‌گذارد",
      'if int(rec.get("leave_blocked_until") or 0) > _now_ml:' in src)
check("T8: حلقه از manual_leave_retry_plan استفاده می‌کند",
      "plan = manual_leave_retry_plan(rec, _now_ml, err)" in src)
check("T8: بعد از ۵ تلاشِ واقعی این دور تمام می‌شود",
      "if _tried_ml >= 5:" in src)
check("T8: حالتِ leaving دیگر مستقیم failed نمی‌شود",
      'status="left" if ok else "failed"' not in src.split("# ۱) لفت‌های دستی")[1][:2000])
worker = src[src.index("async def exchange_worker") :]
check("T9: صفِ خروجِ صریح قبل از گیتِ خاموشی اجرا می‌شود",
      worker.index('eng.db.ex_list("leaving", 20)')
      < worker.index('if not x["enabled"]:'))
check("T9: پاکسازیِ خودکار وقتی تبادل خاموش است اجرا نمی‌شود",
      'if x["enabled"] and int(x.get("_capacity_cleanup_pending", 0) or 0):' in worker)

print()
shutil.rmtree(TMP, ignore_errors=True)
if FAILS:
    print("FAILED:", FAILS)
    sys.exit(1)
print("ALL PASS")
