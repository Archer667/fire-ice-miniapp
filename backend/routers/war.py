from datetime import datetime, timedelta
from bson import ObjectId
from fastapi import APIRouter, Depends, HTTPException
from pydantic import BaseModel
from auth import get_user
from db import players, campaigns, map_castles, roleplays
from game import now, can_afford, pay, normalize_building_state
from game_data import COMMON_TROOPS, REGIONS, SPECIAL_TROOP_COST, BUILDINGS, unit_requirements, campaign_power, travel_minutes
from config import FOOD_COST_REGULAR, FOOD_COST_SPECIAL
from routers.ravens import send_system_message

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

# نبردهای واقعی (نه جای‌گیری/دفاعی) — بعد از رسیدن، آمار دو طرف رد و بدل می‌شود و
# هر دو طرف تا ROLEPLAY_WINDOW_HOURS بعد فرصت دارند سناریوی جنگ را از صفحهٔ رول‌ها بفرستند
ATTACK_OP_TYPES = {"attack", "siege", "naval_raid"}
DEFENSE_OP_TYPES = {"defense", "garrison"}
ROLEPLAY_WINDOW_HOURS = 6

# ۲۴ ساعت بعد از رسیدن، گزارش لشکرکشی از تب گزارش‌های بازیکن پاک می‌شود
REPORT_VISIBLE_HOURS = 24

def _building_levels(player: dict) -> dict:
    return {bid: normalize_building_state(raw)["level"] for bid, raw in player.get("buildings", {}).items()}

class CampaignBody(BaseModel):
    origin_castle: str
    op_type: str
    target_castle: str | None = None
    name: str = ""
    troops: dict            # {troop_id: count}

async def all_castle_names_and_ports():
    """اسم همهٔ قلعه/شهرهای بازی (استاتیک + آنچه ادمین به نقشه اضافه کرده) و زیرمجموعهٔ بندری‌ها"""
    names, ports = set(), set()
    for r in REGIONS.values():
        names |= set(r["castles"]) | set(r["ports"])
        ports |= set(r["ports"])
    async for m in map_castles.find({}):
        names.add(m["name"])
        if m.get("kind", "port" if m.get("port") else "castle") == "port":
            ports.add(m["name"])
    return names, ports

async def resolve_region(name: str) -> str | None:
    """اقلیمی که یک قلعه/شهر در آن قرار دارد — چه از دیتای ثابت، چه آنچه ادمین اضافه کرده"""
    for rid, r in REGIONS.items():
        if name in r["castles"] or name in r["ports"]:
            return rid
    doc = await map_castles.find_one({"name": name})
    return doc["region"] if doc else None

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
    else:
        target_castle = body.origin_castle

    gold, men, food_per_day = troop_food_and_gold(p["region"], body.troops, p.get("buildings", {}))
    if men <= 0:
        raise HTTPException(400, "هیچ نیرویی گسیل نکرده‌ای")
    if not can_afford(p["resources"], {"gold": gold}):
        raise HTTPException(400, "خزانه کافی نیست")
    if p["resources"].get("men", 0) < men:
        raise HTTPException(400, "نفرات کافی نداری")

    same_castle = target_castle == body.origin_castle
    origin_region = await resolve_region(body.origin_castle) or p["region"]
    target_region = (await resolve_region(target_castle) or origin_region) if not same_castle else origin_region
    travel = travel_minutes(same_castle, origin_region, target_region)
    arrival_at = now() + timedelta(minutes=travel)
    power = campaign_power(body.troops, _building_levels(p))

    pay(p["resources"], {"gold": gold})
    p["resources"]["men"] = p["resources"].get("men", 0) - men
    await players.update_one({"tg_id": user["id"]}, {"$set": {"resources": p["resources"]}})

    doc = {
        "tg_id": user["id"], "player_name": p["name"],
        "origin_castle": body.origin_castle,
        "op_type": body.op_type, "target_castle": target_castle,
        "name": body.name.strip()[:60] or op["name"], "troops": body.troops, "power": power,
        "gold_cost": gold, "men_committed": men, "food_per_day": food_per_day,
        "travel_minutes": travel, "arrival_at": arrival_at,
        "active": True, "arrival_notified": False,
        "created_at": now(), "last_food_tick": now(),
    }
    res = await campaigns.insert_one(doc)
    return {
        "ok": True, "id": str(res.inserted_id), "gold_cost": gold, "men_committed": men, "power": power,
        "food_per_day": food_per_day, "travel_minutes": travel, "arrival_at": arrival_at.isoformat(),
    }

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
    """گزارش لشکرکشی‌های خودم — لشکری که بیش از REPORT_VISIBLE_HOURS ساعت پیش رسیده
    دیگر توی این لیست نمی‌آید (پاک‌سازی خودکار تب گزارش‌ها)"""
    cur = campaigns.find({"tg_id": user["id"]}).sort("created_at", -1).limit(50)
    out = []
    async for c in cur:
        arrival_at = c.get("arrival_at")
        arrived = (now() >= arrival_at) if arrival_at else True
        if arrived and arrival_at and now() - arrival_at > timedelta(hours=REPORT_VISIBLE_HOURS):
            continue
        days_active = max(0, int((now() - c["created_at"]).total_seconds() // 86400))
        out.append({
            "id": str(c["_id"]),
            "op_type": c["op_type"], "op_name": OP_TYPES.get(c["op_type"], {}).get("name", c["op_type"]),
            "name": c.get("name") or OP_TYPES.get(c["op_type"], {}).get("name", c["op_type"]),
            "origin": c["origin_castle"], "target": c["target_castle"],
            "active": c.get("active", False), "power": c.get("power", 0),
            "gold_cost": c["gold_cost"], "men_committed": c["men_committed"],
            "food_per_day": c["food_per_day"], "days_active": days_active,
            "travel_minutes": c.get("travel_minutes", 0),
            "arrived": arrived,
            "created_at": c["created_at"].isoformat(),
            "arrival_at": arrival_at.isoformat() if arrival_at else None,
        })
    if len(out) > 30:
        out = out[:30]
    return out

def troops_summary(troops: dict) -> str:
    parts = [f"{COMMON_TROOPS.get(tid, {}).get('name', tid)}×{n}" for tid, n in troops.items() if n]
    return "، ".join(parts) if parts else "بدون نیرو"

async def defending_troops(castle_name: str, owner_tg_id: int) -> dict:
    """مجموع نیروهای «دفاعی»/«جای‌گیری»ِ فعالِ صاحب قلعه که مستقر همان‌جاست"""
    total = {}
    cur = campaigns.find({
        "tg_id": owner_tg_id, "active": True,
        "op_type": {"$in": list(DEFENSE_OP_TYPES)}, "target_castle": castle_name,
    })
    async for c in cur:
        for tid, n in c.get("troops", {}).items():
            total[tid] = total.get(tid, 0) + n
    return total

async def notify_arrivals():
    """کلاغی به مبدا که «لشکرت رسید» و کلاغی به صاحب مقصد که «لشکری به قلعه‌ات رسید» —
    یک‌بار برای هر لشکر، دقیقاً وقتی اولین بار به arrival_at می‌رسد. برای نبردهای واقعی
    (حمله/محاصره/غارت دریایی) آمار نیروهای مهاجم و مدافع هم برای هر دو طرف فرستاده می‌شود
    تا هر دو تا ۶ ساعت بعد سناریوی جنگ را از صفحهٔ رول‌ها بفرستند"""
    cur = campaigns.find({"active": True, "arrival_notified": {"$ne": True}, "arrival_at": {"$lte": now()}})
    async for c in cur:
        origin, target = c["origin_castle"], c["target_castle"]
        same_castle = origin == target
        name = c.get("name") or OP_TYPES.get(c["op_type"], {}).get("name", c["op_type"])
        if not same_castle:
            await send_system_message(
                c["tg_id"], c["player_name"],
                f"لشکرت «{name}» از {origin} به {target} رسید.",
            )
        target_owner = await players.find_one({"castle": target})
        if target_owner and target_owner["tg_id"] != c["tg_id"]:
            await send_system_message(
                target_owner["tg_id"], target_owner["name"],
                f"لشکری از {origin} با نام «{name}» به قلعه‌ات ({target}) رسید — مراقب باش.",
            )

        if c["op_type"] in ATTACK_OP_TYPES and target_owner and target_owner["tg_id"] != c["tg_id"]:
            attacker_summary = troops_summary(c.get("troops", {}))
            defense_troops = await defending_troops(target, target_owner["tg_id"])
            defender_summary = troops_summary(defense_troops)
            defender_power = campaign_power(defense_troops, _building_levels(target_owner))
            attacker_power = c.get("power", 0)
            stats_text = (
                f"آمار نبرد «{name}» در {target}:\n"
                f"مهاجم ({c['player_name']}): {attacker_summary} — توان {attacker_power}\n"
                f"مدافع ({target_owner['name']}): {defender_summary} — توان {defender_power}\n"
                f"هر دو طرف تا {ROLEPLAY_WINDOW_HOURS} ساعت دیگر فرصت دارید سناریوی این نبرد را از صفحهٔ رول‌ها (دستهٔ جنگ) بفرستید — ادمین نتیجه را برای هر دو طرف می‌فرستد."
            )
            await send_system_message(c["tg_id"], c["player_name"], stats_text)
            await send_system_message(target_owner["tg_id"], target_owner["name"], stats_text)

        await campaigns.update_one({"_id": c["_id"]}, {"$set": {"arrival_notified": True}})

@router.get("/roleplay-eligible")
async def roleplay_eligible(user: dict = Depends(get_user)):
    """نبردهایی که همین تازگی رسیده‌اند (چه به‌عنوان مهاجم چه مدافع) و بازیکن هنوز
    سناریویش را برای آن‌ها نفرستاده — برای انتخابگر دستهٔ «جنگ» در صفحهٔ رول‌ها"""
    p = await players.find_one({"tg_id": user["id"]})
    if not p:
        return []
    cutoff = now() - timedelta(hours=ROLEPLAY_WINDOW_HOURS)

    async def build(c, role):
        already = await roleplays.find_one({"tg_id": user["id"], "campaign_id": str(c["_id"])})
        if already:
            return None
        return {
            "campaign_id": str(c["_id"]), "role": role,
            "name": c.get("name") or OP_TYPES.get(c["op_type"], {}).get("name", c["op_type"]),
            "origin": c["origin_castle"], "target": c["target_castle"],
            "arrival_at": c["arrival_at"].isoformat(),
        }

    out = []
    cur = campaigns.find({
        "tg_id": user["id"], "op_type": {"$in": list(ATTACK_OP_TYPES)},
        "arrival_at": {"$lte": now(), "$gte": cutoff},
    })
    async for c in cur:
        row = await build(c, "attacker")
        if row:
            out.append(row)

    cur2 = campaigns.find({
        "tg_id": {"$ne": user["id"]}, "op_type": {"$in": list(ATTACK_OP_TYPES)},
        "target_castle": p["castle"],
        "arrival_at": {"$lte": now(), "$gte": cutoff},
    })
    async for c in cur2:
        row = await build(c, "defender")
        if row:
            out.append(row)

    out.sort(key=lambda r: r["arrival_at"], reverse=True)
    return out
