#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""سقفِ ۵۰۰ کانالِ تلگرام: وقتی «هیچ کاندیدِ امنی» نبود، باید پله‌ای نرم شود.

گزارشِ واقعیِ کاربر:

    ❌ جوین نشد … ChannelsTooMuch
    🧹 سقف عضویت پر بود ولی هیچ تبادلِ کامل‌شده‌ی امنی برای لفت پیدا نشد…

یعنی اکانت به سقفِ تلگرام خورده، پاکسازی **هیچ** کانالی لفت نمی‌داد (چون
فقط «تبادلِ کامل» کاندید بود)، و همان دو پیام هر ۵ دقیقه تکرار می‌شد:
کاربر دستی لفت می‌داد، ربات هم چیزِ تازه‌ای نمی‌گفت.

این تست سه چیز را قفل می‌کند:
  ۱) درجه‌ی ۰ = رفتارِ قبلی (تبادلِ کاملِ امن) — هیچ چیز شل نمی‌شود.
  ۲) درجه‌ی ۱ = پیش‌قدمِ برگشت‌نداده هم لفت می‌شود و **اول** می‌رود.
  ۳) درجه‌ی ۲ = رکوردِ دستیِ بدونِ طرف هم آزاد می‌شود؛ ولی کانالِ خودِ
     کاربر، رکوردِ یادآوردار و کانالِ تکراری در هیچ درجه‌ای لفت نمی‌شوند.
  + پیامِ «هیچ کاندیدی نیست» حداکثر هر ۶ ساعت یک‌بار و با شمارشِ دلیل‌ها.

اجرا: python3 tests/test_capacity_escalation.py
"""
import importlib.util
import os
import sys
import tempfile

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


TMP = tempfile.mkdtemp(prefix="jafj_capesc_")
os.environ["DATA_DIR"] = TMP
os.chdir(TMP)

spec = importlib.util.spec_from_file_location("m95ce", SRC)
m = importlib.util.module_from_spec(spec)
m.__file__ = SRC
spec.loader.exec_module(m)

src = open(SRC, encoding="utf-8").read()


def rec(rid, **kw):
    base = {"id": rid, "status": "joined", "link": f"@c{rid}",
            "peer_id": 1000 + rid, "chat_id": 5000 + rid, "direction": "in",
            "joined_at": 1700000000 + rid, "peer_joined_at": None,
            "next_reminder": 0, "created_at": 1700000000 + rid}
    base.update(kw)
    return base


# ── ۱) درجه ۰: همان قواعدِ سخت‌گیرانه ────────────────────────────────
out_unret = rec(1, direction="out", peer_joined_at=0)
out_done = rec(2, direction="out", peer_joined_at=1700000000)
in_rec = rec(3)
strict = m.select_capacity_leave_batch([out_unret, out_done, in_rec], limit=10)
check("درجه ۰: پیش‌قدمِ برگشت‌نداده حذف می‌شود",
      [r["id"] for r in strict] == [2, 3], [r["id"] for r in strict])

# ── ۲) درجه ۱: برگشت‌نداده‌ها هم آزاد می‌شوند و اول می‌روند ───────────
lvl1 = m.select_capacity_leave_batch([out_unret, out_done, in_rec],
                                     limit=10, relax=1)
check("درجه ۱: پیش‌قدمِ برگشت‌نداده آزاد می‌شود",
      1 in [r["id"] for r in lvl1], [r["id"] for r in lvl1])
check("درجه ۱: اول کم‌ارزش‌ترین‌ها (برگشت‌نداده) لفت می‌شوند",
      [r["id"] for r in lvl1][:1] == [1], [r["id"] for r in lvl1])
check("درجه ۱: ترتیبِ بقیه همان قدیمی‌ترین‌ها",
      [r["id"] for r in lvl1] == [1, 2, 3], [r["id"] for r in lvl1])

# ── ۳) درجه ۲: رکوردِ دستیِ بدونِ طرف ────────────────────────────────
no_peer = rec(4, peer_id=None)
check("درجه ۱: رکوردِ بدونِ طرف هنوز کاندید نیست",
      4 not in [r["id"] for r in m.select_capacity_leave_batch(
          [no_peer], limit=5, relax=1)])
check("درجه ۲: رکوردِ بدونِ طرف کاندید است (کانالی که فقط خودم جوین شدم)",
      [r["id"] for r in m.select_capacity_leave_batch(
          [no_peer], limit=5, relax=2)] == [4])

# ── ۴) محافظ‌های همیشگی در همه‌ی درجه‌ها ─────────────────────────────
own = rec(9, link="@mychannel")
rem = rec(8, next_reminder=999999)
dup = [rec(6, chat_id=777), rec(7, chat_id=777)]
for lvl in (0, 1, 2):
    got_own = [r["id"] for r in m.select_capacity_leave_batch(
        [own, in_rec], own_channels=["@mychannel"], limit=9, relax=lvl)]
    check(f"درجه {lvl}: کانالِ خودِ کاربر لفت نمی‌شود",
          got_own == [3], got_own)
    got_rem = [r["id"] for r in m.select_capacity_leave_batch(
        [rem, in_rec], limit=9, relax=lvl)]
    check(f"درجه {lvl}: رکوردِ با یادآورِ فعال لفت نمی‌شود",
          got_rem == [3], got_rem)
    got_dup = [r["id"] for r in m.select_capacity_leave_batch(
        dup + [in_rec], limit=9, relax=lvl)]
    check(f"درجه {lvl}: کانالِ تکراری لفت نمی‌شود",
          got_dup == [3], got_dup)

# ── ۵) تشخیص: چرا هیچ کاندیدی نیست ──────────────────────────────────
pool = [rec(11, direction="out", peer_joined_at=0),
        rec(12, next_reminder=999),
        rec(13, peer_id=None),
        rec(14, link="@mychannel")]
d = m.capacity_diag(pool, own_channels=["@mychannel"])
check("تشخیص: تعدادِ کلِ joined", d["joined"] == 4, d)
check("تشخیص: برگشت‌نداده", d["unreturned"] == 1, d)
check("تشخیص: یادآوردار", d["reminder"] == 1, d)
check("تشخیص: بدونِ طرف", d["no_peer"] == 1, d)
check("تشخیص: کانالِ خودم", d["own"] == 1, d)

# ── ۶) متنِ پیام ────────────────────────────────────────────────────
note0 = m.format_capacity_cleanup_note([], 30, diag=d)
check("پیامِ بی‌کاندید: همچنان «هیچ تبادل» و «ریست» دارد",
      "هیچ تبادل" in note0 and "ریست" in note0, note0)
check("پیامِ بی‌کاندید: عددِ دلیل‌ها را می‌گوید",
      "کانالِ خودت" in note0 and "برگشت‌نداده" in note0, note0)
check("پیامِ بی‌کاندید: دستورِ لفتِ دستیِ یک مورد را می‌دهد",
      "تبادل خروج" in note0, note0)

note_r = m.format_capacity_cleanup_note(["@c1"], 30, relax=1)
check("پیامِ درجه ۱: شفاف می‌گوید تبادلِ کامل نبود",
      "ℹ️" in note_r and "برگشت‌نداده" in note_r, note_r)
check("پیامِ درجه ۱: همچنان «جا آزاد شد» را می‌گوید",
      "جا آزاد شد" in note_r, note_r)
note0_plain = m.format_capacity_cleanup_note([], 30)
check("پیامِ بی‌کاندیدِ بدونِ تشخیص هم خراب نمی‌شود",
      "هیچ تبادل" in note0_plain)

# ── ۷) سیم‌کشی در cleanup_capacity_for_slots ─────────────────────────
i = src.index("async def cleanup_capacity_for_slots(")
j = src.index("async def ", i + 40)
cleanup_src = src[i:j]
check("پاکسازی: سه پله‌ی نرم‌شدن دارد",
      cleanup_src.count("select_capacity_leave_batch(") == 3,
      cleanup_src.count("select_capacity_leave_batch("))
check("پاکسازی: درجه‌ی ۲ هم امتحان می‌شود", "relax=2" in cleanup_src)
check("پاکسازی: نرم‌شدن در لاگ ثبت می‌شود", "ex_capacity_relax" in cleanup_src)
check("پاکسازی: پیامِ بی‌کاندید throttle دارد",
      "_capacity_note_at" in cleanup_src
      and "CAPACITY_NOTE_GAP_SEC" in cleanup_src)
check("۹۵: فاصله‌ی پیام ۶ ساعت است",
      "CAPACITY_NOTE_GAP_SEC = 6 * 3600" in src)

print()
if FAILS:
    print("FAILED:", len(FAILS))
    sys.exit(1)
print("ALL PASS")
