"""Lifecycle regression tests with an isolated in-memory database (no live game writes)."""
import copy
import unittest
from contextlib import ExitStack
from types import SimpleNamespace
from unittest.mock import AsyncMock, patch

from bson import ObjectId
from fastapi import HTTPException
from starlette.requests import Request
import auth
from game import now, apply_production
from ranks import base_score
from routers import admin, leaderboard, players as player_routes, war


MISSING = object()


def value(doc, key):
    for part in key.split('.'):
        if not isinstance(doc, dict) or part not in doc:
            return MISSING
        doc = doc[part]
    return doc


def matches(doc, query):
    for key, wanted in query.items():
        if key == '$or':
            if not any(matches(doc, sub) for sub in wanted):
                return False
            continue
        actual = value(doc, key)
        if isinstance(wanted, dict):
            for op, arg in wanted.items():
                if op == '$ne' and actual == arg:
                    return False
                if op == '$exists' and (actual is not MISSING) != arg:
                    return False
                if op == '$in' and actual not in arg:
                    return False
        elif actual != wanted and not (wanted is None and actual is MISSING):
            return False
    return True


class Cursor:
    def __init__(self, rows):
        self.rows = copy.deepcopy(rows)

    def __aiter__(self):
        self.iterator = iter(self.rows)
        return self

    async def __anext__(self):
        try:
            return next(self.iterator)
        except StopIteration:
            raise StopAsyncIteration

    async def to_list(self, length):
        return self.rows if length is None else self.rows[:length]

    def sort(self, *args):
        return self


class Collection:
    def __init__(self, rows=()):
        self.rows = copy.deepcopy(list(rows))

    def find(self, query, projection=None):
        return Cursor([r for r in self.rows if matches(r, query)])

    async def find_one(self, query, projection=None):
        return next((copy.deepcopy(r) for r in self.rows if matches(r, query)), None)

    async def update_one(self, query, update):
        return await self._update(query, update, one=True)

    async def update_many(self, query, update):
        return await self._update(query, update)

    async def count_documents(self, query):
        return sum(matches(r, query) for r in self.rows)

    async def _update(self, query, update, one=False):
        count = 0
        for row in self.rows:
            if not matches(row, query):
                continue
            count += 1
            for op, changes in update.items():
                for key, val in changes.items():
                    parts = key.split('.')
                    dest = row
                    for part in parts[:-1]:
                        dest = dest.setdefault(part, {})
                    leaf = parts[-1]
                    if op == '$set':
                        dest[leaf] = copy.deepcopy(val)
                    elif op == '$unset':
                        dest.pop(leaf, None)
                    elif op == '$inc':
                        dest[leaf] = dest.get(leaf, 0) + val
                    elif op == '$pull':
                        dest[leaf] = [x for x in dest.get(leaf, []) if not (matches(x, val) if isinstance(val, dict) else x == val)]
                    else:
                        raise AssertionError(op)
            if one:
                break
        return SimpleNamespace(matched_count=count, modified_count=count)


def player(tg_id, castle, extra=None):
    return {
        'tg_id': tg_id, 'name': f'Lord {tg_id}', 'title': 'Lord',
        'castle': castle, 'region': 'north', 'house': 'house',
        'castle_buildings': extra or {}, 'buildings': {'farm': 3},
        'resources': {'gold': 100, 'wood': 75}, 'troops': {'sword': 20},
        'equipment': {'ram': 2}, 'points': 100, 'popularity': 50,
        'created_at': now(), 'last_tick': now(),
    }


class PlayerDeathTests(unittest.IsolatedAsyncioTestCase):
    def setUp(self):
        self.stack = ExitStack()
        self.addCleanup(self.stack.close)
        self.people = Collection([player(1, 'A', {'B': {'mine': 4}}), player(2, 'C'), player(3, 'D')])
        self.armies = Collection()
        self.ambushes = Collection()
        self.roles = Collection()
        for mod in (admin, auth, leaderboard, player_routes, war):
            self.stack.enter_context(patch.object(mod, 'players', self.people))
        self.stack.enter_context(patch.object(admin, 'campaigns', self.armies))
        self.stack.enter_context(patch.object(admin, 'ambushes', self.ambushes))
        self.stack.enter_context(patch.object(admin, 'roleplays', self.roles))
        self.stack.enter_context(patch.object(admin, 'hierarchy', Collection()))
        self.stack.enter_context(patch.object(admin, 'get_hierarchy_doc', AsyncMock(return_value={})))
        self.stack.enter_context(patch.object(admin, 'get_admin_role', AsyncMock(return_value=None)))
        self.stack.enter_context(patch.object(admin, 'send_system_message', AsyncMock()))
        self.stack.enter_context(patch.object(admin, 'apply_production', side_effect=lambda p: p))
        self.stack.enter_context(patch.object(admin, '_castle_region_map', AsyncMock(return_value={'A': 'north', 'B': 'west', 'C': 'north', 'D': 'north'})))
        self.stack.enter_context(patch.object(admin, 'all_castle_terrain', AsyncMock(return_value={})))
        self.capture_stat = self.stack.enter_context(patch.object(admin, 'bump_player_stat', AsyncMock()))

    async def test_voluntary_death_splits_castles_without_capture_or_resource_transfer(self):
        before = await self.people.find_one({'tg_id': 1})
        await admin.admin_player_death(1, admin.DeathTransferBody(transfers={'A': 2, 'B': 3}), {})
        dead = await self.people.find_one({'tg_id': 1})
        self.assertTrue(dead['is_dead'])
        self.assertIsNone(dead['castle'])
        self.assertEqual(dead['resources'], before['resources'])
        self.assertEqual(dead['death_snapshot']['score'], round(base_score(before)))
        self.assertEqual((await self.people.find_one({'tg_id': 2}))['castle_buildings'], {'A': {'farm': 3}})
        self.assertEqual((await self.people.find_one({'tg_id': 3}))['castle_buildings'], {'B': {'mine': 4}})
        self.assertEqual((await self.people.find_one({'tg_id': 2}))['points'], 100)
        self.capture_stat.assert_not_awaited()

    async def test_invalid_plan_does_not_partially_transfer(self):
        before = copy.deepcopy(self.people.rows)
        for transfers in ({'A': 2}, {'A': 2, 'B': 1}, {'A': 2, 'B': 999}):
            with self.assertRaises(HTTPException):
                await admin.admin_player_death(1, admin.DeathTransferBody(transfers=transfers), {})
            self.assertEqual(self.people.rows, before)

    async def test_capture_promotes_remaining_castle_and_updates_region(self):
        await admin.admin_add_castle(2, admin.AddCastleBody(castle='A'), {})
        old = await self.people.find_one({'tg_id': 1})
        self.assertEqual((old['castle'], old['region'], old['buildings']), ('B', 'west', {'mine': 4}))
        self.assertFalse(old.get('is_dead', False))
        self.assertEqual(old['resources'], {'gold': 100, 'wood': 75})
        self.capture_stat.assert_awaited_once_with(2, 'castles_captured')

    async def test_last_castle_capture_kills_and_preserves_score(self):
        self.people.rows[0]['castle_buildings'] = {}
        before = copy.deepcopy(self.people.rows[0])
        await admin.admin_add_castle(2, admin.AddCastleBody(castle='A'), {})
        dead = await self.people.find_one({'tg_id': 1})
        self.assertTrue(dead['is_dead'])
        self.assertEqual(dead['death_snapshot']['score'], round(base_score(before)))
        self.assertEqual((await self.people.find_one({'tg_id': 2}))['castle_buildings']['A'], before['buildings'])
        self.capture_stat.assert_awaited_once()

    async def test_death_destroys_armies_and_ambush_without_refund(self):
        self.armies.rows = [{'_id': ObjectId(), 'tg_id': 1, 'active': True, 'troops': {'sword': 8}, 'equipment': {'ram': 1}}]
        self.ambushes.rows = [{'tg_id': 1, 'status': 'active', 'troops': {'sword': 5}}]
        await admin.admin_player_death(1, admin.DeathTransferBody(transfers={'A': 2, 'B': 2}), {})
        army = self.armies.rows[0]
        self.assertFalse(army['active'])
        self.assertEqual((army['status'], army['troops'], army['equipment']), ('destroyed', {}, {}))
        self.assertEqual(self.ambushes.rows[0]['status'], 'cancelled')
        dead = await self.people.find_one({'tg_id': 1})
        self.assertEqual(dead['troops'], {})
        self.assertEqual(dead['resources'], {'gold': 100, 'wood': 75})

    async def test_duplicate_death_rejected_and_no_duplicate_awards(self):
        body = admin.DeathTransferBody(transfers={'A': 2, 'B': 3})
        await admin.admin_player_death(1, body, {})
        before = copy.deepcopy(self.people.rows)
        with self.assertRaises(HTTPException):
            await admin.admin_player_death(1, body, {})
        self.assertEqual(self.people.rows, before)

    async def test_dead_auth_cannot_act_but_can_read_me(self):
        self.people.rows[0]['is_dead'] = True
        with patch.object(auth, 'DEV_MODE', True), patch.object(auth, 'get_admin_role', AsyncMock(return_value=None)):
            for path in ('/api/war/launch', '/api/players/register', '/api/trade/send', '/api/ravens/send'):
                with self.assertRaises(HTTPException) as caught:
                    await auth.get_user(Request({'type': 'http', 'path': path, 'headers': []}), '', '1:Lord')
                self.assertEqual(caught.exception.headers['X-Player-Dead'], '1')
            user = await auth.get_user(Request({'type': 'http', 'path': '/api/players/me', 'headers': []}), '', '1:Lord')
            self.assertEqual(user['id'], 1)

    async def test_unassign_dead_opens_fresh_registration(self):
        await admin.admin_player_death(1, admin.DeathTransferBody(transfers={'A': 2, 'B': 3}), {})
        await admin.admin_unassign_house(1, {})
        p = await self.people.find_one({'tg_id': 1})
        self.assertFalse(p['is_dead'])
        self.assertTrue(p['registration_reset'])
        with patch.object(player_routes, 'get_admin_role', AsyncMock(return_value=None)):
            self.assertEqual(await player_routes.me({'id': 1}), {'registered': False})

    async def test_http_dependency_blocks_dead_character(self):
        import httpx
        from fastapi import FastAPI, Depends
        app = FastAPI()

        @app.post('/api/test-action')
        async def action(user=Depends(auth.get_user)):
            return {'ok': True}

        self.people.rows[0]['is_dead'] = True
        with patch.object(auth, 'DEV_MODE', True), patch.object(auth, 'get_admin_role', AsyncMock(return_value=None)):
            async with httpx.AsyncClient(transport=httpx.ASGITransport(app=app), base_url='http://test') as client:
                result = await client.post('/api/test-action', headers={'X-Dev-User': '1:Lord'})
        self.assertEqual(result.status_code, 403)
        self.assertEqual(result.headers['X-Player-Dead'], '1')

    async def test_dead_board_uses_frozen_score_and_castle(self):
        await admin.admin_player_death(1, admin.DeathTransferBody(transfers={'A': 2, 'B': 3}), {})
        rows = await leaderboard.with_dead_players([])
        self.assertEqual(len(rows), 1)
        self.assertTrue(rows[0]['player']['is_dead'])
        self.assertEqual(rows[0]['player']['castle'], 'A')
        self.assertGreater(rows[0]['score'], 0)
        dead = await self.people.find_one({'tg_id': 1})
        self.assertEqual(apply_production(copy.deepcopy(dead)), dead)

    async def test_death_removes_only_its_army_from_group_battle(self):
        a, b, d = ObjectId(), ObjectId(), ObjectId()
        battle_id = str(a)
        self.armies.rows = [
            {'_id': a, 'tg_id': 1, 'active': True, 'battle_is_root': True, 'battle_open': True,
             'engagement_campaign_id': battle_id, 'engagement_locked': True,
             'battle_attacker_army_ids': [str(a), str(b)], 'battle_defender_army_ids': [str(d)],
             'battle_location': 'D', 'battle_defender_tg_id': 3},
            {'_id': b, 'tg_id': 2, 'active': True, 'engagement_campaign_id': battle_id, 'engagement_locked': True},
            {'_id': d, 'tg_id': 3, 'active': True, 'engagement_campaign_id': battle_id, 'engagement_locked': True},
        ]
        await admin.admin_player_death(1, admin.DeathTransferBody(transfers={'A': 2, 'B': 2}), {})
        root = self.armies.rows[0]
        self.assertEqual(root['battle_attacker_army_ids'], [str(b)])
        self.assertTrue(root['battle_open'])
        self.assertFalse(root['active'])
        self.assertNotIn(1, root['battle_participant_tg_ids'])
        self.assertTrue(self.armies.rows[1]['active'])
        self.assertTrue(self.armies.rows[1]['engagement_locked'])

    async def test_last_attacking_army_death_closes_battle_without_destroying_opponent(self):
        a, d = ObjectId(), ObjectId()
        battle_id = str(a)
        self.armies.rows = [
            {'_id': a, 'tg_id': 1, 'active': True, 'battle_is_root': True, 'battle_open': True,
             'engagement_campaign_id': battle_id, 'engagement_locked': True,
             'battle_attacker_army_ids': [str(a)], 'battle_defender_army_ids': [str(d)],
             'battle_location': 'D', 'battle_defender_tg_id': 3},
            {'_id': d, 'tg_id': 3, 'active': True, 'engagement_campaign_id': battle_id, 'engagement_locked': True},
        ]
        await admin.admin_player_death(1, admin.DeathTransferBody(transfers={'A': 2, 'B': 2}), {})
        self.assertFalse(self.armies.rows[0]['battle_open'])
        self.assertTrue(self.armies.rows[1]['active'])
        self.assertFalse(self.armies.rows[1]['engagement_locked'])


if __name__ == '__main__':
    unittest.main()
