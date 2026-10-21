"""Player contracts and private castle life. All calls use game_state_lock.

Escrow uses the existing durable family intents and per-character wallet receipts.
News is explicitly submitted/editor-approved; private gameplay is never harvested.
"""
from datetime import timedelta
from uuid import uuid4, UUID
from typing import Literal
from fastapi import APIRouter, Depends, HTTPException, Query
from pydantic import BaseModel, Field, StrictInt
from auth import get_user, get_full_admin
from db import db, players
from game import now
import game_clock
import character_travel as travel
from family import key, member_for, commit, change, recover
from text_limits import check_text
from admin_notifications import notify_admins

router = APIRouter(prefix='/api')
news_router = APIRouter(prefix='/api')  # Included only in the browser edition.
contracts = db.world_contracts
entries = db.castle_life
articles = db.world_news
DEFAULTS = {'enabled': True, 'max_open_contracts': 10, 'max_duration_days': 30}
STATES = {'open':'پذیرش داوطلب','active':'در حال انجام','submitted':'منتظر تأیید نتیجه','disputed':'در انتظار داوری','completed':'تسویه‌شده','cancelled':'لغوشده','expired':'منقضی'}

async def admin(user=Depends(get_user)):
    return await get_full_admin(user)

async def person(user):
    from auth import get_admin_role
    if await get_admin_role(user):
        raise HTTPException(403, 'این بخش برای کاراکترهای بازیکنان است')
    return await travel.living(user['id'])

async def config():
    row = await db.game_settings.find_one({'_id':'social_world'}) or {}
    return {**DEFAULTS, **{k:row[k] for k in DEFAULTS if k in row}}

def clean(row):
    return {('id' if k=='_id' else k):v for k,v in row.items() if k!='_id' or v is not None}

async def text(value, category='request_words'):
    value = value.strip()
    if not value: raise HTTPException(400, 'متن را وارد کنید')
    await check_text(value, category)
    return value

async def live_snapshot(snapshot):
    p = await players.find_one({'tg_id':snapshot['tg_id']})
    return bool(p and p.get('created_at')==snapshot['character_created_at'] and not p.get('is_dead') and not p.get('registration_reset') and (p.get('castle') or p.get('landless')))

def note(ident, recipients, message):
    return {'event':'world:'+ident, 'recipients':list(set(recipients)), 'text':message}

async def transition(row, fields, actor, wallets=None):
    revision=row['version']+1
    fields={**fields,'version':revision,'updated_at':now()}
    audit={'_id':f"contract:{row['_id']}:{revision}", 'kind':'contract','record':row['_id'],'actor':actor,'at':now(),'from_status':row['status'],'to_status':fields.get('status',row['status'])}
    recipients=[row['owner']['tg_id']]+([row['worker']['tg_id']] if row.get('worker') else [])
    await commit({'_id':audit['_id'],'complete':False,'wallets':wallets or [],'changes':[
        change('world_contracts',{'_id':row['_id']},fields),
        {'collection':'social_audit','query':{'_id':audit['_id']},'update':{'$setOnInsert':audit},'upsert':True}],
        'notices':[note(audit['_id'],recipients,'وضعیت عهدنامهٔ «'+row['title']+'»: '+STATES.get(fields.get('status',row['status']),row['status']))]})
    if fields.get('status')=='disputed':
        await notify_admins('world_contract','عهدنامه منتظر داوری است',row['title'],dedupe_key=audit['_id'],source_id=row['_id'],action='سیاست و محتوا ← عهدنامه‌ها و داوری',audience_roles=('owner','full'))

async def close(row, status, actor, reason):
    await transition(row, {'status':status,'resolution':reason,'escrow':0,'closed_at':now()},actor,
                     [{'member':row['owner'],'cost':{'gold':row['reward']}}] if row.get('escrow') else [])

async def tick():
    await recover()
    if game_clock.paused(): return
    async for row in contracts.find({'status':{'$in':['open','active','submitted','disputed']}}):
        if not await live_snapshot(row['owner']) or (row.get('worker') and not await live_snapshot(row['worker'])):
            await close(row,'cancelled',0,'با پایان زندگی یا تغییر کاراکتر یکی از طرفین، پاداش به صاحب اصلی آن بازگردانده شد.')
        elif row['deadline']<=now() and row['status']=='open':
            await close(row,'expired',0,'مهلت پذیرش داوطلب پایان یافت و پاداش بازگردانده شد.')
        elif row['deadline']<=now() and row['status']=='active':
            await transition(row,{'status':'disputed','dispute_reason':'مهلت انجام قرارداد پایان یافته است.'},0)

def contract_view(row, character=None, management=False):
    result=clean(row)
    private=management or character==row['owner_key'] or character==row.get('worker_key')
    result['owner']={'name':row['owner']['name']}
    result['worker']={'name':row['worker']['name']} if row.get('worker') else None
    if not private:
        for field in ('result','dispute_reason','resolution','review_note'):
            result.pop(field,None)
    applicants=row.get('applicants',[])
    result['applicants']=[{'key':a['key'],'name':a['name'],'message':a['message']} for a in applicants if management or character==row['owner_key'] or character==a['key']]
    result['applicant_count']=len(applicants)
    result['is_owner']=character==row['owner_key']
    result['is_worker']=character==row.get('worker_key')
    result.pop('owner_key',None);result.pop('worker_key',None)
    return result

class ContractDraft(BaseModel):
    request_id:UUID
    title:str=Field(min_length=3,max_length=100)
    description:str=Field(min_length=3,max_length=500000)
    kind:Literal['trade','military','personal']='personal'
    place:str=Field(min_length=2,max_length=150)
    reward:StrictInt=Field(ge=1,le=1000000000)
    duration_days:StrictInt=Field(ge=1,le=365)

@router.get('/contracts')
async def board(limit:int=Query(60,ge=1,le=100), before:str='', mine:bool=False,user=Depends(get_user)):
    p=await person(user);await tick()
    query={} if not mine else {'$or':[{'owner_key':key(p)},{'worker_key':key(p)},{'applicants.key':key(p)}]}
    if not mine:query['status']={'$in':['open','active','submitted','disputed']}
    if before:
        pivot=await contracts.find_one({'_id':before})
        if not pivot:raise HTTPException(400,'نشان صفحه معتبر نیست')
        query={'$and':[query,{'$or':[{'created_at':{'$lt':pivot['created_at']}},{'created_at':pivot['created_at'],'_id':{'$lt':before}}]}]}
    rows=[r async for r in contracts.find(query).sort([('created_at',-1),('_id',-1)]).limit(limit+1)]
    return {'contracts':[contract_view(r,key(p)) for r in rows[:limit]],'next':rows[limit-1]['_id'] if len(rows)>limit else None,'settings':await config(),'game_now':now(),'paused':game_clock.paused()}

@router.post('/contracts')
async def create_contract(body:ContractDraft,user=Depends(get_user)):
    p=await person(user);await tick();cfg=await config()
    title=await text(body.title);description=await text(body.description)
    ident='c:'+str(body.request_id)
    old=await contracts.find_one({'_id':ident})
    payload={'title':title,'description':description,'kind':body.kind,'place':body.place.strip(),'reward':body.reward,'duration_days':body.duration_days}
    if old:
        if old['owner_key']!=key(p) or any(old.get(k)!=v for k,v in payload.items()):raise HTTPException(409,'شناسهٔ این عهدنامه قبلاً استفاده شده است')
        return contract_view(old,key(p))
    if not cfg['enabled']:raise HTTPException(403,'ثبت عهدنامهٔ تازه موقتاً بسته است')
    if body.duration_days>cfg['max_duration_days']:raise HTTPException(400,'مهلت از سقف مجاز قرارداد بیشتر است')
    if await contracts.count_documents({'owner_key':key(p),'status':{'$in':['open','active','submitted','disputed']}})>=cfg['max_open_contracts']:
        raise HTTPException(400,'تعداد قراردادهای باز شما به سقف مجاز رسیده است')
    row={'_id':ident,**payload,'owner':member_for(p,0),'owner_key':key(p),'worker':None,'applicants':[],
         'status':'open','version':1,'escrow':body.reward,'created_at':now(),'deadline':now()+timedelta(days=body.duration_days)}
    await commit({'_id':'contract-create:'+ident,'complete':False,'wallets':[{'member':row['owner'],'cost':{'gold':body.reward},'debit':True}],
        'changes':[{'collection':'world_contracts','query':{'_id':ident},'update':{'$setOnInsert':row},'upsert':True}]})
    return contract_view(row,key(p))

class ContractAction(BaseModel):
    action:Literal['apply','assign','submit','approve','dispute','cancel','return','refund']
    version:StrictInt=Field(ge=1)
    applicant:str=Field(default='',max_length=200)
    message:str=Field(default='',max_length=500000)

async def act_contract(ident,body,actor,p=None,management=False):
    await tick()
    row=await contracts.find_one({'_id':ident})
    if not row:raise HTTPException(404,'عهدنامه پیدا نشد')
    if row['version']!=body.version:raise HTTPException(409,'پرونده تغییر کرده است؛ اطلاعات را تازه کنید')
    own=p and key(p)==row['owner_key'];worker=p and key(p)==row.get('worker_key')
    action=body.action;fields={}
    if action=='apply':
        if management or own or row['status']!='open':raise HTTPException(403,'امکان درخواست همکاری برای این عهدنامه وجود ندارد')
        if any(a['key']==key(p) for a in row['applicants']):raise HTTPException(409,'درخواست همکاری شما قبلاً ثبت شده است')
        if len(row['applicants'])>=100:raise HTTPException(400,'ظرفیت درخواست‌های این عهدنامه تکمیل است')
        message=await text(body.message)
        fields={'applicants':row['applicants']+[{'key':key(p),'name':p['name'],'member':member_for(p,0),'message':message}]}
    elif action=='assign':
        if not(own or management) or row['status']!='open':raise HTTPException(403,'انتخاب طرف قرارداد در این وضعیت مجاز نیست')
        applicant=next((a for a in row['applicants'] if a['key']==body.applicant),None)
        if not applicant or not await live_snapshot(applicant['member']):raise HTTPException(409,'کاراکتر داوطلب دیگر در دسترس نیست')
        fields={'worker':applicant['member'],'worker_key':applicant['key'],'status':'active','started_at':now(),'deadline':now()+timedelta(days=row['duration_days'])}
    elif action=='submit':
        if not worker or row['status']!='active':raise HTTPException(403,'فقط طرف قرارداد فعال می‌تواند نتیجه بدهد')
        fields={'result':await text(body.message,'scenario_words'),'status':'submitted','submitted_at':now()}
    elif action=='approve':
        if not(own or management) or row['status'] not in (['submitted','disputed'] if management else ['submitted']):raise HTTPException(403,'تسویهٔ این عهدنامه مجاز نیست')
        if not row.get('worker') or not await live_snapshot(row['worker']):raise HTTPException(409,'طرف قرارداد تغییر کرده است')
        await transition(row,{'status':'completed','escrow':0,'closed_at':now(),'resolution':body.message.strip() or 'نتیجه تأیید و پاداش پرداخت شد.'},actor,
            [{'member':row['worker'],'cost':{'gold':row['reward']}}]);return {'ok':True}
    elif action=='cancel':
        if not(own or management) or (row['status']!='open' and not(management and row['status'] in ['active','submitted','disputed'])):raise HTTPException(403,'قرارداد شروع‌شده فقط با داوری قابل لغو است')
        await close(row,'cancelled',actor,body.message.strip() or 'عهدنامه لغو و پاداش بازگردانده شد.');return {'ok':True}
    elif action=='dispute':
        if not(own or worker or management) or row['status'] not in ['active','submitted']:raise HTTPException(403,'امکان ارجاع این پرونده وجود ندارد')
        fields={'status':'disputed','dispute_reason':await text(body.message)}
    elif action=='return':
        if not(own or management) or row['status'] not in (['submitted','disputed'] if management else ['submitted']):raise HTTPException(403,'برگشت نتیجه مجاز نیست')
        fields={'status':'active','review_note':await text(body.message),'deadline':now()+timedelta(days=row['duration_days'])}
    elif action=='refund':
        if not management or row['status'] not in ['active','submitted','disputed']:raise HTTPException(403,'استرداد نیازمند داوری مدیریت است')
        await close(row,'cancelled',actor,await text(body.message));return {'ok':True}
    await transition(row,fields,actor)
    if action=='assign':
        from family import notice
        await notice('world-assigned:'+ident+':'+str(row['version']),[fields['worker']['tg_id']],'برای انجام عهدنامهٔ «'+row['title']+'» انتخاب شدید.')
    return {'ok':True}

@router.post('/contracts/{ident}/action')
async def contract_action(ident:str,body:ContractAction,user=Depends(get_user)):
    return await act_contract(ident,body,user['id'],await person(user))

@router.get('/admin/social/contracts')
async def admin_contracts(status:str='',user=Depends(admin)):
    await tick()
    rows=[r async for r in contracts.find({'status':status} if status else {}).sort('created_at',-1).limit(150)]
    return {'contracts':[contract_view(r,management=True) for r in rows],'settings':await config()}

@router.post('/admin/social/contracts/{ident}/action')
async def admin_contract_action(ident:str,body:ContractAction,user=Depends(admin)):
    return await act_contract(ident,body,user['id'],management=True)

class Settings(BaseModel):
    enabled:bool=True
    max_open_contracts:StrictInt=Field(ge=1,le=100)
    max_duration_days:StrictInt=Field(ge=1,le=365)

@router.post('/admin/social/settings')
async def settings_save(body:Settings,user=Depends(admin)):
    await db.game_settings.update_one({'_id':'social_world'},{'$set':body.model_dump()},upsert=True)
    return {'ok':True}

async def location_context(p,place='',management=False):
    await travel.tick();s=await travel.state(p) if p else {}
    place=place or s.get('place')
    if not place:raise HTTPException(409,'برای ورود به تالار باید در یک مکان اقامت داشته باشید')
    dest=await travel.destination(place)
    groups=await travel.gates(dest)
    host_ids={uid for group in groups.values() for uid in group}
    is_host=management or bool(p and p['tg_id'] in host_ids)
    if not is_host and (s.get('place')!=place or s.get('trip')):raise HTTPException(403,'این تالار فقط برای حاضران و میزبانان همان مکان است')
    return place,dest,s,is_host,host_ids

async def residents(place):
    result=[]
    async for s in travel.locations.find({'place':place,'trip':None,'inactive':{'$ne':True}}):
        if s.get('tg_id'):
            p=await players.find_one({'tg_id':s['tg_id']})
            if not p or key(p)!=s['_id'] or p.get('is_dead') or p.get('registration_reset'):continue
        elif s.get('child_id'):
            if not await db.family_children.find_one({'_id':s['child_id'],'status':'alive'}):continue
        else:continue
        result.append({'key':s['_id'],'name':s['name'],'child':bool(s.get('child_id')),'captive':bool(s.get('captive'))})
    return result

def entry_view(row,p=None,management=False):
    result=clean(row)
    result['mine']=bool(p and row['author_key']==key(p))
    result['joined']=bool(p and key(p) in row.get('attendees',[]))
    result['attendee_count']=len(row.get('attendees',[]))
    if not management:result.pop('attendees',None)
    return result

@router.get('/castle-life')
async def castle_view(place:str='',user=Depends(get_user)):
    p=await person(user)
    place,dest,s,is_host,host_ids=await location_context(p,place)
    rows=[r async for r in entries.find({'place':place,'removed':{'$ne':True}}).sort('created_at',-1).limit(150)
          if r['kind']!='meeting' or key(p) in (r['author_key'],r.get('target_key'))]
    arrivals=[travel.clean(r) async for r in travel.trips.find({'target':place,'status':'pending'}).sort('created_at',-1).limit(100)] if is_host else []
    # Origins and family lists are needed only in the existing travel management UI.
    arrivals=[{k:r[k] for k in ('id','name','status','target') if k in r} for r in arrivals]
    present=await residents(place)
    present_keys={r['key'] for r in present}
    hosts=[]
    for uid in sorted(host_ids):
        lord=await players.find_one({'tg_id':uid})
        if lord:hosts.append(lord['name'])
    arrived=[{'name':r['name'],'at':r['arrival_at']} async for r in travel.trips.find({'target':place,'status':'arrived'}).sort('arrival_at',-1).limit(20) if r['character'] in present_keys]
    return {'place':place,'name':dest['name'],'is_host':is_host,'state':travel.clean(s),'residents':present,'hosts':hosts,'arrivals_log':arrived,
            'entries':[entry_view(r,p) for r in rows],'arrivals':arrivals,'blocked':await travel.blocked(place),'paused':game_clock.paused(),'game_now':now()}

class EntryDraft(BaseModel):
    request_id:UUID
    place:str=Field(default='',max_length=150)
    kind:Literal['notice','event','meeting']
    title:str=Field(min_length=3,max_length=100)
    body:str=Field(min_length=3,max_length=500000)
    target_key:str=Field(default='',max_length=200)
    starts_in_hours:StrictInt=Field(default=24,ge=1,le=720)

@router.post('/castle-life')
async def entry_create(body:EntryDraft,user=Depends(get_user)):
    p=await person(user);place,dest,s,is_host,hosts=await location_context(p,body.place)
    ident=str(body.request_id);old=await entries.find_one({'_id':ident})
    title=await text(body.title);content=await text(body.body)
    payload={'place':place,'kind':body.kind,'title':title,'body':content,'target_key':body.target_key,'starts_in_hours':body.starts_in_hours}
    if old:
        if old['author_key']!=key(p) or any(old.get(k)!=v for k,v in payload.items()):raise HTTPException(409,'شناسه قبلاً استفاده شده است')
        return entry_view(old,p)
    if body.kind in ('notice','event') and not is_host:raise HTTPException(403,'ثبت اعلامیه و رویداد به میزبان تعلق دارد')
    recipients=set(hosts)
    if body.kind!='meeting':
        for resident in await residents(place):
            loc=await travel.locations.find_one({'_id':resident['key']})
            if loc and loc.get('tg_id'):recipients.add(loc['tg_id'])
    if body.kind=='meeting':
        if s.get('place')!=place or s.get('trip') or s.get('captive'):raise HTTPException(403,'درخواست ملاقات به حضور آزاد در این مکان نیاز دارد')
        current=await residents(place)
        target=next((r for r in current if r['key']==body.target_key and not r['child'] and not r['captive']),None)
        if not target or body.target_key==key(p):raise HTTPException(400,'یکی از کاراکترهای حاضر و آزاد دیگر را انتخاب کنید')
        # Identity is resolved from a current location row, never trusted from a form.
        target_location=await travel.locations.find_one({'_id':body.target_key})
        recipients={target_location['tg_id']}
    if await entries.count_documents({'author_key':key(p),'created_at':{'$gte':now()-timedelta(days=1)}})>=20:
        raise HTTPException(429,'سقف ثبت روزانهٔ تالار پر شده است')
    row={'_id':ident,**payload,'author_key':key(p),'author_name':p['name'],'created_at':now(),'status':'pending' if body.kind=='meeting' else 'published',
         'starts_at':now()+timedelta(hours=body.starts_in_hours),'attendees':[],'version':1}
    await commit({'_id':'castle-entry:'+ident,'complete':False,'changes':[{'collection':'castle_life','query':{'_id':ident},'update':{'$setOnInsert':row},'upsert':True}],
        'notices':[note('castle-entry:'+ident,recipients,('درخواست ملاقات: ' if body.kind=='meeting' else 'تازه در تالار '+dest['name']+': ')+title)]})
    return entry_view(row,p)

class EntryAction(BaseModel):
    version:StrictInt=Field(ge=1)
    action:Literal['join','leave','accept','reject','remove','cancel']

@router.post('/castle-life/{ident}/action')
async def entry_action(ident:str,body:EntryAction,user=Depends(get_user)):
    p=await person(user);row=await entries.find_one({'_id':ident,'removed':{'$ne':True}})
    if not row:raise HTTPException(404,'این نوشته در تالار نیست')
    place,dest,s,is_host,hosts=await location_context(p,row['place'])
    if body.version!=row['version']:raise HTTPException(409,'اطلاعات تغییر کرده است؛ صفحه را تازه کنید')
    action=body.action;updates={'version':row['version']+1}
    if action in ('join','leave'):
        if row['kind']!='event' or row['status']!='published' or row['starts_at']<=now():raise HTTPException(409,'ثبت حضور این رویداد بسته است')
        if s.get('place')!=place or s.get('trip') or s.get('captive'):raise HTTPException(403,'شرکت در رویداد به حضور آزاد در قلعه نیاز دارد')
        attendees=set(row.get('attendees',[]))
        if action=='join':attendees.add(key(p))
        else:attendees.discard(key(p))
        updates['attendees']=sorted(attendees)
    elif action in ('accept','reject'):
        if row['kind']!='meeting' or row['target_key']!=key(p) or row['status']!='pending':raise HTTPException(403,'پاسخ این ملاقات فقط در اختیار دریافت‌کننده است')
        if s.get('place')!=place or s.get('trip') or s.get('captive'):raise HTTPException(409,'ملاقات به حضور آزاد در همین مکان نیاز دارد')
        author=await travel.locations.find_one({'_id':row['author_key'],'place':place,'trip':None,'inactive':{'$ne':True}})
        if not author or author.get('captive'):raise HTTPException(409,'درخواست‌کننده دیگر در این مکان آزاد و حاضر نیست')
        updates['status']='accepted' if action=='accept' else 'rejected'
    elif action=='cancel':
        if row['author_key']!=key(p):raise HTTPException(403,'فقط نویسنده می‌تواند درخواست خود را لغو کند')
        updates['status']='cancelled';updates['removed']=True
    elif action=='remove':
        if not is_host or row['kind']=='meeting':raise HTTPException(403,'حذف نوشتهٔ عمومی در اختیار میزبان است')
        updates['removed']=True
    notices=[]
    if action in ('accept','reject'):
        author=await travel.locations.find_one({'_id':row['author_key']})
        if author and author.get('tg_id'):
            notices=[note('meeting-response:'+ident+':'+str(body.version),[author['tg_id']], 'پاسخ درخواست ملاقات «'+row['title']+'»: '+('پذیرفته شد' if action=='accept' else 'پذیرفته نشد'))]
    await commit({'_id':'castle-action:'+ident+':'+str(body.version),'complete':False,
                  'changes':[change('castle_life',{'_id':ident},updates)],'notices':notices})
    return {'ok':True}

@router.get('/admin/social/castles')
async def admin_castles(place:str='',user=Depends(admin)):
    if not place:
        return {'places':sorted(travel.TRAVEL_GRAPH)+[r['_id'] async for r in travel.places.find({'enabled':True})]}
    await location_context(None,place,True)
    return {'entries':[entry_view(r,management=True) async for r in entries.find({'place':place}).sort('created_at',-1).limit(150)],'residents':await residents(place)}

class RemoveEntry(BaseModel):
    reason:str=Field(min_length=3,max_length=1000)

@router.post('/admin/social/castles/{ident}/remove')
async def admin_remove(ident:str,body:RemoveEntry,user=Depends(admin)):
    row=await entries.find_one({'_id':ident})
    if not row:raise HTTPException(404,'نوشته پیدا نشد')
    await entries.update_one({'_id':ident},{'$set':{'removed':True,'removed_by':user['id'],'remove_reason':body.reason}})
    return {'ok':True}

class NewsDraft(BaseModel):
    request_id:UUID
    title:str=Field(min_length=3,max_length=120)
    body:str=Field(min_length=5,max_length=500000)
    category:Literal['official','realm','rumor']='realm'
    source:str=Field(min_length=2,max_length=250)
    image:Literal['port','citadel','watch','faith','bank','golden-company','alchemists','none']='none'

@news_router.get('/newspaper')
async def news_list(before:str='',user=Depends(get_user)):
    p=await person(user)
    query={'status':'published'}
    if before:
        pivot=await articles.find_one({'_id':before})
        if not pivot:raise HTTPException(400,'نشان صفحه معتبر نیست')
        query={'$and':[query,{'$or':[{'published_at':{'$lt':pivot.get('published_at',now())}},{'published_at':pivot.get('published_at'),'_id':{'$lt':before}}]}]}
    rows=[r async for r in articles.find(query).sort([('published_at',-1),('_id',-1)]).limit(31)]
    mine=[clean(r) async for r in articles.find({'author_key':key(p)}).sort('created_at',-1).limit(30)]
    # Draft author account IDs never appear in the public edition.
    public=[]
    for r in rows[:30]:
        public.append({k:r[k] for k in ('title','body','category','source','image','published_at','issue') if k in r}|{'id':r['_id']})
    return {'articles':public,'mine':mine,'next':rows[29]['_id'] if len(rows)>30 else None}

async def news_create(body,user,management=False):
    p=None if management else await person(user)
    author='admin:'+str(user['id']) if management else key(p)
    ident='n:'+str(body.request_id)
    title=await text(body.title);content=await text(body.body,'scenario_words')
    payload={**body.model_dump(exclude={'request_id'}),'title':title,'body':content}
    old=await articles.find_one({'_id':ident})
    if old:
        if old['author_key']!=author or any(old.get(k)!=v for k,v in payload.items()):raise HTTPException(409,'شناسه قبلاً استفاده شده است')
        return clean(old)
    if not management and await articles.count_documents({'author_key':author,'status':'pending'})>=5:raise HTTPException(429,'پنج خبر در انتظار بررسی دارید')
    row={'_id':ident,**payload,'author_key':author,'author_name':p['name'] if p else 'تحریریه','status':'pending','version':1,'created_at':now()}
    await articles.insert_one(row)
    await notify_admins('world_news','خبر تازه برای تحریریه',title,dedupe_key='news:'+ident,source_id=ident,action='سیاست و محتوا ← تحریریهٔ روزنامه',audience_roles=('owner','full'))
    return clean(row)

@news_router.post('/newspaper')
async def submit_news(body:NewsDraft,user=Depends(get_user)):
    return await news_create(body,user)

@news_router.get('/admin/social/news')
async def admin_news(user=Depends(admin)):
    return {'articles':[clean(r) async for r in articles.find({}).sort('created_at',-1).limit(150)]}

@news_router.post('/admin/social/news')
async def admin_write_news(body:NewsDraft,user=Depends(admin)):
    return await news_create(body,user,True)

class NewsReview(BaseModel):
    version:StrictInt=Field(ge=1)
    action:Literal['publish','reject','unpublish']
    title:str=Field(default='',max_length=120)
    body:str=Field(default='',max_length=500000)
    category:Literal['official','realm','rumor']='realm'
    source:str=Field(default='',max_length=250)
    image:Literal['port','citadel','watch','faith','bank','golden-company','alchemists','none']='none'
    issue:StrictInt=Field(default=1,ge=1,le=1000000)
    note:str=Field(default='',max_length=1000)

@news_router.post('/admin/social/news/{ident}/review')
async def review_news(ident:str,body:NewsReview,user=Depends(admin)):
    row=await articles.find_one({'_id':ident})
    if not row:raise HTTPException(404,'خبر پیدا نشد')
    if row['version']!=body.version:raise HTTPException(409,'خبر تغییر کرده است؛ صفحه را تازه کنید')
    updates={'status':{'publish':'published','reject':'rejected','unpublish':'withdrawn'}[body.action],'version':row['version']+1,'reviewer':user['id'],'review_note':body.note,'reviewed_at':now()}
    if body.action=='publish':
        updates.update(title=await text(body.title),body=await text(body.body,'scenario_words'),category=body.category,source=body.source.strip(),image=body.image,issue=body.issue,published_at=now())
        if not updates['source']:raise HTTPException(400,'منبع خبر را مشخص کنید')
    await articles.update_one({'_id':ident,'version':body.version},{'$set':updates})
    await db.social_audit.insert_one({'kind':'news','record':ident,'actor':user['id'],'action':body.action,'at':now()})
    return {'ok':True}

async def ensure_indexes():
    await contracts.create_index([('status',1),('created_at',-1)])
    await contracts.create_index('owner_key')
    await entries.create_index([('place',1),('created_at',-1)])
    await articles.create_index([('status',1),('created_at',-1)])
