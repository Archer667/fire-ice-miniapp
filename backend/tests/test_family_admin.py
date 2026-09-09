import os
import unittest
from datetime import datetime, timedelta, timezone
from uuid import uuid4
from unittest.mock import patch
from fastapi import HTTPException, FastAPI
from db import db, client
import family as f
import family_admin as control

class FamilyAdminTests(unittest.IsolatedAsyncioTestCase):
    async def test_controls_access_recovery_and_invariants(self):
        if os.environ.get('DB_NAME') != 'valyria_family_admin_test':
            self.skipTest('Requires disposable family admin database')
        await client.drop_database('valyria_family_admin_test')
        clock=[datetime(2026,9,8)]
        async def p(uid):return await db.players.find_one({'tg_id':uid})
        def make(uid):
            return {'tg_id':uid,'name':f'P{uid}','gender':'lord' if uid%2 else 'lady',
                'castle':f'Castle{uid}','region':'north','created_at':clock[0],'last_tick':clock[0],
                'resources':{'gold':2000,'wine':200,'food':1000},'buildings':{},'castle_buildings':{},'stats':{}}
        await db.players.insert_many([make(i) for i in (11,12,13,14)])
        try:
            with patch('telegram_bot.push'),patch('family.now',lambda:clock[0]),patch('family_admin.now',lambda:clock[0]),patch('game_clock.paused',return_value=False),patch('project_engine.apply_production',lambda p:p),patch('family_admin.apply_production',lambda p:p):
                mid=str(uuid4())
                await f.propose(await p(11),12,mid,500);await f.respond(await p(12),mid,True);await f.approve(mid,True,'')
                await control.penalty(mid,0,700,'adjusted by admin',999)
                self.assertEqual((await db.alliances.find_one({'marriage_id':mid}))['penalty_gold'],700)
                self.assertEqual((await p(11))['resources']['gold'],1900)
                with self.assertRaises(HTTPException):await control.penalty(mid,0,800,'stale',999)
                with self.assertRaises(HTTPException):await control.penalty(mid,1,800,' ',999)
                from routers.family import BirthDate, ChildMove, router
                m=await f.marriages.find_one({'_id':mid})
                dates=[BirthDate(child_id=b['id'],at=(clock[0]+timedelta(hours=5+i*3)).replace(tzinfo=timezone.utc)) for i,b in enumerate(m['birth_plan'])]
                await control.schedule(mid,1,dates,'earlier event',999)
                self.assertEqual((await f.marriages.find_one({'_id':mid}))['birth_plan'][0]['at'],clock[0]+timedelta(hours=5))
                with self.assertRaises(HTTPException):await control.schedule(mid,2,list(reversed([BirthDate(child_id=d.child_id,at=clock[0].replace(tzinfo=timezone.utc)) for d in dates])),'past',999)
                clock[0]+=timedelta(hours=5);await f.tick()
                c=await f.children.find_one({'marriage_id':mid});self.assertIsNotNone(c)
                with self.assertRaises(HTTPException):await control.schedule(mid,2,dates,'already born',999)
                patron=await p(c['patron_id']);target=await p(12 if c['patron_id']==11 else 11)
                await f.child_action(patron,c['_id'],name='My Child');await f.child_action(patron,c['_id'],stage=0)
                before=await f.children.find_one({'_id':c['_id']})
                body=ChildMove(revision=0,expected_patron_key=c['patron_key'],parent_key=f.key(target),castle=target['castle'],reason='custody change')
                await control.move(c['_id'],body,999)
                moved=await f.children.find_one({'_id':c['_id']})
                for field in ('name','born_at','adult_at','training','parents'):
                    self.assertEqual(before[field],moved[field],field)
                self.assertEqual(moved['patron_id'],target['tg_id'])
                self.assertEqual(moved['residence'],target['castle'])
                with self.assertRaises(HTTPException):await control.move(c['_id'],body,999)
                with self.assertRaises(HTTPException):await f.child_action(patron,c['_id'],name='not my child')
                await f.child_action(target,c['_id'],name='New name')
                clock[0]=moved['adult_at']
                self.assertIn(c['_id'],[x['id'] for x in (await f.preview(target))['children']])
                self.assertNotIn(c['_id'],[x['id'] for x in (await f.preview(patron))['children']])
                # API role guard applies to every override and read of future births.
                from auth import get_user
                import httpx
                app=FastAPI();app.include_router(router);app.dependency_overrides[get_user]=lambda:{'id':13}
                await db.admin_roles.insert_one({'tg_id':13,'role':'limited'})
                endpoints=[(f'/api/admin/family/marriages/{mid}/penalty',{'revision':2,'reason':'test','penalty_gold':900}),
                    (f'/api/admin/family/marriages/{mid}/divorce',{'revision':2,'reason':'test'}),
                    (f'/api/admin/family/marriages/{mid}/schedule',{'revision':2,'reason':'test','births':[{'child_id':dates[0].child_id.hex,'at':dates[0].at.isoformat()}]}),
                    (f"/api/admin/family/children/{c['_id']}/move",body.model_dump())]
                async with httpx.AsyncClient(transport=httpx.ASGITransport(app=app),base_url='http://test') as http:
                    self.assertEqual((await http.get('/api/admin/family')).status_code,403)
                    for url,data in endpoints:self.assertEqual((await http.post(url,json=data)).status_code,403)
                    app.dependency_overrides[get_user]=lambda:{'id':999}
                    result=await http.post(f'/api/admin/family/marriages/{mid}/penalty',json={'revision':2,'reason':'authorized','penalty_gold':750})
                    self.assertEqual(result.status_code,200,result.text)
                await db.players.update_one({'tg_id':11},{'$set':{'resources.gold':700}})
                with self.assertRaises(HTTPException):await control.force_divorce(mid,3,11,'insufficient',999)
                self.assertEqual((await f.marriages.find_one({'_id':mid}))['status'],'active')
                await db.players.update_one({'tg_id':11},{'$set':{'resources.gold':1000}})
                receiver_before=(await p(12))['resources']['gold']
                async def crash(op):
                    w=op['wallets'][0]
                    await f.wallet_once(w['member'],w['cost'],f"family:{op['_id']}:0",debit=True)
                    raise RuntimeError('simulated crash')
                with patch('family.finish',crash):
                    with self.assertRaises(RuntimeError):await control.force_divorce(mid,3,11,'court ruling',999)
                await f.recover();await f.recover()
                self.assertEqual((await p(11))['resources']['gold'],250)
                self.assertEqual((await p(12))['resources']['gold'],receiver_before+750)
                self.assertEqual((await db.alliances.find_one({'marriage_id':mid}))['status'],'dissolved')
                self.assertEqual((await f.children.find_one({'_id':c['_id']}))['status'],'alive')
                with self.assertRaises(HTTPException):await control.force_divorce(mid,3,None,'duplicate',999)
                # Waiver is explicit and never charges either account.
                fresh=str(uuid4());await f.propose(await p(11),12,fresh,200);await f.respond(await p(12),fresh,True);await f.approve(fresh,True,'')
                gold=[(await p(i))['resources']['gold'] for i in (11,12)]
                await control.force_divorce(fresh,0,None,'waived',999)
                self.assertEqual([(await p(i))['resources']['gold'] for i in (11,12)],gold)
                self.assertEqual((await f.marriages.find_one({'_id':fresh}))['admin_penalty_paid'],0)
                self.assertGreater(await db.family_notices.count_documents({'text':{'$regex':'دلیل مدیریت'}}),0)
        finally:
            await client.drop_database('valyria_family_admin_test')
