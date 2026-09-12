import unittest
from datetime import datetime,timedelta
from unittest.mock import AsyncMock,patch
from bson import ObjectId
from fastapi import HTTPException
from routers import war
class ReachedRoutes(Exception):pass
class CancelledBattleTests(unittest.IsolatedAsyncioTestCase):
 async def check_block(self,cancelled):
  uid=12;oid=ObjectId();at=datetime(2026,9,12)
  army={'_id':oid,'tg_id':uid,'active':True,'op_type':'defense','target_castle':'تویینز','arrival_at':at-timedelta(days=2)}
  enemy={'active':True,'op_type':'attack','target_castle':'تویینز'}
  if cancelled:enemy['battle_cancelled_at']=at
  async def find(q):
   if '_id' in q:return army
   if q.get('battle_cancelled_at')=={'$exists':False} and cancelled:return None
   return enemy
  with patch.object(war,'campaigns') as db,patch.object(war,'now',return_value=at),patch.object(war,'get_war_window',AsyncMock(return_value={'open':True})),patch.object(war,'all_castle_names_and_ports',AsyncMock(return_value=(['ریوران'],[]))),patch.object(war,'reject_hostile_order_during_pact',AsyncMock()),patch.object(war,'owner_of_castle',AsyncMock(return_value={'tg_id':uid})),patch.object(war,'all_castle_terrain',AsyncMock(side_effect=ReachedRoutes)):
   db.find_one=AsyncMock(side_effect=find)
   await war.move_campaign(str(oid),war.MoveCampaignBody(target_castle='ریوران',op_type='garrison'),{'id':uid})
 async def test_cancelled_attack_does_not_block_departure(self):
  with self.assertRaises(ReachedRoutes):await self.check_block(True)
 async def test_unresolved_attack_still_blocks_departure(self):
  with self.assertRaises(HTTPException) as e:await self.check_block(False)
  self.assertEqual(e.exception.status_code,403)
