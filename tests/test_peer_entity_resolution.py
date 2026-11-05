#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""«ValueError: Could not find the input entity for PeerUser(user_id=…)»

این خطا همان چیزی بود که در گزارشِ اکانتِ فعال دیده می‌شد، همراهِ:

  🕵️ بررسی عضویت مدتی است نامشخص می‌ماند …
  🔎 آخرین علتِ واقعی: ValueError: Could not find the input entity for
     PeerUser(user_id=8256797999) … روی چکِ https://t.me/+GM3JbyFfxRo3OWRk

ریشه (کدِ قدیمی): چکِ عضویت با `GetParticipantRequest(channel, user_id)` و
**آیدیِ خام** انجام می‌شد. Telethon برای آیدیِ خام باید از کشِ entity در
سشن جواب بگیرد؛ بعد از لاگینِ دوباره/بازسازیِ سشن آن کش خالی است و همان
رکورد تا ابد «نامشخص» می‌ماند — «اول کار می‌داد، بعد این‌جوری شد».

این تست قفل می‌کند:
  P1  `_input_user`: بدونِ access_hash هیچ InputPeerUser ساخته نمی‌شود
  P2  ستون‌های هویتِ طرف (`peer_hash`/`peer_username`) در دیتابیس و مهاجرت
  P3  `ex_add` هویت را از اول ذخیره می‌کند (و `@` را برمی‌دارد)
  P4  `ex_note_peer` هویت را روی رکوردهای موجود پر می‌کند، مقدارِ موجود را
      عوض نمی‌کند، رکوردِ rejected را دست نمی‌زند و دوباره‌کاری نمی‌کند
  P5  `CHECK_NO_PEER` از «نمی‌دانم» و «نرفت» جدا است
  P6  سیم‌کشی: درخواست با `upeer` ساخته می‌شود (نه آیدیِ خام)، هویتِ هر پیام
      ذخیره می‌شود، و هر سه مصرف‌کننده‌ی نتیجه، `CHECK_NO_PEER` را جدا
      مدیریت می‌کنند (بدونِ لفتِ بی‌تأیید و بدونِ شمارنده‌ی نامشخص)
  P7  خلاصه‌ی شکست‌های لفت: علت‌ها گروه‌بندی می‌شوند، نه «۶ تلاش ناموفق»
  P8  لفت با هویتِ کهنه: یک‌بار با لینک حل می‌شود (`ex_leave_refresh`)
"""
import asyncio
import importlib.util
import os
import shutil
import tempfile
import time
from types import SimpleNamespace

HERE = os.path.dirname(os.path.abspath(__file__))
REPO = os.path.dirname(HERE)
SRC_PATH = os.path.join(REPO, "95.py")

FAILS = []


def check(name, cond, extra=""):
    print(("PASS " if cond else "FAIL ") + name
          + (f"   [{extra}]" if extra and not cond else ""))
    if not cond:
        FAILS.append(name)


def main():
    root = tempfile.mkdtemp(prefix="jafj_peer_entity_")
    os.environ["DATA_DIR"] = root
    os.environ.setdefault("PORT", "8481")
    os.environ.pop("JAFJ_ONLY", None)
    try:
        spec = importlib.util.spec_from_file_location("m95peer", SRC_PATH)
        m = importlib.util.module_from_spec(spec)
        m.__file__ = SRC_PATH
        spec.loader.exec_module(m)
        SRC = open(SRC_PATH, encoding="utf-8").read()

        # ── P1: _input_user ────────────────────────────────────────────
        check("P1: بدونِ access_hash هیچ peer ساخته نمی‌شود",
              m._input_user(8256797999, None) is None
              and m._input_user(8256797999, 0) is None)
        check("P1: آیدیِ نامعتبر → None",
              m._input_user("x", 123) is None and m._input_user(0, 123) is None)
        peer = m._input_user(8256797999, 123456789)
        check("P1: با access_hash یک InputPeerUser می‌سازد",
              peer is not None
              and int(getattr(peer, "user_id", 0)) == 8256797999
              and int(getattr(peer, "access_hash", 0)) == 123456789, peer)
        check("P1: شناسه‌ی متنی هم قبول است",
              m._input_user("8256797999", "42") is not None)

        # ── P2: ستون‌ها ────────────────────────────────────────────────
        check("P2: ستون peer_hash در ساختِ جدول هست",
              "peer_hash INTEGER" in SRC)
        check("P2: ستون peer_username در ساختِ جدول هست",
              "peer_username TEXT" in SRC)
        mig = SRC[SRC.index("PRAGMA table_info(exchange)"):]
        mig = mig[:mig.index("CREATE INDEX")]
        check("P2: مهاجرتِ دیتابیسِ قدیمی هر دو ستون را اضافه می‌کند",
              '"peer_hash"' in mig and '"peer_username"' in mig)

        # ── P3/P4: DB ──────────────────────────────────────────────────
        db = m.DB(os.path.join(root, "peer.db"))
        rec, fresh = db.ex_add(8256797999, "طرف", "https://t.me/+GM3JbyFfxRo3OWRk",
                               peer_hash=987654321, peer_username="@SomeOne")
        check("P3: رکوردِ تازه ساخته شد", fresh and rec and rec["id"])
        r = db.ex_get(rec["id"])
        check("P3: access_hash ذخیره شد", int(r.get("peer_hash") or 0) == 987654321, r)
        check("P3: یوزرنیم بدونِ @ ذخیره شد",
              (r.get("peer_username") or "") == "SomeOne", r)

        # رکوردِ قدیمی: بدونِ هویت
        old, _ = db.ex_add(1111, "قدیمی", "@old_chan")
        check("P3: رکوردِ قبلی بدونِ هویت است",
              not (db.ex_get(old["id"]).get("peer_hash")))
        n = db.ex_note_peer(1111, 5555, "olduser")
        rr = db.ex_get(old["id"])
        check("P4: ex_note_peer هویتِ رکوردِ قدیمی را پر می‌کند",
              n == 1 and int(rr.get("peer_hash") or 0) == 5555
              and (rr.get("peer_username") or "") == "olduser", (n, rr))
        n2 = db.ex_note_peer(1111, 9999, "newname")
        check("P4: هویتِ موجود بازنویسی نمی‌شود",
              int(db.ex_get(old["id"]).get("peer_hash") or 0) == 5555)
        check("P4: تکرارِ همان طرف دوباره‌کاری نمی‌کند", n2 == 0, n2)
        check("P4: ورودیِ خالی/خراب خطا نمی‌دهد",
              db.ex_note_peer(None, 1, "x") == 0
              and db.ex_note_peer("abc", 1, "x") == 0
              and db.ex_note_peer(1111, None, None) == 0)
        rej, _ = db.ex_add(2222, "رد شده", "@rejected_chan")
        db.ex_set(rej["id"], status="rejected")
        db.ex_note_peer(2222, 7777, "rejuser")
        check("P4: رکوردِ rejected دست‌کاری نمی‌شود",
              not (db.ex_get(rej["id"]).get("peer_hash")))

        # ── P4b: شمارشِ طرف‌های بدونِ هویت (خطِ /diag) ────────────────
        before = db.ex_peer_missing_count()
        bare, _ = db.ex_add(3333, "بی‌هویت", "@bare_chan")
        check("P4b: رکوردِ تازه بدونِ هویت شمرده می‌شود",
              db.ex_peer_missing_count() == before + 1,
              db.ex_peer_missing_count())
        db.ex_note_peer(3333, 31415, "bareuser")
        check("P4b: بعد از ذخیره‌ی هویت از شمارش کم می‌شود",
              db.ex_peer_missing_count() == before, db.ex_peer_missing_count())
        check("P4b: خطِ /diag برای همین حالت هست",
              "ex_peer_missing_count()" in SRC
              and "طرف‌های بدونِ هویت" in SRC)

        # ── P5: سنتینل ─────────────────────────────────────────────────
        check("P5: CHECK_NO_PEER از CHECK_DEFERRED جدا است",
              m.CHECK_NO_PEER is not m.CHECK_DEFERRED
              and m.CHECK_NO_PEER is not None
              and repr(m.CHECK_NO_PEER) == "CHECK_NO_PEER")
        check("P5: CHECK_NO_PEER با True/False یکی نیست",
              not (m.CHECK_NO_PEER is True) and not (m.CHECK_NO_PEER is False))

        # ── P6: سیم‌کشی ────────────────────────────────────────────────
        check("P6: درخواستِ عضویت با peerِ حل‌شده ساخته می‌شود",
              "GetParticipantRequest(channel_peer, upeer)" in SRC
              and "GetParticipantRequest(channel_peer, user_id)" not in SRC)
        check("P6: هر پیام هویتِ طرف را ذخیره می‌کند",
              "save_peer_identity(sender)" in SRC)
        check("P6: ترتیبِ حلِ هویت (hash → کش → یوزرنیم → دیالوگ)",
              "async def partner_input_peer" in SRC
              and "_input_user(uid, uhash)" in SRC
              and "await scan_dialogs_for_peer(client, eng, uid)" in SRC)
        check("P6: حل‌نشدنِ هویت «نامشخص» حساب نمی‌شود",
              SRC.count("still is CHECK_NO_PEER") == 2
              and SRC.count("_conf is CHECK_NO_PEER") == 2)
        check("P6: لفتِ بی‌تأیید برای طرفِ ناشناس انجام نمی‌شود",
              "لفت معلق — طرف قابلِ شناسایی نیست" in SRC)
        check("P6: هشدارِ جدا و راهنما برای این حالت هست",
              "async def warn_peer_unresolvable" in SRC
              and "Could not find the input entity" in SRC)
        check("P6: شمارنده‌ی «نامشخص» برای این حالت نمی‌سوزد",
              "unk_streak=int(rec.get(\"unk_streak\") or 0) + 1,\n"
              not in SRC.split("CHECK_NO_PEER")[1][:4000])

        # ── P6b: رفتارِ واقعیِ partner_input_peer ────────────────────
        def run(coro):
            return asyncio.new_event_loop().run_until_complete(coro)

        class FakeEnt:
            def __init__(self, uid, ah, uname=None):
                self.id, self.access_hash, self.username = uid, ah, uname

        class FakeClient:
            def __init__(self, inputs=None, named=None, dialogs=None,
                         boom=None):
                self._inputs = inputs or {}
                self._named = named or {}
                self._dialogs = dialogs or []
                self._boom = boom

            async def get_input_entity(self, uid):
                if self._boom:
                    raise ValueError(
                        "Could not find the input entity for "
                        "PeerUser(user_id=%s)" % uid)
                if int(uid) in self._inputs:
                    return self._inputs[int(uid)]
                raise ValueError("not cached")

            async def get_entity(self, name):
                if name in self._named:
                    return self._named[name]
                raise ValueError("no such user")

            async def iter_dialogs(self, limit=None):
                for e in self._dialogs:
                    yield SimpleNamespace(entity=e)

        def fake_eng():
            saved = []
            return SimpleNamespace(
                log=lambda *a, **k: None,
                db=SimpleNamespace(ex_note_peer=lambda *a:
                                   (saved.append(a), 1)[1]),
                saved=saved)

        # ۴) access_hashِ رکورد → بدونِ هیچ درخواستی به کلاینت
        eng1 = fake_eng()
        got, why = run(m.partner_input_peer(FakeClient(), eng1, 8256797999,
                                           {"peer_id": 8256797999,
                                            "peer_hash": 4242}))
        check("P6b: access_hashِ رکورد بدونِ درخواست به تلگرام استفاده می‌شود",
              getattr(got, "access_hash", None) == 4242 and why == "", (got, why))
        # کشِ سشن
        eng2 = fake_eng()
        got, _why = run(m.partner_input_peer(
            FakeClient(inputs={8256797999: "cached"}), eng2, 8256797999))
        check("P6b: کشِ سشن دومی است", got == "cached", got)
        # یوزرنیمِ ذخیره‌شده، وقتی کش خالی است
        eng3 = fake_eng()
        got, _why = run(m.partner_input_peer(
            FakeClient(named={"@SomeOne": FakeEnt(8256797999, 777, "SomeOne")}),
            eng3, 8256797999,
            {"peer_id": 8256797999, "peer_username": "SomeOne"}))
        check("P6b: یوزرنیمِ ذخیره‌شده حل می‌کند و هویت را ذخیره می‌کند",
              getattr(got, "access_hash", None) == 777
              and eng3.saved
              and eng3.saved[0][1] == 777, (got, eng3.saved))
        # اسکنِ دیالوگ‌ها
        eng4 = fake_eng()
        got, _why = run(m.partner_input_peer(
            FakeClient(dialogs=[FakeEnt(5, 1), FakeEnt(8256797999, 909)]),
            eng4, 8256797999))
        check("P6b: آخرین راه، اسکنِ دیالوگ‌هاست",
              getattr(got, "access_hash", None) == 909, got)
        # هیچ‌کدام → دلیلِ روشن، نه Noneِ بی‌توضیح
        got, why = run(m.partner_input_peer(FakeClient(boom=True), fake_eng(),
                                           8256797999))
        check("P6b: ناشناسِ کامل → (None, دلیل) برای CHECK_NO_PEER",
              got is None and "قابلِ شناسایی نیست" in why, (got, why))
        check("P6b: آیدیِ خالی/خراب خطا نمی‌دهد",
              run(m.partner_input_peer(FakeClient(), fake_eng(), 0))[0] is None)

        # ── P7: خلاصه‌ی شکست‌ها ───────────────────────────────────────
        reasons = ["FloodWait 63s", "TimeoutError: عملکرد «leave»",
                   "TimeoutError: عملکرد «leave»", "لینک خصوصی منقضی/نامعتبر "
                   "از روی پیش‌نمایش قابل لفت نیست"]
        summ = m.summarize_failures(reasons)
        check("P7: علت‌های تکراری گروه‌بندی می‌شوند",
              summ and summ[0].startswith("2×") and "TimeoutError" in summ[0], summ)
        check("P7: هر علتِ یکتا هم دیده می‌شود",
              any("FloodWait" in x for x in summ), summ)
        check("P7: سقفِ تعداد خطوط رعایت می‌شود",
              len(summ) <= 4, summ)
        note0 = m.format_capacity_cleanup_note(
            [], 3, "سقفِ زمانیِ دور پاکسازی (120s)", failed_count=6,
            failed_reasons=reasons)
        check("P7: پیامِ «هیچ لفتی انجام نشد» علت‌ها را می‌آورد",
              "2×" in note0 and "TimeoutError" in note0, note0)
        check("P7: توقفِ زمانیِ دور هم در پیام می‌آید",
              "زودتر تمام شد" in note0 and "120s" in note0, note0)
        note_ok = m.format_capacity_cleanup_note(["@a", "@b"], 3)
        check("P7: پیامِ موفقیت مثل قبل می‌ماند",
              "2 کانالِ جفج‌زده لفت دادم" in note_ok and "علت‌ها" not in note_ok,
              note_ok)

        # ── P8: هویتِ کهنه در لفت ────────────────────────────────────
        check("P8: لفت با هویتِ کهنه یک‌بار با لینک دوباره تلاش می‌کند",
              "ex_leave_refresh" in SRC
              and "async def _leave_with" in SRC
              and "fresh = await client.get_entity(link)" in SRC)
    finally:
        db = locals().get("db")
        try:
            if db is not None:
                db.conn.close()
        except Exception:
            pass
        shutil.rmtree(root, ignore_errors=True)

    print()
    if FAILS:
        print("FAILED:", ", ".join(FAILS))
        return 1
    print("ALL PASS")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
