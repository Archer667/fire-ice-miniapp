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

    async def test_ceiling_rejects_listing_before_wallet_write(self):
        with patch.object(market, 'price_floors', AsyncMock(return_value={'wood':10})), \
             patch.object(market, 'price_ceilings', AsyncMock(return_value={'wood':20})), \
             patch.object(market, '_market_write_guard'), \
             patch.object(market.players, 'find_one', AsyncMock()) as wallet:
            with self.assertRaises(HTTPException) as error:
                await market.create_player_listing(market.PlayerListingBody(resource='wood',qty=2,price=21),{'id':1})
            self.assertEqual(error.exception.status_code,400)
            wallet.assert_not_awaited()

    async def test_old_overpriced_listing_cannot_be_bought(self):
        from bson import ObjectId
        oid=ObjectId()
        with patch.object(market, '_market_write_guard'), \
             patch.object(market.player_market_listings,'find_one',AsyncMock(return_value={'_id':oid,'seller_tg_id':2,'resource':'wood','price':21})), \
             patch.object(market,'price_floors',AsyncMock(return_value={'wood':10})), \
             patch.object(market,'price_ceilings',AsyncMock(return_value={'wood':20})), \
             patch.object(market.players,'update_one',AsyncMock()) as wallet:
            with self.assertRaises(HTTPException) as error:
                await market.buy_player_listing(market.PlayerMarketBuyBody(listing_id=str(oid),qty=1),{'id':1})
            self.assertEqual(error.exception.status_code,409)
            wallet.assert_not_awaited()

    async def test_admin_rejects_ceiling_below_floor(self):
        prices={key:10 for key in admin.TRADE_GOODS}
        caps={key:20 for key in prices}
        caps['wood']=9
        with patch.object(admin.game_settings,'update_one',AsyncMock()) as save:
            with self.assertRaises(HTTPException):
                await admin.set_player_market_floors(admin.PlayerMarketFloorsBody(prices=prices,ceilings=caps),{})
            save.assert_not_awaited()

    async def test_admin_persists_optional_ceiling_and_equal_bounds(self):
        prices={key:10 for key in admin.TRADE_GOODS}
        caps={key:None for key in prices}
        caps['wood']=10
        with patch.object(admin.game_settings,'update_one',AsyncMock()) as save:
            await admin.set_player_market_floors(admin.PlayerMarketFloorsBody(prices=prices,ceilings=caps),{})
            self.assertEqual(save.call_args.args[1]['$set']['ceilings'],caps)

    def test_ceiling_requires_integer(self):
        with self.assertRaises(ValidationError):
            admin.PlayerMarketFloorsBody(prices={'wood':10},ceilings={'wood':20.5})
