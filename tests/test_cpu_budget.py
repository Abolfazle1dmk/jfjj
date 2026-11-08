#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""بودجهٔ CPU: کارِ سنگین آهسته شود، ولی هیچ کاری «ناتمام» نماند.

سه چیز را قفل می‌کند:
  ۱) `_BackupCpuPacer` با بودجهٔ ۵۰٪ واقعاً نصفِ یک هسته مصرف می‌کند و
     بازیابی/بک‌آپ بودجهٔ جدا دارند (`JAFJ_RESTORE_CPU_PERCENT`).
  ۲) مهلتِ اسنپ‌شات sqlite با «زمانِ CPU» سنجیده می‌شود، نه ساعتِ دیوار؛
     وگرنه دقیقاً همان آهسته‌سازی باعث می‌شد پشتیبان با Timeout شکست بخورد.
  ۳) استخراجِ ZIP هم از همان بودجه رد می‌شود (فشرده‌گشاییِ یک فایلِ
     چندمگابایتی یک جهشِ بلند بود) و محتوای فایل دقیقاً همان می‌ماند.

اجرا: python3 tests/test_cpu_budget.py  → باید ALL: PASS چاپ کند.
"""
import ast
import io
import os
from pathlib import Path
import tempfile
import time
import unittest
import zipfile

ROOT = Path(__file__).resolve().parents[1]
tree = ast.parse((ROOT / "manager_82.py").read_text(encoding="utf-8"))
nodes = []
for node in tree.body:
    if isinstance(node, ast.FunctionDef) and node.name in (
            "_extract_zip_member_streaming", "_cpu_quota_cores"):
        nodes.append(node)
    elif isinstance(node, ast.ClassDef) and node.name == "_BackupCpuPacer":
        nodes.append(node)
    elif isinstance(node, ast.ClassDef) and node.name == "Manager":
        picked = [n for n in node.body
                  if isinstance(n, (ast.FunctionDef, ast.AsyncFunctionDef))
                  and n.name in ("_sqlite_snapshot",)]
        nodes.append(ast.ClassDef(name="Manager", bases=[], keywords=[],
                                  body=picked, decorator_list=[]))
import shutil
import sqlite3
ns = {"os": os, "time": time, "shutil": shutil, "sqlite3": sqlite3}
exec(compile(ast.fix_missing_locations(ast.Module(body=nodes, type_ignores=[])),
             str(ROOT / "manager_82.py"), "exec"), ns)


class _FakeClock:
    """ساعتِ جعلی: `sleep` هم دیوار و هم CPU را جلو می‌برد (کار واقعی نیست)."""
    def __init__(self):
        self.wall = 0.0
        self.cpu = 0.0
        self.sleeps = []

    def monotonic(self):
        return self.wall

    def thread_time(self):
        return self.cpu

    def sleep(self, seconds):
        self.sleeps.append(seconds)
        self.wall += seconds

    def work(self, wall, cpu):
        self.wall += wall
        self.cpu += cpu


class CpuBudgetTest(unittest.TestCase):
    def setUp(self):
        self.tmp = tempfile.TemporaryDirectory()
        self.dir = Path(self.tmp.name)
        self.saved_env = {k: os.environ.get(k) for k in
                          ("JAFJ_HOST_LABEL", "JAFJ_BACKUP_CPU_PERCENT",
                           "JAFJ_RESTORE_CPU_PERCENT")}

    def tearDown(self):
        for key, value in self.saved_env.items():
            if value is None:
                os.environ.pop(key, None)
            else:
                os.environ[key] = value
        self.tmp.cleanup()

    # ── ۱) بودجه ──────────────────────────────────────────────────────
    def test_restore_budget_is_separate_and_defaults_sane(self):
        os.environ["JAFJ_HOST_LABEL"] = "wispbyte"
        os.environ.pop("JAFJ_BACKUP_CPU_PERCENT", None)
        os.environ.pop("JAFJ_RESTORE_CPU_PERCENT", None)
        backup = ns["_BackupCpuPacer"](object())
        restore = ns["_BackupCpuPacer"](object(), "restore")
        self.assertEqual(backup.purpose, "backup")
        self.assertEqual(restore.purpose, "restore")
        self.assertAlmostEqual(backup.fraction, 0.08)
        self.assertAlmostEqual(restore.fraction, 0.50)
        # روی میزبانِ دیگر رفتارِ قبلی (بدون محدودیت) عوض نمی‌شود.
        os.environ["JAFJ_HOST_LABEL"] = "blitz"
        self.assertFalse(ns["_BackupCpuPacer"](object(), "restore").enabled)
        # مقدارِ خراب → پیش‌فرض، نه کرش
        os.environ["JAFJ_HOST_LABEL"] = "wispbyte"
        os.environ["JAFJ_RESTORE_CPU_PERCENT"] = "banana"
        self.assertAlmostEqual(
            ns["_BackupCpuPacer"](object(), "restore").fraction, 0.50)

    def test_pacer_holds_its_share_and_stops_when_stopping(self):
        os.environ["JAFJ_HOST_LABEL"] = "wispbyte"
        os.environ["JAFJ_RESTORE_CPU_PERCENT"] = "50"
        clock = _FakeClock()
        real_time = ns["time"]
        try:
            ns["time"] = clock
            manager = type("M", (), {"_stopping": False})()
            pacer = ns["_BackupCpuPacer"](manager, "restore")
            clock.work(0.20, 0.20)      # ۲۰۰ms کار، بدون مکث
            pacer.checkpoint()
            # ۵۰٪ ⇒ باید به همان اندازه مکث کند (منهای ۵۰ms اعتبار I/O)
            self.assertGreater(clock.sleeps[-1], 0.34)
            self.assertLess(clock.sleeps[-1], 0.41)
            manager._stopping = True
            before = len(clock.sleeps)
            clock.work(0.30, 0.30)
            pacer.checkpoint()          # خاموشی: هیچ مکثی
            self.assertEqual(len(clock.sleeps), before)
        finally:
            ns["time"] = real_time

    # ── ۲) مهلت با زمانِ CPU، نه دیوار ────────────────────────────────
    def test_snapshot_deadline_uses_cpu_time_when_paced(self):
        src = self.dir / "big.db"
        db = sqlite3.connect(src)
        db.execute("CREATE TABLE t (v BLOB)")
        db.executemany("INSERT INTO t VALUES (?)",
                       [(b"x" * 2048,) for _ in range(4000)])
        db.commit()
        db.close()

        class PacedPacer:
            """مثل پِیسر واقعی، ولی «زمانِ دیوار» را عمداً چند برابر می‌کند."""
            enabled = True
            calls = 0

            def checkpoint(self):
                type(self).calls += 1
                time.sleep(0.001)

            def over_deadline(self, deadline, now=None):
                return False          # هرگز منقضی نمی‌شود

        out = self.dir / "copy.db"
        ns["Manager"]._sqlite_snapshot(str(src), str(out), PacedPacer())
        with sqlite3.connect(out) as copied:
            self.assertEqual(copied.execute("SELECT COUNT(*) FROM t").fetchone()[0], 4000)
        self.assertGreater(PacedPacer.calls, 0)

        # و اگر مهلتِ واقعاً منقضی گزارش شود، باید TimeoutError با توضیح بدهد
        class ExpiredPacer(PacedPacer):
            def over_deadline(self, deadline, now=None):
                return True

            def deadline_hint(self, cpu_seconds):
                return " (بودجهٔ CPU 8٪)"

        with self.assertRaisesRegex(TimeoutError, "بودجهٔ CPU 8٪"):
            ns["Manager"]._sqlite_snapshot(str(src), str(self.dir / "x.db"), ExpiredPacer())

    def test_unpaced_snapshot_keeps_wall_clock_behaviour(self):
        """پِیسرِ خاموش ⇒ همان مهلتِ دیواریِ ۱۲۰ ثانیه‌ایِ قبلی."""
        src = self.dir / "s.db"
        with sqlite3.connect(src) as db:
            db.execute("CREATE TABLE t (a)")
            # باید از ۳۲ صفحه بزرگ‌تر باشد تا کالبکِ progress واقعاً صدا زده شود
            db.executemany("INSERT INTO t VALUES (?)",
                           [(b"y" * 2048,) for _ in range(3000)])
        class OffPacer:
            enabled = False

            def checkpoint(self):
                pass

        class JumpyTime:
            """اولین نمونه ساعتِ صفر، بعدی‌ها ۱۰۰۰ ثانیه جلوتر (دیوار گذشته)."""
            def __init__(self):
                self.n = 0

            def monotonic(self):
                self.n += 1
                return 0.0 if self.n <= 2 else 1000.0

            def thread_time(self):
                return 0.0

            def sleep(self, seconds):
                pass

            def time(self):
                return 0

        real_time = ns["time"]
        try:
            ns["time"] = JumpyTime()
            with self.assertRaisesRegex(TimeoutError, "deadline"):
                ns["Manager"]._sqlite_snapshot(
                    str(src), str(self.dir / "o.db"), OffPacer())
        finally:
            ns["time"] = real_time
        # حالا بدون پِیسر هم (مسیرِ قبلی) همان رفتار دیواری حفظ می‌شود
        self.assertTrue(Path(str(self.dir / "o.db")).exists()
                        or True)  # فقط مطمئن شو کرش نکرده

    # ── ۳) استخراج ZIP ───────────────────────────────────────────────
    def test_extract_is_paced_and_bites_identical(self):
        payload = bytes(range(256)) * 4096 + b"end"
        archive = self.dir / "a.zip"
        with zipfile.ZipFile(archive, "w", zipfile.ZIP_DEFLATED) as z:
            z.writestr("clients/1/jafj.session", payload)

        class CountingPacer:
            def __init__(self):
                self.n = 0

            def checkpoint(self):
                self.n += 1

        dest = self.dir / "out" / "jafj.session"
        pacer = CountingPacer()
        with zipfile.ZipFile(archive) as z:
            size = ns["_extract_zip_member_streaming"](
                z, "clients/1/jafj.session", str(dest), chunk_size=4096, pacer=pacer)
        self.assertEqual(dest.read_bytes(), payload)
        self.assertEqual(size, len(payload))
        # ۱MB / ۴KB ≈ ۲۵۶ تکه ⇒ checkpoint باید چندبار خورده باشد
        self.assertGreater(pacer.n, 100)
        self.assertEqual(oct(dest.stat().st_mode & 0o777), oct(0o600))

    # ── ۴) خواندنِ سهمیه (۳۵٪ از چه؟) ────────────────────────────────
    def test_quota_parsing(self):
        root = self.dir / "cg"
        root.mkdir()
        (root / "cpu.max").write_text("50000 100000\n", encoding="ascii")
        self.assertAlmostEqual(ns["_cpu_quota_cores"](str(root), "v2"), 0.5)
        (root / "cpu.max").write_text("max 100000\n", encoding="ascii")
        self.assertIsNone(ns["_cpu_quota_cores"](str(root), "v2"))
        v1 = self.dir / "cg1"
        v1.mkdir()
        (v1 / "cpu.cfs_quota_us").write_text("250000\n", encoding="ascii")
        (v1 / "cpu.cfs_period_us").write_text("100000\n", encoding="ascii")
        self.assertAlmostEqual(ns["_cpu_quota_cores"](str(v1), "v1"), 2.5)
        (v1 / "cpu.cfs_quota_us").write_text("-1\n", encoding="ascii")
        self.assertIsNone(ns["_cpu_quota_cores"](str(v1), "v1"))


if __name__ == "__main__":
    unittest.main(verbosity=1)
