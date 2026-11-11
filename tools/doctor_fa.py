#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""دکترِ جفج — «چرا ۹۵.py بالا نمی‌آید؟» را در یک اجرا جواب می‌دهد.

اجرا (روی همان سروری که ربات آن‌جاست، از همان پوشه‌ای که ربات اجرا می‌شود):

    python3 tools/doctor_fa.py

فقط کتابخانه‌ی استاندارد لازم است؛ telethon هم اگر نصب نباشد، همین را
🟥 گزارش می‌کند (همان علتی که ربات بالا نمی‌آید).

چیزهایی که چک می‌شوند:
  ۱) پایتون، پوشه، فایلِ ۹۵.py (وجود، هش، کامپایل) و نسخه‌ی مرجعِ ایمیج
  ۲) telethon / cryptg
  ۳) شبکه: DNS + TCP به DCهای تلگرام و مقایسه‌اش با ردیِ بوتِ خودِ ۹۵.py
     (همین چک است که می‌گوید مقصر **میزبان** است یا **کد**)
  ۴) اجازه‌ی نوشتن در پوشه (نبودِ آن = سشن/دیتابیس ساخته نمی‌شود)
  ۵) قفلِ اجرا و پروسه‌های ۹۵.py (دو نسخه = هر دو قطع می‌شوند)
  ۶) سشن و creds
  ۷) دیتابیس: سلامت، شمارشِ تبادل، آخرین رویدادها
  ۸) jafj_boot.log → تا کجا بالا آمد؟ / jafj_boot_error.txt → خطای بوت
  ۹) لاگ‌ها: Traceback/Errorِ آخر
  ۱۰) پوشه‌های مشتری (حالتِ مدیر)
  ۱۱) متغیرهای محیطی، دیسک و حافظه

کدِ خروج: ۰ = هیچ 🟥 نبود، ۱ = حداقل یک 🟥 (یعنی ربات با این وضعیت بالا
نمی‌آید).
"""
import glob
import os
import shutil
import sqlite3
import sys
import time

RED, YEL, GRN = "🟥", "🟨", "🟩"
ROWS = []


def add(level, title, *details):
    """یک نتیجه به گزارش اضافه کن (detail ها خط‌به‌خط زیرش چاپ می‌شوند)."""
    ROWS.append((level, title, [str(d) for d in details if d]))


def human_age(sec):
    try:
        sec = int(max(0, sec))
    except Exception:
        return "?"
    if sec < 90:
        return f"{sec} ثانیه"
    if sec < 5400:
        return f"{sec // 60} دقیقه"
    if sec < 172800:
        return f"{sec // 3600} ساعت"
    return f"{sec // 86400} روز"


def sha8(path):
    import hashlib
    try:
        with open(path, "rb") as f:
            return hashlib.sha256(f.read()).hexdigest()[:8]
    except Exception:
        return ""


def read_head(path, n=1):
    try:
        with open(path, encoding="utf-8", errors="ignore") as f:
            return [ln.rstrip("\n") for _, ln in zip(range(n), f)]
    except Exception:
        return []


def tail(path, n=12):
    try:
        with open(path, encoding="utf-8", errors="ignore") as f:
            return [ln.rstrip("\n") for ln in f.readlines()[-n:]]
    except Exception:
        return []


# ───────────── ۱) پایتون، پوشه، فایل‌ها ─────────────
def check_python():
    v = sys.version_info
    txt = f"{v.major}.{v.minor}.{v.micro} ({sys.executable})"
    if (v.major, v.minor) < (3, 8):
        add(RED, "پایتون قدیمی است", txt, "→ پایتون ۳.۹ یا بالاتر نصب کن")
    elif (v.major, v.minor) < (3, 9):
        add(YEL, "پایتون ۳.۸ است (کار می‌کند ولی حداقلی)", txt)
    else:
        add(GRN, "پایتون", txt)


def check_files():
    here = os.getcwd()
    add(GRN, "پوشه‌ی اجرا", here)
    src = os.path.join(here, "95.py")
    if not os.path.isfile(src):
        add(RED, "95.py در این پوشه نیست",
            f"در {here} فایلِ 95.py پیدا نشد.",
            "→ سرویس باید از پوشه‌ای اجرا شود که 95.py داخلش است؛ "
            "یا مسیرِ اجرای سرویس را درست کن.")
        return None
    size = os.path.getsize(src)
    mtime = os.path.getmtime(src)
    stamp = ""
    for ln in read_head(src, 4):
        if "STAMP" in ln:
            stamp = ln.strip("# ").strip()
            break
    add(GRN, "95.py هست", f"هش {sha8(src)} • {size} بایت • "
        f"آخرین تغییر {human_age(time.time() - mtime)} پیش")
    if stamp:
        add(GRN, "نسخه‌ی فایل", stamp[:90])
    if size < 200000:
        add(YEL, "95.py کوچک است", f"{size} بایت — احتمالاً ناقص آپلود شده")
    ref = os.environ.get("JAFJ_SELFBOT_REF") or "/opt/jafj/95.py"
    if os.path.isfile(ref) and os.path.abspath(ref) != os.path.abspath(src):
        h1, h2 = sha8(src), sha8(ref)
        if h1 and h2 and h1 != h2:
            add(YEL, "نسخه‌ی مرجعِ ایمیج با این فایل فرق دارد",
                f"{ref} → {h2} | پوشه → {h1}",
                "→ اگر 95.py پاک/خراب شود، مدیر نسخه‌ی قدیمیِ ایمیج را "
                "برمی‌گرداند و «مثل قبل» می‌شود؛ مرجع را هم به‌روز کن.")
    return src


def check_compile(src):
    if not src:
        return
    try:
        with open(src, encoding="utf-8") as f:
            code = f.read()
        compile(code, "95.py", "exec")
    except SyntaxError as e:
        add(RED, "95.py کامپایل نمی‌شود (SyntaxError)",
            f"خط {e.lineno}: {e.msg}",
            "→ فایل ناقص/اشتباه آپلود شده؛ همین فایل را از گیت دوباره بگیر.")
    except Exception as e:
        add(RED, "95.py خوانده/کامپایل نشد", f"{type(e).__name__}: {e}")
    else:
        add(GRN, "کامپایلِ 95.py", "بدونِ خطا")


# ───────────── ۲) وابستگی‌ها ─────────────
def check_deps():
    try:
        import telethon
        add(GRN, "telethon", getattr(telethon, "__version__", "?"))
    except Exception as e:
        add(RED, "telethon نصب نیست — ربات با همین بالا نمی‌آید",
            f"{type(e).__name__}: {e}",
            f'→ "{sys.executable}" -m pip install -r requirements.txt',
            "→ اگر نصبِ خودکار/این‌جا شکست خورد، همین پایتون را نصب کن "
            "(نه پایتونِ سیستم): pip باید مالِ همان interpreter باشد که "
            "سرویس را اجرا می‌کند.",
            "→ اگر pip به اینترنت دسترسی ندارد، بسته را جای دیگر بگیر و "
            "با همان مسیر نصب کن.")
    try:
        import cryptg  # noqa: F401
        add(GRN, "cryptg", "نصب است (رمزنگاری سریع‌تر، CPU کمتر)")
    except Exception:
        add(YEL, "cryptg نصب نیست", "بدونِ آن ربات کار می‌کند ولی CPU بیشتر "
            "می‌خورد → pip install cryptg")


def check_write():
    probe = os.path.join(os.getcwd(), ".jafj_write_test")
    try:
        with open(probe, "w", encoding="utf-8") as f:
            f.write("x")
        os.remove(probe)
        add(GRN, "اجازه‌ی نوشتن در پوشه", "هست")
    except Exception as e:
        add(RED, "پوشه قابلِ نوشتن نیست — سشن/دیتابیس ساخته نمی‌شود",
            f"{type(e).__name__}: {e}",
            "→ پوشه را روی یک دیسکِ قابلِ نوشتن بگذار (mount فقط‌خواندنی "
            "یا مجوزِ کاربرِ سرویس).")


# ───────────── ۴) قفل و پروسه‌ها ─────────────
def _proc_cmdline(pid):
    try:
        with open(f"/proc/{int(pid)}/cmdline", "rb") as f:
            return f.read().replace(b"\x00", b" ").decode("utf-8", "ignore").strip()
    except Exception:
        return ""


def _proc_cwd(pid):
    try:
        return os.readlink(f"/proc/{int(pid)}/cwd")
    except Exception:
        return ""


def _alive(pid):
    try:
        os.kill(int(pid), 0)
        return True
    except PermissionError:
        return True
    except Exception:
        return False


def looks_like_selfbot_proc(cmd):
    """آیا این cmdline واقعاً «python ... 95.py» است؟

    فقط چک‌کردنِ «95.py داخلِ خطِ فرمان هست» کافی نیست: خودِ شِل یا یک
    دستورِ `rm 95.py` هم همان رشته را دارد و گزارشِ «دو نسخه» می‌سازد.
    """
    parts = (cmd or "").split()
    if not parts:
        return False
    base = os.path.basename(parts[0]).lower()
    if not base.startswith("python"):
        return False
    return any(os.path.basename(tok) == "95.py" for tok in parts[1:])


def find_selfbots(here=None):
    """همه‌ی پروسه‌های python ... 95.py در این ماشین (pid, cmd, cwd)."""
    here = os.path.abspath(here or os.getcwd())
    out = []
    if not os.path.isdir("/proc"):
        return out
    me = os.getpid()
    for name in os.listdir("/proc"):
        if not name.isdigit():
            continue
        pid = int(name)
        if pid == me:
            continue
        cmd = _proc_cmdline(pid)
        if not looks_like_selfbot_proc(cmd):
            continue
        out.append((pid, cmd[:120], _proc_cwd(pid) or "?"))
    return out


def check_lock(here=None):
    here = os.path.abspath(here or os.getcwd())
    lock = os.path.join(here, "jafj.run.lock")
    procs = find_selfbots(here)
    mine = [p for p in procs if os.path.abspath(p[2]) == here]
    if not procs:
        add(RED, "هیچ پروسه‌ی 95.py در حال اجرا نیست",
            "یعنی ربات همین حالا خاموش است (نه اینکه کرش کرده باشد).",
            "→ سرویس/دستورِ شروع را چک کن: python main.py --check سپس "
            "python 95.py (یا از پنلِ مدیر: روشن کن)")
    elif not mine:
        add(YEL, "95.py اجرا می‌شود ولی از پوشه‌ی دیگری",
            *[f"pid {p[0]} | cwd={p[2]}" for p in procs],
            "→ همان پروسه به فایل/سشنِ همان پوشه کار می‌کند؛ پنل هم به همان "
            "حساب جواب می‌دهد. اگر انتظارِ این را نداشتی، آن را ببند.")
    else:
        add(GRN, "پروسه‌ی 95.py زنده است",
            *[f"pid {p[0]} | {p[1]}" for p in mine])
    if len(mine) > 1:
        add(RED, "بیش از یک 95.py روی همین پوشه",
            f"{len(mine)} پروسه — دو سلف روی یک سشن، تلگرام هر دو را قطع "
            "می‌کند و پنل هم جواب نمی‌دهد.",
            "→ همه را ببند و فقط یکی را اجرا کن.")
    if os.path.isfile(lock):
        try:
            with open(lock, encoding="utf-8") as f:
                pid = int((f.read() or "0").strip() or 0)
        except Exception:
            pid = 0
        if pid and _alive(pid):
            add(YEL, "فایلِ قفلِ اجرا موجود است و pid زنده است",
                f"{lock} → pid {pid}",
                "→ اگر آن pid واقعاً 95.py است، نسخه‌ی دومی اجرا نخواهد شد "
                "(این محافظت است، نه خرابی).")
        else:
            add(YEL, "فایلِ قفلِ اجرا مانده (pid مرده)",
                f"{lock} → pid {pid or '?'}",
                f"→ rm {lock}  (نسخه‌ی بعدی خودش هم پاکش می‌کند، اما با "
                "تأخیرِ ۹۰ ثانیه)")
    else:
        add(GRN, "قفلِ اجرا", "فایلی نیست (نشانه‌ی اجرای تمیز یا بسته‌بودنِ "
            "کامل)")


# ───────────── ۵) سشن و creds ─────────────
def check_session(here=None):
    here = os.path.abspath(here or os.getcwd())
    sess = glob.glob(os.path.join(here, "*.session")) + \
        glob.glob(os.path.join(here, "data", "*.session"))
    if not sess:
        add(YEL, "فایلِ سشن پیدا نشد",
            f"در {here} هیچ *.session نبود.",
            "→ اگر تازه نصب است، باید یک‌بار لاگین شود (شماره + کد). "
            "اگر قبلاً کار می‌کرد، سشن پاک شده و لاگینِ دوباره لازم است.")
    else:
        for p in sess[:5]:
            sz = os.path.getsize(p)
            age = human_age(time.time() - os.path.getmtime(p))
            add(GRN if sz > 100 else YEL, "سشن",
                f"{p} • {sz} بایت • آخرین تغییر {age} پیش")
    for cand in ("jafj_creds.json", os.path.join("data", "jafj_creds.json")):
        p = os.path.join(here, cand)
        if not os.path.isfile(p):
            continue
        try:
            import json
            with open(p, encoding="utf-8") as f:
                d = json.load(f)
            add(GRN, "creds", f"{p} • api_id="
                f"{'دارد' if d.get('api_id') else 'ندارد'} • phone="
                f"{'دارد' if d.get('phone') else 'خالی'}")
        except Exception as e:
            add(YEL, "creds خوانده نشد", f"{p}: {type(e).__name__}: {e}")
        break
    else:
        add(YEL, "jafj_creds.json نیست",
            "→ api_id/hash داخلِ 95.py هست؛ فایلِ creds در اولین اجرا ساخته "
            "می‌شود (شماره/کد فقط یک‌بار).")


# ───────────── ۶) دیتابیس ─────────────
def check_db(here=None):
    here = os.path.abspath(here or os.getcwd())
    cands = [p for p in (os.path.join(here, "jafj.db"),
                         os.path.join(here, "data", "jafj.db"))
             if os.path.isfile(p)]
    if not cands:
        found = glob.glob(os.path.join(here, "**", "*.db"), recursive=True)[:5]
        cands = found
    if not cands:
        add(YEL, "دیتابیس پیدا نشد", "→ با اولین اجرای موفق ساخته می‌شود")
        return
    p = cands[0]
    try:
        con = sqlite3.connect(f"file:{p}?mode=ro", uri=True, timeout=3)
        con.row_factory = sqlite3.Row
        ok = con.execute("PRAGMA quick_check").fetchone()[0]
        add(GRN if ok == "ok" else RED, "دیتابیس",
            f"{p} • {os.path.getsize(p) // 1024} کیلوبایت • quick_check="
            f"{ok}")
        try:
            c = {r["status"]: r["c"] for r in con.execute(
                "SELECT status,COUNT(*) c FROM exchange GROUP BY status")}
            unk = con.execute(
                "SELECT COUNT(*) FROM exchange WHERE unk_streak>0").fetchone()[0]
            add(GRN, "تبادل (شمارش)",
                " • ".join(f"{k}={v}" for k, v in sorted(c.items())) or "خالی",
                f"رکوردهای «چکِ نامشخص»: {unk}")
        except Exception as e:
            add(YEL, "جدولِ تبادل خوانده نشد", f"{type(e).__name__}: {e}")
        try:
            rows = con.execute(
                "SELECT ts,level,kind,substr(detail,1,70) d FROM events "
                "ORDER BY id DESC LIMIT 6").fetchall()
            if rows:
                add(GRN, "آخرین رویدادها", *[
                    f"{time.strftime('%m-%d %H:%M', time.localtime(r['ts']))} "
                    f"[{r['level']}] {r['kind']}: {r['d']}" for r in rows])
        except Exception:
            pass
        con.close()
    except Exception as e:
        add(RED, "دیتابیس باز نشد", f"{p} • {type(e).__name__}: {e}",
            "→ فایل قفل/خراب است؛ از بکاپِ آخر برگردان.")


# ───────────── ۷) ردیِ بوت ─────────────
def check_boot(here=None):
    here = os.path.abspath(here or os.getcwd())
    log = os.path.join(here, "jafj_boot.log")
    crash = os.path.join(here, "jafj_boot_error.txt")
    if os.path.isfile(crash):
        lines = [ln for ln in tail(crash, 40) if ln.strip()]
        first = lines[0] if lines else ""
        err = ""
        for ln in lines:
            if "Error" in ln or "Exception" in ln:
                err = ln
                break
        add(RED, "خطای بوت ثبت شده (آخرین‌بار)",
            f"{first}", (err[:160] if err else ""),
            f"→ فایلِ کامل: {crash}")
    if not os.path.isfile(log):
        add(YEL, "jafj_boot.log نیست",
            "یعنی این نسخه‌ی 95.py حتی یک‌بار هم مراحلِ بوت را ثبت نکرده "
            "(یا اصلاً اجرا نشده، یا نسخه‌ی قدیمی است).")
        return
    lines = [ln.strip() for ln in tail(log, 40) if ln.strip()]
    if not lines:
        add(YEL, "jafj_boot.log خالی است")
        return
    last = lines[-1]
    reached = any("آنلاین شد" in ln for ln in lines[-6:])
    age = human_age(time.time() - os.path.getmtime(log))
    add(GRN if reached else YEL,
        "ردیِ بوت: " + ("به پنل رسیده ✅" if reached else "به پنل نرسیده"),
        f"آخرین خط ({age} پیش): {last[:110]}",
        *[f"  {ln[:110]}" for ln in lines[-4:-1]])
    if not reached:
        add(YEL, "یعنی آخرین مرحله‌ی سالم همین بود",
            "→ مرحله‌ی بعد از این خط گیر کرده؛ متنِ خطا در "
            "jafj_boot_error.txt یا لاگِ سرویس است.")


# ───────────── ۸) لاگ‌ها ─────────────
def check_logs(here=None):
    here = os.path.abspath(here or os.getcwd())
    names = ["run.log", "service.log", "app.log", "railway.log"]
    seen = [os.path.join(here, n) for n in names
            if os.path.isfile(os.path.join(here, n))]
    seen += [p for p in glob.glob(os.path.join(here, "*.log"))[:4]
             if p not in seen and not p.endswith("jafj_boot.log")]
    hits = []
    for p in seen[:6]:
        for ln in tail(p, 40):
            low = ln.lower()
            if ("traceback" in low or "error" in low
                    or "modulenotfound" in low or "authkey" in low):
                hits.append(f"{os.path.basename(p)}: {ln.strip()[:120]}")
    if hits:
        add(YEL, "خطا در لاگ‌ها", *hits[-5:])
    elif seen:
        add(GRN, "لاگ‌ها", "خطای واضحی پیدا نشد: " +
            ", ".join(os.path.basename(p) for p in seen[:4]))
    else:
        add(YEL, "لاگ‌ای در این پوشه نیست",
            "→ خروجی را از پنلِ میزبان (Logs) ببین؛ حداقل خطِ اول باید "
            "«▶️ 95.py اجرا شد» باشد.")


# ───────────── ۹) پوشه‌های مشتری (حالتِ مدیر) ─────────────
def check_clients(here=None):
    here = os.path.abspath(here or os.getcwd())
    base = os.path.join(here, "data", "clients")
    if not os.path.isdir(base):
        return
    folders = [d for d in sorted(glob.glob(os.path.join(base, "*")))
               if os.path.isdir(d)][:12]
    if not folders:
        add(YEL, "پوشه‌ی مشتری‌ها خالی است", base)
        return
    lines = []
    for d in folders:
        uid = os.path.basename(d)
        has = os.path.isfile(os.path.join(d, "95.py"))
        pidf = os.path.join(d, ".jafj_self.pid")
        pid = 0
        if os.path.isfile(pidf):
            try:
                with open(pidf, encoding="utf-8") as f:
                    pid = int((f.read() or "0").strip() or 0)
            except Exception:
                pid = 0
        alive = bool(pid) and _alive(pid)
        b = os.path.join(d, "jafj_boot.log")
        last = tail(b, 1)
        lines.append(f"{uid}: 95.py={'✓' if has else '✗'} "
                     f"pid={pid or '—'}{' (زنده)' if alive else ''} "
                     f"| {last[0][:70] if last else 'بدونِ ردیِ بوت'}")
    add(GRN, "مشتری‌ها (حالتِ مدیر)", *lines)


# ───────────── ۱۰) محیط و منابع ─────────────
def check_env():
    keep = []
    for k, v in sorted(os.environ.items()):
        if not (k.startswith("JAFJ_") or k in ("PORT", "RAILWAY_ENVIRONMENT",
                                               "RAILWAY_SERVICE_NAME")):
            continue
        if any(s in k.upper() for s in ("TOKEN", "KEY", "SECRET", "PASS",
                                        "HASH")):
            v = "***"
        keep.append(f"{k}={v}")
    if keep:
        add(GRN, "متغیرهای محیطی", *keep[:12])
    else:
        add(YEL, "هیچ متغیرِ JAFJ_* ست نیست",
            "→ اگر مدیر انتظارِ JAFJ_* دارد (مثل JAFJ_NO_AUTO_LOGIN=1)، "
            "نبودشان رفتار را عوض می‌کند.")


def check_resources():
    try:
        u = shutil.disk_usage(os.getcwd())
        free_mb = u.free // (1024 * 1024)
        add(GRN if free_mb > 200 else RED, "دیسک",
            f"{free_mb} مگابایت آزاد از {u.total // (1024 * 1024)}",
            *([] if free_mb > 200 else ["→ فضا آزاد کن؛ با دیسکِ پر، "
                                        "دیتابیس/سشن خراب می‌شود"]))
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
            add(GRN if avail > 120 else YEL, "حافظه‌ی آزاد",
                f"{avail} مگابایت",
                *([] if avail > 120 else ["→ اگر JAFJ_MIN_FREE_MB بالاتر از "
                                          "این است، سلف عمداً بالا نمی‌آید."]))
    except Exception:
        pass


def check_network(here=None, timeout=3.5):
    """۱۱) شبکه: آیا این میزبان اصلاً به تلگرام می‌رسد؟

    رایج‌ترین علتِ «۹۵.py اجرا شد ولی نه پیامی در Saved Messages آمد نه پنل
    جواب داد» کد نیست — شبکه‌ی میزبان است. این تنها چکی است که آن دو را از
    هم جدا می‌کند، پس بدونِ آن دکتر ناقص بود.

    نکته‌ی مهم: باز بودنِ پورتِ TCP دلیلِ سالم بودنِ مسیر **نیست**. خیلی از
    میزبان‌ها/پروکسی‌ها اتصال را قبول می‌کنند و بعد می‌بندند (DPI/فیلتر)، و
    آن‌وقت TCP «باز» دیده می‌شود ولی دست‌دادنِ MTProto کامل نمی‌شود. پس
    نتیجه‌ی پروب با ردیِ بوتِ خودِ ۹۵.py مقایسه می‌شود.
    """
    import socket
    here = os.path.abspath(here or os.getcwd())
    dcs = (("DC2 آمستردام", "149.154.167.51"),
           ("DC4 آمستردام", "149.154.167.91"),
           ("DC1", "149.154.175.50"),
           ("DC3", "149.154.175.100"),
           ("DC5", "91.108.56.130"))
    try:
        socket.getaddrinfo("api.telegram.org", 443, proto=socket.IPPROTO_TCP)
        dns_ok = True
        add(GRN, "DNS", "api.telegram.org حل شد")
    except Exception as e:
        dns_ok = False
        add(RED, "DNS کار نمی‌کند", f"{type(e).__name__}: {e}",
            "→ بدونِ DNS هیچ اتصالی به تلگرام برقرار نمی‌شود؛ تنظیمِ "
            "شبکه/رزولورِ همین کانتینر را درست کن.")
    detail, n_open, n_closed = [], 0, 0
    for label, ip in dcs:
        t0 = time.time()
        try:
            s = socket.create_connection((ip, 443), timeout=timeout)
            try:
                s.close()
            except Exception:
                pass
            n_open += 1
            detail.append(f"{label} {ip}:443 باز ({int((time.time() - t0) * 1000)}ms)")
        except Exception as e:
            n_closed += 1
            detail.append(f"{label} {ip}:443 بسته — {type(e).__name__}")
    # آیا خودِ ۹۵.py روی اتصال شکست خورده است؟ (ردیِ بوتِ نسخه‌ی جدید)
    conn_fails, last_conn = 0, ""
    try:
        for ln in tail(os.path.join(here, "jafj_boot.log"), 60):
            if "شکستِ اتصال" in ln:
                conn_fails += 1
                last_conn = ln.strip()
    except Exception:
        pass

    if n_open == 0:
        add(RED, "شبکه: هیچ راهی به تلگرام نیست — مقصر میزبان است، نه کد",
            "هیچ‌کدام از DCهای تلگرام روی پورتِ 443 باز نشد:",
            *[f"  {d}" for d in detail],
            "→ فایروال/egress همین کانتینر باید TCP 443 به این IPها را باز "
            "کند. تا بسته است، ۹۵.py سالم هم هرگز آنلاین نمی‌شود.")
        return
    if conn_fails:
        add(RED, "شبکه: پورت باز است ولی MTProto کامل نمی‌شود — مقصر میزبان است",
            *[f"  {d}" for d in detail],
            f"۹۵.py خودش {conn_fails} بار روی اتصال شکست خورده:",
            f"  {last_conn[:150]}",
            "→ چیزی وسطِ راه اتصال را می‌بندد (پروکسیِ شفاف / DPI / فیلتر، یا "
            "میزبانی که فقط HTTP(S) را عبور می‌دهد).",
            "→ آزمونِ قطعی: همین سرویس را روی یک میزبان/شبکه‌ی دیگر بالا بیاور؛ "
            "آن‌جا پنل آمد یعنی کد سالم است و مشکل از شبکه‌ی این میزبان است.")
        return
    add(GRN, "شبکه", f"{n_open} DC از {len(dcs)} باز است"
        + ("" if dns_ok else " (DNS مشکل دارد)"),
        *[f"  {d}" for d in detail],
        "→ اگر پنل هنوز جواب نمی‌دهد، علت شبکه نیست: خطِ «ردیِ بوت» و "
        "jafj_boot_error.txt را ببین.")


def main():
    print("═" * 60)
    print("  🩺 دکترِ جفج — «چرا ۹۵.py بالا نمی‌آید؟»")
    print("═" * 60)
    check_python()
    src = check_files()
    check_compile(src)
    check_deps()
    check_network()
    check_write()
    check_lock()
    check_session()
    check_db()
    check_boot()
    check_logs()
    check_clients()
    check_env()
    check_resources()

    worst = 0
    for level, title, details in ROWS:
        print(f"\n{level} {title}")
        for d in details:
            print(f"    {d}")
        if level == RED:
            worst = 1
    reds = sum(1 for r in ROWS if r[0] == RED)
    yels = sum(1 for r in ROWS if r[0] == YEL)
    print("\n" + "─" * 60)
    if reds:
        print(f"نتیجه: {reds} موردِ 🟥 (ربات با این وضعیت بالا نمی‌آید) "
              f"• {yels} موردِ 🟨")
        print("اولین 🟥 را حل کن، بعد دوباره همین دستور را بزن.")
    else:
        print(f"نتیجه: هیچ 🟥 نیست • {yels} موردِ 🟨")
        print("اگر باز هم پنل جواب نمی‌دهد، خطِ «ردیِ بوت» بالا را بفرست.")
    print("═" * 60)
    return worst


if __name__ == "__main__":
    sys.exit(main())
