#!/usr/bin/env python3
"""The watchdog must not race the initial boot grace-period calculation."""
import importlib.util
import os
from pathlib import Path
import tempfile
import threading
import unittest
from unittest.mock import patch

ROOT = Path(__file__).resolve().parents[1]
os.environ['DATA_DIR'] = tempfile.mkdtemp(prefix='jafj-boot-race-')
spec = importlib.util.spec_from_file_location('manager_boot_race', ROOT / 'manager_82.py')
m = importlib.util.module_from_spec(spec)
spec.loader.exec_module(m)


class FakeDB:
    def expired(self):
        return []


class BootRaceTest(unittest.TestCase):
    def test_watchdog_waits_until_initial_boot_finishes(self):
        sup = m.Supervisor({'auto_restart': True}, FakeDB())
        manager = m.Manager.__new__(m.Manager)
        manager.sup = sup
        started_plan, release_plan, booted = threading.Event(), threading.Event(), threading.Event()
        resumes = []

        def plan(_):
            started_plan.set()
            if not release_plan.wait(5):
                raise RuntimeError('test timed out')
            return 0, 'test'

        sup.boot_all = lambda force_restart=False: (booted.set() or 1)
        sup.resume_wanted = lambda **kw: resumes.append(kw)
        sup._startup_boot_pending.set()  # set before watchdog starts in Manager.run
        try:
            with patch.object(m, 'resume_grace_plan', plan):
                manager._spawn_boot(startup=True)
                self.assertTrue(started_plan.wait(3))
                # A watchdog iteration while the boot thread is planning must skip.
                with patch.object(m.time, 'sleep', side_effect=SystemExit):
                    with self.assertRaises(SystemExit):
                        sup.watchdog()
                self.assertEqual(resumes, [])
                release_plan.set()
                self.assertTrue(booted.wait(3))
                # Wait for the finally block rather than racing boot_all's return.
                with sup.boot_lock:
                    pass
            self.assertFalse(sup._startup_boot_pending.is_set())
            with patch.object(m.time, 'sleep', side_effect=SystemExit):
                with self.assertRaises(SystemExit):
                    sup.watchdog()
            self.assertEqual(len(resumes), 1)
        finally:
            release_plan.set()

    def test_startup_installs_guard_before_watchdog_thread(self):
        src = (ROOT / 'manager_82.py').read_text(encoding='utf-8')
        guard = src.index('self.sup._startup_boot_pending.set()')
        watchdog = src.index('threading.Thread(target=self.sup.watchdog', guard)
        boot = src.index('self._spawn_boot(notify_admins=False, why="بوت", startup=True)', watchdog)
        self.assertLess(guard, watchdog)
        self.assertLess(watchdog, boot)


if __name__ == '__main__':
    unittest.main()
