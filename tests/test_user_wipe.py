#!/usr/bin/env python3
"""تست پاک کردن اطلاعات کاربر + تنظیمات جفج و تنظیمات/دیتابیس تبادل.

پوشش تست:
  ۱. وجود دکمه‌های «🗑 پاک کردن اطلاعات کاربر» (`a:uwipe`) و «🔍 جستجوی کاربر» (`a:ufind`)
     در منوی مدیر و صفحه‌ی مشتری‌ها، و دکمه‌های «🧹 پاک کردن تنظیمات جفج/تبادل» (`auj:`)
     و «🗑 پاک کردن کل اطلاعات» (`aud:`) در کارت هر کاربر.
  ۲. نمایش خلاصه‌ی تنظیمات جفج و تبادل (کانال، روشن بودن تبادل، تعداد گروه‌ها، متن‌های
     سفارشی تبادل، رکوردهای دیتابیس تبادل و صف) در کارت کاربر و صفحه‌ی تأیید حذف.
  ۳. «🧹 پاک کردن تنظیمات جفج و تبادل» (`auj:` -> `aujx:` و دستور `/resetjafj`):
     پاک شدن کامل کانال‌ها، گروه‌های تبادل، متن‌های تبادل، فایل‌های بکاپ `.bak-*`،
     کل دیتابیس `jafj.db` (جدول `exchange` و `queue` و `-wal`/`-shm`) و بازگشت تنظیمات
     به حالت خام پیش‌فرض، بدون دست زدن به سشن، اشتراک، امتیاز، کیف پول و سفارش کاربر.
  ۴. «🗑 پاک کردن کل اطلاعات کاربر» (`aud:` -> `audx:`، مسیر `a:uwipe` با جستجوی
     `@username` / شماره / `uid`، و دستور `/del`):
     توقف پروسه‌ی در حال اجرا (حتی پروسه‌ی یتیم)، حذف کامل پوشه‌ی `clients/<uid>`
     (سشن، تنظیمات جفج، تنظیمات و دیتابیس تبادل، بکاپ‌ها)، حذف کامل از `manager.db`
     (`clients`, `tut_sent`, `log`) و `shop.db` (`points`, `points_log`, `wallet`,
     `wallet_log`, `orders`, `tickets`, `ticket_msgs`, `referrals`, `referral_point_rewards`)،
     دست‌نخورده ماندن اطلاعات سایر کاربران، و به‌روزشدن پشتیبان محلی تا بعد از بازیابی
     اطلاعاتِ پاک‌شده برنگردد.
  ۵. پاک کردن داده‌ی یتیم (پوشه‌ی `clients/<uid>` بدون رکورد در جدول `clients`) و
     اجازه‌ی به‌روزرسانی پشتیبان پس از حذف آخرین کاربر توسط مدیر.
"""
import os
import shutil
import subprocess
import sys
import tempfile
import textwrap

ROOT = os.path.join(tempfile.gettempdir(), "jafj_user_wipe_test")
APP = os.path.join(ROOT, "app")
DATA = os.path.join(ROOT, "data")
SRC_REPO = os.environ.get("REPO", os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

FAKE_TELETHON = textwrap.dedent('''
    class TelegramClient:
        def __init__(self, session, api_id, api_hash, **kw):
            pass
        async def connect(self):
            return
        async def is_user_authorized(self):
            return True
        async def start(self, bot_token=None):
            return self
        async def disconnect(self):
            return
        async def get_me(self):
            class U:
                username = "fakebot"
                id = 1
            return U()
        def on(self, *a, **k):
            def deco(fn):
                return fn
            return deco
        async def run_until_disconnected(self):
            return
        async def send_message(self, *a, **k):
            class R:
                id = 1
            return R()
        async def get_entity(self, x):
            class E:
                username = None
            return E()
        async def send_file(self, *a, **k):
            class M:
                id = 77
                media = True
                document = True
                caption = k.get("caption", "")
                text = ""
            return M()
        async def edit_message(self, *a, **k):
            class M:
                id = 77
                media = True
                document = True
                caption = a[2] if len(a) > 2 else k.get("caption", "")
                text = ""
            return M()
        async def forward_messages(self, *a, **k):
            return None
        async def get_messages(self, *a, **k):
            return []
        def iter_messages(self, *a, **k):
            async def _gen():
                return
                yield
            return _gen()
        async def download_media(self, *a, **k):
            return None

    class Button:
        @staticmethod
        def inline(*a, **k):
            return ("inline", a, k)
        @staticmethod
        def url(*a, **k):
            return ("url", a, k)
        @staticmethod
        def request_phone(*a, **k):
            return ("phone", a, k)
        @staticmethod
        def text(*a, **k):
            return ("text", a, k)
        @staticmethod
        def clear(*a, **k):
            return None

    class events:
        class NewMessage:
            def __init__(self, *a, **k):
                pass
        class CallbackQuery:
            def __init__(self, *a, **k):
                pass

    class _Err(Exception):
        pass
    FloodWaitError = _Err
    PhoneNumberBannedError = _Err
    PhoneNumberInvalidError = _Err
    SessionPasswordNeededError = _Err
    PhoneCodeInvalidError = _Err
    PhoneCodeExpiredError = _Err
    UserNotParticipantError = _Err
''')

FAKE_SESSIONS = textwrap.dedent('''
    class StringSession:
        def __init__(self, s=""):
            self._s = s or ""
            self.dc_id = 1
            self.server_address = "127.0.0.1"
            self.port = 443
            self.auth_key = b"fake-auth-key-1234567890"
        def save(self):
            return self._s

    class SQLiteSession:
        def __init__(self, *a, **k):
            pass
        def set_dc(self, *a, **k):
            pass
        def save(self):
            pass
        def close(self):
            pass
''')

FAKE_ERRORS = textwrap.dedent('''
    class FloodWaitError(Exception):
        def __init__(self, seconds=0, *a, **k):
            super().__init__(f"FloodWait {seconds}")
            self.seconds = int(seconds or 0)
    class PhoneNumberBannedError(Exception):
        pass
    class PhoneNumberInvalidError(Exception):
        pass
    class SessionPasswordNeededError(Exception):
        pass
    class PhoneCodeInvalidError(Exception):
        pass
    class PhoneCodeExpiredError(Exception):
        pass
    class UserNotParticipantError(Exception):
        pass
''')

INNER = textwrap.dedent('''
    import os, sys, json, time, sqlite3, zipfile, asyncio, subprocess
    sys.path.insert(0, os.getcwd())
    import manager_82 as M

    ADMIN = 100
    U_TARGET = 501
    U_KEEP = 502
    U_ORPHAN = 599

    results = []

    def check(cond, name):
        results.append((name, bool(cond)))
        if not cond:
            print("FAIL:", name, flush=True)

    def btn_items(kb):
        out = []
        for row in (kb or []):
            if isinstance(row, tuple):
                row = [row]
            for b in (row or []):
                try:
                    out.append((b[1][0], b[1][1]))
                except Exception:
                    pass
        return out

    def btn_datas(kb):
        out = []
        for _, d in btn_items(kb):
            out.append(d.decode("utf-8", "ignore") if isinstance(d, (bytes, bytearray)) else d)
        return out

    class FakeEv:
        def __init__(self, sender_id, data):
            self.sender_id = sender_id
            self.chat_id = sender_id
            self.data = data.encode() if isinstance(data, str) else data
            self.edits = []
            self.answers = []
        async def edit(self, text, parse_mode=None, buttons=None, **kw):
            self.edits.append((text, buttons))
        async def answer(self, text="", **kw):
            self.answers.append(text)

    def seed_jafj_folder(uid, channel="@target_chan", groups=None):
        folder = os.path.join(M.CLIENTS_DIR, str(uid))
        os.makedirs(folder, exist_ok=True)
        st = {
            "standard": {"channel": channel, "max_per_hour": 20},
            "vip": {"channel": "@vip_chan"},
            "paused": False,
            "exchange": {
                "enabled": True,
                "groups": groups if groups is not None else ["@ex_g1", "@ex_g2"],
                "msg_ok": "جوین شدم بیا",
                "msg_no": "هنوز عضو نشدی",
                "msg_come": "عضو کانالت شدم بیا",
                "scan_last": {"@ex_g1": 123},
            },
            "risk": {"on": True, "trigger": 70},
        }
        st_path = os.path.join(folder, "jafj_settings.json")
        with open(st_path, "w", encoding="utf-8") as f:
            json.dump(st, f, ensure_ascii=False)
        with open(st_path + ".bak-20261029-010101", "w", encoding="utf-8") as f:
            json.dump(st, f, ensure_ascii=False)
        with open(os.path.join(folder, "jafj_creds.json"), "w", encoding="utf-8") as f:
            json.dump({"phone": "+989121112233"}, f)
        # یک سشن sqlite واقعی؛ هدر جعلی و دیتابیس خراب نباید بک‌آپ سالم را جایگزین کند.
        sess = sqlite3.connect(os.path.join(folder, "jafj.session"))
        sess.execute("CREATE TABLE IF NOT EXISTS session_data (value TEXT)")
        sess.execute("INSERT INTO session_data VALUES ('synthetic')")
        sess.commit()
        sess.close()
        with open(os.path.join(folder, "jafj_status.json"), "w", encoding="utf-8") as f:
            json.dump({"ts": int(time.time()), "exchange": {"on": True, "joined": 5}}, f)
        with open(os.path.join(folder, "jafj.log"), "w", encoding="utf-8") as f:
            f.write("log line\\n")
        dbp = os.path.join(folder, "jafj.db")
        conn = sqlite3.connect(dbp)
        conn.execute("CREATE TABLE exchange (id INTEGER PRIMARY KEY, link TEXT, status TEXT)")
        conn.execute("INSERT INTO exchange (link, status) VALUES ('@peer1', 'joined'), ('@peer2', 'pending')")
        conn.execute("CREATE TABLE queue (id INTEGER PRIMARY KEY, text TEXT, status TEXT)")
        conn.execute("INSERT INTO queue (text, status) VALUES ('hello', 'pending')")
        conn.commit()
        conn.close()
        with open(dbp + ".bak-20261029-010101", "wb") as f:
            f.write(b"bak")
        return folder

    async def main():
        from telethon import TelegramClient
        m = M.Manager()
        m.cfg["admin_ids"] = [ADMIN]
        m.bot = TelegramClient("x", 1, "h")
        sent_msgs = []
        async def fake_say(chat, text, buttons=None, **kw):
            sent_msgs.append((chat, text, buttons))
            return True
        m.say = fake_say
        async def fake_edit(ev, text, buttons=None):
            ev.edits.append((text, buttons))
            return True
        m.edit = fake_edit

        # ۱. دکمه‌های منوی مدیر
        adm_datas = btn_datas(M.admin_menu())
        check("a:uwipe" in adm_datas, "admin_menu has a:uwipe button")
        check("a:ufind" in adm_datas, "admin_menu has a:ufind button")

        # ساخت دو کاربر کامل + داده‌ی فروشگاه + تنظیمات جفج و تبادل
        for u, uname, phone, ch in (
            (U_TARGET, "ali_target", "+989121112233", "@ali_channel"),
            (U_KEEP, "reza_keep", "+989129998877", "@reza_channel"),
        ):
            m.db.add(u, uname, f"Name {u}", 0)
            m.db.set(u, phone=phone, phone_verified=1, session="1BVtsFakeSessionString1234567890",
                     status="active", expires_at=int(time.time()) + 86400 * 30,
                     trial_used=1, trial_started_at=1000)
            m.db.tut_mark(u, 1)
            m.db.log(u, "login", "ok")
            m.shop.p_add(u, 50, "admin", "seed")
            m.shop.credit(u, 100000, "manual", "seed")
            m.shop.create_wallet_order(u, 50000)
            m.shop.new_ticket(u, "کمک", "سلام")
            seed_jafj_folder(u, channel=ch)
        m.shop.set_referrer(U_TARGET, U_KEEP)

        # ۲. صفحه‌ی لیست مشتری‌ها و کارت کاربر
        ev_ul = FakeEv(ADMIN, "a:ulist:0")
        await m.on_callback(ev_ul)
        ul_txt, ul_kb = ev_ul.edits[-1]
        check("a:uwipe" in btn_datas(ul_kb) and "a:ufind" in btn_datas(ul_kb),
              "admin_users_page exposes search & wipe buttons")

        ev_u = FakeEv(ADMIN, f"au:{U_TARGET}")
        await m.on_callback(ev_u)
        u_txt, u_kb = ev_u.edits[-1]
        check("@ali_channel" in u_txt and "2 گروه تبادل" in u_txt and "2 رکورد تبادل" in u_txt,
              "user card displays JAFJ channel + exchange groups + exchange DB rows")
        check(f"auj:{U_TARGET}" in btn_datas(u_kb) and f"aud:{U_TARGET}" in btn_datas(u_kb),
              "user card exposes both JAFJ-wipe and full-wipe buttons")

        # ۳. پاک کردن فقط تنظیمات جفج و تبادل (با حفظ سشن و اشتراک و امتیاز)
        ev_j = FakeEv(ADMIN, f"auj:{U_TARGET}")
        await m.on_callback(ev_j)
        j_txt, j_kb = ev_j.edits[-1]
        check(f"aujx:{U_TARGET}" in btn_datas(j_kb) and "@ali_channel" in j_txt,
              "JAFJ wipe confirmation screen shows details and confirm button")

        ev_jx = FakeEv(ADMIN, f"aujx:{U_TARGET}")
        await m.on_callback(ev_jx)
        t_folder = os.path.join(M.CLIENTS_DIR, str(U_TARGET))
        check(not os.path.exists(os.path.join(t_folder, "jafj.db")),
              "JAFJ wipe removes jafj.db (exchange & queue records)")
        check(not any(fn.startswith("jafj_settings.json.bak") or fn.startswith("jafj.db.bak")
                      for fn in os.listdir(t_folder)),
              "JAFJ wipe removes .bak-* backups of settings & exchange DB")
        with open(os.path.join(t_folder, "jafj_settings.json"), encoding="utf-8") as f:
            fresh_st = json.load(f)
        check(fresh_st["standard"]["channel"] == "" and "exchange" not in fresh_st,
              "JAFJ wipe resets jafj_settings.json to clean defaults")
        check(os.path.exists(os.path.join(t_folder, "jafj.session")),
              "JAFJ wipe preserves user session file")
        c_after_j = m.db.get(U_TARGET)
        check(c_after_j["status"] == "active" and m.shop.p_balance(U_TARGET) == 50
              and m.shop.balance(U_TARGET) == 100000,
              "JAFJ wipe preserves subscription, points, and wallet")

        # دوباره تنظیمات جفج و تبادل + یک پروسه‌ی سلف زنده بسازیم و بکاپ محلی بگیریم
        seed_jafj_folder(U_TARGET, channel="@ali_rebuilt", groups=["@g_new"])
        proc = subprocess.Popen(
            [sys.executable, "-c", "import time; time.sleep(60)"],
            cwd=t_folder, start_new_session=True)
        m.sup.procs[U_TARGET] = proc

        latest_zip = os.path.join(M.BASE_DIR, "jafj_backup_latest.zip")
        m._write_backup_zip(latest_zip)
        with zipfile.ZipFile(latest_zip, "r") as zf:
            check(any(n.startswith(f"clients/{U_TARGET}/") for n in zf.namelist()),
                  "pre-wipe backup zip contains target user's client files")

        # ۴. جستجو از مسیر a:uwipe با شماره موبایل و اجرای حذف کامل (audx:)
        ev_w = FakeEv(ADMIN, "a:uwipe")
        await m.on_callback(ev_w)
        check(m.fsm.get(ADMIN, {}).get("step") == "uwipe_pick",
              "a:uwipe opens uwipe_pick FSM step")

        matches = m._resolve_admin_users("09121112233")
        check(len(matches) == 1 and matches[0]["uid"] == U_TARGET,
              "search resolves user by 09... phone format")
        matches_u = m._resolve_admin_users("@ali_target")
        check(len(matches_u) == 1 and matches_u[0]["uid"] == U_TARGET,
              "search resolves user by @username")

        ev_dc = FakeEv(ADMIN, f"aud:{U_TARGET}")
        await m.on_callback(ev_dc)
        dc_txt, dc_kb = ev_dc.edits[-1]
        check(f"audx:{U_TARGET}" in btn_datas(dc_kb) and "تنظیمات تبادل" in dc_txt,
              "full wipe confirmation screen mentions exchange settings & has confirm button")

        ev_dx = FakeEv(ADMIN, f"audx:{U_TARGET}")
        await m.on_callback(ev_dx)

        check(proc.poll() is not None, "full wipe terminates running selfbot process")
        check(not os.path.exists(t_folder),
              "full wipe removes entire clients/<uid> directory (session + JAFJ + exchange)")
        check(m.db.get(U_TARGET) is None, "full wipe removes user from clients table")
        check(not m.db.tut_done(U_TARGET, 1), "full wipe removes user from tut_sent")
        check(m.db.x("SELECT 1 FROM log WHERE uid=?", (U_TARGET,), "one") is None,
              "full wipe removes user's rows from log table")
        check(m.shop.x("SELECT 1 FROM points WHERE uid=?", (U_TARGET,), "one") is None,
              "full wipe leaves zero rows in points table")
        check(m.shop.x("SELECT 1 FROM points_log WHERE uid=?", (U_TARGET,), "one") is None,
              "full wipe removes points_log")
        check(m.shop.x("SELECT 1 FROM wallet WHERE uid=?", (U_TARGET,), "one") is None,
              "full wipe removes wallet")
        check(m.shop.x("SELECT 1 FROM orders WHERE uid=?", (U_TARGET,), "one") is None,
              "full wipe removes orders")
        check(m.shop.x("SELECT 1 FROM tickets WHERE uid=?", (U_TARGET,), "one") is None,
              "full wipe removes tickets & ticket_msgs")
        check(m.shop.x("SELECT 1 FROM referrals WHERE uid=?", (U_TARGET,), "one") is None,
              "full wipe removes referrals")

        # بکاپ محلی هم دیگر نباید فایل‌های کاربر پاک‌شده را داشته باشد
        with zipfile.ZipFile(latest_zip, "r") as zf:
            check(not any(n.startswith(f"clients/{U_TARGET}/") for n in zf.namelist()),
                  "local backup zip refreshed without wiped user's JAFJ/exchange files")

        # کاربر دوم (U_KEEP) کاملاً سالم مانده باشد
        check(m.db.get(U_KEEP) is not None and m.shop.p_balance(U_KEEP) == 50
              and os.path.isfile(os.path.join(M.CLIENTS_DIR, str(U_KEEP), "jafj_settings.json")),
              "other users and their JAFJ/exchange settings remain untouched")

        # ۵. پاک کردن داده‌ی یتیم (فقط پوشه‌ی تنظیمات جفج/تبادل بدون رکورد clients) با دستور /del
        orphan_dir = seed_jafj_folder(U_ORPHAN, channel="@orphan_ch")
        await m.admin_cmd(ADMIN, ADMIN, "del", str(U_ORPHAN))
        check(not os.path.exists(orphan_dir),
              "/del command also wipes orphan clients/<uid> JAFJ/exchange directory")

        # ۶. حذف آخرین کاربر و بررسی اجازه‌ی به‌روزرسانی بکاپ خالی (بدون قفل شدن روی گارد بکاپ)
        await m.admin_cmd(ADMIN, ADMIN, "del", "@reza_keep")
        check(m.db.get(U_KEEP) is None and not os.path.exists(os.path.join(M.CLIENTS_DIR, str(U_KEEP))),
              "/del @username wipes last remaining user completely")
        guard = await m._empty_db_backup_guard(ADMIN)
        check(guard is None,
              "intentional deletion of last user allows updating backup once without empty-DB guard block")

        failed = [n for n, ok in results if not ok]
        print(f"--- user wipe & JAFJ/exchange settings wipe ---")
        print(f"{len(results)} checks, {len(failed)} failed")
        if failed:
            for f in failed:
                print("  FAILED:", f)
            sys.exit(1)
        print("ALL: PASS")

    asyncio.run(main())
''')


def main():
    shutil.rmtree(ROOT, ignore_errors=True)
    os.makedirs(APP, exist_ok=True)
    os.makedirs(DATA, exist_ok=True)
    shutil.copy2(os.path.join(SRC_REPO, "manager_82.py"), os.path.join(APP, "manager_82.py"))
    shutil.copy2(os.path.join(SRC_REPO, "95.py"), os.path.join(APP, "95.py"))
    pkg = os.path.join(APP, "telethon")
    os.makedirs(pkg, exist_ok=True)
    with open(os.path.join(pkg, "__init__.py"), "w", encoding="utf-8") as f:
        f.write(FAKE_TELETHON)
    with open(os.path.join(pkg, "sessions.py"), "w", encoding="utf-8") as f:
        f.write(FAKE_SESSIONS)
    with open(os.path.join(pkg, "errors.py"), "w", encoding="utf-8") as f:
        f.write(FAKE_ERRORS)
    runner = os.path.join(APP, "_run.py")
    with open(runner, "w", encoding="utf-8") as f:
        f.write(INNER)
    env = dict(os.environ, DATA_DIR=DATA, JAFJ_APP_DIR=APP)
    r = subprocess.run([sys.executable, runner], cwd=APP, env=env, text=True, capture_output=True)
    sys.stdout.write(r.stdout)
    if r.stderr:
        sys.stderr.write(r.stderr)
    shutil.rmtree(ROOT, ignore_errors=True)
    sys.exit(r.returncode)


if __name__ == "__main__":
    main()
