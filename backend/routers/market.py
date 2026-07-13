import random
from bson import ObjectId
from fastapi import APIRouter, Depends, HTTPException
from pydantic import BaseModel
from auth import get_user
from db import players, market_listings, black_market_listings
from game import now, can_afford, pay
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

    cost = body.qty * listing["price"]
    if not can_afford(p["resources"], {"gold": cost}):
        raise HTTPException(400, "طلای کافی نداری")
    pay(p["resources"], {"gold": cost})
    p["resources"][body.resource] = p["resources"].get(body.resource, 0) + body.qty
    await players.update_one({"tg_id": user["id"]}, {"$set": {"resources": p["resources"]}})

    # هر خرید، تقاضا را نشان می‌دهد — قیمت را کمی بالا می‌برد (سقف دو برابر قیمت پایه)
    bumped = min(listing["price"] * (1 + 0.015 * body.qty), listing.get("base_price", listing["price"]) * 2)
    await market_listings.update_one({"_id": listing["_id"]},
        {"$set": {"qty": listing["qty"] - body.qty, "price": max(1, round(bumped))}})
    return {"ok": True, "resource": body.resource, "qty": body.qty, "cost": cost}

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
    m = await black_market_listings.find_one({"_id": ObjectId(body.listing_id)})
    if not m or m["qty"] <= 0 or m["expires_at"] <= now():
        raise HTTPException(404, "این کالای بازار سیاه دیگر موجود نیست")
    if body.qty <= 0 or body.qty > m["qty"]:
        raise HTTPException(400, "مقدار نامعتبر یا بیشتر از موجودی")

    cost = body.qty * m["price"]
    if not can_afford(p["resources"], {"gold": cost}):
        raise HTTPException(400, "طلای کافی نداری")
    pay(p["resources"], {"gold": cost})
    p["resources"][m["resource"]] = p["resources"].get(m["resource"], 0) + body.qty
    await players.update_one({"tg_id": user["id"]}, {"$set": {"resources": p["resources"]}})
    await black_market_listings.update_one({"_id": m["_id"]}, {"$inc": {"qty": -body.qty}})
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
