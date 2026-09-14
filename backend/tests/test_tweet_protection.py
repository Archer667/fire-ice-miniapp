import os,unittest
from datetime import datetime,timedelta
from contextlib import ExitStack
from unittest.mock import patch,AsyncMock
from motor.motor_asyncio import AsyncIOMotorClient
from fastapi import HTTPException
from routers import rumors as r
class TweetProtectionTests(unittest.IsolatedAsyncioTestCase):
 async def asyncSetUp(self):
  uri=os.environ['MONGODB_URI'];assert 'quota-test-mongo' in uri
  self.client=AsyncIOMotorClient(uri);self.db=self.client.tweet_test;await self.client.drop_database('tweet_test')
  self.at=datetime(2026,9,14,12);self.stack=ExitStack()
  for name in ('players','rumors'):self.stack.enter_context(patch.object(r,name,self.db[name]))
  self.stack.enter_context(patch.object(r,'now',lambda:self.at))
  self.stack.enter_context(patch.object(r,'rule',lambda key,default=None:12 if key=='tweets.cooldown_hours' else default))
  self.stack.enter_context(patch.object(r,'send_system_message',AsyncMock()))
  self.stack.enter_context(patch.object(r,'apply_production',lambda p:p))
  await self.db.players.insert_many([{'tg_id':i,'name':str(i),'resources':{'gold':1000},'last_tick':self.at,'popularity':50} for i in (1,2,3)])
 async def asyncTearDown(self):self.stack.close();self.client.close()
 async def send(self,uid,target=3):return await r.send_rumor(r.RumorBody(target_tg_id=target,text='متن آزمایشی توییت برای بررسی محدودیت'),{'id':uid})
 async def test_other_author_blocked_without_charge_or_damage(self):
  await self.send(1)
  with self.assertRaises(HTTPException):await self.send(2)
  self.assertEqual((await self.db.players.find_one({'tg_id':2}))['resources']['gold'],1000)
  self.assertEqual(await self.db.rumors.count_documents({}),1)
 async def test_exact_twelve_hour_boundary(self):
  await self.send(1);self.at+=timedelta(hours=12,microseconds=-1)
  with self.assertRaises(HTTPException):await self.send(2)
  self.at+=timedelta(microseconds=1);await self.send(2)
  self.assertEqual(await self.db.rumors.count_documents({}),2)
 async def test_other_target_allowed(self):
  await self.send(1);await self.send(1,2)
  self.assertEqual(await self.db.rumors.count_documents({}),2)
 async def test_existing_tweet_from_before_upgrade_protects_target(self):
  await self.db.rumors.insert_one({'author_tg_id':1,'target_tg_id':3,'created_at':self.at-timedelta(hours=11)})
  with self.assertRaises(HTTPException):await self.send(2)
