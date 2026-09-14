"""Wall-clock display only: never feed converted values back into game timers."""
from datetime import datetime, timedelta, timezone
from zoneinfo import ZoneInfo
from db import db
import game_clock

TEHRAN = ZoneInfo('Asia/Tehran')

def tehran_text(value):
    if not value:
        return 'نامشخص'
    if isinstance(value, str):
        value = datetime.fromisoformat(value.replace('Z', '+00:00'))
    return value.replace(tzinfo=timezone.utc).astimezone(TEHRAN).strftime('%Y-%m-%d %H:%M:%S') if value.tzinfo is None else value.astimezone(TEHRAN).strftime('%Y-%m-%d %H:%M:%S')

class DisplayClock:
    def __init__(self, checkpoints):
        self.checkpoints = sorted(checkpoints, key=lambda row: row[0])

    def real(self, value):
        if not value:
            return None
        for start, offset in reversed(self.checkpoints):
            if value >= start:
                return value + timedelta(seconds=offset)
        return None

    def iso(self, value):
        result = self.real(value)
        return result.isoformat() + 'Z' if result else None

    def text(self, value):
        result = self.real(value)
        return tehran_text(result) if result else (f'{value} (زمان داخلی بازی؛ ساعت واقعی در سوابق موجود نیست)' if value else 'نامشخص')

async def display_clock():
    points = []
    # Successful resume audit records retain both the frozen game timestamp
    # and real UTC. Earlier history is intentionally not guessed.
    async for row in db.admin_activity.find({'path':'/api/admin/game-pause', 'status':{'$gte':200,'$lt':300}, 'request.paused':False}, {'at':1,'game_at':1}):
        if row.get('at') and row.get('game_at'):
            points.append((row['game_at'], (row['at']-row['game_at']).total_seconds()))
    state = await db.game_settings.find_one({'_id':'game_clock'}) or {}
    for row in state.get('display_checkpoints', []):
        points.append((row['game_at'], row['offset_seconds']))
    offset = state.get('offset_seconds', 0)
    if not offset:
        points.append((datetime.min, 0))
    elif state.get('changed_at') and not state.get('paused_at'):
        points.append((state['changed_at']-timedelta(seconds=offset), offset))
    return DisplayClock(points)
