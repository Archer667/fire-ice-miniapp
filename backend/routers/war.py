from datetime import datetime, timedelta
from bson import ObjectId
from fastapi import APIRouter, Depends, HTTPException
from pydantic import BaseModel
from auth import get_user
from db import players, campaigns, map_castles
from game import now, can_afford, pay, normalize_building_state
from game_data import COMMON_TROOPS, REGIONS, SPECIAL_TROOP_COST, BUILDINGS, unit_requirements
from config import FOOD_COST_REGULAR, FOOD_COST_SPECIAL

router = APIRouter(prefix="/api/war", tags=["war"])

# needs_target=False یعنی مقصد لازم نیست (دفاعی — مقصد داخلی = مبدا)
# port_only=True یعنی مقصد باید یک قلعه/شهر بندری باشد (غارت دریایی)
OP_TYPES = {
    "attack":     {"name": "حملهٔ نظامی",                     "needs_target": True,  "port_only": False},
    "siege":      {"name": "محاصرهٔ قلعه",                     "needs_target": True,  "port_only": False},
    "naval_raid": {"name": "غارت دریایی (برای اهداف بندری)",  "needs_target": True,  "port_only": True},
    "garrison":   {"name": "جای‌گیری",                         "needs_target": True,  "port_only": False},
    "defense":    {"name": "دفاعی",                           "needs_target": False, "port_only": False},
}

class CampaignBody(BaseModel):
    origin_castle: str
    op_type: str
    target_castle: str | None = None
    plan: str = ""
    troops: dict            # {troop_id: count}

async def all_castle_names_and_ports():
    """اسم همهٔ قلعه/شهرهای بازی (استاتیک + آنچه ادمین به نقشه اضافه کرده) و زیرمجموعهٔ بندری‌ها"""
    names, ports = set(), set()
    for r in REGIONS.values():
        names |= set(r["castles"]) | set(r["ports"])
        ports |= set(r["ports"])
    async for m in map_castles.find({}):
        names.add(m["name"])
        if m.get("port"):
            ports.add(m["name"])
    return names, ports

def troop_food_and_gold(region: str, troops: dict, buildings: dict):
    """هزینهٔ طلا (یک‌باره)، نفرات کل، و آذوقهٔ روزانهٔ این ترکیب لشکر را حساب می‌کند.
    برای هر نیروی عمومی، ساخته‌بودن پادگان و کارگاه تسلیحاتش را هم اعتبارسنجی می‌کند."""
    specials = REGIONS[region]["special"]
    gold = men = food = 0
    for tid, n in troops.items():
        if n <= 0:
            continue
        if tid in COMMON_TROOPS:
            req = unit_requirements(tid)
            if req:
                camp_id, armory_id = req
                camp_level = normalize_building_state(buildings.get(camp_id))["level"]
                armory_level = normalize_building_state(buildings.get(armory_id))["level"]
                if camp_level <= 0 or armory_level <= 0:
                    raise HTTPException(
                        400,
                        f"برای گسیل {COMMON_TROOPS[tid]['name']} باید {BUILDINGS[camp_id]['name']} "
                        f"و {BUILDINGS[armory_id]['name']} را ساخته باشی",
                    )
            gold += COMMON_TROOPS[tid]["cost"] * n
            food += FOOD_COST_REGULAR * n
        elif tid in specials:
            gold += SPECIAL_TROOP_COST * n
            food += FOOD_COST_SPECIAL * n
        else:
            raise HTTPException(400, f"نیروی نامعتبر: {tid}")
        men += n
    return gold, men, food

async def stationed_origins(tg_id: int) -> set:
    """قلعه‌هایی که لشکر فعلی این بازیکن با عملیات «جای‌گیری» در آن‌ها مستقر است"""
    origins = set()
    async for c in campaigns.find({"tg_id": tg_id, "active": True, "op_type": "garrison"}):
        origins.add(c["target_castle"])
    return origins

async def apply_campaign_upkeep(tg_id: int, resources: dict) -> dict:
    """تیک تنبل: آذوقهٔ هر لشکرِ فعال را از آخرین بار تا الان، روزانه کم می‌کند"""
    cur = campaigns.find({"tg_id": tg_id, "active": True})
    async for c in cur:
        last = c.get("last_food_tick") or c["created_at"]
        if isinstance(last, str):
            last = datetime.fromisoformat(last)
        days = int((now() - last).total_seconds() // 86400)
        if days <= 0:
            continue
        cost = c["food_per_day"] * days
        resources["food"] = max(0, resources.get("food", 0) - cost)
        await campaigns.update_one({"_id": c["_id"]}, {"$set": {"last_food_tick": last + timedelta(days=days)}})
    return resources

@router.post("/submit")
async def submit(body: CampaignBody, user: dict = Depends(get_user)):
    p = await players.find_one({"tg_id": user["id"]})
    if not p:
        raise HTTPException(403, "اول ثبت‌نام کن")

    op = OP_TYPES.get(body.op_type)
    if not op:
        raise HTTPException(400, "نوع عملیات نامعتبر")

    p["resources"] = await apply_campaign_upkeep(user["id"], p["resources"])

    valid_origins = {p["castle"]} | await stationed_origins(user["id"])
    if body.origin_castle not in valid_origins:
        raise HTTPException(400, "مبدا باید قلعهٔ خودت یا جایی باشد که لشکرت همین الان مستقر است")

    if op["needs_target"]:
        if not body.target_castle:
            raise HTTPException(400, "مقصد را مشخص کن")
        names, ports = await all_castle_names_and_ports()
        if body.target_castle not in names:
            raise HTTPException(400, "این قلعه در بازی شناخته‌شده نیست")
        if op["port_only"] and body.target_castle not in ports:
            raise HTTPException(400, "غارت دریایی فقط علیه اهداف بندری ممکن است")
        target_castle = body.target_castle
        if body.op_type != "garrison" and len(body.plan.strip()) < 50:
            raise HTTPException(400, "سناریو خیلی کوتاه است — نقشه‌ات را شرح بده")
    else:
        target_castle = body.origin_castle

    gold, men, food_per_day = troop_food_and_gold(p["region"], body.troops, p.get("buildings", {}))
    if men <= 0:
        raise HTTPException(400, "هیچ نیرویی گسیل نکرده‌ای")
    if not can_afford(p["resources"], {"gold": gold}):
        raise HTTPException(400, "خزانه کافی نیست")
    if p["resources"].get("men", 0) < men:
        raise HTTPException(400, "نفرات کافی نداری")

    pay(p["resources"], {"gold": gold})
    p["resources"]["men"] = p["resources"].get("men", 0) - men
    await players.update_one({"tg_id": user["id"]}, {"$set": {"resources": p["resources"]}})

    doc = {
        "tg_id": user["id"], "player_name": p["name"],
        "origin_castle": body.origin_castle,
        "op_type": body.op_type, "target_castle": target_castle,
        "plan": body.plan.strip(), "troops": body.troops,
        "gold_cost": gold, "men_committed": men, "food_per_day": food_per_day,
        "status": "pending", "verdict": "", "active": True,
        "created_at": now(), "last_food_tick": now(),
    }
    res = await campaigns.insert_one(doc)
    return {"ok": True, "id": str(res.inserted_id), "gold_cost": gold, "men_committed": men, "food_per_day": food_per_day}

@router.post("/{campaign_id}/cancel")
async def cancel(campaign_id: str, user: dict = Depends(get_user)):
    c = await campaigns.find_one({"_id": ObjectId(campaign_id)})
    if not c or c["tg_id"] != user["id"]:
        raise HTTPException(404, "لشکر پیدا نشد")
    if not c.get("active"):
        raise HTTPException(400, "این لشکر دیگر فعال نیست")
    await campaigns.update_one({"_id": c["_id"]}, {"$set": {"active": False, "status": "cancelled"}})
    await players.update_one({"tg_id": user["id"]}, {"$inc": {"resources.men": c["men_committed"]}})
    return {"ok": True}

@router.get("/mine")
async def mine(user: dict = Depends(get_user)):
    cur = campaigns.find({"tg_id": user["id"]}).sort("created_at", -1).limit(30)
    out = []
    async for c in cur:
        days_active = max(0, int((now() - c["created_at"]).total_seconds() // 86400))
        out.append({
            "id": str(c["_id"]),
            "op_type": c["op_type"], "op_name": OP_TYPES.get(c["op_type"], {}).get("name", c["op_type"]),
            "origin": c["origin_castle"], "target": c["target_castle"],
            "status": c["status"], "verdict": c.get("verdict", ""), "active": c.get("active", False),
            "gold_cost": c["gold_cost"], "men_committed": c["men_committed"],
            "food_per_day": c["food_per_day"], "days_active": days_active,
            "created_at": c["created_at"].isoformat(),
        })
    return out
