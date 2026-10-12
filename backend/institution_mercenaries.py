"""Admin-approved, fixed-term armies with surviving-force return."""
from datetime import timedelta
from uuid import uuid4
from bson import ObjectId
from fastapi import APIRouter,Depends,HTTPException
from pydantic import BaseModel,Field,StrictInt
from auth import get_user
from db import db,campaigns,players
from game import now,owned_castles
from army_upkeep import food_rate
from time_management import deadline_view
from institution_bank import living,member,matches,admin,oid,request_key,notice
import institution_services as services
import institution_finance as money
import game_data

router=APIRouter(prefix='/api/institutions',tags=['golden-company'])
offers=db.institution_mercenary_offers
contracts=db.institution_mercenary_contracts

def troop_catalog():
    return {**game_data.COMMON_TROOPS,**game_data.NAVAL_TROOPS,**{name:{'name':name,'power':game_data.GAME_RULES.get('special_troop_power',5)} for r in game_data.REGIONS.values() for name in r['special']}}

def composition(troops,equipment):
    allowed=troop_catalog()
    if any(k not in allowed or type(v) is not int or v<0 or v>100000 for k,v in troops.items()):raise HTTPException(400,'نوع یا تعداد نیرو معتبر نیست')
    if any(k not in game_data.SIEGE_EQUIPMENT or type(v) is not int or v<0 or v>10000 for k,v in equipment.items()):raise HTTPException(400,'نوع یا تعداد ادوات معتبر نیست')
    ts={k:v for k,v in troops.items() if v};eq={k:v for k,v in equipment.items() if v}
    if not ts:raise HTTPException(400,'لشکر باید حداقل یک نیرو داشته باشد')
    return ts,eq
def public(row):return {**{k:row.get(k) for k in ('name','description','troops','equipment','price','duration_hours','status','version','result')},'id':str(row['_id']),'seller':{'tg_id':row['seller']['tg_id'],'name':row['seller']['name']}}
def contract_public(row):return {'id':str(row['_id']),'name':row['name'],'seller':row['seller']['name'],'buyer':row['buyer']['name'],'buyer_id':row['buyer']['tg_id'],'seller_id':row['seller']['tg_id'],'status':row['status'],'castle':row['castle'],'deadline':deadline_view(row['expires_at']),'army_id':str(row['army_id']),'scenario_requested':row.get('scenario_requested',False)}
@router.get('/golden-company')
async def dashboard(page:int=1,user=Depends(get_user)):
    p=await living(user['id']);cfg=await services.settings('golden-company');is_manager=any(matches(p,m) for m in cfg['managers'])
    if not 1<=page<=10000:raise HTTPException(400,'صفحه نامعتبر است')
    q={'status':'listed'} if not is_manager else {'$or':[{'status':'listed'},{'seller.tg_id':p['tg_id'],'seller.created_at':p['created_at']}]}
    rows=[public(r) async for r in offers.find(q).sort('created_at',-1).skip((page-1)*25).limit(25)]
    cq={'$or':[{'buyer.tg_id':p['tg_id'],'buyer.created_at':p['created_at']},{'seller.tg_id':p['tg_id'],'seller.created_at':p['created_at']}]}
    return {'settings':{k:v for k,v in cfg.items() if k!='managers'},'viewer_id':p['tg_id'],'is_manager':is_manager,'offers':rows,'contracts':[contract_public(r) async for r in contracts.find(cq).sort('created_at',-1).limit(100)],'castles':owned_castles(p),'troops':{k:v['name'] for k,v in troop_catalog().items()},'equipment':{k:v['name'] for k,v in game_data.SIEGE_EQUIPMENT.items()},'page':page,'total':await offers.count_documents(q)}
class Listing(BaseModel):
    request_id:str
    name:str=Field(min_length=3,max_length=60)
    description:str=Field(min_length=10,max_length=2000)
    troops:dict[str,StrictInt]=Field(max_length=50)
    equipment:dict[str,StrictInt]=Field(default_factory=dict,max_length=20)
    price:StrictInt=Field(ge=1,le=10**9)
    duration_hours:StrictInt=Field(ge=1,le=720)
@router.post('/golden-company/offers')
async def create(body:Listing,user=Depends(get_user)):
    p,cfg=await services.manager('golden-company',user)
    if not cfg['enabled']:raise HTTPException(400,'ثبت لشکر تازه متوقف است')
    troops,equipment=composition(body.troops,body.equipment);name=services.clean(body.name);description=services.clean(body.description,10)
    key=f"mercenary:{p['tg_id']}:{p['created_at'].isoformat()}:{request_key(body.request_id)}"
    old=await offers.find_one({'request_key':key})
    payload={'name':name,'description':description,'troops':troops,'equipment':equipment,'price':body.price,'duration_hours':body.duration_hours}
    if old:
        if any(old[k]!=v for k,v in payload.items()):raise HTTPException(409,'شناسهٔ تکراری با اطلاعات متفاوت')
        return public(old)
    if await offers.count_documents({'seller.tg_id':p['tg_id'],'status':{'$in':['pending','listed','hired']}})>=cfg['max_open_per_player']:raise HTTPException(400,'سقف لشکرهای ثبت‌شده تکمیل است')
    row={'_id':ObjectId(),**payload,'seller':member(p),'request_key':key,'status':'pending','version':str(uuid4()),'created_at':now()}
    await offers.insert_one(row)
    await services.notify_admins('institution_mercenaries','لشکر مزدوری منتظر تأیید است',name,dedupe_key='mercenary:'+str(row['_id']),source_id=str(row['_id']),player_name=p['name'],player_tg_id=p['tg_id'],action='مدیریت نهادها ← گروهان طلایی',audience_roles=('owner','full'))
    return public(row)
@router.get('/admin/golden-company')
async def admin_dashboard(page:int=1,user=Depends(admin)):
    if not 1<=page<=10000:raise HTTPException(400,'صفحه نامعتبر است')
    cfg=await services.settings('golden-company')
    return {'settings':{**cfg,'managers':[{'tg_id':m['tg_id'],'name':m['name']} for m in cfg['managers']]},'offers':[public(r) async for r in offers.find({}).sort('created_at',-1).skip((page-1)*25).limit(25)],'contracts':[contract_public(r) async for r in contracts.find({}).sort('created_at',-1).limit(100)],'troops':{k:v['name'] for k,v in troop_catalog().items()},'equipment':{k:v['name'] for k,v in game_data.SIEGE_EQUIPMENT.items()},'total':await offers.count_documents({}),'page':page}
class Approval(services.Revision):
    approved:bool
    result:str=Field(min_length=3,max_length=2000)
@router.post('/admin/golden-company/offers/{offer_id}/review')
async def review(offer_id:str,body:Approval,user=Depends(admin)):
    row=await offers.find_one({'_id':oid(offer_id),'version':body.version,'status':{'$in':['pending','listed']}})
    if not row:raise HTTPException(409,'وضعیت پیشنهاد تغییر کرده است')
    fields={'status':'listed' if body.approved else 'rejected','version':str(uuid4()),'result':services.clean(body.result)}
    await offers.update_one({'_id':row['_id'],'version':body.version},{'$set':fields})
    await services.audit('golden-company','listing_review',user['id'],{'offer':offer_id,**fields})
    return {'ok':True}
class Purchase(services.Revision):
    request_id:str
    castle:str=Field(min_length=1,max_length=100)
@router.post('/golden-company/offers/{offer_id}/buy')
async def buy(offer_id:str,body:Purchase,user=Depends(get_user)):
    p=await living(user['id']);cfg=await services.settings('golden-company');key=f"hire:{p['tg_id']}:{p['created_at'].isoformat()}:{request_key(body.request_id)}"
    pending=await money.operations.find_one({'_id':key})
    if pending:
        if pending.get('offer_id')!=offer_id or pending.get('castle')!=body.castle:raise HTTPException(409,'خرید تکراری با اطلاعات متفاوت')
        if pending.get('aborted'):raise HTTPException(409,'این خرید ناموفق بود؛ درخواست تازه ثبت کن')
        await money.finish(pending);return contract_public(await contracts.find_one({'request_key':key}))
    old=await contracts.find_one({'request_key':key})
    if old:
        if str(old['offer_id'])!=offer_id or old['castle']!=body.castle:raise HTTPException(409,'خرید تکراری با اطلاعات متفاوت')
        await money.recover();return contract_public(old)
    if not cfg['enabled']:raise HTTPException(400,'فروش لشکر متوقف است')
    offer=await offers.find_one({'_id':oid(offer_id),'status':'listed','version':body.version})
    if not offer:raise HTTPException(409,'این لشکر دیگر برای خرید موجود نیست')
    seller=await living(offer['seller']['tg_id'])
    if not matches(seller,offer['seller']) or not any(matches(seller,m) for m in cfg['managers']):raise HTTPException(409,'فروشنده دیگر عضو فعال گروهان نیست')
    if matches(p,offer['seller']):raise HTTPException(400,'خرید لشکر خودت مجاز نیست')
    if body.castle not in owned_castles(p):raise HTTPException(400,'قلعهٔ محل استقرار باید متعلق به خودت باشد')
    # Ships require a coastal origin, matching the normal campaign constraints.
    if any(k in game_data.NAVAL_TROOPS for k in offer['troops']):
        from routers.war import all_castle_terrain
        terrain=await all_castle_terrain()
        if terrain.get(body.castle,'land')=='land':raise HTTPException(400,'لشکر دارای کشتی باید در قلعهٔ بندری مستقر شود')
    await money.enough(member(p),{'gold':offer['price']})
    cid=ObjectId();aid=ObjectId();at=now();troops=offer['troops'];equipment=offer['equipment'];expires=at+timedelta(hours=offer['duration_hours'])
    power=sum(v*troop_catalog()[k]['power'] for k,v in troops.items())
    equipment_power=sum(v*game_data.SIEGE_EQUIPMENT[k]['siege_power'] for k,v in equipment.items())
    army={'tg_id':p['tg_id'],'player_name':p['name'],'player_gender':p.get('gender','lord'),'name':offer['name'],'origin_castle':body.castle,'target_castle':body.castle,'op_type':'garrison','troops':troops,'equipment':equipment,'power':power,'equipment_power':equipment_power,'men_committed':sum(v for k,v in troops.items() if k not in game_data.NAVAL_TROOPS),'gold_cost':0,'equipment_cost':{},'naval_material_costs':{},'food_per_day':food_rate(troops),'travel_minutes':0,'route_path':[body.castle],'route_edge_minutes':[],'arrival_at':at,'arrival_notified':True,'active':True,'created_at':at,'last_food_tick':at,'commander_present':False,'item_ids':[],'war_items':[],'mercenary_contract_id':str(cid),'mercenary_expires_at':expires}
    contract={'_id':cid,'request_key':key,'offer_id':offer['_id'],'army_id':aid,'seller':offer['seller'],'buyer':member(p),'name':offer['name'],'castle':body.castle,'status':'activating','created_at':at,'expires_at':expires}
    effects=[{'collection':'campaigns','id':aid,'insert':army},money.effect(offers.name,offer['_id'],{'status':'hired','version':str(uuid4())}),{'collection':contracts.name,'id':cid,'insert':{k:v for k,v in {**contract,'status':'active'}.items() if k!='_id'}}]
    await money.transfer(key,[money.player_leg(member(p),{'gold':-offer['price']}),money.player_leg(offer['seller'],{'gold':offer['price']})],effects,institution='golden-company',event='hire',actor=p['tg_id'],offer_id=offer_id,castle=body.castle)
    await notice(key,[p['tg_id'],seller['tg_id']],f"قرارداد لشکر «{offer['name']}» آغاز شد؛ استقرار در {body.castle}.")
    return contract_public({**contract,'status':'active'})

@router.post('/golden-company/contracts/{contract_id}/scenario')
async def scenario(contract_id:str,body:services.Request,user=Depends(get_user)):
    p=await living(user['id']);row=await contracts.find_one({'_id':oid(contract_id),'status':{'$in':['active','waiting_return']}})
    if not row or not matches(p,row['buyer']):raise HTTPException(403,'این قرارداد متعلق به تو نیست')
    old=await services.cases.find_one({'mercenary_contract_id':contract_id})
    if old:return services.public(old,p)
    case={'_id':ObjectId(),'request_key':'mercenary-scenario:'+contract_id,'mercenary_contract_id':contract_id,'institution':'golden-company','kind':'army-scenario','title':services.clean(body.title),'description':services.clean(body.description,20),'resources':{},'requester':member(p),'assigned':row['seller'],'assigned_id':row['seller']['tg_id'],'assigned_name':row['seller']['name'],'status':'working','version':str(uuid4()),'real_at':services.game_clock.real_now()}
    await services.cases.insert_one(case);await contracts.update_one({'_id':row['_id']},{'$set':{'scenario_requested':True}})
    await notice('mercenary-scenario:'+contract_id,[row['seller']['tg_id']],f"درخواست سناریو برای لشکر «{row['name']}» ثبت شد.")
    return services.public(case,p)

async def return_contract(row,early=False):
    army=await campaigns.find_one({'_id':row['army_id']})
    if army:
        from routers.war import campaign_waiting_for_result,repair_stale_engagement_lock
        army=await repair_stale_engagement_lock(army)
        if army.get('engagement_locked') or campaign_waiting_for_result(army):
            await contracts.update_one({'_id':row['_id']},{'$set':{'status':'waiting_return'}});return False
    troops={k:max(0,int(v)) for k,v in (army or {}).get('troops',{}).items() if int(v)>0}
    equipment={k:max(0,int(v)) for k,v in (army or {}).get('equipment',{}).items() if int(v)>0}
    effects=[money.effect('campaigns',row['army_id'],{'active':False,'status':'contract_returned','troops':{},'equipment':{},'men_committed':0,'power':0,'food_per_day':0}),money.effect(offers.name,row['offer_id'],{'status':'listed' if troops else 'exhausted','troops':troops,'equipment':equipment,'version':str(uuid4())}),money.effect(contracts.name,row['_id'],{'status':'returned','returned_at':now()})]
    await money.transfer('mercenary-return:'+str(row['_id']),[],effects,institution='golden-company',event='return',actor=row['buyer']['tg_id'])
    await notice('mercenary-return:'+str(row['_id']),[row['buyer']['tg_id'],row['seller']['tg_id']],'قرارداد لشکر پایان یافت؛ فقط بازمانده‌ها به فهرست گروهان برگشتند.')
    return True
@router.post('/golden-company/contracts/{contract_id}/return')
async def return_early(contract_id:str,user=Depends(get_user)):
    p=await living(user['id']);row=await contracts.find_one({'_id':oid(contract_id),'status':'active'})
    if not row or not matches(p,row['buyer']):raise HTTPException(403,'قرارداد قابل بازگشت متعلق به تو نیست')
    if not await return_contract(row,True):raise HTTPException(409,'لشکر درگیر است؛ بازگشت پس از نتیجه انجام می‌شود')
    return {'ok':True}
@router.post('/admin/golden-company/contracts/{contract_id}/end')
async def admin_end(contract_id:str,user=Depends(admin)):
    row=await contracts.find_one({'_id':oid(contract_id),'status':{'$in':['active','waiting_return']}})
    if not row:raise HTTPException(409,'قرارداد فعال پیدا نشد')
    await contracts.update_one({'_id':row['_id']},{'$set':{'expires_at':now()}})
    returned=await return_contract(row,True)
    await services.audit('golden-company','end',user['id'],{'contract':contract_id,'returned':returned})
    return {'ok':True,'waiting_battle':not returned}
async def tick():
    async for row in contracts.find({'status':{'$in':['active','waiting_return']},'$or':[{'expires_at':{'$lte':now()}},{'status':'waiting_return'}]}):await return_contract(row)
async def ensure_indexes():
    await offers.create_index('request_key',unique=True);await contracts.create_index('request_key',unique=True)
