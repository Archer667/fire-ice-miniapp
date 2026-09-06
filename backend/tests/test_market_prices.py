import os
import unittest
from contextlib import ExitStack
from datetime import datetime, timedelta
from unittest.mock import patch
from motor.motor_asyncio import AsyncIOMotorClient
from fastapi import HTTPException
from pydantic import ValidationError
from market_pricing import stock_price
from routers import market, admin


class PriceRulesTests(unittest.TestCase):
    def test_stock_price_is_monotonic_bounded_and_reversible(self):
        row = {'qty': 100, 'reference_qty': 100, 'price': 10, 'base_price': 10}
        prices = [stock_price(row, q) for q in range(100, -1, -1)]
        self.assertEqual(prices, sorted(prices))
        self.assertEqual((prices[0], prices[50], prices[-1]), (10, 15, 20))
        self.assertEqual(stock_price(row, 200), 10)

    def test_quantity_and_price_are_separate_positive_integers(self):
        row = market.PlayerListingBody(resource='wood', qty=7, price=4)
        self.assertEqual((row.qty, row.price), (7, 4))
        for changes in ({'price': 0}, {'price': 1.5}, {'qty': 0}, {'qty': True}, {'qty': 1.2}):
            with self.subTest(changes=changes), self.assertRaises(ValidationError):
                market.PlayerListingBody(**{'resource': 'wood', 'qty': 7, 'price': 4, **changes})


@unittest.skipUnless(os.getenv('PROJECT_TEST_DB') == 'valyria_projects_test', 'requires isolated test database')
class MarketPricingTests(unittest.IsolatedAsyncioTestCase):
    async def asyncSetUp(self):
        uri = os.environ['MONGODB_URI']
        if 'valyria-project-test-db:27017' not in uri:
            raise RuntimeError('Refusing non-test Mongo')
        self.client = AsyncIOMotorClient(uri)
        self.db = self.client.valyria_projects_test
        self.stack = ExitStack()
        for name in ('players', 'market_listings', 'player_market_listings', 'black_market_listings'):
            await self.db[name].delete_many({})
            for module in (market, admin):
                self.stack.enter_context(patch.object(module, name, self.db[name]))
        self.stack.enter_context(patch.object(market, 'feature_enabled', return_value=True))
        self.stack.enter_context(patch.object(market, 'apply_production', side_effect=lambda p: p))
        self.stack.enter_context(patch.object(market, 'production_fields', side_effect=lambda p: {'resources': p['resources']}))
        def add(p, goods):
            for k, q in goods.items(): p['resources'][k] = p['resources'].get(k, 0) + q
        self.stack.enter_context(patch.object(market, 'add_resources', side_effect=add))
        for uid in (101, 102):
            await self.db.players.insert_one({'tg_id': uid, 'name': str(uid), 'resources': {'wood': 100, 'gold': 10000}})

    async def asyncTearDown(self):
        self.stack.close()
        self.client.close()

    async def test_player_price_four_and_quantity_seven_stay_independent(self):
        result = await market.create_player_listing(market.PlayerListingBody(resource='wood', qty=7, price=4), {'id': 101})
        rows = await market.list_player_market({'id': 102})
        self.assertEqual((rows[0]['qty'], rows[0]['price']), (7, 4))
        paid = await market.buy_player_listing(market.PlayerMarketBuyBody(listing_id=result['id'], qty=3), {'id': 102})
        self.assertEqual(paid['cost'], 12)
        await market.drift_market_prices()
        rows = await market.list_player_market({'id': 102})
        self.assertEqual((rows[0]['qty'], rows[0]['price']), (4, 4))
        self.assertEqual((await self.db.players.find_one({'tg_id': 101}))['resources']['gold'], 10012)
        await market.cancel_player_listing(result['id'], {'id': 101})
        self.assertEqual((await self.db.players.find_one({'tg_id': 101}))['resources']['wood'], 97)

    async def test_official_shortage_restock_and_percentage_share_one_formula(self):
        await admin.admin_market_set(admin.MarketListingBody(resource='wood', qty=100, price=10), {'id': 999})
        paid = await market.buy(market.BuyBody(resource='wood', qty=50, expected_price=10), {'id': 101})
        self.assertEqual(paid['cost'], 500)
        rows = await market.list_market({'id': 101})
        self.assertEqual((rows[0]['price'], rows[0]['change_pct']), (15, 50))
        await market.drift_market_prices()
        self.assertEqual((await market.list_market({'id': 101}))[0]['price'], 15)
        with self.assertRaises(HTTPException) as error:
            await market.buy(market.BuyBody(resource='wood', qty=1, expected_price=10), {'id': 101})
        self.assertEqual(error.exception.status_code, 409)
        await admin.admin_market_set(admin.MarketListingBody(resource='wood', qty=75, price=10), {'id': 999})
        self.assertEqual((await market.list_market({'id': 101}))[0]['price'], 13)
        await admin.admin_market_set(admin.MarketListingBody(resource='wood', qty=100, price=10), {'id': 999})
        self.assertEqual((await market.list_market({'id': 101}))[0]['change_pct'], 0)

    async def test_black_price_does_not_follow_sales_or_ticks(self):
        created = await self.db.black_market_listings.insert_one({'resource': 'wood', 'qty': 5, 'price': 7,
            'expires_at': datetime.utcnow() + timedelta(hours=1), 'created_at': datetime.utcnow()})
        paid = await market.buy_black_market(market.BlackBuyBody(listing_id=str(created.inserted_id), qty=2), {'id':101})
        self.assertEqual(paid['cost'], 14)
        await market.drift_market_prices()
        row = (await market.list_black_market({'id':101}))[0]
        self.assertEqual((row['qty'], row['price']), (3, 7))
