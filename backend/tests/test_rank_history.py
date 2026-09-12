import unittest
from datetime import datetime,timedelta
from unittest.mock import patch,AsyncMock,MagicMock
import rank_history as h
class HistoryTests(unittest.IsolatedAsyncioTestCase):
 def test_direction_new_and_warmup(self):
  self.assertEqual(h.movement({'a':9},'a',4)['delta'],5)
  self.assertEqual(h.movement({'a':2},'a',6)['delta'],-4)
  self.assertEqual(h.movement({'a':2},'a',2)['delta'],0)
  self.assertEqual(h.movement({},'a',2)['state'],'new')
  self.assertEqual(h.movement(None,'a',2)['state'],'pending')
 def test_character_identity(self):
  self.assertNotEqual(h.player_key({'tg_id':1,'created_at':'old'}),h.player_key({'tg_id':1,'created_at':'new'}))
 async def test_baseline_freshness_and_scope(self):
  history=MagicMock();history.find_one=AsyncMock(return_value={'at':datetime.utcnow()-timedelta(hours=24,seconds=30),'ranks':{'a':2}})
  with patch.object(h,'history',history),patch.object(h,'scope',AsyncMock(return_value='season:week')):
   self.assertEqual(await h.baseline('weekly'),{'a':2})
   self.assertEqual(history.find_one.call_args.args[0]['scope'],'season:week')
   history.find_one.return_value={'at':datetime.utcnow()-timedelta(hours=25),'ranks':{'a':1}}
   self.assertIsNone(await h.baseline('weekly'))
