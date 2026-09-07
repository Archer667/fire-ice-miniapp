"""Persistent game time. Authentication and security logs keep using real UTC."""
from datetime import datetime, timedelta
from db import game_settings

_state = {}

def real_now():
    return datetime.utcnow()

def now():
    current = _state.get('paused_at') or real_now()
    return current - timedelta(seconds=_state.get('offset_seconds', 0))

def paused():
    return bool(_state.get('paused_at'))

async def load():
    global _state
    _state = await game_settings.find_one({'_id': 'game_clock'}) or {}

def status():
    return {'paused': paused(), 'reason': _state.get('reason', ''),
            'game_now': now().isoformat() + 'Z',
            'paused_at': _state['paused_at'].isoformat() + 'Z' if paused() else None}

async def change(stop, reason, actor):
    global _state
    await load()
    if stop == paused():
        return status()
    current = real_now()
    offset = _state.get('offset_seconds', 0)
    if not stop:
        offset += max(0, (current - _state['paused_at']).total_seconds())
    state = {'paused_at': current if stop else None, 'offset_seconds': offset,
             'reason': reason if stop else '', 'changed_by': actor, 'changed_at': current}
    await game_settings.update_one({'_id': 'game_clock'}, {'$set': state}, upsert=True)
    _state = state
    return status()
