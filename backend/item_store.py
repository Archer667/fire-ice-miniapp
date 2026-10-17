"""Escrowed item sales, real-time auctions and replay-safe settlement.

API requests and the auction watcher share the application's single-worker lock.
Every step commits its receipt atomically with its balance/inventory change.
"""
import hashlib
import json
from datetime import timedelta
from uuid import UUID

from bson import ObjectId
from fastapi import HTTPException
from db import db
import game_clock
from game import apply_production, production_fields
from item_effects import character_matches, campaign_for_grant, instant

listings = db.item_store_listings
operations = db.item_store_operations
DEFAULTS = {'enabled': True, 'currency': 'toman', 'toman_step': 50, 'gold_step': 10,
            'title': 'بازار گنجینه‌ها', 'description': 'آیتم‌های کمیاب خاندان‌ها؛ فروش مستقیم و مزایده'}
ACTIVE = ('preparing', 'open', 'pending')


def oid(value):
    try:
        return ObjectId(value)
    except Exception:
        raise HTTPException(400, 'شناسه معتبر نیست') from None


def person(p):
    return {'tg_id': p['tg_id'], 'name': p.get('name', ''), 'created_at': p.get('created_at'),
            'family_child_id': p.get('family_child_id')}


def same(p, identity):
    return bool(p and instant(p.get('created_at')) == instant(identity.get('created_at'))
                and p.get('family_child_id') == identity.get('family_child_id'))


async def player(uid):
    p = await db.players.find_one({'tg_id': uid})
    if not p or p.get('is_dead') or p.get('registration_reset'):
        raise HTTPException(403, 'کاراکتر فعال پیدا نشد')
    return p


async def settings():
    return {**DEFAULTS, **{k: v for k, v in (await db.game_settings.find_one({'_id': 'item_store'}) or {}).items() if k in DEFAULTS}}


async def available():
    cfg = await settings()
    if not cfg['enabled']:
        raise HTTPException(403, 'ثبت و خرید آگهی در فروشگاه موقتاً متوقف است')
    return cfg


def request_key(action, uid, request_id):
    try:
        key = str(UUID(request_id))
    except (ValueError, TypeError, AttributeError):
        raise HTTPException(400, 'شناسه درخواست معتبر نیست') from None
    return f'{action}:{uid}:{key}'


def step(collection, query, *, values=None, inc=None, unset=None, push=None):
    return {'collection': collection, 'query': query, 'set': values or {}, 'inc': inc or {},
            'unset': unset or {}, 'push': push or {}}


def wallet(p, amount):
    q = {'tg_id': p['tg_id'], 'created_at': p.get('created_at')}
    if amount < 0:
        q['resources.gold'] = {'$gte': -amount}
    return step('players', q, inc={'resources.gold': amount})


async def settle(p):
    p = apply_production(p)
    await db.players.update_one({'tg_id': p['tg_id'], 'created_at': p.get('created_at')}, {'$set': production_fields(p)})
    return p


async def finish(op):
    if op.get('complete'):
        return
    for index, change in enumerate(op['steps']):
        col = db[change['collection']]
        receipt = '_item_store_steps.' + hashlib.sha256(f'{op["_id"]}:{index}'.encode()).hexdigest()
        q = {**change['query'], receipt: {'$ne': True}}
        update = {'$set': {**change['set'], receipt: True}}
        for kind in ('inc', 'unset', 'push'):
            if change.get(kind):
                update['$' + kind] = change[kind]
        result = await col.update_one(q, update)
        if not result.matched_count:
            # Remove balance predicates when checking whether this exact step committed.
            receipt_query = {k: v for k, v in change['query'].items() if not k.startswith('resources.')}
            if not await col.find_one({**receipt_query, receipt: True}):
                await operations.update_one({'_id': op['_id']}, {'$set': {'last_error': 'step_conflict', 'failed_step': index}})
                raise HTTPException(409, 'تسویه فروشگاه نیازمند بررسی است؛ از تکرار خرید خودداری کن')
    await operations.update_one({'_id': op['_id']}, {'$set': {'complete': True, 'completed_at': game_clock.real_now()}})


async def execute(key, intent, steps):
    fingerprint = hashlib.sha256(json.dumps(intent, sort_keys=True, default=str).encode()).hexdigest()
    await operations.update_one({'_id': key}, {'$setOnInsert': {
        'fingerprint': fingerprint, 'intent': intent, 'steps': steps, 'complete': False,
        'real_at': game_clock.real_now(), 'game_at': game_clock.now()}}, upsert=True)
    op = await operations.find_one({'_id': key})
    if op['fingerprint'] != fingerprint:
        raise HTTPException(409, 'شناسه درخواست قبلاً برای عملیات دیگری استفاده شده است')
    await finish(op)


async def replay(key, intent):
    op = await operations.find_one({'_id': key})
    if not op:
        return False
    fingerprint = hashlib.sha256(json.dumps(intent, sort_keys=True, default=str).encode()).hexdigest()
    if op['fingerprint'] != fingerprint:
        raise HTTPException(409, 'این شناسه درخواست برای عملیات دیگری ثبت شده است')
    await finish(op)
    return True


async def recover():
    ready = True
    async for op in operations.find({'complete': False}).sort('real_at', 1):
        try:
            await finish(op)
        except HTTPException:
            ready = False
    return ready


def snapshot(tpl, grant):
    return {k: (grant.get('color', tpl.get('color', 'gray')) if k == 'color' else tpl.get(k))
            for k in ('name', 'type', 'description', 'image', 'color', 'building_id', 'yield_percent')}


async def create(uid, body, actor=None):
    cfg = await available()
    key = request_key('list', actor or uid, body.request_id)
    intent = {'seller_id': uid, **body.model_dump()}
    identity = hashlib.sha256(key.encode()).hexdigest()[:24]
    if await replay(key, intent):
        return identity
    p = await player(uid)
    grant = await db.item_grants.find_one({'_id': oid(body.grant_id), 'tg_id': uid})
    if not grant or not character_matches(grant, p):
        raise HTTPException(403, 'این آیتم متعلق به کاراکتر فعلی نیست')
    if grant.get('store_listing_id') or await campaign_for_grant(grant['_id']):
        raise HTTPException(409, 'آیتم در فروشگاه یا همراه لشکر است')
    if grant.get('expires_at') and instant(grant['expires_at']) <= game_clock.now():
        raise HTTPException(400, 'آیتم منقضی شده قابل فروش نیست')
    tpl = await db.items.find_one({'_id': grant['item_id']})
    if not tpl:
        raise HTTPException(404, 'آیتم پیدا نشد')
    p = await settle(p)
    listing = {'_id': oid(identity), 'grant_id': grant['_id'], 'item_id': grant['item_id'],
               'item': snapshot(tpl, grant), 'seller': person(p), 'seller_id': uid,
               'kind': body.kind, 'price': body.price, 'currency': cfg['currency'],
               'bid_step': cfg[cfg['currency'] + '_step'], 'bid_count': 0,
               'created_at': game_clock.real_now(), 'created_by': actor or uid,
               'ends_at': game_clock.real_now() + timedelta(hours=body.duration_hours) if body.kind == 'auction' else None,
               'expires_at': grant.get('expires_at'), 'status': 'preparing', 'version': 1}
    await listings.update_one({'_id': listing['_id']}, {'$setOnInsert': listing}, upsert=True)
    changes = [step('item_grants', {'_id': grant['_id'], 'tg_id': uid}, values={'store_listing_id': identity, 'effect_pending': False}),
               step('players', {'tg_id': uid, 'created_at': p.get('created_at')}, unset={f'item_effects.{grant["_id"]}': ''}),
               step('item_store_listings', {'_id': listing['_id']}, values={'status': 'open'})]
    await execute(key, intent, changes)
    return identity


async def get(identity):
    listing = await listings.find_one({'_id': oid(identity)})
    if not listing:
        raise HTTPException(404, 'آگهی پیدا نشد')
    return listing


async def purchase(uid, identity, body):
    await available()
    key = request_key('offer', uid, body.request_id)
    intent = {'listing': identity, 'buyer_id': uid, **body.model_dump()}
    if await replay(key, intent):
        return
    await tick()
    listing = await get(identity)
    if listing['status'] != 'open':
        raise HTTPException(409, 'این آگهی دیگر برای خرید باز نیست')
    if listing['version'] != body.version:
        raise HTTPException(409, 'قیمت یا پیشنهاد تغییر کرده؛ آگهی را دوباره دریافت کن')
    if uid == listing['seller_id']:
        raise HTTPException(400, 'امکان خرید یا پیشنهاد روی آیتم خودت وجود ندارد')
    p = await player(uid)
    seller = await db.players.find_one({'tg_id': listing['seller_id']})
    if not same(seller, listing['seller']) or seller.get('is_dead') or seller.get('registration_reset'):
        raise HTTPException(409, 'وضعیت فروشنده تغییر کرده؛ این آگهی نیازمند رسیدگی است')
    amount = body.amount
    prior = listing.get('highest')
    if listing['kind'] == 'fixed':
        if amount != listing['price']:
            raise HTTPException(409, 'مبلغ خرید با قیمت آگهی یکسان نیست')
    else:
        minimum = prior['amount'] + listing['bid_step'] if prior else listing['price']
        if amount < minimum or (amount - listing['price']) % listing['bid_step']:
            raise HTTPException(400, f'پیشنهاد باید حداقل {minimum} و با گام {listing["bid_step"]} باشد')
    changes = []
    if listing['currency'] == 'gold':
        p = await settle(p)
        debit = amount - (prior['amount'] if prior and prior['person']['tg_id'] == uid else 0)
        if p.get('resources', {}).get('gold', 0) < debit:
            raise HTTPException(400, 'سکه کافی برای این پیشنهاد نداری')
        changes.append(wallet(p, -debit))
        if prior and prior['person']['tg_id'] != uid:
            previous = await db.players.find_one({'tg_id': prior['person']['tg_id']})
            if not previous:
                raise HTTPException(409, 'بازگشت وجه پیشنهاد قبلی نیازمند رسیدگی ادمین است')
            previous = await settle(previous)
            changes.append(wallet(previous, prior['amount']))
    offer = {'person': person(p), 'amount': amount, 'at': game_clock.real_now()}
    update = {'highest': offer, 'version': listing['version'] + 1}
    if listing['kind'] == 'fixed':
        update.update(status='pending', pending_at=game_clock.real_now())
    changes.append(step('item_store_listings', {'_id': listing['_id']}, values=update,
                        inc={'bid_count': 1}, push={'bid_history': {'$each': [offer], '$slice': -100}}))
    await execute(key, intent, changes)


async def close(listing, status, actor=None, reason=''):
    if listing['status'] not in ACTIVE:
        return
    changes = []
    offer = listing.get('highest')
    if offer and listing['currency'] == 'gold':
        payer = await db.players.find_one({'tg_id': offer['person']['tg_id']})
        if not payer:
            raise HTTPException(409, 'شخصیت خریدار تغییر کرده؛ بازگشت وجه باید بررسی شود')
        changes.append(wallet(await settle(payer), offer['amount']))
    grant = await db.item_grants.find_one({'_id': listing['grant_id']})
    if grant and grant.get('store_listing_id') == str(listing['_id']):
        changes.append(step('item_grants', {'_id': grant['_id']}, unset={'store_listing_id': ''}))
        seller = await db.players.find_one({'tg_id': listing['seller_id']})
        if same(seller, listing['seller']) and character_matches(grant, seller) and not seller.get('is_dead'):
            seller = await settle(seller)
            effect = grant.get('effect')
            if effect:
                effect = {**effect, 'starts_at': game_clock.now()}
                changes.append(step('players', {'tg_id': seller['tg_id'], 'created_at': seller.get('created_at')}, values={f'item_effects.{grant["_id"]}': effect}))
    changes.append(step('item_store_listings', {'_id': listing['_id']}, values={
        'status': status, 'closed_at': game_clock.real_now(), 'closed_by': actor,
        'reason': reason[:500], 'version': listing['version'] + 1}))
    await execute(f'close:{listing["_id"]}', {'status': status, 'actor': actor, 'reason': reason[:500]}, changes)


async def approve(listing, actor):
    if listing['status'] == 'sold':
        return
    if listing['status'] != 'pending' or not listing.get('highest'):
        raise HTTPException(409, 'این خرید منتظر تأیید نیست')
    offer = listing['highest']
    buyer = await player(offer['person']['tg_id'])
    seller = await db.players.find_one({'tg_id': listing['seller_id']})
    if not same(buyer, offer['person']) or not same(seller, listing['seller']):
        raise HTTPException(409, 'کاراکتر یکی از طرفین تغییر کرده؛ خرید را رد و وضعیت حساب را بررسی کن')
    grant = await db.item_grants.find_one({'_id': listing['grant_id'], 'store_listing_id': str(listing['_id'])})
    if not grant:
        raise HTTPException(409, 'آیتم رزروشده پیدا نشد؛ خرید را بررسی کن')
    if grant.get('expires_at') and instant(grant['expires_at']) <= game_clock.now():
        raise HTTPException(409, 'آیتم منقضی شده؛ خرید را رد کن تا وجه برگردد')
    buyer = await settle(buyer)
    effect = grant.get('effect')
    if effect:
        effect = {**effect, 'starts_at': game_clock.now(), 'character_created_at': buyer.get('created_at'),
                  'character_child_id': buyer.get('family_child_id')}
    changes = [step('item_grants', {'_id': grant['_id']}, values={
        'tg_id': buyer['tg_id'], 'character_created_at': buyer.get('created_at'),
        'character_child_id': buyer.get('family_child_id'), 'effect': effect,
        'effect_pending': False, 'transferred_at': game_clock.now(), 'store_sale_id': str(listing['_id'])}, unset={'store_listing_id': ''})]
    if effect:
        changes.append(step('players', {'tg_id': buyer['tg_id'], 'created_at': buyer.get('created_at')}, values={f'item_effects.{grant["_id"]}': effect}))
    if listing['currency'] == 'gold':
        changes.append(wallet(await settle(seller), offer['amount']))
    changes.append(step('item_store_listings', {'_id': listing['_id']}, values={
        'status': 'sold', 'approved_by': actor, 'closed_at': game_clock.real_now(), 'version': listing['version'] + 1}))
    await execute(f'approve:{listing["_id"]}', {'listing': str(listing['_id'])}, changes)


async def tick():
    if not await recover():
        return
    async for listing in listings.find({'status': 'open'}):
        try:
            if listing.get('expires_at') and instant(listing['expires_at']) <= game_clock.now():
                await close(listing, 'expired', reason='اعتبار آیتم پایان یافت')
            elif listing['kind'] == 'auction' and instant(listing['ends_at']) <= game_clock.real_now():
                if listing.get('highest'):
                    await execute(f'end:{listing["_id"]}', {'listing': str(listing['_id'])}, [step(
                        'item_store_listings', {'_id': listing['_id']}, values={'status': 'pending',
                            'pending_at': game_clock.real_now(), 'version': listing['version'] + 1})])
                else:
                    await close(listing, 'unsold', reason='مزایده بدون پیشنهاد پایان یافت')
        except HTTPException as exc:
            # One invalid legacy account must not interrupt army/food watchers.
            await listings.update_one({'_id': listing['_id']}, {'$set': {'review_error': exc.detail}})


def view(row, uid, admin=False):
    own = row['seller_id'] == uid
    highest = row.get('highest')
    result = {k: row.get(k) for k in ('kind', 'price', 'currency', 'bid_step', 'bid_count', 'ends_at', 'created_at', 'status', 'version', 'item', 'expires_at', 'reason')}
    result.update(id=str(row['_id']), seller_name=row['seller']['name'], mine=own,
                  highest_amount=highest['amount'] if highest else None,
                  my_offer=bool(highest and highest['person']['tg_id'] == uid),
                  minimum_offer=(highest['amount'] + row['bid_step']) if highest else row['price'])
    if admin or own or result['my_offer']:
        result['buyer_name'] = highest['person']['name'] if highest else None
    if admin:
        result.update(seller=row['seller'], highest=highest, approved_by=row.get('approved_by'),
                      closed_by=row.get('closed_by'), bid_history=row.get('bid_history', []), review_error=row.get('review_error'))
    return result
