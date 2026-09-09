import os
import unittest
from datetime import datetime
from uuid import uuid4
from unittest.mock import patch, AsyncMock
from fastapi import HTTPException
from db import db, client
import family as f
import marriage_pacts as mp

class MarriagePacts(unittest.IsolatedAsyncioTestCase):
    async def test_pacts_money_permissions_and_recovery(self):
        if os.environ.get('DB_NAME') != 'valyria_marriage_pacts_test':
            self.skipTest('Isolated database required')
        await client.drop_database('valyria_marriage_pacts_test')
        clock=datetime(2026,9,8)
        async def p(uid):return await db.players.find_one({'tg_id':uid})
        def make(uid):
            return {'tg_id':uid,'name':f'P{uid}','gender':'lord' if uid%2 else 'lady','castle':f'Castle{uid}',
                'region':'north','created_at':clock,'last_tick':clock,'resources':{'gold':2000,'wine':200,'food':1000},
                'buildings':{},'castle_buildings':{},'points':100,'alliance_count':0,'stats':{}}
        await db.players.insert_many([make(uid) for uid in range(11,19)])
        try:
            with patch('telegram_bot.push'),patch('family.now',lambda:clock),patch('game_clock.paused',return_value=False),patch('project_engine.apply_production',lambda x:x),patch('marriage_pacts.apply_production',lambda x:x):
                async def marry(a,b,penalty=500):
                    mid=str(uuid4());await f.propose(await p(a),b,mid,penalty);await f.respond(await p(b),mid,True);await f.approve(mid,True,'')
                    return await f.marriages.find_one({'_id':mid})
                m=await marry(11,12)
                pact=await db.alliances.find_one({'marriage_id':m['_id']})
                self.assertEqual(pact['type'],'full_alliance');self.assertEqual(pact['penalty_gold'],500)
                self.assertEqual(pact['wine_cost'],0)
                self.assertEqual((await p(11))['resources']['wine'],180)
                self.assertEqual((await p(12))['resources']['wine'],180)
                self.assertEqual((await p(11))['alliance_count'],1)
                from trade_pacts import trade_partners
                self.assertIn(12,[v['other_id'] for v in await trade_partners(11)])
                # Both directions are blocked on the actual roleplay handler.
                from routers.roleplay import send, RoleplayBody
                with patch('routers.roleplay.check_quota',AsyncMock()):
                    for a,b in [(11,12),(12,11)]:
                        with self.assertRaises(HTTPException) as raised:
                            await send(RoleplayBody(category='sabotage',target_tg_id=b,text='a sufficiently long sabotage role'),{'id':a})
                        self.assertEqual(raised.exception.status_code,403)
                self.assertEqual(await db.roleplays.count_documents({}),0)
                # Direct diplomatic/admin dissolution cannot bypass the marriage payment.
                from routers.admin import admin_dissolve_alliance
                from routers.diplomacy import leave
                with self.assertRaises(HTTPException):await admin_dissolve_alliance(str(pact['_id']),{'id':999})
                with self.assertRaises(HTTPException):await leave(str(pact['_id']),{'id':11})
                await db.players.update_one({'tg_id':11},{'$set':{'resources.gold':499}})
                with self.assertRaises(HTTPException):await mp.divorce(await p(11),m['_id'],500)
                self.assertEqual((await p(11))['resources']['gold'],499)
                self.assertEqual((await f.marriages.find_one({'_id':m['_id']}))['status'],'active')
                self.assertEqual((await db.alliances.find_one({'_id':pact['_id']}))['status'],'accepted')
                await db.players.update_one({'tg_id':11},{'$set':{'resources.gold':900}})
                with self.assertRaises(HTTPException):await mp.divorce(await p(11),m['_id'],1)
                other_gold=(await p(12))['resources']['gold']
                # Simulate a crash after the debit: recovery finishes once, no lost credit.
                async def interrupted(op):
                    w=op['wallets'][0]
                    await f.wallet_once(w['member'],w['cost'],f"family:{op['_id']}:0",debit=True)
                    raise RuntimeError('crash')
                with patch('family.finish',interrupted):
                    with self.assertRaises(RuntimeError):await mp.divorce(await p(11),m['_id'],500)
                self.assertEqual((await p(11))['resources']['gold'],400)
                await f.recover();await f.recover()
                await mp.divorce(await p(11),m['_id'],500)
                self.assertEqual((await p(11))['resources']['gold'],400)
                self.assertEqual((await p(12))['resources']['gold'],other_gold+500)
                self.assertEqual((await p(11))['alliance_count'],0)
                self.assertEqual((await db.alliances.find_one({'_id':pact['_id']}))['status'],'dissolved')
                self.assertFalse(await mp.spouses(await p(11),await p(12)))
                self.assertNotIn(12,[v['other_id'] for v in await trade_partners(11)])
                # A preexisting bilateral pact is reused without charging or duplicating count.
                old=await db.alliances.insert_one({'from_id':13,'to_id':14,'from_name':'P13','to_name':'P14','type':'full_alliance',
                    'created_at':clock,'status':'accepted','penalty_gold':750,'wine_cost':30,'group_id':'single'})
                await db.players.update_many({'tg_id':{'$in':[13,14]}},{'$set':{'alliance_count':1}})
                existing=await marry(13,14,600)
                self.assertEqual(existing['alliance_id'],str(old.inserted_id))
                self.assertEqual((await p(13))['alliance_count'],1)
                self.assertEqual((await db.alliances.find_one({'_id':old.inserted_id}))['penalty_gold'],600)
                # Multi-player group edges survive marriage/divorce without being spliced.
                await db.alliances.insert_many([{'from_id':15,'to_id':uid,'from_name':'P15','to_name':f'P{uid}','type':'full_alliance',
                    'created_at':clock,'status':'accepted','group_id':'shared'} for uid in (16,17)])
                group=await marry(15,16,100)
                await mp.divorce(await p(16),group['_id'],100)
                self.assertEqual(await db.alliances.count_documents({'group_id':'shared','status':'accepted'}),2)
                # API requires a positive integer amount rather than accepting omitted/invalid values.
                from routers.family import Proposal
                from pydantic import ValidationError
                for bad in [None,0,-1,1.2,True,'100']:
                    with self.assertRaises(ValidationError):Proposal(target_id=12,request_id=uuid4(),penalty_gold=bad)
                with self.assertRaises(ValidationError):Proposal(target_id=12,request_id=uuid4())
        finally:
            await client.drop_database('valyria_marriage_pacts_test')
