"""Apply the coastal starting harbor without downgrading completed upgrades."""
from copy import deepcopy
from db import players
from game import normalize_building_state, owned_castles

def harbor_default(buildings):
    result = deepcopy(buildings)
    state = normalize_building_state(result.get('port'))
    if state['level'] < 1:
        state['level'] = 1
        if state.get('upgrade_to') == 1:
            state.update(upgrade_to=None, ready_at=None, notice_pending=None)
        result['port'] = state
    return result

async def ensure_coastal_harbors():
    from routers.war import all_castle_names_and_ports
    from character_records import vacant
    _, ports = await all_castle_names_and_ports()
    async for player in players.find({}):
        changes = {}
        for castle in owned_castles(player):
            if castle not in ports:
                continue
            home = castle == player.get('castle')
            current = player.get('buildings', {}) if home else player['castle_buildings'][castle]
            updated = harbor_default(current)
            if updated != current:
                changes['buildings' if home else f'castle_buildings.{castle}'] = updated
        if changes:
            await players.update_one({'_id': player['_id']}, {'$set': changes})
    for castle in ports:
        row = await vacant.find_one({'_id': castle}) or {}
        buildings = harbor_default(row.get('buildings', {}))
        if buildings != row.get('buildings'):
            await vacant.update_one({'_id': castle}, {'$set': {'buildings': buildings}}, upsert=True)
