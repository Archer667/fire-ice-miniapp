import os
from dotenv import load_dotenv

load_dotenv()

BOT_TOKEN   = os.getenv("BOT_TOKEN", "")
MONGODB_URI = os.getenv("MONGODB_URI", "mongodb://localhost:27017")
DB_NAME     = os.getenv("DB_NAME", "fire_ice")
ADMIN_IDS   = [int(x) for x in os.getenv("ADMIN_IDS", "").split(",") if x.strip()]
DEV_MODE    = os.getenv("DEV_MODE", "false").lower() == "true"
CORS_ORIGINS = os.getenv("CORS_ORIGINS", "*").split(",")

# ---- ثابت‌های اقتصاد بازی ----
STARTING_RESOURCES = {"gold": 1000, "food": 800, "men": 500, "iron": 100, "stone": 100}
DAILY_PRODUCTION   = {"gold": 200,  "food": 300, "men": 50,  "iron": 40,  "stone": 40}
RESOURCE_CAPS      = {"gold": 2000, "food": 2000, "men": 1000, "iron": 500, "stone": 500}
CAMPAIGN_REVEAL_MINUTES = 15
SEASON_LENGTH_DAYS = 30
