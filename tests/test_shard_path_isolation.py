#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""حالتِ شارد: فایل‌های هر اکانت باید در پوشه‌ی **همان اکانت** بنشینند.

مشکلی که این تست می‌گیرد
────────────────────────
گزارشِ کاربر: «۹۵.py اصلاً ران نمی‌شود، مدیر انگار نمی‌تواند ارتباط بگیرد.»

`jafj_shardd.py` چند اکانت را در **یک** پروسه و هر کدام در یک رشته اجرا
می‌کند. به همین دلیل *نمی‌تواند* `os.chdir` کند (chdir سراسریِ پروسه است و
همه‌ی اکانت‌ها را با هم جابه‌جا می‌کند). راه‌حلش این است که ثابت‌های مسیرِ
۹۵.py را برای هر اکانت **مطلق** کند (`PATH_CONSTS` + `REL_PATHS` +
`_patch_paths`).

اما آن فهرست ناقص بود. مقایسه‌ی `PATH_CONSTS` با ثابت‌های واقعیِ ۹۵.py:

    SESSION CREDS_FILE AI_FILE LIMITS_FILE STATUS_FILE SETTINGS_FILE
    DB_FILE LOG_FILE RUN_LOCK                        ← پوشش داده شده
    BOOT_LOG BOOT_CRASH IP_FILE EXPECTED_ACCOUNT_FILE ← **جا افتاده بود**

نتیجه‌ی واقعی (با اجرای خودِ دیمن اثبات شد):

  • `jafj_boot.log` و `jafj_boot_error.txt` هرگز داخلِ پوشه‌ی اکانت ساخته
    نمی‌شدند؛ همه در cwdِ دیمن (یعنی `DATA_DIR` مدیر، چون
    `railway-start.sh` با `cd "$DATA_DIR"` مدیر را اجرا می‌کند) و **قاطیِ
    همه‌ی اکانت‌های شارد** نوشته می‌شدند. ولی مدیر، `tools/doctor_fa.py` و
    صفحه‌ی وضعیت دقیقاً `folder/jafj_boot.log` را می‌خوانند → «ردیِ بوت» و
    «علتِ بالا نیامدن» برای هر اکانت خالی می‌ماند. همان «مدیر نمی‌تواند
    ارتباط بگیرد».
  • اگر cwdِ مدیر پوشه‌ی ایمیج باشد (`/opt/jafj`) نوشتن اصلاً ممکن نیست و
    چون همه‌ی این نوشتن‌ها داخلِ `try/except` هستند، هیچ اثری هیچ‌جا
    نمی‌ماند.
  • `.jafj_expected_account` را مدیر داخلِ پوشه‌ی اکانت می‌نویسد ولی سلف با
    مسیرِ نسبی می‌خواندش → در شارد پیدایش نمی‌کرد → `expected_account_id()`
    صفر برمی‌گرداند → **نگهبانِ اکانت در حالتِ شارد عملاً خاموش بود**.
  • `jafj_ip.txt` مشترک بود → «IPِ خروجی عوض شده» به‌دروغ برای اکانتِ بعدی
    چاپ می‌شد.

باگِ دوم: الگوی `_rewrite` با `$` تمام می‌شد، یعنی فقط خطِ *بدونِ کامنت* را
می‌گرفت. ولی دو خط در ۹۵.py کامنتِ دنبالِ مقدار دارند (`LIMITS_FILE` و
`STATUS_FILE`)، پس نسخه‌ی پشتیبانِ بازنویسیِ سورس آن دو را بی‌صدا رد
می‌کرد.

باگِ سوم: `ShardDaemon`/`ForkDaemon` بدونِ `cwd=` اسپاون می‌شدند و cwdِ مدیر
را به ارث می‌بردند؛ حالا عمدی و نوشتنی است (`_daemon_cwd()` → DATA_DIR).

اجرا: python3 tests/test_shard_path_isolation.py  → باید `ALL: PASS` بدهد.
"""
import ast
import importlib.util
import json
import os
import re
import shutil
import subprocess
import sys
import tempfile
import time

HERE = os.path.dirname(os.path.abspath(__file__))
ROOT = os.path.dirname(HERE)
SELF = os.path.join(ROOT, "95.py")
SHARDD = os.path.join(ROOT, "jafj_shardd.py")
MANAGER = os.path.join(ROOT, "manager_82.py")

FAILS = []


def check(name, ok, extra=""):
    if ok:
        print("PASS", name)
    else:
        FAILS.append(name)
        print("FAIL", name, "" if extra == "" else "→ %r" % (extra,))


# ── بارگذاریِ ماژول‌ها ──
sspec = importlib.util.spec_from_file_location("shardd_iso", SHARDD)
S = importlib.util.module_from_spec(sspec)
sspec.loader.exec_module(S)

with open(SELF, encoding="utf-8") as f:
    SELF_SRC = f.read()
TREE = ast.parse(SELF_SRC)

# ثابت‌های مسیری که ۹۵.py واقعاً دارد (از روی AST، نه دستی)
MODULE_PATH_CONSTS = {}
for node in TREE.body:
    if isinstance(node, ast.Assign) and len(node.targets) == 1:
        t = node.targets[0]
        if isinstance(t, ast.Name) and isinstance(node.value, ast.Constant) \
                and isinstance(node.value.value, str):
            MODULE_PATH_CONSTS[t.id] = node.value.value


# ══════════════════════════════════════════════════════════════
#  T1: هر فایلِ jafj_* در ۹۵.py باید در فهرستِ شارد باشد
# ══════════════════════════════════════════════════════════════
# قاعده: هر ثابتِ سطحِ ماژول که مقدارش با «jafj» یا «.jafj» شروع شود یک فایلِ
# داده‌ی همین اکانت است. اگر روزی یکی اضافه شود و در PATH_CONSTS نیاید، شارد
# آن را در پوشه‌ی اکانت نمی‌گذارد — دقیقاً همان باگی که اینجا گرفته می‌شود.
jafj_consts = {k: v for k, v in MODULE_PATH_CONSTS.items()
               if v.startswith("jafj") or v.startswith(".jafj")}

missing_from_path_consts = sorted(k for k in jafj_consts if k not in S.PATH_CONSTS)
check("T1: همه‌ی ثابت‌های jafj_* در PATH_CONSTS هستند",
      not missing_from_path_consts, missing_from_path_consts)

missing_from_rel = sorted(k for k in jafj_consts if k not in S.REL_PATHS)
check("T1: همه‌ی ثابت‌های jafj_* در REL_PATHS هستند",
      not missing_from_rel, missing_from_rel)

wrong_rel = {k: (S.REL_PATHS.get(k), jafj_consts[k])
             for k in jafj_consts
             if k in S.REL_PATHS and S.REL_PATHS[k] != jafj_consts[k]}
check("T1: مقدارِ REL_PATHS با مقدارِ واقعیِ ۹۵.py یکی است",
      not wrong_rel, wrong_rel)

check("T1: دو فهرست هم‌پوشانیِ کامل دارند",
      set(S.PATH_CONSTS) == set(S.REL_PATHS),
      (sorted(set(S.PATH_CONSTS) ^ set(S.REL_PATHS))))

# چهارتایی که قبلاً جا افتاده بود — صریح قفل شود
for name in ("BOOT_LOG", "BOOT_CRASH", "IP_FILE", "EXPECTED_ACCOUNT_FILE"):
    check(f"T1: {name} پوشش داده می‌شود",
          name in S.PATH_CONSTS and name in S.REL_PATHS
          and name in MODULE_PATH_CONSTS,
          (name in S.PATH_CONSTS, name in S.REL_PATHS,
           MODULE_PATH_CONSTS.get(name)))


# ══════════════════════════════════════════════════════════════
#  T2: هیچ مسیرِ نسبیِ jafj_* به‌شکلِ لیترالِ درونِ تابع نمانده باشد
# ══════════════════════════════════════════════════════════════
# لیترالِ درونِ تابع را شارد نمی‌تواند پچ کند؛ باید ثابتِ سطحِ ماژول باشد.
CALLS = ("open", "isfile", "exists", "remove", "getmtime", "isdir", "lexists")
inline_hits = []
for node in ast.walk(TREE):
    if not isinstance(node, ast.Call):
        continue
    fn = node.func
    fname = fn.attr if isinstance(fn, ast.Attribute) else (
        fn.id if isinstance(fn, ast.Name) else "")
    if fname not in CALLS or not node.args:
        continue
    a = node.args[0]
    if isinstance(a, ast.Constant) and isinstance(a.value, str):
        v = a.value
        if (v.startswith("jafj") or v.startswith(".jafj")) and "/" not in v:
            inline_hits.append(f"line {node.lineno}: {fname}({v!r})")
check("T2: هیچ لیترالِ نسبیِ jafj_* مستقیم در open()/isfile() نیست",
      not inline_hits, inline_hits)


# ══════════════════════════════════════════════════════════════
#  T3: _rewrite خطِ دارای کامنت را هم می‌گیرد
# ══════════════════════════════════════════════════════════════
rew = S._rewrite(SELF_SRC, "/data/clients/777")
not_rewritten = []
for name, rel in S.REL_PATHS.items():
    # باید حداقل یک خطِ مطلق با همین نام وجود داشته باشد
    pat = re.compile(r'(?m)^%s = "%s/%s"' % (re.escape(name),
                                             re.escape("/data/clients/777"),
                                             re.escape(rel)))
    if not pat.search(rew):
        not_rewritten.append((name, rel))
check("T3: _rewrite هر ۱۳ ثابت را مطلق می‌کند (بدونِ استثنا)",
      not not_rewritten, not_rewritten)

# دو خطی که کامنتِ دنبالِ مقدار دارند — همان باگِ `$`
for name in ("LIMITS_FILE", "STATUS_FILE"):
    line = next((ln for ln in rew.splitlines()
                 if ln.startswith(name + " = ")), "")
    check(f"T3: {name} (خطِ کامنت‌دار) بازنویسی شد و کامنتش ماند",
          "/data/clients/777/" in line and "#" in line, line[:110])


# ══════════════════════════════════════════════════════════════
#  T4: اجرای واقعیِ دیمن — جداسازیِ پوشه‌ها
# ══════════════════════════════════════════════════════════════
FAKE_SELF = '''# -*- coding: utf-8 -*-
SESSION = "jafj"
CREDS_FILE = "jafj_creds.json"
AI_FILE = "jafj_ai.json"
LIMITS_FILE = "jafj_limits.json"     # کامنتِ دنبالِ مقدار (آزمونِ _rewrite)
STATUS_FILE = "jafj_status.json"     # کامنتِ دنبالِ مقدار
SETTINGS_FILE = "jafj_settings.json"
DB_FILE = "jafj.db"
LOG_FILE = "jafj.log"
RUN_LOCK = "jafj.run.lock"
BOOT_LOG = "jafj_boot.log"
BOOT_CRASH = "jafj_boot_error.txt"
IP_FILE = "jafj_ip.txt"
EXPECTED_ACCOUNT_FILE = ".jafj_expected_account"
import os
import time


def _is_our_selfbot(pid):
    return True


def expected_account_id():
    try:
        with open(EXPECTED_ACCOUNT_FILE, encoding="utf-8") as f:
            v = f.read().strip()
        return int(v) if v.isdigit() else 0
    except Exception:
        return 0


def main():
    # آنچه واقعاً resolve شده را بنویس تا آزمون بتواند مقایسه کند
    with open(BOOT_LOG, "a", encoding="utf-8") as f:
        f.write("resolved " + os.path.dirname(DB_FILE) + "\\n")
    with open(BOOT_CRASH, "w", encoding="utf-8") as f:
        f.write("crash of " + SESSION + "\\n")
    with open(IP_FILE, "w", encoding="utf-8") as f:
        f.write("1.2.3.4 0\\n")
    print("expected=" + str(expected_account_id()))
    # زنده بمان تا ping واقعاً «اکانتِ در حال اجرا» را بسنجد؛ سلفِ واقعی هم
    # که تا run_until_disconnected می‌ماند. quit با تزریقِ SystemExit
    # همین sleep را قطع می‌کند.
    time.sleep(30)
    return 0
'''

tmp = tempfile.mkdtemp(prefix="jafj_shard_iso_")
shard_cwd = os.path.join(tmp, "data")          # cwdِ دیمن (مثلِ DATA_DIR مدیر)
os.makedirs(shard_cwd, exist_ok=True)
fake_path = os.path.join(tmp, "95.py")
with open(fake_path, "w", encoding="utf-8") as f:
    f.write(FAKE_SELF)

uids = ("111", "222")
for u in uids:
    d = os.path.join(tmp, "clients", u)
    os.makedirs(d, exist_ok=True)
    with open(os.path.join(d, ".jafj_expected_account"), "w",
              encoding="utf-8") as f:
        f.write(u)

def _run_cmd(u):
    return {"cmd": "run",
            "cwd": os.path.join(tmp, "clients", u),
            "log": os.path.join(tmp, "clients", u, "run.log"),
            "uid": u}


py = sys.executable
env = dict(os.environ)
env["PYTHONIOENCODING"] = "utf-8"
out = ""
try:
    # Popen نه subprocess.run: `run` فقط رشته را **شروع** می‌کند و فوراً پاسخ
    # می‌دهد، پس اگر `quit` را پشتِ همه‌ی فرمان‌ها بفرستیم رشته‌ی اکانتِ دوم
    # هنوز کارش تمام نشده SystemExit می‌گیرد و آزمون به‌دروغ «نشت کرد»
    # می‌گیرد. بینِ فرمان‌ها عمداً صبر می‌کنیم.
    proc = subprocess.Popen(
        [py, SHARDD, "--selfbot", fake_path, "--max-accounts", "8",
         "--preload-telethon", "0"],
        stdin=subprocess.PIPE, stdout=subprocess.PIPE,
        stderr=subprocess.PIPE, text=True, cwd=shard_cwd, env=env)

    def _send(obj):
        proc.stdin.write(json.dumps(obj) + "\n")
        proc.stdin.flush()

    for u in uids:
        _send(_run_cmd(u))
        time.sleep(2.5)
    _send({"cmd": "ping", "request_id": 1})
    time.sleep(1.0)
    _send({"cmd": "quit"})
    out, _err = proc.communicate(timeout=90)
except Exception as e:                              # pragma: no cover
    check("T4: دیمن اجرا شد", False, f"{type(e).__name__}: {e}")

ok_msgs = [json.loads(ln) for ln in out.splitlines()
           if ln.strip().startswith("{")]
run_oks = [m for m in ok_msgs if m.get("ok") and "uid" in m and "accounts" not in m]
check("T4: دیمن هر دو اکانت را پذیرفت", len(run_oks) == 2,
      [m for m in ok_msgs])
pings = [m for m in ok_msgs if "accounts" in m]
check("T4: پینگ هر دو اکانت را زنده گزارش کرد",
      bool(pings) and sorted(pings[-1]["accounts"]) == sorted(uids),
      pings)

leaked = sorted(n for n in os.listdir(shard_cwd)
                if n.startswith("jafj") or n.startswith(".jafj"))
check("T4: هیچ فایلِ اکانتی در cwdِ دیمن نشت نکرد (قبلاً همه این‌جا بودند)",
      not leaked, leaked)

per_account_ok = True
detail = {}
for u in uids:
    d = os.path.join(tmp, "clients", u)
    want_dir = os.path.abspath(d)
    got = {}
    for n in ("jafj_boot.log", "jafj_boot_error.txt", "jafj_ip.txt"):
        got[n] = os.path.isfile(os.path.join(d, n))
    resolved = ""
    try:
        with open(os.path.join(d, "jafj_boot.log"), encoding="utf-8") as f:
            resolved = f.read().strip()
    except Exception:
        pass
    detail[u] = (got, resolved)
    if not all(got.values()) or resolved != f"resolved {want_dir}":
        per_account_ok = False
check("T4: هر اکانت boot.log/boot_error/ip_FILE خودش را در پوشه‌ی خودش دارد",
      per_account_ok, detail)
check("T4: مسیرهای ۹۵.py برای هر اکانت به پوشه‌ی همان اکانت resolve شدند",
      all(d[1] == "resolved " + os.path.abspath(os.path.join(tmp, "clients", u))
          for u, d in detail.items()),
      {u: d[1] for u, d in detail.items()})

# نگهبانِ اکانت باید per-account باشد، نه مشترک
def _read_log(u):
    try:
        with open(os.path.join(tmp, "clients", u, "run.log"),
                  encoding="utf-8") as f:
            return f.read()
    except Exception:
        return ""


guard_ok = True
for u in uids:
    if f"expected={u}" not in _read_log(u):
        guard_ok = False
check("T4: نگهبانِ اکانت فایلِ همان اکانت را می‌خواند (قبلاً عملاً خاموش بود)",
      guard_ok, {u: _read_log(u).strip()[:120] for u in uids})


# ══════════════════════════════════════════════════════════════
#  T5: envِ سراسری نمی‌تواند نگهبانِ همه‌ی اکانت‌ها را خراب کند
# ══════════════════════════════════════════════════════════════
# در شارد os.environ بینِ همه مشترک است؛ تابعِ اصلیِ ۹۵.py اول env را می‌خواند.
# shimِ تزریق‌شده باید فقط فایلِ همان اکانت را بخواند.
shim_dir = os.path.join(tmp, "shimacc")
os.makedirs(shim_dir, exist_ok=True)
with open(os.path.join(shim_dir, ".jafj_expected_account"), "w",
          encoding="utf-8") as f:
    f.write("555")
ns = {"EXPECTED_ACCOUNT_FILE": os.path.join(shim_dir, ".jafj_expected_account"),
      "__builtins__": __builtins__}
exec(S.EXPECTED_ACCOUNT_SHIM, ns)
old_env = os.environ.get("JAFJ_EXPECTED_ACCOUNT")
os.environ["JAFJ_EXPECTED_ACCOUNT"] = "999999"
try:
    got = ns["expected_account_id"]()
finally:
    if old_env is None:
        os.environ.pop("JAFJ_EXPECTED_ACCOUNT", None)
    else:
        os.environ["JAFJ_EXPECTED_ACCOUNT"] = old_env
check("T5: shimِ شارد envِ سراسری را نادیده می‌گیرد و فایلِ اکانت را می‌خواند",
      got == 555, got)
check("T5: EXPECTED_ACCOUNT_SHIM در Account.start تزریق می‌شود",
      "EXPECTED_ACCOUNT_SHIM" in open(SHARDD, encoding="utf-8").read())


# ══════════════════════════════════════════════════════════════
#  T6: مدیر دیمن را با cwdِ صریح و نوشتنی اسپاون می‌کند
# ══════════════════════════════════════════════════════════════
msrc = open(MANAGER, encoding="utf-8").read()
mtree = ast.parse(msrc)
fork_cls = next((n for n in mtree.body if isinstance(n, ast.ClassDef)
                 and n.name == "ForkDaemon"), None)
shard_cls = next((n for n in mtree.body if isinstance(n, ast.ClassDef)
                  and n.name == "ShardDaemon"), None)
has_method = bool(fork_cls) and any(
    isinstance(x, ast.FunctionDef) and x.name == "_daemon_cwd"
    for x in fork_cls.body)
check("T6: _daemon_cwd متدِ خودِ ForkDaemon است (نه تابعِ سطحِ ماژول)",
      has_method,
      "تابعِ سطحِ ماژول در هارنسِ ASTِ test_shard_ipc_responsiveness "
      "NameError می‌دهد")
check("T6: ShardDaemon از ForkDaemon ارث می‌برد (پس همان متد را دارد)",
      bool(shard_cls) and any(
          getattr(b, "id", "") == "ForkDaemon" for b in shard_cls.bases),
      [getattr(b, "id", "?") for b in (shard_cls.bases if shard_cls else [])])
# BASE_DIR یک گلوبالِ سطحِ ماژول است و در هارنسِ AST تعریف نمی‌شود؛ پس متد
# نباید به آن **ارجاع** دهد. روی گره‌های Name چک می‌کنیم نه روی متنِ سورس،
# چون توضیحِ خودِ docstring عمداً اسمش را می‌آورد.
_cwd_node = next(x for x in fork_cls.body
                 if getattr(x, "name", "") == "_daemon_cwd")
_global_refs = sorted({n.id for n in ast.walk(_cwd_node)
                       if isinstance(n, ast.Name)
                       and n.id not in ("os",)})
check("T6: متد به BASE_DIRِ سطحِ ماژول ارجاع نمی‌دهد",
      "BASE_DIR" not in _global_refs, _global_refs)

popen_blocks = re.findall(r"self\.proc = subprocess\.Popen\((.{0,400}?)\)\n",
                          msrc, re.S)
daemon_popens = [b for b in popen_blocks if "--selfbot" in b]
check("T6: هر دو دیمن (fork و shard) پیدا شدند", len(daemon_popens) >= 2,
      len(daemon_popens))
check("T6: هر دو با cwd=self._daemon_cwd() اسپاون می‌شوند (نه ارثی)",
      all("cwd=self._daemon_cwd()" in b for b in daemon_popens),
      ["cwd=" in b for b in daemon_popens])

shutil.rmtree(tmp, ignore_errors=True)
print("ALL: PASS" if not FAILS else f"FAILED: {FAILS}")
sys.exit(1 if FAILS else 0)
