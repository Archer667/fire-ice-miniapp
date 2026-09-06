import unittest
from unittest.mock import AsyncMock, patch
from fastapi import HTTPException
from pydantic import ValidationError
import market_rules
from routers import market, admin

class FloorTests(unittest.IsolatedAsyncioTestCase):
    async def test_defaults_and_overrides(self):
        with patch.object(market_rules.game_settings, 'find_one', AsyncMock(return_value=None)):
            self.assertEqual(set((await market_rules.price_floors()).values()), {10})
        with patch.object(market_rules.game_settings, 'find_one', AsyncMock(return_value={'prices': {'wood': 15}})):
            self.assertEqual((await market_rules.price_floors())['wood'], 15)

    async def test_reject_low_price_before_wallet_write(self):
        with patch.object(market, 'price_floors', AsyncMock(return_value={'wood': 10})), patch.object(market, '_market_write_guard'):
            with self.assertRaises(HTTPException) as e:
                await market.create_player_listing(market.PlayerListingBody(resource='wood', qty=2, price=9), {'id': 1})
            self.assertEqual(e.exception.status_code, 400)

    async def test_admin_base_three(self):
        existing={'price': 2, 'base_price': 1, 'qty': 1, 'reference_qty': 300}
        with patch.object(admin.market_listings, 'find_one', AsyncMock(return_value=existing)), patch.object(admin.market_listings, 'update_one', AsyncMock()) as save:
            await admin.admin_market_set(admin.MarketListingBody(resource='wood', qty=300, price=3), {})
            saved=save.call_args.args[1]['$set']
            self.assertEqual(saved['base_price'], 3)
            self.assertEqual(saved['price'], 3)

    def test_floors_require_integer(self):
        with self.assertRaises(ValidationError):
            admin.PlayerMarketFloorsBody(prices={'wood': 1.5})
