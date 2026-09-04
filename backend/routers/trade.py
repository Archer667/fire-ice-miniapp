from datetime import timedelta
from fastapi import APIRouter, Depends, HTTPException
from pydantic import BaseModel
from auth import get_user
from db import players, caravans, alliances
from game import now, can_afford, pay, add_resources, owned_castles, apply_production, production_fields
from game_data import CARAVAN_GOODS, TRADE_GOOD_NAMES, travel_routes
from routers.ravens import send_system_message
from routers.war import all_castle_terrain
from control_settings import feature_enabled

router = APIRouter(prefix="/api/trade", tags=["trade"])

async def has_trade_alliance(a_id: int, b_id: int) -> bool:
    """اتحاد تجاری یا اتحاد کامل، پذیرفته‌شده، بین این دو بازیکن"""
    doc = await alliances.find_one({
        "status": "accepted", "type": {"$in": ["trade", "full_alliance"]},
        "$or": [{"from_id": a_id, "to_id": b_id}, {"from_id": b_id, "to_id": a_id}],
    })
    return doc is not None

class CaravanBody(BaseModel):
    target_tg_id: int
    resources: dict  # {resource: qty}
    origin_castle: str | None = None   # پیش‌فرض: قلعهٔ خانگی‌ات — می‌تونه هرکدوم از قلعه‌های خودت باشه
    target_castle: str | None = None   # پیش‌فرض: قلعهٔ خانگیِ گیرنده — می‌تونه هرکدوم از قلعه‌های او باشه
    via: list[str] | None = None       # مسیر انتخابی از /caravan/routes

async def caravan_route_options(sender_id: int, origin_castle: str, target_castle: str) -> list[dict]:
    """سه مسیر پیشنهادی و لردهای فاقد مجوز عبور تجاری در هر مسیر.

    عدم‌تجاوز مجوز کاروان نیست؛ فقط پیمان تجاری یا اتحاد کامل پذیرفته‌شده حساب می‌شود.
    """
    if origin_castle == target_castle:
        return [{"minutes": 0, "path": [origin_castle], "via_sea": False,
                 "available": True, "missing_lords": []}]
    terrain = await all_castle_terrain()
    raw_routes = travel_routes(origin_castle, target_castle, frozenset(), max_routes=3, terrain=terrain)
    owners_by_castle = {}
    async for owner in players.find({"tg_id": {"$ne": sender_id}}, {"tg_id": 1, "name": 1, "castle": 1, "castle_buildings": 1}):
        for castle in owned_castles(owner):
            owners_by_castle[castle] = owner
    permitted_ids = set()
    async for pact in alliances.find({
        "status": "accepted", "type": {"$in": ["trade", "full_alliance"]},
        "$or": [{"from_id": sender_id}, {"to_id": sender_id}],
    }):
        permitted_ids.add(pact["to_id"] if pact["from_id"] == sender_id else pact["from_id"])
    result = []
    for route in raw_routes:
        missing_by_id = {}
        for castle in route["path"][1:]:
            owner = owners_by_castle.get(castle)
            if owner and owner["tg_id"] not in permitted_ids:
                missing_by_id[owner["tg_id"]] = {"tg_id": owner["tg_id"], "name": owner.get("name", "نامشخص")}
        result.append({**route, "available": not missing_by_id, "missing_lords": list(missing_by_id.values())})
    return result

@router.get("/caravan/routes")
async def caravan_routes(origin_castle: str, target_castle: str, user: dict = Depends(get_user)):
    p = await players.find_one({"tg_id": user["id"]})
    if not p or origin_castle not in owned_castles(p):
        raise HTTPException(400, "قلعهٔ مبدا مال تو نیست")
    return {"routes": await caravan_route_options(user["id"], origin_castle, target_castle)}

@router.post("/caravan")
async def send_caravan(body: CaravanBody, user: dict = Depends(get_user)):
    if not feature_enabled("caravans"):
        raise HTTPException(503, "ارسال کاروان فعلاً غیرفعال است")
    p = await players.find_one({"tg_id": user["id"]})
    if not p:
        raise HTTPException(403, "اول ثبت‌نام کن")
    if body.target_tg_id == user["id"]:
        raise HTTPException(400, "نمی‌تونی برای خودت کاروان بفرستی")
    target = await players.find_one({"tg_id": body.target_tg_id})
    if not target:
        raise HTTPException(404, "گیرنده پیدا نشد")
    if not await has_trade_alliance(user["id"], body.target_tg_id):
        raise HTTPException(403, "فقط با هم‌پیمان‌های تجاری (پیمان تجاری یا اتحاد کامل) می‌تونی کاروان رد و بدل کنی")

    # تولیدِ فاصلهٔ زمانیِ سپری‌شده رو قبل از چک‌کردنِ موجودی حساب می‌کنیم — وگرنه بازیکنی
    # که مدتی سر نزده، با موجودیِ قدیمی (کمتر از واقعی) رد می‌شه
    p = apply_production(p)
    origin_castle = body.origin_castle or p["castle"]
    if origin_castle not in owned_castles(p):
        raise HTTPException(400, "این قلعه مالِ تو نیست")
    target_castle = body.target_castle or target["castle"]
    if target_castle not in owned_castles(target):
        raise HTTPException(400, "این قلعه مالِ گیرنده نیست")

    cost = {}
    for good, qty in body.resources.items():
        if good not in CARAVAN_GOODS:
            raise HTTPException(400, f"کالای نامعتبر: {good}")
        qty = int(qty)
        if qty > 0:
            cost[good] = qty
    if not cost:
        raise HTTPException(400, "هیچ کالایی برای فرستادن انتخاب نکردی")
    if not can_afford(p["resources"], cost):
        raise HTTPException(400, "این مقدار کالا رو نداری")

    route_options = await caravan_route_options(user["id"], origin_castle, target_castle)
    chosen = next((r for r in route_options if body.via and r["path"] == body.via), None)
    if body.via and not chosen:
        raise HTTPException(400, "مسیر انتخاب‌شده دیگر معتبر نیست؛ مسیرها را دوباره دریافت کن")
    chosen = chosen or next((r for r in route_options if r["available"]), None)
    if not chosen or not chosen["available"]:
        missing = (chosen or (route_options[0] if route_options else {})).get("missing_lords", [])
        names = "، ".join(row["name"] for row in missing)
        detail = f"؛ با این لردها پیمان تجاری یا اتحاد کامل نداری: {names}" if names else ""
        raise HTTPException(400, f"هیچ مسیر تجاری مجازی تا مقصد وجود ندارد{detail}")
    travel = chosen["minutes"]

    pay(p["resources"], cost)
    await players.update_one({"tg_id": user["id"]}, {"$set": production_fields(p)})

    arrival_at = now() + timedelta(minutes=travel)

    doc = {
        "tg_id": user["id"], "player_name": p["name"], "origin_castle": origin_castle,
        "target_tg_id": target["tg_id"], "target_name": target["name"], "target_castle": target_castle,
        "resources": cost, "travel_minutes": travel, "route_path": chosen["path"], "arrival_at": arrival_at,
        "active": True, "arrival_notified": False, "created_at": now(),
    }
    res = await caravans.insert_one(doc)
    return {"ok": True, "id": str(res.inserted_id), "travel_minutes": travel,
            "route_path": chosen["path"], "arrival_at": arrival_at.isoformat()}

@router.get("/caravans/mine")
async def my_caravans(user: dict = Depends(get_user)):
    cur = caravans.find({"$or": [{"tg_id": user["id"]}, {"target_tg_id": user["id"]}]}).sort("created_at", -1).limit(30)
    out = []
    async for c in cur:
        arrival_at = c.get("arrival_at")
        out.append({
            "id": str(c["_id"]), "mine_sent": c["tg_id"] == user["id"],
            "from": c["player_name"], "to": c["target_name"],
            "from_castle": c["origin_castle"], "to_castle": c["target_castle"],
            "resources": {TRADE_GOOD_NAMES.get(k, k): v for k, v in c["resources"].items()},
            "travel_minutes": c.get("travel_minutes", 0),
            "arrived": (now() >= arrival_at) if arrival_at else True,
            "created_at": c["created_at"].isoformat(),
        })
    return out

async def notify_caravan_arrivals():
    """کاروانی که می‌رسد کالایش را به گیرنده تحویل می‌دهد و به هر دو طرف کلاغ می‌فرستد"""
    cur = caravans.find({"active": True, "arrival_notified": {"$ne": True}, "arrival_at": {"$lte": now()}})
    async for c in cur:
        target = await players.find_one({"tg_id": c["target_tg_id"]})
        if target:
            add_resources(target, c["resources"])
            await players.update_one({"tg_id": c["target_tg_id"]}, {"$set": {"resources": target["resources"]}})
        goods_text = " · ".join(f"{v} {TRADE_GOOD_NAMES.get(k, k)}" for k, v in c["resources"].items())
        await send_system_message(
            c["tg_id"], c["player_name"],
            f"کاروانت به {c['target_name']} ({c['target_castle']}) رسید و تحویل داده شد: {goods_text}",
            kind="trade",
        )
        await send_system_message(
            c["target_tg_id"], c["target_name"],
            f"کاروانی از {c['player_name']} ({c['origin_castle']}) رسید: {goods_text}",
            kind="trade",
        )
        await caravans.update_one({"_id": c["_id"]}, {"$set": {"arrival_notified": True, "active": False}})
