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

## راه‌اندازی — همه‌چیز روی Railway (یک سرویس)

پروژه با یک `Dockerfile` در ریشهٔ ریپو ساخته می‌شود: مرحلهٔ اول Frontend را build می‌کند،
مرحلهٔ دوم آن را داخل همان سرویس FastAPI سرو می‌کند. یعنی فقط **یک** سرویس روی Railway
لازم است و Vercel/Render دیگر نیازی نیستند.

### گام ۱ — MongoDB Atlas (رایگان، ۵ دقیقه)
1. mongodb.com/cloud/atlas → ثبت‌نام → Create Cluster (M0 رایگان)
2. Database Access → یوزر و پسورد بساز
3. Network Access → `0.0.0.0/0` (Allow from anywhere)
4. Connect → Drivers → Connection String را کپی کن (به‌جای `<db_password>` پسورد واقعی را بگذار)

### گام ۲ — سرویس روی Railway (۵ دقیقه)
1. کل پروژه را به GitHub بفرست
2. railway.com → New Project → Deploy from GitHub repo → همین ریپو
3. **Root Directory را خالی بگذار (ریشهٔ ریپو)** — نه `backend`
4. Railway به‌طور خودکار `Dockerfile` ریشه را پیدا و با آن build می‌کند
5. Settings → Variables → این‌ها را اضافه کن:
   ```
   BOT_TOKEN=توکن_از_BotFather
   MONGODB_URI=connection string از گام ۱ (با پسورد واقعی)
   ADMIN_IDS=آیدی عددی تلگرامت
   ```
6. Deploy → یک دامنهٔ عمومی بگیر (Settings → Networking → Generate Domain)
7. تست: `دامنه/api/health` باید `{"ok":true}` بدهد و خود `دامنه/` باید UI بازی را نشان دهد

### گام ۳ — اتصال به بات (۲ دقیقه)
```
@BotFather → /mybots → بات تو → Bot Settings
→ Menu Button → آدرس Railway را بده
```
بات را باز کن → دکمهٔ منو → 🎮 بازی داخل تلگرام!

## تست بدون سرور
متغیر `VITE_MOCK=true` را در build frontend بگذار → حالت mock: کل UI با دیتای نمایشی کار می‌کند
(بدون این متغیر، frontend به‌طور پیش‌فرض با همان دامنه که رویش سرو می‌شود صحبت می‌کند).
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
