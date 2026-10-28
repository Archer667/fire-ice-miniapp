from datetime import timedelta, datetime, timezone
from uuid import uuid4

from bson import ObjectId
from fastapi import APIRouter, Depends, HTTPException
from pydantic import BaseModel, Field, StrictInt

from auth import get_full_admin, get_user
from db import db, players
from family import commit
from game import now
from game_data import TRADE_GOOD_NAMES
from project_engine import member_for, receipt_key
from realm_state import adjust_influence, adjust_reputation, record_event
from routers.ravens import send_system_message
from realm_controls import rules as realm_rules, DEFAULTS
from market_rules import check_price, price_limits


router = APIRouter(prefix="/api/economy", tags=["economy"])
orders = db.market_buy_orders
contracts = db.supply_contracts


async def trade_rules():
    cfg = {**DEFAULTS, **await realm_rules()}
    if not cfg['trade_network_enabled']:
        raise HTTPException(409, 'ثبت و اجرای معاملهٔ تازه فعلاً متوقف است؛ لغو و بازپرداخت باز است')
    return cfg


@router.get('/meta')
async def trade_meta(user=Depends(get_user)):
    cfg = {**DEFAULTS, **await realm_rules()}
    return {'rules': cfg, **await price_limits()}


def _oid(value):
    if not ObjectId.is_valid(value):
        raise HTTPException(404, "پرونده پیدا نشد")
    return ObjectId(value)


def _resource(value):
    if value == "gold" or value not in TRADE_GOOD_NAMES:
        raise HTTPException(400, "کالای انتخاب‌شده قابل معامله نیست")
    return value


async def _active(uid):
    player = await players.find_one({"tg_id": uid})
    from character_access import status as character_status
    if character_status(player) not in ("landed", "landless"):
        raise HTTPException(403, "کاراکتر فعال پیدا نشد")
    return player


async def full_admin(user=Depends(get_user)):
    return await get_full_admin(user)


def _stat_change(uid, event, increments):
    field = "economy_stat_receipts." + receipt_key(event)
    return {
        "collection": "players", "query": {"tg_id": uid, field: {"$ne": True}},
        "update": {"$set": {field: True}, "$inc": {f"stats.{key}": value for key, value in increments.items()}},
    }


def _event_change(identity, kind, title, actor, targets, detail, data=None, public=False):
    return {"collection": "game_events", "query": {"_id": identity}, "update": {"$setOnInsert": {
        "_id": identity, "kind": kind, "title": title, "actor_id": actor,
        "target_ids": targets, "detail": detail, "data": data or {},
        "visibility": "public" if public else "participants", "game_at": now(), "real_at": datetime.now(timezone.utc),
    }}, "upsert": True}


def _order(row, uid):
    return {
        "id": str(row["_id"]), "buyer_id": row["buyer_id"], "buyer_name": row["buyer_name"],
        "mine": row["buyer_id"] == uid, "resource": row["resource"],
        "resource_name": TRADE_GOOD_NAMES.get(row["resource"], row["resource"]),
        "qty": row["qty"], "remaining": row["remaining"], "unit_price": row["unit_price"],
        "escrow_remaining": row.get("escrow_remaining", 0),
        "status": row["status"], "created_at": row["created_at"].isoformat(),
    }


@router.get("/orders")
async def list_orders(user=Depends(get_user)):
    return [_order(row, user["id"]) async for row in orders.find({"status": "open", "remaining": {"$gt": 0}}).sort("created_at", -1).limit(150)]


class OrderBody(BaseModel):
    resource: str
    qty: StrictInt = Field(ge=1, le=1_000_000_000)
    unit_price: StrictInt = Field(ge=1, le=1_000_000_000)


@router.post("/orders")
async def create_order(body: OrderBody, user=Depends(get_user)):
    resource = _resource(body.resource)
    buyer = await _active(user["id"])
    cfg = await trade_rules()
    await check_price(resource, body.unit_price)
    if body.qty > cfg['max_order_quantity'] or await orders.count_documents({'buyer_id': user['id'], 'status': 'open'}) >= cfg['max_open_orders']:
        raise HTTPException(400, 'تعداد کالا یا سفارش‌های باز بیشتر از سقف مجاز است')
    total = body.qty * body.unit_price
    if total > cfg['max_trade_value']:
        raise HTTPException(400, "ارزش سفارش بیشتر از سقف مجاز است")
    identity = ObjectId()
    doc = {
        "_id": identity, "buyer_id": user["id"], "buyer_name": buyer.get("name", "بازیکن"),
        "buyer_character": buyer.get("created_at"), "resource": resource, "qty": body.qty,
        "remaining": body.qty, "unit_price": body.unit_price, "escrow_remaining": total,
        "status": "open", "created_at": now(),
    }
    await commit({
        "_id": str(uuid4()), "kind": "market_buy_order_create", "complete": False,
        "wallets": [{"member": member_for(buyer, 0), "cost": {"gold": total}, "debit": True}],
        "changes": [{"collection": "market_buy_orders", "query": {"_id": identity}, "update": {"$setOnInsert": doc}, "upsert": True}],
    })
    return _order(doc, user["id"])


class FillBody(BaseModel):
    qty: StrictInt = Field(ge=1, le=1_000_000_000)


@router.post("/orders/{order_id}/fill")
async def fill_order(order_id: str, body: FillBody, user=Depends(get_user)):
    row = await orders.find_one({"_id": _oid(order_id)})
    if not row or row["status"] != "open" or row["remaining"] < body.qty:
        raise HTTPException(409, "سفارش باز نیست یا مقدار باقی‌مانده کافی نیست")
    if row["buyer_id"] == user["id"]:
        raise HTTPException(400, "نمی‌توانی سفارش خرید خودت را تأمین کنی")
    seller = await _active(user["id"])
    buyer = await _active(row["buyer_id"])
    if buyer.get("created_at") != row.get("buyer_character"):
        raise HTTPException(409, "شخصیت سفارش‌دهنده تغییر کرده است؛ سفارش باید بسته شود")
    cfg = await trade_rules()
    await check_price(row['resource'], row['unit_price'])
    gross = body.qty * row["unit_price"]
    cross_region = bool(seller.get("region") and buyer.get("region") and seller.get("region") != buyer.get("region"))
    fee_percent = int(cfg["market_fee_percent"]) + (int(cfg["cross_region_tariff_percent"]) if cross_region else 0)
    fee = gross * fee_percent // 100
    payout = gross - fee
    remaining = row["remaining"] - body.qty
    event = f"buy-order:{order_id}:{row['remaining']}:{body.qty}"
    receipt = "receipts." + receipt_key(event)
    await db.realm_treasury.update_one({"_id": "trade"}, {"$setOnInsert": {"gold": 0, "receipts": {}}}, upsert=True)
    treasury_change = {
        "collection": "realm_treasury", "query": {"_id": "trade", receipt: {"$ne": True}},
        "update": {"$set": {receipt: True}, "$inc": {"gold": fee}},
    }
    await commit({
        "_id": str(uuid4()), "kind": "market_buy_order_fill", "complete": False,
        "wallets": [
            {"member": member_for(seller, 0), "cost": {row["resource"]: body.qty}, "debit": True},
            {"member": member_for(buyer, 0), "cost": {row["resource"]: body.qty}},
            {"member": member_for(seller, 0), "cost": {"gold": payout}},
        ],
        "changes": [
            {"collection": "market_buy_orders", "query": {"_id": row["_id"]}, "update": {"$set": {
                "remaining": remaining, "escrow_remaining": remaining * row["unit_price"],
                "status": "filled" if not remaining else "open", "updated_at": now(),
            }}},
            treasury_change,
            _stat_change(user["id"], event + ":seller", {"market_sold_value": gross}),
            _stat_change(row["buyer_id"], event + ":buyer", {"market_bought_value": gross}),
            _event_change(event, "market_order", "تأمین سفارش خرید", user["id"], [row["buyer_id"]], f"{body.qty:,} {TRADE_GOOD_NAMES[row['resource']]} با ارزش {gross:,} سکه", {"fee": fee, "gross": gross, "payout": payout, "qty": body.qty, "unit_price": row["unit_price"], "resource": row["resource"]}),
        ],
    })
    await adjust_reputation(row["buyer_id"], user["id"], 1, "تأمین سفارش خرید", source_id=event)
    await adjust_influence(user["id"], max(1, gross // cfg['reward_trade_step']), "تجارت موفق", source_id=event)
    return {"ok": True, "gross": gross, "fee": fee, "payout": payout, "remaining": remaining}


@router.delete("/orders/{order_id}")
async def cancel_order(order_id: str, user=Depends(get_user)):
    row = await orders.find_one({"_id": _oid(order_id), "buyer_id": user["id"]})
    if not row or row["status"] != "open":
        raise HTTPException(409, "سفارش باز خودت پیدا نشد")
    return await _cancel_order(row)


async def _cancel_order(row):
    buyer = await players.find_one({'tg_id': row['buyer_id']}) or {}
    buyer_member = {
        "tg_id": row["buyer_id"], "name": row.get("buyer_name", buyer.get("name", "بازیکن")),
        "character_created_at": row.get("buyer_character", buyer.get("created_at")), "shares": 0,
    }
    refund = int(row.get("escrow_remaining", row["remaining"] * row["unit_price"]))
    await commit({
        "_id": str(uuid4()), "kind": "market_buy_order_cancel", "complete": False,
        "wallets": [{"member": buyer_member, "cost": {"gold": refund}}],
        "changes": [{"collection": "market_buy_orders", "query": {"_id": row["_id"]}, "update": {"$set": {"status": "cancelled", "remaining": 0, "escrow_remaining": 0, "closed_at": now()}}}],
    })
    return {"ok": True, "refunded": refund}


def _contract(row, uid):
    return {
        "id": str(row["_id"]), "buyer_id": row["buyer_id"], "buyer_name": row["buyer_name"],
        "seller_id": row["seller_id"], "seller_name": row["seller_name"],
        "mine_as": "buyer" if row["buyer_id"] == uid else "seller",
        "resource": row["resource"], "resource_name": TRADE_GOOD_NAMES.get(row["resource"], row["resource"]),
        "qty_per_delivery": row["qty_per_delivery"], "unit_price": row["unit_price"],
        "deliveries": row["deliveries"], "delivered": row.get("delivered", 0),
        "escrow_remaining": row.get("escrow_remaining", 0),
        "interval_hours": row["interval_hours"], "status": row["status"],
        "next_due": row.get("next_due").isoformat() if row.get("next_due") else None,
        "created_at": row["created_at"].isoformat(), "note": row.get("note", ""),
    }


@router.get("/contracts")
async def list_contracts(user=Depends(get_user)):
    query = {"$or": [{"buyer_id": user["id"]}, {"seller_id": user["id"]}]}
    return [_contract(row, user["id"]) async for row in contracts.find(query).sort("created_at", -1).limit(100)]


class ContractBody(BaseModel):
    seller_id: int
    resource: str
    qty_per_delivery: StrictInt = Field(ge=1, le=1_000_000_000)
    unit_price: StrictInt = Field(ge=1, le=1_000_000_000)
    deliveries: StrictInt = Field(ge=1, le=30)
    interval_hours: StrictInt = Field(ge=1, le=720)
    note: str = Field(default="", max_length=500)


@router.post("/contracts")
async def create_contract(body: ContractBody, user=Depends(get_user)):
    if body.seller_id == user["id"]:
        raise HTTPException(400, "فروشنده باید بازیکن دیگری باشد")
    resource = _resource(body.resource)
    buyer, seller = await _active(user["id"]), await _active(body.seller_id)
    cfg = await trade_rules()
    await check_price(resource, body.unit_price)
    if (body.qty_per_delivery > cfg['max_order_quantity'] or body.deliveries > cfg['max_contract_deliveries'] or
            body.interval_hours > cfg['max_contract_interval'] or
            await contracts.count_documents({'buyer_id': user['id'], 'status': {'$in': ['pending', 'active']}}) >= cfg['max_open_contracts']):
        raise HTTPException(400, 'تعداد، فاصلهٔ تحویل یا قراردادهای باز بیشتر از سقف مجاز است')
    total = body.qty_per_delivery * body.unit_price * body.deliveries
    if total > cfg['max_trade_value']:
        raise HTTPException(400, "ارزش قرارداد بیشتر از سقف مجاز است")
    identity = ObjectId()
    doc = {
        "_id": identity, "buyer_id": user["id"], "buyer_name": buyer.get("name", "بازیکن"),
        "buyer_character": buyer.get("created_at"), "seller_id": seller["tg_id"], "seller_name": seller.get("name", "بازیکن"),
        "seller_character": seller.get("created_at"), "resource": resource,
        "qty_per_delivery": body.qty_per_delivery, "unit_price": body.unit_price,
        "deliveries": body.deliveries, "delivered": 0, "interval_hours": body.interval_hours,
        "escrow_remaining": total, "status": "pending", "note": body.note.strip(), "created_at": now(),
    }
    await commit({
        "_id": str(uuid4()), "kind": "supply_contract_create", "complete": False,
        "wallets": [{"member": member_for(buyer, 0), "cost": {"gold": total}, "debit": True}],
        "changes": [{"collection": "supply_contracts", "query": {"_id": identity}, "update": {"$setOnInsert": doc}, "upsert": True}],
    })
    await send_system_message(body.seller_id, seller.get("name", ""), f"قرارداد تأمین تازه از طرف {buyer.get('name', 'بازیکن')} داری؛ پاسخ را در صفحهٔ تجارت ثبت کن.", kind="trade")
    return _contract(doc, user["id"])


class RespondBody(BaseModel):
    accept: bool


@router.post("/contracts/{contract_id}/respond")
async def respond_contract(contract_id: str, body: RespondBody, user=Depends(get_user)):
    row = await contracts.find_one({"_id": _oid(contract_id), "seller_id": user["id"]})
    if not row or row["status"] != "pending":
        raise HTTPException(409, "این قرارداد منتظر پاسخ تو نیست")
    seller = await _active(user["id"])
    if row.get("seller_character") is not None and seller.get("created_at") != row.get("seller_character"):
        raise HTTPException(409, "شخصیت فروشنده تغییر کرده است؛ مدیریت باید قرارداد را ببندد")
    buyer = await players.find_one({"tg_id": row["buyer_id"]})
    if body.accept:
        buyer = await _active(row["buyer_id"])
        if row.get("buyer_character") is not None and buyer.get("created_at") != row.get("buyer_character"):
            raise HTTPException(409, "شخصیت خریدار تغییر کرده است؛ مدیریت باید قرارداد را ببندد")
    if body.accept:
        await trade_rules()
        await check_price(row['resource'], row['unit_price'])
        stamp = now()
        due = stamp + timedelta(hours=row["interval_hours"])
        await contracts.update_one({"_id": row["_id"], "status": "pending"}, {"$set": {"status": "active", "accepted_at": stamp, "available_at": stamp, "next_due": due}})
        await record_event("supply_contract", "قرارداد تأمین پذیرفته شد", actor_id=user["id"], target_ids=[row["buyer_id"]], detail=f"{row['qty_per_delivery']:,} {TRADE_GOOD_NAMES[row['resource']]} در هر نوبت", dedupe_key=f"contract:{contract_id}:accepted")
    else:
        refund = row["escrow_remaining"]
        buyer_member = ({
            "tg_id": row["buyer_id"], "name": row.get("buyer_name", "بازیکن"),
            "character_created_at": row.get("buyer_character", buyer.get("created_at") if buyer else None), "shares": 0,
        } if buyer else None)
        await commit({
            "_id": str(uuid4()), "kind": "supply_contract_reject", "complete": False,
            "wallets": ([{"member": buyer_member, "cost": {"gold": refund}}] if buyer_member else []),
            "changes": [{"collection": "supply_contracts", "query": {"_id": row["_id"]}, "update": {"$set": {"status": "rejected", "escrow_remaining": 0, "closed_at": now()}}}],
        })
    if buyer:
        await send_system_message(row["buyer_id"], buyer.get("name", ""), f"{seller.get('name', 'فروشنده')} قرارداد تأمین را {'پذیرفت' if body.accept else 'رد کرد'}.", kind="trade")
    return {"ok": True}


@router.post("/contracts/{contract_id}/deliver")
async def deliver_contract(contract_id: str, user=Depends(get_user)):
    row = await contracts.find_one({"_id": _oid(contract_id), "seller_id": user["id"]})
    if not row or row["status"] != "active":
        raise HTTPException(409, "قرارداد فعال پیدا نشد")
    if row.get("available_at") and now() < row["available_at"]:
        raise HTTPException(409, "زمان نوبت بعدی هنوز نرسیده است")
    seller, buyer = await _active(user["id"]), await _active(row["buyer_id"])
    if ((row.get("seller_character") is not None and seller.get("created_at") != row.get("seller_character")) or
            (row.get("buyer_character") is not None and buyer.get("created_at") != row.get("buyer_character"))):
        raise HTTPException(409, "یکی از شخصیت‌های قرارداد تغییر کرده است؛ مدیریت باید قرارداد را ببندد")
    cfg = await trade_rules()
    await check_price(row['resource'], row['unit_price'])
    delivered = row.get("delivered", 0) + 1
    amount = row["qty_per_delivery"] * row["unit_price"]
    cross_region = seller.get('region') != buyer.get('region')
    fee = (amount * (cfg['market_fee_percent'] + (cfg['cross_region_tariff_percent'] if cross_region else 0)) // 100) if cfg['contract_fees_enabled'] else 0
    remaining_gold = row["escrow_remaining"] - amount
    finished = delivered >= row["deliveries"]
    event = f"supply:{contract_id}:{delivered}"
    receipt = 'receipts.' + receipt_key(event)
    await db.realm_treasury.update_one({'_id': 'trade'}, {'$setOnInsert': {'gold': 0}}, upsert=True)
    await commit({
        "_id": str(uuid4()), "kind": "supply_contract_delivery", "complete": False,
        "wallets": [
            {"member": member_for(seller, 0), "cost": {row["resource"]: row["qty_per_delivery"]}, "debit": True},
            {"member": member_for(buyer, 0), "cost": {row["resource"]: row["qty_per_delivery"]}},
            {"member": member_for(seller, 0), "cost": {"gold": amount - fee}},
        ],
        "changes": [
            {"collection": "supply_contracts", "query": {"_id": row["_id"]}, "update": {"$set": {
                "delivered": delivered, "escrow_remaining": remaining_gold,
                "status": "completed" if finished else "active", "last_delivery": now(),
                "available_at": None if finished else now() + timedelta(hours=row["interval_hours"]),
                "next_due": None if finished else now() + timedelta(hours=row["interval_hours"] * 2),
            }}},
            {'collection': 'realm_treasury', 'query': {'_id': 'trade', receipt: {'$ne': True}},
             'update': {'$set': {receipt: True}, '$inc': {'gold': fee}}},
            _stat_change(user["id"], event + ":seller", {"market_sold_value": amount, "supply_deliveries": 1}),
            _stat_change(row["buyer_id"], event + ":buyer", {"market_bought_value": amount}),
            _event_change(event, "supply_delivery", "تحویل قرارداد تأمین", user["id"], [row["buyer_id"]], f"نوبت {delivered} از {row['deliveries']}", {"gross": amount, "fee": fee, "payout": amount-fee, "resource": row["resource"], "qty": row["qty_per_delivery"]}),
        ],
    })
    await adjust_reputation(row["buyer_id"], user["id"], 2, "تحویل به‌موقع قرارداد", source_id=event)
    await adjust_influence(user["id"], 2, "وفای به قرارداد تأمین", source_id=event)
    return {"ok": True, "delivered": delivered, "completed": finished}


async def _close_contract(row, status, reason, actor=None):
    buyer = await players.find_one({"tg_id": row["buyer_id"]})
    refund = max(0, int(row.get("escrow_remaining", 0)))
    buyer_member = ({
        "tg_id": row["buyer_id"], "name": row.get("buyer_name", buyer.get("name", "بازیکن") if buyer else "بازیکن"),
        "character_created_at": row.get("buyer_character", buyer.get("created_at") if buyer else None), "shares": 0,
    } if buyer else None)
    wallets = [{"member": buyer_member, "cost": {"gold": refund}}] if buyer_member and refund else []
    await commit({
        "_id": str(uuid4()), "kind": "supply_contract_close", "complete": False,
        "wallets": wallets,
        "changes": [{"collection": "supply_contracts", "query": {"_id": row["_id"]}, "update": {"$set": {
            "status": status, "close_reason": reason, "escrow_remaining": 0, "closed_at": now(), "closed_by": actor,
        }}}],
    })
    await record_event('contract_closed', 'بسته‌شدن قرارداد تأمین', actor_id=actor,
                       target_ids=[row['buyer_id'], row['seller_id']], detail=reason,
                       data={'contract_id': str(row['_id']), 'refund': refund, 'status': status},
                       dedupe_key=f"contract:{row['_id']}:closed")
    return refund


@router.delete("/contracts/{contract_id}")
async def cancel_contract(contract_id: str, user=Depends(get_user)):
    row = await contracts.find_one({"_id": _oid(contract_id), "buyer_id": user["id"]})
    if not row or row["status"] != "pending":
        raise HTTPException(409, "فقط قرارداد منتظر پاسخ را می‌توانی پس بگیری")
    refund = await _close_contract(row, "cancelled", "پس‌گرفتن پیش از پذیرش", user["id"])
    return {"ok": True, "refunded": refund}


@router.get("/admin/contracts")
async def admin_contracts(admin=Depends(full_admin)):
    return [_contract(row, admin["id"]) async for row in contracts.find({}).sort("created_at", -1).limit(300)]


class AdminCloseBody(BaseModel):
    reason: str = Field(min_length=2, max_length=500)


@router.post("/admin/contracts/{contract_id}/close")
async def admin_close_contract(contract_id: str, body: AdminCloseBody, admin=Depends(full_admin)):
    if len(body.reason.strip()) < 2:
        raise HTTPException(400, 'دلیل بستن قرارداد را بنویس')
    row = await contracts.find_one({"_id": _oid(contract_id)})
    if not row or row["status"] not in ("pending", "active"):
        raise HTTPException(409, "این قرارداد باز نیست")
    refund = await _close_contract(row, "admin_closed", body.reason, admin["id"])
    return {"ok": True, "refunded": refund}


async def settle_overdue_contracts():
    cfg = {**DEFAULTS, **await realm_rules()}
    cutoff = now() - timedelta(hours=cfg["contract_grace_hours"])
    async for row in contracts.find({"status": "active", "next_due": {"$lte": cutoff}}):
        await _close_contract(row, "breached", "مهلت تحویل قرارداد گذشته است")
        await players.update_one({"tg_id": row["seller_id"]}, {"$inc": {"stats.supply_breaches": 1}})
        await adjust_reputation(row["buyer_id"], row["seller_id"], -10, "نقض قرارداد تأمین", source_id=f"contract:{row['_id']}:breach")
        await send_system_message(row["buyer_id"], row["buyer_name"], f"قرارداد تأمین با {row['seller_name']} به‌دلیل نرسیدن تحویل بسته شد و ماندهٔ امانت برگشت.", kind="trade")


async def ensure_indexes():
    await orders.create_index([("status", 1), ("resource", 1), ("created_at", -1)])
    await orders.create_index([("buyer_id", 1), ("created_at", -1)])
    await contracts.create_index([("buyer_id", 1), ("created_at", -1)])
    await contracts.create_index([("seller_id", 1), ("created_at", -1)])
    await contracts.create_index([("status", 1), ("next_due", 1)])


@router.get('/admin/orders')
async def admin_orders(admin=Depends(full_admin)):
    return [_order(row, admin['id']) async for row in orders.find({}).sort('created_at', -1).limit(300)]


@router.post('/admin/orders/{order_id}/close')
async def admin_close_order(order_id: str, body: AdminCloseBody, admin=Depends(full_admin)):
    row = await orders.find_one({'_id': _oid(order_id)})
    if not row or row['status'] != 'open':
        raise HTTPException(409, 'این سفارش باز نیست')
    if not body.reason.strip():
        raise HTTPException(400, 'دلیل بستن سفارش را بنویس')
    result = await _cancel_order(row)
    await record_event('admin_order_closed', 'بستن سفارش خرید', actor_id=admin['id'], target_ids=[row['buyer_id']],
                       detail=body.reason, data={'order_id': order_id, 'refund': result['refunded']},
                       dedupe_key=f'order:{order_id}:admin-closed')
    return result
