"""Shared word limits for player narratives; enforced before state changes."""
import re
from fastapi import HTTPException
from db import game_settings

DEFAULTS = {'roleplay_words': 1000, 'scenario_words': 1000, 'request_words': 1000}
async def text_limits():
    row = await game_settings.find_one({'_id': 'weekly_submission_limits'}) or {}
    return {key: row.get(key, value) for key, value in DEFAULTS.items()}

def word_count(text):
    return len(re.findall(r'[^\s\ufeff]+', text))

async def check_text(text, kind='scenario_words'):
    maximum = (await text_limits())[kind]
    if len(text) > 500000 or word_count(text) > maximum:
        raise HTTPException(400, f'سقف این متن {maximum} کلمه است؛ متن را کوتاه‌تر کن')
