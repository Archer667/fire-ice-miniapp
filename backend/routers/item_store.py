from typing import Literal
from fastapi import APIRouter, Depends, HTTPException, Query
from pydantic import BaseModel, Field, StrictInt
from auth import get_user, get_full_admin
from db import db
import item_store as engine

router = APIRouter(prefix='/api', tags=['item-store'])


async def full(user=Depends(get_user)):
    return await get_full_admin(user)


class ListingBody(BaseModel):
    grant_id: str
    kind: Literal['fixed', 'auction']
    price: StrictInt = Field(ge=1, le=10**12)
    duration_hours: StrictInt = Field(default=24, ge=1, le=720)
    request_id: str


class OfferBody(BaseModel):
    amount: StrictInt = Field(ge=1, le=10**12)
    version: StrictInt = Field(ge=1)
    request_id: str


class SettingsBody(BaseModel):
    enabled: bool
    currency: Literal['toman', 'gold']
    toman_step: StrictInt = Field(ge=1, le=10**10)
    gold_step: StrictInt = Field(ge=1, le=10**10)
    title: str = Field(min_length=1, max_length=60)
    description: str = Field(max_length=300)


class DecisionBody(BaseModel):
    action: Literal['approve', 'reject', 'cancel']
    reason: str = Field(default='', max_length=500)
    payment_confirmed: bool = False


class EditBody(BaseModel):
    price: StrictInt = Field(ge=1, le=10**12)
    duration_hours: StrictInt = Field(ge=1, le=720)


async def ready():
    if not await engine.recover():
        raise HTTPException(409, 'یک تسویه فروشگاه نیازمند رسیدگی است؛ لطفاً با پشتیبانی تماس بگیر')


@router.get('/item-store')
async def index(scope: Literal['market', 'mine'] = 'market', offset: int = Query(default=0, ge=0),
                user=Depends(get_user)):
    await engine.tick()
    query = {'status': 'open'} if scope == 'market' else {'$or': [
        {'seller_id': user['id']}, {'highest.person.tg_id': user['id']}, {'bid_history.person.tg_id': user['id']}]}
    records = await engine.listings.find(query).sort('created_at', -1).skip(offset).limit(41).to_list(41)
    return {'settings': await engine.settings(), 'rows': [engine.view(r, user['id']) for r in records[:40]],
            'has_more': len(records) > 40, 'real_now': engine.game_clock.real_now().isoformat() + 'Z'}


@router.post('/item-store')
async def create(body: ListingBody, user=Depends(get_user)):
    await ready()
    return {'ok': True, 'id': await engine.create(user['id'], body)}


@router.post('/item-store/{identity}/offer')
async def offer(identity: str, body: OfferBody, user=Depends(get_user)):
    await ready()
    await engine.purchase(user['id'], identity, body)
    return {'ok': True}


@router.post('/item-store/{identity}/cancel')
async def cancel(identity: str, user=Depends(get_user)):
    await ready()
    await engine.tick()
    row = await engine.get(identity)
    if row['seller_id'] != user['id']:
        raise HTTPException(403, 'فقط فروشنده می‌تواند آگهی خودش را لغو کند')
    if row['status'] != 'open' or row.get('highest'):
        raise HTTPException(409, 'آگهی دارای پیشنهاد یا خرید در انتظار بررسی، فقط با رسیدگی پشتیبانی لغو می‌شود')
    await engine.close(row, 'cancelled', user['id'], 'لغو توسط فروشنده')
    return {'ok': True}


@router.get('/admin/item-store')
async def admin_index(offset: int = Query(default=0, ge=0), status: str = 'all', user=Depends(full)):
    await engine.tick()
    allowed = ('all', 'preparing', 'open', 'pending', 'sold', 'cancelled', 'rejected', 'unsold', 'expired')
    if status not in allowed:
        raise HTTPException(400, 'وضعیت آگهی معتبر نیست')
    records = await engine.listings.find({} if status == 'all' else {'status': status}).sort('created_at', -1).skip(offset).limit(61).to_list(61)
    pending = await engine.listings.count_documents({'status': 'pending'})
    unsettled = await engine.operations.find({'complete': False}).limit(100).to_list(100)
    return {'settings': await engine.settings(), 'pending_count': pending,
            'unsettled': [{'id': r['_id'], 'listing_id': r.get('intent', {}).get('listing'),
                          'real_at': r.get('real_at')} for r in unsettled],
            'rows': [engine.view(r, user['id'], True) for r in records[:60]], 'has_more': len(records) > 60,
            'real_now': engine.game_clock.real_now().isoformat() + 'Z'}


@router.post('/admin/item-store/recover')
async def recover(user=Depends(full)):
    return {'ready': await engine.recover()}


@router.put('/admin/item-store/settings')
async def save_settings(body: SettingsBody, user=Depends(full)):
    values = body.model_dump()
    values['title'] = values['title'].strip()
    if not values['title']:
        raise HTTPException(400, 'عنوان فروشگاه را بنویس')
    await db.game_settings.update_one({'_id': 'item_store'}, {'$set': {**values,
        'changed_by': user['id'], 'changed_at': engine.game_clock.real_now()}}, upsert=True)
    return await engine.settings()


@router.get('/admin/item-store/inventory/{uid}')
async def admin_inventory(uid: int, user=Depends(full)):
    from routers.assets import my_items
    return await my_items({'id': uid})


@router.post('/admin/item-store/inventory/{uid}')
async def admin_create(uid: int, body: ListingBody, user=Depends(full)):
    await ready()
    return {'ok': True, 'id': await engine.create(uid, body, actor=user['id'])}


@router.put('/admin/item-store/{identity}')
async def edit(identity: str, body: EditBody, user=Depends(full)):
    await ready()
    await engine.tick()
    row = await engine.get(identity)
    if row['status'] != 'open' or row.get('highest'):
        raise HTTPException(409, 'اصلاح قیمت فقط پیش از ثبت اولین پیشنهاد یا خرید ممکن است')
    await engine.listings.update_one({'_id': row['_id'], 'status': 'open', 'version': row['version']}, {'$set': {
        'price': body.price, 'ends_at': engine.game_clock.real_now() + engine.timedelta(hours=body.duration_hours) if row['kind'] == 'auction' else None,
        'edited_by': user['id'], 'edited_at': engine.game_clock.real_now()}, '$inc': {'version': 1}})
    return {'ok': True}


@router.post('/admin/item-store/{identity}/decision')
async def decision(identity: str, body: DecisionBody, user=Depends(full)):
    await ready()
    await engine.tick()
    row = await engine.get(identity)
    if body.action == 'approve':
        if row['currency'] == 'toman' and not body.payment_confirmed:
            raise HTTPException(400, 'تأیید دریافت وجه تومانی لازم است')
        await engine.approve(row, user['id'])
    else:
        if row['status'] not in engine.ACTIVE:
            if row['status'] in ('rejected', 'cancelled'):
                return {'ok': True}
            raise HTTPException(409, 'این آگهی بسته شده است')
        if not body.reason.strip():
            raise HTTPException(400, 'دلیل رد یا حذف آگهی را بنویس')
        await engine.close(row, 'rejected' if body.action == 'reject' else 'cancelled', user['id'], body.reason)
    return {'ok': True}
