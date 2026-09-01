from motor.motor_asyncio import AsyncIOMotorClient
from config import MONGODB_URI, DB_NAME

client = AsyncIOMotorClient(MONGODB_URI)
db = client[DB_NAME]

players    = db.players
campaigns  = db.campaigns
ambushes   = db.ambushes
map_castles = db.map_castles
spy_missions = db.spy_missions
messages   = db.messages
alliances  = db.alliances
hierarchy  = db.hierarchy
polls      = db.polls
admin_roles = db.admin_roles
admin_notifications = db.admin_notifications
caravans   = db.caravans
market_listings = db.market_listings
black_market_listings = db.black_market_listings
player_market_listings = db.player_market_listings
roleplays = db.roleplays
rebellions = db.rebellions
rebellion_checks = db.rebellion_checks
items      = db.items
item_grants = db.item_grants
rumors     = db.rumors
rumor_views = db.rumor_views
game_settings = db.game_settings
tributes   = db.tributes
