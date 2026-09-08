from typing import Literal
from uuid import UUID
from fastapi import APIRouter, Depends, HTTPException
from pydantic import BaseModel, Field, StrictBool
from auth import get_user, get_full_admin
from db import db, players
import family as engine

router = APIRouter(prefix='/api')

async def admin(user=Depends(get_user)):
    return await get_full_admin(user)

@router.get('/family')
async def family(user=Depends(get_user)):
    p = await engine.person(user['id'])
    ownkey = engine.key(p)
    marriages = await engine.marriages.find({'parent_keys': ownkey}).sort('created_at', -1).to_list(None)
    kids = await engine.children.find({'$or': [{'parent_keys': ownkey}, {'patron_key': ownkey}, {'_id': p.get('family_child_id', '')}]}).sort('born_at', 1).to_list(None)
    # Do not reveal future births, random total, other account wallets or private profile data.
    return {'character_key': ownkey, 'settings': await engine.settings(),
            'marriages': [engine.clean(m) for m in marriages], 'children': [engine.clean(c) for c in kids],
            'succession': await engine.preview(p), 'stages': engine.STAGES, 'game_now': engine.now()}

@router.get('/family/candidates')
async def candidates(user=Depends(get_user)):
    p = await engine.person(user['id'])
    from public_audience import _admin_ids
    excluded = set(await _admin_ids())
    busy = {k async for m in engine.marriages.find({'status': {'$in': engine.OPEN}}) for k in m['parent_keys']}
    return [{'tg_id': v['tg_id'], 'name': v['name'], 'castle': v['castle']} async for v in players.find({
        'gender': 'lady' if p['gender'] == 'lord' else 'lord', 'tg_id': {'$ne': p['tg_id']}})
        if engine.active(v) and v['tg_id'] not in excluded and engine.key(v) not in busy]

class Proposal(BaseModel):
    target_id: int
    request_id: UUID

@router.post('/family/proposals')
async def proposal(body: Proposal, user=Depends(get_user)):
    await engine.tick()
    return await engine.propose(await engine.person(user['id']), body.target_id, str(body.request_id))

class Decision(BaseModel):
    accept: StrictBool
    reason: str = Field(default='', max_length=500)

@router.post('/family/proposals/{mid}/respond')
async def response(mid: str, body: Decision, user=Depends(get_user)):
    await engine.tick()
    return await engine.respond(await engine.person(user['id']), mid, body.accept)

class ChildAction(BaseModel):
    name: str | None = Field(default=None, min_length=2, max_length=40)
    stage: int | None = Field(default=None, ge=0, le=3)
    specialty: Literal['strategy', 'diplomacy', 'economy'] = 'strategy'

@router.post('/family/children/{cid}')
async def child(cid: str, body: ChildAction, user=Depends(get_user)):
    if (body.name is None) == (body.stage is None):
        raise HTTPException(400, 'یک نام یا یک مرحلهٔ آموزش مشخص کن')
    return await engine.child_action(await engine.person(user['id']), cid, body.name, body.stage, body.specialty)

@router.get('/admin/family')
async def admin_family(user=Depends(admin)):
    await engine.tick()
    return {'settings': await engine.settings(),
            'requests': [engine.clean(m) async for m in engine.marriages.find({'status': 'accepted'}).sort('created_at', 1)],
            'children': [engine.clean(c) async for c in engine.children.find({'status': 'alive'}).sort('born_at', -1)]}

@router.post('/admin/family/proposals/{mid}')
async def review(mid: str, body: Decision, user=Depends(admin)):
    await engine.tick()
    return await engine.approve(mid, body.accept, body.reason.strip())

class Settings(BaseModel):
    marriage_gold: int = Field(ge=0, le=1000000)
    marriage_wine: int = Field(ge=0, le=1000000)
    training_gold: int = Field(ge=0, le=1000000)
    training_food: int = Field(ge=0, le=1000000)

@router.post('/admin/family/settings')
async def save_settings(body: Settings, user=Depends(admin)):
    if body.marriage_gold % 2 or body.marriage_wine % 2:
        raise HTTPException(400, 'هزینهٔ کل ازدواج باید عدد زوج باشد تا مساوی تقسیم شود')
    await db.game_settings.update_one({'_id': 'family'}, {'$set': body.model_dump()}, upsert=True)
    return {'ok': True}

@router.post('/admin/family/children/{cid}/name')
async def rename(cid: str, body: ChildAction, user=Depends(admin)):
    if body.name is None:
        raise HTTPException(400, 'نام را بنویس')
    return await engine.child_action({}, cid, name=body.name, admin=True)

@router.get('/admin/family/{tg_id}/succession')
async def succession(tg_id: int, user=Depends(admin)):
    await engine.tick()
    return await engine.preview(await engine.person(tg_id))
