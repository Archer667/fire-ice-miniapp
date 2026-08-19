# 🏰 والریا : سیزن اول — Telegram Mini App کامل

> هر تصمیم، یک پیامد . هر انتخاب، یک سرنوشت .

```
fire-ice/
├── frontend/   React + Vite — رابط بازیکن (طراحی v4، Nav شناور)
└── backend/    FastAPI + MongoDB — منطق بازی و API
```

## چی کار می‌کند (همین الان)

| قابلیت | وضعیت |
|--------|-------|
| احراز هویت واقعی تلگرام (initData + HMAC) | ✅ |
| ثبت‌نام دومرحله‌ای: ۹ اقلیم → ~۸۰ قلعه، هر قلعه فقط یک لرد | ✅ |
| تولید روزانهٔ منابع (lazy — بدون cron) | ✅ |
| محبوبیت بر پایهٔ مالیات، سهم غله، ضیافت و نتیجهٔ جنگ | ✅ |
| شورش با تاسِ روزانه، رولِ ۲۴ساعته، پیام تلگرام و داوریِ ادمین | ✅ |
| ارسال سناریوی جنگ + کسر طلا + اعتبارسنجی | ✅ |
| نقشه: لشکرکشی‌ها با تأخیر ۱۵ دقیقه آشکار می‌شوند | ✅ |
| کلاغ‌ها: نامهٔ خصوصی بین لردها + صندوق + گفتگو | ✅ |
| لیدربورد زنده بر اساس امتیاز | ✅ |
| پنل ادمین گرافیکی: بازیکن‌ها، جنگ و رول، شورش، رویداد، نقشه، بازار و تعادل | ✅ |
| حالت mock: بدون Backend هم UI کامل کار می‌کند | ✅ |

## راه‌اندازی — ۴ گام (بدون npm روی لپ‌تاپ)

### گام ۱ — MongoDB Atlas (رایگان، ۵ دقیقه)
1. mongodb.com/cloud/atlas → ثبت‌نام → Create Cluster (M0 رایگان)
2. Database Access → یوزر و پسورد بساز
3. Network Access → `0.0.0.0/0` (Allow from anywhere)
4. Connect → Drivers → Connection String را کپی کن

### گام ۲ — Backend روی Render (رایگان، ۵ دقیقه)
1. کل پروژه را به GitHub بفرست (VSCode → Publish to GitHub)
2. render.com → New → Web Service → ریپو را وصل کن
3. **Root Directory: `backend`**
4. Build: `pip install -r requirements.txt`
   Start: `uvicorn main:app --host 0.0.0.0 --port $PORT`
5. Environment → این‌ها را اضافه کن:
   ```
   BOT_TOKEN=توکن_از_BotFather
   MONGODB_URI=از_گام_۱
   ADMIN_IDS=آیدی_عددی_تلگرامت
   CORS_ORIGINS=https://آدرس-vercel-تو.vercel.app
   ```
   (`PUBLIC_BASE_URL` و `MINI_APP_URL` را بعداً تو گام ۴ اضافه می‌کنی — الان آدرس هیچ‌کدام را نداری)
6. Deploy → آدرس بگیر: `https://fire-ice-api.onrender.com`
7. تست: `آدرس/api/health` باید `{"ok":true}` بدهد

### گام ۳ — Frontend روی Vercel (۵ دقیقه)
1. vercel.com → New Project → همان ریپو
2. **Root Directory: `frontend`**
3. Environment Variables:
   ```
   VITE_API_URL=https://fire-ice-api.onrender.com
   ```
4. Deploy → آدرس: `https://fire-ice.vercel.app`

### گام ۴ — اتصال به بات (۲ دقیقه)

**روش ۱ — Menu Button (بدون کد، همیشه کار می‌کند):**
```
@BotFather → /mybots → بات تو → Bot Settings
→ Menu Button → آدرس Vercel را بده
```
بات را باز کن → دکمهٔ منو → 🎮 بازی داخل تلگرام!

**روش ۲ — فعال‌کردن دستور `/start`:** بات وقتی کسی `/start` می‌زند یک پیام خوش‌آمد
با دکمهٔ «ورود به بازی» برایش می‌فرستد. برای این یکی، برخلاف روش ۱، به کد نیازی
نیست — کدش از قبل تو بک‌اند هست، فقط باید دو تا Environment Variable روی Render
اضافه کنی (بعد از این‌که آدرس هر دو سرویس را از گام‌های ۲ و ۳ داری):
```
PUBLIC_BASE_URL=https://fire-ice-api.onrender.com   ← آدرس همین Backend (گام ۲)
MINI_APP_URL=https://fire-ice.vercel.app             ← آدرس Frontend (گام ۳)
```
بعد از اضافه‌کردن، Render را دوباره Deploy کن — بک‌اند موقع بالاآمدن خودش webhook
را پیش تلگرام ثبت می‌کند (نیازی به دستور دستی نیست). از اون به بعد `/start` هم
همون دکمهٔ «ورود به بازی» را می‌فرستد.

## تست بدون سرور
`VITE_API_URL` را خالی بگذار → حالت mock: کل UI با دیتای نمایشی کار می‌کند.
تست لوکال backend: در `.env` بگذار `DEV_MODE=true` — آنگاه هدر `X-Dev-User: 1:نام` جای تلگرام را می‌گیرد.

## ادمین — کنترل شورش‌ها

از پنل ادمین وارد تبِ «شورش‌ها» شو. ادمین‌ها پرونده، محبوبیت، شانس و رولِ بازیکن رو می‌بینن و
نتیجه رو همراه با تغییرِ محبوبیت، طلا، غله یا نفرات ثبت می‌کنن. ادمینِ کامل می‌تونه مرزهای
محبوبیت، درصدِ تاس، مصرفِ غله، اثرِ مالیات و جنگ، مهلتِ رول و ضیافت رو هم از همون‌جا تغییر بده.

جزئیاتِ کار برایِ بازیکن تو [راهنمای بازیکن](docs/PLAYER_GUIDE.md)، کنترل‌ها تو
[راهنمای ادمین](docs/ADMIN_GUIDE.md) و معماری و APIها تو
[راهنمای دولوپر](docs/DEVELOPER_GUIDE.md) نوشته شده.

## نقشهٔ فازهای بعد
WebSocket برای کلاغ‌های زنده → گزارش‌ها و نمودارهای مدیریتی → رویدادهای تصادفیِ گسترده‌تر
