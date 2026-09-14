import os,unittest
from datetime import datetime,timedelta
from contextlib import ExitStack
from unittest.mock import patch,AsyncMock
from motor.motor_asyncio import AsyncIOMotorClient
from fastapi import HTTPException
import system_reports as q
class SeasonQuotaTests(unittest.IsolatedAsyncioTestCase):
 async def asyncSetUp(self):
  uri=os.environ['MONGODB_URI'];assert 'quota-test-mongo' in uri
  self.client=AsyncIOMotorClient(uri);self.db=self.client.quota_test
  await self.client.drop_database('quota_test')
  self.start=datetime(2026,9,4,20,31,35);self.at=self.start
  await self.db.game_settings.insert_one({'_id':'season_clock','started_at':self.start})
  self.stack=ExitStack()
  self.stack.enter_context(patch.object(q,'db',self.db));self.stack.enter_context(patch.object(q,'game_settings',self.db.game_settings))
  self.stack.enter_context(patch.object(q,'season_day',AsyncMock()))
  self.stack.enter_context(patch.object(q,'now',lambda:self.at))
 async def asyncTearDown(self):self.stack.close();self.client.close()
 async def roll(self,uid,category,at):
  return (await self.db.roleplays.insert_one({'tg_id':uid,'category':category,'created_at':at})).inserted_id
 async def test_week_boundaries_not_monday(self):
  for days,index in [(0,1),(3,1),(6,1),(7,2),(13,2),(14,3),(21,4),(28,5)]:
   self.at=self.start+timedelta(days=days);w=await q.quota_window()
   self.assertEqual(w['week_number'],index);self.assertEqual(w['week_start'],self.start+timedelta(days=(index-1)*7))
  self.at=self.start+timedelta(days=7,microseconds=-1)
  self.assertEqual((await q.quota_window())['week_number'],1)
 async def test_shared_categories_and_new_week(self):
  for cat in ('sabotage','other','economy','war','scout'):
   await self.roll(1,cat,self.start)
  self.assertEqual(await q.usage(1,'roleplays'),3)
  with self.assertRaises(HTTPException):await q.check_quota(1,'roleplays')
  self.at=self.start+timedelta(days=7)
  self.assertEqual(await q.usage(1,'roleplays'),0)
  await self.roll(1,'diplomacy',self.at)
  self.assertEqual(await q.usage(1,'roleplays'),1)
 async def test_receipt_idempotent_and_deleted_roll_still_consumed(self):
  oid=await self.roll(1,'sabotage',self.start)
  await q.consume(1,'roleplays',oid)
  self.assertEqual(await q.usage(1,'roleplays'),1)
  await self.db.roleplays.delete_one({'_id':oid})
  self.assertEqual(await q.usage(1,'roleplays'),1)
 async def test_late_player_shares_same_reset(self):
  self.at=self.start+timedelta(days=6)
  await self.roll(2,'other',self.at)
  self.assertEqual(await q.usage(2,'roleplays'),1)
  self.at=self.start+timedelta(days=7)
  self.assertEqual(await q.usage(2,'roleplays'),0)
 async def test_season_reset_excludes_previous_receipts(self):
  await self.roll(1,'other',self.start);await q.usage(1,'roleplays')
  self.at=self.start+timedelta(days=2)
  await self.db.game_settings.update_one({'_id':'season_clock'},{'$set':{'started_at':self.at}})
  self.assertEqual(await q.usage(1,'roleplays'),0)
  self.assertEqual((await q.quota_window())['week_number'],1)
 async def test_projects_use_same_window_excluding_invalid(self):
  await self.db.projects.insert_many([{'owner_id':1,'created_at':self.start,'status':'pending'},{'owner_id':1,'created_at':self.start,'status':'invalid'}])
  self.assertEqual(await q.usage(1,'projects'),1)
  self.at=self.start+timedelta(days=7)
  self.assertEqual(await q.usage(1,'projects'),0)
