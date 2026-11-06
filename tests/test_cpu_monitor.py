#!/usr/bin/env python3
"""CPU alerts: cgroup accounting, activity windows, and durable delivery.

The manager code is extracted with AST so tests do not start Telegram or bind
its health port. All process/cgroup files and reports here are synthetic.
"""
import ast
import asyncio
import functools
import json
import os
from pathlib import Path
import tempfile
import threading
import time
import unittest

ROOT = Path(__file__).resolve().parents[1]
source = ast.parse((ROOT / "manager_82.py").read_text(encoding="utf-8"))
selected = []
for node in source.body:
    if isinstance(node, ast.Assign) and any(
        isinstance(t, ast.Name) and t.id in ("_CPU_ACTIVITY_LOCK", "_CPU_ACTIVITIES")
        for t in node.targets
    ):
        selected.append(node)
    elif isinstance(node, ast.FunctionDef) and node.name.startswith("_cpu_"):
        selected.append(node)
    elif isinstance(node, ast.ClassDef) and node.name == "Manager":
        methods = [n for n in node.body if isinstance(n, (ast.FunctionDef, ast.AsyncFunctionDef))
                   and n.name in ("_cpu_pending_path", "_cpu_save_report", "_cpu_load_report", "_cpu_queue_report", "_start_cpu_monitor")]
        selected.append(ast.ClassDef(name="Manager", bases=[], keywords=[], body=methods, decorator_list=[]))
ns = {"os": os, "time": time, "threading": threading, "asyncio": asyncio,
      "functools": functools, "json": json}
module = ast.fix_missing_locations(ast.Module(body=selected, type_ignores=[]))
exec(compile(module, str(ROOT / "manager_82.py"), "exec"), ns)


def put(path, content):
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(content, encoding="utf-8")


class CpuMonitorTest(unittest.TestCase):
    def setUp(self):
        self.tmp = tempfile.TemporaryDirectory()
        self.dir = Path(self.tmp.name)
        ns["BASE_DIR"] = str(self.dir / "data")
        ns["_CPU_ACTIVITIES"].clear()

    def tearDown(self):
        self.tmp.cleanup()

    def test_cgroup_v2_v1_and_missing(self):
        root = self.dir / "cg"
        proc = self.dir / "proc-cgroup"
        put(proc, "0::/tenant\n")
        put(root / "tenant" / "cpu.stat", "usage_usec 1250000\nuser_usec 800000\n")
        put(root / "cpu.stat", "usage_usec 999999999\n")
        path, version = ns["_cpu_cgroup_dir"](str(root), str(proc))
        self.assertEqual((path, version), (str(root / "tenant"), "v2"))
        self.assertEqual(ns["_cpu_group_seconds"](path, version), 1.25)
        put(proc, "5:cpu,cpuacct:/abc\n")
        put(root / "cpuacct" / "abc" / "cpuacct.usage", "2000000000\n")
        path, version = ns["_cpu_cgroup_dir"](str(root), str(proc))
        self.assertEqual((path, version), (str(root / "cpuacct" / "abc"), "v1"))
        self.assertEqual(ns["_cpu_group_seconds"](path, version), 2.0)
        self.assertEqual(ns["_cpu_cgroup_dir"](str(self.dir / "empty"), str(proc)), (None, None))

    def test_process_parsing_and_counter_reset(self):
        group, proc = self.dir / "group", self.dir / "proc"
        put(group / "cgroup.procs", "42\n43\n44\n")
        for pid, cmd, ticks, start in [(42, "manager", 80, 100),
                                       (43, "python jafj_shardd.py", 40, 200),
                                       (44, "python other.py", 20, 300)]:
            fields = ["S"] + ["0"] * 19
            fields[11], fields[12], fields[19] = str(ticks), "0", str(start)
            put(proc / str(pid) / "stat", f"{pid} (name with ) parentheses) " + " ".join(fields))
            put(proc / str(pid) / "cmdline", cmd)
        first = ns["_cpu_proc_sample"](str(group), str(proc), 42)
        self.assertEqual(first[42][2], "مدیر")
        self.assertEqual(first[43][2], "سلف‌ها/شارد")
        self.assertEqual(first[44][2], "سایر پروسه‌ها")
        old = {42: (100, 1.0, "مدیر"), 43: (200, 2.0, "سلف‌ها/شارد"), 44: (3, 1, "other")}
        new = {42: (100, 1.3, "مدیر"), 43: (200, 2.6, "سلف‌ها/شارد"), 44: (4, 100, "other")}
        deltas = ns["_cpu_proc_deltas"](old, new, 3.0)
        self.assertAlmostEqual(deltas["مدیر"], 10)
        self.assertAlmostEqual(deltas["سلف‌ها/شارد"], 20)
        self.assertNotIn("other", deltas)  # PID reused
        self.assertEqual(ns["_cpu_proc_deltas"](old, new, 0), {})

    def test_activity_and_explanation(self):
        decorator = ns["_cpu_mark_activity"]
        @decorator("ساخت و فشرده‌سازی بک‌آپ")
        def action():
            self.assertIn("ساخت و فشرده‌سازی بک‌آپ", ns["_cpu_activities_between"](0, time.monotonic()))
            raise ValueError("test")
        with self.assertRaises(ValueError):
            action()
        self.assertIsNotNone(ns["_CPU_ACTIVITIES"][-1][2])
        text = ns["_cpu_alert_text"]({"total": 27.0, "seconds": 3.0,
                                      "groups": {"مدیر": 20},
                                      "activities": ["ساخت و فشرده‌سازی بک‌آپ"]})
        self.assertIn("27.0٪", text)
        self.assertIn("مدیر: 20.0٪", text)
        self.assertIn("هم‌زمانی به معنی اثبات علت نیست", text)
        self.assertIn("علت دقیق ممکن است نامشخص", text)

    def test_monitor_detects_a_high_sample_without_blocking_loop(self):
        manager = ns["Manager"]()
        manager._cpu_monitor_started = False
        manager._cpu_monitor_stop = threading.Event()
        collected = []
        done = threading.Event()
        manager._cpu_save_report = lambda text: collected.append(text)
        def queue(report=None):
            if collected:
                done.set()
        manager._cpu_queue_report = queue
        original = {key: ns[key] for key in ("_cpu_cgroup_dir", "_cpu_group_seconds", "_cpu_proc_sample")}
        old_env = {key: os.environ.get(key) for key in ("JAFJ_HOST_LABEL", "JAFJ_CPU_MONITOR", "JAFJ_CPU_SAMPLE_SECONDS")}
        ns["_cpu_cgroup_dir"] = lambda: ("/fake", "v2")
        calls = [0]
        def usage(*_):
            calls[0] += 1
            return 0.0 if calls[0] <= 2 else 0.5
        ns["_cpu_group_seconds"] = usage
        ns["_cpu_proc_sample"] = lambda _: {}
        os.environ["JAFJ_HOST_LABEL"] = "wispbyte"
        os.environ.pop("JAFJ_CPU_MONITOR", None)
        os.environ["JAFJ_CPU_SAMPLE_SECONDS"] = "1"
        try:
            manager._start_cpu_monitor()
            self.assertTrue(done.wait(3), "high CPU sample did not produce report")
            self.assertIn("مصرف کل", collected[0])
            self.assertIn("علت دقیق ممکن است نامشخص", collected[0])
        finally:
            manager._cpu_monitor_stop.set()
            ns.update(original)
            for key, value in old_env.items():
                if value is None:
                    os.environ.pop(key, None)
                else:
                    os.environ[key] = value

    def test_save_failure_retry_and_recovery(self):
        loop = asyncio.new_event_loop()
        thread = threading.Thread(target=loop.run_forever, daemon=True)
        thread.start()
        self.addCleanup(loop.close)
        self.addCleanup(lambda: thread.join(timeout=2))
        self.addCleanup(loop.call_soon_threadsafe, loop.stop)
        manager = ns["Manager"]()
        manager._cpu_report_lock = threading.Lock()
        manager._cpu_report_in_flight = False
        manager._loop, manager.bot = loop, object()
        manager.cfg = {"admin_ids": [111]}
        messages = []
        async def fail(uid, text, key=None):
            messages.append((uid, text))
            return False
        manager.say = fail
        manager._cpu_save_report("هشدار اول")
        self.assertTrue(manager._cpu_queue_report())
        asyncio.run_coroutine_threadsafe(asyncio.sleep(0.05), loop).result(timeout=2)
        self.assertEqual(manager._cpu_load_report()["text"], "هشدار اول")
        # A new manager after a restart can deliver the stored report.
        next_manager = ns["Manager"]()
        next_manager._cpu_report_lock = threading.Lock()
        next_manager._cpu_report_in_flight = False
        next_manager._loop, next_manager.bot = loop, object()
        next_manager.cfg = {"admin_ids": [111]}
        async def success(uid, text, key=None):
            messages.append((uid, text))
            return True
        next_manager.say = success
        self.assertTrue(next_manager._cpu_queue_report())
        asyncio.run_coroutine_threadsafe(asyncio.sleep(0.05), loop).result(timeout=2)
        self.assertIsNone(next_manager._cpu_load_report())
        self.assertEqual(messages, [(111, "هشدار اول"), (111, "هشدار اول")])


if __name__ == "__main__":
    unittest.main(verbosity=2)
