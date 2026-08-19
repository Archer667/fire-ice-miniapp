import random
from datetime import timedelta
from bson import ObjectId
from fastapi import APIRouter, Depends, HTTPException
from pydantic import BaseModel
from auth import get_user, get_admin, get_full_admin
from config import ADMIN_IDS, POPULARITY_START
from db import players, rebellions, rebellion_checks, game_settings, admin_roles
from game import now
from routers.ravens import send_system_message
import telegram_bot

router = APIRouter(prefix="/api/rebellions", tags=["rebellions"])
SETTINGS_ID = "rebellion_settings"
ACTIVE_STATUSES = ["awaiting_roleplay", "roleplay_submitted", "expired"]

DEFAULT_SETTINGS = {
    "enabled": True,
    "safe_popularity": 50,
    "high_risk_popularity": 40,
    "guaranteed_popularity": 30,
    "roleplay_hours": 24,
    "cooldown_hours": 48,
    "base_food_per_100_men": 20,
    "default_ration": "normal",
    "ration_levels": {
        "very_low": {"label": "جیره ناچیز", "multiplier": 0.50, "popularity": -3},
        "low": {"label": "جیره کم", "multiplier": 0.75, "popularity": -1},
        "normal": {"label": "جیره معمولی", "multiplier": 1.00, "popularity": 0},
        "good": {"label": "جیره خوب", "multiplier": 1.25, "popularity": 1},
        "abundant": {"label": "جیره فراوان", "multiplier": 1.50, "popularity": 2},
    },
    "tax_bands": [
        {"max": 5, "popularity": 2}, {"max": 10, "popularity": 1},
        {"max": 15, "popularity": 0}, {"max": 20, "popularity": -1},
        {"max": 100, "popularity": -2},
    ],
    "chance_low_start": 5,
    "chance_low_step": 3,
    "chance_high_start": 40,
    "chance_high_step": 5,
    "starvation_popularity": -3,
    "feast_food_cost": 80,
    "feast_wine_cost": 40,
    "feast_popularity_gain": 8,
    "war_popularity": {
        "attack_win": 3, "defense_win": 5, "attack_loss": -2,
        "defense_loss": -5, "castle_captured": 3, "castle_lost": -5,
    },
}

def _merge_settings(raw: dict | None) -> dict:
    out = {**DEFAULT_SETTINGS}
    raw = raw or {}
    for key, value in raw.items():
        if key in ("ration_levels", "war_popularity"):
            out[key] = {**DEFAULT_SETTINGS[key], **(value or {})}
        else:
            out[key] = value
    return out

async def get_settings() -> dict:
    doc = await game_settings.find_one({"_id": SETTINGS_ID})
    return _merge_settings((doc or {}).get("settings"))

def rebellion_chance(popularity: int, settings: dict) -> int:
    safe = int(settings["safe_popularity"])
    guaranteed = int(settings["guaranteed_popularity"])
    high_risk = int(settings["high_risk_popularity"])
    if popularity >= safe:
        return 0
    if popularity < guaranteed:
        return 100
    if popularity >= high_risk:
        return min(100, int(settings["chance_low_start"]) + (safe - 1 - popularity) * int(settings["chance_low_step"]))
    return min(100, int(settings["chance_high_start"]) + (high_risk - 1 - popularity) * int(settings["chance_high_step"]))

def _tax_delta(rate: int, settings: dict) -> int:
    for band in settings["tax_bands"]:
        if rate <= int(band["max"]):
            return int(band["popularity"])
    return 0

async def _notify_admins(text: str):
    ids = set(ADMIN_IDS)
    async for a in admin_roles.find({}, {"tg_id": 1}):
        ids.add(a["tg_id"])
    for tg_id in ids:
        telegram_bot.push(tg_id, text)

async def _trigger_rebellion(player: dict, popularity: int, chance: int, roll: int, settings: dict):
    if await rebellions.find_one({"tg_id": player["tg_id"], "status": {"$in": ACTIVE_STATUSES}}):
        return None
    cooldown = await rebellions.find_one({
        "tg_id": player["tg_id"], "resolved_at": {"$gt": now() - timedelta(hours=int(settings["cooldown_hours"]))}
    })
    if cooldown:
        return None
    deadline = now() + timedelta(hours=int(settings["roleplay_hours"]))
    doc = {
        "tg_id": player["tg_id"], "player_name": player["name"], "castle": player.get("castle"),
        "popularity": popularity, "chance": chance, "roll": roll,
        "status": "awaiting_roleplay", "roleplay_text": None,
        "created_at": now(), "deadline": deadline, "resolved": False,
    }
    res = await rebellions.insert_one(doc)
    text = (
        f"🔥 شورش در قلمرو تو آغاز شده است. محبوبیت هنگام وقوع {popularity} بود. "
        f"تا {settings['roleplay_hours']} ساعت فرصت داری سناریوی مقابله با شورش را از صفحه قلمرو بفرستی."
    )
    await send_system_message(player["tg_id"], player["name"], text)
    await _notify_admins(
        f"🚨 شورش جدید برای {player['name']} در {player.get('castle') or 'قلعه نامشخص'}\n"
        f"محبوبیت: {popularity} | شانس: {chance}٪ | تاس: {roll}\n"
        f"مهلت رول: {settings['roleplay_hours']} ساعت"
    )
    return str(res.inserted_id)

async def evaluate_player(player: dict, settings: dict, day_key: str):
    claimed = await rebellion_checks.update_one(
        {"tg_id": player["tg_id"], "day": day_key},
        {"$setOnInsert": {"created_at": now()}}, upsert=True,
    )
    if claimed.upserted_id is None:
        return
    ration_key = player.get("food_ration", settings["default_ration"])
    ration = settings["ration_levels"].get(ration_key, settings["ration_levels"]["normal"])
    men = max(0, int(player.get("resources", {}).get("men", 0)))
    base_food = max(1, round(men * float(settings["base_food_per_100_men"]) / 100))
    wanted = max(0, round(base_food * float(ration["multiplier"])))
    available = max(0, int(player.get("resources", {}).get("food", 0)))
    consumed = min(wanted, available)
    ration_delta = int(ration["popularity"])
    if consumed < wanted:
        ration_delta = int(settings["starvation_popularity"])
    tax_delta = _tax_delta(int(player.get("tax_rate", 10)), settings)
    old_popularity = int(player.get("popularity", POPULARITY_START))
    popularity = max(0, min(100, old_popularity + ration_delta + tax_delta))
    await players.update_one({"tg_id": player["tg_id"]}, {
        "$set": {
            "resources.food": available - consumed, "popularity": popularity,
            "rebellion_last_check": day_key,
        },
        "$push": {"popularity_history": {"$each": [{
            "at": now(), "before": old_popularity, "after": popularity,
            "ration": ration_delta, "tax": tax_delta, "food_consumed": consumed,
        }], "$slice": -60}},
    })
    chance = rebellion_chance(popularity, settings)
    roll = random.SystemRandom().randint(1, 100)
    triggered = chance >= roll
    await rebellion_checks.update_one({"tg_id": player["tg_id"], "day": day_key}, {"$set": {
        "popularity": popularity, "chance": chance, "roll": roll, "triggered": triggered,
    }})
    if triggered:
        await _trigger_rebellion(player, popularity, chance, roll, settings)

async def evaluate_rebellions():
    settings = await get_settings()
    if not settings.get("enabled", True):
        return
    current = now()
    day_key = current.strftime("%Y-%m-%d")
    async for r in rebellions.find({"status": {"$in": ["awaiting_roleplay", "roleplay_submitted"]}, "deadline": {"$lte": current}}):
        await rebellions.update_one({"_id": r["_id"]}, {"$set": {"status": "expired"}})
        await _notify_admins(f"⌛ مهلت رول شورش {r['player_name']} در {r.get('castle') or 'قلمرو'} تمام شد.")
    async for player in players.find({"region": {"$ne": None}, "castle": {"$ne": None}}):
        await evaluate_player(player, settings, day_key)

async def admin_user(user: dict = Depends(get_user)):
    return await get_admin(user)

async def full_admin_user(user: dict = Depends(get_user)):
    return await get_full_admin(user)

class RationBody(BaseModel):
    level: str

class RoleplayBody(BaseModel):
    text: str

class SettingsBody(BaseModel):
    settings: dict

class ResolveBody(BaseModel):
    result: str
    popularity_delta: int = 0
    gold_delta: int = 0
    food_delta: int = 0
    men_delta: int = 0
    outcome: str = "resolved"

@router.get("/status")
async def status(user: dict = Depends(get_user)):
    p = await players.find_one({"tg_id": user["id"]})
    if not p:
        raise HTTPException(403, "اول ثبت‌نام کن")
    settings = await get_settings()
    active = await rebellions.find_one({"tg_id": user["id"], "status": {"$in": ACTIVE_STATUSES}}, sort=[("created_at", -1)])
    return {
        "popularity": p.get("popularity", POPULARITY_START),
        "ration": p.get("food_ration", settings["default_ration"]),
        "ration_levels": settings["ration_levels"],
        "chance": rebellion_chance(int(p.get("popularity", POPULARITY_START)), settings),
        "safe_popularity": settings["safe_popularity"],
        "guaranteed_popularity": settings["guaranteed_popularity"],
        "active": None if not active else {
            "id": str(active["_id"]), "status": active["status"], "deadline": active["deadline"].isoformat(),
            "roleplay_text": active.get("roleplay_text"), "result": active.get("result"),
        },
    }

@router.post("/ration")
async def set_ration(body: RationBody, user: dict = Depends(get_user)):
    settings = await get_settings()
    if body.level not in settings["ration_levels"]:
        raise HTTPException(400, "سطح جیره نامعتبر است")
    await players.update_one({"tg_id": user["id"]}, {"$set": {"food_ration": body.level}})
    return {"ok": True, "ration": body.level}

@router.post("/{rebellion_id}/roleplay")
async def submit_roleplay(rebellion_id: str, body: RoleplayBody, user: dict = Depends(get_user)):
    text = body.text.strip()
    if len(text) < 10:
        raise HTTPException(400, "رول خیلی کوتاه است")
    try:
        oid = ObjectId(rebellion_id)
    except Exception:
        raise HTTPException(400, "شناسه شورش نامعتبر است")
    result = await rebellions.update_one(
        {"_id": oid, "tg_id": user["id"], "status": "awaiting_roleplay", "deadline": {"$gt": now()}},
        {"$set": {"roleplay_text": text[:4000], "roleplay_submitted_at": now(), "status": "roleplay_submitted"}},
    )
    if not result.modified_count:
        raise HTTPException(400, "شورش فعال نیست یا مهلت رول گذشته است")
    await _notify_admins("✍️ بازیکن رول مقابله با شورش را فرستاد؛ نتیجه را در پنل ادمین ثبت کنید.")
    return {"ok": True}

@router.get("/admin/settings")
async def admin_settings(user: dict = Depends(full_admin_user)):
    return await get_settings()

@router.post("/admin/settings")
async def update_settings(body: SettingsBody, user: dict = Depends(get_full_admin)):
    merged = _merge_settings(body.settings)
    if not (0 <= int(merged["guaranteed_popularity"]) < int(merged["high_risk_popularity"]) < int(merged["safe_popularity"]) <= 100):
        raise HTTPException(400, "ترتیب حدها باید قطعی < خطر زیاد < امن و بین صفر تا صد باشد")
    if int(merged["roleplay_hours"]) < 1:
        raise HTTPException(400, "مهلت رول باید حداقل یک ساعت باشد")
    await game_settings.update_one({"_id": SETTINGS_ID}, {"$set": {"settings": merged, "updated_at": now()}}, upsert=True)
    return merged

@router.get("/admin/list")
async def admin_list(user: dict = Depends(admin_user)):
    out = []
    async for r in rebellions.find({}).sort("created_at", -1).limit(100):
        out.append({
            "id": str(r["_id"]), "tg_id": r["tg_id"], "player_name": r["player_name"],
            "castle": r.get("castle"), "popularity": r["popularity"], "chance": r["chance"],
            "roll": r["roll"], "status": r["status"], "roleplay_text": r.get("roleplay_text"),
            "deadline": r["deadline"].isoformat(), "result": r.get("result"),
        })
    return out

@router.post("/admin/{rebellion_id}/resolve")
async def resolve(rebellion_id: str, body: ResolveBody, user: dict = Depends(get_admin)):
    try:
        oid = ObjectId(rebellion_id)
    except Exception:
        raise HTTPException(400, "شناسه شورش نامعتبر است")
    r = await rebellions.find_one({"_id": oid})
    if not r or r.get("resolved"):
        raise HTTPException(404, "شورش فعال پیدا نشد")
    p = await players.find_one({"tg_id": r["tg_id"]})
    if not p:
        raise HTTPException(404, "بازیکن پیدا نشد")
    popularity = max(0, min(100, int(p.get("popularity", POPULARITY_START)) + body.popularity_delta))
    resources = p.get("resources", {})
    for key, delta in (("gold", body.gold_delta), ("food", body.food_delta), ("men", body.men_delta)):
        resources[key] = max(0, resources.get(key, 0) + delta)
    result_text = body.result.strip()
    await players.update_one({"tg_id": p["tg_id"]}, {"$set": {"popularity": popularity, "resources": resources}})
    await rebellions.update_one({"_id": oid}, {"$set": {
        "resolved": True, "status": body.outcome, "result": result_text[:4000],
        "resolved_at": now(), "resolved_by": user["id"],
    }})
    await send_system_message(p["tg_id"], p["name"], f"نتیجه شورش: {result_text}")
    return {"ok": True, "popularity": popularity, "resources": resources}
