from text_limits import check_text
"""Paid narrative services, confidential contracts, and the Faith treasury."""
from datetime import timedelta
from uuid import uuid4
from typing import Literal
from bson import ObjectId
from fastapi import APIRouter,Depends,HTTPException
from pydantic import BaseModel,Field,StrictBool,StrictInt
from db import db,game_settings
from game import now
import game_clock
from auth import get_user
from time_management import deadline_view
from admin_notifications import notify_admins
from institution_bank import living,member,matches,admin,oid,request_key,notice
import institution_finance as money

router=APIRouter(prefix='/api/institutions',tags=['institution-services'])
cases=db.institution_service_cases
KINDS={'alchemists':['craft'],'faceless':['assassination','mission'],'watch':['wall-mission'], 'faith':['ceremony','mediation','regional-legitimacy','westeros-legitimacy','support'],'golden-company':['army-scenario']}
NAMES={'alchemists':'صنف کیمیاگران','faceless':'بی‌چهره‌ها','watch':'نگهبانان شب','faith':'ایمان هفت','golden-company':'گروهان طلایی'}
DEFAULTS={'enabled':False,'member_limit':5,'max_open_per_player':5,'managers':[]}

def valid(institution):
    if institution not in KINDS:raise HTTPException(404,'نهاد پیدا نشد')
async def settings(institution):
    valid(institution);row=await game_settings.find_one({'_id':'institution_'+institution}) or {}
    return {**DEFAULTS,**row.get('settings',{})}
async def manager(institution,user):
    p=await living(user['id']);cfg=await settings(institution)
    if not any(matches(p,m) for m in cfg['managers']):raise HTTPException(403,'عضویت این نهاد به کاراکتر تو واگذار نشده است')
    return p,cfg
def clean(text,minimum=3):
    if len(text.strip())<minimum:raise HTTPException(400,'متن را کامل بنویس')
    return text.strip()
def public(row,viewer=None,administrative=False):
    hidden=row['institution']=='faceless' and not administrative and not matches(viewer,row['requester'])
    result={k:row.get(k) for k in ('institution','kind','title','description','status','version','resources','scenario','proposal','result','assigned_name','assigned_id')}
    result.update({'id':str(row['_id']),'mine':matches(viewer,row['requester']),'created_at':row['real_at'].isoformat()+'Z'})
    if not hidden:result['requester']={'tg_id':row['requester']['tg_id'],'name':row['requester']['name']}
    return result
async def fetch(institution,case_id,version,statuses):
    valid(institution);row=await cases.find_one({'_id':oid(case_id),'institution':institution})
    if not row:raise HTTPException(404,'پرونده پیدا نشد')
    if row['version']!=version or row['status'] not in statuses:raise HTTPException(409,'وضعیت پرونده تغییر کرده؛ تازه‌سازی کن')
    return row
async def change(row,status,**fields):
    values={'status':status,'version':str(uuid4()),**fields}
    result=await cases.update_one({'_id':row['_id'],'version':row['version'],'status':row['status']},{'$set':values})
    if not result.matched_count:raise HTTPException(409,'پرونده هم‌زمان تغییر کرده است')
    return {**row,**values}
async def audit(institution,event,actor,details):
    await db.institution_audit.insert_one({'institution':institution,'event':event,'actor':actor,'details':details,'at':game_clock.real_now()})

@router.get('/services/{institution}')
async def dashboard(institution:str,page:int=1,user=Depends(get_user)):
    p=await living(user['id']);cfg=await settings(institution);is_manager=any(matches(p,m) for m in cfg['managers'])
    if not 1<=page<=10000:raise HTTPException(400,'صفحه نامعتبر است')
    q={'institution':institution,'status':{'$ne':'reserving'}}
    if not is_manager:q.update({'requester.tg_id':p['tg_id'],'requester.created_at':p['created_at']})
    data={'viewer_id':p['tg_id'],'is_manager':is_manager,'settings':{k:v for k,v in cfg.items() if k!='managers'},'managers':[{'tg_id':m['tg_id'],'name':m['name']} for m in cfg['managers']], 'kinds':KINDS[institution], 'resources':money.RESOURCE_NAMES,'cases':[public(r,p) async for r in cases.find(q).sort('real_at',-1).skip((page-1)*25).limit(25)],'total':await cases.count_documents(q),'page':page}
    if institution=='faith':data.update(await faith_view(p))
    return data

class Request(BaseModel):
    request_id:str
    kind:str=Field(max_length=50)
    title:str=Field(min_length=3,max_length=100)
    description:str=Field(min_length=20,max_length=500000)
    resources:dict[str,StrictInt]=Field(default_factory=dict,max_length=7)
@router.post('/services/{institution}/requests')
async def request(institution:str,body:Request,user=Depends(get_user)):
    await check_text(body.description, "request_words")
    p=await living(user['id']);cfg=await settings(institution)
    if institution=='golden-company':raise HTTPException(400,'درخواست سناریو را از قرارداد لشکر ثبت کن')
    if not cfg['enabled']:raise HTTPException(400,'پذیرش درخواست این نهاد متوقف است')
    if body.kind not in KINDS[institution]:raise HTTPException(400,'نوع خدمت معتبر نیست')
    if any(matches(p,m) for m in cfg['managers']):raise HTTPException(400,'عضو نهاد نمی‌تواند سفارش خودش را ثبت کند')
    resources=money.amounts(body.resources);title=clean(body.title);description=clean(body.description,20)
    if institution!='faith' and not resources:raise HTTPException(400,'حداقل یک مبلغ یا منبع برای قرارداد مشخص کن')
    key=f"{institution}:{p['tg_id']}:{p['created_at'].isoformat()}:{request_key(body.request_id)}"
    pending=await money.operations.find_one({'_id':'reserve:'+key})
    if pending:
        if pending.get('payload')!={'kind':body.kind,'title':title,'description':description,'resources':resources}:raise HTTPException(409,'شناسهٔ تکراری با اطلاعات متفاوت')
        if pending.get('aborted'):raise HTTPException(409,'رزرو ناموفق بود؛ درخواست تازه ثبت کن')
        await money.finish(pending)
        return public(await cases.find_one({'request_key':key}),p)
    old=await cases.find_one({'request_key':key})
    if old:
        if (old['kind'],old['title'],old['description'],old['resources'])!=(body.kind,title,description,resources):raise HTTPException(409,'شناسهٔ تکراری با اطلاعات متفاوت')
        op=await money.operations.find_one({'_id':'reserve:'+str(old['_id'])})
        if op and op.get('aborted'):raise HTTPException(409,'رزرو این درخواست ناموفق بود؛ درخواست تازه ثبت کن')
        await money.recover();return public(await cases.find_one({'_id':old['_id']}),p)
    if await cases.count_documents({'institution':institution,'requester.tg_id':p['tg_id'],'requester.created_at':p['created_at'],'status':{'$in':['requested','working','submitted','reserving']}})>=cfg['max_open_per_player']:raise HTTPException(400,'تعداد درخواست‌های باز به سقف نهاد رسیده است')
    await money.enough(member(p),resources)
    row={'_id':ObjectId(),'institution':institution,'request_key':key,'kind':body.kind,'title':title,'description':description,'resources':resources,'requester':member(p),'status':'reserving','version':str(uuid4()),'real_at':game_clock.real_now()}
    await money.transfer('reserve:'+key,[money.player_leg(member(p),{k:-v for k,v in resources.items()})],[{'collection':cases.name,'id':row['_id'],'insert':{k:v for k,v in {**row,'status':'requested'}.items() if k!='_id'}}],institution=institution,event='reserve',actor=p['tg_id'],payload={'kind':body.kind,'title':title,'description':description,'resources':resources})
    # Anonymous orders never include sender identity in member notifications.
    await notice('service:'+str(row['_id'])+':new',[m['tg_id'] for m in cfg['managers']],f"سفارش تازه در {NAMES[institution]}: {title}")
    return public({**row,'status':'requested'},p)

class Revision(BaseModel):version:str
@router.post('/services/{institution}/cases/{case_id}/accept')
async def accept(institution:str,case_id:str,body:Revision,user=Depends(get_user)):
    p,cfg=await manager(institution,user)
    if not cfg['enabled']:raise HTTPException(400,'پذیرش سفارش متوقف است')
    row=await fetch(institution,case_id,body.version,['requested'])
    if matches(p,row['requester']):raise HTTPException(400,'انجام سفارش خودت مجاز نیست')
    row=await change(row,'working',assigned=member(p),assigned_id=p['tg_id'],assigned_name=p['name'])
    await notice('service:'+case_id+':accepted',[row['requester']['tg_id']],f"رسیدگی به «{row['title']}» آغاز شد.")
    return public(row,p)

class Submission(Revision):
    scenario:str=Field(min_length=20,max_length=500000)
    proposal:str=Field(min_length=3,max_length=500000)
@router.post('/services/{institution}/cases/{case_id}/submit')
async def submit(institution:str,case_id:str,body:Submission,user=Depends(get_user)):
    await check_text(body.scenario)
    await check_text(body.proposal)
    p,_=await manager(institution,user);row=await fetch(institution,case_id,body.version,['working'])
    if not matches(p,row.get('assigned')):raise HTTPException(403,'فقط عضو مسئول این سفارش می‌تواند نتیجه ارسال کند')
    if institution=='faceless' and not row.get('quota_used'):
        # Seven elapsed game days; pausing freezes the window. A revised result
        # of the same assignment does not consume a second slot.
        if await cases.count_documents({'institution':'faceless','assigned.tg_id':p['tg_id'],'assigned.created_at':p['created_at'],'quota_at':{'$gt':now()-timedelta(days=7)}})>=2:raise HTTPException(400,'سهمیهٔ دو نتیجه در هفت روز بازی تکمیل شده است')
    row=await change(row,'submitted',scenario=clean(body.scenario,20),proposal=clean(body.proposal),quota_used=True,quota_at=row.get('quota_at') or now())
    await notify_admins('institution_service','نتیجهٔ نهاد منتظر داوری است',row['title'],dedupe_key='service:'+case_id+':'+row['version'],player_name=row['requester']['name'],player_tg_id=row['requester']['tg_id'],source_id=case_id,action='مدیریت نهادها؛ سناریو و منابع رزروشده را بررسی کن.',audience_roles=('owner','full'))
    return public(row,p)

class Decision(Revision):reason:str=Field(min_length=3,max_length=2000)
async def refund(row,result):
    version=str(uuid4())
    await money.transfer('refund:'+str(row['_id']),[money.player_leg(row['requester'],row['resources'])],[money.effect(cases.name,row['_id'],{'status':'rejected','result':result,'version':version})],institution=row['institution'],event='refund',actor=row['requester']['tg_id'])
    await notice('service:'+str(row['_id'])+':refund',[row['requester']['tg_id']],'سفارش رد یا لغو شد و هزینهٔ رزروشده برگشت داده شد.')
    return await cases.find_one({'_id':row['_id']})
@router.post('/services/{institution}/cases/{case_id}/reject')
async def reject(institution:str,case_id:str,body:Decision,user=Depends(get_user)):
    p,_=await manager(institution,user);row=await fetch(institution,case_id,body.version,['requested','working'])
    if row['status']=='working' and not matches(p,row.get('assigned')):raise HTTPException(403,'این سفارش به عضو دیگری واگذار شده است')
    return public(await refund(row,clean(body.reason)),p)
@router.post('/services/{institution}/cases/{case_id}/cancel')
async def cancel(institution:str,case_id:str,body:Revision,user=Depends(get_user)):
    p=await living(user['id']);row=await fetch(institution,case_id,body.version,['requested'])
    if not matches(p,row['requester']):raise HTTPException(403,'این سفارش متعلق به تو نیست')
    return public(await refund(row,'لغو توسط درخواست‌کننده'),p)

class Settings(BaseModel):
    enabled:StrictBool
    member_limit:StrictInt=Field(ge=1,le=100)
    max_open_per_player:StrictInt=Field(ge=1,le=50)
    manager_ids:list[StrictInt]=Field(max_length=100)
@router.put('/admin/services/{institution}/settings')
async def save_settings(institution:str,body:Settings,user=Depends(admin)):
    valid(institution)
    if len(set(body.manager_ids))>body.member_limit:raise HTTPException(400,'تعداد اعضا بیشتر از سقف تعیین‌شده است')
    members=[member(await living(uid)) for uid in dict.fromkeys(body.manager_ids)]
    cfg={k:v for k,v in body.model_dump().items() if k!='manager_ids'};cfg['managers']=members
    await game_settings.update_one({'_id':'institution_'+institution},{'$set':{'settings':cfg}},upsert=True)
    await audit(institution,'settings',user['id'],cfg);return {'ok':True}
@router.get('/admin/services/{institution}')
async def admin_dashboard(institution:str,page:int=1,user=Depends(admin)):
    cfg=await settings(institution)
    if not 1<=page<=10000:raise HTTPException(400,'صفحه نامعتبر است')
    q={'institution':institution};data={'settings':{**cfg,'managers':[{'tg_id':m['tg_id'],'name':m['name']} for m in cfg['managers']]},'kinds':KINDS[institution],'resources':money.RESOURCE_NAMES,'cases':[public(r,administrative=True) async for r in cases.find(q).sort('real_at',-1).skip((page-1)*25).limit(25)],'total':await cases.count_documents(q),'page':page}
    data['ledger']=[{'id':str(r['_id']),'event':r.get('event'),'actor':r.get('actor'),'legs':[{'values':l['values'],'name':l.get('person',{}).get('name')} for l in r['legs']],'complete':r.get('complete',False),'aborted':r.get('aborted',False),'error':r.get('error'),'at':r['real_at'].isoformat()+'Z'} async for r in money.operations.find({'institution':institution}).sort('real_at',-1).limit(100)]
    if institution=='faith':data.update(await faith_view())
    return data

class Review(Revision):
    action:Literal['approve','return','reject']
    result:str=Field(min_length=3,max_length=4000)
    assignee_id:StrictInt|None=None
class Assignment(Revision):assignee_id:StrictInt
@router.post('/admin/services/{institution}/cases/{case_id}/assign')
async def assign(institution:str,case_id:str,body:Assignment,user=Depends(admin)):
    row=await fetch(institution,case_id,body.version,['requested','working','submitted']);cfg=await settings(institution);p=await living(body.assignee_id)
    if not any(matches(p,m) for m in cfg['managers']) or matches(p,row['requester']):raise HTTPException(400,'عضو مسئول معتبر نیست')
    row=await change(row,'working',assigned=member(p),assigned_id=p['tg_id'],assigned_name=p['name'],quota_used=False,quota_at=None)
    await audit(institution,'assign',user['id'],{'case':case_id,'member':p['tg_id']})
    return public(row,administrative=True)
@router.post('/admin/services/{institution}/cases/{case_id}/review')
async def review(institution:str,case_id:str,body:Review,user=Depends(admin)):
    row=await fetch(institution,case_id,body.version,['requested','working','submitted'])
    result=clean(body.result)
    if body.action=='return':
        if row['status']!='submitted':raise HTTPException(400,'فقط سناریوی ارسال‌شده قابل برگشت برای اصلاح است')
        row=await change(row,'working',result=result)
    elif body.action=='reject':row=await refund(row,result)
    else:
        if row['status']!='submitted':raise HTTPException(400,'نتیجه هنوز ارسال نشده است')
        recipient=await living(row['assigned']['tg_id'])
        if not matches(recipient,row['assigned']):raise HTTPException(409,'کاراکتر انجام‌دهنده تغییر کرده؛ پرونده را رد یا اصلاح کن')
        values=row['resources'] if institution!='alchemists' else {k:v for k,v in row['resources'].items() if k=='gold'}
        # Crafting inputs burn here; granting the actual item remains an explicit
        # admin action in the existing item panel.
        legs=[money.player_leg(row['assigned'],values)];effects=[]
        if institution=='faith':
            cfg=await settings('faith');members=[]
            for m in cfg['managers']:
                try:
                    if matches(await living(m['tg_id']),m):members.append(m)
                except HTTPException:pass
            if values:
                effects=await faith_share_effects(values,members)
                legs=[money.treasury_leg('faith',values)]
        effects.append(money.effect(cases.name,row['_id'],{'status':'resolved','result':result,'version':str(uuid4())}))
        await money.transfer('approve:'+case_id,legs,effects,institution=institution,event='payment',actor=user['id'])
        row=await cases.find_one({'_id':row['_id']})
        await notice('service:'+case_id+':resolved',[row['requester']['tg_id'],row['assigned']['tg_id']],f"نتیجهٔ «{row['title']}» تأیید شد: {result}")
    await audit(institution,'review',user['id'],{'case':case_id,'action':body.action,'result':result})
    return public(row,administrative=True)

def split(values,members):
    if not members:raise HTTPException(400,'هیچ عضوی برای تقسیم خزانه تعیین نشده است')
    return [{'person':m,'values':{k:v//len(members)+(i<v%len(members)) for k,v in values.items()}} for i,m in enumerate(members)]
def account_id(person):return f"faith:{person['tg_id']}:{person['created_at'].isoformat()}"
async def faith_share_effects(values,members):
    effects=[]
    for share in split(values,members):
        a=await db.institution_faith_accounts.find_one({'_id':account_id(share['person'])}) or {}
        effects.append({'collection':'institution_faith_accounts','id':account_id(share['person']),'insert':{'person':share['person'],'resources':{}}})
        effects.append(money.effect('institution_faith_accounts',account_id(share['person']),{'resources':{k:a.get('resources',{}).get(k,0)+share['values'].get(k,0) for k in money.RESOURCE_NAMES}}))
    return effects
async def faith_view(person=None):
    treasury=await money.treasuries.find_one({'_id':'faith'}) or {}
    leaders=[{'name':r['name'],'resources':r['resources']} async for r in db.institution_donors.find({}).sort('total',-1).limit(20)]
    data={'treasury':treasury.get('resources',{}),'donors':leaders}
    if person:
        account=await db.institution_faith_accounts.find_one({'_id':account_id(person)}) or {}
        data.update({'share':account.get('resources',{}),'withdrawal_deadline':deadline_view(account['next_at']) if account.get('next_at') else None})
    data['withdrawals']=[{'name':r.get('name'),'resources':r.get('values',{}),'at':r['at'].isoformat()+'Z'} async for r in db.institution_faith_withdrawals.find({}).sort('at',-1).limit(50)]
    return data
class Donation(BaseModel):
    request_id:str
    resources:dict[str,StrictInt]=Field(max_length=7)
@router.post('/services/faith/donate')
async def donate(body:Donation,user=Depends(get_user)):
    p=await living(user['id']);cfg=await settings('faith');values=money.amounts(body.resources)
    if not cfg['enabled'] or not values:raise HTTPException(400,'مذهب غیرفعال است یا مبلغ اهدا خالی است')
    members=[]
    for m in cfg['managers']:
        try:
            if matches(await living(m['tg_id']),m):members.append(m)
        except HTTPException:pass
    shares=split(values,members);key='donate:'+account_id(p)+':'+request_key(body.request_id)
    old=await money.operations.find_one({'_id':key})
    if old:
        if old.get('values')!=values:raise HTTPException(409,'اطلاعات درخواست تکراری متفاوت است')
        await money.finish(old);return {'ok':True}
    await money.enough(member(p),values);effects=await faith_share_effects(values,members)
    donor=await db.institution_donors.find_one({'_id':account_id(p)}) or {}
    totals={k:donor.get('resources',{}).get(k,0)+values.get(k,0) for k in money.RESOURCE_NAMES}
    effects.extend([{'collection':'institution_donors','id':account_id(p),'insert':{'name':p['name']}},money.effect('institution_donors',account_id(p),{'name':p['name'],'resources':totals,'total':sum(totals.values())})])
    await money.transfer(key,[money.player_leg(member(p),{k:-v for k,v in values.items()}),money.treasury_leg('faith',values)],effects,institution='faith',event='donate',actor=p['tg_id'],values=values)
    return {'ok':True}
class Withdrawal(BaseModel):request_id:str
@router.post('/services/faith/withdraw')
async def withdraw(body:Withdrawal,user=Depends(get_user)):
    p,_=await manager('faith',user);key='withdraw:'+account_id(p)+':'+request_key(body.request_id)
    old=await money.operations.find_one({'_id':key})
    if old:await money.finish(old);return {'ok':True}
    account=await db.institution_faith_accounts.find_one({'_id':account_id(p)}) or {}
    if account.get('next_at') and account['next_at']>now():raise HTTPException(400,'از برداشت قبلی هنوز ۲۴ ساعت بازی نگذشته است')
    values={k:v for k,v in account.get('resources',{}).items() if v>0}
    if not values:raise HTTPException(400,'سهم قابل برداشتی نداری')
    effects=[money.effect('institution_faith_accounts',account_id(p),{'resources':{},'next_at':now()+timedelta(hours=24)}),{'collection':'institution_faith_withdrawals','id':key,'insert':{'name':p['name'],'values':values,'at':game_clock.real_now()}}]
    await money.transfer(key,[money.treasury_leg('faith',{k:-v for k,v in values.items()}),money.player_leg(member(p),values)],effects,institution='faith',event='withdraw',actor=p['tg_id'])
    return {'ok':True}
async def ensure_indexes():
    await cases.create_index('request_key',unique=True)
    await cases.create_index([('institution',1),('real_at',-1)])
