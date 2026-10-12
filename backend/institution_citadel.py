"""Citadel service cases. API middleware serializes mutations with game state."""
from datetime import timedelta
from typing import Literal
from uuid import uuid4
from bson import ObjectId
from fastapi import APIRouter,Depends,HTTPException
from pydantic import BaseModel,Field,StrictBool,StrictInt
from db import db,game_settings
from game import now
import game_clock
from time_management import deadline_view
from auth import get_user
from admin_notifications import notify_admins
from institution_bank import admin,living,member,matches,oid,request_key,notice

router=APIRouter(prefix='/api/institutions',tags=['citadel'])
cases=db.institution_citadel_cases
DEFAULTS={'enabled':False,'research_enabled':True,'healing_enabled':True,'member_limit':5,'max_open_per_player':3,'max_duration_hours':720,'managers':[]}
async def settings():
    row=await game_settings.find_one({'_id':'citadel'}) or {}
    return {**DEFAULTS,**row.get('settings',{})}
async def manager(user):
    p=await living(user['id']);cfg=await settings()
    if not any(matches(p,m) for m in cfg['managers']):raise HTTPException(403,'مدیریت سیتادل به این کاراکتر واگذار نشده است')
    return p,cfg
async def audit(event,actor,details):
    await db.institution_audit.insert_one({'institution':'citadel','event':event,'actor':actor,'details':details,'at':game_clock.real_now()})
def public(row):
    return {'id':str(row['_id']),'kind':row['kind'],'title':row['title'],'description':row['description'],
            'requester':{k:row['requester'][k] for k in ('tg_id','name')},'status':row['status'],'version':row['version'],
            'scenario':row.get('scenario',''),'proposal':row.get('proposal',''),'result':row.get('result',''),'reason':row.get('reason',''),
            'assigned_name':row.get('assigned_name'),'deadline':deadline_view(row['due_at']) if row.get('due_at') else None,
            'created_at':row['real_created_at'].isoformat()+'Z'}
async def change(row,status,fields):
    version=str(uuid4())
    updated={'status':status,'version':version,**fields}
    result=await cases.update_one({'_id':row['_id'],'version':row['version'],'status':row['status']},{'$set':updated})
    if not result.matched_count:raise HTTPException(409,'پرونده تغییر کرده؛ صفحه را تازه کن')
    return {**row,**updated}
async def fetch(case_id,version,statuses):
    row=await cases.find_one({'_id':oid(case_id)})
    if not row:raise HTTPException(404,'پروندهٔ سیتادل پیدا نشد')
    if row['version']!=version or row['status'] not in statuses:raise HTTPException(409,'وضعیت پرونده تغییر کرده؛ صفحه را تازه کن')
    return row
@router.get('/citadel')
async def dashboard(page:int=1,user=Depends(get_user)):
    p=await living(user['id']);cfg=await settings();is_manager=any(matches(p,m) for m in cfg['managers'])
    if page<1 or page>10000:raise HTTPException(400,'صفحه نامعتبر است')
    q={} if is_manager else {'requester.tg_id':p['tg_id'],'requester.created_at':p['created_at']}
    return {'viewer_id':p['tg_id'],'is_manager':is_manager,'settings':{k:v for k,v in cfg.items() if k!='managers'},
            'managers':[{'tg_id':m['tg_id'],'name':m['name']} for m in cfg['managers']],
            'cases':[public(r) async for r in cases.find(q).sort('real_created_at',-1).skip((page-1)*25).limit(25)],'page':page,'total':await cases.count_documents(q)}
class Request(BaseModel):
    request_id:str
    kind:Literal['research','healing']
    title:str=Field(min_length=3,max_length=100)
    description:str=Field(min_length=20,max_length=4000)
@router.post('/citadel/requests')
async def request(body:Request,user=Depends(get_user)):
    p=await living(user['id']);cfg=await settings()
    if not cfg['enabled'] or not cfg[body.kind+'_enabled']:raise HTTPException(400,'پذیرش این خدمت فعلاً فعال نیست')
    if len(body.title.strip())<3 or len(body.description.strip())<20:raise HTTPException(400,'عنوان و شرح درخواست را کامل بنویس')
    key=f"{p['tg_id']}:{p['created_at'].isoformat()}:{request_key(body.request_id)}"
    old=await cases.find_one({'request_key':key})
    if old:
        if (old['kind'],old['title'],old['description'])!=(body.kind,body.title.strip(),body.description.strip()):raise HTTPException(409,'شناسهٔ تکراری با اطلاعات متفاوت ارسال شده است')
        return public(old)
    if await cases.count_documents({'requester.tg_id':p['tg_id'],'requester.created_at':p['created_at'],'status':{'$in':['requested','working','submitted']}})>=cfg['max_open_per_player']:raise HTTPException(400,'تعداد پرونده‌های بازت به سقف سیتادل رسیده است')
    row={'_id':ObjectId(),'request_key':key,'kind':body.kind,'title':body.title.strip(),'description':body.description.strip(),'requester':member(p),'status':'requested','version':str(uuid4()),'created_at':now(),'real_created_at':game_clock.real_now()}
    await cases.insert_one(row)
    await notice('citadel:'+str(row['_id'])+':request',[m['tg_id'] for m in cfg['managers']],f"درخواست تازهٔ سیتادل از {p['name']}: {row['title']}")
    return public(row)
class Revision(BaseModel):
    version:str
class Start(Revision):
    duration_hours:StrictInt=Field(ge=1,le=720)
@router.post('/citadel/cases/{case_id}/start')
async def start(case_id:str,body:Start,user=Depends(get_user)):
    p,cfg=await manager(user)
    if not cfg['enabled']:raise HTTPException(400,'سیتادل غیرفعال است')
    if body.duration_hours>cfg['max_duration_hours']:raise HTTPException(400,'مدت از سقف سیتادل بیشتر است')
    row=await fetch(case_id,body.version,['requested']);owner=await living(row['requester']['tg_id'])
    if not matches(owner,row['requester']):raise HTTPException(409,'کاراکتر درخواست‌کننده تغییر کرده است')
    row=await change(row,'working',{'assigned_id':p['tg_id'],'assigned_name':p['name'],'due_at':now()+timedelta(hours=body.duration_hours),'started_at':game_clock.real_now()})
    await audit('start',user['id'],{'case':case_id,'duration_hours':body.duration_hours})
    await notice('citadel:'+case_id+':start',[owner['tg_id']],f"رسیدگی سیتادل به «{row['title']}» آغاز شد.")
    return public(row)
class Submission(Revision):
    scenario:str=Field(min_length=20,max_length=8000)
    proposal:str=Field(min_length=10,max_length=2000)
@router.post('/citadel/cases/{case_id}/submit')
async def submit(case_id:str,body:Submission,user=Depends(get_user)):
    await manager(user)
    if len(body.scenario.strip())<20 or len(body.proposal.strip())<10:raise HTTPException(400,'سناریو و نتیجهٔ پیشنهادی را کامل بنویس')
    row=await fetch(case_id,body.version,['working'])
    row=await change(row,'submitted',{'scenario':body.scenario.strip(),'proposal':body.proposal.strip(),'submitted_by':user['id'],'submitted_at':game_clock.real_now()})
    await audit('submit',user['id'],{'case':case_id})
    await notify_admins('institution_citadel','پروندهٔ سیتادل منتظر داوری است',row['title'],dedupe_key='citadel:'+case_id+':'+row['version'],player_name=row['requester']['name'],player_tg_id=row['requester']['tg_id'],source_id=case_id,action='مدیریت نهادها ← سیتادل؛ سناریو و نتیجهٔ پیشنهادی را بررسی کن.',audience_roles=('owner','full'))
    await notice('citadel:'+case_id+':submitted',[row['requester']['tg_id']],'سناریوی سیتادل برای بررسی نتیجه ارسال شد.')
    return public(row)
class Decision(Revision):
    reason:str=Field(min_length=3,max_length=2000)
@router.post('/citadel/cases/{case_id}/reject')
async def reject(case_id:str,body:Decision,user=Depends(get_user)):
    await manager(user)
    if len(body.reason.strip())<3:raise HTTPException(400,'دلیل رد را بنویس')
    row=await fetch(case_id,body.version,['requested'])
    row=await change(row,'rejected',{'reason':body.reason.strip()})
    await audit('reject',user['id'],{'case':case_id,'reason':body.reason.strip()})
    await notice('citadel:'+case_id+':reject',[row['requester']['tg_id']],f"درخواست سیتادل رد شد: {body.reason.strip()}")
    return public(row)
@router.post('/citadel/cases/{case_id}/cancel')
async def cancel(case_id:str,body:Revision,user=Depends(get_user)):
    p=await living(user['id']);row=await fetch(case_id,body.version,['requested'])
    if not matches(p,row['requester']):raise HTTPException(403,'این درخواست مربوط به تو نیست')
    return public(await change(row,'cancelled',{}))
class Settings(BaseModel):
    enabled:StrictBool
    research_enabled:StrictBool
    healing_enabled:StrictBool
    max_open_per_player:StrictInt=Field(ge=1,le=20)
    max_duration_hours:StrictInt=Field(ge=1,le=720)
    member_limit:StrictInt=Field(default=5,ge=1,le=100)
    manager_ids:list[StrictInt]=Field(max_length=100)
@router.get('/admin/citadel')
async def admin_dashboard(page:int=1,user=Depends(admin)):
    if page<1 or page>10000:raise HTTPException(400,'صفحه نامعتبر است')
    cfg=await settings()
    return {'settings':{**cfg,'managers':[{'tg_id':m['tg_id'],'name':m['name']} for m in cfg['managers']]},'cases':[public(r) async for r in cases.find({}).sort('real_created_at',-1).skip((page-1)*25).limit(25)],'page':page,'total':await cases.count_documents({})}
@router.put('/admin/citadel/settings')
async def save_settings(body:Settings,user=Depends(admin)):
    if len(set(body.manager_ids))>body.member_limit:raise HTTPException(400,'تعداد اعضا بیشتر از سقف نهاد است')
    managers=[member(await living(uid)) for uid in set(body.manager_ids)]
    cfg={k:v for k,v in body.model_dump().items() if k!='manager_ids'};cfg['managers']=managers
    await game_settings.update_one({'_id':'citadel'},{'$set':{'settings':cfg,'changed_by':user['id'],'changed_at':game_clock.real_now()}},upsert=True)
    await audit('settings',user['id'],{**cfg,'managers':[m['tg_id'] for m in managers]})
    return {'ok':True}
class Review(Revision):
    action:Literal['approve','return','reject']
    result:str=Field(min_length=3,max_length=4000)
@router.post('/admin/citadel/cases/{case_id}/review')
async def review(case_id:str,body:Review,user=Depends(admin)):
    if len(body.result.strip())<3:raise HTTPException(400,'نتیجه یا دلیل تصمیم را بنویس')
    row=await fetch(case_id,body.version,['submitted'])
    status={'approve':'resolved','return':'working','reject':'rejected'}[body.action]
    fields={'result':body.result.strip(),'reviewed_by':user['id'],'reviewed_at':game_clock.real_now()}
    if body.action!='approve':fields['reason']=body.result.strip()
    row=await change(row,status,fields)
    await audit(body.action,user['id'],{'case':case_id,'result':body.result.strip()})
    await notice('citadel:'+case_id+':'+row['version'],[row['requester']['tg_id']]+[m['tg_id'] for m in (await settings())['managers']],f"نتیجهٔ رسیدگی سیتادل به «{row['title']}»: {body.result.strip()}")
    return public(row)
async def ensure_indexes():
    await cases.create_index('request_key',unique=True)
    await cases.create_index([('status',1),('real_created_at',-1)])
