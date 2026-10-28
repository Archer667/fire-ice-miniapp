from datetime import timedelta
from bson import ObjectId
from fastapi import APIRouter, Depends, HTTPException
from pydantic import BaseModel, Field, StrictInt

from auth import get_full_admin, get_user
from db import db, players
from game import now
from realm_state import EVENTS, REPUTATION, adjust_influence, overview_for, record_event


router = APIRouter(prefix="/api/realm", tags=["realm"])
proposals = db.council_proposals

from realm_controls import DEFAULTS as DEFAULT_RULES, RulesSchema, rules


async def full_admin(user=Depends(get_user)):
    return await get_full_admin(user)


def _proposal(row, uid):
    votes = row.get("votes", {})
    tally = [0] * len(row["options"])
    for choice in votes.values():
        if isinstance(choice, int) and 0 <= choice < len(tally):
            tally[choice] += 1
    return {
        "id": str(row["_id"]), "title": row["title"], "description": row["description"],
        "scope": row["scope"], "region": row.get("region"), "author_id": row["author_id"],
        "author_name": row["author_name"], "options": row["options"], "status": row["status"],
        "supporters": len(row.get("supporters", [])), "supported": uid in row.get("supporters", []),
        "tally": tally, "total_votes": len(votes), "my_vote": votes.get(str(uid)),
        "created_at": row["created_at"].isoformat(), "closes_at": row["closes_at"].isoformat(),
        "voting_open": row["status"] == "open" and row["closes_at"] > now(),
        "outcome": row.get("outcome", ""), "quorum_percent": row.get("quorum_percent", 30),
    }


async def _player(uid):
    player = await players.find_one({"tg_id": uid})
    from character_access import status as character_status
    if character_status(player) not in ("landed", "landless"):
        raise HTTPException(403, "فقط کاراکتر فعال می‌تواند در سیاست قلمرو شرکت کند")
    return player


@router.get("/overview")
async def overview(user=Depends(get_user)):
    player = await _player(user["id"])
    result = await overview_for(player)
    result["rules"] = await rules()
    relations = []
    target_ids = []
    rows = []
    async for row in REPUTATION.find({"from_id": user["id"]}).sort("score", -1).limit(30):
        rows.append(row); target_ids.append(row["to_id"])
    names = {p["tg_id"]: p.get("name", "بازیکن") async for p in players.find({"tg_id": {"$in": target_ids}}, {"tg_id": 1, "name": 1})}
    for row in rows:
        relations.append({"tg_id": row["to_id"], "name": names.get(row["to_id"], "بازیکن"), "score": row.get("score", 0)})
    result["relations"] = relations
    return result


@router.get("/events")
async def my_events(user=Depends(get_user)):
    query = {"$or": [
        {"visibility": "public"}, {"actor_id": user["id"]}, {"target_ids": user["id"]},
    ]}
    out = []
    async for row in EVENTS.find(query).sort("game_at", -1).limit(80):
        out.append({
            "id": str(row["_id"]), "kind": row["kind"], "title": row["title"],
            "detail": row.get("detail", ""), "at": row["game_at"].isoformat(), "data": row.get("data", {}),
        })
    return out


@router.get("/proposals")
async def list_proposals(user=Depends(get_user)):
    player = await _player(user["id"])
    query = {"$or": [{"scope": "realm"}, {"region": player.get("region")}]}
    out = []
    async for row in proposals.find(query).sort("created_at", -1).limit(60):
        out.append(_proposal(row, user["id"]))
    return out


class ProposalBody(BaseModel):
    title: str = Field(min_length=4, max_length=100)
    description: str = Field(min_length=10, max_length=2500)
    options: list[str]
    scope: str = "realm"


@router.post("/proposals")
async def create_proposal(body: ProposalBody, user=Depends(get_user)):
    player = await _player(user["id"])
    options = [" ".join(item.split())[:80] for item in body.options if item.strip()]
    if not 2 <= len(options) <= 5 or len(set(options)) != len(options):
        raise HTTPException(400, "بین دو تا پنج گزینهٔ متفاوت لازم است")
    if body.scope not in ("realm", "region"):
        raise HTTPException(400, "محدودهٔ پیشنهاد معتبر نیست")
    cfg = await rules()
    if not cfg['council_enabled']:
        raise HTTPException(409, 'شورا فعلاً پیشنهاد تازه نمی‌پذیرد')
    if await proposals.count_documents({'author_id': user['id'], 'status': 'open'}) >= cfg['max_open_proposals']:
        raise HTTPException(409, 'به سقف پیشنهادهای باز رسیده‌ای')
    identity = ObjectId()
    balance = await adjust_influence(user["id"], -int(cfg["proposal_cost"]), "ثبت پیشنهاد در شورا", source_id=f"proposal:{identity}")
    if balance is None:
        raise HTTPException(400, f"برای ثبت پیشنهاد {int(cfg['proposal_cost'])} نفوذ سیاسی لازم داری")
    stamp = now()
    doc = {
        "_id": identity, "title": " ".join(body.title.split()), "description": body.description.strip(),
        "options": options, "scope": body.scope, "region": player.get("region") if body.scope == "region" else None,
        "author_id": user["id"], "author_name": player.get("name", "بازیکن"),
        "status": "open", "supporters": [], "votes": {}, "created_at": stamp,
        "closes_at": stamp + timedelta(hours=int(cfg["voting_hours"])),
        "quorum_percent": int(cfg["quorum_percent"]),
    }
    await proposals.insert_one(doc)
    await record_event("proposal", "پیشنهاد تازه در شورا", actor_id=user["id"], detail=doc["title"], visibility="public", dedupe_key=f"proposal:{identity}:created")
    return _proposal(doc, user["id"])


@router.post("/proposals/{proposal_id}/support")
async def support_proposal(proposal_id: str, user=Depends(get_user)):
    if not ObjectId.is_valid(proposal_id):
        raise HTTPException(404, "پیشنهاد پیدا نشد")
    player = await _player(user["id"])
    row = await proposals.find_one({"_id": ObjectId(proposal_id)})
    if not row or row["status"] != "open" or row["closes_at"] <= now():
        raise HTTPException(409, "این پیشنهاد دیگر برای حمایت باز نیست")
    if user["id"] in row.get("supporters", []):
        raise HTTPException(409, "قبلاً از این پیشنهاد حمایت کرده‌ای")
    if row['scope'] == 'region' and player.get('region') != row.get('region'):
        raise HTTPException(403, 'این پیشنهاد برای اقلیم تو نیست')
    cfg = await rules()
    if not cfg['council_enabled']:
        raise HTTPException(409, 'حمایت در شورا فعلاً متوقف است')
    balance = await adjust_influence(user["id"], -int(cfg["support_cost"]), "حمایت از پیشنهاد شورا", source_id=f"support:{proposal_id}:{user['id']}")
    if balance is None:
        raise HTTPException(400, f"برای حمایت {int(cfg['support_cost'])} نفوذ سیاسی لازم داری")
    await proposals.update_one({"_id": row["_id"]}, {"$addToSet": {"supporters": user["id"]}})
    return {"ok": True, "influence": balance}


class VoteBody(BaseModel):
    option: StrictInt


@router.post("/proposals/{proposal_id}/vote")
async def vote_proposal(proposal_id: str, body: VoteBody, user=Depends(get_user)):
    if not ObjectId.is_valid(proposal_id):
        raise HTTPException(404, "پیشنهاد پیدا نشد")
    player = await _player(user["id"])
    row = await proposals.find_one({"_id": ObjectId(proposal_id)})
    if not row or row["status"] != "open" or row["closes_at"] <= now():
        raise HTTPException(409, "مهلت رأی‌دادن تمام شده است")
    if row["scope"] == "region" and player.get("region") != row.get("region"):
        raise HTTPException(403, "این رأی‌گیری برای اقلیم تو نیست")
    if not 0 <= body.option < len(row["options"]):
        raise HTTPException(400, "گزینهٔ رأی معتبر نیست")
    if not (await rules())['council_enabled']:
        raise HTTPException(409, 'رأی‌گیری شورا فعلاً متوقف است')
    first_vote = str(user["id"]) not in row.get("votes", {})
    await proposals.update_one({"_id": row["_id"]}, {"$set": {f"votes.{user['id']}": body.option}})
    if first_vote:
        await adjust_influence(user["id"], 1, "شرکت در رأی‌گیری شورا", source_id=f"vote:{proposal_id}:{user['id']}")
    return {"ok": True}


class FinishBody(BaseModel):
    outcome: str = Field(default="", max_length=2000)
    enact: bool = False


@router.post("/admin/proposals/{proposal_id}/finish")
async def finish_proposal(proposal_id: str, body: FinishBody, admin=Depends(full_admin)):
    if len(body.outcome.strip()) < 2:
        raise HTTPException(400, 'نتیجه و توضیح نهایی را بنویس')
    if not ObjectId.is_valid(proposal_id):
        raise HTTPException(404, "پیشنهاد پیدا نشد")
    row = await proposals.find_one({"_id": ObjectId(proposal_id)})
    if not row or row["status"] != "open":
        raise HTTPException(409, "این پیشنهاد باز نیست")
    eligible_query = {"is_dead": {"$ne": True}, "registration_reset": {"$ne": True}}
    if row["scope"] == "region": eligible_query["region"] = row.get("region")
    eligible = max(1, await players.count_documents(eligible_query))
    quorum = len(row.get("votes", {})) / eligible * 100
    status = "enacted" if body.enact else "closed"
    await proposals.update_one({"_id": row["_id"]}, {"$set": {
        "status": status, "outcome": body.outcome.strip(), "finished_at": now(),
        "finished_by": admin["id"], "quorum_reached": quorum >= row.get("quorum_percent", 30),
        "actual_quorum_percent": round(quorum, 1),
    }})
    await record_event("proposal_result", "نتیجهٔ شورای قلمرو", actor_id=admin["id"], detail=body.outcome or row["title"], visibility="public", dedupe_key=f"proposal:{proposal_id}:finished")
    return {"ok": True, "status": status, "quorum_percent": round(quorum, 1)}


class RulesBody(RulesSchema):
    reason: str = Field(min_length=2, max_length=500)


@router.get("/admin/rules")
async def admin_rules(admin=Depends(full_admin)):
    return await rules()


@router.get("/admin/proposals")
async def admin_proposals(admin=Depends(full_admin)):
    return [_proposal(row, admin["id"]) async for row in proposals.find({}).sort("created_at", -1).limit(200)]


@router.put("/admin/rules")
async def save_rules(body: RulesBody, admin=Depends(full_admin)):
    if len(body.reason.strip()) < 2:
        raise HTTPException(400, 'دلیل تغییر را بنویس')
    values = body.model_dump(exclude={'reason'})
    before = await rules()
    await db.game_settings.update_one({"_id": "realm_rules"}, {"$set": values}, upsert=True)
    await record_event('admin_realm_rules', 'تغییر قواعد شورا و اقتصاد', actor_id=admin['id'], detail=body.reason,
                       data={'before': before, 'after': values})
    return values


async def ensure_indexes():
    await proposals.create_index([("status", 1), ("closes_at", 1)])
    await proposals.create_index([("scope", 1), ("region", 1), ("created_at", -1)])

class InfluenceBody(BaseModel):
    delta: StrictInt = Field(ge=-1_000_000_000, le=1_000_000_000)
    reason: str = Field(min_length=2, max_length=500)
    request_id: str = Field(min_length=16, max_length=100, pattern=r'^[a-zA-Z0-9_-]+$')


@router.post('/admin/players/{uid}/influence')
async def admin_influence(uid: int, body: InfluenceBody, admin=Depends(full_admin)):
    if not body.reason.strip() or not body.delta:
        raise HTTPException(400, 'مقدار تغییر و دلیل آن را بنویس')
    balance = await adjust_influence(uid, body.delta, body.reason, source_id=f'admin:{admin["id"]}:{body.request_id}')
    if balance is None:
        raise HTTPException(409, 'بازیکن پیدا نشد یا نفوذ کافی برای این کاهش ندارد')
    await record_event('admin_influence', 'اصلاح نفوذ سیاسی', actor_id=admin['id'], target_ids=[uid],
                       detail=body.reason, data={'requested_delta': body.delta, 'balance': balance},
                       dedupe_key=f'admin-influence:{admin["id"]}:{body.request_id}:{uid}')
    return {'ok': True, 'balance': balance}


def _safe_json(value):
    if isinstance(value, dict):
        return {str(k): _safe_json(v) for k,v in value.items()}
    if isinstance(value, list):
        return [_safe_json(v) for v in value]
    if isinstance(value, ObjectId):
        return str(value)
    if hasattr(value, 'isoformat'):
        return value.isoformat()
    return value


@router.get('/admin/overview')
async def admin_overview(admin=Depends(full_admin)):
    treasury = await db.realm_treasury.find_one({'_id': 'trade'}) or {}
    result = {'treasury_gold': treasury.get('gold', 0)}
    for name, collection, query in [
        ('open_proposals', proposals, {'status': 'open'}),
        ('open_orders', db.market_buy_orders, {'status': 'open'}),
        ('open_contracts', db.supply_contracts, {'status': {'$in': ['pending', 'active']}}),
    ]:
        result[name] = await collection.count_documents(query)
    escrow = 0
    for collection in (db.market_buy_orders, db.supply_contracts):
        async for row in collection.find({'status': {'$in': ['open', 'pending', 'active']}}, {'escrow_remaining': 1}):
            escrow += int(row.get('escrow_remaining', 0))
    result['escrow_gold'] = escrow
    return result


@router.get('/admin/influence')
async def admin_influence_players(search: str = '', page: int = 0, admin=Depends(full_admin)):
    import re
    query = {}
    if search.strip():
        query = {'name': {'$regex': re.escape(search.strip()[:100]), '$options': 'i'}}
        if search.strip().isdigit():
            query = {'$or': [query, {'tg_id': int(search.strip())}]}
    page = max(0, min(page, 100000))
    cfg = await rules()
    rows = []
    async for p in players.find(query).sort('name', 1).skip(page*50).limit(50):
        rows.append({'uid': p['tg_id'], 'name': p.get('name', 'بازیکن'),
                     'influence': p.get('political_influence', cfg['influence_start']), 'is_dead': bool(p.get('is_dead'))})
    return {'rows': rows, 'total': await players.count_documents(query), 'page': page}


@router.get('/admin/events')
async def admin_events(kind: str = '', uid: int = 0, page: int = 0, admin=Depends(full_admin)):
    query = {}
    if kind:
        query['kind'] = kind[:80]
    if uid:
        query['$or'] = [{'actor_id': uid}, {'target_ids': uid}]
    page = max(0, min(page, 100000))
    rows = [_safe_json(row) async for row in EVENTS.find(query).sort('real_at', -1).skip(page*50).limit(50)]
    return {'rows': rows, 'total': await EVENTS.count_documents(query), 'page': page}
