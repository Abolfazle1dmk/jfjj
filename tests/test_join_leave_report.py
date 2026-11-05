#!/usr/bin/env python3
"""«چکِ جوین» و «لفت دادن» — درست کار می‌کنند و درست هم خبر می‌دهند؟

این تست سه چیز را روی **کدِ واقعیِ** `95.py` (نه فقط تأییدِ متن) می‌سنجد:

  ۱) مسیر چکِ نگهبانی (`# ۳) چک دوره‌ای نگهبانی` در `membership_loop`):
     طرف عضو است → هیچ پیام/لفتی نیست و شمارنده صفر می‌شود؛
     طرف از کانال من رفته → بعد از دو منفیِ تأییدشده لفت داده می‌شود،
     وضعیت `left` می‌شود و پیام «👋 لفت انجام شد» با دلیلِ درست می‌رود؛
     طرفِ تازه‌ای که هنوز جوین نشده → لفتِ فوری نمی‌گیرد، اول دور
     «نیومدی» شروع می‌شود؛ و اگر لفت **شکست** بخورد، وضعیت در `joined`
     می‌ماند و پیام «⚠️ لفت انجام نشد» با عقب‌نشینی می‌رود.

  ۲) مسیر حلقه‌ی یادآوری (بعد از دو «نیومدی»): لفت + گزارش با دلیلِ
     «⏳ طرف بعد از پیام‌های «نیومدی» عضو کانال من نشد»، و بازگشت به
     عقب‌نشینی در شکست.

  ۳) گزارش‌ها و آمار:
     - لفتِ **ناموفق** هرگز «لفت» شمرده نمی‌شود: رویدادش `ex_leave_fail`
       است نه `ex_left` و شمارنده‌ی «👋 کانال‌های لفت‌داده‌شده» بالا نمی‌رود
       (قبلاً گزارش می‌گفت لفت داده‌ام در حالی‌که طرف لفت نخورده بود).
     - لفتِ **دستی** (`تبادل خروج N`) هم در آمار می‌آید و نتیجه‌اش
       (موفق/ناموفق) گزارش می‌شود — قبلاً اگر شکست می‌خورد هیچ خبری نمی‌آمد.
     - متنِ `ex_live_leave_text` واقعاً اجرا می‌شود (قبلاً فقط `in src`
       چک شده بود): دلیل‌های `left` / `nojoin` / `manual` و حالتِ خطا.

  ۴) دو باگِ واقعیِ کشف‌شده که همین تست‌ها نگهبانشان‌اند:
     - بازنشستگیِ نگهبانی (سقف ساعت) قبلاً رکورد را «همیشه سررسید»
       می‌گذاشت: `next_check=0` + `last_check=الان` و حلقه هر چند ثانیه
       همان رکورد را دوباره برمی‌داشت و در دیتابیس می‌نوشت.
     - پیام «لفت انجام شد» می‌توانست **دو بار** برود: (الف) وقتی یک مسیر
       دیگر زودتر همان رکورد را لفت می‌داد و مسیر دوم با وضعیتِ کهنه
       دوباره تلاش می‌کرد، (ب) وقتی طرف برای یک کانال دو لینک ثبت کرده
       بود و دو رکورد یک `chat_id` داشتند. حالا هر دو مسیرِ خودکار وضعیت
       را تازه از دیتابیس می‌خوانند و رکوردِ هم‌کانالِ لفت‌شده
       (`ex_same_channel_left`) بی‌صدا بسته می‌شود.
     - لفتِ **ناموفق** هم رویداد `ex_left` می‌زد (آمار را بالا می‌برد).
       حالا فقط لفتِ موفق `ex_left` است و خطا `ex_leave_fail`.
"""
import os
import shutil
import subprocess
import sys
import tempfile

HERE = os.path.dirname(os.path.abspath(__file__))
REPO = os.path.dirname(HERE)
ROOT = os.path.join(tempfile.gettempdir(), "jafj_join_leave_report_run")
APP = os.path.join(ROOT, "app")
DATA = os.path.join(ROOT, "data")
SRC_REPO = REPO


DRIVER = r"""
# ── نام‌های تازه‌ی ۹۵.py (سنتینلِ «نرفت» + علتِ چک) ──
# برش‌های کد در namespaceهای این درایور exec می‌شوند، پس هر گلوبالی که کدِ
# برش‌خورده می‌خواند باید این‌جا هم تعریف شده باشد.
class _CdStub:
    def __repr__(self):
        return "CHECK_DEFERRED"


def _ns(d):
    # نام‌های تازه‌ی هویتِ طرف (رفعِ «Could not find the input entity»):
    # برش‌های این درایور از بدنه‌ی peer_in_my_channel می‌آیند و این‌ها را
    # می‌خوانند.
    _mod = globals().get("m") or globals().get("ns_mod") or globals().get("_m")
    for _nm in ("partner_input_peer", "peer_identity", "remember_peer",
                "scan_dialogs_for_peer", "_input_user"):
        if _mod is not None and hasattr(_mod, _nm):
            d.setdefault(_nm, getattr(_mod, _nm))
    if _mod is not None and hasattr(_mod, "CHECK_NO_PEER"):
        d.setdefault("CHECK_NO_PEER", getattr(_mod, "CHECK_NO_PEER"))
    d.setdefault("_LAST_CHECK_WHY", {"why": "", "at": 0})
    d.setdefault("_note_check_why", (lambda w: None))
    for _nm in ("ChannelInvalidError", "UsernameInvalidError"):
        d.setdefault(_nm, type(_nm, (Exception,), {}))
    d.setdefault("manual_leave_retry_plan", m.manual_leave_retry_plan)
    d.setdefault("leave_error_is_transient", m.leave_error_is_transient)
    if "CHECK_DEFERRED" not in d:
        _m = globals().get("m")
        d["CHECK_DEFERRED"] = getattr(_m, "CHECK_DEFERRED", None) or _CdStub()
    return d

import asyncio, importlib.util, os, sys, time
from types import SimpleNamespace
sys.path.insert(0, os.getcwd())

spec = importlib.util.spec_from_file_location("m95", "95.py")
m = importlib.util.module_from_spec(spec)
spec.loader.exec_module(m)
src = open("95.py", encoding="utf-8").read()

FAILS = []
IND = 16


def check(cond, label):
    print(("OK   " if cond else "FAIL "), label)
    if not cond:
        FAILS.append(label)


async def anoop(x=0):
    return None


def fresh_engine():
    for f in ("jafj_settings.json", "jafj.db", "jafj_limits.json"):
        if os.path.exists(f):
            os.remove(f)
    return m.Engine()


def slice_block(start_marker, end_marker, ind=IND):
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


# ═══════ 0. استخراج بلوک‌های واقعی از سورس ═══════
# ═══════ 1. استخراج بلوکِ چکِ نگهبانی و بلوکِ یادآوری از سورس ═══════
guard_ded = slice_block("# ۳) چک دوره‌ای نگهبانی", "# برای دقت فاصله‌ی یادآوری")
rem_ded = slice_block("# ── یادآوری عضو‌نشده", "# ۳) چک دوره‌ای")
manual_ded = slice_block("# ۱) لفت‌های دستی", "# ۲) جوین تأییدشده‌ها")


def make_harness(block, extra=""):
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
        "    asyncio = stub.asyncio\n"
        "    now_rem = int(time.time())\n"
        + extra
        + "\n".join("    " + ln for ln in block.splitlines())
        + "\n")
    ns = {"m": m, "ex_cd": m.ExCooldown(gap_min=0, gap_max=0)}
    _ns(ns)
    exec(src_txt, ns)
    return ns["_run"]


run_guard = make_harness(guard_ded)
run_rem = make_harness(rem_ded)


class FakeGate:
    def blocked(self):
        return False


class Stub:
    # دست‌های تلگرام جعل می‌شوند؛ منطقِ خودِ 95.py واقعی اجرا می‌شود.
    def __init__(self, members=(False,), leave_ok=True,
                 leave_err="InviteHashExpiredError: gone", calls=None):
        self.members = list(members)
        self.leave_ok = leave_ok
        self.leave_err = leave_err
        self.calls = calls if calls is not None else []
        self.notes = []
        self.reminders = []
        self.gate = FakeGate()
        self.asyncio = SimpleNamespace(sleep=anoop,
                                       CancelledError=m.asyncio.CancelledError)

    def unk_fallback(self, rec, extra=1):
        return False

    async def confirm(self, pid, fast=False, rec_id=None, confirm=True):
        return self.members.pop(0) if self.members else False

    async def send_rem(self, rec):
        self.reminders.append(rec["id"])
        return True

    async def leave(self, link, rec_id=None):
        self.calls.append(("leave", link, rec_id))
        await asyncio.sleep(0.05)      # پنجره‌ی هم‌زمانی را باز می‌کند
        return (True, "") if self.leave_ok else (False, self.leave_err)

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


def mk_engine(chan="@mine"):
    eng = fresh_engine()
    eng.st.prof("standard")["channel"] = chan
    x = eng.ex_cfg()
    x["reply"] = True
    x["max_strikes"] = 2
    x["max_reminders"] = 2
    x["permanent_check"] = True
    x["permanent_check_max_hours"] = 24
    return eng, x


def mk_rec(eng, peer, link, **kw):
    rec, _ = eng.db.ex_add(peer, "n%d" % peer, link)
    kw.setdefault("status", "joined")
    kw.setdefault("direction", "out")
    kw.setdefault("last_check", 0)
    kw.setdefault("next_check", 0)
    eng.db.ex_set(rec["id"], **kw)
    return eng.db.ex_get(rec["id"])


# ═══════ 2. چکِ نگهبانی: طرف هنوز عضو است → هیچ کاری ═══════
# (جهتِ in = طرف اول آمده بود؛ در این حالت چک بی‌صداست. حالتِ پیش‌قدم
#  یعنی direction=out در تستِ test_prestep_come_and_jadab.py سنجیده شده.)
eng, x = mk_engine()
rec = mk_rec(eng, 8101, "@peerchan", strikes=1, direction="in")
st = Stub(members=[True])
asyncio.run(run_guard(eng, x, st))
r = eng.db.ex_get(rec["id"])
print("G1", r["status"], r["strikes"], st.notes, st.calls)
check(r["status"] == "joined" and r["strikes"] == 0,
      "G1: عضو است → وضعیت joined و شمارنده صفر")
check(not st.calls and not st.notes, "G1: نه لفت زده شد نه پیامی رفت")

# ═══════ 3. چکِ نگهبانی: طرف رفته → لفت + گزارشِ درست ═══════
eng, x = mk_engine()
rec = mk_rec(eng, 8102, "@peerchan2", strikes=1, replied=1)
st = Stub(members=[False, False])
asyncio.run(run_guard(eng, x, st))
r = eng.db.ex_get(rec["id"])
print("G2", r["status"], "|", r["note"], "|", st.calls)
print("G2 notes:", st.notes)
check([c[1] for c in st.calls] == ["@peerchan2"], "G2: لفت روی همان کانال زده شد")
check(r["status"] == "left" and r["note"] == "طرف رفت → لفت دادم",
      "G2: وضعیت left + یادداشت درست")
check(any("👋 لفت انجام شد" in n and "خارج شده بود" in n for n in st.notes),
      "G2: گزارش «لفت انجام شد» با دلیلِ درست رفت")
check(eng.db.ex_report_counts(0)["left"] == 1,
      "G2: لفتِ موفق در آمار «لفتدادهشده» شمرده شد")
check("ex_left" in [e["kind"] for e in eng.db.recent(5)],
      "G2: رویداد ex_left ثبت شد")

# ═══════ 4. طرفِ تازه که هنوز جوین نشده → اول «نیومدی»، نه لفت ═══════
eng, x = mk_engine()
rec = mk_rec(eng, 8103, "@peerchan3", strikes=0, replied=0,
             direction="in", src_chat=11, src_msg=22)
st = Stub(members=[False])
asyncio.run(run_guard(eng, x, st))
r = eng.db.ex_get(rec["id"])
print("G3", r["status"], r["strikes"], r["reminders"], r["next_reminder"], st.calls)
check(not st.calls, "G3: لفتِ فوری انجام نشد")
check(r["status"] == "joined" and r["reminders"] == 1 and r["next_reminder"] > 0,
      "G3: دور «نیومدی» شروع شد و نوبتِ بعدی زمان‌بندی شد")

# ═══════ 5. لفت شکست می‌خورد → joined + گزارشِ شکست + آمار سالم ═══════
eng, x = mk_engine()
rec = mk_rec(eng, 8104, "@peerchan4", strikes=1, replied=1)
st = Stub(members=[False, False], leave_ok=False)
asyncio.run(run_guard(eng, x, st))
r = eng.db.ex_get(rec["id"])
kinds = [e["kind"] for e in eng.db.recent(5)]
cnt = eng.db.ex_report_counts(0)
print("G4", r["status"], "|", r["note"], "|", kinds, "|", cnt)
print("G4 notes:", st.notes)
check(r["status"] == "joined" and r["leave_fail"] == 1,
      "G4: شکستِ لفت → وضعیت joined و شمارنده‌ی شکست")
check(r["leave_blocked_until"] > int(time.time()),
      "G4: تلاشِ بعدی با فاصله (عقب‌نشینی) زمان‌بندی شد")
check(any("⚠️ لفت انجام نشد" in n for n in st.notes),
      "G4: گزارش «لفت انجام نشد» رفت")
check("ex_left" not in kinds and "ex_leave_fail" in kinds,
      "G4: رویدادش ex_leave_fail است نه ex_left")
check(cnt["left"] == 0,
      "G4: لفتِ ناموفق در آمار «لفتدادهشده» شمرده نشد")

# ═══════ 6. حلقه‌ی یادآوری: بعد از دو «نیومدی» → لفت + گزارش ═══════
def mk_rem(leave_ok=True, leave_err="InviteHashExpiredError: gone"):
    eng, x = mk_engine()
    rec = mk_rec(eng, 8200, "@peerchan5", replied=1, reminders=2,
                 reminders_total=2, strikes=1,
                 next_reminder=int(time.time()) - 5)
    st = Stub(members=[False, False], leave_ok=leave_ok, leave_err=leave_err)
    return eng, x, rec, st


eng, x, rec, st = mk_rem()
asyncio.run(run_rem(eng, x, st))
r = eng.db.ex_get(rec["id"])
print("G5", r["status"], "|", r["note"], "|", st.notes)
check(r["status"] == "left" and r["note"] == "نیومد → لفت دادم",
      "G5: لفتِ مسیر یادآوری انجام شد")
check(any("👋 لفت انجام شد" in n and "«نیومدی»" in n for n in st.notes),
      "G5: گزارش با دلیلِ «بعد از نیومدیها عضو نشد» رفت")
check(eng.db.ex_report_counts(0)["left"] == 1, "G5: آمار لفت درست است")

eng, x, rec, st = mk_rem(leave_ok=False)
asyncio.run(run_rem(eng, x, st))
r = eng.db.ex_get(rec["id"])
print("G5f", r["status"], "|", r["note"], "|", st.notes)
check(r["status"] == "joined" and r["leave_fail"] == 1,
      "G5f: شکست در این مسیر هم رکورد را left نمی‌کند")
check(eng.db.ex_report_counts(0)["left"] == 0 and
      "ex_leave_fail" in [e["kind"] for e in eng.db.recent(5)],
      "G5f: شکست در آمار «لفت» شمرده نشد")

# ═══════ 7. لفتِ دستی (تبادل خروج N) → وضعیت، آمار و گزارش ═══════
def make_manual_harness():
    txt = (
        "import time\n"
        "fa = m.fa\n"
        "async def _run(eng, x, stub):\n"
        "    leave_link = stub.leave\n"
        "    note = stub.note\n"
        "    asyncio = stub.asyncio\n"
        + "\n".join("    " + ln for ln in manual_ded.splitlines())
        + "\n")
    ns = {"m": m}
    _ns(ns)
    exec(txt, ns)
    return ns["_run"]


run_manual = make_manual_harness()


def mk_manual(leave_ok=True):
    eng, x = mk_engine()
    rec = mk_rec(eng, 8300, "@peerchan6", status="leaving")
    st = Stub(leave_ok=leave_ok)
    return eng, x, rec, st


eng, x, rec, st = mk_manual()
asyncio.run(run_manual(eng, x, st))
r = eng.db.ex_get(rec["id"])
print("M1", r["status"], "|", r["note"], "|", st.notes)
check(r["status"] == "left" and r["note"] == "لفت دستی",
      "M1: لفتِ دستی وضعیت را left کرد")
check(eng.db.ex_report_counts(0)["left"] == 1,
      "M1: لفتِ دستی در آمار «لفتدادهشده» آمد")
check(any("👋 لفت انجام شد" in n and "لفت دستی" in n for n in st.notes),
      "M1: گزارشِ لفتِ دستی رفت")

eng, x, rec, st = mk_manual(leave_ok=False)
asyncio.run(run_manual(eng, x, st))
r = eng.db.ex_get(rec["id"])
print("M2", r["status"], "|", r["note"], "|", st.notes)
check(r["status"] == "failed", "M2: شکستِ لفتِ دستی → وضعیت failed")
check(any("⚠️ لفت انجام نشد" in n for n in st.notes),
      "M2: شکستِ لفتِ دستی هم گزارش می‌شود (قبلاً بی‌صدا بود)")
check(eng.db.ex_report_counts(0)["left"] == 0,
      "M2: شکستِ دستی هم «لفت» شمرده نشد")

# ═══════ 8. متنِ گزارشِ لفت: هر سه دلیل + خطا (واقعاً اجرا می‌شود) ═══════
eng, x = mk_engine()
rec = mk_rec(eng, 8400, "@peerchan7")
t_left = eng.ex_live_leave_text(rec, "", "left")
t_nojoin = eng.ex_live_leave_text(rec, "", "nojoin")
t_manual = eng.ex_live_leave_text(rec, "", "manual")
t_err = eng.ex_live_leave_text(dict(rec, leave_fail=2), "InviteHashExpiredError: gone")
print("T left:", repr(t_left))
print("T manual:", repr(t_manual))
check(t_left.startswith("👋 لفت انجام شد") and "خارج شده بود" in t_left,
      "T1: دلیل left → «طرف از کانال من خارج شده بود»")
check("«نیومدی»" in t_nojoin and "خارج شده بود" not in t_nojoin,
      "T2: دلیل nojoin → «بعد از پیام‌های نیومدی عضو نشد»")
check(t_manual.startswith("👋 لفت انجام شد") and "لفت دستی" in t_manual,
      "T3: دلیل manual → «لفت دستی — خودت دستور دادی»")
check(t_err.startswith("⚠️ لفت انجام نشد") and "InviteHashExpiredError" in t_err
      and "تلاش ناموفق" in t_err,
      "T4: خطا → «لفت انجام نشد» + متن خطا + شمارنده‌ی تلاش")
check("@peerchan7" in t_left, "T5: کانالِ طرف در گزارش می‌آید")

# ═══════ 9. پایان نگهبانی (سقف ساعت) → رکورد دیگر «سررسید» نیست ═══════
eng, x = mk_engine()
old = int(time.time()) - 40 * 3600
rec = mk_rec(eng, 8500, "@peerchan8", joined_at=old, created_at=old)
st = Stub(members=[True])
asyncio.run(run_guard(eng, x, st))
r = eng.db.ex_get(rec["id"])
due = [d["id"] for d in eng.db.ex_due(int(time.time()), 5)]
print("G6", r["note"], "| next_check-now =", r["next_check"] - int(time.time()),
      "| due:", due)
check("پایان نگهبانی دائمی" in r["note"], "G6: رکورد بازنشسته شد")
check(due == [],
      "G6: رکوردِ بازنشسته دوباره سررسید نمی‌شود (چرخه‌ی بی‌پایان بسته شد)")

# ═══════ 10. رکوردی که مسیرِ دیگر زودتر لفتش داده → لفت/گزارش تکراری نه ═══════
# سناریوی واقعی: چکِ نگهبانی/یادآوری وسطِ تأیید عضویت است که لفتِ دستی
# (`تبادل خروج N`) یا مسیر دیگر زودتر رکورد را left می‌کند. اگر وضعیتِ
# تازه خوانده نشود، همان مسیر دوباره لفت می‌زند و «👋 لفت انجام شد» دوم
# می‌رود (باگِ قبلی).


class StealStub(Stub):
    # در فاصله‌ی بین تصمیم و لفت، رکورد را «left» می‌کند.
    def __init__(self, eng, members=(False, False)):
        super().__init__(members=members)
        self.eng = eng
        self.stolen = False

    async def confirm(self, pid, fast=False, rec_id=None, confirm=True):
        if rec_id and not self.stolen:
            self.stolen = True
            self.eng.db.ex_set(int(rec_id), status="left", next_reminder=0,
                               next_check=0, note="لفت دستی")
        return self.members.pop(0) if self.members else False


eng, x = mk_engine()
rec = mk_rec(eng, 8600, "@peerchan9", replied=1, strikes=1, reminders=2,
             reminders_total=2, next_reminder=int(time.time()) - 5)
st = StealStub(eng)
asyncio.run(run_rem(eng, x, st))
r = eng.db.ex_get(rec["id"])
print("R1", r["status"], "|", r["note"], "| leave calls:", len(st.calls),
      "| reports:", st.notes)
check(not st.calls, "R1: بعد از left شدنِ مسیرِ دیگر، لفتِ دوباره زده نشد")
check(not [n for n in st.notes if "لفت انجام شد" in n],
      "R1: گزارش «لفت انجام شد» تکراری نرفت")
check([e["kind"] for e in eng.db.recent(5)].count("ex_left") == 0,
      "R1: رویداد ex_left تکراری ثبت نشد")

eng, x = mk_engine()
rec = mk_rec(eng, 8601, "@peerchan10", strikes=1, replied=1)
st = StealStub(eng)
asyncio.run(run_guard(eng, x, st))
r = eng.db.ex_get(rec["id"])
print("R2", r["status"], "| leave calls:", len(st.calls))
check(not st.calls, "R2: همان محافظ در مسیر چکِ نگهبانی هم هست")

# ═══════ 11. یک کانال، دو رکورد (دو لینک) → فقط یک بار «لفت دادم» ═══════
eng, x = mk_engine()
first = mk_rec(eng, 8700, "@chan11", direction="out")
second = mk_rec(eng, 8701, "@chan11alt", direction="out")
same = -1001234567890
eng.db.ex_set(first["id"], chat_id=same, chat_hash=1234, status="left",
              note="نیومد → لفت دادم")
eng.db.ex_set(second["id"], chat_id=same, chat_hash=1234, strikes=1, replied=1)
st = Stub(members=[False, False])
asyncio.run(run_guard(eng, x, st))
r = eng.db.ex_get(second["id"])
print("R3", r["status"], "|", r["note"], "| leave calls:", len(st.calls),
      "| reports:", st.notes)
check(not st.calls, "R3: کانالی که با رکوردِ دیگری لفت شده دوباره لفت نخورد")
check(r["status"] == "left" and "قبلاً لفت شد" in r["note"],
      "R3: رکوردِ دوم بی‌صدا بسته شد")
check(not [n for n in st.notes if "لفت انجام شد" in n],
      "R3: پیام «لفت انجام شد» برای یک کانال دو بار نرفت")

# ═══════ 12. سلامتِ سیم‌کشی در سورس ═══════
check(src.count('_fresh.get("status") != "joined"') >= 2,
      "W1: هر دو مسیر خودکار وضعیت را دوباره از دیتابیس می‌خوانند")
check("ex_same_channel_left" in src and
      'eng.log("info", "ex_left"' in src and "ex_leave_fail" in src,
      "W2: محافظِ کانالِ تکراری + جدا شدن رویداد لفتِ ناموفق")
check(src.count("ex_leave_fail") >= 3,
      "W3: هر سه مسیر لفت رویدادِ درست را ثبت می‌کنند")
check("def ex_same_channel_left" in src and
      "status='left' ORDER BY id LIMIT 1" in src,
      "W4: کوئریِ کانالِ تکراری فقط رکوردهای لفت‌شده را می‌بیند")

print("DONE PASS" if not FAILS else "DONE FAIL %r" % (FAILS,))
"""


def reset():
    shutil.rmtree(ROOT, ignore_errors=True)
    os.makedirs(APP, exist_ok=True)
    os.makedirs(DATA, exist_ok=True)
    for f in ("95.py", "manager_82.py"):
        shutil.copy2(os.path.join(SRC_REPO, f), APP)


def run():
    env = dict(os.environ)
    env["DATA_DIR"] = DATA
    env["PORT"] = "8207"
    env["JAFJ_PORT"] = "8207"
    for k in ("RAILWAY_ENVIRONMENT", "RAILWAY_SERVICE_ID", "RAILWAY_PROJECT_ID",
              "JAFJ_HOSTED", "JAFJ_LOGIN_RETRY", "BOT_TOKEN", "API_ID",
              "API_HASH", "BACKUP_CHAT", "BACKUP_EVERY"):
        env.pop(k, None)
    p = subprocess.run([sys.executable, "-c", DRIVER], cwd=APP, env=env,
                       capture_output=True, text=True, timeout=180)
    return p.stdout, p.stderr, p.returncode


def main():
    print("--- join_leave_report: چکِ جوین، لفت و گزارشِ «لفت دادم» ---")
    reset()
    out, err, rc = run()
    if err.strip():
        print("--- driver stderr (tail) ---")
        print(err[-3000:])
    print("--- driver output ---")
    for line in out.splitlines():
        if line.startswith(("OK", "FAIL", "DONE", "G", "M", "T", "R", "W")):
            print(line)
    if "DONE PASS" in out and "FAIL" not in out and rc == 0:
        print("ALL: PASS")
        return True
    print("ALL: FAIL")
    return False


if __name__ == "__main__":
    sys.exit(0 if main() else 1)
