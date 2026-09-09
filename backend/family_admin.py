"""Explicit, audited administrative overrides for established families."""
from datetime import timezone
from uuid import uuid4
from bson import ObjectId
from fastapi import HTTPException
from db import db
from game import now, apply_production, can_afford
from family import marriages, children, person, key, commit, change, member_for, clean
from marriage_pacts import dissolve_changes

async def current(mid, revision):
    m = await marriages.find_one({'_id': mid, 'status': 'active'})
    if not m or m.get('admin_revision', 0) != revision:
        raise HTTPException(409, 'وضعیت ازدواج تغییر کرده؛ فهرست را تازه کن')
    return m

async def save(actor, reason, changes, recipients, text):
    reason = reason.strip()
    if not reason:
        raise HTTPException(400, 'دلیل تصمیم مدیریت را بنویس')
    oid = str(uuid4())
    await commit({'_id': oid, 'complete': False, 'admin_actor': actor, 'admin_reason': reason,
        'changes': changes, 'notices': [{'event': 'admin:' + oid, 'recipients': recipients,
        'text': text + '\nدلیل مدیریت: ' + reason}]})
    return {'ok': True}

async def penalty(mid, revision, amount, reason, actor):
    m = await current(mid, revision)
    changes = [change('family_marriages', {'_id': mid}, {'penalty_gold': amount, 'admin_revision': revision + 1})]
    if m.get('alliance_id'):
        pact = await db.alliances.find_one({'_id': ObjectId(m['alliance_id']), 'marriage_id': mid, 'status': 'accepted'})
        if not pact:
            raise HTTPException(409, 'پیمان وابسته برقرار نیست؛ وضعیت ازدواج را بررسی کن')
        changes.append(change('alliances', {'_id': pact['_id']}, {'penalty_gold': amount}))
    return await save(actor, reason, changes, [p['tg_id'] for p in m['parents']],
        f"💍 مدیریت غرامت فسخ ازدواج و پیمان شما را از {m.get('penalty_gold', 0):,} به {amount:,} طلا تغییر داد. این مبلغ اکنون برای فسخ اعمال می‌شود؛ فعلاً پولی کسر نشده است.")

async def force_divorce(mid, revision, payer_id, reason, actor):
    m = await current(mid, revision)
    if not reason.strip():
        raise HTTPException(400, 'دلیل فسخ ادمینی را بنویس')
    wallets = []
    paid = 0
    description = 'بدون دریافت غرامت'
    if payer_id is not None:
        if payer_id not in [p['tg_id'] for p in m['parents']]:
            raise HTTPException(400, 'پرداخت‌کننده باید یکی از همسران باشد')
        people = [await person(p['tg_id']) for p in m['parents']]
        if any(key(p) != old['key'] for p, old in zip(people, m['parents'])):
            raise HTTPException(409, 'کاراکتر یکی از طرفین تغییر کرده است')
        payer = apply_production(next(p for p in people if p['tg_id'] == payer_id))
        receiver = next(p for p in people if p['tg_id'] != payer_id)
        paid = m.get('penalty_gold', 0)
        if paid < 1 or not can_afford(payer['resources'], {'gold': paid}):
            raise HTTPException(400, 'پرداخت‌کننده طلای کافی برای غرامت ندارد؛ فسخ انجام نشد')
        wallets = [{'member': member_for(payer, 0), 'cost': {'gold': paid}, 'debit': True},
                   {'member': member_for(receiver, 0), 'cost': {'gold': paid}}]
        description = f"با پرداخت {paid:,} طلا از {payer['name']} به {receiver['name']}"
    changes = await dissolve_changes(m)
    changes.append(change('family_marriages', {'_id': mid}, {'status': 'divorced', 'ended_at': now(),
        'reason': reason.strip(), 'divorced_by_admin': actor, 'divorced_by': payer_id,
        'admin_revision': revision + 1, 'admin_penalty_paid': paid}))
    oid = str(uuid4())
    await commit({'_id': oid, 'complete': False, 'admin_actor': actor, 'admin_reason': reason.strip(),
        'wallets': wallets, 'changes': changes, 'notices': [{'event': 'admin:' + oid,
            'recipients': [p['tg_id'] for p in m['parents']],
            'text': f"💍 ازدواج شما به دستور مدیریت {description} فسخ شد.\nپیمان وابسته و تولدهای آینده پایان یافتند؛ فرزندان فعلی و مسئولیتشان حفظ می‌شوند.\nدلیل مدیریت: {reason.strip()}"}]})
    return {'ok': True, 'penalty_paid': paid}

async def schedule(mid, revision, entries, reason, actor):
    m = await current(mid, revision)
    born = {c['_id'] async for c in children.find({'marriage_id': mid}, {'_id': 1})} | set(m.get('born_ids', []))
    pending = [b for b in m['birth_plan'] if b['id'] not in born]
    if not pending or len(entries) != len(pending) or {str(e.child_id) for e in entries} != {b['id'] for b in pending}:
        raise HTTPException(409, 'فهرست تولدهای باقی‌مانده تغییر کرده؛ اطلاعات را تازه کن')
    dates = {}
    for e in entries:
        if e.at.tzinfo is None:
            raise HTTPException(400, 'منطقهٔ زمانی تاریخ باید مشخص باشد')
        dates[str(e.child_id)] = e.at.astimezone(timezone.utc).replace(tzinfo=None, microsecond=0)
        if dates[str(e.child_id)] <= now():
            raise HTTPException(400, 'تولد جدید باید در آیندهٔ ساعت بازی باشد')
    plan = [{**b, 'at': dates.get(b['id'], b['at'])} for b in m['birth_plan']]
    if any(plan[i]['at'] >= plan[i+1]['at'] for i in range(len(plan)-1)):
        raise HTTPException(400, 'ترتیب تولدها باید حفظ شود؛ هر تولد بعد از قبلی باشد')
    # Administrative override may deliberately go outside the normal 24–48h interval.
    return await save(actor, reason, [change('family_marriages', {'_id': mid},
        {'birth_plan': plan, 'admin_revision': revision + 1})], [p['tg_id'] for p in m['parents']],
        '♥ مدیریت زمان‌بندی تولدهای آیندهٔ خانوادهٔ شما را اصلاح کرد. تاریخ تولد و بلوغ فرزندان متولدشده تغییر نکرد.')

async def move(cid, body, actor):
    c = await children.find_one({'_id': cid, 'status': 'alive'})
    if not c or c.get('admin_revision', 0) != body.revision or c['patron_key'] != body.expected_patron_key:
        raise HTTPException(409, 'وضعیت فرزند تغییر کرده؛ اطلاعات را تازه کن')
    parent = next((p for p in c['parents'] if p['key'] == body.parent_key), None)
    if not parent:
        raise HTTPException(400, 'مقصد باید یکی از والدین این فرزند باشد')
    destination = await person(parent['tg_id'])
    if key(destination) != body.parent_key or destination['castle'] != body.castle:
        raise HTTPException(409, 'کاراکتر یا قلعهٔ اصلی مقصد تغییر کرده؛ فهرست را تازه کن')
    if c['patron_key'] == body.parent_key and c['residence'] == body.castle:
        raise HTTPException(400, 'فرزند همین حالا در همین خاندان و قلعه است')
    fields = {'patron_key': body.parent_key, 'patron_id': destination['tg_id'], 'residence': destination['castle'],
              'admin_revision': body.revision + 1}
    recipients = [p['tg_id'] for p in c['parents']] + [c['patron_id']]
    return await save(actor, body.reason, [change('family_children', {'_id': cid}, fields)], recipients,
        f"♥ {c['name']} به قلعهٔ اصلی {destination['castle']} منتقل شد.\nمسئول هزینه‌های آینده و خاندان جانشینی: {destination['name']}.\nنام، سن و آموزش‌های پرداخت‌شده حفظ شدند؛ هزینه‌های گذشته بازگردانده نمی‌شوند.")

async def view():
    rows = []
    async for m in marriages.find({'status': 'active'}).sort('started_at', -1):
        born = {c['_id'] async for c in children.find({'marriage_id': m['_id']}, {'_id': 1})} | set(m.get('born_ids', []))
        rows.append({**clean(m), 'pending_births': [{'id': b['id'], 'at': b['at']} for b in m.get('birth_plan', []) if b['id'] not in born]})
    kids = []
    async for c in children.find({'status': 'alive'}).sort('born_at', -1):
        destinations = []
        for parent in c['parents']:
            p = await db.players.find_one({'tg_id': parent['tg_id']})
            from family import active
            if active(p) and key(p) == parent['key']:
                destinations.append({'key': key(p), 'name': p['name'], 'castle': p['castle']})
        kids.append({**clean(c), 'destinations': destinations})
    return {'active_marriages': rows, 'children': kids}
