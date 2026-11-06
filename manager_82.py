#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
═══════════════════════════════════════════════════════════
  جفج — ربات فروش و مدیریت      (نسخه تک‌فایلی)
═══════════════════════════════════════════════════════════

  ── نصب و اجرا ───────────────────────────────────────
      pip install telethon
      python manager_82.py

      بار اول manager_config.json ساخته می‌شود.
      داخلش bot_token و api_id و api_hash را بگذار،
      دوباره اجرا کن، بعد در تلگرام /start بزن.
      اولین نفری که /start بزند، مدیر می‌شود.

  ── ترموکس ───────────────────────────────────────────
      pkg update && pkg install python -y
      pip install telethon
      termux-wake-lock
      ulimit -n 4096
      python manager_82.py

  ── فایل‌های لازم ────────────────────────────────────
      manager_82.py            همین فایل
      95.py            سلف مشتری‌ها  (حتماً کنارش باشد)

  ── فایل‌هایی که خودش می‌سازد ────────────────────────
      manager_config.json   تنظیمات
      manager.db            مشتری‌ها
      shop.db               پلن، سفارش، امتیاز
      clients/<uid>/        پوشه هر مشتری
═══════════════════════════════════════════════════════════
"""

import os
import re
import sys
import json
import time
import random
import string
import signal
import sqlite3
import asyncio
import shutil
import subprocess
import tempfile
import threading
import traceback
import zipfile
import functools

# --- فیکس آف شدن بعد 30 دقیقه بدون فعالیت (Railway) - وب سرور سالم ---
def _health_port():
    """پورتی که وب‌سرور سلامت باید رویش گوش بدهد.

    چرا این‌قدر وسواسی: هر میزبانِ کانتینری (Hostless/Render/Railway/blitz)
    می‌گوید «روی $PORT گوش بده وگرنه سرویس را سالم نمی‌شناسم». اگر PORT
    ناخوانا باشد و int() خطا بدهد، وب‌سرور بالا نمی‌آید، هیچ پورتی باز
    نمی‌شود و میزبان پروسه را می‌کُشد — که دقیقاً شبیه «پروسه خیلی زود
    تمام شد» دیده می‌شود. پس هر شکلِ رایج را می‌خوانیم و آخرین راه 8080 است.
    """
    raw = (os.environ.get("PORT") or "").strip()
    for cand in (raw, raw.rsplit(":", 1)[-1] if ":" in raw else ""):
        try:
            p = int(str(cand).strip().strip("/").split("/")[0] or "8080")
            if 1 <= p <= 65535:
                return p
        except Exception:
            continue
    try:
        m = re.search(r"(\d{2,5})", raw)
        if m:
            p = int(m.group(1))
            if 1 <= p <= 65535:
                return p
    except Exception:
        pass
    if raw:
        print(f"  ⚠️ PORT={raw!r} قابلِ خواندن نبود — 8080 استفاده می‌شود", flush=True)
    return 8080


def _start_health_server():
    try:
        import http.server, socketserver
        port = _health_port()
        class Handler(http.server.BaseHTTPRequestHandler):
            def setup(self):
                super().setup()
                self.connection.settimeout(10)

            def do_HEAD(self):
                self._health(False)

            def do_GET(self):
                self._health(True)

            def _payload(self, path):
                """/version کدام بیلد/کامیت روی هاست اجرا می‌شود را می‌گوید.

                چرا: بعد از مرج، تنها سؤالِ واقعی این است «دیپلوی شد یا نه؟».
                بدونِ این، باید لاگ‌ها را گشت. مسیرهای / و /healthz عمداً
                همان «JAFJ OK» می‌مانند (هلث‌چکِ Render و تست‌ها به همان
                بایت‌ها وابسته‌اند).
                """
                if path in ("/version", "/build"):
                    g = globals()
                    ver = g.get("BUILD_VERSION") or "?"
                    commit = g.get("GIT_COMMIT") or "?"
                    try:
                        boot = time.strftime("%Y-%m-%d %H:%M:%S %Z",
                                             g.get("_BOOT_TIME_STRUCT")
                                             or time.localtime())
                    except Exception:
                        boot = "?"
                    txt = ("build: %s\ncommit: %s\ncode: %s\n"
                           "manager: %s\nstarted: %s\n"
                           % (ver, commit, g.get("CODE_ID") or "?",
                              g.get("MANAGER_PATH") or "?", boot))
                    # «زنده‌بودنِ واقعی»: پروسه بودن با جواب‌دادنِ ربات یکی نیست.
                    try:
                        _s = live_snapshot()
                        txt += ("live: ready=%d ping_age=%s loop_age=%s fails=%d"
                                % (1 if _s.get("ready") else 0,
                                   _s.get("ping_age"), _s.get("loop_age"),
                                   int(_s.get("fails") or 0)))
                        if _s.get("last_error"):
                            txt += " err=" + str(_s["last_error"])[:120]
                        txt += "\n"
                    except Exception:
                        pass
                    return txt.encode("utf-8")
                return b"JAFJ OK\n"

            def _health(self, body):
                try:
                    path = (self.path or "/").split("?", 1)[0]
                except Exception:
                    path = "/"
                code = 200
                if path in ("/livez", "/readyz"):
                    # برای مانیتوری که باید ری‌استارت بدهد: اگر حلقه گیر
                    # کرده یا پینگ‌ها پشتِ‌سرهم شکست خورده‌اند، ۵۰۳.
                    # مسیرهای / و /healthz عمداً همان ۲۰۰ می‌مانند.
                    try:
                        code, state = livez_verdict()
                    except Exception:
                        code, state = 200, "ok"
                    payload = (state + "\n").encode("utf-8")
                else:
                    payload = self._payload(path)
                self.send_response(code)
                self.send_header("Content-Type", "text/plain; charset=utf-8")
                self.send_header("Content-Length", str(len(payload)))
                self.send_header("Cache-Control", "no-store")
                self.end_headers()
                if body:
                    self.wfile.write(payload)

            def log_message(self, *a): pass

        class ReusableTCPServer(socketserver.ThreadingTCPServer):
            allow_reuse_address = True
            daemon_threads = True
            request_queue_size = 64
        # حلقه: اگر bind شکست بخورد یا سرویس بعداً بمیرد، دوباره بالا بیاید.
        # قبلاً یک شکستِ موقت (پورت هنوز آزاد نشده) برای همیشه وب‌سرور را
        # خاموش می‌کرد؛ آن‌وقت میزبان «پورت باز نیست» می‌دید و کانتینر را
        # می‌کشت — همان «پروسه خیلی زود تمام شد».
        _tries = 0
        while True:
            _tries += 1
            try:
                with ReusableTCPServer(("0.0.0.0", port), Handler) as httpd:
                    print(f"  🌐 LISTENING on 0.0.0.0:{port} — health: / و /healthz "
                          f"(نسخه: /version)", flush=True)
                    httpd.serve_forever()
                return          # shutdown خواسته شده
            except Exception as e:
                if _tries <= 3 or _tries % 30 == 0:
                    print(f"  ⚠️ health server failed (try {_tries}, port {port}): "
                          f"{type(e).__name__}: {e}", flush=True)
                time.sleep(2)
    except Exception as e:
        print(f"health server failed: {e}", flush=True)

threading.Thread(target=_start_health_server, daemon=True).start()
# --- پایان فیکس ---

from datetime import datetime, timedelta, timezone

# ساعتِ محلیِ ربات. سرورِ هاست (Render/Railway) معمولاً روی UTC است؛ با
# datetime.now() ساعتِ ایران ۳:۳۰ عقب می‌ماند و «ظهر» روی «صبح» می‌ماند.
# پیش‌فرض Asia/Tehran؛ با متغیر محیطی BOT_TZ قابل تغییر است (مثلاً Europe/Istanbul).
BOT_TZ_NAME = (os.environ.get("BOT_TZ") or "Asia/Tehran").strip() or "Asia/Tehran"


def _bot_tz():
    try:
        from zoneinfo import ZoneInfo
        return ZoneInfo(BOT_TZ_NAME)
    except Exception:
        # tzdata نصب نیست: ایران بدون ساعت تابستانی = UTC+03:30
        if BOT_TZ_NAME == "Asia/Tehran":
            return timezone(timedelta(hours=3, minutes=30))
        return timezone.utc


# ── فیلتر خروجی: پیامِ ناخواسته‌ی «برای استفاده از ربات باید کانال ... جوین شوی» ──
# این متن در کدِ این پروژه وجود ندارد و از منبعی بیرونی (سرویس میزبان، کانفیگ
# قدیمی یا تزریق شخص ثالث) به کاربران ارسال می‌شد. هر پیام خروجی‌ای که با این
# الگوها بخواند، قبل از رسیدن به تلگرام حذف می‌شود.
BLOCKED_OUTGOING_PATTERNS = (
    re.compile(r"a_toolsx2", re.IGNORECASE),
    re.compile(r"t\.me/a_toolsx2", re.IGNORECASE),
    re.compile(r"to\s+use\s+this\s+bot\s*,?\s*you\s+must\s+join", re.IGNORECASE),
)


def is_blocked_outgoing(text):
    """True اگر متنِ پیام جزو پیام‌های مسدودشده باشد."""
    if not isinstance(text, str) or not text:
        return False
    return any(p.search(text) for p in BLOCKED_OUTGOING_PATTERNS)


def install_outgoing_filter(client):
    """روی نمونه‌ی TelegramClient، send/edit را طوری می‌پوشاند که پیام مسدودشده
    هرگز ارسال نشود. برای پیام‌های عادی رفتار تغییری نمی‌کند."""
    if client is None or getattr(client, "_jafj_out_filter", False):
        return client
    from types import SimpleNamespace
    orig_send = client.send_message
    orig_edit = client.edit_message

    async def send_message(entity, message=None, *args, **kwargs):
        if is_blocked_outgoing(message):
            print("🛡 پیام مسدودشده (جوین اجباریِ بیرونی) ارسال نشد", flush=True)
            return SimpleNamespace(id=0)
        return await orig_send(entity, message, *args, **kwargs)

    async def edit_message(entity, message=None, *args, **kwargs):
        body = message if isinstance(message, str) else kwargs.get("text")
        if is_blocked_outgoing(body):
            print("🛡 ویرایش پیام مسدودشده ارسال نشد", flush=True)
            return SimpleNamespace(id=0)
        return await orig_edit(entity, message, *args, **kwargs)

    client.send_message = send_message
    client.edit_message = edit_message
    client._jafj_out_filter = True
    return client


def local_now():
    """زمان فعلی به ساعت محلیِ ربات (نه ساعت سرور)."""
    return datetime.now(_bot_tz())


def local_dt(ts):
    """timestamp → datetime به ساعت محلیِ ربات."""
    return datetime.fromtimestamp(ts, _bot_tz())


def _fa_digits(n):
    return str(n)


def now():
    return int(time.time())


# ═══════════════════════════════════════════════════════════
#   بخش ۱ — موتور فروشگاه
# ═══════════════════════════════════════════════════════════
BASE_DIR = os.environ.get("DATA_DIR", ".")
os.makedirs(BASE_DIR, exist_ok=True)
SHOP_DB = os.path.join(BASE_DIR, "shop.db")

SHOP_SCHEMA = """
CREATE TABLE IF NOT EXISTS plans (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    name TEXT NOT NULL,
    days INTEGER NOT NULL,
    price INTEGER NOT NULL,
    max_accounts INTEGER NOT NULL DEFAULT 1,
    features TEXT,
    active INTEGER NOT NULL DEFAULT 1,
    sort INTEGER NOT NULL DEFAULT 0
);

CREATE TABLE IF NOT EXISTS packs (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    name TEXT NOT NULL,
    points INTEGER NOT NULL,
    bonus INTEGER NOT NULL DEFAULT 0,
    price INTEGER NOT NULL,
    active INTEGER NOT NULL DEFAULT 1,
    sort INTEGER NOT NULL DEFAULT 0
);

CREATE TABLE IF NOT EXISTS orders (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    uid INTEGER NOT NULL,
    plan_id INTEGER,
    plan_name TEXT,
    days INTEGER,
    amount INTEGER NOT NULL,
    discount_code TEXT,
    discount_off INTEGER NOT NULL DEFAULT 0,
    wallet_used INTEGER NOT NULL DEFAULT 0,
    final INTEGER NOT NULL,
    status TEXT NOT NULL DEFAULT 'draft',
    receipt_file TEXT,
    receipt_text TEXT,
    created_at INTEGER NOT NULL,
    paid_at INTEGER,
    decided_at INTEGER,
    admin_id INTEGER,
    note TEXT,
    kind TEXT NOT NULL DEFAULT 'sub',
    points INTEGER NOT NULL DEFAULT 0
);
CREATE INDEX IF NOT EXISTS idx_ord ON orders(status, uid);

CREATE TABLE IF NOT EXISTS discounts (
    code TEXT PRIMARY KEY,
    percent INTEGER NOT NULL DEFAULT 0,
    flat INTEGER NOT NULL DEFAULT 0,
    max_uses INTEGER NOT NULL DEFAULT 0,
    used INTEGER NOT NULL DEFAULT 0,
    expires_at INTEGER NOT NULL DEFAULT 0,
    active INTEGER NOT NULL DEFAULT 1,
    created_at INTEGER NOT NULL
);

CREATE TABLE IF NOT EXISTS wallet (
    uid INTEGER PRIMARY KEY,
    balance INTEGER NOT NULL DEFAULT 0,
    total_in INTEGER NOT NULL DEFAULT 0
);

CREATE TABLE IF NOT EXISTS wallet_log (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    uid INTEGER NOT NULL, amount INTEGER NOT NULL,
    kind TEXT, detail TEXT, ts INTEGER NOT NULL
);

CREATE TABLE IF NOT EXISTS referrals (
    uid INTEGER PRIMARY KEY,
    referrer INTEGER NOT NULL,
    joined_at INTEGER NOT NULL,
    rewarded INTEGER NOT NULL DEFAULT 0
);
CREATE INDEX IF NOT EXISTS idx_ref ON referrals(referrer);

CREATE TABLE IF NOT EXISTS referral_rewards (
    order_id INTEGER PRIMARY KEY,
    referrer INTEGER NOT NULL,
    amount INTEGER NOT NULL,
    created_at INTEGER NOT NULL
);

CREATE TABLE IF NOT EXISTS referral_point_rewards (
    invitee_uid INTEGER PRIMARY KEY,
    referrer INTEGER NOT NULL,
    points INTEGER NOT NULL,
    created_at INTEGER NOT NULL
);

CREATE TABLE IF NOT EXISTS points (
    uid INTEGER PRIMARY KEY,
    balance INTEGER NOT NULL DEFAULT 0,
    earned INTEGER NOT NULL DEFAULT 0,
    spent INTEGER NOT NULL DEFAULT 0,
    last_charge INTEGER NOT NULL DEFAULT 0
);

CREATE TABLE IF NOT EXISTS points_log (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    uid INTEGER NOT NULL, amount INTEGER NOT NULL,
    kind TEXT, detail TEXT, ts INTEGER NOT NULL
);

CREATE TABLE IF NOT EXISTS tickets (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    uid INTEGER NOT NULL,
    subject TEXT,
    status TEXT NOT NULL DEFAULT 'open',
    created_at INTEGER NOT NULL,
    updated_at INTEGER NOT NULL
);

CREATE TABLE IF NOT EXISTS ticket_msgs (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    tid INTEGER NOT NULL, from_admin INTEGER NOT NULL DEFAULT 0,
    text TEXT, ts INTEGER NOT NULL
);
"""

# قیمت‌گذاری بر پایه: اشتراک ماهانه 110٬000 تومان = 720 ساعت
# ➜ هر امتیاز 153 تومان   ·   هر 2 امتیاز (2 ساعت) 306 تومان
# خرد گران‌تر، عمده ارزان‌تر تا اشتراک ماهانه همیشه به‌صرفه بماند.
DEFAULT_PACKS = [
    # (نام, امتیاز, هدیه, قیمت)
    ("خرد",    20,    0,   5_000),   # 20 ساعت  · 250 تومان هر امتیاز
    ("کوچک",   60,    5,  13_000),   # 65 ساعت  · 200
    ("متوسط",  180,  20,  36_000),   # 200 ساعت · 180
    ("بزرگ",   450,  60,  79_000),   # 510 ساعت · 155
    ("ویژه",   900, 180, 138_000),   # 1080 ساعت · 128
]

DEFAULT_PLANS = [
    ("برنزی",  30,  110_000, 1, "یک اکانت • بدون محدودیت ساعتی • پشتیبانی"),
    ("نقره‌ای", 90,  290_000, 1, "یک اکانت • تبادل پیش‌قدم • پشتیبانی ویژه"),
    ("طلایی",  180, 540_000, 1, "یک اکانت • همه امکانات • پشتیبانی آنی"),
]



def _fa_digits(n):
    return str(n)


def money(n):
    return _fa_digits(f"{int(n):,}") + " تومان"


def gen_code(n=8):
    return "".join(random.choices(string.ascii_uppercase + string.digits, k=n))


class Shop:
    def __init__(self, path=SHOP_DB, seed=True):
        self.lock = threading.RLock()
        self.c = sqlite3.connect(path, check_same_thread=False)
        self.c.row_factory = sqlite3.Row
        self.c.execute("PRAGMA journal_mode=WAL")
        with self.lock:
            self.c.executescript(SHOP_SCHEMA)
            self.c.commit()
        if seed and not self.plans(all_=True):
            for i, (n, d, p, m, f) in enumerate(DEFAULT_PLANS):
                self.add_plan(n, d, p, m, f, sort=i)
        # همیشه پلن‌های پیش‌فرض را با مقادیرِ جدید همگام کن (به‌ویژه سقف اکانت).
        # اگر دیتابیسِ قدیمی پلن را با «۵ اکانت» ساخته باشد، اینجا به ۱ برمی‌گردد.
        if seed:
            for (n, d, p, m, f) in DEFAULT_PLANS:
                row = self.x("SELECT id,max_accounts,days,price FROM plans "
                             "WHERE name=? AND active=1", (n,), "one")
                if row:
                    upd = {}
                    if int(row["max_accounts"]) != int(m):
                        upd["max_accounts"] = int(m)
                    if upd:
                        self.set_plan(row["id"], **upd)
        if seed and not self.packs(all_=True):
            for i, (n, pt, bn, pr) in enumerate(DEFAULT_PACKS):
                self.add_pack(n, pt, pr, bn, sort=i)

    def x(self, sql, a=(), f=None):
        with self.lock:
            cur = self.c.execute(sql, a)
            if f == "one":
                r = cur.fetchone()
                return dict(r) if r else None
            if f == "all":
                return [dict(r) for r in cur.fetchall()]
            self.c.commit()
            return cur.lastrowid

    def close(self):
        """بستن اتصال (برای بازیابی پشتیبان)."""
        try:
            with self.lock:
                try:
                    self.c.commit()
                except Exception:
                    pass
                try:
                    self.c.close()
                except Exception:
                    pass
        except Exception:
            pass

    # ═══════════════ پلن‌ها ═══════════════
    def add_plan(self, name, days, price, max_accounts=1, features="", sort=0):
        days, price, max_accounts = int(days), int(price), int(max_accounts)
        if not str(name).strip() or days <= 0 or price <= 0 or max_accounts <= 0:
            raise ValueError("مشخصات پلن نامعتبر است")
        return self.x("INSERT INTO plans (name,days,price,max_accounts,features,sort)"
                      " VALUES (?,?,?,?,?,?)",
                      (str(name).strip(), days, price, max_accounts, features, sort))

    def plans(self, all_=False):
        if all_:
            return self.x("SELECT * FROM plans ORDER BY sort,id", (), "all")
        return self.x("SELECT * FROM plans WHERE active=1 ORDER BY sort,id", (), "all")

    def plan(self, pid):
        return self.x("SELECT * FROM plans WHERE id=?", (pid,), "one")

    def set_plan(self, pid, **kw):
        if not kw:
            return
        if "name" in kw and not str(kw["name"]).strip():
            raise ValueError("نام پلن خالی است")
        if "days" in kw and int(kw["days"]) <= 0:
            raise ValueError("مدت پلن باید مثبت باشد")
        if "price" in kw and int(kw["price"]) <= 0:
            raise ValueError("قیمت پلن باید مثبت باشد")
        if "max_accounts" in kw and int(kw["max_accounts"]) <= 0:
            raise ValueError("تعداد اکانت باید مثبت باشد")
        cols = ",".join(f"{k}=?" for k in kw)
        self.x(f"UPDATE plans SET {cols} WHERE id=?", tuple(kw.values()) + (pid,))

    def del_plan(self, pid):
        self.x("UPDATE plans SET active=0 WHERE id=?", (pid,))

    # ═══════════════ بسته امتیاز ═══════════════
    def add_pack(self, name, points, price, bonus=0, sort=0):
        points, price, bonus = int(points), int(price), int(bonus)
        if not str(name).strip() or points <= 0 or price <= 0 or bonus < 0:
            raise ValueError("مشخصات بسته امتیاز نامعتبر است")
        return self.x("INSERT INTO packs (name,points,price,bonus,sort)"
                      " VALUES (?,?,?,?,?)",
                      (str(name).strip(), points, price, bonus, sort))

    def packs(self, all_=False):
        if all_:
            return self.x("SELECT * FROM packs ORDER BY sort,id", (), "all")
        return self.x("SELECT * FROM packs WHERE active=1 ORDER BY sort,id", (), "all")

    def pack(self, pid):
        return self.x("SELECT * FROM packs WHERE id=?", (pid,), "one")

    def set_pack(self, pid, **kw):
        if not kw:
            return
        if "name" in kw and not str(kw["name"]).strip():
            raise ValueError("نام بسته خالی است")
        if "points" in kw and int(kw["points"]) <= 0:
            raise ValueError("تعداد امتیاز باید مثبت باشد")
        if "price" in kw and int(kw["price"]) <= 0:
            raise ValueError("قیمت بسته باید مثبت باشد")
        if "bonus" in kw and int(kw["bonus"]) < 0:
            raise ValueError("هدیه نمی‌تواند منفی باشد")
        cols = ",".join(f"{k}=?" for k in kw)
        self.x(f"UPDATE packs SET {cols} WHERE id=?", tuple(kw.values()) + (pid,))

    def del_pack(self, pid):
        self.x("UPDATE packs SET active=0 WHERE id=?", (pid,))

    def create_pack_order(self, uid, pack_id, code="", use_wallet=False):
        """سفارش خرید امتیاز. (سفارش, خطا)"""
        k = self.pack(pack_id)
        if not k or not k["active"]:
            return None, "این بسته موجود نیست"
        amount = k["price"]
        off = 0
        if code:
            off, err = self.check_discount(code, amount)
            if err:
                return None, err
        after = amount - off
        w = 0
        if use_wallet:
            w = min(self.balance(uid), after)
            after -= w
        total = k["points"] + k["bonus"]
        oid = self.x(
            "INSERT INTO orders (uid,plan_id,plan_name,days,amount,discount_code,"
            "discount_off,wallet_used,final,status,created_at,kind,points)"
            " VALUES (?,?,?,0,?,?,?,?,?,'pending',?,'points',?)",
            (uid, pack_id, k["name"], amount, code.upper() if code else None,
             off, w, after, now(), total))
        return self.order(oid), ""

    def create_custom_points_order(self, uid, points, price):
        """خرید امتیاز به تعداد دلخواه."""
        points = int(points)
        price = int(price)
        if points <= 0 or price <= 0:
            return None, "مقدار نامعتبر"
        oid = self.x(
            "INSERT INTO orders (uid,plan_id,plan_name,days,amount,"
            "discount_off,wallet_used,final,status,created_at,kind,points)"
            " VALUES (?,0,?,0,?,0,0,?,'pending',?,'points',?)",
            (uid, f"{points} امتیاز", price, price, now(), points))
        return self.order(oid), ""

    def create_wallet_order(self, uid, amount):
        """شارژ کیف پول."""
        amount = int(amount)
        if amount <= 0:
            return None, "مبلغ نامعتبر"
        oid = self.x(
            "INSERT INTO orders (uid,plan_id,plan_name,days,amount,"
            "discount_off,wallet_used,final,status,created_at,kind,points)"
            " VALUES (?,0,'شارژ کیف پول',0,?,0,0,?,'pending',?,'wallet',0)",
            (uid, amount, amount, now()))
        return self.order(oid), ""

    # ═══════════════ کد تخفیف ═══════════════
    def add_discount(self, code, percent=0, flat=0, max_uses=0, days_valid=0):
        code = code.upper().strip()
        percent, flat = int(percent), int(flat)
        max_uses, days_valid = int(max_uses), int(days_valid)
        if not code or not (0 <= percent <= 100) or flat < 0 or max_uses < 0 or days_valid < 0:
            raise ValueError("مقادیر کد تخفیف نامعتبر است")
        exp = now() + days_valid * 86400 if days_valid else 0
        self.x("INSERT OR REPLACE INTO discounts"
               " (code,percent,flat,max_uses,used,expires_at,active,created_at)"
               " VALUES (?,?,?,?,COALESCE((SELECT used FROM discounts WHERE code=?),0),"
               "?,1,?)", (code, int(percent), int(flat), int(max_uses), code, exp, now()))
        return code

    def discount(self, code):
        return self.x("SELECT * FROM discounts WHERE code=?",
                      (code.upper().strip(),), "one")

    def check_discount(self, code, amount):
        """(مبلغ_تخفیف, پیام_خطا)"""
        d = self.discount(code)
        if not d:
            return 0, "کد تخفیف پیدا نشد"
        if not d["active"]:
            return 0, "این کد غیرفعال است"
        if d["expires_at"] and d["expires_at"] < now():
            return 0, "این کد منقضی شده"
        if d["max_uses"] and d["used"] >= d["max_uses"]:
            return 0, "ظرفیت این کد پر شده"
        off = d["flat"] + (amount * d["percent"] // 100)
        return min(off, amount), ""

    def use_discount(self, code):
        self.x("UPDATE discounts SET used=used+1 WHERE code=?",
               (code.upper().strip(),))

    def discounts(self):
        return self.x("SELECT * FROM discounts ORDER BY created_at DESC", (), "all")

    # ═══════════════ کیف پول ═══════════════
    def balance(self, uid):
        r = self.x("SELECT balance FROM wallet WHERE uid=?", (uid,), "one")
        return r["balance"] if r else 0

    def credit(self, uid, amount, kind="manual", detail=""):
        amount = int(amount)
        self.x("INSERT INTO wallet (uid,balance,total_in) VALUES (?,?,?)"
               " ON CONFLICT(uid) DO UPDATE SET balance=balance+excluded.balance,"
               " total_in=total_in+MAX(excluded.balance,0)",
               (uid, amount, max(amount, 0)))
        self.x("INSERT INTO wallet_log (uid,amount,kind,detail,ts) VALUES (?,?,?,?,?)",
               (uid, amount, kind, detail, now()))
        return self.balance(uid)

    def wallet_log(self, uid, n=10):
        return self.x("SELECT * FROM wallet_log WHERE uid=? ORDER BY id DESC LIMIT ?",
                      (uid, n), "all")

    # ═══════════════ سفارش ═══════════════
    def create_order(self, uid, plan_id, code="", use_wallet=False):
        """(سفارش, خطا)"""
        p = self.plan(plan_id)
        if not p or not p["active"]:
            return None, "این پلن موجود نیست"
        amount = p["price"]
        off = 0
        if code:
            off, err = self.check_discount(code, amount)
            if err:
                return None, err
        after = amount - off
        w = 0
        if use_wallet:
            w = min(self.balance(uid), after)
            after -= w
        oid = self.x(
            "INSERT INTO orders (uid,plan_id,plan_name,days,amount,discount_code,"
            "discount_off,wallet_used,final,status,created_at)"
            " VALUES (?,?,?,?,?,?,?,?,?,'pending',?)",
            (uid, plan_id, p["name"], p["days"], amount, code.upper() if code else None,
             off, w, after, now()))
        return self.order(oid), ""

    def order(self, oid):
        return self.x("SELECT * FROM orders WHERE id=?", (oid,), "one")

    def attach_receipt(self, oid, file_id=None, text=None):
        self.x("UPDATE orders SET receipt_file=?,receipt_text=?,status='paid',"
               "paid_at=? WHERE id=? AND status='pending'",
               (file_id, text, now(), oid))
        return self.order(oid)

    def pending_orders(self):
        return self.x("SELECT * FROM orders WHERE status='paid' ORDER BY id", (), "all")

    def user_orders(self, uid, n=10):
        return self.x("SELECT * FROM orders WHERE uid=? ORDER BY id DESC LIMIT ?",
                      (uid, n), "all")

    def last_open_order(self, uid):
        return self.x("SELECT * FROM orders WHERE uid=? AND status='pending'"
                      " ORDER BY id DESC LIMIT 1", (uid,), "one")

    def approve(self, oid, admin_id):
        """(سفارش, خطا) — تأیید مالی اتمیک انجام می‌شود."""
        with self.lock:
            o = self.x("SELECT * FROM orders WHERE id=?", (oid,), "one")
            if not o:
                return None, "سفارش پیدا نشد"
            if o["status"] in ("approved", "rejected"):
                return None, f"قبلاً {o['status']} شده"
            if o["status"] != "paid":
                return None, "فقط سفارش دارای رسید قابل تأیید است"

            if o["wallet_used"]:
                w = self.x("SELECT balance FROM wallet WHERE uid=?", (o["uid"],), "one")
                if not w or w["balance"] < o["wallet_used"]:
                    return None, "موجودی کیف پول برای این سفارش دیگر کافی نیست"

            if o["discount_code"]:
                d = self.discount(o["discount_code"])
                if not d or not d["active"]:
                    return None, "کد تخفیف این سفارش دیگر فعال نیست"
                if d["max_uses"] and d["used"] >= d["max_uses"]:
                    return None, "ظرفیت کد تخفیف این سفارش پر شده است"

            try:
                cur = self.c.execute(
                    "UPDATE orders SET status='approved',decided_at=?,admin_id=? "
                    "WHERE id=? AND status='paid'", (now(), admin_id, oid))
                if cur.rowcount != 1:
                    self.c.rollback()
                    return None, "سفارش قبلاً رسیدگی شده است"

                if o["wallet_used"]:
                    cur = self.c.execute(
                        "UPDATE wallet SET balance=balance-? "
                        "WHERE uid=? AND balance>=?",
                        (o["wallet_used"], o["uid"], o["wallet_used"]))
                    if cur.rowcount != 1:
                        self.c.rollback()
                        return None, "موجودی کیف پول برای این سفارش کافی نیست"
                    self.c.execute(
                        "INSERT INTO wallet_log (uid,amount,kind,detail,ts) "
                        "VALUES (?,?,?,?,?)",
                        (o["uid"], -o["wallet_used"], "order",
                         f"سفارش #{oid}", now()))

                if o["discount_code"]:
                    cur = self.c.execute(
                        "UPDATE discounts SET used=used+1 WHERE code=? AND active=1 "
                        "AND (max_uses=0 OR used<max_uses)", (o["discount_code"],))
                    if cur.rowcount != 1:
                        self.c.rollback()
                        return None, "ظرفیت کد تخفیف این سفارش پر شده است"
                self.c.commit()
            except Exception:
                self.c.rollback()
                raise
            return self.order(oid), ""

    def reject(self, oid, admin_id, reason=""):
        o = self.order(oid)
        if not o:
            return None, "سفارش پیدا نشد"
        if o["status"] in ("approved", "rejected"):
            return None, f"قبلاً {o['status']} شده"
        if o["status"] != "paid":
            return None, "فقط سفارش دارای رسید قابل رد است"
        self.x("UPDATE orders SET status='rejected',decided_at=?,admin_id=?,note=?"
               " WHERE id=? AND status='paid'", (now(), admin_id, reason, oid))
        return self.order(oid), ""

    def cancel_open(self, uid):
        self.x("UPDATE orders SET status='canceled' WHERE uid=? AND status='pending'",
               (uid,))

    # ═══════════════ زیرمجموعه ═══════════════
    def set_referrer(self, uid, referrer):
        if uid == referrer:
            return False
        if self.x("SELECT uid FROM referrals WHERE uid=?", (uid,), "one"):
            return False
        self.x("INSERT INTO referrals (uid,referrer,joined_at) VALUES (?,?,?)",
               (uid, referrer, now()))
        return True

    def referrer_of(self, uid):
        r = self.x("SELECT referrer FROM referrals WHERE uid=?", (uid,), "one")
        return r["referrer"] if r else None

    def my_refs(self, uid):
        return self.x("SELECT * FROM referrals WHERE referrer=?", (uid,), "all")

    def pay_referral(self, oid, percent):
        """سازگاری با سفارش‌های قدیمی؛ پاداش درصدی دیگر وجود ندارد."""
        return None, 0

    def reward_verified_referral(self, invitee_uid, referrer_uid, points=2):
        """یک‌بار برای هر دعوت‌شده پس از تأیید شماره، امتیاز بدهد؛ اتمیک."""
        points = max(0, int(points or 0))
        if points <= 0 or not invitee_uid or not referrer_uid or invitee_uid == referrer_uid:
            return None, 0
        with self.lock:
            try:
                self.c.execute("BEGIN")
                r = self.c.execute(
                    "SELECT uid, referrer FROM referrals WHERE uid=? AND referrer=?",
                    (invitee_uid, referrer_uid)).fetchone()
                if not r:
                    self.c.rollback()
                    return None, 0
                cur = self.c.execute(
                    "INSERT OR IGNORE INTO referral_point_rewards "
                    "(invitee_uid,referrer,points,created_at) VALUES (?,?,?,?)",
                    (invitee_uid, referrer_uid, points, now()))
                if cur.rowcount != 1:
                    self.c.rollback()
                    return None, 0
                self.c.execute("INSERT OR IGNORE INTO points (uid) VALUES (?)", (referrer_uid,))
                self.c.execute("UPDATE points SET balance=balance+?, earned=earned+? WHERE uid=?",
                                (points, points, referrer_uid))
                self.c.execute(
                    "INSERT INTO points_log (uid,amount,kind,detail,ts) VALUES (?,?,?,?,?)",
                    (referrer_uid, points, "referral",
                     f"دعوت معتبر کاربر {invitee_uid}", now()))
                self.c.execute("UPDATE referrals SET rewarded=1 WHERE uid=?", (invitee_uid,))
                self.c.commit()
                return referrer_uid, points
            except Exception:
                self.c.rollback()
                raise

    # ═══════════════ امتیاز ═══════════════
    def p_row(self, uid):
        r = self.x("SELECT * FROM points WHERE uid=?", (uid,), "one")
        if not r:
            self.x("INSERT OR IGNORE INTO points (uid) VALUES (?)", (uid,))
            r = self.x("SELECT * FROM points WHERE uid=?", (uid,), "one")
        return r

    def p_balance(self, uid):
        return self.p_row(uid)["balance"]

    def p_add(self, uid, amount, kind="bonus", detail=""):
        amount = int(amount)
        self.p_row(uid)
        if amount >= 0:
            self.x("UPDATE points SET balance=balance+?, earned=earned+? WHERE uid=?",
                   (amount, amount, uid))
        else:
            cur = self.x("SELECT balance FROM points WHERE uid=?",
                         (uid,), "one")["balance"]
            real = min(cur, -amount)          # فقط همان‌قدر که واقعاً کم شد
            amount = -real
            self.x("UPDATE points SET balance=balance-?, spent=spent+? WHERE uid=?",
                   (real, real, uid))
        self.x("INSERT INTO points_log (uid,amount,kind,detail,ts) VALUES (?,?,?,?,?)",
               (uid, amount, kind, detail, now()))
        return self.p_balance(uid)

    def p_spend(self, uid, amount, detail=""):
        """کسر اتمیک؛ فقط هزینه کم می‌شود و مانده حفظ می‌شود."""
        amount = abs(int(amount or 0))
        if amount <= 0:
            return True, self.p_balance(uid)
        with self.lock:
            self.c.execute("INSERT OR IGNORE INTO points (uid) VALUES (?)", (uid,))
            cur = self.c.execute(
                "UPDATE points SET balance=balance-?, spent=spent+? "
                "WHERE uid=? AND balance>=?",
                (amount, amount, uid, amount))
            if cur.rowcount != 1:
                self.c.commit()
                return False, self.p_balance(uid)
            self.c.execute(
                "INSERT INTO points_log (uid,amount,kind,detail,ts) VALUES (?,?,?,?,?)",
                (uid, -amount, "use", detail, now()))
            self.c.commit()
            return True, self.p_balance(uid)

    def p_charge_due(self, uid, per_hour):
        """بر اساس زمان سپری‌شده امتیاز کم می‌کند.
        برمی‌گرداند (کسر_شده, موجودی, تمام_شد)"""
        r = self.p_row(uid)
        t = now()
        if not r["last_charge"]:
            self.x("UPDATE points SET last_charge=? WHERE uid=?", (t, uid))
            return 0, r["balance"], False
        hours = (t - r["last_charge"]) // 3600
        if hours <= 0:
            return 0, r["balance"], r["balance"] <= 0
        cost = hours * per_hour
        self.x("UPDATE points SET last_charge=? WHERE uid=?",
               (r["last_charge"] + hours * 3600, uid))
        bal = self.p_add(uid, -cost, "runtime", f"{hours} ساعت کارکرد")
        return cost, bal, bal <= 0

    def p_reset_charge(self, uid):
        self.p_row(uid)
        self.x("UPDATE points SET last_charge=? WHERE uid=?", (now(), uid))

    def p_log(self, uid, n=10):
        return self.x("SELECT * FROM points_log WHERE uid=? ORDER BY id DESC LIMIT ?",
                      (uid, n), "all")

    def p_top(self, n=10):
        return self.x("SELECT * FROM points ORDER BY earned DESC LIMIT ?", (n,), "all")

    def p_stats(self):
        r = self.x("SELECT COUNT(*) c, COALESCE(SUM(balance),0) b,"
                   " COALESCE(SUM(earned),0) e, COALESCE(SUM(spent),0) s"
                   " FROM points", (), "one")
        return r or {"c": 0, "b": 0, "e": 0, "s": 0}

    # ═══════════════ تیکت ═══════════════
    def new_ticket(self, uid, subject, text):
        tid = self.x("INSERT INTO tickets (uid,subject,created_at,updated_at)"
                     " VALUES (?,?,?,?)", (uid, subject[:80], now(), now()))
        self.add_msg(tid, text, False)
        return tid

    def add_msg(self, tid, text, from_admin):
        self.x("INSERT INTO ticket_msgs (tid,from_admin,text,ts) VALUES (?,?,?,?)",
               (tid, 1 if from_admin else 0, text, now()))
        self.x("UPDATE tickets SET updated_at=?,status=? WHERE id=?",
               (now(), "answered" if from_admin else "open", tid))

    def ticket(self, tid):
        return self.x("SELECT * FROM tickets WHERE id=?", (tid,), "one")

    def ticket_msgs(self, tid):
        return self.x("SELECT * FROM ticket_msgs WHERE tid=? ORDER BY id", (tid,), "all")

    def open_tickets(self):
        return self.x("SELECT * FROM tickets WHERE status='open' ORDER BY updated_at",
                      (), "all")

    def user_tickets(self, uid):
        return self.x("SELECT * FROM tickets WHERE uid=? ORDER BY id DESC LIMIT 10",
                      (uid,), "all")

    def close_ticket(self, tid):
        self.x("UPDATE tickets SET status='closed' WHERE id=?", (tid,))

    # ═══════════════ آمار ═══════════════
    def revenue(self, since=0):
        r = self.x("SELECT COUNT(*) c, COALESCE(SUM(final),0) s FROM orders"
                   " WHERE status='approved' AND decided_at>=?", (since,), "one")
        return r["c"], r["s"]

    def stats(self):
        t = now()
        d1, s1 = self.revenue(t - 86400)
        d7, s7 = self.revenue(t - 604800)
        d30, s30 = self.revenue(t - 2592000)
        all_c, all_s = self.revenue(0)
        st = {r["status"]: r["c"] for r in
              self.x("SELECT status,COUNT(*) c FROM orders GROUP BY status", (), "all")}
        return {"day": (d1, s1), "week": (d7, s7), "month": (d30, s30),
                "all": (all_c, all_s), "orders": st,
                "wallet_total": (self.x("SELECT COALESCE(SUM(balance),0) s FROM wallet",
                                        (), "one") or {}).get("s", 0)}

    def top_refs(self, n=10):
        return self.x("SELECT referrer, COUNT(*) c FROM referrals"
                      " GROUP BY referrer ORDER BY c DESC LIMIT ?", (n,), "all")

    def has_user_data(self, uid):
        uid = int(uid or 0)
        if uid <= 0:
            return False
        for sql, args in (
            ("SELECT 1 FROM points WHERE uid=? LIMIT 1", (uid,)),
            ("SELECT 1 FROM wallet WHERE uid=? LIMIT 1", (uid,)),
            ("SELECT 1 FROM orders WHERE uid=? LIMIT 1", (uid,)),
            ("SELECT 1 FROM tickets WHERE uid=? LIMIT 1", (uid,)),
            ("SELECT 1 FROM referrals WHERE uid=? OR referrer=? LIMIT 1", (uid, uid)),
            ("SELECT 1 FROM referral_point_rewards WHERE invitee_uid=? OR referrer=? LIMIT 1", (uid, uid)),
        ):
            if self.x(sql, args, "one"):
                return True
        return False

    def delete_user(self, uid):
        """پاک کردن کامل همه‌ی داده‌های فروشگاهی یک کاربر (کیف‌پول، امتیاز، سفارش، تیکت، زیرمجموعه)."""
        uid = int(uid or 0)
        counts = {"orders": 0, "wallet": 0, "points": 0, "tickets": 0, "referrals": 0}
        if uid <= 0:
            return counts
        with self.lock:
            try:
                self.c.execute(
                    "DELETE FROM ticket_msgs WHERE tid IN (SELECT id FROM tickets WHERE uid=?)",
                    (uid,))
                counts["tickets"] = max(0, self.c.execute(
                    "DELETE FROM tickets WHERE uid=?", (uid,)).rowcount or 0)
                self.c.execute(
                    "DELETE FROM referral_rewards WHERE order_id IN (SELECT id FROM orders WHERE uid=?) OR referrer=?",
                    (uid, uid))
                counts["orders"] = max(0, self.c.execute(
                    "DELETE FROM orders WHERE uid=?", (uid,)).rowcount or 0)
                counts["wallet"] = max(0, self.c.execute(
                    "DELETE FROM wallet WHERE uid=?", (uid,)).rowcount or 0)
                self.c.execute("DELETE FROM wallet_log WHERE uid=?", (uid,))
                counts["points"] = max(0, self.c.execute(
                    "DELETE FROM points WHERE uid=?", (uid,)).rowcount or 0)
                self.c.execute("DELETE FROM points_log WHERE uid=?", (uid,))
                self.c.execute(
                    "DELETE FROM referral_point_rewards WHERE invitee_uid=? OR referrer=?",
                    (uid, uid))
                counts["referrals"] = max(0, self.c.execute(
                    "DELETE FROM referrals WHERE uid=? OR referrer=?",
                    (uid, uid)).rowcount or 0)
                self.c.commit()
            except Exception:
                self.c.rollback()
                raise
        try:
            touch_data("shop_user_delete")
        except Exception:
            pass
        return counts


# ═══════════════════════════════════════════════════════════
#   بخش ۲ — ربات، پنل و مدیریت سرویس‌ها
# ═══════════════════════════════════════════════════════════

CONFIG_FILE = os.path.join(BASE_DIR, "manager_config.json")
DB_FILE = os.path.join(BASE_DIR, "manager.db")
CLIENTS_DIR = os.path.join(BASE_DIR, "clients")

# ═══════════════════════════════════════════════════════════════════════
#  تاریخچه‌ی manager_config.json — تورِ نجاتِ «بخش‌های آموزش پرید»
#
#  چرا: کانفیگ تنها جایی است که بخش‌های آموزش (و محتوای ثبت‌شده‌یشان)
#  نگه داشته می‌شود. اگر نسخه‌ی قدیمی‌اش از راه برسد — بازیابی از پشتیبانِ
#  کهنه، pullِ سینکِ گیت‌هاب قبل از بوت، یا یک نمونه‌ی زامبی با کانفیگِ تهی
#  که ذخیره می‌کند — همه‌ی بخش‌ها یک‌جا می‌پرند و مدیر می‌بیند «فقط آموزش
#  فعال‌سازی مانده». پس قبل از هر تغییرِ بخش‌ها یک نسخه‌ی زمان‌دار همین‌جا
#  می‌گذاریم (و چون داخلِ پوشه‌ی داده است، با سینکِ گیت‌هاب و پشتیبانِ
#  تلگرام هم می‌رود و برمی‌گردد) تا با یک دکمه برگردد.
# ═══════════════════════════════════════════════════════════════════════
CFG_HISTORY_DIR = os.path.join(BASE_DIR, "config_history")
CFG_HISTORY_MAX = 500   # سقفِ نسخه‌هایی که خوانده/جست‌وجو می‌شوند (چرخش هم همین را نگه می‌دارد)
CFG_SNAPSHOT_MARK = os.path.join(CFG_HISTORY_DIR, ".last")


def cfg_snapshot_throttled(reason="", mins=30):
    """حداکثر یک نسخه در هر `mins` دقیقه (برای ذخیره‌های پیاپیِ پنل).

    چرا لازم است: Config.save() بعدِ هر تغییر صدا زده می‌شود؛ بدونِ مهار،
    یک نشستِ ویرایش صدها نسخه‌ی میانی می‌سازد و نسخه‌های مهمِ قدیمی‌تر
    زودتر از سقف می‌چرخند. زمان از «نشانگرِ» خودِ پوشه خوانده می‌شود نه از
    mtime فایل — چون mtime با کپی/بازیابی (pullِ سینک) عوض می‌شود.
    """
    try:
        os.makedirs(CFG_HISTORY_DIR, exist_ok=True)
        last = 0.0
        try:
            with open(CFG_SNAPSHOT_MARK, encoding="utf-8") as f:
                last = float((f.read() or "0").strip() or 0)
        except Exception:
            last = 0.0
        if time.time() - last < max(1, int(mins)) * 60:
            return ""
        name = cfg_snapshot(reason)
        try:
            with open(CFG_SNAPSHOT_MARK, "w", encoding="utf-8") as f:
                f.write(str(int(time.time())))
        except OSError:
            pass
        return name
    except Exception:
        return ""


def cfg_snapshot(reason=""):
    """یک نسخه‌ی زمان‌دار از manager_config.json می‌گذارد (ارزان و بی‌خطر).

    اگر محتوا با آخرین نسخه یکی باشد فایلِ تازه نمی‌سازد. نامِ فایل
    «زمان + شمارنده» است؛ چون چند تغییرِ پیاپی در یک ثانیه می‌افتند و با
    نامِ فقط-زمانی، نسخه‌های همان ثانیه روی هم می‌افتادند و «تاریخچه»
    عملاً یک فایل بیشتر نداشت (یعنی همان چیزی که باید نجات می‌داد گم
    می‌شد). شمارنده ترتیبِ زمانی را هم در نام حفظ می‌کند.
    """
    try:
        if not os.path.isfile(CONFIG_FILE):
            return ""
        with open(CONFIG_FILE, "rb") as f:
            data = f.read()
        if not data.strip():
            return ""
        os.makedirs(CFG_HISTORY_DIR, exist_ok=True)
        names = sorted(n for n in os.listdir(CFG_HISTORY_DIR)
                       if n.endswith(".json"))
        if names:
            last = os.path.join(CFG_HISTORY_DIR, names[-1])
            try:
                with open(last, "rb") as f:
                    if f.read() == data:
                        return ""
            except OSError:
                pass
        ts = int(time.time())
        name = f"config_{ts}.json"
        seq = 1
        while os.path.exists(os.path.join(CFG_HISTORY_DIR, name)):
            name = f"config_{ts}_{seq}.json"
            seq += 1
        tmp = os.path.join(CFG_HISTORY_DIR, name + ".tmp")
        with open(tmp, "wb") as f:
            f.write(data)
        os.replace(tmp, os.path.join(CFG_HISTORY_DIR, name))
        _cfg_history_rotate()
        return name
    except Exception as e:
        print(f"cfg_snapshot: {type(e).__name__}: {e}", flush=True)
        return ""


def _cfg_history_rotate(keep_days=7, hard_cap=500):
    """چرخشِ تاریخچه بر اساسِ سن: تازه‌ها کامل، قدیمی‌ترها نمایی.

    چون قبلِ <b>هر</b> تغییرِ بخش‌ها یک نسخه می‌نشیند، یک نشستِ ویرایش می‌تواند
    ده‌ها نسخه‌ی میانی بسازد. اگر فقط «آخرین N تا» را نگه داریم، حالتِ هفته‌ی
    پیش همان روزِ اول می‌چرخد و می‌پرد؛ پس نسخه‌های هفت روزِ اخیر کامل
    می‌مانند و بعد از آن یکی‌درمیان، چهاردَرمیان، … حذف می‌شوند تا هم عمقِ
    تاریخ بماند هم سقفِ دیسک و حجمِ بسته‌ی سینک (هر نسخه یکی دو کیلوبایت).
    """
    try:
        entries = []
        for n in sorted(os.listdir(CFG_HISTORY_DIR)):
            if not n.endswith(".json"):
                continue
            try:
                age = time.time() - os.path.getmtime(
                    os.path.join(CFG_HISTORY_DIR, n))
            except OSError:
                age = 0.0
            entries.append((n, age))
    except OSError:
        return
    if not entries:
        return
    keep = set()
    for idx in range(len(entries) - 1, -1, -1):
        n, age = entries[idx]
        if age <= keep_days * 86400:
            keep.add(n)
            continue
        step = 2
        span = keep_days * 86400
        while age > span * 2:
            step *= 2
            span *= 2
        if step <= 1 or idx % step == 0:
            keep.add(n)
    for n, _age in entries:
        if n in keep:
            continue
        try:
            os.remove(os.path.join(CFG_HISTORY_DIR, n))
        except OSError:
            pass
    left = [n for n, _a in entries if n in keep]
    for n in left[:max(0, len(left) - hard_cap)]:
        try:
            os.remove(os.path.join(CFG_HISTORY_DIR, n))
        except OSError:
            pass


def cfg_history_list():
    """[(نامِ فایل, dictِ کانفیگ, mtime)] — از تازه به قدیم."""
    out = []
    try:
        names = sorted((n for n in os.listdir(CFG_HISTORY_DIR)
                        if n.endswith(".json")), reverse=True)
    except OSError:
        return out
    for n in names[:CFG_HISTORY_MAX]:
        path = os.path.join(CFG_HISTORY_DIR, n)
        try:
            with open(path, encoding="utf-8") as f:
                d = json.load(f)
            if isinstance(d, dict):
                out.append((n, d, os.path.getmtime(path)))
        except Exception:
            continue
    return out


def _cfg_secs(d):
    """بخش‌های آموزشِ یک dictِ کانفیگ (بدون هیچ وابستگی به کلاس‌ها)."""
    raw = (d or {}).get("tut_sections") or []
    out = []
    if not isinstance(raw, list):
        return out
    for i, s in enumerate(raw):
        if not isinstance(s, dict):
            continue
        try:
            sid = int(s.get("id") or i + 1)
        except (TypeError, ValueError):
            sid = i + 1
        try:
            n = len([x for x in (s.get("ids") or [])])
        except Exception:
            n = 0
        out.append({"id": sid, "name": str(s.get("name") or f"بخش {sid}")[:60],
                    "emoji": str(s.get("emoji") or "▫️")[:4], "n": n})
    return out


def _cfg_sec_registered(rec):
    """آیا این رکوردِ بخش «واقعاً ثبت‌شده» است یا پیش‌نویسِ نیمه‌ساخته؟

    پیش‌نویس یعنی بخشی که تازه با «➕ بخش جدید» ساخته شده و هنوز نه محتوا
    دارد، نه اسمِ عوض‌شده، نه preset، نه دکمه/متنِ پایان. چنین رکوردی در
    نسخه‌های تاریخچه هست (چون نسخه‌برداری قبلِ هر تغییر انجام می‌شود) و
    اگر «گم‌شده» حساب می‌شد، موقعِ بازیابی یک‌جا بخشِ تکراریِ خالی
    برمی‌گشت. معیارها دقیقاً همان‌هایی است که مدیر روی صفحه‌ی بخش می‌بیند.
    """
    try:
        if len(rec.get("ids") or []):
            return True
    except Exception:
        pass
    if str(rec.get("text") or "").strip():
        return True
    if str(rec.get("preset") or "").strip():
        return True
    if str(rec.get("name") or "").strip() not in ("", "بخش جدید"):
        return True
    if str(rec.get("btn_cmd") or "").strip():
        return True
    if str(rec.get("note") or "").strip():
        return True
    return False


def _cfg_lost_map(extra=False):
    """بخش‌هایی که دیگر در کانفیگِ فعلی نیستند ولی در تاریخچه پیدا می‌شوند.

    خروجی: ``{idِ بخش در آن نسخه: (dictِ بخش, نامِ نسخه)}`` — برای هر بخش
    پُرترین نسخه‌اش (بیشترین پیامِ ثبت‌شده)، چون نسخه‌های تاریخچه مربوط به
    زمان‌های مختلف‌اند.

    معیارِ «گم‌شده» <b>نام</b>ِ بخش است، نه کد:
      • ``tut_next_id`` کدهای آزاد را دوباره استفاده می‌کند؛ پس اگر بعد از
        پریدنِ بخش‌ها بخشِ تازه‌ای ساخته باشند، کدِ بخشِ گم‌شده به آن می‌خورد
        و با کد نمی‌شود فهمید که «این همان نیست» (و موقعِ برگرداندن هم به
        بخشِ برگشتی کدِ تازه داده می‌شود).
      • اگر کاربر نامِ بخشی را عوض کرده باشد، محتوا سر جایش است و نسخه‌ی
        کهنه‌ی آن برنمی‌گردد (نامِ قدیم در لیستِ فعلی نیست ولی همان بخش است).
    """
    try:
        with open(CONFIG_FILE, encoding="utf-8") as f:
            cur = json.load(f)
    except Exception:
        return {}
    if not isinstance(cur, dict):
        return {}
    have_names = set()
    for x in (cur.get("tut_sections") or []):
        if not isinstance(x, dict):
            continue
        nm = str(x.get("name") or "").strip()
        if nm:
            have_names.add(nm)
    lost = {}
    snaps = cfg_history_list()
    if extra:
        snaps = snaps + [(lbl, d, 0.0) for lbl, d in _cfg_extra_sources()]
        # منابعِ بیرونی آخر بررسی می‌شوند تا در تساوی، تاریخچه ترجیح داده شود.
    for name, d, _mt in snaps:
        raw = d.get("tut_sections") or []
        if not isinstance(raw, list):
            continue
        for s in raw:
            if not isinstance(s, dict):
                continue
            if not _cfg_sec_registered(s):
                continue          # پیش‌نویسِ نیمه‌ساخته «گم‌شده» نیست
            try:
                sid = int(s.get("id") or 0)
            except (TypeError, ValueError):
                continue
            if not sid:
                continue
            if str(s.get("name") or "").strip() in have_names:
                continue          # همین بخش (با هر کدی) الان هست
            try:
                n = len(s.get("ids") or [])
            except Exception:
                n = 0
            hit = lost.get(sid)
            if hit is None or n > len(hit[0].get("ids") or []):
                lost[sid] = (s, name)
    return lost


def cfg_lost_section_map(extra=False):
    """بخش‌های گم‌شده؛ با ``extra=True`` داخلِ zipِ پشتیبانِ ربات هم می‌گردد."""
    return _cfg_lost_map(extra=extra)


def cfg_lost_sections(extra=False):
    """خلاصه‌ی بخش‌های گم‌شده برای هشدارِ بوت و پنلِ بازیابی.

    ``extra=True`` ⇒ اگر در تاریخچه چیزی نبود، zipِ پشتیبانِ خودِ ربات هم
    جست‌وجو می‌شود (تنها منبعِ باقی‌مانده برای کسی که تازه این قابلیت را
    دیپلوی کرده و تاریخچه‌اش خالی است).

    خروجی: ``(نامِ بهترین نسخه, dictِ همان نسخه, [id بخش‌های گم‌شده])``
    یا ``None``. «بهترین» = نسخه‌ای که بیشترین بخشِ گم‌شده را دارد و در
    تساوی، نسخه‌ای که <b>مجموعِ پیام‌های ثبت‌شده‌اش</b> بیشتر است (چیزی که
    برای مدیر ارزش دارد خودِ ویدیوها/متن‌ها هستند، نه تعدادِ ردیف‌ها).
    """
    lost = cfg_lost_section_map(extra=extra)
    if not lost:
        return None
    tally = {}
    for sid, (_s, name) in lost.items():
        tally[name] = tally.get(name, 0) + 1
    top = max(tally.values())
    cand = [n for n, c in tally.items() if c == top]
    snaps = cfg_history_list()
    if len(cand) > 1:
        wanted = set(cand)
        best_name, best_rich = None, -1
        for name, d, _mt in snaps:
            if name not in wanted:
                continue
            rich = 0
            for s in (d.get("tut_sections") or []):
                if isinstance(s, dict):
                    try:
                        rich += len(s.get("ids") or [])
                    except Exception:
                        pass
            if rich > best_rich:
                best_name, best_rich = name, rich
        best = best_name or cand[0]
    else:
        best = cand[0]
    snap = None
    for name, d, _mt in snaps:
        if name == best:
            snap = d
            break
    return best, (snap or {}), sorted(lost.keys())


def _cfg_sec_best_versions(extra_snaps=()):
    """پُرترین نسخه‌ی هر بخش، هم با کلیدِ «نام» هم با کلیدِ «کد».

    ``extra_snaps`` منبع‌های بیرون از تاریخچه‌اند (مثلِ zipِ پشتیبانِ ربات)؛
    چون در هر دو حالتِ «گم‌شده» و «خالی‌شده» فقط <b>یک</b> نسخه به کار
    می‌رود، اگر آن منبع پُرتر باشد جایش را می‌گیرد وگرنه نسخه‌ی تاریخچه
    می‌ماند — این‌طور پیام‌های خیلی قدیمی با پیام‌های تازه قاطی نمی‌شوند.

    برای بخش‌هایی که <b>هستند</b> ولی محتوایشان خالی شده (ویدیو/متنِ
    ثبت‌شده پریده) — مثلاً «💳 شارژ کیف پول»، «🎯 خرید امتیاز»، «💎 اشتراک
    ماهانه» — چون نامِ بخش سرِ جایش است، «گم‌شده» حساب نمی‌شود؛ پس جدا
    پُرترین نسخه‌ی تاریخیِ هر بخش را پیدا می‌کنیم تا محتوایش برگردد.
    """
    by_name, by_id = {}, {}
    snaps = [(n, d) for n, d, _mt in cfg_history_list()]
    snaps += [(lbl, d) for lbl, d in (extra_snaps or ())]
    for name, d in snaps:
        raw = d.get("tut_sections") or []
        if not isinstance(raw, list):
            continue
        for rec in raw:
            if not isinstance(rec, dict) or not _cfg_sec_registered(rec):
                continue
            try:
                n = len(rec.get("ids") or []) + (1 if str(rec.get("text") or "").strip() else 0)
            except Exception:
                n = 0
            nm = str(rec.get("name") or "").strip()
            if nm:
                hit = by_name.get(nm)
                if hit is None or n > hit[0]:
                    by_name[nm] = (n, rec, name)
            try:
                sid = int(rec.get("id") or 0)
            except (TypeError, ValueError):
                sid = 0
            if sid:
                hit = by_id.get(sid)
                if hit is None or n > hit[0]:
                    by_id[sid] = (n, rec, name)
    return by_name, by_id


def _cfg_poor(extra=False):   # noqa: C901 — یک پاس روی بخش‌ها
    """بخش‌هایی که الان هستند ولی از نسخه‌ی تاریخیِ خودشان خالی‌ترند.

    خروجی: ``[(sid, name, [توضیحِ چه‌چیزی کم است], dictِ نسخه‌ی پُر)]``
    — مرتب بر اساسِ «چقدر محتوا کم شده» (بیشترین اول) تا در پنل همان‌هایی که
    بیشتر به چشم می‌آیند بالا باشند.
    """
    try:
        with open(CONFIG_FILE, encoding="utf-8") as f:
            cur = json.load(f)
    except Exception:
        return []
    if not isinstance(cur, dict):
        return []
    extra_snaps = _cfg_extra_sources() if extra else ()
    by_name, by_id = _cfg_sec_best_versions(extra_snaps)
    out = []
    for s in (cur.get("tut_sections") or []):
        if not isinstance(s, dict):
            continue
        try:
            sid = int(s.get("id") or 0)
        except (TypeError, ValueError):
            sid = 0
        nm = str(s.get("name") or "").strip()
        best = None
        for key, table in ((nm, by_name), (sid, by_id)):
            hit = table.get(key) if key else None
            if hit and (best is None or hit[0] > best[0]):
                best = hit
        if not best:
            continue
        _n, hist, _src = best
        miss = []
        try:
            cur_ids = [int(x) for x in (s.get("ids") or [])]
        except Exception:
            cur_ids = []
        try:
            hist_ids = [int(x) for x in (hist.get("ids") or [])]
        except Exception:
            hist_ids = []
        if len(hist_ids) > len(cur_ids):
            miss.append(("ids", "%d پیامِ محتوا" % (len(hist_ids) - len(cur_ids))))
        cur_txt = str(s.get("text") or "").strip()
        hist_txt = str(hist.get("text") or "").strip()
        if len(hist_txt) > len(cur_txt):
            miss.append(("text", "متنِ بخش"))
        for key, label in (("note", "متنِ پایان"), ("btn_label", "برچسبِ دکمه"),
                           ("btn_cmd", "دستورِ دکمه")):
            if len(str(hist.get(key) or "").strip()) > len(str(s.get(key) or "").strip()):
                miss.append((key, label))
        if cur_ids and not int(s.get("chat") or 0) and int(hist.get("chat") or 0):
            miss.append(("chat", "چتِ منبعِ محتوا"))
        if not bool(s.get("on", True)) and bool(hist.get("on", True)):
            miss.append(("on", "روشن بودنِ بخش"))
        if miss:
            out.append((sid, nm, miss, hist))
    out.sort(key=lambda r: -sum(1 for k, _v in r[2] if k == "ids"))
    return out


def cfg_poor_sections(extra=False):
    """بخش‌های موجود ولی خالی‌شده؛ ``extra=True`` یعنی zipِ پشتیبان هم بررسی شود."""
    return _cfg_poor(extra=extra)


def cfg_restore_section_content(only_sid=None, extra=False):
    """محتوای پریده‌ی بخش‌های <b>موجود</b> را از پُرترین نسخه‌ی تاریخی برمی‌گرداند.

    فقط چیزی را برمی‌گرداند که الان خالی/کمتر است؛ آنچه مدیر امروز دارد
    (متنِ تازه‌تر، پیام‌های بیشتر، تنظیمِ دستیِ دکمه) دست نمی‌خورد. اگر هم
    الان کمتر است، نسخه‌ی تاریخیِ پُرتر جایگزین نمی‌شود بلکه **ادغام** می‌شود
    (پیام‌های تکراری اضافه نمی‌شوند).

    خروجی: ``(تعدادِ بخشِ ترمیم‌شده, [(نامِ بخش, [برچسبِ چه‌چیزی برگشت])])``
    """
    poor = cfg_poor_sections(extra=extra)
    if only_sid is not None:
        try:
            only_sid = int(only_sid)
        except (TypeError, ValueError):
            only_sid = None
        poor = [r for r in poor if r[0] == only_sid]
    if not poor:
        return 0, []
    cfg_snapshot("before-restore-content")
    try:
        with open(CONFIG_FILE, encoding="utf-8") as f:
            cur = json.load(f)
        if not isinstance(cur, dict):
            return 0, []
        rows = cur.get("tut_sections") or []
    except Exception as e:
        print(f"cfg_restore_section_content: {type(e).__name__}: {e}", flush=True)
        return 0, []
    fixed = []
    for sid, nm, miss, hist in poor:
        for row in rows:
            if not isinstance(row, dict):
                continue
            try:
                if int(row.get("id") or 0) != sid:
                    continue
            except (TypeError, ValueError):
                continue
            labels = []
            for key, label in miss:
                if key == "ids":
                    try:
                        have = [int(x) for x in (row.get("ids") or [])]
                    except Exception:
                        have = []
                    try:
                        add = [int(x) for x in (hist.get("ids") or [])]
                    except Exception:
                        add = []
                    merged = list(have)
                    for x in add:
                        if x not in merged:
                            merged.append(x)
                    if len(merged) > len(have):
                        row["ids"] = merged
                        if not int(row.get("chat") or 0) and int(hist.get("chat") or 0):
                            row["chat"] = int(hist["chat"])
                        labels.append(label)
                    continue
                hv = str(row.get(key) or "")
                nv = str(hist.get(key) or "")
                if key == "on":
                    if not bool(row.get("on", True)) and bool(hist.get("on", True)):
                        row["on"] = True
                        labels.append(label)
                    continue
                if len(nv.strip()) > len(hv.strip()):
                    row[key] = nv
                    labels.append(label)
            if labels:
                fixed.append((nm, labels))
            break
    if not fixed:
        return 0, []
    try:
        tmp = CONFIG_FILE + ".tmp"
        with open(tmp, "w", encoding="utf-8") as f:
            json.dump(cur, f, ensure_ascii=False, indent=2)
        os.replace(tmp, CONFIG_FILE)
        try:
            os.chmod(CONFIG_FILE, 0o600)
        except OSError:
            pass
        touch_data("config-restore-content")
    except Exception as e:
        print(f"cfg_restore_section_content: {type(e).__name__}: {e}", flush=True)
        return 0, []
    return len(fixed), fixed


BACKUP_ZIP_CANDIDATES = (
    os.path.join(BASE_DIR, "jafj_backup_latest.zip"),
    os.path.join(BASE_DIR, "backups", "jafj_backup_latest.zip"),
)


def cfg_from_backup_zip():
    """کانفیگِ داخلِ zipِ پشتیبانِ ربات — تنها نسخه‌ی قدیمیِ موجود برای کسی
    که <b>تازه</b> این قابلیت را دیپلوی می‌کند و پوشه‌ی ``config_history``
    برایش خالی است (تاریخچه از همین دیپلوی به بعد ساخته می‌شود).

    خروجی: ``(dictِ کانفیگ, مسیرِ zip)`` یا ``None``.
    """
    for path in BACKUP_ZIP_CANDIDATES:
        if not os.path.isfile(path):
            continue
        try:
            with zipfile.ZipFile(path) as zf:
                hits = [n for n in zf.namelist()
                        if os.path.basename(n) == "manager_config.json"
                        and not n.endswith("/")]
                if not hits:
                    continue
                hits.sort(key=len)          # نزدیک‌ترین به ریشه‌ی بسته
                with zf.open(hits[0]) as f:
                    d = json.load(f)
                if isinstance(d, dict):
                    return d, path
        except Exception as e:
            print(f"cfg_from_backup_zip: {type(e).__name__}: {e}", flush=True)
            continue
    return None


def _cfg_extra_sources():
    """منبع‌های نجاتِ بیرون از config_history: [(برچسب, dictِ کانفیگ)]."""
    out = []
    got = cfg_from_backup_zip()
    if got:
        out.append((os.path.basename(got[1]), got[0]))
    return out


def cfg_restore_sections(fname=None, extra=False):
    """بخش‌های گم‌شده را از تاریخچه (و با extra=True از zipِ پشتیبان) برمی‌گرداند.

    fname=None یعنی «از هر نسخه‌ای که داری» (پُرترین نسخه‌ی هر بخش)؛
    در غیرِ این صورت فقط همان نسخه.

    دو نکته که داده را خراب نکند:
      • بخشی که مدیر <b>الان</b> دارد دست نمی‌خورد.
      • اگر کدِ یک بخشِ گم‌شده در این فاصله به بخشِ دیگری خورده باشد
        (tut_next_id کدهای آزاد را دوباره استفاده می‌کند)، بخشِ برگشتی
        <b>کدِ تازه</b> می‌گیرد و سر جایش قرار می‌دهد — نه اینکه بی‌صدا
        رد شود و نه اینکه بخشِ فعلی له شود.

    خروجی: (تعدادِ برگردانده‌شده, تعدادِ کلِ بخش‌ها) یا (0, 0) اگر نشد.
    """
    if fname is None:
        items = [(sid, s) for sid, (s, _n)
                 in cfg_lost_section_map(extra=extra).items()]
        if not items:
            return 0, 0
        items.sort(key=lambda kv: kv[0])
    else:
        hit = None
        for n, d, _mt in cfg_history_list():
            if n == fname:
                hit = d
                break
        if hit is None:
            return 0, 0
        have_ids0 = set()
        try:
            with open(CONFIG_FILE, encoding="utf-8") as f:
                cur0 = json.load(f)
            for x in _cfg_secs(cur0 if isinstance(cur0, dict) else {}):
                have_ids0.add(x["id"])
        except Exception:
            pass
        have_names = set()
        try:
            with open(CONFIG_FILE, encoding="utf-8") as f:
                cur1 = json.load(f)
            for x in (cur1.get("tut_sections") or [] if isinstance(cur1, dict) else []):
                if isinstance(x, dict):
                    nm = str(x.get("name") or "").strip()
                    if nm:
                        have_names.add(nm)
        except Exception:
            pass
        items = []
        for s in (hit.get("tut_sections") or []):
            if not isinstance(s, dict):
                continue
            if not _cfg_sec_registered(s):
                continue          # پیش‌نویس را برنگردان
            if str(s.get("name") or "").strip() in have_names:
                continue          # همان بخش الان هم هست
            try:
                sid = int(s.get("id") or 0)
            except (TypeError, ValueError):
                continue
            if sid and sid not in have_ids0:
                items.append((sid, s))
            elif sid:
                # کدش به بخشِ دیگری خورده؛ با کدِ تازه برمی‌گردد
                items.append((0, s))
        items.sort(key=lambda kv: kv[0])
        if not items:
            return 0, 0
    cfg_snapshot("before-restore-sections")
    try:
        with open(CONFIG_FILE, encoding="utf-8") as f:
            cur = json.load(f)
        if not isinstance(cur, dict):
            cur = {}
    except Exception:
        cur = {}
    have = [s for s in (cur.get("tut_sections") or []) if isinstance(s, dict)]
    used = {str(x.get("name") or "").strip() for x in have}
    used.discard("")
    used_ids = set()
    for s in have:
        try:
            used_ids.add(int(s.get("id") or 0))
        except (TypeError, ValueError):
            continue
    nxt = (max(used_ids) if used_ids else 0) + 1
    added = 0
    for _sid, sec in items:
        sec = dict(sec)
        nm = str(sec.get("name") or "").strip()
        if nm and nm in used:
            continue                      # همین بخش الان هم هست
        try:
            sid = int(sec.get("id") or 0)
        except (TypeError, ValueError):
            sid = 0
        if not sid or sid in used_ids:
            while nxt in used_ids:
                nxt += 1
            sec["id"] = nxt
            used_ids.add(nxt)
            nxt += 1
        else:
            used_ids.add(sid)
        if nm:
            used.add(nm)
        have.append(sec)
        added += 1
    cur["tut_sections"] = have
    tmp = CONFIG_FILE + ".tmp"
    with open(tmp, "w", encoding="utf-8") as f:
        json.dump(cur, f, ensure_ascii=False, indent=2)
    os.replace(tmp, CONFIG_FILE)
    try:
        touch_data("config-restore")
    except Exception:
        pass
    return added, len(have)


def cfg_restore_full(fname):
    """کلِ کانفیگ را از یک نسخه‌ی تاریخچه برمی‌گرداند (اول یک نسخه‌ی نجات هم می‌گذارد)."""
    path = os.path.join(CFG_HISTORY_DIR, fname)
    if not os.path.isfile(path):
        return False
    try:
        with open(path, encoding="utf-8") as f:
            json.load(f)
    except Exception:
        return False
    cfg_snapshot("before-full-restore")
    try:
        shutil.copyfile(path, CONFIG_FILE)
        touch_data("config-restore-full")
        return True
    except Exception as e:
        print(f"cfg_restore_full: {type(e).__name__}: {e}", flush=True)
        return False

# ═══════════════════════════════════════════════════════════════════════
#  کرش و پایداریِ داده
#
#  چرا این بخش لازم شد: روی میزبانی که دیسکِ ماندگار ندارد (یا Disk روی
#  مسیرِ اشتباه مانت شده)، هر کرش/ری‌استارت پوشه‌ی داده را از نو می‌سازد.
#  یعنی «ربات اطلاعات را گرفته بود» ولی با اولین کرش همه‌چیز رفت. تنها
#  چیزی که از کرش جان سالم به‌در می‌برد، یک نسخه‌ی بیرونی است (تلگرام یا
#  گیت‌هاب). پس این بخش:
#    ۱) هر تغییرِ مهم را بلافاصله (با تأخیرِ کوتاه) به گیت‌هاب می‌فرستد؛
#    ۲) کرش را با دلیلش در crash.log ثبت می‌کند تا دفعه‌ی بعد معلوم باشد؛
#    ۳) هنگامِ مرگِ غیرمنتظره هم یک «ذخیره‌ی نجات» می‌زند.
# ═══════════════════════════════════════════════════════════════════════

# «سرد» بوت شدیم؟ یعنی پوشه‌ی داده از قبل هیچ دیتابیسی نداشت — نشانه‌ی
# قویِ اینکه دیسک پاک شده (یا ماندگار نیست).
COLD_START = not os.path.exists(DB_FILE)
# رکوردِ آخرین خروجِ ناظر (railway-start.sh) — برای گزارشِ «چرا مرد».
LAST_EXIT_FILE = os.path.join(BASE_DIR, ".jafj_last_exit")
CRASH_LOG_FILE = os.path.join(BASE_DIR, "crash.log")

_CRASH_LOCK = threading.Lock()
_CRASH_MAX_BYTES = 256 * 1024

# هوک‌هایی که Manager وصل می‌کند؛ DB/Config هم می‌توانند صدایش بزنند بدون
# اینکه به کلاس Manager وابسته باشند.
_DATA_TOUCH = [None]          # callable(reason) → None


def touch_data(reason=""):
    """«داده عوض شد» را به Manager خبر بده (بدون هیچ خطری اگر وصل نباشد)."""
    fn = _DATA_TOUCH[0]
    if not fn:
        return False
    try:
        fn(reason)
        return True
    except Exception:
        return False


def log_crash(reason, detail=""):
    """یک بلوک به crash.log اضافه کن (چرخشی، حداکثر ۲۵۶KB)."""
    try:
        with _CRASH_LOCK:
            d = os.path.dirname(CRASH_LOG_FILE) or "."
            if not os.path.isdir(d):
                os.makedirs(d, exist_ok=True)
            with open(CRASH_LOG_FILE, "a", encoding="utf-8") as f:
                f.write(f"\n===== {datetime.now():%Y-%m-%d %H:%M:%S} [{reason}] "
                        f"build={BUILD_VERSION} pid={os.getpid()} "
                        f"host={HOST_LABEL} =====\n")
                tail = (detail or "").strip()
                f.write((tail[-8000:] if len(tail) > 8000 else tail) + "\n")
            try:
                if os.path.getsize(CRASH_LOG_FILE) > _CRASH_MAX_BYTES:
                    with open(CRASH_LOG_FILE, encoding="utf-8",
                              errors="ignore") as f:
                        keep = f.read()[-_CRASH_MAX_BYTES // 2:]
                    with open(CRASH_LOG_FILE, "w", encoding="utf-8") as f:
                        f.write(keep)
            except Exception:
                pass
        return True
    except Exception:
        return False


def read_crash_log(max_bytes=4000):
    """بخشِ آخرِ crash.log (برای پیامِ مدیر و /diag)."""
    try:
        with open(CRASH_LOG_FILE, encoding="utf-8", errors="ignore") as f:
            return f.read()[-max_bytes:].strip()
    except Exception:
        return ""


def crash_blocks(within_secs=None):
    """بلوک‌های crash.log → [(ts, reason, body), …] (تازه‌ترین آخر)."""
    out = []
    try:
        with open(CRASH_LOG_FILE, encoding="utf-8", errors="ignore") as f:
            txt = f.read()
    except Exception:
        return out
    cur = None
    for line in txt.splitlines():
        if line.startswith("=====") and "[" in line:
            if cur:
                out.append(cur)
            ts = 0
            try:
                stamp = line.split("=====")[1].strip().split()[0] + " " + \
                    line.split("=====")[1].strip().split()[1]
                ts = int(time.mktime(time.strptime(stamp, "%Y-%m-%d %H:%M:%S")))
            except Exception:
                ts = 0
            reason = ""
            try:
                reason = line.split("[", 1)[1].split("]", 1)[0]
            except Exception:
                pass
            cur = (ts, reason, [])
        elif cur is not None:
            cur[2].append(line)
    if cur:
        out.append(cur)
    res = [(ts, r, "\n".join(b).strip()) for ts, r, b in out]
    if within_secs:
        cutoff = int(time.time()) - int(within_secs)
        res = [x for x in res if x[0] >= cutoff]
    return res


def last_exit_info():
    """آخرین خروجِ ثبت‌شده توسط railway-start.sh → dict یا {}."""
    try:
        with open(LAST_EXIT_FILE, encoding="utf-8") as f:
            return json.load(f) or {}
    except Exception:
        return {}


def write_last_exit(code, uptime=0, note=""):
    try:
        with open(LAST_EXIT_FILE, "w", encoding="utf-8") as f:
            json.dump({"code": int(code), "uptime": int(uptime or 0),
                       "ts": now(), "note": note,
                       "build": BUILD_VERSION}, f, ensure_ascii=False)
        return True
    except Exception:
        return False


def _cgroup_memory_available_mb(cgroup_root="/sys/fs/cgroup",
                                proc_cgroup="/proc/self/cgroup"):
    """حافظه‌ی باقی‌مانده تا سقفِ cgroup، در صورتِ وجود.

    /proc/meminfo در کانتینرها معمولاً حافظه‌ی کلِ میزبان را نشان می‌دهد؛
    در نتیجه محافظِ بک‌آپ ممکن است خیال کند چند گیگابایت آزاد است، درحالی‌که
    خودِ کانتینر مثلاً فقط ۲۵۶ مگابایت دارد. هر دو قالبِ cgroup v1 و v2 را
    می‌خوانیم و مقدارِ «نامحدود» را نادیده می‌گیریم.
    """
    candidates = [cgroup_root]
    try:
        with open(proc_cgroup, encoding="utf-8") as f:
            for line in f:
                parts = line.rstrip("\n").split(":", 2)
                if len(parts) != 3:
                    continue
                _hierarchy, controllers, group_path = parts
                group_path = group_path.lstrip("/")
                if not group_path:
                    continue
                # در cgroupهای تو در تو ممکن است محدودیت روی یکی از گروه‌های
                # والد باشد و برای leaf مقدار memory.max برابر max باشد. همه‌ی
                # اجدادِ مسیر را هم بررسی کن؛ فقط leaf می‌تواند سقف مؤثر را
                # از دست بدهد و باعث انتخاب حالتِ پرمصرف یا OOM شود.
                parts = [p for p in group_path.split("/")
                         if p and p not in (".", "..")]
                bases = ([cgroup_root] if not controllers else
                         ([os.path.join(cgroup_root, "memory"), cgroup_root]
                          if "memory" in controllers.split(",") else []))
                for base in bases:
                    for depth in range(1, len(parts) + 1):
                        candidates.append(os.path.join(base, *parts[:depth]))
    except Exception:
        pass

    seen = set()
    headroom = []
    for directory in candidates:
        if directory in seen:
            continue
        seen.add(directory)
        for usage_name, limit_name in (
                ("memory.current", "memory.max"),
                ("memory.usage_in_bytes", "memory.limit_in_bytes")):
            try:
                with open(os.path.join(directory, limit_name), encoding="ascii") as f:
                    raw_limit = f.read().strip()
                if not raw_limit or raw_limit.lower() == "max":
                    continue
                limit = int(raw_limit)
                # cgroup v1 uses a very large sentinel for an unlimited limit.
                if limit <= 0 or limit >= (1 << 60):
                    continue
                with open(os.path.join(directory, usage_name), encoding="ascii") as f:
                    usage = int(f.read().strip())
                headroom.append(max(0, limit - max(0, usage)))
            except Exception:
                continue
    # محدودیتِ گروه‌های والد هم برای پروسه معتبر است؛ کمترین فضای باقی‌مانده
    # همان سقفِ مؤثر است، حتی اگر سطحِ والد فضای بیشتری گزارش کند.
    return min(headroom) // (1024 * 1024) if headroom else None


def _extract_zip_member_streaming(zf, arc, dest, chunk_size=64 * 1024):
    """یک عضو ZIP را تکه‌تکه و اتمیک استخراج کن، بدون zf.read() در RAM.

    فایل‌های دیتابیس/سشن ممکن است از RAM پلن رایگان بزرگ‌تر باشند. zf.read()
    کلِ عضوِ فشرده‌نشده را یکجا می‌سازد و می‌تواند کانتینر را با کد ۱۳۷ بکشد.
    """
    directory = os.path.dirname(dest)
    if directory:
        os.makedirs(directory, exist_ok=True)
    tmp = dest + ".restore_tmp"
    try:
        with zf.open(arc, "r") as src, open(tmp, "wb") as out:
            shutil.copyfileobj(src, out, length=max(4096, int(chunk_size or 0)))
        size = os.path.getsize(tmp)
        os.replace(tmp, dest)
        try:
            os.chmod(dest, 0o600)
        except Exception:
            pass
        return size
    except Exception:
        try:
            if os.path.exists(tmp):
                os.remove(tmp)
        except Exception:
            pass
        raise


# نامِ فارسیِ حلقه‌های سلف — همان کلیدهایی که 95.py در
# jafj_status.json → loops می‌نویسد.
LOOP_LABELS_FA = {
    "sender": "ارسال", "exchange": "تبادل", "scan": "اسکنِ گروه‌ها",
    "membership": "بررسیِ عضویت", "report": "گزارشِ خلاصه",
    "risk": "محافظِ ریپ", "status": "وضعیت",
    "memory": "آزادسازیِ حافظه",
}


def cgroup_mem_mb(root="/sys/fs/cgroup", proc_cgroup="/proc/self/cgroup"):
    """(سقف, مصرف) حافظه‌ی همین کانتینر به مگابایت یا (None, None).

    برای گزارش لازم است، نه تصمیم: `/diag` باید بگوید «۴۰۰MB آزاد از
    ۵۱۲MB سقف» تا معلوم شود کمبودِ رم واقعی است یا توهمِ meminfo.
    """
    seen = set()
    dirs = [root]
    try:
        with open(proc_cgroup, encoding="utf-8") as f:
            for line in f:
                parts = line.rstrip("\n").split(":", 2)
                if len(parts) != 3:
                    continue
                _h, ctrl, group = parts
                group = group.lstrip("/")
                if not group:
                    continue
                if not ctrl:
                    dirs.append(os.path.join(root, group))
                elif "memory" in ctrl.split(","):
                    dirs.append(os.path.join(root, "memory", group))
                    dirs.append(os.path.join(root, group))
    except Exception:
        pass
    for d in dirs:
        if d in seen:
            continue
        seen.add(d)
        for lim_name, use_name in (("memory.max", "memory.current"),
                                   ("memory.limit_in_bytes",
                                    "memory.usage_in_bytes")):
            try:
                with open(os.path.join(d, lim_name), encoding="ascii") as f:
                    raw = f.read().strip()
            except Exception:
                continue
            if not raw or raw.lower() == "max":
                continue
            try:
                lim = int(raw)
            except Exception:
                continue
            if lim <= 0 or lim > (1 << 60):
                continue
            use = 0
            try:
                with open(os.path.join(d, use_name), encoding="ascii") as f:
                    use = int(f.read().strip() or 0)
            except Exception:
                use = 0
            return round(lim / 1048576.0, 1), round(use / 1048576.0, 1)
    return None, None


def mem_available_mb():
    """حافظه‌ی آزادِ واقعیِ پروسه (MB) یا None اگر معلوم نبود."""
    limited = _cgroup_memory_available_mb()
    if limited is not None:
        return limited
    try:
        with open("/proc/meminfo", encoding="utf-8") as f:
            for line in f:
                if line.startswith("MemAvailable:"):
                    return int(line.split()[1]) // 1024
    except Exception:
        pass
    # ru_maxrss حافظه‌ی مصرف‌شده را می‌دهد، نه حافظه‌ی آزاد؛ برای تصمیمِ OOM
    # استفاده از آن اشتباه است، پس اگر meminfo/cgroup نبود عددِ جعلی نمی‌دهیم.
    return None

# سلف فقط 95.py است - 77/78 پاک میشوند
SELF_NAMES = ("95.py",)
# فقط «نام» فایل — برای ساختن مسیر داخل پوشه‌ی مشتری. هیچ‌وقت SELFBOT کامل
# (مسیر absolute) را داخل os.path.join با پوشه نده، چون join مسیر اول را دور
# می‌ریزد و فایل سلفِ مشترک با فایل مشتری یکی می‌شود.
SELF_NAME = SELF_NAMES[0]
# نسخه‌ی مرجع سلف بیرون از پوشه‌ی اجرا (توی ایمیج داکر ساخته می‌شود).
# اگر 95.py کنار manager پاک یا خراب شد، سلف از همین نسخه بازسازی می‌شود.
SELFBOT_REF = os.environ.get("JAFJ_SELFBOT_REF", "/opt/jafj/95.py")
JUNK_SELF = (
    "jafj_self.py", "jafj_self", "self.py", "سلف.py",
    "جفج سلف.py", "جفج_سلف.py", "jafj_manager.py",
    "2.0-self.py", "2_old.py", "2.py.bak", "2.py.old",
    "78.py", "77.py",
)
SELF_MARK = "جــفــج 3.0"


SHARED_PREFIXES = ("/storage/emulated", "/sdcard", "/storage/self",
                   "/mnt/sdcard", "/storage/")


def fix_workdir():
    """اندروید روی حافظه مشترک اجازه قفل SQLite نمی‌دهد.
    اگر آنجا اجرا شده باشیم، به پوشه‌ی امن خانگی کوچ می‌کنیم."""
    cwd = os.path.abspath(os.getcwd())
    if not cwd.startswith(SHARED_PREFIXES):
        return None
    home = os.path.expanduser("~")
    if home.startswith(SHARED_PREFIXES) or not os.path.isdir(home):
        return None
    target = os.path.join(home, "jafj")
    os.makedirs(target, exist_ok=True)

    import shutil
    moved = []
    # خود اسکریپت هم برود تا دفعه بعد از همان‌جا اجرا شود
    try:
        me = os.path.abspath(sys.argv[0])
        if os.path.isfile(me):
            dst_me = os.path.join(target, os.path.basename(me))
            if os.path.abspath(dst_me) != me:
                shutil.copy2(me, dst_me)
                moved.append(os.path.basename(me))
    except Exception:
        pass
    # سلف باید هر بار از نسخه‌ی جدید کنار manager_82.py همگام شود؛
    # قبلاً اگر نسخه‌ی قدیمی در ~/jafj وجود داشت، همان نسخه دوباره اجرا می‌شد.
    try:
        import filecmp
        for n in SELF_NAMES:
            src = os.path.join(cwd, n)
            dst = os.path.join(target, n)
            same = (os.path.isfile(src) and os.path.isfile(dst)
                    and filecmp.cmp(src, dst, shallow=False))
            if os.path.isfile(src) and not same:
                shutil.copy2(src, dst)
                moved.append(n + " (به‌روز شد)")
    except Exception:
        pass

    # تنظیمات و دیتابیس‌های موجود را فقط اگر مقصد ندارد ببر؛
    # تا اطلاعات ذخیره‌شده‌ی داخل پوشه‌ی امن از بین نرود.
    for n in [CONFIG_FILE, DB_FILE, "shop.db", "jafj_ai.json"]:
        src = os.path.join(cwd, n)
        dst = os.path.join(target, n)
        if os.path.exists(src) and not os.path.exists(dst):
            try:
                shutil.copy2(src, dst)
                moved.append(n)
            except Exception:
                pass
    os.chdir(target)
    print("\n" + "═" * 54)
    print("  ⚠️  حافظه‌ی مشترک اندروید برای دیتابیس مناسب نیست")
    print("═" * 54)
    print(f"  از:  {cwd}")
    print(f"  به:  {target}")
    if moved:
        print(f"  کپی شد: {'، '.join(moved)}")
    print()
    print("  دفعه‌ی بعد مستقیم از همان‌جا اجرا کن:")
    print(f"    cd {target} && python manager_82.py")
    print("═" * 54 + "\n", flush=True)
    return target


LOCK_FILE = "bot.lock"


def pid_alive(pid):
    try:
        os.kill(pid, 0)
        return True
    except (OSError, ProcessLookupError):
        return False
    except PermissionError:
        return True


def pid_is_manager(pid):
    """آیا این PID واقعاً یک manager_82 در حال اجراست؟

    True/False = مطمئنیم، None = نمی‌شود فهمید (غیر لینوکس).

    چرا لازم است: bot.lock کنار داده‌ها می‌ماند و روی Railway یعنی داخل
    Volume. بعد از هر دیپلوی، PID قدیمیِ داخل فایل به PID زنده‌ی دیگری در
    کانتینر جدید می‌خورد (پروسه‌ی سلف، خود shell و…)؛ نتیجه‌اش این بود که
    manager با «یک نسخه در حال اجراست» exit 1 می‌کرد و Railway هم پشت‌سرهم
    ری‌استارت می‌شد — همان کرش‌لوپ.
    """
    try:
        with open(f"/proc/{int(pid)}/cmdline", "rb") as f:
            cmd = f.read().replace(b"\x00", b" ").decode("utf-8", "ignore")
    except Exception:
        return None
    return "manager_82" in cmd


def acquire_lock():
    """جلوگیری از اجرای همزمان دو نسخه. (موفق, پیام)"""
    try:
        if os.path.exists(LOCK_FILE):
            try:
                old = int(open(LOCK_FILE).read().strip() or 0)
            except Exception:
                old = 0
            # قفل فقط وقتی معتبر است که آن PID هم زنده باشد و هم واقعاً
            # manager باشد؛ وگرنه قفلِ مانده از دیپلوی قبلی است.
            if (old and old != os.getpid() and pid_alive(old)
                    and pid_is_manager(old) is not False):
                return False, old
            os.remove(LOCK_FILE)          # قفل مرده
        with open(LOCK_FILE, "w") as f:
            f.write(str(os.getpid()))
        return True, os.getpid()
    except Exception:
        return True, os.getpid()          # اگر نشد، مانع اجرا نشو


def release_lock():
    try:
        if os.path.exists(LOCK_FILE):
            if open(LOCK_FILE).read().strip() == str(os.getpid()):
                os.remove(LOCK_FILE)
    except Exception:
        pass


def selfbot_version(path):
    try:
        chunk = open(path, encoding="utf-8", errors="ignore").read()
    except Exception:
        return ""
    m = re.search(r'VERSION\s*=\s*["\']([^"\']+)["\']', chunk)
    return (m.group(1) if m else "").strip()


def purge_old_selfbots(root="."):
    """هر فایل جفج‌سلف / jafj_self / self.py را پاک می‌کند."""
    gone = []
    for dirpath, _dirs, files in os.walk(root):
        if any(x in dirpath for x in (".git", "__pycache__", ".venv")):
            continue
        for fn in files:
            low = fn.lower()
            if fn in JUNK_SELF or low in {x.lower() for x in JUNK_SELF} \
                    or "jafj_self" in low or fn in ("جفج سلف.py",):
                p = os.path.join(dirpath, fn)
                try:
                    os.remove(p)
                    gone.append(p)
                except Exception:
                    pass
    return gone


def selfbot_search_dirs():
    """پوشه‌هایی که 95.py می‌تواند داخلشان باشد (بدون تکرار)."""
    try:
        script_dir = os.path.dirname(os.path.abspath(sys.argv[0]))
    except Exception:
        script_dir = ""
    out, seen = [], set()
    for d in (script_dir, os.getcwd(), os.path.abspath(BASE_DIR), "/app"):
        if d and d not in seen and os.path.isdir(d):
            seen.add(d)
            out.append(d)
    if not out:
        out = [os.path.abspath(BASE_DIR)]
    return out


def _restore_selfbot(dst):
    """95.py را از نسخه مرجع ایمیج بازمی‌گرداند. True اگر موفق بود."""
    ref = SELFBOT_REF
    if not ref or not os.path.isfile(ref):
        return False
    try:
        with open(ref, "rb") as f:
            data = f.read()
        if not data or os.path.abspath(ref) == os.path.abspath(dst):
            return False
        # symlink حلقه‌ای/خراب قبلی مانع نوشتن نمی‌شد، اول پاکش کن
        if os.path.lexists(dst) and not os.path.isfile(dst):
            try:
                os.remove(dst)
            except Exception:
                return False
        with open(dst, "wb") as f:
            f.write(data)
        print(f"  ♻️ فایل سلف از نسخه مرجع بازسازی شد: {dst}", flush=True)
        return True
    except Exception as e:
        print("restore selfbot:", e, flush=True)
        return False


def ensure_selfbot_ref(src=None):
    """یک نسخه سالم از سلف در مسیر مرجع نگه می‌دارد تا اگر نسخه‌ی اجرا
    پاک یا خراب شد، سلف قابل بازسازی باشد (فایل ایمیج /opt/jafj)."""
    try:
        src = os.path.abspath(src or SELFBOT)
        ref = os.path.abspath(SELFBOT_REF)
        if src == ref or not os.path.isfile(src):
            return False
        if os.path.isfile(ref):
            if os.path.getsize(ref) == os.path.getsize(src):
                return False
            # نسخه‌ی مرجعِ تازه‌تر هرگز با فایل قدیمیِ پوشه‌ی اجرا بازنویسی
            # نمی‌شود؛ وگرنه یک Volume کهنه، تنها نسخه‌ی سالم را هم خراب می‌کند.
            try:
                if os.path.getmtime(ref) > os.path.getmtime(src):
                    return False
            except Exception:
                pass
        d = os.path.dirname(ref)
        if not os.path.isdir(d):
            os.makedirs(d, exist_ok=True)
        with open(src, "rb") as f:
            data = f.read()
        tmp = ref + ".tmp"
        with open(tmp, "wb") as f:
            f.write(data)
        os.replace(tmp, ref)
        return True
    except Exception:
        return False      # /opt روی بعضی سیستم‌ها نوشتنی نیست — اشکالی ندارد


def find_selfbot():
    """سلف فقط 95.py است؛ همیشه مسیر کامل (absolute) برمی‌گرداند.

    دو باگ قدیمی اینجا رفع شد:
      ۱) مسیر نسبی برمی‌گشت، پس با هر cwd دیگری «95.py پیدا نشد» می‌داد.
      ۲) فایل پاک‌شده یا symlink حلقه‌ای به‌جای 95.py، مرور بعدی را هم
         می‌سوزاند؛ حالا از نسخه مرجع (/opt/jafj) بازسازی می‌شود.
    """
    for d in selfbot_search_dirs():
        for cand in SELF_NAMES + ("95",):
            p = os.path.join(d, cand)
            if os.path.isfile(p):
                return p
    # هیچ نسخه سالمی نبود → از نسخه مرجع بازسازی کن
    for d in selfbot_search_dirs():
        for cand in SELF_NAMES:
            p = os.path.join(d, cand)
            if _restore_selfbot(p):
                return p
    # هیچ‌کدام نبود — مسیر پیش‌فرض کنار اسکریپت (پیام خطا دقیق بماند)
    return os.path.join(selfbot_search_dirs()[0], SELF_NAME)


def ensure_selfbot_current(path=None):
    """اگر نسخه‌ی مرجعِ ایمیج تازه‌تر از نسخه‌ی اجراست، نسخه‌ی اجرا را از آن
    به‌روز کن. True یعنی فایل عوض شد.

    این لایه‌ی دومِ دفاع است: railway-start.sh همین کار را قبل از بوت می‌کند،
    ولی اگر کسی manager را مستقیم اجرا کند (start command دستی) یا سلف بعد از
    بوت خراب شود، اینجا نسخه‌ی سالم ایمیج جایگزین می‌شود.
    """
    try:
        path = os.path.abspath(path or SELFBOT)
        ref = os.path.abspath(SELFBOT_REF)
        if path == ref or not os.path.isfile(ref):
            return False
        if not os.path.isfile(path):
            return _restore_selfbot(path)
        try:
            if os.path.getmtime(ref) <= os.path.getmtime(path):
                return False        # نسخه‌ی اجرا قدیمی نیست — دست نمی‌زنیم
        except Exception:
            return False
        with open(ref, "rb") as f:
            fresh = f.read()
        with open(path, "rb") as f:
            current = f.read()
        if not fresh or fresh == current:
            return False
        tmp = path + ".incoming"
        with open(tmp, "wb") as f:
            f.write(fresh)
        os.replace(tmp, path)       # جای symlink خراب/حلقه‌ای را هم می‌گیرد
        print(f"  ♻️ سلف از نسخه‌ی ایمیج به‌روز شد: {path}", flush=True)
        return True
    except Exception as e:
        print("refresh selfbot:", e, flush=True)
        return False


def image_dir():
    """پوشه‌ی غیرقابل‌تغییر ایمیج (جایی که railway-start.sh کد را از آن اجرا
    می‌کند). روی ترموکس/اجرای دستی معمولاً وجود ندارد."""
    return os.environ.get("JAFJ_IMAGE_DIR") \
        or os.path.dirname(os.path.abspath(SELFBOT_REF))


def ensure_fresh_code():
    """اگر نسخه‌ی دیگری از manager_82.py اجرا شده و نسخه‌ی ایمیج فرق دارد،
    خودمان را از روی نسخه‌ی ایمیج دوباره exec می‌کنیم.

    دلیلش: روی Railway اگر Volume روی /app باشد یا start command دستی روی
    «python manager_82.py» تنظیم شده باشد، کد قدیمی اجرا می‌شود و هر دیپلوی
    بی‌اثر می‌ماند (همان «فایل 95.py پیدا نشد» همیشگی).
    """
    try:
        if os.environ.get("JAFJ_REEXEC_GUARD"):
            return False                       # جلوی حلقه‌ی exec بی‌پایان
        mine = os.path.abspath(sys.argv[0] or __file__)
        fresh = os.path.join(image_dir(), "manager_82.py")
        if not os.path.isfile(fresh) or os.path.abspath(fresh) == mine:
            return False
        if not os.path.isfile(mine):
            return False
        with open(mine, "rb") as f:
            a = f.read()
        with open(fresh, "rb") as f:
            b = f.read()
        if a == b:
            return False
        print(f"  ♻️ کد قدیمی اجرا شده بود ({mine}) — از نسخه‌ی ایمیج "
              f"({fresh}) دوباره اجرا می‌شود", flush=True)
        os.environ["JAFJ_REEXEC_GUARD"] = "1"
        os.execv(sys.executable, [sys.executable, fresh] + sys.argv[1:])
    except Exception as e:
        print("ensure_fresh_code:", e, flush=True)
    return False


SELFBOT = find_selfbot()

# ── تنظیمات مستقیم داخل همین فایل Python ──
# توکن تازه در BotFather صادر شده (توکن قبلی Revoke شد تا سرویس زامبیِ
# حساب Railway قدیمی که دسترسی‌اش از دست رفته، کور شود).
BOT_TOKEN = "8832561144:AAFSRpyaD4M9GWWsiltBMXs6acbbo6W0J-M"
API_ID = 28039994
API_HASH = "00877cdcd706564a4de6abf7f7d64349"
ADMIN_IDS = [8287266200]
BUILD_VERSION = "v1028-nocode"
# کدام کامیتِ گیت دارد اجرا می‌شود؟ (اول JAFJ_COMMIT که هاست/اسکریپتِ بوت
# می‌تواند بدهد، بعد تلاشِ محلی برای git — داخلِ ایمیج معمولاً .git نیست)
GIT_COMMIT = ""
for _k in ("JAFJ_COMMIT", "RENDER_GIT_COMMIT", "RAILWAY_GIT_COMMIT",
           "HEROKU_SLUG_COMMIT", "SOURCE_COMMIT"):
    GIT_COMMIT = (os.environ.get(_k) or "").strip()[:12]
    if GIT_COMMIT:
        break
if not GIT_COMMIT:
    try:
        import subprocess as _sp
        GIT_COMMIT = _sp.run(["git", "rev-parse", "--short", "HEAD"],
                             cwd=os.path.dirname(os.path.abspath(__file__)),
                             capture_output=True, text=True,
                             timeout=5).stdout.strip()[:12]
    except Exception:
        GIT_COMMIT = ""
if not GIT_COMMIT:
    GIT_COMMIT = "?"
_BOOT_TIME_STRUCT = time.localtime()

def code_fingerprint(path=None):
    """اثرانگشتِ کوتاهِ کدی که <b>واقعاً</b> اجرا می‌شود.

    چرا: بعد از دیپلوی، سؤال این است «رسید یا نه؟». کامیتِ گیت فقط وقتی هست
    که میزبان متغیرش را بدهد یا .git داخلِ ایمیج باشد؛ ولی محتوای فایل‌ها
    همیشه هست. پس هشِ manager_82.py و 95.py را می‌گیریم: با <b>هر</b> تغییرِ
    کد عوض می‌شود و اگر دیپلوی بی‌اثر مانده باشد (ایمیجِ قدیمی، یا دیسکی که
    روی مسیرِ کد مانت شده) همان مقدارِ قبلی می‌ماند.
    """
    import hashlib
    d = path or image_dir()
    h = hashlib.sha256()
    for name in ("manager_82.py", "95.py"):
        fp = os.path.join(d, name)
        try:
            with open(fp, "rb") as f:
                h.update(f.read())
        except OSError:
            h.update(b"<missing:%s>" % name.encode())
    return h.hexdigest()[:8]


# اگر اسکریپتِ بوت خودش اثرانگشت را حساب کرده باشد، همان را نشان می‌دهیم تا
# لاگ و /version و پنلِ تلگرام یک عدد را بگویند.
CODE_ID = (os.environ.get("JAFJ_CODE_ID") or "").strip()[:12] \
    or code_fingerprint()
MANAGER_PATH = os.path.abspath(__file__)
_BOOT_AT = time.time()


def uptime_text():
    """چقدر است که این نسخه بالا آمده (برای «آیا دیپلوی شد؟»)."""
    secs = max(0, int(time.time() - _BOOT_AT))
    d, rem = divmod(secs, 86400)
    hrs, rem = divmod(rem, 3600)
    mins = rem // 60
    parts = []
    if d:
        parts.append(f"{d} روز")
    if hrs:
        parts.append(f"{hrs} ساعت")
    parts.append(f"{mins} دقیقه")
    return " و ".join(parts)
CODE_IS_STALE = (os.path.dirname(MANAGER_PATH) != os.path.abspath(image_dir()))
BUILD_TAG = "JAFJ_MANAGER_82_v1028-nocode_2026_10_28"

# ═══════════════════════════════════════════════════════════════════════════
#  شناسه‌ی نمونه (instance) + تشخیص «سرویس قدیمی هنوز روشنه»
#
#  وقتی روی Railway دو سرویس/دو دیپلویِ همین ربات هم‌زمان بالا باشند، تلگرام
#  آپدیت‌ها را بین هر دو کانکشن پخش می‌کند: دکمه‌ی «روشن کن» یک‌بار به نسخه‌ی
#  جدید می‌رسد (که سالم است) و بار دیگر به سرویس قدیمی که 95.py داخل ایمیجش
#  نیست و «فایل 95.py پیدا نشد» می‌دهد. ریشه‌ی آن باگ و باگ «ریل‌وی قدیمی
#  هنوز روشنه» یکی است. این بخش با یک «ضربان» (beacon) در چت مدیر، نمونه‌های
#  هم‌زمان را پیدا می‌کند و هشدار واضح می‌دهد.
# ═══════════════════════════════════════════════════════════════════════════

# تصادفی برای هر پروسه — هر ری‌استارت عوض می‌شود.
INSTANCE_ID = os.environ.get("JAFJ_INSTANCE_ID", "").strip() or "".join(
    random.choice("0123456789abcdef") for _ in range(4))
# ثابت تا وقتی داده‌ها (Volume) یکی است — یعنی همان سرویس/دیپلوی.
DEPLOY_ID = ""


def _load_deploy_id():
    """شناسه‌ی پایدار این سرویس؛ داخل داده‌ها ذخیره می‌شود تا ری‌استارت عوضش
    نکند ولی دو سرویس جدا (با Volume/داده‌ی جدا) شناسه‌ی متفاوت داشته باشند."""
    global DEPLOY_ID
    try:
        path = os.path.join(os.path.abspath(BASE_DIR), ".jafj_deploy_id")
        did = ""
        try:
            with open(path, encoding="utf-8") as f:
                did = f.read().strip()
        except Exception:
            did = ""
        if not did or not re.fullmatch(r"[0-9a-f]{6,16}", did):
            did = "".join(random.choice("0123456789abcdef") for _ in range(8))
            try:
                with open(path, "w", encoding="utf-8") as f:
                    f.write(did)
            except Exception:
                pass
        DEPLOY_ID = did
    except Exception:
        DEPLOY_ID = "".join(random.choice("0123456789abcdef") for _ in range(8))


_load_deploy_id()


def host_label():
    """برچسب کوتاه محل اجرا (blitz / railway-us-east / local / …) برای پیام‌ها."""
    # برچسبِ دستی همیشه اولویت دارد (VPS/blitz نامِ env نمی‌گذارند).
    manual = (os.environ.get("JAFJ_HOST_LABEL") or "").strip()
    if manual:
        return re.sub(r"\s+", "-", manual)[:24]
    for key in ("BLITZ_APP_NAME", "BLITZ_APP_ID",
                "HOSTLESS_APP_NAME", "HOSTLESS_APP_ID", "HOSTLESS_PROJECT",
                "RAILWAY_SERVICE_NAME", "RAILWAY_SERVICE_ID",
                "FLY_APP_NAME", "KOYEB_APP_NAME", "HEROKU_APP_NAME",
                "RENDER_SERVICE_NAME"):
        v = (os.environ.get(key) or "").strip()
        # "1"/"true" یعنی فقط «روی بلایتز هستیم»، نه نامِ اپ.
        if v and v.lower() not in ("1", "true", "yes", "on"):
            return re.sub(r"\s+", "-", v)[:24]
    if (os.environ.get("BLITZ") or "").strip():
        return "blitz"
    try:
        import socket
        return "host-" + (socket.gethostname() or "local")[:12]
    except Exception:
        return "local"


HOST_LABEL = host_label()
BEACON_TAG = "#JAFJBEACON"


def beacon_text():
    """متن ضربانِ همین نمونه (هر ~۶۰ ثانیه edit می‌شود)."""
    return (f"{BEACON_TAG} <code>i={INSTANCE_ID}</code> <code>d={DEPLOY_ID}</code> "
            f"<code>b={BUILD_VERSION}</code> <code>h={HOST_LABEL}</code> "
            f"<code>t={int(time.time())}</code>")


# تگ‌های <code>…</code> که دور فیلدها پیچیده شده‌اند نباید مچ را خراب کنند؛
# بین فیلدها هر ترکیبی از فاصله/تگ مجاز است.
_BEACON_RE = re.compile(
    r"#JAFJBEACON(?:\s|</?[a-z]+>)+"
    r"i=(?P<inst>[0-9a-z]{2,16})(?:\s|</?[a-z]+>)+"
    r"d=(?P<dep>[0-9a-f]{6,16})(?:\s|</?[a-z]+>)+"
    r"b=(?P<build>[0-9A-Za-z._\-]{1,40})(?:\s|</?[a-z]+>)+"
    r"h=(?P<host>[0-9A-Za-z._\-]{1,40})(?:\s|</?[a-z]+>)+"
    r"t=(?P<ts>\d{6,12})")


def parse_beacon(text):
    """متن پیام را می‌خواند؛ اگر ضربان جفج باشد دیکشنری شناسه برمی‌گرداند."""
    if not text:
        return None
    m = _BEACON_RE.search(str(text))
    if not m:
        return None
    d = m.groupdict()
    try:
        d["ts"] = int(d["ts"])
    except Exception:
        d["ts"] = 0
    return d


def scan_beacons(messages, my_deploy=None, window_sec=170, now_ts=None):
    """از میان پیام‌های اخیرِ چت، ضربانِ زنده را جدا می‌کند.

    ورودی: لیستی از دیکشنری {"text", "edit_ts" (آخرین ویرایش/ارسال، ثانیه)}.
    خروجی: (mine, foreign) — mine = ضربان همین نمونه (dep یکسان)،
    foreign = ضربان زنده‌ی نمونه‌های دیگر (dep متفاوت و تازه‌تر از window).
    خالص است تا بدون تلگرام قابل تست باشد.
    """
    my_deploy = my_deploy or DEPLOY_ID
    now_ts = int(now_ts if now_ts is not None else time.time())
    mine, foreign = [], []
    for msg in messages:
        b = parse_beacon(msg.get("text"))
        if not b:
            continue
        age = now_ts - int(msg.get("edit_ts") or b.get("ts") or 0)
        if age > window_sec:
            continue          # ضربانِ خاموش/قدیمی — مرده فرض می‌شود
        if b["dep"] == my_deploy:
            mine.append(b)
        else:
            foreign.append(b)
    return mine, foreign


def count_legacy_foreign(msgs, bot_id, sent_ids, live_ids, boot_at,
                         window_sec=170, now_ts=None):
    """پیام‌هایِ نسخه‌ی زامبیِ قدیمی (که ضربان ندارد) را می‌شمارد.

    «بیگانه» یعنی: فرستنده خودِ ربات است ولی این نمونه نفرستاده/ویرایشش نکرده،
    متن دارد، تازه است (در window_sec ثانیه‌ی اخیر) و مربوط به قبل از بوت این
    نمونه نیست. خالص است تا بدون تلگرام تست شود.

    ورودی msgs: لیستی از دیکشنری {"id", "sender_id", "text", "ts" (epoch)}
    """
    now_ts = int(now_ts if now_ts is not None else time.time())
    sent_ids = set(sent_ids or ())
    live_ids = set(live_ids or ())
    hits = 0
    for m in msgs:
        try:
            if not bot_id or int(m.get("sender_id", 0)) != bot_id:
                continue
            txt = (m.get("text") or "").strip()
            if not txt or parse_beacon(txt):
                continue
            mts = int(m.get("ts", 0))
            if now_ts - mts > window_sec:
                continue
            if mts < int(boot_at) - 5:
                continue
            if m.get("id") in sent_ids or m.get("id") in live_ids:
                continue
            hits += 1
        except Exception:
            continue
    return hits


def _self_sync_failure_hint(sync_err):
    """وقتی سلف بالا نمی‌آید، در محیط میزبان محتمل‌ترین علت را بگو."""
    if is_hosted():
        return ("\n\n<b>🔸 روی Railway هستی؟ این خطا یعنی همین سرویس نسخه‌ی "
                "قدیمی است.</b>\n"
                "۱) در داشبورد Railway این سرویس را Remove/Redeploy کن و "
                "مطمئن شو فقط یک سرویس از این ربات روشن است.\n"
                "۲) دو سرویسِ هم‌زمان با یک توکن، آپدیت‌ها را نصف‌ونیمه "
                "می‌گیرند؛ سرویس قدیمی را خاموش کن.")
    return ""


# ── نشست ذخیره‌شده ربات مدیر (جلوگیری از ImportBotAuthorization در هر بوت) ──
BOT_SESSION_FILE = os.path.join(BASE_DIR, "manager_bot.string")
# ── پشتیبان خودکار روی تلگرام ──
BACKUP_TAG = "JAFJBACKUP1"


def build_stamp():
    """مُهر نسخه برای پایین پیام‌ها (تشخیص از روی اسکرین‌شات)."""
    try:
        s = globals().get("SELFBOT") or ""
        bn = os.path.basename(s) if s else "?"
        dn = os.path.dirname(s) if s else "?"
        return (f"build {BUILD_VERSION} · self {bn} در {dn} · cwd {os.getcwd()}"
                f" · code {os.path.dirname(os.path.abspath(sys.argv[0] or __file__))}")
    except Exception:
        return f"build {BUILD_VERSION}"


HOSTED_ENV_KEYS = ("RAILWAY_ENVIRONMENT", "RAILWAY_SERVICE_ID", "RAILWAY_PROJECT_ID",
                   "RENDER", "RENDER_SERVICE_NAME", "RENDER_SERVICE_ID",
                   "BLITZ", "BLITZ_APP_NAME", "BLITZ_APP_ID",
                   "HOSTLESS", "HOSTLESS_APP_NAME", "HOSTLESS_APP_ID",
                   "FLY_APP_NAME", "HEROKU_APP_NAME", "KOYEB_APP_NAME")


def is_hosted():
    """روی سرویس میزبان (Railway و…) هستیم؟

    آنجا exit کردن پروسه = ری‌استارت کامل کانتینر؛ پس خطای موقتی مثل
    FloodWait نباید پروسه را بمیراند، وگرنه کرش‌لوپ می‌شود.
    """
    if any((os.environ.get(k) or "").strip() for k in HOSTED_ENV_KEYS):
        return True
    return (os.environ.get("JAFJ_HOSTED") or "").strip().lower() in ("1", "true", "yes", "on")


def login_retry_forever():
    """آیا بعد از شکست ورود، به‌جای exit کردن به تلاش ادامه بدهیم؟"""
    raw = (os.environ.get("JAFJ_LOGIN_RETRY") or "").strip().lower()
    if raw in ("off", "0", "no", "false", "exit"):
        return False
    if raw in ("forever", "always", "1", "true", "yes", "on"):
        return True
    return is_hosted()      # پیش‌فرض: روی Railway زنده بمان، روی ترموکس exit کن


def login_retry_wait(round_no, base=20, cap=300):
    """فاصله‌ی بین تلاش‌های ورود: ۲۰، ۴۰، ۶۰ … تا سقف ۳۰۰ ثانیه."""
    try:
        n = max(1, int(round_no))
    except Exception:
        n = 1
    return max(5, min(base * n, cap))


def reconnect_limit():
    """چند بار بعد از قطع‌شدنِ اتصال، در همین پروسه دوباره وصل شویم؟ (۰ = بی‌نهایت)

    چرا محدود: اتصالِ دوباره با «همان نمونهٔ کلاینت» انجام می‌شود تا هندلرها
    گم نشوند. اگر نشست واقعاً مرده باشد (توکن عوض شده، AuthKey باطل) این
    تلاش‌ها هیچ‌وقت جواب نمی‌دهند؛ آن‌وقت بهتر است پروسه با کدِ غیرصفر خارج
    شود تا ناظر (railway-start.sh) آن را از صفر و با هندلرهای تازه بالا
    بیاورد — و اگر تکرار شد، میزبان خطا را ببیند، نه «Exit code 0».
    مقدارِ صریح با JAFJ_RECONNECT_TRIES قابل تغییر است (inf = بی‌نهایت).
    """
    raw = (os.environ.get("JAFJ_RECONNECT_TRIES") or "").strip().lower()
    if raw in ("inf", "forever", "always", "unlimited", "-1"):
        return 0
    try:
        if raw:
            return max(0, int(raw))
    except Exception:
        pass
    return 3


# خطاهایی که یعنی «توکن مرده/باطل‌شده» است، نه مشکل شبکه. در این حالت به‌جای
# حلقه‌ی انتظار روی همان توکن، سراغ توکن بعدی (هاردکد داخل ایمیج) می‌رویم — این
# همان شفای خودکار بعد از Revoke در BotFather است.
_DEAD_TOKEN_MARKS = (
    "unauthorized", "auth key", "authkey", "revoked", "invalid",
    "token", "deactivated", "forbidden", "bot was", "banned")


def is_dead_token_error(exc):
    """True یعنی توکن فعلی معتبر نیست (b/Revoke شده) و باید عوضش کرد."""
    try:
        msg = f"{type(exc).__name__} {exc}".lower()
    except Exception:
        return False
    return any(k in msg for k in _DEAD_TOKEN_MARKS)


def _truthy_env(*keys):
    for k in keys:
        if (os.environ.get(k) or "").strip().lower() in ("1", "true", "yes", "on"):
            return True
    return False


def host_may_sleep():
    """آیا میزبان ممکن است با بی‌کاری بخوابد؟ (پلنِ رایگانِ blitz.cloud / Render)

    روی چنین میزبانی، دیرشدنِ پشتیبان یعنی بیدارشدن با دادهٔ قدیمی‌تر — پس
    فاصلهٔ پیش‌فرضِ پشتیبان کوتاه می‌شود. با JAFJ_APP_SLEEPS=0 می‌شود خاموشش
    کرد (مثلاً روی VPS یا پلنِ always-on که هرگز نمی‌خوابد).
    """
    raw = (os.environ.get("JAFJ_APP_SLEEPS") or "").strip().lower()
    if raw in ("0", "no", "false", "off"):
        return False
    if raw in ("1", "true", "yes", "on"):
        return True
    return _truthy_env("RENDER")


def backup_interval():
    """فاصله پشتیبان خودکار (ثانیه): BACKUP_EVERY خودت را تعیین می‌کند، حداقل ۱۲۰.

    روی Render رایگان و پلن رایگانِ blitz.cloud (که برنامه را با ۳۰ دقیقه
    بی‌بازدید خواب می‌کند؛ با JAFJ_APP_SLEEPS=1) دیسک ماندگاری وجود
    ندارد و محتوای /data با هر دیپلوی (مثلاً هر push به گیت‌هاب) و هر
    ری‌استارت/خواب پاک می‌شود. برای همین پیش‌فرض را در Render از ۹۰۰ به ۱۲۰
    ثانیه می‌آوریم تا پیش از دیپلوی بعدی نهایتاً ۲ دقیقهٔ آخرِ داده از دست
    برود، نه کل آن. مقدار صریح BACKUP_EVERY همیشه بر پیش‌فرض اولویت دارد."""
    v = 900
    try:
        v = int((os.environ.get("BACKUP_EVERY") or "").strip() or "900")
    except Exception:
        v = 900
    if not (os.environ.get("BACKUP_EVERY") or "").strip() and host_may_sleep():
        v = 120
    return max(120, v)


def backup_target_raw():
    raw = (os.environ.get("BACKUP_CHAT") or "").strip()
    if raw:
        return raw
    # اگر BACKUP_CHAT تنظیم نشده باشد، طبق روال قبلی به «admin» برمی‌گردیم:
    # یعنی چت خصوصی اولین مدیر (admin_ids). به این ترتیب بکاپِ خودکار حتی بدون
    # هیچ تنظیمِ دستی هم روشن می‌شود و داده‌ها بعد از هر آپدیت کد/ری‌استارت
    # قابل بازیابی‌اند. اگر مقصد دیگری می‌خواهی، BACKUP_CHAT را صریح ست کن
    # (پذیرنده است: admin / آیدی عددی / @username).
    return "admin"


# سقف آپلودِ ربات تلگرام ۵۰ مگابایت است. اگر zip از این بزرگ‌تر شود send_file
# رد می‌شود و در لاگ می‌ماند — مدیر هیچ فایلی نمی‌بیند و بعد از دیپلوی
# «پشتیبانی پیدا نشد». کمی پایین‌تر می‌مانیم.
BOT_BACKUP_MAX_BYTES = 45 * 1024 * 1024

# این‌ها داده نیستند: لاگِ سلف بی‌حد رشد می‌کند و همان باعث رد شدنِ آپلود است.
_BACKUP_SKIP_SUFFIXES = (
    ".log", "-wal", "-shm", "-journal", ".restore_tmp",
    ".tmp", ".bad", ".bak",
)
_BACKUP_SKIP_NAMES = {"run.log", "95.py", "jafj_self.py", "jafj_status.json"}
_BACKUP_ESSENTIAL = {
    "manager.db", "shop.db", "manager_config.json", "manager_bot.string",
    "jafj_ai.json", ".jafj_deploy_id",
    "jafj.session", "jafj_settings.json", "jafj_creds.json", "jafj_limits.json",
}
_CMD_ALIASES = {
    "backup": "backup",
    "restore": "restore",
    "rules": "rules",
    "بکاپ": "backup",
    "بکآپ": "backup",
    "یکاپ": "backup",
    "یکآپ": "backup",
    "پشتیبان": "backup",
    "بازیابی": "restore",
    "قوانین": "rules",
}


def backup_file_skipped(name):
    """فایل‌هایی که نباید داخل zip/اثرانگشتِ پشتیبان بروند."""
    base = os.path.basename(name or "")
    low = base.lower()
    if low in _BACKUP_SKIP_NAMES:
        return True
    if ".bak-" in low:
        return True
    return low.endswith(_BACKUP_SKIP_SUFFIXES)


def backup_arc_essential(arc):
    return os.path.basename(arc or "") in _BACKUP_ESSENTIAL


def _admin_upload_path():
    """zip پشتیبانی که مدیر مستقیم در پیوی بات فرستاده (یک‌بار مصرف)."""
    return os.path.join(BASE_DIR, "jafj_admin_upload.zip")


def _backup_clients_count(caption):
    """تعداد مشتری‌ای که در کپشن پشتیبان نوشته شده (clients=N). نامعلوم → None."""
    m = re.search(r"clients=(\d+)", str(caption or ""))
    return int(m.group(1)) if m else None


def parse_restore_ref(text, reply_id=None):
    """ارجاعِ پیامِ پشتیبان را از متنِ مدیر بیرون بکشد → (چت, آیدی پیام).

    سه شکل پذیرفته می‌شود (همه بدون نیاز به هیچ فایلی روی دیسک):

        .restore            → (None, None)  یعنی «آخرین پشتیبانِ شناخته‌شده»
        .restore 12345      → (None, 12345) یعنی پیامِ شمارهٔ ۱۲۳۴۵ در چتِ پشتیبان
        .restore https://t.me/c/123456789/45
                            → (-100123456789, 45) از روی لینک
        (ریپلای روی همان پیام و نوشتنِ `.restore`) → (None, reply_id)

    چرا لازم است؟ رباتِ تلگرام `messages.getHistory` ندارد؛ اگر دیسک پاک شود
    هیچ راهی برای «گشتن» در پیام‌ها نمی‌ماند. ولی `getMessages` با آیدیِ
    مشخص کار می‌کند — و این آیدی را خودِ مدیر با ریپلای/لینک می‌دهد.
    """
    t = (text or "").strip()
    if t:
        tok = t.split()[0].strip("<>")
        m = re.search(r"(?:https?://)?t\.me/(?:c/)?([A-Za-z0-9_+\-]+)/(\d+)/?", tok)
        if m:
            chat, mid = m.group(1), int(m.group(2))
            # t.me/c/<internal_id>/<msg> → آیدیِ داخلیِ کانال/گروه
            if "/c/" in tok:
                try:
                    return int("-100" + str(int(chat))), mid
                except Exception:
                    return None, mid
            return chat, mid
        if re.fullmatch(r"\d{1,12}", tok):
            return None, int(tok)
        m2 = re.fullmatch(r"(?:msg|message)?[:#]?(\d{1,12})", tok, re.I)
        if m2:
            return None, int(m2.group(1))
    try:
        rid = int(reply_id) if reply_id else 0
    except Exception:
        rid = 0
    return None, (rid or None)


def command_text(text):
    """`.backup` / `.restore` و شکلِ فارسیِ تک‌کلمه‌ای را به دستور اسلش تبدیل می‌کند.

    پیامِ خطای بازیابی می‌گوید `.restore` بفرست، ولی هندلر فقط `/` را می‌فهمید
    و جوابش «/help را بزن» بود — یعنی بک‌آپِ دستی هم گرفته نمی‌شد.
    جمله‌ها (مثل «بک آپ نمیگیره») دست نمی‌خورند.
    """
    t = (text or "").strip()
    if not t:
        return t
    low = t.lower().replace("\u200c", "")
    compact = low.replace(" ", "")
    if compact in ("بکاپ", "بکآپ", "یکاپ", "یکآپ"):
        return "/backup"
    if compact == "قوانین":
        return "/rules"
    body = low[1:].strip() if low.startswith(".") and not low.startswith("..") else low
    if body.startswith("/"):
        body = body[1:]
    head = body.split()[0].split("@")[0] if body else ""
    mapped = _CMD_ALIASES.get(head) or _CMD_ALIASES.get(head.replace(" ", ""))
    if not mapped:
        return t
    rest = " ".join(body.split()[1:]).strip()
    # فقط خودِ دستور، نه یک جمله که با این کلمه شروع شده — به‌جز `.restore`
    # که آرگومان (آیدی/لینکِ پیامِ پشتیبان) می‌گیرد.
    if len(body.split()) > 1:
        if mapped == "restore" and (re.fullmatch(r"\d{1,12}", rest or "")
                                    or "t.me/" in rest):
            return "/restore " + rest
        return t
    return "/" + mapped


def maybe_migrate_to_data_dir():
    """اگر DATA_DIR تنظیم شد و داده کنار اسکریپت بود، یک‌بار و بدون بازنویسی منتقل کن."""
    data_dir = (os.environ.get("DATA_DIR") or "").strip()
    if not data_dir:
        return []
    try:
        target = os.path.abspath(BASE_DIR)
        script_d = os.path.dirname(os.path.abspath(__file__))
        if os.path.abspath(target) == os.path.abspath(script_d):
            return []
        moved = []
        for name in ("manager.db", "shop.db", "manager_config.json",
                     "manager_bot.string", "jafj_ai.json"):
            s = os.path.join(script_d, name)
            d = os.path.join(target, name)
            try:
                if os.path.isfile(s) and not os.path.exists(d):
                    shutil.copy2(s, d)
                    moved.append(name)
                    print(f"  \U0001F4E6 مهاجرت {name} به DATA_DIR", flush=True)
            except Exception as e:
                print(f"  \u26A0\uFE0F مهاجرت {name}: {e}", flush=True)
        sc = os.path.join(script_d, "clients")
        dc = os.path.join(target, "clients")
        try:
            if os.path.isdir(sc) and not os.path.exists(dc):
                shutil.copytree(sc, dc)
                moved.append("clients/")
                print("  \U0001F4E6 مهاجرت clients/ به DATA_DIR", flush=True)
        except Exception as e:
            print(f"  \u26A0\uFE0F مهاجرت clients: {e}", flush=True)
        return moved
    except Exception as e:
        print(f"  \u26A0\uFE0F مهاجرت DATA_DIR: {e}", flush=True)
        return []


# مهاجرت زودهنگام (قبل از ساخت DB) تا فایل خالی در مقصد ساخته نشود
try:
    maybe_migrate_to_data_dir()
except Exception:
    pass

DEFAULTS = {
    "bot_token": BOT_TOKEN,
    "api_id": API_ID,
    "api_hash": API_HASH,
    "admin_ids": list(ADMIN_IDS),
    "trial_days": 0,        # سازگاری با نسخه قدیمی
    "trial_on": False,  # فیکس 30 دقیقه آف نشه - تست رایگان خاموش
    "trial_minutes": 30,    # تست رایگان خالص پس از راه‌اندازی موفق
    "trial_warning_minutes": 10,
    "max_clients": 9999,    # سقف کل مشتری‌های همزمان (بی‌نهایت عملی — دیگر محدود نمی‌شود)
    "auto_restart": True,   # اگر پروسه‌ای مرد، دوباره بالا بیاور
    "welcome": "",          # متن خوش‌آمد — خودت بنویس
    "sample_chat": 0,        # چت منبع نمونه‌های جفج رفتن ربات
    "sample_ids": [],        # پیام‌های نمونه (متن/لینک/عکس/آلبوم)
    "sold_text": "",        # متن بعد از راه‌اندازی موفق
    "expired_text": "",     # متن وقتی اشتراک تمام شد
    "contact": "",          # آیدی پشتیبانی، مثل @yourid
    "help_text": "",        # متن راهنمای مشتری (خالی = پیش‌فرض)
    "support_text": "",     # متن بالای صفحه پشتیبانی (خالی = پیش‌فرض)
    # ── قوانین ربات (نمایش و تأیید در ابتدای ورود به ربات) ──
    "rules_on": True,       # نمایش قوانین در ابتدای ربات قبل از ورود به منو
    "rules_text": "",       # متن قوانین (خالی = متن پیش‌فرض قوانین)
    "rules_btn": "",        # متن دکمه تأیید قوانین (خالی = پیش‌فرض)
    # ── بک‌آپ خودکار (فقط در صورت ثبت اطلاعات جدید) ──
    "auto_backup_on": True, # گرفتن بک‌آپ خودکار فقط موقع ثبت/تغییر اطلاعات جدید
    # ── اشاره‌گرِ «تک‌پیامِ» پشتیبان (چت + آیدی پیام) ──
    # رباتِ تلگرام اجازه‌ی خواندنِ تاریخچه را ندارد؛ بدون این اشاره‌گر، بعد از
    # پاک‌شدنِ دیسک پیامِ پشتیبان پیدا نمی‌شود («پشتیبانی پیدا نشد»). عمداً
    # داخل manager_config.json هم هست، چون خودِ آن فایل داخل zipِ پشتیبان و
    # سینکِ گیت‌هاب است — یعنی بازیابی بعدی اشاره‌گر را با خودش می‌آورد.
    "backup_msg_chat": "",
    "backup_msg_id": 0,
    # ── سلامِ بالای منوی اصلی (هر خط یک جمله؛ خالی = پیش‌فرض) ──
    "greet_morning": "",    # ۵ تا ۱۲
    "greet_noon": "",       # ۱۲ تا ۱۷
    "greet_evening": "",    # ۱۷ تا ۲۱
    "greet_night": "",      # ۲۱ تا ۵
    # ── «📋 دستورات آماده» — راهنمای مرحله‌به‌مرحله‌ی فعال‌سازی سلف ──
    # هر مورد: {"title": عنوان، "cmd": دستور، "note": توضیح ساده}
    "cmd_items": [],
    "cmd_intro": "",        # متنِ بالای صفحه‌ی دستورات آماده (خالی = متن پیش‌فرض)
    # ── 🗂 توضیحات: فهرستِ تپ‌کردنیِ همه‌ی بخش‌ها ──
    "hub_on": True,         # دکمه‌ی «🗂 توضیحات» در منوی اصلی مشتری
    "hub_intro": "",        # متنِ بالای فهرستِ «🗂 توضیحات» (خالی = پیش‌فرض)
    "hub_page_size": 8,     # چند مورد در هر صفحه
    "hub_defaults": True,   # توضیحاتِ پیش‌فرضِ قابلیت‌های ربات در فهرست
    # ── فروشگاه ──
    "shop_on": True,
    "card_number": "",      # شماره کارت برای واریز
    "card_name": "",        # نام صاحب کارت
    "pay_note": "",         # توضیح اضافه‌ی پرداخت
    "referral_percent": 0,  # سازگاری؛ پاداش درصدی حذف شده است
    "referral_points": 2,   # پاداش هر دعوت معتبر وقتی معرف اصلاً سلف فعال ندارد
    "referral_points_self": 1,  # پاداش هر دعوت معتبر وقتی سلف روی اکانت معرف فعال است
    "remind_days": 3,       # چند روز قبل از انقضا یادآوری
    # ── سیستم امتیاز (خریدنی) ──
    "points_on": True,  # فیکس: امتیاز همیشه روشن
    "cost_per_hour": 1,      # هر ساعت کارکرد چند امتیاز  (2 ساعت = 2 امتیاز)
    "min_points": 20,        # حداقل امتیاز لازم برای فعال‌سازی
    "start_fee": 20,         # هزینه هر بار روشن کردن دستی
    "restart_fee": 20,       # هزینه روشن کردن دوباره
    "self_error_fee": 5,     # خطای خود سلف؛ خطای مدیر/سیستم رایگان
    "low_warn": 10,          # زیر این عدد هشدار بده
    "point_price": 250,      # قیمت هر امتیاز در خرید دلخواه (تومان)
    "min_points_buy": 20,    # کمترین تعداد در خرید دلخواه
    "max_points_buy": 5000,  # بیشترین تعداد در خرید دلخواه
    "min_topup": 10000,      # کمترین شارژ کیف پول
    "max_topup": 5000000,    # بیشترین شارژ کیف پول
    "force_join": [],        # [{id, user, title}] جوین اجباری
    # ── آموزش فعال‌سازی (دکمه‌ی «📚 آموزش فعال‌سازی») ──
    "tut_chat": 0,           # چت منبع محتوا — چت خصوصیِ مدیر با ربات
    "tut_ids": [],           # آیدی پیام‌های محتوا، به ترتیب ارسال
    # ── بخش‌بندی آموزش (تگ‌های بخش‌ها؛ مدیر خودش تعیین می‌کند) ──
    "tut_auto": True,        # بخش‌های «بعد از فعال‌سازی» خودکار بروند
    "tut_auto_wait": 8,      # چند ثانیه بعد از پیام راه‌اندازی سلف
    "tut_sections": [],      # [{id,name,emoji,chat,ids,when,delay,on,once,header,note,btn_label,btn_cmd}]
}

EN = str.maketrans("۰۱۲۳۴۵۶۷۸۹٠١٢٣٤٥٦٧٨٩", "01234567890123456789")


def _fa_digits(n):
    return str(n)


def digits(s):
    return re.sub(r"\D", "", str(s).translate(EN))


def normalize_iran_phone(value):
    """شماره را به فرمت +98 نرمال می‌کند؛ فقط موبایل ایران پذیرفته است."""
    raw = digits(value)
    if raw.startswith("0098"):
        raw = raw[2:]
    if raw.startswith("98"):
        national = raw[2:]
    elif raw.startswith("0"):
        national = raw[1:]
    else:
        return ""
    if len(national) != 10 or not national.startswith("9"):
        return ""
    return "+98" + national


def event_phone(ev):
    """شماره اشتراک‌شده از پیام تلگرام. (phone, owner_id)"""
    msg = getattr(ev, "message", None) or ev
    c = getattr(ev, "contact", None) or getattr(msg, "contact", None)
    media = getattr(ev, "media", None) or getattr(msg, "media", None)
    if c is None and media is not None:
        name = type(media).__name__
        if "Contact" in name or getattr(media, "phone_number", None):
            c = media
    if c is None:
        return "", None
    phone = (getattr(c, "phone_number", None) or getattr(c, "phone", None) or "")
    phone = str(phone).strip()
    if phone.lower() in ("none", "null"):
        phone = ""
    oid = getattr(c, "user_id", None)
    try:
        oid = int(oid) if oid else None
    except (TypeError, ValueError):
        oid = None
    return phone, oid


def secs_short(sec):
    sec = int(sec)
    h, r = divmod(sec, 3600)
    mnt = r // 60
    if h:
        return f"{_fa_digits(h)}:{_fa_digits(f'{mnt:02d}')} ساعت"
    if mnt:
        return f"{_fa_digits(mnt)} دقیقه"
    return f"{_fa_digits(sec)} ثانیه"


def human_left(ts):
    if not ts:
        return "نامحدود"
    d = ts - now()
    if d <= 0:
        return "تمام شده"
    days, rem = divmod(d, 86400)
    hours, rem = divmod(rem, 3600)
    minutes = rem // 60
    if days:
        return f"{_fa_digits(days)} روز و {_fa_digits(hours)} ساعت"
    if hours:
        return f"{_fa_digits(hours)} ساعت" + (f" و {_fa_digits(minutes)} دقیقه" if minutes else "")
    return f"{_fa_digits(minutes)} دقیقه" if minutes else "کمتر از یک دقیقه"


def trial_duration_label(minutes):
    """برچسب فارسیِ مدت تست رایگان.

    30 → «30 دقیقه» · 60 → «1 ساعت» · 90 → «1 ساعت و 30 دقیقه»
    · 240 → «4 ساعت» · 1440 → «24 ساعت».

    همه‌جا از این یک تابع استفاده می‌شود تا دکمه‌ی منو، متنِ پنل، پیام
    کاربر و توضیحات با عددِ تنظیمات هم‌خوان بمانند.
    """
    try:
        m = max(1, int(minutes or 30))
    except (TypeError, ValueError):
        m = 30
    if m < 60:
        return f"{_fa_digits(m)} دقیقه"
    h, rem = divmod(m, 60)
    if not rem:
        return f"{_fa_digits(h)} ساعت"
    return f"{_fa_digits(h)} ساعت و {_fa_digits(rem)} دقیقه"


# ═══════════════════════════════════════════════════
#  تنظیمات
# ═══════════════════════════════════════════════════
class Config:
    def __init__(self):
        self.d = dict(DEFAULTS)
        if os.path.exists(CONFIG_FILE):
            try:
                with open(CONFIG_FILE, encoding="utf-8") as f:
                    saved = json.load(f)
                for k, v in saved.items():
                    # False و رشته خالی مقدار معتبرند؛ فقط کلیدهای ناشناخته را رد کن.
                    if k in DEFAULTS:
                        self.d[k] = v
                if self.d.get("restart_fee") in (None, 10):
                    self.d["restart_fee"] = 20
            except Exception as e:
                print(f"⚠️ خواندن تنظیمات: {e}")
        # اولویت اتصال: متغیر محیطی → manager_config.json → هاردکد.
        # قبلاً هاردکد همیشه روی فایل می‌نشست و api_id شخصی کاربر هیچ‌وقت
        # اعمال نمی‌شد؛ api_id مشترک دلیل اصلی FloodWait روی ورود بود.
        _env_token = (os.environ.get("BOT_TOKEN") or "").strip()
        if _env_token:
            self.d["bot_token"] = _env_token
        _env_api_id = (os.environ.get("API_ID") or "").strip()
        if _env_api_id:
            try:
                self.d["api_id"] = int(_env_api_id)
            except ValueError:
                self.d["api_id"] = _env_api_id
        _env_api_hash = (os.environ.get("API_HASH") or "").strip()
        if _env_api_hash:
            self.d["api_hash"] = _env_api_hash
        # مدیر: متغیر محیطی ADMIN_IDS → فایل → هاردکد (قبلاً همیشه هاردکد بود)
        _env_admins = (os.environ.get("ADMIN_IDS") or "").strip()
        if _env_admins:
            try:
                _ids = []
                for _tok in re.split(r"[,\s]+", _env_admins):
                    _tok = _tok.strip()
                    if not _tok:
                        continue
                    _ids.append(int(_tok))
                if _ids:
                    self.d["admin_ids"] = _ids
            except Exception:
                pass
        if not self.d.get("admin_ids"):
            self.d["admin_ids"] = list(ADMIN_IDS)
        # مقدار قدیمی ۱۰ برای شروع، اکنون ۲۰ امتیاز است.
        if self.d.get("start_fee") in (None, 10):
            self.d["start_fee"] = 20
        # cmd_items یک لیست است و dict(DEFAULTS) کپیِ کم‌عمق می‌کند؛ بدون این
        # کپی، تغییرِ درجای لیست، پیش‌فرضِ خودِ ماژول را هم خراب می‌کرد.
        _ci = self.d.get("cmd_items")
        self.d["cmd_items"] = [dict(x) for x in _ci if isinstance(x, dict)] \
            if isinstance(_ci, list) else []

    def save(self):
        tmp = CONFIG_FILE + ".tmp"
        with open(tmp, "w", encoding="utf-8") as f:
            json.dump(self.d, f, ensure_ascii=False, indent=2)
        os.replace(tmp, CONFIG_FILE)
        try:
            os.chmod(CONFIG_FILE, 0o600)
        except Exception:
            pass
        # تنظیمات عوض شد → نسخه‌ی بیرونی هم باید تازه شود (کرش نباید ببردش)
        try:
            touch_data("config")
        except Exception:
            pass
        # و یک نسخه‌ی زمان‌دار همین‌جا (مهاردار) تا «تازه‌ترین» حالتِ بخش‌ها
        # همیشه در تاریخچه باشد — نسخه‌های «قبل از تغییر» به‌تنهایی همیشه
        # یک قدم عقب‌اند.
        try:
            cfg_snapshot_throttled("config-save")
        except Exception:
            pass

    def __getitem__(self, k):
        return self.d[k]

    def __setitem__(self, k, v):
        self.d[k] = v
        self.save()

    def get(self, k, default=None):
        return self.d.get(k, default)

    def is_admin(self, uid):
        return uid in (self.d.get("admin_ids") or [])


# ═══════════════════════════════════════════════════
#  دیتابیس مشتری‌ها
# ═══════════════════════════════════════════════════
SCHEMA = """
CREATE TABLE IF NOT EXISTS clients (
    uid INTEGER PRIMARY KEY,
    username TEXT,
    name TEXT,
    phone TEXT,
    tg_id INTEGER,
    session TEXT,
    status TEXT NOT NULL DEFAULT 'new',
    expires_at INTEGER NOT NULL DEFAULT 0,
    created_at INTEGER NOT NULL,
    started_at INTEGER,
    restarts INTEGER NOT NULL DEFAULT 0,
    note TEXT,
    proxy TEXT,
    phone_verified INTEGER NOT NULL DEFAULT 0,
    current_plan_id INTEGER NOT NULL DEFAULT 0,
    trial_used INTEGER NOT NULL DEFAULT 0,
    trial_started_at INTEGER NOT NULL DEFAULT 0,
    trial_expires_at INTEGER NOT NULL DEFAULT 0,
    trial_warning_sent INTEGER NOT NULL DEFAULT 0,
    rules_accepted INTEGER NOT NULL DEFAULT 1,
    want_on INTEGER NOT NULL DEFAULT 1,
    need_login INTEGER NOT NULL DEFAULT 0
);
CREATE TABLE IF NOT EXISTS log (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    ts INTEGER NOT NULL, uid INTEGER, kind TEXT, detail TEXT
);
CREATE TABLE IF NOT EXISTS tut_sent (
    uid INTEGER NOT NULL, sec INTEGER NOT NULL, ts INTEGER NOT NULL,
    PRIMARY KEY (uid, sec)
);
"""


class DB:
    def __init__(self, path=DB_FILE):
        self.lock = threading.RLock()
        self.c = sqlite3.connect(path, check_same_thread=False)
        self.c.row_factory = sqlite3.Row
        self.c.execute("PRAGMA journal_mode=WAL")
        with self.lock:
            self.c.executescript(SCHEMA)
            # مهاجرت دیتابیس‌های قدیمی
            cols = {r[1] for r in self.c.execute("PRAGMA table_info(clients)")}
            if "phone_verified" not in cols:
                self.c.execute("ALTER TABLE clients ADD COLUMN phone_verified INTEGER NOT NULL DEFAULT 0")
            if "current_plan_id" not in cols:
                self.c.execute("ALTER TABLE clients ADD COLUMN current_plan_id INTEGER NOT NULL DEFAULT 0")
            if "max_accounts" not in cols:
                # سقف اکانتِ مخصوصِ این کاربر (اولویت بر پلنِ جهانی). 0 = از پلن.
                self.c.execute("ALTER TABLE clients ADD COLUMN max_accounts INTEGER NOT NULL DEFAULT 0")
            for col, decl in (("trial_used", "INTEGER NOT NULL DEFAULT 0"),
                              ("trial_started_at", "INTEGER NOT NULL DEFAULT 0"),
                              ("trial_expires_at", "INTEGER NOT NULL DEFAULT 0"),
                              ("trial_warning_sent", "INTEGER NOT NULL DEFAULT 0"),
                              ("rules_accepted", "INTEGER NOT NULL DEFAULT 1"),
                              # «این سرویس باید روشن بماند؟» — پیش‌فرض ۱ تا
                              # بعد از آپدیت، سرویسِ همه مثل قبل خودکار بالا
                              # بیاید؛ خاموش‌کردنِ دستی آن را ۰ می‌کند.
                              ("want_on", "INTEGER NOT NULL DEFAULT 1"),
                              # ۱ = سشن باطل است و باید از پنل دوباره لاگین شود؛
                              # تا آن موقع هیچ پروسه‌ای بالا نمی‌آید (وگرنه هر
                              # بار تلگرام برای مشتری کدِ ورود می‌فرستد).
                              ("need_login", "INTEGER NOT NULL DEFAULT 0")):
                if col not in cols:
                    self.c.execute(f"ALTER TABLE clients ADD COLUMN {col} {decl}")
                    if col == "trial_used":
                        pass
            # اصلاح خودکار کاربرانی که به اشتباه تست‌سوخته ثبت شده بودند ولی تستی نزده‌اند:
            self.c.execute("UPDATE clients SET trial_used=0 WHERE trial_started_at=0")
            self.c.commit()

    def x(self, sql, a=(), f=None):
        with self.lock:
            cur = self.c.execute(sql, a)
            if f == "one":
                r = cur.fetchone()
                return dict(r) if r else None
            if f == "all":
                return [dict(r) for r in cur.fetchall()]
            self.c.commit()
            return cur.lastrowid

    def close(self):
        """بستن اتصال (برای بازیابی پشتیبان)."""
        try:
            with self.lock:
                try:
                    self.c.commit()
                except Exception:
                    pass
                try:
                    self.c.close()
                except Exception:
                    pass
        except Exception:
            pass

    def get(self, uid):
        return self.x("SELECT * FROM clients WHERE uid=?", (uid,), "one")

    def add(self, uid, username, name, trial_days):
        if self.get(uid):
            return
        trial_days = max(0, int(trial_days or 0))
        exp = now() + trial_days * 86400 if trial_days else 0
        status = "active" if exp else "new"
        self.x("INSERT INTO clients (uid,username,name,created_at,expires_at,status)"
               " VALUES (?,?,?,?,?,?)", (uid, username, name, now(), exp, status))

    # ستون‌هایی که تغییرشان «داده‌ی مشتری» است و باید سریع بیرون ذخیره شود.
    # عمداً started_at/restarts اینجا نیستند: watchdog هر ۳۰ ثانیه عوضشان
    # می‌کند و اگر آن‌ها هم trigger بودند، هر ۳۰ ثانیه یک sync می‌رفت.
    CRITICAL_COLS = ("session", "phone", "tg_id", "status", "expires_at",
                     "trial_expires_at", "trial_started_at", "trial_used",
                     "current_plan_id", "max_accounts", "want_on",
                     "phone_verified", "rules_accepted")

    def set(self, uid, **kw):
        if not kw:
            return
        cols = ",".join(f"{k}=?" for k in kw)
        self.x(f"UPDATE clients SET {cols} WHERE uid=?",
               tuple(kw.values()) + (uid,))
        try:
            if any(k in self.CRITICAL_COLS for k in kw):
                touch_data("clients")
        except Exception:
            pass

    def all(self, status=None):
        if status:
            return self.x("SELECT * FROM clients WHERE status=? ORDER BY uid",
                          (status,), "all")
        return self.x("SELECT * FROM clients ORDER BY created_at DESC", (), "all")

    def runnable(self):
        return self.x("SELECT * FROM clients WHERE status='active'"
                      " AND session IS NOT NULL AND session<>''", (), "all")

    def wanted(self):
        """سرویس‌هایی که «باید روشن باشند» — یعنی مشتری/مدیر خاموششان نکرده.

        ستون `want_on` در نسخه‌های قبل نبود؛ برای همان رکوردهای قدیمی پیش‌فرض
        ۱ است تا بعد از آپدیت همه مثل قبل خودکار بالا بیایند (وگرنه هیچ سرویسی
        روشن نمی‌شد). فقط «خاموش کردنِ عمدی» این مقدار را ۰ می‌کند.
        """
        return self.x("SELECT * FROM clients WHERE status='active'"
                      " AND session IS NOT NULL AND session<>''"
                      " AND COALESCE(want_on, 1)<>0", (), "all")

    def want_on(self, uid):
        """آیا این سرویس باید روشن بماند؟ (رکوردِ قدیمی/نامعلوم = بله)"""
        c = self.get(uid) or {}
        v = c.get("want_on", None)
        return True if v is None else bool(v)

    def set_want(self, uid, on):
        """ثبتِ «باید روشن بماند» روی دیسک تا بعد از آپدیت/ری‌استارت بماند."""
        try:
            self.set(uid, want_on=1 if on else 0)
            return True
        except Exception:
            return False

    # ---------- تست رایگان ----------
    def trial_stats(self):
        """(کل کاربران، در حال تست، قبلاً تست گرفته‌اند)"""
        total = self.x("SELECT COUNT(*) c FROM clients", (), "one")["c"]
        running = self.x("SELECT COUNT(*) c FROM clients WHERE trial_expires_at>?",
                         (now(),), "one")["c"]
        used = self.x("SELECT COUNT(*) c FROM clients WHERE trial_used<>0"
                      " OR trial_started_at>0", (), "one")["c"]
        return int(total), int(running), int(used)

    def trial_reset_all(self):
        """تست رایگان را برای همه از نو قابل استفاده می‌کند.

        - کسی که تستش تمام شده: کلِ ردِ تست پاک می‌شود (دوباره می‌تواند
          تست بگیرد).
        - کسی که همین حالا داخل تست است: تایمرِ جاری دست‌نخورده می‌ماند
          (حلقه‌ی تست همان‌طور سرِ موعد خاموشش می‌کند) ولی از این لحظه
          دوباره «واجد شرایط» حساب می‌شود.

        خروجی: (تعداد رکوردهای ریست‌شده، تعداد در حال تست)
        """
        now_t = now()
        with self.lock:
            running = self.c.execute(
                "SELECT COUNT(*) c FROM clients WHERE trial_expires_at>?",
                (now_t,)).fetchone()[0]
            cur = self.c.execute(
                "UPDATE clients SET trial_used=0, trial_started_at=0,"
                " trial_warning_sent=0,"
                " trial_expires_at=CASE WHEN trial_expires_at>? THEN trial_expires_at"
                " ELSE 0 END", (now_t,))
            n = cur.rowcount
            self.c.commit()
        return max(0, int(n or 0)), int(running or 0)

    def trial_reset_one(self, uid):
        """تست رایگانِ یک کاربر را از نو می‌کند (تایمرِ در حال اجرا حفظ می‌شود)."""
        now_t = now()
        c = self.get(uid) or {}
        keep = int(c.get("trial_expires_at") or 0)
        self.set(uid, trial_used=0, trial_started_at=0, trial_warning_sent=0,
                 trial_expires_at=(keep if keep > now_t else 0))
        return True

    def rules_stats(self):
        """(کل کاربران، تعداد کاربرانی که قوانین را پذیرفته‌اند)"""
        try:
            total = self.x("SELECT COUNT(*) c FROM clients", (), "one")["c"]
            acc = self.x("SELECT COUNT(*) c FROM clients WHERE rules_accepted<>0",
                         (), "one")["c"]
            return int(total or 0), int(acc or 0)
        except Exception:
            return 0, 0

    def rules_reset_all(self):
        """تأیید قوانین را برای همه‌ی کاربران صفر می‌کند تا قوانین جدید را دوباره ببینند."""
        with self.lock:
            cur = self.c.execute("UPDATE clients SET rules_accepted=0")
            n = cur.rowcount
            self.c.commit()
        return max(0, int(n or 0))

    def expired(self):
        return self.x("SELECT * FROM clients WHERE status='active'"
                      " AND expires_at>0 AND expires_at<=?", (now(),), "all")

    def counts(self):
        return {r["status"]: r["c"] for r in
                self.x("SELECT status,COUNT(*) c FROM clients GROUP BY status",
                       (), "all")}

    def log(self, uid, kind, detail=""):
        self.x("INSERT INTO log (ts,uid,kind,detail) VALUES (?,?,?,?)",
               (now(), uid, kind, str(detail)[:500]))

    def recent(self, n=20):
        return self.x("SELECT * FROM log ORDER BY id DESC LIMIT ?", (n,), "all")

    # ---------- بخش‌های آموزش: کدام بخش برای کدام کاربر رفته ----------
    def _tut_table(self):
        """جدولِ tut_sent را مطمئن می‌کند.

        چرا لازم است: بعد از بازیابی از پشتیبانِ قدیمی، فایل دیتابیس همان‌جا
        کپی می‌شود و جدول‌های تازه ندارند؛ اینجا خودش را ترمیم می‌کند تا
        «یک‌بار برای هر کاربر» بعد از ری‌استور از کار نیفتد.
        """
        if getattr(self, "_tut_ok", False):
            return
        with self.lock:
            try:
                self.c.execute(
                    "CREATE TABLE IF NOT EXISTS tut_sent ("
                    " uid INTEGER NOT NULL, sec INTEGER NOT NULL,"
                    " ts INTEGER NOT NULL, PRIMARY KEY (uid, sec))")
                self.c.commit()
            except Exception as e:
                print("tut_table:", type(e).__name__, e)
            self._tut_ok = True

    def tut_mark(self, uid, sec):
        self._tut_table()
        try:
            self.x("INSERT OR REPLACE INTO tut_sent (uid,sec,ts) VALUES (?,?,?)",
                   (int(uid), int(sec), now()))
            return True
        except Exception as e:
            print("tut_mark:", type(e).__name__, e)
            return False

    def tut_done(self, uid, sec):
        self._tut_table()
        try:
            r = self.x("SELECT 1 AS x FROM tut_sent WHERE uid=? AND sec=?",
                       (int(uid), int(sec)), "one")
            return bool(r)
        except Exception:
            return False

    def tut_reset_user(self, uid):
        """شمارنده‌ی بخش‌های فرستاده‌شده‌ی یک کاربر را پاک می‌کند."""
        self._tut_table()
        try:
            self.x("DELETE FROM tut_sent WHERE uid=?", (int(uid),))
            return True
        except Exception:
            return False

    def find_users(self, query, limit=15):
        """جستجوی کاربر با uid، tg_id، @username، شماره موبایل یا نام."""
        raw = str(query or "").strip()
        if not raw:
            return []
        uname = raw
        if "t.me/" in uname.lower():
            uname = uname.split("/")[-1].split("?")[0]
        uname = uname.lstrip("@").strip()
        num = digits(raw)
        seen = set()
        out = []

        def _push(rows):
            for r in (rows or []):
                u = r.get("uid")
                if u is not None and u not in seen:
                    seen.add(u)
                    out.append(r)

        if num and raw.lstrip("+- ").replace(" ", "").isdigit() or (num and num == raw):
            try:
                iv = int(num)
                _push(self.x("SELECT * FROM clients WHERE uid=? OR tg_id=?",
                             (iv, iv), "all"))
            except Exception:
                pass
        # نرمال‌سازی شماره موبایل (مثلاً 0912... یا +98912...)
        if len(num) >= 7:
            tail = num[-10:] if len(num) >= 10 else num
            _push(self.x("SELECT * FROM clients WHERE REPLACE(REPLACE(COALESCE(phone,''),' ',''),'+','') LIKE ?"
                         " ORDER BY created_at DESC LIMIT ?",
                         (f"%{tail}%", int(limit)), "all"))
        if uname:
            _push(self.x("SELECT * FROM clients WHERE LOWER(COALESCE(username,''))=LOWER(?)"
                         " ORDER BY created_at DESC LIMIT ?",
                         (uname, int(limit)), "all"))
            like = f"%{uname}%"
            _push(self.x("SELECT * FROM clients WHERE LOWER(COALESCE(username,'')) LIKE LOWER(?)"
                         " OR LOWER(COALESCE(name,'')) LIKE LOWER(?)"
                         " ORDER BY created_at DESC LIMIT ?",
                         (like, like, int(limit)), "all"))
        return out[:int(limit)]

    def delete_user(self, uid):
        """پاک کردن کامل رکورد کاربر، سوابق آموزش و لاگ‌های او از manager.db."""
        uid = int(uid or 0)
        counts = {"client": 0, "tut_sent": 0, "log": 0}
        if uid <= 0:
            return counts
        self._tut_table()
        with self.lock:
            try:
                counts["client"] = max(0, self.c.execute(
                    "DELETE FROM clients WHERE uid=?", (uid,)).rowcount or 0)
                counts["tut_sent"] = max(0, self.c.execute(
                    "DELETE FROM tut_sent WHERE uid=?", (uid,)).rowcount or 0)
                counts["log"] = max(0, self.c.execute(
                    "DELETE FROM log WHERE uid=?", (uid,)).rowcount or 0)
                self.c.commit()
            except Exception:
                self.c.rollback()
                raise
        try:
            touch_data("clients")
        except Exception:
            pass
        return counts


# ── اعتبارسنجیِ فایل سشن (بدون نیاز به telethon) ─────────────────────────
# چرا: `TelegramClient.start(phone=...)` وقتی سشن معتبر نباشد **کد ورود
# می‌فرستد**. بعد از هر بازیابی/آپدیت، اگر فایل سشن خراب یا کلیدش باطل شده
# باشد، یک‌جا برای همه‌ی مشتری‌ها کد می‌رفت. قبل از اجرا اعتبارسنجی می‌کنیم
# تا هرگز کدِ ناخواسته نرود.

# جدولِ سشنِ تلگرام (SQLiteSession): auth_key خالی = لاگین‌نشده.
_SESSION_SQLS = (
    "SELECT auth_key FROM sessions LIMIT 1",
    "SELECT auth_key FROM session LIMIT 1",
)


# نشانه‌های «کدِ ورود فرستاده شد» در لاگِ سلف — اگر جایی دیدیم، فوراً
# متوقف می‌کنیم تا اسپمِ کد نسازد.
_LOGIN_CODE_RE = re.compile(
    r"(code request|send_code_request|PHONE_CODE|phone_code|Code request|"
    r"کد ورود|Login code)", re.I)


def session_health(path):
    """فایل‌های سشن را بررسی کن → (سالم؟, دلیل).

    چک‌ها همه محلی و بی‌خطرند (هیچ اتصالی به تلگرام زده نمی‌شود):
      • فایل هست و خالی نیست
      • sqlite سالم است (نه نیمه‌کاره/خراب)
      • جدولِ سشن و auth_key دارد
    """
    try:
        if not path or not os.path.isfile(path):
            return False, "فایل سشن نیست"
        if os.path.getsize(path) == 0:
            return False, "فایل سشن خالی است"
        con = None
        try:
            con = sqlite3.connect(f"file:{path}?mode=ro", uri=True, timeout=2)
            cur = con.execute("PRAGMA quick_check")
            row = cur.fetchone()
            if not row or str(row[0]).lower() != "ok":
                return False, "فایل سشن خراب است"
            for sql in _SESSION_SQLS:
                try:
                    r = con.execute(sql).fetchone()
                except Exception:
                    continue
                if r is None:
                    return False, "سشن خالی است (بدون کلید)"
                key = r[0]
                if isinstance(key, memoryview):
                    key = bytes(key)
                if not key:
                    return False, "کلید سشن خالی است"
                return True, ""
            return False, "جدولِ سشن پیدا نشد"
        except sqlite3.DatabaseError:
            return False, "فایل سشن قابل خواندن نیست"
        finally:
            try:
                if con is not None:
                    con.close()
            except Exception:
                pass
    except Exception as e:
        return False, f"خطا: {type(e).__name__}"


class _AdoptedProc:
    """دستگیره‌ی سبک برای پروسه‌ی سلفی که ما نساختیمش (بعد از ری‌استارت manager).

    فقط همان چیزی را دارد که Supervisor از یک Popen می‌خواهد: `pid` و
    `poll()`. با آن، `is_running` / `running_count` / `stop` بدون تغییر
    کار می‌کنند و نسخه‌ی دومِ سلف اجرا نمی‌شود.
    """

    def __init__(self, pid, daemon=None):
        self.pid = int(pid)
        self.daemon = daemon            # برای خواندنِ کدِ خروجِ واقعی
        self.returncode = None

    def _exit_code(self, default=1):
        """کدِ خروج را از دیمنِ fork بگیر (۷۶ تکراری، ۷۷ سوخته، ۷۸ لاگین)."""
        try:
            if self.daemon is not None:
                if self.daemon.drain() is False:
                    return None  # reader busy: don't lose a meaningful exit code
                code = self.daemon.exits.get(self.pid)
                if isinstance(code, int):
                    return code
        except Exception:
            pass
        return default

    def poll(self):
        try:
            os.kill(self.pid, 0)
        except ProcessLookupError:
            self.returncode = self._exit_code()
            return self.returncode
        except PermissionError:
            pass
        except Exception:
            self.returncode = self._exit_code()
            return self.returncode
        # پروسه‌ی زامبی (مرده ولی جمع‌نشده) هم «مرده» است؛ وگرنه سلفی که با
        # fork اجرا شده و مرده، برای همیشه «زنده» شمرده می‌شود.
        try:
            with open(f"/proc/{self.pid}/stat", encoding="utf-8") as f:
                if f.read().rsplit(")", 1)[-1].split()[0] == "Z":
                    self.returncode = self._exit_code()
                    return self.returncode
        except Exception:
            pass
        return None

    def kill(self):
        try:
            os.kill(self.pid, signal.SIGKILL)
        except Exception:
            pass

    def terminate(self):
        try:
            os.kill(self.pid, signal.SIGTERM)
        except Exception:
            pass


class ForkDaemon:
    """کلاینتِ `jafj_forkd.py` — سلف‌ها با حافظه‌ی مشترک.

    چرا: هر سلفِ جدا `import telethon` را تکرار می‌کند (~۴۰ مگابایت). با
    fork از یک والدِ مشترک، آن ۴۰ مگابایت یک‌بار در رم می‌نشیند و بینِ همه
    شریک می‌شود (copy-on-write). برای ۱۰۰ اکانت تفاوتِ چند گیگابایت است.

    رابطش عمداً همان چیزی است که Supervisor از یک پروسه می‌خواهد: pid و poll.
    """

    def __init__(self, selfbot=None, python=None):
        self.python = python or sys.executable
        self.selfbot = selfbot or SELFBOT
        self.proc = None
        self._buf = b""
        self._lock = threading.Lock()
        self.last_error = ""
        self.exits = {}                 # pid → کدِ خروج (از رویدادهای دیمن)
        self.uid_exits = {}             # شارد: خروجِ هر اکانت مستقل است

    def forker_path(self):
        d = os.path.dirname(os.path.abspath(self.selfbot))
        cand = os.path.join(d, "jafj_forkd.py")
        if os.path.isfile(cand):
            return cand
        return os.path.join(os.path.dirname(os.path.abspath(__file__)),
                            "jafj_forkd.py")

    def alive(self):
        return bool(self.proc is not None and self.proc.poll() is None)

    def start(self, timeout=90):
        if self.alive():
            return True
        path = self.forker_path()
        if not os.path.isfile(path):
            self.last_error = f"jafj_forkd.py پیدا نشد ({path})"
            return False
        try:
            _env = dict(os.environ)
            _env.setdefault("JAFJ_NO_AUTO_LOGIN", "1")
            self.proc = subprocess.Popen(
                [self.python, path, "--selfbot", os.path.abspath(self.selfbot)],
                stdin=subprocess.PIPE, stdout=subprocess.PIPE,
                stderr=subprocess.DEVNULL, bufsize=0, env=_env,
                start_new_session=True)
            # Even if readiness changes between select() and read(), read must
            # not park the event loop forever on an empty blocking pipe.
            try:
                os.set_blocking(self.proc.stdout.fileno(), False)
            except (AttributeError, OSError):
                pass  # Serialized reads still protect platforms without it.
        except Exception as e:
            self.last_error = f"{type(e).__name__}: {e}"
            return False
        msg = self._read_until({"event": "ready"}, timeout=timeout)
        if msg is None:
            self.last_error = "دیمن آماده نشد (timeout)"
            return False
        return True

    def _send(self, obj):
        self.proc.stdin.write((json.dumps(obj, ensure_ascii=False) + "\n")
                              .encode("utf-8"))
        self.proc.stdin.flush()

    def _read_msg(self, timeout):
        end = time.time() + max(0.0, timeout)
        while True:
            nl = self._buf.find(b"\n")
            if nl >= 0:
                line, self._buf = self._buf[:nl], self._buf[nl + 1:]
                try:
                    msg = json.loads(line.decode("utf-8", "ignore"))
                except Exception:
                    continue
                if isinstance(msg, dict) and msg.get("event") == "exit":
                    # ۷۶ = نسخه‌ی تکراری، ۷۷ = کلیدِ سوخته، ۷۸ = نیاز به لاگین
                    try:
                        self.exits[int(msg.get("pid"))] = msg.get("code")
                        if msg.get("uid") is not None:
                            self.uid_exits[str(msg["uid"])] = msg.get("code")
                    except Exception:
                        pass
                    continue
                return msg
            left = end - time.time()
            if left <= 0 or not self.alive():
                return None
            try:
                import select
                r, _, _ = select.select([self.proc.stdout], [], [], left)
                if not r:
                    return None
                chunk = os.read(self.proc.stdout.fileno(), 65536)
            except BlockingIOError:
                continue
            except Exception:
                return None
            if not chunk:
                return None
            self._buf += chunk

    def _drain_locked(self, timeout=0.02):
        # Caller owns _lock; no other thread may consume protocol replies.
        while True:
            msg = self._read_msg(timeout)
            if msg is None:
                return

    def drain(self, timeout=0.02):
        """خروجی را فقط اگر خوانندهٔ دیگری مشغول نیست بخوان."""
        if not self._lock.acquire(blocking=False):
            return False
        try:
            self._drain_locked(timeout)
            return True
        finally:
            self._lock.release()

    def _read_until(self, want, timeout=30):
        end = time.time() + timeout
        while time.time() < end:
            msg = self._read_msg(max(0.1, end - time.time()))
            if msg is None:
                return None
            if all(msg.get(k) == v for k, v in want.items()):
                return msg
        return None

    def _read_ok(self, timeout=30, skip_events=True, expected_uid=None):
        end = time.time() + timeout
        while time.time() < end:
            msg = self._read_msg(max(0.1, end - time.time()))
            if msg is None:
                return None
            # A late ping/stop response is not a reply to a run request.
            if "ok" in msg and "accounts" not in msg and "alive" not in msg:
                invalid = ((msg.get("ok") and not msg.get("pid"))
                           or (expected_uid is not None and msg.get("uid") is not None
                               and str(msg["uid"]) != str(expected_uid)))
                if invalid and skip_events:
                    continue
                return msg
            if not skip_events:
                return msg
        return None

    def spawn(self, cwd, log, uid, timeout=60):
        """(pid, خطا) — فرزندِ تازه با cwd پوشه‌ی همان اکانت."""
        with self._lock:
            if not self.start():
                return None, self.last_error or "دیمن بالا نیامد"
            try:
                self._send({"cmd": "run", "cwd": str(cwd), "log": str(log),
                            "uid": str(uid)})
            except Exception as e:
                return None, f"{type(e).__name__}: {e}"
            msg = self._read_ok(timeout=timeout, expected_uid=uid)
            if not msg or not msg.get("ok"):
                return None, (msg or {}).get("error") or "پاسخِ دیمن نیامد"
            try:
                return int(msg["pid"]), ""
            except Exception:
                return None, "pid نامعتبر"

    def close(self):
        try:
            if self.alive():
                self._send({"cmd": "quit"})
        except Exception:
            pass
        try:
            if self.alive():
                self.proc.terminate()
        except Exception:
            pass


# پیش‌فرض ۱۶: هر پروسه‌ی شارد ~۶۷MB پایه دارد (اندازه‌گیری‌شده)، پس
# شاردهای کوچکِ زیاد گران‌تر از یک شاردِ بزرگ‌اند. ۴ شارد × ۲ اکانت = ۲۶۷MB
# در حالی که ۱ شارد × ۲۴ اکانت = ۸۲MB.
SHARD_SIZE = 16         # پیش‌فرض؛ با JAFJ_SHARD_SIZE عوض می‌شود


def shard_size(env=None):
    """چند اکانت در یک پروسه‌ی shard (۱ تا ۶۴)."""
    e = env if env is not None else os.environ
    try:
        v = int((e.get("JAFJ_SHARD_SIZE") or "").strip() or SHARD_SIZE)
    except Exception:
        v = SHARD_SIZE
    return max(1, min(64, v))


class ShardDaemon(ForkDaemon):
    """چند اکانت در یک پروسه (`jafj_shardd.py`).

    حافظه‌ی اندازه‌گیری‌شده: fork ~۱۱.۲MB برای هر اکانت، shard ~۳.۳MB.
    بهایش: یک پروسه = یک نقطه‌ی شکست، پس اندازه‌اش کوچک نگه داشته می‌شود.
    """

    def __init__(self, selfbot=None, python=None, size=None):
        ForkDaemon.__init__(self, selfbot, python)
        self.size = int(size or shard_size())
        self.uids = {}                  # uid → pid (همیشه pid این پروسه)
        self._status_lock = threading.Lock()
        self._account_status = {}       # آخرین وضعیت تأییدشده، نه حدسِ timeout
        self._status_verified_at = {}   # زمان تأیید برای محافظت از هزینهٔ مشتری
        self._probe_inflight = False
        self._probe_last = 0.0
        self._probe_seq = 0

    def forker_path(self):
        d = os.path.dirname(os.path.abspath(self.selfbot))
        for base in (d, os.path.dirname(os.path.abspath(__file__))):
            cand = os.path.join(base, "jafj_shardd.py")
            if os.path.isfile(cand):
                return cand
        return os.path.join(d, "jafj_shardd.py")

    def start(self, timeout=120):
        if self.alive():
            return True
        path = self.forker_path()
        if not os.path.isfile(path):
            self.last_error = f"jafj_shardd.py پیدا نشد ({path})"
            return False
        try:
            _env = dict(os.environ)
            _env.setdefault("JAFJ_NO_AUTO_LOGIN", "1")
            self.proc = subprocess.Popen(
                [self.python, path, "--selfbot", os.path.abspath(self.selfbot),
                 "--max-accounts", str(self.size)],
                stdin=subprocess.PIPE, stdout=subprocess.PIPE,
                stderr=subprocess.DEVNULL, bufsize=0, env=_env,
                start_new_session=True)
            # Even if readiness changes between select() and read(), read must
            # not park the event loop forever on an empty blocking pipe.
            try:
                os.set_blocking(self.proc.stdout.fileno(), False)
            except (AttributeError, OSError):
                pass  # Serialized reads still protect platforms without it.
        except Exception as e:
            self.last_error = f"{type(e).__name__}: {e}"
            return False
        msg = self._read_until({"event": "ready"}, timeout=timeout)
        if msg is None:
            self.last_error = "شارد آماده نشد (timeout)"
            return False
        return True

    def room(self):
        return max(0, self.size - len(self.uids))

    def spawn(self, cwd, log, uid, timeout=90):
        with self._lock:
            if not self.alive():
                self.uids.clear()
                with self._status_lock:
                    self._account_status.clear()
                    self._status_verified_at.clear()
            if not self.start():
                return None, self.last_error or "شارد بالا نیامد"
            try:
                self._send({"cmd": "run", "cwd": str(cwd), "log": str(log),
                            "uid": str(uid)})
            except Exception as e:
                return None, f"{type(e).__name__}: {e}"
            msg = self._read_ok(timeout=timeout, expected_uid=uid)
            if not msg or not msg.get("ok"):
                return None, (msg or {}).get("error") or "پاسخِ شارد نیامد"
            uid = str(uid)
            self.uids[uid] = int(msg.get("pid") or 0)
            self.uid_exits.pop(uid, None)
            with self._status_lock:
                self._account_status[uid] = True
                self._status_verified_at[uid] = time.monotonic()
            return self.uids[uid], ""

    def _refresh_accounts(self):
        """پینگ شارد فقط در thread؛ None یعنی نامشخص، نه اینکه اکانت مرده."""
        with self._lock:
            if not self.alive():
                return None
            self._drain_locked()
            self._probe_seq += 1
            request_id = self._probe_seq
            try:
                self._send({"cmd": "ping", "request_id": request_id})
            except Exception:
                return None
            end = time.monotonic() + 5
            while time.monotonic() < end:
                msg = self._read_msg(max(0.01, end - time.monotonic()))
                if msg is None:
                    break
                # پاسخ دیرهنگامِ پینگ قبلی نباید باعث ری‌استارت اشتباه شود.
                if (msg.get("ok") and isinstance(msg.get("accounts"), list)
                        and msg.get("request_id") == request_id):
                    accounts = {str(x) for x in msg["accounts"]}
                    with self._status_lock:
                        checked_at = time.monotonic()
                        for uid in self.uids:
                            self._account_status[uid] = uid in accounts
                            self._status_verified_at[uid] = checked_at
                    return accounts
        return None

    def _schedule_status_probe(self):
        with self._status_lock:
            if self._probe_inflight or time.monotonic() - self._probe_last < 5:
                return
            self._probe_inflight = True
        def worker():
            try:
                self._refresh_accounts()
            finally:
                with self._status_lock:
                    self._probe_last = time.monotonic()
                    self._probe_inflight = False
        try:
            threading.Thread(target=worker, name="shard-status", daemon=True).start()
        except Exception:
            with self._status_lock:
                self._probe_inflight = False

    def alive_uid(self, uid):
        """وضعیت کش‌شده؛ هرگز منتظر قفل یا پاسخ IPC روی حلقهٔ مدیر نمی‌ماند."""
        uid = str(uid)
        if not self.alive():
            return False
        self._schedule_status_probe()
        with self._status_lock:
            # هنگام جواب ندادن شارد، بی‌دلیل نسخهٔ دوم از سشن اجرا نکن.
            return self._account_status.get(uid, True)

    def recently_confirmed_alive(self, uid, max_age=120):
        """وضعیت نامطمئن برای اجرای نسخهٔ دوم کافی نیست؛ برای شارژ هم کافی نیست."""
        uid = str(uid)
        if not self.alive():
            return False
        with self._status_lock:
            checked = self._status_verified_at.get(uid)
            return bool(self._account_status.get(uid) is True and checked is not None
                        and time.monotonic() - checked <= max_age)

    def alive_uid_confirmed(self, uid):
        """بررسی واقعی اولیه؛ ممکن است منتظر پاسخ شارد بماند."""
        if not self.alive():
            return False
        accounts = self._refresh_accounts()
        return str(uid) in accounts if accounts is not None else None

    def stop_uid(self, uid, timeout=40):
        uid = str(uid)
        with self._lock:
            if not self.alive():
                self.uids.pop(uid, None)
                return True
            try:
                self._send({"cmd": "stop", "uid": uid})
            except Exception:
                return False
            end = time.time() + timeout
            while time.time() < end:
                msg = self._read_msg(max(0.1, end - time.time()))
                if msg is None:
                    break
                if msg.get("uid") == uid and "ok" in msg:
                    ok = bool(msg.get("ok"))
                    if not ok:
                        # رشته نمرد → کلِ شارد را ببند (بقیه ری‌استارت می‌شوند)
                        try:
                            self.proc.terminate()
                        except Exception:
                            pass
                    self.uids.pop(uid, None)
                    with self._status_lock:
                        self._account_status[uid] = False
                    return True
        self.uids.pop(uid, None)
        return False


class _ShardProc:
    """دستگیره‌ی یک اکانت داخلِ شارد — مثلِ Popen اما محدود به همان اکانت."""

    def __init__(self, pid, daemon, uid):
        self.pid = int(pid)
        self.daemon = daemon
        self.uid = str(uid)
        self.returncode = None

    def poll(self):
        if self.returncode is not None:
            return self.returncode
        return self._poll_result(self.daemon.alive_uid(self.uid))

    def poll_confirmed(self):
        if self.returncode is not None:
            return self.returncode
        return self._poll_result(self.daemon.alive_uid_confirmed(self.uid))

    def _poll_result(self, alive):
        if alive is not False:   # True or unknown: never duplicate a session
            return None
        self.returncode = self.daemon.uid_exits.get(self.uid)
        if not isinstance(self.returncode, int):
            self.returncode = 1
        return self.returncode

    def terminate(self):
        self.daemon.stop_uid(self.uid)

    def kill(self):
        self.daemon.stop_uid(self.uid)

    def remote_stop(self):
        return self.daemon.stop_uid(self.uid)


# ═══════════════════════════════════════════════════
#  «چرا سلف بالا نیامد؟» — تشخیصِ علت از لاگِ خودِ سلف
#
#  بدون این، شدنی‌ترین حالت این بود: مدیر پروسه را اجرا می‌کرد، سلف دو
#  ثانیه بعد می‌مرد، مدیر آن را «روشن» می‌شمرد، watchdog هر ۳۰ ثانیه تا ۱۰
#  دقیقه دوباره تلاش می‌کرد و مشتری هیچ پیامی نمی‌گرفت — یعنی از بیرون
#  دقیقاً «۹۵.py اجرا نمی‌شود» دیده می‌شد.
# ═══════════════════════════════════════════════════
SESSION_FAIL_RE = re.compile(
    r"سشنِ این اکانت معتبر نیست|needs[_ ]relogin|از تلگرام خارج|"
    r"SESSION_REVOKED|AUTH_KEY_UNREGISTERED|AUTH_KEY_DUPLICATED|"
    r"AuthKeyDuplicated|AuthKeyUnregistered|SessionRevoked|"
    r"Client is not authorized|not authorized", re.I)

# «کلیدِ سشن سوخته» — دقیقاً همان چیزی که در پیامِ واقعیِ کاربر بود:
# AuthKeyDuplicatedError: ... used under two different IP addresses
# simultaneously, and can no longer be used.
# قبلاً الگو فقط AUTH_KEY_DUPLICATED (با آندرلاین) را می‌شناخت و متنِ
# Telethon نمی‌خواند → علت «شبکه» گزارش می‌شد و درمان (لاگینِ دوبارهٔ
# اجباری) هرگز انجام نمی‌شد؛ یعنی اکانت تا ابد «بالا نمی‌آمد».
KEY_BURNED_RE = re.compile(
    r"AUTH_KEY_DUPLICATED|AUTH_KEY_UNREGISTERED|AuthKeyDuplicated|"
    r"AuthKeyUnregistered|SessionRevoked|SESSION_REVOKED|"
    r"two different IP addresses|can no longer be used|"
    r"کلیدِ این سشن را تلگرام", re.I)
NET_FAIL_RE = re.compile(
    r"اتصال برای بررسیِ سشن|اتصال قطع شد|اتصال دوباره|ConnectionError|"
    r"Cannot connect|Connection to Telegram failed|timed out|TimeoutError|"
    r"Auto-reconnect|NetworkError|OSError", re.I)
DEPS_FAIL_RE = re.compile(
    r"Telethon نصب نیست|ModuleNotFoundError|ImportError|No module named", re.I)
CRASH_RE = re.compile(
    r"Traceback \(most recent call last\)|Error:|Exception:", re.I)


def _h(text, limit=1600):
    """متنِ لاگ برای گذاشتن داخل پیامِ HTML تلگرام."""
    try:
        s2 = str(text or "")
    except Exception:
        return ""
    s2 = s2.replace("&", "&amp;").replace("<", "&lt;").replace(">", "&gt;")
    return s2[-limit:] if limit and len(s2) > limit else s2


# فقط نشانه‌های «نسخه‌ی محلیِ دوم». AUTH_KEY_DUPLICATED عمداً این‌جا نیست:
# آن یعنی کلید را تلگرام سوزانده و درمانش لاگینِ دوباره است، نه «سشن سالم».
DUP_FAIL_RE = re.compile(
    r"نسخه‌ی دیگری از همین اکانت|jafj\.run\.lock|"
    r"duplicate(d)? (key|session)|"
    r"two (?:clients|processes|instances)", re.I)


def classify_selfbot_log(tail, rc=None):
    """علتِ توقفِ سلف از آخرین خطوطِ run.log → (نوع, توضیحِ فارسی)."""
    t = tail or ""
    # «کلیدِ سوخته» اول از همه: متنش («اتصال قطع شد»، «وصل نمی‌شود») با شبکه
    # قاطی می‌شود و درمانش هم دقیقاً برعکسِ شبکه است (سشنِ تازه، نه ری‌استارت).
    if rc == 77 or KEY_BURNED_RE.search(t):
        return "keydup", ("کلیدِ این سشن را تلگرام برای همیشه باطل کرده "
                          "(یک سشن از دو IPِ مختلف) — با ری‌استارت درست "
                          "نمی‌شود؛ لاگینِ تازه لازم است")
    # «نسخه‌ی تکراری» بعد از آن: پیامش («اتصال قطع شد») با شبکه و سشن
    # قاطی می‌شود، ولی درمانش کاملاً متفاوت است.
    if rc == 76 or DUP_FAIL_RE.search(t):
        return "dup", ("نسخه‌ی دیگری از همین اکانت هم‌زمان در حال اجرا بود "
                       "(یک سشن، چند پروسه → تلگرام هر دو را قطع می‌کند)")
    if rc == 79:
        return "network", ("شبکه/MTProto از این میزبان باز نمی‌شود "
                           "(هر تلاشِ اتصال شکست خورد)")
    if rc == 78 or SESSION_FAIL_RE.search(t):
        return "session", "سشنِ این اکانت باطل/خارج شده است"
    if DEPS_FAIL_RE.search(t):
        return "deps", ("پایتونی که سلف را اجرا می‌کند telethon ندارد "
                        "(venv یا نصبِ وابستگی‌ها ناقص است)")
    if NET_FAIL_RE.search(t):
        return "network", "به تلگرام وصل نمی‌شود (شبکه/MTProto یا فیلترِ میزبان)"
    if CRASH_RE.search(t):
        return "crash", "سلف با خطا (Traceback) بسته شد"
    if rc is not None:
        return "exit", f"سلف با کدِ خروجِ {rc} بسته شد"
    return "", ""


def selfbot_failure_notice(nm, uid, kind, hint, tail=""):
    """متنِ پیامِ «سلف بالا نیامد» برای مشتری/مدیر (خالص و قابل تست)."""
    first = ""
    for ln in (tail or "").splitlines():
        ln = ln.strip()
        if ln and not ln.startswith(("File ", "~", "=====")):
            first = ln
    body = (f"⚠️ <b>سلف روی این اکانت بالا نیامد</b>\n\n"
            f"👤 {_h(nm, 60)}\n<code>{uid}</code>\n"
            f"🔎 علت: {_h(hint or 'نامعلوم', 200)}\n")
    if first:
        body += f"\n<pre>{_h(first, 300)}</pre>\n"
    if kind == "network":
        body += ("\n💡 اگر این تکرار شد: مطمئن شو **فقط یک نسخه** از این "
                 "اکانت بالاست (دو پروسه روی یک سشن = همین قطعِ مداوم). "
                 "وگرنه شبکه‌ی میزبان MTProto را می‌بندد.\n")
    if kind == "dup":
        body += ("\n💡 دو نسخه هم‌زمان روی همین اکانت اجرا شده بود؛ "
                 "نسخه‌ی اضافه بسته شد و سشن سالم است.\n")
    if kind == "keydup":
        body += ("\n💡 تلگرام این سشن را **سوزانده** (AuthKeyDuplicated): "
                 "یک سشن هم‌زمان از دو IPِ مختلف استفاده شده — معمولاً دو "
                 "نسخه‌ی ربات، دو سرویس، یا ری‌استارتِ هم‌زمانِ دو کانتینر. "
                 "این سشن دیگر هیچ‌وقت وصل نمی‌شود؛ یک‌بار از "
                 "«🚀 راه‌اندازی سلف روی اکانتم» دوباره لاگین کن (کد می‌آید) "
                 "و قبلش مطمئن شو سرویس/نسخه‌ی دیگری روی همین اکانت بالاست "
                 "نیست.\n")
    body += "\n👉 «⚙️ سرویس من» → «📜 گزارش» همه‌ی لاگ را نشان می‌دهد."
    return body


def selfbot_failure_text(msg, tail="", folder="", limit=1000):
    """پیامِ شکست + آخرین خطوطِ لاگِ سلف + مسیرِ پوشه‌ی همان اکانت."""
    out = str(msg or "")
    t = (tail or "").strip()
    if t and t not in ("لاگی نیست.", "خالی"):
        lines = [ln for ln in t.splitlines() if ln.strip()]
        clean = "\n".join(lines)[-limit:]
        if clean:
            out += ("\n\n📜 <b>آخرین خطوطِ سلف</b>\n<pre>"
                    + _h(clean, 0) + "</pre>")
    if folder:
        out += f"\n📂 <code>{_h(folder, 0)}</code>"
    return out


# ═══════════════════════════════════════════════════
#  ناظر پروسه‌ها — هر مشتری یک پروسه‌ی جدا
# ═══════════════════════════════════════════════════
# ═══════════════════════════════════════════════════
#  مهلتِ بوت — چرا هر آپدیت سشن‌ها را می‌سوزاند و این‌جا بسته می‌شود
#
#  گزارشِ واقعیِ کاربر: «هر آپدیت سشن می‌سوزد». علتش این بود که هنگامِ
#  دیپلوی، کانتینرِ تازه در ثانیه‌ی صفر همه‌ی سشن‌ها را وصل می‌کرد، در حالی
#  که کانتینرِ قبلی هنوز زنده بود (در لاگِ خودش: start 17:33:17 و
#  «Server marked as stopping» 17:33:24). دو IP، یک کلید →
#  AuthKeyDuplicated و مرگِ دائمیِ سشن.
#
#  راه‌حل: بعد از بوت، تا JAFJ_RESUME_DELAY (پیش‌فرض ۱۲۰s) هیچ سلفی وصل
#  نشود؛ و اگر نشانه‌ی «خروجِ ناگهانی» یا «اتصالِ خیلی تازه» دیدیم، مهلت
#  بیشتر شود. با JAFJ_RESUME_DELAY=0 یا JAFJ_NO_RESUME_DELAY=1 خاموش است.
RESUME_AT_NAME = ".jafj_resume_at"
LAST_EXIT_NAME = ".jafj_last_exit"
HEARTBEAT_NAME = ".jafj_heartbeat"       # «اجرای قبلی چطور مرد؟»
HEARTBEAT_EVERY = 60
RAM_GATE_MB = 150                        # حاشیه‌ی امن برای کانتینرهای کم‌حافظه؛ پیش از سلفِ تازه
HARD_EXIT_CODES = (137, 143, -9, 9)      # SIGKILL/OOM، SIGTERM، kill
RECENT_CONNECT_WINDOW = 180              # ثانیه
MAX_GRACE = 900


def _read_json_soft(path):
    try:
        with open(path, encoding="utf-8", errors="ignore") as f:
            v = json.load(f)
        return v if isinstance(v, dict) else {}
    except Exception:
        return {}


def _env_off(name):
    return (os.environ.get(name) or "").strip().lower() in ("1", "true", "yes",
                                                            "on", "بله")


def resume_grace_plan(data_dir, env=None, now_ts=None):
    """(ثانیه, دلیل) — چقدر بعد از بوت صبر کنیم تا هیچ سشنی وصل نشود."""
    e = env if env is not None else os.environ
    now_ts = time.time() if now_ts is None else float(now_ts)
    if _env_off("JAFJ_NO_RESUME_DELAY"):
        return 0.0, "خاموش (JAFJ_NO_RESUME_DELAY)"
    try:
        base = float((e.get("JAFJ_RESUME_DELAY") or "120").strip() or 120)
    except Exception:
        base = 120.0
    base = max(0.0, min(float(MAX_GRACE), base))
    if base <= 0:
        return 0.0, "خاموش (JAFJ_RESUME_DELAY=0)"
    why = "مهلتِ بوت"
    # ۱) خروجِ ناگهانی = احتمالِ OOM/کشتنِ پروسه؛ اتصالِ قبلی سمتِ تلگرام
    #    ممکن است هنوز باز باشد → مهلت دو برابر.
    last = _read_json_soft(os.path.join(str(data_dir), LAST_EXIT_NAME))
    try:
        code = int(last.get("code"))
    except Exception:
        code = None
    if code is not None and code in HARD_EXIT_CODES:
        base = min(float(MAX_GRACE), base * 2)
        why = f"خروجِ ناگهانیِ قبلی (code={code}) — احتمالاً OOM/کشتن"
    # ۲) اگر همین چند لحظه پیش سلفی وصل شده بود، هنوز ممکن است نسخه‌ی قبلی
    #    زنده باشد (دیپلویِ روی هم‌افتاده) → حداقل ۱۸۰ ثانیه.
    rec = _read_json_soft(os.path.join(str(data_dir), RESUME_AT_NAME))
    try:
        ts = float(rec.get("ts") or 0)
    except Exception:
        ts = 0.0
    age = now_ts - ts if ts else None
    if age is not None and 0 <= age < RECENT_CONNECT_WINDOW:
        if base < RECENT_CONNECT_WINDOW:
            base = float(RECENT_CONNECT_WINDOW)
        why = (f"آخرین اتصالِ سشن‌ها فقط {int(age)} ثانیه پیش بود — "
               "شاید نسخه‌ی قبلی هنوز زنده است")
    return float(min(float(MAX_GRACE), base)), why


# ═══════════════════════════════════════════════════
#  ضربانِ قلب — «دیروز داشت کار می‌کرد، یهو سرور آفلاین شد» چرا؟
#
#  وقتی کانتینر با کمبودِ حافظه (OOM) یا با Stopِ پنل کشته می‌شود، هیچ
#  کدی اجرا نمی‌شود؛ پس نه crash.log، نه .jafj_last_exit، هیچ‌چیز نمی‌ماند
#  و بوتِ بعدی بی‌خبر است. راه‌حل: هر دقیقه یک فایلِ کوچک با زمان، حافظه‌ی
#  آزاد و تعدادِ سلف‌ها می‌نویسیم. بوتِ بعد با مقایسه‌ی آن با ثبتِ خروج
#  می‌فهمد پروسه «تمیز» مرده یا ناگهانی — و همان را در لاگ می‌گوید.
def total_ram_mb():
    """کلِ حافظه‌ای که **ما** داریم (MB) — اول سقفِ cgroup، بعد meminfo.

    چرا سقفِ کانتینر اول است: انتخابِ خودکارِ حالتِ اجرا (`spawn_mode`) روی
    همین عدد تصمیم می‌گیرد. اگر سقفِ کانتینر ۵۱۲MB باشد ولی میزبان ۳۲GB،
    meminfo عددِ ۳۲GB را می‌دهد، حالتِ «fork» انتخاب می‌شود (~۱۲MB سربارِ
    هر اکانت) و همان لحظه که سلف‌ها بالا می‌آیند OOM می‌شویم — «رم کم
    می‌آورد». با خواندنِ سقفِ کانتینر، روی همین ۵۱۲MB حالتِ shard
    (~۴MB برای هر اکانت) انتخاب می‌شود.
    """
    lim, _use = cgroup_mem_mb()
    if lim:
        return float(lim)
    try:
        with open("/proc/meminfo", encoding="utf-8") as f:
            for line in f:
                if line.startswith("MemTotal:"):
                    return int(line.split()[1]) / 1024.0
    except Exception:
        pass
    return None


# زیرِ این مقدار حافظه، پیش‌فرض «shard» می‌شود: در fork هر اکانت ~۱۱MB
# سربارِ پروسه دارد و برای یک سرورِ ۵۱۲ مگابایتی یعنی ۵۰ اکانت کمتر.
AUTO_SHARD_BELOW_MB = 1536.0


def fork_supported():
    """آیا این سیستم fork واقعی دارد؟ (لینوکس بله، ویندوز نه)"""
    try:
        return bool(hasattr(os, "fork") and os.path.isdir("/proc/self"))
    except Exception:
        return False


def spawn_mode(env=None):
    """«fork» (پیش‌فرض) یا «process» — به‌ترتیب با حافظه‌ی مشترک/جدا.

    پیش‌فرض عمداً fork است: بدونِ این، هر اکانت یک نسخه‌ی کاملِ telethon
    (~۴۰ مگابایت) جدا می‌خورد. کسی که رفتارِ قدیمی را می‌خواهد
    `JAFJ_SPAWN_MODE=process` بگذارد؛ روی ویندوز/بدونِ fork خودکار
    process می‌شود.
    """
    e = env if env is not None else os.environ
    v = (e.get("JAFJ_SPAWN_MODE") or "").strip().lower()
    if v in ("process", "proc", "off", "0", "no", "جدا", "جداگانه"):
        return "process"
    if v in ("shard", "shards", "sharded", "share-proc", "shard-proc",
             "شارد", "یک‌پروسه"):
        return "shard" if fork_supported() else "process"
    if v in ("fork", "forked", "shared", "share", "1", "on", "yes", "اشتراکی"):
        return "fork" if fork_supported() else "process"
    if not fork_supported():
        return "process"
    # پیش‌فرضِ خودکار: روی ماشین‌های کم‌حافظه shard (هر اکانت ~۳.۳MB)،
    # روی بقیه fork (هر اکانت یک پروسه‌ی جدا، خطاها کاملاً جدا).
    total = None
    try:
        raw = (e.get("JAFJ_TOTAL_MB") or "").strip()
        total = float(raw) if raw else total_ram_mb()
    except Exception:
        total = None
    if total is not None and total <= AUTO_SHARD_BELOW_MB:
        return "shard"
    return "fork"


# مصرفِ اندازه‌گیری‌شده‌ی هر سلف (MB) — با همین 95.py، PSS نه RSS:
# «process» = یک پروسه برای هر اکانت، «fork» = حافظه‌ی مشترک (WISPBYTE_FA §۱۲).
# fork: اندازه‌گیریِ پله‌ای ۱ تا ۸ اکانت → هر اکانتِ اضافه ۱۱.۲MB.
PER_ACCOUNT_MB = {"shard": 3, "fork": 12, "process": 62}
# هزینه‌ی پایه‌ی هر **پروسه** (اندازه‌گیری‌شده): هر پروسه‌ای که `telethon` را
# لود می‌کند ~۶۷MB PSS می‌گیرد و این بینِ پروسه‌ها **مشترک نمی‌شود**.
# پس تعدادِ پروسه‌ها از تعدادِ اکانت‌ها مهم‌تر است:
#   ۱ شارد × ۲۴ اکانت = ۸۲MB   ولی   ۴ شارد × ۲ اکانت = ۲۶۷MB
PROC_BASE_MB = {"shard": 67, "fork": 70, "process": 62}
MANAGER_MB = 20              # مدیر در حالتِ پایدار ~۱۷MB (اندازه‌گیری‌شده)
RAM_RESERVE_MB = 96          # برای دیتابیس، پشتیبان و OS


def capacity_estimate(free_mb=None, mode=None, reserve_mb=None, size=None):
    """(چند اکانت جا می‌شود, مصرفِ هر اکانت, حافظه‌ی آزاد).

    مدلِ اندازه‌گیری‌شده:

        process : n × ۶۲MB
        fork    : ۷۰MB (دیمن + اکانتِ اول) + (n−۱) × ۱۲MB
        shard   : ceil(n/size) پروسه × ۶۷MB + n × ۳MB

    نکته‌ی مهم: چون هر **پروسه** ~۶۷MB پایه دارد، در shard تعدادِ پروسه
    (یعنی `JAFJ_SHARD_SIZE`) تعیین‌کننده است، نه تعدادِ اکانت.
    """
    m = mode or spawn_mode()
    per = PER_ACCOUNT_MB.get(m, PER_ACCOUNT_MB["process"])
    base = PROC_BASE_MB.get(m, PROC_BASE_MB["process"])
    res = RAM_RESERVE_MB if reserve_mb is None else float(reserve_mb)
    if free_mb is None:
        try:
            free_mb = mem_available_mb()
        except Exception:
            free_mb = None
    if free_mb is None:
        return None, per, None
    try:
        usable = float(free_mb) - float(res) - MANAGER_MB
    except Exception:
        return None, per, None
    if usable <= 0:
        return 0, per, float(free_mb)
    if m == "process":
        return int(usable // per), per, float(free_mb)
    if m == "fork":
        if usable <= base:
            return 0, per, float(free_mb)
        return int(1 + (usable - base) // per), per, float(free_mb)
    # shard: پرکردنِ پشتِ‌سرِهمِ شاردها
    sz = int(size or shard_size())
    sz = max(1, sz)
    n, shards = 0, 1
    while n < 100000:
        nxt = n + 1
        need_shards = -(-nxt // sz)             # ceil
        if nxt * per + need_shards * base > usable:
            break
        n, shards = nxt, need_shards
    return n, per, float(free_mb)


def proc_pss_mb(pid):
    """سهمِ واقعیِ یک پروسه از حافظه (MB) از /proc/PID/smaps_rollup.

    چرا PSS و نه RSS: با fork، صفحه‌های مشترک در RSSِ **هر** فرزند کامل
    حساب می‌شوند؛ یعنی ۱۰۰ اکانت با RSS «۸ گیگ» نشان می‌دهند در حالی که
    واقعاً ~۱ گیگ برده‌اند. PSS سهمِ هر پروسه از صفحه‌های مشترک را تقسیم
    می‌کند — همان عددی که کرنل/کنترل‌پنل حساب می‌کند.
    """
    try:
        with open(f"/proc/{int(pid)}/smaps_rollup", encoding="utf-8") as f:
            for line in f:
                if line.startswith("Pss:"):
                    return round(int(line.split()[1]) / 1024.0, 1)
    except Exception:
        pass
    return None


def proc_rss_mb(pid):
    """حافظه‌ی واقعیِ یک پروسه (MB) از /proc — None اگر نبود."""
    try:
        with open(f"/proc/{int(pid)}/status", encoding="utf-8") as f:
            for line in f:
                if line.startswith("VmRSS:"):
                    return round(int(line.split()[1]) / 1024.0, 1)
    except Exception:
        pass
    return None


def ram_gate_mb(env=None):
    """حدِ حافظه‌ی آزادِ لازم برای روشن‌کردنِ سلفِ بعدی (۰ = بی‌نگهبان).

    چرا: هر سلف (telethon + asyncio + sqlite) حدودِ ۶۰-۹۰ مگابایت است. وقتی
    حافظه‌ی آزاد ته می‌کشد، کرنل کلِ کانتینر را می‌کشد و «سرور آفلاین»
    می‌شود — یعنی به‌جای یک سرویسِ کم، همه می‌خوابند. بهتر است سلفِ تازه
    بالا نیاید و دلیلش را بگوید.
    """
    e = env if env is not None else os.environ
    try:
        v = float((e.get("JAFJ_MIN_FREE_MB") or "").strip() or RAM_GATE_MB)
    except Exception:
        v = float(RAM_GATE_MB)
    return max(0.0, min(8192.0, v))


def ram_gate_check(env=None):
    """(اجازه؟, حافظه‌ی آزاد, حد) — فقط‌خواندنی و بی‌خطر."""
    limit = ram_gate_mb(env)
    if limit <= 0:
        return True, None, 0.0
    try:
        free = mem_available_mb()
    except Exception:
        free = None
    if free is None:
        return True, None, limit        # نمی‌دانیم → مانع نشو
    return (float(free) >= limit), float(free), limit


def write_heartbeat(data_dir, extra=None):
    """(فایلِ ضربان) — ارزان و بی‌خطر؛ هر خطایی بلعیده می‌شود."""
    rec = {"ts": time.time(), "pid": os.getpid()}
    try:
        rec["free"] = mem_available_mb()
    except Exception:
        rec["free"] = None
    if isinstance(extra, dict):
        rec.update(extra)
    try:
        path = os.path.join(str(data_dir), HEARTBEAT_NAME)
        tmp = path + ".tmp"
        with open(tmp, "w", encoding="utf-8") as f:
            json.dump(rec, f)
        os.replace(tmp, path)
        return rec
    except Exception:
        return rec


def read_heartbeat(data_dir):
    return _read_json_soft(os.path.join(str(data_dir), HEARTBEAT_NAME))


def last_death_report(data_dir, now_ts=None):
    """متنِ «اجرای قبلی چطور تمام شد» ("" = چیزی برای گفتن نیست)."""
    now_ts = time.time() if now_ts is None else float(now_ts)
    hb = read_heartbeat(data_dir)
    try:
        hb_ts = float(hb.get("ts") or 0)
    except Exception:
        hb_ts = 0.0
    if hb_ts <= 0:
        return ""
    ex = _read_json_soft(os.path.join(str(data_dir), LAST_EXIT_NAME))
    try:
        ex_ts = float(ex.get("ts") or 0)
    except Exception:
        ex_ts = 0.0
    try:
        ex_code = int(ex.get("code"))
    except Exception:
        ex_code = None
    age = int(max(0, now_ts - hb_ts))
    clean = ex_ts >= (hb_ts - 5)
    free = hb.get("free")
    clients = hb.get("clients")
    hardy = f"حافظه‌ی آزاد {free}MB، {clients} سلف روشن"
    # دو حالتی که خودِ «نگهبانِ سکوت» پروسه را بست؛ از OOM/Stopِ پنل جدا
    # گفته می‌شوند، وگرنه مدیر فکر می‌کند رم کم آورده و دنبالِ علتِ اشتباه
    # می‌رود.
    stage = str(hb.get("stage") or "")
    if stage == "hang-exit":
        return ("🧯 اجرای قبلی **گیر کرده بود** — حلقه‌ی اصلی "
                f"{age} ثانیه هیچ ضربانی نزد و نگهبان پروسه را بست "
                "(ردِ stack‌ها: hang.log).")
    if stage == "silence-exit":
        return ("🧯 اجرای قبلی بالا بود ولی **به تلگرام جواب نمی‌داد** — "
                "نگهبانِ سکوت خودش پروسه را ری‌استارت کرد "
                "(crash.log → silence).")
    if clean and ex_code not in HARD_EXIT_CODES:
        if age > 600:
            return (f"ℹ️ سرویس حدودِ {age // 60} دقیقه خاموش بود (خروجِ "
                    f"ثبت‌شده: code={ex_code}).")
        return ""
    if clean:
        return (f"🧯 اجرای قبلی با کدِ {ex_code} تمام شد (SIGKILL/OOM یا "
                f"کشته‌شدنِ پروسه) — آخرین ضربان {age} ثانیه پیش ({hardy}).")
    return (f"🧯 اجرای قبلی **بدونِ خروجِ تمیز** تمام شد — آخرین ضربان "
            f"{age} ثانیه پیش ({hardy}). یعنی پروسه ناگهانی کشته شده؛ "
            "معمولاً کمبودِ حافظه (OOM) یا Stop از پنل.")


# ═══════════════════════════════════════════════════
#  نگهبانِ سکوت — «پروسه روشن است، پنل هم می‌گوید online، ولی ربات جواب نمی‌دهد»
#
#  تفاوتِ این حالت با کرش این است که هیچ‌چیز نمی‌میرد: پروسه زنده است،
#  وب‌سرورِ سلامت ۲۰۰ می‌دهد و میزبان هم دلیلی برای ری‌استارت نمی‌بیند؛ فقط
#  اتصالِ MTProto نیمه‌باز مانده یا حلقه‌ی اصلی گیر کرده. از بیرون دقیقاً
#  «منیجر آفلاین شد» دیده می‌شود — و چون کدی اجرا نشده، crash.log هم خالی
#  است. دو نگهبان جلوی این را می‌گیرند:
#
#    ۱) liveness_loop (async): هر JAFJ_PING_SECS یک درخواستِ **واقعی** به
#       تلگرام. شکستِ پیاپی: اول اتصالِ نیمه‌باز بسته می‌شود (serve_forever
#       خودش دوباره وصل می‌کند و هندلرها می‌مانند)، و اگر باز هم جواب نداد
#       پروسه با کدِ ۷۵ می‌بندد تا ناظر نسخه‌ی تازه با اتصالِ تازه بالا بیاورد.
#    ۲) silence_watch (thread): اگر حلقه‌ی اصلی کاملاً قفل شود، ضربان کهنه
#       می‌ماند؛ این thread ردِ stackِ همه‌ی تردها را در hang.log می‌نویسد و
#       پروسه را می‌بندد — وگرنه سرور تا ابد «روشن» می‌ماند.
# ═══════════════════════════════════════════════════
LIVE = {
    "boot": time.time(), "ready": False, "stopping": False,
    "loop": 0.0, "ping": 0.0, "update": 0.0,
    "ping_fail": 0, "last_err": "",
}


def _live_env_num(name, default, lo=0.0, hi=86400.0):
    try:
        v = float((os.environ.get(name) or "").strip() or default)
    except Exception:
        v = float(default)
    return max(lo, min(hi, v))


def ping_seconds():
    """فاصله‌ی پینگِ تلگرام (۰ = نگهبانِ پینگ خاموش)."""
    return _live_env_num("JAFJ_PING_SECS", 120.0, 0.0, 3600.0)


def ping_timeout():
    """هر پینگ چند ثانیه حق دارد بی‌جواب بماند تا «مرده» حساب شود."""
    return _live_env_num("JAFJ_PING_TIMEOUT", 45.0, 5.0, 300.0)


def hang_seconds():
    """اگر حلقه‌ی اصلی این‌قدر ثانیه ضربان نزند، «گیر کرده» حساب می‌شود."""
    return _live_env_num("JAFJ_HANG_SECS", 900.0, 0.0, 86400.0)


def ping_reconnect_after():
    """چند پینگِ ناموفقِ پیاپی → اتصال از نو بسته شود."""
    return int(_live_env_num("JAFJ_PING_RECONNECT", 2.0, 1.0, 100.0))


def ping_restart_after():
    """چند پینگِ ناموفقِ پیاپی → پروسه ری‌استارت شود (کدِ ۷۵)."""
    return int(_live_env_num("JAFJ_PING_RESTART", 4.0, 1.0, 1000.0))


def mark_live(kind="loop", extra=None):
    """یک «نشانه‌ی زنده‌بودنِ واقعی» ثبت کن (ارزان، هر خطایی بلعیده می‌شود).

    kind: loop = حلقه‌ی اصلی کار می‌کند · ping = تلگرام جواب داد ·
          update = پیامی از تلگرام رسید · ping_fail = پینگ شکست خورد.
    """
    try:
        LIVE[kind] = time.time()
    except Exception:
        return
    if kind == "ping_fail":
        try:
            LIVE["ping_fail"] = int((extra or {}).get("fails") or 0)
            LIVE["last_err"] = str((extra or {}).get("err") or "")[:300]
        except Exception:
            pass
    elif kind == "ping":
        try:
            LIVE["ping_fail"] = 0
            LIVE["last_err"] = ""
        except Exception:
            pass


def live_age(kind="loop", now_ts=None):
    """چند ثانیه از آخرین نشانه‌ی این نوع گذشته (None = هرگز)."""
    try:
        ts = float(LIVE.get(kind) or 0)
    except Exception:
        ts = 0.0
    if ts <= 0:
        return None
    now_ts = time.time() if now_ts is None else float(now_ts)
    return max(0.0, now_ts - ts)


def live_snapshot():
    """عکسِ لحظه‌ای از «زنده‌بودنِ واقعی» — برای /version، /livez و /diag."""
    out = {
        "ready": bool(LIVE.get("ready")),
        "stopping": bool(LIVE.get("stopping")),
        "fails": int(LIVE.get("ping_fail") or 0),
        "last_error": str(LIVE.get("last_err") or ""),
        "ping_age": None, "loop_age": None, "update_age": None,
    }
    for k in ("ping", "loop", "update"):
        a = live_age(k)
        if a is not None:
            out[k + "_age"] = int(a)
    return out


def livez_verdict(snap=None, hang=None):
    """(کد, وضعیت) — ۲۰۰ سالم، ۵۰۳ «پروسه هست ولی ربات کار نمی‌کند».

    عمداً `/` و `/healthz` دست‌نخورده می‌مانند (میزبان‌ها و مانیتورِ بیرونی
    به همان ۲۰۰ «JAFJ OK» وابسته‌اند و همین است که سرویس را بیدار نگه
    می‌دارد)؛ این مسیرِ تازه برای مانیتوری است که باید **ری‌استارت** بدهد.
    """
    snap = snap or live_snapshot()
    limit = hang_seconds() if hang is None else float(hang)
    if limit <= 0 or not snap.get("ready") or snap.get("stopping"):
        return 200, "ok"
    age = snap.get("loop_age")
    if age is not None and age >= limit:
        return 503, "stalled"
    if snap.get("fails") and snap.get("fails") >= ping_restart_after():
        return 503, "silent"
    return 200, "ok"


def ping_verdict(fails, reconnect_at=None, restart_at=None):
    """تصمیمِ نگهبان از تعدادِ پینگِ ناموفقِ پیاپی: ok/retry/reconnect/restart."""
    f = int(fails or 0)
    if f <= 0:
        return "ok"
    r = int(reconnect_at if reconnect_at is not None else ping_reconnect_after())
    s = int(restart_at if restart_at is not None else ping_restart_after())
    if s and f >= s:
        return "restart"
    if r and f >= r:
        return "reconnect"
    return "retry"


def _ping_request():
    """یک درخواستِ سبکِ تلگرام برای پینگ (None = نسخه‌ی تلگرام اجازه نمی‌دهد)."""
    try:
        from telethon.tl.functions.help import GetConfigRequest
        return GetConfigRequest()
    except Exception:
        return None


def _silence_evidence(limit, age):
    """شاهدِ «گیر کردن» را جایی بنویس که بوتِ بعدی و /diag ببینند."""
    txt = (f"حلقه‌ی اصلی {int(age)} ثانیه هیچ ضربانی نزد (حدِ مجاز "
           f"{int(limit)}s) — پروسه زنده بود ولی کار نمی‌کرد.")
    try:
        import faulthandler
        with open(os.path.join(str(BASE_DIR), "hang.log"), "a",
                  encoding="utf-8", errors="ignore") as f:
            f.write(f"\n===== {datetime.now():%Y-%m-%d %H:%M:%S} "
                    f"pid={os.getpid()} host={HOST_LABEL} — {txt}\n")
            faulthandler.dump_traceback(all_threads=True, file=f)
    except Exception as e:
        txt += f"\n(ذخیره‌ی stack ناموفق: {type(e).__name__}: {e})"
    try:
        log_crash("hang", txt)
    except Exception:
        pass
    return txt


def _hanglog_text():
    """آخرین شاهد، فقط نام فایل/تابع و شماره خط؛ بدون مسیر، کد یا محتویات لاگ."""
    header = "🧩 <b>گزارش آخرین گیرکردن مدیر</b>\n"
    try:
        with open(os.path.join(str(BASE_DIR), "hang.log"), "rb") as f:
            f.seek(0, os.SEEK_END)
            size = f.tell()
            f.seek(max(0, size - 128 * 1024))
            raw = f.read(128 * 1024).decode("utf-8", "replace")
    except OSError:
        return header + "گزارشی پیدا نشد؛ ممکن است هنوز ثبت نشده یا با پاک شدن دیسک از بین رفته باشد."
    if not raw.strip():
        return header + "گزارش خالی است."
    marker = raw.rfind("\n===== ")
    if marker >= 0:
        raw = raw[marker + 1:]
        partial = False
    else:
        partial = size > 128 * 1024
    date = re.match(r"===== (\d{4}-\d{2}-\d{2} \d{2}:\d{2}:\d{2})", raw)
    lines = []
    frame_re = re.compile(r'^\s*File "([^"\r\n]+)", line (\d{1,9}) in '
                          r'([A-Za-z_][A-Za-z_0-9]{0,79}|<(?:module|lambda|listcomp|dictcomp|setcomp|genexpr)>)\s*$')
    for line in raw.splitlines():
        if re.match(r"^(?:Current thread|Thread) 0x[0-9a-fA-F]+ \(most recent call first\):$", line):
            lines.append("— رشته —")
            continue
        match = frame_re.match(line)
        if not match:
            continue
        name = os.path.basename(match.group(1).replace("\\", "/"))
        func = match.group(3).strip("<>")
        # نام‌های غیرعادی یا شامل شماره‌های طولانی ممکن است شناسه/راز باشند.
        if (not re.fullmatch(r"[A-Za-z_][A-Za-z_0-9.-]{0,79}\.py", name)
                or re.search(r"\d{5,}", name) or re.search(r"\d{5,}", func)):
            name, func = "unknown.py", "unknown"
        lines.append(f"{name}:{match.group(2)} {func}")
    if not lines:
        return header + "گزارش پیدا شد، اما فریم قابل نمایش در آن نیست."
    # انتهای dump معمولاً شامل رشتهٔ اصلی است. اندازه برای پیام تلگرام محدود است.
    selected, used = [], 0
    for line in reversed(lines):
        if used + len(line) + 1 > 3000:
            partial = True
            break
        selected.append(line)
        used += len(line) + 1
    selected.reverse()
    when = ("زمان ثبت: " + date.group(1) + "\n") if date else ""
    truncated = "بخشی از گزارش طولانی حذف شد.\n" if partial else ""
    return (header + when + truncated + "<pre>" + _h("\n".join(selected), 0) + "</pre>\n"
            + "این فقط شاهد لحظهٔ گیرکردن است، نه علت قطعی. بعد از بالا آمدن ربات قابل دریافت است.")


def silence_watch(data_dir=None, step=None):
    """thread: اگر حلقه‌ی اصلی از کار افتاد، پروسه را می‌بندد تا ناظر بالا بیاورد.

    چرا thread و نه asyncio: خودِ حلقه‌ی اصلی موضوعِ مشکوک است؛ اگر قفل شده
    باشد هیچ coroutine‌ای اجرا نمی‌شود. این thread از GIL جدا سود می‌برد و
    در خواب‌های I/O هم اجرا می‌شود.
    """
    limit = hang_seconds()
    if limit <= 0:
        return
    try:
        step = float(step) if step else max(5.0, min(30.0, limit / 4.0))
    except Exception:
        step = max(5.0, min(30.0, limit / 4.0))
    while True:
        time.sleep(step)
        if LIVE.get("stopping") or not LIVE.get("ready"):
            continue
        age = live_age("loop")
        if age is not None and age < limit:
            continue
        if age is None:
            age = 0.0
        txt = _silence_evidence(limit, age)
        print(f"  ⛔ {txt}\n     → پروسه با کدِ ۷۵ بسته می‌شود تا ناظر یک "
              f"نسخه‌ی تازه بالا بیاورد (stack: hang.log)", flush=True)
        try:
            write_heartbeat(data_dir or BASE_DIR,
                            {"stage": "hang-exit", "loop_age": int(age)})
        except Exception:
            pass
        LIVE["stopping"] = True
        os._exit(75)


class Supervisor:
    def __init__(self, cfg, db):
        self.cfg = cfg
        self.db = db
        self.procs = {}          # uid -> Popen
        self.last_failure = {}   # uid -> manager | session | selfbot
        # uid -> توضیحِ فارسیِ علت (برای پیامِ مشتری و /diag)
        self.last_detail = {}
        self._fail_notified = {} # uid -> زمانِ آخرین اطلاع‌رسانیِ شکست
        self._deps_ok = None     # آیا sys.executable می‌تواند telethon را import کند؟
        self.mgr = None          # به Manager وصل می‌شود
        # uid -> {"n": تعداد تلاش‌های ناموفق، "next": زمانِ تلاشِ بعدی}
        # تا پروسه‌ای که فوراً می‌میرد (سشنِ خراب/FloodWait) هر ۳۰ ثانیه
        # دوباره و دوباره اجرا نشود.
        self._resume_fail = {}
        # تا این زمان هیچ سلفی وصل نمی‌شود (مهلتِ بوت؛ بخشِ resume_grace_plan).
        self._grace_until = 0.0
        # از پیش از شروع watchdog تا پایان بوت اولیه، بازیابی خودکار نباید
        # قبل از محاسبه و اعمال مهلت سشن‌ها شروع شود.
        self._startup_boot_pending = threading.Event()
        # قفلِ «بالا آوردنِ همه» — بوتِ خودکار و بازیابیِ دستی نباید هم‌زمان
        # یک سرویس را دو بار ری‌استارت کنند.
        self.boot_lock = threading.Lock()
        # شروعِ دستیِ چند اکانت می‌تواند از event loop و thread بوت هم‌زمان
        # برسد. چکِ RAM بدون این قفل race می‌شود و چند شارد می‌توانند هم‌زمان
        # از همان فضای آزاد استفاده کنند.
        self._start_lock = threading.RLock()
        os.makedirs(CLIENTS_DIR, exist_ok=True)

    # ---------- «باید روشن بماند» ----------
    def set_want(self, uid, on):
        """نیتِ روشن‌بودن را ذخیره می‌کند تا بعد از دیپلوی/ری‌استارت برگردد.

        چرا روی دیسک؟ پروسه‌های سلف فرزندِ همین manager هستند و هر آپدیت کد
        (دیپلوی) همه را می‌کشد. بدون یادآوریِ این نیت، بعد از هر آپدیت مدیر
        باید برای هر مشتری دوباره «روشن کن» بزند.
        """
        try:
            self.db.set_want(uid, on)
        except Exception:
            try:
                self.db.set(uid, want_on=1 if on else 0)
            except Exception:
                pass
        try:
            self.db.log(uid, "want_on" if on else "want_off", "")
        except Exception:
            pass

    def allowed(self, uid):
        """اجازه اجرا دارد؟ (اشتراک یا امتیاز کافی)"""
        if not self.mgr:
            return True, ""
        return self.mgr.can_run(uid)

    def folder(self, uid):
        p = os.path.join(CLIENTS_DIR, str(uid))
        os.makedirs(p, exist_ok=True)
        return p

    # ---------- تبدیل StringSession به فایل .session ----------
    def write_session(self, uid, string_session, keep_existing=True):
        """StringSession را به فایل .session تبدیل می‌کند.

        `keep_existing=True` (پیش‌فرض): اگر فایلِ سالمی از قبل هست، **دست به
        آن نمی‌زنیم**. قبلاً فایلِ زنده پاک و از رشته‌ی داخل DB بازنویسی می‌شد؛
        اگر آن رشته قدیمی‌تر بود، کلیدِ زنده دور ریخته می‌شد، سشن باطل می‌شد و
        سلف برای «روشن شدن» از تلگرام **کدِ ورود** می‌گرفت.
        """
        if not string_session or len(string_session) < 20:
            raise ValueError("سشن خالی یا نامعتبر")
        folder = self.folder(uid)
        path = os.path.join(folder, "jafj.session")
        if keep_existing and os.path.isfile(path):
            ok, _why = session_health(path)
            if ok:
                return path                     # فایلِ سالم را خراب نکن
        from telethon.sessions import StringSession, SQLiteSession
        if os.path.exists(path):
            try:
                os.remove(path)
            except Exception:
                pass
        ss = StringSession(string_session)
        sq = SQLiteSession(path[:-8])       # بدون پسوند
        sq.set_dc(ss.dc_id, ss.server_address, ss.port)
        sq.auth_key = ss.auth_key
        sq.save()
        sq.close()
        return path

    def write_creds(self, uid, phone):
        folder = self.folder(uid)
        with open(os.path.join(folder, "jafj_creds.json"), "w",
                  encoding="utf-8") as f:
            json.dump({"api_id": self.cfg["api_id"],
                       "api_hash": self.cfg["api_hash"],
                       "phone": phone}, f, ensure_ascii=False, indent=2)
        try:
            os.chmod(os.path.join(folder, "jafj_creds.json"), 0o600)
        except Exception:
            pass

    def write_ai(self, uid):
        """اگر خودت کلید AI داری، همان را به سلف مشتری هم بده."""
        src = os.path.abspath("jafj_ai.json")
        if not os.path.exists(src):
            return False
        dst = os.path.join(self.folder(uid), "jafj_ai.json")
        try:
            with open(src, encoding="utf-8") as f:
                cfg = json.load(f)
            if not cfg.get("key"):
                return False
            cfg["pv_answer"] = False          # جواب خودکار PV برای مشتری خاموش
            with open(dst, "w", encoding="utf-8") as f:
                json.dump(cfg, f, ensure_ascii=False, indent=2)
            os.chmod(dst, 0o600)
            return True
        except Exception as e:
            print("write_ai:", e)
            return False

    def write_limits(self, uid, plan=None, points_mode=False,
                     points=None, hours_left=None, override_max_accounts=0):
        """سقف‌های پلن و موجودی امتیاز را برای سلف مشتری می‌نویسد.
        override_max_accounts>0 یعنی سقف اکانتِ سفارشیِ این کاربر (اولویت بر پلن)؛
        0 یعنی از پلن."""
        d = {"plan": "", "max_channels": 1, "max_per_hour": 12,
             "min_gap_sec": 45, "exchange": True, "initiate": True,
             "max_joins_per_day": 0, "ai": False,
             "points": 0, "hours_left": 0, "points_mode": False,
             "expires_at": 0}
        if plan:
            # اولویت: اگر مدیر برای این کاربر سقف اکانتِ خودش را ست کرده (max_accounts>0)،
            # همان ملاک است؛ وگرنه سقفِ پلن (plan.max_accounts).
            mx = 1
            if override_max_accounts > 0:
                mx = int(override_max_accounts)
            else:
                mx = int(plan.get("max_accounts", 1) or 1)
            d.update({
                "plan": plan.get("name", ""),
                "max_channels": max(1, mx),
                "max_per_hour": 12 * max(1, mx),
                "min_gap_sec": 45 if mx <= 1 else 30,
                "initiate": mx >= 2,
                "max_joins_per_day": 0,
                "ai": mx >= 2,
            })
        elif points_mode:
            d.update({
                "plan": "امتیازی", "max_channels": 1,
                "initiate": True, "points_mode": True,
                "points": max(0, int(points or 0)),
                "hours_left": max(0, int(hours_left or 0)),
            })
        try:
            path = os.path.join(self.folder(uid), "jafj_limits.json")
            with open(path, "w", encoding="utf-8") as f:
                json.dump(d, f, ensure_ascii=False, indent=2)
            return True
        except Exception as e:
            print("write_limits:", e)
            return False

    def read_status(self, uid):
        """گزارش زنده‌ای که سلف نوشته."""
        path = os.path.join(self.folder(uid), "jafj_status.json")
        if not os.path.exists(path):
            return None
        try:
            with open(path, encoding="utf-8") as f:
                d = json.load(f)
            d["age"] = now() - d.get("ts", 0)
            return d
        except Exception:
            return None

    def write_defaults(self, uid, max_accounts=1):
        """تنظیمات اولیه سلف — فقط اگر از قبل نبود."""
        dst = os.path.join(self.folder(uid), "jafj_settings.json")
        if os.path.exists(dst):
            return False
        base = {
            "standard": {"mode": "cycle", "active_minutes": 60, "rest_minutes": 30,
                         "max_per_hour": 12, "min_gap_sec": 45, "max_gap_sec": 120,
                         "quiet_hours": [], "channel": ""},
            "vip": {"mode": "always", "active_minutes": 60, "rest_minutes": 15,
                    "max_per_hour": 30, "min_gap_sec": 20, "max_gap_sec": 45,
                    "quiet_hours": [], "channel": ""},
            "paused": False,
            "_max_accounts": max_accounts,
        }
        try:
            with open(dst, "w", encoding="utf-8") as f:
                json.dump(base, f, ensure_ascii=False, indent=2)
            return True
        except Exception as e:
            print("write_defaults:", e)
            return False

    def prepare(self, uid, string_session, phone, max_accounts=1, plan=None):
        self.write_session(uid, string_session)
        self.write_creds(uid, phone)
        self.write_ai(uid)
        self.write_defaults(uid, max_accounts)
        self.write_limits(uid, plan, points_mode=plan is None)
        # کپی سلف در پوشه‌ی مشتری — همیشه نسخه جدید، نسخه قدیمی نمی‌ماند
        ok, err = self.link_selfbot(uid)
        if not ok:
            print("sync selfbot:", err)

    # ---------- همگام‌سازی و کنترل ----------
    def link_selfbot(self, uid):
        """فایل سلف را داخل پوشه مشتری می‌گذارد (symlink، وگرنه کپی).

        نکته حیاتی: مقصد همیشه با SELF_NAME ساخته می‌شود. SELFBOT مسیر
        absolute است و os.path.join(folder, "/app/95.py") پوشه مشتری را
        دور می‌ریزد؛ نتیجه‌اش این بود که فایل مشترک /app/95.py پاک و به
        symlink حلقه‌ای تبدیل می‌شد و بعد از آن هر sync با «فایل 95.py
        پیدا نشد» می‌ترکید.
        """
        src = os.path.abspath(SELFBOT)
        dst = os.path.join(self.folder(uid), SELF_NAME)
        if not os.path.isfile(src):
            _restore_selfbot(src)          # نسخه مرجع ایمیج، بدون ری‌استارت
        if not os.path.isfile(src):
            # پیام باید بگوید مشکل کجاست، نه فقط اینکه فایل نیست.
            hint = ("نسخه‌ی مرجع هست ولی بازسازی نشد؛ دسترسی نوشتن پوشه را چک کن"
                    if os.path.isfile(SELFBOT_REF) else
                    "نسخه‌ی مرجع هم نیست؛ ایمیج قدیمی است — Redeploy بزن")
            return False, (f"فایل {src} پیدا نشد (cwd={os.getcwd()}، "
                           f"مرجع={SELFBOT_REF}) — {hint}")
        if os.path.abspath(dst) == src:          # پوشه مشتری = پوشه سلف
            return True, ""
        try:
            if os.path.lexists(dst):
                os.remove(dst)
            try:
                os.symlink(src, dst)
            except Exception:
                import shutil
                shutil.copy2(src, dst)
            ensure_selfbot_ref(src)
            return True, ""
        except Exception as e:
            return False, str(e)

    def sync_selfbot(self, uid):
        """نسخه فعلی 95.py را داخل پوشه مشتری می‌نویسد و نام‌های قدیمی را پاک می‌کند."""
        folder = self.folder(uid)
        for junk in JUNK_SELF:
            p = os.path.join(folder, junk)
            if os.path.lexists(p):
                try:
                    os.remove(p)
                except Exception:
                    pass
        ok, err = self.link_selfbot(uid)
        if ok:
            src = os.path.abspath(SELFBOT)
            dst = os.path.join(folder, SELF_NAME)
            # اگر لینک/کپی از کار افتاد، لااقل محتوا را مستقیم بنویس
            if not (os.path.isfile(dst) and os.path.getsize(dst) == os.path.getsize(src)):
                try:
                    with open(src, "rb") as f:
                        data = f.read()
                    if os.path.abspath(dst) != src:
                        with open(dst, "wb") as f:
                            f.write(data)
                except Exception as e:
                    return False, str(e)
            return True, ""
        return False, err

    # ---------- ردِ پای پروسه‌ی سلف (زنده‌ماندن بعد از ری‌استارتِ manager) ----------
    def _pidfile(self, uid):
        return os.path.join(self.folder(uid), ".jafj_self.pid")

    def _write_pid(self, uid, pid):
        try:
            with open(self._pidfile(uid), "w", encoding="utf-8") as f:
                f.write(str(int(pid)))
        except Exception:
            pass

    def _clear_pid(self, uid):
        try:
            os.remove(self._pidfile(uid))
        except Exception:
            pass

    def _pid_alive(self, pid):
        try:
            os.kill(int(pid), 0)
            return True
        except ProcessLookupError:
            return False
        except PermissionError:
            return True
        except Exception:
            return False

    def _pid_is_selfbot(self, uid, pid):
        """آیا این PID واقعاً سلفِ همین پوشه است؟ (جلوگیری از PID بازاستفاده‌شده)

        فایلِ pid روی دیسکِ ماندگار می‌ماند، ولی شماره‌ی پروسه‌ها در کانتینرِ
        تازه از نو توزیع می‌شود؛ بدون این بررسی ممکن بود یک پروسه‌ی بی‌ربط
        «پذیرفته» و سرویسِ واقعی هرگز اجرا نشود.
        """
        try:
            with open(f"/proc/{int(pid)}/cmdline", "rb") as f:
                cmd = f.read().replace(b"\x00", b" ").decode("utf-8", "ignore")
        except Exception:
            return True          # بدون /proc (مثلاً BSD) خوش‌بین باش
        base = os.path.basename(SELFBOT or "95.py")
        if base not in cmd and str(uid) not in cmd:
            return False
        try:
            cwd = os.path.abspath(os.readlink(f"/proc/{int(pid)}/cwd"))
            if cwd != os.path.abspath(self.folder(uid)):
                return False
        except Exception:
            pass                 # cwd خوانده نشد → به cmdline بسنده کن
        return True

    def _adopt_orphan(self, uid):
        """پروسه‌ی سلفی که بعد از ری‌استارتِ manager زنده مانده را «بپذیر».

        فرزندهای سلف با start_new_session اجرا می‌شوند، پس اگر فقط manager
        دوباره بالا بیاید (بدون کشته‌شدنِ کانتینر) آن‌ها زنده‌اند. بدون این
        پذیرش، watchdog آن‌ها را «خاموش» می‌دید و نسخه‌ی دوم را اجرا می‌کرد
        (دو سلف هم‌زمان روی یک سشن = خرابیِ سشن و پیام‌های تکراری).
        """
        try:
            with open(self._pidfile(uid), encoding="utf-8") as f:
                pid = int(f.read().strip() or 0)
        except Exception:
            return False
        if not pid or not self._pid_alive(pid) or not self._pid_is_selfbot(uid, pid):
            self._clear_pid(uid)
            return False
        self.procs[uid] = _AdoptedProc(pid)
        self.db.log(uid, "adopt", f"pid={pid}")
        return True

    def _code_changed_since_start(self, uid):
        """آیا 95.py بعد از شروعِ این پروسه عوض شده؟ (یعنی کدِ داخل حافظه کهنه است)"""
        try:
            started = os.path.getmtime(self._pidfile(uid))
            return os.path.getmtime(SELFBOT) > started
        except Exception:
            return True      # نمی‌دانیم → مثل قبل ری‌استارت کن

    # ---------- «این اکانت باید لاگین شود» ----------
    def needs_login(self, uid):
        try:
            return bool((self.db.get(uid) or {}).get("need_login"))
        except Exception:
            return False

    def mark_needs_login(self, uid, reason="سشن باطل است", quarantine=True):
        """اکانت را «نیاز به لاگینِ دوباره» علامت بزن و اجرای خودکارش را ببند.

        چرا want_on=0 هم می‌شود؟ وگرنه watchdog/resume هر ۳۰ ثانیه پروسه را
        بالا می‌آورد و هر بار تلگرام یک **کد ورود** به گوشیِ مشتری می‌فرستد.
        """
        try:
            self.db.set(uid, need_login=1, want_on=0)
        except Exception:
            pass
        try:
            self.db.log(uid, "need_login", str(reason)[:300])
        except Exception:
            pass
        if quarantine:
            try:
                p = os.path.join(self.folder(uid), "jafj.session")
                if os.path.isfile(p):
                    bad = p + ".bad"
                    try:
                        os.replace(p, bad)
                    except Exception:
                        shutil.copy2(p, bad)
                self._clear_pid(uid)
            except Exception:
                pass
        try:
            if self.mgr and hasattr(self.mgr, "_notify_needs_login"):
                self.mgr._notify_needs_login(uid, reason)
        except Exception:
            pass
        return True

    def clear_needs_login(self, uid):
        try:
            self.db.set(uid, need_login=0)
            return True
        except Exception:
            return False

    def verify_session(self, uid, rebuild=True):
        """قبل از اجرا مطمئن شو سشن سالم است → (آماده؟, دلیل).

        اگر فایل نبود/خراب بود، از رشته‌ی داخل DB بازسازی می‌کند (اگر آن هم
        نبود، «نیاز به لاگین»). هیچ اتصالی به تلگرام زده نمی‌شود و هیچ کدی
        نمی‌رود؛ فقط جلوی «کد برای همه» گرفته می‌شود.
        """
        path = os.path.join(self.folder(uid), "jafj.session")
        ok, why = session_health(path)
        if ok:
            return True, ""
        row = None
        try:
            row = self.db.get(uid)
        except Exception:
            row = None
        sess = (row or {}).get("session") or ""
        if rebuild and sess and not os.path.isfile(path + ".bad"):
            try:
                self.write_session(uid, sess, keep_existing=False)
            except Exception as e:
                print(f"  ⚠️ بازسازیِ سشن {uid}: {type(e).__name__}", flush=True)
            ok2, why2 = session_health(path)
            if ok2:
                self.db.log(uid, "session_rebuilt", why or "بدون فایل")
                return True, ""
            why = why2 or why
        if not sess:
            why = why or "سشن ندارد"
        return False, why

    def _burned_session(self, uid, reason="کلیدِ سشن توسط تلگرام باطل شد"):
        """سشنِ سوخته را یک‌سره کنار بگذار (فایل → .bad، رشته‌ی DB پاک).

        چرا رشته‌ی DB هم پاک می‌شود: همین رشته منبعِ «بازسازیِ خودکارِ سشن»
        است؛ اگر بمانَد، هر بوت/بازیابی دوباره همان کلیدِ مرده را می‌سازد و
        حلقه‌ی «بالا نمی‌آید» تکرار می‌شود — با یک کدِ ورودِ اضافی روی
        گوشیِ مشتری. کلیدِ سوخته ارزشِ نگه‌داشتن ندارد.
        """
        try:
            self.mark_needs_login(uid, reason)      # فایل → jafj.session.bad
        except Exception:
            pass
        try:
            self.db.set(uid, session="")
        except Exception:
            pass
        try:
            self.db.log(uid, "session_burned", str(reason)[:300])
        except Exception:
            pass
        return True

    def _session_ok_or_mark(self, uid):
        """(آماده؟, پیام) — قبل از هر start صدا زده می‌شود."""
        ok, why = self.verify_session(uid)
        if ok:
            if self.needs_login(uid):
                self.clear_needs_login(uid)
            return True, ""
        self.mark_needs_login(uid, why)
        return False, ("سشنِ این اکانت معتبر نیست (" + why + ") — کدِ ورود عمداً "
                       "فرستاده نشد. از «🚀 راه‌اندازی سلف روی اکانتم» دوباره "
                       "لاگین کن.")

    # ---------- تشخیص و اطلاع‌رسانیِ «چرا سلف بالا نیامد» ----------
    def _why(self, uid, kind, msg, hint="", tail_n=12):
        """شکست را یک‌دست ثبت کن: علت + آخرین خطوطِ run.log + مسیرِ پوشه.

        `kind` همان چیزی است که بقیه‌ی کد با آن کار می‌کند
        (manager | session | selfbot)، `hint` توضیحِ خواناست.
        """
        self.last_failure[uid] = kind
        try:
            self.last_detail[uid] = (hint or msg or "")[:300]
        except Exception:
            pass
        tail = ""
        try:
            tail = self.tail(uid, tail_n)
        except Exception:
            tail = ""
        try:
            folder = self.folder(uid)
        except Exception:
            folder = ""
        return False, selfbot_failure_text(msg, tail, folder)

    def python_deps_ok(self):
        """آیا مفسری که سلف را اجرا می‌کند telethon دارد؟ (یک‌بار در هر بوت)

        چرا لازم است: اگر venv ساخته نشده باشد، مدیر با همان مفسری اجرا
        می‌شود که سلف را هم اجرا می‌کند؛ ولی سلف بعد از `pip install`ِ
        ناموفق (محیطِ externally-managed) فوراً می‌میرد و هیچ دلیلی هم به
        مشتری نمی‌رسد. این چک قبل از Popen جلوی آن را می‌گیرد.
        """
        if self._deps_ok is not None:
            return self._deps_ok
        try:
            r = subprocess.run([sys.executable, "-c", "import telethon"],
                               stdout=subprocess.DEVNULL,
                               stderr=subprocess.DEVNULL, timeout=30)
            self._deps_ok = (r.returncode == 0)
        except Exception:
            self._deps_ok = False
        return self._deps_ok

    def _watch_start(self, uid, p, delay=None):
        """پروسه‌ی تازه را در ثانیه‌های اول زیرِ نظر بگیر و اگر مرد، بگو چرا.

        `start()` فقط ۱.۲ ثانیه صبر می‌کرد. سلفی که در ثانیه‌ی ۲ یا ۵ (سشن
        باطل، نبودِ telethon، خطای شبکه) می‌مرد «روشن» شمرده می‌شد و مشتری
        هیچ پیامی نمی‌گرفت. این رشته، هم مرگِ دیرتر را می‌بیند و هم
        «گیرکردن در اتصال» را (سلفی که زنده است ولی هیچ‌وقت وصل نمی‌شود،
        پس هرگز پنل نمی‌فرستد).
        """
        if delay is None:
            try:
                delay = float(os.environ.get("JAFJ_START_WATCH", "") or 25)
            except Exception:
                delay = 25.0

        def _run():
            rc = None
            try:
                rc = p.wait(timeout=delay)
            except Exception:
                rc = None                     # هنوز زنده است
            if self.procs.get(uid) is not p:
                return                        # پروسه‌ی دیگری جایگزین شده
            tail = ""
            try:
                tail = self.tail(uid, 25)
            except Exception:
                tail = ""
            kind, hint = classify_selfbot_log(tail, rc)
            if rc is None:
                if not kind:                  # سالم و در حال کار
                    try:
                        self.db.log(uid, "alive", f"{int(delay)}s pid={p.pid}")
                    except Exception:
                        pass
                    return
                # زنده ولی وصل نمی‌شود / در حلقه‌ی تلاش است
                self.last_detail[uid] = hint[:300]
                try:
                    self.db.log(uid, "start_stuck_" + kind, hint)
                except Exception:
                    pass
                self._notify_start_failure(uid, kind, hint, tail)
                return
            self.procs.pop(uid, None)
            self._clear_pid(uid)
            if kind == "keydup":
                self.last_failure[uid] = "session"
                self.last_detail[uid] = hint[:300]
                try:
                    self._burned_session(uid, hint)
                except Exception:
                    pass
            elif kind == "session":
                self.last_failure[uid] = "session"
                self.last_detail[uid] = hint[:300]
                try:
                    self.mark_needs_login(uid, "سشن باطل/خارج‌شده")
                except Exception:
                    pass
            elif kind == "dup":
                # نسخه‌ی تکراری: سشن سالم است؛ فقط یک نسخه باید بماند.
                self.last_failure[uid] = "manager"
                self.last_detail[uid] = hint[:300]
            else:
                self.last_failure[uid] = "selfbot"
                self.last_detail[uid] = hint[:300]
                try:
                    self._bump_fail(uid)
                except Exception:
                    pass
            try:
                self.db.log(uid, "start_failed_" + (kind or "exit"),
                            f"rc={rc} {hint}")
            except Exception:
                pass
            self._notify_start_failure(uid, kind, hint, tail)

        try:
            threading.Thread(target=_run, daemon=True,
                             name=f"jafj-watch-{uid}").start()
        except Exception:
            pass

    def _notify_start_failure(self, uid, kind, hint, tail=""):
        """حداکثر یک‌بار در ساعت: به مشتری و مدیر بگو چرا سلف روشن نشد."""
        if not self.mgr:
            return False
        try:
            now_t = time.time()
            if now_t - float(self._fail_notified.get(uid) or 0) < 3600:
                return False
            self._fail_notified[uid] = now_t
        except Exception:
            pass
        try:
            c = self.db.get(uid) or {}
            nm = c.get("name") or str(uid)
        except Exception:
            nm = str(uid)
        body = selfbot_failure_notice(nm, uid, kind, hint, tail)

        async def _say():
            try:
                await self.mgr.say(uid, body, key=f"startfail:{uid}:{int(now_t // 3600)}")
            except Exception:
                pass
            for a in (self.cfg.get("admin_ids") or []):
                try:
                    await self.mgr.say(
                        a, body + (f"\n📂 <code>{_h(self.folder(uid), 0)}</code>"),
                        key=f"startfail-admin:{uid}:{int(now_t // 3600)}")
                    break
                except Exception:
                    continue

        try:
            loop = getattr(self.mgr, "_loop", None)
            if loop is None:
                return False
            asyncio.run_coroutine_threadsafe(_say(), loop)
            return True
        except Exception:
            return False

    def is_running(self, uid):
        p = self.procs.get(uid)
        if p is None:
            # پروسه‌ای که خودمان نساختیم ولی هنوز زنده است (بعد از ری‌استارت)
            if self._adopt_orphan(uid):
                p = self.procs.get(uid)
            else:
                return False
        return bool(p and p.poll() is None)

    def start(self, uid):
        """شروعِ اتمیک؛ چکِ حافظه و ساختِ پروسه‌ها با هم race نکنند."""
        with self._start_lock:
            return self._start_one(uid)

    def _ram_gate_failure(self, uid):
        """اگر حاشیه‌ی RAM کم است، قبل از کارهای پرهزینه شروع را رد کن."""
        _ok_ram, _free, _limit = ram_gate_check()
        if _ok_ram:
            return None
        try:
            self.db.log(uid, "ram_gate", f"free={_free} limit={_limit}")
        except Exception:
            pass
        try:
            _run = self.running_count()
        except Exception:
            _run = None
        try:
            _kids = self.children_rss()
            _kid_tot = int(round(sum(k[2] for k in _kids))) if _kids else 0
        except Exception:
            _kid_tot = 0
        _short = max(0, int(round(float(_limit) - float(_free))))
        return self._why(
            uid, "manager",
            f"حافظه‌ی آزاد کافی نیست: {int(_free)} مگابایت "
            f"(حدِ لازم {int(_limit)} — {_short} مگابایت کم است). "
            + (f"الان {_run} سلف روشن است و روی‌هم {_kid_tot} مگابایت "
               "می‌خورند. " if _run else "")
            + "یا یکی-دو سلف را خاموش کن، یا پلن/سقفِ حافظه را بالا "
            "ببر، یا `JAFJ_MIN_FREE_MB` را پایین‌تر بگذار (مثلاً ۳۰) — "
            "ولی زیرِ ۳۰ خطرِ OOM و خوابیدنِ کلِ سرور هست؛ نگهبان برای "
            "همین گذاشته شده. (خاموش‌کردنِ کاملِ نگهبان: "
            "JAFJ_MIN_FREE_MB=0)",
            hint="کمبودِ حافظه")

    def _start_one(self, uid):
        self.last_failure.pop(uid, None)
        if self.is_running(uid):
            return True, "از قبل روشن بود"
        if self.mgr and self.running_count() >= int(self.cfg["max_clients"]):
            return self._why(uid, "manager",
                             "ظرفیت اجرای همزمان تکمیل است "
                             f"({self.running_count()}/{self.cfg['max_clients']})")
        # اول حاشیه‌ی RAM را بررسی کن؛ حتی probe وابستگی‌ها، بازسازیِ فایلِ
        # نشست و بالا آوردنِ شارد می‌توانند در میزبانِ ۶۱۲MB جهش کوتاه بسازند.
        _ram_failure = self._ram_gate_failure(uid)
        if _ram_failure is not None:
            return _ram_failure
        folder = self.folder(uid)
        _sess_file = os.path.join(folder, "jafj.session")
        if not os.path.exists(_sess_file):
            # اگر DB سشن دارد ولی فایل نیست (مثلاً بعد از بازیابی پشتیبان)، بازسازی کن
            _c0 = None
            try:
                _c0 = self.db.get(uid) if hasattr(self.db, "get") else None
            except Exception:
                _c0 = None
            if _c0 and _c0.get("session"):
                try:
                    _plan = None
                    try:
                        if self.mgr:
                            _plan = self.mgr.effective_plan(uid)
                    except Exception:
                        _plan = None
                    _mx0 = 1
                    try:
                        if _plan:
                            _mx0 = max(1, int(_plan.get("max_accounts", 1) or 1))
                    except Exception:
                        pass
                    self.prepare(uid, _c0["session"], _c0.get("phone") or "", _mx0, _plan)
                except Exception as e:
                    return self._why(uid, "manager", f"بازسازی سشن نشد: {e}")
                if not os.path.exists(_sess_file):
                    return self._why(uid, "manager", "سشن ندارد")
            else:
                return self._why(
                    uid, "manager",
                    "سشن ندارد — این اکانت هنوز لاگین نشده "
                    "(jafj.session داخلِ پوشه‌ی همین اکانت نیست). "
                    "از «🚀 راه‌اندازی سلف روی اکانتم» لاگین کن.")
        # ── ۱) سشن سالم است؟ (وگرنه سلف برای «روشن شدن» کد می‌گیرد) ──
        ready, why_not = self._session_ok_or_mark(uid)
        if not ready:
            return self._why(uid, "session", why_not, hint="سشن باطل/خارج‌شده")
        # قبل از هر اجرا/ری‌استارت، هم امتیاز و هم محدودیت جدید پلن را Sync کن.
        if self.mgr:
            try:
                plan = self.mgr.effective_plan(uid)
                if plan:
                    self.write_limits(uid, plan)
                else:
                    self.mgr.sync_points_limits(uid)
            except Exception as e:
                self.db.log(uid, "points_sync_failed", str(e))
        ok_sync, sync_err = self.sync_selfbot(uid)
        if not ok_sync:
            return self._why(
                uid, "manager",
                "به‌روزرسانی فایل سلف نشد: " + sync_err + " · "
                + build_stamp() + _self_sync_failure_hint(sync_err),
                hint="فایلِ سلف (95.py) سرِ جایش نیست")
        # ── ۰) پیش‌پرواز: سلف و مفسرِ اجراکننده سالم‌اند؟ ──
        # بدون این، اگر پایتونِ سلف telethon نداشته باشد پروسه بالا می‌آید،
        # در لاگِ خودش می‌نویسد «Telethon نصب نیست» و می‌میرد؛ از بیرون فقط
        # «پنل نمی‌آید» دیده می‌شود.
        if not os.path.isfile(SELFBOT) or os.path.getsize(SELFBOT or "") == 0:
            return self._why(uid, "manager",
                             f"فایلِ سلف نیست یا خالی است: {SELFBOT}",
                             hint="۹۵.py سرِ جایش نیست")
        if not self.python_deps_ok():
            # فقط هشدار، نه توقف: خودِ 95.py اول telethon را نصب می‌کند
            # (pip) و اگر نشد می‌میرد؛ آن مرگ را _watch_start با علتِ
            # «deps» گزارش می‌کند. مسدود کردنِ اجرا اینجا، سلفِ سالمی را که
            # فقط هشدار داده بود از کار می‌انداخت.
            try:
                self.db.log(uid, "deps_missing", f"python={sys.executable}")
            except Exception:
                pass
        logf = open(os.path.join(folder, "run.log"), "a", encoding="utf-8")
        # هدرِ کامل: بدونِ این، «چرا بالا نیامد» فقط با آزمون و خطا فهمیده
        # می‌شد. حالا خودِ لاگ می‌گوید با چه مفسر/مسیری اجرا شده.
        logf.write(f"\n===== start {datetime.now():%Y-%m-%d %H:%M:%S} =====\n")
        try:
            logf.write(f"  python={sys.executable} cwd={folder}\n")
            logf.write(f"  self={SELFBOT} ref={SELFBOT_REF} "
                       f"build={build_stamp()}\n")
        except Exception:
            pass
        logf.flush()
        try:
            # JAFJ_NO_AUTO_LOGIN=1 → سلف هرگز خودش کدِ ورود نمی‌فرستد؛ اگر
            # سشن معتبر نباشد با کدِ ۷۸ خارج می‌شود و ما علامت می‌زنیم.
            _env = dict(os.environ)
            _env.setdefault("JAFJ_NO_AUTO_LOGIN", "1")
            p = None
            if spawn_mode() == "shard" and not getattr(self, "_shard_broken", False):
                # چند اکانت در یک پروسه: ~۳.۳MB به‌ازای هر اکانت (fork: ~۱۱.۲)
                _sd = self.pick_shard()
                _pid, _err = _sd.spawn(
                    folder, os.path.join(folder, "run.log"), uid)
                if _pid:
                    p = _ShardProc(_pid, _sd, uid)
                else:
                    self._shard_broken = True
                    try:
                        print(f"  ⚠️ شارد برای {uid} نشد ({_err}) — از این به "
                              "بعد با پروسه‌ی fork اجرا می‌کنم", flush=True)
                    except Exception:
                        pass
            if (spawn_mode() == "fork" or getattr(self, "_shard_broken", False)) \
                    and p is None and not getattr(self, "_fork_broken", False):
                # حافظه‌ی تلگرام بینِ همه‌ی اکانت‌ها مشترک می‌شود (COW).
                _pid, _err = self.fork_daemon().spawn(
                    folder, os.path.join(folder, "run.log"), uid)
                if _pid:
                    p = _AdoptedProc(_pid, self.fork_daemon())
                else:
                    # یک بار شکست کافی است: وگرنه هر اکانت ۶۰ ثانیه معطلِ
                    # timeout می‌شود و هیچ‌کس بالا نمی‌آید.
                    self._fork_broken = True
                    try:
                        print(f"  ⚠️ fork برای {uid} نشد ({_err}) — از این به "
                              "بعد با پروسه‌ی جدا اجرا می‌کنم تا معطل نشود",
                              flush=True)
                    except Exception:
                        pass
            if p is None:
                p = subprocess.Popen(
                    [sys.executable, SELFBOT],
                    cwd=folder, stdout=logf, stderr=subprocess.STDOUT,
                    stdin=subprocess.DEVNULL, env=_env,
                    start_new_session=True)
        except Exception as e:
            try:
                logf.close()
            except Exception:
                pass
            return self._why(uid, "manager",
                             f"اجرای سلف شکست خورد: {type(e).__name__}: {e}",
                             hint="Popen ناموفق بود")
        self.procs[uid] = p
        self._write_pid(uid, p.pid)      # بمانَد تا بعد از ری‌استارت manager
        try:
            logf.close()
        except Exception:
            pass
        # اجرای Popen به‌تنهایی نشانه سالم‌بودن سلف نیست؛ ممکن است فوراً با
        # Session خراب یا خطای ورود بسته شود. نتیجه اولیه را بررسی می‌کنیم.
        time.sleep(1.2)
        # Preserve the existing initial failure detection for a fresh shard.
        initial_rc = p.poll_confirmed() if isinstance(p, _ShardProc) else p.poll()
        if initial_rc is not None:
            self.procs.pop(uid, None)
            self._clear_pid(uid)
            rc = p.returncode
            raw = self.tail(uid, 12)
            tail = (raw or "").strip().replace("\n", " | ")[-900:]
            self.db.log(uid, "start_failed", f"rc={rc} {tail}")
            kind, hint = classify_selfbot_log(raw, rc)
            if rc == 76 or kind == "dup":
                # نسخه‌ی دوم عمداً بسته شد؛ سشن سالم است و لاگین لازم نیست.
                try:
                    self._bump_fail(uid)
                except Exception:
                    pass
                return self._why(
                    uid, "manager",
                    "دو نسخه از این اکانت هم‌زمان اجرا شده بود؛ نسخه‌ی دوم "
                    "بسته شد تا سشن خراب نشود. اگر بیرون از این سرویس هم یک "
                    "ربات روی همین اکانت بالا است، همان را ببند.",
                    hint=hint or "نسخه‌ی تکراری")
            if rc == 77 or kind == "keydup":
                # کلیدِ سوخته: تنها درمان، لاگینِ تازه است. سشنِ مرده را
                # کنار می‌گذاریم تا دیگر هیچ بوت/بازیابی‌ای از آن بالا نیاید.
                self._burned_session(
                    uid, hint or "کلیدِ سشن توسط تلگرام باطل شده "
                                 "(AuthKeyDuplicated)")
                return self._why(
                    uid, "session",
                    "کلیدِ این سشن را تلگرام برای همیشه باطل کرده "
                    "(یک سشن از دو IPِ مختلف — AuthKeyDuplicated). با "
                    "ری‌استارت درست نمی‌شود: باید یک‌بار از «🚀 راه‌اندازی "
                    "سلف روی اکانتم» دوباره لاگین کنی (کد می‌آید). قبلش "
                    "مطمئن شو نسخه/سرویسِ دیگری روی همین اکانت بالاست نیست.",
                    hint=hint or "کلیدِ سشن باطل شده", tail_n=14)
            if rc == 78 or kind == "session" or _LOGIN_CODE_RE.search(tail or ""):
                # سشن باطل (یا بدتر: یک جایی کد ورود رفته) → دیگر تلاش نکن
                try:
                    self.mark_needs_login(uid, "سشن باطل/خارج‌شده")
                except Exception:
                    pass
                return self._why(
                    uid, "session",
                    "این اکانت باید دوباره لاگین شود — کدِ ورودِ اضافی "
                    "فرستاده نشد و اجرای خودکارش تا لاگین متوقف شد.",
                    hint=hint or "سشن باطل/خارج‌شده")
            reason = hint or "سلف اجرا نشد"
            return self._why(uid, "selfbot",
                             f"سلف اجرا نشد ({reason})؛ Session یا اطلاعات ورود "
                             "را بررسی کن.", hint=reason, tail_n=14)
        # اگر سلف با موفقیت بالا آمد، مهرِ «نیاز به لاگین» برداشته می‌شود
        self.db.set(uid, started_at=now(), want_on=1, need_login=0)
        self._resume_fail.pop(uid, None)
        self.db.log(uid, "start", f"pid={p.pid}")
        self.mark_connected(uid)
        self.last_detail.pop(uid, None)
        # ثانیه‌های اول را زیرِ نظر بگیر: مرگِ دیرتر یا «گیرکردن در اتصال»
        # همین‌جا معلوم می‌شود، نه با صبر کردنِ الکیِ مشتری.
        self._watch_start(uid, p)
        return True, f"روشن شد (pid {p.pid})"

    def stop(self, uid, remember_off=False):
        """خاموش کردن پروسه.

        `remember_off=True` یعنی «این خاموشی عمدی است» — پس روی دیسک ثبت
        می‌شود (`want_on=0`) تا بعد از آپدیت/ری‌استارت خودکار روشن نشود.
        خاموشی‌های سیستمی (انقضا، بن، ری‌استارت) این پرچم را نمی‌گذارند.
        """
        if remember_off:
            try:
                self.set_want(uid, False)
            except Exception:
                pass
        p = self.procs.get(uid)
        if (not p or p.poll() is not None) and self._adopt_orphan(uid):
            p = self.procs.get(uid)
        if not p or p.poll() is not None:
            self.procs.pop(uid, None)
            self._clear_pid(uid)
            return True, "خاموش بود"
        if hasattr(p, "remote_stop"):
            # اکانتِ داخلِ shard: کشتنِ گروهِ پروسه یعنی کشتنِ همه‌ی اکانت‌های
            # همان شارد. باید از خودِ شارد بخواهیم فقط همین یکی را ببندد.
            try:
                p.remote_stop()
            except Exception:
                pass
            self.procs.pop(uid, None)
            self._clear_pid(uid)
            self.db.log(uid, "stop")
            return True, "خاموش شد"
        try:
            os.killpg(os.getpgid(p.pid), signal.SIGTERM)
        except Exception:
            try:
                p.terminate()
            except Exception:
                pass
        for _ in range(20):
            if p.poll() is not None:
                break
            time.sleep(0.25)
        if p.poll() is None:
            try:
                os.killpg(os.getpgid(p.pid), signal.SIGKILL)
            except Exception:
                p.kill()
        self.procs.pop(uid, None)
        self._clear_pid(uid)
        self.db.log(uid, "stop")
        return True, "خاموش شد"

    def jafj_summary(self, uid):
        """خلاصه‌ی وضعیت تنظیمات جفج و تنظیمات/دیتابیس تبادل روی دیسک (بدون ساخت پوشه)."""
        info = {
            "folder_exists": False,
            "files_count": 0,
            "has_settings": False,
            "has_db": False,
            "channel_std": "",
            "channel_vip": "",
            "ex_enabled": False,
            "ex_groups": 0,
            "ex_custom_msgs": 0,
            "ex_rows": 0,
            "queue_rows": 0,
        }
        folder = os.path.join(CLIENTS_DIR, str(uid))
        if not os.path.isdir(folder):
            return info
        info["folder_exists"] = True
        try:
            names = os.listdir(folder)
        except Exception:
            names = []
        info["files_count"] = len(names)
        st_path = os.path.join(folder, "jafj_settings.json")
        db_path = os.path.join(folder, "jafj.db")
        info["has_settings"] = any(n == "jafj_settings.json" or n.startswith("jafj_settings.json.bak") for n in names)
        info["has_db"] = any(n == "jafj.db" or n.startswith("jafj.db.bak") for n in names)
        if os.path.isfile(st_path):
            try:
                with open(st_path, encoding="utf-8") as f:
                    d = json.load(f) or {}
                info["channel_std"] = str((d.get("standard") or {}).get("channel") or "").strip()
                info["channel_vip"] = str((d.get("vip") or {}).get("channel") or "").strip()
                ex = d.get("exchange") or {}
                if isinstance(ex, dict):
                    info["ex_enabled"] = bool(ex.get("enabled"))
                    grps = ex.get("groups") or []
                    info["ex_groups"] = len(grps) if isinstance(grps, list) else 0
                    c_msgs = 0
                    for mk in ("msg_ok", "msg_no", "msg_claim_no", "msg_wait",
                               "msg_nolink", "msg_come", "msg_first"):
                        if str(ex.get(mk) or "").strip():
                            c_msgs += 1
                    info["ex_custom_msgs"] = c_msgs
            except Exception:
                pass
        if os.path.isfile(db_path):
            conn = None
            try:
                conn = sqlite3.connect(db_path, timeout=2.0)
                try:
                    r = conn.execute("SELECT COUNT(*) FROM exchange").fetchone()
                    info["ex_rows"] = int(r[0] or 0) if r else 0
                except Exception:
                    pass
                try:
                    r = conn.execute("SELECT COUNT(*) FROM queue").fetchone()
                    info["queue_rows"] = int(r[0] or 0) if r else 0
                except Exception:
                    pass
            except Exception:
                pass
            finally:
                if conn is not None:
                    try:
                        conn.close()
                    except Exception:
                        pass
        return info

    def wipe_jafj_settings(self, uid, max_accounts=1, recreate_defaults=True):
        """پاک کردن کامل تنظیمات جفج + تنظیمات تبادل + دیتابیس تبادل/صف (با حفظ سشن و اشتراک)."""
        was_running = self.is_running(uid)
        self.stop(uid)
        self.last_failure.pop(uid, None)
        self._resume_fail.pop(uid, None)
        folder = os.path.join(CLIENTS_DIR, str(uid))
        removed = 0
        if os.path.isdir(folder):
            try:
                names = list(os.listdir(folder))
            except Exception:
                names = []
            for fn in names:
                if (fn == "jafj_settings.json"
                        or fn.startswith("jafj_settings.json.")
                        or fn == "jafj.db"
                        or fn.startswith("jafj.db-")
                        or fn.startswith("jafj.db.")
                        or fn == "jafj_status.json"
                        or fn.startswith("jafj_status.json.")
                        or fn in ("jafj.log", "run.log")):
                    fp = os.path.join(folder, fn)
                    try:
                        if os.path.isdir(fp) and not os.path.islink(fp):
                            shutil.rmtree(fp, ignore_errors=True)
                        else:
                            os.remove(fp)
                        removed += 1
                    except Exception:
                        pass
            if recreate_defaults:
                self.write_defaults(uid, max_accounts=max_accounts)
        try:
            touch_data("wipe_jafj")
        except Exception:
            pass
        return {"removed_files": removed, "was_running": was_running}

    def wipe_folder(self, uid):
        """توقف کامل سلف و حذف کل پوشه‌ی کاربر (سشن، تنظیمات جفج، تنظیمات و دیتابیس تبادل، بکاپ‌ها و لاگ‌ها)."""
        self.is_running(uid)
        self.stop(uid)
        self.procs.pop(uid, None)
        self.last_failure.pop(uid, None)
        self._resume_fail.pop(uid, None)
        folder = os.path.join(CLIENTS_DIR, str(uid))
        removed = 0
        if os.path.isdir(folder):
            for _r, _d, files in os.walk(folder):
                removed += len(files)
            shutil.rmtree(folder, ignore_errors=True)
        try:
            touch_data("wipe_folder")
        except Exception:
            pass
        return removed

    def restart(self, uid):
        self.stop(uid)
        time.sleep(1)
        return self.start(uid)

    def tail(self, uid, n=25):
        f = os.path.join(self.folder(uid), "run.log")
        if not os.path.exists(f):
            return "لاگی نیست."
        try:
            with open(f, encoding="utf-8", errors="ignore") as fh:
                lines = fh.readlines()[-n:]
            return "".join(lines)[-3000:] or "خالی"
        except Exception as e:
            return f"خطا: {e}"

    def running_count(self):
        return sum(1 for u in list(self.procs) if self.is_running(u))

    # ---------- نگهبان ----------
    def shard_pool(self):
        """شاردهای ساخته‌شده (هر کدام چند اکانت)."""
        pool = getattr(self, "_shards", None)
        if pool is None:
            pool = []
            self._shards = pool
        return pool

    def pick_shard(self):
        """شاردی که جا دارد؛ اگر همه پر بودند یکی تازه بساز."""
        for d in self.shard_pool():
            try:
                if d.alive() and d.room() > 0:
                    return d
            except Exception:
                continue
        d = ShardDaemon(SELFBOT)
        self.shard_pool().append(d)
        return d

    def fork_daemon(self):
        """دیمنِ fork (یک‌بار ساخته می‌شود)."""
        d = getattr(self, "_forkd", None)
        if d is None:
            d = ForkDaemon(SELFBOT)
            self._forkd = d
        return d

    def children_rss(self):
        """[(uid, pid, MB)] برای سلف‌های روشن + مجموع. برای گزارشِ حافظه."""
        out = []
        for uid, p in list(getattr(self, "procs", {}).items()):
            try:
                if p is None or p.poll() is not None:
                    continue
                if getattr(p, "daemon", None) is not None and hasattr(p, "uid"):
                    # چند اکانت یک پروسه‌اند: PSSِ شارد را بین‌شان تقسیم کن،
                    # وگرنه ۸ اکانت هر کدام «۷۶MB» نشان می‌دهند.
                    _d = p.daemon
                    _n = max(1, len(getattr(_d, "uids", {}) or {}))
                    _tot = proc_pss_mb(p.pid) or proc_rss_mb(p.pid) or 0.0
                    out.append((uid, p.pid, round(_tot / _n, 1)))
                    continue
                mb = proc_pss_mb(p.pid)
                if mb is None:
                    mb = proc_rss_mb(p.pid)
                if mb is not None:
                    out.append((uid, p.pid, mb))
            except Exception:
                continue
        return out

    def mark_connected(self, uid=None):
        """زمانِ آخرین «وصل‌کردنِ سشن» را روی دیسک بنویس.

        چرا روی دیسک و نه در حافظه: نسخه‌ی بعدیِ همین کد (بعد از دیپلوی)
        باید بداند که چند لحظه پیش سلفی وصل شده — یعنی احتمالاً کانتینرِ
        قبلی هنوز زنده است و اتصال‌دادنِ فوری، کلیدِ سشن را می‌سوزاند.
        """
        try:
            p = os.path.join(BASE_DIR, RESUME_AT_NAME)
            tmp = p + ".tmp"
            with open(tmp, "w", encoding="utf-8") as f:
                json.dump({"ts": time.time(), "uid": uid, "pid": os.getpid()}, f)
            os.replace(tmp, p)
        except Exception:
            pass
        return True

    def grace_left(self):
        """چند ثانیه از مهلتِ بوت مانده (۰ = تمام شده)."""
        try:
            return max(0.0, float(self._grace_until or 0) - time.time())
        except Exception:
            return 0.0

    def _bump_fail(self, uid):
        """تلاشِ ناموفق را ثبت کن و دفعه‌ی بعد را عقب بینداز (۶۰s، ۱۲۰s … تا ۱۰m).

        بدون این عقب‌گرد، سرویسی که سشنش خراب است هر ۳۰ ثانیه دوباره اجرا
        می‌شد؛ ولی بدون هیچ تلاشی هم «خودش روشن نمی‌شود». عقب‌گرد هر دو را
        حل می‌کند: سرویس سالم بلافاصله، سرویس خراب حداکثر هر ۱۰ دقیقه یک‌بار.
        """
        e = self._resume_fail.get(uid) or {"n": 0}
        n = int(e.get("n") or 0) + 1
        self._resume_fail[uid] = {"n": n, "next": time.time() + min(600, 60 * n)}

    def resume_wanted(self, log_kind="autorestart", respect_backoff=True,
                      force=False):
        """همه‌ی سرویس‌هایی که «باید روشن باشند» ولی روشن نیستند را بالا بیاورد.

        این همان چیزی است که بعد از هر آپدیت لازم است: پروسه‌های سلف فرزندِ
        manager بودند و با دیپلوی همه مردند. حالا نیتِ «روشن بماند» روی دیسک
        است و این تابع آن را دوباره اجرا می‌کند — بدون اینکه مدیر برای هر
        مشتری «روشن کن» بزند.

        خروجی: (شروع‌شده‌ها, ناموفق‌ها, رد‌شده‌ها) — لیستِ uid/پیام.
        """
        started, failed, skipped = [], [], []
        if self.grace_left() > 0:
            # مهلتِ بوت: هیچ سشنی وصل نشود تا نسخه‌ی قبلی قطعاً از تلگرام
            # جدا شده باشد (دو IP روی یک کلید = سوختنِ دائمیِ سشن).
            return started, failed, skipped
        try:
            rows = self.db.wanted()
        except Exception:
            try:
                rows = self.db.runnable()
            except Exception:
                return started, failed, skipped
        for c in rows:
            uid = c.get("uid")
            if uid is None:
                continue
            if self.is_running(uid):
                continue
            if self.needs_login(uid) and not force:
                # سشن باطل → هیچ تلاشی نکن (هر تلاش = یک کد برای مشتری)
                skipped.append((uid, "نیاز به لاگین"))
                continue
            self.procs.pop(uid, None)
            if respect_backoff:
                st = self._resume_fail.get(uid)
                if st and float(st.get("next") or 0) > time.time():
                    continue
            ok, why = self.allowed(uid)
            if not ok:
                # اعتبار ندارد — «نیت» را پاک نمی‌کنیم؛ با شارژ شدن، خودش می‌آید.
                self._bump_fail(uid)
                self.db.log(uid, "no_credit", why)
                skipped.append((uid, why))
                continue
            try:
                started_ok, msg = self.start(uid)
            except Exception as e:
                started_ok, msg = False, f"{type(e).__name__}: {e}"
            if started_ok:
                started.append(uid)
                self._resume_fail.pop(uid, None)
                try:
                    if self.mgr and self.mgr.shop and not self.mgr.has_sub(uid):
                        # زمان خاموشی نباید به‌عنوان کارکرد امتیازی حساب شود.
                        self.mgr.shop.p_reset_charge(uid)
                except Exception:
                    pass
                try:
                    self.db.set(uid, restarts=(int(c.get("restarts") or 0) + 1))
                except Exception:
                    pass
                self.db.log(uid, log_kind, msg)
            else:
                failed.append((uid, msg))
                self._bump_fail(uid)
                self.db.log(uid, "resume_failed", msg)
        if started or failed:
            print(f"  ♻️ {log_kind}: {len(started)} روشن، {len(failed)} ناموفق، "
                  f"{len(skipped)} بدون اعتبار", flush=True)
        return started, failed, skipped

    def watchdog(self):
        while True:
            try:
                # منقضی‌ها را خاموش کن
                for c in self.db.expired():
                    if self.is_running(c["uid"]):
                        self.stop(c["uid"])
                    self.db.set(c["uid"], status="expired")
                    self.db.log(c["uid"], "expired")

                # افتاده‌ها را بلند کن — فقط اگر اعتبار دارند.
                # اگر همین حالا «بالا آوردنِ همه» در جریان است صبر می‌کنیم؛
                # وگرنه یک سرویس دو بار اجرا می‌شد.
                if (self.cfg["auto_restart"] and not self._startup_boot_pending.is_set()
                        and self.boot_lock.acquire(blocking=False)):
                    try:
                        self.resume_wanted(log_kind="autorestart")
                    finally:
                        self.boot_lock.release()
            except Exception as e:
                print("watchdog:", e)
            time.sleep(30)

    def boot_all(self, force_restart=False):
        """سلف جدید را به همه منتقل می‌کند و سرویس‌های معتبر را از نو بالا می‌آورد.

        فقط سرویس‌هایی که «باید روشن باشند» (`want_on`) — یعنی مشتری خودش
        خاموششان نکرده. سرویسی که همین چند ثانیه پیش با همین کد بالا آمده
        دست نمی‌خورد تا بوتِ دوباره (بعد از بازیابی) آن را بی‌دلیل قطع نکند.
        """
        n = skipped = 0
        try:
            _mode = spawn_mode()
        except Exception:
            _mode = "process"
        if _mode == "fork":
            print("  🧠 حالتِ اجرا: اشتراکی (fork) — تلگرام یک‌بار در رم؛ "
                  "هر اکانتِ اضافه ~۱۱MB به‌جای ~۶۲MB", flush=True)
        elif _mode == "shard":
            print(f"  🧠 حالتِ اجرا: شارد — {shard_size()} اکانت در یک پروسه؛ "
                  "هر اکانتِ اضافه ~۴MB", flush=True)
        skip_why = []                 # [(uid, دلیل)] — برای پیامِ روشن به مدیر
        self._resume_fail.clear()
        try:
            rows = self.db.wanted()
        except Exception:
            rows = self.db.runnable()
        try:
            _cap, _per, _free = capacity_estimate(mode=_mode)
            if _cap is not None:
                print(f"  📊 ظرفیتِ تخمینی: {int(_free)}MB آزاد ÷ ~{_per}MB "
                      f"≈ {_cap} سلف (حالتِ {_mode}) — "
                      f"{len(rows)} اکانت باید روشن باشند", flush=True)
                if len(rows) > _cap:
                    print(f"  ⚠️ با این پلن {len(rows) - _cap} اکانت جا نمی‌شود: "
                          f"یا پلن/حافظه را بالا ببر یا سلف‌ها را کم کن",
                          flush=True)
        except Exception:
            pass
        for c in rows:
            uid = c["uid"]
            if self.needs_login(uid) and not force_restart:
                # سشنِ باطل: بالا آوردنش فقط کدِ ورود برای مشتری می‌سازد.
                skipped += 1
                skip_why.append((uid, "نیاز به لاگین"))
                self.db.log(uid, "boot_skip", "نیاز به لاگین")
                continue
            # اگر از قبل روشن بود: فقط وقتی ری‌استارت کن که کدِ روی دیسک
            # (95.py) بعد از شروعِ آن پروسه عوض شده باشد — یعنی نسخه‌ی
            # درونِ حافظه کهنه است. ری‌استارتِ بی‌دلیل، سرویسِ سالمِ
            # مشتری را بعد از هر بوت قطع می‌کند.
            if self.is_running(uid):
                # بعد از بازیابی، سشن/تنظیماتِ روی دیسک عوض شده و پروسه‌ی
                # در حال اجرا نسخه‌ی قدیمی را در حافظه دارد → ری‌استارتِ اجباری.
                if not force_restart and not self._code_changed_since_start(uid):
                    n += 1          # با همین کد اجرا می‌شود؛ دست نزن
                    continue
                self.stop(uid)
                time.sleep(0.4)
            ok, why = self.allowed(uid)
            if not ok:
                skipped += 1
                skip_why.append((uid, why))
                self.db.log(uid, "boot_skip", why)
                continue
            started, _ = self.start(uid)
            if started:
                n += 1
                if self.mgr and self.mgr.shop:
                    self.mgr.shop.p_reset_charge(uid)
            time.sleep(0.5)
        if skipped:
            # «چرا روشن نکرد؟» باید در همان خط معلوم باشد، نه با حدس. قبلاً
            # همه‌ی دلیل‌ها «بدون اعتبار» گفته می‌شد که گمراه‌کننده بود.
            parts = []
            for uid, why in skip_why[:6]:
                parts.append(f"{uid}: {why}")
            more = "" if len(skip_why) <= 6 else f" · و {len(skip_why) - 6} تای دیگر"
            print(f"  ⏭️ {skipped} سرویس بالا نیامد → " + " · ".join(parts) + more,
                  flush=True)
        if n == 0 and not skipped:
            print("  ℹ️ سرویسی برای بالا آوردن نبود (همه خاموش‌اند یا هیچ "
                  "اکانتی در دیتابیس نیست)", flush=True)
        return n

    def shutdown(self):
        for uid in list(self.procs):
            self.stop(uid)
        try:
            if getattr(self, "_forkd", None) is not None:
                self._forkd.close()
        except Exception:
            pass
        for _sd in list(getattr(self, "_shards", []) or []):
            try:
                _sd.close()
            except Exception:
                pass


# ═══════════════════════════════════════════════════
#  متن‌ها
# ═══════════════════════════════════════════════════
USER_HELP = """📖 <b>دستورها</b>

<b>🛒 خرید</b>
/plans — پلن‌ها و قیمت‌ها
/buy 1 — خرید پلن شماره 1
/buy 1 CODE — خرید با کد تخفیف
/orders — سفارش‌های من
/wallet — کیف پول
/ref — لینک زیرمجموعه‌گیری

<b>🎯 امتیاز و کیف پول</b>
/points — امتیاز من
/packs — خرید امتیاز
/topup 50000 — شارژ کیف پول
/whoami — آیدی عددی من

<b>🎧 پشتیبانی</b>
/ticket متن — ارسال تیکت
/tickets — تیکت‌های من

<b>⚙️ سرویس</b>
/start — شروع و وضعیت
/setup — راه‌اندازی سلف روی اکانتم
/status — وضعیت سرویس من
/on — روشن کردن
/off — خاموش کردن
/restart — راه‌اندازی دوباره
/trial — شروع تست رایگان (مدتش را مدیر تعیین می‌کند)
/log — چند خط آخر گزارش
/cancel — لغو مرحله‌ی فعلی
/help — همین راهنما"""

# متن پیش‌فرضِ «آموزش فعال‌سازی» — تا وقتی مدیر از پنل محتوای خودش را ثبت نکرده
DEFAULT_TUTORIAL = """📚 <b>آموزش فعال‌سازی سلف</b>
━━━━━━━━━━━━━━━
<b>قدم ۱</b> — از منوی اصلی «🚀 راه‌اندازی سلف روی اکانتم» را بزن.

<b>قدم ۲</b> — شماره موبایل ایرانِ اکانتت را تأیید کن و کد ورودی‌ای که تلگرام برایت می‌فرستد را وارد کن.

<b>قدم ۳</b> — سلف بالا می‌آید و از «⚙️ سرویس من» می‌توانی روشنش کنی.

💡 <b>اعتبار</b>
• «🎁 تست رایگان» — بدون هزینه امتحانش کن.
• «🎯 خرید امتیاز» یا «💎 اشتراک ماهانه» — برای استفاده‌ی دائمی.

⚠️ کد ورودی فقط برای خودت می‌آید؛ آن را با کسی به اشتراک نگذار."""

ADMIN_HELP = """🛠 <b>پنل مدیر</b>

/users — لیست مشتری‌ها
/user 123 — جزئیات یک مشتری (uid / @username / شماره)
/ok 123 30 — فعال‌سازی برای 30 روز
/off_user 123 — غیرفعال کردن
/ext 123 15 — تمدید 15 روز
/del 123 — پاک کردن کامل اطلاعات کاربر (حساب + سشن + تنظیمات جفج/تبادل + فروشگاه)
/resetjafj 123 — پاک کردن فقط تنظیمات جفج و تبادل کاربر (حفظ اشتراک و سشن)
/pon 123 /poff 123 — روشن/خاموش کردن پروسه
/plog 123 — لاگ پروسه
/stats — آمار کلی
/say 123 متن — پیام به یک مشتری
/all متن — پیام به همه
/set trial_days 7 — تغییر تنظیمات
/cfg — نمایش تنظیمات
/mlog — رویدادهای اخیر
/hanglog — گزارش آخرین گیرکردن مدیر

<b>🛒 فروشگاه</b>
/pending — سفارش‌های منتظر تأیید
/approve 12 — تأیید سفارش
/deny 12 دلیل — رد سفارش
/order 12 — جزئیات سفارش
/revenue — درآمد
/shopplans — همه پلن‌ها
/addplan نام|روز|قیمت|اکانت|توضیح
/editplan 2 price 200000
/rmplan 2 — حذف پلن
/disc CODE 20 — کد تخفیف 20٪
/disc CODE 0 50000 — تخفیف مبلغی
/discs — لیست کدها
/give 123 50000 — شارژ کیف پول
/acct 123 3 — تعیین سقف اکانت برای یک کاربر (0 = سقفِ پلن)
/gp 123 20 — هدیه امتیاز به یک کاربر
/tk — تیکت‌های باز
/tr 5 متن — جواب تیکت
/card 6037... نام — شماره کارت

<b>🎯 امتیاز</b>
/packs — بسته‌های امتیاز
/addpack نام|امتیاز|قیمت|هدیه
/editpack 2 price 200000
/rmpack 2 — حذف بسته
/gp 123 20 — دادن امتیاز دستی
/pstats — آمار امتیاز
/pset cost_per_hour 2 — تنظیمات
/pset self_error_fee 5 — هزینه خطای خود سلف

<b>🩺 نگهداری</b>
/doctor — بررسی سلامت کل سیستم
/fix — اصلاح خودکار ناهماهنگی‌ها
/sync — بروزرسانی فایل AI مشتری‌ها
/lim 123 — دیدن و تغییر سقف‌های یک مشتری

<b>📦 پشتیبان</b>
/backup یا .backup — گرفتن پشتیبان همین الان
/restore یا .restore — بازیابی از آخرین پشتیبان

<b>♻️ بعد از آپدیت</b>
/onall — همه‌ی سرویس‌هایی که باید روشن باشند را روشن کن
(بعد از هر آپدیت/بازیابی خودکار هم همین کار انجام می‌شود)

<b>🔍 عیب‌یابی</b>
/diag — چرا داده می‌پرد یا چرا کرش می‌کند؟
(دیسک، نسخه‌ی بیرونی، کرش‌های آخر، حافظه)"""



# ═══════════════════════════════════════════════════
#  دکمه‌های شیشه‌ای
# ═══════════════════════════════════════════════════
def B(text, data, style=None):
    """دکمه شیشه‌ای. style: primary(آبی) | success(سبز) | danger(قرمز)
    نیاز به Bot API 9.4 — کلاینت‌های قدیمی دکمه را بی‌رنگ نشان می‌دهند."""
    d = data.encode() if isinstance(data, str) else data
    try:
        from telethon import Button
    except ImportError:
        return ("inline", (text, d), {"style": style} if style else {})
    if style:
        try:
            return Button.inline(text, d, style=style)
        except Exception:
            pass
    return Button.inline(text, d)


def main_menu(is_admin=False, shop_on=True, points_on=True,
              has_session=False, running=False, trial_available=False,
              has_cmds=False, has_hub=True, trial_label="30 دقیقه"):
    rows = []
    # قدم اول همیشه بالا و برجسته
    # این دکمه همیشه باشد تا اکانت خارج‌شده یا اکانت قابل‌تعویض دوباره راه‌اندازی شود.
    rows.append([B("🚀 راه‌اندازی سلف روی اکانتم", "s:setup", "primary")])
    # دکمه تست رایگان همیشه برای تمام کاربران نمایش داده می‌شود
    # (مدتش را مدیر از «🎁 تست رایگان» در پنل تعیین می‌کند)
    rows.append([B(f"🎁 تست رایگان {trial_label}", "m:trial", "success")])
    # دو راه خرید، کنار هم — دکمه‌های خرید امتیاز همیشه نمایش داده می‌شوند
    if shop_on:
        buy = [B("💎 اشتراک ماهانه", "m:plans", "primary"),
               B("🎯 خرید امتیاز", "m:packs", "success")]
        rows.append(buy)
    # سرویس: سبز وقتی روشن است، قرمز وقتی خاموش و آماده‌ی روشن شدن
    svc_style = "success" if running else ("danger" if has_session else "primary")
    rows.append([B("⚙️ سرویس من" + ("  🟢" if running else "  ⚪"), "m:svc",
                   svc_style),
                 B("📊 وضعیت", "m:status", svc_style)])
    # دکمه امتیاز من همیشه نمایش داده می‌شود
    rows.append([B("🎯 امتیاز من", "m:pts", "success")])
    if shop_on:
        rows.append([B("💳 کیف پول", "m:wallet", "primary"),
                     B("🎁 زیرمجموعه", "m:ref", "success")])
        rows.append([B("🧾 سفارش‌ها", "m:orders", "primary"),
                     B("🎧 پشتیبانی", "m:support", "primary")])
    # 🗂 توضیحات — فهرستِ تپ‌کردنیِ همه‌ی توضیحات (هر بخشی که مدیر بسازد)
    if has_hub:
        rows.append([B("🗂 توضیحات", "m:hub", "success")])
    rows.append([B("📚 آموزش فعال‌سازی", "m:tut", "success"),
                 B("📖 راهنما", "m:help")])
    rows.append([B("🎞 نمونه‌های جفج رفتن ربات", "m:samples", "primary")])
    rows.append([B("📜 قوانین ربات", "m:rules")])
    # فقط وقتی مدیر دستوری ثبت کرده باشد؛ وگرنه دکمه‌ی خالی می‌دهد.
    if has_cmds:
        rows.append([B("📋 دستورات آماده", "m:cmds", "success")])
    if is_admin:
        rows.append([B("🛠 پنل مدیر", "a:home", "danger")])
    return rows


def back_btn(to="m:home"):
    return [B("⬅️ بازگشت", to)]


def phone_keyboard(label):
    """کیبورد جمع‌وجور تأیید شماره + بازگشت؛ بعداً با Button.clear حذف می‌شود."""
    from telethon import Button
    try:
        return [[
            Button.request_phone(label, resize=True, single_use=True, persistent=False),
            Button.text("⬅️ بازگشت", resize=True, single_use=True, persistent=False),
        ]]
    except TypeError:
        # سازگاری با نسخه‌های قدیمی Telethon
        return [[Button.request_phone(label), Button.text("⬅️ بازگشت")]]


def clear_reply_keyboard():
    from telethon import Button
    return Button.clear()


def svc_menu(running, has_session, fee=0, sub=False):
    rows = []
    if not has_session:
        rows.append([B("🚀 راه‌اندازی سلف", "s:setup", "primary")])
    else:
        rows.append([B("🔄 ورود دوباره / تعویض اکانت", "s:setup", "primary")])
        if running:
            rows.append([B("⏹ خاموش کردن", "s:off", "danger"),
                         B("🔄 ری‌استارت", "s:restart", "danger")])
        else:
            lbl = "▶️ روشن کردن"
            if fee and not sub:
                lbl += f"  ({_fa_digits(fee)} امتیاز)"
            rows.append([B(lbl, "s:on", "success")])
        rows.append([B("📜 گزارش", "s:log", "primary"),
                     B("🔁 تعویض اکانت", "s:setup", "primary")])
    rows.append(back_btn())
    return rows


def admin_menu(pending=0, tickets=0, trial_on=True):
    p_lbl = "📤 سفارش‌های منتظر" + (f"  ({pending})" if pending else "")
    t_lbl = "🎧 تیکت‌ها" + (f"  ({tickets})" if tickets else "")
    # دکمه حالا صفحه‌ی تنظیمات تست را باز می‌کند (مدت/یادآوری/ریست).
    tr_lbl = "🎁 تست رایگان: " + ("🟢 فعال" if trial_on else "🔴 غیرفعال")
    return [
        [B(p_lbl, "a:pending", "danger" if pending else "primary"),
         B("💰 درآمد", "a:revenue", "success")],
        [B("👥 مشتری‌ها", "a:ulist:0", "primary"),
         B("📊 آمار", "a:stats", "primary")],
        [B("🔍 جستجوی کاربر", "a:ufind", "primary"),
         B("🗑 پاک کردن اطلاعات کاربر", "a:uwipe", "danger")],
        [B("💰 قیمت پلن‌ها", "a:prices", "success"),
         B("🎯 قیمت امتیاز", "a:pkprice", "success")],
        [B("🎟 کد تخفیف", "a:discs", "success"),
         B("📢 پیام همگانی", "a:bcast", "danger")],
        [B(t_lbl, "a:tk", "danger" if tickets else "primary"),
         B("💳 شماره کارت", "a:card", "primary")],
        [B("🎯 آمار امتیاز", "a:pstats", "success"),
         B("🩺 سلامت سیستم", "a:doctor", "success")],
        [B("🔍 عیب‌یابی (کرش/دیسک/پشتیبان)", "a:diag", "primary")],
        [B("🎬 آموزش فعال‌سازی", "a:tut", "success"),
         B("🧩 بخش‌های آموزش", "a:secs", "success")],
        [B("🗂 توضیحات (فهرست تپ‌کردنی)", "a:hub", "success"),
         B("📜 قوانین ربات", "a:rules", "primary")],
        [B("📝 متن خوش‌آمدگویی", "a:welcome", "primary"),
         B(tr_lbl, "a:trial", "success" if trial_on else "danger")],
        [B("🎞 نمونه‌های جفج رفتن ربات", "a:samples", "primary")],
        [B("📝 متن‌های ربات", "a:rt", "success"),
         B("📋 دستورات آماده", "a:cm", "success")],
        [B("📣 جوین اجباری", "a:fjoin", "danger"),
         B("📜 رویدادها", "a:mlog", "primary")],
        [B("📦 بک‌آپ", "a:backup", "success"),
         B("♻️ بازیابی", "a:restore", "danger")],
        [B("🟢 روشن کردن همه سرویس‌ها", "a:onall", "success")],
        back_btn(),
    ]


class _BackupCpuPacer:
    """سهم CPU تردِ بک‌آپ را در Wispbyte پخش می‌کند، نه CPU کل کانتینر را.

    این محدودکننده تضمین سقف کل نمی‌دهد: سایر تردها و سلف‌ها مستقل‌اند.
    برای پشتیبان پایانیِ SIGTERM عمداً مکث نمی‌کنیم تا فرصت ارسال از بین نرود.
    """
    def __init__(self, manager):
        self.manager = manager
        default = "8" if (os.environ.get("JAFJ_HOST_LABEL") or "").strip().lower() == "wispbyte" else "0"
        try:
            percent = float(os.environ.get("JAFJ_BACKUP_CPU_PERCENT", default))
            if not (0 <= percent <= 100):
                raise ValueError("invalid percentage")
        except (TypeError, ValueError):
            percent = float(default)
        self.fraction = percent / 100.0
        self.enabled = self.fraction > 0 and callable(getattr(time, "thread_time", None))
        self.wall = time.monotonic()
        self.cpu = time.thread_time() if self.enabled else 0.0

    def checkpoint(self):
        if not self.enabled:
            return
        wall = time.monotonic()
        cpu = time.thread_time()
        if not getattr(self.manager, "_stopping", False):
            # انتظار طولانی I/O به اعتبار نامحدود برای جهش CPU تبدیل نشود.
            wall_elapsed = min(0.05, max(0.0, wall - self.wall))
            delay = max(0.0, (cpu - self.cpu) / self.fraction - wall_elapsed)
            if delay:
                time.sleep(delay)
        self.wall = time.monotonic()
        self.cpu = time.thread_time()


# ── نمونه‌برداری سبک CPU؛ درصد = سهم از یک هسته، نه درصد سهمیه ──
_CPU_ACTIVITY_LOCK = threading.Lock()
_CPU_ACTIVITIES = []


def _cpu_mark_activity(label):
    """بازه‌های کوتاه بک‌آپ را برای تطبیق با نمونه CPU نگه دار، نه محتوای داده را."""
    def decorate(fn):
        @functools.wraps(fn)
        def wrapped(*args, **kwargs):
            item = [label, time.monotonic(), None]
            with _CPU_ACTIVITY_LOCK:
                _CPU_ACTIVITIES.append(item)
                del _CPU_ACTIVITIES[:-64]
            try:
                return fn(*args, **kwargs)
            finally:
                with _CPU_ACTIVITY_LOCK:
                    item[2] = time.monotonic()
        return wrapped
    return decorate


def _cpu_activities_between(start, end):
    with _CPU_ACTIVITY_LOCK:
        return sorted({label for label, begin, finish in _CPU_ACTIVITIES
                       if begin <= end and (finish is None or finish >= start)})


def _cpu_cgroup_dir(root="/sys/fs/cgroup", proc_cgroup="/proc/self/cgroup"):
    """مسیر خود کانتینر، نه مجموعِ CPU ماشین میزبان. cgroup v1/v2."""
    candidates = []
    nested_group = False
    found_group = False
    try:
        with open(proc_cgroup, encoding="utf-8") as f:
            for line in f:
                parts = line.strip().split(":", 2)
                if len(parts) != 3:
                    continue
                _, controllers, group = parts
                segments = [p for p in group.split("/") if p not in ("", ".", "..")]
                if not controllers:
                    found_group = True
                    nested_group = nested_group or bool(segments)
                    candidates.append((os.path.join(root, *segments), "v2"))
                elif "cpuacct" in controllers.split(","):
                    found_group = True
                    nested_group = nested_group or bool(segments)
                    for name in ("cpuacct", "cpu,cpuacct", "cpuacct,cpu", ""):
                        candidates.append((os.path.join(root, name, *segments), "v1"))
    except OSError:
        pass
    if not found_group:
        return None, None
    # در namespace کانتینر اغلب cgroup خودش به ریشه mount شده است.
    fallbacks = [(root, "v2")] + [(os.path.join(root, name), "v1")
                                   for name in ("cpuacct", "cpu,cpuacct", "cpuacct,cpu", "")]
    # فقط اگر PID خودمان در ریشه باشد، ریشه را به‌جای گروه تو‌در‌تو بگیر؛
    # وگرنه ممکن است مصرف تمام میزبان را اشتباه به برنامه نسبت دهیم.
    for path, version in fallbacks:
        if nested_group:
            try:
                with open(os.path.join(path, "cgroup.procs"), encoding="ascii") as f:
                    if str(os.getpid()) not in f.read().split():
                        continue
            except OSError:
                continue
        candidates.append((path, version))
    for path, version in candidates:
        name = "cpu.stat" if version == "v2" else "cpuacct.usage"
        if os.path.isfile(os.path.join(path, name)) and _cpu_group_seconds(path, version) is not None:
            return path, version
    return None, None


def _cpu_group_seconds(path, version):
    try:
        if version == "v2":
            with open(os.path.join(path, "cpu.stat"), encoding="ascii") as f:
                for line in f:
                    key, _, value = line.partition(" ")
                    if key == "usage_usec":
                        return int(value.strip()) / 1000000.0
        elif version == "v1":
            with open(os.path.join(path, "cpuacct.usage"), encoding="ascii") as f:
                return int(f.read().strip()) / 1000000000.0
    except (OSError, ValueError):
        pass
    return None


def _cpu_proc_sample(group_dir, proc_root="/proc", manager_pid=None):
    """فقط PIDهای همین cgroup؛ مقدار هر پروسه و برچسب بدون مسیر/آیدی مشتری."""
    manager_pid = manager_pid if manager_pid is not None else os.getpid()
    try:
        with open(os.path.join(group_dir, "cgroup.procs"), encoding="ascii") as f:
            pids = [int(line) for line in f if line.strip().isdigit()]
        ticks = os.sysconf("SC_CLK_TCK")
    except (OSError, ValueError, AttributeError):
        return {}
    result = {}
    for pid in pids:
        try:
            with open(os.path.join(proc_root, str(pid), "stat"), encoding="ascii") as f:
                stat = f.read()
            # comm می‌تواند حاوی فاصله یا پرانتز باشد؛ از آخرین ) جدا کن.
            fields = stat[stat.rfind(")") + 2:].split()
            seconds = (int(fields[11]) + int(fields[12])) / float(ticks)
            start = int(fields[19])
            if pid == manager_pid:
                label = "مدیر"
            else:
                with open(os.path.join(proc_root, str(pid), "cmdline"), "rb") as f:
                    args = f.read(8192).replace(b"\0", b" ").lower()
                label = ("سلف‌ها/شارد" if any(x in args for x in
                         (b"95.py", b"jafj_shardd.py", b"jafj_forkd.py"))
                         else "سایر پروسه‌ها")
            result[pid] = (start, seconds, label)
        except (OSError, ValueError, IndexError):
            continue
    return result


def _cpu_proc_deltas(old, new, elapsed):
    groups = {}
    if elapsed <= 0:
        return groups
    for pid, (start, cpu, label) in new.items():
        previous = old.get(pid)
        if previous and previous[0] == start and cpu >= previous[1]:
            groups[label] = groups.get(label, 0.0) + 100.0 * (cpu - previous[1]) / elapsed
    return groups


def _cpu_alert_text(sample):
    parts = ["⚠️ گزارش مصرف CPU",
             "زمان ثبت: " + sample.get("when", "نامشخص"),
             f"مصرف کل: {sample['total']:.1f}٪ از یک هسته (میانگین {sample['seconds']:.1f} ثانیه)"]
    groups = sample.get("groups") or {}
    if groups:
        parts.append("پروسه‌های قابل اندازه‌گیری: " + "، ".join(
            f"{label}: {value:.1f}٪" for label, value in
            sorted(groups.items(), key=lambda item: -item[1])))
    else:
        parts.append("تفکیک پروسه‌ها در این نمونه در دسترس نبود.")
    activities = sample.get("activities") or []
    parts.append("هم‌زمان با جهش: " + ("، ".join(activities) if activities
                                       else "بک‌آپ در بخش‌های رصدشده دیده نشد"))
    parts.append("هم‌زمانی به معنی اثبات علت نیست؛ علت دقیق ممکن است نامشخص باشد. "
                 "پروسه‌های کوتاه‌عمر ممکن است در تفکیک دیده نشوند.")
    return "\n".join(parts)


# ═══════════════════════════════════════════════════
#  ربات
# ═══════════════════════════════════════════════════
class Manager:
    def __init__(self):
        self.cfg = Config()
        self.db = DB()
        self.sup = Supervisor(self.cfg, self.db)
        self.sup.mgr = self
        self.shop = Shop()
        self._receipts = {}
        self._live = set()      # آیدی پیام‌هایی که همین نشست ساخته‌ایم
        self._sent_ids = set()  # همه‌ی پیام‌های فرستاده‌ی این نمونه (تشخیص زامبی)
        self.boot_at = now()    # زمان بالا آمدن
        self.fsm = {}            # uid -> {"step":..., "client":..., "phone":...}
        self.bot = None
        self._join_ok = {}       # uid -> expire ts cache
        self._say_last = {}      # کش ضد تکرار say (روی self نه روی bound method)
        self._backup_fp_loaded = False   # اثرانگشتِ خوانده‌شده از دیسک؟
        self._backup_msg_id = None       # آیدی «تک‌پیامِ» پشتیبان در پیوی
        self._backup_msg_chat = None     # کلیدِ چتِ همان پیام (برای getMessages)
        self._backup_extra_cleaned = False  # پاک‌سازیِ یکباره‌ی پیام‌های اضافی قدیمی
        self._restore_tries = 0          # چند تلاشِ بازیابی موقع بوت انجام شد
        self._boot_last = (0, 0, 0)      # (شروع‌شده, ناموفق, بدون‌اعتبار)
        self._loop = None                # حلقه‌ی asyncio (در run ست می‌شود)
        # ── پایداریِ داده در برابر کرش ──
        self._sync_lock = threading.Lock()
        self._dirty_at = 0.0             # آخرین تغییرِ مهم
        self._dirty_reason = ""
        self._flush_thread = None
        self._last_flush = 0.0           # آخرین pushِ موفق (throttle)
        self._flushed_on_exit = False
        self._crash_hooks_done = False
        self._boot_notice = []           # خطوطِ هشدار برای پیامِ «بالا آمد»
        self._cpu_report_lock = threading.Lock()
        self._cpu_report_in_flight = False
        self._cpu_monitor_started = False
        self._cpu_monitor_stop = threading.Event()

    # ---------- گزارش CPU به مدیر؛ بدون تغییر در زمان‌بندی سلف ----------
    def _cpu_pending_path(self):
        return os.path.join(BASE_DIR, ".jafj_cpu_alert.json")

    def _cpu_save_report(self, text):
        report = {"id": str(time.time_ns()), "text": text}
        path = self._cpu_pending_path()
        with self._cpu_report_lock:
            try:
                os.makedirs(os.path.dirname(path), exist_ok=True)
                tmp = path + ".tmp"
                with open(tmp, "w", encoding="utf-8") as f:
                    json.dump(report, f, ensure_ascii=False)
                    f.flush()
                    os.fsync(f.fileno())
                os.replace(tmp, path)
            except OSError as e:
                print(f"  ⚠️ ذخیره گزارش CPU: {type(e).__name__}", flush=True)
        return report

    def _cpu_load_report(self):
        with self._cpu_report_lock:
            try:
                with open(self._cpu_pending_path(), encoding="utf-8") as f:
                    data = json.load(f)
                if isinstance(data, dict) and data.get("id") and isinstance(data.get("text"), str):
                    return data
            except (OSError, ValueError):
                pass
        return None

    def _cpu_queue_report(self, report=None):
        """ارسال async به مدیر؛ در صورت شکست فایل می‌ماند و بعداً retry می‌شود."""
        if self.bot is None or self._loop is None or self._loop.is_closed():
            return False
        report = report or self._cpu_load_report()
        if not report:
            return False
        with self._cpu_report_lock:
            if self._cpu_report_in_flight:
                return False
            self._cpu_report_in_flight = True

        async def send():
            delivered = False
            try:
                for admin in list(self.cfg.get("admin_ids") or []):
                    try:
                        delivered = await self.say(admin, report["text"], key="cpu:" + report["id"]) or delivered
                    except Exception:
                        continue
                if delivered:
                    with self._cpu_report_lock:
                        try:
                            with open(self._cpu_pending_path(), encoding="utf-8") as f:
                                current = json.load(f)
                            if current.get("id") == report["id"]:
                                os.remove(self._cpu_pending_path())
                        except (OSError, ValueError, AttributeError):
                            pass
                else:
                    print("  ⚠️ گزارش CPU ارسال نشد؛ برای تلاش بعدی نگه داشته شد.", flush=True)
            finally:
                with self._cpu_report_lock:
                    self._cpu_report_in_flight = False

        coro = send()
        try:
            asyncio.run_coroutine_threadsafe(coro, self._loop)
            return True
        except Exception:
            coro.close()
            with self._cpu_report_lock:
                self._cpu_report_in_flight = False
            return False

    def _start_cpu_monitor(self):
        """یک thread نمونه‌بردار مستقل از asyncio، پیش‌فرض فقط برای Wispbyte."""
        flag = (os.environ.get("JAFJ_CPU_MONITOR") or "").strip().lower()
        if not flag:
            flag = "1" if (os.environ.get("JAFJ_HOST_LABEL") or "").strip().lower() == "wispbyte" else "0"
        if flag not in ("1", "true", "yes", "on") or self._cpu_monitor_started:
            return
        self._cpu_queue_report()  # گزارش قبلی حتی اگر cgroup دیگر در دسترس نباشد
        group, version = _cpu_cgroup_dir()
        if not group or _cpu_group_seconds(group, version) is None:
            print("  ⚠️ گزارش CPU فعال نشد: آمار cgroup در دسترس نیست.", flush=True)
            return
        def setting(name, default, minimum, maximum):
            try:
                value = float(os.environ.get(name, "") or default)
                if not (minimum <= value <= maximum):
                    return default
                return value
            except (TypeError, ValueError):
                return default
        threshold = setting("JAFJ_CPU_ALERT_PERCENT", 25.0, 1.0, 1000.0)
        interval = setting("JAFJ_CPU_SAMPLE_SECONDS", 3.0, 1.0, 60.0)
        cooldown = setting("JAFJ_CPU_ALERT_COOLDOWN", 300.0, 30.0, 86400.0)
        self._cpu_monitor_started = True

        def worker():
            previous_cpu = _cpu_group_seconds(group, version)
            previous_procs = _cpu_proc_sample(group)
            previous_time = time.monotonic()
            last_alert = -float("inf")
            last_retry = -float("inf")
            while not self._cpu_monitor_stop.wait(interval):
                try:
                    current_time = time.monotonic()
                    current_cpu = _cpu_group_seconds(group, version)
                    current_procs = _cpu_proc_sample(group)
                    elapsed = current_time - previous_time
                    if (current_cpu is not None and previous_cpu is not None
                            and current_cpu >= previous_cpu and elapsed > 0):
                        total = 100.0 * (current_cpu - previous_cpu) / elapsed
                        if total >= threshold and current_time - last_alert >= cooldown:
                            sample = {"total": total, "seconds": elapsed,
                                      "when": time.strftime("%Y-%m-%d %H:%M:%S %Z"),
                                      "groups": _cpu_proc_deltas(previous_procs, current_procs, elapsed),
                                      "activities": _cpu_activities_between(previous_time, current_time)}
                            text = _cpu_alert_text(sample)
                            print("  " + text.replace("\n", " | "), flush=True)
                            report = self._cpu_save_report(text)
                            self._cpu_queue_report(report)
                            last_alert = current_time
                            last_retry = current_time
                    previous_time, previous_cpu, previous_procs = current_time, current_cpu, current_procs
                    if current_time - last_retry >= 60:
                        self._cpu_queue_report()
                        last_retry = current_time
                except Exception as e:
                    print(f"  ⚠️ نمونه‌برداری CPU: {type(e).__name__}", flush=True)

        threading.Thread(target=worker, name="jafj-cpu-monitor", daemon=True).start()
        print(f"  📊 گزارش CPU روشن: آستانه {threshold:g}٪ از یک هسته، نمونه {interval:g} ثانیه", flush=True)

    # ---------- پایداریِ داده (کرش نباید اطلاعات را ببرد) ----------
    def _gh_sync_cmd(self):
        """فرمانِ pushِ سینکِ گیت‌هاب، یا None اگر توکن/ابزار نبود."""
        if not (os.environ.get("DATA_GITHUB_TOKEN") or "").strip():
            return None
        tool = os.path.join(image_dir(), "tools", "gh_data_sync.py")
        if not os.path.isfile(tool):
            tool = os.path.join(os.path.dirname(os.path.abspath(__file__)),
                                "tools", "gh_data_sync.py")
        if not os.path.isfile(tool):
            return None
        return [sys.executable, tool, "push"]

    def _run_gh_sync(self, why="", timeout=180):
        """pushِ همگام (در thread جدا صدا زده می‌شود؛ قفل دارد)."""
        cmd = self._gh_sync_cmd()
        if not cmd:
            return False
        if not self._sync_lock.acquire(timeout=5):
            print("  ☁️ سینکِ گیت‌هاب: یک pushِ دیگر در حال اجراست — رد شد",
                  flush=True)
            return False
        try:
            r = subprocess.run(cmd, capture_output=True, text=True,
                              timeout=max(20, int(timeout)))
            out = ((r.stdout or "") + (r.stderr or "")).strip()
            ok = (r.returncode == 0)
            print(f"  {'☁️' if ok else '⚠️'} سینکِ گیت‌هاب ({why or 'دوره‌ای'}): "
                  f"{out[-300:]}", flush=True)
            if ok:
                self._last_flush = time.time()
                # همین لحظه یک نسخه‌ی تازه از کانفیگ بگیر: اگر بعداً نسخه‌ی
                # قدیمی از راه برسد، تازه‌ترین حالتِ بخش‌ها در تاریخچه هست.
                try:
                    cfg_snapshot_throttled("gh-sync")
                except Exception:
                    pass
            return ok
        except Exception as e:
            print(f"  ⚠️ سینکِ گیت‌هاب ({why or 'دوره‌ای'}): "
                  f"{type(e).__name__}: {e}", flush=True)
            return False
        finally:
            self._sync_lock.release()

    def _push_gh_sync(self, why=""):
        """push در پس‌زمینه (بدون بلاک‌کردنِ ربات)."""
        if not self._gh_sync_cmd():
            return False
        threading.Thread(target=self._run_gh_sync, args=(why,),
                         daemon=True).start()
        return True

    def _flush_durable(self, why="", timeout=180, force=False):
        """همین حالا داده را بیرون از این ماشین ذخیره کن.

        فقط گیت‌هاب (اگر توکن هست) — چون فقط همان از «پاک‌شدنِ دیسک» جان
        سالم به‌در می‌برد. throttle دارد تا تغییرهای پشتِ‌سرهم، push نسازند.
        """
        if self._gh_sync_cmd():
            if not force and (time.time() - self._last_flush) < 45:
                return False
            return self._run_gh_sync(why or "تغییرِ داده", timeout=timeout)
        # ── بدون گیت‌هاب: تنها نسخه‌ی بیرونی، پیامِ پشتیبان در تلگرام است ──
        # پس بعد از هر تغییرِ مهم (با فاصله‌ی حداقل ۲ دقیقه) همان تک‌پیام
        # به‌روز می‌شود. کرشِ ناگهانی حداکثر ~۲ دقیقه داده را می‌برد، نه کلِ
        # آن روز. (فقط یک بار در هر ۲ دقیقه، وگرنه FloodWait می‌خوریم.)
        if self.bot is None or self._loop is None:
            return False
        if not force and (time.time() - self._last_flush) < 120:
            return False

        async def _tg():
            try:
                ok, msg = await self.backup_once(force=False)
                if ok:
                    self._last_flush = time.time()
                elif "بدون تغییر" not in (msg or ""):
                    print(f"  ℹ️ پشتیبانِ فوری ({why or 'تغییر'}): {msg}",
                          flush=True)
            except Exception as e:
                print(f"  ⚠️ پشتیبانِ فوری: {type(e).__name__}: {e}", flush=True)

        try:
            asyncio.run_coroutine_threadsafe(_tg(), self._loop)
            return True
        except Exception as e:
            print(f"  ⚠️ پشتیبانِ فوری: {type(e).__name__}", flush=True)
            return False

    def _touch_data(self, reason=""):
        """تغییرِ مهم ثبت شد → یک flushِ کوتاهِ تأخیری (debounce) بزن.

        تأخیر عمدی است: ثبتِ سشن/تنظیمات معمولاً چند نوشتنِ پشتِ‌سرهم دارد و
        نمی‌خواهیم برای هر کدام یک push برود. ۲۰ ثانیه بعد از «آخرین»
        تغییر می‌رود، پس حداکثر ۲۰ ثانیه داده در معرضِ کرش است — نه ۳۰ دقیقه.
        """
        try:
            self._dirty_at = time.time()
            self._dirty_reason = reason or "تغییر"
        except Exception:
            pass
        th = getattr(self, "_flush_thread", None)
        if th is not None and th.is_alive():
            return True               # همان تایمر، آخرین وضعیت را می‌فرستد

        def _later():
            gap_sec = 20.0
            try:
                gap_sec = max(5.0, float(os.environ.get("JAFJ_FLUSH_SEC", "20") or 20))
            except Exception:
                gap_sec = 20.0
            for _ in range(int(600 / max(5, gap_sec))):   # حداکثر ۱۰ دقیقه صبر
                time.sleep(1.0)
                if (time.time() - self._dirty_at) >= gap_sec:
                    break
            self._dirty_at = 0.0
            self._flush_durable(self._dirty_reason or "تغییرِ داده")

        try:
            self._flush_thread = threading.Thread(target=_later, daemon=True)
            self._flush_thread.start()
        except Exception:
            return False
        return True

    def _atexit_flush(self):
        """اگر پروسه از راهِ غیرمنتظره بسته شد، آخرین ذخیره را بزن."""
        if self._flushed_on_exit:
            return
        self._flushed_on_exit = True
        try:
            if self._dirty_at or True:
                log_crash("exit", f"خروجِ پروسه (uptime={int(time.time() - self.boot_at)}s)")
        except Exception:
            pass
        try:
            self._flush_durable("خروجِ پروسه", timeout=45, force=True)
        except Exception:
            pass

    def _install_crash_hooks(self):
        """هر مرگِ غیرمنتظره را ثبت و «ذخیره‌ی نجات» را اجرا کن."""
        if self._crash_hooks_done:
            return
        self._crash_hooks_done = True

        def _on_exc(exc_type, exc, tb):
            try:
                txt = "".join(traceback.format_exception(exc_type, exc, tb))
            except Exception:
                txt = f"{exc_type}: {exc}"
            log_crash("uncaught", txt)
            try:
                self._flush_durable("کرشِ ربات", timeout=45, force=True)
            except Exception:
                pass
            try:
                sys.__excepthook__(exc_type, exc, tb)
            except Exception:
                pass

        try:
            sys.excepthook = _on_exc
        except Exception:
            pass

        def _on_thread(args):
            try:
                txt = (f"{args.exc_type.__name__}: {args.exc_value}\n"
                       + "".join(traceback.format_tb(args.exc_traceback)))
            except Exception:
                txt = "thread exception"
            log_crash("thread", txt)
        try:
            threading.excepthook = _on_thread
        except Exception:
            pass
        try:
            import atexit
            atexit.register(self._atexit_flush)
        except Exception:
            pass
        try:
            _DATA_TOUCH[0] = self._touch_data
        except Exception:
            pass

    # ---------- بالا آوردنِ سرویس‌ها بعد از آپدیت/بازیابی ----------
    def _spawn_boot(self, notify_admins=False, why="", force_restart=False,
                    startup=False):
        """همه‌ی سرویس‌هایی که «باید روشن باشند» را در پس‌زمینه بالا می‌آورد.

        چرا thread؟ هر سرویس ~۱.۵ ثانیه وقت می‌برد؛ اگر همین‌جا و همگام اجرا
        شود، ربات بعد از آپدیت دقیقاً وقتی بیشترین نیاز به آن است (مدیر
        «روشن کن» می‌زند) چند دقیقه جواب نمی‌دهد.
        """
        def _worker():
            got = self.sup.boot_lock.acquire(timeout=600)
            if not got:
                if startup:
                    self.sup._startup_boot_pending.clear()
                print("  ⚠️ بالا آوردنِ سرویس‌ها: قفل نگرفت — watchdog جبران می‌کند",
                      flush=True)
                return
            try:
                delay, why = resume_grace_plan(BASE_DIR)
                if delay > 0:
                    print(f"  ⏳ مهلتِ سشن‌ها: {int(delay)} ثانیه صبر می‌کنم "
                          f"({why}) — تا اتصالِ نسخه‌ی قبلی سمتِ تلگرام بسته "
                          "شود و کلیدِ سشن نسوزد "
                          "(خاموش‌کردن: JAFJ_RESUME_DELAY=0)", flush=True)
                    deadline = time.time() + delay
                    self.sup._grace_until = deadline
                    try:
                        while True:
                            left = deadline - time.time()
                            if left <= 0:
                                break
                            print(f"  ⏳ مهلتِ سشن‌ها: {int(left)} ثانیه مانده …",
                                  flush=True)
                            time.sleep(min(30.0, max(0.2, left)))
                    finally:
                        self.sup._grace_until = 0.0
                    print("  ✅ مهلت تمام شد — سرویس‌ها را بالا می‌آورم.",
                          flush=True)
                n = self.sup.boot_all(force_restart=force_restart)
                try:
                    self._boot_last = (n, 0, 0)
                except Exception:
                    pass
                print(f"  ♻️ بالا آوردنِ سرویس‌ها ({why or 'بوت'}): "
                      f"{n} سرویس روشن", flush=True)
                if notify_admins and self.bot is not None and self._loop is not None:
                    for a in (self.cfg.get("admin_ids") or []):
                        try:
                            note = (f"♻️ <b>سرویس‌ها دوباره بالا آمدند</b>\n\n"
                                    f"🟢 {_fa_digits(n)} سرویس روشن شد\n"
                                    f"<i>دلیل: {why or 'آپدیت'}</i>\n"
                                    "اگر سرویسی روشن نشد، <code>/onall</code> را بزن.")
                            asyncio.run_coroutine_threadsafe(
                                self.say(a, note, key="boot_report"), self._loop)
                        except Exception:
                            pass
            except Exception as e:
                print(f"  ⚠️ بالا آوردنِ سرویس‌ها: {type(e).__name__}: {e}", flush=True)
            finally:
                if startup:
                    self.sup._startup_boot_pending.clear()
                self.sup.boot_lock.release()
        try:
            threading.Thread(target=_worker, daemon=True).start()
        except Exception:
            if startup:
                self.sup._startup_boot_pending.clear()
            raise

    def _resume_after_restore(self, why="بازیابی"):
        """بعد از هر بازیابی: سرویس‌های «قبلاً روشن» را خودکار برگردان.

        این همان حلقه‌ی گم‌شده بود: بازیابی اطلاعات را برمی‌گرداند ولی هیچ
        سرویسی را روشن نمی‌کرد، پس مدیر باید برای تک‌تک مشتری‌ها «روشن کن»
        می‌زد.
        """
        try:
            n_want = len(self.db.wanted())
        except Exception:
            n_want = 0
        if n_want <= 0:
            return 0
        try:
            self._reload_cfg_from_disk()
        except Exception:
            pass
        # داده‌ی تازه از پشتیبان آمده؛ مهرِ «نیاز به لاگین» ممکن است مربوط به
        # وضعیت قبلی باشد. پاکش می‌کنیم، ولی هر اکانتی که فایل سشنش خراب
        # باشد دوباره (بدون فرستادنِ کد) علامت می‌خورد.
        self._clear_all_needs_login()
        # force_restart: بعد از بازیابی، پروسه‌ی در حال اجرا اطلاعاتِ کهنه
        # در حافظه دارد؛ باید با داده‌ی تازه بالا بیاید.
        self._spawn_boot(notify_admins=True, why=why, force_restart=True)
        # بعد از بازیابی، «تک‌پیامِ» پشتیبان را فوراً تازه کن: هم داده‌ی
        # همین حالا داخلش برود، هم اشاره‌گرش (چت + آیدی) ثبت شود. بدون این،
        # پشتیبانِ تازه‌ای ساخته نمی‌شد و بوتِ بعدی دوباره «پشتیبان پیدا نشد»
        # می‌داد — همان حلقه‌ای که مدیر را مجبور می‌کرد هر بار zip بفرستد.
        self._reanchor_backup(why)
        return n_want

    def _notify_needs_login(self, uid, reason=""):
        """به مدیر بگو کدام اکانت سشنش باطل است — یک‌بار برای هر اکانت.

        عمداً فقط یک پیام کوتاه و یک‌بار (نه هر دور watchdog) تا پیوی مدیر
        پر نشود؛ لیستِ کامل با /needlogin.
        """
        if self.bot is None or self._loop is None:
            return False
        now_t = time.time()
        seen = getattr(self, "_login_notified", None)
        if seen is None:
            seen = self._login_notified = {}
        if now_t - float(seen.get(uid, 0) or 0) < 6 * 3600:
            return False
        seen[uid] = now_t
        try:
            c = self.db.get(uid) or {}
            nm = c.get("name") or str(uid)
        except Exception:
            nm = str(uid)

        async def _say():
            for a in (self.cfg.get("admin_ids") or []):
                try:
                    await self.say(
                        a,
                        "🔑 <b>یک اکانت نیاز به لاگین دارد</b>\n\n"
                        f"👤 {self._esc(nm)}\n<code>{uid}</code>\n"
                        f"دلیل: {self._esc(reason or 'سشن باطل')}\n\n"
                        "⛔ برای اینکه برای مشتری <b>کدِ ورود</b> نرود، اجرای "
                        "خودکارش متوقف شد.\n"
                        "👉 از «🚀 راه‌اندازی سلف روی اکانتم» (یا با مشتری) "
                        "دوباره لاگین کن.\n"
                        "لیست کامل: <code>/needlogin</code>",
                        key=f"needlogin:{uid}")
                    break
                except Exception:
                    continue

        try:
            asyncio.run_coroutine_threadsafe(_say(), self._loop)
            return True
        except Exception:
            return False

    def _clear_all_needs_login(self):
        try:
            n = self.db.x("UPDATE clients SET need_login=0 WHERE need_login<>0",
                          (), None)
            return int(n or 0) if isinstance(n, int) else 0
        except Exception:
            return 0

    def _reanchor_backup(self, reason=""):
        """بعد از بازیابی، تک‌پیامِ پشتیبان را بازسازی و اشاره‌گرش را ثبت کن.

        در پس‌زمینه اجرا می‌شود تا بازیابی/بوت کند نشود. اگر دیتابیس هنوز
        خالی باشد کاری نمی‌کند (پشتیبانِ خالی نباید پشتیبانِ خوب را بپُراند).
        """
        if self.bot is None:
            return False

        async def _go():
            try:
                try:
                    _delay = float(os.environ.get("JAFJ_REANCHOR_DELAY", "20") or 20)
                except Exception:
                    _delay = 20.0
                try:
                    _min_free = int(os.environ.get("JAFJ_MIN_FREE_MB", "150") or 150)
                except Exception:
                    _min_free = 150
                await asyncio.sleep(max(0.0, _delay))  # بگذار سشن‌ها جا بیفتند
                # ساختِ zip حافظه می‌خواهد؛ بلافاصله بعد از بازیابی که چند
                # سلف هم دارند بالا می‌آیند، این می‌تواند OOM کند و همان
                # «کرش بعد از بازیابی» را بسازد.
                free = mem_available_mb()
                if free is not None and free < _min_free:
                    log_crash("backup-skipped-low-mem", f"free={free}MB")
                    print(f"  ⚠️ حافظه‌ی آزاد {free}MB است — بازسازیِ پشتیبان "
                          "به تعویق افتاد", flush=True)
                    await asyncio.sleep(60)
                    free = mem_available_mb()
                    if free is not None and free < _min_free:
                        return
                try:
                    r = self.db.x("SELECT COUNT(*) c FROM clients", (), "one")
                    n = r["c"] if r else 0
                except Exception:
                    n = 0
                if not n:
                    print("  ℹ️ پشتیبانِ تازه بعد از بازیابی: دیتابیس خالی است — "
                          "پشتیبان قبلی دست‌نخورده می‌ماند", flush=True)
                    return
                ok, msg = await self.backup_once(force=True)
                print(f"  {'📦' if ok else '⚠️'} بازسازیِ تک‌پیامِ پشتیبان پس از "
                      f"{reason or 'بازیابی'}: {msg}", flush=True)
                # و یک «ذخیره‌ی فوری» در گیت‌هاب: سینکِ دوره‌ای هر ۳۰ دقیقه
                # است، ولی بین بازیابی و دیپلویِ بعدی ممکن است نرسد. داده‌ی
                # همین حالا باید از قبل جایی ماندگار داشته باشد.
                self._push_gh_sync("پس از " + (reason or "بازیابی"))
            except Exception as e:
                print(f"  ⚠️ بازسازیِ پشتیبان بعد از بازیابی: {type(e).__name__}: {e}",
                      flush=True)

        try:
            asyncio.get_running_loop()
            asyncio.create_task(_go())
            return True
        except RuntimeError:
            try:
                if self._loop is not None:
                    asyncio.run_coroutine_threadsafe(_go(), self._loop)
                    return True
            except Exception:
                pass
        except Exception:
            pass
        return False

    # ---------- کمکی ----------
    def is_admin(self, uid):
        return self.cfg.is_admin(uid)

    def _mark(self, mid):
        if not mid:
            return
        self._live.add(mid)
        if len(self._live) > 4000:          # جلوگیری از رشد بی‌نهایت
            for _ in range(1000):
                self._live.pop()

    async def say(self, uid, text, buttons=None, key=None):
        """ارسال پیام با ضد تکرار ساده.

        key: برای پیام‌هایی که متنشان تکراری است ولی باید جدا شمرده شوند
        (مثلاً «متن پایان» دو بخش آموزش که ممکن است یکسان باشد).
        """
        # ── ضد تکرار: اگه همین متن اخیراً به همین کاربر فرستاده شده، رد کن ──
        msg_key = f"say:{uid}:{key if key else hash(text[:200])}"
        now_t = time.time()
        last = getattr(self, "_say_last", None)
        if last is None:
            last = self._say_last = {}
        last_send = last.get(msg_key, 0)
        if now_t - last_send < 2:
            return True
        last[msg_key] = now_t
        if len(last) > 500:
            cutoff = now_t - 30
            self._say_last = {k: v for k, v in last.items() if v > cutoff}
        try:
            r = await self.bot.send_message(uid, text, parse_mode="html",
                                            link_preview=False, buttons=buttons)
            if buttons:
                self._mark(getattr(r, "id", None))
            return True
        except Exception as e:
            print("say:", type(e).__name__, e)
            try:
                r = await self.bot.send_message(uid, text, parse_mode="html",
                                                link_preview=False)
                return True
            except Exception as e2:
                print("say2:", type(e2).__name__, e2)
                return False

    async def edit(self, ev, text, buttons=None):
        """ویرایش پیام فعلی.
        فقط edit می‌کنه و اگه نشد، هیچ پیام جدیدی نمی‌فرسته تا از تکرار جلوگیری بشه."""
        try:
            await ev.edit(text, parse_mode="html", link_preview=False,
                          buttons=buttons)
            self._mark(getattr(ev, "message_id", None))
            return True
        except Exception as e:
            # اگه edit نشد، هیچ کاری نکن — پیام جدید نفرست تا duplicate نشه
            print(f"edit failed: {type(e).__name__}: {e}")
            return False

    async def hide_reply_keyboard(self, chat):
        """ReplyKeyboard را از چت حذف می‌کند؛ کیبورد اینلاین منو جداست."""
        try:
            await self.bot.send_message(chat, "\u2063",
                                        link_preview=False,
                                        buttons=clear_reply_keyboard())
        except Exception as e:
            print("hide_keyboard:", type(e).__name__, e)

    def client_state(self, c):
        if not c:
            return "❓ ناشناخته"
        if c["status"] == "active":
            live = "🟢 در حال کار" if self.sup.is_running(c["uid"]) else "🟡 متوقف"
            if int(c.get("trial_expires_at") or 0) > now():
                return f"🎁 تست رایگان — {human_left(c['trial_expires_at'])}"
            return f"{live} — {human_left(c['expires_at'])}"
        return {"new": "🆕 ثبت‌نام نشده",
                "pending": "⏳ منتظر تأیید",
                "expired": "🔴 منقضی",
                "banned": "⛔ مسدود"}.get(c["status"], c["status"])

    # ═══════════════════════════════════════════════
    #  ورود مشتری
    # ═══════════════════════════════════════════════
    async def setup_start(self, uid, chat, source_ev=None, trial=False):
        c = self.db.get(uid)
        if not c:
            return await self.say(chat, "اول /start را بزن.")
        if c["status"] == "banned":
            return await self.say(chat, "دسترسی شما بسته شده.")
        # حتی اگر اعتبار قبلی منقضی شده باشد، اجازه ورود/تعویض اکانت را بده.
        # بعد از ذخیره سشن، can_run اعتبار را بررسی می‌کند و فقط در صورت داشتن
        # اشتراک یا امتیاز، سرویس را روشن خواهد کرد.
        if (self.sup.running_count() >= self.cfg["max_clients"]
                and not self.sup.is_running(uid)):
            return await self.say(chat, "ظرفیت تکمیل است، بعداً امتحان کن.")

        # ── اعتبار را قبل از گرفتن شماره چک کن ──
        if trial and not self.trial_available(uid):
            return await self.say(chat, "🎁 تست رایگان قبلاً استفاده شده یا در دسترس نیست.")
        allow, why = self.can_run(uid)
        if not allow and not trial:
            kb = []
            if self.cfg["points_on"] and self.shop:
                kb.append([B("🎯 خرید امتیاز", "m:packs", "success")])
            if self.cfg["shop_on"] and self.shop:
                kb.append([B("💎 اشتراک ماهانه", "m:plans", "primary")])
            kb.append([B("⬅️ بازگشت", "m:home")])
            bal = self.shop.p_balance(uid) if self.shop else 0
            mn = self.cfg["min_points"]
            return await self.say(chat,
                f"🔒 <b>هنوز اعتبار نداری</b>\n{self.LINE}\n"
                f"{why}\n{self.LINE}\n\n"
                f"موجودی فعلی: <b>{_fa_digits(bal)}</b> امتیاز\n"
                f"لازم: <b>{_fa_digits(mn)}</b> امتیاز  یا  اشتراک ماهانه\n\n"
                f"<i>اول اعتبار بگیر، بعد سلف را راه بینداز.</i>", kb)

        saved_phone = normalize_iran_phone(c.get("phone") or "")
        if self.phone_ok(uid) and saved_phone:
            # شماره قبلاً در همین حساب تأیید شده؛ دوباره نپرس، فقط کد ورود بگیر.
            self.fsm[uid] = {"step": "phone", "trial": bool(trial)}
            return await self.setup_phone(uid, chat, saved_phone)
        if c.get("phone_verified") and not saved_phone:
            # شماره قدیمی/غیرایرانی معتبر نیست؛ دوباره تأیید لازم است.
            self.db.set(uid, phone_verified=0)
        self.fsm[uid] = {"step": "phone", "trial": bool(trial)}
        from telethon import Button
        prompt_text = (
            "📱 <b>مرحله 1 از 2</b>\n\n"
            "شماره موبایل ایران اکانتی را که می‌خواهی سلف روی آن اجرا شود انتخاب کن.\n"
            "دکمه پایین صفحه را بزن تا شماره خودت ارسال شود.\n"
            "یا شماره را با کد ایران بفرست، مثل <code>+98912...</code>\n\n"
            "⚠️ فقط شماره اکانت خودت.\nلغو: /cancel\n"
            "بعد از تأیید، برای راه‌اندازی دوباره همین شماره استفاده می‌شود.")
        # request_phone فقط روی ReplyKeyboard کار می‌کند؛
        # با دکمه اینلاین قاطی نشود وگرنه پیام اصلاً نمی‌رود.
        kb = phone_keyboard("📱 ارسال شماره")
        try:
            if source_ev is not None:
                await source_ev.edit(
                    "✅ مرحله ورود باز شد.\nدکمه پایین صفحه را بزن.",
                    parse_mode="html", buttons=[[B("❌ لغو", "m:home")]])
        except Exception:
            pass
        return await self.say(chat, prompt_text, kb)

    async def setup_phone(self, uid, chat, text):
        phone = normalize_iran_phone(text)
        if not phone:
            return await self.say(chat, "فقط شماره موبایل ایران با کد +98 قابل تأیید است.")

        from telethon import TelegramClient
        from telethon.sessions import StringSession
        from telethon.errors import (FloodWaitError, PhoneNumberBannedError,
                                     PhoneNumberInvalidError)

        await self.say(chat, "⏳ در حال ارسال کد…", clear_reply_keyboard())
        cl = TelegramClient(
            StringSession(), self.cfg["api_id"], self.cfg["api_hash"],
            timeout=15, request_retries=2, connection_retries=2, retry_delay=1)
        try:
            await asyncio.wait_for(cl.connect(), timeout=20)
            sent = await asyncio.wait_for(cl.send_code_request(phone), timeout=20)
        except PhoneNumberInvalidError:
            await cl.disconnect()
            return await self.say(chat, "❌ این شماره معتبر نیست.")
        except PhoneNumberBannedError:
            await cl.disconnect()
            return await self.say(chat, "❌ این شماره در تلگرام مسدود است.")
        except asyncio.TimeoutError:
            await cl.disconnect()
            return await self.say(chat, "⏱ اتصال یا ارسال کد طول کشید. دوباره تلاش کن.")
        except FloodWaitError as e:
            await cl.disconnect()
            return await self.say(chat,
                f"⏳ تلگرام گفته {_fa_digits(getattr(e,'seconds',60))} ثانیه صبر کن.")
        except Exception as e:
            await cl.disconnect()
            return await self.say(chat, f"❌ خطا: {type(e).__name__}")

        trial = bool((self.fsm.get(uid) or {}).get("trial"))
        self.fsm[uid] = {"step": "code", "client": cl, "phone": phone,
                         "hash": sent.phone_code_hash, "tries": 0, "trial": trial}
        await self.say(chat,
            "🔑 <b>مرحله 2 از 2</b>\n\n"
            "کد وارد تلگرامت شد. آن را اینجا بفرست.\n\n"
            "⚠️ <b>مهم:</b> کد را با فاصله بین رقم‌ها بفرست، مثل:\n"
            "<code>1 2 3 4 5</code>\n"
            "(اگر بدون فاصله بفرستی تلگرام کد را باطل می‌کند)\n\n"
            "برای لغو: /cancel")

    async def setup_code(self, uid, chat, text):
        st = self.fsm.get(uid)
        if not st:
            return
        from telethon.errors import (SessionPasswordNeededError,
                                     PhoneCodeInvalidError,
                                     PhoneCodeExpiredError)
        code = digits(text)
        if not code:
            return await self.say(chat, "فقط رقم‌های کد را بفرست.")
        cl = st["client"]
        try:
            await asyncio.wait_for(
                cl.sign_in(st["phone"], code, phone_code_hash=st["hash"]),
                timeout=30)
        except SessionPasswordNeededError:
            st["step"] = "pass"
            return await self.say(chat,
                "🔐 اکانتت رمز دو مرحله‌ای دارد.\nرمز را بفرست.\n\n/cancel برای لغو")
        except PhoneCodeInvalidError:
            st["tries"] += 1
            if st["tries"] >= 3:
                await self.cancel(uid)
                return await self.say(chat, "❌ سه بار اشتباه. /setup را دوباره بزن.")
            return await self.say(chat,
                f"❌ کد اشتباه بود. ({_fa_digits(st['tries'])}/3) دوباره بفرست.")
        except PhoneCodeExpiredError:
            await self.cancel(uid)
            return await self.say(chat, "❌ کد منقضی شد. /setup را دوباره بزن.")
        except asyncio.TimeoutError:
            await self.cancel(uid)
            return await self.say(chat, "⏱ ورود طول کشید. /setup را دوباره بزن.")
        except Exception as e:
            await self.cancel(uid)
            return await self.say(chat, f"❌ خطا: {type(e).__name__}")
        await self.finish(uid, chat)

    async def setup_pass(self, uid, chat, text):
        st = self.fsm.get(uid)
        if not st:
            return
        cl = st["client"]
        try:
            await asyncio.wait_for(cl.sign_in(password=text.strip()), timeout=30)
        except asyncio.TimeoutError:
            await self.cancel(uid)
            return await self.say(chat, "⏱ ورود طول کشید. /setup را دوباره بزن.")
        except Exception:
            st["tries"] = st.get("tries", 0) + 1
            if st["tries"] >= 3:
                await self.cancel(uid)
                return await self.say(chat, "❌ سه بار اشتباه. /setup را دوباره بزن.")
            return await self.say(chat, "❌ رمز اشتباه. دوباره بفرست.")
        await self.finish(uid, chat)

    async def finish(self, uid, chat):
        from telethon.sessions import StringSession
        st = self.fsm.pop(uid, None)
        if not st:
            return
        cl = st["client"]
        trial = bool(st.get("trial"))
        try:
            me = await asyncio.wait_for(cl.get_me(), timeout=20)
            s = StringSession.save(cl.session)
        except asyncio.TimeoutError:
            try:
                await cl.disconnect()
            except Exception:
                pass
            return await self.say(chat, "⏱ دریافت اطلاعات اکانت طول کشید. دوباره /setup را بزن.")
        except Exception as e:
            try:
                await cl.disconnect()
            except Exception:
                pass
            return await self.say(chat, f"❌ خطا در ذخیره: {type(e).__name__}")
        try:
            await cl.disconnect()
        except Exception:
            pass

        # قبل از جایگزین‌کردن Session، پروسه اکانت قبلی را متوقف کن؛
        # وگرنه sup.start فقط «از قبل روشن بود» می‌گوید و اکانت قدیمی ادامه می‌دهد.
        was_running = self.sup.is_running(uid)
        was_started = bool((self.db.get(uid) or {}).get("started_at"))
        if was_running:
            self.sup.stop(uid)

        name = (me.first_name or "") + (f" @{me.username}" if me.username else "")
        if trial:
            trial_start = now()
            trial_end = trial_start + max(1, int(self.cfg.get("trial_minutes", 30) or 30)) * 60
            self.db.set(uid, phone=st["phone"], phone_verified=1, session=s, tg_id=me.id, need_login=0,
                        name=name, status="active", expires_at=trial_end,
                        current_plan_id=0, trial_used=1,
                        trial_started_at=trial_start, trial_expires_at=trial_end,
                        trial_warning_sent=0)
        else:
            self.db.set(uid, phone=st["phone"], phone_verified=1, session=s, tg_id=me.id,
                        name=name, status="active", need_login=0)
        # لاگینِ موفق = سشن تازه و سالم → مهرِ «نیاز به لاگین» برداشته می‌شود و
        # اجازه می‌دهیم بعد از این خودکار روشن بماند.
        try:
            self.db.set(uid, need_login=0, want_on=1)
            self.sup.clear_needs_login(uid)
            # سشنِ تازه = سالم؛ اگر سشنِ خرابِ قبلی قرنطینه شده بود (.bad)،
            # کنارش را بردار تا مسیرِ «بازسازی از دیتابیس» دوباره باز شود.
            try:
                bad = os.path.join(self.sup.folder(uid), "jafj.session.bad")
                if os.path.isfile(bad):
                    os.remove(bad)
            except Exception:
                pass
            self._login_notified and self._login_notified.pop(uid, None)
        except Exception:
            pass
        self.db.log(uid, "login", f"tg_id={me.id}" + (" trial" if trial else ""))
        ref_uid, ref_points = self.reward_verified_referral(uid)
        if ref_uid:
            await self.say(ref_uid, f"🎁 دعوت معتبر شد! {_fa_digits(ref_points)} امتیاز به حسابت اضافه شد.")
        for existing_ref_uid, existing_points in self.reward_existing_referrals(uid):
            await self.say(existing_ref_uid,
                           f"🎁 دعوت معتبر شد! {_fa_digits(existing_points)} امتیاز به حسابت اضافه شد.")
        if not trial and not self.has_sub(uid):
            self.activate_points_mode(uid)

        best = self.effective_plan(uid)
        mx = max(1, int(best.get("max_accounts", 1))) if best else 1
        await self.say(chat, "⏳ ورود موفق بود؛ سلف در حال آماده‌سازی است…")
        await asyncio.to_thread(self.sup.prepare, uid, s, st["phone"], mx, best)
        self.sync_points_limits(uid)
        allow, why = self.can_run(uid)
        if allow:
            ok, msg, fee_msg = await asyncio.to_thread(
                self.start_service, uid, not was_started, False, True)
        else:
            ok, msg = False, why
        if trial and not ok:
            self.db.set(uid, status="new", expires_at=0, trial_used=0,
                        trial_started_at=0, trial_expires_at=0,
                        trial_warning_sent=0)
        c = self.db.get(uid)

        if self.trial_active(uid):
            credit = f"تست رایگان: {human_left(c['trial_expires_at'])}"
        elif self.has_sub(uid):
            credit = f"اعتبار: {human_left(c['expires_at'])}"
        elif self.shop and self.cfg["points_on"]:
            b = self.shop.p_balance(uid)
            per = max(1, self.cfg["cost_per_hour"])
            credit = f"امتیاز: {_fa_digits(b)}  ·  ≈{_fa_digits(b // per)} ساعت"
        else:
            credit = f"اعتبار: {human_left(c['expires_at'])}"

        txt = self.cfg["sold_text"] or (
            ("🎁 <b>تست رایگان " + self.trial_label() + " فعال شد</b>" if trial
             else "✅ <b>راه‌اندازی شد")
            + "\n" + self.LINE + "\n"
            f"👤 اکانت: {name}\n"
            f"📡 وضعیت: {'🟢 در حال کار' if ok else '🟡 ' + msg}\n"
            f"🎯 {credit}\n" + self.LINE + "\n\n"
            "حالا برو به <b>Saved Messages</b> اکانتت و بفرست:\n"
            "<code>.panel</code>\n\n"
            "<i>همه‌ی تنظیمات از همان‌جاست.</i>")
        # مُهر نسخه پایین پیام راه‌اندازی (تشخیص از روی اسکرین‌شات)
        try:
            txt = txt + f"\n\n{self.LINE}\n<i>{build_stamp()}</i>"
        except Exception:
            pass
        kb = [[B("⚙️ سرویس من", "m:svc", "primary")]]
        # اگر مدیر دستوری ثبت کرده باشد، راهنمای مرحله‌به‌مرحله همین‌جا
        # زیرِ پیام «راه‌اندازی شد» در دسترس مشتری است.
        if self.has_cmds():
            kb.append([B("📋 دستورات آماده", "m:cmds", "success")])
        if not ok:
            kb = []
            if self.cfg["points_on"] and self.shop:
                kb.append([B("🎯 خرید امتیاز", "m:packs", "success")])
            if self.cfg["shop_on"] and self.shop:
                kb.append([B("💎 اشتراک ماهانه", "m:plans", "primary")])
            kb.append([B("⬅️ منوی اصلی", "m:home")])
        await self.say(chat, txt, kb)

        # بخش‌های آموزش «بعد از فعال‌سازی» — خودکار، بعد از پیام راه‌اندازی
        if ok and self.cfg.get("tut_auto", True):
            self.tut_schedule(uid, "after_run",
                              wait=int(self.cfg.get("tut_auto_wait", 8) or 0))
            # سلف فعال شد → آموزش خودکار می‌رود؛ اگر مدیر بخشی نساخته باشد،
            # متن آماده‌ی «بعد از فعال‌سازی» (یک‌بار برای هر کاربر) می‌رود
            self.tut_schedule_self_default(
                uid, wait=int(self.cfg.get("tut_auto_wait", 8) or 0))

        for a in self.cfg["admin_ids"]:
            await self.say(a, f"🆕 مشتری جدید\n{name}\nuid: <code>{uid}</code>\n"
                              f"شماره: {st['phone']}")

    async def cancel(self, uid):
        st = self.fsm.pop(uid, None)
        if st and st.get("client"):
            try:
                await st["client"].disconnect()
            except Exception:
                pass



    # ═══════════════════════════════════════════════
    #  دکمه‌ها
    # ═══════════════════════════════════════════════
    LINE = "━━━━━━━━━━━━━━━"

    # ═══════════════════════════════════════════════
    #  📜 قوانین ربات — نمایش و پذیرش قوانین در ابتدای ورود به ربات
    # ═══════════════════════════════════════════════
    DEFAULT_RULES_TEXT = (
        "۱. این ربات جهت راه‌اندازی و مدیریت خودکار سلف‌بات تلگرام ارائه شده است.\n"
        "۲. مسئولیت نحوه‌ی استفاده از اکانت و رعایت قوانین تلگرام بر عهده‌ی کاربر است.\n"
        "۳. برای جلوگیری از محدودیت تلگرام (FloodWait)، از تغییر مداوم اکانت یا ارسال اسپم خودداری کنید.\n"
        "۴. امتیازها و اشتراک‌های خریداری‌شده مربوط به حساب کاربری شما در ربات است.\n"
        "۵. استفاده از ربات به منزله‌ی مطالعه و پذیرش کامل این قوانین است."
    )
    DEFAULT_RULES_BTN = "✅ قوانین را خواندم و می‌پذیرم"

    def rules_on(self):
        return bool(self.cfg.get("rules_on", True))

    def rules_body(self):
        cur = str(self.cfg.get("rules_text") or "").strip()
        return cur if cur else self.DEFAULT_RULES_TEXT

    def rules_btn_label(self):
        cur = str(self.cfg.get("rules_btn") or "").strip()
        return cur if cur else self.DEFAULT_RULES_BTN

    def rules_accepted(self, uid):
        c = self.db.get(uid)
        if not c:
            return True
        return bool(int(c.get("rules_accepted", 1) or 0))

    def rules_required(self, uid):
        if self.is_admin(uid) or not self.rules_on():
            return False
        return not self.rules_accepted(uid)

    def accept_rules(self, uid):
        if self.db.get(uid):
            self.db.set(uid, rules_accepted=1)

    def rules_gate_text(self):
        return (
            f"📜 <b>قوانین و مقررات استفاده از ربات</b>\n{self.LINE}\n\n"
            f"{self.rules_body()}\n\n{self.LINE}\n"
            "👇 <i>برای ورود به ربات و استفاده از امکانات، ابتدا قوانین بالا را مطالعه کرده و دکمه‌ی تأیید را بزنید:</i>"
        )

    def rules_gate_kb(self):
        return [[B(self.rules_btn_label(), "rules:accept", "success")]]

    def rules_view_text(self):
        return (
            f"📜 <b>قوانین و مقررات ربات</b>\n{self.LINE}\n\n"
            f"{self.rules_body()}"
        )

    async def enforce_rules(self, uid, ev=None, chat=None):
        if not self.rules_required(uid):
            return False
        t, kb = self.rules_gate_text(), self.rules_gate_kb()
        if ev is not None:
            try:
                await ev.edit(t, parse_mode="html", buttons=kb, link_preview=False)
            except Exception:
                await self.say(chat or uid, t, kb, key="rules_gate")
        else:
            await self.say(chat or uid, t, kb, key="rules_gate")
        return True

    def rules_screen(self):
        """صفحه‌ی «📜 قوانین ربات» در پنل مدیر."""
        on = self.rules_on()
        cur_txt = str(self.cfg.get("rules_text") or "").strip()
        cur_btn = str(self.cfg.get("rules_btn") or "").strip()
        total, accepted = self.db.rules_stats()
        shown_txt = cur_txt if cur_txt else self.DEFAULT_RULES_TEXT
        txt = "\n".join([
            "📜 <b>قوانین و مقررات ربات</b>",
            self.LINE,
            f"وضعیت نمایش در شروع ربات: <b>{'🟢 فعال (قبل از ورود به ربات)' if on else '🔴 غیرفعال'}</b>",
            f"متن قوانین: <b>{'✅ متن اختصاصی مدیر' if cur_txt else '⚪ متن پیش‌فرض'}</b>",
            f"متن دکمه تأیید: <b>{self._esc(self.rules_btn_label())}</b>",
            f"👥 کاربران تأییدکرده: {_fa_digits(accepted)} از {_fa_digits(total)}",
            self.LINE,
            "<b>متن فعلی قوانین:</b>",
            self._esc(shown_txt[:1500]) + ("…" if len(shown_txt) > 1500 else ""),
            self.LINE,
            "<i>وقتی قوانین فعال باشد، هر کاربر جدید قبل از دیدن منوی اصلی اول این متن را می‌بیند و باید دکمه‌ی تأیید را بزند.</i>",
        ])
        kb = [
            [B("✏️ تغییر متن قوانین", "a:rules:edit", "success")],
            [B("🔴 غیرفعال کردن قوانین در شروع" if on else "🟢 فعال کردن قوانین در شروع",
               "a:rules:tog", "danger" if on else "success")],
            [B("✏️ تغییر متن دکمه تأیید", "a:rules:btn", "primary"),
             B("👁 پیش‌نمایش قوانین", "a:rules:prev", "primary")],
            [B("🔄 درخواست تأیید مجدد از همه کاربران", "a:rules:reset", "warning")],
        ]
        if cur_txt or cur_btn:
            kb.append([B("♻️ برگشت به قوانین پیش‌فرض", "a:rules:def", "danger")])
        kb.append(back_btn("a:home"))
        return txt, kb

    def backup_screen(self, status_line=""):
        """صفحه‌ی «📦 بک‌آپ» در پنل مدیر."""
        auto_on = bool(self.cfg.get("auto_backup_on", True))
        try:
            cnt = self.db.x("SELECT COUNT(*) c FROM clients", (), "one")
            n = cnt["c"] if cnt else 0
        except Exception:
            n = 0
        lines = []
        if status_line:
            lines += [status_line, self.LINE]
        lines += [
            "📦 <b>مدیریت بک‌آپ و بازیابی</b>",
            self.LINE,
            f"👥 مشتری‌های فعلی در دیتابیس: <b>{_fa_digits(n)}</b> نفر",
            f"🔄 بک‌آپ خودکار (فقط موقع ثبت اطلاعات جدید): "
            f"<b>{'🟢 روشن' if auto_on else '🔴 خاموش'}</b>",
            self.LINE,
            "📥 با زدن <b>«📥 دریافت فایل بک‌آپ همین الان»</b>، فایل <code>.zip</code> کامل اطلاعات (مشتری‌ها، سشن‌ها، امتیازها، تنظیمات و قوانین) همین‌جا برایت ارسال می‌شود.",
            "",
            "♻️ <b>نحوه بازیابی اطلاعات:</b>\n"
            "هر زمان خواستی اطلاعات برگردد، کافیست همان فایل <code>.zip</code> بک‌آپ را در پیوی برای خودِ ربات بفرستی و دکمه‌ی <b>«♻️ بازیابی»</b> را بزنی.",
        ]
        kb = [
            [B("📥 دریافت فایل بک‌آپ همین الان", "a:backup:dl", "success")],
            [B("🔄 بک‌آپ خودکار موقع تغییر اطلاعات: " + ("🟢 روشن" if auto_on else "🔴 خاموش"),
               "a:backup:auto", "success" if auto_on else "danger")],
            [B("♻️ بازیابی از آخرین بک‌آپ", "a:restore", "danger")],
            back_btn("a:home"),
        ]
        return "\n".join(lines), kb

    async def send_backup_to_admin(self, chat_id):
        async with self._backup_operation_lock():
            return await self._send_backup_to_admin_locked(chat_id)

    async def _send_backup_to_admin_locked(self, chat_id):
        """بک‌آپ کامل می‌گیرد و فایل zip را مستقیماً در چت مدیر هم ارسال می‌کند."""
        ok, msg = await self._backup_once_locked(force=True)
        latest = os.path.join(BASE_DIR, "jafj_backup_latest.zip")
        if os.path.isfile(latest) and self.bot is not None:
            try:
                cnt = self.db.x("SELECT COUNT(*) c FROM clients", (), "one")
                n = cnt["c"] if cnt else 0
            except Exception:
                n = "?"
            sz_kb = max(1, os.path.getsize(latest) // 1024)
            cap = (
                f"📦 <b>فایل بک‌آپ کامل ربات</b> ({BACKUP_TAG})\n"
                f"👥 مشتری‌ها: {_fa_digits(n)} · حجم: {_fa_digits(sz_kb)}KB\n\n"
                "♻️ هر زمان خواستی اطلاعات (مشتری‌ها، سشن‌ها، امتیازها، تنظیمات و قوانین) برگردد، "
                "همین فایل را در پیوی برای خودِ ربات بفرست و دکمه‌ی «♻️ بازیابی» را بزن."
            )
            # اگر مقصدِ خودکار چت دیگری بود یا پیام قدیمی ویرایش شد، یک فایل مستقیم هم پایین چت مدیر بفرست
            try:
                await self.bot.send_file(chat_id, latest, caption=cap,
                                         parse_mode="html", force_document=True)
                ok = True
            except TypeError:
                try:
                    await self.bot.send_file(chat_id, latest, caption=cap)
                    ok = True
                except Exception:
                    pass
            except Exception as e:
                print(f"  ⚠️ ارسال مستقیم فایل بک‌آپ به مدیر: {type(e).__name__}: {e}", flush=True)
        return ok, msg

    # ═══════════════════════════════════════════════
    #  📝 متن‌های ربات — همه‌ی متن‌های قابل‌تنظیمِ ربات یک‌جا
    #  (id, emoji, عنوان، کلید در cfg، چندخطی؟، سقف حرف، توضیح)
    # ═══════════════════════════════════════════════
    READY_TEXTS = (
        ("rules", "📜", "متن قوانین ربات", "rules_text", False, 3500,
         "در ابتدای ورود کاربر به ربات (قبل از منوی اصلی) و در بخش قوانین نمایش داده می‌شود."),
        ("rules_btn", "✅", "دکمه تأیید قوانین", "rules_btn", False, 80,
         "متن دکمه‌ی پذیرش زیر قوانین در ابتدای ربات (پیش‌فرض: ✅ قوانین را خواندم و می‌پذیرم)."),
        ("welcome", "📝", "متن خوش‌آمدگویی", "welcome", False, 2000,
         "زیرِ سلامِ بالای منوی اصلیِ مشتری نمایش داده می‌شود."),
        ("sold", "🚀", "بعد از راه‌اندازی سلف", "sold_text", False, 3500,
         "بعد از اینکه سلفِ مشتری با موفقیت روشن شد برایش می‌رود. "
         "خالی = متنِ پیش‌فرض (وضعیت، اعتبار و راهنمای .panel)."),
        ("expired", "⏳", "اشتراک / سرویس غیرفعال", "expired_text", False, 2000,
         "وقتی مشتری با سرویسِ غیرفعال یا اشتراکِ تمام‌شده کار می‌خواهد "
         "انجام بدهد، این متن را می‌بیند."),
        ("help_txt", "📖", "متن راهنمای مشتری", "help_text", False, 3500,
         "وقتی مشتری دکمه‌ی «📖 راهنما» یا دستور /help را می‌زند نمایش داده می‌شود."),
        ("support_txt", "💬", "متن صفحه پشتیبانی", "support_text", False, 2000,
         "بالای صفحه‌ی «🎧 پشتیبانی» و ثبت تیکت به مشتری نمایش داده می‌شود."),
        ("contact", "🎧", "آیدی پشتیبانی", "contact", False, 100,
         "مثل @yourid — زیرِ منوی اصلی و صفحه‌ی پشتیبانی نشان داده می‌شود."),
        ("paynote", "💳", "توضیح پرداخت", "pay_note", False, 1000,
         "زیرِ شماره کارت در فاکتورها اضافه می‌شود."),
        ("g_morning", "☀️", "سلام صبح (۵ تا ۱۲)", "greet_morning", True, 2000,
         "هر خط یک جمله؛ هر بار یکی تصادفی انتخاب می‌شود."),
        ("g_noon", "🌞", "سلام ظهر (۱۲ تا ۱۷)", "greet_noon", True, 2000,
         "هر خط یک جمله؛ هر بار یکی تصادفی انتخاب می‌شود."),
        ("g_evening", "🌇", "سلام عصر (۱۷ تا ۲۱)", "greet_evening", True, 2000,
         "هر خط یک جمله؛ هر بار یکی تصادفی انتخاب می‌شود."),
        ("g_night", "🌙", "سلام شب (۲۱ تا ۵)", "greet_night", True, 2000,
         "هر خط یک جمله؛ هر بار یکی تصادفی انتخاب می‌شود."),
    )
    RT_CLEAR_WORDS = ("خاموش", "پاک", "حذف", "پیش‌فرض", "پیشفرض", "-")

    def rt_find(self, rid):
        for r in self.READY_TEXTS:
            if r[0] == rid:
                return r
        return None

    def rt_current(self, r):
        """متنِ ذخیره‌شده‌ی مدیر ('' = تنظیم نشده)."""
        return str(self.cfg.get(r[3]) or "")

    @staticmethod
    def _esc(t):
        return (str(t).replace("&", "&amp;").replace("<", "&lt;")
                .replace(">", "&gt;"))

    def rt_clean(self, r, text):
        """متنِ ورودیِ مدیر را برای ذخیره آماده می‌کند."""
        text = (text or "").strip()
        if r[4]:   # چندخطی: خط‌های خالی حذف، هر خط حداکثر ۸۰ حرف، حداکثر ۱۰ خط
            lines = [ln.strip()[:80] for ln in text.splitlines() if ln.strip()]
            return "\n".join(lines[:10])
        return text[:r[5]]

    def rt_list_view(self):
        kb, row = [], []
        for r in self.READY_TEXTS:
            mark = "✅" if self.rt_current(r) else "⚪"
            row.append(B(f"{mark} {r[1]} {r[2].split(' (')[0]}", f"a:rt:{r[0]}",
                         "primary" if self.rt_current(r) else None))
            if len(row) == 2:
                kb.append(row)
                row = []
        if row:
            kb.append(row)
        kb.append(back_btn("a:home"))
        txt = (f"📝 <b>متن‌های ربات</b>\n{self.LINE}\n"
               "همه‌ی متن‌هایی که ربات به مشتری می‌گوید را از همین‌جا خودت "
               "تنظیم کن. روی هر مورد بزن، متن فعلی را ببین و عوضش کن.\n\n"
               "✅ = متنِ خودت ثبت شده\n"
               "⚪ = متنِ پیش‌فرض می‌رود\n\n"
               "<i>برای سلام‌ها می‌توانی جای اسمِ مشتری را با "
               "<code>{name}</code> مشخص کنی.</i>")
        return txt, kb

    def rt_item_view(self, r):
        cur = self.rt_current(r)
        t = [f"{r[1]} <b>{r[2]}</b>", self.LINE, r[6], ""]
        if r[4]:
            hint = ("جمله‌ی خودت را بنویس؛ برای جای اسم <code>{name}</code> "
                    "بگذار. مثال: <code>{name} جان، ظهرت بخیر 🌞</code>")
            opts = self.greet_options(r[3])
            t.append("<b>جمله‌های فعلی:</b>" + ("" if cur else " <i>(پیش‌فرض)</i>"))
            t += [f"• {self._esc(o)}" for o in opts]
            t += ["", hint]
        else:
            t.append("<b>متن فعلی:</b>" + ("" if cur else " <i>تنظیم نشده (پیش‌فرض)</i>"))
            if cur:
                t.append(self._esc(cur[:1500]) + ("…" if len(cur) > 1500 else ""))
        kb = [[B("✏️ تغییر متن", f"a:rte:{r[0]}", "success")]]
        if cur:
            kb.append([B("♻️ برگشت به پیش‌فرض", f"a:rtr:{r[0]}", "danger")])
        kb.append(back_btn("a:rt"))
        return "\n".join(t), kb

    # پیش‌فرضِ سلام‌ها؛ مدیر از «📝 متن‌های ربات» عوضشان می‌کند.
    GREET_DEFAULTS = {
        "greet_morning": ("صبح بخیر ☀️", "سلام صبحت بخیر 🌤", "صبحت پرانرژی ☕️"),
        "greet_noon": ("سلام 👋", "ظهرت بخیر 🌞", "خسته نباشی 🙌"),
        "greet_evening": ("عصر بخیر 🌇", "سلام عصرت بخیر 🌆", "خوش اومدی 👋"),
        "greet_night": ("شب بخیر 🌙", "سلام شبت بخیر ✨", "بیدارِ شب‌کار 🌃"),
    }

    @staticmethod
    def greet_key(hour):
        """کلیدِ بازه‌ی روز برای ساعت محلی (۰ تا ۲۳)."""
        if 5 <= hour < 12:
            return "greet_morning"
        if 12 <= hour < 17:
            return "greet_noon"
        if 17 <= hour < 21:
            return "greet_evening"
        return "greet_night"

    def greet_options(self, key):
        """جمله‌های سلام این بازه: متنِ مدیر (هر خط یکی) یا پیش‌فرض."""
        raw = str(self.cfg.get(key) or "")
        custom = [ln.strip() for ln in raw.splitlines() if ln.strip()]
        return custom or list(self.GREET_DEFAULTS[key])

    def greet(self, hour=None):
        # ساعتِ محلیِ ربات (Asia/Tehran)، نه ساعتِ سرور
        h = local_now().hour if hour is None else int(hour)
        return random.choice(self.greet_options(self.greet_key(h)))

    # ═══════════════════════════════════════════════
    #  📋 دستورات آماده — راهنمای مرحله‌به‌مرحله‌ی فعال‌سازی سلف
    #  مدیر عنوان/دستور/توضیح را ثبت می‌کند؛ داده در cfg["cmd_items"] و
    #  cfg["cmd_intro"] می‌ماند. مشتری همین‌ها را شماره‌دار می‌بیند و هر
    #  دستور داخل <code> است تا با یک لمس کپی شود.
    # ═══════════════════════════════════════════════
    CM_MAX = 40            # سقفِ تعدادِ دستور در لیست
    CM_MSG_LIMIT = 3800    # سقفِ حرفِ هر پیامِ مشتری (بعد از آن شکسته می‌شود)

    # «⚡️ پیشنهادِ شروع» — پنج دستور از راهنمای خودِ سلف (HELP در 95.py).
    # فقط وقتی لیست خالی است پیشنهاد می‌شود.
    CMD_STARTER = (
        ("پنل", ".panel",
         "داشبورد سلف؛ وضعیت، اعتبار و همه‌ی تنظیمات از همین‌جاست."),
        ("کانال", "کانال @channel",
         "کانالی که پیام‌ها به آن می‌روند را معرفی کن؛ جای @channel آیدی کانال خودت."),
        ("افزودن گروه", "افزودن گروه @group",
         "گروه تبادل را اضافه کن؛ جای @group آیدی گروه را بنویس."),
        ("تبادل روشن", "تبادل روشن",
         "حالت تبادل ممبر را روشن می‌کند."),
        ("راهنما", "راهنما",
         "فهرست همه‌ی دستورهای سلف را می‌فرستد."),
    )

    def cmd_items(self):
        """لیستِ تمیزِ دستورهای ثبت‌شده؛ داده‌ی خراب را بی‌صدا رد می‌کند."""
        raw = self.cfg.get("cmd_items")
        out = []
        if isinstance(raw, list):
            for it in raw:
                if not isinstance(it, dict):
                    continue
                d = {"title": str(it.get("title") or "").strip()[:80],
                     "cmd": str(it.get("cmd") or "").strip()[:200],
                     "note": str(it.get("note") or "").strip()[:300]}
                if d["title"] or d["cmd"]:   # موردِ کاملاً خالی شمرده نمی‌شود
                    out.append(d)
        return out

    def cmd_save(self, items):
        """ذخیره‌ی لیست (همیشه کپیِ تازه، تا پیش‌فرضِ ماژول دست‌نخورده بماند)."""
        self.cfg["cmd_items"] = [dict(x) for x in items]

    def has_cmds(self):
        return bool(self.cmd_items())

    # ---------- صفحه‌ی مشتری ----------
    def cmds_pages(self):
        """صفحه‌های راهنمای مشتری؛ هر صفحه زیر CM_MSG_LIMIT حرف.

        لیست خالی → [] (یعنی دکمه و پیامی هم نمی‌رود).
        """
        items = self.cmd_items()
        if not items:
            return []
        intro = str(self.cfg.get("cmd_intro") or "").strip()
        head = ("📋 <b>دستورات آماده</b>\n" + self.LINE + "\n"
                + (self._esc(intro) + "\n" + self.LINE + "\n" if intro else "")
                + "به‌ترتیب زیر برو جلو؛ روی هر دستور یک لمس بزن تا کپی شود و "
                  "در <b>Saved Messages</b> اکانتت بفرست.\n")
        pages, cur, n = [], head, 0
        for i, it in enumerate(items, 1):
            blk = "\n<b>%s) %s</b>\n" % (_fa_digits(i),
                                         self._esc(it["title"]) or "—")
            if it["cmd"]:
                blk += "<code>%s</code>\n" % self._esc(it["cmd"])
            if it["note"]:
                blk += "<i>%s</i>\n" % self._esc(it["note"])
            # n>0 یعنی این صفحه چیزی دارد؛ پس شکستن همیشه جلو می‌رود و
            # یک موردِ خیلی بلند هم هرگز حلقه‌ی بی‌پایان نمی‌سازد.
            if n and len(cur) + len(blk) > self.CM_MSG_LIMIT:
                pages.append(cur)
                cur = ("📋 <b>دستورات آماده</b> — ادامه (%s)\n%s\n"
                       % (_fa_digits(len(pages) + 1), self.LINE))
                n = 0
            cur += blk
            n += 1
        if n:
            pages.append(cur)
        return pages

    async def send_cmds(self, uid, back=True):
        """فرستادن راهنما به مشتری؛ اگر بلند بود به چند پیام شکسته می‌شود."""
        pages = self.cmds_pages()
        if not pages:
            return False
        last = len(pages) - 1
        for i, p in enumerate(pages):
            await self.say(uid, p, [back_btn("m:home")] if (back and i == last)
                           else None, key="cmds:%d:%d" % (i, len(pages)))
        return True

    # ---------- صفحه‌های مدیر ----------
    def cm_list_view(self):
        items = self.cmd_items()
        txt = ["📋 <b>دستورات آماده</b>", self.LINE,
               "مرحله‌هایی که مشتری بعد از راه‌اندازی سلف می‌بیند. هر مورد سه "
               "بخش دارد: <b>عنوان</b>، <b>دستور</b> و <b>توضیح ساده</b>.",
               "دستور داخل <code>&lt;code&gt;</code> می‌رود تا مشتری با یک لمس "
               "کپی‌اش کند.", ""]
        if items:
            txt.append("<b>%s دستور ثبت شده:</b>" % _fa_digits(len(items)))
            for i, it in enumerate(items):
                lbl = self._esc(it["title"] or it["cmd"])
                txt.append("%s) %s — <code>%s</code>"
                           % (_fa_digits(i + 1), lbl, self._esc(it["cmd"])))
        else:
            txt.append("⚪ هنوز دستوری ثبت نکرده‌ای؛ مشتری دکمه‌ی "
                       "«📋 دستورات آماده» را نمی‌بیند.")
            txt.append("«⚡️ پیشنهادِ شروع» پنج دستور آماده از راهنمای خودِ سلف "
                       "می‌گذارد، یا خودت «➕ افزودن دستور» را بزن.")
        kb, row = [], []
        for i, it in enumerate(items):
            lbl = (it["title"] or it["cmd"] or "—")
            row.append(B("%s. %s" % (_fa_digits(i + 1), lbl)[:38],
                         "a:cme:%d" % i, "primary"))
            if len(row) == 2:
                kb.append(row)
                row = []
        if row:
            kb.append(row)
        add = [B("➕ افزودن دستور", "a:cmi", "success")]
        if not items:
            add.append(B("⚡️ پیشنهادِ شروع", "a:cmx", "success"))
        kb.append(add)
        kb.append([B("📝 متن بالای صفحه", "a:cme:intro"),
                   B("👁 پیش‌نمایش", "a:cm:prev", "primary")])
        kb.append(back_btn("a:home"))
        return "\n".join(txt), kb

    def cm_item_view(self, i):
        items = self.cmd_items()
        if not (0 <= i < len(items)):
            return None
        it = items[i]
        txt = "\n".join([
            "📋 <b>%s</b>" % (self._esc(it["title"]) or "—"), self.LINE,
            "🔢 جایگاه: %s از %s" % (_fa_digits(i + 1), _fa_digits(len(items))),
            "✏️ عنوان: %s" % (self._esc(it["title"]) or "<i>خالی</i>"),
            "⌨️ دستور: %s" % ("<code>%s</code>" % self._esc(it["cmd"])
                             if it["cmd"] else "<i>خالی</i>"),
            "📄 توضیح: %s" % (self._esc(it["note"]) or "<i>خالی</i>"),
        ])
        kb = [[B("✏️ عنوان", "a:cme:%d:t" % i), B("⌨️ دستور", "a:cme:%d:c" % i)],
              [B("📄 توضیح", "a:cme:%d:n" % i)],
              [B("⬆️ بالا", "a:cmu:%d:u" % i), B("⬇️ پایین", "a:cmu:%d:d" % i)],
              [B("🗑 حذف", "a:cmd:%d" % i, "danger")],
              back_btn("a:cm")]
        return txt, kb

    CM_FIELDS = (("t", "title", "✏️ عنوان", "عنوان این مرحله (کوتاه)"),
                 ("c", "cmd", "⌨️ دستور", "دستوری که مشتری باید بفرستد"),
                 ("n", "note", "📄 توضیح", "یک توضیح ساده برای مشتری"))

    def cm_field(self, code):
        for f in self.CM_FIELDS:
            if f[0] == code:
                return f
        return None

    def cm_edit_prompt(self, i, code):
        """متنِ صفحه‌ی «این فیلد را عوض کن»؛ اگر مورد نبود None."""
        f = self.cm_field(code)
        items = self.cmd_items()
        if not f or not (0 <= i < len(items)):
            return None
        cur = items[i].get(f[1]) or ""
        txt = "\n".join([
            "%s <b>%s</b>" % (f[2], self._esc(items[i]["title"] or items[i]["cmd"])),
            self.LINE,
            "%s را بفرست." % f[3],
            "فعلی: %s" % (("<code>%s</code>" % self._esc(cur)) if cur
                          else "<i>خالی</i>"),
            "",
            "خالی‌کردن: بنویس <code>-</code>",
            "<i>/cancel برای لغو</i>",
        ])
        return txt, [[B("⬅️ بازگشت", "a:cme:%d" % i)]]

    def cm_del_view(self, i):
        items = self.cmd_items()
        if not (0 <= i < len(items)):
            return None
        it = items[i]
        txt = "\n".join(x for x in [
            "🗑 <b>حذف دستور</b>", self.LINE,
            "«%s» برای همیشه پاک شود؟" % self._esc(it["title"] or it["cmd"] or "—"),
            ("<code>%s</code>" % self._esc(it["cmd"])) if it["cmd"] else "",
        ] if x)
        kb = [[B("✅ بله، پاک شود", "a:cmd:%d:y" % i, "danger")],
              [B("↩️ نه، برگرد", "a:cme:%d" % i)],
              back_btn("a:cm")]
        return txt, kb

    def cm_starter_view(self):
        txt = ["⚡️ <b>پیشنهادِ شروع</b>", self.LINE,
               "این پنج دستور از راهنمای خودِ سلف آمده‌اند و برای شروع "
               "کافی‌اند؛ بعداً هرکدام را می‌توانی عوض کنی یا حذف کنی.", ""]
        for i, (title, cmd, note) in enumerate(self.CMD_STARTER, 1):
            txt.append("<b>%s) %s</b> — <code>%s</code>\n<i>%s</i>"
                       % (_fa_digits(i), self._esc(title), self._esc(cmd),
                          self._esc(note)))
        kb = [[B("✅ همین‌ها را بگذار", "a:cmxy", "success")]]
        if self.cmd_items():
            txt.append("\n⚠️ لیست خالی نیست؛ این کار جایگزینش نمی‌کند.")
        kb.append(back_btn("a:cm"))
        return "\n".join(txt), kb

    def cm_intro_view(self):
        cur = str(self.cfg.get("cmd_intro") or "").strip()
        txt = "\n".join([
            "📝 <b>متن بالای صفحه</b>", self.LINE,
            "این متن اولِ «📋 دستورات آماده» مشتری می‌آید؛ مثلاً یک جمله "
            "درباره‌ی اینکه این دستورها را در Saved Messages بفرستد.",
            "",
            "فعلی: %s" % (self._esc(cur) if cur else "<i>خالی</i>"),
            "",
            "متن جدید را بفرست؛ برای خالی‌کردن بنویس <code>-</code>",
            "<i>/cancel برای لغو</i>",
        ])
        return txt, [back_btn("a:cm")]

    def has_sub(self, uid):
        """اشتراک پولی فعال دارد؟

        مُهرِ «کهنه»ی تست رایگان (trial_expires_at در گذشته) نباید اشتراکِ
        فعال را پنهان کند؛ وگرنه مشترکِ ماهانه‌ای که یک بار تست گرفته بود
        به‌اشتباه «امتیازی» حساب می‌شود، امتیازش ساعتی می‌سوزد و بعد از
        چند ساعت خاموش می‌شود. فقط تستِ «در حال اجرا» (در آینده) جلوی
        has_sub را می‌گیرد.
        """
        c = self.db.get(uid)
        return bool(c and c["status"] == "active" and c["expires_at"] > now()
                    and int(c.get("trial_expires_at") or 0) <= now())

    def trial_active(self, uid):
        c = self.db.get(uid)
        return bool(c and c["status"] == "active"
                    and int(c.get("trial_expires_at") or 0) > now())

    def trial_available(self, uid):
        if not self.cfg.get("trial_on", True):
            return False
        if self.is_admin(uid):
            return True
        c = self.db.get(uid)
        if not c:
            return True
        if c.get("status") == "banned":
            return False
        if self.has_sub(uid):
            return False
        if int(c.get("trial_used") or 0) and int(c.get("trial_started_at") or 0):
            return False
        return True

    # ---------- تنظیمِ تست رایگان از پنل مدیر ----------
    def trial_minutes_now(self):
        return max(1, int(self.cfg.get("trial_minutes", 30) or 30))

    def trial_warn_now(self):
        return max(1, int(self.cfg.get("trial_warning_minutes", 10) or 10))

    def trial_label(self):
        """برچسبِ مدتِ فعلی — برای دکمه‌ی منو و متن‌های کاربر."""
        return trial_duration_label(self.trial_minutes_now())

    def _parse_trial_minutes(self, raw):
        """مدتِ تست از متن مدیر: «90» = ۹۰ دقیقه، «2 ساعت» = ۱۲۰ دقیقه.
        سقف: ۳۰ روز. صفر = نامعتبر."""
        t = str(raw or "").strip()
        if not t:
            return 0
        t_num = t.translate(EN)
        m = re.search(r"\d+(?:[.,]\d+)?", t_num)
        if not m:
            return 0
        try:
            v = float(m.group(0).replace(",", "."))
        except ValueError:
            return 0
        is_hours = ("ساعت" in t) or ("h" in t_num.lower())
        mins = int(round(v * 60)) if is_hours else int(round(v))
        return max(1, min(30 * 24 * 60, mins))

    def _set_trial_minutes(self, mins):
        """مدت را ذخیره می‌کند و یادآوری را هم منطقی نگه می‌دارد
        (یادآوری هرگز از نصفِ مدت بیشتر و از خودِ مدت کمتر نمی‌شود)."""
        mins = max(1, int(mins or 30))
        self.cfg["trial_minutes"] = mins
        warn = max(1, min(self.trial_warn_now(), max(1, mins // 2)))
        self.cfg["trial_warning_minutes"] = warn
        self.cfg.save()
        return mins, warn

    def trial_screen(self):
        """صفحه‌ی «🎁 تست رایگان» در پنل مدیر: روشن/خاموش، مدت، ریست."""
        on = bool(self.cfg.get("trial_on", True))
        mins = self.trial_minutes_now()
        warn = self.trial_warn_now()
        total, running, used = self.db.trial_stats()
        txt = "\n".join([
            "🎁 <b>تست رایگان</b>",
            self.LINE,
            f"وضعیت: {'🟢 فعال' if on else '🔴 غیرفعال'}",
            f"مدت هر تست: <b>{trial_duration_label(mins)}</b>",
            f"یادآوری: {_fa_digits(warn)} دقیقه آخر",
            self.LINE,
            f"👥 کاربران: {_fa_digits(total)}   ·   "
            f"🌀 در حال تست: {_fa_digits(running)}   ·   "
            f"✅ تست‌گرفته: {_fa_digits(used)}",
            "",
            "مدت را از دکمه‌ها انتخاب کن (✅ = فعلی) یا «مقدار دلخواه» را بزن.",
            "♻️ «ریست تست همه» پرونده‌ی تستِ همه را پاک می‌کند تا دوباره "
            "بتوانند تست رایگان بگیرند (تستِ در حال اجرا قطع نمی‌شود).",
        ])

        def dur_btn(m):
            return B(("✅ " if m == mins else "") + trial_duration_label(m),
                     f"a:trial_min:{m}",
                     "success" if m == mins else "primary")

        kb = [
            [B("🔴 خاموش کن" if on else "🟢 روشن کن", "a:trial_tog",
               "danger" if on else "success")],
            [dur_btn(30), dur_btn(60), dur_btn(120)],
            [dur_btn(180), dur_btn(360), dur_btn(720)],
            [dur_btn(1440), B("✍️ مقدار دلخواه", "a:trial_min:x", "warning")],
            [B(("✅ " if w == warn else "") + f"⏰ یادآوری {_fa_digits(w)} دقیقه",
               f"a:trial_warn:{w}", "success" if w == warn else "primary")
             for w in (5, 10, 15, 30)],
            [B("♻️ ریست تست برای همه", "a:trial_reset", "danger")],
            back_btn("a:home"),
        ]
        return txt, kb

    def can_run(self, uid):
        """(اجازه_اجرا, دلیل) — برای شروع حداقل min_points لازم است."""
        c = self.db.get(uid)
        if not c or c["status"] == "banned":
            return False, "دسترسی بسته است"
        # انقضا را همان لحظه اعمال کن، نه فقط در چرخه watchdog.
        if c["status"] == "active" and c["expires_at"] and c["expires_at"] <= now():
            if self.sup.is_running(uid):
                self.sup.stop(uid)
            self.db.set(uid, status="expired", current_plan_id=0)
            required = max(int(self.cfg["min_points"]), int(self.cfg["start_fee"]))
            if (self.cfg["points_on"] and self.shop
                    and self.shop.p_balance(uid) >= required):
                self.db.set(uid, status="active", expires_at=0, current_plan_id=0)
                self.sync_points_limits(uid)
                return True, "points"
            c = self.db.get(uid)
            return False, "اشتراک منقضی شده است"
        if self.trial_active(uid):
            return True, "trial"
        if self.has_sub(uid):
            return True, "sub"
        if self.cfg["points_on"] and self.shop:
            b = self.shop.p_balance(uid)
            mn = self.cfg["min_points"]
            if self.sup.is_running(uid) and b > 0:
                return True, "points"
            need = max(mn, self.cfg["start_fee"])
            if b >= need:
                return True, "points"
            if b <= 0:
                return False, "امتیاز نداری"
            return False, (f"برای روشن کردن حداقل {_fa_digits(need)} امتیاز لازم است "
                           f"({_fa_digits(need - b)} تا کم داری)")
        return False, "اشتراک فعال نداری"

    def charge_start(self, uid, first=False):
        """هزینه روشن‌کردن دستی؛ بار اول و روشن‌کردن دوباره هر دو پیش‌فرض ۲۰ امتیاز."""
        if self.has_sub(uid) or self.trial_active(uid) or not (self.shop and self.cfg["points_on"]):
            return True, ""
        fee = self.cfg["start_fee"] if first else self.cfg.get("restart_fee", 20)
        fee = max(0, int(fee))
        if fee <= 0:
            return True, ""
        ok, bal = self.shop.p_spend(uid, fee, "اولین روشن کردن" if first else "روشن کردن دوباره")
        if not ok:
            return False, (f"برای روشن کردن {_fa_digits(fee)} امتیاز لازم است "
                           f"(موجودی {_fa_digits(bal)})")
        return True, (f"−{_fa_digits(fee)} امتیاز بابت "
                      f"{'اولین روشن کردن' if first else 'روشن کردن دوباره'} · "
                      f"موجودی {_fa_digits(bal)}")

    def effective_plan(self, uid):
        """فقط پلنی که همین اشتراک را فعال کرده ملاک است؛ سابقه قدیمی نیست.
        اگر مدیر برای این کاربر سقف اکانتِ خودش را ست کرده (max_accounts>0)،
        همان ملاک است (اولویت بر پلنِ جهانی)."""
        if not self.shop or not self.has_sub(uid):
            return None
        c = self.db.get(uid) or {}
        ua = int(c.get("max_accounts") or 0)
        pid = int(c.get("current_plan_id") or 0)
        if ua > 0:
            return {"name": "اشتراک دستی", "max_accounts": ua}
        if pid:
            pl = self.shop.plan(pid)
            if pl:
                return pl
        # فعال‌سازی دستی یا Trial پلن سفارشی ندارد.
        return {"name": "اشتراک دستی", "max_accounts": 1}

    def activate_points_mode(self, uid):
        """اشتراک منقضی‌شده‌ای که امتیاز کافی دارد وارد حالت امتیازی شود."""
        if not (self.shop and self.cfg["points_on"] and not self.has_sub(uid)):
            return False
        required = max(int(self.cfg["min_points"]), int(self.cfg["start_fee"]))
        if self.shop.p_balance(uid) < required:
            return False
        self.db.set(uid, status="active", expires_at=0, current_plan_id=0)
        self.sync_points_limits(uid)
        return True

    def sync_points_limits(self, uid):
        """موجودی جاری امتیاز را به پنل سلف منتقل می‌کند."""
        if not (self.shop and self.cfg["points_on"] and not self.has_sub(uid)):
            return False
        per = max(1, int(self.cfg["cost_per_hour"]))
        bal = self.shop.p_balance(uid)
        return self.sup.write_limits(uid, None, points_mode=True,
                                     points=bal, hours_left=bal // per)

    def charge_selfbot_error(self, uid, detail=""): 
        """فقط خطای خود پروسه ۵ امتیاز هزینه دارد؛ خطای مدیر رایگان است."""
        if self.has_sub(uid) or not (self.shop and self.cfg["points_on"]):
            return ""
        fee = max(0, int(self.cfg.get("self_error_fee", 5)))
        if fee <= 0:
            return ""
        before = self.shop.p_balance(uid)
        real = min(before, fee)
        if real <= 0:
            return ""
        after = self.shop.p_add(uid, -real, "start_error",
                                detail or "خطای داخلی سلف")
        self.sync_points_limits(uid)
        return (f"\n🎯 به‌دلیل خطای خود سلف، {_fa_digits(real)} امتیاز کسر شد "
                f"(موجودی {_fa_digits(after)})")

    def start_service(self, uid, first=False, restart=False, charge_success=True):
        """شروع استاندارد با تفکیک خطای مدیر از خطای خود سلف."""
        was_running = self.sup.is_running(uid)
        if restart:
            self.sup.stop(uid)
            time.sleep(0.2)
        elif was_running:
            return True, "از قبل روشن بود", ""

        ok, msg = self.sup.start(uid)
        if not ok:
            if self.sup.last_failure.get(uid) == "selfbot":
                msg += self.charge_selfbot_error(uid, msg)
            return False, msg, ""

        fee_msg = ""
        if charge_success and not self.has_sub(uid) and self.shop and self.cfg["points_on"]:
            paid, fee_msg = self.charge_start(uid, first=first)
            if not paid:
                self.sup.stop(uid)
                return False, "برداشت هزینه انجام نشد؛ سرویس خاموش شد.", ""
        if self.shop:
            self.shop.p_reset_charge(uid)
        self.sync_points_limits(uid)
        return True, msg, fee_msg

    def hours_left(self, uid):
        cost = max(1, self.cfg["cost_per_hour"])
        return self.shop.p_balance(uid) // cost if self.shop else 0

    def home_text(self, uid):
        c = self.db.get(uid)
        name = (c.get("name") or "").split("@")[0].strip() if c else ""
        g = self.greet()
        if "{name}" in g:
            # مدیر جای اسم را خودش گذاشته؛ بدون اسم، همان جا خالی می‌شود
            hi = " ".join(g.replace("{name}", name).split())
        elif name:
            hi = f"{g.split()[0]} {name} {' '.join(g.split()[1:])}".strip()
        else:
            hi = g
        t = [f"<b>{hi}</b>", ""]
        t.append(self.cfg["welcome"] or "به پنل <b>جفج</b> خوش آمدی.")
        t += ["", self.LINE]
        t.append(f"⚡️ <b>سرویس</b>   {self.client_state(c)}")
        if self.trial_active(uid):
            t.append(f"🎁 <b>تست رایگان</b>   {human_left(c['trial_expires_at'])}")
        elif c and c["expires_at"]:
            t.append(f"⏳ <b>اعتبار</b>   {human_left(c['expires_at'])}")
        if self.shop and self.cfg["points_on"]:
            pb = self.shop.p_balance(uid)
            note = "  ·  اشتراک فعال، بدون مصرف" if self.has_sub(uid) else ""
            t.append(f"🎯 <b>امتیاز</b>   {_fa_digits(pb)}  ·  ≈{_fa_digits(self.hours_left(uid))} ساعت{note}")
        if self.shop:
            b = self.shop.balance(uid)
            t.append(f"💳 <b>کیف پول</b>   {money(b)}")
            refs = len(self.shop.my_refs(uid))
            if refs:
                t.append(f"🎁 <b>زیرمجموعه</b>   {_fa_digits(refs)} نفر")
        t.append(self.LINE)

        # راهنمای قدم بعدی
        has_credit = self.has_sub(uid) or (
            self.shop and self.cfg["points_on"]
            and self.shop.p_balance(uid) >= self.cfg["min_points"])
        steps = []
        if not has_credit:
            steps.append(f"<b>{_fa_digits(1)}.</b> اشتراک یا امتیاز بخر 👇")
        if not (c and c["session"]):
            steps.append(f"<b>{_fa_digits(len(steps) + 1)}.</b> سلف را روی اکانتت راه بینداز")
        if steps:
            t.append("")
            t.append("🔰 <b>برای شروع</b>")
            t += steps
        elif c and c["session"] and not self.sup.is_running(uid):
            t.append("")
            t.append("▶️ سرویست خاموش است — از «سرویس من» روشنش کن.")

        if self.cfg["contact"]:
            t.append(f"\n🎧 پشتیبانی: {self.cfg['contact']}")
        return "\n".join(t)

    def _jafj_summary_line(self, uid):
        js = self.sup.jafj_summary(uid)
        if not js["folder_exists"]:
            return "ندارد (پوشه خالی)"
        parts = []
        ch = js["channel_std"] or js["channel_vip"]
        if ch:
            parts.append(f"کانال {self._esc(ch)}")
        if js["ex_enabled"]:
            parts.append("تبادل روشن")
        if js["ex_groups"]:
            parts.append(f"{_fa_digits(js['ex_groups'])} گروه تبادل")
        if js["ex_custom_msgs"]:
            parts.append(f"{_fa_digits(js['ex_custom_msgs'])} متن تبادل")
        if js["ex_rows"]:
            parts.append(f"{_fa_digits(js['ex_rows'])} رکورد تبادل")
        if js["queue_rows"]:
            parts.append(f"{_fa_digits(js['queue_rows'])} صف")
        if parts:
            return " · ".join(parts)
        if js["has_settings"] or js["has_db"]:
            return "پیش‌فرض (بدون کانال/گروه تبادل)"
        return "ثبت نشده"

    def _admin_user_text(self, c):
        if not c:
            return "پیدا نشد."
        uid = c["uid"]
        pr = self.shop.x("SELECT balance FROM points WHERE uid=?", (uid,), "one") if self.shop else None
        pts = pr["balance"] if pr else 0
        wal = self.shop.balance(uid) if self.shop else 0
        live = "🟢 روشن" if self.sup.is_running(uid) else "⚪ خاموش"
        return (
            f"👤 <b>{self._esc(c.get('name') or '—')}</b>\n{self.LINE}\n"
            f"uid: <code>{uid}</code>\n"
            f"یوزرنیم: @{self._esc(c.get('username') or '—')}\n"
            f"وضعیت: {self.client_state(c)}\n"
            f"پروسه: {live}\n"
            f"اعتبار: {human_left(c.get('expires_at') or 0)}\n"
            f"سشن: {'✅' if c.get('session') else '❌'}\n"
            f"شماره: {self._esc(c.get('phone') or '—')}\n"
            f"🎯 امتیاز: {_fa_digits(pts)}\n"
            f"💳 کیف پول: {money(wal)}\n"
            f"⚙️ جفج/تبادل: {self._jafj_summary_line(uid)}\n"
            f"{self.LINE}")

    def _admin_user_kb(self, c):
        uid = c["uid"]
        banned = c.get("status") == "banned"
        return [
            [B("⛔ بن" if not banned else "✅ آنبن",
               f"ab:{uid}:{'1' if not banned else '0'}",
               "danger" if not banned else "success"),
             B("🗑 حذف اشتراک", f"as:{uid}", "danger")],
            [B("➕ ۱۰ امتیاز", f"ag:{uid}:10", "success"),
             B("➖ ۱۰ امتیاز", f"ag:{uid}:-10", "danger")],
            [B("➕ ۲۰ امتیاز", f"ag:{uid}:20", "success"),
             B("➖ ۲۰ امتیاز", f"ag:{uid}:-20", "danger")],
            [B("✏️ امتیاز دلخواه", f"ag:{uid}:x", "primary"),
             B("📅 دادن روز", f"ad:{uid}", "success")],
            [B("➕ اکانت +۱", f"ac:{uid}:1", "success"),
             B("➖ اکانت -۱", f"ac:{uid}:-1", "danger")],
            [B("👥 اکانت دلخواه", f"ac:{uid}:x", "primary"),
             B("🐞 برگشت به پلن", f"ac:{uid}:0", "warning")],
            [B("💬 پیام به کاربر", f"am:{uid}", "primary"),
             B("▶️ روشن" if not self.sup.is_running(uid) else "⏹ خاموش",
               f"aproc:{uid}",
               "success" if not self.sup.is_running(uid) else "danger")],
            [B("♻️ ریست تست رایگان", f"aut:{uid}", "warning")],
            [B("🧹 پاک کردن تنظیمات جفج/تبادل", f"auj:{uid}", "danger"),
             B("🗑 پاک کردن کل اطلاعات", f"aud:{uid}", "danger")],
            [B("⬅️ لیست مشتری", "a:ulist:0", "primary"),
             B("🛠 پنل", "a:home", "danger")],
        ]

    def _user_or_orphan(self, tid):
        """رکورد کاربر را برمی‌گرداند؛ حتی اگر فقط پوشه‌ی جفج/تبادل یا داده‌ی فروشگاهش مانده باشد."""
        tid = int(tid or 0)
        if tid <= 0:
            return None
        c = self.db.get(tid)
        if c:
            return c
        has_dir = os.path.isdir(os.path.join(CLIENTS_DIR, str(tid)))
        has_shop = bool(self.shop and self.shop.has_user_data(tid))
        if has_dir or has_shop:
            return {
                "uid": tid, "username": "", "name": f"کاربر {tid} (داده‌ی باقیمانده)",
                "phone": "", "tg_id": tid, "session": "", "status": "new",
                "expires_at": 0, "created_at": now(), "restarts": 0,
            }
        return None

    def _resolve_admin_users(self, query):
        """جستجوی کاربر (در clients + پوشه‌ی clients/ + فروشگاه)."""
        raw = str(query or "").strip()
        if not raw:
            return []
        rows = self.db.find_users(raw)
        num = digits(raw)
        if not rows and num and raw.lstrip("+- ").replace(" ", "").isdigit():
            try:
                orphan = self._user_or_orphan(int(num))
                if orphan:
                    rows = [orphan]
            except Exception:
                pass
        return rows

    def _admin_wipe_confirm_view(self, tid):
        c = self._user_or_orphan(tid)
        if not c:
            return "کاربر پیدا نشد.", [back_btn("a:ulist:0")]
        js = self.sup.jafj_summary(tid)
        pr = self.shop.x("SELECT balance FROM points WHERE uid=?", (tid,), "one") if self.shop else None
        pts = pr["balance"] if pr else 0
        wal = self.shop.balance(tid) if self.shop else 0
        txt = (
            f"⚠️ <b>پاک کردن کامل اطلاعات کاربر</b>\n{self.LINE}\n"
            f"👤 نام: <b>{self._esc(c.get('name') or '—')}</b>\n"
            f"🆔 آیدی: <code>{tid}</code>\n"
            f"📱 شماره: {self._esc(c.get('phone') or '—')}\n"
            f"🎯 امتیاز: {_fa_digits(pts)}  ·  💳 کیف پول: {money(wal)}\n"
            f"⚙️ جفج/تبادل: {self._jafj_summary_line(tid)}\n"
            f"{self.LINE}\n"
            "با زدن تأیید، همه‌ی موارد زیر <b>کاملاً و غیرقابل‌بازگشت</b> پاک می‌شوند:\n"
            "• پروفایل، شماره، وضعیت تأیید، اشتراک و تست رایگان\n"
            "• سشن تلگرام و توقف کامل پروسه‌ی سلف\n"
            "• <b>تنظیمات جفج و تنظیمات تبادل</b> (کانال‌ها، گروه‌های تبادل، متن‌های تبادل، زمان‌بندی‌ها، اسکن و محافظ ریسک + بکاپ‌ها)\n"
            f"• <b>دیتابیس تبادل و صف ارسال</b> ({_fa_digits(js['ex_rows'])} رکورد تبادل، {_fa_digits(js['queue_rows'])} آیتم صف)\n"
            "• امتیازها، کیف پول، سفارش‌ها، تیکت‌ها و زیرمجموعه"
        )
        kb = [
            [B("✅ بله، کل اطلاعات کاربر پاک شود", f"audx:{tid}", "danger")],
            [B("🧹 فقط تنظیمات جفج و تبادل پاک شود", f"aujx:{tid}", "primary")],
            [B("❌ انصراف و بازگشت", f"au:{tid}")],
        ]
        return txt, kb

    def _admin_jafj_wipe_confirm_view(self, tid):
        c = self._user_or_orphan(tid)
        if not c:
            return "کاربر پیدا نشد.", [back_btn("a:ulist:0")]
        js = self.sup.jafj_summary(tid)
        ch_std = self._esc(js["channel_std"] or "—")
        ch_vip = self._esc(js["channel_vip"] or "—")
        txt = (
            f"🧹 <b>پاک کردن تنظیمات جفج و تبادل کاربر</b>\n{self.LINE}\n"
            f"👤 نام: <b>{self._esc(c.get('name') or '—')}</b>  (<code>{tid}</code>)\n"
            f"📢 کانال عادی: {ch_std}  ·  VIP: {ch_vip}\n"
            f"🔄 وضعیت تبادل: {'روشن' if js['ex_enabled'] else 'خاموش'}  ·  "
            f"{_fa_digits(js['ex_groups'])} گروه  ·  "
            f"{_fa_digits(js['ex_custom_msgs'])} متن سفارشی\n"
            f"🗄 دیتابیس سلف: {_fa_digits(js['ex_rows'])} رکورد تبادل  ·  "
            f"{_fa_digits(js['queue_rows'])} آیتم صف\n"
            f"{self.LINE}\n"
            "با تأیید این گزینه:\n"
            "• تمام <b>تنظیمات جفج</b> و <b>تنظیمات تبادل</b> (کانال‌ها، گروه‌ها، متن‌ها، زمان‌بندی‌ها و بکاپ‌های تنظیمات) پاک و به حالت خام اولیه برمی‌گردد.\n"
            "• کل <b>دیتابیس تبادل و صف ارسال</b> (`jafj.db`) پاک می‌شود.\n"
            "• ✅ اشتراک، امتیاز، کیف پول و سشن ورود کاربر <b>حفظ می‌شود</b>."
        )
        kb = [
            [B("✅ بله، تنظیمات جفج و تبادل پاک شود", f"aujx:{tid}", "danger")],
            [B("🗑 کل اطلاعات کاربر هم پاک شود", f"aud:{tid}", "danger")],
            [B("❌ انصراف و بازگشت", f"au:{tid}")],
        ]
        return txt, kb

    def _refresh_local_backups_after_wipe(self):
        """همگام‌سازی فوری دیسک/پشتیبان محلی بعد از حذف اطلاعات تا در بازیابی برنگردد."""
        for handle in (getattr(self, "db", None), getattr(self, "shop", None)):
            if handle is not None:
                try:
                    handle.c.execute("PRAGMA wal_checkpoint(TRUNCATE)")
                except Exception:
                    pass
                try:
                    handle.c.commit()
                except Exception:
                    pass
        try:
            cnt = self.db.x("SELECT COUNT(*) c FROM clients", (), "one")
            if cnt and int(cnt.get("c") or 0) == 0:
                self._allow_empty_backup_once = True
        except Exception:
            pass
        latest = os.path.join(BASE_DIR, "jafj_backup_latest.zip")
        has_local_bak = os.path.isfile(latest) or os.path.isdir(os.path.join(BASE_DIR, "backups"))
        if has_local_bak:
            tmp = os.path.join(tempfile.gettempdir(), f"jafj_wipe_bk_{os.getpid()}.zip")
            try:
                zc, sz, _om = self._write_backup_zip(tmp)
                if zc > 0 and sz > 0 and os.path.isfile(tmp):
                    self._save_local_backup_copy(tmp)
            except Exception as e:
                print("refresh_local_backups_after_wipe:", type(e).__name__, e)
            finally:
                try:
                    if os.path.exists(tmp):
                        os.remove(tmp)
                except Exception:
                    pass

    async def wipe_user_jafj(self, tid, by_admin=0):
        async with self._backup_operation_lock():
            return await self._wipe_user_jafj_locked(tid, by_admin)

    async def _wipe_user_jafj_locked(self, tid, by_admin=0):
        """پاک کردن کامل تنظیمات جفج + تنظیمات و دیتابیس تبادل یک کاربر (با حفظ حساب/سشن)."""
        tid = int(tid or 0)
        c = self._user_or_orphan(tid)
        if not c:
            return False, "کاربر پیدا نشد.", {}
        plan = self.effective_plan(tid)
        mx = 1
        try:
            ov = int(c.get("max_accounts") or 0)
            mx = ov if ov > 0 else max(1, int((plan or {}).get("max_accounts", 1) or 1))
        except Exception:
            mx = 1
        res = await self._backup_run_blocking(
            self.sup.wipe_jafj_settings, tid, mx, bool(self.db.get(tid)))
        restarted = False
        if res["was_running"] and (self.db.get(tid) or {}).get("session"):
            allow, _why = self.can_run(tid)
            if allow:
                ok_st, _m = await self._backup_run_blocking(self.sup.start, tid)
                restarted = bool(ok_st)
        if self.db.get(tid):
            self.db.log(tid, "jafj_wiped", f"by={by_admin} files={res['removed_files']}")
        await self._backup_run_blocking(self._refresh_local_backups_after_wipe)
        touch_data("wipe_jafj")
        msg = (
            f"🧹 <b>تنظیمات جفج و تبادل کاربر <code>{tid}</code> پاک شد.</b>\n"
            f"{self.LINE}\n"
            f"• فایل‌های پاک‌شده (تنظیمات/تبادل/صف/بکاپ): {_fa_digits(res['removed_files'])}\n"
            f"• تنظیمات جفج و تبادل به حالت خام اولیه برگشت.\n"
            + ("• 🟢 سلف با تنظیمات خام دوباره روشن شد." if restarted else
               "• سشن و اشتراک/امتیاز کاربر بدون تغییر حفظ شد.")
        )
        return True, msg, res

    async def wipe_user_data(self, tid, by_admin=0):
        async with self._backup_operation_lock():
            return await self._wipe_user_data_locked(tid, by_admin)

    async def _wipe_user_data_locked(self, tid, by_admin=0):
        """پاک کردن کامل کل اطلاعات یک کاربر (حساب + سشن + تنظیمات جفج/تبادل + فروشگاه)."""
        tid = int(tid or 0)
        c = self._user_or_orphan(tid)
        if not c:
            return False, "کاربر پیدا نشد.", {}
        name = c.get("name") or "—"
        await self.cancel(tid)
        self._receipts.pop(tid, None)
        self._join_ok.pop(tid, None)
        if getattr(self, "_login_notified", None):
            self._login_notified.pop(tid, None)
        js = self.sup.jafj_summary(tid)
        removed_files = await self._backup_run_blocking(self.sup.wipe_folder, tid)
        db_counts = self.db.delete_user(tid)
        shop_counts = self.shop.delete_user(tid) if self.shop else {
            "orders": 0, "wallet": 0, "points": 0, "tickets": 0, "referrals": 0}
        if by_admin and by_admin != tid:
            self.db.log(by_admin, "user_wiped", f"uid={tid}")
        await self._backup_run_blocking(self._refresh_local_backups_after_wipe)
        touch_data("wipe_user")
        stats = {
            "removed_files": removed_files,
            "db": db_counts,
            "shop": shop_counts,
            "jafj": js,
        }
        msg = (
            f"🗑 <b>کل اطلاعات کاربر کامل پاک شد</b>\n{self.LINE}\n"
            f"👤 کاربر: <b>{self._esc(name)}</b>  (<code>{tid}</code>)\n"
            f"• پروفایل، شماره، سشن و وضعیت تست/اشتراک: پاک شد\n"
            f"• تنظیمات جفج، تنظیمات تبادل و دیتابیس تبادل/صف: پاک شد "
            f"({_fa_digits(removed_files)} فایل)\n"
            f"• فروشگاه (امتیاز، کیف‌پول، {_fa_digits(shop_counts['orders'])} سفارش، "
            f"{_fa_digits(shop_counts['tickets'])} تیکت، زیرمجموعه): پاک شد"
        )
        return True, msg, stats

    def force_chans(self):
        return list(self.cfg.d.get("force_join") or [])

    def save_force_chans(self, rows):
        self.cfg["force_join"] = rows

    def _chan_url(self, ch):
        u = (ch.get("user") or "").lstrip("@")
        if u:
            return f"https://t.me/{u}"
        return ""

    async def bot_admin_in(self, ent):
        try:
            perm = await self.bot.get_permissions(ent, "me")
            return bool(getattr(perm, "is_admin", False))
        except Exception as e:
            print("bot_admin_in:", type(e).__name__, e)
            return False

    async def missing_joins(self, uid):
        chans = self.force_chans()
        if not chans or self.is_admin(uid):
            return []
        until = self._join_ok.get(uid) or 0
        if until > now():
            return []
        from telethon.errors import UserNotParticipantError
        missing = []
        for ch in chans:
            ent = ch.get("id") or ch.get("user")
            if not ent:
                continue
            # رفع باگِ قفلِ کاذب: ابتدا entityِ واقعیِ کانال را resolve کن؛
            # اگر کانال برایِ خودِ بات هم قابل‌دیدن نبود، آن را «missing»
            # نشمار (چون به‌معنای عضویتِ کاربر نیست)، فقط گزارش بده.
            try:
                ent = await self.bot.get_entity(ent)
            except Exception as e:
                print("joincheck (entity skip):", ch, type(e).__name__, e)
                continue
            try:
                perm = await self.bot.get_permissions(ent, uid)
                left = bool(getattr(perm, "has_left", False))
                kicked = bool(getattr(perm, "has_banned", False) or
                              getattr(perm, "is_banned", False))
                if left or kicked:
                    missing.append(ch)
            except UserNotParticipantError:
                missing.append(ch)
            except Exception as e:
                # فقط خطای «کاربر عضو نیست» را missing بشمار؛ خطاهای عمومی
                # (مثلاً بات ادمینِ کانال نیست) را نباید قفلِ کاذب حساب کنیم.
                print("joincheck (skip):", ch, type(e).__name__, e)
        if missing:
            self._join_ok.pop(uid, None)
        else:
            self._join_ok[uid] = now() + 15
        return missing

    def join_gate_text(self, missing):
        L = ["🔒 <b>عضویت اجباری</b>", self.LINE,
             "برای استفاده از ربات باید در کانال/گروه زیر عضو باشی.",
             "اگر لفت بدهی، دوباره همینجا گیر می‌کنی.", "", self.LINE]
        for i, ch in enumerate(missing, 1):
            title = ch.get("title") or ch.get("user") or str(ch.get("id"))
            L.append(f"{_fa_digits(i)}. <b>{title}</b>")
        L += ["", "اول عضو شو، بعد «عضو شدم» را بزن."]
        return "\n".join(L)

    def join_gate_kb(self, missing):
        from telethon import Button
        rows = []
        for ch in missing:
            title = ch.get("title") or ch.get("user") or "کانال"
            url = self._chan_url(ch)
            if url:
                rows.append([Button.url(f"📢 عضویت — {title[:24]}", url)])
        rows.append([B("✅ عضو شدم — بررسی", "fj:ok", "success")])
        return rows

    async def enforce_join(self, uid, ev=None, chat=None):
        if self.is_admin(uid):
            return False
        missing = await self.missing_joins(uid)
        if not missing:
            return False
        t, kb = self.join_gate_text(missing), self.join_gate_kb(missing)
        if ev is not None:
            try:
                await ev.edit(t, parse_mode="html", buttons=kb, link_preview=False)
            except Exception:
                await self.say(chat or uid, t, kb)
        else:
            await self.say(chat or uid, t, kb)
        return True

    # ═══════════════════════════════════════════════
    #  آموزش فعال‌سازی — دکمه‌ی «📚 آموزش فعال‌سازی»
    # ═══════════════════════════════════════════════
    def tut_src(self):
        """منبع محتوای آموزش: (chat_id, [msg_id, ...]) یا (0, [])."""
        try:
            chat = int(self.cfg.get("tut_chat") or 0)
        except (TypeError, ValueError):
            chat = 0
        try:
            ids = [int(x) for x in (self.cfg.get("tut_ids") or [])]
        except (TypeError, ValueError):
            ids = []
        return chat, ids

    def samples_src(self):
        """منبع نمونه‌های جفج رفتن ربات: (chat_id, [msg_id, ...])."""
        try:
            chat = int(self.cfg.get("sample_chat") or 0)
        except (TypeError, ValueError):
            chat = 0
        try:
            ids = [int(x) for x in (self.cfg.get("sample_ids") or [])]
        except (TypeError, ValueError):
            ids = []
        return chat, ids

    async def send_samples(self, uid):
        """نمونه‌های ثبت‌شده را به همان ترتیبی که مدیر فرستاده کپی می‌کند."""
        chat, ids = self.samples_src()
        msgs = await self._tut_load(chat, ids)
        if not msgs:
            return await self.say(uid,
                "🎞 <b>نمونه‌های جفج رفتن ربات</b>\n\n"
                "هنوز نمونه‌ای برای نمایش ثبت نشده است. لطفاً کمی بعد دوباره سر بزن.",
                [back_btn()])
        sent, _ = await self._tut_copy(uid, msgs, chat)
        if not sent:
            return await self.say(uid,
                "متأسفانه نمونه‌ها الان ارسال نشدند. لطفاً کمی بعد دوباره تلاش کن.",
                [back_btn()])
        return True

    @staticmethod
    def _tut_groups(msgs):
        """پیام‌های آلبوم (grouped_id یکسان و پشت‌سرهم) را یک گروه می‌کند."""
        groups = []
        for m in msgs:
            gid = getattr(m, "grouped_id", None)
            if groups and gid and getattr(groups[-1][0], "grouped_id", None) == gid:
                groups[-1].append(m)
            else:
                groups.append([m])
        return groups

    async def _tut_load(self, chat, ids):
        """پیام‌های ثبت‌شده‌ی یک لیست را از تلگرام می‌خواند.

        پیام‌های حذف‌شده (None) و پیام‌های سرویس فیلتر می‌شوند.
        """
        if not chat or not ids:
            return []
        try:
            got = await self.bot.get_messages(chat, ids=list(ids))
        except Exception as e:
            print("tut fetch:", type(e).__name__, e)
            return []
        return [m for m in (got or [])
                if m is not None and (m.media or (m.raw_text or "").strip())]

    async def _tut_copy(self, uid, msgs, chat, buttons=None):
        """پیام‌ها را کپی می‌کند؛ دکمه‌ها به آخرین پیام می‌چسبند.

        خروجی: (تعداد ارسال‌شده, آیا دکمه‌ها چسبیدند)
        دکمه فقط وقتی روی خودِ آخرین پیام می‌نشیند که آن پیام <b>تک</b> باشد؛
        تلگرام روی آلبوم دکمه‌ی شیشه‌ای نمی‌گذارد، پس آن‌جا پایین بخش یک
        پیام جداگانه با دکمه می‌فرستیم.
        """
        groups = self._tut_groups(msgs)
        ok = 0
        attached = False
        for i, grp in enumerate(groups):
            last = (i == len(groups) - 1)
            b = buttons if (last and buttons and len(grp) == 1) else None
            try:
                if len(grp) == 1:
                    # Telethon خودش پیامِ Message را کپی می‌کند: مدیا با کپشن
                    # و فرمت، متنِ لینک‌دار با پیش‌نمایش — بدون هدر فوروارد.
                    if b:
                        await self.bot.send_message(uid, grp[0], buttons=b)
                        attached = True
                    else:
                        await self.bot.send_message(uid, grp[0])
                else:
                    # آلبوم: همه‌ی مدیاها با هم، کپشنِ هر کدام سر جایش
                    caps = [(m.raw_text or "") for m in grp]
                    await self.bot.send_file(
                        uid, [m.media for m in grp],
                        caption=caps if any(caps) else None)
                ok += 1
            except Exception as e:
                # پلن ب: فوروارد (مثلاً FILE_REFERENCE منقضی شده)
                print("tut copy:", type(e).__name__, e)
                try:
                    await self.bot.forward_messages(uid, [m.id for m in grp], chat)
                    ok += 1
                except Exception as e2:
                    print("tut fwd:", type(e2).__name__, e2)
            await asyncio.sleep(0.25)
        return ok, attached

    # ── مدیریتِ دانه‌دانه‌ی محتوا: فهرست، حذف یک مورد، حذف همه ──
    async def _tut_items(self, chat, ids):
        """محتوای ثبت‌شده را با جای هر آیتم برمی‌گرداند.

        خروجی: [(جایِ پیام در لیستِ ids, Message), ...]

        چرا «جای در ids» مهم است: آیتم‌ها با شماره‌شان در همین فهرست حذف
        می‌شوند؛ اگر چند پیام وسط کار از تلگرام پاک شده باشند (None) یا
        پیام سرویس باشند، شماره‌ها نباید جابه‌جا شوند وگرنه مدیر به‌جای
        ویدیوی اول، ویدیوی دوم را پاک می‌کند. فیلتر دقیقاً همان فیلترِ
        _tut_load است تا شماره‌ی فهرست با چیزی که برای کاربر می‌رود یکی باشد.
        """
        items = []
        if not chat or not ids:
            return items
        try:
            got = await self.bot.get_messages(chat, ids=list(ids))
        except Exception as e:
            print("tut items:", type(e).__name__, e)
            return items
        for i, m in enumerate(got or []):
            if i >= len(ids):
                break
            if m is None:
                continue
            if not (getattr(m, "media", None) or (getattr(m, "raw_text", "") or "").strip()):
                continue
            items.append((i, m))
        return items

    @staticmethod
    def _content_kind(m=None, text=""):
        """نوعِ یک پیام/مدیا به شکلِ برچسبِ خوانا (🎬 ویدیو، 📝 متن…)."""
        if m is not None:
            if getattr(m, "photo", None):
                return "🖼 عکس"
            if getattr(m, "video", None):
                return "🎬 ویدیو"
            if getattr(m, "gif", None):
                return "🎞 گیف"
            if getattr(m, "voice", None):
                return "🎤 ویس"
            if getattr(m, "audio", None):
                return "🎵 آهنگ"
            if getattr(m, "sticker", None):
                return "🎨 استیکر"
            if getattr(m, "contact", None):
                return "👤 مخاطب"
            if getattr(m, "document", None):
                return "📎 فایل"
        t = (text or "").strip()
        if not t and m is not None:
            t = (getattr(m, "raw_text", "") or "").strip()
        return "📝 متن" if t else "💬 پیام"

    @staticmethod
    def _content_snippet(m, limit=42):
        """یک خط خلاصه از پیام تا مدیر بفهمد کدام ویدیو/متن را دارد پاک می‌کند."""
        raw = " ".join((getattr(m, "raw_text", "") or "").split())
        if not raw:
            try:
                f = getattr(m, "file", None)
                raw = str(getattr(f, "name", "") or "").strip()
            except Exception:
                raw = ""
        raw = raw[:limit]
        return Manager._esc(raw + ("…" if len(raw) >= limit else "")) if raw else ""

    def tut_content_del(self, step, sid, index):
        """یک آیتم از محتوای ثبت‌شده را پاک می‌کند (ویدیو، متن، ویس… فرقی ندارد).

        index = جای آیتم در فهرستِ _tut_items (همان شماره‌ای که مدیر می‌بیند).
        خروجی: تعداد آیتم‌های باقی‌مانده، یا None اگر بخش/محتوا پیدا نشد.
        """
        try:
            index = int(index)
        except (TypeError, ValueError):
            return None
        if step == "sec_set":
            s = self.tut_find(sid)
            if not s:
                return None
            ids = list(s["ids"] or [])
            chat = int(s["chat"] or 0)
        else:
            chat, ids = self.tut_src()
            ids = list(ids or [])
        if index < 0 or index >= len(ids):
            return None
        del ids[index]
        if step == "sec_set":
            self.tut_update(sid, chat=chat, ids=ids)
        else:
            self.cfg["tut_chat"] = chat
            self.cfg["tut_ids"] = ids
            self.cfg.save()
        return len(ids)

    def tut_content_clear(self, step, sid=0):
        """همه‌ی محتوای ثبت‌شده (متن/ویدیو/ویس/عکس/…) را یک‌جا پاک می‌کند."""
        if step == "sec_set":
            self.tut_update(sid, chat=0, ids=[])
        else:
            self.cfg["tut_chat"] = 0
            self.cfg["tut_ids"] = []
            self.cfg.save()
        return True

    async def send_tutorial(self, uid):
        """محتوای «📚 آموزش فعال‌سازی» را برای کاربر می‌فرستد.

        پیام‌ها <b>کپی</b> می‌شوند (بدون هدر فوروارد) تا مثل پیام خودِ ربات
        باشند — مدیا، کپشن، فرمتِ متن و پیش‌نمایش لینک همه حفظ می‌شوند؛
        یعنی هر نوعی که مدیر از پنل ثبت کرده باشد: متن، لینک، عکس، ویدیو،
        ویس، فایل، استیکر، آلبوم…
        اگر کپی ممکن نشد همان پیام فوروارد می‌شود؛ اگر هیچ‌طور نرفت،
        متن پیش‌فرض آموزش ارسال می‌شود.

        بعد از محتوای اصلی، اگر مدیر «بخش» ساخته باشد، تگِ هر بخش هم
        پایین فرستاده می‌شود تا کاربر هر آموزش را جدا بگیرد.
        """
        chat, ids = self.tut_src()
        msgs = await self._tut_load(chat, ids)
        if not msgs:
            await self.say(uid, DEFAULT_TUTORIAL,
                           [[B("🚀 راه‌اندازی سلف روی اکانتم", "s:setup", "primary")],
                            back_btn()])
        else:
            ok, _ = await self._tut_copy(uid, msgs, chat)
            if ok:
                await self.say(uid,
                    f"📚 <b>آموزش فعال‌سازی</b>\n{self.LINE}\n"
                    "سوالی داشتی از «🎧 پشتیبانی» بپرس.\n"
                    "برای شروع، دکمه‌ی زیر:",
                    [[B("🚀 راه‌اندازی سلف روی اکانتم", "s:setup", "primary")],
                     back_btn()])
            else:
                await self.say(uid, DEFAULT_TUTORIAL,
                               [[B("🚀 راه‌اندازی سلف روی اکانتم", "s:setup", "primary")],
                                back_btn()])
        # تگِ بخش‌ها پایین آموزش
        return await self.tut_send_menu(uid)

    async def send_menu_tutorial(self, uid, key):
        """«📚 آموزش …» آخرِ منوهای کیف پول / خرید امتیاز / اشتراک ماهانه.

        زدن دکمه = ارسال خودکارِ آموزشِ همان کار با تحویلِ تمیز (bare=True):
        فقط و فقط «محتوای ثبت‌شده‌ی مدیر» + «دکمه‌ی پایانِ همان کار» — بدون هیچ
        متنِ اضافه‌ای بینشان: نه «متن پایان» (note) و نه تزریقِ متنِ آماده‌ی
        پیش‌فرض وقتی مدیر پیام/محتوا ثبت کرده. اگر محتوایی ثبت نشده باشد
        fallback: متن آماده‌ی پیش‌فرض + همان دکمه — دکمه هیچ‌وقت خالی نیست.
        """
        if key not in self.TUT_MENU_KEYS:
            return False
        sec = self.tut_find_preset(key)
        if sec and sec["on"]:
            ok = await self.tut_send_section(uid, sec["id"], force=True, bare=True)
            if ok:
                return True
        lbl, cmd = self.TUT_MENU_FOOT[key]
        return await self.say(uid, self.tut_preset_text(key) or DEFAULT_TUTORIAL,
                              [[B(lbl, cmd, "success")]],
                              key=f"tut:x:{key}")

    # ═══════════════════════════════════════════════
    #  بخش‌بندی آموزش — هر بخش یک «تگ» که کاربر می‌زند
    #  (مدیر: محتوا + زمان ارسال + دکمه‌ی پایان بخش)
    # ═══════════════════════════════════════════════
    TUT_WHENS = (
        ("after_run",    "🟢 بعد از فعال‌سازی سلف — خودکار"),
        ("after_wallet", "💳 بعد از شارژ کیف پول — خودکار"),
        ("after_points", "🎯 بعد از تأیید خرید امتیاز — خودکار"),
        ("after_sub",    "💎 بعد از تأیید اشتراک ماهانه — خودکار"),
        ("manual",       "👉 فقط با دکمه (کاربر خودش می‌زند)"),
    )
    # دکمه‌ی پایان هر بخش — مقصدهای آماده
    TUT_TARGETS = (
        ("w:topup",   "💳 شارژ کیف پول"),
        ("m:wallet",  "💳 کیف پول من"),
        ("m:packs",   "🎯 خرید امتیاز"),
        ("m:plans",   "💎 اشتراک ماهانه"),
        ("m:pts",     "🎯 امتیاز من"),
        ("m:svc",     "⚙️ سرویس من"),
        ("s:setup",   "🚀 راه‌اندازی سلف"),
        ("m:support", "🎧 پشتیبانی"),
        ("m:tut",     "📚 آموزش‌ها"),
        ("m:home",    "🏠 منوی اصلی"),
    )
    TUT_FOOT_FALLBACK = "👇"

    def tut_sections(self, on_only=False):
        """لیست بخش‌ها (نرمال‌شده، به ترتیب نمایش)."""
        raw = self.cfg.get("tut_sections") or []
        out = []
        if not isinstance(raw, list):
            return out
        for i, s in enumerate(raw):
            d = self.tut_norm(s, i)
            if on_only and not d["on"]:
                continue
            out.append(d)
        return out

    @staticmethod
    def tut_norm(s, idx=0):
        """بخش خام را به شکلِ کامل و قابل‌اتکا درمی‌آورد (همه‌ی کلیدها همیشه)."""
        s = s if isinstance(s, dict) else {}
        try:
            sid = int(s.get("id") or idx + 1)
        except (TypeError, ValueError):
            sid = idx + 1
        try:
            ids = [int(x) for x in (s.get("ids") or [])]
        except (TypeError, ValueError):
            ids = []
        try:
            chat = int(s.get("chat") or 0)
        except (TypeError, ValueError):
            chat = 0
        try:
            delay = max(0, int(s.get("delay") or 0))
        except (TypeError, ValueError):
            delay = 0
        when = str(s.get("when") or "after_run")
        if when not in dict(Manager.TUT_WHENS):
            when = "after_run"
        return {
            "id": sid,
            "name": str(s.get("name") or f"بخش {sid}")[:60],
            "emoji": str(s.get("emoji") or "▫️")[:4],
            "chat": chat,
            "ids": ids,
            "when": when,
            "delay": delay,
            "on": bool(s.get("on", True)),
            "once": bool(s.get("once", True)),
            "header": bool(s.get("header", False)),
            # در فهرستِ «🗂 آموزشها» دیده شود؟ (پیشفرض بله)
            "in_hub": bool(s.get("in_hub", True)),
            "note": str(s.get("note") or "")[:1000],
            "btn_label": str(s.get("btn_label") or "")[:40],
            "btn_cmd": str(s.get("btn_cmd") or "")[:64],
            # متنِ آماده‌ی بخش (HTML) — بدون نیاز به ثبت پیام از چت مدیر
            "text": str(s.get("text") or "")[:3500],
            # اگر از یکی از متن‌های آماده ساخته شده، کلیدش (wallet/points/sub/after_run)
            "preset": str(s.get("preset") or "")[:20],
        }

    def tut_when_label(self, when):
        return dict(self.TUT_WHENS).get(when, when)

    def tut_sec_label(self, s):
        return f"{s.get('emoji') or '▫️'} {s.get('name') or 'بخش'}"

    def tut_next_id(self):
        return max([0] + [s["id"] for s in self.tut_sections()]) + 1

    def tut_find(self, sid):
        try:
            sid = int(sid)
        except (TypeError, ValueError):
            return None
        for s in self.tut_sections():
            if s["id"] == sid:
                return s
        return None

    def tut_save(self, rows):
        # قبل از هر تغییرِ بخش‌ها یک نسخه‌ی زمان‌دار از کانفیگ می‌گذاریم؛ اگر
        # روزی نسخه‌ی قدیمیِ کانفیگ از راه رسید (پشتیبانِ کهنه / pullِ سینکِ
        # گیت‌هاب / نمونه‌ی زامبی) و بخش‌ها پریدند، از همین‌ها برمی‌گردند.
        cfg_snapshot("sections")
        self.cfg["tut_sections"] = [self.tut_norm(s, i) for i, s in enumerate(rows)]
        self.cfg.save()
        return self.cfg["tut_sections"]

    def tut_update(self, sid, **kw):
        rows = self.tut_sections()
        hit = None
        for s in rows:
            if s["id"] == int(sid):
                s.update({k: v for k, v in kw.items() if k in s})
                hit = s
                break
        if hit is None:
            return None
        self.tut_save(rows)
        return self.tut_find(sid)

    def tut_new(self, name="بخش جدید", emoji="▫️"):
        rows = self.tut_sections()
        sid = self.tut_next_id()
        rows.append(self.tut_norm({"id": sid, "name": name, "emoji": emoji,
                                   "when": "after_run", "on": True, "once": True}))
        self.tut_save(rows)
        return self.tut_find(sid)

    def tut_remove(self, sid):
        rows = [s for s in self.tut_sections() if s["id"] != int(sid)]
        self.tut_save(rows)
        return True

    def tut_move(self, sid, delta):
        """جای بخش را در لیست عوض می‌کند (ترتیب ارسال)."""
        rows = self.tut_sections()
        idx = next((i for i, s in enumerate(rows) if s["id"] == int(sid)), None)
        if idx is None:
            return False
        j = max(0, min(len(rows) - 1, idx + int(delta)))
        if j == idx:
            return False
        rows.insert(j, rows.pop(idx))
        self.tut_save(rows)
        return True

    # ═══════════════════════════════════════════════
    #  ثبت محتوای آموزش/بخش — دو حالت: «افزودن» و «جایگزینی»
    # ═══════════════════════════════════════════════
    def tut_capture_start(self, uid, step, sid=0, append=False):
        """حالتِ گرفتنِ پیام‌های مدیر را باز می‌کند و لیستِ در‌انتظار را می‌سازد.

        append=True یعنی محتوای قبلیِ همین بخش (یا آموزش فعال‌سازی اصلی) سرِ
        جایش می‌ماند و پیام‌های تازه <b>به آخرِ آن اضافه</b> می‌شوند — پس فردا
        می‌شود ویدیوی دوم را پشت ویدیوی اول پیوند زد بدون اینکه چیزی پاک شود.
        append=False رفتار قدیمی است: هرچه از قبل ثبت شده <b>جایگزین</b> می‌شود.

        خروجی: (حالتِ واقعی, تعداد پیامِ قبلی)
        """
        mode = "append" if append else "replace"
        have, src_chat = [], 0
        if step == "sec_set":
            s = self.tut_find(sid) or {}
            have, src_chat = list(s.get("ids") or []), int(s.get("chat") or 0)
        elif step == "tut_set":
            chat0, ids0 = self.tut_src()
            have, src_chat = list(ids0 or []), int(chat0 or 0)
        if mode == "append" and not have:
            mode = "replace"          # چیزی نیست که به آن اضافه شود
        st = {"step": step, "mode": mode, "tut_chat": src_chat,
              "tut_pending": list(have) if mode == "append" else []}
        if step == "sec_set":
            st["sec_id"] = int(sid)
        self.fsm[uid] = st
        return mode, len(have)

    # ═══════════════════════════════════════════════
    #  چهار متنِ آماده‌ی آموزش — مدیر با یک دکمه از پنل می‌سازد
    #  (کیف پول / خرید امتیاز / اشتراک ماهانه / بعد از فعال‌سازی)
    #  متن‌ها با اعداد تنظیمات (حداقل شارژ، امتیاز هر ساعت…) پر می‌شوند.
    #  دکمه‌های «📚 آموزش …» آخرِ منوهای کیف پول / خرید امتیاز / اشتراک ماهانه
    #  (tut:x:…) هم همین متن‌ها را می‌فرستند.
    # ═══════════════════════════════════════════════
    TUT_PRESETS = (
        ("wallet", {
            "name": "آموزش کیف پول", "emoji": "💳",
            "when": "after_wallet",
            "btn_cmd": "w:topup", "btn_label": "💳 شارژ کیف پول",
            "note": "برای شارژ کیف پول دکمه‌ی زیر را بزن 👇",
        }),
        ("points", {
            "name": "آموزش خرید امتیاز", "emoji": "🎯",
            "when": "after_points",
            "btn_cmd": "m:packs", "btn_label": "🎯 خرید امتیاز",
            "note": "برای خرید امتیاز دکمه‌ی زیر را بزن 👇",
        }),
        ("sub", {
            "name": "آموزش اشتراک ماهانه", "emoji": "💎",
            "when": "after_sub",
            "btn_cmd": "m:plans", "btn_label": "💎 اشتراک ماهانه",
            "note": "برای خرید اشتراک ماهانه دکمه‌ی زیر را بزن 👇",
        }),
        ("after_run", {
            "name": "بعد از فعال‌سازی", "emoji": "🚀",
            "when": "after_run",
            "btn_cmd": "m:svc", "btn_label": "⚙️ سرویس من",
            "note": "وضعیت سرویس و اعتبارت را از دکمه‌ی زیر ببین 👇",
        }),
    )

    # کلید دکمه‌های «📚 آموزش …» آخرِ منوها (tut:x:<key>)
    TUT_MENU_KEYS = ("wallet", "points", "sub")
    # دکمه‌ی پایانِ متنِ پیش‌فرضِ هر آموزش — مقصد + برچسب
    TUT_MENU_FOOT = {
        "wallet": ("💳 شارژ کیف پول", "w:topup"),
        "points": ("🎯 خرید امتیاز", "m:packs"),
        "sub":    ("💎 اشتراک ماهانه", "m:plans"),
        "after_run": ("⚙️ سرویس من", "m:svc"),
    }
    # شناسه‌ی رزرو در جدول tut_sent برای متن پیش‌فرضِ «بعد از فعال‌سازی»
    # (وقتی مدیر هنوز بخشی نساخته) — یک‌بار برای هر کاربر
    TUT_SELF_DEF_ID = 0

    def tut_preset_text(self, key):
        """متنِ آماده‌ی یک پیش‌فرض، با اعدادِ فعلیِ تنظیمات."""
        cfg = self.cfg
        L = self.LINE
        per = max(1, int(cfg.get("cost_per_hour", 1) or 1))
        mn_pts = int(cfg.get("min_points", 20) or 0)
        start_fee = int(cfg.get("start_fee", 0) or 0)
        low = int(cfg.get("low_warn", 10) or 0)
        pp = int(cfg.get("point_price", 250) or 0)
        mn_buy = int(cfg.get("min_points_buy", 20) or 0)
        mx_buy = int(cfg.get("max_points_buy", 5000) or 0)
        mn_top = int(cfg.get("min_topup", 10000) or 0)
        mx_top = int(cfg.get("max_topup", 5000000) or 0)
        if key == "wallet":
            return (
                f"💳 <b>آموزش کیف پول</b>\n{L}\n"
                "کیف پول، موجودیِ تومانیِ تو داخل ربات است؛ یک‌بار شارژ می‌کنی و "
                "بعداً خرید امتیاز یا اشتراک را بدون کارت‌به‌کارتِ دوباره، "
                "با همان موجودی انجام می‌دهی.\n\n"
                "<b>قدم ۱</b> — از منوی اصلی «💳 کیف پول» را بزن.\n"
                "<b>قدم ۲</b> — «➕ افزایش موجودی» و یکی از مبلغ‌ها را انتخاب کن، "
                "یا مبلغ دلخواه بفرست.\n"
                f"      <i>بین {money(mn_top)} تا {money(mx_top)}</i>\n"
                "<b>قدم ۳</b> — مبلغ را به شماره کارتِ داخل فاکتور واریز کن.\n"
                "<b>قدم ۴</b> — <b>عکس رسید</b> را همان‌جا بفرست.\n"
                "<b>قدم ۵</b> — بعد از تأیید مدیر، موجودی خودکار به کیف پولت "
                "اضافه می‌شود و پیام می‌گیری.\n\n"
                f"{L}\n"
                "💡 موقع خرید امتیاز یا اشتراک، دکمه‌ی «خرید با کیف پول» را بزن "
                "تا از موجودی کم شود — این خریدها نیاز به تأیید مدیر ندارند و "
                "درجا انجام می‌شوند.\n"
                "📋 گردش تراکنش‌ها همیشه در «💳 کیف پول» هست.\n\n"
                "⚠️ رسید را فقط داخل همین ربات بفرست؛ به کسی خارج از ربات نده."
            )
        if key == "points":
            return (
                f"🎯 <b>آموزش خرید امتیاز</b>\n{L}\n"
                "امتیاز، سوختِ سلف است: تا وقتی سلف روشن است، هر ساعت "
                f"<b>{_fa_digits(per)}</b> امتیاز کم می‌شود؛ خاموشش کنی، مصرف هم می‌ایستد.\n\n"
                "<b>قدم ۱</b> — از منوی اصلی «🎯 خرید امتیاز» را بزن.\n"
                "<b>قدم ۲</b> — یک بسته انتخاب کن (بسته‌های بزرگ‌تر 🎁 هدیه دارند)، "
                "یا «✏️ مقدار دلخواه» را بزن.\n"
                f"      <i>هر امتیاز {money(pp)} — بین {_fa_digits(mn_buy)} تا {_fa_digits(mx_buy)} امتیاز</i>\n"
                "<b>قدم ۳</b> — پرداخت:\n"
                "      • «💳 خرید با کیف پول» → درجا و بدون تأیید\n"
                "      • «✅ خرید» → کارت‌به‌کارت + ارسال <b>عکس رسید</b>\n"
                "<b>قدم ۴</b> — امتیاز بعد از تأیید به حسابت می‌نشیند و پیام می‌گیری.\n\n"
                f"{L}\n"
                f"🔓 برای روشن‌کردن سرویس حداقل <b>{_fa_digits(mn_pts)}</b> امتیاز لازم است.\n"
                + (f"▶️ هر بار روشن‌کردن <b>{_fa_digits(start_fee)}</b> امتیاز.\n" if start_fee else "")
                + f"🟠 زیر <b>{_fa_digits(low)}</b> امتیاز هشدار می‌گیری؛ صفر که شد سرویس خاموش می‌شود.\n"
                "🎟 کد تخفیف داری؟ روی بسته، «🎟 دارم کد تخفیف» را بزن.\n"
                "📋 موجودی و گردش امتیاز: «🎯 امتیاز من»."
            )
        if key == "sub":
            return (
                f"💎 <b>آموزش اشتراک ماهانه</b>\n{L}\n"
                "با اشتراک ماهانه، سلف تا پایان دوره روشن می‌ماند و هیچ امتیازی "
                "مصرف نمی‌شود؛ یک‌بار پرداخت می‌کنی و تا پایان اشتراک خیالت راحت است.\n\n"
                "<b>قدم ۱</b> — از منوی اصلی «💎 اشتراک ماهانه» را بزن.\n"
                "<b>قدم ۲</b> — یک پلن را انتخاب کن — مدت، تعداد اکانت و قیمت هر "
                "پلن نوشته شده است.\n"
                "<b>قدم ۳</b> — پرداخت:\n"
                "      • «💳 خرید با کیف پول» → درجا و بدون تأیید مدیر\n"
                "      • «✅ خرید» → کارت‌به‌کارت + ارسال <b>عکس رسید</b>\n"
                "      • «🎟 دارم کد تخفیف» → اگر کد تخفیف داری\n"
                "<b>قدم ۴</b> — بعد از تأیید مدیر، اشتراک فعال می‌شود و پیام می‌گیری.\n\n"
                f"{L}\n"
                "💡 اگر الان هم اشتراک داشته باشی، دوره‌ی جدید به باقی‌مانده‌اش "
                "اضافه می‌شود و از دست نمی‌رود.\n"
                "💤 تا پایان اشتراک، امتیازی مصرف نمی‌شود و سرویس به‌خاطر کمبود "
                "امتیاز قطع نمی‌شود.\n"
                "👥 با پلن‌های چند اکانته می‌توانی چند سلف با یک اشتراک داشته باشی.\n"
                "🔔 قبل از پایان دوره یادآوری می‌گیری — برای تمدید، دوباره پلن بخر.\n"
                "📋 سفارش‌هایت همیشه در «🧾 سفارش‌ها» هست.\n\n"
                "⚠️ رسید را فقط داخل همین ربات بفرست؛ به کسی خارج از ربات نده."
            )
        if key == "after_run":
            return (
                f"🚀 <b>سلف روی اکانتت فعال شد — حالا چه کنم؟</b>\n{L}\n"
                "<b>۱</b> — برو داخل تلگرامِ خودت به <b>Saved Messages</b> و بفرست:\n"
                "<code>.panel</code>\n"
                "پنل سلف همان‌جا باز می‌شود؛ همه‌ی تنظیمات از همین پنل است.\n\n"
                "<b>۲</b> — «⚙️ سرویس من» در همین ربات: وضعیتِ روشن/خاموش، "
                "اعتبار، و دکمه‌ی روشن/خاموش‌کردن سرویس.\n\n"
                "<b>۳</b> — اعتبار:\n"
                f"      • امتیاز: هر ساعتِ روشن‌بودن <b>{_fa_digits(per)}</b> امتیاز کم می‌شود "
                f"(حداقل <b>{_fa_digits(mn_pts)}</b> برای روشن‌کردن)\n"
                "      • اشتراک ماهانه: بدون مصرف امتیاز تا پایان دوره\n"
                "      قبل از تمام‌شدن اعتبار پیام یادآوری می‌گیری.\n\n"
                "<b>۴</b> — مشکلی پیش آمد؟ اول از «⚙️ سرویس من» یک‌بار خاموش/روشن کن؛ "
                "حل نشد، «🎧 پشتیبانی».\n\n"
                f"{L}\n"
                "⚠️ اکانتت را از دستگاه‌های دیگر خارج نکن و رمز دومرحله‌ای را عوض نکن؛ "
                "وگرنه سلف قطع می‌شود و باید دوباره راه‌اندازی کنی.\n"
                "⚠️ کد ورودی تلگرام را هیچ‌وقت به کسی نده."
            )
        return ""

    def tut_preset_label(self, key):
        d = dict(self.TUT_PRESETS).get(key)
        return f"{d['emoji']} {d['name']}" if d else key

    def tut_find_preset(self, key):
        """بخشی که از این پیش‌فرض ساخته شده (اگر هست)."""
        for s in self.tut_sections():
            if s.get("preset") == key:
                return s
        return None

    def tut_new_preset(self, key):
        """از یک متنِ آماده بخش می‌سازد؛ اگر قبلاً ساخته شده همان را برمی‌گرداند.

        خروجی: (section, created)
        """
        d = dict(self.TUT_PRESETS).get(key)
        if not d:
            return None, False
        old = self.tut_find_preset(key)
        if old:
            return old, False
        s = self.tut_new(d["name"], d["emoji"])
        # text خالی می‌ماند → همیشه متنِ آماده‌ی به‌روز (با اعداد فعلی تنظیمات)
        s = self.tut_update(s["id"], when=d["when"], btn_cmd=d["btn_cmd"],
                            btn_label=d["btn_label"], note=d["note"],
                            text="", preset=key)
        return s, True

    def tut_new_all_presets(self):
        """هر چهار متنِ آماده را یک‌جا می‌سازد (فقط آن‌هایی که هنوز نیستند)."""
        made = []
        for key, _ in self.TUT_PRESETS:
            s, created = self.tut_new_preset(key)
            if created:
                made.append(s)
        return made

    def tut_body_text(self, s):
        """متنِ بدنه‌ی بخش: متنِ ذخیره‌شده، یا (برای پیش‌فرض‌ها) متن آماده‌ی به‌روز."""
        t = (s.get("text") or "").strip()
        if t:
            return t
        if s.get("preset"):
            p = str(s["preset"])
            if p.startswith("hub:"):
                return self.hub_default_text(p[4:])
            return self.tut_preset_text(p)
        return ""

    def tut_btn_rows(self, s):
        """دکمه‌های شیشه‌ای پایانِ یک بخش (از روی btn_label/btn_cmd)."""
        cmd = (s.get("btn_cmd") or "").strip()
        if not cmd:
            return []
        label = (s.get("btn_label") or "").strip() or \
            dict(self.TUT_TARGETS).get(cmd, "ادامه")
        if cmd.startswith(("http://", "https://", "tg://")):
            try:
                from telethon import Button
                return [[Button.url(label, cmd)]]
            except Exception as e:
                print("tut url btn:", type(e).__name__, e)
                return []
        return [[B(label, cmd, "success")]]

    async def tut_send_section(self, uid, sid, force=False, header=False, bare=False,
                               extra=None):
        """یک بخش را برای کاربر می‌فرستد: محتوا + (در آخر) دکمه‌ی پایان.

        force=True یعنی حتی اگر قبلاً رفته، دوباره برود (مثلاً کاربر خودش
        تگ را زده). با once=False همیشه می‌رود.

        bare=True فقط برای دکمه‌های «📚 آموزش …» (tut:x:…) — تحویلِ تمیز:
        فقط محتوای ثبت‌شده‌ی مدیر + دکمه‌ی پایانِ همان کار؛ نه «متن پایان»
        (note)، نه تزریقِ متنِ آماده‌ی پیش‌فرض وقتی مدیر پیام/محتوا ثبت کرده.
        دکمه به آخرین پیامِ محتوا می‌چسبد؛ اگر آخرین پیام آلبوم بود، یک پیامِ
        بدون‌متن فقط با دکمه می‌رود. اگر محتوایی ثبت نشده باشد fallback:
        متن آماده‌ی پیش‌فرض + همان دکمه. مسیرهای خودکار و تگ‌ها (bare=False)
        با همان رفتار قبلی — از جمله متن پایان — دست‌نخورده می‌مانند.
        """
        s = self.tut_find(sid)
        if not s or not s["on"]:
            return False
        if s["once"] and not force and self.db.tut_done(uid, s["id"]):
            return False
        # extra: ردیف‌دکمه‌های اضافی (مثلاً «🗂 همه‌ی آموزش‌ها» آخرِ آموزشِ فهرست)
        buttons = self.tut_btn_rows(s) + [list(r) for r in (extra or [])]
        if bare and not buttons and s.get("preset") in dict(self.TUT_MENU_FOOT):
            # دکمه‌ی پایانِ همان کار هیچ‌وقت خالی نیست
            lbl, cmd = self.TUT_MENU_FOOT[s["preset"]]
            buttons = [[B(lbl, cmd, "success")]]
        if bare:
            # فقط محتوای ثبت‌شده‌ی مدیر: پیام‌های ثبت‌شده + متنِ ذخیره‌شده
            msgs = await self._tut_load(s["chat"], s["ids"])
            body = (s.get("text") or "").strip()
            if not msgs and not body:
                # fallback: متن آماده‌ی پیش‌فرض + همان دکمه (بدون متن پایان)
                body = self.tut_body_text(s)
                if not body:
                    return False
                await self.say(uid, body, buttons, key=f"tut:body:{s['id']}")
                self.db.tut_mark(uid, s["id"])
                self.db.log(uid, "tut_sec", f"#{s['id']} {s['name']}")
                return True
            ok = 0
            attached = False
            if msgs:
                ok, attached = await self._tut_copy(uid, msgs, s["chat"],
                                                    buttons if not body else None)
            if body:
                await self.say(uid, body, buttons, key=f"tut:body:{s['id']}")
                attached = bool(buttons)
            if buttons and not attached:
                # آخرین پیام آلبوم بوده (دکمه روی آلبوم نمی‌نشیند):
                # یک پیامِ بدون‌متن فقط با دکمه
                await self.say(uid, "\u2063", buttons, key=f"tut:btn:{s['id']}")
            if not ok and not body:
                return False
            self.db.tut_mark(uid, s["id"])
            self.db.log(uid, "tut_sec", f"#{s['id']} {s['name']}")
            return True
        show_hdr = bool(header or s.get("header"))
        if show_hdr:
            allsec = self.tut_sections(on_only=True)
            pos = next((i for i, x in enumerate(allsec) if x["id"] == s["id"]), 0) + 1
            await self.say(uid,
                f"🧩 <b>بخش {_fa_digits(pos)} از {_fa_digits(len(allsec))}"
                f" — {s['name']}</b>", None)
        msgs = await self._tut_load(s["chat"], s["ids"])
        body = self.tut_body_text(s)
        ok = 0
        attached = False
        # ترتیب: پیام‌های ثبت‌شده → متنِ بخش → متن پایان + دکمه.
        # اگر مدیر «متن پایان» نوشته، آن متن با دکمه می‌رود (پیام پایانی جدا)،
        # وگرنه دکمه روی آخرین پیامِ محتوا (یا روی متنِ بخش) می‌نشیند.
        attach = bool(buttons) and not s["note"]
        if msgs:
            ok, attached = await self._tut_copy(uid, msgs, s["chat"],
                                                buttons if (attach and not body) else None)
        if body:
            await self.say(uid, body, buttons if attach else None,
                           key=f"tut:body:{s['id']}")
            if attach:
                attached = True
        if buttons and (s["note"] or not attached):
            # key مخصوصِ همین بخش: متنِ پایانِ تکراریِ دو بخش با هم قاطی نشود
            await self.say(uid, s["note"] or self.TUT_FOOT_FALLBACK, buttons,
                           key=f"tut:{s['id']}")
        elif s["note"]:
            await self.say(uid, s["note"], None, key=f"tut:{s['id']}")
        if not msgs and not body and not buttons and not s["note"]:
            return False
        self.db.tut_mark(uid, s["id"])
        self.db.log(uid, "tut_sec", f"#{s['id']} {s['name']}")
        return True

    async def tut_fire(self, uid, when, force=False):
        """همه‌ی بخش‌های یک رویداد را به ترتیب می‌فرستد (با فاصله‌ی خودشان)."""
        n = 0
        for s in self.tut_sections(on_only=True):
            if s["preset"].startswith("hub:") or s["when"] != when:
                continue
            if s["delay"]:
                await asyncio.sleep(s["delay"])
            if await self.tut_send_section(uid, s["id"], force=force):
                n += 1
        # بعد از فعال‌سازی، تگِ همه‌ی بخش‌ها را هم یک‌جا می‌دهیم تا کاربر
        # هر آموزش را بعداً با یک دکمه بگیرد.
        if n and when == "after_run":
            await self.tut_send_menu(uid)
        return n

    def tut_pending_sections(self, uid, when, force=False):
        """بخش‌هایی که برای این کاربر در این رویداد باید بروند (بدون ارسال)."""
        out = []
        for s in self.tut_sections(on_only=True):
            if s["preset"].startswith("hub:") or s["when"] != when:
                continue
            if s["once"] and not force and self.db.tut_done(uid, s["id"]):
                continue
            out.append(s)
        return out

    def tut_schedule(self, uid, when, wait=0, force=False):
        """ارسال بخش‌های یک رویداد را در پس‌زمینه می‌اندازد (بدون بلوکه‌کردن).

        اگر بخشی برای این رویداد نباشد، هیچ تسکی ساخته نمی‌شود.
        """
        try:
            if not self.tut_pending_sections(uid, when, force):
                return False
        except Exception as e:
            print("tut_schedule:", type(e).__name__, e)
            return False

        async def _run():
            try:
                if wait and int(wait) > 0:
                    await asyncio.sleep(int(wait))
                await self.tut_fire(uid, when, force=force)
            except Exception as e:
                print("tut_run:", type(e).__name__, e)
        try:
            asyncio.create_task(_run())
            return True
        except RuntimeError:
            return False

    def tut_self_default_pending(self, uid):
        """متن آماده‌ی «بعد از فعال‌سازی» وقتی باید برود که بخشِ after_run نباشد.

        اگر مدیر بخشی با زمانِ «بعد از فعال‌سازی» ساخته باشد، همان بخش‌ها
        (tut_schedule) مسئول‌اند و متن پیش‌فرض کنار می‌رود؛ وگرنه خودِ سلف
        که فعال شد، آموزش خودکار می‌رود — یک‌بار برای هر کاربر.
        """
        for s in self.tut_sections():
            if s["when"] == "after_run":
                return False
        return not self.db.tut_done(uid, self.TUT_SELF_DEF_ID)

    async def tut_send_self_default(self, uid):
        """«بعد از فعال‌سازی»ِ پیش‌فرض را می‌فرستد و یک‌بار ثبت می‌کند."""
        lbl, cmd = self.TUT_MENU_FOOT["after_run"]
        ok = await self.say(uid, self.tut_preset_text("after_run"),
                            [[B(lbl, cmd, "success")], back_btn()],
                            key="tut:self_def")
        if ok:
            self.db.tut_mark(uid, self.TUT_SELF_DEF_ID)
            self.db.log(uid, "tut_sec", "default after_run")
        return ok

    def tut_schedule_self_default(self, uid, wait=0):
        """اگر بخشی برای after_run نیست، متن پیش‌فرض «بعد از فعال‌سازی» را می‌فرستد.

        ارسال خودکارِ آموزشِ سلف: به‌محض فعال‌شدن سلف، خودش می‌رود (بلاک نمی‌کند).
        """
        try:
            if not self.tut_self_default_pending(uid):
                return False
        except Exception as e:
            print("tut_self_def_chk:", type(e).__name__, e)
            return False

        async def _run():
            try:
                if wait and int(wait) > 0:
                    await asyncio.sleep(int(wait))
                await self.tut_send_self_default(uid)
            except Exception as e:
                print("tut_self_def:", type(e).__name__, e)
        try:
            asyncio.create_task(_run())
            return True
        except RuntimeError:
            return False

    async def tut_send_menu(self, uid):
        """تگِ همه‌ی بخش‌های فعال را به کاربر نشان می‌دهد."""
        secs = [s for s in self.tut_sections(on_only=True)
                if not s["preset"].startswith("hub:")]
        if not secs and not self.hub_on():
            return False
        kb = [[B(self.tut_sec_label(s), f"tut:s:{s['id']}", "success")]
              for s in secs]
        if self.hub_on():
            # دسترسی جداگانه به معرفی سرویس (نه فهرست آموزش‌ها)
            kb.append([B("🗂 توضیحات (فهرست)", "m:hub", "primary")])
        kb.append([B("🚀 راه‌اندازی سلف روی اکانتم", "s:setup", "primary")])
        kb.append(back_btn())
        return await self.say(uid,
            f"🧩 <b>بخش‌های آموزش</b>\n{self.LINE}\n"
            f"{_fa_digits(len(secs))} بخش آماده است — هر کدام را خواستی بزن:",
            kb)

    # ═══════════════════════════════════════════════
    #  🗂 توضیحات — فهرستِ تپ‌کردنیِ همه‌ی بخش‌ها
    #  مستقل از آموزش‌ها؛ فقط بخش‌های توضیحی با preset=hub: نمایش داده می‌شوند.
    # ═══════════════════════════════════════════════

    # ── توضیحاتِ پیش‌فرضِ فهرست: قابلیت‌های ربات ──
    # تا وقتی مدیر متنِ خودش را نگذاشته، همین‌ها برای مشتری می‌روند و
    # با «📥 ساختن بخش از پیش‌فرض‌ها» به بخشِ قابل‌ویرایش تبدیل می‌شوند.
    # (key, emoji, عنوان, مقصدِ دکمه‌ی پایان, برچسبِ دکمه)
    HUB_DEFAULTS = (
        ("start", "🤖", "سلف چیست؟",
         "s:setup", "🚀 راه‌اندازی سلف روی اکانتم"),
        ("phone", "📱", "چرا شماره می‌گیریم؟", "", ""),
        ("verify", "🔑", "چرا تأیید شماره لازم است؟", "", ""),
        ("svc", "⚙️", "سرویس من: روشن / خاموش",
         "m:svc", "⚙️ سرویس من"),
        ("trial", "🎁", "تست رایگان",
         "m:trial", "🎁 تست رایگان"),
        ("panel", "🕹", "قابلیت‌های سلف",
         "", ""),
        ("exchange", "🤝", "تبادل ممبر", "", ""),
        ("wallet", "💳", "کیف پول و شارژ",
         "m:wallet", "💳 کیف پول"),
        ("points", "🎯", "امتیاز چطور کار می‌کند",
         "m:packs", "🎯 خرید امتیاز"),
        ("sub", "💎", "اشتراک ماهانه",
         "m:plans", "💎 اشتراک ماهانه"),
        ("ref", "🎁", "زیرمجموعه و پاداش",
         "m:ref", "🎁 زیرمجموعه"),
        ("security", "🔐", "امنیت و لغو دسترسی", "", ""),
        ("support", "🎧", "پشتیبانی",
         "m:support", "🎧 پشتیبانی"),
    )

    def hub_on(self):
        return bool(self.cfg.get("hub_on", True))

    def hub_sections(self):
        """بخش‌هایی که در فهرست «🗂 توضیحات» دیده می‌شوند.

        سه نوع بخش داریم:
          • بخش‌های آموزشِ قدیمی (preset: wallet/points/sub/after_run) —
            این‌ها «آموزش»اند نه «توضیح»، در فهرست توضیحات نمی‌آیند.
          • بخش دست‌ساز مدیر (preset="") — در فهرست توضیحات می‌آید.
          • توضیحِ تبدیل‌شده (preset="hub:*") — در فهرست می‌آید.
        پرچم in_hub امکان حذف همان مورد از فهرست بدون پاک‌کردن بخش است."""
        return [s for s in self.tut_sections(on_only=True)
                if s.get("in_hub", True) and self._is_hub_section(s)]

    @staticmethod
    def _is_hub_section(section):
        """بخشِ متعلق به فهرست توضیحات است یا آموزشِ قدیمی؟"""
        preset = str(section.get("preset") or "")
        return preset == "" or preset.startswith("hub:")

    def hub_page_size(self):
        try:
            return min(20, max(2, int(self.cfg.get("hub_page_size", 8) or 8)))
        except Exception:
            return 8

    # ─────────── توضیحاتِ پیش‌فرض (قابلیت‌های ربات) ───────────
    def hub_defaults_on(self):
        return bool(self.cfg.get("hub_defaults", True))

    def hub_made_keys(self):
        """کلیدهای پیش‌فرضی که مدیر از قبل به بخش تبدیل کرده (تا دوباره نیایند)."""
        out = set()
        for s in self.tut_sections():
            p = str(s.get("preset") or "")
            if p.startswith("hub:"):
                out.add(p[4:])
        return out

    def hub_defaults_all(self):
        """پیش‌فرض‌هایی که هنوز به بخشِ قابل‌ویرایش تبدیل نشده‌اند."""
        done = self.hub_made_keys()
        return [d for d in self.HUB_DEFAULTS if d[0] not in done]

    def hub_default_items(self):
        """توضیحاتِ پیش‌فرضِ آماده‌ی نمایش در فهرست.

        قانون‌ها:
          • پیش‌فرضی که به بخشِ قابل‌ویرایش تبدیل شده (preset="hub:*")
            دیگر نمی‌آید — خودِ همان بخش جایش را می‌گیرد (بدون تکرار).
          • در بقیه‌ی حالت‌ها پیش‌فرض‌ها <b>همیشه</b> در فهرست می‌مانند،
            حتی وقتی مدیر بخشِ دست‌سازِ خودش را اضافه کرده؛ بخش‌های مدیر
            اولِ فهرست می‌آیند و توضیحاتِ آماده‌ی قابلیت‌ها (سلف چیست،
            تست رایگان، کیف پول، امتیاز، اشتراک، امنیت…) بعدشان.
            تنها راهِ برداشتنشان همان سوئیچِ «📦 توضیحات پیش‌فرض» در پنل است.

        چرا: قبلاً به‌محضِ اضافه‌شدنِ <b>یک</b> بخشِ دست‌ساز، همه‌ی توضیحاتِ
        آماده غیب می‌شدند و فهرستِ مشتری عملاً خالی می‌ماند (انگار همه‌ی
        قابلیت‌ها پریده‌اند). حذفِ خودکار بدونِ رضایتِ مدیر = از‌دست‌رفتنِ
        محتوا؛ پس حذف فقط دستی و با سوئیچِ خودش انجام می‌شود."""
        if not self.hub_defaults_on():
            return []
        return self.hub_defaults_all()

    def hub_default_row(self, item):
        return [B(f"{item[1]} {item[2]}", f"hub:d:{item[0]}", "success")]

    def hub_default_text(self, key):
        """متنِ توضیحِ پیش‌فرضِ یک قابلیت، با اعدادِ فعلیِ تنظیمات."""
        cfg = self.cfg
        L = self.LINE
        per = max(1, int(cfg.get("cost_per_hour", 1) or 1))
        mn = int(cfg.get("min_points", 20) or 0)
        start_fee = int(cfg.get("start_fee", 0) or 0)
        low = int(cfg.get("low_warn", 10) or 0)
        mins = max(1, int(cfg.get("trial_minutes", 30) or 30))
        r_self = int(cfg.get("referral_points_self", 1) or 0)
        r_no = int(cfg.get("referral_points", 2) or 0)
        pct = int(cfg.get("referral_percent", 0) or 0)

        if key == "start":
            return (
                f"🤖 <b>سلف چیست؟</b>\n{L}\n"
                "سلف برنامه‌ای است که با ورود به حساب تلگرام خودت، بعضی کارها را "
                "از طرف همان حساب و طبق تنظیماتت انجام می‌دهد؛ برخلاف ربات معمولی، "
                "فعالیتش با نام حساب تو انجام می‌شود.\n\n"
                "در این سرویس، سلف برای مدیریت تبادل ممبر، بررسی عضویت و تنظیم "
                "زمان فعالیت استفاده می‌شود. ربات مدیریت هم وضعیت سرویس و اعتبارت را نشان می‌دهد.\n\n"
                "ورود سلف یک نشست جدید برای حسابت ایجاد می‌کند؛ فقط اگر به سرویس اعتماد داری ادامه بده. "
                "خودکارسازی ممکن است باعث محدودیت حساب از طرف تلگرام شود."
            )
        if key == "phone":
            return (
                f"📱 <b>چرا شماره می‌گیریم؟</b>\n{L}\n"
                "تلگرام برای شناسایی حساب هنگام ورود، شماره تلفن آن حساب را لازم دارد. "
                "شماره را می‌گیریم تا درخواست ورود سلف برای حساب خودت ارسال شود؛ "
                "نام کاربری به‌تنهایی برای ورود کافی نیست.\n\n"
                "ارسال شماره به‌تنهایی به معنی ورود موفق نیست؛ تأیید ورود تلگرام هم لازم است. "
                "شماره تلفن اطلاعات شخصی است و نباید شماره شخص دیگری را ارسال کنی."
            )
        if key == "verify":
            return (
                f"🔑 <b>چرا تأیید شماره لازم است؟</b>\n{L}\n"
                "تلگرام با کد ورود بررسی می‌کند که درخواست‌کننده به حساب دسترسی دارد. "
                "این کد صرفاً تأیید یک فرم نیست: با تأیید آن، سلف می‌تواند یک نشست ورود "
                "برای حساب تو ایجاد کند و از طرف حسابت فعالیت کند.\n\n"
                "اگر تأیید دومرحله‌ای فعال باشد، تلگرام رمز آن را هم برای ورود لازم دارد. "
                "کد و رمز ورود حساس‌اند؛ آن‌ها را برای اشخاص یا پشتیبانی نفرست. "
                "فقط در صورتی ادامه بده که این دسترسی را آگاهانه به سرویس مورد اعتماد می‌دهی.\n\n"
                "خاموش‌کردن سرویس با لغو نشست فرق دارد؛ برای قطع دسترسی، نشست مربوط را "
                "از بخش دستگاه‌های تلگرام خاتمه بده."
            )
        if key == "svc":
            return (
                f"⚙️ <b>سرویس من — کنترل کامل دستِ خودت</b>\n{L}\n"
                "از «⚙️ سرویس من» در همین ربات:\n"
                "• وضعیت سلف را می‌بینی: 🟢 در حال کار / 🟡 متوقف\n"
                "• هر وقت خواستی روشن یا خاموشش می‌کنی\n"
                "• اعتبار و زمان باقی‌مانده را می‌بینی\n"
                "• اگر مشکلی پیش آمد، همان‌جا یک‌بار خاموش/روشن کافی است\n\n"
                f"{L}\n"
                f"🎯 امتیازی‌ها: هر ساعتِ روشن‌بودن <b>{_fa_digits(per)}</b> امتیاز کم "
                f"می‌شود و برای روشن‌کردن حداقل <b>{_fa_digits(mn)}</b> امتیاز لازم است"
                + (f" (هر بار روشن‌کردن {_fa_digits(start_fee)} امتیاز)"
                   if start_fee else "") + ".\n"
                f"🟠 زیر <b>{_fa_digits(low)}</b> امتیاز هشدار می‌گیری و صفر که شد "
                "سرویس خاموش می‌شود.\n"
                "💤 با اشتراک ماهانه، تا پایان دوره هیچ امتیازی مصرف نمی‌شود."
            )
        if key == "trial":
            return (
                f"🎁 <b>تست رایگان {trial_duration_label(mins)}</b>\n{L}\n"
                "بدون پرداخت، بدون کارت بانکی و بدون تعهد — کامل امتحان کن؛ "
                "راضی بودی ادامه بده، نبودی هیچ هزینه‌ای ندادی.\n\n"
                f"{L}\n"
                "⏱ تایمر از لحظه‌ای شروع می‌شود که سلف روی اکانتت بالا بیاید و "
                "چند دقیقه آخر هم خودِ ربات یادآوری می‌کند.\n"
                "🔁 تست رایگان برای هر نفر یک‌بار است؛ بعدش امتیاز یا اشتراک لازم است."
            )
        if key == "panel":
            return (
                f"🕹 <b>قابلیت‌های سلف</b>\n{L}\n"
                "سلف این امکانات را در اختیار تو می‌گذارد:\n"
                "• ⏰ فعالیت/استراحت و سقف ارسال در ساعت\n"
                "• 🤝 تبادل: روشن/خاموش، فاصله‌ها، جوین و لفت\n"
                "• 🎛 دو پروفایل مستقل: عادی و ویژه (VIP)\n"
                "• 📊 وضعیت زنده و گزارش کار\n\n"
                f"{L}\n"
                "این قابلیت‌ها از پنل سلف در پیام‌های ذخیره‌شده قابل تنظیم‌اند؛ "
                "کافی است در پیام‌های ذخیره‌شده فرمان <code>.panel</code> را بفرستی."
            )
        if key == "exchange":
            return (
                f"🤝 <b>تبادل ممبر — چطور کار می‌کند</b>\n{L}\n"
                "• طرف پیام می‌دهد «جوین شدم» → سلف <b>واقعاً</b> چک می‌کند عضو "
                "کانال تو شده یا نه.\n"
                "• اگر شده بود، سلف هم عضو کانال او می‌شود.\n"
                "• اگر بعداً از کانالت بیرون بیاید، سلف خودکار از کانال او لفت می‌دهد.\n"
                "• اگر ادعا کند ولی عضو نشده باشد، دو پیام «نیومدی» با فاصله‌ی "
                "تصادفی می‌فرستد و بعد لفت می‌دهد.\n\n"
                f"{L}\n"
                "🛡 بین درخواست‌ها فاصله‌ی امن (تصادفی) رعایت می‌شود تا اکانتت "
                "شبیه یک آدم رفتار کند — این فاصله‌ها را صفر نکن.\n"
                "رعایت فاصله‌ها خطر محدودیت را حذف نمی‌کند؛ قوانین و محدودیت‌های تلگرام همچنان برقرارند."
            )
        if key == "wallet":
            return (
                f"💳 <b>کیف پول و شارژ</b>\n{L}\n"
                "کیف پول، موجودیِ تومانیِ تو داخل ربات است؛ یک‌بار شارژ می‌کنی و "
                "بعد خریدهایت را بدون کارت‌به‌کارتِ دوباره انجام می‌دهی.\n\n"
                "شارژ کیف پول پس از بررسی و تأیید پرداخت توسط مدیر به موجودی اضافه می‌شود.\n\n"
                f"{L}\n"
                "💡 با «خرید با کیف پول» خریدها درجا و بدون تأیید انجام می‌شوند.\n"
                "📋 گردش تراکنش‌ها همیشه در «💳 کیف پول» هست.\n"
                "⚠️ رسید را فقط داخل همین ربات بفرست."
            )
        if key == "points":
            return (
                f"🎯 <b>امتیاز چطور کار می‌کند</b>\n{L}\n"
                "امتیاز، سوختِ سلف است:\n"
                f"• هر ساعتِ روشن‌بودن: <b>{_fa_digits(per)}</b> امتیاز\n"
                f"• برای روشن‌کردن: حداقل <b>{_fa_digits(mn)}</b> امتیاز\n"
                f"• زیر <b>{_fa_digits(low)}</b> امتیاز هشدار می‌گیری\n"
                "• امتیاز که صفر شود، سرویس خودکار خاموش می‌شود\n"
                "• خاموشش کنی، مصرف هم می‌ایستد — امتیازت نمی‌سوزد\n\n"
                f"{L}\n"
                "🛒 از «🎯 خرید امتیاز» می‌خری؛ مقدار دلخواه هم می‌توانی بدهی.\n"
                "🎁 از دوستانت دعوت کن (بخش «🎁 زیرمجموعه») و رایگان امتیاز بگیر.\n"
                "💎 اشتراک ماهانه داشته باشی، تا پایان دوره امتیاز مصرف نمی‌شود."
            )
        if key == "sub":
            return (
                f"💎 <b>اشتراک ماهانه</b>\n{L}\n"
                "با اشتراک، سلف تا پایان دوره روشن می‌ماند و <b>هیچ امتیازی</b> "
                "مصرف نمی‌شود — به‌خاطر کمبود امتیاز هم قطع نمی‌شود.\n\n"
                "• پلن را از «💎 اشتراک ماهانه» انتخاب کن؛\n"
                "• پرداخت کیف پول = درجا، کارت‌به‌کارت = با تأیید مدیر؛\n"
                "• با پلن‌های چند اکانته می‌توانی چند سلف داشته باشی؛\n"
                "• تمدید که کنی، روزهای جدید به باقی‌مانده اضافه می‌شود و از "
                "دست نمی‌رود؛\n"
                "• قبل از تمام‌شدن دوره یادآوری می‌گیری."
            )
        if key == "ref":
            base = (f"🎁 <b>زیرمجموعه و پاداش</b>\n{L}\n"
                    "لینک دعوتت را از «🎁 زیرمجموعه» بگیر و برای دوستانت بفرست "
                    "(یا با دستور <code>/ref</code>).\n\n")
            if r_self or r_no:
                base += ("با هر دعوتِ <b>معتبر</b> امتیاز می‌گیری:\n"
                         f"• سلف تو فعال باشد: <b>{_fa_digits(r_self)}</b> امتیاز\n"
                         f"• سلف تو فعال نباشد: <b>{_fa_digits(r_no)}</b> امتیاز\n\n")
            if pct:
                base += (f"💰 خریدهای زیرمجموعه‌ات هم <b>{_fa_digits(pct)}٪</b> به "
                         "کیف پولت برمی‌گرداند.\n\n")
            base += (f"{L}\n"
                     "✅ دعوت زمانی معتبر می‌شود که طرف شماره‌ی خودش را تأیید کند "
                     "(رایگان است و سلف لازم ندارد).\n"
                     "🚫 شماره‌ی تکراری پاداش نمی‌گیرد.")
            return base
        if key == "security":
            return (
                f"🔐 <b>امنیت و لغو دسترسی</b>\n{L}\n"
                "• کد ورودی تلگرام را فقط داخل همین ربات بفرست و به هیچ‌کس "
                "بیرون از ربات نده — هیچ پشتیبانی‌ای کد یا رمز نمی‌پرسد.\n"
                "• رمز دومرحله‌ای (اگر داشته باشی) ذخیره نمی‌شود؛ فقط همان "
                "لحظه‌ی ورود استفاده می‌شود.\n"
                "• کنترل کامل دست خودت است: هر وقت خواستی از «⚙️ سرویس من» "
                "خاموشش کن یا از تلگرام → Settings → Devices همان نشست را "
                "«پایان» بده؛ همان لحظه سلف قطع می‌شود.\n"
                "• در صورت مشاهدهٔ فعالیت مشکوک، نشست ناشناس را خاتمه بده و "
                "تنظیمات امنیتی حساب را بررسی کن.\n\n"
                f"{L}\n"
                "🗑 حذف کامل اطلاعات هم با یک تیکت «🎧 پشتیبانی» انجام می‌شود."
            )
        if key == "support":
            return (
                f"🎧 <b>پشتیبانی</b>\n{L}\n"
                "هر سؤالی داشتی یا جایی گیر کردی، از «🎧 پشتیبانی» تیکت بفرست — "
                "پیامت مستقیم به مدیر می‌رسد و همین‌جا جواب می‌گیری.\n\n"
                "⏱ پاسخ معمولاً سریع است؛ اگر طول کشید، تیکت دوباره بفرست.\n"
                "📌 برای پیگیری سریع‌تر، آیدی عددی‌ات را هم بنویس: دستور "
                "<code>/whoami</code>."
            )
        return ""

    def _hub_items(self):
        """(آیتم‌ها, سقف هر صفحه) برای فهرست توضیحات.

        اول بخش‌های خودِ مدیر (به همان ترتیبی که چیده)، بعد توضیحاتِ
        پیش‌فرضِ قابلیت‌ها — هر دو با هم صفحه‌بندی می‌شوند."""
        secs = self.hub_sections()
        defaults = self.hub_default_items()
        items = [("s", s) for s in secs] + [("d", d) for d in defaults]
        per = self.hub_page_size()
        # اگر بخش‌های متعلق به فهرست وجود دارند ولی الان همه in_hub=False
        # شده‌اند، پیش‌فرض‌ها جای خالی را یک‌جا (تک‌صفحه‌ای) پر می‌کنند تا
        # با سقف کوچک صفحه (مثلاً ۴) پخش نشوند. وقتی اصلاً هیچ بخشی ساخته
        # نشده، پیش‌فرض‌ها طبق سقف عادی صفحه‌بندی می‌شوند.
        hidden_sections = any(self._is_hub_section(s)
                              for s in self.tut_sections())
        if not secs and defaults and hidden_sections:
            per = max(per, len(items))
        return items, per

    def hub_pages(self):
        items, per = self._hub_items()
        return max(1, (len(items) + per - 1) // per)

    def hub_intro(self):
        t = str(self.cfg.get("hub_intro") or "").strip()
        if t:
            return t
        return ("🗂 <b>توضیحات جفج</b>\n" + self.LINE + "\n"
                "سلف چیست، چرا شماره و تأیید ورود لازم است و چه قابلیت‌هایی دارد؟\n"
                "برای آشنایی با سرویس، موضوع موردنظرت را انتخاب کن. "
                "مراحل راه‌اندازی در بخش جداگانهٔ «📚 آموزش فعال‌سازی» است.")

    def hub_view(self, page=0):
        """(متن, کیبورد) صفحه‌ی فهرست توضیحات. صفحه‌ی ۱ = ۰."""
        items, per = self._hub_items()
        pages = max(1, (len(items) + per - 1) // per)
        try:
            page = int(page or 0)
        except (TypeError, ValueError):
            page = 0
        page = max(0, min(page, pages - 1))
        shown = items[page * per:(page + 1) * per]

        txt = [self.hub_intro(), self.LINE]
        if pages > 1:
            txt.append(f"📄 صفحه‌ی {_fa_digits(page + 1)} از {_fa_digits(pages)}")

        kb = []
        # «آموزش فعال‌سازی کامل» فقط وقتی بخشی در فهرست هست و فقط در
        # صفحه‌ی اول می‌آید؛ در حالتِ فقط-پیش‌فرض این دکمه نشان داده
        # نمی‌شود (توضیحات از آموزش‌ها جداست).
        has_secs = any(kind == "s" for kind, _ in items)
        if page == 0 and has_secs:
            kb.append([B("📖 آموزش فعال‌سازی (کامل)", "m:tut", "primary")])
        for kind, item in shown:
            if kind == "s":
                kb.append([B(self.tut_sec_label(item), f"hub:s:{item['id']}",
                             "success")])
            else:
                kb.append(self.hub_default_row(item))

        nav = []
        if page > 0:
            nav.append(B("⬅️ قبلی", f"hub:p:{page - 1}", "primary"))
        if page < pages - 1:
            nav.append(B("➡️ بعدی", f"hub:p:{page + 1}", "primary"))
        if nav:
            kb.append(nav)

        if items:
            kb.append([B("📤 ارسال همه‌ی توضیحات", "hub:all", "primary")])
        else:
            txt.append("")
            txt.append("<i>هنوز توضیحی اضافه نشده.</i>")
        kb.append(back_btn("m:home"))
        return "\n".join(txt), kb

    async def send_hub(self, uid, page=0):
        txt, kb = self.hub_view(page)
        return await self.say(uid, txt, kb, key=f"hub:{page}")

    def hub_back_row(self):
        """دکمه‌ی بازگشت به فهرست، آخرِ هر آموزشِ فرستاده‌شده."""
        return [[B("🗂 همه‌ی توضیحات", "hub:list", "primary")]]

    async def hub_send_default(self, uid, key):
        """یک توضیحِ پیش‌فرض را با دکمه‌ی پایانش می‌فرستد."""
        item = next((d for d in self.hub_default_items() if d[0] == key), None)
        if not item:
            return False
        body = self.hub_default_text(key)
        if not body:
            return False
        rows = []
        if item[3]:
            rows.append([B(item[4] or "ادامه", item[3], "success")])
        rows += self.hub_back_row()
        await self.say(uid, body, rows, key=f"hub:d:{key}")
        self.db.log(uid, "hub_default", key)
        return True

    async def hub_make_sections(self):
        """توضیحاتِ پیش‌فرض را به بخشِ قابل‌ویرایش تبدیل می‌کند (یک‌بار برای هر کلید)."""
        made = []
        for key, emoji, name, cmd, lbl in self.hub_defaults_all():
            s = self.tut_new(name=name, emoji=emoji)
            if not s:
                continue
            self.tut_update(s["id"], preset=f"hub:{key}", when="manual",
                            btn_cmd=cmd, btn_label=lbl, in_hub=True)
            made.append(self.tut_find(s["id"]))
        return made

    async def hub_send_all(self, uid):
        """همه‌ی آموزش‌های فهرست را به ترتیب (با فاصله‌ی خودِ هر بخش) می‌فرستد."""
        n = 0
        for s in self.hub_sections():
            if s["delay"]:
                await asyncio.sleep(min(10, int(s["delay"])))
            if await self.tut_send_section(uid, s["id"], force=True,
                                           extra=self.hub_back_row()):
                n += 1
        for d in self.hub_default_items():
            if await self.hub_send_default(uid, d[0]):
                n += 1
        return n

    # ─────────── پنل مدیر: مدیریت بخش‌ها ───────────
    async def hub_admin(self, ev):
        """صفحه‌ی «🗂 توضیحات» در پنل مدیر — تنظیم فهرستِ مشتری."""
        # بخش‌های متعلق به فهرست توضیحات (دست‌ساز مدیر و پیش‌فرض‌های
        # تبدیل‌شده) قابل ✅/⬜ کردن‌اند؛ آموزش‌های قدیمی (wallet/…) چون
        # اصلاً به فهرست نمی‌آیند این‌جا هم کلید ندارند.
        secs = [s for s in self.tut_sections() if self._is_hub_section(s)]
        in_hub = self.hub_sections()
        txt = [f"🗂 <b>توضیحات (فهرست تپ‌کردنی)</b>", self.LINE,
               "مشتری دکمه‌ی «🗂 توضیحات» را می‌زند و این‌جا هر توضیح را "
               "با یک تپ می‌گیرد.",
               self.LINE,
               f"وضعیت دکمه در منوی مشتری: "
               f"<b>{'🟢 روشن' if self.hub_on() else '🔴 خاموش'}</b>",
               f"توضیحاتِ پیش‌فرض (قابلیت‌ها): "
               f"<b>{'🟢 روشن' if self.hub_defaults_on() else '🔴 خاموش'}</b> — "
               f"{_fa_digits(len(self.hub_defaults_all()))} موردِ آماده\n"
               f"در فهرست: <b>{_fa_digits(len(in_hub))}</b> مورد "
               f"(از {_fa_digits(len(secs))} بخش)   ·   "
               f"هر صفحه: {_fa_digits(self.hub_page_size())}",
               "",
               f"📝 متن بالای صفحه: "
               f"{'✅ ثبت‌شده' if str(self.cfg.get('hub_intro') or '').strip() else '— (پیش‌فرض)'}",
               self.LINE,
               "<i>هر بخش آموزشی با ✅ در فهرست مشتری دیده می‌شود؛ با ⬜ "
               "کردنش از فهرست حذف می‌شود بدون اینکه بخش یا محتوایش پاک شود.</i>",
               "",
               "<b>توضیحاتِ پیش‌فرض:</b> معرفی سلف، دلیل دریافت شماره و تأیید ورود، "
               "قابلیت‌ها و امنیت. این‌ها <b>همیشه</b> کنارِ بخش‌های خودت در فهرست "
               "می‌مانند (اضافه‌کردنِ بخش، پاکشان نمی‌کند)؛ فقط با سوئیچِ بالا "
               "خاموش می‌شوند. با «📥 تبدیل به بخش» "
               "همه‌شان بخشِ قابل‌ویرایش می‌شوند؛ بعد متن هرکدام را از صفحه‌ی "
               "همان بخش با «📝 متن بخش» به متنِ خودت عوض کن."]
        kb = [[B(("🔴 خاموش کردن" if self.hub_on() else "🟢 روشن کردن")
                 + " دکمه‌ی «🗂 توضیحات»", "a:hub_on",
                 "danger" if self.hub_on() else "success")],
              [B("👁 پیش‌نمایش فهرست", "a:hub_p", "primary"),
               B("📤 فرستادن همه", "a:hub_all", "success")],
              [B("📝 متن بالای صفحه", "a:hub_i", "primary"),
               B("📄 تعداد در هر صفحه", "a:hub_pg", "primary")],
              [B(("📦 توضیحات پیش‌فرض: 🟢 روشن" if self.hub_defaults_on()
                  else "📦 توضیحات پیش‌فرض: 🔴 خاموش"), "a:hub_def",
                 "success" if self.hub_defaults_on() else "danger")],
              [B("📥 تبدیل پیش‌فرض‌ها به بخش (قابل ویرایش)", "a:hub_mk",
                 "success")]]
        if not secs:
            kb.append([B("➕ ساختن بخش", "a:secs", "success")])
        for s in secs:
            mark = "✅" if s.get("in_hub", True) else "⬜"
            kb.append([B(f"{mark} {self.tut_sec_label(s)}"
                         + ("" if s["on"] else "  (🔴 خاموش)"),
                         f"a:hub_t:{s['id']}",
                         "success" if s.get("in_hub", True) else "primary")])
        kb.append([B("🧩 مدیریت بخش‌ها", "a:secs", "success")])
        kb.append(back_btn("a:home"))
        return await self.edit(ev, "\n".join(txt), kb)

    async def tut_admin_list(self, ev):
        """صفحه‌ی «🧩 بخش‌های آموزش» در پنل مدیر."""
        secs = self.tut_sections()
        txt = [f"🧩 <b>بخش‌های آموزش</b>", self.LINE,
               "هر بخش = یک تگ برای کاربر: محتوا + زمان ارسال + دکمه‌ی پایان.",
               self.LINE]
        kb = [[B("➕ بخش جدید", "a:sec_add", "success")]]
        if not secs:
            txt.append("<i>هنوز بخشی نساخته‌ای. با «➕ بخش جدید» شروع کن.</i>")
        for s in secs:
            n = len(s["ids"])
            parts = []
            if n:
                parts.append(f"{_fa_digits(n)} پیام")
            if self.tut_body_text(s):
                parts.append("📝 متن")
            txt.append(f"{'🟢' if s['on'] else '⚪'} {self.tut_sec_label(s)} — "
                       f"{' + '.join(parts) or 'بدون محتوا'} — "
                       f"{self.tut_when_label(s['when'])}"
                       + ("" if s.get("in_hub", True) else " — 🚫 در فهرست نیست"))
            kb.append([B(("🟢" if s["on"] else "⚪")
                         + ("" if s.get("in_hub", True) else " 🚫")
                         + " " + self.tut_sec_label(s),
                         f"a:sec:{s['id']}",
                         "success" if s["on"] else "primary")])
        missing = [k for k, _ in self.TUT_PRESETS if not self.tut_find_preset(k)]
        if missing:
            kb.append([B("📝 متن‌های آماده (کیف پول / امتیاز / اشتراک / بعد از فعال‌سازی)",
                         "a:sec_tpl", "success")])
        kb.append([B("⚙️ ارسال خودکار بعد از فعال‌سازی", "a:tut_auto", "primary")])
        kb.append([B("🕘 بازیابی بخش‌ها (اگر پریدند)", "a:secs_h", "primary")])
        kb.append([B("📚 آموزش فعال‌سازی (اصلی)", "a:tut", "success")])
        kb.append(back_btn("a:home"))
        return await self.edit(ev, "\n".join(txt), kb)

    async def tut_admin_one(self, ev, sid):
        """صفحه‌ی یک بخش."""
        s = self.tut_find(sid)
        if not s:
            return await self.edit(ev, "این بخش پیدا نشد.",
                                   [back_btn("a:secs")])
        n = len(s["ids"])
        btn = (f"<b>{s['btn_label'] or '—'}</b> → <code>{s['btn_cmd']}</code>"
               if s["btn_cmd"] else "ندارد")
        body = self.tut_body_text(s)
        warn = [] if (n or body) else [
            "", "⚠️ <i>محتوایی ثبت نشده — با «📤 ثبت محتوا» پیام بفرست یا با «📝 متن بخش» متن بنویس.</i>"]
        if body:
            body_l = ("📝 متن: " + ("متن آماده‌ی " + self.tut_preset_label(s["preset"])
                                  if s.get("preset") and not s.get("text") else
                                  f"{_fa_digits(len(body))} حرف") + "  ✅")
        else:
            body_l = "📝 متن: —"
        txt = (f"{self.tut_sec_label(s)}   (کد {_fa_digits(s['id'])})\n{self.LINE}\n"
               f"🎛 زمان ارسال: {self.tut_when_label(s['when'])}\n"
               f"⏱ فاصله: {_fa_digits(s['delay'])} ثانیه بعد از بخش قبلی\n"
               f"📦 محتوا: {_fa_digits(n)} پیام{'  ✅' if n else ''}\n"
               f"{body_l}\n"
               f"🔚 دکمه‌ی پایان: {btn}\n"
               f"📝 متن پایان: {s['note'] or '—'}\n"
               f"🔁 {'یک‌بار برای هر کاربر' if s['once'] else 'هر بار'}"
               f"   ·   🏷 سرتیتر: {'روشن' if s['header'] else 'خاموش'}\n"
               f"وضعیت: {'🟢 فعال' if s['on'] else '🔴 خاموش'}"
               f"   ·   🗂 در فهرست توضیحات: "
               f"{'✅' if s.get('in_hub', True) else '⬜'}"
               + "\n".join(warn))
        kb = []
        if n:
            # محتوای قبلی هست → دو راهِ جدا: «اضافه‌کردن به آخرِ آن» (ویدیوی
            # دوم پشت ویدیوی اول) یا «جایگزینی کل» (از صفر).
            kb.append([B("➕ افزودن به محتوا", f"a:sec_add:{sid}", "success")])
            kb.append([B("📤 ثبت / تغییر محتوا (جایگزینی)", f"a:sec_set:{sid}",
                         "primary")])
        else:
            kb.append([B("📤 ثبت محتوا", f"a:sec_set:{sid}", "success")])
        kb += [
            [B("📦 مدیریت محتوا", f"a:sec_items:{sid}", "primary"),
             B("🗑 پاک‌کردن همه", f"a:sec_clr:{sid}", "danger")],
            [B("👁 پیش‌نمایش", f"a:sec_vw:{sid}", "primary")],
            [B("📝 متن بخش", f"a:sec_txt:{sid}", "success")]
            + ([B("♻️ متن آماده", f"a:sec_tpl_rst:{sid}", "primary")]
               if s.get("preset") else []),
            [B("🎛 زمان ارسال", f"a:sec_when:{sid}", "primary"),
             B("⏱ فاصله (ثانیه)", f"a:sec_dly:{sid}", "primary")],
            [B("🔚 دکمه‌ی پایان بخش", f"a:sec_btn:{sid}", "success"),
             B("📝 متن پایان", f"a:sec_note:{sid}", "primary")],
            [B("🏷 نام بخش", f"a:sec_rn:{sid}", "primary"),
             B("🎨 ایموجی", f"a:sec_em:{sid}", "primary")],
            [B("⬆️ بالا", f"a:sec_up:{sid}"), B("⬇️ پایین", f"a:sec_dn:{sid}"),
             B(("🔁 یک‌بار" if s["once"] else "♾ همیشه"), f"a:sec_once:{sid}")],
            [B(("🏷 سرتیتر ✅" if s["header"] else "🏷 سرتیتر ⚪"), f"a:sec_hdr:{sid}"),
             B(("🔴 خاموش" if s["on"] else "🟢 روشن"), f"a:sec_on:{sid}")],
            [B(("🗂 در فهرست توضیحات ✅" if s.get("in_hub", True)
                else "🗂 در فهرست توضیحات ⬜"), f"a:sec_hub:{sid}")],
            [B("🗑 حذف بخش", f"a:sec_rm:{sid}", "danger")],
            back_btn("a:secs")]
        return await self.edit(ev, txt, kb)

    async def tut_admin_items(self, ev, sid):
        """«📦 مدیریت محتوا»ی یک بخش: فهرستِ دانه‌دانه‌ی پیام‌های ثبت‌شده.

        هر آیتم (ویدیو، متن، ویس، عکس، فایل، استیکر…) جدا با شماره دیده می‌شود
        تا مدیر بتواند <b>همان یکی</b> را پاک کند — مثلاً از دو ویدیوی ثبت‌شده
        فقط ویدیوی اول برود — یا با «🗑 پاک‌کردن همه» یک‌جا همه را بردارد.
        شماره‌ها دقیقاً همان ترتیبی است که برای کاربر ارسال می‌شود.
        """
        s = self.tut_find(sid)
        if not s:
            return await self.edit(ev, "این بخش پیدا نشد.",
                                   [back_btn("a:secs")])
        items = await self._tut_items(s["chat"], s["ids"])
        txt = [f"📦 <b>محتوای «{self.tut_sec_label(s)}»</b>", self.LINE]
        kb = []
        if not items:
            txt.append("⚪ پیامی ثبت نشده (یا پیام‌های منبع در تلگرام پاک شده‌اند).")
            txt.append("<i>با «➕ افزودن به محتوا» ویدیو/عکس/متن بفرست.</i>")
        else:
            txt.append(f"🔢 {_fa_digits(len(items))} پیام — به همان ترتیبی که "
                       "برای کاربر می‌رود:")
            txt.append("")
            for num, (i, m) in enumerate(items, start=1):
                kind = self._content_kind(m=m)
                snip = self._content_snippet(m)
                txt.append(f"{_fa_digits(num)}. {kind}" + (f" — {snip}" if snip else ""))
                # تلگرام متنِ دکمه را هم محدود می‌کند؛ برچسب کوتاه و بی‌خطر:
                lbl = f"🗑 {_fa_digits(num)}: {kind}" + (f" {snip}" if snip else "")
                kb.append([B(lbl[:60], f"a:sec_di:{sid}:{i}", "danger")])
            txt += ["", "<i>هر مورد را جدا می‌توانی پاک کنی؛ بقیه سر جایشان می‌مانند.</i>"]
        if items:
            kb.append([B("🗑 پاک‌کردن همه‌ی محتوا", f"a:sec_dall:{sid}", "danger")])
        kb.append([B("➕ افزودن به آخرِ محتوا", f"a:sec_add:{sid}", "success")])
        kb.append([B("📤 ثبت / تغییر محتوا (جایگزینی)", f"a:sec_set:{sid}", "primary"),
                   B("👁 پیش‌نمایش", f"a:sec_vw:{sid}", "primary")])
        kb.append([B("⬅️ بخش", f"a:sec:{sid}")])
        return await self.edit(ev, "\n".join(txt), kb)

    async def tut_admin_content(self, ev):
        """«📦 مدیریت محتوا»ی آموزش فعال‌سازی اصلی — مثل بخش‌ها، دانه‌دانه."""
        chat, ids = self.tut_src()
        items = await self._tut_items(chat, ids)
        txt = [f"📦 <b>محتوای «🎬 آموزش فعال‌سازی»</b>", self.LINE]
        kb = []
        if not items:
            txt.append("⚪ پیامی ثبت نشده (متن پیش‌فرض برای کاربر می‌رود).")
            txt.append("<i>با «➕ افزودن به محتوا» یا «📤 ثبت محتوا» پیام بفرست.</i>")
        else:
            txt.append(f"🔢 {_fa_digits(len(items))} پیام — به همان ترتیبی که "
                       "برای کاربر می‌رود:")
            txt.append("")
            for num, (i, m) in enumerate(items, start=1):
                kind = self._content_kind(m=m)
                snip = self._content_snippet(m)
                txt.append(f"{_fa_digits(num)}. {kind}" + (f" — {snip}" if snip else ""))
                # تلگرام متنِ دکمه را هم محدود می‌کند؛ برچسب کوتاه و بی‌خطر:
                lbl = f"🗑 {_fa_digits(num)}: {kind}" + (f" {snip}" if snip else "")
                kb.append([B(lbl[:60], f"a:tut_di:{i}", "danger")])
            txt += ["", "<i>هر مورد را جدا می‌توانی پاک کنی؛ بقیه سر جایشان می‌مانند.</i>"]
        if items:
            kb.append([B("🗑 پاک‌کردن همه‌ی محتوا", "a:tut_dall", "danger")])
        kb.append([B("➕ افزودن به آخرِ محتوا", "a:tut_add", "success")])
        kb.append([B("📤 ثبت / تغییر محتوا (جایگزینی)", "a:tut_set", "primary"),
                   B("👁 پیش‌نمایش", "a:tut_view", "primary")])
        kb.append([B("⬅️ بازگشت", "a:tut")])
        return await self.edit(ev, "\n".join(txt), kb)

    async def version_status(self, ev):
        """«🧬 نسخه‌ی کد» — کدام کد <b>الان</b> روی هاست اجرا می‌شود.

        تنها سؤالی که بعد از هر مرج می‌ماند «رسید یا نه؟» است. همین‌جا
        بیلد/کامیت/اثرانگشتِ کد، مسیرِ فایلِ در حالِ اجرا، آپ‌تایم و خلاصه‌ی
        وضعیتِ بازیابیِ بخش‌ها یک‌جا می‌آید تا بدونِ بازکردنِ داشبورد و لاگ
        معلوم شود دیپلوی نشسته یا نه.
        """
        fresh = os.path.join(image_dir(), "manager_82.py")
        lines = [f"🧬 <b>نسخه‌ی در حالِ اجرا</b>", self.LINE,
                 f"🏷 بیلد: <code>{BUILD_VERSION}</code>",
                 f"🔖 کامیت: <code>{GIT_COMMIT}</code>",
                 f"🧬 اثرانگشتِ کد: <code>{CODE_ID}</code>",
                 f"⏱ آپ‌تایم: {uptime_text()}",
                 f"📄 فایل: <code>{self._esc(MANAGER_PATH)}</code>",
                 f"🖼 نسخه‌ی ایمیج: <code>{self._esc(fresh)}</code>"]
        same = os.path.abspath(MANAGER_PATH) == os.path.abspath(fresh)
        if same:
            lines.append("✅ همین فایلِ ایمیج اجرا می‌شود (دیپلوی نشسته).")
        elif CODE_IS_STALE:
            lines.append("⚠️ <b>کد از ایمیج اجرا نمی‌شود</b> — دیپلویِ تازه "
                         "بی‌اثر می‌ماند. مسیرِ دیسک باید <code>/data</code> "
                         "باشد، نه <code>/app</code> یا <code>/opt/jafj</code>.")
        lines += [self.LINE,
                  "🌐 همین اطلاعات در مرورگر: "
                  "<code>https://YOUR-SERVICE.onrender.com/version</code>",
                  "🔺 اگر کامیت/اثرانگشت قدیمی است: داشبورد Render → "
                  "<b>Manual Deploy → Deploy latest commit</b>."]
        try:
            lost = cfg_lost_sections(extra=True)
            poor = cfg_poor_sections(extra=True)
            if lost:
                lines.append(f"🧩 {_fa_digits(len(lost[2]))} بخشِ گم‌شده در "
                             "تاریخچه/پشتیبان پیدا شد.")
            if poor:
                lines.append(f"📚 محتوای {_fa_digits(len(poor))} بخش خالی شده.")
            if not lost and not poor:
                lines.append("✅ بخشِ گم‌شده یا خالی‌شده‌ای دیده نمی‌شود.")
        except Exception:
            pass
        kb = [[B("🕘 بازیابی بخش‌ها", "a:secs_h", "primary")],
              [B("🔄 تازه‌سازی", "a:ver")],
              back_btn("a:home")]
        return await self.edit(ev, "\n".join(lines), kb)

    async def tut_admin_history(self, ev):
        """«🕘 بازیابی بخش‌ها» — نسخه‌های تاریخچه‌ی manager_config.json.

        اگر بخش‌های آموزش (ویدیو/متنِ ثبت‌شده‌یشان) پریده باشند — معمولاً
        چون نسخه‌ی قدیمیِ کانفیگ از پشتیبان/سینکِ گیت‌هاب برگشته — از این‌جا
        با یک دکمه برمی‌گردند: «🧩 برگرداندن بخش‌ها» فقط بخش‌های گم‌شده را
        اضافه می‌کند (بخش‌های تازه‌ی مدیر له نمی‌شوند)، «📥 کل تنظیمات»
        همان نسخه را کامل می‌نشاند.
        """
        rows = cfg_history_list()
        try:
            lost_map = cfg_lost_section_map()
        except Exception:
            lost_map = {}
        secs = self.tut_sections()
        txt = [f"🕘 <b>بازیابی بخش‌های آموزش</b>", self.LINE,
               f"📦 الان: {_fa_digits(len(secs))} بخش"
               f" · {_fa_digits(sum(len(s['ids']) for s in secs))} پیامِ محتوا",
               f"🗂 {CFG_HISTORY_DIR} — {_fa_digits(len(rows))} نسخه"]
        if lost_map:
            txt += ["", f"⚠️ <b>{_fa_digits(len(lost_map))} بخشِ گم‌شده "
                    "در تاریخچه پیدا شد</b> — در کانفیگِ فعلی نیست:", ""]
            for sid in sorted(lost_map):
                sec, fname = lost_map[sid]
                try:
                    n = len(sec.get("ids") or [])
                except Exception:
                    n = 0
                txt.append(f"• {str(sec.get('emoji') or '▫️')} "
                           f"{self._esc(str(sec.get('name') or '')[:60])} "
                           f"(کد {_fa_digits(sid)} · {_fa_digits(n)} پیام"
                           f" · از <code>{fname}</code>)")
            txt += ["", "<i>«🧩 برگرداندنِ همه» همین‌ها را برمی‌گرداند؛ "
                    "بخش‌های تازه‌ات سر جایشان می‌مانند. از هر نسخه هم "
                    "می‌توانی جدا انتخاب کنی.</i>"]
        else:
            txt += ["", "✅ بخشِ گم‌شده‌ای پیدا نشد."]
        try:
            poor = cfg_poor_sections()
        except Exception:
            poor = []
        if poor:
            tot = sum(len(m) for _s, _n, m, _h in poor)
            txt += ["", f"🧩 <b>{_fa_digits(len(poor))} بخش هست ولی محتوایش "
                    f"خالی شده</b> ({_fa_digits(tot)} مورد کم دارد):", ""]
            for sid, nm, miss, _hist in poor[:10]:
                txt.append(f"• {self._esc(nm[:60])} — "
                           + "، ".join(lbl for _k, lbl in miss))
            txt += ["", "<i>«📚 برگرداندنِ محتوا» فقط جاهای خالی را از "
                    "پُرترین نسخه‌ی تاریخچه پُر می‌کند؛ آنچه الان داری (متنِ "
                    "تازه‌تر/پیام‌های بیشتر) دست نمی‌خورد و پیامِ تکراری هم "
                    "اضافه نمی‌شود.</i>"]
        kb = []
        if lost_map:
            kb.append([B(f"🧩 برگرداندنِ هر {_fa_digits(len(lost_map))} بخشِ "
                         "گم‌شده", "a:secs_h_all", "success")])
        if poor:
            kb.append([B(f"📚 برگرداندنِ محتوای {_fa_digits(len(poor))} بخش",
                         "a:secs_h_c", "success")])
        shown = 0
        for name, d, mt in rows:
            if shown >= 8:
                break
            cs = _cfg_secs(d)
            try:
                tut = len([int(x) for x in (d.get("tut_ids") or [])])
            except Exception:
                tut = 0
            when = local_dt(mt).strftime("%m-%d %H:%M")
            txt.append(f"🕘 <code>{name}</code> — "
                       f"{_fa_digits(len(cs))} بخش / "
                       f"{_fa_digits(sum(x['n'] for x in cs))} پیام / "
                       f"آموزشِ اصلی {_fa_digits(tut)} پیام")
            kb.append([B(f"🧩 بخش‌ها ← {when}", f"a:secs_h_rs:{name}", "success"),
                       B(f"📥 کل تنظیمات ← {when}", f"a:secs_h_rf:{name}",
                         "primary")])
            shown += 1
        for sid, nm, _miss, _h in poor[:3]:
            kb.append([B(f"📚 محتوای {self._esc(nm[:24])}", f"a:secs_h_c:{sid}")])
        # منبعِ دوم: فایلِ پشتیبانِ خودِ ربات. هر وقت چیزی دارد که در
        # تاریخچه نیست دکمه‌اش می‌آید — هم برای کسی که تاریخچه‌اش خالی است
        # (دیپلویِ تازه) هم وقتی پشتیبانِ دیروز بخشی دارد که هفته‌ی پیش
        # پریده و از تاریخچه چرخش خورده.
        zip_src = None
        zip_extra = 0
        try:
            got = cfg_from_backup_zip()
            if got:
                xlost = cfg_lost_section_map(extra=True)
                xpoor = cfg_poor_sections(extra=True)
                zip_extra = (len(xlost) - len(lost_map)
                             + len(xpoor) - len(poor))
                if zip_extra > 0:
                    zip_src = got[1]
        except Exception:
            zip_src = None
        if zip_src:
            txt += ["", f"📦 در پشتیبانِ خودِ ربات "
                    f"(<code>{self._esc(os.path.basename(zip_src))}</code>) هم "
                    f"{_fa_digits(max(0, zip_extra))} مورد هست که در تاریخچه "
                    "پیدا نشد — دکمه‌ی پایین همان‌ها را برمی‌گرداند (بخشِ "
                    "گم‌شده + محتوای خالی‌شده، با ترجیحِ پُرترین نسخه)."]
            kb.append([B("📦 بازیابی از فایلِ پشتیبانِ ربات", "a:secs_h_zip",
                         "primary")])
        if not rows:
            txt.append("")
            txt.append("<i>هنوز نسخه‌ای در تاریخچه نیست؛ تاریخچه از اولین "
                       "تغییرِ بخش‌ها به بعد خودکار ساخته می‌شود. اگر فایلِ "
                       "پشتیبانِ ربات را داری، دکمه‌ی «📦 بازیابی از فایلِ "
                       "پشتیبانِ ربات» همان را می‌خواند.</i>")
        kb.append([B("⬅️ بازگشت", "a:secs")])
        return await self.edit(ev, "\n".join(txt), kb)

    async def tut_admin_when(self, ev, sid):
        """انتخاب زمان ارسال بخش."""
        s = self.tut_find(sid)
        if not s:
            return await self.edit(ev, "این بخش پیدا نشد.", [back_btn("a:secs")])
        kb = [[B(("✅ " if s["when"] == w else "") + lbl, f"a:sec_w:{sid}:{w}",
                 "success" if s["when"] == w else "primary")]
              for w, lbl in self.TUT_WHENS]
        kb.append([B("⬅️ بخش", f"a:sec:{sid}")])
        return await self.edit(ev,
            f"🎛 <b>زمان ارسال — {s['name']}</b>\n{self.LINE}\n"
            "• خودکار: به‌محض وقوع آن رویداد برای کاربر می‌رود.\n"
            "• فقط با دکمه: فقط وقتی خودِ کاربر تگِ بخش را بزند.", kb)

    async def tut_admin_btn(self, ev, sid):
        """انتخاب دکمه‌ی پایان بخش (مثلاً «💳 شارژ کیف پول»)."""
        s = self.tut_find(sid)
        if not s:
            return await self.edit(ev, "این بخش پیدا نشد.", [back_btn("a:secs")])
        kb = [[B(("✅ " if s["btn_cmd"] == cmd else "") + lbl,
                 f"a:sec_b:{sid}:{cmd}", "success")]
              for cmd, lbl in self.TUT_TARGETS]
        kb.append([B("🔗 دکمه‌ی لینک (URL)", f"a:sec_burl:{sid}", "primary")])
        if s["btn_cmd"]:
            kb.append([B("🗑 حذف دکمه", f"a:sec_bdel:{sid}", "danger")])
        kb.append([B("✏️ متن دکمه", f"a:sec_bl:{sid}", "primary")])
        kb.append([B("⬅️ بخش", f"a:sec:{sid}")])
        return await self.edit(ev,
            f"🔚 <b>دکمه‌ی پایان بخش — {s['name']}</b>\n{self.LINE}\n"
            f"دکمه‌ی فعلی: "
            + (f"<b>{s['btn_label']}</b> → <code>{s['btn_cmd']}</code>"
               if s["btn_cmd"] else "ندارد") + "\n\n"
            "این دکمه <b>آخرِ</b> محتوای بخش می‌آید — مثلاً آخرِ آموزشِ کیف "
            "پول، دکمه‌ی «💳 شارژ کیف پول»؛ آخرِ آموزشِ اشتراک، دکمه‌ی "
            "«💎 اشتراک ماهانه».", kb)

    async def admin_users_page(self, ev, page=0):
        rows = self.db.all()
        per = 6
        page = max(0, int(page))
        chunk = rows[page * per:(page + 1) * per]
        if not rows:
            return await self.edit(ev, "مشتری‌ای نیست.",
                                   [[B("🗑 پاک کردن با آیدی", "a:uwipe", "danger")],
                                    back_btn("a:home")])
        txt = [f"👥 <b>مشتری‌ها</b>  ({_fa_digits(len(rows))})", self.LINE]
        kb = [[B("🔍 جستجوی کاربر", "a:ufind", "primary"),
               B("🗑 پاک کردن اطلاعات کاربر", "a:uwipe", "danger")]]
        for c in chunk:
            live = "🟢" if self.sup.is_running(c["uid"]) else "⚪"
            st = {"active": "✅", "banned": "⛔", "expired": "🔴",
                  "new": "🆕"}.get(c["status"], "•")
            txt.append(f"{live}{st} <code>{c['uid']}</code> {c['name'] or '—'}")
            kb.append([B(f"{st} {c['name'] or c['uid']}", f"au:{c['uid']}",
                         "danger" if c["status"] == "banned" else "primary")])
        nav = []
        if page > 0:
            nav.append(B("◀️", f"a:ulist:{page - 1}"))
        if (page + 1) * per < len(rows):
            nav.append(B("▶️", f"a:ulist:{page + 1}"))
        if nav:
            kb.append(nav)
        kb.append(back_btn("a:home"))
        return await self.edit(ev, "\n".join(txt), kb)

    async def on_callback(self, ev):
        uid = ev.sender_id
        data = ev.data.decode("utf-8", "ignore")
        sh = self.shop
        adm = self.is_admin(uid)

        async def ans(t=""):
            try:
                await ev.answer(t)
            except Exception:
                pass

        # ── ضد تکرار: جلوی پردازش همزمان callback مشابه ──
        cb_key = f"{uid}:{data}"
        now_cb = time.time()
        if not hasattr(self, "_cb_dedup"):
            self._cb_dedup = {}
        last_cb = self._cb_dedup.get(cb_key, 0)
        if now_cb - last_cb < 2:
            return await ans()
        self._cb_dedup[cb_key] = now_cb
        # پاک‌کردن ورودی‌های قدیمی
        if len(self._cb_dedup) > 500:
            cutoff = now_cb - 10
            self._cb_dedup = {k: v for k, v in self._cb_dedup.items() if v > cutoff}

        # دکمه‌های منو بعد از ری‌استارت هم معتبر بمانند.
        # رفتن به هر صفحه‌ی دیگر، مرحله‌ی نیمه‌کاره را پاک می‌کند
        st_now = self.fsm.get(uid)
        phone_keyboard_active = bool(st_now and st_now.get("step") in ("phone", "verify_phone", "verify_referral"))
        if st_now and st_now.get("step") in ("topup", "custom_pts", "disc",
                                             "pdisc", "ticket", "deny",
                                             "verify_phone", "verify_referral", "bcast", "disc_new",
                                             "price_plan", "price_pack",
                                             "gp_n", "say_u", "card_set", "welcome_set",
                                             "sample_set", "trial_min",
                                             "ok_days", "acct_n", "fjoin_add", "tut_set",
                                             "sec_set", "sec_name", "sec_emoji",
                                             "sec_delay", "sec_note", "sec_btn_url",
                                             "sec_btn_label", "sec_text", "tut_wait",
                                             "rt_set",
                                             "cm_add", "cm_edit", "cm_intro",
                                             "hub_intro", "rules_set", "rules_btn_set",
                                             "ufind_q", "uwipe_pick"):
            # a:tut_add / a:sec_add / a:sec_set: خودشان حالتِ ثبت محتوا را
            # (از نو) باز می‌کنند؛ اگر اینجا پاکشان کنیم، سوییچ بین
            # «➕ افزودن» و «📤 جایگزینی» وسطِ کار حالت را از بین می‌برد.
            keep = data in ("wq:0", "kc:x", "a:tut_done", "a:tut_add") \
                or data.startswith(("a:sec_done", "a:sec_add:", "a:sec_set:")) \
                or data == "a:sample_done" or (
                st_now.get("step") in ("verify_phone", "verify_referral") and data.startswith(("ko:", "o:", "wq:", "kc:", "kp:")))
            if st_now.get("step") in ("verify_phone", "verify_referral") and data not in ("m:home",):
                keep = True
            if not keep:
                self.fsm.pop(uid, None)

        if data == "fj:ok":
            self._join_ok.pop(uid, None)
            missing = await self.missing_joins(uid)
            if missing:
                await ans("هنوز عضو نیستی")
                return await self.edit(ev, self.join_gate_text(missing),
                                       self.join_gate_kb(missing))
            await ans("عضویت تأیید شد ✅")
            if await self.enforce_rules(uid, ev=ev, chat=ev.chat_id):
                return
            return await self.edit(ev, self.home_text(uid),
                                   main_menu(adm, self.cfg["shop_on"], self.cfg["points_on"],
                                   bool((self.db.get(uid) or {}).get("session")),
                                   self.sup.is_running(uid),
                                   self.trial_available(uid),
                                   trial_label=self.trial_label(),
                                   has_cmds=self.has_cmds(),
                                   has_hub=self.hub_on()))

        if data == "rules:accept":
            self.accept_rules(uid)
            self.db.log(uid, "rules_accept", "پذیرش قوانین")
            await ans("قوانین پذیرفته شد ✅")
            return await self.edit(ev, self.home_text(uid),
                                   main_menu(adm, self.cfg["shop_on"], self.cfg["points_on"],
                                   bool((self.db.get(uid) or {}).get("session")),
                                   self.sup.is_running(uid),
                                   self.trial_available(uid),
                                   trial_label=self.trial_label(),
                                   has_cmds=self.has_cmds(),
                                   has_hub=self.hub_on()))

        if not adm and not data.startswith("a:") and data != "m:home":
            if await self.enforce_join(uid, ev=ev, chat=ev.chat_id):
                await ans("اول عضو شو")
                return
        if not adm and not data.startswith("a:") and data not in ("rules:accept",):
            if await self.enforce_rules(uid, ev=ev, chat=ev.chat_id):
                await ans("اول قوانین را تأیید کن")
                return

        # ---------- منوی اصلی ----------
        if data == "m:home":
            await ans()
            if phone_keyboard_active:
                await self.hide_reply_keyboard(uid)
            return await self.edit(ev, self.home_text(uid),
                                   main_menu(adm, self.cfg["shop_on"], self.cfg["points_on"],
                                   bool((self.db.get(uid) or {}).get("session")),
                                   self.sup.is_running(uid),
                                   self.trial_available(uid),
                                   trial_label=self.trial_label(),
                                   has_cmds=self.has_cmds(),
                                   has_hub=self.hub_on()))

        if data == "m:trial":
            await ans()
            return await self.start_trial(uid, ev.chat_id, ev)

        if data == "r:verify":
            await ans()
            return await self.require_phone_for_referral(uid, ev.chat_id, ev)

        if data == "m:help":
            await ans()
            return await self.edit(ev, self.cfg.get("help_text") or USER_HELP, [back_btn()])

        if data == "m:samples":
            await ans("در حال ارسال…")
            return await self.send_samples(uid)

        if data == "m:rules":
            await ans()
            return await self.edit(ev, self.rules_view_text(), [back_btn("m:home")])

        if data == "m:tut":
            await ans("در حال ارسال…")
            return await self.send_tutorial(uid)

        # 🗂 توضیحات — فهرستِ تپ‌کردنیِ همه‌ی توضیحات
        if data == "m:hub":
            await ans("در حال ارسال…")
            return await self.send_hub(uid)

        if data.startswith("hub:p:"):
            # ورق‌زدن فهرست: همان پیام ویرایش می‌شود (چت مشتری شلوغ نمی‌شود)
            try:
                pg = int(digits(data.split(":")[-1]) or 0)
            except Exception:
                pg = 0
            txt, kb = self.hub_view(pg)
            await ans()
            return await self.edit(ev, txt, kb)

        if data == "hub:list":
            await ans("در حال ارسال…")
            return await self.send_hub(uid)

        if data == "hub:all":
            await ans("در حال ارسال همه…")
            return await self.hub_send_all(uid)

        # تپِ یک توضیحِ پیش‌فرض: متنِ توضیح + دکمه‌ی همان کار + بازگشت به فهرست
        if data.startswith("hub:d:"):
            key = data.split(":", 2)[-1]
            if not self.hub_defaults_on():
                await ans("فعلاً موجود نیست")
                return await self.edit(ev, "این توضیح فعلاً موجود نیست.",
                                       [back_btn("m:hub")])
            await ans("در حال ارسال…")
            ok = await self.hub_send_default(uid, key)
            if not ok:
                return await self.edit(ev, "این توضیح فعلاً موجود نیست.",
                                       [back_btn("m:hub")])
            return

        # تپِ یک آموزش در فهرست: فقط همان آموزش می‌رود + دکمه‌ی بازگشت به فهرست
        if data.startswith("hub:s:"):
            sid = int(digits(data.split(":")[-1]) or 0)
            sec = self.tut_find(sid)
            if not sec or sec not in self.hub_sections():
                await ans("این مورد فعلاً موجود نیست")
                return await self.edit(ev, "این مورد فعلاً موجود نیست.",
                                       [back_btn("m:hub")])
            await ans("در حال ارسال…")
            ok = await self.tut_send_section(uid, sid, force=True,
                                             extra=self.hub_back_row())
            if not ok:
                return await self.edit(ev,
                    "⚠️ محتوای این مورد ثبت نشده.\\n"
                    "اگر تازه اضافه شده، کمی بعد دوباره امتحان کن.",
                    [back_btn("m:hub")])
            return

        # 📋 دستورات آماده — راهنمای مرحله‌به‌مرحله‌ی فعال‌سازی سلف
        if data == "m:cmds":
            if not self.has_cmds():
                await ans("فعلاً دستوری ثبت نشده")
                return await self.edit(ev, "این بخش فعلاً خالی است.",
                                       [back_btn("m:home")])
            await ans("در حال ارسال…")
            await self.send_cmds(uid)
            return

        # تگِ یک بخش آموزش: کاربر دکمه را می‌زند → همان بخش برایش می‌رود
        if data.startswith("tut:s:"):
            sid = int(digits(data.split(":")[-1]) or 0)
            sec = self.tut_find(sid)
            if not sec or not sec["on"]:
                await ans("این بخش فعلاً موجود نیست")
                return await self.edit(ev, "این بخش فعلاً موجود نیست.",
                                       [back_btn("m:tut")])
            await ans("در حال ارسال…")
            ok = await self.tut_send_section(uid, sid, force=True)
            if not ok:
                await self.edit(ev,
                    "⚠️ محتوای این بخش ثبت نشده.\n"
                    "اگر تازه اضافه شده، کمی بعد دوباره امتحان کن.",
                    [back_btn("m:tut")])
            return

        # دکمه‌ی «📚 آموزش …» آخرِ منوهای کیف پول / خرید امتیاز / اشتراک ماهانه:
        # زدن دکمه = ارسال خودکارِ آموزشِ همان کار (تنظیم‌شدنی از پنلِ مدیر)
        if data.startswith("tut:x:"):
            key = data.split(":")[-1]
            if key not in self.TUT_MENU_KEYS:
                return await ans()
            await ans("در حال ارسال…")
            return await self.send_menu_tutorial(uid, key)

        if data == "m:status":
            await ans()
            c = self.db.get(uid)
            live = self.sup.is_running(uid)
            st = self.sup.read_status(uid)
            if not c:
                return await self.edit(ev, "اول /start را بزن.", [back_btn()])
            t = [f"📊 <b>وضعیت</b>", self.LINE,
                 f"👤  اکانت       {c['name'] or '—'}",
                 f"📡  سرویس      {self.client_state(c)}"]
            if self.has_sub(uid):
                t.append(f"⏳  اعتبار      {human_left(c['expires_at'])}")
            if self.shop and self.cfg["points_on"]:
                extra = "  ·  اشتراک فعال، بدون مصرف" if self.has_sub(uid) else ""
                t.append(f"🎯  امتیاز      {_fa_digits(self.shop.p_balance(uid))}"
                         f"  ·  ≈{_fa_digits(self.hours_left(uid))} ساعت{extra}")
            t.append(f"🔄  ری‌استارت   {_fa_digits(c['restarts'] or 0)}")
            if st and st.get("age", 999) < 300:
                q = st.get("queue", {})
                ex = st.get("exchange", {})
                t += [self.LINE, "<b>گزارش زنده سلف</b>",
                      f"⏱  آپ‌تایم      {human_left(now() + st.get('uptime', 0))}",
                      f"📮  در صف       {_fa_digits(q.get('pending', 0))}"
                      + (f" (📦 {_fa_digits(q.get('held', 0))} معلق)"
                         if q.get("held") else ""),
                      f"📤  24 ساعت     {_fa_digits(st.get('sent_24h', 0))} ارسال",
                      f"✅  کل ارسال     {_fa_digits(q.get('sent', 0))}"]
                if ex.get("on"):
                    t.append(f"🔁  تبادل        {_fa_digits(ex.get('joined', 0))} جوین"
                             f"  ·  امروز {_fa_digits(ex.get('today', 0))}")
                if st.get("last_error"):
                    t.append(f"⚠️  {st['last_error'][:60]}")
            elif live:
                t += [self.LINE, "<i>گزارش زنده هنوز نرسیده…</i>"]
            try:
                t += [self.LINE, f"<i>{build_stamp()}</i>"]
            except Exception:
                pass
            return await self.edit(ev, "\n".join(t),
                [[B("🔄 بروزرسانی", "m:status")], back_btn()])



        # ---------- امتیاز ----------
        if data == "m:pts" or data == "pt:log":
            if not (sh and self.cfg["points_on"]):
                return await ans("سیستم امتیاز خاموش است")
            await ans()

            if data == "pt:log":
                lg = sh.p_log(uid, 12)
                ic = {"buy": "🛒", "runtime": "⚡️", "admin": "🎁", "use": "💸"}
                txt = f"📋 <b>گردش امتیاز</b>\n{self.LINE}\n\n" + ("\n".join(
                    f"{ic.get(w['kind'], '•')} {'+' if w['amount'] > 0 else ''}"
                    f"{_fa_digits(w['amount'])}   <i>{w['detail'] or w['kind']}</i>"
                    for w in lg) if lg else "<i>هنوز چیزی نیست.</i>")
                return await self.edit(ev, txt, [back_btn("m:pts")])

            bal = sh.p_balance(uid)
            per = max(1, self.cfg["cost_per_hour"])
            hrs = bal // per
            mn = self.cfg["min_points"]
            running = self.sup.is_running(uid)

            t = ["🎯 <b>امتیاز من</b>", self.LINE,
                 f"موجودی      <b>{_fa_digits(bal)}</b> امتیاز",
                 f"کارکرد       ≈ <b>{_fa_digits(hrs)} ساعت</b>"]
            if hrs >= 24:
                t.append(f"                 ({_fa_digits(hrs // 24)} روز و {_fa_digits(hrs % 24)} ساعت)")
            t += [self.LINE, ""]

            if self.has_sub(uid):
                t += ["💎 <b>اشتراک فعال داری</b>",
                      "تا پایان اشتراک امتیازی مصرف نمی‌شود.", ""]
            elif bal <= 0:
                t += ["🔴 <b>امتیازی نداری</b>",
                      f"برای روشن کردن سرویس حداقل <b>{_fa_digits(mn)}</b> امتیاز لازم است.", ""]
            elif bal < mn and not running:
                t += [f"🟠 برای فعال‌سازی حداقل <b>{_fa_digits(mn)}</b> امتیاز لازم است.",
                      f"<b>{_fa_digits(mn - bal)}</b> امتیاز کم داری.", ""]
            elif bal <= self.cfg["low_warn"]:
                t += ["🟠 <b>موجودی کم است</b> — به‌زودی سرویس خاموش می‌شود.", ""]
            else:
                t += ["🟢 موجودی کافی است.", ""]

            t += [self.LINE,
                  f"⚡️ مصرف: هر ساعت <b>{_fa_digits(per)}</b> امتیاز",
                  f"          (2 ساعت = {_fa_digits(per * 2)} امتیاز)",
                  f"🔓 حداقل برای فعال‌سازی: <b>{_fa_digits(mn)}</b> امتیاز",
                  f"🧯 خطای خود سلف: <b>{_fa_digits(self.cfg.get('self_error_fee', 5))}</b> امتیاز"]
            if self.cfg["start_fee"]:
                t += [f"▶️ هر بار روشن کردن: <b>{_fa_digits(self.cfg['start_fee'])}</b> امتیاز",
                      "💤 خاموش که باشد، مصرفی ندارد"]

            kb = [[B("🛒 خرید امتیاز", "m:packs", "success")]]
            if bal >= mn and not running and self.db.get(uid) \
                    and self.db.get(uid)["session"]:
                kb.append([B("▶️ روشن کردن سرویس", "s:on", "primary")])
            kb.append([B("📋 گردش امتیاز", "pt:log"),
                       B("💎 اشتراک ماهانه", "m:plans")])
            kb.append(back_btn())
            return await self.edit(ev, "\n".join(t), kb)

        # ---------- بسته‌های امتیاز ----------
        if data == "m:packs":
            if not (sh and self.cfg["points_on"]):
                return await ans("سیستم امتیاز خاموش است")
            await ans()
            pk = sh.packs()
            if not pk:
                return await self.edit(ev, "فعلاً بسته‌ای موجود نیست.", [back_btn("m:pts")])
            per = max(1, self.cfg["cost_per_hour"])
            icons = ["🔹", "🔷", "💠", "💎", "👑"]
            t = ["🛒 <b>خرید امتیاز</b>", self.LINE]
            rows = []
            for i, k in enumerate(pk):
                tot = k["points"] + k["bonus"]
                hrs = tot // per
                t.append(f"{icons[i % len(icons)]} <b>{k['name']}</b>")
                line = f"     {_fa_digits(k['points'])} امتیاز"
                if k["bonus"]:
                    line += f"  +  🎁 {_fa_digits(k['bonus'])} هدیه"
                t.append(line)
                t.append(f"     ≈ {_fa_digits(hrs)} ساعت  ·  <b>{money(k['price'])}</b>")
                t.append("")
                rows.append([B(f"{icons[i % len(icons)]} {_fa_digits(tot)} امتیاز  ·  "
                               f"{money(k['price'])}", f"kp:{k['id']}")])
            per2 = max(1, self.cfg["cost_per_hour"])
            t += [self.LINE,
                  f"💳 موجودی فعلی: <b>{_fa_digits(sh.p_balance(uid))}</b> امتیاز", "",
                  f"⚡️ هر ساعت کارکرد {_fa_digits(per2)} امتیاز کم می‌شود",
                  "💤 خاموشش کنی، مصرف هم متوقف می‌شود",
                  f"🔓 برای روشن کردن حداقل {_fa_digits(self.cfg['min_points'])} امتیاز",
                  f"▶️ هر بار روشن کردن {_fa_digits(self.cfg['start_fee'])} امتیاز"]
            t += ["", f"✏️ مقدار دلخواه هم می‌توانی بخری — هر امتیاز "
                      f"{money(self.cfg['point_price'])}"]
            rows.append([B("✏️ مقدار دلخواه", "kc:0", "primary")])
            rows.append([B("💎 اشتراک ماهانه (بدون محدودیت)", "m:plans", "primary")])
            rows.append([B("📚 آموزش خرید امتیاز", "tut:x:points", "success")])
            rows.append(back_btn())
            return await self.edit(ev, "\n".join(t), rows)

        if data.startswith("kp:"):
            await ans()
            k = sh.pack(int(data[3:]))
            if not k:
                return await self.edit(ev, "بسته پیدا نشد.", [back_btn("m:packs")])
            per = max(1, self.cfg["cost_per_hour"])
            tot = k["points"] + k["bonus"]
            wb = sh.balance(uid)
            t = [f"┏━━━━━━━━━━━━━━━┓", f"     <b>{k['name']}</b>",
                 f"┗━━━━━━━━━━━━━━━┛", "",
                 f"🎯  <b>امتیاز</b>      {_fa_digits(k['points'])}"]
            if k["bonus"]:
                t.append(f"🎁  <b>هدیه</b>        {_fa_digits(k['bonus'])}")
                t.append(f"➜   <b>جمع</b>         {_fa_digits(tot)}")
            t += [f"⏱  <b>کارکرد</b>      ≈ {_fa_digits(tot // per)} ساعت",
                  f"💰  <b>قیمت</b>        {money(k['price'])}",
                  "", self.LINE,
                  f"<i>هر امتیاز ≈ {money(k['price'] // max(tot, 1))}</i>"]
            rows = [[B("✅ خرید", f"ko:{k['id']}:0", "success")]]
            if wb > 0:
                rows.append([B(f"💳 خرید با کیف پول ({money(wb)})",
                               f"ko:{k['id']}:1", "success")])
            rows.append([B("🎟 دارم کد تخفیف", f"kd:{k['id']}")])
            rows.append(back_btn("m:packs"))
            return await self.edit(ev, "\n".join(t), rows)

        if data.startswith("kd:"):
            await ans()
            kid = int(data[3:])
            sh.cancel_open(uid)
            self.fsm[uid] = {"step": "pdisc", "pack": kid}
            return await self.edit(ev, "🎟 کد تخفیفت را بفرست:\n\n<i>/cancel برای لغو</i>",
                                   [back_btn(f"kp:{kid}")])

        if data.startswith("ko:"):
            await ans("در حال ساخت فاکتور…")
            _, kid, w = data.split(":")
            return await self.pack_invoice(uid, ev, int(kid), "", w == "1", edit=True)

        # ---------- خرید امتیاز به مقدار دلخواه ----------
        if data.startswith("kc:"):
            arg = data[3:]
            pp = self.cfg["point_price"]
            per = max(1, self.cfg["cost_per_hour"])
            mn, mx = self.cfg["min_points_buy"], self.cfg["max_points_buy"]
            if arg == "x":
                await ans()
                self.fsm[uid] = {"step": "custom_pts"}
                return await self.edit(ev,
                    f"✏️ <b>تعداد دلخواه</b>\n{self.LINE}\n\n"
                    f"عدد را بفرست. مثال: <code>150</code>\n\n"
                    f"<i>بین {_fa_digits(mn)} تا {_fa_digits(mx)}</i>\n\n"
                    f"<i>/cancel برای لغو</i>", [back_btn("kc:0")])
            if arg and arg != "0":
                await ans("در حال ساخت فاکتور…")
                self.fsm.pop(uid, None)
                return await self.custom_invoice(uid, ev, int(arg), edit=True)
            await ans()
            sh.cancel_open(uid)
            self.fsm[uid] = {"step": "custom_pts"}
            quick = [v for v in (50, 100, 250, 500) if mn <= v <= mx]
            rows = []
            for i in range(0, len(quick), 2):
                rows.append([B(f"{_fa_digits(v)} امتیاز · {money(v * pp)}", f"kc:{v}",
                               "success") for v in quick[i:i + 2]])
            rows.append([B("✏️ تعداد دلخواه", "kc:x")])
            rows.append(back_btn("m:packs"))
            return await self.edit(ev,
                f"✏️ <b>خرید امتیاز</b>\n{self.LINE}\n"
                f"هر امتیاز <b>{money(pp)}</b>  ·  "
                f"{_fa_digits(1)} امتیاز = {_fa_digits(1)} ساعت\n{self.LINE}\n\n"
                f"یکی را بزن، یا خودت عدد بفرست.\n"
                f"<i>بین {_fa_digits(mn)} تا {_fa_digits(mx)}</i>",
                rows)

        # ---------- شارژ کیف پول ----------
        if data == "w:topup":
            await ans()
            sh.cancel_open(uid)
            self.fsm[uid] = {"step": "topup"}
            mn, mx = self.cfg["min_topup"], self.cfg["max_topup"]
            quick = [v for v in (50_000, 100_000, 200_000, 500_000)
                     if mn <= v <= mx]
            rows = []
            for i in range(0, len(quick), 2):
                rows.append([B(money(v), f"wq:{v}", "success")
                             for v in quick[i:i + 2]])
            rows.append([B("✏️ مبلغ دلخواه", "wq:0")])
            rows.append(back_btn("m:wallet"))
            return await self.edit(ev,
                f"➕ <b>افزایش موجودی</b>\n{self.LINE}\n"
                f"موجودی فعلی: <b>{money(sh.balance(uid))}</b>\n"
                f"{self.LINE}\n\n"
                f"یکی از مبالغ زیر را بزن،\n"
                f"یا خودت عدد بفرست.\n\n"
                f"<i>بین {money(mn)} تا {money(mx)}</i>",
                rows)

        if data.startswith("wq:"):
            v = int(data[3:])
            if v == 0:
                await ans()
                self.fsm[uid] = {"step": "topup"}
                return await self.edit(ev,
                    f"✏️ <b>مبلغ دلخواه</b>\n{self.LINE}\n\n"
                    f"عدد را بفرست. مثال: <code>75000</code>\n\n"
                    f"<i>بین {money(self.cfg['min_topup'])} تا "
                    f"{money(self.cfg['max_topup'])}</i>\n\n"
                    f"<i>/cancel برای لغو</i>",
                    [back_btn("w:topup")])
            await ans("در حال ساخت فاکتور…")
            self.fsm.pop(uid, None)
            return await self.topup_invoice(uid, ev, v, edit=True)

        # ---------- سرویس ----------
        if data == "m:svc":
            await ans()
            c = self.db.get(uid)
            live = self.sup.is_running(uid)
            return await self.edit(ev,
                f"⚙️ <b>سرویس من</b>\n{self.LINE}\n"
                f"📡  وضعیت      {self.client_state(c)}\n"
                + (f"⏳  اعتبار      {human_left(c['expires_at'])}\n"
                   if self.has_sub(uid) else "")
                + (f"🎯  امتیاز      {_fa_digits(self.shop.p_balance(uid))}"
                   f"  ·  ≈{_fa_digits(self.hours_left(uid))} ساعت\n"
                   if self.shop and self.cfg["points_on"] else "")
                + (f"👤  اکانت       {c['name']}\n" if c and c.get("name") else "")
                + (f"🔄  ری‌استارت   {_fa_digits((c or {}).get('restarts') or 0)}\n"
                   if c and c.get("restarts") else "")
                + f"{self.LINE}\n\n" +
                ("🚀 هنوز سلف را روی اکانتت راه نینداخته‌ای.\n"
                 "<i>فقط شماره و یک کد می‌خواهد.</i>"
                 if not (c and c.get("session")) else
                 "💡 برای تنظیمات، در <b>Saved Messages</b> اکانتت بفرست:\n"
                 "<code>.panel</code>"
                 + ("" if self.has_sub(uid) or not self.cfg["points_on"] else
                    f"\n\n💤 خاموش که باشد، امتیازی مصرف نمی‌شود.\n"
                    f"<i>روشن کردن دوباره {_fa_digits(self.cfg['start_fee'])} امتیاز "
                    f"هزینه دارد.</i>")),
                svc_menu(live, bool(c and c.get("session")),
                         self.cfg["start_fee"], self.has_sub(uid)))

        if data.startswith("s:"):
            act = data[2:]
            c = self.db.get(uid)
            if act == "setup":
                await ans()
                return await self.setup_start(uid, ev.chat_id, ev)
            if not c:
                return await ans("اول /start را بزن")
            if act in ("on", "restart") and self.activate_points_mode(uid):
                c = self.db.get(uid)
            if c["status"] != "active":
                await ans("سرویست فعال نیست")
                return await self.edit(ev,
                    f"🔒 <b>سرویس هنوز فعال نیست</b>\n{self.LINE}\n"
                    f"وضعیت: {self.client_state(c)}\n\n"
                    "اول اشتراک یا امتیاز بخر، بعد راه‌اندازی سلف را بزن.",
                    [[B("🎯 خرید امتیاز", "m:packs", "success")],
                     [B("💎 اشتراک ماهانه", "m:plans", "primary")],
                     [B("🚀 راه‌اندازی سلف", "s:setup", "primary")],
                     back_btn("m:svc")])
            fee_msg = ""
            if act in ("on", "restart"):
                allow, why = self.can_run(uid)
                if not allow:
                    await ans(why)
                    return await self.edit(ev,
                        f"🔋 <b>{why}</b>\n\nبرای روشن کردن سرویس یکی از این‌ها:",
                        [[B("🛒 خرید امتیاز", "m:packs", "success")],
                         [B("💎 اشتراک ماهانه", "m:plans", "primary")],
                         back_btn("m:svc")])
                if act == "on":
                    ok, msg, fee_msg = self.start_service(
                        uid, first=not bool(c.get("started_at")),
                        restart=False, charge_success=not self.sup.is_running(uid))
                else:
                    # ری‌استارت هزینه عادی ندارد، اما خطای خود سلف ۵ امتیاز دارد.
                    ok, msg, fee_msg = self.start_service(
                        uid, restart=True, charge_success=False)
            elif act == "off":
                # خاموشیِ عمدی ثبت می‌شود تا بعد از آپدیت خودکار روشن نشود.
                ok, msg = self.sup.stop(uid, remember_off=True)
            elif act == "log":
                await ans()
                return await self.edit(ev, "📜 <b>گزارش</b>\n\n<pre>" +
                    self.sup.tail(uid, 20).replace("<", "&lt;")[-2000:] + "</pre>",
                    [[B("🔄 بروزرسانی", "s:log")], back_btn("m:svc")])
            else:
                return await ans()
            await ans(("✅ " if ok else "❌ ") + msg[:180])
            if not ok and act in ("on", "restart"):
                return await self.edit(ev,
                    "❌ <b>سلف فعال نشد</b>\n\n" + msg +
                    "\n\nاگر از اکانت خارج شده‌ای، ورود دوباره را بزن:",
                    [[B("🚀 راه‌اندازی سلف روی اکانتم", "s:setup", "primary")],
                     back_btn("m:svc")])
            # روشن کردن دستی سرویس هم مثل فعال‌سازی، بخش‌های آموزش را می‌فرستد
            # (بخش‌های «یک‌بار برای هر کاربر» دوباره تکرار نمی‌شوند)
            if ok and act == "on" and self.cfg.get("tut_auto", True):
                self.tut_schedule(uid, "after_run",
                                  wait=int(self.cfg.get("tut_auto_wait", 8) or 0))
                # سلف فعال شد → آموزش خودکار می‌رود (متن پیش‌فرض اگر بخشی نیست)
                self.tut_schedule_self_default(
                    uid, wait=int(self.cfg.get("tut_auto_wait", 8) or 0))
            live = self.sup.is_running(uid)
            body = f"⚙️ <b>سرویس من</b>\n\n{('✅ ' if ok else '❌ ')}{msg}\n"
            if fee_msg and ok:
                body += f"\n🎯 {fee_msg}\n"
            if act == "off" and ok:
                body += ("\n💤 تا وقتی خاموش است امتیازی مصرف نمی‌شود.\n"
                         f"<i>روشن کردن دوباره {_fa_digits(self.cfg['start_fee'])} "
                         f"امتیاز هزینه دارد.</i>\n")
            body += f"\nوضعیت: {'🟢 در حال کار' if live else '⚪ خاموش'}"
            return await self.edit(ev, body,
                svc_menu(live, bool(c["session"]),
                         self.cfg["start_fee"], self.has_sub(uid)))

        if not sh:
            return await ans()

        # ---------- فروشگاه ----------
        if data == "m:plans":
            await ans()
            pl = sh.plans()
            if not pl:
                return await self.edit(ev, "فعلاً پلنی موجود نیست.", [back_btn()])
            gems = ["🥉", "🥈", "🥇", "💎", "👑"]
            rows = [[B(f"{gems[i % len(gems)]} {x['name']}  ·  {money(x['price'])}",
                       f"p:{x['id']}")] for i, x in enumerate(pl)]
            b = sh.balance(uid)
            txt = ["🛒 <b>پلن‌های جفج</b>", "", self.LINE]
            for i, x in enumerate(pl):
                txt.append(f"{gems[i % len(gems)]} <b>{x['name']}</b>")
                txt.append(f"     ⏱ {_fa_digits(x['days'])} روز   ·   👥 {_fa_digits(x['max_accounts'])} اکانت")
                txt.append(f"     💰 <b>{money(x['price'])}</b>")
                per = x["price"] // max(x["days"] // 30, 1)
                if x["days"] >= 60:
                    txt.append(f"     <i>ماهی {money(per)}</i>")
                txt.append("")
            txt.append(self.LINE)
            if b:
                txt.append(f"💳 موجودی شما: <b>{money(b)}</b>")
            txt.append("\n👇 یکی را انتخاب کن")
            if self.cfg["points_on"]:
                txt.append("")
                txt.append("<i>پول ماهانه نداری؟ با امتیاز هم می‌شود —</i>")
                txt.append(f"<i>از {money(sh.packs()[0]['price']) if sh.packs() else ''} "
                           f"شروع می‌شود.</i>")
                rows.append([B("🎯 خرید امتیاز به‌جای اشتراک", "m:packs", "success")])
            rows.append([B("📚 آموزش اشتراک ماهانه", "tut:x:sub", "success")])
            rows.append(back_btn())
            return await self.edit(ev, "\n".join(txt), rows)

        if data.startswith("p:"):
            await ans()
            pid = int(data[2:])
            x = sh.plan(pid)
            if not x:
                return await self.edit(ev, "پلن پیدا نشد.", [back_btn("m:plans")])
            b = sh.balance(uid)
            feats = [f.strip() for f in (x["features"] or "").split("•") if f.strip()]
            txt = (f"┏━━━━━━━━━━━━━━━┓\n"
                   f"     <b>{x['name']}</b>\n"
                   f"┗━━━━━━━━━━━━━━━┛\n\n"
                   f"⏱  <b>مدت</b>        {_fa_digits(x['days'])} روز\n"
                   f"👥  <b>اکانت</b>       تا {_fa_digits(x['max_accounts'])} عدد\n"
                   f"💰  <b>قیمت</b>       {money(x['price'])}\n")
            if feats:
                txt += "\n" + "\n".join(f"   ✓ {f}" for f in feats) + "\n"
            txt += f"\n{self.LINE}\n"
            if b:
                rest = max(0, x["price"] - b)
                txt += (f"💳 موجودی: {money(b)}\n"
                        f"➜ با کیف پول فقط <b>{money(rest)}</b>\n")
            rows = [[B("✅ خرید", f"o:{pid}:0", "success")]]
            if b > 0:
                rows.append([B(f"💳 خرید با کیف پول ({money(b)})", f"o:{pid}:1", "success")])
            rows.append([B("🎟 دارم کد تخفیف", f"d:{pid}")])
            rows.append(back_btn("m:plans"))
            return await self.edit(ev, txt, rows)

        if data.startswith("d:"):
            await ans()
            pid = int(data[2:])
            sh.cancel_open(uid)
            self.fsm[uid] = {"step": "disc", "plan": pid}
            return await self.edit(ev,
                "🎟 کد تخفیفت را بفرست:\n\n(یا /cancel برای لغو)",
                [back_btn(f"p:{pid}")])

        if data.startswith("o:"):
            await ans("در حال ساخت فاکتور…")
            _, pid, w = data.split(":")
            return await self.make_invoice(uid, ev, int(pid), "", w == "1", edit=True)

        if data == "m:wallet":
            await ans()
            b = sh.balance(uid)
            lg = sh.wallet_log(uid, 6)
            txt = (f"💳 <b>کیف پول</b>\n{self.LINE}\n"
                   f"موجودی فعلی\n"
                   f"<b>{money(b)}</b>\n{self.LINE}\n")
            if lg:
                txt += "\n📋 <b>تراکنش‌های اخیر</b>\n\n" + "\n".join(
                    f"{'🟢 +' if w['amount'] > 0 else '🔴 −'}{money(abs(w['amount']))}\n"
                    f"     <i>{w['detail'] or w['kind']}</i>" for w in lg)
            else:
                txt += "\n<i>هنوز تراکنشی نداری.</i>"
            txt += (f"\n\n{self.LINE}\n"
                    "<i>موجودی کیف پول را می‌توانی هنگام خرید اشتراک یا "
                    "امتیاز خرج کنی.</i>")
            return await self.edit(ev, txt,
                [[B("➕  افزایش موجودی", "w:topup", "success")],
                 [B("💎 اشتراک", "m:plans", "primary"),
                  B("🎯 امتیاز", "m:packs", "primary")],
                 [B("📚 آموزش شارژ کیف پول", "tut:x:wallet", "success")],
                 back_btn()])

        if data == "m:ref":
            await ans()
            if not self.phone_ok(uid):
                txt = ("🎁 <b>زیرمجموعه‌گیری</b>\n" + self.LINE + "\n\n"
                       "برای فعال‌شدن پاداش دعوت، اول شماره موبایل ایرانت را تأیید کن.\n"
                       + self.referral_rate_text(uid) + "\n"
                       "فعال‌سازی سلف لازم نیست.")
                return await self.edit(ev, txt,
                    [[B("✅ تأیید شماره", "r:verify", "success")], back_btn()])
            me = await self.bot.get_me()
            link = f"https://t.me/{me.username}?start=r{uid}"
            refs = sh.my_refs(uid)
            rewarded = sum(1 for r in refs if r["rewarded"])
            pts = sh.p_balance(uid)
            return await self.edit(ev,
                "🎁 <b>زیرمجموعه‌گیری</b>\n" + self.LINE + "\n"
                "✅ شماره تأیید شده\n\n"
                f"🔗 <b>لینک دعوت شما</b>\n<code>{link}</code>\n\n"
                + self.referral_rate_text(uid) + "\n"
                "دعوت‌شده باید شماره موبایل ایرانش را تأیید کند.\n"
                + self.LINE + "\n"
                f"👥 دعوت‌شده: {_fa_digits(len(refs))} نفر\n"
                f"✅ دعوت معتبر: {_fa_digits(rewarded)} نفر\n"
                f"🎯 امتیاز فعلی: {_fa_digits(pts)}",
                [[B("🔄 بروزرسانی", "m:ref")], back_btn()])

        if data == "m:orders":
            await ans()
            rows = sh.user_orders(uid, 8)
            if not rows:
                return await self.edit(ev, "سفارشی نداری.",
                                       [[B("🛒 خرید", "m:plans", "primary")], back_btn()])
            ic = {"pending": "⏳", "paid": "📤", "approved": "✅",
                  "rejected": "❌", "canceled": "🚫"}
            kic = {"wallet": "💳", "points": "🎯"}
            txt = "🧾 <b>سفارش‌های من</b>\n\n" + "\n".join(
                f"{ic.get(o['status'], '•')} {kic.get(o.get('kind'), '💎')} "
                f"#{_fa_digits(o['id'])} {o['plan_name']} — {money(o['final'])}"
                + (f"\n     💬 {o['note']}" if o["note"] else "")
                for o in rows)
            return await self.edit(ev, txt, [back_btn()])

        if data == "m:support":
            await ans()
            self.fsm[uid] = {"step": "ticket"}
            ts = sh.user_tickets(uid)
            sup_head = self.cfg.get("support_text") or "🎧 <b>پشتیبانی</b>\n\nمشکل یا سوالت را بنویس و بفرست."
            txt = sup_head
            if ts:
                txt += "\n\n<b>تیکت‌های قبلی</b>\n" + "\n".join(
                    f"#{_fa_digits(t['id'])} {t['subject'][:40]} — {t['status']}" for t in ts[:5])
            if self.cfg["contact"]:
                txt += f"\n\nیا مستقیم: {self.cfg['contact']}"
            return await self.edit(ev, txt, [back_btn()])

        # ---------- مدیر ----------
        if data.startswith("a:") and adm:
            k = data[2:]
            await ans()
            if k == "rules":
                t, kb = self.rules_screen()
                return await self.edit(ev, t, kb)
            if k == "rules:tog":
                now_val = not self.rules_on()
                self.cfg["rules_on"] = now_val
                self.cfg.save()
                self.db.log(uid, "rules_toggle", "on" if now_val else "off")
                t, kb = self.rules_screen()
                return await self.edit(ev,
                    f"وضعیت قوانین در شروع ربات: <b>{'🟢 فعال' if now_val else '🔴 غیرفعال'}</b>\n"
                    + self.LINE + "\n" + t, kb)
            if k == "rules:edit":
                self.fsm[uid] = {"step": "rules_set"}
                cur = str(self.cfg.get("rules_text") or "").strip()
                return await self.edit(ev,
                    f"✏️ <b>تغییر متن قوانین ربات</b>\n{self.LINE}\n"
                    "متن جدید قوانین را همین‌جا بفرست (چندخطی مجاز است).\n"
                    "این متن در ابتدای ورود کاربر به ربات نمایش داده می‌شود و کاربر باید آن را تأیید کند.\n\n"
                    + (f"<b>متن فعلی:</b>\n{self._esc(cur[:1200])}\n\n" if cur else "")
                    + "برای برگشت به متن پیش‌فرض بنویس: <code>پیش‌فرض</code>\n"
                    "<i>/cancel برای لغو</i>",
                    [[B("⬅️ بازگشت", "a:rules")]])
            if k == "rules:btn":
                self.fsm[uid] = {"step": "rules_btn_set"}
                cur_b = self.rules_btn_label()
                return await self.edit(ev,
                    f"✏️ <b>تغییر متن دکمه تأیید قوانین</b>\n{self.LINE}\n"
                    f"متن فعلی دکمه: <b>{self._esc(cur_b)}</b>\n\n"
                    "متن جدید دکمه را بفرست (مثلاً: <code>✅ قوانین را قبول دارم</code>).\n"
                    "برای برگشت به پیش‌فرض بنویس: <code>پیش‌فرض</code>\n"
                    "<i>/cancel برای لغو</i>",
                    [[B("⬅️ بازگشت", "a:rules")]])
            if k == "rules:prev":
                await self.say(uid, self.rules_gate_text(),
                               [[B(self.rules_btn_label(), "a:rules", "success")],
                                [B("⬅️ بازگشت به تنظیمات قوانین", "a:rules")]],
                               key="rules_prev")
                t, kb = self.rules_screen()
                return await self.edit(ev,
                    "👁 پیش‌نمایش قوانین در چت ارسال شد.\n" + self.LINE + "\n" + t, kb)
            if k == "rules:reset":
                n_rst = self.db.rules_reset_all()
                self.db.log(uid, "rules_reset_all", str(n_rst))
                t, kb = self.rules_screen()
                return await self.edit(ev,
                    f"🔄 تأیید قوانین برای <b>{_fa_digits(n_rst)}</b> کاربر ریست شد (همه دوباره قوانین را می‌بینند).\n"
                    + self.LINE + "\n" + t, kb)
            if k == "rules:def":
                self.cfg["rules_text"] = ""
                self.cfg["rules_btn"] = ""
                self.cfg.save()
                self.db.log(uid, "rules_default", "")
                t, kb = self.rules_screen()
                return await self.edit(ev,
                    "♻️ متن قوانین و دکمه تأیید به حالت پیش‌فرض برگشت.\n"
                    + self.LINE + "\n" + t, kb)
            if k == "trial":
                t, kb = self.trial_screen()
                return await self.edit(ev, t, kb)
            if k == "trial_tog":
                now_val = not bool(self.cfg.get("trial_on", True))
                self.cfg["trial_on"] = now_val
                self.cfg.save()
                self.db.log(uid, "trial_toggle", "on" if now_val else "off")
                t, kb = self.trial_screen()
                return await self.edit(ev,
                    f"وضعیت تست رایگان: <b>{'🟢 فعال' if now_val else '🔴 غیرفعال'}</b>\n"
                    + self.LINE + "\n" + t, kb)
            if k.startswith("trial_min:"):
                v = k.split(":", 1)[1]
                if v == "x":
                    await ans()
                    self.fsm[uid] = {"step": "trial_min"}
                    return await self.edit(ev,
                        "✍️ <b>مدت تست رایگان</b>\n" + self.LINE + "\n"
                        "مدت را به <b>دقیقه</b> بفرست — مثال: <code>90</code>\n"
                        "اگر ساعت می‌خواهی بنویس: <code>2 ساعت</code>\n"
                        "نیم‌ساعت: <code>30</code> · یک‌ساعت: <code>60</code> · "
                        "دو‌ساعت: <code>120</code>\n\n"
                        "<i>/cancel برای لغو</i>",
                        [back_btn("a:trial")])
                mins = self._parse_trial_minutes(v)
                if not mins:
                    await ans("عدد نامعتبر")
                    t, kb = self.trial_screen()
                    return await self.edit(ev, t, kb)
                mins, warn = self._set_trial_minutes(mins)
                await ans(f"مدت: {trial_duration_label(mins)}")
                t, kb = self.trial_screen()
                return await self.edit(ev, f"✅ مدت تست: <b>{trial_duration_label(mins)}</b>"
                                           f"  ·  یادآوری: {_fa_digits(warn)} دقیقه آخر\n"
                                           + self.LINE + "\n" + t, kb)
            if k.startswith("trial_warn:"):
                mins = self.trial_minutes_now()
                w = int(digits(k.split(":", 1)[1]) or 0)
                w = max(1, min(w or 1, max(1, mins // 2)))
                self.cfg["trial_warning_minutes"] = w
                self.cfg.save()
                await ans(f"یادآوری: {w} دقیقه آخر")
                t, kb = self.trial_screen()
                return await self.edit(ev, t, kb)
            if k == "trial_reset":
                total, running, used = self.db.trial_stats()
                return await self.edit(ev,
                    f"♻️ <b>ریست تست رایگان برای همه</b>\n{self.LINE}\n"
                    f"پرونده‌ی تستِ <b>{_fa_digits(total)}</b> کاربر پاک می‌شود "
                    f"({_fa_digits(used)} نفر قبلاً تست گرفته‌اند) و همه دوباره "
                    "می‌توانند «تست رایگان» بگیرند.\n\n"
                    "• تستِ کسی که همین حالا در حال اجراست قطع نمی‌شود؛ فقط "
                    "دوباره واجد شرایط می‌شود.\n"
                    "• اشتراک، امتیاز و کیف پول دست نمی‌خورد.\n\n"
                    "مطمئنی؟",
                    [[B("✅ بله، همه را ریست کن", "a:trial_reset_yes", "danger")],
                     [B("↩️ انصراف", "a:trial", "primary")]])
            if k == "trial_reset_yes":
                n, running = self.db.trial_reset_all()
                self.db.log(uid, "trial_reset_all", f"{n} clients, running={running}")
                await ans("ریست شد")
                t, kb = self.trial_screen()
                msg = (f"✅ <b>ریست شد</b> — {_fa_digits(n)} کاربر دوباره می‌توانند "
                       "تست رایگان بگیرند.\n")
                if running:
                    msg += (f"🌀 {_fa_digits(running)} نفر همین حالا داخل تست‌اند و "
                            "تستشان قطع نشد.\n")
                return await self.edit(ev, msg + self.LINE + "\n" + t, kb)

            if k == "home":
                cnt = self.db.counts()
                st = sh.stats() if sh else {"day": (0, 0), "orders": {}}
                return await self.edit(ev,
                    f"🛠 <b>پنل مدیر</b>\n{self.LINE}\n"
                    f"👥  مشتری فعال      {_fa_digits(cnt.get('active', 0))}\n"
                    f"🟢  سرویس روشن      {_fa_digits(self.sup.running_count())}\n"
                    f"📤  منتظر تأیید      {_fa_digits(st['orders'].get('paid', 0))}\n"
                    f"💰  فروش امروز      {money(st['day'][1])}\n"
                    f"{self.LINE}\n"
                    f"🧬 نسخه‌ی کد: <code>{BUILD_VERSION}</code> · کامیت "
                    f"<code>{GIT_COMMIT}</code> · <code>{CODE_ID}</code> · "
                    f"⏱ {uptime_text()}",
                    admin_menu(st['orders'].get('paid', 0),
                               len(sh.open_tickets()) if sh else 0,
                               trial_on=bool(self.cfg.get("trial_on", True))))
            if k == "pending":
                rows = sh.pending_orders()
                if not rows:
                    return await self.edit(ev, "سفارش منتظری نیست ✅",
                                           [back_btn("a:home")])
                kb = []
                txt = [f"📤 <b>منتظر تأیید ({_fa_digits(len(rows))})</b>", ""]
                for o in rows[:8]:
                    c = self.db.get(o["uid"])
                    ic = {"wallet": "💳", "points": "🎯"}.get(o.get("kind"), "💎")
                    txt.append(f"{ic} #{_fa_digits(o['id'])} {money(o['final'])} — "
                               f"{o['plan_name']} — {c['name'] if c else o['uid']}")
                    kb.append([B(f"✅ #{o['id']}", f"ao:{o['id']}", "success"),
                               B(f"❌ #{o['id']}", f"ar:{o['id']}", "danger"),
                               B(f"👁", f"av:{o['id']}")])
                kb.append(back_btn("a:home"))
                return await self.edit(ev, "\n".join(txt), kb)
            if k.startswith("ulist:"):
                return await self.admin_users_page(ev, int(digits(k.split(":")[-1]) or 0))
            if k == "ufind":
                self.fsm[uid] = {"step": "ufind_q"}
                return await self.edit(ev,
                    f"🔍 <b>جستجوی کاربر</b>\n{self.LINE}\n"
                    "آیدی عددی (<code>uid</code>)، <code>@username</code>، شماره موبایل "
                    "یا بخشی از نام کاربر را بفرست تا صفحه‌ی مدیریتش باز شود.\n\n"
                    "<i>/cancel برای لغو</i>",
                    [[B("👥 لیست مشتری‌ها", "a:ulist:0", "primary")],
                     back_btn("a:home")])
            if k == "uwipe":
                self.fsm[uid] = {"step": "uwipe_pick"}
                rows = self.db.all()[:6]
                kb = []
                for c in rows:
                    lbl = f"🗑 {c.get('name') or c['uid']} ({c['uid']})"
                    kb.append([B(lbl[:48], f"aud:{c['uid']}", "danger")])
                kb.append([B("👥 لیست کامل مشتری‌ها", "a:ulist:0", "primary")])
                kb.append(back_btn("a:home"))
                return await self.edit(ev,
                    f"🗑 <b>پاک کردن اطلاعات کاربر</b>\n{self.LINE}\n"
                    "آیدی عددی (<code>uid</code>)، <code>@username</code> یا شماره‌ی کاربر را "
                    "همینجا بفرست (یا از لیست زیر انتخاب کن).\n\n"
                    "در مرحله‌ی بعد با تأیید تو، دو حالت داری:\n"
                    "• <b>🗑 پاک کردن کل اطلاعات</b> (حساب، سشن، اشتراک، امتیاز/کیف‌پول + تمام تنظیمات جفج و تنظیمات و دیتابیس تبادل)\n"
                    "• <b>🧹 فقط پاک کردن تنظیمات جفج و تبادل</b> (با حفظ سشن و اشتراک)\n\n"
                    "<i>/cancel برای لغو</i>",
                    kb)
            if k == "bcast":
                self.fsm[uid] = {"step": "bcast"}
                return await self.edit(ev,
                    f"📢 <b>پیام همگانی</b>\n{self.LINE}\n"
                    "متنی که می‌فرستی به <b>همه</b> مشتری‌ها می‌رود.\n\n"
                    "<i>/cancel برای لغو</i>",
                    [back_btn("a:home")])
            if k == "prices":
                pl = sh.plans(all_=True) if sh else []
                if not pl:
                    return await self.edit(ev, "پلنی نیست.", [back_btn("a:home")])
                txt = [f"💰 <b>قیمت پلن‌ها</b>", self.LINE]
                kb = []
                for x in pl:
                    txt.append(f"{'🟢' if x['active'] else '⚪'} {x['name']} — "
                               f"{_fa_digits(x['days'])} روز — <b>{money(x['price'])}</b>")
                    kb.append([B(f"✏️ {x['name']}  {money(x['price'])}",
                                 f"apr:{x['id']}")])
                kb.append(back_btn("a:home"))
                return await self.edit(ev, "\n".join(txt), kb)
            if k == "pkprice":
                pk = sh.packs(all_=True) if sh else []
                if not pk:
                    return await self.edit(ev, "بسته‌ای نیست.", [back_btn("a:home")])
                txt = [f"🎯 <b>قیمت بسته‌های امتیاز</b>", self.LINE]
                kb = []
                for x in pk:
                    tot = x["points"] + x["bonus"]
                    txt.append(f"{'🟢' if x['active'] else '⚪'} {x['name']} — "
                               f"{_fa_digits(tot)} امتیاز — <b>{money(x['price'])}</b>")
                    kb.append([B(f"✏️ {x['name']}  {money(x['price'])}",
                                 f"apk:{x['id']}")])
                kb.append(back_btn("a:home"))
                return await self.edit(ev, "\n".join(txt), kb)
            if k == "discs":
                rows = sh.discounts() if sh else []
                txt = [f"🎟 <b>کدهای تخفیف</b>", self.LINE]
                if not rows:
                    txt.append("<i>هنوز کدی نیست.</i>")
                else:
                    for d in rows[:15]:
                        txt.append(
                            f"{'🟢' if d['active'] else '⚪'} <code>{d['code']}</code> "
                            f"{_fa_digits(d['percent'])}٪"
                            + (f"+{money(d['flat'])}" if d["flat"] else "")
                            + f"  {_fa_digits(d['used'])}/"
                            + (_fa_digits(d["max_uses"]) if d["max_uses"] else "∞"))
                kb = [[B("➕ ساخت کد تخفیف", "a:ndisc", "success")]]
                for d in (rows or [])[:8]:
                    kb.append([B(("🔴 خاموش " if d["active"] else "🟢 روشن ") + d["code"],
                                 f"adt:{d['code']}")])
                kb.append(back_btn("a:home"))
                return await self.edit(ev, "\n".join(txt), kb)
            if k == "ndisc":
                self.fsm[uid] = {"step": "disc_new"}
                return await self.edit(ev,
                    f"🎟 <b>کد تخفیف جدید</b>\n{self.LINE}\n"
                    "یک خط بفرست به این شکل:\n"
                    "<code>OFF20 20</code>  ← ۲۰ درصد\n"
                    "<code>GIFT 0 50000</code>  ← ۵۰ هزار تومان\n"
                    "<code>VIP 30 0 10 7</code>  ← ۳۰٪، ۱۰ بار، ۷ روز\n\n"
                    "<i>/cancel برای لغو</i>",
                    [back_btn("a:discs")])
            if k == "rt":
                txt, kb = self.rt_list_view()
                return await self.edit(ev, txt, kb)
            if k.startswith(("rt:", "rte:", "rtr:")):
                kind, rid = k.split(":", 1)
                r = self.rt_find(rid)
                if not r:
                    return await self.edit(ev, "این مورد پیدا نشد.",
                                           [back_btn("a:rt")])
                if kind == "rt":
                    txt, kb = self.rt_item_view(r)
                    return await self.edit(ev, txt, kb)
                if kind == "rte":
                    self.fsm[uid] = {"step": "rt_set", "rt_id": rid}
                    cur = self.rt_current(r)
                    return await self.edit(ev,
                        f"✏️ <b>{r[1]} {r[2]}</b>\n{self.LINE}\n"
                        + ("هر خط یک جمله بفرست (حداکثر ۱۰ خط)؛ هر بار یکی "
                           "تصادفی انتخاب می‌شود.\n"
                           "جای اسمِ مشتری: <code>{name}</code>\n"
                           if r[4] else
                           "متنِ جدید را همین‌جا بفرست.\n")
                        + ("\nبرای برگشت به پیش‌فرض بنویس: <code>پیش‌فرض</code>\n"
                           if cur else "")
                        + "\n<i>/cancel برای لغو</i>",
                        [[B("⬅️ بازگشت", f"a:rt:{rid}")]])
                if kind == "rtr":
                    self.cfg[r[3]] = ""
                    self.db.log(uid, "rt_reset", rid)
                    txt, kb = self.rt_item_view(r)
                    return await self.edit(ev,
                        "♻️ برگشت به پیش‌فرض.\n\n" + txt, kb)
            # ── 📋 دستورات آماده (a:cm*) ──
            if k == "cm":
                txt, kb = self.cm_list_view()
                return await self.edit(ev, txt, kb)
            if k == "cm:prev":
                pages = self.cmds_pages()
                if not pages:
                    return await self.edit(ev,
                        "👁 <b>پیش‌نمایش</b>\n%s\n\n"
                        "⚪ چیزی برای نمایش نیست؛ اول یک دستور ثبت کن."
                        % self.LINE, [back_btn("a:cm")])
                await self.say(uid,
                    "👁 <b>پیش‌نمایش</b> — مشتری همین را می‌بیند "
                    "(%s پیام):" % _fa_digits(len(pages)),
                    [[B("⬅️ بازگشت", "a:cm")]])
                await self.send_cmds(uid)
                return
            if k == "cmi":
                if len(self.cmd_items()) >= self.CM_MAX:
                    return await self.edit(ev,
                        "سقف لیست %s دستور است؛ اول چندتا را پاک کن."
                        % _fa_digits(self.CM_MAX), [back_btn("a:cm")])
                self.fsm[uid] = {"step": "cm_add", "n": 1, "d": {}}
                return await self.edit(ev,
                    "➕ <b>افزودن دستور</b> — قدم ۱ از ۳\n%s\n"
                    "<b>عنوان</b> این مرحله را بفرست؛ مثل «پنل» یا «کانال».\n\n"
                    "<i>/cancel برای لغو</i>" % self.LINE,
                    [back_btn("a:cm")])
            if k == "cmxy":
                items = [dict(zip(("title", "cmd", "note"), s))
                         for s in self.CMD_STARTER]
                self.cmd_save(items)
                self.db.log(uid, "cm_starter", str(len(items)))
                txt, kb = self.cm_list_view()
                return await self.edit(ev,
                    "⚡️ %s دستورِ پیشنهادی ثبت شد. حالا هرکدام را می‌توانی "
                    "عوض کنی یا حذف کنی.\n\n%s" % (_fa_digits(len(items)), txt), kb)
            if k == "cmx":
                txt, kb = self.cm_starter_view()
                return await self.edit(ev, txt, kb)
            if k.startswith("cme:"):
                rest = k[4:]
                if rest == "intro":
                    self.fsm[uid] = {"step": "cm_intro"}
                    txt, kb = self.cm_intro_view()
                    return await self.edit(ev, txt, kb)
                parts = rest.split(":")
                try:
                    i = int(parts[0])
                except (TypeError, ValueError):
                    return await self.edit(ev, "این مورد پیدا نشد.",
                                           [back_btn("a:cm")])
                items = self.cmd_items()
                if not (0 <= i < len(items)):
                    return await self.edit(ev, "این مورد پیدا نشد.",
                                           [back_btn("a:cm")])
                if len(parts) == 1:
                    got = self.cm_item_view(i)
                    if not got:
                        return await self.edit(ev, "این مورد پیدا نشد.",
                                               [back_btn("a:cm")])
                    txt, kb = got
                    return await self.edit(ev, txt, kb)
                f = self.cm_field(parts[1])
                if not f:
                    return await self.edit(ev, "این مورد پیدا نشد.",
                                           [back_btn("a:cm")])
                self.fsm[uid] = {"step": "cm_edit", "idx": i, "f": f[0]}
                got = self.cm_edit_prompt(i, f[0])
                if not got:
                    return await self.edit(ev, "این مورد پیدا نشد.",
                                           [back_btn("a:cm")])
                txt, kb = got
                return await self.edit(ev, txt, kb)
            if k.startswith("cmu:"):
                parts = k[4:].split(":")
                try:
                    i = int(parts[0])
                except (TypeError, ValueError):
                    return await self.edit(ev, "این مورد پیدا نشد.",
                                           [back_btn("a:cm")])
                items = self.cmd_items()
                j = i - 1 if len(parts) > 1 and parts[1] == "u" else i + 1
                if not (0 <= i < len(items)) or not (0 <= j < len(items)):
                    got = self.cm_item_view(i) if 0 <= i < len(items) else None
                    if not got:
                        return await self.edit(ev, "جابه‌جایی ممکن نیست؛ "
                                                   "همین‌جا اول یا آخر است.",
                                               [back_btn("a:cm")])
                    txt, kb = got
                    return await self.edit(ev, txt, kb)
                items[i], items[j] = items[j], items[i]
                self.cmd_save(items)
                self.db.log(uid, "cm_move", "%d->%d" % (i, j))
                got = self.cm_item_view(j)
                txt, kb = got if got else self.cm_list_view()
                return await self.edit(ev, txt, kb)
            if k.startswith("cmd:"):
                parts = k[4:].split(":")
                try:
                    i = int(parts[0])
                except (TypeError, ValueError):
                    return await self.edit(ev, "این مورد پیدا نشد.",
                                           [back_btn("a:cm")])
                items = self.cmd_items()
                if not (0 <= i < len(items)):
                    return await self.edit(ev, "این مورد پیدا نشد.",
                                           [back_btn("a:cm")])
                if len(parts) > 1 and parts[1] == "y":
                    gone = items.pop(i)
                    self.cmd_save(items)
                    self.db.log(uid, "cm_del", gone.get("cmd") or gone.get("title"))
                    txt, kb = self.cm_list_view()
                    return await self.edit(ev,
                        "🗑 «%s» پاک شد.\n\n%s"
                        % (self._esc(gone.get("title") or gone.get("cmd") or "—"),
                           txt), kb)
                got = self.cm_del_view(i)
                if not got:
                    return await self.edit(ev, "این مورد پیدا نشد.",
                                           [back_btn("a:cm")])
                txt, kb = got
                return await self.edit(ev, txt, kb)
            if k == "samples":
                chat, ids = self.samples_src()
                n = len(ids)
                stat = (f"✅ ثبت شده — {_fa_digits(n)} پیام" if chat and n
                        else "⚪ هنوز نمونه‌ای ثبت نشده")
                kb = [[B("📤 ثبت / تغییر نمونه‌ها", "a:sample_set", "success")],
                      [B("👁 پیش‌نمایش", "a:sample_view", "primary")]]
                if chat and n:
                    kb.append([B("🗑 پاک کردن نمونه‌ها", "a:sample_del", "danger")])
                kb.append(back_btn("a:home"))
                return await self.edit(ev,
                    f"🎞 <b>نمونه‌های جفج رفتن ربات</b>\n{self.LINE}\n"
                    f"وضعیت: {stat}\n{self.LINE}\n"
                    "محتوایی که کاربر با زدن دکمه‌ی «🎞 نمونه‌های جفج رفتن ربات» می‌بیند را اینجا ثبت کن.\n\n"
                    "لینک کانال، عکس، کپشن یا چند پیام پشت‌سرهم بفرست؛ می‌توانی لینک و عکس را با هم ثبت کنی.\n"
                    "پیام‌ها به همان ترتیبی که می‌فرستی برای کاربر کپی می‌شوند.\n\n"
                    "<i>برای تغییر، مجموعه‌ی جدید را ثبت کن؛ برای حذف، «پاک کردن نمونه‌ها» را بزن.</i>", kb)
            if k == "sample_set":
                self.fsm[uid] = {"step": "sample_set", "sample_chat": 0,
                                 "sample_pending": []}
                return await self.edit(ev,
                    f"📤 <b>ثبت نمونه‌های جفج رفتن ربات</b>\n{self.LINE}\n"
                    "محتوا را همین‌جا بفرست — لینک، متن، عکس یا کپشن‌دار.\n"
                    "اگر هم لینک و هم عکس داری، هر دو را به ترتیب بفرست؛ آلبوم هم پشتیبانی می‌شود.\n\n"
                    "وقتی تمام شد «✅ تمام شد — ذخیره» را بزن. برای لغو /cancel بفرست.",
                    [[B("✅ تمام شد — ذخیره", "a:sample_done", "success")],
                     [B("⬅️ بازگشت", "a:samples")]])
            if k == "sample_done":
                state = self.fsm.get(uid) or {}
                pending = state.get("sample_pending") or []
                if not pending:
                    return await self.edit(ev,
                        "❌ هنوز محتوایی دریافت نشده. اول لینک یا عکس را بفرست.",
                        [[B("✅ تمام شد — ذخیره", "a:sample_done", "success")],
                         [B("⬅️ بازگشت", "a:samples")]])
                self.fsm.pop(uid, None)
                self.cfg["sample_chat"] = state.get("sample_chat") or uid
                self.cfg["sample_ids"] = pending
                self.cfg.save()
                self.db.log(uid, "samples_set", f"{len(pending)} پیام")
                return await self.edit(ev,
                    f"✅ <b>نمونه‌ها ذخیره شد</b>\n📦 {_fa_digits(len(pending))} پیام ثبت شد.",
                    [[B("👁 پیش‌نمایش", "a:sample_view", "primary")],
                     [B("🎞 صفحه‌ی نمونه‌ها", "a:samples")]])
            if k == "sample_view":
                await self.send_samples(uid)
                return await self.edit(ev,
                    "👁 <b>پیش‌نمایش</b>\nنمونه‌های فعلی برایت ارسال شد؛ همین را کاربر می‌گیرد.",
                    [[B("⬅️ بازگشت", "a:samples")]])
            if k == "sample_del":
                self.cfg["sample_chat"] = 0
                self.cfg["sample_ids"] = []
                self.cfg.save()
                self.db.log(uid, "samples_del", "")
                return await self.edit(ev,
                    "🗑 نمونه‌های جفج رفتن ربات پاک شد.",
                    [[B("📤 ثبت دوباره", "a:sample_set", "success")],
                     [B("⬅️ بازگشت", "a:samples")]])

            if k == "welcome":
                self.fsm[uid] = {"step": "welcome_set"}
                cur = self.cfg.get("welcome") or "تنظیم نشده"
                return await self.edit(ev,
                    f"📝 <b>متن خوش‌آمدگویی</b>\n{self.LINE}\n\n"
                    f"متن فعلی:\n{cur}\n\n"
                    "متن جدید را بفرست. برای حذف متن بنویس: خاموش\n"
                    "/cancel برای لغو",
                    [back_btn("a:home")])
            if k == "tut":
                chat, ids = self.tut_src()
                n = len(ids)
                stat = (f"✅ ثبت شده — {_fa_digits(n)} پیام" if chat and n
                        else "⚪ هنوز محتوا ثبت نشده (متن پیش‌فرض می‌رود)")
                if chat and n:
                    kb = [[B("➕ افزودن به محتوا", "a:tut_add", "success")],
                          [B("📤 ثبت / تغییر محتوا (جایگزینی)", "a:tut_set",
                             "primary")],
                          [B("📦 مدیریت محتوا", "a:tut_items", "primary"),
                           B("🗑 پاک‌کردن همه", "a:tut_del", "danger")],
                          [B("👁 پیش‌نمایش", "a:tut_view", "primary")]]
                else:
                    kb = [[B("📤 ثبت محتوا", "a:tut_set", "success")],
                          [B("📦 مدیریت محتوا", "a:tut_items", "primary"),
                           B("👁 پیش‌نمایش", "a:tut_view", "primary")]]
                kb.append([B("🧩 بخش‌بندی آموزش (تگ‌ها)", "a:secs", "success")])
                kb.append(back_btn("a:home"))
                return await self.edit(ev,
                    f"🎬 <b>آموزش فعال‌سازی</b>\n{self.LINE}\n"
                    f"وضعیت: {stat}\n{self.LINE}\n"
                    "وقتی کاربر دکمه‌ی «📚 آموزش فعال‌سازی» را بزند، این محتوا "
                    "<b>کپی‌شده</b> (بدون هدر فوروارد) برایش ارسال می‌شود.\n\n"
                    "<b>هر چیزی قابل ثبت است:</b> متن، لینک، عکس، ویدیو، ویس، "
                    "فایل، استیکر، آلبوم — به ترتیبی که می‌خواهی کاربر ببیند.\n\n"
                    "«➕ افزودن به محتوا» = پیام‌های تازه <b>به آخرِ</b> همین‌ها "
                    "اضافه می‌شوند (قبلی‌ها سر جایشان می‌مانند).\n"
                    "«📦 مدیریت محتوا» = فهرستِ دانه‌دانه؛ هر ویدیو/متن/ویس را "
                    "خواستی جدا پاک کن.\n\n"
                    "<i>محتوا در چتِ خودت با ربات نگه داشته می‌شود؛ "
                    "پیام‌هایش را پاک نکن.</i>", kb)
            if k == "tut_set" or k == "tut_add":
                mode, had = self.tut_capture_start(uid, "tut_set",
                                                   append=(k == "tut_add"))
                done = B("✅ تمام شد — ذخیره", "a:tut_done", "success")
                if mode == "append":
                    return await self.edit(ev,
                        f"➕ <b>افزودن به محتوای آموزش فعال‌سازی</b>\n{self.LINE}\n"
                        f"📦 {_fa_digits(had)} پیام قبلی <b>سر جایش می‌ماند</b>؛ "
                        "هرچه الان بفرستی به <b>آخرِ</b> همان‌ها اضافه می‌شود.\n\n"
                        "ویدیو/عکس/ویس/متن را همین‌جا بفرست — چند پیام "
                        "پشت‌سرهم هم اشکال ندارد.\n"
                        "تمام شد؟ «✅ تمام شد — ذخیره» را بزن.\n\n"
                        "<i>هر دکمه‌ی دیگر = لغو (چیزی ذخیره یا پاک نمی‌شود)</i>",
                        [[done], [B("⬅️ بازگشت", "a:tut")]])
                return await self.edit(ev,
                    f"📤 <b>ثبت محتوای آموزش فعال‌سازی</b>\n{self.LINE}\n"
                    + (f"⚠️ {_fa_digits(had)} پیامِ ثبت‌شده <b>جایگزین</b> می‌شود؛ "
                       "اگر می‌خواهی قبلی‌ها بمانند «➕ افزودن به محتوا» را بزن.\n\n"
                       if had else "")
                    + "محتوا را <b>همین‌جا</b> بفرست — هر چیزی:\n"
                    "• 📝 متن و لینک\n"
                    "• 🖼 عکس / 🎬 ویدیو / 🎤 ویس / 📎 فایل / 🎨 استیکر\n"
                    "• 🖼🖼 آلبوم (چند مدیا با هم)\n\n"
                    "هر پیام به ترتیب ثبت می‌شود؛ چند پیام پشت‌سرهم هم اشکال ندارد.\n"
                    "تمام شد؟ دکمه‌ی «✅ تمام شد» را بزن.\n\n"
                    "<i>/cancel برای لغو</i>",
                    [[done], [B("⬅️ بازگشت", "a:tut")]])
            if k == "tut_items":
                return await self.tut_admin_content(ev)
            if k.startswith("tut_di:") or k == "tut_dall":
                if k == "tut_dall":
                    self.tut_content_clear("tut_set")
                    self.db.log(uid, "tut_items_del", "همه")
                    return await self.edit(ev,
                        "🗑 همه‌ی محتوای آموزش فعال‌سازی پاک شد.\n"
                        "از این به بعد متن پیش‌فرض برای کاربر می‌رود.",
                        [[B("📤 ثبت محتوا", "a:tut_set", "success")],
                         [B("⬅️ بازگشت", "a:tut")]])
                idx = int(digits(k.split(":")[-1]) or -1)
                left = self.tut_content_del("tut_set", 0, idx)
                if left is None:
                    return await self.edit(ev, "این آیتم پیدا نشد.",
                                           [[B("📦 مدیریت محتوا", "a:tut_items",
                                               "primary")],
                                            [B("⬅️ بازگشت", "a:tut")]])
                self.db.log(uid, "tut_item_del", f"#{idx}")
                await self.say(uid,
                    f"🗑 آن آیتم پاک شد.\n📦 {_fa_digits(left)} پیام باقی ماند.",
                    key=f"tut:del:{left}:{int(time.time())}")
                return await self.tut_admin_content(ev)
            if k == "tut_done":
                st_tut = self.fsm.get(uid) or {}
                mode = st_tut.get("mode") or "replace"
                pend = st_tut.get("tut_pending") or []
                if not pend:
                    return await self.edit(ev,
                        "❌ هنوز پیامی ثبت نشده.\n"
                        "اول محتوا را بفرست، بعد «✅ تمام شد» را بزن.",
                        [[B("✅ تمام شد — ذخیره", "a:tut_done", "success")],
                         [B("⬅️ بازگشت", "a:tut")]])
                self.fsm.pop(uid, None)
                _c0, ids0 = self.tut_src()
                had = 0 if mode == "append" else len(ids0 or [])
                self.cfg["tut_chat"] = st_tut.get("tut_chat") or uid
                self.cfg["tut_ids"] = pend
                self.cfg.save()
                self.db.log(uid, "tut_set", f"{len(pend)} پیام ({mode})")
                return await self.edit(ev,
                    f"✅ <b>آموزش فعال‌سازی ذخیره شد</b>\n"
                    + (f"➕ {_fa_digits(had)} پیام قبلی ماند و "
                       f"{_fa_digits(len(pend) - had)} پیام تازه به آخرش اضافه شد.\n"
                       if mode == "append" and len(pend) > had else "")
                    + f"📦 مجموع: {_fa_digits(len(pend))} پیام.\n\n"
                    "از «👁 پیش‌نمایش» ببین کاربر دقیقاً چه می‌گیرد.",
                    [[B("👁 پیش‌نمایش", "a:tut_view", "primary")],
                     [B("🎬 صفحه‌ی آموزش", "a:tut")]])
            if k == "tut_view":
                await self.send_tutorial(uid)
                return await self.edit(ev,
                    "👁 <b>پیش‌نمایش</b>\n"
                    "محتوای فعلی برایت ارسال شد — پیام‌های همین چت را ببین.\n"
                    "<i>همین را کاربر می‌گیرد.</i>",
                    [[B("⬅️ بازگشت", "a:tut")]])
            if k == "tut_del":
                self.cfg["tut_chat"] = 0
                self.cfg["tut_ids"] = []
                self.cfg.save()
                self.db.log(uid, "tut_del", "")
                return await self.edit(ev,
                    "🗑 محتوای آموزش پاک شد.\n"
                    "از این به بعد متن پیش‌فرض برای کاربر می‌رود.",
                    [[B("📤 ثبت دوباره", "a:tut_set", "success")],
                     [B("⬅️ بازگشت", "a:tut")]])

            # ── بخش‌بندی آموزش (تگ‌ها) ──
            if k == "secs":
                return await self.tut_admin_list(ev)
            if k == "ver":
                return await self.version_status(ev)
            if k == "secs_h":
                return await self.tut_admin_history(ev)
            if k == "secs_h_all":
                added, total = cfg_restore_sections(None)
                self.db.log(uid, "cfg_restore_all", f"+{added}")
                self.cfg = Config()
                self.sup.cfg = self.cfg
                secs = self.tut_sections()
                return await self.edit(ev,
                    (f"✅ <b>{_fa_digits(added)} بخشِ گم‌شده برگشت</b>\n"
                     if added else
                     "ℹ️ بخشِ گم‌شده‌ای پیدا نشد.\n")
                    + f"🧩 حالا {_fa_digits(total)} بخش داری · "
                    f"{_fa_digits(sum(len(s['ids']) for s in secs))} پیامِ محتوا\n\n"
                    "<i>محتوای هر بخش به پیام‌های چتِ خودت با ربات اشاره دارد؛ "
                    "اگر آن پیام‌ها را در تلگرام پاک کرده باشی، باید دوباره "
                    "ثبتشان کنی (با «➕ افزودن به محتوا»).</i>",
                    [[B("🧩 بخش‌های آموزش", "a:secs", "success")],
                     [B("🕘 بازیابی بخش‌ها", "a:secs_h", "primary")],
                     back_btn("a:home")])
            if k == "secs_h_c" or k.startswith("secs_h_c:"):
                only = k.split(":", 1)[1] if ":" in k else None
                n, fixed = cfg_restore_section_content(only)
                if n:
                    self.db.log(uid, "cfg_restore_content",
                                f"+{n}" + (f" sid={only}" if only else ""))
                self.cfg = Config()
                self.sup.cfg = self.cfg
                secs = self.tut_sections()
                if n:
                    body = (f"✅ <b>محتوای {_fa_digits(n)} بخش برگشت</b>\n"
                            + "".join(f"• {self._esc(nm[:50])}: "
                                      + "، ".join(lbl for lbl in labels) + "\n"
                                      for nm, labels in fixed[:8]))
                else:
                    body = ("ℹ️ چیزی برای برگرداندن نبود — هر چه در تاریخچه "
                            "پُرتر است الان هم در بخش هست.\n")
                return await self.edit(ev,
                    body + f"\n🧩 {_fa_digits(len(secs))} بخش · "
                    f"{_fa_digits(sum(len(s['ids']) for s in secs))} پیامِ محتوا\n\n"
                    "<i>اگر پیامی برنگشت، یعنی در تلگرام پاک شده؛ همان را "
                    "دوباره با «➕ افزودن به محتوا» بفرست.</i>",
                    [[B("🧩 بخش‌های آموزش", "a:secs", "success")],
                     [B("🕘 بازیابی بخش‌ها", "a:secs_h", "primary")],
                     back_btn("a:home")])
            if k == "secs_h_zip":
                got = cfg_from_backup_zip()
                if not got:
                    return await self.edit(ev,
                        "❌ فایلِ پشتیبانی پیدا نشد "
                        "(<code>jafj_backup_latest.zip</code> در پوشه‌ی داده).",
                        [[B("🕘 بازیابی بخش‌ها", "a:secs_h", "primary")],
                         [B("⬅️ بازگشت", "a:secs")]])
                added, total = cfg_restore_sections(None, extra=True)
                fixed, detail = cfg_restore_section_content(None, extra=True)
                self.db.log(uid, "cfg_restore_zip", os.path.basename(got[1]))
                self.cfg = Config()
                self.sup.cfg = self.cfg
                secs = self.tut_sections()
                lines = [f"📦 <b>از <code>{self._esc(os.path.basename(got[1]))}</code> "
                         "بازیابی شد</b>"]
                lines.append(f"🧩 {_fa_digits(added)} بخشِ گم‌شده برگشت · "
                             f"📚 محتوای {_fa_digits(fixed)} بخش پُر شد")
                for nm, labels in detail[:6]:
                    lines.append(f"• {self._esc(nm[:40])}: " + "، ".join(labels))
                lines.append("")
                lines.append(f"حالا {_fa_digits(total)} بخش داری · "
                             f"{_fa_digits(sum(len(s['ids']) for s in secs))} "
                             "پیامِ محتوا")
                lines.append("")
                lines.append("<i>اگر چیزی برنگشت، یعنی در آن فایلِ پشتیبان هم "
                             "نبوده؛ همان را با «➕ افزودن به محتوا» دوباره "
                             "بفرست.</i>")
                return await self.edit(ev, "\n".join(lines),
                    [[B("🧩 بخش‌های آموزش", "a:secs", "success")],
                     [B("🕘 بازیابی بخش‌ها", "a:secs_h", "primary")],
                     back_btn("a:home")])
            if k.startswith("secs_h_rs:") or k.startswith("secs_h_rf:"):
                full = k.startswith("secs_h_rf:")
                fname = k.split(":", 1)[1]
                if not os.path.isfile(os.path.join(CFG_HISTORY_DIR, fname)):
                    return await self.edit(ev,
                        "❌ آن نسخه‌ی تاریخچه پیدا نشد (شاید چرخش خورده).",
                        [[B("🕘 بازیابی بخش‌ها", "a:secs_h", "primary")],
                         [B("⬅️ بازگشت", "a:secs")]])
                if full:
                    ok = cfg_restore_full(fname)
                    if not ok:
                        return await self.edit(ev,
                            "❌ بازیابیِ آن نسخه نشد (فایل سالم نیست).",
                            [[B("🕘 بازیابی بخش‌ها", "a:secs_h", "primary")],
                             [B("⬅️ بازگشت", "a:secs")]])
                    # کانفیگ از بیرون عوض شد → کلاس Config باید دوباره بخواند
                    self.cfg = Config()
                    self.sup.cfg = self.cfg
                    self.db.log(uid, "cfg_restore_full", fname)
                    secs = self.tut_sections()
                    return await self.edit(ev,
                        f"📥 <b>کل تنظیمات از <code>{fname}</code> برگشت</b>\n"
                        f"🧩 {_fa_digits(len(secs))} بخش · "
                        f"{_fa_digits(sum(len(s['ids']) for s in secs))} پیامِ محتوا\n\n"
                        "<i>اگر نتیجه درست نیست، همین‌جا نسخه‌ی دیگری را انتخاب کن "
                        "(قبل از بازیابی هم یک نسخه‌ی نجات گذاشته شد).</i>",
                        [[B("🧩 بخش‌های آموزش", "a:secs", "success")],
                         [B("🕘 بازیابی بخش‌ها", "a:secs_h", "primary")],
                         back_btn("a:home")])
                added, total = cfg_restore_sections(fname)
                self.db.log(uid, "cfg_restore_secs", f"{fname} +{added}")
                # بخش‌های گم‌شده‌ی نسخه‌های دیگر هم با دکمه‌ی «برگرداندنِ همه»
                # قابل برگرداندن‌اند؛ این دکمه فقط همان نسخه را می‌نشاند.
                self.cfg = Config()
                self.sup.cfg = self.cfg
                secs = self.tut_sections()
                return await self.edit(ev,
                    (f"✅ <b>{_fa_digits(added)} بخشِ گم‌شده برگشت</b>\n"
                     if added else
                     "ℹ️ بخشِ تازه‌ای برای برگرداندن نبود (همه هست یا آن نسخه "
                     "بخشی ندارد).\n")
                    + f"🧩 حالا {_fa_digits(total)} بخش داری · "
                    f"{_fa_digits(sum(len(s['ids']) for s in secs))} پیامِ محتوا\n\n"
                    "<i>محتوای هر بخش به پیام‌های چتِ خودت با ربات اشاره دارد؛ "
                    "اگر آن پیام‌ها را در تلگرام پاک کرده باشی، باید دوباره "
                    "ثبتشان کنی.</i>",
                    [[B("🧩 بخش‌های آموزش", "a:secs", "success")],
                     [B("🕘 بازیابی بخش‌ها", "a:secs_h", "primary")],
                     back_btn("a:home")])

            # ── 🗂 توضیحات: فهرستِ تپ‌کردنیِ مشتری ──
            if k == "hub":
                return await self.hub_admin(ev)
            if k == "hub_on":
                self.cfg["hub_on"] = not self.hub_on()
                self.db.log(uid, "hub_on", "1" if self.hub_on() else "0")
                return await self.hub_admin(ev)
            if k == "hub_def":
                self.cfg["hub_defaults"] = not self.hub_defaults_on()
                self.db.log(uid, "hub_defs",
                            "1" if self.hub_defaults_on() else "0")
                return await self.hub_admin(ev)
            if k == "hub_mk":
                made = await self.hub_make_sections()
                for s in made:
                    self.db.log(uid, "hub_mk", f"#{s['id']} {s['preset']}")
                return await self.edit(ev,
                    (f"✅ {_fa_digits(len(made))} مورد به بخش تبدیل شد:\n"
                     + "\n".join(f"• {self.tut_sec_label(s)}"
                                  for s in made)
                     + "\n\n<i>حالا از «🧩 بخش‌های آموزش» هر کدام را باز کن و "
                       "متنش را با «📝 متن بخش» به متنِ خودت عوض کن. "
                       "دکمه‌ی پایانش هم همان‌جاست.</i>"
                     if made else
                     "ℹ️ همه‌ی پیش‌فرض‌ها قبلاً به بخش تبدیل شده‌اند."),
                    [[B("🧩 بخش‌های آموزش", "a:secs", "success")],
                     back_btn("a:hub")])
            if k == "hub_pg":
                sizes = [4, 6, 8, 10, 12]
                cur = self.hub_page_size()
                nxt = sizes[(sizes.index(cur) + 1) % len(sizes)] \
                    if cur in sizes else 8
                self.cfg["hub_page_size"] = nxt
                self.db.log(uid, "hub_pg", str(nxt))
                return await self.hub_admin(ev)
            if k == "hub_p":
                await self.send_hub(uid)
                return await self.edit(ev,
                    "👁 <b>پیش‌نمایش فهرست</b>\n"
                    "همان چیزی که مشتری می‌بیند برایت ارسال شد.\n"
                    "<i>در پیش‌نمایش، تپِ هر مورد هم کار می‌کند.</i>",
                    [back_btn("a:hub")])
            if k == "hub_all":
                n = await self.hub_send_all(uid)
                return await self.edit(ev,
                    f"📤 {_fa_digits(n)} مورد پشت‌سرهم فرستاده شد.",
                    [back_btn("a:hub")])
            if k == "hub_i":
                cur_txt = str(self.cfg.get("hub_intro") or "").strip()
                self.fsm[uid] = {"step": "hub_intro"}
                return await self.edit(ev,
                    f"📝 <b>متن بالای «🗂 توضیحات»</b>\n{self.LINE}\n"
                    "این متن اولِ فهرست نشان داده می‌شود — مثلاً یک جمله "
                    "درباره‌ی اینکه هر آموزش را بزن تا بیاید.\n\n"
                    + (f"فعلی: {self._esc(cur_txt)}\n\n" if cur_txt else "")
                    + "متن جدید را بفرست؛ برای برگشت به متن پیش‌فرض بنویس: "
                    "<code>-</code>\n"
                    "<i>/cancel برای لغو</i>",
                    [back_btn("a:hub")])
            if k.startswith("hub_t:"):
                sid = int(digits(k.split(":")[-1]) or 0)
                s = self.tut_find(sid)
                if not s:
                    return await self.edit(ev, "این بخش پیدا نشد.",
                                           [back_btn("a:hub")])
                new_val = not bool(s.get("in_hub", True))
                self.tut_update(sid, in_hub=new_val)
                self.db.log(uid, "hub_sec", f"#{sid} {int(new_val)}")
                return await self.hub_admin(ev)
            # ── سه متنِ آماده: کیف پول / خرید امتیاز / بعد از فعال‌سازی ──
            if k == "sec_tpl":
                kb = []
                for key, d in self.TUT_PRESETS:
                    have = self.tut_find_preset(key)
                    kb.append([B(("✅ " if have else "➕ ") + self.tut_preset_label(key),
                                 f"a:sec:{have['id']}" if have else f"a:sec_tpl_one:{key}",
                                 "primary" if have else "success")])
                missing = [k2 for k2, _ in self.TUT_PRESETS if not self.tut_find_preset(k2)]
                if len(missing) > 1:
                    kb.append([B(f"⚡️ ساختن هر {_fa_digits(len(missing))} تا با هم",
                                 "a:sec_tpl_all", "success")])
                kb.append(back_btn("a:secs"))
                return await self.edit(ev,
                    f"📝 <b>متن‌های آماده‌ی آموزش</b>\n{self.LINE}\n"
                    "چهار بخشِ آماده — با یک دکمه ساخته می‌شود؛ متن، زمان ارسال و "
                    "دکمه‌ی پایان از قبل تنظیم است:\n\n"
                    "💳 <b>کیف پول</b> — بعد از شارژ کیف پول (خودکار) · دکمه‌ی «💳 شارژ کیف پول»\n"
                    "🎯 <b>خرید امتیاز</b> — بعد از تأیید خرید امتیاز (خودکار) · دکمه‌ی «🎯 خرید امتیاز»\n"
                    "💎 <b>اشتراک ماهانه</b> — بعد از تأیید اشتراک (خودکار) · دکمه‌ی «💎 اشتراک ماهانه»\n"
                    "🚀 <b>بعد از فعال‌سازی</b> — بعد از فعال‌شدن سلف (خودکار) · دکمه‌ی «⚙️ سرویس من»\n\n"
                    "دکمه‌های «📚 آموزش …» آخرِ منوهای کیف پول / خرید امتیاز / اشتراک "
                    "ماهانه هم همین متن‌ها را می‌فرستند.\n"
                    "اعدادِ متن (حداقل شارژ، امتیاز هر ساعت…) از تنظیماتِ فعلی پر می‌شود.\n"
                    "<i>بعد از ساختن، هر چیزی را می‌توانی از صفحه‌ی بخش عوض کنی.</i>",
                    kb)
            if k.startswith("sec_tpl_one:"):
                key = k.split(":", 1)[1]
                s, created = self.tut_new_preset(key)
                if not s:
                    return await self.edit(ev, "این متن آماده پیدا نشد.",
                                           [back_btn("a:sec_tpl")])
                if created:
                    self.db.log(uid, "sec_tpl", f"#{s['id']} {key}")
                return await self.edit(ev,
                    (f"✅ بخش ساخته شد: <b>{self.tut_sec_label(s)}</b>\n\n"
                     if created else
                     f"ℹ️ این بخش قبلاً ساخته شده: <b>{self.tut_sec_label(s)}</b>\n\n")
                    + f"🎛 {self.tut_when_label(s['when'])}\n"
                    f"🔚 دکمه‌ی پایان: {s['btn_label']}\n\n"
                    "با «👁 پیش‌نمایش» ببین کاربر دقیقاً چه می‌گیرد.",
                    [[B("👁 پیش‌نمایش", f"a:sec_vw:{s['id']}", "primary"),
                      B("🧩 باز کردن بخش", f"a:sec:{s['id']}", "success")],
                     back_btn("a:sec_tpl")])
            if k == "sec_tpl_all":
                made = self.tut_new_all_presets()
                for s in made:
                    self.db.log(uid, "sec_tpl", f"#{s['id']} {s['preset']}")
                return await self.edit(ev,
                    (f"✅ {_fa_digits(len(made))} بخش ساخته شد:\n"
                     + "\n".join(f"• {self.tut_sec_label(s)} — {self.tut_when_label(s['when'])}"
                                 for s in made)
                     if made else "ℹ️ هر سه بخش قبلاً ساخته شده بود.")
                    + "\n\n<i>هر کدام را از «🧩 بخش‌های آموزش» باز کن و اگر خواستی تغییر بده.</i>",
                    [back_btn("a:secs")])
            if k.startswith("sec_tpl_rst:"):
                sid = int(digits(k.split(":", 1)[1]) or 0)
                s = self.tut_find(sid)
                if not s or not s.get("preset"):
                    return await self.edit(ev, "این بخش متن آماده ندارد.",
                                           [back_btn("a:secs")])
                self.tut_update(sid, text="")
                return await self.edit(ev,
                    f"♻️ متنِ بخش به متن آماده‌ی {self.tut_preset_label(s['preset'])} برگشت.",
                    [[B("👁 پیش‌نمایش", f"a:sec_vw:{sid}", "primary"),
                      B("⬅️ بخش", f"a:sec:{sid}")]])
            if k.startswith("sec_txt:"):
                sid = int(digits(k[8:]) or 0)
                s = self.tut_find(sid)
                if not s:
                    return await self.edit(ev, "این بخش پیدا نشد.",
                                           [back_btn("a:secs")])
                self.fsm[uid] = {"step": "sec_text", "sec_id": sid}
                cur = self.tut_body_text(s)
                return await self.edit(ev,
                    f"📝 <b>متن بخش — {s['name']}</b>\n{self.LINE}\n"
                    "متنِ آموزش را همین‌جا بفرست (بولد/لینک تلگرام حفظ می‌شود). "
                    "این متن بعد از پیام‌های ثبت‌شده و قبل از دکمه‌ی پایان می‌رود.\n\n"
                    + (f"فعلی: {_fa_digits(len(cur))} حرف\n\n" if cur else "")
                    + "برای حذف بنویس: <code>خاموش</code>\n\n"
                    "<i>/cancel برای لغو</i>",
                    [[B("⬅️ بخش", f"a:sec:{sid}")]])
            if k == "sec_add":
                s = self.tut_new()
                if not s:
                    return await self.edit(ev, "ساخت بخش نشد.",
                                           [back_btn("a:secs")])
                self.db.log(uid, "sec_new", f"#{s['id']}")
                return await self.edit(ev,
                    f"✅ بخش جدید ساخته شد: <b>{self.tut_sec_label(s)}</b>\n\n"
                    "حالا سه کار:\n"
                    "1️⃣ «📤 ثبت / تغییر محتوا» → ویدیو/عکس/متنِ آموزش را بفرست\n"
                    "2️⃣ «🎛 زمان ارسال» → مثلاً بعد از فعال‌سازی سلف (خودکار)\n"
                    "3️⃣ «🔚 دکمه‌ی پایان بخش» → مثلاً «💳 شارژ کیف پول»\n\n"
                    "<i>اسم بخش را هم با «🏷 نام بخش» عوض کن.</i>\n"
                    "<i>یا به‌جای این‌ها، از «📝 متن‌های آماده» یکی را بردار.</i>",
                    [[B("🧩 باز کردن بخش", f"a:sec:{s['id']}", "success")],
                     [B("📝 متن‌های آماده", "a:sec_tpl", "primary")],
                     back_btn("a:secs")])
            if k.startswith("sec:"):
                return await self.tut_admin_one(ev, int(digits(k[4:]) or 0))
            if k.startswith("sec_when:"):
                return await self.tut_admin_when(ev, int(digits(k[9:]) or 0))
            if k.startswith("sec_btn:"):
                return await self.tut_admin_btn(ev, int(digits(k[8:]) or 0))
            if k.startswith("sec_w:"):
                parts = k.split(":")
                sid = int(digits(parts[1]) or 0)
                when = parts[2] if len(parts) > 2 else ""
                s = self.tut_find(sid)
                if not s:
                    return await self.edit(ev, "این بخش پیدا نشد.",
                                           [back_btn("a:secs")])
                self.tut_update(sid, when=when)
                self.db.log(uid, "sec_when", f"#{sid} {when}")
                return await self.tut_admin_one(ev, sid)
            if k.startswith("sec_b:"):
                parts = k.split(":")
                sid = int(digits(parts[1]) or 0)
                cmd = ":".join(parts[2:])
                s = self.tut_find(sid)
                if not s:
                    return await self.edit(ev, "این بخش پیدا نشد.",
                                           [back_btn("a:secs")])
                label = s["btn_label"] or dict(self.TUT_TARGETS).get(cmd, "ادامه")
                self.tut_update(sid, btn_cmd=cmd, btn_label=label)
                self.db.log(uid, "sec_btn", f"#{sid} {cmd}")
                return await self.tut_admin_btn(ev, sid)
            if k.startswith("sec_burl:"):
                sid = int(digits(k[8:]) or 0)
                if not self.tut_find(sid):
                    return await self.edit(ev, "این بخش پیدا نشد.",
                                           [back_btn("a:secs")])
                self.fsm[uid] = {"step": "sec_btn_url", "sec_id": sid}
                return await self.edit(ev,
                    f"🔗 <b>دکمه‌ی لینک</b>\n{self.LINE}\n"
                    "لینک را بفرست — مثل:\n"
                    "<code>https://t.me/mychannel</code>\n\n"
                    "<i>/cancel برای لغو</i>",
                    [[B("⬅️ بخش", f"a:sec:{sid}")]])
            if k.startswith("sec_bdel:"):
                sid = int(digits(k[9:]) or 0)
                self.tut_update(sid, btn_cmd="", btn_label="")
                return await self.tut_admin_btn(ev, sid)
            if k.startswith("sec_bl:"):
                sid = int(digits(k[7:]) or 0)
                s = self.tut_find(sid)
                if not s:
                    return await self.edit(ev, "این بخش پیدا نشد.",
                                           [back_btn("a:secs")])
                if not s["btn_cmd"]:
                    return await self.edit(ev,
                        "اول با «🔚 دکمه‌ی پایان بخش» یک دکمه انتخاب کن، "
                        "بعد متنش را عوض کن.", [back_btn(f"a:sec:{sid}")])
                self.fsm[uid] = {"step": "sec_btn_label", "sec_id": sid}
                return await self.edit(ev,
                    f"✏️ <b>متن دکمه</b>\n{self.LINE}\n"
                    f"فعلی: <b>{s['btn_label'] or '—'}</b>\n\n"
                    "متن جدید را بفرست (مثلاً: <code>💳 شارژ کیف پول</code>)\n\n"
                    "<i>/cancel برای لغو</i>",
                    [[B("⬅️ بخش", f"a:sec:{sid}")]])
            if k.startswith("sec_rn:"):
                sid = int(digits(k[7:]) or 0)
                if not self.tut_find(sid):
                    return await self.edit(ev, "این بخش پیدا نشد.",
                                           [back_btn("a:secs")])
                self.fsm[uid] = {"step": "sec_name", "sec_id": sid}
                return await self.edit(ev,
                    f"🏷 <b>نام بخش</b>\n{self.LINE}\n"
                    "اسمی که کاربر روی دکمه می‌بیند را بفرست.\n"
                    "مثال: <code>آموزش کامل پنل جفج</code>\n\n"
                    "<i>/cancel برای لغو</i>",
                    [[B("⬅️ بخش", f"a:sec:{sid}")]])
            if k.startswith("sec_em:"):
                sid = int(digits(k[7:]) or 0)
                if not self.tut_find(sid):
                    return await self.edit(ev, "این بخش پیدا نشد.",
                                           [back_btn("a:secs")])
                self.fsm[uid] = {"step": "sec_emoji", "sec_id": sid}
                return await self.edit(ev,
                    f"🎨 <b>ایموجی بخش</b>\n{self.LINE}\n"
                    "یک ایموجی بفرست؛ مثل: 🎬 💳 🎯 💎 📚\n\n"
                    "<i>/cancel برای لغو</i>",
                    [[B("⬅️ بخش", f"a:sec:{sid}")]])
            if k.startswith("sec_dly:"):
                sid = int(digits(k[8:]) or 0)
                if not self.tut_find(sid):
                    return await self.edit(ev, "این بخش پیدا نشد.",
                                           [back_btn("a:secs")])
                self.fsm[uid] = {"step": "sec_delay", "sec_id": sid}
                return await self.edit(ev,
                    f"⏱ <b>فاصله‌ی بخش</b>\n{self.LINE}\n"
                    "چند ثانیه <b>بعد از بخش قبلی</b> ارسال شود؟\n"
                    "مثال: <code>0</code> (درجا) یا <code>60</code> (یک دقیقه بعد)\n\n"
                    "<i>/cancel برای لغو</i>",
                    [[B("⬅️ بخش", f"a:sec:{sid}")]])
            if k.startswith("sec_note:"):
                sid = int(digits(k[9:]) or 0)
                if not self.tut_find(sid):
                    return await self.edit(ev, "این بخش پیدا نشد.",
                                           [back_btn("a:secs")])
                self.fsm[uid] = {"step": "sec_note", "sec_id": sid}
                return await self.edit(ev,
                    f"📝 <b>متن پایان بخش</b>\n{self.LINE}\n"
                    "این متن <b>آخرِ</b> محتوای بخش، همراه دکمه‌ی پایان می‌رود.\n"
                    "مثال: <code>برای شارژ کیف پول دکمه‌ی زیر را بزن 👇</code>\n\n"
                    "برای حذف بنویس: <code>خاموش</code>\n\n"
                    "<i>/cancel برای لغو</i>",
                    [[B("⬅️ بخش", f"a:sec:{sid}")]])
            if k.startswith("sec_up:") or k.startswith("sec_dn:"):
                up = k.startswith("sec_up:")
                sid = int(digits(k.split(":", 1)[1]) or 0)
                self.tut_move(sid, -1 if up else 1)
                return await self.tut_admin_one(ev, sid)
            if k.startswith("sec_once:") or k.startswith("sec_hdr:") or \
                    k.startswith("sec_on:") or k.startswith("sec_hub:"):
                key, sid_s = k.split(":", 1)
                sid = int(digits(sid_s) or 0)
                s = self.tut_find(sid)
                if not s:
                    return await self.edit(ev, "این بخش پیدا نشد.",
                                           [back_btn("a:secs")])
                field = {"sec_once": "once", "sec_hdr": "header",
                         "sec_on": "on", "sec_hub": "in_hub"}[key]
                self.tut_update(sid, **{field: not s[field]})
                return await self.tut_admin_one(ev, sid)
            if k.startswith("sec_clr:"):
                sid = int(digits(k[8:]) or 0)
                self.tut_update(sid, chat=0, ids=[])
                self.db.log(uid, "sec_clr", f"#{sid}")
                return await self.edit(ev,
                    "🗑 محتوای این بخش پاک شد.",
                    [[B("⬅️ بخش", f"a:sec:{sid}")], back_btn("a:secs")])
            if k.startswith("sec_vw:"):
                sid = int(digits(k[7:]) or 0)
                s = self.tut_find(sid)
                if not s:
                    return await self.edit(ev, "این بخش پیدا نشد.",
                                           [back_btn("a:secs")])
                ok = await self.tut_send_section(uid, sid, force=True)
                return await self.edit(ev,
                    ("👁 <b>پیش‌نمایش</b>\n همین را کاربر می‌گیرد — "
                     "پیام‌های همین چت را ببین."
                     if ok else
                     "⚠️ این بخش محتوایی ندارد.\nبا «📤 ثبت محتوا» پیام‌ها را بفرست."),
                    [[B("⬅️ بخش", f"a:sec:{sid}")]])
            if k.startswith("sec_rm:"):
                sid = int(digits(k[7:]) or 0)
                s = self.tut_find(sid)
                if not s:
                    return await self.edit(ev, "این بخش پیدا نشد.",
                                           [back_btn("a:secs")])
                return await self.edit(ev,
                    f"🗑 بخش <b>{s['name']}</b> پاک شود؟\n"
                    "<i>محتوای داخل تلگرام پاک نمی‌شود؛ فقط این بخش از پنل.</i>",
                    [[B("✅ بله، پاک کن", f"a:sec_rm_y:{sid}", "danger")],
                     [B("⬅️ نه", f"a:sec:{sid}")]])
            if k.startswith("sec_rm_y:"):
                sid = int(digits(k[9:]) or 0)
                self.tut_remove(sid)
                self.db.log(uid, "sec_rm", f"#{sid}")
                return await self.edit(ev, "🗑 بخش حذف شد.",
                                       [back_btn("a:secs")])
            if k == "tut_auto":
                on = not bool(self.cfg.get("tut_auto", True))
                self.cfg["tut_auto"] = on
                self.cfg.save()
                secs = [s for s in self.tut_sections(on_only=True)
                        if s["when"] == "after_run"]
                return await self.edit(ev,
                    f"⚙️ <b>ارسال خودکار بعد از فعال‌سازی</b>\n{self.LINE}\n"
                    f"وضعیت: {'🟢 روشن' if on else '🔴 خاموش'}\n"
                    f"⏱ تأخیر: {_fa_digits(self.cfg.get('tut_auto_wait', 8))} ثانیه\n"
                    f"🧩 بخش‌های این رویداد: {_fa_digits(len(secs))}\n\n"
                    "وقتی کاربر سلف را روی اکانتش روشن کند، این بخش‌ها خودکار "
                    "برای او می‌روند (هر بخش با فاصله‌ی خودش).",
                    [[B("🔴 خاموش کن" if on else "🟢 روشن کن", "a:tut_auto",
                        "danger" if on else "success")],
                     [B("⏱ تغییر تأخیر", "a:tut_wait", "primary")],
                     back_btn("a:secs")])
            if k == "tut_wait":
                self.fsm[uid] = {"step": "tut_wait"}
                return await self.edit(ev,
                    f"⏱ <b>تأخیر ارسال خودکار</b>\n{self.LINE}\n"
                    "چند ثانیه بعد از پیام «راه‌اندازی شد»، بخش‌ها شروع شوند؟\n"
                    "فعلی: {0} ثانیه\n\n"
                    "مثال: <code>8</code>\n\n"
                    "<i>/cancel برای لغو</i>".format(
                        _fa_digits(self.cfg.get("tut_auto_wait", 8))),
                    [[B("⬅️ بازگشت", "a:tut_auto")]])
            if k.startswith("sec_done"):
                st_sec = self.fsm.get(uid) or {}
                sid = int(st_sec.get("sec_id") or 0)
                mode = st_sec.get("mode") or "replace"
                pend = list(st_sec.get("tut_pending") or [])
                kb_back = ([[B("🧩 همان بخش", f"a:sec:{sid}", "success")]]
                           if sid else [])
                kb_back.append(back_btn("a:secs"))
                if not sid:
                    return await self.edit(ev, "بخشی انتخاب نشده بود.", kb_back)
                if not pend:
                    kb = [[B("✅ تمام شد — ذخیره", f"a:sec_done:{sid}", "success")],
                          back_btn(f"a:sec:{sid}")]
                    return await self.edit(ev,
                        "❌ هنوز پیامی ثبت نشده.\n"
                        "اول محتوا را بفرست (ویدیو، عکس، متن…)، بعد «✅ تمام شد».",
                        kb)
                self.fsm.pop(uid, None)
                s_before = self.tut_find(sid) or {}
                had = 0 if mode == "append" else len(s_before.get("ids") or [])
                chat = int(st_sec.get("tut_chat") or uid)
                self.tut_update(sid, chat=chat, ids=pend)
                self.db.log(uid, "sec_set", f"#{sid} {len(pend)} پیام ({mode})")
                s = self.tut_find(sid) or {"name": "", "id": sid}
                return await self.edit(ev,
                    f"✅ <b>محتوای بخش ذخیره شد</b>\n{self.LINE}\n"
                    f"🧩 {s.get('name')}\n"
                    + (f"➕ {_fa_digits(had)} پیام قبلی ماند و "
                       f"{_fa_digits(len(pend) - had)} پیام تازه به آخرش اضافه شد.\n"
                       if mode == "append" and len(pend) > had else "")
                    + f"📦 مجموع: {_fa_digits(len(pend))} پیام.\n\n"
                    "از «👁 پیش‌نمایش» ببین کاربر دقیقاً چه می‌گیرد؛\n"
                    "با «📦 مدیریت محتوا» هم می‌توانی هر کدام را جدا پاک کنی.",
                    [[B("👁 پیش‌نمایش", f"a:sec_vw:{sid}", "primary")],
                     [B("📦 مدیریت محتوا", f"a:sec_items:{sid}", "primary")],
                     [B("🎛 زمان ارسال", f"a:sec_when:{sid}", "primary")],
                     back_btn("a:secs")])
            if k.startswith("sec_add:") or k.startswith("sec_set:"):
                append = k.startswith("sec_add:")
                sid = int(digits(k.split(":", 1)[1]) or 0)
                s = self.tut_find(sid)
                if not s:
                    return await self.edit(ev, "این بخش پیدا نشد.",
                                           [back_btn("a:secs")])
                mode, had = self.tut_capture_start(uid, "sec_set", sid=sid,
                                                   append=append)
                done = B("✅ تمام شد — ذخیره", f"a:sec_done:{sid}", "success")
                if mode == "append":
                    return await self.edit(ev,
                        f"➕ <b>افزودن به محتوای «{s['name']}»</b>\n{self.LINE}\n"
                        f"📦 {_fa_digits(had)} پیام قبلی <b>سر جایش می‌ماند</b>؛ "
                        "هرچه الان بفرستی به <b>آخرِ</b> همان‌ها اضافه می‌شود.\n\n"
                        "ویدیو/عکس/ویس/متن را همین‌جا بفرست — چند پیام "
                        "پشت‌سرهم هم اشکال ندارد.\n"
                        "تمام شد؟ «✅ تمام شد — ذخیره» را بزن.\n\n"
                        "<i>هر دکمه‌ی دیگر = لغو (چیزی ذخیره یا پاک نمی‌شود)</i>",
                        [[done], [B("⬅️ بخش", f"a:sec:{sid}")]])
                return await self.edit(ev,
                    f"📤 <b>ثبت محتوای «{s['name']}»</b>\n{self.LINE}\n"
                    + (f"⚠️ {_fa_digits(had)} پیامِ ثبت‌شده <b>جایگزین</b> می‌شود؛ "
                       "اگر می‌خواهی قبلی‌ها بمانند «➕ افزودن به محتوا» را بزن.\n\n"
                       if had else "")
                    + "محتوا را <b>همین‌جا</b> بفرست — هر چیزی:\n"
                    "• 📝 متن و لینک\n"
                    "• 🎬 ویدیو / 🖼 عکس / 🎤 ویس / 📎 فایل / 🎨 استیکر\n"
                    "• 🖼🖼 آلبوم (چند مدیا با هم)\n\n"
                    "به همان ترتیبی که می‌فرستی، برای کاربر می‌رود؛ "
                    "متن و کپشن‌ها دست‌نخورده می‌مانند.\n"
                    "تمام شد؟ «✅ تمام شد — ذخیره» را بزن.\n\n"
                    "<i>هر دکمه‌ی دیگر = لغو</i>",
                    [[done], [B("⬅️ بخش", f"a:sec:{sid}")]])
            if k.startswith("sec_items:"):
                sid = int(digits(k.split(":", 1)[1]) or 0)
                return await self.tut_admin_items(ev, sid)
            if k.startswith("sec_di:") or k.startswith("sec_dall:"):
                sid = int(digits(k.split(":")[1]) or 0)
                if not self.tut_find(sid):
                    return await self.edit(ev, "این بخش پیدا نشد.",
                                           [back_btn("a:secs")])
                if k.startswith("sec_dall:"):
                    self.tut_content_clear("sec_set", sid)
                    self.db.log(uid, "sec_items_del", f"#{sid} همه")
                    return await self.edit(ev,
                        f"🗑 همه‌ی محتوای «{self.tut_sec_label(self.tut_find(sid))}» "
                        "پاک شد.",
                        [[B("➕ افزودن به محتوا", f"a:sec_add:{sid}", "success")],
                         [B("⬅️ بخش", f"a:sec:{sid}")], back_btn("a:secs")])
                parts = k.split(":")
                idx = int(digits(parts[2]) if len(parts) > 2 else -1)
                left = self.tut_content_del("sec_set", sid, idx)
                if left is None:
                    return await self.edit(ev, "این آیتم پیدا نشد.",
                                           [[B("📦 مدیریت محتوا",
                                               f"a:sec_items:{sid}", "primary")],
                                            [B("⬅️ بخش", f"a:sec:{sid}")]])
                self.db.log(uid, "sec_item_del", f"#{sid} آیتم {idx}")
                await self.say(uid,
                    f"🗑 آن آیتم پاک شد.\n📦 {_fa_digits(left)} پیام باقی ماند.",
                    key=f"sec:del:{sid}:{left}:{int(time.time())}")
                return await self.tut_admin_items(ev, sid)
            if k == "fjoin":
                rows = self.force_chans()
                txt = [f"📣 <b>جوین اجباری</b>", self.LINE,
                       "بات باید در کانال <b>ادمین</b> باشد تا عضویت دقیق چک شود.",
                       "اگر کاربر لفت بدهد، دفعه بعد دوباره قفل می‌شود.",
                       self.LINE]
                kb = []
                if not rows:
                    txt.append("<i>هنوز کانالی ثبت نشده.</i>")
                for i, ch in enumerate(rows):
                    title = ch.get("title") or ch.get("user") or str(ch.get("id"))
                    un = ch.get("user") or "—"
                    txt.append(f"{_fa_digits(i + 1)}. <b>{title}</b>  (@{str(un).lstrip('@')})")
                    kb.append([B(f"🗑 حذف {title[:18]}", f"a:frm:{i}", "danger")])
                kb.insert(0, [B("➕ افزودن کانال", "a:fadd", "success")])
                kb.append([B("🔄 بررسی ادمین بودن بات", "a:fchk", "primary")])
                kb.append(back_btn("a:home"))
                return await self.edit(ev, "\n".join(txt), kb)
            if k == "fadd":
                self.fsm[uid] = {"step": "fjoin_add"}
                return await self.edit(ev,
                    f"📣 <b>افزودن کانال جوین اجباری</b>\n{self.LINE}\n"
                    "یوزرنیم کانال را بفرست، مثل:\n"
                    "<code>@mychannel</code>\n\n"
                    "بات را از قبل در آن کانال <b>ادمین</b> کن.\n"
                    "<i>/cancel برای لغو</i>",
                    [back_btn("a:fjoin")])
            if k == "fchk":
                lines = [f"🩺 <b>وضعیت بات در کانال‌ها</b>", self.LINE]
                for ch in self.force_chans():
                    ent = ch.get("id") or ch.get("user")
                    ok = await self.bot_admin_in(ent)
                    title = ch.get("title") or ch.get("user") or ent
                    lines.append(("✅ ادمین است — " if ok else "❌ ادمین نیست — ") + str(title))
                if len(lines) == 2:
                    lines.append("کانالی نیست.")
                return await self.edit(ev, "\n".join(lines),
                                       [[B("📣 جوین اجباری", "a:fjoin", "danger")],
                                        back_btn("a:home")])
            if k.startswith("frm:"):
                idx = int(digits(k.split(":")[-1]) or 0)
                rows = self.force_chans()
                if 0 <= idx < len(rows):
                    rows.pop(idx)
                    self.save_force_chans(rows)
                    self._join_ok.clear()
                ev.data = b"a:fjoin"
                return await self.on_callback(ev)
            if k == "card":
                self.fsm[uid] = {"step": "card_set"}
                return await self.edit(ev,
                    f"💳 <b>شماره کارت</b>\n{self.LINE}\n"
                    f"فعلی: <code>{self.cfg['card_number'] or '—'}</code>\n"
                    f"به نام: {self.cfg['card_name'] or '—'}\n\n"
                    "یک خط بفرست:\n"
                    "<code>6037991234567890 علی رضایی</code>\n\n"
                    "<i>/cancel برای لغو</i>",
                    [back_btn("a:home")])
            if k in ("backup", "backup:dl"):
                ok, msg = await self.send_backup_to_admin(ev.chat_id)
                st_line = ("✅ <b>فایل بک‌آپ همین الان برایت ارسال شد</b>\n" if ok else "❌ ") + str(msg)
                t, kb = self.backup_screen(status_line=st_line)
                return await self.edit(ev, t, kb)
            if k == "backup:auto":
                now_auto = not bool(self.cfg.get("auto_backup_on", True))
                self.cfg["auto_backup_on"] = now_auto
                self.cfg.save()
                self.db.log(uid, "backup_auto", "on" if now_auto else "off")
                st_line = (
                    "🟢 بک‌آپ خودکار روشن شد — فقط زمانی که اطلاعات جدیدی ثبت شود بک‌آپ می‌گیرد."
                    if now_auto else
                    "🔴 بک‌آپ خودکار خاموش شد — فقط زمانی که دکمه‌ی «📦 بک‌آپ» را بزنی بک‌آپ می‌دهد."
                )
                t, kb = self.backup_screen(status_line=st_line)
                return await self.edit(ev, t, kb)
            if k == "restore":
                ok, msg = await self.restore_from_backup(force=True)
                text = ("✅ " if ok else "❌ ") + str(msg)
                if not ok:
                    text += ("\n\n💡 اگر «پشتیبانی پیدا نشد» داد، روی همان پیامِ "
                             "پشتیبان در تلگرام <b>ریپلای</b> کن و بنویس "
                             "<code>.restore</code> — یا آیدی همان پیام را بفرست: "
                             "<code>.restore 12345</code>")
                return await self.edit(ev, text,
                                       [[B("📦 مدیریت بک‌آپ", "a:backup", "primary")],
                                        back_btn("a:home")])
            if k == "diag":
                return await self.edit(ev, self.diag_text(), [back_btn("a:home")])
            if k == "onall":
                # «روشن کردن همه» — همان کاری که بعد از آپدیت/بازیابی خودکار
                # انجام می‌شود، ولی دستی و با گزارشِ فوری.
                rows = self.db.wanted()
                alive = sum(1 for c in rows if self.sup.is_running(c["uid"]))
                self.sup._resume_fail.clear()      # عقب‌گرد را صفر کن
                self._spawn_boot(notify_admins=False, why="دستور مدیر")
                return await self.edit(ev,
                    f"🟢 <b>روشن کردن همه سرویس‌ها</b>\\n{self.LINE}\\n"
                    f"👥 باید روشن باشند: {_fa_digits(len(rows))}\\n"
                    f"🟢 از قبل روشن: {_fa_digits(alive)}\\n"
                    f"⏳ بقیه در پس‌زمینه روشن می‌شوند (~۲ ثانیه هر سرویس).\\n\\n"
                    "<i>سرویس‌هایی که مشتری خودش خاموش کرده در این لیست نیستند؛ "
                    "برای روشن‌کردنشان «روشن کن» خودش را بزن.</i>",
                    [[B("🔄 بروزرسانی وضعیت", "a:stats", "primary")],
                     back_btn("a:home")])
            if k in ("revenue", "stats", "users", "plans", "tk",
                     "mlog", "pstats", "doctor"):
                cmd = {"revenue": "revenue", "stats": "stats", "users": "users",
                       "plans": "shopplans", "tk": "tk",
                       "mlog": "mlog", "pstats": "pstats",
                       "doctor": "doctor"}[k]
                sent = []
                orig = self.say
                async def cap(u, t, buttons=None):
                    sent.append(t)
                    return True
                self.say = cap
                try:
                    if not await self.shop_admin(uid, ev.chat_id, cmd, ""):
                        await self.admin_cmd(uid, ev.chat_id, cmd, "")
                finally:
                    self.say = orig
                return await self.edit(ev, sent[-1] if sent else "—",
                                       [back_btn("a:home")])

        if data.startswith("au:") and adm:
            await ans()
            c = self._user_or_orphan(int(digits(data[3:]) or 0))
            if not c:
                return await self.edit(ev, "پیدا نشد.", [back_btn("a:ulist:0")])
            return await self.edit(ev, self._admin_user_text(c), self._admin_user_kb(c))

        if data.startswith("aud:") and adm:
            await ans()
            tid = int(digits(data[4:]) or 0)
            txt, kb = self._admin_wipe_confirm_view(tid)
            return await self.edit(ev, txt, kb)

        if data.startswith("audx:") and adm:
            tid = int(digits(data[5:]) or 0)
            await ans("در حال پاک کردن اطلاعات…")
            ok, msg, _st = await self.wipe_user_data(tid, by_admin=uid)
            kb = [
                [B("🗑 پاک کردن کاربر دیگر", "a:uwipe", "danger")],
                [B("👥 لیست مشتری‌ها", "a:ulist:0", "primary"),
                 B("🛠 پنل مدیر", "a:home", "danger")],
            ]
            return await self.edit(ev, msg if ok else f"❌ {msg}", kb)

        if data.startswith("auj:") and adm:
            await ans()
            tid = int(digits(data[4:]) or 0)
            txt, kb = self._admin_jafj_wipe_confirm_view(tid)
            return await self.edit(ev, txt, kb)

        if data.startswith("aujx:") and adm:
            tid = int(digits(data[5:]) or 0)
            await ans("در حال پاک کردن تنظیمات جفج/تبادل…")
            ok, msg, _st = await self.wipe_user_jafj(tid, by_admin=uid)
            c = self._user_or_orphan(tid)
            if ok and c:
                return await self.edit(ev,
                    self._admin_user_text(c) + "\n" + msg,
                    self._admin_user_kb(c))
            return await self.edit(ev, msg if ok else f"❌ {msg}",
                                   [[B("👥 لیست مشتری‌ها", "a:ulist:0", "primary"),
                                     B("🛠 پنل مدیر", "a:home", "danger")]])

        if data.startswith("aut:") and adm:
            # ریستِ تست رایگان برای یک کاربر (مدت و روشن‌بودنِ تست عوض نمی‌شود)
            await ans()
            tid = int(digits(data[4:]) or 0)
            c = self.db.get(tid)
            if not c:
                return await self.edit(ev, "پیدا نشد.", [back_btn("a:ulist:0")])
            self.db.trial_reset_one(tid)
            self.db.log(tid, "trial_reset", "ریست توسط مدیر")
            try:
                await self.say(tid, "🎁 تست رایگانت دوباره فعال شد — از منو "
                                    "«🎁 تست رایگان» را بزن.")
            except Exception:
                pass
            c = self.db.get(tid)
            return await self.edit(ev, self._admin_user_text(c) +
                                   "\n♻️ تست رایگان این کاربر ریست شد"
                                   + (" (تستِ در حال اجرا قطع نشد)."
                                      if self.trial_active(tid) else "."),
                                   self._admin_user_kb(c))

        if data.startswith("ab:") and adm:
            _, suid, flag = data.split(":")
            tid = int(suid)
            if flag == "1":
                self.sup.stop(tid)
                self.db.set(tid, status="banned")
                self.db.log(tid, "banned")
                await self.say(tid, "⛔ دسترسی شما بسته شد.")
                await ans("بن شد")
            else:
                self.db.set(tid, status="active")
                self.db.log(tid, "unban")
                await self.say(tid, "✅ دسترسی شما باز شد.")
                await ans("آنبن شد")
            c = self.db.get(tid)
            return await self.edit(ev, self._admin_user_text(c), self._admin_user_kb(c))

        if data.startswith("as:") and adm:
            tid = int(digits(data[3:]) or 0)
            self.sup.stop(tid)
            self.db.set(tid, expires_at=0, status="expired", current_plan_id=0)
            self.db.log(tid, "sub_removed")
            await self.say(tid, "اشتراک شما حذف شد.")
            await ans("اشتراک حذف شد")
            c = self.db.get(tid)
            return await self.edit(ev, self._admin_user_text(c), self._admin_user_kb(c))

        if data.startswith("ag:") and adm:
            parts = data.split(":")
            tid = int(parts[1])
            arg = parts[2]
            if arg == "x":
                await ans()
                self.fsm[uid] = {"step": "gp_n", "tid": tid}
                return await self.edit(ev,
                    f"✏️ امتیاز برای <code>{tid}</code>\n"
                    "عدد بفرست (منفی = کم کردن). مثال: <code>-15</code>",
                    [back_btn(f"au:{tid}")])
            amt = int(arg)
            nb = sh.p_add(tid, amt, "admin", "مدیر از پنل")
            self.sync_points_limits(tid)
            sign = "+" if amt > 0 else ""
            await self.say(tid, f"🎯 امتیازت {sign}{_fa_digits(amt)} شد.\nموجودی: {_fa_digits(nb)}")
            await ans(f"امتیاز {sign}{amt}")
            c = self.db.get(tid)
            return await self.edit(ev, self._admin_user_text(c) +
                f"\nآخرین تغییر: {sign}{_fa_digits(amt)} → موجودی {_fa_digits(nb)}",
                self._admin_user_kb(c))

        if data.startswith("ad:") and adm:
            tid = int(digits(data[3:]) or 0)
            await ans()
            self.fsm[uid] = {"step": "ok_days", "tid": tid}
            return await self.edit(ev,
                f"📅 چند روز اشتراک برای <code>{tid}</code>؟\nمثال: <code>30</code>",
                [back_btn(f"au:{tid}")])

        if data.startswith("ac:") and adm:
            parts = data.split(":")
            tid = int(parts[1])
            arg = parts[2] if len(parts) > 2 else "0"
            c = self.db.get(tid)
            if not c:
                return await ans("کاربر پیدا نشد")
            if arg == "x":
                await ans()
                self.fsm[uid] = {"step": "acct_n", "tid": tid}
                return await self.edit(ev,
                    f"👥 سقف اکانت برای <code>{tid}</code>\n"
                    "عدد بفرست (۰ = برگشت به پلن). مثال: <code>3</code>",
                    [back_btn(f"au:{tid}")])
            # سقفِ مؤثر فعلی: سقفِ شخصی اگر هست، وگرنه سقفِ پلن.
            cur = int(c.get("max_accounts") or 0)
            base = self.effective_plan(tid)
            plan_mx = int(base.get("max_accounts", 1) or 1) if base else 1
            eff = cur if cur > 0 else plan_mx
            if arg == "1":
                v = eff + 1
            elif arg == "-1":
                v = max(0, eff - 1)
            else:
                v = max(0, int(digits(arg) or 0))
            self.db.set(tid, max_accounts=v)
            if v > 0:
                self.sup.write_limits(tid, {"name": "سفارشی", "max_accounts": v},
                                      override_max_accounts=v)
            else:
                if (self.cfg.get("points_on") and self.shop
                        and not self.has_sub(tid)):
                    bal = self.shop.p_balance(tid)
                    per = max(1, int(self.cfg["cost_per_hour"]))
                    self.sup.write_limits(tid, None, points_mode=True,
                                          points=bal, hours_left=bal // per)
                else:
                    best = self.effective_plan(tid) or {"name": "", "max_accounts": 1}
                    self.sup.write_limits(tid, best)
            if self.sup.is_running(tid):
                await self.sup.restart(tid)
            await ans(f"اکانت {v}")
            c = self.db.get(tid)
            return await self.edit(ev, self._admin_user_text(c) +
                f"\n👥 آخرین تغییر: سقف اکانت → <b>{_fa_digits(v)}</b>"
                + ("" if v else " (برگشت به پلن)"),
                self._admin_user_kb(c))

        if data.startswith("am:") and adm:
            tid = int(digits(data[3:]) or 0)
            await ans()
            self.fsm[uid] = {"step": "say_u", "tid": tid}
            return await self.edit(ev,
                f"💬 پیام به <code>{tid}</code> را بنویس:",
                [back_btn(f"au:{tid}")])

        if data.startswith("aproc:") and adm:
            tid = int(digits(data[6:]) or 0)
            if self.sup.is_running(tid):
                ok, msg = self.sup.stop(tid, remember_off=True)
            else:
                ok, msg, _ = self.start_service(tid, charge_success=False)
            await ans(msg[:40])
            c = self.db.get(tid)
            return await self.edit(ev, self._admin_user_text(c) + f"\n{msg}",
                                   self._admin_user_kb(c))

        if data.startswith("apr:") and adm:
            pid = int(digits(data[4:]) or 0)
            x = sh.plan(pid) if sh else None
            if not x:
                return await ans("پیدا نشد")
            await ans()
            self.fsm[uid] = {"step": "price_plan", "pid": pid}
            return await self.edit(ev,
                f"💰 قیمت جدید <b>{x['name']}</b>\nفعلی: {money(x['price'])}\n"
                "فقط عدد تومان را بفرست. مثال: <code>150000</code>",
                [back_btn("a:prices")])

        if data.startswith("apk:") and adm:
            kid = int(digits(data[4:]) or 0)
            x = sh.pack(kid) if sh else None
            if not x:
                return await ans("پیدا نشد")
            await ans()
            self.fsm[uid] = {"step": "price_pack", "kid": kid}
            return await self.edit(ev,
                f"🎯 قیمت جدید بسته <b>{x['name']}</b>\nفعلی: {money(x['price'])}\n"
                "فقط عدد تومان را بفرست.",
                [back_btn("a:pkprice")])

        if data.startswith("adt:") and adm:
            code = data[4:]
            d = sh.discount(code) if sh else None
            if not d:
                return await ans("کد نیست")
            sh.x("UPDATE discounts SET active=? WHERE code=?",
                 (0 if d["active"] else 1, code.upper()))
            await ans("تغییر کرد")
            # refresh list
            ev.data = b"a:discs"
            return await self.on_callback(ev)

        if data.startswith(("ao:", "ar:", "av:")) and adm:
            oid = int(data[3:])
            if data.startswith("ao:"):
                await ans("در حال تأیید…")
                await self.shop_admin(uid, ev.chat_id, "approve", str(oid))
            elif data.startswith("ar:"):
                await ans()
                self.fsm[uid] = {"step": "deny", "oid": oid}
                return await self.edit(ev,
                    f"❌ دلیل رد سفارش #{_fa_digits(oid)} را بنویس:\n\n/cancel برای لغو",
                    [back_btn("a:pending")])
            else:
                await ans()
                await self.shop_admin(uid, ev.chat_id, "order", str(oid))
                return
            return await self.edit(ev, f"✅ سفارش #{_fa_digits(oid)} رسیدگی شد.",
                                   [[B("📤 بقیه سفارش‌ها", "a:pending")],
                                    back_btn("a:home")])

        return await ans()

    def _card_block(self):
        card = self.cfg["card_number"]
        pretty = " ".join(card[i:i + 4] for i in range(0, len(card), 4))
        L = ["💳 <b>واریز به کارت</b>", "", f"<code>{pretty}</code>",
             f"👤 {self.cfg['card_name'] or '—'}", ""]
        if self.cfg["pay_note"]:
            L += [f"<i>{self.cfg['pay_note']}</i>", ""]
        L += [self.LINE, "📸 بعد از واریز، <b>عکس رسید</b> را همینجا بفرست."]
        return L

    def phone_ok(self, uid):
        c = self.db.get(uid)
        return bool(c and int(c.get("phone_verified") or 0) == 1
                    and normalize_iran_phone(c.get("phone") or ""))

    def ensure_client(self, uid, username=None, name=None):
        """بدون /start هم ردیف مشتری ساخته شود تا phone_verified ذخیره شود."""
        if not self.db.get(uid):
            self.db.add(uid, username, name or "", self.cfg["trial_days"])
        return self.db.get(uid)

    def save_verified_phone(self, uid, phone):
        normalized = normalize_iran_phone(phone)
        if not normalized:
            return ""
        self.ensure_client(uid)
        self.db.set(uid, phone=normalized, phone_verified=1)
        return normalized

    def self_active(self, uid):
        """سلف روی اکانت این کاربر فعال است؟

        فعال یعنی یا پروسه‌ی سلفش همین الان روشن است، یا اکانت تلگرامش وصل شده
        (سشن دارد) و وضعیتش active و منقضی‌نشده است. کاربری که اصلاً سلف
        راه‌اندازی نکرده یا سلفش منقضی/مسدود شده، «بدون سلف» حساب می‌شود.
        """
        try:
            if self.sup and self.sup.is_running(uid):
                return True
        except Exception:
            pass
        c = self.db.get(uid)
        if not c or not c.get("session") or c.get("status") != "active":
            return False
        exp = int(c.get("expires_at") or 0)
        return exp == 0 or exp > now()

    def _cfg_points(self, key, default):
        try:
            v = self.cfg.get(key, default)
            return max(0, int(default if v is None else v))
        except Exception:
            return default

    def referral_points_for(self, referrer_uid):
        """پاداش هر دعوت معتبر برای این معرف:
        سلف فعال → referral_points_self (پیش‌فرض ۱)،
        بدون سلف → referral_points (پیش‌فرض ۲)."""
        if self.self_active(referrer_uid):
            return self._cfg_points("referral_points_self", 1)
        return self._cfg_points("referral_points", 2)

    def referral_rate_text(self, uid):
        """متن نرخ پاداش دعوت برای نمایش در بخش زیرمجموعه."""
        pts = _fa_digits(self.referral_points_for(uid))
        if self.self_active(uid):
            return (f"🎯 پاداش هر دعوت معتبر: <b>{pts} امتیاز</b> (سلف روی اکانتت فعال است)\n"
                    f"ℹ️ بدون سلف فعال، هر دعوت "
                    f"{_fa_digits(self._cfg_points('referral_points', 2))} امتیاز است.")
        return (f"🎯 پاداش هر دعوت معتبر: <b>{pts} امتیاز</b> (سلف روی اکانتت فعال نیست)\n"
                f"ℹ️ با سلف فعال، هر دعوت "
                f"{_fa_digits(self._cfg_points('referral_points_self', 1))} امتیاز است.")

    def reward_verified_referral(self, invitee_uid):
        """پس از تأیید شماره دعوت‌شده، یک‌بار به معرف امتیاز بده
        (سلف فعال: ۱ امتیاز، بدون سلف: ۲ امتیاز — قابل تنظیم با /set)."""
        if not (self.shop and self.cfg["points_on"]):
            return None, 0
        invitee = self.db.get(invitee_uid) or {}
        if not invitee.get("phone_verified") or not normalize_iran_phone(invitee.get("phone") or ""):
            return None, 0
        referrer_uid = self.shop.referrer_of(invitee_uid)
        if not referrer_uid or referrer_uid == invitee_uid:
            return None, 0
        referrer = self.db.get(referrer_uid) or {}
        if not referrer.get("phone_verified") or not normalize_iran_phone(referrer.get("phone") or ""):
            return None, 0
        same = self.db.x("SELECT uid FROM clients WHERE phone=? AND phone_verified=1 AND uid<>? LIMIT 1",
                         (invitee.get("phone"), invitee_uid), "one")
        if same:
            return None, 0
        return self.shop.reward_verified_referral(
            invitee_uid, referrer_uid, self.referral_points_for(referrer_uid))

    def reward_existing_referrals(self, referrer_uid):
        """اگر دعوت‌شده قبلاً تأیید کرده بود، بعد از تأیید معرف پاداش را تکمیل کن."""
        if not self.shop:
            return []
        out = []
        for row in self.shop.my_refs(referrer_uid):
            got = self.reward_verified_referral(row["uid"])
            if got[0]:
                out.append(got)
        return out

    async def require_phone_for_referral(self, uid, chat, ev=None):
        """تأیید شماره فقط برای پاداش زیرمجموعه؛ بدون خرید یا فعال‌سازی سلف."""
        self.ensure_client(uid)
        if self.phone_ok(uid):
            return True
        self.fsm[uid] = {"step": "verify_referral"}
        msg = (
            "🔐 <b>تأیید شماره برای زیرمجموعه‌گیری</b>\n" + self.LINE + "\n"
            "برای فعال‌شدن پاداش، شماره موبایل ایران خودت را تأیید کن.\n"
            "این کار رایگان است و فعال‌سازی سلف لازم ندارد.\n\n"
            "👇 دکمه پایین صفحه را بزن.\nلغو: /cancel")
        if ev is not None:
            try:
                await ev.edit(msg, parse_mode="html", buttons=[[B("❌ لغو", "m:home")]])
            except Exception:
                pass
        try:
            await self.bot.send_message(chat, msg, parse_mode="html",
                                         buttons=phone_keyboard("📱 تأیید شماره"))
        except Exception as e:
            print("require_referral_phone:", type(e).__name__, e)
            await self.say(chat, msg + "\n\nشماره را با کد +98 بفرست.", [back_btn("m:home")])
        return False

    async def start_trial(self, uid, chat, ev=None):
        """شروع تست رایگان؛ مدت از پنل مدیر تعیین می‌شود و تایمر بعد از
        راه‌اندازی موفق سلف شروع می‌شود."""
        if not self.cfg.get("trial_on", True):
            return await self.say(chat, "🎁 تست رایگان فعلاً در تنظیمات غیرفعال است.")
        
        self.ensure_client(uid)
        c = self.db.get(uid) or {}
        
        # اگر مدیر است، تست را آزادانه ریست کن
        if self.is_admin(uid):
            self.db.set(uid, trial_used=0, trial_started_at=0, trial_expires_at=0, trial_warning_sent=0)
        else:
            if c.get("status") == "banned":
                return await self.say(chat, "❌ دسترسی حساب شما مسدود است.")
            # فقط در صورتی مانع شو که کاربر واقعاً تستش را استارت زده باشد
            if int(c.get("trial_used") or 0) == 1 and int(c.get("trial_started_at") or 0) > 0:
                txt = ("🎁 <b>تست رایگان قبلاً استفاده شده است</b>\n" + self.LINE + "\n"
                       f"شما قبلاً از {self.trial_label()} تست رایگان این اکانت استفاده "
                       "کرده‌اید.\n"
                       "برای ادامه، می‌توانید اشتراک ماهانه یا بسته امتیازی تهیه کنید.")
                kb = [[B("💎 خرید اشتراک", "m:plans", "primary"),
                       B("🎯 خرید امتیاز", "m:packs", "success")],
                      back_btn("m:home")]
                return await (self.edit(ev, txt, kb) if ev else self.say(chat, txt, kb))
        
        return await self.setup_start(uid, chat, ev, trial=True)

    async def require_phone_for_card(self, uid, chat, pending=None, ev=None):
        """اگر شماره تأیید نشده، کیبورد تأیید بفرست و فاکتور را نگه دار."""
        self.ensure_client(uid)
        if self.phone_ok(uid):
            return True
        from telethon import Button
        self.fsm[uid] = {"step": "verify_phone", "pending": pending or {}}
        msg = (
            "🔐 <b>تأیید شماره برای کارت‌به‌کارت</b>\n" + self.LINE + "\n"
            "قبل از دیدن شماره کارت، باید شماره موبایل ایران همین اکانت تلگرام را تأیید کنی.\n\n"
            "👇 دکمه پایین صفحه را بزن. شماره را تایپ نکن.\n"
            "لغو: /cancel")
        if ev is not None:
            try:
                await ev.edit(msg + "\n\n<i>کیبورد پایین صفحه باز شد.</i>",
                              parse_mode="html", buttons=[[B("❌ لغو", "m:home")]])
            except Exception:
                pass
        try:
            await self.bot.send_message(
                chat, msg, parse_mode="html",
                buttons=phone_keyboard("📱 تأیید شماره"))
        except Exception as e:
            print("require_phone:", type(e).__name__, e)
            await self.say(chat,
                msg + "\n\nاگر دکمه نیامد، شماره را با کد کشور بفرست.",
                [back_btn("m:home")])
        return False

    async def resume_pending_pay(self, uid, chat):
        pend = (self.fsm.get(uid) or {}).get("pending") or {}
        self.fsm.pop(uid, None)
        kind = pend.get("kind")
        if kind == "pack":
            return await self.pack_invoice(uid, None, pend["kid"], pend.get("code", ""),
                                           pend.get("use_w", False), edit=False)
        if kind == "plan":
            return await self.make_invoice(uid, None, pend["pid"], pend.get("code", ""),
                                           pend.get("use_w", False), edit=False)
        if kind == "custom":
            return await self.custom_invoice(uid, None, pend["points"], edit=False)
        if kind == "wallet":
            return await self.topup_invoice(uid, None, pend["amount"], edit=False)
        return await self.say(chat, "✅ شماره تأیید شد. دوباره خرید را بزن تا فاکتور و شماره کارت بیاید.")

    async def custom_invoice(self, uid, ev, points, edit=False):
        """فاکتور خرید امتیاز به مقدار دلخواه."""
        sh = self.shop
        points = int(points)
        mn, mx = int(self.cfg["min_points_buy"]), int(self.cfg["max_points_buy"])
        if not (mn <= points <= mx):
            t = f"تعداد امتیاز باید بین {_fa_digits(mn)} تا {_fa_digits(mx)} باشد."
            return await (self.edit(ev, t, [back_btn("m:packs")] if edit and ev is not None
                           else self.say(uid, t)))
        price = points * self.cfg["point_price"]
        if not self.cfg["card_number"]:
            t = "شماره کارت مدیر ثبت نشده. مدیر باید با /card شماره کارت را بگذارد."
            return await (self.edit(ev, t, [back_btn()]) if edit and ev is not None else self.say(uid, t))
        if not await self.require_phone_for_card(
                uid, uid, pending={"kind": "custom", "points": points}, ev=ev if edit else None):
            return None
        sh.cancel_open(uid)
        o, err = sh.create_custom_points_order(uid, points, price)
        if err:
            return await self.say(uid, f"❌ {err}")
        per = max(1, self.cfg["cost_per_hour"])
        L = ["🧾 <b>فاکتور امتیاز</b>  " + f"<code>#{_fa_digits(o['id'])}</code>", self.LINE,
             f"🎯 {_fa_digits(points)} امتیاز  ·  ≈{_fa_digits(points // per)} ساعت",
             f"هر امتیاز {money(self.cfg['point_price'])}", "",
             self.LINE, f"💵 <b>قابل پرداخت    {money(price)}</b>", ""]
        L += self._card_block()
        t = "\n".join(L)
        kb = [[B("❌ لغو سفارش", "m:packs", "danger")], back_btn()]
        if edit and ev is not None:
            return await self.edit(ev, t, kb)
        return await self.say(uid, t, kb)

    async def topup_invoice(self, uid, ev, amount, edit=False):
        """فاکتور شارژ کیف پول."""
        sh = self.shop
        amount = int(amount)
        if not (int(self.cfg["min_topup"]) <= amount <= int(self.cfg["max_topup"])):
            t = f"مبلغ باید بین {money(self.cfg['min_topup'])} تا {money(self.cfg['max_topup'])} باشد."
            return await (self.edit(ev, t, [back_btn("m:wallet")] if edit and ev is not None
                           else self.say(uid, t)))
        if not self.cfg["card_number"]:
            t = "شماره کارت مدیر ثبت نشده. مدیر باید با /card شماره کارت را بگذارد."
            return await (self.edit(ev, t, [back_btn()]) if edit and ev is not None else self.say(uid, t))
        if not await self.require_phone_for_card(
                uid, uid, pending={"kind": "wallet", "amount": amount}, ev=ev if edit else None):
            return None
        sh.cancel_open(uid)
        o, err = sh.create_wallet_order(uid, amount)
        if err:
            return await self.say(uid, f"❌ {err}")
        L = ["🧾 <b>فاکتور شارژ کیف پول</b>  " + f"<code>#{_fa_digits(o['id'])}</code>",
             self.LINE,
             f"موجودی فعلی    {money(sh.balance(uid))}",
             f"شارژ            +{money(amount)}",
             f"بعد از تأیید    {money(sh.balance(uid) + amount)}", "",
             self.LINE, f"💵 <b>قابل پرداخت    {money(amount)}</b>", ""]
        L += self._card_block()
        t = "\n".join(L)
        kb = [[B("❌ لغو سفارش", "m:wallet", "danger")], back_btn()]
        if edit and ev is not None:
            return await self.edit(ev, t, kb)
        return await self.say(uid, t, kb)

    async def pack_invoice(self, uid, ev, kid, code="", use_w=False, edit=False):
        sh = self.shop
        # اول شماره؛ سفارش را بعد از تأیید بساز تا فاکتور گم نشود
        k = sh.pack(kid)
        need_pay = True
        if k:
            need_pay = (k["price"] - (min(sh.balance(uid), k["price"]) if use_w else 0)) > 0
        if need_pay and not await self.require_phone_for_card(
                uid, uid,
                pending={"kind": "pack", "kid": kid, "code": code, "use_w": use_w},
                ev=ev if edit else None):
            return None
        sh.cancel_open(uid)
        o, err = sh.create_pack_order(uid, kid, code, use_w)
        if err:
            t, kb = f"❌ {err}", [back_btn("m:packs")]
            return await (self.edit(ev, t, kb) if edit else self.say(uid, t, kb))

        card = self.cfg["card_number"]
        if not card and o["final"] > 0:
            t = "فعلاً امکان پرداخت نیست، بعداً امتحان کن."
            return await (self.edit(ev, t, [back_btn()]) if edit else self.say(uid, t))
        per = max(1, self.cfg["cost_per_hour"])
        L = ["🧾 <b>فاکتور امتیاز</b>  " + f"<code>#{_fa_digits(o['id'])}</code>", self.LINE,
             f"📦 {o['plan_name']}",
             f"🎯 {_fa_digits(o['points'])} امتیاز  ·  ≈{_fa_digits(o['points'] // per)} ساعت", "",
             f"مبلغ                {money(o['amount'])}"]
        if o["discount_off"]:
            L.append(f"🎟 {o['discount_code']}          −{money(o['discount_off'])}")
        if o["wallet_used"]:
            L.append(f"💳 کیف پول         −{money(o['wallet_used'])}")
        L += [self.LINE, f"💵 <b>قابل پرداخت    {money(o['final'])}</b>", ""]
        if o["final"] <= 0:
            sh.attach_receipt(o["id"], text="پرداخت کامل از کیف پول")
            # پرداخت کامل از کیف پول نیاز به تأیید مدیر ندارد.
            await self.shop_admin(uid, uid, "approve", str(o["id"]))
            L.append("✅ پرداخت کامل از کیف پول انجام شد و سفارش خودکار تأیید شد.")
            kb = [back_btn("m:pts")]
        else:
            pretty = " ".join(card[i:i + 4] for i in range(0, len(card), 4))
            L += ["💳 <b>واریز به کارت</b>", "", f"<code>{pretty}</code>",
                  f"👤 {self.cfg['card_name'] or '—'}", "", self.LINE,
                  "📸 بعد از واریز، <b>عکس رسید</b> را همینجا بفرست."]
            kb = [[B("❌ لغو سفارش", "m:packs", "danger")], back_btn("m:pts")]
        t = "\n".join(L)
        return await (self.edit(ev, t, kb) if edit else self.say(uid, t, kb))

    async def make_invoice(self, uid, ev, pid, code="", use_w=False, edit=False):
        sh = self.shop
        pl = sh.plan(pid)
        need_pay = True
        if pl:
            after = pl["price"]
            if use_w:
                after -= min(sh.balance(uid), after)
            need_pay = after > 0
        if need_pay and not await self.require_phone_for_card(
                uid, uid,
                pending={"kind": "plan", "pid": pid, "code": code, "use_w": use_w},
                ev=ev if edit else None):
            return None
        sh.cancel_open(uid)
        o, err = sh.create_order(uid, pid, code, use_w)
        if err:
            t, kb = f"❌ {err}", [back_btn("m:plans")]
            return await (self.edit(ev, t, kb) if edit else self.say(uid, t, kb))

        card = self.cfg["card_number"]
        if not card and o["final"] > 0:
            t = "فعلاً امکان پرداخت نیست، بعداً امتحان کن."
            return await (self.edit(ev, t, [back_btn()]) if edit else self.say(uid, t))

        L = ["🧾 <b>فاکتور</b>  " + f"<code>#{_fa_digits(o['id'])}</code>", self.LINE,
             f"📦 {o['plan_name']}  ·  {_fa_digits(o['days'])} روز", "",
             f"مبلغ پلن            {money(o['amount'])}"]
        if o["discount_off"]:
            L.append(f"🎟 {o['discount_code']}          −{money(o['discount_off'])}")
        if o["wallet_used"]:
            L.append(f"💳 کیف پول         −{money(o['wallet_used'])}")
        L += [self.LINE,
              f"💵 <b>قابل پرداخت    {money(o['final'])}</b>", ""]

        if o["final"] <= 0:
            sh.attach_receipt(o["id"], text="پرداخت کامل از کیف پول")
            # پرداخت کامل از کیف پول نیاز به تأیید مدیر ندارد.
            await self.shop_admin(uid, uid, "approve", str(o["id"]))
            L.append("✅ پرداخت کامل از کیف پول انجام شد و سفارش خودکار تأیید شد.")
            kb = [back_btn()]
        else:
            pretty = " ".join(card[i:i + 4] for i in range(0, len(card), 4))
            L += ["💳 <b>واریز به کارت</b>", "",
                  f"<code>{pretty}</code>",
                  f"👤 {self.cfg['card_name'] or '—'}", ""]
            if self.cfg["pay_note"]:
                L += [f"<i>{self.cfg['pay_note']}</i>", ""]
            L += [self.LINE,
                  "📸 بعد از واریز، <b>عکس رسید</b> را همینجا بفرست.",
                  "<i>تأیید معمولاً کمتر از 10 دقیقه طول می‌کشد.</i>"]
            kb = [[B("❌ لغو سفارش", "m:plans", "danger")], back_btn()]
        t = "\n".join(L)
        return await (self.edit(ev, t, kb) if edit else self.say(uid, t, kb))

    # ═══════════════════════════════════════════════
    #  فروشگاه — مشتری
    # ═══════════════════════════════════════════════
    async def shop_user(self, uid, chat, cmd, arg, user):
        if not self.shop or not self.cfg["shop_on"]:
            return None
        sh = self.shop
        p = arg.split()

        # خرید از کیف پول کامل، نیاز به تأیید شماره ندارد.
        if cmd in ("plans", "buy_list", "shop"):
            pl = sh.plans()
            if not pl:
                return await self.say(chat, "فعلاً پلنی موجود نیست.")
            out = ["🛒 <b>پلن‌ها</b>", ""]
            for i, x in enumerate(pl, 1):
                out.append(f"<b>{i}. {x['name']}</b>")
                out.append(f"   ⏱ {_fa_digits(x['days'])} روز")
                out.append(f"   💰 {money(x['price'])}")
                out.append(f"   👥 تا {_fa_digits(x['max_accounts'])} اکانت")
                if x["features"]:
                    out.append(f"   ✨ {x['features']}")
                out.append(f"   خرید: <code>/buy {i}</code>")
                out.append("")
            b = sh.balance(uid)
            if b:
                out.append(f"💳 موجودی کیف پول شما: {money(b)}")
                out.append("برای استفاده: <code>/buy 1 - w</code>")
            return await self.say(chat, "\n".join(out))

        if cmd == "buy":
            c = self.db.get(uid)
            if not c:
                return await self.say(chat, "اول /start را بزن.")
            if not p:
                return await self.say(chat, "شماره پلن را بده: <code>/buy 1</code>")
            pl = sh.plans()
            try:
                idx = int(digits(p[0])) - 1
                plan = pl[idx]
            except Exception:
                return await self.say(chat, "شماره پلن درست نیست. /plans")
            code = ""
            use_w = False
            for t in p[1:]:
                if t.lower() in ("w", "wallet", "کیف"):
                    use_w = True
                elif t != "-":
                    code = t
            after = plan["price"]
            if use_w:
                after -= min(sh.balance(uid), after)
            if after > 0 and not await self.require_phone_for_card(
                    uid, chat, pending={"kind": "plan", "pid": plan["id"],
                                        "code": code, "use_w": use_w}):
                return None
            sh.cancel_open(uid)
            o, err = sh.create_order(uid, plan["id"], code, use_w)
            if err:
                return await self.say(chat, f"❌ {err}")

            card = self.cfg["card_number"]
            if not card:
                for a in self.cfg["admin_ids"]:
                    await self.say(a, "⚠️ شماره کارت تنظیم نشده! /card")
                return await self.say(chat, "فعلاً امکان پرداخت نیست، بعداً امتحان کن.")

            lines = [f"🧾 <b>فاکتور #{_fa_digits(o['id'])}</b>", "",
                     f"پلن: {o['plan_name']} ({_fa_digits(o['days'])} روز)",
                     f"مبلغ: {money(o['amount'])}"]
            if o["discount_off"]:
                lines.append(f"تخفیف ({o['discount_code']}): -{money(o['discount_off'])}")
            if o["wallet_used"]:
                lines.append(f"از کیف پول: -{money(o['wallet_used'])}")
            lines += ["", f"<b>قابل پرداخت: {money(o['final'])}</b>", ""]
            if o["final"] <= 0:
                sh.attach_receipt(o["id"], text="پرداخت کامل از کیف پول")
                # پرداخت کامل از کیف پول خودکار تأیید می‌شود؛ فقط رسید کارت نیازمند مدیر است.
                await self.shop_admin(uid, uid, "approve", str(o["id"]))
                lines.append("✅ پرداخت کامل از کیف پول انجام شد و سفارش خودکار تأیید شد.")
            else:
                lines += ["💳 <b>واریز به:</b>",
                          f"<code>{card}</code>",
                          f"به نام: {self.cfg['card_name'] or '—'}", ""]
                if self.cfg["pay_note"]:
                    lines += [self.cfg["pay_note"], ""]
                lines += ["بعد از واریز، <b>عکس رسید</b> یا متن آن را همینجا بفرست.",
                          "لغو: /cancel"]
            return await self.say(chat, "\n".join(lines))

        if cmd == "orders":
            rows = sh.user_orders(uid)
            if not rows:
                return await self.say(chat, "سفارشی نداری. /plans")
            ic = {"pending": "⏳ منتظر رسید", "paid": "📤 منتظر تأیید",
                  "approved": "✅ تأیید شده", "rejected": "❌ رد شده",
                  "canceled": "🚫 لغو شده"}
            kic = {"wallet": "💳", "points": "🎯"}
            out = ["🧾 <b>سفارش‌های من</b>", ""]
            for o in rows:
                out.append(f"{kic.get(o.get('kind'), '💎')} #{_fa_digits(o['id'])} "
                           f"{o['plan_name']} — {money(o['final'])}")
                out.append(f"     {ic.get(o['status'], o['status'])} • "
                           f"{local_dt(o['created_at']):%m-%d %H:%M}")
                if o["note"]:
                    out.append(f"     💬 {o['note']}")
            return await self.say(chat, "\n".join(out))

        if cmd == "wallet":
            b = sh.balance(uid)
            out = [f"💳 <b>کیف پول</b>", "", f"موجودی: <b>{money(b)}</b>", ""]
            lg = sh.wallet_log(uid, 8)
            if lg:
                out.append("<b>تراکنش‌ها</b>")
                for w in lg:
                    sign = "+" if w["amount"] > 0 else ""
                    out.append(f"{sign}{money(abs(w['amount']))} — {w['detail'] or w['kind']}")
            else:
                out.append("تراکنشی نداری.")
            out += ["", "برای استفاده هنگام خرید: <code>/buy 1 w</code>"]
            return await self.say(chat, "\n".join(out))

        if cmd in ("points", "point", "امتیاز", "packs", "pack"):
            if not self.cfg["points_on"]:
                return await self.say(chat, "سیستم امتیاز خاموش است.")
            per = max(1, self.cfg["cost_per_hour"])
            bal = sh.p_balance(uid)
            if cmd in ("packs", "pack"):
                out = ["🛒 <b>بسته‌های امتیاز</b>", self.LINE]
                for k in sh.packs():
                    tot = k["points"] + k["bonus"]
                    out.append(f"<b>{k['name']}</b> — {_fa_digits(tot)} امتیاز "
                               f"(≈{_fa_digits(tot // per)} ساعت) — {money(k['price'])}")
                return await self.say(chat, "\n".join(out),
                                      [[B("🛒 خرید", "m:packs", "success")]])
            return await self.say(chat,
                f"🎯 <b>امتیاز</b>\n{self.LINE}\n"
                f"موجودی: <b>{_fa_digits(bal)}</b>\n"
                f"کارکرد: ≈{_fa_digits(bal // per)} ساعت\n"
                f"حداقل فعال‌سازی: {_fa_digits(self.cfg['min_points'])}",
                [[B("🎯 پنل امتیاز", "m:pts", "success")]])

        if cmd in ("topup", "شارژ"):
            if not arg:
                return await self.say(chat,
                    f"💳 موجودی: <b>{money(sh.balance(uid))}</b>\n\n"
                    f"<code>/topup 50000</code> — شارژ کیف پول",
                    [[B("➕ افزایش موجودی", "w:topup", "success")]])
            try:
                amt = int(digits(arg))
            except ValueError:
                return await self.say(chat, "عدد بده: <code>/topup 50000</code>")
            mn, mx = self.cfg["min_topup"], self.cfg["max_topup"]
            if not (mn <= amt <= mx):
                return await self.say(chat,
                    f"مبلغ باید بین {money(mn)} تا {money(mx)} باشد.")
            return await self.topup_invoice(uid, None, amt)

        if cmd in ("buypoints", "bp"):
            if not arg:
                return await self.say(chat,
                    f"<code>/bp 100</code> — خرید ۱۰۰ امتیاز\n"
                    f"هر امتیاز {money(self.cfg['point_price'])}",
                    [[B("✏️ مقدار دلخواه", "kc:0", "primary")]])
            try:
                n = int(digits(arg))
            except ValueError:
                return await self.say(chat, "عدد بده: <code>/bp 100</code>")
            mn, mx = self.cfg["min_points_buy"], self.cfg["max_points_buy"]
            if not (mn <= n <= mx):
                return await self.say(chat,
                    f"تعداد باید بین {_fa_digits(mn)} تا {_fa_digits(mx)} باشد.")
            return await self.custom_invoice(uid, None, n)

        if cmd in ("ref", "referral"):
            if not self.phone_ok(uid):
                return await self.say(chat,
                    "برای فعال‌شدن پاداش زیرمجموعه، اول شماره موبایل ایرانت را تأیید کن.",
                    [[B("✅ تأیید شماره", "r:verify", "success")]])
            me = await self.bot.get_me()
            link = f"https://t.me/{me.username}?start=r{uid}"
            refs = sh.my_refs(uid)
            rewarded = sum(1 for r in refs if r["rewarded"])
            return await self.say(chat,
                f"🎁 <b>لینک زیرمجموعه</b>\n\n<code>{link}</code>\n\n"
                + self.referral_rate_text(uid) + "\n"
                f"👥 دعوت‌شده: {_fa_digits(len(refs))}\n"
                f"✅ معتبر: {_fa_digits(rewarded)}")

        if cmd == "ticket":
            if not arg:
                return await self.say(chat, "متن را بنویس:\n<code>/ticket سلف بالا نمیاد</code>")
            tid = sh.new_ticket(uid, arg[:60], arg)
            for a in self.cfg["admin_ids"]:
                await self.say(a, f"🎧 <b>تیکت جدید #{_fa_digits(tid)}</b>\n"
                                  f"از: <code>{uid}</code>\n\n{arg[:500]}\n\n"
                                  f"جواب: <code>/tr {tid} متن</code>")
            return await self.say(chat, f"✅ تیکت #{_fa_digits(tid)} ثبت شد. زودی جواب می‌دهیم.")

        if cmd == "tickets":
            rows = sh.user_tickets(uid)
            if not rows:
                return await self.say(chat, "تیکتی نداری.")
            ic = {"open": "🟡 باز", "answered": "✅ جواب داده شد", "closed": "⚪ بسته"}
            out = ["🎧 <b>تیکت‌های من</b>", ""]
            for t in rows:
                out.append(f"#{_fa_digits(t['id'])} {t['subject']}")
                out.append(f"     {ic.get(t['status'], t['status'])}")
                for msg in sh.ticket_msgs(t["id"])[-2:]:
                    who = "👤 شما" if not msg["from_admin"] else "🛠 پشتیبانی"
                    out.append(f"     {who}: {(msg['text'] or '')[:60]}")
                out.append("")
            return await self.say(chat, "\n".join(out))

        return None

    async def notify_admins_receipt(self, o, ev):
        """رسید عکسی را برای ادمین‌ها فوروارد می‌کند."""
        if not o:
            return
        c = self.db.get(o["uid"])
        kind = o.get("kind", "sub")
        icon = {"wallet": "💳", "points": "🎯"}.get(kind, "💎")
        what = {"wallet": f"شارژ کیف پول {money(o['amount'])}",
                "points": f"{_fa_digits(o['points'])} امتیاز — {o['plan_name']}"
                }.get(kind, f"{o['plan_name']} ({_fa_digits(o['days'])} روز)")
        txt = (f"{icon} <b>رسید سفارش #{_fa_digits(o['id'])}</b>\n\n"
               f"مشتری: <code>{o['uid']}</code> {c['name'] if c else ''}\n"
               f"مورد: {what}\n"
               f"مبلغ: <b>{money(o['final'])}</b>\n\n"
               f"رسید عکسی بالا ⬆️")
        kb = [[B("✅ تأیید", f"ao:{o['id']}", "success"), B("❌ رد", f"ar:{o['id']}", "danger")]]
        for a in self.cfg["admin_ids"]:
            try:
                await self.bot.forward_messages(a, ev.id, ev.chat_id)
            except Exception:
                pass
            await self.say(a, txt, kb)

    async def _save_photo(self, ev, uid=None):
        uid = uid or getattr(ev, "sender_id", 0)
        folder = os.path.join(self.sup.folder(uid), "receipts")
        os.makedirs(folder, exist_ok=True)
        path = os.path.join(folder, f"receipt_{ev.id}.jpg")
        try:
            saved = await ev.download_media(file=path)
            return str(saved) if saved else None
        except Exception as e:
            print("save_photo:", type(e).__name__, e)
            return None

    async def notify_admins_order(self, o, user=None):
        if not o:
            return
        c = self.db.get(o["uid"])
        kind = o.get("kind", "sub")
        icon = {"wallet": "💳", "points": "🎯"}.get(kind, "💎")
        what = {"wallet": f"شارژ کیف پول {money(o['amount'])}",
                "points": f"{_fa_digits(o['points'])} امتیاز — {o['plan_name']}"
                }.get(kind, f"{o['plan_name']} ({_fa_digits(o['days'])} روز)")
        txt = (f"{icon} <b>سفارش جدید #{_fa_digits(o['id'])}</b>\n\n"
               f"مشتری: <code>{o['uid']}</code> {c['name'] if c else ''}\n"
               f"مورد: {what}\n"
               f"مبلغ: <b>{money(o['final'])}</b>\n")
        if o["discount_code"]:
            txt += f"تخفیف: {o['discount_code']} (-{money(o['discount_off'])})\n"
        if o["wallet_used"]:
            txt += f"کیف پول: -{money(o['wallet_used'])}\n"
        if o["receipt_text"]:
            txt += f"\nرسید: {o['receipt_text'][:200]}\n"
        kb = [[B("✅ تأیید", f"ao:{o['id']}", "success"), B("❌ رد", f"ar:{o['id']}", "danger")]]
        for a in self.cfg["admin_ids"]:
            await self.say(a, txt, kb)

    # ═══════════════════════════════════════════════
    #  دستورهای مشتری
    # ═══════════════════════════════════════════════
    async def user_cmd(self, uid, chat, cmd, arg, user):
        if cmd == "start":
            new = not self.db.get(uid)
            self.db.add(uid, user.get("username"), user.get("name"),
                        self.cfg["trial_days"])
            if new and self.rules_on() and not self.is_admin(uid):
                self.db.set(uid, rules_accepted=0)
            if new and self.shop and arg.startswith("r"):
                try:
                    ref = int(digits(arg))
                    if ref and self.db.get(ref) and self.shop.set_referrer(uid, ref):
                        await self.say(ref, "🎉 یک نفر با لینک تو وارد شد!")
                        msg_ref = (
                            "🎁 <b>شما با لینک دعوت وارد شدید!</b>\n" + self.LINE + "\n"
                            "برای فعال‌شدن امتیاز و دسترسی کامل، وارد بخش <b>«🎁 زیرمجموعه»</b> شوید "
                            "و شماره موبایل ایران خود را تأیید کنید."
                        )
                        await self.say(chat, msg_ref, [[B("🎁 تأیید شماره در زیرمجموعه", "m:ref", "success")]])
                except Exception:
                    pass
            if await self.enforce_join(uid, chat=chat):
                return
            if await self.enforce_rules(uid, chat=chat):
                return
            return await self.say(chat, self.home_text(uid),
                                  main_menu(self.is_admin(uid), self.cfg["shop_on"],
                                            self.cfg["points_on"],
                                            bool((self.db.get(uid) or {}).get("session")),
                                            self.sup.is_running(uid),
                                   self.trial_available(uid),
                                   trial_label=self.trial_label(),
                                   has_cmds=self.has_cmds(),
                                   has_hub=self.hub_on()))

        if cmd == "rules":
            if self.rules_required(uid):
                return await self.enforce_rules(uid, chat=chat)
            return await self.say(chat, self.rules_view_text(),
                                  [[B("⬅️ منوی اصلی", "m:home")]])

        if cmd == "trial":
            if await self.enforce_rules(uid, chat=chat):
                return
            return await self.start_trial(uid, chat)

        if cmd == "help":
            return await self.say(chat, self.cfg.get("help_text") or USER_HELP)

        if cmd in ("whoami", "id", "myid"):
            return await self.say(chat,
                f"🆔 آیدی عددی تو: <code>{uid}</code>\n"
                f"مدیر: {'✅ بله' if self.is_admin(uid) else '❌ خیر'}")

        if cmd == "cancel":
            await self.cancel(uid)
            if self.shop:
                self.shop.cancel_open(uid)
            await self.say(chat, "لغو شد.", clear_reply_keyboard())
            if await self.enforce_rules(uid, chat=chat):
                return
            return await self.say(chat, "به منوی اصلی برگشتی.",
                                  main_menu(self.is_admin(uid), self.cfg["shop_on"],
                                            self.cfg["points_on"],
                                            bool((self.db.get(uid) or {}).get("session")),
                                            self.sup.is_running(uid),
                                   self.trial_available(uid),
                                   trial_label=self.trial_label(),
                                   has_cmds=self.has_cmds(),
                                   has_hub=self.hub_on()))

        if cmd == "setup":
            if await self.enforce_rules(uid, chat=chat):
                return
            return await self.setup_start(uid, chat)

        c = self.db.get(uid)
        if not c:
            return await self.say(chat, "اول /start را بزن.")

        if cmd == "status":
            live = self.sup.is_running(uid)
            _stamp = ""
            try:
                _stamp = f"\n{self.LINE}\n<i>{build_stamp()}</i>"
            except Exception:
                pass
            return await self.say(chat,
                f"📊 <b>وضعیت شما</b>\n\n"
                f"اکانت: {c['name'] or '—'}\n"
                f"سرویس: {self.client_state(c)}\n"
                f"اعتبار: {human_left(c['expires_at'])}\n"
                + (f"امتیاز: {_fa_digits(self.shop.p_balance(uid))}  ·  "
                   f"≈{_fa_digits(self.hours_left(uid))} ساعت\n"
                   if self.shop and self.cfg["points_on"] else "")
                + f"پروسه: {'روشن' if live else 'خاموش'}\n"
                + f"ری‌استارت: {_fa_digits(c['restarts'] or 0)}" + _stamp)

        if cmd in ("on", "restart") and self.activate_points_mode(uid):
            c = self.db.get(uid)
        if c["status"] != "active":
            return await self.say(chat,
                self.cfg["expired_text"] or f"سرویس فعال نیست ({c['status']}).")

        if cmd in ("on", "off", "restart"):
            if not c["session"]:
                return await self.say(chat, "اول /setup را بزن.")
            fee_msg = ""
            if cmd == "on":
                ok, msg, fee_msg = self.start_service(
                    uid, first=not bool(c.get("started_at")),
                    restart=False, charge_success=not self.sup.is_running(uid))
            elif cmd == "off":
                ok, msg = self.sup.stop(uid, remember_off=True)
            else:
                ok, msg, fee_msg = self.start_service(
                    uid, restart=True, charge_success=False)
            extra = f"\n🎯 {fee_msg}" if fee_msg and ok else ""
            if cmd == "off" and ok:
                extra = ("\n💤 امتیازی مصرف نمی‌شود.\n"
                         f"روشن کردن دوباره: {_fa_digits(self.cfg['start_fee'])} امتیاز")
            return await self.say(chat, ("✅ " if ok else "❌ ") + msg + extra)

        if cmd == "log":
            return await self.say(chat,
                "📜 <b>گزارش</b>\n\n<pre>" +
                self.sup.tail(uid, 20).replace("<", "&lt;")[-2500:] + "</pre>")

        ADMIN_ONLY = {"card", "doctor", "fix", "sync", "users", "user", "ok",
                      "ext", "off_user", "del", "pon", "poff", "plog", "stats",
                      "say", "all", "set", "cfg", "mlog", "pending", "approve",
                      "deny", "reject", "order", "revenue", "shopplans",
                      "addplan", "editplan", "rmplan", "disc", "discs", "give",
                      "tk", "tr", "tclose", "packs", "addpack", "editpack",
                      "rmpack", "gp", "acct", "pstats", "pset", "lim", "admin", "panel",
                      "backup", "restore", "onall", "all_on",
                      "diag", "why", "diagnose", "hanglog",
                      "needlogin", "nlogin", "relogin"}
        if cmd in ADMIN_ONLY:
            return await self.say(chat,
                f"🔒 <b>{cmd}</b> فقط برای مدیر است.\n\n"
                f"آیدی عددی تو: <code>{uid}</code>\n"
                f"<i>اگر مدیری، این آیدی را در manager_config.json "
                f"داخل admin_ids بگذار و ربات را ری‌استارت کن.</i>")
        return await self.say(chat, "دستور ناشناخته. /help")

    # ═══════════════════════════════════════════════
    #  دستورهای مدیر
    # ═══════════════════════════════════════════════
    async def admin_cmd(self, uid, chat, cmd, arg, ev=None):
        p = arg.split()

        if cmd in ("backup",):
            ok, msg = await self.backup_once(force=True)
            return await self.say(chat, ("✅ " if ok else "ℹ️ ") + msg)
        if cmd in ("restore",):
            # ارجاعِ پیام: `.restore` به‌صورت ریپلای روی همان پیامِ پشتیبان،
            # یا `.restore 12345` / `.restore https://t.me/c/…/12345`.
            reply_id = None
            try:
                reply_id = (getattr(ev, "reply_to_msg_id", None)
                            or getattr(getattr(ev, "message", None),
                                       "reply_to_msg_id", None))
            except Exception:
                reply_id = None
            ref_chat, ref_mid = parse_restore_ref(arg, reply_id=reply_id)
            ok, msg = await self.restore_from_backup(
                force=True, ref_chat=ref_chat, ref_msg_id=ref_mid)
            return await self.say(chat, ("✅ " if ok else "❌ ") + msg)
        if cmd == "hanglog":
            if not self.is_admin(uid):
                return await self.say(chat, "🔒 این گزارش فقط برای مدیر است.")
            # حتی اگر دستور در گروه باشد، گزارش فقط به پیوی مدیر می‌رود.
            text = await asyncio.get_running_loop().run_in_executor(None, _hanglog_text)
            return await self.say(uid, text)
        if cmd in ("diag", "why", "diagnose"):
            return await self.say(chat, self.diag_text())
        if cmd in ("needlogin", "nlogin", "relogin"):
            try:
                rows = self.db.x("SELECT * FROM clients WHERE need_login<>0"
                                 " ORDER BY uid", (), "all")
            except Exception:
                rows = []
            if not rows:
                return await self.say(chat, "✅ هیچ اکانتی نیاز به لاگین ندارد.")
            lines = ["🔑 <b>اکانت‌هایی که باید دوباره لاگین شوند</b>",
                     f"<i>{_fa_digits(len(rows))} مورد — برای هر کدام اجرای خودکار "
                     "متوقف است تا کدِ ورود نرود.</i>", ""]
            for c in rows[:30]:
                lines.append(f"• <code>{c['uid']}</code> — "
                             f"{self._esc(c.get('name') or '—')} — "
                             f"{self._esc((c.get('phone') or '—'))}")
            if len(rows) > 30:
                lines.append(f"… و {_fa_digits(len(rows) - 30)} مورد دیگر")
            lines += ["", "👉 هر اکانت را از «🚀 راه‌اندازی سلف روی اکانتم» "
                          "دوباره لاگین کن."]
            return await self.say(chat, "\n".join(lines))
        if cmd in ("onall", "all_on"):
            # دستور عجله‌ایِ مدیر: «همه‌ی سرویس‌هایی که باید روشن باشند را
            # همین حالا روشن کن» — همان چیزی که بعد از آپدیت لازم است.
            rows = self.db.wanted()
            alive = sum(1 for c in rows if self.sup.is_running(c["uid"]))
            self.sup._resume_fail.clear()
            self._spawn_boot(notify_admins=False, why="دستور /onall")
            return await self.say(chat,
                f"🟢 <b>روشن کردن همه</b>\n{self.LINE}\n"
                f"👥 باید روشن باشند: {_fa_digits(len(rows))}\n"
                f"🟢 از قبل روشن: {_fa_digits(alive)}\n"
                f"⏳ بقیه در پس‌زمینه روشن می‌شوند.\n"
                "<i>برای دیدن نتیجه: /stats</i>")
        if cmd in ("admin", "panel"):
            sh = self.shop
            pend = len(sh.pending_orders()) if sh else 0
            tks = len(sh.open_tickets()) if sh else 0
            return await self.say(chat, "🛠 <b>پنل مدیر</b>",
                                  admin_menu(pend, tks, trial_on=bool(self.cfg.get("trial_on", True))))
        if cmd in ("ahelp", "cmds"):
            return await self.say(chat, ADMIN_HELP)
        if cmd == "menu":
            return await self.say(chat, self.home_text(uid),
                                  main_menu(True, self.cfg["shop_on"], self.cfg["points_on"],
                                            bool((self.db.get(uid) or {}).get("session")),
                                            self.sup.is_running(uid),
                                   self.trial_available(uid),
                                   trial_label=self.trial_label(),
                                   has_cmds=self.has_cmds(),
                                   has_hub=self.hub_on()))

        if cmd == "stats":
            cnt = self.db.counts()
            return await self.say(chat,
                f"📊 <b>آمار</b>\n\n"
                f"کل: {_fa_digits(sum(cnt.values()))}\n"
                f"فعال: {_fa_digits(cnt.get('active', 0))}\n"
                f"منقضی: {_fa_digits(cnt.get('expired', 0))}\n"
                f"ثبت‌نام‌نشده: {_fa_digits(cnt.get('new', 0))}\n"
                f"مسدود: {_fa_digits(cnt.get('banned', 0))}\n\n"
                f"پروسه‌های روشن: {_fa_digits(self.sup.running_count())}"
                f"/{_fa_digits(self.cfg['max_clients'])}")

        if cmd == "users":
            rows = self.db.all()
            if not rows:
                return await self.say(chat, "مشتری‌ای نیست.")
            out = [f"👥 <b>مشتری‌ها ({_fa_digits(len(rows))})</b>", ""]
            for c in rows[:40]:
                live = "🟢" if self.sup.is_running(c["uid"]) else "⚪"
                out.append(f"{live} <code>{c['uid']}</code> {c['name'] or '—'}")
                out.append(f"     {c['status']} • {human_left(c['expires_at'])}")
            return await self.say(chat, "\n".join(out))

        if cmd == "user":
            if not p:
                return await self.say(chat, "/user 123456  (یا @username یا شماره)")
            matches = self._resolve_admin_users(arg)
            if not matches:
                return await self.say(chat, "پیدا نشد.")
            c = matches[0]
            st = self.sup.read_status(c["uid"])
            live = ""
            if st and st.get("age", 999) < 600:
                q = st.get("queue", {})
                ex = st.get("exchange", {})
                live = (f"\n{self.LINE}\n<b>گزارش زنده</b>\n"
                        f"پلن سلف: {st.get('plan') or '—'}\n"
                        f"کانال: {st.get('channels', {}).get('standard') or '—'}\n"
                        f"صف: {_fa_digits(q.get('pending', 0))} · "
                        f"ارسال 24س: {_fa_digits(st.get('sent_24h', 0))} · "
                        f"کل: {_fa_digits(q.get('sent', 0))}\n"
                        f"تبادل: {'روشن' if ex.get('on') else 'خاموش'} · "
                        f"{_fa_digits(ex.get('joined', 0))} جوین\n"
                        f"AI: {'✅' if st.get('ai') else '❌'} · "
                        f"سن گزارش: {_fa_digits(st.get('age', 0))} ثانیه")
                if st.get("last_error"):
                    live += f"\n⚠️ {st['last_error'][:80]}"
            return await self.say(chat,
                f"👤 <b>{self._esc(c.get('name') or '—')}</b>\n\n"
                f"uid: <code>{c['uid']}</code>\n"
                f"یوزرنیم: @{self._esc(c.get('username') or '—')}\n"
                f"شماره: {self._esc(c.get('phone') or '—')}\n"
                f"وضعیت: {self.client_state(c)}\n"
                f"اعتبار: {human_left(c.get('expires_at') or 0)}\n"
                f"سشن: {'✅' if c.get('session') else '❌'}\n"
                f"جفج/تبادل: {self._jafj_summary_line(c['uid'])}\n"
                f"ری‌استارت: {_fa_digits(c.get('restarts') or 0)}\n"
                f"عضویت: {local_dt(c.get('created_at') or now()):%Y-%m-%d}" + live,
                [[B("⚙️ پنل مدیریت کاربر", f"au:{c['uid']}", "primary"),
                  B("🗑 پاک کردن اطلاعات", f"aud:{c['uid']}", "danger")]])

        if cmd in ("ok", "ext"):
            if not p:
                return await self.say(chat, f"/{cmd} 123456 30")
            tid = int(digits(p[0]) or 0)
            days = int(digits(p[1])) if len(p) > 1 else 30
            c = self.db.get(tid)
            if not c:
                return await self.say(chat, "پیدا نشد.")
            base = max(c["expires_at"], now()) if cmd == "ext" else now()
            self.db.set(tid, expires_at=base + days * 86400, status="active",
                        current_plan_id=0, trial_expires_at=0)
            self.db.log(tid, cmd, f"{days} روز")
            self.sup.write_limits(tid, self.effective_plan(tid) or
                                  {"name": "اشتراک دستی", "max_accounts": 1})
            if c["session"]:
                self.sup.start(tid)
            await self.say(tid, f"✅ سرویس شما {_fa_digits(days)} روز فعال شد.")
            return await self.say(chat,
                f"✅ {tid} → {human_left(self.db.get(tid)['expires_at'])}")

        if cmd == "off_user":
            tid = int(digits(p[0]) or 0) if p else 0
            self.sup.stop(tid)
            self.db.set(tid, status="banned")
            self.db.log(tid, "banned")
            return await self.say(chat, f"⛔ {tid} غیرفعال شد.")

        if cmd in ("del", "wipe", "deluser", "rmuser"):
            if not arg.strip():
                return await self.say(chat, "فرمت: <code>/del 123456</code>  (یا @username یا شماره)")
            matches = self._resolve_admin_users(arg)
            if not matches:
                return await self.say(chat, "کاربر پیدا نشد.")
            if len(matches) > 1 and not digits(arg.strip()) == arg.strip():
                kb = [[B(f"🗑 {m.get('name') or m['uid']} ({m['uid']})", f"aud:{m['uid']}", "danger")]
                      for m in matches[:6]]
                return await self.say(chat, "چند کاربر پیدا شد؛ یکی را انتخاب کن:", kb)
            tid = matches[0]["uid"]
            ok, msg, _st = await self.wipe_user_data(tid, by_admin=uid)
            return await self.say(chat, msg if ok else f"❌ {msg}")

        if cmd in ("resetjafj", "deljafj", "wipejafj", "clearjafj"):
            if not arg.strip():
                return await self.say(chat, "فرمت: <code>/resetjafj 123456</code>  (یا @username یا شماره)")
            matches = self._resolve_admin_users(arg)
            if not matches:
                return await self.say(chat, "کاربر پیدا نشد.")
            if len(matches) > 1 and not digits(arg.strip()) == arg.strip():
                kb = [[B(f"🧹 {m.get('name') or m['uid']} ({m['uid']})", f"auj:{m['uid']}", "danger")]
                      for m in matches[:6]]
                return await self.say(chat, "چند کاربر پیدا شد؛ یکی را انتخاب کن:", kb)
            tid = matches[0]["uid"]
            ok, msg, _st = await self.wipe_user_jafj(tid, by_admin=uid)
            return await self.say(chat, msg if ok else f"❌ {msg}",
                                  [[B("👤 مشتری", f"au:{tid}", "primary")]])

        if cmd in ("pon", "poff"):
            tid = int(digits(p[0]) or 0) if p else 0
            if cmd == "pon":
                ok, msg, _ = self.start_service(tid, charge_success=False)
            else:
                ok, msg = self.sup.stop(tid, remember_off=True)
            return await self.say(chat, ("✅ " if ok else "❌ ") + msg)

        if cmd == "plog":
            tid = int(digits(p[0]) or 0) if p else 0
            return await self.say(chat, "<pre>" +
                self.sup.tail(tid, 30).replace("<", "&lt;")[-3000:] + "</pre>")

        if cmd == "say":
            if len(p) < 2:
                return await self.say(chat, "/say 123456 متن")
            tid = int(digits(p[0]) or 0)
            ok = await self.say(tid, arg.split(None, 1)[1])
            return await self.say(chat, "✅ رفت" if ok else "❌ نرسید")

        if cmd == "all":
            if not arg:
                return await self.say(chat, "/all متن")
            n = 0
            for c in self.db.all():
                if await self.say(c["uid"], arg):
                    n += 1
                await asyncio.sleep(0.15)
            return await self.say(chat, f"✅ به {_fa_digits(n)} نفر رسید.")

        if cmd == "cfg":
            safe = {k: v for k, v in self.cfg.d.items()
                    if k not in ("bot_token", "api_hash")}
            return await self.say(chat, "<pre>" +
                json.dumps(safe, ensure_ascii=False, indent=2) + "</pre>")

        if cmd == "set":
            if len(p) < 2:
                return await self.say(chat, "/set trial_days 7")
            k, v = p[0], " ".join(p[1:])
            if k not in DEFAULTS:
                return await self.say(chat, f"کلید ناشناخته: {k}")
            cur = DEFAULTS[k]
            try:
                if isinstance(cur, bool):
                    v = v.lower() in ("1", "true", "on", "روشن")
                elif isinstance(cur, int):
                    v = int(digits(v))
                elif isinstance(cur, list):
                    v = [int(digits(x)) for x in v.split()]
            except Exception:
                return await self.say(chat, "مقدار نامعتبر.")
            self.cfg[k] = v
            return await self.say(chat, f"✅ {k} = {v}")

        if cmd == "mlog":
            rows = self.db.recent(20)
            if not rows:
                return await self.say(chat, "رویدادی نیست.")
            return await self.say(chat, "📜 <b>رویدادها</b>\n\n" + "\n".join(
                f"<code>{local_dt(r['ts']):%m-%d %H:%M}</code> "
                f"{r['uid']} {r['kind']} {(r['detail'] or '')[:30]}"
                for r in rows))

        return None


    # ═══════════════════════════════════════════════
    #  فروشگاه — مدیر
    # ═══════════════════════════════════════════════
    async def shop_admin(self, uid, chat, cmd, arg):
        if not self.shop:
            return None
        sh = self.shop
        p = arg.split()

        if cmd == "pending":
            rows = sh.pending_orders()
            if not rows:
                return await self.say(chat, "سفارش منتظری نیست ✅")
            out = [f"📤 <b>منتظر تأیید ({_fa_digits(len(rows))})</b>", ""]
            for o in rows:
                c = self.db.get(o["uid"])
                ic = {"wallet": "💳", "points": "🎯"}.get(o.get("kind"), "💎")
                out.append(f"{ic} #{_fa_digits(o['id'])} — {money(o['final'])} — "
                           f"{o['plan_name']}")
                out.append(f"     <code>{o['uid']}</code> {c['name'] if c else ''}")
                out.append(f"     ✅ <code>/approve {o['id']}</code>  "
                           f"❌ <code>/deny {o['id']}</code>")
                out.append("")
            return await self.say(chat, "\n".join(out))

        if cmd == "order":
            if not p:
                return await self.say(chat, "/order 12")
            o = sh.order(int(digits(p[0]) or 0))
            if not o:
                return await self.say(chat, "پیدا نشد.")
            c = self.db.get(o["uid"])
            txt = (f"🧾 <b>سفارش #{_fa_digits(o['id'])}</b>\n\n"
                   f"مشتری: <code>{o['uid']}</code> {c['name'] if c else ''}\n"
                   f"پلن: {o['plan_name']} — {_fa_digits(o['days'])} روز\n"
                   f"مبلغ اصلی: {money(o['amount'])}\n"
                   f"تخفیف: {o['discount_code'] or '—'} (-{money(o['discount_off'])})\n"
                   f"کیف پول: -{money(o['wallet_used'])}\n"
                   f"<b>نهایی: {money(o['final'])}</b>\n"
                   f"وضعیت: {o['status']}\n"
                   f"تاریخ: {local_dt(o['created_at']):%Y-%m-%d %H:%M}")
            if o["note"]:
                txt += f"\nیادداشت: {o['note']}"
            if o["receipt_file"]:
                try:
                    return await self.bot.send_file(chat, o["receipt_file"],
                                                    caption=txt, parse_mode="html")
                except Exception:
                    pass
            if o["receipt_text"]:
                txt += f"\n\nرسید: {o['receipt_text'][:400]}"
            return await self.say(chat, txt)

        if cmd == "approve":
            if not p:
                return await self.say(chat, "/approve 12")
            oid = int(digits(p[0]) or 0)
            o, err = sh.approve(oid, uid)
            if err:
                return await self.say(chat, f"❌ {err}")
            # ---- شارژ کیف پول ----
            if o.get("kind") == "wallet":
                nb = sh.credit(o["uid"], o["amount"], "topup",
                               f"شارژ · سفارش #{oid}")
                ref, rew = sh.pay_referral(oid, self.cfg["referral_percent"])
                if ref:
                    await self.say(ref, f"🎁 زیرمجموعه‌ات شارژ کرد!\n"
                                        f"{money(rew)} به کیف پولت اضافه شد.")
                await self.say(o["uid"],
                    f"✅ <b>کیف پولت شارژ شد</b>\n{self.LINE}\n"
                    f"➕ {money(o['amount'])}\n"
                    f"موجودی: <b>{money(nb)}</b>\n{self.LINE}\n\n"
                    f"<i>می‌توانی هنگام خرید اشتراک یا امتیاز خرجش کنی.</i>",
                    [[B("💳 کیف پول", "m:wallet", "primary")]])
                # آموزش‌های «بعد از شارژ کیف پول»
                self.tut_schedule(o["uid"], "after_wallet", wait=3)
                return await self.say(chat,
                    f"✅ سفارش #{_fa_digits(oid)} تأیید شد — {money(o['final'])}\n"
                    f"💳 کیف پول {o['uid']}: {money(nb)}")

            # ---- خرید امتیاز ----
            if o.get("kind") == "points":
                had_sub = self.has_sub(o["uid"])
                nb = sh.p_add(o["uid"], o["points"], "buy",
                              f"{o['plan_name']} · سفارش #{oid}")
                c = self.db.get(o["uid"])
                if c:
                    if not had_sub:
                        self.db.set(o["uid"], status="active", expires_at=0,
                                    current_plan_id=0, trial_expires_at=0)
                        self.sync_points_limits(o["uid"])
                    else:
                        # خرید امتیاز نباید اشتراک فعال را پاک کند.
                        self.db.set(o["uid"], status="active")
                    self.db.log(o["uid"], "points_buy", f"+{o['points']}")
                ref, rew = sh.pay_referral(oid, self.cfg["referral_percent"])
                if ref:
                    await self.say(ref, f"🎁 زیرمجموعه‌ات خرید کرد!\n"
                                        f"{money(rew)} به کیف پولت اضافه شد.")
                per = max(1, self.cfg["cost_per_hour"])
                started = False
                if c and c["session"] and nb >= self.cfg["min_points"] \
                        and not self.sup.is_running(o["uid"]):
                    started, _, _ = self.start_service(
                        o["uid"], restart=False, charge_success=False)
                await self.say(o["uid"],
                    f"✅ <b>پرداختت تأیید شد</b>\n{self.LINE}\n"
                    f"🎯 <b>+{_fa_digits(o['points'])} امتیاز</b>\n"
                    f"موجودی: <b>{_fa_digits(nb)}</b>  ·  ≈{_fa_digits(nb // per)} ساعت\n"
                    f"{self.LINE}\n\n" +
                    ("🟢 سرویست روشن شد." if started else
                     ("💡 حالا می‌توانی سرویس را روشن کنی."
                      if c and c["session"] else
                      "🚀 حالا سلف را روی اکانتت راه بینداز.")),
                    [[B("🎯 امتیاز من", "m:pts", "success")]] if c and c["session"]
                    else [[B("🚀 راه‌اندازی سلف", "s:setup", "primary")]])
                # آموزش‌های «بعد از خرید امتیاز»
                self.tut_schedule(o["uid"], "after_points", wait=3)
                return await self.say(chat,
                    f"✅ سفارش #{_fa_digits(oid)} تأیید شد — {money(o['final'])}\n"
                    f"🎯 {_fa_digits(o['points'])} امتیاز به {o['uid']} اضافه شد "
                    f"(موجودی {_fa_digits(nb)})")

            # فعال‌سازی سرویس
            c = self.db.get(o["uid"])
            if c:
                base = max(c["expires_at"], now()) if c["expires_at"] else now()
                self.db.set(o["uid"], expires_at=base + o["days"] * 86400,
                            status="active", current_plan_id=o["plan_id"] or 0,
                            trial_expires_at=0)
                self.db.log(o["uid"], "paid", f"order #{oid} {o['final']}")
                pl = sh.plan(o["plan_id"])
                if pl:
                    # اگر مدیر برای این کاربر سقف اکانتِ سفارشی گذاشته (max_accounts>0),
                    # همان حفظ شود؛ وگرنه سقفِ پلنِ خریداری‌شده (که اکنون همگی ۱ است).
                    ua = int((self.db.get(o["uid"]) or {}).get("max_accounts") or 0)
                    self.sup.write_limits(o["uid"], pl, override_max_accounts=ua)
                if c["session"]:
                    self.sup.restart(o["uid"]) if self.sup.is_running(o["uid"]) \
                        else self.sup.start(o["uid"])
            # پاداش معرف
            ref, rew = sh.pay_referral(oid, self.cfg["referral_percent"])
            if ref:
                await self.say(ref, f"🎁 زیرمجموعه‌ات خرید کرد!\n"
                                    f"{money(rew)} به کیف پولت اضافه شد.\n"
                                    f"موجودی: {money(sh.balance(ref))}")
            nc = self.db.get(o["uid"])
            await self.say(o["uid"],
                f"✅ <b>پرداختت تأیید شد</b>\n\n"
                f"پلن: {o['plan_name']}\n"
                f"اعتبار: {human_left(nc['expires_at'])}\n\n" +
                ("سرویست روشن شد 🟢" if c and c["session"]
                 else "حالا سلف را روی اکانتت راه بینداز."),
                [[B("⚙️ سرویس من", "m:svc", "primary")]] if c and c["session"]
                else [[B("🚀 راه‌اندازی سلف", "s:setup", "primary")]])
            # آموزش‌های «بعد از خرید اشتراک ماهانه»
            self.tut_schedule(o["uid"], "after_sub", wait=3)
            return await self.say(chat,
                f"✅ سفارش #{_fa_digits(oid)} تأیید شد — {money(o['final'])}\n"
                f"اعتبار مشتری: {human_left(nc['expires_at'])}")

        if cmd in ("deny", "reject"):
            if not p:
                return await self.say(chat, "/deny 12 دلیل")
            oid = int(digits(p[0]) or 0)
            reason = arg.split(None, 1)[1] if len(p) > 1 else "رسید تأیید نشد"
            o, err = sh.reject(oid, uid, reason)
            if err:
                return await self.say(chat, f"❌ {err}")
            await self.say(o["uid"], f"❌ سفارش #{_fa_digits(oid)} تأیید نشد.\n"
                                     f"دلیل: {reason}\n\n"
                                     f"می‌توانی دوباره تلاش کنی: /plans")
            return await self.say(chat, f"❌ سفارش #{_fa_digits(oid)} رد شد.")

        if cmd == "revenue":
            st = sh.stats()
            avg = st['all'][1] // st['all'][0] if st['all'][0] else 0
            return await self.say(chat,
                f"💰 <b>گزارش درآمد</b>\n{self.LINE}\n"
                f"📅  24 ساعت    {_fa_digits(st['day'][0])} × {money(st['day'][1])}\n"
                f"📆  7 روز        {_fa_digits(st['week'][0])} × {money(st['week'][1])}\n"
                f"🗓  30 روز       {_fa_digits(st['month'][0])} × {money(st['month'][1])}\n"
                f"{self.LINE}\n"
                f"🏆  <b>کل        {money(st['all'][1])}</b>\n"
                f"      {_fa_digits(st['all'][0])} سفارش · میانگین {money(avg)}\n"
                f"{self.LINE}\n"
                f"📤  منتظر تأیید   {_fa_digits(st['orders'].get('paid', 0))}\n"
                f"❌  رد شده        {_fa_digits(st['orders'].get('rejected', 0))}\n"
                f"💳  کیف پول‌ها     {money(st['wallet_total'])}")

        if cmd == "shopplans":
            out = ["📦 <b>پلن‌ها</b>", ""]
            for x in sh.plans(all_=True):
                out.append(f"{'🟢' if x['active'] else '⚪'} <code>{x['id']}</code> "
                           f"{x['name']} — {_fa_digits(x['days'])} روز — {money(x['price'])} "
                           f"— {_fa_digits(x['max_accounts'])} اکانت")
            out += ["", "<code>/addplan نام|روز|قیمت|اکانت|توضیح</code>",
                    "<code>/editplan 2 price 200000</code>", "<code>/rmplan 2</code>"]
            return await self.say(chat, "\n".join(out))

        if cmd == "addplan":
            parts = [t.strip() for t in arg.split("|")]
            if len(parts) < 3:
                return await self.say(chat,
                    "<code>/addplan طلایی|180|690000|1|یک اکانت</code>")
            try:
                pid = sh.add_plan(parts[0], int(digits(parts[1])),
                                  int(digits(parts[2])),
                                  int(digits(parts[3])) if len(parts) > 3 else 1,
                                  parts[4] if len(parts) > 4 else "")
            except Exception as e:
                return await self.say(chat, f"❌ {e}")
            return await self.say(chat, f"✅ پلن #{pid} اضافه شد.")

        if cmd == "editplan":
            if len(p) < 3:
                return await self.say(chat, "<code>/editplan 2 price 200000</code>")
            pid = int(digits(p[0]) or 0)
            k, v = p[1], " ".join(p[2:])
            if k not in ("name", "days", "price", "max_accounts", "features",
                         "active", "sort"):
                return await self.say(chat, "کلید نامعتبر.")
            if k != "name" and k != "features":
                v = int(digits(v) or 0)
            sh.set_plan(pid, **{k: v})
            return await self.say(chat, f"✅ پلن {pid}: {k} = {v}")

        if cmd == "rmplan":
            sh.del_plan(int(digits(p[0]) or 0) if p else 0)
            return await self.say(chat, "✅ حذف شد.")

        if cmd == "disc":
            if not p:
                return await self.say(chat,
                    "<code>/disc OFF20 20</code> — 20٪\n"
                    "<code>/disc GIFT 0 50000</code> — 50 هزار تومان\n"
                    "<code>/disc VIP 30 0 10 7</code> — 30٪، 10 بار، 7 روز")
            code = p[0].upper()
            pc = int(digits(p[1])) if len(p) > 1 else 0
            fl = int(digits(p[2])) if len(p) > 2 else 0
            mx = int(digits(p[3])) if len(p) > 3 else 0
            dv = int(digits(p[4])) if len(p) > 4 else 0
            sh.add_discount(code, pc, fl, mx, dv)
            return await self.say(chat,
                f"✅ کد <code>{code}</code>\n"
                f"تخفیف: {_fa_digits(pc)}٪" + (f" + {money(fl)}" if fl else "") +
                f"\nسقف استفاده: {_fa_digits(mx) if mx else 'نامحدود'}"
                f"\nاعتبار: {_fa_digits(dv) + ' روز' if dv else 'نامحدود'}")

        if cmd == "discs":
            rows = sh.discounts()
            if not rows:
                return await self.say(chat, "کدی نیست.")
            return await self.say(chat, "🎟 <b>کدها</b>\n\n" + "\n".join(
                f"{'🟢' if d['active'] else '⚪'} <code>{d['code']}</code> "
                f"{_fa_digits(d['percent'])}٪"
                + (f"+{money(d['flat'])}" if d['flat'] else "")
                + f" — {_fa_digits(d['used'])}/{_fa_digits(d['max_uses']) if d['max_uses'] else '∞'}"
                for d in rows))

        if cmd == "give":
            if len(p) < 2:
                return await self.say(chat, "/give 123456 50000")
            tid = int(digits(p[0]) or 0)
            amt = int(digits(p[1]) or 0)
            bal = sh.credit(tid, amt, "admin", "هدیه مدیر")
            await self.say(tid, f"🎁 {money(amt)} به کیف پولت اضافه شد.\n"
                                f"موجودی: {money(bal)}")
            return await self.say(chat, f"✅ موجودی {tid}: {money(bal)}")

        if cmd == "gp":
            if len(p) < 2:
                return await self.say(chat, "<code>/gp 123456 20</code> — دادن امتیاز (هدیه)")
            tid = int(digits(p[0]) or 0)
            amt = int(digits(p[1]) or 0)
            nb = sh.p_add(tid, amt, "bonus", "هدیه مدیر")
            self.sync_points_limits(tid)
            await self.say(tid, f"🎯 <b>+{_fa_digits(amt)} امتیاز هدیه</b> گرفتی!\n"
                                f"موجودی: {_fa_digits(nb)}",
                           [[B("🎯 امتیاز من", "m:pts", "success")]])
            return await self.say(chat, f"✅ امتیاز هدیه {tid}: +{_fa_digits(amt)} → {_fa_digits(nb)}")

        if cmd == "acct":
            if len(p) < 2:
                return await self.say(chat,
                    "<code>/acct 123456 3</code> — تعیین سقف اکانت برای یک کاربر\n"
                    "<code>/acct 123456</code> — دیدن سقف فعلی\n"
                    "<code>/acct 123456 0</code> — برگرداندن به سقفِ پلن")
            tid = int(digits(p[0]) or 0)
            c = self.db.get(tid)
            if not c:
                return await self.say(chat, "کاربر پیدا نشد.")
            cur = int(c.get("max_accounts") or 0)
            if len(p) == 2:
                base = self.effective_plan(tid)
                plan_mx = int(base.get("max_accounts", 1) or 1) if base else 1
                eff = cur if cur > 0 else plan_mx
                return await self.say(chat,
                    f"👤 <b>{c['name'] or '—'}</b> (uid {tid})\n"
                    f"سقف اکانتِ خودش: <b>{cur if cur > 0 else '— (از پلن)'}</b>\n"
                    f"سقفِ پلن: <b>{_fa_digits(plan_mx)}</b>  ·  اثر فعلی: <b>{_fa_digits(eff)}</b>\n\n"
                    "برای تغییر: <code>/acct 123456 3</code>")
            v = max(0, int(digits(p[1]) or 0))
            self.db.set(tid, max_accounts=v)
            if v > 0:
                # سقفِ سفارشی برای همین کاربر؛ اولویت بر پلنِ جهانی.
                self.sup.write_limits(tid, {"name": "سفارشی", "max_accounts": v},
                                      override_max_accounts=v)
            else:
                # برگردان به پلنِ جهانی. اگر کاربر در حالتِ امتیازی است،
                # همان حالت حفظ شود (نه پلنِ عادی).
                if (self.cfg.get("points_on") and self.shop
                        and not self.has_sub(tid)):
                    bal = self.shop.p_balance(tid)
                    per = max(1, int(self.cfg["cost_per_hour"]))
                    self.sup.write_limits(tid, None, points_mode=True,
                                          points=bal, hours_left=bal // per)
                else:
                    best = self.effective_plan(tid) or {"name": "", "max_accounts": 1}
                    self.sup.write_limits(tid, best)
            if self.sup.is_running(tid):
                await self.sup.restart(tid)
            return await self.say(chat,
                f"✅ سقف اکانتِ {tid} → <b>{_fa_digits(v)}</b>"
                + (" (از پلن)" if v == 0 else ""))

        if cmd == "lim":
            if not p:
                return await self.say(chat,
                    "<code>/lim 123456</code> — دیدن سقف‌ها\n"
                    "<code>/lim 123456 max_per_hour 30</code> — تغییر\n"
                    "<code>/lim 123456 exchange 0</code> — خاموش کردن\n\n"
                    "کلیدها: plan · max_channels · max_per_hour · min_gap_sec\n"
                    "exchange · initiate · max_joins_per_day · ai")
            tid = int(digits(p[0]) or 0)
            path = os.path.join(self.sup.folder(tid), "jafj_limits.json")
            cur = {}
            if os.path.exists(path):
                try:
                    cur = json.load(open(path, encoding="utf-8"))
                except Exception:
                    pass
            if len(p) < 3:
                if not cur:
                    return await self.say(chat, "سقفی تنظیم نشده.")
                return await self.say(chat,
                    f"📦 <b>سقف‌های {tid}</b>\n\n<pre>" +
                    json.dumps(cur, ensure_ascii=False, indent=2) + "</pre>")
            k, v = p[1], " ".join(p[2:])
            if k not in ("plan", "max_channels", "max_per_hour", "min_gap_sec",
                         "exchange", "initiate", "max_joins_per_day", "ai"):
                return await self.say(chat, "کلید نامعتبر.")
            if k in ("exchange", "initiate", "ai"):
                cur[k] = v.lower() in ("1", "true", "on", "روشن", "بله")
            elif k == "plan":
                cur[k] = v
            else:
                cur[k] = int(digits(v) or 0)
            try:
                with open(path, "w", encoding="utf-8") as f:
                    json.dump(cur, f, ensure_ascii=False, indent=2)
            except Exception as e:
                return await self.say(chat, f"❌ {e}")
            if self.sup.is_running(tid):
                self.sup.restart(tid)
            return await self.say(chat,
                f"✅ سقف {tid}: {k} = {cur[k]}\n<i>سرویس ری‌استارت شد.</i>")

        if cmd in ("doctor", "check", "سلامت"):
            L = ["🩺 <b>بررسی سلامت سیستم</b>", self.LINE]
            ok_all = True

            def line(good, name, detail=""):
                nonlocal ok_all
                if not good:
                    ok_all = False
                L.append(f"{'✅' if good else '❌'} {name}"
                         + (f"\n     <i>{detail}</i>" if detail else ""))

            # فایل‌ها
            found = os.path.isfile(SELFBOT)
            line(found, f"فایل سلف ({SELF_NAME})",
                 "" if found else
                 f"{SELFBOT} نیست — فایل {SELF_NAME} باید کنار manager_82.py "
                 f"در ایمیج باشد (نسخه مرجع: {SELFBOT_REF})")
            line(True, "موتور فروشگاه (داخلی)")
            try:
                import telethon
                line(True, f"Telethon {telethon.__version__}")
            except ImportError:
                line(False, "Telethon", "pip install telethon")

            # تنظیمات
            line(bool(self.cfg["bot_token"]), "توکن ربات")
            line(bool(self.cfg["api_id"] and self.cfg["api_hash"]),
                 "api_id / api_hash",
                 "" if self.cfg["api_id"] else "برای ورود مشتری‌ها لازم است")
            line(bool(self.cfg["admin_ids"]), "مدیر تعریف شده")
            line(bool(self.cfg["card_number"]), "شماره کارت",
                 "" if self.cfg["card_number"] else "بدون آن خرید کار نمی‌کند: /card")
            line(bool(self.cfg["card_name"]), "نام صاحب کارت")

            # فروشگاه
            if sh:
                line(len(sh.plans()) > 0, f"پلن فعال ({_fa_digits(len(sh.plans()))})")
                if self.cfg["points_on"]:
                    line(len(sh.packs()) > 0,
                         f"بسته امتیاز ({_fa_digits(len(sh.packs()))})")

            # امتیاز
            if self.cfg["points_on"]:
                per = max(1, self.cfg["cost_per_hour"])
                mn = self.cfg["min_points"]
                fee = self.cfg["start_fee"]
                line(mn >= per, "حداقل امتیاز منطقی",
                     f"حداقل {_fa_digits(mn)} = {_fa_digits(mn // per)} ساعت کارکرد")
                line(mn >= fee, "حداقل ≥ هزینه روشن کردن",
                     f"حداقل {_fa_digits(mn)} · هزینه روشن {_fa_digits(fee)}")

            # دیتابیس و پوشه‌ها
            line(os.path.isdir(CLIENTS_DIR), f"پوشه مشتری‌ها ({CLIENTS_DIR})")
            try:
                self.db.counts()
                line(True, "دیتابیس مدیر")
            except Exception as e:
                line(False, "دیتابیس مدیر", str(e))

            # سرویس‌ها
            L.append(self.LINE)
            runnable = self.db.runnable()
            live = self.sup.running_count()
            L.append(f"👥 مشتری با سشن: {_fa_digits(len(runnable))}")
            L.append(f"🟢 در حال کار: {_fa_digits(live)}")
            stuck = []
            for c in runnable:
                allow, why = self.can_run(c["uid"])
                running = self.sup.is_running(c["uid"])
                if allow and not running:
                    stuck.append((c["uid"], "باید روشن باشد ولی نیست"))
                elif not allow and running:
                    stuck.append((c["uid"], f"روشن است ولی {why}"))
            if stuck:
                L.append(f"\n⚠️ <b>ناهماهنگی ({_fa_digits(len(stuck))})</b>")
                for u, w in stuck[:6]:
                    L.append(f"   <code>{u}</code> — {w}")
                L.append(f"\nاصلاح خودکار: <code>/fix</code>")
            else:
                L.append("✅ همه سرویس‌ها هماهنگ‌اند")

            # گزارش‌های زنده
            fresh = stale = 0
            for c in runnable:
                st2 = self.sup.read_status(c["uid"])
                if st2 and st2.get("age", 999) < 300:
                    fresh += 1
                elif self.sup.is_running(c["uid"]):
                    stale += 1
            if fresh or stale:
                L.append(f"📡 گزارش زنده: {_fa_digits(fresh)} تازه"
                         + (f" · ⚠️ {_fa_digits(stale)} کهنه" if stale else ""))

            # فایل‌های مشتری‌ها
            miss = []
            for c in runnable[:50]:
                f = self.sup.folder(c["uid"])
                for need in ("jafj.session", "jafj_creds.json", SELF_NAME):
                    if not os.path.exists(os.path.join(f, need)):
                        miss.append(f"{c['uid']}: {need}")
            if miss:
                L.append(f"\n⚠️ فایل ناقص: {_fa_digits(len(miss))}")
                for x in miss[:5]:
                    L.append(f"   <code>{x}</code>")

            L.append(self.LINE)
            L.append("🟢 <b>همه‌چیز آماده است</b>" if ok_all
                     else "🔴 <b>موارد ❌ را درست کن</b>")
            return await self.say(chat, "\n".join(L))

        if cmd == "fix":
            fixed = []
            for c in self.db.runnable():
                uid2 = c["uid"]
                allow, why = self.can_run(uid2)
                running = self.sup.is_running(uid2)
                if allow and not running:
                    if sh:
                        sh.p_reset_charge(uid2)
                    okk, why_start, _ = self.start_service(uid2, charge_success=False)
                    fixed.append(f"▶️ {uid2} روشن شد" if okk else
                                 f"⚠️ {uid2}: {why_start[:120]}")
                elif not allow and running:
                    self.sup.stop(uid2)
                    fixed.append(f"⏹ {uid2} خاموش شد ({why})")
                # فایل‌های گمشده
                f = self.sup.folder(uid2)
                if c["session"] and not os.path.exists(
                        os.path.join(f, "jafj.session")):
                    try:
                        self.sup.prepare(uid2, c["session"], c["phone"] or "")
                        fixed.append(f"🔧 {uid2} فایل‌ها بازسازی شد")
                    except Exception as e:
                        fixed.append(f"❌ {uid2}: {e}")
                if not os.path.exists(os.path.join(f, SELF_NAME)):
                    try:
                        self.sup.prepare(uid2, c["session"], c["phone"] or "")
                    except Exception as e:
                        fixed.append(f"⚠️ {uid2}: سشن معتبر نیست ({type(e).__name__})")
            if not fixed:
                return await self.say(chat, "✅ چیزی برای اصلاح نبود.")
            return await self.say(chat, "🔧 <b>اصلاح شد</b>\n\n" + "\n".join(fixed[:25]))

        if cmd == "sync":
            n = 0
            for c in self.db.runnable():
                if self.sup.write_ai(c["uid"]):
                    n += 1
            return await self.say(chat,
                f"🔄 فایل AI برای {_fa_digits(n)} مشتری بروزرسانی شد.")

        if cmd == "packs":
            per = max(1, self.cfg["cost_per_hour"])
            out = ["📦 <b>بسته‌های امتیاز</b>", self.LINE]
            for k in sh.packs(all_=True):
                tot = k["points"] + k["bonus"]
                out.append(f"{'🟢' if k['active'] else '⚪'} <code>{k['id']}</code> "
                           f"{k['name']} — {_fa_digits(k['points'])}"
                           + (f"+{_fa_digits(k['bonus'])}🎁" if k["bonus"] else "")
                           + f" = {_fa_digits(tot)} امتیاز ({_fa_digits(tot // per)} ساعت)"
                           f" — {money(k['price'])}")
            out += ["", "<code>/addpack نام|امتیاز|قیمت|هدیه</code>",
                    "<code>/editpack 2 price 200000</code>", "<code>/rmpack 2</code>"]
            return await self.say(chat, "\n".join(out))

        if cmd == "addpack":
            parts = [t.strip() for t in arg.split("|")]
            if len(parts) < 3:
                return await self.say(chat,
                    "<code>/addpack بسته بزرگ|400|390000|80</code>")
            try:
                kid = sh.add_pack(parts[0], int(digits(parts[1])),
                                  int(digits(parts[2])),
                                  int(digits(parts[3])) if len(parts) > 3 else 0)
            except Exception as e:
                return await self.say(chat, f"❌ {e}")
            return await self.say(chat, f"✅ بسته #{kid} اضافه شد.")

        if cmd == "editpack":
            if len(p) < 3:
                return await self.say(chat, "<code>/editpack 2 price 200000</code>")
            kid = int(digits(p[0]) or 0)
            k, v = p[1], " ".join(p[2:])
            if k not in ("name", "points", "bonus", "price", "active", "sort"):
                return await self.say(chat, "کلید نامعتبر.")
            if k != "name":
                v = int(digits(v) or 0)
            sh.set_pack(kid, **{k: v})
            return await self.say(chat, f"✅ بسته {kid}: {k} = {v}")

        if cmd == "rmpack":
            sh.del_pack(int(digits(p[0]) or 0) if p else 0)
            return await self.say(chat, "✅ حذف شد.")

        if cmd == "pstats":
            st = sh.p_stats()
            per = max(1, self.cfg["cost_per_hour"])
            top = sh.p_top(5)
            return await self.say(chat,
                f"🎯 <b>آمار امتیاز</b>\n{self.LINE}\n"
                f"👥  کاربر        {_fa_digits(st['c'])}\n"
                f"💰  در گردش      {_fa_digits(st['b'])}\n"
                f"📈  کل کسب‌شده   {_fa_digits(st['e'])}\n"
                f"📉  کل مصرف‌شده  {_fa_digits(st['s'])}\n"
                f"{self.LINE}\n"
                f"⚡️ هر ساعت {_fa_digits(per)} امتیاز · حداقل فعال‌سازی "
                f"{_fa_digits(self.cfg['min_points'])}\n"
                f"{self.LINE}\n<b>برترین‌ها</b>\n" +
                "\n".join(f"{i+1}. <code>{r['uid']}</code> — "
                          f"{_fa_digits(r['earned'])} کسب / {_fa_digits(r['balance'])} مانده"
                          for i, r in enumerate(top)))

        if cmd == "pset":
            keys = ("points_on", "cost_per_hour", "min_points", "start_fee",
                    "self_error_fee", "low_warn")
            if len(p) < 2:
                cur = "\n".join(f"<code>{k}</code> = {self.cfg[k]}" for k in keys)
                return await self.say(chat,
                    f"🎯 <b>تنظیمات امتیاز</b>\n\n{cur}\n\n"
                    f"<code>/pset cost_per_hour 2</code>")
            k, v = p[0], p[1]
            if k not in keys:
                return await self.say(chat, "کلید نامعتبر.")
            if k == "points_on":
                self.cfg[k] = v.lower() in ("1", "true", "on", "روشن")
            else:
                self.cfg[k] = max(0, int(digits(v) or 0))
            per = max(1, self.cfg["cost_per_hour"])
            return await self.say(chat,
                f"✅ {k} = {self.cfg[k]}\n\n"
                f"<i>مصرف: 2 ساعت = {_fa_digits(per * 2)} · "
                f"24 ساعت = {_fa_digits(24 * per)} · "
                f"30 روز = {_fa_digits(720 * per)} امتیاز\n"
                f"روشن کردن: {_fa_digits(self.cfg['start_fee'])} امتیاز هر بار</i>")

        if cmd == "tk":
            rows = sh.open_tickets()
            if not rows:
                return await self.say(chat, "تیکت بازی نیست ✅")
            out = [f"🎧 <b>تیکت‌های باز ({_fa_digits(len(rows))})</b>", ""]
            for t in rows:
                msgs = sh.ticket_msgs(t["id"])
                last = msgs[-1] if msgs else {}
                out.append(f"#{_fa_digits(t['id'])} <code>{t['uid']}</code> {t['subject']}")
                out.append(f"     💬 {(last.get('text') or '')[:80]}")
                out.append(f"     <code>/tr {t['id']} متن</code>")
                out.append("")
            return await self.say(chat, "\n".join(out))

        if cmd == "tr":
            if len(p) < 2:
                return await self.say(chat, "/tr 5 متن جواب")
            tid = int(digits(p[0]) or 0)
            t = sh.ticket(tid)
            if not t:
                return await self.say(chat, "تیکت پیدا نشد.")
            body = arg.split(None, 1)[1]
            sh.add_msg(tid, body, True)
            await self.say(t["uid"], f"🎧 <b>پاسخ تیکت #{_fa_digits(tid)}</b>\n\n{body}")
            return await self.say(chat, "✅ فرستاده شد.")

        if cmd == "tclose":
            sh.close_ticket(int(digits(p[0]) or 0) if p else 0)
            return await self.say(chat, "✅ بسته شد.")

        if cmd == "card":
            if not p:
                return await self.say(chat,
                    f"کارت فعلی: <code>{self.cfg['card_number'] or '—'}</code>\n"
                    f"به نام: {self.cfg['card_name'] or '—'}\n\n"
                    "<code>/card 6037991234567890 علی رضایی</code>")
            self.cfg["card_number"] = digits(p[0])
            if len(p) > 1:
                self.cfg["card_name"] = " ".join(p[1:])
            return await self.say(chat,
                f"✅ کارت: <code>{self.cfg['card_number']}</code>\n"
                f"به نام: {self.cfg['card_name']}")

        return None

    async def trial_loop(self):
        """تست رایگان را پایش می‌کند و «trial_warning_minutes» دقیقه مانده
        به کاربر یادآوری می‌کند (چند دقیقه، از پنلِ مدیر تعیین می‌شود)."""
        while True:
            try:
                warning = max(1, int(self.cfg.get("trial_warning_minutes", 10) or 10)) * 60
                now_t = now()
                for c in self.db.all("active"):
                    exp = int(c.get("trial_expires_at") or 0)
                    if not exp:
                        continue
                    left = exp - now_t
                    if left <= 0:
                        if self.sup.is_running(c["uid"]):
                            self.sup.stop(c["uid"])
                        # مُهرِ تست باید صفر شود؛ وگرنه روی رکورد می‌ماند و
                        # بعداً has_sub را برای اشتراکِ خریداری‌شده مخدوش می‌کند.
                        self.db.set(c["uid"], status="expired", trial_expires_at=0)
                        self.db.log(c["uid"], "trial_expired", "تست رایگان تمام شد")
                    elif left <= warning and not int(c.get("trial_warning_sent") or 0):
                        self.db.set(c["uid"], trial_warning_sent=1)
                        await self.say(c["uid"],
                            f"⏰ تست رایگانت {human_left(exp)} دیگر تمام می‌شود.\n\n"
                            "برای ادامه یکی از پلن‌ها یا امتیاز را انتخاب کن.",
                            [[B("💎 خرید اشتراک", "m:plans", "primary")],
                             [B("🎯 خرید امتیاز", "m:packs", "success")]])
            except Exception as e:
                print("trial_loop:", e)
            await asyncio.sleep(30)

    async def points_loop(self):
        """هر 5 دقیقه: امتیاز کاربران در حال کار را کسر می‌کند."""
        while True:
            try:
                if self.shop and self.cfg["points_on"]:
                    per = max(1, self.cfg["cost_per_hour"])
                    for c in self.db.all("active"):
                        uid = c["uid"]
                        if not self.sup.is_running(uid):
                            continue
                        proc = self.sup.procs.get(uid)
                        if (isinstance(proc, _ShardProc)
                                and not proc.daemon.recently_confirmed_alive(uid)):
                            # هنگام قطع پاسخ شارد، بدون تأیید کارکرد از مشتری
                            # هزینه نگیریم و بعداً هم زمان نامعلوم را تسویه نکنیم.
                            self.shop.p_reset_charge(uid)
                            continue
                        if self.has_sub(uid) or self.trial_active(uid):
                            self.shop.p_reset_charge(uid)   # اشتراکی‌ها و تست رایگان معافند
                            continue
                        cost, bal, dead = self.shop.p_charge_due(uid, per)
                        if cost:
                            self.sync_points_limits(uid)
                        if dead:
                            self.sup.stop(uid)
                            self.db.log(uid, "points_out", "امتیاز تمام شد")
                            await self.say(uid,
                                "🔋 <b>امتیازت تمام شد</b>\n\n"
                                "سرویس خاموش شد. برای ادامه امتیاز بخر 👇",
                                [[B("🛒 خرید امتیاز", "m:packs", "success")],
                                 [B("💎 اشتراک ماهانه", "m:plans", "primary")]])
                        elif bal and bal <= self.cfg["low_warn"] and cost:
                            await self.say(uid,
                                f"⚠️ فقط <b>{_fa_digits(bal)}</b> امتیاز مانده "
                                f"(≈{_fa_digits(bal // per)} ساعت).",
                                [[B("🛒 خرید امتیاز", "m:packs", "success")]])
            except Exception as e:
                print("points_loop:", e)
            await asyncio.sleep(300)

    async def duplicate_watch_loop(self):
        """تشخیص «نسخه‌ی دیگری از همین ربات هم‌زمان روشنه».

        هر دقیقه یک پیام ضربان در چت مدیر edit می‌کند و ضربانِ تازه‌ی نمونه‌های
        دیگر (DEPLOY_ID متفاوت) را می‌خواند. اگر همان نمونه‌ی غریبه در دو اسکن
        پیاپی ضربانش تازه مانده باشد (یعنی ری‌استارت/دیپلویِ سالم نیست و واقعاً
        یک سرویس دوم زنده است)، هشدار می‌دهد: همان ریشه‌ی «فایل 95.py پیدا
        نشد» و «ریل‌وی قدیمی هنوز روشنه».
        """
        try:
            me = await self.bot.get_me()
            bot_id = getattr(me, "id", 0) or 0
        except Exception:
            bot_id = 0
        # chat -> آخرین پیام ضربان خودمان (برای edit به‌جای اسپم)
        my_beacon = {}
        # dep غریبه -> اسکن‌های پیاپی‌ای که زنده دیده شده
        seen = {}
        # ردِ فعالیتِ بیگانه‌ی نسخه‌ی قدیمی (که ضربان ندارد)
        legacy_seen = 0
        last_alert = 0.0
        alerts_sent = 0
        MAX_ALERTS = 4
        ALERT_EVERY = 900        # بین هشدارها حداقل ۱۵ دقیقه
        while True:
            try:
                foreign_live = []
                legacy_hits = 0
                for a in self.cfg.get("admin_ids") or []:
                    try:
                        msgs = await self.bot.get_messages(a, limit=25)
                    except Exception:
                        continue
                    parsed = []
                    stale_own = []
                    raw = []
                    for m in msgs:
                        try:
                            txt = m.message or ""
                        except Exception:
                            continue
                        try:
                            raw.append({
                                "id": m.id,
                                "sender_id": getattr(m, "sender_id", 0) or 0,
                                "text": txt,
                                "ts": int((m.edit_date or m.date).timestamp()),
                            })
                        except Exception:
                            pass
                        b = parse_beacon(txt)
                        if not b:
                            continue
                        try:
                            ets = int((m.edit_date or m.date).timestamp())
                        except Exception:
                            ets = b["ts"]
                        parsed.append({"text": txt, "edit_ts": ets})
                        # ضربانِ مرده (خودی یا غریبه — مانده از دیپلوی/ری‌استارت
                        # قبل) را پاک کن؛ ضربانِ زنده هر ۶۰ثانیه edit می‌شود و
                        # هرگز این‌قدر کهنه نمی‌ماند. این‌طور پیوی مدیر با
                        # ضربانِ هر دیپلوی شلوغ نمی‌شود.
                        if int(time.time()) - ets > 1800:
                            stale_own.append(m)
                    for m in stale_own:
                        try:
                            await m.delete()
                        except Exception:
                            pass
                    mine, foreign = scan_beacons(parsed)
                    foreign_live.extend(foreign)
                    # ── نسخه‌ی قدیمیِ زامبی (ضربان ندارد) از روی فعالیتش ──
                    legacy_hits += count_legacy_foreign(
                        raw, bot_id, self._sent_ids, self._live, self.boot_at)
                    # ── ضربان خودمان: edit کن، وگرنه تازه بفرست ──
                    existing = None
                    for m in msgs:
                        b = parse_beacon(getattr(m, "message", "") or "")
                        if not b:
                            continue
                        if b["dep"] == DEPLOY_ID:
                            existing = m
                            break
                        # پیامِ ضربانِ «مرده‌ی» یک نمونه‌ی دیگر (کهنه، نه زنده)
                        # بازیافت می‌شود تا هر دیپلوی/ری‌استارت یک پیامِ تازه در
                        # پیوی مدیر نگذارد. ضربانِ زنده‌ی نمونه‌ی دیگر (تازه‌تر
                        # از ۱۸۰ثانیه) هرگز دست‌نخورده می‌ماند و مانده‌های
                        # بالای ۱۸۰۰ثانیه هم در حلقه‌ی بالا پاک می‌شوند.
                        try:
                            ets2 = int((m.edit_date or m.date).timestamp())
                        except Exception:
                            ets2 = b["ts"]
                        _age2 = int(time.time()) - ets2
                        if 180 < _age2 <= 1800:
                            existing = m
                            break
                    try:
                        if existing is not None:
                            await self.bot.edit_message(a, existing, beacon_text())
                            my_beacon[a] = existing.id
                        else:
                            sent = await self.bot.send_message(a, beacon_text())
                            my_beacon[a] = getattr(sent, "id", None)
                    except Exception as e:
                        print("beacon:", type(e).__name__, e)

                # ── تصمیم هشدار: غریبه باید در دو اسکن پیاپی زنده باشد ──
                deps_now = {b["dep"]: b for b in foreign_live}
                confirmed = {}
                for dep, b in list(deps_now.items()):
                    seen[dep] = seen.get(dep, 0) + 1
                    if seen[dep] >= 2:
                        confirmed[dep] = b
                for dep in list(seen):
                    if dep not in deps_now:
                        seen.pop(dep, None)

                # نسخه‌ی قدیمی هم اگر دو اسکن پیاپی پیامِ تازه‌ی بیگانه داشته
                # باشد، زنده است (روی ۳ دقیقه اخیر دیده شود، بعد صفر می‌شود).
                if legacy_hits:
                    legacy_seen += 1
                else:
                    legacy_seen = 0
                legacy_confirmed = legacy_seen >= 2

                if (confirmed or legacy_confirmed) and alerts_sent < MAX_ALERTS \
                        and time.time() - last_alert > ALERT_EVERY:
                    last_alert = time.time()
                    alerts_sent += 1
                    lines = ["⚠️ <b>نسخه‌ی دیگری از همین ربات هم‌زمان روشن است!</b>",
                             "",
                             "چند سرویس/دیپلوی با یک توکن به تلگرام وصل‌اند؛ "
                             "تلگرام پیام‌ها و دکمه‌ها را بینشان پخش می‌کند. "
                             "به همین خاطر است که گاهی «فایل 95.py پیدا نشد» "
                             "می‌آید و ریل‌وی قدیمی هنوز پاسخ می‌دهد.",
                             "",
                             f"نمونه‌ی خودت: <code>{INSTANCE_ID}</code> · "
                             f"<code>{BUILD_VERSION}</code> · {HOST_LABEL}"]
                    if confirmed:
                        lines.append("نمونه(های) دارای ضربان:")
                        for b in list(confirmed.values())[:4]:
                            lines.append(f"  • <code>{b['build']}</code> — {b['host']}")
                    if legacy_confirmed:
                        lines.append("+ یک نمونه‌ی نسخه‌ی قدیمی هم دارد پیام "
                                     "می‌فرستد (ضربان ندارد — احتمالاً همان "
                                     "سرویس Railway که به حسابش دسترسی نداری).")
                    lines += [
                        "",
                        "🔧 <b>اگر به سرویس قدیمی دسترسی داری:</b> توی داشبورد "
                        "Railway سرویس اضافی را <b>Remove</b> کن؛ فقط یک سرویس "
                        "بماند و اینجا Redeploy بزن.",
                        "",
                        "🔑 <b>اگر دسترسی نداری (حسابش پریده):</b> توکن ربات "
                        "را عوض کن تا سرویس قدیمی کور شود:",
                        "۱) در تلگرام به <b>@BotFather</b> برو → <code>/mybots</code> "
                        "→ رباتت → <b>API Token</b> → <b>Revoke current token</b>",
                        "۲) توکن جدید را در متغیرهای محیطی همین سرویس بگذار "
                        "(<code>BOT_TOKEN</code>) و Redeploy بزن (یا فایل "
                        "manager_config.json را به‌روز کن).",
                        "۳) فایل <code>manager_bot.string</code> لازم نیست "
                        "دست بزنی؛ خودش با توکن جدید دوباره ساخته می‌شود."]
                    for a in self.cfg.get("admin_ids") or []:
                        try:
                            await self.bot.send_message(a, "\n".join(lines),
                                                        parse_mode="html",
                                                        link_preview=False)
                        except Exception:
                            pass
            except Exception as e:
                print("duplicate_watch:", e)
            await asyncio.sleep(60)

    async def reminder_loop(self):
        """یادآوری تمدید چند روز قبل از انقضا."""
        sent = set()
        while True:
            try:
                d = self.cfg["remind_days"] * 86400
                for c in self.db.all("active"):
                    e = c["expires_at"]
                    if not e:
                        continue
                    left = e - now()
                    key = (c["uid"], e)
                    if 0 < left <= d and key not in sent:
                        sent.add(key)
                        await self.say(c["uid"],
                            f"⏰ <b>یادآوری</b>\n\n"
                            f"اعتبار سرویست {human_left(e)} دیگر تمام می‌شود.\n"
                            f"برای تمدید: /plans")
            except Exception as e:
                print("reminder:", e)
            await asyncio.sleep(3600)

    # ═══════════════════════════════════════════════
    #  ورود ربات + پشتیبان خودکار (v0905-fix2)
    # ═══════════════════════════════════════════════
    async def login_with_patience(self, tries=5):
        """login_bot را تا موفقیت تکرار می‌کند.

        چرا: قبلاً بعد از ۵ تلاش، run() مقدار ۱ برمی‌گرداند و پروسه exit(1)
        می‌شد. روی Railway یعنی کانتینر می‌میرد، ری‌استارت می‌شود، دوباره
        FloodWait می‌گیرد و… — همان «ریل‌وی همش کرش می‌کند». اینجا روی محیط
        میزبان پروسه زنده می‌ماند (وب‌سرور سلامت هم بالاست) و با فاصله‌ی
        فزاینده دوباره تلاش می‌کند.
        """
        round_no = 0
        while True:
            round_no += 1
            try:
                return await self.login_bot(tries=tries)
            except Exception as e:
                if not login_retry_forever():
                    raise
                wait = login_retry_wait(round_no)
                print(f"  🔁 ورود ناموفق ({type(e).__name__}: {e}) — پروسه زنده "
                      f"می‌ماند، {wait}s دیگر تلاش {round_no + 1}", flush=True)
                await asyncio.sleep(wait)

    async def login_bot(self, tries=5):
        """ورود ربات با نشست ذخیره‌شده + تحمل FloodWait.

        - نشست در BASE_DIR/manager_bot.string ذخیره می‌شود.
        - در بوت بعدی فقط connect() + is_user_authorized() (بدون start با توکن).
        - اگر FloodWait آمد، دقیقاً min(seconds,3600)+30 ثانیه می‌خوابد و دوباره تلاش می‌کند.
        - بدون خوابیدن چکش نمی‌زند (برای خطاهای دیگر هم backoff دارد).
        """
        from telethon import TelegramClient
        from telethon.sessions import StringSession
        try:
            from telethon.errors import FloodWaitError as _FloodWait
        except Exception:
            _FloodWait = None

        def _flood_seconds(exc):
            try:
                if _FloodWait is not None and isinstance(exc, _FloodWait):
                    return int(getattr(exc, "seconds", 0) or 0)
            except Exception:
                pass
            try:
                if type(exc).__name__ == "FloodWaitError":
                    return int(getattr(exc, "seconds", 0) or 0)
            except Exception:
                pass
            return None

        c = self.cfg
        api_id = c["api_id"]
        api_hash = c["api_hash"]
        token = c["bot_token"]
        last_err = None
        tries = max(1, int(tries or 5))
        class _RetryLoop(Exception):
            pass

        for attempt in range(1, tries + 1):
            # ── 1) نشست ذخیره‌شده ──
            saved = ""
            try:
                if os.path.isfile(BOT_SESSION_FILE):
                    with open(BOT_SESSION_FILE, encoding="utf-8", errors="ignore") as f:
                        saved = (f.read() or "").strip()
            except Exception as e:
                print(f"  ⚠️ خواندن نشست: {e}", flush=True)
                saved = ""

            use_token_path = True
            if saved:
                # 1-الف) ساخت آبجکت نشست — اگر خراب بود پاک کن و به توکن برو
                try:
                    _sess_obj = StringSession(saved)
                except Exception as e:
                    print(f"  ⚠️ نشست ذخیره‌شده خراب ({type(e).__name__}) — پاک و ورود با توکن", flush=True)
                    try:
                        if os.path.exists(BOT_SESSION_FILE):
                            os.remove(BOT_SESSION_FILE)
                    except Exception:
                        pass
                    _sess_obj = None
                    # ادامه به مسیر توکن در همین تلاش (بدون خواب)
                    use_token_path = True
                else:
                    # 1-ب) اتصال با نشست ذخیره‌شده (بدون start)
                    client = None
                    try:
                        client = TelegramClient(_sess_obj, api_id, api_hash)
                        await client.connect()
                    except Exception as e:
                        secs = _flood_seconds(e)
                        if secs is not None:
                            wait = min(max(0, secs), 3600) + 30
                            print(f"  ⏳ FloodWait روی نشست ({secs}s) — خواب {wait}s (تلاش {attempt}/{tries})", flush=True)
                            try:
                                if client is not None:
                                    try:
                                        await client.disconnect()
                                    except Exception:
                                        pass
                            except Exception:
                                pass
                            await asyncio.sleep(wait)
                            last_err = e
                            continue
                        # خطای اتصال (احتمالاً شبکه) — فایل را نگه دار، با backoff تلاش بعدی
                        if attempt < tries:
                            wait = min(10 * attempt, 60)
                            print(f"  ⚠️ اتصال با نشست ناموفق ({type(e).__name__}: {e}) — تلاش {attempt}/{tries}، خواب {wait}s", flush=True)
                            try:
                                if client is not None:
                                    try:
                                        await client.disconnect()
                                    except Exception:
                                        pass
                            except Exception:
                                pass
                            await asyncio.sleep(wait)
                            last_err = e
                            continue
                        print(f"  ⛔ اتصال ناموفق پس از {tries} تلاش: {type(e).__name__}: {e}", flush=True)
                        raise
                    # 1-ج) اعتبارسنجی
                    try:
                        try:
                            ok = await client.is_user_authorized()
                        except Exception as e:
                            secs = _flood_seconds(e)
                            if secs is not None:
                                wait = min(max(0, secs), 3600) + 30
                                print(f"  ⏳ FloodWait روی نشست ({secs}s) — خواب {wait}s (تلاش {attempt}/{tries})", flush=True)
                                try:
                                    await client.disconnect()
                                except Exception:
                                    pass
                                await asyncio.sleep(wait)
                                last_err = e
                                # حلقه بعدی دوباره نشست را امتحان می‌کند
                                raise _RetryLoop()
                            raise
                        if ok:
                            # is_user_authorized فقط می‌گوید نشست از نظر MTProto معتبر
                            # است؛ تضمین نمی‌کند نشست متعلق به همین ربات باشد. اگر
                            # توکن عوض شده باشد، نشستِ ربات قبلی می‌تواند همچنان
                            # وصل شود و تمام callbackهای ربات فعلی به این پروسه نرسند.
                            me = await client.get_me()
                            expected_bot_id = None
                            try:
                                expected_bot_id = int(str(token).strip().split(":", 1)[0])
                            except Exception:
                                pass
                            session_is_bot = getattr(me, "bot", None) is True
                            try:
                                session_matches_token = (
                                    expected_bot_id is not None
                                    and int(getattr(me, "id", 0)) == expected_bot_id
                                )
                            except Exception:
                                session_matches_token = False
                            if session_is_bot and session_matches_token:
                                self.bot = install_outgoing_filter(client)
                                print("  ✅ نشست ذخیره‌شده متعلق به همین ربات است "
                                      "(بدون ورود دوباره)", flush=True)
                                return client
                            print("  ⚠️ نشست ذخیره‌شده متعلق به ربات/اکانت دیگری است "
                                  "— پاک و ورود با توکن فعلی", flush=True)
                            try:
                                if os.path.exists(BOT_SESSION_FILE):
                                    os.remove(BOT_SESSION_FILE)
                            except Exception:
                                pass
                            use_token_path = True
                        else:
                            # معتبر نیست → پاک و ورود با توکن در همین تلاش
                            print("  ⚠️ نشست ذخیره‌شده معتبر نیست — پاک و ورود با توکن", flush=True)
                        try:
                            await client.disconnect()
                        except Exception:
                            pass
                        try:
                            if os.path.exists(BOT_SESSION_FILE):
                                os.remove(BOT_SESSION_FILE)
                        except Exception:
                            pass
                        use_token_path = True
                    except _RetryLoop:
                        continue
                    except Exception as e:
                        secs = _flood_seconds(e)
                        if secs is not None:
                            wait = min(max(0, secs), 3600) + 30
                            print(f"  ⏳ FloodWait روی نشست ({secs}s) — خواب {wait}s (تلاش {attempt}/{tries})", flush=True)
                            try:
                                await client.disconnect()
                            except Exception:
                                pass
                            await asyncio.sleep(wait)
                            last_err = e
                            continue
                        # خطای اعتبارسنجی غیر Flood — اگر نشست خراب به نظر می‌رسد پاک کن
                        # در غیر این صورت (شبکه) نگه دار و backoff
                        _msg = f"{type(e).__name__}: {e}".lower()
                        _looks_bad = any(k in _msg for k in ("auth", "session", "revoked", "deactivated", "banned", "unauthorized", "invalid", "corrupt"))
                        if _looks_bad:
                            print(f"  ⚠️ نشست ذخیره‌شده خراب ({type(e).__name__}) — پاک و ورود با توکن", flush=True)
                            try:
                                await client.disconnect()
                            except Exception:
                                pass
                            try:
                                if os.path.exists(BOT_SESSION_FILE):
                                    os.remove(BOT_SESSION_FILE)
                            except Exception:
                                pass
                            use_token_path = True
                        else:
                            if attempt < tries:
                                wait = min(10 * attempt, 60)
                                print(f"  ⚠️ اعتبارسنجی نشست ناموفق ({type(e).__name__}: {e}) — تلاش {attempt}/{tries}، خواب {wait}s", flush=True)
                                try:
                                    await client.disconnect()
                                except Exception:
                                    pass
                                await asyncio.sleep(wait)
                                last_err = e
                                continue
                            print(f"  ⛔ ورود ناموفق پس از {tries} تلاش: {type(e).__name__}: {e}", flush=True)
                            raise
            else:
                use_token_path = True

            if not use_token_path:
                continue

            # ── 2) ورود با توکن ──
            # لیست توکن‌ها: اول توکن تنظیمات/متغیر محیطی، بعد توکن هاردکد داخل
            # همین فایل (ایمیج). اگر توکن قبلی در BotFather باطل (Revoke) شده و
            # توکن جدید در کد آمده ولی توکن کهنه توی manager_config.json یا
            # متغیر BOT_TOKEN گیر کرده باشد، خودکار سراغ هاردکد می‌رویم.
            candidates = []
            for t in (token, BOT_TOKEN):
                t = (t or "").strip()
                if t and t not in candidates:
                    candidates.append(t)
            for ci, cand in enumerate(candidates):
                client2 = None
                try:
                    client2 = TelegramClient(StringSession(), api_id, api_hash)
                    await client2.start(bot_token=cand)
                    if cand != token:
                        print("  🔑 توکن تنظیمات معتبر نبود؛ با توکن داخل کد وارد "
                              "شدم و تنظیمات را به‌روز می‌کنم", flush=True)
                        try:
                            self.cfg["bot_token"] = cand
                        except Exception:
                            pass
                    # نشست ذخیره شود
                    try:
                        s = StringSession.save(client2.session)
                        if s:
                            with open(BOT_SESSION_FILE, "w", encoding="utf-8") as f:
                                f.write(s)
                            try:
                                os.chmod(BOT_SESSION_FILE, 0o600)
                            except Exception:
                                pass
                            print(f"  💾 نشست ربات ذخیره شد ({len(s)} حرف)", flush=True)
                    except Exception as e:
                        print(f"  ⚠️ ذخیره نشست: {type(e).__name__}: {e}", flush=True)
                    self.bot = install_outgoing_filter(client2)
                    return client2
                except Exception as e:
                    secs = _flood_seconds(e)
                    if secs is not None:
                        wait = min(max(0, secs), 3600) + 30
                        print(f"  ⏳ FloodWait روی ورود ({secs}s) — خواب {wait}s (تلاش {attempt}/{tries})", flush=True)
                        try:
                            if client2 is not None:
                                try:
                                    await client2.disconnect()
                                except Exception:
                                    pass
                        except Exception:
                            pass
                        await asyncio.sleep(wait)
                        last_err = e
                        break
                    dead = is_dead_token_error(e)
                    last_err = e
                    if ci < len(candidates) - 1:
                        if dead:
                            print(f"  ⚠️ توکن {ci + 1} باطل است ({type(e).__name__}) — "
                                  f"توکن بعدی را امتحان می‌کنم", flush=True)
                            try:
                                if client2 is not None:
                                    try:
                                        await client2.disconnect()
                                    except Exception:
                                        pass
                            except Exception:
                                pass
                            # نشستِ متعلق به توکن باطل را پاک کن تا دوباره استفاده نشود
                            try:
                                if os.path.exists(BOT_SESSION_FILE):
                                    os.remove(BOT_SESSION_FILE)
                            except Exception:
                                pass
                            continue
                        # توکن بعدی هم هست ولی خطا شبکه‌ای بود؛ صبر کن و کل دور را تکرار کن
                        wait = min(10 * attempt, 60)
                        print(f"  ⚠️ ورود ناموفق ({type(e).__name__}: {e}) — خواب {wait}s", flush=True)
                        try:
                            if client2 is not None:
                                try:
                                    await client2.disconnect()
                                except Exception:
                                    pass
                        except Exception:
                            pass
                        await asyncio.sleep(wait)
                        break
                    if attempt < tries:
                        wait = min(10 * attempt, 60)
                        print(f"  ⚠️ ورود ناموفق ({type(e).__name__}: {e}) — تلاش {attempt}/{tries}، خواب {wait}s", flush=True)
                        try:
                            if client2 is not None:
                                try:
                                    await client2.disconnect()
                                except Exception:
                                    pass
                        except Exception:
                            pass
                        await asyncio.sleep(wait)
                        break
                    print(f"  ⛔ ورود ناموفق پس از {tries} تلاش: {type(e).__name__}: {e}", flush=True)
                    raise

            # اگر از حلقه‌ی کاندیدها بدون return بیرون آمدیم (flood/شبکه/انتظار)،
            # دور بیرونی (attempt) خودش دوباره تلاش می‌کند.

        if last_err is not None:
            raise last_err
        raise RuntimeError("login failed")

    # ---------- پشتیبان خودکار ----------
    def _backup_target(self):
        """مقصد پشتیبان: admin → چت مدیر، عدد → آیدی، وگرنه @username.

        بدون BACKUP_CHAT به «admin» برمی‌گردد تا بکاپ خودکار حتی بدون تنظیم
        دستی هم به چت خصوصی اولین مدیر برود (داده‌ها بعد از هر دیپلوی/ری‌استارت
        قابل بازیابی بمانند)."""
        raw = backup_target_raw()
        if not raw:
            return None
        if raw.lower() == "admin":
            try:
                aids = self.cfg.get("admin_ids") or []
                if aids:
                    return int(aids[0])
            except Exception:
                pass
            return None
        try:
            if re.fullmatch(r"-?\d+", raw):
                return int(raw)
        except Exception:
            pass
        return raw

    async def _backup_target_is_public(self, target):
        """(عمومی_است, توضیح) — اگر کانال عمومی بود True."""
        if isinstance(target, int):
            return False, str(target)
        try:
            ent = await self.bot.get_entity(target)
            username = getattr(ent, "username", None)
            if username:
                return True, f"@{username}"
            if getattr(ent, "public", False):
                return True, str(target)
            return False, str(target)
        except Exception as e:
            print(f"  ⚠️ بررسی کانال پشتیبان: {type(e).__name__}", flush=True)
            return False, str(target)

    @_cpu_mark_activity("بررسی تغییرات بک‌آپ")
    def _backup_fingerprint(self, use_live=True, paced=False):
        """اثرانگشت پشتیبان — فقط بر اساس محتوای واقعی اطلاعات (مشتری‌ها، فروشگاه، تنظیمات).
        تغییراتِ لحظه‌ایِ زمان فایل (مثل wal_checkpoint، پینگ سشن تلگرام یا گزارش زنده‌ی سلف)
        باعث بک‌آپ تکراری و بی‌مورد نمی‌شوند؛ فقط ثبت یا تغییر اطلاعات واقعی اثرانگشت را عوض می‌کند."""
        import hashlib
        pacer = _BackupCpuPacer(self) if paced else None

        def _sqlite_hash(path, live_conn=None):
            if not os.path.isfile(path):
                return None
            h = hashlib.md5()
            c = live_conn
            close_it = False
            try:
                if c is None:
                    from urllib.parse import quote
                    uri = "file:" + quote(os.path.abspath(path), safe="/") + "?mode=ro"
                    c = sqlite3.connect(uri, uri=True, timeout=2)
                    close_it = True
                tables = [r[0] for r in c.execute(
                    "SELECT name FROM sqlite_master WHERE type='table' AND name NOT LIKE 'sqlite_%' ORDER BY name"
                ).fetchall()]
                for t in tables:
                    h.update(t.encode("utf-8", "ignore"))
                    for i, row in enumerate(c.execute(f'SELECT * FROM "{t}"')):
                        h.update(repr(tuple(row)).encode("utf-8", "ignore"))
                        if pacer is not None and i % 128 == 127:
                            pacer.checkpoint()
                    if pacer is not None:
                        pacer.checkpoint()
                return h.hexdigest()[:16]
            except Exception:
                if not use_live:
                    # خواندن خامِ db ممکن است تغییرات WAL را جا بیندازد؛
                    # در این حالت بک‌آپ را متوقف کن نه اینکه «بی‌تغییر» بدانی.
                    raise RuntimeError("خواندن اثرانگشت دیتابیس ناموفق")
                try:
                    # Fallback هم فایل را chunk به chunk می‌خواند؛ f.read()
                    # کاملِ دیتابیس را در RAM نگه می‌داشت و در حافظه‌ی کم خطرناک بود.
                    h = hashlib.md5()
                    with open(path, "rb") as f:
                        for chunk in iter(lambda: f.read(64 * 1024), b""):
                            h.update(chunk)
                    return h.hexdigest()[:16]
                except Exception:
                    return None
            finally:
                if close_it and c is not None:
                    try:
                        c.close()
                    except Exception:
                        pass

        def _fp_file(path, rel=None):
            key = rel or path
            try:
                if not os.path.isfile(path):
                    return (key, None, None, None)
                base = os.path.basename(path).lower()
                if base.endswith(".session"):
                    return (key, "session", 0, "exists")
                if base == "jafj.db":
                    return (key, "client_db", 0, "exists")
                if base.endswith(".json"):
                    try:
                        with open(path, encoding="utf-8") as f:
                            d = json.load(f)
                        if isinstance(d, dict):
                            d = {k: v for k, v in d.items()
                                 if not str(k).startswith(("_adaptive_", "_block_"))}
                            # اشاره‌گرِ پیام را خودِ ارسال تغییر می‌دهد؛ دادهٔ مشتری نیست.
                            if os.path.abspath(path) == os.path.abspath(CONFIG_FILE):
                                d.pop("backup_msg_id", None)
                                d.pop("backup_msg_chat", None)
                        raw = json.dumps(d, sort_keys=True, ensure_ascii=False).encode("utf-8")
                        return (key, len(raw), 0, hashlib.md5(raw).hexdigest()[:16])
                    except Exception:
                        pass
                st = os.stat(path)
                h = None
                try:
                    if st.st_size < 1024 * 1024:
                        with open(path, "rb") as f:
                            h = hashlib.md5(f.read()).hexdigest()[:16]
                except Exception:
                    h = None
                return (key, st.st_size, 0, h)
            except Exception:
                return (key, None, None, None)

        fps = []
        # تردِ پشتیبان از اتصال‌های زندهٔ مدیر استفاده نمی‌کند.
        db_conn = getattr(getattr(self, "db", None), "c", None) if use_live else None
        shop_conn = getattr(getattr(self, "shop", None), "c", None) if use_live else None
        fps.append((DB_FILE, "sqlite", 0, _sqlite_hash(DB_FILE, db_conn)))
        fps.append((SHOP_DB, "sqlite", 0, _sqlite_hash(SHOP_DB, shop_conn)))
        for p in (CONFIG_FILE, BOT_SESSION_FILE):
            fps.append(_fp_file(p))
        for p in (os.path.join(BASE_DIR, "jafj_ai.json"), os.path.join(BASE_DIR, ".jafj_deploy_id")):
            fps.append(_fp_file(p))
        if os.path.isdir(CLIENTS_DIR):
            try:
                for root, dirs, files in os.walk(CLIENTS_DIR):
                    for fn in sorted(files):
                        if backup_file_skipped(fn):
                            continue
                        low = fn.lower()
                        if low.endswith(".session") or low == "jafj.db":
                            continue
                        fp = os.path.join(root, fn)
                        rel = os.path.relpath(fp, BASE_DIR)
                        fps.append(_fp_file(fp, rel))
                        if pacer is not None:
                            pacer.checkpoint()
            except Exception:
                if not use_live:
                    raise
        if pacer is not None:
            pacer.checkpoint()
        return tuple(sorted(fps))

    # ── «یک پیامِ پشتیبان» — پیام پشتیبان همیشه همان یکی است و به‌روز می‌شود ──
    # قبلاً هر تغییر داده و هر ری‌استارت/دیپلوی یک پیامِ پشتیبانِ تازه در پیوی
    # مدیر می‌گذاشت و پیوی پر از فایل می‌شد. الان: پیام قبلی پیدا می‌شود، مدیای
    # همان پیام عوض می‌شود (edit) و بعد از هر ری‌استارتِ بی‌تغییر هم هیچ پیام
    # تازه‌ای نمی‌رود. فقط و فقط «یک» پیام پشتیبان در چت می‌ماند.
    def _backup_fp_path(self):
        return os.path.join(BASE_DIR, ".jafj_backup_fp")

    def _backup_meta_path(self):
        return os.path.join(BASE_DIR, ".jafj_backup_meta")

    def _save_backup_fp(self, fp):
        """اثرانگشت آخرین پشتیبان را در حافظه + فایل داده ذخیره کن؛ تا بعد از
        ری‌استارتِ بدون تغییرِ داده، پشتیبانِ تکراری به پیوی مدیر نرود."""
        self._backup_fp = fp
        try:
            import json as _json
            with open(self._backup_fp_path(), "w", encoding="utf-8") as f:
                _json.dump([list(x) for x in (fp or ())], f)
        except Exception:
            pass
        if getattr(self, "_backup_msg_id", None):
            self._remember_backup_pointer(
                getattr(self, "_backup_msg_chat", None), self._backup_msg_id)

    def _remember_backup_pointer(self, chat, mid):
        """آدرسِ «تک‌پیامِ» پشتیبان را در دو جای ماندگار ثبت کن.

        چرا دو جا؟
          • `.jafj_backup_meta` روی دیسکِ داده — سریع و ساده.
          • `manager_config.json` — چون همین فایل داخل zipِ پشتیبان و در
            سینکِ گیت‌هاب است. یعنی پشتیبان «آدرسِ خودش» را هم حمل می‌کند و
            بعد از بازیابی، بوتِ بعدی می‌تواند پیام را با getMessages بخواند
            (ربات‌ها getHistory ندارند، پس گشتن در چت ممکن نیست).
        """
        try:
            self._backup_msg_id = int(mid) if mid else None
        except Exception:
            self._backup_msg_id = None
        if chat is not None:
            try:
                self._backup_msg_chat = self._chat_key(chat)
            except Exception:
                pass
        chat_key = getattr(self, "_backup_msg_chat", None)
        try:
            import json as _json
            with open(self._backup_meta_path(), "w", encoding="utf-8") as f:
                _json.dump({"msg_id": self._backup_msg_id,
                            "chat": chat_key, "ts": now()}, f)
        except Exception:
            pass
        try:
            self.cfg["backup_msg_id"] = int(self._backup_msg_id or 0)
            self.cfg["backup_msg_chat"] = chat_key or ""
            self.cfg.save()
        except Exception:
            pass

    def _backup_pointer(self):
        """(چت, آیدی پیام) از حافظه → meta → cfg؛ هر کدام که بود."""
        mid = getattr(self, "_backup_msg_id", None)
        chat = getattr(self, "_backup_msg_chat", None)
        if not mid or not chat:
            try:
                self._load_backup_fp()
            except Exception:
                pass
            mid = mid or getattr(self, "_backup_msg_id", None)
            chat = chat or getattr(self, "_backup_msg_chat", None)
        if not mid:
            try:
                mid = int(self.cfg.get("backup_msg_id") or 0) or None
            except Exception:
                mid = None
        if not chat:
            try:
                chat = (self.cfg.get("backup_msg_chat") or "").strip() or None
            except Exception:
                chat = None
        return chat, mid

    def _load_backup_fp(self):
        """فقط یکبار در هر پروسه: اثرانگشتِ ذخیره‌شده از بوتِ قبل را بخوان."""
        if getattr(self, "_backup_fp_loaded", False):
            return
        self._backup_fp_loaded = True
        try:
            import json as _json
            with open(self._backup_fp_path(), encoding="utf-8") as f:
                data = _json.load(f)
            self._backup_fp = tuple(tuple(x) for x in (data or []))
        except Exception:
            pass
        try:
            import json as _json
            if not getattr(self, "_backup_msg_id", None) and os.path.isfile(self._backup_meta_path()):
                with open(self._backup_meta_path(), encoding="utf-8") as f:
                    meta = _json.load(f) or {}
                if meta.get("msg_id"):
                    self._backup_msg_id = int(meta["msg_id"])
                if meta.get("chat"):
                    self._backup_msg_chat = str(meta["chat"])
        except Exception:
            pass
        # آخرین خطِ دفاع: اشاره‌گری که داخل خودِ manager_config.json است
        # (همان فایلی که با zipِ پشتیبان و سینکِ گیت‌هاب برمی‌گردد).
        try:
            if not getattr(self, "_backup_msg_id", None):
                mid = int(self.cfg.get("backup_msg_id") or 0)
                if mid:
                    self._backup_msg_id = mid
            if not getattr(self, "_backup_msg_chat", None):
                ch = (self.cfg.get("backup_msg_chat") or "").strip()
                if ch:
                    self._backup_msg_chat = ch
        except Exception:
            pass

    @staticmethod
    def _chat_key(x):
        """کلیدِ مقایسه‌پذیر برای یک چت/مقصد (آیدی، username یا خود مقدار)."""
        try:
            if x is None:
                return None
            if isinstance(x, (int, str)):
                return str(x).strip().lower().lstrip("@")
            i = getattr(x, "id", None)
            if i is not None:
                return str(i)
            u = getattr(x, "username", None)
            if u:
                return str(u).strip().lower().lstrip("@")
        except Exception:
            pass
        return str(x)

    @staticmethod
    def _msg_has_media(m):
        """پیام واقعاً فایل/مدیا دارد؟ (فایلِ zip همین است).

        پیامِ «متنی» که فقط نشانهٔ JAFJBACKUP1 را نقل‌قول کرده (مثلاً مدیر
        کپشن را فوروارد/کپی کرده باشد) هیچ zipی ندارد؛ اگر همان را به‌جای
        پیامِ اصلی بگیریم، هم بازیابی شکست می‌خورد و هم پشتیبانِ بعدی روی
        یک پیامِ بی‌فایل edit می‌شود."""
        for attr in ("document", "photo", "media", "file"):
            try:
                if getattr(m, attr, None) is not None:
                    return True
            except Exception:
                continue
        # تست‌ها فایل را در _fpath می‌گذارند؛ پیامِ واقعیِ تلگرام این را ندارد.
        try:
            fp = getattr(m, "_fpath", None)
            if fp and os.path.isfile(str(fp)):
                return True
        except Exception:
            pass
        return False

    async def _find_last_backup_msg(self, target, limit=50, prefer_media=True):
        """تازه‌ترین پیامِ پشتیبانِ خودِ ربات در چت مقصد (یا None).

        برای «تک‌پیامِ پشتیبان»: همان پیام edit می‌شود، نه اینکه پیام تازه
        انباشته شود. پیامِ چت‌های دیگر دست‌نخورده می‌ماند.

        prefer_media=True → پیامی که واقعاً «فایل» دارد بر پیامِ متنیِ
        نقل‌قولی مقدم است؛ اگر هیچ فایل‌داری نبود، همان تازه‌ترین پیامِ
        نشانه‌دار برمی‌گردد (رفتار قدیمی)."""
        self._last_iter_ok = True
        # ۱) اشاره‌گرِ ذخیره‌شده — تنها راهِ مطمئن برای رباتِ تلگرام، چون
        #    ربات`messages.getHistory` ندارد و `iter_messages` خطا می‌دهد.
        try:
            _chat, _mid = self._backup_pointer()
            if _mid:
                got = await self.bot.get_messages(target, ids=[int(_mid)])
                m = got[0] if isinstance(got, (list, tuple)) and got else got
                if m is not None and getattr(m, "id", None):
                    if not prefer_media or self._msg_has_media(m):
                        return m
        except Exception as e:
            print(f"  ⚠️ خواندنِ پشتیبان با اشاره‌گر: {type(e).__name__}", flush=True)
        try:
            bot_id = 0
            try:
                me = await self.bot.get_me()
                bot_id = getattr(me, "id", 0) or 0
            except Exception:
                bot_id = 0
            first_tagged = None
            async for m in self.bot.iter_messages(target, limit=limit):
                try:
                    txt = (getattr(m, "text", "") or "") + " " + (getattr(m, "caption", "") or "")
                except Exception:
                    continue
                if BACKUP_TAG not in txt:
                    continue
                sid = getattr(m, "sender_id", None)
                if bot_id and sid and int(sid) != int(bot_id):
                    continue
                if first_tagged is None:
                    first_tagged = m
                if prefer_media and self._msg_has_media(m):
                    return m
            return first_tagged
        except Exception as e:
            self._last_iter_ok = False
            print(f"  ⚠️ جستجوی پیام پشتیبان: {type(e).__name__}: {e}", flush=True)
            # در ربات‌های تلگرام iter_messages ممکن است BotMethodInvalid بدهد؛
            # اگر آیدی آخرین پیام پشتیبان را داریم، با get_messages مستقیم بگیر.
            self._load_backup_fp()
            mid = getattr(self, "_backup_msg_id", None)
            if mid:
                try:
                    got = await self.bot.get_messages(target, ids=[int(mid)])
                    m = got[0] if isinstance(got, list) and got else got
                    if m is not None and getattr(m, "id", None):
                        if not prefer_media or self._msg_has_media(m):
                            return m
                except Exception:
                    pass
        return None

    async def _find_backup_by_pointer(self, fallback_chat=None):
        """پیامِ پشتیبان را با آدرسِ ذخیره‌شده پیدا کن → (چت, پیام) یا (None, None).

        مزیتِ اصلی: هیچ گشتنی در تاریخچه لازم نیست. ربات‌های تلگرام
        `messages.getHistory` ندارند، پس این تنها راهِ کار کردنِ بازیابیِ
        خودکار روی یک ربات است.
        """
        if self.bot is None:
            return None, None
        chat, mid = self._backup_pointer()
        if not mid:
            return None, None
        cands = []
        for c in (chat, fallback_chat):
            if c is None:
                continue
            k = str(c).strip()
            try:
                if re.fullmatch(r"-?\d+", k):
                    c = int(k)
            except Exception:
                pass
            if c not in cands:
                cands.append(c)
        for c in cands:
            try:
                got = await self.bot.get_messages(c, ids=[int(mid)])
                m = got[0] if isinstance(got, (list, tuple)) and got else got
                if m is not None and getattr(m, "id", None) and self._msg_has_media(m):
                    print(f"  🔗 پشتیبان از اشاره‌گر پیدا شد "
                          f"(چت {self._chat_key(c)}، id={mid})", flush=True)
                    return c, m
            except Exception as e:
                print(f"  ⚠️ اشاره‌گر در چت {self._chat_key(c)}: "
                      f"{type(e).__name__}", flush=True)
        return None, None

    async def _find_backup_anywhere(self, limit=40, skip=None, max_chats=12):
        """جست‌وجوی سراسری: پیامِ پشتیبان در «همهٔ» چت‌های ربات → (مقصد, پیام).

        بعد از دیپلوی/ری‌استارت ممکن است مقصدِ فعلی دیگر آن چتی نباشد که
        پشتیبان در آن ساخته شده (BACKUP_CHAT عوض/حذف شده، یا admin_ids به
        پیش‌فرضِ هاردکد برگشته و ربات هرگز آنجا پیام نداده). تک‌پیامِ پشتیبان
        هنوز سر جایش است؛ این متد همان را پیدا می‌کند تا بازیابی و ادامهٔ
        پشتیبان از دست نرود. اگر پیدا نشد (None, None)."""
        ents = []
        # ربات تلگرام getDialogs ندارد (BotMethodInvalid). اگر اینجا تسلیم شویم
        # پشتیبانِ پیویِ مدیر هرگز پیدا نمی‌شود — همان «نه در تلگرام نه روی دیسک».
        # پس اول همهٔ admin_ids را (بدون سقف) می‌گردیم، بعد اگر API اجازه داد دیالوگ‌ها.
        for a in (self.cfg.get("admin_ids") or []):
            try:
                ents.append(int(a))
            except Exception:
                ents.append(a)
        raw = backup_target_raw()
        if raw and raw.lower() != "admin":
            try:
                ents.append(self._backup_target() or raw)
            except Exception:
                ents.append(raw)
        try:
            dialogs = None
            try:
                dialogs = await self.bot.get_dialogs(limit=max_chats * 3)
            except Exception:
                dialogs = None
            if dialogs:
                for d in dialogs:
                    e = getattr(d, "entity", None)
                    if e is None:
                        e = getattr(d, "id", None)
                    if e is not None:
                        ents.append(e)
            else:
                async for d in self.bot.iter_dialogs(limit=max_chats * 3):
                    e = getattr(d, "entity", None)
                    if e is None:
                        e = getattr(d, "id", None)
                    if e is not None:
                        ents.append(e)
        except Exception as e:
            print(f"  ⚠️ فهرست چت‌ها برای جستجوی سراسری پشتیبان: "
                  f"{type(e).__name__}: {e}", flush=True)
            if not ents:
                return None, None
        skip_key = self._chat_key(skip)
        seen = set()
        tried = 0
        for ent in ents:
            key = self._chat_key(ent)
            if key is None or key in seen:
                continue
            seen.add(key)
            if skip_key is not None and key == skip_key:
                continue
            if tried >= max_chats:
                break
            tried += 1
            try:
                msg = await self._find_last_backup_msg(ent, limit=limit, prefer_media=True)
            except Exception as e:
                print(f"  ⚠️ جستجوی پشتیبان در {key}: {type(e).__name__}", flush=True)
                msg = None
            if msg is not None:
                print(f"  🔎 پیامِ پشتیبان در چت {key} پیدا شد "
                      f"(id={getattr(msg, 'id', None)})", flush=True)
                return ent, msg
        return None, None

    async def _backup_target_reachable(self, target):
        """مقصدِ پشتیبان برای ربات قابل دسترسی است؟

        بعد از دیپلوی ممکن است BACKUP_CHAT پاک شده و admin_ids به پیش‌فرضِ
        هاردکد برگردد — آیدیِ کاربری که ربات هرگز با او گفت‌وگو نکرده
        (PeerIdInvalid/CouldNotFindChat). در این حالت پشتیبان تا ابد شکست
        می‌خورد، مگر اینکه از چتِ «پیامِ پشتیبانِ قبلی» ادامه بدهیم."""
        if target is None or self.bot is None:
            return False
        try:
            await self.bot.get_entity(target)
            return True
        except Exception as e:
            print(f"  ⚠️ مقصدِ پشتیبان در دسترس نیست ({self._chat_key(target)}): "
                  f"{type(e).__name__}", flush=True)
            return False

    # ── تازه‌سازی تنظیمات از دیسک بعد از بازیابی ──
    def _reload_cfg_from_disk(self):
        """cfg را از همان manager_config.json که همین الان بازیابی شد دوباره بخوان.

        باگِ اصلیِ «بعد از دیپلوی همه‌ش می‌پره»: بازیابی، فایل تنظیمات را از
        zip روی دیسک می‌نویسد، ولی self.cfg هنوز نسخهٔ حافظه است — یعنی همان
        پیش‌فرض‌هایی که موقع بوت (با دیسکِ خالی) ساخته شد. اولین cfg.save()
        بعد از بوت (و هر `self.cfg[...] = ...`) همان فایلِ بازیابی‌شده را با
        پیش‌فرض بازنویسی می‌کند و همهٔ تنظیمات می‌پرد.

        این متد همان کلیدها را از دیسکِ تازه می‌خواند و «درجا» در همین شیء
        Config جایگذاری می‌کند (تا ارجاع‌های دیگر مثل self.sup.cfg هم همان
        مقادیر تازه را ببینند). مقادیرِ محیطی (BOT_TOKEN/API_ID/API_HASH/
        ADMIN_IDS) مثل همیشه اولویت دارند، چون Config() خودش آن‌ها را می‌خواند.
        خروجی: True اگر از دیسک خوانده و جایگذاری شد."""
        try:
            if not os.path.isfile(CONFIG_FILE):
                return False
            fresh = Config()
        except Exception as e:
            print(f"  ⚠️ تازه‌سازی تنظیمات از دیسک: {type(e).__name__}: {e}", flush=True)
            return False
        try:
            old = dict(getattr(self.cfg, "d", {}) or {})
            new = dict(getattr(fresh, "d", {}) or {})
            # کلیدهای غیرِپیش‌فرضی که فقط در حافظهٔ همین نشست هستند از دست نروند
            for k, v in old.items():
                if k not in DEFAULTS and k not in new:
                    new[k] = v
            self.cfg.d.clear()
            self.cfg.d.update(new)
            try:
                self.sup.cfg = self.cfg
            except Exception:
                pass
            changed = sum(1 for k, v in new.items() if old.get(k, "<none>") != v)
            print(f"  ♻️ تنظیمات از دیسکِ بازیابی‌شده تازه شد "
                  f"({changed} کلید عوض شد) — اولین save دیگر پاکش نمی‌کند", flush=True)
            return True
        except Exception as e:
            print(f"  ⚠️ جایگزینی cfg از دیسک: {type(e).__name__}: {e}", flush=True)
            return False

    async def _cleanup_extra_backup_msgs(self, target, keep_id=None, max_delete=10):
        """پیام‌های پشتیبانِ اضافیِ مانده از نسخه‌های قبل را پاک می‌کند.

        قبلاً هر پشتیبان یک پیامِ تازه بود و در پیوی مدیر انباشته می‌شد؛ این
        توده‌ی قدیمی تدریجی و با سقف (max_delete در هر صدا) پاک می‌شود تا در
        چت فقط «یک» پیام پشتیبان بماند. پشتیبانِ چت‌های دیگر دست نمی‌خورد."""
        try:
            bot_id = 0
            try:
                me = await self.bot.get_me()
                bot_id = getattr(me, "id", 0) or 0
            except Exception:
                bot_id = 0
            deleted = 0
            async for m in self.bot.iter_messages(target, limit=100):
                if deleted >= max_delete:
                    break
                try:
                    txt = (getattr(m, "text", "") or "") + " " + (getattr(m, "caption", "") or "")
                except Exception:
                    continue
                if BACKUP_TAG not in txt:
                    continue
                if keep_id is not None and getattr(m, "id", None) == keep_id:
                    continue
                sid = getattr(m, "sender_id", None)
                if bot_id and sid and int(sid) != int(bot_id):
                    continue
                try:
                    await self.bot.delete_messages(target, [getattr(m, "id", None)])
                    deleted += 1
                except Exception:
                    continue
            if deleted:
                print(f"  🧹 {deleted} پیام پشتیبانِ اضافی پاک شد — فقط یک پشتیبان در چت می‌ماند", flush=True)
        except Exception as e:
            print(f"  ⚠️ پاک‌سازی پیام‌های اضافی پشتیبان: {type(e).__name__}", flush=True)

    def _save_local_backup_copy(self, src_zip):
        """یک کپی از zip روی دیسک داده (Render Disk /data) هم نگه می‌دارد.
        روی Railway/Render اگر Disk مانت باشد، این فایل بین دیپلوی‌ها می‌ماند؛
        روی فریِ بدون Disk هم ضرری ندارد و برای تست/دیباگ مفید است.
        حداکثر ۵ کپی گردشی + یک latest نگه می‌دارد.
        علاوه بر zip، برای هر فایل اصلی یک .bak هم می‌سازد تا در ls باز باشد (درخواست کاربر Render)."""
        try:
            # کپی latest
            latest = os.path.join(BASE_DIR, "jafj_backup_latest.zip")
            try:
                shutil.copy2(src_zip, latest)
            except Exception as e:
                print(f"  ⚠️ کپی پشتیبان local latest: {e}", flush=True)
            # کپی گردشی با تاریخ
            try:
                bdir = os.path.join(BASE_DIR, "backups")
                os.makedirs(bdir, exist_ok=True)
                ts = datetime.now().strftime("%Y%m%d_%H%M%S")
                dst = os.path.join(bdir, f"jafj_backup_{ts}.zip")
                shutil.copy2(src_zip, dst)
                # نگه‌دار فقط 5 تا آخر
                try:
                    files = sorted([os.path.join(bdir, f) for f in os.listdir(bdir) if f.startswith("jafj_backup_") and f.endswith(".zip")])
                    while len(files) > 5:
                        old = files.pop(0)
                        try:
                            os.remove(old)
                        except Exception:
                            pass
                except Exception:
                    pass
            except Exception as e:
                print(f"  ⚠️ کپی گردشی پشتیبان: {e}", flush=True)
            # ── .bak تکی برای هر DB/کانفیگ (قابل دیدن با ls) ──
            try:
                for src in (DB_FILE, SHOP_DB, CONFIG_FILE, BOT_SESSION_FILE, os.path.join(BASE_DIR, "jafj_ai.json")):
                    if not src or not os.path.isfile(src):
                        continue
                    try:
                        # یک .bak ساده (آخرین) + یک چرخشی با timestamp داخل backups/
                        bak_latest = src + ".bak"
                        shutil.copy2(src, bak_latest)
                        # چرخشی داخل backups/ با نام واضح
                        try:
                            bdir = os.path.join(BASE_DIR, "backups")
                            os.makedirs(bdir, exist_ok=True)
                            bn = os.path.basename(src)
                            ts2 = datetime.now().strftime("%Y%m%d_%H%M%S")
                            bak_rot = os.path.join(bdir, f"{bn}.bak-{ts2}")
                            shutil.copy2(src, bak_rot)
                            # نگه‌دار فقط 3 نسخه از هر فایل
                            try:
                                pref = f"{bn}.bak-"
                                cand = sorted([os.path.join(bdir, f) for f in os.listdir(bdir) if f.startswith(pref)])
                                while len(cand) > 3:
                                    old = cand.pop(0)
                                    try:
                                        os.remove(old)
                                    except Exception:
                                        pass
                            except Exception:
                                pass
                        except Exception:
                            pass
                    except Exception as e:
                        print(f"  ⚠️ .bak {src}: {e}", flush=True)
            except Exception:
                pass
        except Exception as e:
            print(f"  ⚠️ ذخیره پشتیبان محلی: {e}", flush=True)

    def _extra_admin_targets(self, primary):
        """پیویِ بقیهٔ مدیرها — اگر ارسال به مقصد اصلی شکست خورد."""
        pk = self._chat_key(primary)
        out = []
        seen = {pk} if pk else set()
        for a in (self.cfg.get("admin_ids") or []):
            try:
                a = int(a)
            except Exception:
                pass
            k = self._chat_key(a)
            if not k or k in seen:
                continue
            seen.add(k)
            out.append(a)
        return out

    @staticmethod
    def _looks_sqlite(path):
        base = os.path.basename(path or "").lower()
        return base.endswith(".db") or base.endswith(".session")

    @staticmethod
    def _sqlite_snapshot(src, dst, pacer=None):
        """کپیِ سازگار حتی وقتی WAL باز است. کپیِ خامِ فایلِ db بدون -wal دادهٔ تازه را جا می‌اندازد."""
        from urllib.parse import quote
        # mode=ro مانع ساخت دیتابیس خالی اگر فایل وسط کار حذف شود.
        uri = "file:" + quote(os.path.abspath(src), safe="/") + "?mode=ro"
        src_conn = sqlite3.connect(uri, uri=True, timeout=2)
        last_progress = time.monotonic()
        deadline = last_progress + 120
        last_remaining = None
        def progress(status, remaining, total):
            nonlocal last_progress, last_remaining
            current = time.monotonic()
            if current > deadline:
                raise TimeoutError("sqlite snapshot deadline")
            if last_remaining is None or remaining < last_remaining:
                last_progress = current
            elif current - last_progress > 30:
                raise TimeoutError("sqlite snapshot stalled")
            last_remaining = remaining
            if pacer is not None:
                pacer.checkpoint()
        try:
            dst_conn = sqlite3.connect(dst)
            try:
                src_conn.backup(dst_conn, pages=32, progress=progress, sleep=0.05)
            finally:
                dst_conn.close()
        finally:
            src_conn.close()

    def _iter_backup_sources(self):
        for src in (DB_FILE, SHOP_DB, CONFIG_FILE, BOT_SESSION_FILE):
            if os.path.isfile(src):
                yield src, os.path.basename(src)
            else:
                print(f"  ⚠️ پشتیبان: {src} نیست — رد شد", flush=True)
        for extra in (os.path.join(BASE_DIR, "jafj_ai.json"),
                      os.path.join(BASE_DIR, ".jafj_deploy_id")):
            if os.path.isfile(extra):
                yield extra, os.path.basename(extra)
        if os.path.isdir(CLIENTS_DIR):
            for root, dirs, files in os.walk(CLIENTS_DIR):
                for fn in files:
                    if backup_file_skipped(fn):
                        continue
                    fpath = os.path.join(root, fn)
                    if not os.path.isfile(fpath):
                        continue
                    arc = os.path.relpath(fpath, BASE_DIR).replace(os.sep, "/")
                    if not arc.startswith("clients/"):
                        arc = "clients/" + os.path.basename(fpath)
                    yield fpath, arc

    @_cpu_mark_activity("ساخت و فشرده‌سازی بک‌آپ")
    def _write_backup_zip(self, tmpzip):
        """zip پشتیبان. لاگ و فایل موقت نمی‌آیند؛ sqlite با backup API کپی می‌شود.
        اگر از سقف آپلود ربات بزرگ‌تر شد، فایل‌های غیرضروری حذف می‌شوند.
        خروجی: (تعداد فایل, بایت, فهرستِ حذف‌شده)."""
        work = tempfile.mkdtemp(prefix="jafj_bk_")
        pacer = _BackupCpuPacer(self)
        try:
            members = []
            for src, arc in self._iter_backup_sources():
                path = src
                if self._looks_sqlite(src):
                    snap = os.path.join(work, f"{len(members)}.snap")
                    try:
                        self._sqlite_snapshot(src, snap, pacer)
                        if os.path.isfile(snap) and os.path.getsize(snap) > 0:
                            path = snap
                    except Exception as e:
                        # بعضی فایل‌های قدیمی با پسوند session اصلاً sqlite نیستند.
                        # آن‌ها را عیناً نگه دار؛ اما کپی خامِ sqlite ممکن است
                        # WAL را جا بیندازد و نباید جای بک‌آپ سالم را بگیرد.
                        try:
                            with open(src, "rb") as check:
                                header = check.read(16)
                        except OSError:
                            raise RuntimeError(f"خواندن فایل پشتیبان ناموفق: {arc}") from e
                        if header == b"SQLite format 3\x00":
                            raise RuntimeError(f"اسنپ‌شات sqlite ناموفق: {arc}") from e
                        print(f"  ⚠️ فایل غیر sqlite با پسوند دیتابیس: {arc}", flush=True)
                        path = src
                    else:
                        if path == src:
                            raise RuntimeError(f"اسنپ‌شات sqlite خالی: {arc}")
                try:
                    sz = os.path.getsize(path)
                except Exception:
                    sz = 0
                members.append((path, arc, backup_arc_essential(arc), sz))
                pacer.checkpoint()
            essential = [m for m in members if m[2]]
            optional = sorted((m for m in members if not m[2]), key=lambda m: m[3])
            chosen = list(essential)
            used = sum(m[3] for m in chosen)
            omitted = []
            for item in optional:
                if used + item[3] > BOT_BACKUP_MAX_BYTES:
                    omitted.append(item[1])
                    continue
                chosen.append(item)
                used += item[3]
            if not chosen and members:
                # حتی یک فایل ضروری نبود — کوچک‌ترین‌ها را تا سقف بردار
                for item in sorted(members, key=lambda m: m[3]):
                    if used + item[3] > BOT_BACKUP_MAX_BYTES and chosen:
                        omitted.append(item[1])
                        continue
                    chosen.append(item)
                    used += item[3]
            if os.path.exists(tmpzip):
                try:
                    os.remove(tmpzip)
                except Exception:
                    pass
            def compress(level):
                failed = []
                with zipfile.ZipFile(tmpzip, "w", zipfile.ZIP_DEFLATED,
                                     compresslevel=level) as z:
                    for path, arc, essential, _ in chosen:
                        try:
                            info = zipfile.ZipInfo.from_file(path, arc)
                            info.compress_type = zipfile.ZIP_DEFLATED
                            info._compresslevel = level
                            with open(path, "rb") as source, z.open(info, "w") as dest:
                                while True:
                                    chunk = source.read(64 * 1024)
                                    if not chunk:
                                        break
                                    dest.write(chunk)
                                    pacer.checkpoint()
                            pacer.checkpoint()
                        except Exception as e:
                            # دادهٔ ضروری را هرگز بی‌صدا از یک بک‌آپ «موفق» حذف نکن.
                            if essential:
                                raise RuntimeError(f"فایل ضروری پشتیبان خوانده نشد: {arc}") from e
                            print(f"  ⚠️ پشتیبان {arc}: {type(e).__name__}", flush=True)
                            failed.append(arc)
                return failed

            # سطح ۱ مصرف CPU را معمولاً کاهش می‌دهد، با هزینهٔ فایل بزرگ‌تر.
            omitted.extend(compress(1))
            size = os.path.getsize(tmpzip)
            # اگر فایل سبک از سقف امن عبور کرد، سطح قبلی را امتحان کن تا
            # بک‌آپی که با فشرده‌سازی قوی‌تر قابل ارسال است از دست نرود.
            if size > BOT_BACKUP_MAX_BYTES:
                print("  📦 بک‌آپ بزرگ است — فشرده‌سازی مجدد برای سقف تلگرام", flush=True)
                retry_failed = compress(6)
                omitted = [arc for arc in omitted if arc not in {m[1] for m in chosen}]
                omitted.extend(retry_failed)
                size = os.path.getsize(tmpzip)
            try:
                with zipfile.ZipFile(tmpzip, "r") as z:
                    zcount = len(z.namelist())
            except Exception:
                zcount = 0
            if omitted:
                print(f"  ℹ️ {len(omitted)} فایل غیرضروری از پشتیبان جا ماند تا حجم از سقف تلگرام رد نشود",
                      flush=True)
            return zcount, size, omitted
        finally:
            shutil.rmtree(work, ignore_errors=True)

    async def _upload_backup(self, target, tmpzip, caption):
        """فایل را در چت مقصد بگذار (edit همان تک‌پیام، وگرنه ارسال تازه).
        اگر مقصد در دسترس نبود، از پیامِ پشتیبانِ قبلی در چتِ دیگر ادامه بده.
        خروجی: (مقصدِ واقعی, پیامِ فرستاده‌شده)."""
        old_msg = await self._find_last_backup_msg(target)
        if old_msg is not None and not self._msg_has_media(old_msg):
            # پیامِ متنی که فقط نشانه را نقل کرده فایل نیست؛ edit رویش بک‌آپ نمی‌سازد.
            old_msg = None
        if old_msg is None and not await self._backup_target_reachable(target):
            alt_t, alt_m = None, None
            try:
                alt_t, alt_m = await self._find_backup_anywhere(limit=40, skip=target)
            except Exception as e:
                print(f"  ⚠️ جستجوی سراسری برای ادامهٔ پشتیبان: "
                      f"{type(e).__name__}: {e}", flush=True)
            if alt_m is not None and self._msg_has_media(alt_m):
                print(f"  🔁 ادامهٔ پشتیبان از پیامِ قبلی در چت "
                      f"{self._chat_key(alt_t)} (مقصد فعلی: "
                      f"{self._chat_key(target)})", flush=True)
                target, old_msg = alt_t, alt_m
                self._remember_backup_pointer(alt_t, getattr(alt_m, "id", None))
        sent = None
        if old_msg is not None:
            try:
                sent = await self.bot.edit_message(
                    target, getattr(old_msg, "id", None), caption,
                    file=tmpzip, force_document=True)
            except Exception as e:
                print(f"  ℹ️ به‌روزرسانیِ همان پیام پشتیبان ممکن نشد "
                      f"({type(e).__name__}) — پیام تازه جایگزین قبلی می‌شود", flush=True)
                sent = None
        if sent is None:
            try:
                sent = await self.bot.send_file(
                    target, tmpzip, caption=caption, force_document=True)
            except TypeError:
                sent = await self.bot.send_file(target, tmpzip, caption=caption)
            if old_msg is not None:
                try:
                    await self.bot.delete_messages(target, [getattr(old_msg, "id", None)])
                except Exception:
                    pass
        return target, sent

    async def _tell_admins_backup_failed(self, reason):
        """خطای پشتیبانِ خودکار را به پیوی مدیر بگو — وگرنه فقط در لاگ می‌ماند
        و مدیر فکر می‌کند بک‌آپ گرفته می‌شود."""
        reason = (reason or "").strip()
        if not reason or "بدون تغییر" in reason:
            return
        now_t = time.time()
        last = getattr(self, "_backup_fail_at", 0)
        last_reason = getattr(self, "_backup_fail_reason", "")
        if reason == last_reason and now_t - last < 1800:
            return
        self._backup_fail_at = now_t
        self._backup_fail_reason = reason
        text = ("⚠️ <b>پشتیبان گرفته نشد</b>\n\n"
                f"{reason}\n\n"
                "تا وقتی این خطا هست، بعد از دیپلوی اطلاعات برنمی‌گردد.\n"
                "دوباره: <code>.backup</code>")
        for a in (self.cfg.get("admin_ids") or []):
            try:
                await self.say(a, text, key="backup_fail")
            except Exception:
                pass

    def _is_admin_backup_file(self, ev):
        """تشخیص سریع: پیام‌های معمولی نباید منتظر قفلِ بک‌آپ بمانند."""
        uid = getattr(ev, "sender_id", None)
        if not self.is_admin(uid):
            return False
        st = (self.fsm.get(uid) or {}).get("step")
        if st in ("tut_set", "sec_set", "sample_set"):
            return False
        msg = getattr(ev, "message", None) or ev
        doc = getattr(ev, "document", None) or getattr(msg, "document", None)
        if doc is None:
            return False
        name = ""
        try:
            f = getattr(msg, "file", None) or getattr(ev, "file", None)
            name = getattr(f, "name", None) or ""
        except Exception:
            name = ""
        caption = ""
        try:
            caption = (getattr(ev, "raw_text", None) or getattr(msg, "message", None) or "")
        except Exception:
            caption = ""
        mime = (getattr(doc, "mime_type", None) or "")
        looks = (str(name).lower().endswith(".zip") or "zip" in str(mime).lower()
                 or BACKUP_TAG in str(caption) or "پشتیبان" in str(caption))
        return bool(looks)

    async def accept_admin_backup_file(self, ev):
        # هر پیام مدیر از اینجا می‌گذرد. فقط فایل پشتیبان باید منتظر قفل شود؛
        # وگرنه یک upload طولانی حتی /start و /hanglog را هم متوقف می‌کند.
        if not self._is_admin_backup_file(ev):
            return False
        async with self._backup_operation_lock():
            return await self._accept_admin_backup_file_locked(ev)

    async def _accept_admin_backup_file_locked(self, ev):
        """ذخیرهٔ فایل ارسالی مدیر، سریالی با بک‌آپ و بازیابی."""
        # وضعیت و دسترسی ممکن است در زمان انتظار برای قفل تغییر کرده باشد.
        if not self._is_admin_backup_file(ev):
            return False
        uid = getattr(ev, "sender_id", None)
        msg = getattr(ev, "message", None) or ev
        tmp = os.path.join(tempfile.gettempdir(),
                           f"jafj_in_{int(time.time())}_{os.getpid()}.zip")
        try:
            downloaded = await self.bot.download_media(msg, file=tmp)
        except Exception as e:
            await self.say(uid, f"❌ دانلود فایل پشتیبان نشد: {type(e).__name__}")
            return True
        path = downloaded if isinstance(downloaded, str) and os.path.isfile(downloaded) else tmp
        if not os.path.isfile(path):
            await self.say(uid, "❌ فایل پشتیبان دانلود نشد.")
            return True
        try:
            with zipfile.ZipFile(path, "r") as z:
                names = [n.replace("\\", "/") for n in z.namelist()]
        except Exception:
            await self.say(uid, "❌ این فایل zip سالم نیست.")
            return True
        if not any(os.path.basename(n) in ("manager.db", "shop.db", "manager_config.json")
                   or n.startswith("clients/") for n in names):
            await self.say(uid, "این zip پشتیبان جفج نیست — داخلش manager.db نیست.")
            return True
        try:
            latest = os.path.join(BASE_DIR, "jafj_backup_latest.zip")
            shutil.copy2(path, latest)
            try:
                os.chmod(latest, 0o600)
            except Exception:
                pass
            # همان zipی که مدیر فرستاده، جدا هم نگه داشته می‌شود: `.restore` دستی
            # اول از همین فایل بازیابی می‌کند، نه از پشتیبانِ قدیمیِ تلگرام.
            upload = _admin_upload_path()
            shutil.copy2(path, upload)
            try:
                os.chmod(upload, 0o600)
            except Exception:
                pass
        except Exception as e:
            await self.say(uid, f"❌ ذخیرهٔ فایل پشتیبان نشد: {type(e).__name__}")
            return True
        await self.say(uid,
                       "✅ <b>فایل پشتیبان ذخیره شد</b>\n\n"
                       "برای برگرداندن اطلاعات دکمه‌ی زیر را بزن یا بفرست: <code>.restore</code>",
                       [[B("♻️ بازیابی اطلاعات همین الان", "a:restore", "success")],
                        [B("🛠 پنل مدیر", "a:home", "primary")]])
        return True

    async def _graceful_stop(self):
        """SIGTERM دیپلوی: قبل از مرگ یک پشتیبان پایانی بگیر. دیتابیس خالی
        پشتیبانِ قبلی را بازنویسی نمی‌کند."""
        if getattr(self, "_stopping", False):
            return
        self._stopping = True
        stop = getattr(self, "_cpu_monitor_stop", None)
        if stop is not None:
            stop.set()
        # به نگهبانِ سکوت بگو «این خاموشیِ عمدی است» — وگرنه ممکن است وسطِ
        # پشتیبانِ پایانی پروسه را با کدِ ۷۵ ببندد.
        LIVE["stopping"] = True
        print("  📦 خاموشی — پشتیبان پایانی…", flush=True)
        try:
            n = 0
            try:
                r = self.db.x("SELECT COUNT(*) c FROM clients", (), "one")
                n = r["c"] if r else 0
            except Exception:
                n = 0
            if n or getattr(self, "_allow_empty_backup_once", False):
                await asyncio.wait_for(self.backup_once(force=True), timeout=20)
            else:
                print("  ℹ️ دیتابیس خالی است — پشتیبان قبلی بازنویسی نشد", flush=True)
        except Exception as e:
            print(f"  ⚠️ پشتیبان پایانی: {type(e).__name__}: {e}", flush=True)
        try:
            self.sup.shutdown()
        except Exception:
            pass
        try:
            if self.bot is not None:
                await self.bot.disconnect()
        except Exception:
            pass

    async def _empty_db_backup_guard(self, target):
        """اگر دیتابیس خالی است و پشتیبانِ پُرِ قبلی در تلگرام هست، پیام خطا برمی‌گرداند
        (یعنی پشتیبانِ خالی نباید آن را بازنویسی کند). وگرنه None = ادامه بده.

        پشتیبانِ قبلی ۰ مشتری داشته باشد، بازنویسی بی‌خطر است. اگر جست‌وجو هم
        شکست بخورد و نمی‌دانیم پشتیبانی هست یا نه، محتاطانه نفرست."""
        if getattr(self, "_allow_empty_backup_once", False):
            self._allow_empty_backup_once = False
            return None
        try:
            prev = await self._find_last_backup_msg(target, limit=100)
        except Exception:
            prev = None
        if prev is None:
            if getattr(self, "_last_iter_ok", True):
                return None  # پشتیبانی در این چت نبوده؛ چیزی برای حفظ کردن نیست
            return ("⚠️ دیتابیس خالی است و نتوانستم پشتیبانِ قبلی را در تلگرام پیدا کنم؛ "
                    "پشتیبانِ خالی نفرستادم.\n"
                    "راهِ درست: روی همان پیامِ پشتیبان <b>ریپلای</b> کن و بنویس "
                    "<code>.restore</code> — یا آیدی‌اش را بفرست: "
                    "<code>.restore 12345</code>.")
        if not self._msg_has_media(prev):
            return None
        prev_n = _backup_clients_count(getattr(prev, "caption", "") or getattr(prev, "text", ""))
        if prev_n == 0:
            return None
        shown = _fa_digits(prev_n) if prev_n is not None else "؟"
        return (f"⚠️ دیتابیسِ الان خالی است (۰ مشتری) و پشتیبانِ قبلیِ ({shown} مشتری) "
                "بازنویسی نشد.\n"
                "اگر بعد از آپدیت هستی، <code>.restore</code> را بزن (یا فایل zip پشتیبان را "
                "در پیوی بفرست و بعد <code>.restore</code>).\n"
                "اگر «پشتیبانی پیدا نشد» داد: روی همان پیامِ پشتیبان ریپلای کن و "
                "<code>.restore</code> بفرست، یا آیدی‌اش را بده: "
                "<code>.restore 12345</code>.")

    def _backup_operation_lock(self):
        # فقط در event loop ساخته می‌شود؛ backup و restore روی یک داده هم‌زمان نیستند.
        lock = getattr(self, "_backup_async_lock", None)
        if lock is None:
            lock = self._backup_async_lock = asyncio.Lock()
        return lock

    async def _backup_run_blocking(self, fn, *args):
        """کار سنگین بیرون حلقه؛ لغو، worker را پیش از پاک‌کردن فایل رها نمی‌کند."""
        future = asyncio.get_running_loop().run_in_executor(None, fn, *args)
        try:
            return await asyncio.shield(future)
        except asyncio.CancelledError:
            # asyncio نمی‌تواند کار thread را قطع کند. تا اتمام آن نگه می‌داریم
            # تا فایل موقت و قفل قبل از پایان نوشتن پاک/آزاد نشوند.
            while not future.done():
                try:
                    await asyncio.shield(future)
                except asyncio.CancelledError:
                    continue
                except Exception:
                    break
            if future.done() and not future.cancelled():
                try:
                    future.result()
                except Exception:
                    pass
            raise

    async def backup_once(self, force=False):
        """پشتیبان و بازیابی هم‌زمان روی داده‌های مشترک انجام نمی‌شوند."""
        async with self._backup_operation_lock():
            return await self._backup_once_locked(force=force)

    async def _backup_once_locked(self, force=False):
        """یک پشتیبان zip بساز و به تلگرام + دیسک بفرست.
        اگر اثرانگشت عوض نشده و force نباشد، کاری نمی‌کند."""
        target = self._backup_target()
        if not target:
            # مقصد پیدا نشد (نه BACKUP_CHAT هست نه admin_ids). به‌جای تسلیم شدن
            # — که یعنی پشتیبان تا ابد قطع می‌شود — چتِ همان «پیامِ پشتیبانِ
            # قبلی» را سراسری پیدا کن و از همان ادامه بده.
            fb_t, fb_m = None, None
            if self.bot is not None:
                try:
                    fb_t, fb_m = await self._find_backup_anywhere(limit=40)
                except Exception as e:
                    print(f"  ⚠️ پیدا کردن مقصد از پیامِ قبلی: {type(e).__name__}: {e}",
                          flush=True)
            if fb_t is None:
                return False, "BACKUP_CHAT تنظیم نشده"
            target = fb_t
            self._backup_msg_id = getattr(fb_m, "id", None)
            print(f"  🔁 مقصدِ پشتیبان تنظیم نبود — از پیامِ پشتیبانِ قبلی در "
                  f"{self._chat_key(target)} ادامه می‌دهیم", flush=True)
        if self.bot is None:
            return False, "ربات وصل نیست"
        try:
            is_pub, info = await self._backup_target_is_public(target)
            if is_pub:
                msg = f"⚠️ پشتیبان شامل سشن تلگرام همهٔ مشتری‌هاست؛ کانال {info} عمومی است — ارسال رد شد."
                print(f"  {msg}", flush=True)
                try:
                    for a in (self.cfg.get("admin_ids") or []):
                        await self.say(a, msg)
                except Exception:
                    pass
                return False, msg
        except Exception as e:
            print(f"  ⚠️ بررسی عمومی/خصوصی: {e}", flush=True)
        # ترد مستقل و اتصال‌های جداگانه: اثرانگشت هم حلقهٔ تلگرام را معطل نکند.
        try:
            fp = await self._backup_run_blocking(
                self._backup_fingerprint, False, True)
        except Exception as e:
            return False, f"بررسی تغییرات پشتیبان ناموفق: {type(e).__name__}"
        if not force:
            if not bool(self.cfg.get("auto_backup_on", True)):
                return False, "بدون تغییر"
            self._load_backup_fp()
            if getattr(self, "_backup_fp", None) == fp:
                # داده‌ها از آخرین پشتیبان عوض نشده — ولی فقط وقتی «هیچ کاری
                # نکن» که پیامِ پشتیبان هنوز در چت هست؛ اگر مدیر آن تک‌پیام را
                # پاک کرده باشد، همین‌جا دوباره ساخته می‌شود.
                existing = await self._find_last_backup_msg(target, limit=100)
                # پیامِ متنیِ بی‌فایل «پشتیبان موجود» نیست — وگرنه بک‌آپ هرگز فرستاده نمی‌شود.
                if (existing is not None and self._msg_has_media(existing)) or not getattr(self, "_last_iter_ok", True):
                    return False, "بدون تغییر"
        # SQLite backup API فایل WAL را در snapshot لحاظ می‌کند؛ checkpoint
        # سنگین TRUNCATE اینجا لازم نیست و ممکن است حلقهٔ ربات را معطل کند.
        for store in (getattr(self, "db", None), getattr(self, "shop", None)):
            try:
                if store is not None:
                    store.c.commit()
            except Exception:
                pass
        fd, tmpzip = tempfile.mkstemp(prefix="jafj_backup_", suffix=".zip")
        os.close(fd)
        try:
            zcount, sz, omitted = await self._backup_run_blocking(self._write_backup_zip, tmpzip)
            if zcount <= 0 or not os.path.isfile(tmpzip) or sz <= 0:
                return False, "فایل پشتیبان خالی ساخته شد"
            try:
                cnt = self.db.x("SELECT COUNT(*) c FROM clients", (), "one")
                n = cnt["c"] if cnt else 0
            except Exception:
                n = "?"
            # باگِ «بعد از آپدیت صفر مشتری»: دیتابیسِ خالی (مثلاً بوتِ تازه قبل از
            # بازیابی) نباید پشتیبانِ پُرِ قبلی را در تلگرام و دیسک بازنویسی کند.
            if n == 0:
                guard_msg = await self._empty_db_backup_guard(target)
                if guard_msg:
                    return False, guard_msg
            try:
                await self._backup_run_blocking(self._save_local_backup_copy, tmpzip)
            except Exception as e:
                print(f"  ⚠️ ذخیره محلی پشتیبان: {e}", flush=True)
            if sz > 50 * 1024 * 1024:
                return False, (f"حجم پشتیبان {sz // (1024 * 1024)}MB از سقف ۵۰MB ربات تلگرام بیشتر است — ارسال رد می‌شد")
            omit_note = f" omitted={len(omitted)}" if omitted else ""
            caption = (f"{BACKUP_TAG} {datetime.now():%Y-%m-%d %H:%M} clients={n} files={zcount} "
                       f"size={sz//1024}KB build={BUILD_VERSION}{omit_note} \u2502 "
                       f"\U0001F4E6 پشتیبان کامل (DB+shop+clients) — همین «یک» پیام همیشه با آخرین نسخه به‌روز می‌شود؛ پاکش نکن؛ بعد از هر دیپلوی/ری‌استارت Render خودکار برمی‌گردد")
            # ── فقط «یک» پیامِ پشتیبان در این چت بماند ──
            # پیام پشتیبان قبلی پیدا می‌شود؛ اگر بود، مدیای «همان» پیام با zip
            # تازه عوض می‌شود (edit) — پیام جدیدی به پیوی اضافه نمی‌شود. اگر edit
            # ممکن نبود (مثلاً ۴۸ ساعت از ارسالش گذشته باشد)، پیام تازه می‌رود و
            # قبلی درجا پاک می‌شود؛ نتیجه در هر دو حالت: فقط یک پیام پشتیبان.
            sent = None
            last_up = None
            try_targets = [target] + self._extra_admin_targets(target)
            for i, t in enumerate(try_targets):
                try:
                    target, sent = await self._upload_backup(t, tmpzip, caption)
                    break
                except Exception as e:
                    last_up = e
                    print(f"  ⚠️ ارسال پشتیبان به {self._chat_key(t)}: "
                          f"{type(e).__name__}: {e}", flush=True)
                    if i + 1 < len(try_targets):
                        print("  🔁 تلاش در پیوی مدیر بعدی…", flush=True)
            if sent is None:
                raise last_up or RuntimeError("ارسال پشتیبان ناموفق")
            try:
                self._remember_backup_pointer(target, getattr(sent, "id", None))
            except Exception:
                self._backup_msg_id = getattr(sent, "id", None)
            # تایید متنی کوتاه در PV مدیر (غیر از فایل) — فقط در حالت دستی / موقع اولین بکاپ خودکار بعد از تغییری بزرگ
            # از اسپم جلوگیری: فقط اگر force بود یا بیش از یک ساعت از آخرین تایید گذشته
            try:
                if force:
                    kb = sz//1024
                    await self.say(target, f"✅ <b>پشتیبان ذخیره شد</b>\n\n"
                                           f"👥 {n} مشتری · 📦 {zcount} فایل · {kb}KB\n"
                                           f"جای ذخیره: تلگرام (این چت) + <code>{os.path.join(BASE_DIR, 'jafj_backup_latest.zip')}</code>" + (f" + <code>{os.path.join(BASE_DIR, 'backups/')}</code>" if os.path.isdir(os.path.join(BASE_DIR, "backups")) else "") + "\n"
                                           f"این پشتیبان شامل همه "
                                           f"\u00ab<code>clients/</code>\u00bb (سشن و تنظیمات هر اکانت) هم هست و بعد از ری‌استارت Render خودکار بازیابی می‌شود."
                                           + ("\n\n⚠️ ربات سیگنال خاموشی دریافت کرده است؛ فرستندهٔ سیگنال مشخص نیست."
                                              if getattr(self, "_stopping", False) else ""))
            except Exception:
                pass
            # اثرانگشتِ قبل از شروع؛ تغییرِ حین ساخت یا ارسال نباید گم شود.
            self._save_backup_fp(fp)
            print(f"  📦 پشتیبان فرستاده شد به {target} ({sz} بایت, {zcount} فایل, {n} مشتری)", flush=True)
            return True, f"پشتیبان فرستاده شد ({n} مشتری, {zcount} فایل, {sz//1024}KB) — تلگرام + دیسک"
        except asyncio.CancelledError:
            raise
        except Exception as e:
            print(f"  ⚠️ پشتیبان: {type(e).__name__}: {e}", flush=True)
            import traceback
            traceback.print_exc()
            return False, f"{type(e).__name__}: {e}"
        finally:
            try:
                os.remove(tmpzip)
            except OSError:
                pass

    async def heartbeat_loop(self):
        """هر دقیقه یک ضربان بنویس و هر ۵ دقیقه حافظه را در لاگ بگو."""
        _last_log = 0.0
        while True:
            try:
                # «حلقه زنده است» — همین نشانه است که نگهبانِ سکوت (thread)
                # کهنه‌شدنش را «گیر کردن» حساب می‌کند.
                mark_live("loop")
                free = mem_available_mb()
                try:
                    running = self.sup.running_count()
                except Exception:
                    running = None
                write_heartbeat(BASE_DIR, {"free": free, "clients": running})
                nowt = time.time()
                if nowt - _last_log >= 300:
                    _last_log = nowt
                    parts = [f"RAM آزاد: {free if free is not None else '?'}MB",
                             f"سلف‌های روشن: "
                             f"{running if running is not None else '?'}"]
                    try:
                        kids = self.sup.children_rss()
                        if kids:
                            tot = round(sum(k[2] for k in kids), 1)
                            worst = sorted(kids, key=lambda k: -k[2])[:3]
                            parts.append(
                                f"مصرفِ سلف‌ها: {tot}MB / {len(kids)} اکانت "
                                f"(~{round(tot / len(kids), 1)}MB هر کدام، PSS) (" +
                                ", ".join(f"{u}:{mb}MB" for u, _p, mb in worst) +
                                ")")
                        me = proc_pss_mb(os.getpid()) or proc_rss_mb(os.getpid())
                        if me:
                            parts.append(f"مدیر: {me}MB")
                    except Exception:
                        pass
                    print("  💾 " + " · ".join(parts), flush=True)
                    if free is not None and free < 80:
                        print("  ⚠️ حافظه‌ی آزاد کم است — اگر ادامه پیدا کند "
                              "کرنل پروسه را می‌کشد (سرور آفلاین می‌شود). "
                              "تعدادِ سلف‌ها را کم کن یا BACKUP_EVERY را بالا ببر.",
                              flush=True)
            except Exception as e:
                print(f"  ⚠️ ضربان: {type(e).__name__}", flush=True)
            await asyncio.sleep(HEARTBEAT_EVERY)

    async def liveness_loop(self):
        """هر JAFJ_PING_SECS یک درخواستِ واقعی به تلگرام — «پروسه هست، ربات مرده» نه.

        چرا لازم بود: heartbeat_loop فقط ثابت می‌کند **asyncio** زنده است، نه
        اینکه تلگرام جواب می‌دهد. با اتصالِ نیمه‌باز (NAT/فایروالِ میزبان
        مسیر را می‌بندد، یا قطعیِ سمتِ تلگرام که FIN نمی‌فرستد) پروسه سالم
        به‌نظر می‌رسد، `/healthz` هم ۲۰۰ می‌دهد، ولی هیچ پیامی جواب نمی‌گیرد.
        روی Wispbyte این دقیقاً همان «بعد از مدتی استفاده آفلاین می‌شود» بود.
        """
        every = ping_seconds()
        if every <= 0:
            print("  ℹ️ نگهبانِ پینگ خاموش است (JAFJ_PING_SECS=0)", flush=True)
            return
        # کمی صبر تا اتصالِ اولیه و بازیابیِ بوت تمام شود.
        await asyncio.sleep(min(45.0, every))
        fails = 0
        while True:
            mark_live("loop")
            ok, err = await self._ping_telegram()
            if ok:
                if fails:
                    print(f"  ✅ ربات دوباره جواب می‌دهد (بعد از {fails} "
                          f"پینگِ ناموفق)", flush=True)
                fails = 0
                mark_live("ping")
            else:
                fails += 1
                mark_live("ping_fail", {"fails": fails, "err": err})
                verdict = ping_verdict(fails)
                print(f"  ⚠️ پینگِ تلگرام ناموفق ({fails}): {err} — "
                      f"تصمیم: {verdict}", flush=True)
                if verdict == "reconnect":
                    await self._drop_stale_connection(err)
                elif verdict == "restart":
                    self._die_on_silence(fails, err)
                    return
            try:
                await asyncio.sleep(every)
            except asyncio.CancelledError:
                raise

    async def _ping_telegram(self):
        """(سالم؟, خطا) — یک رفت‌وبرگشتِ واقعی با تلگرام، با مهلت."""
        bot = getattr(self, "bot", None)
        if bot is None:
            return False, "کلاینت ساخته نشده"
        try:
            if hasattr(bot, "is_connected") and not bot.is_connected():
                return False, "اتصال بسته است"
        except Exception:
            pass
        timeout = ping_timeout()
        try:
            req = _ping_request()
            if req is not None:
                await asyncio.wait_for(bot(req), timeout=timeout)
            else:
                await asyncio.wait_for(bot.get_me(), timeout=timeout)
            return True, ""
        except asyncio.CancelledError:
            raise
        except asyncio.TimeoutError:
            return False, f"بی‌پاسخ بعد از {int(timeout)}s"
        except Exception as e:
            return False, f"{type(e).__name__}: {e}"

    async def _drop_stale_connection(self, why=""):
        """اتصالِ نیمه‌باز را ببند؛ خودِ serve_forever دوباره وصل می‌کند.

        عمداً اینجا connect() صدا زده نمی‌شود: run_until_disconnected با همین
        بستن برمی‌گردد و serve_forever همان نمونهٔ کلاینت را (با هندلرهای
        حفظ‌شده) دوباره وصل می‌کند — دو مسئولِ اتصال، همان چیزی است که
        «🔄 اتصال قطع شد»ِ بی‌پایان می‌ساخت.
        """
        print(f"  🔌 اتصالِ نیمه‌باز بسته می‌شود تا از نو ساخته شود ({why})",
              flush=True)
        try:
            await asyncio.wait_for(self.bot.disconnect(), timeout=20)
        except asyncio.CancelledError:
            raise
        except Exception as e:
            print(f"  ⚠️ بستنِ اتصال: {type(e).__name__}: {e}", flush=True)

    def _die_on_silence(self, fails, err):
        """پروسه را با کدِ ۷۵ ببند تا ناظر یک نسخه‌ی تازه بالا بیاورد.

        چرا خروج و نه «فقط لاگ کردن»: تا وقتی پروسه «روشن» است هیچ میزبانی
        ری‌استارت نمی‌کند؛ نتیجه همان «آفلاین ماند تا دستی ری‌استارت کنم» بود.
        """
        detail = (f"ربات {fails} بار پیاپی به تلگرام جواب نداد: {err}\n"
                  f"host={HOST_LABEL} build={BUILD_VERSION} "
                  f"ping_every={int(ping_seconds())}s")
        print(f"  ⛔ {detail}\n     → خروج با کدِ ۷۵ تا ناظر نسخه‌ی تازه "
              f"بالا بیاورد", flush=True)
        try:
            log_crash("silence", detail)
        except Exception:
            pass
        try:
            write_heartbeat(BASE_DIR, {"stage": "silence-exit",
                                       "fails": fails, "err": err})
        except Exception:
            pass
        LIVE["stopping"] = True
        try:
            self.sup.shutdown()
        except Exception:
            pass
        os._exit(75)

    async def backup_loop(self):
        """حلقه پشتیبان خودکار — هر backup_interval() یکبار، بیدار و اثرانگشت را چک می‌کند.
        روی Render رایگان پیش‌فرض ۱۲۰ثانیه است تا بین دو دیپلوی نهایت ۲ دقیقه داده از دست برود.
        اگر ارسال شکست بخورد، دلیلش به پیوی مدیر می‌رود — سکوت یعنی «بک‌آپ نمی‌گیرد»."""
        await asyncio.sleep(3)
        # پاک‌سازیِ یکباره‌ی پیام‌های پشتیبانِ اضافیِ مانده از نسخه‌های قبل —
        # قبلاً هر پشتیبان یک پیامِ تازه در پیوی مدیر می‌گذاشت و انباشته می‌شد.
        # حالا به‌جز «تک‌پیامِ» پشتیبان، بقیه با سقفِ محدود پاک می‌شوند.
        try:
            if not getattr(self, "_backup_extra_cleaned", False):
                self._backup_extra_cleaned = True
                _t = self._backup_target()
                if _t and self.bot is not None:
                    _keep = await self._find_last_backup_msg(_t, limit=100)
                    _kid = getattr(_keep, "id", None) if _keep is not None else None
                    await self._cleanup_extra_backup_msgs(_t, keep_id=_kid)
        except Exception as e:
            print(f"  ⚠️ پاک‌سازی پشتیبان‌های اضافی: {type(e).__name__}", flush=True)
        while True:
            try:
                interval = backup_interval()
                try:
                    ok, msg = await self.backup_once(force=False)
                    if ok:
                        print(f"  📦 پشتیبان خودکار: {msg}", flush=True)
                    elif "بدون تغییر" not in (msg or ""):
                        print(f"  ℹ️ پشتیبان خودکار: {msg}", flush=True)
                        if "عمومی" not in (msg or ""):
                            await self._tell_admins_backup_failed(msg)
                        # FloodWait را با خوابِ خودش رد کن، نه با چکش زدن هر ۲ دقیقه
                        if msg and "FloodWait" in msg:
                            digits_only = "".join(ch for ch in msg if ch.isdigit())
                            try:
                                interval = min(3600, max(interval, int(digits_only or 0) + 5))
                            except Exception:
                                pass
                except Exception as e:
                    print(f"  ⚠️ پشتیبان خودکار: {type(e).__name__}: {e}", flush=True)
                    import traceback
                    traceback.print_exc()
                    await self._tell_admins_backup_failed(f"{type(e).__name__}: {e}")
                await asyncio.sleep(interval)
            except asyncio.CancelledError:
                break
            except Exception as e:
                print(f"backup_loop: {e}", flush=True)
                await asyncio.sleep(120)

    async def restore_from_backup(self, force=False, ref_chat=None, ref_msg_id=None):
        async with self._backup_operation_lock():
            return await self._restore_from_backup_locked(force, ref_chat, ref_msg_id)

    async def _restore_from_backup_locked(self, force=False, ref_chat=None, ref_msg_id=None):
        """بازیابی از آخرین پشتیبان تلگرام (یا کپی محلی روی دیسک). (موفق, پیام)

        `ref_msg_id` (و اختیاری `ref_chat`): پیامِ دقیقِ پشتیبان — از ریپلایِ
        مدیر روی همان پیام یا از لینکِ `t.me/...`. این تنها راهِ قطعیِ بازیابی
        است وقتی دیسک پاک شده و ربات هم اجازه‌ی گشتن در تاریخچه را ندارد.
        """
        target = self._backup_target()
        if not target:
            return False, "BACKUP_CHAT تنظیم نشده"
        if self.bot is None:
            return False, "ربات وصل نیست"
        try:
            cnt = self.db.x("SELECT COUNT(*) c FROM clients", (), "one")
            n0 = cnt["c"] if cnt else 0
        except Exception:
            n0 = 0
        if n0 != 0 and not force:
            return False, f"دیتابیس خالی نیست ({n0} مشتری)"
        # زیپی که مدیر همین الان در پیوی فرستاده، در `.restore` دستی بر پشتیبانِ
        # قدیمیِ تلگرام مقدم است. (بوت خودکار همان قبلی را می‌خواند.)
        admin_up = _admin_upload_path()
        prefer_admin = bool(force) and os.path.isfile(admin_up) and not ref_msg_id
        # ── پیدا کردنِ پیامِ پشتیبان ──
        # اول در چتِ مقصد، با اولویتِ «فایل» بر متنِ نقل‌قولی (prefer_media):
        # پیامِ متنی که فقط نشانهٔ JAFJBACKUP1 را دارد هیچ zipی ندارد و اگر
        # همان انتخاب شود، بازیابی شکست می‌خورد.
        last = None
        search_err = None
        if ref_msg_id:
            # پیام را دقیقاً با آیدی می‌خوانیم؛ هیچ گشتنی لازم نیست.
            cand_chats = []
            for ch in (ref_chat, target) + tuple(self.cfg.get("admin_ids") or []):
                if ch is None:
                    continue
                k = self._chat_key(ch)
                if k and k not in [self._chat_key(c) for c in cand_chats]:
                    cand_chats.append(ch)
            for ch in cand_chats:
                try:
                    got = await self.bot.get_messages(ch, ids=[int(ref_msg_id)])
                    m = got[0] if isinstance(got, (list, tuple)) and got else got
                    if m is not None and getattr(m, "id", None):
                        last, target = m, ch
                        self._remember_backup_pointer(ch, getattr(m, "id", None))
                        print(f"  🔗 پشتیبان با ارجاعِ مدیر در چت "
                              f"{self._chat_key(ch)} (id={ref_msg_id})", flush=True)
                        break
                except Exception as e:
                    print(f"  ⚠️ خواندنِ پیامِ {ref_msg_id} در "
                          f"{self._chat_key(ch)}: {type(e).__name__}", flush=True)
            if last is None:
                return False, (f"پیامِ پشتیبان با شناسهٔ {ref_msg_id} پیدا نشد. "
                               "آیدی را چک کن یا همان zip را در پیوی بفرست و "
                               "<code>.restore</code> بزن.")
        if last is None and not ref_msg_id and not prefer_admin:
            # اشاره‌گر (چت + آیدی) از meta/cfg — بدون گشتن در تاریخچه
            p_chat, p_msg = await self._find_backup_by_pointer(target)
            if p_msg is not None:
                last, target = p_msg, p_chat
        try:
            if not prefer_admin and last is None:
                last = await self._find_last_backup_msg(target, limit=200, prefer_media=True)
        except Exception as e:
            search_err = f"{type(e).__name__}: {e}"
        if last is None and not prefer_admin and not ref_msg_id:
            # چتِ مقصد چیزی نداشت (بعد از دیپلوی BACKUP_CHAT/admin_ids عوض یا
            # پاک شده) → جست‌وجوی سراسری در همهٔ چت‌های ربات؛ تک‌پیامِ پشتیبان
            # هر جا باشد پیدا می‌شود و بازیابی از دست نمی‌رود.
            alt_target, alt_msg = None, None
            try:
                alt_target, alt_msg = await self._find_backup_anywhere(limit=100, skip=target)
            except Exception as e:
                print(f"  ⚠️ جست‌وجوی سراسری پشتیبان: {type(e).__name__}: {e}", flush=True)
            if alt_msg is not None:
                print(f"  🔁 پشتیبان در چتِ {self._chat_key(alt_target)} پیدا شد "
                      f"(مقصدِ تنظیم‌شده: {self._chat_key(target)})", flush=True)
                target, last = alt_target, alt_msg
                try:
                    self._remember_backup_pointer(alt_target, getattr(last, "id", None))
                except Exception:
                    pass
            elif search_err:
                return False, f"خطا در جستجوی پشتیبان: {search_err}"
        if last is None:
            # تلگرام چیزی نداشت — اگر کپی محلی روی Disk هست، همان را امتحان کن (برای Render Disk)
            for cand in (((admin_up,) if prefer_admin else ()) + (os.path.join(BASE_DIR, "jafj_backup_latest.zip"), os.path.join(BASE_DIR, "backups", "jafj_backup_latest.zip"))):
                if os.path.isfile(cand):
                    print(f"  ℹ️ پشتیبان تلگرام نبود؛ کپی محلی {cand} امتحان می‌شود", flush=True)
                    try:
                        # مستقیم به مرحله استخراج برو — کافیست zip_path را روی همان فایل بگذاریم
                        # برای هماهنگی با کد پایین، یک tmp کپی می‌سازیم
                        tmpzip2 = os.path.join(tempfile.gettempdir(), f"jafj_restore_local_{int(time.time())}_{os.getpid()}.zip")
                        shutil.copy2(cand, tmpzip2)
                        last = None  # علامت اینکه از local می‌آییم
                        # ترفند: zip_path محلی را نگه دار و به بعد بپر — ساده: اینجا استخراج را صدا زده و برگردیم
                        # ولی چون کد پایین انتظار دانلود از last را دارد، یک مسیر جدا باز می‌کنیم:
                        zip_path = tmpzip2
                        # —————————————— استخراج از کپی محلی ——————————————
                        try:
                            if hasattr(self.db, "close"):
                                self.db.close()
                            else:
                                try:
                                    self.db.c.commit()
                                except Exception:
                                    pass
                                try:
                                    self.db.c.close()
                                except Exception:
                                    pass
                        except Exception:
                            pass
                        try:
                            if getattr(self, "shop", None) is not None:
                                if hasattr(self.shop, "close"):
                                    self.shop.close()
                                else:
                                    try:
                                        self.shop.c.commit()
                                    except Exception:
                                        pass
                                    try:
                                        self.shop.c.close()
                                    except Exception:
                                        pass
                        except Exception:
                            pass
                        for suffix in ("-wal", "-shm", "-journal"):
                            for base in (DB_FILE, SHOP_DB):
                                try:
                                    p = base + suffix
                                    if os.path.exists(p):
                                        os.remove(p)
                                except Exception:
                                    pass
                        try:
                            with zipfile.ZipFile(zip_path, "r") as z:
                                names = z.namelist()
                                for arc in names:
                                    arc_norm = arc.replace("\\", "/")
                                    if arc_norm.startswith("/") or ".." in arc_norm.split("/"):
                                        continue
                                    bn = os.path.basename(arc_norm)
                                    if arc_norm.startswith("clients/"):
                                        dest = os.path.join(BASE_DIR, arc_norm)
                                    elif bn in ("manager.db", "shop.db", "manager_config.json", "manager_bot.string", "jafj_ai.json", ".jafj_deploy_id"):
                                        dest = os.path.join(BASE_DIR, bn)
                                    elif "/" in arc_norm and arc_norm.startswith("clients"):
                                        dest = os.path.join(BASE_DIR, arc_norm)
                                    else:
                                        continue
                                    try:
                                        _extract_zip_member_streaming(z, arc, dest)
                                    except Exception:
                                        continue
                        except Exception as e:
                            try:
                                self.db = DB()
                                self.sup.db = self.db
                            except Exception:
                                pass
                            try:
                                self.shop = Shop()
                            except Exception:
                                pass
                            return False, f"خطا در استخراج محلی: {type(e).__name__}: {e}"
                        try:
                            self.db = DB()
                            self.sup.db = self.db
                            self.shop = Shop()
                        except Exception as e:
                            return False, f"خطا در بازسازی دیتابیس: {e}"
                        try:
                            cnt2 = self.db.x("SELECT COUNT(*) c FROM clients", (), "one")
                            n2 = cnt2["c"] if cnt2 else 0
                        except Exception:
                            n2 = -1
                        regen = 0
                        try:
                            for cc in self.db.runnable():
                                _uid = cc["uid"]
                                _folder = self.sup.folder(_uid)
                                _sess_path = os.path.join(_folder, "jafj.session")
                                if not os.path.exists(_sess_path) and cc.get("session"):
                                    try:
                                        _plan = self.effective_plan(_uid)
                                    except Exception:
                                        _plan = None
                                    _mx = 1
                                    try:
                                        if _plan:
                                            _mx = max(1, int(_plan.get("max_accounts", 1) or 1))
                                    except Exception:
                                        pass
                                    self.sup.prepare(_uid, cc["session"], cc.get("phone") or "", _mx, _plan)
                                    regen += 1
                        except Exception:
                            pass
                        try:
                            if zip_path and zip_path.startswith(tempfile.gettempdir()) and os.path.exists(zip_path):
                                os.remove(zip_path)
                        except Exception:
                            pass
                        try:
                            self._save_backup_fp(self._backup_fingerprint())
                        except Exception:
                            pass
                        # تنظیمات از دیسکِ بازیابی‌شده تازه شود (مثل مسیر تلگرام)
                        try:
                            self._reload_cfg_from_disk()
                        except Exception as e:
                            print(f"  ⚠️ تازه‌سازی تنظیمات بعد از بازیابی محلی: "
                                  f"{type(e).__name__}", flush=True)
                        if cand == admin_up:
                            # یک‌بار مصرف: وگرنه بوت بعدی یک فایل قدیمی را به جای پشتیبانِ تازه می‌گذارد
                            try:
                                os.remove(admin_up)
                            except Exception:
                                pass
                            # سرویس‌هایی که «باید روشن باشند» را خودکار برگردان
                            want = self._resume_after_restore("بازیابی از فایل")
                            return True, (f"بازیابی از فایلی که فرستادی: {n2} مشتری"
                                          + (f" + {regen} سشن" if regen else "")
                                          + (f" · {want} سرویس در حال روشن شدن" if want else ""))
                        want = self._resume_after_restore("بازیابی از دیسک")
                        return True, (f"بازیابی از دیسک محلی: {n2} مشتری"
                                      + (f" + {regen} سشن" if regen else "")
                                      + (f" · {want} سرویس در حال روشن شدن" if want else ""))
                    except Exception as e:
                        print(f"  ⚠️ restore local {cand}: {e}", flush=True)
                        continue
            if prefer_admin:
                return False, ("فایلی که فرستادی بازیابی نشد (خراب یا ناقص است). "
                               "دوباره همان zip پشتیبان را بفرست.")
            return False, "پشتیبانی پیدا نشد (نه در تلگرام نه روی دیسک)"
        tmpzip = os.path.join(tempfile.gettempdir(), f"jafj_restore_{int(time.time())}_{os.getpid()}.zip")
        try:
            downloaded = None
            try:
                downloaded = await self.bot.download_media(last, file=tmpzip)
            except TypeError:
                try:
                    downloaded = await self.bot.download_media(last)
                    if downloaded and str(downloaded) != tmpzip and os.path.isfile(str(downloaded)):
                        try:
                            shutil.copy2(str(downloaded), tmpzip)
                        except Exception:
                            tmpzip = str(downloaded)
                except Exception as e:
                    return False, f"دانلود نشد: {type(e).__name__}: {e}"
            except AttributeError:
                try:
                    dl = getattr(last, "download_media", None)
                    if dl is None:
                        return False, "دانلود پشتیبانی نمی‌شود"
                    downloaded = await dl(file=tmpzip)
                except Exception as e:
                    return False, f"دانلود نشد: {type(e).__name__}: {e}"
            except Exception as e:
                return False, f"دانلود نشد: {type(e).__name__}: {e}"
            zip_path = None
            try:
                if downloaded and isinstance(downloaded, str) and os.path.isfile(downloaded):
                    zip_path = downloaded
                elif os.path.isfile(tmpzip):
                    zip_path = tmpzip
                else:
                    return False, "فایل پشتیبان دانلود نشد"
            except Exception:
                if os.path.isfile(tmpzip):
                    zip_path = tmpzip
                else:
                    return False, "فایل پشتیبان دانلود نشد"
            # ── سلف‌های در حال اجرا را ببند ──
            # اگر فایلِ سشنِ یک پروسهٔ زنده را زیر پایش عوض کنیم، یا سشن
            # نیمه‌کاره می‌شود یا دو نسخه هم‌زمان روی یک کلید می‌روند؛ هر دو
            # یعنی «سشن باطل» و بعدش کدِ ورود برای مشتری. پس اول می‌بندیم.
            try:
                running = [u for u in list(self.sup.procs)
                           if self.sup.is_running(u)]
                if running:
                    print(f"  ⏹ بستنِ {len(running)} سرویس پیش از بازیابی…",
                          flush=True)
                self.sup.shutdown()
            except Exception as e:
                print(f"  ⚠️ بستنِ سرویس‌ها قبل از بازیابی: "
                      f"{type(e).__name__}", flush=True)
            # ── بستن اتصال‌ها قبل از نوشتن (وگرنه SQLite خالی را برمی‌گرداند) ──
            try:
                if hasattr(self.db, "close"):
                    self.db.close()
                else:
                    try:
                        self.db.c.commit()
                    except Exception:
                        pass
                    try:
                        self.db.c.close()
                    except Exception:
                        pass
            except Exception:
                pass
            try:
                if getattr(self, "shop", None) is not None:
                    if hasattr(self.shop, "close"):
                        self.shop.close()
                    else:
                        try:
                            self.shop.c.commit()
                        except Exception:
                            pass
                        try:
                            self.shop.c.close()
                        except Exception:
                            pass
            except Exception:
                pass
            for suffix in ("-wal", "-shm", "-journal"):
                for base in (DB_FILE, SHOP_DB):
                    try:
                        p = base + suffix
                        if os.path.exists(p):
                            os.remove(p)
                    except Exception:
                        pass
            # ── استخراج ──
            try:
                with zipfile.ZipFile(zip_path, "r") as z:
                    names = z.namelist()
                    # ایمن‌سازی: هیچ arc نباید از BASE_DIR بیرون برود
                    for arc in names:
                        # نرمال‌سازی و جلوگیری از zip-slip
                        try:
                            # نگهداری فقط مسیرهای نسبی ایمن
                            arc_norm = arc.replace("\\", "/")
                            # اگر با / شروع شد یا شامل .. بود، رد کن
                            if arc_norm.startswith("/") or ".." in arc_norm.split("/"):
                                print(f"  ⚠️ فایل ناامن در پشتیبان: {arc} — رد شد", flush=True)
                                continue
                        except Exception:
                            arc_norm = arc
                        # فایل‌های تکی قدیمی (بدون پوشه) یا clients/... یا jafj_ai و...
                        # سه دسته را پشتیبانی می‌کنیم:
                        # 1) نام ساده: manager.db ...
                        # 2) clients/<uid>/...
                        # 3) jafj_ai.json / .jafj_deploy_id
                        bn = os.path.basename(arc_norm)
                        # تعیین مقصد
                        if arc_norm.startswith("clients/"):
                            dest = os.path.join(BASE_DIR, arc_norm)
                        elif bn in ("manager.db", "shop.db", "manager_config.json", "manager_bot.string", "jafj_ai.json", ".jafj_deploy_id"):
                            # پشتیبان قدیمی فقط basename دارد؛ پشتیبان جدید هم basename برای اینها
                            dest = os.path.join(BASE_DIR, bn)
                        else:
                            # فایل ناشناخته داخل clients/... ممکن است با نام متفاوت باشد؛ اگر مسیر clients دارد بپذیر
                            if "/" in arc_norm:
                                # هرچیزی که زیر clients است حتی اگر قدیمی باشد
                                if arc_norm.startswith("clients"):
                                    dest = os.path.join(BASE_DIR, arc_norm)
                                else:
                                    print(f"  ⚠️ فایل ناشناخته در پشتیبان: {arc} — رد شد", flush=True)
                                    continue
                            else:
                                print(f"  ⚠️ فایل ناشناخته در پشتیبان: {arc} — رد شد", flush=True)
                                continue
                        try:
                            # جریانِ ZIP را مستقیم به دیسک می‌ریزیم؛ z.read عضوِ
                            # کامل را در RAM می‌ساخت و روی پلن‌های 256MB باعث OOM می‌شد.
                            size = _extract_zip_member_streaming(z, arc, dest)
                            print(f"  ♻️ بازیابی {arc_norm} ({size} بایت)", flush=True)
                        except Exception as e:
                            print(f"  ⚠️ استخراج/نوشتن {bn}: {e}", flush=True)
            except Exception as e:
                try:
                    self.db = DB()
                    self.sup.db = self.db
                except Exception:
                    pass
                try:
                    self.shop = Shop()
                except Exception:
                    pass
                return False, f"خطا در استخراج: {type(e).__name__}: {e}"
            # ── بازسازی DB و Shop ──
            try:
                self.db = DB()
                self.sup.db = self.db
                self.shop = Shop()
            except Exception as e:
                return False, f"خطا در بازسازی دیتابیس: {e}"
            try:
                cnt2 = self.db.x("SELECT COUNT(*) c FROM clients", (), "one")
                n2 = cnt2["c"] if cnt2 else 0
            except Exception:
                n2 = -1
            # بازسازی سشن‌های گمشده تا بوت بعد از Redeploy کار کند
            regen = 0
            try:
                for cc in self.db.runnable():
                    _uid = cc["uid"]
                    _folder = self.sup.folder(_uid)
                    _sess_path = os.path.join(_folder, "jafj.session")
                    if not os.path.exists(_sess_path) and cc.get("session"):
                        try:
                            try:
                                _plan = self.effective_plan(_uid)
                            except Exception:
                                _plan = None
                            _mx = 1
                            try:
                                if _plan:
                                    _mx = max(1, int(_plan.get("max_accounts", 1) or 1))
                            except Exception:
                                pass
                            self.sup.prepare(_uid, cc["session"], cc.get("phone") or "", _mx, _plan)
                            regen += 1
                        except Exception as e:
                            print(f"  ⚠️ بازسازی سشن {_uid}: {e}", flush=True)
            except Exception as e:
                print(f"  ⚠️ بازسازی سشن‌ها: {e}", flush=True)
            try:
                if zip_path and zip_path.startswith(tempfile.gettempdir()) and os.path.exists(zip_path):
                    os.remove(zip_path)
            except Exception:
                pass
            try:
                self._save_backup_fp(self._backup_fingerprint())
            except Exception:
                pass
            # ── تنظیمات را از دیسکِ بازیابی‌شده تازه کن ──
            # وگرنه اولین cfg.save() بعد از بوت، manager_config.jsonِ
            # بازیابی‌شده را با پیش‌فرض‌های حافظه بازنویسی می‌کند
            # (باگِ اصلیِ «بعد از دیپلوی همه‌ش می‌پره»).
            try:
                self._reload_cfg_from_disk()
            except Exception as e:
                print(f"  ⚠️ تازه‌سازی تنظیمات بعد از بازیابی: {type(e).__name__}", flush=True)
            want = self._resume_after_restore("بازیابی از تلگرام")
            return True, (f"بازیابی شد: {n2} مشتری"
                          + (f" + {regen} سشن بازسازی" if regen else "")
                          + (f" · {want} سرویس در حال روشن شدن" if want else ""))
        except Exception as e:
            try:
                try:
                    self.db.x("SELECT 1", (), "one")
                except Exception:
                    try:
                        self.db = DB()
                        self.sup.db = self.db
                    except Exception:
                        pass
            except Exception:
                pass
            try:
                if getattr(self, "shop", None) is not None:
                    try:
                        self.shop.x("SELECT 1", (), "one")
                    except Exception:
                        try:
                            self.shop = Shop()
                        except Exception:
                            pass
                else:
                    try:
                        self.shop = Shop()
                    except Exception:
                        pass
            except Exception:
                pass
            import traceback
            traceback.print_exc()
            return False, f"خطا: {type(e).__name__}: {e}"

    async def startup_restore(self, notify=True, retries=1, wait_sec=20):
        """بازیابیِ موقعِ بوت: یک تلاشِ دوباره + پیامِ وضعیت در پیوی مدیر.

        چرا تلاشِ دوباره؟ موقع بوتِ بعد از دیپلوی، تلگرام/شبکه ممکن است چند
        ثانیه آماده نباشد؛ یک بار شکست نباید یعنی «همهٔ داده‌ها رفت».
        چرا پیامِ وضعیت؟ تا مدیر بداند بازیابی شد یا نه — سکوت همان چیزی است
        که باعث می‌شود فکر کند «همه‌ش می‌پره».

        اگر دیتابیس از قبل پر باشد هیچ کاری نمی‌کند (و پیامی هم نمی‌فرستد تا
        بعد از هر ری‌استارتِ عادی پیوی مدیر شلوغ نشود). خروجی: (موفق, پیام)."""
        if not backup_target_raw():
            return False, "BACKUP_CHAT تنظیم نشده"

        def _count():
            try:
                r = self.db.x("SELECT COUNT(*) c FROM clients", (), "one")
                return r["c"] if r else 0
            except Exception:
                return 0

        n0 = _count()
        if n0 != 0:
            print(f"  ℹ️ {n0} مشتری در دیتابیس — نیازی به بازیابی نیست", flush=True)
            return True, f"{n0} مشتری در دیتابیس — نیازی به بازیابی نبود"

        tries = max(1, int(retries) + 1)
        ok, msg = False, "بازیابی انجام نشد"
        print("  🔍 دیتابیس خالی است — جستجوی پشتیبان تلگرام…", flush=True)
        for i in range(tries):
            try:
                ok, msg = await self.restore_from_backup(force=False)
            except Exception as e:
                ok, msg = False, f"{type(e).__name__}: {e}"
            self._restore_tries = i + 1
            print(f"  {'✅' if ok else 'ℹ️'} بازیابی (تلاش {i + 1}/{tries}): {msg}",
                  flush=True)
            if ok:
                break
            if i + 1 < tries:
                # یک مکث کوتاه و تلاشِ دوباره
                try:
                    await asyncio.sleep(max(0, int(wait_sec)))
                except Exception:
                    pass
        # حتی اگر بازیابیِ تلگرامی نشد، تنظیماتِ روی دیسک (کپیِ محلی یا دستی)
        # باید در حافظه تازه شود تا اولین cfg.save() پاکش نکند.
        try:
            self._reload_cfg_from_disk()
        except Exception:
            pass
        n2 = _count()
        if notify:
            if ok:
                status = ("✅ <b>بازیابیِ اطلاعات بعد از دیپلوی انجام شد</b>\n\n"
                          f"{msg}\n👥 {n2} مشتری در دیتابیس\n"
                          "⚙️ تنظیمات هم از همان پشتیبان تازه شد — چیزی نپَریده.\n"
                          "<i>بازیابیِ دستی: <code>.restore</code></i>")
            else:
                status = ("⚠️ <b>بازیابیِ اطلاعات ناموفق بود</b>\n\n"
                          f"{msg}\n\nدیتابیس خالی است و پشتیبانی پیدا نشد.\n\n"
                          "<b>سه راهِ قطعی (هر کدام راحت‌تر بود):</b>\n"
                          "۱) روی همان <b>پیامِ پشتیبان</b> در تلگرام <b>ریپلای</b> کن و "
                          "بنویس <code>.restore</code>\n"
                          "۲) آیدیِ همان پیام را بفرست: "
                          "<code>.restore 12345</code> (یا لینکش: "
                          "<code>.restore https://t.me/c/.../12345</code>)\n"
                          "۳) همان zipِ پشتیبان را در این چت بفرست و بعد "
                          "<code>.restore</code> بزن.\n"
                          f"• چتِ پشتیبان: <code>{backup_target_raw()}</code>\n"
                          "• گرفتنِ دستی: <code>.backup</code>\n\n"
                          "<b>چرا پیدا نشد؟</b> رباتِ تلگرام اجازهٔ گشتن در تاریخچهٔ "
                          "چت را ندارد؛ اگر دیسک هم پاک شود، آدرسِ پیام از دست "
                          "می‌رود. برای اینکه دیگر تکرار نشود، در رندر یک "
                          "<b>Disk</b> روی <code>/data</code> با "
                          "<code>DATA_DIR=/data</code> بگذار یا "
                          "<code>DATA_GITHUB_TOKEN</code> را فعال کن.")
            sent_any = False
            for a in (self.cfg.get("admin_ids") or []):
                try:
                    if await self.say(a, status, key="startup_restore"):
                        sent_any = True
                except Exception as e:
                    print(f"  ⚠️ پیامِ وضعیتِ بازیابی: {type(e).__name__}", flush=True)
            if not sent_any:
                print("  ℹ️ پیامِ وضعیتِ بازیابی به پیوی مدیر نرسید "
                      "(مدیری ثبت نشده)", flush=True)
        return ok, msg


    def live_diag_lines(self):
        """«ربات واقعاً جواب می‌دهد؟» — سنِ پینگ، ضربان و آخرین پیام.

        /diag قبلاً فقط می‌گفت پروسه بالا است و رم چقدر آزاد است؛ حالا اگر
        اتصال مرده باشد (همان «آفلاین»ی که پنل نشان نمی‌دهد) همین‌جا معلوم
        است، نه با آزمونِ «یک پیام بفرست ببین جواب می‌دهد یا نه».
        """
        out = []
        try:
            s = live_snapshot()
        except Exception:
            return out

        def _age(a):
            if a is None:
                return "—"
            if a < 90:
                return f"{_fa_digits(int(a))} ثانیه پیش"
            return f"{_fa_digits(int(a // 60))} دقیقه پیش"

        tail = ""
        if s.get("fails"):
            err = self._esc(str(s.get("last_error") or "")[:60])
            tail = (f" · ⚠️ {_fa_digits(s['fails'])} پینگِ ناموفقِ پیاپی"
                    + (f" ({err})" if err else ""))
        out.append(f"💓 ضربانِ ربات: پینگ {_age(s.get('ping_age'))} · "
                   f"حلقه {_age(s.get('loop_age'))} · "
                   f"آخرین پیام {_age(s.get('update_age'))}{tail}")
        try:
            code, state = livez_verdict(s)
        except Exception:
            code, state = 200, "ok"
        if code != 200:
            out.append(f"🩺 وضعیت: <b>{state}</b> — نگهبان در حالِ ری‌استارتِ "
                       "ربات است (سلامتِ ظاهری کافی نیست)")
        return out

    def _alive_notes(self, uid):
        """نکته‌های مهم درباره‌ی سلفی که «روشن» است ولی ممکن است کار نکند.

        دو حالتِ واقعی: (۱) حلقه‌ای مرده و خودش را ری‌استارت کرده — یعنی
        مدتی هیچ کاری نکرده؛ (۲) ضربانِ jafj_status.json پیر شده — یعنی
        پروسه هست ولی حلقه‌ی اصلی گیر کرده. هر دو قبلاً بی‌صدا بودند.
        """
        notes = []
        try:
            proc = self.sup.procs.get(uid)
            if (isinstance(proc, _ShardProc) and proc.daemon.alive()
                    and proc.returncode is None
                    and not proc.daemon.recently_confirmed_alive(uid)):
                notes.append("⚠️ وضعیت شارد موقتاً نامشخص است؛ پاسخ تازه نرسیده")
        except Exception:
            pass
        try:
            stt = self.sup.read_status(uid) or {}
        except Exception:
            stt = {}
        try:
            age = float(stt.get("age") or 0)
        except Exception:
            age = 0.0
        if age > 300:
            notes.append(f"⚠️ ضربان {_fa_digits(int(age // 60))} دقیقه "
                         "است تازه نشده")
        # سه دلیلِ بی‌صدای «پنل جواب می‌دهد ولی هیچ کاری انجام نمی‌شود»:
        # pause، تبادلِ خاموش، و نبودِ کانالِ خودت (قاعده‌ی «اول کانال»).
        if stt.get("paused"):
            notes.append("⏸ در حالتِ Pause است — هیچ کاری اجرا نمی‌شود")
        ex = stt.get("exchange") or {}
        if isinstance(ex, dict) and ex.get("on") is False:
            notes.append("🔁 تبادل خاموش است («تبادل روشن» را بزن)")
        chans = stt.get("channels") or {}
        if isinstance(chans, dict) and chans:
            if not any(str(v or "").strip() for v in chans.values()):
                notes.append("📣 کانالِ خودت ثبت نشده — بدونِ کانال "
                             "جوین/تبادل اجرا نمی‌شود")
        loops = stt.get("loops") or {}
        if isinstance(loops, dict):
            restarts = 0
            worst = None
            for name, rec in loops.items():
                if not isinstance(rec, dict):
                    continue
                n = int(rec.get("restarts") or 0)
                errs = int(rec.get("errors") or 0)
                restarts += n
                if errs and (worst is None or errs > worst[1]):
                    worst = (name, errs, str(rec.get("last_error") or ""))
            if restarts:
                notes.append(f"♻️ {_fa_digits(restarts)} ری‌استارتِ حلقه")
            if worst:
                label = LOOP_LABELS_FA.get(worst[0], worst[0])
                notes.append(f"آخرین خطای «{self._esc(label)}»: "
                             f"{self._esc(worst[2])[:70] or '—'}")
        try:
            mem = stt.get("mem") or {}
            fr = mem.get("free_mb")
            # فقط وقتی کم است — وگرنه هر سلفِ سالم هم یک خطِ بی‌مصرف می‌گیرد.
            if fr is not None and float(fr) < 100:
                notes.append(f"🧠 در زمانِ آخرین ضربان {_fa_digits(fr)}MB آزاد")
        except Exception:
            pass
        return notes

    def selfbot_diag_lines(self, limit=3):
        """خطوطِ /diag برای سلف‌هایی که روشن نشده‌اند: علت + آخرین خطِ لاگ.

        گزارشِ کاربر «مدیر بالا می‌آید ولی پنلِ سلف نمی‌آید» تا امروز فقط با
        گشتنِ دستیِ data/clients/<uid>/run.log جواب می‌گرفت. حالا همان جواب
        داخلِ /diag هست.
        """
        out = []
        try:
            rows = self.db.wanted()
        except Exception:
            rows = []
        shown = 0
        for c in rows:
            uid = c.get("uid")
            if uid is None or shown >= limit:
                continue
            try:
                alive = self.sup.is_running(uid)
            except Exception:
                alive = False
            detail = ""
            try:
                detail = self.sup.last_detail.get(uid) or ""
            except Exception:
                detail = ""
            nm = c.get("name") or str(uid)
            if alive:
                # «روشن» به‌تنهایی دروغِ راحت‌طلبی است: پروسه می‌تواند بالا
                # باشد و هیچ حلقه‌ای کار نکند. این‌جا ضربانِ وضعیت و
                # ری‌استارت‌شدنِ حلقه‌ها را هم می‌گوییم.
                notes = self._alive_notes(uid)
                if not detail and not notes:
                    continue
                line = (f"  • {self._esc(nm)[:24]} <code>{uid}</code>: "
                        "روشن ✅")
                if notes:
                    line += "\n    " + " · ".join(notes)
                out.append(line)
                shown += 1
                continue
            out.append(f"  • {self._esc(nm)[:24]} <code>{uid}</code>: "
                       f"خاموش — {self._esc(detail or 'علت ثبت نشده')[:90]}")
            try:
                tail = self.sup.tail(uid, 8)
            except Exception:
                tail = ""
            firsts = [ln.strip() for ln in (tail or "").splitlines()
                      if ln.strip() and not ln.strip().startswith(
                          ("File ", "~", "=====", "python=", "self="))]
            if firsts:
                out.append(f"    <pre>{_h(firsts[-1], 160)}</pre>")
            shown += 1
        return out

    def mem_diag_lines(self, free=None):
        """«حافظه» با اعدادِ واقعی — تا «کم‌آوردنِ رم» قابلِ اثبات باشد.

        /diag قبلاً فقط یک عددِ آزاد نشان می‌داد. اگر سقفِ کانتینر پایین‌تر
        از حافظه‌ی میزبان باشد (که در اکثر هاست‌های کوچک هست)، آن عدد
        گمراه‌کننده است: «۴۰۰ مگابایت آزاد» می‌بینیم و همان لحظه OOM
        پروسه را می‌کشد. حالا سقف/مصرفِ cgroup + تصمیمِ نگهبان + مصرفِ
        واقعیِ سلف‌ها هم می‌آید.
        """
        out = []
        if free is None:
            try:
                free = mem_available_mb()
            except Exception:
                free = None
        try:
            limit, used = cgroup_mem_mb()
        except Exception:
            limit, used = None, None
        line = (f"🧠 حافظه‌ی آزاد: {free}MB" if free is not None
                else "🧠 حافظه: ؟")
        if limit:
            line += f" از {int(limit)}MB سقفِ کانتینر"
            if used is not None:
                line += f" (مصرف: {int(used)}MB)"
        out.append(line)
        try:
            limit_mb = ram_gate_mb()
            ok, fr, lim = ram_gate_check()
        except Exception:
            ok, fr, lim = True, free, 0
        if lim and lim > 0:
            verdict = ("✅ روشن‌کردنِ سلفِ تازه مجاز است" if ok
                       else "⛔ سلفِ تازه بالا نمی‌آید — حافظه کم است")
            out.append(f"🧪 نگهبانِ حافظه: حدِ {int(lim)}MB → {verdict}")
            if not ok:
                out.append("  <i>«سلف‌های روشن‌نشده» پایین‌تر همین را با "
                           "عددِ دقیقِ کمبود می‌گویند؛ یک سلف خاموش کن یا "
                           "JAFJ_MIN_FREE_MB را کم کن.</i>")
        else:
            out.append("🧪 نگهبانِ حافظه: خاموش (JAFJ_MIN_FREE_MB=0)")
        # حالتِ اجرا + ظرفیت: جوابِ «چند سلفِ دیگر جا می‌شود؟» با همین
        # حافظه. اگر shard انتخاب شود، هر اکانت ~۴MB است نه ~۶۲MB — همان تفاوتی که
        # «رم کم می‌آورد» را حل می‌کند.
        try:
            mode = spawn_mode()
            cap, per, _fr = capacity_estimate(free, mode)
        except Exception:
            mode, cap, per = "", None, None
        if mode:
            line = f"🧵 حالتِ اجرا: {mode}"
            if per:
                line += f" (~{_fa_digits(int(per))}MB هر اکانت)"
            if cap is not None:
                line += (" · با حافظه‌ی فعلی "
                         f"{_fa_digits(int(cap))} اکانتِ دیگر جا می‌شود")
            out.append(line)

        # مصرفِ سلف‌ها: روی pidِ یکتا حساب می‌شود، نه روی اکانت — در حالتِ
        # شارد چند اکانت یک پروسه‌اند و جمعِ «سهمِ هر اکانت» عددِ غلط می‌داد.
        tot, seen_pid, worst, n_acc = 0.0, set(), (None, 0.0), 0
        try:
            for uid, p in list(getattr(self.sup, "procs", {}).items()):
                if p is None or p.poll() is not None:
                    continue
                n_acc += 1
                pid = getattr(p, "pid", None)
                if pid in seen_pid:
                    continue
                seen_pid.add(pid)
                mb = proc_pss_mb(pid)
                if mb is None:
                    mb = proc_rss_mb(pid)
                if not mb:
                    continue
                tot += mb
                if mb > worst[1]:
                    worst = (uid, mb)
        except Exception:
            pass
        if n_acc:
            line = (f"👶 سلف‌های روشن: {_fa_digits(n_acc)} اکانت در "
                    f"{_fa_digits(len(seen_pid))} پروسه · "
                    f"{_fa_digits(int(round(tot)))}MB")
            if worst[0] is not None:
                line += (f" · سنگین‌ترین <code>{worst[0]}</code> "
                         f"{_fa_digits(int(worst[1]))}MB")
            out.append(line)
        return out

    def diag_text(self):
        """🔍 عیب‌یابی: چرا داده می‌پرد / چرا کرش می‌کند؟ (همه در یک نگاه)"""
        L = self.LINE
        try:
            n = self.db.x("SELECT COUNT(*) c FROM clients", (), "one")["c"]
        except Exception:
            n = -1
        try:
            n_want = len(self.db.wanted())
        except Exception:
            n_want = -1
        try:
            n_login = int(self.db.x(
                "SELECT COUNT(*) c FROM clients WHERE need_login<>0",
                (), "one")["c"] or 0)
        except Exception:
            n_login = 0
        data_dir = os.path.abspath(BASE_DIR)
        writable = "✅" if os.access(data_dir, os.W_OK) else "❌ فقط‌خواندنی"
        token = bool((os.environ.get("DATA_GITHUB_TOKEN") or "").strip())
        try:
            up = int(time.time() - self.boot_at)
        except Exception:
            up = 0
        free = mem_available_mb()
        dbsz = ""
        try:
            if os.path.isfile(DB_FILE):
                dbsz = f"{os.path.getsize(DB_FILE) // 1024}KB"
        except Exception:
            dbsz = ""
        t = [f"🔍 <b>عیب‌یابی</b>\n{L}",
             f"📂 داده: <code>{data_dir}</code> ({writable})",
             f"🧊 بوت سرد: {'بله — دیسک پاک شده بود' if COLD_START else 'نه'}",
             f"👥 مشتری: {_fa_digits(n)} · باید روشن: {_fa_digits(n_want)}"
             f" · روشن: {_fa_digits(self.sup.running_count())}",
             f"🗄 دیتابیس: {dbsz or '—'}",
             f"☁️ نسخه‌ی بیرونی (گیت‌هاب): "
             f"{'✅ فعال' if token else '❌ تنظیم نشده — کرش = پاک‌شدنِ داده'}",
             (f"🔑 نیاز به لاگین: {_fa_digits(n_login)}"
              f" (کد نمی‌رود؛ /needlogin)" if n_login else "🔑 نیاز به لاگین: ۰"),
             *self.mem_diag_lines(free),
             *self.live_diag_lines(),
             f"⏱ بالا: {up // 60} دقیقه"]
        try:
            sb_lines = self.selfbot_diag_lines()
        except Exception:
            sb_lines = []
        if sb_lines:
            t.append("")
            t.append("🤖 <b>سلف‌های روشن‌نشده</b> (علت + آخرین خطِ لاگ)")
            t += sb_lines
            t.append("  <i>لاگِ کامل: «⚙️ سرویس من» → «📜 گزارش»</i>")
        ex = last_exit_info()
        if ex:
            t.append(f"💥 آخرین خروج: کد {ex.get('code')} بعد از "
                     f"{int(ex.get('uptime') or 0)}s")
        blocks = crash_blocks()
        if blocks:
            t.append("")
            t.append(f"🧯 <b>کرش‌ها ({_fa_digits(len(blocks))})</b>")
            for ts, reason, body in blocks[-3:]:
                when = f"{local_dt(ts):%m-%d %H:%M}" if ts else "?"
                first = ""
                for ln in (body or "").splitlines():
                    ln = ln.strip()
                    if ln and not ln.startswith("File "):
                        first = ln[:120]
                        break
                t.append(f"  • {when} [{reason}] {first or '—'}")
        else:
            t.append("")
            t.append("🧯 کرشی ثبت نشده ✅")
        t += [L,
              "💡 <b>اگر داده می‌پرد:</b> دیسکِ ماندگار روی <code>/data</code> با "
              "<code>DATA_DIR=/data</code> بگذار، یا "
              "<code>DATA_GITHUB_TOKEN</code> را تنظیم کن. بدون یکی از این دو، "
              "هر کرش/دیپلوی دادهٔ دیسک را پاک می‌کند.",
              "",
              "<code>.backup</code> پشتیبان فوری · <code>.restore</code> بازیابی "
              "· <code>/onall</code> روشن‌کردنِ همه"]
        return "\n".join(t)

    # ═══════════════════════════════════════════════
    #  اجرا
    # ═══════════════════════════════════════════════
    def _startup_notices(self):
        """هشدارهای بوت: دیسکِ پاک‌شده، کرشِ قبلی، نبودِ نسخه‌ی بیرونی.

        همه‌ی این‌ها همان سؤالِ «چرا اطلاعات می‌پرد؟» را در همان لحظه جواب
        می‌دهند، به‌جای اینکه مدیر بعد از چند روز خودش حدس بزند.
        """
        out = []
        try:
            n = self.db.x("SELECT COUNT(*) c FROM clients", (), "one")["c"]
        except Exception:
            n = 0
        token = bool((os.environ.get("DATA_GITHUB_TOKEN") or "").strip())
        if COLD_START:
            out.append("🧊 بوت سرد: پوشه‌ی داده از قبل دیتابیس نداشت "
                       "(دیسک پاک شده یا ماندگار نیست).")
        # هشدارِ مهم مستقل از بوتِ سرد است: بدونِ نسخه‌ی بیرونی، هر کرشی که
        # دیسک را نبرد هم، داده‌ی چند دقیقه‌ی آخر را می‌برد.
        if not token:
            out.append("⚠️ <b>DATA_GITHUB_TOKEN تنظیم نیست</b> — تنها نسخه‌ی "
                       "بیرونی، پیامِ پشتیبان در تلگرام است. بدون Diskِ ماندگار "
                       "روی <code>/data</code>، هر کرش/دیپلوی داده‌ی دیسک را "
                       "می‌برد. یکی از این دو را فعال کن.")
        ex = last_exit_info()
        if ex and ex.get("code"):
            up = int(ex.get("uptime") or 0)
            out.append(f"💥 آخرین خروج با کد {ex.get('code')} بعد از "
                       f"{up}s ({ex.get('build') or '?'})")
        # کدام کد بالا آمده؟ تنها سؤالِ بعد از هر مرج: «دیپلوی شد یا نه؟»
        out.append(f"🧬 نسخه‌ی در حالِ اجرا: <code>{BUILD_VERSION}</code> · "
                   f"کامیت <code>{GIT_COMMIT}</code> · کد "
                   f"<code>{CODE_ID}</code> — برای دیدنِ جزئیات و راهنمای "
                   "دیپلوی: «🛠 پنل مدیر → 🧬 نسخه‌ی کد» یا <code>/version</code>")
        if CODE_IS_STALE:
            out.append("⚠️ <b>کد از پوشه‌ی ایمیج اجرا نمی‌شود</b> "
                       f"(<code>{self._esc(MANAGER_PATH)}</code>) — یعنی دیپلویِ "
                       "تازه احتمالاً بی‌اثر است. دیسک باید روی <code>/data</code> "
                       "باشد، نه <code>/app</code> یا <code>/opt/jafj</code>.")
        # بخش‌های آموزش پریده؟ (کانفیگِ قدیمی جایِ تازه را گرفته)
        try:
            lost = cfg_lost_sections(extra=True)
            if lost:
                _fn, _d, _ids = lost
                out.append(f"🧩 <b>{_fa_digits(len(_ids))} بخشِ آموزش در کانفیگِ "
                           "فعلی نیست</b> ولی در تاریخچه‌ی کانفیگ هست — احتمالاً "
                           "نسخه‌ی قدیمیِ manager_config.json برگشته. از "
                           "«🛠 پنل مدیر → 🧩 بخش‌های آموزش → 🕘 بازیابی "
                           "بخش‌ها» با یک دکمه برگردانشان کن.")
        except Exception:
            pass
        # محتوای بخش‌ها خالی شده؟ (بخش هست، ویدیو/متنش نه)
        try:
            poor = cfg_poor_sections()
            if poor:
                names = "، ".join(str(nm)[:24] for _sid, nm, _m, _h in poor[:3])
                out.append(f"📚 <b>محتوای {_fa_digits(len(poor))} بخش خالی شده "
                           f"است</b> ({self._esc(names)}) ولی نسخه‌ی پُرترشان در "
                           "تاریخچه‌ی کانفیگ هست — از «🛠 پنل مدیر → 🧩 بخش‌های "
                           "آموزش → 🕘 بازیابی بخش‌ها → 📚 برگرداندنِ محتوا» "
                           "برگردانشان کن.")
        except Exception:
            pass
        blocks = crash_blocks(within_secs=6 * 3600)
        if blocks:
            last_ts, reason, body = blocks[-1]
            first = ""
            for ln in (body or "").splitlines():
                ln = ln.strip()
                if ln and not ln.startswith("File "):
                    first = ln[:160]
            if not first:
                first = "(بدون جزئیات)"
            out.append(f"🧯 {len(blocks)} کرش در ۶ ساعتِ اخیر — آخری "
                       f"({reason}): {first}")
        return out

    async def run(self):
        try:
            from telethon import TelegramClient, events
        except ImportError:
            print("\n📦 Telethon نصب نیست؛ نصب خودکار را شروع می‌کنم…", flush=True)
            try:
                subprocess.check_call([sys.executable, "-m", "pip", "install", "telethon"])
                from telethon import TelegramClient, events
            except Exception as e:
                print(f"\n❌ نصب Telethon انجام نشد: {type(e).__name__}: {e}")
                print("دستی اجرا کن: pip install telethon\n")
                return 1

        c = self.cfg
        missing = [k for k in ("bot_token", "api_id", "api_hash") if not c[k]]
        if missing:
            print(f"\n{'='*54}\n  تنظیمات ناقص است\n{'='*54}")
            print(f"  فایل: {os.path.abspath(CONFIG_FILE)}")
            print("  این‌ها خالی‌اند:")
            for k in missing:
                print(f"    ❌ {k}")
            print()
            print("  bot_token   ← از @BotFather")
            print("  api_id/hash ← از my.telegram.org")
            print()
            print("  💡 اگر نسخه‌ی آماده را دانلود کرده‌ای، احتمالاً یک")
            print(f"     {CONFIG_FILE} قدیمی و خالی کنارش مانده.")
            print(f"     پاکش کن و دوباره اجرا کن:")
            print(f"       rm {CONFIG_FILE}")
            print(f"{'='*54}\n")
            self.cfg.save()
            return 1

        global SELFBOT
        SELFBOT = find_selfbot()
        ensure_selfbot_current(SELFBOT)      # اگر ایمیج تازه‌تر است، جایگزین شود
        if not os.path.isfile(SELFBOT):
            print(f"\n⚠️ فایل سلف پیدا نشد: {SELFBOT}")
            print(f"   نسخه مرجع: {SELFBOT_REF}"
                  + (" (سالم است)" if os.path.isfile(SELFBOT_REF) else " (نیست)"))
            print("   فقط 95.py را کنار manager_82.py بگذار. jafj_self لازم نیست.\n")
        else:
            ensure_selfbot_ref(SELFBOT)
            ver = selfbot_version(SELFBOT)
            print(f"  سلف: {SELFBOT}  VERSION={ver or '?'}")
            if "3.0" not in ver:
                print("  ⛔ این 95.py پنل جدید نیست. فایل 95.py همین چت را آپلود کن.")

        # ورود با نشست ذخیره‌شده + تحمل FloodWait (بدون چرخه کرش)
        try:
            await self.login_with_patience(tries=5)
        except Exception as e:
            print(f"\n⛔ ورود ناموفق پس از تلاش‌ها: {type(e).__name__}: {e}")
            print("   توکن/api یا محدودیت FloodWait را چک کن.\n")
            return 1

        # آیدی هر پیامی که این نمونه می‌فرستد را نگه دار تا نمونه‌ی زامبیِ
        # هم‌زمان (نسخه‌ی قدیمیِ بی‌ضربان) را از روی فعالیتش تشخیص بدهیم.
        try:
            bot_id_track = getattr((await self.bot.get_me()), "id", 0) or 0
            _orig_send = self.bot.send_message

            def _track(r):
                try:
                    self._sent_ids.add(getattr(r, "id", 0))
                    if len(self._sent_ids) > 4000:
                        self._sent_ids = set(sorted(self._sent_ids)[-2000:])
                except Exception:
                    pass
                return r

            async def _tracking_send(chat, *a, **k):
                return _track(await _orig_send(chat, *a, **k))
            self.bot.send_message = _tracking_send

            _orig_edit = getattr(self.bot, "edit_message", None)
            if _orig_edit is not None:
                async def _tracking_edit(*a, **k):
                    return _track(await _orig_edit(*a, **k))
                self.bot.edit_message = _tracking_edit
        except Exception:
            bot_id_track = 0

        # فایل نشست قدیمی اگر مانده، پاکش کن (نسخه .string جایگزین شده)
        for junk in ("manager_bot.session", "manager_bot.session-journal"):
            try:
                if os.path.exists(junk):
                    os.remove(junk)
            except Exception:
                pass
        me = await self.bot.get_me()
        print(f"\n{'='*54}\n  ربات مدیر جفج\n{'='*54}")
        print(f"  ربات: @{me.username}")
        if c["admin_ids"]:
            print(f"  مدیر: {c['admin_ids']}")
        else:
            print("  ⚠️  مدیری ثبت نشده")
            print(f"  👉 در تلگرام @{me.username} را باز کن و /start بزن")
            print("     اولین نفر مدیر می‌شود.")
        print(f"  سقف: {c['max_clients']} مشتری")

        # حلقه‌ی جاری را نگه دار: بوتِ پس‌زمینه از یک thread جدا پیام‌ها را
        # با run_coroutine_threadsafe به همین حلقه می‌فرستد.
        try:
            self._loop = asyncio.get_running_loop()
        except Exception:
            self._loop = None

        try:
            self._start_cpu_monitor()
        except Exception as e:
            print(f"  ⚠️ شروع گزارش CPU: {type(e).__name__}", flush=True)

        # ── کرش‌گیری ──
        # از همین‌جا هر مرگِ غیرمنتظره ثبت می‌شود و یک «ذخیره‌ی نجات» می‌زند،
        # تا داده‌ی چند دقیقه‌ی آخر با هیچ کرشی از دست نرود.
        try:
            self._install_crash_hooks()
        except Exception as e:
            print(f"  ⚠️ نصبِ قلاب‌های کرش: {type(e).__name__}", flush=True)
        try:
            self._boot_notice = self._startup_notices()
            for line in self._boot_notice:
                print("  " + line.replace("<b>", "").replace("</b>", ""), flush=True)
        except Exception as e:
            print(f"  ⚠️ گزارشِ وضعیتِ بوت: {type(e).__name__}", flush=True)

        # ── بازیابی خودکار از پشتیبان تلگرام (اگر دیتابیس خالی است) ──
        # مقصد از backup_target_raw() خوانده می‌شود که بدون BACKUP_CHAT هم
        # به «admin» برمی‌گردد، پس بعد از هر دیپلوی/ری‌استارت که دیتابیس
        # پاک شده باشد، بازیابی خودکار انجام می‌شود.
        # startup_restore: بازیابی + یک تلاشِ دوباره + پیامِ وضعیت در پیوی مدیر
        try:
            await self.startup_restore()
        except Exception as e:
            print(f"  ⚠️ بازیابی خودکار: {type(e).__name__}: {e}", flush=True)

        self.boot_at = now()
        # بالا آوردنِ سرویس‌ها در پس‌زمینه: هر سرویس ~۱.۵ ثانیه وقت می‌برد و
        # اگر همگام اجرا شود، ربات بعد از آپدیت دقیقاً وقتی مدیر «روشن کن»
        # می‌زند چند دقیقه جواب نمی‌دهد. قبل از شروع watchdog پرچم را
        # می‌گذاریم تا حتی اگر thread بوت هنوز اجرا نشده، محافظ دور زده نشود.
        self.sup._startup_boot_pending.set()
        threading.Thread(target=self.sup.watchdog, daemon=True).start()
        # «چرا دیروز یهو آفلاین شد؟» — از ضربانِ اجرای قبلی می‌گوییم.
        try:
            _death = last_death_report(BASE_DIR)
            if _death:
                print(f"  {_death}", flush=True)
                self._death_note = _death
        except Exception as e:
            print(f"  ⚠️ گزارشِ مرگِ قبلی: {type(e).__name__}", flush=True)
        write_heartbeat(BASE_DIR, {"stage": "boot"})
        print(f"{'='*54}\n")
        self._spawn_boot(notify_admins=False, why="بوت", startup=True)
        # ارجاع را نگه دار؛ وگرنه حلقهٔ پشتیبان ممکن است وسط کار جمع شود و بک‌آپ نرود.
        self._bg_tasks = []
        for _coro in (self.heartbeat_loop(), self.liveness_loop(),
                      self.duplicate_watch_loop(),
                      self.reminder_loop(), self.points_loop(),
                      self.trial_loop()):
            self._bg_tasks.append(asyncio.create_task(_coro))
        # از این لحظه «سکوت» معنا دارد: بوتِ اولیه (اتصال، بازیابی، بالا
        # آوردنِ سلف‌ها) می‌تواند دقیقه‌ها طول بکشد و نباید گیر کردن شمرده شود.
        LIVE["ready"] = True
        mark_live("loop")
        # پشتیبان خودکار روی تلگرام
        try:
            if backup_target_raw():
                self._bg_tasks.append(asyncio.create_task(self.backup_loop()))
                print(f"  📦 پشتیبان خودکار فعال: هر {backup_interval()}s به {backup_target_raw()}", flush=True)
        except Exception as e:
            print(f"  ⚠️ پشتیبان خودکار: {e}", flush=True)
        try:
            _loop = asyncio.get_running_loop()
            _loop.add_signal_handler(
                signal.SIGTERM, lambda: asyncio.create_task(self._graceful_stop()))
        except Exception as e:
            print(f"  ⚠️ سیگنال خاموشی: {type(e).__name__}", flush=True)

        @self.bot.on(events.NewMessage(incoming=True))
        async def handler(ev):
            # پیامِ تازه = بهترین شاهدِ اینکه اتصال واقعاً کار می‌کند.
            mark_live("update")
            if not ev.is_private:
                return
            # پیامی که موقع خاموشی فرستاده شده، پردازش نشود
            try:
                mdate = getattr(ev.message, "date", None)
                if mdate and mdate.timestamp() < self.boot_at - 5:
                    return
            except Exception:
                pass
            if ev.photo and self.shop and ev.sender_id not in self.fsm:
                if (not self.is_admin(ev.sender_id)
                        and await self.enforce_join(ev.sender_id, chat=ev.chat_id)):
                    return
                op = self.shop.last_open_order(ev.sender_id)
                if op:
                    o = self.shop.attach_receipt(
                        op["id"], str(ev.id), (ev.raw_text or "")[:300] or None)
                    self._receipts[str(ev.id)] = (ev.chat_id, ev.id)
                    await self.notify_admins_receipt(o, ev)
                    return await self.say(ev.chat_id,
                        f"✅ رسید سفارش #{_fa_digits(op['id'])} دریافت شد.\n"
                        "به‌محض تأیید، سرویست فعال می‌شود.")
            uid = ev.sender_id
            text = command_text(ev.raw_text or "")
            try:
                if self.is_admin(uid) and await self.accept_admin_backup_file(ev):
                    return
            except Exception as e:
                print(f"  ⚠️ فایل پشتیبان مدیر: {type(e).__name__}: {e}", flush=True)
            sender = await ev.get_sender()
            user = {"username": getattr(sender, "username", None),
                    "name": getattr(sender, "first_name", "") or ""}

            # دکمه «بازگشت» کیبورد درخواست شماره، متن عادی می‌فرستد.
            phone_step = (self.fsm.get(uid) or {}).get("step") in ("phone", "verify_phone", "verify_referral")
            if phone_step and text in ("بازگشت", "⬅️ بازگشت", "لغو", "❌ لغو"):
                await self.cancel(uid)
                if self.shop:
                    self.shop.cancel_open(uid)
                await self.hide_reply_keyboard(ev.chat_id)
                return await self.say(ev.chat_id, "به منوی اصلی برگشتی.",
                                      main_menu(self.is_admin(uid), self.cfg["shop_on"],
                                                self.cfg["points_on"],
                                                bool((self.db.get(uid) or {}).get("session")),
                                                self.sup.is_running(uid),
                                   self.trial_available(uid),
                                   trial_label=self.trial_label(),
                                   has_cmds=self.has_cmds(),
                                   has_hub=self.hub_on()))

            ev_phone, _oid = event_phone(ev)
            if (not self.is_admin(uid)
                    and not text.lower().startswith("/start")
                    and not ev_phone
                    and await self.enforce_join(uid, chat=ev.chat_id)):
                return
            if (not self.is_admin(uid)
                    and not text.lower().startswith("/start")
                    and not ev_phone
                    and await self.enforce_rules(uid, chat=ev.chat_id)):
                return

            # ---- مراحل دکمه‌ای ----
            st0 = self.fsm.get(uid)
            if st0 and not text.startswith("/"):
                stp = st0.get("step")

                if (stp == "tut_set" or stp == "sec_set" or stp == "sample_set") and self.is_admin(uid):
                    # ثبت محتوای آموزش فعال‌سازی / یک بخش — هر نوع پیامی:
                    # متن، لینک، عکس، ویدیو، ویس، فایل، استیکر، آلبوم
                    # (هر آیتم جدا می‌آید). برای بخش‌ها id بخش هم نگه داشته می‌شود.
                    is_sample = stp == "sample_set"
                    pending_key = "sample_pending" if is_sample else "tut_pending"
                    chat_key = "sample_chat" if is_sample else "tut_chat"
                    mode = st0.get("mode") or "replace"
                    src_chat = int(st0.get(chat_key) or 0)
                    if (not is_sample and mode == "append" and src_chat
                            and int(ev.chat_id or 0) != src_chat):
                        # محتوای قبلی در چتِ دیگری ثبت شده و یک لیستِ پیام فقط
                        # یک چتِ منبع دارد؛ هیچ چیزی دست نمی‌خورد تا محتوای
                        # قبلیِ مدیر پاک یا قاطی نشود.
                        return await self.say(ev.chat_id,
                            "⚠️ <b>این پیام ثبت نشد</b>\n\n"
                            "محتوای قبلیِ این آموزش در چتِ دیگری ثبت شده و "
                            "نمی‌شود پیامِ چتِ دیگر را به آن چسباند.\n"
                            "محتوا را در <b>همان چتی</b> بفرست که قبلی‌ها را "
                            "فرستاده بودی، یا از «📤 ثبت / تغییر محتوا "
                            "(جایگزینی)» از اول ثبت کن.",
                            key=f"tut:chatdiff:{int(time.time())}")
                    pend = st0.setdefault(pending_key, [])
                    st0.setdefault(chat_key, ev.chat_id)
                    had_before = len(pend)
                    pend.append(ev.id)
                    kind = self._content_kind(m=ev, text=text)
                    if is_sample:
                        head = "🎞 نمونه‌های جفج رفتن ربات\n"
                        btn = "a:sample_done"
                    elif stp == "sec_set":
                        sec_now = self.tut_find(st0.get("sec_id") or 0) or {}
                        head = f"🧩 بخش: {sec_now.get('name') or '—'}\n"
                        btn = f"a:sec_done:{st0.get('sec_id') or 0}"
                    else:
                        head = ""
                        btn = "a:tut_done"
                    tail = (f"➕ {_fa_digits(had_before)} پیام قبلی + "
                            f"{_fa_digits(len(pend) - had_before)} پیام تازه\n"
                            if mode == "append" and had_before else "")
                    return await self.say(ev.chat_id,
                        f"➕ ثبت شد: {kind}\n"
                        f"📦 مجموع: {_fa_digits(len(pend))} پیام\n"
                        f"{tail}"
                        f"{head}"
                        "<i>تمام شد؟ دکمه‌ی «✅ تمام شد — ذخیره» در پیامِ بالا را بزن.</i>",
                        [[B("✅ تمام شد — ذخیره", btn, "success")]])

                # ── بخش‌های آموزش: ورودی‌های متنی پنل مدیر ──
                if stp == "sec_name" and self.is_admin(uid):
                    sid = int(st0.get("sec_id") or 0)
                    self.fsm.pop(uid, None)
                    name = text.strip()[:60]
                    if not name:
                        return await self.say(ev.chat_id, "نام خالی بود؛ دوباره بفرست.")
                    self.tut_update(sid, name=name)
                    self.db.log(uid, "sec_name", f"#{sid} {name}")
                    return await self.say(ev.chat_id, f"✅ نام بخش → <b>{name}</b>",
                                          [[B("🧩 بخش", f"a:sec:{sid}", "success")],
                                           back_btn("a:secs")])
                if stp == "sec_emoji" and self.is_admin(uid):
                    sid = int(st0.get("sec_id") or 0)
                    self.fsm.pop(uid, None)
                    em = text.strip()[:4] or "▫️"
                    self.tut_update(sid, emoji=em)
                    return await self.say(ev.chat_id, f"✅ ایموجی بخش → {em}",
                                          [[B("🧩 بخش", f"a:sec:{sid}", "success")]])
                if stp == "sec_delay" and self.is_admin(uid):
                    sid = int(st0.get("sec_id") or 0)
                    self.fsm.pop(uid, None)
                    try:
                        sec = max(0, int(digits(text) or 0))
                    except (TypeError, ValueError):
                        sec = 0
                    self.tut_update(sid, delay=sec)
                    return await self.say(ev.chat_id,
                        f"✅ فاصله‌ی این بخش → {_fa_digits(sec)} ثانیه",
                        [[B("🧩 بخش", f"a:sec:{sid}", "success")]])
                if stp == "sec_note" and self.is_admin(uid):
                    sid = int(st0.get("sec_id") or 0)
                    self.fsm.pop(uid, None)
                    note = "" if text.strip().lower() in ("خاموش", "پاک", "حذف", "-") \
                        else text.strip()[:1000]
                    self.tut_update(sid, note=note)
                    return await self.say(ev.chat_id,
                        "✅ متن پایان بخش " + ("حذف شد." if not note else "ذخیره شد."),
                        [[B("🧩 بخش", f"a:sec:{sid}", "success")]])
                if stp == "sec_text" and self.is_admin(uid):
                    sid = int(st0.get("sec_id") or 0)
                    self.fsm.pop(uid, None)
                    raw = text.strip()
                    if raw.lower() in ("خاموش", "پاک", "حذف", "-"):
                        body = ""
                    else:
                        # فرمتِ تلگرام (بولد/لینک…) را به HTML نگه می‌داریم
                        body = raw
                        try:
                            ents = getattr(getattr(ev, "message", None), "entities", None)
                            if ents:
                                from telethon.extensions import html as _tg_html
                                body = _tg_html.unparse(raw, ents)
                        except Exception as e:
                            print("sec_text html:", type(e).__name__, e)
                        body = body[:3500]
                    self.tut_update(sid, text=body)
                    self.db.log(uid, "sec_text", f"#{sid} {len(body)}")
                    return await self.say(ev.chat_id,
                        "✅ متن بخش " + ("حذف شد." if not body else
                                          f"ذخیره شد ({_fa_digits(len(body))} حرف)."),
                        [[B("👁 پیش‌نمایش", f"a:sec_vw:{sid}", "primary"),
                          B("🧩 بخش", f"a:sec:{sid}", "success")]])
                if stp == "sec_btn_label" and self.is_admin(uid):
                    sid = int(st0.get("sec_id") or 0)
                    self.fsm.pop(uid, None)
                    lbl = text.strip()[:40]
                    if not lbl:
                        return await self.say(ev.chat_id, "متن خالی بود؛ دوباره بفرست.")
                    self.tut_update(sid, btn_label=lbl)
                    return await self.say(ev.chat_id, f"✅ متن دکمه → {lbl}",
                                          [[B("🧩 بخش", f"a:sec:{sid}", "success")]])
                if stp == "sec_btn_url" and self.is_admin(uid):
                    sid = int(st0.get("sec_id") or 0)
                    self.fsm.pop(uid, None)
                    url = text.strip()
                    if not url.startswith(("http://", "https://", "tg://")):
                        url = "https://" + url.lstrip("/")
                    self.tut_update(sid, btn_cmd=url,
                                    btn_label=(self.tut_find(sid) or {}).get("btn_label")
                                    or "🔗 لینک")
                    return await self.say(ev.chat_id, f"✅ دکمه‌ی لینک → <code>{url}</code>",
                                          [[B("🧩 بخش", f"a:sec:{sid}", "success")]])
                if stp == "tut_wait" and self.is_admin(uid):
                    self.fsm.pop(uid, None)
                    sec = max(0, int(digits(text) or 0))
                    self.cfg["tut_auto_wait"] = sec
                    self.cfg.save()
                    return await self.say(ev.chat_id,
                        f"✅ تأخیر ارسال خودکار → {_fa_digits(sec)} ثانیه",
                        [[B("⚙️ ارسال خودکار", "a:tut_auto", "primary")]])

                if stp == "disc":
                    self.fsm.pop(uid, None)
                    return await self.make_invoice(
                        uid, ev, st0["plan"], text.strip().split()[0], False)
                if stp == "pdisc":
                    self.fsm.pop(uid, None)
                    return await self.pack_invoice(
                        uid, ev, st0["pack"], text.strip().split()[0], False)

                if stp == "custom_pts" and self.shop:
                    try:
                        n = int(digits(text))
                    except (ValueError, TypeError):
                        return await self.say(ev.chat_id,
                            "فقط عدد بفرست. مثال: <code>100</code>")
                    mn, mx = self.cfg["min_points_buy"], self.cfg["max_points_buy"]
                    if n < mn:
                        return await self.say(ev.chat_id,
                            f"کمترین مقدار {_fa_digits(mn)} امتیاز است.")
                    if n > mx:
                        return await self.say(ev.chat_id,
                            f"بیشترین مقدار {_fa_digits(mx)} امتیاز است.")
                    self.fsm.pop(uid, None)
                    return await self.custom_invoice(uid, ev, n)

                if stp == "topup" and self.shop:
                    try:
                        amt = int(digits(text))
                    except (ValueError, TypeError):
                        return await self.say(ev.chat_id,
                            "فقط عدد بفرست. مثال: <code>50000</code>")
                    mn, mx = self.cfg["min_topup"], self.cfg["max_topup"]
                    if amt < mn:
                        return await self.say(ev.chat_id,
                            f"کمترین مبلغ {money(mn)} است.")
                    if amt > mx:
                        return await self.say(ev.chat_id,
                            f"بیشترین مبلغ {money(mx)} است.")
                    self.fsm.pop(uid, None)
                    return await self.topup_invoice(uid, ev, amt)
                if stp == "ticket" and self.shop:
                    self.fsm.pop(uid, None)
                    tid = self.shop.new_ticket(uid, text[:60], text)
                    for a in self.cfg["admin_ids"]:
                        await self.say(a,
                            f"🎧 <b>تیکت #{_fa_digits(tid)}</b>\nاز <code>{uid}</code>"
                            f"\n\n{text[:500]}\n\nجواب: <code>/tr {tid} متن</code>")
                    return await self.say(ev.chat_id,
                        f"✅ تیکت #{_fa_digits(tid)} ثبت شد.",
                        [[B("⬅️ بازگشت", "m:home")]])
                if stp == "deny" and self.is_admin(uid):
                    self.fsm.pop(uid, None)
                    return await self.shop_admin(
                        uid, ev.chat_id, "deny", f"{st0['oid']} {text}")

                if stp == "bcast" and self.is_admin(uid):
                    self.fsm.pop(uid, None)
                    n = 0
                    for c in self.db.all():
                        if await self.say(c["uid"], text):
                            n += 1
                        await asyncio.sleep(0.12)
                    return await self.say(ev.chat_id,
                        f"✅ پیام همگانی به {_fa_digits(n)} نفر رسید.",
                        [[B("🛠 پنل مدیر", "a:home")]])

                if stp == "disc_new" and self.is_admin(uid):
                    self.fsm.pop(uid, None)
                    await self.shop_admin(uid, ev.chat_id, "disc", text)
                    return await self.say(ev.chat_id, "اگر فرمت درست بود کد ساخته شد.",
                                          [[B("🎟 کدها", "a:discs")], [B("🛠 پنل", "a:home")]])

                if stp == "price_plan" and self.is_admin(uid):
                    pid = st0.get("pid")
                    self.fsm.pop(uid, None)
                    try:
                        val = int(digits(text))
                    except Exception:
                        return await self.say(ev.chat_id, "فقط عدد بفرست.")
                    self.shop.set_plan(pid, price=val)
                    return await self.say(ev.chat_id, f"✅ قیمت پلن شد {money(val)}",
                                          [[B("💰 قیمت پلن‌ها", "a:prices")]])

                if stp == "price_pack" and self.is_admin(uid):
                    kid = st0.get("kid")
                    self.fsm.pop(uid, None)
                    try:
                        val = int(digits(text))
                    except Exception:
                        return await self.say(ev.chat_id, "فقط عدد بفرست.")
                    self.shop.set_pack(kid, price=val)
                    return await self.say(ev.chat_id, f"✅ قیمت بسته شد {money(val)}",
                                          [[B("🎯 قیمت امتیاز", "a:pkprice")]])

                if stp == "gp_n" and self.is_admin(uid):
                    tid = st0.get("tid")
                    self.fsm.pop(uid, None)
                    raw = text.strip().replace("−", "-")
                    neg = raw.startswith("-")
                    try:
                        amt = int(digits(raw)) * (-1 if neg else 1)
                    except Exception:
                        return await self.say(ev.chat_id, "عدد نامعتبر.")
                    nb = self.shop.p_add(tid, amt, "admin", "مدیر از پنل")
                    self.sync_points_limits(tid)
                    sign = "+" if amt > 0 else ""
                    await self.say(tid, f"🎯 امتیازت {sign}{_fa_digits(amt)} شد.\nموجودی: {_fa_digits(nb)}")
                    return await self.say(ev.chat_id,
                        f"✅ {tid}: {sign}{_fa_digits(amt)} → موجودی {_fa_digits(nb)}",
                        [[B("👤 مشتری", f"au:{tid}")]])

                if stp == "say_u" and self.is_admin(uid):
                    tid = st0.get("tid")
                    self.fsm.pop(uid, None)
                    ok = await self.say(tid, text)
                    return await self.say(ev.chat_id, "✅ رفت" if ok else "❌ نرسید",
                                          [[B("👤 مشتری", f"au:{tid}")]])

                if stp == "rt_set" and self.is_admin(uid):
                    self.fsm.pop(uid, None)
                    r = self.rt_find(st0.get("rt_id"))
                    if not r:
                        return await self.say(ev.chat_id, "این مورد پیدا نشد.",
                                              [[B("📝 متن‌های ربات", "a:rt", "primary")]])
                    if text.strip().lower() in self.RT_CLEAR_WORDS:
                        val = ""
                    else:
                        val = self.rt_clean(r, text)
                    self.cfg[r[3]] = val
                    if r[0] == "rules" and val:
                        self.db.rules_reset_all()
                    self.db.log(uid, "rt_set", f"{r[0]} {len(val)}")
                    return await self.say(ev.chat_id,
                        (f"✅ {r[2]} ذخیره شد." if val else
                         f"✅ {r[2]} به پیش‌فرض برگشت."),
                        [[B(f"{r[1]} {r[2]}", f"a:rt:{r[0]}", "primary")],
                         [B("📝 متن‌های ربات", "a:rt", "success")]])

                if stp == "rules_set" and self.is_admin(uid):
                    self.fsm.pop(uid, None)
                    raw = text.strip()
                    if raw.lower() in self.RT_CLEAR_WORDS:
                        val = ""
                    else:
                        val = raw[:3500]
                    self.cfg["rules_text"] = val
                    self.cfg.save()
                    if val:
                        self.db.rules_reset_all()
                    self.db.log(uid, "rules_set", str(len(val)))
                    t, kb = self.rules_screen()
                    return await self.say(ev.chat_id,
                        ("✅ متن قوانین جدید ذخیره شد و در شروع ربات نمایش داده می‌شود.\n"
                         if val else "✅ متن قوانین به حالت پیش‌فرض برگشت.\n")
                        + self.LINE + "\n" + t, kb)

                if stp == "rules_btn_set" and self.is_admin(uid):
                    self.fsm.pop(uid, None)
                    raw = text.strip()
                    if raw.lower() in self.RT_CLEAR_WORDS:
                        val = ""
                    else:
                        val = raw[:80]
                    self.cfg["rules_btn"] = val
                    self.cfg.save()
                    self.db.log(uid, "rules_btn_set", str(len(val)))
                    t, kb = self.rules_screen()
                    return await self.say(ev.chat_id,
                        (f"✅ متن دکمه تأیید قوانین → <b>{self._esc(val)}</b>\n"
                         if val else "✅ متن دکمه تأیید به پیش‌فرض برگشت.\n")
                        + self.LINE + "\n" + t, kb)

                # ── 📋 دستورات آماده: افزودنِ سه‌قدمی ──
                if stp == "cm_add" and self.is_admin(uid):
                    val = text.strip()
                    d = dict(st0.get("d") or {})
                    n = int(st0.get("n") or 1)
                    if n == 1:
                        if not val:
                            return await self.say(ev.chat_id,
                                "عنوان خالی نمی‌شود؛ یک عنوان بفرست "
                                "یا /cancel بزن.",
                                [[B("⬅️ بازگشت", "a:cm")]])
                        d["title"] = val[:80]
                        self.fsm[uid] = {"step": "cm_add", "n": 2, "d": d}
                        return await self.say(ev.chat_id,
                            "➕ <b>افزودن دستور</b> — قدم ۲ از ۳\n%s\n"
                            "عنوان: <b>%s</b>\n\n"
                            "حالا <b>دستور</b> را بفرست؛ مثل "
                            "<code>.panel</code> یا "
                            "<code>کانال @channel</code>.\n\n"
                            "<i>/cancel برای لغو</i>"
                            % (self.LINE, self._esc(d["title"])),
                            [[B("⬅️ بازگشت", "a:cm")]])
                    if n == 2:
                        if not val:
                            return await self.say(ev.chat_id,
                                "دستور خالی نمی‌شود؛ دستور را بفرست "
                                "یا /cancel بزن.",
                                [[B("⬅️ بازگشت", "a:cm")]])
                        d["cmd"] = val[:200]
                        self.fsm[uid] = {"step": "cm_add", "n": 3, "d": d}
                        return await self.say(ev.chat_id,
                            "➕ <b>افزودن دستور</b> — قدم ۳ از ۳\n%s\n"
                            "عنوان: <b>%s</b>\n"
                            "دستور: <code>%s</code>\n\n"
                            "یک <b>توضیح ساده</b> بفرست، یا <code>-</code> "
                            "بفرست تا بدون توضیح ثبت شود.\n\n"
                            "<i>/cancel برای لغو</i>"
                            % (self.LINE, self._esc(d["title"]),
                               self._esc(d["cmd"])),
                            [[B("⬅️ بازگشت", "a:cm")]])
                    # n == 3 → توضیح (قابل رد شدن)
                    d["note"] = "" if val in ("-", "—", "خالی", "رد", "بیخیال") \
                        else val[:300]
                    self.fsm.pop(uid, None)
                    items = self.cmd_items()
                    items.append({"title": d.get("title") or "",
                                  "cmd": d.get("cmd") or "",
                                  "note": d.get("note") or ""})
                    self.cmd_save(items)
                    self.db.log(uid, "cm_add", d.get("cmd") or d.get("title"))
                    return await self.say(ev.chat_id,
                        "✅ دستور «%s» ثبت شد (%s از %s).\n"
                        "مشتری همین را داخل <code>&lt;code&gt;</code> می‌بیند و "
                        "با یک لمس کپی می‌کند."
                        % (self._esc(d.get("title") or d.get("cmd") or "—"),
                           _fa_digits(len(items)), _fa_digits(len(items))),
                        [[B("📋 دستورهای ثبت‌شده", "a:cm", "primary")],
                         [B("👁 پیش‌نمایش", "a:cm:prev")],
                         [B("➕ افزودن دستور", "a:cmi", "success")]])

                # ── ویرایشِ یک فیلد از یک دستور ──
                if stp == "cm_edit" and self.is_admin(uid):
                    self.fsm.pop(uid, None)
                    i = int(st0.get("idx") or 0)
                    f = self.cm_field(st0.get("f"))
                    items = self.cmd_items()
                    if not f or not (0 <= i < len(items)):
                        return await self.say(ev.chat_id, "این مورد پیدا نشد.",
                                              [[B("📋 دستورات آماده", "a:cm",
                                                 "primary")]])
                    val = text.strip()
                    items[i][f[1]] = "" if val in ("-", "—", "خالی", "پاک",
                                                   "حذف") else val[:300]
                    if not (items[i]["title"] or items[i]["cmd"]):
                        return await self.say(ev.chat_id,
                            "عنوان و دستور با هم خالی نمی‌شوند؛ این مورد "
                            "عوض نشد.", [[B("⬅️ بازگشت", "a:cme:%d" % i)]])
                    self.cmd_save(items)
                    self.db.log(uid, "cm_edit", "%d:%s" % (i, f[1]))
                    return await self.say(ev.chat_id,
                        "✅ %s ذخیره شد." % f[2],
                        [[B("📋 %s" % (items[i]["title"] or items[i]["cmd"]),
                           "a:cme:%d" % i, "primary")],
                         [B("📋 دستورات آماده", "a:cm", "success")]])

                # ── متنِ بالای صفحه ──
                if stp == "cm_intro" and self.is_admin(uid):
                    self.fsm.pop(uid, None)
                    val = text.strip()
                    self.cfg["cmd_intro"] = "" if val in ("-", "—", "خالی",
                                                          "پاک", "حذف",
                                                          "پیش‌فرض") else val[:600]
                    self.db.log(uid, "cm_intro", str(len(self.cfg["cmd_intro"])))
                    return await self.say(ev.chat_id,
                        "✅ متن بالای صفحه ذخیره شد." if self.cfg["cmd_intro"]
                        else "✅ متن بالای صفحه خالی شد.",
                        [[B("👁 پیش‌نمایش", "a:cm:prev", "primary")],
                         [B("📋 دستورات آماده", "a:cm", "success")]])

                # ── متنِ بالای «🗂 توضیحات» ──
                if stp == "hub_intro" and self.is_admin(uid):
                    self.fsm.pop(uid, None)
                    val = text.strip()
                    self.cfg["hub_intro"] = "" if val in ("-", "—", "خالی",
                                                          "پاک", "حذف",
                                                          "پیش‌فرض") else val[:800]
                    self.db.log(uid, "hub_intro",
                                str(len(self.cfg["hub_intro"])))
                    return await self.say(ev.chat_id,
                        "✅ متن بالای فهرست توضیحات ذخیره شد."
                        if self.cfg["hub_intro"] else
                        "✅ متن بالای فهرست به حالت پیش‌فرض برگشت.",
                        [[B("👁 پیش‌نمایش فهرست", "a:hub_p", "primary")],
                         [B("🗂 توضیحات", "a:hub", "success")]])

                if stp == "welcome_set" and self.is_admin(uid):
                    self.fsm.pop(uid, None)
                    self.cfg["welcome"] = "" if text.lower() in ("خاموش", "پاک", "حذف", "-") else text[:2000]
                    self.cfg.save()
                    return await self.say(ev.chat_id,
                        "✅ متن خوش‌آمدگویی ذخیره شد." if self.cfg["welcome"] else
                        "✅ متن خوش‌آمدگویی حذف شد.",
                        [[B("📝 متن خوش‌آمدگویی", "a:welcome", "primary")],
                         [B("🛠 پنل مدیر", "a:home", "danger")]])

                if stp == "card_set" and self.is_admin(uid):
                    self.fsm.pop(uid, None)
                    return await self.shop_admin(uid, ev.chat_id, "card", text)

                if stp == "ok_days" and self.is_admin(uid):
                    tid = st0.get("tid")
                    self.fsm.pop(uid, None)
                    days = int(digits(text) or 0)
                    if days <= 0:
                        return await self.say(ev.chat_id, "عدد روز را بفرست.")
                    c = self.db.get(tid)
                    if not c:
                        return await self.say(ev.chat_id, "پیدا نشد.")
                    base = max(c["expires_at"] or 0, now())
                    # مثل /ok: مُهرِ کهنهٔ تست رایگان پاک شود تا has_sub
                    # اشتراکِ تازه را نبیند و مشتری «امتیازی» حساب نشود.
                    self.db.set(tid, expires_at=base + days * 86400, status="active",
                                current_plan_id=0, trial_expires_at=0)
                    self.sup.write_limits(tid, self.effective_plan(tid) or
                                          {"name": "اشتراک دستی", "max_accounts": 1})
                    await self.say(tid, f"✅ سرویس شما {_fa_digits(days)} روز فعال شد.")
                    return await self.say(ev.chat_id, f"✅ {tid} → {human_left(self.db.get(tid)['expires_at'])}",
                                          [[B("👤 مشتری", f"au:{tid}")]])

                if stp == "acct_n" and self.is_admin(uid):
                    tid = st0.get("tid")
                    self.fsm.pop(uid, None)
                    v = max(0, int(digits(text) or 0))
                    c = self.db.get(tid)
                    if not c:
                        return await self.say(ev.chat_id, "پیدا نشد.")
                    self.db.set(tid, max_accounts=v)
                    if v > 0:
                        self.sup.write_limits(tid, {"name": "سفارشی", "max_accounts": v},
                                              override_max_accounts=v)
                    else:
                        if (self.cfg.get("points_on") and self.shop
                                and not self.has_sub(tid)):
                            bal = self.shop.p_balance(tid)
                            per = max(1, int(self.cfg["cost_per_hour"]))
                            self.sup.write_limits(tid, None, points_mode=True,
                                                  points=bal, hours_left=bal // per)
                        else:
                            best = self.effective_plan(tid) or {"name": "", "max_accounts": 1}
                            self.sup.write_limits(tid, best)
                    if self.sup.is_running(tid):
                        await self.sup.restart(tid)
                    await self.say(tid, f"👥 سقف اکانتت → <b>{_fa_digits(v)}</b>")
                    return await self.say(ev.chat_id,
                        f"✅ سقف اکانت {tid} → <b>{_fa_digits(v)}</b>"
                        + ("" if v else " (برگشت به پلن)"),
                        [[B("👤 مشتری", f"au:{tid}")]])

                if stp == "trial_min" and self.is_admin(uid):
                    self.fsm.pop(uid, None)
                    mins = self._parse_trial_minutes(text)
                    if not mins:
                        return await self.say(ev.chat_id,
                            "عدد نامعتبر. مثال: <code>90</code> (دقیقه) یا "
                            "<code>2 ساعت</code>",
                            [[B("🎁 تست رایگان", "a:trial", "primary")]])
                    mins, warn = self._set_trial_minutes(mins)
                    self.db.log(uid, "trial_minutes", str(mins))
                    t, kb = self.trial_screen()
                    return await self.say(ev.chat_id,
                        f"✅ مدت تست: <b>{trial_duration_label(mins)}</b>  ·  "
                        f"یادآوری: {_fa_digits(warn)} دقیقه آخر\n"
                        + self.LINE + "\n" + t, kb)

                if stp == "ufind_q" and self.is_admin(uid):
                    self.fsm.pop(uid, None)
                    matches = self._resolve_admin_users(text)
                    if not matches:
                        return await self.say(ev.chat_id,
                            "❌ کاربری با این مشخصات پیدا نشد.",
                            [[B("🔍 جستجوی دوباره", "a:ufind", "primary")],
                             back_btn("a:ulist:0")])
                    if len(matches) == 1:
                        c = matches[0]
                        return await self.say(ev.chat_id,
                            self._admin_user_text(c), self._admin_user_kb(c))
                    kb = [[B(f"👤 {m.get('name') or m['uid']} ({m['uid']})",
                             f"au:{m['uid']}", "primary")] for m in matches[:8]]
                    kb.append([B("🔍 جستجوی دوباره", "a:ufind", "primary")])
                    kb.append(back_btn("a:ulist:0"))
                    return await self.say(ev.chat_id,
                        f"🔍 <b>{_fa_digits(len(matches))} کاربر پیدا شد</b> — انتخاب کن:", kb)

                if stp == "uwipe_pick" and self.is_admin(uid):
                    self.fsm.pop(uid, None)
                    matches = self._resolve_admin_users(text)
                    if not matches:
                        return await self.say(ev.chat_id,
                            "❌ کاربری با این مشخصات پیدا نشد.",
                            [[B("🗑 تلاش دوباره", "a:uwipe", "danger")],
                             back_btn("a:home")])
                    if len(matches) == 1:
                        txt_c, kb_c = self._admin_wipe_confirm_view(matches[0]["uid"])
                        return await self.say(ev.chat_id, txt_c, kb_c)
                    kb = [[B(f"🗑 {m.get('name') or m['uid']} ({m['uid']})",
                             f"aud:{m['uid']}", "danger")] for m in matches[:8]]
                    kb.append([B("🔍 تلاش دوباره", "a:uwipe", "primary")])
                    kb.append(back_btn("a:home"))
                    return await self.say(ev.chat_id,
                        f"🗑 <b>{_fa_digits(len(matches))} کاربر پیدا شد</b> — کدام پاک شود؟", kb)

                if stp == "fjoin_add" and self.is_admin(uid):
                    self.fsm.pop(uid, None)
                    raw = text.strip()
                    if "t.me/" in raw:
                        raw = raw.split("t.me/")[-1].split("?")[0].strip("/")
                    raw = raw.lstrip("@")
                    if not raw:
                        return await self.say(ev.chat_id, "یوزرنیم کانال را بفرست.")
                    try:
                        ent = await self.bot.get_entity(raw)
                    except Exception as e:
                        return await self.say(ev.chat_id,
                            f"❌ کانال پیدا نشد: {type(e).__name__}")
                    if not await self.bot_admin_in(ent):
                        return await self.say(ev.chat_id,
                            "❌ بات در این کانال ادمین نیست.\n"
                            "اول بات را ادمین کن، بعد دوباره اضافه کن.",
                            [[B("📣 جوین اجباری", "a:fjoin", "danger")]])
                    un = getattr(ent, "username", None) or raw
                    title = getattr(ent, "title", None) or un
                    cid = getattr(ent, "id", None)
                    rows = self.force_chans()
                    if any(str(r.get("id")) == str(cid) or r.get("user") == un
                           for r in rows):
                        return await self.say(ev.chat_id, "این کانال از قبل هست.",
                                              [[B("📣 جوین اجباری", "a:fjoin", "danger")]])
                    rows.append({"id": cid, "user": un, "title": title})
                    self.save_force_chans(rows)
                    self._join_ok.clear()
                    return await self.say(ev.chat_id,
                        f"✅ اضافه شد: <b>{title}</b> (@{un})\n"
                        "عضویت از این به بعد چک می‌شود.",
                        [[B("📣 جوین اجباری", "a:fjoin", "danger")]])

            # کانتکت را قبل از رسید بخوان
            st = self.fsm.get(uid)
            phone_c, owner_id = event_phone(ev)
            if st and st.get("step") in ("verify_phone", "verify_referral"):
                if not phone_c and text and not text.startswith("/"):
                    d_txt = digits(text)
                    if (d_txt.startswith("09") and len(d_txt) == 11) or                        (d_txt.startswith("989") and len(d_txt) == 12) or                        (d_txt.startswith("9") and len(d_txt) == 10):
                        phone_c = d_txt
                        owner_id = uid
                if phone_c:
                    if owner_id and owner_id != uid:
                        return await self.say(ev.chat_id, "❌ فقط شماره خودت را با دکمه تأیید کن.")
                    normalized = self.save_verified_phone(uid, phone_c)
                    if not normalized:
                        return await self.say(ev.chat_id,
                            "❌ فقط شماره موبایل ایران با کد +98 قابل تأیید است.")
                    ref_uid, ref_points = self.reward_verified_referral(uid)
                    if ref_uid:
                        await self.say(ref_uid,
                            f"🎁 دعوت معتبر شد! {_fa_digits(ref_points)} امتیاز به حسابت اضافه شد.")
                    existing_rewards = self.reward_existing_referrals(uid)
                    if existing_rewards:
                        total_pts = sum(p for _, p in existing_rewards)
                        await self.say(uid,
                            f"🎁 پاداش {_fa_digits(len(existing_rewards))} دعوت قبلی شما آزاد شد! "
                            f"{_fa_digits(total_pts)} امتیاز به حسابت اضافه شد.")
                    if st.get("step") == "verify_referral":
                        await self.say(ev.chat_id, "✅ شماره تأیید شد و پاداش زیرمجموعه فعال شد.",
                                       clear_reply_keyboard())
                        return await self.say(ev.chat_id,
                            "🎁 حالا می‌توانی لینک زیرمجموعه‌گیری‌ات را بگیری.",
                            [[B("🎁 زیرمجموعه‌گیری", "m:ref", "success")], back_btn()])
                    await self.say(ev.chat_id, "✅ شماره تأیید شد. فاکتور کارت‌به‌کارت همین الان می‌آید.",
                                   clear_reply_keyboard())
                    return await self.resume_pending_pay(uid, ev.chat_id)
                return await self.say(ev.chat_id,
                    "❌ شماره از پیام گرفته نشد. لطفاً از دکمه «📱 تأیید شماره» پایین صفحه استفاده کنید.")
            if st and st.get("step") == "phone" and phone_c:
                if owner_id and owner_id != uid:
                    return await self.say(ev.chat_id, "❌ فقط شماره خودت را با دکمه ارسال کن.")
                if not phone_c.startswith("+"):
                    phone_c = "+" + digits(phone_c)
                return await self.setup_phone(uid, ev.chat_id, phone_c)

            # ---- رسید پرداخت — فقط وقتی در هیچ مرحله‌ای نیستیم ----
            if (self.shop and not text.startswith("/")
                    and uid not in self.fsm):
                op = self.shop.last_open_order(uid)
                if op and op["final"] > 0:
                    fid = None
                    if ev.photo:
                        try:
                            fid = ev.photo.id and await self._save_photo(ev, ev.sender_id)
                        except Exception:
                            fid = None
                    if fid or len(text) >= 4:
                        o = self.shop.attach_receipt(op["id"], fid,
                                                     text[:500] or None)
                        await self.notify_admins_order(o)
                        kind = {"wallet": "شارژ کیف پول",
                                "points": "خرید امتیاز"}.get(o["kind"], "اشتراک")
                        return await self.say(ev.chat_id,
                            f"✅ رسید دریافت شد\n{self.LINE}\n"
                            f"سفارش <code>#{_fa_digits(op['id'])}</code> — {kind}\n"
                            f"مبلغ: {money(op['final'])}\n{self.LINE}\n\n"
                            "<i>به‌محض تأیید مدیر، خبرت می‌کنم.</i>")

            # مرحله‌ی ورود
            if st and not text.startswith("/"):
                try:
                    if st["step"] == "phone":
                        return await self.setup_phone(uid, ev.chat_id, text)
                    if st["step"] == "code":
                        return await self.setup_code(uid, ev.chat_id, text)
                    if st["step"] == "pass":
                        return await self.setup_pass(uid, ev.chat_id, text)
                except Exception as e:
                    await self.cancel(uid)
                    return await self.say(ev.chat_id, f"❌ {type(e).__name__}")

            # اولین کسی که /start بزند، مدیر می‌شود
            if not self.cfg["admin_ids"] and text.startswith("/"):
                self.cfg["admin_ids"] = [uid]
                self.db.log(uid, "first_admin", "ثبت خودکار")
                print(f"\n✅ مدیر ثبت شد: {uid} "
                      f"({user['name']} @{user['username']})\n", flush=True)
                await self.say(ev.chat_id,
                    f"👑 <b>تو مدیر ربات شدی</b>\n{self.LINE}\n"
                    f"آیدی تو: <code>{uid}</code>\n"
                    f"در <code>{CONFIG_FILE}</code> ذخیره شد.\n{self.LINE}\n\n"
                    f"<b>قدم بعدی:</b>\n"
                    f"1. شماره کارت را ثبت کن:\n"
                    f"   <code>/card 6037xxxxxxxxxxxx نام صاحب کارت</code>\n"
                    f"2. سلامت سیستم را چک کن: /doctor\n"
                    f"3. پنل: /admin",
                    [[B("🛠 پنل مدیر", "a:home", "primary")]])

            if text in ("❌ لغو", "لغو"):
                await self.cancel(uid)
                return await self.say(ev.chat_id, "لغو شد.",
                    main_menu(self.is_admin(uid), self.cfg["shop_on"],
                              self.cfg["points_on"],
                              bool((self.db.get(uid) or {}).get("session")),
                              self.sup.is_running(uid),
                                   self.trial_available(uid),
                                   trial_label=self.trial_label(),
                                   has_cmds=self.has_cmds(),
                                   has_hub=self.hub_on()))

            if not text.startswith("/"):
                return await self.say(ev.chat_id, "/help را بزن.")

            parts = text[1:].split(None, 1)
            cmd = parts[0].lower().split("@")[0]
            arg = parts[1].strip() if len(parts) > 1 else ""

            try:
                if self.is_admin(uid):
                    if await self.shop_admin(uid, ev.chat_id, cmd, arg) is not None:
                        return
                    if await self.admin_cmd(uid, ev.chat_id, cmd, arg, ev=ev) is not None:
                        return
                if await self.shop_user(uid, ev.chat_id, cmd, arg, user) is not None:
                    return
                await self.user_cmd(uid, ev.chat_id, cmd, arg, user)
            except Exception as e:
                import traceback
                traceback.print_exc()
                await self.say(ev.chat_id, f"⚠️ {type(e).__name__}: {e}")

        @self.bot.on(events.CallbackQuery)
        async def cb(ev):
            try:
                await self.on_callback(ev)
            except Exception as e:
                import traceback
                traceback.print_exc()
                try:
                    await ev.answer(f"خطا: {type(e).__name__}")
                except Exception:
                    pass

        _boot_lines = list(getattr(self, "_boot_notice", []) or [])
        _boot_txt = "🟢 <b>ربات مدیر بالا آمد</b>\n"
        _boot_txt += (f"<i>نسخه {BUILD_VERSION} · نمونه {INSTANCE_ID} · "
                      f"{HOST_LABEL}</i>\n")
        if _boot_lines:
            _boot_txt += "\n" + "\n".join(_boot_lines) + "\n"
        _boot_txt += ("\nاگر دو پیام «بالا آمد» با نمونه‌های متفاوت می‌بینی، یعنی "
                      "یک سرویس قدیمی هنوز روشن است — همان را خاموش کن.")
        for a in c["admin_ids"]:
            await self.say(
                a, _boot_txt,
                [[B("🛠 پنل مدیر", "a:home", "primary")],
                 [B("🩺 عیب‌یابی", "a:diag", "success")]])
        if not c["admin_ids"]:
            print("  ⏳ منتظر اولین /start …\n", flush=True)

        return await self.serve_forever()

    async def serve_forever(self):
        """ربات را تا وقتی میزبان/مدیر نگفته «خاموش شو» زنده نگه می‌دارد.

        باگی که روی میزبان‌ها (Hostless، Render، Railway، blitz) به‌شکل
        «The process stopped soon after it started — Exit code 0» دیده
        می‌شد: `run_until_disconnected()` تمام می‌شد، `run()` مقدار ۰
        برمی‌گرداند و پروسه با کد ۰ می‌مرد. میزبان هم (به‌حق) می‌گفت
        «سرویس باید بالا بماند ولی پروسه تمام شد».

        چرا اتصال قطع می‌شود (و هیچ‌کدام دلیلِ مردنِ ربات نیست):

          * نمونه‌ی دوم با همان توکن روشن شده → تلگرام نشستِ یکی را
            می‌بندد (بیشتر وقت‌ها یک سرویسِ قدیمیِ جا‌مانده)؛
          * پرشِ شبکه یا ری‌استارتِ سرورهای تلگرام؛
          * خطای موقت (FloodWait/Timeout).

        پس اینجا، مثل یک رباتِ همیشه-روشن، دوباره وصل می‌شویم؛ فقط
        درخواستِ خاموشی (SIGTERM/دیپلوی) پروسه را با موفقیت می‌بندد.
        """
        tries = 0
        # وقتی اتصال «به‌اندازه‌ی کافی پایدار» ماند تازه شمارنده صفر می‌شود؛
        # وگرنه اتصالی که هر چند ثانیه قطع می‌شود (نمونه‌ی دوم با همان
        # توکن) تا ابد «موفق» حساب می‌شد و هیچ‌وقت به سقفِ تلاش نمی‌رسید.
        stable_since = 0.0
        try:
            stable_seconds = max(15, int(os.environ.get("JAFJ_STABLE_SECONDS") or 60))
        except Exception:
            stable_seconds = 60
        while True:
            reason = "اتصال قطع شد"
            try:
                await self.bot.run_until_disconnected()
            except asyncio.CancelledError:
                raise
            except Exception as e:
                reason = f"{type(e).__name__}: {e}"

            if getattr(self, "_stopping", False):
                print("  ✅ خاموشیِ درخواستی — خروجِ تمیز", flush=True)
                return 0

            if stable_since and (time.time() - stable_since) >= stable_seconds:
                tries = 0            # اتصال واقعاً پایدار بود
            stable_since = 0.0
            tries += 1
            limit = reconnect_limit()
            lim = "" if limit <= 0 else f"/{limit}"
            print(f"  ⚠️ ربات قطع شد ({reason}) — پروسه زنده می‌ماند؛ "
                  f"تلاشِ {tries}{lim} برای اتصالِ دوباره", flush=True)
            if limit > 0 and tries > limit:
                print("  ⛔ اتصالِ دوباره ممکن نشد. علتِ رایج: نمونه‌ی دیگری "
                      "با همین توکن روشن است (سرویسِ قدیمی را خاموش کن) یا "
                      "توکن باطل شده. — پروسه با کد ۱ خارج می‌شود تا میزبان "
                      "متوجهِ خطا شود.", flush=True)
                try:
                    log_crash("reconnect", f"{reason}\n{limit} tries failed")
                except Exception:
                    pass
                return 1
            wait = login_retry_wait(tries, base=5, cap=60)
            try:
                await asyncio.sleep(wait)
            except asyncio.CancelledError:
                raise
            if getattr(self, "_stopping", False):
                return 0
            try:
                # مهم: همین نمونهٔ کلاینت را دوباره وصل می‌کنیم، نه یک
                # TelegramClient تازه. هندلرهای /start و دکمه‌ها به همین
                # آبجکت بسته شده‌اند؛ اگر کلاینت عوض شود، ربات «بالا» می‌آید
                # ولی به هیچ پیامی جواب نمی‌دهد. اگر نشست واقعاً مرده باشد،
                # تلاش‌ها شکست می‌خورند و پروسه با کدِ غیرصفر خارج می‌شود تا
                # ناظر آن را از صفر (با هندلرهای تازه) بالا بیاورد.
                if not self.bot.is_connected():
                    await self.bot.connect()
                try:
                    authorized = await self.bot.is_user_authorized()
                except Exception:
                    authorized = True
                if not authorized:
                    await self.bot.start(bot_token=self.cfg.get("bot_token") or None)
                stable_since = time.time()
                print("  🔄 اتصال دوباره برقرار شد (همان نمونه — هندلرها حفظ شدند)",
                      flush=True)
                for a in (self.cfg.get("admin_ids") or []):
                    try:
                        await self.say(
                            a, "🔄 <b>اتصال ربات دوباره برقرار شد</b>\n"
                               f"<i>علتِ قطع: {reason}</i>")
                    except Exception:
                        break
            except asyncio.CancelledError:
                raise
            except Exception as e:
                print(f"  ⚠️ اتصالِ دوباره برقرار نشد: {type(e).__name__}: {e}",
                      flush=True)


def main():
    # اگر کد قدیمی (مثلاً از یک Volume کهنه) اجرا شده باشد، از نسخه‌ی ایمیج
    # دوباره اجرا شو؛ وگرنه هر دیپلوی بی‌اثر می‌ماند.
    ensure_fresh_code()
    print(f"\n{BUILD_TAG}", flush=True)
    print(f"  🆔 PID: {os.getpid()} — فقط یک پروسه باید این خط را نشان دهد", flush=True)
    # همیشه از پوشه‌ی خود فایل اجرا کن تا اگر از جای دیگری اجرا شد،
    # 95.py قدیمیِ پوشه‌ی فعلی اشتباهی انتخاب نشود.
    try:
        script_dir = os.path.dirname(os.path.abspath(sys.argv[0]))
        if script_dir:
            os.chdir(script_dir)
    except Exception:
        pass
    fix_workdir()
    gone = purge_old_selfbots(".")
    if gone:
        print("🗑 فایل سلف قدیمی پاک شد:")
        for g in gone[:20]:
            print("   ", g)
    ok, other = acquire_lock()
    if not ok:
        print(f"\n{'='*54}")
        print("  ⛔ یک نسخه از ربات همین حالا در حال اجراست")
        print(f"{'='*54}")
        print(f"  شناسه پروسه: {other}")
        print()
        print("  اول آن را ببند:")
        print(f"    kill {other}")
        print("  یا همه را یکجا:")
        print("    pkill -f manager_82.py")
        print()
        print("  بعد دوباره اجرا کن.")
        print(f"{'='*54}\n")
        return 1

    global SELFBOT
    SELFBOT = find_selfbot()
    ensure_selfbot_current(SELFBOT)     # نسخه‌ی ایمیج تازه‌تر باشد، جایگزین کن
    if os.path.isfile(SELFBOT):
        ensure_selfbot_ref(SELFBOT)     # نسخه مرجع برای بازسازی در بوت بعدی
    else:
        print(f"⚠️ فایل سلف پیدا نشد — مسیرهای جستجو: "
              f"{', '.join(selfbot_search_dirs())}", flush=True)
        print(f"   نسخه مرجع: {SELFBOT_REF} "
              f"{'(سالم است)' if os.path.isfile(SELFBOT_REF) else '(یافت نشد)'}",
              flush=True)
    try:
        maybe_migrate_to_data_dir()
    except Exception:
        pass
    try:
        print(f"  {build_stamp()}", flush=True)
        print(f"  📂 داده: {os.path.abspath(BASE_DIR)}  ·  کد: {image_dir()}",
              flush=True)
    except Exception:
        pass
    # نگهبانِ سکوت: thread جدا، چون اگر خودِ حلقه‌ی asyncio قفل شود هیچ
    # coroutine‌ای برای تشخیصِ آن اجرا نمی‌شود. تا LIVE["ready"] نشود کاری
    # نمی‌کند (بوتِ اولیه نباید «سکوت» شمرده شود).
    try:
        threading.Thread(target=silence_watch, args=(BASE_DIR,),
                         name="jafj-silence-watch", daemon=True).start()
    except Exception as e:
        print(f"  ⚠️ نگهبانِ سکوت بالا نیامد: {type(e).__name__}", flush=True)
    m = Manager()
    try:
        return asyncio.run(m.run())
    except KeyboardInterrupt:
        print("\nدر حال خاموش کردن سرویس‌ها…")
        try:
            m._flush_durable("خاموشیِ دستی", timeout=40, force=True)
        except Exception:
            pass
        m.sup.shutdown()
        release_lock()
        return 0
    except BaseException as e:
        # هر مرگِ غیرمنتظره: دلیلش را ثبت کن و قبل از مردن یک نسخه‌ی بیرونی
        # بگیر. اگر همین‌جا هم شکست بخورد، ناظرِ shell (railway-start.sh)
        # بعد از خروجِ غیرصفر دوباره push می‌زند.
        try:
            log_crash("main", "".join(traceback.format_exc()))
        except Exception:
            pass
        print(f"\n⛔ ربات با خطا ایستاد: {type(e).__name__}: {e}", flush=True)
        try:
            m._flushed_on_exit = True     # atexit دوباره تلاش نکند
            m._flush_durable("کرشِ ربات", timeout=45, force=True)
        except Exception:
            pass
        raise
    finally:
        try:
            m.sup.shutdown()
        except Exception:
            pass
        release_lock()


def _boot_guard():
    """اگر بوتِ قبلی خراب بوده، علتش را در خروجی نگه دار (برای /diag)."""
    try:
        ex = last_exit_info()
        if ex and int(ex.get("code") or 0) != 0:
            print(f"  ⚠️ بوتِ قبلی با کد {ex.get('code')} تمام شد "
                  f"(بعد از {int(ex.get('uptime') or 0)}s) — /diag را ببین",
                  flush=True)
    except Exception:
        pass


if __name__ == "__main__":
    _boot_guard()
    _rc = main()
    # روی میزبان، دیدنِ این خط یعنی سرویس مرده است. دلیلش چند خط بالاتر
    # نوشته شده؛ بدونِ این خط، لاگ با یک «Exit code 0» بی‌توضیح تمام می‌شد
    # و معلوم نبود پروسه چرا پایین آمد.
    print(f"  ⏹ خروجِ پروسه با کد {_rc}"
          + (" (خاموشیِ درخواستی)" if _rc == 0 else " — دلیلش چند خط بالاتر است"),
          flush=True)
    sys.exit(_rc)
