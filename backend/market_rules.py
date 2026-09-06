from db import game_settings
from game_data import TRADE_GOODS

async def price_floors():
    doc = await game_settings.find_one({'_id': 'player_market_price_floors'}) or {}
    saved = doc.get('prices', {})
    return {key: max(1, int(saved.get(key, 10))) for key in TRADE_GOODS}
