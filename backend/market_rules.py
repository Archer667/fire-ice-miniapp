from db import game_settings
from game_data import TRADE_GOODS

async def price_floors():
    doc = await game_settings.find_one({'_id': 'player_market_price_floors'}) or {}
    saved = doc.get('prices', {})
    return {key: max(1, int(saved.get(key, 10))) for key in TRADE_GOODS}

async def price_ceilings():
    doc = await game_settings.find_one({'_id': 'player_market_price_floors'}) or {}
    saved = doc.get('ceilings', {})
    return {key: saved.get(key) for key in TRADE_GOODS}

async def price_limits():
    return {'prices': await price_floors(), 'ceilings': await price_ceilings()}

async def check_price(resource, price):
    from fastapi import HTTPException
    limits = await price_limits()
    floor = limits['prices'].get(resource, 10)
    ceiling = limits['ceilings'].get(resource)
    if price < floor:
        raise HTTPException(400, f'حداقل قیمت هر واحد این کالا {floor} سکه است')
    if ceiling is not None and price > ceiling:
        raise HTTPException(400, f'حداکثر قیمت هر واحد این کالا {ceiling} سکه است')
    return limits
