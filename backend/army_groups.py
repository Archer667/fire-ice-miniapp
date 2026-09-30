"""Shared army formations preserve each constituent's ownership and upkeep."""
from datetime import timedelta
from bson import ObjectId
from fastapi import APIRouter, Depends, HTTPException, Request
from pydantic import BaseModel
from auth import get_user
from db import db, campaigns, players
from game import now
from army_upkeep import food_rate
from game_data import NAVAL_TROOPS
from player_labels import titled_name

async def require_war(request: Request):
    from control_settings import feature_enabled
    if request.method == 'POST' and not feature_enabled('war'):
        raise HTTPException(503, 'جنگ فعلاً غیرفعال است')


router = APIRouter(prefix='/api/army-groups', tags=['army-groups'], dependencies=[Depends(require_war)])
groups = db.army_groups
requests = db.army_merge_requests


def oid(value):
    try: return ObjectId(value)
    except Exception: raise HTTPException(400, 'شناسهٔ نامعتبر') from None


def location(army):
    edge = army.get('stationed_edge')
    return ('edge', edge['a'], edge['b'], round(edge['position'], 7)) if edge else ('castle', army.get('target_castle'))


async def ready(army):
    from routers.war import campaign_waiting_for_result, repair_stale_engagement_lock
    if not army or not army.get('active'):
        raise HTTPException(409, 'لشکر دیگر فعال نیست')
    army = await repair_stale_engagement_lock(army)
    if army.get('engagement_locked') or campaign_waiting_for_result(army):
        raise HTTPException(409, 'لشکر درگیر نبرد است')
    if army.get('arrival_at') and army['arrival_at'] > now():
        raise HTTPException(409, 'لشکر هنوز در حال حرکت است')
    return army


async def members(group):
    return await campaigns.find({'_id': {'$in': group['army_ids']}, 'active': True}).to_list(None)


async def group_for(army_id):
    return await groups.find_one({'army_ids': oid(army_id), 'active': True})


async def available_group(group):
    rows = await members(group)
    if not rows: raise HTTPException(409, 'لشکر مشترک دیگر نیروی فعالی ندارد')
    for row in rows: await ready(row)
    if len({location(row) for row in rows}) != 1:
        raise HTTPException(409, 'اجزای لشکر در یک محل نیستند؛ ابتدا وضعیت حرکت یا نبرد را بررسی کن')
    return rows


def totals(rows):
    troops, equipment = {}, {}
    for row in rows:
        for target, key in ((troops, 'troops'), (equipment, 'equipment')):
            for item, value in (row.get(key) or {}).items(): target[item] = target.get(item, 0) + max(0, int(value or 0))
    return troops, equipment


def roster(rows):
    owners = {}
    for row in rows:
        owners.setdefault(row['tg_id'], []).append(row)
    troops, equipment = totals(rows)
    def line(ts, eq):
        return f"{sum(v for k,v in ts.items() if k not in NAVAL_TROOPS):,} سرباز · {sum(v for k,v in ts.items() if k in NAVAL_TROOPS):,} کشتی · {sum(eq.values()):,} ادوات"
    text = 'جمع کل: ' + line(troops, equipment)
    for uid, units in owners.items():
        ts, eq = totals(units)
        text += f"\n{titled_name(name=units[0].get('player_name'), gender=units[0].get('player_gender'))}: {line(ts,eq)} · غلات روزانه {food_rate(ts):g}"
        if any(u.get('commander_present') for u in units): text += ' · کاراکتر همراه است'
    return text


def composition(rows):
    from routers.war import troop_name
    from game_data import SIEGE_EQUIPMENT
    ts,eq=totals(rows)
    return {'forces':[{'id':k,'name':troop_name(k),'count':v} for k,v in ts.items() if v and k not in NAVAL_TROOPS],
            'ships':[{'id':k,'name':troop_name(k),'count':v} for k,v in ts.items() if v and k in NAVAL_TROOPS],
            'devices':[{'id':k,'name':SIEGE_EQUIPMENT.get(k,{}).get('name',k),'count':v} for k,v in eq.items() if v]}


async def notice(rows, event, intro):
    from battle_notices import enqueue
    recipients = await players.find({'tg_id': {'$in': list({a['tg_id'] for a in rows})}}).to_list(None)
    await enqueue(event, recipients, intro + '\n\n' + roster(rows))


async def set_members(group, ids):
    # Group document is authoritative. Derived campaign tags are repaired before ticks/requests.
    await groups.update_one({'_id': group['_id']}, {'$set': {'army_ids': ids, 'active': len(ids) > 1, 'updated_at': now()}})
    await repair_tags()


async def repair_tags():
    active = await groups.find({'active': True}).to_list(None)
    for group in active:
        live = await members(group)
        leader = await players.find_one({'tg_id':group['leader_tg_id'],'is_dead':{'$ne':True}})
        if len(live) < 2 or not leader:
            await groups.update_one({'_id':group['_id']},{'$set':{'active':False}})
            group['army_ids'] = []

    expected = {}
    for group in active:
        for aid in group['army_ids']: expected[aid] = str(group['_id'])
    async for army in campaigns.find({'$or': [{'merge_group_id': {'$exists': True}}, {'_id': {'$in': list(expected)}}]}, {'merge_group_id': 1}):
        gid = expected.get(army['_id'])
        if gid != army.get('merge_group_id'):
            await campaigns.update_one({'_id': army['_id']}, {'$set': {'merge_group_id': gid}} if gid else {'$unset': {'merge_group_id': ''}})


class Invite(BaseModel):
    base_id: str
    target_id: str


async def validate_pair(base_id, target_id, leader):
    from routers.war import detect_route_encounters
    await detect_route_encounters()
    base = await ready(await campaigns.find_one({'_id': oid(base_id)}))
    target = await ready(await campaigns.find_one({'_id': oid(target_id)}))
    group = await group_for(base_id)
    if (group and group['leader_tg_id'] != leader) or (not group and base['tg_id'] != leader):
        raise HTTPException(403, 'فقط فرمانده می‌تواند برای این لشکر درخواست ادغام بدهد')
    rows = await available_group(group) if group else [base]
    if base['_id'] == target['_id'] or await group_for(target_id):
        raise HTTPException(409, 'لشکر انتخاب‌شده قبلاً عضو ادغام است')
    if location(base) != location(target):
        raise HTTPException(409, 'لشکرها باید دقیقاً در یک محل مستقر باشند')
    return base, target, group, rows


async def merge(base, target, group, rows, leader):
    gid = group['_id'] if group else ObjectId()
    doc = {**(group or {}), 'leader_tg_id': leader,
           'root_id': (group or {}).get('root_id', base['_id']),
           'name': (group or {}).get('name', base.get('name', 'لشکر مشترک')),
           'army_ids': [a['_id'] for a in [*rows, target]], 'active': True,
           'created_at': (group or {}).get('created_at', now())}
    doc.pop('_id', None)
    at=now()
    updates=[]
    for army in [*rows,target]:
        history={**{k:army.get(k) for k in ('origin_castle','target_castle','route_path','route_edge_minutes','route_start_position','created_at','moved_at','arrival_at')},'ended_at':at,'reason':'merge'}
        updates.append({'id':army['_id'],'update':{'$set':{
            'origin_castle':army['target_castle'],'route_path':[army['target_castle']],
            'route_segments':[],'route_edge_minutes':[],'travel_minutes':0,
            'moved_at':at,'arrival_at':at,'arrival_notified':True,
            'movement_history':[*army.get('movement_history',[]),history]}}})
    await db.army_group_moves.insert_one({'status':'prepared','group_id':gid,'group_doc':doc,'updates':updates,'created_at':at})
    await recover_moves()
    await notice([*rows,target], f'merge:{gid}:{target["_id"]}', '🤝 لشکرها ادغام شدند؛ مالکیت و هزینهٔ غلات هر عضو جدا حفظ می‌شود.')
    return {'ok': True, 'group_id': str(gid)}


@router.get('/candidates/{base_id}')
async def candidates(base_id: str, user=Depends(get_user)):
    base = await ready(await campaigns.find_one({'_id': oid(base_id)}))
    group = await group_for(base_id)
    if (group['leader_tg_id'] if group else base['tg_id']) != user['id']: raise HTTPException(403, 'دسترسی نداری')
    out = []
    async for row in campaigns.find({'active': True, '_id': {'$ne': base['_id']}, 'target_castle': base['target_castle']}):
        if location(row) != location(base) or await group_for(str(row['_id'])): continue
        try: await ready(row)
        except HTTPException: continue
        out.append({'id': str(row['_id']), 'name': row.get('name'), 'player_name': row.get('player_name'), 'tg_id': row['tg_id'], 'is_mine':row['tg_id']==user['id'], 'summary': roster([row])})
    return out


@router.post('/invite')
async def invite(body: Invite, user=Depends(get_user)):
    base,target,group,rows = await validate_pair(body.base_id,body.target_id,user['id'])
    if target['tg_id'] == user['id']: return await merge(base,target,group,rows,user['id'])
    old = await requests.find_one({'base_id':body.base_id,'target_id':body.target_id,'status':'pending','expires_at':{'$gt':now()}})
    if old: raise HTTPException(409, 'برای این لشکر درخواست در انتظار پاسخ وجود دارد')
    doc={'base_id':body.base_id,'target_id':body.target_id,'from_id':user['id'],'to_id':target['tg_id'],
         'from_name':base.get('player_name'),'target_name':target.get('name'),'status':'pending','created_at':now(),'expires_at':now()+timedelta(hours=24)}
    rid=(await requests.insert_one(doc)).inserted_id
    from routers.ravens import send_system_message
    await send_system_message(target['tg_id'],target.get('player_name',''),f"🤝 درخواست ادغام از {base.get('player_name')} برای لشکر «{target.get('name')}»\nفرماندهی با درخواست‌دهنده است؛ سهم نیروها و غلاتت متعلق به خودت می‌ماند. برای پذیرش یا رد به نیرو ← لشکرها برو.\n\n"+roster([*rows,target]))
    return {'ok':True,'request_id':str(rid)}


@router.get('/requests')
async def pending(user=Depends(get_user)):
    return [{**{k:v for k,v in r.items() if k not in ('_id','created_at','expires_at')},'id':str(r['_id'])} async for r in requests.find({'to_id':user['id'],'status':'pending','expires_at':{'$gt':now()}})]


class Reply(BaseModel):
    accept: bool


@router.post('/requests/{request_id}/reply')
async def reply(request_id: str, body: Reply, user=Depends(get_user)):
    r=await requests.find_one({'_id':oid(request_id),'to_id':user['id'],'status':'pending','expires_at':{'$gt':now()}})
    if not r: raise HTTPException(409,'درخواست دیگر معتبر نیست')
    if body.accept:
        existing=await group_for(r['base_id'])
        if existing and existing['leader_tg_id']==r['from_id'] and oid(r['target_id']) in existing['army_ids']:
            await requests.update_one({'_id':r['_id']},{'$set':{'status':'accepted','answered_at':now()}})
            return {'ok':True,'group_id':str(existing['_id'])}
        base,target,group,rows=await validate_pair(r['base_id'],r['target_id'],r['from_id'])
        if target['tg_id']!=user['id']: raise HTTPException(403,'مالکیت لشکر تغییر کرده است')
        result=await merge(base,target,group,rows,r['from_id'])
    else: result={'ok':True}
    await requests.update_one({'_id':r['_id']},{'$set':{'status':'accepted' if body.accept else 'rejected','answered_at':now()}})
    return result


@router.post('/{group_id}/leave')
async def leave(group_id: str, user=Depends(get_user)):
    group=await groups.find_one({'_id':oid(group_id),'active':True})
    if not group: raise HTTPException(404,'ادغام پیدا نشد')
    rows=await available_group(group)
    if user['id'] != group['leader_tg_id'] and user['id'] not in {a['tg_id'] for a in rows}: raise HTTPException(403,'عضو این لشکر نیستی')
    ids=[] if user['id']==group['leader_tg_id'] else [a['_id'] for a in rows if a['tg_id']!=user['id']]
    await set_members(group,ids)
    await notice(rows,f'split:{group_id}:{now().isoformat()}','لشکر مشترک تفکیک شد؛ نیروها و ادوات باقی‌مانده در همان محل هستند.')
    return {'ok':True}

async def recover_moves():
    async for command in db.army_group_moves.find({'status':'prepared'}):
        for entry in command['updates']:
            await campaigns.update_one({'_id':entry['id']},entry['update'])
        if command.get('group_doc'):
            await groups.update_one({'_id':command['group_id']},{'$set':command['group_doc']},upsert=True)
        await db.army_group_moves.update_one({'_id':command['_id']},{'$set':{'status':'done'}})
    await repair_tags()


async def move_group(group, body, user):
    from routers import war
    if group['leader_tg_id']!=user['id']: raise HTTPException(403,'فقط فرماندهٔ لشکر مشترک می‌تواند فرمان حرکت بدهد')
    rows=await available_group(group)
    updates=[]
    ts,eq=totals(rows)
    formation={'troops':ts,'equipment':eq,'commander_present':any(a.get('commander_present') for a in rows)}
    # Validate every participant before writing any movement.
    for army in rows:
        update=await war._move_campaign(str(army['_id']),body,{'id':army['tg_id']},preview=True,formation=formation)
        updates.append((army,update))
    if len({tuple(u['$set']['route_path']) for _,u in updates})!=1:
        raise HTTPException(409,'برای همهٔ اعضا یک مسیر مشترک قابل پیمایش انتخاب کن')
    duration=max(u['$set']['travel_minutes'] for _,u in updates)
    at=now();arrival=at+timedelta(minutes=duration)
    writes=[]
    for army,update in updates:
        update['$set'].update(moved_at=at,arrival_at=arrival,travel_minutes=duration)
        history={**update.pop('$push')['movement_history'],'ended_at':at}
        update['$set']['movement_history']=[*army.get('movement_history',[]),history]
        writes.append({'id':army['_id'],'update':update})
    await db.army_group_moves.insert_one({'status':'prepared','group_id':group['_id'],'updates':writes,'created_at':at})
    await recover_moves()
    moved=[{**a,**u['$set']} for a,u in updates]
    leader=next((a for a in moved if a['tg_id']==group['leader_tg_id']),moved[0])
    await war.notify_campaign_departure(leader)
    await notice(moved,f'group-move:{group["_id"]}:{at.isoformat()}',f"⚔️ لشکر مشترک به فرماندهی {leader.get('player_name')} به سمت {body.target_castle} حرکت کرد.")
    return {'ok':True,'arrival_at':arrival.isoformat(),'travel_minutes':duration,'route_path':updates[0][1]['$set']['route_path']}


def proportional_losses(rows, field, losses):
    """Largest remainder allocation by each unit type; integer sums stay exact."""
    result={str(a['_id']):{} for a in rows}
    for key,raw in losses.items():
        loss=int(raw or 0);counts=[max(0,int(a.get(field,{}).get(key,0))) for a in rows];total=sum(counts)
        if loss<0 or loss>total: raise HTTPException(400,'تلفات از تعداد حاضر بیشتر است')
        if not loss: continue
        shares=[loss*n//total for n in counts]
        order=sorted(range(len(rows)),key=lambda i:(-(loss*counts[i]%total),str(rows[i]['_id'])))
        for i in order[:loss-sum(shares)]:shares[i]+=1
        for a,n in zip(rows,shares):result[str(a['_id'])][key]=n
    return result


async def distribute_battle_losses(armies, troop_losses, equipment_losses):
    """Admin can enter a formation's losses across cards; distribute total fairly."""
    for gid in {a.get('merge_group_id') for a in armies if a.get('merge_group_id')}:
        rows=[a for a in armies if a.get('merge_group_id')==gid]
        for field,loss_map in (('troops',troop_losses),('equipment',equipment_losses)):
            combined={}
            for army in rows:
                for key,n in loss_map.get(str(army['_id']),{}).items():combined[key]=combined.get(key,0)+int(n or 0)
            allocated=proportional_losses(rows,field,combined)
            loss_map.update(allocated)


@router.get('/mine')
async def mine(user=Depends(get_user)):
    from battle_passage import status as passage_status
    owned=[a['_id'] async for a in campaigns.find({'tg_id':user['id'],'active':True},{'_id':1})]
    out=[]
    async for group in groups.find({'active':True,'$or':[{'army_ids':{'$in':owned}},{'leader_tg_id':user['id']}]}):
        rows=await members(group)
        troops,equipment=totals(rows)
        command_army=next((a for a in rows if a['tg_id']==group['leader_tg_id']),rows[0])
        free=True
        try:await available_group(group)
        except HTTPException:free=False
        out.append({'id':str(group['_id']),'root_id':str(command_army['_id']),'name':group['name'],'leader_tg_id':group['leader_tg_id'],
                    'army_ids':[str(a['_id']) for a in rows],'troops':troops,'equipment':equipment,'summary':roster(rows),
                    'composition':composition(rows),'passage':await passage_status(command_army,user['id']),
                    'member_compositions':[{'tg_id':uid,'name':titled_name(name=next(a for a in rows if a['tg_id']==uid).get('player_name'),gender=next(a for a in rows if a['tg_id']==uid).get('player_gender')),**composition([a for a in rows if a['tg_id']==uid])} for uid in sorted({a['tg_id'] for a in rows})],
                    'state':('مستقر' if free else 'در حال حرکت' if any(a.get('arrival_at') and a['arrival_at']>now() for a in rows) else 'درگیر نبرد'),'can_split':free,'can_attack':free and all(a.get('op_type')=='siege' for a in rows) and group['leader_tg_id']==user['id'],'location':rows[0].get('target_castle') if rows else '',
                    'arrival_at':rows[0].get('arrival_at').isoformat() if rows and rows[0].get('arrival_at') else None,
                    'stationed_edge':rows[0].get('stationed_edge') if rows else None, 'is_leader':group['leader_tg_id']==user['id'], 'can_move':free and group['leader_tg_id']==user['id']})
    return out

async def attach_battle_group(root):
    from routers import war
    from encounter_runtime import halt
    bid=root.get('engagement_campaign_id')
    if not bid:return root
    ids=[*(root.get('battle_attacker_army_ids') or []),*(root.get('battle_defender_army_ids') or [])]
    present=await campaigns.find({'_id':{'$in':[oid(i) for i in ids]},'active':True}).to_list(None)
    for first in present:
        if not first.get('merge_group_id'):continue
        group=await group_for(str(first['_id']))
        if not group:continue
        side='defender' if str(first['_id']) in (root.get('battle_defender_army_ids') or []) else 'attacker'
        point=first.get('battle_contact') or ({'kind':'edge',**first['stationed_edge']} if first.get('stationed_edge') else {'kind':'castle','castle':root.get('battle_location') or first['target_castle']})
        at=first.get('battle_started_at') or now()
        for army in await members(group):
            aid=str(army['_id'])
            if aid in ids:continue
            if army.get('engagement_locked'):
                if army.get('engagement_campaign_id')!=bid:continue
            await halt(war,army,point,at,bid,str(root['_id']))
            entry={'campaign_id':aid,'tg_id':army['tg_id'],'player_name':army.get('player_name'),'side':side,'joined_at':at}
            key='battle_defender_snapshot' if side=='defender' else 'battle_attacker_snapshots'
            await campaigns.update_one({'_id':root['_id']},{'$push':{f'battle_{side}_army_ids':aid,key:war.battle_army_snapshot(army),'battle_joins':entry,f'battle_{side}_joins':entry},'$addToSet':{'battle_participant_tg_ids':army['tg_id']}})
            ids.append(aid)
    return await campaigns.find_one({'_id':root['_id']}) or root


async def attack_group(group, user):
    from routers.war import reject_hostile_order_during_pact
    from control_settings import feature_enabled
    if not feature_enabled('war'): raise HTTPException(503, 'جنگ فعلاً غیرفعال است')
    if group['leader_tg_id'] != user['id']: raise HTTPException(403, 'فقط فرمانده می‌تواند فرمان بدهد')
    rows = await available_group(group)
    for army in rows:
        if army.get('op_type') != 'siege': raise HTTPException(400, 'لشکر باید در حالت محاصره باشد')
        await reject_hostile_order_during_pact(army['tg_id'], army['target_castle'], 'attack')
    at=now()
    updates=[{'id':a['_id'],'update':{'$set':{'op_type':'attack','arrival_at':at,'arrival_notified':False,'attack_ordered_at':at}}} for a in rows]
    await db.army_group_moves.insert_one({'status':'prepared','group_id':group['_id'],'updates':updates,'created_at':at})
    await recover_moves()
    await notice(rows,f'group-attack:{group["_id"]}:{at.isoformat()}','⚔️ فرمان حملهٔ لشکر مشترک صادر شد.')
    return {'ok':True}
