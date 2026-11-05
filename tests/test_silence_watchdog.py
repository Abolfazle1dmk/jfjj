#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""«بعد از مدتی استفاده، منیجر آفلاین می‌شود» — این دو حالت را می‌بندد.

۱) پروسه زنده است، پنل هم می‌گوید online، `/healthz` هم ۲۰۰ می‌دهد، ولی
   ربات به هیچ پیامی جواب نمی‌دهد (اتصالِ MTProto نیمه‌باز). کدِ قبلی هیچ
   درخواستی به تلگرام نمی‌زد، پس هیچ‌وقت هم نمی‌فهمید. حالا `liveness_loop`
   با پینگِ واقعی می‌فهمد، اول اتصال را از نو می‌سازد و در نهایت پروسه را
   با کدِ ۷۵ می‌بندد تا ناظر نسخه‌ی تازه بالا بیاورد.

۲) ناظر بعد از ۵ کرشِ سریع «تسلیم» می‌شد و می‌مرد. روی Wispbyte هیچ‌کس
   پروسه‌ی مرده را دوباره استارت نمی‌کند، پس پنل تا ابد Offline می‌ماند.
   با `JAFJ_NEVER_GIVE_UP=1` (پیش‌فرضِ بوت‌استرپِ Wispbyte) فقط خوابِ کوتاه
   می‌کند و از صفر شروع می‌کند.

۳) اگر حلقه‌ی اصلی کاملاً قفل شود، threadِ `silence_watch` ردِ stack‌ها را
   در `hang.log` می‌نویسد و پروسه را می‌بندد (وگرنه «روشنِ بی‌فایده»).
"""
import os
import shutil
import subprocess
import sys
import tempfile
import time
from pathlib import Path

HERE = Path(__file__).resolve().parent
REPO = HERE.parent
FAILS = []


def check(name, cond, extra=""):
    print(("PASS " if cond else "FAIL ") + name
          + (f"   [{extra}]" if extra and not cond else ""))
    if not cond:
        FAILS.append(name)


def clean_env(**kw):
    env = dict(os.environ)
    for k in ("JAFJ_ONLY", "JAFJ_PING_SECS", "JAFJ_PING_RESTART",
              "JAFJ_PING_RECONNECT", "JAFJ_HANG_SECS", "JAFJ_NEVER_GIVE_UP",
              "JAFJ_SUPERVISE", "JAFJ_MAX_CRASHES", "JAFJ_COOL_DOWN",
              "JAFJ_NAP_BASE", "DATA_GITHUB_TOKEN", "JAFJ_KEEP_ALIVE",
              "JAFJ_HOSTED"):
        env.pop(k, None)
    env.update({k: str(v) for k, v in kw.items()})
    return env


def run_py(code, env, timeout=60):
    p = subprocess.run([sys.executable, "-c", code], cwd=str(REPO), env=env,
                       capture_output=True, text=True, timeout=timeout)
    return p.returncode, p.stdout + p.stderr


# ─────────────────────────────────────────── بخش ۱: منطقِ نگهبان ──────────
INNER_LOGIC = r'''
import os, sys, time, json
sys.path.insert(0, os.getcwd())
import manager_82 as M

out = {}
# ── آستانه‌ها: ۱ تلاش دوباره، ۲ بستنِ اتصال، ۴ ری‌استارت ─────────────
out["verdicts"] = [M.ping_verdict(n) for n in (0, 1, 2, 3, 4, 9)]
out["verdicts_custom"] = [M.ping_verdict(n, reconnect_at=1, restart_at=2)
                          for n in (1, 2)]

# ── «سکوت» یعنی حلقه‌ی اصلی ضربان نمی‌زند ─────────────────────────────
M.LIVE["ready"] = True
M.mark_live("loop")
out["healthy"] = M.livez_verdict()
out["stalled"] = M.livez_verdict({"ready": True, "stopping": False, "fails": 0,
                                  "loop_age": int(M.hang_seconds()) + 5})
out["silent"] = M.livez_verdict({"ready": True, "stopping": False,
                                 "loop_age": 1,
                                 "fails": M.ping_restart_after()})
out["stale_when_on"] = M.livez_verdict({"ready": True, "stopping": False,
                                        "loop_age": 10 ** 6, "fails": 0})
os.environ["JAFJ_HANG_SECS"] = "0"
out["off_calc"] = M.livez_verdict({"ready": True, "stopping": False,
                                   "loop_age": 10 ** 6, "fails": 0})
out["stopping"] = M.livez_verdict({"ready": True, "stopping": True,
                                   "loop_age": 10 ** 6, "fails": 9})

# ── نشانه‌های زنده‌بودن ───────────────────────────────────────────────
M.mark_live("ping_fail", {"fails": 3, "err": "TimeoutError: x"})
out["fail_snap"] = M.live_snapshot()
M.mark_live("ping")
out["ping_reset"] = M.live_snapshot()

# ── گزارشِ مرگ باید این دو حالت را از OOM جدا بگوید ───────────────────
d = os.environ["DATA_DIR"]
M.write_heartbeat(d, {"stage": "hang-exit", "loop_age": 900})
out["death_hang"] = M.last_death_report(d)
M.write_heartbeat(d, {"stage": "silence-exit", "fails": 4})
out["death_silence"] = M.last_death_report(d)
M.write_heartbeat(d, {"free": 40, "clients": 3})
out["death_plain"] = M.last_death_report(d)

# ── شاهدِ گیر کردن: هم hang.log هم crash.log ──────────────────────────
txt = M._silence_evidence(M.hang_seconds(), 999)
out["evidence"] = txt
try:
    out["hang_log"] = open(os.path.join(d, "hang.log"), encoding="utf-8",
                           errors="ignore").read()[-2000:]
except Exception as e:
    out["hang_log"] = "ERR " + repr(e)
out["crash_log"] = M.read_crash_log(4000)
print("JSON" + json.dumps(out, ensure_ascii=False))
'''


def part_logic():
    print("--- 1: منطقِ نگهبان (پینگ، livez، گزارشِ مرگ) ---")
    root = Path(tempfile.mkdtemp(prefix="jafj_silence_logic_"))
    env = clean_env(DATA_DIR=root / "data", PORT="8491")
    Path(env["DATA_DIR"]).mkdir(parents=True, exist_ok=True)
    try:
        rc, out = run_py(INNER_LOGIC, env)
        line = [ln for ln in out.splitlines() if ln.startswith("JSON")]
        if not line:
            print(out[-2000:])
            check("منطق: اجرا شد", False)
            return
        import json
        o = json.loads(line[0][4:])
        check("آستانه‌ها: 1→retry, 2→reconnect, 4→restart",
              o["verdicts"] == ["ok", "retry", "reconnect", "reconnect",
                                "restart", "restart"], o["verdicts"])
        check("آستانه‌ها با env قابلِ تغییرند",
              o["verdicts_custom"] == ["reconnect", "restart"],
              o["verdicts_custom"])
        check("سلامت: ۲۰۰ ok", o["healthy"] == [200, "ok"], o["healthy"])
        check("حلقه‌ی گیرکرده: ۵۰۳ stalled",
              o["stalled"] == [503, "stalled"], o["stalled"])
        check("پینگ‌های پیاپیِ ناموفق: ۵۰۳ silent",
              o["silent"] == [503, "silent"], o["silent"])
        check("حلقه‌ی کهنه: ۵۰۳ stalled",
              o["stale_when_on"] == [503, "stalled"], o["stale_when_on"])
        check("نگهبانِ خاموش (JAFJ_HANG_SECS=0): هیچ‌وقت ۵۰۳ نمی‌دهد",
              o["off_calc"] == [200, "ok"], o["off_calc"])
        check("وسطِ خاموشیِ عمدی: ۵۰۳ نمی‌دهد",
              o["stopping"] == [200, "ok"], o["stopping"])
        check("پینگِ ناموفق: شمارنده و علت ثبت می‌شود",
              o["fail_snap"]["fails"] == 3
              and "TimeoutError" in o["fail_snap"]["last_error"],
              o["fail_snap"])
        check("پینگِ موفق: شمارنده صفر می‌شود",
              o["ping_reset"]["fails"] == 0
              and o["ping_reset"]["last_error"] == "", o["ping_reset"])
        check("گزارشِ مرگ: «گیر کرده بود»",
              "گیر کرده بود" in o["death_hang"], o["death_hang"])
        check("گزارشِ مرگ: «به تلگرام جواب نمی‌داد»",
              "جواب نمی‌داد" in o["death_silence"], o["death_silence"])
        check("گزارشِ مرگ: حالتِ معمولی هم می‌گوید OOM/Stop",
              "OOM" in o["death_plain"], o["death_plain"])
        check("شاهد: متنِ گیر کردن",
              "هیچ ضربانی نزد" in o["evidence"], o["evidence"])
        check("شاهد: hang.log نوشته شد",
              "=====" in o["hang_log"] and "hang.log" not in o["hang_log"],
              o["hang_log"][-300:])
        check("شاهد: crash.log هم بلوکِ hang دارد",
              "[hang]" in o["crash_log"], o["crash_log"][-300:])
    finally:
        shutil.rmtree(root, ignore_errors=True)


# ─────────────────────────── بخش ۲: thread واقعاً پروسه را می‌بندد ────────
INNER_WATCH = r'''
import os, sys, time
sys.path.insert(0, os.getcwd())
import manager_82 as M
M.LIVE["ready"] = True
M.LIVE["loop"] = time.time() - 10 ** 6      # حلقه‌ی مرده
M.silence_watch(os.environ["DATA_DIR"], step=0.3)
print("STILL_ALIVE", flush=True)            # نباید به اینجا برسیم
time.sleep(30)
'''


def part_thread():
    print("--- 2: نگهبانِ thread پروسه‌ی گیرکرده را می‌بندد ---")
    root = Path(tempfile.mkdtemp(prefix="jafj_silence_thread_"))
    data = root / "data"
    data.mkdir(parents=True, exist_ok=True)
    try:
        rc, out = run_py(INNER_WATCH, clean_env(DATA_DIR=data, PORT="8492",
                                                JAFJ_HANG_SECS="1"),
                         timeout=60)
        check("پروسه با کدِ ۷۵ بسته می‌شود", rc == 75, f"rc={rc}")
        check("بعد از تشخیص، زنده نمی‌ماند", "STILL_ALIVE" not in out, out[-300:])
        check("پایانِ کار را در لاگ می‌گوید",
              "نسخه‌ی تازه" in out, out[-400:])
        hb = (data / ".jafj_heartbeat")
        check("ضربان با stage=hang-exit نوشته شد",
              hb.is_file() and "hang-exit" in hb.read_text(encoding="utf-8"),
              hb.read_text(encoding="utf-8") if hb.is_file() else "no file")
        check("hang.log ساخته شد", (data / "hang.log").is_file())
    finally:
        shutil.rmtree(root, ignore_errors=True)


# ──────────── بخش ۲ب: خودِ liveness_loop (اتصال را می‌بندد، ری‌استارت می‌کند) ─
INNER_PING = r'''
import asyncio, os, sys
sys.path.insert(0, os.getcwd())
import manager_82 as M


class Bot:
    def is_connected(self):
        return True

    async def get_me(self):
        raise RuntimeError("اتصال مرده")

    async def disconnect(self):
        print("DISCONNECTED", flush=True)


class Sup:
    def shutdown(self):
        pass


class Fake:
    bot = Bot()
    sup = Sup()
    cfg = {"bot_token": "x"}
    _ping_telegram = M.Manager._ping_telegram
    _drop_stale_connection = M.Manager._drop_stale_connection
    _die_on_silence = M.Manager._die_on_silence


asyncio.run(M.Manager.liveness_loop(Fake()))
print("STILL_ALIVE", flush=True)
'''


def part_liveness():
    print("--- 2b: liveness_loop روی اتصالِ مرده ---")
    root = Path(tempfile.mkdtemp(prefix="jafj_silence_ping_"))
    data = root / "data"
    data.mkdir(parents=True, exist_ok=True)
    try:
        rc, out = run_py(INNER_PING, clean_env(DATA_DIR=data, PORT="8494",
                                               JAFJ_PING_SECS="1",
                                               JAFJ_PING_TIMEOUT="5",
                                               JAFJ_PING_RECONNECT="2",
                                               JAFJ_PING_RESTART="3"),
                         timeout=90)
        check("پینگِ ناموفق لاگ می‌شود", "پینگِ تلگرام ناموفق" in out, out[-500:])
        check("بعد از ۲ شکست، اتصال بسته می‌شود (serve_forever دوباره وصل کند)",
              "DISCONNECTED" in out, out[-500:])
        check("بعد از ۳ شکست، پروسه با کدِ ۷۵ بسته می‌شود",
              rc == 75 and "STILL_ALIVE" not in out, f"rc={rc}")
        hb = data / ".jafj_heartbeat"
        check("ضربان با stage=silence-exit نوشته شد",
              hb.is_file() and "silence-exit" in hb.read_text(encoding="utf-8"),
              hb.read_text(encoding="utf-8") if hb.is_file() else "no file")
        check("بلوکِ [silence] در crash.log هست",
              "[silence]" in (data / "crash.log").read_text(encoding="utf-8"))
    finally:
        shutil.rmtree(root, ignore_errors=True)


HTTP_INNER = r'''
import os, sys, time
sys.path.insert(0, os.getcwd())
import manager_82 as M
M.LIVE["ready"] = True
if os.environ.get("STALE") == "1":
    M.LIVE["loop"] = time.time() - 10 ** 6
else:
    M.mark_live("loop")
print("UP", flush=True)
time.sleep(30)
'''


# ─────────────── بخش ۳: وب‌سرورِ سلامتِ واقعی (/livez و /version) ─────────
def http_get(port, path, timeout=10):
    import urllib.error
    import urllib.request
    url = f"http://127.0.0.1:{port}{path}"
    try:
        with urllib.request.urlopen(url, timeout=timeout) as r:
            return r.status, r.read().decode("utf-8", "ignore")
    except urllib.error.HTTPError as e:
        return e.code, e.read().decode("utf-8", "ignore")
    except Exception as e:
        return 0, repr(e)


def part_http():
    """وب‌سرورِ سلامتِ واقعی: /livez باید ۵۰۳ بدهد وقتی حلقه گیر کرده."""
    print("--- 3: /livez و /version روی وب‌سرورِ واقعی ---")
    import socket
    for stale, want in ((0, 200), (1, 503)):
        root = Path(tempfile.mkdtemp(prefix="jafj_silence_http_"))
        data = root / "data"
        data.mkdir(parents=True, exist_ok=True)
        port = 8495 + stale
        env = clean_env(DATA_DIR=data, PORT=port, JAFJ_HANG_SECS="60",
                        STALE=str(stale))
        proc = subprocess.Popen([sys.executable, "-c", HTTP_INNER],
                                cwd=str(REPO), env=env, text=True,
                                stdout=subprocess.PIPE,
                                stderr=subprocess.STDOUT)
        try:
            up = False
            deadline = time.time() + 25
            while time.time() < deadline:
                try:
                    with socket.create_connection(("127.0.0.1", port), timeout=1):
                        up = True
                        break
                except OSError:
                    time.sleep(0.2)
            check("وب‌سرورِ سلامت بالا آمد", up)
            if not up:
                continue
            code, body = http_get(port, "/livez")
            check(f"/livez → {want}", code == want, (code, body))
            code, body = http_get(port, "/healthz")
            check("/healthz همچنان ۲۰۰ JAFJ OK است",
                  code == 200 and "JAFJ OK" in body, (code, body))
            code, body = http_get(port, "/version")
            check("/version خطِ live را دارد (سنِ پینگ/حلقه)",
                  code == 200 and "live: ready=1" in body, body[-300:])
        finally:
            proc.terminate()
            try:
                proc.wait(timeout=10)
            except Exception:
                proc.kill()
            shutil.rmtree(root, ignore_errors=True)


# ───────────────────── بخش ۴: ناظرِ shell تسلیم نمی‌شود ─────────────────
STUB = """import os, sys
p = os.path.join(os.environ['DATA_DIR'], 'runs')
n = int(open(p).read()) if os.path.exists(p) else 0
open(p, 'w').write(str(n + 1))
print('BOOM', flush=True)
sys.exit(0 if n >= 2 else 3)
"""


def shell_run(extra, timeout=120):
    root = Path(tempfile.mkdtemp(prefix="jafj_silence_shell_"))
    image = root / "image"
    app = root / "data"
    image.mkdir(parents=True)
    app.mkdir(parents=True)
    shutil.copy2(REPO / "railway-start.sh", image / "railway-start.sh")
    (image / "manager_82.py").write_text(STUB, encoding="utf-8")
    (image / "95.py").write_text("# stub\n", encoding="utf-8")
    env = clean_env(JAFJ_IMAGE_DIR=image, JAFJ_APP_DIR=app, DATA_DIR=app,
                    PORT="8493", **extra)
    p = subprocess.run(["sh", str(image / "railway-start.sh")], cwd=str(root),
                       env=env, capture_output=True, text=True, timeout=timeout)
    out = p.stdout + p.stderr
    runs = (app / "runs")
    n = int(runs.read_text()) if runs.is_file() else 0
    shutil.rmtree(root, ignore_errors=True)
    return p.returncode, out, n


def part_supervisor():
    print("--- 4: ناظر با NEVER_GIVE_UP تسلیم نمی‌شود ---")
    rc, out, n = shell_run({"JAFJ_NEVER_GIVE_UP": "1", "JAFJ_MAX_CRASHES": "1",
                            "JAFJ_COOL_DOWN": "0", "JAFJ_NAP_BASE": "0"})
    # سه اجرا: اولی و دومی کرش (و هر بار «تسلیم نمی‌شوم»)، سومی موفق.
    check("روی Wispbyte: تا موفقیت ادامه می‌دهد (۳ اجرا)", n == 3, f"runs={n}")
    check("روی Wispbyte: پیامِ «تسلیم نمی‌شوم» دارد",
          "NOT giving up" in out, out[-600:])
    check("روی Wispbyte: هرگز «giving up so Railway» نمی‌گوید",
          "giving up so Railway" not in out, out[-600:])
    check("روی Wispbyte: خروجِ تمیز با کدِ ۰", rc == 0, f"rc={rc}")

    print("--- 5: بدونِ این سوییچ، رفتارِ قبلی (تحویل به Railway) می‌ماند ---")
    rc, out, n = shell_run({"JAFJ_MAX_CRASHES": "2", "JAFJ_NAP_BASE": "0"})
    check("Railway: بعد از سقفِ کرش تسلیم می‌شود", n == 2, f"runs={n}")
    check("Railway: کدِ خروجِ مدیر گزارش می‌شود", rc == 3, f"rc={rc}")
    check("Railway: پیامِ «giving up» می‌آید",
          "giving up so Railway" in out, out[-600:])


# ───────────────────────── بخش ۶: بوت‌استرپ سوییچ را ست می‌کند ────────────
def part_bootstrap_env():
    print("--- 6: بوت‌استرپِ Wispbyte سوییچ را پیش‌فرض روشن می‌کند ---")
    for name in ("main.py", "deploy/wispbyte/main.py"):
        src = (REPO / name).read_text(encoding="utf-8")
        check(f"{name}: JAFJ_NEVER_GIVE_UP پیش‌فرض ۱",
              'env["JAFJ_NEVER_GIVE_UP"]' in src, name)
        check(f"{name}: JAFJ_COOL_DOWN ست می‌شود",
              'env["JAFJ_COOL_DOWN"]' in src, name)
    mgr = (REPO / "manager_82.py").read_text(encoding="utf-8")
    check("مدیر: نگهبانِ سکوت در بوت بالا می‌آید",
          "target=silence_watch" in mgr, "silence_watch thread")
    check("مدیر: پینگ در حلقه‌ی پس‌زمینه اجرا می‌شود",
          "self.liveness_loop()" in mgr, "liveness_loop")
    check("مدیر: /livez مسیرِ جدا دارد", '"/livez"' in mgr, "/livez")
    check("مدیر: /healthz دست‌نخورده مانده (JAFJ OK)",
          'return b"JAFJ OK\\n"' in mgr, "JAFJ OK")
    check("مدیر: /diag وضعیتِ واقعیِ ربات را نشان می‌دهد",
          "def live_diag_lines" in mgr and "*self.live_diag_lines()" in mgr,
          "live_diag_lines")


def main():
    part_logic()
    part_thread()
    part_liveness()
    part_http()
    part_supervisor()
    part_bootstrap_env()
    print()
    if FAILS:
        print("FAILED:", ", ".join(FAILS))
        return 1
    print("ALL PASS")
    return 0


if __name__ == "__main__":
    sys.exit(main())
