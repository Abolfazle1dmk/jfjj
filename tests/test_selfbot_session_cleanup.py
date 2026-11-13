"""Each failed connection attempt must close the SQLite session before retry."""
import ast
import asyncio
import sqlite3
import sys
import tempfile
import types
import unittest
from pathlib import Path
from unittest.mock import patch

SOURCE = Path(__file__).resolve().parents[1] / '95.py'
module = ast.parse(SOURCE.read_text(encoding='utf-8'))
wrapper = next(n for n in module.body if isinstance(n, ast.AsyncFunctionDef)
               and n.name == 'connect_and_run')


class SessionCleanup(unittest.IsolatedAsyncioTestCase):
    async def test_retry_releases_database_lock(self):
        with tempfile.TemporaryDirectory() as tmp:
            path = str(Path(tmp) / 'jafj.session')
            with sqlite3.connect(path) as db:
                db.execute('create table t (x integer)')
            clients = []
            class Client:
                def __init__(self, *args, **kwargs):
                    self.db = sqlite3.connect(path, timeout=0)
                    clients.append(self)
                async def disconnect(self):
                    self.db.rollback()
                    self.db.close()
            async def attempt(eng, creds, client):
                client.db.execute('begin exclusive')
                client.db.execute('insert into t values (1)')
                return 'retry'
            ns = {'SESSION': 'jafj', '_connect_and_run_client': attempt}
            exec(compile(ast.Module(body=[wrapper], type_ignores=[]), str(SOURCE), 'exec'), ns)
            with patch.dict(sys.modules, {'telethon': types.SimpleNamespace(TelegramClient=Client)}):
                self.assertEqual(await ns['connect_and_run'](None, {'api_id': 1, 'api_hash': 'x'}), 'retry')
                # A second connection would fail with "database is locked" if
                # the first attempt left its transaction and session open.
                with sqlite3.connect(path, timeout=0) as db:
                    db.execute('insert into t values (2)')
                self.assertEqual(await ns['connect_and_run'](None, {'api_id': 1, 'api_hash': 'x'}), 'retry')

    async def test_session_closed_if_disconnect_fails(self):
        closed = []
        class Session:
            def close(self): closed.append(True)
        class Client:
            def __init__(self, *args, **kwargs): self.session = Session()
            async def disconnect(self): raise sqlite3.OperationalError('database is locked')
        async def attempt(*args): return 'retry'
        ns = {'SESSION': 'jafj', '_connect_and_run_client': attempt}
        exec(compile(ast.Module(body=[wrapper], type_ignores=[]), str(SOURCE), 'exec'), ns)
        with patch.dict(sys.modules, {'telethon': types.SimpleNamespace(TelegramClient=Client)}):
            self.assertEqual(await ns['connect_and_run'](None, {'api_id': 1, 'api_hash': 'x'}), 'retry')
        self.assertEqual(closed, [True])

    async def test_exception_and_cancellation_also_disconnect(self):
        for error in (ValueError('broken'), asyncio.CancelledError()):
            closed = []
            class Client:
                def __init__(self, *args, **kwargs): pass
                async def disconnect(self): closed.append(True)
            async def attempt(*args): raise error
            ns = {'SESSION': 'jafj', '_connect_and_run_client': attempt}
            exec(compile(ast.Module(body=[wrapper], type_ignores=[]), str(SOURCE), 'exec'), ns)
            with patch.dict(sys.modules, {'telethon': types.SimpleNamespace(TelegramClient=Client)}):
                with self.assertRaises(type(error)):
                    await ns['connect_and_run'](None, {'api_id': 1, 'api_hash': 'x'})
            self.assertEqual(closed, [True])


if __name__ == '__main__':
    unittest.main()
