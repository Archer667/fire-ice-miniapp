"""Public broadcasts include every admin, even without a player character."""
from db import players
from admin_notifications import _admin_ids

async def public_recipients():
    rows = {p['tg_id']: p async for p in players.find({}, {'tg_id': 1, 'name': 1})}
    for uid in await _admin_ids():
        rows.setdefault(uid, {'tg_id': uid, 'name': 'ادمین'})
    return list(rows.values())

async def public_players():
    for row in await public_recipients():
        yield row
