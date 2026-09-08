from datetime import datetime, timedelta, timezone
from uuid import UUID
import hashlib
import json
from fastapi import APIRouter, Depends, HTTPException
from pydantic import BaseModel, Field, StrictInt
from pymongo.errors import DuplicateKeyError
from auth import get_user, get_admin_role, get_full_admin
from db import players, admin_roles
from config import ADMIN_IDS, OWNER_ID
from game import now
from project_engine import (
    projects, project_lock, RESOURCES, TERMS, member_for, scaled, recover,
    tick_project, fail_project, finish_purchase, settle, public_project,
    announcement, queue_notice,
)

router = APIRouter(prefix='/api/projects', tags=['projects'])


async def manager(user=Depends(get_user)):
    return await get_full_admin(user)


async def living_player(user):
    p = await players.find_one({'tg_id': user['id']})
    if not p or p.get('is_dead') or not p.get('castle') or not p.get('region') or await get_admin_role(user):
        raise HTTPException(403, 'فقط بازیکن زنده و خاندان‌دار می‌تواند پروژه بسازد یا سهم بخرد')
    return p


def clean_key(raw):
    try:
        return str(UUID(raw))
    except (ValueError, TypeError, AttributeError):
        raise HTTPException(400, 'شناسهٔ درخواست نامعتبر است')


def validate_basket(values):
    if not values or any(k not in RESOURCES or v < 0 or v > 1_000_000_000 for k, v in values.items()) or not any(values.values()):
        raise HTTPException(400, 'حداقل یک مقدار مثبت از منابع مجاز وارد کن؛ مقادیر منفی مجاز نیستند')
    return {k: v for k, v in values.items() if v}


class Proposal(BaseModel):
    request_id: str
    kind: str = 'shared'
    name: str = Field(min_length=3, max_length=80)
    goal: str = Field(min_length=10, max_length=250)
    description: str = Field(min_length=20, max_length=600)
    budget: dict[str, StrictInt]
    total_shares: StrictInt = Field(ge=1, le=10000)
    owner_shares: StrictInt = Field(ge=1, le=10000)
    period_return: dict[str, StrictInt]
    period_hours: StrictInt = Field(ge=1, le=720)
    period_count: StrictInt = Field(ge=1, le=365)
    accepted_terms: bool


@router.get('/rules')
async def rules(user=Depends(get_user)):
    return {'terms': TERMS, 'resources': RESOURCES, 'server_time': now()}


@router.post('')
async def submit(body: Proposal, user=Depends(get_user)):
    p = await living_player(user)
    pid = clean_key(body.request_id)
    budget, output = validate_basket(body.budget), validate_basket(body.period_return)
    if not body.accepted_terms:
        raise HTTPException(400, 'شرایط سرمایه‌گذاری را بخوان و بپذیر')
    if body.kind not in ('personal', 'shared'):
        raise HTTPException(400, 'نوع پروژه نامعتبر است')
    if body.owner_shares > body.total_shares or (body.kind == 'personal') != (body.owner_shares == body.total_shares):
        raise HTTPException(400, 'پروژهٔ شخصی تمام سهام را برای طراح دارد؛ پروژهٔ مشترک باید سهم قابل عرضه داشته باشد')
    if any(v % body.total_shares for v in budget.values()):
        raise HTTPException(400, 'هر منبع بودجه باید بر تعداد کل سهام بخش‌پذیر باشد تا بهای هر سهم عدد صحیح شود')
    if not all(s.strip() for s in (body.name, body.goal, body.description)):
        raise HTTPException(400, 'نام، هدف و توضیح نمی‌توانند خالی باشند')
    fingerprint = hashlib.sha256(json.dumps(body.model_dump(), sort_keys=True).encode()).hexdigest()
    async with project_lock:
        from system_reports import check_quota, consume
        if not await projects.find_one({'_id':pid}):
            await check_quota(user['id'], 'projects')
        doc = {**body.model_dump(exclude={'request_id', 'accepted_terms'}), '_id': pid,
               'name': body.name.strip(), 'goal': body.goal.strip(), 'description': body.description.strip(),
               'budget': budget, 'period_return': output, 'owner_id': p['tg_id'], 'owner_name': p['name'],
               'status': 'reserving', 'created_at': now(), 'paid_periods': 0,
               'share_cost': {k: v // body.total_shares for k, v in budget.items()},
               'sold_shares': body.owner_shares, 'members': {str(p['tg_id']): member_for(p, body.owner_shares)},
               'notification_terms': TERMS, 'terms_accepted_at': now(), 'request_fingerprint': fingerprint}
        try:
            await projects.insert_one(doc)
        except DuplicateKeyError:
            doc = await projects.find_one({'_id': pid})
            if doc['owner_id'] != p['tg_id'] or doc['request_fingerprint'] != fingerprint:
                raise HTTPException(409, 'شناسهٔ درخواست برای طرح دیگری استفاده شده است')
        if doc['status'] == 'invalid':
            raise HTTPException(400, doc.get('reason', 'ثبت پروژه ناموفق بود؛ درخواست تازه بفرست'))
        doc = await recover(doc)
        if doc['status'] != 'invalid':
            await consume(user['id'], 'projects', pid)
        if doc['status'] == 'pending':
            admins = set(ADMIN_IDS) | {a['tg_id'] async for a in admin_roles.find({'role': {'$in': ['owner', 'full']}})}
            if OWNER_ID:
                admins.add(OWNER_ID)
            await queue_notice(doc, 'submitted', list(admins), f"📜 پروژهٔ «{doc['name']}» از {p['name']} منتظر بررسی است.\nپنل ادمین ← پروژه‌ها")
        return public_project(doc, p['tg_id'])


@router.get('')
async def listing(mine: bool = False, user=Depends(get_user)):
    async with project_lock:
        result = []
        async for p in projects.find({'status': {'$ne': 'invalid'}}).sort('created_at', -1):
            p = await tick_project(p)
            involved = p['owner_id'] == user['id'] or str(user['id']) in p['members']
            public = p['kind'] == 'shared' and p.get('publish_at') and now() >= p['publish_at'] and p['status'] != 'pending'
            if (mine and involved) or (not mine and (involved or public)):
                result.append(public_project(p, user['id']))
        return result


class Purchase(BaseModel):
    request_id: str
    shares: StrictInt = Field(ge=1, le=10000)


@router.post('/{project_id}/buy')
async def buy(project_id: str, body: Purchase, user=Depends(get_user)):
    p = await living_player(user)
    key = clean_key(body.request_id)
    async with project_lock:
        doc = await projects.find_one({'_id': project_id})
        if not doc:
            raise HTTPException(404, 'پروژه پیدا نشد')
        doc = await tick_project(doc)
        if doc['owner_id'] == p['tg_id']:
            raise HTTPException(403, 'طراح نمی‌تواند سهام پروژهٔ خودش را بخرد')
        if key in doc.get('purchase_keys', []):
            # Receipt identity is scoped to the buyer, not just the caller's UUID.
            member = doc['members'].get(str(p['tg_id']))
            from project_engine import receipt_key
            wallet = await players.find_one({'tg_id': p['tg_id']})
            if not member or not wallet.get('project_receipts', {}).get(receipt_key(f'{project_id}:buy:{key}')):
                raise HTTPException(409, 'شناسهٔ خرید متعلق به درخواست دیگری است')
            return public_project(doc, p['tg_id'])
        if doc['status'] != 'funding' or now() < doc['publish_at'] or now() >= doc['funding_deadline']:
            raise HTTPException(409, 'خرید سهام این پروژه اکنون باز نیست')
        held = doc['members'].get(str(p['tg_id']), {})
        if held and held['character_created_at'] != p['created_at']:
            raise HTTPException(409, 'سهام شخصیت قبلی در این پروژه ثبت شده است')
        if body.shares > doc['total_shares'] - doc['sold_shares']:
            raise HTTPException(409, 'این تعداد سهم باقی نمانده است؛ فهرست را تازه کن')
        limit = doc.get('max_shares_per_player')
        if limit and held.get('shares', 0) + body.shares > limit:
            raise HTTPException(400, f'سقف مجموع خرید تو در این پروژه {limit} سهم است')
        await projects.update_one({'_id': project_id}, {'$set': {'purchase_intent': {
            'key': key, 'member': member_for(p, body.shares), 'cost': scaled(doc['share_cost'], body.shares), 'accepted_at': now(),
        }}})
        doc = await finish_purchase(await projects.find_one({'_id': project_id}))
        return public_project(doc, p['tg_id'])


@router.get('/admin/list')
async def admin_list(user=Depends(manager)):
    async with project_lock:
        out = []
        async for doc in projects.find({'status': {'$ne': 'invalid'}}).sort('created_at', -1):
            doc = await tick_project(doc)
            out.append({**public_project(doc, user['id']), 'members': list(doc['members'].values())})
        return out


class Approval(BaseModel):
    publish_at: datetime
    funding_hours: StrictInt = Field(ge=1, le=720)
    max_shares_per_player: StrictInt | None = Field(default=None, ge=1, le=10000)
    reason: str = Field(min_length=3, max_length=500)
    notification_terms: str = Field(default=TERMS, min_length=10, max_length=1000)


@router.post('/admin/{project_id}/approve')
async def approve(project_id: str, body: Approval, user=Depends(manager)):
    if body.publish_at.tzinfo is None:
        raise HTTPException(400, 'زمان عرضه باید منطقهٔ زمانی داشته باشد')
    stamp = body.publish_at.astimezone(timezone.utc).replace(tzinfo=None)
    if stamp < now():
        raise HTTPException(400, 'زمان عرضه باید در آینده باشد')
    async with project_lock:
        doc = await projects.find_one({'_id': project_id})
        if not doc:
            raise HTTPException(404, 'پروژه پیدا نشد')
        doc = await tick_project(doc)
        if doc['status'] != 'pending':
            raise HTTPException(409, 'فقط درخواست در انتظار بررسی قابل تأیید است')
        updates = {'status': 'scheduled', 'publish_at': stamp, 'funding_hours': body.funding_hours,
                   'funding_deadline': stamp + timedelta(hours=body.funding_hours),
                   'max_shares_per_player': body.max_shares_per_player, 'reason': body.reason.strip(),
                   'notification_terms': body.notification_terms.strip(), 'approved_by': user['id'], 'approved_at': now()}
        if len(updates['reason']) < 3 or len(updates['notification_terms']) < 10:
            raise HTTPException(400, 'دلیل و متن شرایط را کامل بنویس')
        doc.update(updates)
        text = announcement(doc)
        if len(text) > 3900:
            raise HTTPException(400, 'متن اعلان طولانی است؛ شرایط اعلان را کوتاه‌تر کن')
        await projects.update_one({'_id': project_id}, {'$set': updates})
        excluded = set(ADMIN_IDS) | {a['tg_id'] async for a in admin_roles.find({})} | {OWNER_ID}
        recipients = [p['tg_id'] async for p in players.find({'castle': {'$ne': None}, 'is_dead': {'$ne': True}})
                      if p['tg_id'] not in excluded]
        if doc['kind'] == 'shared':
            from admin_notifications import _admin_ids
            recipients = list(set(recipients) | await _admin_ids())
        await queue_notice(doc, 'approved', recipients if doc['kind'] == 'shared' else [doc['owner_id']], text)
        return public_project(doc, user['id'])


class Decision(BaseModel):
    reason: str = Field(min_length=3, max_length=500)


@router.post('/admin/{project_id}/reject')
async def reject(project_id: str, body: Decision, user=Depends(manager)):
    if len(body.reason.strip()) < 3:
        raise HTTPException(400, 'دلیل تصمیم را کامل بنویس')
    async with project_lock:
        doc = await projects.find_one({'_id': project_id})
        if not doc:
            raise HTTPException(404, 'پروژه پیدا نشد')
        doc = await tick_project(doc)
        if doc['status'] != 'pending':
            raise HTTPException(409, 'فقط درخواست در انتظار بررسی قابل رد است')
        amounts = {k: scaled(doc['share_cost'], m['shares']) for k, m in doc['members'].items()}
        doc = await settle(doc, 'rejected_refund', amounts, {'status': 'rejected', 'reason': body.reason,
            'decided_by': user['id'], 'ended_at': now()},
            f"📜 درخواست پروژهٔ «{doc['name']}» رد شد.\nدلیل: {body.reason}\nتمام آوردهٔ رزروشده‌ات بازگردانده شد.")
        return public_project(doc, user['id'])


@router.post('/admin/{project_id}/fail')
async def fail(project_id: str, body: Decision, user=Depends(manager)):
    if len(body.reason.strip()) < 3:
        raise HTTPException(400, 'دلیل تصمیم را کامل بنویس')
    async with project_lock:
        doc = await projects.find_one({'_id': project_id})
        if not doc or doc['status'] != 'active':
            raise HTTPException(409, 'فقط پروژهٔ در حال اجرا را می‌توان شکست‌خورده اعلام کرد')
        doc = await fail_project(doc, body.reason, user['id'])
        return public_project(doc, user['id'])
