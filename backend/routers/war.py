from datetime import datetime, timedelta
from bson import ObjectId
from fastapi import APIRouter, Depends, HTTPException
from pydantic import BaseModel
from auth import get_user
from db import players, campaigns, map_castles, roleplays, game_settings, alliances
from game import now, can_afford, pay, normalize_building_state, add_resources, owned_castles, building_levels_for
from game_data import (
    COMMON_TROOPS, REGIONS, SPECIAL_TROOP_COST, BUILDINGS, unit_requirements, campaign_power,
    NAVAL_TROOPS, NAVAL_CAMP_BUILDING, TROOP_WEAPON_KEY, WEAPON_PER_SOLDIER, WEAPON_NAMES, MAP_TERRAINS, travel_routes,
    _dijkstra_path, DEFAULT_SEA_CASTLES, SIEGE_EQUIPMENT, SIEGE_WORKSHOP_BUILDING,
)
from config import FOOD_COST_REGULAR, FOOD_COST_SPECIAL
from routers.ravens import send_system_message
from admin_notifications import notify_admins

router = APIRouter(prefix="/api/war", tags=["war"])

# needs_target=False یعنی مقصد لازم نیست (دفاعی — مقصد داخلی = مبدا)
# port_only=True یعنی مقصد باید یک قلعه/شهر بندری باشد (غارت دریایی)
# land_only=True یعنی مقصد نباید بندری باشد (محاصره — فقط علیه قلعه‌های خشکی معنا دارد)
OP_TYPES = {
    "attack":     {"name": "حملهٔ نظامی",                     "needs_target": True,  "port_only": False, "land_only": False},
    "siege":      {"name": "محاصرهٔ قلعه (فقط اهداف غیربندری)", "needs_target": True,  "port_only": False, "land_only": True},
    "naval_raid": {"name": "غارت دریایی (برای اهداف بندری)",  "needs_target": True,  "port_only": True,  "land_only": False},
    "garrison":   {"name": "جای‌گیری",                         "needs_target": True,  "port_only": False, "land_only": False},
    "defense":    {"name": "دفاعی",                           "needs_target": False, "port_only": False, "land_only": False},
}

# نبردهای واقعی (نه جای‌گیری/دفاعی) — بعد از رسیدن، آمار دو طرف رد و بدل می‌شود و
# هر دو طرف تا ROLEPLAY_WINDOW_HOURS بعد فرصت دارند سناریوی جنگ را از صفحهٔ رول‌ها بفرستند
ATTACK_OP_TYPES = {"attack", "siege", "naval_raid"}
DIRECT_ATTACK_OP_TYPES = {"attack", "naval_raid"}
DEFENSE_OP_TYPES = {"defense", "garrison"}
ROLEPLAY_WINDOW_HOURS = 6

def campaign_waiting_for_result(campaign: dict) -> bool:
    """حملهٔ مستقیم از لحظهٔ رسیدن تا ثبت نتیجه توسط ادمین قفل است. این محاسبه
    مستقل از واچر/فلگ دیتابیس است تا در فاصلهٔ اجرای واچر یا برای مقصد خالی هم
    هیچ راهی برای حرکت یا لغو حمله وجود نداشته باشد."""
    arrival_at = campaign.get("arrival_at")
    return bool(
        campaign.get("active")
        and campaign.get("op_type") in DIRECT_ATTACK_OP_TYPES
        and (not arrival_at or now() >= arrival_at)
        and not campaign.get("combat_resolved_at")
    )

# ۲۴ ساعت بعد از رسیدن، گزارش لشکرکشی از تب گزارش‌های بازیکن پاک می‌شود
REPORT_VISIBLE_HOURS = 24

WAR_WINDOW_ID = "war_window"

async def get_war_window() -> dict:
    """پیش‌فرض باز است — تا وقتی ادمین صریحاً نبندتش، رفتار بازی مثل قبل می‌ماند"""
    doc = await game_settings.find_one({"_id": WAR_WINDOW_ID})
    if not doc:
        return {"open": True, "updated_at": None, "updated_by": None}
    return {"open": doc.get("open", True), "updated_at": doc.get("updated_at"), "updated_by": doc.get("updated_by")}

@router.get("/window")
async def war_window(user: dict = Depends(get_user)):
    """وضعیت فعلی پنجرهٔ لشکرکشی — پلیر باید بتواند قبل از پرکردن فرم ببیند بسته است یا باز"""
    w = await get_war_window()
    return {"open": w["open"], "updated_at": w["updated_at"].isoformat() if w["updated_at"] else None}

def _building_levels(player: dict, castle: str | None = None) -> dict:
    """سطحِ ساختمان‌های یک قلعهٔ مشخصِ این بازیکن — پیش‌فرض قلعهٔ اصلی‌اش. برای قدرتِ
    حمله/دفاع باید همیشه قلعهٔ واقعاً درگیر در نبرد را داد، نه لزوماً خانه‌اش، چون
    ممکن است این بازیکن چند قلعه (پایگاه) داشته باشد"""
    return dict(building_levels_for(player, castle or player.get("castle")))

class CampaignBody(BaseModel):
    origin_castle: str
    op_type: str
    target_castle: str | None = None
    name: str = ""
    troops: dict            # {troop_id: count}
    equipment: dict = {}    # {equipment_id: count}
    via: list[str] | None = None   # مسیرِ انتخابیِ بازیکن (اگر چند گزینهٔ مسیر بود) — از /war/routes

class MoveCampaignBody(BaseModel):
    target_castle: str
    op_type: str = "garrison"
    via: list[str] | None = None

async def all_castle_terrain() -> dict:
    """نگاشتِ اسمِ هر قلعه/شهرِ بازی (استاتیک + آنچه ادمین به نقشه اضافه کرده) به نوع
    زمینش: land | coastal | sea. منبعِ اصلی فیلدِ terrain روی map_castles است — همان‌جا
    که ادمین موقع گذاشتنِ پین از تب نقشه مشخصش می‌کند. برای قلعه‌هایی که هنوز پین
    ندارند، پیش‌فرض روی دیتای استاتیکِ REGIONS است (castles→land, ports→coastal، مگر
    آن‌هایی که در DEFAULT_SEA_CASTLES‌اند و اصلاً راهِ خشکی ندارند→sea)"""
    terrain = {}
    for r in REGIONS.values():
        for c in r["castles"]:
            terrain[c] = "land"
        for c in r["ports"]:
            terrain[c] = "sea" if c in DEFAULT_SEA_CASTLES else "coastal"
    async for m in map_castles.find({}):
        t = m.get("terrain")
        if t in MAP_TERRAINS:
            terrain[m["name"]] = t
        elif m["name"] not in terrain:
            # پینِ قدیمی/سفارشیِ بدون فیلدِ terrain — بر اساسِ kindِ آیکنش حدس می‌زنیم
            terrain[m["name"]] = "coastal" if m.get("kind", "port" if m.get("port") else "castle") == "port" else "land"
    return terrain

async def all_castle_names_and_ports():
    """اسم همهٔ قلعه/شهرهای بازی و زیرمجموعهٔ بندری‌ها (خشکی‌دریایی یا کاملاً دریایی)"""
    terrain = await all_castle_terrain()
    names = set(terrain.keys())
    ports = {n for n, t in terrain.items() if t in ("coastal", "sea")}
    return names, ports

async def region_of_castle(castle: str) -> str | None:
    """اقلیمی که این قلعه واقعاً توش قرار داره — نیروهای ویژه‌ای که از این قلعه
    می‌شه ساخت باید بر همین اساس باشه، نه بر اساس اقلیمِ خانگیِ بازیکن (که ممکنه
    قلعهٔ دومش در یک اقلیمِ دیگه باشه). برای قلعه‌های استاتیک از REGIONS، برای
    قلعه/شهرهای سفارشیِ ادمین از فیلدِ region روی پینِ نقشه‌اش"""
    for rid, r in REGIONS.items():
        if castle in r["castles"] or castle in r["ports"]:
            return rid
    m = await map_castles.find_one({"name": castle})
    return m["region"] if m else None

PASSAGE_ALLIANCE_TYPES = ["non_aggression", "full_alliance"]  # پیمان تجاری فقط برای کاروان/مناسبات تجاریه، ربطی به عبورِ لشکر نداره

async def allied_tg_ids(tg_id: int) -> set:
    """هرکسی که با tg_id پیمانِ پذیرفته‌شدهٔ عدم‌تجاوز یا اتحاد کامل دارد — این دو
    اجازهٔ عبورِ لشکر از قلمرو را می‌دهند، پیمان تجاری نه"""
    out = set()
    async for a in alliances.find({
        "status": "accepted", "type": {"$in": PASSAGE_ALLIANCE_TYPES},
        "$or": [{"from_id": tg_id}, {"to_id": tg_id}],
    }):
        out.add(a["to_id"] if a["from_id"] == tg_id else a["from_id"])
    return out

async def players_are_friendly(a_id: int, b_id: int) -> bool:
    """فقط عدم‌تجاوز و اتحاد کامل جلوی ساخته‌شدن پروندهٔ نبرد را می‌گیرند."""
    if a_id == b_id:
        return True
    return b_id in await allied_tg_ids(a_id)

async def active_peace_pact(a_id: int, b_id: int):
    return await alliances.find_one({
        "status": "accepted", "type": {"$in": PASSAGE_ALLIANCE_TYPES},
        "$or": [{"from_id": a_id, "to_id": b_id}, {"from_id": b_id, "to_id": a_id}],
    })

async def reject_hostile_order_during_pact(attacker_tg_id: int, target_castle: str, op_type: str):
    """در عدم‌تجاوز و اتحاد کامل، فقط فرمان غیرخصمانهٔ جای‌گیری مجاز است."""
    if op_type not in ATTACK_OP_TYPES:
        return
    target_player = await owner_of_castle(target_castle)
    if not target_player or target_player["tg_id"] == attacker_tg_id:
        return
    pact = await active_peace_pact(attacker_tg_id, target_player["tg_id"])
    if pact:
        pact_name = "اتحاد کامل" if pact.get("type") == "full_alliance" else "پیمان عدم تجاوز"
        raise HTTPException(403, f"با صاحب این قلعه {pact_name} داری؛ حمله، محاصره و غارت ممنوع است و فقط می‌توانی جای‌گیری کنی")

async def owner_of_castle(castle: str) -> dict | None:
    """صاحبِ یک قلعه — چه قلعهٔ اصلی‌اش باشه چه یکی از قلعه‌های اضافه‌ای که فتح کرده"""
    return await players.find_one({"$or": [
        {"castle": castle}, {f"castle_buildings.{castle}": {"$exists": True}},
    ]})

async def blocked_castles_for(tg_id: int) -> frozenset:
    """قلعه‌های دیگر بازیکن‌هایی که با tg_id پیمانی ندارند — لشکرِ tg_id نمی‌تواند
    از این قلعه‌ها رد شود (فقط برای مقصد نهایی استثنا می‌شود، نه عبور میان‌راه).
    قلعهٔ اصلی و هر قلعهٔ اضافه‌ای (فتح‌شده) که آن بازیکن دارد، هر دو قلمروِ اشغالی
    حساب می‌شوند"""
    allies = await allied_tg_ids(tg_id)
    blocked = set()
    async for other in players.find({"tg_id": {"$ne": tg_id}}, {"tg_id": 1, "castle": 1, "castle_buildings": 1}):
        if other["tg_id"] in allies:
            continue
        for c in owned_castles(other):
            blocked.add(c)
    return frozenset(blocked)

async def blocked_route_message(origin_castle: str, target_castle: str, blocked: frozenset) -> str:
    """وقتی مسیر پیدا نشود، به‌جای پیام کلی، دقیقاً می‌گوید مسیرِ طبیعی از کدام قلعه(ها)
    می‌گذرد که دستِ بازیکنی‌ست که با او پیمان نداری — تا بداند باید با چه کسی پیمان ببندد"""
    _min, natural_path = _dijkstra_path(origin_castle, target_castle, frozenset())
    generic = "مسیری بین این دو قلعه پیدا نشد — یا مسیرها از قلمروِ لردی می‌گذرد که با او پیمان نداری"
    if not natural_path:
        return generic
    blockers = [c for c in natural_path[1:-1] if c in blocked]
    if not blockers:
        return generic
    owners = {}
    for c in blockers:
        pl = await owner_of_castle(c)
        if pl:
            owners[c] = pl
    parts = []
    for c in blockers:
        o = owners.get(c)
        who = f"{o['name']}{' · ' + o['title'] if o and o.get('title') else ''}" if o else "یکی دیگر"
        parts.append(f"«{c}» (دستِ {who})")
    return "این قلعه سرِ راهت است و باهاش پیمان نداری: " + "، ".join(parts) if len(parts) == 1 else \
        "این قلعه‌ها سرِ راهت هستند و باهاشان پیمان نداری: " + "، ".join(parts)

async def has_non_aggression_pact(a_id: int, b_id: int):
    """پیمانِ عدم‌تجاوزِ پذیرفته‌شده بین این دو نفر، اگر باشد (برای چک غرامتِ خیانت)"""
    return await alliances.find_one({
        "status": "accepted", "type": "non_aggression",
        "$or": [{"from_id": a_id, "to_id": b_id}, {"from_id": b_id, "to_id": a_id}],
    })

def troop_food_and_gold(region: str, troops: dict, buildings: dict, is_port: bool):
    """هزینهٔ طلا (یک‌باره)، نفرات کل، آذوقهٔ روزانه، و تسلیحات مصرفی این ترکیب لشکر را حساب
    می‌کند. برای هر نیروی عمومی فقط ساخته‌بودن پادگانش شرط است — کارگاه تسلیحات دیگر
    پیش‌نیاز نیست، فقط منبع تسلیحاتی‌ست که موقع اعزام مصرف می‌شود (چک کافی‌بودنش را
    فراخوان بعد از این تابع، روی resources واقعی بازیکن انجام می‌دهد)"""
    specials = REGIONS[region]["special"]
    gold = men = food = 0
    weapons = {}
    for tid, n in troops.items():
        if n <= 0:
            continue
        if tid in COMMON_TROOPS:
            req = unit_requirements(tid)
            if req:
                camp_id, _armory_id = req
                camp_level = normalize_building_state(buildings.get(camp_id))["level"]
                if camp_level <= 0:
                    raise HTTPException(400, f"برای گسیل {COMMON_TROOPS[tid]['name']} باید {BUILDINGS[camp_id]['name']} را ساخته باشی")
            weapon_key = TROOP_WEAPON_KEY.get(tid)
            if weapon_key:
                weapons[weapon_key] = weapons.get(weapon_key, 0) + n * WEAPON_PER_SOLDIER
            gold += COMMON_TROOPS[tid]["cost"] * n
            food += FOOD_COST_REGULAR * n
        elif tid in NAVAL_TROOPS:
            if not is_port:
                raise HTTPException(400, "فقط قلعه/شهرهای خشکی‌دریایی یا کاملاً دریایی می‌توانند کشتی بسازند")
            port_level = normalize_building_state(buildings.get(NAVAL_CAMP_BUILDING))["level"]
            if port_level <= 0:
                raise HTTPException(400, f"برای ساخت {NAVAL_TROOPS[tid]['name']} باید {BUILDINGS[NAVAL_CAMP_BUILDING]['name']} را بنا کرده باشی")
            gold += NAVAL_TROOPS[tid]["cost"] * n
            food += FOOD_COST_SPECIAL * n
        elif tid in specials:
            gold += SPECIAL_TROOP_COST * n
            food += FOOD_COST_SPECIAL * n
        else:
            raise HTTPException(400, f"نیروی نامعتبر: {tid}")
        men += n
    return gold, men, food, weapons

def equipment_cost_and_effect(equipment: dict, buildings: dict):
    workshop_level = normalize_building_state(buildings.get(SIEGE_WORKSHOP_BUILDING))["level"]
    cost, siege_power, slowdown = {}, 0, 0.0
    for eid, raw in equipment.items():
        count = max(0, int(raw or 0))
        if not count:
            continue
        if count > 100:
            raise HTTPException(400, "از هر نوع ادوات حداکثر ۱۰۰ عدد می‌توانی همراه یک لشکر ببری")
        meta = SIEGE_EQUIPMENT.get(eid)
        if not meta:
            raise HTTPException(400, "نوع ادوات نظامی نامعتبر است")
        if workshop_level < meta["level"]:
            raise HTTPException(400, f"برای ساخت {meta['name']} به کارگاه مهندسی ادوات سطح {meta['level']} نیاز داری")
        for resource, amount in meta["cost"].items():
            cost[resource] = cost.get(resource, 0) + amount * count
        siege_power += meta["siege_power"] * count
        slowdown += meta["slowdown"] * count
    return cost, siege_power, min(1.0, slowdown)

async def stationed_origins(tg_id: int) -> set:
    """قلعه‌هایی که لشکر فعلی این بازیکن با عملیات «جای‌گیری» در آن‌ها مستقر است —
    فقط جای‌گیری‌هایی که واقعاً رسیده‌اند، وگرنه لشکری که هنوز در راهِ جای‌گیری است
    می‌توانست همون لحظه مبدای یک فرمانِ کاملاً جدا و مستقل باشد"""
    origins = set()
    async for c in campaigns.find({"tg_id": tg_id, "active": True, "op_type": "garrison"}):
        arrival_at = c.get("arrival_at")
        if arrival_at and now() >= arrival_at:
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

@router.get("/routes")
async def routes(origin_castle: str, target_castle: str, user: dict = Depends(get_user)):
    """گزینه‌های مسیرِ واقعیِ بین دو قلعه (۱ یا ۲ تا) — قبل از فرستادنِ فرمان، برای
    اینکه بازیکن ببینه از کجاها رد می‌شود و اگه چند مسیر بود انتخاب کند"""
    if origin_castle == target_castle:
        return {"routes": [{"minutes": 0, "path": [origin_castle]}]}
    terrain = await all_castle_terrain()
    if origin_castle not in terrain or target_castle not in terrain:
        raise HTTPException(400, "قلعهٔ مبدا یا مقصد شناخته‌شده نیست")
    blocked = await blocked_castles_for(user["id"])
    opts = travel_routes(origin_castle, target_castle, blocked, terrain=terrain)
    if not opts:
        raise HTTPException(400, await blocked_route_message(origin_castle, target_castle, blocked))
    return {"routes": opts}

@router.post("/submit")
async def submit(body: CampaignBody, user: dict = Depends(get_user)):
    p = await players.find_one({"tg_id": user["id"]})
    if not p:
        raise HTTPException(403, "اول ثبت‌نام کن")

    op = OP_TYPES.get(body.op_type)
    if not op:
        raise HTTPException(400, "نوع عملیات نامعتبر")

    if not (await get_war_window())["open"]:
        raise HTTPException(403, "پنجرهٔ لشکرکشی الان بسته است — ادمین باید بازش کند تا بتوانی فرمان گسیل بدهی")

    p["resources"] = await apply_campaign_upkeep(user["id"], p["resources"])

    # قلعه‌ای که دشمن به آن رسیده و هنوز نتیجهٔ حمله/محاصره‌اش مشخص نشده، فقط
    # اجازهٔ ساخت لشکر دفاعی دارد؛ نه گسیل یک لشکر تازه و نه جای‌گیری در بیرون.
    origin_owner = await owner_of_castle(body.origin_castle)
    if body.op_type != "defense" and origin_owner and origin_owner["tg_id"] == user["id"]:
        besieged = await campaigns.find_one({
            "tg_id": {"$ne": user["id"]}, "active": True,
            "op_type": {"$in": list(ATTACK_OP_TYPES)},
            "target_castle": body.origin_castle, "arrival_at": {"$lte": now()},
            "combat_resolved_at": {"$exists": False},
        })
        if besieged:
            raise HTTPException(403, "این قلعه زیر حمله یا محاصره است — فعلاً فقط می‌توانی برای همین قلعه لشکر دفاعی بسازی")

    valid_origins = {p["castle"]} | set(p.get("castle_buildings", {})) | await stationed_origins(user["id"])
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
        if op["port_only"] and body.origin_castle not in ports:
            raise HTTPException(400, "غارت دریایی فقط از قلعه/شهرهای بندری ممکن است — لشکرکشی از راه آبی")
        if op["port_only"] and not any(tid in NAVAL_TROOPS and n and n > 0 for tid, n in body.troops.items()):
            raise HTTPException(400, "غارت دریایی باید با کشتی انجام شود — این فرمان هیچ کشتی‌ای همراه ندارد")
        if op.get("land_only") and body.target_castle in ports:
            raise HTTPException(400, "محاصره فقط علیه قلعه‌های غیربندری معنا دارد — برای هدف‌های بندری از غارت دریایی استفاده کن")
        target_castle = body.target_castle
    else:
        target_castle = body.origin_castle

    await reject_hostile_order_during_pact(user["id"], target_castle, body.op_type)

    terrain = await all_castle_terrain()
    origin_is_port = terrain.get(body.origin_castle, "land") in ("coastal", "sea")
    origin_region = await region_of_castle(body.origin_castle) or p["region"]
    origin_buildings = _building_levels(p, body.origin_castle)
    gold, men, food_per_day, weapons = troop_food_and_gold(origin_region, body.troops, origin_buildings, origin_is_port)
    equipment_cost, equipment_power, equipment_slowdown = equipment_cost_and_effect(body.equipment, origin_buildings)
    if men <= 0:
        raise HTTPException(400, "هیچ نیرویی گسیل نکرده‌ای")
    if not can_afford(p["resources"], {"gold": gold}):
        raise HTTPException(400, "خزانه کافی نیست")
    if p["resources"].get("men", 0) < men:
        raise HTTPException(400, "نفرات کافی نداری")
    for weapon_key, needed in weapons.items():
        if p["resources"].get(weapon_key, 0) < needed:
            raise HTTPException(400, f"{WEAPON_NAMES[weapon_key]} کافی نداری — کارگاه تسلیحاتش را بساز یا صبر کن بیشتر تولید شود")
    combined_cost = {"gold": gold, **weapons}
    for resource, amount in equipment_cost.items():
        combined_cost[resource] = combined_cost.get(resource, 0) + amount
    if not can_afford(p["resources"], combined_cost):
        raise HTTPException(400, "منابع لازم برای ساخت ادوات انتخاب‌شده کافی نیست")

    naval_capacity = sum(NAVAL_TROOPS[tid]["capacity"] * n for tid, n in body.troops.items() if tid in NAVAL_TROOPS and n and n > 0)
    land_men = sum(n for tid, n in body.troops.items() if tid not in NAVAL_TROOPS and n and n > 0)

    same_castle = target_castle == body.origin_castle
    if not same_castle:
        if terrain.get(body.origin_castle, "land") == "sea" and land_men > naval_capacity:
            raise HTTPException(400, f"این قلعه کاملاً دریایی است و راهی به خشکی ندارد — کشتی‌های این فرمان فقط {naval_capacity} نفر را جابه‌جا می‌کنند، کشتی بیشتری اضافه کن یا نیروی کمتری بفرست")
    blocked = frozenset() if same_castle else await blocked_castles_for(user["id"])
    if same_castle:
        travel, route_path = 0, [body.origin_castle]
    else:
        opts = travel_routes(body.origin_castle, target_castle, blocked, terrain=terrain)
        if not opts:
            raise HTTPException(400, await blocked_route_message(body.origin_castle, target_castle, blocked))
        chosen = next((r for r in opts if r["path"] == body.via), None) if body.via else None
        chosen = chosen or opts[0]
        if chosen["via_sea"] and land_men > naval_capacity:
            land_opts = travel_routes(body.origin_castle, target_castle, blocked, allow_sea=False, terrain=terrain)
            if land_opts:
                raise HTTPException(400, "این مسیر از آب می‌گذرد و کشتی‌های این فرمان ظرفیتِ کافی برای حملِ همهٔ نیروهای زمینی را ندارند — یا کشتی بیشتری اضافه کن، یا مسیرِ زمینیِ دیگری که از /war/routes پیشنهاد می‌شود انتخاب کن")
            raise HTTPException(400, f"این مسیر فقط از راهِ آب ممکن است و کشتی‌های این فرمان فقط {naval_capacity} نفر را جابه‌جا می‌کنند — کشتی بیشتری اضافه کن یا نیروی کمتری بفرست")
        travel, route_path = chosen["minutes"], chosen["path"]
    travel = max(travel, round(travel * (1 + equipment_slowdown)))
    arrival_at = now() + timedelta(minutes=travel)
    power = campaign_power(body.troops, _building_levels(p, body.origin_castle))

    pay(p["resources"], combined_cost)
    p["resources"]["men"] = p["resources"].get("men", 0) - men

    # فرمان خصمانه علیه عدم‌تجاوز/اتحاد کامل بالاتر کاملاً مسدود شده است.
    # این فیلد فقط برای سازگاری پاسخ با نسخه‌های قدیمی باقی می‌ماند.
    penalty_charged = 0

    await players.update_one({"tg_id": user["id"]}, {"$set": {"resources": p["resources"], "points": p.get("points", 0)}})

    doc = {
        "tg_id": user["id"], "player_name": p["name"],
        "origin_castle": body.origin_castle,
        "op_type": body.op_type, "target_castle": target_castle,
        "name": body.name.strip()[:60] or op["name"], "troops": body.troops, "power": power,
        "gold_cost": gold, "men_committed": men, "food_per_day": food_per_day,
        "equipment": {k: int(v or 0) for k, v in body.equipment.items() if k in SIEGE_EQUIPMENT and int(v or 0) > 0},
        "equipment_cost": equipment_cost, "equipment_power": equipment_power,
        "travel_minutes": travel, "arrival_at": arrival_at, "route_path": route_path,
        "penalty_charged": penalty_charged,
        "active": True, "arrival_notified": False,
        "created_at": now(), "last_food_tick": now(),
    }
    res = await campaigns.insert_one(doc)
    return {
        "ok": True, "id": str(res.inserted_id), "gold_cost": gold, "men_committed": men, "power": power,
        "food_per_day": food_per_day, "travel_minutes": travel, "arrival_at": arrival_at.isoformat(),
        "route_path": route_path, "penalty_charged": penalty_charged,
    }

@router.post("/{campaign_id}/cancel")
async def cancel(campaign_id: str, user: dict = Depends(get_user)):
    """لغو تا پنج دقیقه بدون جریمه؛ پس از آن فقط نیمی از هزینه و نفرات برمی‌گردد."""
    c = await campaigns.find_one({"_id": ObjectId(campaign_id)})
    if not c or c["tg_id"] != user["id"]:
        raise HTTPException(404, "لشکر پیدا نشد")
    if not c.get("active"):
        raise HTTPException(400, "این لشکر دیگر فعال نیست")
    if c.get("engagement_locked") or campaign_waiting_for_result(c):
        raise HTTPException(409, "این لشکر درگیر نبرد است و تا ثبت نتیجه توسط ادمین قابل لغو یا حرکت نیست")

    # اتمیک و مشروط به active=True — وگرنه دو کلیکِ هم‌زمانِ لغو هردو از رویِ همون
    # خواندنِ قدیمی رد می‌شن و منابع/تسلیحات دوبار برمی‌گردن
    result = await campaigns.update_one(
        {"_id": c["_id"], "active": True}, {"$set": {"active": False, "status": "cancelled"}},
    )
    if result.matched_count == 0:
        raise HTTPException(400, "این لشکر دیگر فعال نیست")

    weapons_refund = {}
    for tid, n in c.get("troops", {}).items():
        if not n or n <= 0:
            continue
        weapon_key = TROOP_WEAPON_KEY.get(tid)
        if weapon_key:
            weapons_refund[weapon_key] = weapons_refund.get(weapon_key, 0) + n * WEAPON_PER_SOLDIER

    grace_started_at = c.get("moved_at") or c.get("created_at") or now()
    penalty_applied = (now() - grace_started_at) > timedelta(minutes=5)
    refund_ratio = 0.5 if penalty_applied else 1.0
    def refundable(value):
        return max(0, int(int(value or 0) * refund_ratio))

    p = await players.find_one({"tg_id": user["id"]})
    if p:
        equipment_refund = {k: refundable(v) for k, v in c.get("equipment_cost", {}).items()}
        weapons_refund = {k: refundable(v) for k, v in weapons_refund.items()}
        deltas = {"men": refundable(c["men_committed"]), "gold": refundable(c["gold_cost"]), **weapons_refund}
        for resource, amount in equipment_refund.items():
            deltas[resource] = deltas.get(resource, 0) + amount
        add_resources(p, deltas)
        await players.update_one({"tg_id": user["id"]}, {"$set": {"resources": p["resources"]}})
    return {
        "ok": True, "penalty_applied": penalty_applied, "refund_ratio": refund_ratio,
        "men_refunded": refundable(c["men_committed"]), "gold_refunded": refundable(c["gold_cost"]),
        "weapons_refunded": weapons_refund, "equipment_refunded": equipment_refund,
    }

@router.post("/{campaign_id}/move")
async def move_campaign(campaign_id: str, body: MoveCampaignBody, user: dict = Depends(get_user)):
    """همان لشکرِ رسیده را بدون ساخت دوباره و بدون کم‌کردن نفرات/طلا به مقصد بعدی می‌فرستد."""
    try:
        oid = ObjectId(campaign_id)
    except Exception:
        raise HTTPException(400, "شناسهٔ لشکر نامعتبر است")
    c = await campaigns.find_one({"_id": oid, "tg_id": user["id"], "active": True})
    if not c:
        raise HTTPException(404, "لشکر فعال پیدا نشد")
    if c.get("engagement_locked") or campaign_waiting_for_result(c):
        raise HTTPException(409, "این لشکر درگیر نبرد است و تا ثبت نتیجه توسط ادمین قفل می‌ماند")
    if c.get("arrival_at") and now() < c["arrival_at"]:
        raise HTTPException(400, "این لشکر هنوز به مقصد قبلی نرسیده است")
    if body.op_type not in ("attack", "siege", "naval_raid", "garrison"):
        raise HTTPException(400, "فرمان حرکت نامعتبر است")
    if not (await get_war_window())["open"]:
        raise HTTPException(403, "پنجرهٔ لشکرکشی بسته است")

    origin = c["target_castle"]
    if body.target_castle == origin:
        raise HTTPException(400, "مقصد جدید باید با محل فعلی لشکر فرق داشته باشد")
    names, ports = await all_castle_names_and_ports()
    if body.target_castle not in names:
        raise HTTPException(400, "مقصد در نقشه شناخته‌شده نیست")
    if body.op_type == "siege" and body.target_castle in ports:
        raise HTTPException(400, "محاصره فقط برای قلعه‌های غیربندری است")
    if body.op_type == "naval_raid" and (origin not in ports or body.target_castle not in ports):
        raise HTTPException(400, "غارت دریایی باید از یک بندر به بندر دیگر باشد")
    await reject_hostile_order_during_pact(user["id"], body.target_castle, body.op_type)

    # از قلعهٔ تحت حمله نمی‌شود لشکر مستقر را هم فراری داد؛ دفاع باید همان‌جا بماند.
    origin_owner = await owner_of_castle(origin)
    if origin_owner and origin_owner["tg_id"] == user["id"]:
        besieged = await campaigns.find_one({
            "tg_id": {"$ne": user["id"]}, "active": True,
            "op_type": {"$in": list(ATTACK_OP_TYPES)}, "target_castle": origin,
            "arrival_at": {"$lte": now()}, "combat_resolved_at": {"$exists": False},
        })
        if besieged:
            raise HTTPException(403, "این قلعه زیر حمله یا محاصره است و هیچ لشکری نمی‌تواند از آن خارج شود")

    terrain = await all_castle_terrain()
    blocked = await blocked_castles_for(user["id"])
    opts = travel_routes(origin, body.target_castle, blocked, terrain=terrain)
    if not opts:
        raise HTTPException(400, await blocked_route_message(origin, body.target_castle, blocked))
    chosen = next((r for r in opts if r["path"] == body.via), None) if body.via else None
    chosen = chosen or opts[0]
    troops = {k: max(0, int(v or 0)) for k, v in c.get("troops", {}).items()}
    naval_capacity = sum(NAVAL_TROOPS[t]["capacity"] * n for t, n in troops.items() if t in NAVAL_TROOPS)
    land_men = sum(n for t, n in troops.items() if t not in NAVAL_TROOPS)
    if chosen.get("via_sea") and land_men > naval_capacity:
        raise HTTPException(400, f"کشتی‌های این لشکر فقط ظرفیت جابه‌جایی {naval_capacity} نیروی زمینی را دارند")

    move_slowdown = min(1.0, sum(SIEGE_EQUIPMENT.get(eid, {}).get("slowdown", 0) * int(count or 0) for eid, count in c.get("equipment", {}).items()))
    move_minutes = max(chosen["minutes"], round(chosen["minutes"] * (1 + move_slowdown)))
    arrival_at = now() + timedelta(minutes=move_minutes)
    await campaigns.update_one({"_id": oid}, {
        "$set": {
            "origin_castle": origin, "target_castle": body.target_castle,
            "op_type": body.op_type, "travel_minutes": move_minutes,
            "route_path": chosen["path"], "arrival_at": arrival_at,
            "arrival_notified": False, "moved_at": now(),
        },
        "$unset": {
            "combat_resolved_at": "", "combat_outcome": "", "winner_tg_id": "",
            "medal_outcome_recorded": "", "engagement_campaign_id": "",
        },
    })
    return {"ok": True, "arrival_at": arrival_at.isoformat(), "travel_minutes": move_minutes, "route_path": chosen["path"]}

@router.post("/{campaign_id}/attack")
async def order_siege_attack(campaign_id: str, user: dict = Depends(get_user)):
    """محاصرهٔ رسیده را به حملهٔ مستقیم تبدیل می‌کند؛ واچر درگیری را ایجاد و لشکرها را قفل می‌کند."""
    try:
        oid = ObjectId(campaign_id)
    except Exception:
        raise HTTPException(400, "شناسهٔ لشکر نامعتبر است")
    c = await campaigns.find_one({"_id": oid, "tg_id": user["id"], "active": True})
    if not c:
        raise HTTPException(404, "لشکر پیدا نشد")
    if c.get("op_type") != "siege" or (c.get("arrival_at") and now() < c["arrival_at"]):
        raise HTTPException(400, "فقط لشکر محاصره‌ای که به مقصد رسیده می‌تواند دستور حمله بگیرد")
    if c.get("engagement_locked"):
        raise HTTPException(409, "این لشکر همین حالا درگیر نبرد است")
    await reject_hostile_order_during_pact(user["id"], c["target_castle"], "attack")
    await campaigns.update_one({"_id": oid}, {"$set": {
        "op_type": "attack", "arrival_at": now(), "arrival_notified": False, "attack_ordered_at": now(),
    }})
    return {"ok": True}

@router.get("/legions")
async def legions(user: dict = Depends(get_user)):
    """همهٔ لشکرهای فعالِ من — از جمله دفاعی/جای‌گیری — برای مدیریت (لغو یا حرکت‌دادن).
    برخلاف /mine که فقط برای گزارش تهاجمی‌ها و با تأخیر/بازهٔ زمانی محدود است، اینجا
    خودِ صاحبِ لشکرهاست که دارد می‌بیند، پس نه چیزی حذف می‌شود نه پنهان"""
    cur = campaigns.find({"tg_id": user["id"], "active": True}).sort("created_at", -1).limit(50)
    out = []
    async for c in cur:
        is_mine = c["tg_id"] == user["id"]
        arrival_at = c.get("arrival_at")
        arrived = (now() >= arrival_at) if arrival_at else True
        waiting_result = campaign_waiting_for_result(c)
        troops = [
            {"name": troop_name(t), "count": n}
            for t, n in c.get("troops", {}).items() if n and n > 0
        ]
        out.append({
            "id": str(c["_id"]),
            # نوع فرمان و نام سفارشی فقط برای صاحب همان لشکر است؛ گزارش عمومی
            # صرفاً وجود و مسیر لشکرکشی را نشان می‌دهد.
            "mine": is_mine,
            "op_type": c["op_type"] if is_mine else None,
            "op_name": OP_TYPES.get(c["op_type"], {}).get("name", c["op_type"]) if is_mine else "لشکرکشی",
            "name": (c.get("name") or OP_TYPES.get(c["op_type"], {}).get("name", c["op_type"])) if is_mine else "لشکرکشی",
            "origin": c["origin_castle"], "target": c["target_castle"],
            "troops": troops, "men_committed": c["men_committed"], "power": c.get("power", 0),
            "equipment": c.get("equipment", {}), "equipment_power": c.get("equipment_power", 0),
            "travel_minutes": c.get("travel_minutes", 0), "route_path": c.get("route_path"),
            "arrived": arrived,
            "engagement_locked": bool(c.get("engagement_locked") or waiting_result),
            "waiting_for_result": waiting_result,
            "can_move": arrived and not c.get("engagement_locked") and not waiting_result,
            "can_attack": c["op_type"] == "siege" and arrived and not c.get("engagement_locked"),
            "created_at": c["created_at"].isoformat(),
            "arrival_at": arrival_at.isoformat() if arrival_at else None,
        })
    return out

@router.get("/mine")
async def mine(user: dict = Depends(get_user)):
    """گزارش لشکرکشی‌های همهٔ بازیکنان — عمداً حداقلی: فقط اسم، فرستنده، مبدا/مقصد و زمان رسیدن؛
    نه توان نه ترکیب/تعداد نیرو. لشکر دفاعی (همون‌جایی) اصلاً وارد گزارش‌ها نمی‌شود، و
    لشکری که بیش از REPORT_VISIBLE_HOURS ساعت پیش رسیده دیگر توی این لیست نمی‌آید"""
    cur = campaigns.find({"op_type": {"$ne": "defense"}}).sort("created_at", -1).limit(100)
    out = []
    async for c in cur:
        arrival_at = c.get("arrival_at")
        arrived = (now() >= arrival_at) if arrival_at else True
        if arrived and arrival_at and now() - arrival_at > timedelta(hours=REPORT_VISIBLE_HOURS):
            continue
        out.append({
            "id": str(c["_id"]),
            "op_type": c["op_type"], "op_name": OP_TYPES.get(c["op_type"], {}).get("name", c["op_type"]),
            "name": c.get("name") or OP_TYPES.get(c["op_type"], {}).get("name", c["op_type"]),
            "sender": c["player_name"],
            "origin": c["origin_castle"], "target": c["target_castle"],
            "active": c.get("active", False),
            "travel_minutes": c.get("travel_minutes", 0), "route_path": c.get("route_path"),
            "arrived": arrived,
            "created_at": c["created_at"].isoformat(),
            "arrival_at": arrival_at.isoformat() if arrival_at else None,
        })
    if len(out) > 30:
        out = out[:30]
    return out

def troop_name(tid: str) -> str:
    """اسمِ فارسیِ یک نیرو، چه عمومی/ویژه باشه چه دریایی — نیروهای ویژه کلیدشون خودِ
    اسمِ فارسیه (خودش fallback درسته)"""
    if tid in COMMON_TROOPS:
        return COMMON_TROOPS[tid]["name"]
    if tid in NAVAL_TROOPS:
        return NAVAL_TROOPS[tid]["name"]
    return tid

def troops_summary(troops: dict) -> str:
    parts = [f"{troop_name(tid)}×{n}" for tid, n in troops.items() if n]
    return "، ".join(parts) if parts else "بدون نیرو"

def battle_army_snapshot(campaign: dict) -> dict:
    return {
        "campaign_id": str(campaign.get("_id", "")),
        "name": campaign.get("name", "لشکر"),
        "men": campaign.get("men_committed", sum(campaign.get("troops", {}).values())),
        "troops": dict(campaign.get("troops", {})),
        "equipment": dict(campaign.get("equipment", {})),
        "equipment_power": int(campaign.get("equipment_power", 0) or 0),
    }

async def notify_battle_admins(engagement_id: str, location: str, attacker: dict, defender: dict, defender_troops: dict):
    """همان لحظهٔ تشکیل پروندهٔ نبرد، آمار دو طرف را در بات و پنل همهٔ ادمین‌ها می‌فرستد."""
    attacker_troops = dict(attacker.get("troops", {}))
    attacker_total = sum(max(0, int(n or 0)) for n in attacker_troops.values())
    defender_total = sum(max(0, int(n or 0)) for n in defender_troops.values())
    attacker_name = attacker.get("player_name") or "مهاجم"
    defender_name = defender.get("player_name") or defender.get("name") or "مدافع"
    detail = (
        f"محل درگیری: {location}\n"
        f"{attacker_name}: {attacker_total} نفر — {troops_summary(attacker_troops)}\n"
        f"{defender_name}: {defender_total} نفر — {troops_summary(defender_troops)}"
    )
    attacker_equipment = "، ".join(f"{SIEGE_EQUIPMENT.get(k, {}).get('name', k)}×{v}" for k, v in attacker.get("equipment", {}).items() if v)
    defender_equipment = "، ".join(f"{SIEGE_EQUIPMENT.get(k, {}).get('name', k)}×{v}" for k, v in defender.get("equipment", {}).items() if v)
    if attacker_equipment or defender_equipment:
        detail += f"\nادوات {attacker_name}: {attacker_equipment or 'ندارد'}\nادوات {defender_name}: {defender_equipment or 'ندارد'}"
    await notify_admins(
        "battle_started", "⚔️ نبرد تازه آغاز شد", detail,
        dedupe_key=f"battle-started:{engagement_id}", priority="urgent",
        player_name=attacker_name, player_tg_id=attacker.get("tg_id"), castle=location,
        source_id=engagement_id, deadline=now() + timedelta(hours=ROLEPLAY_WINDOW_HOURS),
        action="در پنل ادمین ← نبردها، نیروها و رول‌های دو طرف را بررسی کن.",
    )
    # اعلان عمومی شروع نبرد: فقط هویت طرفین و محل؛ ترکیب/تعداد نیروها محرمانه و فقط
    # برای خود طرفین و ادمین‌هاست. فلگ اتمیک جلوی ارسال دوبارهٔ همان اعلان را می‌گیرد.
    try:
        root_id = ObjectId(engagement_id)
    except Exception:
        root_id = None
    claimed = await campaigns.update_one(
        {"_id": root_id, "public_start_notified": {"$ne": True}},
        {"$set": {"public_start_notified": True}},
    ) if root_id else None
    if claimed and claimed.modified_count:
        public_text = f"⚔️ نبردی میان لرد {attacker_name} و لرد {defender_name} در {location} آغاز شد."
        async for player in players.find({}, {"tg_id": 1, "name": 1}):
            await send_system_message(player["tg_id"], player["name"], public_text, kind="battle")

async def defending_troops(castle_name: str, owner_tg_id: int) -> dict:
    """مجموع نیروهای «دفاعی»/«جای‌گیری»ِ فعالِ صاحب قلعه که مستقر همان‌جاست"""
    total = {}
    cur = campaigns.find({
        "tg_id": owner_tg_id, "active": True,
        "op_type": {"$in": list(DEFENSE_OP_TYPES)}, "target_castle": castle_name,
        "arrival_at": {"$lte": now()},
    })
    async for c in cur:
        for tid, n in c.get("troops", {}).items():
            total[tid] = total.get(tid, 0) + n
    return total

async def detect_route_encounters():
    """برخورد دو لشکرِ بی‌پیمان روی یک یالِ مشترک و در جهت مخالف.
    زمان عبور هر قطعه متناسب با تعداد قطعه‌های مسیر محاسبه می‌شود؛ واچر در اولین
    تیک بعد از زمان تلاقی، هر دو لشکر را روی همان پروندهٔ نبرد قفل می‌کند."""
    moving = [c async for c in campaigns.find({
        "active": True, "engagement_locked": {"$ne": True}, "arrival_at": {"$gt": now()},
        "route_path.1": {"$exists": True},
    }).sort("arrival_at", 1).limit(100)]
    for i, a in enumerate(moving):
        for b in moving[i + 1:]:
            if a["tg_id"] == b["tg_id"] or await players_are_friendly(a["tg_id"], b["tg_id"]):
                continue
            pa, pb = a.get("route_path", []), b.get("route_path", [])
            shared = None
            for ai in range(len(pa) - 1):
                for bi in range(len(pb) - 1):
                    if pa[ai] == pb[bi + 1] and pa[ai + 1] == pb[bi]:
                        sa, ea = a.get("moved_at") or a.get("created_at"), a.get("arrival_at")
                        sb, eb = b.get("moved_at") or b.get("created_at"), b.get("arrival_at")
                        if not (sa and ea and sb and eb):
                            continue
                        a0 = sa + (ea - sa) * (ai / (len(pa) - 1)); a1 = sa + (ea - sa) * ((ai + 1) / (len(pa) - 1))
                        b0 = sb + (eb - sb) * (bi / (len(pb) - 1)); b1 = sb + (eb - sb) * ((bi + 1) / (len(pb) - 1))
                        meet_at = max(a0, b0)
                        if meet_at <= min(a1, b1) and now() >= meet_at:
                            shared = (pa[ai], pa[ai + 1], meet_at)
                            break
                if shared:
                    break
            if not shared:
                continue
            root, opponent = (a, b) if str(a["_id"]) < str(b["_id"]) else (b, a)
            engagement_id = str(root["_id"])
            location = f"مسیر {shared[0]} — {shared[1]}"
            await campaigns.update_one({"_id": root["_id"], "engagement_locked": {"$ne": True}}, {"$set": {
                "engagement_locked": True, "engagement_campaign_id": engagement_id,
                "opponent_campaign_id": str(opponent["_id"]), "opponent_tg_id": opponent["tg_id"],
                "battle_location": location, "battle_started_at": now(),
                "battle_open": True,
                "battle_attacker_snapshot": battle_army_snapshot(root),
                "battle_defender_snapshot": [battle_army_snapshot(opponent)],
                "battle_defender_tg_id": opponent["tg_id"],
                "battle_defender_name": opponent.get("player_name", "طرف مقابل"),
            }})
            await campaigns.update_one({"_id": opponent["_id"], "engagement_locked": {"$ne": True}}, {"$set": {
                "engagement_locked": True, "engagement_campaign_id": engagement_id,
                "opponent_campaign_id": str(root["_id"]), "opponent_tg_id": root["tg_id"],
                "battle_location": location, "battle_started_at": now(),
            }})
            root_eq = "، ".join(f"{SIEGE_EQUIPMENT.get(eid, {}).get('name', eid)}×{count}" for eid, count in root.get("equipment", {}).items() if count) or "بدون ادوات"
            opponent_eq = "، ".join(f"{SIEGE_EQUIPMENT.get(eid, {}).get('name', eid)}×{count}" for eid, count in opponent.get("equipment", {}).items() if count) or "بدون ادوات"
            msg = (
                f"لشکرهای شما در {location} با هم روبه‌رو شدند و تا اعلام نتیجهٔ ادمین قفل‌اند.\n"
                f"{root['player_name']}: {troops_summary(root.get('troops', {}))} · ادوات: {root_eq}\n"
                f"{opponent['player_name']}: {troops_summary(opponent.get('troops', {}))} · ادوات: {opponent_eq}\n"
                f"تا {ROLEPLAY_WINDOW_HOURS} ساعت فرصت ارسال رول جنگ دارید."
            )
            await send_system_message(root["tg_id"], root["player_name"], msg)
            await send_system_message(opponent["tg_id"], opponent["player_name"], msg)
            await notify_battle_admins(engagement_id, location, root, opponent, dict(opponent.get("troops", {})))

async def notify_arrivals():
    """کلاغی به مبدا که «لشکرت رسید» و کلاغی به صاحب مقصد که «لشکری به قلعه‌ات رسید» —
    یک‌بار برای هر لشکر، دقیقاً وقتی اولین بار به arrival_at می‌رسد. برای نبردهای واقعی
    (حمله/محاصره/غارت دریایی) آمار نیروهای مهاجم و مدافع هم برای هر دو طرف فرستاده می‌شود
    تا هر دو تا ۶ ساعت بعد سناریوی جنگ را از صفحهٔ رول‌ها بفرستند"""
    await detect_route_encounters()
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
        target_owner = await owner_of_castle(target)

        # دو لشکرِ بی‌پیمان که در یک قلعه (حتی قلعهٔ خالی) به هم می‌رسند، یک
        # پروندهٔ نبرد مشترک می‌سازند. قدیمی‌ترین لشکرِ حاضر طرف دوم است.
        opposing_army = None
        async for other in campaigns.find({
            "_id": {"$ne": c["_id"]}, "tg_id": {"$ne": c["tg_id"]}, "active": True,
            "target_castle": target, "arrival_at": {"$lte": now()},
            "combat_resolved_at": {"$exists": False},
            "engagement_locked": {"$ne": True},
        }).sort("arrival_at", 1):
            if not await players_are_friendly(c["tg_id"], other["tg_id"]):
                opposing_army = other
                break
        if target_owner and target_owner["tg_id"] != c["tg_id"]:
            await send_system_message(
                target_owner["tg_id"], target_owner["name"],
                f"لشکری از {origin} با نام «{name}» به قلعه‌ات ({target}) رسید — مراقب باش.",
            )

        owner_is_friendly = bool(target_owner and await players_are_friendly(c["tg_id"], target_owner["tg_id"]))
        creates_battle = (c["op_type"] in DIRECT_ATTACK_OP_TYPES and not owner_is_friendly) or opposing_army is not None
        if creates_battle:
            engagement_id = str(c["_id"])
            battle_defender = target_owner if target_owner and target_owner["tg_id"] != c["tg_id"] else None
            if not battle_defender and opposing_army:
                battle_defender = await players.find_one({"tg_id": opposing_army["tg_id"]})
            defender_armies = [opposing_army] if opposing_army else []
            if battle_defender and not opposing_army:
                defender_armies = [d async for d in campaigns.find({
                    "tg_id": battle_defender["tg_id"], "active": True,
                    "engagement_locked": {"$ne": True},
                    "op_type": {"$in": list(DEFENSE_OP_TYPES)}, "target_castle": target,
                    "arrival_at": {"$lte": now()},
                })]
            engagement_update = {
                "engagement_locked": True, "engagement_campaign_id": engagement_id,
                "battle_location": target, "battle_started_at": now(),
                "battle_open": True,
                "battle_attacker_snapshot": battle_army_snapshot(c),
                "battle_defender_snapshot": [battle_army_snapshot(a) for a in defender_armies],
                "battle_defender_army_ids": [str(a["_id"]) for a in defender_armies],
                "battle_defender_tg_id": battle_defender["tg_id"] if battle_defender else None,
                "battle_defender_name": battle_defender["name"] if battle_defender else "بدون مدافع",
            }
            if opposing_army:
                engagement_update["opponent_campaign_id"] = str(opposing_army["_id"])
                engagement_update["opponent_tg_id"] = opposing_army["tg_id"]
            await campaigns.update_one({"_id": c["_id"]}, {"$set": engagement_update})
            if opposing_army:
                await campaigns.update_one({"_id": opposing_army["_id"]}, {"$set": {
                    "engagement_locked": True, "engagement_campaign_id": engagement_id,
                    "opponent_campaign_id": str(c["_id"]), "opponent_tg_id": c["tg_id"],
                    "battle_location": target,
                }})
            if target_owner and target_owner["tg_id"] != c["tg_id"]:
                await campaigns.update_many({
                    "tg_id": target_owner["tg_id"], "active": True,
                    "engagement_locked": {"$ne": True},
                    "op_type": {"$in": list(DEFENSE_OP_TYPES)}, "target_castle": target,
                    "arrival_at": {"$lte": now()},
                }, {"$set": {"engagement_locked": True, "engagement_campaign_id": engagement_id}})

        if creates_battle and battle_defender:
            attacker_summary = troops_summary(c.get("troops", {}))
            defense_troops = {}
            for army in defender_armies:
                for tid, count in army.get("troops", {}).items():
                    defense_troops[tid] = defense_troops.get(tid, 0) + count
            defender_summary = troops_summary(defense_troops)
            attacker_equipment_summary = "، ".join(f"{SIEGE_EQUIPMENT.get(eid, {}).get('name', eid)}×{count}" for eid, count in c.get("equipment", {}).items() if count) or "بدون ادوات"
            defender_equipment_totals = {}
            for army in defender_armies:
                for eid, count in army.get("equipment", {}).items():
                    defender_equipment_totals[eid] = defender_equipment_totals.get(eid, 0) + int(count or 0)
            defender_equipment_summary = "، ".join(f"{SIEGE_EQUIPMENT.get(eid, {}).get('name', eid)}×{count}" for eid, count in defender_equipment_totals.items() if count) or "بدون ادوات"
            defender_power = opposing_army.get("power", 0) if opposing_army else campaign_power(defense_troops, _building_levels(battle_defender, target))
            attacker_power = c.get("power", 0)
            stats_text = (
                f"آمار نبرد «{name}» در {target}:\n"
                f"مهاجم ({c['player_name']}): {attacker_summary} — توان {attacker_power}\n"
                f"طرف مقابل ({battle_defender['name']}): {defender_summary} — توان {defender_power}\n"
                f"ادوات مهاجم: {attacker_equipment_summary}\nادوات طرف مقابل: {defender_equipment_summary}\n"
                f"هر دو طرف تا {ROLEPLAY_WINDOW_HOURS} ساعت دیگر فرصت دارید سناریوی این نبرد را از صفحهٔ رول‌ها (دستهٔ جنگ) بفرستید — ادمین نتیجه را برای هر دو طرف می‌فرستد."
            )
            await send_system_message(c["tg_id"], c["player_name"], stats_text)
            await send_system_message(battle_defender["tg_id"], battle_defender["name"], stats_text)
            await notify_battle_admins(engagement_id, target, c, battle_defender, defense_troops)

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
        canonical_id = c.get("engagement_campaign_id") or str(c["_id"])
        try:
            root = await campaigns.find_one({"_id": ObjectId(canonical_id)})
        except Exception:
            root = c
        root = root or c
        already = await roleplays.find_one({"tg_id": user["id"], "campaign_id": canonical_id})
        if already:
            return None
        actual_role = "attacker" if root.get("tg_id") == user["id"] else "defender"
        return {
            "campaign_id": canonical_id,
            "name": root.get("name") or OP_TYPES.get(root["op_type"], {}).get("name", root["op_type"]),
            "origin": root["origin_castle"], "target": root.get("battle_location") or root["target_castle"],
            "arrival_at": (root.get("battle_started_at") or root["arrival_at"]).isoformat(),
            "role": actual_role,
        }

    out = []
    seen_engagements = set()
    cur = campaigns.find({"tg_id": user["id"], "engagement_locked": True})
    async for c in cur:
        if (c.get("battle_started_at") or c.get("arrival_at")) < cutoff:
            continue
        row = await build(c, "attacker")
        if row and row["campaign_id"] not in seen_engagements:
            out.append(row)
            seen_engagements.add(row["campaign_id"])

    cur2 = campaigns.find({
        "tg_id": {"$ne": user["id"]}, "engagement_locked": True,
        "$or": [{"target_castle": {"$in": owned_castles(p)}}, {"opponent_tg_id": user["id"]}],
    })
    async for c in cur2:
        if (c.get("battle_started_at") or c.get("arrival_at")) < cutoff:
            continue
        row = await build(c, "defender")
        if row and row["campaign_id"] not in seen_engagements:
            out.append(row)
            seen_engagements.add(row["campaign_id"])

    out.sort(key=lambda r: r["arrival_at"], reverse=True)
    return out

