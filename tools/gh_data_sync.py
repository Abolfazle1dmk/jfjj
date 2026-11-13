#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""همگام‌سازی اطلاعات مشتری‌ها با گیت‌هاب — فقط stdlib.

ایده خیلی ساده: یک فایل zip داخل یک ریپوی *خصوصی* گیت‌هاب.

    pull  ← قبل از استارتِ manager: فایل zip را از گیت‌هاب بگیر و اطلاعات
            مشتری‌ها را برگردان (دیپلوی → wipe → بازیابی خودکار).
    push  → داده‌های مشتری را جمع کن و در همان فایل zip در گیت‌هاب ذخیره کن.
    loop  → push دوره‌ای (پیش‌فرض هر ۳۰ دقیقه) + یک «ذخیره‌ی پایانی» هنگام
            SIGTERM (آخرین ذخیره قبل از خاموشی/دیپلوی بعدی).

متغیرهای محیطی:
    DATA_DIR                   پوشه‌ی داده (مثل manager_82.py؛ پیش‌فرض «.»)
    DATA_GITHUB_TOKEN          توکن گیت‌هاب (الزامی) با دسترسی Contents: Read/Write
    DATA_GITHUB_REPO           پیش‌فرض: djskkskw/jfjj-data
    DATA_GITHUB_PATH           پیش‌فرض: data/customer_data.zip
    DATA_GITHUB_BRANCH         پیش‌فرض: main
    DATA_GITHUB_API            پیش‌فرض: https://api.github.com (فقط برای تست)
    DATA_GITHUB_INTERVAL_MIN   پیش‌فرض: 30 (دقیقه)

نکته‌ی امنیتی: این فایل zip حاوی شماره و سشن مشتری‌هاست و باید فقط در ریپوی
خصوصی برود — هرگز در ریپوی public کد نریزید.
"""
from __future__ import annotations

import base64
import hashlib
import io
import json
import os
import shutil
import signal
import sqlite3
import sys
import tempfile
import time
import urllib.error
import urllib.parse
import urllib.request
import zipfile

BUNDLE_FORMAT = 1
MANIFEST_NAME = "manifest.json"

# فهرست «اطلاعات مشتری» که باید بعد از دیپلوی زنده بماند — همان فهرستِ
# backup/restore خودِ manager_82.py.
TOP_FILES = (
    "manager.db",
    "shop.db",
    "manager_config.json",
    "manager_bot.string",
    "jafj_ai.json",
    ".jafj_deploy_id",
    # آدرسِ «تک‌پیامِ» پشتیبان در تلگرام. ربات‌ها `messages.getHistory` ندارند،
    # پس اگر این اشاره‌گر با دیسک پاک شود، پیامِ پشتیبان عملاً گم می‌شود
    # («پشتیبان پیدا نشد»). با سینکِ گیت‌هاب، اشاره‌گر قبل از بوت برمی‌گردد.
    ".jafj_backup_meta",
    ".jafj_backup_fp",
    # خودِ آخرین zip: اگر تلگرام در دسترس نباشد، بازیابی از همین کپی محلی
    # انجام می‌شود — یعنی داده حتی بدون دیسک هم از دست نمی‌رود.
    "jafj_backup_latest.zip",
)
TOP_DIRS = (
    "clients",
    # تاریخچه‌ی خودِ کانفیگ (manager_82.py قبل از هر تغییرِ بخش‌ها یک نسخه
    # می‌گذارد) — اگر روزی بخش‌ها پریدند، از همین‌ها برمی‌گردند.
    "config_history",
)

# فایل‌هایی که هرگز به بسته نمی‌روند (لاگ و فایل‌های موقت sqlite/telethon).
EXCLUDE_NAMES = {"run.log"}
EXCLUDE_SUFFIXES = (".log", "-journal", "-wal", "-shm", ".tmp", ".bad")

SENSITIVE_SUFFIXES = (".session", ".string", ".db")
SENSITIVE_NAMES = {"jafj_creds.json", "manager_config.json"}


def log(msg):
    print("[gh_data_sync] %s" % msg, flush=True)


def data_dir():
    return os.path.abspath(os.environ.get("DATA_DIR") or os.getcwd())


def cfg():
    token = (os.environ.get("DATA_GITHUB_TOKEN") or "").strip()
    if not token:
        raise SystemExit(
            "[gh_data_sync] DATA_GITHUB_TOKEN تنظیم نیست — برای ذخیره/بازیابی "
            "در گیت‌هاب لازم است (به README نگاه کن)")
    return {
        "token": token,
        "repo": (os.environ.get("DATA_GITHUB_REPO") or "djskkskw/jfjj-data").strip(),
        "path": (os.environ.get("DATA_GITHUB_PATH") or "data/customer_data.zip").strip().lstrip("/"),
        "branch": (os.environ.get("DATA_GITHUB_BRANCH") or "main").strip(),
        "api": (os.environ.get("DATA_GITHUB_API") or "https://api.github.com").strip().rstrip("/"),
        "interval": _interval_min(),
    }


def _interval_min():
    raw = (os.environ.get("DATA_GITHUB_INTERVAL_MIN") or "30").strip()
    try:
        val = float(raw)
    except ValueError:
        val = 30.0
    return max(0.02, val) * 60.0


def _included(rel):
    base = os.path.basename(rel)
    if base in EXCLUDE_NAMES:
        return False
    for suf in EXCLUDE_SUFFIXES:
        if base.endswith(suf):
            return False
    return True


def _chmod_private(path):
    try:
        os.chmod(path, 0o600)
    except OSError:
        pass


def _sqlite_snapshot(src, dst):
    """کپیِ سازگار از sqlite حتی وسط نوشتن (api backup داخلی)."""
    try:
        s = sqlite3.connect(src)
        try:
            d = sqlite3.connect(dst)
            try:
                s.backup(d)
            finally:
                d.close()
        finally:
            s.close()
        return
    except Exception:
        # دیتابیس خراب/غیر-sqlite → کپی معمولی بهتر از حذف است
        shutil.copy2(src, dst)


def collect(staging):
    """فایل‌های اطلاعات مشتری را در staging کپی کن؛ فهرست [{path,size,sha256}]."""
    root = data_dir()
    picked = []

    def add(rel, src):
        if not _included(rel):
            return
        dst = os.path.join(staging, rel)
        os.makedirs(os.path.dirname(dst), exist_ok=True)
        if rel.endswith(".db"):
            _sqlite_snapshot(src, dst)
        else:
            shutil.copy2(src, dst)
        with open(dst, "rb") as fh:
            digest = hashlib.sha256(fh.read()).hexdigest()
        picked.append({
            "path": rel.replace(os.sep, "/"),
            "size": os.path.getsize(dst),
            "sha256": digest,
        })

    for name in TOP_FILES:
        src = os.path.join(root, name)
        if os.path.isfile(src):
            add(name, src)
    for dname in TOP_DIRS:
        base = os.path.join(root, dname)
        if not os.path.isdir(base):
            continue
        for cur, dirs, files in os.walk(base):
            dirs.sort()
            for fn in sorted(files):
                src = os.path.join(cur, fn)
                rel = os.path.relpath(src, root).replace(os.sep, "/")
                add(rel, src)
    picked.sort(key=lambda r: r["path"])
    return picked


def fingerprint(files):
    h = hashlib.sha256()
    for rec in files:
        h.update(("%s\t%s\n" % (rec["path"], rec["sha256"])).encode("utf-8"))
    return h.hexdigest()


def _deploy_id():
    try:
        with open(os.path.join(data_dir(), ".jafj_deploy_id"), encoding="utf-8") as fh:
            return fh.read().strip()[:32]
    except OSError:
        return ""


def build_bundle(skip_fingerprint=None):
    """Snapshot and fingerprint first; omit compression if already remote."""
    staging = tempfile.mkdtemp(prefix=".gh_sync_stage_", dir=data_dir())
    try:
        files = collect(staging)
        manifest = {
            "format": BUNDLE_FORMAT,
            "tool": "gh_data_sync",
            "created_at": time.strftime("%Y-%m-%dT%H:%M:%SZ", time.gmtime()),
            "deploy_id": _deploy_id(),
            "files": files,
            "fingerprint": fingerprint(files),
        }
        if files and skip_fingerprint and manifest["fingerprint"] == skip_fingerprint:
            return None, manifest
        with open(os.path.join(staging, MANIFEST_NAME), "w", encoding="utf-8") as fh:
            json.dump(manifest, fh, ensure_ascii=False, indent=1)
        out = os.path.join(data_dir(), ".gh_sync_bundle.zip")
        with zipfile.ZipFile(out, "w", zipfile.ZIP_DEFLATED) as zf:
            zf.write(os.path.join(staging, MANIFEST_NAME), MANIFEST_NAME)
            for rec in files:
                zf.write(os.path.join(staging, rec["path"]), rec["path"])
        with open(out, "rb") as fh:
            blob = fh.read()
        return blob, manifest
    finally:
        shutil.rmtree(staging, ignore_errors=True)
        try:
            os.remove(os.path.join(data_dir(), ".gh_sync_bundle.zip"))
        except OSError:
            pass


# ── GitHub Contents API با urllib (بدون هیچ وابستگی) ──────────────────────────

def api_call(c, method, path, body=None):
    url = "%s%s" % (c["api"], path)
    data = None
    if body is not None:
        data = json.dumps(body).encode("utf-8")
    req = urllib.request.Request(url, data=data, method=method)
    req.add_header("Authorization", "Bearer %s" % c["token"])
    req.add_header("Accept", "application/vnd.github+json")
    req.add_header("X-GitHub-Api-Version", "2022-11-28")
    req.add_header("User-Agent", "jafj-gh-data-sync")
    if data is not None:
        req.add_header("Content-Type", "application/json")
    try:
        with urllib.request.urlopen(req, timeout=60) as resp:
            raw = resp.read()
            return resp.status, (json.loads(raw) if raw else {})
    except urllib.error.HTTPError as e:
        raw = e.read()
        try:
            parsed = json.loads(raw) if raw else {}
        except ValueError:
            parsed = {"message": raw[:200].decode("utf-8", "replace")}
        return e.code, parsed


def _contents_url(c, with_ref=False):
    quoted = "/".join(urllib.parse.quote(seg) for seg in c["path"].split("/"))
    url = "/repos/%s/contents/%s" % (c["repo"], quoted)
    if with_ref:
        url += "?ref=" + urllib.parse.quote(c["branch"])
    return url


def get_remote(c):
    """(بایت‌ها، sha) یا None اگر پشتیبانی هنوز ساخته نشده."""
    status, body = api_call(c, "GET", _contents_url(c, with_ref=True))
    if status == 404:
        return None
    if status != 200:
        raise RuntimeError("GET contents → HTTP %s: %s"
                           % (status, body.get("message", "")))
    content = body.get("content") or ""
    blob = base64.b64decode("".join(content.split()))
    return blob, body.get("sha", "")


def put_remote(c, blob, sha, message):
    """آپلود فایل؛ 409/422 (sha کهنه) → چند بار با sha تازه تلاش مجدد."""
    last = None
    for attempt in range(4):
        body = {
            "message": message,
            "content": base64.b64encode(blob).decode("ascii"),
            "branch": c["branch"],
        }
        if sha:
            body["sha"] = sha
        status, resp = api_call(c, "PUT", _contents_url(c), body)
        if status in (200, 201):
            return
        if status in (409, 422):
            last = "HTTP %s: %s" % (status, resp.get("message", ""))
            fresh = get_remote(c)      # sha تازه بگیر
            sha = fresh[1] if fresh else None
            log("تلاقی نسخه (%s) — تلاش دوباره با sha تازه (%d)" % (status, attempt + 1))
            time.sleep(1 + attempt)
            continue
        raise RuntimeError("PUT contents → HTTP %s: %s"
                           % (status, resp.get("message", "")))
    raise RuntimeError("PUT contents بعد از چند تلاش: %s" % last)


# ── ادغامِ manager_config.json هنگامِ بازیابی ─────────────────────────────────
# چرا: pull قبل از هر بوت، فایل‌ها را «کور» جایگزین می‌کند. اگر آخرین pushِ
# موفق برای چند ساعت/چند روز پیش باشد (خطای شبکه، توکن، کشتنِ سختِ کانتینر،
# یا دو نمونه‌ی همزمان که یکی‌شان کانفیگِ تهی دارد) و در این فاصله مدیر
# بخش‌های آموزش را ثبت کرده باشد، همان دیپلوی/ری‌استارت همه‌ی بخش‌ها را
# برمی‌گرداند به نسخه‌ی قدیمی — یعنی «همه‌ی آموزش‌ها پرید».
#
# دو قاعده:
#   1) اگر کانفیگِ محلی از بسته <b>تازه‌تر</b> است (mtime > created_atِ بسته)،
#      دست نمی‌خورد؛ پس تغییرِ عمدیِ مدیر (حتی پاک‌کردنِ یک بخش) له نمی‌شود.
#   2) وگرنه (محلی قدیمی یا اصلاً نیست) کلیدبه‌کلید ادغام می‌شود و برای
#      کلیدهای محتوایی، هر طرف <b>پُرتر</b> است می‌ماند — هیچ‌وقت داده‌ی
#      بیشتر با داده‌ی کمترِ کهنه جایگزین نمی‌شود.
CONFIG_REL = "manager_config.json"
# کلیدهایی که «هر طرف بلندتر/پُرتر بود، همان بماند» — یعنی هیچ‌وقت متن/لیستِ
# پُرترِ محلی با نسخه‌ی کهنه‌ی بسته جایگزین نمی‌شود (قابلیت‌های دستیِ مدیر:
# «📋 دستورات آماده»، متن‌های ربات، شماره‌کارت، سلام‌ها و…).
LONGER_LIST_KEYS = ("tut_ids", "sample_ids", "admin_ids", "cmd_items")
# هر «متنِ» که مدیر دستی ثبت کرده: اگر یک طرف پُرتر بود، همان بماند.
LONGER_TEXT_KEYS = (
    "rules_text", "welcome", "hub_intro", "rt_text",
    "cmd_intro", "sold_text", "expired_text", "help_text", "support_text",
    "contact", "pay_note", "card_number", "card_name",
    "greet_morning", "greet_noon", "greet_evening", "greet_night",
)
# کلیدهای paired: لیست + چتِ منبعش از <b>یک</b> طرف می‌آیند تا قاطی نشوند
PAIRED_KEYS = {"tut_ids": "tut_chat", "sample_ids": "sample_chat"}
# شماره‌چینه‌ی بسته برای مقایسه با mtime محلی
_TIME_FMT = "%Y-%m-%dT%H:%M:%SZ"


def _days_from_civil(y, m, d):
    """شمارِ روزها از ۱۹۷۰/۱/۱ برای تاریخِ میلادی (بدونِ نیاز به datetime)."""
    y -= m <= 2
    era = (y if y >= 0 else y - 399) // 400
    yoe = y - era * 400
    doy = (153 * (m + (-3 if m > 2 else 9)) + 2) // 5 + d - 1
    doe = yoe * 365 + yoe // 4 - yoe // 100 + doy
    return era * 146097 + doe - 719468


def _parse_bundle_time(value):
    """«زمانِ ساختِ بسته» (ISO/UTC) را به ثانیه‌ی epoch برمی‌گرداند.

    عمداً بدون ``calendar``/``datetime`` نوشته شده تا وابستگی‌های این ابزار
    همان لیستِ کوچکِ stdlib بماند (تستِ test_gh_data_sync این را می‌پاید).
    خروجی‌اش با ``calendar.timegm`` یکی است؛ اگر نشود پارس کرد صفر
    برمی‌گرداند تا مقایسه با mtime محلی به‌سمتِ «محلی تازه‌تر است» نرود
    (صفر یعنی بسته خیلی قدیمی فرض می‌شود ⇒ merge انجام می‌شود که رفتارِ
    امنِ قبلی است).
    """
    try:
        st = time.strptime(str(value).strip(), _TIME_FMT)
    except Exception:
        return 0
    try:
        return (_days_from_civil(st.tm_year, st.tm_mon, st.tm_mday) * 86400
                + st.tm_hour * 3600 + st.tm_min * 60 + st.tm_sec)
    except Exception:
        return 0


def _richness(key, val):
    if isinstance(val, list):
        return len(val)
    if isinstance(val, str):
        return len(val.strip())
    if isinstance(val, dict):
        return len(val)
    return 0 if val in (None, "", 0, False) else 1


def merge_config(bundle_cfg, local_cfg):
    """(کانفیگِ ادغام‌شده, فهرستِ کلیدهایی که از نسخه‌ی محلیِ پُرتر نگه داشتیم)."""
    kept = []
    if not isinstance(bundle_cfg, dict) or not isinstance(local_cfg, dict):
        return (local_cfg if isinstance(local_cfg, dict) else bundle_cfg), kept
    out = dict(bundle_cfg)
    out.update(local_cfg)          # پایه: محلی (تازه‌تر) برنده است
    for key in ("tut_sections",) + LONGER_LIST_KEYS + LONGER_TEXT_KEYS:
        b, l = bundle_cfg.get(key), local_cfg.get(key)
        if key not in bundle_cfg or key not in local_cfg:
            continue
        if _richness(key, b) > _richness(key, l):
            out[key] = b
            kept.append(key)
            pair = PAIRED_KEYS.get(key)
            if pair and pair in bundle_cfg:
                out[pair] = bundle_cfg[pair]
    return out, kept


def _write_config(path, data):
    tmp = path + ".ghnew"
    with open(tmp, "w", encoding="utf-8") as fh:
        json.dump(data, fh, ensure_ascii=False, indent=2)
    os.replace(tmp, path)
    _chmod_private(path)


def _manifest_of(blob):
    try:
        with zipfile.ZipFile(io.BytesIO(blob)) as zf:
            with zf.open(MANIFEST_NAME) as fh:
                return json.loads(fh.read().decode("utf-8"))
    except Exception:
        return None


def cmd_push(quiet=False):
    c = cfg()
    remote = get_remote(c)
    rmanifest = _manifest_of(remote[0]) if remote else None
    blob, manifest = build_bundle(
        skip_fingerprint=rmanifest.get("fingerprint") if rmanifest else None)
    if not manifest["files"]:
        if remote:
            log("داده‌ی محلی خالی است — پشتیبان گیت‌هاب دست نخورد")
            return 1
        log("چیزی برای ذخیره نیست")
        return 0
    if blob is None:
        log("بدون تغییر — ذخیره‌ی جدید لازم نیست")
        return 0
    if len(blob) > 90 * 1024 * 1024:
        log("بسته خیلی بزرگ است (%d MB) — از سقف Contents API می‌گذرد" % (len(blob) // (1024 * 1024)))
        return 1
    msg = "data sync: %s (%d file%s)" % (
        manifest["created_at"], len(manifest["files"]),
        "s" if len(manifest["files"]) != 1 else "")
    put_remote(c, blob, remote[1] if remote else None, msg)
    log("ذخیره شد: %s (%d فایل، %d بایت)" % (c["path"], len(manifest["files"]), len(blob)))
    return 0


def _safe_member(name):
    if name.startswith("/") or name.startswith("\\") or ".." in name.split("/"):
        return False
    return True


def cmd_pull():
    c = cfg()
    root = data_dir()
    os.makedirs(root, exist_ok=True)
    remote = get_remote(c)
    if remote is None:
        log("هنوز پشتیبانی در گیت‌هاب نیست (%s) — اولین اجرا؛ با داده‌ی فعلی ادامه می‌دهیم"
            % c["path"])
        return 0
    blob = remote[0]
    staging = tempfile.mkdtemp(prefix=".gh_sync_rest_", dir=root)
    try:
        try:
            with zipfile.ZipFile(io.BytesIO(blob)) as zf:
                for member in zf.namelist():
                    if not _safe_member(member):
                        raise ValueError("نام نامعتبر در zip: %r" % member)
                zf.extractall(staging)
        except zipfile.BadZipFile:
            log("فایل پشتیبان خراب است — با داده‌ی فعلی ادامه می‌دهیم")
            return 1
        mpath = os.path.join(staging, MANIFEST_NAME)
        if not os.path.isfile(mpath):
            log("manifest در بسته نیست — با داده‌ی فعلی ادامه می‌دهیم")
            return 1
        with open(mpath, encoding="utf-8") as fh:
            manifest = json.load(fh)
        if manifest.get("format") != BUNDLE_FORMAT:
            log("قالب ناشناخته‌ی بسته (%r) — با داده‌ی فعلی ادامه می‌دهیم"
                % manifest.get("format"))
            return 1
        created = _parse_bundle_time(manifest.get("created_at"))
        n = 0
        for rec in manifest.get("files", []):
            rel = rec.get("path", "")
            if not rel or not _safe_member(rel):
                continue
            src = os.path.join(staging, rel)
            if not os.path.isfile(src):
                continue
            dst = os.path.join(root, rel)
            os.makedirs(os.path.dirname(dst) or root, exist_ok=True)
            if rel == CONFIG_REL and os.path.isfile(dst):
                # کانفیگِ محلی تازه‌تر از بسته → دست نمی‌خورد (تغییرِ عمدیِ
                # مدیر، از جمله پاک‌کردنِ یک بخش، له نمی‌شود).
                try:
                    if created and os.path.getmtime(dst) > created:
                        log("%s: نسخه‌ی محلی تازه‌تر است — دست نخورد" % rel)
                        n += 1
                        continue
                except OSError:
                    pass
                try:
                    with open(src, encoding="utf-8") as fh:
                        bundle_cfg = json.load(fh)
                    with open(dst, encoding="utf-8") as fh:
                        local_cfg = json.load(fh)
                    merged, kept = merge_config(bundle_cfg, local_cfg)
                    if kept:
                        log("%s: ادغام شد — کلیدهای پُرترِ محلی نگه داشته شد: %s"
                            % (rel, ", ".join(kept)))
                    if merged == local_cfg:
                        n += 1
                        continue
                    _write_config(dst, merged)
                    n += 1
                    continue
                except Exception as e:
                    log("%s: ادغام نشد (%s) — همان نسخه‌ی بسته می‌نشیند"
                        % (rel, e))
            tmp = dst + ".ghnew"
            shutil.copy2(src, tmp)          # اول به فایل موقت کنار مقصد
            os.replace(tmp, dst)            # بعد جایگزینی اتمیک
            _chmod_private(dst)
            n += 1
        log("بازیابی شد: %d فایل از %s (ساخته‌شده %s)"
            % (n, c["repo"], manifest.get("created_at", "?")))
        return 0
    finally:
        shutil.rmtree(staging, ignore_errors=True)


def _try_push(tag):
    try:
        rc = cmd_push()
        log("%s: %s" % (tag, "انجام شد" if rc == 0 else "ناموفق"))
    except Exception as e:
        log("%s: خطا — %s" % (tag, e))


def cmd_loop():
    stop = {"v": False}

    def _sig(signum, frame):
        stop["v"] = True

    signal.signal(signal.SIGTERM, _sig)
    signal.signal(signal.SIGINT, _sig)
    interval = cfg()["interval"]
    log("loop شروع شد — هر %.0f دقیقه + ذخیره‌ی پایانی هنگام خاموشی" % (interval / 60.0))
    first = True
    while True:
        if not first:
            deadline = time.time() + interval
            while time.time() < deadline and not stop["v"]:
                time.sleep(min(2.0, max(0.1, deadline - time.time())))
        first = False
        if stop["v"]:
            _try_push("ذخیره‌ی پایانی")
            log("loop تمام شد")
            return 0
        _try_push("push دوره‌ای")


def main(argv):
    if len(argv) < 2 or argv[1] not in ("pull", "push", "loop"):
        print(__doc__)
        return 2
    cmd = argv[1]
    if cmd == "pull":
        return cmd_pull()
    if cmd == "push":
        return cmd_push()
    return cmd_loop()


if __name__ == "__main__":
    sys.exit(main(sys.argv))
