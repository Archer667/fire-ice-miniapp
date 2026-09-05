"""Project escrow, share ownership and restart-safe periodic settlements.

Mongo runs standalone. A persisted intent plus an atomic per-character wallet
receipt makes replay safe without depending on multi-document transactions.
The deployed single-worker API and its watchers share game_state_lock so legacy
read/modify/write resource handlers cannot overwrite a project wallet change.
"""
import asyncio
import hashlib
import logging
from datetime import timedelta
from decimal import Decimal
from zoneinfo import ZoneInfo
from fastapi import HTTPException
from db import db, players, messages, admin_roles
from game import now, apply_production, production_fields, can_afford, pay
from config import ADMIN_IDS, OWNER_ID, SYSTEM_SENDER_ID, SYSTEM_SENDER_NAME, MINI_APP_URL
import telegram_bot

projects = db.projects
game_state_lock = asyncio.Lock()
project_lock = asyncio.Lock()
logger = logging.getLogger(__name__)
RESOURCES = {'gold': 'طلا', 'wood': 'چوب', 'stone': 'سنگ', 'iron': 'آهن', 'food': 'غذا', 'wine': 'شراب'}
TERMS = ('آوردهٔ طراح هنگام ثبت درخواست رزرو می‌شود؛ در صورت رد درخواست کامل بازمی‌گردد. '
         'اگر در مهلت مقرر تمام سهام فروش نرود، آوردهٔ سرمایه‌گذاران کامل بازمی‌گردد و طراح فقط نصف آوردهٔ خود را پس می‌گیرد. '
         'با اعلام شکست توسط ادمین یا مرگ طراح، سرمایه بازنمی‌گردد و پرداخت‌های آینده متوقف می‌شوند؛ دریافتی‌های قبلی محفوظ‌اند. '
         'اصل سرمایه در پایان پروژه جداگانه بازپرداخت نمی‌شود. طراح نمی‌تواند سهام پروژهٔ خودش را بخرد. '
         'خروج یا فروش سهام پیش از پایان پروژه ممکن نیست. بازده اعلام‌شده مشروط به ادامهٔ موفق پروژه است.')
OPEN_STATES = ('pending', 'scheduled', 'funding', 'active')


def scaled(amounts, shares, total=1):
    return {k: float((Decimal(str(v)) * shares / total).quantize(Decimal('0.00000001'))) for k, v in amounts.items() if v}


def basket(amounts):
    return ' + '.join(f'{v:,.8f}'.rstrip('0').rstrip('.') + ' ' + RESOURCES[k] for k, v in amounts.items() if v) or '۰'


def receipt_key(key):
    return hashlib.sha256(key.encode()).hexdigest()


async def wallet_once(member, amounts, key, debit=False):
    """One Mongo update commits both resource changes and the replay receipt."""
    field = 'project_receipts.' + receipt_key(key)
    p = await players.find_one({'tg_id': member['tg_id']})
    if not p or p.get('created_at') != member['character_created_at']:
        if debit:
            raise HTTPException(409, 'شخصیت سرمایه‌گذار تغییر کرده است')
        return  # Never pay an old character's proceeds to a newly registered character.
    if p.get('project_receipts', {}).get(receipt_key(key)):
        return
    if debit and (p.get('is_dead') or not p.get('castle')):
        raise HTTPException(403, 'فقط بازیکن زنده و خاندان‌دار می‌تواند سرمایه‌گذاری کند')
    p = apply_production(p)
    await players.update_one({'tg_id': p['tg_id']}, {'$set': production_fields(p)})
    if debit:
        if not can_afford(p['resources'], amounts):
            raise HTTPException(400, 'طلا یا منابع کافی برای این سرمایه‌گذاری نداری')
        resources = dict(p['resources'])
        pay(resources, amounts)
        change = {'$set': {field: True, **{f'resources.{k}': resources[k] for k in amounts}}}
    else:
        # Escrow refunds and promised payouts are not truncated by warehouse caps.
        change = {'$set': {field: True}, '$inc': {f'resources.{k}': v for k, v in amounts.items()}}
        if not change['$inc']:
            change.pop('$inc')
    await players.update_one({'tg_id': p['tg_id'], 'created_at': member['character_created_at'], field: {'$ne': True}}, change)


def member_for(p, shares):
    return {'tg_id': p['tg_id'], 'name': p['name'], 'character_created_at': p['created_at'], 'shares': shares}


async def queue_notice(project, event, recipients, text):
    field = 'notices.' + event
    await projects.update_one({'_id': project['_id'], field: {'$exists': False}}, {'$set': {
        field: {'text': text, 'recipients': list(set(recipients)), 'sent': []}, 'notices_pending': True,
    }})


async def flush_notices():
    async for project in projects.find({'notices_pending': True}):
        for event, notice in project.get('notices', {}).items():
            for tg_id in notice['recipients']:
                if tg_id in notice.get('sent', []):
                    continue
                message_id = f"project:{project['_id']}:{event}:{tg_id}"
                doc = {'from_id': SYSTEM_SENDER_ID, 'from_name': SYSTEM_SENDER_NAME,
                       'to_id': tg_id, 'to_name': '', 'text': notice['text'], 'kind': 'project',
                       'read': False, 'created_at': now()}
                await messages.update_one({'_id': message_id}, {'$setOnInsert': doc}, upsert=True)
                markup = {'inline_keyboard': [[{'text': '🏰 ورود به بازی و مشاهدهٔ پروژه', 'web_app': {'url': MINI_APP_URL}}]]} if MINI_APP_URL else None
                telegram_bot.push(tg_id, notice['text'], reply_markup=markup)
                await projects.update_one({'_id': project['_id']}, {'$addToSet': {f'notices.{event}.sent': tg_id}})
        await projects.update_one({'_id': project['_id']}, {'$set': {'notices_pending': False}})


async def finish_purchase(project):
    intent = project.get('purchase_intent')
    if not intent:
        return project
    try:
        await wallet_once(intent['member'], intent['cost'], f"{project['_id']}:buy:{intent['key']}", debit=True)
    except HTTPException:
        await projects.update_one({'_id': project['_id']}, {'$unset': {'purchase_intent': ''}})
        raise
    key = str(intent['member']['tg_id'])
    existing = project['members'].get(key)
    member = {**intent['member'], 'shares': (existing or {}).get('shares', 0) + intent['member']['shares']}
    update = {'$set': {f'members.{key}': member}, '$inc': {'sold_shares': intent['member']['shares']},
              '$addToSet': {'purchase_keys': intent['key']}, '$unset': {'purchase_intent': ''}}
    if project['sold_shares'] + intent['member']['shares'] == project['total_shares']:
        update['$set'].update({'status': 'active', 'started_at': intent['accepted_at'],
                              'next_payout_at': intent['accepted_at'] + timedelta(hours=project['period_hours'])})
    await projects.update_one({'_id': project['_id'], 'purchase_intent.key': intent['key']}, update)
    return await projects.find_one({'_id': project['_id']})


async def finish_settlement(project):
    intent = project.get('settlement')
    if not intent:
        return project
    for key, member in project['members'].items():
        await wallet_once(member, intent['amounts'].get(key, {}), f"{project['_id']}:{intent['key']}:{key}")
    if intent.get('notice'):
        await queue_notice(project, intent['key'], [m['tg_id'] for m in project['members'].values()], intent['notice'])
    await projects.update_one({'_id': project['_id'], 'settlement.key': intent['key']}, {
        '$set': intent['after'], '$unset': {'settlement': ''},
    })
    return await projects.find_one({'_id': project['_id']})


async def settle(project, key, amounts, after, notice=None):
    await projects.update_one({'_id': project['_id'], 'settlement': {'$exists': False}}, {'$set': {
        'settlement': {'key': key, 'amounts': amounts, 'after': after, 'notice': notice},
    }})
    return await finish_settlement(await projects.find_one({'_id': project['_id']}))


async def recover(project):
    if project['status'] == 'reserving':
        owner = project['members'][str(project['owner_id'])]
        try:
            await wallet_once(owner, scaled(project['share_cost'], owner['shares']), project['_id'] + ':reserve', debit=True)
        except HTTPException as exc:
            await projects.update_one({'_id': project['_id']}, {'$set': {'status': 'invalid', 'reason': exc.detail}})
            raise
        await projects.update_one({'_id': project['_id'], 'status': 'reserving'}, {'$set': {'status': 'pending'}})
        project = await projects.find_one({'_id': project['_id']})
    project = await finish_purchase(project)
    return await finish_settlement(project)


async def fail_project(project, reason, actor=None):
    project = await recover(project)
    if project['status'] not in OPEN_STATES:
        return project
    await projects.update_one({'_id': project['_id']}, {'$set': {
        'status': 'failed', 'reason': reason, 'ended_at': now(), 'failed_by': actor,
    }})
    await queue_notice(project, 'failed', [m['tg_id'] for m in project['members'].values()],
        f"⚔️ پروژهٔ «{project['name']}» شکست خورد.\nدلیل: {reason}\nسرمایه بازنمی‌گردد و پرداخت‌های بعدی متوقف شدند؛ دریافتی‌های قبلی محفوظ‌اند.")
    return await projects.find_one({'_id': project['_id']})


async def fail_owner_projects(tg_id):
    async with project_lock:
        async for project in projects.find({'owner_id': tg_id, 'status': {'$in': [*OPEN_STATES, 'reserving']}}):
            await fail_project(project, 'مرگ طراح پروژه')


async def tick_project(project):
    project = await recover(project)
    if project['status'] not in OPEN_STATES:
        return project
    owner = await players.find_one({'tg_id': project['owner_id']})
    if not owner or owner.get('is_dead') or owner.get('created_at') != project['members'][str(project['owner_id'])]['character_created_at']:
        return await fail_project(project, 'مرگ یا پایان شخصیت طراح پروژه')
    current = now()
    if project['status'] == 'scheduled' and current >= project['publish_at']:
        state = {'status': 'funding'}
        if project['kind'] == 'personal':
            state = {'status': 'active', 'started_at': project['publish_at'],
                     'next_payout_at': project['publish_at'] + timedelta(hours=project['period_hours'])}
        await projects.update_one({'_id': project['_id']}, {'$set': state})
        project.update(state)
    if project['status'] == 'funding' and current >= project['funding_deadline']:
        amounts = {key: scaled(project['share_cost'], m['shares'], 2 if m['tg_id'] == project['owner_id'] else 1)
                   for key, m in project['members'].items()}
        return await settle(project, 'funding_refund', amounts, {'status': 'unfunded', 'ended_at': current,
            'reason': 'تمام سهام در مهلت مقرر فروش نرفت'},
            f"⏳ جذب سرمایهٔ «{project['name']}» تکمیل نشد. آوردهٔ سرمایه‌گذاران کامل و نصف آوردهٔ طراح بازگردانده شد.")
    # Catch up missed periods after downtime. Each period has its own durable receipt.
    while project['status'] == 'active' and current >= project['next_payout_at']:
        period = project['paid_periods'] + 1
        amounts = {key: scaled(project['period_return'], m['shares'], project['total_shares']) for key, m in project['members'].items()}
        after = {'paid_periods': period, 'next_payout_at': project['next_payout_at'] + timedelta(hours=project['period_hours'])}
        if period == project['period_count']:
            after.update({'status': 'completed', 'ended_at': project['next_payout_at']})
        project = await settle(project, f'payout_{period}', amounts, after,
            f"💰 پرداخت دورهٔ {period} از {project['period_count']} پروژهٔ «{project['name']}» انجام شد." +
            ('\nپروژه با موفقیت پایان یافت؛ اصل سرمایه جداگانه بازپرداخت نمی‌شود.' if after.get('status') == 'completed' else ''))
    return project


async def tick_projects():
    async with project_lock:
        async for project in projects.find({'$or': [{'status': {'$in': [*OPEN_STATES, 'reserving']}},
                                                  {'settlement': {'$exists': True}}, {'purchase_intent': {'$exists': True}}]}):
            try:
                await tick_project(project)
            except Exception:
                logger.exception('project tick failed: %s', project['_id'])
        await flush_notices()


def public_project(project, user_id):
    out = {k: v for k, v in project.items() if k not in ('_id', 'notices', 'notices_pending', 'purchase_intent', 'settlement', 'purchase_keys', 'members', 'request_fingerprint')}
    out['id'] = project['_id']
    member = project['members'].get(str(user_id), {})
    out['my_shares'] = member.get('shares', 0)
    out['is_owner'] = project['owner_id'] == user_id
    out['share_return'] = scaled(project['period_return'], 1, project['total_shares'])
    out['my_return'] = scaled(project['period_return'], out['my_shares'], project['total_shares'])
    out['my_total_return'] = scaled(out['my_return'], project['period_count'])
    out['my_investment'] = scaled(project['share_cost'], out['my_shares'])
    out['my_received'] = scaled(out['my_return'], project['paid_periods'])
    out['my_net'] = {k: out['my_total_return'].get(k, 0) - out['my_investment'].get(k, 0) for k in RESOURCES}
    out['remaining_shares'] = project['total_shares'] - project['sold_shares']
    out['can_buy'] = project['status'] == 'funding' and not out['is_owner']
    return out


def announcement(project):
    stamp = project['publish_at'].replace(tzinfo=ZoneInfo('UTC')).astimezone(ZoneInfo('Asia/Tehran')).strftime('%Y/%m/%d — %H:%M')
    share_return = scaled(project['period_return'], 1, project['total_shares'])
    total = scaled(share_return, project['period_count'])
    net = {k: total.get(k, 0) - project['share_cost'].get(k, 0) for k in RESOURCES}
    return (f"📜 فرمان تأسیس پروژهٔ {'مشترک' if project['kind'] == 'shared' else 'شخصی'}\n🏰 {project['name']}\n\n"
            f"👤 طراح: {project['owner_name']}\n🎯 چشم‌انداز: {project['goal']}\n🛠 شیوهٔ اجرا: {project['description']}\n\n"
            f"💰 بودجه: {basket(project['budget'])}\n📊 کل سهام: {project['total_shares']} — سهم طراح: {project['owner_shares']}\n"
            f"سهام قابل خرید: {project['total_shares'] - project['owner_shares']}\nبهای هر سهم: {basket(project['share_cost'])}\n"
            f"سقف خرید هر بازیکن: {project.get('max_shares_per_player') or 'بدون محدودیت'}\n\n"
            f"📈 هر سهم، هر {project['period_hours']} ساعت: {basket(share_return)}\nتعداد پرداخت‌ها: {project['period_count']}\n"
            f"کل دریافتی هر سهم: {basket(total)}\nخالص هر سهم در صورت موفقیت کامل: {basket(net)}\n\n"
            f"🗓 عرضه: {stamp} به وقت تهران (میلادی)\n⏳ مهلت جذب سرمایه: {project['funding_hours']} ساعت\n"
            f"اولین پرداخت: {project['period_hours']} ساعت پس از شروع اجرای پروژه\n\n"
            f"⚖️ شرایط سرمایه‌گذاری\n{project['notification_terms']}\n\n🏰 تجارت ← پروژه‌های مشترک")
