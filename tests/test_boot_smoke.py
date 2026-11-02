#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""دود‌تستِ بوتِ واقعی: آیا 95.py اصلاً بالا می‌آید و تا کجا می‌رسد؟

چرا لازم است
────────────
تست‌های دیگر قطعه‌قطعه‌اند و کلِ مسیرِ `main() → run_bot() → connect_and_run()`
را اجرا نمی‌کنند؛ پس یک خطای ساده در همان مسیر (ایمپورتِ جاافتاده، نامِ
اشتباه، شرطِ بوت) با هیچ تستی گرفته نمی‌شد و کاربر فقط «بالا نمی‌آید»
می‌دید. این تست خودِ فایل را در یک پوشه‌ی موقت با یک telethonِ بدلی اجرا
می‌کند (بدونِ شبکه) و می‌خواهد:

  A) با telethonِ بدلی: تا «شروعِ اتصال به تلگرام» برسد، سشنِ نامعتبر را
     تشخیص دهد، با کدِ 78 (نیاز به لاگین) خارج شود و ردیِ بوت کامل باشد.
  B) بدونِ telethon: به‌جای مرگِ خاموش، کدِ 70 بدهد و
     `jafj_boot_error.txt` را با ModuleNotFoundError بنویسد.

اجرا: python3 tests/test_boot_smoke.py
"""
import importlib.util
import os
import shutil
import subprocess
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
        print("FAIL", name, "" if extra == "" else "→ %r" % (str(extra)[:400],))


STUB = {
    "telethon/__init__.py": '''
class TelegramClient:
    def __init__(self, session, api_id, api_hash, flood_sleep_threshold=0, **kw):
        self.session, self.api_id, self.api_hash = session, api_id, api_hash
    async def connect(self):
        return True
    async def disconnect(self):
        return True
    async def is_user_authorized(self):
        return False            # سشنِ تازه → باید کدِ 78 بدهد
    def is_connected(self):
        return True


class _Events:
    class NewMessage:
        def __init__(self, *a, **k):
            pass


events = _Events()
__version__ = "stub"
''',
    "telethon/errors.py": '''
class _E(Exception):
    seconds = 30
    def __init__(self, *a, **k):
        super().__init__("stub")
FloodWaitError = SlowModeWaitError = RPCError = _E
class FloodError(_E): pass
class ChannelPrivateError(_E): pass
class ChannelInvalidError(_E): pass
class UsernameInvalidError(_E): pass
class UsernameNotOccupiedError(_E): pass
class InviteHashExpiredError(_E): pass
class InviteHashInvalidError(_E): pass
class InviteRequestSentError(_E): pass
class UserAlreadyParticipantError(_E): pass
class ChannelsTooMuchError(_E): pass
class ChatAdminRequiredError(_E): pass
class SessionPasswordNeededError(_E): pass
class AuthKeyDuplicatedError(_E): pass
class AuthKeyUnregisteredError(_E): pass
class UserDeactivatedError(_E): pass
class PhoneCodeInvalidError(_E): pass
class PhoneNumberBannedError(_E): pass
class ChatWriteForbiddenError(_E): pass
class UserNotParticipantError(_E): pass
''',
    "telethon/tl/__init__.py": "",
    "telethon/tl/functions/__init__.py": "",
    "telethon/tl/functions/channels.py": '''
class _R:
    def __init__(self, *a, **k):
        pass
JoinChannelRequest = LeaveChannelRequest = GetParticipantRequest = _R
''',
    "telethon/tl/functions/messages.py": '''
class _R:
    def __init__(self, *a, **k):
        pass
ImportChatInviteRequest = CheckChatInviteRequest = _R
''',
}


def make_tree(with_stub=True):
    d = tempfile.mkdtemp(prefix="jafj_smoke_")
    shutil.copy2(SRC, os.path.join(d, "95.py"))
    if with_stub:
        for rel, body in STUB.items():
            p = os.path.join(d, "stub", *rel.split("/"))
            os.makedirs(os.path.dirname(p), exist_ok=True)
            with open(p, "w", encoding="utf-8") as f:
                f.write(body.lstrip("\n"))
    return d


def run(d, py_path=""):
    env = dict(os.environ)
    env.pop("PYTHONPATH", None)
    if py_path:
        env["PYTHONPATH"] = py_path
    env["JAFJ_NO_AUTO_LOGIN"] = "1"          # کدِ ورود فرستاده نشود
    env["PIP_NO_INDEX"] = "1"                # نصبِ خودکار در تست به شبکه نرود
    env["PIP_DISABLE_PIP_VERSION_CHECK"] = "1"
    for k in ("JAFJ_SELF_UID", "JAFJ_ONLY", "JAFJ_SELF_DIR"):
        env.pop(k, None)
    return subprocess.run([sys.executable, "95.py"], cwd=d, env=env,
                          capture_output=True, text=True, timeout=180)


def read(p):
    try:
        with open(p, encoding="utf-8", errors="ignore") as f:
            return f.read()
    except Exception:
        return ""


# ── A) با telethonِ بدلی: بوت تا مرحله‌ی اتصال ──
d1 = make_tree(with_stub=True)
r1 = run(d1, os.path.join(d1, "stub"))
boot = read(os.path.join(d1, "jafj_boot.log"))
crash = read(os.path.join(d1, "jafj_boot_error.txt"))

check("A1: 95.py اجرا می‌شود", "95.py اجرا شد" in r1.stdout, r1.stdout[-500:] or
      r1.stderr[-500:])
check("A2: دیتابیس/تنظیمات مانعِ بوت نمی‌شوند",
      "جفج" in r1.stdout, r1.stdout[:300])
check("A3: مرحله‌ی بارگذاریِ telethon ثبت شده",
      "telethon بارگذاری شد" in boot, boot[-300:])
check("A4: مرحله‌ی ساختِ کلاینت ثبت شده",
      "کلاینتِ تلگرام ساخته شد" in boot, boot[-300:])
check("A5: مرحله‌ی شروعِ اتصال ثبت شده",
      "شروعِ اتصال به تلگرام" in boot, boot[-300:])
check("A6: سشنِ نامعتبر → کدِ خروج ۷۸ (کدِ ورود فرستاده نمی‌شود)",
      r1.returncode == 78, r1.returncode)
check("A7: پیامِ شروع («آنلاین شد») در این حالت نباید ثبت شود",
      "آنلاین شد — پنل فعال" not in boot, boot[-200:])
check("A8: این مسیر «خطای بوت» نیست (فایلِ خطا ساخته نشود)",
      crash == "", crash[:300])
shutil.rmtree(d1, ignore_errors=True)

# ── B) بدونِ telethon: خطا باید در فایل بنشیند، نه اینکه خاموش بماند ──
if importlib.util.find_spec("telethon") is None:
    d2 = make_tree(with_stub=False)
    r2 = run(d2, "")
    crash2 = read(os.path.join(d2, "jafj_boot_error.txt"))
    check("B1: نبودِ telethon → کدِ ۷۱ (وابستگی)، نه مرگِ خاموش",
          r2.returncode == 71, r2.returncode)
    check("B2: علت + مسیرِ پایتون در jafj_boot_error.txt نوشته می‌شود",
          "Telethon نصب نیست" in crash2 and sys.executable in crash2,
          crash2[:300])
    check("B3: خروجیِ کنسول هم مسیرِ فایل را می‌گوید",
          "jafj_boot_error.txt" in r2.stdout, r2.stdout[-400:])
    check("B4: ردیِ بوت تا آخرین مرحله‌ی سالم هست",
          "اجرا شد" in read(os.path.join(d2, "jafj_boot.log")))
    shutil.rmtree(d2, ignore_errors=True)
else:
    print("SKIP B: در این محیط telethon نصب است")

print()
if FAILS:
    print("FAILED:", FAILS)
    sys.exit(1)
print("ALL PASS")
