"""Independent bank treasury and restart-safe loan operations (single API worker)."""
import hashlib
from datetime import timedelta
from uuid import UUID, uuid4
from bson import ObjectId
from fastapi import APIRouter, Depends, HTTPException
from pydantic import BaseModel, Field, StrictInt, StrictBool
from pymongo.errors import DuplicateKeyError
from db import db, players, game_settings, messages
from auth import get_user, get_full_admin, get_admin_role
from game import now, apply_production, production_fields
import game_clock
from time_management import deadline_view
from config import SYSTEM_SENDER_ID, SYSTEM_SENDER_NAME

router = APIRouter(prefix='/api/institutions', tags=['institutions'])
bank = db.institution_treasuries
loans = db.institution_loans
operations = db.institution_bank_operations
DEFAULTS = {'enabled':False, 'max_principal':10000, 'max_interest_percent':20,
            'max_installments':12, 'min_interval_hours':24, 'max_interval_hours':720,
            'grace_hours':24, 'require_guarantor':True, 'member_limit':5, 'managers':[]}
CATALOG = [
    ('iron-bank','بانک آهنین براووس','bank','وام، اقساط و ضمانت'),
    ('citadel','سیتادل','citadel','پژوهش و درمان کاراکتر'),
    ('golden-company','گروهان طلایی',None,'قرارداد و اعزام مزدور'),
    ('alchemists','صنف کیمیاگران','alchemists','سفارش ساخت و سناریوی تولید'),
    ('faceless','بی‌چهره‌ها','faceless','سفارش مأموریت و ارسال سناریو'),
    ('faith','ایمان هفت','faith','مراسم، میانجی‌گری و حمایت مذهبی'),
    ('watch','نگهبانان شب',None,'مأموریت‌های دیوار و پشتیبانی'),
]

def request_key(raw):
    try:
        return str(UUID(raw))
    except (ValueError,TypeError,AttributeError):
        raise HTTPException(400,'شناسهٔ درخواست نامعتبر است') from None

def oid(raw):
    try:
        return ObjectId(raw)
    except Exception:
        raise HTTPException(400,'شناسهٔ قرارداد نامعتبر است') from None

def member(p):
    return {'tg_id':p['tg_id'], 'name':p['name'], 'created_at':p['created_at']}

def matches(p,m):
    return bool(p and p.get('tg_id') == m.get('tg_id') and p.get('created_at') == m.get('created_at'))

async def settings():
    row = await game_settings.find_one({'_id':'iron_bank'}) or {}
    return {**DEFAULTS, **row.get('settings',{})}

async def living(uid):
    p = await players.find_one({'tg_id':uid})
    if not p or p.get('is_dead') or p.get('registration_reset') or p.get('pending') or not p.get('castle') or not p.get('region') or await get_admin_role({'id':uid}):
        raise HTTPException(403,'بازیکن باید زنده و دارای خاندان تأییدشده باشد')
    return p

async def manager(user):
    cfg = await settings()
    p = await living(user['id'])
    if not any(matches(p,m) for m in cfg['managers']):
        raise HTTPException(403,'مدیریت بانک به این کاراکتر واگذار نشده است')
    return p,cfg

async def admin(user=Depends(get_user)):
    return await get_full_admin(user)

async def treasury():
    await bank.update_one({'_id':'iron-bank'}, {'$setOnInsert':{'gold':0}}, upsert=True)
    return await bank.find_one({'_id':'iron-bank'})

def capital_id(person):return f"{person['tg_id']}:{person['created_at'].isoformat()}"
async def capital_snapshot():
    return [{'person':row['person'],'amount':row['amount']} async for row in db.institution_bank_capital.find({'amount':{'$gt':0}})]
def weighted_split(amount,shares):
    total=sum(s['amount'] for s in shares)
    if not total or not amount:return []
    result=[];acc=0
    for s in shares:
        part=(acc+s['amount'])*amount//total-acc*amount//total;acc+=s['amount']
        if part:result.append({'person':s['person'],'amount':part})
    return result

class CapitalChange(BaseModel):
    request_id:str
    amount:StrictInt=Field(ge=1,le=10**9)
@router.post('/bank/capital/{action}')
async def change_capital(action:str,body:CapitalChange,user=Depends(get_user)):
    p,_=await manager(user)
    if action not in ('deposit','withdraw'):raise HTTPException(400,'عملیات سرمایه معتبر نیست')
    person=member(p);key='capital:'+action+':'+capital_id(person)+':'+request_key(body.request_id)
    old=await operations.find_one({'_id':key})
    if old:
        if old['amount']!=body.amount:raise HTTPException(409,'مبلغ درخواست تکراری متفاوت است')
        if old.get('aborted'):raise HTTPException(409,'درخواست ناموفق بود؛ درخواست تازه ثبت کن')
        await finish_operation(old);return {'ok':True}
    if await operations.count_documents({'kind':{'$in':['deposit','withdraw']},'complete':{'$ne':True},'aborted':{'$ne':True}}):raise HTTPException(409,'یک انتقال سرمایه ناتمام است؛ رسیدگی لازم است')
    account=await db.institution_bank_capital.find_one({'_id':capital_id(person)}) or {}
    capital=account.get('amount',0)
    if action=='withdraw':
        if account.get('next_at') and account['next_at']>now():raise HTTPException(400,'از برداشت قبلی هنوز ۲۴ ساعت بازی نگذشته است')
        if body.amount>capital or body.amount>(await treasury())['gold']:raise HTTPException(400,'مبلغ از سرمایهٔ تو یا موجودی آزاد بانک بیشتر است')
    else:
        current=apply_production(p)
        if current.get('resources',{}).get('gold',0)<body.amount:raise HTTPException(400,'طلای شخصی کافی نیست')
    await prepare_operation({'_id':key,'kind':action,'person':person,'amount':body.amount,'capital_after':capital+(body.amount if action=='deposit' else -body.amount),'actor':p['tg_id'],'at':now(),'complete':False,'recipients':[p['tg_id']],'text':f"{body.amount} طلا {'به خزانهٔ بانک افزوده شد' if action=='deposit' else 'از سرمایهٔ بانک برداشت شد'}."})
    return {'ok':True}
@router.get('/bank/capital-ledger')
async def capital_ledger(user=Depends(get_user)):
    await manager(user)
    return [{'name':r.get('person',{}).get('name'),'event':r['kind'],'amount':r['amount'],'complete':r.get('complete',False),'aborted':r.get('aborted',False),'at':r['real_at'].isoformat()+'Z'} async for r in operations.find({'kind':{'$in':['deposit','withdraw']}}).sort('real_at',-1).limit(100)]

def schedule(principal,interest,count,interval,start):
    total = principal + (principal*interest+99)//100
    if count > total:
        raise HTTPException(400,'تعداد اقساط از مبلغ بازپرداخت بیشتر است')
    base,extra = divmod(total,count)
    return [{'number':i+1, 'amount':base+(i<extra), 'due_at':start+timedelta(hours=interval*(i+1)), 'paid':False} for i in range(count)]

async def audit(event,actor,details):
    await db.institution_audit.insert_one({'institution':'iron-bank', 'event':event,'actor':actor,'details':details,'at':game_clock.real_now(),'game_at':now()})

async def notice(event,recipients,text):
    for uid in set(recipients):
        await messages.update_one({'_id':f'bank:{event}:{uid}'}, {'$setOnInsert':{'from_id':SYSTEM_SENDER_ID,'from_name':SYSTEM_SENDER_NAME,'to_id':uid,'to_name':'','text':text,'kind':'institution','read':False,'created_at':now()}}, upsert=True)

async def bank_once(amount,key):
    await treasury()
    field='receipts.'+hashlib.sha256(key.encode()).hexdigest()
    row=await bank.find_one({'_id':'iron-bank'})
    if row.get('receipts',{}).get(field.split('.')[1]):
        return
    query={'_id':'iron-bank',field:{'$ne':True}}
    if amount < 0:
        query['gold']={'$gte':-amount}
    result=await bank.update_one(query,{'$inc':{'gold':amount},'$set':{field:True}})
    if not result.matched_count:
        raise HTTPException(409,'موجودی خزانهٔ بانک کافی نیست')

async def player_once(m,amount,key):
    field='institution_receipts.'+hashlib.sha256(key.encode()).hexdigest()
    p=await players.find_one({'tg_id':m['tg_id']})
    if not matches(p,m):
        raise HTTPException(409,'کاراکتر طرف قرارداد تغییر کرده؛ رسیدگی ادمین لازم است')
    if p.get('institution_receipts',{}).get(field.split('.')[1]):
        return
    if p.get('is_dead'):
        raise HTTPException(409,'کاراکتر طرف قرارداد درگذشته؛ رسیدگی ادمین لازم است')
    if amount < 0:
        p=apply_production(p)
        await players.update_one({'tg_id':m['tg_id'],'created_at':m['created_at']},{'$set':production_fields(p)})
    query={'tg_id':m['tg_id'],'created_at':m['created_at'],field:{'$ne':True}}
    if amount < 0:
        query['resources.gold']={'$gte':-amount}
    result=await players.update_one(query,{'$inc':{'resources.gold':amount},'$set':{field:True}})
    if not result.matched_count:
        raise HTTPException(400,'طلای کافی برای پرداخت این قسط موجود نیست')

async def finish_operation(op):
    """Every money leg and loan installment has a durable replay receipt."""
    if op.get('complete') or op.get('aborted'):
        return
    key=str(op['_id'])
    if op['kind']=='disburse':
        # Recovery must also handle a crash immediately after persisting intent.
        await loans.update_one({'_id':op['loan_id'],'status':'offered','version':op['version']},{'$set':{'status':'disbursing'}})
        loan=await loans.find_one({'_id':op['loan_id']})
        if not loan or loan['status'] not in ('disbursing','active','repaid'):
            raise HTTPException(409,'وضعیت قرارداد با عملیات پرداخت هماهنگ نیست')
        await bank_once(-op['amount'],key+':bank')
        await operations.update_one({'_id':key},{'$set':{'started':True}})
        await player_once(op['recipient'],op['amount'],key+':player')
        await loans.update_one({'_id':op['loan_id'],'status':'disbursing'},{'$set':{'status':'active','started_at':op['at'],'installments':op['installments'],'capital_shares':op.get('capital_shares',[])}})
    elif op['kind']=='repay':
        await player_once(op['payer'],-op['amount'],key+':player')
        await operations.update_one({'_id':key},{'$set':{'started':True}})
        await bank_once(op['amount']-sum(s['amount'] for s in op.get('profit_shares',[])),key+':bank')
        for share in op.get('profit_shares',[]):await player_once(share['person'],share['amount'],key+':profit:'+capital_id(share['person']))
        await loans.update_one({'_id':op['loan_id'],f"installments.{op['index']}.paid":False},{'$set':{f"installments.{op['index']}.paid":True,f"installments.{op['index']}.paid_by":op['payer']['tg_id'],f"installments.{op['index']}.paid_at":op['at']}})
        loan=await loans.find_one({'_id':op['loan_id']})
        if loan and all(i['paid'] for i in loan['installments']):
            await loans.update_one({'_id':op['loan_id'],'status':'active'},{'$set':{'status':'repaid','finished_at':now()}})
    elif op['kind'] in ('deposit','withdraw'):
        if op['kind']=='deposit':
            await player_once(op['person'],-op['amount'],key+':player');await bank_once(op['amount'],key+':bank')
        else:
            await bank_once(-op['amount'],key+':bank');await player_once(op['person'],op['amount'],key+':player')
        await db.institution_bank_capital.update_one({'_id':capital_id(op['person'])},{'$set':{'person':op['person'],'amount':op['capital_after'],**({'next_at':op['at']+timedelta(hours=24)} if op['kind']=='withdraw' else {})}},upsert=True)
    else:
        await bank_once(op['amount'],key+':bank')
    await notice(key,op.get('recipients',[]),op['text'])
    await operations.update_one({'_id':key},{'$set':{'complete':True,'completed_at':game_clock.real_now()}})

async def recover():
    async for op in operations.find({'complete':{'$ne':True},'aborted':{'$ne':True}}):
        try:
            await finish_operation(op)
        except HTTPException as exc:
            await operations.update_one({'_id':op['_id']},{'$set':{'last_error':exc.detail}})
            # An uncommitted debit must not silently happen days later. A debit
            # receipt, rather than the advisory started flag, proves commitment.
            if op['kind'] in ('repay','adjust','deposit','withdraw'):
                personal=op['kind'] in ('repay','deposit')
                source=await (players.find_one({'tg_id':(op.get('payer') or op['person'])['tg_id']}) if personal else treasury())
                namespace='institution_receipts' if personal else 'receipts'
                suffix=':player' if personal else ':bank'
                receipt=hashlib.sha256((str(op['_id'])+suffix).encode()).hexdigest()
                if not (source or {}).get(namespace,{}).get(receipt):
                    await operations.update_one({'_id':op['_id']},{'$set':{'aborted':True}})

async def prepare_operation(op):
    op.setdefault('real_at',game_clock.real_now())
    await operations.update_one({'_id':op['_id']},{'$setOnInsert':op},upsert=True)
    saved=await operations.find_one({'_id':op['_id']})
    await finish_operation(saved)

def public_loan(loan):
    terms=loan.get('terms') or {}
    return {'id':str(loan['_id']),'status':loan['status'],'borrower':{k:loan['borrower'][k] for k in ('tg_id','name')},
            'guarantor':{k:loan['guarantor'][k] for k in ('tg_id','name')} if loan.get('guarantor') else None,
            'requested_amount':loan['requested_amount'],'purpose':loan['purpose'],'collateral':loan.get('collateral',''),'terms':terms,'version':loan.get('version'),
            'borrower_accepted':loan.get('borrower_accepted',False),'guarantor_accepted':loan.get('guarantor_accepted',False),
            'installments':[{'number':i['number'],'amount':i['amount'],'paid':i['paid'],'paid_by':i.get('paid_by'),**deadline_view(i['due_at'])} for i in loan.get('installments',[])],
            'outstanding':0 if loan['status']=='written_off' else sum(i['amount'] for i in loan.get('installments',[]) if not i['paid']),
            'reason':loan.get('reason'), 'created_at':loan['created_at'].isoformat()+'Z'}

@router.get('')
async def catalog(user=Depends(get_user)):
    cfg=await settings()
    from institution_citadel import settings as citadel_settings
    citadel=await citadel_settings()
    available={'iron-bank':cfg['enabled'],'citadel':citadel['enabled']}
    from institution_services import settings as service_settings,KINDS
    for key in KINDS:available[key]=(await service_settings(key))['enabled']
    return [{'id':key,'name':name,'icon':icon,'description':description,'available':available.get(key,False),'implemented':key in available} for key,name,icon,description in CATALOG]

@router.get('/bank')
async def dashboard(page:int=1,user=Depends(get_user)):
    p=await living(user['id']);cfg=await settings()
    is_manager=any(matches(p,m) for m in cfg['managers'])
    query={} if is_manager else {'$or':[{'borrower.tg_id':p['tg_id'],'borrower.created_at':p['created_at']},{'guarantor.tg_id':p['tg_id'],'guarantor.created_at':p['created_at']}]}
    if page<1 or page>10000:raise HTTPException(400,'صفحه نامعتبر است')
    rows=[public_loan(row) async for row in loans.find(query).sort('created_at',-1).skip((page-1)*25).limit(25)]
    capital=await db.institution_bank_capital.find_one({'_id':capital_id(member(p))}) or {}
    return {'capital':capital.get('amount',0),'withdrawal_deadline':deadline_view(capital['next_at']) if capital.get('next_at') else None,'viewer_id':p['tg_id'],'settings':{k:v for k,v in cfg.items() if k!='managers'},'managers':[{'tg_id':m['tg_id'],'name':m['name']} for m in cfg['managers']],
            'is_manager':is_manager,'treasury':(await treasury())['gold'] if is_manager else None,'loans':rows,'page':page,'total':await loans.count_documents(query)}

class RequestLoan(BaseModel):
    request_id:str
    amount:StrictInt=Field(ge=1,le=1000000000)
    purpose:str=Field(min_length=5,max_length=500)
    collateral:str=Field(default='',max_length=300)

@router.post('/bank/requests')
async def request_loan(body:RequestLoan,user=Depends(get_user)):
    p=await living(user['id']);cfg=await settings()
    if not cfg['enabled']:raise HTTPException(400,'بانک فعلاً درخواست تازه نمی‌پذیرد')
    if any(matches(p,m) for m in cfg['managers']):raise HTTPException(403,'مدیر بانک نمی‌تواند از بانک تحت مدیریت خودش وام بگیرد')
    if body.amount>cfg['max_principal']:raise HTTPException(400,'مبلغ از سقف وام بانک بیشتر است')
    key=f"{p['tg_id']}:{p['created_at'].isoformat()}:{request_key(body.request_id)}"
    old=await loans.find_one({'request_key':key})
    if len(body.purpose.strip())<5:raise HTTPException(400,'هدف وام را در دست‌کم پنج حرف بنویس')
    if old:
        if old['requested_amount']!=body.amount or old['purpose']!=body.purpose.strip() or old.get('collateral','')!=body.collateral.strip():raise HTTPException(409,'شناسهٔ تکراری با اطلاعات متفاوت ارسال شده است')
        return public_loan(old)
    doc={'_id':ObjectId(),'request_key':key,'borrower':member(p),'requested_amount':body.amount,'purpose':body.purpose.strip(),'collateral':body.collateral.strip(),'status':'requested','created_at':now()}
    try:await loans.insert_one(doc)
    except DuplicateKeyError:return public_loan(await loans.find_one({'request_key':key}))
    await notice(str(doc['_id'])+':request',[m['tg_id'] for m in cfg['managers']],f"درخواست وام {body.amount} طلا از {p['name']} در بانک آهنین ثبت شد.")
    return public_loan(doc)

class Offer(BaseModel):
    principal:StrictInt=Field(ge=1,le=1000000000)
    interest_percent:StrictInt=Field(ge=0,le=100)
    installment_count:StrictInt=Field(ge=1,le=24)
    interval_hours:StrictInt=Field(ge=1,le=720)
    guarantor_id:StrictInt|None=None

@router.post('/bank/loans/{loan_id}/offer')
async def offer(loan_id:str,body:Offer,user=Depends(get_user)):
    p,cfg=await manager(user)
    if not cfg['enabled']:raise HTTPException(400,'بانک غیرفعال است')
    loan=await loans.find_one({'_id':oid(loan_id),'status':{'$in':['requested','offered']}})
    if not loan:raise HTTPException(409,'درخواست برای پیشنهاد تازه در دسترس نیست')
    borrower=await living(loan['borrower']['tg_id'])
    if not matches(borrower,loan['borrower']):raise HTTPException(409,'کاراکتر وام‌گیرنده تغییر کرده است')
    if any(matches(borrower,m) for m in cfg['managers']):raise HTTPException(403,'وام‌دادن به مدیر بانک مجاز نیست')
    if body.principal>cfg['max_principal'] or body.interest_percent>cfg['max_interest_percent'] or body.installment_count>cfg['max_installments'] or not cfg['min_interval_hours']<=body.interval_hours<=cfg['max_interval_hours']:
        raise HTTPException(400,'شرایط پیشنهادی خارج از حدود تنظیم‌شدهٔ بانک است')
    if cfg['require_guarantor'] and body.guarantor_id is None and not loan.get('collateral','').strip():raise HTTPException(400,'برای این وام ضامن یا وثیقهٔ پیشنهادی لازم است')
    guarantor=await living(body.guarantor_id) if body.guarantor_id is not None else None
    if guarantor and guarantor['tg_id']==borrower['tg_id']:raise HTTPException(400,'وام‌گیرنده نمی‌تواند ضامن خودش باشد')
    schedule(body.principal,body.interest_percent,body.installment_count,body.interval_hours,now())
    terms={k:v for k,v in body.model_dump().items() if k!='guarantor_id'}
    terms.update({'grace_hours':cfg['grace_hours'],'total_repayment':sum(i['amount'] for i in schedule(body.principal,body.interest_percent,body.installment_count,body.interval_hours,now()))})
    change={'terms':terms,'guarantor':member(guarantor) if guarantor else None,'status':'offered','version':str(uuid4()),'borrower_accepted':False,'guarantor_accepted':False,'offered_by':p['tg_id']}
    await loans.update_one({'_id':loan['_id'],'status':{'$in':['requested','offered']}},{'$set':change})
    await audit('offer',user['id'],{'loan':loan_id,**terms})
    await notice(loan_id+':'+change['version'],[borrower['tg_id']]+([guarantor['tg_id']] if guarantor else []),'پیشنهاد تازهٔ بانک آهنین آماده است؛ مبلغ، اقساط و مسئولیت ضامن را در صفحهٔ نهادها بررسی کن.')
    return public_loan({**loan,**change})

class Acceptance(BaseModel):
    version:str
    accepted:StrictBool

async def activate(loan):
    if not loan.get('borrower_accepted') or (loan.get('guarantor') and not loan.get('guarantor_accepted')):return
    cfg=await settings()
    if not cfg['enabled']:raise HTTPException(400,'بانک غیرفعال است؛ پرداخت وام متوقف شد')
    borrower=await living(loan['borrower']['tg_id'])
    if not matches(borrower,loan['borrower']) or any(matches(borrower,m) for m in cfg['managers']):raise HTTPException(403,'پرداخت وام به این کاراکتر مجاز نیست')
    if loan.get('guarantor'):
        if not matches(await living(loan['guarantor']['tg_id']),loan['guarantor']):raise HTTPException(409,'کاراکتر ضامن تغییر کرده است')
    terms=loan['terms'];at=now()
    if (await treasury())['gold']<terms['principal']:raise HTTPException(409,'خزانهٔ بانک برای پرداخت وام کافی نیست؛ پس از تأمین خزانه دوباره تأیید کن')
    op={'_id':str(loan['_id'])+':disburse','kind':'disburse','loan_id':loan['_id'],'version':loan['version'],'recipient':loan['borrower'],'amount':terms['principal'],'at':at,'complete':False,
        'real_at':game_clock.real_now(),'actor':loan.get('offered_by'),
        'installments':schedule(terms['principal'],terms['interest_percent'],terms['installment_count'],terms['interval_hours'],at),
        'recipients':[loan['borrower']['tg_id']]+([loan['guarantor']['tg_id']] if loan.get('guarantor') else []),'text':f"وام {terms['principal']} طلایی بانک آهنین پرداخت شد. مبلغ کل بازپرداخت {terms['total_repayment']} طلا است؛ اقساط در صفحهٔ نهادها نمایش داده می‌شوند."}
    op['capital_shares']=await capital_snapshot()
    # Intent precedes state and money, so restart recovery can finish the same loan.
    await operations.update_one({'_id':op['_id']},{'$setOnInsert':op},upsert=True)
    await loans.update_one({'_id':loan['_id'],'status':'offered'},{'$set':{'status':'disbursing'}})
    await finish_operation(await operations.find_one({'_id':op['_id']}))

@router.post('/bank/loans/{loan_id}/accept')
async def accept(loan_id:str,body:Acceptance,user=Depends(get_user)):
    p=await living(user['id']);loan=await loans.find_one({'_id':oid(loan_id)})
    if not loan or loan['status'] not in ('offered','active','disbursing','repaid') or loan.get('version')!=body.version:raise HTTPException(409,'پیشنهاد تغییر کرده؛ قرارداد را تازه کن')
    role='borrower' if matches(p,loan['borrower']) else 'guarantor' if loan.get('guarantor') and matches(p,loan['guarantor']) else None
    if not role:raise HTTPException(403,'این قرارداد مربوط به تو نیست')
    if loan['status']!='offered':return public_loan(loan)
    if not body.accepted:
        await loans.update_one({'_id':loan['_id'],'status':'offered','version':body.version},{'$set':{'status':'declined','reason':f'رد توسط {role}'}})
        await audit('decline',user['id'],{'loan':loan_id,'role':role,'version':body.version})
        return {'ok':True}
    await loans.update_one({'_id':loan['_id'],'status':'offered','version':body.version},{'$set':{role+'_accepted':True,role+'_accepted_at':game_clock.real_now()}})
    await audit('accept',user['id'],{'loan':loan_id,'role':role,'version':body.version})
    loan=await loans.find_one({'_id':loan['_id']});await activate(loan)
    return public_loan(await loans.find_one({'_id':loan['_id']}))

async def pay_installment(loan,index,payer):
    # Refresh: a replay of an old dashboard must never collect a paid installment.
    loan=await loans.find_one({'_id':loan['_id']})
    if not loan or loan['status']!='active':return
    i=loan['installments'][index]
    if i['paid']:return
    prefix=f"{loan['_id']}:repay:{index}"
    pending=await operations.find_one({'loan_id':loan['_id'],'kind':'repay','index':index,'complete':{'$ne':True},'aborted':{'$ne':True}})
    if pending:
        await finish_operation(pending);return
    key=f"{prefix}:{payer['tg_id']}"
    existing=await operations.find_one({'_id':key})
    if existing and not existing.get('aborted'):
        await finish_operation(existing);return
    if existing:
        key=f'{prefix}:{payer["tg_id"]}:{uuid4()}'
    current=await players.find_one({'tg_id':payer['tg_id']})
    if not matches(current,payer) or current.get('is_dead'):raise HTTPException(409,'کاراکتر پرداخت‌کننده تغییر کرده یا درگذشته است')
    current=apply_production(current)
    if current.get('resources',{}).get('gold',0)<i['amount']:raise HTTPException(400,'طلا برای پرداخت کامل این قسط کافی نیست')
    shares=loan.get('capital_shares',[])
    total=loan['terms']['total_repayment'];principal=loan['terms']['principal'];before=sum(x['amount'] for x in loan['installments'][:index])
    principal_part=(before+i['amount'])*principal//total-before*principal//total
    profit=weighted_split(i['amount']-principal_part,shares)
    await prepare_operation({'_id':key,'kind':'repay','loan_id':loan['_id'],'payer':payer,'amount':i['amount'],'profit_shares':profit,'index':index,'at':now(),'complete':False,
        'actor':payer['tg_id'],
        'recipients':[loan['borrower']['tg_id']]+([loan['guarantor']['tg_id']] if loan.get('guarantor') else []),'text':f"قسط {i['number']} وام بانک آهنین به مبلغ {i['amount']} طلا توسط {payer['name']} پرداخت شد."})

class Payment(BaseModel):
    number:StrictInt=Field(ge=1,le=24)

@router.post('/bank/loans/{loan_id}/pay')
async def pay_next(loan_id:str,body:Payment,user=Depends(get_user)):
    p=await living(user['id']);loan=await loans.find_one({'_id':oid(loan_id),'status':'active'})
    if not loan:raise HTTPException(409,'وام فعالی پیدا نشد')
    if not matches(p,loan['borrower']):raise HTTPException(403,'فقط وام‌گیرنده می‌تواند پرداخت زودتر از موعد را انجام دهد')
    index=next((n for n,i in enumerate(loan['installments']) if not i['paid']),None)
    if index is not None:
        if loan['installments'][index]['number']!=body.number:raise HTTPException(409,'این قسط قبلاً پرداخت شده؛ قرارداد را تازه کن')
        await pay_installment(loan,index,loan['borrower'])
    return public_loan(await loans.find_one({'_id':loan['_id']}))

async def tick():
    await recover()
    if game_clock.paused():return
    async for loan in loans.find({'status':'active'}):
        for index,i in enumerate(loan.get('installments',[])):
            if i['paid'] or i['due_at']>now():continue
            try:
                await pay_installment(loan,index,loan['borrower'])
            except HTTPException:
                if loan.get('guarantor') and now()>=i['due_at']+timedelta(hours=loan['terms']['grace_hours']):
                    try:await pay_installment(loan,index,loan['guarantor'])
                    except HTTPException:
                        await notice(f"{loan['_id']}:overdue:{index}",[loan['borrower']['tg_id'],loan['guarantor']['tg_id']],'قسط وام بانک آهنین معوق است؛ وام‌گیرنده و ضامن طلای کافی نداشتند یا کاراکترشان تغییر کرده است.')
                else:
                    await notice(f"{loan['_id']}:due:{index}",[loan['borrower']['tg_id']],'قسط وام بانک آهنین سررسید شد و پرداخت انجام نشد. پیش از پایان فرصت جبران، موجودی طلا را تأمین کن.')

class BankSettings(BaseModel):
    enabled:StrictBool
    max_principal:StrictInt=Field(ge=1,le=1000000000)
    max_interest_percent:StrictInt=Field(ge=0,le=100)
    max_installments:StrictInt=Field(ge=1,le=24)
    min_interval_hours:StrictInt=Field(ge=1,le=720)
    max_interval_hours:StrictInt=Field(ge=1,le=720)
    grace_hours:StrictInt=Field(ge=1,le=720)
    require_guarantor:StrictBool
    member_limit:StrictInt=Field(default=5,ge=1,le=100)
    manager_ids:list[StrictInt]=Field(max_length=100)

@router.get('/admin/bank')
async def admin_dashboard(page:int=1,user=Depends(admin)):
    if page<1 or page>10000:raise HTTPException(400,'صفحه نامعتبر است')
    cfg=await settings()
    return {'settings':{**cfg,'managers':[{'tg_id':m['tg_id'],'name':m['name']} for m in cfg['managers']]},'treasury':(await treasury())['gold'],
            'loans':[public_loan(row) async for row in loans.find({}).sort('created_at',-1).skip((page-1)*25).limit(25)],'page':page,'total':await loans.count_documents({})}

@router.put('/admin/bank/settings')
async def save_settings(body:BankSettings,user=Depends(admin)):
    if body.min_interval_hours>body.max_interval_hours:raise HTTPException(400,'حداقل فاصلهٔ اقساط از حداکثر بیشتر است')
    if len(set(body.manager_ids))>body.member_limit:raise HTTPException(400,'تعداد اعضا از سقف بانک بیشتر است')
    managers=[member(await living(uid)) for uid in set(body.manager_ids)]
    cfg={k:v for k,v in body.model_dump().items() if k!='manager_ids'};cfg['managers']=managers
    await game_settings.update_one({'_id':'iron_bank'},{'$set':{'settings':cfg,'changed_by':user['id'],'changed_at':game_clock.real_now()}},upsert=True)
    await audit('settings',user['id'],{**cfg,'managers':[m['tg_id'] for m in managers]})
    return {'ok':True}

class TreasuryChange(BaseModel):
    request_id:str
    amount:StrictInt=Field(ge=-1000000000,le=1000000000)
    reason:str=Field(min_length=3,max_length=500)

@router.post('/admin/bank/treasury')
async def change_treasury(body:TreasuryChange,user=Depends(admin)):
    if not body.amount or len(body.reason.strip())<3:raise HTTPException(400,'مبلغ غیرصفر و دلیل اصلاح لازم است')
    key='treasury:'+request_key(body.request_id)
    old=await operations.find_one({'_id':key})
    if old and (old['amount']!=body.amount or old.get('reason')!=body.reason.strip() or old.get('actor')!=user['id']):
        raise HTTPException(409,'شناسهٔ تکراری با اطلاعات متفاوت ارسال شده است')
    if old and old.get('aborted'):raise HTTPException(409,'این درخواست ناموفق بسته شده؛ درخواست تازه ثبت کن')
    if not old and body.amount<0 and (await treasury())['gold']<-body.amount:raise HTTPException(409,'خزانه طلای کافی ندارد')
    await prepare_operation({'_id':key,'kind':'adjust','amount':body.amount,'actor':user['id'],'reason':body.reason.strip(),'at':now(),'complete':False,'recipients':[],'text':''})
    return {'gold':(await treasury())['gold']}

class Decision(BaseModel):
    reason:str=Field(min_length=3,max_length=500)

@router.post('/admin/bank/loans/{loan_id}/reject')
async def admin_reject(loan_id:str,body:Decision,user=Depends(admin)):
    if len(body.reason.strip())<3:raise HTTPException(400,'دلیل رد را بنویس')
    pending=await operations.find_one({'loan_id':oid(loan_id),'complete':{'$ne':True},'aborted':{'$ne':True}})
    if pending:raise HTTPException(409,'عملیات مالی ناتمام است؛ ابتدا باید تکمیل شود')
    result=await loans.update_one({'_id':oid(loan_id),'status':{'$in':['requested','offered']}},{'$set':{'status':'rejected','reason':body.reason}})
    if not result.matched_count:raise HTTPException(409,'این درخواست قابل رد نیست')
    await audit('reject',user['id'],{'loan':loan_id,'reason':body.reason})
    return {'ok':True}

@router.post('/bank/loans/{loan_id}/reject')
async def reject(loan_id:str,body:Decision,user=Depends(get_user)):
    await manager(user)
    if len(body.reason.strip())<3:raise HTTPException(400,'دلیل رد را بنویس')
    result=await loans.update_one({'_id':oid(loan_id),'status':{'$in':['requested','offered']}},{'$set':{'status':'rejected','reason':body.reason}})
    if not result.matched_count:raise HTTPException(409,'این درخواست قابل رد نیست')
    await audit('reject',user['id'],{'loan':loan_id,'reason':body.reason})
    return {'ok':True}

@router.post('/admin/bank/loans/{loan_id}/writeoff')
async def writeoff(loan_id:str,body:Decision,user=Depends(admin)):
    if len(body.reason.strip())<3:raise HTTPException(400,'دلیل بخشودگی را بنویس')
    pending=await operations.find_one({'loan_id':oid(loan_id),'complete':{'$ne':True},'aborted':{'$ne':True}})
    if pending:raise HTTPException(409,'عملیات مالی ناتمام است؛ ابتدا باید تکمیل شود')
    result=await loans.update_one({'_id':oid(loan_id),'status':'active'},{'$set':{'status':'written_off','reason':body.reason,'written_off_by':user['id'],'finished_at':now()}})
    if not result.matched_count:raise HTTPException(409,'فقط بدهی وام فعال قابل بخشودگی است')
    await audit('writeoff',user['id'],{'loan':loan_id,'reason':body.reason})
    return {'ok':True}

@router.get('/admin/bank/audit')
async def history(user=Depends(admin)):
    financial=[{'id':str(op['_id']),'event':op['kind'],'amount':op['amount'],'actor':op.get('actor'),'reason':op.get('reason'),'complete':op.get('complete',False),'aborted':op.get('aborted',False),'error':op.get('last_error'),'loan_id':str(op['loan_id']) if op.get('loan_id') else None,'party':(op.get('payer') or op.get('recipient') or {}).get('name'),'at':op.get('completed_at',op['at']).isoformat()+'Z'} async for op in operations.find({}).sort('at',-1).limit(100)]
    changes=[{'event':op['event'],'actor':op['actor'],'details':op['details'],'at':op['at'].isoformat()+'Z'} async for op in db.institution_audit.find({'institution':'iron-bank'}).sort('at',-1).limit(100)]
    return {'financial':financial,'changes':changes}

async def ensure_indexes():
    await loans.create_index('request_key',unique=True)
    await loans.create_index([('status',1),('created_at',-1)])
    await operations.create_index([('complete',1),('at',1)])
