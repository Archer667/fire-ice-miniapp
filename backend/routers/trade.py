from datetime import timedelta
from fastapi import APIRouter, Depends, HTTPException
from pydantic import BaseModel
from auth import get_user
from db import players, caravans, alliances
from game import now, can_afford, pay, add_resources, owned_castles, apply_production
from game_data import TRADE_GOODS, TRADE_GOOD_NAMES, travel_minutes
from routers.ravens import send_system_message
from routers.war import blocked_castles_for

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

@router.post("/caravan")
async def send_caravan(body: CaravanBody, user: dict = Depends(get_user)):
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
        if good not in TRADE_GOODS:
            raise HTTPException(400, f"کالای نامعتبر: {good}")
        qty = int(qty)
        if qty > 0:
            cost[good] = qty
    if not cost:
        raise HTTPException(400, "هیچ کالایی برای فرستادن انتخاب نکردی")
    if not can_afford(p["resources"], cost):
        raise HTTPException(400, "این مقدار کالا رو نداری")

    same_castle = origin_castle == target_castle
    blocked = frozenset() if same_castle else await blocked_castles_for(user["id"])
    travel = travel_minutes(same_castle, origin_castle, target_castle, blocked)
    if travel is None:
        raise HTTPException(400, "مسیر این کاروان از قلمروِ لردی می‌گذرد که با او پیمان (عدم‌تجاوز یا اتحاد کامل) نداری")

    pay(p["resources"], cost)
    await players.update_one({"tg_id": user["id"]}, {"$set": {"resources": p["resources"], "last_tick": p["last_tick"]}})

    arrival_at = now() + timedelta(minutes=travel)

    doc = {
        "tg_id": user["id"], "player_name": p["name"], "origin_castle": origin_castle,
        "target_tg_id": target["tg_id"], "target_name": target["name"], "target_castle": target_castle,
        "resources": cost, "travel_minutes": travel, "arrival_at": arrival_at,
        "active": True, "arrival_notified": False, "created_at": now(),
    }
    res = await caravans.insert_one(doc)
    return {"ok": True, "id": str(res.inserted_id), "travel_minutes": travel, "arrival_at": arrival_at.isoformat()}

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
        )
        await send_system_message(
            c["target_tg_id"], c["target_name"],
            f"کاروانی از {c['player_name']} ({c['origin_castle']}) رسید: {goods_text}",
        )
        await caravans.update_one({"_id": c["_id"]}, {"$set": {"arrival_notified": True, "active": False}})
