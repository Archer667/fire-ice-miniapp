import os
from dotenv import load_dotenv

load_dotenv()

BOT_TOKEN   = os.getenv("BOT_TOKEN", "")
MONGODB_URI = os.getenv("MONGODB_URI", "mongodb://localhost:27017")
DB_NAME     = os.getenv("DB_NAME", "fire_ice")
ADMIN_IDS   = [int(x) for x in os.getenv("ADMIN_IDS", "").split(",") if x.strip()]
DEV_MODE    = os.getenv("DEV_MODE", "false").lower() == "true"
CORS_ORIGINS = os.getenv("CORS_ORIGINS", "*").split(",")
# Vercel روی هر دیپلوی/پریویو یک URL تصادفی می‌سازد — این regex اجازه می‌دهد
# همهٔ پریویوهای یک پروژه بدون ویرایش دستی CORS_ORIGINS با هر پوش قبول شوند
CORS_ORIGIN_REGEX = os.getenv("CORS_ORIGIN_REGEX", "") or None

# ---- بات تلگرام: دستور /start ----
# MINI_APP_URL = آدرس Vercel فرانت‌اند — همان دکمه‌ای که با /start زیر پیام خوش‌آمد می‌آید
# PUBLIC_BASE_URL = آدرس عمومی همین بک‌اند — برای ثبت webhook پیش تلگرام لازم است
# هر دو خالی باشند یعنی /start غیرفعال می‌ماند (مثلاً موقع تست لوکال)
MINI_APP_URL     = os.getenv("MINI_APP_URL", "")
PUBLIC_BASE_URL  = os.getenv("PUBLIC_BASE_URL", "").rstrip("/")
TELEGRAM_WEBHOOK_PATH = "/api/telegram/webhook"

# ---- ثابت‌های اقتصاد بازی ----
# wine=30 عمدی است: DAILY_PRODUCTION.wine=0 (بدون می‌کده صفر تولید می‌شود) و هر سه نوع
# پیمان دیپلماتیک هزینهٔ شراب دارند (حداقل «پیمان تجاری»=۳۰) — با شراب شروع صفر، بازیکن
# تازه‌کار تا ساختن و بالغ‌شدن می‌کده اصلاً نمی‌توانست پیمانی (و در نتیجه کاروانی) ببندد
# weapon_* یک استوک آغازین کوچک دارند تا بازیکن تازه‌کار قبل از ساختن کارگاه تسلیحات هم
# بتواند اولین لشکرش را بفرستد؛ بعد از آن فقط از تولید روزانهٔ کارگاه تسلیحات پر می‌شود
STARTING_RESOURCES = {
    "gold": 1000, "food": 800, "men": 500, "iron": 100, "stone": 100, "wood": 150, "wine": 30,
    "weapon_sword": 20, "weapon_spear": 20, "weapon_archer": 20, "weapon_lcav": 20, "weapon_hcav": 20,
}
DAILY_PRODUCTION   = {"gold": 200,  "food": 300, "men": 50,  "iron": 40,  "stone": 40,  "wood": 50,  "wine": 0}
RESOURCE_CAPS      = {
    "gold": 2000, "food": 2000, "men": 1000, "iron": 500, "stone": 500, "wood": 800, "wine": 300,
    "weapon_sword": 300, "weapon_spear": 300, "weapon_archer": 300, "weapon_lcav": 200, "weapon_hcav": 200,
}
CAMPAIGN_REVEAL_MINUTES = 30
SEASON_LENGTH_DAYS = 30

# ---- آذوقهٔ روزانهٔ لشکر — به‌ازای هر سرباز، تا وقتی لشکر فعال است ----
FOOD_COST_REGULAR = 1   # سرباز عادی، غله در روز
FOOD_COST_SPECIAL = 2   # نیروی ویژهٔ اقلیمی، غله در روز

# ---- فرستندهٔ سیستمی پیام‌ها — روایت‌های جنگ که ادمین برای بازیکنان می‌فرستد ----
SYSTEM_SENDER_ID = 0
SYSTEM_SENDER_NAME = "شورای جنگ"

# ---- جاسوسی — عملیات ویژه: بازیکن سناریو می‌نویسد، ادمین امتیازش می‌دهد و همان
# امتیاز (۰ تا ۱۰۰) مستقیماً شانس موفقیت است؛ بی‌آبرویی هنگام دستگیری ----
SPY_GOLD_COST = 1000
SPY_MEN_COST = 5   # «جاسوس» از جمعیت کم می‌شود؛ اگر موفق باشد برمی‌گردد، اگر دستگیر شود نه

# ---- مالیات و محبوبیت ----
TAX_RATE_DEFAULT = 10     # درصد، در ابتدای بازی
TAX_RATE_BASE_MAX = 20    # سقف مالیات بدون احتساب بونوس محبوبیت
POPULARITY_START = 50
POPULARITY_MAX = 100

def max_tax_rate(popularity: int) -> int:
    """محبوبیت بالاتر یعنی نارضایتی کمتر → سقف مالیات هم بالاتر می‌رود"""
    return max(0, TAX_RATE_BASE_MAX + (popularity - POPULARITY_START) // 5)

def tax_yield_multiplier(popularity: int) -> float:
    """بازدهی مالیات به نسبت جمعیت — با محبوبیت بیشتر می‌شود"""
    return 0.5 + popularity / (2 * POPULARITY_MAX)

# ---- جشن (ضیافت) ----
FEAST_COST = {"wine": 40, "food": 80}
FEAST_POPULARITY_GAIN = 8
FEAST_COOLDOWN_HOURS = 24

# پیمان خصوصی (توی تب عمومیِ «اتحادها» نشان داده نمی‌شود) دو برابر شرابِ معمولی هزینه دارد
PRIVATE_ALLIANCE_MULTIPLIER = 2

# ---- شایعات — کارزار عمومی علیه یک بازیکن؛ همه می‌بینند، محبوبیت هدف کم می‌شود ----
RUMOR_GOLD_COST = 100
RUMOR_POPULARITY_DAMAGE = 3
RUMOR_COOLDOWN_HOURS = 6   # یک نفر نمی‌تواند علیه همان هدف زودتر از این دوباره شایعه بسازد

# ---- امتیاز ترکیبی ----
SCORE_W_ECONOMY    = 4     # به‌ازای هر سطح ساختمان اقتصادی
SCORE_W_MILITARY   = 5     # به‌ازای هر سطح پادگان/کارگاه تسلیحات
SCORE_W_POPULARITY = 0.4   # به‌ازای هر واحد محبوبیت
SCORE_W_ALLIANCE   = 6     # به‌ازای هر اتحاد فعال
TITLE_SCORE_BONUS  = {"overlord": 50, "warden": 150, "king": 400}

# ---- عناوین پیش‌فرض ----
DEFAULT_TITLE = {"lord": "لرد جوان", "lady": "لیدی جوان"}

# ---- جایزهٔ ورود روزانه — چرخهٔ ۷ روزه با منحنی افزایشی، روز ۷ به‌مراتب باارزش‌تر از
# مجموع روزهای ۱ تا ۶ — بعد از روز ۷ دوباره از روز ۱ شروع می‌شود اما شمارش استریک ادامه دارد.
# اگر یک روز رد شود (نه دیروز نه امروز کلیم شده)، استریک از روز ۱ ریست می‌شود.
DAILY_REWARDS = [
    {"gold": 50},
    {"gold": 80,  "food": 40},
    {"gold": 120, "food": 60},
    {"gold": 180, "wood": 40, "stone": 40},
    {"gold": 260, "iron": 40, "men": 20},
    {"gold": 350, "wine": 10, "men": 30},
    {"gold": 600, "men": 80,  "wine": 20, "food": 200},
]
