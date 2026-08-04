# راهنمای دیپلوی — انتقال «نغمهٔ آتش و یخ» به هاست/VPS

این راهنما برای کسی نوشته شده که می‌خواد بازی رو از حالت توسعه (روی لپ‌تاپ) به یک آدرس واقعی
و قابل‌دسترس برای بازیکن‌ها ببره — چه با سرویس‌های رایگان و آماده (مسیر A)، چه با یک VPS
اختصاصی (مسیر B، داخلی یا خارجی). لازم نیست هر دو رو بخونی — فقط مسیری که انتخاب کردی رو دنبال کن.

## ۰. اول بفهمیم چی داریم دیپلوی می‌کنیم

سه تکه‌ی جدا از هم:

| تکه | چیه | نیاز داره به |
|---|---|---|
| **Backend** | `backend/` — یک اپ FastAPI (پایتون) که کل منطق بازی و API رو می‌ده | پایتون ۳.۱۱+، دسترسی به یک MongoDB |
| **Frontend** | `frontend/` — یک اپ React که با Vite ساخته می‌شه به چندتا فایل استاتیک (HTML/JS/CSS) | فقط برای *ساختن* نیاز به Node داره؛ بعد از build، فقط چندتا فایل ساده‌ست که هر وب‌سروری می‌تونه سرو کنه |
| **MongoDB** | دیتابیس بازی — همه‌چیز (بازیکن‌ها، قلعه‌ها، لشکرکشی‌ها...) اینجاست | یا یک سرویس ابری (MongoDB Atlas، رایگان تا حد مشخصی) یا نصب خودت روی VPS |

بک‌اند و فرانت‌اند لازم نیست روی یک سرور باشن — می‌تونن جدا از هم هاست بشن (مثل مسیر A) یا
هردو روی یک VPS (مسیر B). فرانت‌اند هیچ‌وقت مستقیم با MongoDB حرف نمی‌زنه؛ همیشه از طریق API
بک‌اند.

**نکته دربارهٔ VPS داخلی در مقابل خارجی:** بک‌اند باید بتونه به `api.telegram.org` وصل بشه
(هم برای فرستادن پیام، هم برای ثبت webhook دستور `/start`). اگه VPS داخل ایرانه و به تلگرام
دسترسی مستقیم نداره، یا باید از یک VPS خارجی استفاده کنی، یا یک پراکسی/HTTP proxy معتبر برای
درخواست‌های خروجی بک‌اند تنظیم کنی. این تنها تفاوت فنیِ واقعیِ داخلی/خارجی برای این پروژه‌ست.

---

## مسیر A — سریع‌ترین راه (Render + Vercel + MongoDB Atlas، رایگان)

این مسیر برای شروع سریع و تست با بازیکن‌های واقعی خوبه. نیازی به مدیریت سرور نداری.

### گام ۱ — MongoDB Atlas (دیتابیس، ۵ دقیقه)
۱. برو mongodb.com/cloud/atlas → ثبت‌نام → Create Cluster (پلن رایگان M0)
۲. Database Access → یک یوزر/پسورد دیتابیس بساز (این جدا از اکانت Atlas خودته)
۳. Network Access → Add IP Address → `0.0.0.0/0` (اجازه به همه — چون Render/VPS آی‌پی ثابت رایگان نداره)
۴. Connect → Drivers → رشتهٔ اتصال (Connection String) رو کپی کن؛ شکلش این‌جوریه:
   `mongodb+srv://user:pass@cluster0.xxxxx.mongodb.net/`

### گام ۲ — Backend روی Render (رایگان)
۱. کل ریپو رو به GitHub پوش کن (یا از قبل هست)
۲. render.com → New → Web Service → ریپوی گیت‌هاب رو وصل کن
۳. تنظیمات:
   - **Root Directory:** `backend`
   - **Build Command:** `pip install -r requirements.txt`
   - **Start Command:** `uvicorn main:app --host 0.0.0.0 --port $PORT`
   - (فایل `backend/render.yaml` همین تنظیمات رو از قبل داره — Render می‌تونه خودش تشخیص بده)
۴. Environment Variables (بخش Environment):
   ```
   BOT_TOKEN=توکن از BotFather
   MONGODB_URI=رشتهٔ اتصال گام ۱
   ADMIN_IDS=آیدی عددی تلگرام خودت (با کاما جدا کن اگه چندتا ادمین کامل داری)
   OWNER_ID=آیدی عددی تلگرام خودت (صاحب بازی — برای کارهای خطرناک مثل ریست کامل)
   CORS_ORIGINS=https://آدرس-frontend-تو.vercel.app
   ```
   `PUBLIC_BASE_URL` و `MINI_APP_URL` رو فعلاً خالی بذار — بعد از گام ۳ برمی‌گردیم اینجا.
۵. Deploy بزن → یک آدرس می‌گیری شبیه `https://fire-ice-api.onrender.com`
۶. تست کن: `https://آدرس-بکندت/api/health` باید `{"ok":true}` برگردونه

### گام ۳ — Frontend روی Vercel (رایگان)
۱. vercel.com → New Project → همون ریپو
۲. **Root Directory: `frontend`**
۳. Environment Variables:
   ```
   VITE_API_URL=https://fire-ice-api.onrender.com   ← آدرس بک‌اند از گام ۲
   ```
   (اگه این خالی بمونه، فرانت‌اند میره تو حالت mock و به بک‌اند وصل نمی‌شه)
۴. Deploy → آدرس می‌گیری شبیه `https://fire-ice.vercel.app`

### گام ۴ — وصل‌کردنِ بات تلگرام
برو BotFather → `/mybots` → بات‌ت → **Bot Settings → Menu Button** → آدرس Vercel (گام ۳) رو بده.
همین کافیه که دکمهٔ منوی بات بازی رو باز کنه — بدون نیاز به کد اضافه.

اگه می‌خوای دستور `/start` هم خودکار دکمهٔ «ورود به بازی» بفرسته (اختیاری):
۱. برگرد به Environment Variables بک‌اند روی Render و این دوتا رو اضافه کن:
   ```
   PUBLIC_BASE_URL=https://fire-ice-api.onrender.com   ← آدرس بک‌اند (گام ۲)
   MINI_APP_URL=https://fire-ice.vercel.app             ← آدرس فرانت‌اند (گام ۳)
   ```
۲. Render رو Manual Deploy کن — بک‌اند موقع بالا اومدن خودش webhook رو پیش تلگرام ثبت می‌کنه،
   نیازی به دستور دستی نیست.

### محدودیت‌های پلن رایگان که باید بدونی
- Render رایگان بعد از چند دقیقه بی‌فعالیتی می‌خوابه و درخواست اول بعدش ۳۰-۵۰ ثانیه طول می‌کشه
  (کاربر اول صبح یا بعد وقفه، صفحه‌ی سفید/لودینگ طولانی می‌بینه). برای رفع این، یا پلن پولی
  Render بگیر، یا یک cron ساده هر ۱۰ دقیقه به `/api/health` پینگ بزنه که نخوابه.
- MongoDB Atlas M0 محدودیت فضا و throughput داره — برای یک بازی با چند ده بازیکن کافیه.

### آپدیت بعد از تغییر کد
فقط `git push` کن — هم Render و هم Vercel با هر پوش به شاخهٔ متصل‌شده، خودکار دوباره دیپلوی می‌کنن.

---

## مسیر B — VPS اختصاصی (خودت همه‌چیز رو مدیریت می‌کنی)

مناسب وقتی: می‌خوای هزینه/کنترل بهتری داشته باشی، یا پلن رایگان کافی نیست، یا می‌خوای همه‌چیز
(بک‌اند + فرانت‌اند + دیتابیس) روی یک سرور باشه.

### پیش‌نیاز
- یک VPS با Ubuntu 22.04 (یا جدیدتر)، حداقل ۱ vCPU / ۱ گیگ RAM (برای شروع کافیه)
- یک دامنه (اختیاری ولی توصیه‌شده — برای SSL و آدرس تمیز؛ می‌شه بدون دامنه هم با IP کار کرد ولی
  Telegram Mini App به HTTPS معتبر نیاز داره، پس یا دامنه بگیر یا از Cloudflare Tunnel/مشابه استفاده کن)
- دسترسی SSH root یا sudo

### گام ۱ — بسته‌های پایه
```bash
sudo apt update && sudo apt upgrade -y
sudo apt install -y python3.11 python3.11-venv python3-pip nginx git curl ufw
curl -fsSL https://deb.nodesource.com/setup_20.x | sudo -E bash -
sudo apt install -y nodejs
```

### گام ۲ — MongoDB
دو گزینه:
- **ساده‌تر:** از MongoDB Atlas استفاده کن (مثل مسیر A، گام ۱) — نیازی به نصب چیزی روی VPS نیست،
  فقط رشتهٔ اتصالش رو تو `.env` می‌ذاری. برای اکثر پروژه‌ها همین کافی و ساده‌تره.
- **نصب محلی روی همون VPS** (اگه می‌خوای همه‌چیز خودت‌مختار باشه):
  ```bash
  curl -fsSL https://pgp.mongodb.com/server-7.0.asc | sudo gpg -o /usr/share/keyrings/mongodb-server-7.0.gpg --dearmor
  echo "deb [signed-by=/usr/share/keyrings/mongodb-server-7.0.gpg] https://repo.mongodb.org/apt/ubuntu jammy/mongodb-org/7.0 multiverse" | sudo tee /etc/apt/sources.list.d/mongodb-org-7.0.list
  sudo apt update && sudo apt install -y mongodb-org
  sudo systemctl enable --now mongod
  ```
  در این حالت `MONGODB_URI=mongodb://localhost:27017` (پیش‌فرضِ خودِ پروژه هم همینه) و
  دیگه لازم نیست نگران Network Access باشی چون از بیرون قابل‌دسترس نیست — ولی خودت مسئول
  بکاپ‌گیری‌شی (پایین توضیح دادم).

### گام ۳ — کد رو بیار روی سرور
```bash
cd /opt
sudo git clone <آدرس ریپوی گیت‌هاب> fire-ice
sudo chown -R $USER:$USER fire-ice
cd fire-ice
```

### گام ۴ — Backend
```bash
cd /opt/fire-ice/backend
python3.11 -m venv venv
source venv/bin/activate
pip install -r requirements.txt
```
یک فایل `.env` بساز (کنار `main.py`):
```bash
cat > .env << 'EOF'
BOT_TOKEN=توکن_از_BotFather
MONGODB_URI=mongodb://localhost:27017     # یا رشتهٔ Atlas
DB_NAME=fire_ice
ADMIN_IDS=آیدی_عددی_تلگرام_تو
OWNER_ID=آیدی_عددی_تلگرام_تو
CORS_ORIGINS=https://دامنه‌ی-فرانت‌اند-تو.com
PUBLIC_BASE_URL=https://api.دامنه‌ی-تو.com
MINI_APP_URL=https://دامنه‌ی-فرانت‌اند-تو.com
EOF
```
تست دستی (باید بدون خطا بالا بیاد، Ctrl+C بزن بعدش):
```bash
uvicorn main:app --host 127.0.0.1 --port 8000
```

**سرویسِ دائمی با systemd** (تا با ری‌استارتِ سرور یا کرش، خودکار بالا بیاد):
```bash
sudo tee /etc/systemd/system/fire-ice-api.service << 'EOF'
[Unit]
Description=Fire & Ice API
After=network.target mongod.service

[Service]
User=root
WorkingDirectory=/opt/fire-ice/backend
Environment=PATH=/opt/fire-ice/backend/venv/bin
ExecStart=/opt/fire-ice/backend/venv/bin/uvicorn main:app --host 127.0.0.1 --port 8000 --workers 2
Restart=always
RestartSec=3

[Install]
WantedBy=multi-user.target
EOF

sudo systemctl daemon-reload
sudo systemctl enable --now fire-ice-api
sudo systemctl status fire-ice-api   # باید active (running) باشه
```
(بک‌اند اینجا فقط روی `127.0.0.1:8000` گوش می‌ده — به بیرون از طریق nginx در گام ۶ می‌رسه، نه مستقیم)

### گام ۵ — Frontend
```bash
cd /opt/fire-ice/frontend
npm install
echo "VITE_API_URL=https://api.دامنه‌ی-تو.com" > .env.production
npm run build
```
خروجی تو `frontend/dist/` می‌شینه — چندتا فایل استاتیک ساده. اینو nginx سرو می‌کنه، فرآیند
جدایی نمی‌خواد.

### گام ۶ — Nginx (reverse proxy برای API + سرو فرانت‌اند)
```bash
sudo tee /etc/nginx/sites-available/fire-ice << 'EOF'
# --- فرانت‌اند: دامنه‌ی اصلی ---
server {
    listen 80;
    server_name دامنه‌ی-فرانت‌اند-تو.com;
    root /opt/fire-ice/frontend/dist;
    index index.html;
    location / {
        try_files $uri $uri/ /index.html;   # SPA — همه‌چیز باید بره index.html
    }
}

# --- بک‌اند: زیردامنه‌ی جدا (api.) ---
server {
    listen 80;
    server_name api.دامنه‌ی-تو.com;
    location / {
        proxy_pass http://127.0.0.1:8000;
        proxy_set_header Host $host;
        proxy_set_header X-Real-IP $remote_addr;
        proxy_set_header X-Forwarded-For $proxy_add_x_forwarded_for;
        proxy_set_header X-Forwarded-Proto $scheme;
    }
}
EOF

sudo ln -s /etc/nginx/sites-available/fire-ice /etc/nginx/sites-enabled/
sudo nginx -t   # چک کن سینتکس درسته
sudo systemctl reload nginx
```

### گام ۷ — SSL رایگان با Let's Encrypt
Telegram Mini App **حتماً** به HTTPS معتبر نیاز داره (نه self-signed). قبل از این گام مطمئن شو
هر دو دامنه (اصلی و `api.`) تو DNS به IP همین VPS اشاره می‌کنن.
```bash
sudo apt install -y certbot python3-certbot-nginx
sudo certbot --nginx -d دامنه‌ی-فرانت‌اند-تو.com -d api.دامنه‌ی-تو.com
```
Certbot خودش nginx config رو برای HTTPS آپدیت می‌کنه و تمدید خودکار هم تنظیم می‌کنه.

### گام ۸ — فایروال
```bash
sudo ufw allow OpenSSH
sudo ufw allow 'Nginx Full'
sudo ufw enable
```

### گام ۹ — تست و وصل‌کردن بات
- `https://api.دامنه‌ی-تو.com/api/health` باید `{"ok":true}` بده
- BotFather → `/mybots` → بات‌ت → Bot Settings → Menu Button → آدرس فرانت‌اند رو بده
- چون `PUBLIC_BASE_URL`/`MINI_APP_URL` تو `.env` گام ۴ ست شده بودن، بک‌اند موقع بالا اومدن
  خودش webhook دستور `/start` رو هم ثبت کرده — نیازی به کار اضافه نیست

### آپدیت بعد از تغییر کد (مسیر B)
```bash
cd /opt/fire-ice
git pull

# بک‌اند تغییر کرده؟
cd backend && source venv/bin/activate && pip install -r requirements.txt
sudo systemctl restart fire-ice-api

# فرانت‌اند تغییر کرده؟
cd ../frontend && npm install && npm run build
# نیازی به ری‌استارت nginx نیست، فایل‌های استاتیک فوراً جایگزین می‌شن
```

---

## متغیرهای محیطی — مرجع کامل

همه از `backend/config.py` خونده می‌شن (فایل `.env` کنار `main.py`، یا Environment Variables تو Render):

| متغیر | اجباری؟ | توضیح |
|---|---|---|
| `BOT_TOKEN` | بله | از BotFather، برای فرستادن پیام و ثبت webhook |
| `MONGODB_URI` | بله (پیش‌فرض `mongodb://localhost:27017`) | رشتهٔ اتصال Mongo |
| `DB_NAME` | خیر (پیش‌فرض `fire_ice`) | اسم دیتابیس داخل Mongo |
| `ADMIN_IDS` | بله برای مدیریت بازی | آیدی عددی تلگرام ادمین‌های کامل، با کاما جدا (مثلاً `123,456`) |
| `OWNER_ID` | توصیه‌شده | آیدی عددی صاحب بازی — سخت‌گیرتر از ادمین کامل (مثلاً ریست کل بازی)؛ اگه ندی، اولین `ADMIN_IDS` می‌شه |
| `DEV_MODE` | خیر (پیش‌فرض `false`) | `true` فقط برای تست لوکال — هدر `X-Dev-User: id:name` جای احراز هویت واقعی تلگرام می‌شینه؛ **هرگز روی سرور واقعی `true` نذار** |
| `CORS_ORIGINS` | بله | آدرس(های) فرانت‌اند، با کاما جدا؛ `*` یعنی همه (فقط برای تست) |
| `CORS_ORIGIN_REGEX` | خیر | برای قبول‌کردن پریویوهای Vercel که هر بار آدرس تصادفی می‌سازن |
| `PUBLIC_BASE_URL` | خیر (برای `/start` خودکار لازمه) | آدرس عمومی خودِ بک‌اند |
| `MINI_APP_URL` | خیر (برای `/start` خودکار لازمه) | آدرس فرانت‌اند |
| `VITE_API_URL` (فرانت‌اند) | خیر | خالی = حالت mock بدون بک‌اند؛ ست‌شده = وصل به بک‌اند واقعی |

---

## بکاپ‌گیری از دیتابیس

اگه از Atlas استفاده می‌کنی، خودش بکاپ خودکار داره (بسته به پلن). اگه Mongo رو خودت رو VPS
نصب کردی:
```bash
# بکاپ
mongodump --uri="mongodb://localhost:27017/fire_ice" --out=/opt/backups/$(date +%F)

# بازگردانی
mongorestore --uri="mongodb://localhost:27017/fire_ice" /opt/backups/2026-08-04/fire_ice
```
یک کرون‌جاب روزانه برای `mongodump` بذار (`crontab -e`) تا خودکار بکاپ بگیره.

---

## عیب‌یابی رایج

- **صفحهٔ سفید تو تلگرام / «Failed to fetch»:** اول `VITE_API_URL` فرانت‌اند رو چک کن، بعد
  `CORS_ORIGINS` بک‌اند — باید دقیقاً آدرس فرانت‌اند رو شامل بشه (با `https://` و بدون `/` آخر).
- **`/api/health` جواب نمی‌ده:** سرویس بک‌اند بالا نیست — `sudo systemctl status fire-ice-api`
  و `sudo journalctl -u fire-ice-api -n 50` رو چک کن.
- **بات به `/start` جواب نمی‌ده:** `PUBLIC_BASE_URL`/`MINI_APP_URL` ست نشدن یا بعد از ست‌کردن
  سرویس ری‌استارت نشده — این دو فقط موقع *بالا اومدنِ* بک‌اند webhook رو ثبت می‌کنن.
- **Mini App باز نمی‌شه یا خطای HTTPS می‌ده:** گواهی SSL معتبر نداری یا expire شده — تلگرام
  self-signed یا http ساده رو قبول نمی‌کنه.
- **کار نکردن از داخل ایران:** اگه VPS یا بک‌اند دسترسی مستقیم به `api.telegram.org` نداره،
  پیام‌ها و webhook کار نمی‌کنن — نیاز به VPS خارجی یا پراکسی داری (بالای همین فایل توضیح داده شد).
