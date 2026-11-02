#!/usr/bin/env python3
# -*- coding: utf-8 -*-
# ═══════════════════════════════════════════════════════════════════════
#  JAFJ — main.py   (بوت‌استرپِ میزبانِ «اپ پایتونی» — بدونِ نیاز به ترمینال)
#
#  کارِ همیشگی‌اش را می‌کند (clone از گیت → venv → وابستگی‌ها → داده →
#  اجرای railway-start.sh) و علاوه بر آن:
#
#   ★ یک «صفحه‌ی وضعیت» روی همان PORT باز می‌کند. کافی است آدرسِ اپ را در
#     مرورگر باز کنی تا ببینی: کدام کامیت اجرا می‌شود، آپدیت رسیده یا نه،
#     telethon نصب است یا نه، داده کجاست، دیتابیس/تبادل چه وضعی دارند،
#     و آخرین خطوطِ ردیِ بوت/خطا. لازم نیست ترمینال داشته باشی.
#
#   ★ اگر بوت شکست بخورد، پروسه فوراً نمی‌میرد: تا ۱۰ دقیقه صفحه را باز
#     نگه می‌دارد (قابلِ تنظیم با JAFJ_DIE_HOLD) تا خطا را در مرورگر
#     بخوانی. بعد از آن با کدِ خطا خارج می‌شود.
#
#  اصلاح‌های واقعی نسبت به نسخه‌ی قبل:
#   ۱) «telethon>=1.34.0» ← موجودیتِ HTML در argvِ pip؛
#      نصب همیشه شکست می‌خورد. حالا `telethon>=1.34.0`.
#   ۲) توکنِ گیت در لاگ چاپ می‌شد → redact().
#   ۳) شکستِ `git fetch` بی‌صدا بود → کدِ قدیمی می‌ماند و آپدیت اثری
#      نداشت. حالا ⛔ + کامیت + علت، و در صفحه‌ی وضعیت.
#   ۴) شکستِ نصبِ وابستگی‌ها فقط لاگ می‌شد و ادامه می‌داد → سلف بدونِ
#      telethon می‌مرد. حالا صریح می‌میرد و علت را در صفحه می‌نویسد.
#   ۵) پوشهٔ دادهٔ غیرقابلِ‌نوشتن بی‌صدا به /tmp می‌رفت (هر ری‌استارت =
#      از دست دادنِ سشن). حالا هشدارِ صریح + علامت در صفحه.
#   ۶) اختلافِ `95.py`ِ ریشه با `code/95.py` (کدی که واقعاً اجرا می‌شود)
#      حالا گفته می‌شود — همان چیزی که «آپدیت کردم، عینِ قبل است» را
#      می‌سازد.
# ═══════════════════════════════════════════════════════════════════════
import glob
import hashlib
import html
import json
import os
import re
import shutil
import sqlite3
import subprocess
import sys
import threading
import time
from pathlib import Path

HERE = Path(__file__).resolve().parent
os.chdir(HERE)

BOOT_VERSION = "2026-11-02-slim3"
DEFAULT_REPO = "abolfazleoy/jfjj"
DEFAULT_BRANCH = "main"

CODE_DIR = HERE / "code"
VENV_DIR = HERE / "venv"
DEFAULT_DATA = HERE / "data"
MANAGER_NAME = "manager_82.py"
SELF_NAME = "95.py"
ENTRY_NAME = "railway-start.sh"
STATUS_FILE = HERE / "boot-status.txt"

_boot_srv = None
_boot_phase = {"phase": "شروع", "error": "", "exit": None}

CODE_STATE = {"commit": "", "branch": "", "stale": False, "why": ""}
DATA_STATE = {"dir": "", "writable": True, "tmp": False, "why": ""}
DEPS_STATE = {"ok": True, "python": ""}


# ─────────────────────────── ابزارهای پایه ───────────────────────────
def log(msg):
    print(f"JAFJ-BOOT: {msg}", flush=True)


def token():
    return (os.environ.get("JAFJ_GIT_TOKEN") or "").strip()


def redact(text):
    """توکن/رمز را از متن حذف کن — لاگِ اپ جای توکن نیست."""
    out = str(text)
    t = token()
    if t:
        out = out.replace(t, "***")
    out = re.sub(r"https://[^/\s@]+@", "https://***@", out)
    out = re.sub(r"(?i)(token|password|secret)(=|:)\s*\S+", r"\1\2***", out)
    return out


def hold_seconds():
    try:
        return max(0.0, float(os.environ.get("JAFJ_DIE_HOLD", "600") or 0))
    except Exception:
        return 600.0


def die(msg, code=1):
    """خطای بوت: چاپ + ذخیره در فایل + نگه‌داشتنِ صفحه‌ی وضعیت.

    بدونِ ترمینال، تنها راهِ دیدنِ علت همین صفحه است. پس پروسه فوراً
    نمی‌میرد؛ تا JAFJ_DIE_HOLD (پیش‌فرض ۱۰ دقیقه) صفحه را باز نگه
    می‌دارد، بعد با کدِ خطا خارج می‌شود.
    """
    _boot_phase["error"] = str(msg)
    _boot_phase["phase"] = "خطا"
    log(f"❌ {msg}")
    try:
        with open(STATUS_FILE, "w", encoding="utf-8") as f:
            f.write(f"{time.strftime('%Y-%m-%d %H:%M:%S')}\n"
                    f"boot={BOOT_VERSION}\ncwd={HERE}\n"
                    f"commit={CODE_STATE.get('commit') or '?'}\n\n{msg}\n")
    except Exception:
        pass
    hold = hold_seconds()
    if hold and _boot_srv is not None:
        log(f"   ⏳ صفحه‌ی وضعیت تا {int(hold)} ثانیه باز می‌ماند — آدرسِ اپ "
            "را در مرورگر باز کن و همین خطا را بخوان.")
        try:
            time.sleep(hold)
        except KeyboardInterrupt:
            pass
    sys.exit(code)


def repo():
    return (os.environ.get("JAFJ_REPO") or DEFAULT_REPO).strip()


def branch():
    return (os.environ.get("JAFJ_BRANCH") or DEFAULT_BRANCH).strip() or DEFAULT_BRANCH


def data_dir():
    return Path(os.environ.get("DATA_DIR") or DEFAULT_DATA).expanduser().resolve()


def repo_url():
    r, t = repo(), token()
    if "://" in r or r.startswith(("/", "./", "git@")):
        return r
    if t:
        return f"https://{t}@github.com/{r}.git"
    return f"https://github.com/{r}.git"


def shown(url):
    return redact(url)


def run(cmd, cwd=None, env=None, quiet=False):
    log("$ " + redact(" ".join(str(c) for c in cmd)))
    out = subprocess.DEVNULL if quiet else None
    try:
        return subprocess.run([str(c) for c in cmd],
                              cwd=str(cwd) if cwd else None, env=env,
                              stdout=out, stderr=out)
    except FileNotFoundError:
        die(f"دستور «{cmd[0]}» روی این میزبان نصب نیست — بدونِ آن بوت ممکن "
            f"نیست.")
        return None


def run_capture(cmd, timeout=60):
    try:
        r = subprocess.run([str(c) for c in cmd], capture_output=True,
                           text=True, timeout=timeout)
        return r.returncode, (r.stdout or "") + (r.stderr or "")
    except Exception as e:
        return 127, f"{type(e).__name__}: {e}"


def git_head(folder=None):
    d = str(folder or CODE_DIR)
    rc, out = run_capture(["git", "-C", d, "rev-parse", "--short", "HEAD"], 20)
    return out.strip() if rc == 0 else ""


def file_sha8(path):
    try:
        with open(path, "rb") as f:
            return hashlib.sha256(f.read()).hexdigest()[:8]
    except Exception:
        return ""


def tail_lines(path, n=12):
    try:
        with open(path, encoding="utf-8", errors="ignore") as f:
            return [ln.rstrip("\n") for ln in f.readlines()[-n:]]
    except Exception:
        return []


def human_mb(n):
    try:
        return f"{int(n) // (1024 * 1024)} مگابایت"
    except Exception:
        return "?"


# ─────────────────────────── ۰) صفحه‌ی وضعیت ───────────────────────────
#  این صفحه جای ترمینال را می‌گیرد: آدرسِ اپ را در مرورگر باز کن.
def _proc_cmdline(pid):
    try:
        with open(f"/proc/{int(pid)}/cmdline", "rb") as f:
            return f.read().replace(b"\x00", b" ").decode("utf-8", "ignore").strip()
    except Exception:
        return ""


def looks_like_selfbot_proc(cmd):
    parts = (cmd or "").split()
    if not parts:
        return False
    if not os.path.basename(parts[0]).lower().startswith("python"):
        return False
    return any(os.path.basename(t) == SELF_NAME for t in parts[1:])


def live_selfbots():
    out = []
    if not os.path.isdir("/proc"):
        return out
    me = os.getpid()
    for name in os.listdir("/proc"):
        if not name.isdigit() or int(name) == me:
            continue
        cmd = _proc_cmdline(int(name))
        if looks_like_selfbot_proc(cmd):
            out.append((int(name), cmd[:110]))
    return out


def _db_summary():
    """شمارشِ وضعیت‌های تبادل از دیتابیس (فقط‌خواندنی، بی‌خطر)."""
    for p in (data_dir() / "jafj.db", HERE / "jafj.db",
              data_dir() / "jafj_data.db"):
        if not Path(p).is_file():
            continue
        try:
            con = sqlite3.connect(f"file:{p}?mode=ro", uri=True, timeout=3)
            ok = con.execute("PRAGMA quick_check").fetchone()[0]
            try:
                rows = {r[0]: r[1] for r in con.execute(
                    "SELECT status,COUNT(*) FROM exchange GROUP BY status")}
            except Exception:
                rows = {}
            try:
                unk = con.execute("SELECT COUNT(*) FROM exchange "
                                  "WHERE unk_streak>0").fetchone()[0]
            except Exception:
                unk = 0
            try:
                ev = con.execute(
                    "SELECT ts,level,kind,substr(detail,1,60) FROM events "
                    "ORDER BY id DESC LIMIT 5").fetchall()
            except Exception:
                ev = []
            con.close()
            return {"path": str(p), "check": ok, "counts": rows,
                    "unknown": unk, "events": ev}
        except Exception as e:
            return {"path": str(p), "error": f"{type(e).__name__}: {e}"}
    return None


def diagnose():
    """همه‌ی چیزهایی که «بالا نمی‌آید» را می‌سازند → [(سطح, عنوان, جزئیات)].

    سطح: red / yellow / green
    """
    rows = []

    def add(level, title, *details):
        rows.append({"level": level, "title": title,
                     "details": [str(d) for d in details if d != ""]})

    add("green", "فازِ بوت", _boot_phase.get("phase", "?"),
        f"نسخه‌ی بوت‌استرپ: {BOOT_VERSION}")
    if _boot_phase.get("error"):
        add("red", "خطای بوت", _boot_phase["error"])

    # پایتون و ابزارها
    v = sys.version_info
    add("green" if (v.major, v.minor) >= (3, 8) else "red", "پایتون",
        f"{v.major}.{v.minor}.{v.micro} — {sys.executable}")
    add("green" if shutil.which("git") else "red", "git",
        shutil.which("git") or "نصب نیست — clone/به‌روزرسانی ممکن نیست")

    # کد
    if CODE_DIR.is_dir():
        commit = CODE_STATE.get("commit") or git_head() or "?"
        tail = read_boot_tail()
        add("red" if CODE_STATE.get("stale") else "green", "کدِ در حالِ اجرا",
            f"commit={commit} • برنچ {branch()}",
            ("⛔ به‌روزرسانی از گیت شکست خورد — همین کدِ قدیمی اجرا می‌شود"
             f" ({CODE_STATE.get('why')})") if CODE_STATE.get("stale") else "",
            f"مسیر: {CODE_DIR}",
            tail)
    else:
        add("yellow", "پوشه‌ی code", f"{CODE_DIR} هنوز نیست (اولین clone)")

    root_self, code_self = HERE / SELF_NAME, CODE_DIR / SELF_NAME
    if root_self.is_file() and code_self.is_file():
        h1, h2 = file_sha8(root_self), file_sha8(code_self)
        if h1 and h2 and h1 != h2:
            add("yellow", "95.pyِ ریشه ≠ code/95.py",
                f"ریشه {h1} • code {h2}",
                "کدی که اجرا می‌شود code/95.py است (از گیت). آپدیتِ فایلِ "
                "ریشه اثری ندارد؛ تغییر را به گیت بفرست.")

    # وابستگی‌ها
    py = DEPS_STATE.get("python") or str(VENV_DIR / "bin" / "python")
    if Path(py).exists():
        rc, out = run_capture([py, "-c", "import telethon,sys;"
                               "print(getattr(telethon,'__version__','?'))"], 60)
        if rc == 0:
            add("green", "telethon", f"{out.strip().splitlines()[-1]} — {py}")
        else:
            add("red", "telethon نصب نیست",
                f"در {py} قابلِ import نیست",
                f'"{py}" -m pip install -r {CODE_DIR / "requirements.txt"}')
    else:
        add("yellow", "venv", "هنوز ساخته نشده (اولین بوت)")

    # داده
    add("red" if not DATA_STATE.get("writable") else
        ("yellow" if DATA_STATE.get("tmp") else "green"), "پوشه‌ی داده",
        f"{DATA_STATE.get('dir') or data_dir()}",
        "⛔ نوشتنی نیست — سشن/دیتابیس ساخته نمی‌شود" if not
        DATA_STATE.get("writable") else "",
        "⚠️ روی /tmp است — با هر ری‌استارت پاک می‌شود" if
        DATA_STATE.get("tmp") else "")

    # پروسه و قفل
    procs = live_selfbots()
    if procs:
        add("green", "پروسه‌ی سلف", *[f"pid {p} — {c}" for p, c in procs])
        if len(procs) > 1:
            add("red", "بیش از یک سلف",
                f"{len(procs)} پروسه — دو سلف روی یک سشن، تلگرام هر دو را "
                "قطع می‌کند و پنل جواب نمی‌دهد.")
    else:
        add("yellow", "سلفِ زنده", "هیچ پروسه‌ی python … 95.py پیدا نشد",
            "اگر انتظار داشتی بالا باشد، یعنی همین بوت کامل نشده است.")

    # دیتابیس و تبادل
    db = _db_summary()
    if db:
        if db.get("error"):
            add("yellow", "دیتابیس", f"{db['path']} — {db['error']}")
        else:
            add("green" if db["check"] == "ok" else "red", "دیتابیس",
                f"{db['path']} • quick_check={db['check']}",
                "تبادل: " + (" • ".join(f"{k}={v}" for k, v in
                                        sorted(db["counts"].items()))
                            or "خالی"),
                f"رکوردهای «چکِ نامشخص»: {db.get('unknown', 0)}")
            for ts, lvl, kind, det in db.get("events", []):
                add("green", "آخرین رویداد",
                    f"{time.strftime('%m-%d %H:%M', time.localtime(ts))} "
                    f"[{lvl}] {kind}: {det}")

    # ردیِ بوت / خطای بوتِ سلف (اگر مدیر آن را نوشته باشد)
    for folder in selfbot_folders():
        blog = Path(folder) / "jafj_boot.log"
        crash = Path(folder) / "jafj_boot_error.txt"
        if crash.is_file():
            add("red", f"خطای بوتِ سلف — {Path(folder).name}",
                *tail_lines(crash, 6))
        if blog.is_file():
            lines = tail_lines(blog, 8)
            reached = any("آنلاین شد" in ln for ln in lines[-6:])
            add("green" if reached else "yellow",
                f"ردیِ بوتِ سلف — {Path(folder).name}",
                "به پنل رسیده ✅" if reached else "به پنل نرسیده",
                *lines)

    # منابع
    try:
        du = shutil.disk_usage(str(HERE))
        free = du.free // (1024 * 1024)
        add("green" if free > 200 else "red", "دیسک", f"{human_mb(du.free)} آزاد")
    except Exception:
        pass
    try:
        mem = {}
        with open("/proc/meminfo", encoding="utf-8") as f:
            for ln in f:
                k, _, rest = ln.partition(":")
                mem[k] = int(rest.split()[0]) // 1024
        avail = mem.get("MemAvailable")
        if avail is not None:
            add("green" if avail > 120 else "yellow", "حافظه",
                f"{avail} مگابایت آزاد")
    except Exception:
        pass
    return rows


def selfbot_folders():
    out = []
    base = data_dir() / "clients"
    if base.is_dir():
        out += [str(d) for d in sorted(glob.glob(str(base / "*"))) if
                os.path.isdir(d)]
    out.append(str(data_dir()))
    return out


def read_boot_tail():
    lines = tail_lines(data_dir() / "jafj_boot.log", 3)
    return ("ردیِ بوتِ مدیر: " + " | ".join(ln[20:] for ln in lines)) if lines else ""


def status_payload():
    rows = diagnose()
    worst = "red" if any(r["level"] == "red" for r in rows) else (
        "yellow" if any(r["level"] == "yellow" for r in rows) else "green")
    return {
        "ok": worst != "red",
        "boot": True,
        "version": BOOT_VERSION,
        "phase": _boot_phase.get("phase"),
        "error": _boot_phase.get("error"),
        "worst": worst,
        "commit": CODE_STATE.get("commit") or git_head(),
        "stale": bool(CODE_STATE.get("stale")),
        "why": CODE_STATE.get("why", ""),
        "deps": bool(DEPS_STATE.get("ok")),
        "python": DEPS_STATE.get("python", ""),
        "data": DATA_STATE.get("dir") or str(data_dir()),
        "data_tmp": bool(DATA_STATE.get("tmp")),
        "checks": rows,
        "time": time.strftime("%Y-%m-%d %H:%M:%S"),
    }


def status_html():
    p = status_payload()
    color = {"red": "#e5484d", "yellow": "#f5a524", "green": "#30a46c"}
    icon = {"red": "🟥", "yellow": "🟨", "green": "🟩"}
    parts = []
    for r in p["checks"]:
        det = "".join(f"<div class='d'>{html.escape(d)}</div>"
                      for d in r["details"])
        parts.append(
            f"<div class='row' style='border-right:4px solid "
            f"{color[r['level']]}'>"
            f"<div class='t'>{icon[r['level']]} {html.escape(r['title'])}</div>"
            f"{det}</div>")
    head = ("✅ همه‌چیز در بوت سالم است" if p["worst"] == "green" else
            ("⚠️ چند هشدار" if p["worst"] == "yellow" else
             "⛔ ربات با این وضعیت بالا نمی‌آید"))
    return f"""<!doctype html><html lang="fa" dir="rtl"><head>
<meta charset="utf-8"><meta name="viewport" content="width=device-width,initial-scale=1">
<meta http-equiv="refresh" content="10">
<title>وضعیتِ جفج</title>
<style>
 body{{font-family:system-ui,Tahoma,sans-serif;background:#0f1115;color:#e6e6e6;
      margin:0;padding:18px;line-height:1.7}}
 h1{{font-size:19px;margin:0 0 4px}}
 .sub{{color:#9aa0a6;font-size:13px;margin-bottom:14px}}
 .sum{{font-size:16px;font-weight:700;margin:10px 0 16px;padding:12px;
       border-radius:10px;background:#171a21}}
 .row{{background:#171a21;border-radius:10px;padding:10px 12px;margin:8px 0}}
 .t{{font-weight:700;font-size:14px}}
 .d{{color:#b9bec6;font-size:13px;word-break:break-word;
     font-family:ui-monospace,Menlo,monospace}}
 .kv{{display:flex;gap:10px;flex-wrap:wrap;font-size:13px;color:#9aa0a6;
      margin-bottom:10px}}
 .pill{{background:#171a21;padding:4px 10px;border-radius:999px}}
 .hint{{color:#9aa0a6;font-size:12px;margin-top:16px}}
</style></head><body>
<h1>🩺 وضعیتِ بوتِ جفج</h1>
<div class="sub">{html.escape(p['time'])} • نسخه‌ی بوت‌استرپ {p['version']}</div>
<div class="kv">
 <span class="pill">commit: {html.escape(p['commit'] or '?')}</span>
 <span class="pill">stale: {'بله' if p['stale'] else 'نه'}</span>
 <span class="pill">مرحله: {html.escape(str(p['phase']))}</span>
</div>
<div class="sum">{head}</div>
{''.join(parts)}
<div class="hint">این صفحه هر ۱۰ ثانیه خودش تازه می‌شود. اگر بوت شکست
بخورد، همین صفحه تا چند دقیقه باز می‌ماند تا خطا را بخوانی؛ بعد پروسه با
خطا خارج می‌شود. نسخه‌ی JSON: همین آدرس با <code>?json=1</code>.</div>
</body></html>"""


def _make_handler():
    from http.server import BaseHTTPRequestHandler

    class _H(BaseHTTPRequestHandler):
        def do_GET(self):
            try:
                if "json" in (self.path or ""):
                    body = json.dumps(status_payload(), ensure_ascii=False,
                                      default=str).encode("utf-8")
                    ctype = "application/json; charset=utf-8"
                else:
                    body = status_html().encode("utf-8")
                    ctype = "text/html; charset=utf-8"
            except Exception as e:
                body = json.dumps({"ok": False,
                                   "error": f"{type(e).__name__}: {e}"}
                                  ).encode("utf-8")
                ctype = "application/json; charset=utf-8"
            try:
                self.send_response(200)
                self.send_header("Content-Type", ctype)
                self.send_header("Content-Length", str(len(body)))
                self.send_header("Cache-Control", "no-store")
                self.end_headers()
                self.wfile.write(body)
            except Exception:
                pass

        def do_HEAD(self):
            self.do_GET()

        def log_message(self, *a):
            pass

    return _H


def boot_listener(port=None):
    """شنونده‌ی PORT از ثانیه‌ی اول — هم برای «زنده دیده شدن»، هم صفحه‌ی وضعیت."""
    global _boot_srv
    if _boot_srv is not None:
        return _boot_srv
    port = port if port is not None else os.environ.get("PORT")
    if port in (None, "") or str(port).strip() == "":
        return None
    try:
        from http.server import HTTPServer
        srv = HTTPServer(("0.0.0.0", int(port)), _make_handler())
        srv.daemon_threads = True
        threading.Thread(target=srv.serve_forever, daemon=True,
                         name="jafj-status-http").start()
        _boot_srv = srv
        log(f"صفحه‌ی وضعیت روی 0.0.0.0:{port} — آدرسِ اپ را در مرورگر باز کن")
        return srv
    except Exception as e:
        log(f"⚠️ شنونده‌ی PORT بالا نیامد ({type(e).__name__}: {e}) — ادامه "
            "می‌دهم؛ اگر پنل وسطِ بوت ری‌استارت کرد، همین علتش است.")
        return None


def boot_listener_stop():
    global _boot_srv
    srv, _boot_srv = _boot_srv, None
    if srv is None:
        return
    try:
        srv.shutdown()
    except Exception:
        pass
    try:
        srv.server_close()
    except Exception:
        pass
    log("شنونده‌ی بوت بسته شد (مدیر پورت را می‌گیرد).")


# ─────────────────────────── ۱) کد از گیت → ./code ───────────────────────────
def root_vs_code_warning():
    root_self, code_self = HERE / SELF_NAME, CODE_DIR / SELF_NAME
    if not (root_self.is_file() and code_self.is_file()):
        return ""
    if os.path.abspath(root_self) == os.path.abspath(code_self):
        return ""
    h1, h2 = file_sha8(root_self), file_sha8(code_self)
    if not h1 or not h2 or h1 == h2:
        return ""
    return (f"⚠️ {root_self} با {code_self} فرق دارد (هش {h1} ≠ {h2}).\n"
            f"   کدی که اجرا می‌شود {code_self} است (از گیت)؛ آپدیتِ فایلِ "
            f"ریشه اثری ندارد.")


def sync_code():
    _boot_phase["phase"] = "همگام‌سازیِ کد"
    CODE_DIR.parent.mkdir(parents=True, exist_ok=True)
    url = repo_url()
    if not (CODE_DIR / ".git").exists():
        if CODE_DIR.exists():
            shutil.rmtree(CODE_DIR, ignore_errors=True)
        log(f"clone {shown(url)} (branch {branch()}) → {CODE_DIR}")
        ok = run(["git", "clone", "--depth", "1", "--branch", branch(), url,
                  str(CODE_DIR)]).returncode == 0
        if not ok:
            log(f"⚠️ برنچِ «{branch()}» clone نشد — برنچِ پیش‌فرض را می‌گیرم")
            if run(["git", "clone", "--depth", "1", url,
                    str(CODE_DIR)]).returncode != 0:
                die("git clone نشد. JAFJ_REPO / JAFJ_BRANCH / JAFJ_GIT_TOKEN را "
                    "چک کن (یا میزبان به github.com دسترسی ندارد).")
    else:
        log("code موجود است — به‌روزرسانی…")
        if run(["git", "-C", str(CODE_DIR), "fetch", "--depth", "1", "origin",
                branch()]).returncode == 0:
            run(["git", "-C", str(CODE_DIR), "reset", "--hard", "FETCH_HEAD"])
            run(["git", "-C", str(CODE_DIR), "clean", "-fdq"])
        else:
            CODE_STATE["stale"] = True
            CODE_STATE["why"] = "git fetch نشد"
            log("⛔ به‌روزرسانیِ کد از گیت انجام نشد — با نسخه‌ی موجود ادامه "
                "می‌دهم، ولی **این نسخه قدیمی است**؛ آپدیتِ تازه اثری ندارد.")
            log("   علت‌های رایج: نبودِ JAFJ_GIT_TOKEN (ریپوی خصوصی)، نبودِ "
                f"شبکه به github.com، یا برنچِ اشتباه (الان: {branch()}).")

    CODE_STATE["commit"] = git_head()
    CODE_STATE["branch"] = branch()
    if not CODE_STATE["commit"]:
        CODE_STATE["stale"] = True
        CODE_STATE["why"] = CODE_STATE["why"] or "کامیت خوانده نشد"
    log(f"کدِ در حالِ اجرا: commit={CODE_STATE['commit'] or '?'} "
        f"branch={CODE_STATE['branch']}"
        + (" ⛔ (قدیمی — به‌روزرسانی نشد)" if CODE_STATE["stale"] else ""))
    warn = root_vs_code_warning()
    if warn:
        for ln in warn.splitlines():
            log(ln)

    for need in (MANAGER_NAME, SELF_NAME):
        if not (CODE_DIR / need).is_file():
            die(f"{need} در ریپو نیست ({CODE_DIR}) — ریپو/برنچ را چک کن.")

    for sh in CODE_DIR.glob("*.sh"):
        try:
            os.chmod(sh, 0o755)
        except Exception:
            pass
    return not CODE_STATE["stale"]


# ─────────────────────────── ۲) venv + وابستگی‌ها ───────────────────────────
def req_hash():
    f = CODE_DIR / "requirements.txt"
    return hashlib.sha256(f.read_bytes()).hexdigest() if f.is_file() else ""


def stamp_file():
    return VENV_DIR / ".reqhash"


def deps_ok(py):
    try:
        return subprocess.run([str(py), "-c", "import telethon"],
                              stdout=subprocess.DEVNULL,
                              stderr=subprocess.DEVNULL, timeout=90).returncode == 0
    except Exception:
        return False


def install_deps(py):
    req = CODE_DIR / "requirements.txt"
    if not req.is_file():
        log("requirements.txt نیست — telethon را نصب می‌کنم")
        return run([str(py), "-m", "pip", "install",
                    "--disable-pip-version-check", "-q",
                    "telethon>=1.34.0"]).returncode == 0
    run([str(py), "-m", "pip", "install", "--disable-pip-version-check",
         "--upgrade", "pip"], quiet=True)
    return run([str(py), "-m", "pip", "install",
                "--disable-pip-version-check", "-r", str(req)]).returncode == 0


def _require_deps(py):
    DEPS_STATE["python"] = str(py)
    if deps_ok(py):
        DEPS_STATE["ok"] = True
        return True
    DEPS_STATE["ok"] = False
    die(f"telethon در این مفسر نصب نیست: {py}\n"
        f'   راهِ حل: "{py}" -m pip install -r '
        f'{CODE_DIR / "requirements.txt"}\n'
        "   با نبودِ telethon سلف اصلاً بالا نمی‌آید (نه پنل، نه پیامِ "
        "آنلاین‌شدن). اگر پایتونِ سرویس با پایتونِ pip یکی نباشد همین "
        "اتفاق می‌افتد.")


def ensure_python():
    _boot_phase["phase"] = "محیطِ پایتون"
    if (os.environ.get("JAFJ_SKIP_VENV") or "").strip() in ("1", "true", "yes"):
        py = Path(sys.executable)
        log(f"venv رد شد (JAFJ_SKIP_VENV=1) — python={py}")
        if not deps_ok(py):
            install_deps(py)
        _require_deps(py)
        return py
    py = VENV_DIR / "bin" / "python"
    if not py.exists():
        log("ساختِ محیطِ مجازی…")
        if run([sys.executable, "-m", "venv", str(VENV_DIR)]).returncode != 0:
            log("⚠️ venv ساخته نشد — با پایتونِ سیستم ادامه می‌دهم")
            py = Path(sys.executable)
            if not deps_ok(py):
                install_deps(py)
            _require_deps(py)
            return py
        if not install_deps(py):
            die("نصبِ وابستگی‌ها شکست خورد (pip install -r requirements.txt)")
        stamp_file().write_text(req_hash(), encoding="utf-8")
        _require_deps(py)
        return py

    want = req_hash()
    have = stamp_file().read_text(encoding="utf-8").strip() if stamp_file().exists() else ""
    if want != have or not deps_ok(py):
        log("وابستگی‌ها تغییر کرده/ناقص است — نصبِ دوباره…")
        if install_deps(py):
            stamp_file().write_text(want, encoding="utf-8")
        elif not deps_ok(py):
            die(f"پکیج‌ها نصب نشدند و telethon هم قابلِ import نیست ({py}).\n"
                f'   راهِ حل: "{py}" -m pip install -r '
                f'{CODE_DIR / "requirements.txt"}')
        else:
            log("⚠️ pip install شکست خورد — ولی telethon هست، ادامه می‌دهم")
    else:
        log("وابستگی‌ها به‌روز است.")
    _require_deps(py)
    return py


# ─────────────────────────── ۳) محیط و داده ───────────────────────────
def build_env(py):
    env = os.environ.copy()
    env["PYTHONUNBUFFERED"] = "1"
    env["PYTHONIOENCODING"] = "utf-8"
    env["JAFJ_HOSTED"] = env.get("JAFJ_HOSTED", "1")
    env["JAFJ_HOST_LABEL"] = env.get("JAFJ_HOST_LABEL", "wispbyte")
    env["JAFJ_IMAGE_DIR"] = str(CODE_DIR)
    d = data_dir()
    env["JAFJ_APP_DIR"] = str(d)
    env["DATA_DIR"] = str(d)
    env["JAFJ_SELFBOT_REF"] = str(CODE_DIR / SELF_NAME)
    env["JAFJ_SUPERVISE"] = env.get("JAFJ_SUPERVISE", "1")
    env["JAFJ_KEEP_ALIVE"] = env.get("JAFJ_KEEP_ALIVE", "1")
    env["PORT"] = env.get("PORT", "8080")
    env["PATH"] = str(Path(py).parent) + os.pathsep + env.get("PATH", "")
    return env


def check_layout(env):
    """پوشه‌ی داده باید قابلِ نوشتن باشد و روی /tmp نباشد."""
    _boot_phase["phase"] = "پوشه‌ی داده"
    d = Path(env["DATA_DIR"])
    DATA_STATE["dir"] = str(d)
    try:
        d.mkdir(parents=True, exist_ok=True)
    except Exception as e:
        DATA_STATE.update(writable=False, why=str(e))
    probe = d / ".jafj_write_test"
    try:
        probe.write_text("ok", encoding="utf-8")
        probe.unlink()
        DATA_STATE["writable"] = True
    except Exception as e:
        DATA_STATE.update(writable=False, why=str(e))
        log(f"⛔ DATA_DIR نوشتنی نیست ({d}: {e}).")
        log("   داده به /tmp می‌رود تا لااقل بوت ادامه پیدا کند — ولی با هر "
            "ری‌استارت سشن/دیتابیس پاک می‌شود. یک Volume پایدار بده.")
        env["DATA_DIR"] = env["JAFJ_APP_DIR"] = "/tmp/jafj-data"
        Path(env["DATA_DIR"]).mkdir(parents=True, exist_ok=True)
        DATA_STATE.update(dir=env["DATA_DIR"], tmp=True)
    else:
        if str(d).startswith(("/tmp", "/var/tmp", "/dev/shm")):
            DATA_STATE["tmp"] = True
            log(f"⚠️ DATA_DIR روی {d} است — دادهٔ موقت؛ با هر ری‌استارت "
                "سشن/دیتابیس پاک می‌شود.")
    return env


# ─────────────────────────── ۴) اجرا ───────────────────────────
def main():
    check_only = bool(os.environ.get("JAFJ_CHECK_ONLY")) or "--check" in sys.argv
    log(f"host={os.environ.get('JAFJ_HOST_LABEL', 'wispbyte')} "
        f"python={sys.version.split()[0]} dir={HERE} boot={BOOT_VERSION}")
    boot_listener()
    _boot_phase["phase"] = "شروعِ بوت"

    sync_code()
    py = ensure_python()
    env = check_layout(build_env(py))
    log(f"code={CODE_DIR} data={env['DATA_DIR']} python={py} port={env['PORT']}"
        f" commit={CODE_STATE['commit'] or '?'}"
        + (" ⛔ کدِ قدیمی" if CODE_STATE["stale"] else ""))

    if check_only:
        _boot_phase["phase"] = "بررسی (--check) — اجرا نشد"
        log("حالتِ بررسی: اجرا نمی‌کنم. صفحه‌ی وضعیت ۱۰ دقیقه باز می‌ماند.")
        try:
            time.sleep(hold_seconds())
        except KeyboardInterrupt:
            pass
        boot_listener_stop()
        return 0

    _boot_phase["phase"] = "اجرای مدیر"
    entry = CODE_DIR / ENTRY_NAME
    boot_listener_stop()
    if entry.is_file():
        log("اجرای entrypoint ریپو (supervisor + manager_82.py)…")
        os.chdir(env["DATA_DIR"])
        os.execve("/bin/sh", ["sh", str(entry)], env)
    log(f"⚠️ {ENTRY_NAME} نیست — manager_82.py را مستقیم اجرا می‌کنم")
    os.chdir(str(CODE_DIR))
    os.execve(str(py), [str(py), str(CODE_DIR / MANAGER_NAME)], env)


if __name__ == "__main__":
    try:
        sys.exit(main())
    except KeyboardInterrupt:
        print("\nJAFJ-BOOT: خاموش شد.", flush=True)
        sys.exit(0)
    except SystemExit:
        raise
    except Exception as e:
        import traceback
        traceback.print_exc()
        die(f"{type(e).__name__}: {e}")
