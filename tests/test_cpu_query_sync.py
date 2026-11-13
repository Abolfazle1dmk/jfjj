"""Regression tests for risk indexes and the unchanged sync fast path."""
import importlib.util
import os
from pathlib import Path
import sqlite3
import tempfile
import time
import unittest
from unittest import mock

ROOT = Path(__file__).resolve().parents[1]


def load(path, name):
    spec = importlib.util.spec_from_file_location(name, ROOT / path)
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return module


class CpuOptimizations(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.selfbot = load('95.py', 'selfbot_cpu_test')
        cls.sync = load('tools/gh_data_sync.py', 'sync_cpu_test')

    def test_existing_database_and_flood_matching(self):
        with tempfile.TemporaryDirectory() as tmp:
            path = os.path.join(tmp, 'account.db')
            # Opening an existing database must create the indexes too.
            db = self.selfbot.DB(path)
            db.conn.close()
            db = self.selfbot.DB(path)
            try:
                indexes = {row[0] for row in db.conn.execute(
                    "SELECT name FROM sqlite_master WHERE type='index'")}
                self.assertTrue({'idx_events_flood_ts', 'idx_events_kind_ts',
                                 'idx_queue_sent', 'idx_ex_joined'} <= indexes)
                now = int(time.time())
                for kind in ('flood', 'CUSTOM_FLOOD_EVENT', 'not-a-match'):
                    db._x('INSERT INTO events(ts,level,kind) VALUES(?,?,?)',
                          (now, 'warn', kind))
                sql = "SELECT COUNT(*) FROM events WHERE lower(kind) LIKE '%flood%' AND ts>=?"
                self.assertEqual(db.conn.execute(sql, (now - 60,)).fetchone()[0], 2)
                plan = str(list(db.conn.execute('EXPLAIN QUERY PLAN ' + sql, (now - 60,)))[0][3])
                self.assertIn('idx_events_flood_ts', plan)
                eng = self.selfbot.Engine.__new__(self.selfbot.Engine)
                eng.db = db
                eng.st = {'risk': {}}
                self.assertEqual(eng.real_risk_edge(now)[2]['flood'], 2)
                db.log('warn', 'another_flood', 'new')
                self.assertEqual(eng.real_risk_edge(now)[2]['flood'], 3)
            finally:
                db.conn.close()

    def test_unchanged_snapshot_skips_compression(self):
        with tempfile.TemporaryDirectory() as tmp, mock.patch.dict(os.environ, {'DATA_DIR': tmp}):
            config = Path(tmp) / 'manager_config.json'
            config.write_text('{"version": 1}')
            blob, manifest = self.sync.build_bundle()
            self.assertIsNotNone(blob)
            with mock.patch.object(self.sync.zipfile, 'ZipFile', side_effect=AssertionError('compressed')):
                result, same = self.sync.build_bundle(manifest['fingerprint'])
            self.assertIsNone(result)
            self.assertEqual(manifest['fingerprint'], same['fingerprint'])
            config.write_text('{"version": 2}')
            changed, newer = self.sync.build_bundle(manifest['fingerprint'])
            self.assertIsNotNone(changed)
            self.assertNotEqual(manifest['fingerprint'], newer['fingerprint'])


if __name__ == '__main__':
    unittest.main()
