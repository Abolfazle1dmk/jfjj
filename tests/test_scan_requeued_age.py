#!/usr/bin/env python3
"""A new group message must give a retried exchange a fresh queue age."""
import asyncio
import datetime
import importlib.util
import os
from pathlib import Path
import tempfile
import textwrap
import time
import unittest
from types import SimpleNamespace

ROOT = Path(__file__).resolve().parents[1]
os.environ['DATA_DIR'] = tempfile.mkdtemp(prefix='jafj-scan-age-')
spec = importlib.util.spec_from_file_location('m95_scan_age', ROOT / '95.py')
m = importlib.util.module_from_spec(spec)
spec.loader.exec_module(m)

source = (ROOT / '95.py').read_text(encoding='utf-8')
start = source.index('    async def scan_groups(manual=False):')
end = source.index('    # ---------- اسکن مستقل پیش', start)
scan_source = textwrap.dedent(source[start:end])


class DB:
    def __init__(self, status):
        self.row = {'id': 1, 'link': '@other_channel', 'status': status,
                    'created_at': int(time.time()) - 3600}
        self.rows = [self.row]

    def ex_by_link(self, link):
        return next((row for row in self.rows if link == row['link']), None)

    def ex_add(self, peer_id, peer_name, link):
        row = {'id': len(self.rows) + 1, 'link': link, 'status': 'pending',
               'created_at': int(time.time())}
        self.rows.append(row)
        return row, True

    def ex_set(self, rid, **values):
        next(row for row in self.rows if rid == row['id']).update(values)


class Message:
    id = 51
    out = False
    chat_id = 42
    raw_text = '@other_channel'

    def __init__(self, age):
        self.date = datetime.datetime.now(datetime.timezone.utc) - datetime.timedelta(seconds=age)

    async def get_sender(self):
        return SimpleNamespace(id=5, username='peer', bot=False)


class Client:
    def __init__(self, message):
        self.messages = message if isinstance(message, list) else [message]

    async def iter_messages(self, group, limit):
        for message in self.messages:
            if isinstance(message, Exception):
                raise message
            yield message


class Settings:
    def prof(self, tier):
        return {'channel': '@my_channel' if tier == 'standard' else ''}

    def save(self):
        pass


class ScanRetryAgeTest(unittest.IsolatedAsyncioTestCase):
    async def scan(self, status, message_age=0, messages=None, pick=1):
        cfg = dict(m.DEFAULTS['exchange'])
        cfg.update(groups=['@group'], scan_last={}, scan_max_age_sec=300, scan_pick=pick)
        db = DB(status)
        eng = SimpleNamespace(ex_cfg=lambda: cfg, ex_channel_ready=lambda: True,
                              st=Settings(), my_username='', my_id=7, db=db,
                              log=lambda *args: None)
        ns = dict(eng=eng, client=Client(messages if messages is not None else Message(message_age)), time=time,
                  asyncio=asyncio, random=m.random,
                  group_failover_scan_groups=m.group_failover_scan_groups,
                  group_failover_after_scan=m.group_failover_after_scan,
                  extract_links=m.extract_links,
                  FloodWaitError=type('FloodWaitError', (Exception,), {}))
        exec(scan_source, ns)
        result = await ns['scan_groups'](manual=True)
        return result, db

    async def test_fresh_message_requeues_failed_or_left_with_fresh_age(self):
        for status in ('failed', 'left'):
            with self.subTest(status=status):
                before = int(time.time())
                result, db = await self.scan(status)
                row = db.row
                self.assertEqual(result, (1, ''))
                self.assertEqual(row['status'], 'approved')
                self.assertGreaterEqual(row['created_at'], before)
                # The same age condition used by exchange_worker now allows it.
                self.assertLess(time.time() - row['created_at'], 300)

    async def test_old_message_is_not_requeued(self):
        result, db = await self.scan('left', message_age=301)
        row = db.row
        self.assertEqual(result, (0, ''))
        self.assertEqual(row['status'], 'left')
        self.assertGreater(time.time() - row['created_at'], 300)

    async def test_joined_record_not_requeued(self):
        result, db = await self.scan('joined')
        row = db.row
        self.assertEqual(result, (0, ''))
        self.assertEqual(row['status'], 'joined')
        self.assertGreater(time.time() - row['created_at'], 300)


    async def test_active_duplicate_does_not_hide_new_link(self):
        duplicate = Message(0)
        duplicate.id = 52
        fresh = Message(0)
        fresh.id = 51
        fresh.raw_text = '@new_channel'
        result, db = await self.scan('joined', messages=[duplicate, fresh])
        self.assertEqual(result, (1, ''))
        self.assertEqual(db.ex_by_link('@new_channel')['status'], 'approved')
        self.assertEqual(db.row['status'], 'joined')

    async def test_second_choice_counts_only_eligible_messages(self):
        duplicate = Message(0)
        duplicate.id = 53
        first = Message(0)
        first.id = 52
        first.raw_text = '@first_channel'
        second = Message(0)
        second.id = 51
        second.raw_text = '@second_channel'
        result, db = await self.scan('joined', messages=[duplicate, first, second], pick=2)
        self.assertEqual(result, (1, ''))
        self.assertIsNone(db.ex_by_link('@first_channel'))
        self.assertEqual(db.ex_by_link('@second_channel')['status'], 'approved')

    async def test_scan_error_is_reported(self):
        result, _ = await self.scan('joined', messages=[RuntimeError('access denied')])
        self.assertEqual(result[0], 0)
        self.assertIn('RuntimeError', result[1])
        self.assertIn('@group', result[1])

if __name__ == '__main__':
    unittest.main()
