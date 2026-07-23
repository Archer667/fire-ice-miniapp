import random
from datetime import timedelta
from bson import ObjectId
from fastapi import APIRouter, Depends, HTTPException
from pydantic import BaseModel
from auth import get_user, get_admin, get_full_admin
from db import campaigns, players, admin_roles, map_castles, market_listings, black_market_listings, spy_missions, roleplays, items, item_grants, alliances
from game import now, normalize_building_state
from game_data import REGIONS, COMMON_TROOPS, TRADE_GOODS, BUILDINGS, ROLEPLAY_CATEGORIES, ITEM_TYPES, ITEM_DURATIONS, ITEM_RARITY_COLORS, ALLIANCE_TYPES
from config import ADMIN_IDS
from routers.war import OP_TYPES
from routers.ravens import send_system_message

router = APIRouter(prefix="/api/admin", tags=["admin"])

async def admin_user(user: dict = Depends(get_user)):
    """ادمین کامل یا محدود — برای سناریوها"""
    return await get_admin(user)

async def full_admin_user(user: dict = Depends(get_user)):
    """فقط ادمین کامل — برای مدیریت ادمین‌ها"""
    return await get_full_admin(user)

@router.get("/campaigns")
async def list_campaigns(user: dict = Depends(admin_user)):
    """اطلاعات کامل لشکرکشی‌ها برای ادمین — فقط نمایشی، بدون تایید/رد"""
    out = []
    cur = campaigns.find({}).sort("created_at", -1).limit(50)
    async for s in cur:
        troops = [
            {"name": COMMON_TROOPS[tid]["name"] if tid in COMMON_TROOPS else tid, "count": n}
            for tid, n in s["troops"].items() if n and n > 0
        ]
        arrival_at = s.get("arrival_at")
        target_owner = None
        if s["target_castle"] != s["origin_castle"]:
            target_owner = await players.find_one({"castle": s["target_castle"]}, {"tg_id": 1, "name": 1})
        out.append({
            "id": str(s["_id"]), "player": s["player_name"], "tg_id": s["tg_id"],
            "from": s["origin_castle"], "to": s["target_castle"],
            "target_tg_id": target_owner["tg_id"] if target_owner else None,
            "target_player": target_owner["name"] if target_owner else None,
            "op_type": s["op_type"], "op_name": OP_TYPES.get(s["op_type"], {}).get("name", s["op_type"]),
            "name": s.get("name") or OP_TYPES.get(s["op_type"], {}).get("name", s["op_type"]),
            "troops": troops, "power": s.get("power", 0),
            "gold_cost": s["gold_cost"], "men_committed": s["men_committed"], "food_per_day": s["food_per_day"],
            "travel_minutes": s.get("travel_minutes", 0),
            "arrived": (now() >= arrival_at) if arrival_at else True,
            "active": s.get("active", False),
            "created_at": s["created_at"].isoformat(),
        })
    return out

def _building_levels(player: dict) -> dict:
    out = {}
    for bid, raw in player.get("buildings", {}).items():
        lvl = normalize_building_state(raw)["level"]
        if lvl > 0:
            out[bid] = lvl
    return out

@router.get("/espionage")
async def list_spy_pending(user: dict = Depends(admin_user)):
    """سناریوهای جاسوسی که بازیکنان فرستاده‌اند و هنوز امتیازدهی نشده‌اند"""
    out = []
    cur = spy_missions.find({"resolved": False}).sort("created_at", -1).limit(50)
    async for m in cur:
        out.append({
            "id": str(m["_id"]), "player": m["player_name"], "tg_id": m["tg_id"],
            "origin": m["origin_castle"], "target": m["target_castle"],
            "scenario": m["scenario"], "arrived": now() >= m["arrival_at"],
            "created_at": m["created_at"].isoformat(),
        })
    return out

@router.get("/espionage/resolved")
async def list_spy_resolved(user: dict = Depends(admin_user)):
    """سناریوهای جاسوسی‌ای که قبلاً امتیازدهی شده‌اند — برای مرور نتیجه‌ای که ادمین
    خودش قبلاً داده، چون بعد از امتیازدهی از لیست «در انتظار» ناپدید می‌شوند"""
    out = []
    cur = spy_missions.find({"resolved": True}).sort("resolved_at", -1).limit(50)
    async for m in cur:
        out.append({
            "id": str(m["_id"]), "player": m["player_name"], "tg_id": m["tg_id"],
            "target": m["target_castle"], "scenario": m["scenario"],
            "admin_score": m.get("admin_score"), "success": m.get("success"),
            "resolved_at": m["resolved_at"].isoformat() if m.get("resolved_at") else None,
        })
    return out

class SpyScoreBody(BaseModel):
    score: int

@router.post("/espionage/{mission_id}/score")
async def score_spy(mission_id: str, body: SpyScoreBody, user: dict = Depends(admin_user)):
    """ادمین سناریو را می‌خواند و امتیاز جاسوسی (۰ تا ۱۰۰) می‌دهد — همان امتیاز
    مستقیماً شانس موفقیت است؛ نتیجه فوراً برای بازیکن کلاغ می‌شود"""
    if not (0 <= body.score <= 100):
        raise HTTPException(400, "امتیاز باید بین ۰ تا ۱۰۰ باشد")
    try:
        oid = ObjectId(mission_id)
    except Exception:
        raise HTTPException(400, "شناسهٔ ماموریت نامعتبر است")
    m = await spy_missions.find_one({"_id": oid})
    if not m:
        raise HTTPException(404, "این ماموریت پیدا نشد")
    if m.get("resolved"):
        raise HTTPException(400, "این ماموریت قبلاً امتیازدهی شده")

    success = random.random() * 100 < body.score
    spy_player = await players.find_one({"tg_id": m["tg_id"]})
    target = await players.find_one({"tg_id": m["target_tg_id"]})

    report = None
    if success and target:
        levels = _building_levels(target)
        military = [{"name": BUILDINGS[bid]["name"], "level": lvl}
                    for bid, lvl in levels.items() if BUILDINGS.get(bid, {}).get("type") in ("barracks", "armory")]
        defense = [{"name": BUILDINGS[bid]["name"], "level": lvl}
                   for bid, lvl in levels.items() if BUILDINGS.get(bid, {}).get("type") == "defense"]
        camps = []
        async for c in campaigns.find({"tg_id": target["tg_id"], "active": True}):
            camps.append({
                "op_type": c["op_type"], "op_name": OP_TYPES.get(c["op_type"], {}).get("name", c["op_type"]),
                "origin": c["origin_castle"], "target": c["target_castle"],
                "men_committed": c["men_committed"],
                "arrived": now() >= c.get("arrival_at", now()),
            })
        report = {"resources": target["resources"], "military": military, "defense": defense, "campaigns": camps}

    await spy_missions.update_one({"_id": m["_id"]}, {"$set": {
        "admin_score": body.score, "success": success, "report": report,
        "resolved": True, "resolved_at": now(),
    }})

    if spy_player:
        if success:
            await players.update_one({"tg_id": spy_player["tg_id"]}, {"$inc": {"resources.men": m["men_sent"]}})
            await send_system_message(
                spy_player["tg_id"], spy_player["name"],
                f"جاسوس‌های تو با موفقیت به {m['target_castle']} نفوذ کردند و گزارش کاملی به دست آوردند — نتیجه در بخش جاسوسی منتظر توست.",
            )
        else:
            await send_system_message(
                spy_player["tg_id"], spy_player["name"],
                f"جاسوسی تو در {m['target_castle']} شناسایی و دستگیر شد — نفرات اعزامی برنگشتند.",
            )
    if not success and target:
        await send_system_message(
            target["tg_id"], target["name"],
            f"جاسوسی از سوی {m['player_name']} در تلاش برای نفوذ به {m['target_castle']} شناسایی و دستگیر شد.",
        )

    return {"ok": True, "success": success}

@router.get("/roleplay")
async def list_roleplay_pending(user: dict = Depends(admin_user)):
    """رول‌های بازیکنان که هنوز ادمین نتیجه‌شان را ننوشته — برای دستهٔ «جنگ» طرف
    مقابلِ همان نبرد (اگر او هم سناریواش را فرستاده باشد) هم برای مقایسه نشان داده می‌شود"""
    out = []
    cur = roleplays.find({"resolved": False}).sort("created_at", -1).limit(50)
    async for r in cur:
        row = {
            "id": str(r["_id"]), "player": r["player_name"], "tg_id": r["tg_id"], "castle": r["castle"],
            "category": r["category"], "category_name": ROLEPLAY_CATEGORIES.get(r["category"], r["category"]),
            "text": r["text"], "campaign_id": r.get("campaign_id"), "sibling": None,
            "created_at": r["created_at"].isoformat(),
        }
        if r["category"] == "war" and r.get("campaign_id"):
            sib = await roleplays.find_one({"category": "war", "campaign_id": r["campaign_id"], "tg_id": {"$ne": r["tg_id"]}})
            if sib:
                row["sibling"] = {"player": sib["player_name"], "text": sib["text"], "resolved": sib.get("resolved", False)}
        out.append(row)
    return out

class RoleplayResultBody(BaseModel):
    result: str
    visibility: str = "participants"   # "participants" | "all" — چه کسی نتیجه را کلاغ می‌گیرد
    other_lords: list[int] = []        # ادمین دستی مشخص می‌کند این رول بین چه لردهای دیگری هم بوده —
                                        # چون سناریوی یک لرد ممکن است به چند لرد دیگر اشاره کند، نه فقط
                                        # طرف مقابلِ خودکارِ لشکرکشی (که فقط برای دستهٔ «جنگ» پیدا می‌شود)

@router.post("/roleplay/{roleplay_id}/respond")
async def respond_roleplay(roleplay_id: str, body: RoleplayResultBody, user: dict = Depends(admin_user)):
    """برای دستهٔ «جنگ»، نتیجه برای هر دو طرف نبرد فرستاده می‌شود — چه هر دو سناریو
    فرستاده باشند چه فقط یکی؛ طرفی که ننوشته هم از طریق خودِ لشکرکشی پیدا و باخبر می‌شود.
    ادمین می‌تواند دستی هم لردهای دیگری را به‌عنوان «طرف این رول» اضافه کند (other_lords) —
    اسم‌شان در پیام هم نوشته می‌شود تا برای گیرنده روشن باشد این نتیجه بین چه کسانی بوده.
    اگر visibility=all باشد، علاوه بر شرکت‌کننده‌ها، همهٔ بازیکنان بازی هم کلاغ می‌گیرند —
    جایگزین «روایت جنگ» قدیمی برای وقتی نتیجه باید عمومی اعلام شود"""
    result = body.result.strip()
    if len(result) < 3:
        raise HTTPException(400, "متن نتیجه خیلی کوتاه است")
    if body.visibility not in ("participants", "all"):
        raise HTTPException(400, "نوع نمایش نامعتبر")
    try:
        oid = ObjectId(roleplay_id)
    except Exception:
        raise HTTPException(400, "شناسهٔ رول نامعتبر است")
    r = await roleplays.find_one({"_id": oid})
    if not r:
        raise HTTPException(404, "این رول پیدا نشد")
    if r.get("resolved"):
        raise HTTPException(400, "این رول قبلاً پاسخ داده شده")

    ids_to_resolve = [r["_id"]]
    recipient_tg_ids = {r["tg_id"]}

    if r["category"] == "war" and r.get("campaign_id"):
        sibling = await roleplays.find_one({
            "category": "war", "campaign_id": r["campaign_id"],
            "tg_id": {"$ne": r["tg_id"]}, "resolved": False,
        })
        if sibling:
            ids_to_resolve.append(sibling["_id"])
            recipient_tg_ids.add(sibling["tg_id"])
        try:
            campaign = await campaigns.find_one({"_id": ObjectId(r["campaign_id"])})
        except Exception:
            campaign = None
        if campaign:
            recipient_tg_ids.add(campaign["tg_id"])
            defender = await players.find_one({"castle": campaign["target_castle"]})
            if defender:
                recipient_tg_ids.add(defender["tg_id"])

    other_lord_names = []
    for tg_id in body.other_lords:
        lord = await players.find_one({"tg_id": tg_id})
        if lord:
            recipient_tg_ids.add(tg_id)
            other_lord_names.append(lord["name"])

    await roleplays.update_many({"_id": {"$in": ids_to_resolve}}, {"$set": {
        "result": result[:4000], "resolved": True, "resolved_at": now(),
    }})

    if body.visibility == "all":
        recipient_tg_ids = {p["tg_id"] async for p in players.find({}, {"tg_id": 1})}

    cat_name = ROLEPLAY_CATEGORIES.get(r["category"], r["category"])
    prefix = "اعلامیهٔ عمومی" if body.visibility == "all" else f"نتیجهٔ رول «{cat_name}»{'ِ نبرد' if r['category'] == 'war' else ''}"
    parties_line = ""
    if other_lord_names:
        all_names = list(dict.fromkeys([r["player_name"], *other_lord_names]))
        parties_line = f"\nطرف‌های این رول: {' و '.join(all_names)}"
    for tg_id in recipient_tg_ids:
        player = await players.find_one({"tg_id": tg_id})
        if player:
            await send_system_message(player["tg_id"], player["name"], f"{prefix}: {result}{parties_line}")

    return {"ok": True, "sent_to": len(recipient_tg_ids)}

@router.get("/players/pending")
async def list_pending_players(user: dict = Depends(admin_user)):
    """بازیکن‌هایی که فقط اسم‌نویسی کرده‌اند و هنوز خاندان (اقلیم) و قلعه‌شان تعیین نشده"""
    out = []
    cur = players.find({"$or": [{"region": None}, {"castle": None}]}).sort("created_at", 1)
    async for p in cur:
        out.append({
            "tg_id": p["tg_id"], "name": p["name"], "title": p.get("title"),
            "gender": p.get("gender"), "created_at": p["created_at"].isoformat(),
        })
    return out

@router.get("/players/roster")
async def list_roster(user: dict = Depends(admin_user)):
    """همهٔ بازیکن‌های خاندان‌دار — برای مرور، حذف از خاندان یا تخصیص دوباره"""
    out = []
    cur = players.find({"region": {"$ne": None}, "castle": {"$ne": None}}).sort("name", 1)
    async for p in cur:
        out.append({
            "tg_id": p["tg_id"], "name": p["name"], "title": p.get("title"),
            "region": p["region"], "region_name": REGIONS.get(p["region"], {}).get("name", p["region"]),
            "castle": p["castle"], "is_port": p.get("is_port", False),
        })
    return out

class AssignHouseBody(BaseModel):
    region: str
    castle: str

@router.post("/players/{tg_id}/assign")
async def admin_assign_house(tg_id: int, body: AssignHouseBody, user: dict = Depends(admin_user)):
    """خاندان (اقلیم) و قلعهٔ یک بازیکن را دستی تعیین می‌کند — چه تازه‌ثبت‌نامی چه
    بازیکنی که می‌خواهی به خاندان/قلعهٔ دیگری منتقلش کنی"""
    target = await players.find_one({"tg_id": tg_id})
    if not target:
        raise HTTPException(404, "بازیکن پیدا نشد")
    if body.region not in REGIONS:
        raise HTTPException(400, "اقلیم نامعتبر")
    region = REGIONS[body.region]
    if body.castle not in region["castles"] + region["ports"]:
        raise HTTPException(400, "این قلعه در این اقلیم نیست")
    holder = await players.find_one({"castle": body.castle})
    if holder and holder["tg_id"] != tg_id:
        raise HTTPException(409, "این قلعه صاحب دارد — یکی دیگر برگزین")

    was_assigned = bool(target.get("region") and target.get("castle"))
    await players.update_one({"tg_id": tg_id}, {"$set": {
        "region": body.region, "castle": body.castle, "is_port": body.castle in region["ports"],
    }})
    msg = (
        f"خاندانت جابه‌جا شد — حالا به {region['name']} تعلق داری و قلعه‌ات {body.castle} است."
        if was_assigned else
        f"خاندانت مشخص شد — به {region['name']} تعلق داری و قلعه‌ات {body.castle} است. اکنون می‌توانی وارد بازی شوی."
    )
    await send_system_message(tg_id, target["name"], msg)
    return {"ok": True}

@router.post("/players/{tg_id}/unassign")
async def admin_unassign_house(tg_id: int, user: dict = Depends(admin_user)):
    """خاندان و قلعهٔ یک بازیکن را از او می‌گیرد — دوباره «در انتظار تخصیص» می‌شود
    و قلعه‌اش برای بازیکن دیگری آزاد می‌شود؛ منابع/ساختمان‌هایش دست‌نخورده می‌ماند"""
    target = await players.find_one({"tg_id": tg_id})
    if not target:
        raise HTTPException(404, "بازیکن پیدا نشد")
    if not target.get("region") and not target.get("castle"):
        raise HTTPException(400, "این بازیکن اصلاً خاندانی ندارد")
    await players.update_one({"tg_id": tg_id}, {"$set": {"region": None, "castle": None, "is_port": False}})
    await send_system_message(
        tg_id, target["name"],
        "خاندان و قلعه‌ات از تو گرفته شد — منتظر بمان تا ادمین دوباره خاندانی برایت مشخص کند.",
    )
    return {"ok": True}

MAP_KINDS = {"castle", "city", "ruin", "port"}

@router.get("/map/options")
async def map_options(region: str, user: dict = Depends(admin_user)):
    """اسم قلعه/بندرهای این اقلیم که هنوز روی نقشه مکان ندارند — برای پرکردن انتخابگر ادمین"""
    if region not in REGIONS:
        raise HTTPException(400, "اقلیم نامعتبر")
    placed = {m["name"] async for m in map_castles.find({"region": region}, {"name": 1})}
    r = REGIONS[region]
    options = [{"name": c, "kind": "castle"} for c in r["castles"] if c not in placed]
    options += [{"name": c, "kind": "port"} for c in r["ports"] if c not in placed]
    return options

class MapCastleBody(BaseModel):
    region: str
    x: float
    y: float
    name: str | None = None       # انتخاب از دیتای موجودِ بازی
    new_name: str | None = None   # قلعه/شهر کاملاً جدید
    kind: str = "castle"          # نوع آیکن روی نقشه: castle | city | ruin | port

@router.post("/map/castles")
async def add_map_castle(body: MapCastleBody, user: dict = Depends(admin_user)):
    if body.region not in REGIONS:
        raise HTTPException(400, "اقلیم نامعتبر")
    if not (0 <= body.x <= 100 and 0 <= body.y <= 100):
        raise HTTPException(400, "مختصات نامعتبر")
    if body.kind not in MAP_KINDS:
        raise HTTPException(400, "نوع آیکن نامعتبر")

    r = REGIONS[body.region]
    all_names = {name async for doc in map_castles.find({}, {"name": 1}) for name in [doc["name"]]}
    for reg in REGIONS.values():
        all_names |= set(reg["castles"]) | set(reg["ports"])

    if body.new_name and body.new_name.strip():
        name = body.new_name.strip()[:40]
        if name in all_names:
            raise HTTPException(409, "این اسم قبلاً در بازی وجود دارد")
        custom = True
    else:
        name = (body.name or "").strip()
        if name not in r["castles"] + r["ports"]:
            raise HTTPException(400, "این قلعه/بندر در دیتای این اقلیم نیست")
        if await map_castles.find_one({"region": body.region, "name": name}):
            raise HTTPException(409, "این قلعه از قبل روی نقشه گذاشته شده")
        custom = False

    # نوع آیکن (قلعه/شهر/مخروبه/بندر) را ادمین همیشه دستی مشخص می‌کند — چه برای اسم تازه چه موجود
    await map_castles.insert_one({
        "region": body.region, "name": name, "kind": body.kind,
        "x": body.x, "y": body.y, "custom": custom, "created_at": now(),
    })
    return {"ok": True, "name": name}

@router.delete("/map/castles/{name}")
async def delete_map_castle(name: str, user: dict = Depends(admin_user)):
    res = await map_castles.delete_one({"name": name})
    if res.deleted_count == 0:
        raise HTTPException(404, "این نشانه روی نقشه پیدا نشد")
    return {"ok": True}

@router.get("/admins")
async def list_admins(user: dict = Depends(full_admin_user)):
    """همهٔ ادمین‌ها — کامل (از env) و محدود (از دیتابیس)"""
    tg_ids = list(ADMIN_IDS) + [a["tg_id"] async for a in admin_roles.find({})]
    names = {}
    async for p in players.find({"tg_id": {"$in": tg_ids}}, {"tg_id": 1, "name": 1, "castle": 1}):
        names[p["tg_id"]] = {"name": p["name"], "castle": p["castle"]}

    out = [{"tg_id": tid, "role": "full", "source": "env", **names.get(tid, {})} for tid in ADMIN_IDS]
    async for a in admin_roles.find({}):
        out.append({"tg_id": a["tg_id"], "role": a["role"], "source": "db", **names.get(a["tg_id"], {})})
    return out

class AddAdminBody(BaseModel):
    tg_id: int

@router.post("/admins")
async def add_admin(body: AddAdminBody, user: dict = Depends(full_admin_user)):
    if body.tg_id in ADMIN_IDS:
        raise HTTPException(400, "این کاربر از قبل ادمین کامل است")
    if not await players.find_one({"tg_id": body.tg_id}):
        raise HTTPException(404, "این کاربر هنوز ثبت‌نام نکرده")
    await admin_roles.update_one(
        {"tg_id": body.tg_id},
        {"$set": {"tg_id": body.tg_id, "role": "limited", "added_by": user["id"], "created_at": now()}},
        upsert=True,
    )
    return {"ok": True}

@router.delete("/admins/{tg_id}")
async def remove_admin(tg_id: int, user: dict = Depends(full_admin_user)):
    if tg_id in ADMIN_IDS:
        raise HTTPException(400, "ادمین کامل از env مدیریت می‌شود، نه از اینجا")
    res = await admin_roles.delete_one({"tg_id": tg_id})
    if res.deleted_count == 0:
        raise HTTPException(404, "ادمین محدود پیدا نشد")
    return {"ok": True}

@router.get("/market")
async def admin_market_list(user: dict = Depends(full_admin_user)):
    out = []
    async for m in market_listings.find({}):
        out.append({"resource": m["resource"], "qty": m["qty"], "price": m["price"],
                    "base_price": m.get("base_price", m["price"])})
    return out

class MarketListingBody(BaseModel):
    resource: str
    qty: int
    price: int

@router.post("/market")
async def admin_market_set(body: MarketListingBody, user: dict = Depends(full_admin_user)):
    if body.resource not in TRADE_GOODS:
        raise HTTPException(400, "کالای نامعتبر")
    if body.qty < 0 or body.price <= 0:
        raise HTTPException(400, "مقدار یا قیمت نامعتبر")
    await market_listings.update_one(
        {"resource": body.resource},
        {"$set": {"resource": body.resource, "qty": body.qty, "price": body.price,
                   "prev_price": body.price, "base_price": body.price, "updated_at": now()}},
        upsert=True,
    )
    return {"ok": True}

@router.delete("/market/{resource}")
async def admin_market_delete(resource: str, user: dict = Depends(full_admin_user)):
    res = await market_listings.delete_one({"resource": resource})
    if res.deleted_count == 0:
        raise HTTPException(404, "این کالا توی بازار نیست")
    return {"ok": True}

@router.get("/market/black")
async def admin_black_market_list(user: dict = Depends(full_admin_user)):
    out = []
    async for m in black_market_listings.find({}).sort("created_at", -1):
        out.append({
            "id": str(m["_id"]), "resource": m["resource"], "qty": m["qty"], "price": m["price"],
            "expires_in_minutes": max(0, int((m["expires_at"] - now()).total_seconds() // 60)),
        })
    return out

class BlackMarketBody(BaseModel):
    resource: str
    qty: int
    price: int
    hours: int = 6

@router.post("/market/black")
async def admin_black_market_create(body: BlackMarketBody, user: dict = Depends(full_admin_user)):
    if body.resource not in TRADE_GOODS:
        raise HTTPException(400, "کالای نامعتبر")
    if body.qty <= 0 or body.price <= 0 or body.hours <= 0:
        raise HTTPException(400, "مقدار، قیمت یا مدت نامعتبر")
    doc = {
        "resource": body.resource, "qty": body.qty, "price": body.price,
        "expires_at": now() + timedelta(hours=body.hours), "created_at": now(),
    }
    res = await black_market_listings.insert_one(doc)
    return {"ok": True, "id": str(res.inserted_id)}

@router.delete("/market/black/{listing_id}")
async def admin_black_market_delete(listing_id: str, user: dict = Depends(full_admin_user)):
    res = await black_market_listings.delete_one({"_id": ObjectId(listing_id)})
    if res.deleted_count == 0:
        raise HTTPException(404, "این نشانی بازار سیاه پیدا نشد")
    return {"ok": True}

PLAYER_RESOURCE_KEYS = {
    "gold", "wood", "stone", "iron", "food", "wine", "men",
    "weapon_sword", "weapon_spear", "weapon_archer", "weapon_lcav", "weapon_hcav",
}

@router.get("/items")
async def admin_list_items(user: dict = Depends(full_admin_user)):
    """قالب‌های آیتم — همراه با تعداد بارِ داده‌شده به لردها"""
    out = []
    async for tpl in items.find({}).sort("created_at", -1):
        grant_count = await item_grants.count_documents({"item_id": tpl["_id"]})
        out.append({
            "id": str(tpl["_id"]), "name": tpl["name"],
            "type": tpl["type"], "type_name": ITEM_TYPES.get(tpl["type"], tpl["type"]),
            "duration": tpl["duration"], "duration_name": ITEM_DURATIONS.get(tpl["duration"], tpl["duration"]),
            "duration_hours": tpl.get("duration_hours"),
            "description": tpl.get("description", ""),
            "grant_count": grant_count,
        })
    return out

class ItemBody(BaseModel):
    name: str
    type: str
    duration: str
    duration_hours: int | None = None
    description: str = ""

@router.post("/items")
async def admin_create_item(body: ItemBody, user: dict = Depends(full_admin_user)):
    name = body.name.strip()
    if not name:
        raise HTTPException(400, "نام آیتم را بنویس")
    if body.type not in ITEM_TYPES:
        raise HTTPException(400, "نوع آیتم نامعتبر")
    if body.duration not in ITEM_DURATIONS:
        raise HTTPException(400, "مدت آیتم نامعتبر")
    duration_hours = None
    if body.duration == "temporary":
        if not body.duration_hours or body.duration_hours <= 0:
            raise HTTPException(400, "برای آیتم موقتی، مدت (ساعت) را مشخص کن")
        duration_hours = body.duration_hours

    doc = {
        "name": name[:60], "type": body.type, "duration": body.duration,
        "duration_hours": duration_hours, "description": body.description.strip()[:300],
        "created_by": user["id"], "created_at": now(),
    }
    res = await items.insert_one(doc)
    return {"ok": True, "id": str(res.inserted_id)}

@router.delete("/items/{item_id}")
async def admin_delete_item(item_id: str, user: dict = Depends(full_admin_user)):
    try:
        oid = ObjectId(item_id)
    except Exception:
        raise HTTPException(400, "شناسهٔ آیتم نامعتبر است")
    res = await items.delete_one({"_id": oid})
    if res.deleted_count == 0:
        raise HTTPException(404, "این آیتم پیدا نشد")
    await item_grants.delete_many({"item_id": oid})
    return {"ok": True}

class ItemGrantBody(BaseModel):
    tg_id: int
    color: str

@router.post("/items/{item_id}/grant")
async def admin_grant_item(item_id: str, body: ItemGrantBody, user: dict = Depends(full_admin_user)):
    try:
        oid = ObjectId(item_id)
    except Exception:
        raise HTTPException(400, "شناسهٔ آیتم نامعتبر است")
    tpl = await items.find_one({"_id": oid})
    if not tpl:
        raise HTTPException(404, "این آیتم پیدا نشد")
    if body.color not in ITEM_RARITY_COLORS:
        raise HTTPException(400, "رنگ نامعتبر")
    target = await players.find_one({"tg_id": body.tg_id})
    if not target:
        raise HTTPException(404, "این لرد پیدا نشد")

    expires_at = now() + timedelta(hours=tpl["duration_hours"]) if tpl["duration"] == "temporary" else None
    await item_grants.insert_one({
        "item_id": oid, "tg_id": body.tg_id, "color": body.color,
        "granted_by": user["id"], "granted_at": now(), "expires_at": expires_at,
    })
    await send_system_message(
        target["tg_id"], target["name"],
        f"آیتم «{tpl['name']}» ({ITEM_RARITY_COLORS[body.color]}) به دارایی‌های تو اضافه شد — در صفحهٔ «دارایی‌ها» ببینش.",
    )
    return {"ok": True}

@router.get("/players/{tg_id}/resources")
async def admin_get_player_resources(tg_id: int, user: dict = Depends(full_admin_user)):
    p = await players.find_one({"tg_id": tg_id})
    if not p:
        raise HTTPException(404, "بازیکن پیدا نشد")
    res = {k: p.get("resources", {}).get(k, 0) for k in PLAYER_RESOURCE_KEYS}
    return {"name": p["name"], "castle": p["castle"], "resources": res}

class SetPlayerResourcesBody(BaseModel):
    resources: dict

@router.post("/players/{tg_id}/resources")
async def admin_set_player_resources(tg_id: int, body: SetPlayerResourcesBody, user: dict = Depends(full_admin_user)):
    p = await players.find_one({"tg_id": tg_id})
    if not p:
        raise HTTPException(404, "بازیکن پیدا نشد")
    updates = {}
    for k, v in body.resources.items():
        if k not in PLAYER_RESOURCE_KEYS:
            raise HTTPException(400, f"منبع نامعتبر: {k}")
        v = int(v)
        if v < 0:
            raise HTTPException(400, "مقدار منفی مجاز نیست")
        updates[f"resources.{k}"] = v
    if not updates:
        raise HTTPException(400, "هیچ منبعی برای تغییر مشخص نشده")
    await players.update_one({"tg_id": tg_id}, {"$set": updates})
    return {"ok": True}

@router.get("/players/{tg_id}/campaigns")
async def admin_player_campaigns(tg_id: int, user: dict = Depends(full_admin_user)):
    """لشکرکشی‌های یک بازیکن خاص — برای دیدن و در صورت نیاز منحل‌کردن، کنار ویرایش منابع"""
    p = await players.find_one({"tg_id": tg_id})
    if not p:
        raise HTTPException(404, "بازیکن پیدا نشد")
    out = []
    cur = campaigns.find({"tg_id": tg_id}).sort("created_at", -1).limit(30)
    async for c in cur:
        troops = [
            {"name": COMMON_TROOPS[t]["name"] if t in COMMON_TROOPS else t, "count": n}
            for t, n in c["troops"].items() if n and n > 0
        ]
        arrival_at = c.get("arrival_at")
        out.append({
            "id": str(c["_id"]),
            "name": c.get("name") or OP_TYPES.get(c["op_type"], {}).get("name", c["op_type"]),
            "op_name": OP_TYPES.get(c["op_type"], {}).get("name", c["op_type"]),
            "from": c["origin_castle"], "to": c["target_castle"],
            "troops": troops, "power": c.get("power", 0), "men_committed": c["men_committed"],
            "active": c.get("active", False),
            "arrived": (now() >= arrival_at) if arrival_at else True,
        })
    return out

@router.post("/campaigns/{campaign_id}/disband")
async def admin_disband_campaign(campaign_id: str, user: dict = Depends(full_admin_user)):
    """ادمین هر لشکرکشیِ فعالی را (از هر بازیکنی) منحل می‌کند — نفراتش به صاحبش برمی‌گردد"""
    try:
        oid = ObjectId(campaign_id)
    except Exception:
        raise HTTPException(400, "شناسهٔ لشکرکشی نامعتبر است")
    c = await campaigns.find_one({"_id": oid})
    if not c:
        raise HTTPException(404, "این لشکرکشی پیدا نشد")
    if not c.get("active"):
        raise HTTPException(400, "این لشکرکشی دیگر فعال نیست")
    await campaigns.update_one({"_id": oid}, {"$set": {"active": False, "status": "disbanded"}})
    await players.update_one({"tg_id": c["tg_id"]}, {"$inc": {"resources.men": c["men_committed"]}})
    owner = await players.find_one({"tg_id": c["tg_id"]})
    if owner:
        await send_system_message(
            owner["tg_id"], owner["name"],
            f"لشکر «{c.get('name') or OP_TYPES.get(c['op_type'], {}).get('name', c['op_type'])}» به فرمان ادمین منحل شد و نفراتش به خانه برگشتند.",
        )
    return {"ok": True}

@router.get("/alliances")
async def admin_list_alliances(user: dict = Depends(admin_user)):
    """همهٔ پیمان‌ها — از جمله خصوصی و رد/در انتظار — برای مرور و در صورت نیاز انحلال"""
    out = []
    cur = alliances.find({}).sort("created_at", -1).limit(100)
    async for a in cur:
        out.append({
            "id": str(a["_id"]), "from": a["from_name"], "from_tg_id": a["from_id"],
            "to": a["to_name"], "to_tg_id": a["to_id"],
            "type": a["type"], "type_name": ALLIANCE_TYPES.get(a["type"], {}).get("name", a["type"]),
            "name": a.get("name") or "", "status": a["status"], "public": a.get("public", True),
            "created_at": a["created_at"].isoformat(),
        })
    return out

@router.post("/alliances/{alliance_id}/dissolve")
async def admin_dissolve_alliance(alliance_id: str, user: dict = Depends(full_admin_user)):
    """ادمین یک پیمانِ برقرار را زورکی منحل می‌کند — شمار اتحاد هر دو طرف کم می‌شود و هر دو باخبر می‌شوند"""
    try:
        oid = ObjectId(alliance_id)
    except Exception:
        raise HTTPException(400, "شناسهٔ پیمان نامعتبر است")
    a = await alliances.find_one({"_id": oid})
    if not a:
        raise HTTPException(404, "این پیمان پیدا نشد")
    if a["status"] != "accepted":
        raise HTTPException(400, "فقط پیمان برقرار را می‌شود منحل کرد")

    await alliances.update_one({"_id": oid}, {"$set": {"status": "dissolved"}})
    await players.update_one({"tg_id": a["from_id"]}, {"$inc": {"alliance_count": -1}})
    await players.update_one({"tg_id": a["to_id"]}, {"$inc": {"alliance_count": -1}})
    for tg_id, name, other_name in [(a["from_id"], a["from_name"], a["to_name"]), (a["to_id"], a["to_name"], a["from_name"])]:
        await send_system_message(tg_id, name, f"پیمانت با لرد {other_name} به فرمان ادمین منحل شد.")
    return {"ok": True}
