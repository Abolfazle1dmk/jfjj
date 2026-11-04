#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""نگهبانِ حلقه‌ها + گزارشِ حافظه — «روشن است ولی کار نمی‌کند».

نشانه‌ی کاربر: «پنل درست شد، ولی فرایندِ جفج اصلاً انجام نمی‌شود». هر حلقه
(tabدل/ارسال/اسکن/…) یک Task است؛ اگر یکی بمیرد `run_until_disconnected`
زنده می‌ماند، پنل جواب می‌دهد و **هیچ کاری انجام نمی‌شود** تا کسی دستی
ری‌استارت کند. این تست همان کدِ نگهبان را (از خودِ 95.py بیرون کشیده و
اجرا شده) می‌سنجد: حلقه‌ی مرده باید خودکار برگردد و شمارش/علتش ثبت شود.

همچنین: `mem_info()` باید عددِ سقفِ کانتینر (cgroup) را بدهد، نه حافظه‌ی
میزبان — وگرنه «۴۰۰MB آزاد» می‌بینیم و همان لحظه OOM می‌شویم.

اجرا: python3 tests/test_loop_watchdog.py
"""
import ast
import asyncio
import importlib.util
import os
import sys
import tempfile
import textwrap

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


spec = importlib.util.spec_from_file_location("m95lw", SRC)
m = importlib.util.module_from_spec(spec)
m.__file__ = SRC
spec.loader.exec_module(m)

src_text = open(SRC, encoding="utf-8").read()
tree = ast.parse(src_text)


# ── ۱) حافظه: cgroup مقدم بر meminfo ───────────────────────────────────
def put(path, text):
    os.makedirs(os.path.dirname(path), exist_ok=True)
    with open(path, "w", encoding="ascii") as f:
        f.write(text)


root = tempfile.mkdtemp(prefix="jafj_cg_")
try:
    put(os.path.join(root, "memory.max"), str(512 * 1024 * 1024))
    put(os.path.join(root, "memory.current"), str(480 * 1024 * 1024))
    proc = os.path.join(root, "proc-cgroup")
    put(proc, "0::/\n")
    lim, use = m.cgroup_mem_mb(root, proc)
    check("cgroup: سقف و مصرف را می‌خواند", (lim, use) == (512.0, 480.0), (lim, use))

    # سقفِ «max» = نامحدود → نباید عددِ جعلی بدهد
    put(os.path.join(root, "memory.max"), "max")
    lim2, use2 = m.cgroup_mem_mb(root, proc)
    check("cgroup: max (نامحدود) نادیده گرفته می‌شود", lim2 is None, (lim2, use2))

    # اگر parent محدود باشد و leaf «max» داشته باشد، والد سقف واقعی است.
    nested = tempfile.mkdtemp(prefix="jafj_cg_parent_")
    try:
        put(os.path.join(nested, "memory.max"), "max")
        put(os.path.join(nested, "tenant", "memory.max"), str(512 * 1024 * 1024))
        put(os.path.join(nested, "tenant", "memory.current"), str(450 * 1024 * 1024))
        put(os.path.join(nested, "tenant", "worker", "memory.max"), "max")
        put(os.path.join(nested, "tenant", "worker", "memory.current"), str(8 * 1024 * 1024))
        nested_proc = os.path.join(nested, "proc-cgroup")
        put(nested_proc, "0::/tenant/worker" + chr(10))
        nested_pair = m.cgroup_mem_mb(nested, nested_proc)
        check("cgroup nested: سقفِ والدِ محدود از leaf نامحدود تشخیص داده می‌شود",
              nested_pair == (512.0, 450.0), nested_pair)
    finally:
        import shutil
        shutil.rmtree(nested, ignore_errors=True)

    # mem_info باید از همین مسیر استفاده کند
    orig = m.cgroup_mem_mb
    m.cgroup_mem_mb = lambda *a, **k: (512.0, 480.0)
    info = m.mem_info()
    m.cgroup_mem_mb = orig
    check("mem_info: free از سقفِ کانتینر (۳۲MB نه چند گیگ)",
          info.get("free_mb") == 32 and info.get("limit_mb") == 512
          and info.get("source") == "cgroup", info)
finally:
    import shutil
    shutil.rmtree(root, ignore_errors=True)

info2 = m.mem_info()
check("mem_info: بدونِ cgroup هم جواب می‌دهد (dict با کلیدهای لازم)",
      isinstance(info2, dict) and "free_mb" in info2 and "source" in info2, info2)

check("۹۵: نامِ فارسیِ حلقه‌ها هست",
      isinstance(getattr(m, "LOOP_LABELS", None), dict)
      and m.LOOP_LABELS.get("exchange") == "تبادل")
check("۹۵: وضعیتِ حلقه‌ها در jafj_status.json نوشته می‌شود",
      '"loops": {k: dict(v)' in src_text and '"mem": mem_info(),' in src_text)


# ── ۲) خودِ نگهبان: از 95.py بیرون کشیده و اجرا می‌شود ──────────────────
# حلقه‌ها و نگهبان داخلِ connect_and_run تعریف می‌شوند (همان تابعی که
# کلاینت را وصل می‌کند و بعد run_until_disconnected را صدا می‌زند).
host_fn = next((n for n in tree.body
                if isinstance(n, (ast.FunctionDef, ast.AsyncFunctionDef))
                and n.name == "connect_and_run"), None)
check("۹۵: connect_and_run پیدا شد", host_fn is not None)

nested = {}
if host_fn is not None:
    for n in host_fn.body:
        if isinstance(n, (ast.FunctionDef, ast.AsyncFunctionDef)):
            nested[n.name] = n

wanted = ["_loop_mark", "_loop_restart_note", "_supervise"]
check("۹۵: نگهبان و نشانه‌گذارها تعریف شده‌اند",
      all(w in nested for w in wanted), sorted(nested))

if all(w in nested for w in wanted):
    first = min(nested[w].lineno for w in wanted)
    last = max(nested[w].end_lineno for w in wanted)
    code = textwrap.dedent("".join(
        src_text.splitlines(True)[first - 1:last]))
    # شماره‌ی خط‌های in_code درست است چون فقط از یک نقطه بریده‌ایم.

    class _Eng:
        def __init__(self):
            self.loop_state = {}
            self.logs = []

        def log(self, *a):
            self.logs.append(a)

        def write_status(self, extra=None):
            pass

    notes = []

    async def _note(text):
        notes.append(text)

    async def _main():
        eng = _Eng()
        ns = {
            "asyncio": asyncio, "time": m.time,
            "eng": eng, "note": _note, "fa": str,
            "LOOP_LABELS": m.LOOP_LABELS,
            "_loop_note_at": {},
        }
        exec(compile(code, "<95.py:connect_and_run/supervise>", "exec"), ns)

        calls = {"n": 0}

        async def boom():
            calls["n"] += 1
            raise RuntimeError("کار خراب شد")

        t = ns["_supervise"]("exchange", boom, first_delay=0.01, max_delay=0.02)
        await asyncio.sleep(0.12)
        st = eng.loop_state.get("exchange", {})
        check("نگهبان: حلقه‌ی مرده دوباره راه می‌افتد",
              calls["n"] >= 2, calls["n"])
        check("نگهبان: خطا و ری‌استارت شمرده می‌شود",
              int(st.get("errors") or 0) >= 1
              and int(st.get("restarts") or 0) >= 1, st)
        check("نگهبان: علتِ خطا در وضعیت می‌نشیند",
              "RuntimeError" in str(st.get("last_error") or ""), st)
        check("نگهبان: Taskِ نگهبان نمی‌میرد (مثلِ قبل بی‌صدا خاموش نمی‌شود)",
              not t.done(), t)
        check("نگهبان: یک پیامِ هشدار به Saved Messages می‌رود",
              len(notes) == 1 and "تبادل" in notes[0], notes[:2])
        check("نگهبان: خطا در لاگِ اکانت هم ثبت می‌شود",
              any("loop_crash" in str(x) for x in eng.logs), eng.logs[:3])

        t.cancel()
        try:
            await t
        except asyncio.CancelledError:
            pass
        check("نگهبان: لغوِ بیرونی → وضعیت cancelled، نه ری‌استارت",
              eng.loop_state["exchange"].get("state") == "cancelled",
              eng.loop_state["exchange"])

        # حلقه‌ای که «تمام» می‌شود هم باید برگردد (وگرنه کار بی‌صدا می‌ایستد)
        eng2 = _Eng()
        ns2 = dict(ns)
        ns2.update({"eng": eng2})

        async def once():
            return None

        exec(compile(code, "<95.py:connect_and_run/supervise2>", "exec"), ns2)
        ends = {"n": 0}

        async def finite():
            ends["n"] += 1
            return None

        t2 = ns2["_supervise"]("sender", finite, first_delay=0.01, max_delay=0.02)
        await asyncio.sleep(0.08)
        t2.cancel()
        try:
            await t2
        except asyncio.CancelledError:
            pass
        check("نگهبان: حلقه‌ای که بی‌خطا تمام می‌شود هم دوباره اجرا می‌شود",
              ends["n"] >= 2, ends["n"])

    asyncio.run(_main())

# ── ۳) سیم‌کشی: هر ۸ حلقه زیرِ نگهبان باشند ───────────────────────────
for name in ("sender_loop", "exchange_worker", "scan_loop", "membership_loop",
             "report_loop", "risk_loop", "status_loop", "memory_loop"):
    check("۹۵: %s زیرِ نگهبان است" % name,
          '_supervise(' in src_text and src_text.count("_supervise(") >= 8)
    break

for key in ('_supervise("sender"', '_supervise("exchange"', '_supervise("scan"',
            '_supervise("membership"', '_supervise("report"',
            '_supervise("risk"', '_supervise("status"', '_supervise("memory"'):
    check("۹۵: %s وصل است" % key, key in src_text)

print()
if FAILS:
    print("FAILED:", len(FAILS))
    sys.exit(1)
print("ALL PASS")
