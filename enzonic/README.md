# `enzonic/` — پوشهٔ اپ برای Enzonic Deploy

این پوشه برای همان خطای اولِ Enzonic است:

```
Framework: Dockerfile (project setting)
Error: Dockerfile projects cannot be built yet: Enzonic Deploy builds Node.js,
       Bun, Python and Go apps from source. Set the root directory to the app's
       folder or pick a framework preset in the project settings
```

Enzonic فعلاً ایمیج نمی‌سازد. ریشهٔ این ریپو یک `Dockerfile` دارد (برای
blitz.cloud، Render و Railway) و همین باعث می‌شود تشخیصِ خودکار روی
`Dockerfile` بماند. این پوشه **هیچ Dockerfile‌ای ندارد** و فقط همان چیزی را
دارد که بیلدِ سورسی لازم دارد — یعنی همان «app's folder» که پیامِ خطا می‌گوید.

## دو راه (اولی ساده‌تر است)

**راه ۱ — preset را عوض کن (توصیه‌شده):**

| فیلد | مقدار |
| --- | --- |
| Framework | `Python` |
| Root directory | `/` (ریشهٔ ریپو) |
| Install | `pip install -r requirements.txt` |
| Start command | `sh start.sh` |

**راه ۲ — اگر dropdown روی `Dockerfile` گیر کرده / گزینهٔ Python نیست:**

| فیلد | مقدار |
| --- | --- |
| Root directory | `enzonic` |
| Framework | `Python` (یا هر چیزی که خودش تشخیص داد) |
| Install | `pip install -r requirements.txt` |
| Start command | `sh start.sh` |

در هر دو حالت فقط یک اسکریپت اجرا می‌شود:

```
enzonic/start.sh  →  ../start.sh  →  hostless-start.sh  →  railway-start.sh
```

یعنی هیچ منطقی تکرار نشده و کدِ ربات همان چک‌اوت است (نه یک کپیِ دوم).

## نکته‌ها

- این پوشه باید **داخلِ** همان clone باشد؛ اگر پلتفرم فقط محتوای
  `enzonic/` را کپی کند، `start.sh` با پیامِ روشن (`the repository root is not
  next to this folder`) می‌ایستد تا معلوم باشد کدام تنظیم غلط است.
- `requirements.txt` اینجا فقط `-r ../requirements.txt` است؛ نسخه‌های پکیج
  همان‌جای اصلی نگه داشته می‌شوند.
- `PORT` را پلتفرم می‌دهد؛ `DATA_DIR` خودکار انتخاب می‌شود. اگر دیسکِ
  ماندگار داری روی `/data` وصل کن، وگرنه `DATA_GITHUB_TOKEN` را ست کن —
  وگرنه `manager.db`/`shop.db`/`clients/` با هر دیپلوی پاک می‌شوند.

راهنمای کامل: [`../ENZONIC_DEPLOY_FA.md`](../ENZONIC_DEPLOY_FA.md)
