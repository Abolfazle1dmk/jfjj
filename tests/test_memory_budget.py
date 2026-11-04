#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""بودجه‌ی حافظه — کش‌های بی‌سقف، انتخابِ حالت و گرم‌کردنِ بایت‌کد.

هر چیزی که این‌جا تست می‌شود، از اندازه‌گیریِ واقعی آمده است:

* `hash_map` تلگرام سقف ندارد → هر موجودیت ~۰.۴KB (۵۰٬۰۰۰ = ~۱۹MB اندازه‌گیری شد).
* کشِ لینک‌ها (`_exchange_link_id_cache`) هم بدونِ سقف پر می‌شد.
* کامپایلِ `manager_82.py` ~۲۷MB حافظه‌ی موقت می‌گیرد → باید بایت‌کد آماده باشد.
* روی ماشینِ کم‌حافظه پیش‌فرض باید shard باشد (هر اکانت ~۱.۳MB در برابر ~۱۱.۵MB).
"""
import os
import sys
from pathlib import Path

HERE = Path(__file__).resolve().parent
REPO = HERE.parent
FAILS = []


def check(name, cond, extra=""):
    print(("PASS " if cond else "FAIL ") + name
          + (f"   [{extra}]" if extra and not cond else ""))
    if not cond:
        FAILS.append(name)


class FakeClient:
    pass


class FakeCache:
    def __init__(self):
        self.hash_map = {}


class FakeEng:
    pass


def main():
    sys.path.insert(0, str(REPO))
    os.environ.setdefault("DATA_DIR", "/tmp/jafj_memtest/data")
    os.environ.setdefault("PORT", "8891")

    import manager_82 as M

    # ── ۱) 95.py را به‌عنوان «بدونِ اجرای main» لود کن ──
    src = (REPO / "95.py").read_text(encoding="utf-8")
    ns = {"__name__": "jafj_memtest", "__file__": str(REPO / "95.py"),
          "__builtins__": __builtins__}
    exec(compile(src, str(REPO / "95.py"), "exec"), ns)

    trim_entity = ns["trim_entity_cache"]
    trim_link = ns["trim_link_cache"]
    lim_e = ns["ENTITY_CACHE_LIMIT"]
    lim_l = ns["LINK_CACHE_LIMIT"]
    check("سقفِ کشِ موجودیت‌ها تعریف شده", lim_e > 0, lim_e)
    check("سقفِ کشِ لینک‌ها تعریف شده", lim_l > 0, lim_l)

    # ── ۲) کوتاه‌کردنِ کشِ موجودیت‌ها ──────────────────────────────
    c = FakeClient()
    c._mb_entity_cache = FakeCache()
    for i in range(5000):
        c._mb_entity_cache.hash_map[100000 + i] = (123456789, 1)
    n = trim_entity(c, limit=1000)
    check("کشِ موجودیت‌ها کوتاه شد", len(c._mb_entity_cache.hash_map) == 1000,
          len(c._mb_entity_cache.hash_map))
    check("تعدادِ حذف‌شده گزارش می‌شود", n == 4000, n)
    # جدیدترین‌ها می‌مانند (dict ترتیبِ درج را نگه می‌دارد)
    check("جدیدترین موجودیت‌ها نگه داشته شدند",
          104999 in c._mb_entity_cache.hash_map and 100000 not in c._mb_entity_cache.hash_map)

    # پاک‌سازیِ کشِ خیلی بزرگ نباید اول کلِ آن را با .items() در RAM کپی کند.
    class NoFullItemsDict(dict):
        def items(self):
            raise AssertionError("must not materialize the whole entity cache")

    c._mb_entity_cache.hash_map = NoFullItemsDict(
        (i, (123456789, 1)) for i in range(10000))
    removed_bounded = trim_entity(c, limit=1000)
    check("کوتاه‌سازی بدون کپیِ کلِ کشِ موجودیت‌ها",
          removed_bounded == 9000
          and len(c._mb_entity_cache.hash_map) == 1000
          and 9999 in c._mb_entity_cache.hash_map
          and 9000 in c._mb_entity_cache.hash_map
          and 8999 not in c._mb_entity_cache.hash_map,
          removed_bounded)
    check("کشِ کوچک دست‌نخورده می‌ماند", trim_entity(c, limit=5000) == 0)
    check("بدونِ کلاینت → خطا نمی‌دهد", trim_entity(None) == 0)
    check("کلاینتِ بی‌کش → خطا نمی‌دهد", trim_entity(FakeClient()) == 0)

    # ── ۳) کوتاه‌کردنِ کشِ لینک‌ها ─────────────────────────────────
    import time
    eng = FakeEng()
    now = time.time()
    eng._exchange_link_id_cache = {
        "old%d" % i: (now - 100, 1) for i in range(300)
    }
    eng._exchange_link_id_cache.update(
        {"fresh%d" % i: (now + 300, 2) for i in range(50)})
    removed = trim_link(eng, limit=1500)
    check("رکوردهای منقضی پاک شدند", removed >= 300, removed)
    check("رکوردهای تازه ماندند",
          len(eng._exchange_link_id_cache) == 50,
          len(eng._exchange_link_id_cache))
    for i in range(4000):
        eng._exchange_link_id_cache["x%d" % i] = (now + 300, 3)
    trim_link(eng, limit=1500)
    check("سقفِ کشِ لینک رعایت شد",
          len(eng._exchange_link_id_cache) <= 1500,
          len(eng._exchange_link_id_cache))
    check("بدونِ eng → خطا نمی‌دهد", trim_link(FakeEng()) == 0)

    # جستجوی دستورِ خروج نباید تمام جدولِ exchange را یکجا materialize کند.
    check("جستجوی لینکِ تبادل صفحه‌ای و RAM-bounded است",
          "SELECT id,link FROM exchange" in src and "LIMIT 128" in src
          and "before_id = rows[-1][\"id\"]" in src)

    # ── ۴) حلقه‌ی دوره‌ای در سلف ثبت شده ──────────────────────────
    # از PRِ «نگهبانِ حلقه‌ها» به بعد، هر حلقه زیرِ _supervise راه می‌افتد
    # تا اگر مرده خودش برگردد؛ قرارداد همان است: memory_loop اجرا شود.
    check("حلقه‌ی memory_loop ساخته می‌شود",
          ('asyncio.create_task(memory_loop())' in src
           or '_supervise("memory", memory_loop)' in src))
    check("حلقه‌ی حافظه در پاک‌سازیِ خروج لغو می‌شود",
          "mem_task" in src and "st_task, mem_task)" in src)
    # محلِ استفاده: سقف باید همان‌جا هم چک شود (نه فقط در trim_link_cache)
    check("کشِ لینک در محلِ استفاده هم سقف دارد",
          'globals().get("LINK_CACHE_LIMIT"' in src
          and "len(cache) > _lim" in src)

    # ── ۵) انتخابِ حالت بر اساس حافظه ─────────────────────────────
    check("total_ram_mb عدد می‌دهد", (M.total_ram_mb() or 0) > 0, M.total_ram_mb())
    want_shard = "shard" if M.fork_supported() else "process"
    for tot in ("256", "512", "1024"):
        check(f"حافظه‌ی {tot}MB → shard",
              M.spawn_mode({"JAFJ_TOTAL_MB": tot}) == want_shard,
              M.spawn_mode({"JAFJ_TOTAL_MB": tot}))
    want_fork = "fork" if M.fork_supported() else "process"
    check("حافظه‌ی ۲GB → fork", M.spawn_mode({"JAFJ_TOTAL_MB": "2048"}) == want_fork)
    check("JAFJ_SPAWN_MODE=process روی ۵۱۲MB هم رعایت می‌شود",
          M.spawn_mode({"JAFJ_TOTAL_MB": "512", "JAFJ_SPAWN_MODE": "process"}) == "process")
    check("JAFJ_SPAWN_MODE=fork روی ۵۱۲MB هم رعایت می‌شود",
          M.spawn_mode({"JAFJ_TOTAL_MB": "512", "JAFJ_SPAWN_MODE": "fork"}) == want_fork)

    # ── ۶) گرم‌کردنِ بایت‌کد در main.py ────────────────────────────
    main_src = (REPO / "main.py").read_text(encoding="utf-8")
    check("main.py بایت‌کد را گرم می‌کند", "def warm_bytecode" in main_src)
    check("قبل از اجرای مدیر صدا زده می‌شود",
          main_src.index("warm_bytecode(py)") < main_src.index("return start_manager"))
    check("compileall روی فایل‌های سنگین", "compileall" in main_src
          and "manager_82.py" in main_src)

    # ── ۷) shard: یک بار کامپایل ──────────────────────────────────
    shard_src = (REPO / "jafj_shardd.py").read_text(encoding="utf-8")
    check("shard یک بار کامپایل می‌کند", "base_code = compile(src" in shard_src)
    check("مسیرها با پچِ namespace مطلق می‌شوند", "def _patch_paths" in shard_src)
    check("پیش‌فرض‌های تابع هم اصلاح می‌شوند", "def _fix_defaults" in shard_src)
    check("اگر پچ نگرفت، بازنویسی‌وکامپایلِ جایگزین هست",
          "fallback_code" in shard_src)

    # ── ۸) ابزارِ گزارشِ حافظه موجود و سالم است ────────────────────
    tool = REPO / "tools" / "mem_report.py"
    check("tools/mem_report.py موجود است", tool.is_file())
    tool_src = tool.read_text(encoding="utf-8")
    check("گزارش PSS می‌خواند", "smaps_rollup" in tool_src and "Pss:" in tool_src)
    check("درختِ پروسه‌ها را جمع می‌زند", "children" in tool_src and "def tree" in tool_src)
    check("ظرفیت را حساب می‌کند", "def capacity" in tool_src)

    # ── ۹) سقف‌ها از محیط قابلِ تنظیم‌اند ──────────────────────────
    check("JAFJ_ENTITY_CACHE خوانده می‌شود", "JAFJ_ENTITY_CACHE" in src)
    check("JAFJ_LINK_CACHE خوانده می‌شود", "JAFJ_LINK_CACHE" in src)

    print()
    if FAILS:
        print("FAILED:", ", ".join(FAILS))
        return 1
    print("ALL PASS")
    return 0


if __name__ == "__main__":
    sys.exit(main())
