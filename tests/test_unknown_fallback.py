#!/usr/bin/env python3
"""بن‌بستِ «چک نامشخص» + نرخِ پنهانِ GetParticipant.

باگ: هر سه مسیر (پیام ورودی، حلقه‌ی یادآوری، چکِ نگهبانی) نتیجه‌ی قطعیِ
confirm_peer_membership را می‌خواستند؛ با FloodWait نتیجه None می‌شد و
جریان تا ابد عقب می‌افتاد («فقط جوین می‌شه، نه چک نه نیومدی نه لفت»).
ضمناً هر چک دو درخواست می‌زد و چکِ دومِ هر جفت با queue=False فاصله‌ی
۱۵–۲۰ ثانیه‌ی صف را دور می‌زد.

فیکس: unk_fallback + پارامترِ confirm — چکِ معمول یک درخواست، چکِ دوبل
فقط قبل از لفت.
"""
import os
import shutil
import subprocess
import sys
import tempfile

HERE = os.path.dirname(os.path.abspath(__file__))
REPO = os.path.dirname(HERE)
ROOT = os.path.join(tempfile.gettempdir(), "jafj_unknown_fallback_run")
APP = os.path.join(ROOT, "app")
DATA = os.path.join(ROOT, "data")

DRIVER = r"""
# ── نام‌های تازه‌ی ۹۵.py (سنتینلِ «نرفت» + علتِ چک) ──
# برش‌های کد در namespaceهای این درایور exec می‌شوند، پس هر گلوبالی که کدِ
# برش‌خورده می‌خواند باید این‌جا هم تعریف شده باشد.
class _CdStub:
    def __repr__(self):
        return "CHECK_DEFERRED"


def _ns(d):
    d.setdefault("_LAST_CHECK_WHY", {"why": "", "at": 0})
    d.setdefault("_note_check_why", (lambda w: None))
    for _nm in ("ChannelInvalidError", "UsernameInvalidError"):
        d.setdefault(_nm, type(_nm, (Exception,), {}))
    if "CHECK_DEFERRED" not in d:
        _m = globals().get("m")
        d["CHECK_DEFERRED"] = getattr(_m, "CHECK_DEFERRED", None) or _CdStub()
    return d

import asyncio, importlib.util, os, sys, time
sys.path.insert(0, os.getcwd())

spec = importlib.util.spec_from_file_location("m95", "95.py")
m = importlib.util.module_from_spec(spec)
spec.loader.exec_module(m)
src = open("95.py", encoding="utf-8").read()

FAILS = []

def check(cond, label):
    if cond:
        print("OK", label)
        return True
    print("FAIL", label)
    FAILS.append(label)
    return False


for f in ("jafj_settings.json", "jafj.db", "jafj_limits.json"):
    if os.path.exists(f):
        os.remove(f)
eng = m.Engine()
eng.st.prof("standard")["channel"] = "@std_chan"
x = eng.ex_cfg()
CD0 = m.ExCooldown(gap_min=0, gap_max=0)

check(x.get("unk_fallback_after") == 0, "U0: تبدیل نامشخص به منفی خاموش است")


# ═══════ U1 — آستانه‌ی unk_fallback ═══════
a = src.find("    def unk_fallback(rec, extra=1):")
b = src.find("    def reminder_delay():", a)
assert a > 0 and b > a, "unk_fallback not found"
ded = "\n".join(ln[4:] if ln.startswith("    ") else ln
                for ln in src[a:b].splitlines())
uns = {"eng": eng}
_ns(uns)
exec(ded, uns)
unk_fallback = uns["unk_fallback"]

check(unk_fallback({"unk_streak": 0}) is False, "U1: آستانه۲ — بارِ اول نه")
check(unk_fallback({"unk_streak": 1}) is False, "U1: آستانه۲ — بارِ دوم هم خیر")
check(unk_fallback({"unk_streak": 5}) is False, "U1: streak بالا هم نامشخص")
check(unk_fallback({"unk_streak": 0}, extra=2) is False, "U1: extra=2 هم نامشخص")
check(unk_fallback({}, extra=0) is False, "U1: extra=0 → هرگز")
check(unk_fallback(None) is False, "U1: رکوردِ None امن است")
check(unk_fallback({"unk_streak": "خراب"}) is False,
      "U1: مقدارِ خرابِ رکورد → صفر فرض می‌شود")

x["unk_fallback_after"] = 0
check(unk_fallback({"unk_streak": 99}) is False, "U1: آستانه ۰ → هرگز")
x["unk_fallback_after"] = 5
check(unk_fallback({"unk_streak": 3}) is False, "U1: آستانه ۵ — ۴ کافی نیست")
check(unk_fallback({"unk_streak": 4}) is False, "U1: آستانه ۵ — پنجمی هم نامشخص")
x["unk_fallback_after"] = 2
print("DONE U1 threshold")


# ═══════ U2 — سیم‌کشیِ سورس ═══════
check("async def confirm_peer_membership(user_id, fast=False, rec_id=None,"
      in src and "confirm=True):" in src, "U2: پارامترِ confirm در امضا")
check("if first is not False or not confirm:" in src,
      "U2: confirm=False → همان نتیجه‌ی چکِ اول")
check(src.count("confirm=False") >= 3,
      "U2: هر دو حلقه + مسیر پیام با confirm=False چک می‌کنند")
check(src.count("_conf = await confirm_peer_membership") == 2,
      "U2: دقیقاً دو چکِ دوبل قبلِ لفت")
check(src.count("لفت لغو شد — تأیید شد عضو است") == 2,
      "U2: هر دو لفت با تأییدِ عضویت لغو می‌شوند")
check("_need_check = bool(claim or replied_to_me or (" in src,
      "U2: چکِ ورودی فقط وقتی لازم است")
check("unk_streak=int(rec0.get(\"unk_streak\") or 0) + 1," in src,
      "U2: مسیرِ «نامشخص» شمارنده را بالا می‌برد")
check(src.count("if still is None and unk_fallback(rec):") == 2,
      "U2: هر دو حلقه fallback دارند")
print("DONE U2 wiring")


# ═══════ U3 — شمارشِ واقعیِ درخواست‌ها ═══════
a = src.find("    async def confirm_peer_membership")
b = src.find("    async def join_link", a)
cf_src = "\n".join(ln[4:] if ln.startswith("    ") else ln
                   for ln in src[a:b].splitlines())

CALLS = []
class FakeAsyncio:
    @staticmethod
    async def sleep(s):
        pass
async def always_out(uid, rec_id=None, queue=True):
    CALLS.append(queue)
    return False
cns = {"eng": eng, "asyncio": FakeAsyncio, "peer_in_my_channel": always_out,
       "membership_check_delay": lambda: 20, "ex_cd": CD0}
_ns(cns)
exec(cf_src, cns)
confirm = cns["confirm_peer_membership"]

CALLS.clear()
got = asyncio.run(confirm(1, rec_id=1, confirm=False))
check(got is False and CALLS == [True],
      "U3: confirm=False → فقط یک درخواست (بود %r)" % (CALLS,))

CALLS.clear()
got = asyncio.run(confirm(1, rec_id=1))
check(got is False and len(CALLS) == 2, "U3: پیش‌فرض → دو درخواست")
check(CALLS[1] is False,
      "U3: چکِ دوم queue=False است (نوبتِ تازه‌ی صف نمی‌گیرد)")

async def always_in(uid, rec_id=None, queue=True):
    CALLS.append(queue)
    return True
cns["peer_in_my_channel"] = always_in
_ns(cns)
exec(cf_src, cns)
confirm2 = cns["confirm_peer_membership"]
CALLS.clear()
check(asyncio.run(confirm2(1)) is True and len(CALLS) == 1,
      "U3: نتیجه‌ی مثبت → یک درخواست")
print("DONE U3 request count")


# ═══════ U4 — رفتارِ واقعیِ حلقه‌ی یادآوری با چکِ همیشه None ═══════
a = src.find("# ── یادآوری عضو‌نشده: دو پیام «نیومدی»")
b = src.find("# ۳) چک دوره‌ای", a)
assert a > 0 and b > a, "reminder loop markers missing"
lines = src[a:b].splitlines()
while lines and (lines[0].lstrip().startswith("#") or not lines[0].strip()):
    lines.pop(0)
while lines and not lines[-1].strip():
    lines.pop()
IND = 16
ded = "\n".join(ln[IND:] if ln.startswith(" " * IND) else ln for ln in lines)
harness = (
    "import time\n"
    "async def _run(eng, x, stub):\n"
    "    now_rem = int(time.time())\n"
    "    confirm_peer_membership = stub.confirm\n"
    "    send_not_joined_reminder = stub.send_rem\n"
    "    leave_link = stub.leave\n"
    "    reminder_delay = stub.reminder_delay\n"
    "    membership_check_delay = stub.check_delay\n"
    "    note = stub.note\n"
    "    check_gate = stub.gate\n"
    "    warn_membership_check_broken = stub.warn_broken\n"
    "    unk_fallback = stub.unk_fallback\n"
    "    ex_cd = CD0\n"
    "    next_action_after = lambda rec, base=None: int(base)\n"
    + "\n".join("    " + ln for ln in ded.splitlines())
    + "\n"
)
hns = {"CD0": CD0}
_ns(hns)
exec(harness, hns)
run_reminder = hns["_run"]

class GateStub:
    def blocked(self, now=None):
        return False

class Stub:
    def __init__(self, results, real_fallback=True):
        self.results = results
        self.real_fallback = real_fallback
        self.sent = []
        self.left = []
        self.notes = []
        self.warned = []
        self.confirms = []
        self.gate = GateStub()
    def unk_fallback(self, rec, extra=1):
        if not self.real_fallback:
            return False
        return unk_fallback(rec, extra)
    async def confirm(self, pid, fast=False, rec_id=None, confirm=True):
        self.confirms.append((pid, bool(confirm)))
        val = self.results.get(pid)
        if isinstance(val, list):
            return val.pop(0) if val else None
        return val
    async def send_rem(self, rec):
        self.sent.append(rec["id"])
        return True
    async def leave(self, link, rec_id=None):
        self.left.append(link)
        return True, ""
    async def note(self, text):
        self.notes.append(text)
    async def warn_broken(self, now):
        self.warned.append(now)
    @staticmethod
    def reminder_delay():
        return 15
    @staticmethod
    def check_delay():
        return 15

def mkrec(peer, link, status="pending", reminders=0, direction="in"):
    r, _n = eng.db.ex_add(peer, "p%d" % peer, link)
    eng.db.ex_set(r["id"], status=status, direction=direction,
                  reminders=reminders, peer_id=peer, src_chat=11, src_msg=22,
                  next_reminder=int(time.time()) - 5, unk_streak=0)
    return eng.db.ex_get(r["id"])

r1 = mkrec(9001, "@u9001")
stub = Stub({9001: None})
asyncio.run(run_reminder(eng, x, stub))
g = eng.db.ex_get(r1["id"])
check(stub.sent == [], "U4: بارِ اولِ «نامشخص» → «نیومدی» نمی‌رود")
check(int(g["unk_streak"] or 0) == 1, "U4: unk_streak=1 شد (بود %r)" % g["unk_streak"])
check(int(g["strikes"] or 0) == 0, "U4: نتیجه‌ی بی‌نتیجه اخطارِ لفت نیست")

eng.db.ex_set(r1["id"], next_reminder=int(time.time()) - 5)
asyncio.run(run_reminder(eng, x, stub))
g2 = eng.db.ex_get(r1["id"])
check(stub.sent == [],
      "U4: بارِ دوم → نامشخص ماند و پیام نرفت")
check(stub.confirms and all(c[1] is False for c in stub.confirms),
      "U4: چکِ حلقه‌ی یادآوری تک‌درخواستی است (confirm=False)")
print("DONE U4 reminder loop fallback")


# ═══════ U5 — لفتِ حلقه‌ی یادآوری با تأییدِ دوبل لغو می‌شود ═══════
r2 = mkrec(9002, "@u9002", status="joined", reminders=2, direction="out")
stub2 = Stub({9002: [False, True]})
asyncio.run(run_reminder(eng, x, stub2))
g3 = eng.db.ex_get(r2["id"])
check(stub2.left == [], "U5: لفت انجام نشد (چکِ دوبل عضو بودن را تأیید کرد)")
check(g3["status"] == "joined", "U5: رکورد همچنان joined ماند")
check(int(g3["strikes"] or 0) == 0, "U5: strikes صفر شد")
check("لفت لغو شد" in (g3.get("note") or ""), "U5: note شاملِ «لفت لغو شد»")
check(len(stub2.confirms) == 2 and stub2.confirms[1][1] is True,
      "U5: چکِ دومِ قبلِ لفت با confirm=True است (دوبل)")
r_unknown = mkrec(9010, "@u9010", status="joined", reminders=2, direction="out")
unknown_stub = Stub({9010: [False, None]})
asyncio.run(run_reminder(eng, x, unknown_stub))
check(unknown_stub.left == [], "U5: تأیید نهایی نامشخص → لفت ممنوع")
check(eng.db.ex_get(r_unknown["id"])["next_reminder"] > int(time.time()),
      "U5: تأیید نامشخص دوباره زمان‌بندی شد")
print("DONE U5 reminder-loop leave cancelled")


# ═══════ U6 — چکِ نگهبانی: fallback و لغوِ لفت ═══════
a = src.find("# ۳) چک دوره‌ای")
b = src.find("# برای دقت فاصله‌ی یادآوری", a)
assert a > 0 and b > a, "watch loop markers missing"
wlines = src[a:b].splitlines()
while wlines and (wlines[0].lstrip().startswith("#") or not wlines[0].strip()):
    wlines.pop(0)
while wlines and not wlines[-1].strip():
    wlines.pop()
wded = "\n".join(ln[IND:] if ln.startswith(" " * IND) else ln for ln in wlines)
wharness = (
    "import asyncio, time\n"
    "async def _runw(eng, x, stub):\n"
    "    confirm_peer_membership = stub.confirm\n"
    "    send_not_joined_reminder = stub.send_rem\n"
    "    leave_link = stub.leave\n"
    "    reminder_delay = stub.reminder_delay\n"
    "    membership_check_delay = stub.check_delay\n"
    "    watch_delay_seconds = stub.watch_delay\n"
    "    warn_membership_check_broken = stub.warn_broken\n"
    "    note = stub.note\n"
    "    check_gate = stub.gate\n"
    "    unk_fallback = stub.unk_fallback\n"
    "    ex_cd = CD0\n"
    "    fa = m.fa\n"
    "    next_action_after = lambda rec, base=None: int(base)\n"
    + "\n".join("    " + ln for ln in wded.splitlines())
    + "\n"
)
whns = {"CD0": CD0, "m": m, "asyncio": asyncio}
_ns(whns)
exec(wharness, whns)
run_watch = whns["_runw"]

class WStub(Stub):
    @staticmethod
    def watch_delay(rec):
        return 15

def mkjoined(peer, link, replied=1, strikes=0):
    r, _n = eng.db.ex_add(peer, "p%d" % peer, link)
    eng.db.ex_set(r["id"], status="joined", peer_id=peer, replied=replied,
                  strikes=strikes, direction="out", src_chat=11, src_msg=22,
                  joined_at=int(time.time()) - 60,
                  next_check=int(time.time()) - 5, next_reminder=0,
                  unk_streak=0)
    return eng.db.ex_get(r["id"])

r3 = mkjoined(9003, "@u9003")
stub3 = WStub({9003: None})
asyncio.run(run_watch(eng, x, stub3))
g4 = eng.db.ex_get(r3["id"])
check(int(g4["unk_streak"] or 0) == 1, "U6: نگهبانی — بارِ اولِ نامشخص → streak=1")
check(int(g4["strikes"] or 0) == 0, "U6: نامشخص اخطارِ لفت حساب نشد")
check(stub3.left == [], "U6: لفتی انجام نشد")

eng.db.ex_set(r3["id"], next_check=int(time.time()) - 5)
asyncio.run(run_watch(eng, x, stub3))
g5 = eng.db.ex_get(r3["id"])
check(int(g5["strikes"] or 0) == 0,
      "U6: بارِ دوم → هنوز نامشخص؛ اخطار ندارد")
check(stub3.confirms and stub3.confirms[0][1] is False,
      "U6: چکِ نگهبانی تک‌درخواستی است")

r4 = mkjoined(9004, "@u9004", strikes=1)
stub4 = WStub({9004: [False, True]})
asyncio.run(run_watch(eng, x, stub4))
g6 = eng.db.ex_get(r4["id"])
check(stub4.left == [], "U6: لفتِ نگهبانی با تأییدِ دوبل لغو شد")
check(g6["status"] == "joined" and int(g6["strikes"] or 0) == 0,
      "U6: رکورد joined ماند و strikes صفر شد")
check("لفت لغو شد" in (g6.get("note") or ""), "U6: note شاملِ «لفت لغو شد»")
r_unknown2 = mkjoined(9011, "@u9011", strikes=1)
unknown_stub2 = WStub({9011: [False, None]})
asyncio.run(run_watch(eng, x, unknown_stub2))
check(unknown_stub2.left == [], "U6: تأیید نهایی نامشخص نگهبانی → لفت ممنوع")
check(eng.db.ex_get(r_unknown2["id"])["next_check"] > int(time.time()),
      "U6: نگهبانی نامشخص دوباره زمان‌بندی شد")
print("DONE U6 watch loop")


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
    env["PORT"] = "8272"
    env["JAFJ_PORT"] = "8272"
    for k in ("RAILWAY_ENVIRONMENT", "RAILWAY_SERVICE_ID", "RAILWAY_PROJECT_ID",
              "RENDER", "RENDER_SERVICE_NAME", "JAFJ_HOSTED", "JAFJ_LOGIN_RETRY",
              "BOT_TOKEN", "API_ID", "API_HASH", "BACKUP_CHAT", "BACKUP_EVERY"):
        env.pop(k, None)
    p = subprocess.run([sys.executable, "-c", DRIVER], cwd=APP, env=env,
                       capture_output=True, text=True, timeout=300)
    return p.stdout, p.stderr, p.returncode


def main():
    print("--- unknown-check deadlock + hidden GetParticipant rate ---")
    reset()
    out, err, rc = run()
    if err.strip():
        print("--- driver stderr (tail) ---")
        print(err[-3000:])
    print("--- driver output ---")
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
