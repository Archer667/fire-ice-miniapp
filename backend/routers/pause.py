from fastapi import APIRouter, Depends
from pydantic import BaseModel, Field, StrictBool
from auth import get_owner, get_user
import game_clock

router = APIRouter(prefix='/api')

async def owner_user(user: dict = Depends(get_user)):
    return await get_owner(user)

@router.get('/game/status')
async def game_status():
    return game_clock.status()

class PauseBody(BaseModel):
    paused: StrictBool
    reason: str = Field(default='بررسی و رسیدگی به وضعیت بازی', max_length=500)

@router.post('/admin/game-pause')
async def change_pause(body: PauseBody, user: dict = Depends(owner_user)):
    return await game_clock.change(body.paused, body.reason.strip() or 'بررسی و رسیدگی به وضعیت بازی', user['id'])
