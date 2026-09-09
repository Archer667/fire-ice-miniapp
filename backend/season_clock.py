"""One season epoch for all accounts, including late registrations and heirs."""
from datetime import datetime
from db import game_settings, players
import game_clock
from config import SEASON_LENGTH_DAYS

async def start_season(at=None):
    await game_settings.update_one({'_id': 'season_clock'}, {'$set': {'started_at': at or game_clock.now()}}, upsert=True)

async def season_day():
    row = await game_settings.find_one({'_id': 'season_clock'}) or {}
    start = row.get('started_at')
    if not isinstance(start, datetime):
        from admin_notifications import _admin_ids
        query = {'tg_id': {'$nin': list(await _admin_ids())}}
        # Migrate the old reset marker once; never use each visitor's signup date.
        reset = await players.find_one({**query, 'season_started_at': {'$type': 'date'}}, sort=[('season_started_at', -1)])
        first = reset or await players.find_one({**query, 'created_at': {'$type': 'date'}}, sort=[('created_at', 1)])
        start = (first.get('season_started_at') or first.get('created_at')) if first else None
        if start:
            await game_settings.update_one({'_id': 'season_clock'}, {'$setOnInsert': {'started_at': start}}, upsert=True)
            start = (await game_settings.find_one({'_id': 'season_clock'}))['started_at']
    day = min(SEASON_LENGTH_DAYS, max(0, (game_clock.now() - start).days) + 1) if start else 1
    return {'day': day, 'season_length': SEASON_LENGTH_DAYS}
