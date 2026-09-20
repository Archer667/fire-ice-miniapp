import unittest
from copy import deepcopy
import control_settings
from game import daily_production
from player_search import find_matches
from routers.war import troop_food_and_gold
from game_data import REGIONS
from troop_materials import snapshot,refund

class Changes(unittest.TestCase):
 def test_secondary_castle_spelling_and_english(self):
  rows=[{'tg_id':1,'name':'Lord','castle':'X','castle_buildings':{'استون هلم':{}},'region':'x'}]
  for q in ('استون هلم','استون‌هلم','استونهلم','Stonehelm'):
   self.assertEqual(find_matches(rows,q)[0]['tg_id'],1)
 def test_population_controls(self):
  old=control_settings.snapshot()
  try:
   cfg=deepcopy(control_settings.DEFAULTS);control_settings.replace(cfg)
   p={'castle':'A','castle_buildings':{},'buildings':{},'resources':{'men':0},'popularity':50}
   one=daily_production(p)['men'];p['castle_buildings']={'A':{},'B':{}}
   self.assertEqual(daily_production(p)['men'],one*2)
   cfg['economy']['population_extra_castle_multiplier']=0;cfg['economy']['population_growth_multiplier']=1;control_settings.replace(cfg)
   self.assertEqual(daily_production(p)['men'],one/2)
  finally:control_settings.replace(old)
 def test_ship_charge_and_survivor_refund(self):
  troops={'cargo_ship':2,'ship':1}
  gold,men,food,materials=troop_food_and_gold(next(iter(REGIONS)),troops,{'port':1},True)
  self.assertEqual(gold,250);self.assertEqual(materials,{'wood':200,'iron':50})
  a={'naval_material_costs':snapshot(troops),'troops':{'cargo_ship':1,'ship':1}}
  self.assertEqual(refund(a),{'wood':150,'iron':50})
  self.assertEqual(refund({'troops':troops}),{})
