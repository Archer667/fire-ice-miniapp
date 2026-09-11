import os
import unittest
from contextlib import ExitStack
from unittest.mock import patch, AsyncMock
from motor.motor_asyncio import AsyncIOMotorClient
from fastapi import HTTPException
from routers import diplomacy as d
import trade_pacts

class InviteTests(unittest.IsolatedAsyncioTestCase):
    async def asyncSetUp(self):
        uri=os.environ['MONGODB_URI']
        assert 'valyria-project-test-db:27017' in uri
        self.client=AsyncIOMotorClient(uri)
        self.db=self.client.valyria_invites_test
        await self.db.players.delete_many({})
        await self.db.alliances.delete_many({})
        self.stack=ExitStack()
        for mod, name in [(d,'players'),(d,'alliances'),(trade_pacts,'alliances')]:
            self.stack.enter_context(patch.object(mod,name,self.db[name]))
        self.stack.enter_context(patch.object(d,'send_system_message',AsyncMock()))
        self.stack.enter_context(patch.object(d,'apply_production',side_effect=lambda p:p))
        self.stack.enter_context(patch.object(d,'production_fields',side_effect=lambda p:{'resources':p['resources']}))
        self.stack.enter_context(patch.object(d,'rule',side_effect=lambda key,default:default))
        for uid in range(1,5):
            await self.db.players.insert_one({'tg_id':uid,'name':str(uid),'castle':str(uid),'resources':{'wine':10000}})
        self.source=(await self.db.alliances.insert_one({'from_id':1,'to_id':2,'from_name':'1','to_name':'2','type':'trade','name':'Group','public':False,'status':'accepted','group_id':'g'})).inserted_id

    async def asyncTearDown(self):
        self.stack.close()
        self.client.close()

    async def invite(self,ids,user=1):
        return await d.invite(str(self.source),d.InviteBody(to_tg_ids=ids),{'id':user})

    async def test_pending_inheritance_duplicates_and_acceptance(self):
        result=await self.invite([2,3,3])
        self.assertEqual(result['sent_to'],1)
        self.assertEqual(result['skipped'],1)
        edge=await self.db.alliances.find_one({'to_id':3})
        self.assertEqual((edge['group_id'],edge['name'],edge['public'],edge['status']),('g','Group',False,'pending'))
        self.assertEqual(await trade_pacts.trade_partners(3),[])
        self.assertEqual((await self.db.players.find_one({'tg_id':1}))['resources']['wine'],10000-result['wine_spent'])
        await d.respond(str(edge['_id']),d.RespondBody(accept=True),{'id':3})
        self.assertEqual({p['other_id'] for p in await trade_pacts.trade_partners(3)},{1,2})
        with self.assertRaises(HTTPException): await self.invite([3])

    async def test_only_creator_active_non_marriage(self):
        with self.assertRaises(HTTPException): await self.invite([3],2)
        for change in [{'marriage_id':'m'},{'marriage_id':None,'status':'left'}]:
            await self.db.alliances.update_one({'_id':self.source},{'$set':change})
            with self.assertRaises(HTTPException): await self.invite([3])
        self.assertEqual(await self.db.alliances.count_documents({}),1)

    async def test_no_money_no_mutation(self):
        await self.db.players.update_one({'tg_id':1},{'$set':{'resources.wine':0}})
        with self.assertRaises(HTTPException): await self.invite([3])
        self.assertEqual(await self.db.alliances.count_documents({}),1)

    async def test_legacy_source_and_closed_group(self):
        await self.db.alliances.update_one({'_id':self.source},{'$unset':{'group_id':'','name':'','public':''}})
        await self.invite([3])
        edge=await self.db.alliances.find_one({'to_id':3})
        self.assertEqual(edge['group_id'],(await self.db.alliances.find_one({'_id':self.source}))['group_id'])
        await self.db.alliances.update_one({'_id':self.source},{'$set':{'status':'left'}})
        with self.assertRaises(HTTPException):
            await d.respond(str(edge['_id']),d.RespondBody(accept=True),{'id':3})
        self.assertEqual((await self.db.alliances.find_one({'to_id':3}))['status'],'pending')

    async def test_unregistered_target_excluded(self):
        await self.db.players.update_one({'tg_id':3},{'$unset':{'castle':''}})
        result=await self.invite([3,4])
        self.assertEqual(result['sent_to'],1)
        self.assertIsNone(await self.db.alliances.find_one({'to_id':3}))
