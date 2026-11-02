#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""لفت: پیدا کردنِ کانالِ طرف از میانِ **همه‌ی** دیالوگ‌ها.

باگی که این تست قفل می‌کند (گزارشِ کاربر: «اصلاً لفت نمی‌ده، می‌گه خودت
لفت بده»): وقتی لینکِ خصوصیِ طرف منقضی/باطل شود، تنها راهِ لفت «پیدا
کردنِ کانال از روی عنوان/آیدیِ ذخیره‌شده در دیالوگ‌ها» است. کد قبلی فقط
۳۰۰ دیالوگِ اول را می‌گشت؛ اکانتی که به سقفِ ۵۰۰ کانال خورده صدها دیالوگ
دارد، پس کانالِ طرف پیدا نمی‌شد، لفت شکست می‌خورد و پیامِ «دستی از کانال
خارج شو» می‌آمد.

قواعد:
  L1  تطبیق با عنوان حتی اگر کانال بعد از دیالوگِ ۳۰۰م باشد
  L2  تطبیق با chat_id ذخیره‌شده (بدونِ عنوان)
  L3  بعد از پیدا کردن، آیدی/هش روی رکورد ذخیره می‌شود (لفتِ بعدی بدونِ اسکن)
  L4  عنوانِ تکراری → هیچ لفتِ اشتباهی انجام نمی‌شود
  L5  پیدا نشدن → پیامِ صادقانه (دستی خارج شو) و رکورد left نمی‌شود
"""
import asyncio
import os
import sys
import tempfile
import time
from types import SimpleNamespace

HERE = os.path.dirname(os.path.abspath(__file__))
REPO = os.path.dirname(HERE)
SRC = os.path.join(REPO, "95.py")

text = open(SRC, encoding="utf-8").read()

a = text.find("    async def leave_link(link, rec_id=None):")
b = text.find("    async def cleanup_capacity_for_slots", a)
assert a > 0 and b > a, "leave_link پیدا نشد"
fn_src = "\n".join(ln[4:] if ln.startswith("    ") else ln
                   for ln in text[a:b].splitlines())

# ── ماژول را برای گرفتنِ کلاسِ DB واقعی لود می‌کنیم ──
ns_mod = {"__name__": "jafj_leave_scan", "__file__": SRC,
          "__builtins__": __builtins__}
exec(compile(text, SRC, "exec"), ns_mod)
DB = ns_mod["DB"]
FA = ns_mod["fa"]


# ── کلاس‌های خطا (هم‌نامِ مسیرِ واقعی) ──
class InviteHashExpiredError(Exception):
    pass


class InviteHashInvalidError(Exception):
    pass


class UserNotParticipantError(Exception):
    pass


class ChannelPrivateError(Exception):
    pass


class ChannelInvalidError(Exception):
    pass


class UsernameNotOccupiedError(Exception):
    pass


class UsernameInvalidError(Exception):
    pass


class FloodWaitError(Exception):
    seconds = 60


class LeaveChannelRequest:
    def __init__(self, ent):
        self.ent = ent


class ExCd:                     # صفِ تک‌عملکردی: بدونِ فاصله اجرا می‌کند
    blocked_until = 0.0

    async def action(self, kind, rec_id=None, fn=None, *args, **kw):
        if fn is None:
            return None
        return await fn(*args, **kw)


class FakeEng:
    def __init__(self, db):
        self.db = db
        self.st = SimpleNamespace(prof=lambda t: {"channel": "@mychan"})
        self.join_thr = SimpleNamespace(penalize=lambda w: None)
        self.logs = []

    def log(self, lvl, kind, detail=""):
        self.logs.append((lvl, kind, detail))

    def adaptive_on_flood(self, w):
        pass


class FakeClient:
    def __init__(self, dialogs=(), get_entity_error=None):
        self.dialogs = list(dialogs)
        self.get_entity_error = get_entity_error
        self.leaves = []
        self.entity_calls = []
        self.scanned = 0

    async def get_entity(self, link):
        self.entity_calls.append(link)
        if self.get_entity_error:
            raise self.get_entity_error
        return SimpleNamespace(id=-100999, access_hash=7, title="t")

    async def __call__(self, req):
        if isinstance(req, LeaveChannelRequest):
            self.leaves.append(req.ent)
            return True
        raise AssertionError("unexpected request %r" % (req,))

    def iter_dialogs(self, limit=None):
        # مثلِ تلگرام: اگر limit داده شود فقط همان تعداد اول برگردانده
        # می‌شود. این‌طور تست واقعاً نشان می‌دهد `limit=300` کانالِ طرف را
        # از دست می‌دهد (باگِ گزارش‌شده) و اسکنِ کامل پیدایش می‌کند.
        async def gen():
            for d in (self.dialogs if limit is None else self.dialogs[:limit]):
                self.scanned += 1
                yield d
        return gen()


def dialog(cid, title, username=None):
    return SimpleNamespace(entity=SimpleNamespace(
        id=cid, access_hash=1000 + cid, title=title, username=username))


FAILS = []


def check(name, ok, extra=""):
    if ok:
        print("PASS", name)
    else:
        FAILS.append(name)
        print("FAIL", name, "" if extra == "" else "→ %r" % (extra,))


def make_leave():
    """نسخه‌ی اجراییِ leave_link با وابستگی‌های شبیه‌سازی‌شده."""
    holder = {}

    def remember_channel(rec_id, ent):
        if not rec_id or ent is None:
            return
        cid = getattr(ent, "id", None)
        chash = getattr(ent, "access_hash", None)
        if not cid:
            return
        holder["eng"].db.ex_set(int(rec_id), chat_id=int(cid),
                                chat_hash=(int(chash) if chash is not None else None))

    def _input_channel(cid, chash=None):
        return SimpleNamespace(id=int(cid), access_hash=int(chash or 0))

    ns = {
        "DRY_RUN": False, "eng": None, "client": None,
        "ex_cd": ExCd(), "remember_channel": remember_channel,
        "_input_channel": _input_channel,
        "LeaveChannelRequest": LeaveChannelRequest,
        "InviteHashExpiredError": InviteHashExpiredError,
        "InviteHashInvalidError": InviteHashInvalidError,
        "UserNotParticipantError": UserNotParticipantError,
        "ChannelPrivateError": ChannelPrivateError,
        "ChannelInvalidError": ChannelInvalidError,
        "UsernameNotOccupiedError": UsernameNotOccupiedError,
        "UsernameInvalidError": UsernameInvalidError,
        "FloodWaitError": FloodWaitError,
        "time": time, "SimpleNamespace": SimpleNamespace,
        "secs": ns_mod["secs"], "fa": FA,
    }
    exec(fn_src, ns)
    return ns, holder


def fresh_db():
    d = tempfile.mkdtemp(prefix="jafj_leave_scan_")
    return DB(os.path.join(d, "t.db"))


def new_rec(db, **kw):
    rec, _ = db.ex_add(9001, "@peer", kw.pop("link", "https://t.me/+expiredhash"))
    db.ex_set(rec["id"], status="joined", peer_id=9001, direction="in",
              next_reminder=0, joined_at=int(time.time()) - 600, **kw)
    return db.ex_get(rec["id"])


def run_case(dialogs, rec_kw, get_entity_error=InviteHashExpiredError("expired")):
    ns, holder = make_leave()
    db = fresh_db()
    rec = new_rec(db, **rec_kw)
    eng = FakeEng(db)
    client = FakeClient(dialogs, get_entity_error=get_entity_error)
    ns["eng"] = eng
    holder["eng"] = eng
    ns["client"] = client
    ok, err = asyncio.run(ns["leave_link"](rec["link"], rec["id"]))
    return db, rec, client, eng, ok, err


# ── L1: کانال بعد از دیالوگِ ۳۰۰م، تطبیق با عنوان ──
many = [dialog(-100500 - i, "کانال دیگر %d" % i) for i in range(350)]
many.append(dialog(-100777, "کانال طرف"))
many += [dialog(-100900 - i, "کانال اضافه %d" % i) for i in range(50)]
db, rec, client, eng, ok, err = run_case(
    many, {"channel_title": "کانال طرف"})
check("L1: لفت با تطبیقِ عنوان بعد از دیالوگِ ۳۵۰ انجام شد", ok is True, err)
check("L1: همه‌ی دیالوگ‌ها اسکن شدند (نه فقط ۳۰۰ تای اول)",
      client.scanned == len(many), (client.scanned, len(many)))
check("L1: درخواستِ لفت روی همان کانال رفت",
      len(client.leaves) == 1 and getattr(client.leaves[0], "id", None) == -100777,
      [getattr(x, "id", None) for x in client.leaves])

# ── L2: بدونِ عنوان، تطبیق با chat_id ──
db, rec, client, eng, ok, err = run_case(
    many, {"channel_title": None, "chat_id": -100777})
check("L2: با chat_id ذخیره‌شده (بدونِ عنوان) لفت انجام شد", ok is True, err)
check("L2: همان کانال درست انتخاب شد",
      len(client.leaves) == 1 and getattr(client.leaves[0], "id", None) == -100777)

# ── L3: هویت بعد از پیدا شدن ذخیره می‌شود ──
check("L3: chat_id روی رکورد ذخیره شد",
      int(db.ex_get(rec["id"]).get("chat_id") or 0) == -100777,
      db.ex_get(rec["id"]).get("chat_id"))
check("L3: access_hash هم ذخیره شد (برای لفتِ بعدی بدونِ اسکن)",
      int(db.ex_get(rec["id"]).get("chat_hash") or 0) == 1000 - 100777,
      db.ex_get(rec["id"]).get("chat_hash"))

# ── L4: عنوانِ تکراری → لفتِ اشتباه نده ──
dup = [dialog(-100501, "کانال طرف"), dialog(-100502, "کانال طرف")]
db, rec, client, eng, ok, err = run_case(dup, {"channel_title": "کانال طرف"})
check("L4: عنوانِ تکراری → لفت انجام نشد", ok is False and not client.leaves, err)
check("L4: رکورد همچنان joined ماند",
      db.ex_get(rec["id"])["status"] == "joined")

# ── L5: پیدا نشدن → پیامِ صادقانه ──
db, rec, client, eng, ok, err = run_case(
    [dialog(-100600, "یک کانالِ دیگر")], {"channel_title": "کانال طرف"})
check("L5: پیدا نشدن → ok=False", ok is False)
check("L5: پیام می‌گوید لینک منقضی است و راهِ دستی را می‌دهد",
      "منقضی" in err and "دستی" in err, err)
check("L5: رکورد left نشد", db.ex_get(rec["id"])["status"] == "joined")

# ── L6: تطبیق با آیدی حتی وقتی عنوان چیزِ دیگری است ──
odd = [dialog(-100777, "عنوانِ عوض‌شده")]
db, rec, client, eng, ok, err = run_case(
    odd, {"channel_title": "کانال طرف", "chat_id": -100777})
check("L6: تغییرِ عنوانِ کانال جلوی لفت را نمی‌گیرد (تطبیق با id)", ok is True, err)

# ── L7: اگر get_entity موفق شود، هویت ذخیره می‌شود ──
db, rec, client, eng, ok, err = run_case(
    [], {"channel_title": "کانال طرف"}, get_entity_error=None)
check("L7: مسیرِ get_entity بی‌خطا → لفت انجام شد", ok is True, err)
check("L7: هویت از همان مسیر هم ذخیره شد",
      int(db.ex_get(rec["id"]).get("chat_id") or 0) == -100999,
      db.ex_get(rec["id"]).get("chat_id"))

if FAILS:
    print("\nFAILED:", FAILS)
    sys.exit(1)
print("ALL PASS")
