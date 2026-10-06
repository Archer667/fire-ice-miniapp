"""Inventory, production timing and administrator endpoints without a live DB."""
import copy
import unittest
from datetime import datetime, timedelta
from types import SimpleNamespace
from unittest.mock import patch, AsyncMock
from bson import ObjectId
from fastapi import HTTPException
import game
import db
from item_effects import building_item_percent, select_war_items, character_matches
from routers import admin, assets, projects
from game_data import BUILDINGS, building_produces


def matches(row, query):
    for key, expected in query.items():
        if isinstance(expected, dict):
            if '$in' in expected:
                actual = row.get(key)
                if not any(x in expected['$in'] for x in (actual if isinstance(actual, list) else [actual])):
                    return False
            elif '$ne' in expected and row.get(key) == expected['$ne']:
                return False
        elif isinstance(row.get(key), list):
            if expected not in row[key]:
                return False
        elif row.get(key) != expected:
            return False
    return True


class Cursor:
    def __init__(self, rows): self.rows = copy.deepcopy(rows)
    def sort(self, *args): return self
    def __aiter__(self): self.it = iter(self.rows); return self
    async def __anext__(self):
        try: return next(self.it)
        except StopIteration: raise StopAsyncIteration
    async def to_list(self, *args): return self.rows


class Collection:
    def __init__(self, rows=()): self.rows = copy.deepcopy(list(rows))
    def find(self, query): return Cursor([r for r in self.rows if matches(r, query)])
    async def find_one(self, query): return copy.deepcopy(next((r for r in self.rows if matches(r, query)), None))
    async def insert_one(self, row):
        row = copy.deepcopy(row); row.setdefault('_id', ObjectId()); self.rows.append(row)
        return SimpleNamespace(inserted_id=row['_id'])
    async def update_one(self, query, update):
        row = next((r for r in self.rows if matches(r, query)), None)
        if row is None: return SimpleNamespace(modified_count=0)
        for op, fields in update.items():
            for key, value in fields.items():
                target = row; parts = key.split('.')
                for part in parts[:-1]: target = target.setdefault(part, {})
                if op == '$set': target[parts[-1]] = copy.deepcopy(value)
                elif op == '$unset': target.pop(parts[-1], None)
        return SimpleNamespace(modified_count=1)
    async def delete_one(self, query):
        old = len(self.rows); self.rows = [r for r in self.rows if not matches(r, query)]
        return SimpleNamespace(deleted_count=old-len(self.rows))
    async def delete_many(self, query): return await self.delete_one(query)


class ProductionTests(unittest.TestCase):
    def setUp(self):
        self.at = datetime(2026, 10, 5)
        self.bid = next(b for b in BUILDINGS if building_produces(b))
        self.player = {'tg_id': 1, 'created_at': self.at, 'last_tick': self.at, 'castle': 'وینترفل',
                       'resources': {'men': 0, 'gold': 0}, 'tax_rate': 0,
                       'buildings': {self.bid: {'level': 2}}, 'item_effects': {}}
    def effect(self, start, end=None, percent=15):
        return {'building_id': self.bid, 'percent': percent, 'starts_at': start, 'expires_at': end,
                'character_created_at': self.at, 'character_child_id': None}
    def test_percent_stacks_only_on_selected_building(self):
        self.player['item_effects'] = {'a': self.effect(self.at), 'b': self.effect(self.at, percent=10)}
        with patch('game.now', return_value=self.at):
            yields = game.effective_building_produces(self.player, self.bid)
        for key, value in building_produces(self.bid).items(): self.assertAlmostEqual(yields[key], value * 1.25)
        self.assertEqual(building_item_percent(self.player, 'different', self.at), 0)
    def test_start_and_expiration_split_elapsed_production(self):
        self.player['item_effects'] = {'a': self.effect(self.at + timedelta(hours=6), self.at + timedelta(hours=18))}
        clean = copy.deepcopy(self.player); clean['item_effects'] = {}
        with patch('game.now', return_value=self.at + timedelta(days=1)), patch('game.effective_caps', return_value={}):
            game.apply_production(self.player); game.apply_production(clean)
        for key, value in building_produces(self.bid).items():
            self.assertAlmostEqual(self.player['resources'][key] - clean['resources'][key], value * 2 * .15 * .5)
    def test_no_retroactive_bonus_and_no_expired_bonus(self):
        self.player['item_effects'] = {'a': self.effect(self.at + timedelta(hours=1), self.at + timedelta(hours=2))}
        self.assertEqual(building_item_percent(self.player, self.bid, self.at), 0)
        self.assertEqual(building_item_percent(self.player, self.bid, self.at + timedelta(hours=2)), 0)
    def test_heir_does_not_inherit_effect(self):
        self.player['item_effects'] = {'a': self.effect(self.at)}
        self.player['family_child_id'] = 'new-heir'
        self.assertEqual(building_item_percent(self.player, self.bid, self.at), 0)
    def test_population_project_budget_and_return_allowed(self):
        self.assertEqual(projects.validate_basket({'men': 200, 'wood': 100}), {'men': 200, 'wood': 100})
        with self.assertRaises(HTTPException): projects.validate_basket({'men': -1})


class InventoryTests(unittest.IsolatedAsyncioTestCase):
    def setUp(self):
        self.at = datetime(2026, 10, 5)
        self.bid = next(b for b in BUILDINGS if building_produces(b))
        self.player = {'tg_id': 1, 'name': 'Player', 'created_at': self.at, 'castle': 'وینترفل',
                       'last_tick': self.at, 'resources': {'men': 500, 'gold': 500}, 'buildings': {}}
        self.tpl = {'_id': ObjectId(), 'name': 'Sword', 'type': 'war', 'duration': 'permanent', 'color': 'legendary'}
        self.grant = {'_id': ObjectId(), 'item_id': self.tpl['_id'], 'tg_id': 1, 'granted_at': self.at,
                      'character_created_at': self.at, 'character_child_id': None, 'color': 'legendary'}
        self.players = Collection([self.player]); self.items = Collection([self.tpl]); self.grants = Collection([self.grant]); self.campaigns = Collection()
        for module in (db, admin, assets):
            for key, collection in [('players',self.players),('items',self.items),('item_grants',self.grants),('campaigns',self.campaigns)]:
                if hasattr(module,key): self.enterContext(patch.object(module,key,collection))
        self.enterContext(patch('game.now', return_value=self.at))
        self.enterContext(patch.object(admin,'now',return_value=self.at))
        self.enterContext(patch.object(assets,'now',return_value=self.at))
        self.enterContext(patch.object(admin,'send_system_message',new=AsyncMock()))
    async def test_war_item_selection_blocks_duplicates_foreign_expired_and_economic(self):
        ids = [str(self.grant['_id'])]
        self.assertEqual((await select_war_items(self.player, ids))[0]['name'], 'Sword')
        with self.assertRaises(HTTPException): await select_war_items(self.player, ids * 2)
        with self.assertRaises(HTTPException): await select_war_items({'tg_id': 2}, ids)
        self.grants.rows[0]['expires_at'] = self.at
        with self.assertRaises(HTTPException): await select_war_items(self.player, ids)
        self.grants.rows[0].pop('expires_at'); self.items.rows[0]['type'] = 'economy'
        with self.assertRaises(HTTPException): await select_war_items(self.player, ids)
    async def test_active_army_reserves_item_and_closing_releases_it(self):
        self.campaigns.rows.append({'_id': ObjectId(), 'active': True, 'item_ids': [str(self.grant['_id'])]})
        with self.assertRaises(HTTPException) as error: await select_war_items(self.player,[str(self.grant['_id'])])
        self.assertEqual(error.exception.status_code, 409)
        self.campaigns.rows[0]['active'] = False
        self.assertEqual(len(await select_war_items(self.player,[str(self.grant['_id'])])), 1)
    async def test_delete_in_use_item_rejected_without_changing_inventory(self):
        self.campaigns.rows.append({'active': True, 'item_ids': [str(self.grant['_id'])]})
        with self.assertRaises(HTTPException): await admin.admin_delete_item(str(self.tpl['_id']), {'id': 9})
        self.assertEqual(len(self.items.rows),1); self.assertEqual(len(self.grants.rows),1)
    async def test_grant_retry_is_idempotent_and_effect_removed_on_delete(self):
        self.items.rows[0].update(type='economy',building_id=self.bid,yield_percent=15)
        body = admin.ItemGrantBody(tg_id=1,request_id='69f56554-90d6-4900-b743-9925f65bff91')
        await admin.admin_grant_item(str(self.tpl['_id']),body,{'id':9})
        await admin.admin_grant_item(str(self.tpl['_id']),body,{'id':9})
        self.assertEqual(len(self.grants.rows),2)
        self.assertEqual(len(self.players.rows[0]['item_effects']),1)
        self.assertAlmostEqual(building_item_percent(self.players.rows[0],self.bid,self.at),15)
        await admin.admin_delete_item(str(self.tpl['_id']),{'id':9})
        self.assertEqual(self.players.rows[0]['item_effects'],{})
        self.assertEqual(self.grants.rows,[])
    async def test_invalid_effect_rejected_before_item_created(self):
        for percent, bid, kind in [(-1,self.bid,'economy'),(float('nan'),self.bid,'economy'),(15,self.bid,'war'),(15,'missing','economy')]:
            with self.subTest(percent=percent,bid=bid,kind=kind), self.assertRaises(HTTPException):
                await admin.admin_create_item(admin.ItemBody(name='Test',type=kind,duration='permanent',building_id=bid,yield_percent=percent),{'id':9})
        self.assertEqual(len(self.items.rows),1)
    async def test_heir_cannot_equip_previous_character_item(self):
        self.player['family_child_id'] = 'new-heir'
        with self.assertRaises(HTTPException): await select_war_items(self.player,[str(self.grant['_id'])])
    async def test_expired_inventory_hidden_and_utc_times_returned(self):
        self.grants.rows[0]['expires_at'] = self.at + timedelta(hours=1)
        output = await assets.my_items({'id': 1})
        self.assertTrue(output[0]['expires_at'].endswith('Z'))
        self.grants.rows[0]['expires_at'] = self.at
        self.assertEqual(await assets.my_items({'id': 1}), [])
    async def test_interrupted_grant_recovers_once(self):
        from item_effects import recover_item_effects
        self.grants.rows[0].update(effect_pending=True, effect={'building_id': self.bid, 'percent': 15,
                                  'starts_at': self.at, 'character_created_at': self.at, 'character_child_id': None})
        await recover_item_effects(); await recover_item_effects()
        self.assertEqual(len(self.players.rows[0]['item_effects']), 1)
        self.assertAlmostEqual(building_item_percent(self.players.rows[0], self.bid, self.at), 15)
