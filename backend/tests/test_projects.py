"""Run only against the disposable project-test Mongo container, never the game DB."""
import asyncio
import copy
import os
import unittest
from contextlib import ExitStack
from datetime import datetime, timedelta, timezone
from uuid import uuid4
from unittest.mock import AsyncMock, patch
from fastapi import HTTPException
from motor.motor_asyncio import AsyncIOMotorClient
import project_engine as engine
from routers import projects as routes


@unittest.skipUnless(os.getenv('PROJECT_TEST_DB') == 'valyria_projects_test', 'requires isolated project-test database')
class ProjectIntegrationTests(unittest.IsolatedAsyncioTestCase):
    async def asyncSetUp(self):
        uri = os.environ['MONGODB_URI']
        if 'valyria-project-test-db:27017' not in uri:
            raise RuntimeError('Refusing tests outside the disposable Mongo container')
        self.client = AsyncIOMotorClient(uri)
        self.database = self.client.valyria_projects_test
        for name in ('projects', 'players', 'messages', 'admin_roles'):
            await self.database[name].delete_many({})
        self.stack = ExitStack()
        self.when = datetime(2026, 9, 6, 12)
        for mod in (engine, routes):
            for name in ('projects', 'players', 'admin_roles'):
                self.stack.enter_context(patch.object(mod, name, self.database[name]))
            self.stack.enter_context(patch.object(mod, 'now', lambda: self.when))
        self.stack.enter_context(patch.object(engine, 'messages', self.database.messages))
        self.stack.enter_context(patch.object(engine, 'apply_production', side_effect=lambda p: p))
        self.stack.enter_context(patch.object(routes, 'get_admin_role', AsyncMock(return_value=None)))
        self.stack.enter_context(patch.object(engine.telegram_bot, 'push'))
        for uid in (101, 102, 103):
            await self.database.players.insert_one({'tg_id': uid, 'name': f'Lord {uid}', 'castle': f'Castle {uid}',
                'region': 'north', 'created_at': self.when, 'last_tick': self.when,
                'resources': {'gold': 10000, 'wood': 2000}, 'buildings': {}})

    async def asyncTearDown(self):
        self.stack.close()
        self.client.close()

    def proposal(self, **changes):
        return routes.Proposal(**{'request_id': str(uuid4()), 'kind': 'shared', 'name': 'بندر آزمایشی',
            'goal': 'گسترش تجارت منطقه و تأمین چوب', 'description': 'ساخت بندر و انبار و ایجاد یک مسیر تازهٔ تجاری',
            'budget': {'gold': 1000, 'wood': 200}, 'total_shares': 100, 'owner_shares': 30,
            'period_return': {'gold': 200, 'wood': 100}, 'period_hours': 24, 'period_count': 3,
            'accepted_terms': True, **changes})

    async def create(self, **changes):
        return await routes.submit(self.proposal(**changes), {'id': 101})

    async def approve(self, doc, limit=None):
        return await routes.approve(doc['id'], routes.Approval(publish_at=(self.when + timedelta(hours=1)).replace(tzinfo=timezone.utc),
            funding_hours=48, max_shares_per_player=limit, reason='طرح تأیید شد'), {'id': 999})

    async def buy(self, doc, uid=102, qty=70, key=None):
        return await routes.buy(doc['id'], routes.Purchase(request_id=key or str(uuid4()), shares=qty), {'id': uid})

    async def resources(self, uid):
        return (await self.database.players.find_one({'tg_id': uid}))['resources']

    async def tick(self, doc):
        return await engine.tick_project(await self.database.projects.find_one({'_id': doc['id']}))

    async def test_reserve_and_reject_refund_exactly_once(self):
        proposal = self.proposal()
        p = await routes.submit(proposal, {'id': 101})
        await routes.submit(proposal, {'id': 101})
        self.assertEqual(await self.resources(101), {'gold': 9700, 'wood': 1940})
        await routes.reject(p['id'], routes.Decision(reason='طرح نیاز به اصلاح دارد'), {'id': 999})
        self.assertEqual(await self.resources(101), {'gold': 10000, 'wood': 2000})
        with self.assertRaises(HTTPException):
            await routes.reject(p['id'], routes.Decision(reason='تکرار درخواست'), {'id': 999})

    async def test_owner_cannot_buy_and_window_and_aggregate_cap(self):
        p = await self.approve(await self.create(), 10)
        with self.assertRaises(HTTPException):
            await self.buy(p, qty=1)
        self.when += timedelta(hours=1)
        with self.assertRaises(HTTPException) as e:
            await self.buy(p, uid=101, qty=1)
        self.assertEqual(e.exception.status_code, 403)
        await self.buy(p, qty=6)
        with self.assertRaises(HTTPException):
            await self.buy(p, qty=5)
        await self.buy(p, qty=4)
        self.assertEqual(await self.resources(102), {'gold': 9900, 'wood': 1980})

    async def test_timeout_investors_full_owner_half_and_no_repeat(self):
        p = await self.approve(await self.create())
        self.when += timedelta(hours=1)
        await self.buy(p, qty=10)
        self.when += timedelta(hours=48)
        result = await self.tick(p)
        self.assertEqual(result['status'], 'unfunded')
        self.assertEqual(await self.resources(101), {'gold': 9850, 'wood': 1970})
        self.assertEqual(await self.resources(102), {'gold': 10000, 'wood': 2000})
        await self.tick(p)
        self.assertEqual(await self.resources(101), {'gold': 9850, 'wood': 1970})

    async def test_full_funding_starts_clock_and_catches_up_without_duplicates(self):
        p = await self.approve(await self.create())
        self.when += timedelta(hours=2)
        active = await self.buy(p)
        self.assertEqual(active['status'], 'active')
        self.assertEqual(active['started_at'], self.when)
        self.assertEqual(await self.resources(102), {'gold': 9300, 'wood': 1860})
        await self.tick(p)
        self.assertEqual(await self.resources(102), {'gold': 9300, 'wood': 1860})
        self.when += timedelta(hours=73)
        result = await self.tick(p)
        self.assertEqual((result['status'], result['paid_periods']), ('completed', 3))
        self.assertEqual(await self.resources(102), {'gold': 9720, 'wood': 2070})
        await self.tick(p)
        self.assertEqual(await self.resources(102), {'gold': 9720, 'wood': 2070})

    async def test_failed_project_keeps_previous_payment_and_never_refunds(self):
        p = await self.approve(await self.create())
        self.when += timedelta(hours=1)
        await self.buy(p)
        self.when += timedelta(hours=24)
        await self.tick(p)
        before = await self.resources(102)
        await routes.fail(p['id'], routes.Decision(reason='بندر در جنگ از بین رفت'), {'id': 999})
        self.when += timedelta(days=5)
        result = await self.tick(p)
        self.assertEqual(result['status'], 'failed')
        self.assertEqual(await self.resources(102), before)

    async def test_owner_death_in_funding_burns_escrow_without_timeout_refund(self):
        p = await self.approve(await self.create())
        self.when += timedelta(hours=1)
        await self.buy(p, qty=10)
        await self.database.players.update_one({'tg_id': 101}, {'$set': {'is_dead': True}})
        await engine.fail_owner_projects(101)
        self.when += timedelta(days=3)
        self.assertEqual((await self.tick(p))['status'], 'failed')
        self.assertEqual(await self.resources(101), {'gold': 9700, 'wood': 1940})
        self.assertEqual(await self.resources(102), {'gold': 9900, 'wood': 1980})

    async def test_concurrent_last_shares_cannot_be_oversold(self):
        p = await self.approve(await self.create())
        self.when += timedelta(hours=1)
        results = await asyncio.gather(self.buy(p, uid=102), self.buy(p, uid=103), return_exceptions=True)
        self.assertEqual(sum(isinstance(r, HTTPException) for r in results), 1)
        stored = await self.database.projects.find_one({'_id': p['id']})
        self.assertEqual(stored['sold_shares'], 100)
        self.assertEqual(sum(m['shares'] for m in stored['members'].values()), 100)

    async def test_purchase_replay_and_crash_after_wallet_debit(self):
        p = await self.approve(await self.create())
        self.when += timedelta(hours=1)
        key = str(uuid4())
        original = engine.wallet_once
        async def debit_then_crash(*args, **kwargs):
            await original(*args, **kwargs)
            raise RuntimeError('simulated process crash after wallet commit')
        with patch.object(engine, 'wallet_once', side_effect=debit_then_crash):
            with self.assertRaises(RuntimeError):
                await self.buy(p, qty=10, key=key)
        await self.tick(p)
        await self.buy(p, qty=10, key=key)
        self.assertEqual(await self.resources(102), {'gold': 9900, 'wood': 1980})
        self.assertEqual((await self.database.projects.find_one({'_id': p['id']}))['sold_shares'], 40)

    async def test_payout_crash_mid_settlement_replays_without_double_credit(self):
        p = await self.approve(await self.create())
        self.when += timedelta(hours=1)
        await self.buy(p)
        self.when += timedelta(hours=24)
        original = engine.wallet_once
        calls = 0
        async def crash(*args, **kwargs):
            nonlocal calls
            await original(*args, **kwargs)
            calls += 1
            if calls == 1:
                raise RuntimeError('simulated crash after first shareholder credit')
        with patch.object(engine, 'wallet_once', side_effect=crash):
            with self.assertRaises(RuntimeError):
                await self.tick(p)
        await self.tick(p)
        self.assertEqual(await self.resources(101), {'gold': 9760, 'wood': 1970})
        self.assertEqual(await self.resources(102), {'gold': 9440, 'wood': 1930})

    async def test_insufficient_wallet_does_not_create_free_shares(self):
        p = await self.approve(await self.create())
        self.when += timedelta(hours=1)
        await self.database.players.update_one({'tg_id': 102}, {'$set': {'resources': {'gold': 0, 'wood': 0}}})
        with self.assertRaises(HTTPException):
            await self.buy(p)
        stored = await self.database.projects.find_one({'_id': p['id']})
        self.assertEqual(stored['sold_shares'], 30)
        self.assertNotIn('purchase_intent', stored)

    async def test_personal_project_needs_no_investors(self):
        p = await self.approve(await self.create(kind='personal', owner_shares=100))
        self.when += timedelta(hours=1)
        self.assertEqual((await self.tick(p))['status'], 'active')
        self.when += timedelta(hours=24)
        await self.tick(p)
        self.assertEqual(await self.resources(101), {'gold': 9200, 'wood': 1900})

    async def test_custom_notice_is_complete_and_does_not_change_rules(self):
        p = await self.create()
        result = await routes.approve(p['id'], routes.Approval(publish_at=(self.when + timedelta(hours=1)).replace(tzinfo=timezone.utc),
            funding_hours=48, reason='تأیید طرح بندر', notification_terms='شرایط روایی اختصاصی این بندر؛ قوانین ثابت بازی برقرارند.'), {'id': 999})
        doc = await self.database.projects.find_one({'_id': p['id']})
        text = engine.announcement(doc)
        self.assertIn('شرایط روایی اختصاصی', text)
        self.assertNotIn('معاف', text)
        self.assertLessEqual(len(text), 3900)
        await engine.flush_notices()
        count = await self.database.messages.count_documents({'kind': 'project'})
        await engine.flush_notices()
        self.assertEqual(await self.database.messages.count_documents({'kind': 'project'}), count)
        self.assertEqual((await routes.rules({'id': 101}))['terms'], engine.TERMS)

    async def test_new_character_never_receives_previous_character_payout(self):
        p = await self.approve(await self.create())
        self.when += timedelta(hours=1)
        await self.buy(p)
        await self.database.players.update_one({'tg_id': 102}, {'$set': {'created_at': self.when, 'resources': {'gold': 10, 'wood': 0}}})
        self.when += timedelta(hours=24)
        await self.tick(p)
        self.assertEqual(await self.resources(102), {'gold': 10, 'wood': 0})

    async def test_visibility_before_publication_and_divisibility_validation(self):
        with self.assertRaises(HTTPException):
            await self.create(budget={'gold': 1001})
        p = await self.approve(await self.create())
        self.assertEqual(await routes.listing(False, {'id': 102}), [])
        self.assertEqual(len(await routes.listing(True, {'id': 101})), 1)
        self.when += timedelta(hours=1)
        self.assertEqual(len(await routes.listing(False, {'id': 102})), 1)
