"""Daily food settlement; prepared absolute writes are recoverable under game_state_lock."""
from datetime import timedelta
import math
from db import db, players, campaigns, ambushes
from game import now, normalize_datetime, apply_production, production_fields, building_levels_for
from game_data import NAVAL_TROOPS, campaign_power
from army_upkeep import food_rate


def starvation_plan(men, available, civilian_rate, armies):
    """Spend deficit on civilians first; remaining deficit yields equal army loss ratios.

    armies contains (troops, elapsed_days). Ship hulls/equipment are not people.
    Largest remainders distribute whole-person casualties without favouring small armies.
    """
    men = max(0, int(men))
    civilian_need = men * max(0, civilian_rate)
    army_need = sum(food_rate(t) * days for t, days in armies)
    need = civilian_need + army_need
    consumed = min(max(0, available), need)
    deficit = max(0, need - consumed)
    civil_loss = min(men, math.ceil(min(deficit, civilian_need) / civilian_rate - 1e-9)) if civilian_rate > 0 else 0
    remaining = max(0, deficit - civilian_need)
    ratio = min(1, remaining / army_need) if army_need > 0 else 0
    losses = [{} for _ in armies]
    cells = [(i, tid, max(0, int(n)) * ratio) for i, (t, _) in enumerate(armies) for tid, n in t.items() if tid not in NAVAL_TROOPS]
    total = math.ceil(sum(x[2] for x in cells) - 1e-9)
    used = 0
    for i, tid, value in cells:
        losses[i][tid] = math.floor(value)
        used += losses[i][tid]
    for i, tid, _ in sorted(cells, key=lambda x: -(x[2] % 1))[:max(0, total-used)]:
        losses[i][tid] += 1
    return {"consumed": consumed, "shortage": deficit, "civilian_losses": civil_loss, "army_losses": losses, "required": need}


async def apply_record(record):
    for entry in record['armies']:
        await db[entry['collection']].update_one({'_id': entry['id']}, {'$set': entry['update']})
    await players.update_one({'tg_id': record['tg_id']}, {'$set': record['player_update']})
    # Cleanup is idempotent; a destroyed army must no longer lock a battle.
    for entry in record['armies']:
        if entry['collection'] == 'campaigns' and entry['update'].get('active') is False:
            from routers.admin import _remove_campaign_from_battle
            await _remove_campaign_from_battle(entry['before'], 'این لشکر به علت کمبود غذا از بین رفت.')
    await db.food_settlements.update_one({'_id': record['_id']}, {'$set': {'status': 'done'}})


async def recover_pending_food():
    async for record in db.food_settlements.find({'status': 'prepared'}):
        await apply_record(record)


async def tick():
    current = now()
    await db.game_settings.update_one({'_id': 'food_settlement_v1'}, {'$setOnInsert': {'started_at': current}}, upsert=True)
    epoch = (await db.game_settings.find_one({'_id': 'food_settlement_v1'}))['started_at']
    from routers.rebellions import get_settings
    settings = await get_settings()
    async for player in players.find({'region': {'$ne': None}, 'castle': {'$ne': None}, 'is_dead': {'$ne': True}}):
        start = normalize_datetime(player.get('food_settled_at')) or max(epoch, normalize_datetime(player.get('created_at')) or epoch)
        days = int((current-start).total_seconds() // 86400)
        if days < 1:
            continue
        end = start + timedelta(days=days)
        key = f"{player['tg_id']}:{end.isoformat()}"
        previous = await db.food_settlements.find_one({'_id': key})
        if previous:
            if previous['status'] == 'prepared':
                await apply_record(previous)
            continue
        player = apply_production(player)
        rows = [('campaigns', c) async for c in campaigns.find({'tg_id': player['tg_id'], 'active': True})]
        rows += [('ambushes', c) async for c in ambushes.find({'tg_id': player['tg_id'], 'status': {'$in': ['pending_score', 'active']}})]
        durations = [max(0, (end-max(start, normalize_datetime(c.get('created_at')) or start)).total_seconds()/86400) for _, c in rows]
        ration = settings['ration_levels'].get(player.get('food_ration', settings['default_ration']), settings['ration_levels']['normal'])
        rate = float(settings['base_food_per_100_men'])/100 * float(ration['multiplier']) * days
        result = starvation_plan(player['resources'].get('men', 0), player['resources'].get('food', 0), rate,
                                 [(c.get('troops', {}), duration) for (_, c), duration in zip(rows, durations)])
        player['resources']['food'] = max(0, player['resources'].get('food', 0)-result['consumed'])
        player['resources']['men'] = max(0, player['resources'].get('men', 0)-result['civilian_losses'])
        updates = []
        for (collection, army), losses in zip(rows, result['army_losses']):
            if not any(losses.values()):
                continue
            troops = {tid: max(0, int(n)-losses.get(tid, 0)) for tid, n in army.get('troops', {}).items()}
            count = sum(troops.values())
            update = {'troops': troops, 'men_committed': count, 'food_per_day': food_rate(troops),
                      'power': campaign_power(troops, dict(building_levels_for(player, army.get('origin_castle'))))}
            if collection == 'ambushes':
                update['soldiers_committed'] = sum(n for tid, n in troops.items() if tid not in NAVAL_TROOPS)
            if count == 0:
                update.update(active=False, status='destroyed', engagement_locked=False)
            updates.append({'collection': collection, 'id': army['_id'], 'before': army, 'update': update})
        summary = {k: v for k, v in result.items() if k != 'army_losses'}
        summary.update(at=end, soldiers_lost=sum(sum(v.values()) for v in result['army_losses']))
        record = {'_id': key, 'tg_id': player['tg_id'], 'status': 'prepared', 'armies': updates,
                  'player_update': {**production_fields(player), 'food_settled_at': end, 'food_settlement_summary': summary}}
        await db.food_settlements.insert_one(record)
        await apply_record(record)
