"""One recoverable, administrator-directed resource transfer per naval battle."""
from db import db, players
from game import apply_production, production_fields, effective_caps, now
from fastapi import HTTPException

transfers = db.naval_loot_transfers

async def recover():
    async for record in transfers.find({'complete': False}):
        # The global game lock runs this before any request/watcher mutates state.
        for change in record['changes']:
            await players.update_one({'tg_id': change['tg_id']}, {'$set': change['fields']})
        await transfers.update_one({'_id': record['_id']}, {'$set': {'complete': True}})

def loot_changes(sender, recipient, amounts, allowed):
    if not amounts or not any(amounts.values()):
        raise HTTPException(400, 'مقدار غنیمت را وارد کن')
    caps = effective_caps(recipient)
    for key, amount in amounts.items():
        if key not in allowed or type(amount) is not int or amount < 0:
            raise HTTPException(400, 'نوع یا مقدار غنیمت نامعتبر است')
        if sender['resources'].get(key, 0) < amount:
            raise HTTPException(409, 'موجودی مدافع کافی نیست؛ فهرست را تازه کن')
        if amount and recipient['resources'].get(key, 0) + amount > caps.get(key, float('inf')):
            raise HTTPException(409, 'ظرفیت انبار مهاجم کافی نیست؛ مقدار غنیمت را کاهش بده')
    for key, amount in amounts.items():
        sender['resources'][key] = sender['resources'].get(key, 0) - amount
        recipient['resources'][key] = recipient['resources'].get(key, 0) + amount
    return [{'tg_id': p['tg_id'], 'fields': production_fields(p)} for p in (sender, recipient)]

async def transfer(root, recipient_id, amounts, actor):
    from routers.war import owner_of_castle
    from routers.admin import ROLEPLAY_RESOURCE_NAMES
    battle_id = root.get('engagement_campaign_id') or str(root['_id'])
    previous = await transfers.find_one({'_id': battle_id})
    if previous:
        if previous['recipient'] != recipient_id or previous['amounts'] != amounts:
            raise HTTPException(409, 'غنیمت این نبرد قبلاً ثبت شده است')
        await recover()
        return {'ok': True, 'already_applied': True}
    if root.get('op_type') != 'naval_raid' or not root.get('battle_open') or root.get('combat_resolved_at') or root.get('battle_cancelled_at'):
        raise HTTPException(409, 'فقط نبرد باز غارت دریایی می‌تواند غنیمت داشته باشد')
    if str(root.get('battle_location', '')).startswith('مسیر '):
        raise HTTPException(400, 'درگیری مسیر، غارت خزانهٔ قلعه نیست')
    attacker_ids = {root['tg_id']}
    from db import campaigns
    async for army in campaigns.find({'engagement_campaign_id': battle_id, '_id': {'$in': [__import__('bson').ObjectId(x) for x in root.get('battle_attacker_army_ids', [])]}}):
        attacker_ids.add(army['tg_id'])
    if recipient_id not in attacker_ids:
        raise HTTPException(400, 'گیرنده باید از مهاجمان همین نبرد باشد')
    sender = await owner_of_castle(root.get('battle_location') or root['target_castle'])
    recipient = await players.find_one({'tg_id': recipient_id, 'is_dead': {'$ne': True}, 'castle': {'$nin': [None, '']}})
    if not sender or not recipient or sender['tg_id'] == recipient_id or sender['tg_id'] != root.get('battle_defender_tg_id'):
        raise HTTPException(409, 'مالکیت یا طرفین نبرد تغییر کرده است؛ پرونده را تازه کن')
    sender, recipient = apply_production(sender), apply_production(recipient)
    changes = loot_changes(sender, recipient, amounts, set(ROLEPLAY_RESOURCE_NAMES) - {'men'})
    await transfers.insert_one({'_id': battle_id, 'changes': changes, 'amounts': amounts,
                               'sender': sender['tg_id'], 'recipient': recipient_id,
                               'actor': actor, 'created_at': now(), 'complete': False})
    await recover()
    return {'ok': True}
