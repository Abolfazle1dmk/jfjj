#!/usr/bin/env python3
"""پیوی + لینک → «دارم چک می‌کنم» → سکوت ابدی (باگِ گزارش‌شده).

سناریوی کاربر: یکی در پیوی لینک کانالش را می‌فرستد، ربات می‌گوید
«⏳ دارم چک می‌کنم، صبر کن» (msg_wait) ولی دیگر هیچ‌وقت هیچی نمی‌گوید —
نه «نیومدی»، نه «جوین شدم».

ریشه (سه بن‌بست که هر سه همین علامت را می‌دهند):

  ۱) دروازه‌ی send_not_joined_reminder: حلقه‌ی یادآوری هر نوبت اول
     عضویت را چک می‌کند (یک عملکرد در صف تک‌عملکردی) و بلافاصله بعدش
     می‌خواهد «نیومدی» بفرستد؛ ولی دروازه‌ی «پشت‌سرهم نرو» چون چک همین
     الان تمام شده، همیشه ارسال را رد می‌کند (False). حلقه این False را
     «شکستِ ارسال» حساب می‌کند، سه بار اخطار می‌سوزاند و تبادل را لغو
     می‌کند — بدون اینکه حتی یک «نیومدی» رسیده باشد. یعنی برای لینکِ
     پیویِ کسی که هنوز عضو کانال من نشده (حالت معمول)، بعد از msg_wait
     سکوت قطعی بود.

  ۲) تأیید دستی (auto_join خاموش): say("msg_wait") پرچم replied را ۱
     می‌کند و دستور «تبادل تأیید» آن را صفر نمی‌کرد؛ بعد از جوینِ واقعی،
     reply_joined به‌خاطر replied=1 پیام «جوین شدم» را نمی‌فرستاد.

  ۳) کانال من تنظیم نشده: شاخه‌ی «نامشخص» برای این حالت next_reminder
     ست نمی‌کرد؛ رکورد برای همیشه pending می‌ماند و حتی بعد از ست‌کردن
     کانال هم هیچ‌وقت دوباره چک نمی‌شد.

فیکس: صف تک‌عملکردی «نوعِ آخرین عملکردِ هر رکورد» را نگه می‌دارد؛
دروازه فقط وقتی رد می‌کند که آخرین عملکرد یک پیام/جوین/لفت بوده باشد
(محافظِ پیامِ تکراری سر جایش می‌ماند)، ولی وقتی آخرین عملکرد «چکِ»
بی‌صدای همان نوبت بوده، ارسال ادامه‌ی همان نوبت است: صف خودش باقیِ
فاصله را صبر می‌کند و بعد می‌فرستد. به‌علاوه: تأیید دستی replied را
صفر می‌کند و شاخه‌ی بی‌کانال هم نوبتِ چکِ بعدی می‌گیرد.

این تست حلقه‌ی واقعیِ یادآوری را با send_not_joined_reminder واقعی و
صف واقعی (نه stub ارسال) اجرا می‌کند — همان ترکیبی که قبلاً هیچ تستی
با هم اجرایش نکرده بود و باگ از همان‌جا رد شده بود.
"""
import os
import shutil
import subprocess
import sys
import tempfile

HERE = os.path.dirname(os.path.abspath(__file__))
REPO = os.path.dirname(HERE)
ROOT = os.path.join(tempfile.gettempdir(), "jafj_pv_link_wait_run")
APP = os.path.join(ROOT, "app")
DATA = os.path.join(ROOT, "data")
SRC_REPO = REPO


DRIVER = r"""
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


def fresh_engine():
    for f in ("jafj_settings.json", "jafj.db", "jafj_limits.json"):
        if os.path.exists(f):
            os.remove(f)
    return m.Engine()


GAP = 0.4          # فاصله‌ی صف در تست (در واقعیت ۱۵–۲۰ ثانیه)

# ── استخراج تابع واقعی ارسال «نیومدی» ──────────────────────────────────
a = src.find("    async def send_not_joined_reminder")
b = src.find("    # ---------- پیدا کردن کانال طرف", a)
assert a > 0 and b > a, "send_not_joined_reminder not found"
fn_src = "\n".join(ln[4:] if ln.startswith("    ") else ln
                   for ln in src[a:b].splitlines())


class FakeClient:
    def __init__(self):
        self.sent = []

    async def send_message(self, chat, body, reply_to=None, **kw):
        self.sent.append((time.time(), chat, body, reply_to))
        return object()


eng = fresh_engine()
eng.st.prof("standard")["channel"] = "@my_chan"
x = eng.ex_cfg()
x["enabled"] = True
x["reply"] = True
x["auto_join"] = True
x["msg_no"] = ""
x["max_reminders"] = 2

fake = FakeClient()
cd = m.ExCooldown(gap_min=GAP, gap_max=GAP)
ns = {"eng": eng, "client": fake, "DRY_RUN": False, "asyncio": asyncio,
      "time": time, "DEFAULT_MSG_NO": m.DEFAULT_MSG_NO, "ex_cd": cd}
exec(fn_src, ns)
real_send = ns["send_not_joined_reminder"]

# ── استخراج حلقه‌ی واقعی یادآوری ────────────────────────────────────────
a = src.find("# ── یادآوری عضو‌نشده: دو پیام «نیومدی»")
b = src.find("# ۳) چک دوره‌ای", a)
assert a > 0 and b > a, "reminder loop markers missing"
block = src[a:b]
lines = block.splitlines()
while lines and (lines[0].lstrip().startswith("#") or not lines[0].strip()):
    lines.pop(0)
while lines and not lines[-1].strip():
    lines.pop()
IND = 16
ded = "\n".join(ln[IND:] if ln.startswith(" " * IND) else ln for ln in lines)
harness_src = (
    "import time\n"
    "async def _run(eng, x, stub):\n"
    "    now_rem = int(time.time())\n"
    "    confirm_peer_membership = stub.confirm\n"
    "    send_not_joined_reminder = _REAL_SEND\n"
    "    leave_link = stub.leave\n"
    "    reminder_delay = stub.reminder_delay\n"
    "    membership_check_delay = stub.check_delay\n"
    "    note = stub.note\n"
    "    check_gate = stub.gate\n"
    "    unk_fallback = stub.unk_fallback\n"
    "    warn_membership_check_broken = stub.warn_broken\n"
    "    ex_cd = _CD\n"
    "    next_action_after = lambda rec, base=None: int(base)\n"
    + "\n".join("    " + ln for ln in ded.splitlines())
    + "\n"
)
async def _warn_no_peer_stub(*a, **k):
    return None


hns = {"_REAL_SEND": real_send, "_CD": cd, "fa": m.fa,
       # این بلوک از 95.py برش خورده و این دو نام را می‌خواند
       # (سنتینلِ «طرف قابلِ شناسایی نیست» + هشدارِ راهنمای آن).
       "CHECK_NO_PEER": m.CHECK_NO_PEER,
       "warn_peer_unresolvable": _warn_no_peer_stub}
exec(harness_src, hns)
run_once = hns["_run"]


class GateStub:
    def blocked(self, now=None):
        return False


MEMBER = {}


class Stub:
    def __init__(self):
        self.left = []
        self.notes = []
        self.gate = GateStub()
        self.warned = []

    async def warn_broken(self, now):
        self.warned.append(now)

    def unk_fallback(self, rec, extra=1):
        return False

    async def confirm(self, pid, fast=False, rec_id=None, confirm=True):
        # وفادار به peer_in_my_channel واقعی: چک عضویت یک «عملکرد» در
        # صف تک‌عملکردی همان رکورد است و خنک‌کننده‌اش را ثبت می‌کند.
        async def _req():
            return MEMBER.get(pid)
        return await cd.action("check", rec_id, _req)

    async def leave(self, link, rec_id=None):
        self.left.append(link)
        return True, ""

    async def note(self, text):
        self.notes.append(text)

    @staticmethod
    def reminder_delay():
        return 1

    @staticmethod
    def check_delay():
        return 1


def pv_record(peer, link):
    # دقیقاً همان وضعیتی که شاخه‌ی «نامشخص» بعد از msg_wait می‌سازد:
    # رکورد pending با نوبتِ چکِ دوباره.
    r, _n = eng.db.ex_add(peer, "@pvuser", link)
    eng.db.ex_set(r["id"], status="pending", direction="in", peer_id=peer,
                  src_chat=peer, src_msg=99, replied=0, reminders=0,
                  next_reminder=int(time.time()) - 1,
                  note="عضویت نامشخص — دوباره چک می‌کنم")
    return eng.db.ex_get(r["id"])


# ════ P1: لینکِ پیوی، طرف هنوز عضو نیست → دو «نیومدی» و بعد لغو ════
MEMBER[4242] = False
r1 = pv_record(4242, "@pvchan")
stub = Stub()
for turn in range(6):
    asyncio.run(run_once(eng, x, stub))
    g = eng.db.ex_get(r1["id"])
    if g["status"] in ("failed", "left", "approved"):
        break
    # گذشتنِ زمان: هم خنک‌کننده تمام می‌شود هم نوبتِ یادآوری می‌رسد
    time.sleep(GAP + 0.25)
    eng.db.ex_set(r1["id"], next_reminder=int(time.time()) - 1)

g1 = eng.db.ex_get(r1["id"])
bodies = [s[2] for s in fake.sent]
print("P1 sent", bodies, "status", g1["status"],
      "reminders", g1["reminders"], "strikes", g1["strikes"])
check(len(bodies) == 2,
      "P1: بعد از «دارم چک می‌کنم» دقیقاً دو «نیومدی» به طرف رسید (نه سکوت)")
check(all("نیومدی" in bd and "@my_chan" in bd for bd in bodies),
      "P1: متن یادآوری‌ها «نیومدی» + کانال من است")
if len(fake.sent) >= 2:
    gap_sent = fake.sent[1][0] - fake.sent[0][0]
    print("P1 gap between reminders %.2f" % gap_sent)
    check(gap_sent >= GAP - 0.05,
          "P1: دو یادآوری پشت‌سرهمِ درجا نیستند (فاصله‌ی عملکرد حفظ شد)")
check(g1["status"] == "failed",
      "P1: بعد از دو یادآوریِ بی‌جواب، تبادل لغو شد")

# ════ P2: لینکِ پیوی، طرف عضو است → approved، بدون «نیومدی» ════
MEMBER[555] = True
fake.sent.clear()
r2 = pv_record(555, "@memberchan")
asyncio.run(run_once(eng, x, stub))
g2 = eng.db.ex_get(r2["id"])
print("P2 status", g2["status"], "next", g2["next_reminder"],
      "sent", len(fake.sent))
check(g2["status"] == "approved" and g2["next_reminder"] == 0,
      "P2: عضوِ واقعی در صف جوین رفت")
check(len(fake.sent) == 0, "P2: برای عضوِ واقعی «نیومدی» نرفت")

# ════ P3: محافظِ پیام تکراری سر جایش ماند ════
eng3 = fresh_engine()
eng3.st.prof("standard")["channel"] = "@my_chan"
x3 = eng3.ex_cfg()
x3["reply"] = True
fake3 = FakeClient()
cd3 = m.ExCooldown(gap_min=GAP, gap_max=GAP)
ns3 = {"eng": eng3, "client": fake3, "DRY_RUN": False, "asyncio": asyncio,
       "time": time, "DEFAULT_MSG_NO": m.DEFAULT_MSG_NO, "ex_cd": cd3}
exec(fn_src, ns3)
send3 = ns3["send_not_joined_reminder"]
r3, _n = eng3.db.ex_add(6001, "@dup", "@dupchan")
eng3.db.ex_set(r3["id"], src_chat=111, src_msg=222)


async def dup_scenario():
    first = await send3(eng3.db.ex_get(r3["id"]))
    second = await send3(eng3.db.ex_get(r3["id"]))
    return first, second


first, second = asyncio.run(dup_scenario())
print("P3 first", first, "second", second, "sent", len(fake3.sent))
# None = «تعویق، نه شکست»؛ حلقه‌ی یادآوری با این مقدار اخطار نمی‌سوزاند
# و مسیر «سه بار نشد → لفت» را جلو نمی‌آورد. پیام هم که نرفته (sent==1).
check(first is True and second is None and len(fake3.sent) == 1,
      "P3: «نیومدی» دوم درجا پشت اولی نمی‌رود (محافظ تکراری سالم ماند)")


async def after_join():
    rec = eng3.db.ex_get(r3["id"])
    await cd3.action("join", rec["id"], lambda: None)
    return await send3(eng3.db.ex_get(r3["id"]))


time.sleep(GAP + 0.25)
# سقف مادام‌العمر را برای ادامه‌ی این سناریو مستقل نگه می‌داریم
eng3.db.ex_set(r3["id"], reminders_total=0)
after_join_res = asyncio.run(after_join())
print("P3 after join", after_join_res, "sent", len(fake3.sent))
check(after_join_res is None and len(fake3.sent) == 1,
      "P3: «نیومدی» درجا بعد از جوین هم نمی‌رود (رفتار پین‌شده‌ی قبلی)")

# ════ P4: تأیید دستی، پرچم replied نباید «جوین شدم» را خفه کند ════
eng4 = fresh_engine()
x4 = eng4.ex_cfg()
x4["enabled"] = True
x4["auto_join"] = False
r4, _n = eng4.db.ex_add(777, "@waiter", "@waitchan")
# replied=1 یعنی پیام «دارم چک می‌کنم» (msg_wait) قبلاً رفته است
eng4.db.ex_set(r4["id"], status="pending", replied=1, peer_id=777)
out4 = eng4.exchange_cmd("تأیید %d" % r4["id"])
g4 = eng4.db.ex_get(r4["id"])
print("P4 cmd", out4, "status", g4["status"], "replied", g4["replied"])
check(g4["status"] == "approved",
      "P4: تأیید دستی رکورد را در صف جوین گذاشت")
check(int(g4["replied"] or 0) == 0,
      "P4: بعد از تأیید دستی replied صفر است تا «جوین شدم» بعد از جوین برود")

# ════ P5: شاخه‌ی «کانال من تنظیم نشده» بن‌بست نیست ════
i = src.find("# ── نامشخص ──")
j = src.find("# ── عضو هست →", i)
assert i > 0 and j > i
branch = src[i:j]
check("ex_no_channel" in branch, "P5: هشدارِ کانال‌نداشتن سر جایش است")
k = branch.find("ex_no_channel")
window_before = branch[max(0, k - 900):k]
check("next_reminder" in window_before,
      "P5: رکوردِ بی‌کانال هم نوبتِ چکِ دوباره می‌گیرد (بعد از ست‌کردن کانال زنده می‌شود)")

# ════ P6: سیم‌کشی فیکس ════
check("def last_kind" in src,
      "P6: صف تک‌عملکردی نوع آخرین عملکرد هر رکورد را می‌داند")
check('wait_op = ex_cd.wait_for(rec.get("id"))' in src,
      "P6: دروازه‌ی «پشت‌سرهم نرو» در نقطه‌ی ارسال سر جایش است")

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
        shutil.copy2(os.path.join(SRC_REPO, f), APP)


def run():
    env = dict(os.environ)
    env["DATA_DIR"] = DATA
    env["PORT"] = "8247"
    env["JAFJ_PORT"] = "8247"
    for k in ("RAILWAY_ENVIRONMENT", "RAILWAY_SERVICE_ID", "RAILWAY_PROJECT_ID",
              "JAFJ_HOSTED", "JAFJ_LOGIN_RETRY", "BOT_TOKEN", "API_ID",
              "API_HASH", "BACKUP_CHAT", "BACKUP_EVERY"):
        env.pop(k, None)
    p = subprocess.run([sys.executable, "-c", DRIVER], cwd=APP, env=env,
                       capture_output=True, text=True, timeout=180)
    return p.stdout, p.stderr, p.returncode


def main():
    print("--- pv_link_wait_flow: لینک پیوی → «دارم چک می‌کنم» → نباید سکوت شود ---")
    reset()
    out, err, rc = run()
    if err.strip():
        print("--- driver stderr (tail) ---")
        print(err[-2000:])
    print("--- driver output ---")
    for line in out.splitlines():
        if line.startswith(("P1", "P2", "P3", "P4", "OK", "FAIL", "FAILED",
                            "DONE", "  -")):
            print(line)
    if "DONE PASS" in out and "FAIL" not in out and rc == 0:
        print("ALL: PASS")
        return True
    print("ALL: FAIL")
    return False


if __name__ == "__main__":
    sys.exit(0 if main() else 1)
