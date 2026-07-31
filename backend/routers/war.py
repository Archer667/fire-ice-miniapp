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
    _dijkstra_path,
)
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
    via: list[str] | None = None   # مسیرِ انتخابیِ بازیکن (اگر چند گزینهٔ مسیر بود) — از /war/routes

async def all_castle_terrain() -> dict:
    """نگاشتِ اسمِ هر قلعه/شهرِ بازی (استاتیک + آنچه ادمین به نقشه اضافه کرده) به نوع
    زمینش: land | coastal | sea. منبعِ اصلی فیلدِ terrain روی map_castles است — همان‌جا
    که ادمین موقع گذاشتنِ پین از تب نقشه مشخصش می‌کند. برای قلعه‌هایی که هنوز پین
    ندارند، پیش‌فرض روی دیتای استاتیکِ REGIONS است (castles→land, ports→coastal —
    هیچ‌وقت خودکار sea فرض نمی‌شود، چون «راه‌نداشتن به خشکی» باید صریح علامت بخورد)"""
    terrain = {}
    for r in REGIONS.values():
        for c in r["castles"]:
            terrain[c] = "land"
        for c in r["ports"]:
            terrain[c] = "coastal"
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

async def owner_of_castle(castle: str) -> dict | None:
    """صاحبِ یک قلعه — چه قلعهٔ اصلی‌اش باشه چه یکی از قلعه‌های اضافه‌ای که فتح کرده"""
    return await players.find_one({"$or": [
        {"castle": castle}, {f"castle_buildings.{castle}": {"$exists": True}},
    ]})

async def blocked_castles_for(tg_id: int) -> frozenset:
    """قلعه‌های دیگر بازیکن‌هایی که با tg_id پیمانی ندارند — لشکرِ tg_id نمی‌تواند
    از این قلعه‌ها رد شود (فقط برای مقصد نهایی استثنا می‌شود، نه عبور میان‌راه)"""
    allies = await allied_tg_ids(tg_id)
    blocked = set()
    async for other in players.find({"tg_id": {"$ne": tg_id}}, {"tg_id": 1, "castle": 1}):
        if other.get("castle") and other["tg_id"] not in allies:
            blocked.add(other["castle"])
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
    async for pl in players.find({"castle": {"$in": blockers}}, {"castle": 1, "name": 1, "title": 1}):
        owners[pl["castle"]] = pl
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

@router.get("/routes")
async def routes(origin_castle: str, target_castle: str, user: dict = Depends(get_user)):
    """گزینه‌های مسیرِ واقعیِ بین دو قلعه (۱ یا ۲ تا) — قبل از فرستادنِ فرمان، برای
    اینکه بازیکن ببینه از کجاها رد می‌شود و اگه چند مسیر بود انتخاب کند"""
    if origin_castle == target_castle:
        return {"routes": [{"minutes": 0, "path": [origin_castle]}]}
    names, _ports = await all_castle_names_and_ports()
    if origin_castle not in names or target_castle not in names:
        raise HTTPException(400, "قلعهٔ مبدا یا مقصد شناخته‌شده نیست")
    blocked = await blocked_castles_for(user["id"])
    opts = travel_routes(origin_castle, target_castle, blocked)
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
        target_castle = body.target_castle
    else:
        target_castle = body.origin_castle

    terrain = await all_castle_terrain()
    origin_is_port = terrain.get(body.origin_castle, "land") in ("coastal", "sea")
    gold, men, food_per_day, weapons = troop_food_and_gold(
        p["region"], body.troops, _building_levels(p, body.origin_castle), origin_is_port,
    )
    if men <= 0:
        raise HTTPException(400, "هیچ نیرویی گسیل نکرده‌ای")
    if not can_afford(p["resources"], {"gold": gold}):
        raise HTTPException(400, "خزانه کافی نیست")
    if p["resources"].get("men", 0) < men:
        raise HTTPException(400, "نفرات کافی نداری")
    for weapon_key, needed in weapons.items():
        if p["resources"].get(weapon_key, 0) < needed:
            raise HTTPException(400, f"{WEAPON_NAMES[weapon_key]} کافی نداری — کارگاه تسلیحاتش را بساز یا صبر کن بیشتر تولید شود")

    same_castle = target_castle == body.origin_castle
    if not same_castle:
        if terrain.get(body.origin_castle, "land") == "sea":
            capacity = sum(NAVAL_TROOPS[tid]["capacity"] * n for tid, n in body.troops.items() if tid in NAVAL_TROOPS and n and n > 0)
            land_men = sum(n for tid, n in body.troops.items() if tid not in NAVAL_TROOPS and n and n > 0)
            if land_men > capacity:
                raise HTTPException(400, f"این قلعه کاملاً دریایی است و راهی به خشکی ندارد — کشتی‌های این فرمان فقط {capacity} نفر را جابه‌جا می‌کنند، کشتی بیشتری اضافه کن یا نیروی کمتری بفرست")
    blocked = frozenset() if same_castle else await blocked_castles_for(user["id"])
    if same_castle:
        travel, route_path = 0, [body.origin_castle]
    else:
        opts = travel_routes(body.origin_castle, target_castle, blocked)
        if not opts:
            raise HTTPException(400, await blocked_route_message(body.origin_castle, target_castle, blocked))
        chosen = next((r for r in opts if r["path"] == body.via), None) if body.via else None
        chosen = chosen or opts[0]
        travel, route_path = chosen["minutes"], chosen["path"]
    arrival_at = now() + timedelta(minutes=travel)
    power = campaign_power(body.troops, _building_levels(p, body.origin_castle))

    pay(p["resources"], {"gold": gold, **weapons})
    p["resources"]["men"] = p["resources"].get("men", 0) - men

    # خیانت به پیمان عدم‌تجاوز: حمله/غارت/محاصره (نه جای‌گیری، چون آن برای حمله نیست)
    # علیه کسی که چنین پیمانی باهاش داری — غرامت از طلایش کم می‌شود (اگر طلا کم بود
    # از امتیازش)، و خودِ خاطی از همان پیمان اخراج می‌شود (پیمان باطل می‌شود)
    penalty_charged = 0
    if body.op_type in ATTACK_OP_TYPES and not same_castle:
        target_player = await owner_of_castle(target_castle)
        if target_player:
            pact = await has_non_aggression_pact(user["id"], target_player["tg_id"])
            if pact:
                penalty_charged = pact.get("penalty_gold", 0)
                if penalty_charged > 0:
                    gold_paid = min(p["resources"].get("gold", 0), penalty_charged)
                    p["resources"]["gold"] -= gold_paid
                    shortfall = penalty_charged - gold_paid
                    if shortfall > 0:
                        p["points"] = max(0, p.get("points", 0) - shortfall)
                await alliances.update_one({"_id": pact["_id"]}, {"$set": {"status": "broken", "broken_by": user["id"]}})
                await players.update_one({"tg_id": pact["from_id"]}, {"$inc": {"alliance_count": -1}})
                await players.update_one({"tg_id": pact["to_id"]}, {"$inc": {"alliance_count": -1}})
                await send_system_message(
                    target_player["tg_id"], target_player["name"],
                    f"لرد {p['name']} با وجود پیمان عدم‌تجاوز به تو حمله کرد — {penalty_charged:,} سکه غرامت پرداخت و از پیمان اخراج شد.",
                )

    await players.update_one({"tg_id": user["id"]}, {"$set": {"resources": p["resources"], "points": p.get("points", 0)}})

    doc = {
        "tg_id": user["id"], "player_name": p["name"],
        "origin_castle": body.origin_castle,
        "op_type": body.op_type, "target_castle": target_castle,
        "name": body.name.strip()[:60] or op["name"], "troops": body.troops, "power": power,
        "gold_cost": gold, "men_committed": men, "food_per_day": food_per_day,
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
    """لغو لشکر فعال — طلا، نفرات، و تسلیحاتِ مصرف‌شده (بر اساس ترکیب نیروها) کامل
    برمی‌گردد؛ فقط غله‌ای که تا همین الان به‌عنوان آذوقهٔ روزانه مصرف شده برنمی‌گردد"""
    c = await campaigns.find_one({"_id": ObjectId(campaign_id)})
    if not c or c["tg_id"] != user["id"]:
        raise HTTPException(404, "لشکر پیدا نشد")
    if not c.get("active"):
        raise HTTPException(400, "این لشکر دیگر فعال نیست")

    weapons_refund = {}
    for tid, n in c.get("troops", {}).items():
        if not n or n <= 0:
            continue
        weapon_key = TROOP_WEAPON_KEY.get(tid)
        if weapon_key:
            weapons_refund[weapon_key] = weapons_refund.get(weapon_key, 0) + n * WEAPON_PER_SOLDIER

    await campaigns.update_one({"_id": c["_id"]}, {"$set": {"active": False, "status": "cancelled"}})
    p = await players.find_one({"tg_id": user["id"]})
    if p:
        deltas = {"men": c["men_committed"], "gold": c["gold_cost"], **weapons_refund}
        add_resources(p, deltas)
        await players.update_one({"tg_id": user["id"]}, {"$set": {"resources": p["resources"]}})
    return {
        "ok": True, "men_refunded": c["men_committed"], "gold_refunded": c["gold_cost"],
        "weapons_refunded": weapons_refund,
    }

@router.get("/legions")
async def legions(user: dict = Depends(get_user)):
    """همهٔ لشکرهای فعالِ من — از جمله دفاعی/جای‌گیری — برای مدیریت (لغو یا حرکت‌دادن).
    برخلاف /mine که فقط برای گزارش تهاجمی‌ها و با تأخیر/بازهٔ زمانی محدود است، اینجا
    خودِ صاحبِ لشکرهاست که دارد می‌بیند، پس نه چیزی حذف می‌شود نه پنهان"""
    cur = campaigns.find({"tg_id": user["id"], "active": True}).sort("created_at", -1).limit(50)
    out = []
    async for c in cur:
        arrival_at = c.get("arrival_at")
        arrived = (now() >= arrival_at) if arrival_at else True
        troops = [
            {"name": COMMON_TROOPS[t]["name"] if t in COMMON_TROOPS else t, "count": n}
            for t, n in c.get("troops", {}).items() if n and n > 0
        ]
        out.append({
            "id": str(c["_id"]),
            "op_type": c["op_type"], "op_name": OP_TYPES.get(c["op_type"], {}).get("name", c["op_type"]),
            "name": c.get("name") or OP_TYPES.get(c["op_type"], {}).get("name", c["op_type"]),
            "origin": c["origin_castle"], "target": c["target_castle"],
            "troops": troops, "men_committed": c["men_committed"], "power": c.get("power", 0),
            "travel_minutes": c.get("travel_minutes", 0), "route_path": c.get("route_path"),
            "arrived": arrived,
            "can_relaunch": c["op_type"] == "garrison" and arrived,
            "created_at": c["created_at"].isoformat(),
            "arrival_at": arrival_at.isoformat() if arrival_at else None,
        })
    return out

@router.get("/mine")
async def mine(user: dict = Depends(get_user)):
    """گزارش لشکرکشی‌های خودم — عمداً حداقلی: فقط اسم، فرستنده، مبدا/مقصد و زمان رسیدن؛
    نه توان نه ترکیب/تعداد نیرو. لشکر دفاعی (همون‌جایی) اصلاً وارد گزارش‌ها نمی‌شود، و
    لشکری که بیش از REPORT_VISIBLE_HOURS ساعت پیش رسیده دیگر توی این لیست نمی‌آید"""
    cur = campaigns.find({"tg_id": user["id"], "op_type": {"$ne": "defense"}}).sort("created_at", -1).limit(50)
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
        target_owner = await owner_of_castle(target)
        if target_owner and target_owner["tg_id"] != c["tg_id"]:
            await send_system_message(
                target_owner["tg_id"], target_owner["name"],
                f"لشکری از {origin} با نام «{name}» به قلعه‌ات ({target}) رسید — مراقب باش.",
            )

        if c["op_type"] in ATTACK_OP_TYPES and target_owner and target_owner["tg_id"] != c["tg_id"]:
            attacker_summary = troops_summary(c.get("troops", {}))
            defense_troops = await defending_troops(target, target_owner["tg_id"])
            defender_summary = troops_summary(defense_troops)
            defender_power = campaign_power(defense_troops, _building_levels(target_owner, target))
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
