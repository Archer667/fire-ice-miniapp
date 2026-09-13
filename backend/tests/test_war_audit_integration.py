"""Integration tests run only against a disposable MongoDB, never the game DB."""
import os,unittest
from contextlib import ExitStack
from datetime import datetime,timedelta
from unittest.mock import patch,AsyncMock
from motor.motor_asyncio import AsyncIOMotorClient
from fastapi import HTTPException
from routers import war,admin
class WarAuditTests(unittest.IsolatedAsyncioTestCase):
 async def asyncSetUp(self):
  uri=os.environ['MONGODB_URI'];assert 'war-audit-mongo' in uri
  self.client=AsyncIOMotorClient(uri);self.db=self.client.war_audit_test
  await self.client.drop_database('war_audit_test')
  self.stack=ExitStack();self.at=datetime(2026,9,13,12)
  for mod in (war,admin):
   for name in ('campaigns','players','alliances','roleplays','ambushes','map_castles','game_settings'):
    if hasattr(mod,name):self.stack.enter_context(patch.object(mod,name,self.db[name]))
   self.stack.enter_context(patch.object(mod,'now',return_value=self.at))
  for name in ('send_system_message','notify_admins','notify_battle_admins','queue_battle_roster'):
   self.stack.enter_context(patch.object(war,name,AsyncMock()))
  self.stack.enter_context(patch.object(admin,'send_system_message',AsyncMock()))
  self.stack.enter_context(patch.object(war,'battle_admin_roster_text',AsyncMock(return_value='test')))
  async def owner(castle):return await self.db.players.find_one({'castle':castle})
  self.stack.enter_context(patch.object(war,'owner_of_castle',owner))
  self.stack.enter_context(patch.object(admin,'owner_of_castle',owner))
  self.stack.enter_context(patch.object(war,'defensive_infrastructure',return_value=[]))
 async def asyncTearDown(self):self.stack.close();self.client.close()
 async def player(self,uid,castle=None):await self.db.players.insert_one({'tg_id':uid,'name':str(uid),'castle':castle or str(uid),'buildings':{}})
 async def pact(self,a,b,kind='full_alliance',group='g'):
  await self.db.alliances.insert_one({'from_id':a,'to_id':b,'status':'accepted','type':kind,'group_id':group})
 async def army(self,uid,op='garrison',target='T',moving=False,path=None):
  row={'tg_id':uid,'player_name':str(uid),'origin_castle':'O','target_castle':target,'op_type':op,'name':op,'active':True,'arrival_notified':False,'arrival_at':self.at+timedelta(hours=1) if moving else self.at-timedelta(minutes=1),'created_at':self.at-timedelta(hours=1),'troops':{'infantry':100},'men_committed':100,'power':100,'equipment':{}}
  if path:row['route_path']=path
  return (await self.db.campaigns.insert_one(row)).inserted_id
 async def test_group_pacts_block_all_hostile_orders_and_arrivals(self):
  for kind in ('full_alliance','non_aggression'):
   await self.db.alliances.delete_many({});await self.db.campaigns.delete_many({});await self.db.players.delete_many({})
   await self.player(2,'T');await self.player(3,'S');await self.pact(1,2,kind);await self.pact(1,3,kind)
   for op in ('attack','siege','naval_raid'):
    with self.assertRaises(HTTPException):await war.reject_hostile_order_during_pact(3,'T',op)
    await self.army(3,op)
   await war.notify_arrivals()
   self.assertEqual(await self.db.campaigns.count_documents({'engagement_locked':True}),0)
   self.assertEqual(await self.db.campaigns.count_documents({'battle_open':True}),0)
 async def test_guests_of_same_owner_no_battle(self):
  await self.player(1,'T');await self.player(2);await self.player(3)
  await self.pact(1,2,group='a');await self.pact(1,3,group='b')
  await self.army(2);await self.army(3,'defense')
  await war.notify_arrivals()
  self.assertEqual(await self.db.campaigns.count_documents({'battle_open':True}),0)
 async def test_real_attack_one_root_despite_arrival_cursor(self):
  await self.player(1);await self.player(2,'T')
  await self.army(1,'attack');await self.army(2,'defense')
  await war.notify_arrivals()
  self.assertEqual(await self.db.campaigns.count_documents({'battle_open':True}),1)
  rows=await self.db.campaigns.find({}).to_list(None)
  self.assertEqual(len({r.get('engagement_campaign_id') for r in rows}),1)
 async def test_cancelled_battle_stays_closed_without_pact(self):
  await self.test_real_attack_one_root_despite_arrival_cursor()
  root=await self.db.campaigns.find_one({'battle_open':True})
  await admin._close_battle_state(root,root['engagement_campaign_id'],cancelled=True)
  await war.notify_arrivals();await war.notify_arrivals()
  self.assertEqual(await self.db.campaigns.count_documents({'engagement_locked':True}),0)
 async def test_peaceful_route_crossing_no_battle(self):
  await self.army(1,moving=True,path=['A','B']);await self.army(2,moving=True,path=['B','A'])
  await war.detect_route_encounters()
  self.assertEqual(await self.db.campaigns.count_documents({'engagement_locked':True}),0)
 async def test_allied_hostile_route_crossing_no_battle(self):
  await self.pact(1,2)
  await self.army(1,'attack',moving=True,path=['A','B']);await self.army(2,'attack',moving=True,path=['B','A'])
  await war.detect_route_encounters()
  self.assertEqual(await self.db.campaigns.count_documents({'engagement_locked':True}),0)
 async def test_route_army_cannot_belong_to_two_roots(self):
  await self.army(1,'attack',moving=True,path=['A','B'])
  await self.army(2,'attack',moving=True,path=['B','A']);await self.army(3,'attack',moving=True,path=['B','A'])
  await war.detect_route_encounters()
  self.assertEqual(await self.db.campaigns.count_documents({'battle_open':True}),1)
  self.assertEqual(await self.db.campaigns.count_documents({'engagement_locked':True}),2)
 async def test_join_side_uses_secondary_members_and_stays_neutral_if_both(self):
  a=await self.army(1,'attack');b=await self.army(2,'defense');extra=await self.army(3,'defense')
  root={'tg_id':1,'battle_attacker_army_ids':[str(a)],'battle_defender_army_ids':[str(b),str(extra)],'battle_defender_tg_id':2}
  await self.pact(3,4,group='a')
  self.assertEqual(await war.choose_battle_side(root,{'tg_id':4,'op_type':'garrison'}),'defender')
  await self.pact(1,4,group='b')
  self.assertIsNone(await war.choose_battle_side(root,{'tg_id':4,'op_type':'garrison'}))
  self.assertIsNone(await war.choose_battle_side(root,{'tg_id':5,'op_type':'garrison'}))
 async def test_siege_upgrade_rechecks_pact(self):
  await self.player(2,'T');await self.pact(1,2)
  oid=await self.army(1,'siege')
  with self.assertRaises(HTTPException) as e:await war.order_siege_attack(str(oid),{'id':1})
  self.assertEqual(e.exception.status_code,403)

 async def test_ambush_does_not_damage_group_ally(self):
  await self.pact(1,2,'non_aggression');await self.pact(1,3,'non_aggression')
  oid=await self.army(2,'attack',moving=True,path=['A','B'])
  aid=(await self.db.ambushes.insert_one({'tg_id':3,'status':'active','edge_key':war.ambush_edge_key('A','B')})).inserted_id
  await war.process_route_ambushes()
  self.assertEqual((await self.db.ambushes.find_one({'_id':aid}))['status'],'active')
  self.assertEqual((await self.db.campaigns.find_one({'_id':oid}))['men_committed'],100)
