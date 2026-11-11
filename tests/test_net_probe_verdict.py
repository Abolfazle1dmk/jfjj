#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""«۹۵.py اجرا شد ولی پنل نیامد» — مقصر میزبان است یا کد؟

مشکلی که این تست می‌گیرد
────────────────────────
گزارشِ واقعیِ کاربر: «وقتی ران می‌کنم می‌گه ران شد، ولی نه داخلِ Saved
Messages پیامی می‌آید نه وقتی `پنل` را می‌فرستم اتفاقی می‌افتد.»

بازسازیِ همان حالت در یک کانتینر نشان داد علت معمولاً **شبکه‌ی میزبان** است
(پورتِ TCP باز می‌شود ولی دست‌دادنِ MTProto کامل نمی‌شود — پروکسیِ شفاف یا
DPI اتصال را می‌بندد). اما کد هیچ اثری از آن نمی‌گذاشت:

  • مسیرِ شکستِ اتصال در `connect_and_run` فقط یک `print` داشت و
    `"retry"` برمی‌گرداند؛ نه `_boot_step` صدا زده می‌شد نه
    `record_boot_crash`.
  • نتیجه: `jafj_boot.log` تا ابد روی «شروعِ اتصال به تلگرام» می‌ماند و
    `jafj_boot_error.txt` هرگز نوشته نمی‌شد — همان دو فایلی که صفحه‌ی وضعیتِ
    `main.py` و `tools/doctor_fa.py` می‌خوانند.
  • یعنی کاربرِ بدونِ ترمینال هیچ راهی نداشت بفهمد مقصر کانتینر است یا کد.

حالا:
  • `_boot_note()` هر شکست را **بدونِ حذفِ تکراری** در ردیِ بوت می‌نویسد
    (`_boot_step` عمداً تکراری‌ها را حذف می‌کند، پس برای حلقه‌ی retry
    به درد نمی‌خورد).
  • اولین شکستِ «شبکه‌ای» یک پروبِ DNS+TCP به DCهای تلگرام می‌زند، خطای
    واقعی را طبقه‌بندی می‌کند و رأیِ «مقصر کیست» را در
    `jafj_boot_error.txt` می‌گذارد.
  • `tools/doctor_fa.py` و صفحه‌ی وضعیتِ `deploy/wispbyte/main.py` همان
    پروب را دارند و نتیجه‌اش را با ردیِ بوتِ خودِ سلف مقایسه می‌کنند.

نکته‌ی کلیدی که این تست قفل می‌کند: **باز بودنِ TCP به‌تنهایی «سالم» نیست.**
پس رأی فقط از ترکیبِ «پروبِ TCP» + «شکستِ واقعیِ خودِ سلف» ساخته می‌شود.

اجرا: python3 tests/test_net_probe_verdict.py  → باید `ALL: PASS` بدهد.
"""
import importlib.util
import os
import shutil
import sys
import tempfile

HERE = os.path.dirname(os.path.abspath(__file__))
ROOT = os.path.dirname(HERE)
SRC = os.path.join(ROOT, "95.py")
DOCTOR = os.path.join(ROOT, "tools", "doctor_fa.py")
WISP = os.path.join(ROOT, "deploy", "wispbyte", "main.py")

FAILS = []


def check(name, ok, extra=""):
    if ok:
        print("PASS", name)
    else:
        FAILS.append(name)
        print("FAIL", name, "" if extra == "" else "→ %r" % (extra,))


spec = importlib.util.spec_from_file_location("m95net", SRC)
m = importlib.util.module_from_spec(spec)
m.__file__ = SRC
spec.loader.exec_module(m)

work = tempfile.mkdtemp(prefix="jafj_net_")
old_cwd = os.getcwd()


def in_tmp(fn):
    def wrapper(*a, **kw):
        os.chdir(work)
        try:
            return fn(*a, **kw)
        finally:
            os.chdir(old_cwd)
    return wrapper


class FakeSocket:
    """جای‌گزینِ `socket` تا پروب به شبکه‌ی واقعیِ ماشینِ آزمون وابسته نباشد.

    `open_tcp=True`  → اتصال قبول می‌شود (پورت «باز» دیده می‌شود)
    `open_tcp=False` → همه‌ی تلاش‌ها خطا می‌دهند (میزبان راه را بسته)
    """

    IPPROTO_TCP = 6

    def __init__(self, open_tcp=True, dns_ok=True):
        self.open_tcp = open_tcp
        self.dns_ok = dns_ok
        self.attempts = 0

    def getaddrinfo(self, host, port, **kw):
        if not self.dns_ok:
            raise OSError("DNS شکست خورد")
        return [(2, 1, 6, "", ("1.2.3.4", port))]

    def create_connection(self, addr, timeout=None):
        self.attempts += 1
        if not self.open_tcp:
            raise OSError("network is unreachable")
        return _FakeConn()


class _FakeConn:
    def close(self):
        pass


def use_socket(fake):
    """`socket` را در sys.modules عوض کن و تابعِ برگرداندنش را بده."""
    real = sys.modules.get("socket")
    sys.modules["socket"] = fake

    def restore():
        if real is None:
            sys.modules.pop("socket", None)
        else:
            sys.modules["socket"] = real
    return restore


# ── T1: _boot_note برخلافِ _boot_step تکراری‌ها را حذف نمی‌کند ──
@in_tmp
def _t1():
    log = os.path.join(work, "jafj_boot.log")
    if os.path.exists(log):
        os.remove(log)
    m._BOOT_SEEN.clear()
    m._boot_step("شروعِ اتصال به تلگرام")
    m._boot_step("شروعِ اتصال به تلگرام")       # تکراری: نباید بنشیند
    m._boot_note("شکستِ اتصال #1", "net")
    m._boot_note("شکستِ اتصال #2", "net")
    m._boot_note("شکستِ اتصال #3", "net")
    with open(log, encoding="utf-8") as f:
        lines = [ln for ln in f.read().splitlines() if ln.strip()]
    return lines


lines = _t1()
check("T1: _boot_step تکراری را حذف می‌کند",
      sum(1 for ln in lines if "شروعِ اتصال" in ln) == 1, lines)
check("T1: _boot_note هر سه شکست را می‌نویسد (حلقه‌ی retry ردی دارد)",
      sum(1 for ln in lines if "شکستِ اتصال" in ln) == 3, lines)
check("T1: هر خط pid و زمان دارد",
      all("pid=" in ln and ln[:4].isdigit() for ln in lines), lines)
check("T1: آخرین مرحله به‌روز می‌شود",
      "شکستِ اتصال #3" in m.boot_last_step(), m.boot_last_step())


# ── T2: طبقه‌بندیِ خطای واقعیِ اتصال ──
CASES = [
    ("IncompleteReadError", "0 bytes read on a total of 8 expected bytes", "net"),
    ("ConnectionError", "Server closed the connection", "net"),
    ("ConnectionResetError", "Connection reset by peer", "net"),
    ("TimeoutError", "timed out", "net"),
    ("OSError", "Network is unreachable", "net"),
    ("gaierror", "Name or service not known", "net"),
    ("AuthKeyDuplicatedError",
     "The authorization key (session file) was used under two different IP "
     "addresses simultaneously, and can no longer be used.", "auth"),
    ("SessionRevokedError", "The session has been revoked", "auth"),
    ("FloodWaitError", "A wait of 34 seconds is required", "flood"),
    ("RPCError", "API_ID_INVALID", "creds"),
    ("SomethingWeird", "no idea what happened", "?"),
]
bad = [(n, t, exp, m.classify_conn_error(n, t)[0])
       for n, t, exp in CASES if m.classify_conn_error(n, t)[0] != exp]
check("T2: هر خطای اتصال درست طبقه‌بندی می‌شود", not bad, bad)
_k, _why = m.classify_conn_error("IncompleteReadError", "0 bytes read")
check("T2: طبقه‌بندی توضیحِ فارسیِ قابل‌فهم می‌دهد", bool(_why.strip()), _why)


# ── T3/T4: رأیِ «مقصر کیست» ──
probe_open = {"dns": "ok", "open": 3, "closed": 0,
              "detail": ["DC2 149.154.167.51:443 باز"]}
probe_closed = {"dns": "ok", "open": 0, "closed": 3,
                "detail": ["DC2 149.154.167.51:443 بسته — OSError"]}
v_open = m.conn_verdict(probe_open, "IncompleteReadError: 0 bytes read", "net")
v_closed = m.conn_verdict(probe_closed, "OSError: unreachable", "net")

check("T3: TCP باز + شکستِ MTProto → مقصر میزبان (پروکسی/DPI)",
      "میزبان" in v_open and "کد سالم است" in v_open and "DPI" in v_open,
      v_open[:200])
check("T4: همه‌ی DCها بسته → صریح «میزبان راه را بسته»",
      "میزبان راهِ تلگرام را بسته" in v_closed and "کد سالم است" in v_closed,
      v_closed[:200])
check("T4: رأی IPهای لازم برای بازکردنِ فایروال را می‌دهد",
      all(ip in v_closed for _, ip in m.TELEGRAM_DCS), v_closed[:400])
v_auth = m.conn_verdict(probe_open, "AuthKeyDuplicated", "auth")
check("T3: خطای سشن به «شبکه» نسبت داده نمی‌شود",
      "لاگین" in v_auth and "بسته است" not in v_auth, v_auth[:200])


# ── T5: note_conn_fail ردیِ بوت و فایلِ خطا را واقعاً می‌نویسد ──
@in_tmp
def _t5(open_tcp=True):
    for n in ("jafj_boot.log", "jafj_boot_error.txt"):
        p = os.path.join(work, n)
        if os.path.exists(p):
            os.remove(p)
    m.CONN_STATE.update({"count": 0, "err": "", "kind": "", "probe": None})
    m._BOOT_SEEN.clear()
    fake = FakeSocket(open_tcp=open_tcp)
    restore = use_socket(fake)
    try:
        err = OSError("Server closed the connection: 0 bytes read")
        k1 = m.note_conn_fail(err, "بررسیِ سشن")
        k2 = m.note_conn_fail(err, "بررسیِ سشن")
        probe = dict(m.CONN_STATE.get("probe") or {})
    finally:
        restore()
    log = os.path.join(work, "jafj_boot.log")
    crash = os.path.join(work, "jafj_boot_error.txt")
    with open(log, encoding="utf-8") as f:
        log_txt = f.read()
    crash_txt = open(crash, encoding="utf-8").read() if os.path.isfile(crash) else ""
    return k1, k2, log_txt, crash_txt, probe, fake.attempts


k1, k2, log_txt, crash_txt, probe, attempts = _t5(open_tcp=True)
check("T5: شکست به «net» طبقه‌بندی شد", (k1, k2) == ("net", "net"), (k1, k2))
check("T5: هر دو شکست در jafj_boot.log نشست (قبلاً هیچ‌کدام نمی‌نشست)",
      "شکستِ اتصال #1" in log_txt and "شکستِ اتصال #2" in log_txt, log_txt[:300])
check("T5: jafj_boot_error.txt با رأیِ «میزبان» نوشته شد",
      "میزبان" in crash_txt and "کد سالم است" in crash_txt, crash_txt[:200])
check("T5: پروب فقط یک‌بار زده می‌شود (حلقه‌ی retry شبکه را بمباران نمی‌کند)",
      attempts == len(m.TELEGRAM_DCS), attempts)

k1b, k2b, log_b, crash_b, probe_b, attempts_b = _t5(open_tcp=False)
check("T5: وقتی همه‌ی DCها بسته‌اند رأی همان «میزبان» است",
      "میزبان راهِ تلگرام را بسته" in crash_b, crash_b[:200])


# ── T6: خودِ پروب هیچ‌وقت بوت را نمی‌خواباند ──
@in_tmp
def _t6():
    fake = FakeSocket(open_tcp=False, dns_ok=False)
    restore = use_socket(fake)
    try:
        return m.probe_telegram_net(timeout=0.05)
    finally:
        restore()


res = _t6()
check("T6: پروب با DNS و TCPِ خراب هم dict برمی‌گرداند (استثنا نمی‌دهد)",
      isinstance(res, dict) and res["open"] == 0
      and res["closed"] == len(m.TELEGRAM_DCS), res)
check("T6: شکستِ DNS هم گزارش می‌شود", res.get("dns") not in ("", "ok"), res)


# ── T7: دکترِ repo همین رأی را می‌دهد ──
dspec = importlib.util.spec_from_file_location("doctor_net", DOCTOR)
D = importlib.util.module_from_spec(dspec)
dspec.loader.exec_module(D)


@in_tmp
def _t7(open_tcp, with_conn_fails):
    log = os.path.join(work, "jafj_boot.log")
    with open(log, "w", encoding="utf-8") as f:
        f.write("2026-11-11 14:00:00 pid=1 شروعِ اتصال به تلگرام\n")
        if with_conn_fails:
            f.write("2026-11-11 14:00:05 pid=1 شکستِ اتصال #1 (بررسیِ سشن) "
                    "| net: IncompleteReadError: 0 bytes read\n")
    D.ROWS.clear()
    restore = use_socket(FakeSocket(open_tcp=open_tcp))
    try:
        D.check_network(here=work, timeout=0.05)
    finally:
        restore()
    return list(D.ROWS)


rows = _t7(open_tcp=True, with_conn_fails=True)
check("T7: دکتر — TCP باز ولی سلف شکست خورده → 🟥 مقصر میزبان",
      any(r[0] == D.RED and "MTProto" in r[1] and "میزبان" in r[1] for r in rows),
      [(r[0], r[1]) for r in rows])

rows = _t7(open_tcp=False, with_conn_fails=False)
check("T7: دکتر — هیچ DC باز نیست → 🟥 «میزبان راه را بسته»",
      any(r[0] == D.RED and "هیچ راهی به تلگرام نیست" in r[1] for r in rows),
      [(r[0], r[1]) for r in rows])

rows = _t7(open_tcp=True, with_conn_fails=False)
check("T7: دکتر — شبکه باز و بی‌شکست → 🟩 (به‌دروغ قرمز نمی‌کند)",
      any(r[0] == D.GRN and r[1] == "شبکه" for r in rows),
      [(r[0], r[1]) for r in rows])
check("T7: دکتر در حالتِ سالم هیچ 🟥 شبکه‌ای نمی‌دهد",
      not any(r[0] == D.RED and "شبکه" in r[1] for r in rows),
      [(r[0], r[1]) for r in rows])


# ── T8: صفحه‌ی وضعیت (جایِ ترمینال) هم همین را نشان می‌دهد ──
if os.path.isfile(WISP):
    wtmp = tempfile.mkdtemp(prefix="jafj_wisp_")
    try:
        shutil.copy(WISP, os.path.join(wtmp, "main.py"))
        os.makedirs(os.path.join(wtmp, "data", "clients", "999"), exist_ok=True)
        with open(os.path.join(wtmp, "data", "clients", "999", "jafj_boot.log"),
                  "w", encoding="utf-8") as f:
            f.write("2026-11-11 14:00:05 pid=1 شکستِ اتصال #1 | net: x\n")
        wspec = importlib.util.spec_from_file_location(
            "wisp_net", os.path.join(wtmp, "main.py"))
        W = importlib.util.module_from_spec(wspec)
        os.environ["DATA_DIR"] = os.path.join(wtmp, "data")
        saved = os.getcwd()
        try:
            wspec.loader.exec_module(W)          # ماژول os.chdir می‌کند
        finally:
            os.chdir(saved)

        @in_tmp
        def _t8(open_tcp):
            W._NET_CACHE.update({"at": 0.0, "res": None})
            restore = use_socket(FakeSocket(open_tcp=open_tcp))
            try:
                return W.status_payload()
            finally:
                restore()

        p = _t8(open_tcp=True)
        titles = [(r["level"], r["title"]) for r in p["checks"]]
        check("T8: صفحه‌ی وضعیت ردیفِ شبکه دارد",
              any("شبکه" in t for _, t in titles), titles)
        check("T8: با شکستِ سلف، صفحه 🟥 «میزبان» می‌دهد",
              any(lv == "red" and "میزبان" in t for lv, t in titles), titles)
        check("T8: نتیجه در JSON هم هست (?json=1)",
              isinstance(p.get("net"), dict) and "open" in p["net"], p.get("net"))
        check("T8: وضعیتِ کلی قرمز می‌شود تا در نگاهِ اول دیده شود",
              p["worst"] == "red", p["worst"])

        p = _t8(open_tcp=False)
        check("T8: همه‌ی DCها بسته → «راهی به تلگرام نیست»",
              any(lv == "red" and "راهی به تلگرام نیست" in t
                  for lv, t in [(r["level"], r["title"]) for r in p["checks"]]),
              [(r["level"], r["title"]) for r in p["checks"]])

        # کش: صفحه هر ۱۰ ثانیه تازه می‌شود؛ پروب نباید هر بار شبکه بزند.
        W._NET_CACHE.update({"at": 0.0, "res": None})
        fake = FakeSocket(open_tcp=True)
        restore = use_socket(fake)
        try:
            W.net_probe()
            n1 = fake.attempts
            W.net_probe()
            n2 = fake.attempts
        finally:
            restore()
        check("T8: پروب کش می‌شود (رفرشِ ۱۰ ثانیه‌ای شبکه را بمباران نمی‌کند)",
              n1 > 0 and n2 == n1, (n1, n2))
    finally:
        shutil.rmtree(wtmp, ignore_errors=True)
else:
    print("SKIP T8: deploy/wispbyte/main.py نیست")

shutil.rmtree(work, ignore_errors=True)
print("ALL: PASS" if not FAILS else f"FAILED: {FAILS}")
sys.exit(1 if FAILS else 0)
