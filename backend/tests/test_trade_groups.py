import os
import unittest
from contextlib import ExitStack
from datetime import datetime, timedelta
from unittest.mock import AsyncMock, patch
from motor.motor_asyncio import AsyncIOMotorClient
from pydantic import ValidationError
import trade_pacts
from routers import trade


class CaravanValidationTests(unittest.TestCase):
    def test_rejects_fractional_negative_string_and_bool(self):
        for value in (-1, 1.5, '2', True, None, float('inf')):
            with self.subTest(value=value), self.assertRaises(ValidationError):
                trade.CaravanBody(target_tg_id=2, resources={'gold': value})


@unittest.skipUnless(os.getenv('PROJECT_TEST_DB') == 'valyria_projects_test', 'requires isolated test database')
class TradeGroupTests(unittest.IsolatedAsyncioTestCase):
    async def asyncSetUp(self):
        uri = os.environ['MONGODB_URI']
        if 'valyria-project-test-db:27017' not in uri:
            raise RuntimeError('Refusing non-test database')
        self.client = AsyncIOMotorClient(uri)
        self.db = self.client.valyria_projects_test
        for name in ('alliances', 'caravans', 'players'):
            await self.db[name].delete_many({})
        self.stack = ExitStack()
        self.stack.enter_context(patch.object(trade_pacts, 'alliances', self.db.alliances))
        for name in ('alliances', 'players', 'caravans'):
            self.stack.enter_context(patch.object(trade, name, self.db[name]))
        self.stack.enter_context(patch.object(trade, 'send_system_message', AsyncMock()))
        self.stack.enter_context(patch.object(trade, 'apply_production', side_effect=lambda p: p))
        self.stack.enter_context(patch.object(trade, 'production_fields', side_effect=lambda p: {'resources': p['resources']}))
        self.when = datetime(2026, 9, 5)

    async def asyncTearDown(self):
        self.stack.close()
        self.client.close()

    async def pact(self, source, target, group=None, status='accepted', **kwargs):
        return await self.db.alliances.insert_one({'from_id': source, 'to_id': target,
            'from_name': str(source), 'to_name': str(target), 'type': 'trade', 'name': 'same name',
            'status': status, 'created_at': self.when, **({'group_id': group} if group else {}), **kwargs})

    async def ids(self, uid):
        return {p['other_id'] for p in await trade_pacts.trade_partners(uid)}

    async def test_group_access_is_not_transitive_and_requires_acceptance(self):
        await self.pact(1, 2, 'one')
        await self.pact(1, 3, 'one')
        await self.pact(1, 4, 'one', 'pending')
        await self.pact(5, 1, 'two')
        self.assertEqual(await self.ids(2), {1, 3})
        self.assertEqual(await self.ids(5), {1})
        self.assertEqual(await self.ids(4), set())
        self.assertTrue(await trade.has_trade_alliance(2, 3))
        self.assertFalse(await trade.has_trade_alliance(2, 5))

    async def test_leaving_removes_group_access_without_breaking_other_members(self):
        await self.pact(1, 2, 'one')
        await self.pact(1, 3, 'one')
        await self.pact(1, 4, 'one')
        await self.db.alliances.update_one({'to_id': 2}, {'$set': {'status': 'left'}})
        self.assertEqual(await self.ids(2), set())
        self.assertEqual(await self.ids(3), {1, 4})

    async def test_migration_only_merges_same_creation_batch_and_is_repeatable(self):
        await self.pact(1, 2)
        await self.pact(1, 3)
        await self.pact(1, 4, created_at=self.when + timedelta(seconds=1))
        await trade_pacts.migrate_legacy_groups()
        await trade_pacts.migrate_legacy_groups()
        self.assertEqual(await self.ids(2), {1, 3})
        self.assertEqual(await self.ids(4), {1})

    async def test_group_members_allow_route_but_other_group_does_not(self):
        await self.pact(1, 2, 'one')
        await self.pact(1, 3, 'one')
        await self.pact(5, 1, 'two')
        for uid in (1, 2, 3, 5):
            await self.db.players.insert_one({'tg_id': uid, 'name': str(uid), 'castle': str(uid)})
        with patch.object(trade, 'all_castle_terrain', AsyncMock(return_value={})), patch.object(trade, 'travel_routes', return_value=[{'path': ['2', '3', '1'], 'minutes': 10}]), patch.object(trade, 'owned_castles', side_effect=lambda p: [p['castle']]):
            self.assertTrue((await trade.caravan_route_options(2, '2', '1'))[0]['available'])
            self.assertFalse((await trade.caravan_route_options(5, '5', '1'))[0]['available'])

    async def test_delivery_retry_after_notification_failure_does_not_pay_twice(self):
        await self.db.players.insert_one({'tg_id': 2, 'resources': {'gold': 100}, 'created_at': self.when})
        await self.db.caravans.insert_one({'tg_id': 1, 'target_tg_id': 2, 'resources': {'gold': 20},
            'target_name': '2', 'player_name': '1', 'target_castle': 'B', 'origin_castle': 'A', 'active': True,
            'arrival_at': self.when, 'target_character_created_at': self.when})
        def credit(p, goods):
            p['resources']['gold'] += goods['gold']
        with patch.object(trade, 'add_resources', side_effect=credit):
            with patch.object(trade, 'send_system_message', AsyncMock(side_effect=RuntimeError('cut'))):
                with self.assertRaises(RuntimeError):
                    await trade.notify_caravan_arrivals()
            await trade.notify_caravan_arrivals()
            await trade.notify_caravan_arrivals()
        self.assertEqual((await self.db.players.find_one({'tg_id': 2}))['resources']['gold'], 120)

    async def test_old_character_cannot_receive_delivery(self):
        await self.db.players.insert_one({'tg_id': 2, 'resources': {'gold': 100}, 'created_at': self.when + timedelta(days=1)})
        await self.db.caravans.insert_one({'tg_id': 1, 'target_tg_id': 2, 'resources': {'gold': 20},
            'active': True, 'arrival_at': self.when, 'target_character_created_at': self.when})
        await trade.notify_caravan_arrivals()
        self.assertEqual((await self.db.players.find_one({'tg_id': 2}))['resources']['gold'], 100)
        self.assertTrue((await self.db.caravans.find_one({}))['delivery_failed'])
