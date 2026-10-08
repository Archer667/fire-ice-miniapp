import unittest
from datetime import datetime
from unittest.mock import AsyncMock, patch
from bson import ObjectId
from routers import war

class Cursor:
    def __init__(self, rows): self.rows = rows
    def sort(self, *args): return self
    def __aiter__(self): self.iterator = iter(self.rows); return self
    async def __anext__(self):
        try: return next(self.iterator)
        except StopIteration: raise StopAsyncIteration

class Store:
    def __init__(self, army): self.army = army; self.updates = []
    def find(self, q): return Cursor([] if q.get('_id') else [self.army])
    async def find_one(self, q): return self.army if q.get('_id') == self.army['_id'] else None
    async def update_one(self, q, update):
        self.updates.append(update); self.army.update(update.get('$set', {}))

class UnownedArrival(unittest.IsolatedAsyncioTestCase):
    async def test_attack_to_unowned_castle_stations_without_dossier_or_score(self):
        at = datetime(2026,10,8)
        army = {'_id':ObjectId(), 'tg_id':1, 'player_name':'Player', 'active':True,
                'origin_castle':'A', 'target_castle':'هارنهال', 'op_type':'attack',
                'arrival_at':at, 'troops':{'infantry':100}, 'name':'red9'}
        store = Store(army)
        with patch.object(war,'campaigns',store), patch.object(war,'now',return_value=at), \
             patch.object(war,'owner_of_castle',AsyncMock(return_value=None)), \
             patch.object(war,'send_system_message',AsyncMock()), \
             patch.object(war,'reconcile_battle_locks',AsyncMock()), \
             patch.object(war,'repair_open_battle_rosters',AsyncMock()), \
             patch.object(war,'process_route_ambushes',AsyncMock()), \
             patch.object(war,'detect_route_encounters',AsyncMock()), \
             patch.object(war,'notify_battle_admins',AsyncMock()) as notify:
            await war.notify_arrivals()
        self.assertEqual(army['op_type'],'garrison')
        self.assertFalse(army['engagement_locked'])
        self.assertTrue(army['arrival_notified'])
        self.assertNotIn('engagement_campaign_id',army)
        self.assertNotIn('winner_tg_id',army)
        self.assertFalse(war.campaign_waiting_for_result(army))
        notify.assert_not_awaited()
