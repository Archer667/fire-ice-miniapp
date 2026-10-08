import unittest
from datetime import datetime, timedelta
from unittest.mock import patch, AsyncMock
from routers import admin, war


class ExplicitRetreat(unittest.IsolatedAsyncioTestCase):
    def army(self):
        t = datetime(2026, 9, 27)
        return {'tg_id': 2, 'origin_castle': 'A', 'target_castle': 'B',
                'route_path': ['A', 'B'], 'route_edge_minutes': [30],
                'created_at': t, 'arrival_at': t + timedelta(minutes=30),
                'battle_started_at': t + timedelta(hours=1), 'troops': {'infantry': 10}}

    async def test_selected_destination_overrides_recorded_origin(self):
        at = datetime(2026, 9, 27, 2)
        with patch.object(war, 'all_castle_names_and_ports', AsyncMock(return_value=({'A','B','C'}, set()))), \
             patch.object(war, 'all_castle_terrain', AsyncMock(return_value={})), \
             patch.object(war, 'travel_routes', return_value=[{'path':['B','C'], 'minutes':20}]), \
             patch.object(war, 'TRAVEL_GRAPH', {'B':{'C':20}}), \
             patch.object(war, 'rule', side_effect=lambda k,d:d):
            plan = await admin._plan_battle_return(self.army(), 'battle', at, False, {'2':'C'})
        self.assertEqual(plan['target_castle'], 'C')
        self.assertEqual(plan['route_path'], ['B','C'])
        self.assertEqual(plan['travel_minutes'], 20)

    async def test_invalid_destination_does_not_fall_back(self):
        with patch.object(war, 'all_castle_names_and_ports', AsyncMock(return_value=({'A','B'}, set()))):
            with self.assertRaises(ValueError):
                await admin._plan_battle_return(self.army(), 'battle', datetime(2026,9,27,2), False, {'2':'missing'})

    async def test_road_retreat_keeps_physical_start(self):
        point = {'a':'A','b':'B','position':.25,'base_minutes':40}
        army = {**self.army(), 'target_castle':'road', 'stationed_edge':point}
        with patch.object(war, 'all_castle_names_and_ports', AsyncMock(return_value=({'A','B'}, set()))), \
             patch.object(war, 'all_castle_terrain', AsyncMock(return_value={})), \
             patch.object(war, 'rule', side_effect=lambda k,d:d):
            plan = await admin._plan_battle_return(army, 'battle', datetime(2026,9,27,2), False, {'2':'B'})
        self.assertEqual(plan['target_castle'], 'B')
        self.assertEqual(plan['route_start_position'], point)
        self.assertEqual(plan['travel_minutes'], 30)

    async def test_cancelled_battle_keeps_original_return(self):
        plan = await admin._plan_battle_return(self.army(), 'battle', datetime(2026,9,27,2), True, {'2':'C'})
        self.assertEqual(plan['target_castle'], 'A')

