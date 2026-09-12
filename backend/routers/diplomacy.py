from public_audience import public_recipients, public_players
from datetime import datetime, timedelta
from uuid import uuid4
from bson import ObjectId
from fastapi import APIRouter, Depends, HTTPException
from pydantic import BaseModel
from auth import get_user
from db import players, alliances
from game import now, apply_production, can_afford, pay, add_resources, production_fields
from game_data import ALLIANCE_TYPES
from config import FEAST_COST, FEAST_POPULARITY_GAIN, FEAST_COOLDOWN_HOURS, POPULARITY_MAX, PRIVATE_ALLIANCE_MULTIPLIER
from routers.ravens import send_system_message
from player_labels import titled_name
from control_settings import get as rule

router = APIRouter(prefix="/api/diplomacy", tags=["diplomacy"])

class ProposeBody(BaseModel):
    to_tg_ids: list[int]
    type: str
    name: str = ""
    private: bool = False
    existing_alliance_id: str | None = None
    penalty_gold: int = 0   # فقط برای «پیمان عدم‌تجاوز» — غرامتی که خیانت‌کننده باید بپردازد

@router.post("/propose")
async def propose(body: ProposeBody, user: dict = Depends(get_user)):
    source = None
    if body.existing_alliance_id:
        if not ObjectId.is_valid(body.existing_alliance_id):
            raise HTTPException(400, 'شناسهٔ پیمان نامعتبر است')
        source = await alliances.find_one({'_id': ObjectId(body.existing_alliance_id)})
        if not source or source['from_id'] != user['id']:
            raise HTTPException(403, 'فقط سازندهٔ پیمان می‌تواند عضو جدید دعوت کند')
        if source['status'] != 'accepted' or source.get('marriage_id'):
            raise HTTPException(409, 'فقط پیمان برقرار و مستقل از ازدواج قابل گسترش است')
        body = body.model_copy(update={'type': source['type'], 'name': source.get('name', ''),
            'private': not source.get('public', True), 'penalty_gold': source.get('penalty_gold', 0)})
    if not 0 <= body.penalty_gold <= 1000000000:
        raise HTTPException(400, "غرامت باید بین صفر و یک میلیارد سکه باشد")
    if body.type not in ALLIANCE_TYPES:
        raise HTTPException(400, "نوع پیمان نامعتبر")
    if body.type == "non_aggression" and body.penalty_gold <= 0:
        raise HTTPException(400, "برای پیمان عدم‌تجاوز باید مقدار غرامت (طلا) را مشخص کنی")
    me = await players.find_one({"tg_id": user["id"]})
    if not me or not me.get('castle') or me.get('is_dead') or me.get('registration_reset'):
        raise HTTPException(403, "اول ثبت‌نام کن")

    target_ids = [tid for tid in dict.fromkeys(body.to_tg_ids) if tid != user["id"]]
    if not target_ids:
        raise HTTPException(400, "هیچ گیرنده‌ای انتخاب نشده")
    if len(target_ids) > 50:
        raise HTTPException(400, 'هر بار حداکثر ۵۰ بازیکن را دعوت کن')
    targets = await players.find({"tg_id": {"$in": target_ids}, 'castle': {'$exists': True, '$nin': [None, '']},
        'is_dead': {'$ne': True}, 'registration_reset': {'$ne': True}}).to_list(len(target_ids))
    if not targets:
        raise HTTPException(404, "هیچ‌کدام از گیرنده‌های انتخابی پیدا نشدند")

    # حذف کسانی که همین الان پیمانی از همین نوع باهاشون در جریان است
    valid_targets = []
    for t in targets:
        existing = await alliances.find_one({
            "type": body.type, "status": {"$in": ["pending", "accepted"]},
            "$or": [
                {"from_id": user["id"], "to_id": t["tg_id"]},
                {"from_id": t["tg_id"], "to_id": user["id"]},
            ],
        })
        if not existing:
            valid_targets.append(t)
    if not valid_targets:
        raise HTTPException(409, "با همهٔ گیرنده‌های انتخابی، پیمانی از همین نوع از قبل داری")

    me = apply_production(me)
    pact_costs = rule("diplomacy.pact_costs", {})
    base_cost = int(pact_costs.get(body.type, ALLIANCE_TYPES[body.type]["wine_cost"]))
    unit_cost = round(base_cost * (float(rule("diplomacy.private_multiplier", PRIVATE_ALLIANCE_MULTIPLIER)) if body.private else 1))
    total_cost = {"wine": unit_cost * len(valid_targets)}
    if not can_afford(me["resources"], total_cost):
        raise HTTPException(400, f"شراب کافی برای پیشنهاد به {len(valid_targets)} نفر نداری")
    pay(me["resources"], total_cost)
    await players.update_one({"tg_id": user["id"]}, {"$set": production_fields(me)})

    pact_name = body.name.strip()[:60]
    penalty_gold = max(0, body.penalty_gold)
    group_id = (source.get('group_id') or 'pact-' + str(source['_id'])) if source else str(uuid4())
    if source and not source.get('group_id'):
        # Extend this exact invitation batch, never unrelated pacts sharing a name.
        batch = {'_id': source['_id']}
        if source.get('created_at'):
            batch = {'from_id': source['from_id'], 'type': source['type'],
                'name': source.get('name', ''), 'public': source.get('public', True),
                'created_at': source['created_at'], 'group_id': {'$exists': False}}
        await alliances.update_many(batch, {'$set': {'group_id': group_id}})
        await alliances.update_one({'_id': source['_id']}, {'$set': {'group_id': group_id}})
    await alliances.insert_many([{
        **({"group_id": group_id} if group_id else {}),
        **({'invited_via': str(source['_id'])} if source else {}),
        "from_id": user["id"], "from_name": me["name"],
        "from_gender": me.get("gender", "lord"),
        "to_id": t["tg_id"], "to_name": t["name"], "to_gender": t.get("gender", "lord"),
        "type": body.type, "wine_cost": unit_cost, "name": pact_name,
        "penalty_gold": penalty_gold,
        "public": not body.private,
        "status": "pending", "created_at": now(),
    } for t in valid_targets])

    type_name = ALLIANCE_TYPES[body.type]["name"]
    penalty_note = f" — غرامتِ خیانت: {penalty_gold:,} سکه" if penalty_gold else ""
    for t in valid_targets:
        await send_system_message(
            t["tg_id"], t["name"],
            f"{titled_name(me)} {'دعوت به عضویت در' if source else 'پیشنهاد'} «{type_name}»{f' («{pact_name}»)' if pact_name else ''} فرستاد{penalty_note} — از تب دیپلماسی بپذیر یا رد کن. عضویت فقط پس از پذیرش فعال می‌شود.",
            kind="diplomacy",
        )
    return {"ok": True, "sent_to": len(valid_targets), "skipped": len(target_ids) - len(valid_targets), 'wine_spent': total_cost['wine']}

class InviteBody(BaseModel):
    to_tg_ids: list[int]

@router.post('/{alliance_id}/invite')
async def invite(alliance_id: str, body: InviteBody, user: dict = Depends(get_user)):
    return await propose(ProposeBody(to_tg_ids=body.to_tg_ids, type='', existing_alliance_id=alliance_id), user)

@router.get("/mine")
async def mine(user: dict = Depends(get_user)):
    out = []
    group_members = {}
    cur = alliances.find({"$or": [{"from_id": user["id"]}, {"to_id": user["id"]}]}).sort("created_at", -1)
    async for a in cur:
        mine_proposed = a["from_id"] == user["id"]
        gid = a.get('group_id')
        if gid and gid not in group_members:
            members = {}
            async for edge in alliances.find({'group_id': gid, 'status': 'accepted'}):
                members[edge['from_id']] = edge['from_name']
                members[edge['to_id']] = edge['to_name']
            group_members[gid] = list(members.values())
        out.append({
            "id": str(a["_id"]),
            "mine_proposed": mine_proposed,
            'can_invite': mine_proposed and a['status'] == 'accepted' and not a.get('marriage_id'),
            'invite_wine_cost': round(int(rule('diplomacy.pact_costs', {}).get(a['type'], ALLIANCE_TYPES[a['type']]['wine_cost'])) *
                (float(rule('diplomacy.private_multiplier', PRIVATE_ALLIANCE_MULTIPLIER)) if not a.get('public', True) else 1)),
            "group_id": a.get("group_id"),
            "group_members": group_members.get(gid, []) if a['status'] in ('pending', 'accepted') else [],
            "other_id": a["to_id"] if mine_proposed else a["from_id"],
            "other_name": a["to_name"] if mine_proposed else a["from_name"],
            "type": a["type"], "type_name": ALLIANCE_TYPES[a["type"]]["name"],
            "name": a.get("name", ""),
            "public": a.get("public", True),
            "penalty_gold": a.get("penalty_gold", 0), "marriage_id": a.get("marriage_id"),
            "status": a["status"],
        })
    return out

@router.get("/public")
async def public_alliances(user: dict = Depends(get_user)):
    """اتحادهای برقرارِ عمومی — همهٔ بازیکنان می‌بینند، مگر آن‌هایی که با هزینهٔ دوبرابر خصوصی نگه داشته شده‌اند"""
    out = []
    cur = alliances.find({"status": "accepted", "public": {"$ne": False}}).sort("created_at", -1).limit(100)
    async for a in cur:
        out.append({
            "id": str(a["_id"]), "from_name": a["from_name"], "to_name": a["to_name"],
            "type": a["type"], "type_name": ALLIANCE_TYPES[a["type"]]["name"],
            "name": a.get("name", ""), "created_at": a["created_at"].isoformat(),
        })
    return out

class RespondBody(BaseModel):
    accept: bool

@router.post("/{alliance_id}/respond")
async def respond(alliance_id: str, body: RespondBody, user: dict = Depends(get_user)):
    a = await alliances.find_one({"_id": ObjectId(alliance_id)})
    if not a:
        raise HTTPException(404, "پیمان پیدا نشد")
    if a["to_id"] != user["id"]:
        raise HTTPException(403, "این پیمان برای تو نیست")
    if a["status"] != "pending":
        raise HTTPException(400, "این پیمان قبلاً پاسخ داده شده")

    if body.accept and a.get('invited_via'):
        proposer = await players.find_one({'tg_id': a['from_id']})
        active = await alliances.find_one({'group_id': a.get('group_id'), 'from_id': a['from_id'], 'status': 'accepted'})
        if not active or not proposer or proposer.get('is_dead') or not proposer.get('castle') or proposer.get('registration_reset'):
            raise HTTPException(409, 'این پیمان دیگر فعال نیست؛ دعوت را رد کن تا هزینهٔ آن به سازنده برگردد')

    if body.accept and a['type'] == 'full_alliance':
        from marriage_pacts import spouses
        first = await players.find_one({'tg_id': a['from_id']})
        second = await players.find_one({'tg_id': a['to_id']})
        if await spouses(first, second):
            raise HTTPException(409, 'پیمان کامل ازدواج برقرار است؛ این درخواست قدیمی را رد کن تا هزینه‌اش برگردد')

    # اتمیک و مشروط به status=pending — وگرنه دو کلیکِ هم‌زمانِ پذیرفتن/ردکردن هردو از
    # رویِ همون خواندنِ قدیمی رد می‌شن و alliance_count دوبار می‌خوره یا شرابِ رد دوبار برمی‌گرده
    new_status = "accepted" if body.accept else "rejected"
    guard = await alliances.update_one(
        {"_id": a["_id"], "status": "pending"}, {"$set": {"status": new_status, **({"accepted_at": now()} if body.accept else {})}},
    )
    if guard.matched_count == 0:
        raise HTTPException(400, "این پیمان قبلاً پاسخ داده شده")

    party_rows = await players.find(
        {"tg_id": {"$in": [a["from_id"], a["to_id"]]}}, {"tg_id": 1, "name": 1, "gender": 1},
    ).to_list(2)
    party_by_id = {p["tg_id"]: p for p in party_rows}
    from_label = titled_name(party_by_id.get(a["from_id"]), name=a["from_name"], gender=a.get("from_gender"))
    to_label = titled_name(party_by_id.get(a["to_id"]), name=a["to_name"], gender=a.get("to_gender"))

    if body.accept:
        await players.update_one({"tg_id": a["from_id"]}, {"$inc": {"alliance_count": 1, "stats.alliances_accepted": 1}})
        await players.update_one({"tg_id": a["to_id"]}, {"$inc": {"stats.alliances_accepted": 1}})
        await players.update_one({"tg_id": a["to_id"]}, {"$inc": {"alliance_count": 1}})
        await send_system_message(a["from_id"], a["from_name"], f"{to_label} پیشنهاد پیمانت را پذیرفت.", kind="diplomacy")
        # پیمان‌های عمومی (غیرخصوصی) به همهٔ لردها اطلاع داده می‌شود — نه فقط دو طرفِ پیمان
        if a.get("public", True):
            type_name = ALLIANCE_TYPES.get(a["type"], {}).get("name", a["type"])
            pact_name = f" («{a['name']}»)" if a.get("name") else ""
            text = f"📜 {type_name}{pact_name} میان {from_label} و {to_label} بسته شد."
            if a.get('group_id'):
                members = {a['from_name']}
                async for member in alliances.find({'group_id': a['group_id'], 'status': 'accepted'}):
                    members.add(member['to_name'])
                access_note = '\nاعضای این گروه مجوز تجارت و عبور کاروان با یکدیگر دارند.' if a['type'] in ('trade', 'full_alliance') else '\nشرایط عدم‌تجاوز و غرامت بین سازنده و هر عضو برقرار است.'
                text = f"📜 {to_label} به گروه {type_name}{pact_name} پیوست.\nاعضای پذیرفته‌شده: {'، '.join(sorted(members))}{access_note}"
            async for p in public_players():
                if p["tg_id"] not in (a["from_id"], a["to_id"]):
                    await send_system_message(p["tg_id"], p["name"], text, kind="diplomacy")
    else:
        proposer = await players.find_one({"tg_id": a["from_id"]})
        if proposer:
            add_resources(proposer, {"wine": a["wine_cost"]})
            await players.update_one({"tg_id": a["from_id"]}, {"$set": {"resources": proposer["resources"]}})
        await send_system_message(a["from_id"], a["from_name"], f"{to_label} پیشنهاد پیمانت را رد کرد — شرابت برگشت.", kind="diplomacy")
    return {"ok": True}

@router.post("/{alliance_id}/leave")
async def leave(alliance_id: str, user: dict = Depends(get_user)):
    from pact_exits import exit_pact
    return await exit_pact(alliance_id, departing=user['id'])

@router.post("/feast")
async def feast(user: dict = Depends(get_user)):
    from routers.rebellions import get_settings as get_rebellion_settings
    rebellion_settings = await get_rebellion_settings()
    feast_cost = {"food": int(rule("diplomacy.feast_food_cost", rebellion_settings["feast_food_cost"])), "wine": int(rule("diplomacy.feast_wine_cost", rebellion_settings["feast_wine_cost"]))}
    feast_gain = int(rule("diplomacy.feast_popularity_gain", rebellion_settings["feast_popularity_gain"]))
    p = await players.find_one({"tg_id": user["id"]})
    if not p:
        raise HTTPException(403, "اول ثبت‌نام کن")
    p = apply_production(p)

    last_feast = p.get("last_feast")
    if last_feast:
        if isinstance(last_feast, str):
            last_feast = datetime.fromisoformat(last_feast)
        if now() - last_feast < timedelta(hours=float(rule("diplomacy.feast_cooldown_hours", FEAST_COOLDOWN_HOURS))):
            raise HTTPException(400, "ضیافت را همین امروز برگزار کرده‌ای — فردا دوباره امتحان کن")

    if not can_afford(p["resources"], feast_cost):
        raise HTTPException(400, "شراب یا غذای کافی برای ضیافت نداری")
    pay(p["resources"], feast_cost)
    popularity = min(POPULARITY_MAX, p.get("popularity", 0) + feast_gain)

    fields = production_fields(p)
    fields.update({"popularity": popularity, "last_feast": now()})
    await players.update_one({"tg_id": user["id"]}, {"$set": fields})
    return {"ok": True, "popularity": popularity}
