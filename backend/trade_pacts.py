"""Trade access within an explicit invitation batch; never transitive across groups."""
from hashlib import sha256
from db import alliances
from game_data import ALLIANCE_TYPES

TRADE_TYPES = ['trade', 'full_alliance']


async def migrate_legacy_groups():
    batches = {}
    async for row in alliances.find({'type': {'$in': list(ALLIANCE_TYPES)}, '$or': [
            {'group_id': {'$exists': False}}, {'group_id': {'$regex': '^legacy-'}}]}):
        if not row.get('created_at'):
            continue
        key = (row['from_id'], row['type'], row.get('name', ''), row.get('public', True), row['created_at'])
        batches.setdefault(key, []).append(row)
    for key, rows in batches.items():
        if len(rows) < 2:
            continue
        group = 'legacy-' + sha256(repr(key).encode()).hexdigest()[:24]
        await alliances.update_many({'_id': {'$in': [r['_id'] for r in rows]}, 'group_id': {'$exists': False}},
                                    {'$set': {'group_id': group}})


async def trade_partners(user_id):
    direct = await alliances.find({'status': 'accepted', 'type': {'$in': TRADE_TYPES},
        '$or': [{'from_id': user_id}, {'to_id': user_id}]}).to_list(None)
    groups = {a['group_id'] for a in direct if a.get('group_id')}
    rows = direct + (await alliances.find({'status': 'accepted', 'type': {'$in': TRADE_TYPES},
                    'group_id': {'$in': list(groups)}}).to_list(None) if groups else [])
    partners = {}
    for a in rows:
        for side in ('from', 'to'):
            uid = a[side + '_id']
            if uid != user_id:
                partners[uid] = {'other_id': uid, 'other_name': a[side + '_name'], 'type': a['type'],
                                'type_name': ALLIANCE_TYPES[a['type']]['name'],
                                'status': 'accepted', 'name': a.get('name', ''), 'group_id': a.get('group_id')}
    return list(partners.values())
