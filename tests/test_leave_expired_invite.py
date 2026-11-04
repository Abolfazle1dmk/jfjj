#!/usr/bin/env python3
"""لفت با لینکِ منقضی + رکوردی که بعد از شکستِ لفت در پیوی ساکت می‌ماند.

باگِ گزارش‌شده:

  ⚠️ لفت انجام نشد … InviteHashExpiredError: The chat the user tried to
  join has expired and is not valid anymore (caused by CheckChatInviteRequest)

و بعدش: «دیگر به کسانی که در پیوی لینک می‌فرستند جواب نمی‌دهد».

ریشه‌ی خطا: `leave_link` فقط با «لینک» لفت می‌داد؛ برای لینک‌های خصوصی
(t.me/+hash) همان لینک باید دوباره با CheckChatInvite حل شود. اگر طرف
لینکش را باطل/منقضی کرده باشد، تلگرام InviteHashExpired می‌دهد و لفت
هیچ‌وقت انجام نمی‌شود — در حالی که اکانت هنوز عضوِ آن کانال است.

ریشه‌ی سکوتِ پیوی: مسیر لفتِ ناموفق، رکورد را `joined` با
`next_reminder=الان+۶۰` نگه می‌داشت؛ یعنی پنجره‌ی فعالِ «نیومدی» هیچ‌وقت
بسته نمی‌شد و در مسیر ورودیِ پیوی همین `active_window` باعث می‌شد پیام
بعدیِ همان طرف (حتی با لینک تازه) بی‌جواب بماند — هر دقیقه یک تلاش و
یک نوتیف هم روی اکانت می‌رفت.

فیکسِ این تست:
  ۱) آیدی/access_hash کانال در لحظه‌ی جوین ذخیره می‌شود؛ لفت دیگر به
     لینکِ طرف وابسته نیست.
  ۲) اگر لینکِ خصوصی منقضی شد، با «عنوانِ ذخیره‌شده» و فقط تطبیقِ یکتا
     بین دیالوگ‌ها یک تلاش دیگر می‌شود.
  ۳) شکستِ لفت رکورد را قفل نمی‌کند: next_reminder صفر می‌شود و تلاش
     بعدی با عقب‌نشینیِ پلکانی (۱ دقیقه → … → ۶ ساعت) زمان‌بندی می‌شود.
"""
import os
import shutil
import subprocess
import sys
import tempfile

HERE = os.path.dirname(os.path.abspath(__file__))
REPO = os.path.dirname(HERE)
ROOT = os.path.join(tempfile.gettempdir(), "jafj_leave_expired_invite_run")
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
    d.setdefault("_LAST_CHECK_WHY", {"why": "", "at": 0})
    d.setdefault("_note_check_why", (lambda w: None))
    for _nm in ("ChannelInvalidError", "UsernameInvalidError",
                "UsernameNotOccupiedError"):
        d.setdefault(_nm, type(_nm, (Exception,), {}))
    if "CHECK_DEFERRED" not in d:
        _m = globals().get("m")
        d["CHECK_DEFERRED"] = getattr(_m, "CHECK_DEFERRED", None) or _CdStub()
    return d

import asyncio, importlib.util, os, sys, time, types
from types import SimpleNamespace
sys.path.insert(0, os.getcwd())

# Stub the lazily imported Telegram request used to resolve old private-invite
# records that predate persisted chat_id/access_hash metadata.
class CheckChatInviteRequest:
    def __init__(self, invite_hash):
        self.invite_hash = invite_hash

_tl = types.ModuleType("telethon.tl")
_functions = types.ModuleType("telethon.tl.functions")
_messages = types.ModuleType("telethon.tl.functions.messages")
_messages.CheckChatInviteRequest = CheckChatInviteRequest
_telethon = sys.modules.setdefault("telethon", types.ModuleType("telethon"))
if not hasattr(_telethon, "__path__"):
    _telethon.__path__ = []
_tl.functions = _functions
_functions.messages = _messages
_telethon.tl = _tl
sys.modules["telethon.tl"] = _tl
sys.modules["telethon.tl.functions"] = _functions
sys.modules["telethon.tl.functions.messages"] = _messages

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


def fresh_engine():
    for f in ("jafj_settings.json", "jafj.db", "jafj_limits.json"):
        if os.path.exists(f):
            os.remove(f)
    return m.Engine()


# ═══════ L1 — ستون‌های جدید + مهاجرت ═══════
eng = fresh_engine()
cols = {r[1] for r in eng.db.conn.execute("PRAGMA table_info(exchange)")}
for c in ("chat_id", "chat_hash", "leave_fail", "leave_blocked_until"):
    check(c in cols, "L1: ستون exchange.%s ساخته شد" % c)
check('("chat_id", "INTEGER")' in src and '("leave_blocked_until"' in src,
      "L1: مهاجرت دیتابیس قدیمی هم ستون‌ها را اضافه می‌کند")
print("DONE L1 schema")


# ═══════ استخراج leave_link از سورس واقعی ═══════
class InviteHashExpiredError(Exception):
    pass


class InviteHashInvalidError(Exception):
    pass


class UserNotParticipantError(Exception):
    pass


class ChannelPrivateError(Exception):
    pass


class FloodWaitError(Exception):
    seconds = 60


class LeaveChannelRequest:
    def __init__(self, ent):
        self.ent = ent


class FakeThrottle:
    def penalize(self, w):
        pass


class FakeCheckGate:
    def penalize(self, w):
        pass


class FakeSt:
    def prof(self, tier):
        return {"channel": ""}


class FakeEng:
    def __init__(self, db):
        self.db = db
        self.st = FakeSt()
        self.join_thr = FakeThrottle()
        self.logs = []

    def log(self, lvl, kind, detail=""):
        self.logs.append((lvl, kind, detail))

    def adaptive_on_flood(self, w):
        pass


class Dial:
    def __init__(self, ent):
        self.entity = ent


class FakeClient:
    def __init__(self, expired=False, dialogs=(), leave_error=None,
                 invite_entity=None):
        self.expired = expired
        self.dialogs = list(dialogs)
        self.leave_error = leave_error
        self.invite_entity = invite_entity
        self.invite_calls = []
        self.leaves = []
        self.entity_calls = []

    async def get_entity(self, link):
        self.entity_calls.append(link)
        if self.expired:
            raise InviteHashExpiredError("expired")
        return SimpleNamespace(id=-100999, access_hash=7, title="t")

    async def __call__(self, req):
        if isinstance(req, CheckChatInviteRequest):
            self.invite_calls.append(req.invite_hash)
            return SimpleNamespace(chat=self.invite_entity)
        if isinstance(req, LeaveChannelRequest):
            if self.leave_error:
                raise self.leave_error
            self.leaves.append(req.ent)
            return True
        raise AssertionError("unexpected request: %r" % (req,))

    def iter_dialogs(self, limit=300):
        async def gen():
            for d in self.dialogs:
                yield d
        return gen()


a = src.find("    async def leave_link(link, rec_id=None):")
b = src.find("    async def reply_joined", a)
assert a > 0 and b > a, "leave_link not found in 95.py"
fn_src = "\n".join(ln[4:] if ln.startswith("    ") else ln
                   for ln in src[a:b].splitlines())
ns = {"m": m, "DRY_RUN": m.DRY_RUN, "eng": None, "client": None,
      "check_gate": FakeCheckGate(), "action_calls": [],
      "ex_cd": m.ExCooldown(gap_min=0, gap_max=0),
      "InviteHashExpiredError": InviteHashExpiredError,
      "InviteHashInvalidError": InviteHashInvalidError,
      "UserNotParticipantError": UserNotParticipantError,
      "ChannelPrivateError": ChannelPrivateError,
      "FloodWaitError": FloodWaitError,
      "LeaveChannelRequest": LeaveChannelRequest,
      "_input_channel": m._input_channel,
      "is_invite": m.is_invite,
      "invite_hash": m.invite_hash,
      # داخلِ connect_and_run تعریف می‌شود و در برشِ leave_link نیست؛
      # وظیفه‌اش فقط ذخیره‌ی هویتِ کانال است و در test_leave_scan جدا
      # آزموده می‌شود.
      "remember_channel": lambda rec_id, ent: None,
      "time": time, "SimpleNamespace": SimpleNamespace}
_ns(ns)
exec(fn_src, ns)
leave_link = ns["leave_link"]
CD0 = ns["ex_cd"]


# ═══════ L2 — لینک منقضی، ولی آیدی کانال ذخیره شده → لفت موفق ═══════
eng = fresh_engine()
rec, _new = eng.db.ex_add(7001, "@peer", "https://t.me/+expiredhash")
eng.db.ex_set(rec["id"], status="joined", chat_id=-1001234567890,
              chat_hash=987654321, channel_title="کانال طرف")
fake = FakeClient(expired=True)
ns["eng"] = FakeEng(eng.db)
ns["client"] = fake
ok, err = asyncio.run(leave_link("https://t.me/+expiredhash", rec["id"]))
check(ok is True and err == "",
      "L2: با آیدیِ ذخیره‌شده حتی وقتی لینک منقضی است لفت انجام شد (%r, %r)"
      % (ok, err))
check(len(fake.leaves) == 1
      and (getattr(fake.leaves[0], "id", None)
           or getattr(fake.leaves[0], "channel_id", None)) == 1234567890,
      "L2: لفت با InputChannel همان کانال زده شد")
check(fake.entity_calls == [],
      "L2: لینکِ منقضی اصلاً حل نشد (get_entity صدا زده نشد)")
print("DONE L2 stored identity")


# ═══════ L3 — بدون آیدیِ ذخیره‌شده و لینکِ منقضی → پیامِ روشن، نه موفقیتِ کاذب ═══════
eng = fresh_engine()
rec, _new = eng.db.ex_add(7002, "@peer2", "https://t.me/+deadlink")
eng.db.ex_set(rec["id"], status="joined")
fake = FakeClient(expired=True)
ns["eng"] = FakeEng(eng.db)
ns["client"] = fake
ok, err = asyncio.run(leave_link("https://t.me/+deadlink", rec["id"]))
check(ok is False and "منقضی" in err,
      "L3: لینکِ منقضی + بی‌آیدی → شکستِ صادقانه با پیام فارسی (%r)" % (err,))
check(fake.leaves == [] and not err.startswith("InviteHashExpiredError"),
      "L3: خطای خام انگلیسی نمایش داده نمی‌شود")
print("DONE L3 honest failure")


# ═══════ L3b — رکورد قدیمیِ لینک خصوصی بدون chat_id/title ═══════
# get_entity روی t.me/+… با ValueError/InviteHashExpired می‌افتد؛ اگر خودِ
# اکانت هنوز عضو باشد، CheckChatInvite باید کانال را resolve کند تا ظرفیت آزاد شود.
eng = fresh_engine()
rec, _new = eng.db.ex_add(7006, "@peer6", "https://t.me/+legacyhash")
eng.db.ex_set(rec["id"], status="joined")
ent = SimpleNamespace(id=-1006666, access_hash=66, title="کانال قدیمی")
fake = FakeClient(expired=True, invite_entity=ent)
ns["eng"] = FakeEng(eng.db)
ns["client"] = fake
ok, err = asyncio.run(leave_link("https://t.me/+legacyhash", rec["id"]))
check(ok is True and len(fake.leaves) == 1 and fake.invite_calls == ["legacyhash"],
      "L3b: private invite بدون metadata با CheckChatInvite حل شد (%r, %r)"
      % (ok, err))
print("DONE L3b legacy invite resolution")


# ═══════ L4 — خطاهای «عضو نیست»/«کانال خصوصی» = لفت لازم نیست، نه خطا ═══════
for exc, label in ((UserNotParticipantError("x"), "عضو نبودیم"),
                   (ChannelPrivateError("x"), "کانال خصوصی/بن")):
    eng = fresh_engine()
    rec, _new = eng.db.ex_add(7003, "@peer3", "@peer3chan")
    eng.db.ex_set(rec["id"], status="joined", chat_id=-1005, chat_hash=3)
    ns["eng"] = FakeEng(eng.db)
    ns["client"] = FakeClient(leave_error=exc)
    ok, err = asyncio.run(leave_link("@peer3chan", rec["id"]))
    check(ok is True and err == "", "L4: %s → لفت شود (بدون خطا)" % label)
print("DONE L4 already-left")


# ═══════ L5 — فالبکِ «عنوانِ ذخیره‌شده» برای لینکِ منقضیِ بی‌آیدی ═══════
eng = fresh_engine()
rec, _new = eng.db.ex_add(7004, "@peer4", "https://t.me/+gone4")
eng.db.ex_set(rec["id"], status="joined", channel_title="کانال یکتا ۴")
ent = SimpleNamespace(id=-1004444, access_hash=44, title="کانال یکتا ۴",
                      username=None)
fake = FakeClient(expired=True, dialogs=[Dial(ent)])
ns["eng"] = FakeEng(eng.db)
ns["client"] = fake
ok, err = asyncio.run(leave_link("https://t.me/+gone4", rec["id"]))
check(ok is True and len(fake.leaves) == 1
      and getattr(fake.leaves[0], "id", None) == -1004444,
      "L5: با تطبیقِ یکتای عنوان هم لفت انجام شد (%r)" % ((ok, err, fake.leaves),))

# عنوان تکراری → هیچ لفتِ اشتباهی
eng = fresh_engine()
rec, _new = eng.db.ex_add(7005, "@peer5", "https://t.me/+gone5")
eng.db.ex_set(rec["id"], status="joined", channel_title="کانال تکراری")
d1 = SimpleNamespace(id=-1001, access_hash=1, title="کانال تکراری", username=None)
d2 = SimpleNamespace(id=-1002, access_hash=2, title="کانال تکراری", username=None)
fake = FakeClient(expired=True, dialogs=[Dial(d1), Dial(d2)])
ns["eng"] = FakeEng(eng.db)
ns["client"] = fake
ok, err = asyncio.run(leave_link("https://t.me/+gone5", rec["id"]))
check(ok is False and fake.leaves == [],
      "L5: عنوان تکراری → لفتِ اشتباه انجام نمی‌شود")
print("DONE L5 title fallback")


# ═══════ L6 — حلقه‌ی یادآوری: شکستِ لفت رکورد را قفل نمی‌کند ═══════
a = src.find("# ── یادآوری عضو‌نشده")
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
    "fa = m.fa\n"
    "async def _run(eng, x, stub):\n"
    "    now_rem = int(time.time())\n"
    "    confirm_peer_membership = stub.confirm\n"
    "    send_not_joined_reminder = stub.send_rem\n"
    "    leave_link = stub.leave\n"
    "    reminder_delay = stub.reminder_delay\n"
    "    membership_check_delay = stub.check_delay\n"
    "    note = stub.note\n"
    "    warn_membership_check_broken = stub.warn\n"
    "    check_gate = stub.gate\n"
    "    unk_fallback = stub.unk_fallback\n"
    "    next_action_after = lambda rec, base=None: int(base)\n"
    + "\n".join("    " + ln for ln in ded.splitlines())
    + "\n")
hns = {"m": m, "ex_cd": m.ExCooldown(gap_min=0, gap_max=0)}
_ns(hns)
exec(harness, hns)
run_reminder = hns["_run"]


class FakeGate:
    def blocked(self):
        return False


class Stub:
    def __init__(self, member=False, leave_ok=False, leave_err="InviteHashExpiredError: expired"):
        self.member = member
        self.leave_ok = leave_ok
        self.leave_err = leave_err
        self.left = []
        self.notes = []
        self.gate = FakeGate()

    def unk_fallback(self, rec, extra=1):
        return False

    async def confirm(self, pid, fast=False, rec_id=None, confirm=True):
        return self.member

    async def send_rem(self, rec):
        return True

    async def leave(self, link, rec_id=None):
        self.left.append(link)
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


def mkRec(eng, peer, link, status, reminders=0, direction="in"):
    r, _n = eng.db.ex_add(peer, "p%d" % peer, link)
    now = int(time.time())
    eng.db.ex_set(r["id"], status=status, direction=direction,
                  reminders=reminders, peer_id=peer,
                  src_chat=111, src_msg=222, next_reminder=now - 5,
                  next_check=0, last_check=0)
    return eng.db.ex_get(r["id"])


eng = fresh_engine()
stub = Stub(member=False, leave_ok=False)
r = mkRec(eng, 7010, "@c7010", "joined", reminders=2, direction="out")
asyncio.run(run_reminder(eng, eng.ex_cfg(), stub))
g = eng.db.ex_get(r["id"])
now = int(time.time())
check(len(stub.left) == 1 and g["status"] == "joined",
      "L6: شکستِ لفت → رکورد joined می‌ماند")
check(g["leave_fail"] == 1, "L6: شمارنده‌ی شکستِ لفت بالا رفت")
check(int(g["next_reminder"] or 0) == 0,
      "L6: next_reminder صفر شد → پنجره‌ی «نیومدی» باز نمی‌ماند")
check(int(g["leave_blocked_until"] or 0) > now,
      "L6: عقب‌نشینیِ لفت فعال شد")
check(int(g["next_check"] or 0) >= now + 30,
      "L6: تلاش بعدیِ لفت با فاصله زمان‌بندی شد (نه هر دقیقه)")
check(any("نیومدی" in t for t in stub.notes),
      "L6: گزارش می‌گوید دلیل لفت «نیومدی» بود (نه ادعای خروجِ طرف)")

# اجرای دوباره در همان بازه → تلاش تکراری روی اکانت نمی‌رود
eng.db.ex_set(r["id"], next_reminder=now - 5)
asyncio.run(run_reminder(eng, eng.ex_cfg(), stub))
check(len(stub.left) == 1,
      "L6: داخل بازه‌ی عقب‌نشینی، لفتِ تکراری زده نشد")
print("DONE L6 reminder loop backoff")


# ═══════ L7 — سیم‌کشیِ سورس (هر دو حلقه + جوین + گزارش) ═══════
check(src.count("leave_blocked_until") >= 6,
      "L7: عقب‌نشینیِ لفت در هر دو حلقه و دیتابیس سیم‌کشی شده")
check("def ex_live_leave_text(self, rec, err=\"\", reason=\"left\")" in src,
      "L7: گزارشِ لفت دلیل را می‌گیرد (دیگر همیشه «طرف خارج شده بود» نمی‌گوید)")
check('def remember_channel(rec_id, ent):' in src
      and "remember_channel(rec_id, joined_ent[\"e\"])" in src,
      "L7: جوین، آیدیِ کانال را برای لفتِ بعدی ذخیره می‌کند")
check("input_from_record()" in src and "resolve_by_title" in src,
      "L7: لفت اول با آیدیِ ذخیره‌شده و بعد لینک/عنوان را امتحان می‌کند")
check('x.get("_block_notice_at"' in src and "ex_blocked" in src,
      "L7: وقتی صف به‌خاطر FloodWait بسته می‌شود، یک‌بار به مالک گفته می‌شود")
check("event.is_private and extract_links(body_text)" in src,
      "L7: فیلترِ کلمات، لینکِ پیوی را بی‌جواب نمی‌کند")
print("DONE L7 wiring")

print("DONE PASS")
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
    env["PORT"] = "8204"
    env["JAFJ_PORT"] = "8204"
    for k in ("RAILWAY_ENVIRONMENT", "RAILWAY_SERVICE_ID", "RAILWAY_PROJECT_ID",
              "JAFJ_HOSTED", "JAFJ_LOGIN_RETRY", "BOT_TOKEN", "API_ID",
              "API_HASH", "BACKUP_CHAT", "BACKUP_EVERY"):
        env.pop(k, None)
    p = subprocess.run([sys.executable, "-c", DRIVER], cwd=APP, env=env,
                       capture_output=True, text=True, timeout=180)
    return p.stdout, p.stderr, p.returncode


def main():
    print("--- leave_expired_invite: لفت با لینکِ منقضی + پایانِ سکوتِ پیوی ---")
    reset()
    out, err, rc = run()
    if err.strip():
        print("--- driver stderr (tail) ---")
        print(err[-2000:])
    print("--- driver output ---")
    for line in out.splitlines():
        if line.startswith(("OK", "FAIL", "DONE", "L1", "L2", "L3", "L4", "L5", "L6", "L7")):
            print(line)
    if "DONE PASS" in out and "FAIL" not in out and rc == 0:
        print("ALL: PASS")
        return True
    print("ALL: FAIL")
    return False


if __name__ == "__main__":
    sys.exit(0 if main() else 1)
