import unittest
from copy import deepcopy
import control_settings as controls
from army_upkeep import food_rate,civilian_food_rate

class FoodControls(unittest.TestCase):
 def setUp(self):self.old=controls.snapshot()
 def tearDown(self):controls.replace(self.old)
 def test_independent_multipliers(self):
  base=food_rate({'infantry':100});data=controls.snapshot();data['food']={'civilian_consumption_percent':50,'army_consumption_percent':25};controls.replace(data)
  self.assertAlmostEqual(food_rate({'infantry':100}),base*.25)
  self.assertAlmostEqual(civilian_food_rate({'base_food_per_100_men':20}),.1)
 def test_zero_and_validation(self):
  data=controls.snapshot();data['food']={'civilian_consumption_percent':0,'army_consumption_percent':0};controls.replace(data)
  self.assertEqual(food_rate({'infantry':100}),0);self.assertEqual(civilian_food_rate({'base_food_per_100_men':20}),0)
  for bad in [-1,1001,float('nan'),'bad']:
   data['food']['army_consumption_percent']=bad
   with self.assertRaises(ValueError):controls.validate(data)
