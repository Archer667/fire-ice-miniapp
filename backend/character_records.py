from public_audience import public_recipients, public_players
"""Character history and castle buildings are independent of Telegram accounts."""
from copy import deepcopy
from datetime import datetime
from db import db, players
from game import now, apply_production
from config import STARTING_RESOURCES
from control_settings import get as rule

blacklist = db.account_blacklist  # Deliberately excluded from every season/reset cleanup.
archives = db.character_archives
vacant = db.vacant_castle_buildings

async def save_castles(player):
    states = dict(player.get('castle_buildings') or {})
    if player.get('castle'):
        states[player['castle']] = player.get('buildings', {})
    for castle, buildings in states.items():
        # A vacant castle keeps completed levels, not a previous owner's paid queue.
        levels = {key: {'level': value.get('level', 0)} if isinstance(value, dict) else value
                  for key, value in buildings.items()}
        await vacant.update_one({'_id': castle}, {'$set': {'buildings': levels}}, upsert=True)

async def vacant_buildings(castle):
    row = await vacant.find_one({'_id': castle}) or {}
    from routers.war import all_castle_names_and_ports
    from castle_defaults import harbor_default
    _, ports = await all_castle_names_and_ports()
    buildings = deepcopy(row.get('buildings', {}))
    return harbor_default(buildings) if castle in ports else buildings

def death_text(player, reason, narrative):
    title = 'لیدی' if player.get('gender') == 'lady' else 'لرد'
    parts = ['🐦‍⬛ کلاغ سیاه از راه رسید', f"⚔️ {title} {player['name']} درگذشت"]
    if player.get('house'): parts.append(f"از خاندان {player['house']}")
    if player.get('castle'): parts.append(f"فرمانروای قلعهٔ {player['castle']}")
    parts += ['📜 علت مرگ به اعلام مدیریت:', reason,
              '🏰 قلعه‌های این کاراکتر آزاد شدند؛ سطح ساختمان‌ها حفظ می‌شود.']
    if narrative.strip(): parts += ['📖 روایت کاراکتر', narrative.strip()]
    parts.append('🕯 داستان این کاراکتر به پایان رسید.')
    return '\n\n'.join(parts)

async def retire(tg_id, body, actor):
    from routers.admin import _mark_player_dead
    from fastapi import HTTPException
    from auth import get_admin_role
    target = await players.find_one({'tg_id': tg_id})
    if not target or target.get('registration_reset'):
        raise HTTPException(409, 'این کاراکتر قبلاً حذف شده؛ فهرست را تازه کن')
    if await get_admin_role({'id': tg_id}):
        raise HTTPException(400, 'حساب ادمین از این مسیر حذف نمی‌شود')
    target = apply_production(target) if target.get('castle') else target
    already_dead = target.get('is_dead')
    key = f"{tg_id}:{target.get('created_at')}"
    if body.character_key and body.character_key != key:
        raise HTTPException(409, 'شخصیت این حساب تغییر کرده؛ فهرست را تازه کن')
    if body.action == 'death' and not already_dead:
        from family import preview, succeed, end_character
        state = await preview(target)
        if state['heir'] and not getattr(body, 'kill_heirs', False):
            from family import children
            heir = await children.find_one({'_id': state['heir']['id']})
            return await succeed(target, heir, body, actor)
    from family import end_character
    await end_character(target, getattr(body, 'kill_heirs', False))
    await db.character_retirements.update_one({'_id': key}, {'$setOnInsert': {'snapshot': target}}, upsert=True)
    target = (await db.character_retirements.find_one({'_id': key}))['snapshot']
    if body.blacklisted:
        await blacklist.update_one({'_id': tg_id}, {'$set': {
            'name': target['name'], 'reason': body.reason, 'added_by': actor,
            'added_at': datetime.utcnow(),
        }}, upsert=True)
    await save_castles(target)
    if not already_dead:
        await _mark_player_dead(target, body.reason or 'حذف بازیکن به فرمان مدیریت', notify=False)
    dead = await players.find_one({'tg_id': tg_id})
    if body.action == 'death' or target.get('is_dead'):
        archived = {k: v for k, v in dead.items() if k != '_id'}
        archived['archive_id'] = key
        await archives.update_one({'_id': key}, {'$setOnInsert': archived}, upsert=True)
    if body.action == 'death':
        text = death_text(target, body.reason, body.narrative)
        recipients = await public_recipients()
        await db.character_announcements.update_one({'_id': key}, {'$setOnInsert': {
            'text': text, 'recipients': recipients, 'delivered': [], 'ready': False,
        }}, upsert=True)
    # Character-bound work must not reward or charge a newly registered character.
    await db.caravans.update_many({'$or': [{'tg_id': tg_id}, {'target_tg_id': tg_id}], 'active': True}, {'$set': {'active': False, 'arrival_notified': True, 'delivery_failed': True}})
    await db.player_market_listings.delete_many({'seller_tg_id': tg_id})
    await db.spy_missions.update_many({'$or': [{'tg_id': tg_id}, {'target_tg_id': tg_id}], 'status': {'$in': ['pending', 'pending_score', 'travelling', 'active']}}, {'$set': {'status': 'cancelled'}})
    for collection in (db.alliances, db.tributes):
        await collection.update_many({'$or': [{'from_id': tg_id}, {'to_id': tg_id}], 'status': {'$in': ['pending', 'accepted']}}, {'$set': {'status': 'cancelled'}})
    await players.update_one({'tg_id': tg_id}, {'$set': {
        'is_dead': False, 'registration_reset': True, 'castle': None, 'region': None,
        'house': None, 'is_port': False, 'buildings': {}, 'castle_buildings': {},
        'resources': deepcopy(rule('economy.starting_resources', STARTING_RESOURCES)),
        'troops': {}, 'equipment': {}, 'last_tick': now(),
    }})
    if body.action == 'death':
        await db.character_announcements.update_one({'_id': key}, {'$set': {'ready': True}})
    return {'ok': True}

async def recover_swaps():
    from naval_loot import recover as recover_loot
    await recover_loot()
    from family import recover
    await recover()
    async for swap in db.castle_swaps.find({'complete': False}):
        for change in swap['changes']:
            await players.update_one({'tg_id': change['tg_id']}, {'$set': change['fields']})
        await db.castle_swaps.update_one({'_id': swap['_id']}, {'$set': {'complete': True}})

async def swap_castles(first_id, first_castle, second_id, second_castle):
    from fastapi import HTTPException
    from auth import get_admin_role
    from routers.admin import _castle_region_map, all_castle_terrain, CASTLE_HOUSES
    if first_id == second_id or first_castle == second_castle:
        raise HTTPException(400, 'دو بازیکن و دو قلعهٔ متفاوت انتخاب کن')
    people = [await players.find_one({'tg_id': uid}) for uid in (first_id, second_id)]
    chosen = [first_castle, second_castle]
    regions, terrain = await _castle_region_map(), await all_castle_terrain()
    if any(castle not in regions for castle in chosen):
        raise HTTPException(400, 'یکی از قلعه‌ها در نقشه شناخته‌شده نیست')
    states = []
    for person, castle in zip(people, chosen):
        if not person or person.get('is_dead') or not person.get('castle'):
            raise HTTPException(409, 'هر دو بازیکن باید زنده و خاندان‌دار باشند')
        if await get_admin_role({'id': person['tg_id']}):
            raise HTTPException(400, 'قلعهٔ حساب ادمین قابل جابجایی نیست')
        person.update(apply_production(person))
        castles = {**person.get('castle_buildings', {}), person['castle']: person.get('buildings', {})}
        if castle not in castles:
            raise HTTPException(409, 'مالکیت قلعه تغییر کرده؛ فهرست را تازه کن')
        states.append(castles[castle])
    from game import production_fields
    for person in people:
        await players.update_one({'tg_id': person['tg_id']}, {'$set': production_fields(person)})
    changes = []
    for i, person in enumerate(people):
        outgoing, incoming = chosen[i], chosen[1-i]
        fields = {'castle_buildings': deepcopy(person.get('castle_buildings', {}))}
        if person['castle'] == outgoing:
            fields.update(castle=incoming, buildings=states[1-i], region=regions[incoming],
                          house=CASTLE_HOUSES.get(incoming), is_port=terrain.get(incoming, 'land') in ('coastal', 'sea'))
        else:
            fields['castle_buildings'].pop(outgoing)
            fields['castle_buildings'][incoming] = states[1-i]
        changes.append({'tg_id': person['tg_id'], 'fields': fields})
    await db.castle_swaps.insert_one({'changes': changes, 'complete': False, 'created_at': now()})
    await recover_swaps()
    return {'ok': True}

async def deliver_announcements():
    from routers.ravens import send_system_message
    async for item in db.character_announcements.find({'ready': True, 'complete': {'$ne': True}}):
        for recipient in item['recipients']:
            uid = recipient['tg_id']
            if uid in item.get('delivered', []): continue
            await send_system_message(uid, recipient.get('name', ''), item['text'], kind='character_death')
            await db.character_announcements.update_one({'_id': item['_id']}, {'$addToSet': {'delivered': uid}})
        await db.character_announcements.update_one({'_id': item['_id']}, {'$set': {'complete': True}})
