#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""jafj_shardd — چند اکانت در **یک** پروسه (هر اکانت در namespace و رشته‌ی خودش).

چرا: در حالتِ fork هر اکانت یک پروسه‌ی جدا است و صفحه‌هایی که فرزند دست
می‌زند (refcountها، گلوبال‌ها، sqlite، asyncio) در هر فرزند **خصوصی** می‌شوند:
اندازه‌گیری ~۱۱.۲ مگابایت به‌ازای هر اکانت. در یک پروسه با namespace جدا،
همان اکانت‌ها ~۳.۳ مگابایت می‌شوند (`WISPBYTE_FA.md` §۱۳).

مکانیزم: فایلِ `95.py` برای هر اکانت با مسیرهای **مطلق** بازنویسی و در یک
namespace جدا `exec` می‌شود؛ بعد `main()` همان namespace در یک رشته فراخوانی
می‌شود (هر رشته `asyncio.run` خودش را دارد). کدآبجکت‌ها، کتابخانه‌ها و همه‌ی
صفحه‌های فقط‌خواندنی مشترک می‌مانند.

پروتکل: خط‌به‌خط JSON روی stdin/stdout (همان قراردادِ `jafj_forkd.py`) —

    {"cmd":"run","cwd":"/…/clients/123","log":"/…/run.log","uid":"123"}
      → {"ok":true,"pid":<shard pid>,"uid":"123"}
    {"cmd":"stop","uid":"123"}     → {"ok":true,"uid":"123"}
    {"cmd":"ping","request_id":N} → {"ok":true,"accounts":[…],"request_id":N}
    {"cmd":"ping"}                 → {"ok":true,"accounts":[…]} (قدیمی)
    {"cmd":"quit"}                 → خروج
    رویداد: {"event":"exit","uid":"123","code":0}

محدودیت‌های عمدی:

* یک شارد = یک نقطه‌ی شکست؛ برای همین اندازه‌اش (`--max-accounts`، پیش‌فرض
  ۸) کوچک است: اگر پروسه بمیرد فقط همان ۸ اکانت تا ری‌استارتِ بعدی می‌خوابند.
* `stop` یک اکانت با تزریقِ `SystemExit` به رشته‌اش انجام می‌شود؛ اگر در
  ۵ ثانیه نمرد، کلِ شارد بسته می‌شود (مدیر بقیه را دوباره بالا می‌آورد) —
  بهتر از این است که سلفی روشن بمانَد که مدیر فکر می‌کند خاموش است.
"""
import argparse
import ast
import json
import os
import re
import sys
import threading
import time

# ثابت‌های مسیر در 95.py — در شارد باید مطلق باشند، وگرنه همه‌ی اکانت‌ها
# روی یک فایل می‌نویسند (سشنِ مشترک = سوزاندنِ کلید).
PATH_CONSTS = ("SESSION", "CREDS_FILE", "AI_FILE", "LIMITS_FILE",
               "STATUS_FILE", "SETTINGS_FILE", "DB_FILE", "LOG_FILE",
               "RUN_LOCK")

# در حالتِ شارد، «قفلِ زنده» را باید بتوانیم از پروسه‌ی شارد تشخیص دهیم؛
# وگرنه `_is_our_selfbot` می‌گوید «قفل مرده است»، قفل را پاک می‌کند و
# نسخه‌ی دوم روی همان اکانت بالا می‌آید (= AuthKeyDuplicated).
LOCK_OWNER_SHIM = '''

def _is_our_selfbot(pid):          # ← تزریق‌شده توسطِ jafj_shardd
    try:
        with open("/proc/%d/cmdline" % int(pid), "rb") as f:
            cmd = f.read().replace(bytes([0]), b" ").decode("utf-8", "ignore")
    except Exception:
        return True
    return ("95.py" in cmd) or ("jafj_shardd" in cmd) or ("jafj_forkd" in cmd)
'''


def _reply(obj, lock):
    with lock:
        try:
            sys.stdout.write(json.dumps(obj, ensure_ascii=False) + "\n")
            sys.stdout.flush()
        except Exception:
            pass


# نامِ ثابت → مقدارِ پیش‌فرضِ نسبی در 95.py
REL_PATHS = {
    "SESSION": "jafj",
    "CREDS_FILE": "jafj_creds.json",
    "AI_FILE": "jafj_ai.json",
    "LIMITS_FILE": "jafj_limits.json",
    "STATUS_FILE": "jafj_status.json",
    "SETTINGS_FILE": "jafj_settings.json",
    "DB_FILE": "jafj.db",
    "LOG_FILE": "jafj.log",
    "RUN_LOCK": "jafj.run.lock",
}


def _fix_defaults(fn, mapping):
    """آرگومان‌های پیش‌فرضی که با مقدارِ نسبی بسته شده‌اند را مطلق کن.

    مهم: `def __init__(self, path=DB_FILE)` مقدار را **هنگامِ تعریف** قفل
    می‌کند؛ پس پچِ گلوبال به‌تنهایی کافی نیست.
    """
    try:
        d = getattr(fn, "__defaults__", None)
        if d:
            nd = tuple(mapping.get(x, x) if isinstance(x, str) else x for x in d)
            if nd != d:
                fn.__defaults__ = nd
        kw = getattr(fn, "__kwdefaults__", None)
        if kw:
            for k, v in list(kw.items()):
                if isinstance(v, str) and v in mapping:
                    kw[k] = mapping[v]
    except Exception:
        pass


def _patch_paths(ns, folder):
    """(mapping) — مسیرهای همین اکانت را داخلِ namespace مطلق کن."""
    import types
    mapping = {}
    for name, rel in REL_PATHS.items():
        abs_p = os.path.join(folder, rel)
        ns[name] = abs_p
        mapping[rel] = abs_p
    for obj in list(ns.values()):
        if isinstance(obj, types.FunctionType):
            _fix_defaults(obj, mapping)
        elif isinstance(obj, type):
            for v in vars(obj).values():
                if isinstance(v, types.FunctionType):
                    _fix_defaults(v, mapping)
    return mapping


def _rewrite(src, folder):
    """مسیرهای نسبیِ 95.py را برای همین اکانت مطلق کن."""
    out = src
    for name in PATH_CONSTS:
        out = re.sub(r'(?m)^(%s = )"([^"]*)"$' % name,
                     lambda m: '%s"%s/%s"' % (m.group(1), folder, m.group(2)),
                     out, count=1)
    return out


def _dep_names(src):
    names = set()
    try:
        for node in ast.walk(ast.parse(src)):
            if isinstance(node, ast.Import):
                for a in node.names:
                    names.add(a.name.split(".")[0])
            elif isinstance(node, ast.ImportFrom) and node.level == 0 and node.module:
                names.add(node.module.split(".")[0])
    except Exception:
        pass
    return names


class Account:
    """یک اکانت داخلِ شارد: رشته + لاگِ خودش + وضعیت."""

    def __init__(self, uid, cwd, log_path, code, fallback_code=None):
        self.uid = str(uid)
        self.cwd = str(cwd)
        self.log_path = str(log_path or "")
        self.code = code                 # کدِ مشترک (یک بار کامپایل)
        self.fallback_code = fallback_code   # نسخه‌ی بازنویسی‌شده (اگر پچ نشد)
        self.thread = None
        self.exited = None        # کدِ خروج وقتی تمام شد
        self._log = None

    def write(self, text):
        try:
            if self._log is None and self.log_path:
                self._log = open(self.log_path, "a", encoding="utf-8",
                                 buffering=1)
            if self._log is not None:
                self._log.write(text)
                self._log.flush()
        except Exception:
            pass

    def _mk_print(self):
        def _p(*args, **kwargs):
            try:
                text = " ".join(str(a) for a in args)
            except Exception:
                text = ""
            end = kwargs.get("end", "\n")
            self.write(text + (end if isinstance(end, str) else "\n"))
        return _p

    def start(self):
        def _run():
            code = 1
            try:
                ns = {"__name__": "jafj_acc_%s" % self.uid,
                      "__file__": self.path, "__builtins__": __builtins__}
                exec(self.code, ns)
                # مسیرهای این اکانت (سشن/دیتابیس/قفل) مطلق می‌شوند.
                _patch_paths(ns, self.cwd)
                if not str(ns.get("DB_FILE") or "").startswith(self.cwd):
                    # اگر 95.py عوض شد و پچ جواب نداد: نسخه‌ی بازنویسی‌شده.
                    self.write("  ⚠️ پچِ مسیرها نگرفت — با کامپایلِ جداگانه\n")
                    ns = {"__name__": "jafj_acc_%s" % self.uid,
                          "__file__": self.path, "__builtins__": __builtins__}
                    exec(self.fallback_code, ns)
                # اصلاح‌های مخصوصِ شارد، بعد از اجرای بدنه و قبل از main():
                ns["print"] = self._mk_print()
                exec(LOCK_OWNER_SHIM, ns)
                r = ns["main"]()
                if hasattr(r, "__await__"):
                    import asyncio
                    r = asyncio.run(r)
                code = 0 if r is None else int(r or 0)
            except SystemExit as e:
                code = e.code if isinstance(e.code, int) else (
                    0 if e.code is None else 1)
            except KeyboardInterrupt:
                code = 0
            except BaseException:
                try:
                    import traceback
                    self.write(traceback.format_exc())
                except Exception:
                    pass
                code = 1
            finally:
                self.exited = code
                try:
                    if self._log is not None:
                        self._log.close()
                except Exception:
                    pass
        self.thread = threading.Thread(target=_run, name="acc-%s" % self.uid,
                                       daemon=True)
        self.thread.start()

    def stop(self, timeout=5.0):
        """توقفِ رشته؛ اگر نشد False (شارد باید بسته شود)."""
        if self.thread is None or not self.thread.is_alive():
            return True
        try:
            import ctypes
            tid = ctypes.c_ulong(self.thread.ident)
            ctypes.pythonapi.PyThreadState_SetAsyncExc(tid,
                                                      ctypes.py_object(SystemExit))
        except Exception:
            return False
        t0 = time.time()
        while time.time() - t0 < timeout:
            if not self.thread.is_alive():
                return True
            time.sleep(0.1)
        return False

    def alive(self):
        return self.thread is not None and self.thread.is_alive()


def main():
    ap = argparse.ArgumentParser(description="JAFJ shard daemon")
    ap.add_argument("--selfbot", required=True)
    ap.add_argument("--max-accounts", type=int, default=8)
    ap.add_argument("--preload-telethon", default="1")
    args = ap.parse_args()
    selfbot_path = os.path.abspath(args.selfbot)
    Account.path = selfbot_path

    out_lock = threading.Lock()
    src = ""
    base_code = None
    try:
        with open(selfbot_path, encoding="utf-8", errors="replace") as f:
            src = f.read()
    except Exception:
        _reply({"event": "ready", "pid": os.getpid(), "error": "selfbot-missing"},
               out_lock)
        return 2

    try:
        # یک بار برای همه‌ی اکانت‌ها: نه ۲۵ مگابایت جهشِ کامپایل برای هر
        # اکانت، نه یک کدآبجکتِ جدا برای هر کدام.
        base_code = compile(src, selfbot_path, "exec")
    except Exception:
        base_code = None

    if str(args.preload_telethon).strip() not in ("0", "false", "no", "نه"):
        try:
            import telethon            # noqa: F401  (اشتراکِ حافظه)
        except Exception:
            pass
    for name in sorted(_dep_names(src)):
        if name in ("__future__",):
            continue
        try:
            __import__(name)
        except Exception:
            pass
    try:
        import gc
        gc.collect()
        if hasattr(gc, "freeze"):
            gc.freeze()
    except Exception:
        pass

    accounts = {}
    max_acc = max(1, int(args.max_accounts or 1))

    # نگهبان: رشته‌ای که تمام شود باید رویداد بفرستد (وگرنه مدیر فکر می‌کند
    # سلف زنده است).
    def _watch():
        last = {}
        while True:
            time.sleep(0.5)
            for uid, acc in list(accounts.items()):
                if acc.exited is not None and last.get(uid) != acc.exited:
                    last[uid] = acc.exited
                    _reply({"event": "exit", "uid": uid, "pid": os.getpid(),
                            "code": acc.exited}, out_lock)
    threading.Thread(target=_watch, name="watch", daemon=True).start()

    _reply({"event": "ready", "pid": os.getpid(), "max": max_acc}, out_lock)

    for line in sys.stdin:
        line = (line or "").strip()
        if not line:
            continue
        try:
            msg = json.loads(line)
        except Exception:
            _reply({"ok": False, "error": "bad-json"}, out_lock)
            continue
        cmd = (msg.get("cmd") or "").strip().lower()
        if cmd == "run":
            uid = str(msg.get("uid") or "")
            cwd = msg.get("cwd") or "."
            logp = msg.get("log") or ""
            if uid in accounts and accounts[uid].alive():
                _reply({"ok": True, "pid": os.getpid(), "uid": uid,
                        "note": "already-running"}, out_lock)
                continue
            if len([a for a in accounts.values() if a.alive()]) >= max_acc:
                _reply({"ok": False, "error": "shard-full"}, out_lock)
                continue
            try:
                os.makedirs(cwd, exist_ok=True)
                fb = None
                if base_code is None:
                    fb = compile(_rewrite(src, cwd), selfbot_path, "exec")
            except Exception as e:
                _reply({"ok": False, "error": "prepare: %s" % e}, out_lock)
                continue
            acc = Account(uid, cwd, logp, base_code if base_code is not None else fb, fb)
            accounts[uid] = acc
            acc.start()
            _reply({"ok": True, "pid": os.getpid(), "uid": uid}, out_lock)
        elif cmd == "stop":
            uid = str(msg.get("uid") or "")
            acc = accounts.get(uid)
            if acc is None:
                _reply({"ok": True, "uid": uid, "note": "unknown"}, out_lock)
                continue
            ok = acc.stop()
            _reply({"ok": bool(ok), "uid": uid,
                    "note": "" if ok else "thread-alive"}, out_lock)
            if not ok:
                break
        elif cmd == "ping":
            reply = {"ok": True, "accounts": sorted(
                u for u, a in accounts.items() if a.alive())}
            if "request_id" in msg:
                reply["request_id"] = msg["request_id"]
            _reply(reply, out_lock)
        elif cmd == "quit":
            break
        else:
            _reply({"ok": False, "error": "unknown-cmd"}, out_lock)

    for acc in list(accounts.values()):
        acc.stop(timeout=2.0)
    return 0


if __name__ == "__main__":
    sys.exit(main())
