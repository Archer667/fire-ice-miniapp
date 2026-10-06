from datetime import datetime
from fastapi import APIRouter,Depends,HTTPException,Response
from pydantic import BaseModel,Field
from pymongo.errors import DuplicateKeyError
from auth import get_user,get_full_admin
from db import db,players
from game import now
from character_images import decode_character_image,map_flag_image

router=APIRouter(prefix='/api')
requests=db.character_profile_requests
FIELDS=('name','backstory','profile_image','flag_image')

def character_key(p):
    return str(p.get('family_child_id') or '')+':'+str(p.get('created_at') or '')+':'+str(p.get('character_retired_at') or '')+':'+str(p.get('season_started_at') or '')

async def administrator(user=Depends(get_user)):return await get_full_admin(user)
async def current_player(uid):
    p=await players.find_one({'tg_id':uid})
    if not p or not p.get('castle') or p.get('is_dead') or p.get('registration_reset'):raise HTTPException(403,'ابتدا کاراکتر فعال داشته باش')
    return p

def visible_request(r):
    if not r:return None
    return {k:r.get(k) for k in ('revision','status','submitted_at','reviewed_at','reason','proposed','before','player_name','tg_id')}

class ProfileBody(BaseModel):
    name:str=Field(min_length=1,max_length=40)
    backstory:str=Field(min_length=40,max_length=2000)
    profile_image:str|None=Field(default=None,max_length=349650)
    flag_image:str|None=Field(default=None,max_length=349650)

@router.get('/character/profile')
async def profile(user=Depends(get_user)):
    p=await current_player(user['id'])
    r=await requests.find_one({'_id':user['id']})
    if r and r.get('character_key')!=character_key(p):r={**r,'status':'stale'}
    return {'current':{k:p.get(k) for k in FIELDS},'request':visible_request(r)}

@router.post('/character/profile')
async def submit(body:ProfileBody,user=Depends(get_user)):
    p=await current_player(user['id'])
    before={k:p.get(k) for k in FIELDS}
    proposed={**before,**body.model_dump(exclude_unset=True)};proposed['name']=body.name.strip();proposed['backstory']=body.backstory.strip()
    if not proposed['name'] or len(proposed['backstory'])<40:raise HTTPException(422,'نام و بک‌استوری حداقل ۴۰ نویسه‌ای را کامل کن')
    for key in ('profile_image','flag_image'):
        if proposed[key]!=before[key]:decode_character_image(proposed[key])
    if proposed==before:raise HTTPException(400,'اطلاعات جدیدی وارد نشده')
    try:
        result=await requests.find_one_and_update({'_id':user['id'],'status':{'$ne':'processing'}},{'$set':{'tg_id':user['id'],'player_name':p['name'],'character_key':character_key(p),'before':before,'proposed':proposed,'status':'pending','submitted_at':now(),'reason':'','reviewed_at':None},'$inc':{'revision':1}},upsert=True,return_document=True)
    except DuplicateKeyError:raise HTTPException(409,'ادمین در حال بررسی درخواست است؛ کمی بعد دوباره تلاش کن')
    from admin_notifications import notify_admins
    await notify_admins('character_profile','درخواست ساخت و ویرایش کاراکتر',p['name'],dedupe_key=f"character-profile:{user['id']}:{result['revision']}",player_name=p['name'],player_tg_id=user['id'],action='بازیکنان و جهان ← درخواست‌های کاراکتر')
    return visible_request(result)

@router.get('/admin/character-profiles')
async def pending(user=Depends(administrator)):
    # Recover a review interrupted after its claim; applying a revision is idempotent.
    async for r in requests.find({'status':'processing'}):await finish_review(r)
    waiting=[visible_request(r) async for r in requests.find({'status':'pending'}).sort('submitted_at',1).limit(1000)]
    history=[visible_request(r) async for r in requests.find({'status':{'$in':['approved','rejected','stale']}}).sort('submitted_at',-1).limit(100)]
    return waiting+history

class ReviewBody(BaseModel):
    revision:int=Field(ge=1)
    accept:bool
    reason:str=Field(default='',max_length=500)

async def finish_review(r):
    p=await players.find_one({'tg_id':r['tg_id']})
    token=f"{r['tg_id']}:{r['revision']}"
    valid=p and character_key(p)==r['character_key'] and not p.get('is_dead') and not p.get('registration_reset')
    if valid and p.get('approved_profile_request')==token:
        status='approved'
    elif valid:
        query={'tg_id':r['tg_id'],**r['before'],'is_dead':{'$ne':True},'registration_reset':{'$ne':True}}
        for key in ('created_at','family_child_id','season_started_at'):query[key]=p.get(key)
        update=await players.update_one(query,{'$set':{**r['proposed'],'flag_map_image':map_flag_image(r['proposed'].get('flag_image')),'approved_profile_request':token,'profile_edited_at':now(),'profile_edited_by':r['reviewer']}})
        status='approved' if update.matched_count else 'stale'
    else:status='stale'
    await requests.update_one({'_id':r['_id'],'revision':r['revision'],'status':'processing'},{'$set':{'status':status,'reviewed_at':now()}})
    return status

@router.post('/admin/character-profiles/{tg_id}/review')
async def review(tg_id:int,body:ReviewBody,user=Depends(administrator)):
    r=await requests.find_one_and_update({'_id':tg_id,'revision':body.revision,'status':'pending'},{'$set':{'status':'processing' if body.accept else 'rejected','reviewer':user['id'],'reason':body.reason.strip(),'reviewed_at':now()}},return_document=True)
    if not r:raise HTTPException(409,'این درخواست تغییر کرده یا قبلاً بررسی شده؛ فهرست را تازه کن')
    status=await finish_review(r) if body.accept else 'rejected'
    from routers.ravens import send_system_message
    text='اطلاعات کاراکترت تأیید و فعال شد.' if status=='approved' else 'درخواستت رد شد.' if status=='rejected' else 'اطلاعات کاراکتر تغییر کرده؛ درخواست تازه بفرست.'
    await send_system_message(tg_id,r['player_name'],text+(f"\nدلیل: {body.reason.strip()}" if body.reason.strip() else ''),kind='character_profile')
    return {'ok':True,'status':status}

@router.get('/character/flags/{tg_id}')
async def flag(tg_id:int):
    p=await players.find_one({'tg_id':tg_id,'is_dead':{'$ne':True},'registration_reset':{'$ne':True}},{'flag_image':1,'flag_map_image':1})
    if not p or not p.get('flag_image'):raise HTTPException(404,'پرچم ثبت نشده')
    raw,mime=decode_character_image(p.get('flag_map_image') or p['flag_image'])
    return Response(raw,media_type=mime,headers={'Cache-Control':'public, max-age=3600','X-Content-Type-Options':'nosniff'})
