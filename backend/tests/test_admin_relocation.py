import unittest
from types import SimpleNamespace
from unittest.mock import AsyncMock, patch
from bson import ObjectId
from fastapi import HTTPException
from routers import admin, war


class Relocation(unittest.IsolatedAsyncioTestCase):
    async def call(self, *, engaged=False, confirm=False, destination='C', group=None):
        army = {'_id': ObjectId(), 'tg_id': 2, 'active': True, 'name': 'north',
                'target_castle': 'B', 'origin_castle': 'A', 'troops': {'infantry': 10},
                'engagement_locked': engaged, 'merge_group_id': group}
        database = SimpleNamespace(find_one=AsyncMock(return_value=army),
                                   update_one=AsyncMock(return_value=SimpleNamespace(matched_count=1)))
        detach = AsyncMock(return_value={'removed': engaged, 'battle_closed': False})
        with patch.object(admin, 'campaigns', database), \
             patch.object(admin, 'players', SimpleNamespace(find_one=AsyncMock(return_value=None))), \
             patch.object(war, 'all_castle_names_and_ports', AsyncMock(return_value=({'A','B','C'}, set()))), \
             patch.object(admin, '_remove_campaign_from_battle', detach):
            try:
                result = await admin._relocate_campaign(str(army['_id']), admin.RelocateCampaignBody(destination=destination, confirm_battle_exit=confirm), {'id': 1})
            except HTTPException as exc:
                return exc, database, detach, army
        return result, database, detach, army

    async def test_instant_move_preserves_inventory(self):
        result, db, detach, army = await self.call()
        self.assertTrue(result['ok'])
        update = db.update_one.call_args.args[1]
        self.assertEqual(update['$set']['target_castle'], 'C')
        self.assertEqual(update['$set']['travel_minutes'], 0)
        self.assertEqual(update['$set']['route_path'], ['C'])
        self.assertNotIn('troops', update['$set'])
        self.assertNotIn('equipment', update['$set'])
        self.assertEqual(army['troops']['infantry'], 10)
        self.assertEqual(update['$push']['movement_history']['reason'], 'admin_relocation')

    async def test_battle_needs_separate_confirmation(self):
        result, db, detach, _ = await self.call(engaged=True)
        self.assertEqual(result.status_code, 409)
        db.update_one.assert_not_awaited(); detach.assert_not_awaited()

    async def test_confirmed_battle_detaches_before_move(self):
        result, db, detach, _ = await self.call(engaged=True, confirm=True)
        self.assertTrue(result['ok']); detach.assert_awaited_once(); db.update_one.assert_awaited_once()

    async def test_invalid_destination_and_shared_army_do_not_mutate(self):
        for kwargs in ({'destination':'missing'}, {'group':'shared'}):
            result, db, detach, _ = await self.call(**kwargs)
            self.assertIsInstance(result, HTTPException)
            db.update_one.assert_not_awaited(); detach.assert_not_awaited()

