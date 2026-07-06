# 🔥❄️ نغمه آتش و یخ — Telegram Mini App

بازی استراتژی سیاسی-نظامی در جهان Game of Thrones، ساخته‌شده به‌عنوان Mini App تلگرام.

## 🛠️ Stack
- **React 18 + Vite** — سریع، مدرن
- **CSS خالص** — همان طراحی Glassmorphism تأییدشده (بدون Tailwind = بدون پیچیدگی اضافه)
- **Telegram Web App SDK** — از CDN رسمی تلگرام (بدون نصب پکیج)
- **لایه API جدا** (`src/api.js`) — الان mock است، بعداً فقط همین یک فایل به Backend وصل می‌شود

## 📁 ساختار
```
src/
├── main.jsx          نقطه شروع
├── App.jsx           روتینگ صفحات + Nav
├── store.jsx         State مرکزی بازی (طلا، منابع، بازیکن، toast)
├── telegram.js       اتصال به تلگرام (نام کاربر، haptic، تمام‌صفحه)
├── api.js            لایه دیتا (mock → بعداً FastAPI)
├── index.css         طراحی کامل
├── components/       NavBar, Toast, ResourceRow
└── pages/            Onboarding, Dashboard, War, Leaderboard, Chat
```

## 🚀 اجرای محلی
```bash
npm install
npm run dev
# باز کن: http://localhost:3000
```

## ✨ چرا React اینجا می‌درخشد؟
در صفحه‌ی «لشکرکشی» فرمان بفرست — طلا خرج می‌شود.
برگرد به «قلمرو» — نوار طلا **خودش** کم شده. بدون حتی یک خط کد دستی DOM.
این همان چیزی است که با HTML خالص کابوس بود.

## 📱 اتصال به تلگرام
راهنمای کامل در `DEPLOY_GUIDE.md`
