# اجرا روی Enzonic Deploy (بیلد از سورس) — «Dockerfile projects cannot be built yet»

این سند مربوط به همین خطاست، در اولین بیلد روی Enzonic Deploy:

```
Framework: Dockerfile (project setting) → mode: server
Note: Dockerfile projects are not supported yet.
       Enzonic Deploy builds Node.js, Bun, Python and Go apps from source.
Error: Dockerfile projects cannot be built yet: Enzonic Deploy builds Node.js,
       Bun, Python and Go apps from source. Set the root directory to the app's
       folder or pick a framework preset in the project settings
```

---

## ۱) پیام چه می‌گوید (و چه نمی‌گوید)

| بخشِ پیام | معنی |
|---|---|
| `Framework: Dockerfile (project setting)` | پلتفرم از تنظیماتِ پروژه (`Dockerfile`) خوانده که فریمورک را Docker در نظر بگیرد. |
| `Dockerfile projects are not supported yet` | Enzonic فعلاً **ایمیج نمی‌سازد**. |
| `builds Node.js, Bun, Python and Go apps from source` | تنها راه: نصبِ پکیج‌ها از سورس (`requirements.txt`) و اجرای یک دستورِ start. |
| `Set the root directory… or pick a framework preset` | خودش راه‌حل را می‌گوید: preset را عوض کن (یا root directory را روی پوشهٔ اپ بگذار). |

**این خطا دربارهٔ کد نیست.** کد سالم است؛ فقط حالتِ بیلد اشتباه انتخاب شده.
`Dockerfile` این ریپو دست نمی‌خورد — روی Render، Railway و blitz.cloud همان
چیزی است که سرویس را بالا می‌آورد و باید سر جایش بماند.

---

## ۲) تنظیماتِ درست (تنها کاری که باید بکنی)

Enzonic → پروژهٔ `jfjj` → **Settings**:

| فیلد | مقدار |
| --- | --- |
| **Framework** | `Python` — **نه** `Dockerfile` |
| **Root directory** | ریشهٔ ریپو (`/`) |
| **Python version** | `3.11` (همان `.python-version`؛ `3.12+` تست نشده) |
| **Install command** | `pip install -r requirements.txt` |
| **Start command** | `sh start.sh` |
| **Port** | آنچه پلتفرم می‌دهد (`PORT`) — دست نزن |
| **Health check path** | `/healthz` |
| **Service type** | web/bot (نه workerِ یک‌بارمصرف) |

بعد **Redeploy**.

اگر فیلدِ Start command را خالی بگذاری، Enzonic سراغ `Procfile` می‌رود:

```
web: sh start.sh
```

و بیلدهای Nixpacks سراغ `nixpacks.toml`:

```toml
[start]
cmd = "sh start.sh"
```

پس در هر سه حالت یک مقصد اجرا می‌شود.

### متغیرهای محیطی

| متغیر | لازم؟ | کار |
| --- | --- | --- |
| `BOT_TOKEN` | **بله** | توکنِ رباتِ مدیر |
| `DATA_GITHUB_TOKEN` | عملاً بله (بدون دیسک) | بازگردانی و pushِ دوره‌ایِ داده با `tools/gh_data_sync.py` |
| `DATA_GITHUB_REPO` | اختیاری | ریپوی داده، اگر با ریپوی کد یکی نیست |
| `BACKUP_CHAT` | اختیاری | مقصدِ پشتیبان |
| `BOT_TZ` | اختیاری | منطقهٔ زمانی |
| `DATA_DIR` | اختیاری | پوشهٔ داده (پیش‌فرض: `/data` → `$JAFJ_DATA_MOUNT` → `$HOME/jafj-data` → پوشهٔ کد) |
| `PORT` | — | را خودِ پلتفرم می‌دهد؛ ست نکن |

---

## ۳) بیلدِ سورسی چه چیزی ندارد (مهم‌ترین بخش)

`Dockerfile` سه کارِ اضافه می‌کند که در بیلدِ سورسی **انجام نمی‌شود**:

| در ایمیج | در بیلدِ سورسی |
| --- | --- |
| کد در `/opt/jafj` کپی می‌شود (پوشهٔ غیرقابل‌تغییر) | کد از خودِ چک‌اوت اجرا می‌شود (`JAFJ_IMAGE_DIR=$HERE`) |
| `VOLUME ["/data"]` → داده بین ری‌استارت‌ها می‌ماند | هیچ دیسکی خودکار ماندگار نیست |
| `DATA_DIR=/data` برای blitz | `DATA_DIR` از اولین مسیرِ قابل‌نوشتن انتخاب می‌شود |

نتیجه‌های عملی:

1. **اگر دیسکِ ماندگار داری**، آن را روی `/data` وصل کن (یا `DATA_DIR=/data`
   بگذار). وگرنه `manager.db`، `shop.db`، `manager_bot.string` و
   `clients/<uid>/` با هر دیپلوی پاک می‌شوند — همان «ربات هر چند ساعت همه‌چیز
   را فراموش می‌کند».
2. **اگر دیسک نداری**، `DATA_GITHUB_TOKEN` عملاً اجباری است. ری‌استارتِ
   اسکریپت‌ها داده را نگه می‌دارد؛ دیپلوی نه.
3. لاگِ بوت این خط را دارد و تکلیف را روشن می‌کند:

   ```
   HOSTLESS: code=/app data=/home/user/jafj-data port=8080
   ```

   اگر `data` با `code` یکی بود، هشدارِ `WARNING: data is living next to the
   code` هم می‌آید — یعنی داده ماندگار نیست.

---

## ۴) راستی‌آزمایی بعد از دیپلوی

1. `https://<app>/healthz` → باید `200` بدهد. (وب‌سرورِ سلامت هنگامِ import
   بالا می‌آید، **قبل** از لاگینِ تلگرام؛ پس حتی اگر توکن نداشته باشی هم
   پاسخ می‌دهد و «سرویس مرده» گزارش نمی‌شود.)
2. `https://<app>/version` → کامیت و `code=` را نشان می‌دهد؛ یعنی همان کدی
   که push کردی اجرا می‌شود.
3. در ربات `/diag` → باید «داده: …» و **«بوت سرد: نه»** بدهد. اگر «بله» داد،
   داده ماندگار نیست (بندِ ۳).

خطاهای رایج و معنی‌شان:

| نشانه | معنی | کار |
| --- | --- | --- |
| `Dockerfile projects cannot be built yet` | preset روی Dockerfile است | Framework = Python |
| `No start command could be found` | start command خالی و `Procfile`/`nixpacks.toml` خوانده نشده | `sh start.sh` را دستی بگذار |
| `The process stopped soon after it started · Exit code 0` | پروسه با موفقیت تمام شده، یعنی سرویس نیست | `sh start.sh` (نه `python main.py`)؛ `start.sh` با `JAFJ_HOSTED=1` خروجِ ۰ را کرش می‌شمارد |
| `ModuleNotFoundError: telethon` | install اجرا نشده یا requirements خوانده نشده | Install = `pip install -r requirements.txt` |
| بوت می‌شود ولی بعد از دیپلوی همه‌چیز صفر | `DATA_DIR` ماندگار نیست | دیسک روی `/data` یا `DATA_GITHUB_TOKEN` |
| ربات خاموش می‌شود بعد از بی‌کاری | اپِ sleeping در پلنِ رایگان | پلنِ همیشه‌بیدار یا مانیتورِ HTTP روی `/healthz` هر ۵ دقیقه |

---

## ۵) چرا `Dockerfile` را حذف نمی‌کنیم

چون میزبان‌های فعلی/جایگزین با آن کار می‌کنند و برایشان تنها راه است:

- **blitz.cloud** — ایمیج می‌سازد و فقط پوشه‌های `VOLUME` را نگه می‌دارد.
- **Render** — `render.yaml` با `dockerfilePath: ./Dockerfile` و
  `dockerCommand: sh /opt/jafj/render-start.sh`.
- **Railway** — `railway.json` با `"builder": "dockerfile"`.

حذف یا جابه‌جا کردنِ `Dockerfile` این سه را می‌شکند (و تست‌های
`tests/test_blitz_host.py`، `tests/test_hostless_host.py`،
`tests/test_render_host.py` هم دقیقاً همین را قفل کرده‌اند). پس راهِ درست:
`Dockerfile` سر جایش، و برای Enzonic فقط **preset** را Python کن.

---

## ۶) خلاصهٔ یک‌خطی

> کد آماده است (`requirements.txt` + `start.sh` + `Procfile`)؛ در Enzonic فقط
> `Framework = Python` و `Start = sh start.sh` را بگذار و یک دیسک روی `/data`
> (یا `DATA_GITHUB_TOKEN`) بده.
