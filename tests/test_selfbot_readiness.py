#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""«ربات می‌گوید سلف روشن شد، ولی در Saved Messages هیچ پیامی نمی‌آید.»

ریشه‌ی گزارش: مدیر فقط `Popen` را می‌دید و می‌گفت «روشن شد (pid …)».
پروسه می‌تواند زنده باشد و در همان حال:

  • با اکانتِ **دیگری** وصل شود (سشنِ پوشه به اکانتِ دیگر تعلق دارد) →
    پیام‌های پنل به اکانتِ دیگر می‌رود و کاربر در Saved Messages خودش
    هیچ چیزی نمی‌بیند؛
  • هنوز به پنل نرسیده باشد (در حال اتصال/تلاشِ دوباره)؛
  • فایلِ سلف باشد ولی ناقص/خالی/نسخه‌ی دیگر، پس اجرا نشود.

این تست همان سه حالت را روی شاهدِ واقعی (`jafj_status.json` و `run.log`)
قفل می‌کند و مطمئن می‌شود پیامِ شکست برای حالتِ «اکانتِ اشتباه» هم متنِ
راهنما دارد.

اجرا: `python3 tests/test_selfbot_readiness.py` → `ALL PASS`
"""
import os
import sys
import tempfile
import time
from pathlib import Path

HERE = Path(__file__).resolve().parent
REPO = HERE.parent
FAILS = []


def check(name, cond, extra=""):
    print(("PASS " if cond else "FAIL ") + name
          + (f"   [{extra}]" if extra and not cond else ""))
    if not cond:
        FAILS.append(name)


def main():
    root = Path(tempfile.mkdtemp(prefix="jafj_ready_"))
    os.environ["DATA_DIR"] = str(root / "data")
    os.environ["PORT"] = "8291"
    os.environ.pop("JAFJ_ONLY", None)
    sys.path.insert(0, str(REPO))
    import manager_82 as M

    now = time.time()

    # ── ۱) مقایسه‌ی اکانت ────────────────────────────────────────────────
    check("account_mismatch: ناشناخته → None", M.account_mismatch(1, 0) is None)
    check("account_mismatch: یکی → False", M.account_mismatch(777, 777) is False)
    check("account_mismatch: فرق → True", M.account_mismatch(777, 888) is True)

    # ── ۲) فایلِ سالمِ سلف ───────────────────────────────────────────────
    ok_file = root / "ok_95.py"
    ok_file.write_text(
        "#!/usr/bin/env python3\n# جفج سلف\nVERSION = '3.0'\ndef main():\n"
        "    return 0\nif __name__ == '__main__':\n    sys.exit(main())\n",
        encoding="utf-8")
    bad, why = M.selfbot_file_problem(str(ok_file))
    check("فایلِ سالمِ سلف مشکلی ندارد", bad is False and why == "", why)

    empty = root / "empty_95.py"
    empty.write_text("", encoding="utf-8")
    bad, why = M.selfbot_file_problem(str(empty))
    check("فایلِ خالی «قابل اجرا نیست»", bad is True and "خالی" in why, why)

    half = root / "half_95.py"
    half.write_text("import os\nprint('نصفه'\n", encoding="utf-8")
    bad, why = M.selfbot_file_problem(str(half))
    check("فایلِ نیمه‌کاره (خطای سینتکس) رد می‌شود",
          bad is True and "سینتکس" in why, why)

    minimal = root / "minimal_95.py"
    minimal.write_text("import time\ntime.sleep(1)\n", encoding="utf-8")
    bad, why = M.selfbot_file_problem(str(minimal))
    check("فایلِ پایتونِ ساده (نسخه‌ی دیگر) بلاک نمی‌شود", bad is False, why)

    bad, why = M.selfbot_file_problem(str(root / "nope.py"))
    check("فایلِ ناموجود «پیدا نشد» می‌دهد", bad is True and "پیدا نشد" in why, why)

    # ── ۳) readiness از روی گزارشِ خودِ سلف ─────────────────────────────
    folder = root / "clients" / "555"
    folder.mkdir(parents=True, exist_ok=True)

    def status(**kw):
        import json
        d = {"ts": int(now), "pid": 1, "user_id": 555}
        d.update(kw)
        (folder / "jafj_status.json").write_text(
            json.dumps(d), encoding="utf-8")

    status()
    rd = M.selfbot_readiness(str(folder), expected_uid=555, proc_alive=True,
                             now_ts=now)
    check("گزارشِ تازه + اکانتِ درست → ready",
          rd["ready"] is True and rd["state"] == "ready", rd)

    rd = M.selfbot_readiness(str(folder), expected_uid=999, proc_alive=True,
                             now_ts=now)
    check("اکانتِ لاگین‌شده با ثبت‌شده فرق دارد → wrong_account",
          rd["ready"] is False and rd["state"] == "wrong_account", rd)
    check("پیامِ wrong_account عددِ هر دو اکانت را دارد",
          "999" in rd["why"] and "555" in rd["why"], rd["why"])

    status(ts=int(now - 3600), user_id=888)
    rd = M.selfbot_readiness(str(folder), expected_uid=555, proc_alive=True,
                             now_ts=now)
    check("گزارشِ کهنه (بیش از ۵ دقیقه) → stale",
          rd["ready"] is False and rd["state"] == "stale", rd)

    # وضعیتِ JSON ممکن است از اجرای قبلی مانده باشد: لاگِ اجرای قبلی نباید
    # آن را ready کند، اما پیامِ شروعِ اجرای فعلی باید stale را خنثی کند.
    (folder / "run.log").write_text(
        "===== start old =====\nورود انجام شد | id=555\nآنلاین شد — پنل فعال\n"
        "===== start current =====\nورود انجام شد | id=555\n",
        encoding="utf-8")
    rd = M.selfbot_readiness(str(folder), expected_uid=555, proc_alive=True,
                             now_ts=now)
    check("ready قدیمی در لاگِ اجرای قبل stale را پنهان نمی‌کند",
          rd["ready"] is False and rd["state"] == "stale", rd)
    with open(folder / "run.log", "a", encoding="utf-8") as f:
        f.write("آنلاین شد — پنل فعال\n")
    rd = M.selfbot_readiness(str(folder), expected_uid=555, proc_alive=True,
                             now_ts=now)
    check("لاگِ اجرای فعلی ready را بر stale-status اولویت می‌دهد",
          rd["ready"] is True and rd["state"] == "ready", rd)

    (folder / "jafj_status.json").unlink()
    (folder / "run.log").write_text(
        "▶️ 95.py اجرا شد | pid=9\n  ◦ بوت: ورود انجام شد | ali | id=555\n"
        "  ✅ آماده — در Saved Messages بفرست: پنل\n", encoding="utf-8")
    rd = M.selfbot_readiness(str(folder), expected_uid=555, proc_alive=True,
                             now_ts=now)
    check("بدونِ jafj_status ولی با «آماده» در لاگ → ready",
          rd["ready"] is True, rd)

    (folder / "run.log").write_text(
        "▶️ 95.py اجرا شد | pid=9\n  ◦ بوت: ورود انجام شد | other | id=888\n",
        encoding="utf-8")
    rd = M.selfbot_readiness(str(folder), expected_uid=555, proc_alive=True,
                             now_ts=now)
    check("لاگ با اکانتِ دیگر → wrong_account",
          rd["state"] == "wrong_account", rd)

    (folder / "run.log").write_text(
        "▶️ 95.py اجرا شد | pid=9\n  ◦ بوت: شروعِ اتصال به تلگرام\n",
        encoding="utf-8")
    rd = M.selfbot_readiness(str(folder), expected_uid=555, proc_alive=True,
                             now_ts=now)
    check("فقط «شروعِ اتصال» → ready=None (هنوز معلوم نیست)",
          rd["ready"] is None and rd["state"] == "starting", rd)

    rd = M.selfbot_readiness(str(folder), expected_uid=555, proc_alive=False,
                             now_ts=now)
    check("پروسه مرده و هیچ نشانه‌ای نیست → crashed",
          rd["ready"] is False and rd["state"] == "crashed", rd)

    # ── ۴) متنِ پیامِ شکست برای اکانتِ اشتباه ───────────────────────────
    txt = M.selfbot_failure_notice("acc", 555, "account",
                                   "اکانتِ دیگر", "")
    check("پیامِ account راهنمای لاگینِ دوباره دارد",
          "لاگین" in txt and "Saved Messages" in txt, txt[-200:])

    # ── ۵) Supervisor.readiness روی DB واقعی ────────────────────────────
    sup = M.Supervisor(M.Config(), M.DB())

    # `uid` در دیتابیس شناسه‌ی چت با ربات مدیر است؛ `tg_id` شناسه‌ی
    # اکانتی است که Telethon لاگین کرده. این‌ها باید متفاوت باشند تا
    # رگرسیونِ نوشتن uid به‌جای tg_id را بگیریم.
    manager_uid, telegram_uid = 123456, 987654321
    sup.db.add(manager_uid, "tester", "Tester", 0)
    sup.db.set(manager_uid, tg_id=telegram_uid)
    check("expected-account از tg_id اکانت تلگرام نوشته می‌شود",
          sup.write_expected_account(manager_uid) and
          Path(sup.folder(manager_uid), ".jafj_expected_account").read_text().strip()
          == str(telegram_uid))

    # رکوردهای قدیمی که tg_id ندارند، از رخدادِ معتبرِ لاگین backfill شوند.
    legacy_uid, legacy_tg_id = 123458, 876543210
    sup.db.add(legacy_uid, "legacy", "Legacy", 0)
    sup.db.log(legacy_uid, "login", f"tg_id={legacy_tg_id}")
    legacy_file = Path(sup.folder(legacy_uid), ".jafj_expected_account")
    check("حسابِ قدیمی: tg_id از لاگین backfill می‌شود",
          sup.write_expected_account(legacy_uid) and
          legacy_file.read_text().strip() == str(legacy_tg_id) and
          int(sup.db.get(legacy_uid).get("tg_id") or 0) == legacy_tg_id)

    # اگر سلف قدیمی هنوز زنده است ولی guard فایلش اشتباه است، start نباید
    # به «از قبل روشن است» برگردد؛ باید آن را یک‌بار برای اعمال اصلاح متوقف کند.
    repair_uid, repair_tg_id = 123459, 765432109
    sup.db.add(repair_uid, "legacy-running", "Legacy Running", 0)
    sup.db.set(repair_uid, tg_id=repair_tg_id)
    repair_path = Path(sup.folder(repair_uid), ".jafj_expected_account")
    repair_path.write_text(str(repair_uid), encoding="utf-8")
    stopped_ids = []
    real_running, real_stop, real_ram_gate = sup.is_running, sup.stop, sup._ram_gate_failure
    sup.is_running = lambda _uid: True
    sup.stop = lambda _uid: (stopped_ids.append(_uid) is None, "stopped")
    sup._ram_gate_failure = lambda _uid: (False, "test-stop-after-repair")
    try:
        repair_result = sup._start_one(repair_uid)
    finally:
        sup.is_running, sup.stop, sup._ram_gate_failure = real_running, real_stop, real_ram_gate
    check("سلفِ قدیمیِ زنده با guard کهنه برای اصلاح ری‌استارت می‌شود",
          stopped_ids == [repair_uid] and
          repair_path.read_text().strip() == str(repair_tg_id) and
          repair_result == (False, "test-stop-after-repair"))

    # بدون tg_id و بدون سابقه‌ی ورود نباید uid مدیر را جعل کند.
    manager_uid_missing = 123457
    sup.db.add(manager_uid_missing, "tester", "Tester", 0)
    check("بدون tg_id یا سابقه‌ی ورود، فایل ساخته نمی‌شود",
          not sup.write_expected_account(manager_uid_missing) and
          not Path(sup.folder(manager_uid_missing), ".jafj_expected_account").exists())

    uid = 555
    f2 = Path(sup.folder(uid))
    f2.mkdir(parents=True, exist_ok=True)
    sup.db.x("INSERT OR IGNORE INTO clients(uid,status,created_at,session,tg_id)"
             " VALUES(?,?,?,?,?)",
             (uid, "active", int(time.time()), "s" * 40, uid), None)
    import json
    (f2 / "jafj_status.json").write_text(
        json.dumps({"ts": int(time.time()), "user_id": uid}), encoding="utf-8")
    rd = sup.readiness(uid, proc_alive=True)
    check("Supervisor.readiness اکانت را از DB می‌خواند",
          rd["ready"] is True and rd["state"] == "ready", rd)

    print()
    if FAILS:
        print("FAILED:", ", ".join(FAILS))
        return 1
    print("ALL PASS")
    return 0


if __name__ == "__main__":
    sys.exit(main())
