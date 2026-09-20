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
  await self.db.game_settings.insert_one({'_id':'encounter_engine_v2','started_at':self.at-timedelta(days=1)})
  self.stack.enter_context(patch.object(war,'TRAVEL_GRAPH',{'A':{'B':60},'B':{'A':60,'C':30},'C':{'B':30}}))
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
 async def test_guests_of_same_owner_fight_without_pairwise_pact(self):
  await self.player(1,'T');await self.player(2);await self.player(3)
  await self.pact(1,2,group='a');await self.pact(1,3,group='b')
  await self.army(2);await self.army(3,'defense')
  await war.notify_arrivals()
  self.assertEqual(await self.db.campaigns.count_documents({'battle_open':True}),1)
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
 async def test_unpacted_garrison_route_crossing_fights(self):
  await self.army(1,moving=True,path=['A','B']);await self.army(2,moving=True,path=['B','A'])
  await war.detect_route_encounters()
  self.assertEqual(await self.db.campaigns.count_documents({'engagement_locked':True}),2)
 async def test_allied_hostile_route_crossing_no_battle(self):
  await self.pact(1,2)
  await self.army(1,'attack',moving=True,path=['A','B']);await self.army(2,'attack',moving=True,path=['B','A'])
  await war.detect_route_encounters()
  self.assertEqual(await self.db.campaigns.count_documents({'engagement_locked':True}),0)
 async def test_route_army_cannot_belong_to_two_roots(self):
  await self.army(1,'attack',moving=True,path=['A','B'])
  await self.army(2,'attack',moving=True,path=['B','A'])
  third=await self.army(3,'attack',moving=True,path=['B','A'])
  await self.db.campaigns.update_one({'_id':third},{'$set':{'created_at':self.at-timedelta(minutes=30),'arrival_at':self.at+timedelta(minutes=30)}})
  await war.detect_route_encounters()
  self.assertEqual(await self.db.campaigns.count_documents({'battle_open':True}),1)
  self.assertEqual(await self.db.campaigns.count_documents({'engagement_locked':True}),3)
 async def test_join_side_uses_secondary_members_and_stays_neutral_if_both(self):
  a=await self.army(1,'attack');b=await self.army(2,'defense');extra=await self.army(3,'defense')
  root={'tg_id':1,'battle_attacker_army_ids':[str(a)],'battle_defender_army_ids':[str(b),str(extra)],'battle_defender_tg_id':2}
  await self.pact(3,4,group='a')
  self.assertEqual(await war.choose_battle_side(root,{'tg_id':4,'op_type':'garrison'}),'independent')
  await self.pact(1,4,group='b')
  self.assertEqual(await war.choose_battle_side(root,{'tg_id':4,'op_type':'garrison'}),'independent')
  self.assertEqual(await war.choose_battle_side(root,{'tg_id':5,'op_type':'garrison'}),'independent')
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

 async def test_three_enemies_share_case_but_not_teams(self):
  for uid in [1,2,3]:
   await self.player(uid)
   await self.army(uid)
  await war.notify_arrivals()
  self.assertEqual(await self.db.campaigns.count_documents({'battle_open':True}),1)
  self.assertEqual(await self.db.campaigns.count_documents({'engagement_locked':True}),3)
  root=await self.db.campaigns.find_one({'battle_open':True})
  parties=await war.battle_relations(root)
  self.assertEqual([p['hostile_to'] for p in parties],[[2,3],[1,3],[1,2]])
  await admin._close_battle_state(root,root['engagement_campaign_id'],cancelled=True)
  await war.notify_arrivals()
  self.assertEqual(await self.db.campaigns.count_documents({'engagement_locked':True}),0)

 async def test_removing_legacy_defender_keeps_two_remaining_enemies(self):
  for uid in [1,2,3]:
   await self.player(uid)
   await self.army(uid)
  await war.notify_arrivals()
  root=await self.db.campaigns.find_one({'battle_open':True})
  from bson import ObjectId
  leaving=await self.db.campaigns.find_one({'_id':ObjectId(root['battle_defender_army_ids'][0])})
  result=await admin._remove_campaign_from_battle(leaving,'test')
  self.assertFalse(result['battle_closed'])
  self.assertEqual(await self.db.campaigns.count_documents({'engagement_locked':True}),2)

 async def test_closing_old_case_does_not_unlock_army_in_new_case(self):
  from bson import ObjectId
  aid=await self.army(1)
  root={'_id':ObjectId(),'battle_attacker_army_ids':[str(aid)]}
  await self.db.campaigns.update_one({'_id':aid},{'$set':{'engagement_campaign_id':'new-case','engagement_locked':True}})
  await admin._close_battle_state(root,'old-case',cancelled=True)
  self.assertTrue((await self.db.campaigns.find_one({'_id':aid}))['engagement_locked'])

 async def test_road_battle_closure_keeps_exact_position(self):
  await self.army(1,moving=True,path=['A','B'])
  await self.army(2,moving=True,path=['B','A'])
  await war.detect_route_encounters()
  root=await self.db.campaigns.find_one({'battle_open':True})
  self.assertEqual(root['stationed_edge']['position'],0.5)
  await admin._close_battle_state(root,root['engagement_campaign_id'],cancelled=True)
  await war.detect_route_encounters()
  rows=await self.db.campaigns.find({}).to_list(None)
  self.assertTrue(all(not r['engagement_locked'] for r in rows))
  self.assertTrue(all(r['stationed_edge']['position']==0.5 for r in rows))
  self.assertTrue(all(r['target_castle'].startswith('مسیر ') for r in rows))

 async def test_intermediate_castle_stops_army_before_destination(self):
  moving=await self.army(1,target='C',moving=True,path=['A','B','C'])
  await self.db.campaigns.update_one({'_id':moving},{'$set':{'created_at':self.at-timedelta(minutes=70),'arrival_at':self.at+timedelta(minutes=20)}})
  await self.army(2,'defense',target='B',path=['B'])
  await self.db.campaigns.update_many({'tg_id':2},{'$set':{'arrival_at':self.at-timedelta(hours=3)}})
  await war.detect_route_encounters()
  army=await self.db.campaigns.find_one({'_id':moving})
  self.assertTrue(army['engagement_locked'])
  self.assertEqual(army['target_castle'],'B')
  self.assertEqual(army['battle_started_at'],self.at-timedelta(minutes=10))

 async def test_late_tick_still_detects_crossing(self):
  for uid,path in [(1,['A','B']),(2,['B','A'])]:
   oid=await self.army(uid,path=path)
   await self.db.campaigns.update_one({'_id':oid},{'$set':{'created_at':self.at-timedelta(hours=2),'arrival_at':self.at-timedelta(hours=1)}})
  await war.detect_route_encounters()
  self.assertEqual(await self.db.campaigns.count_documents({'engagement_locked':True}),2)

 async def test_road_departure_requires_endpoint_and_keeps_distance(self):
  from road_positions import endpoint_route
  from game_data import TRAVEL_GRAPH
  point={'a':'A','b':'B','position':0.25,'base_minutes':60}
  army={'target_castle':'مسیر A — B','stationed_edge':point}
  self.assertEqual(endpoint_route(army,'A',{'A':'land','B':'land'})['minutes'],15)
  self.assertEqual(endpoint_route(army,'B',{'A':'land','B':'land'})['minutes'],45)
  with self.assertRaises(HTTPException):endpoint_route(army,'C')

 async def test_third_army_joins_stopped_road_battle_later(self):
  await self.army(1,moving=True,path=['A','B'])
  await self.army(2,moving=True,path=['B','A'])
  await war.detect_route_encounters()
  third=await self.army(3,moving=True,path=['A','B'])
  await self.db.campaigns.update_one({'_id':third},{'$set':{'created_at':self.at,'arrival_at':self.at+timedelta(minutes=60)}})
  war.now.return_value=self.at+timedelta(minutes=40)
  await war.detect_route_encounters()
  self.assertEqual(await self.db.campaigns.count_documents({'battle_open':True}),1)
  self.assertEqual(await self.db.campaigns.count_documents({'engagement_locked':True}),3)

 async def test_new_order_cannot_skip_a_past_collision(self):
  ids=[]
  for uid,path in [(1,['A','B']),(2,['B','A'])]:
   oid=await self.army(uid,path=path);ids.append(oid)
   await self.db.campaigns.update_one({'_id':oid},{'$set':{'created_at':self.at-timedelta(hours=2),'arrival_at':self.at-timedelta(hours=1)}})
  with self.assertRaises(HTTPException) as raised:
   await war.move_campaign(str(ids[0]),war.MoveCampaignBody(target_castle='C',op_type='garrison'),{'id':1})
  self.assertEqual(raised.exception.status_code,409)

 async def test_depart_from_road_after_closure_with_correct_remaining_time(self):
  oid=await self.army(1,moving=True,path=['A','B'])
  await self.army(2,moving=True,path=['B','A'])
  await war.detect_route_encounters()
  root=await self.db.campaigns.find_one({'battle_open':True})
  await admin._close_battle_state(root,root['engagement_campaign_id'],cancelled=True)
  with patch.object(war,'get_war_window',AsyncMock(return_value={'open':True})),patch.object(war,'all_castle_names_and_ports',AsyncMock(return_value=(['A','B','C'],[]))),patch.object(war,'all_castle_terrain',AsyncMock(return_value={'A':'land','B':'land','C':'land'})):
   result=await war.move_campaign(str(oid),war.MoveCampaignBody(target_castle='B',op_type='garrison'),{'id':1})
  self.assertEqual(result['travel_minutes'],30)
  row=await self.db.campaigns.find_one({'_id':oid})
  self.assertNotIn('stationed_edge',row)
  self.assertEqual(row['route_start_position']['position'],0.5)
  war.now.return_value=self.at+timedelta(minutes=10)
  await war.detect_route_encounters()
  self.assertEqual(await self.db.campaigns.count_documents({'engagement_locked':True}),0)

 async def test_multi_party_resolution_applies_each_army_losses_once(self):
  for uid in [1,2,3]:
   await self.player(uid)
   await self.army(uid)
  await war.notify_arrivals()
  root=await self.db.campaigns.find_one({'battle_open':True})
  rows=await self.db.campaigns.find({}).to_list(None)
  amounts={str(a['_id']):{'infantry':a['tg_id']*10} for a in rows}
  body=admin.RoleplayResultBody(result='نتیجهٔ آزمون چندطرفه',winner_tg_ids=[3],
       attacker_army_losses={i:amounts[i] for i in root['battle_attacker_army_ids']},
       defender_army_losses={i:amounts[i] for i in root['battle_defender_army_ids']})
  await admin.resolve_battle_without_required_roll(root['engagement_campaign_id'],body,{'id':999})
  for army in await self.db.campaigns.find({}).to_list(None):
   self.assertEqual(army['troops']['infantry'],100-army['tg_id']*10)
   self.assertFalse(army['engagement_locked'])
  with self.assertRaises(HTTPException):
   await admin.resolve_battle_without_required_roll(root['engagement_campaign_id'],body,{'id':999})

 async def test_ending_peace_starts_combat_for_colocated_armies(self):
  await self.pact(1,2)
  await self.army(1,target='T',path=['T'])
  await self.army(2,target='T',path=['T'])
  await war.detect_route_encounters()
  self.assertEqual(await self.db.campaigns.count_documents({'battle_open':True}),0)
  await self.db.alliances.update_many({},{'$set':{'status':'left'}})
  war.now.return_value=self.at+timedelta(minutes=1)
  await war.detect_route_encounters()
  self.assertEqual(await self.db.campaigns.count_documents({'battle_open':True}),1)

 async def test_late_tick_recomputes_arrival_after_first_armies_stop(self):
  a=await self.army(1,moving=True,path=['A','B'])
  b=await self.army(2,moving=True,path=['B','A'])
  c=await self.army(3,moving=True,path=['A','B'])
  for aid,start,end in ((a,-90,30),(b,-60,60),(c,-40,20)):
   await self.db.campaigns.update_one({'_id':aid},{'$set':{'created_at':self.at+timedelta(minutes=start),'arrival_at':self.at+timedelta(minutes=end)}})
  await war.detect_route_encounters()
  self.assertEqual(await self.db.campaigns.count_documents({'battle_open':True}),1)
  rows=await self.db.campaigns.find({}).to_list(None)
  self.assertTrue(all(r.get('engagement_locked') for r in rows))
  third=await self.db.campaigns.find_one({'_id':c})
  self.assertEqual(third['arrival_at'],self.at-timedelta(minutes=2.5))
