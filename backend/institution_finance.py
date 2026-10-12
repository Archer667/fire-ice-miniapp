"""Durable, replay-safe resource transfers for institution services."""
import hashlib
from fastapi import HTTPException
from db import db, players
from game import apply_production, production_fields
import game_clock
from institution_bank import matches

operations=db.institution_transfers
treasuries=db.institution_service_treasuries
RESOURCE_NAMES={'gold':'طلا','wood':'چوب','stone':'سنگ','iron':'آهن','food':'غلات','wine':'شراب','men':'نیروی انسانی'}

def amounts(values):
    if any(k not in RESOURCE_NAMES or type(v) is not int or v<0 or v>10**9 for k,v in values.items()):
        raise HTTPException(400,'نوع یا مقدار منابع معتبر نیست')
    return {k:v for k,v in values.items() if v}

async def balance(person):
    row=await players.find_one({'tg_id':person['tg_id']})
    if not matches(row,person):raise HTTPException(409,'کاراکتر طرف پرداخت تغییر کرده؛ رسیدگی ادمین لازم است')
    row=apply_production(row)
    await players.update_one({'tg_id':row['tg_id'],'created_at':row['created_at']},{'$set':production_fields(row)})
    return row.get('resources',{})

async def enough(person,values):
    res=await balance(person)
    if any(res.get(k,0)<v for k,v in values.items()):raise HTTPException(400,'موجودی منابع برای این درخواست کافی نیست')

async def leg_once(leg,key):
    receipt='institution_transfer_receipts.'+hashlib.sha256(key.encode()).hexdigest()
    if leg['kind']=='player':
        collection=players; query={'tg_id':leg['person']['tg_id'],'created_at':leg['person']['created_at']}
        row=await collection.find_one(query)
        if not matches(row,leg['person']):raise HTTPException(409,'کاراکتر طرف انتقال تغییر کرده است')
    else:
        collection=treasuries; query={'_id':leg['treasury']}
        await collection.update_one(query,{'$setOnInsert':{'resources':{}}},upsert=True)
        row=await collection.find_one(query)
    if row.get('institution_transfer_receipts',{}).get(receipt.split('.')[1]):return
    query[receipt]={'$ne':True}
    for k,v in leg['values'].items():
        if v<0:query['resources.'+k]={'$gte':-v}
    inc={'resources.'+k:v for k,v in leg['values'].items()}
    result=await collection.update_one(query,{'$inc':inc,'$set':{receipt:True}})
    if not result.matched_count:raise HTTPException(409,'موجودی تغییر کرده یا برای انتقال کافی نیست')

async def finish(op):
    if op.get('aborted'):raise HTTPException(409,'این عملیات ناموفق بسته شده؛ درخواست تازه ثبت کن')
    if op.get('complete'):return
    for i,leg in enumerate(op['legs']):await leg_once(leg,f"{op['_id']}:{i}")
    for effect in op.get('effects',[]):
        collection=db[effect['collection']]
        if effect.get('insert'):
            await collection.update_one({'_id':effect['id']},{'$setOnInsert':effect['insert']},upsert=True)
        else:await collection.update_one({'_id':effect['id']},{'$set':effect['set']})
    await operations.update_one({'_id':op['_id']},{'$set':{'complete':True,'completed_at':game_clock.real_now()}})

async def transfer(key,legs,effects=None,**details):
    targets={(e['collection'],str(e['id'])) for e in (effects or [])}
    async for pending in operations.find({'complete':{'$ne':True},'aborted':{'$ne':True},'_id':{'$ne':key}}):
        if targets.intersection((e['collection'],str(e['id'])) for e in pending.get('effects',[])):
            raise HTTPException(409,'عملیات قبلی این حساب ناتمام است؛ رسیدگی ادمین لازم است')
    row={'_id':key,'legs':legs,'effects':effects or [],'real_at':game_clock.real_now(),'game_at':game_clock.now(),'complete':False,**details}
    await operations.update_one({'_id':key},{'$setOnInsert':row},upsert=True)
    saved=await operations.find_one({'_id':key})
    if saved.get('aborted'):raise HTTPException(409,'این عملیات ناموفق بود؛ درخواست تازه ثبت کن')
    try:await finish(saved)
    except HTTPException as exc:
        await operations.update_one({'_id':key},{'$set':{'error':exc.detail}})
        # Only an uncommitted first debit may be abandoned. Committed transfers
        # remain pending and recover before subsequent requests.
        first=saved['legs'][0] if saved['legs'] else None
        if first and any(v<0 for v in first['values'].values()):
            source=await (players.find_one({'tg_id':first['person']['tg_id']}) if first['kind']=='player' else treasuries.find_one({'_id':first['treasury']}))
            receipt=hashlib.sha256((key+':0').encode()).hexdigest()
            if not (source or {}).get('institution_transfer_receipts',{}).get(receipt):
                await operations.update_one({'_id':key},{'$set':{'aborted':True}})
        raise
    return await operations.find_one({'_id':key})

def player_leg(person,values):return {'kind':'player','person':person,'values':values}
def treasury_leg(key,values):return {'kind':'treasury','treasury':key,'values':values}
def effect(collection,key,values):return {'collection':collection,'id':key,'set':values}

async def recover():
    async for row in operations.find({'complete':{'$ne':True},'aborted':{'$ne':True}}):
        try:await finish(row)
        except HTTPException as exc:await operations.update_one({'_id':row['_id']},{'$set':{'error':exc.detail}})

async def ensure_indexes():
    await operations.create_index([('institution',1),('real_at',-1)])
    await operations.create_index([('complete',1),('aborted',1)])
