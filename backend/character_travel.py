"""Character visits, private admission, and captivity. Serialized by game_state_lock.

Location identity is tied to a character, not a Telegram account. Durable family
operations atomically receipt charges and replay absolute domain writes.
"""
from datetime import timedelta
from uuid import uuid4
from fastapi import HTTPException
from db import db, players, campaigns
from game import now, owned_castles
from game_data import TRAVEL_GRAPH, _dijkstra_path
from family import key, commit, change, member_for, recover, notice
import game_clock

locations = db.character_locations
trips = db.character_trips
captures = db.character_captures
places = db.character_places
ATTACK_OP_TYPES = {'attack','siege','naval_raid'}
INSTITUTIONS = {'iron-bank':'بانک آهنین','citadel':'سیتادل','golden-company':'گروهان طلایی','alchemists':'صنف کیمیاگران','faceless':'بی‌چهره‌ها','faith':'ایمان هفت','watch':'نگهبانان شب'}

def clean(row):
    return {('id' if k == '_id' else k): v for k,v in row.items()}

async def living(uid):
    p = await players.find_one({'tg_id':uid})
    if not p or p.get('is_dead') or p.get('registration_reset') or not (p.get('castle') or p.get('landless')):
        raise HTTPException(403,'کاراکتر زنده و تأییدشده لازم است')
    return p

async def state(p):
    ident = key(p)
    row = await locations.find_one({'_id':ident})
    if not row:
        row = {'_id':ident,'tg_id':p['tg_id'],'name':p['name'],'place':p.get('castle'), 'previous':None,'trip':None,'captive':None}
        await locations.update_one({'_id':ident},{'$setOnInsert':row},upsert=True)
    return row

async def owner(node):
    return await players.find_one({'is_dead':{'$ne':True},'registration_reset':{'$ne':True},'$or':[{'castle':node},{f'castle_buildings.{node}':{'$exists':True}}]})

async def destination(ident):
    custom = await places.find_one({'_id':ident,'enabled':True})
    if custom: return custom
    if ident in TRAVEL_GRAPH: return {'_id':ident,'name':ident,'node':ident,'kind':'castle'}
    raise HTTPException(400,'مقصد در نقشه تعریف نشده است')

async def member_ids(institution):
    from institution_bank import matches
    setting_id = {'iron-bank':'iron_bank','citadel':'citadel'}.get(institution,'institution_'+institution)
    cfg = await db.game_settings.find_one({'_id':setting_id}) or {}
    members = cfg.get('settings',{}).get('managers',[])
    result=[]
    for m in members:
        p=await players.find_one({'tg_id':m['tg_id']})
        if matches(p,m) and not p.get('is_dead') and not p.get('registration_reset'):result.append(p['tg_id'])
    return result

async def gates(dest):
    result={}
    lord=await owner(dest['node'])
    if lord:result['owner']=[lord['tg_id']]
    if dest.get('institution'):result['institution']=await member_ids(dest['institution'])
    return result

def accepted(required, approvals):
    return all(set(group).intersection(approvals) for group in required.values())

async def blocked(place):
    if not place:return False
    dest=await destination(place)
    node=dest['node']
    return bool(await campaigns.find_one({'active':True,'combat_resolved_at':{'$exists':False},'battle_cancelled_at':{'$exists':False},'$or':[
        {'battle_location':node,'engagement_locked':True},
        {'target_castle':node,'op_type':{'$in':list(ATTACK_OP_TYPES)},'arrival_at':{'$lte':now()}}
    ]}))

async def commanding(subject):
    """Return the active army assignment that keeps a character with its troops."""
    return await campaigns.find_one({
        'active': True,
        'commander.key': subject,
        'commander.status': 'accepted',
    }, {'_id': 1, 'name': 1})

async def kids(p,s):
    result=[]
    async for c in db.family_children.find({'status':'alive','$or':[{'parent_keys':key(p)},{'patron_key':key(p)}]}):
        loc=await locations.find_one({'_id':'child:'+c['_id']})
        if not loc:
            patron=await players.find_one({'tg_id':c['patron_id']})
            ps=await state(patron) if patron and key(patron)==c['patron_key'] else {}
            loc={'_id':'child:'+c['_id'],'name':c['name'],'place':ps.get('place'),'trip':None,'captive':None,'child_id':c['_id']}
            await locations.update_one({'_id':loc['_id']},{'$setOnInsert':loc},upsert=True)
        result.append({**clean(loc),'available':not loc.get('captive') and loc.get('place')==s.get('place') and loc.get('trip')==s.get('trip')})
    return result

def remaining_segments(trip,at):
    elapsed=max(0,(at-trip['started_at']).total_seconds()/60)
    for seg in trip['segments']:
        if elapsed < seg['minutes']:
            return seg, elapsed
        elapsed-=seg['minutes']
    return None,0

def route(origin,target,old=None):
    if target not in TRAVEL_GRAPH:raise HTTPException(400,'مقصد باید به مسیرهای نقشه متصل باشد')
    candidates=[]
    if old:
        seg,elapsed=remaining_segments(old,now())
        if seg:
            start=seg.get('start_position',0)
            end=seg.get('end_position',1)
            position=start+(end-start)*elapsed/seg['minutes'] if seg['minutes'] else end
            edge_minutes=TRAVEL_GRAPH[seg['a']][seg['b']]
            for endpoint,minutes,end_position in ((seg['a'],position*edge_minutes,0),(seg['b'],(1-position)*edge_minutes,1)):
                duration,path=_dijkstra_path(endpoint,target)
                if duration is not None:
                    candidates.append((minutes+duration,[{'a':seg['a'],'b':seg['b'],'minutes':minutes,'start_position':position,'end_position':end_position}]+[{'a':a,'b':b,'minutes':TRAVEL_GRAPH[a][b]} for a,b in zip(path,path[1:])]))
    else:
        duration,path=_dijkstra_path(origin,target)
        if duration is not None and all(a in TRAVEL_GRAPH and b in TRAVEL_GRAPH[a] for a,b in zip(path,path[1:])):
            candidates.append((duration,[{'a':a,'b':b,'minutes':TRAVEL_GRAPH[a][b]} for a,b in zip(path,path[1:])]))
    if not candidates:raise HTTPException(400,'مسیر معتبر بین مبدأ و مقصد وجود ندارد')
    return min(candidates,key=lambda x:x[0])

async def request(p,target,child_ids,request_id,forced=False,settle=True):
    if settle:await tick()
    s=await state(p)
    if s.get('captive'):raise HTTPException(403,'کاراکتر در اسارت است')
    if await commanding(key(p)):raise HTTPException(409,'تا وقتی فرماندهٔ یک لشکر هستی، سفر جداگانه ممکن نیست')
    if not s.get('place') and not s.get('trip'):raise HTTPException(400,'ابتدا ادمین محل حضور را تعیین کند')
    dest=await destination(target)
    if s.get('place')==target and not s.get('trip'):raise HTTPException(400,'هم‌اکنون در همین مکان هستی')
    if not s.get('trip') and await blocked(s['place']):raise HTTPException(403,'تا پایان درگیری خروج از این مکان ممکن نیست')
    selected=list(dict.fromkeys(child_ids))
    available={c['child_id']:c for c in await kids(p,s) if c['available']}
    if any(c not in available for c in selected):raise HTTPException(400,'فرزندان انتخاب‌شده باید زنده، آزاد و همراهت در همین مکان باشند')
    for child_id in selected:
        if await commanding('child:'+child_id):
            raise HTTPException(409,'یکی از فرزندان انتخاب‌شده فرماندهٔ یک لشکر است و نمی‌تواند جداگانه سفر کند')
    old=await trips.find_one({'_id':s['trip']}) if s.get('trip') else None
    if old and old['status']=='held':raise HTTPException(403,'سفر توسط ادمین متوقف شده است')
    if old and set(selected)!=set(old['children']):raise HTTPException(400,'در میانهٔ راه نمی‌توان اعضای گروه را جدا کرد')
    ident=key(p)+':'+request_id
    existing=await trips.find_one({'_id':ident})
    if existing:
        if existing['target']!=target or existing['children']!=selected:raise HTTPException(409,'شناسهٔ تکراری با اطلاعات متفاوت')
        return clean(existing)
    required=await gates(dest)
    row={'_id':ident,'character':key(p),'tg_id':p['tg_id'],'name':p['name'],'target':target,'origin':s.get('place') or old['origin'],
         'children':selected,'status':'pending','approvals':[p['tg_id']],'required':required,'created_at':now(),'forced':forced,'departure_trip':s.get('trip')}
    await trips.insert_one(row)
    if accepted(required,row['approvals']):await start(row)
    else:await notice('travel-request:'+ident,[u for group in required.values() for u in group],f"{p['name']} درخواست ورود به {dest['name']} داده است.")
    return clean(await trips.find_one({'_id':ident}))

async def start(row):
    p=await living(row['tg_id'])
    if key(p)!=row['character']:raise HTTPException(409,'کاراکتر تغییر کرده است')
    s=await state(p)
    if s.get('captive'):raise HTTPException(403,'کاراکتر اسیر است')
    dest=await destination(row['target'])
    required=await gates(dest)
    if not accepted(required,row['approvals']):raise HTTPException(409,'مالک یا اعضای میزبان تغییر کرده‌اند؛ پذیرش تازه لازم است')
    old=await trips.find_one({'_id':s['trip']}) if s.get('trip') else None
    if old and old['status']=='held':raise HTTPException(403,'سفر توسط ادمین متوقف شده است')
    if not old and s.get('place')!=row['origin']:
        previous=await trips.find_one({'_id':row.get('departure_trip'),'status':'arrived'}) if row.get('departure_trip') else None
        if not previous or previous['target']!=s.get('place'):raise HTTPException(409,'مبدأ مسافر تغییر کرده است')
    if not old and await blocked(s['place']):raise HTTPException(403,'خروج از مکان درگیر نبرد یا محاصره ممکن نیست')
    available={c['child_id'] for c in await kids(p,s) if c['available']}
    if not set(row['children']).issubset(available):raise HTTPException(409,'وضعیت فرزندان تغییر کرده است')
    if old and set(old['children'])!=set(row['children']):raise HTTPException(409,'گروه سفر تغییر کرده است')
    origin=await destination(s.get('place') or old['origin'])
    minutes,segments=route(origin['node'],dest['node'],old)
    cost=0 if not owned_castles(p) or row.get('forced') else 10*(1+len(row['children']))
    fields={'status':'travelling','started_at':now(),'arrival_at':now()+timedelta(minutes=minutes),'segments':segments,'cost':cost,'origin':s.get('place') or old['origin']}
    updates=[change('character_trips',{'_id':row['_id']},fields)]
    if old:updates.append(change('character_trips',{'_id':old['_id']},{'status':'redirected'}))
    for ident in [key(p)]+['child:'+cid for cid in row['children']]:
        updates.append(change('character_locations',{'_id':ident},{'trip':row['_id'],'place':None}))
    await commit({'_id':'travel-start:'+row['_id']+':'+str(uuid4()),'complete':False,'wallets':([{'member':member_for(p,0),'cost':{'wine':cost},'debit':True}] if cost else []),'changes':updates})
    await trips.update_many({'character':key(p),'status':'pending','_id':{'$ne':row['_id']}},{'$set':{'status':'superseded'}})

async def respond(uid,ident,allow):
    row=await trips.find_one({'_id':ident,'status':'pending'})
    if not row:raise HTTPException(409,'درخواست باز پیدا نشد')
    required=await gates(await destination(row['target']))
    if not any(uid in group for group in required.values()):raise HTTPException(403,'این درخواست مربوط به میزبان دیگری است')
    if not allow:
        await trips.update_one({'_id':ident},{'$set':{'status':'rejected'}})
        await notice('travel-reject:'+ident,[row['tg_id']],'درخواست ورود پذیرفته نشد؛ هزینه‌ای کم نشده است.')
        return {'ok':True}
    approvals=list(set(row['approvals']+[uid]))
    await trips.update_one({'_id':ident},{'$set':{'approvals':approvals,'required':required}})
    row.update(approvals=approvals,required=required)
    if accepted(required,approvals):await start(row)
    return {'ok':True}

async def tick():
    await recover()
    if game_clock.paused():return
    async for row in trips.find({'status':'travelling','arrival_at':{'$lte':now()}}):
        p=await players.find_one({'tg_id':row['tg_id']})
        if not p or key(p)!=row['character'] or p.get('is_dead') or p.get('registration_reset'):
            await trips.update_one({'_id':row['_id']},{'$set':{'status':'cancelled'}})
            continue
        changes=[change('character_trips',{'_id':row['_id']},{'status':'arrived'})]
        for ident in [row['character']]+['child:'+c for c in row['children']]:
            changes.append(change('character_locations',{'_id':ident,'trip':row['_id']},{'place':row['target'],'previous':row['origin'],'trip':None}))
        groups=await gates(await destination(row['target']))
        recipients={row['tg_id']}|{u for group in groups.values() for u in group}
        async for loc in locations.find({'place':row['target'],'tg_id':{'$exists':True}}):recipients.add(loc['tg_id'])
        await commit({'_id':'travel-arrive:'+row['_id'],'complete':False,'changes':changes,'notices':[{'event':'travel-arrive:'+row['_id'],'recipients':list(recipients),'text':f"{row['name']} به {row['target']} رسید."}]})
    async for s in locations.find({'expulsion.pending':True,'trip':None,'captive':None,'tg_id':{'$exists':True}}):
        if not s.get('previous'):continue
        try:
            await host(s['expulsion']['host_id'],s)
            if await blocked(s['place']) or await blocked(s['previous']):continue
            p=await living(s['tg_id'])
            if key(p)!=s['_id']:continue
            selected=[c['child_id'] for c in await kids(p,s) if c['available']]
            await request(p,s['previous'],selected,s['expulsion']['id'],forced=True,settle=False)
            await locations.update_one({'_id':s['_id']},{'$set':{'expulsion.pending':False}})
        except HTTPException:
            continue

async def host(uid,s):
    if not s.get('place') or s.get('trip'):raise HTTPException(400,'مهمان باید در مقصد حاضر باشد')
    required=await gates(await destination(s['place']))
    if not any(uid in group for group in required.values()):raise HTTPException(403,'اجازهٔ مدیریت مهمانان این مکان را نداری')
    if s.get('tg_id')==uid:raise HTTPException(400,'این عملیات برای خودت مجاز نیست')

async def capture_request(uid,subject,reason):
    s=await locations.find_one({'_id':subject})
    if not s:raise HTTPException(404,'مهمان پیدا نشد')
    await host(uid,s)
    if s.get('captive'):raise HTTPException(409,'این فرد قبلاً اسیر شده است')
    if await commanding(subject):raise HTTPException(409,'این مهمان همراه یک لشکر و در مأموریت فرماندهی است')
    existing=await captures.find_one({'subject':subject,'status':'pending'})
    if existing:return clean(existing)
    row={'_id':str(uuid4()),'subject':subject,'name':s['name'],'place':s['place'],'host_id':uid,'reason':reason,'status':'pending','at':now()}
    await captures.insert_one(row)
    return clean(row)

async def review_capture(ident,accept,actor):
    row=await captures.find_one({'_id':ident,'status':'pending'})
    if not row:raise HTTPException(409,'پروندهٔ باز پیدا نشد')
    if accept:
        s=await locations.find_one({'_id':row['subject']})
        if not s or s.get('place')!=row['place'] or s.get('captive'):raise HTTPException(409,'وضعیت مهمان تغییر کرده است')
        await host(row['host_id'],s)
    changes=[change('character_captures',{'_id':ident},{'status':'approved' if accept else 'rejected','reviewer':actor})]
    if accept:changes.append(change('character_locations',{'_id':row['subject']},{'captive':{'host_id':row['host_id'],'case_id':ident,'at':now()}}))
    await commit({'_id':'capture:'+ident,'complete':False,'changes':changes})
    return {'ok':True}

async def release(subject,uid,admin=False):
    s=await locations.find_one({'_id':subject})
    if not s or not s.get('captive'):raise HTTPException(409,'این فرد اسیر نیست')
    if not admin:
        await host(uid,s)
    await locations.update_one({'_id':subject},{'$set':{'captive':None}})
    return {'ok':True}

async def view(p):
    await tick()
    s=await state(p)
    children=await kids(p,s)
    dests=[{'id':n,'name':n,'node':n,'kind':'castle'} for n in sorted(TRAVEL_GRAPH)]
    dests += [clean(r) async for r in places.find({'enabled':True})]
    owned=set(owned_castles(p))
    memberships={i for i in INSTITUTIONS if p['tg_id'] in await member_ids(i)}
    hosted=[]
    for d in dests:
        if d['node'] in owned or d.get('institution') in memberships:hosted.append(d['id'])
    requests=[clean(t) async for t in trips.find({'$or':[{'character':key(p)},{'target':{'$in':hosted},'status':{'$in':['pending','travelling']}}]}).sort('created_at',-1).limit(100)]
    guests=[clean(g) async for g in locations.find({'place':{'$in':hosted},'_id':{'$ne':key(p)}})]
    return {'state':clean(s),'children':children,'destinations':dests,'requests':requests,'guests':guests,'hosted':hosted,'game_now':now(),'paused':game_clock.paused(),'free_travel':not bool(owned_castles(p))}

async def end_character(p):
    """Retire presence and cancel requests without touching unrelated characters."""
    s=await locations.find_one({'_id':key(p)})
    if s and s.get('trip'):
        trip=await trips.find_one({'_id':s['trip']})
        if trip:
            await locations.update_many({'_id':{'$in':['child:'+c for c in trip['children']]},'trip':trip['_id']},
                {'$set':{'trip':None,'place':trip['origin']}})
    await trips.update_many({'character':key(p),'status':{'$in':['pending','travelling','held']}},{'$set':{'status':'cancelled'}})
    await locations.update_one({'_id':key(p)},{'$set':{'place':None,'trip':None,'captive':None,'inactive':True}})
