#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""بوت‌استرپِ میزبان (main.py) — پنج باگی که «آپدیت کردم، عینِ قبل است» را می‌سازد.

باگ‌های واقعیِ main.pyِ میزبان (نسخه‌ی slim که روی Wispbyte اجرا می‌شد):
  ۱) `telethon&gt;=1.34.0` — کاراکترهای HTML-escape داخلِ argvِ pip؛
     `pip install telethon&gt;=1.34.0` همیشه شکست می‌خورد و بعدش `die`.
  ۲) توکنِ گیت در لاگ چاپ می‌شد (`git clone https://<token>@github.com/…`).
  ۳) شکستِ `git fetch` بی‌صدا بود → کدِ قدیمی در `./code` می‌ماند و
     آپدیتِ کاربر هیچ اثری نداشت (نه خطا، نه هشدار).
  ۴) شکستِ نصبِ وابستگی‌ها فقط لاگ می‌شد و «ادامه می‌داد» → سلف بدونِ
     telethon می‌مرد؛ از بیرون: «نه پنل، نه پیامِ آنلاین‌شدن».
  ۵) پوشه‌ی داده‌ی غیرقابلِ‌نوشتن بی‌صدا به /tmp می‌رفت (هر ری‌استارت =
     از دست دادنِ سشن/دیتابیس).
  (+) کدِ اجرا از `code/` می‌آید؛ آپدیتِ `95.py` در ریشه هیچ اثری ندارد و
      هیچ‌جا هم گفته نمی‌شد.

اجرا: python3 tests/test_wispbyte_main.py
"""
import ast
import importlib.util
import io
import json
import os
import shutil
import subprocess
import sys
import tempfile
import urllib.request
from contextlib import redirect_stdout
from pathlib import Path

HERE = os.path.dirname(os.path.abspath(__file__))
ROOT = os.path.dirname(HERE)
REPO_MAIN = os.path.join(ROOT, "main.py")
SLIM_MAIN = os.path.join(ROOT, "deploy", "wispbyte", "main.py")
SELF = os.path.join(ROOT, "95.py")

FAILS = []


def check(name, ok, extra=""):
    if ok:
        print("PASS", name)
    else:
        FAILS.append(name)
        print("FAIL", name, "" if extra == "" else "→ %r" % (str(extra)[:400],))


def load(path, name):
    old = os.getcwd()
    spec = importlib.util.spec_from_file_location(name, path)
    mod = importlib.util.module_from_spec(spec)
    mod.__file__ = path
    try:
        spec.loader.exec_module(mod)
    finally:
        os.chdir(old)          # این فایل‌ها در import «chdir» می‌کنند
    return mod


# ── T2: هیچ رشته‌ای در کد نباید موجودیتِ HTML داشته باشد ──
def html_entities(path):
    src = open(path, encoding="utf-8").read()
    tree = ast.parse(src)
    bad = []
    for node in ast.walk(tree):
        if isinstance(node, ast.Constant) and isinstance(node.value, str):
            for ent in ("&gt;", "&lt;", "&amp;", "&quot;"):
                if ent in node.value:
                    bad.append(node.value[:60])
    return bad


for path in (SELF, REPO_MAIN, SLIM_MAIN):
    bad = html_entities(path)
    check(f"T2: هیچ رشته‌ی HTML-escape در {os.path.relpath(path, ROOT)} نیست",
          not bad, bad)

slim_src = open(SLIM_MAIN, encoding="utf-8").read()
check("T2: argvِ pip تمیز است", '"telethon>=1.34.0"' in slim_src)

slim = load(SLIM_MAIN, "slim_main")
repo = load(REPO_MAIN, "repo_main")

# ── T3: توکنِ گیت نباید در لاگ بیفتد ──
TOK = "ghp_SECRET1234567890"
os.environ["JAFJ_GIT_TOKEN"] = TOK
try:
    url = slim.repo_url()
    check("T3: url واقعاً توکن دارد", TOK in url, url)
    red = slim.redact(url)
    check("T3: redact توکن را پاک می‌کند", TOK not in red, red)
    check("T3: شکلِ آدرس حفظ می‌شود", red.startswith("https://***@github.com"),
          red)
    check("T3: main.py ریپو هم همان کار را می‌کند",
          TOK not in repo.redact(url), repo.redact(url))
    check("T3: خودِ توکن تنها هم ماسک می‌شود",
          TOK not in slim.redact(f"token={TOK}"), slim.redact(f"token={TOK}"))
finally:
    os.environ.pop("JAFJ_GIT_TOKEN", None)

# ── T4/T5: شکستِ fetch باید بلند و قابلِ‌دیدن باشد، نه بی‌صدا ──
tmp = Path(tempfile.mkdtemp(prefix="jafj_slim_"))
(tmp / "code" / ".git").mkdir(parents=True)
for n in ("95.py", "manager_82.py"):
    (tmp / "code" / n).write_text("# stub\n", encoding="utf-8")
slim.HERE = tmp
slim.CODE_DIR = tmp / "code"
slim.CODE_STATE.update(commit="", branch="main", stale=False, why="")


class _R:
    def __init__(self, rc):
        self.returncode = rc


_real_run, _real_git_head = slim.run, slim.git_head
slim.run = lambda cmd, cwd=None, env=None, quiet=False: _R(1)   # همه شکست
slim.git_head = lambda folder=None: "abc1234"
buf = io.StringIO()
with redirect_stdout(buf):
    ok = slim.sync_code()
out = buf.getvalue()
check("T4: sync_code با شکستِ fetch مقدار False می‌دهد", ok is False, ok)
check("T4: وضعیت «قدیمی» ست می‌شود", slim.CODE_STATE["stale"] is True,
      slim.CODE_STATE)
check("T4: دلیل ثبت می‌شود", "fetch" in slim.CODE_STATE["why"],
      slim.CODE_STATE["why"])
check("T4: لاگ صریحاً ⛔ و «قدیمی» می‌گوید",
      "⛔" in out and "قدیمی" in out, out[-500:])
check("T4: کامیتِ در حالِ اجرا چاپ می‌شود", "abc1234" in out, out[-300:])
check("T4: علت‌های رایج گفته می‌شود",
      "JAFJ_GIT_TOKEN" in out and "github.com" in out, out[-600:])

# ── T5: 95.pyِ ریشه در برابر code/95.py ──
(tmp / "95.py").write_text("# نسخه‌ی ریشه — فرق دارد\n", encoding="utf-8")
warn = slim.root_vs_code_warning()
check("T5: اختلافِ فایلِ ریشه و code/ گفته می‌شود", bool(warn), warn)
check("T5: می‌گوید آپدیتِ ریشه اثری ندارد", "اثری ندارد" in warn, warn)
(tmp / "95.py").write_text("# stub\n", encoding="utf-8")   # حالا یکسان
check("T5: با فایلِ یکسان هشدار نمی‌دهد",
      slim.root_vs_code_warning() == "", slim.root_vs_code_warning())

# ── T6: /health باید کامیت و تازگیِ کد را بگوید ──
slim.CODE_STATE.update(commit="abc1234", stale=True, why="git fetch نشد")
slim.DEPS_STATE.update(ok=True, python="/usr/bin/python3")
slim.DATA_STATE.update(dir=str(tmp / "data"), tmp=False)
srv = slim.boot_listener(port=0)
check("T6: شنونده‌ی بوت ساخته شد", srv is not None)
if srv is not None:
    port = srv.server_address[1]
    # مسیرِ مرورگر: HTML فارسی (کاربر ترمینال ندارد)
    with urllib.request.urlopen(f"http://127.0.0.1:{port}/", timeout=20) as r:
        page = r.read().decode("utf-8")
    check("T6: صفحه‌ی مرورگر HTML است", page.lstrip().startswith("<!doctype"),
          page[:80])
    check("T6: عنوانِ فارسی دارد", "وضعیتِ بوتِ جفج" in page, page[:200])
    check("T6: کامیت در صفحه دیده می‌شود", "abc1234" in page)
    check("T6: وضعیتِ «قدیمی» در صفحه هشدار می‌دهد",
          "قدیمی" in page or "stale" in page, page[:200])
    # مسیرِ برنامه‌ای: ?json=1
    with urllib.request.urlopen(f"http://127.0.0.1:{port}/?json=1",
                                timeout=20) as r:
        data = json.loads(r.read().decode("utf-8"))
    check("T6: پاسخ JSON است", isinstance(data, dict), data)
    check("T6: commit در پاسخ هست", data.get("commit") == "abc1234", data)
    check("T6: stale در پاسخ هست", data.get("stale") is True, data)
    check("T6: علتِ قدیمی‌بودن هم می‌آید", data.get("why") == "git fetch نشد",
          data)
    check("T6: وضعیتِ وابستگی‌ها هم می‌آید", data.get("deps") is True, data)
    check("T6: فهرستِ چک‌ها در پاسخ هست",
          isinstance(data.get("checks"), list) and len(data["checks"]) >= 5,
          len(data.get("checks") or []))
    check("T6: بدترین سطح گزارش می‌شود",
          data.get("worst") in ("red", "yellow", "green"), data.get("worst"))
    buf = io.StringIO()
    with redirect_stdout(buf):
        slim.boot_listener_stop()
    check("T6: بستنِ شنونده امن است", slim._boot_srv is None)

# ── T7: پوشه‌ی داده‌ی غیرقابلِ‌نوشتن نباید بی‌صدا /tmp شود ──
blocker = tmp / "iam_a_file"
blocker.write_text("x", encoding="utf-8")
env = {"DATA_DIR": str(blocker / "sub"), "JAFJ_APP_DIR": ""}
slim.DATA_STATE.update(dir="", writable=True, tmp=False, why="")
buf = io.StringIO()
with redirect_stdout(buf):
    env2 = slim.check_layout(env)
out = buf.getvalue()
check("T7: وضعیت «نوشتنی نیست» ثبت می‌شود",
      slim.DATA_STATE["writable"] is False, slim.DATA_STATE)
check("T7: پرش به /tmp علامت‌گذاری می‌شود",
      slim.DATA_STATE["tmp"] is True, slim.DATA_STATE)
check("T7: هشدارِ صریح چاپ می‌شود", "⛔" in out and "ری‌استارت" in out,
      out[-400:])
check("T7: مسیرِ جایگزین اعمال می‌شود",
      env2["DATA_DIR"] == "/tmp/jafj-data", env2["DATA_DIR"])

# ── T8: نبودِ telethon باید همین‌جا بمیرد، نه بعداً ──
slim.deps_ok = lambda py: False
slim.install_deps = lambda py: False
os.environ["JAFJ_SKIP_VENV"] = "1"
buf = io.StringIO()
died = False
try:
    with redirect_stdout(buf):
        slim.ensure_python()
except SystemExit as e:
    died = e.code not in (0, None)
finally:
    os.environ.pop("JAFJ_SKIP_VENV", None)
out = buf.getvalue()
check("T8: بدونِ telethon با خطا می‌میرد (نه ادامه)", died)
check("T8: پیام می‌گوید با نبودِ telethon سلف بالا نمی‌آید",
      "بالا نمی‌آید" in out, out[-400:])
check("T8: دستورِ نصب را با همان مفسر می‌دهد",
      "pip install -r" in out and sys.executable in out, out[-400:])

# ── T10: die() باید علت را ذخیره کند و صفحه را نگه دارد ──
slim.STATUS_FILE = tmp / "boot-status.txt"
slim.HERE = tmp
slim._boot_srv = None                     # شنونده‌ای نیست → نگه‌داشتن لازم نیست
os.environ["JAFJ_DIE_HOLD"] = "0"
rc = None
buf = io.StringIO()
try:
    with redirect_stdout(buf):
        slim.die("تست-خطای-بوت", 7)
except SystemExit as e:
    rc = e.code
finally:
    os.environ.pop("JAFJ_DIE_HOLD", None)
check("T10: die با کدِ خودش خارج می‌شود", rc == 7, rc)
check("T10: متنِ خطا در boot-status.txt ذخیره شده",
      slim.STATUS_FILE.is_file() and
      "تست-خطای-بوت" in slim.STATUS_FILE.read_text(encoding="utf-8"))
check("T10: فایلِ وضعیت کامیت را هم دارد",
      "commit=" in slim.STATUS_FILE.read_text(encoding="utf-8"))
check("T10: فازِ بوت روی «خطا» می‌رود", slim._boot_phase["phase"] == "خطا",
      slim._boot_phase)
check("T10: پیامِ خطا در خروجی چاپ می‌شود", "تست-خطای-بوت" in buf.getvalue())
os.environ["JAFJ_DIE_HOLD"] = "77"
check("T10: JAFJ_DIE_HOLD خوانده می‌شود", slim.hold_seconds() == 77.0,
      slim.hold_seconds())
os.environ.pop("JAFJ_DIE_HOLD", None)
check("T10: پیش‌فرضِ نگه‌داشتن ۱۰ دقیقه است", slim.hold_seconds() == 600.0,
      slim.hold_seconds())

# ── T9: git_head روی مخزنِ واقعی ──
slim.run, slim.git_head = _real_run, _real_git_head
gd = Path(tempfile.mkdtemp(prefix="jafj_git_"))
subprocess.run(["git", "init", "-q", str(gd)], check=False)
(gd / "a.txt").write_text("x", encoding="utf-8")
subprocess.run(["git", "-C", str(gd), "-c", "user.email=t@t", "-c",
                "user.name=t", "add", "."], check=False)
subprocess.run(["git", "-C", str(gd), "-c", "user.email=t@t", "-c",
                "user.name=t", "commit", "-qm", "x"], check=False)
head = slim.git_head(gd)
check("T9: git_head کامیتِ کوتاه می‌دهد",
      bool(head) and len(head) >= 7 and all(c in "0123456789abcdef" for c in head),
      head)
check("T9: برای پوشه‌ی غیرگیت رشته‌ی خالی", slim.git_head(tmp / "code") == "")

shutil.rmtree(tmp, ignore_errors=True)
shutil.rmtree(gd, ignore_errors=True)

print()
if FAILS:
    print("FAILED:", FAILS)
    sys.exit(1)
print("ALL PASS")
