#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""«۹۵.py اجرا می‌شود ولی پنل نمی‌آید» — سه ریشه‌ی واقعی، سه نگهبان.

گزارشِ کاربر: ربات مدیر می‌گوید سلف روشن شد، ولی در Saved Messages هیچ
پیامی نمی‌آید و نوشتنِ «پنل» هم جوابی ندارد. سه ریشه در سمتِ خودِ `95.py`
باقی مانده بود:

  A) **سشن به اکانتِ دیگری وصل شده** — سلف با موفقیت بالا می‌آید، اما همه‌ی
     پیام‌های پنل به Saved Messages همان اکانتِ دیگر می‌رود. تا امروز هیچ
     کدی این را نمی‌فهمید (پروسه سالم است!). حالا `account_guard()` با
     `.jafj_expected_account` (که مدیر می‌نویسد) مقایسه می‌کند و با کدِ
     مشخص متوقف می‌شود تا مدیر «اکانتِ اشتباه» را ببیند.

  B) **ارسالِ پیامِ شروع شکست می‌خورد** (`send_message("me", …)` خطا
     می‌دهد) ولی هیچ‌کس آن را نمی‌دید؛ حالا در لاگ و `jafj_boot.log` با
     کلیدِ «پیامِ شروع نرفت» ثبت می‌شود.

  C) **نوشتنِ نیمه‌کاره‌ی فایل‌ها** (تنظیمات/وضعیت/کردنشیال) بعد از کرش،
     فایلِ خراب می‌گذاشت و دفعه‌ی بعد خواندنش استثنا می‌داد. `write_json_atomic`
     این را می‌بندد.

تست با telethon جعلی و `run_bot()` واقعی اجرا می‌شود (بدونِ شبکه).
اجرا: `python3 tests/test_selfbot_account_guard.py` → `ALL PASS`
"""
import os
import shutil
import sqlite3
import subprocess
import sys
import tempfile
import textwrap

REPO = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
ROOT = os.path.join(tempfile.gettempdir(), "jafj_account_guard_run")

INNER = textwrap.dedent('''
    import asyncio, os, sys, types

    REPO = os.environ["REPO"]
    os.chdir(os.environ["DATA"])
    sys.path.insert(0, REPO)

    ME_ID = int(os.environ["ME_ID"])
    SEND_FAILS = os.environ.get("SEND_FAILS") == "1"
    SENT = []

    class FakeMsg:
        def __init__(self, mid, text=""):
            self.id = mid
            self.raw_text = text

    class FakeClient:
        def __init__(self, *a, **k):
            self._id = 500
            self.handlers = []
        def on(self, builder):
            def deco(fn):
                self.handlers.append((builder, fn))
                return fn
            return deco
        async def connect(self, *a, **k):
            return True
        async def is_user_authorized(self):
            return True
        def is_connected(self):
            return True
        async def get_me(self):
            return types.SimpleNamespace(
                first_name="Tester", username="tester", id=ME_ID,
                last_message_date=None, status=None)
        async def send_message(self, peer, text=None, **k):
            if SEND_FAILS:
                raise RuntimeError("blocked")
            self._id += 1
            m = FakeMsg(self._id, text or "")
            SENT.append(m)
            return m
        async def run_until_disconnected(self):
            # اجرای واقعی ساعت‌ها می‌ماند؛ تست خودش بعد از دیدنِ «آنلاین شد»
            # این task را لغو می‌کند.
            await asyncio.sleep(3600)
        async def disconnect(self, *a, **k):
            return True
        async def delete_messages(self, *a, **k):
            return True
        def __getattr__(self, name):
            async def _stub(*a, **k):
                return None
            return _stub

    class Builder:
        def __init__(self, *a, **k):
            pass

    telethon = types.ModuleType("telethon")
    telethon.TelegramClient = FakeClient
    telethon.__version__ = "1.99-fake"
    events = types.ModuleType("telethon.events")
    events.NewMessage = Builder
    telethon.events = events
    errors = types.ModuleType("telethon.errors")

    class _E(Exception):
        pass

    for _n in ("FloodWaitError", "SlowModeWaitError", "ChatWriteForbiddenError",
               "ChannelPrivateError", "UsernameNotOccupiedError", "RPCError",
               "UserNotParticipantError", "UserAlreadyParticipantError",
               "InviteHashExpiredError", "InviteHashInvalidError",
               "ChannelsTooMuchError", "InviteRequestSentError",
               "ChannelInvalidError", "UsernameInvalidError"):
        setattr(errors, _n, type(_n, (_E,), {}))
    telethon.errors = errors
    tl = types.ModuleType("telethon.tl")
    fn = types.ModuleType("telethon.tl.functions")
    ch = types.ModuleType("telethon.tl.functions.channels")
    ms = types.ModuleType("telethon.tl.functions.messages")
    for _m, _nms in ((ch, ("JoinChannelRequest", "LeaveChannelRequest",
                           "GetParticipantRequest")),
                     (ms, ("ImportChatInviteRequest",))):
        for _n in _nms:
            setattr(_m, _n, type(_n, (object,), {"__init__": lambda self, *a, **k: None}))
    sys.modules.update({"telethon": telethon, "telethon.events": events,
                        "telethon.errors": errors, "telethon.tl": tl,
                        "telethon.tl.functions": fn,
                        "telethon.tl.functions.channels": ch,
                        "telethon.tl.functions.messages": ms})

    import importlib.util
    spec = importlib.util.spec_from_file_location("sb95", os.path.join(REPO, "95.py"))
    SB = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(SB)

    BOOT = os.path.join(os.getcwd(), "jafj_boot.log")

    def boot_has_panel():
        try:
            return "آنلاین شد" in open(BOOT, encoding="utf-8").read()
        except Exception:
            return False

    async def driver():
        task = asyncio.ensure_future(SB.run_bot())
        for _ in range(900):
            if task.done() or boot_has_panel():
                break
            await asyncio.sleep(0.1)
        if not task.done():
            task.cancel()
        try:
            rc = await task
        except asyncio.CancelledError:
            rc = 0
        return rc

    rc = asyncio.run(driver())
    print("RC=%s" % rc)
    print("SENT=%d" % len(SENT))
''')


def run_case(name, me_id, expected=None, send_fails=False, extra_env=None):
    """یک اجرای کاملِ run_bot() با telethon جعلی → (rc, sent, log)."""
    data = os.path.join(ROOT, name)
    shutil.rmtree(data, ignore_errors=True)
    os.makedirs(data, exist_ok=True)
    # سشنِ واقعیِ sqlite (تا is_user_authorized رد نشود)
    con = sqlite3.connect(os.path.join(data, "jafj.session"))
    con.execute("CREATE TABLE IF NOT EXISTS sessions (dc_id integer primary key,"
                " server_address text, port integer, auth_key blob,"
                " takeout_id integer)")
    con.execute("INSERT INTO sessions VALUES (2,'149.154.167.51',443,?,NULL)",
                (b"A" * 256,))
    con.commit()
    con.close()
    with open(os.path.join(data, "jafj_creds.json"), "w", encoding="utf-8") as f:
        f.write('{"api_id": 123456, "api_hash": "0123456789abcdef",'
                ' "phone": "+989120000000"}')
    if expected is not None:
        with open(os.path.join(data, ".jafj_expected_account"), "w",
                  encoding="utf-8") as f:
            f.write(str(expected))
    env = dict(os.environ)
    env.update({"REPO": REPO, "DATA": data, "ME_ID": str(me_id),
                "SEND_FAILS": "1" if send_fails else "0",
                "JAFJ_NO_AUTO_LOGIN": "1", "PYTHONPATH": REPO,
                "JAFJ_SELFBOT_REF": os.path.join(REPO, "95.py")})
    env.pop("JAFJ_EXPECTED_ACCOUNT", None)
    env.pop("JAFJ_TG_ID", None)
    if extra_env:
        env.update(extra_env)
    script = os.path.join(data, "_inner.py")
    with open(script, "w", encoding="utf-8") as f:
        f.write(INNER)
    p = subprocess.run([sys.executable, script], capture_output=True, text=True,
                       timeout=180, env=env, cwd=data)
    out = (p.stdout or "") + (p.stderr or "")
    rc = None
    sent = None
    for ln in out.splitlines():
        if ln.startswith("RC="):
            try:
                rc = int(ln[3:].strip())
            except Exception:
                rc = ln[3:].strip()
        elif ln.startswith("SENT="):
            try:
                sent = int(ln[5:].strip())
            except Exception:
                sent = None
    try:
        boot = open(os.path.join(data, "jafj_boot.log"), encoding="utf-8").read()
    except Exception:
        boot = ""
    return rc, sent, out + "\n" + boot


FAILS = []


def check(name, cond, extra=""):
    print(("PASS " if cond else "FAIL ") + name
          + (f"   [{str(extra)[:400]}]" if not cond else ""))
    if not cond:
        FAILS.append(name)


def main():
    shutil.rmtree(ROOT, ignore_errors=True)
    os.makedirs(ROOT, exist_ok=True)

    # ── A) اکانتِ درست → پنل می‌رود ─────────────────────────────────────
    rc, sent, log = run_case("correct", me_id=777, expected=777)
    check("اکانتِ درست: سلف پنل را می‌فرستد", rc == 0 and (sent or 0) > 0,
          f"rc={rc} sent={sent}")
    check("اکانتِ درست: boot بین «آنلاین شد»", "آنلاین شد — پنل فعال" in log, log[-500:])

    # ── B) اکانتِ اشتباه → باید صریح متوقف شود، نه «سالم» ───────────────
    rc, sent, log = run_case("wrong_account", me_id=888, expected=777)
    check("اکانتِ اشتباه: اجرا متوقف می‌شود (کد ۷۸)", rc == 78, f"rc={rc}")
    check("اکانتِ اشتباه: پنل عمداً فرستاده نمی‌شود", (sent or 0) == 0, f"sent={sent}")
    check("اکانتِ اشتباه: پیامِ فارسیِ روشن در لاگ",
          "این پوشه برای اکانتِ" in log and "777" in log, log[-600:])
    check("اکانتِ اشتباه: boot «بوت متوقف شد» را ثبت می‌کند",
          "بوت متوقف شد" in log and "اکانتِ دیگری" in log, log[-400:])

    # ── C) نگهبان با JAFJ_ACCOUNT_GUARD=0 خاموش می‌شود ──────────────────
    rc, sent, log = run_case("guard_off", me_id=888, expected=777,
                             extra_env={"JAFJ_ACCOUNT_GUARD": "0"})
    check("خاموش‌کردنِ نگهبان کار می‌کند (اجرا ادامه می‌یابد)",
          rc == 0 and (sent or 0) > 0, f"rc={rc} sent={sent}")

    # ── D) ارسال شکست می‌خورد → باید در لاگ گفت‌وگو شود، نه سکوت ────────
    rc, sent, log = run_case("send_fail", me_id=777, expected=777,
                             send_fails=True)
    check("ارسالِ ناموفق: «پیامِ شروع نرفت» در boot ثبت می‌شود",
          "پیامِ شروع نرفت" in log, log[-500:])
    check("ارسالِ ناموفق: sلف را نمی‌کشد (کد ۰)", rc == 0, f"rc={rc}")

    print()
    if FAILS:
        print("FAILED:", ", ".join(FAILS))
        return 1
    print("ALL PASS")
    return 0


if __name__ == "__main__":
    sys.exit(main())
