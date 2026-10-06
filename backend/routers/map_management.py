"""Server-backed visual map drafts; publishing never changes castle ownership."""
import math
import json
from pathlib import Path
from fastapi import APIRouter, Depends, HTTPException
from pydantic import BaseModel, Field
from auth import get_user, get_full_admin
from db import game_settings
from game import now
from season_clock import season_day

router = APIRouter(prefix='/api/admin/map-layout', tags=['admin'])
KEY = 'visual_map_layout'
DEFAULT_LAYOUT = {'placements':json.loads((Path(__file__).parent.parent/'default_map_layout.json').read_text(encoding='utf-8')), 'climate':{'mode':'auto','spring_rain':.35,'autumn_rain':.65,'winter_snow':.55}}
MODELS = {f'{kind}-{n}' for kind in ('land','harbor','city','ruin') for n in (1,2,3)} | {'winterfell','twins','riverrun','pyke','eyrie','highgarden','sunspear','dragonstone','red-keep','kings-landing','oldtown','casterly-rock'}

async def admin_access(user=Depends(get_user)):
    return await get_full_admin(user)

class LayoutBody(BaseModel):
    revision: int = Field(ge=0)
    placements: list[dict] = Field(max_length=1000)
    climate: dict = Field(default_factory=dict)

def validate_layout(body):
    seen=set()
    for p in body.placements:
        if not isinstance(p.get('id'),str) or p['id'] in seen or not p.get('name') or len(p['name'])>150 or p.get('model') not in MODELS:
            raise HTTPException(422,'نام، شناسه یا مدل قلعه نامعتبر یا تکراری است')
        seen.add(p['id'])
        pos=p.get('position',{})
        for k,limit in [('x',1.5),('y',1),('z',2.8)]:
            v=pos.get(k)
            if isinstance(v,bool) or not isinstance(v,(int,float)) or not math.isfinite(v) or abs(v)>limit:
                raise HTTPException(422,'مختصات قلعه خارج از محدوده است')
        for k,lo,hi in [('size',.02,.4),('rotation',-3600,3600),('lift',-.1,.2)]:
            v=p.get(k)
            if isinstance(v,bool) or not isinstance(v,(int,float)) or not math.isfinite(v) or not lo<=v<=hi:
                raise HTTPException(422,'اندازه، چرخش یا ارتفاع نامعتبر است')
    climate=body.climate
    if climate.get('mode','auto') not in ('auto','manual') or climate.get('season',0) not in (0,1,2,3):
        raise HTTPException(422,'فصل نامعتبر است')
    for k in ('spring_rain','autumn_rain','winter_snow'):
        v=climate.get(k,.35 if k=='spring_rain' else .65 if k=='autumn_rain' else .55)
        if not isinstance(v,(int,float)) or not math.isfinite(v) or not 0<=v<=1:raise HTTPException(422,'احتمال بارش باید بین صفر و یک باشد')
    return {'placements':body.placements,'climate':climate}

@router.get('')
async def read_layout(user=Depends(admin_access)):
    row=await game_settings.find_one({'_id':KEY}) or {}
    return {'revision':row.get('revision',0),'draft':row.get('draft'),'published':row.get('published',DEFAULT_LAYOUT),'has_previous':bool(row.get('previous')),'calendar':await season_day()}

@router.put('')
async def save_layout(body:LayoutBody,user=Depends(admin_access)):
    layout=validate_layout(body)
    await game_settings.update_one({'_id':KEY},{'$setOnInsert':{'revision':0}},upsert=True)
    result=await game_settings.update_one({'_id':KEY,'revision':body.revision},{'$set':{'draft':layout,'updated_at':now(),'updated_by':user['id']},'$inc':{'revision':1}})
    if not result.modified_count:raise HTTPException(409,'ادمین دیگری نقشه را تغییر داده؛ دوباره بارگذاری کن')
    return await read_layout(user)

class RevisionBody(BaseModel):
    revision:int=Field(ge=0)

@router.post('/{action}')
async def publish_layout(action:str,body:RevisionBody,user=Depends(admin_access)):
    row=await game_settings.find_one({'_id':KEY}) or {}
    target=row.get('draft') if action=='publish' else row.get('previous') if action=='rollback' else None
    if target is None:raise HTTPException(400,'پیش‌نویس یا نسخهٔ قبلی موجود نیست')
    result=await game_settings.update_one({'_id':KEY,'revision':body.revision},{'$set':{'published':target,'previous':row.get('published',DEFAULT_LAYOUT),'published_at':now(),'published_by':user['id']},'$inc':{'revision':1}})
    if not result.modified_count:raise HTTPException(409,'نسخه تغییر کرده؛ دوباره بارگذاری کن')
    return await read_layout(user)
