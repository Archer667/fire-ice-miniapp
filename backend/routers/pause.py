from fastapi import APIRouter, Depends
from pydantic import BaseModel, Field, StrictBool
from auth import get_owner, get_user
import game_clock

router = APIRouter(prefix='/api')

async def owner_user(user: dict = Depends(get_user)):
    return await get_owner(user)

async def season_day():
    from db import players
    from config import SEASON_LENGTH_DAYS
    from admin_notifications import _admin_ids
    ids = list(await _admin_ids())
    query = {'tg_id': {'$nin': ids}}
    reset = await players.find_one({**query, 'season_started_at': {'$type': 'date'}}, sort=[('season_started_at', -1)])
    first = reset or await players.find_one({**query, 'created_at': {'$type': 'date'}}, sort=[('created_at', 1)])
    start = (first.get('season_started_at') or first.get('created_at')) if first else None
    day = max(0, (game_clock.now() - start).days) % SEASON_LENGTH_DAYS + 1 if start else 1
    return {'day': day, 'season_length': SEASON_LENGTH_DAYS}

@router.get('/game/status')
async def game_status():
    return {**game_clock.status(), **await season_day()}

class PauseBody(BaseModel):
    paused: StrictBool
    reason: str = Field(default='بررسی و رسیدگی به وضعیت بازی', max_length=500)

@router.post('/admin/game-pause')
async def change_pause(body: PauseBody, user: dict = Depends(owner_user)):
    return await game_clock.change(body.paused, body.reason.strip() or 'بررسی و رسیدگی به وضعیت بازی', user['id'])
