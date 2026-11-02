#!/usr/bin/env python3
# -*- coding: utf-8 -*-
# ═══════════════════════════════════════════════════════════════════════
#  JAFJ — main.py  (بوت‌استرپِ Wispbyte / هر میزبانِ «اپ پایتونی»)
#  شنونده‌ی PORT از ثانیه‌ی اول + آپدیت از گیت + venv + وابستگی‌ها + داده
#
#  این فایل همان main.pyای است که روی میزبان اجرا می‌شد، با شش اصلاح:
#   ۱) `telethon&gt;=1.34.0` → `telethon>=1.34.0`
#      (کاراکترهای HTML-escape در argvِ pip؛ نصبِ telethon همیشه شکست
#       می‌خورد و بعد `die` — یعنی «بالا نمی‌آید» بدونِ سرنخ)
#   ۲) توکنِ گیت دیگر در لاگ چاپ نمی‌شود (قبلاً آدرسِ clone با توکنِ
#      داخلش در لاگِ اپ می‌رفت)
#   ۳) شکستِ `git fetch` دیگر بی‌صدا نیست: ⛔ + کامیتِ فعلی + علت. و
#      `commit`/`stale` در پاسخِ /health می‌آید تا «آپدیتم رسید؟» با یک
#      curl معلوم شود
#   ۴) شکستِ نصبِ وابستگی‌ها ⇒ `die` با مسیرِ همان مفسر و دستورِ درست
#      (قبلاً «با نسخه‌ی فعلی ادامه می‌دهم» و بعد سلف بی‌telethon می‌مرد)
#   ۵) اگر DATA_DIR نوشتنی نباشد، به /tmp نمی‌پردازد و ادعا نمی‌کند همه
#      چیز خوب است: هشدارِ بزرگ + ثبت در /health (وگرنه هر ری‌استارت
#      سشن/دیتابیس را از دست می‌دهد)
#   ۶) اگر در ریشه‌ی اپ یک 95.py باشد که با code/95.py فرق کند، صریح
#      می‌گوید: «کدی که اجرا می‌شود code/ است؛ آپدیتِ فایلِ ریشه اثری
#      ندارد» — دقیقاً همان چیزی که «آپدیت کردم، عینِ قبل است» را می‌سازد
# ═══════════════════════════════════════════════════════════════════════
import hashlib
import os
import re
import shutil
import subprocess
import sys
import threading
from pathlib import Path

HERE = Path(__file__).resolve().parent
os.chdir(HERE)

BOOT_VERSION = "2026-11-02-slim2"
DEFAULT_REPO = "abolfazleoy/jfjj"
DEFAULT_BRANCH = "main"

CODE_DIR = HERE / "code"
VENV_DIR = HERE / "venv"
DEFAULT_DATA = HERE / "data"
MANAGER_NAME = "manager_82.py"
SELF_NAME = "95.py"
ENTRY_NAME = "railway-start.sh"

_boot_srv = None

# وضعیتِ کد و داده — در لاگ، در /health و در پیام‌های بوت دیده می‌شود.
CODE_STATE = {"commit": "", "branch": "", "stale": False, "why": ""}
DATA_STATE = {"dir": "", "writable": True, "tmp": False, "why": ""}
DEPS_STATE = {"ok": True, "python": ""}


def log(msg):
    print(f"JAFJ-BOOT: {msg}", flush=True)


def die(msg, code=1):
    print(f"JAFJ-BOOT: ❌ {msg}", flush=True)
    sys.exit(code)


def repo():
    return (os.environ.get("JAFJ_REPO") or DEFAULT_REPO).strip()


def branch():
    return (os.environ.get("JAFJ_BRANCH") or DEFAULT_BRANCH).strip() or DEFAULT_BRANCH


def token():
    return (os.environ.get("JAFJ_GIT_TOKEN") or "").strip()


def data_dir():
    return Path(os.environ.get("DATA_DIR") or DEFAULT_DATA).expanduser().resolve()


def repo_url():
    r, t = repo(), token()
    if "://" in r or r.startswith(("/", "./", "git@")):
        return r
    if t:
        return f"https://{t}@github.com/{r}.git"
    return f"https://github.com/{r}.git"


def redact(text):
    """توکن/رمز را قبل از لاگ کردن پاک کن.

    قبلاً `git clone https://<token>@github.com/...` عیناً در لاگ می‌رفت؛
    هر کسی که لاگِ اپ را می‌دید، دسترسیِ نوشتن به ریپو را می‌گرفت.
    """
    out = str(text)
    t = token()
    if t:
        out = out.replace(t, "***")
    out = re.sub(r"https://[^/\s@]+@", "https://***@", out)
    out = re.sub(r"(?i)(token|password|secret)(=|:)\s*\S+", r"\1\2***", out)
    return out


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


def git_head(folder=None):
    d = str(folder or CODE_DIR)
    try:
        r = subprocess.run(["git", "-C", d, "rev-parse", "--short", "HEAD"],
                           capture_output=True, text=True, timeout=20)
        return (r.stdout or "").strip() if r.returncode == 0 else ""
    except Exception:
        return ""


def file_sha8(path):
    try:
        with open(path, "rb") as f:
            return hashlib.sha256(f.read()).hexdigest()[:8]
    except Exception:
        return ""


# ── ۰) شنونده‌ی PORT از ثانیه‌ی اول ────────────────────────────────────
# بدونِ این، پنل تا پایانِ clone/venv/pip هیچ شنونده‌ای نمی‌بیند، اپ را
# «مرده» می‌داند و ری‌استارت می‌کند؛ هر ری‌استارت = IPِ تازه در حالی که
# اتصالِ قبلی باز است → AuthKeyDuplicated → کلیدِ سشن می‌سوزد.
def boot_listener(port=None):
    global _boot_srv
    if _boot_srv is not None:
        return _boot_srv
    port = port if port is not None else os.environ.get("PORT")
    if port in (None, "") or str(port).strip() == "":
        return None
    try:
        import json
        from http.server import BaseHTTPRequestHandler, HTTPServer

        class _H(BaseHTTPRequestHandler):
            def _body(self):
                return json.dumps({
                    "ok": True, "boot": True, "mode": "manager",
                    "version": BOOT_VERSION,
                    "commit": CODE_STATE.get("commit", ""),
                    "stale": bool(CODE_STATE.get("stale")),
                    "why": CODE_STATE.get("why", ""),
                    "deps": bool(DEPS_STATE.get("ok")),
                    "python": DEPS_STATE.get("python", ""),
                    "data": DATA_STATE.get("dir", ""),
                    "data_tmp": bool(DATA_STATE.get("tmp")),
                }, ensure_ascii=False).encode("utf-8")

            def do_GET(self):
                body = self._body()
                try:
                    self.send_response(200)
                    self.send_header("Content-Type", "application/json")
                    self.send_header("Content-Length", str(len(body)))
                    self.end_headers()
                    self.wfile.write(body)
                except Exception:
                    pass

            def do_HEAD(self):
                self.do_GET()

            def log_message(self, *a):
                pass

        srv = HTTPServer(("0.0.0.0", int(port)), _H)
        srv.daemon_threads = True
        threading.Thread(target=srv.serve_forever, daemon=True,
                         name="jafj-boot-http").start()
        _boot_srv = srv
        log(f"شنونده‌ی بوت روی 0.0.0.0:{port} — پنل از همین حالا ۲۰۰ می‌گیرد "
            "و وسطِ نصب ری‌استارت نمی‌کند")
        return srv
    except Exception as e:
        log(f"⚠️ شنونده‌ی بوت بالا نیامد ({type(e).__name__}: {e}) — ادامه "
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


# ── ۱) کد از گیت → ./code ─────────────────────────────────────────────
def root_vs_code_warning():
    """آیا 95.pyای که کاربر دستی آپدیت کرده، همان کدی است که اجرا می‌شود؟

    کدِ اجرا از `code/` می‌آید. اگر کسی فایل را در ریشه‌ی اپ عوض کند،
    هیچ اثری ندارد و از بیرون «عینِ قبل» به نظر می‌رسد. این تابع همین را
    با مقایسه‌ی هش دو فایل می‌گوید.
    """
    root_self = HERE / SELF_NAME
    code_self = CODE_DIR / SELF_NAME
    if not (root_self.is_file() and code_self.is_file()):
        return ""
    if os.path.abspath(root_self) == os.path.abspath(code_self):
        return ""
    h1, h2 = file_sha8(root_self), file_sha8(code_self)
    if not h1 or not h2 or h1 == h2:
        return ""
    return (f"⚠️ {root_self} با {code_self} فرق دارد "
            f"(هش {h1} ≠ {h2}).\n"
            f"   کدی که اجرا می‌شود {code_self} است (از گیت)؛ آپدیتِ فایلِ "
            f"ریشه اثری ندارد.\n"
            "   یا تغییر را به گیت بفرست، یا همان فایلِ درست را در code/ "
            "بگذار (و بدان که با هر fetch بعدی بازنویسی می‌شود).")


def sync_code():
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
            if run(["git", "clone", "--depth", "1", url, str(CODE_DIR)]).returncode != 0:
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


# ── ۲) venv + وابستگی‌ها ───────────────────────────────────────────────
def req_hash():
    f = CODE_DIR / "requirements.txt"
    return hashlib.sha256(f.read_bytes()).hexdigest() if f.is_file() else ""


def stamp_file():
    return VENV_DIR / ".reqhash"


def deps_ok(py):
    try:
        return subprocess.run([str(py), "-c", "import telethon"],
                              stdout=subprocess.DEVNULL,
                              stderr=subprocess.DEVNULL, timeout=60).returncode == 0
    except Exception:
        return False


def install_deps(py):
    req = CODE_DIR / "requirements.txt"
    if not req.is_file():
        log("requirements.txt نیست — telethon را نصب می‌کنم")
        # اینجا قبلاً «telethon&gt;=1.34.0» بود (HTML-escape) و pip همیشه
        # شکست می‌خورد؛ بعدش هم die.
        return run([str(py), "-m", "pip", "install",
                    "--disable-pip-version-check", "-q",
                    "telethon>=1.34.0"]).returncode == 0
    run([str(py), "-m", "pip", "install", "--disable-pip-version-check",
         "--upgrade", "pip"], quiet=True)
    return run([str(py), "-m", "pip", "install",
                "--disable-pip-version-check", "-r", str(req)]).returncode == 0


def _require_deps(py):
    """اگر telethon در این مفسر نیست، همین‌جا و با پیامِ روشن بمیر."""
    if deps_ok(py):
        DEPS_STATE.update(ok=True, python=str(py))
        return True
    DEPS_STATE.update(ok=False, python=str(py))
    die(f"telethon در این مفسر نصب نیست: {py}\n"
        f'    "{py}" -m pip install -r {CODE_DIR / "requirements.txt"}\n'
        "   با نبودِ telethon سلف اصلاً بالا نمی‌آید (نه پنل، نه پیامِ "
        "آنلاین‌شدن) — و اگر پایتونِ سرویس با پایتونِ pip یکی نباشد، همین "
        "اتفاق می‌افتد.")


def ensure_python():
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
                f'    "{py}" -m pip install -r '
                f'{CODE_DIR / "requirements.txt"}')
        else:
            log("⚠️ pip install شکست خورد — ولی telethon هست، ادامه می‌دهم")
    else:
        log("وابستگی‌ها به‌روز است.")
    _require_deps(py)
    return py


# ── ۳) محیط و داده ────────────────────────────────────────────────────
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
    """پوشه‌ی داده: قابلِ نوشتن باشد و روی /tmp نباشد (داده‌ی موقت = فاجعه)."""
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
        # قبلاً بی‌صدا به /tmp می‌پرید؛ یعنی هر ری‌استارت سشن و دیتابیس را
        # از دست می‌داد و از بیرون «سلف بالا نمی‌آید» دیده می‌شد.
        log("   بن‌بست: مسیری پایدار (Volume) با دسترسیِ نوشتن به DATA_DIR "
            "بده. تا آن موقع داده در /tmp می‌ماند و با هر ری‌استارت پاک "
            "می‌شود.")
        env["DATA_DIR"] = env["JAFJ_APP_DIR"] = "/tmp/jafj-data"
        Path(env["DATA_DIR"]).mkdir(parents=True, exist_ok=True)
        DATA_STATE.update(dir=env["DATA_DIR"], tmp=True)
    else:
        if str(d).startswith(("/tmp", "/var/tmp", "/dev/shm")):
            DATA_STATE["tmp"] = True
            log(f"⚠️ DATA_DIR روی {d} است — دادهٔ موقت. با هر ری‌استارت "
                "سشن/دیتابیس پاک می‌شود؛ یک Volume پایدار بده.")
    return env


# ── ۴) اجرا ───────────────────────────────────────────────────────────
def main():
    check_only = bool(os.environ.get("JAFJ_CHECK_ONLY")) or "--check" in sys.argv
    log(f"host={os.environ.get('JAFJ_HOST_LABEL', 'wispbyte')} "
        f"python={sys.version.split()[0]} dir={HERE} boot={BOOT_VERSION}")
    boot_listener()
    sync_code()
    py = ensure_python()
    env = check_layout(build_env(py))
    log(f"code={CODE_DIR} data={env['DATA_DIR']} python={py} port={env['PORT']}"
        f" commit={CODE_STATE['commit'] or '?'}"
        + (" ⛔ کدِ قدیمی" if CODE_STATE["stale"] else ""))
    if check_only:
        log("حالتِ بررسی (--check): اجرا نمی‌کنم.")
        boot_listener_stop()
        return 0
    entry = CODE_DIR / ENTRY_NAME
    if entry.is_file():
        log("اجرای entrypoint ریپو (supervisor + manager_82.py)…")
        boot_listener_stop()
        os.chdir(env["DATA_DIR"])
        os.execve("/bin/sh", ["sh", str(entry)], env)
    log(f"⚠️ {ENTRY_NAME} نیست — manager_82.py را مستقیم اجرا می‌کنم")
    boot_listener_stop()
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
