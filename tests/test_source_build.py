#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""بیلدِ سورسی (بدون Docker) — همان خطای Enzonic Deploy:

    "Dockerfile projects cannot be built yet: Enzonic Deploy builds Node.js,
     Bun, Python and Go apps from source. Set the root directory to the app's
     folder or pick a framework preset in the project settings"

پیام از کد نیست، از presetِ پروژه است؛ ولی فقط وقتی می‌شود preset را روی
Python گذاشت که ریپو **واقعاً** بدون ایمیج بالا بیاید. این تست همان را قفل
می‌کند:

  ۱) فایل‌های ورودیِ بیلدِ سورسی موجود و سازگارند: `Procfile`،
     `.python-version`، `nixpacks.toml`، `requirements.txt` — و همه به یک
     اسکریپتِ موجود اشاره می‌کنند (`start.sh`).
  ۲) نسخهٔ پایتون، همان نسخه‌ای است که `Dockerfile` پین کرده (۳.۱۱).
  ۳) `start.sh` خودش منطق ندارد: `hostless-start.sh` را صدا می‌زند و
     `JAFJ_HOST_LABEL` را برای /diag ست می‌کند.
  ۴) اجرای واقعی از یک «چک‌اوت» بدون `/opt/jafj`: کد از همان پوشه اجرا
     می‌شود و `DATA_DIR` پوشه‌ای جدا از کد انتخاب می‌کند (وگرنه هر دیپلوی
     داده را پاک می‌کند).
  ۵) با `JAFJ_HOSTED=1`، خروجِ ۰ به‌عنوان کرش شمرده می‌شود — همان
     «The process stopped soon after it started · Exit code 0».

اجرا:  python tests/test_source_build.py     (خریدِ ALL: PASS)
"""
import os
import re
import shutil
import socket
import stat
import subprocess
import sys
import tempfile
from pathlib import Path

REPO = Path(__file__).resolve().parents[1]
ROOT = Path(tempfile.gettempdir()) / "jafj_source_build"
FAILS = []

ENTRY_SCRIPTS = ("start.sh", "hostless-start.sh", "railway-start.sh")


def check(cond, label):
    print(("PASS  " if cond else "FAIL  ") + label)
    if not cond:
        FAILS.append(label)
    return bool(cond)


def free_port():
    s = socket.socket()
    s.bind(("127.0.0.1", 0))
    p = s.getsockname()[1]
    s.close()
    return p


def clean_env():
    env = dict(os.environ)
    for k in list(env):
        if k.startswith("JAFJ_") or k in (
                "PORT", "DATA_DIR", "DATA_GITHUB_TOKEN", "DATA_GITHUB_REPO",
                "BACKUP_EVERY", "BACKUP_CHAT", "BOT_TOKEN", "PYTHON",
                "RAILWAY_ENVIRONMENT", "RENDER", "BLITZ", "HOSTLESS",
                "HEROKU_APP_NAME"):
            env.pop(k, None)
    return env


# ── ۱) فایل‌های بیلدِ سورسی ─────────────────────────────────────────────────
def check_build_files():
    print("--- 1: فایل‌های بیلدِ سورسی (Enzonic: Python preset) ---")

    proc = REPO / "Procfile"
    if check(proc.exists(), "Procfile در ریشه هست (پلتفرمِ بی‌start-command) "):
        line = proc.read_text(encoding="utf-8").strip()
        m = re.match(r"^web:\s*sh\s+(\S+)$", line)
        check(bool(m), "Procfile یک فرمانِ web تعریف می‌کند: %s" % line)
        if m:
            check((REPO / m.group(1)).exists(),
                  "فایلی که Procfile اجرا می‌کند واقعاً هست (%s)" % m.group(1))

    ver = REPO / ".python-version"
    if check(ver.exists(), ".python-version پین شده (بیلدهای Nixpacks/uv/pyenv)"):
        v = ver.read_text(encoding="utf-8").strip()
        check(re.match(r"^3\.11(\.\d+)?$", v) is not None,
              "نسخهٔ پایتون 3.11 است (%s)" % v)
        docker = (REPO / "Dockerfile").read_text(encoding="utf-8")
        check("python:3.11" in docker,
              "همان نسخه‌ای که Dockerfile پین کرده (python:3.11-slim)")

    nix = REPO / "nixpacks.toml"
    if check(nix.exists(), "nixpacks.toml هست (خطای «No start command»)"):
        t = nix.read_text(encoding="utf-8")
        m = re.search(r'^\s*cmd\s*=\s*"sh\s+([^"]+)"', t, re.M)
        check(bool(m), 'nixpacks یک cmd دارد (%s)' % (m.group(0) if m else "—"))
        if m:
            check((REPO / m.group(1)).exists(),
                  "اسکریپتِ start در nixpacks موجود است (%s)" % m.group(1))

    req = REPO / "requirements.txt"
    if check(req.exists(), "requirements.txt هست (منبعِ نصبِ بیلدِ سورسی)"):
        t = req.read_text(encoding="utf-8")
        check("telethon" in t.lower(), "telethon در requirements هست")
        check("tzdata" in t.lower(), "tzdata پین شده (ساعتِ سلام/بکاپ)")

    for name in ENTRY_SCRIPTS:
        p = REPO / name
        if not check(p.exists(), "%s در ریشه‌ی ریپو هست" % name):
            return False
        sh = subprocess.run(["sh", "-n", str(p)], capture_output=True, text=True)
        check(sh.returncode == 0, "سینتکس sh سالم است: %s" % name)
    return True


# ── ۲) start.sh: ورودیِ بی‌منطق، فقط یک برچسب ──────────────────────────────
def check_start_script():
    print("--- 2: start.sh (ورودیِ قابل‌حمل) ---")
    p = REPO / "start.sh"
    t = p.read_text(encoding="utf-8")
    check('exec sh "$HERE/hostless-start.sh"' in t,
          "همان یک نقطه‌ی حقیقت: hostless-start.sh را صدا می‌زند")
    check("JAFJ_HOSTED" in t, "پروسه را hosted اعلام می‌کند (سرویس نباید بمیرد)")
    check("JAFJ_HOST_LABEL" in t, "برچسبِ میزبان برای /diag می‌دهد")
    code_only = "\n".join(l for l in t.splitlines() if not l.lstrip().startswith("#"))
    check("/opt/jafj" not in code_only,
          "به ایمیج وابسته نیست (روی چک‌اوتِ سورسی هم کار می‌کند)")
    check("PORT=" not in t, "PORT را از پلتفرم می‌گیرد، خودش ست نمی‌کند")

    mode = p.stat().st_mode
    check(bool(mode & stat.S_IXUSR), "اجرایی (`./start.sh`) هم هست")

    docker = (REPO / "Dockerfile").read_text(encoding="utf-8")
    check("start.sh" in docker,
          "Dockerfile هم آن را داخل ایمیج می‌برد (یک ورودی برای هر دو حالت)")


# ── ۳–۵) اجرای واقعی از یک چک‌اوتِ سورسی (بدون /opt/jafj) ──────────────────
def build_checkout(manager_body):
    """چیزی که یک پلتفرمِ سورسی می‌سازد: کپیِ ریپو + pip install. بدون /opt/jafj."""
    shutil.rmtree(ROOT, ignore_errors=True)
    code = ROOT / "app"
    code.mkdir(parents=True, exist_ok=True)
    for name in ("railway-start.sh", "hostless-start.sh", "start.sh",
                 "Procfile", "requirements.txt", ".python-version"):
        src = REPO / name
        if src.exists():
            shutil.copy2(src, code / name)
    # کدها: 95.py واقعی، مدیرِ جعلی (تست نباید به تلگرام وصل شود)
    shutil.copy2(REPO / "95.py", code / "95.py")
    (code / "manager_82.py").write_text(manager_body, encoding="utf-8")
    if (REPO / "tools").is_dir():
        shutil.copytree(REPO / "tools", code / "tools")
    return code


def run_start(code, extra_env, timeout=120):
    env = clean_env()
    env.update({"PORT": str(free_port()),
                "HOME": str(ROOT / "home"),
                "PATH": os.environ.get("PATH", "/usr/local/bin:/usr/bin:/bin")})
    (ROOT / "home").mkdir(parents=True, exist_ok=True)
    # PYTHON: تست با همان مفسرِ خودش اجرا شود، نه با python3 سیستم
    env["PYTHON"] = sys.executable
    # /opt/jafj در این محیط نیست — اگر اسکریپت به آن تکیه کند، همین‌جا لو می‌رود
    env["JAFJ_IMAGE_DIR"] = str(code)
    env.pop("JAFJ_IMAGE_DIR")          # بگذار خودش تصمیم بگیرد
    env.update(extra_env)
    p = subprocess.run(["sh", "start.sh"], cwd=str(code), env=env,
                       capture_output=True, text=True, timeout=timeout)
    return p.returncode, p.stdout + p.stderr, env


NOOP_MANAGER = (
    "import os, sys, pathlib\n"
    "print('STUB manager up', flush=True)\n"
    "pathlib.Path(os.environ['STUB_OUT']).write_text(\n"
    "    'code=%s\\ndata=%s' % (os.environ.get('JAFJ_IMAGE_DIR'),\n"
    "                          os.environ.get('DATA_DIR')), encoding='utf-8')\n"
    "sys.exit(0)\n"
)


def check_source_run():
    print("--- 3: اجرا از چک‌اوت (کد از همان پوشه، داده جای دیگر) ---")
    data = ROOT / "data"
    data.mkdir(parents=True, exist_ok=True)
    stub = ROOT / "stub.txt"
    code = build_checkout(NOOP_MANAGER)

    rc, out, _ = run_start(code, {
        "DATA_DIR": str(data),
        "STUB_OUT": str(stub),
        "JAFJ_SUPERVISE": "0",         # بدون ناظر: فقط مسیرِ کد/داده سنجیده شود
    })
    print("\n".join(l for l in out.splitlines()
                    if "code=" in l or "HOSTLESS:" in l)[:1200])
    check(rc == 0, "start.sh بدون Docker و بدون /opt/jafj اجرا شد (rc=%s)" % rc)
    check(stub.exists(), "مدیرِ داخلِ چک‌اوت اجرا شد")
    if stub.exists():
        got = stub.read_text(encoding="utf-8")
        check("code=%s" % code in got,
              "کد از خودِ چک‌اوت اجرا می‌شود، نه از /opt/jafj")
        check("data=%s" % data in got, "DATA_DIR همان چیزی است که داده شده")

    print("--- 4: انتخابِ پوشهٔ داده وقتی DATA_DIR ست نشده ---")
    stub.unlink()
    rc, out, _ = run_start(code, {
        "STUB_OUT": str(stub),
        "JAFJ_SUPERVISE": "0",
    })
    check(stub.exists(), "بدون DATA_DIR هم بالا می‌آید (rc=%s)" % rc)
    if stub.exists():
        got = stub.read_text(encoding="utf-8")
        m = re.search(r"^data=(.+)$", got, re.M)
        chosen = (m.group(1) if m else "").strip()
        check(bool(chosen), "یک پوشهٔ داده انتخاب شد (%s)" % chosen)
        check(os.path.realpath(chosen) != os.path.realpath(str(code)),
              "پوشهٔ داده روی کد نیست (وگرنه هر دیپلوی داده را پاک می‌کند)")
        check("data is living next to the code" not in out,
              "هشدارِ «داده کنارِ کد» داده نشد")
        check(os.access(chosen, os.W_OK), "پوشهٔ داده قابل‌نوشتن است")

    print("--- 5: «Exit code 0» روی میزبان = کرش (پروسه باید بماند) ---")
    code = build_checkout(NOOP_MANAGER)
    stub2 = ROOT / "stub2.txt"
    rc, out, _ = run_start(code, {
        "DATA_DIR": str(data),
        "STUB_OUT": str(stub2),
        "JAFJ_MAX_CRASHES": "1",       # تست سریع: بعد از یک کرش تسلیم شود
        "JAFJ_NAP_BASE": "0",
        "JAFJ_COOL_DOWN": "0",
    })
    check("counts as a crash" in out,
          "خروجِ ۰ به‌عنوان کرش لاگ شد (پیامِ گمراه‌کنندهٔ پلتفرم تکرار نمی‌شود)")
    check(rc != 0, "کدِ خروج غیرصفر است تا پلتفرم خطا را ببیند (rc=%s)" % rc)


def main():
    ok = check_build_files()
    check_start_script()
    if ok:
        check_source_run()
    else:
        print("SKIP  اجرای واقعی (فایل‌های ورودی ناقص‌اند)")
    print()
    if FAILS:
        print("FAILS: %d" % len(FAILS))
        for f in FAILS:
            print("  - " + f)
        return 1
    print("ALL: PASS")
    return 0


if __name__ == "__main__":
    sys.exit(main())
