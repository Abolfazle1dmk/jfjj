"""A running process is not necessarily a ready panel; fork has no wait()."""
import os
import sys
import tempfile
import time
import unittest
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))
os.environ.setdefault('DATA_DIR', tempfile.mkdtemp(prefix='jafj_restart_test_'))
import manager_82 as M


class ProcessHandle:
    pid = 1234
    def __init__(self, exit_after, code):
        self.start = time.monotonic()
        self.exit_after = exit_after
        self.code = code
    def poll(self):
        return self.code if time.monotonic() - self.start >= self.exit_after else None


class DB:
    def log(self, *args):
        pass


class Tests(unittest.TestCase):
    def make_supervisor(self, handle):
        sup = M.Supervisor.__new__(M.Supervisor)
        sup.procs = {12: handle}
        sup.db = DB()
        sup.last_failure = {}
        sup.last_detail = {}
        sup.last_ready = {}
        sup.tail = lambda *args: 'Traceback (most recent call last):\nValueError: broken'
        sup._clear_pid = lambda *args: None
        sup._bump_fail = lambda *args: None
        sup._notify_start_failure = lambda *args: None
        return sup

    def test_poll_only_handle_late_exit_detected(self):
        p = ProcessHandle(.3, 1)
        sup = self.make_supervisor(p)
        sup._watch_start(12, p, delay=2)
        until = time.monotonic() + 3
        while 12 not in sup.last_failure and time.monotonic() < until:
            time.sleep(.02)
        self.assertEqual(sup.last_failure.get(12), 'selfbot')
        self.assertNotIn(12, sup.procs)

    def test_running_handle_waits_before_diagnosis(self):
        p = ProcessHandle(100, 1)
        sup = self.make_supervisor(p)
        checked = []
        sup.readiness = lambda *args, **kwargs: (checked.append(time.monotonic()) or {'ready': True})
        start = time.monotonic()
        sup._watch_start(12, p, delay=.4)
        until = start + 2
        while not checked and time.monotonic() < until:
            time.sleep(.02)
        self.assertTrue(checked)
        self.assertGreaterEqual(checked[0] - start, .35)

    def test_labels_distinguish_process_from_panel(self):
        class Sup:
            running = True
            ready = None
            def is_running(self, uid): return self.running
            def readiness(self, uid, proc_alive=None): return {'ready': self.ready}
        manager = M.Manager.__new__(M.Manager)
        manager.sup = Sup()
        self.assertIn('تأیید نشده', manager.service_run_label(1))
        manager.sup.ready = True
        self.assertIn('تأیید شد', manager.service_run_label(1))
        manager.sup.running = False
        self.assertIn('خاموش', manager.service_run_label(1))


if __name__ == '__main__':
    unittest.main()
