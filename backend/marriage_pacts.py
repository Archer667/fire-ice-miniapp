"""Marriage-owned full alliances and compensated divorce under game_state_lock."""
from uuid import uuid4
from bson import ObjectId
from fastapi import HTTPException
from db import db, players
from game import now, apply_production, can_afford

TERMS = ('پس از تأیید ازدواج، پیمان کامل بدون هزینهٔ جداگانه برقرار می‌شود. '
         'فسخ‌کننده باید غرامت توافق‌شده را کامل به همسرش بپردازد؛ بدون طلای کافی فسخ ممکن نیست. '
         'با فسخ، پیمان وابسته و تولدهای آینده متوقف می‌شوند؛ فرزندان متولدشده و مسئولیتشان باقی می‌مانند. '
         'تا زمان برقرار بودن ازدواج، ارسال رول خرابکاری علیه همسر ممنوع است.')

async def pact_changes(m):
    from family import change
    first, second = m['parents']
    matches = await db.alliances.find({'type': 'full_alliance', 'status': 'accepted', '$or': [
        {'from_id': first['tg_id'], 'to_id': second['tg_id']},
        {'from_id': second['tg_id'], 'to_id': first['tg_id']}]}).sort('created_at', 1).to_list(None)
    existing = None
    for row in matches:
        # Keep independent group memberships intact; never splice a spouse into a group.
        if row.get('group_id') and await db.alliances.count_documents({'group_id': row['group_id'], 'status': {'$in': ['accepted', 'pending']}}) > 1:
            continue
        existing = row
        break
    aid = existing['_id'] if existing else ObjectId()
    fields = {'marriage_id': m['_id'], 'penalty_gold': m['penalty_gold'], 'status': 'accepted'}
    if not existing:
        fields.update(from_id=first['tg_id'], to_id=second['tg_id'], from_name=first['name'], to_name=second['name'],
            from_gender=first['gender'], to_gender=second['gender'], type='full_alliance', wine_cost=0,
            name='پیمان ازدواج', public=True, created_at=now(), accepted_at=now(), group_id='marriage:' + m['_id'])
    result = [{'collection': 'alliances', 'query': {'_id': aid}, 'update': {'$set': fields}, 'upsert': not bool(existing)}]
    if not existing:
        for parent in m['parents']:
            p = await players.find_one({'tg_id': parent['tg_id']})
            result.append(change('players', {'tg_id': p['tg_id'], 'created_at': p['created_at']}, {'alliance_count': p.get('alliance_count', 0) + 1}))
    return str(aid), result

async def spouses(p, target):
    from family import key, active
    if not active(p) or not active(target):
        return False
    return bool(await db.family_marriages.find_one({'status': 'active',
        'parent_keys': {'$all': [key(p), key(target)]}}))

async def dissolve_changes(m):
    """Replay-safe fixed values instead of counters incremented during recovery."""
    from family import change
    aid = m.get('alliance_id')
    if not aid:
        return []
    pact = await db.alliances.find_one({'_id': ObjectId(aid), 'marriage_id': m['_id'], 'status': 'accepted'})
    if not pact:
        return []
    result = [change('alliances', {'_id': pact['_id']}, {'status': 'dissolved', 'ended_at': now()})]
    for uid in (pact['from_id'], pact['to_id']):
        p = await players.find_one({'tg_id': uid})
        if p:
            result.append(change('players', {'tg_id': uid, 'created_at': p['created_at']},
                                 {'alliance_count': max(0, p.get('alliance_count', 0) - 1)}))
    return result

async def divorce(p, mid, expected_penalty):
    from family import marriages, key, person, commit, change, member_for
    m = await marriages.find_one({'_id': mid})
    if not m or key(p) not in m['parent_keys']:
        raise HTTPException(404, 'این ازدواج متعلق به کاراکتر تو نیست')
    if m['status'] == 'divorced' and m.get('divorced_by') == p['tg_id']:
        return {'ok': True, 'penalty_paid': m['penalty_gold']}
    if m['status'] != 'active':
        raise HTTPException(409, 'فقط ازدواج برقرار را می‌توان فسخ کرد')
    penalty = m.get('penalty_gold')
    if not isinstance(penalty, int) or penalty < 1:
        raise HTTPException(409, 'این ازدواج قدیمی غرامت توافق‌شده ندارد؛ با مدیریت تماس بگیر')
    if expected_penalty != penalty:
        raise HTTPException(409, 'مبلغ غرامت تغییر کرده؛ اطلاعات ازدواج را تازه کن')
    p = apply_production(p)
    if not can_afford(p['resources'], {'gold': penalty}):
        raise HTTPException(400, f'برای فسخ باید {penalty:,} طلا غرامت به همسرت بدهی؛ طلای کافی نداری')
    partner = next(x for x in m['parents'] if x['tg_id'] != p['tg_id'])
    other = await person(partner['tg_id'])
    if key(other) != partner['key']:
        raise HTTPException(409, 'کاراکتر همسر تغییر کرده؛ اطلاعات را تازه کن')
    # Debit and receipt are atomic; recovery can finish credit/state after a crash.
    changes = await dissolve_changes(m)
    changes.append(change('family_marriages', {'_id': mid}, {'status': 'divorced',
        'divorced_by': p['tg_id'], 'ended_at': now(), 'reason': f"فسخ توسط {p['name']}؛ پرداخت {penalty:,} طلا به {other['name']}"}))
    await commit({'_id': str(uuid4()), 'complete': False,
        'wallets': [{'member': member_for(p, 0), 'cost': {'gold': penalty}, 'debit': True},
                    {'member': member_for(other, 0), 'cost': {'gold': penalty}}],
        'changes': changes, 'notices': [{'event': mid + ':divorced', 'recipients': [p['tg_id'], other['tg_id']],
            'text': f"💍 فسخ ازدواج\n{p['name']} ازدواج با {other['name']} را فسخ کرد و {penalty:,} طلا غرامت به او پرداخت شد.\nپیمان کامل وابسته لغو شد؛ تولدهای آینده متوقف شدند. فرزندان متولدشده و مسئولیت نگهداری آن‌ها حفظ می‌شوند."}]})
    return {'ok': True, 'penalty_paid': penalty}
