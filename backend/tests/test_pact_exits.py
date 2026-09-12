import os
import unittest
from contextlib import ExitStack
from unittest.mock import patch, AsyncMock
from datetime import datetime
from motor.motor_asyncio import AsyncIOMotorClient
from fastapi import HTTPException
import pact_exits as e
import family
import project_engine
from routers import admin

class PactExitTests(unittest.IsolatedAsyncioTestCase):
 async def asyncSetUp(self):
  assert 'valyria-project-test-db:27017' in os.environ['MONGODB_URI']
  self.client=AsyncIOMotorClient(os.environ['MONGODB_URI']);self.db=self.client.pact_exits_test
  for n in await self.db.list_collection_names(): await self.db[n].delete_many({})
  self.stack=ExitStack()
  for mod,name,col in [(e,'alliances','alliances'),(e,'players','players'),(e,'operations','family_operations'),(family,'operations','family_operations'),(project_engine,'players','players'),(admin,'alliances','alliances')]:
   self.stack.enter_context(patch.object(mod,name,self.db[col]))
  self.stack.enter_context(patch.object(family,'db',self.db))
  self.stack.enter_context(patch.object(family,'notice',AsyncMock()))
  self.stack.enter_context(patch.object(family,'flush_notices',AsyncMock()))
  self.stack.enter_context(patch.object(project_engine,'apply_production',side_effect=lambda p:p))
  self.stack.enter_context(patch.object(e,'apply_production',side_effect=lambda p:p))
  self.stack.enter_context(patch.object(project_engine,'production_fields',side_effect=lambda p:{'resources':p['resources']}))
  for uid in (1,2,3,4): await self.db.players.insert_one({'tg_id':uid,'name':str(uid),'created_at':datetime(2026,9,1),'castle':'A','resources':{'gold':1,'wine':0},'alliance_count':2 if uid==1 else 1})
  self.edges=[]
  for uid in (2,3):
   r={'from_id':1,'to_id':uid,'from_name':'1','to_name':str(uid),'type':'non_aggression','group_id':'g','penalty_gold':5,'status':'accepted','created_at':datetime(2026,9,1)}
   self.edges.append((await self.db.alliances.insert_one(r)).inserted_id)
 async def asyncTearDown(self):self.stack.close();self.client.close()
 async def gold(self,uid):return (await self.db.players.find_one({'tg_id':uid}))['resources']['gold']
 async def test_member_expulsion_debt_and_exact_split(self):
  r=await e.exit_pact(str(self.edges[0]),2,True,99)
  self.assertFalse(r['dissolved']);self.assertEqual(await self.gold(2),-4)
  self.assertEqual(await self.gold(1)+await self.gold(3),7)
  self.assertEqual(await self.db.alliances.count_documents({'status':'accepted'}),1)
  with self.assertRaises(HTTPException):await e.exit_pact(str(self.edges[0]),2,True,99)
  self.assertEqual(await self.gold(2),-4)
 async def test_voluntary_insufficient_funds_changes_nothing(self):
  with self.assertRaises(HTTPException): await e.exit_pact(str(self.edges[0]),2)
  self.assertEqual(await self.gold(2),1);self.assertEqual(await self.db.alliances.count_documents({'status':'accepted'}),2)
 async def test_creator_dissolves_and_refunds_pending(self):
  await self.db.alliances.insert_one({'from_id':1,'to_id':4,'group_id':'g','status':'pending','wine_cost':20})
  r=await e.exit_pact(str(self.edges[0]),1,True,99)
  self.assertTrue(r['dissolved']);self.assertEqual(await self.gold(1),-4)
  self.assertEqual(await self.db.alliances.count_documents({'status':'accepted'}),0)
  self.assertEqual((await self.db.players.find_one({'tg_id':1}))['resources']['wine'],20)
 async def test_listing_complete_and_marriage_protection(self):
  for i in range(110):await self.db.alliances.insert_one({'from_id':1,'to_id':100+i,'from_name':'1','to_name':str(i),'group_id':'g','type':'trade','status':'accepted','created_at':datetime(2026,9,1)})
  result=await admin.admin_list_alliances({'id':99});self.assertEqual(len(result),1);self.assertEqual(len(result[0]['members']),113)
  await self.db.alliances.update_one({'_id':self.edges[0]},{'$set':{'marriage_id':'m'}})
  with self.assertRaises(HTTPException):await e.exit_pact(str(self.edges[0]),2,True,99)
 async def test_recovery_does_not_charge_twice(self):
  await e.exit_pact(str(self.edges[0]),2,True,99)
  await self.db.family_operations.update_many({}, {'$set':{'complete':False}})
  await e.recover_exits();self.assertEqual(await self.gold(2),-4);self.assertEqual(await self.gold(1)+await self.gold(3),7)
