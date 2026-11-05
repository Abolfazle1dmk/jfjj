#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""نگهبانِ حافظه — «خیلی رم می‌خوری؟»

هر سلف (telethon + asyncio + sqlite) حدودِ ۶۰-۹۰ مگابایت است (اندازه‌گیریِ
واقعی: importِ telethon به‌تنهایی ۴۷MB). با ۶ سلف روی یک پلنِ کم‌حافظه،
کرنل کلِ کانتینر را OOM می‌کند و **همه** سرویس‌ها می‌افتند؛ کاربر فقط
«سرور آفلاین شد» می‌بیند.

این تست نگهبان را قفل می‌کند: با حافظه‌ی کم، سلفِ تازه بالا نمی‌آید، دلیلش
در لاگ نوشته می‌شود، سشن قرنطینه نمی‌شود و امتیازی کسر نمی‌شود.
"""
import importlib.util
import os
import sys
import tempfile
import threading
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
    root = Path(tempfile.mkdtemp(prefix="jafj_ram_"))
    here = os.getcwd()
    saved = {k: os.environ.get(k) for k in
             ("DATA_DIR", "PORT", "JAFJ_ONLY", "JAFJ_MIN_FREE_MB",
              "JAFJ_RESUME_DELAY")}
    os.environ["DATA_DIR"] = str(root / "data")
    os.environ["PORT"] = "8533"
    os.environ.pop("JAFJ_ONLY", None)
    os.environ.pop("JAFJ_MIN_FREE_MB", None)
    os.environ["JAFJ_RESUME_DELAY"] = "0"
    try:
        sys.path.insert(0, str(REPO))
        import manager_82 as M

        # ── ۱) تنظیمِ حد ───────────────────────────────────────────────
        check("ram_gate: پیش‌فرض ۱۵۰ مگابایت", M.ram_gate_mb({}) == 150.0,
              M.ram_gate_mb({}))
        check("ram_gate: مقدارِ دلخواه", M.ram_gate_mb({"JAFJ_MIN_FREE_MB": "120"}) == 120.0)
        check("ram_gate: صفر = بی‌نگهبان", M.ram_gate_mb({"JAFJ_MIN_FREE_MB": "0"}) == 0.0)
        check("ram_gate: مقدارِ خراب → پیش‌فرض",
              M.ram_gate_mb({"JAFJ_MIN_FREE_MB": "abc"}) == 150.0)
        check("ram_gate: منفی → صفر", M.ram_gate_mb({"JAFJ_MIN_FREE_MB": "-5"}) == 0.0)
        check("ram_gate: سقف دارد", M.ram_gate_mb({"JAFJ_MIN_FREE_MB": "99999"}) == 8192.0)

        # ── ۲) بررسی با حافظه‌ی ساختگی ────────────────────────────────
        orig_mem = M.mem_available_mb
        M.mem_available_mb = lambda: 20
        ok, free, limit = M.ram_gate_check({})
        check("ram_gate_check: با ۲۰MB آزاد اجازه نمی‌دهد", ok is False, (ok, free))
        check("ram_gate_check: حافظه و حد را برمی‌گرداند",
              free == 20.0 and limit == 150.0, (free, limit))
        M.mem_available_mb = lambda: 100
        ok100, free100, limit100 = M.ram_gate_check({})
        check("ram_gate_check: با ۱۰۰MB آزاد زیرِ حاشیه‌ی امن است",
              ok100 is False and free100 == 100 and limit100 == 150,
              (ok100, free100, limit100))
        M.mem_available_mb = lambda: 160
        ok160, free160, limit160 = M.ram_gate_check({})
        check("ram_gate_check: با ۱۶۰MB آزاد از حاشیه عبور می‌کند",
              ok160 is True and free160 == 160 and limit160 == 150,
              (ok160, free160, limit160))
        ok0, _, _ = M.ram_gate_check({"JAFJ_MIN_FREE_MB": "0"})
        check("ram_gate_check: با حدِ صفر همیشه اجازه می‌دهد", ok0 is True)
        M.mem_available_mb = lambda: 500
        ok5, free5, _ = M.ram_gate_check({})
        check("ram_gate_check: با ۵۰۰MB آزاد اجازه می‌دهد", ok5 is True, free5)

        # ── ۳) start() با حافظه‌ی کم: بالا نیامدن + دلیلِ روشن ────────
        sup = M.Supervisor(M.Config(), M.DB())
        uid = 999000111
        folder = Path(sup.folder(uid))
        folder.mkdir(parents=True, exist_ok=True)
        (folder / "jafj.session").write_bytes(b"session")
        (folder / "jafj_creds.json").write_text("{}", encoding="utf-8")
        sup.db.x("INSERT OR IGNORE INTO clients(uid, status, created_at, session)"
                 " VALUES(?,?,?,?)", (uid, "active", int(time.time()), "s" * 40), None)
        sup.db.set(uid, want_on=1, need_login=0)
        sup._session_ok_or_mark = lambda u: (True, "")
        sup.sync_selfbot = lambda u: (True, "")

        fake = root / "fake_self.py"
        fake.write_text("import time\ntime.sleep(30)\n", encoding="utf-8")
        old_self = M.SELFBOT
        M.SELFBOT = str(fake)
        M.mem_available_mb = lambda: 15
        ok_ram, msg = sup.start(uid)
        M.mem_available_mb = orig_mem
        check("start با RAMِ کم → False", ok_ram is False)
        check("start با RAMِ کم → پیام «حافظه» دارد", "حافظه" in msg, msg[:200])
        check("start با RAMِ کم → پلنِ بالا/خاموش‌کردن را پیشنهاد می‌دهد",
              "پلن" in msg and "JAFJ_MIN_FREE_MB=0" in msg, msg[:250])
        check("start با RAMِ کم → پروسه‌ای ساخته نشد", uid not in sup.procs)
        check("start با RAMِ کم → نوعِ manager (امتیاز کسر نمی‌شود)",
              sup.last_failure.get(uid) == "manager", sup.last_failure.get(uid))
        check("start با RAMِ کم → سشن قرنطینه نشد",
              (folder / "jafj.session").exists())
        check("start با RAMِ کم → نیاز به لاگین علامت نمی‌خورد",
              not (sup.db.get(uid) or {}).get("need_login"))

        # ── ۴) با حافظه‌ی کافی، همان اکانت بالا می‌آید ────────────────
        M.mem_available_mb = lambda: 800
        ok_ok, msg2 = sup.start(uid)
        M.mem_available_mb = orig_mem
        M.SELFBOT = old_self
        check("start با RAMِ کافی → اجرا شد", ok_ok is True, msg2[:200])
        check("start با RAMِ کافی → پروسه ثبت شد", uid in sup.procs)
        try:
            sup.stop(uid)
        except Exception:
            pass

        # شروع‌ها از بوت‌ترد و هندلرهای کاربر ممکن است هم‌زمان برسند؛
        # چکِ RAM باید با خودِ ساختِ سلف سریال شود.
        active = [0]
        peak = [0]
        active_lock = threading.Lock()
        original_start_one = sup._start_one
        def fake_start_one(_uid):
            with active_lock:
                active[0] += 1
                peak[0] = max(peak[0], active[0])
            time.sleep(0.05)
            with active_lock:
                active[0] -= 1
            return True, "fake"
        sup._start_one = fake_start_one
        threads = [threading.Thread(target=sup.start, args=(1000 + i,))
                   for i in range(6)]
        for thread in threads:
            thread.start()
        for thread in threads:
            thread.join()
        sup._start_one = original_start_one
        check("start: شش درخواست هم‌زمان سریال می‌شوند", peak[0] == 1, peak[0])

        # ── ۴ب) اندازه‌گیریِ واقعیِ مصرفِ هر سلف ──────────────────────
        me = M.proc_rss_mb(os.getpid())
        # ── ظرفیتِ تخمینی (چند سلف روی این پلن) ──────────────────────
        n, per, free = M.capacity_estimate(free_mb=1024, mode="fork")
        check("ظرفیت: fork → هر اکانت ۱۲MB", per == 12, per)
        usable = 1024 - M.RAM_RESERVE_MB - M.MANAGER_MB
        check("ظرفیت: fork = ۱ + (بودجه−پایه)/۱۲",
              n == int(1 + (usable - M.PROC_BASE_MB["fork"]) // 12), n)
        check("ظرفیت: shard روی ۵۱۲MB بیشتر از fork جا می‌دهد",
              M.capacity_estimate(free_mb=512, mode="shard")[0]
              > M.capacity_estimate(free_mb=512, mode="fork")[0])
        # پروفایل: هر پروسه ۶۷MB — شاردهای کوچکِ زیاد گران‌ترند
        small = M.capacity_estimate(free_mb=1024, mode="shard", size=4)[0]
        big = M.capacity_estimate(free_mb=1024, mode="shard", size=32)[0]
        check("ظرفیت: شاردِ بزرگ‌تر → اکانتِ بیشتر", big > small, (small, big))
        n2, per2, _ = M.capacity_estimate(free_mb=1024, mode="process")
        check("ظرفیت: process → هر سلف ۶۲MB", per2 == 62, per2)
        check("ظرفیت: حالتِ process کمتر جا می‌دهد", n2 < n, (n, n2))
        n3, _, _ = M.capacity_estimate(free_mb=50, mode="fork")
        check("ظرفیت: حافظه‌ی کم → صفر (نه عددِ منفی)", n3 == 0, n3)
        nS, perS, _ = M.capacity_estimate(free_mb=1024, mode="shard")
        check("ظرفیت: shard → هر اکانت ۳MB", perS == 3, perS)
        check("ظرفیت: shard از fork بیشتر جا می‌دهد", nS > n, (nS, n))
        check("ظرفیت: پایه‌ی هر پروسه در مدل هست",
              M.PROC_BASE_MB.get("shard", 0) > 0 and M.MANAGER_MB > 0)
        n4, _, f4 = M.capacity_estimate(free_mb=None, mode="fork")
        check("ظرفیت: بدونِ خواندنِ حافظه → None بی‌استثنا",
              n4 is None or isinstance(n4, int))
        src_m = open(os.path.join(REPO, "manager_82.py"), encoding="utf-8").read()
        check("ظرفیت: خطِ بوت چاپ می‌شود", "ظرفیتِ تخمینی" in src_m)
        check("ظرفیت: هشدارِ کمبود چاپ می‌شود", "اکانت جا نمی‌شود" in src_m)

        check("proc_rss_mb: حافظه‌ی خودِ پروسه را می‌خواند",
              me is not None and me > 5, me)
        pss = M.proc_pss_mb(os.getpid())
        check("proc_pss_mb: سهمِ واقعیِ خودِ پروسه را می‌خواند",
              pss and pss > 0, pss)
        check("proc_pss_mb: PIDِ ناموجود → None", M.proc_pss_mb(999999) is None)
        # PSS هرگز از RSS بیشتر نیست (سهمِ مشترک تقسیم می‌شود)
        check("proc_pss_mb: PSS ≤ RSS",
              pss is not None and M.proc_rss_mb(os.getpid()) is not None
              and pss <= M.proc_rss_mb(os.getpid()) + 1)
        check("proc_rss_mb: PIDِ ناموجود → None", M.proc_rss_mb(999999) is None)
        rss = sup.children_rss()
        check("children_rss: لیستی از (uid, pid, MB) می‌دهد",
              isinstance(rss, list) and all(len(x) == 3 for x in rss), rss)
        src_now = (REPO / "manager_82.py").read_text(encoding="utf-8")
        src_hb = open(os.path.join(REPO, "manager_82.py"), encoding="utf-8").read()
        check("ضربان: مصرفِ سرانه و PSS را چاپ می‌کند",
              "هر کدام، PSS" in src_hb)
        check("ضربان: مصرفِ تجمعیِ سلف‌ها را چاپ می‌کند",
              "مصرفِ سلف‌ها" in src_now)

        # ── ۵) پیام و ثبت در لاگ ─────────────────────────────────────
        src = (REPO / "manager_82.py").read_text(encoding="utf-8")
        check("مدیر: دلیلِ کمبودِ حافظه در db.log ثبت می‌شود",
              '"ram_gate"' in src and "ram_gate_check()" in src)
        check("مدیر: هشدارِ حافظه در ضربان هست", "حافظه‌ی آزاد کم است" in src)
    finally:
        os.chdir(here)
        for k, v in saved.items():
            if v is None:
                os.environ.pop(k, None)
            else:
                os.environ[k] = v
        import shutil
        shutil.rmtree(root, ignore_errors=True)

    print()
    if FAILS:
        print("FAILED:", ", ".join(FAILS))
        return 1
    print("ALL PASS")
    return 0


if __name__ == "__main__":
    sys.exit(main())
