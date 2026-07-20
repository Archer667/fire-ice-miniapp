from motor.motor_asyncio import AsyncIOMotorClient
from config import MONGODB_URI, DB_NAME

client = AsyncIOMotorClient(MONGODB_URI)
db = client[DB_NAME]

players    = db.players
campaigns  = db.campaigns
map_castles = db.map_castles
battle_reports = db.battle_reports
spy_missions = db.spy_missions
messages   = db.messages
alliances  = db.alliances
hierarchy  = db.hierarchy
polls      = db.polls
admin_roles = db.admin_roles
caravans   = db.caravans
market_listings = db.market_listings
black_market_listings = db.black_market_listings
roleplays = db.roleplays
items      = db.items
item_grants = db.item_grants
rumors     = db.rumors
