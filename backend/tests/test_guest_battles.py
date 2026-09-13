import unittest
from unittest.mock import AsyncMock,patch
from bson import ObjectId
from routers import war,admin
from tests.test_battle_lifecycle import DB
class GuestBattleTests(unittest.IsolatedAsyncioTestCase):
 async def test_two_guests_do_not_fight_without_direct_pact(self):
  with patch.object(war,'players_are_friendly',AsyncMock(return_value=False)):
   self.assertFalse(await war.castle_armies_are_hostile({'tg_id':1,'op_type':'garrison'},{'tg_id':2,'op_type':'defense'},{'tg_id':3}))
 async def test_pact_prevents_army_combat(self):
  with patch.object(war,'players_are_friendly',AsyncMock(return_value=True)):
   self.assertFalse(await war.castle_armies_are_hostile({'tg_id':1,'op_type':'attack'},{'tg_id':2,'op_type':'defense'},{'tg_id':2}))
 async def test_real_attack_still_meets_defense(self):
  with patch.object(war,'players_are_friendly',AsyncMock(return_value=False)):
   self.assertTrue(await war.castle_armies_are_hostile({'tg_id':1,'op_type':'attack'},{'tg_id':2,'op_type':'defense'},{'tg_id':2}))
 async def test_join_checks_every_opponent_not_just_leader(self):
  oid=ObjectId();root={'tg_id':1,'battle_defender_tg_id':2,'battle_defender_army_ids':[str(oid)]}
  async def friendly(a,b):return b==3
  with patch.object(war,'campaigns',DB([{'_id':oid,'active':True,'tg_id':3}])),patch.object(war,'players_are_friendly',AsyncMock(side_effect=friendly)):
   self.assertFalse(await war.may_join_battle(root,4,'attacker'))
 async def test_twins_guest_battle_is_dismissed(self):
  rid=ObjectId();did=ObjectId()
  root={'_id':rid,'tg_id':1,'active':True,'op_type':'garrison','battle_open':True,'battle_location':'تویینز','battle_defender_tg_id':3,'battle_attacker_army_ids':[str(rid)],'battle_defender_army_ids':[str(did)]}
  db=DB([root,{'_id':did,'tg_id':2,'active':True,'op_type':'defense'}])
  async def friendly(a,b):return b==3
  with patch.object(war,'campaigns',db),patch.object(war,'players_are_friendly',AsyncMock(side_effect=friendly)),patch.object(admin,'_dismiss_battle_record',AsyncMock()) as close:
   await war.reconcile_battle_locks();close.assert_awaited_once()
