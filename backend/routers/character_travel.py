from uuid import UUID, uuid4
from typing import Literal
from fastapi import APIRouter, Depends, HTTPException
from pydantic import BaseModel, Field, StrictBool
from auth import get_user, get_full_admin, get_admin_role
from db import db, players
from game import now
from family import key, commit, change
import character_travel as engine

router=APIRouter(prefix='/api')
async def admin(user=Depends(get_user)):
    return await get_full_admin(user)

class Journey(BaseModel):
    target:str=Field(max_length=150)
    children:list[str]=Field(default_factory=list,max_length=100)
    request_id:UUID

@router.get('/character-travel')
async def view(user=Depends(get_user)):
    return await engine.view(await engine.living(user['id']))

@router.post('/character-travel/requests')
async def request(body:Journey,user=Depends(get_user)):
    return await engine.request(await engine.living(user['id']),body.target,body.children,str(body.request_id))

class Response(BaseModel):
    id:str=Field(max_length=200)
    accept:StrictBool
@router.post('/character-travel/respond')
async def respond(body:Response,user=Depends(get_user)):
    await engine.living(user['id'])
    return await engine.respond(user['id'],body.id,body.accept)

class GuestAction(BaseModel):
    subject:str=Field(max_length=200)
    reason:str=Field(default='',max_length=1000)
@router.post('/character-travel/capture')
async def capture(body:GuestAction,user=Depends(get_user)):
    await engine.living(user['id'])
    return await engine.capture_request(user['id'],body.subject,body.reason)

@router.post('/character-travel/release')
async def release(body:GuestAction,user=Depends(get_user)):
    await engine.living(user['id'])
    return await engine.release(body.subject,user['id'])

@router.post('/character-travel/expel')
async def expel(body:GuestAction,user=Depends(get_user)):
    await engine.living(user['id'])
    s=await engine.locations.find_one({'_id':body.subject})
    if not s or not s.get('tg_id'):raise HTTPException(400,'اخراج را برای کاراکتر بزرگسال ثبت کن')
    await engine.host(user['id'],s)
    if s.get('captive'):raise HTTPException(400,'ابتدا مهمان را از اسارت آزاد کن')
    expulsion_id=str(uuid4())
    await engine.locations.update_one({'_id':body.subject},{'$set':{'expulsion':{'host_id':user['id'],'at':now(),'reason':body.reason,'id':expulsion_id,'pending':True}}})
    if not s.get('previous') or await engine.blocked(s['place']) or await engine.blocked(s['previous']):
        return {'ok':True,'message':'اخراج ثبت شد؛ منتظر پایان درگیری یا تعیین مقصد مجاز است.'}
    p=await engine.living(s['tg_id'])
    ids=[c['child_id'] for c in await engine.kids(p,s) if c['available']]
    result=await engine.request(p,s['previous'],ids,expulsion_id,forced=True,settle=False)
    await engine.locations.update_one({'_id':body.subject},{'$set':{'expulsion.pending':False}})
    return result

@router.get('/admin/character-travel')
async def management(user=Depends(admin)):
    await engine.tick()
    from config import ADMIN_IDS, OWNER_ID
    admin_ids=set(ADMIN_IDS)
    if OWNER_ID is not None:admin_ids.add(OWNER_ID)
    async for row in db.admin_roles.find({'role':{'$in':['owner','full','limited','war_roleplay']}}):admin_ids.add(row['tg_id'])
    people=[]
    async for p in players.find({}, {'profile_image':0,'backstory':0,'flag_image':0,'flag_map_image':0,'resources':0,'buildings':0,'castle_buildings':0}).sort('name',1):
        if p['tg_id'] in admin_ids:continue
        people.append({'character_key':key(p),**{k:v for k,v in p.items() if k in ('tg_id','name','created_at','castle','landless','is_dead','registration_reset','region','registration_mode','points','stats','medals','profile_image','backstory','death_reason')}})
    archived=[]
    async for a in db.character_archives.find({}).sort('died_at',-1):
        archived.append({k:v for k,v in a.items() if k in ('name','tg_id','created_at','died_at','points','stats','medals','death_reason','archive_id')})
    return {'players':people,'archives':archived,'locations':[engine.clean(s) async for s in engine.locations.find({})],
        'trips':[engine.clean(t) async for t in engine.trips.find({'status':{'$in':['pending','travelling','held']}})],
        'captures':[engine.clean(c) async for c in engine.captures.find({'status':'pending'})],
        'places':[engine.clean(d) async for d in engine.places.find({})], 'nodes':sorted(engine.TRAVEL_GRAPH),'institutions':engine.INSTITUTIONS}

class Place(BaseModel):
    institution:Literal['iron-bank','citadel','golden-company','alchemists','faceless','faith','watch']|None=None
    name:str=Field(min_length=2,max_length=100)
    node:str=Field(max_length=100)
    enabled:StrictBool=True
@router.post('/admin/character-travel/places')
async def place(body:Place,user=Depends(admin)):
    if body.node not in engine.TRAVEL_GRAPH:raise HTTPException(400,'مقر یا شهر باید به یکی از نقاط نقشه متصل شود')
    ident='institution:'+body.institution if body.institution else 'city:'+body.name
    old=await engine.places.find_one({'_id':ident})
    if old and (old['node']!=body.node or not body.enabled):
        if await engine.locations.find_one({'place':ident}) or await engine.trips.find_one({'target':ident,'status':{'$in':['pending','travelling','held']}}):
            raise HTTPException(409,'ابتدا مهمانان و سفرهای این مقر را تعیین تکلیف کن')
    await engine.places.update_one({'_id':ident},{'$set':{**body.model_dump(),'kind':'institution' if body.institution else 'city'}},upsert=True)
    return {'ok':True}

@router.post('/admin/character-travel/captures')
async def review(body:Response,user=Depends(admin)):
    return await engine.review_capture(body.id,body.accept,user['id'])

class Control(BaseModel):
    subject:str=Field(max_length=200)
    action:Literal['move','release','capture','cancel','hold','resume','cancel-request']
    target:str=Field(default='',max_length=150)
@router.post('/admin/character-travel/control')
async def control(body:Control,user=Depends(admin)):
    if body.action=='release':return await engine.release(body.subject,user['id'],True)
    if body.action=='cancel-request':
        await engine.trips.update_one({'_id':body.subject,'status':'pending'},{'$set':{'status':'cancelled'}})
        return {'ok':True}
    s=await engine.locations.find_one({'_id':body.subject})
    if not s:raise HTTPException(404,'محل کاراکتر پیدا نشد؛ ابتدا بازیکن را از فهرست انتخاب کن')
    if body.action=='capture':
        if not s.get('place') or s.get('trip'):raise HTTPException(400,'ابتدا محل حضور فرد را مشخص کن')
        if s.get('captive'):raise HTTPException(409,'این فرد هم‌اکنون اسیر است')
        groups=await engine.gates(await engine.destination(s['place']))
        host_id=next((uid for group in groups.values() for uid in group),user['id'])
        await engine.locations.update_one({'_id':s['_id']},{'$set':{'captive':{'host_id':host_id,'admin_id':user['id'],'at':now()}}})
        return {'ok':True}
    trip=await engine.trips.find_one({'_id':s['trip']}) if s.get('trip') else None
    if body.action in ('hold','resume'):
        if not trip or trip['status'] not in ('travelling','held'):raise HTTPException(409,'سفر فعال پیدا نشد')
        if (body.action=='hold' and trip['status']=='held') or (body.action=='resume' and trip['status']!='held'):raise HTTPException(409,'وضعیت سفر تغییر کرده است')
        fields={'status':'held','held_at':now()} if body.action=='hold' else {'status':'travelling','started_at':trip['started_at']+(now()-trip['held_at']),'arrival_at':trip['arrival_at']+(now()-trip['held_at'])}
        await engine.trips.update_one({'_id':trip['_id']},{'$set':fields})
        return {'ok':True}
    target=body.target or (trip['origin'] if trip else s.get('place'))
    await engine.destination(target)
    ids=[trip['character']]+['child:'+c for c in trip['children']] if trip else [s['_id']]
    changes=[change('character_locations',{'_id':i},{'place':target,'trip':None}) for i in ids]
    if trip:changes.append(change('character_trips',{'_id':trip['_id']},{'status':'cancelled'}))
    await commit({'_id':'travel-admin:'+str(uuid4()),'complete':False,'changes':changes})
    return {'ok':True}

class PlayerAction(BaseModel):
    action:Literal['revive','death','locate']
    archive_id:str=Field(default='',max_length=200)
    target:str=Field(default='',max_length=150)
    reason:str=Field(default='',max_length=500)
@router.post('/admin/character-travel/players/{uid}')
async def player_action(uid:int,body:PlayerAction,user=Depends(admin)):
    p=await players.find_one({'tg_id':uid})
    if not p or await get_admin_role({'id':uid}):raise HTTPException(400,'بازیکن معتبر انتخاب کن')
    if body.action=='locate':
        s=await engine.state(p)
        return await control(Control(subject=s['_id'],action='move',target=body.target),user)
    if body.action=='death':
        if not body.reason.strip():raise HTTPException(400,'دلیل مرگ را بنویس')
        from routers.characters import RetireBody
        from character_records import retire
        return await retire(uid,RetireBody(action='death',reason=body.reason,character_key=key(p)),user['id'])
    if not p.get('is_dead') and not p.get('registration_reset'):raise HTTPException(409,'این حساب هم‌اکنون کاراکتر زنده دارد')
    source=await db.character_archives.find_one({'_id':body.archive_id,'tg_id':uid}) if body.archive_id else p
    if not source or not (source.get('is_dead') or source.get('died_at')):raise HTTPException(400,'کاراکتر کشته‌شده را انتخاب کن')
    retirement=await db.character_retirements.find_one({'_id':body.archive_id or key(source)})
    if retirement:source={**source,**retirement.get('snapshot',{})}
    identity=('name','gender','title','house','region','backstory','profile_image','flag_image','flag_map_image','points','stats','medals','scoreboard_baseline','popularity')
    fields={k:source[k] for k in identity if k in source}
    fields.update(is_dead=False,registration_reset=False,landless=True,castle=None,castle_buildings={},buildings={},troops={},equipment={},resources={},
                  created_at=now(),last_tick=now(),revived_from=body.archive_id or key(p),revived_at=now())
    archive_id=body.archive_id or key(source)
    await commit({'_id':'character-revive:'+str(uuid4()),'complete':False,'changes':[
        {'collection':'players','query':{'tg_id':uid},'update':{'$set':fields,'$unset':{'death_reason':'','death_snapshot':'','died_at':''}}},
        change('character_archives',{'_id':archive_id},{'superseded_by_revival':key({'tg_id':uid,'created_at':fields['created_at']})}),
    ]})
    await engine.state(await players.find_one({'tg_id':uid}))
    return {'ok':True}
