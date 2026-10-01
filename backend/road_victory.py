"""Journaled, exact-once automatic victories at new two-formation road contacts."""
import math
from copy import deepcopy
from hashlib import sha256
from types import SimpleNamespace
from db import db, players, campaigns
from game import now
from control_settings import get as rule
from medals import normalize_stats, sync_medals
from player_labels import titled_name

results = db.road_auto_results


def decision(first, second, ratio):
    if not all(math.isfinite(x) for x in (first,second,ratio)) or ratio <= 1 or first < 0 or second < 0 or first == second:
        return None
    high, low = max(first, second), min(first, second)
    return (0 if first > second else 1) if high > 0 and high >= low * ratio else None


async def formation(army):
    from army_groups import group_for, members
    group = await group_for(str(army['_id']))
    return await members(group) if group else [army]


def on_edge(army, point, at, graph):
    from encounter_runtime import point_at
    from encounter_geometry import legs
    if army.get('stationed_edge'):
        current = army['stationed_edge']
    else:
        current = None
        for leg in legs(army, graph, at):
            if leg[2] <= at <= leg[3] and set(leg[:2]) == {point['a'], point['b']}:
                current = point_at(army, at, 'edge', leg[:2], graph, at)
                break
    return bool(current and current.get('a') == point['a'] and current.get('b') == point['b']
                and abs(current['position'] - point['position']) < 1e-7)


async def try_resolve(w, a, b, point, at, all_armies, partners):
    if point['kind'] != 'edge': return False
    await db.game_settings.update_one({'_id':'road_victory_v1'},{'$setOnInsert':{'started_at':now()}},upsert=True)
    epoch = await db.game_settings.find_one({'_id':'road_victory_v1'})
    if at < epoch['started_at']:return False
    first, second = await formation(a), await formation(b)
    rows = first + second
    ids = {r['_id'] for r in rows}
    if len(ids) != len(rows) or any(r.get('engagement_locked') or not on_edge(r,point,at,w.TRAVEL_GRAPH) for r in rows):
        return False
    # A formation must not destroy a member protected by a peace treaty.
    if any(x['tg_id'] == y['tg_id'] or y['tg_id'] in partners.get(x['tg_id'], set()) for x in first for y in second):
        return False
    # Do not resolve a pair in isolation when another formation is at this contact.
    if any(r['_id'] not in ids and on_edge(r,point,at,w.TRAVEL_GRAPH) for r in all_armies):
        return False
    if any(not sum(int(n or 0) for n in r.get('troops',{}).values()) and not any(r.get('equipment',{}).values()) for r in rows):
        return False
    from routers.admin import _admin_army_metrics
    powers = []
    for team in (first,second):
        total = 0
        for row in team:
            metric = await _admin_army_metrics(row)
            total += max(0,float(metric['power'])) + max(0,float(metric['equipment_power']))
        powers.append(total)
    ratio = float(rule('war.road_victory_ratio',7))
    side = decision(*powers,ratio)
    if side is None:return False
    winners,losers = (first,second) if side == 0 else (second,first)
    owners = sorted({r['tg_id'] for r in winners})
    winner_updates = []
    for uid in owners:
        p = await players.find_one({'tg_id':uid})
        if not p or p.get('is_dead') or p.get('registration_reset'):return False
        stats = normalize_stats(deepcopy(p));stats['attack_wins'] += 1
        fields = {'stats':stats,'points':int(p.get('points',0))+int(rule('scoring.victory',10)),
                  'medals':sync_medals({**p,'stats':stats})}
        winner_updates.append({'tg_id':uid,'created_at':p['created_at'],'fields':fields})
    deaths = []
    for uid in sorted({r['tg_id'] for r in losers if r.get('commander_present')}):
        p = await players.find_one({'tg_id':uid})
        if p and not p.get('is_dead') and not p.get('registration_reset'):deaths.append(p)
    token = sha256(repr((sorted(str(i) for i in ids),point,at)).encode()).hexdigest()
    from encounter_runtime import label
    from army_groups import roster
    winner_names = '، '.join(dict.fromkeys(titled_name(name=r.get('player_name'),gender=r.get('player_gender')) for r in winners))
    loser_names = '، '.join(dict.fromkeys(titled_name(name=r.get('player_name'),gender=r.get('player_gender')) for r in losers))
    text = (f'⚔️ پیروزی خودکار در مسیر\n📍 {label(point)}\n\n🏆 برنده‌ها: {winner_names}\n'
            f'💥 لشکرهای نابودشده: {loser_names}\n\nتوان برنده: {powers[side]:g} · توان بازنده: {powers[1-side]:g}\n'
            f'ضریب لازم: {ratio:g} برابر\n\n{roster(winners)}\n\nلشکر برنده بدون تلفات مسیرش را ادامه می‌دهد.')
    if deaths:text += '\nکاراکترهای همراه لشکر بازنده کشته می‌شوند؛ وارث بالغ طبق قانون جانشین می‌شود.'
    await results.update_one({'_id':token},{'$setOnInsert':{'status':'prepared','at':at,'point':point,'ratio':ratio,
        'powers':powers,'winners':winners,'losers':losers,'winner_updates':winner_updates,'deaths':deaths,'deaths_done':[],
        'winner_tg_ids':owners,'loser_tg_ids':sorted({r['tg_id'] for r in losers}),'text':text}},upsert=True)
    await recover()
    return True


async def kill_character(snapshot, op):
    from character_records import retire, save_castles, archives
    from family import preview, recover as recover_family
    from routers.admin import _mark_player_dead
    await recover_family()
    p = await players.find_one({'tg_id':snapshot['tg_id']})
    if not p or p.get('created_at') != snapshot['created_at'] or p.get('registration_reset'):
        return
    reason = f"کشته‌شدن در نابودی خودکار لشکر در مسیر {op['point']['a']} — {op['point']['b']}"
    body = SimpleNamespace(action='death',character_key=f"{p['tg_id']}:{p.get('created_at')}",
        kill_heirs=False,blacklisted=False,reason=reason,narrative=p.get('backstory') or '')
    state = await preview(p)
    if not state['heir'] or p.get('is_dead'):
        # Resume the existing idempotent cleanup after a crash following the death flag.
        await save_castles(snapshot)
        await _mark_player_dead(snapshot,reason,notify=False,resume=True)
    await retire(p['tg_id'],body,0,system_death=True)


async def recover():
    async for op in results.find({'status':'prepared'}):
        # Absolute writes under game_state_lock make replays exact-once.
        for row in op['losers']:
            await campaigns.update_one({'_id':row['_id']},{'$set':{'active':False,'status':'destroyed',
                'troops':{},'equipment':{},'power':0,'equipment_power':0,'men_committed':0,
                'soldiers_committed':0,'food_per_day':0,'arrival_notified':True,'engagement_locked':False,
                'destroyed_at':op['at'],'road_auto_result_id':op['_id']}})
        for change in op['winner_updates']:
            await players.update_one({'tg_id':change['tg_id'],'created_at':change['created_at']},{'$set':change['fields']})
        for row in op['winners']:
            await campaigns.update_one({'_id':row['_id']},{'$set':{'road_auto_result_id':op['_id']}})
        for p in op['deaths']:
            if p['tg_id'] in op.get('deaths_done',[]):continue
            await kill_character(p,op)
            await results.update_one({'_id':op['_id']},{'$addToSet':{'deaths_done':p['tg_id']}})
        from admin_notifications import _admin_ids
        from battle_notices import enqueue
        ids=set(op['winner_tg_ids']+op['loser_tg_ids']) | set(await _admin_ids())
        recipients={p['tg_id']:p async for p in players.find({'tg_id':{'$in':list(ids)}},{'tg_id':1,'name':1})}
        for uid in ids:recipients.setdefault(uid,{'tg_id':uid,'name':'ادمین'})
        await enqueue('road-auto:'+op['_id'],list(recipients.values()),op['text'])
        await db.admin_activity.update_one({'_id':'road-auto:'+op['_id']},{'$setOnInsert':{
            'at':op['at'],'game_at':op['at'],'actor_id':0,'actor_name':'سامانه','role':'system',
            'method':'AUTO','path':'/system/road-victory','request':{'ratio':op['ratio'],'winner_tg_ids':op['winner_tg_ids'],
            'loser_tg_ids':op['loser_tg_ids']},'status':200,'changes':[],'result':op['text']}},upsert=True)
        await results.update_one({'_id':op['_id']},{'$set':{'status':'done','finished_at':now()}})
