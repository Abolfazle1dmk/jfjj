#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""«تعدادِ لفت/جذب آپدیت نمی‌شود» — شمارنده‌هایی که یک مسیر را می‌دیدند.

باگِ واقعی: ستونِ `peer_joined_at` (پایه‌ی «جذب موفق») فقط در **یک** مسیر
نوشته می‌شد — چکِ دوره‌ایِ نگهبانی. هر مسیرِ دیگری که عضویتِ طرف را تأیید
می‌کرد (پیامِ «جوین شدم» در پیوی، یا رکوردی که از قبل joined بود) بی‌صدا
رد می‌شد؛ نتیجه: تبادل انجام می‌شد ولی «جذب» همیشه صفر می‌ماند و «لفت»
هم معلوم نبود «چیزی نبوده» یا «گیر کرده».

این تست قفل می‌کند:
  ۱) `ex_mark_peer_joined` یک‌بار ثبت می‌کند (idempotent) و True/False درست
     برمی‌گرداند — پس پیامِ «تبادل کامل شد» هم دوباره نمی‌رود.
  ۲) آمارِ گزارش «جذب» و «لفت» و زمانِ آخرین‌ها را می‌دهد.
  ۳) پنلِ تبادل خودش «جذب امروز / لفت امروز / آخرین …» را نشان می‌دهد.
  ۴) هر سه مسیرِ تأییدِ عضویت از همان تابعِ مشترک رد می‌شوند.

اجرا: python3 tests/test_exchange_stats.py
"""
import importlib.util
import os
import sys
import tempfile
import time

HERE = os.path.dirname(os.path.abspath(__file__))
ROOT = os.path.dirname(HERE)
SRC = os.path.join(ROOT, "95.py")
FAILS = []


def check(name, ok, extra=""):
    if ok:
        print("PASS", name)
    else:
        FAILS.append(name)
        print("FAIL", name, "" if extra == "" else "→ %r" % (str(extra)[:300],))


TMP = tempfile.mkdtemp(prefix="jafj_exstats_")
os.environ["DATA_DIR"] = TMP
os.chdir(TMP)          # 95.py فایل‌هایش را در cwd می‌سازد

spec = importlib.util.spec_from_file_location("m95es", SRC)
m = importlib.util.module_from_spec(spec)
m.__file__ = SRC
spec.loader.exec_module(m)

src_text = open(SRC, encoding="utf-8").read()

db = m.DB(os.path.join(TMP, "t.db"))
now = int(time.time())

rec, _new = db.ex_add(555001, "@peer", "https://t.me/peerchan")
db.ex_set(rec["id"], direction="out", status="joined", joined_at=now)

# ── ۱) ثبتِ «طرف برگشت» ─────────────────────────────────────────────
first = db.ex_mark_peer_joined(rec["id"], now)
check("جذب: اولین تأیید ثبت می‌شود", first is True, first)
check("جذب: ستون پر شد",
      int((db.ex_get(rec["id"]) or {}).get("peer_joined_at") or 0) == now,
      db.ex_get(rec["id"]))
second = db.ex_mark_peer_joined(rec["id"], now + 60)
check("جذب: تأیید دوباره True نمی‌دهد (پیام تکرار نمی‌شود)", second is False,
      second)
check("جذب: زمانِ اول دست‌نخورده می‌ماند",
      int(db.ex_get(rec["id"])["peer_joined_at"]) == now,
      db.ex_get(rec["id"]).get("peer_joined_at"))
check("جذب: رکوردِ ناموجود → False", db.ex_mark_peer_joined(999999) is False)

# رکوردِ «in» (طرف از اول عضوِ کانال من بود) نباید «جذبِ پیش‌قدم» بسازد،
# وگرنه پیامِ «تبادل کامل شد» بی‌دلیل و تکراری می‌رفت.
rec_in, _ = db.ex_add(555002, "@peer2", "https://t.me/peerchan2")
# عمداً دو روز پیش: نباید آمارِ «امروز» را جابه‌جا کند.
db.ex_set(rec_in["id"], direction="in", status="joined", joined_at=now - 172800)
check("جذب: رکوردِ in ثبت نمی‌شود (شمارش با joined_at است)",
      db.ex_mark_peer_joined(rec_in["id"], now) is False)
check("جذب: رکوردِ in دست‌نخورده می‌ماند",
      not db.ex_get(rec_in["id"]).get("peer_joined_at"))

# ── ۲) آمار ─────────────────────────────────────────────────────────
db.log("info", "ex_left", "#x https://t.me/x")
db.log("warn", "ex_leave_fail", "#y")     # لفتِ ناموفق نباید شمرده شود
day_start = int(time.mktime(time.localtime()[:3] + (0, 0, 0, 0, 0, -1)))
c = db.ex_report_counts(day_start)
check("آمار: جذب ۱ نفر", c["in_joined"] == 1, c)
check("آمار: لفت ۱ (لفتِ ناموفق شمرده نمی‌شود)", c["left"] == 1, c)
check("آمار: جوین امروز ۱", c["joined"] == 1, c)
check("آمار: زمانِ آخرین جذب را می‌دهد",
      int(c["last_peer_join"]) == now, c.get("last_peer_join"))
check("آمار: زمانِ آخرین لفت را می‌دهد",
      int(c["last_left"]) > 0, c.get("last_left"))
check("آمار: بدونِ فعالیت → last = ۰ (نه None)",
      db.ex_last_ts()["last_join"] >= 0)

# ── ۳) پنلِ تبادل خودش اعداد را نشان می‌دهد ─────────────────────────
check("when_fa: صفر → «هرگز»", m.when_fa(0) == "هرگز", m.when_fa(0))
check("when_fa: زمانِ واقعی خوانا است", ":" in m.when_fa(now), m.when_fa(now))

eng = m.Engine()
eng.db = db
panel = eng.exchange_text()
check("پنل: «جذب امروز» را نشان می‌دهد", "جذب امروز" in panel, panel[:400])
check("پنل: «لفت امروز» را نشان می‌دهد", "لفت امروز" in panel, panel[:400])
check("پنل: عددِ جذب درست است", "۱ نفر" in panel, panel[:600])
check("پنل: «آخرین لفت» را نشان می‌دهد", "آخرین لفت" in panel, panel[:600])

report = eng.ex_report_text()
check("گزارش: خطِ «آخرین جذب/لفت» دارد",
      "آخرین جذب" in report and "آخرین لفت" in report, report)
_line = [ln for ln in report.splitlines() if "جذب موفق تبادل:" in ln]
_num = (_line[0].split("جذب موفق تبادل:")[1].strip().split() or ["?"])[0] \
    if _line else "?"
check("گزارش: جذب = ۱ (ارقام فارسی یا لاتین)", _num in ("1", "۱"), _line)
check("گزارش: لفت = ۱",
      any(ln.split(":")[-1].strip().split()[0] in ("1", "۱")
          for ln in report.splitlines() if "لفت‌داده‌شده:" in ln), report)

# ── ۴) همه‌ی مسیرها از یک تابع رد می‌شوند ──────────────────────────
uses = src_text.count("ex_mark_peer_joined(")
check("۹۵: حداقل ۴ نقطه (تعریف + سه مسیر) از تابعِ مشترک استفاده می‌کند",
      uses >= 4, uses)
check("۹۵: مسیرِ پیامِ «جوین شدم» هم ثبت می‌کند",
      "تأیید شد؛ قبلاً همین مسیر بی‌صدا رد" in src_text)
check("۹۵: مسیرِ عضویتِ تأییدشده هم ثبت می‌کند",
      "عضویت همین حالا تأیید شد → «جذب»" in src_text)
check("۹۵: چکِ دوره‌ای هم از همان تابع استفاده می‌کند",
      'if eng.db.ex_mark_peer_joined(rec["id"], now):' in src_text)

print()
if FAILS:
    print("FAILED:", len(FAILS))
    sys.exit(1)
print("ALL PASS")
