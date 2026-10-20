from typing import Literal
from fastapi import APIRouter, Depends
from pydantic import BaseModel, Field, StrictBool
from auth import get_user, get_admin, get_full_admin
from character_records import blacklist, retire

router = APIRouter(prefix='/api/admin')

async def administrator(user=Depends(get_user)):
    return await get_admin(user)

async def full_administrator(user=Depends(get_user)):
    return await get_full_admin(user)

class RetireBody(BaseModel):
    character_key: str = ''
    action: Literal['delete', 'death']
    reason: str = Field(default='', max_length=500)
    narrative: str = Field(default='', max_length=2000)
    blacklisted: StrictBool = False
    kill_heirs: StrictBool = False

@router.get('/blacklist')
async def list_blacklist(user=Depends(administrator)):
    return [{'tg_id': r['_id'], 'name': r.get('name', ''), 'reason': r.get('reason', '')}
            async for r in blacklist.find({}).sort('added_at', -1)]

@router.post('/characters/{tg_id}/retire')
async def retire_character(tg_id: int, body: RetireBody, user=Depends(full_administrator)):
    from routers.admin import castle_transfer_lock
    from fastapi import HTTPException
    if body.action == 'death' and not body.reason.strip():
        raise HTTPException(400, 'دلیل مرگ را بنویس')
    async with castle_transfer_lock:
        return await retire(tg_id, body, user['id'])

class SwapBody(BaseModel):
    first_id: int
    first_castle: str
    second_id: int
    second_castle: str

@router.post('/castle-swap')
async def swap(body: SwapBody, user=Depends(full_administrator)):
    from routers.admin import castle_transfer_lock
    from character_records import swap_castles
    async with castle_transfer_lock:
        return await swap_castles(body.first_id, body.first_castle, body.second_id, body.second_castle)

class CharacterAdmissionBody(BaseModel):
    region: str = Field(max_length=80)
    place: str = Field(min_length=1, max_length=150)
    character_key: str = Field(default='', max_length=200)

@router.get('/character-admission/options')
async def admission_options(user=Depends(full_administrator)):
    import character_travel as travel
    places = [{'id':name,'name':name} for name in sorted(travel.TRAVEL_GRAPH)]
    places += [{'id':p['_id'],'name':p['name']} async for p in travel.places.find({'enabled':True})]
    return {'places':places}

@router.post('/players/{tg_id}/approve-character')
async def approve_character(tg_id:int, body:CharacterAdmissionBody, user=Depends(full_administrator)):
    from routers.admin import castle_transfer_lock
    from character_admission import approve
    from auth import get_admin_role
    from fastapi import HTTPException
    if await get_admin_role({'id':tg_id}): raise HTTPException(400,'حساب مدیریت از ثبت‌نام بازیکن جداست')
    async with castle_transfer_lock:
        return await approve(tg_id,body.region,body.place,user['id'],body.character_key)
