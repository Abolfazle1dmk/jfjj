#!/usr/bin/env python3
"""Synthetic safety tests; no Telegram or production data is used."""
import ast
import asyncio
from datetime import datetime
import json
import os
from pathlib import Path
import re
import shutil
import sqlite3
import tempfile
import threading
import time
import unittest
import zipfile

ROOT = Path(__file__).resolve().parents[1]
tree = ast.parse((ROOT / 'manager_82.py').read_text(encoding='utf8'))
methods = {'_looks_sqlite', '_sqlite_snapshot', '_iter_backup_sources',
           '_write_backup_zip', '_backup_fingerprint', '_backup_operation_lock',
           '_backup_run_blocking', 'backup_once', '_backup_once_locked',
           'restore_from_backup', 'wipe_user_data', 'admin_cmd', 'user_cmd'}
nodes = []
for node in tree.body:
    if isinstance(node, ast.FunctionDef) and node.name in {
        '_h', '_hanglog_text', 'backup_file_skipped', 'backup_arc_essential'
    }:
        nodes.append(node)
    elif isinstance(node, ast.ClassDef) and node.name == 'Manager':
        selected = [n for n in node.body if isinstance(n, (ast.FunctionDef, ast.AsyncFunctionDef)) and n.name in methods]
        nodes.append(ast.ClassDef(name='Manager', bases=[], keywords=[], body=selected, decorator_list=[]))
ns = dict(os=os, re=re, json=json, asyncio=asyncio, datetime=datetime, sqlite3=sqlite3,
          time=time, shutil=shutil, tempfile=tempfile, zipfile=zipfile,
          _cpu_mark_activity=lambda label: lambda fn: fn,
          BOT_BACKUP_MAX_BYTES=45 * 1024 * 1024,
          _BACKUP_SKIP_SUFFIXES=('.log', '-wal', '-shm', '-journal', '.tmp', '.bak'),
          _BACKUP_SKIP_NAMES={'run.log', '95.py', 'jafj_self.py', 'jafj_status.json'},
          _BACKUP_ESSENTIAL={'manager.db', 'shop.db', 'manager_config.json',
                             'manager_bot.string', 'jafj.session', 'jafj_settings.json'},
          BACKUP_TAG='BACKUP', BUILD_VERSION='test')
exec(compile(ast.fix_missing_locations(ast.Module(body=nodes, type_ignores=[])), str(ROOT / 'manager_82.py'), 'exec'), ns)
Manager = ns['Manager']


class SafetyTest(unittest.TestCase):
    def setUp(self):
        self.tmp = tempfile.TemporaryDirectory()
        self.d = Path(self.tmp.name)
        ns.update(BASE_DIR=str(self.d), CLIENTS_DIR=str(self.d / 'clients'),
                  DB_FILE=str(self.d / 'manager.db'), SHOP_DB=str(self.d / 'shop.db'),
                  CONFIG_FILE=str(self.d / 'manager_config.json'),
                  BOT_SESSION_FILE=str(self.d / 'manager_bot.string'),
                  BOT_BACKUP_MAX_BYTES=45 * 1024 * 1024)
        self.manager = Manager()

    def tearDown(self):
        self.tmp.cleanup()

    def test_wal_snapshot_roundtrip_and_snapshot_failure(self):
        db = sqlite3.connect(ns['DB_FILE'])
        db.execute('PRAGMA journal_mode=WAL')
        db.execute('CREATE TABLE clients (name TEXT)')
        db.execute("INSERT INTO clients VALUES ('synthetic customer')")
        db.commit()
        self.assertTrue(Path(ns['DB_FILE'] + '-wal').exists())
        client = self.d / 'clients' / '123'
        client.mkdir(parents=True)
        session = sqlite3.connect(str(client / 'jafj.session'))
        session.execute('CREATE TABLE sessions (token TEXT)')
        session.execute("INSERT INTO sessions VALUES ('synthetic session')")
        session.commit()
        session.close()
        (client / 'jafj_settings.json').write_text('{"enabled":true}')
        Path(ns['CONFIG_FILE']).write_text('{"backup_msg_id":1}')
        archive = self.d / 'out.zip'
        count, size, omitted = self.manager._write_backup_zip(str(archive))
        self.assertGreaterEqual(count, 4)
        self.assertGreater(size, 0)
        self.assertEqual(omitted, [])
        with zipfile.ZipFile(archive) as z:
            self.assertIsNone(z.testzip())
            self.assertNotIn('manager.db-wal', z.namelist())
            z.extract('manager.db', self.d / 'restore')
            z.extract('clients/123/jafj.session', self.d / 'restore')
        restored = sqlite3.connect(self.d / 'restore' / 'manager.db')
        self.assertEqual(restored.execute('PRAGMA integrity_check').fetchone()[0], 'ok')
        self.assertEqual(restored.execute('SELECT name FROM clients').fetchone()[0], 'synthetic customer')
        restored.close()
        restored = sqlite3.connect(self.d / 'restore' / 'clients/123/jafj.session')
        self.assertEqual(restored.execute('SELECT token FROM sessions').fetchone()[0], 'synthetic session')
        restored.close()
        db.close()
        # A real SQLite header with an unusable DB must fail, not upload raw WAL-less data.
        Path(ns['DB_FILE']).write_bytes(b'SQLite format 3\x00' + b'broken')
        with self.assertRaisesRegex(RuntimeError, 'sqlite'):
            self.manager._write_backup_zip(str(archive))

    def test_compression_falls_back_before_rejecting(self):
        Path(ns['CONFIG_FILE']).write_bytes(b'a' * 1_000_000)
        ns['BOT_BACKUP_MAX_BYTES'] = 4000
        archive = self.d / 'out.zip'
        _, size, _ = self.manager._write_backup_zip(str(archive))
        self.assertLess(size, 4000)
        with zipfile.ZipFile(archive) as z:
            self.assertEqual(z.read('manager_config.json'), b'a' * 1_000_000)
        small = self.d / 'level1.zip'
        with zipfile.ZipFile(small, 'w', zipfile.ZIP_DEFLATED, compresslevel=1) as z:
            z.write(ns['CONFIG_FILE'], 'manager_config.json')
        self.assertGreater(small.stat().st_size, 4000)

    def test_fingerprint_ignores_only_pointer_metadata(self):
        path = Path(ns['CONFIG_FILE'])
        path.write_text(json.dumps({'backup_msg_id': 1, 'backup_msg_chat': '123', 'foo': 'old'}))
        a = self.manager._backup_fingerprint()
        path.write_text(json.dumps({'backup_msg_id': 2, 'backup_msg_chat': '456', 'foo': 'old'}))
        self.assertEqual(a, self.manager._backup_fingerprint())
        path.write_text(json.dumps({'backup_msg_id': 2, 'backup_msg_chat': '456', 'foo': 'new'}))
        self.assertNotEqual(a, self.manager._backup_fingerprint())

    def test_hanglog_bounded_redacted_latest_event_and_admin_only(self):
        p = self.d / 'hang.log'
        self.assertIn('پیدا نشد', ns['_hanglog_text']())
        p.write_text('', encoding='utf8')
        self.assertIn('خالی', ns['_hanglog_text']())
        p.write_text('===== 2026-01-01 00:00:00 pid=42 host=secret\n'
                     'Thread 0x10 (most recent call first):\n'
                     '  File "/old/private.py", line 99 in old\n'
                     '===== 2026-11-06 12:07:00 pid=42 host=secret\n'
                     'Current thread 0x123 (most recent call first):\n'
                     '  File "/home/private+989121112233/manager_82.py", line 123 in backup_once\n'
                     '    password = "TOKEN_SECRET"\n'
                     '  File "/customer/989121112233.py", line 34 in token123456789\n'
                     + ('irrelevant TOKEN_SECRET\n' * 1000), encoding='utf8')
        text = ns['_hanglog_text']()
        self.assertIn('manager_82.py:123 backup_once', text)
        self.assertNotIn('private', text)
        self.assertNotIn('TOKEN_SECRET', text)
        self.assertNotIn('989121112233', text)
        self.assertNotIn('old.py', text)
        self.assertLess(len(text), 4096)
        seen = []
        async def say(chat, text, *a):
            seen.append((chat, text))
            return True
        self.manager.say = say
        self.manager.is_admin = lambda uid: uid == 77
        self.manager.db = type('Db', (), {'get': lambda self, uid: {'name': 'synthetic', 'status': 'active'}})()
        async def exercise():
            await self.manager.admin_cmd(77, -100, 'hanglog', '')
            self.assertEqual(seen[-1][0], 77)  # Never disclose in group.
            await self.manager.admin_cmd(88, 88, 'hanglog', '')
            self.assertNotIn('manager_82.py', seen[-1][1])
            await self.manager.user_cmd(88, 88, 'hanglog', '', {})
            self.assertNotIn('manager_82.py', seen[-1][1])
            self.assertIn('فقط برای مدیر', seen[-1][1])
        asyncio.run(exercise())

    def test_worker_cancel_cleanup_serialization_and_dirty_fingerprint(self):
        started, release = threading.Event(), threading.Event()
        m = self.manager
        m.bot, m.cfg = object(), {'admin_ids': [77]}
        m.fp, m.saved, m.paths = ('before',), None, []
        m._backup_target = lambda: 77
        async def public(target): return False, ''
        m._backup_target_is_public = public
        m._backup_fingerprint = lambda: m.fp
        m._load_backup_fp = lambda: None
        m._save_backup_fp = lambda fp: setattr(m, 'saved', fp)
        m._remember_backup_pointer = lambda *args: None
        m._save_local_backup_copy = lambda *args: None
        m._extra_admin_targets = lambda target: []
        m.db = type('Db', (), {'c': type('C', (), {'commit': lambda s: None})(),
                               'x': lambda s, *args: {'c': 1}})()
        m.shop = None
        def write(path):
            m.paths.append(path)
            Path(path).write_bytes(b'valid test zip placeholder')
            started.set()
            release.wait(3)
            return 1, os.path.getsize(path), []
        m._write_backup_zip = write
        async def upload(target, path, caption):
            m.fp = ('changed during upload',)
            return target, type('Msg', (), {'id': 10})()
        m._upload_backup = upload
        async def restore(*args): return True, 'restored'
        m._restore_from_backup_locked = restore
        async def wipe(*args): return True, 'wiped', {}
        m._wipe_user_data_locked = wipe
        async def exercise():
            first = asyncio.create_task(m.backup_once())
            for _ in range(200):
                if started.is_set(): break
                await asyncio.sleep(.005)
            self.assertTrue(started.is_set())
            # Event loop stays live while the ZIP worker waits; lock also covers restore.
            other = asyncio.create_task(m.restore_from_backup())
            wipe_task = asyncio.create_task(m.wipe_user_data(123))
            await asyncio.sleep(.03)
            self.assertFalse(other.done())
            self.assertFalse(wipe_task.done())
            first.cancel()
            await asyncio.sleep(.03)
            self.assertFalse(first.done())
            self.assertTrue(os.path.exists(m.paths[0]))
            release.set()
            with self.assertRaises(asyncio.CancelledError): await first
            self.assertFalse(os.path.exists(m.paths[0]))
            self.assertEqual(await other, (True, 'restored'))
            self.assertEqual(await wipe_task, (True, 'wiped', {}))
            ok, _ = await m.backup_once()
            self.assertTrue(ok)
            self.assertEqual(m.saved, ('before',))
            self.assertEqual(m.fp, ('changed during upload',))
            self.assertFalse(os.path.exists(m.paths[-1]))
        asyncio.run(exercise())


if __name__ == '__main__':
    unittest.main()
