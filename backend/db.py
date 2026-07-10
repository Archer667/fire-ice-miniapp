from motor.motor_asyncio import AsyncIOMotorClient
from config import MONGODB_URI, DB_NAME

client = AsyncIOMotorClient(MONGODB_URI)
db = client[DB_NAME]

players    = db.players
scenarios  = db.scenarios
campaigns  = db.campaigns
map_castles = db.map_castles
battle_reports = db.battle_reports
messages   = db.messages
buildings  = db.buildings
alliances  = db.alliances
hierarchy  = db.hierarchy
polls      = db.polls
admin_roles = db.admin_roles
