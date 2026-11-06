#!/usr/bin/env python3
"""The membership load optimization must preserve counts and scheduling.

Synthetic, temporary SQLite databases only; no Telegram or customer data.
"""
import ast
import importlib.util
import os
from pathlib import Path
import random
import sys
import tempfile
import threading
import unittest

ROOT = Path(__file__).resolve().parents[1]
os.environ['DATA_DIR'] = tempfile.mkdtemp(prefix='jafj-count-test-')
spec = importlib.util.spec_from_file_location('selfbot_cpu_test', ROOT / '95.py')
m = importlib.util.module_from_spec(spec)
sys.modules[spec.name] = m
spec.loader.exec_module(m)


class MembershipCountTests(unittest.TestCase):
    def setUp(self):
        self.db = m.DB(':memory:')

    def tearDown(self):
        self.db.conn.close()

    def add(self, n, status, start=0):
        with self.db.lock:
            self.db.conn.executemany(
                'INSERT INTO exchange (link,status,created_at,last_check,note) VALUES (?,?,?,?,?)',
                ((f'{status}-{start+i}', status, i, i % 7, 'x' * 400)
                 for i in range(n)))
            self.db.conn.commit()

    def assert_equivalent(self):
        old = len(self.db.ex_list('joined', 500))
        new = self.db.ex_joined_count_capped()
        self.assertEqual(new, old)
        old_gate, new_gate = m.CheckGate(), m.CheckGate()
        old_gate.set_load(old)
        new_gate.set_load(new)
        self.assertEqual(old_gate.base_gap, new_gate.base_gap)

    def test_boundaries_and_unrelated_statuses(self):
        self.add(67, 'pending')
        self.add(54, 'left')
        for start, n in ((0, 0), (0, 1), (1, 13), (14, 485), (499, 1), (500, 1), (501, 4499)):
            with self.subTest(total=start+n):
                self.add(n, 'joined', start)
                self.assert_equivalent()
                self.assertEqual(self.db.ex_joined_count_capped(), min(500, start+n))

    def test_status_changes_and_missing_index(self):
        self.add(1100, 'joined')
        self.add(600, 'approved')
        with self.db.lock:
            self.db.conn.execute("UPDATE exchange SET status='left' WHERE id % 3 = 0")
            self.db.conn.execute("UPDATE exchange SET status='joined' WHERE status='approved' AND id % 2 = 0")
            self.db.conn.commit()
        self.assert_equivalent()
        with self.db.lock:
            for name in ('idx_ex', 'idx_ex_next_check', 'idx_ex_rem'):
                self.db.conn.execute(f'DROP INDEX IF EXISTS {name}')
            self.db.conn.commit()
        self.assert_equivalent()

    def test_read_only(self):
        self.add(550, 'joined')
        before = self.db.conn.total_changes
        data = self.db.conn.execute('SELECT * FROM exchange ORDER BY id').fetchall()
        self.assertEqual(self.db.ex_joined_count_capped(), 500)
        self.assertEqual(self.db.conn.total_changes, before)
        self.assertEqual(data, self.db.conn.execute('SELECT * FROM exchange ORDER BY id').fetchall())

    def test_concurrent_updates_remain_equivalent_on_same_snapshot(self):
        self.add(550, 'joined')
        self.add(50, 'pending')
        errors = []
        def writer():
            try:
                rng = random.Random(7)
                for _ in range(300):
                    with self.db.lock:
                        self.db.conn.execute('UPDATE exchange SET status=? WHERE id=?',
                            (rng.choice(['joined', 'pending', 'left']), rng.randint(1, 600)))
                        self.db.conn.commit()
            except Exception as exc:
                errors.append(exc)
        thread = threading.Thread(target=writer)
        thread.start()
        try:
            for _ in range(300):
                with self.db.lock:
                    self.assert_equivalent()
        finally:
            thread.join(timeout=5)
        self.assertFalse(thread.is_alive())
        self.assertEqual(errors, [])

    def test_membership_loop_uses_bounded_count_and_original_sleep(self):
        source = (ROOT / '95.py').read_text(encoding='utf8')
        begin = source.index('    async def membership_loop():')
        end = source.index('    async def exchange_worker():', begin)
        block = source[begin:end]
        self.assertIn('check_gate.set_load(eng.db.ex_joined_count_capped())', block)
        self.assertIn('await asyncio.sleep(2)', block)
        ast.parse(source)


if __name__ == '__main__':
    unittest.main()
