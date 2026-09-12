import unittest
from datetime import datetime,timedelta
from unittest.mock import AsyncMock,MagicMock,patch
from army_upkeep import food_rate,campaign_food
from routers import war
import game_data as g
class Cursor:
 def __aiter__(self):return self
 async def __anext__(self):
  if not self.rows:raise StopAsyncIteration
  return self.rows.pop(0)
 def __init__(self,rows):self.rows=rows
class FoodTests(unittest.IsolatedAsyncioTestCase):
 def test_survivors_and_inactive(self):
  self.assertEqual(food_rate({'infantry':60,'ship':2}),64)
  self.assertEqual(campaign_food({'active':False,'troops':{'infantry':100},'food_per_day':100}),0)
  self.assertEqual(campaign_food({'active':True,'troops':{},'food_per_day':100}),0)
 async def test_debit_ignores_old_cached_cost(self):
  at=datetime(2026,9,12)
  collection=MagicMock();collection.find.return_value=Cursor([{'_id':1,'created_at':at-timedelta(days=1),'active':True,'troops':{'infantry':20},'food_per_day':100}]);collection.update_one=AsyncMock()
  with patch.object(war,'campaigns',collection),patch.object(war,'now',return_value=at):
   self.assertEqual((await war.apply_campaign_upkeep(1,{'food':200}))['food'],180)
   self.assertEqual(collection.update_one.call_args.args[1]['$set']['food_per_day'],20)
 def test_arbor_edges_and_sea(self):
  expected={'فیرکسل':80,'لنیسپورت':80,'اولد اوک':50,'باندالون':40,'اولد تاون':10,'استارفال':20,'سالت شور':70,'سان اسپیر':90,'لمون وود':100}
  for target,minutes in expected.items():
   self.assertEqual(g.TRAVEL_GRAPH['آربور'][target],minutes)
   self.assertEqual(g.TRAVEL_GRAPH[target]['آربور'],minutes)
   self.assertIn(frozenset(('آربور',target)),g.SEA_EDGES)
