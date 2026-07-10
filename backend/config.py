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

# ---- ثابت‌های اقتصاد بازی ----
STARTING_RESOURCES = {"gold": 1000, "food": 800, "men": 500, "iron": 100, "stone": 100, "wood": 150, "wine": 0}
DAILY_PRODUCTION   = {"gold": 200,  "food": 300, "men": 50,  "iron": 40,  "stone": 40,  "wood": 50,  "wine": 0}
RESOURCE_CAPS      = {"gold": 2000, "food": 2000, "men": 1000, "iron": 500, "stone": 500, "wood": 800, "wine": 300}
CAMPAIGN_REVEAL_MINUTES = 15
SEASON_LENGTH_DAYS = 30

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

# ---- امتیاز ترکیبی ----
SCORE_W_ECONOMY    = 4     # به‌ازای هر سطح ساختمان اقتصادی
SCORE_W_MILITARY   = 5     # به‌ازای هر سطح پادگان/کارگاه تسلیحات
SCORE_W_POPULARITY = 0.4   # به‌ازای هر واحد محبوبیت
SCORE_W_ALLIANCE   = 6     # به‌ازای هر اتحاد فعال
TITLE_SCORE_BONUS  = {"overlord": 50, "warden": 150, "king": 400}

# ---- عناوین پیش‌فرض ----
DEFAULT_TITLE = {"lord": "لرد جوان", "lady": "لیدی جوان"}
