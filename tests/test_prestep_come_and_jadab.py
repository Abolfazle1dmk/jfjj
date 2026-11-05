#!/usr/bin/env python3
"""«پیش‌قدم» — دو باگِ گزارش/پیام که کاربر دید:

  ۱) پیامِ پیش‌قدم بدونِ «زیر متن»: وقتی خودت اول جوینِ کانال طرف می‌شوی،
     ربات روی پیامِ طرف یک متن می‌فرستد که باید **کانالِ خودت زیرش** باشد
     (طرف فقط از همین پیام می‌فهمد کجا جوین شود). ولی این خط فقط برای
     «نیومدی» اضافه می‌شد؛ پیامِ پیش‌قدم در همه‌ی حالت‌ها — متنِ سفارشی،
     یا وقتی فقط «پیام موفق» ثبت شده — **بدون آدرس** می‌رفت و تبادل
     هیچ‌وقت کامل نمی‌شد.

  ۲) «جذب موفق» هیچ‌وقت بالا نمی‌رفت: در حالت پیش‌قدم (direction='out')
     طرف دیرتر برمی‌گردد و عضوِ کانالِ تو می‌شود؛ آن لحظه هیچ‌جا ثبت
     نمی‌شد — فقط شمارنده‌ی «پیش‌قدم موفق» بالا می‌رفت. الان
     `peer_joined_at` ذخیره می‌شود، در آمارِ «جذب موفق» می‌آید و یک‌بار
     هم گزارشِ «🤝 تبادل کامل شد» برایت می‌رود.

همه‌ی سنجه‌ها روی **کدِ واقعی** اجرا می‌شوند: تابع `reply_joined` و
بلوکِ چکِ نگهبانی از خودِ `95.py` استخراج و با Engine/DB واقعی و
telethonِ جعلی اجرا می‌شوند.
"""
import os
import shutil
import subprocess
import sys
import tempfile

HERE = os.path.dirname(os.path.abspath(__file__))
REPO = os.path.dirname(HERE)
ROOT = os.path.join(tempfile.gettempdir(), "jafj_prestep_run")
APP = os.path.join(ROOT, "app")
DATA = os.path.join(ROOT, "data")


DRIVER = r"""
import asyncio, importlib.util, os, sqlite3, sys, time
from types import SimpleNamespace
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


async def anoop(x=0):
    return None


def fresh_engine(chan="@mychan"):
    for f in ("jafj_settings.json", "jafj.db", "jafj_limits.json"):
        if os.path.exists(f):
            os.remove(f)
    eng = m.Engine()
    eng.st.prof("standard")["channel"] = chan
    x = eng.ex_cfg()
    x["reply"] = True
    x["max_strikes"] = 2
    x["max_reminders"] = 2
    x["permanent_check"] = True
    x["permanent_check_max_hours"] = 24
    eng.st.save()
    return eng, x


def slice_block(start_marker, end_marker, ind=16):
    a = src.find(start_marker)
    assert a > 0, "start marker missing: %r" % (start_marker,)
    b = src.find(end_marker, a)
    assert b > a, "end marker missing: %r" % (end_marker,)
    lines = src[a:b].splitlines()
    while lines and (lines[0].lstrip().startswith("#") or not lines[0].strip()):
        lines.pop(0)
    while lines and not lines[-1].strip():
        lines.pop()
    return "\n".join(ln[ind:] if ln.startswith(" " * ind) else ln
                     for ln in lines)


reply_ded = slice_block("async def reply_joined(rec):", "def joins_left_today():", ind=4)
guard_ded = slice_block("# ۳) چک دوره‌ای نگهبانی", "# برای دقت فاصله‌ی یادآوری")

SENT = []


class Client:
    async def send_message(self, chat, body, **kw):
        SENT.append((chat, body, kw))
        return SimpleNamespace(id=999)


class Cd:
    async def action(self, kind, rec_id, fn, *a, **kw):
        return await fn()


def build_reply(eng, ex_cd):
    ns = {"m": m, "eng": eng, "client": Client(), "ex_cd": ex_cd,
          "asyncio": asyncio, "time": time,
          "DRY_RUN": False,
          "come_delay_seconds": lambda: 0,
          "response_delay_seconds": lambda: 0}
    exec("async def _r(rec):\n"
         + "\n".join("    " + l for l in reply_ded.splitlines())
         + "\n    return await reply_joined(rec)\n", ns)
    return ns["_r"]


def mk_rec(eng, peer, link, **kw):
    rec, _ = eng.db.ex_add(peer, "n%d" % peer, link)
    kw.setdefault("status", "joined")
    kw.setdefault("direction", "out")
    kw.setdefault("last_check", 0)
    kw.setdefault("next_check", 0)
    eng.db.ex_set(rec["id"], **kw)
    return eng.db.ex_get(rec["id"])


async def send_come(eng, x, **setup):
    # پیامِ پس از جوینِ پیش‌قدم را با کدِ واقعی می‌سازد و می‌فرستد.
    for k, v in setup.items():
        x[k] = v
    eng.st.save()
    rec = mk_rec(eng, 7001, "@peerchan", direction="out", replied=0,
                 src_chat=555, src_msg=777)
    SENT.clear()
    ok = await build_reply(eng, Cd())(rec)
    body = SENT[-1][1] if SENT else ""
    return ok, body


# ═══════ A) پیامِ پیش‌قدم: کانالِ خودت باید زیرِ متن باشد ═══════
async def part_a():
    print("--- A) پیامِ پیش‌قدم (زیر متن: کانال خودت) ---")
    eng, x = fresh_engine()

    # A1) متنِ سفارشیِ پیش‌قدم بدونِ {mychannel}
    ok, body = await send_come(eng, x, msg_come="جوینم بیا", msg_ok="", msg_first="")
    check(ok and body == "جوینم بیا\n@mychan",
          "A1: متنِ سفارشیِ پیش‌قدم + کانالِ من زیرش (بود %r)" % body)

    # A2) متنی که خودش {mychannel} دارد → دوبار اضافه نشود
    ok, body = await send_come(eng, x, msg_come="جوینم، {mychannel} را جوین شو")
    check(body == "جوینم، @mychan را جوین شو",
          "A2: اگر متن خودش {mychannel} دارد، دوبار نمی‌آید (بود %r)" % body)

    # A3) متنِ پیش‌قدم خالی، فقط «پیام موفق» ثبت شده → همان + کانال
    ok, body = await send_come(eng, x, msg_come="", msg_first="", msg_ok="اومدم بیا")
    check(body == "اومدم بیا\n@mychan",
          "A3: بازگشت به «پیام موفق» هم کانال را زیرش می‌آورد (بود %r)" % body)

    # A4) متنِ پیش‌قدم خالی، msg_first ثبت شده
    ok, body = await send_come(eng, x, msg_come="", msg_first="اومدم", msg_ok="")
    check(body == "اومدم\n@mychan",
          "A4: مسیر msg_first هم کانال را زیرش دارد (بود %r)" % body)

    # A5) آدرسِ نوشته‌شده به شکلِ دیگر (t.me) → دوبار اضافه نشود
    ok, body = await send_come(eng, x, msg_come="بیا t.me/mychan",
                               msg_first="", msg_ok="")
    check(body == "بیا t.me/mychan",
          "A5: آدرسِ t.me داخل متن، تکرار نمی‌شود (بود %r)" % body)

    # A6) کانالِ من تنظیم نشده → متن دست‌نخورده (و کرشی نیست)
    eng, x = fresh_engine(chan="")
    ok, body = await send_come(eng, x, msg_come="جوینم بیا", msg_first="", msg_ok="")
    check(ok and body == "جوینم بیا",
          "A6: بدونِ کانالِ تنظیم‌شده، همان متن می‌رود (بود %r)" % body)

    # A7) reply خاموش → هیچ پیامی نمی‌رود
    eng, x = fresh_engine()
    x["reply"] = False
    ok, body = await send_come(eng, x, msg_come="جوینم بیا")
    check(not ok and not SENT,
          "A7: با خاموش‌بودنِ پاسخ، پیامِ پیش‌قدم نمی‌رود")

    # A8) لینکِ طرف با placeholder قدیمی نباید داخل پیام پیش‌قدم بیاید؛
    # فقط کانالِ خودمان زیر متن قرار می‌گیرد.
    eng, x = fresh_engine()
    ok, body = await send_come(eng, x, msg_come="جوینم {channel}؛ کانال من {mychannel} را جوین شو")
    check(ok and "@peerchan" not in body and body ==
          "جوینم؛ کانال من @mychan را جوین شو",
          "A8: پیام پیش‌قدم لینک طرف را حذف می‌کند و لینک خودم را نگه می‌دارد")

    # A9) مسیرِ غیرِ پیش‌قدم (طرف اول آمده) پیام موفق را بدونِ کانال خودم می‌فرستد.
    eng, x = fresh_engine()
    x["msg_ok"] = "اومدم ✅"
    rec = mk_rec(eng, 7002, "@peerchan2", direction="in", replied=0,
                 src_chat=556, src_msg=778)
    SENT.clear()
    ok = await build_reply(eng, Cd())(rec)
    body = SENT[-1][1] if SENT else ""
    check(body == "اومدم ✅",
          "A9: در تبادلِ عادی (طرف اول آمده) متن دست‌نخورده است (بود %r)" % body)


asyncio.run(part_a())


# ═══════ B) «جذب موفق» و گزارشِ تکمیلِ تبادل ═══════
def part_b_counts():
    print("--- B) شمارنده‌ی «جذب موفق» ---")
    eng, x = fresh_engine()
    now = int(time.time())
    # رکورد عادی: طرف اول آمد، من بعداً جوین شدم
    mk_rec(eng, 7101, "@in1", direction="in", joined_at=now)
    # رکورد پیش‌قدم: من اول رفتم، طرف بعداً برگشت
    mk_rec(eng, 7102, "@out1", direction="out", joined_at=now,
           peer_joined_at=now)
    c = eng.db.ex_report_counts(now - 60)
    check(c["in_joined"] == 2,
          "B1: هم تبادلِ عادی هم بازگشتِ طرف در «جذب موفق» شمرده شد (بود %d)"
          % c["in_joined"])
    check(c["out_joined"] == 1 and c["joined"] == 2,
          "B2: «پیش‌قدم موفق» و «Join شده» دست‌نخورده‌اند")

    # رکوردی که هر دو شرط را دارد، فقط یک‌بار شمرده شود
    mk_rec(eng, 7103, "@both", direction="in", joined_at=now, peer_joined_at=now)
    c = eng.db.ex_report_counts(now - 60)
    check(c["in_joined"] == 3,
          "B3: رکوردِ دارای هر دو شرط یک‌بار شمرده می‌شود (بود %d)"
          % c["in_joined"])

    # بازگشتِ قدیمی بیرونِ بازه، شمرده نشود
    old = now - 10 * 86400
    mk_rec(eng, 7104, "@old", direction="out", joined_at=old, peer_joined_at=old)
    c = eng.db.ex_report_counts(now - 60)
    check(c["in_joined"] == 3, "B4: بازگشتِ قدیمی در بازه‌ی امروز نمی‌آید")

    # متنِ گزارشِ تکمیل هم واقعاً ساخته می‌شود
    rec = eng.db.ex_find("@out1")
    txt = eng.ex_live_peer_join_text(rec)
    check("تبادل کامل شد" in txt and "@out1" in txt and "جذب موفق" in txt,
          "B5: متنِ «🤝 تبادل کامل شد» ساخته می‌شود")


part_b_counts()


# ═══════ C) مهاجرتِ دیتابیسِ قدیمی ═══════
def part_c_migration():
    print("--- C) مهاجرتِ ستونِ تازه روی دیتابیسِ قدیمی ---")
    path = "old_migrate.db"
    if os.path.exists(path):
        os.remove(path)
    con = sqlite3.connect(path)
    con.executescript(
        "CREATE TABLE exchange ("
        " id INTEGER PRIMARY KEY AUTOINCREMENT, peer_id INTEGER, peer_name TEXT,"
        " link TEXT NOT NULL UNIQUE, channel_title TEXT, status TEXT,"
        " strikes INTEGER, created_at INTEGER, joined_at INTEGER,"
        " last_check INTEGER, note TEXT);")
    con.execute("INSERT INTO exchange (peer_id,link,status,created_at)"
                " VALUES (1,'@oldpeer','joined',1)")
    con.commit()
    con.close()
    db = m.DB(path)
    cols = {r[1] for r in db.conn.execute("PRAGMA table_info(exchange)")}
    check("peer_joined_at" in cols, "C1: ستونِ peer_joined_at اضافه شد")
    row = db._x("SELECT * FROM exchange WHERE link='@oldpeer'", (), "one")
    check(row and not row.get("peer_joined_at"),
          "C2: رکوردِ قدیمی سالم خوانده می‌شود و ستونش خالی است")
    db.ex_set(row["id"], peer_joined_at=123)
    check(db.ex_get(row["id"])["peer_joined_at"] == 123,
          "C3: نوشتنِ ستونِ تازه روی دیتابیسِ قدیمی کار می‌کند")
    db.conn.close()
    os.remove(path)


part_c_migration()


# ═══════ D) چکِ نگهبانی: لحظه‌ی بازگشتِ طرف ثبت و گزارش می‌شود ═══════
class FakeGate:
    def blocked(self):
        return False


class Stub:
    def __init__(self, members=(True,)):
        self.members = list(members)
        self.notes = []
        self.gate = FakeGate()
        self.asyncio = SimpleNamespace(sleep=anoop,
                                       CancelledError=m.asyncio.CancelledError)

    def unk_fallback(self, rec, extra=1):
        return False

    async def confirm(self, pid, fast=False, rec_id=None, confirm=True):
        return self.members.pop(0) if self.members else False

    async def send_rem(self, rec):
        return True

    async def leave(self, link, rec_id=None):
        raise AssertionError("in this scenario no leave should happen")

    async def note(self, text):
        self.notes.append(text)

    async def warn(self, now):
        pass

    @staticmethod
    def reminder_delay():
        return 15

    @staticmethod
    def check_delay():
        return 15

    @staticmethod
    def watch_delay(rec):
        return 30


def make_guard():
    src_txt = (
        "import time\n"
        "fa = m.fa\n"
        "async def _run(eng, x, stub):\n"
        "    confirm_peer_membership = stub.confirm\n"
        "    send_not_joined_reminder = stub.send_rem\n"
        "    leave_link = stub.leave\n"
        "    reminder_delay = stub.reminder_delay\n"
        "    membership_check_delay = stub.check_delay\n"
        "    note = stub.note\n"
        "    warn_membership_check_broken = stub.warn\n"
        "    check_gate = stub.gate\n"
        "    unk_fallback = stub.unk_fallback\n"
        "    watch_delay_seconds = stub.watch_delay\n"
        "    next_action_after = lambda rec, base=None: int(base)\n"
        # سنتینلِ «طرف قابلِ شناسایی نیست» + هشدارش (بلوکِ استخراج‌شده
        # از 95.py این دو را می‌خواند)
        "    CHECK_NO_PEER = m.CHECK_NO_PEER\n"
        "    async def warn_peer_unresolvable(*a, **k):\n"
        "        return None\n"
        "    asyncio = stub.asyncio\n"
        "    now_rem = int(time.time())\n"
        + "\n".join("    " + ln for ln in guard_ded.splitlines()) + "\n")
    ns = {"m": m, "ex_cd": m.ExCooldown(gap_min=0, gap_max=0)}
    exec(src_txt, ns)
    return ns["_run"]


run_guard = make_guard()

eng, x = fresh_engine()
rec = mk_rec(eng, 7201, "@prestep", strikes=1, direction="out", replied=1)
st = Stub(members=[True])
asyncio.run(run_guard(eng, x, st))
r = eng.db.ex_get(rec["id"])
check(bool(r["peer_joined_at"]),
      "D1: بازگشتِ طرف در رکوردِ پیش‌قدم ثبت شد")
check(sum(1 for n in st.notes if "تبادل کامل شد" in n) == 1,
      "D2: گزارشِ «🤝 تبادل کامل شد» یک‌بار رفت (%d بار)" % len(st.notes))
check(eng.db.ex_report_counts(int(r["peer_joined_at"]) - 1)["in_joined"] == 1,
      "D3: همان لحظه در «جذب موفق» شمرده شد")
check("ex_peer_joined" in [e["kind"] for e in eng.db.recent(5)],
      "D4: رویداد ex_peer_joined ثبت شد")

# دورِ بعدیِ چک نگهبانی → گزارشِ تکراری نمی‌رود
st2 = Stub(members=[True])
asyncio.run(run_guard(eng, x, st2))
check(not st2.notes, "D5: دورِ بعدی گزارشِ تکراری نمی‌فرستد")

# رکوردِ غیرِ پیش‌قدم (طرف اول آمده) → بی‌صدا، مثل قبل
eng, x = fresh_engine()
rec = mk_rec(eng, 7202, "@incoming", strikes=1, direction="in", replied=1)
st3 = Stub(members=[True])
asyncio.run(run_guard(eng, x, st3))
r = eng.db.ex_get(rec["id"])
check(not r["peer_joined_at"] and not st3.notes,
      "D6: تبادلِ عادی (direction=in) رفتارِ بی‌صدای قبلی را دارد")

# در حالتِ گزارشِ خلاصه، پیامِ لحظه‌ای نمی‌رود (فقط آمار ثبت می‌شود)
eng, x = fresh_engine()
x["report_mode"] = "summary"
eng.st.save()
rec = mk_rec(eng, 7203, "@prestep2", strikes=1, direction="out", replied=1)
st4 = Stub(members=[True])
asyncio.run(run_guard(eng, x, st4))
r = eng.db.ex_get(rec["id"])
check(bool(r["peer_joined_at"]) and not st4.notes,
      "D7: در حالتِ «خلاصه» بازگشت ثبت می‌شود ولی پیامِ لحظه‌ای نمی‌رود")

print("DONE FAIL" if FAILS else "DONE PASS")
if FAILS:
    for f in FAILS:
        print("  -", f)
    sys.exit(1)
print("ALL: PASS")
"""


def main():
    os.makedirs(APP, exist_ok=True)
    os.makedirs(DATA, exist_ok=True)
    shutil.copy(os.path.join(REPO, "95.py"), os.path.join(APP, "95.py"))
    env = os.environ.copy()
    env["DATA_DIR"] = DATA
    for k in ("PORT", "RENDER", "RAILWAY_ENVIRONMENT"):
        env.pop(k, None)
    p = subprocess.run([sys.executable, "-c", DRIVER], cwd=APP, env=env,
                       capture_output=True, text=True, timeout=300)
    print(p.stdout[-9000:])
    if p.stderr.strip():
        print("STDERR:", p.stderr[-3000:])
    return p.returncode


if __name__ == "__main__":
    sys.exit(main())
