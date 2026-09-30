import os,unittest
from datetime import datetime,timedelta
from contextlib import ExitStack
from unittest.mock import patch,AsyncMock
from bson import ObjectId
from motor.motor_asyncio import AsyncIOMotorClient
from fastapi import HTTPException
import battle_passage as p
import army_groups as g
from routers import admin

class JourneyTests(unittest.TestCase):
 def test_resume_partial_leg_keeps_direction_and_remaining_time(self):
  start=datetime(2026,9,30);contact=start+timedelta(minutes=5);restart=start+timedelta(hours=12)
  for path in (['A','B'],['B','A']):
   army={'target_castle':'مسیر A — B','movement_history':[{'reason':'battle','battle_id':'b','origin_castle':path[0],'target_castle':path[-1],'op_type':'garrison','route_path':path,'route_edge_minutes':[10],'moved_at':start,'arrival_at':start+timedelta(minutes=10),'ended_at':contact}]}
   plan=p.continuation(army,'b',restart,{'A':{'B':10},'B':{'A':10}})
   self.assertEqual(plan['target_castle'],path[-1]);self.assertEqual(plan['travel_minutes'],5)
   self.assertEqual(plan['arrival_at'],restart+timedelta(minutes=5));self.assertEqual(plan['route_segments'][0]['p0'],.5)
 def test_multi_leg_and_bad_history(self):
  at=datetime(2026,9,30)
  army={'target_castle':'مسیر A — B','movement_history':[{'reason':'battle','battle_id':'b','origin_castle':'A','target_castle':'C','route_path':['A','B','C'],'route_edge_minutes':[10,20],'moved_at':at,'arrival_at':at+timedelta(minutes=30),'ended_at':at+timedelta(minutes=5)}]}
  plan=p.continuation(army,'b',at+timedelta(days=1),{})
  self.assertEqual(plan['travel_minutes'],25);self.assertEqual(plan['route_path'],['مسیر A — B','B','C'])
  with self.assertRaises(ValueError):p.continuation({},'b',at,{})

@unittest.skipUnless(os.getenv('DB_NAME')=='battle_passage_test','isolated database required')
class ConsentTests(unittest.IsolatedAsyncioTestCase):
 async def test_unanimity_group_control_withdrawal_and_recovery(self):
  client=AsyncIOMotorClient(os.environ['MONGODB_URI']);db=client.battle_passage_test
  for name in ('campaigns','players','army_groups','roleplays','battle_passage_commands'):await db[name].delete_many({})
  at=datetime(2026,9,30,12);bid=str(ObjectId());gid=ObjectId()
  def army(uid):
   aid=ObjectId();path=['A','B'] if uid!=3 else ['B','A']
   return {'_id':aid,'tg_id':uid,'active':True,'engagement_locked':True,'engagement_campaign_id':bid,'battle_contact':{'kind':'edge','a':'A','b':'B','position':.5},'stationed_edge':{'a':'A','b':'B','position':.5},'target_castle':'مسیر A — B','op_type':'garrison','troops':{'infantry':100},'equipment':{'ram':1},'movement_history':[{'reason':'battle','battle_id':bid,'origin_castle':path[0],'target_castle':path[-1],'route_path':path,'route_edge_minutes':[10],'moved_at':at-timedelta(minutes=10),'arrival_at':at,'ended_at':at-timedelta(minutes=5)}]}
  rows=[army(1),army(2),army(3)];root=rows[0];root.update(battle_open=True,battle_is_root=True,battle_location='مسیر A — B')
  for a in rows[:2]:a['merge_group_id']=str(gid)
  await db.campaigns.insert_many(rows);await db.players.insert_many([{'tg_id':i,'name':str(i),'resources':{'food':1000}} for i in (1,2,3,4)])
  await db.army_groups.insert_one({'_id':gid,'active':True,'leader_tg_id':1,'army_ids':[a['_id'] for a in rows[:2]]})
  await db.roleplays.insert_one({'category':'war','campaign_id':bid,'resolved':False})
  with ExitStack() as stack:
   for m,n,v in [(p,'db',db),(p,'campaigns',db.campaigns),(p,'roleplays',db.roleplays),(p,'players',db.players),(g,'groups',db.army_groups),(p,'now',lambda:at)]:stack.enter_context(patch.object(m,n,v))
   async def find_root(_):return await db.campaigns.find_one({'_id':root['_id']})
   stack.enter_context(patch.object(admin,'_battle_root',AsyncMock(side_effect=find_root)))
   stack.enter_context(patch.object(admin,'_battle_members_query',return_value={'engagement_campaign_id':bid}))
   stack.enter_context(patch('battle_notices.enqueue',AsyncMock()))
   stack.enter_context(patch('routers.war.all_castle_terrain',AsyncMock(return_value={'A':'land','B':'land'})))
   self.assertEqual((await p.status(root,1))['required_count'],2)
   with self.assertRaises(HTTPException):await p.consent(str(rows[1]['_id']),True,{'id':2})
   first=await p.consent(str(root['_id']),True,{'id':1});self.assertFalse(first['closed'])
   self.assertEqual(await db.campaigns.count_documents({'engagement_locked':True}),3)
   await p.consent(str(root['_id']),False,{'id':1});self.assertFalse((await p.status(root,1))['agreed'])
   await p.consent(str(root['_id']),True,{'id':1})
   # A new participant invalidates earlier votes; the new party must also consent.
   extra=army(4);await db.campaigns.insert_one(extra)
   self.assertEqual((await p.status(root,1))['agreed_count'],0)
   await p.consent(str(root['_id']),True,{'id':1});await p.consent(str(rows[2]['_id']),True,{'id':3})
   with patch('routers.war.all_castle_terrain',AsyncMock(return_value={'A':'sea','B':'land'})):
    with self.assertRaises(HTTPException):await p.consent(str(extra['_id']),True,{'id':4})
   self.assertEqual(await db.campaigns.count_documents({'engagement_locked':True}),4)
   last=await p.consent(str(extra['_id']),True,{'id':4});self.assertTrue(last['closed'])
   final=await db.campaigns.find({}).to_list(None)
   self.assertTrue(all(not a['engagement_locked'] and a['arrival_at']==at+timedelta(minutes=5) for a in final))
   self.assertEqual({a['target_castle'] for a in final},{'A','B'})
   self.assertTrue((await db.roleplays.find_one({}))['resolved'])
   self.assertTrue(all(a['troops']=={'infantry':100} and a['equipment']=={'ram':1} for a in final))
   await db.battle_passage_commands.update_one({}, {'$set':{'status':'prepared'}})
   await p.recover();await p.recover()
   self.assertEqual([len(a['movement_history']) for a in await db.campaigns.find({}).to_list(None)],[2,2,2,2])
   self.assertTrue(all(a['resources']=={'food':1000} for a in await db.players.find({}).to_list(None)))
  client.close()
