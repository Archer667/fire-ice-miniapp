"""Chronological encounters. Called under the game's existing state lock.

An activation epoch prevents replaying unverified historical movements on deploy.
New movements and all subsequent contacts use physical positions and an explicit
stationary state; closing a case never transports an army to its old destination.
"""
from itertools import combinations
from bson import ObjectId
from encounter_geometry import encounters, legs, position


def point_at(army, at, kind, place, graph, horizon):
    if kind == 'castle':
        return {'kind': 'castle', 'castle': place[0]}
    for leg in legs(army, graph, horizon):
        if set(leg[:2]) == set(place) and leg[2] <= at <= leg[3]:
            fraction = position(leg, at)
            first, second = leg[0], leg[1]
            if first > second:
                first, second, fraction = second, first, 1 - fraction
            weight = graph.get(leg[0], {}).get(leg[1])
            old = army.get('stationed_edge') or army.get('route_start_position') or {}
            return {'kind': 'edge', 'a': first, 'b': second,
                    'position': round(max(0, min(1, fraction)), 8),
                    'base_minutes': old.get('base_minutes') or weight}
    return None


def label(point):
    return point['castle'] if point['kind'] == 'castle' else f"مسیر {point['a']} — {point['b']}"


async def halt(w, army, point, at, battle_id, root_id, is_root=False):
    location = label(point)
    state = {'engagement_locked': True, 'engagement_campaign_id': battle_id,
             'battle_root_campaign_id': root_id, 'battle_is_root': is_root,
             'battle_location': location, 'battle_started_at': at,
             'battle_contact': point, 'stationed_at': at,
             'target_castle': location, 'arrival_at': at,
             'route_path': [location], 'travel_minutes': 0, 'arrival_notified': True}
    unset = {'combat_resolved_at': '', 'battle_cancelled_at': '', 'battle_left_at': '',
             'battle_left_reason': '', 'route_start_position': ''}
    if point['kind'] == 'edge':
        state['stationed_edge'] = {k: v for k, v in point.items() if k != 'kind'}
    else:
        unset['stationed_edge'] = ''
    movement = {k: army.get(k) for k in ('origin_castle', 'target_castle', 'route_path',
                 'route_edge_minutes', 'route_start_position', 'created_at', 'moved_at', 'arrival_at')}
    movement.update({'ended_at': at, 'reason': 'battle', 'battle_id': battle_id})
    await w.campaigns.update_one({'_id': army['_id'], 'engagement_locked': {'$ne': True}},
        {'$set': state, '$unset': unset, '$push': {'movement_history': movement}})


async def announce(w, root, event, intro):
    await w.queue_battle_roster(root, event, intro)
    text = await w.battle_admin_roster_text(root, root['engagement_campaign_id'], intro)
    await w.notify_admins('battle_started', '⚔️ پروندهٔ نبرد', text,
        dedupe_key=event, priority='urgent', source_id=root['engagement_campaign_id'])


async def start(w, first, second, point, at):
    battle_id = str(ObjectId())
    location = label(point)
    defender = await w.owner_of_castle(location) if point['kind'] == 'castle' else None
    if defender and defender['tg_id'] == first['tg_id']:
        first, second = second, first
    if defender and await w.players_are_friendly(first['tg_id'], defender['tg_id']) and await w.players_are_friendly(second['tg_id'], defender['tg_id']):
        defender = None
    root_id = str(first['_id'])
    snapshots = [w.battle_army_snapshot(a) for a in (first, second)]
    joins = [{'campaign_id': str(a['_id']), 'tg_id': a['tg_id'],
              'player_name': a['player_name'], 'side': side, 'joined_at': at}
             for a, side in ((first, 'attacker'), (second, 'defender'))]
    for army in (first, second):
        await halt(w, army, point, at, battle_id, root_id, army['_id'] == first['_id'])
    state = {
        'battle_open': True, 'battle_engine_version': 2,
        'opponent_campaign_id': str(second['_id']), 'opponent_tg_id': second['tg_id'],
        'battle_attacker_snapshot': snapshots[0], 'battle_attacker_snapshots': [snapshots[0]],
        'battle_attacker_army_ids': [root_id], 'battle_attacker_joins': [joins[0]],
        'battle_defender_snapshot': [snapshots[1]],
        'battle_defender_army_ids': [str(second['_id'])], 'battle_defender_joins': [joins[1]],
        'battle_joins': joins, 'battle_participant_tg_ids': sorted({first['tg_id'], second['tg_id']} | ({defender['tg_id']} if defender else set())),
        'battle_defender_tg_id': defender['tg_id'] if defender else second['tg_id'],
        'battle_defender_name': defender.get('name', second['player_name']) if defender else second['player_name'],
        'battle_defense_infrastructure': w.defensive_infrastructure(defender, location) if defender else [],
    }
    await w.campaigns.update_one({'_id': first['_id']}, {'$set': state})
    root = await w.campaigns.find_one({'_id': first['_id']})
    await announce(w, root, f'battle-started:{battle_id}', f'⚔️ نبرد در {location} آغاز شد.')


async def join(w, root, army, point, at):
    side = await w.choose_battle_side(root, army)
    if side is None:
        return
    bid, rid = root['engagement_campaign_id'], str(root['_id'])
    snapshot = w.battle_army_snapshot(army)
    entry = {'campaign_id': str(army['_id']), 'tg_id': army['tg_id'],
             'player_name': army['player_name'], 'side': side, 'joined_at': at}
    await halt(w, army, point, at, bid, rid)
    # Storage buckets preserve old per-army loss APIs, never define allegiance.
    bucket = 'defender' if side == 'defender' else 'attacker'
    snapshot_key = 'battle_defender_snapshot' if bucket == 'defender' else 'battle_attacker_snapshots'
    await w.campaigns.update_one({'_id': root['_id'], 'battle_open': True}, {
        '$push': {'battle_joins': entry, f'battle_{bucket}_joins': entry,
                  f'battle_{bucket}_army_ids': str(army['_id']), snapshot_key: snapshot},
        '$addToSet': {'battle_participant_tg_ids': army['tg_id']}})
    await announce(w, root, f"battle-join:{bid}:{army['_id']}",
                   f"⚔️ لشکر {army['player_name']} به نبرد {label(point)} رسید.")
    return True


async def detect(w):
    # Recompute positions after every stop: later arrivals now meet a stationary army.
    while await _detect_pass(w):
        pass


async def _detect_pass(w):
    at = w.now()
    await w.game_settings.update_one({'_id': 'encounter_engine_v2'},
        {'$setOnInsert': {'started_at': at}}, upsert=True)
    engine_state = await w.game_settings.find_one({'_id': 'encounter_engine_v2'})
    epoch = engine_state['started_at']
    previous_peace = set(engine_state.get('peace_pairs', []))
    armies = await w.campaigns.find({'active': True}).to_list(None)
    events = []
    partners = {uid: await w.allied_tg_ids(uid) for uid in {a['tg_id'] for a in armies}}
    current_peace = set()
    for a, b in combinations(armies, 2):
        if a['tg_id'] == b['tg_id']:
            continue
        if a.get('engagement_locked') and b.get('engagement_locked'):
            continue
        pair_key = ':'.join(map(str, sorted((a['tg_id'], b['tg_id']))))
        if b['tg_id'] in partners[a['tg_id']]:
            current_peace.add(pair_key)
            continue
        if pair_key in previous_peace:
            def current_point(army):
                if army.get('stationed_edge'):
                    return {'kind': 'edge', **army['stationed_edge']}
                for segment in legs(army, w.TRAVEL_GRAPH, at):
                    if segment[2] <= at < segment[3]:
                        return point_at(army, at, 'edge', segment[:2], w.TRAVEL_GRAPH, at)
                if army.get('arrival_at') and army['arrival_at'] <= at:
                    return {'kind': 'castle', 'castle': army['target_castle']}
            first_point, second_point = current_point(a), current_point(b)
            if first_point and first_point == second_point:
                events.append((at, str(a['_id']), str(b['_id']), first_point))
                continue
        cutoff = max(epoch, a.get('encounters_checked_at') or epoch,
                     b.get('encounters_checked_at') or epoch,
                     a.get('battle_cancelled_at') or epoch, b.get('battle_cancelled_at') or epoch,
                     a.get('combat_resolved_at') or epoch, b.get('combat_resolved_at') or epoch)
        for when, kind, place in encounters(a, b, w.TRAVEL_GRAPH, at):
            if when < cutoff:
                continue
            closed = [x.get(k) for x in (a, b) for k in ('battle_cancelled_at', 'combat_resolved_at') if x.get(k)]
            if closed and when <= max(closed):
                continue
            checked = [x.get('encounters_checked_at') for x in (a, b) if x.get('encounters_checked_at')]
            if checked and when <= max(checked):
                continue
            # Closing a case permits departure without restarting that same
            # encounter at the departure instant. A later meeting is a new case.
            departing = any(when == x.get('moved_at') and str(y['_id']) in x.get('released_with_army_ids', [])
                            for x, y in ((a, b), (b, a)))
            if departing:
                continue
            point = point_at(a, when, kind, place, w.TRAVEL_GRAPH, at)
            if point:
                events.append((when, str(a['_id']), str(b['_id']), point))
                break
    events.sort(key=lambda e: e[:3])
    for when, aid, bid, point in events:
        a = await w.campaigns.find_one({'_id': ObjectId(aid), 'active': True})
        b = await w.campaigns.find_one({'_id': ObjectId(bid), 'active': True})
        if not a or not b:
            continue
        if a.get('engagement_locked') and b.get('engagement_locked'):
            continue
        locked = a if a.get('engagement_locked') else b if b.get('engagement_locked') else None
        if locked:
            other = b if locked is a else a
            root = await w.campaigns.find_one({'engagement_campaign_id': locked.get('engagement_campaign_id'),
                                             'battle_is_root': True, 'battle_open': True})
            if root and (root.get('battle_contact') == point or (point['kind'] == 'castle' and root.get('battle_location') == point['castle'])):
                if await join(w, root, other, point, when):
                    return True
            continue
        # An earlier event may have stopped one of these armies elsewhere.
        if any(x.get('stationed_at') and x['stationed_at'] > when for x in (a, b)):
            continue
        await start(w, a, b, point, when)
        return True
    await w.campaigns.update_many({'_id': {'$in': [a['_id'] for a in armies]}},
                                 {'$set': {'encounters_checked_at': at}})

    await w.game_settings.update_one({'_id': 'encounter_engine_v2'}, {'$set': {'peace_pairs': sorted(current_peace)}})
