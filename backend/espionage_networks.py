"""Character-bound intelligence networks with durable decisions and private replies."""
from datetime import datetime, timezone
import hashlib
import inspect
import json
import re
import secrets
from uuid import UUID

from bson import ObjectId
from fastapi import APIRouter, Depends, HTTPException, Query
from pydantic import BaseModel, Field, StrictBool, StrictInt

from auth import get_user, get_full_admin
from config import SPY_GOLD_COST, SYSTEM_SENDER_ID, SYSTEM_SENDER_NAME
from control_settings import get as rule, feature_enabled
from db import db, players
import family
from game import now
from game_data import spy_travel_minutes
from project_engine import member_for
from system_reports import quota_window
from text_limits import check_text


router = APIRouter(prefix='/api/espionage', tags=['espionage'])
networks = db.espionage_networks
questions = db.espionage_questions
audits = db.espionage_audit
outbox = db.espionage_outbox
OPEN = ('pending', 'active', 'risk_review', 'suspended')
QUESTION_OPEN = ('pending', 'returned')
DEFAULTS = {'enabled': True, 'weekly_questions': 3, 'max_networks': 3}


async def full_admin(user=Depends(get_user)):
    return await get_full_admin(user)


def oid(value):
    if not ObjectId.is_valid(value):
        raise HTTPException(404, 'پرونده پیدا نشد')
    return ObjectId(value)


def draw():
    return secrets.randbelow(100) + 1


def fingerprint(value):
    return hashlib.sha256(json.dumps(value, sort_keys=True, ensure_ascii=False, default=str).encode()).hexdigest()


async def person(uid, landed=False):
    p = await players.find_one({'tg_id': uid})
    if not p or p.get('is_dead') or p.get('registration_reset') or not p.get('region') or not (p.get('castle') or p.get('landless')):
        raise HTTPException(403, 'کاراکتر فعال پیدا نشد')
    if landed and not p.get('castle'):
        raise HTTPException(403, 'برای استقرار شبکهٔ تازه به قلعهٔ مبدأ نیاز داری')
    return p


async def settings(player=None):
    row = await db.game_settings.find_one({'_id': 'espionage_networks'}) or {}
    cfg = {**DEFAULTS, 'gold_cost': int(rule('war.spy_gold_cost', SPY_GOLD_COST))}
    cfg.update({k: row[k] for k in cfg if k in row})
    if player:
        override = await db.espionage_player_limits.find_one({'tg_id': player['tg_id'], 'character_created_at': player.get('created_at')}) or {}
        cfg.update({k: override[k] for k in ('weekly_questions', 'max_networks', 'enabled') if override.get(k) is not None})
    return cfg


async def epoch():
    window = await quota_window()
    row = await db.game_settings.find_one({'_id': 'season_clock'}) or {}
    return row.get('started_at'), window


def mutation(collection, query, fields, *, insert=False):
    return {'collection': collection, 'query': query,
            'update': {'$setOnInsert' if insert else '$set': fields}, 'upsert': insert}


def notice(action, recipient, text, *, admin=False):
    row = {'_id': action + (':admin' if admin else ':' + str(recipient['tg_id'])),
           'recipient': None if admin else recipient['tg_id'],
           'character_created_at': None if admin else recipient.get('created_at'),
           'admin': admin, 'text': text, 'created_at': now(), 'complete': False}
    return mutation('espionage_outbox', {'_id': row['_id']}, row, insert=True)


async def resume(action, body):
    op = await family.operations.find_one({'_id': action})
    if not op:
        return None
    if op.get('payload_hash') != fingerprint(body):
        raise HTTPException(409, 'شناسهٔ درخواست با محتوای دیگری استفاده شده است')
    if op.get('failed'):
        raise HTTPException(409, 'درخواست قبلی انجام نشد؛ درخواست تازه‌ای ثبت کن')
    if not op.get('complete'):
        await family.finish(op)
    return op['result']


async def recover_for(network_id=None):
    query = {'kind': 'espionage_network', 'complete': False}
    if network_id is not None:
        query['spy_network'] = network_id
    async for op in family.operations.find(query):
        try:
            await family.finish(op)
        except HTTPException:
            continue


def action_id(kind, actor, request):
    return 'spy:' + kind + ':' + str(actor) + ':' + str(request)


async def commit(action, body, result, changes, *, actor, network_id=None, reason='', wallets=None):
    changes.append(mutation('espionage_audit', {'_id': action}, {
        '_id': action, 'network_id': network_id, 'actor_id': actor,
        'action': action.split(':')[1], 'reason': reason, 'result': result,
        'game_at': now(), 'real_at': datetime.now(timezone.utc),
    }, insert=True))
    await family.commit({'_id': action, 'kind': 'espionage_network', 'complete': False,
                         'spy_network': network_id, 'payload_hash': fingerprint(body), 'result': result,
                         'wallets': wallets or [], 'changes': changes})


async def flush_notifications():
    from admin_notifications import notify_admins
    import telegram_bot
    async for item in outbox.find({'complete': False}).limit(40):
        if item['admin']:
            await notify_admins('espionage', '👁️ پروندهٔ جاسوسی', item['text'],
                dedupe_key=item['_id'], audience_roles=('owner', 'full'),
                action='پنل مدیریت ← داوری و ارتباط ← جاسوسی')
        else:
            recipient = await players.find_one({'tg_id': item['recipient']})
            if recipient and recipient.get('created_at') == item.get('character_created_at'):
                key = 'espionage:' + item['_id']
                claimed = await db.messages.update_one({'_id': key}, {'$setOnInsert': {
                    '_id': key, 'from_id': SYSTEM_SENDER_ID, 'from_name': SYSTEM_SENDER_NAME,
                    'to_id': recipient['tg_id'], 'to_name': recipient.get('name', ''),
                    'text': item['text'], 'kind': 'espionage', 'read': False, 'created_at': item['created_at'],
                }}, upsert=True)
                if claimed.upserted_id is not None and not getattr(telegram_bot, 'PERSISTS_NOTICES', False):
                    result = telegram_bot.push(recipient['tg_id'], item['text'])
                    if inspect.isawaitable(result):
                        await result
        await outbox.update_one({'_id': item['_id']}, {'$set': {'complete': True}})


async def context(row):
    from routers.war import owner_of_castle
    p = await players.find_one({'tg_id': row['tg_id']})
    current_epoch, _ = await epoch()
    if not p or p.get('created_at') != row.get('character_created_at') or p.get('is_dead') or p.get('registration_reset'):
        return p, None, 'وضعیت کاراکتر صاحب شبکه تغییر کرده است'
    if row.get('season_epoch') != current_epoch:
        return p, None, 'این شبکه مربوط به فصل قبلی است'
    target = await owner_of_castle(row['target_castle'])
    if (not target or target.get('is_dead') or target.get('registration_reset') or
            target['tg_id'] != row['target_tg_id'] or target.get('created_at') != row.get('target_character_created_at')):
        return p, target, 'مالک یا کاراکتر هدف تغییر کرده است؛ شبکه نیاز به بررسی دارد'
    if target['tg_id'] == p['tg_id']:
        return p, target, 'قلعهٔ هدف اکنون متعلق به صاحب شبکه است'
    return p, target, None


async def owned_network(identity, p):
    row = await networks.find_one({'_id': oid(identity), 'tg_id': p['tg_id'], 'character_created_at': p.get('created_at')})
    if not row:
        raise HTTPException(404, 'شبکه پیدا نشد')
    return row


async def quota(row, player, cfg=None):
    cfg = cfg or await settings(player)
    _, window = await epoch()
    used = await questions.count_documents({'network_id': row['_id'],
        'created_at': {'$gte': window['week_start'], '$lt': window['week_end']}, 'quota_refunded': {'$ne': True}})
    key = str(row['_id']) + ':' + window['week_start'].isoformat()
    adjustment = await db.espionage_quota_adjustments.find_one({'_id': key}) or {}
    maximum = max(0, int(cfg['weekly_questions']) + int(adjustment.get('extra', 0)))
    return {'used': used, 'limit': maximum, 'remaining': max(0, maximum - used),
            'week_number': window['week_number'], 'week_start': window['week_start'].isoformat(),
            'week_end': window['week_end'].isoformat(), 'adjustment_key': key}


async def network_view(row, *, admin=False):
    p, target, blocked = await context(row)
    status = 'suspended' if blocked and row['status'] in OPEN else row['status']
    result = {'id': str(row['_id']), 'target': row['target_castle'], 'origin': row['origin_castle'],
        'status': status, 'stored_status': row['status'], 'blocked_reason': blocked,
        'arrived': now() >= row['arrival_at'], 'arrival_at': row['arrival_at'].isoformat(),
        'created_at': row['created_at'].isoformat(), 'scenario': row['scenario'],
        'gold_cost': row.get('gold_cost', 0), 'note': row.get('player_note', ''),
        'quota': await quota(row, p) if p else None}
    if admin:
        result.update(tg_id=row['tg_id'], player_name=row['player_name'], target_name=(target or {}).get('name', ''),
            score=row.get('score'), deployment_roll=row.get('deployment_roll'), blocked=bool(blocked))
    return result


def question_view(row, *, admin=False):
    result = {'id': str(row['_id']), 'network_id': str(row['network_id']),
        'target': row['target_castle'], 'text': row['text'], 'status': row['status'],
        'created_at': row['created_at'].isoformat(), 'review_note': row.get('review_note', ''),
        'quota_refunded': bool(row.get('quota_refunded')),
        'answer': row.get('answer', '') if row['status'] == 'delivered' else ''}
    if admin:
        result.update(answer=row.get('answer', ''), score=row['score'], roll=row.get('roll'),
            delivery_chance=row.get('delivery_chance'),
            tg_id=row['tg_id'], player_name=row['player_name'], forced=bool(row.get('forced')))
    return result


class Request(BaseModel):
    request_id: UUID


class Deployment(Request):
    target_castle: str = Field(min_length=1, max_length=200)
    scenario: str = Field(min_length=10, max_length=500000)


@router.get('/meta')
async def meta(user=Depends(get_user)):
    p = await person(user['id'])
    current_epoch, window = await epoch()
    cfg = await settings(p)
    occupied = await networks.count_documents({'tg_id': p['tg_id'], 'character_created_at': p.get('created_at'),
        'season_epoch': current_epoch, 'status': {'$in': OPEN}})
    return {**cfg, 'enabled': bool(cfg['enabled'] and feature_enabled('espionage')), 'networks_used': occupied,
        'can_deploy': bool(p.get('castle')), 'week_number': window['week_number'],
        'week_end': window['week_end'].isoformat()}


@router.post('/send')
async def deploy(body: Deployment, user=Depends(get_user)):
    p = await person(user['id'], landed=True)
    raw = {**body.model_dump(mode='json'), 'character_created_at': p.get('created_at')}
    action = action_id('deploy', user['id'], body.request_id)
    replay = await resume(action, raw)
    if replay is not None:
        return replay
    await recover_for()
    cfg = await settings(p)
    if not cfg['enabled'] or not feature_enabled('espionage'):
        raise HTTPException(503, 'جاسوسی فعلاً غیرفعال است')
    scenario = body.scenario.strip()
    await check_text(scenario)
    if len(scenario) < 10:
        raise HTTPException(400, 'روش نفوذ و استقرار را کامل‌تر بنویس')
    from routers.war import owner_of_castle
    target = await owner_of_castle(body.target_castle)
    if not target or target.get('is_dead') or target.get('registration_reset'):
        raise HTTPException(404, 'قلعهٔ هدف صاحب فعالی ندارد')
    if target['tg_id'] == p['tg_id']:
        raise HTTPException(400, 'نمی‌توانی در قلعهٔ خودت شبکهٔ جاسوسی مستقر کنی')
    current_epoch, _ = await epoch()
    occupied = {'tg_id': p['tg_id'], 'character_created_at': p.get('created_at'),
                'season_epoch': current_epoch, 'status': {'$in': OPEN}}
    if await networks.count_documents(occupied) >= cfg['max_networks']:
        raise HTTPException(409, 'ظرفیت شبکه‌های فعال تو تکمیل است')
    if await networks.find_one({**occupied, 'target_castle': body.target_castle}):
        raise HTTPException(409, 'در این قلعه از قبل شبکه یا درخواست استقرار داری')
    identity = ObjectId(fingerprint(action)[:24])
    from datetime import timedelta
    travel = spy_travel_minutes(p['castle'], body.target_castle)
    doc = {'_id': identity, 'tg_id': p['tg_id'], 'player_name': p['name'],
        'character_created_at': p.get('created_at'), 'season_epoch': current_epoch,
        'origin_castle': p['castle'], 'target_castle': body.target_castle,
        'target_tg_id': target['tg_id'], 'target_character_created_at': target.get('created_at'),
        'scenario': scenario, 'gold_cost': cfg['gold_cost'], 'status': 'pending', 'score': None,
        'deployment_roll': None, 'created_at': now(), 'arrival_at': now() + timedelta(minutes=travel)}
    result = {'ok': True, 'id': str(identity), 'travel_minutes': travel}
    changes = [mutation('espionage_networks', {'_id': identity}, doc, insert=True),
               notice(action, p, f"درخواست استقرار جاسوسی در {body.target_castle} ثبت شد."),
               notice(action, p, f"{p['name']} برای استقرار جاسوسی در {body.target_castle} رول فرستاده است.", admin=True)]
    await commit(action, raw, result, changes, actor=p['tg_id'], network_id=identity,
                 wallets=[{'member': member_for(p, 0), 'cost': {'gold': cfg['gold_cost']}, 'debit': True}])
    return result


@router.get('/mine')
async def mine(user=Depends(get_user)):
    p = await person(user['id'])
    current_epoch, _ = await epoch()
    query = {'tg_id': p['tg_id'], 'character_created_at': p.get('created_at'), 'season_epoch': current_epoch}
    result = [await network_view(row) async for row in networks.find({**query, 'status': {'$in': OPEN}}).sort('created_at', -1)]
    result += [await network_view(row) async for row in networks.find({**query, 'status': {'$nin': OPEN}}).sort('created_at', -1).limit(100)]
    return result


@router.get('/questions')
async def my_questions(user=Depends(get_user)):
    p = await person(user['id'])
    current_epoch, _ = await epoch()
    return [question_view(row) async for row in questions.find({'tg_id': p['tg_id'],
        'character_created_at': p.get('created_at'), 'season_epoch': current_epoch}).sort('created_at', -1).limit(200)]


class Question(Request):
    text: str = Field(min_length=3, max_length=10000)


@router.post('/networks/{network_id}/questions')
async def ask(network_id: str, body: Question, user=Depends(get_user)):
    p = await person(user['id'])
    raw = {**body.model_dump(mode='json'), 'network_id': network_id, 'character_created_at': p.get('created_at')}
    action = action_id('ask', p['tg_id'], body.request_id)
    replay = await resume(action, raw)
    if replay is not None:
        return replay
    await recover_for(oid(network_id))
    row = await owned_network(network_id, p)
    _, _, blocked = await context(row)
    cfg = await settings(p)
    if blocked or row['status'] != 'active':
        raise HTTPException(409, blocked or 'این شبکه در حال حاضر آمادهٔ دریافت سؤال نیست')
    if not cfg['enabled'] or not feature_enabled('espionage'):
        raise HTTPException(503, 'ارسال سؤال فعلاً غیرفعال است')
    text = body.text.strip()
    if len(text) < 3:
        raise HTTPException(400, 'متن سؤال را کامل بنویس')
    await check_text(text, 'request_words')
    limit = await quota(row, p, cfg)
    if limit['remaining'] <= 0:
        raise HTTPException(429, 'سهمیهٔ سؤال این شبکه در هفتهٔ جاری تمام شده است')
    identity = ObjectId(fingerprint(action)[:24])
    doc = {'_id': identity, 'network_id': row['_id'], 'tg_id': p['tg_id'], 'player_name': p['name'],
        'character_created_at': p.get('created_at'), 'season_epoch': row['season_epoch'],
        'target_castle': row['target_castle'], 'text': text, 'status': 'pending',
        'score': row['score'], 'roll': None, 'answer': '', 'quota_refunded': False, 'created_at': now()}
    result = {'ok': True, 'id': str(identity)}
    await commit(action, raw, result, [mutation('espionage_questions', {'_id': identity}, doc, insert=True),
        notice(action, p, f"سؤال تازهٔ {p['name']} دربارهٔ {row['target_castle']} در انتظار پاسخ است.", admin=True)],
        actor=p['tg_id'], network_id=row['_id'])
    return result


@router.post('/questions/{question_id}/edit')
async def edit_question(question_id: str, body: Question, user=Depends(get_user)):
    p = await person(user['id'])
    raw = {**body.model_dump(mode='json'), 'question_id': question_id}
    action = action_id('edit-question', p['tg_id'], body.request_id)
    replay = await resume(action, raw)
    if replay is not None:
        return replay
    q = await questions.find_one({'_id': oid(question_id), 'tg_id': p['tg_id'], 'character_created_at': p.get('created_at')})
    if q:
        await recover_for(q['network_id'])
        q = await questions.find_one({'_id': q['_id']})
    if not q or q['status'] != 'returned':
        raise HTTPException(409, 'فقط سؤال برگشت‌خورده را می‌توانی اصلاح کنی')
    row = await owned_network(str(q['network_id']), p)
    _, _, blocked = await context(row)
    if blocked or row['status'] != 'active':
        raise HTTPException(409, blocked or 'شبکه آماده نیست')
    if len(body.text.strip()) < 3:
        raise HTTPException(400, 'متن سؤال را کامل بنویس')
    await check_text(body.text.strip(), 'request_words')
    result = {'ok': True, 'id': question_id}
    await commit(action, raw, result, [mutation('espionage_questions', {'_id': q['_id']},
        {'text': body.text.strip(), 'status': 'pending', 'edited_at': now()}),
        notice(action, p, f"سؤال اصلاح‌شدهٔ {p['name']} در پروندهٔ جاسوسی منتظر بررسی است.", admin=True)],
        actor=p['tg_id'], network_id=q['network_id'])
    return result


async def close_changes(row, status, note):
    changes = [mutation('espionage_networks', {'_id': row['_id']}, {'status': status, 'player_note': note, 'closed_at': now()})]
    async for question in questions.find({'network_id': row['_id'], 'status': {'$in': QUESTION_OPEN}}):
        changes.append(mutation('espionage_questions', {'_id': question['_id']},
            {'status': 'cancelled', 'review_note': 'شبکه بسته شد؛ این سؤال دیگر قابل پاسخ‌گویی نیست'}))
    return changes


@router.post('/networks/{network_id}/recall')
async def recall(network_id: str, body: Request, user=Depends(get_user)):
    p = await person(user['id'])
    raw = {**body.model_dump(mode='json'), 'network_id': network_id}
    action = action_id('recall', p['tg_id'], body.request_id)
    replay = await resume(action, raw)
    if replay is not None:
        return replay
    await recover_for(oid(network_id))
    row = await owned_network(network_id, p)
    if row['status'] not in ('pending', 'active', 'suspended'):
        raise HTTPException(409, 'این شبکه قابل جمع‌کردن نیست؛ پروندهٔ خطر باید ابتدا بررسی شود')
    result = {'ok': True}
    await commit(action, raw, result, await close_changes(row, 'closed', 'شبکه به درخواست صاحب آن جمع شد'),
                 actor=p['tg_id'], network_id=row['_id'])
    return result


class Score(Request):
    score: StrictInt = Field(ge=0, le=100)
    reason: str = Field(default='داوری رول استقرار', min_length=3, max_length=1000)


@router.post('/admin/networks/{network_id}/score')
async def score_network(network_id: str, body: Score, admin=Depends(full_admin)):
    raw = {**body.model_dump(mode='json'), 'network_id': network_id}
    action = action_id('score', admin['id'], body.request_id)
    replay = await resume(action, raw)
    if replay is not None:
        return replay
    await recover_for(oid(network_id))
    row = await networks.find_one({'_id': oid(network_id)})
    if not row or row['status'] != 'pending':
        raise HTTPException(409, 'این استقرار منتظر داوری نیست')
    p, target, blocked = await context(row)
    if blocked:
        raise HTTPException(409, blocked)
    if now() < row['arrival_at']:
        raise HTTPException(409, 'جاسوسی هنوز به مقصد نرسیده است')
    roll = draw()
    success = roll <= body.score
    result = {'ok': True, 'success': success, 'score': body.score, 'roll': roll}
    changes = [mutation('espionage_networks', {'_id': row['_id']}, {
        'score': body.score, 'deployment_score': body.score, 'deployment_roll': roll, 'status': 'active' if success else 'failed',
        'scored_at': now(), 'scored_by': admin['id']}),
        notice(action, p, f"استقرار جاسوسی در {row['target_castle']} {'موفق بود؛ شبکه آمادهٔ دریافت سؤال است' if success else 'ناموفق بود'}." )]
    if not success:
        changes.append(notice(action + ':target', target, f"تلاش برای نفوذ جاسوسی در {row['target_castle']} شناسایی شد."))
    await commit(action, raw, result, changes, actor=admin['id'], network_id=row['_id'], reason=body.reason)
    return result


class Answer(Request):
    action: str = 'answer'
    text: str = Field(default='', max_length=500000)
    reason: str = Field(default='', max_length=1000)
    chance: StrictInt | None = Field(default=None, ge=0, le=100)


@router.post('/admin/questions/{question_id}')
async def answer_question(question_id: str, body: Answer, admin=Depends(full_admin)):
    if body.action not in ('answer', 'reject', 'return', 'force_deliver'):
        raise HTTPException(400, 'اقدام معتبر نیست')
    raw = {**body.model_dump(mode='json'), 'question_id': question_id}
    action = action_id('answer', admin['id'], body.request_id)
    replay = await resume(action, raw)
    if replay is not None:
        return replay
    q = await questions.find_one({'_id': oid(question_id)})
    if not q:
        raise HTTPException(404, 'سؤال پیدا نشد')
    await recover_for(q['network_id'])
    q = await questions.find_one({'_id': q['_id']})
    row = await networks.find_one({'_id': q['network_id']})
    if not row:
        raise HTTPException(404, 'شبکه پیدا نشد')
    p, _, blocked = await context(row)
    if blocked:
        raise HTTPException(409, blocked)
    forced = body.action == 'force_deliver'
    if forced:
        if q['status'] != 'delivery_failed' or row['status'] not in ('active', 'risk_review') or len(body.reason.strip()) < 3:
            raise HTTPException(409, 'ارسال استثنایی فقط برای پاسخ نرسیده و با ثبت دلیل ممکن است')
    elif q['status'] not in QUESTION_OPEN or row['status'] != 'active':
        raise HTTPException(409, 'این سؤال یا شبکه آمادهٔ پاسخ نیست')
    fields = {'reviewed_at': now(), 'reviewed_by': admin['id']}
    changes = []
    if body.action in ('reject', 'return'):
        if len(body.reason.strip()) < 3:
            raise HTTPException(400, 'دلیل را بنویس')
        fields.update(status='rejected' if body.action == 'reject' else 'returned',
                      review_note=body.reason.strip(), quota_refunded=body.action == 'reject')
        changes.append(notice(action, p, f"سؤال جاسوسی دربارهٔ {row['target_castle']} {'رد شد و سهمیهٔ آن برگشت' if body.action == 'reject' else 'برای اصلاح برگشت'}."))
    else:
        text = body.text.strip() or (q.get('answer', '') if forced else '')
        if not text:
            raise HTTPException(400, 'متن پاسخ را بنویس')
        await check_text(text, 'scenario_words')
        if not forced and body.chance is None:
            raise HTTPException(400, 'شانس رسیدن همین پاسخ را از ۰ تا ۱۰۰ وارد کن')
        chance = q.get('delivery_chance') if forced else body.chance
        roll = q.get('roll') if forced else draw()
        success = forced or roll <= chance
        fields.update(answer=text, roll=roll, delivery_chance=chance, status='delivered' if success else 'delivery_failed', forced=forced)
        if forced:
            fields['override_reason'] = body.reason.strip()
        if success:
            changes.append(notice(action, p, f"پاسخ سؤال جاسوسی دربارهٔ {row['target_castle']} رسید؛ در صفحهٔ جاسوسی بخوان."))
        else:
            changes.append(mutation('espionage_networks', {'_id': row['_id']}, {'status': 'risk_review'}))
            changes.append(notice(action, p, f"گزارش جاسوسی دربارهٔ {row['target_castle']} به دستت نرسید؛ وضعیت ارتباط در حال بررسی است."))
            changes.append(notice(action, p, f"پیام شبکهٔ {p['name']} در {row['target_castle']} نرسید. دربارهٔ ادامهٔ فعالیت یا دستگیری تصمیم بگیرید.", admin=True))
    changes.append(mutation('espionage_questions', {'_id': q['_id']}, fields))
    result = {'ok': True, 'status': fields['status'], 'roll': fields.get('roll'), 'score': fields.get('delivery_chance')}
    await commit(action, raw, result, changes, actor=admin['id'], network_id=row['_id'], reason=body.reason)
    return result


class NetworkAction(Request):
    action: str
    reason: str = Field(min_length=3, max_length=1000)
    score: StrictInt | None = Field(default=None, ge=0, le=100)
    delta: StrictInt = Field(default=0, ge=-1000, le=1000)
    disclose_sender: StrictBool = False


@router.post('/admin/networks/{network_id}')
async def manage_network(network_id: str, body: NetworkAction, admin=Depends(full_admin)):
    if len(body.reason.strip()) < 3:
        raise HTTPException(400, 'دلیل اقدام را کامل بنویس')
    raw = {**body.model_dump(mode='json'), 'network_id': network_id}
    action = action_id('manage', admin['id'], body.request_id)
    replay = await resume(action, raw)
    if replay is not None:
        return replay
    await recover_for(oid(network_id))
    row = await networks.find_one({'_id': oid(network_id)})
    if not row or row['status'] not in OPEN:
        raise HTTPException(409, 'شبکهٔ باز پیدا نشد')
    p, target, blocked = await context(row)
    changes = []
    if body.action in ('close', 'capture'):
        status = 'captured' if body.action == 'capture' else 'closed'
        changes += await close_changes(row, status, body.reason.strip())
        if p:
            changes.append(notice(action, p, f"شبکهٔ جاسوسی در {row['target_castle']} {'دستگیر شد' if status == 'captured' else 'بسته شد'}."))
        if status == 'captured' and target:
            detail = f"شبکهٔ جاسوسی در {row['target_castle']} شناسایی و دستگیر شد."
            if body.disclose_sender:
                detail += f" سفارش‌دهنده: {row['player_name']}."
            changes.append(notice(action + ':target', target, detail))
    elif body.action == 'suspend':
        changes.append(mutation('espionage_networks', {'_id': row['_id']}, {'status': 'suspended', 'player_note': body.reason.strip()}))
    elif body.action == 'resume':
        if not p or p.get('created_at') != row.get('character_created_at') or p.get('is_dead') or p.get('registration_reset'):
            raise HTTPException(409, 'کاراکتر صاحب شبکه تغییر کرده است')
        current_epoch, _ = await epoch()
        if row.get('season_epoch') != current_epoch or not target or target['tg_id'] == p['tg_id'] or target.get('is_dead') or target.get('registration_reset'):
            raise HTTPException(409, 'هدف یا فصل این شبکه معتبر نیست')
        changes.append(mutation('espionage_networks', {'_id': row['_id']}, {
            'status': 'pending' if row.get('score') is None else 'active', 'player_note': '', 'target_tg_id': target['tg_id'],
            'target_character_created_at': target.get('created_at')}))
    elif body.action == 'rescore':
        if body.score is None or row.get('score') is None:
            raise HTTPException(400, 'امتیاز معتبر شبکه را وارد کن')
        changes.append(mutation('espionage_networks', {'_id': row['_id']}, {'score': body.score}))
    elif body.action in ('quota_delta', 'quota_reset'):
        if not p:
            raise HTTPException(404, 'صاحب شبکه پیدا نشد')
        limit = await quota(row, p)
        old = await db.espionage_quota_adjustments.find_one({'_id': limit['adjustment_key']}) or {}
        extra = limit['used'] if body.action == 'quota_reset' else int(old.get('extra', 0)) + body.delta
        changes.append(mutation('espionage_quota_adjustments', {'_id': limit['adjustment_key']},
            {'extra': extra, 'network_id': row['_id'], 'updated_by': admin['id'], 'updated_at': now()}, insert=False))
        changes[-1]['upsert'] = True
    else:
        raise HTTPException(400, 'اقدام معتبر نیست')
    result = {'ok': True}
    await commit(action, raw, result, changes, actor=admin['id'], network_id=row['_id'], reason=body.reason)
    return result


class Rules(Request):
    enabled: StrictBool
    gold_cost: StrictInt = Field(ge=0, le=1000000000)
    weekly_questions: StrictInt = Field(ge=0, le=1000)
    max_networks: StrictInt = Field(ge=0, le=100)
    reason: str = Field(min_length=3, max_length=1000)


@router.get('/admin/settings')
async def admin_settings(admin=Depends(full_admin)):
    return await settings()


@router.post('/admin/settings')
async def save_settings(body: Rules, admin=Depends(full_admin)):
    if len(body.reason.strip()) < 3:
        raise HTTPException(400, 'دلیل تغییر را کامل بنویس')
    raw = body.model_dump(mode='json')
    action = action_id('rules', admin['id'], body.request_id)
    replay = await resume(action, raw)
    if replay is not None:
        return replay
    await recover_for()
    values = body.model_dump(exclude={'request_id', 'reason'})
    change = mutation('game_settings', {'_id': 'espionage_networks'}, values)
    change['upsert'] = True
    await commit(action, raw, values, [change], actor=admin['id'], reason=body.reason)
    return values


class PlayerLimits(Request):
    weekly_questions: StrictInt | None = Field(default=None, ge=0, le=1000)
    max_networks: StrictInt | None = Field(default=None, ge=0, le=100)
    enabled: StrictBool | None = None
    reason: str = Field(min_length=3, max_length=1000)


@router.post('/admin/players/{uid}/limits')
async def save_player_limits(uid: int, body: PlayerLimits, admin=Depends(full_admin)):
    if len(body.reason.strip()) < 3:
        raise HTTPException(400, 'دلیل تغییر را کامل بنویس')
    p = await person(uid)
    raw = {**body.model_dump(mode='json'), 'uid': uid, 'character_created_at': p.get('created_at')}
    action = action_id('player-limits', admin['id'], body.request_id)
    replay = await resume(action, raw)
    if replay is not None:
        return replay
    await recover_for()
    fields = {**body.model_dump(exclude={'request_id', 'reason'}), 'tg_id': uid,
              'character_created_at': p.get('created_at'), 'updated_by': admin['id'], 'updated_at': now()}
    change = mutation('espionage_player_limits', {'tg_id': uid, 'character_created_at': p.get('created_at')}, fields)
    change['upsert'] = True
    result = {'ok': True}
    await commit(action, raw, result, [change], actor=admin['id'], reason=body.reason)
    return result


@router.get('/admin/players/{uid}/limits')
async def player_limits(uid: int, admin=Depends(full_admin)):
    p = await person(uid)
    override = await db.espionage_player_limits.find_one({'tg_id': uid, 'character_created_at': p.get('created_at')}) or {}
    return {'player_name': p['name'], 'effective': await settings(p),
            'overrides': {key: override.get(key) for key in ('weekly_questions', 'max_networks', 'enabled')}}


@router.get('/admin/networks')
async def admin_networks(q: str = Query(default='', max_length=100), status: str = '',
                         offset: int = Query(default=0, ge=0), admin=Depends(full_admin)):
    query = {}
    if q.strip():
        pattern = {'$regex': re.escape(q.strip()), '$options': 'i'}
        query['$or'] = [{'player_name': pattern}, {'target_castle': pattern}]
        if q.isdigit():
            query['$or'].append({'tg_id': int(q)})
    if status:
        if status not in (*OPEN, 'closed', 'captured', 'failed'):
            raise HTTPException(400, 'وضعیت معتبر نیست')
        query['status'] = status
    return {'total': await networks.count_documents(query), 'rows': [await network_view(row, admin=True)
        async for row in networks.find(query).sort('created_at', -1).skip(offset).limit(50)]}


@router.get('/admin/questions')
async def admin_questions(q: str = Query(default='', max_length=100), status: str = '',
                          offset: int = Query(default=0, ge=0), admin=Depends(full_admin)):
    query = {}
    if q.strip():
        pattern = {'$regex': re.escape(q.strip()), '$options': 'i'}
        query['$or'] = [{'player_name': pattern}, {'target_castle': pattern}, {'text': pattern}]
    if status:
        if status not in (*QUESTION_OPEN, 'rejected', 'delivered', 'delivery_failed', 'cancelled'):
            raise HTTPException(400, 'وضعیت معتبر نیست')
        query['status'] = status
    rows = []
    async for row in questions.find(query).sort('created_at', -1).skip(offset).limit(50):
        view = question_view(row, admin=True)
        network = await networks.find_one({'_id': row['network_id']}) or {}
        view.update(deployment_scenario=network.get('scenario', ''),
                    deployment_score=network.get('deployment_score', network.get('score')),
                    deployment_roll=network.get('deployment_roll'))
        rows.append(view)
    return {'total': await questions.count_documents(query), 'rows': rows}


@router.get('/admin/networks/{network_id}/audit')
async def network_audit(network_id: str, admin=Depends(full_admin)):
    return [{**{k: v for k, v in row.items() if k not in ('_id', 'network_id')}, 'id': row['_id']}
        async for row in audits.find({'network_id': oid(network_id)}).sort('real_at', -1).limit(100)]


@router.get('/admin/legacy')
async def legacy_missions(admin=Depends(full_admin)):
    return [{'id': str(row['_id']), 'player_name': row.get('player_name', ''), 'tg_id': row['tg_id'],
        'target': row.get('target_castle', ''), 'scenario': row.get('scenario', ''),
        'resolved': row.get('resolved', False), 'migrated': bool(row.get('network_id'))}
        async for row in db.spy_missions.find({}).sort('created_at', -1).limit(100)]


@router.post('/admin/legacy/{mission_id}/convert')
async def convert_legacy(mission_id: str, body: Request, admin=Depends(full_admin)):
    raw = {**body.model_dump(mode='json'), 'mission_id': mission_id}
    action = action_id('convert', admin['id'], body.request_id)
    replay = await resume(action, raw)
    if replay is not None:
        return replay
    await recover_for()
    old = await db.spy_missions.find_one({'_id': oid(mission_id)})
    if not old or old.get('network_id') or old.get('resolved'):
        raise HTTPException(409, 'فقط پروندهٔ قدیمیِ بررسی‌نشده قابل تبدیل است')
    p = await person(old['tg_id'])
    if not old.get('created_at') or old['created_at'] < p['created_at']:
        raise HTTPException(409, 'این مأموریت مربوط به کاراکتر فعلی نیست')
    from routers.war import owner_of_castle
    target = await owner_of_castle(old['target_castle'])
    if not target or target['tg_id'] == p['tg_id']:
        raise HTTPException(409, 'هدف مأموریت معتبر نیست')
    current_epoch, _ = await epoch()
    base_query = {'tg_id': p['tg_id'], 'character_created_at': p['created_at'], 'season_epoch': current_epoch, 'status': {'$in': OPEN}}
    cfg = await settings(p)
    if await networks.count_documents(base_query) >= cfg['max_networks'] or await networks.find_one({**base_query, 'target_castle': old['target_castle']}):
        raise HTTPException(409, 'ظرفیت یا محل شبکه تکراری است')
    identity = ObjectId(fingerprint(action)[:24])
    doc = {'_id': identity, 'tg_id': p['tg_id'], 'player_name': p['name'], 'character_created_at': p['created_at'],
        'season_epoch': current_epoch, 'origin_castle': old.get('origin_castle', ''), 'target_castle': old['target_castle'],
        'target_tg_id': target['tg_id'], 'target_character_created_at': target.get('created_at'),
        'scenario': old.get('scenario', ''), 'gold_cost': old.get('gold_cost', 0), 'status': 'pending',
        'score': None, 'deployment_roll': None, 'created_at': old['created_at'],
        'arrival_at': old.get('arrival_at') or now(), 'legacy_mission': old['_id']}
    result = {'ok': True, 'id': str(identity)}
    await commit(action, raw, result, [mutation('espionage_networks', {'_id': identity}, doc, insert=True),
        mutation('spy_missions', {'_id': old['_id']}, {'network_id': identity, 'resolved': True,
            'resolved_at': now(), 'resolution': 'converted_to_network'})], actor=admin['id'], network_id=identity,
        reason='تبدیل پروندهٔ قدیمی بدون دریافت هزینهٔ تازه')
    return result


async def ensure_indexes():
    await networks.create_index([('tg_id', 1), ('character_created_at', 1), ('season_epoch', 1), ('status', 1)])
    await questions.create_index([('network_id', 1), ('created_at', -1)])
    await questions.create_index([('status', 1), ('created_at', -1)])
    await audits.create_index([('network_id', 1), ('real_at', -1)])
    await outbox.create_index('complete')
    await family.operations.create_index([('kind', 1), ('complete', 1), ('spy_network', 1)])
    await db.espionage_player_limits.create_index([('tg_id', 1), ('character_created_at', 1)], unique=True)
