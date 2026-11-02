#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""«رم کم است» باید عدد داشته باشد — نه حس.

کاربر گفت: «حسم می‌گوید رم کم می‌آورد و سلف‌ها بالا نمی‌آیند». تا امروز
`/diag` فقط یک عددِ آزاد نشان می‌داد و اگر سقفِ کانتینر پایین‌تر از حافظه‌ی
میزبان بود، همان عدد دروغ بود («۴۰۰MB آزاد» و همان لحظه OOM).

این تست سه چیز را قفل می‌کند:
  ۱) خواندنِ سقف/مصرفِ cgroup (v1 و v2) و رد کردنِ «max».
  ۲) خطِ حافظه در `/diag`: عدد + تصمیمِ نگهبان (مجاز/مسدود/خاموش) + مصرفِ
     واقعیِ سلف‌ها.
  ۳) توضیحِ سلفِ «روشن»ی که کار نمی‌کند: حلقه‌ی ری‌استارت‌شده، ضربانِ کهنه.

اجرا: python3 tests/test_ram_diag.py
"""
import os
import sys
import tempfile
from pathlib import Path

HERE = Path(__file__).resolve().parent
REPO = HERE.parent
FAILS = []


def check(name, cond, extra=""):
    print(("PASS " if cond else "FAIL ") + name
          + (f"   [{extra}]" if extra and not cond else ""))
    if not cond:
        FAILS.append(name)


def put(path, text):
    os.makedirs(os.path.dirname(path), exist_ok=True)
    with open(path, "w", encoding="ascii") as f:
        f.write(text)


def main():
    root = Path(tempfile.mkdtemp(prefix="jafj_ramdiag_"))
    saved_env = {k: os.environ.get(k) for k in
                 ("DATA_DIR", "PORT", "JAFJ_ONLY", "JAFJ_MIN_FREE_MB",
                  "JAFJ_RESUME_DELAY")}
    os.environ["DATA_DIR"] = str(root / "data")
    os.environ["PORT"] = "8547"
    os.environ.pop("JAFJ_ONLY", None)
    os.environ.pop("JAFJ_MIN_FREE_MB", None)
    os.environ["JAFJ_RESUME_DELAY"] = "0"
    try:
        sys.path.insert(0, str(REPO))
        import manager_82 as M

        # ── ۱) خواندنِ cgroup ──────────────────────────────────────────
        cg = root / "cg"
        put(str(cg / "memory.max"), str(512 * 1024 * 1024))
        put(str(cg / "memory.current"), str(400 * 1024 * 1024))
        proc = str(cg / "proc-cgroup")
        put(proc, "0::/\n")
        lim, use = M.cgroup_mem_mb(str(cg), proc)
        check("cgroup v2: سقف/مصرف خوانده می‌شود",
              (lim, use) == (512.0, 400.0), (lim, use))

        put(str(cg / "memory.max"), "max")
        lim2, _ = M.cgroup_mem_mb(str(cg), proc)
        check("cgroup: «max» یعنی نامحدود → None (نه عددِ جعلی)",
              lim2 is None, lim2)

        # cgroup v1
        v1 = root / "cg1"
        put(str(v1 / "memory" / "tenant" / "memory.limit_in_bytes"),
            str(256 * 1024 * 1024))
        put(str(v1 / "memory" / "tenant" / "memory.usage_in_bytes"),
            str(200 * 1024 * 1024))
        proc1 = str(v1 / "proc-cgroup")
        put(proc1, "5:memory:/tenant\n")
        lim3, use3 = M.cgroup_mem_mb(str(v1), proc1)
        check("cgroup v1: سقف/مصرف خوانده می‌شود",
              (lim3, use3) == (256.0, 200.0), (lim3, use3))

        # ── ۲) خطِ حافظه در /diag ─────────────────────────────────────
        class _Sup:
            procs = {}

        class _Shim:
            sup = _Sup()

        orig_gate, orig_gate_mb = M.ram_gate_check, M.ram_gate_mb

        # حافظه کم: نگهبان مسدود می‌کند
        M.ram_gate_check = lambda env=None: (False, 30.0, 60.0)
        M.ram_gate_mb = lambda env=None: 60.0
        M.cgroup_mem_mb = lambda *a, **k: (512.0, 490.0)
        lines = "\n".join(M.Manager.mem_diag_lines(_Shim(), free=22))
        check("/diag: عددِ آزاد را می‌گوید", "22MB" in lines, lines)
        check("/diag: سقفِ کانتینر را می‌گوید", "512MB" in lines, lines)
        check("/diag: تصمیمِ نگهبان = مسدود", "⛔" in lines, lines)
        check("/diag: علتِ مسدود بودن را توضیح می‌دهد",
              "یک سلف خاموش" in lines or "JAFJ_MIN_FREE_MB" in lines, lines)

        # حافظه کافی: مجاز
        M.ram_gate_check = lambda env=None: (True, 300.0, 60.0)
        lines2 = "\n".join(M.Manager.mem_diag_lines(_Shim(), free=300))
        check("/diag: تصمیمِ نگهبان = مجاز", "✅" in lines2, lines2)
        check("/diag: حالتِ اجرا و ظرفیت را می‌گوید",
              "حالتِ اجرا" in lines2, lines2)

        # total_ram_mb باید سقفِ کانتینر را بر meminfo مقدم بدارد
        put(str(cg / "memory.max"), str(512 * 1024 * 1024))
        put(str(cg / "memory.current"), str(100 * 1024 * 1024))
        orig_cg_total = M.cgroup_mem_mb
        M.cgroup_mem_mb = lambda *a, **k: (512.0, 100.0)
        check("total_ram_mb: سقفِ کانتینر (نه حافظه‌ی میزبان)",
              M.total_ram_mb() == 512.0, M.total_ram_mb())
        # کانتینرِ کوچک → حالتِ shard (هر اکانت ~۴MB نه ~۶۲MB)
        M.cgroup_mem_mb = orig_cg_total
        M.total_ram_mb = lambda: 512.0
        check("spawn_mode: روی ۵۱۲MB خودکار shard انتخاب می‌شود",
              M.spawn_mode({}) == "shard", M.spawn_mode({}))

        # نگهبان خاموش
        M.ram_gate_check = lambda env=None: (True, None, 0.0)
        M.ram_gate_mb = lambda env=None: 0.0
        lines3 = "\n".join(M.Manager.mem_diag_lines(_Shim(), free=100))
        check("/diag: نگهبانِ خاموش را صریح می‌گوید", "خاموش" in lines3, lines3)
        M.ram_gate_check, M.ram_gate_mb = orig_gate, orig_gate_mb
        M.cgroup_mem_mb = orig_cg = M.__dict__["cgroup_mem_mb"]

        # ── ۳) «روشن» ولی بی‌کار: توضیح لازم است ──────────────────────
        class _Sup2:
            def __init__(self, st):
                self._st = st

            def read_status(self, uid):
                return self._st

        class _Shim2:
            _esc = staticmethod(lambda t: "" if t is None else str(t))

            def __init__(self, st):
                self.sup = _Sup2(st)

        fresh = {"age": 20, "loops": {"sender": {"state": "running",
                                                "restarts": 0, "errors": 0}},
                 "mem": {"free_mb": 210}}
        notes = M.Manager._alive_notes(_Shim2(fresh), 111)
        check("سلفِ سالم: هیچ هشداری نمی‌دهد", notes == [], notes)

        broken = {"age": 900, "mem": {"free_mb": 12},
                  "loops": {"sender": {"state": "running", "restarts": 4,
                                       "errors": 0},
                            "exchange": {"state": "crashed", "restarts": 3,
                                         "errors": 3,
                                         "last_error": "MemoryError: oops"}}}
        notes2 = " | ".join(M.Manager._alive_notes(_Shim2(broken), 111))
        check("ضربانِ کهنه را می‌گوید", "دقیقه" in notes2, notes2)
        check("ری‌استارتِ حلقه‌ها را می‌گوید", "ری‌استارت" in notes2, notes2)
        check("آخرین خطای حلقه را می‌گوید", "MemoryError" in notes2, notes2)
        check("حافظه‌ی آخرین ضربان را می‌گوید", "12MB" in notes2, notes2)

        # ── ۳ب) سه دلیلِ بی‌صدای «هیچ کاری نمی‌کند» ────────────────────
        idle = {"age": 30, "paused": True,
                "exchange": {"on": False},
                "channels": {"standard": "", "vip": ""},
                "loops": {}, "mem": {"free_mb": 300}}
        notes3 = " | ".join(M.Manager._alive_notes(_Shim2(idle), 111))
        check("Pause را می‌گوید", "Pause" in notes3, notes3)
        check("تبادلِ خاموش را می‌گوید", "تبادل خاموش" in notes3, notes3)
        check("کانالِ ثبت‌نشده را می‌گوید", "کانالِ خودت ثبت نشده" in notes3,
              notes3)

        # ── ۴) پیامِ مسدودشدن در start() باید عددِ کمبود را بدهد ─────
        src = (REPO / "manager_82.py").read_text(encoding="utf-8")
        check("start(): «چند مگابایت کم است» را می‌گوید",
              "_short = max(0, int(round(float(_limit) - float(_free))))" in src)
        check("start(): تعداد/مصرفِ سلف‌های روشن در پیام می‌آید",
              "سلف روشن است و روی‌هم" in src)
        check("start(): راهِ خروج (JAFJ_MIN_FREE_MB) در پیام هست",
              "JAFJ_MIN_FREE_MB=0" in src)
        check("۹۵: mem_info و loops به jafj_status.json اضافه شده‌اند",
              '"mem": mem_info(),' in (REPO / "95.py").read_text(encoding="utf-8"))
    finally:
        for k, v in saved_env.items():
            if v is None:
                os.environ.pop(k, None)
            else:
                os.environ[k] = v

    print()
    if FAILS:
        print("FAILED:", len(FAILS))
        return 1
    print("ALL PASS")
    return 0


if __name__ == "__main__":
    sys.exit(main())
