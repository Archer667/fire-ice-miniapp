import unittest
from fastapi import HTTPException
from routers.war import _building_levels,equipment_cost_and_effect
from game_data import SIEGE_EQUIPMENT
class WorkshopTests(unittest.TestCase):
 def test_every_equipment_tier_from_real_castle_levels(self):
  for level in (0,1,2,3):
   player={'castle':'home','buildings':{'siege_workshop':{'level':level}}}
   for eid,meta in SIEGE_EQUIPMENT.items():
    with self.subTest(level=level,equipment=eid):
     if meta['level']>level:
      with self.assertRaises(HTTPException):equipment_cost_and_effect({eid:1},_building_levels(player))
     else:
      cost,power,_=equipment_cost_and_effect({eid:1},_building_levels(player))
      self.assertEqual(cost,meta['cost']);self.assertEqual(power,meta['siege_power'])
 def test_secondary_castle_does_not_use_home_level(self):
  p={'castle':'home','buildings':{'siege_workshop':{'level':3}},'castle_buildings':{'outpost':{'siege_workshop':{'level':1}}}}
  with self.assertRaises(HTTPException):equipment_cost_and_effect({'catapult':1},_building_levels(p,'outpost'))
  p['castle_buildings']['outpost']['siege_workshop']['level']=2
  equipment_cost_and_effect({'catapult':1},_building_levels(p,'outpost'))
 def test_pending_upgrade_not_completed_level(self):
  p={'castle':'home','buildings':{'siege_workshop':{'level':1,'upgrade_to':3}}}
  with self.assertRaises(HTTPException):equipment_cost_and_effect({'trebuchet':1},_building_levels(p))
 def test_raw_and_legacy_states(self):
  equipment_cost_and_effect({'trebuchet':1},{'siege_workshop':{'level':3}})
  equipment_cost_and_effect({'ladder':1},{'siege_workshop':True})
  with self.assertRaises(HTTPException):equipment_cost_and_effect({'catapult':1},{'siege_workshop':True})
