#!/usr/bin/env python3
"""Reproduce shard IPC races and verify safe, nonblocking manager status checks.

No real Telegram, sessions, or production data are used.
"""
import ast
import asyncio
import json
import os
from pathlib import Path
import select
import subprocess
import sys
import tempfile
import threading
import time
from types import SimpleNamespace
import unittest

ROOT = Path(__file__).resolve().parents[1]
tree = ast.parse((ROOT / 'manager_82.py').read_text(encoding='utf8'))
classes = [n for n in tree.body if isinstance(n, ast.ClassDef)
           and n.name in {'_AdoptedProc', 'ForkDaemon', 'ShardDaemon', '_ShardProc'}]
ns = dict(os=os, json=json, sys=sys, time=time, threading=threading,
          subprocess=__import__('subprocess'), SELFBOT=str(ROOT / '95.py'),
          shard_size=lambda: 16, __file__=str(ROOT / 'manager_82.py'))
exec(compile(ast.fix_missing_locations(ast.Module(body=classes, type_ignores=[])),
             str(ROOT / 'manager_82.py'), 'exec'), ns)
ForkDaemon, ShardDaemon, ShardProc = ns['ForkDaemon'], ns['ShardDaemon'], ns['_ShardProc']
manager_node = next(n for n in tree.body if isinstance(n, ast.ClassDef) and n.name == 'Manager')
points_method = next(n for n in manager_node.body if isinstance(n, ast.AsyncFunctionDef) and n.name == 'points_loop')
points_class = ast.ClassDef(name='PointsManager', bases=[], keywords=[], body=[points_method], decorator_list=[])
ns['asyncio'] = asyncio
exec(compile(ast.fix_missing_locations(ast.Module(body=[points_class], type_ignores=[])),
             str(ROOT / 'manager_82.py'), 'exec'), ns)


class ShardIpcTest(unittest.TestCase):
    def test_select_then_read_race_has_bounded_timeout(self):
        # Both readers observe one readable pipe. The second read must see
        # EAGAIN and honor the deadline, never block forever as the old code did.
        d = ForkDaemon(selfbot='synthetic')
        rd, wr = os.pipe()
        os.set_blocking(rd, False)
        output = os.fdopen(rd, 'rb', buffering=0)
        d.proc = SimpleNamespace(stdout=output, poll=lambda: None)
        barrier, original_select = threading.Barrier(2), select.select
        def synced_select(*args, **kwargs):
            ready = original_select(*args, **kwargs)
            if ready[0]:
                barrier.wait(2)
            return ready
        results, errors = [], []
        def read():
            try: results.append(d._read_msg(.2))
            except Exception as e: errors.append(e)
        select.select = synced_select
        threads = [threading.Thread(target=read, daemon=True) for _ in range(2)]
        try:
            os.write(wr, b'{"ok":true}\n')
            for thread in threads: thread.start()
            for thread in threads: thread.join(1)
            self.assertFalse(any(thread.is_alive() for thread in threads))
            self.assertEqual(errors, [])
            self.assertIn({'ok': True}, results)
            self.assertIn(None, results)
        finally:
            os.close(wr)
            for thread in threads: thread.join(1)
            select.select = original_select
            output.close()

    def test_drain_never_steals_an_inflight_reply(self):
        d = ForkDaemon(selfbot='synthetic')
        rd, wr = os.pipe()
        os.set_blocking(rd, False)
        output = os.fdopen(rd, 'rb', buffering=0)
        d.proc = SimpleNamespace(stdout=output, poll=lambda: None)
        try:
            os.write(wr, b'{"ok":true,"pid":123,"uid":"1"}\n')
            d._lock.acquire()
            try:
                self.assertFalse(d.drain())
                self.assertEqual(d._read_ok(.2)['pid'], 123)
            finally:
                d._lock.release()
        finally:
            os.close(wr)
            output.close()

    def test_late_ping_not_misidentified_as_run_response(self):
        d = ForkDaemon(selfbot='synthetic')
        messages = iter([{'ok': True, 'accounts': []},
                         {'ok': True, 'uid': '1'},  # late stop reply
                         {'ok': True, 'pid': 999, 'uid': 'another'},
                         {'ok': True, 'pid': 123, 'uid': '1'}])
        d._read_msg = lambda timeout: next(messages, None)
        self.assertEqual(d._read_ok(.2, expected_uid='1')['pid'], 123)

    def test_cached_probe_cannot_freeze_loop_or_duplicate_session(self):
        d = ShardDaemon(selfbot='synthetic')
        d.proc = SimpleNamespace(poll=lambda: None)
        d.uids['123'] = 456
        d._account_status['123'] = True
        p = ShardProc(456, d, 123)
        d._lock.acquire()
        async def exercise():
            # The worker waits on a locked IPC channel, not the event loop.
            self.assertIsNone(p.poll())
            await asyncio.wait_for(asyncio.sleep(.03), .3)
            self.assertIsNone(p.poll())
            self.assertEqual(p.returncode, None)
        try:
            asyncio.run(exercise())
        finally:
            # Let the worker exit without writing to a fabricated stdin.
            d.proc.poll = lambda: 1
            d._lock.release()
        for _ in range(100):
            with d._status_lock:
                if not d._probe_inflight: break
            time.sleep(.01)
        self.assertFalse(d._probe_inflight)
        self.assertEqual(p.poll(), 1)  # actual dead daemon, not a timeout

    def test_many_checks_reuse_one_inflight_probe(self):
        d = ShardDaemon(selfbot='synthetic')
        d.proc = SimpleNamespace(poll=lambda: None)
        d.uids['1'] = 777
        entered, release = threading.Event(), threading.Event()
        calls = []
        def slow_probe():
            calls.append(1)
            entered.set()
            release.wait(3)
        d._refresh_accounts = slow_probe
        p = ShardProc(777, d, 1)
        try:
            self.assertIsNone(p.poll())
            self.assertTrue(entered.wait(1))
            for _ in range(1000):
                self.assertIsNone(p.poll())
            self.assertEqual(calls, [1])
        finally:
            release.set()
        for _ in range(100):
            with d._status_lock:
                if not d._probe_inflight: break
            time.sleep(.01)
        self.assertFalse(d._probe_inflight)

    def test_slow_real_ipc_keeps_event_loop_responsive_then_detects_exit(self):
        # The fake server answers after 0.6 seconds; ordinary asyncio work
        # must continue immediately, and absence is used only after confirmation.
        server = ("import sys,json,time\n"
                  "for line in sys.stdin:\n"
                  " m=json.loads(line)\n"
                  " if m.get('cmd')=='ping':\n"
                  "  time.sleep(.6)\n"
                  "  print(json.dumps({'ok':True,'accounts':[],"
                  "'request_id':m.get('request_id')}),flush=True)\n")
        proc = subprocess.Popen([sys.executable, '-u', '-c', server],
                                stdin=subprocess.PIPE, stdout=subprocess.PIPE,
                                stderr=subprocess.DEVNULL, bufsize=0)
        os.set_blocking(proc.stdout.fileno(), False)
        d = ShardDaemon(selfbot='synthetic')
        d.proc = proc
        d.uids['1'] = proc.pid
        d._account_status['1'] = True
        p = ShardProc(proc.pid, d, '1')
        async def exercise():
            before = time.monotonic()
            self.assertIsNone(p.poll())
            await asyncio.wait_for(asyncio.sleep(.05), .3)
            self.assertLess(time.monotonic() - before, .3)
            self.assertIsNone(p.poll())  # no false death while waiting
            for _ in range(150):
                with d._status_lock:
                    done = not d._probe_inflight
                if done: break
                await asyncio.sleep(.01)
            self.assertTrue(done)
            self.assertEqual(p.poll(), 1)  # confirmed absent
        try:
            asyncio.run(exercise())
        finally:
            proc.terminate()
            proc.wait(timeout=5)
            proc.stdin.close()
            proc.stdout.close()

    def test_ping_ignores_stale_responses_and_uid_exits_are_isolated(self):
        d = ShardDaemon(selfbot='synthetic')
        d.proc = SimpleNamespace(poll=lambda: None)
        d.uids.update({'1': 777, '2': 777})
        d._account_status.update({'1': True, '2': True})
        d._drain_locked = lambda *args: None
        captured = []
        d._send = captured.append
        responses = iter([{'ok': True, 'accounts': [], 'request_id': 999},
                          {'ok': True, 'accounts': ['1', '2'], 'request_id': 1}])
        d._read_msg = lambda timeout: next(responses, None)
        self.assertEqual(d._refresh_accounts(), {'1', '2'})
        self.assertEqual(captured[0]['request_id'], 1)
        self.assertTrue(d._account_status['1'])
        self.assertTrue(d._account_status['2'])
        d._account_status['1'] = False
        d.uid_exits.update({'1': 77, '2': 0})
        d._probe_last = time.monotonic()  # use cached known status
        p1, p2 = ShardProc(777, d, '1'), ShardProc(777, d, '2')
        self.assertEqual(p1.poll(), 77)
        self.assertIsNone(p2.poll())

    def test_unanswered_probe_does_not_mark_session_dead(self):
        d = ShardDaemon(selfbot='synthetic')
        d.proc = SimpleNamespace(poll=lambda: None)
        d.uids['1'] = 777
        d._account_status['1'] = True
        d._drain_locked = lambda *args: None
        d._send = lambda message: None
        d._read_msg = lambda timeout: None  # shard didn't reply
        self.assertIsNone(d._refresh_accounts())
        d._probe_last = time.monotonic()
        self.assertIsNone(ShardProc(777, d, '1').poll())

    def test_fork_exit_code_waits_for_busy_reader(self):
        d = ForkDaemon(selfbot='synthetic')
        d.exits[123] = 77
        p = ns['_AdoptedProc'](123, d)
        d._lock.acquire()
        try:
            self.assertIsNone(p._exit_code())
        finally:
            d._lock.release()
        self.assertEqual(p._exit_code(), 77)

    def test_points_are_not_charged_during_prolonged_unconfirmed_shard_state(self):
        d = ShardDaemon(selfbot='synthetic')
        d.proc = SimpleNamespace(poll=lambda: None)
        d.uids['1'] = 777
        d._account_status['1'] = True
        d._status_verified_at['1'] = time.monotonic() - 121
        proc = ShardProc(777, d, '1')
        calls = []
        shop = SimpleNamespace(p_reset_charge=lambda uid: calls.append(('reset', uid)),
                               p_charge_due=lambda uid, per: (calls.append(('charge', uid)) or (0, 99, False)))
        manager = ns['PointsManager']()
        manager.shop = shop
        manager.cfg = {'points_on': True, 'cost_per_hour': 1, 'low_warn': 5}
        manager.db = SimpleNamespace(all=lambda status: [{'uid': 1}])
        manager.sup = SimpleNamespace(is_running=lambda uid: True, procs={1: proc})
        manager.has_sub = lambda uid: False
        manager.trial_active = lambda uid: False
        async def run_once():
            task = asyncio.create_task(manager.points_loop())
            await asyncio.sleep(.02)
            task.cancel()
            with self.assertRaises(asyncio.CancelledError): await task
        asyncio.run(run_once())
        self.assertEqual(calls, [('reset', 1)])
        calls.clear()
        d._status_verified_at['1'] = time.monotonic()
        asyncio.run(run_once())
        self.assertEqual(calls, [('charge', 1)])
        calls.clear()
        manager.sup.is_running = lambda uid: False
        asyncio.run(run_once())
        self.assertEqual(calls, [('reset', 1)])

    def test_shard_protocol_real_process_and_account_lifecycle(self):
        # Two synthetic accounts share one real shard; stopping one must not
        # mark the other dead. The fake account never talks to Telegram.
        with tempfile.TemporaryDirectory() as td:
            root = Path(td)
            source = root / 'self.py'
            source.write_text('import time\ndef main():\n    while True: time.sleep(.05)\n')
            d = ShardDaemon(selfbot=str(source), size=3)
            try:
                for uid in ('111', '222'):
                    folder = root / uid
                    folder.mkdir()
                    pid, err = d.spawn(folder, folder / 'run.log', uid, timeout=15)
                    self.assertTrue(pid, err)
                a, b = ShardProc(d.uids['111'], d, '111'), ShardProc(d.uids['222'], d, '222')
                self.assertIsNone(a.poll_confirmed())
                self.assertIsNone(b.poll_confirmed())
                self.assertTrue(d.stop_uid('111', timeout=10))
                # Real ping echoes request_id, excludes 111, includes 222.
                self.assertEqual(d._refresh_accounts(), {'222'})
                self.assertIsNotNone(a.poll_confirmed())
                self.assertIsNone(b.poll_confirmed())
            finally:
                d.close()
                if d.proc:
                    try: d.proc.wait(timeout=5)
                    except Exception:
                        d.proc.kill()
                        d.proc.wait(timeout=5)
                    d.proc.stdin.close()
                    d.proc.stdout.close()


if __name__ == '__main__':
    unittest.main()
