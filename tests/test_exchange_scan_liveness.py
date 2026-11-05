#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""زنده‌ماندنِ اسکن تبادل و نظمِ «عملکرد»ها.

ریشه‌ی گزارش مشتری: «اسکن تبادل می‌میره، چندتا عملکرد خوب کار نمی‌کنن».
چهار حلقه‌ی اتصال که هر کدام جدا خاموش/گیر می‌شد:

  ۱) دروازه‌ی ضد-انباشت با «تعداد کل approved» کار می‌کرد. هر رکوردی که
     به هر دلیلی در صف میخکوب می‌شد (خطای موقت، سقف ۵۰۰ کانال، سیلِ
     FloodWait) سقف را پر نگه می‌داشت و اسکنِ خودکار **تا ابد** رد می‌شد.
  ۲) صفِ Join «تازه‌ترین اول» (ORDER BY id DESC) بود؛ تازه‌واردها نوبتِ
     بقیه را می‌زدند، انتهای صف پیر می‌شد و فقط سرِ صفِ تازه «قدیمی»
     شمرده می‌شد → صف تخلیه نمی‌شد و همان دروازه هم بسته می‌ماند.
  ۳) رکوردِ «در جریان» (busy) هیچ‌وقت ثبت نمی‌شد؛ `_busy` همیشه خالی بود،
     پس `wait_for`/`defer_if_due` وسطِ یک جوین/چکِ در جریان «آزاد» می‌گفت
     و دو مسیر روی یک رکورد قاطی می‌شدند.
  ۴) اگر `iter_messages` روی شبکه معلق می‌ماند، حلقه‌ی اسکن بی‌صدا
     می‌خوابید؛ نگهبانِ حلقه‌ها فقط «مرگ» (استثنا) را می‌دید، نه «گیر
     کردن»، و در وضعیتِ running تا ری‌استارتِ دستی می‌ماند.

سنجه‌ها رفتاری‌اند (DB و کلاسِ واقعیِ `95.py` اجرا می‌شوند) + چند قفل
متنی برای بخش‌هایی که داخل `run()`‌اند و جدا قابل‌اجرا نیستند.
"""
import asyncio
import importlib.util
import os
import sys
import tempfile
import time
from pathlib import Path
from types import SimpleNamespace

ROOT = Path(__file__).resolve().parents[1]
os.environ.setdefault("DATA_DIR", tempfile.mkdtemp(prefix="jafj-scan-live-"))
spec = importlib.util.spec_from_file_location("m95_scan_live", ROOT / "95.py")
m = importlib.util.module_from_spec(spec)
spec.loader.exec_module(m)

SRC = (ROOT / "95.py").read_text(encoding="utf-8")
FAILS = []


def check(label, cond, extra=""):
    print(("OK   " if cond else "FAIL ") + label + ((" → " + str(extra)) if not cond and extra else ""))
    if not cond:
        FAILS.append(label)


# ── ۱) دروازه: فقط رکوردِ «تازه و پیش‌قدمِ خودی» اسکن را نگه می‌دارد ──
now = 1000.0
recs = [
    {"status": "approved", "direction": "out", "created_at": 900},   # تازه  → می‌شمارد
    {"status": "approved", "direction": "out", "created_at": 100},  # کهنه  → نمی‌شمارد
    {"status": "approved", "direction": "in", "created_at": 990},   # درخواستِ طرف → نمی‌شمارد
    {"status": "joined", "direction": "out", "created_at": 999},    # خارج از صف → نمی‌شمارد
    {"status": "approved", "direction": "out"},                     # بدون زمان → نمی‌شمارد
    None,                                                            # سطرِ خراب → خطا نمی‌دهد
]
check("scan_backlog_count فقط approved+out+تازه را می‌شمارد",
      m.scan_backlog_count(recs, now, 300) == 1,
      m.scan_backlog_count(recs, now, 300))
check("رکوردهای کهنه جلوی اسکن را نمی‌گیرند (قفلِ ابدی = «اسکن می‌میرد»)",
      m.scan_backlog_count([{"status": "approved", "direction": "out",
                             "created_at": 0}] * 9, now, 300) == 0)
check("ورودیِ خالی/خراب خطا نمی‌دهد",
      m.scan_backlog_count([], now, 300) == 0
      and m.scan_backlog_count(None, None, None) == 0)
check("با همان ورودی، دروازه دیگر «backlog» نمی‌گوید",
      m.scan_gate_reason(0, m.scan_backlog_count(recs[1:3], now, 300), now) == "")
sg = SRC[SRC.index("async def scan_groups(manual=False):"):
         SRC.index("    # ---------- اسکن مستقل پیش", SRC.index("async def scan_groups(manual=False):"))]
check("خودِ اسکن هم از همین شمارش استفاده می‌کند",
      "scan_backlog_count(eng.db.ex_list(\"approved\", 100)" in sg, "scan_groups")

# ── ۲) DB: صفِ Join (FIFO + ردکردنِ ناآماده) و عقب‌نشینیِ تلاش ──
db = m.DB(os.path.join(os.environ["DATA_DIR"], "live.db"))
base = int(time.time())
ids = []
for i in range(3):
    rec, _ = db.ex_add(500 + i, "@p%d" % i, "@q%d" % i)
    db.ex_set(rec["id"], status="approved", direction="out",
              created_at=base - (300 - 60 * i))
    ids.append(rec["id"])
links = [r["link"] for r in db.ex_join_queue(int(time.time()), 5)]
check("صفِ Join قدیمی‌ترین را اول می‌دهد (FIFO)",
      links == ["@q0", "@q1", "@q2"], links)
# رکوردِ وسط را «۱۰ دقیقه بعد» زمان‌بندی کن → صف باید از کنارش رد شود
db.ex_set(ids[1], next_join_try=int(time.time()) + 600)
links = [r["link"] for r in db.ex_join_queue(int(time.time()), 5)]
check("رکوردِ ناآماده صف را قفل نمی‌کند", links == ["@q0", "@q2"], links)

db.ex_set(ids[2], status="pending")
check("خارج از approved، نوبتِ جوین ندارد",
      [r["link"] for r in db.ex_join_queue(int(time.time()), 5)] == ["@q0"])

# عقب‌نشینیِ پلکانی + سقف تلاش
db.ex_set(ids[0], join_attempts=0, next_join_try=0)
gave = db.ex_join_retry(ids[0], backoff_sec=60, max_attempts=4, step=5)
b1 = int(db.ex_get(ids[0])["next_join_try"]) - int(time.time())
gave2 = db.ex_join_retry(ids[0], backoff_sec=60, max_attempts=4, step=5)
b2 = int(db.ex_get(ids[0])["next_join_try"]) - int(time.time())
check("تلاشِ ناموفق، رکورد را از سرِ صف برمی‌دارد (۶۰ث→۵د)",
      not gave and not gave2 and 55 <= b1 <= 61 and 295 <= b2 <= 301, (b1, b2))
db.ex_join_retry(ids[0], backoff_sec=60, max_attempts=4, step=5)
db.ex_join_retry(ids[0], backoff_sec=60, max_attempts=4, step=5)
row = db.ex_get(ids[0])
check("بعد از سقفِ تلاش، رکورد بسته می‌شود (بی‌نهایت تکرار نمی‌شود)",
      gave2 is False and row["status"] == "failed" and row["next_join_try"] == 0,
      (row["status"], row["next_join_try"]))
db.ex_set(ids[0], status="approved", join_attempts=0, next_join_try=0)
for _ in range(6):
    out = db.ex_join_retry(ids[0], max_attempts=0, backoff_sec=300)
check("max_attempts=0 یعنی بی‌سقف (سقف ۵۰۰ کانال نباید بسته شود)",
      out is False and db.ex_get(ids[0])["status"] == "approved")

# ── ۳) ExCooldown: رکوردِ «در جریان» باید بقیه را نگه دارد ──
class Cfg(dict):
    def get(self, k, d=None):
        return dict.get(self, k, d)


async def busy_case():
    cfg = Cfg({"op_gap_min_sec": 15, "op_gap_max_sec": 20})
    cd = m.ExCooldown(cfg=cfg.get, gap_min=15, gap_max=20)
    cd.apply_config = lambda: None          # تنظیمِ ثابت، بدونِ cfg
    gate = asyncio.Event()
    done = []

    async def slow():
        done.append("start")
        await gate.wait()
        return "ok"

    t1 = asyncio.create_task(cd.action("join", 42, slow))
    await asyncio.sleep(0.05)
    check("حینِ اجرای یک عملکرد، رکورد «در جریان» علامت می‌خورد",
          42 in cd._busy and cd.wait_for(42) > 0)
    ok_turn, defer_ts = cd.defer_if_due({"id": 42}, int(time.time()))
    check("`defer_if_due` وسطِ عملکرد می‌گوید «الان نه»",
          ok_turn is False and defer_ts > int(time.time()))
    check("خودِ همان تسک با busyِ خودش صبرِ کاذب نمی‌سازد",
          cd.wait_for(42, ignore_busy=True) == 0.0)
    gate.set()
    out = await t1
    check("عملکرد اجرا و نتیجه برگشت", out == "ok")
    check("بعد از پایان، علامتِ «در جریان» پاک می‌شود", 42 not in cd._busy)

    # خطا و لغو هم باید علامت را بردارند (وگرنه رکورد تا ابد قفل می‌ماند)
    async def boom():
        raise RuntimeError("boom")

    try:
        await cd.action("check", 43, boom)
    except RuntimeError:
        pass
    check("خطای عملکرد، رکورد را برای همیشه قفل نمی‌کند", 43 not in cd._busy)

    async def hang():
        await asyncio.sleep(30)

    t = asyncio.create_task(cd.action("leave", 44, hang))
    await asyncio.sleep(0.05)
    t.cancel()
    try:
        await t
    except asyncio.CancelledError:
        pass
    check("لغوِ عملکرد (wait_for timeout) هم رکورد را آزاد می‌کند",
          44 not in cd._busy)


asyncio.run(busy_case())

# ── ۴) قفل‌های متنی: مهلتِ اسکن، پایشِ گیرکردن، چکِ دوم ──
check("یک دورِ اسکن مهلت دارد (درخواستِ گیرکرده حلقه را نمی‌کشد)",
      "asyncio.wait_for(\n                            scan_groups(manual),"
      in SRC or "scan_groups(manual),\n" in SRC and "SCAN_ROUND_TIMEOUT_SEC" in SRC)
check("سقفِ زمانِ اسکن از پیش تعریف شده", "SCAN_ROUND_TIMEOUT_SEC = 180" in SRC)
sl = SRC[SRC.index("async def scan_loop()"):
         SRC.index("    # ---------- کارگر بررسی عضویت")]
check("حلقه‌ی اسکن beat می‌زند تا «گیر کردن» دیده شود", "_loop_beat(\"scan\")" in sl)
check("دروازه‌ی بسته بعد از ۱۵ دقیقه به صاحب‌حساب گفته می‌شود",
      "_report_gate(" in sl and "gate_since" in sl)
check("نگهبان، گیرکردن را از مرگ جدا می‌کند و دوباره راه می‌اندازد",
      "stall_after" in SRC and "loop_stall" in SRC
      and "SCAN_STALL_AFTER_SEC)" in SRC)
class ChannelParticipantLeft:          # نامِ کلاس در کدِ واقعی مهم است
    left = False


class _FakeCd:
    blocked_until = 0.0

    def __init__(self):
        self.lock = asyncio.Lock()
        self.noted = []

    async def action(self, kind, rec_id, fn):
        return await fn()

    def note_done(self, rid):
        self.noted.append(rid)


class _FakeGate:
    def blocked(self):
        return False

    def wait(self, now=None):
        return 0.0

    def record(self, now=None):
        pass

    def penalize(self, sec):
        pass


class _FakeClient:
    def __init__(self, answers):
        self.answers = answers
        self.calls = []

    async def __call__(self, req):
        self.calls.append(req.peer)
        a = self.answers.get(req.peer, "left")
        if a == "left":
            return SimpleNamespace(participant=ChannelParticipantLeft())
        if a == "unknown":
            return SimpleNamespace(participant=None)
        return SimpleNamespace(participant=SimpleNamespace(left=False))


class _HangingClient:
    """سوکتِ نیمه‌باز: درخواست «هیچ‌وقت» برنمی‌گردد."""
    calls = []

    async def __call__(self, req):
        await asyncio.sleep(30)


async def _async_note(*a, **k):
    return True


def _peer_check_source(buggy=False):
    i = SRC.index("    async def peer_in_my_channel(")
    j = SRC.index("    async def confirm_peer_membership(")
    body = SRC[i:j]
    if buggy:
        # بازتولیدِ باگِ قبلی: چکِ دوم بعد از «همین یک کانال» برمی‌گشت
        anchor = "ex_cd.note_done(rec_id)\n"
        k = body.index(anchor) + len(anchor)
        body = body[:k] + " " * 20 + "return out\n" + body[k:]
    import textwrap
    return textwrap.dedent(body)


def _run_peer_check(queue, answers, buggy=False, hang=False, timeout=45):
    """`peer_in_my_channel` واقعی را با دو کانال (عادی + VIP) اجرا می‌کند."""
    ns = {
        "time": time, "asyncio": asyncio,
        "eng": SimpleNamespace(
            st=SimpleNamespace(prof=lambda t: {
                "standard": {"channel": "@my_chan"},
                "vip": {"channel": "@my_vip"}}[t]),
            db=SimpleNamespace(log=lambda *a: None),
            log=lambda *a: None),
        "ex_cd": _FakeCd(), "check_gate": _FakeGate(),
        "client": _HangingClient() if hang else _FakeClient(answers),
        "CHECK_CALL_TIMEOUT_SEC": timeout,
        "GetParticipantRequest": (
            lambda peer, uid: SimpleNamespace(peer=peer, user_id=uid)),
        "FloodWaitError": type("FloodWaitError", (Exception,), {}),
        "UserNotParticipantError": type(
            "UserNotParticipantError", (Exception,),
            {"__init__": lambda self, request=None: Exception.__init__(self)}),
        "CHECK_DEFERRED": object(), "_note_check_why": lambda *a: None,
        "_warn_check_flood": {"last": 0}, "secs": lambda s: "%ss" % s,
        "membership_check_delay": lambda: 0, "note": _async_note,
        # هویتِ طرف (رفعِ «Could not find the input entity»): بدنه‌ی برش‌خورده
        # این نام‌ها را می‌خواند. کلاینتِ جعلیِ این تست __call__ دارد و نه
        # get_input_entity، پس resolver همان آیدیِ خامِ قبلی را می‌دهد.
        "partner_input_peer": m.partner_input_peer,
        "peer_identity": m.peer_identity,
        "remember_peer": m.remember_peer,
        "scan_dialogs_for_peer": m.scan_dialogs_for_peer,
        "CHECK_NO_PEER": m.CHECK_NO_PEER,
    }
    exec(_peer_check_source(buggy), ns)

    async def go():
        return await ns["peer_in_my_channel"](7, rec_id=1, queue=queue)

    return asyncio.run(go()), ns["client"].calls


VIP_ONLY = {"@my_chan": "unknown", "@my_vip": "member"}
ok_q, calls_q = _run_peer_check(True, VIP_ONLY)
ok_nq, calls_nq = _run_peer_check(False, VIP_ONLY)
check("چکِ عادی: عضویت در VIP کافی است (هر دو کانال دیده می‌شوند)",
      ok_q is True and len(calls_q) == 2, (ok_q, calls_q))
check("چکِ دومِ تأییدی هم همه‌ی کانال‌ها را می‌بیند "
      "(قبلاً «نامشخص» روی کانال اول یعنی VIP هرگز تأیید نمی‌شد)",
      ok_nq is True and len(calls_nq) == 2, (ok_nq, calls_nq))
bad_q, bad_calls = _run_peer_check(False, VIP_ONLY, buggy=True)
check("تست همان باگ را می‌گیرد (نسخهٔ «return out» → None با یک کانال)",
      bad_q is None and len(bad_calls) == 1, (bad_q, bad_calls))
check("عضو نبودن در هر دو کانال، همان «False» می‌دهد",
      _run_peer_check(True, {"@my_chan": "left", "@my_vip": "left"})[0] is False)
check("«نمی‌دانم» در یکی از کانال‌ها، جوابِ قطعی نمی‌سازد",
      _run_peer_check(True, {"@my_chan": "left", "@my_vip": "unknown"})[0] is None)
check("رفتِ رکورد از صف با پیامِ تازه، شمارنده‌ی تلاش را هم صفر می‌کند",
      'note="پیام جدید — دوباره در صف Join"' in SRC and "join_attempts=0, next_join_try=0" in SRC)

# ── ۵) نگهبانِ حلقه‌ها: «گیر کردن» را هم می‌بیند، خاموشی را نه ──
def _supervise_ns():
    """`_loop_mark` + `_supervise` واقعی را بیرون می‌کشد (بدون حلقه‌های run)."""
    import textwrap
    a = SRC.index("    def _loop_mark(name, state, err=\"\"):")
    b = SRC.index("    async def _loop_restart_note(")
    c = SRC.index("    def _supervise(name, factory")
    d = SRC.index("    task = _supervise(\"sender\", sender_loop)")
    body = textwrap.dedent(SRC[a:b] + SRC[c:d])
    ns = {"time": time, "asyncio": asyncio}
    notes = []
    logs = []

    class Eng:
        loop_state = {}

        def log(self, lvl, kind, detail=""):
            logs.append((kind, detail))

        def write_status(self, *a, **k):
            pass

    ns["eng"] = Eng()

    async def _note(*a, **k):
        notes.append(a)

    ns["_loop_restart_note"] = _note
    ns["_loop_stall_note"] = _note
    exec(body, ns)
    return ns, notes, logs


async def _supervise_cases():
    ns, notes, logs = _supervise_ns()
    entries = []
    hang = asyncio.Event()

    async def hangs_once():
        entries.append(len(entries) + 1)
        if len(entries) == 1:
            await hang.wait()          # هرگز آزاد نمی‌شود → «گیر کرده»

    t = ns["_supervise"]("scan", hangs_once, first_delay=0.05, max_delay=0.1,
                         stall_after=0.2, stall_poll_sec=0.05)
    await asyncio.sleep(1.2)
    rec = ns["eng"].loop_state.get("scan") or {}
    check("حلقه‌ی گیرکرده شناسایی و از نو راه‌اندازی می‌شود",
          len(entries) >= 2 and int(rec.get("restarts") or 0) >= 1,
          (entries, rec))
    check("علتِ «گیر کردن» لاگ و پیام می‌شود (دیگر بی‌صدا نیست)",
          any(k == "loop_stall" for k, _ in logs) and bool(notes),
          (logs[:3], notes[:2]))
    t.cancel()
    try:
        await t
        alive = True
    except asyncio.CancelledError:
        alive = False
    check("خاموشیِ عادی بلعیده نمی‌شود (ری‌استارتِ کامل)", alive is False)

    # خطا باید مثل قبل «crashed» شمرده شود، نه «stalled»
    async def boom():
        raise RuntimeError("dead loop")

    t2 = ns["_supervise"]("ex", boom, first_delay=0.05, max_delay=0.1)
    await asyncio.sleep(0.2)
    t2.cancel()
    try:
        await t2
    except asyncio.CancelledError:
        pass
    rec2 = ns["eng"].loop_state.get("ex") or {}
    check("مرگِ حلقه هنوز «crashed» است (نه «stalled») و شمارنده بالا می‌رود",
          rec2.get("state") in ("crashed", "cancelled")
          and int(rec2.get("restarts") or 0) >= 1
          and "dead loop" in str(rec2.get("last_error", "")), rec2)


asyncio.run(_supervise_cases())

# ════════════════════════════════════════════════════════════
# ۸) سقفِ زمانِ خودِ عملکرد — قفلِ سراسری آزاد می‌ماند
# ════════════════════════════════════════════════════════════
print("── ۸. مهلتِ عملکرد (سوکتِ گیرکرده کل تبادل را نخواباند) ──")
_a = SRC.index("                try:\n                    if fn is None:")
_b = SRC.index("    def note_done(self, rec_id=None, now=None):", _a)
_act = SRC[_a:_b]
check("بدنه‌ی action داخل wait_for است",
      "asyncio.wait_for(fn(*a, **kw), timeout=_to)" in _act)
check("مهلتِ تمام‌شده به TimeoutErrorِ روشن تبدیل می‌شود",
      "except asyncio.TimeoutError" in _act and "raise TimeoutError" in _act)
_ops = SRC[SRC.index("OP_TIMEOUT_SEC = {"):SRC.index("class ExCooldown:")]
for _k in ("check", "leave", "join", "reminder", "say"):
    check(f"مهلتِ «{_k}» تعریف شده است", f'"{_k}"' in _ops)
check("ثابت‌های مهلت پیش از کلاس می‌آیند",
      SRC.index("OP_TIMEOUT_SEC = {") < SRC.index("class ExCooldown:"))
_cds = SRC[SRC.index("class ExCooldown:"):SRC.index("class Throttle:")]
check("op_timeout روی همان کلاسِ صف است", "def op_timeout(self, kind)" in _cds)



async def _op_timeout_case():
    cd = m.ExCooldown(gap_min=0, gap_max=0)
    cd.op_timeout = lambda kind: 0.2          # مهلتِ آزمایشی
    hung = asyncio.Event()

    async def slow_fn():
        hung.set()
        await asyncio.sleep(30)               # دقیقاً همان «هیچ‌وقت برنمی‌گردد»

    async def runner():
        try:
            await cd.action("check", 9, slow_fn)
        except asyncio.CancelledError:
            raise
        except TimeoutError as e:
            return f"timeout:{type(e).__name__}"
        return "no-timeout"

    async def next_op():
        await asyncio.sleep(0.05)             # بگذار first واقعاً قفل را بگیرد
        return await cd.action("check", 7, lambda: "ran")

    r = await asyncio.wait_for(asyncio.gather(runner(), next_op()), timeout=5)
    return r, hung.is_set(), (9 in cd._busy), cd._lock.locked()


_r, _fired, _still_busy, _lock_held = asyncio.run(_op_timeout_case())
check("عملکردِ گیرکرده با TimeoutError بسته شد", _r[0] == "timeout:TimeoutError", _r[0])
check("مهلت بعد از شروعِ تابع کار می‌کند (نه قبل از صف)", _fired)
check("بعد از مهلت، رکورد دیگر «در حال عملیات» نیست", not _still_busy)
check("قفلِ سراسری آزاد می‌ماند", not _lock_held)
check("عملکردِ بعدی پشتِ گیرکردگی اجرا شد", _r[1] == "ran", _r[1])
check("مهلتِ join زیرِ wait_for(۱۸۰) حلقه است",
      m.OP_TIMEOUT_SEC["join"] < m.OP_TIMEOUT_SEC["leave"])

# ════════════════════════════════════════════════════════════
# ۹) «نیومدی» تعویق‌شده ≠ «نیومدی» نرفته
# ════════════════════════════════════════════════════════════
print("── ۹. تعویقِ یادآوری اخطار نمی‌سوزاند ──")
_fn = SRC.index("    async def send_not_joined_reminder(rec):")
_g = SRC[SRC.index("        wait_op = ex_cd.wait_for(rec.get(\"id\"))", _fn):
         SRC.index("# لینک طرف هرگز داخل متن ارسالی", _fn)]
check("مسیرِ تعویق None برمی‌گرداند (نه False)",
      "return None" in _g and "return False" not in _g)
check("نوبتِ تازه هنگام تعویق ثبت می‌شود",
      'note="در صف عملکرد — «نیومدی» کمی دیگر می‌رود"' in _g)
_ml = SRC[SRC.index("    async def membership_loop():"):
          SRC.index("    async def exchange_worker()")]
_rem_loop = _ml[_ml.index("for rec in eng.db.ex_reminder_due"):]
_rem_loop = _rem_loop[:_rem_loop.index("for rec in eng.db.ex_due(")]
check("حلقه‌ی یادآوری تعویق را از شکست جدا می‌کند", "sent is None" in _rem_loop)
check("شمارنده‌ی «سه بار نشد → لفت» فقط با شکستِ واقعی جلو می‌رود",
      _rem_loop.index("if sent is None") < _rem_loop.index("fails = int(rec.get(\"strikes\")"))

# ════════════════════════════════════════════════════════════
# ۱۰) درخواستِ گیرکردهٔ چک، حلقه را نمی‌کُشد
# ════════════════════════════════════════════════════════════
print("── ۱۰. مهلتِ خودِ درخواستِ چک و نوتیف ──")
_body = SRC[SRC.index("            async def _one_req():"):
            SRC.index("            try:\n                # گیتِ چک خودش بسته است؟")]
check("درخواستِ GetParticipant مهلت دارد",
      "asyncio.wait_for(\n                        client(GetParticipantRequest" in _body
      and "timeout=CHECK_CALL_TIMEOUT_SEC)" in _body)
check("مهلتِ چک از بیرونِ صف هم کار می‌کند",
      "except asyncio.TimeoutError" in _body and "_note_check_why" in _body)
check("resolveِ لینکِ خصوصیِ کانالِ من هم مهلت دارد",
      "asyncio.wait_for(\n                            client(CheckChatInviteRequest" in _body)
check("مهلتِ نوتیفِ Saved Messages",
      "timeout=NOTE_TIMEOUT_SEC)" in SRC[SRC.index("    async def note(text):"):
                                       SRC.index("    def _startup_text():")])
_t0 = time.time()
_hang, _ = _run_peer_check(True, {}, hang=True, timeout=0.2)
_dt = time.time() - _t0
check("چکِ گیرکرده «نامشخص» می‌شود، نه بلوکه", _hang is None, _hang)
check("و در چند صدم ثانیه برمی‌گردد (تا ابد صبر نمی‌کند)", _dt < 5, round(_dt, 2))

# ════════════════════════════════════════════════════════════
# ۱۱) نشانهٔ «اسکن دستی» در تنظیمات گیر نمی‌کند
# ════════════════════════════════════════════════════════════
print("── ۱۱. اسکنِ دستی معلق نمی‌ماند ──")
_pre = sl[sl.index("        while True:") + 12:
          sl.index("# ۰) اسکن گروه‌ها (حالت پیش‌قدم)")]
check("نشانه پیش از گیت‌ها دیده می‌شود",
      'if x.get("_scan_now") and (not x["enabled"] or not eng.ex_channel_ready()):' in _pre)
check("نشانه پاک می‌شود (اسکنِ شبح‌وارِ بعدی ندارد)", 'x.pop("_scan_now", None)' in _pre)
check("به جای سکوت، جواب داده می‌شود", "اسکنی در کار نیست" in _pre)

print("DONE PASS" if not FAILS else "FAILED: %d" % len(FAILS))
for f in FAILS:
    print("  -", f)
sys.exit(1 if FAILS else 0)
