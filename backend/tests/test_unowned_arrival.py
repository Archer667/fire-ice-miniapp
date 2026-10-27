import unittest
from datetime import datetime
from unittest.mock import AsyncMock, patch
from bson import ObjectId
from routers import war
from mongomock_motor import AsyncMongoMockClient

class UnownedArrival(unittest.IsolatedAsyncioTestCase):
    async def test_attack_to_unowned_castle_stations_without_dossier_or_score(self):
        at = datetime(2026,10,8)
        army = {'_id':ObjectId(), 'tg_id':1, 'player_name':'Player', 'active':True,
                'origin_castle':'A', 'target_castle':'هارنهال', 'op_type':'attack',
                'arrival_at':at, 'troops':{'infantry':100}, 'name':'red9'}
        store = AsyncMongoMockClient()['unowned_arrival_test'].campaigns
        await store.insert_one(army)
        with patch.object(war,'campaigns',store), patch.object(war,'now',return_value=at), \
             patch.object(war,'owner_of_castle',AsyncMock(return_value=None)), \
             patch.object(war,'send_system_message',AsyncMock()), \
             patch.object(war,'reconcile_battle_locks',AsyncMock()), \
             patch.object(war,'repair_open_battle_rosters',AsyncMock()), \
             patch.object(war,'process_route_ambushes',AsyncMock()), \
             patch.object(war,'detect_route_encounters',AsyncMock()), \
             patch.object(war,'notify_battle_admins',AsyncMock()) as notify:
            await war.notify_arrivals()
        army = await store.find_one({'_id':army['_id']})
        self.assertEqual(army['op_type'],'garrison')
        self.assertFalse(army['engagement_locked'])
        self.assertTrue(army['arrival_notified'])
        self.assertNotIn('engagement_campaign_id',army)
        self.assertNotIn('winner_tg_id',army)
        self.assertFalse(war.campaign_waiting_for_result(army))
        notify.assert_not_awaited()
