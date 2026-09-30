"""Unanimous passage agreements for battles on road/sea edges."""
from datetime import timedelta
from hashlib import sha256
from bson import ObjectId
from fastapi import HTTPException
from db import db, campaigns, roleplays, players
from game import now
from encounter_geometry import legs, position, coordinates


def continuation(army, bid, at, graph):
    source=next((m for m in reversed(army.get('movement_history',[])) if m.get('reason')=='battle' and m.get('battle_id')==bid),None)
    if not source: raise ValueError('مسیر قبل از نبرد ثبت نشده است؛ ادمین باید وضعیت این لشکر را بررسی کند')
    contact=source.get('ended_at') or army.get('battle_started_at')
    if not contact: raise ValueError('زمان برخورد این لشکر ثبت نشده است')
    source={**source,'created_at':source.get('created_at') or army.get('created_at')}
    segments=[]
    for leg in legs(source,graph,source.get('arrival_at')):
        start=max(contact,leg[2]);end=leg[3]
        if end<=start:continue
        p0=position(leg,start);p1=coordinates(leg)[1]
        if abs(p1-p0)<1e-9:continue
        segments.append({'a':leg[0],'b':leg[1],'p0':p0,'p1':p1,'seconds':(end-start).total_seconds()})
    if not segments:
        if source.get('stationed_edge') or len(source.get('route_path') or [])<2:
            return None  # Already stationed on the edge; no old journey to resume.
        raise ValueError('باقی‌ماندهٔ مسیر این لشکر مشخص نیست')
    target=source.get('target_castle')
    path=[army.get('target_castle')]
    for seg in segments:
        endpoint=seg['a'] if seg['p1']==0 else seg['b'] if seg['p1']==1 else target
        if path[-1]!=endpoint:path.append(endpoint)
    seconds=sum(s['seconds'] for s in segments)
    return {'origin_castle':source.get('origin_castle'),'target_castle':target,
            'op_type':source.get('op_type') or army.get('op_type','garrison'),
            'route_path':path,'route_segments':segments,'route_edge_minutes':[],
            'travel_minutes':seconds/60,'moved_at':at,'arrival_at':at+timedelta(seconds=seconds),
            'arrival_notified':False,'encounters_checked_at':at}


async def context(army):
    from routers.admin import _battle_root, _battle_members_query
    bid=army.get('engagement_campaign_id')
    root=await _battle_root(bid) if bid else None
    if not root or not root.get('battle_open') or root.get('combat_resolved_at') or root.get('battle_cancelled_at'):
        return None
    if (root.get('battle_contact') or {}).get('kind')!='edge':return None
    rows=await campaigns.find(_battle_members_query(root,bid)).to_list(None)
    rows=[a for a in rows if a.get('active') and a.get('engagement_locked')]
    if not rows:return None
    from army_groups import group_for
    controllers={};bindings=[]
    for a in rows:
        group=await group_for(str(a['_id'])) if a.get('merge_group_id') else None
        uid=group['leader_tg_id'] if group else a['tg_id']
        controllers.setdefault(uid,[]).append(a)
        bindings.append(f"{a['_id']}:{uid}:{a.get('merge_group_id','')}")
    fingerprint=sha256('|'.join(sorted(bindings)).encode()).hexdigest()
    consent=root.get('passage_consent') or {}
    votes=set(consent.get('votes',[])) if consent.get('fingerprint')==fingerprint else set()
    return root,bid,rows,controllers,fingerprint,votes


async def status(army,uid):
    ctx=await context(army)
    if not ctx:return None
    root,bid,rows,controllers,fp,votes=ctx
    return {'battle_id':bid,'can_vote':uid in controllers,'agreed':uid in votes,
            'agreed_count':len(votes & controllers.keys()),'required_count':len(controllers)}


async def consent(campaign_id,agree,user):
    try:aid=ObjectId(campaign_id)
    except Exception:raise HTTPException(400,'شناسهٔ نامعتبر') from None
    army=await campaigns.find_one({'_id':aid,'active':True})
    ctx=await context(army or {})
    if not ctx:raise HTTPException(409,'این گزینه فقط برای نبرد باز در مسیر است')
    root,bid,rows,controllers,fp,votes=ctx
    if user['id'] not in controllers:raise HTTPException(403,'فقط صاحب لشکر یا فرماندهٔ ادغام می‌تواند موافقت کند')
    # Owning a different army in this battle does not grant control of this formation.
    from army_groups import group_for
    group=await group_for(str(aid)) if army.get('merge_group_id') else None
    if (group['leader_tg_id'] if group else army['tg_id'])!=user['id']:
        raise HTTPException(403,'برای این لشکر حق فرماندهی نداری')
    if agree:votes.add(user['id'])
    else:votes.discard(user['id'])
    if votes>=controllers.keys():
        from game_data import TRAVEL_GRAPH
        at=now();updates=[];released=[str(a['_id']) for a in rows]
        plans={}
        for a in rows:
            try:plan=continuation(a,bid,at,TRAVEL_GRAPH)
            except ValueError as e:raise HTTPException(409,str(e)) from None
            plans[str(a['_id'])]=plan
            state={'engagement_locked':False,'battle_open':False,'battle_cancelled_at':at,
                   'battle_close_reason':'unanimous_passage','released_with_army_ids':released,
                   'encounters_checked_at':at}
            unset={'engagement_campaign_id':'','battle_root_campaign_id':'','battle_is_root':'','opponent_campaign_id':'','opponent_tg_id':''}
            if plan:
                state.update(plan)
                # Departure grace is represented by released_with_army_ids + moved_at.
                unset.update({'stationed_edge':'','stationed_at':'','route_start_position':'','battle_contact':'','returning_from_battle':'','return_destination_edge':''})
                unset['battle_cancelled_at']=''
                state.pop('battle_cancelled_at')
            history={k:a.get(k) for k in ('origin_castle','target_castle','route_path','route_segments','route_edge_minutes','created_at','moved_at','arrival_at')}
            history.update(reason='passage_agreement',ended_at=at)
            state['movement_history']=[*a.get('movement_history',[]),history]
            updates.append({'id':a['_id'],'update':{'$set':state,'$unset':unset}})
        # Fleet capacity remains a property of the whole merged army.
        from game_data import NAVAL_TROOPS, is_sea_edge
        from routers.war import all_castle_terrain
        from army_groups import totals
        terrain=await all_castle_terrain()
        fleets={}
        for a in rows:fleets.setdefault(a.get('merge_group_id') or str(a['_id']),[]).append(a)
        for fleet in fleets.values():
            if not any(plan and any(is_sea_edge(s['a'],s['b'],terrain) for s in plan['route_segments']) for plan in [plans[str(a['_id'])] for a in fleet]):continue
            ts,_=totals(fleet)
            men=sum(n for k,n in ts.items() if k not in NAVAL_TROOPS)
            capacity=sum(NAVAL_TROOPS[k]['capacity']*n for k,n in ts.items() if k in NAVAL_TROOPS)
            if men>capacity:raise HTTPException(409,'ظرفیت کشتی‌های لشکر برای ادامهٔ مسیر دریایی کافی نیست')
        closure={'battle_open':False,'engagement_locked':False,'battle_close_reason':'unanimous_passage',
                 'passage_closed_at':at,'passage_consent':{'fingerprint':fp,'votes':sorted(votes)}}
        # The root is also an army: don't override its restored movement fields.
        for entry in updates:
            if entry['id']==root['_id']:entry['update']['$set'].update(closure)
        await db.battle_passage_commands.insert_one({'status':'prepared','battle_id':bid,'root_id':root['_id'],
            'updates':updates,'closure':closure,'battle_snapshot':root,'recipients':list({a['tg_id'] for a in rows}|set(controllers)),
            'location':root.get('battle_location'),'created_at':at})
        await recover()
        return {'ok':True,'closed':True}
    await campaigns.update_one({'_id':root['_id']},{'$set':{'passage_consent':{'fingerprint':fp,'votes':sorted(votes)}}})
    return {'ok':True,'closed':False,'agreed_count':len(votes),'required_count':len(controllers)}


async def recover():
    async for command in db.battle_passage_commands.find({'status':'prepared'}):
        for entry in command['updates']:await campaigns.update_one({'_id':entry['id']},entry['update'])
        if command['root_id'] not in {e['id'] for e in command['updates']}:
            await campaigns.update_one({'_id':command['root_id']},{'$set':command['closure']})
        await roleplays.update_many({'category':'war','campaign_id':command['battle_id'],'resolved':False},{'$set':{
            'resolved':True,'resolved_at':command['created_at'],'result':'نبرد با موافقت تمام طرف‌ها برای ادامهٔ مسیر، بدون نتیجه بسته شد.'}})
        from battle_notices import enqueue
        recipients=await players.find({'tg_id':{'$in':command['recipients']}}).to_list(None)
        await enqueue(f"battle-passage:{command['battle_id']}",recipients,
            f"🤝 نبرد {command.get('location','')} با موافقت همهٔ طرف‌ها بدون نتیجه بسته شد. لشکرهای در حال سفر، باقی‌ماندهٔ مسیر قبلی را از محل برخورد ادامه می‌دهند.")
        await db.battle_passage_commands.update_one({'_id':command['_id']},{'$set':{'status':'done'}})
