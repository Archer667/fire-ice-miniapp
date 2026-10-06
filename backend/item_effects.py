"""Item effects and campaign inventory, independent of presentation rarity."""
from datetime import datetime, timezone


def instant(value):
    if isinstance(value, str):
        value = datetime.fromisoformat(value.replace('Z', '+00:00'))
    return value.astimezone(timezone.utc).replace(tzinfo=None) if value and value.tzinfo else value


def character_matches(grant, player):
    if grant.get('character_created_at') and instant(grant['character_created_at']) != instant(player.get('created_at')):
        return False
    return 'character_child_id' not in grant or grant['character_child_id'] == player.get('family_child_id')


def building_item_percent(player, building_id, at):
    at = instant(at)
    return sum(float(effect.get('percent', 0)) for effect in player.get('item_effects', {}).values()
               if effect.get('building_id') == building_id and character_matches(effect, player)
               and (not effect.get('starts_at') or instant(effect['starts_at']) <= at)
               and (not effect.get('expires_at') or at < instant(effect['expires_at'])))


async def campaign_for_grant(grant_id):
    from db import campaigns
    return await campaigns.find_one({'active': True, 'item_ids': str(grant_id)})


async def recover_item_effects():
    """Resume a grant interrupted between inventory insertion and effect activation."""
    from db import item_grants, players
    async for grant in item_grants.find({'effect_pending': True}):
        player = await players.find_one({'tg_id': grant['tg_id']})
        if player and character_matches(grant, player):
            await players.update_one({'tg_id': grant['tg_id'], 'created_at': player['created_at']},
                                     {'$set': {f"item_effects.{grant['_id']}": grant['effect']}})
        await item_grants.update_one({'_id': grant['_id']}, {'$unset': {'effect_pending': ''}})


async def select_war_items(player, ids):
    from bson import ObjectId
    from fastapi import HTTPException
    from db import item_grants, items
    from game import now
    if len(ids) > 30 or len(set(ids)) != len(ids):
        raise HTTPException(400, 'هر آیتم را فقط یک بار انتخاب کن؛ حداکثر ۳۰ آیتم')
    selected = []
    for raw in ids:
        try:
            oid = ObjectId(raw)
        except Exception:
            raise HTTPException(400, 'شناسهٔ آیتم نامعتبر است') from None
        grant = await item_grants.find_one({'_id': oid, 'tg_id': player['tg_id']})
        if not grant or not character_matches(grant, player):
            raise HTTPException(403, 'این آیتم متعلق به کاراکتر فعلی تو نیست')
        if grant.get('expires_at') and instant(grant['expires_at']) <= now():
            raise HTTPException(400, 'آیتم انتخاب‌شده منقضی شده است')
        template = await items.find_one({'_id': grant['item_id']})
        if not template or template.get('type') != 'war':
            raise HTTPException(400, 'فقط آیتم جنگی را می‌توان همراه لشکر فرستاد')
        if await campaign_for_grant(oid):
            raise HTTPException(409, 'این آیتم همراه یک لشکر فعال دیگر است')
        selected.append({'id': str(oid), 'name': template['name'], 'color': grant.get('color', template.get('color', 'gray')),
                         'description': template.get('description', ''), 'expires_at': grant.get('expires_at')})
    return selected
