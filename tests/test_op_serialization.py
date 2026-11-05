#!/usr/bin/env python3
"""صفِ تک‌عملکردی تبادل: هیچ دو عملکردی پشت‌سرهم (درجا) اجرا نمی‌شوند.

باگی که صاحب‌حساب گزارش کرد:

  «عملکردها را پشت سر هم انجام می‌داد. در قسمت تبادل مثلاً جوین می‌شد و
   در صدم‌ثانیه به طرف می‌گفت «نیومدی»، بار دوم هم همین‌طور، و درجا لفت
   می‌داد. اگر جوین زده بود باید ۱۵ تا ۲۰ ثانیه بعد چک کند که آیا طرف
   واقعاً جوین شده یا نه؛ رکوردی که توی چک‌های قبلی بوده را نباید همین
   الان دوباره چک کند. بین «نیومدی» اول و دوم هم باید فاصله باشد، نه درجا.»

ریشه: چهار مسیر همزمان (پیامِ «جوین شدم»ِ طرف، حلقه‌ی یادآوری، چک
نگهبانی، کارگرِ صفِ جوین) هیچ‌کدام از کارِ بقیه خبر نداشتند و روی **یک
رکورد** پشت‌سرهم عملیات می‌زدند. هیچ‌جا «زمانِ آخرین عملکرد» نگه داشته
نمی‌شد.

فیکس (ExCooldown):

  ۱) قفل سراسری — در هر لحظه فقط یک عملکردِ تبادل (چک عضویت / جوین / لفت /
     پیام «نیومدی» / پیام «جوین شدم») اجرا می‌شود؛
  ۲) فاصله‌ی سراسری — بعد از تمام‌شدن هر عملکرد، ۱۵–۲۰ ثانیه (پیش‌فرض،
     تصادفی) صبر می‌شود و بعد نوبتِ بعدی؛
  ۳) خنک‌کننده‌ی هر رکورد — رکوردی که تازه جوین/چک/پیام گرفته، تا پایانِ
     همان فاصله دوباره چک یا پیام نمی‌گیرد.

این تست هم کلاس را رفتاری می‌سنجد (با فاصله‌ی کوتاه تا سریع بماند) و هم
سیم‌کشیِ سورسِ واقعی را پین می‌کند تا مسیرها دوباره از صف بیرون نزنند.
"""
import os
import shutil
import subprocess
import sys
import tempfile

HERE = os.path.dirname(os.path.abspath(__file__))
REPO = os.path.dirname(HERE)
ROOT = os.path.join(tempfile.gettempdir(), "jafj_op_serialization_run")
APP = os.path.join(ROOT, "app")
DATA = os.path.join(ROOT, "data")
SRC_REPO = REPO


DRIVER = r"""
import asyncio, importlib.util, json, os, random, sys, time
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


# ════════════════════════════════════════════════════════════
# ۱) پیش‌فرض‌ها و سیم‌کشی سورس
# ════════════════════════════════════════════════════════════
eng = m.Engine()
x = eng.ex_cfg()
print("DEF op_gap_min", x.get("op_gap_min_sec"), "max", x.get("op_gap_max_sec"))
check(x.get("op_gap_min_sec") == 15, "۱: پیش‌فرض کفِ فاصله‌ی عملکرد ۱۵ ثانیه")
check(x.get("op_gap_max_sec") == 20, "۱: پیش‌فرض سقفِ فاصله‌ی عملکرد ۲۰ ثانیه")
check("class ExCooldown" in src, "۱: کلاس صفِ تک‌عملکردی وجود دارد")

i_gate = src.find("check_gate = CheckGate()")
i_cd = src.find("ex_cd = ExCooldown(")
i_pimc = src.find("async def peer_in_my_channel")
check(0 < i_gate < i_cd < i_pimc,
      "۱: صف قبل از تابع‌های چک ساخته می‌شود (همه‌ی مسیرها از یک دریچه)")

check('await ex_cd.action("check", rec_id, _one_req)' in src,
      "۱: چکِ عضویت داخل صفِ سراسری است")
check('await ex_cd.action("join", rec_id, _do_join)' in src,
      "۱: جوین داخل صفِ سراسری است")
check('await ex_cd.action("leave", rec_id, _do_leave)' in src,
      "۱: لفت داخل صفِ سراسری است")
check('await ex_cd.action("reminder", rec.get("id"), _send_reminder)' in src,
      "۱: ارسال «نیومدی» داخل صفِ سراسری است")
check('await ex_cd.action("reply_joined", rec.get("id"), _send_reply)' in src,
      "۱: پیام «جوین شدم» داخل صفِ سراسری است")
check('await ex_cd.action("say", (rec or {}).get("id"), _do_reply)' in src,
      "۱: پاسخ مستقیم رویداد داخل صفِ سراسری است")
check("wait_op = ex_cd.wait_for(rec.get(\"id\"))" in src,
      "۱: دروازه‌ی قطعیِ «پشت‌سرهم نرو» داخل تنها نقطه‌ی ارسال «نیومدی»")

# حلقه‌ی یادآوری و حلقه‌ی نگهبانی هر دو نوبتِ رکورد را از صف می‌پرسند
r = src.find("# ── یادآوری عضو‌نشده")
r2 = src.find("# ۳) چک دوره‌ای", r)
w2 = src.find("# برای دقت فاصله‌ی یادآوری", r2)
check(0 < r < r2 < w2, "۱: مارکرهای دو حلقه سر جایشان است")
check("ex_cd.defer_if_due(rec, rec.get(\"next_reminder\"))" in src[r:r2],
      "۱: حلقه‌ی یادآوری رکوردِ در صف/خنک‌کننده را عقب می‌اندازد")
check("ex_cd.defer_if_due(rec, rec.get(\"next_check\"))" in src[r2:w2],
      "۱: چک نگهبانی رکوردی که همین الان چک/جوین شده را دوباره چک نمی‌کند")
check("rec_id=rec[\"id\"]" in src[r:r2], "۱: چکِ حلقه‌ی یادآوری با شناسه‌ی رکورد")
check("rec_id=rec[\"id\"]" in src[r2:w2], "۱: چکِ نگهبانی با شناسه‌ی رکورد")
check("leave_link(rec[\"link\"], rec[\"id\"])" in src[r:r2],
      "۱: لفتِ حلقه‌ی یادآوری در صفِ همان رکورد")
check("leave_link(rec[\"link\"], rec[\"id\"])" in src[r2:w2],
      "۱: لفتِ نگهبانی در صفِ همان رکورد")
check("join_link(_join_link, _join_rec_id)" in src,
      "۱: جوینِ کارگر با شناسه‌ی رکورد در صف می‌رود")
check("next_action_after(" in src[src.find("ok, msg, title = await asyncio.wait_for"):],
      "۱: چکِ بعد از جوین با فاصله‌ی عملکرد زمان‌بندی می‌شود")
print("DONE 1 wiring")


# ════════════════════════════════════════════════════════════
# ۲) کلاس: صفِ سراسری — دو عملکرد هم‌پوشانی ندارند و بینشان فاصله است
# ════════════════════════════════════════════════════════════
GAP = 3.0
cd = m.ExCooldown(gap_min=GAP, gap_max=GAP)
SPAN = []


async def slow(kind, sec=0.6):
    t0 = time.time()
    await asyncio.sleep(sec)
    SPAN.append((kind, t0, time.time()))
    return kind


async def two_concurrent():
    return await asyncio.gather(
        cd.action("join", 901, slow, "join"),
        cd.action("check", 902, slow, "check"),
    )


t_start = time.time()
res = asyncio.run(two_concurrent())
total = time.time() - t_start
print("S2 order", [s[0] for s in SPAN], "total %.2f" % total)
check(sorted(res) == ["check", "join"], "۲: هر دو عملکرد اجرا شدند")
a, b = SPAN[0], SPAN[1]
check(a[2] <= b[1] + 0.01, "۲: هم‌پوشانی ندارند — دومی بعد از تمام‌شدنِ اولی شروع شد")
check((b[1] - a[2]) >= GAP - 0.35,
      "۲: بین دو عملکرد فاصله‌ی تنظیم‌شده رعایت شد (قبلاً درجا بود)")
check(total >= 2 * 0.6 + GAP - 0.35, "۲: زمانِ کل = اجرا + فاصله، نه موازی")
print("DONE 2 global serialization")


# ════════════════════════════════════════════════════════════
# ۳) خنک‌کننده‌ی هر رکورد: همان رکورد دوباره چک نمی‌شود، رکوردِ دیگر چرا
# ════════════════════════════════════════════════════════════
cd2 = m.ExCooldown(gap_min=GAP, gap_max=GAP)


async def rec_flow():
    t0 = time.time()
    await cd2.action("join", 701, slow, "join", 0.05)
    at_join = time.time() - t0
    # بلافاصله بعد از جوین، چکِ همان رکورد → باید صبر کند
    await cd2.action("check", 701, slow, "check", 0.05)
    at_same = time.time() - t0
    # رکوردِ دیگر معطلِ خنک‌کننده‌ی ۷۰۱ نمی‌ماند (فقط صفِ سراسری)
    await cd2.action("check", 702, slow, "check", 0.05)
    at_other = time.time() - t0
    return at_join, at_same, at_other


t_join, t_same, t_other = asyncio.run(rec_flow())
print("S3 join@%.2f same-rec@%.2f other-rec@%.2f (gap=%.1f)"
      % (t_join, t_same, t_other, GAP))
check(t_join < 0.5, "۳: جوین بدون خنک‌کننده فوراً اجرا شد")
check(GAP - 0.6 <= t_same - t_join < 2 * GAP,
      "۳: چکِ «آیا واقعاً جوین شده؟» درجا بعد از جوین نرفت — "
      "دقیقاً یک فاصله (نه صفر، نه دوبار)")
check(GAP - 0.6 <= t_other - t_same < 2 * GAP,
      "۳: عملکردِ بعدی (حتی رکوردِ دیگر) بلافاصله پشتِ قبلی نرفت — یک فاصله")
check(cd2.wait_for(701) == 0.0, "۳: بعد از گذشتنِ فاصله، رکورد آماده است")
cd2.mark_done(701)
check(cd2.wait_for(701) > 0, "۳: mark_done خنک‌کننده را برمی‌گرداند")
print("DONE 3 per-record cooldown")


# ════════════════════════════════════════════════════════════
# ۴) defer_if_due: نوبتِ سررسیده‌ی رکوردِ در صف به زمانِ درست منتقل می‌شود
# ════════════════════════════════════════════════════════════
cd3 = m.ExCooldown(gap_min=GAP, gap_max=GAP)
now = int(time.time())
ok, ts = cd3.defer_if_due({"id": 11, "next_reminder": now - 5}, now - 5)
check(ok is True and ts == 0, "۴: رکوردِ تازه (بدون عملکرد قبلی) آزاد است")
cd3.mark_done(11, now=now)
ok, ts = cd3.defer_if_due({"id": 11, "next_reminder": now - 5}, now - 5, now=now)
print("S4 defer ->", ok, ts - now)
check(ok is False, "۴: رکوردِ تازه‌عملیات‌کرده «الان نه» می‌گیرد")
check(now < ts <= now + int(GAP) + 2, "۴: زمانِ پیشنهادی به اندازه‌ی فاصله جلو است")
ok2, _ = cd3.defer_if_due({"id": 12, "next_reminder": now - 5}, now - 5, now=now)
check(ok2 is True, "۴: رکوردِ دیگر معطلِ خنک‌کننده‌ی رکوردِ اول نمی‌شود")
print("DONE 4 defer_if_due")


# ════════════════════════════════════════════════════════════
# ۵) کفِ فاصله‌ها: یادآوری/چک هرگز کوتاه‌تر از فاصله‌ی عملکرد نمی‌شوند
# ════════════════════════════════════════════════════════════
a = src.find("    def op_gap_seconds():")
b = src.find("    def watch_delay_seconds(rec):", a)
assert a > 0 and b > a, "op_gap_seconds / next_action_after / delays not found"
delays_src = "\n".join(ln[4:] if ln.startswith("    ") else ln
                       for ln in src[a:b].splitlines())
dns = {"eng": eng, "random": random, "time": time,
       "ex_cd": m.ExCooldown(gap_min=0, gap_max=0)}
exec(delays_src, dns)
op_gap_seconds = dns["op_gap_seconds"]
next_action_after = dns["next_action_after"]
reminder_delay = dns["reminder_delay"]
membership_check_delay = dns["membership_check_delay"]

x2 = eng.ex_cfg()
samples = [op_gap_seconds() for _ in range(200)]
print("S5 op_gap samples", min(samples), max(samples))
check(all(15 <= v <= 20 for v in samples), "۵: فاصله‌ی عملکرد پیش‌فرض ۱۵–۲۰ است")
check(min(samples) < max(samples), "۵: فاصله تصادفی است (الگوی ماشینی نیست)")

# حتی اگر کاربر فاصله‌ی یادآوری/چک را خیلی کوتاه گذاشته باشد، کف رعایت می‌شود
x2["reminder_min_sec"], x2["reminder_max_sec"] = 1, 3
x2["check_min_sec"], x2["check_max_sec"] = 1, 3
rem = [reminder_delay() for _ in range(200)]
chk = [membership_check_delay() for _ in range(200)]
print("S5 floored reminder", min(rem), max(rem), "check", min(chk), max(chk))
check(all(15 <= v <= 20 for v in rem),
      "۵: دو «نیومدی» هرگز درجا پشتِ هم نمی‌روند (کفِ ۱۵ ثانیه)")
check(all(15 <= v <= 20 for v in chk),
      "۵: چکِ عضویت هرگز درجا بعد از جوین نمی‌رود (کفِ ۱۵ ثانیه)")
x2["reminder_min_sec"], x2["reminder_max_sec"] = 20, 40
x2["check_min_sec"], x2["check_max_sec"] = 15, 30
check(all(20 <= reminder_delay() <= 40 for _ in range(100)),
      "۵: بازه‌ی بلندترِ کاربر دست‌نخورده می‌ماند (کف فقط کف است)")
check(all(15 <= membership_check_delay() <= 30 for _ in range(100)),
      "۵: بازه‌ی چکِ کاربر هم دست‌نخورده می‌ماند")

# next_action_after: نوبتِ بعدی هرگز زودتر از پایانِ خنک‌کننده نیست
cd4 = m.ExCooldown(gap_min=15, gap_max=20)
dns["ex_cd"] = cd4
nxt_base = int(time.time()) + 1
check(next_action_after({"id": 21}, nxt_base) == nxt_base,
      "۵: رکوردِ تازه → همان زمانِ پایه")
cd4.mark_done(21)
nxt = next_action_after({"id": 21}, nxt_base)
print("S5 next_action_after pushed", nxt - int(time.time()))
check(nxt - int(time.time()) >= 14,
      "۵: نوبتِ رکوردِ تازه‌عملیات‌کرده به بعد از خنک‌کننده منتقل شد")
check(next_action_after(None, nxt_base) == nxt_base, "۵: بدون رکورد بی‌خطر است")
print("DONE 5 delay floors")


# ════════════════════════════════════════════════════════════
# ۶) رفتاری: «نیومدی» دوم درجا پشتِ اولی نمی‌رود
# ════════════════════════════════════════════════════════════
a = src.find("    async def send_not_joined_reminder")
b = src.find("    # ---------- پیدا کردن کانال طرف", a)
assert a > 0 and b > a
fn_src = "\n".join(ln[4:] if ln.startswith("    ") else ln
                   for ln in src[a:b].splitlines())


class FakeClient:
    def __init__(self):
        self.sent = []

    async def send_message(self, chat, body, reply_to=None, **kw):
        self.sent.append((time.time(), chat, body, reply_to))
        return object()


eng6 = fresh_engine()
eng6.st.prof("standard")["channel"] = "@my_chan"
fake6 = FakeClient()
cd6 = m.ExCooldown(gap_min=GAP, gap_max=GAP)
ns6 = {"eng": eng6, "client": fake6, "DRY_RUN": False, "asyncio": asyncio,
       "time": time, "DEFAULT_MSG_NO": m.DEFAULT_MSG_NO, "ex_cd": cd6}
exec(fn_src, ns6)
send_rem = ns6["send_not_joined_reminder"]

rec6, _n = eng6.db.ex_add(6001, "@liar", "@theirchan")
eng6.db.ex_set(rec6["id"], src_chat=111, src_msg=222)


async def two_reminders():
    first = await send_rem(eng6.db.ex_get(rec6["id"]))
    t0 = time.time()
    second = await send_rem(eng6.db.ex_get(rec6["id"]))
    return first, second, time.time() - t0


first, second, waited = asyncio.run(two_reminders())
g6 = eng6.db.ex_get(rec6["id"])
print("S6 first", first, "second", second, "sent", len(fake6.sent),
      "next_reminder>now", g6["next_reminder"] > int(time.time()))
check(first is True and len(fake6.sent) == 1, "۶: «نیومدی» اول رفت")
check(second is None and len(fake6.sent) == 1,
      "۶: «نیومدی» دوم درجا پشتِ اولی نرفت (باگِ گزارش‌شده)")
# None = تعویق، False = شکستِ واقعی. اگر این دو یکی شوند، حلقه‌ی یادآوری
# «صف شلوغ است» را «پیام فرستاده نشد → سه بار شد → لفتش کن» می‌خواند و
# تبادل بی‌آنکه یک «نیومدی» برود لغو می‌شود.
eng6.ex_cfg()["reply"] = False
check(asyncio.run(send_rem(eng6.db.ex_get(rec6["id"]))) is False,
      "۶: شکستِ واقعی (ریپل خاموش) همان False می‌ماند، نه None")
eng6.ex_cfg()["reply"] = True
check(g6["next_reminder"] > int(time.time()),
      "۶: نوبتِ بعدی به زمانِ درست منتقل شد (حلقه دوباره تلاش می‌کند)")
check(g6["reminders_total"] == 0, "۶: شمارنده‌ی مادام‌العمر بی‌دلیل نسوخت")


async def third_after_gap():
    await asyncio.sleep(GAP + 0.6)
    return await send_rem(eng6.db.ex_get(rec6["id"]))


third = asyncio.run(third_after_gap())
print("S6 third", third, "sent", len(fake6.sent),
      "gap %.2f" % (fake6.sent[-1][0] - fake6.sent[0][0]))
check(third is True and len(fake6.sent) == 2,
      "۶: بعد از گذشتنِ فاصله، پیامِ دوم می‌رود")
check((fake6.sent[-1][0] - fake6.sent[0][0]) >= GAP - 0.05,
      "۶: فاصله‌ی واقعیِ دو پیام حداقل همان بازه‌ی تنظیم‌شده است")
print("DONE 6 no back-to-back reminders")


# ════════════════════════════════════════════════════════════
# ۷) رفتاری: مسابقه‌ی دو مسیر روی یک رکورد → فقط یک پیام
# ════════════════════════════════════════════════════════════
eng7 = fresh_engine()
eng7.st.prof("standard")["channel"] = "@my_chan"
fake7 = FakeClient()
cd7 = m.ExCooldown(gap_min=GAP, gap_max=GAP)
ns7 = dict(ns6, eng=eng7, client=fake7, ex_cd=cd7)
exec(fn_src, ns7)
send7 = ns7["send_not_joined_reminder"]
rec7, _n = eng7.db.ex_add(7001, "@racer", "@racechan")
eng7.db.ex_set(rec7["id"], src_chat=111, src_msg=222,
               next_reminder=int(time.time()) - 5)


async def race():
    return await asyncio.gather(
        send7(eng7.db.ex_get(rec7["id"])),
        send7(eng7.db.ex_get(rec7["id"])),
    )


r = asyncio.run(race())
print("S7 race", r, "sent", len(fake7.sent))
check(sorted([bool(v) for v in r]) == [False, True],
      "۷: دو مسیر همزمان روی یک رکورد → فقط یکی پیام داد")
check(len(fake7.sent) == 1, "۷: دقیقاً یک «نیومدی» ارسال شد")
print("DONE 7 race yields one message")


# ════════════════════════════════════════════════════════════
# ۸) رفتاری: چکِ نگهبانیِ رکوردِ تازه‌جوین‌شده درجا انجام نمی‌شود
# ════════════════════════════════════════════════════════════
a = src.find("# ۳) چک دوره‌ای")
b = src.find("# برای دقت فاصله‌ی یادآوری", a)
assert a > 0 and b > a, "periodic loop markers missing"
lines = src[a:b].splitlines()
while lines and (lines[0].lstrip().startswith("#") or not lines[0].strip()):
    lines.pop(0)
while lines and not lines[-1].strip():
    lines.pop()
IND = 16
ded = "\n".join(ln[IND:] if ln.startswith(" " * IND) else ln for ln in lines)


class Gate:
    def blocked(self, now=None):
        return False


class WStub:
    def __init__(self, member):
        self.member = member
        self.checked = []
        self.sent = []
        self.left = []
        self.notes = []
        self.warns = []

    def unk_fallback(self, rec, extra=1):
        # رفتار تست‌های قدیمی دست‌نخورده بماند
        return False

    async def confirm(self, pid, fast=False, rec_id=None, confirm=True):
        self.checked.append((pid, rec_id))
        return self.member

    async def send_rem(self, rec):
        self.sent.append(rec["id"])
        return True

    async def leave(self, link, rec_id=None):
        self.left.append(link)
        return True, ""

    async def note(self, text):
        self.notes.append(text)

    async def warn(self, now):
        self.warns.append(int(now))

    @staticmethod
    def reminder_delay():
        return 15

    @staticmethod
    def check_delay():
        return 15

    @staticmethod
    def watch_delay(rec):
        return 15


async def _warn_no_peer(*a, **k):
    return None


ph = {"m": m, "asyncio": asyncio, "time": time, "fa": m.fa,
      "_CHECK_NO_PEER": m.CHECK_NO_PEER, "_warn_no_peer": _warn_no_peer}
pharness = (
    "import asyncio, time\n"
    "async def _run(eng, x, stub, ex_cd, next_action_after):\n"
    "    confirm_peer_membership = stub.confirm\n"
    "    send_not_joined_reminder = stub.send_rem\n"
    "    leave_link = stub.leave\n"
    "    reminder_delay = stub.reminder_delay\n"
    "    membership_check_delay = stub.check_delay\n"
    "    watch_delay_seconds = stub.watch_delay\n"
    "    warn_membership_check_broken = stub.warn\n"
    "    note = stub.note\n"
    "    check_gate = stub.gate\n"
    "    unk_fallback = stub.unk_fallback\n"
    # سنتینلِ «طرف قابلِ شناسایی نیست» + هشدارِ راهنمایش؛ بلوک‌های
    # استخراج‌شده از 95.py این دو نام را می‌خوانند.
    "    CHECK_NO_PEER = _CHECK_NO_PEER\n"
    "    warn_peer_unresolvable = _warn_no_peer\n"
    + "\n".join("    " + ln for ln in ded.splitlines())
    + "\n"
)
exec(pharness, ph)
run_periodic = ph["_run"]

eng8 = fresh_engine()
x8 = eng8.ex_cfg()
x8["enabled"] = True
rec8, _n = eng8.db.ex_add(8001, "@fresh", "@freshchan")
now8 = int(time.time())
eng8.db.ex_set(rec8["id"], status="joined", direction="out", peer_id=8001,
               joined_at=now8, last_check=now8,
               next_check=now8 - 5,      # «سررسید» — همان حالتِ باگ
               src_chat=111, src_msg=222)
cd8 = m.ExCooldown(gap_min=GAP, gap_max=GAP)
cd8.mark_done(rec8["id"], now=now8)     # یعنی همین الان جوین شده
stub8 = WStub(False)
stub8.gate = Gate()
asyncio.run(run_periodic(eng8, x8, stub8, cd8,
                         lambda rec, base=None: int(base)))
g8 = eng8.db.ex_get(rec8["id"])
print("S8 checked", stub8.checked, "sent", stub8.sent, "left", stub8.left,
      "next_check", g8["next_check"] - now8, "strikes", g8["strikes"])
check(stub8.checked == [], "۸: رکوردِ تازه‌جوین‌شده درجا چک نشد")
check(stub8.sent == [] and stub8.left == [],
      "۸: بدون چک، نه «نیومدی» رفت نه لفت (قبلاً هر دو درجا بود)")
check(g8["next_check"] > now8, "۸: چکِ بعدی به بعد از خنک‌کننده منتقل شد")
check(g8["strikes"] == 0, "۸: اخطارِ لفت بی‌دلیل ثبت نشد")

# بعد از گذشتنِ فاصله، همان رکورد واقعاً چک می‌شود
cd8b = m.ExCooldown(gap_min=0, gap_max=0)
cd8b.mark_done(rec8["id"], now=time.time() - 60)
eng8.db.ex_set(rec8["id"], next_check=int(time.time()) - 1, strikes=0)
stub8b = WStub(True)
stub8b.gate = Gate()
asyncio.run(run_periodic(eng8, x8, stub8b, cd8b,
                         lambda rec, base=None: int(base)))
print("S8b checked", stub8b.checked, "note", eng8.db.ex_get(rec8["id"])["note"])
check(stub8b.checked and stub8b.checked[0][1] == rec8["id"],
      "۸: بعد از فاصله، چک با شناسه‌ی رکورد انجام شد")
print("DONE 8 no instant check after join")


# ════════════════════════════════════════════════════════════
# ۹) رفتاری: حلقه‌ی یادآوری هم رکوردِ در صف را عقب می‌اندازد
# ════════════════════════════════════════════════════════════
a = src.find("# ── یادآوری عضو‌نشده: دو پیام «نیومدی»")
b = src.find("# ۳) چک دوره‌ای", a)
assert a > 0 and b > a, "reminder loop markers missing"
lines = src[a:b].splitlines()
while lines and (lines[0].lstrip().startswith("#") or not lines[0].strip()):
    lines.pop(0)
while lines and not lines[-1].strip():
    lines.pop()
ded = "\n".join(ln[IND:] if ln.startswith(" " * IND) else ln for ln in lines)
rh = {"m": m, "asyncio": asyncio, "time": time, "fa": m.fa,
      "_CHECK_NO_PEER": m.CHECK_NO_PEER, "_warn_no_peer": _warn_no_peer}
rharness = (
    "import time\n"
    "async def _run(eng, x, stub, ex_cd, next_action_after):\n"
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
    "    CHECK_NO_PEER = _CHECK_NO_PEER\n"
    "    warn_peer_unresolvable = _warn_no_peer\n"
    + "\n".join("    " + ln for ln in ded.splitlines())
    + "\n"
)
exec(rharness, rh)
run_reminder = rh["_run"]

eng9 = fresh_engine()
x9 = eng9.ex_cfg()
x9["enabled"] = True
now9 = int(time.time())
# رکوردِ الف: همین الان چک شده → باید معطل بماند
ra, _n = eng9.db.ex_add(9001, "@a", "@chana")
eng9.db.ex_set(ra["id"], status="pending", direction="in", peer_id=9001,
               reminders=1, src_chat=111, src_msg=222,
               next_reminder=now9 - 5)
# رکوردِ ب: تازه → نوبتش همین حالا اجرا می‌شود
rb, _n = eng9.db.ex_add(9002, "@b", "@chanb")
eng9.db.ex_set(rb["id"], status="pending", direction="in", peer_id=9002,
               reminders=1, src_chat=111, src_msg=222,
               next_reminder=now9 - 5)
cd9 = m.ExCooldown(gap_min=GAP, gap_max=GAP)
cd9.mark_done(ra["id"], now=now9)
stub9 = WStub(False)
stub9.gate = Gate()
asyncio.run(run_reminder(eng9, x9, stub9, cd9,
                         lambda rec, base=None: int(base)))
ga = eng9.db.ex_get(ra["id"])
gb = eng9.db.ex_get(rb["id"])
print("S9 sent", stub9.sent, "A reminders", ga["reminders"],
      "A next", ga["next_reminder"] - now9, "B reminders", gb["reminders"])
check(stub9.sent == [rb["id"]],
      "۹: فقط رکوردِ آزاد پیام گرفت؛ رکوردِ در خنک‌کننده معطل ماند")
check(ga["reminders"] == 1 and ga["next_reminder"] > now9,
      "۹: رکوردِ معطل شمارنده نسوزاند و نوبتش به آینده منتقل شد")
check(gb["reminders"] == 2, "۹: رکوردِ آزاد نوبتِ دومش را گرفت")
print("DONE 9 reminder loop respects the queue")


# ════════════════════════════════════════════════════════════
# ۱۰) مهاجرت تنظیم‌ها + دستورِ کاربر
# ════════════════════════════════════════════════════════════
old_cfg = {"_cfg_migrated_v2": True, "exchange": {
    "enabled": True, "reminder_min_sec": 5, "reminder_max_sec": 8,
    "check_min_sec": 5, "check_max_sec": 8,
}}
with open(m.SETTINGS_FILE, "w", encoding="utf-8") as f:
    json.dump(old_cfg, f, ensure_ascii=False)
st = m.Settings()
ox = st.data["exchange"]
print("MIG op_gap", ox.get("op_gap_min_sec"), ox.get("op_gap_max_sec"))
check(ox.get("op_gap_min_sec") == 15 and ox.get("op_gap_max_sec") == 20,
      "۱۰: نصبِ قدیمی هم کلیدهای صفِ عملکرد را با پیش‌فرض می‌گیرد")
os.remove(m.SETTINGS_FILE)

eng10 = fresh_engine()
out = eng10.exchange_cmd("فاصله عملکرد ۲۵ ۴۰")
x10 = eng10.ex_cfg()
print("CMD", x10.get("op_gap_min_sec"), x10.get("op_gap_max_sec"),
      "| reminder", x10.get("reminder_min_sec"), "| check", x10.get("check_min_sec"))
check(x10.get("op_gap_min_sec") == 25 and x10.get("op_gap_max_sec") == 40,
      "۱۰: «تبادل فاصله عملکرد ۲۵ ۴۰» بازه را ست می‌کند")
check(x10.get("reminder_min_sec") >= 25 and x10.get("check_min_sec") >= 25,
      "۱۰: کفِ فاصله‌ی یادآوری/چک هم با درخواست کاربر بالا می‌رود")
out2 = eng10.exchange_cmd("فاصله عملکرد")
check("25" in out2 and "40" in out2,
      "۱۰: بدون آرگومان، وضعیتِ فعلیِ صف نمایش داده می‌شود")
out3 = eng10.exchange_cmd("فاصله عملکرد ۳۰")
check(eng10.ex_cfg().get("op_gap_min_sec") == 30
      and eng10.ex_cfg().get("op_gap_max_sec") == 30,
      "۱۰: یک عدد = بازه‌ی ثابت (عدد فارسی هم خوانده می‌شود)")
check("تبادل فاصله عملکرد" in src[src.find("⏱ تنظیم تبادل"):src.find("🧠 تطبیقی هوشمند")],
      "۱۰: دستور در راهنما هم آمده")
check("صف تک‌عملکردی" in eng10.permanent_check_status_text(),
      "۱۰: وضعیتِ چک دائمی هم صف را گزارش می‌کند")
print("DONE 10 migration + command")


# ════════════════════════════════════════════════════════════
# ۱۱) چکِ دومِ تأییدی، نوبتِ کاملِ صف نمی‌خورد (توان نصف نمی‌شود)
# ════════════════════════════════════════════════════════════
a = src.find("    async def confirm_peer_membership")
b = src.find("    async def join_link", a)
assert a > 0 and b > a, "confirm_peer_membership not found"
cf = "\n".join(ln[4:] if ln.startswith("    ") else ln
               for ln in src[a:b].splitlines())

REQS = []
cd11 = m.ExCooldown(gap_min=GAP, gap_max=GAP)


async def pimc(uid, rec_id=None, queue=True):
    # تابعِ واقعیِ چک از صف رد می‌شود؛ اینجا فقط «نوبت خوردن» را می‌شماریم.
    if queue:
        await cd11.action("check", rec_id, lambda: REQS.append(("queued", time.time())))
    else:
        async with cd11.lock:
            REQS.append(("continuation", time.time()))
            cd11.note_done(rec_id)
    return False


cns = {"eng": eng, "asyncio": asyncio, "time": time, "ex_cd": cd11,
       "peer_in_my_channel": pimc, "membership_check_delay": lambda: 1}
exec(cf, cns)
confirm = cns["confirm_peer_membership"]

t11 = time.time()
got = asyncio.run(confirm(4242, rec_id=55))
el11 = time.time() - t11
print("S11 result", got, "reqs", [k for k, _ in REQS], "elapsed %.2f" % el11)
check(got is False and len(REQS) == 2, "۱۱: منفی با دو درخواست تأیید شد")
check([k for k, _ in REQS] == ["queued", "continuation"],
      "۱۱: چکِ دوم در صف نوبتِ تازه نگرفت (ادامه‌ی همان عملکرد است)")
check(el11 < 2 * GAP,
      "۱۱: یک بررسیِ عضویت دو فاصله‌ی کامل صف نمی‌خورد (توان نصف نشد)")
check(cd11.since_done(55) is not None and cd11.since_done(55) < 1.0,
      "۱۱: خنک‌کننده‌ی رکورد بعد از چکِ دوم هم ثبت شد")
print("DONE 11 confirmation is one op")


# ════════════════════════════════════════════════════════════
# ۱۲) سناریوی گزارش‌شده: جوین → چکِ عضویت → «نیومدی» (دیگر درجا نیست)
# ════════════════════════════════════════════════════════════
eng12 = fresh_engine()
eng12.st.prof("standard")["channel"] = "@my_chan"
fake12 = FakeClient()
cd12 = m.ExCooldown(gap_min=GAP, gap_max=GAP)
ns12 = {"eng": eng12, "client": fake12, "DRY_RUN": False, "asyncio": asyncio,
        "time": time, "DEFAULT_MSG_NO": m.DEFAULT_MSG_NO, "ex_cd": cd12}
exec(fn_src, ns12)
send12 = ns12["send_not_joined_reminder"]
rec12, _n = eng12.db.ex_add(1201, "@buyer", "@buyerchan")
eng12.db.ex_set(rec12["id"], src_chat=111, src_msg=222)

TIMELINE = []


async def do_join():
    # جوینِ واقعی از صف رد می‌شود (همان مسیرِ join_link)
    await cd12.action("join", rec12["id"], lambda: TIMELINE.append(("join", time.time())))
    # زمان‌بندیِ چکِ بعد از جوین، دقیقاً مثل exchange_worker
    nxt = next_action_after({"id": rec12["id"]},
                            int(time.time()) + membership_check_delay())
    eng12.db.ex_set(rec12["id"], status="joined", joined_at=int(time.time()),
                    last_check=int(time.time()), next_check=nxt)
    return nxt


async def scenario():
    t0 = time.time()
    nxt = await do_join()
    t_join_done = time.time() - t0
    TIMELINE.append(("join_done_at", round(t_join_done, 2)))
    TIMELINE.append(("scheduled_check_in", nxt - int(time.time())))
    # ۱) چکِ عضویت: نوبتش درجا بعد از جوین نمی‌رسد
    r_now = eng12.db.ex_get(rec12["id"])
    okc, defer_c = cd12.defer_if_due(r_now, r_now["next_check"])
    TIMELINE.append(("check_allowed_now", okc, defer_c - int(time.time())))
    # ۲) «نیومدی» بلافاصله بعد از جوین → درجا نمی‌رود؛ اول فاصله را صبر می‌کند
    s1 = await send12(eng12.db.ex_get(rec12["id"]))
    TIMELINE.append(("reminder1_sent", s1, len(fake12.sent),
                     round(time.time() - t0, 2)))
    # ۳) «نیومدی» دوم، درجا پشتِ اولی نمی‌رود
    s2 = await send12(eng12.db.ex_get(rec12["id"]))
    g = eng12.db.ex_get(rec12["id"])
    TIMELINE.append(("reminder2_sent", s2, "sent", len(fake12.sent),
                     "next_in", g["next_reminder"] - int(time.time())))
    # ۴) بعد از گذشتنِ فاصله، هم چک مجاز است هم پیامِ دوم
    await asyncio.sleep(GAP + 0.6)
    okc2, _ = cd12.defer_if_due(eng12.db.ex_get(rec12["id"]), nxt)
    s3 = await send12(eng12.db.ex_get(rec12["id"]))
    TIMELINE.append(("after_gap", okc2, s3, "sent", len(fake12.sent)))
    return t0


t0 = asyncio.run(scenario())
for row in TIMELINE:
    print("S12", row)


def row(name):
    return [r for r in TIMELINE if r[0] == name][0]


check(row("scheduled_check_in")[1] >= int(GAP),
      "۱۲: چکِ «آیا واقعاً جوین شده؟» به بعد از فاصله زمان‌بندی شد (درجا نه)")
check(row("check_allowed_now")[1] is False
      and row("check_allowed_now")[2] >= int(GAP) - 1,
      "۱۲: چکِ درجا بعد از جوین رد شد و به بعد از فاصله منتقل شد")
r1 = row("reminder1_sent")
check(r1[1] is None and r1[2] == 0,
      "۱۲: «نیومدی» درجا بعد از جوین نرفت (باگِ گزارش‌شده) — رفت به نوبتِ بعد")
r2 = row("reminder2_sent")
check(r2[1] is None and r2[3] == 0,
      "۱۲: تلاشِ دوباره هم درجا پیام نفرستاد")
check(r2[5] >= 1,
      "۱۲: نوبتِ بعدی به زمانِ درست منتقل شد و شمارنده‌ی یادآوری نسوخت")
aft = row("after_gap")
check(aft[1] is True and aft[2] is True and aft[4] == 1,
      "۱۲: بعد از گذشتنِ فاصله، هم چک مجاز شد هم «نیومدی» رفت")
# پیامِ بعدی هم دوباره درجا پشتِ همین نمی‌رود
s4 = asyncio.run(send12(eng12.db.ex_get(rec12["id"])))
g12 = eng12.db.ex_get(rec12["id"])
print("S12b again", s4, "sent", len(fake12.sent), "next_in",
      g12["next_reminder"] - int(time.time()))
check(s4 is None and len(fake12.sent) == 1,
      "۱۲: «نیومدی» دوم درجا پشتِ اولی نرفت")
check(g12["next_reminder"] > int(time.time()),
      "۱۲: نوبتِ «نیومدی» دوم به آینده منتقل شد (حلقه سرِ وقت می‌فرستد)")
print("DONE 12 reported scenario")


# A concurrent operation can finish while this record waits for its cooldown.
# Its fresh global timestamp must not have the record wait subtracted twice.
async def concurrent_spacing_regression():
    cd = m.ExCooldown(gap_min=0.06, gap_max=0.06)
    cd.note_done(111)
    cd.last_global_done = 0
    times = []
    async def other():
        await asyncio.sleep(0.04)
        times.append(time.time())
    async def target():
        times.append(time.time())
    await asyncio.gather(cd.action("other", 222, other),
                         cd.action("target", 111, target))
    return times[1] - times[0]
check(asyncio.run(concurrent_spacing_regression()) >= 0.05,
      "رکورد منتظر، فاصله از پایان آخرین عملکرد را دوباره کم نمی‌کند")

async def flood_deadline_regression():
    cd = m.ExCooldown(gap_min=0, gap_max=0)
    class FloodWaitError(Exception):
        seconds = 30
    async def fail():
        raise FloodWaitError()
    try:
        await cd.action("reminder", 1, fail)
    except FloodWaitError:
        pass
    return cd.blocked_until - time.time()
check(asyncio.run(flood_deadline_regression()) >= 30,
      "فلود ارسال یادآوری سقف سراسری عملکردها را فعال می‌کند")

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
    env["PORT"] = "8231"
    env["JAFJ_PORT"] = "8231"
    for k in ("RAILWAY_ENVIRONMENT", "RAILWAY_SERVICE_ID", "RAILWAY_PROJECT_ID",
              "JAFJ_HOSTED", "JAFJ_LOGIN_RETRY", "BOT_TOKEN", "API_ID",
              "API_HASH", "BACKUP_CHAT", "BACKUP_EVERY"):
        env.pop(k, None)
    p = subprocess.run([sys.executable, "-c", DRIVER], cwd=APP, env=env,
                       capture_output=True, text=True, timeout=300)
    return p.stdout, p.stderr, p.returncode


def main():
    print("--- op_serialization: صف تک‌عملکردی + فاصله ۱۵–۲۰ ثانیه ---")
    reset()
    out, err, rc = run()
    if err.strip():
        print("--- driver stderr (tail) ---")
        print(err[-3000:])
    print("--- driver output ---")
    for line in out.splitlines():
        if line.startswith(("DEF", "S2", "S3", "S4", "S5", "S6", "S7", "S8",
                            "S9", "S11", "S12", "MIG", "CMD", "OK", "MISSING",
                            "FAIL", "FAILED", "DONE", "  -")):
            print(line)
    if "DONE PASS" in out and "FAIL" not in out and rc == 0:
        print("ALL: PASS")
        return True
    print("ALL: FAIL")
    return False


if __name__ == "__main__":
    sys.exit(0 if main() else 1)
