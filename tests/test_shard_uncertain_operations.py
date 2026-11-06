#!/usr/bin/env python3
"""Shard run/stop failures must not cause duplicate starts or delete data.

Uses fake accounts and temporary files only. Never connects to Telegram.
"""
import asyncio
import os
import sys
import tempfile
import time
import unittest
from pathlib import Path
from types import SimpleNamespace

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))
TEMP = tempfile.TemporaryDirectory(prefix='jafj-safe-shard-')
os.environ['DATA_DIR'] = TEMP.name
os.environ['PORT'] = '0'
import manager_82 as m

FAKE = '''import time
DB_FILE="jafj.db"
LOG_FILE="jafj.log"
SESSION="jafj"
RUN_LOCK="jafj.run.lock"
def main():
    while True: time.sleep(.05)
'''


class UncertainOperations(unittest.TestCase):
    def setUp(self):
        self.tmp = tempfile.TemporaryDirectory(prefix='jafj-shard-case-')
        self.root = Path(self.tmp.name)
        self.src = self.root / 'fake.py'
        self.src.write_text(FAKE)
        self.folder = self.root / '42'
        self.folder.mkdir()
        self.daemon = m.ShardDaemon(str(self.src))

    def tearDown(self):
        d = self.daemon
        d.close()
        if d.proc:
            try:
                d.proc.wait(timeout=5)
            except Exception:
                d.proc.kill()
                d.proc.wait(timeout=5)
            for f in (d.proc.stdin, d.proc.stdout):
                if f:
                    f.close()
        self.tmp.cleanup()

    def spawn(self):
        pid, err = self.daemon.spawn(self.folder, self.folder / 'run.log', 42, timeout=15)
        self.assertTrue(pid, err)
        self.daemon._probe_last = time.monotonic()
        return m._ShardProc(pid, self.daemon, 42)

    def supervisor(self, proc):
        sup = m.Supervisor.__new__(m.Supervisor)
        sup.procs = {42: proc}
        sup.db = SimpleNamespace(log=lambda *args: None)
        sup.last_failure, sup._resume_fail = {}, {}
        sup._adopt_orphan = lambda uid: False
        sup.cleared = []
        sup._clear_pid = lambda uid: sup.cleared.append(uid)
        return sup

    def test_failed_stop_preserves_handle_and_living_account(self):
        p = self.spawn()
        sup = self.supervisor(p)
        original = self.daemon._send
        def break_stop(obj):
            if obj.get('cmd') == 'stop':
                raise BrokenPipeError('simulated stop send failure')
            return original(obj)
        self.daemon._send = break_stop
        try:
            ok, msg = sup.stop(42)
            self.assertFalse(ok, msg)
            self.assertIs(sup.procs[42], p)
            self.assertEqual(sup.cleared, [])
            self.assertIn('42', self.daemon.uids)
        finally:
            self.daemon._send = original
        self.assertEqual(self.daemon._refresh_accounts(), {'42'})
        self.assertTrue(sup.stop(42)[0])
        self.assertNotIn(42, sup.procs)

    def test_failed_stop_does_not_terminate_other_accounts_in_shard(self):
        p = self.spawn()
        other = self.root / '43'
        other.mkdir()
        pid, err = self.daemon.spawn(other, other / 'run.log', 43, timeout=15)
        self.assertTrue(pid, err)
        self.daemon._probe_last = time.monotonic()
        sup = self.supervisor(p)
        original = self.daemon._send
        def fail_stop(obj):
            if obj.get('cmd') == 'stop':
                raise BrokenPipeError('synthetic failure')
            return original(obj)
        self.daemon._send = fail_stop
        try:
            self.assertFalse(sup.stop(42)[0])
        finally:
            self.daemon._send = original
        self.assertEqual(self.daemon._refresh_accounts(), {'42', '43'})
        self.assertIsNone(self.daemon.proc.poll())

    def test_timeout_stop_keeps_uid_for_retry(self):
        p = self.spawn()
        d = self.daemon
        old_send, old_read = d._send, d._read_msg
        try:
            d._send = lambda obj: None  # dropped command, account stays alive
            d._read_msg = lambda timeout: None
            self.assertFalse(d.stop_uid(42, timeout=.1))
            self.assertIn('42', d.uids)
            self.assertIsNone(p.poll())
        finally:
            d._send, d._read_msg = old_send, old_read
        self.assertEqual(d._refresh_accounts(), {'42'})

    def test_delayed_run_ack_is_not_stop_ack(self):
        d = self.daemon
        d.proc = SimpleNamespace(poll=lambda: None)
        d.uids['42'] = 999
        d._send = lambda obj: None
        replies = iter([{'ok': True, 'uid': '42', 'pid': 999}, None])
        d._read_msg = lambda timeout: next(replies, None)
        self.assertFalse(d.stop_uid(42, timeout=.1))
        self.assertIn('42', d.uids)
        d.proc = None

    def test_lost_run_ack_reserves_uid_and_ping_finds_real_account(self):
        d = self.daemon
        original = d._read_ok
        d._read_ok = lambda *args, **kwargs: None
        try:
            pid, _ = d.spawn(self.folder, self.folder / 'run.log', 42, timeout=2)
        finally:
            d._read_ok = original
        self.assertIsNone(pid)
        self.assertTrue(d.last_spawn_uncertain)
        self.assertEqual(d.uids['42'], d.proc.pid)
        self.assertIsNone(m._ShardProc(d.proc.pid, d, 42).poll())
        self.assertEqual(d._refresh_accounts(), {'42'})

    def test_unconfirmed_start_confirmed_absent_releases_reservation(self):
        d = self.daemon
        self.assertTrue(d.start(timeout=15))
        original_read, original_send = d._read_ok, d._send
        # Run request was lost, but the later ordered ping works.
        d._send = lambda obj: None if obj.get('cmd') == 'run' else original_send(obj)
        d._read_ok = lambda *args, **kwargs: None
        try:
            pid, _ = d.spawn(self.folder, self.folder / 'run.log', 42, timeout=2)
        finally:
            d._read_ok, d._send = original_read, original_send
        self.assertIsNone(pid)
        self.assertIn('42', d.uids)
        self.assertEqual(d._refresh_accounts(), set())
        self.assertNotIn('42', d.uids)
        self.assertEqual(d.room(), d.size)
        self.assertFalse(d._account_status['42'])

    def test_supervisor_unconfirmed_start_does_not_launch_fallback(self):
        d = self.daemon
        sup = self.supervisor(None)
        sup.procs.clear()
        charges_reset = []
        sup.mgr = SimpleNamespace(
            shop=SimpleNamespace(p_reset_charge=lambda uid: charges_reset.append(uid)),
            has_sub=lambda uid: False,
            effective_plan=lambda uid: None,
            sync_points_limits=lambda uid: None)
        sup.cfg = {'max_clients': 16}
        sup.last_detail = {}
        sup._ram_gate_failure = lambda uid: None
        sup.folder = lambda uid: str(self.folder)
        sup._session_ok_or_mark = lambda uid: (True, '')
        sup.sync_selfbot = lambda uid: (True, '')
        sup.python_deps_ok = lambda: True
        sup.pick_shard = lambda: d
        sup._why = lambda uid, kind, msg, **kwargs: (False, msg)
        pids, fallback = [], []
        sup._write_pid = lambda uid, pid: pids.append((uid, pid))
        sup.fork_daemon = lambda: fallback.append(True)
        (self.folder / 'jafj.session').write_text('synthetic')
        old_selfbot, old_mode, old_read = m.SELFBOT, m.spawn_mode, d._read_ok
        m.SELFBOT = str(self.src)
        m.spawn_mode = lambda *args: 'shard'
        d._read_ok = lambda *args, **kwargs: None
        try:
            ok, msg = sup._start_one(42)
        finally:
            d._read_ok = old_read
            m.SELFBOT, m.spawn_mode = old_selfbot, old_mode
        self.assertFalse(ok, msg)
        self.assertEqual(fallback, [])
        self.assertIsInstance(sup.procs[42], m._ShardProc)
        self.assertEqual(pids, [(42, d.proc.pid)])
        self.assertEqual(charges_reset, [42])
        d._probe_last = time.monotonic()
        self.assertFalse(sup._start_one(42)[0])  # not reported as already running
        manager = m.Manager.__new__(m.Manager)
        manager.sup = sup
        self.assertFalse(manager.start_service(42)[0])
        self.assertEqual(d._refresh_accounts(), {'42'})
        self.assertTrue(manager.start_service(42)[0])  # confirmed now

    def test_manager_wipes_and_restart_propagate_failures(self):
        manager = m.Manager.__new__(m.Manager)
        deletions = []
        manager._user_or_orphan = lambda uid: {'name': 'synthetic'}
        manager.effective_plan = lambda uid: None
        manager.cfg = {}
        manager.db = SimpleNamespace(get=lambda uid: {'session': 'synthetic'},
                                     delete_user=lambda uid: deletions.append(uid))
        manager.sup = SimpleNamespace(
            wipe_jafj_settings=lambda *args: {'removed_files': 0, 'was_running': True, 'error': 'stop failed'},
            wipe_folder=lambda uid: None,
            jafj_summary=lambda uid: {},
            is_running=lambda uid: True,
            stop=lambda uid: (False, 'stop failed'))
        manager._receipts, manager._join_ok = {}, {}
        manager._login_notified = None
        async def cancel(uid): pass
        async def blocking(fn, *args): return fn(*args)
        manager.cancel = cancel
        manager._backup_run_blocking = blocking
        async def exercise():
            self.assertFalse((await manager._wipe_user_jafj_locked(42))[0])
            self.assertFalse((await manager._wipe_user_data_locked(42))[0])
        asyncio.run(exercise())
        self.assertEqual(deletions, [])
        ok, _, _ = manager.start_service(42, restart=True)
        self.assertFalse(ok)

    def test_failed_stop_refuses_both_wipes_and_restart(self):
        p = self.spawn()
        sup = self.supervisor(p)
        old_clients = m.CLIENTS_DIR
        m.CLIENTS_DIR = str(self.root)
        original = self.daemon._send
        self.daemon._send = lambda obj: (_ for _ in ()).throw(BrokenPipeError())
        marker = self.folder / 'jafj.session'
        marker.write_text('synthetic data')
        calls = []
        sup.start = lambda uid: calls.append(uid)
        try:
            result = sup.wipe_jafj_settings(42)
            self.assertIn('error', result)
            self.assertTrue(marker.exists())
            self.assertIsNone(sup.wipe_folder(42))
            self.assertTrue(marker.exists())
            self.assertFalse(sup.restart(42)[0])
            self.assertEqual(calls, [])
            self.assertIs(sup.procs[42], p)
        finally:
            self.daemon._send = original
            m.CLIENTS_DIR = old_clients
        self.assertEqual(self.daemon._refresh_accounts(), {'42'})


if __name__ == '__main__':
    unittest.main()
