import unittest
from datetime import datetime,timedelta
from battle_returns import return_plan
from encounter_geometry import legs

class Returns(unittest.TestCase):
 def test_castle_returns_whole_route(self):
  t=datetime(2026,9,27);a={'origin_castle':'A','target_castle':'C','created_at':t,'arrival_at':t+timedelta(minutes=60),'route_path':['A','B','C'],'route_edge_minutes':[20,40],'battle_started_at':t+timedelta(hours=3)}
  p=return_plan(a,'b',t+timedelta(hours=4),{})
  self.assertEqual(p['route_path'],['C','B','A']);self.assertEqual(p['travel_minutes'],60)
 def test_road_returns_only_travelled_distance(self):
  t=datetime(2026,9,27);m={'reason':'battle','battle_id':'b','origin_castle':'A','target_castle':'C','created_at':t,'arrival_at':t+timedelta(minutes=60),'route_path':['A','B','C'],'route_edge_minutes':[20,40],'ended_at':t+timedelta(minutes=30)}
  p=return_plan({'target_castle':'road','movement_history':[m]},'b',t+timedelta(hours=3),{})
  self.assertEqual(p['target_castle'],'A');self.assertEqual(p['travel_minutes'],30)
  line=legs(p,{})
  self.assertEqual(line[0][4:],(.25,0));self.assertEqual(line[-1][4:],(1,0))
 def test_defender_at_own_origin_stays(self):
  self.assertIsNone(return_plan({'origin_castle':'A','target_castle':'A'},'b',datetime(2026,9,27),{}))
 def test_unrecorded_route_not_teleported(self):
  with self.assertRaises(ValueError):return_plan({'origin_castle':'A','target_castle':'B'},'b',datetime(2026,9,27),{})

class CloseReturns(unittest.IsolatedAsyncioTestCase):
 async def test_only_surviving_losers_return(self):
  from unittest.mock import patch,AsyncMock
  from bson import ObjectId
  from routers import admin,war
  from tests.test_battle_lifecycle import DB
  t=datetime(2026,9,27);rid=ObjectId();bid='case'
  root={'_id':rid,'tg_id':1,'active':True,'origin_castle':'A','target_castle':'B','route_path':['A','B'],'route_edge_minutes':[30],'created_at':t,'arrival_at':t+timedelta(minutes=30),'engagement_campaign_id':bid,'battle_started_at':t+timedelta(minutes=30)}
  loser={**root,'_id':ObjectId(),'tg_id':2};dead={**root,'_id':ObjectId(),'tg_id':3,'active':False}
  root['battle_attacker_army_ids']=[str(rid)];root['battle_defender_army_ids']=[str(loser['_id']),str(dead['_id'])]
  db=DB([root,loser,dead])
  with patch.object(admin,'campaigns',db),patch.object(admin,'now',return_value=t+timedelta(hours=1)),patch.object(war,'notify_campaign_departure',AsyncMock()):
   await admin._close_battle_state(root,bid,return_tg_ids=[2,3])
  self.assertNotIn('returning_from_battle',root)
  self.assertEqual(loser['target_castle'],'A');self.assertEqual(loser['travel_minutes'],30)
  self.assertNotIn('returning_from_battle',dead)
