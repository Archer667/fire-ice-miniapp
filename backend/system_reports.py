"""Persistent audit history; never included in game reset collections."""
import json, re
from datetime import datetime
from bson import ObjectId
from fastapi import APIRouter, Depends, HTTPException
from pydantic import BaseModel, StrictInt, Field
from db import db, players, game_settings
from auth import get_user, get_admin, get_full_admin, get_admin_role
from game import now
from ranks import current_week_start

CATEGORIES = ['sabotage','other','economy','diplomacy']
async def limits():
    row = await game_settings.find_one({'_id':'weekly_submission_limits'}) or {}
    return {k: row.get(k,v) for k,v in {'roleplays':3,'projects':1}.items()}

async def usage(uid, kind):
    start = current_week_start()
    collection = db.roleplays if kind == 'roleplays' else db.projects
    query = {'tg_id' if kind == 'roleplays' else 'owner_id':uid, 'created_at':{'$gte':start}}
    if kind == 'roleplays': query['category'] = {'$in': CATEGORIES}
    else: query['status'] = {'$ne':'invalid'}
    async for row in collection.find(query, {'_id':1,'created_at':1}):
        await db.submission_usage.update_one({'_id':kind+':'+str(row['_id'])},{'$setOnInsert':{'uid':uid,'kind':kind,'created_at':row['created_at']}},upsert=True)
    return await db.submission_usage.count_documents({'uid':uid,'kind':kind,'created_at':{'$gte':start}})

async def check_quota(uid, kind):
    maximum = (await limits())[kind]
    if await usage(uid,kind) >= maximum:
        raise HTTPException(429, f'سهمیهٔ هفتگی این بخش تمام شده است؛ سقف فعلی {maximum} درخواست در هفته است')

async def consume(uid,kind,identity):
    await db.submission_usage.update_one({'_id':kind+':'+str(identity)},{'$setOnInsert':{'uid':uid,'kind':kind,'created_at':now()}},upsert=True)

def clean(value):
    if isinstance(value,dict): return {k:('[حذف محتوای محرمانه/تصویر]' if any(x in k.lower() for x in ['token','secret','password','image','audio','authorization']) else clean(v)) for k,v in value.items()}
    if isinstance(value,list): return [clean(x) for x in value]
    if isinstance(value,str): return value[:6000]
    return value

async def snapshot():
    return {str(p['tg_id']):p async for p in players.find({}, {'_id':0,'tg_id':1,'name':1,'resources':1,'buildings':1,'castle_buildings':1,'castle':1,'region':1,'points':1,'stats':1,'is_dead':1,'registration_reset':1})}

async def begin_admin(request):
    if request.method in ('GET','HEAD','OPTIONS'): return None
    try:
        user = await get_user(request=request,authorization=request.headers.get('authorization',''),x_dev_user=request.headers.get('x-dev-user',''))
        role = await get_admin_role(user)
    except HTTPException: return None
    if not role: return None
    try: body = clean(await request.json())
    except (ValueError,UnicodeDecodeError): body = {}
    before = await snapshot()
    target = None
    match = re.search(r'/roleplay/([a-f0-9]{24})/',request.scope['path'])
    if match: target = await db.roleplays.find_one({'_id':ObjectId(match[1])},{'tg_id':1,'player_name':1,'category':1,'admin_score':1})
    row = {'at':datetime.utcnow(),'game_at':now(),'actor_id':user['id'],'actor_name':user.get('first_name',''),'role':role,'method':request.method,'path':request.scope['path'],'request':body,'roleplay':target,'status':'started'}
    result = await db.admin_activity.insert_one(row)
    return result.inserted_id,before

async def finish_admin(ticket,status):
    if not ticket: return
    identity,before=ticket
    after=await snapshot()
    changes=[{'tg_id':uid,'before':before.get(uid),'after':after.get(uid)} for uid in before.keys()|after.keys() if before.get(uid)!=after.get(uid)]
    await db.admin_activity.update_one({'_id':identity},{'$set':{'status':status,'changes':changes,'finished_at':datetime.utcnow()}})

async def market_start(buyer, source, resource, qty, price, seller=None):
    result=await db.market_history.insert_one({'at':datetime.utcnow(),'game_at':now(),'source':source,'buyer_id':buyer['tg_id'],'buyer_name':buyer.get('name',''),'seller_id':seller.get('seller_tg_id') if seller else None,'seller_name':seller.get('seller_name','') if seller else 'مدیریت','resource':resource,'qty':qty,'unit_price':price,'total':qty*price,'status':'started'})
    return result.inserted_id
async def market_done(identity):
    await db.market_history.update_one({'_id':identity},{'$set':{'status':'completed'}})

router=APIRouter(prefix='/api')
async def admin(user=Depends(get_user)): return await get_admin(user)
async def full(user=Depends(get_user)): return await get_full_admin(user)
class LimitsBody(BaseModel):
    roleplays: StrictInt = Field(ge=0,le=1000)
    projects: StrictInt = Field(ge=0,le=1000)
@router.get('/submission-limits')
async def read_limits(user=Depends(get_user)):
    return {**await limits(),'roleplays_used':await usage(user['id'],'roleplays'),'projects_used':await usage(user['id'],'projects'),'week_start':current_week_start()}
@router.post('/admin/submission-limits')
async def save_limits(body:LimitsBody,user=Depends(full)):
    await game_settings.update_one({'_id':'weekly_submission_limits'},{'$set':body.model_dump()},upsert=True)
    return await limits()
@router.get('/admin/reports/{kind}')
async def report(kind:str,user=Depends(full)):
    if kind not in ('admin-activity','market'): raise HTTPException(404)
    col = db.admin_activity if kind=='admin-activity' else db.market_history
    title='گزارش فعالیت ادمین‌ها' if kind=='admin-activity' else 'گزارش معاملات بازار'
    lines=[title,'این گزارش فقط سوابق ثبت‌شده از زمان فعال‌سازی گزارش‌گیری را شامل می‌شود.','زمان at میلادی UTC است؛ game_at زمان بازی است.','started یعنی عملیات آغاز شده و تکمیل آن تأیید نشده؛ completed یا کد 2xx یعنی تکمیل موفق.','']
    async for row in col.find({}).sort('at',1):
        lines += ['─'*45, 'زمان: '+str(row.get('at')), 'وضعیت: '+str(row.get('status'))]
        if kind == 'market':
            from game_data import TRADE_GOOD_NAMES
            lines += ['بازار: '+{'players':'بین بازیکنان','westeros':'وستروس','black':'بلک مارکت'}.get(row['source'],row['source']),
                      f"خریدار: {row['buyer_name']} | آیدی: {row['buyer_id']}", f"فروشنده: {row['seller_name']} | آیدی: {row.get('seller_id') or 'مدیریت'}",
                      'کالا: '+TRADE_GOOD_NAMES.get(row['resource'],row['resource']), f"حجم: {row['qty']} | قیمت واحد: {row['unit_price']} | مبلغ کل: {row['total']} سکه"]
        else:
            lines += [f"ادمین: {row['actor_name']} | آیدی: {row['actor_id']} | سطح: {row['role']}", f"اقدام: {row['method']} {row['path']}",
                      'جزئیات درخواست: '+json.dumps(row.get('request'),ensure_ascii=False,default=str),
                      'رول مرتبط: '+json.dumps(row.get('roleplay'),ensure_ascii=False,default=str),
                      'تغییرات قبل و بعد: '+json.dumps(row.get('changes',[]),ensure_ascii=False,default=str)]
            from game_data import TRADE_GOOD_NAMES
            for change in row.get('changes',[]):
                before,after=change.get('before') or {},change.get('after') or {}
                lines.append(f"بازیکن: {after.get('name') or before.get('name','')} | آیدی: {change['tg_id']}")
                old,new=before.get('resources',{}),after.get('resources',{})
                for resource in old.keys()|new.keys():
                    delta=new.get(resource,0)-old.get(resource,0)
                    if delta: lines.append(f"  {TRADE_GOOD_NAMES.get(resource,resource)}: {old.get(resource,0)} ← {new.get(resource,0)} | تغییر: {delta:+}")

    return {'filename':kind+'.txt','text':'\n'.join(lines)}
