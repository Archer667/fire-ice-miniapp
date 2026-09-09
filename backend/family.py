"""Character-bound families; persisted schedules and replayable wallet operations.

All callers run under game_state_lock (one API worker). Family writes use a
durable intent and atomic wallet receipts; recovery runs before other gameplay.
"""
from copy import deepcopy
from datetime import datetime, timedelta
from uuid import uuid4
import secrets
from fastapi import HTTPException
from db import db, players
from game import now, apply_production, production_fields
from project_engine import wallet_once, member_for

marriages = db.family_marriages
children = db.family_children
operations = db.family_operations
DEFAULTS = {'marriage_gold': 200, 'marriage_wine': 40, 'training_gold': 25, 'training_food': 30}
STAGES = ['مراقبت و پرورش', 'خواندن و آداب خاندان', 'آموزش راهبرد', 'آمادگی فرمانروایی']
OPEN = ['proposed', 'accepted', 'active']

def key(p):
    return f"{p['tg_id']}:{p.get('created_at')}"

def active(p):
    return bool(p and p.get('castle') and p.get('region') and not p.get('is_dead') and not p.get('registration_reset'))

async def settings():
    row = await db.game_settings.find_one({'_id': 'family'}) or {}
    return {**DEFAULTS, **{k: row[k] for k in DEFAULTS if k in row}}

async def person(uid):
    from auth import get_admin_role
    p = await players.find_one({'tg_id': uid})
    if not active(p) or await get_admin_role({'id': uid}):
        raise HTTPException(403, 'این کاراکتر زنده و خاندان‌دار نیست')
    return p

def clean(row):
    return {('id' if k == '_id' else k): v for k, v in row.items() if k not in ('birth_plan', 'wallets')}

async def notice(event, recipients, text):
    await db.family_notices.update_one({'_id': event}, {'$setOnInsert': {
        'recipients': list(set(recipients)), 'text': text, 'sent': [], 'complete': False,
    }}, upsert=True)

async def flush_notices():
    from config import SYSTEM_SENDER_ID, SYSTEM_SENDER_NAME
    import telegram_bot
    async for n in db.family_notices.find({'complete': False}):
        for uid in n['recipients']:
            if uid in n['sent']:
                continue
            await db.messages.update_one({'_id': f"family:{n['_id']}:{uid}"}, {'$setOnInsert': {
                'from_id': SYSTEM_SENDER_ID, 'from_name': SYSTEM_SENDER_NAME, 'to_id': uid,
                'to_name': '', 'text': n['text'], 'kind': 'family', 'read': False, 'created_at': now(),
            }}, upsert=True)
            telegram_bot.push(uid, n['text'])
            await db.family_notices.update_one({'_id': n['_id']}, {'$addToSet': {'sent': uid}})
        await db.family_notices.update_one({'_id': n['_id']}, {'$set': {'complete': True}})

async def commit(op):
    """Only one debit per intent. Failed debit makes no domain change."""
    await operations.insert_one(op)
    await finish(op)

async def finish(op):
    try:
        for i, w in enumerate(op.get('wallets', [])):
            await wallet_once(w['member'], w['cost'], f"family:{op['_id']}:{i}", debit=w.get('debit', False))
    except HTTPException:
        await operations.update_one({'_id': op['_id']}, {'$set': {'complete': True, 'failed': True}})
        raise
    for change in op.get('changes', []):
        await db[change['collection']].update_one(change['query'], change['update'], upsert=change.get('upsert', False))
    for n in op.get('notices', []):
        await notice(n['event'], n['recipients'], n['text'])
    await operations.update_one({'_id': op['_id']}, {'$set': {'complete': True}})

async def recover():
    async for op in operations.find({'complete': False}):
        try:
            await finish(op)
        except HTTPException:
            pass  # An unpaid intent is rejected, not retried against a later balance.
    async for op in db.family_successions.find({'complete': False}):
        await finish_succession(op)

def change(collection, query, fields):
    return {'collection': collection, 'query': query, 'update': {'$set': fields}}

async def propose(p, target_id, request_id, penalty_gold=100):
    if type(penalty_gold) is not int or not 1 <= penalty_gold <= 1000000000:
        raise HTTPException(400, 'غرامت را به‌صورت عدد صحیح مثبت مشخص کن')
    old = await marriages.find_one({'_id': request_id})
    if old:
        if old['parents'][0]['key'] != key(p):
            raise HTTPException(409, 'شناسهٔ درخواست تکراری است')
        return clean(old)
    target = await person(target_id)
    if p['tg_id'] == target_id or p.get('gender') == target.get('gender') or {p.get('gender'), target.get('gender')} != {'lord', 'lady'}:
        raise HTTPException(400, 'دو کاراکتر متفاوت، یک لرد و یک لیدی انتخاب کن')
    # Never marry a biological parent, child or sibling, including past characters.
    a, b = p.get('family_child_id'), target.get('family_child_id')
    ca = await children.find_one({'_id': a}) if a else None
    cb = await children.find_one({'_id': b}) if b else None
    if ((ca and key(target) in ca.get('ancestor_keys', ca['parent_keys'])) or (cb and key(p) in cb.get('ancestor_keys', cb['parent_keys'])) or
            (ca and cb and set(ca['parent_keys']) & set(cb['parent_keys']))):
        raise HTTPException(400, 'ازدواج با والد، فرزند یا خواهر و برادر مجاز نیست')
    if await marriages.find_one({'parent_keys': {'$in': [key(p), key(target)]}, 'status': {'$in': OPEN}}):
        raise HTTPException(409, 'یکی از طرفین همسر یا درخواست باز دارد')
    from marriage_pacts import TERMS
    s = await settings()
    half = {'gold': s['marriage_gold'] // 2, 'wine': s['marriage_wine'] // 2}
    parents = [{**member_for(v, 0), 'key': key(v), 'gender': v['gender']} for v in (p, target)]
    doc = {'_id': request_id, 'parents': parents, 'parent_keys': [v['key'] for v in parents],
           'status': 'proposed', 'penalty_gold': penalty_gold, 'half_cost': half, 'paid': [p['tg_id']], 'created_at': now(),
           'expires_at': now() + timedelta(hours=48)}
    await commit({'_id': str(uuid4()), 'complete': False,
        'wallets': [{'member': parents[0], 'cost': half, 'debit': True}],
        'changes': [{'collection': 'family_marriages', 'query': {'_id': request_id}, 'update': {'$setOnInsert': doc}, 'upsert': True}],
        'notices': [{'event': request_id + ':proposal', 'recipients': [target_id],
            'text': f"💍 {p['name']} درخواست ازدواج فرستاد. سهم هر طرف: {half['gold']} طلا و {half['wine']} شراب. تا ۴۸ ساعت بازی در «خاندان و خانواده» پاسخ بده.\nغرامت فسخ: {penalty_gold:,} طلا، پرداخت به همسر.\n{TERMS}"}]})
    return clean(doc)

async def close_marriage(m, status, reason):
    from marriage_pacts import dissolve_changes
    pact_changes = await dissolve_changes(m) if m['status'] == 'active' else []
    # Active weddings have consumed their cost; pending reservations are refunded.
    wallets = [{'member': p, 'cost': m['half_cost']} for p in m['parents'] if p['tg_id'] in m['paid']] if m['status'] != 'active' else []
    await commit({'_id': str(uuid4()), 'complete': False, 'wallets': wallets,
        'changes': [change('family_marriages', {'_id': m['_id']}, {'status': status, 'reason': reason, 'ended_at': now()})] + pact_changes,
        'notices': [{'event': m['_id'] + ':' + status, 'recipients': [p['tg_id'] for p in m['parents']],
                     'text': '💍 وضعیت ازدواج: ' + reason + ('\nآورده‌های رزروشده بازگشتند.' if wallets else '')}]})

async def respond(p, mid, accept):
    m = await marriages.find_one({'_id': mid})
    if not m or key(p) not in m['parent_keys']:
        raise HTTPException(404, 'درخواست پیدا نشد')
    if m['status'] != 'proposed':
        raise HTTPException(409, 'این درخواست دیگر منتظر پاسخ نیست')
    if not accept:
        await close_marriage(m, 'rejected', 'درخواست توسط یکی از طرفین رد یا پس گرفته شد')
    else:
        if key(p) != m['parents'][1]['key']:
            raise HTTPException(403, 'فقط طرف دریافت‌کننده می‌تواند قبول کند')
        from public_audience import _admin_ids
        await commit({'_id': str(uuid4()), 'complete': False,
            'wallets': [{'member': m['parents'][1], 'cost': m['half_cost'], 'debit': True}],
            'changes': [change('family_marriages', {'_id': mid}, {'status': 'accepted', 'paid': [x['tg_id'] for x in m['parents']], 'expires_at': now() + timedelta(hours=72)})],
            'notices': [{'event': mid + ':accepted', 'recipients': list(await _admin_ids()), 'text': '💍 درخواست ازدواج منتظر تأیید مدیریت: ' + ' و '.join(x['name'] for x in m['parents'])}]})
    return {'ok': True}

async def approve(mid, accepted, reason):
    m = await marriages.find_one({'_id': mid})
    if not m or m['status'] != 'accepted':
        raise HTTPException(409, 'درخواست آمادهٔ بررسی نیست')
    if not accepted:
        await close_marriage(m, 'rejected', reason or 'رد درخواست توسط مدیریت')
        return {'ok': True}
    for parent in m['parents']:
        p = await person(parent['tg_id'])
        if key(p) != parent['key']:
            raise HTTPException(409, 'کاراکتر یکی از طرفین تغییر کرده است')
    if not m.get('penalty_gold'):
        raise HTTPException(409, 'درخواست قدیمی غرامت ندارد؛ آن را رد کنید تا با توافق جدید ثبت شود')
    from marriage_pacts import pact_changes, TERMS
    alliance_id, pact_updates = await pact_changes(m)
    count = secrets.choice([2, 3, 4])
    plan, at = [], now()
    for i in range(count):
        if i % 2 == 0:
            side = secrets.randbelow(2)
        else:
            side = 1 - plan[-1]['side']
        at += timedelta(seconds=secrets.randbelow(86401) + 86400)
        gender = secrets.choice(['lord', 'lady'])
        fallback = secrets.choice(['آریک', 'دارن', 'آلن', 'رایان'] if gender == 'lord' else ['لیارا', 'آریا', 'الینا', 'میرا'])
        plan.append({'id': str(uuid4()), 'at': at, 'side': side, 'gender': gender, 'fallback_name': fallback})
    from public_audience import public_recipients
    recipients = [p['tg_id'] for p in await public_recipients()]
    await commit({'_id': str(uuid4()), 'complete': False, 'changes': [change('family_marriages', {'_id': mid}, {
        'status': 'active', 'alliance_id': alliance_id, 'started_at': now(), 'birth_plan': plan, 'training_cost': {
            'gold': (await settings())['training_gold'], 'food': (await settings())['training_food']}})] + pact_updates,
        'notices': [{'event': mid + ':wedding', 'recipients': recipients,
                     'text': '💍 پیوند دو خاندان\n' + ' و '.join(p['name'] for p in m['parents']) + '\nبا رضایت دو طرف و تأیید مدیریت ازدواج کردند. پیمان کامل بدون هزینهٔ پیمان برقرار شد. تا پایان ازدواج، خرابکاری علیه همسر ممنوع است.'}]})
    return {'ok': True}

async def tick():
    import game_clock
    if game_clock.paused():
        return
    at = now()
    async for m in marriages.find({'status': {'$in': OPEN}}):
        people = [await players.find_one({'tg_id': p['tg_id']}) for p in m['parents']]
        if any(not active(p) or key(p) != old['key'] for p, old in zip(people, m['parents'])):
            await close_marriage(m, 'ended', 'با پایان زندگی یکی از کاراکترها، این پیوند پایان یافت')
            continue
        if m['status'] != 'active':
            if m['expires_at'] <= at:
                await close_marriage(m, 'expired', 'مهلت پاسخ یا بررسی به پایان رسید')
            continue
        for birth in m['birth_plan']:
            if birth['at'] > at:
                break
            if birth['id'] in m.get('born_ids', []):
                continue
            patron = people[birth['side']]
            ancestors = set(m['parent_keys'])
            for parent in people:
                origin = await children.find_one({'_id': parent.get('family_child_id', '')})
                if origin:
                    ancestors.update(origin.get('ancestor_keys', origin['parent_keys']))
            child = {'_id': birth['id'], 'ancestor_keys': sorted(ancestors), 'marriage_id': m['_id'], 'parent_keys': m['parent_keys'],
                     'parents': m['parents'], 'patron_key': key(patron), 'patron_id': patron['tg_id'],
                     'residence': patron['castle'], 'name': 'فرزند بی‌نام', 'named': False, 'gender': birth['gender'], 'fallback_name': birth.get('fallback_name', 'آریک'),
                     'born_at': birth['at'], 'adult_at': birth['at'] + timedelta(hours=96), 'status': 'alive',
                     'training': {}, 'training_cost': m['training_cost']}
            await children.update_one({'_id': birth['id']}, {'$setOnInsert': child}, upsert=True)
            await notice(birth['id'] + ':born', [p['tg_id'] for p in people],
                f"♥ فرزند شما متولد شد. اقامت: {patron['castle']}\n{patron['name']} نام فرزند را در «خاندان و خانواده» انتخاب می‌کند و مسئول هزینهٔ رشد و آموزش اوست. بلوغ پس از چهار روز بازی است.")
            await marriages.update_one({'_id': m['_id']}, {'$addToSet': {'born_ids': birth['id']}})
    async for c in children.find({'status': 'alive'}):
        patron = await players.find_one({'tg_id': c['patron_id']})
        if not active(patron) or key(patron) != c['patron_key']:
            await children.update_one({'_id': c['_id']}, {'$set': {'status': 'retired', 'ended_at': at}})
            continue
        if c['residence'] not in {patron['castle'], *patron.get('castle_buildings', {}).keys()}:
            await children.update_one({'_id': c['_id']}, {'$set': {'residence': patron['castle']}})
        day = min(3, max(0, int((at - c['born_at']).total_seconds() // 86400)))
        if at >= c['adult_at'] and not c.get('adult_notified'):
            if not c.get('named'):
                # Explicitly temporary and still nameable after adulthood once.
                await children.update_one({'_id': c['_id']}, {'$set': {'name': c.get('fallback_name', 'آریک')}})
            c = await children.find_one({'_id': c['_id']})
            await notice(c['_id'] + ':adult', [p['tg_id'] for p in c['parents']], f"♛ {c['name']} به بلوغ رسید و در خاندان مسئول خود آمادهٔ جانشینی است.")
            await children.update_one({'_id': c['_id']}, {'$set': {'adult_notified': True}})
        elif at < c['adult_at'] and c.get('announced_stage') != day:
            await notice(c['_id'] + ':stage:' + str(day), [c['patron_id']], f"♥ آموزش روز {day + 1} فرزند: {STAGES[day]}\nدر «خاندان و خانواده» آموزش را انجام بده؛ هزینه فقط از والد مسئول کم می‌شود.")
            await children.update_one({'_id': c['_id']}, {'$set': {'announced_stage': day}})
    await flush_notices()

async def child_action(p, cid, name=None, stage=None, specialty=None, admin=False):
    c = await children.find_one({'_id': cid, 'status': 'alive'})
    if not c:
        raise HTTPException(404, 'فرزند در دسترس نیست')
    if not admin and c['patron_key'] != key(p):
        raise HTTPException(403, 'این کار فقط در اختیار والد مسئول است')
    if name is not None:
        name = ' '.join(name.split())
        if not 2 <= len(name) <= 40 or any(ord(x) < 32 for x in name):
            raise HTTPException(400, 'نام باید بین ۲ تا ۴۰ نویسه باشد')
        if not admin and now() >= c['adult_at'] and c.get('named'):
            raise HTTPException(409, 'ویرایش نام پس از بلوغ فقط توسط ادمین انجام می‌شود')
        await children.update_one({'_id': cid}, {'$set': {'name': name, 'named': True}})
    else:
        day = int((now() - c['born_at']).total_seconds() // 86400)
        if stage != day or not 0 <= day < 4:
            raise HTTPException(409, 'مهلت این مرحلهٔ آموزش تمام شده است')
        if str(day) in c['training']:
            return {'ok': True}
        await commit({'_id': str(uuid4()), 'complete': False,
            'wallets': [{'member': member_for(p, 0), 'cost': c['training_cost'], 'debit': True}],
            'changes': [change('family_children', {'_id': cid}, {f'training.{day}': {'at': now(), 'specialty': specialty or 'strategy'}})]})
    return {'ok': True}

async def heirs(p):
    return await children.find({'patron_key': key(p), 'status': 'alive'}).sort([('born_at', 1), ('_id', 1)]).to_list(None)

async def preview(p):
    rows = await heirs(p)
    adult = [c for c in rows if c['adult_at'] <= now()]
    return {'character_key': key(p), 'heir': clean(adult[0]) if adult else None,
            'children': [clean(c) for c in rows], 'has_minors': any(c['adult_at'] > now() for c in rows)}

async def end_character(p, kill_children=False):
    async for m in marriages.find({'parent_keys': key(p), 'status': {'$in': OPEN}}):
        await close_marriage(m, 'ended', 'با مرگ یا حذف کاراکتر، پیوند پایان یافت')
    if p.get('family_child_id'):
        await children.update_one({'_id': p['family_child_id'], 'status': 'succeeded'}, {'$set': {'status': 'dead', 'ended_at': now()}})
    await children.update_many({'patron_key': key(p), 'status': 'alive'}, {'$set': {
        'status': 'dead' if kill_children else 'retired', 'ended_at': now()}})

async def succeed(p, heir, body, actor):
    from ranks import base_score, get_hierarchy_doc, title_bonus_and_rank, current_week_start
    from public_audience import public_recipients
    from character_records import death_text
    p = apply_production(p)
    heir = {**heir, 'name': heir['name'] if heir.get('named') else heir.get('fallback_name', 'آریک')}
    bonus, rank = title_bonus_and_rank(p['tg_id'], await get_hierarchy_doc())
    score = max(0, round(base_score(p) + bonus - p.get('scoreboard_baseline', 0)))
    week = current_week_start()
    baseline = p.get('weekly_baseline_score', score) if p.get('weekly_baseline_at') == week else score
    archived = {**deepcopy(p), 'is_dead': True, 'died_at': now(), 'death_reason': body.reason,
                'death_snapshot': {'castle': p['castle'], 'region': p['region'], 'score': score,
                'weekly_score': max(0, score - baseline), 'week_start': week, 'rank_label': rank}, 'archive_id': key(p)}
    archived.pop('_id', None)
    # Millisecond precision survives Mongo roundtrip; unique monotonically newer identity.
    stamp = max(datetime.utcnow().replace(microsecond=0), p['created_at'] + timedelta(seconds=1))
    from config import DEFAULT_TITLE
    fields = {**production_fields(p), 'created_at': stamp, 'name': heir['name'], 'gender': heir['gender'],
              'family_child_id': heir['_id'], 'title': DEFAULT_TITLE[heir['gender']], 'profile_image': None,
              'backstory': '', 'is_dead': False, 'registration_reset': False}
    from config import SCORE_W_ALLIANCE
    from control_settings import get as rule
    linked = await db.alliances.count_documents({'marriage_id': {'$exists': True}, 'status': 'accepted', '$or': [{'from_id': p['tg_id']}, {'to_id': p['tg_id']}]})
    if linked:
        fields['scoreboard_baseline'] = p.get('scoreboard_baseline', 0) - linked * float(rule('scoring.alliance', SCORE_W_ALLIANCE))
    newkey = key({**p, **fields})
    text = death_text(p, body.reason, body.narrative).replace(
        '🏰 قلعه‌های این کاراکتر آزاد شدند؛ سطح ساختمان‌ها حفظ می‌شود.',
        f"♛ {heir['name']} جانشین شد. قلعه‌ها، لشکرها، پروژه‌ها، امتیازها و مدال‌های خاندان حفظ شدند.")
    op = {'_id': key(p), 'complete': False, 'tg_id': p['tg_id'], 'old_created_at': p['created_at'],
          'new_key': newkey, 'fields': fields, 'archive': archived, 'heir_id': heir['_id'],
          'text': text, 'recipients': await public_recipients(), 'blacklisted': body.blacklisted,
          'reason': body.reason, 'actor': actor}
    await db.family_successions.insert_one(op)
    await finish_succession(op)
    return {'ok': True, 'succession': True, 'heir': heir['name']}

async def finish_succession(op):
    from character_records import archives, blacklist
    uid = op['tg_id']
    # Recover open project purchases/settlements before changing character identities.
    from project_engine import recover as recover_project
    async for project in db.projects.find({'$or': [{'owner_id': uid}, {f'members.{uid}': {'$exists': True}}]}):
        await recover_project(project)
    await archives.update_one({'_id': op['_id']}, {'$setOnInsert': op['archive']}, upsert=True)
    async for m in marriages.find({'parent_keys': op['_id'], 'status': {'$in': OPEN}}):
        await close_marriage(m, 'ended', 'با مرگ کاراکتر، ازدواج پایان یافت؛ تولد دیگری در این پیوند رخ نمی‌دهد')
    await players.update_one({'tg_id': uid, 'created_at': op['old_created_at']}, {'$set': op['fields']})
    if op['archive'].get('family_child_id'):
        await children.update_one({'_id': op['archive']['family_child_id']}, {'$set': {'status': 'dead', 'ended_at': op['archive']['died_at']}})
    await children.update_one({'_id': op['heir_id']}, {'$set': {'status': 'succeeded', 'successor_key': op['new_key']}})
    # Remaining siblings stay in this dynasty as reserve heirs, not biological children of the heir.
    await children.update_many({'patron_key': op['_id'], 'status': 'alive'}, {'$set': {'patron_key': op['new_key']}})
    await db.projects.update_many({'status': {'$in': ['pending', 'scheduled', 'funding', 'active']}, f'members.{uid}.character_created_at': op['old_created_at']}, {'$set': {
        f'members.{uid}.character_created_at': op['fields']['created_at'], f'members.{uid}.name': op['fields']['name']}})
    await db.projects.update_many({'owner_id': uid, 'status': {'$in': ['pending', 'scheduled', 'funding', 'active']}}, {'$set': {'owner_name': op['fields']['name']}})
    await db.caravans.update_many({'target_tg_id': uid, 'active': True, 'target_character_created_at': op['old_created_at']}, {'$set': {'target_character_created_at': op['fields']['created_at']}})
    name, gender = op['fields']['name'], op['fields']['gender']
    for collection, query, fields in (
        (db.caravans, {'tg_id': uid, 'active': True}, {'player_name': name}),
        (db.caravans, {'target_tg_id': uid, 'active': True}, {'target_name': name}),
        (db.campaigns, {'tg_id': uid, 'active': True}, {'player_name': name, 'player_gender': gender}),
        (db.campaigns, {'battle_defender_tg_id': uid, 'battle_open': True}, {'battle_defender_name': name}),
        (db.ambushes, {'tg_id': uid, 'status': {'$in': ['active', 'pending_score']}}, {'player_name': name, 'player_gender': gender}),
        (db.player_market_listings, {'seller_tg_id': uid}, {'seller_name': name}),
        (db.spy_missions, {'tg_id': uid, 'status': {'$in': ['pending', 'pending_score', 'travelling', 'active']}}, {'player_name': name}),
    ):
        await collection.update_many(query, {'$set': fields})
    for collection in (db.alliances, db.tributes):
        for side in ('from', 'to'):
            fields = {side + '_name': name}
            if collection.name == 'alliances':
                fields[side + '_gender'] = gender
            await collection.update_many({side + '_id': uid, 'status': {'$in': ['pending', 'accepted']}}, {'$set': fields})
    for field in ('battle_attacker_joins', 'battle_defender_joins', 'battle_participants'):
        await db.campaigns.update_many({'battle_open': True, field + '.tg_id': uid},
            {'$set': {field + '.$[member].player_name': name}}, array_filters=[{'member.tg_id': uid}])
    if op['blacklisted']:
        await blacklist.update_one({'_id': uid}, {'$set': {'name': op['archive']['name'], 'reason': op['reason'], 'added_by': op['actor'], 'added_at': datetime.utcnow()}}, upsert=True)
    await db.character_announcements.update_one({'_id': op['_id']}, {'$setOnInsert': {
        'text': op['text'], 'recipients': op['recipients'], 'delivered': [], 'ready': True}}, upsert=True)
    await db.family_successions.update_one({'_id': op['_id']}, {'$set': {'complete': True}})
