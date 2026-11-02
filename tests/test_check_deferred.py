#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""تفکیکِ «درخواست نرفت» از «نمی‌دانم» در بررسیِ عضویت.

باگی که این تست قفل می‌کند (شکایتِ کاربر: «چرا همش پیامِ بررسی عضویت
نامشخص می‌آید»): وقتی صفِ عملکردها با FloodWait بسته بود یا گیتِ چک سقف
داشت، `peer_in_my_channel` بدونِ اینکه **هیچ درخواستی** بفرستد `None`
برمی‌گرداند — یعنی دقیقاً همان مقدارِ «نتیجه نامشخص». نتیجه: شمارنده‌ی
`unk_streak` تا ۵ بالا می‌رفت و پیامِ هشدار هر ۱۰ دقیقه تکرار می‌شد،
در حالی که مشکل فقط «صبر کن» بود.

قواعد:
  D1  صفِ بسته (FloodWait) → CHECK_DEFERRED و صفر درخواست
  D2  گیتِ چک بسته → CHECK_DEFERRED و صفر درخواست
  D3  انتظارِ گیت > ۴۵ ثانیه → CHECK_DEFERRED و صفر درخواست
  D4  عضو است → True
  D5  عضو نیست → False
  D6  FloodWait از خودِ تلگرام → None (نامشخصِ واقعی)
  D7  خطای دیگرِ API → None
  D8  confirm_peer_membership مقدارِ DEFERRED را دست‌نخورده برمی‌گرداند
"""
import asyncio
import os
import sys
import time
from types import SimpleNamespace

HERE = os.path.dirname(os.path.abspath(__file__))
REPO = os.path.dirname(HERE)
SRC = os.path.join(REPO, "95.py")
text = open(SRC, encoding="utf-8").read()

ns_mod = {"__name__": "jafj_check_defer", "__file__": SRC,
          "__builtins__": __builtins__}
exec(compile(text, SRC, "exec"), ns_mod)
CHECK_DEFERRED = ns_mod["CHECK_DEFERRED"]

a = text.find("    async def peer_in_my_channel(")
b = text.find("    def remember_channel(", a)
assert a > 0 and b > a, "peer_in_my_channel پیدا نشد"
fn_src = "\n".join(ln[4:] if ln.startswith("    ") else ln
                   for ln in text[a:b].splitlines())


class FloodWaitError(Exception):
    def __init__(self, seconds=60):
        super().__init__("flood %s" % seconds)
        self.seconds = seconds


class UserNotParticipantError(Exception):
    pass


class GetParticipantRequest:
    def __init__(self, ch, uid):
        self.ch, self.uid = ch, uid


class FakeExCd:
    def __init__(self, blocked_until=0.0):
        self.blocked_until = blocked_until
        self.lock = asyncio.Lock()
        self.actions = 0
        self.last_global_done = 0.0
        self._last_done = {}
        self._last_kind = {}
        self._order = []

    def apply_config(self):
        pass

    def seconds(self):
        return 0.0

    def wait_for(self, rid):
        return 0.0

    async def action(self, kind, rec_id=None, fn=None, *args, **kw):
        self.actions += 1
        async with self.lock:
            if fn is None:
                return None
            return await fn(*args, **kw)

    def note_done(self, rec_id=None, now=None):
        return None


class FakeGate:
    def __init__(self, wait=0.0, blocked=False):
        self._w, self._blocked, self.records, self.penalties = wait, blocked, 0, 0

    def wait(self):
        return self._w

    def blocked(self):
        return self._blocked

    def record(self):
        self.records += 1

    def penalize(self, w):
        self.penalties += 1
        self._w = max(self._w, float(w))


NOTES = []


async def note(txt):
    NOTES.append(txt)


def make(client_fn, blocked_until=0.0, gate_wait=0.0, gate_blocked=False,
         channels=None):
    calls = {"n": 0, "chans": []}

    async def client(req):
        calls["n"] += 1
        calls["chans"].append(getattr(req, "ch", None))
        return await client_fn(req)

    chans = channels or {"standard": "@mychan", "vip": ""}
    # جعبه‌ی «علت» مخصوص همین نمونه؛ نسخه‌ی واقعی داخل 95.py به گلوبالِ
    # خودش می‌نویسد، پس این‌جا معادلش را به همان دیکشنریِ ns می‌بندیم.
    why_box = {"why": "", "at": 0}

    ns = {
        "eng": SimpleNamespace(
            st=SimpleNamespace(prof=lambda t: {"channel": chans.get(t, "")}),
            db=SimpleNamespace(log=lambda *a, **k: None),
            log=lambda *a, **k: None),
        "client": client,
        "ex_cd": FakeExCd(blocked_until),
        "check_gate": FakeGate(gate_wait, gate_blocked),
        "GetParticipantRequest": GetParticipantRequest,
        "FloodWaitError": FloodWaitError,
        "UserNotParticipantError": UserNotParticipantError,
        "CHECK_DEFERRED": CHECK_DEFERRED,
        "_note_check_why": (lambda w: why_box.__setitem__(
            "why", str(w or "")[:120])),
        "_LAST_CHECK_WHY": why_box,
        "asyncio": asyncio, "time": time,
        "note": note, "secs": ns_mod["secs"],
        "membership_check_delay": lambda: 2,
        "_warn_check_flood": {"last": 0},
    }
    exec(fn_src, ns)
    return ns, calls


FAILS = []


def check(name, ok, extra=""):
    if ok:
        print("PASS", name)
    else:
        FAILS.append(name)
        print("FAIL", name, "" if extra == "" else "→ %r" % (extra,))


async def member(req):
    return SimpleNamespace(participant=SimpleNamespace(user_id=1))


async def raiser(exc):
    raise exc


def run(verdict, **kw):
    ns, calls = make(verdict, **kw)
    out = asyncio.run(ns["peer_in_my_channel"](4242))
    return out, calls["n"], ns


# D1: صف با FloodWait بسته است → هیچ درخواستی نرود و DEFERRED برگردد
out, sent, ns = run(member, blocked_until=time.time() + 3600)
check("D1: صفِ بسته → CHECK_DEFERRED", out is CHECK_DEFERRED, out)
check("D1: هیچ درخواستی به تلگرام نرفت", sent == 0, sent)

# D2: گیتِ چک بسته
out, sent, ns = run(member, gate_blocked=True)
check("D2: گیتِ بسته → CHECK_DEFERRED", out is CHECK_DEFERRED, out)
check("D2: هیچ درخواستی نرفت", sent == 0, sent)

# D3: انتظارِ گیت بیشتر از ۴۵ ثانیه
out, sent, ns = run(member, gate_wait=120.0)
check("D3: انتظارِ بلندِ گیت → CHECK_DEFERRED", out is CHECK_DEFERRED, out)
check("D3: هیچ درخواستی نرفت", sent == 0, sent)

# D4/D5: نتیجه‌های واقعی
out, sent, ns = run(member)
check("D4: عضو است → True", out is True, out)
check("D4: دقیقاً یک درخواست رفت", sent == 1, sent)

out, sent, ns = run(lambda req: raiser(UserNotParticipantError()))
check("D5: عضو نیست → False", out is False, out)

# D6/D7: نامشخصِ واقعی (درخواست رفت و جواب نداد)
out, sent, ns = run(lambda req: raiser(FloodWaitError(60)))
check("D6: FloodWait تلگرام → None (نامشخصِ واقعی)", out is None, out)
check("D6: درخواست واقعاً رفت", sent == 1, sent)

out, sent, ns = run(lambda req: raiser(RuntimeError("boom")))
check("D7: خطای دیگرِ API → None", out is None, out)

# D8: confirm_peer_membership مقدارِ DEFERRED را عوض نمی‌کند
ns, calls = make(member, blocked_until=time.time() + 600)
confirmed = asyncio.run(ns["confirm_peer_membership"](4242, fast=True, rec_id=7))
check("D8: confirm هم CHECK_DEFERRED را برمی‌گرداند",
      confirmed is CHECK_DEFERRED, confirmed)
check("D8: چکِ دومِ بی‌فایده هم اجرا نشد", calls["n"] == 0, calls["n"])

# ── D10–D12: دو کانال (عادی + VIP) — جمع‌بندیِ درست ──
# باگِ واقعی: اگر کانالِ اول False می‌داد و کانالِ دوم خطا، نتیجه False
# می‌شد ⇒ «نیومدی» و لفتِ اشتباه، در حالی که طرف ممکن بود عضوِ VIP باشد.

async def _member_on(req):
    return SimpleNamespace(participant=SimpleNamespace(user_id=1))


async def _not_member_on(req):
    raise UserNotParticipantError()


async def _member_vip_only(req):
    # فقط عضوِ کانالِ VIP است ⇒ باید هر دو کانال بررسی شوند
    if req.ch == "@mychan":
        raise UserNotParticipantError()
    return SimpleNamespace(participant=SimpleNamespace(user_id=1))


BOTH = {"standard": "@mychan", "vip": "@mychan_vip"}


def run_chan(fn):
    ns, calls = make(fn, channels=BOTH)
    out = asyncio.run(ns["peer_in_my_channel"](4242))
    return out, calls


out, calls = run_chan(_member_vip_only)
check("D14: عضوِ VIP (نه عادی) → True", out is True, out)
check("D14: هر دو کانال بررسی شدند", calls["chans"] == ["@mychan", "@mychan_vip"],
      calls["chans"])

out, calls = run_chan(_member_on)
check("D10: عضوِ کانالِ اول → True (کوتاه‌می‌شود)", out is True, out)
check("D10: با True شدن کانالِ اول، کانالِ دوم بررسی نشد",
      calls["chans"] == ["@mychan"], calls["chans"])

async def _seq(req):
    # کانالِ اول «عضو نیست»، کانالِ دوم خطای API
    if req.ch == "@mychan":
        raise UserNotParticipantError()
    raise RuntimeError("boom")


out, calls = run_chan(_seq)
check("D11: False + نامشخص → None (نه False)", out is None, out)

async def _seq2(req):
    if req.ch == "@mychan":
        raise UserNotParticipantError()
    return SimpleNamespace(participant=SimpleNamespace(user_id=1))


out, calls = run_chan(_seq2)
check("D12: False + True → True", out is True, out)

async def _seq3(req):
    if req.ch == "@mychan":
        raise UserNotParticipantError()
    raise FloodWaitError(300)


out, calls = run_chan(_seq3)
check("D13: False + FloodWait → None (نه False)", out is None, out)

# ── D15–D17: علتِ واقعیِ «نامشخص» ثبت شود ──
# چرا: پیامِ «بررسی عضویت نامشخص می‌ماند (FloodWait یا محدودیت API)» حتی
# وقتی علت FloodWait نبود هم همین متن را می‌گفت. حالا علت ثبت و نمایش
# داده می‌شود، و حالتِ «درخواست نرفت» اصلاً علتِ خطا حساب نمی‌شود.

async def _flood(req):
    raise FloodWaitError(300)


out, sent, ns = run(_flood)
check("D15: FloodWait → None", out is None, out)
check("D15: علت ثبت شد و FloodWait است",
      "FloodWait" in (ns["_LAST_CHECK_WHY"]["why"] or ""),
      ns["_LAST_CHECK_WHY"])

out, sent, ns = run(member, blocked_until=time.time() + 3600)
check("D16: صفِ بسته → DEFERRED", out is CHECK_DEFERRED, out)
check("D16: علت با deferred: شروع می‌شود (نه خطای ساختگی)",
      (ns["_LAST_CHECK_WHY"]["why"] or "").startswith("deferred:"),
      ns["_LAST_CHECK_WHY"])

out, sent, ns = run(member)
check("D17: جوابِ قطعی → علت پاک می‌شود", ns["_LAST_CHECK_WHY"]["why"] == "",
      ns["_LAST_CHECK_WHY"])

# D9: حالتِ «نامشخص» نباید False حساب شود (لفتِ اشتباه)
check("D9: DEFERRED هرگز برابرِ False نیست", CHECK_DEFERRED is not False)

if FAILS:
    print("\nFAILED:", FAILS)
    sys.exit(1)
print("ALL PASS")
