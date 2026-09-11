"""Persist battle roster notices before sending; retry transient Telegram failures."""
import asyncio
from datetime import datetime, timedelta
import httpx
from db import db
from config import BOT_TOKEN, DEV_MODE, SYSTEM_SENDER_NAME, SYSTEM_SENDER_ID
from control_settings import notification_route

outbox = db.battle_notice_outbox

async def enqueue(event, recipients, text):
    route = notification_route('battle')
    for player in recipients:
        key = f"{event}:{player['tg_id']}"
        await outbox.update_one({'_id': key}, {'$setOnInsert': {
            'to_id': player['tg_id'], 'to_name': player['name'], 'text': text,
            'raven_done': not route.get('raven', True), 'bot_done': not route.get('bot', True),
            'complete': False, 'attempts': 0, 'next_attempt': datetime.utcnow(),
            'created_at': datetime.utcnow(),
        }}, upsert=True)

async def flush():
    from game import now
    from player_labels import normalize_player_names
    pending = await outbox.find({'complete': False, 'next_attempt': {'$lte': datetime.utcnow()}}).limit(20).to_list(None)
    for item in pending:
        changes = {}
        try:
            if not item['raven_done']:
                await db.messages.update_one({'battle_notice_id': item['_id']}, {'$setOnInsert': {
                    'from_id': SYSTEM_SENDER_ID, 'from_name': SYSTEM_SENDER_NAME,
                    'to_id': item['to_id'], 'to_name': item['to_name'],
                    'text': await normalize_player_names(item['text']), 'kind': 'battle',
                    'read': False, 'created_at': now(),
                }}, upsert=True)
                changes['raven_done'] = True
                await outbox.update_one({'_id': item['_id']}, {'$set': changes})
            if not item['bot_done'] and BOT_TOKEN and not DEV_MODE:
                chunks = [item['text'][i:i+3000] for i in range(0,len(item['text']),3000)] or ['']
                async with httpx.AsyncClient(timeout=10) as client:
                    for part in range(item.get('bot_part', 0), len(chunks)):
                        response = await client.post(f'https://api.telegram.org/bot{BOT_TOKEN}/sendMessage',
                            json={'chat_id': item['to_id'], 'text': f"{SYSTEM_SENDER_NAME}: {chunks[part]}"})
                        result = response.json()
                        if response.status_code == 200 and result.get('ok'):
                            changes.update(bot_part=part+1, telegram_message_id=result.get('result', {}).get('message_id'))
                            await outbox.update_one({'_id': item['_id']}, {'$set': changes})
                        elif response.status_code == 403:
                            changes.update(bot_done=True, delivery_error='recipient_unavailable')
                            break
                        else:
                            changes['delivery_error'] = f"telegram_{response.status_code}"
                            break
                    else:
                        changes.update(bot_done=True, delivery_error=None)
            if (item['raven_done'] or changes.get('raven_done')) and (item['bot_done'] or changes.get('bot_done')):
                changes['complete'] = True
        except (httpx.HTTPError, ValueError):
            changes['delivery_error'] = 'temporary_transport_error'
        attempts = item.get('attempts', 0) + 1
        changes.update(attempts=attempts, next_attempt=datetime.utcnow() + timedelta(seconds=min(1800, 30 * 2 ** min(attempts, 6))))
        await outbox.update_one({'_id': item['_id']}, {'$set': changes})

async def watcher():
    import logging
    while True:
        try:
            await flush()
        except Exception:
            # Do not log exception URLs, which may contain the bot credential.
            logging.getLogger(__name__).warning('Battle notice delivery will retry')
        await asyncio.sleep(15)
