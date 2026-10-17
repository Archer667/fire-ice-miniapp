"""Display identity of the game season; independent of clocks and world resets."""
from datetime import datetime, timezone

from fastapi import APIRouter, Depends, HTTPException, Response
from pydantic import BaseModel, Field, StrictInt
from pymongo.errors import DuplicateKeyError

from auth import get_user, get_full_admin
from db import game_settings

router = APIRouter(tags=['season branding'])
SETTINGS_ID = 'season_branding_v1'
ORDINALS = ('اول', 'دوم', 'سوم', 'چهارم', 'پنجم', 'ششم', 'هفتم', 'هشتم', 'نهم', 'دهم')


class SeasonBrandingBody(BaseModel):
    number: StrictInt = Field(ge=1, le=9999)
    name: str = Field(default='', max_length=80)
    revision: StrictInt = Field(ge=0)


def season_title(number, name=''):
    label = ORDINALS[number - 1] if number <= len(ORDINALS) else str(number).translate(str.maketrans('0123456789', '۰۱۲۳۴۵۶۷۸۹'))
    return f'والریا : سیزن {label}' + (f' — {name}' if name else '')


async def read_branding():
    row = await game_settings.find_one({'_id': SETTINGS_ID}) or {}
    number = row.get('number', 1)
    name = row.get('name', '')
    return {'number': number, 'name': name, 'revision': row.get('revision', 0),
            'title': season_title(number, name)}


@router.get('/api/season-branding')
async def public_branding(response: Response):
    response.headers['Cache-Control'] = 'no-store'
    return await read_branding()


@router.put('/api/admin/season-branding')
async def save_branding(body: SeasonBrandingBody, user=Depends(get_user)):
    user = await get_full_admin(user)
    name = body.name.strip()
    if any(ord(char) < 32 for char in name):
        raise HTTPException(400, 'نام سیزن باید در یک خط نوشته شود')
    try:
        result = await game_settings.update_one(
            {'_id': SETTINGS_ID, 'revision': body.revision},
            {'$set': {'number': body.number, 'name': name,
                      'updated_at': datetime.now(timezone.utc), 'updated_by': user['id']},
             '$inc': {'revision': 1}}, upsert=body.revision == 0)
    except DuplicateKeyError:
        raise HTTPException(409, 'تنظیمات سیزن تغییر کرده است؛ اطلاعات تازه را دریافت کن')
    if not result.matched_count and result.upserted_id is None:
        raise HTTPException(409, 'تنظیمات سیزن تغییر کرده است؛ اطلاعات تازه را دریافت کن')
    return {'number': body.number, 'name': name, 'revision': body.revision + 1,
            'title': season_title(body.number, name)}
