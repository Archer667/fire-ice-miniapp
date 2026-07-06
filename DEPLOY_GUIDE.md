# 🚀 راهنمای Deploy و دیدن نتیجه در تلگرام

## گام ۱: تست محلی (۵ دقیقه)
```bash
# نصب Node.js از nodejs.org (نسخه 18+)
cd fire-ice-miniapp
npm install
npm run dev
```
مرورگر: `http://localhost:3000` — بازی را کامل تست کن.
(خارج از تلگرام، حالت mock فعال است و همه‌چیز کار می‌کند)

## گام ۲: آپلود به GitHub (۵ دقیقه)
1. github.com → Sign up → **New Repository** → نام: `fire-ice-miniapp` → Public → Create
2. **Add file → Upload files** → کل پوشه پروژه را بکش و بینداز (به‌جز node_modules!)
3. **Commit changes**

## گام ۳: Deploy روی Vercel (۵ دقیقه)
1. vercel.com → **Sign up with GitHub**
2. **New Project** → ریپوی `fire-ice-miniapp` را Import کن
3. Framework: خودش Vite را تشخیص می‌دهد → **Deploy**
4. بعد ۱-۲ دقیقه آدرس می‌گیری:
   `https://fire-ice-miniapp.vercel.app`

## گام ۴: اتصال به بات تلگرام (۳ دقیقه)
در تلگرام:
```
@BotFather
→ /mybots
→ بات خودت را انتخاب کن
→ Bot Settings
→ Menu Button (یا Configure Mini App)
→ آدرس Vercel را بده:
   https://fire-ice-miniapp.vercel.app
```

## گام ۵: نتیجه! 🎉
1. بات خودت را در تلگرام باز کن
2. دکمه Menu (کنار فیلد تایپ) را بزن
3. **Mini App باز می‌شود — با اسم واقعی تلگرامت!**
   (چون `telegram.js` اسمت را از SDK می‌خواند)

## ⚠️ نکته‌ها
- هر بار کد را در GitHub آپدیت کنی، Vercel خودکار دوباره build می‌کند
- توکن بات هرگز در این پروژه نیست — Frontend به توکن نیاز ندارد ✅
- برای چت واقعی بین بازیکنان، فاز Backend لازم است (فاز ۳)
