#!/usr/bin/env python3
# -*- coding: utf-8 -*-
# JAFJ_V54_STAMP — پاسخ فوریِ قابل‌تنظیم و بررسی کامل تبادل
"""
═══════════════════════════════════════════════════════════
  جفج (Jafj) — سلف‌بات تلگرام
  با شماره وارد اکانت خودت می‌شود | کنترل از Saved Messages
═══════════════════════════════════════════════════════════

  ▸ ورود با شماره موبایل + کد تأیید (مثل خود تلگرام)
  ▸ پنل مدیریت داخل «پیام‌های ذخیره‌شده» (Saved Messages)
  ▸ فعالیت/استراحت و سقف ساعتی — همه با دستور قابل تنظیم
  ▸ دو پروفایل مستقل: عادی و VIP
  ▸ هوش مصنوعی فقط پیام را تحلیل می‌کند و پاسخ خودکار نمی‌سازد

  ── نصب ──────────────────────────────────────────────
      pip install telethon

  ── راه‌اندازی ────────────────────────────────────────
   ۱) pip install telethon
   ۲) python 32.py
   ۳) شماره را وارد کن → کد در تلگرام می‌آید → وارد کن
      (رمز دو مرحله‌ای داشته باشی، آن را هم می‌پرسد)
   ۴) در تلگرام برو Saved Messages و بفرست:  .panel

   هیچ ویرایشی لازم نیست — api_id از قبل داخل فایل است.

  همه‌چیز در jafj_creds.json و jafj.session ذخیره می‌شود؛
  دفعات بعد دیگر هیچ‌چیز نمی‌پرسد.

  تنظیمات را خودت تعیین می‌کنی. چیزی تنظیم نکنی هم
  ربات روشن می‌ماند و کار می‌کند — با مقادیر پیش‌فرض.
═══════════════════════════════════════════════════════════
"""

# ═══════════════════════════════════════════════════════
#  ۱) اینجا را پر کن
# ═══════════════════════════════════════════════════════

#  آماده است — نیازی به ویرایش نیست.
#  فقط اجرا کن و شماره و کدی که تلگرام می‌فرستد را وارد کن.
API_ID = 28039994
API_HASH = "00877cdcd706564a4de6abf7f7d64349"
PHONE = ""            # خالی بگذار — موقع اجرا می‌پرسد

PREFIX = "."          # پیشوند دستورها. هم "." و هم "/" کار می‌کند.
DRY_RUN = False       # True = چیزی واقعاً ارسال نمی‌شود (تست)

# متن پیش‌فرض «جوین نشدی»؛ وقتی کاربر با «تبادل پیام ناموفق» متنی ثبت
# نکرده باشد، همین جمله + کانال خودم (standard/vip) فرستاده می‌شود.
# وقتی متن سفارشی ثبت شده باشد، فقط همان متن می‌رود و لینک طرف زیرش نمی‌آید.
DEFAULT_MSG_NO = "نیومدی"

QUICK_EXCHANGE_DEFAULTS = {
    "msg_ok": "جوین شدم ✅",
    "msg_no": "چک کردم، نیومدی؛ بیا تا بیام. نمیای، درجا لفت می‌دم\n{mychannel}",
    "msg_come": "جوینم، جوین شو؛ نمیای لفت می‌دم و چک می‌کنم\n{mychannel}",
    "msg_wait": "⏳ دارم چک می‌کنم، صبر کن",
    "msg_nolink": "🔗 لینک کانالت رو بفرست",
    "msg_claim_no": "گفتی جوین شدی ولی عضو نشدی؛ چک کردم، بیا تا بیام\n{mychannel}",
}

# این مقادیر همان پیش‌فرض‌های quick exchange نسخه‌ی قبلی‌اند. اگر مدیر
# خودش متنی را عوض نکرده باشد، با اجرای دوباره‌ی wizard به متن‌های جدید
# مهاجرت می‌کنند؛ متن‌های سفارشی دیگر دست‌نخورده می‌مانند.
QUICK_EXCHANGE_PREVIOUS_DEFAULTS = {
    "msg_no": "❌ نیومدی | اول عضو شو بعد بگو",
    "msg_come": "✅ اومدم 🤝 نوبت تو",
    "msg_wait": "⏳ دارم چک می‌کنم صبر کن",
    "msg_claim_no": "❌ گفتی جوین شدی ولی عضو نشدی",
}

# توضیحِ تبادل سریع: دو قدم اصلی، سپس پرسشِ اختیاریِ پشتیبان با ردِ روشن.
QUICK_EXCHANGE_HELP = (
    "⚡ تبادل سریع — فقط ۲ قدم اصلی:\n"
    "۱) کانالِ خودت (مثلاً @mychannel)\n"
    "۲) گروه اصلی (مثلاً @exchange_group)\n"
    "بعدش فقط می‌پرسم گروه پشتیبان هم می‌خواهی یا نه؛ می‌توانی رد کنی."
)

# ═══════════════════════════════════════════════════════
#  ۲) پیش‌فرض‌ها — همه با دستور قابل تغییرند
# ═══════════════════════════════════════════════════════

DEFAULTS = {
    "standard": {
        "mode": "cycle",         # always = ۲۴ساعته | cycle = فعالیت/استراحت
        "active_minutes": 60,
        "rest_minutes": 30,
        "max_per_hour": 12,      # سقف ارسال در ساعت (۰ = نامحدود)
        "min_gap_sec": 45,
        "max_gap_sec": 120,
        "quiet_hours": [],
        "channel": "",           # با دستور .setch تنظیم می‌شود
    },
    "vip": {
        "mode": "always",
        "active_minutes": 60,
        "rest_minutes": 15,
        "max_per_hour": 30,
        "min_gap_sec": 20,
        "max_gap_sec": 45,
        "quiet_hours": [],
        "channel": "",           # با دستور .setvip تنظیم می‌شود
    },
    "paused": False,

    # ── تبادل دوطرفه ──────────────────────────────────
    #  طرف پیام می‌دهد «جوین شدم» → ربات چک می‌کند
    #  واقعاً عضو کانال تو شده یا نه → اگر شده بود جوین می‌شود
    #  اگر بعداً لفت داد، ربات هم از کانالش لفت می‌دهد
    #  اگر ادعای جوین کرد ولی عضو نبود: دو پیام «نیومدی» با فاصله‌ی
    #  تصادفی (پیش‌فرض ۲۰ تا ۴۰ ثانیه) و بعد از آن لفت از کانالش
    "exchange": {
        "enabled": False,          # .ex on
        "auto_join": True,         # False = اول از تو تأیید می‌گیرد
        "groups": [],              # با جایگزینی روشن: ترتیب اولویت؛ وگرنه همه مثل قبل اسکن می‌شوند
        "group_failover_on": False, # جایگزینی خودکار اختیاری؛ خاموش پیش‌فرض
        "group_failover_after_sec": 300, # چند ثانیه بدون لینک معتبر تا گروه بعدی
        "auto_leave_completed_on_limit": True, # هنگام رسیدن سقف تلگرام، فقط تبادل تمام‌شده
        # هر دور پاکسازی سقف، چند کانالِ جفج‌زده لفت شود (هم‌ارزِ
        # CAPACITY_CLEANUP_BATCH_DEFAULT پایین‌تر؛ این‌جا عددِ خام است چون
        # DEFAULTS قبل از آن ثابت‌ها تعریف می‌شود).
        "capacity_cleanup_batch": 3,
        "_capacity_join_blocked_until": 0,
        "_group_failover_active_index": 0,
        "_group_failover_last_activity": 0,
        "min_join_gap_sec": 30,    # فاصله پیش‌فرض بین دو جوین (از یک عدد ثابت به بازه تصادفی)
        "max_join_gap_sec": 60,
        # بررسی عضویت طرف بی‌صدا و با فاصله تصادفی انجام می‌شود.
        # پیش‌فرض سالم: ۱۵ تا ۳۰ ثانیه تصادفی (نه آن‌قدر کوتاه که فلود بسازد).
        # بعد از جوین، تا سقف ۲۴ ساعت چک می‌کنیم؛ فاصله‌ی چک با سن رکورد
        # پلکانی بلند می‌شود تا بارِ «چک تا ابد» روی اکانت نیفتد.
        # لفت فقط بعد از ۲ منفیِ تأییدشده (هرکدام با چک دوم) انجام می‌شود.
        "check_min_sec": 15,
        "check_max_sec": 30,
        "check_interval_sec": 30,
        "response_delay_sec": 15,  # تأخیر پاسخ بعد از Join واقعی
        "max_joins_per_day": 0,    # Join بدون سقف روزانه
        "recheck_hours": 24,       # چک عضویت تا ۲۴ ساعت بعد از جوین ادامه دارد
        "recheck_minutes": 1,       # بررسی پیش‌فرض عضویت هر یک دقیقه (پشتیبان قدیمی)
        "max_strikes": 2,          # لفت بعد از ۲ بار نبودنِ تأییدشده (نه یک منفیِ تنها)
        "permanent_check": True,   # نگهبانی عضویت بعد از جوین
        "permanent_check_max_hours": 24,  # سقف نگهبانی: ۲۴ ساعت بعد از جوین (۰ = تا ابد)
        # متن جواب‌ها را خودت تعیین می‌کنی:
        #   .ex msgok متن   → وقتی جوین شد
        #   .ex msgno متن   → وقتی طرف هنوز عضو نشده
        #                     اگر متن سفارشی ثبت کرده باشی: فقط همان متن می‌رود
        #                     (لینک طرف زیرش نمی‌آید). اگر ثبت نکرده باشی:
        #                     پیش‌فرض «نیومدی» + کانال خودت (نه کانال طرف)
        #   .ex msgwait متن → وقتی در حال بررسی است
        # هرکدام خالی باشد، همان مورد جواب داده نمی‌شود؛ تنها استثنا msgno است
        # که همیشه پیش‌فرض «نیومدی» می‌فرستد.
        "reply": True,
        # هیچ متن ثابتی از طرف کد ارسال نمی‌شود؛ متن‌ها را خودت ثبت می‌کنی.
        "msg_ok": "",
        "msg_no": "",
        "msg_claim_no": "",
        "msg_wait": "",
        "msg_nolink": "",
        "msg_come": "",
        "come_delay_sec": 0,         # تأخیر پیام «بیا» بعد از جوین (سازگاری)
        "come_min_sec": 34,          # بازه‌ی تصادفی تأخیر «بیا» بعد از جوینِ ربات
        "come_max_sec": 35,          # (پیش‌فرض: ۳۴–۳۵ ثانیه؛ هرگز ۰/درجا)
        "response_delay_sec": 15,    # تأخیر پاسخ بعد از Join واقعی (سازگاری)
        "response_min_sec": 11,      # بازه‌ی تصادفی پاسخ موفق «جوین شدم» روی پیام طرف
        "response_max_sec": 48,      # (پیش‌فرض: ۱۱–۴۸ ثانیه)
        "reply_min_sec": 5,          # بازه‌ی تصادفی تأخیر پاسخ‌های مستقیم رویداد
        "reply_max_sec": 18,         # (عضو نیست/صبر کن/کانالت پیدا نشد؛ ۵–۱۸ ثانیه)
        "reminder_min_sec": 20,      # فاصله کمینه بین دو پیام «نیومدی» (پیش‌فرض ۲۰–۴۰ ثانیه تصادفی)
        "reminder_max_sec": 40,      # فاصله بیشینه بین دو پیام «نیومدی» — هیچ‌وقت پشت سر هم نمی‌روند
        # ── صفِ تک‌عملکردی تبادل (فیکس «همه‌چیز درجا پشت سر هم») ──
        # هر عملکرد تبادل (چک عضویت / جوین / لفت / پیام «نیومدی» / «جوین شدم»)
        # یک «عملکرد» حساب می‌شود. تا وقتی یک عملکرد تمام نشده، عملکرد بعدی
        # شروع نمی‌شود؛ بعد از تمام‌شدنش هم op_gap_min تا op_gap_max ثانیه
        # (پیش‌فرض ۱۵–۲۰ تصادفی) صبر می‌شود و بعد نوبت بعدی اجرا می‌شود.
        # روی هر رکورد هم همین فاصله رعایت می‌شود: رکوردی که همین الان
        # چک/جوین/پیام گرفته، دوباره چک نمی‌شود (مثلاً بلافاصله بعد از جوین
        # «نیومدی» نمی‌رود؛ اول ۱۵–۲۰ ثانیه صبر، بعد چکِ واقعیِ عضویت).
        # این بازه «کفِ» فاصله‌هاست: فاصله‌ی یادآوری/پاسخ اگر بلندتر باشد،
        # همان بلندتر مبناست (هرگز کوتاه‌تر از این نمی‌شود).
        "op_gap_min_sec": 15,
        "op_gap_max_sec": 20,
        # کلید قدیمی برای سازگاری؛ نامشخص هرگز به عدم عضویت تبدیل نمی‌شود
        "unk_fallback_after": 0,
        # بعد از این تعداد پیام «عضو نیست»، اگر طرف هنوز نیامده باشد از
        # کانالش لفت می‌دهیم (یا اگر هنوز جوین نشده‌ایم، تبادل لغو می‌شود).
        "max_reminders": 2,
        # ── حالت پیش‌قدم: خودت اول جوین می‌شوی ──
        "initiate": True,         # پیش‌فرض روشن
        "scan_every_sec": 30,     # پیش‌قدم: هر ۳۰ ثانیه پیام‌های جدید را می‌بیند
        "scan_jitter_min_sec": 5,  # تأخیر تصادفی بین اسکن گروه‌ها — ضد اسپم (پیش‌فرض ۵–۱۵ ثانیه)
        "scan_jitter_max_sec": 15, # اگر ۲ گروه داری: اولی سر ۳۰ ثانیه، دومی ۵–۱۵ ثانیه بعد، بعد دوباره ۳۰ ثانیه صبر
        "scan_every_min": 1,      # سازگاری با تنظیم قدیمیِ دقیقه‌ای
        "scan_limit": 50,         # چند پیام آخر هر گروه
        "scan_max_age_sec": 300,   # فقط لینک حداکثر ۵ دقیقه اخیر
        "scan_age_version": 1,
        "scan_pick": 1,           # تازه‌ترین لینک جدید
        "msg_first": "",          # متنی که بعد از جوینِ خودت ریپلای می‌شود
        "scan_last": {},          # آخرین پیام دیده‌شده هر گروه
        "scan_last_time": {},     # آخرین زمان اسکن هر گروه — برای پخش تصادفی ضد اسپم
        # فقط به ریپلای‌هایی که این کلمات را دارند واکنش نشان بده.
        # خالی = به هر ریپلایی روی پیام تو واکنش نشان می‌دهد.
        "words": [],
        # گزارش خصوصی در Saved Messages؛ پیش‌فرض لحظه‌ای است.
        "report_mode": "live",                 # live | summary | off
        "report_summary_interval_sec": 86400,   # خلاصه خودکار هر ۲۴ ساعت
        "report_last_sent": 0,
        # ── سقف جوین/ساعت (محدودیت آهسته، جدا از محافظ ریسک) ──
        #  خاموش پیش‌فرض؛ اگر روشن باشد، در یک ساعتِ غلتان از این تعداد
        #  بیشتر جوین نمی‌زند و تا باز شدن پنجره صبر می‌کند.
        "hour_cap_on": False,        # پیش‌فرض خاموش (فقط با دستور فعال می‌شود)
        "hour_cap": 60,              # عددِ امنِ پیشنهادی: ۶۰ جوین/ساعت
        "_hour_cap_blocked": 0,      # آخرین باری که به‌خاطر سقف متوقف شده
        # ── تطبیقیِ هوشمند: فاصله جوین با FloodWait و آپ‌تایم زیاد می‌شود ──
        #  ایده کاربر: حالت عادی هر ۳۰ ثانیه یک جوین؛ اگر FloodWait آمد
        #  هر بار ۱۵ ثانیه به فاصله اضافه شود؛ اگر چند ساعت روشن بود
        #  از ۳۰ ثانیه به ۱ دقیقه برود تا ریسک ریپ کم شود.
        "adaptive_on": True,                    # روشن پیش‌فرض
        "adaptive_flood_step_sec": 15,          # هر FloodWait چقدر اضافه کند
        "adaptive_flood_max_sec": 120,          # سقف اضافه از Flood
        "adaptive_flood_decay_min": 60,         # بعد از این دقیقه بدون Flood، یکی کم می‌کند
        "adaptive_uptime_threshold_hours": 3,   # بعد از چند ساعت کند شود
        "adaptive_uptime_extra_sec": 30,        # بعد از آستانه چقدر اضافه (۳۰→۶۰)
        "adaptive_uptime_per_hour_sec": 10,     # هر ساعت اضافه بعد آستانه چقدر بیشتر
        "adaptive_uptime_max_sec": 90,          # سقفِ کلِّ اضافه از آپ‌تایم — بی‌نهایت رشد نمی‌کند
        "_adaptive_flood_extra": 0,             # اضافه فعلی از Flood
        "_adaptive_last_flood": 0,              # آخرین زمان Flood
        "_adaptive_last_decay": 0,              # آخرین چک کاهش
        "_adaptive_hard_until": 0,              # 🧯 تا این لحظه فاصله برگشت نمی‌خورد (فلود بزرگ)
    },

    # ── محافظ ریپورت ───────────────────────────────────
    #  با چند معیار (ارسال، جوین، لفت، خطای جوین، فلاد/محدودیت، برنگشتنی)
    #  درصدِ تقریبیِ خطرِ ریپورت/محدود شدن حساب را می‌سازد.
    #  وقتی به آستانه (trigger) برسد، تبادل را کاملاً خودکار خاموش می‌کند
    #  تا اکانت در خطر نیفتد؛ وقتی زیر آستانه‌ی بازگشت (resume) رفت،
    #  خودش دوباره روشنش می‌کند. فقط اگر خودِ محافظ خاموشش کرده باشد
    #  برمی‌گرداند تا تصمیم دستیِ کاربر (روشن/خاموشِ .ex) را نادیده نگیرد.
    "risk": {
        # ── حالت پیش‌فرض: توقف بر اساس «امتیازِ انتزاعی» خاموش است ──
        "on": False,             # توقفِ خودکار بر اساس درصدِ تخیلیِ ریسک: خاموش در حالت پیش‌فرض
        # ── پایشِ «واقعی» (همیشه فعال): فقط وقتی اکانت واقعاً در مرز ریپ است ──
        "hard_on": True,         # چکِ سیگنال‌های واقعیِ ریپ — همیشه روشن
        "hard_trigger": 80,      # امتیازِ واقعی بالای این → توقف اجباری
        "hard_window_min": 30,   # بازه‌ی پایشِ سیگنال واقعی (دقیقه)
        "window_hours": 24,      # بازه‌ی آماری (ساعت اخیر)
        "trigger": 75,           # بالای این درصد (فقط زمانی که on=True) → تبادل خاموش
        "resume": 55,            # زیر این درصد → تبادل روشن دوباره
        "check_interval_sec": 60, # هر چند ثانیه یک‌بار محاسبه
        "_auto_off": False,      # آیا محافظ خودش خاموش کرده؟
        "_last_off": 0,          # زمان آخرین خاموشی خودکار
        "_last_alert": 0,        # زمان آخرین هشدار (ضد اسپم نوتیف)
    },
}

# ── سقفِ حافظه‌ی کش‌ها ───────────────────────────────────────────────
# تلگرام (telethon) هر کاربر/گروهی که ببیند را در `_mb_entity_cache` نگه
# می‌دارد و آن دیکشنری **هیچ سقفی ندارد**. یک سلف‌باتِ تبادل که در چند ماه
# با هزاران نفر طرف می‌شود، بی‌سروصدا چند مگابایت برای همیشه نگه می‌دارد.
# اندازه‌گیری: هر موجودیت ~۰.۴ کیلوبایت → ۱۰٬۰۰۰ موجودیت ≈ ۴ مگابایت.
ENTITY_CACHE_LIMIT = 8000
LINK_CACHE_LIMIT = 1500


def _env_int(name, default):
    try:
        v = int((os.environ.get(name) or "").strip() or default)
    except Exception:
        v = default
    return max(0, v)


ENTITY_CACHE_LIMIT = _env_int("JAFJ_ENTITY_CACHE", ENTITY_CACHE_LIMIT)
LINK_CACHE_LIMIT = _env_int("JAFJ_LINK_CACHE", LINK_CACHE_LIMIT)


def trim_entity_cache(client, limit=None):
    """(تعدادِ حذف‌شده) — قدیمی‌ترین موجودیت‌ها را از کشِ تلگرام بردار.

    چرا: `hash_map` سقف ندارد و با هر کاربرِ تازه رشد می‌کند. حذفِ قدیمی‌ها
    فقط یعنی «برای بارِ بعد باید دوباره resolve شود» — هیچ رفتاری عوض
    نمی‌شود، فقط حافظه آزاد می‌شود.
    """
    lim = int(limit if limit is not None else ENTITY_CACHE_LIMIT)
    if lim <= 0:
        return 0
    try:
        cache = getattr(client, "_mb_entity_cache", None)
        hm = getattr(cache, "hash_map", None)
        if not isinstance(hm, dict) or len(hm) <= lim:
            return 0
        keep = dict(list(hm.items())[-lim:])     # dict ترتیبِ درج را می‌داند
        removed = len(hm) - len(keep)
        hm.clear()
        hm.update(keep)
        return removed
    except Exception:
        return 0


def trim_link_cache(eng, limit=None):
    """(تعدادِ حذف‌شده) — کشِ «شناسه‌ی کانالِ لینک‌ها» را کوتاه کن.

    این کش هم بدونِ سقف پر می‌شد: هر لینکِ تازه‌ای که در جریانِ تبادل دیده
    شود یک رکورد می‌گذاشت و رکوردهای منقضی هیچ‌وقت پاک نمی‌شدند.
    """
    lim = int(limit if limit is not None else LINK_CACHE_LIMIT)
    try:
        cache = getattr(eng, "_exchange_link_id_cache", None)
        if not isinstance(cache, dict):
            return 0
        now0 = time.time()
        dead = [k for k, v in list(cache.items())
                if not v or not isinstance(v, tuple) or v[0] < now0]
        for k in dead:
            cache.pop(k, None)
        extra = 0
        if lim > 0:
            while len(cache) > lim:
                cache.pop(next(iter(cache)), None)
                extra += 1
        return len(dead) + extra
    except Exception:
        return 0


SESSION = "jafj"
CREDS_FILE = "jafj_creds.json"
AI_FILE = "jafj_ai.json"
LIMITS_FILE = "jafj_limits.json"     # سقف‌های پلن — از سمت پنل نوشته می‌شود
STATUS_FILE = "jafj_status.json"     # گزارش زنده — پنل می‌خواندش
SETTINGS_FILE = "jafj_settings.json"
DB_FILE = "jafj.db"
LOG_FILE = "jafj.log"


# ═══════════════════════════════════════════════════════
#  ۳) کد
# ═══════════════════════════════════════════════════════

import os
import re
import sys
import json
import time
import glob
import shutil
import random
import sqlite3
import asyncio
import threading
import traceback
import http.cookiejar
import urllib.parse
import urllib.request
import urllib.error
from datetime import datetime


# ── اعتبارسنجی آیدی/لینکِ کانال و گروه ──────────────────────────────
# قاعده‌ی اصلی: در «تبادل سریع» هر ورودی باید یک آیدی/لینکِ واقعی باشد.
# قبلاً هر چیزی (حتی خودِ کلمه‌ی «کانال» یا «گروه») به‌عنوان مقدار ذخیره
# می‌شد؛ نتیجه: کانال خالی می‌ماند ولی گروهِ بی‌معنی ثبت می‌شد و تبادل
# روشن می‌شد. این تابع همان باگ را می‌بندد.
_REF_USERNAME_RE = re.compile(r"^[A-Za-z][A-Za-z0-9_]{3,31}$")
_REF_INVITE_RE = re.compile(r"^[A-Za-z0-9_-]{6,64}$")
_REF_NOT_A_VALUE = {
    "کانال", "چنل", "گروه", "پنل", "بستن", "لغو", "تبادل", "تنظیمات",
    "channel", "group", "panel", "close", "cancel", "none", "off",
}


def normalize_peer_ref(value):
    """«@name / name / t.me/name / +hash / t.me/+hash» → مقدارِ قابل‌ذخیره.

    None یعنی مقدار معتبر نیست (خالی، دستور، جمله، فاصله‌دار یا لینکِ
    ناشناخته). عمداً محافظه‌کار است: چیزی که مطمئن نیستیم آیدی است را
    ذخیره نمی‌کنیم تا دوباره «گروهِ الکی» ثبت نشود.
    """
    v = (value or "").strip().strip("«»\"'")
    if not v or len(v) > 100 or re.search(r"\s", v):
        return None
    low = v.lower().strip(".:،")
    if low in _REF_NOT_A_VALUE:
        return None
    # لینک کامل یا کوتاهِ t.me / telegram.me
    m = re.match(r"^(?:https?://)?(?:www\.)?(?:t|telegram)\.me/(.+)$",
                 v, flags=re.I)
    if m:
        path = m.group(1).strip("/")
        if path.lower().startswith("joinchat/"):
            path = "+" + path[len("joinchat/"):]
        if path.lower().startswith("s/"):
            path = path[2:]
        if path.startswith("+"):
            h = path[1:]
            return f"https://t.me/+{h}" if _REF_INVITE_RE.match(h) else None
        if path.lower().startswith("c/"):
            return None          # لینکِ پیامِ خصوصی، آیدیِ کانال نیست
        name = path.split("/")[0]
        return f"@{name}" if _REF_USERNAME_RE.match(name) else None
    # هشِ دعوتِ خالی: «+abc123»
    if v.startswith("+"):
        h = v[1:]
        return f"https://t.me/+{h}" if _REF_INVITE_RE.match(h) else None
    # آیدیِ عددی (کانال/گروهِ جوین‌شده)
    if re.fullmatch(r"-?\d{5,20}", v):
        return v
    name = v.lstrip("@")
    if _REF_USERNAME_RE.match(name):
        return f"@{name}"
    return None


def peer_ref_key(ref):
    """کلیدِ نرمال‌شده‌ی یک لینک/یوزرنیم برای مقایسه (بدونِ regex در حلقه).

    جدا کردنش از ``same_peer_ref`` برای سرعت است: در پاکسازیِ سقف عضویت،
    همین نرمال‌سازی میلیون‌ها بار صدا زده می‌شد و کلِ event loop را
    ده‌ها ثانیه قفل می‌کرد (باعثِ «آفلاین شدن» اکانت می‌شد).
    """
    s = str(ref or "").strip().lower().rstrip("/")
    s = re.sub(r"^https?://", "", s)
    s = re.sub(r"^(www\.)?(t|telegram)\.me/", "", s)
    s = s.replace("joinchat/+", "+")
    return s.lstrip("@")


def same_peer_ref(a, b):
    """آیا دو مقدار به یک کانال/گروه اشاره می‌کنند؟ (برای ردِ کانال=گروه)"""
    na, nb = peer_ref_key(a), peer_ref_key(b)
    return bool(na) and na == nb

def group_failover_index(ex_cfg, groups, now_ts):
    """Return the prioritized group index when optional failover is enabled.

    A missing activity timestamp starts a fresh grace period; old settings
    therefore never fail over immediately just because the feature was added.
    """
    if not ex_cfg.get("group_failover_on") or len(groups or []) < 2:
        return None
    try:
        index = int(ex_cfg.get("_group_failover_active_index", 0))
    except (TypeError, ValueError):
        index = 0
    if index < 0 or index >= len(groups):
        index = 0
        ex_cfg["_group_failover_active_index"] = 0
    try:
        last_activity = int(ex_cfg.get("_group_failover_last_activity", 0) or 0)
    except (TypeError, ValueError):
        last_activity = 0
    if last_activity <= 0:
        ex_cfg["_group_failover_last_activity"] = int(now_ts)
    return index


def group_failover_scan_groups(ex_cfg, groups, now_ts):
    """Return all legacy scan targets or the single active priority group."""
    group_list = list(groups or [])
    index = group_failover_index(ex_cfg, group_list, now_ts)
    return group_list if index is None else [group_list[index]]


def group_failover_after_scan(ex_cfg, groups, now_ts, found, scan_error=False):
    """Record activity or advance to the next group after a quiet interval.

    Returns ``(old_index, new_index)`` only when a switch happens.
    """
    index = group_failover_index(ex_cfg, groups, now_ts)
    if index is None:
        return None
    if found:
        ex_cfg["_group_failover_last_activity"] = int(now_ts)
        return None
    if scan_error:
        return None
    try:
        last_activity = int(ex_cfg.get("_group_failover_last_activity", now_ts) or now_ts)
        after_sec = int(ex_cfg.get("group_failover_after_sec", 300) or 300)
    except (TypeError, ValueError):
        last_activity, after_sec = int(now_ts), 300
    after_sec = max(60, min(after_sec, 7 * 24 * 60 * 60))
    if int(now_ts) - last_activity < after_sec:
        return None
    next_index = (index + 1) % len(groups)
    ex_cfg["_group_failover_active_index"] = next_index
    # Give the newly selected group a full interval before rotating again.
    ex_cfg["_group_failover_last_activity"] = int(now_ts)
    return index, next_index


# ── دروازه و اعلان‌های اسکن پیش‌قدم (ضد طوفانِ اعلان) ──────────────
# چند رکورد «در صف Join» می‌تواند معلق بماند تا اسکنِ خودکار متوقف شود؟
# با فاصله‌ی پیش‌فرض ۳۰–۶۰ ثانیه، این تعداد تقریباً کل پنجره‌ی ۵ دقیقه‌ای
# «سن لینک» را پر می‌کند؛ بیشتر از این، رکوردها پیش از رسیدن نوبت پیر
# می‌شدند و فقط رکورد مرده و اعلان تکراری می‌ساختند.
SCAN_JOIN_BACKLOG_LIMIT = 5
# اعلان خودکار «کانال تازه پیدا شد» حداکثر هر چند ثانیه یک‌بار و به‌صورت
# تجمیعی برود (اسکن دستی مشمول این محدودیت نیست و همان لحظه جواب می‌دهد).
SCAN_FOUND_NOTE_GAP_SEC = 300
# خلاصه‌ی «کانال قدیمی رد شد»: حداکثر چند لینک داخل یک پیام نشان داده شود
# و حداکثر چند ثانیه برای تجمیع صبر شود.
STALE_NOTE_MAX_LINKS = 10
STALE_FLUSH_SEC = 20


def scan_gate_reason(blocked_until, approved_count, now_ts,
                     limit=SCAN_JOIN_BACKLOG_LIMIT):
    """چرا اسکنِ خودکار باید فعلاً رد شود؟ خروجی: 'flood' / 'backlog' / ''.

    'flood'    → صفِ تک‌عملکردی به‌خاطر FloodWait بسته است و هیچ جوینی
                 تا پایان جریمه اجرا نمی‌شود؛ اسکن جدید فقط انباشت می‌کند.
    'backlog'  → به سقف رکوردهای معلقِ Join رسیده‌ایم؛ رکورد تازه قبل از
                 رسیدن نوبت از پنجره‌ی سن لینک پیر می‌شود.
    اسکنِ دستی (دستور «تبادل اسکن») عمداً از این دروازه رد نمی‌شود.
    """
    try:
        if blocked_until and float(blocked_until) > float(now_ts):
            return "flood"
        if int(approved_count or 0) >= int(limit):
            return "backlog"
    except (TypeError, ValueError):
        return ""
    return ""


def format_stale_batch(links, max_age_sec, shown=STALE_NOTE_MAX_LINKS):
    """خلاصه‌ی یک‌پیامیِ رکوردهای منقضی‌شده، به‌جای اعلان جدا per-record."""
    clean = [str(l) for l in (links or []) if l]
    n = len(clean)
    head = clean[:shown]
    lines = [f"🕒 {fa(n)} کانال قدیمی (بیش از {secs(int(max_age_sec or 0))}) "
             "رد شد؛ Join نشد."]
    lines += [f"`{l}`" for l in head]
    if n > len(head):
        lines.append(f"و {fa(n - len(head))} مورد دیگر…")
    return "\n".join(lines)


def _safe_id(rec):
    try:
        return int((rec or {}).get("id") or 0)
    except (TypeError, ValueError):
        return 0


def _capacity_pool(records):
    """استخرِ joined + شمارشِ idها به‌ازای هر chat_id/لینک (یک پاس).

    تشخیص «تکراری» قبلاً برای هر رکورد کلِ استخر را می‌گشت (O(n²) با
    regex داخلش). روی ۱۰۰۰ رکورد همان کار **۶۱ ثانیه** طول می‌کشید و چون
    همگام (sync) است، ثبت/وقفه‌ی event loop می‌کرد و اتصالِ تلگرام
    می‌افتاد — یعنی اکانت «آفلاین» می‌شد. حالا یک پاسِ خطی است.
    """
    joined = [r for r in (records or []) if r.get("status") == "joined"]
    by_chat, by_link = {}, {}
    for r in joined:
        rid = _safe_id(r)
        try:
            cid = int(r.get("chat_id") or 0)
        except (TypeError, ValueError):
            cid = 0
        if cid:
            by_chat.setdefault(cid, set()).add(rid)
        key = peer_ref_key(r.get("link"))
        if key:
            by_link.setdefault(key, set()).add(rid)
    return joined, by_chat, by_link


def _capacity_candidates(records, own_channels=(), exclude_id=None,
                         exclude_ids=None):
    """کاندیدهای امنِ لفت، قدیمی‌ترین اول — بدونِ حلقه‌ی تودرتو."""
    joined, by_chat, by_link = _capacity_pool(records)
    own_keys = {peer_ref_key(c) for c in (own_channels or []) if c}
    own_keys.discard("")
    skip = set()
    for v in (exclude_ids or ()):
        try:
            skip.add(int(v))
        except (TypeError, ValueError):
            pass
    if exclude_id:
        try:
            skip.add(int(exclude_id))
        except (TypeError, ValueError):
            pass

    out = []
    for rec in joined:
        rid = _safe_id(rec)
        if rid in skip:
            continue
        if not rec.get("peer_id"):
            continue
        if (str(rec.get("direction") or "in").lower() == "out"
                and not rec.get("peer_joined_at")):
            continue
        try:
            if int(rec.get("next_reminder") or 0) > 0:
                continue
        except (TypeError, ValueError):
            pass
        key = peer_ref_key(rec.get("link"))
        if key and key in own_keys:
            continue
        try:
            cid = int(rec.get("chat_id") or 0)
        except (TypeError, ValueError):
            cid = 0
        # تکراری = رکوردِ دیگری (با id متفاوت) که همان کانال/لینک را دارد.
        if cid and len(by_chat.get(cid, ())) > 1:
            continue
        if key and len(by_link.get(key, ())) > 1:
            continue
        out.append(rec)

    def _age_key(rec):
        try:
            return (int(rec.get("joined_at") or rec.get("created_at") or 0),
                    int(rec.get("id") or 0))
        except (TypeError, ValueError):
            return (0, 0)

    out.sort(key=_age_key)
    return out


def select_capacity_leave_candidate(records, own_channels=(), exclude_id=None,
                                   exclude_ids=None):
    """قدیمی‌ترین کاندیدِ امنِ لفت (یا None).

    قواعد: فقط joined، با peer_id، یادآورِ فعال نداشته باشد، کانال خودِ
    کاربر نباشد، تبادلِ outbound فقط اگر طرف متقابلاً جوین زده باشد، و
    کانالِ تکراری (چند رکورد روی یک کانال) کنار گذاشته می‌شود.
    """
    cands = _capacity_candidates(records, own_channels=own_channels,
                                 exclude_id=exclude_id,
                                 exclude_ids=exclude_ids)
    return cands[0] if cands else None


# ── پاکسازی دسته‌ای سقف عضویت (فرایند لفت موقع پر شدن ۵۰۰) ──────────
# وقتی تلگرام ChannelsTooMuch بدهد، به‌جای یک لفت + بلاک یک‌ساعته، یک
# «دور پاکسازی» اجرا می‌شود و تا این تعداد از قدیمی‌ترین کانال‌هایی که
# خود جفج جوین زده (تبادل‌های کامل‌شده‌ی امن) لفت می‌شوند. عدد با دستور
# «تبادل لفت خودکار تعداد <عدد>» قابل تغییر است.
CAPACITY_CLEANUP_BATCH_DEFAULT = 3
CAPACITY_CLEANUP_BATCH_MIN = 1
CAPACITY_CLEANUP_BATCH_MAX = 100
# سقفِ زمانیِ یک دور پاکسازی. هر لفت از صفِ تک‌عملکردی رد می‌شود و فاصله‌ی
# ۱۵–۲۰ ثانیه‌ای دارد؛ دورِ طولانی، صفِ تبادل را دقایقی در انحصار می‌گیرد و
# پاسخ به پیوی هم عقب می‌افتد. با این سقف، دورِ نیمه‌کاره در حلقه‌ی بعد
# ادامه پیدا می‌کند.
CAPACITY_CLEANUP_MAX_SEC = 120
# اگر حلقه‌ی اصلی بیش از این مقدار عقب بیفتد (کارِ همگامِ طولانی)، در لاگ
# و status ثبت می‌شود — همان چیزی که «آفلاین شدنِ ناگهانی» را توضیح می‌دهد.
LOOP_LAG_WARN_SEC = 20
# اگر بعد از یک دور پاکسازیِ موفق، تلگرام هنوز سقف را پر اعلام کند (ثبتِ
# آزادشدن slot در سرور تلگرام کمی تأخیر دارد)، جوین چقدر مکث کند؟
CAPACITY_REBLOCK_SEC = 300


def capacity_round_exhausted(started, now, limit_sec=CAPACITY_CLEANUP_MAX_SEC):
    """آیا وقتِ یک دور پاکسازی تمام شده است؟ (توقفِ نرم، ادامه در دور بعد)"""
    try:
        return (float(now) - float(started)) >= float(limit_sec)
    except (TypeError, ValueError):
        return False


def clamp_capacity_batch(value):
    """عدد دور پاکسازی را به بازه‌ی مجاز می‌چسباند؛ ورودی نامعتبر → پیش‌فرض."""
    try:
        n = int(value)
    except (TypeError, ValueError):
        return CAPACITY_CLEANUP_BATCH_DEFAULT
    return max(CAPACITY_CLEANUP_BATCH_MIN,
               min(CAPACITY_CLEANUP_BATCH_MAX, n))


def select_capacity_leave_batch(records, own_channels=(),
                                limit=CAPACITY_CLEANUP_BATCH_DEFAULT,
                                exclude_id=None):
    """فهرست مرتب‌شده‌ی کاندیدهای لفتِ امن برای یک دور پاکسازی.

    هر بار قدیمی‌ترین کاندید را با همان قواعد
    ``select_capacity_leave_candidate`` برمی‌دارد و idش را به مجموعه‌ی
    skip اضافه می‌کند تا دور بعد کاندیدِ بعدی (نه دوباره همان) انتخاب شود؛
    تا سقف ``limit``. استخر اصلی دست‌نخورده می‌ماند تا تشخیص تکراری نسبت
    به رکوردهای برداشته‌شده هم درست کار کند. کانال‌های خود کاربر،
    تبادل‌های ناتمام/یادآوردار و تکراری‌ها طبق همان قواعد وارد نمی‌شوند.
    """
    limit = clamp_capacity_batch(limit)
    cands = _capacity_candidates(records, own_channels=own_channels,
                                 exclude_id=exclude_id)
    return cands[:limit]


def format_capacity_cleanup_note(left_links, target, stopped=None):
    """خلاصه‌ی یک‌پیامیِ فرایند پاکسازی سقف (به‌جای نوتیف per لفت)."""
    links = [str(l) for l in (left_links or []) if l]
    n = len(links)
    if n == 0:
        return ("🧹 سقف عضویت تلگرام پر بود ولی هیچ تبادلِ کامل‌شده‌ی امنی "
                "برای لفت پیدا نشد؛ یک عضویت را دستی آزاد کن و بعد "
                "`تبادل لفت خودکار ریست` را بفرست.")
    head = links[:STALE_NOTE_MAX_LINKS]
    lines = [f"🧹 پاکسازی سقف عضویت: از {fa(n)} کانالِ جفج‌زده لفت دادم "
             f"(هدف هر دور: {fa(target)})."]
    lines += [f"`{l}`" for l in head]
    if n > len(head):
        lines.append(f"و {fa(n - len(head))} مورد دیگر…")
    if stopped:
        lines.append(f"⏹ پاکسازی زودتر تمام شد: {stopped}")
    else:
        lines.append("جا آزاد شد؛ جوینِ معلق دوباره تلاش می‌شود.")
    return "\n".join(lines)


VERSION = "3.0"
BUILD_TAG = "JAFJ_SELF_69_70_EN_2026_08_28"
FA = str.maketrans("0123456789", "۰۱۲۳۴۵۶۷۸۹")
EN = str.maketrans("۰۱۲۳۴۵۶۷۸۹٠١٢٣٤٥٦٧٨٩", "01234567890123456789")


def fa(n):
    return str(n)


_FA_DIGITS = str.maketrans("0123456789", "۰۱۲۳۴۵۶۷۸۹")


def fad(n):
    """عدد با رقم فارسی — برای نمایش خلوت در پنل تبادل."""
    return str(n).translate(_FA_DIGITS)


def num(s):
    """عدد فارسی یا انگلیسی → int"""
    return int(str(s).translate(EN).strip())


def dur(m):
    m = int(m)
    if m <= 0:
        return "ندارد"
    if m < 60:
        return f"{fa(m)} دقیقه"
    h, r = divmod(m, 60)
    return f"{fa(h)} ساعت" + (f" و {fa(r)} دقیقه" if r else "")


def secs(s):
    s = int(s)
    if s < 60:
        return f"{fa(s)} ثانیه"
    m, r = divmod(s, 60)
    if m < 60:
        return f"{fa(m)} دقیقه" + (f" و {fa(r)} ثانیه" if r else "")
    h, m = divmod(m, 60)
    return f"{fa(h)} ساعت" + (f" و {fa(m)} دقیقه" if m else "")


# ─────────────────────────────────────────────
#  تنظیمات
# ─────────────────────────────────────────────
def backup_settings_file(path, keep=5):
    """یک کپی زمان‌دار از فایل داده می‌سازد تا اگر مهاجرت یا هر اتفاق
    غیرمنتظره چیزی را تغییر داد، نسخه‌ی قبل در دسترس بماند.
    فقط `keep` بکاپ آخر نگه داشته می‌شود تا پوشه‌ی داده باد نکند."""
    try:
        if not os.path.exists(path):
            return None
        ts = datetime.now().strftime("%Y%m%d-%H%M%S")
        bak = f"{path}.bak-{ts}"
        shutil.copy2(path, bak)
        try:
            backups = sorted(glob.glob(f"{path}.bak-*"))
            for old in backups[:-keep]:
                try:
                    os.remove(old)
                except Exception:
                    pass
        except Exception:
            pass
        return bak
    except Exception:
        return None


class Settings:
    def __init__(self, path=SETTINGS_FILE):
        self.path = path
        self.data = json.loads(json.dumps(DEFAULTS))
        if os.path.exists(path):
            try:
                with open(path, encoding="utf-8") as f:
                    saved = json.load(f)
                for k, v in saved.items():
                    if isinstance(v, dict) and isinstance(self.data.get(k), dict):
                        self.data[k].update(v)
                    else:
                        self.data[k] = v
                old_ex = saved.get("exchange") or {}
                if ("msg_come" not in old_ex and old_ex.get("msg_first")):
                    self.data["exchange"]["msg_come"] = old_ex["msg_first"]
                # متن‌های پیش‌فرض نسخه‌های قبلی متن ثابت بودند؛ در این نسخه
                # فقط متن‌هایی که خود کاربر ثبت کرده‌اند نگه داشته می‌شوند.
                if old_ex.get("msg_come") in ("بیا", "اومدم", "اومدم بیا"):
                    self.data["exchange"]["msg_come"] = ""
                    self.data["exchange"]["msg_first"] = ""
                if old_ex.get("msg_ok") in ("بیا", "اومدم", "اومدم بیا"):
                    self.data["exchange"]["msg_ok"] = ""
                if old_ex.get("msg_no") == "اول عضو شو":
                    self.data["exchange"]["msg_no"] = ""
                if old_ex.get("msg_nolink") == "لینک کانالت را بفرست":
                    self.data["exchange"]["msg_nolink"] = ""
                # تنظیم‌های قدیمی (فاصله‌ی دقیقاً ثابت) به بازه‌ی تصادفی جدید منتقل شوند.
                # فاصله‌ی ثابت الگوی ماشینی و قابل شناسایی است؛ پس به ۳۰–۶۰ ثانیه تصادفی می‌رود.
                if ((old_ex.get("min_join_gap_sec"), old_ex.get("max_join_gap_sec"))
                        in ((90, 240), (30, 30), (60, 60), (45, 45))):
                    self.data["exchange"]["min_join_gap_sec"] = 30
                    self.data["exchange"]["max_join_gap_sec"] = 60
                if old_ex.get("scan_age_version") != 1:
                    self.data["exchange"]["scan_max_age_sec"] = 300
                    self.data["exchange"]["scan_age_version"] = 1
                if "scan_every_sec" not in old_ex:
                    # درخواست فعلی: پیش‌قدم هر ۳۰ ثانیه یک فرصت اسکن/Join داشته باشد؛
                    # مقدارهای دقیقه‌ای نسخه‌های قبل (حتی ۲ دقیقه) به این cadence منتقل می‌شوند.
                    self.data["exchange"]["scan_every_sec"] = 30
                    self.data["exchange"]["scan_every_min"] = 1
                    # یک بار بعد از ارتقا دوباره آخرین پیام‌ها را ببین تا کانال
                    # معطل‌مانده‌ای از اسکن قبلی جا نماند.
                    self.data["exchange"]["scan_last"] = {}
                # ضد اسپم چندگروهی: فاصله تصادفی ۵–۱۵ ثانیه بین اسکن گروه‌ها
                if "scan_jitter_min_sec" not in old_ex:
                    self.data["exchange"]["scan_jitter_min_sec"] = 5
                if "scan_jitter_max_sec" not in old_ex:
                    self.data["exchange"]["scan_jitter_max_sec"] = 15
                if "scan_last_time" not in old_ex:
                    self.data["exchange"]["scan_last_time"] = {}
                # صفِ تک‌عملکردی تبادل: کلیدهای گم‌شده همیشه پر می‌شوند
                # (مهاجرتِ مستقل از v2 تا برای همه‌ی نصب‌ها اعمال شود).
                if "op_gap_min_sec" not in old_ex:
                    self.data["exchange"]["op_gap_min_sec"] = 15
                if "op_gap_max_sec" not in old_ex:
                    self.data["exchange"]["op_gap_max_sec"] = 20
                if old_ex.get("recheck_minutes") in (None, 0):
                    self.data["exchange"]["recheck_minutes"] = 1
                # ── مهاجرت یک‌بار (نسخه ۲) به پیش‌فرض‌های سالم ──
                # نسخه‌های قبلی این مقادیر را «هر استارت» و بدون اجازه‌ی کاربر
                # بازنویسی می‌کردند (مثلاً بررسی ۱۵-۳۰ را ۱۰-۲۰ یا اخطار ۳ را ۱).
                # نتیجه: هیچ تنظیمی نمی‌چسبید و بارِ چک آن‌قدر زیاد بود که اکانت
                # هر ۲۰-۳۰ دقیقه فلود می‌خورد. حالا این مهاجرت:
                #   • فقط یک‌بار (پشت نشانِ _cfg_migrated_v2) اجرا می‌شود؛
                #   • قبلش از فایل تنظیمات یک بکاپِ زمان‌دار گرفته می‌شود؛
                #   • فقط مقدارهایی را که «پیش‌فرض/آلوده‌ی نسخه‌های قبل» هستند به
                #     پیش‌فرض سالم جدید می‌برد؛ مقدار سفارشی کاربر دست نمی‌خورد؛
                #   • بعد از آن هرگز هیچ مقدار موجودی بازنویسی نمی‌شود و فقط
                #     کلیدهای گم‌شده از روی پیش‌فرض‌ها پر می‌شوند.
                if not saved.get("_cfg_migrated_v2"):
                    # بکاپ قبل از هر تغییری: تنظیمات + دیتابیس تبادل
                    backup_settings_file(self.path)
                    try:
                        backup_settings_file(DB_FILE)
                    except Exception:
                        pass
                    ex = self.data["exchange"]
                    # فاصله بررسی عضویت: فقط جفت‌های قدیمی به ۱۵-۳۰ می‌روند
                    pair = (old_ex.get("check_min_sec"), old_ex.get("check_max_sec"))
                    if ("check_min_sec" not in old_ex or "check_max_sec" not in old_ex
                            or pair in ((5, 15), (15, 15), (15, 30), (10, 20))):
                        ex["check_min_sec"] = 15
                        ex["check_max_sec"] = 30
                    if old_ex.get("check_interval_sec") in (None, 15, 20, 30):
                        ex["check_interval_sec"] = 30
                    # لفت فقط بعد از ۲ نبودنِ تأییدشده (نه یک منفیِ تنها)
                    if old_ex.get("max_strikes") in (None, 1, 3):
                        ex["max_strikes"] = 2
                    # نگهبانی عضویت با سقف ۲۴ ساعت (نه «تا ابد»)
                    if old_ex.get("recheck_hours") in (None, 0, 12):
                        ex["recheck_hours"] = 24
                    if "permanent_check" not in old_ex:
                        ex["permanent_check"] = True
                    if old_ex.get("permanent_check_max_hours") in (None, 0):
                        ex["permanent_check_max_hours"] = 24
                    # دو پیام «نیومدی» با فاصله ۲۰-۴۰ ثانیه
                    if old_ex.get("max_reminders") in (None, 1, 3):
                        ex["max_reminders"] = 2
                    rpair = (old_ex.get("reminder_min_sec"), old_ex.get("reminder_max_sec"))
                    if ("reminder_min_sec" not in old_ex or "reminder_max_sec" not in old_ex
                            or rpair in ((5, 15), (5, 5), (15, 15), (10, 20), (20, 40))):
                        ex["reminder_min_sec"] = 20
                        ex["reminder_max_sec"] = 40
                    # کلیدهای گم‌شده از پیش‌فرض پر شوند (بدون بازنویسی مقدار موجود)
                    if "response_delay_sec" not in old_ex:
                        ex["response_delay_sec"] = 15
                    if "initiate" not in old_ex:
                        ex["initiate"] = True
                    if "auto_join" not in old_ex:
                        ex["auto_join"] = True
                    self.data["_cfg_migrated_v2"] = True
                    try:
                        self.save()  # نشان را همین حالا ذخیره کن تا مهاجرت تکرار نشود
                    except Exception:
                        pass
                if not old_ex.get("scan_pick") or old_ex.get("scan_pick") == 2:
                    self.data["exchange"]["scan_pick"] = 1
            except Exception as e:
                print(f"⚠️ خواندن تنظیمات ناموفق: {e}")
        # سقف روزانه Join از این نسخه حذف شده؛ حتی تنظیم قدیمی ۲۰ هم نادیده گرفته می‌شود.
        self.data["exchange"]["max_joins_per_day"] = 0

    def save(self):
        try:
            tmp = self.path + ".tmp"
            with open(tmp, "w", encoding="utf-8") as f:
                json.dump(self.data, f, ensure_ascii=False, indent=2)
            os.replace(tmp, self.path)
        except Exception as e:
            print(f"⚠️ ذخیره ناموفق: {e}")

    def prof(self, tier):
        return self.data["vip" if tier == "vip" else "standard"]

    def __getitem__(self, k):
        return self.data[k]

    def __setitem__(self, k, v):
        self.data[k] = v


# ─────────────────────────────────────────────
#  دیتابیس
# ─────────────────────────────────────────────
SCHEMA = """
CREATE TABLE IF NOT EXISTS queue (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    target TEXT NOT NULL,
    text TEXT NOT NULL,
    tier TEXT NOT NULL DEFAULT 'standard',
    status TEXT NOT NULL DEFAULT 'pending',
    attempts INTEGER NOT NULL DEFAULT 0,
    last_error TEXT,
    created_at INTEGER NOT NULL,
    scheduled_at INTEGER NOT NULL DEFAULT 0,
    sent_at INTEGER,
    message_id INTEGER
);
-- انتخابِ آیتمِ بعدیِ صف با «ORDER BY id LIMIT 1» انجام می‌شود؛ ایندکسِ
-- قبلی (status, tier, scheduled_at) ترتیب را روی scheduled_at می‌داد، پس
-- sqlite مجبور می‌شد کلِ ردیف‌های آن tier را در یک B-Tree موقت مرتب کند
-- (روی ۲۰ هزار ردیف: ~۱۶ms برای هر پیام!). این ایندکس ترتیب را روی id
-- می‌دهد و همان کوئری ۰.۰۰۸ms می‌شود. اندازه‌گیری نشان داد نسخه‌ی
-- سه‌ستونه به‌همان سرعت است و کوچک‌تر؛ و با بودنِ آن، ایندکسِ قدیمی
-- (idx_q) هیچ کوئری‌ای را سریع‌تر نمی‌کرد، پس در مهاجرت پایین حذف می‌شود.
CREATE INDEX IF NOT EXISTS idx_q_pick ON queue(status, tier, id);

CREATE TABLE IF NOT EXISTS exchange (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    peer_id INTEGER,
    peer_name TEXT,
    link TEXT NOT NULL UNIQUE,
    channel_title TEXT,
    status TEXT NOT NULL DEFAULT 'pending',
    strikes INTEGER NOT NULL DEFAULT 0,
    created_at INTEGER NOT NULL,
    joined_at INTEGER,
    last_check INTEGER NOT NULL DEFAULT 0,
    note TEXT,
    src_chat INTEGER,
    src_msg INTEGER,
    replied INTEGER NOT NULL DEFAULT 0,
    direction TEXT NOT NULL DEFAULT 'in',
    reminders INTEGER NOT NULL DEFAULT 0,
    next_reminder INTEGER NOT NULL DEFAULT 0,
    next_check INTEGER NOT NULL DEFAULT 0,
    reminders_total INTEGER NOT NULL DEFAULT 0,
    chat_id INTEGER,
    chat_hash INTEGER,
    leave_fail INTEGER NOT NULL DEFAULT 0,
    leave_blocked_until INTEGER NOT NULL DEFAULT 0,
    peer_joined_at INTEGER
);
CREATE INDEX IF NOT EXISTS idx_ex ON exchange(status, last_check);
CREATE TABLE IF NOT EXISTS events (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    ts INTEGER NOT NULL, level TEXT NOT NULL,
    kind TEXT NOT NULL, detail TEXT
);
"""


class DB:
    def __init__(self, path=DB_FILE):
        self.lock = threading.RLock()
        self.conn = sqlite3.connect(path, check_same_thread=False, timeout=30.0)
        self.conn.row_factory = sqlite3.Row
        self.conn.execute("PRAGMA journal_mode=WAL")
        self.conn.execute("PRAGMA busy_timeout = 30000")
        # پیش‌فرضِ sqlite برای هر اتصال ~۲ مگابایت کش می‌گیرد (۲۰۰۰ صفحه).
        # با ۱۰۰ اکانت یعنی ۲۰۰ مگابایت فقط کشِ دیتابیس. این سلف کوئریِ
        # سنگین ندارد؛ ۴۰۰ صفحه (۱.۶ مگابایت کمتر برای هر اکانت) کافی است.
        try:
            self.conn.execute("PRAGMA cache_size = -400")
            self.conn.execute("PRAGMA mmap_size = 0")
        except Exception:
            pass
        with self.lock:
            self.conn.executescript(SCHEMA)
            # مهاجرت: ستون‌های جدید روی دیتابیس قدیمی
            have = {r[1] for r in self.conn.execute("PRAGMA table_info(exchange)")}
            for col, decl in (("src_chat", "INTEGER"), ("src_msg", "INTEGER"),
                              ("replied", "INTEGER NOT NULL DEFAULT 0"),
                              ("direction", "TEXT NOT NULL DEFAULT 'in'"),
                              ("reminders", "INTEGER NOT NULL DEFAULT 0"),
                              ("next_reminder", "INTEGER NOT NULL DEFAULT 0"),
                              ("next_check", "INTEGER NOT NULL DEFAULT 0"),
                              ("reminders_total", "INTEGER NOT NULL DEFAULT 0"),
                              ("claim_joined", "INTEGER NOT NULL DEFAULT 0"),
                              ("unk_streak", "INTEGER NOT NULL DEFAULT 0"),
                              ("chat_id", "INTEGER"), ("chat_hash", "INTEGER"),
                              ("leave_fail", "INTEGER NOT NULL DEFAULT 0"),
                              ("leave_blocked_until", "INTEGER NOT NULL DEFAULT 0"),
                              # «طرف برگشت و جوینِ کانال من شد» — فقط برای
                              # رکوردهای پیش‌قدم (direction='out') پر می‌شود؛
                              # ستون آمارِ «جذب موفق» از همین ساخته می‌شود.
                              ("peer_joined_at", "INTEGER")):
                if col not in have:
                    self.conn.execute(f"ALTER TABLE exchange ADD COLUMN {col} {decl}")
            # بعد از مهاجرت ساخته شود؛ وگرنه دیتابیس قدیمی هنوز ستون next_check ندارد.
            self.conn.execute("CREATE INDEX IF NOT EXISTS idx_ex_next_check "
                              "ON exchange(status, next_check)")
            # ایندکس‌های زیر فقط سرعت‌اند، نه داده. هرکدام جدا و در
            # try/except ساخته می‌شوند تا یک دیتابیسِ عجیب/خراب هرگز
            # جلوی بالا آمدنِ سلف‌بات را نگیرد.
            for _dml in (
                # یادآورها با (status IN (pending,joined) AND next_reminder<=?)
                # خوانده می‌شوند؛ بدونِ این ایندکس هر بار کلِ جدول اسکن
                # می‌شد (روی ۲۰ هزار رکورد ~۱۵ms در هر دورِ حلقه).
                "CREATE INDEX IF NOT EXISTS idx_ex_rem "
                "ON exchange(status, next_reminder)",
                # برای هر پیامِ ورودی از یک طرف، ex_by_peer آخرین رکوردش را
                # می‌خواهد؛ بدونِ این ایندکس کلِ جدول پیمایش می‌شد
                # (اندازه‌گیری روی ۵۰ هزار رکورد: ۱.۲ تا ۲.۳ms → ۰.۰۱ms).
                "CREATE INDEX IF NOT EXISTS idx_ex_peer "
                "ON exchange(peer_id)",
                # ایندکسِ قدیمیِ صف دیگر به کاری نمی‌آید و فقط حجم و
                # زمانِ نوشتن را زیاد می‌کند (اندازه‌گیری‌شده).
                "DROP INDEX IF EXISTS idx_q",
            ):
                try:
                    self.conn.execute(_dml)
                except Exception:
                    pass
            # اگر دیتابیس از نسخه‌ی قبل ایندکسِ چهارستونه‌ی صف را دارد،
            # به نسخه‌ی سه‌ستونه (هم‌سرعت، کم‌حجم‌تر) تبدیل شود.
            try:
                _cols = [r[2] for r in
                         self.conn.execute("PRAGMA index_info(idx_q_pick)")]
                if _cols and _cols != ["status", "tier", "id"]:
                    self.conn.execute("DROP INDEX idx_q_pick")
                    self.conn.execute("CREATE INDEX idx_q_pick "
                                      "ON queue(status, tier, id)")
            except Exception:
                pass
            self.conn.commit()

    def _x(self, sql, a=(), f=None):
        with self.lock:
            c = self.conn.execute(sql, a)
            if f == "one":
                r = c.fetchone()
                return dict(r) if r else None
            if f == "all":
                return [dict(r) for r in c.fetchall()]
            self.conn.commit()
            return c.lastrowid

    def _pick(self, sql_forced, sql_plain, a=(), f="all"):
        """اجرای کوئری با ایندکسِ اجباری؛ اگر ایندکس موجود نبود (دیتابیسِ
        دست‌کاری‌شده) همان کوئری بدونِ اجبار اجرا می‌شود تا هیچ‌وقت خطا ندهد."""
        try:
            return self._x(sql_forced, a, f)
        except sqlite3.OperationalError:
            return self._x(sql_plain, a, f)

    def enqueue(self, target, text, tier="standard", when=0):
        now = int(time.time())
        return self._x("INSERT INTO queue (target,text,tier,created_at,scheduled_at)"
                       " VALUES (?,?,?,?,?)", (target, text, tier, now, when or now))

    def next_pending(self, tier):
        """آیتم‌های بدون مقصد نگه داشته می‌شوند تا کانال تعیین شود.

        این کوئری داغ‌ترین کوئریِ صف است (هر پیام یک بار). با ایندکسِ
        ``idx_q_pick`` ترتیب روی ``id`` می‌آید و sqlite دیگر لازم نیست همه‌ی
        ردیف‌های هم‌tier را مرتب کند؛ اندازه‌گیری روی ۲۰ هزار ردیف:
        ۶.۷ میلی‌ثانیه → ۰.۰۰۸ میلی‌ثانیه."""
        return self._pick(
            "SELECT * FROM queue INDEXED BY idx_q_pick WHERE status='pending'"
            " AND tier=? AND target<>'' AND scheduled_at<=? ORDER BY id LIMIT 1",
            "SELECT * FROM queue WHERE status='pending' AND tier=?"
            " AND target<>'' AND scheduled_at<=? ORDER BY id LIMIT 1",
            (tier, int(time.time())), "one")

    def held_count(self, tier=None):
        """پیام‌هایی که منتظر تعیین کانال‌اند."""
        if tier:
            return self._x("SELECT COUNT(*) c FROM queue WHERE status='pending'"
                           " AND target='' AND tier=?", (tier,), "one")["c"]
        return self._x("SELECT COUNT(*) c FROM queue WHERE status='pending'"
                       " AND target=''", (), "one")["c"]

    def assign_target(self, tier, channel):
        """وقتی کانال تعیین شد، پیام‌های معلق همان بخش آزاد می‌شوند."""
        with self.lock:
            c = self.conn.execute("UPDATE queue SET target=? WHERE status='pending'"
                                  " AND target='' AND tier=?", (channel, tier))
            self.conn.commit()
            return c.rowcount

    def retarget_pending(self, tier, old_channel, new_channel):
        """پیام‌های صف‌مانده را از کانال قبلی به کانال جدید منتقل می‌کند."""
        if not old_channel or old_channel == new_channel:
            return 0
        with self.lock:
            c = self.conn.execute(
                "UPDATE queue SET target=? WHERE status='pending' AND tier=? AND target=?",
                (new_channel, tier, old_channel))
            self.conn.commit()
            return c.rowcount

    def mark_sent(self, qid, mid=None):
        self._x("UPDATE queue SET status='sent',sent_at=?,message_id=? WHERE id=?",
                (int(time.time()), mid, qid))

    def mark_failed(self, qid, err, retry_at=None, mx=3):
        r = self._x("SELECT attempts FROM queue WHERE id=?", (qid,), "one")
        n = (r["attempts"] if r else 0) + 1
        if retry_at and n < mx:
            self._x("UPDATE queue SET attempts=?,last_error=?,scheduled_at=?,"
                    "status='pending' WHERE id=?", (n, str(err)[:400], int(retry_at), qid))
        else:
            self._x("UPDATE queue SET attempts=?,last_error=?,status='failed' WHERE id=?",
                    (n, str(err)[:400], qid))

    def counts(self):
        return {r["status"]: r["c"] for r in
                self._x("SELECT status,COUNT(*) c FROM queue GROUP BY status", (), "all")}

    def pending_count(self, tier=None):
        if tier:
            return self._x("SELECT COUNT(*) c FROM queue WHERE status='pending'"
                           " AND tier=?", (tier,), "one")["c"]
        return self._x("SELECT COUNT(*) c FROM queue WHERE status='pending'",
                       (), "one")["c"]

    def list_pending(self, n=10):
        return self._pick(
            "SELECT * FROM queue INDEXED BY idx_q_pick WHERE status='pending'"
            " ORDER BY id LIMIT ?",
            "SELECT * FROM queue WHERE status='pending' ORDER BY id LIMIT ?",
            (n,), "all")

    def clear_pending(self):
        with self.lock:
            c = self.conn.execute("DELETE FROM queue WHERE status='pending'")
            self.conn.commit()
            return c.rowcount

    def delete_item(self, qid):
        with self.lock:
            c = self.conn.execute("DELETE FROM queue WHERE id=? AND status='pending'",
                                  (qid,))
            self.conn.commit()
            return c.rowcount

    def retry_failed(self):
        with self.lock:
            c = self.conn.execute("UPDATE queue SET status='pending',attempts=0,"
                                  "scheduled_at=? WHERE status='failed'",
                                  (int(time.time()),))
            self.conn.commit()
            return c.rowcount

    def sent_since(self, ts):
        return self._x("SELECT COUNT(*) c FROM queue WHERE status='sent' AND sent_at>=?",
                       (ts,), "one")["c"]

    # ---------- تبادل ----------
    def ex_add(self, peer_id, peer_name, link):
        """برمی‌گرداند (رکورد, آیا_جدید_بود)"""
        cur = self.ex_by_link(link)
        if cur:
            if peer_id and not cur.get("peer_id"):
                self.ex_set(cur["id"], peer_id=peer_id, peer_name=peer_name)
                cur = self.ex_get(cur["id"])
            return cur, False
        self._x("INSERT INTO exchange (peer_id,peer_name,link,created_at)"
                " VALUES (?,?,?,?)", (peer_id, peer_name, link, int(time.time())))
        return self.ex_by_link(link), True

    def ex_by_link(self, link):
        if not link:
            return None
        r = self._x("SELECT * FROM exchange WHERE link=?", (link,), "one")
        if r:
            return r
        return self._x("SELECT * FROM exchange WHERE lower(link)=lower(?)",
                       (link,), "one")

    def ex_by_peer(self, peer_id):
        """آخرین رکورد تبادلی که کانالِ این طرف در آن ثبت شده است.
        برای اینکه «نیومدی» فقط به کسی برود که واقعاً کانالش را ثبت
        کرده — نه به هر ریپلای‌کننده‌ی تصادفی."""
        if not peer_id:
            return None
        try:
            pid = int(peer_id)
        except (TypeError, ValueError):
            return None
        return self._x("SELECT * FROM exchange WHERE peer_id=?"
                       " ORDER BY id DESC LIMIT 1", (pid,), "one")

    def ex_get(self, eid):
        return self._x("SELECT * FROM exchange WHERE id=?", (eid,), "one")

    def ex_find(self, key):
        """با آیدی عددی یا لینک/یوزرنیم پیدا کن"""
        try:
            r = self.ex_get(num(key))
            if r:
                return r
        except (ValueError, TypeError):
            pass
        k = key.strip().lstrip("@").lower()
        return self._x("SELECT * FROM exchange WHERE lower(link) LIKE ?"
                       " ORDER BY id DESC LIMIT 1", (f"%{k}%",), "one")

    def ex_set(self, eid, **kw):
        if not kw:
            return
        cols = ",".join(f"{k}=?" for k in kw)
        self._x(f"UPDATE exchange SET {cols} WHERE id=?",
                tuple(kw.values()) + (eid,))

    def ex_list(self, status=None, limit=30):
        if status:
            return self._x("SELECT * FROM exchange WHERE status=? ORDER BY id DESC"
                           " LIMIT ?", (status, limit), "all")
        return self._x("SELECT * FROM exchange ORDER BY id DESC LIMIT ?",
                       (limit,), "all")

    def ex_same_channel_left(self, rec):
        """رکوردِ دیگری که «همین کانال» را قبلاً لفت داده است.

        چرا لازم است: طرف می‌تواند برای یک کانال دو لینک ثبت کند
        (مثلاً `@chan` و `t.me/+hash`) و دو رکورد بسازد. هر دو رکورد
        `chat_id` یکسان می‌گیرند؛ بعد از لفتِ اولی، لفتِ دومی خطای
        «عضو نیستی» می‌دهد که در `leave_link` موفق حساب می‌شود — یعنی
        پیام «👋 لفت انجام شد» برای یک کانال دو بار می‌رفت. با این چک،
        رکوردِ دوم بی‌صدا بسته می‌شود.
        """
        cid = (rec or {}).get("chat_id")
        if not cid:
            return None
        return self._x("SELECT * FROM exchange WHERE id<>? AND chat_id=?"
                       " AND status='left' ORDER BY id LIMIT 1",
                       (int(rec.get("id") or 0), int(cid)), "one")

    def ex_due(self, ts, limit=15):
        """تبادل‌های انجام‌شده‌ای که زمان بررسی بعدی‌شان رسیده است.
        next_check برای فاصله تصادفی جدید است؛ last_check پشتیبان دیتابیس قدیمی است.
        """
        return self._x(
            "SELECT * FROM exchange WHERE status='joined' AND "
            "((next_check>0 AND next_check<=?) OR "
            " (next_check=0 AND last_check<=?)) "
            "ORDER BY CASE WHEN next_check>0 THEN next_check ELSE last_check END "
            "LIMIT ?", (ts, ts, limit), "all")

    def ex_reminder_due(self, ts, limit=20):
        """رکوردهایی که نوبتِ پیام «نیومدی» یا لفتِ بعدی‌شان رسیده است.
        pending = تبادل هنوز انجام نشده؛ joined = پیش‌قدمی که قبلاً جوین
        کرده‌ام و طرف ادعای جوین کرده ولی عضو نیست."""
        return self._x("SELECT * FROM exchange WHERE status IN ('pending','joined')"
                       " AND peer_id IS NOT NULL"
                       " AND next_reminder>0 AND next_reminder<=?"
                       " ORDER BY next_reminder LIMIT ?", (ts, limit), "all")

    def ex_counts(self):
        return {r["status"]: r["c"] for r in
                self._x("SELECT status,COUNT(*) c FROM exchange GROUP BY status",
                        (), "all")}

    def ex_report_counts(self, since):
        """آمار تبادل برای گزارش خصوصی، از timestamp داده‌شده تا الان."""
        since = int(since or 0)
        q = lambda sql, args=(): int(self._x(sql, args, "one")["c"])
        return {
            "joined": q("SELECT COUNT(*) c FROM exchange WHERE joined_at IS NOT NULL AND joined_at>=?", (since,)),
            "out_joined": q("SELECT COUNT(*) c FROM exchange WHERE direction='out' AND joined_at IS NOT NULL AND joined_at>=?", (since,)),
            # «جذب موفق» = تبادل‌هایی که کسی عضوِ کانال من شد.
            #   • جهتِ in  → طرف اول آمد و من بعداً جوینِ کانال او شدم.
            #   • جهتِ out → من پیش‌قدم شدم؛ طرف وقتی برگشت و جوینِ کانال
            #     من شد (peer_joined_at) — تا قبل از این ستون، این حالت
            #     هیچ‌جا شمرده نمی‌شد و «جذب موفق» همیشه صفر می‌ماند.
            # هر رکورد فقط یک‌بار شمرده می‌شود (COUNT روی ردیف است، نه جمع دو کوئری).
            "in_joined": q("SELECT COUNT(*) c FROM exchange"
                           " WHERE (direction='in' AND joined_at IS NOT NULL AND joined_at>=?)"
                           " OR (peer_joined_at IS NOT NULL AND peer_joined_at>=?)",
                           (since, since)),
            "left": q("SELECT COUNT(*) c FROM events WHERE kind='ex_left' AND ts>=?", (since,)),
            "failed": q("SELECT COUNT(*) c FROM events WHERE kind='ex_join_fail' AND ts>=?", (since,)),
            "pending": q("SELECT COUNT(*) c FROM exchange WHERE status='pending'"),
            "approved": q("SELECT COUNT(*) c FROM exchange WHERE status='approved'"),
            "not_returned": q("SELECT COUNT(*) c FROM exchange WHERE direction='out' AND status='joined' AND strikes>0"),
        }

    def ex_joins_today(self):
        start = int(time.mktime(datetime.now().replace(
            hour=0, minute=0, second=0, microsecond=0).timetuple()))
        return self._x("SELECT COUNT(*) c FROM exchange WHERE joined_at>=?",
                       (start,), "one")["c"]

    # ---------- محافظ ریپورت ----------
    def ex_delete(self, eid):
        with self.lock:
            c = self.conn.execute("DELETE FROM exchange WHERE id=?", (eid,))
            self.conn.commit()
            return c.rowcount

    def log(self, lvl, kind, detail=""):
        self._x("INSERT INTO events (ts,level,kind,detail) VALUES (?,?,?,?)",
                (int(time.time()), lvl, kind, str(detail)[:600]))

    def recent(self, n=15):
        return self._x("SELECT * FROM events ORDER BY id DESC LIMIT ?", (n,), "all")


# ─────────────────────────────────────────────
#  کنترل نرخ ارسال
# ─────────────────────────────────────────────
class CheckGate:
    """پاس‌گاه سراسری درخواست‌های «بررسی عضویت» (GetParticipantRequest).

    چک نگهبانیِ هر رکورد با فاصله‌ی تصادفی (پیش‌فرض ۱۵–۳۰ ثانیه که با سنِ
    رکورد پلکانی بلند می‌شود) با N رکورد یعنی چند درخواست در دقیقه — و سه
    مسیر همزمان (حلقه‌ی یادآوری، چک دوره‌ای، پیام ورودی) بدون هماهنگی
    می‌زدند؛ نتیجه‌اش FloodWait «بی‌دلیل» بود. این پاس‌گاه
    همه‌ی مسیرها را از یک دریچه رد می‌کند:
      • حداقل فاصله بین دو درخواست؛ با تعداد رکوردها خودکار بلندتر می‌شود
      • روی FloodWait، کل بررسی‌ها تا پایان سقف متوقف می‌شود (نه اینکه
        بقیه‌ی رکوردها هم پشت‌سرهم فلود بخورند)
      • بعد از چند دقیقه بدون Flood، فاصله کم‌کم برمی‌گردد
    """

    def __init__(self, base_gap=1.5):
        self.base_gap = float(base_gap)
        self.flood_extra = 0.0
        self.last = 0.0
        self.cooldown_until = 0.0
        self.last_flood = 0.0
        self.last_decay = 0.0

    def gap(self):
        return self.base_gap + self.flood_extra

    def wait(self, now=None):
        now = now if now is not None else time.time()
        if now < self.cooldown_until:
            return self.cooldown_until - now
        return max(0.0, (self.last + self.gap()) - now)

    def record(self, now=None):
        now = now if now is not None else time.time()
        self.last = now

    def penalize(self, sec, now=None):
        """FloodWait خورد → سقف سراسری + فاصله‌ی بلندتر دائمی (تا سقف ۲۰ث)."""
        now = now if now is not None else time.time()
        w = float(sec)
        self.flood_extra = min(20.0, self.flood_extra + 1.5)
        self.cooldown_until = max(self.cooldown_until, now + w + 2.0)
        self.last_flood = now
        self.last_decay = now

    def set_load(self, records):
        """با رکوردهای بیشتر، فاصله‌ی پایه بلندتر — پخش عادلانه‌ی چک.
        ۱۰ رکورد → ~۶ثانیه بین درخواست‌ها، ۵۰ رکورد → سقف ۸ ثانیه.
        یعنی هر رکورد عملاً هر (records × gap) ثانیه یک‌بار چک می‌شود."""
        n = max(0, int(records))
        self.base_gap = min(8.0, max(1.5, 0.6 * n))

    def maybe_decay(self, now=None):
        """هر ۵ دقیقه بدون Flood، ۱ ثانیه از فاصله‌ی اضافه کم کن."""
        now = now if now is not None else time.time()
        if self.flood_extra <= 0:
            return
        if self.last_flood and now - self.last_flood < 300:
            return
        if (self.last_decay or self.last_flood) and \
                now - (self.last_decay or self.last_flood) < 300:
            return
        self.flood_extra = max(0.0, self.flood_extra - 1.0)
        self.last_decay = now

    def blocked(self, now=None):
        now = now if now is not None else time.time()
        return now < self.cooldown_until


class ExCooldown:
    """صفِ «تک‌عملکردی» تبادل + خنک‌کننده‌ی بین عملکرد‌ها.

    باگی که این کلاس می‌بندد: چند مسیر همزمان (پیامِ «جوین شدم»ِ طرف،
    حلقه‌ی یادآوری «نیومدی»، چک نگهبانی عضویت، کارگر صفِ جوین) هیچ‌کدام
    از کارِ بقیه خبر نداشتند و روی **یک رکورد** پشت‌سرهم عملیات می‌زدند؛
    نتیجه‌اش این بود که جوین → چک → «نیومدی» → «نیومدی» دوم → لفت همه
    در یک لحظه (صدم‌ثانیه) اتفاق می‌افتاد و طرف اصلاً فرصت جوین‌شدن نداشت.

    سه کاری که می‌کند:

      ۱) قفل سراسری عملکرد‌ها — در هر لحظه فقط **یک** عملکردِ تبادل
         (چک عضویت، جوین، لفت، ارسال پیام) اجرا می‌شود. عملکردِ بعدی تا
         تمام‌شدنِ قبلی منتظر می‌ماند.

      ۲) فاصله‌ی سراسری — بعد از تمام‌شدن هر عملکرد، یک فاصله‌ی تصادفی
         (پیش‌فرض ۱۵–۲۰ ثانیه) قبل از عملکردِ بعدی صبر می‌شود.

      ۳) خنک‌کننده‌ی هر رکورد — برای هر رکورد تبادل زمانِ «آخرین عملکردِ
         تمام‌شده» نگه داشته می‌شود؛ رکوردی که تازه چک/جوین/پیام گرفته،
         تا پایانِ همان فاصله دوباره چک یا پیام نمی‌گیرد. پس چکِ عضویتِ
         بلافاصله بعد از جوین («آیا واقعاً جوین شده؟») زودتر از ۱۵–۲۰
         ثانیه انجام نمی‌شود و دو پیام «نیومدی» هرگز پشت‌سرهم نمی‌روند.

    نکته‌ی طراحی: صبرهای طولانیِ انسانی (تأخیر پیام «بیا»، فاصله‌ی چک دوم)
    بیرونِ قفل سراسری انجام می‌شوند تا کل ربات را قفل نکنند؛ فقط خودِ
    عملیاتِ تلگرام (درخواست/ارسال) زیر قفل است. خنک‌کننده‌ی رکورد مستقل از
    قفل کار می‌کند، پس نظمِ زمانی حتی وقتی عملیات سریع است هم حفظ می‌شود.
    """

    def __init__(self, cfg=None, gap_min=15.0, gap_max=20.0, now=None):
        self._cfg = cfg
        self.gap_min = float(gap_min)
        self.gap_max = float(gap_max)
        self.lock = asyncio.Lock()      # قفل سراسری عملکرد‌ها
        self._lock = self.lock
        # رکوردهایی که همین الان عملکردشان در صف/جریان است؛ wait_for برای
        # این‌ها «صبر کن» می‌دهد تا دو مسیر همزمان روی یک رکورد کار نکنند.
        self._busy = set()
        self._last_done = {}        # رکورد → زمانِ تمام‌شدنِ آخرین عملکرد
        self._last_kind = {}        # رکورد → نوعِ آخرین عملکرد (check/join/…)
        self._order = []            # برای هرسِ حافظه
        self.last_global_done = 0.0
        self.blocked_until = 0.0
        if now is not None:
            self.last_global_done = float(now)

    # ── تنظیم‌ها ──
    def configure(self, lo, hi):
        """بازه‌ی فاصله را از تنظیم‌ها می‌گیرد (هیچ‌وقت وارونه یا منفی نمی‌شود)."""
        try:
            lo = float(lo)
            hi = float(hi)
        except (TypeError, ValueError):
            return
        self.gap_min = max(0.0, min(3600.0, lo))
        self.gap_max = max(self.gap_min, min(3600.0, hi))

    def apply_config(self):
        """هر بار از تنظیم‌های فعلی موتور خوانده می‌شود تا دستورِ کاربر اثر کند."""
        if self._cfg is None:
            return
        try:
            x = self._cfg()
            self.configure(x.get("op_gap_min_sec", 15), x.get("op_gap_max_sec", 20))
        except Exception:
            pass

    def seconds(self):
        """یک فاصله‌ی تصادفیِ تازه از بازه‌ی تنظیم‌شده."""
        self.apply_config()
        lo, hi = self.gap_min, self.gap_max
        if hi <= lo:
            return lo
        return random.uniform(lo, hi)

    def floor_seconds(self):
        """کفِ فاصله (کمینه‌ی بازه) — برای زمان‌بندی‌های قطعی."""
        self.apply_config()
        return self.gap_min

    # ── وضعیتِ یک رکورد ──
    def since_done(self, rec_id, now=None):
        """چند ثانیه از آخرین عملکردِ تمام‌شده‌ی این رکورد گذشته است."""
        if not rec_id:
            return None
        now = time.time() if now is None else float(now)
        last = self._last_done.get(int(rec_id))
        if last is None:
            return None
        return now - float(last)

    def wait_for(self, rec_id, now=None):
        """چند ثانیه دیگر باید صبر کرد تا نوبتِ این رکورد برسد (۰ = آماده)."""
        if not rec_id:
            return 0.0
        now = time.time() if now is None else float(now)
        rid = int(rec_id)
        if rid in self._busy:
            # عملکردی روی همین رکورد در جریان است — تا تمام‌شدنش صبر کن.
            return max(1.0, self.gap_min)
        left = self.since_done(rid, now)
        if left is None:
            return 0.0
        # کفِ بازه (نه عدد تصادفی) مبناست تا «چقدر مانده» پایدار بماند؛
        # خودِ زمان‌بندیِ نوبتِ بعدی (next_action_after) تصادفی است.
        need = self.floor_seconds()
        return max(0.0, need - left) if left < need else 0.0

    def ready(self, rec_id, now=None):
        return self.wait_for(rec_id, now) <= 0.0

    def last_kind(self, rec_id):
        """نوعِ آخرین عملکردِ تمام‌شده روی این رکورد ("" اگر هیچی).

        دروازه‌ی ارسال «نیومدی» با این فرق می‌گذارد بین:
          • «پیامِ تکراری درجا پشتِ پیام/جوین/لفتِ قبلی» → باید رد شود
            و نوبتش به بعد منتقل شود؛
          • «ادامه‌ی همان نوبت بعد از چکِ بی‌صدای عضویت» → چک و پیامِ
            بعدش دو نیمه‌ی یک نوبت‌اند؛ اگر این هم رد شود، حلقه‌ی
            یادآوری که هر نوبت اول چک می‌کند، هیچ‌وقت به ارسال نمی‌رسد
            (باگِ «گفت دارم چک می‌کنم و دیگر هیچی نگفت»).
        """
        if not rec_id:
            return ""
        try:
            return self._last_kind.get(int(rec_id), "") or ""
        except (TypeError, ValueError):
            return ""

    def defer_if_due(self, rec, due_ts, now=None):
        """رکوردِ سررسیدشده را اگر در خنک‌کننده/صف است به زمانِ درست منتقل می‌کند.

        خروجی: ``(False, زمان_جدید)`` یعنی «الان نه» و زمانِ پیشنهادی برای
        ست‌کردنِ ``next_reminder``/``next_check``؛ ``(True, 0)`` یعنی آزاد است.
        """
        if not rec:
            return True, 0
        now = time.time() if now is None else float(now)
        w = self.wait_for(rec.get("id"), now)
        if w <= 0:
            return True, 0
        try:
            base = max(float(now), float(due_ts or 0))
        except (TypeError, ValueError):
            base = now
        return False, int(base + max(1.0, w))

    # ── اجرای یک عملکرد در صف سراسری ──
    async def action(self, kind, rec_id=None, fn=None, *a, **kw):
        """عملکرد را در صفِ سراسری اجرا می‌کند و خنک‌کننده‌ها را ثبت می‌کند.

        ترتیب: (۱) اگر این رکورد خنک‌کننده دارد → صبر؛ (۲) قفل سراسری →
        اگر از پایانِ آخرین عملکرد (سراسری یا همین رکورد) کمتر از فاصله
        گذشته باشد → صبر؛ (۳) اجرا؛ (۴) ثبتِ زمانِ پایان برای رکورد و
        برای کل صف.

        نکته: فاصله **دوبار** جمع نمی‌شود. اگر خنک‌کننده‌ی رکورد به‌اندازه‌ی
        کافی صبر کرده باشد، در قفل سراسری دیگر صبرِ اضافه نمی‌خورد؛ یعنی
        از پایانِ عملکردِ قبلی دقیقاً یک فاصله (پیش‌فرض ۱۵–۲۰ ثانیه) می‌گذرد.
        """
        self.apply_config()
        rid = int(rec_id) if rec_id else None
        # ۱) خنک‌کننده‌ی خودِ رکورد: اگر همین رکورد تازه چک/جوین/پیام گرفته،
        #    ابتدا همان‌قدر صبر می‌شود (پیش از صف رفتن).
        if rid is not None:
            w = self.wait_for(rid)
            if w > 0:
                await asyncio.sleep(w)
        # ۲) صفِ سراسری
        async with self._lock:
            # مبنای «آخرین عملکرد» را **داخل** قفل می‌خوانیم؛ اگر بیرون
            # خوانده شود، نوبتی که پشتِ قفل معطل مانده با مبنای کهنه صفر
            # حساب می‌کند و عملکردِ بعدی درجا پشتِ قبلی می‌رود.
            ref = self.last_global_done
            if rid is not None:
                ref = max(ref, float(self._last_done.get(rid, 0.0) or 0.0))
            # زمان سپری‌شده همین حالا در time.time لحاظ شده؛ دوباره کم نکن.
            w = max(ref + self.seconds(), self.blocked_until) - time.time()
            if w > 0:
                await asyncio.sleep(w)
            try:
                if fn is None:
                    return None
                if asyncio.iscoroutinefunction(fn):
                    return await fn(*a, **kw)
                return fn(*a, **kw)
            except Exception as e:
                if kind != "check" and type(e).__name__ in ("FloodWaitError", "FloodPremiumWaitError"):
                    self.blocked_until = max(self.blocked_until,
                                             time.time() + getattr(e, "seconds", 60) + 2)
                raise
            finally:
                done = time.time()
                self.last_global_done = done
                if rid is not None:
                    self._last_done[rid] = done
                    self._last_kind[rid] = kind
                    self._order.append(rid)
                    if len(self._order) > 600:
                        for k in self._order[:200]:
                            self._last_done.pop(k, None)
                            self._last_kind.pop(k, None)
                        del self._order[:200]

    def note_done(self, rec_id=None, now=None):
        """پایانِ یک عملکرد را ثبت می‌کند بدون اینکه فاصله‌ی صف را تحمیل کند.

        برای درخواستی است که ادامه‌ی همان عملکرد قبلی محسوب می‌شود (چکِ دومِ
        تأییدیِ عضویت): فاصله‌ی واقعی را خودش داده (۱۵–۳۰ ثانیه)، پس یک
        فاصله‌ی صفِ اضافه فقط توانِ کل را نصف می‌کرد.
        """
        now = time.time() if now is None else float(now)
        self.last_global_done = now
        if not rec_id:
            return
        rid = int(rec_id)
        self._last_done[rid] = now
        # ادامه‌ی همان چکِ عضویت است؛ نوع عملکرد «check» می‌ماند تا
        # دروازه‌ی ارسال بداند پیامِ بعدی ادامه‌ی همان نوبت است.
        self._last_kind[rid] = "check"
        self._order.append(rid)
        if len(self._order) > 600:
            for k in self._order[:200]:
                self._last_done.pop(k, None)
                self._last_kind.pop(k, None)
            del self._order[:200]

    def mark_done(self, rec_id, now=None):
        """زمانِ پایانِ عملکردِ یک رکورد را دستی ثبت می‌کند (مثلاً بعد از جوین)."""
        if not rec_id:
            return
        now = time.time() if now is None else float(now)
        rid = int(rec_id)
        self._last_done[rid] = now
        self._order.append(rid)
        self.last_global_done = max(self.last_global_done, now)
        if len(self._order) > 600:
            for k in self._order[:200]:
                self._last_done.pop(k, None)
                self._last_kind.pop(k, None)
            del self._order[:200]

    def reset(self, rec_id=None):
        """خنک‌کننده را پاک می‌کند (برای رکوردِ تازه یا تست)."""
        if rec_id:
            self._last_done.pop(int(rec_id), None)
            self._last_kind.pop(int(rec_id), None)
            self._busy.discard(int(rec_id))
        else:
            self._last_done.clear()
            self._last_kind.clear()
            self._busy.clear()
            self._order.clear()
            self.last_global_done = 0.0
        self.blocked_until = 0.0

    def status_text(self):
        self.apply_config()
        return (f"صف عملکرد: فاصله {fa(int(self.gap_min))}–{fa(int(self.gap_max))} "
                f"ثانیه تصادفی بین دو عملکرد | "
                f"رکوردهای در خنک‌کننده: {fa(len(self._last_done))}")


class Throttle:
    def __init__(self, p):
        self.apply(p)
        self.last = 0.0
        self.hist = []
        self.blocked_until = 0.0
        self.next_gap = self.min_gap

    def apply(self, p):
        self.min_gap = max(1, int(p["min_gap_sec"]))
        self.max_gap = max(self.min_gap, int(p["max_gap_sec"]))
        self.cap = max(0, int(p["max_per_hour"]))
        if hasattr(self, "next_gap"):
            self.next_gap = min(max(self.next_gap, self.min_gap), self.max_gap)

    def wait_time(self, now=None):
        now = now if now is not None else time.time()
        if now < self.blocked_until:
            return self.blocked_until - now
        gap = max(0.0, (self.last + self.next_gap) - now) if self.last else 0.0
        self.hist = [t for t in self.hist if t > now - 3600]
        if self.cap and len(self.hist) >= self.cap:
            gap = max(gap, (min(self.hist) + 3600) - now)
        return gap

    def record(self, now=None):
        now = now if now is not None else time.time()
        self.last = now
        self.hist.append(now)
        self.next_gap = (random.uniform(self.min_gap, self.max_gap)
                         if self.max_gap > self.min_gap else self.min_gap)

    def penalize(self, sec):
        self.blocked_until = time.time() + float(sec) + 1

    def sent_last_hour(self):
        now = time.time()
        self.hist = [t for t in self.hist if t > now - 3600]
        return len(self.hist)


# ─────────────────────────────────────────────
#  چرخه فعالیت / استراحت
# ─────────────────────────────────────────────
class Cycle:
    def __init__(self, p):
        self.anchor = time.time()
        self.apply(p)

    def apply(self, p):
        self.mode = p["mode"]
        self.active = max(1, int(p["active_minutes"]))
        self.rest = max(0, int(p["rest_minutes"]))
        self.quiet = set(p.get("quiet_hours") or [])

    def reset(self):
        self.anchor = time.time()

    def phase(self, now=None):
        now = now if now is not None else time.time()
        d = datetime.fromtimestamp(now)
        if self.quiet and d.hour in self.quiet:
            return "quiet", 3600 - (d.minute * 60 + d.second)
        if self.mode == "always" or self.rest == 0:
            return "active", 0
        period = (self.active + self.rest) * 60
        act = self.active * 60
        pos = (now - self.anchor) % period
        return ("active", act - pos) if pos < act else ("rest", period - pos)

    def label(self):
        p, rem = self.phase()
        if p == "active":
            return f"🟢 فعال — تا شروع استراحت: {secs(rem)}" if rem else "🟢 فعال"
        if p == "rest":
            return f"😴 استراحت — تا شروع فعالیت: {secs(rem)}" if rem else "😴 استراحت"
        return f"🌙 ساعت سکوت — تا پایان: {secs(rem)}" if rem else "🌙 ساعت سکوت"


# ─────────────────────────────────────────────
#  سقف‌های پلن  (اگر فایلش نباشد، هیچ محدودیتی نیست)
# ─────────────────────────────────────────────
LIMIT_DEFAULTS = {
    "plan": "",
    "max_channels": 0,
    "max_per_hour": 0,
    "min_gap_sec": 0,
    "exchange": True,
    "initiate": True,
    "max_joins_per_day": 0,
    "ai": True,
    "points": 0,
    "hours_left": 0,
    "points_mode": False,
    "expires_at": 0,
}


class Limits:
    def __init__(self, path=LIMITS_FILE):
        self.path = path
        self.d = dict(LIMIT_DEFAULTS)
        self.active = False
        self.load()

    def load(self):
        if not os.path.exists(self.path):
            return
        try:
            with open(self.path, encoding="utf-8") as f:
                self.d.update(json.load(f))
            # حالت پیش‌قدم در این نسخه برای همه پلن‌ها آزاد است.
            self.d["initiate"] = True
            # محدودیت روزانه Join عمداً وجود ندارد.
            self.d["max_joins_per_day"] = 0
            self.active = True
        except Exception as e:
            print(f"⚠️ خواندن {self.path}: {e}")

    def __getitem__(self, k):
        return self.d.get(k, LIMIT_DEFAULTS.get(k))

    def cap_int(self, key, value):
        """مقدار را به سقف می‌چسباند. برمی‌گرداند (مقدار, آیا_محدود_شد)"""
        lim = self.d.get(key) or 0
        if not lim:
            return value, False
        if key == "min_gap_sec":                 # اینجا کف است نه سقف
            return (max(value, lim), value < lim)
        if value == 0 or value > lim:            # ۰ یعنی نامحدود
            return lim, True
        return value, False

    def allowed(self, key):
        return bool(self.d.get(key, True))

    def summary(self):
        if not self.active:
            return ""
        o = []
        if self.d["plan"]:
            o.append(f"📦 پلن: <b>{self.d['plan']}</b>")
        if self.d["max_channels"]:
            o.append(f"📡 حداکثر کانال: {fa(self.d['max_channels'])}")
        if self.d["max_per_hour"]:
            o.append(f"🚦 سقف ارسال: {fa(self.d['max_per_hour'])}/ساعت")
        if self.d["min_gap_sec"]:
            o.append(f"⏱ کف فاصله: {fa(self.d['min_gap_sec'])} ثانیه")
        if self.d["max_joins_per_day"]:
            o.append(f"🔁 سقف جوین: {fa(self.d['max_joins_per_day'])}/روز")
        if not self.d["exchange"]:
            o.append("🔒 تبادل غیرفعال")
        if not self.d["initiate"]:
            o.append("🔒 پیش‌قدم غیرفعال")
        if not self.d["ai"]:
            o.append("🔒 هوش مصنوعی غیرفعال")
        return "\n".join(o)


# ─────────────────────────────────────────────
#  هوش مصنوعی (سازگار با OpenAI / nano-gpt / OpenRouter …)
# ─────────────────────────────────────────────
AI_DEFAULTS = {
    "enabled": True,
    "key": "sk-nry-lgTU-k8Jkm1goQBVCq8-MBolO_xhW6bkBpcPSni2RKs",
    "base_url": "https://nano-gpt.com/api/v1",
    "model": "qwen3.8-27b",
    "temperature": 0.4,
    "max_tokens": 700,
    "smart_detect": True,
    "pv_answer": False,       # AI فقط تحلیل می‌کند؛ به دیگران پیام نمی‌دهد
    "persona": "",
}


class AI:
    def __init__(self, path=AI_FILE):
        self.path = path
        self.cfg = dict(AI_DEFAULTS)
        self.last_error = ""
        self.load()

    def load(self):
        if os.path.exists(self.path):
            try:
                with open(self.path, encoding="utf-8") as f:
                    self.cfg.update(json.load(f))
            except Exception as e:
                print(f"⚠️ خواندن {self.path}: {e}")
        if not (self.cfg.get("key") or "").strip():
            self.cfg["key"] = AI_DEFAULTS["key"]

    def save(self):
        try:
            tmp = self.path + ".tmp"
            with open(tmp, "w", encoding="utf-8") as f:
                json.dump(self.cfg, f, ensure_ascii=False, indent=2)
            os.replace(tmp, self.path)
            try:
                os.chmod(self.path, 0o600)
            except Exception:
                pass
        except Exception as e:
            print(f"⚠️ ذخیره {self.path}: {e}")

    @property
    def ready(self):
        return bool(self.cfg["enabled"] and self.cfg["key"] and self.cfg["base_url"])

    # ---------- تماس با سرویس ----------
    def chat(self, messages, temperature=None, max_tokens=None, timeout=60):
        """برمی‌گرداند (متن, خطا)"""
        if not self.ready:
            return "", "AI فعال نیست یا کلید ندارد"
        url = self.cfg["base_url"].rstrip("/") + "/chat/completions"
        payload = {
            "model": self.cfg["model"],
            "messages": messages,
            "temperature": (self.cfg["temperature"] if temperature is None
                            else temperature),
            "max_tokens": max_tokens or self.cfg["max_tokens"],
        }
        req = urllib.request.Request(
            url, data=json.dumps(payload).encode("utf-8"),
            headers={"Authorization": "Bearer " + self.cfg["key"],
                     "Content-Type": "application/json"},
            method="POST")
        try:
            with urllib.request.urlopen(req, timeout=timeout) as r:
                d = json.loads(r.read().decode("utf-8", "ignore"))
            out = (d["choices"][0]["message"]["content"] or "").strip()
            self.last_error = ""
            return out, ""
        except urllib.error.HTTPError as e:
            body = e.read().decode("utf-8", "ignore")[:200]
            msg = f"HTTP {e.code}"
            try:
                j = json.loads(body)
                msg += ": " + str((j.get("error") or {}).get("message", body))[:150]
            except Exception:
                msg += ": " + body
            if e.code in (401, 403):
                msg += "\n(کلید پذیرفته نشد — با `.ai key کلید` عوضش کن)"
            self.last_error = msg
            return "", msg
        except urllib.error.URLError as e:
            self.last_error = f"شبکه: {e.reason}"
            return "", self.last_error
        except Exception as e:
            self.last_error = f"{type(e).__name__}: {e}"
            return "", self.last_error

    async def achat(self, messages, **kw):
        return await asyncio.to_thread(self.chat, messages, **kw)

    # ---------- تشخیص هوشمند پیام ----------
    SNIFF = (
        "تو فقط تحلیل‌گر پیام تبادل تلگرام هستی. هیچ متن پاسخی تولید نکن. "
        "فقط یک JSON خالص و کوتاه بده.\n"
        '{"joined":true/false,"asking":true/false,'
        '"intent":"join_claim|join_request|question|other"}\n'
        "joined=true فقط وقتی طرف درباره خودش صریحاً می‌گوید جوین شدم، عضو شدم، "
        "اومدم، داخل شدم یا عبارت هم‌معنی.\n"
        "عبارت‌های دستوری مثل «جوین شو»، «عضو شو»، «جوین کن»، "
        "«بیا جوین شو» و «برو عضو شو» درخواست از ربات هستند و حتماً "
        "joined=false و intent=join_request هستند. عبارت‌های دوم‌شخص مثل "
        "«جوین شدی بگو بیام» یا «تو عضو شدی؟» هم ادعای Join فرستنده نیستند.\n"
        "اگر صرفاً سوال یا لینک فرستاده، joined=false باشد."
    )

    async def sniff(self, text):
        """تحلیل پیام. اگر AI در دسترس نباشد None برمی‌گرداند."""
        if not (self.ready and self.cfg["smart_detect"]) or not text:
            return None
        out, err = await self.achat(
            [{"role": "system", "content": self.SNIFF},
             {"role": "user", "content": text[:1500]}],
            temperature=0, max_tokens=300, timeout=40)
        if err or not out:
            return None
        raw = out.strip()
        if "```" in raw:
            raw = raw.split("```")[1]
            if raw.lstrip().lower().startswith("json"):
                raw = raw.lstrip()[4:]
        i, j = raw.find("{"), raw.rfind("}")
        if i < 0 or j <= i:
            return None
        try:
            d = json.loads(raw[i:j + 1])
        except Exception:
            return None
        if not isinstance(d, dict):
            return None
        d["links"] = [str(l) for l in (d.get("links") or []) if l]

        def as_bool(v):
            if isinstance(v, bool):
                return v
            if isinstance(v, (int, float)):
                return bool(v)
            return str(v).strip().lower() in (
                "1", "true", "yes", "y", "بله", "درست")

        d["joined"] = as_bool(d.get("joined"))
        d["asking"] = as_bool(d.get("asking"))
        return d

    def _join_text(self, text):
        t = (text or "").replace("\u200c", "").replace("ي", "ی").replace("ك", "ک").lower()
        return re.sub(r"\s+", " ", t).strip()

    def _has_join_phrase(self, text, phrase):
        """عبارت را با مرز کلمه بررسی می‌کند تا «شدیم» با «شدی» قاطی نشود."""
        return bool(re.search(r"(?<!\w)" + re.escape(phrase) + r"(?!\w)", text or ""))

    def looks_like_join_request(self, text):
        """دستور «جوین شو» ادعای Join نیست؛ قبل از AI آن را قطعی رد کن."""
        t = self._join_text(text)
        if not t:
            return False
        requests = (
            "جوین شو", "جوین بشو", "جوین کن", "برو جوین", "بیا جوین",
            "عضو شو", "عضو بشو", "عضو کن", "برو عضو", "بیا عضو",
            "جوین شدی", "عضو شدی", "تو جوین شدی", "تو عضو شدی",
            "بگو بیام", "بگو بیا", "join me", "please join", "join شو", "join کن",
        )
        return any(self._has_join_phrase(t, k) for k in requests)

    def looks_like_join(self, text):
        """فقط ادعای انجام‌شدن Join را تشخیص می‌دهد، نه درخواست Join."""
        t = self._join_text(text)
        if not t or self.looks_like_join_request(t):
            return False
        # منفی‌ها اول بررسی شوند تا جمله‌هایی مثل «اومدم ولی عضو نشدم» مثبت نشوند.
        negatives = (
            "جوین نشدم", "جوین نشده", "عضو نشدم", "عضو نشده", "عضو نیستم",
            "هنوز عضو نیستم", "هنوز جوین نشدم", "نیومدم", "نیامدم",
            "جوین نکردم", "عضو نکردم", "not joined", "didn't join",
        )
        if any(self._has_join_phrase(t, k) for k in negatives):
            return False
        claims = (
            "جوین شدم", "جوینشدم", "جوین شدیم", "جوینشدیم", "جوینم",
            "عضو شدم", "عضوشدم", "عضو شدیم", "عضوشدیم", "عضوم",
            "اومدم", "آمدم", "اومدیم", "آمدیم",
            "داخل شدم", "وارد شدم", "جوین کردم", "عضو کانال شدم",
            "joined", "i joined",
        )
        return any(self._has_join_phrase(t, k) for k in claims)

    # ---------- پرسش و پاسخ درباره ربات ----------
    async def ask(self, question, context=""):
        persona = self.cfg.get("persona") or ""
        sysmsg = (
            "تو دستیار داخلی ربات «جفج» هستی؛ یک سلف‌بات تلگرام برای مدیریت "
            "کانال و تبادل. کوتاه، دقیق و فارسی جواب بده. اگر سوال درباره "
            "دستورها یا تنظیمات است، از اطلاعات زیر استفاده کن و دستور دقیق "
            "را بنویس. چیزی که نمی‌دانی را از خودت نساز.\n\n" + context
        )
        if persona:
            sysmsg += "\n\nلحن: " + persona
        return await self.achat(
            [{"role": "system", "content": sysmsg},
             {"role": "user", "content": question[:2000]}])


# ─────────────────────────────────────────────
#  استخراج لینک کانال از متن
# ─────────────────────────────────────────────
_LINK_PATTERNS = [
    re.compile(r"(?:https?://)?t\.me/(?:joinchat/|\+)([A-Za-z0-9_-]{10,})"),
    re.compile(r"(?:https?://)?t\.me/([A-Za-z][A-Za-z0-9_]{3,31})(?![\w/])"),
    re.compile(r"@([A-Za-z][A-Za-z0-9_]{3,31})"),
]
_SKIP = {"joinchat", "share", "addstickers", "proxy", "socks", "iv", "s", "c"}


def extract_links(text):
    """همه لینک‌های کانال داخل متن را برمی‌گرداند (یکتا، به ترتیب)."""
    if not text:
        return []
    out, seen = [], set()
    for m in _LINK_PATTERNS[0].finditer(text):
        v = "https://t.me/+" + m.group(1)
        if v.lower() not in seen:
            seen.add(v.lower())
            out.append(v)
    for pat in _LINK_PATTERNS[1:]:
        for m in pat.finditer(text):
            u = m.group(1)
            if u.lower() in _SKIP:
                continue
            v = "@" + u
            if v.lower() not in seen:
                seen.add(v.lower())
                out.append(v)
    return out


def _input_channel(cid, chash=None):
    """InputChannel از آیدی/access_hash کانال.

    اگر access_hash نداشته باشیم ۰ می‌فرستیم (تلگرام خودش تصمیم می‌گیرد).
    در محیطِ تست که telethon نصب نیست، شیمِ سبک برمی‌گردد تا منطقِ لفت
    قابل‌آزمایش بماند.
    """
    try:
        from telethon.tl.types import InputChannel
        return InputChannel(int(cid), int(chash or 0))
    except Exception:
        try:
            from types import SimpleNamespace
            return SimpleNamespace(id=int(cid), access_hash=int(chash or 0))
        except Exception:
            return None


def is_invite(link):
    return "+" in link or "joinchat" in link


def invite_hash(link):
    return link.split("+")[-1].split("/")[-1]


def strip_peer_links(text, peer):
    """هر شکلی از لینکِ همین طرفِ تبادل را از متن حذف می‌کند.

    قاعده‌ی قطعیِ محصول: لینکِ طرفِ تبادل هرگز نباید داخل متنِ پیام‌های
    جفج (که در گروه ریپلای می‌شوند) بیاید — نه با توکنِ قدیمیِ
    `{channel}` و نه اگر لینکش به‌صورت خام داخل متنِ ذخیره‌شده مانده
    باشد (مثلاً تنظیماتِ به‌جامانده از نسخه‌های قدیمی که لینک طرف را
    اتوماتیک زیر پیام می‌چسباندند). همه‌ی املای یک لینک پوشش داده
    می‌شود: `@name`، `t.me/name`، `https://telegram.me/name`،
    `t.me/+HASH` و `t.me/joinchat/HASH` و `+HASH`.

    عمداً مستقل از `_LINK_PATTERNS` است تا منطقِ اسکن/تشخیص لینک دست
    نخورد؛ فقط پاک‌سازی متن ارسالی کامل‌تر باشد. آیدی عددی کانال چون
    لینکِ قابل‌کلیک در متن نیست عمداً حذف نمی‌شود.
    """
    if not text or not peer:
        return text or ""
    try:
        def _bare(value):
            s = str(value or "").strip().lower().rstrip("/")
            s = re.sub(r"^https?://", "", s)
            s = re.sub(r"^(?:www\.)?(?:t|telegram)\.me/", "", s)
            s = s.replace("joinchat/", "").lstrip("+@")
            return s

        if is_invite(peer):
            h = re.escape(invite_hash(peer))
            if not h:
                return text
            patterns = [
                r"(?:https?://)?(?:www\.)?(?:t|telegram)\.me/"
                r"(?:joinchat/|\+)" + h + r"/?",
                # joinchat خام بدون پیشوند t.me (املای ناقصِ متن‌های قدیمی)
                r"(?<![\w.\-])joinchat/" + h + r"(?![\w.\-])",
                r"(?<![\w.\-])\+" + h + r"(?![\w.\-])",
            ]
        else:
            u = re.escape(_bare(peer))
            if not u or not re.match(r"^[a-z][a-z0-9_]{3,31}$", u):
                # یوزرنیم معتبر نیست (مثلاً آیدی عددی) → حذفِ ناامن انجام نده.
                return text
            patterns = [
                r"@" + u + r"\b",
                r"(?:https?://)?(?:www\.)?(?:t|telegram)\.me/"
                + u + r"/?(?![\w/])",
            ]
        for pat in patterns:
            text = re.sub(pat, "", text, flags=re.IGNORECASE)
    except Exception:
        return text
    return text


# ─────────────────────────────────────────────
#  راهنما
# ─────────────────────────────────────────────
HELP = """🤖 راهنمای جفج

دستورها را در Saved Messages بفرست. نقطه و اسلش هم قابل استفاده‌اند، اما دستورهای اصلی فارسی هستند.

🏠 خانه و وضعیت
پنل — نمایش پنل اصلی
راهنما — همین راهنما
تنظیمات — تنظیمات کامل
آمار — آمار ارسال
گزارش — رویدادهای اخیر
زنده — بررسی زنده‌بودن سلف

📝 ارسال
ارسال متن — ارسال به صف عادی
ارسال فوری متن — ارسال فوری
ویژه متن — ارسال به صف ویژه

📡 کانال‌ها
کانال @channel — کانال عادی
کانال ویژه @channel — کانال ویژه
کانال‌ها — نمایش کانال‌ها
حذف کانال — حذف کانال بخش فعلی

⚙️ تنظیمات عادی
عادی — ورود به بخش عادی
فعالیت ۶۰ — مدت فعالیت به دقیقه
استراحت ۳۰ — مدت استراحت
سقف ۱۲ — سقف ارسال در ساعت
فاصله ۴۵ ۱۲۰ — فاصله بین ارسال‌ها
سکوت ۰ ۱ ۲ — ساعت‌های سکوت
حالت — تعویض حالت ۲۴ ساعته و چرخه‌ای

👑 تنظیمات ویژه
ویژه — ورود به بخش ویژه
فعالیت ویژه ۶۰
استراحت ویژه ۳۰
سقف ویژه ۳۰
فاصله ویژه ۲۰ ۴۵
سکوت ویژه ۰ ۱
حالت ویژه

⏯ کنترل صف
توقف — توقف ارسال
ادامه — ادامه ارسال
بازنشانی — شروع دوباره چرخه
صف — نمایش صف
حذف ۵ — حذف پیام شماره ۵
پاکسازی — خالی‌کردن صف
تلاش دوباره — تلاش دوباره پیام‌های ناموفق

👥 گروه‌های تبادل
گروه‌ها — نمایش منوی گروه‌ها
افزودن گروه @group — افزودن گروه
تبادل گروه جایگزین @backup — فعال‌سازی پشتیبان اختیاری
تبادل گروه جایگزین روشن/خاموش — کنترل حالت
تبادل گروه جایگزین بعد ۵ — انتقال پس از ۵ دقیقه بی‌لینک‌ماندن
حذف گروه @group — حذف یک گروه
حذف همه گروه‌ها — حذف همه گروه‌ها

🔁 تبادل
تبادل — منوی تبادل
تبادل تنظیمات — صفحه تنظیمات تبادل
تبادل راهنما — راهنمای حالت‌ها
تبادل دستورها — همه دستورهای تبادل
تبادل تشخیص — روشن/خاموش تشخیص هوشمند
تبادل روشن / تبادل خاموش
تبادل خودکار — روشن یا خاموش‌کردن Join خودکار
تبادل پیش‌قدم — اسکن گروه‌ها و پیش‌قدم‌شدن
تبادل اسکن — اسکن فوری
تبادل فهرست — فهرست تبادل‌ها
تبادل منتظر — موارد منتظر
تبادل تأیید ۵ — تأیید یک مورد
تبادل رد ۵ — رد یک مورد
تبادل خروج ۵ — لفت از یک کانال
تبادل لفت خودکار روشن/خاموش/ریست — لفت امن و پاک‌کردن توقف سقف
تبادل حذف ۵ — حذف یک مورد
تبادل ارسال ۵ — ارسال دوباره متن برای Join شماره ۵

⏱ تنظیم تبادل
تبادل هر ۳۰ ثانیه — فاصله پیش‌فرض ثابت بین Joinها
تبادل فاصله ۹۰ ۲۴۰ — فاصله تصادفی بین Joinها
تبادل Join روزانه بدون سقف است.
تبادل سقف ساعتی 60 — سقف جوین در هر ساعت (خاموش پیش‌فرض؛ با «روشن» فعال می‌شود)
تبادل سقف ساعتی روشن / تبادل سقف ساعتی خاموش
تبادل بررسی ۱۵ ۳۰ — بررسی عضویت با فاصله تصادفی ۱۵ تا ۳۰ ثانیه
تبادل زمان پاسخ ۱۵ — تأخیر پاسخ بعد از Join واقعی
تبادل اخطار ۲ — بعد از دو بار نبودنِ تأییدشده لفت بده (این پیام نیست؛ پیش‌فرض ۲)
تبادل تعداد یادآوری ۲ — دو پیام «نیومدی» با فاصله؛ بعد از آن لفت (پیش‌فرض ۲؛ ۰ = بدون پیام)
تبادل فاصله یادآوری ۲۰ ۴۰ — فاصله تصادفی بین دو پیام «نیومدی» (پیش‌فرض)
تبادل فاصله عملکرد ۱۵ ۲۰ — هیچ دو عملکردی پشت‌سرهم نمی‌روند: چک/جوین/لفت/پیام
                              یکی تمام شود، ۱۵–۲۰ ثانیه صبر، بعدی اجرا شود
🧠 تطبیقی هوشمند — فاصله جوین با FloodWait و آپ‌تایم خودکار زیاد می‌شود
تبادل تطبیقی — نمایش وضعیت (پایه + Flood + آپ‌تایم)
تبادل تطبیقی روشن / خاموش — فعال/غیرفعال کردن تطبیقی (پیش‌فرض روشن)
تبادل تطبیقی ریست — صفر کردن اضافه Flood
تبادل تطبیقی flood 15 — هر FloodWait چقدر اضافه کند (پیش‌فرض ۱۵ ثانیه)
تبادل تطبیقی max 120 — سقف اضافه Flood (پیش‌فرض ۱۲۰ ثانیه)
تبادل تطبیقی decay 60 — هر چند دقیقه بدون Flood کم شود (پیش‌فرض ۶۰ دقیقه)
تبادل تطبیقی uptime 3 — بعد از چند ساعت کند شود (پیش‌فرض ۳ ساعت)
تبادل تطبیقی extra 30 10 — اضافه آپ‌تایم (۳۰ ثانیه بعد آستانه + ۱۰ ثانیه هر ساعت)

📊 گزارش خصوصی تبادل
تبادل گزارش — ورود به منوی گزارش تبادل
تنظیم گزارش روشن — فعال‌کردن گزارش لحظه‌ای در PV
تنظیم گزارش لحظه‌ای — فعال‌کردن گزارش لحظه‌ای در PV
تنظیم گزارش خلاصه — یک گزارش جمعی خودکار
تنظیم گزارش هر 24 — فاصله گزارش خلاصه به ساعت
گزارش خلاصه — ارسال گزارش خلاصه همین حالا
تنظیم گزارش خاموش — خاموش‌کردن گزارش

تبادل اسکن هر ۳۰ ثانیه — اسکن پیش‌قدم؛ اسکن فوری با «تبادل اسکن»
تبادل انتخاب پیام ۲ — پیام دوم از جدیدترین لینک‌ها
تبادل عمق اسکن ۵۰ — چند پیام آخر گروه بررسی شود
تبادل سن لینک ۵ — فقط لینک‌های حداکثر ۵ دقیقه اخیر

💬 متن‌های تبادل
متن‌های تبادل — نمایش منوی متن‌ها
تبادل پیام موفق جوین شدم
تبادل پیام ناموفق اول عضو شو
تبادل پیام ادعای جوین گفتی جوین شدی ولی عضو نشدی
تبادل پیام انتظار دارم بررسی می‌کنم
تبادل پیام بدون لینک لینک کانالت را بفرست
تبادل پیام متن دلخواه — متن بعد از هر Join موفق
مثال: تبادل پیام جوین شدم جوین شو
تبادل زمان بیا ۰ — تأخیر پیام بیا به ثانیه
برای خاموش‌کردن هر متن، در پایان بنویس: خاموش

🧠 هوش مصنوعی
هوش — وضعیت هوش مصنوعی
هوش روشن / هوش خاموش
هوش تست
هوش تشخیص
هوش پاسخ

📊 پلن
پلن — نمایش محدودیت‌های پلن

🛡 محافظ ریپورت
ریسک — وضعیت و درصد ریسک (ارسال/جوین/لفت/فلاد/…)
ریسک آستانه 75 — آستانه‌ی خاموشی خودکار تبادل
ریسک بازگشت 55 — زیر این درصد دوباره روشن می‌شود
ریسک بررسی — محاسبه‌ی همین لحظه
ریسک روشن / ریسک خاموش — فعال/غیرفعال‌کردن «توقف بر امتیاز» (پیش‌فرض: خاموش)
ریسک پایش روشن / ریسک پایش خاموش — فعال/غیرفعال‌کردن «پایشِ واقعی» (پیش‌فرض: روشن و همیشه فعال)
ریسک ریست — پاک‌کردن وضعیت خاموشی خودکار
"""


def _soft_clean(s):
    """ایموجی و فاصلهٔ اضافه را از دستور برمی‌دارد."""
    s = (s or "").replace("\u200c", " ").replace("\u200b", "")
    s = s.replace("ي", "ی").replace("ك", "ک")
    s = re.sub(r"[\U0001F300-\U0001FAFF\U00002700-\U000027BF"
               r"\U0001F000-\U0001F0FF\u2600-\u26FF\u2300-\u23FF"
               r"🔹👑📡✍🚦🔁📮🧠🔕⏸▶🏠➕🗑📋⏱🎲💬✨⭐⏳🆔🔗👤🟢💎]",
               " ", s)
    return re.sub(r"\s+", " ", s).strip()


# ─────────────────────────────────────────────
#  هسته
# ─────────────────────────────────────────────
class Engine:
    """موتور مستقل از تلگرام — قابل تست"""

    def __init__(self):
        self.st = Settings()
        self.db = DB()
        self.thr = {t: Throttle(self.st.prof(t)) for t in ("standard", "vip")}
        self.cyc = {t: Cycle(self.st.prof(t)) for t in ("standard", "vip")}
        x = self.st["exchange"]
        self.join_thr = Throttle({"min_gap_sec": x["min_join_gap_sec"],
                                  "max_gap_sec": x["max_join_gap_sec"],
                                  "max_per_hour": 0})
        self.ai = AI()
        self.lim = Limits()
        self.apply_limits()
        self.started = int(time.time())
        self.me = None
        self.my_username = ""
        self.my_id = 0
        self.last_error = ""

    def apply_limits(self):
        """سقف‌های پلن را روی تنظیمات فعلی اعمال می‌کند."""
        if not self.lim.active:
            return []
        hit = []
        for tier in ("standard", "vip"):
            p = self.st.prof(tier)
            v, capped = self.lim.cap_int("max_per_hour", p["max_per_hour"])
            if capped:
                p["max_per_hour"] = v
                hit.append(f"سقف ارسال {tier} → {v}/ساعت")
            v, capped = self.lim.cap_int("min_gap_sec", p["min_gap_sec"])
            if capped:
                p["min_gap_sec"] = v
                p["max_gap_sec"] = max(p["max_gap_sec"], v)
                hit.append(f"فاصله {tier} → حداقل {v} ثانیه")
            self.thr[tier].apply(p)
        x = self.st["exchange"]
        if not self.lim.allowed("exchange") and x["enabled"]:
            x["enabled"] = False
            hit.append("تبادل در پلن تو نیست")
        if not self.lim.allowed("initiate") and x["initiate"]:
            x["initiate"] = False
            hit.append("حالت پیش‌قدم در پلن تو نیست")
        # سقف روزانه Join حذف شده است؛ هیچ پلنی این بخش را محدود نمی‌کند.
        x["max_joins_per_day"] = 0
        if not self.lim.allowed("ai") and self.ai.cfg["enabled"]:
            self.ai.cfg["enabled"] = False
            hit.append("هوش مصنوعی در پلن تو نیست")
        if hit:
            self.st.save()
        return hit

    def reload(self, tier):
        self.thr[tier].apply(self.st.prof(tier))
        self.cyc[tier].apply(self.st.prof(tier))
        self.st.save()
        self.apply_limits()

    def log(self, lvl, kind, detail=""):
        if lvl in ("error", "warn"):
            self.last_error = f"{kind}: {str(detail)[:120]}"
        self.db.log(lvl, kind, detail)
        line = f"[{datetime.now():%H:%M:%S}] {lvl.upper():5} {kind} {detail}"
        print(line, flush=True)
        try:
            with open(LOG_FILE, "a", encoding="utf-8") as f:
                f.write(line + "\n")
        except Exception:
            pass

    def target(self, tier):
        ch = self.st.prof(tier)["channel"]
        if not ch and tier == "vip":
            ch = self.st.prof("standard")["channel"]
        return ch

    # ---------- دستورها (همه رشته برمی‌گردانند) ----------
    def cmd(self, cmd, arg, reply_text=None):
        c = _soft_clean(cmd).lower().strip()
        a0 = (arg or "").strip()
        # «تنظیم کانال» یک فرمان کامل است (با فاصله)
        full = (c + (" " + a0 if a0 else "")).strip()
        if c in ("عادی", "std", "normal", "بخش عادی") and not (a0 or reply_text):
            self.st.data["_menu"] = "standard"
            try:
                self.st.save()
            except Exception:
                pass
            return self.section_text("standard")
        if c in ("ویژه", "وی‌آی‌پی", "vipmenu", "بخش ویژه") and not (a0 or reply_text):
            self.st.data["_menu"] = "vip"
            try:
                self.st.save()
            except Exception:
                pass
            return self.section_text("vip")
        menus = {
            "کانال": self.submenu_channel,
            "تنظیم کانال": self.submenu_channel,
            "تنظیم‌کانال": self.submenu_channel,
            "تنظیمکانال": self.submenu_channel,
            "افزودن": self.submenu_add_channel,
            "افزودن کانال": self.submenu_add_channel,
            "افزودن‌کانال": self.submenu_add_channel,
            "تغییر": self.submenu_add_channel,
            "تغییر کانال": self.submenu_add_channel,
            "تغییر‌کانال": self.submenu_add_channel,
            "حذف": self.submenu_del_channel,
            "حذف کانال": self.cmd_del_channel,
            "حذف‌کانال": self.cmd_del_channel,
            "پاک کردن کانال": self.cmd_del_channel,
            "حذفکانال": self.cmd_del_channel,
            "لیست": self.submenu_list_channel,
            "لیست کانال": self.submenu_list_channel,
            "لیست‌کانال": self.submenu_list_channel,
            "متن": self.submenu_post,
            "تنظیم متن": self.submenu_post,
            "تنظیم‌متن": self.submenu_post,
            "گروه‌ها": self.submenu_groups,
            "گروه ها": self.submenu_groups,
            "افزودن گروه": self.submenu_add_group,
            "ثبت گروه": self.submenu_add_group,
            "حذف گروه": self.cmd_clear_groups,
            "پاک کردن گروه": self.cmd_clear_groups,
            "سقف": self.submenu_limit,
            "سقف ارسال": self.submenu_limit,
            "سقف‌ارسال": self.submenu_limit,
            "گروه": self.submenu_groups,
            "تنظیم گروه": self.submenu_groups,
            "تنظیم‌گروه": self.submenu_groups,
            "چرخه": self.submenu_cycle,
            "نوسان": self.submenu_gap,
            "متن تبادل": self.submenu_ex_msgs,
            "متن‌تبادل": self.submenu_ex_msgs,
            "متن‌های تبادل": self.submenu_ex_msgs,
            "متن های تبادل": self.submenu_ex_msgs,
            "کانال‌ها": self.submenu_list_channel,
            "کانال ها": self.submenu_list_channel,
            "حذف همه گروه‌ها": self.cmd_clear_groups,
            "حذف همه گروه ها": self.cmd_clear_groups,
        }
        if full in menus and not reply_text:
            return menus[full]()
        if c == "تنظیم" and a0.startswith("کانال"):
            return self.submenu_channel()
        if c == "تنظیم" and a0.startswith("متن"):
            return self.submenu_post()
        if c == "تنظیم":
            setting = re.sub(r"\s+", " ", a0.replace("\u200c", " ")).strip()
            if setting.startswith("تبادل "):
                setting = setting[6:].strip()
            if setting.startswith("گزارش"):
                suffix = setting[len("گزارش"):].strip()
                if not suffix:
                    return "برای ورود به منوی گزارش، `تبادل گزارش` را بفرست."
                if suffix in ("روشن", "لحظه‌ای", "لحظه ای"):
                    return self.exchange_cmd("report_live")
                if suffix == "خلاصه":
                    return self.exchange_cmd("report_summary")
                if suffix in ("خاموش", "off"):
                    return self.exchange_cmd("report_off")
                if suffix.startswith("هر "):
                    return self.exchange_cmd("report_every " + suffix[4:].strip())
                if suffix.startswith(("خلاصه الان", "خلاصه همین الان")):
                    return self.exchange_cmd("report_now")
            # سازگاری با تنظیم‌های قدیمی مثل «تنظیم تبادل ...»
            if a0.startswith("تبادل") or a0.startswith("تبادل‌"):
                rest_ex = a0[5:].strip() if a0.startswith("تبادل") else a0[6:].strip()
                return self.exchange_cmd(rest_ex)
        if c == "تنظیم" and a0.startswith("گروه"):
            return self.submenu_groups()
        if c in ("گروه", "گروه‌ها", "گروه ها") and a0:
            return self.exchange_cmd("groups " + a0)
        if c in ("افزودن گروه", "ثبت گروه") and a0:
            return self.exchange_cmd("groups " + a0)
        if c == "افزودن" and a0.startswith("گروه"):
            return self.cmd("گروه", a0[5:].strip(), reply_text)
        if c in ("حذف گروه",) and a0:
            return self.exchange_cmd("removegroup " + a0)
        if c == "حذف" and a0.startswith("همه گروه"):
            return self.cmd_clear_groups()
        if c in ("حذف گروه", "حذف همه گروه‌ها", "حذف همه گروه ها"):
            return self.cmd_clear_groups()
        if c in ("تبادل", "تبادل‌ها", "تبادل ها") and a0:
            return self.exchange_cmd(a0)
        if c == "ارسال" and a0.lower().startswith("فوری"):
            return self.cmd("now", a0[4:].strip(), reply_text)
        if c == "کانال" and (a0.lower() == "ویژه" or
                              a0.lower().startswith(("ویژه ", "ویژه‌"))):
            return self.cmd("setvip", a0[5:].strip(), reply_text)
        if c == "افزودن" and a0.startswith("کانال"):
            return self.submenu_add_channel()
        if c == "تغییر" and a0.startswith("کانال"):
            return self.submenu_add_channel()
        if c == "حذف" and a0.startswith("گروه"):
            return self.cmd("حذف گروه", a0[5:].strip(), reply_text)
        if c == "حذف" and a0.startswith("کانال"):
            return self.cmd("حذف کانال", "", reply_text)
        if c == "لیست" and a0.startswith("کانال"):
            return self.submenu_list_channel()
        if c in ("فعالیت", "استراحت", "سقف", "فاصله", "سکوت", "حالت") \
                and (a0.lower() == "ویژه" or
                     a0.lower().startswith(("ویژه ", "ویژه‌"))):
            return self.cmd(c + " ویژه", a0[5:].strip(), reply_text)
        if c == "سقف" and a0.startswith("ارسال"):
            return self.submenu_limit()
        if c == "متن" and a0.startswith("تبادل"):
            return self.submenu_ex_msgs()
        if c == "نوسان" and not a0:
            return self.submenu_gap()
        arg = a0
        # نام‌های فارسی ساده برای دستورات اصلی
        aliases = {
            "عادی": "post",
            "ارسال": "post", "پست": "post", "ارسال فوری": "now",
            "ویژه": "vip", "وی‌آی‌پی": "vip", "وی ای پی": "vip",
            "پنل": "panel", "خانه": "panel",
            "کانال": "setch", "کانال ویژه": "setvip", "کانال‌ویژه": "setvip",
            "تنظیمکانال": "setch",
            "کانالوِیژه": "setvip", "کانالویژه": "setvip",
            "کانال vip": "setvip", "کانالوی آی پی": "setvip",
            "کانالها": "chans", "کانال‌ها": "chans",
            "توقف": "pause", "ادامه": "resume", "بازنشانی": "reset",
            "صف": "queue", "حذف": "del", "پاکسازی": "clear",
            "تلاش": "retry", "راهنما": "help", "وضعیت": "panel",
            "تنظیمات": "set", "آمار": "stats", "گزارش": "log",
            "زنده": "ping", "پنل": "panel", "تبادل": "ex",
            "فعالیت": "active", "استراحت": "rest", "سقف": "limit",
            "فاصله": "gap", "نوسان": "gap", "سکوت": "quiet", "حالت": "mode",
            "فعالیت vip": "vactive", "استراحت vip": "vrest",
            "فعالیت ویژه": "vactive", "استراحت ویژه": "vrest",
            "سقف ویژه": "vlimit", "فاصله ویژه": "vgap",
            "سکوت ویژه": "vquiet", "حالت ویژه": "vmode",
            "کانال‌ویژه": "setvip", "کانالویژه": "setvip",
            "فعالیت‌ویژه": "vactive", "فعالیتویژه": "vactive",
            "استراحت‌ویژه": "vrest", "استراحتویژه": "vrest",
            "نوسان‌ویژه": "vgap", "نوسانویژه": "vgap",
            "سقف‌ویژه": "vlimit", "سقفویژه": "vlimit",
        }
        c = aliases.get(c, c)

        # ارسال
        if c in ("now", "فوری"):
            body = arg or reply_text
            if not body:
                return "متن را بنویس:\n`ارسال فوری سلام`"
            tgt = self.target("standard")
            if not tgt:
                return "اول کانال را تعیین کن: `کانال @channel`"
            qid = self.db.enqueue(tgt, body, "standard", when=int(time.time()) - 1)
            return f"⚡ فوری به صف رفت (#{fa(qid)}) → `{tgt}`"

        if c in ("id", "آیدی"):
            return "روی همین چت `.id` را از داخل تلگرام بزن؛ آیدی عددی در لایه تلگرام جواب داده می‌شود."

        if c in ("post", "vip"):
            tier = "vip" if c == "vip" else "standard"
            body = arg or reply_text
            if not body:
                return ("متن را بنویس یا روی یک پیام ریپلای کن:\n"
                        + ("`ویژه سلام`" if tier == "vip" else "`ارسال سلام`"))
            tgt = self.target(tier)
            qid = self.db.enqueue(tgt, body, tier)
            if not tgt:
                return (f"📦 ذخیره شد (#{fa(qid)}) — منتظر تعیین کانال.\n"
                        f"هر وقت `{'کانال ویژه' if tier == 'vip' else 'کانال'} @channel` "
                        f"بزنی، خودکار ارسال می‌شود.\n"
                        f"معلق: {fa(self.db.held_count(tier))}")
            ph, rem = self.cyc[tier].phase()
            w = self.thr[tier].wait_time()
            when = ("به‌زودی" if ph == "active" and w <= 0
                    else (f"بعد از {secs(rem)}" if ph != "active" else f"تا {secs(w)} دیگر"))
            return (f"✅ به صف {'VIP 👑' if tier == 'vip' else 'عادی'} اضافه شد (#{fa(qid)})\n"
                    f"مقصد: `{tgt}`\nارسال: {when}\nدر صف: {fa(self.db.pending_count(tier))}")

        # کانال‌ها
        if c in ("setch", "setvip"):
            tier = "vip" if c == "setvip" else "standard"
            if not arg:
                cur = self.st.prof(tier)["channel"] or "تنظیم نشده"
                return (f"کانال فعلی: `{cur}`\n"
                        + ("`کانال ویژه @mychannel`" if tier == "vip"
                           else "`کانال @mychannel`"))
            v = arg.strip().split()[0]
            old_channel = (self.st.prof(tier)["channel"] or "").strip()
            mc = self.lim["max_channels"]
            if mc:
                others = [self.st.prof(t)["channel"]
                          for t in ("standard", "vip") if t != tier]
                cnt = len([c for c in others if c]) + 1
                if cnt > mc:
                    return (f"⚠️ پلن تو حداکثر {fa(mc)} کانال دارد.\n"
                            f"اول یکی را خالی کن یا پلن را ارتقا بده.")
            self.st.prof(tier)["channel"] = v
            self.st.save()
            nm = "VIP 👑" if tier == "vip" else "عادی"
            freed = self.db.assign_target(tier, v)
            moved = self.db.retarget_pending(tier, old_channel, v)
            freed += moved
            if tier == "standard" and not self.st.prof("vip")["channel"]:
                freed += self.db.assign_target("vip", v)
                freed += self.db.retarget_pending("vip", old_channel, v)
            extra = f"\n📦 {fa(freed)} پیام صف به کانال جدید منتقل شد و ارسال می‌شود." if freed else ""
            return f"✅ کانال {nm}: `{v}`{extra}"

        if c == "chans":
            s = self.st.prof("standard")["channel"] or "—"
            v = self.st.prof("vip")["channel"] or "—"
            return f"📡 **کانال‌ها**\n\nعادی: `{s}`\nVIP: `{v}`"

        # تنظیمات
        tune = {
            "active": ("standard", "active"), "vactive": ("vip", "active"),
            "rest": ("standard", "rest"), "vrest": ("vip", "rest"),
            "limit": ("standard", "limit"), "vlimit": ("vip", "limit"),
            "gap": ("standard", "gap"), "vgap": ("vip", "gap"),
            "quiet": ("standard", "quiet"), "vquiet": ("vip", "quiet"),
            "mode": ("standard", "mode"), "vmode": ("vip", "mode"),
        }
        if c in tune:
            return self.tune(*tune[c], arg)

        # کنترل
        if c == "pause":
            self.st["paused"] = True
            self.st.save()
            return "⏸ ارسال متوقف شد.\n`ادامه` برای ادامه."
        if c == "resume":
            self.st["paused"] = False
            self.st.save()
            return "▶️ ارسال ادامه یافت."
        if c == "reset":
            for x in self.cyc.values():
                x.reset()
            return "♻️ چرخه هر دو بخش از الان شروع شد."
        if c == "clear":
            return f"🗑 {fa(self.db.clear_pending())} آیتم از صف حذف شد."
        if c == "retry":
            return f"♻️ {fa(self.db.retry_failed())} آیتم ناموفق دوباره به صف رفت."
        if c == "del":
            try:
                n = self.db.delete_item(num(arg))
            except (ValueError, TypeError):
                return "فرمت: `حذف ۵`"
            return "✅ حذف شد." if n else "چنین آیتمی در صف نیست."

        # تبادل
        if c in ("ex", "tb"):
            return self.exchange_cmd(arg)

        # محافظ ریپورت
        if c in ("risk", "ریسک", "امنی", "حفاظت", "امنیت"):
            out = self.risk_cmd(arg)
            return out if out is not None else self.risk_status_text()

        # نمایش
        if c in ("panel", "p", "start"):
            return self.panel()
        if c == "help":
            return HELP
        if c == "set":
            return self.settings_text()
        if c == "queue":
            return self.queue_text()
        if c == "stats":
            return self.stats_text()
        if c == "log":
            evs = self.db.recent(15)
            if not evs:
                return "رویدادی ثبت نشده."
            ic = {"info": "ℹ️", "warn": "⚠️", "error": "❌", "ok": "✅"}
            return "📜 **رویدادهای اخیر**\n\n" + "\n".join(
                f"{ic.get(e['level'], '•')} `{datetime.fromtimestamp(e['ts']):%H:%M}` "
                f"{e['kind']} {(e['detail'] or '')[:45]}" for e in evs)
        if c in ("plan", "limits", "پلن"):
            if not self.lim.active:
                return "📦 هیچ محدودیتی روی این نسخه نیست."
            sm = (self.lim.summary() or "").replace("<b>", "**").replace("</b>", "**")
            return ("📦 **پلن و سقف‌های تو**\n" + self.LINE_ + "\n"
                    + sm + "\n" + self.LINE_
                    + "\n_برای ارتقا با پشتیبانی تماس بگیر._")

        if c in ("بررسی", "هوش‌بررسی"):
            rest = (arg or "").strip()
            if rest in ("فعال", "روشن", "on"):
                return self.ai_settings_cmd("بررسی فعال")
            if rest in ("خاموش", "off"):
                return self.ai_settings_cmd("بررسی خاموش")
            return self.ai_settings_cmd("بررسی")

        if c in ("متن موفق", "متن‌موفق", "متنموفق", "پیام موفق"):
            return self.exchange_cmd(("پیام موفق " + (arg or "")).strip())
        if c in ("متن ناموفق", "متن‌ناموفق", "متنناموفق", "پیام ناموفق"):
            return self.exchange_cmd(("پیام ناموفق " + (arg or "")).strip())
        if c in ("متن انتظار", "متن‌انتظار", "متنانتظار", "پیام انتظار"):
            return self.exchange_cmd(("پیام انتظار " + (arg or "")).strip())
        if c in ("متن بدون لینک", "متن‌بدون‌لینک", "متنبدونلینک", "پیام بدون لینک"):
            return self.exchange_cmd(("پیام بدون لینک " + (arg or "")).strip())
        if c in ("لیست",) and (not arg or "تبادل" in (arg or "")):
            return self.exchange_cmd("list")
        if c in ("لیست تبادل", "لیست‌تبادل", "لیستتبادل"):
            return self.exchange_cmd("list")

        if c in ("ver", "version", "نسخه"):
            return (f"🧬 نسخه همین پروسه: **{VERSION}**\n"
                    f"ساخت: `{BUILD_TAG}`\n"
                    "اگر این ساخت را نمی‌بینی، هنوز فایل قدیمی اجرا می‌شود.")
        if c == "ping":
            return f"🏓 زنده‌ام — آپ‌تایم {secs(int(time.time()) - self.started)}"

        return None  # دستور ناشناخته → بی‌صدا رد شود

    # ---------- تغییر مقادیر ----------
    def tune(self, tier, field, arg):
        p = self.st.prof(tier)
        nm = "👑 ویژه" if tier == "vip" else "🔹 عادی"

        def label(name):
            return f"{name} ویژه" if tier == "vip" else name

        if field == "mode":
            p["mode"] = "cycle" if p["mode"] == "always" else "always"
            self.reload(tier)
            m = "چرخه‌ای (فعالیت/استراحت)" if p["mode"] == "cycle" else "۲۴ ساعته"
            return f"{nm} — حالت: **{m}**\n{self.brief(tier)}"

        if field == "active":
            if not arg:
                return f"فعالیت فعلی: {dur(p['active_minutes'])}\n`{label('فعالیت')} ۹۰`"
            try:
                v = num(arg)
            except ValueError:
                return f"عدد بده: `{label('فعالیت')} ۶۰`"
            v = max(1, v)
            p["active_minutes"] = v
            if p["rest_minutes"] > 0:
                p["mode"] = "cycle"
            self.reload(tier)
            return f"{nm} — فعالیت: **{dur(v)}**\n{self.brief(tier)}"

        if field == "rest":
            if not arg:
                return (f"استراحت فعلی: {dur(p['rest_minutes'])}\n"
                        f"`{label('استراحت')} ۳۰`  |  `{label('استراحت')} ۰` برای ۲۴ساعته")
            try:
                v = num(arg)
            except ValueError:
                return f"عدد بده: `{label('استراحت')} ۳۰`"
            v = max(0, v)
            p["rest_minutes"] = v
            p["mode"] = "always" if v == 0 else "cycle"
            self.reload(tier)
            t = "بدون استراحت (۲۴ ساعته)" if v == 0 else dur(v)
            return f"{nm} — استراحت: **{t}**\n{self.brief(tier)}"

        if field == "limit":
            if not arg:
                cur = "نامحدود" if not p["max_per_hour"] else f"{fa(p['max_per_hour'])} در ساعت"
                return (f"سقف فعلی: {cur}\n"
                        f"`{label('سقف')} ۱۲`  |  `{label('سقف')} ۰` نامحدود")
            try:
                v = num(arg)
            except ValueError:
                return f"عدد بده: `{label('سقف')} ۱۲`"
            v = max(0, v)
            v, capped = self.lim.cap_int("max_per_hour", v)
            p["max_per_hour"] = v
            self.reload(tier)
            t = "نامحدود" if v == 0 else f"{fa(v)} پیام در ساعت"
            w = (f"\n⚠️ پلن تو تا {fa(self.lim['max_per_hour'])} در ساعت است — روی همان تنظیم شد."
                 if capped else "")
            return f"{nm} — سقف ساعتی: **{t}**{w}\n{self.brief(tier)}"

        if field == "gap":
            if not arg:
                return (f"فاصله فعلی: {fa(p['min_gap_sec'])}–{fa(p['max_gap_sec'])} ثانیه\n"
                        f"`{label('فاصله')} ۴۵ ۱۲۰`")
            try:
                ns = [num(x) for x in arg.split()]
                lo, hi = ns[0], (ns[1] if len(ns) > 1 else ns[0])
            except (ValueError, IndexError):
                return f"فرمت: `{label('فاصله')} ۴۵ ۱۲۰`"
            lo = max(1, lo)
            hi = max(1, hi)
            lo, capped = self.lim.cap_int("min_gap_sec", lo)
            hi = max(lo, hi)
            p["min_gap_sec"], p["max_gap_sec"] = lo, hi
            self.reload(tier)
            w = (f"\n⚠️ کف فاصله در پلن تو {fa(self.lim['min_gap_sec'])} ثانیه است."
                 if capped else "")
            return f"{nm} — فاصله: **{fa(lo)}–{fa(hi)} ثانیه**{w}\n{self.brief(tier)}"

        if field == "quiet":
            if not arg:
                cur = p.get("quiet_hours") or []
                q = "ندارد" if not cur else "، ".join(fa(h) for h in sorted(cur))
                return f"ساعت سکوت: {q}\n`{label('سکوت')} ۰ ۱ ۲ ۳`  |  `{label('سکوت')} خاموش`"
            if arg.lower() in ("off", "خاموش"):
                p["quiet_hours"] = []
            else:
                try:
                    p["quiet_hours"] = sorted({num(x) % 24 for x in arg.split()})
                except ValueError:
                    return f"فرمت: `{label('سکوت')} ۰ ۱ ۲ ۳`"
            self.reload(tier)
            cur = p["quiet_hours"]
            return (f"{nm} — ساعت سکوت: "
                    f"**{'حذف شد' if not cur else '، '.join(fa(h) for h in cur)}**")

    LINE_ = "━━━━━━━━━━━━━━━"

    # ---------- گزارش زنده برای پنل ----------
    def write_status(self, extra=None):
        try:
            c = self.db.counts()
            ec = self.db.ex_counts()
            now_t = int(time.time())
            d = {
                "ts": now_t,
                "pid": os.getpid(),
                "uptime": now_t - self.started,
                "account": self.me or "",
                "username": self.my_username,
                "user_id": self.my_id,
                "paused": bool(self.st["paused"]),
                "channels": {t: self.st.prof(t)["channel"] for t in
                             ("standard", "vip")},
                "queue": {"pending": self.db.pending_count()
                                     - self.db.held_count(),
                          "held": self.db.held_count(),
                          "sent": c.get("sent", 0),
                          "failed": c.get("failed", 0)},
                "sent_24h": self.db.sent_since(now_t - 86400),
                "sent_1h": self.db.sent_since(now_t - 3600),
                "phase": {t: self.cyc[t].phase()[0] for t in ("standard", "vip")},
                "capacity_blocked_until": int(self.ex_cfg().get(
                    "_capacity_join_blocked_until", 0) or 0),
                "cleanup_pending": bool(self.ex_cfg().get(
                    "_capacity_cleanup_pending", 0)),
                "exchange": {"on": bool(self.ex_cfg()["enabled"]),
                             "initiate": bool(self.ex_cfg()["initiate"]),
                             "joined": ec.get("joined", 0),
                             "pending": ec.get("pending", 0),
                             "left": ec.get("left", 0),
                             "today": self.db.ex_joins_today()},
                "ai": bool(self.ai.ready),
                "plan": self.lim["plan"],
                "last_error": self.last_error,
                "risk": self.risk_current()[0],
                "risk_on": bool(self.st["risk"].get("on", True)),
                "risk_trigger": self.st["risk"].get("trigger", 75),
                "risk_resume": self.st["risk"].get("resume", 55),
                "risk_auto_off": bool(self.st["risk"].get("_auto_off")),
                "hard_on": bool(self.st["risk"].get("hard_on", True)),
                "hard_trigger": self.st["risk"].get("hard_trigger", 80),
            }
            _hedge, _hparts, _hmeta = self.real_risk_edge()
            d.update({
                "hard_edge": bool(_hedge),
                "hard_score": _hmeta.get("score", 0),
            })
            if extra:
                d.update(extra)
            tmp = STATUS_FILE + ".tmp"
            with open(tmp, "w", encoding="utf-8") as f:
                json.dump(d, f, ensure_ascii=False)
            os.replace(tmp, STATUS_FILE)
        except Exception as e:
            print("write_status:", e)

    # ---------- تبادل ----------
    def ex_cfg(self):
        return self.st["exchange"]

    def ex_channel_ready(self):
        """قاعده‌ی اصلیِ تبادل: تا کانالِ معتبرِ خودت ثبت نشده، هیچ عملکردی نرو.

        کانال «عادی» اولویت دارد ولی اگر فقط VIP ست شده باشد هم کافی است
        (همان منطقِ `peer_in_my_channel`). مقدارِ ذخیره‌شده با همان
        اعتبارسنجیِ wizard سنجیده می‌شود تا داده‌ی خرابِ قدیمی (مثلاً
        کلمه‌ی «کانال» که اشتباهی ذخیره شده) «کانالِ ثبت‌شده» حساب نشود.
        """
        for tier in ("standard", "vip"):
            ch = (self.st.prof(tier)["channel"] or "").strip()
            if ch and normalize_peer_ref(ch):
                return True
        return False

    def hour_cap_wait(self, now=None):
        """سقف جوین/ساعت: اگر روشن باشد و در یک ساعتِ غلتان به سقف رسیده‌ایم،
        مدتِ مانده تا باز شدن پنجره را برمی‌گرداند؛ وگرنه ۰.
        (این محدودیت آهسته جدا از محافظ ریپورت است و فقط وقتی فعال باشد اجرا می‌شود.)"""
        x = self.ex_cfg()
        if not x.get("hour_cap_on"):
            return 0
        cap = max(1, int(x.get("hour_cap", 60) or 60))
        now = now or int(time.time())
        hour_ago = now - 3600
        n = self.db._x("SELECT COUNT(*) c FROM exchange "
                       "WHERE joined_at IS NOT NULL AND joined_at>=?", (hour_ago,), "one")["c"]
        if n < cap:
            return 0
        # قدیمی‌ترین جوینِ داخل پنجره؛ بعد از ۱ ساعت از آن، جا باز می‌شود.
        oldest = self.db._x("SELECT MIN(joined_at) m FROM exchange "
                            "WHERE joined_at IS NOT NULL AND joined_at>=?", (hour_ago,), "one")
        oldest = (oldest or {}).get("m") or now
        return max(1, int(oldest) + 3600 - now)

    # ── تطبیقیِ هوشمند: FloodWait + آپ‌تایم طولانی ──
    def adaptive_extra(self, now=None):
        """برمی‌گرداند (flood_extra, uptime_extra, total_extra)"""
        x = self.ex_cfg()
        if not x.get("adaptive_on", True):
            return 0, 0, 0
        now = now or int(time.time())
        flood_extra = max(0, int(x.get("_adaptive_flood_extra", 0) or 0))
        uptime = now - self.started
        thresh_h = int(x.get("adaptive_uptime_threshold_hours", 3) or 3)
        thresh = thresh_h * 3600
        uptime_extra = 0
        if uptime > thresh:
            uptime_extra = int(x.get("adaptive_uptime_extra_sec", 30) or 30)
            per_hour = int(x.get("adaptive_uptime_per_hour_sec", 10) or 10)
            extra_hours = int((uptime - thresh) // 3600)
            uptime_extra += extra_hours * per_hour
        # سقف: جریمه‌ی آپ‌تایم هرگز بی‌نهایت رشد نمی‌کند؛ وگرنه روی سرورِ
        # ۲۴/۷ (مثل رندر) بعد چند روز فاصله‌ی جوین به ده‌ها دقیقه می‌رسید و
        # عملاً تبادل می‌خوابید.
        up_max = int(x.get("adaptive_uptime_max_sec", 90) or 90)
        if up_max > 0:
            uptime_extra = min(uptime_extra, up_max)
        return flood_extra, uptime_extra, flood_extra + uptime_extra

    def effective_join_gap(self, now=None):
        """فاصله موثر جوین با احتساب تطبیقی"""
        x = self.ex_cfg()
        base_min = max(1, int(x.get("min_join_gap_sec", 30) or 30))
        base_max = max(base_min, int(x.get("max_join_gap_sec", 60) or 60))
        _, _, extra = self.adaptive_extra(now)
        return base_min + extra, base_max + extra

    def adaptive_on_flood(self, flood_seconds=0, now=None):
        """وقتی FloodWait می‌گیریم: هر بار ۱۵ ثانیه اضافه کن"""
        x = self.ex_cfg()
        if not x.get("adaptive_on", True):
            return 0
        now = now or int(time.time())
        step = max(1, int(x.get("adaptive_flood_step_sec", 15) or 15))
        max_extra = max(step, int(x.get("adaptive_flood_max_sec", 120) or 120))
        cur = max(0, int(x.get("_adaptive_flood_extra", 0) or 0))
        new = min(max_extra, cur + step)
        # 🧯 مدار قطع‌کن: فلود بزرگ (≥۱۰ دقیقه) یعنی سقف «تعداد جوین روزانه»
        # تلگرام فعال شده — نه فاصله‌ی کوتاه. اضافه مستقیم به سقف می‌رود و
        # تا پایان جریمه اجازه‌ی برگشت ندارد تا جریمه‌ی بعدی طولانی‌تر نشود.
        try:
            _w = int(flood_seconds or 0)
        except Exception:
            _w = 0
        if _w >= 600:
            new = max_extra
            x["_adaptive_flood_extra"] = new
            x["_adaptive_hard_until"] = int(now + min(_w, 6 * 3600))
        x["_adaptive_flood_extra"] = new
        x["_adaptive_last_flood"] = now
        x["_adaptive_last_decay"] = now
        self.st.save()
        # throttle را هم با فاصله جدید به‌روز کن
        try:
            emin, emax = self.effective_join_gap(now)
            self.join_thr.apply({"min_gap_sec": emin, "max_gap_sec": emax, "max_per_hour": 0})
        except Exception:
            pass
        self.log("warn", "adaptive_flood", f"+{step}s → extra={new}s (flood {flood_seconds}s)")
        return new

    def adaptive_maybe_decay(self, now=None):
        """اگر مدتی Flood نیامده، کم‌کم فاصله را برگردان"""
        x = self.ex_cfg()
        if not x.get("adaptive_on", True):
            return
        now = now or int(time.time())
        if now < int(x.get("_adaptive_hard_until", 0) or 0):
            return  # 🧯 حالت احتیاط: فاصله تا پایان جریمه برگشت نمی‌خورد
        cur = int(x.get("_adaptive_flood_extra", 0) or 0)
        if cur <= 0:
            return
        last = int(x.get("_adaptive_last_flood", 0) or 0)
        if not last:
            return
        decay_min = max(1, int(x.get("adaptive_flood_decay_min", 60) or 60))
        last_decay = int(x.get("_adaptive_last_decay", 0) or last)
        # هر decay_min دقیقه یک step کم کن
        elapsed = now - last_decay
        if elapsed < decay_min * 60:
            return
        steps = elapsed // (decay_min * 60)
        if steps <= 0:
            return
        step = max(1, int(x.get("adaptive_flood_step_sec", 15) or 15))
        new = max(0, cur - int(steps * step))
        x["_adaptive_flood_extra"] = new
        x["_adaptive_last_decay"] = now
        self.st.save()
        try:
            emin, emax = self.effective_join_gap(now)
            self.join_thr.apply({"min_gap_sec": emin, "max_gap_sec": emax, "max_per_hour": 0})
        except Exception:
            pass
        if new != cur:
            self.log("info", "adaptive_decay", f"-{steps*step}s → extra={new}s after {decay_min}min no flood")

    def adaptive_status_text(self):
        x = self.ex_cfg()
        on = bool(x.get("adaptive_on", True))
        base_min = int(x.get("min_join_gap_sec", 30) or 30)
        base_max = int(x.get("max_join_gap_sec", 60) or 60)
        f_extra, u_extra, total = self.adaptive_extra()
        emin, emax = self.effective_join_gap()
        uptime = int(time.time()) - self.started
        flood_step = int(x.get("adaptive_flood_step_sec", 15) or 15)
        flood_max = int(x.get("adaptive_flood_max_sec", 120) or 120)
        decay = int(x.get("adaptive_flood_decay_min", 60) or 60)
        up_thresh = int(x.get("adaptive_uptime_threshold_hours", 3) or 3)
        up_extra = int(x.get("adaptive_uptime_extra_sec", 30) or 30)
        up_per_h = int(x.get("adaptive_uptime_per_hour_sec", 10) or 10)
        up_max = int(x.get("adaptive_uptime_max_sec", 90) or 90)
        last_flood = int(x.get("_adaptive_last_flood", 0) or 0)
        last_str = "هرگز" if not last_flood else f"{secs(int(time.time())-last_flood)} پیش"
        return "\n".join([
            f"🧠 تطبیقیِ جوین: {'🟢 روشن' if on else '🔴 خاموش'}",
            "━━━━━━━━━━━━",
            f"پایه: {fa(base_min)}–{fa(base_max)} ثانیه",
            f"موثر فعلی: {fa(emin)}–{fa(emax)} ثانیه (پایه + تطبیقی)",
            f"  • اضافه از FloodWait: {fa(f_extra)} ثانیه",
            f"  • اضافه از آپ‌تایم ({fa(uptime//3600)}ساعت روشن): {fa(u_extra)} ثانیه",
            f"  • جمع اضافه: {fa(total)} ثانیه",
            *([f"🧯 حالت احتیاط: {secs(int(x.get('_adaptive_hard_until', 0) or 0) - int(time.time()))} دیگر — برگشت فاصله متوقف است"]
              if int(x.get("_adaptive_hard_until", 0) or 0) > int(time.time()) else []),
            "",
            f"⚙️ هر FloodWait: +{fa(flood_step)} ثانیه (سقف {fa(flood_max)} ثانیه)",
            f"♻️ کاهش خودکار: هر {fa(decay)} دقیقه بدون Flood، {fa(flood_step)} ثانیه کم می‌شود",
            f"⏳ کندشدن آپ‌تایم: بعد از {fa(up_thresh)} ساعت +{fa(up_extra)}ثانیه، هر ساعت اضافه +{fa(up_per_h)}ثانیه",
            f"  • سقف اضافه آپ‌تایم: {fa(up_max)} ثانیه (بعدش بیشتر نمی‌شود تا جوین‌ها روی سرور طولانی‌مدت نخوابند)",
            f"🕒 آخرین Flood: {last_str}",
            f"🕒 آپ‌تایم فعلی: {secs(uptime)}",
            "",
            "دستورها:",
            "`تبادل تطبیقی روشن/خاموش`",
            "`تبادل تطبیقی ریست` (صفر کردن اضافه Flood)",
            "`تبادل فاصله ۳۰ ۶۰` (تنظیم پایه)",
            "`تبادل تطبیقی` (نمایش همین صفحه)",
        ])

    def permanent_check_status_text(self):
        x = self.ex_cfg()
        on = bool(x.get("permanent_check", True))
        max_h = int(x.get("permanent_check_max_hours", 0) or 0)
        check_min = int(x.get("check_min_sec", 15) or 15)
        check_max = int(x.get("check_max_sec", 30) or 30)
        rem_min = int(x.get("reminder_min_sec", 20) or 20)
        rem_max = int(x.get("reminder_max_sec", 40) or 40)
        strikes = int(x.get("max_strikes", 2) or 2)
        # آمار فعلی
        joined_cnt = len(self.db.ex_list("joined", 500))
        pending_check = len(self.db.ex_due(int(time.time()), 100))
        return "\n".join([
            f"🔄 چک دائمی عضویت: {'🟢 روشن (تا ابد)' if on and max_h==0 else ('🟢 روشن' if on else '🔴 خاموش')}",
            "━━━━━━━━━━━━",
            f"وضعیت: {'تا ابد چک می‌کنم — هیچ‌وقت متوقف نمی‌شود' if on and max_h==0 else (f'روشن تا {fa(max_h)} ساعت بعد جوین' if on else 'خاموش')}",
            f"فاصله چک نگهبانی: {fa(check_min)}–{fa(check_max)} ثانیه تصادفی (هر بار دوباره رندوم)",
            "  با سن رکورد پلکانی بلند می‌شود: تا ۳۰دقیقه ×۱، تا ۲ساعت ×۲، تا ۶ساعت ×۴، بعدش ×۸",
            f"فاصله «نیومدی»: {fa(rem_min)}–{fa(rem_max)} ثانیه تصادفی — دوبار می‌گوید بعد لفت",
            f"صف تک‌عملکردی: هیچ دو عملکردی پشت‌سرهم نمی‌روند — {fa(int(x.get('op_gap_min_sec', 15) or 0))}–{fa(int(x.get('op_gap_max_sec', 20) or 0))} ثانیه صبر بعد از هر عملکرد (چک/جوین/لفت/پیام)",
            "چکِ بی‌نتیجه: فقط بررسی مجدد؛ نه پیام ناموفق و نه لفت",
            f"لفت: بعد از {fa(strikes)} بار نبودنِ تأییدشده (هرکدام با چک دوم) — نه با یک منفیِ تنها",
            "",
            f"📊 الان {fa(joined_cnt)} کانال جوین‌شده تحت نظر نگهبانی",
            f"⏳ {fa(pending_check)} مورد نوبت چک فوری",
            "",
            "⚙️ دستورها:",
            "`تبادل بررسی ۱۵ ۳۰` → فاصله چک عضویت (پیش‌فرض ۱۵-۳۰ ثانیه، هر بار رندوم)",
            "`تبادل اخطار ۲` → بعد چند بار نبودن لفت بده (پیش‌فرض ۲)",
            "`تبادل فاصله یادآوری ۲۰ ۴۰` → فاصله دو پیام «نیومدی»",
            "`تبادل فاصله عملکرد ۱۵ ۲۰` → فاصله بین هر دو عملکرد (چک/جوین/لفت/پیام)",
            "`تبادل دائمی روشن/خاموش`",
            "`تبادل دائمی ساعت 0` → ۰=تا ابد، ۲۴=فقط ۲۴ ساعت چک کن (پیش‌فرض ۲۴)",
            "`تبادل دائمی` → نمایش همین صفحه",
        ])

    def should_watch_joined(self, rec, now=None):
        """آیا این رکورد جوین‌شده هنوز باید دائمی چک شود؟"""
        x = self.ex_cfg()
        if not x.get("permanent_check", True):
            # اگر چک دائمی خاموش است، فقط تا recheck_hours چک کن
            max_h = int(x.get("permanent_check_max_hours", 0) or x.get("recheck_hours", 0) or 0)
            if max_h <= 0:
                return False
            now = now or int(time.time())
            joined_at = int(rec.get("joined_at") or rec.get("created_at") or now)
            return (now - joined_at) <= max_h * 3600
        # دائمی روشن
        max_h = int(x.get("permanent_check_max_hours", 0) or 0)
        if max_h <= 0:
            return True  # تا ابد
        now = now or int(time.time())
        joined_at = int(rec.get("joined_at") or rec.get("created_at") or now)
        return (now - joined_at) <= max_h * 3600

    def risk_current(self):
        """(درصد_ریسک, جزئیات_هرمورد, آمار_خام) — بر پایه بازه‌ی زمانی تنظیم‌شده.

        دو لایه:
          1) ریسکِ پایه (بلندمدت) — چقدر در ۲۴ ساعتِ اخیر فعالیت داشته.
          2) ریسکِ پرش (burst) — چقدر در «ساعتِ اخیر» ناگهانی عمل کرده.
        تلگرام به لینکِ نحوه‌ی حرکت (پرشِ ناگهانی) خیلی بیشتر از میانگین حساس است؛
        پس این دو لایه با هم جمع می‌شوند تا هم پیشگیریِ واقعی باشد و هم
        جوینِ عادیِ پخش‌شده در طول روز حساب نشود.
        """
        rc = self.st["risk"]
        window = max(1, int(rc.get("window_hours", 24) or 24)) * 3600
        since = int(time.time()) - window
        hour_ago = int(time.time()) - 3600

        def count(sql, args):
            return self.db._x(sql, args, "one")["c"]

        # ── شمارش بازه‌ی ۲۴ ساعته ──
        sent = count("SELECT COUNT(*) c FROM queue WHERE status='sent' AND sent_at>=?",
                     (since,))
        joins = count("SELECT COUNT(*) c FROM exchange "
                      "WHERE joined_at IS NOT NULL AND joined_at>=?", (since,))
        left = count("SELECT COUNT(*) c FROM events WHERE kind='ex_left' AND ts>=?",
                     (since,))
        failed = count("SELECT COUNT(*) c FROM events WHERE kind='ex_join_fail' AND ts>=?",
                       (since,))
        flood24 = count("SELECT COUNT(*) c FROM events "
                        "WHERE lower(kind) LIKE '%flood%' AND ts>=?", (since,))
        strikes = count("SELECT COUNT(*) c FROM events WHERE kind='ex_strike' AND ts>=?",
                        (since,))
        # ── شمارش بازه‌ی «ساعتِ اخیر» برای تشخیص پرش ──
        joins_h = count("SELECT COUNT(*) c FROM exchange "
                        "WHERE joined_at IS NOT NULL AND joined_at>=?", (hour_ago,))
        flood_h = count("SELECT COUNT(*) c FROM events "
                        "WHERE lower(kind) LIKE '%flood%' AND ts>=?", (hour_ago,))
        left_h = count("SELECT COUNT(*) c FROM events WHERE kind='ex_left' AND ts>=?",
                       (hour_ago,))

        # ── سهمِ پایه (بلندمدت) ──
        BASE = [  # (برچسب, ضریب, سقفِ نقش)
            ("ارسال",        0.02,  4),   # 200 ارسال/روز → 4
            ("جوین",         0.40, 38),   # 95 جوین/روز → 38؛ به‌تنهایی به سقف می‌رسد، نه توقف
            ("لفت",          1.50, 12),   # 8 لفت/روز → 12
            ("خطای جوین",    1.00,  4),   # 4 خطا/روز → 4
            ("فلاد",         7.00, 20),   # 3 فلاد/روز → 20؛ زمینه‌ی خطر
            ("برگشت‌نکردن",  0.30,  2),
        ]
        base_counts = {"ارسال": sent, "جوین": joins, "لفت": left,
                       "خطای جوین": failed, "فلاد": flood24, "برگشت‌نکردن": strikes}
        base = sum(min(cap, float(base_counts[n] or 0) * unit)
                   for n, unit, cap in BASE)

        # ── سهمِ پرش (کوتاه‌مدت) — عاملِ اصلیِ توقف ──
        BURST = [  # (برچسب, ضریب, سقفِ نقش)
            ("پرش جوین (۱ ساعت)",    1.40, 42),   # 30+ جوین/ساعت → 42؛ توقف با یک پرشِ واقعی
            ("پرش فلاد (۱ ساعت)",   30.0, 60),   # 2+ فلاد/ساعت → 60 (فوری)
            ("پرش لفت (۱ ساعت)",     1.5, 10),   # 7+ لفت/ساعت → 10
        ]
        burst_counts = {"پرش جوین (۱ ساعت)": joins_h, "پرش فلاد (۱ ساعت)": flood_h,
                        "پرش لفت (۱ ساعت)": left_h}
        burst = sum(min(cap, float(burst_counts[n] or 0) * unit)
                    for n, unit, cap in BURST)

        risk = round(min(100.0, max(0.0, base + burst)), 1)

        parts = {f"پایه·{n}": round(min(100.0, min(cap, float(base_counts[n] or 0) * unit) / cap * 100), 1)
                 for n, unit, cap in BASE}
        parts.update({f"پرش·{n}": round(min(100.0, min(cap, float(burst_counts[n] or 0) * unit) / cap * 100), 1)
                      for n, unit, cap in BURST})
        meta = {"sent": sent, "joins": joins, "left": left, "failed": failed,
                "flood": flood24, "strikes": strikes, "window": window,
                "joins_1h": joins_h, "flood_1h": flood_h, "left_1h": left_h}
        return risk, parts, meta

    def real_risk_edge(self, now=None):
        """پایشِ سیگنال‌های *واقعی* ریپ شدن اکانت — مستقل از امتیازِ انتزاعی.

        سیگنال‌های واقعی (یعنی تلگرام خودش واکنش نشان داده):
          • FloodWait واقعی (تلگرام خواسته صبر کنی) — قوی‌ترین نشانه‌ی محدود شدن
          • خطاهای پشت‌سرهمِ ورود (تحریمِ حساب از سمت تلگرام)
          • رسیدن به سقف کانال/محدودیتِ حسابی
        وقتی این‌ها در بازه‌ی کوچک تکرار شوند = «مرزِ ریپ» → توقف اجباری.

        برمی‌گرداند (در_مرز_هست, جزئیات, آمار_خام).
        """
        rc = self.st["risk"]
        now = now or int(time.time())
        win = max(5, int(rc.get("hard_window_min", 30) or 30)) * 60
        since = now - win
        since10 = now - 600

        def count(sql, args=()):
            return self.db._x(sql, args, "one")["c"]

        flood = count("SELECT COUNT(*) c FROM events WHERE lower(kind) LIKE '%flood%' AND ts>=?", (since,))
        flood10 = count("SELECT COUNT(*) c FROM events WHERE lower(kind) LIKE '%flood%' AND ts>=?", (since10,))
        # فقط خطاهایِ «محدودیتِ حسابیِ خودِ اکانت» سیگنالِ واقعیِ ریپ هستند؛
        # خطاهایِ خودِ لینکِ خریدار (منقضی/خصوصی/ناموجود) اینجا حساب نمی‌شوند
        # تا توقفِ اجباریِ کاذب رخ ندهد.
        fails = count("SELECT COUNT(*) c FROM events WHERE kind='ex_join_limit' AND ts>=?", (since,))
        fails10 = count("SELECT COUNT(*) c FROM events WHERE kind='ex_join_limit' AND ts>=?", (since10,))
        retries = count("SELECT COUNT(*) c FROM events WHERE kind='ex_join_retry' AND ts>=?", (since,))

        # ── امتیازِ واقعی (از نرخ حوادثِ واقعی، نه از شمارشِ کارِ عادی) ──
        score = 0.0
        score += min(45, flood * 22)          # 1 فلاد در بازه=22، 2=45
        score += min(35, flood10 * 35)        # پرشِ فلاد در ۱۰ دقیقه — محکم‌تر
        score += min(25, fails * 8)           # خطاهای ورود
        score += min(25, fails10 * 14)
        score += min(15, retries * 3)
        score = round(score, 1)

        # ── مرزِ ریپ: یا چند نشانه‌ی هم‌زمان، یا یک نشانه‌ی بسیار قوی ──
        trigger = float(rc.get("hard_trigger", 80))
        #  ۲ فلاد در ۱۰ دقیقه، یا (۱ فلاد + ۲ خطا در ۱۰ دقیقه)، یا ۴+ خطا در ۱۰ دقیقه
        critical = (flood10 >= 2) or (flood >= 1 and fails10 >= 2) or (fails10 >= 4)
        edge = critical or score >= trigger

        parts = {
            f"فلاد در {win // 60}د": flood,
            f"فلاد در ۱۰د": flood10,
            f"خطای ورود در {win // 60}د": fails,
            f"خطای ورود در ۱۰د": fails10,
            f"تلاش مجدد": retries,
        }
        meta = {"flood": flood, "flood_10": flood10, "fails": fails,
                "fails_10": fails10, "retries": retries, "win": win,
                "score": score, "critical": critical}
        return edge, parts, meta

    def risk_status_text(self):
        rc = self.st["risk"]
        risk, parts, meta = self.risk_current()
        x = self.ex_cfg()
        guard_on = bool(rc.get("on", True))
        hard_on = bool(rc.get("hard_on", True))
        edge, rparts, rmeta = self.real_risk_edge()
        ex_on = bool(x["enabled"])
        auto = ("🌑 خاموشِ خودکار توسط محافظ" if rc.get("_auto_off")
                else ("🙌 روشنِ دستی/بدون خاموشی خودکار" if ex_on else "—"))
        if edge and hard_on:
            edge_state = "🔴 **در مرز ریپ — توقف اجباری فعال**"
        elif edge:
            edge_state = "🟠 در مرز ریپ ولی پایش خاموش است — توقف اجباری نمی‌زند"
        else:
            edge_state = "🟢 عادی — در مرز ریپ نیست"
        rtbl = "   ".join(f"{k}: <b>{v}</b>" for k, v in rparts.items())
        o = [
            "🛡 محافظ ریپورت — دو چیزِ جدا",
            "━━━━━━━━━━━━",
            "🔴 **پایشِ واقعی** (همیشه فعال، نگهبانِ اصلی):",
            f"   وضعیت: {edge_state}",
            f"   امتیازِ واقعی: <b>{rmeta['score']}</b>  (مرز {rc.get('hard_trigger', 80)})",
            "   فقط نشانه‌ی واقعیِ محدودیتِ تلگرام را می‌شمارد:",
            "   " + rtbl,
            "   **جوینِ عادی اینجا هیچ نقشی ندارد.**",
            "   `ریسک پایش روشن/خاموش`",
            "━━━━━━━━━━━━",
        ]
        # ── لایه‌ی انتزاعی: اگر خاموش است فقط به‌عنوان «نمایش» بیاید، نه کنترل ──
        if guard_on:
            o += [
                "🟡 **توقف بر امتیاز** (فقط وقتی روشن باشد):",
                f"   امتیازِ انتزاعی: <b>{risk}%</b>  ·  آستانه‌ی خاموشی: "
                f"<b>{rc.get('trigger', 75)}%</b>  ·  بازگشت: <b>{rc.get('resume', 55)}%</b>",
                "   این مدل **علاوه بر فلاد، جوینِ عادی را هم می‌شمارد** "
                "و به آن «درصد» می‌دهد؛ با `ریسک خاموش` غیرفعال می‌شود.",
                f"   بازه‌ی {fa(meta['window'] // 3600)} ساعت · جوین: {fa(meta['joins'])} · "
                f"فلاد: {fa(meta['flood'])} · خطا: {fa(meta['failed'])}",
            ]
        else:
            o += [
                "⚪ **توقف بر امتیاز: خاموش** — فقط برای نمایش:",
                f"   امتیازِ انتزاعی: <b>{risk}%</b> (اگر روشن بود، آستانه‌ی "
                f"خاموشی {rc.get('trigger', 75)}% بود)",
                "   این مدل جوینِ عادی را هم می‌شمارد و به آن «درصد» می‌دهد؛ "
                "**الان هیچ کنترلی ندارد** و چیزی را خاموش نمی‌کند.",
                "   فقط `ریسک روشن` آن را فعال می‌کند.",
            ]
        o += [
            "━━━━━━━━━━━━",
            f"تبادل: {'🟢 روشن' if ex_on else '🔴 خاموش'}   ·   {auto}",
            "",
            "💡 فرقِ اصلی: پایشِ واقعی فقط به **واکنشِ خودِ تلگرام** نگاه می‌کند؛ "
            "توقف بر امتیاز به **مقدارِ کارِ ما** (حتی جوینِ سالم) امتیاز می‌دهد.",
            "",
            "`ریسک بررسی` الان · `ریسک ریست` پاک‌کردن وضعیت",
        ]
        return "\n".join(o)

    def risk_cmd(self, arg):
        rc = self.st["risk"]
        a = re.sub(r"\s+", " ", (arg or "").strip())
        low = a.lower()
        if low in ("on", "روشن", "فعال") or a in ("روشن", "فعال"):
            rc["on"] = True
            self.st.save()
            return "🛡 محافظ ریپورت **روشن** شد."
        if low in ("off", "خاموش", "غیرفعال") or a in ("خاموش", "غیرفعال"):
            rc["on"] = False
            self.st.save()
            return "🛡 محافظ ریپورت **خاموش** شد. (تبادل به‌صورت خودکار دیگر کنترل نمی‌شود)"
        if low.startswith(("trigger", "آستانه", "حد ")) or a.startswith("آستانه"):
            m = re.search(r"(\d+(?:\.\d+)?)", a)
            if not m:
                return "فرمت: `ریسک آستانه 75`"
            val = max(10.0, min(100.0, float(m.group(1))))
            rc["trigger"] = val
            # فاصله‌ی منطقی ۱۵ درصدی: همیشه آستانه‌ی بازگشت پایین‌تر می‌ماند
            resume = float(rc.get("resume", 55))
            if resume >= val - 5:
                rc["resume"] = max(1.0, val - 15)
            self.st.save()
            return (f"🛡 آستانه‌ی خاموشی: <b>{val:.0f}%</b>  ·  "
                    f"بازگشت زیر: <b>{rc['resume']:.0f}%</b>")
        if low.startswith(("resume", "بازگشت")):
            m = re.search(r"(\d+(?:\.\d+)?)", a)
            if not m:
                return "فرمت: `ریسک بازگشت 55`"
            val = max(1.0, min(100.0, float(m.group(1))))
            trigger = float(rc.get("trigger", 75))
            if val >= trigger - 5:
                return (f"❌ آستانه‌ی بازگشت باید دست‌کم ۵ درصد از "
                        f"آستانه‌ی خاموشی ({trigger:.0f}%) کمتر باشد.")
            rc["resume"] = val
            self.st.save()
            return f"🛡 بازگشایی زیر <b>{val:.0f}%</b> شد."
        if low.startswith(("reset", "ریست", "پاک", "بازنشانی")):
            rc["_auto_off"] = False
            rc["_last_off"] = 0
            self.st.save()
            return "🛡 وضعیت خاموشیِ خودکار پاک شد. تبادل با وضعیت فعلی‌اش می‌ماند."
        if low.startswith(("پایش", "hard", "واقعی")) or a.startswith("پایش"):
            # کلمه‌ی «روشن/خاموش» اگر باشد، جهت را تعیین می‌کند؛ وگرنه toggle.
            if "خاموش" in low or "off" in a.lower():
                new = False
            elif "روشن" in low or "on" in a.lower() or "فعال" in low:
                new = True
            else:
                new = not bool(rc.get("hard_on", True))
            rc["hard_on"] = new
            self.st.save()
            return ("🔴 پایشِ واقعیِ ریپ **خاموش** شد — دیگر هیچ‌وقت توقف اجباری نمی‌زند."
                    if not new else
                    "🟢 پایشِ واقعیِ ریپ **روشن** شد — در مرز ریپ توقف اجباری می‌زند.")
        if low in ("check", "now", "بررسی", "الان", "وضعیت"):
            return self.risk_status_text()
        # پیش‌فرض: وضعیت
        return self.risk_status_text()


    def exchange_cmd(self, arg):
        x = self.ex_cfg()
        raw = (arg or "").strip()
        # دستورهای چندکلمه‌ای فارسی باید قبل از split شدن تشخیص داده شوند.
        normalized = re.sub(r"\s+", " ", raw.replace("\u200c", " ")).strip()
        multi = (
            ("متن بدون لینک", "msgnolink"),
            ("متن ناموفق", "msgno"),
            ("متن انتظار", "msgwait"),
            ("متن موفق", "msgok"),
            ("پیام بدون لینک", "msgnolink"),
            ("پیام ناموفق", "msgno"),
            ("پیام ادعای جوین", "msgclaimno"),
            ("پیام ادعا", "msgclaimno"),
            ("پیام انتظار", "msgwait"),
            ("پیام موفق", "msgok"),
            ("پیام بیا", "come"),
            ("پیام", "come"),
            ("زمان بیا", "cometime"),
            ("زمان جواب", "replytime"),
            ("سقف روزانه", "maxday"),
            ("سقف ساعتی", "hourcap"),
            ("سقف هر ساعت", "hourcap"),
            ("سقف جوین ساعت", "hourcap"),
            ("زمان پاسخ", "response_delay"),
            ("تأخیر پاسخ", "response_delay"),
            ("تعداد یادآوری", "max_reminders"),
            ("حداکثر یادآوری", "max_reminders"),
            ("گزارش لحظه‌ای", "report_live"),
            ("گزارش لحظه ای", "report_live"),
            ("گزارش روشن", "report_live"),
            ("گزارش خلاصه همین الان", "report_now"),
            ("گزارش خلاصه الان", "report_now"),
            ("گزارش خلاصه", "report_now"),
            ("گزارش خاموش", "report_off"),
            ("گزارش الان", "report_now"),
            ("گزارش هر", "report_every"),
            ("گزارش", "report"),
            ("فاصله یادآوری", "reminder_gap"),
            ("نوسان یادآوری", "reminder_gap"),
            ("فاصله عملکرد", "op_gap"),
            ("فاصله عملکردها", "op_gap"),
            ("فاصله عملیات", "op_gap"),
            ("صف عملکرد", "op_gap"),
            ("فاصله تبادل", "gap"),
            ("زمان تبادل", "gap"),
            ("عمق اسکن", "scanlimit"),
            ("سن لینک", "scan_age"),
            ("حداکثر سن لینک", "scan_age"),
            ("انتخاب پیام", "scan_pick"),
            ("اسکن هر", "scanevery"),
            ("بررسی هر", "every"),
            ("گروه‌ها", "groups"),
            ("گروه ها", "groups"),
            ("پیش قدم", "go"),
            ("پیشقدم", "go"),
            ("تطبیقی", "adaptive"),
            ("حالت تطبیقی", "adaptive"),
            ("جوین تطبیقی", "adaptive"),
            ("گپ تطبیقی", "adaptive"),
            ("فاصله تطبیقی", "adaptive"),
            ("دائمی", "permanent"),
            ("چک دائمی", "permanent"),
            ("نگهبانی دائمی", "permanent"),
            ("بررسی دائمی", "permanent"),
            ("اسکن تصادفی", "scan_jitter"),
            ("تاخیر اسکن", "scan_jitter"),
            ("تأخیر اسکن", "scan_jitter"),
            ("فاصله اسکن", "scan_jitter"),
            ("ضد اسپم", "scan_jitter"),
            ("لفت خودکار", "capacity_leave"),
            ("پاکسازی سقف", "capacity_leave"),
            ("گروه جایگزین", "groupfailover"),
            ("جایگزین گروه", "groupfailover"),
            ("گروه پشتیبان", "groupfailover"),
            ("جایگزین", "groupfailover"),
            ("پشتیبان", "groupfailover"),
            ("همه دستورها", "cmds"),
            ("همه دستورات", "cmds"),
            ("راهنمای حالت ها", "guide"),
            ("راهنمای حالت‌ها", "guide"),
            ("راهنمای حالت", "guide"),
            ("تشخیص هوشمند", "smart"),
        )
        sub = rest = ""
        for phrase, canonical in multi:
            if normalized == phrase or normalized.startswith(phrase + " "):
                sub = canonical
                # بخش بعد از فرمان را از متن اصلی بردار تا نیم‌فاصله‌های
                # متن پیام، مثل «می‌کنم»، از بین نرود.
                words = phrase.split()
                pattern = r"^\s*" + r"[\s\u200c]+".join(
                    re.escape(w) for w in words) + r"(?:\s+|\u200c+|$)"
                match = re.match(pattern, raw, flags=re.S)
                if match:
                    rest = raw[match.end():].strip()
                else:
                    rest = normalized[len(phrase):].strip()
                break
        if not sub:
            parts = normalized.split(None, 1)
            sub = parts[0].lower() if parts else ""
            rest = parts[1].strip() if len(parts) > 1 else ""
        ex_aliases = {
            "روشن": "on", "خاموش": "off", "خودکار": "auto",
            "جواب": "reply", "متن": "msg", "پیشقدم": "go",
            "پیش‌قدم": "go", "اسکن": "scan", "ارسال": "replynow",
            "فرستادن": "replynow", "گروهها": "groups",
            "گروه‌ها": "groups", "کلمات": "words", "فاصله": "gap",
            "سقفروزانه": "maxday", "سقف روزانه": "maxday",
            "سقفساعتی": "hourcap", "سقف ساعتی": "hourcap",
            "سقف هر ساعت": "hourcap", "سقف جوین ساعت": "hourcap",
            "بررسی": "check", "فهرست": "list", "منتظرها": "wait",
            "تأیید": "ok", "تایید": "ok", "رد": "no", "خروج": "out",
            "حذف": "del", "اول": "msgfirst", "موفق": "msgok",
            "ناموفق": "msgno", "انتظار": "msgwait", "بدون لینک": "msgnolink",
            "پیام ادعا": "msgclaimno", "پیام ادعای جوین": "msgclaimno",
            "گروه": "groups", "گروه‌ها": "groups", "گروه ها": "groups",
            "افزودن": "add", "اضافه": "add",
            "اخطار": "strikes", "اسکن هر": "scanevery",
            "انتخاب": "scan_pick", "زمان پاسخ": "response_delay", "تأخیر پاسخ": "response_delay",
            "یادآوری": "reminder_gap", "فاصله یادآوری": "reminder_gap",
            "نوسان یادآوری": "reminder_gap", "تعداد یادآوری": "max_reminders",
            "عملکرد": "op_gap", "عملکردها": "op_gap",
            "فاصله عملکرد": "op_gap", "فاصله عملکردها": "op_gap",
            "فاصله عملیات": "op_gap", "صف عملکرد": "op_gap",
            "opgap": "op_gap", "op_gap": "op_gap",
            "حداکثر یادآوری": "max_reminders",
            "سن لینک": "scan_age", "حداکثر سن لینک": "scan_age",
            "گزارش": "report", "گزارش لحظه‌ای": "report_live",
            "گزارش لحظه ای": "report_live", "گزارش روشن": "report_live",
            "گزارش خلاصه الان": "report_now", "گزارش خلاصه همین الان": "report_now",
            "خلاصه": "report_now",
            "فاصله تبادل": "gap", "زمان تبادل": "gap",
            "تطبیقی": "adaptive", "حالت تطبیقی": "adaptive", "جوین تطبیقی": "adaptive",
            "بیا": "come", "پیام بیا": "come", "زمان بیا": "cometime",
            "زمان جواب": "replytime", "زمان پاسخ مستقیم": "replytime",
            "replytime": "replytime", "reply_time": "replytime", "reply_delay": "replytime",
            "راهنما": "guide", "حالت‌ها": "guide", "حالت ها": "guide",
            "دستورها": "cmds", "دستورات": "cmds", "دستور": "cmds",
            "کامندها": "cmds", "commands": "cmds", "help": "guide",
            "تشخیص": "smart", "smart": "smart", "detect": "smart",
        }
        sub = ex_aliases.get(sub, sub)
        if sub == "check":
            sub = "every"
        if sub == "scan" and rest:
            rnorm = rest.replace("\u200c", " ").strip()
            if rnorm.startswith("هر "):
                sub, rest = "scanevery", rnorm[3:].strip()
        if sub == "هر":
            sub = "gap"
            rest = re.sub(r"\s*(?:ثانیه|ثانیه‌ای)\s*$", "", rest).strip()

        if not sub:
            return self.exchange_text()
        if sub in ("تنظیمات", "تنظیمات تبادل", "settings"):
            return self.ex_settings_text()
        if sub in ("guide", "راهنما"):
            return self.ex_guide_text()
        if sub in ("cmds", "دستورها"):
            return self.ex_commands_text()
        if sub in ("smart", "تشخیص"):
            # روشن/خاموش‌کردن تشخیص هوشمند پیام و لینک (هوش مصنوعی)
            try:
                self.ai.cfg["smart_detect"] = not bool(
                    self.ai.cfg.get("smart_detect", True))
                self.ai.save()
            except Exception:
                pass
            on = bool((getattr(self.ai, "cfg", {}) or {}).get("smart_detect"))
            return ("🔍 تشخیص هوشمند پیام و لینک: **" +
                    ("روشن" if on else "خاموش") + "**\n\n" +
                    self.exchange_text())

        if sub in ("on", "روشن"):
            if not self.lim.allowed("exchange"):
                return ("🔒 تبادل در پلن فعلی تو نیست.\n"
                        "برای فعال شدن، پلن را ارتقا بده.")
            # ── قاعده‌ی “اول کانال، بعد گروه” ──
            # بدون کانال، نه اسکنِ گروه لازم است نه چکِ عضویت؛ روشن‌کردنِ
            # تبادل فقط این توهم را می‌ساخت که ربات دارد کار می‌کند و در
            # عمل هیچ‌چیز تأیید نمی‌شد. حالا روشن‌کردن هم رد می‌شود.
            if not self.ex_channel_ready():
                x["enabled"] = False
                self.st.save()
                return ("❌ تبادل روشن **نشد** — اول کانالِ خودت رو ثبت کن.\n\n"
                        "📡 `کانال @mychannel`\n"
                        "⚡ یا کلِ راه با هم: `تبادل سریع`\n\n"
                        "قاعده: تا کانال ثبت نشه، ربات سراغ گروهِ تبادل نمی‌ره، "
                        "عضویت کسی رو چک نمی‌کنه و جوین/لفت نمی‌زنه.")
            x["enabled"] = True
            # تصمیم دستیِ کاربر، خاموشیِ خودکارِ محافظ را باطل می‌کند
            self.st["risk"]["_auto_off"] = False
            self.st.save()
            w = ""
            if not any(x[k] for k in ("msg_ok", "msg_wait",
                                      "msg_nolink", "msg_first", "msg_come")):
                w += ("\n\n💬 هنوز متنی برای جواب‌ها تعیین نکرده‌ای؛ فعلاً فقط "
                      "پیش‌فرضِ «نیومدی» برای عضو‌نشده‌ها می‌رود "
                      "(فقط چک و جوین می‌کنم).\n`متن‌های تبادل`")
            return f"🔁 تبادل **روشن** شد.{w}"

        if sub in ("off", "خاموش"):
            x["enabled"] = False
            # خاموشیِ دستی: محافظ نباید دوباره خودکار روشنش کند
            self.st["risk"]["_auto_off"] = False
            self.st.save()
            return "🔁 تبادل **خاموش** شد."

        if sub == "auto":
            x["auto_join"] = not x["auto_join"]
            self.st.save()
            return ("🔁 جوین **خودکار** — هرکه تأیید شد، بدون پرسیدن جوین می‌شوم."
                    if x["auto_join"] else
                    "🔁 **تأیید دستی** — اول به تو خبر می‌دهم، با `تبادل تأیید ۵` جوین می‌شوم.")

        if sub == "reply":
            x["reply"] = not x["reply"]
            self.st.save()
            return f"💬 جواب دادن به طرف: **{'روشن' if x['reply'] else 'خاموش'}**"

        if sub == "replynow":
            if not rest:
                return "برای ارسال دوباره، شماره را بده: `تبادل ارسال ۱`"
            rec = self.db.ex_find(rest)
            if not rec:
                return "تبادل پیدا نشد."
            if rec["status"] != "joined":
                return "این تبادل هنوز Join نشده است."
            x["_reply_now"] = rec["id"]
            self.st.save()
            return f"✅ پیام تبادل `#{fa(rec['id'])}` در نوبت ارسال قرار گرفت."

        if sub in ("msg", "msgs", "متن"):
            return self.ex_msgs_text()

        if sub in ("come", "msgcome"):
            if not rest:
                cur = x.get("msg_come") or x.get("msg_ok") or "— خاموش"
                return (f"متن بعد از Join موفق: {cur}\n"
                        "`تبادل پیام متن دلخواه` برای تغییر\n"
                        "مثال: `تبادل پیام جوین شدم جوین شو`\n"
                        "`تبادل پیام خاموش` برای خاموش‌کردن")
            if rest.lower() in ("off", "خاموش", "پاک", "حذف", "-"):
                x["msg_come"] = ""
                x["msg_first"] = ""
                x["msg_ok"] = ""
                self.st.save()
                return "🚫 پیام بعد از جوین خاموش شد."
            x["msg_come"] = rest
            x["msg_first"] = rest
            # این فرمان، متن موفقیت همه Joinها را یکسان می‌کند؛
            # چه Join آخرین لینک گروه باشد و چه تبادل عادی.
            x["msg_ok"] = rest
            x["reply"] = True
            self.st.save()
            return f"✅ متن بعد از Join ذخیره شد:\n\n{rest}"

        if sub in ("cometime", "come_time"):
            if not rest:
                lo = int(x.get("come_min_sec", 34) or 34)
                hi = int(x.get("come_max_sec", 35) or 35)
                lo, hi = max(1, lo), max(lo, hi)
                shown = (f"{fa(lo)} ثانیه"
                         if lo == hi else f"تصادفی بین {fa(lo)} تا {fa(hi)} ثانیه")
                return (f"تأخیر پیام «بیا» بعد از جوین: {shown}\n"
                        "`تبادل زمان بیا ۳۴ ۳۵` (هر دو عدد = بازه)  |  "
                        "`تبادل زمان بیا ۴۰` (یک عدد = ثابت)")
            rest = re.sub(r"\s*(?:ثانیه|ثانیه‌ای)\s*$", "", rest).strip()
            try:
                ns = [num(v) for v in rest.split()]
                if len(ns) == 1:
                    v = max(1, min(3600, ns[0]))
                    lo, hi = v, v
                else:
                    lo = max(1, min(3600, ns[0]))
                    hi = max(lo, min(3600, ns[1]))
            except (ValueError, IndexError):
                return "فرمت: `تبادل زمان بیا ۳۴ ۳۵` (بازه) یا `تبادل زمان بیا ۴۰` (ثابت)"
            x["come_min_sec"] = lo
            x["come_max_sec"] = hi
            # سازگاری با تنظیم‌های قدیم: اگر بازه ۰ نبود، کلید قدیمی هم
            # روی مقدار وسط ست می‌شود تا گزارش‌های قدیمی اشتباه نکنند.
            x["come_delay_sec"] = (lo if lo == hi else (lo + hi) // 2)
            self.st.save()
            shown = (f"{fa(lo)} ثانیه"
                     if lo == hi else f"تصادفی بین {fa(lo)} تا {fa(hi)} ثانیه")
            return f"⏱ تأخیر پیام «بیا»: **{shown}**"

        if sub in ("replytime", "reply_time", "reply_delay"):
            if not rest:
                lo = int(x.get("reply_min_sec", 5) or 5)
                hi = int(x.get("reply_max_sec", 18) or 18)
                lo, hi = max(1, lo), max(lo, hi)
                shown = (f"{fa(lo)} ثانیه"
                         if lo == hi else f"تصادفی بین {fa(lo)} تا {fa(hi)} ثانیه")
                return (f"تأخیر پاسخ‌های مستقیم (عضو نیست/صبر کن/کانالت): {shown}\n"
                        "`تبادل زمان جواب ۵ ۱۸` (بازه)  |  `تبادل زمان جواب ۱۰` (ثابت)")
            rest = re.sub(r"\s*(?:ثانیه|ثانیه‌ای)\s*$", "", rest).strip()
            try:
                ns = [num(v) for v in rest.split()]
                if len(ns) == 1:
                    v = max(1, min(3600, ns[0]))
                    lo, hi = v, v
                else:
                    lo = max(1, min(3600, ns[0]))
                    hi = max(lo, min(3600, ns[1]))
            except (ValueError, IndexError):
                return "فرمت: `تبادل زمان جواب ۵ ۱۸`"
            x["reply_min_sec"] = lo
            x["reply_max_sec"] = hi
            self.st.save()
            shown = (f"{fa(lo)} ثانیه"
                     if lo == hi else f"تصادفی بین {fa(lo)} تا {fa(hi)} ثانیه")
            return f"⏱ تأخیر پاسخ‌های مستقیم: **{shown}**"

        if sub in ("msgok", "msgno", "msgclaimno", "msgwait", "msgnolink",
                   "msgfirst"):
            key = {"msgok": "msg_ok", "msgno": "msg_no", "msgwait": "msg_wait",
                   "msgclaimno": "msg_claim_no",
                   "msgnolink": "msg_nolink", "msgfirst": "msg_first"}[sub]
            pretty = {"msgok": "پیام موفق", "msgno": "پیام ناموفق",
                      "msgclaimno": "پیام ادعای جوین",
                      "msgwait": "پیام انتظار", "msgnolink": "پیام بدون لینک",
                      "msgfirst": "پیام بیا"}[sub]
            when = {"msgok": "عضو بود و جوین شدم",
                    "msgno": "عضو نبود — جوین نمی‌شوم",
                    "msgclaimno": "گفته جوین شدم ولی عضو نیست",
                    "msgwait": "در حال بررسی‌ام",
                    "msgnolink": "کانالش را پیدا نکردم",
                    "msgfirst": "خودم پیش‌قدم شدم و جوین شدم"}[sub]
            command = f"تبادل {pretty}"
            if not rest:
                cur = x[key]
                if cur:
                    return (f"**متن فعلی** ({when}):\n\n{cur}\n\n"
                            f"عوض‌کردن: `{command} متن جدید`\n"
                            f"برداشتن: `{command} خاموش`")
                if sub == "msgclaimno":
                    return (f"**{when}** — متنی تعیین نکرده‌ای، پس همان متنِ "
                            "«پیام ناموفق» می‌رود (و اگر آن هم خالی باشد، "
                            f"پیش‌فرض «{DEFAULT_MSG_NO}» + کانال خودت).\n\n"
                            f"`{command} متن دلخواهت`\n\n"
                            "می‌توانی از این‌ها هم استفاده کنی:\n"
                            "`{name}` اسم طرف • `{mychannel}` کانال خودت. "
                            "لینک طرف به‌صورت خودکار در متن نمی‌آید؛ `{channel}` پشتیبانی نمی‌شود.")
                if sub == "msgno":
                    # پیام ناموفق همیشه پیش‌فرض دارد؛ خاموشی معنا ندارد.
                    return (f"**{when}** — متنی تعیین نکرده‌ای، پس پیش‌فرض "
                            f"«{DEFAULT_MSG_NO}» + کانال خودت می‌رود (نه کانال طرف). "
                            "اگر متن سفارشی ثبت کرده باشی، فقط همان متن می‌رود و "
                            "هیچ لینکی زیرش اضافه نمی‌شود — لینک طرف هرگز اتوماتیک نمی‌آید. "
                            "فقط به کسی می‌رود که لینکش را فرستاده یا کانالش قبلاً در "
                            "تبادل ثبت شده؛ ریپلای‌های تصادفی جواب نمی‌گیرند.\n\n"
                            f"`{command} متن دلخواهت`\n\n"
                            "می‌توانی از این‌ها هم استفاده کنی:\n"
                            "`{name}` اسم طرف • `{mychannel}` کانال خودت. "
                            "لینک طرف به‌صورت خودکار در متن نمی‌آید؛ `{channel}` پشتیبانی نمی‌شود.")
                return (f"**{when}** — متنی تعیین نکرده‌ای، پس چیزی نمی‌فرستم.\n\n"
                        f"`{command} متن دلخواهت`\n\n"
                        "می‌توانی از این‌ها هم استفاده کنی:\n"
                        "`{name}` اسم طرف • `{mychannel}` کانال خودت. "
                        "لینک طرف به‌صورت خودکار در متن نمی‌آید؛ `{channel}` پشتیبانی نمی‌شود.")
            if rest.lower() in ("off", "خاموش", "پاک", "حذف", "-"):
                x[key] = ""
                if sub == "msgfirst":
                    x["msg_come"] = ""
                self.st.save()
                if sub == "msgclaimno":
                    return ("🚫 برداشته شد — از این به بعد برای «گفتی جوین شدم "
                            "ولی نیستی» همان متنِ «پیام ناموفق» می‌رود.")
                if sub == "msgno":
                    return (f"🚫 برداشته شد — از این به بعد پیش‌فرض "
                            f"«{DEFAULT_MSG_NO}» می‌رود.")
                return f"🚫 برداشته شد — دیگر {when} چیزی نمی‌فرستم."
            x[key] = rest
            if sub == "msgfirst":
                x["msg_come"] = rest
            x["reply"] = True
            self.st.save()
            return f"✅ ذخیره شد ({when}):\n\n{rest}"

        if sub in ("go", "پیشقدم"):
            if not x["initiate"] and not self.lim.allowed("initiate"):
                return ("🔒 حالت پیش‌قدم در پلن فعلی تو نیست.\n"
                        "برای فعال شدن، پلن را ارتقا بده.")
            x["initiate"] = not x["initiate"]
            self.st.save()
            if not x["initiate"]:
                return "🚶 حالت پیش‌قدم **خاموش** شد — فقط منتظر ریپلای دیگران می‌مانم."
            w = ""
            if not x["groups"]:
                w += ("\n\n⚠️ گروهی تعیین نکرده‌ای — جایی برای اسکن ندارم."
                      "\n`افزودن گروه @tabadol`")
            if not (x.get("msg_come") or x.get("msg_first")):
                w += ("\n\n💬 متن بعد از جوین را تعیین نکرده‌ای، پس جوین می‌شوم "
                      "ولی چیزی نمی‌گویم.\n`تبادل پیام بیا`")
            return (f"🚶 حالت پیش‌قدم **روشن** شد.\n"
                    f"هر {secs(max(30, int(x.get('scan_every_sec', 30) or 30)))} گروه‌ها را نگاه می‌کنم، "
                    f"کانال‌ها را جوین می‌شوم و متنت را ریپلای می‌زنم.{w}")

        if sub in ("scanevery",):
            if not rest:
                sec = max(30, int(x.get("scan_every_sec", 30) or 30))
                return (f"هر {secs(sec)} اسکن می‌کنم\n"
                        "`تبادل اسکن هر 30 ثانیه`")
            raw_scan = rest.strip()
            is_seconds = "ثانیه" in raw_scan
            raw_scan = re.sub(r"\s*(?:ثانیه|ثانیه‌ای|دقیقه|دقیقه‌ای)\s*$", "", raw_scan).strip()
            try:
                v = max(1, num(raw_scan))
            except ValueError:
                return "فرمت: `تبادل اسکن هر 30 ثانیه` یا `تبادل اسکن هر 1 دقیقه`"
            sec = max(30, v if is_seconds else v * 60)
            x["scan_every_sec"] = sec
            x["scan_every_min"] = max(1, (sec + 59) // 60)
            self.st.save()
            return f"🔍 اسکن پیش‌قدم هر **{secs(sec)}**"

        if sub in ("scan_jitter", "jitter"):
            # ضد اسپم چندگروهی: فقط وقتی ۲ گروه یا بیشتر داری
            jitter_min = int(x.get("scan_jitter_min_sec", 5) or 5)
            jitter_max = int(x.get("scan_jitter_max_sec", 15) or 15)
            groups_cnt = len(x.get("groups") or [])
            if not rest:
                if groups_cnt >= 2:
                    return (f"🔀 ضد اسپم چندگروهی **فعال** (چون {fa(groups_cnt)} گروه داری):\n"
                            f"بنر اول سر {fa(x.get('scan_every_sec', 30))} ثانیه، دومی {fa(jitter_min)}–{fa(jitter_max)} ثانیه تصادفی بعد\n"
                            f"تک گروه = بدون تأخیر اضافه (مثل قبل)\n"
                            f"`تبادل اسکن تصادفی 5 15` برای تغییر")
                else:
                    return (f"🔀 ضد اسپم چندگروهی **غیرفعال** (چون {fa(groups_cnt)} گروه داری — تک گروه مثل قبل هر {fa(x.get('scan_every_sec', 30))} ثانیه)\n"
                            f"اگر ۲ گروه بذاری خودکار فعال میشه: اولی سر ۳۰ ثانیه، دومی ۵–۱۵ ثانیه تصادفی بعد\n"
                            f"`تبادل اسکن تصادفی 5 15`")
            rest = rest.replace("ثانیه", "").replace("تصادفی", "").strip()
            try:
                ns = [num(v) for v in rest.split()]
                lo = max(1, min(60, ns[0]))
                hi = max(lo, min(60, ns[1] if len(ns) > 1 else ns[0]))
            except (ValueError, IndexError):
                return "فرمت: `تبادل اسکن تصادفی 5 15` یا `تبادل ضد اسپم 5 15`"
            x["scan_jitter_min_sec"] = lo
            x["scan_jitter_max_sec"] = hi
            self.st.save()
            if groups_cnt >= 2:
                return (f"✅ ضد اسپم چندگروهی تنظیم شد: **{fa(lo)}–{fa(hi)} ثانیه** تصادفی بین گروه‌ها\n"
                        f"الان {fa(groups_cnt)} گروه داری → بنر اول سر {fa(x.get('scan_every_sec', 30))} ثانیه، بقیه هر کدام {fa(lo)}–{fa(hi)}s بعد")
            else:
                return (f"✅ تأخیر تصادفی ذخیره شد: **{fa(lo)}–{fa(hi)} ثانیه**\n"
                        f"الان تک گروه داری، پس فعلاً بدون تأخیر اضافه کار می‌کنه. وقتی ۲ گروه بذاری خودکار فعال میشه.")

        if sub in ("scanlimit", "عمق", "عمق اسکن"):
            if not rest:
                return (f"هر بار {fa(x['scan_limit'])} پیام آخر را می‌بینم\n"
                        "`تبادل عمق اسکن ۵۰`")
            try:
                v = max(1, min(200, num(rest)))
            except ValueError:
                return "عدد بده: `تبادل عمق اسکن ۵۰`"
            x["scan_limit"] = v
            self.st.save()
            return f"🔍 عمق اسکن: **{fa(v)} پیام**"

        if sub == "scan_age":
            current_min = max(1, int(x.get("scan_max_age_sec", 300) or 300) // 60)
            if not rest:
                return (f"سن مجاز لینک: حداکثر {fa(current_min)} دقیقه\n"
                        "`تبادل سن لینک 5`")
            is_hours = "ساعت" in rest
            raw_age = re.sub(r"\s*(?:ساعت|ساعته|دقیقه|دقیقه‌ای)\s*$", "", rest).strip()
            try:
                value = max(1, min(168 if is_hours else 1440, num(raw_age)))
            except ValueError:
                return "عدد بده: `تبادل سن لینک 5`"
            seconds = value * (3600 if is_hours else 60)
            x["scan_max_age_sec"] = seconds
            x["scan_age_version"] = 1
            self.st.save()
            unit = "ساعت" if is_hours else "دقیقه"
            return f"🔍 فقط لینک‌های حداکثر **{fa(value)} {unit}** اخیر بررسی می‌شوند."

        if sub == "scan_pick":
            if not rest:
                return (f"انتخاب پیام: مورد {fa(x.get('scan_pick', 2) or 2)} از جدیدترین لینک‌ها\n"
                        "`تبادل انتخاب پیام 2` یعنی پیام یکی‌مانده‌به‌آخر")
            try:
                v = max(1, min(200, num(rest)))
            except ValueError:
                return "عدد بده: `تبادل انتخاب پیام 2`"
            x["scan_pick"] = v
            self.st.save()
            return f"✅ پیام شماره {fa(v)} از جدیدترین لینک‌ها انتخاب می‌شود."

        if sub == "scan":
            if not x["enabled"]:
                return "اول `تبادل روشن` را بفرست، بعد `تبادل اسکن` را بزن."
            x["_scan_now"] = True
            return "🔍 اسکن فوری در نوبت — نتیجه را همین‌جا می‌گویم."

        if sub in ("words", "کلمات"):
            if rest.lower().startswith("خاموش"):
                rest = "off"
            if not rest:
                w = x["words"]
                return ("🔤 **کلمات کلیدی**\n\n" +
                        ("فقط ریپلای‌هایی که یکی از این‌ها را دارند بررسی می‌شوند:\n"
                         + "، ".join(f"`{i}`" for i in w)
                         if w else "خالی — به **هر** ریپلایی روی پیام تو واکنش نشان می‌دهم.") +
                        "\n\n`تبادل کلمات جوین شدم | اومدم | عضو شدم`"
                        "\n`تبادل کلمات خاموش` برای برداشتن")
            if rest.lower() in ("off", "خاموش", "پاک", "-"):
                x["words"] = []
            else:
                sep = "|" if "|" in rest else ("،" if "،" in rest else ",")
                x["words"] = [w.strip() for w in rest.split(sep) if w.strip()]
            self.st.save()
            w = x["words"]
            return ("🔤 کلمات کلیدی: " +
                    ("، ".join(f"`{i}`" for i in w) if w
                     else "برداشته شد — هر ریپلایی بررسی می‌شود"))

        if sub in ("capacity_leave", "leave_completed"):
            action = re.sub(r"\s+", " ", rest.replace("\u200c", " ")).strip().lower()
            enabled = bool(x.get("auto_leave_completed_on_limit", True))
            if not action:
                blocked_until = int(x.get("_capacity_join_blocked_until", 0) or 0)
                blocked = (f"\n⏸ تلاش برای جوین تا {secs(blocked_until - int(time.time()))} متوقف است."
                           if blocked_until > int(time.time()) else "")
                batch = clamp_capacity_batch(
                    x.get("capacity_cleanup_batch", CAPACITY_CLEANUP_BATCH_DEFAULT))
                return ("🧹 لفتِ خودکار برای سقف عضویت تلگرام: "
                        f"{'روشن' if enabled else 'خاموش'}{blocked}\n"
                        f"وقتی سقف پر شود، یک دور پاکسازی تا {fa(batch)} کانالِ جفج‌زده‌ی "
                        "قدیمی را لفت می‌دهم (فقط تبادلِ کامل‌شده؛ در پیش‌قدم، طرف هم "
                        "باید به کانال تو جوین شده باشد) و بعد جوینِ معلق را دوباره می‌زنم.\n"
                        "`تبادل لفت خودکار روشن` / `خاموش`\n"
                        "`تبادل لفت خودکار تعداد ۳۰` برای تغییر تعداد هر دور\n"
                        "بعد از آزادکردن جا دستی: `تبادل لفت خودکار ریست`")
            nums = re.findall(r"[۰-۹0-9]+", action)
            if nums:
                val = clamp_capacity_batch(num(nums[0]))
                x["capacity_cleanup_batch"] = val
                self.st.save()
                return (f"✅ هر دور پاکسازی سقف، تا {fa(val)} کانالِ جفج‌زده را "
                        "لفت می‌دهم.\n"
                        "`تبادل لفت خودکار تعداد <عدد>` برای تغییر دوباره.")
            if action in ("ریست", "reset", "آزاد"):
                x["_capacity_join_blocked_until"] = 0
                self.st.save()
                return "✅ توقف جوین به‌خاطر سقف پاک شد؛ اگر جا آزاد باشد تبادل ادامه می‌دهد."
            if action in ("روشن", "فعال", "on", "true"):
                x["auto_leave_completed_on_limit"] = True
                self.st.save()
                return ("✅ لفت امن برای سقف عضویت روشن شد؛ فقط تبادلِ کامل‌شده انتخاب می‌شود "
                        "و در پیش‌قدم، جوین‌شدن طرف به کانال تو هم لازم است.")
            if action in ("خاموش", "غیرفعال", "off", "false"):
                x["auto_leave_completed_on_limit"] = False
                self.st.save()
                return "✅ لفت خودکار برای سقف عضویت خاموش شد؛ در صورت پرشدن سقف، دستی لفت بده."
            return "فرمت: `تبادل لفت خودکار روشن` یا `تبادل لفت خودکار خاموش`."

        if sub in ("groupfailover", "failover", "backupgroup"):
            groups = list(x.get("groups") or [])
            now = int(time.time())
            action = re.sub(r"\s+", " ", rest.replace("\u200c", " ")).strip()
            action_low = action.lower()
            if not action:
                enabled = bool(x.get("group_failover_on"))
                active_i = int(x.get("_group_failover_active_index", 0) or 0)
                active_i = min(max(active_i, 0), max(0, len(groups) - 1))
                primary = groups[0] if groups else "ثبت نشده"
                backup = groups[1] if len(groups) > 1 else "ثبت نشده"
                state = "روشن" if enabled and len(groups) > 1 else "خاموش"
                minutes = max(1, int(x.get("group_failover_after_sec", 300) or 300) // 60)
                active = groups[active_i] if groups else "—"
                return ("🔁 **جایگزینی گروه (اختیاری)**\n"
                        f"وضعیت: {state}\nگروه اصلی: `{primary}`\n"
                        f"گروه پشتیبان: `{backup}`\nگروه فعال: `{active}`\n"
                        f"انتقال پس از {fa(minutes)} دقیقه بدون لینک تازه\n\n"
                        "تنظیم گروه پشتیبان: `تبادل گروه جایگزین @backup`\n"
                        "روشن/خاموش: `تبادل گروه جایگزین روشن` / `خاموش`\n"
                        "تغییر زمان: `تبادل گروه جایگزین بعد ۵` (دقیقه)")
            if action_low in ("روشن", "فعال", "on", "true"):
                if len(groups) < 2:
                    return ("برای روشن‌کردن جایگزینی، اول گروه اصلی و پشتیبان را ثبت کن؛ "
                            "مثلاً `تبادل گروه @main @backup`.\n"
                            "قابلیت اختیاری است و تا آن زمان رفتار قبلی تغییری نمی‌کند.")
                x["group_failover_on"] = True
                x["_group_failover_active_index"] = 0
                x["_group_failover_last_activity"] = now
                self.st.save()
                return (f"✅ جایگزینی گروه روشن شد. `{groups[0]}` گروه اصلی و "
                        f"`{groups[1]}` پشتیبان است؛ پس از {fa(max(1, int(x.get('group_failover_after_sec', 300)) // 60))} دقیقه بی‌لینک‌ماندن جابه‌جا می‌شود.")
            if action_low in ("خاموش", "غیرفعال", "off", "false"):
                x["group_failover_on"] = False
                x["_group_failover_active_index"] = 0
                self.st.save()
                return "✅ جایگزینی گروه خاموش شد؛ اسکن با رفتار عادی قبلی ادامه دارد."
            if action_low.startswith(("بعد", "پس از", "after")) or re.fullmatch(r"\d+", action.translate(EN)):
                match = re.search(r"\d+", action.translate(EN))
                if not match:
                    return "فرمت زمان: `تبادل گروه جایگزین بعد ۵` (دقیقه، از ۱ تا ۱۰۰۸۰)"
                minutes = max(1, min(10080, int(match.group(0))))
                x["group_failover_after_sec"] = minutes * 60
                self.st.save()
                return f"⏱ انتقال به گروه پشتیبان پس از {fa(minutes)} دقیقه بدون لینک تازه انجام می‌شود."
            backup = normalize_peer_ref(action)
            if backup:
                if not groups:
                    return "اول گروه اصلی را ثبت کن؛ مثلاً `تبادل گروه @main`؛ بعد گروه پشتیبان را بده."
                if same_peer_ref(backup, groups[0]):
                    return "❌ گروه پشتیبان باید با گروه اصلی متفاوت باشد."
                own_channels = [self.st.prof(t).get("channel") for t in ("standard", "vip")]
                if any(same_peer_ref(backup, channel) for channel in own_channels):
                    return "❌ گروه پشتیبان نمی‌تواند یکی از کانال‌های خودت باشد."
                # مورد دوم جایگزین می‌شود؛ گروه‌های بعدی با همان ترتیب حفظ می‌شوند.
                tail = [g for g in groups[2:] if not same_peer_ref(g, backup)]
                x["groups"] = [groups[0], backup] + tail
                x["group_failover_on"] = True
                x["_group_failover_active_index"] = 0
                x["_group_failover_last_activity"] = now
                self.st.save()
                return (f"✅ گروه پشتیبان ثبت و جایگزینی روشن شد: `{groups[0]}` → `{backup}`.\n"
                        "خاموش‌کردن اختیاری: `تبادل گروه جایگزین خاموش`")
            return ("فرمت: `تبادل گروه جایگزین @backup`، `روشن`، `خاموش` یا "
                    "`بعد ۵` (دقیقه).")

        if sub == "removegroup":
            target = rest.strip().lower()
            before = self.ex_cfg().get("groups") or []
            kept = [g for g in before if g.strip().lstrip("@").lower() != target.lstrip("@")]
            self.ex_cfg()["groups"] = kept
            if len(kept) < 2:
                self.ex_cfg()["group_failover_on"] = False
            self.ex_cfg()["_group_failover_active_index"] = 0
            self.ex_cfg()["_group_failover_last_activity"] = int(time.time())
            self.st.save()
            if len(kept) == len(before):
                return "این گروه در فهرست نبود."
            return f"✅ گروه حذف شد: {rest}"

        if sub == "groups":
            # گروه‌ها با «افزودن گروه» هم قابل ثبت هستند.
            if rest.lower().startswith("افزودن "):
                rest = rest[7:].strip()
            if not rest:
                g = x["groups"]
                listed = ("، ".join(f"`{i}`" for i in g) if g else "هیچ — فقط پیام خصوصی")
                failover_state = ("روشن — گروه اول اصلی، گروه دوم پشتیبان"
                                  if x.get("group_failover_on") and len(g) >= 2
                                  else "خاموش — رفتار قبلی حفظ می‌شود")
                return ("📡 گروه‌های رصدشده: " + listed +
                        f"\n🔁 جایگزینی اختیاری: {failover_state}" +
                        "\n\n`افزودن گروه @g1 @g2`  |  `حذف همه گروه‌ها`\n"
                        "`تبادل گروه جایگزین` برای تنظیم و فعال‌سازی اختیاری")
            if rest.lower() in ("off", "خاموش", "none"):
                x["groups"] = []
                x["group_failover_on"] = False
            else:
                current = list(x.get("groups") or [])
                for group in (w.strip() for w in rest.split() if w.strip()):
                    if group.lower() not in {g.lower() for g in current}:
                        current.append(group)
                x["groups"] = current
            x["_group_failover_active_index"] = 0
            x["_group_failover_last_activity"] = int(time.time())
            if len(x.get("groups") or []) < 2:
                x["group_failover_on"] = False
            self.st.save()
            g = x["groups"]
            return ("📡 گروه‌ها: " + ("، ".join(f"`{i}`" for i in g) if g
                    else "پاک شد — فقط پیام خصوصی"))

        if sub == "gap":
            if not rest:
                return (f"فاصله جوین: {fa(x['min_join_gap_sec'])}–"
                        f"{fa(x['max_join_gap_sec'])} ثانیه\n"
                        f"`تبادل فاصله {fa(x['min_join_gap_sec'])} {fa(x['max_join_gap_sec'])}`\n"
                        "برای فاصله ثابت: `تبادل هر ۳۰ ثانیه`")
            rest = re.sub(r"\s*(?:ثانیه|ثانیه‌ای)\s*$", "", rest).strip()
            try:
                ns = [num(v) for v in rest.split()]
                lo = max(1, ns[0])
                hi = max(lo, ns[1] if len(ns) > 1 else ns[0])
            except (ValueError, IndexError):
                return "فرمت: `تبادل فاصله ۹۰ ۲۴۰` یا `تبادل هر ۱۲۰ ثانیه`"
            x["min_join_gap_sec"], x["max_join_gap_sec"] = lo, hi
            self.st.save()
            self.join_thr.apply({"min_gap_sec": lo, "max_gap_sec": hi, "max_per_hour": 0})
            return f"⏱ فاصله جوین: **{fa(lo)}–{fa(hi)} ثانیه**"

        if sub == "op_gap":
            if not rest:
                lo = int(x.get("op_gap_min_sec", 15) or 0)
                hi = int(x.get("op_gap_max_sec", 20) or lo)
                return (f"⏳ فاصله بین عملکرد‌های تبادل: {fa(lo)} تا {fa(hi)} ثانیه تصادفی\n"
                        "در هر لحظه فقط **یک** عملکرد (چک عضویت / جوین / لفت / «نیومدی» / «جوین شدم»)\n"
                        "اجرا می‌شود؛ بعد از تمام‌شدنش همین‌قدر صبر می‌شود و بعد نوبتِ بعدی.\n"
                        "روی هر رکورد هم رعایت می‌شود: مثلاً بعد از جوین، چکِ عضویت زودتر از این نمی‌رود\n"
                        "و دو پیام «نیومدی» پشت‌سرهم نمی‌افتند.\n\n"
                        "`تبادل فاصله عملکرد ۱۵ ۲۰` (پیش‌فرض)  |  `تبادل فاصله عملکرد ۲۵` (ثابت)")
            rest = re.sub(r"\s*(?:ثانیه|ثانیه‌ای)\s*$", "", rest).strip()
            try:
                ns = [num(v) for v in rest.split()]
                if len(ns) == 1:
                    lo = max(1, min(3600, ns[0]))
                    hi = lo
                else:
                    lo = max(1, min(3600, ns[0]))
                    hi = max(lo, min(3600, ns[1]))
            except (ValueError, IndexError):
                return "فرمت: `تبادل فاصله عملکرد ۱۵ ۲۰`"
            x["op_gap_min_sec"] = lo
            x["op_gap_max_sec"] = hi
            # کفِ فاصله‌ها هم با همین بازه بالا می‌رود تا هیچ عملکردی
            # کوتاه‌تر از فاصله‌ی درخواستی کاربر پشت‌سرهم نرود.
            if int(x.get("reminder_min_sec", 0) or 0) < lo:
                x["reminder_min_sec"] = lo
            if int(x.get("reminder_max_sec", 0) or 0) < x["reminder_min_sec"]:
                x["reminder_max_sec"] = x["reminder_min_sec"]
            if int(x.get("check_min_sec", 0) or 0) < lo:
                x["check_min_sec"] = lo
            if int(x.get("check_max_sec", 0) or 0) < x["check_min_sec"]:
                x["check_max_sec"] = x["check_min_sec"]
            # نوبت‌های معطلِ در دیتابیس هم از حالا روی زمانِ درست بیفتند.
            nowg = int(time.time())
            for r in self.db._x("SELECT * FROM exchange WHERE next_reminder>0"
                                " OR next_check>0 LIMIT 300", (), "all"):
                kw = {}
                if int(r.get("next_reminder") or 0) > 0:
                    kw["next_reminder"] = max(int(r["next_reminder"]), nowg + lo)
                if int(r.get("next_check") or 0) > 0:
                    kw["next_check"] = max(int(r["next_check"]), nowg + lo)
                if kw:
                    self.db.ex_set(r["id"], **kw)
            self.st.save()
            shown = (f"{fa(lo)} ثانیه" if lo == hi
                     else f"تصادفی بین {fa(lo)} تا {fa(hi)} ثانیه")
            return (f"⏳ فاصله بین عملکرد‌های تبادل: **{shown}**\n"
                    "هیچ دو عملکردی (چک/جوین/لفت/پیام) پشت‌سرهم نمی‌روند — "
                    "اولی تمام می‌شود، این‌قدر صبر، بعد دومی.")

        if sub == "reminder_gap":
            if not rest:
                return (f"فاصله یادآوری «نیومدی»: {fa(x.get('reminder_min_sec', 20))} تا "
                        f"{fa(x.get('reminder_max_sec', 40))} ثانیه تصادفی (هر بار رندوم)\n"
                        "`تبادل فاصله یادآوری ۲۰ ۴۰` (پیش‌فرض)")
            rest = re.sub(r"\s*(?:ثانیه|ثانیه‌ای)\s*$", "", rest).strip()
            try:
                ns = [num(v) for v in rest.split()]
                lo = max(1, ns[0])
                hi = max(lo, ns[1] if len(ns) > 1 else ns[0])
            except (ValueError, IndexError):
                return "فرمت: `تبادل فاصله یادآوری ۲۰ ۴۰`"
            x["reminder_min_sec"], x["reminder_max_sec"] = lo, hi
            # همگام‌سازی: چک عضویت هم با همین بازه
            x["check_min_sec"], x["check_max_sec"] = lo, hi
            x["check_interval_sec"] = hi if lo == hi else 0
            for r in self.db.ex_list("joined", 200):
                self.db.ex_set(r["id"], next_check=0)
            self.st.save()
            return f"🔔 فاصله یادآوری «نیومدی» و چک عضویت: **{fa(lo)}–{fa(hi)} ثانیه تصادفی** — دوبار «نیومدی» بعد لفت، هر بار رندوم"

        if sub == "response_delay":
            if not rest:
                if "response_min_sec" in x or "response_max_sec" in x:
                    lo = int(x.get("response_min_sec", 11) or 11)
                    hi = int(x.get("response_max_sec", 48) or 48)
                    lo, hi = max(0, lo), max(lo, hi)
                    shown = (f"{fa(lo)} ثانیه"
                             if lo == hi else f"تصادفی بین {fa(lo)} تا {fa(hi)} ثانیه")
                else:
                    shown = f"{fa(int(x.get('response_delay_sec', 15) or 15))} ثانیه"
                return (f"تأخیر پاسخ بعد از Join: {shown}\n"
                        "`تبادل زمان پاسخ ۱۱ ۴۸` (بازه)  |  `تبادل زمان پاسخ 15` (ثابت)")
            rest = re.sub(r"\s*(?:ثانیه|ثانیه‌ای)\s*$", "", rest).strip()
            try:
                ns = [num(v) for v in rest.split()]
                if len(ns) == 1:
                    v = max(0, min(3600, ns[0]))
                    lo, hi = v, v
                else:
                    lo = max(0, min(3600, ns[0]))
                    hi = max(lo, min(3600, ns[1]))
            except (ValueError, IndexError):
                return "فرمت: `تبادل زمان پاسخ ۱۱ ۴۸` یا `تبادل زمان پاسخ 15`"
            x["response_min_sec"] = lo
            x["response_max_sec"] = hi
            # سازگاری: کلید قدیمی هم به‌روزرسانی شود.
            x["response_delay_sec"] = (lo if lo == hi else (lo + hi) // 2)
            self.st.save()
            shown = (f"{fa(lo)} ثانیه"
                     if lo == hi else f"تصادفی بین {fa(lo)} تا {fa(hi)} ثانیه")
            return f"⏱ تأخیر پاسخ: **{shown}**"

        if sub == "maxday":
            x["max_joins_per_day"] = 0
            self.st.save()
            return "♾️ سقف روزانه Join حذف شده است — Join نامحدود است."

        if sub == "hourcap":
            on = bool(x.get("hour_cap_on", False))
            cap = int(x.get("hour_cap", 60) or 60)
            # اگر عددی آمده، اول مقدار را تنظیم کن و فعالش کن.
            rest_num = re.sub(r"\s*(?:جوین|جوین|بار)\s*$", "", (rest or "").strip())
            if rest_num and (rest_num.isdigit() or re.fullmatch(r"[۰-۹]+", rest_num)):
                try:
                    cap = max(1, min(5000, num(rest_num)))
                except ValueError:
                    pass
                x["hour_cap"] = cap
                x["hour_cap_on"] = False
                self.st.save()
                return (f"⚙️ سقف جوین/ساعت روی **{fa(cap)}** ست شد — هنوز **خاموش** است. "
                        f"برای فعال‌کردن: `تبادل سقف ساعتی روشن`")
            if rest_num.lower() in ("on", "روشن", "فعال"):
                x["hour_cap_on"] = True
                self.st.save()
                return (f"✅ سقف جوین/ساعت **روشن** شد. در یک ساعتِ غلتان بیشتر از "
                        f"**{fa(cap)}** جوین نمی‌زنم و تا باز شدن پنجره صبر می‌کنم.\n"
                        f"غیرفعال: `تبادل سقف ساعتی خاموش`")
            if rest_num.lower() in ("خاموش", "off"):
                x["hour_cap_on"] = False
                x["_hour_cap_blocked"] = 0
                self.st.save()
                return (f"🔓 سقف جوین/ساعت **خاموش** شد — دوباره آزادانه و بدون سقف ساعتی "
                        f"جوین می‌زنم (فقط محافظ ریپورت بالای سر است).")
            # بدون آرگومان: نمایش وضعیت
            if on:
                return (f"🟢 سقف جوین/ساعت **روشن**: حداکثر {fa(cap)} جوین در هر ساعت. "
                        f"`تبادل سقف ساعتی خاموش` برای برداشتن.")
            return (f"⚪ سقف جوین/ساعت **خاموش** (پیش‌فرض — فقط با دستور فعال می‌شود).\n"
                    f"عددِ امنِ پیشنهادی: **{fa(cap)}** جوین در ساعت.\n"
                    f"فعال‌کردن: `تبادل سقف ساعتی روشن`  ·  تغییر عدد: `تبادل سقف ساعتی 60`")

        if sub == "every":
            lo = max(1, int(x.get("check_min_sec", 15) or 15))
            hi = max(lo, int(x.get("check_max_sec", 30) or 30))
            if not rest:
                if lo == hi:
                    return (f"هر {fa(lo)} ثانیه چک می‌شود\n"
                            "`تبادل بررسی 15 30` برای حالت تصادفی")
                return (f"چک عضویت: تصادفی بین {fa(lo)} تا {fa(hi)} ثانیه\n"
                        "`تبادل بررسی 15 30`")
            rest = re.sub(r"\s*(?:ثانیه|ثانیه‌ای)\s*$", "", rest).strip()
            rest = re.sub(r"^(?:تصادفی|نوسانی|رندوم)\s+", "", rest).strip()
            try:
                ns = [num(v) for v in rest.split()]
                lo, hi = max(1, ns[0]), max(1, ns[1] if len(ns) > 1 else ns[0])
                hi = max(lo, hi)
            except (ValueError, IndexError):
                return "فرمت: `تبادل بررسی 15 30` یا `تبادل بررسی 30`"
            x["check_min_sec"], x["check_max_sec"] = lo, hi
            # همگام‌سازی: فاصله یادآوری «نیومدی» هم با همین بازه تصادفی تنظیم می‌شود
            # تا هر بار که بخواهد بگوید بین همون عدد تصادفی که تنظیم کردی باشد.
            x["reminder_min_sec"], x["reminder_max_sec"] = lo, hi
            # برای سازگاری با نسخه‌های قدیمی نگه داشته می‌شود؛ موتور جدید
            # همیشه min/max را استفاده می‌کند.
            x["check_interval_sec"] = hi if lo == hi else 0
            # تغییر تنظیم، چک همه موارد انجام‌شده را از نو زمان‌بندی می‌کند.
            for r in self.db.ex_list("joined", 200):
                self.db.ex_set(r["id"], next_check=0)
            for r in self.db._x("SELECT * FROM exchange WHERE next_reminder>0 LIMIT 200", (), "all"):
                self.db.ex_set(r["id"], next_reminder=int(__import__('time').time()) + __import__('random').randint(lo, hi))
            self.st.save()
            return (f"🔄 چک عضویت و یادآوری «نیومدی»: "
                    f"{'هر ' + fa(lo) + ' ثانیه' if lo == hi else 'تصادفی بین ' + fa(lo) + ' تا ' + fa(hi) + ' ثانیه تصادفی — هر بار دوباره رندوم'}\n"
                    f"• چک دائمی: {fa(lo)}–{fa(hi)}s | • «نیومدی» دوبار بعد لفت، هر بار {fa(lo)}–{fa(hi)}s")

        if sub in ("max_reminders", "reminders"):
            if not rest:
                v = max(0, int(x.get("max_reminders", 2) or 0))
                return (f"حداکثر پیام «عضو نیست»: {fa(v)} بار"
                        + ("؛ بعد از آن لفت" if v else "") + "\n"
                        "`تبادل تعداد یادآوری ۲` — `۰` یعنی بدون پیام")
            rest = re.sub(r"\s*(?:بار|پیام)\s*$", "", rest).strip()
            try:
                v = max(0, min(3, num(rest)))
            except ValueError:
                return "عدد بده: `تبادل تعداد یادآوری ۲`"
            x["max_reminders"] = v
            self.st.save()
            return (f"🔔 حداکثر یادآوری: **{fa(v)} بار**"
                    + (" — فقط بررسی بی‌صدا" if v == 0 else ""))

        # ── چک دائمی: فیکس باگ لفت ۱۵ ثانیه‌ای ──
        if sub in ("permanent", "دائمی", "چک_دائمی", "watch", "نگهبانی"):
            rest_low = (rest or "").strip().lower()
            if rest_low in ("on", "روشن", "فعال"):
                x["permanent_check"] = True
                x["permanent_check_max_hours"] = 0
                x["recheck_hours"] = 0
                self.st.save()
                return ("🔄 چک دائمی **روشن** شد — بدون سقف زمانی چک می‌کنم "
                        "(فاصله با سن رکورد پلکانی بلند می‌شود)، اگر طرف لفت داد "
                        "بعد از چند نبودنِ تأییدشده از کانالش لفت می‌دهم.\n"
                        + self.permanent_check_status_text())
            if rest_low in ("off", "خاموش", "غیرفعال"):
                x["permanent_check"] = False
                self.st.save()
                return "🔄 چک دائمی **خاموش** شد — فقط تا چند ساعت اول چک می‌کنم."
            if rest_low.startswith(("max ", "سقف ", "ساعت ")):
                try:
                    v = max(0, min(720, num(rest_low.split(None,1)[1])))
                    x["permanent_check_max_hours"] = v
                    x["recheck_hours"] = v
                    self.st.save()
                    if v==0:
                        return "♾️ چک دائمی بدون محدودیت زمانی — تا ابد چک می‌کنم.\n" + self.permanent_check_status_text()
                    return f"⏱ چک دائمی تا {fa(v)} ساعت بعد جوین ادامه دارد، بعدش متوقف می‌شود.\n" + self.permanent_check_status_text()
                except Exception:
                    return "فرمت: `تبادل دائمی ساعت 0` (۰=تا ابد) یا `تبادل دائمی ساعت 24`"
            return self.permanent_check_status_text()

        if sub in ("report", "report_status"):
            mode = x.get("report_mode", "live")
            label = {"live": "لحظه‌ای در PV", "summary": "خلاصه خودکار در PV", "off": "خاموش"}.get(mode, mode)
            return (f"📊 گزارش خصوصی تبادل: **{label}**\n"
                    "مقصد: Saved Messages همین اکانت\n\n"
                    "`تبادل گزارش` — ورود به منو\n"
                    "`تنظیم گزارش روشن`\n"
                    "`تنظیم گزارش لحظه‌ای`\n"
                    "`تنظیم گزارش خلاصه`\n"
                    "`گزارش خلاصه` — ارسال همین حالا\n"
                    "`تنظیم گزارش خاموش`")

        if sub == "report_live":
            x["report_mode"] = "live"
            x["report_last_sent"] = int(time.time())
            self.st.save()
            return "📊 گزارش خصوصی روی حالت **لحظه‌ای** قرار گرفت."

        if sub == "report_summary":
            x["report_mode"] = "summary"
            x["report_last_sent"] = int(time.time())
            self.st.save()
            return ("📊 گزارش خصوصی روی حالت **خلاصه خودکار** قرار گرفت.\n"
                    f"فاصله فعلی: {secs(int(x.get('report_summary_interval_sec', 86400) or 86400))}")

        if sub == "report_off":
            x["report_mode"] = "off"
            self.st.save()
            return "🔕 گزارش خصوصی تبادل خاموش شد؛ پاسخ ثبت‌شده به طرف همچنان ارسال می‌شود."

        if sub == "report_now":
            x["_report_now"] = True
            return "📊 خلاصه گزارش در نوبت ارسال به PV قرار گرفت."

        if sub == "report_every":
            if not rest:
                return (f"فاصله خلاصه: {secs(int(x.get('report_summary_interval_sec', 86400) or 86400))}\n"
                        "`تبادل گزارش هر 24` یعنی هر ۲۴ ساعت")
            raw_hours = re.sub(r"\s*(?:ساعت|ساعته)\s*$", "", rest).strip()
            try:
                hours = max(1, min(168, num(raw_hours)))
            except ValueError:
                return "عدد بده: `تبادل گزارش هر 24`"
            x["report_summary_interval_sec"] = hours * 3600
            x["report_mode"] = "summary"
            x["report_last_sent"] = int(time.time())
            self.st.save()
            return f"📊 خلاصه گزارش هر **{fa(hours)} ساعت** ارسال می‌شود."

        if sub == "strikes":
            if not rest:
                return (f"بعد از {fa(x['max_strikes'])} بار نبودنِ تأییدشده لفت می‌دهم "
                        "(پیش‌فرض ۲ — هر بار با چک دوم تأیید می‌شود)\n"
                        "`تبادل اخطار ۲`")
            try:
                v = max(1, num(rest))
            except ValueError:
                return "عدد بده: `تبادل اخطار ۲`"
            x["max_strikes"] = v
            self.st.save()
            return f"⚠️ بعد از **{fa(v)} بار** نبودنِ تأییدشده، لفت می‌دهم."

        if sub in ("list", "l", "فهرست"):
            return self.ex_list_text()
        if sub in ("wait", "pending", "منتظر"):
            return self.ex_list_text("pending")
        if sub == "joined":
            return self.ex_list_text("joined")
        if sub == "left":
            return self.ex_list_text("left")

        if sub == "add":
            if not rest:
                return "`تبادل افزودن @channel`"
            links = extract_links(rest)
            if not links:
                return "لینک معتبری پیدا نکردم."
            rec, new = self.db.ex_add(None, "دستی", links[0])
            if not new:
                return f"قبلاً ثبت شده: `#{fa(rec['id'])}` — {rec['status']}"
            self.db.ex_set(rec["id"], note="دستی")
            return (f"✅ ثبت شد `#{fa(rec['id'])}` → `{links[0]}`\n"
                    f"با `تبادل تأیید {fa(rec['id'])}` جوین می‌شوم.")

        if sub in ("ok", "no", "out", "del"):
            if not rest:
                return f"`تبادل {sub} ۵`"
            rec = self.db.ex_find(rest)
            if not rec:
                return "پیدا نشد."
            if sub == "no":
                self.db.ex_set(rec["id"], status="rejected")
                return f"🚫 `#{fa(rec['id'])}` رد شد."
            if sub == "del":
                self.db.ex_delete(rec["id"])
                return f"🗑 `#{fa(rec['id'])}` حذف شد."
            if sub == "ok":
                # replied=0: پیام «دارم چک می‌کنم» (msg_wait) که قبل از
                # تأیید رفته، replied را ۱ کرده است؛ اگر صفر نشود، بعد از
                # جوینِ واقعی reply_joined پیام «جوین شدم» را نمی‌فرستد و
                # طرف فقط همان «در حال بررسی» را می‌بیند و دیگر هیچ.
                self.db.ex_set(rec["id"], status="approved", strikes=0,
                               replied=0)
                return f"✅ `#{fa(rec['id'])}` تأیید شد — تو نوبت جوین."
            self.db.ex_set(rec["id"], status="leaving")
            return f"👋 `#{fa(rec['id'])}` تو نوبت لفت."

        if sub == "check":
            n = 0
            for r in self.db.ex_list("joined", 200):
                self.db.ex_set(r["id"], last_check=0, next_check=0)
                n += 1
            return f"🔄 {fa(n)} تبادل برای چک فوری علامت خورد."

        # ── تطبیقیِ هوشمند: FloodWait → +۱۵ ثانیه، آپ‌تایم طولانی → ۳۰ثانیه→۶۰ثانیه ──
        if sub in ("adaptive", "تطبیقی", "هوشمند", "auto_gap", "گپ_هوشمند"):
            rest_low = (rest or "").strip().lower()
            # روشن/خاموش
            if rest_low in ("on", "روشن", "فعال"):
                x["adaptive_on"] = True
                self.st.save()
                try:
                    emin, emax = self.effective_join_gap()
                    self.join_thr.apply({"min_gap_sec": emin, "max_gap_sec": emax, "max_per_hour": 0})
                except Exception:
                    pass
                return "🧠 تطبیقیِ جوین **روشن** شد.\n" + self.adaptive_status_text()
            if rest_low in ("off", "خاموش", "غیرفعال"):
                x["adaptive_on"] = False
                self.st.save()
                # برگرد به پایه
                try:
                    base_min = int(x.get("min_join_gap_sec", 30) or 30)
                    base_max = int(x.get("max_join_gap_sec", 60) or 60)
                    self.join_thr.apply({"min_gap_sec": base_min, "max_gap_sec": base_max, "max_per_hour": 0})
                except Exception:
                    pass
                return "🧠 تطبیقیِ جوین **خاموش** شد — فقط فاصله پایه استفاده می‌شود."
            if rest_low in ("reset", "ریست", "صفر", "پاک"):
                x["_adaptive_flood_extra"] = 0
                x["_adaptive_last_flood"] = 0
                x["_adaptive_last_decay"] = 0
                self.st.save()
                try:
                    emin, emax = self.effective_join_gap()
                    self.join_thr.apply({"min_gap_sec": emin, "max_gap_sec": emax, "max_per_hour": 0})
                except Exception:
                    pass
                return "♻️ اضافه Flood صفر شد.\n" + self.adaptive_status_text()
            # تنظیمات عددی: flood_step, flood_max, decay, uptime_threshold, uptime_extra, uptime_per_hour
            # مثال: تبادل تطبیقی flood 15 / تبادل تطبیقی max 120 / تبادل تطبیقی decay 60
            #       تبادل تطبیقی uptime 3 / تبادل تطبیقی uptime_extra 30 / تبادل تطبیقی uptime_per_hour 10
            if rest_low.startswith(("flood ", "فلاد ")):
                try:
                    v = max(1, min(120, num(rest_low.split(None,1)[1])))
                    x["adaptive_flood_step_sec"] = v
                    self.st.save()
                    return f"⚙️ هر FloodWait → +{fa(v)} ثانیه\n" + self.adaptive_status_text()
                except Exception:
                    return "فرمت: `تبادل تطبیقی flood 15`"
            if rest_low.startswith(("max ", "سقف ")):
                try:
                    v = max(15, min(600, num(rest_low.split(None,1)[1])))
                    x["adaptive_flood_max_sec"] = v
                    self.st.save()
                    return f"⚙️ سقف اضافه Flood → {fa(v)} ثانیه\n" + self.adaptive_status_text()
                except Exception:
                    return "فرمت: `تبادل تطبیقی max 120`"
            if rest_low.startswith(("decay ", "کاهش ")):
                try:
                    v = max(5, min(720, num(rest_low.split(None,1)[1])))
                    x["adaptive_flood_decay_min"] = v
                    self.st.save()
                    return f"⚙️ کاهش خودکار هر {fa(v)} دقیقه\n" + self.adaptive_status_text()
                except Exception:
                    return "فرمت: `تبادل تطبیقی decay 60`"
            if rest_low.startswith(("uptime ", "آپتایم ", "ساعت ")):
                try:
                    v = max(1, min(24, num(rest_low.split(None,1)[1])))
                    x["adaptive_uptime_threshold_hours"] = v
                    self.st.save()
                    return f"⚙️ آستانه کندشدن آپ‌تایم → {fa(v)} ساعت\n" + self.adaptive_status_text()
                except Exception:
                    return "فرمت: `تبادل تطبیقی uptime 3`"
            if rest_low.startswith(("uptime_extra ", "extra ", "اضافه ")):
                try:
                    # می‌تواند دو عددی باشد: uptime_extra 30 یا extra 30
                    parts = rest_low.replace("uptime_extra","").replace("extra","").replace("اضافه","").strip()
                    v = max(0, min(300, num(parts.split()[0])))
                    x["adaptive_uptime_extra_sec"] = v
                    if len(parts.split())>1:
                        v2 = max(0, min(120, num(parts.split()[1])))
                        x["adaptive_uptime_per_hour_sec"] = v2
                    self.st.save()
                    return f"⚙️ اضافه آپ‌تایم تنظیم شد\n" + self.adaptive_status_text()
                except Exception:
                    return "فرمت: `تبادل تطبیقی extra 30 10`"
            # بدون آرگومان: نمایش وضعیت
            return self.adaptive_status_text()

        return (f"زیر‌دستور ناشناخته: `{sub}`\n`تبادل` برای وضعیت • "
                "`راهنما` برای راهنما")

    def exchange_text(self):
        """پنل اصلی تبادل — کوتاه و خلوت؛ کارهای آماده در صفحه‌ها."""
        x = self.ex_cfg()
        c = self.db.ex_counts()
        ch = self.st.prof("standard")["channel"]
        today = self.db.ex_joins_today()
        groups = x.get("groups") or []
        try:
            emin, emax = self.effective_join_gap()
            gap = f"{fad(emin)}–{fad(emax)} ثانیه"
        except Exception:
            gap = "—"
        adapt = "تطبیقی روشن" if x.get("adaptive_on", True) else "تطبیقی خاموش"
        _perm_max = int(x.get("permanent_check_max_hours", 0) or 0)
        if x.get("permanent_check", True) and _perm_max == 0:
            perm = "تا ابد"
        elif x.get("permanent_check", True):
            perm = f"تا {fad(_perm_max)} ساعت"
        else:
            perm = "خاموش"
        rep = {"live": "لحظه‌ای", "summary": "خلاصه"}.get(
            x.get("report_mode", "live"), "خاموش")
        ai_on = bool((getattr(self.ai, "cfg", {}) or {}).get("smart_detect"))
        lines = [
            "🔁 تبادل",
            "",
            "━━━━━━━━━━━━━━",
            "",
            f"وضعیت: {'🟢 روشن' if x['enabled'] else '🔴 خاموش'} · "
            f"جوین خودکار: {'روشن' if x['auto_join'] else 'تأیید دستی'}",
            "",
            f"کانال من: {ch or 'تنظیم نشده'} · گروه‌ها: {fad(len(groups))}",
            f"گروه جایگزین: {'🟢 روشن' if x.get('group_failover_on') and len(groups) >= 2 else 'خاموش (اختیاری)'}",
            "",
        ]
        if not self.ex_channel_ready():
            lines += [
                "❌ کانالِ من تنظیم نشده — تا ثبتش نکنی تبادل هیچ کاری "
                "نمی‌کند:",
                "`کانال @mychannel` · یا کلِ راه: `تبادل سریع`",
                "",
            ]
        lines += [
            f"جوین امروز: {fad(today)} · انجام‌شده: {fad(c.get('joined', 0))}"
            f" · در صف: {fad(c.get('approved', 0))}",
            "",
            f"فاصله Join: {gap} ({adapt})",
            "",
            f"نگهبانی عضویت: {perm} · گزارش: {rep}",
            "",
            "━━━ صفحه‌ها ━━━",
            "",
            "⚙️ تنظیمات — `تبادل تنظیمات`",
            "",
            "📖 راهنمای حالت‌ها — `تبادل راهنما`",
            "",
            "⌨️ همه دستورها — `تبادل دستورها`",
            "",
            "💬 متن‌های جوین — `متن‌های تبادل`",
            "",
            f"🧠 تشخیص هوشمند: {'روشن' if ai_on else 'خاموش'} — `تبادل تشخیص`",
            "",
            "↩️ بازگشت: `عادی`",
        ]
        return "\n".join(lines)

    def ex_guide_text(self):
        """راهنمای حالت‌های تبادل — هر حالت چه می‌کند و با چه دستوری عوض می‌شود."""
        lines = [
            "📖 راهنمای حالت‌های تبادل",
            "",
            "━━━━━━━━━━━━━━",
            "",
            "🔁 **روشن/خاموش** — کلید اصلی؛ وقتی خاموش است هیچ چکی و جوینی نمی‌رود.",
            "`تبادل روشن` · `تبادل خاموش`",
            "",
            "🤖 **جوین خودکار** — روشن: بعد از تأیید عضویت طرف، خودم کانالش را جوین می‌شوم.",
            "خاموش (تأیید دستی): اول به تو خبر می‌دهم و با `تبادل تأیید ۵` جوین می‌شوم.",
            "`تبادل خودکار`",
            "",
            "🚶 **پیش‌قدم** — خودم گروه‌های تبادل را اسکن می‌کنم، روی لینک‌های تازه",
            "جوین می‌شوم و متن جوین‌ات را ریپلای می‌زنم.",
            "`تبادل پیش‌قدم` · اسکن فوری: `تبادل اسکن`",
            "",
            "🛡 **نگهبانی عضویت** — بعد از جوین، عضو موندنِ طرف را چک می‌کنم؛",
            "اگر لفت داد، بعد از ۲ منفیِ تأییدشده از کانالش لفت می‌دهم.",
            "`تبادل دائمی` · سقف زمانی: `تبادل دائمی ساعت ۲۴` (۰ = تا ابد)",
            "",
            "📊 **گزارش** — لحظه‌ای: هر رویداد همان لحظه به PV می‌آید؛",
            "خلاصه: هر چند ساعت یک جمع‌بندی.",
            "`تبادل گزارش لحظه‌ای` · `تبادل گزارش خلاصه` · `تبادل گزارش خاموش`",
            "",
            "🧠 **تطبیقی** — فاصله جوین با FloodWait و آپ‌تایم طولانی خودش زیاد می‌شود",
            "تا ریسک ریپورت کم شود؛ بعد از چند ساعت بی‌فلود دوباره کم می‌کند.",
            "`تبادل تطبیقی`",
            "",
            "🔍 **تشخیص هوشمند** — پیام‌های طرف را با هوش مصنوعی تحلیل می‌کند تا",
            "«جوین شدم» واقعی را از دستوری و سوالی تشخیص بدهد.",
            "`تبادل تشخیص`",
            "",
            "↩️ بازگشت: `تبادل`",
        ]
        return "\n".join(lines)

    def ex_commands_text(self):
        """همه دستورهای تبادل در یک صفحه."""
        lines = [
            "⌨️ همه دستورهای تبادل",
            "",
            "━━━━━━━━━━━━━━",
            "",
            "**کلید**",
            "`تبادل روشن` · `تبادل خاموش` · `تبادل خودکار`",
            "",
            "**پیش‌قدم و فهرست**",
            "`تبادل پیش‌قدم` · `تبادل اسکن` · `تبادل فهرست` · `تبادل منتظر`",
            "`تبادل تأیید ۵` · `تبادل رد ۵` · `تبادل خروج ۵`",
            "`تبادل حذف ۵` · `تبادل ارسال ۵`",
            "",
            "**گروه‌ها و کلمات**",
            "`تبادل گروه‌ها @گروه` · `تبادل کلمات جوین شدم`",
            "`تبادل گروه جایگزین @backup` — ثبت و روشن‌کردن پشتیبان (اختیاری)",
            "`تبادل گروه جایگزین خاموش` · `تبادل گروه جایگزین بعد ۵` (دقیقه)",
            "`تبادل لفت خودکار` — لفت امن فقط هنگام پرشدن سقف ۵۰۰ عضویت",
            "`تبادل لفت خودکار ریست` — ادامه پس از آزادکردن جا به‌صورت دستی",
            "",
            "**فاصله‌ها و زمان‌ها**",
            "`تبادل فاصله ۹۰ ۲۴۰` — فاصله تصادفی بین جوین‌ها",
            "`تبادل بررسی ۱۵ ۳۰` — فاصله چک عضویت",
            "`تبادل هر ۳۰ ثانیه` — فاصله اسکن گروه‌ها",
            "`تبادل زمان پاسخ ۱۵` — تأخیر جواب بعد از جوین",
            "`تبادل فاصله عملکرد ۱۵ ۲۰` — فاصله بین هر عملکرد",
            "`تبادل فاصله یادآوری ۲۰ ۴۰` · `تبادل تعداد یادآوری ۲`",
            "`تبادل اخطار ۲` — بعد از چند منفی لفت بدهد",
            "",
            "**سقف‌ها**",
            "`تبادل سقف ساعتی ۶۰` · `تبادل سقف ساعتی روشن/خاموش`",
            "",
            "**نگهبانی و تطبیقی**",
            "`تبادل دائمی` · `تبادل دائمی ساعت ۲۴`",
            "`تبادل تطبیقی` · `تبادل تطبیقی روشن/خاموش` · `تبادل تطبیقی ریست`",
            "`تبادل تطبیقی flood 15` · `تبادل تطبیقی max 120` · `تبادل تطبیقی decay 60`",
            "",
            "**گزارش خصوصی**",
            "`تبادل گزارش` · `تبادل گزارش لحظه‌ای` · `تبادل گزارش خلاصه`",
            "`تبادل گزارش خاموش` · `تبادل گزارش هر ۲۴` · `تبادل گزارش الان`",
            "",
            "**متن‌های جوین**",
            "`تبادل پیام موفق …` · `تبادل پیام ناموفق …` · `تبادل پیام انتظار …`",
            "`تبادل پیام بدون لینک …` · `تبادل پیام ادعا …` · `تبادل پیام بیا …`",
            "همه با هم: `متن‌های تبادل`",
            "",
            "**هوشمند**",
            "`تبادل تشخیص` — روشن/خاموش تشخیص هوشمند پیام",
            "",
            "↩️ بازگشت: `تبادل`",
        ]
        return "\n".join(lines)

    def ex_settings_text(self):
        x = self.ex_cfg()
        groups = x.get("groups") or []
        try:
            emin, emax = self.effective_join_gap()
            eff = f"{fa(emin)}–{fa(emax)} ثانیه"
        except Exception:
            eff = "—"
        _perm_max = int(x.get('permanent_check_max_hours', 0) or 0)
        _perm_on = x.get('permanent_check', True)
        if _perm_on and _perm_max == 0:
            perm_cur = "تا ابد"
        elif _perm_on:
            perm_cur = f"تا {fa(_perm_max)} ساعت بعد از جوین"
        else:
            perm_cur = "خاموش"
        rem_n = max(0, int(x.get("max_reminders", 2) or 0))
        if rem_n:
            rem_cur = (f"{fa(rem_n)} پیام با فاصله {fa(x.get('reminder_min_sec', 20))}"
                       f" تا {fa(x.get('reminder_max_sec', 40))} ثانیه")
        else:
            rem_cur = "بدون پیام «نیومدی»"
        hour_cur = (f"روشن — {fa(x.get('hour_cap', 60))} در ساعت"
                    if x.get("hour_cap_on") else "خاموش")
        report_cur = {"live": "لحظه‌ای", "summary": "خلاصه"}.get(
            x.get("report_mode", "live"), "خاموش")
        jitter_cur = "فعال (چندگروه)" if len(groups) >= 2 else "خاموش (تک‌گروه)"
        failover_cur = ("روشن" if x.get("group_failover_on") and len(groups) >= 2
                        else "خاموش (پیش‌فرض؛ رفتار قبلی حفظ می‌شود)")
        failover_min = max(1, int(x.get("group_failover_after_sec", 300) or 300) // 60)
        capacity_leave_cur = ("روشن" if x.get("auto_leave_completed_on_limit", True)
                              else "خاموش")
        age_min = max(1, int(x.get('scan_max_age_sec', 300) or 300)) // 60
        lines = [
            "⚙️ تنظیمات تبادل",
            "━━━━━━━━━━━━━━",
            "",
            "⏱ وقتی می‌خواهی فاصله بین جوین‌ها را عوض کنی:",
            "دستور آماده برای کپی:",
            "`تبادل فاصله ۹۰ ۲۴۰`",
            f"فعلی: {fa(x['min_join_gap_sec'])} تا {fa(x['max_join_gap_sec'])} ثانیه (موثر: {eff})",
            "",
            "🔍 وقتی می‌خواهی فاصله اسکن گروه را عوض کنی:",
            "دستور آماده برای کپی:",
            "`تبادل اسکن هر ۳۰ ثانیه`",
            f"فعلی: هر {fa(x.get('scan_every_sec', 30))} ثانیه",
            "",
            "🛡 وقتی می‌خواهی فاصله چک عضویت را عوض کنی:",
            "دستور آماده برای کپی:",
            "`تبادل بررسی ۱۵ ۳۰`",
            f"فعلی: {fa(x.get('check_min_sec', 15))} تا {fa(x.get('check_max_sec', 30))} ثانیه",
            "",
            "⚠️ وقتی می‌خواهی تعداد اخطار قبل از لفت را عوض کنی:",
            "دستور آماده برای کپی:",
            "`تبادل اخطار ۲`",
            f"فعلی: {fa(x.get('max_strikes', 2))}",
            "",
            "⏳ وقتی می‌خواهی تعداد پیام «نیومدی» را عوض کنی:",
            "دستور آماده برای کپی:",
            "`تبادل تعداد یادآوری ۲`",
            f"فعلی: {rem_cur}",
            "",
            "🚦 وقتی می‌خواهی سقف ساعتی جوین بگذاری:",
            "دستور آماده برای کپی:",
            "`تبادل سقف ساعتی ۶۰`",
            f"فعلی: {hour_cur}",
            "",
            "📡 وقتی می‌خواهی نگهبانی عضویت (چک بعد از جوین) را ببینی:",
            "دستور آماده برای کپی:",
            "`تبادل دائمی`",
            f"فعلی: {perm_cur}",
            "",
            "⚙️ وقتی می‌خواهی فاصله بین عملکردها را عوض کنی:",
            "دستور آماده برای کپی:",
            "`تبادل فاصله عملکرد ۱۵ ۲۰`",
            f"فعلی: {fa(x.get('op_gap_min_sec', 15))} تا {fa(x.get('op_gap_max_sec', 20))} ثانیه",
            "",
            "💬 وقتی می‌خواهی زمان پاسخ بعد از Join را عوض کنی:",
            "دستور آماده برای کپی:",
            "`تبادل زمان پاسخ ۱۵`",
            f"فعلی: {fa(x.get('response_delay_sec', 15))} ثانیه",
            "",
            "🔗 وقتی می‌خواهی حداکثر سن لینک را عوض کنی:",
            "دستور آماده برای کپی:",
            "`تبادل سن لینک ۵`",
            f"فعلی: حداکثر {fa(age_min)} دقیقه",
            "",
            "🎯 وقتی می‌خواهی انتخاب پیام اسکن را عوض کنی:",
            "دستور آماده برای کپی:",
            "`تبادل انتخاب ۲`",
            f"فعلی: مورد {fa(x.get('scan_pick', 2) or 2)} از جدیدترین‌ها",
            "",
            "🧯 وقتی می‌خواهی ضد اسپم چندگروهی را ببینی:",
            "دستور آماده برای کپی:",
            "`تبادل اسکن تصادفی`",
            f"فعلی: {jitter_cur}",
            "",
            "🔁 گروه پشتیبان (اختیاری؛ خاموش پیش‌فرض):",
            "`تبادل گروه جایگزین @backup` برای ثبت و فعال‌سازی",
            "`تبادل گروه جایگزین روشن` / `خاموش` برای کنترل",
            f"انتقال پس از {fa(failover_min)} دقیقه بی‌لینک‌ماندن · وضعیت: {failover_cur}",
            "`تبادل گروه جایگزین بعد ۵` برای تغییر زمان به ۵ دقیقه",
            "",
            "🧹 آزادکردن ظرفیت سقف عضویت تلگرام:",
            f"وضعیت: {capacity_leave_cur} · هر دور تا {fa(clamp_capacity_batch(x.get('capacity_cleanup_batch', CAPACITY_CLEANUP_BATCH_DEFAULT)))} "
            "کانالِ جفج‌زده‌ی قدیمی لفت می‌شود (فقط تبادل کامل‌شده)",
            "`تبادل لفت خودکار روشن` / `خاموش` · `تعداد ۳۰` برای تغییر · `ریست` بعد از آزادکردن جا دستی",
            "",
            "📊 وقتی می‌خواهی گزارش خصوصی را تنظیم کنی:",
            "دستور آماده برای کپی:",
            "`تنظیم گزارش لحظه‌ای`",
            "`تنظیم گزارش خلاصه`",
            f"فعلی: {report_cur}",
            "",
            "🧠 وقتی می‌خواهی تنظیم تطبیقی (فلود و آپ‌تایم) را ببینی:",
            "دستور آماده برای کپی:",
            "`تبادل تطبیقی`",
            "",
            "↩️ بازگشت: `تبادل`",
        ]
        return "\n".join(lines)

    def ex_msgs_text(self):
        x = self.ex_cfg()
        sections = [
            ("🟢 وقتی ربات در پیش‌قدم با موفقیت Join شد چه بگوید؟",
             "تبادل پیام بیا جوین شدم", "msg_come"),
            ("✅ وقتی تبادل عادی موفق شد چه بگوید؟",
             "تبادل پیام موفق اومدم بیا", "msg_ok"),
            ("❌ وقتی من جوین شدم ولی طرف هنوز نیامده چه بگوید؟",
             "تبادل پیام ناموفق من جوین شدم، تو هنوز عضو نشدی", "msg_no"),
            ("🗣 وقتی طرف گفته جوین شدم ولی عضو نیست چه بگوید؟",
             "تبادل پیام ادعای جوین گفتی جوین شدی ولی عضو نشدی", "msg_claim_no"),
            ("⏳ وقتی بررسی هنوز تمام نشده چه بگوید؟",
             "تبادل پیام انتظار دارم بررسی می‌کنم", "msg_wait"),
            ("🔗 وقتی لینک طرف پیدا نشد چه بگوید؟",
             "تبادل پیام بدون لینک لینک کانالت را بفرست", "msg_nolink"),
        ]
        lines = [
            "💬 تنظیم متن‌های تبادل",
            "━━━━━━━━━━━━━━",
            "توضیح هر مورد بالا نوشته شده است.",
            "دستور نمونه را کپی کن و متن آخر آن را هرطور خواستی تغییر بده.",
            "بین فرمان و متن فقط فاصله لازم است؛ ویرگول لازم نیست.",
        ]
        for title, command, key in sections:
            cur = x.get(key) or ""
            if not cur and key == "msg_no":
                cur = (f"{DEFAULT_MSG_NO} (پیش‌فرض) + کانال خودت، زیر متن"
                       " — فقط برای کسی که کانالش ثبت شده است؛ "
                       "اگر متن سفارشی ثبت کنی، فقط همان متن می‌رود")
            if not cur and key == "msg_claim_no":
                cur = ("تنظیم نشده — همان «پیام ناموفق» می‌رود "
                       "(برای طرفی که ادعای جوین کرده)")
            if key == "msg_come":
                # پیامِ پیش‌قدم: کانالِ خودم خودکار زیر متن می‌آید (اگر
                # خودت داخل متن نگذاشته باشی) تا طرف بداند کجا جوین شود.
                cur = (cur or "تنظیم نشده — چیزی نمی‌فرستم") + \
                      "  ←  کانال خودت خودکار زیر متن می‌آید"
            lines += ["", title, "دستور آماده برای کپی:", f"`{command}`",
                      f"متن فعلی: {cur or 'تنظیم نشده'}"]
        lines += ["", "فرمان عمومی «تبادل پیام» متن موفقیت هر دو نوع Join را تنظیم می‌کند.",
                  "خاموش‌کردن متن عمومی: `تبادل پیام خاموش`",
                  "متغیرها: `{name}` نام طرف  ·  `{mychannel}` کانال من. "
                  "لینک طرف در متن درج نمی‌شود؛ `{channel}` پشتیبانی نمی‌شود.",
                  f"پاسخ‌دادن: {'روشن' if x['reply'] else 'خاموش'}  ·  تغییر: `تبادل جواب`"]
        return "\n".join(lines)

    def _day_start(self):
        return int(time.mktime(datetime.now().replace(
            hour=0, minute=0, second=0, microsecond=0).timetuple()))

    def ex_report_text(self, since=None):
        """متن گزارش جمعی؛ مقصد نهایی در لایه تلگرام PV/Saved Messages است."""
        since = self._day_start() if since is None else int(since)
        c = self.db.ex_report_counts(since)
        interval_label = "امروز" if since == self._day_start() else "از گزارش قبلی"
        return "\n".join([
            "📊 گزارش کامل تبادل جفج",
            "━━━━━━━━━━━━━━━━",
            f"🕒 بازه گزارش: {interval_label}",
            "",
            f"✅ کانال‌های Join‌شده: {fa(c['joined'])}",
            f"🚶 پیش‌قدم موفق: {fa(c['out_joined'])}",
            f"👥 جذب موفق تبادل: {fa(c['in_joined'])} نفر",
            f"👋 کانال‌های لفت‌داده‌شده: {fa(c['left'])}",
            f"⏳ برگشت‌نداده‌های فعلی: {fa(c['not_returned'])}",
            f"⏳ در صف Join: {fa(c['approved'])}",
            f"⌛ منتظر بررسی: {fa(c['pending'])}",
            f"❌ Join ناموفق: {fa(c['failed'])}",
            "",
            f"📈 نتیجه: {fa(c['in_joined'])} تبادل موفق برای جذب",
            "━━━━━━━━━━━━━━━━",
            "📍 مقصد: PV / Saved Messages",
        ])

    def ex_live_join_text(self, rec, title="", reply_sent=False):
        c = self.db.ex_report_counts(self._day_start())
        direction = "پیش‌قدم انجام شد" if rec.get("direction") == "out" else "تبادل عادی انجام شد"
        icon = "🚶" if rec.get("direction") == "out" else "🤝"
        return "\n".join([
            f"{icon} {direction}",
            "",
            f"📡 کانال: {rec.get('link') or '—'}",
            "✅ وضعیت: Join شد",
            *( [f"🏷 عنوان: {title}"] if title else [] ),
            *( ["💬 متن تبادل ارسال شد"] if reply_sent else [] ),
            "",
            "📊 آمار امروز:",
            f"✅ Join شده: {fa(c['joined'])} کانال",
            f"👋 لفت داده‌شده: {fa(c['left'])} کانال",
            f"👥 جذب موفق تبادل: {fa(c['in_joined'])} نفر",
        ])

    def ex_live_peer_join_text(self, rec):
        """گزارشِ «طرف هم برگشت و جوینِ کانال من شد» — تکمیلِ پیش‌قدم.

        در حالت پیش‌قدم، گزارشِ لحظه‌ایِ جوین فقط می‌گوید «من رفتم»؛
        لحظه‌ی تکمیلِ تبادل وقتی است که طرف هم عضو کانال من شود. قبلاً
        این لحظه هیچ پیامی نداشت و ستونِ «جذب موفق» هم هیچ‌وقت بالا
        نمی‌رفت — کاربر فکر می‌کرد تبادل انجام شده ولی هیچ‌جا نمی‌دید.
        """
        c = self.db.ex_report_counts(self._day_start())
        return "\n".join([
            "🤝 تبادل کامل شد",
            "",
            f"📡 کانال: {rec.get('link') or '—'}",
            "✅ طرف هم عضوِ کانال من شد",
            "",
            "📊 آمار امروز:",
            f"✅ Join شده: {fa(c['joined'])} کانال",
            f"👋 لفت داده‌شده: {fa(c['left'])} کانال",
            f"👥 جذب موفق تبادل: {fa(c['in_joined'])} نفر",
        ])

    def ex_live_leave_text(self, rec, err="", reason="left"):
        """گزارش لفت.

        reason:
          «left»   → چکِ نگهبانی دید طرف از کانال من خارج شده → من هم لفت دادم
          «nojoin» → طرف بعد از دو «نیومدی» عضو کانال من نشد → من از کانالش لفت دادم
          «manual» → خودت دستور `تبادل خروج N` را داده بودی

        متنِ قبلی همیشه می‌گفت «طرف از کانال من خارج شده بود»، حتی وقتی
        دلیلِ لفت این نبود (مثلاً طرف اصلاً نیامده بود) — همین باعث
        سوتفاهم می‌شد.
        """
        why = ("🖐 لفت دستی — خودت دستور دادی"
               if reason == "manual" else
               "⏳ طرف بعد از پیام‌های «نیومدی» عضو کانال من نشد"
               if reason == "nojoin" else
               "✅ طرف از کانال من خارج شده بود")
        out = ["👋 لفت انجام شد" if not err else "⚠️ لفت انجام نشد",
               "",
               f"📡 کانال: {rec.get('link') or '—'}",
               why,
               "✅ من هم از کانالش خارج شدم" if not err else f"⚠️ {err}"]
        if err:
            fails = int(rec.get("leave_fail") or 0)
            if fails:
                out.append(f"🔁 تلاش ناموفق: {fa(fails)} — تلاش بعدی با فاصله‌ی "
                           "بیشتر انجام می‌شود تا روی اکانت فشار نیفتد.")
        return "\n".join(out)

    def ex_my_channel(self):
        """کانال خودم (standard اولویت، بعد vip) — خالی = تنظیم نشده."""
        return (self.st.prof("standard")["channel"] or
                self.st.prof("vip")["channel"] or "").strip()

    def ex_append_my_channel(self, body):
        """کانال خودم را «زیر متن» می‌آورد — اگر از قبل داخل متن نباشد.

        قاعده‌ی کلیِ محصول: هیچ‌وقت لینکِ *طرف* اتوماتیک زیر پیام نمی‌رود؛
        ولی کانالِ *خودم* باید زیر متن باشد تا طرف بداند کدام کانال را
        جوین شود. مقایسه‌ی تکراری‌بودن نرمال است: `@chan` و
        `https://t.me/chan` یکی حساب می‌شوند، پس «دو بار» نمی‌آید.
        """
        txt = (body or "").strip()
        mych = self.ex_my_channel()
        if not txt or not mych:
            return txt

        def _norm(s):
            s = str(s or "").strip().lower().rstrip("/")
            s = re.sub(r"^https?://", "", s)
            s = re.sub(r"^(t\.me|telegram\.me)/", "", s)
            return s.lstrip("@")

        if _norm(mych) and _norm(mych) in _norm(txt):
            return txt
        return f"{txt}\n{mych}"

    def ex_render(self, key, name="", channel=""):
        """متن کاربر را با مقادیر واقعی پر می‌کند. خالی = جوابی نده.
        تنها استثنا msg_no است: اگر متنی ثبت نشده باشد، پیش‌فرض
        «نیومدی» + کانال خودم (standard/vip) فرستاده می‌شود.
        وقتی متن سفارشی msg_no ثبت شده باشد، فقط همان متن می‌رود و
        هیچ لینکی زیرش اضافه نمی‌شود — لینک طرف هرگز اتوماتیک نمی‌آید.

        دو لایه محافظت برای لینکِ طرف اینجاست: (۱) توکنِ قدیمیِ
        `{channel}` با هر فاصله/حرف‌بندی‌ای خالی می‌شود؛ (۲) اگر لینکِ
        همین طرف به‌صورت خام هم داخل متن ذخیره شده باشد،
        `strip_peer_links` حذفش می‌کند. لینکِ کانالِ خودم
        (`{mychannel}`) چون با لینک طرف برابر نیست دست‌نخورده می‌ماند.

        «پیام پیش‌قدم» (msg_come و مسیرهای جایگزینش) جداست: کانالِ خودم
        همیشه زیرش می‌آید و این کار در `reply_joined` انجام می‌شود (نه
        اینجا) تا هر سه مسیرِ متن را پوشش بدهد."""
        cfg = self.ex_cfg()
        raw = (cfg.get(key) or "").strip()
        custom = bool(raw)
        t = raw
        if not t and key == "msg_claim_no":
            t = (cfg.get("msg_no") or "").strip() or DEFAULT_MSG_NO
            custom = bool((cfg.get("msg_no") or "").strip())
        if not t and key == "msg_no":
            t = DEFAULT_MSG_NO
        if not t:
            return ""
        # کانال خودم: standard اولویت، بعد vip
        mych = self.ex_my_channel()
        try:
            rendered = (t.replace("{name}", name or "")
                         # لینکِ طرف نباید داخل متن پیام‌های جفج منتشر شود.
                         # توکن قدیمی را — با هر فاصله/حرف‌بندی‌ای — خالی
                         # می‌کنیم تا از تنظیمات ذخیره‌شده هم هیچ invite
                         # linkای بیرون نزند (باگ قدیمیِ «لینک یارو زیر پیام»).
                         .replace("{mychannel}", mych or ""))
            rendered = re.sub(r"\{\s*channel\s*\}", "", rendered,
                              flags=re.IGNORECASE)
            # دفاعِ لایه‌دوم: اگر لینکِ همین طرف به‌صورت خام هم داخل متن
            # مانده باشد (املای @name / t.me / +HASH)، حذفش کن. لینکِ
            # کانالِ خودم دست‌نخورده می‌ماند چون با لینک طرف برابر نیست.
            rendered = strip_peer_links(rendered, channel)
            rendered = re.sub(r"[ \t]{2,}", " ", rendered)
            rendered = re.sub(r"[ \t]+([،؛,:.!؟])", r"\1", rendered)
            # اگر حذف لینک یک خط را خالی کرد، خطوط خالی پشت‌سرهم جمع شوند؛
            # خطوط تک‌خطی و قالب‌بندی عمدی کاربر دست نمی‌خورد.
            rendered = re.sub(r"[ \t]*\n[ \t]*(?=\n)", "", rendered)
            rendered = re.sub(r"\n{2,}", "\n", rendered)
        except Exception:
            # هیچ خطای قالب‌بندی‌ای نباید متن خام (که ممکن است لینک طرف
            # داشته باشد) را مستقیم بیرون بدهد؛ حداقل strip را مستقل تکرار کن.
            try:
                rendered = strip_peer_links(t, channel)
            except Exception:
                rendered = t.replace("{mychannel}", mych or "")
                rendered = re.sub(r"\{\s*channel\s*\}", "", rendered,
                                  flags=re.IGNORECASE)
        rendered = rendered.strip()
        # اگر msg_no سفارشی نیست (یعنی پیش‌فرض)، کانال خودم را زیرش بیاور
        # نه کانال طرف. اگر سفارشی است، هیچ لینکی اتوماتیک اضافه نکن.
        if key in ("msg_no", "msg_claim_no") and not custom:
            rendered = self.ex_append_my_channel(rendered)
        return rendered

    def ex_list_text(self, status=None):
        rows = self.db.ex_list(status, 25)
        if not rows:
            return "چیزی در این لیست نیست."
        ic = {"pending": "⏳", "approved": "✅", "joined": "🤝", "left": "👋",
              "rejected": "🚫", "failed": "❌", "leaving": "🚪"}
        title = {"pending": "منتظر", "joined": "جوین‌شده",
                 "left": "لفت‌داده"}.get(status, "همه تبادل‌ها")
        o = [f"🔁 **{title}** ({fa(len(rows))})", ""]
        for r in rows:
            who = r["peer_name"] or (f"آیدی {fa(r['peer_id'])}" if r["peer_id"] else "—")
            d = "🚶" if r.get("direction") == "out" else "↩️"
            line = f"{ic.get(r['status'], '•')}{d} `#{fa(r['id'])}` `{r['link']}`"
            if r["strikes"]:
                line += f" ⚠️{fa(r['strikes'])}"
            if r.get("reminders"):
                line += f" 🔔{fa(r['reminders'])}/{fa(max(0, int(self.ex_cfg().get('max_reminders', 2) or 0)))}"
            o.append(line)
            o.append(f"     {who}" + (f" — {r['note']}" if r["note"] else ""))
        o += ["", "`تبادل تأیید ۵` تأیید • `تبادل خروج ۵` لفت • "
                  "`تبادل حذف ۵` حذف • `تبادل ارسال ۵` ارسال پیام"]
        return "\n".join(o)

    # ---------- هوش مصنوعی ----------
    def ai_settings_cmd(self, arg):
        """زیر‌دستورهای غیرشبکه‌ای. سوال‌ها در لایه async جواب داده می‌شوند."""
        a = self.ai
        parts = arg.split(None, 1)
        sub = parts[0].lower() if parts else ""
        rest = parts[1].strip() if len(parts) > 1 else ""
        sub = {
            "روشن": "on", "خاموش": "off", "کلید": "key", "آدرس": "url",
            "نشانی": "url", "مدل": "model", "تشخیص": "detect",
            "پاسخ": "pv", "لحن": "persona", "وضعیت": "status",
        }.get(sub, sub)

        if sub in ("on", "روشن"):
            a.cfg["enabled"] = True
            a.save()
            return "🧠 هوش مصنوعی **روشن** شد." + ("" if a.cfg["key"]
                    else "\n⚠️ کلید ندارد: `هوش کلید کلید`")
        if sub in ("off", "خاموش"):
            a.cfg["enabled"] = False
            a.save()
            return "🧠 هوش مصنوعی **خاموش** شد."
        if sub == "key":
            if not rest:
                k = a.cfg["key"]
                shown = (k[:6] + "…" + k[-4:]) if len(k) > 12 else ("—" if not k else "***")
                return (f"کلید فعلی: `{shown}`\n`هوش کلید sk-...`\n"
                        f"در فایل `{AI_FILE}` ذخیره می‌شود.")
            a.cfg["key"] = rest.split()[0]
            a.save()
            return (f"✅ کلید ذخیره شد در `{AI_FILE}`\n"
                    "با `هوش تست` امتحانش کن.")
        if sub in ("url", "base"):
            if not rest:
                return f"آدرس فعلی: `{a.cfg['base_url']}`\n`هوش آدرس https://…/v1`"
            a.cfg["base_url"] = rest.split()[0].rstrip("/")
            a.save()
            return f"✅ آدرس: `{a.cfg['base_url']}`"
        if sub == "model":
            if not rest:
                return f"مدل فعلی: `{a.cfg['model']}`\n`هوش مدل gpt-4o-mini`"
            a.cfg["model"] = rest.split()[0]
            a.save()
            return f"✅ مدل: `{a.cfg['model']}`"
        if sub in ("detect", "تشخیص"):
            a.cfg["smart_detect"] = not a.cfg["smart_detect"]
            a.save()
            return ("🔍 تشخیص هوشمند پیام و لینک: **" +
                    ("روشن" if a.cfg["smart_detect"] else "خاموش") + "**")
        if sub == "pv":
            a.cfg["pv_answer"] = not a.cfg["pv_answer"]
            a.save()
            return ("💬 جواب دادن به سوال‌های PV: **" +
                    ("روشن" if a.cfg["pv_answer"] else "خاموش") + "**")
        if sub in ("persona", "لحن"):
            if not rest:
                return (f"لحن فعلی: {a.cfg['persona'] or '—'}\n"
                        "`هوش لحن خودمونی و کوتاه`")
            a.cfg["persona"] = "" if rest.lower() in ("off", "-") else rest
            a.save()
            return f"✅ لحن: {a.cfg['persona'] or 'پیش‌فرض'}"
        if sub in ("", "status", "وضعیت"):
            return self.ai_status_text()
        return None   # یعنی این یک سوال است، نه تنظیم

    def ai_status_text(self):
        a = self.ai
        k = a.cfg["key"]
        shown = (k[:6] + "…" + k[-4:]) if len(k) > 12 else ("— ندارد" if not k else "***")
        return "\n".join([
            "🧠 **هوش مصنوعی**", "",
            f"وضعیت: {'🟢 روشن' if a.cfg['enabled'] else '🔴 خاموش'}   `هوش روشن/خاموش`",
            f"کلید: `{shown}`   `هوش کلید`",
            f"آدرس: `{a.cfg['base_url']}`   `هوش آدرس`",
            f"مدل: `{a.cfg['model']}`   `هوش مدل`",
            f"تشخیص هوشمند: {'روشن' if a.cfg['smart_detect'] else 'خاموش'}"
            "   `هوش تشخیص`",
            f"جواب به پیام خصوصی: {'روشن' if a.cfg['pv_answer'] else 'خاموش'}   `هوش پاسخ`",
            f"لحن: {a.cfg['persona'] or 'پیش‌فرض'}   `هوش لحن`",
            "",
            f"آخرین خطا: {a.last_error or '—'}",
            "",
            "سوال بپرس: `هوش چطور تبادل رو روشن کنم؟`",
            "تست اتصال: `هوش تست`",
        ])

    def ai_context(self):
        """بافتی که به AI داده می‌شود تا درباره ربات درست جواب بدهد."""
        x = self.ex_cfg()
        st, vp = self.st.prof("standard"), self.st.prof("vip")
        lines = [
            "== معرفی ==",
            "جفج یک سلف‌بات تلگرام است که با شماره وارد اکانت کاربر می‌شود و",
            "از داخل Saved Messages کنترل می‌شود. دستورها با . یا / شروع می‌شوند.",
            "",
            "== کارهایی که می‌کند ==",
            "۱) ارسال زمان‌بندی‌شده پست به کانال‌ها با صف، چرخه فعالیت/استراحت،",
            "   سقف ساعتی و فاصله بین ارسال‌ها. دو پروفایل مستقل: عادی و VIP.",
            "۲) تبادل دوطرفه: اگر کسی روی پیام کاربر ریپلای بزند و بگوید جوین شدم،",
            "   چک می‌کند واقعا عضو کانال شده یا نه؛ اگر شده بود کانالش را جوین",
            "   می‌شود و متن تعیین‌شده را ریپلای می‌کند؛ اگر نشده بود فقط متن",
            "   مربوطه را جواب می‌دهد و جوین نمی‌شود.",
            "۳) حالت پیش‌قدم: خودش گروه‌های تبادل را اسکن می‌کند، کانال‌های تازه را",
            "   جوین می‌شود و متن تعیین‌شده را ریپلای می‌زند.",
            "۴) رصد جبران: اگر طرف بعدا لفت بدهد، بعد از چند بار چک، از کانالش لفت می‌دهد.",
            "",
            "== دستورهای اصلی ==",
            ".panel داشبورد | .set تنظیمات | .help راهنما | .stats آمار | .log رویدادها",
            ".post متن (صف عادی) | .vip متن (صف VIP) | .now متن (ارسال فوری)",
            ".setch @ch کانال عادی | .setvip @ch کانال VIP | .chans نمایش",
            ".active دقیقه | .rest دقیقه | .limit تعداد در ساعت | .gap ثانیه ثانیه",
            ".quiet ساعت‌ها | .mode تعویض ۲۴ساعته و چرخه‌ای | همین‌ها با v برای VIP",
            ".pause .resume .reset .queue .del شماره .clear .retry",
            ".ex on/off روشن‌کردن تبادل | .ex go حالت پیش‌قدم | .ex scan اسکن فوری",
            ".ex list .ex wait .ex ok شماره .ex no شماره .ex out شماره .ex del شماره",
            ".ex groups @g | .ex words کلمات | .ex gap ثانیه | Join روزانه بدون سقف",
            ".ex بررسی ۱۵ ۳۰ (فاصله تصادفی چک عضویت) | .ex strikes تعداد | .ex تعداد یادآوری ۱",
            ".ex scanevery 30 ثانیه | .ex scanlimit تعداد | اسکن فوری: .ex scan",
            ".ex msgfirst / .ex msgok / .ex msgno / .ex msgwait / .ex msgnolink",
            ".ai on/off .ai key .ai url .ai model .ai detect .ai pv .ai persona .ai test",
            "",
            "== وضعیت فعلی کاربر ==",
            f"کانال عادی: {st['channel'] or 'تعیین نشده'} | کانال VIP: {vp['channel'] or 'تعیین نشده'}",
            f"عادی: {'۲۴ساعته' if st['mode'] == 'always' else str(st['active_minutes']) + 'د فعال/' + str(st['rest_minutes']) + 'د استراحت'}"
            f" | سقف {st['max_per_hour'] or 'نامحدود'} در ساعت | فاصله {st['min_gap_sec']}-{st['max_gap_sec']} ثانیه",
            f"VIP: {'۲۴ساعته' if vp['mode'] == 'always' else str(vp['active_minutes']) + 'د فعال/' + str(vp['rest_minutes']) + 'د استراحت'}"
            f" | سقف {vp['max_per_hour'] or 'نامحدود'} در ساعت",
            f"ارسال متوقف است؟ {'بله' if self.st['paused'] else 'خیر'}",
            f"در صف: {self.db.pending_count()} | ارسال‌شده: {self.db.counts().get('sent', 0)}",
            f"تبادل: {'روشن' if x['enabled'] else 'خاموش'} | پیش‌قدم: {'روشن' if x['initiate'] else 'خاموش'}"
            f" | جوین خودکار: {'بله' if x['auto_join'] else 'خیر'}",
            f"گروه‌های تبادل: {'، '.join(x['groups']) if x['groups'] else 'تعیین نشده'}",
            f"Join روزانه: بدون سقف | امروز: {self.db.ex_joins_today()}",
            f"تبادل‌ها: {self.db.ex_counts()}",
        ]
        return "\n".join(lines)

    # ---------- متن‌ها ----------
    def brief(self, tier):
        p = self.st.prof(tier)
        m = ("۲۴ ساعته" if p["mode"] == "always"
             else f"{dur(p['active_minutes'])} فعال / {dur(p['rest_minutes'])} استراحت")
        cap = "نامحدود" if not p["max_per_hour"] else f"{fa(p['max_per_hour'])}/ساعت"
        return f"__{m} • سقف {cap} • فاصله {fa(p['min_gap_sec'])}–{fa(p['max_gap_sec'])} ثانیه__"

    def _tier(self):
        t = self.st.data.get("_menu") or "standard"
        return "vip" if t == "vip" else "standard"

    SEP = "━━━━━━━━━━━━━━━━━━━━"

    def _item(self, label, cmd):
        return f"{label}\n\n`{cmd}`"

    def _back_cmd(self):
        return "ویژه" if self._tier() == "vip" else "عادی"

    def _page(self, title, intro, items):
        """صفحه‌های منو را خوانا و بدون فاصله‌های خالی اضافی می‌سازد."""
        o = [title, self.SEP]
        if intro:
            o += ["", intro]
        for label, cmd in items:
            o += ["", label, f"`{cmd}`"]
        return "\n".join(o).rstrip() + "\n"

    def submenu_channel(self):
        tier = self._tier()
        cur = (self.st.prof(tier)["channel"] or "").strip()
        nm = "ویژه" if tier == "vip" else "عادی"
        st = "🟢  متصل" if cur else "⚪️  تنظیم نشده"
        return self._page(
            f"📡  کانال {nm}",
            f"{st}\n📌  فعلی:  {cur or '—'}",
            [
                ("➕  افزودن", "افزودن کانال"),
                ("✏️  تغییر", "تغییر کانال"),
                ("🗑  حذف", "حذف کانال"),
                ("📋  لیست", "کانال‌ها"),
                ("↩️  بازگشت", self._back_cmd()),
            ],
        )

    def submenu_add_channel(self):
        tier = self._tier()
        cmd = "کانال ویژه @آیدی" if tier == "vip" else "کانال @آیدی"
        cur = (self.st.prof(tier)["channel"] or "").strip() or "—"
        return self._page(
            "✏️  افزودن / تغییر کانال",
            f"الان:  {cur}",
            [
                ("✅  ثبت", cmd),
                ("↩️  بازگشت", "کانال"),
            ],
        )

    def submenu_del_channel(self):
        tier = self._tier()
        cur = self.st.prof(tier)["channel"] or "ندارد"
        return self._page(
            "🗑  حذف کانال",
            f"الان:  {cur}",
            [
                ("🗑  پاک کردن", "پاک کردن کانال"),
                ("↩️  بازگشت", "کانال"),
            ],
        )

    def cmd_del_channel(self):
        tier = self._tier()
        self.st.prof(tier)["channel"] = ""
        self.st.save()
        return self._page(
            "✅  پاک شد",
            "این بخش کانال ندارد.",
            [("↩️  بازگشت", "کانال‌ها")],
        )

    def submenu_list_channel(self):
        s = self.st.prof("standard")["channel"] or "تنظیم نشده"
        v = self.st.prof("vip")["channel"] or "تنظیم نشده"
        return self._page(
            "📋  لیست کانال",
            f"🔹  عادی:  {s}\n👑  ویژه:  {v}",
            [("↩️  بازگشت", "کانال")],
        )

    def submenu_post(self):
        tier = self._tier()
        if tier == "vip":
            return self._page(
                "✍️  متن ویژه",
                "متن را بعد از فرمان بنویس.",
                [
                    ("📝  نمونه", "ویژه سلام دوستان"),
                    ("↩️  بازگشت", "ویژه"),
                ],
            )
        return self._page(
            "✍️  متن عادی",
            "متن را بعد از فرمان بنویس.",
            [
                ("📝  نمونه", "ارسال سلام دوستان"),
                ("↩️  بازگشت", "عادی"),
            ],
        )

    def submenu_groups(self):
        ex = self.ex_cfg()
        g = ex.get("groups") or []
        lst = "، ".join(g) if g else "هیچ — فقط پیام خصوصی"
        failover = bool(ex.get("group_failover_on") and len(g) >= 2)
        after = max(1, int(ex.get("group_failover_after_sec", 300) or 300) // 60)
        status = "روشن" if failover else "خاموش (رفتار فعلی حفظ می‌شود)"
        return self._page(
            "👥  گروه‌های تبادل",
            f"تعداد:  {fa(len(g))}\nفعلی:  {lst}\n"
            f"ترتیب: گروه اول اصلی، گروه دوم پشتیبان\n"
            f"جایگزینی: {status} · پس از {fa(after)} دقیقه بی‌لینک‌ماندن",
            [
                ("➕  افزودن گروه", "گروه @گروه1 @گروه2"),
                ("🔁  تنظیم پشتیبان", "تبادل گروه جایگزین @backup"),
                (("🔄  خاموش‌کردن جایگزینی" if failover else "🔄  روشن‌کردن جایگزینی"),
                 ("تبادل گروه جایگزین خاموش" if failover else "تبادل گروه جایگزین روشن")),
                ("⏱  زمان انتقال: ۵ دقیقه", "تبادل گروه جایگزین بعد ۵"),
                ("🗑  حذف یک گروه", "حذف گروه @گروه1"),
                ("🧹  پاک کردن همه", "حذف همه گروه‌ها"),
                ("🔄  بروزرسانی", "گروه"),
                ("↩️  بازگشت", self._back_cmd()),
            ],
        )

    def submenu_add_group(self):
        return self._page(
            "➕  افزودن گروه تبادل",
            "یوزرنیم یک یا چند گروه را با فاصله بفرست.",
            [
                ("📝  نمونه", "گروه @exchange_group"),
                ("📝  چند گروه", "گروه @group1 @group2"),
                ("↩️  بازگشت", "گروه"),
            ],
        )

    def cmd_clear_groups(self):
        self.ex_cfg()["groups"] = []
        self.ex_cfg()["group_failover_on"] = False
        self.ex_cfg()["_group_failover_active_index"] = 0
        self.ex_cfg()["_group_failover_last_activity"] = int(time.time())
        self.st.save()
        return self.submenu_groups()

    def submenu_limit(self):
        tier = self._tier()
        p = self.st.prof(tier)
        cap = "آزاد" if not p["max_per_hour"] else f"{fa(p['max_per_hour'])} در ساعت"
        sample = "سقف‌ویژه 30" if tier == "vip" else "سقف 12"
        return self._page(
            "🚦  سقف",
            f"الان:  {cap}",
            [
                ("✏️  نمونه", sample),
                ("↩️  بازگشت", self._back_cmd()),
            ],
        )

    def submenu_cycle(self):
        if self._tier() != "vip":
            return self._page("🔄  چرخه", "فقط در بخش ویژه.", [("👑  ویژه", "ویژه")])
        p = self.st.prof("vip")
        return self._page(
            "🔄  چرخه",
            f"کار:  {fa(p['active_minutes'])} دقیقه\nاستراحت:  {fa(p['rest_minutes'])} دقیقه",
            [
                ("▶️  کار", "فعالیت‌ویژه 60"),
                ("😴  استراحت", "استراحت‌ویژه 30"),
                ("↩️  بازگشت", "ویژه"),
            ],
        )

    def submenu_gap(self):
        if self._tier() != "vip":
            return self._page("⏱  نوسان", "فقط در بخش ویژه.", [("👑  ویژه", "ویژه")])
        p = self.st.prof("vip")
        return self._page(
            "⏱  نوسان",
            f"{fa(p['min_gap_sec'])} تا {fa(p['max_gap_sec'])} ثانیه",
            [
                ("🎲  نمونه ارسال", "نوسان‌ویژه ۲۰ ۴۵"),
                ("🔔  نوسان یادآوری تبادل", "تبادل فاصله یادآوری 20 40"),
                ("↩️  بازگشت", "ویژه"),
            ],
        )

    def submenu_ex_msgs(self):
        x = self.ex_cfg()
        def cur(k):
            v = (x.get(k) or "").strip()
            return v[:50] if v else "تنظیم نشده"
        return self._page(
            "💬  متن تبادل",
            f"💬 بعد از هر Join: {cur('msg_come')}\n✅  موفقیت تبادل: {cur('msg_ok')}\n❌  {cur('msg_no')}\n⏳  {cur('msg_wait')}\n🔗  {cur('msg_nolink')}",
            [
                ("🚶  پیام بعد از آخرین پیام", "تبادل پیام بیا"),
                ("⏱  زمان پیام «بیا»", "تبادل زمان بیا ۰"),
                ("✅  موفق", "تبادل پیام موفق جوین شدم"),
                ("❌  ناموفق", "تبادل پیام ناموفق اول عضو شو"),
                ("🗣  ادعای جوین", "تبادل پیام ادعای جوین گفتی جوین شدی ولی عضو نشدی"),
                ("⏳  انتظار", "تبادل پیام انتظار دارم چک می‌کنم"),
                ("🔗  بدون لینک", "تبادل پیام بدون لینک لینک بده"),
                ("↩️  بازگشت", "تبادل"),
            ],
        )

    def profile_status(self, tier, detailed=True):
        """وضعیت واقعی همان بخش؛ «فعال» چرخه بدون کانال نشان داده نشود."""
        if not (self.st.prof(tier)["channel"] or "").strip():
            return "⚪ خاموش — کانال تنظیم نشده"
        if self.st["paused"]:
            return "⏸ متوقف"
        return self.cyc[tier].label() if detailed else "🟢 فعال"

    def section_text(self, tier):
        vip = tier == "vip"
        p = self.st.prof(tier)
        ch = (p["channel"] or "").strip()
        qn = self.db.pending_count(tier)
        x = self.ex_cfg()
        title = "👑 جفج  |  بخش VIP" if vip else "🔹 جفج  |  بخش عادی"
        channel_label = "کانال VIP" if vip else "کانال"
        items = [
            ("📡 کانال VIP" if vip else "📡 کانال",
             "کانال ویژه" if vip else "کانال"),
            ("✍️ متن ارسال", "متن"),
            ("👥 گروه‌های تبادل", "گروه"),
            ("🚦 سقف ارسال", "سقف ویژه" if vip else "سقف"),
        ]
        if vip:
            items += [("🔄 چرخه فعالیت", "چرخه"),
                      ("🎲 نوسان ارسال", "نوسان")]
        items += [("🔁 تنظیم تبادل", "تبادل"),
                  ("📮 صف پیام‌ها", "صف")]

        lines = [
            title,
            self.SEP,
            "",
            f"📡 {channel_label}: {ch or 'تنظیم نشده'}",
            f"📮 صف ارسال: {'خالی' if not qn else fa(qn)}",
            f"🔁 تبادل: {'روشن' if x['enabled'] else 'خاموش'}",
            f"📤 وضعیت ارسال: {self.profile_status(tier, detailed=False)}",
            "",
            "━━━━━━━━ مدیریت ━━━━━━━━",
        ]
        for label, cmd in items:
            # هر فرمان یک جفت backtick متوازن دارد؛ _to_html آن را به code تبدیل می‌کند.
            lines.append(f"{label} — `{cmd}`")
        lines += [
            "",
            "━━━━━━━━ ابزارها ━━━━━━━━",
            "🧠 بررسی هوشمند — `بررسی فعال`",
            "🔕 خاموش‌کردن بررسی — `بررسی خاموش`",
            "⏸ توقف ارسال — `توقف`",
            "▶️ ادامه ارسال — `ادامه`",
            "",
            "━━━━━━━━━━━━━━━━",
            "🏠 بازگشت به پنل اصلی — `پنل`",
        ]
        return "\n".join(lines) + "\n"

    def panel(self):
        try:
            self.lim.load()
        except Exception:
            pass

        name = (self.me or "—").split("(")[0].strip() or "—"
        standard = self.st.prof("standard")
        vip = self.st.prof("vip")
        counts = self.db.counts()
        ex_counts = self.db.ex_counts()
        exchange = self.ex_cfg()
        points = int(self.lim["points"] or 0)
        hours = int(self.lim["hours_left"] or 0)
        plan = (self.lim["plan"] or "").strip()
        points_mode = bool(self.lim["points_mode"] or points or plan == "امتیازی")

        lines = [
            "💎 جفج 3.0",
            "━━━━━━━━━━━━━━",
            "",
            f"👤 حساب: {name}",
        ]
        if self.my_username:
            lines.append(f"🔗 یوزرنیم: @{self.my_username.lstrip('@')}")
        lines += [
            f"🆔 آیدی: {fa(self.my_id) if self.my_id else '—'}",
            "",
            "━━━━━━━━━━━━━━",
        ]

        if points_mode:
            lines += [
                f"⭐ امتیاز: {fa(points)}",
                f"⏳ زمان تقریبی: {('تمام شده' if hours <= 0 and points <= 0 else fa(hours or points) + ' ساعت')}",
            ]
        elif plan:
            lines.append(f"💎 پلن: {plan}")
        else:
            lines.append("💎 پلن: ثبت نشده")

        if self.st["paused"]:
            state_icon, state_text = "⏸", "متوقف"
        elif points_mode and points <= 0:
            state_icon, state_text = "🔴", "امتیاز تمام شده"
        elif not plan and not points_mode:
            state_icon, state_text = "⚪", "اعتبار ثبت نشده"
        else:
            state_icon, state_text = "🟢", "در حال کار"

        lines += [
            f"{state_icon} وضعیت: {state_text}",
            f"📡 کانال عادی: {standard['channel'] or 'تنظیم نشده'}",
            f"👑 کانال ویژه: {vip['channel'] or 'تنظیم نشده'}",
            "",
            "━━━━━━━━━━━━━━",
            f"📮 صف: {fa(self.db.pending_count())} پیام"
            + (f"  ·  بی‌کانال: {fa(self.db.held_count())}" if self.db.held_count() else ""),
            f"📤 ارسال امروز: {fa(self.db.sent_since(int(time.time()) - 86400))}",
            f"✅ کل ارسال: {fa(counts.get('sent', 0))}",
            f"❌ ناموفق: {fa(counts.get('failed', 0))}",
            f"🔹 عادی: {self.profile_status('standard')}",
            f"👑 ویژه: {self.profile_status('vip')}",
        ]

        if exchange["enabled"]:
            try:
                _fex, _uex, _tex = self.adaptive_extra()
                _emin, _emax = self.effective_join_gap()
                _adapt_str = f" +{fa(_tex)} تطبیقی" if _tex else ""
            except Exception:
                _emin = int(exchange.get("min_join_gap_sec",30) or 30)
                _emax = int(exchange.get("max_join_gap_sec",60) or 60)
                _adapt_str = ""
                _tex = 0
            lines += [
                "",
                "━━━━━━━━━━━━━━",
                f"🔁 تبادل: روشن  ·  گروه‌ها: {fa(len(exchange.get('groups') or []))}",
                f"⏱ فاصله جوین: {fa(_emin)}–{fa(_emax)} ثانیه (پایه {fa(exchange['min_join_gap_sec'])}–{fa(exchange['max_join_gap_sec'])}{_adapt_str})",
                f"🧠 تطبیقی: {'روشن' if exchange.get('adaptive_on',True) else 'خاموش'} · اضافه Flood {fa(exchange.get('_adaptive_flood_extra',0))}ثانیه · آپ‌تایم {fa(int((int(time.time())-self.started)//3600))}ساعت",
                f"🔍 اسکن گروه: هر {secs(max(30, int(exchange.get('scan_every_sec', 30) or 30)))}",
                f"🤝 جوین امروز: {fa(ex_counts.get('joined', 0))}",
                f"⏳ در صف Join: {fa(ex_counts.get('approved', 0))}",
                f"⌛ منتظر بررسی: {fa(ex_counts.get('pending', 0))}",
            ]
        else:
            lines.append("🔁 تبادل: خاموش")

        lines.append(f"🧠 هوش مصنوعی: {'روشن' if self.ai.ready else 'خاموش'}")
        try:
            _rc = self.st["risk"]
            _edge, _rparts, _rmeta = self.real_risk_edge()
            _hard = bool(_rc.get("hard_on", True))
            _ex_state = "🟢" if exchange["enabled"] else "🔴"
            _reason = " (خاموشی خودکار)" if _rc.get("_auto_off") else ""
            # پایشِ واقعی را به‌عنوان نگهبانِ اصلی نمایش بده؛
            # امتیازِ انتزاعی را فقط وقتی روشن است بیاور.
            if _hard:
                _pl = ("🟢 در مرز ریپ نیست" if not _edge
                       else "🔴 در مرز ریپ — توقف اجباری")
                lines.append(f"🛡 پایشِ واقعی: {_pl}  ·  "
                             f"امتیازِ واقعی {_rmeta['score']}/{_rc.get('hard_trigger', 80)}  ·  "
                             f"تبادل {_ex_state}{_reason}")
            else:
                lines.append(f"🛡 پایشِ واقعی: 🔴 خاموش  ·  تبادل {_ex_state}{_reason}")
            if _rc.get("on", True):
                _risk, _parts, _meta = self.risk_current()
                lines.append(f"🎛 توقف بر امتیاز: 🟢 روشن  ·  "
                             f"ریسک {_risk}%  ·  آستانه {_rc.get('trigger', 75)}%")
        except Exception:
            pass
        if self.last_error:
            lines += [f"⚠️ آخرین خطا: {self.last_error[:100]}"]

        lines += [
            "",
            "━━━━━━━━━━━━━━",
            "📂 منوی اصلی:",
            "🔹 بخش عادی  →  `عادی`",
            "👑 بخش ویژه  →  `ویژه`",
            "🔁 تبادل  →  `تبادل`",
            "👥 گروه‌ها  →  `گروه`",
            "📮 صف ارسال  →  `صف`",
            "📊 آمار  →  `آمار`",
            "🎛 تنظیمات  →  `تنظیمات`",
            "📖 راهنما  →  `راهنما`",
            "",
            "━━━━━━━━━━━━━━",
            QUICK_EXCHANGE_HELP,
            "👉  `تبادل سریع`",
            "",
            "🚪 بستن پنل  →  `بستن پنل`",
            "   (پنل پاک می‌شه و پیامِ شروع دوباره میاد)",
        ]
        return "\n".join(lines) + "\n"

    def settings_text(self):
        o = [
            "════════════════════",
            "🎛   تنظیمات کامل",
            "════════════════════",
        ]
        for tier, nm, ic in (("standard", "عادی", "🔹"), ("vip", "VIP", "👑")):
            p = self.st.prof(tier)
            cap = "آزاد" if not p["max_per_hour"] else f"{fa(p['max_per_hour'])} پیام در ساعت"
            q = p.get("quiet_hours") or []
            qs = "ندارد" if not q else "، ".join(fa(h) for h in q)
            o += [
                f"{ic}  بخش {nm}",
                f"📡  کانال: {p['channel'] or 'تنظیم نشده'}",
                f"⚙️  حالت: {'۲۴ ساعته' if p['mode']=='always' else 'چرخه‌ای'}     {'حالت ویژه' if tier == 'vip' else 'حالت'}",
                f"▶️  فعالیت: {dur(p['active_minutes'])}     {'فعالیت ویژه' if tier == 'vip' else 'فعالیت'}",
                f"😴  استراحت: {dur(p['rest_minutes'])}     {'استراحت ویژه' if tier == 'vip' else 'استراحت'}",
                f"🚦  سقف: {cap}     {'سقف ویژه' if tier == 'vip' else 'سقف'}",
                f"⏳  فاصله: {fa(p['min_gap_sec'])} تا {fa(p['max_gap_sec'])} ثانیه     {'فاصله ویژه' if tier == 'vip' else 'فاصله'}",
                f"🌙  سکوت: {qs}     {'سکوت ویژه' if tier == 'vip' else 'سکوت'}",
                f"📍  الان: {self.profile_status(tier)}",
                "────────────────────",
            ]
        o += [
            "⏸  توقف ارسال: توقف",
            "▶️  ادامه: ادامه",
            "♻️  ریست چرخه: بازنشانی",
            "════════════════════",
        ]
        return "\n".join(o)

    def queue_text(self):
        items = self.db.list_pending(12)
        c = self.db.counts()
        o = [
            "════════════════════",
            "📮   صف ارسال",
            "════════════════════",
            f"⏳  در انتظار: {fa(self.db.pending_count())}",
            f"✅  ارسال‌شده: {fa(c.get('sent', 0))}",
            f"❌  ناموفق: {fa(c.get('failed', 0))}",
            f"📦  معلق (بی‌کانال): {fa(self.db.held_count())}",
            "────────────────────",
        ]
        if not items:
            o.append("🕳  صف خالی است.")
        else:
            for it in items:
                if not it["target"]:
                    mark = "📦 معلق"
                elif it["tier"] == "vip":
                    mark = "👑 VIP"
                else:
                    mark = "🔹 عادی"
                preview = (it["text"] or "").replace("\n", " ")[:40]
                o.append(f"{mark}  #{fa(it['id'])}")
                o.append(f"    {preview}")
            o += [
                "────────────────────",
                "🗑  حذف یکی:  حذف شماره",
                "🧹  خالی کردن:  پاکسازی",
                "♻️  تلاش دوباره:  تلاش دوباره",
            ]
        o.append("════════════════════")
        return "\n".join(o)

    def stats_text(self):
        now = int(time.time())
        c = self.db.counts()
        return "\n".join([
            "════════════════════",
            "📊   آمار ارسال",
            "════════════════════",
            f"🕐  ۱ ساعت اخیر: {fa(self.db.sent_since(now - 3600))}",
            f"📆  ۲۴ ساعت: {fa(self.db.sent_since(now - 86400))}",
            f"🗓  ۷ روز: {fa(self.db.sent_since(now - 604800))}",
            f"🏆  کل ارسال: {fa(c.get('sent', 0))}",
            f"❌  ناموفق: {fa(c.get('failed', 0))}",
            f"📮  الان در صف: {fa(self.db.pending_count())}",
            f"🕰  آپ‌تایم: {secs(now - self.started)}",
            "════════════════════",
        ])


# ─────────────────────────────────────────────
#  گرفتن خودکار api_id و api_hash از my.telegram.org
# ─────────────────────────────────────────────
MTG = "https://my.telegram.org"
UA = ("Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 "
      "(KHTML, like Gecko) Chrome/122.0 Safari/537.36")


class MyTelegram:
    """ورود به my.telegram.org و ساخت/خواندن اپلیکیشن."""

    def __init__(self):
        self.jar = http.cookiejar.CookieJar()
        self.opener = urllib.request.build_opener(
            urllib.request.HTTPCookieProcessor(self.jar))
        self.random_hash = ""

    def _post(self, path, data, timeout=30):
        body = urllib.parse.urlencode(data).encode()
        req = urllib.request.Request(
            MTG + path, data=body, method="POST",
            headers={"User-Agent": UA,
                     "Referer": MTG + "/auth",
                     "Origin": MTG,
                     "X-Requested-With": "XMLHttpRequest",
                     "Content-Type": "application/x-www-form-urlencoded"})
        with self.opener.open(req, timeout=timeout) as r:
            return r.read().decode("utf-8", "ignore").strip()

    def _get(self, path, timeout=30):
        req = urllib.request.Request(
            MTG + path, headers={"User-Agent": UA, "Referer": MTG + "/auth"})
        with self.opener.open(req, timeout=timeout) as r:
            return r.read().decode("utf-8", "ignore")

    # ---------- مرحله ۱: درخواست کد ----------
    def send_code(self, phone):
        """کد را به تلگرامِ همان شماره می‌فرستد. (موفق, پیام)"""
        phone = phone.strip().replace(" ", "").replace("-", "")
        if not phone.startswith("+"):
            phone = "+" + phone
        try:
            out = self._post("/auth/send_password", {"phone": phone})
        except urllib.error.HTTPError as e:
            return False, f"HTTP {e.code} — سایت جواب نداد"
        except urllib.error.URLError as e:
            return False, f"دسترسی به my.telegram.org نشد ({e.reason})"
        except Exception as e:
            return False, f"{type(e).__name__}: {e}"

        try:
            d = json.loads(out)
        except Exception:
            low = out.lower()
            if "banned" in low:
                return False, "این شماره از my.telegram.org مسدود شده"
            if "invalid" in low or "phone" in low:
                return False, "شماره پذیرفته نشد — با کد کشور بزن مثل +989121234567"
            return False, f"پاسخ نامفهوم: {out[:120]}"

        self.random_hash = d.get("random_hash", "")
        if not self.random_hash:
            return False, f"random_hash نیامد: {out[:120]}"
        return True, "کد در تلگرام فرستاده شد"

    # ---------- مرحله ۲: ورود با کد ----------
    def login(self, phone, code):
        phone = phone.strip().replace(" ", "").replace("-", "")
        if not phone.startswith("+"):
            phone = "+" + phone
        try:
            out = self._post("/auth/login", {
                "phone": phone,
                "random_hash": self.random_hash,
                "password": code.strip()})
        except urllib.error.HTTPError as e:
            return False, f"HTTP {e.code}"
        except Exception as e:
            return False, f"{type(e).__name__}: {e}"

        if out.lower().startswith("true"):
            return True, "وارد شدی"
        low = out.lower()
        if "invalid" in low or "false" in low:
            return False, "کد اشتباه بود"
        return False, f"ورود نشد: {out[:120]}"

    # ---------- مرحله ۳: خواندن یا ساختن اپ ----------
    @staticmethod
    def _parse(html):
        api_id = api_hash = ""
        mh = re.search(r"\b([0-9a-fA-F]{32})\b", html)
        if mh:
            api_hash = mh.group(1).lower()
        mi = re.search(r"App\s*api_id.*?>\s*(\d{4,12})\s*<", html, re.S | re.I)
        if not mi:
            mi = re.search(r'uneditable-input[^>]*>\s*(\d{4,12})\s*<', html)
        if mi:
            api_id = mi.group(1)
        return api_id, api_hash

    def get_or_create(self, title="jafj", shortname="jafj"):
        """(api_id, api_hash, پیام)"""
        try:
            html = self._get("/apps")
        except Exception as e:
            return "", "", f"صفحه apps باز نشد: {e}"

        api_id, api_hash = self._parse(html)
        if api_id and api_hash:
            return api_id, api_hash, "اپلیکیشن از قبل وجود داشت"

        mh = re.search(r'name="hash"\s+value="([^"]+)"', html)
        if not mh:
            if "log in" in html.lower() or "/auth" in html[:400].lower():
                return "", "", "نشست منقضی شد — دوباره تلاش کن"
            return "", "", "فرم ساخت اپ پیدا نشد"

        short = re.sub(r"[^a-z0-9]", "", shortname.lower())[:32]
        if len(short) < 5:
            short = (short + "jafjapp")[:8]
        try:
            self._post("/apps/create", {
                "hash": mh.group(1),
                "app_title": title[:32] or "jafj",
                "app_shortname": short,
                "app_url": "",
                "app_platform": "desktop",
                "app_desc": "personal channel manager"})
        except Exception as e:
            return "", "", f"ساخت اپ نشد: {e}"

        time.sleep(1.5)
        try:
            html = self._get("/apps")
        except Exception as e:
            return "", "", f"بعد از ساخت، صفحه باز نشد: {e}"
        api_id, api_hash = self._parse(html)
        if api_id and api_hash:
            return api_id, api_hash, "اپلیکیشن ساخته شد"
        return "", "", "ساخته شد ولی مقادیر خوانده نشد — چند دقیقه بعد دوباره اجرا کن"


def auto_get_api(phone_hint=""):
    """گفتگوی ترمینالی برای گرفتن خودکار. برمی‌گرداند dict یا None."""
    print("\n" + "─" * 52)
    print("  گرفتن خودکار api_id و api_hash")
    print("  کدی که می‌آید، داخل خودِ تلگرام است (چت Telegram)")
    print("─" * 52)

    mt = MyTelegram()

    phone = phone_hint
    for _ in range(3):
        if not phone:
            phone = ask("📱 شماره با کد کشور (+989121234567): ") or ""
        if not phone:
            return None
        ok, msg = mt.send_code(phone)
        print(("✅ " if ok else "❌ ") + msg)
        if ok:
            break
        phone = ""
    else:
        return None

    for _ in range(3):
        code = ask("🔑 کدی که در تلگرام آمد: ")
        if code is None:
            return None
        if not code:
            continue
        ok, msg = mt.login(phone, code)
        print(("✅ " if ok else "❌ ") + msg)
        if ok:
            break
    else:
        return None

    print("⏳ در حال ساخت اپلیکیشن…")
    api_id, api_hash, msg = mt.get_or_create()
    print(("✅ " if api_id else "❌ ") + msg)
    if not (api_id and api_hash):
        return None

    print(f"\n   api_id:   {api_id}")
    print(f"   api_hash: {api_hash[:8]}…{api_hash[-4:]}\n")
    try:
        return {"api_id": int(api_id), "api_hash": api_hash, "phone": phone}
    except ValueError:
        return None


# ─────────────────────────────────────────────
#  اطلاعات ورود — اگر نبود، می‌پرسد و ذخیره می‌کند
# ─────────────────────────────────────────────
def load_creds():
    c = {"api_id": API_ID, "api_hash": API_HASH, "phone": PHONE}
    if os.path.exists(CREDS_FILE):
        try:
            with open(CREDS_FILE, encoding="utf-8") as f:
                saved = json.load(f)
            # فایل کنار سلف (از پنل مدیر) اولویت دارد
            for k in c:
                if saved.get(k):
                    c[k] = saved[k]
        except Exception:
            pass
    return c


def save_creds(c):
    try:
        with open(CREDS_FILE, "w", encoding="utf-8") as f:
            json.dump(c, f, ensure_ascii=False, indent=2)
        if hasattr(os, "chmod"):
            try:
                os.chmod(CREDS_FILE, 0o600)
            except Exception:
                pass
    except Exception as e:
        print(f"⚠️ ذخیره اطلاعات ورود ناموفق: {e}")


def ask(prompt):
    """ورودی امن — اگر ترمینال تعاملی نبود None برمی‌گرداند."""
    try:
        print(prompt, end="", flush=True)
        sys.stdout.flush()
        sys.stderr.flush()
        line = sys.stdin.readline()
        if line == "":
            return None
        return line.strip()
    except (EOFError, KeyboardInterrupt, OSError):
        return None


# ─────────────────────────────────────────────
#  قفلِ «یک نسخه روی یک اکانت»
# ─────────────────────────────────────────────
#  چرا: اگر دو 95.py روی یک سشن اجرا شوند، تلگرام هر دو اتصال را می‌بندد و
#  نتیجه دقیقاً همان چیزی است که کاربر می‌بیند: «🔄 اتصال قطع شد» بی‌پایان و
#  «پنل نمی‌آید». این قفل جلوی تولدِ نسخه‌ی دوم را می‌گیرد.
RUN_LOCK = "jafj.run.lock"


def _num_alive(pid):
    try:
        os.kill(int(pid), 0)
        return True
    except PermissionError:
        return True
    except Exception:
        return False


def _is_our_selfbot(pid):
    """آیا آن PID واقعاً یک 95.py در همین پوشه است؟"""
    try:
        with open(f"/proc/{int(pid)}/cmdline", "rb") as f:
            cmd = f.read().replace(b"\x00", b" ").decode("utf-8", "ignore")
    except Exception:
        return True                      # نمی‌دانیم → محافظه‌کارانه «بله»
    if "95.py" not in cmd:
        return False
    try:
        cwd = os.readlink(f"/proc/{int(pid)}/cwd")
    except Exception:
        return True
    try:
        return os.path.abspath(cwd) == os.path.abspath(os.getcwd())
    except Exception:
        return True


def acquire_run_lock():
    """(گرفتم؟, pidِ نسخه‌ی دیگر) — قفلِ فایلیِ ساده و مقاوم."""
    for _ in range(3):
        try:
            fd = os.open(RUN_LOCK, os.O_CREAT | os.O_EXCL | os.O_WRONLY, 0o600)
            try:
                os.write(fd, str(os.getpid()).encode())
            finally:
                os.close(fd)
            return True, ""
        except FileExistsError:
            pid = 0
            try:
                with open(RUN_LOCK, encoding="utf-8") as f:
                    pid = int((f.read() or "0").strip() or 0)
            except Exception:
                pid = 0
            if pid and pid != os.getpid() and _num_alive(pid) and _is_our_selfbot(pid):
                return False, str(pid)
            # نسخه‌ی قبلی مرده است، ولی اگر «همین چند لحظه پیش» مرده باشد،
            # اتصالش سمتِ تلگرام ممکن است هنوز باز باشد؛ وصل‌شدنِ فوری با
            # همان کلید از IPِ تازه = AuthKeyDuplicated (سوختنِ دائمیِ سشن).
            _wait_for_lock_grace()
            try:
                os.remove(RUN_LOCK)          # قفلِ مرده (PID بازاستفاده‌شده)
            except Exception:
                return True, ""
        except Exception:
            return True, ""                  # اگر نشد، مانعِ اجرا نشو
    return True, ""


def _lock_age():
    """چند ثانیه از نوشتنِ فایلِ قفل گذشته (None اگر معلوم نیست)."""
    try:
        return max(0.0, time.time() - os.path.getmtime(RUN_LOCK))
    except Exception:
        return None


def _lock_grace():
    try:
        return max(0.0, float(os.environ.get("JAFJ_LOCK_GRACE", "90") or 0))
    except Exception:
        return 90.0


def _wait_for_lock_grace():
    """قفلِ مرده‌ی «تازه» را فوری پاک نکن؛ کمی صبر کن.

    چرا: اگر نسخه‌ی قبلی ناگهانی کشته شود (OOM/دیپلوی)، تلگرام اتصالش را
    چند لحظه باز نگه می‌دارد. اجرای فوریِ نسخه‌ی تازه با همان کلید از IPِ
    تازه، کلید را برای همیشه باطل می‌کند. یعنی چند ثانیه صبر ارزان‌تر از
    یک سشنِ سوخته است.
    """
    grace = _lock_grace()
    age = _lock_age()
    if grace <= 0 or age is None or age >= grace:
        return True
    print(f"\n⏳ نسخه‌ی قبلیِ این اکانت {int(age)} ثانیه پیش بسته شده — "
          f"تا ثانیه‌ی {int(grace)} صبر می‌کنم", flush=True)
    print("   (اتصالِ قبلی سمتِ تلگرام ممکن است هنوز باز باشد؛ وصل‌شدنِ فوری "
          "کلید را می‌سوزاند)", flush=True)
    while True:
        age = _lock_age()
        if age is None or age >= grace:
            break
        time.sleep(min(5.0, max(0.2, grace - age)))
    print("✅ مهلت تمام شد — ادامه می‌دهم.", flush=True)
    return True


def release_run_lock():
    try:
        with open(RUN_LOCK, encoding="utf-8") as f:
            if int((f.read() or "0").strip() or 0) != os.getpid():
                return
    except Exception:
        pass
    try:
        os.remove(RUN_LOCK)
    except Exception:
        pass


# ─────────────────────────────────────────────
#  کدهای خروج — مدیر از همین عدد علت را می‌فهمد
# ─────────────────────────────────────────────
#  ۷۶ = نسخه‌ی دومِ همین اکانت (سشن سالم است، اجرا نکردیم)
#  ۷۷ = کلیدِ سشن را تلگرام برای همیشه باطل کرده (AuthKeyDuplicated)
#  ۷۸ = سشن معتبر نیست؛ لاگینِ دوباره لازم است
#  ۷۹ = شبکه/MTProto از این میزبان باز نمی‌شود (تلاش‌ها تمام شد)
EXIT_DUP = 76
EXIT_KEY_BURNED = 77
EXIT_NEEDS_RELOGIN = 78
EXIT_NET_DEAD = 79

# چرا این تشخیص مهم است: متنِ واقعیِ تلگرام
#   «AuthKeyDuplicatedError: The authorization key (session file) was used
#    under two different IP addresses simultaneously, and can no longer be
#    used.»
# با الگوی قدیمی (AUTH_KEY_DUPLICATED با آندرلاین) **نمی‌خواند**، پس خطا
# «شبکه» دیده می‌شد و آدم می‌رفت سراغِ فیلتر و ری‌استارت؛ در حالی که کلید
# مرده است و هر ری‌استارت فقط همان حلقه را تکرار می‌کند.
BURNED_KEY_RE = re.compile(
    r"AUTH_KEY_DUPLICATED|AUTH_KEY_UNREGISTERED|SESSION_REVOKED|"
    r"AuthKeyDuplicated|AuthKeyUnregistered|SessionRevoked|"
    r"two different IP addresses|session file.*used|"
    r"can no longer be used|USER_DEACTIVATED", re.I)


def is_burned_key_error(name="", text=""):
    """آیا این خطا یعنی «کلیدِ سشن سوخته و دیگر هیچ‌وقت وصل نمی‌شود»؟"""
    try:
        return bool(BURNED_KEY_RE.search(str(name or ""))
                    or BURNED_KEY_RE.search(str(text or "")))
    except Exception:
        return False


def burned_key_help(err=""):
    """متنِ روشنِ «چه شد و چه باید کرد» برای لاگ (و در نتیجه برای مدیر)."""
    print("\n" + "═" * 56, flush=True)
    print("⛔ کلیدِ این سشن را تلگرام برای همیشه باطل کرده است "
          "(AuthKeyDuplicated).", flush=True)
    print("   یعنی همین سشن، هم‌زمان از دو IPِ مختلف به تلگرام وصل شده بود؛ "
          "معمولاً", flush=True)
    print("   وقتی دو نسخه از ربات روی یک اکانت اجرا شود یا سرویس از دو "
          "میزبان/دو", flush=True)
    print("   IP بالا بیاید (ری‌استارتِ هم‌زمانِ دو کانتینر).", flush=True)
    print("   این فایلِ سشن دیگر هیچ‌وقت وصل نمی‌شود؛ تلاشِ دوباره فایده "
          "ندارد.", flush=True)
    print("   ✅ کارِ درست: مدیر همین اکانت را «نیاز به لاگین» می‌کند و سشنِ "
          "تازه", flush=True)
    print("      ساخته می‌شود؛ قبلش مطمئن شو فقط یک نسخه از این اکانت "
          "بالاست.", flush=True)
    if err:
        print(f"   ↳ {err}", flush=True)
    print("═" * 56 + "\n", flush=True)


def egress_ip(timeout=4.0):
    """IPِ عمومیِ خروجی — بهترین تلاش، هرگز اجرا را متوقف نمی‌کند."""
    if (os.environ.get("JAFJ_NO_IP_PROBE") or "").strip() not in ("", "0",
                                                                 "false", "نه"):
        return None
    try:
        with urllib.request.urlopen("https://api.ipify.org", timeout=timeout) as r:
            ip = (r.read(64) or b"").decode("utf-8", "ignore").strip()
    except Exception:
        return None
    if not (6 <= len(ip) <= 45):
        return None
    if any(c not in "0123456789.:abcdefABCDEF" for c in ip):
        return None
    return ip


def log_egress_ip():
    """IPِ خروجی را در لاگ بنویس و اگر عوض شده هشدار بده.

    چرا: «یک سشن از دو IP» تنها دلیلی است که تلگرام کلید را می‌سوزاند. با
    ثبتِ IP در هر اجرا، اگر میزبان بین دو اجرا IP را عوض کند (یا IPv4/IPv6
    را قاطی کند) خودِ لاگ لو می‌دهد — بدونِ آزمون و خطا.
    """
    ip = egress_ip()
    if not ip:
        return None
    prev = ""
    try:
        if os.path.isfile("jafj_ip.txt"):
            with open("jafj_ip.txt", encoding="utf-8") as f:
                prev = ((f.read() or "").strip().split() or [""])[0]
        with open("jafj_ip.txt", "w", encoding="utf-8") as f:
            f.write(f"{ip} {int(time.time())}\n")
    except Exception:
        pass
    print(f"🌐 IPِ خروجی: {ip}"
          + (f"   (دفعه‌ی قبل: {prev})" if prev and prev != ip else ""),
          flush=True)
    if prev and prev != ip:
        print("⚠️ IPِ خروجی بین این اجرا و اجرای قبل عوض شده. اگر تلگرام یک "
              "سشن را", flush=True)
        print("   هم‌زمان از دو IP ببیند، کلیدش را برای همیشه باطل می‌کند "
              "(AuthKeyDuplicated).", flush=True)
        print("   یعنی مقصر «کد» نیست، میزبان/شبکه است؛ سرویسِ دوم را ببند.",
              flush=True)
        try:
            if os.path.exists(SESSION + ".session"):
                print("   ⚠️ این اکانت سشن دارد و IP عوض شده — اگر بعد از این "
                      "«کلید باطل شده» دیدی، همین علتش بوده است.", flush=True)
        except Exception:
            pass
    return ip


def ensure_creds():
    """تا وقتی api_id و api_hash درست نگرفته، می‌پرسد. خاموش نمی‌شود."""
    c = load_creds()
    if c["api_id"] and c["api_hash"]:
        return c

    print("\n" + "─" * 52)
    print("  یک بار باید api_id و api_hash داشته باشی.")
    print("─" * 52)
    print("  ۱) خودکار بگیرم  (فقط شماره و یک کد از تلگرام)")
    print("  ۲) خودم دستی وارد می‌کنم")
    print("─" * 52)

    pick = ask("انتخاب [۱]: ")
    if pick is None:
        print("\n⚠️ ترمینال تعاملی نیست. api_id و api_hash را بالای فایل بگذار.")
        return None

    if pick.strip() in ("", "1", "۱"):
        got = auto_get_api(c.get("phone") or "")
        if got:
            c.update(got)
            save_creds(c)
            print("✅ ذخیره شد — دفعه بعد نمی‌پرسد.\n")
            return c
        print("\n⚠️ خودکار نشد. دستی وارد کن.")
        print("   my.telegram.org → API development tools\n")

    while not c["api_id"]:
        v = ask("🔑 api_id (فقط عدد): ")
        if v is None:
            print("\n⚠️ ترمینال تعاملی نیست. api_id و api_hash را بالای فایل بگذار.")
            return None
        try:
            c["api_id"] = num(v)
        except ValueError:
            print("   عدد نبود، دوباره بزن.")

    while not c["api_hash"]:
        v = ask("🔑 api_hash: ")
        if v is None:
            return None
        if len(v) >= 8:
            c["api_hash"] = v
        else:
            print("   کوتاه بود، دوباره بزن.")

    save_creds(c)
    print("✅ ذخیره شد — دفعه بعد نمی‌پرسد.\n")
    return c


# ─────────────────────────────────────────────
#  لایه تلگرام (Telethon)
# ─────────────────────────────────────────────
def need_telethon():
    try:
        import telethon  # noqa
        return False
    except ImportError:
        return True


async def connect_and_run(eng, creds):
    """یک بار وصل می‌شود و کار می‌کند. برمی‌گرداند: 'retry' یا 'stop'"""
    from telethon import TelegramClient, events
    from telethon.errors import (FloodWaitError, SlowModeWaitError,
                                 ChatWriteForbiddenError, ChannelPrivateError,
                                 UsernameNotOccupiedError, RPCError,
                                 UserNotParticipantError, UserAlreadyParticipantError,
                                 InviteHashExpiredError, InviteHashInvalidError,
                                 ChannelsTooMuchError, InviteRequestSentError)
    from telethon.tl.functions.channels import (JoinChannelRequest, LeaveChannelRequest,
                                                GetParticipantRequest)
    from telethon.tl.functions.messages import ImportChatInviteRequest

    client = TelegramClient(SESSION, creds["api_id"], creds["api_hash"],
                            flood_sleep_threshold=0)

    async def phone_cb():
        if creds.get("phone"):
            return creds["phone"]
        while True:
            v = ask("📱 شماره (مثال +989123456789): ")
            if v is None:
                raise RuntimeError("no-tty")
            if len(v) >= 7:
                creds["phone"] = v
                save_creds(creds)
                return v
            print("   شماره کوتاه بود، دوباره بزن.")

    # ═══════════════════════════════════════════════════════════════════
    #  ورود — و این‌جا مهم‌ترین قاعده: **هیچ کدِ ورودیِ ناخواسته نرود**
    #
    #  `client.start(phone=...)` وقتی سشن معتبر نباشد برای صاحبِ شماره کد
    #  می‌فرستد. بعد از آپدیت/بازیابی، اگر فایل سشن خراب یا کلیدش باطل شده
    #  باشد، این یک خط برای **همه‌ی مشتری‌ها** کد می‌فرستد (اسپمِ کد).
    #
    #  حالا: اول وصل می‌شویم و `is_user_authorized()` را می‌پرسیم (این کار
    #  هیچ کدی نمی‌فرستد). اگر authorized نبود:
    #    • با NO_AUTO_LOGIN=1 (حالتِ مدیر) → کد نمی‌فرستیم، دلیل را چاپ
    #      می‌کنیم و با کدِ ۷۸ خارج می‌شویم تا مدیر اکانت را «نیاز به
    #      لاگینِ دوباره» علامت بزند و حلقهٔ ری‌استارت کد نسازد.
    #    • بدون آن (اجرای دستی روی لپ‌تاپ) → رفتار قبلی، با پرسیدن از کاربر.
    # ═══════════════════════════════════════════════════════════════════
    no_auto = (os.environ.get("JAFJ_NO_AUTO_LOGIN") or "").strip() not in ("", "0", "false", "نه")
    authorized = False
    try:
        await client.connect()
        try:
            authorized = bool(await client.is_user_authorized())
        except Exception as e:
            if is_burned_key_error(type(e).__name__, e):
                burned_key_help(f"{type(e).__name__}: {e}")
                return "key_burned"
            print(f"\n⚠️ بررسیِ سشن: {type(e).__name__}: {e}", flush=True)
            authorized = False
    except Exception as e:
        if is_burned_key_error(type(e).__name__, e):
            # کلید مرده است: تلاشِ دوباره فقط همان حلقه را تکرار می‌کند و
            # مدیر هم جایی برای دیدنِ علتِ واقعی ندارد.
            burned_key_help(f"{type(e).__name__}: {e}")
            return "key_burned"
        print(f"\n⚠️ اتصال برای بررسیِ سشن: {type(e).__name__}: {e}", flush=True)
        await asyncio.sleep(5)
        return "retry"

    if not authorized:
        if no_auto:
            print("\n⛔ سشنِ این اکانت معتبر نیست (از تلگرام خارج یا باطل شده).",
                  flush=True)
            print("   ✅ کدِ ورود **فرستاده نشد** — عمداً؛ تا اسپمِ کد نسازیم.",
                  flush=True)
            print("   👉 از پنلِ مدیر: «🚀 راه‌اندازی سلف روی اکانتم» را برای این "
                  "اکانت بزن.", flush=True)
            try:
                await client.disconnect()
            except Exception:
                pass
            return "needs_relogin"
        # اجرای دستی: همان رفتارِ قبلی (کد می‌رود، چون خودِ کاربر نشسته)
        try:
            await client.start(phone=phone_cb)
        except RuntimeError:
            print("\n⚠️ ترمینال تعاملی نیست — PHONE را بالای فایل بگذار.")
            return "stop"
        except FloodWaitError as e:
            w = getattr(e, "seconds", 60)
            print(f"\n⏳ تلگرام برای ورود {secs(w)} صبر خواسته. منتظر می‌مانم…")
            await asyncio.sleep(w + 5)
            return "retry"
        except Exception as e:
            print(f"\n⚠️ ورود ناموفق: {type(e).__name__}: {e}")
            print("   ۳۰ ثانیه دیگر دوباره تلاش می‌کنم… (Ctrl+C برای خروج)")
            await asyncio.sleep(30)
            return "retry"
    # وصل بمان: بقیه‌ی کد به اتصالِ زنده نیاز دارد (قبلاً start() خودش وصل
    # می‌ماند؛ حالا ما وصل می‌کنیم).
    try:
        if not client.is_connected():
            await client.connect()
    except Exception as e:
        print(f"\n⚠️ اتصال دوباره: {type(e).__name__}: {e}", flush=True)
        await asyncio.sleep(5)
        return "retry"

    me = await client.get_me()
    eng.me = (f"{me.first_name or ''} (@{me.username})" if me.username
              else (me.first_name or str(me.id)))
    eng.my_username = me.username or ""
    eng.my_id = me.id
    eng.write_status()
    eng.log("ok", "login", f"{eng.me} | id={me.id}")

    for tier in ("standard", "vip"):
        p = eng.st.prof(tier)
        mode = ("۲۴ساعته" if p["mode"] == "always"
                else f"{p['active_minutes']}د فعال/{p['rest_minutes']}د استراحت")
        print(f"  {tier:9} | {mode} | سقف {p['max_per_hour'] or '∞'}/ساعت "
              f"| فاصله {p['min_gap_sec']}-{p['max_gap_sec']}s "
              f"| {p['channel'] or 'کانال تعیین نشده'}")
    held = eng.db.held_count()
    if held:
        print(f"  📦 {held} پیام معلق — منتظر تعیین کانال")
    _x = eng.ex_cfg()
    if _x["enabled"]:
        _ec = eng.db.ex_counts()
        print(f"  🔁 تبادل روشن | {_ec.get('joined', 0)} جوین‌شده | "
              f"{'خودکار' if _x['auto_join'] else 'تأیید دستی'} | "
              "بدون سقف روزانه")
    print("═" * 50)
    print("  ✅ آماده — در Saved Messages بفرست: پنل\n")

    # ── ضدحلقه ──
    # شناسه‌ی پیام‌هایی که خودِ ربات به Saved Messages فرستاده. هندلرِ «me»
    # حالا outgoing را هم می‌شنود (فرمانِ کاربر از گوشی‌اش هم out=True
    # می‌آید)، پس فقط راهِ تشخیص «پاسخِ خودِ ربات» از «فرمانِ کاربر»،
    # نگه‌داشتن شناسه‌ی ارسال‌های خودِ ربات است.
    own_msg_ids = {}
    quick_exchange_state = {}
    # شناسه‌ی پیام‌های «پنل» که خودِ ربات فرستاده. با `بستن پنل` همین‌ها
    # پاک می‌شوند تا کاربر مجبور نباشد پیامِ طولانیِ پنل را دستی حذف کند.
    panel_msg_ids = []

    def _track_own(msg):
        try:
            own_msg_ids[int(getattr(msg, "id", 0) or 0)] = time.time()
        except Exception:
            pass
        if len(own_msg_ids) > 800:
            cutoff = time.time() - 900
            for k in [k for k, v in own_msg_ids.items() if v < cutoff]:
                own_msg_ids.pop(k, None)
            while len(own_msg_ids) > 800:
                own_msg_ids.pop(next(iter(own_msg_ids)))

    async def note(text):
        try:
            msg = await client.send_message("me", text, link_preview=False)
            _track_own(msg)
            return msg
        except Exception:
            return None

    def _startup_text():
        """پیامِ شروع — همان متنی که موقعِ بالا آمدن ربات می‌رود.

        `بستن پنل` عیناً همین را دوباره می‌فرستد تا کاربر بعد از بستنِ
        پنل دوباره راهنمای شروع (و میان‌برِ `تبادل سریع`) را ببیند. یک
        تابعِ مشترک است تا پیامِ ران و پیامِ بعد از بستن هیچ‌وقت از هم
        جدا نیفتند.
        """
        hint = ""
        if not eng.ex_channel_ready():
            hint = "\n\n📡 کانال هنوز تعیین نشده: `کانال @channel`"
        elif not (eng.ex_cfg().get("groups") or []):
            hint = "\n\n👥 گروه تبادل هنوز ثبت نشده: `تبادل سریع`"
        return (f"🟢 جفج {VERSION} آنلاین شد — پنل جدید\n\n"
                f"`پنل` داشبورد • `راهنما` راهنما\n\n"
                f"⚡ `تبادل سریع` — فقط کانال + گروه → تبادل آماده با "
                f"متن‌های پیش‌فرض{hint}")

    _warn_check = {"last": 0}
    _warn_check_flood = {"last": 0}
    _warn_no_channel = {"last": 0}

    async def warn_ex_no_channel(now):
        """هشدارِ یک‌بار در ۱۰ دقیقه: تبادل روشن است ولی کانال نداریم."""
        if int(now) - int(_warn_no_channel["last"] or 0) < 600:
            return
        _warn_no_channel["last"] = int(now)
        await note("⚠️ تبادل روشن است ولی **کانالِ من** تنظیم نشده — "
                   "تا ثبتش نکنی هیچ اسکن/چک/جوینی انجام نمی‌دهم.\n"
                   "`کانال @mychannel` یا `تبادل سریع`")
    check_gate = CheckGate()
    # صفِ تک‌عملکردی تبادل: هیچ دو عملکردی (چک/جوین/لفت/پیام) همزمان یا
    # پشت‌سرهمِ بدون فاصله اجرا نمی‌شوند. قبل از تعریف تابع‌های چک ساخته
    # می‌شود تا همه‌ی مسیرها از یک دریچه رد شوند.
    ex_cd = ExCooldown(cfg=eng.ex_cfg,
                       gap_min=eng.ex_cfg().get("op_gap_min_sec", 15),
                       gap_max=eng.ex_cfg().get("op_gap_max_sec", 20))

    async def warn_membership_check_broken(now):
        """هشدارِ یک‌بار در ۱۰ دقیقه: چک عضویت مدتی است بی‌نتیجه است.
        قبلاً این حالت کاملاً بی‌صدا بود؛ نتیجه‌اش این بود که نه «نیومدی»
        می‌رفت نه لفت انجام می‌شد و صاحب‌حساب هم نمی‌فهمد چرا."""
        if int(now) - int(_warn_check["last"] or 0) < 600:
            return
        _warn_check["last"] = int(now)
        has_ch = any((eng.st.prof(t)["channel"] or "").strip()
                     for t in ("standard", "vip"))
        if has_ch:
            await note("🕵️ بررسی عضویت مدتی است **نامشخص** می‌ماند "
                       "(FloodWait یا محدودیت API). خودم دوباره امتحان "
                       "می‌کنم؛ اگر ادامه داشت اکانت را کمی استراحت بده.")
        else:
            await note("⚠️ **کانال من تنظیم نشده است** — تا وقتی با "
                       "`کانال @username` ستش نکنی، هیچ عضویتی تأیید "
                       "نمی‌شود: نه «نیومدی» می‌رود نه لفت خودکار انجام "
                       "می‌شود.")

    # ---------- هوش مصنوعی ----------
    async def handle_ai(event, arg, reply_text=None):
        a = eng.ai

        # تست اتصال
        if arg.strip().lower() in ("test", "تست"):
            if not a.cfg["key"]:
                return "⚠️ کلیدی ثبت نشده.\n`هوش کلید sk-...`"
            try:
                await event.reply("⏳ در حال تست…")
            except Exception:
                pass
            out, err = await a.achat(
                [{"role": "user", "content": "فقط بنویس: سلام"}],
                temperature=0, max_tokens=20, timeout=45)
            if err:
                return (f"❌ اتصال برقرار نشد.\n\n`{err}`\n\n"
                        f"سرویس: `{a.cfg['base_url']}`\nمدل: `{a.cfg['model']}`\n\n"
                        "کلید تازه: `هوش کلید sk-...`\n"
                        "سرویس دیگر: `هوش آدرس https://…/v1`")
            return (f"✅ وصل شد!\n\nسرویس: `{a.cfg['base_url']}`\n"
                    f"مدل: `{a.cfg['model']}`\nجواب: {out}")

        # تنظیمات (بدون شبکه)
        res = eng.ai_settings_cmd(arg)
        if res is not None:
            return res

        # سوال
        if not a.ready:
            return (f"🧠 AI آماده نیست.\n"
                    f"{'کلید ثبت نشده' if not a.cfg['key'] else 'خاموش است'}.\n"
                    "`هوش کلید sk-...` سپس `هوش تست`")

        q = arg if not reply_text else f"{arg}\n\n--- متن ریپلای‌شده ---\n{reply_text}"
        try:
            _track_own(await event.reply("🧠 …"))
        except Exception:
            pass
        out, err = await a.ask(q, eng.ai_context())
        if err:
            return f"❌ {err}"
        return out or "جوابی نیامد."

    # ---------- پنل — incoming و outgoing هر دو (پیام از گوشی دیگر هم برسد)
    pattern = re.compile(r"^[./]([^\s]+)(?:\s+([\s\S]*))?$")

    def _norm_cmd(s):
        # نیم‌فاصله متن کاربر حفظ شود؛ برای تشخیص دستور از low استفاده می‌کنیم.
        s = (s or "").replace("\u200b", "").replace("\ufeff", "")
        s = s.replace("ي", "ی").replace("ك", "ک").strip()
        return s

    def _to_html(txt):
        import html as _html
        parts = re.split(r"`([^`]+)`", txt or "")
        o = []
        for i, p in enumerate(parts):
            if i % 2:
                o.append("<code>" + _html.escape(p) + "</code>")
            else:
                q = _html.escape(p)
                q = re.sub(r"\*\*(.+?)\*\*", r"<b>\1</b>", q, flags=re.S)
                q = re.sub(r"__(.+?)__", r"<i>\1</i>", q, flags=re.S)
                o.append(q)
        return "".join(o)

    async def _say(txt, event=None):
        if not txt:
            return None
        h = _to_html(txt)
        # همیشه به Saved Messages (me) برمی‌گردد تا پاسخ، مستقل از محلِ پیام،
        # حتماً در جایی که ربات کنترلِ آن را دارد دیده شود.
        try:
            msg = await client.send_message("me", h, parse_mode="html",
                                            link_preview=False)
            _track_own(msg)
            return msg
        except Exception as e:
            eng.log("warn", "say_html", f"{type(e).__name__}: {str(e)[:120]}")
        # اگر HTML رد شد، با متنِ خام تلاش کن.
        try:
            msg = await client.send_message("me", txt, link_preview=False)
            _track_own(msg)
            return msg
        except Exception as e:
            eng.log("error", "say", f"{type(e).__name__}: {str(e)[:120]}")
        return None

    async def _send_panel():
        try:
            txt = eng.panel()
        except Exception as e:
            txt = f"⚠️ پنل خطا داد: {type(e).__name__}: {e}"
            traceback.print_exc()
            eng.log("error", "panel", str(e))
        msg = await _say(txt)
        mid = int(getattr(msg, "id", 0) or 0) if msg else 0
        if mid:
            panel_msg_ids.append(mid)
            # فقط پنل‌های اخیر را نگه دار؛ بستنِ پنل همه‌ی همین‌ها را پاک می‌کند.
            if len(panel_msg_ids) > 50:
                del panel_msg_ids[:-50]

    async def _close_panel(user_id=0):
        """بستنِ پنل: پیام‌های پنل پاک می‌شوند و پیامِ شروع دوباره می‌آید.

        «پنل» در Saved Messages یک پیامِ ساده است (دکمه‌ی بستن ندارد)، پس
        بدون این مسیر کاربر مجبور بود پیام را دستی حذف کند. حالا هم
        می‌تواند دستی پیام را پاک کند (ربات چیزی نمی‌فرستد) و هم با
        `بستن پنل` هم پیام پاک شود و هم پیامِ شروع برگردد.
        """
        ids = [int(i) for i in panel_msg_ids if i]
        panel_msg_ids.clear()
        quick_exchange_state.pop(user_id, None)
        if ids:
            try:
                await client.delete_messages("me", ids)
            except Exception as e:
                eng.log("warn", "panel_close",
                        f"{type(e).__name__}: {str(e)[:120]}")
        await note(_startup_text())

    def _ensure_quick_exchange_defaults(ex_cfg):
        updated = False
        for key, default_text in QUICK_EXCHANGE_DEFAULTS.items():
            current = str(ex_cfg.get(key) or "").strip()
            previous_default = QUICK_EXCHANGE_PREVIOUS_DEFAULTS.get(key)
            if not current or (previous_default and current == previous_default):
                if current != default_text:
                    ex_cfg[key] = default_text
                    updated = True
        return updated

    def _qe_prompt(step, extra=""):
        if step == "channel":
            return ("📡 کانالِ خودت رو بفرست (مثلاً @mychannel)\n"
                    "برای انصراف: `لغو`" + extra)
        if step == "backup_group":
            return ("➕ گروه اصلی ثبت شد. گروه پشتیبان هم می‌خواهی؟\n"
                    "۱) برای افزودن، آیدی گروه دوم را بفرست؛ مثلاً `@backup`\n"
                    "۲) برای ادامه بدون پشتیبان، بنویس `بدون پشتیبان`\n"
                    "برای لغو کامل: `لغو`")
        return ("👥 فقط گروه اصلی رو بفرست (مثلاً @exchange_group).\n"
                "بعدش دربارهٔ گروه پشتیبان ازت می‌پرسم؛ اجباری نیست.\n"
                "برای انصراف: `لغو`" + extra)

    def _qe_group_refs(ex_cfg):
        groups = ex_cfg.get("groups") or []
        if isinstance(groups, str):
            groups = [groups]
        elif not isinstance(groups, (list, tuple, set)):
            groups = []
        result = []
        for item in groups:
            normalized = normalize_peer_ref(str(item or "").strip())
            if normalized and not any(same_peer_ref(normalized, old) for old in result):
                result.append(normalized)
        return result

    async def _start_quick_exchange(user_id):
        x = eng.ex_cfg()
        # مقادیرِ قدیمی هم از همین فیلتر رد می‌شوند: کانالی که «کانال» یا
        # یک جمله‌ی فارسی ذخیره شده، به‌عنوان کانالِ معتبر شناخته نمی‌شود.
        raw_channel = str(eng.st.prof("standard").get("channel") or "").strip()
        channel = normalize_peer_ref(raw_channel) or ""
        saved_groups = _qe_group_refs(x)
        group = saved_groups[0] if saved_groups else ""
        backup_group = saved_groups[1] if len(saved_groups) > 1 else ""

        # قاعده: اگر کانال معتبر نیست، حتی اگر گروه ثبت شده باشد، سراغ
        # گروه نمی‌رویم؛ اول کانال.
        if channel:
            if group and same_peer_ref(channel, group):
                group = ""
            if backup_group and same_peer_ref(channel, backup_group):
                backup_group = ""

        if channel and group:
            if _ensure_quick_exchange_defaults(x):
                eng.st.save()
            quick_exchange_state.pop(user_id, None)
            backup_line = (f"🔁 گروه پشتیبان: {backup_group}\n"
                           f"حالت جایگزین: {'روشن' if x.get('group_failover_on') else 'خاموش'}\n"
                           if backup_group else
                           "🔁 گروه پشتیبان: تنظیم نشده (اختیاری)\n")
            if x.get("enabled"):
                await _say("⚡ تبادل سریع از قبل آماده و روشن است.\n\n"
                           f"📡 کانال: {channel}\n"
                           f"👥 گروه اصلی: {group}\n"
                           f"{backup_line}\n"
                           + ("برای روشن‌کردن جایگزینی: `تبادل گروه جایگزین روشن`\n"
                              if backup_group and not x.get("group_failover_on") else
                              "برای ثبت گروه پشتیبان: `تبادل گروه جایگزین @backup`\n"
                              if not backup_group else "")
                           + "برای دیدن وضعیت: `تبادل`")
            else:
                await _say("⚡ تبادل سریع از قبل آماده است؛ فقط روشنش کن:\n"
                           "`تبادل روشن`\n"
                           + ("جایگزینی گروه اختیاری است؛ تنظیم: `تبادل گروه جایگزین`"
                              if backup_group else ""))
            return

        state = {"step": "channel" if not channel else "group"}
        if channel:
            state["channel"] = channel
        if group:
            # گروه بدون کانال نگه داشته می‌شود ولی تا ثبت کانال شروع نمی‌کنیم.
            state["group"] = group
        if backup_group:
            state["backup_group"] = backup_group
        quick_exchange_state[user_id] = state
        if channel:
            await _say(_qe_prompt("group"))
        else:
            extra = ("\n\n👥 گروهِ ثبت‌شده فعلاً نگه داشته می‌شود؛ تا کانال "
                     "ثبت نشه کاری شروع نمی‌کنم." if group else "")
            await _say(QUICK_EXCHANGE_HELP + "\n\n"
                       + _qe_prompt("channel", extra))

    async def _finish_quick_exchange(user_id, state):
        channel = normalize_peer_ref(state.get("channel"))
        group = normalize_peer_ref(state.get("group"))
        backup_group = normalize_peer_ref(state.get("backup_group"))
        if not channel:
            state.pop("channel", None)
            state["step"] = "channel"
            await _say("❌ کانال معتبر نیست — تبادل شروع نشد.\n"
                       + _qe_prompt("channel",
                                    "\nمثال: `@mychannel` یا `https://t.me/mychannel`"))
            return
        if not group:
            state.pop("group", None)
            state["step"] = "group"
            await _say("❌ گروه معتبر نیست — تبادل شروع نشد.\n"
                       + _qe_prompt("group",
                                    "\nمثال: `@exchange_group`"))
            return
        if same_peer_ref(channel, group):
            state.pop("group", None)
            state.pop("backup_group", None)
            state["step"] = "group"
            await _say("❌ کانال و گروه نمی‌توانند یکی باشند.\n"
                       + _qe_prompt("group"))
            return
        if backup_group and (same_peer_ref(channel, backup_group)
                             or same_peer_ref(group, backup_group)):
            state.pop("backup_group", None)
            state["step"] = "group"
            await _say("❌ گروه پشتیبان باید با کانال و گروه اصلی متفاوت باشد.\n"
                       + _qe_prompt("group"))
            return

        st = eng.st
        st.prof("standard")["channel"] = channel
        ex_cfg = eng.ex_cfg()
        ex_cfg["groups"] = [group] + ([backup_group] if backup_group else [])
        ex_cfg["group_failover_on"] = bool(backup_group)
        ex_cfg["_group_failover_active_index"] = 0
        ex_cfg["_group_failover_last_activity"] = int(time.time())
        _ensure_quick_exchange_defaults(ex_cfg)
        # ── قاعده‌ی ایمنی: بدون کانالِ معتبر هیچ‌وقت روشن نکن ──
        if not eng.ex_channel_ready():
            ex_cfg["enabled"] = False
            st.save()
            await _say("❌ کانال ذخیره نشد؛ تبادل روشن نشد.\n"
                       "`کانال @mychannel` رو دستی بفرست.")
            return
        ex_cfg["enabled"] = True
        # مثل روشن‌کردن دستی، توقف قبلیِ خودکار را از نظر محافظ باطل کن.
        st["risk"]["_auto_off"] = False
        st.save()
        quick_exchange_state.pop(user_id, None)

        await _say(
            "✅ تبادل آماده‌ست!\n\n"
            f"📡 کانال: {channel} ✓\n"
            f"👥 گروه اصلی: {group} ✓\n"
            + (f"🔁 گروه پشتیبان: {backup_group} ✓ (جایگزینی اختیاری روشن)\n"
               if backup_group else
               "🔁 گروه پشتیبان: تنظیم نشده؛ اختیاری است.\n"
               "برای افزودنش بعداً: `تبادل گروه جایگزین @backup`\n")
            + "📝 متن‌های پیش‌فرض: فعال ✓\n"
            "🔁 تبادل: 🟢 روشن\n\n"
            "شروع کردم به جذب ممبر! 🚀\n"
            "برای تنظیمات بیشتر: `پنل`"
        )

    # پیشوندهای صریحِ ورودی در wizard: «کانال @x» و «گروه @y» همیشه به
    # فیلدِ درست می‌روند، نه به فیلدِ فعلی. قبلاً اگر در قدمِ گروه بودی و
    # می‌نوشتی «کانال @x»، خودِ کلمه‌ی «کانال» به‌عنوان گروه ذخیره می‌شد.
    _QE_CHANNEL_PREFIXES = ("کانال", "چنل", "channel")
    _QE_GROUP_PREFIXES = ("گروه", "گروهِ", "group")

    def _qe_parse_input(raw, step):
        """(فیلد, مقدار) — پیشوندِ صریح بر قدمِ فعلی اولویت دارد."""
        text = (raw or "").strip()
        low = text.lower()
        for pref in _QE_CHANNEL_PREFIXES:
            if low == pref:
                return "channel", ""
            if low.startswith(pref) and low[len(pref):len(pref) + 1] in (" ", ":", "：", "\u200c"):
                return "channel", text[len(pref):].strip(" :：\u200c")
        for pref in _QE_GROUP_PREFIXES:
            target = "backup_group" if step == "backup_group" else "group"
            if low == pref:
                return target, ""
            if low.startswith(pref) and low[len(pref):len(pref) + 1] in (" ", ":", "：", "\u200c"):
                return target, text[len(pref):].strip(" :：\u200c")
        value = text if step in ("group", "backup_group") else (text.split()[0] if text.split() else "")
        return (step or "channel"), value

    async def _handle_quick_exchange_input(user_id, raw, low):
        state = quick_exchange_state.get(user_id) or {}
        if low in ("لغو", "cancel", ".cancel", "/cancel", "انصراف"):
            quick_exchange_state.pop(user_id, None)
            await _say("❌ تبادل سریع لغو شد. هیچ تنظیمی تغییر نکرد.")
            return
        if state.get("step") == "backup_group" and low in (
                "رد", "نه", "ندارم", "بدون پشتیبان", "ادامه", "ادامه بدون پشتیبان",
                "skip", "no", "none"):
            state.pop("backup_group", None)
            await _finish_quick_exchange(user_id, state)
            return

        target, value = _qe_parse_input(raw, state.get("step"))
        if not value:
            await _say(_qe_prompt(target))
            return

        if target in ("group", "backup_group"):
            prompt_step = "backup_group" if target == "backup_group" else "group"
            if len(value.split()) > 1:
                if target == "group":
                    await _say("در این مرحله فقط گروه اصلی را بفرست؛ بعد می‌پرسم گروه پشتیبان هم می‌خواهی یا نه.")
                else:
                    await _say("برای گروه پشتیبان فقط یک آیدی/لینک بفرست؛ یا بنویس `رد`.")
                return
            parsed = normalize_peer_ref(value)
            if not parsed:
                await _say(f"❌ «{value[:60]}» آیدی/لینک معتبر نیست.\n"
                           + _qe_prompt(prompt_step, "\nمثال: `@mygroup`"))
                return
            channel = normalize_peer_ref(state.get("channel"))
            main_group = normalize_peer_ref(state.get("group"))
            if channel and same_peer_ref(channel, parsed):
                await _say("❌ گروه نمی‌تواند با کانال خودت یکی باشد.\n"
                           + _qe_prompt(prompt_step))
                return
            if target == "backup_group":
                if main_group and same_peer_ref(main_group, parsed):
                    await _say("❌ گروه پشتیبان باید با گروه اصلی فرق داشته باشد.\n"
                               + _qe_prompt("backup_group"))
                    return
                state["backup_group"] = parsed
                quick_exchange_state[user_id] = state
                await _finish_quick_exchange(user_id, state)
                return
            state["group"] = parsed
            state.pop("backup_group", None)
        else:
            parsed = normalize_peer_ref(value)
            if not parsed:
                await _say(f"❌ «{value[:40]}» یک آیدی/لینکِ معتبر نیست.\n"
                           + _qe_prompt(target, "\nمثال: `@mychannel` یا "
                                                "`https://t.me/+AbCdEfGh`"))
                return
            for other_group in (state.get("group"), state.get("backup_group")):
                if other_group and same_peer_ref(parsed, other_group):
                    await _say("❌ کانال و گروه نمی‌توانند یکی باشند.\n"
                               + _qe_prompt(target))
                    return
            state[target] = parsed
        quick_exchange_state[user_id] = state

        # ── قاعده‌ی «اول کانال» ──
        # حتی اگر کاربر گروه را زودتر داده باشد، تا کانال ثبت نشود
        # هیچ تبادلی شروع نمی‌شود و گروه فقط نگه داشته می‌شود.
        if not normalize_peer_ref(state.get("channel")):
            state["step"] = "channel"
            extra = ("\n\n👥 گروه ذخیره شد، ولی تا کانال ثبت نشه شروع "
                     "نمی‌کنم." if state.get("group") else "")
            await _say(_qe_prompt("channel", extra))
            return

        if not normalize_peer_ref(state.get("group")):
            state["step"] = "group"
            await _say(_qe_prompt("group"))
            return

        if not normalize_peer_ref(state.get("backup_group")):
            state["step"] = "backup_group"
            quick_exchange_state[user_id] = state
            await _say(_qe_prompt("backup_group"))
            return

        await _finish_quick_exchange(user_id, state)

    # incoming و outgoing «هر دو»: فرمانِ «پنل» که از گوشیِ خودت می‌فرستی
    # به این سشن با out=True می‌رسد (همه‌ی پیام‌های Saved Messages از
    # فرستنده‌ی خودِ اکانت‌اند) و فیلترِ incoming=True قبلی آن را می‌کُشت —
    # همین دلیلِ «پنل باز نمی‌شود» بود.
    @client.on(events.NewMessage(chats="me"))
    async def on_saved(event):
        # روی out فیلتر نمی‌کنیم (فرمانِ کاربر هم out=True است). به‌جایش
        # پیام‌هایی که خودِ ربات فرستاده را با شناسه‌شان رد می‌کنیم تا
        # حلقه‌ی «پنل → پاسخ → پاسخِ پاسخ» پیش نیاید.
        if int(getattr(getattr(event, "message", None), "id", 0) or 0) in own_msg_ids:
            return
        # فرمان پنل قبل از هر مسیر AI/تبادل بررسی می‌شود.
        raw = _norm_cmd(event.raw_text or "")
        low = _soft_clean(raw).lower()
        try:
            user_id = int(getattr(event, "sender_id", None) or eng.my_id or 0)
        except (TypeError, ValueError):
            user_id = int(eng.my_id or 0)

        # «بستن پنل» همیشه کار می‌کند — حتی وسطِ wizard تبادل سریع.
        if low in {"بستن پنل", "پنل بستن", ".closepanel", "/closepanel",
                   "closepanel", "close panel", "بستن"}:
            await _close_panel(user_id)
            return

        # ورودیِ فعالِ wizard همیشه داده است، نه فرمان؛ فقط «لغو» از آن خارج می‌شود.
        if user_id in quick_exchange_state:
            await _handle_quick_exchange_input(user_id, raw, low)
            return
        if low in {"تبادل سریع", ".quickexchange", "/quickexchange"}:
            await _start_quick_exchange(user_id)
            return

        panel_words = {
            "panel", ".panel", "/panel", "پنل", ".پنل", "/پنل",
            "p", ".p", "/p", "داشبورد", ".داشبورد", "خانه",
        }
        # «پنل» را حتی با نیم‌فاصله/فاصله‌ی تایپی (پن‌ل / پن ل) هم تشخیص بده.
        if low.startswith(("پن ", "پن‌")) or low in ("پن ل",):
            low = "پنل"
        if low in panel_words or low.startswith(".panel") or low.startswith("/panel"):
            await _send_panel()
            return
        if low == "هوش" or low.startswith("هوش ") or low.startswith("هوش مصنوعی"):
            ai_arg = raw[3:].strip() if low.startswith("هوش ") else ""
            if low.startswith("هوش مصنوعی"):
                ai_arg = raw[len("هوش مصنوعی"):].strip()
            out = await handle_ai(event, ai_arg)
            await _say(out, event)
            return
        bare = {
            "عادی": ("عادی", ""),
            "ویژه": ("ویژه", ""),
            "تبادل": ("ex", ""),
            "گزارش": ("ex", "report"),
            "گزارش خلاصه": ("ex", "report_now"),
            "گزارش خلاصه الان": ("ex", "report_now"),
            "گزارش خلاصه همین الان": ("ex", "report_now"),
            "صف": ("queue", ""),
            "آمار": ("stats", ""),
            "راهنما": ("help", ""),
            "تنظیمات": ("set", ""),
            "گروه": ("گروه", ""),
            "گروه‌ها": ("گروه", ""),
            "گروه ها": ("گروه", ""),
            "افزودن گروه": ("افزودن گروه", ""),
            "ثبت گروه": ("افزودن گروه", ""),
            "حذف گروه": ("حذف گروه", ""),
            "حذف همه گروه‌ها": ("حذف همه گروه‌ها", ""),
            "حذف همه گروه ها": ("حذف همه گروه‌ها", ""),
            "پاک کردن گروه": ("حذف گروه", ""),
            "پاکسازی": ("clear", ""),
            "تلاش دوباره": ("retry", ""),
            "بازنشانی": ("reset", ""),
            "زنده": ("ping", ""),
            "فعالیت": ("active", ""),
            "استراحت": ("rest", ""),
            "فاصله": ("gap", ""),
            "سکوت": ("quiet", ""),
            "حالت": ("mode", ""),
            "فعالیت ویژه": ("vactive", ""),
            "استراحت ویژه": ("vrest", ""),
            "سقف ویژه": ("vlimit", ""),
            "فاصله ویژه": ("vgap", ""),
            "سکوت ویژه": ("vquiet", ""),
            "حالت ویژه": ("vmode", ""),
            "بررسی فعال": ("بررسی", "فعال"),
            "بررسی خاموش": ("بررسی", "خاموش"),
            "هوش مصنوعی بررسی فعال": ("بررسی", "فعال"),
            "هوش مصنوعی بررسی خاموش": ("بررسی", "خاموش"),
            "تبادل روشن": ("ex", "on"),
            "تبادل خاموش": ("ex", "off"),
            "لیست تبادل": ("ex", "list"),
            "توقف": ("pause", ""),
            "ادامه": ("resume", ""),
            "کانال": ("کانال", ""),
            "تنظیم کانال": ("تنظیم‌کانال", ""),
            "افزودن": ("افزودن", ""),
            "تغییر": ("تغییر", ""),
            "حذف": ("حذف", "کانال"),
            "افزودن کانال": ("افزودن‌کانال", ""),
            "تغییر کانال": ("تغییر کانال", ""),
            "حذف کانال": ("حذف", "کانال"),
            "پاک کردن کانال": ("پاک کردن کانال", ""),
            "لیست کانال": ("لیست‌کانال", ""),
            "متن": ("متن", ""),
            "تنظیم متن": ("تنظیم‌متن", ""),
            "سقف ارسال": ("سقف‌ارسال", ""),
            "چرخه": ("چرخه", ""),
            "نوسان": ("نوسان", ""),
            "متن تبادل": ("متن‌تبادل", ""),
            "متن‌های تبادل": ("متن تبادل", ""),
            "متن های تبادل": ("متن تبادل", ""),
            "کانال‌ها": ("کانال‌ها", ""),
            "کانال ها": ("کانال‌ها", ""),
            "کانال ویژه": ("کانال ویژه", ""),
            "تبادل متن": ("ex", "msg"),
            "تبادل تنظیمات": ("ex", "تنظیمات"),
            "تنظیمات تبادل": ("ex", "تنظیمات"),
            "تبادل راهنما": ("ex", "راهنما"),
            "تبادل دستورها": ("ex", "دستورها"),
            "تبادل تشخیص": ("ex", "تشخیص"),
            "تبادل پیام": ("ex", "come"),
            "تبادل متن موفق": ("متن‌موفق", ""),
            "تبادل متن ناموفق": ("متن‌ناموفق", ""),
            "تبادل متن انتظار": ("متن‌انتظار", ""),
            "تبادل متن بدون لینک": ("متن‌بدون‌لینک", ""),
            "تبادل پیام موفق": ("متن‌موفق", ""),
            "تبادل پیام ناموفق": ("متن‌ناموفق", ""),
            "تبادل پیام انتظار": ("متن‌انتظار", ""),
            "تبادل پیام بدون لینک": ("متن‌بدون‌لینک", ""),
            "تبادل پیام بیا": ("ex", "come"),
            "تبادل زمان بیا": ("ex", "cometime"),
            "تبادل گروه‌ها": ("ex", "groups"),
            "تبادل گروه ها": ("ex", "groups"),
            "هوش": ("ai", ""),
            "ریسک": ("risk", ""),
            "امنیت": ("risk", ""),
            "محافظ": ("risk", ""),
            "حفاظت": ("risk", ""),
        }
        if low in bare:
            cmd, arg = bare[low]
            try:
                out = eng.cmd(cmd, arg, None)
            except Exception as e:
                out = f"⚠️ {type(e).__name__}: {e}"
            await _say(out, event)
            return
        # جمله‌های فارسی بدون نقطه
        for pref, cmap in (
            ("متن موفق ", ("متن‌موفق",)),
            ("متن ناموفق ", ("متن‌ناموفق",)),
            ("متن انتظار ", ("متن‌انتظار",)),
            ("متن بدون لینک ", ("متن‌بدون‌لینک",)),
            ("متن‌موفق ", ("متن‌موفق",)),
            ("متن‌ناموفق ", ("متن‌ناموفق",)),
            ("متن‌انتظار ", ("متن‌انتظار",)),
            ("متن‌بدون‌لینک ", ("متن‌بدون‌لینک",)),
            ("کانال ویژه ", ("setvip",)),
            ("کانال‌ویژه ", ("setvip",)),
            ("کانال ", ("setch",)),
            ("ارسال فوری ", ("now",)),
            ("ارسال ", ("post",)),
            ("ویژه ", ("vip",)),
            ("سقف ویژه ", ("vlimit",)),
            ("سقف‌ویژه ", ("vlimit",)),
            ("سقف ", ("limit",)),
            ("فعالیت ویژه ", ("vactive",)),
            ("فعالیت‌ویژه ", ("vactive",)),
            ("فعالیت ", ("active",)),
            ("استراحت ویژه ", ("vrest",)),
            ("استراحت‌ویژه ", ("vrest",)),
            ("استراحت ", ("rest",)),
            ("فاصله ویژه ", ("vgap",)),
            ("نوسان‌ویژه ", ("vgap",)),
            ("فاصله ", ("gap",)),
            ("سکوت ویژه ", ("vquiet",)),
            ("سکوت ", ("quiet",)),
            ("تنظیم تبادل گزارش ", ("ex",)),
            ("تنظیم‌تبادل گزارش ", ("ex",)),
            ("تنظیم گزارش ", ("ex",)),
            ("تنظیم‌گزارش ", ("ex",)),
            ("گروه ", ("گروه",)),
            ("گروه‌ها ", ("گروه",)),
            ("گروه ها ", ("گروه",)),
            ("افزودن گروه ", ("گروه",)),
            ("حذف گروه ", ("حذف گروه",)),
            ("حذف ", ("del",)),
            ("تبادل ", ("ex",)),
            ("ریسک ", ("risk",)),
            ("امنیت ", ("risk",)),
            ("محافظ ", ("risk",)),
        ):
            if raw.startswith(pref) or low.startswith(pref):
                cmd = cmap[0]
                arg = raw[len(pref):].strip()
                if pref in ("تنظیم تبادل گزارش ", "تنظیم‌تبادل گزارش ",
                             "تنظیم گزارش ", "تنظیم‌گزارش "):
                    # تنظیم‌ها با فرم کوتاه به یک زیر‌دستور قطعی تبدیل شوند.
                    action = re.sub(r"\s+", " ", arg.replace("\u200c", " ")).strip()
                    if action in ("روشن", "لحظه‌ای", "لحظه ای"):
                        arg = "report_live"
                    elif action == "خلاصه":
                        arg = "report_summary"
                    elif action in ("خاموش", "off"):
                        arg = "report_off"
                    elif action.startswith("هر "):
                        arg = "report_every " + action[4:].strip()
                    elif action.startswith(("خلاصه الان", "خلاصه همین الان")):
                        arg = "report_now"
                    else:
                        arg = "report"
                try:
                    out = eng.cmd(cmd, arg, None)
                except Exception as e:
                    out = f"⚠️ {type(e).__name__}: {e}"
                await _say(out, event)
                return
        m = pattern.match(raw)
        if not m:
            return
        cmd, arg = m.group(1), (m.group(2) or "").strip()
        reply_text = None
        try:
            r = await event.get_reply_message()
            if r and r.raw_text:
                reply_text = r.raw_text
        except Exception:
            pass

        # ---- هوش مصنوعی ----
        if cmd.lower() in ("id", "آیدی"):
            try:
                chat = await event.get_chat()
                cid = getattr(chat, "id", None)
                _track_own(await event.reply(f"🆔 آیدی این چت: `{cid}`"))
            except Exception as e:
                _track_own(await event.reply(f"خطا: {type(e).__name__}"))
            return

        if cmd.lower() in ("ai", "هوش"):
            out = await handle_ai(event, arg, reply_text)
            await _say(out, event)
            return

        try:
            out = eng.cmd(cmd, arg, reply_text)
        except Exception as e:
            out = f"⚠️ {type(e).__name__}: {e}"
            traceback.print_exc()
        await _say(out, event)

    async def deliver(item):
        tgt, text, qid = item["target"], item["text"], item["id"]
        tier = item.get("tier") or "standard"
        if DRY_RUN:
            eng.db.mark_sent(qid, None)
            eng.thr[tier].record()
            eng.log("info", "dry_run_send", f"#{qid} → {tgt}")
            return
        try:
            sent = await client.send_message(tgt, text, link_preview=False)
            mid = getattr(sent, "id", None)
            eng.db.mark_sent(qid, mid)
            eng.thr[tier].record()
            eng.log("ok", "sent", f"#{qid} → {tgt}")
        except FloodWaitError as e:
            w = getattr(e, "seconds", 60)
            eng.thr[tier].penalize(w)
            eng.db.mark_failed(qid, f"FloodWait {w}s", retry_at=time.time() + w + 2)
            eng.log("warn", "flood", f"#{qid}: {w}s")
        except (ChatWriteForbiddenError, ChannelPrivateError,
                UsernameNotOccupiedError) as e:
            eng.db.mark_failed(qid, type(e).__name__)
            eng.log("error", "send", f"#{qid}: {type(e).__name__}")
            await note(f"❌ ارسال #{qid} نشد: {type(e).__name__}")
        except SlowModeWaitError as e:
            w = getattr(e, "seconds", 30)
            eng.db.mark_failed(qid, f"SlowMode {w}s", retry_at=time.time() + w + 1)
        except Exception as e:
            eng.db.mark_failed(qid, f"{type(e).__name__}: {e}",
                               retry_at=time.time() + 60)
            eng.log("error", "send", f"#{qid}: {e}")

    # ══════════════════════════════════════════════════
    #  تبادل دوطرفه
    # ══════════════════════════════════════════════════
    async def peer_in_my_channel(user_id, rec_id=None, queue=True):
        """عضو کانال عادی یا VIP هست؟ True / False / None(نامشخص)
        همه‌ی درخواست‌ها از CheckGate رد می‌شوند تا فلود «الکی» نسازد.
        از صفِ تک‌عملکردی (ex_cd) هم رد می‌شوند: در هر لحظه فقط یک عملکردِ
        تبادل اجرا می‌شود و بین دو عملکرد، فاصله‌ی تنظیم‌شده (پیش‌فرض
        ۱۵–۲۰ ثانیه) رعایت می‌شود. rec_id برای خنک‌کننده‌ی همان رکورد است
        تا رکوردی که همین الان چک شده، دوباره چک نشود."""
        if not user_id:
            return None
        chans = []
        for t in ("standard", "vip"):
            ch = (eng.st.prof(t)["channel"] or "").strip()
            if ch and ch not in chans:
                chans.append(ch)
        if not chans:
            return None
        saw_false = False
        for ch in chans:
            async def _one_req():
                # درون قفل: درخواستِ منتظر صف باید FloodWait جدید را هم ببیند.
                if time.time() < ex_cd.blocked_until:
                    return None
                w = check_gate.wait()
                if w > 45:
                    return None
                if w > 0:
                    await asyncio.sleep(w)
                check_gate.record()
                try:
                    result = await client(GetParticipantRequest(ch, user_id))
                except FloodWaitError as e:
                    w = getattr(e, "seconds", 60)
                    check_gate.penalize(w)
                    raise
                participant = getattr(result, "participant", None)
                if participant is None:
                    return None
                if (type(participant).__name__ == "ChannelParticipantLeft"
                        or getattr(participant, "left", False)):
                    raise UserNotParticipantError(request=None)
                return True

            try:
                # یک «عملکرد» در صف سراسری: تا عملکرد قبلی تمام نشده و
                # فاصله‌ی تنظیم‌شده نگذشته باشد، درخواستِ بعدی زده نمی‌شود.
                # queue=False فقط برای «چک دومِ تأییدی» همان عضویت است: آنجا
                # خودِ فاصله‌ی چک (۱۵–۳۰ ثانیه) بین دو درخواست صبر شده، پس
                # یک‌بار فاصله‌ی صفِ اضافه فقط توان را نصف می‌کرد.
                if queue:
                    out = await ex_cd.action("check", rec_id, _one_req)
                else:
                    # ادامه‌ی همان عملکردِ چک: فقط قفل سراسری را می‌گیرد (تا
                    # با عملکردِ دیگری هم‌پوشانی نکند) ولی فاصله‌ی صف را
                    # دوباره صبر نمی‌کند — آن فاصله را خودش همین الان داده.
                    async with ex_cd.lock:
                        out = await _one_req()
                        ex_cd.note_done(rec_id)
                    return out
                return out
            except UserNotParticipantError:
                saw_false = True
            except FloodWaitError as e:
                w = getattr(e, "seconds", 60)
                # فیکس: فلودِ «بررسی عضویت» ربطی به ظرفیت ارسال ندارد؛
                # قبلاً تروتیل ارسال هم جریمه می‌شد و کل ربات فریز می‌شد
                # (نه پیام می‌رفت نه لفت انجام می‌شد). فقط گیت چک می‌ایستد.
                eng.db.log("warn", "ex_check_flood", f"{ch}: {w}s")
                # فلودِ چک یعنی کل مسیر بررسی دارد قیچی می‌شود — به
                # صاحب‌حساب بگو (حداکثر هر ۱۰ دقیقه یک‌بار).
                nowf = int(time.time())
                if w >= 60 and nowf - int(_warn_check_flood["last"] or 0) > 600:
                    _warn_check_flood["last"] = nowf
                    await note(f"⏳ FloodWait {secs(w)} روی بررسی عضویت — "
                               "چک‌ها تا پایانش متوقف می‌شوند و بعد خودکار "
                               "ادامه می‌دهند. اگر زیاد تکرار شد، «تبادل بررسی» "
                               "را بلندتر بگذار یا تعداد تبادل‌های فعال را کم کن.")
                return None
            except Exception as e:
                eng.log("warn", "ex_check", f"{ch}: {type(e).__name__}: {e}")
                return None
        return False if saw_false else None

    async def confirm_peer_membership(user_id, fast=False, rec_id=None,
                                      confirm=True):
        """عضویت را حداقل دوبار تأیید می‌کند تا منفی کاذب ندهد.
        اگر درخواست اول False باشد، یک بار دیگر بعد از فاصله تصادفی
        تنظیم‌شده بررسی می‌شود؛ هیچ پیام اضافه‌ای در این فاصله ارسال نمی‌شود.
        fast=True برای نوبت‌های یادآوری است: چکِ دوم فقط چند ثانیه است تا
        فاصله‌ی چک عضویت روی بازه‌ی تنظیم‌شده‌ی کاربر جمع نشود — فاصله‌ی
        واقعی بین دو پیام «نیومدی» همان بازه‌ی تنظیم‌شده می‌ماند.

        rec_id که داده شود، هر دو درخواست از صفِ تک‌عملکردی رد می‌شوند و
        خنک‌کننده‌ی همان رکورد ثبت می‌شود: یعنی رکوردی که تازه جوین/چک
        شده، تا ۱۵–۲۰ ثانیه (پیش‌فرض) دوباره چک نمی‌شود و بلافاصله بعد
        از چک هم پیامی نمی‌رود.
        """
        first = await peer_in_my_channel(user_id, rec_id)
        if first is not False or not confirm:
            return first
        # گاهی انتشار عضویت در API تلگرام چند ثانیه طول می‌کشد.
        # این صبرِ بی‌صدا بیرونِ قفل سراسری است تا بقیه‌ی رکوردها معطل نمانند.
        await asyncio.sleep(2 if fast else membership_check_delay())
        # چک دوم در ادامه‌ی همان عملکردِ چک است (نه یک عملکردِ تازه)، پس
        # دوباره پشتِ فاصله‌ی صف نمی‌ایستد؛ فقط خنک‌کننده‌ی رکورد تازه می‌شود.
        return await peer_in_my_channel(user_id, rec_id, queue=False)

    def remember_channel(rec_id, ent):
        """آیدی و access_hash کانالِ جوین‌شده را روی رکورد ذخیره می‌کند.

        چرا لازم است: لفت از کانال طرف قبلاً فقط با «لینک» انجام می‌شد و
        برای لینک‌های خصوصی (t.me/+…) همان لینک باید دوباره حل شود؛ اگر
        طرف لینک را باطل/منقضی کرده باشد، CheckChatInvite خطای
        InviteHashExpired می‌دهد و لفت هیچ‌وقت انجام نمی‌شود (همان باگی که
        گزارش شد). با ذخیره‌ی آیدیِ کانال در لحظه‌ی جوین، لفت دیگر به
        لینک وابسته نیست."""
        if not rec_id or ent is None:
            return
        try:
            cid = getattr(ent, "id", None)
            chash = getattr(ent, "access_hash", None)
            if not cid:
                return
            eng.db.ex_set(int(rec_id), chat_id=int(cid),
                          chat_hash=(int(chash) if chash is not None else None))
        except Exception as e:
            try:
                eng.log("warn", "ex_identity", f"#{rec_id}: {type(e).__name__}: {e}")
            except Exception:
                pass

    def block_joins_for_capacity(reason, seconds=3600):
        x = eng.ex_cfg()
        until = int(time.time()) + max(1, int(seconds or 3600))
        x["_capacity_join_blocked_until"] = until
        eng.st.save()
        eng.log("warn", "ex_capacity_block", f"تا {until}: {reason}")

    async def join_link(link, rec_id=None):
        """جوین به کانال. برمی‌گرداند (موفق, پیام, عنوان)

        rec_id که داده شود، جوین در صفِ تک‌عملکردی اجرا می‌شود و
        خنک‌کننده‌ی همان رکورد ثبت می‌شود؛ یعنی چکِ عضویتِ بعد از جوین
        زودتر از فاصله‌ی تنظیم‌شده (پیش‌فرض ۱۵–۲۰ ثانیه) انجام نمی‌شود.
        همچنین آیدیِ کانال برای لفت‌های بعدی ذخیره می‌شود."""
        if DRY_RUN:
            return True, "joined", "DRY_RUN"

        joined_ent = {"e": None}

        async def _do_join():
            if is_invite(link):
                upd = await client(ImportChatInviteRequest(invite_hash(link)))
                title = ""
                chats = getattr(upd, "chats", None)
                if chats:
                    joined_ent["e"] = chats[0]
                    title = getattr(chats[0], "title", "")
                return True, "joined", title
            ent = await client.get_entity(link)
            await client(JoinChannelRequest(ent))
            joined_ent["e"] = ent
            return True, "joined", getattr(ent, "title", "")

        try:
            # جوین یک «عملکرد» است: تا عملکرد قبلی تمام نشده و فاصله‌ی
            # تنظیم‌شده (پیش‌فرض ۱۵–۲۰ ثانیه) نگذشته باشد، اجرا نمی‌شود.
            out = await ex_cd.action("join", rec_id, _do_join)
            remember_channel(rec_id, joined_ent["e"])
            return out

        except UserAlreadyParticipantError:
            return True, "already", ""
        except InviteRequestSentError:
            return False, "درخواست عضویت فرستاده شد — منتظر تأیید ادمین", ""
        except (InviteHashExpiredError, InviteHashInvalidError):
            return False, "لینک منقضی یا نامعتبر است", ""
        except UsernameNotOccupiedError:
            return False, "این یوزرنیم وجود ندارد", ""
        except ChannelPrivateError:
            return False, "کانال خصوصی است یا بن شده‌ای", ""
        except ChannelsTooMuchError:
            # نکته‌ی معماری: خودِ پاکسازی این‌جا اجرا نمی‌شود چون join_link در
            # worker داخل wait_for(180s) صدا زده می‌شود و یک دور ۳۰تایی با
            # فاصله‌ی ۱۵–۲۰ ثانیه‌ای چند دقیقه طول می‌کشد. فقط فلگ می‌زنیم؛
            # exchange_worker در ابتدای حلقه‌ی بعد، بیرون از آن timeout،
            # دور پاکسازی را کامل اجرا می‌کند و رکورد approved خودکار دوباره
            # به صف جوین برمی‌گردد (هندلر شکست جوین، رکورد سقف را failed نمی‌کند).
            cfg = eng.ex_cfg()
            if not cfg.get("auto_leave_completed_on_limit", True):
                block_joins_for_capacity("پاکسازی خودکار خاموش است و سقف عضویت پر شد")
                return (False,
                        "تو حداکثر تعداد کانال ممکن هستی — یک عضویت را دستی آزاد کن، "
                        "بعد `تبادل لفت خودکار ریست` را بفرست.", "")
            last_clean = int(cfg.get("_last_capacity_cleanup_at", 0) or 0)
            if last_clean and int(time.time()) - last_clean < CAPACITY_REBLOCK_SEC:
                # دور پاکسازی اخیر جا آزاد کرده ولی تلگرام هنوز پر می‌گوید
                # (ثبت آزادشدن slot کمی تأخیر دارد)؛ به‌جای لفت پشت‌سرهم،
                # چند دقیقه مکث کن تا سمت سرور جاها واقعاً آزاد شوند.
                block_joins_for_capacity(
                    "بعد از دور پاکسازی، تلگرام هنوز سقف را پر اعلام می‌کند",
                    seconds=CAPACITY_REBLOCK_SEC)
                return (False,
                        "تلگرام هنوز خطای حداکثر تعداد کانال (ChannelsTooMuch) می‌دهد؛ "
                        "پاکسازی اخیر جا آزاد کرده ولی ثبتش سمت تلگرام تأخیر دارد. "
                        f"{secs(CAPACITY_REBLOCK_SEC)} صبر می‌کنم و بعد خودکار دوباره "
                        "تلاش می‌کنم. اگر باز هم تکرار شد، چند کانالِ غیرجفج را دستی لفت بده.",
                        "")
            cfg["_capacity_cleanup_pending"] = True
            eng.st.save()
            eng.log("warn", "ex_capacity_trigger",
                    "ChannelsTooMuch؛ دور پاکسازی در صف worker قرار گرفت")
            return (False,
                    "تلگرام سقف را پر اعلام کرد (حداکثر تعداد کانال / ChannelsTooMuch)؛ "
                    "دور پاکسازی کانال‌های جفج‌زده شروع می‌شود و بعدش جوینِ معلق "
                    "خودکار دوباره تلاش می‌شود.",
                    "")
        except FloodWaitError as e:
            w = getattr(e, "seconds", 60)
            eng.join_thr.penalize(w)
            eng.db.log("warn", "ex_flood", f"join {link}: {w}s")
            try:
                eng.adaptive_on_flood(w)
            except Exception:
                pass
            if w >= 300:
                # حساب در جریمه است؛ چک‌های عضویت بار اضافه‌اند — گیت چک هم آرام بگیرد
                try:
                    check_gate.penalize(min(w, 1800))
                except Exception:
                    pass
            return False, f"FloodWait {w}s", ""
        except Exception as e:
            return False, f"{type(e).__name__}: {e}", ""

    async def leave_link(link, rec_id=None):
        """لفت از کانال طرف — یک «عملکرد» در صفِ تک‌عملکردی.

        با rec_id، لفت بلافاصله بعد از چک/پیام اجرا نمی‌شود: اول
        خنک‌کننده‌ی رکورد (پیش‌فرض ۱۵–۲۰ ثانیه) تمام می‌شود. این همان
        باگِ «چک کرد، درجا گفت نیومدی، درجا لفت داد» را می‌بندد.

        ترتیبِ پیدا کردن کانال برای لفت:
          ۱) آیدی/access_hash ذخیره‌شده در لحظه‌ی جوین — دیگر به لینک
             طرف وابسته نیست؛
          ۲) خودِ لینک/یوزرنیم طرف؛
          ۳) اگر لینکِ خصوصی منقضی شده باشد: کانالی با همان عنوانِ
             ذخیره‌شده که قبلاً جوینش کرده‌ایم (فقط تطبیقِ یکتا).
        """
        if DRY_RUN:
            return True, ""

        rec = None
        if rec_id:
            try:
                rec = eng.db.ex_get(int(rec_id))
            except Exception:
                rec = None

        def input_from_record():
            # بدون access_hash هم InputChannel معتبر نیست (CHANNEL_INVALID)؛
            # در آن حالت برمی‌گردیم به مسیر لینک/عنوان.
            if not rec or not rec.get("chat_id") or not rec.get("chat_hash"):
                return None
            return _input_channel(rec.get("chat_id"), rec.get("chat_hash"))

        async def resolve_by_title():
            """آخرین چاره: کانالی که با همین عنوان قبلاً جوینش کرده‌ایم.
            فقط اگر تطبیقِ یکتا باشد (عنوان تکراری = هیچ‌کاری نکن)."""
            title = ((rec or {}).get("channel_title") or "").strip()
            if not title:
                return None
            mine = {(eng.st.prof(t)["channel"] or "").lstrip("@").lower()
                    for t in ("standard", "vip")}
            mine.discard("")
            found = None
            try:
                async for d in client.iter_dialogs(limit=300):
                    e = d.entity
                    if (getattr(e, "title", "") or "").strip() != title:
                        continue
                    if not hasattr(e, "access_hash"):
                        continue
                    if (getattr(e, "username", None) or "").lower() in mine:
                        continue
                    if found is not None:
                        return None      # عنوان تکراری → لفتِ اشتباه نده
                    found = e
            except Exception as e:
                eng.log("warn", "ex_leave_scan", f"{type(e).__name__}: {e}")
                return None
            return found

        async def _do_leave():
            ent = input_from_record()
            if ent is None:
                try:
                    ent = await client.get_entity(link)
                except (InviteHashExpiredError, InviteHashInvalidError):
                    # لینکِ طرف باطل/منقضی شده — با عنوانِ ذخیره‌شده امتحان کن
                    ent = await resolve_by_title()
                    if ent is None:
                        eng.log("warn", "ex_leave_expired", str(link))
                        raise
            await client(LeaveChannelRequest(ent))
            return True, ""

        try:
            return await ex_cd.action("leave", rec_id, _do_leave)
        except UserNotParticipantError:
            # از قبل عضو نبودیم → لفت لازم نیست؛ این خطا نیست
            return True, ""
        except ChannelPrivateError:
            # کانال دیگر برای ما در دسترس نیست (خصوصی/بن) → عملاً عضو نیستیم
            eng.log("warn", "ex_leave_private", str(link))
            return True, ""
        except (InviteHashExpiredError, InviteHashInvalidError):
            return False, ("لینک طرف منقضی/باطل شده و آیدیِ کانال هم ذخیره "
                           "نشده بود — لفت نشد؛ یک لینک تازه از طرف بگیر یا "
                           "دستی از کانال خارج شو")
        except FloodWaitError as e:
            w = getattr(e, "seconds", 60)
            eng.join_thr.penalize(w)
            eng.db.log("warn", "ex_flood", f"leave {link}: {w}s")
            try:
                eng.adaptive_on_flood(w)
            except Exception:
                pass
            if w >= 300:
                try:
                    check_gate.penalize(min(w, 1800))
                except Exception:
                    pass
            return False, f"FloodWait {w}s"
        except Exception as e:
            return False, f"{type(e).__name__}: {e}"

    async def cleanup_capacity_for_slots():
        """فرایند پاکسازی سقف: یک دور، تا سقف تنظیم‌شده کانالِ جفج‌زده لفت می‌زند.

        وقتی تلگرام ChannelsTooMuch بدهد، exchange_worker با فلگ
        ``_capacity_cleanup_pending`` این تابع را بیرون از timeout جوین
        صدا می‌زند. فقط رکوردهای تبادلِ کامل‌شده‌ی امن (همان قواعد
        select_capacity_leave_candidate) انتخاب می‌شوند و کانال خود کاربر
        هرگز لفت نمی‌شود؛ رکوردِ در حال جوین هم چون هنوز joined نیست
        اصلاً وارد استخر نمی‌شود. لفت‌ها از صف تک‌عملکردی رد می‌شوند پس
        فاصله‌ی ۱۵–۲۰ ثانیه‌ای به‌صورت خودکار رعایت و ریسک فلود حداقل
        است. اگر وسط دور FloodWait بیاید همان‌جا متوقف می‌شود (جریمه در
        join_thr ثبت شده) و دور بعد از رکورد بعدی ادامه می‌دهد. در پایان
        فقط یک پیام خلاصه می‌رود، نه پیام per لفت.
        برمی‌گرداند (تعداد لفت‌شده، دلیل توقف زودهنگام یا None).
        """
        cfg = eng.ex_cfg()
        target = clamp_capacity_batch(
            cfg.get("capacity_cleanup_batch", CAPACITY_CLEANUP_BATCH_DEFAULT))
        joined = eng.db.ex_list("joined", 1000)
        own_channels = [eng.st.prof(t).get("channel")
                        for t in ("standard", "vip")]
        candidates = select_capacity_leave_batch(
            joined, own_channels=own_channels, limit=target)
        if not candidates:
            eng.log("warn", "ex_capacity_no_candidate",
                    "هیچ تبادلِ کامل و قابل‌تشخیص برای آزادسازی ظرفیت نبود")
            try:
                await note(format_capacity_cleanup_note([], target))
            except Exception:
                pass
            return 0, "هیچ تبادلِ کامل‌شدهٔ امنی برای لفت پیدا نشد."

        left_links = []
        stopped = None
        left_at = int(time.time())
        had_outbound = False
        round_started = time.time()
        for cand in candidates:
            # سقفِ زمانی: دورِ طولانی صفِ تبادل را در انحصار می‌گیرد و پاسخ
            # به پیوی عقب می‌افتد؛ بقیه در دور بعدِ حلقه ادامه می‌یابد.
            if capacity_round_exhausted(round_started, time.time()):
                stopped = (f"سقفِ زمانیِ دور پاکسازی ({secs(CAPACITY_CLEANUP_MAX_SEC)})؛ "
                           "بقیه در دور بعد ادامه می‌یابد")
                cfg["_capacity_cleanup_pending"] = True
                try:
                    eng.st.save()
                except Exception:
                    pass
                break
            ok, err = await leave_link(cand.get("link"), cand.get("id"))
            if not ok:
                eng.log("warn", "ex_capacity_leave_fail",
                        f"#{cand.get('id')} {cand.get('link')}: {err}")
                if isinstance(err, str) and "FloodWait" in err:
                    stopped = (f"محدودیت تلگرام ({err})؛ دور پاکسازی تا "
                               "کاهش محدودیت متوقف شد")
                    break
                # لینک منقضی/خطای موقت روی این رکورد: ردش کن و سراغ بعدی برو
                continue
            eng.db.ex_set(cand["id"], status="left", last_check=left_at,
                          next_check=0, next_reminder=0,
                          leave_fail=0, leave_blocked_until=0,
                          note="لفت خودکار دسته‌ای برای آزادکردن ظرفیت سقف")
            left_links.append(cand.get("link") or f"#{cand.get('id')}")
            had_outbound = had_outbound or cand.get("direction") == "out"
            eng.log("info", "ex_left",
                    f"ظرفیت تلگرام؛ پاکسازی دسته‌ای — "
                    f"#{cand.get('id')} {cand.get('link')}")
        eng.log("info", "ex_capacity_cleanup",
                f"دور پاکسازی: {len(left_links)} لفت از هدف {target}"
                + (f" — توقف: {stopped}" if stopped else ""))
        if had_outbound:
            eng.ex_cfg()["_scan_now"] = True
        try:
            await note(format_capacity_cleanup_note(left_links, target, stopped))
        except Exception:
            pass
        if not left_links:
            return 0, (stopped or "لفت هیچ‌کدام از کاندیدها انجام نشد.")
        return len(left_links), stopped

    async def reply_joined(rec):
        """متن «جوین شدم» کاربر را روی پیام خود طرف ریپلای می‌کند.
        بدون لینک، بدون آیدی، بدون منشن — فقط همان متنی که تعیین کرده."""
        x = eng.ex_cfg()
        if not x["reply"] or not rec:
            return False
        if rec.get("replied"):
            return False
        outgoing = rec.get("direction") == "out"
        key = "msg_come" if outgoing else "msg_ok"
        body = eng.ex_render(key, rec.get("peer_name") or "", rec["link"])
        if not body and outgoing:
            # سازگاری با تنظیمات قدیمی که فقط msgfirst داشتند.
            body = eng.ex_render("msg_first", rec.get("peer_name") or "", rec["link"])
        if not body and outgoing:
            # اگر فقط «پیام موفق» ثبت شده باشد، پیش‌قدم هم همان متن را می‌گوید.
            body = eng.ex_render("msg_ok", rec.get("peer_name") or "", rec["link"])
        if not body:
            return False
        if outgoing:
            # باگِ «پیش‌قدم: زیرِ متن، کانال نیست»: در پیامِ «جوین شدم»ِ
            # پیش‌قدم (خودت اول جوین شدی) لینکِ کانالِ خودت زیرِ متن
            # می‌آید — چون طرف فقط از همین پیام می‌فهمد کدام کانال را
            # جوین شود و تبادل کامل شود. تا قبلش این خط فقط برای
            # «نیومدی» اضافه می‌شد و پیامِ پیش‌قدم بدون آدرس می‌رفت.
            # اگر کاربر خودش {mychannel} یا آدرس را داخل متن گذاشته
            # باشد، دوباره اضافه نمی‌شود.
            body = eng.ex_append_my_channel(body)
        chat, mid = rec.get("src_chat"), rec.get("src_msg")
        if not chat or not mid:
            return False
        if outgoing:
            delay = come_delay_seconds()
        else:
            delay = response_delay_seconds()
        if delay:
            # تأخیر انسانی بیرونِ صف است تا بقیه‌ی عملکردها معطل نمانند؛
            # فقط خودِ ارسال داخل صف تک‌عملکردی می‌رود.
            await asyncio.sleep(delay)

        async def _send_reply():
            if DRY_RUN:
                return True
            await client.send_message(chat, body, reply_to=mid, link_preview=False)
            return True

        try:
            # پیام «جوین شدم» هم یک عملکرد است: درجا بعد از جوین یا بعد از
            # یک «نیومدی» نمی‌رود؛ اول نوبتِ صف و فاصله‌ی تنظیم‌شده.
            await ex_cd.action("reply_joined", rec.get("id"), _send_reply)
            eng.db.ex_set(rec["id"], replied=1)
            eng.log("ok", "ex_reply" if not DRY_RUN else "dry_run_reply",
                    f"#{rec['id']}")
            return True
        except Exception as e:
            eng.log("warn", "ex_reply", f"#{rec['id']}: {type(e).__name__}: {e}")
            return False

    def joins_left_today():
        # عمداً هیچ سقف روزانه‌ای برای Join وجود ندارد.
        return 999999999

    def op_gap_seconds():
        """فاصله‌ی تصادفی بین دو «عملکرد» تبادل (پیش‌فرض ۱۵–۲۰ ثانیه).

        هر عملکرد (چک عضویت، جوین، لفت، پیام «نیومدی»، پیام «جوین شدم»)
        که تمام شود، این‌قدر صبر می‌شود تا عملکردِ بعدی اجرا شود. این
        کفِ همه‌ی فاصله‌هاست: هیچ دو عملکردی پشت‌سرهم (درجا) نمی‌روند.
        """
        x = eng.ex_cfg()
        lo = max(0, int(x.get("op_gap_min_sec", 15) or 0))
        hi = max(lo, int(x.get("op_gap_max_sec", 20) or lo))
        if lo == hi:
            return lo
        return random.randint(lo, hi)

    def next_action_after(rec, base=None):
        """زمانِ مجازِ عملکردِ بعدی روی این رکورد.

        حداکثرِ «زمانِ پایه» و «پایانِ خنک‌کننده‌ی رکورد» را برمی‌گرداند؛
        یعنی رکوردی که همین الان جوین/چک/پیام گرفته، عملکردِ بعدی‌اش
        زودتر از فاصله‌ی تنظیم‌شده (پیش‌فرض ۱۵–۲۰ ثانیه) اجرا نمی‌شود.
        """
        now = int(time.time())
        try:
            base = now if base is None else int(max(now, int(base or 0)))
        except (TypeError, ValueError):
            base = now
        gap = op_gap_seconds()
        since = ex_cd.since_done((rec or {}).get("id"), now)
        if since is None:
            return base
        return int(max(base, now + max(0, int(gap - since))))

    def unk_fallback(rec, extra=1):
        """خطا/محدودیت API هیچ‌وقت مدرکِ عدم عضویت نیست (حتی تنظیم قدیمی)."""
        return False

    def reminder_delay():
        """فاصله‌ی تصادفی بین دو پیام «نیومدی»؛ پیش‌فرض ۲۰ تا ۴۰ ثانیه تصادفی.
        هر بار که بخواهد بگوید بین همون عدد تصادفی که تنظیم کردی (پیش‌فرض ۲۰–۴۰)
        است، دوبار می‌گوید بعد لفت.
        دو پیام عضو‌نشده هرگز پشت سر هم فرستاده نمی‌شوند: کفِ فاصله همان
        فاصله‌ی بین عملکرد‌هاست (پیش‌فرض ۱۵ ثانیه)، حتی اگر بازه‌ی یادآوری
        کوتاه‌تر تنظیم شده باشد."""
        x = eng.ex_cfg()
        # اگر کاربر فقط چک را تنظیم کرده، یادآوری هم از همان بازه استفاده کند
        floor = max(0, int(x.get("op_gap_min_sec", 15) or 0))
        lo = max(1, int(x.get("reminder_min_sec", x.get("check_min_sec", 20)) or 20))
        hi = max(lo, int(x.get("reminder_max_sec", x.get("check_max_sec", 40)) or 40))
        lo = max(lo, floor)
        hi = max(hi, lo)
        return random.randint(lo, hi)

    def membership_check_delay():
        """فاصله‌ی بی‌صدای بررسی عضویت؛ هر بار دوباره تصادفی انتخاب می‌شود.
        کفِ آن فاصله‌ی بین عملکرد‌هاست (پیش‌فرض ۱۵ ثانیه) تا چکِ عضویت هرگز
        درجا بعد از جوین اجرا نشود — اول صبر، بعد چک."""
        x = eng.ex_cfg()
        floor = max(0, int(x.get("op_gap_min_sec", 15) or 0))
        lo = max(1, int(x.get("check_min_sec", 15) or 15))
        hi = max(lo, int(x.get("check_max_sec", 30) or 30))
        lo = max(lo, floor)
        hi = max(hi, lo)
        return random.randint(lo, hi)

    def watch_delay_seconds(rec):
        """فاصله‌ی چک نگهبانی بر اساس سنِ رکورد — پلکانی بلند می‌شود.
        قبلاً هر رکورد جوین‌شده «تا ابد» هر ۱۰–۲۰ ثانیه چک می‌شد؛ با زیادشدن
        رکوردها بارِ GetParticipant آن‌قدر بالا می‌رفت که اکانت هر ۲۰–۳۰
        دقیقه FloodWait می‌خورد. حالا:
          نیم‌ساعت اول: بازه‌ی تنظیم‌شده (پیش‌فرض ۱۵–۳۰ ثانیه)
          تا ۲ ساعت: ۲ برابر | تا ۶ ساعت: ۴ برابر | بعدش: ۸ برابر
        بعد از سقف ساعتِ نگهبانی (پیش‌فرض ۲۴ ساعت) چک کلاً متوقف می‌شود."""
        base = membership_check_delay()
        try:
            joined_at = int(rec.get("joined_at") or rec.get("created_at")
                            or time.time())
        except Exception:
            return base
        age_h = (time.time() - joined_at) / 3600.0
        if age_h <= 0.5:
            return base
        if age_h <= 2:
            return base * 2
        if age_h <= 6:
            return base * 4
        return base * 8

    def response_delay_seconds():
        """تأخیر تصادفی پاسخ موفق «جوین شدم» روی پیام طرف.

        بازه‌ی پیش‌فرض: ۱۱–۴۸ ثانیه (response_min_sec/response_max_sec).
        اگر فقط کلید قدیمی response_delay_sec موجود باشد، به‌عنوان بازه‌ی
        ثابت (min=max) تفسیر می‌شود تا سازگاری با تنظیم‌های قدیم حفظ شود.
        صفر بودنِ مقدار به معنای «پاسخ فوری» است و واقعاً صفر می‌ماند.
        """
        x = eng.ex_cfg()
        if "response_min_sec" in x or "response_max_sec" in x:
            lo = int(x.get("response_min_sec") or 0)
            hi = int(x.get("response_max_sec") or lo)
            if lo == 0 and hi == 0:
                return 0
            lo, hi = max(0, lo), max(lo, hi)
            if lo == hi:
                return max(0, min(3600, lo))
            return random.randint(lo, hi)
        # ── سازگاری با کلید قدیمی response_delay_sec ──
        v = x.get("response_delay_sec")
        try:
            return max(0, min(3600, int(15 if v is None else v)))
        except (TypeError, ValueError):
            return 15

    def come_delay_seconds():
        """تأخیر تصادفی پیام «بیا» بعد از جوینِ خود ربات (out direction).

        بازه‌ی پیش‌فرض: ۳۴–۳۵ ثانیه. هرگز ۰ نیست تا الگوی ربات ماشینی نشود.
        """
        x = eng.ex_cfg()
        lo = int(x.get("come_min_sec", 34) or 34)
        hi = int(x.get("come_max_sec", 35) or 35)
        lo, hi = max(1, lo), max(lo, hi)
        if lo == hi:
            return max(1, min(3600, lo))
        return random.randint(lo, hi)

    def reply_delay_seconds():
        """تأخیر تصادفی پاسخ‌های مستقیم رویداد (msg_no/msg_wait/msg_nolink).

        بازه‌ی پیش‌فرض: ۵–۱۸ ثانیه. هر پاسخ برای هر شخص فقط یک‌بار.
        """
        x = eng.ex_cfg()
        lo = int(x.get("reply_min_sec", 5) or 5)
        hi = int(x.get("reply_max_sec", 18) or 18)
        lo, hi = max(1, lo), max(lo, hi)
        if lo == hi:
            return max(1, min(3600, lo))
        return random.randint(lo, hi)

    async def send_not_joined_reminder(rec):
        """متن msg_no را روی پیام اصلی می‌فرستد.
        - اگر متن سفارشی msg_no ثبت شده باشد: فقط همان متن می‌رود،
          هیچ لینکی (نه کانال طرف، نه کانال خودم) زیرش اضافه نمی‌شود.
        - اگر متنی ثبت نشده باشد: پیش‌فرض «نیومدی» + کانال خودم
          (standard/vip) فرستاده می‌شود — نه کانال طرف.
        این رفتار باگ قبلی که لینک طرف (@SWAG_815) را زیر پیام می‌گذاشت
        و پیش‌فرض همیشه روشن بود را برطرف می‌کند."""
        x = eng.ex_cfg()
        if not x["reply"] or not rec:
            return False
        # سقف مطلق (فیکس «تا ابد میگه»): برای هر تبادل فقط max_rem بار
        # «نیومدی» می‌رود — شمارندهٔ مادام‌العمر (reminders_total) فقط با
        # عضویتِ واقعیِ طرف صفر می‌شود؛ چرخه‌های جدید (ادعای دوباره،
        # ری‌استارت بعد از لفت و…) حق پیام تازه نمی‌سازند.
        _max_rem = max(0, min(3, int(x.get("max_reminders", 2) or 0)))
        if _max_rem == 0:
            return False
        if int(rec.get("reminders_total") or 0) >= _max_rem:
            eng.log("info", "ex_reminder_cap",
                    f"#{rec['id']} total={rec.get('reminders_total')} >= {_max_rem}")
            return False
        # ── دروازه‌ی سراسریِ «پشت‌سرهم نرو» ──
        # این تابع تنها نقطه‌ی ارسال «نیومدی» است، پس محافظِ قطعی همین‌جاست:
        # اگر کمتر از فاصله‌ی بین عملکرد‌ها (پیش‌فرض ۱۵–۲۰ ثانیه) از آخرین
        # عملکردِ این رکورد گذشته باشد، پیام نمی‌رود. در این حالت نوبتِ
        # بعدی کمی جلو می‌افتد تا دوباره تلاش شود — بدون سوزاندنِ شمارنده‌ی
        # یادآوری و بدون لفتِ زودهنگام. (باگِ «دو تا نیومدی درجا» همین‌جا
        # بسته می‌شود، چون هر سه مسیر ارسال از این تابع رد می‌شوند.)
        #
        # استثنا — فیکسِ «گفت دارم چک می‌کنم و دیگر هیچی نگفت»: حلقه‌ی
        # یادآوری هر نوبت اول عضویت را «چک» می‌کند و اگر عضو نبود،
        # بلافاصله همین تابع را صدا می‌زند؛ یعنی آخرین عملکرد همیشه
        # چکِ همین چند لحظه پیش است و دروازه بدون استثنا، ارسال را
        # «همیشه» رد می‌کرد. حلقه هم آن را شکستِ ارسال حساب می‌کرد،
        # اخطار می‌سوزاند و تبادل را بی‌اینکه حتی یک «نیومدی» برود لغو
        # می‌کرد — طرف فقط «دارم چک می‌کنم» را دیده بود. وقتی آخرین
        # عملکرد چکِ بی‌صدای همان نوبت بوده، این ارسال ادامه‌ی همان
        # نوبت است، نه پیامِ تکراری: رد نمی‌شود و صفِ تک‌عملکردی در
        # action() خودش باقیِ فاصله (۱۵–۲۰ ثانیه) را صبر می‌کند و بعد
        # می‌فرستد — فاصله‌ی بین عملکرد‌ها همچنان کامل رعایت می‌شود.
        wait_op = ex_cd.wait_for(rec.get("id"))
        _last_kind_fn = getattr(ex_cd, "last_kind", None)
        _last_kind = (_last_kind_fn(rec.get("id"))
                      if callable(_last_kind_fn) else "")
        if wait_op > 0 and _last_kind != "check":
            nxt = int(time.time() + max(1, int(wait_op) + 1))
            eng.db.ex_set(rec["id"], next_reminder=nxt,
                          note="در صف عملکرد — «نیومدی» کمی دیگر می‌رود")
            eng.log("info", "ex_reminder_gap", f"#{rec['id']} wait={int(wait_op)}s")
            return False
        # لینک طرف هرگز داخل متن ارسالی قرار نمی‌گیرد؛ حتی placeholderهای
        # قدیمیِ {channel} در ex_render خالی می‌شوند.
        link = (rec.get("link") or "").strip()
        _claim_no = bool(rec.get("claim_joined"))
        body = eng.ex_render("msg_claim_no" if _claim_no else "msg_no",
                             rec.get("peer_name") or "", link)
        chat, mid = rec.get("src_chat"), rec.get("src_msg")
        if not body or not chat or not mid:
            return False

        async def _send_reminder():
            if DRY_RUN:
                return True
            await client.send_message(chat, body, reply_to=mid, link_preview=False)
            return True

        try:
            # ارسال هم یک «عملکرد» است: در صفِ سراسری اجرا می‌شود و
            # خنک‌کننده‌ی این رکورد را ثبت می‌کند تا عملکردِ بعدی
            # (چک / لفت / پیام دوم) درجا پشتِ این نیفتد.
            return bool(await ex_cd.action("reminder", rec.get("id"), _send_reminder))
        except Exception as e:
            eng.log("warn", "ex_reminder", f"#{rec['id']}: {type(e).__name__}: {e}")
            return False

    # ---------- پیدا کردن کانال طرف ----------
    async def find_their_channel(event, sender, chat_id, deep=True):
        """کانال طرف را پیدا می‌کند و لینک کانال‌های خودمان را کنار می‌گذارد.

        لینک‌های عمومی با نام کاربری و لینک‌های خصوصی با شناسه‌ی واقعی کانال
        مقایسه می‌شوند؛ وگرنه t.me/+HASH کانال خودمان با @username یکی تشخیص
        داده نمی‌شد و در پیام‌های دوتا‌لینکی ممکن بود لینک اول (کانال خودمان)
        به‌اشتباه به‌عنوان لینک طرف تبادل انتخاب شود.

        اولویت: لینک همین پیام، پیام‌های قبلی خودش در همین گروه، کانال پروفایل.
        deep=False فقط لینک همین پیام را بررسی می‌کند.
        """
        def norm_ref(value):
            value = str(value or "").strip().lower().rstrip("/")
            value = re.sub(r"^https?://", "", value)
            value = re.sub(r"^(?:www\.)?(?:t\.me|telegram\.me)/", "", value)
            value = value.lstrip("@")
            if value.startswith("joinchat/"):
                return "invite:" + value.split("/", 1)[1]
            if value.startswith("+"):
                return "invite:" + value[1:]
            return value

        mine = set()
        own_refs = []
        for tier in ("standard", "vip"):
            raw = (eng.st.prof(tier).get("channel") or "").strip()
            if raw:
                own_refs.append(raw)
                mine.add(norm_ref(raw))
        if eng.my_username:
            mine.add(norm_ref(eng.my_username))

        # کانال‌ها را با ID مقایسه کن تا invite link خصوصیِ کانال خودمان هم
        # از لینک طرف تفکیک شود. CheckChatInvite فقط بررسی می‌کند و عضو نمی‌شود.
        cache = getattr(eng, "_exchange_link_id_cache", None)
        if cache is None:
            cache = eng._exchange_link_id_cache = {}

        async def channel_id(ref):
            key = norm_ref(ref)
            now0 = time.time()
            cached = cache.get(key)
            if cached and cached[0] > now0:
                return cached[1]
            cid = None
            try:
                if is_invite(ref):
                    from telethon.tl.functions.messages import CheckChatInviteRequest
                    info = await client(CheckChatInviteRequest(invite_hash(ref)))
                    chat = getattr(info, "chat", None)
                    cid = getattr(chat, "id", None) if chat else None
                else:
                    ent = await client.get_entity(ref)
                    cid = getattr(ent, "id", None)
            except Exception:
                # اگر لینک خصوصی قابل‌بررسی نبود، انتخابِ باقیمانده‌ها ادامه یابد؛
                # هیچ لینک دعوتی را برای تشخیص، Import/Join نمی‌کنیم.
                cid = None
            cache[key] = (now0 + (300 if cid is not None else 30), cid)
            # سقفِ کش: با globals() خوانده می‌شود تا اگر این تابع به‌تنهایی
            # (بدونِ کلِ ماژول) اجرا شد، NameError ندهد.
            try:
                _lim = int(globals().get("LINK_CACHE_LIMIT", 1500) or 0)
            except Exception:
                _lim = 1500
            if _lim > 0 and len(cache) > _lim:
                try:
                    trim_link_cache(eng)
                except Exception:
                    pass
            return cid

        mine_ids = set()
        for ref in own_refs:
            cid = await channel_id(ref)
            if cid is not None:
                mine_ids.add(int(cid))

        async def pick(links):
            unresolved = []
            for link in links:
                if norm_ref(link) in mine:
                    continue
                cid = await channel_id(link)
                if cid is None:
                    unresolved.append(link)
                    continue
                if int(cid) in mine_ids:
                    continue
                return link
            # قالب دو لینکِ جفج: لینک اول کانال خودمان (جایی که ممبر باید
            # بیاید) و لینک دوم کانال طرف تبادل است. اگر تلگرام برای هر دو
            # invite خصوصی شناسه نداد، نقش‌ها را از همین ترتیب بگیر؛ وگرنه
            # لینک اولِ مبهم اشتباهاً به‌عنوان کانال طرف انتخاب می‌شد.
            if (len(links) == 2 and len(unresolved) == 2
                    and all(is_invite(link) for link in links)):
                return links[1]
            return unresolved[0] if unresolved else None

        # ۱) فقط لینک واقعی داخل همان پیام؛ AI اجازه انتخاب لینک ندارد.
        got = await pick(extract_links(event.raw_text))
        if got:
            return got, "از پیام خودش"

        if not deep:
            return None, ""

        # ۲) پیام‌های قبلی همین شخص در همین گروه
        try:
            async for msg in client.iter_messages(chat_id, from_user=sender.id,
                                                  limit=40):
                if msg.id == event.id or not msg.raw_text:
                    continue
                got = await pick(extract_links(msg.raw_text))
                if got:
                    return got, "از پیام‌های قبلی‌اش"
        except Exception as e:
            eng.log("warn", "ex_scan", f"{type(e).__name__}: {e}")

        # ۳) کانال شخصی روی پروفایل
        try:
            from telethon.tl.functions.users import GetFullUserRequest
            full = await client(GetFullUserRequest(sender.id))
            pcid = getattr(full.full_user, "personal_channel_id", None)
            if pcid:
                ent = await client.get_entity(pcid)
                u = getattr(ent, "username", None)
                if u and norm_ref(u) not in mine:
                    return "@" + u, "از پروفایلش"
        except Exception:
            pass

        return None, ""

    # ---------- دریافت درخواست تبادل ----------
    @client.on(events.NewMessage(incoming=True))
    async def on_exchange_request(event):
        x = eng.ex_cfg()
        if not x["enabled"]:
            return

        replied_to_me = False
        try:
            r = await event.get_reply_message()
            replied_to_me = bool(
                r and (getattr(r, "out", False)
                       or getattr(r, "sender_id", None) == eng.my_id))
        except Exception:
            pass

        if (not event.is_private and not replied_to_me
                and not getattr(event, "mentioned", False)):
            return

        sender = await event.get_sender()
        if not sender or getattr(sender, "bot", False):
            return
        body_text = event.raw_text or ""
        # دستورهای «جوین شو/عضو شو» هرگز ادعای Join نیستند. این منفیِ قطعی
        # قبل از تماس با AI اجرا می‌شود تا حتی پاسخ اشتباه مدل هم اثر نگذارد.
        join_request = eng.ai.looks_like_join_request(body_text)
        local_claim = bool(
            not join_request and
            (eng.ai.looks_like_join(body_text)
             or (x["words"] and any(w.lower() in body_text.lower() for w in x["words"]))
             )
        )
        ai_sniff = None
        # عبارت‌های رایج بدون انتظار شبکه فوراً پردازش می‌شوند؛ AI فقط برای
        # جمله‌های مبهمِ مرتبط، آن هم فقط برای تشخیص claim، استفاده می‌شود.
        relevant = (replied_to_me
                    or getattr(event, "mentioned", False)
                    or local_claim or bool(extract_links(body_text)))
        if event.is_private and not relevant:
            return
        if (not join_request and not local_claim and relevant and eng.ai.ready
                and eng.ai.cfg.get("smart_detect") and body_text.strip()):
            ai_sniff = await eng.ai.sniff(body_text)

        ai_intent = str((ai_sniff or {}).get("intent") or "").strip().lower()
        ai_join_request = ai_intent in ("join_request", "request", "imperative")
        # فقط نتیجه «آیا ادعای Join شده یا نه» از AI استفاده می‌شود؛ درخواست
        # Join و هر عبارت دستوری همیشه false است.
        claim = bool(not join_request and not ai_join_request
                     and (local_claim or (ai_sniff and ai_sniff.get("joined"))))

        if join_request or ai_join_request:
            eng.log("info", "ex_join_request", body_text[:160])
            return

        # کجاها گوش بده
        if event.is_private:
            pass
        else:
            # سابقهٔ تبادل، حتی joined، مجوز پاسخ به گفتگوی دیگران نیست.
            if not replied_to_me and not getattr(event, "mentioned", False):
                return

        # ریپلای خالی/نامرتبط به پیام جفج را هم پردازش نکن؛ فقط ادعای Join
        # یا لینک واقعی کانال، درخواست تبادل محسوب می‌شود.
        if replied_to_me and not claim and not extract_links(body_text):
            return

        # فیلترِ کلمات برای ادعا/ریپلای است، نه برای لینکی که مستقیم در
        # پیوی فرستاده می‌شود: کسی که در پیوی لینک کانالش را می‌فرستد
        # دقیقاً درخواست تبادل داده است و نباید به‌خاطر فیلترِ گروهی
        # بی‌جواب بماند (باگِ «به لینک‌های پیوی جواب نمی‌دهد»).
        if x["words"] and not claim and not replied_to_me and not (
                event.is_private and extract_links(body_text)):
            return
        sender_name = (f"@{sender.username}" if getattr(sender, "username", None)
                       else (getattr(sender, "first_name", "") or str(sender.id)))

        # پیام‌های عادی PV فقط برای تحلیل/تشخیص هستند؛ AI هیچ پاسخ خودکاری نمی‌فرستد.
        if event.is_private and not extract_links(body_text) and not claim:
            return

        # ── آیا عضو کانال من هست؟ ──
        # یک False منفرد را نتیجه قطعی نگیر؛ قبل از پیام ناموفق دوباره تأیید کن.
        # رکورد تبادلِ همین طرف (در مسیرهای پایین پر می‌شود)؛ say برای
        # ثبتِ پرچم replied به آن نیاز دارد.
        rec = None
        # اگر برای این طرف رکوردی داریم، چک با شناسه‌ی همان رکورد در صفِ
        # تک‌عملکردی می‌رود: رکوردی که همین الان جوین/چک/پیام گرفته، دوباره
        # چک نمی‌شود («اگه توی چک کردن قبلی‌ها بود، همین الان دوباره چک نکن»)
        # و خنک‌کننده‌ی ۱۵–۲۰ ثانیه‌ایِ بعد از چک هم ثبت می‌شود.
        rec_pre = eng.db.ex_by_peer(getattr(sender, "id", 0) or 0)
        _need_check = bool(claim or replied_to_me or (
            rec_pre and rec_pre.get("status") in ("pending", "approved", "joined")))
        if _need_check:
            member = await confirm_peer_membership(
                sender.id, rec_id=(rec_pre or {}).get("id"), confirm=False)
        else:
            member = None

        async def say(key, channel="", fallbacks=()):
            if not x["reply"]:
                return False
            keys = (key,) + tuple(fallbacks or ())
            t = ""
            used = ""
            for k in keys:
                t = eng.ex_render(k, sender_name, channel)
                if t:
                    used = k
                    break
            # اگر کاربر متنی ثبت نکرد، هیچ پیام خودکاری ارسال نشود
            # (msg_no پیش‌فرضِ «نیومدی» + کانال خودم را از ex_render می‌گیرد).
            if not t:
                return False
            # وقتی msg_no سفارشی ثبت شده باشد، فقط همان متن می‌رود و
            # هیچ لینکی زیرش اضافه نمی‌شود. وقتی پیش‌فرض است، ex_render
            # خودش کانال من را اضافه کرده (نه کانال طرف).
            # باگ قبلی که @SWAG_815 (کانال طرف) را زیر پیام می‌گذاشت حذف شد.
            # پاسخ‌های مستقیم رویداد (msg_no/msg_wait/msg_nolink) قبل از
            # ارسال یک تأخیر انسانی ۵–۱۸ ثانیه می‌گیرند تا شکل رباتی نداشته باشد.
            # پیام موفق (msg_ok/msg_come) مسیر خودش را دارد (reply_joined با
            # بازه‌ی ۱۱–۴۸ ثانیه) و از این تأخیر عبور نمی‌کند.
            if key in ("msg_no", "msg_wait", "msg_nolink"):
                await asyncio.sleep(reply_delay_seconds())

            async def _do_reply():
                return await event.reply(t)

            try:
                # پاسخ مستقیم هم یک عملکرد است: تا عملکرد قبلی (چک عضویت،
                # جوین، «نیومدی» قبلی) تمام نشده و فاصله‌ی تنظیم‌شده
                # (پیش‌فرض ۱۵–۲۰ ثانیه) نگذشته باشد، ارسال نمی‌شود.
                await ex_cd.action("say", (rec or {}).get("id"), _do_reply)
                eng.log("info", "ex_reply_attempt", f"{sender_name} [{used}]")
                # پرچم replied=1 تا همین پیام دوباره ارسال نشود (هر شخص فقط یک بار)
                # برای پیام‌های مستقیم رویداد ضروری است.
                if key in ("msg_no", "msg_wait", "msg_nolink"):
                    rec_after = eng.db.ex_get(rec["id"]) if rec and rec.get("id") else None
                    if rec_after:
                        eng.db.ex_set(rec_after["id"], replied=1)
                return True
            except Exception as e:
                eng.log("warn", "ex_reply", f"{sender_name}: {type(e).__name__}: {e}")
                return False

        # ── عضو نیست → «نیومدی» (۲ بار فاصله‌دار) → لفت ──
        # پیام «جوین شدم» هرگز همین‌جا گفته نمی‌شود؛ فقط بعد از Join واقعی
        # می‌رود (reply_joined). قبلاً «نیومدی» و «جوین شدم» پشت سر هم
        # فرستاده می‌شدند؛ آن باگ برطرف شد.
        if member is False:
            # «نیومدی + لینک» فقط برای کسی می‌رود که کانالش واقعاً در تبادل
            # ثبت شده باشد: یا لینکش را در همین پیام خودش فرستاده، یا
            # قبلاً رکوردی برایش ساخته شده (مثلاً از اسکن گروه). کانال
            # شخصیِ پروفایل و لینک پیام‌های قبلی دیگر بیرون کشیده نمی‌شود
            # تا هر ریپلای‌کننده‌ی تصادفی‌ای «نیومدی + لینک» نگیرد.
            link, _src = await find_their_channel(event, sender, event.chat_id,
                                                  deep=False)
            rec = None
            if link:
                rec, _ = eng.db.ex_add(sender.id, sender_name, link)
            if not rec:
                # رکورد قبلی: کانالی که خودِ همین طرف قبلاً ثبت کرده است.
                rec = eng.db.ex_by_peer(sender.id)
            if not rec or rec["status"] in ("rejected", "leaving"):
                # نه لینکی در پیامش هست و نه کانالی در تبادل ثبت کرده →
                # ریپلای تصادفی است؛ نه پیامی می‌رود و نه رکوردی ساخته می‌شود.
                eng.log("info", "ex_notmember_skip", sender_name)
                return
            eng.db.ex_set(rec["id"], claim_joined=int(claim))
            link = link or (rec.get("link") or "")
            max_rem = max(0, min(3, int(x.get("max_reminders", 2) or 0)))
            send_now = False
            now0 = int(time.time())
            old_count = max(0, int(rec.get("reminders") or 0))
            # سقف مادام‌العمر: کل «نیومدی»های قبلی این رکورد (هر چرخه‌ای)
            total_sent = max(0, int(rec.get("reminders_total") or 0))
            can_more = total_sent < max_rem
            # اگر همین حالا نوبتِ یادآوری/لفتِ این طرف فعال است، پیامِ
            # تازه‌ای پشت سر همان نمی‌رود؛ همان زمان‌بندی کار خودش را
            # می‌کند تا دو پیام «نیومدی» پشت سر هم نیفتند.
            # فیکس مسابقه: «منقضی‌شده ولی هنوز پردازش‌نشده» هم فعال حساب
            # می‌شود؛ قبلاً اگر حلقه‌ی یادآوری وسط پردازش بود، این مسیر هم
            # همزمان پیام می‌فرستاد و دو «نیومدی» تقریباً پشت‌سرهم می‌رفت.
            active_window = int(rec.get("next_reminder") or 0) > 0
            if rec["status"] == "joined":
                # رکورد پیش‌قدم را خراب نکن؛ دو یادآوری فاصله‌دار می‌رود
                # و اگر طرف تا آن موقع نیامد، از کانالش لفت می‌دهم.
                if can_more and not active_window and old_count < max_rem and x["reply"]:
                    send_now = True
                eng.db.ex_set(rec["id"],
                              src_chat=event.chat_id, src_msg=event.id,
                              note="پیش‌قدم انجام شده؛ طرف هنوز عضو کانال من نیست")
            else:
                # رکورد بسته‌شده (لفت/شکست) با ادعای تازه از نو شروع می‌شود.
                fresh = rec["status"] in ("left", "failed")
                if fresh:
                    old_count = 0
                if can_more and not active_window and old_count < max_rem and x["reply"]:
                    send_now = True
                eng.db.ex_set(rec["id"], status="pending",
                              strikes=0 if fresh else rec["strikes"] + 1,
                              unk_streak=0,
                              direction="in",
                              src_chat=event.chat_id, src_msg=event.id,
                              replied=0, reminders=old_count,
                              # در دور تازه، نوبت مانده از دور قبلی بی‌معنی است
                              next_reminder=0 if fresh else int(rec.get("next_reminder") or 0),
                              note="عضو نیست — دو یادآوری فاصله‌دار، بعد لفت")
            eng.log("info", "ex_notmember", sender_name)
            # اولین «نیومدی» همین حالا می‌رود؛ اگر متن سفارشی ثبت شده باشد
            # فقط همان متن می‌رود، وگرنه پیش‌فرض «نیومدی» + کانال خودم.
            # لینک طرف هرگز اتوماتیک زیر پیام نمی‌آید (باگ @SWAG_815 فیکس شد).
            _say_key = "msg_claim_no" if claim else "msg_no"
            sent_now = (await say(_say_key, link, fallbacks=("msg_no",))
                        if send_now else False)
            if rec and rec.get("id"):
                # زمان‌بندی یادآوری بعدی از لحظه‌ی ارسالِ واقعی همین پیام
                # حساب می‌شود (فاصله تصادفی، پیش‌فرض ۲۰ تا ۴۰ ثانیه) تا دو
                # پیام پشت سر هم نیایند. این پیام اول خودش یکی از همان دو
                # یادآوری است، پس شمارنده همین‌جا بالا می‌رود. جوینِ کانال
                # طرف فقط بعد از عضویتِ واقعی‌اش در صف می‌رود؛ پیام «جوین
                # شدم» هم فقط بعد از Join واقعی می‌رود، نه همین‌جا.
                rec_now = eng.db.ex_get(rec["id"])
                new_count = int(rec_now.get("reminders") or 0) + (1 if sent_now else 0)
                # رکوردِ قبلاً جوین‌شده فقط وقتی زمان‌بندی می‌گیرد که پیامِ
                # اول واقعاً رفته باشد؛ وگرنه چکِ دوره‌ای (strikes) کار خودش
                # را می‌کند تا رکورد بی‌پایان معطل نماند.
                joined_rec = rec_now.get("status") == "joined"
                if sent_now or (not joined_rec
                                and not int(rec_now.get("next_reminder") or 0)):
                    # نوبتِ «نیومدی» بعدی هرگز درجا پشتِ پیامِ قبلی یا پشتِ
                    # چکِ عضویتی که همین الان انجام شد نمی‌افتد.
                    eng.db.ex_set(rec["id"], reminders=new_count,
                                  reminders_total=total_sent + (1 if sent_now else 0),
                                  next_reminder=next_action_after(
                                      rec_now, int(time.time()) + reminder_delay()))
            return

        # ── نامشخص ──
        if member is None:
            eng.log("warn", "ex_unknown", f"{sender_name} — عضویت قابل بررسی نبود")
            # مثل مسیر «عضو نیست» فقط لینکِ خودِ پیام یا رکوردِ ثبت‌شده‌ی
            # قبلی مبناست — نه کانال شخصی پروفایل هر ریپلای‌کننده‌ای.
            link, _src = await find_their_channel(event, sender, event.chat_id,
                                                  deep=False)
            rec0 = None
            if link:
                rec0, _n = eng.db.ex_add(sender.id, sender_name, link)
            if not rec0:
                rec0 = eng.db.ex_by_peer(sender.id)
            # فیکس: «نامشخص» دیگر به معنی تأییدِ بدون چک نیست. قبلاً همین‌جا
            # طرف بدون هیچ بررسی‌ای approved می‌شد و کانالش بعداً جوین می‌شد —
            # یعنی ادعای «جوین شدم» اصلاً چک نمی‌شد.
            has_channel = any((eng.st.prof(t)["channel"] or "").strip()
                              for t in ("standard", "vip"))
            if rec0 and rec0["status"] not in ("joined", "rejected",
                                               "left", "failed"):
                if has_channel:
                    # چک موقتاً نامشخص شده (FloodWait/خطای API) — یک بررسی
                    # بی‌صدای دوباره زمان‌بندی کن؛ حلقه‌ی یادآوری اگر واقعاً
                    # عضو شد تأیید می‌کند، اگر نه «نیومدی» می‌رود.
                    eng.db.ex_set(rec0["id"], direction="in", claim_joined=int(claim),
                                  peer_id=sender.id, peer_name=sender_name,
                                  src_chat=event.chat_id, src_msg=event.id,
                                  replied=0, strikes=0,
                                  unk_streak=int(rec0.get("unk_streak") or 0) + 1,
                                  next_reminder=next_action_after(
                                      rec0, int(time.time())
                                      + membership_check_delay()),
                                  note="عضویت نامشخص — دوباره چک می‌کنم")
                    eng.log("info", "ex_unknown_recheck",
                            f"{sender_name} → {link or rec0.get('link')}")
                else:
                    # کانال من اصلاً تنظیم نشده؛ عضویت فعلاً قابل تأیید نیست.
                    # در وضعیت pending می‌ماند تا کانال ست شود — نه تأییدِ
                    # کورکورانه، نه جوینِ کانال طرف. نوبتِ چکِ دوباره هم
                    # می‌گیرد تا به‌محض ست‌شدن کانال، حلقه‌ی یادآوری خودش
                    # ادامه بدهد؛ قبلاً next_reminder ست نمی‌شد و رکورد
                    # برای همیشه مرده می‌ماند (طرف فقط «دارم چک می‌کنم»
                    # را دیده بود و دیگر هیچ).
                    eng.db.ex_set(rec0["id"], status="pending", direction="in", claim_joined=int(claim),
                                  peer_id=sender.id, peer_name=sender_name,
                                  src_chat=event.chat_id, src_msg=event.id,
                                  replied=0, strikes=0,
                                  next_reminder=next_action_after(
                                      rec0, int(time.time())
                                      + membership_check_delay()),
                                  note="کانال من تنظیم نشده — عضویت تأیید نشد")
                    eng.log("warn", "ex_no_channel",
                            f"{sender_name} → {link or rec0.get('link')}")
            # پیام «جوین شدم» فقط بعد از Join واقعی می‌رود (reply_joined)؛
            # همین‌جا و زودتر از موعد گفته نمی‌شود تا پشت سر پیام دیگری
            # نیفتد. اگر متنی برای انتظار ثبت شده باشد، همان می‌رود.
            # لینک طرف (اگر در دسترس است) برای لایه‌ی دوم strip پاس می‌شود.
            await say("msg_wait", link or (rec0 or {}).get("link") or "")
            if not has_channel:
                await warn_membership_check_broken(int(time.time()))
            return

        # ── عضو هست → کانالش را پیدا کن ──
        link, src = await find_their_channel(event, sender, event.chat_id)

        if not link:
            eng.log("info", "ex_nolink", sender_name)
            await say("msg_nolink")
            await note(f"🔎 یکی ریپلای زد و **عضو هم هست**، ولی کانالش را پیدا نکردم.\n"
                       f"از: {sender_name}\n"
                       "دستی اضافه کن: `تبادل افزودن @channel`")
            return

        rec, is_new = eng.db.ex_add(sender.id, sender_name, link)
        if not rec:
            return
        if rec["status"] == "joined":
            delay = response_delay_seconds()
            if delay:
                await asyncio.sleep(delay)
            await say("msg_ok", rec.get("link") or "", ("msg_come", "msg_first"))
            return
        if rec["status"] == "rejected":
            return

        eng.db.ex_set(rec["id"], src_chat=event.chat_id, src_msg=event.id,
                      replied=0, peer_id=sender.id, peer_name=sender_name,
                      reminders_total=0)   # عضو واقعی بود — سابقه «نیومدی» پاک شود

        if x["auto_join"]:
            eng.db.ex_set(rec["id"], status="approved", strikes=0,
                          note=f"عضو است ({src})")
            eng.log("info", "ex_approved", f"{sender_name} → {link} ({src})")
            # متن «جوین شدم» بعد از جوینِ واقعی ریپلای می‌شود
        else:
            eng.db.ex_set(rec["id"], status="pending",
                          note=f"✅ عضو است — منتظر تأیید تو ({src})")
            await say("msg_wait", rec.get("link") or "")
            await note(f"🔁 **درخواست تبادل**\n\nاز: {sender_name}\n"
                       f"کانال: `{link}` ({src})\nوضعیت: ✅ عضو کانال من هست\n\n"
                       f"`تبادل تأیید {rec['id']}` جوین • "
                       f"`تبادل رد {rec['id']}` رد")

    # ---------- اسکن گروه‌ها: خودت پیش‌قدم شو ----------
    async def scan_groups(manual=False):
        """از هر گروه ثبت‌شده فقط پیام‌های جدیدِ دارای لینک را بررسی می‌کند.
        پیش‌فرض تازه‌ترین لینک جدید است.
        زمان واقعی Join با min_join_gap_sec/max_join_gap_sec کنترل می‌شود."""
        x = eng.ex_cfg()
        if time.time() < float(x.get("_scan_flood_until", 0)):
            return 0, "اسکن در انتظار پایان FloodWait"
        # قاعده‌ی «اول کانال، بعد گروه»: بدون کانال، اسکنِ گروه فقط لینک
        # جمع می‌کند و بعد جوین می‌زند؛ پس همان‌جا متوقف می‌شود.
        if not eng.ex_channel_ready():
            return 0, ("کانال تنظیم نشده — تا `کانال @mychannel` ثبت نشه "
                       "گروه‌ها اسکن نمی‌شوند")
        if not x["groups"]:
            return 0, "گروهی تعیین نشده"

        mine = {(eng.st.prof(t)["channel"] or "").lstrip("@").lower()
                for t in ("standard", "vip")}
        mine.discard("")
        if eng.my_username:
            mine.add(eng.my_username.lower())

        last = x.get("scan_last") or {}
        found = 0
        max_age = max(30, int(x.get("scan_max_age_sec", 300) or 300))
        scan_now = time.time()
        raw_groups = x.get("groups") or []
        all_groups = [raw_groups] if isinstance(raw_groups, str) else list(raw_groups)
        groups_to_scan = group_failover_scan_groups(x, all_groups, int(scan_now))
        scan_error = False

        # ── دروازه‌ی ضد-انباشت (فقط اسکن خودکار؛ اسکن دستی همیشه رد است) ──
        # وقتی صفِ عملکرد به‌خاطر FloodWait بسته است یا هنوز انباری از
        # رکوردهای Join‌نشده داریم، اسکنِ تازه نکن: هر کانالی که الان ثبت
        # شود پیش از رسیدن نوبتش از پنجره‌ی سن لینک پیر می‌شود و فقط
        # رکورد مرده + طوفانِ اعلان («کانال تازه…» و بعدش «کانال قدیمی
        # رد شد») می‌سازد. scan_last هم جلو نمی‌رود تا بعد از باز شدنِ
        # صف، همان پیام‌ها دوباره دیده شوند (ثبت تکراری با ex_by_link
        # کنترل می‌شود).
        if not manual:
            gate = scan_gate_reason(
                getattr(ex_cd, "blocked_until", 0),
                len(eng.db.ex_list("approved", 100)),
                scan_now)
            if gate == "flood":
                return 0, "صف تبادل به‌خاطر FloodWait بسته است"
            if gate == "backlog":
                return 0, (f"صف Join {fa(SCAN_JOIN_BACKLOG_LIMIT)} رکورد "
                           "معلق دارد — بعد از تخلیه، اسکن ادامه می‌یابد")

        for g in groups_to_scan:
            key = str(g)
            previous = int(last.get(key, 0) or 0)
            newest = previous
            candidates = []
            try:
                # Telegram پیام‌ها را از جدیدترین به قدیمی‌ترین می‌دهد.
                # پیش‌فرض مورد ۱ یعنی تازه‌ترین لینک؛ اگر وجود نداشت،
                # آخرین پیام معتبر انتخاب می‌شود.
                pick = max(1, int(x.get("scan_pick", 1) or 1))
                async for msg in client.iter_messages(g, limit=x["scan_limit"]):
                    if not msg:
                        continue
                    msg_id = int(getattr(msg, "id", 0) or 0)
                    newest = max(newest, msg_id)
                    # پیام‌هایی که قبلاً تا این شناسه دیده شده‌اند، دوباره
                    # کاندید Join نشوند؛ فقط پیام جدید را بررسی کن.
                    if msg_id <= previous:
                        continue
                    if msg.out:
                        continue
                    msg_date = getattr(msg, "date", None)
                    if msg_date is not None:
                        try:
                            age = scan_now - msg_date.timestamp()
                            if age > max_age:
                                continue
                        except Exception:
                            pass

                    sender = None
                    try:
                        sender = await msg.get_sender()
                    except Exception:
                        pass
                    if not sender or getattr(sender, "bot", False):
                        continue
                    if getattr(sender, "id", 0) == eng.my_id:
                        continue

                    links = [l for l in extract_links(msg.raw_text or "")
                             if l.lstrip("@").lower() not in mine]
                    if not links:
                        continue
                    candidates.append((msg, sender, links[0]))
                    if len(candidates) >= pick:
                        break

                if candidates:
                    selected_index = min(pick, len(candidates))
                    msg, sender, link = candidates[selected_index - 1]
                    existing = eng.db.ex_by_link(link)
                    sender_name = (f"@{sender.username}"
                                   if getattr(sender, "username", None)
                                   else (getattr(sender, "first_name", "")
                                         or str(sender.id)))
                    if not existing:
                        rec, is_new = eng.db.ex_add(sender.id, sender_name, link)
                        if rec and is_new:
                            # رفع باگ: peer_id حتماً ست شود تا رکوردِ پیش‌قدمِ جدید
                            # هم در ex_due چک شود (طرف «نیامد» → strike/لفت/نیومدی).
                            eng.db.ex_set(rec["id"], status="approved",
                                          direction="out", src_chat=msg.chat_id,
                                          src_msg=msg.id, replied=0,
                                          peer_id=sender.id, peer_name=sender_name,
                                          note=f"پیش‌قدم — پیام شماره {selected_index} از جدیدترین‌ها")
                            found += 1
                    elif existing.get("status") in ("failed", "left"):
                        # پیام جدیدی از همان کانال آمده؛ دوباره در صف Join قرار بده.
                        eng.db.ex_set(existing["id"], status="approved",
                                      peer_id=sender.id, peer_name=sender_name,
                                      direction="out", src_chat=msg.chat_id,
                                      src_msg=msg.id, replied=0, claim_joined=0,
                                      reminders=0, next_reminder=0, next_check=0,
                                      strikes=0, note="پیام جدید — دوباره در صف Join")
                        found += 1

            except FloodWaitError as e:
                w = getattr(e, "seconds", 60)
                eng.log("warn", "scan_flood", f"{g}: {w}s")
                x["_scan_flood_until"] = time.time() + w + 2
                return found, f"FloodWait {w}s"
            except Exception as e:
                scan_error = True
                eng.log("warn", "scan", f"{g}: {type(e).__name__}: {e}")
                continue

            if newest:
                last[key] = newest
            # ضد اسپم چندگروهی: فقط وقتی ۲ گروه یا بیشتر داری، بین اسکن گروه‌ها ۵–۱۵ ثانیه تصادفی صبر کن
            # تا هر دو گروه سر ۳۰ ثانیه با هم اسکن نشن و اکانت ریپورت نشه.
            # تک گروه = مثل قبل ۰.۵ ثانیه.
            groups_count = len(groups_to_scan)
            if groups_count >= 2 and not manual:
                jitter_min = max(1, int(x.get("scan_jitter_min_sec", 5) or 5))
                jitter_max = max(jitter_min, int(x.get("scan_jitter_max_sec", 15) or 15))
                # اگر گروه آخر نیست، تأخیر تصادفی
                # (برای اینکه بنر اول سر ۳۰ ثانیه، دومی ۵–۱۵ ثانیه بعد بره)
                if g != groups_to_scan[-1]:
                    await asyncio.sleep(random.randint(jitter_min, jitter_max))
                else:
                    await asyncio.sleep(0.5)
            else:
                # تک گروه یا حالت دستی: کوتاه نگه‌دار
                await asyncio.sleep(0.5)

        x["scan_last"] = last
        switched = group_failover_after_scan(
            x, all_groups, int(time.time()), found, scan_error=scan_error
        )
        if switched:
            old_i, new_i = switched
            eng.log("info", "group_failover",
                    f"{all_groups[old_i]} → {all_groups[new_i]} پس از بی‌لینک‌ماندن")
        eng.st.save()
        if found:
            eng.log("info", "scan", f"{found} آخرین پیام دارای لینک ثبت شد")
        return found, ""

    # ---------- اسکن مستقل پیش‌قدم ----------
    async def scan_loop():
        # تجمیع اعلان «کانال تازه پیدا شد»: به‌جای یک نوتیف per اسکن،
        # شمارش‌ها جمع می‌شوند و حداکثر هر SCAN_FOUND_NOTE_GAP_SEC ثانیه
        # یک پیام تجمیعی می‌رود تا Saved Messages طوفان نبیند.
        found_buf = [0]
        last_found_note = [0.0]

        def _join_gate_now():
            try:
                return scan_gate_reason(
                    getattr(ex_cd, "blocked_until", 0),
                    len(eng.db.ex_list("approved", 100)), time.time())
            except Exception:
                return ""

        # اسکن مستقل است تا بررسی‌های طولانی عضویت، فرصت هر ۳۰ ثانیه
        # برای پیدا کردن کانال جدید را عقب نیندازد.
        last_scan = [0.0]
        while True:
            try:
                x = eng.ex_cfg()
                if not x["enabled"]:
                    await asyncio.sleep(2)
                    continue
                # قاعده‌ی «اول کانال»: بدون کانال، اسکنِ گروه هم بی‌معنی است.
                if not eng.ex_channel_ready():
                    await warn_ex_no_channel(int(time.time()))
                    await asyncio.sleep(20)
                    continue
                # ۰) اسکن گروه‌ها (حالت پیش‌قدم)
                now_t = time.time()
                manual = bool(x.pop("_scan_now", False))
                scan_seconds = max(30, int(x.get("scan_every_sec", 30) or 30))
                if manual or (x["initiate"] and
                              now_t - last_scan[0] >= scan_seconds):
                    last_scan[0] = now_t
                    n, err = await scan_groups(manual)
                    if manual:
                        if err:
                            await note(f"🔍 اسکن انجام نشد — {err}")
                        else:
                            wait = eng.join_thr.wait_time()
                            left = joins_left_today()
                            if left <= 0:
                                state = "به‌دلیل خطای داخلی امکان Join نیست"
                            elif wait > 0:
                                state = f"در صف است؛ حدود {secs(int(wait))} دیگر امتحان می‌کنم"
                            else:
                                state = "همین حالا برای Join امتحان می‌کنم"
                            await note(f"🔍 اسکن تمام شد — {fa(n)} کانال تازه پیدا شد؛ {state}.")
                    elif n:
                        # اعلان تجمیعی و راستگو: وقتی صف بلاک/شلوغ است
                        # هرگز قول «همین نوبت جوین» نده — همان قولی که
                        # مشتری دید و عملاً هیچ جوینی اتفاق نمی‌افتاد.
                        found_buf[0] += int(n)
                        if (time.time() - last_found_note[0]
                                >= SCAN_FOUND_NOTE_GAP_SEC):
                            total = found_buf[0]
                            found_buf[0] = 0
                            last_found_note[0] = time.time()
                            gate = _join_gate_now()
                            wait = eng.join_thr.wait_time()
                            if gate == "flood":
                                state = ("صف تبادل به‌خاطر محدودیت تلگرام "
                                         "(FloodWait) بسته است؛ به‌محض بازشدن "
                                         "خودکار جوین می‌زنم")
                            elif joins_left_today() <= 0:
                                state = "به‌دلیل خطای داخلی امکان Join نیست"
                            elif gate == "backlog" or wait > 0:
                                state = (f"در صف Join؛ حدود "
                                         f"{secs(int(max(wait, 0)))} دیگر")
                            else:
                                state = "برای Join همین نوبت"
                            await note(f"🔍 {fa(total)} کانال تازه پیدا شد — {state}.")
                    elif err:
                        # اسکن خودکار عمداً رد شده (فلود/بک‌لاگ)؛ فقط لاگ،
                        # بدون نوتیف تا طوفان پیام تکراری ساخته نشود.
                        eng.log("info", "scan_gated", err)

                # زمان‌بندی دقیق‌تر از حلقه‌ی اصلی تبادل.
                await asyncio.sleep(1)
            except asyncio.CancelledError:
                raise
            except Exception as e:
                eng.log("error", "scan_loop", f"{type(e).__name__}: {e}")
                await asyncio.sleep(5)

    # ---------- کارگر بررسی عضویت ----------
    async def membership_loop():
        # بررسی‌های ۱۵ تا ۳۰ ثانیه‌ای نباید صف Join را متوقف کنند.
        while True:
            try:
                x = eng.ex_cfg()
                if not x["enabled"]:
                    await asyncio.sleep(20)
                    continue
                # بدون کانال، چکِ عضویت همه «نامشخص» می‌شود و «نیومدی»
                # اشتباهی می‌رود؛ پس کلِ این حلقه صبر می‌کند.
                if not eng.ex_channel_ready():
                    await warn_ex_no_channel(int(time.time()))
                    await asyncio.sleep(20)
                    continue
                # پاس‌گاه ضد-فلود: با تعداد رکوردهای جوین‌شده، فاصله‌ی
                # بین درخواست‌های بررسی خودکار تنظیم می‌شود و اگر مدتی
                # Flood نخورده باشد، کم‌کم برمی‌گردد.
                try:
                    check_gate.set_load(len(eng.db.ex_list("joined", 500)))
                    check_gate.maybe_decay()
                except Exception:
                    pass
                # ── یادآوری عضو‌نشده: دو پیام «نیومدی» با فاصله‌ی تصادفی ──
                # (پیش‌فرض ۲۰ تا ۴۰ ثانیه) و بعد از آن، اگر طرف هنوز
                # نیامده باشد، لفت از کانالش (یا لغو تبادلِ هنوز انجام‌نشده).
                now_rem = int(time.time())
                for rec in eng.db.ex_reminder_due(now_rem, 20):
                    if not rec.get("peer_id"):
                        continue
                    # ── صفِ تک‌عملکردی: نوبتِ این رکورد رسیده یا نه؟ ──
                    # اگر عملکردی روی همین رکورد در جریان است (چک نگهبانی،
                    # جوین، پیام قبلی) یا کمتر از فاصله‌ی تنظیم‌شده
                    # (پیش‌فرض ۱۵–۲۰ ثانیه) از تمام‌شدنش گذشته، هیچ کاری
                    # نمی‌کنیم و نوبت را به زمانِ درست منتقل می‌کنیم. این
                    # همان باگِ «چک کرد و درجا گفت نیومدی» را می‌بندد.
                    ok_turn, defer_ts = ex_cd.defer_if_due(rec, rec.get("next_reminder"))
                    if not ok_turn:
                        eng.db.ex_set(rec["id"], next_reminder=defer_ts,
                                      note="عملکرد قبلی در جریان/تازه تمام شده — صبر")
                        continue
                    # چک سریع: فاصله‌ی بررسی عضویت (۱۵–۳۰ ثانیه) روی
                    # بازه‌ی تنظیم‌شده‌ی «فاصله یادآوری» کاربر جمع نشود.
                    still = await confirm_peer_membership(rec["peer_id"],
                                                          fast=True,
                                                          rec_id=rec["id"],
                                                          confirm=False)
                    if still is None and unk_fallback(rec):
                        still = False
                    now2 = int(time.time())
                    max_rem = max(0, min(3, int(x.get("max_reminders", 2) or 0)))
                    if still is True:
                        # طرف عضو شد؛ رکورد برای Join آزاد می‌شود و پیام
                        # «جوین شدم» فقط بعد از Join واقعی می‌رود (replied=0).
                        # شمارنده یادآوری صفر می‌شود تا اگر بعداً دوباره بیاید
                        # و برود، دورِ تازه‌ای از دو یادآوری شروع شود.
                        eng.db.ex_set(rec["id"],
                                      status="approved" if rec["status"] == "pending"
                                      else rec["status"],
                                      reminders=0, reminders_total=0,
                                      next_reminder=0,
                                      strikes=0, unk_streak=0, replied=0,
                                      note="عضو شد — آماده Join")
                    elif still is False:
                        count = int(rec.get("reminders") or 0)
                        if count < max_rem:
                            # یادآوری بعدی «نیومدی» — فاصله تصادفی تا پیام
                            # بعدی/لفت تا پیام‌ها پشت سر هم نیایند.
                            sent = await send_not_joined_reminder(rec)
                            if sent:
                                count += 1
                                # نوبتِ بعدی هرگز زودتر از پایانِ خنک‌کننده‌ی
                                # رکورد نیست: «نیومدی» دوم درجا پشتِ اولی نمی‌رود.
                                eng.db.ex_set(rec["id"], reminders=count,
                                              strikes=0, unk_streak=0,
                                              next_reminder=next_action_after(
                                                  rec, now2 + reminder_delay()),
                                              note="یادآوری ارسال شد")
                            else:
                                # فیکس: اگر ارسال پیام ممکن نشد (ریپلای
                                # خاموش، پیام مرجع پیدا نشد، خطای ارسال)،
                                # قبلاً همین‌جا تا ابد دوباره زمان‌بندی
                                # می‌شد و لفت هیچ‌وقت نمی‌رسید. حالا بعد
                                # از ۳ تلاشِ ناموفق، سراغ لفت/لغو می‌رویم.
                                fails = int(rec.get("strikes") or 0) + 1
                                if fails >= 3:
                                    eng.db.ex_set(rec["id"], reminders=max_rem,
                                                  strikes=fails,
                                                  next_reminder=next_action_after(
                                                      rec, now2 + 5),
                                                  note="ارسال یادآوری نشد — رفتن به مرحله لفت")
                                    eng.log("warn", "ex_remind_fail",
                                            f"#{rec['id']} {rec['link']} — ۳ تلاش ناموفق")
                                else:
                                    eng.db.ex_set(rec["id"], strikes=fails,
                                                  next_reminder=next_action_after(
                                                      rec, now2 + reminder_delay()),
                                                  note=f"یادآوری ارسال نشد — تلاش {fa(fails)} از ۳")
                        elif max_rem == 0:
                            # «بدون پیام»: فقط بی‌صدای عضویت را چک می‌کنیم.
                            eng.db.ex_set(rec["id"],
                                          next_reminder=next_action_after(
                                              rec, now2 + membership_check_delay()),
                                          note="بدون پیام — بررسی بی‌صدای عضویت")
                        elif rec.get("status") == "joined":
                            # هر دو یادآوری رفت و طرف نیامد → لفت از کانالش.
                            # rec_id داده می‌شود تا لفت در صفِ تک‌عملکردی برود:
                            # درجا بعد از آخرین «نیومدی» لفت نمی‌دهد، اول
                            # فاصله‌ی تنظیم‌شده (پیش‌فرض ۱۵–۲۰ ثانیه) صبر می‌کند.
                            _conf = await confirm_peer_membership(
                                rec["peer_id"], fast=True, rec_id=rec["id"])
                            if _conf is True:
                                eng.db.ex_set(rec["id"], reminders=0,
                                              reminders_total=0,
                                              next_reminder=0, strikes=0,
                                              unk_streak=0, replied=0,
                                              note="لفت لغو شد — تأیید شد عضو است")
                                continue
                            if _conf is None:
                                eng.db.ex_set(rec["id"], next_reminder=next_action_after(
                                    rec, int(time.time()) + membership_check_delay()),
                                    note="لفت معلق — عضویت نامشخص است")
                                continue
                            # وضعیتِ تازه: اگر رکورد دیگر در حالت joined
                            # نیست (لفتِ مسیر دیگر/دستی)، دوباره لفت نزن.
                            _fresh = eng.db.ex_get(rec["id"])
                            if not _fresh or _fresh.get("status") != "joined":
                                continue
                            # اگر تلاشِ قبلیِ لفت شکست خورده و عقب‌نشینی
                            # فعال است، دوباره تلاش نکن: هم به اکانت فشار
                            # نمی‌آید، هم نوتیف تکراری نمی‌رود.
                            _blk = int(max(int(rec.get("leave_blocked_until") or 0),
                                           int(_fresh.get("leave_blocked_until") or 0)))
                            if _blk > int(time.time()):
                                eng.db.ex_set(rec["id"], next_reminder=0,
                                              next_check=_blk,
                                              note="لفت معلق — لینکِ طرف "
                                                   "قابل‌حل نیست، بعداً دوباره")
                                continue
                            # کانالِ تکراری: اگر همان کانال با رکوردِ دیگری
                            # قبلاً لفت شده، این رکورد را هم بی‌صدا ببند تا
                            # پیام «لفت انجام شد» دوباره نرود.
                            _twin = eng.db.ex_same_channel_left(_fresh)
                            if _twin:
                                eng.db.ex_set(rec["id"], status="left",
                                              next_reminder=0, next_check=0,
                                              note="همان کانال قبلاً لفت شد "
                                                   f"(رکورد #{_twin['id']})")
                                continue
                            ok, err = await leave_link(rec["link"], rec["id"])
                            _now_l = int(time.time())
                            if ok:
                                eng.db.ex_set(rec["id"], status="left",
                                              next_reminder=0, next_check=0,
                                              leave_fail=0, leave_blocked_until=0,
                                              note="نیومد → لفت دادم")
                            else:
                                # فیکس باگِ «بعد از خطای لفت، طرف در پیوی
                                # جواب نمی‌گیرد»: رکوردِ لفت‌نشده دیگر در
                                # حالتِ انتظار نمی‌ماند. با صفرکردن
                                # next_reminder، پنجره‌ی فعالِ «نیومدی» باز
                                # نمی‌ماند و پیام بعدی همین طرف جواب
                                # می‌گیرد؛ تلاش بعدیِ لفت با عقب‌نشینیِ
                                # پلکانی (۱ دقیقه → … → ۶ ساعت) زمان‌بندی
                                # می‌شود تا حلقه‌ی تلاشِ هر دقیقه‌ای نسازد.
                                _fails = int(rec.get("leave_fail") or 0) + 1
                                _back = min(6 * 3600, 60 * (5 ** (_fails - 1)))
                                eng.db.ex_set(rec["id"], status="joined",
                                              next_reminder=0,
                                              next_check=_now_l + _back,
                                              leave_fail=_fails,
                                              leave_blocked_until=_now_l + _back,
                                              note=f"لفت نشد (تلاش {_fails}): {err}")
                            # لفتِ ناموفق «لفت» حساب نمی‌شود: آمارِ گزارش و
                            # ریسک فقط لفت‌های واقعی را می‌شمارند، وگرنه
                            # گزارش می‌گفت «لفت داده‌شده» در حالی‌که طرف
                            # هنوز در کانالِ طرف است.
                            if ok:
                                eng.log("info", "ex_left", f"#{rec['id']} {rec['link']}")
                            else:
                                eng.log("warn", "ex_leave_fail",
                                        f"#{rec['id']} {rec['link']} — {err}")
                            if ok and rec.get("direction") == "out":
                                # بعد از لفت، نوبت بعدی را از گروه بررسی کن.
                                x["_scan_now"] = True
                            if eng.ex_cfg().get("report_mode", "live") == "live":
                                await note(eng.ex_live_leave_text(
                                    eng.db.ex_get(rec["id"]) or rec,
                                    "" if ok else err, "nojoin"))
                        else:
                            # هنوز در کانالش جوین نشده‌ام؛ فقط تبادل لغو می‌شود.
                            eng.db.ex_set(rec["id"], status="failed",
                                          next_reminder=0,
                                          note="مهلت دو یادآوری گذشت و عضو نشد")
                            eng.log("info", "ex_expired", f"#{rec['id']} {rec['link']}")
                            if eng.ex_cfg().get("report_mode", "live") == "live":
                                await note("🕒 تبادل لغو شد — طرف در مهلتِ دو پیام "
                                           "«نیومدی» عضو کانال نشد.\n"
                                           f"📡 کانال: `{rec.get('link') or '—'}`\n"
                                           f"👤 طرف: {rec.get('peer_name') or rec.get('peer_id')}")
                    else:
                        # نامشخص (FloodWait/خطای API).
                        if check_gate.blocked():
                            # سقف فلود فعال است — شمارنده نسوزان؛ فقط ۶۰
                            # ثانیه دیگر دوباره. قبلاً همین‌جا رکوردها در
                            # حالت «نامشخص» می‌چرخیدند و لفت عقب می‌افتد.
                            eng.db.ex_set(rec["id"],
                                          next_reminder=next_action_after(rec, now2 + 60),
                                          note="فلود بررسی — ۶۰ ثانیه صبر")
                            continue
                        # قبلاً همین‌جا تا ابد با فاصله کوتاه دوباره چک
                        # می‌شد — بی‌صدا و بی‌اثر. حالا بعد از ۵ بار
                        # پشت‌سرهم فاصله بلند می‌شود و هشدار می‌رود.
                        # مهم: نتیجه‌ی «نامشخص» شمارنده‌ی مخصوص خودش
                        # (unk_streak) را دارد؛ هرگز روی strikes واقعی
                        # اثر نمی‌گذارد تا فلود/خطای API باعث لفتِ اشتباه نشود.
                        unk = int(rec.get("unk_streak") or 0) + 1
                        if unk >= 5:
                            eng.db.ex_set(rec["id"], unk_streak=unk,
                                          next_reminder=next_action_after(rec, now2 + 600),
                                          note="بررسی عضویت مدتی است نامشخص — ۱۰ دقیقه صبر")
                            await warn_membership_check_broken(now2)
                        else:
                            eng.db.ex_set(rec["id"], unk_streak=unk,
                                          next_reminder=next_action_after(
                                              rec, now2 + membership_check_delay()),
                                          note="بررسی عضویت نامشخص است")

                # ۳) چک دوره‌ای نگهبانی: طرف هنوز عضو کانال من هست؟
                # فاصله‌ی چک با سن رکورد پلکانی بلند می‌شود (watch_delay_seconds)
                # و بعد از سقف ساعتِ نگهبانی (پیش‌فرض ۲۴ ساعت) متوقف می‌شود.
                # لفت فقط بعد از چند نبودنِ تأییدشده انجام می‌شود (پیش‌فرض ۲ بار)،
                # نه با یک منفیِ تنها؛ نتیجه‌های «نامشخص» (فلود/خطا) اصلاً
                # جزو اخطارها حساب نمی‌شوند.
                for rec in eng.db.ex_due(int(time.time()), 5):
                    # ── صفِ تک‌عملکردی: رکوردی که همین الان جوین/چک/پیام
                    # گرفته، دوباره چک نمی‌شود. عملکردِ در جریان یا
                    # خنک‌کننده‌ی تمام‌نشده (پیش‌فرض ۱۵–۲۰ ثانیه) یعنی
                    # «الان نه» — نوبت به زمانِ درست منتقل می‌شود و هیچ
                    # پیامی هم نمی‌رود. باگِ «جوین شد و درجا چک شد و درجا
                    # نیومدی رفت» همین‌جا بسته می‌شود.
                    ok_watch, defer_w = ex_cd.defer_if_due(rec, rec.get("next_check"))
                    if not ok_watch:
                        eng.db.ex_set(rec["id"], last_check=int(time.time()),
                                      next_check=defer_w,
                                      note="در صف عملکرد — چکِ بعدی کمی دیگر")
                        continue
                    if not rec["peer_id"]:
                        now_no_peer = int(time.time())
                        eng.db.ex_set(rec["id"], last_check=now_no_peer,
                                      next_check=now_no_peer + watch_delay_seconds(rec))
                        continue
                    # اگر چک دائمی خاموش یا مهلتش گذشته → دیگر چک نکن
                    if not eng.should_watch_joined(rec):
                        # فیکس باگِ «چرخه‌ی بی‌پایان»: قبلاً next_check صفر و
                        # last_check «الان» می‌شد؛ یعنی همان شرطِ ex_due
                        # (next_check=0 AND last_check<=now) دوباره برقرار
                        # بود و حلقه هر چند ثانیه همین رکورد را برمی‌داشت،
                        # هر بار یک نوشتن در دیتابیس می‌زد و جا را برای
                        # رکوردهای واقعی تنگ می‌کرد. الان بازنشستگی تا ۶
                        # ساعت دیگر قطعی است و هر ۶ ساعت یک‌بار دوباره چک
                        # می‌شود (اگر تنظیمات را عوض کنی، خودش برمی‌گردد).
                        _retire_to = int(time.time()) + 6 * 3600
                        eng.db.ex_set(rec["id"], last_check=int(time.time()),
                                      next_check=_retire_to,
                                      note="پایان نگهبانی دائمی (سقف ساعت)")
                        continue
                    # رکوردهای دارای نوبتِ یادآوری فعال (ادعای «جوین شدم» بدون
                    # عضویت واقعی) را حلقه‌ی یادآوری مدیریت می‌کند: دو پیام
                    # فاصله‌دار و بعد لفت. اینجا واردش نمی‌شویم تا نه پیامِ
                    # دوباره فرستاده شود و نه لفت زودتر از موعد اتفاق بیفتد.
                    if (int(rec.get("next_reminder") or 0) > 0
                            and max(0, int(x.get("max_reminders", 2) or 0)) >= 1):
                        now_skip = int(time.time())
                        eng.db.ex_set(rec["id"], last_check=now_skip,
                                      next_check=now_skip + watch_delay_seconds(rec))
                        continue
                    still = await confirm_peer_membership(rec["peer_id"],
                                                          rec_id=rec["id"],
                                                          confirm=False)
                    if still is None and unk_fallback(rec):
                        still = False
                    now = int(time.time())
                    if still is True:
                        # باگِ «جذب موفق آپدیت نمی‌شود»: در حالت پیش‌قدم
                        # (direction='out') طرف دیرتر برمی‌گردد و عضوِ کانال
                        # من می‌شود؛ این لحظه هیچ‌جا ثبت نمی‌شد، پس شمارنده‌ی
                        # «جذب موفق» هم هیچ‌وقت بالا نمی‌رفت. الان با اولین
                        # تأییدِ عضویت، زمانش ذخیره و یک‌بار هم به خودت
                        # گزارش می‌شود (فقط یک‌بار، چون ستون دیگر خالی نیست).
                        _peer_back = (rec.get("direction") == "out"
                                      and not int(rec.get("peer_joined_at") or 0))
                        eng.db.ex_set(rec["id"], last_check=now,
                                      next_check=next_action_after(
                                          rec, now + watch_delay_seconds(rec)),
                                      strikes=0, unk_streak=0, reminders_total=0,
                                      note="عضو است",
                                      **({"peer_joined_at": now} if _peer_back else {}))
                        if _peer_back:
                            eng.log("ok", "ex_peer_joined",
                                    f"#{rec['id']} {rec['link']}")
                            if eng.ex_cfg().get("report_mode", "live") == "live":
                                await note(eng.ex_live_peer_join_text(
                                    eng.db.ex_get(rec["id"]) or rec))
                    elif still is False:
                        st = rec["strikes"] + 1
                        # فیکس: طرفی که از اول هیچ‌وقت نیامده (بدون ادعای
                        # «جوین شدم» و بدون پیام موفق — replied=0) اول باید
                        # «نیومدی» بشنود؛ لفتِ بی‌هشدار منصفانه نیست. دور
                        # یادآوری شروع می‌شود و حلقه‌ی یادآوری بعد از پیام‌ها
                        # لفت می‌دهد. لفتِ فوری فقط برای تقلب‌کننده‌هاست:
                        # عضو شد، پیام موفق گرفت، بعد لفت داد (replied=1).
                        if (x["reply"] and rec.get("peer_id")
                                and not int(rec.get("replied") or 0)
                                and st <= 1
                                and max(0, int(x.get("max_reminders", 2) or 0)) >= 1):
                            sent0 = await send_not_joined_reminder(rec)
                            nowf = int(time.time())
                            eng.db.ex_set(rec["id"],
                                          strikes=1, unk_streak=0, last_check=nowf,
                                          next_check=0,
                                          reminders=1 if sent0 else 0,
                                          reminders_total=(int(rec.get("reminders_total") or 0)
                                                           + (1 if sent0 else 0)),
                                          next_reminder=next_action_after(
                                              rec, nowf + reminder_delay()),
                                          note="نیومد — دور «نیومدی» شروع شد (چک نگهبانی)")
                            eng.log("info", "ex_first_miss",
                                    f"#{rec['id']} {rec['link']}")
                            await asyncio.sleep(2)
                            continue
                        if st >= x["max_strikes"]:
                            # لفت در صفِ تک‌عملکردی: درجا بعد از چک/پیام نیست.
                            _conf = await confirm_peer_membership(
                                rec["peer_id"], rec_id=rec["id"])
                            if _conf is True:
                                eng.db.ex_set(
                                    rec["id"], last_check=int(time.time()),
                                    next_check=next_action_after(
                                        rec, int(time.time())
                                        + watch_delay_seconds(rec)),
                                    strikes=0, unk_streak=0,
                                    note="لفت لغو شد — تأیید شد عضو است")
                                continue
                            if _conf is None:
                                eng.db.ex_set(rec["id"], next_check=next_action_after(
                                    rec, int(time.time()) + membership_check_delay()),
                                    note="لفت معلق — عضویت نامشخص است")
                                continue
                            # وضعیتِ تازه را از دیتابیس بخوان: اگر بینِ این
                            # تصمیم و چکِ قبلی، رکورد از حالت joined خارج شده
                            # (لفتِ دستیِ خودت، لفتِ مسیر یادآوری، حذف/رد)،
                            # دوباره لفت نزن و پیام «لفت انجام شد» تکراری نساز.
                            _fresh = eng.db.ex_get(rec["id"])
                            if not _fresh or _fresh.get("status") != "joined":
                                continue
                            # عقب‌نشینیِ لفتِ ناموفق (لینک منقضی/خطای موقت):
                            # تا پایان مهلت، تلاش تکراری نکن.
                            _blk = int(max(int(rec.get("leave_blocked_until") or 0),
                                           int(_fresh.get("leave_blocked_until") or 0)))
                            if _blk > int(time.time()):
                                eng.db.ex_set(rec["id"], last_check=now,
                                              next_check=_blk,
                                              note="لفت معلق — لینکِ طرف "
                                                   "قابل‌حل نیست، بعداً دوباره")
                                continue
                            # کانالِ تکراری: اگر همان کانال با رکوردِ دیگری
                            # قبلاً لفت شده، این رکورد را هم بی‌صدا ببند تا
                            # پیام «لفت انجام شد» دوباره نرود.
                            _twin = eng.db.ex_same_channel_left(_fresh)
                            if _twin:
                                eng.db.ex_set(rec["id"], status="left",
                                              last_check=now, next_check=0,
                                              strikes=st,
                                              note="همان کانال قبلاً لفت شد "
                                                   f"(رکورد #{_twin['id']})")
                                continue
                            ok, err = await leave_link(rec["link"], rec["id"])
                            _now_l = int(time.time())
                            if ok:
                                eng.db.ex_set(rec["id"], status="left",
                                              last_check=_now_l, next_check=0,
                                              strikes=st, unk_streak=0,
                                              leave_fail=0, leave_blocked_until=0,
                                              note="طرف رفت → لفت دادم")
                            else:
                                # همان فیکسِ مسیر یادآوری: بعد از شکستِ لفت،
                                # رکورد در «انتظارِ درجا» گیر نمی‌کند و تلاش
                                # بعدی با عقب‌نشینیِ پلکانی زمان‌بندی می‌شود
                                # (۱ دقیقه → … → ۶ ساعت).
                                _fails = int(rec.get("leave_fail") or 0) + 1
                                _back = min(6 * 3600, 60 * (5 ** (_fails - 1)))
                                eng.db.ex_set(rec["id"], status="joined",
                                              last_check=_now_l,
                                              next_check=_now_l + _back,
                                              strikes=st, unk_streak=0,
                                              leave_fail=_fails,
                                              leave_blocked_until=_now_l + _back,
                                              note=f"لفت نشد (تلاش {_fails}): {err}")
                            # لفتِ ناموفق در آمار/ریسک «لفت» شمرده نمی‌شود.
                            if ok:
                                eng.log("info", "ex_left", f"#{rec['id']} {rec['link']}")
                            else:
                                eng.log("warn", "ex_leave_fail",
                                        f"#{rec['id']} {rec['link']} — {err}")
                            if ok and rec.get("direction") == "out":
                                # بعد از لفت، نوبت بعدی را از گروه بررسی کن.
                                x["_scan_now"] = True
                            # رفع باگ: به کسی که جوین کرده ولی واقعاً عضو نشده
                            # (دروغگو) همین‌جا «نیومدی» بگو — نه فقط پیش‌قدم‌ها.
                            # اگر در دورِ اخطارها قبلاً پیام گرفته، تکرارش نکن.
                            if x["reply"] and rec.get("peer_id") and ok:
                                rec2 = eng.db.ex_get(rec["id"])
                                if not int(rec2.get("reminders") or 0):
                                    await send_not_joined_reminder(rec2)
                            if eng.ex_cfg().get("report_mode", "live") == "live":
                                await note(eng.ex_live_leave_text(
                                    eng.db.ex_get(rec["id"]) or rec,
                                    "" if ok else err, "left"))
                        else:
                            # در مرز، فقط یک‌بار یادآوری «نیومدی» بفرست؛ سپس بی‌صدا.
                            reminded = int(rec.get("reminders") or 0)
                            extra_total = 0
                            if x["reply"] and rec.get("peer_id") and st == 1 \
                                    and reminded < max(1, int(x.get("max_reminders", 2) or 1)):
                                sent = await send_not_joined_reminder(eng.db.ex_get(rec["id"]))
                                if sent:
                                    reminded += 1
                                    extra_total = 1
                            eng.db.ex_set(rec["id"], last_check=now,
                                          next_check=next_action_after(
                                              rec, now + watch_delay_seconds(rec)),
                                          strikes=st, unk_streak=0, reminders=reminded,
                                          reminders_total=(int(rec.get("reminders_total") or 0)
                                                           + extra_total),
                                          note=f"عضو نیست ({st}/{x['max_strikes']})")
                            eng.log("info", "ex_strike",
                                    f"#{rec['id']} {st}/{x['max_strikes']}")
                    else:
                        # نامشخص در چک نگهبانی (فلود/خطای API) — هرگز اخطارِ
                        # لفت حساب نمی‌شود؛ شمارنده‌ی جدای خودش را دارد.
                        if check_gate.blocked():
                            eng.db.ex_set(rec["id"], last_check=now,
                                          next_check=next_action_after(rec, now + 60),
                                          note="فلود بررسی — ۶۰ ثانیه صبر")
                            continue
                        # بعد از ۵ بار نامشخصِ واقعی (نه فلود)، فاصله بلند
                        # کن و یک‌بار هشدار بده.
                        unk = int(rec.get("unk_streak") or 0) + 1
                        if unk >= 5:
                            eng.db.ex_set(rec["id"], last_check=now,
                                          next_check=next_action_after(rec, now + 600),
                                          unk_streak=unk,
                                          note="بررسی عضویت مدتی است نامشخص — ۱۰ دقیقه صبر")
                            await warn_membership_check_broken(now)
                        else:
                            eng.db.ex_set(rec["id"], last_check=now,
                                          next_check=next_action_after(
                                              rec, now + watch_delay_seconds(rec)),
                                          unk_streak=unk)
                    await asyncio.sleep(2)

                # برای دقت فاصله‌ی یادآوری، بیشتر از دو ثانیه در صف نمان.
                await asyncio.sleep(2)
            except asyncio.CancelledError:
                raise
            except Exception as e:
                eng.log("error", "membership_loop", f"{type(e).__name__}: {e}")
                await asyncio.sleep(5)

    # ---------- کارگر صف Join ----------
    async def exchange_worker():
        # تجمیع اعلان «کانال قدیمی رد شد»: قبلاً هر رکورد منقضی یک پیام
        # جدا می‌ساخت و چند ثانیه پشت سر هم Saved Messages را پر می‌کرد.
        stale_links = []
        stale_since = [0.0]
        stale_age_sec = [300]

        async def flush_stale():
            if not stale_links:
                return
            links = stale_links[:]
            age = stale_age_sec[0]
            stale_links.clear()
            stale_since[0] = 0.0
            await note(format_stale_batch(links, age))

        while True:
            try:
                # اگر پنجره‌ی تجمیع پر شد، یک پیام خلاصه بفرست.
                if (stale_links and
                        time.time() - stale_since[0] >= STALE_FLUSH_SEC):
                    await flush_stale()
                x = eng.ex_cfg()

                # ارسال دوباره‌ی پیام برای Joinهایی که قبلاً انجام شده‌اند.
                # این عملیات حتی اگر تبادل خاموش باشد هم انجام می‌شود.
                reply_now = x.pop("_reply_now", None)
                if reply_now:
                    rec = eng.db.ex_get(int(reply_now))
                    if rec and rec.get("status") == "joined":
                        eng.db.ex_set(rec["id"], replied=0)
                        sent_reply = await reply_joined(eng.db.ex_get(rec["id"]))
                        await note(f"💬 پیام تبادل #{fa(rec['id'])} "
                                   + ("ارسال شد." if sent_reply else "ارسال نشد."))
                    eng.st.save()

                if not x["enabled"]:
                    await asyncio.sleep(20)
                    continue

                # توجه: گیتِ «سقفِ عضویت» دیگر این‌جا نیست. قبلاً این‌جا با
                # `continue` کلِ حلقه (چکِ عضویت، یادآور، گزارش) تا یک ساعت
                # می‌خوابید و اکانت عملاً «آفلاین» دیده می‌شد؛ حالا فقط
                # بخشِ جوین پشتِ گیت است.

                # ── شفافیتِ صف: اگر یک عملیات FloodWait خورده باشد، صفِ
                # تک‌عملکردی تا پایان جریمه بسته است و هیچ پاسخ خودکاری
                # (از جمله در پیوی) نمی‌آید. قبلاً این حالت کاملاً بی‌صدا
                # بود و به‌نظر می‌رسید ربات مرده است؛ حالا یک‌بار توضیح
                # داده می‌شود و در رویدادها هم ثبت می‌شود.
                try:
                    _bu = float(getattr(ex_cd, "blocked_until", 0) or 0)
                except Exception:
                    _bu = 0.0
                if _bu > time.time():
                    _left_b = max(1, int(_bu - time.time()))
                    if int(x.get("_block_notice_at", 0) or 0) != int(_bu):
                        x["_block_notice_at"] = int(_bu)
                        eng.st.save()
                        eng.db.log("warn", "ex_blocked", f"{_left_b}s")
                        await note(
                            "⏳ **صفِ تبادل موقتاً بسته است**\n"
                            f"تلگرام برای این اکانت {secs(_left_b)} محدودیت "
                            "(FloodWait) گذاشته است. تا پایان آن هیچ عملکردی "
                            "— از جمله پاسخ به پیوی — اجرا نمی‌شود؛ بعد "
                            "خودکار ادامه می‌دهم.\n"
                            "اگر زیاد تکرار شد، «تبادل فاصله» را بزرگ‌تر کن "
                            "یا تعداد تبادل‌های هم‌زمان را کم کن.")

                # ۰) دور پاکسازی سقف عضویت. بیرون از wait_forِ جوین اجرا
                # می‌شود چون یک دور کامل (تا ۳۰ لفت با فاصله‌ی صف عملیات)
                # ممکن است چند دقیقه طول بکشد و timeout ۱۸۰ ثانیه‌ای جوین
                # وسطش کنسلش می‌کرد. لفت‌ها از همان ex_cd.action رد می‌شوند
                # پس فاصله‌ی ۱۵–۲۰ ثانیه‌ای و محافظ فلود خودکار رعایت می‌شود.
                if int(x.get("_capacity_cleanup_pending", 0) or 0):
                    x["_capacity_cleanup_pending"] = False
                    eng.st.save()
                    try:
                        left_count, stopped = await cleanup_capacity_for_slots()
                    except Exception as cleanup_error:
                        left_count, stopped = 0, (
                            f"پاکسازی ناموفق: {type(cleanup_error).__name__}: {cleanup_error}")
                        eng.log("warn", "ex_capacity_cleanup_error", stopped)
                    x["_last_capacity_cleanup_at"] = int(time.time())
                    eng.st.save()
                    if left_count <= 0 and not str(stopped or "").startswith("سقفِ زمانی"):
                        # کاندید امن نبود/همه لفت‌ها شکست خورد؛ بدون این بلاک
                        # هر جوین دوباره فلگ می‌زد و دور بی‌فایده تکرار می‌شد.
                        # (اگر فقط «سقفِ زمانی» دور را بست، بلاک نمی‌کنیم؛
                        # دور بعد ادامه می‌دهد.)
                        block_joins_for_capacity(
                            stopped or "کاندید امن برای لفت پیدا نشد")
                        # گیتِ بلاک بالای حلقه است؛ همین دور دیگر جوین نزن تا
                        # رکورد approved دست‌نخورده بماند و دور بعد پشت گیت بخوابد.
                        continue

                # ۱) لفت‌های دستی
                for rec in eng.db.ex_list("leaving", 5):
                    ok, err = await leave_link(rec["link"], rec["id"])
                    eng.db.ex_set(rec["id"], status="left" if ok else "failed",
                                  note="لفت دستی" if ok else err)
                    # لفتِ دستی هم در آمار شمرده می‌شود (ex_left فقط برای
                    # لفتِ واقعی) و نتیجه‌اش هم به خودت گزارش می‌شود؛ قبلاً
                    # اگر لفت دستی شکست می‌خورد، هیچ پیامی نمی‌آمد.
                    eng.log("info" if ok else "warn",
                            "ex_left" if ok else "ex_leave_fail",
                            f"#{rec['id']} {rec['link']} {err}")
                    if eng.ex_cfg().get("report_mode", "live") == "live":
                        await note(eng.ex_live_leave_text(
                            eng.db.ex_get(rec["id"]) or rec,
                            "" if ok else err, "manual"))
                    await asyncio.sleep(3)

                # ۲) جوین تأییدشده‌ها — تطبیقی + سقف ساعتی
                # گیتِ سقفِ عضویت — فقط جوین را متوقف می‌کند.
                capacity_blocked_until = int(x.get("_capacity_join_blocked_until", 0) or 0)
                if capacity_blocked_until > int(time.time()):
                    await asyncio.sleep(min(30, max(1, capacity_blocked_until - int(time.time()))))
                    continue
                if capacity_blocked_until:
                    x["_capacity_join_blocked_until"] = 0
                    eng.st.save()

                # قاعده‌ی «اول کانال»: لفتِ دستی (بالا) چون خودِ کاربر
                # خواسته و به کانالِ من کاری ندارد اجرا می‌شود؛ ولی
                # جوین/چک/پیامِ خودکار بدون کانالِ ثبت‌شده معنا ندارد و
                # اصلاً اجرا نمی‌شود.
                if not eng.ex_channel_ready():
                    await warn_ex_no_channel(int(time.time()))
                    await asyncio.sleep(20)
                    continue
                # هر بار فاصله موثر (پایه + Flood + آپ‌تایم) را حساب و به throttle بده
                try:
                    eng.adaptive_maybe_decay()
                    emin, emax = eng.effective_join_gap()
                    # فقط اگر با مقدار فعلی فرق دارد، apply کن تا next_gap الکی عوض نشود
                    if (emin != eng.join_thr.min_gap or emax != eng.join_thr.max_gap):
                        eng.join_thr.apply({"min_gap_sec": emin, "max_gap_sec": emax, "max_per_hour": 0})
                except Exception:
                    pass
                if eng.join_thr.wait_time() <= 0 and joins_left_today() > 0:
                    # ── سقف جوین/ساعت (محدودیت آهسته، خاموش پیش‌فرض) ──
                    hw = eng.hour_cap_wait()
                    if hw > 0:
                        # هر ۲ دقیقه یک‌بار نوتیف بده (ضد اسپم).
                        last_blocked = int(x.get("_hour_cap_blocked", 0) or 0)
                        if int(time.time()) - last_blocked > 120:
                            await note(f"⏸ سقف جوین/ساعت: در این ساعت به حد "
                                       f"{fa(int(x.get('hour_cap', 60) or 60))} رسیدی. "
                                       f"حدود {secs(hw)} دیگر ادامه می‌دهم.")
                        x["_hour_cap_blocked"] = int(time.time())
                        eng.st.save()
                        await asyncio.sleep(min(hw, 20))
                        continue
                    rec = None
                    for r in eng.db.ex_list("approved", 5):
                        rec = r
                        break
                    if rec:
                        max_age = max(30, int(eng.ex_cfg().get("scan_max_age_sec", 300) or 300))
                        queued_age = time.time() - float(rec.get("created_at") or time.time())
                        if rec.get("direction") == "out" and queued_age > max_age:
                            stale_note = f"لینک بیش از {secs(max_age)} قدیمی است؛ Join نشد"
                            eng.db.ex_set(rec["id"], status="failed", note=stale_note)
                            eng.log("info", "ex_stale", f"#{rec['id']} {rec['link']}")
                            # تجمیع به‌جای یک نوتیف per رکورد (طوفان پیام در
                            # صف‌های شلوغ). سقفِ نمایش یا پنجره‌ی زمانی، فلاش می‌کند.
                            if not stale_links:
                                stale_since[0] = time.time()
                                stale_age_sec[0] = max_age
                            stale_links.append(rec["link"])
                            if (len(stale_links) >= STALE_NOTE_MAX_LINKS
                                    or time.time() - stale_since[0] >= STALE_FLUSH_SEC):
                                await flush_stale()
                            await asyncio.sleep(1)
                            continue
                        eng.log("info", "ex_join_try", f"#{rec['id']} {rec['link']}")
                        # جوین در صفِ تک‌عملکردی: اگر عملکرد دیگری (چک عضویت،
                        # «نیومدی»، لفت) در جریان باشد یا تازه تمام شده باشد،
                        # اول صبر می‌کند. rec_id خنک‌کننده‌ی همین رکورد را
                        # ثبت می‌کند → چکِ «آیا واقعاً جوین شده؟» زودتر از
                        # فاصله‌ی تنظیم‌شده (پیش‌فرض ۱۵–۲۰ ثانیه) انجام نمی‌شود.
                        _join_rec_id = rec["id"]
                        _join_link = rec["link"]

                        async def _queued_join():
                            return await join_link(_join_link, _join_rec_id)

                        try:
                            ok, msg, title = await asyncio.wait_for(
                                _queued_join(), timeout=180)
                        except asyncio.TimeoutError:
                            ok, msg, title = False, "TimeoutError: درخواست Join بیشتر از حد مجاز طول کشید (صفِ عملکرد + ۶۰ ثانیه)", ""
                        if ok:
                            eng.join_thr.record()
                            joined_now = int(time.time())
                            # چکِ بعد از جوین هرگز درجا نیست: حداقل به اندازه‌ی
                            # فاصله‌ی بین عملکرد‌ها (پیش‌فرض ۱۵–۲۰ ثانیه) و
                            # فاصله‌ی چک عضویت، بعد از جوین زمان‌بندی می‌شود.
                            eng.db.ex_set(rec["id"], status="joined",
                                          joined_at=joined_now,
                                          last_check=joined_now,
                                          next_check=next_action_after(
                                              {"id": rec["id"]},
                                              joined_now + membership_check_delay()),
                                          channel_title=title or None,
                                          strikes=0,
                                          note="جوین شدم" if msg == "joined"
                                               else "از قبل عضو بودم")
                            eng.log("ok", "ex_join", f"#{rec['id']} {rec['link']}")

                            # ریپلای «جوین شدم» روی پیام خود طرف
                            sent_reply = await reply_joined(eng.db.ex_get(rec["id"]))

                            if eng.ex_cfg().get("report_mode", "live") == "live":
                                await note(eng.ex_live_join_text(rec, title, sent_reply))
                        else:
                            if msg.startswith("FloodWait"):
                                eng.db.ex_set(rec["id"], note=msg)
                                try:
                                    _fw = int(re.search(r"FloodWait (\d+)s", msg).group(1))
                                except Exception:
                                    _fw = 0
                                if _fw >= 600:
                                    # جریمه‌ی سقف روزانه است — صادقانه توضیح بده
                                    _today = eng.db.ex_joins_today()
                                    await note(
                                        "🧯 **FloodWait " + secs(_fw) + "** — این جریمه‌ی "
                                        "**سقف تعداد جوین روزانه** است، نه فاصله‌ی کوتاه؛ "
                                        "تلگرام (مخصوصاً لینک خصوصی t.me/+…) جوینِ زیادِ "
                                        "یک‌روزه را ساعت‌ها می‌بندد.\n"
                                        f"امروز {fa(_today)} جوین زدم. تا پایان جریمه صبر "
                                        "می‌کنم و بعد با حداکثر فاصله ادامه می‌دهم.\n"
                                        "برای ریسک کمتر: «تبادل فاصله ۹۰ ۱۸۰» یا جوین کمتر در روز.")
                                else:
                                    await note(f"⏳ تبادل — {msg}\nصبر می‌کنم و ادامه می‌دهم.")
                            elif msg.startswith("درخواست عضویت"):
                                # درخواست عضویت با تأیید مدیر تمام نشده؛ شکست قطعی نیست.
                                eng.db.ex_set(rec["id"], status="pending", note=msg)
                                eng.log("info", "ex_join_pending", f"#{rec['id']} {msg}")
                                await note(f"⏳ درخواست عضویت برای `{rec['link']}` فرستاده شد.\n"
                                           "بعد از تأیید مدیر، `تبادل تأیید شماره` را بفرست.")
                            else:
                                transient = msg.startswith((
                                    "TimeoutError", "RPCError", "ConnectionError",
                                    "OSError", "NetworkError", "ServerError"))
                                if transient:
                                    eng.join_thr.penalize(15)
                                    eng.db.ex_set(rec["id"], status="approved",
                                                  note=f"تلاش دوباره بعد از خطای موقت: {msg}")
                                    eng.log("warn", "ex_join_retry", f"#{rec['id']} {msg}")
                                    await note(f"⏳ Join موقتاً نشد: `{rec['link']}` — {msg}؛ "
                                               "۱۵ ثانیه دیگر دوباره امتحان می‌کنم.")
                                else:
                                    # مهم: محدودیت ۵۰۰عضویت شکستِ خودِ لینک نیست.
                                    # رکورد را در صف نگه دار تا بعد از آزادشدن جا دوباره امتحان شود.
                                    account_limit = any(
                                        h in msg for h in ("حداکثر تعداد کانال",
                                                           "ChannelsTooMuch"))
                                    eng.db.ex_set(
                                        rec["id"],
                                        status="approved" if account_limit else "failed",
                                        note=msg,
                                    )
                                    kind = "ex_join_limit" if account_limit else "ex_join_fail"
                                    eng.log("warn", kind, f"#{rec['id']} {msg}")
                                    await note(f"❌ جوین نشد: `{rec['link']}` — {msg}")


                # صف Join مستقل و سریع می‌چرخد.
                await asyncio.sleep(1)

            except asyncio.CancelledError:
                raise
            except Exception as e:
                eng.log("error", "ex_worker", f"{type(e).__name__}: {e}")
                traceback.print_exc()
                await asyncio.sleep(15)

    async def sender_loop():
        while True:
            try:
                if eng.st["paused"]:
                    await asyncio.sleep(5)
                    continue
                did, nap = False, 5.0
                for tier in ("vip", "standard"):
                    ph, rem = eng.cyc[tier].phase()
                    if ph != "active":
                        nap = min(nap, max(2.0, min(30.0, rem)))
                        continue
                    w = eng.thr[tier].wait_time()
                    if w > 0:
                        nap = min(nap, min(w, 10.0))
                        continue
                    item = eng.db.next_pending(tier)
                    if item:
                        await deliver(item)
                        did = True
                if not did:
                    await asyncio.sleep(max(1.0, nap))
            except asyncio.CancelledError:
                raise
            except Exception as e:
                eng.log("error", "sender", f"{type(e).__name__}: {e}")
                traceback.print_exc()
                await asyncio.sleep(5)

    async def status_loop():
        """گزارشِ وضعیت + تشخیصِ «قفل‌شدنِ event loop».

        چرا: بزرگ‌ترین دلیلِ «اکانت آفلاین شد» یک کارِ همگامِ طولانی در
        همان loop است (مثلِ انتخابِ کاندیدِ پاکسازی که قبلاً O(n²) بود و
        روی ۱۰۰۰ رکورد ۶۱ ثانیه CPU می‌گرفت). آن‌وقت هیچ پینگ/پاسخی
        نمی‌رود و تلگرام اتصال را می‌بندد. حالا هر تأخیرِ محسوس در همین
        حلقه ثبت می‌شود تا علت از لاگ معلوم باشد.
        """
        last_tick = time.time()
        while True:
            try:
                now_tick = time.time()
                lag = int(now_tick - last_tick - 60)
                last_tick = now_tick
                if lag >= LOOP_LAG_WARN_SEC:
                    eng.log("warn", "loop_lag", f"{lag}s")
                    try:
                        eng.write_status({"loop_lag_sec": lag,
                                          "loop_lag_at": int(now_tick)})
                    except Exception:
                        pass
                else:
                    eng.write_status()
            except Exception:
                pass
            await asyncio.sleep(60)

    async def report_loop():
        """گزارش خلاصه را فقط در حالت summary و فقط در PV ارسال می‌کند."""
        while True:
            try:
                x = eng.ex_cfg()
                manual = bool(x.pop("_report_now", False))
                if manual:
                    await note(eng.ex_report_text())
                    await asyncio.sleep(1)
                    continue
                elif x.get("report_mode", "live") == "summary":
                    interval = max(3600, int(x.get("report_summary_interval_sec", 86400) or 86400))
                    now_r = int(time.time())
                    last = int(x.get("report_last_sent", 0) or 0)
                    if not last:
                        x["report_last_sent"] = now_r
                        eng.st.save()
                    elif now_r - last >= interval:
                        counts = eng.db.ex_report_counts(last)
                        if any(counts[k] for k in ("joined", "left", "failed")):
                            await note(eng.ex_report_text(last))
                        x["report_last_sent"] = now_r
                        eng.st.save()
                await asyncio.sleep(30)
            except asyncio.CancelledError:
                raise
            except Exception as e:
                eng.log("error", "report_loop", f"{type(e).__name__}: {e}")
                await asyncio.sleep(30)

    async def risk_loop():
        """محافظ ریپورت، دو لایه:
          ۱) پایشِ «واقعی» (همیشه فعال): فقط وقتی اکانت واقعاً در مرز ریپ است
             (FloodWait/خطاهای واقعی) تبادل را اجباراً خاموش می‌کند. در حالت
             پیش‌فرض روشن می‌ماند حتی اگر «توقف بر امتیاز» خاموش باشد.
          ۲) توقف بر «امتیازِ انتزاعی» (خاموش در حالت پیش‌فرض): فقط وقتی
             روی=True باشد.
        هر لایه خاموشیِ «خودش» را برمی‌گرداند و یک قفلِ موقت (`_off_until`)
        و دلیل (`_off_reason`) دارد تا وقتی هر دو فعال‌اند، خاموشیِ یکی توسط
        دیگری فوراً باطل نشود. ضد اسپمِ نوتیف نیز دارد."""
        while True:
            try:
                rc = eng.st["risk"]
                x = eng.ex_cfg()
                now_t = int(time.time())
                auto_off = bool(rc.get("_auto_off"))
                off_until = int(rc.get("_off_until", 0) or 0)
                off_reason = str(rc.get("_off_reason", "") or "")

                # ── تصمیم‌های خاموشیِ هر لایه ──
                stop_hard = False
                hard_meta = {}
                if rc.get("hard_on", True):
                    edge, rparts, hard_meta = eng.real_risk_edge(now_t)
                    stop_hard = bool(edge)
                stop_score = False
                risk = None
                if rc.get("on", True):
                    risk, _p, _m = eng.risk_current()
                    stop_score = bool(risk >= float(rc.get("trigger", 75)))

                # ── خاموشی (اجباری) ──
                if x["enabled"] and (stop_hard or stop_score):
                    x["enabled"] = False
                    rc["_auto_off"] = True
                    rc["_last_off"] = now_t
                    rc["_off_reason"] = "hard" if stop_hard else "score"
                    rc["_off_until"] = now_t + (600 if stop_hard else 120)
                    rc["_auto_off"] = True
                    rc["_last_alert"] = now_t
                    eng.st.save()
                    if stop_hard:
                        eng.log("warn", "risk_hard_off",
                                f"مرز ریپ (امتیاز واقعی {hard_meta.get('score')}) → تبادل خاموش")
                        await note(f"🛡 **محافظ ریپورت — توقف اجباری**: اکانت در مرز ریپ است "
                                   f"(امتیازِ واقعی {hard_meta.get('score')}، فلاد "
                                   f"{hard_meta.get('flood')}/{hard_meta.get('fails_10')} خطا در ۱۰د). "
                                   "تبادل را **خاموش** کردم تا اکانت در امان بماند.\n"
                                   f"`ریسک بررسی` برای جزئیات")
                    else:
                        eng.log("warn", "risk_off",
                                f"ریسک {risk}% >= {float(rc.get('trigger', 75)):.0f}% → تبادل خاموش")
                        await note(f"🛡 **محافظ ریپورت**: ریسک به {risk}% رسید "
                                   f"(آستانه {float(rc.get('trigger', 75)):.0f}%)، تبادل را "
                                   "**خاموش** کردم. اکانت در امان است.\n"
                                   f"`ریسک بررسی` برای جزئیات")
                # ── بازگشایی (فقط خاموشیِ همان لایه، بعد از قفلِ موقت) ──
                elif (auto_off and not x["enabled"]
                      and now_t >= off_until
                      # قاعده‌ی «اول کانال»: بازگشاییِ خودکار هم بدون کانال
                      # نباید تبادل را روشن کند؛ وگرنه پنل «روشن» نشان
                      # می‌دهد ولی هیچ کاری انجام نمی‌شود.
                      and eng.ex_channel_ready()
                      and ((off_reason == "hard" and not (rc.get("hard_on", True) and stop_hard))
                           or (off_reason == "score"
                               and (risk is not None)
                               and risk < float(rc.get("resume", 55))))):
                    x["enabled"] = True
                    rc["_auto_off"] = False
                    rc["_off_until"] = 0
                    rc["_off_reason"] = ""
                    rc["_last_alert"] = now_t
                    eng.st.save()
                    eng.log("info", "risk_on",
                            f"{off_reason} رفع شد → تبادل روشن")
                    await note(f"🛡 خطرِ ریپ برطرف شد (دلیل: {off_reason}). "
                               "تبادل را دوباره **روشن** کردم.")
                # ── هشدار پیشگیرانه نزدیک‌بودن به آستانه‌ی امتیاز ──
                elif (not auto_off and x["enabled"] and rc.get("on", True)
                      and 0.9 * float(rc.get("trigger", 75)) <= risk < float(rc.get("trigger", 75))
                      and now_t - int(rc.get("_last_alert", 0) or 0) > 3600):
                    rc["_last_alert"] = now_t
                    eng.st.save()
                    await note(f"⚠️ ریسک ریپورت به {risk}% رسید "
                               f"(آستانه {float(rc.get('trigger', 75)):.0f}%). "
                               "به‌زودی تبادل خاموش می‌شود.")
            except asyncio.CancelledError:
                raise
            except Exception as e:
                eng.log("error", "risk_loop", f"{type(e).__name__}: {e}")
            await asyncio.sleep(max(10, int(eng.st["risk"].get("check_interval_sec", 60) or 60)))

    async def memory_loop():
        """هر ۱۰ دقیقه: کش‌های بی‌سقف را کوتاه کن (نشتیِ آرامِ حافظه).

        بدونِ این، حافظه‌ی هر اکانت در طولِ هفته‌ها فقط بالا می‌رفت و تنها
        راهِ برگشتنش ری‌استارت بود.
        """
        while True:
            try:
                n = trim_entity_cache(client)
                if n:
                    print(f"  🧹 {n} موجودیتِ قدیمی از کشِ تلگرام آزاد شد",
                          flush=True)
                m = trim_link_cache(eng)
                if m:
                    print(f"  🧹 {m} لینکِ قدیمی از کش آزاد شد", flush=True)
            except asyncio.CancelledError:
                raise
            except Exception:
                pass
            await asyncio.sleep(600)

    task = asyncio.create_task(sender_loop())
    ex_task = asyncio.create_task(exchange_worker())
    scan_task = asyncio.create_task(scan_loop())
    member_task = asyncio.create_task(membership_loop())
    report_task = asyncio.create_task(report_loop())
    risk_task = asyncio.create_task(risk_loop())
    st_task = asyncio.create_task(status_loop())
    mem_task = asyncio.create_task(memory_loop())

    await note(_startup_text())

    # خطای اولیه‌ای که باعث ورود به پاک‌سازی شد را نگه می‌داریم؛ اگر لغوِ
    # بیرونی (CancelledError) بود، در پایان دوباره پرتاب می‌شود تا خاموشی
    # واقعاً کامل گردد و بی‌جهت بلعیده نشود.
    _shutdown_exc = None
    try:
        await client.run_until_disconnected()
    except BaseException as _e:
        _shutdown_exc = _e
    finally:
        for t in (task, ex_task, scan_task, member_task, report_task, risk_task,
                  st_task, mem_task):
            t.cancel()
        # دور awaitهای پاک‌سازی فقط except Exception می‌گذاریم؛ لغوِ بیرونی
        # اینجا بلعیده نمی‌شود (gather با return_exceptions خطای لغوِ فرزندها
        # را به‌جای پرتاب به‌عنوان نتیجه جمع می‌کند) ولی پاک‌سازیِ همه‌ی
        # فرزندها کامل انجام می‌شود.
        try:
            await asyncio.gather(task, ex_task, scan_task, member_task,
                                 report_task, risk_task, st_task, mem_task,
                                 return_exceptions=True)
        except Exception:
            pass

    if isinstance(_shutdown_exc, asyncio.CancelledError):
        raise _shutdown_exc
    if _shutdown_exc is not None:
        raise _shutdown_exc
    eng.log("warn", "disconnected", "اتصال قطع شد")
    # «lost» یعنی وصل شده بود و بعد قطع شد (شبکه‌ی لرزان) — با «retry»
    # (نتوانست اصلاً وصل شود) قاطی نشود تا شمارنده‌ی شکستِ اتصال درست کار کند.
    return "lost"


async def run_bot():
    print(f"\n{BUILD_TAG}", flush=True)
    if need_telethon():
        print("\n📦 Telethon نصب نیست — نصبش می‌کنم…")
        os.system(f'"{sys.executable}" -m pip install telethon')
        if need_telethon():
            print("\n❌ نصب خودکار نشد. دستی بزن:\n\n   pip install telethon\n")
            return 1

    creds = ensure_creds()
    if not creds:
        return 1

    eng = Engine()
    print(f"\n{'═' * 50}\n  جفج {VERSION} — سلف‌بات تلگرام\n{'═' * 50}", flush=True)
    print(f"  شماره: {creds.get('phone') or 'هنوز نیست — پایین ازت می‌پرسد'}", flush=True)
    if os.path.exists(SESSION + ".session"):
        print("  سشن از قبل هست؛ اگر وصل شود دیگر شماره نمی‌پرسد.", flush=True)

    log_egress_ip()
    try:
        max_fails = int(os.environ.get("JAFJ_MAX_CONNECT_FAILS", "") or 12)
    except Exception:
        max_fails = 12
    max_fails = max(3, max_fails)
    backoff = 10
    fails = 0
    while True:
        try:
            r = await connect_and_run(eng, creds)
            if r == "stop":
                return 1
            if r == "key_burned":
                # سشن سوخته — هیچ تلاشی نجاتش نمی‌دهد؛ سریع و صریح تمام کن
                # تا مدیر اکانت را «نیاز به لاگین» کند و مشتری منتظر نماند.
                print("\n⛔ تا لاگینِ دوباره، این سشن اجرا نمی‌شود (کلید باطل "
                      "شده).", flush=True)
                return EXIT_KEY_BURNED
            if r == "needs_relogin":
                # عمداً retry نمی‌کنیم: هر تلاشِ دوباره = یک کدِ ورودِ تازه
                # برای مشتری. مدیر باید از پنل دوباره لاگین کند.
                print("\n⛔ تا لاگینِ دوباره از پنل، این سرویس اجرا نمی‌شود.",
                      flush=True)
                return EXIT_NEEDS_RELOGIN
            if r == "lost":
                fails = 0                      # وصل شده بود؛ شمارنده صفر
                backoff = 10
            else:
                fails += 1
                if fails >= max_fails:
                    print(f"\n⛔ {fails} بارِ پشتِ‌سرهم نتوانستم به تلگرام وصل "
                          f"شوم.", flush=True)
                    print("   یعنی شبکه/MTProto از این میزبان باز نمی‌شود؛ "
                          "تلاشِ دوباره در همین پروسه فایده ندارد.", flush=True)
                    print("   IPِ خروجی همین بالا در لاگ هست — با اجرای قبل "
                          "مقایسه‌اش کن.", flush=True)
                    return EXIT_NET_DEAD
        except KeyboardInterrupt:
            raise
        except Exception as e:
            eng.log("error", "fatal", f"{type(e).__name__}: {e}")
            traceback.print_exc()
        print(f"\n🔄 اتصال قطع شد — {backoff} ثانیه دیگر دوباره وصل می‌شوم…")
        print("   (پیام‌های صف حفظ شده‌اند. Ctrl+C برای خروج)")
        await asyncio.sleep(backoff)
        # سقفِ ۹۰ ثانیه (نه ۳۰۰): هر ثانیه‌ی این انتظار، اکانت «آفلاین» است.
        backoff = min(backoff * 2, 90)


def main():
    # «۹۵.py اجرا شد یا نه؟» باید از خودِ لاگ معلوم باشد؛ وگرنه هر کسی از
    # بیرون حدس می‌زند که فایل اجرا نشده، در حالی که اجرا شده و مثلاً روی
    # اتصال شکست خورده است.
    print(f"\n▶️ 95.py اجرا شد | pid={os.getpid()} | python={sys.executable} "
          f"| cwd={os.getcwd()}", flush=True)
    ok, other = acquire_run_lock()
    if not ok:
        print("\n" + "─" * 52, flush=True)
        print(f"⛔ نسخه‌ی دیگری از همین اکانت همین حالا در حال اجراست (pid={other}).",
              flush=True)
        print("   دو سلف روی یک سشن، اتصال را بی‌پایان قطع می‌کند («اتصال قطع شد»).",
              flush=True)
        print("   این نسخه اجرا نشد تا سشنِ سالم خراب نشود.", flush=True)
        print(f"   اگر مطمئنی آن پروسه مرده است: rm {RUN_LOCK}", flush=True)
        return 76
    try:
        return asyncio.run(run_bot())
    except KeyboardInterrupt:
        print("\n\nخاموش شد. صف و تنظیمات ذخیره شدند.")
        return 0
    finally:
        release_run_lock()


if __name__ == "__main__":
    sys.exit(main())
