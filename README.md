# 🏰 نغمه آتش و یخ — Telegram Mini App کامل

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
| ارسال سناریوی جنگ + کسر طلا + اعتبارسنجی | ✅ |
| نقشه: لشکرکشی‌ها با تأخیر ۱۵ دقیقه آشکار می‌شوند | ✅ |
| کلاغ‌ها: نامهٔ خصوصی بین لردها + صندوق + گفتگو | ✅ |
| لیدربورد زنده بر اساس امتیاز | ✅ |
| API ادمین: صف سناریوها، تأیید/رد + امتیازدهی، برگشت طلا هنگام رد | ✅ |
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
```
@BotFather → /mybots → بات تو → Bot Settings
→ Menu Button → آدرس Vercel را بده
```
بات را باز کن → دکمهٔ منو → 🎮 بازی داخل تلگرام!

## راه‌اندازی روی Railway (همه‌چیز یک‌جا)

Railway نمی‌تواند Backend و Frontend را در یک سرویس اجرا کند — باید **دو سرویس جدا** در همان پروژهٔ Railway بسازید.

### سرویس ۱ — Backend
1. New Service → Deploy from GitHub Repo → همان ریپو
2. Settings → **Root Directory: `backend`**
3. `Procfile` همراه پروژه هست (`uvicorn main:app --host 0.0.0.0 --port $PORT`) — نیازی به تنظیم دستی Start Command نیست
4. Variables:
   ```
   BOT_TOKEN=...
   MONGODB_URI=...
   DB_NAME=fire_ice
   ADMIN_IDS=...
   CORS_ORIGINS=آدرس-سرویس-فرانت‌اند-Railway  (بعد از ساخت سرویس ۲ پر کن)
   ```
5. Settings → Networking → **Generate Domain** → آدرس را کپی کن، مثلاً `https://fire-ice-backend-production.up.railway.app`

### سرویس ۲ — Frontend
1. همان پروژهٔ Railway → New Service → Deploy from GitHub Repo → همان ریپو
2. Settings → **Root Directory: `frontend`**
3. `Procfile` همراه پروژه هست (`npm run start` → `vite preview --host 0.0.0.0 --port $PORT`)
4. Variables:
   ```
   VITE_API_URL=آدرس-سرویس-Backend-از-مرحلهٔ-قبل   (مثلاً https://fire-ice-backend-production.up.railway.app)
   ```
   (چون `VITE_API_URL` موقع build خوانده می‌شود، هر بار عوضش کردی باید Redeploy بزنی)
5. Settings → Networking → **Generate Domain** → این آدرس همان آدرسی است که به بات تلگرام می‌دهی

### وصل کردن دو سرویس به هم
- برو توی سرویس Backend → Variables → `CORS_ORIGINS` را برابر آدرس سرویس Frontend بگذار
- برو توی سرویس Frontend → Variables → `VITE_API_URL` را برابر آدرس سرویس Backend بگذار
- هر دو سرویس را Redeploy کن

### تست
- `آدرس-Backend/api/health` → باید `{"ok":true}` بدهد (خود ریشهٔ `/` بک‌اند عمداً 404 می‌دهد، طبیعی است)
- `آدرس-Frontend/` → باید صفحهٔ بازی باز شود

## تست بدون سرور
`VITE_API_URL` را خالی بگذار → حالت mock: کل UI با دیتای نمایشی کار می‌کند.
تست لوکال backend: در `.env` بگذار `DEV_MODE=true` — آنگاه هدر `X-Dev-User: 1:نام` جای تلگرام را می‌گیرد.

## ادمین — داوری سناریوها (فعلاً با API)
```bash
# لیست در انتظار
curl -H "X-Dev-User: <ADMIN_ID>:ادمین" https://API/api/admin/pending

# تأیید + امتیاز
curl -X POST https://API/api/admin/<id>/approve \
  -H "Content-Type: application/json" -H "X-Dev-User: <ADMIN_ID>:ادمین" \
  -d '{"verdict":"حمله موفق بود — قلعه سقوط کرد","points_delta":150}'
```
(پنل ادمین گرافیکی = فاز بعدی)

## نقشهٔ فازهای بعد
ساخت‌وساز و پادگان (endpoint + صفحه) → پنل ادمین گرافیکی → جاسوسی و دیپلماسی → WebSocket برای کلاغ‌های زنده → رویدادهای تصادفی
