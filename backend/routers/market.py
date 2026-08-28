import random
from bson import ObjectId
from fastapi import APIRouter, Depends, HTTPException
from pydantic import BaseModel
from auth import get_user
from db import players, market_listings, black_market_listings, player_market_listings
from game import now, can_afford, pay, add_resources, apply_production
from game_data import TRADE_GOOD_NAMES

router = APIRouter(prefix="/api/market", tags=["market"])

@router.get("")
async def list_market(user: dict = Depends(get_user)):
    out = []
    async for m in market_listings.find({"qty": {"$gt": 0}}):
        prev = m.get("prev_price") or m["price"]
        change_pct = round((m["price"] - prev) / prev * 100, 1) if prev else 0.0
        out.append({
            "resource": m["resource"], "name": TRADE_GOOD_NAMES.get(m["resource"], m["resource"]),
            "qty": m["qty"], "price": m["price"], "change_pct": change_pct,
        })
    return out

class BuyBody(BaseModel):
    resource: str
    qty: int

@router.post("/buy")
async def buy(body: BuyBody, user: dict = Depends(get_user)):
    p = await players.find_one({"tg_id": user["id"]})
    if not p:
        raise HTTPException(403, "اول ثبت‌نام کن")
    if body.qty <= 0:
        raise HTTPException(400, "مقدار نامعتبر")
    listing = await market_listings.find_one({"resource": body.resource})
    if not listing or listing["qty"] <= 0:
        raise HTTPException(404, "این کالا در بازار وستروس موجود نیست")
    if body.qty > listing["qty"]:
        raise HTTPException(400, f"فقط {listing['qty']} واحد از این کالا در بازار مانده")

    p = apply_production(p)
    cost = body.qty * listing["price"]
    if not can_afford(p["resources"], {"gold": cost}):
        raise HTTPException(400, "طلای کافی نداری")

    # به‌روزرسانیِ اتمیک و مشروط به موجودیِ واقعی — وگرنه دو خریدِ هم‌زمان می‌تونن
    # هردو رویِ همون خواندنِ قدیمیِ qty رد بشن و بازار رو منفی/بیش‌ازموجودی بفروشن
    bumped = min(listing["price"] * (1 + 0.015 * body.qty), listing.get("base_price", listing["price"]) * 2)
    result = await market_listings.update_one(
        {"_id": listing["_id"], "qty": {"$gte": body.qty}},
        {"$set": {"price": max(1, round(bumped))}, "$inc": {"qty": -body.qty}},
    )
    if result.matched_count == 0:
        raise HTTPException(409, "موجودیِ بازار همین الان تغییر کرد — دوباره امتحان کن")

    pay(p["resources"], {"gold": cost})
    add_resources(p, {body.resource: body.qty})
    await players.update_one({"tg_id": user["id"]}, {"$set": {"resources": p["resources"], "last_tick": p["last_tick"]}})
    return {"ok": True, "resource": body.resource, "qty": body.qty, "cost": cost}

@router.get("/players")
async def list_player_market(user: dict = Depends(get_user)):
    out = []
    async for m in player_market_listings.find({"qty": {"$gt": 0}}).sort("created_at", -1):
        out.append({
            "id": str(m["_id"]), "seller_tg_id": m["seller_tg_id"], "seller_name": m["seller_name"],
            "mine": m["seller_tg_id"] == user["id"], "resource": m["resource"],
            "name": TRADE_GOOD_NAMES.get(m["resource"], m["resource"]), "qty": m["qty"], "price": 1,
        })
    return out

class PlayerListingBody(BaseModel):
    resource: str
    qty: int

@router.post("/players")
async def create_player_listing(body: PlayerListingBody, user: dict = Depends(get_user)):
    if body.resource not in TRADE_GOOD_NAMES or body.resource == "gold":
        raise HTTPException(400, "فقط کالاهای بازار قابل فروش‌اند")
    if body.qty <= 0:
        raise HTTPException(400, "تعداد باید بیشتر از صفر باشد")
    p = await players.find_one({"tg_id": user["id"]})
    if not p:
        raise HTTPException(403, "اول ثبت‌نام کن")
    p = apply_production(p)
    if int(p.get("resources", {}).get(body.resource, 0)) < body.qty:
        raise HTTPException(400, "از این کالا به‌اندازهٔ کافی نداری")
    result = await players.update_one(
        {"tg_id": user["id"], f"resources.{body.resource}": {"$gte": body.qty}},
        {"$inc": {f"resources.{body.resource}": -body.qty}, "$set": {"last_tick": p["last_tick"]}},
    )
    if not result.matched_count:
        raise HTTPException(409, "موجودی‌ات همین الان تغییر کرد؛ دوباره امتحان کن")
    res = await player_market_listings.insert_one({
        "seller_tg_id": user["id"], "seller_name": p["name"], "resource": body.resource,
        "qty": body.qty, "price": 1, "created_at": now(),
    })
    return {"ok": True, "id": str(res.inserted_id), "price": 1}

class PlayerMarketBuyBody(BaseModel):
    listing_id: str
    qty: int

@router.post("/players/buy")
async def buy_player_listing(body: PlayerMarketBuyBody, user: dict = Depends(get_user)):
    try:
        oid = ObjectId(body.listing_id)
    except Exception:
        raise HTTPException(400, "شناسهٔ آگهی نامعتبر است")
    if body.qty <= 0:
        raise HTTPException(400, "تعداد نامعتبر است")
    listing = await player_market_listings.find_one({"_id": oid, "qty": {"$gte": body.qty}})
    if not listing:
        raise HTTPException(404, "آگهی موجود نیست یا موجودی‌اش کافی نیست")
    if listing["seller_tg_id"] == user["id"]:
        raise HTTPException(400, "نمی‌توانی کالای خودت را بخری")
    cost = body.qty  # قانون بازار بازیکن‌ها: هر واحد دقیقاً یک سکه
    buyer = await players.update_one(
        {"tg_id": user["id"], "resources.gold": {"$gte": cost}}, {"$inc": {"resources.gold": -cost}},
    )
    if not buyer.matched_count:
        raise HTTPException(400, "سکهٔ کافی نداری")
    reserved = await player_market_listings.update_one(
        {"_id": oid, "qty": {"$gte": body.qty}}, {"$inc": {"qty": -body.qty}},
    )
    if not reserved.matched_count:
        await players.update_one({"tg_id": user["id"]}, {"$inc": {"resources.gold": cost}})
        raise HTTPException(409, "این کالا همین الان فروخته شد")
    await players.update_one({"tg_id": user["id"]}, {"$inc": {f"resources.{listing['resource']}": body.qty}})
    await players.update_one({"tg_id": listing["seller_tg_id"]}, {"$inc": {"resources.gold": cost}})
    return {"ok": True, "qty": body.qty, "cost": cost, "resource": listing["resource"]}

@router.delete("/players/{listing_id}")
async def cancel_player_listing(listing_id: str, user: dict = Depends(get_user)):
    try:
        oid = ObjectId(listing_id)
    except Exception:
        raise HTTPException(400, "شناسهٔ آگهی نامعتبر است")
    listing = await player_market_listings.find_one({"_id": oid, "seller_tg_id": user["id"]})
    if not listing:
        raise HTTPException(404, "آگهی خودت پیدا نشد")
    result = await player_market_listings.delete_one({"_id": oid, "seller_tg_id": user["id"]})
    if not result.deleted_count:
        raise HTTPException(409, "آگهی همین الان تغییر کرد")
    if listing.get("qty", 0) > 0:
        await players.update_one({"tg_id": user["id"]}, {"$inc": {f"resources.{listing['resource']}": listing["qty"]}})
    return {"ok": True, "refunded": listing.get("qty", 0)}

@router.get("/black")
async def list_black_market(user: dict = Depends(get_user)):
    out = []
    async for m in black_market_listings.find({"qty": {"$gt": 0}, "expires_at": {"$gt": now()}}).sort("created_at", -1):
        out.append({
            "id": str(m["_id"]), "resource": m["resource"], "name": TRADE_GOOD_NAMES.get(m["resource"], m["resource"]),
            "qty": m["qty"], "price": m["price"],
            "expires_in_minutes": max(0, int((m["expires_at"] - now()).total_seconds() // 60)),
        })
    return out

class BlackBuyBody(BaseModel):
    listing_id: str
    qty: int

@router.post("/black/buy")
async def buy_black_market(body: BlackBuyBody, user: dict = Depends(get_user)):
    p = await players.find_one({"tg_id": user["id"]})
    if not p:
        raise HTTPException(403, "اول ثبت‌نام کن")
    try:
        oid = ObjectId(body.listing_id)
    except Exception:
        raise HTTPException(400, "شناسهٔ نامعتبر")
    m = await black_market_listings.find_one({"_id": oid})
    if not m or m["qty"] <= 0 or m["expires_at"] <= now():
        raise HTTPException(404, "این کالای بازار سیاه دیگر موجود نیست")
    if body.qty <= 0 or body.qty > m["qty"]:
        raise HTTPException(400, "مقدار نامعتبر یا بیشتر از موجودی")

    p = apply_production(p)
    cost = body.qty * m["price"]
    if not can_afford(p["resources"], {"gold": cost}):
        raise HTTPException(400, "طلای کافی نداری")

    # همون اتمیک‌سازیِ بازارِ وستروس، اینجا هم — تا دو خریدِ هم‌زمان بیشتر از
    # موجودیِ واقعیِ کالای محدود برنداره
    result = await black_market_listings.update_one(
        {"_id": oid, "qty": {"$gte": body.qty}, "expires_at": {"$gt": now()}},
        {"$inc": {"qty": -body.qty}},
    )
    if result.matched_count == 0:
        raise HTTPException(409, "این کالای بازار سیاه همین الان تمام شد — دوباره امتحان کن")

    pay(p["resources"], {"gold": cost})
    add_resources(p, {m["resource"]: body.qty})
    await players.update_one({"tg_id": user["id"]}, {"$set": {"resources": p["resources"], "last_tick": p["last_tick"]}})
    return {"ok": True, "resource": m["resource"], "qty": body.qty, "cost": cost}

async def drift_market_prices():
    """هر تیک، قیمت‌های بازار وستروس را کمی نوسان می‌دهد — با کشش ملایم به‌سمت قیمت پایه"""
    async for m in market_listings.find({}):
        base = m.get("base_price", m["price"])
        price = m["price"]
        revert = (base - price) * 0.1
        noise = price * random.uniform(-0.05, 0.05)
        new_price = max(1, round(price + revert + noise))
        await market_listings.update_one({"_id": m["_id"]}, {"$set": {"prev_price": price, "price": new_price}})
