import random
from datetime import timedelta
from bson import ObjectId
from fastapi import APIRouter, Depends, HTTPException
from pydantic import BaseModel
from auth import get_user, get_admin, get_full_admin
from db import campaigns, players, admin_roles, map_castles, battle_reports, market_listings, black_market_listings, spy_missions, roleplays
from game import now, normalize_building_state
from game_data import REGIONS, COMMON_TROOPS, TRADE_GOODS, BUILDINGS, ROLEPLAY_CATEGORIES
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
            "plan": s["plan"], "troops": troops,
            "gold_cost": s["gold_cost"], "men_committed": s["men_committed"], "food_per_day": s["food_per_day"],
            "travel_minutes": s.get("travel_minutes", 0),
            "arrived": (now() >= arrival_at) if arrival_at else True,
            "active": s.get("active", False),
            "created_at": s["created_at"].isoformat(),
        })
    return out

class BattleReportBody(BaseModel):
    participant_tg_ids: list[int]
    text: str

@router.get("/battles")
async def list_battles(user: dict = Depends(admin_user)):
    out = []
    async for b in battle_reports.find({}).sort("created_at", -1).limit(30):
        out.append({
            "id": str(b["_id"]), "participants": b["participant_names"],
            "text": b["text"], "created_at": b["created_at"].isoformat(),
        })
    return out

@router.post("/battles")
async def create_battle(body: BattleReportBody, user: dict = Depends(admin_user)):
    """روایت نتیجهٔ یک جنگ — برای هر شرکت‌کننده به‌عنوان کلاغی از «شورای جنگ» فرستاده می‌شود"""
    text = body.text.strip()
    if not text:
        raise HTTPException(400, "متن روایت خالی است")
    ids = list(dict.fromkeys(body.participant_tg_ids))
    if not ids:
        raise HTTPException(400, "حداقل یک شرکت‌کننده انتخاب کن")

    targets = await players.find({"tg_id": {"$in": ids}}).to_list(len(ids))
    if not targets:
        raise HTTPException(404, "هیچ‌کدام از شرکت‌کننده‌ها پیدا نشدند")

    for t in targets:
        await send_system_message(t["tg_id"], t["name"], text)

    await battle_reports.insert_one({
        "participant_tg_ids": [t["tg_id"] for t in targets],
        "participant_names": [t["name"] for t in targets],
        "text": text, "created_by": user["id"], "created_at": now(),
    })
    return {"ok": True, "sent_to": len(targets)}

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

@router.post("/roleplay/{roleplay_id}/respond")
async def respond_roleplay(roleplay_id: str, body: RoleplayResultBody, user: dict = Depends(admin_user)):
    """برای دستهٔ «جنگ»، نتیجه برای هر دو طرف نبرد فرستاده می‌شود — چه هر دو سناریو
    فرستاده باشند چه فقط یکی؛ طرفی که ننوشته هم از طریق خودِ لشکرکشی پیدا و باخبر می‌شود"""
    result = body.result.strip()
    if len(result) < 3:
        raise HTTPException(400, "متن نتیجه خیلی کوتاه است")
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

    await roleplays.update_many({"_id": {"$in": ids_to_resolve}}, {"$set": {
        "result": result[:4000], "resolved": True, "resolved_at": now(),
    }})

    cat_name = ROLEPLAY_CATEGORIES.get(r["category"], r["category"])
    for tg_id in recipient_tg_ids:
        player = await players.find_one({"tg_id": tg_id})
        if player:
            await send_system_message(
                player["tg_id"], player["name"],
                f"نتیجهٔ رول «{cat_name}»{'ِ نبرد ' if r['category'] == 'war' else ''} آمد: {result}",
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

PLAYER_RESOURCE_KEYS = {"gold", "wood", "stone", "iron", "food", "wine", "men"}

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
