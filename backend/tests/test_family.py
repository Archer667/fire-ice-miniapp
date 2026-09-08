import os
import unittest
from datetime import datetime, timedelta
from unittest.mock import patch
from uuid import uuid4
from fastapi import HTTPException
from db import db, client
import family as f


class FamilyIntegration(unittest.IsolatedAsyncioTestCase):
    async def test_family_lifecycle_and_succession(self):
        if os.environ.get('DB_NAME') != 'valyria_family_test':
            self.skipTest('Requires isolated family database')
        await client.drop_database('valyria_family_test')
        clock = [datetime(2026, 9, 1)]
        from game_data import REGIONS
        region = next(k for k,v in REGIONS.items() if len(v['castles']) >= 4)
        castles = REGIONS[region]['castles'][:4]
        def make(uid, gender, castle):
            return {'tg_id':uid,'name':f'Player {uid}','gender':gender,'castle':castle,'region':region,
                    'created_at':clock[0], 'last_tick':clock[0], 'resources':{'gold':1000,'wine':200,'food':1000},
                    'buildings':{'farm':{'level':3}},'castle_buildings':{},'troops':{'sword':10},
                    'points':123,'stats':{'attack_wins':3},'medals':{'special':[]},'popularity':50}
        await db.players.insert_many([make(11,'lord',castles[0]),make(12,'lady',castles[1]),make(13,'lord',castles[2]),make(14,'lady',castles[3])])
        async def p(uid): return await db.players.find_one({'tg_id':uid})
        try:
            with patch('family.now', lambda: clock[0]), patch('project_engine.now', lambda: clock[0]), patch('game.now', lambda: clock[0]), patch('character_records.apply_production',lambda p:p), patch('family.apply_production',lambda p:p), patch('project_engine.apply_production',lambda p:p), patch('game_clock.paused', return_value=False), patch('telegram_bot.push'):
                # Proposer only pays their half; retries and cancellation refund once.
                mid=str(uuid4()); first=await p(11)
                await f.propose(first,12,mid)
                self.assertEqual((await p(11))['resources']['gold'],900)
                self.assertEqual((await p(12))['resources']['gold'],1000)
                await f.propose(await p(11),12,mid)
                self.assertEqual((await p(11))['resources']['gold'],900)
                with self.assertRaises(HTTPException): await f.propose(await p(13),12,str(uuid4()))
                with self.assertRaises(HTTPException): await f.respond(await p(13),mid,True)
                await f.respond(await p(12),mid,False)
                await f.recover()
                self.assertEqual((await p(11))['resources']['gold'],1000)
                mid=str(uuid4());await f.propose(await p(11),12,mid);await f.respond(await p(12),mid,True)
                self.assertEqual((await p(12))['resources']['gold'],900)
                await f.approve(mid,True,'')
                m=await f.marriages.find_one({'_id':mid}); plan=m['birth_plan']
                self.assertIn(len(plan),[2,3,4]);self.assertNotEqual(plan[0]['side'],plan[1]['side'])
                if len(plan)==4:self.assertNotEqual(plan[2]['side'],plan[3]['side'])
                previous=m['started_at']
                for b in plan:
                    self.assertGreaterEqual((b['at']-previous).total_seconds(),86400)
                    self.assertLessEqual((b['at']-previous).total_seconds(),172800);previous=b['at']
                self.assertNotIn('birth_plan',f.clean(m))
                # Pause must not process even overdue births.
                clock[0]=plan[0]['at']
                with patch('game_clock.paused',return_value=True):await f.tick()
                self.assertEqual(await f.children.count_documents({}),0)
                await f.tick();await f.tick()
                self.assertEqual(await f.children.count_documents({}),1)
                c=await f.children.find_one({}); patron=await p(c['patron_id']); other=await p(12 if c['patron_id']==11 else 11)
                self.assertEqual(c['residence'],patron['castle'])
                self.assertEqual(c['adult_at']-c['born_at'],timedelta(hours=96))
                with self.assertRaises(HTTPException):await f.child_action(other,c['_id'],name='Wrong')
                await f.child_action(patron,c['_id'],name='ÙˆØ§Ø±Ø« Ø¢Ø²Ù…Ø§ÛŒØ´ÛŒ')
                before=patron['resources']['gold'];other_before=other['resources']['gold']
                await f.child_action(patron,c['_id'],stage=0,specialty='economy')
                await f.child_action(await p(patron['tg_id']),c['_id'],stage=0,specialty='economy')
                self.assertEqual((await p(patron['tg_id']))['resources']['gold'],before-25)
                self.assertEqual((await p(other['tg_id']))['resources']['gold'],other_before)
                # Lost castle follows the responsible character's new main castle.
                await db.players.update_one({'tg_id':patron['tg_id']},{'$set':{'castle':'Moved main'}})
                await f.tick();self.assertEqual((await f.children.find_one({'_id':c['_id']}))['residence'],'Moved main')
                await db.players.update_one({'tg_id':patron['tg_id']},{'$set':{'castle':patron['castle']}})
                # An interrupted wallet operation is replayed without a second debit.
                clock[0]=c['born_at']+timedelta(hours=24)
                original=f.finish
                async def interrupted(op):
                    w=op['wallets'][0]
                    await f.wallet_once(w['member'],w['cost'],f"family:{op['_id']}:0",debit=True)
                    raise RuntimeError('simulated crash after wallet write')
                with patch('family.finish',interrupted):
                    with self.assertRaises(RuntimeError):await f.child_action(await p(patron['tg_id']),c['_id'],stage=1)
                balance=(await p(patron['tg_id']))['resources']['gold']
                await f.recover();await f.recover()
                self.assertEqual((await p(patron['tg_id']))['resources']['gold'],balance)
                self.assertIn('1',(await f.children.find_one({'_id':c['_id']}))['training'])
                # Mature heir retains all gameplay and project payout eligibility.
                clock[0]=c['adult_at'];await f.tick()
                old=await p(patron['tg_id']); uid=old['tg_id']; c=await f.children.find_one({'_id':c['_id']})
                self.assertIsNotNone((await f.preview(old))['heir'])
                with self.assertRaises(HTTPException):await f.child_action(old,c['_id'],name='Too late')
                await db.campaigns.insert_one({'tg_id':uid,'active':True,'troops':{'sword':10}})
                await db.projects.insert_one({'_id':'family-project','status':'active','owner_id':uid,'owner_name':old['name'],
                    'members':{str(uid):f.member_for(old,3)},'name':'test project'})
                from routers.characters import RetireBody
                from character_records import retire
                from ranks import base_score
                expected=base_score(old)
                await db.caravans.insert_one({'tg_id':other['tg_id'],'target_tg_id':uid,'target_name':old['name'],'active':True,'target_character_created_at':old['created_at']})
                await db.player_market_listings.insert_one({'seller_tg_id':uid,'seller_name':old['name'],'qty':10})
                result=await retire(uid,RetireBody(action='death',reason='test',character_key=f.key(old)),999)
                self.assertTrue(result['succession'])
                current=await p(uid)
                self.assertEqual(current['name'],'ÙˆØ§Ø±Ø« Ø¢Ø²Ù…Ø§ÛŒØ´ÛŒ');self.assertNotEqual(current['created_at'],old['created_at'])
                for field in ['castle','buildings','castle_buildings','points','stats','medals','troops']:
                    self.assertEqual(current[field],old[field],field)
                self.assertEqual(base_score(current),expected)
                self.assertTrue((await db.campaigns.find_one({'tg_id':uid}))['active'])
                project=await db.projects.find_one({'_id':'family-project'})
                self.assertEqual(project['status'],'active')
                self.assertEqual(project['members'][str(uid)]['character_created_at'],current['created_at'])
                self.assertEqual((await db.caravans.find_one({'target_tg_id':uid}))['target_character_created_at'],current['created_at'])
                self.assertEqual((await db.player_market_listings.find_one({'seller_tg_id':uid}))['seller_name'],current['name'])
                gold=current['resources']['gold']
                await f.wallet_once(project['members'][str(uid)],{'gold':40},'after-succession')
                self.assertEqual((await p(uid))['resources']['gold'],gold+40)
                await db.family_successions.update_one({'tg_id':uid},{'$set':{'complete':False}})
                await f.recover()
                self.assertEqual((await p(uid))['resources']['gold'],gold+40)
                self.assertEqual(await db.character_archives.count_documents({'tg_id':uid}),1)
                self.assertEqual((await f.marriages.find_one({'_id':mid}))['status'],'ended')
                count=await f.children.count_documents({});clock[0]+=timedelta(days=20);await f.tick()
                self.assertEqual(await f.children.count_documents({}),count)
                # Full lineage death affects own heirs only, frees castles and fails project.
                own_key=f.key(await p(uid)); other_key=f.key(await p(other['tg_id']))
                await f.children.insert_many([{'_id':'own-reserve','patron_key':own_key,'status':'alive','adult_at':clock[0], 'born_at':clock[0], 'name':'Reserve'},
                                             {'_id':'other-reserve','patron_key':other_key,'status':'alive','adult_at':clock[0], 'born_at':clock[0], 'name':'Other'}])
                with patch('routers.admin.apply_production',lambda p:p):
                    await retire(uid,RetireBody(action='death',reason='lineage',kill_heirs=True),999)
                self.assertIsNone((await p(uid))['castle'])
                self.assertTrue((await p(uid))['registration_reset'])
                self.assertEqual((await f.children.find_one({'_id':'own-reserve'}))['status'],'dead')
                self.assertEqual((await f.children.find_one({'_id':'other-reserve'}))['status'],'alive')
                self.assertEqual((await db.projects.find_one({'_id':'family-project'}))['status'],'failed')
                # Full/owner administration only; invalid settings and protected routes.
                import httpx
                from fastapi import FastAPI
                from routers.family import router
                from auth import get_user
                app=FastAPI();app.include_router(router);app.dependency_overrides[get_user]=lambda:{'id':13}
                async with httpx.AsyncClient(transport=httpx.ASGITransport(app=app),base_url='http://test') as http:
                    self.assertEqual((await http.get('/api/admin/family')).status_code,403)
                    self.assertEqual((await http.post('/api/family/children/other-reserve',json={'name':'Hijack'})).status_code,403)
                    app.dependency_overrides[get_user]=lambda:{'id':999}
                    self.assertEqual((await http.post('/api/admin/family/settings',json={**f.DEFAULTS,'marriage_gold':201})).status_code,400)
                # Expiry refunds both reservations once; low funds create no wedding.
                pending=str(uuid4());await f.propose(await p(13),14,pending);await f.respond(await p(14),pending,True)
                balances=[(await p(i))['resources']['gold'] for i in (13,14)]
                clock[0]+=timedelta(hours=73)
                m=await f.marriages.find_one({'_id':pending})
                self.assertLess(m['expires_at'],clock[0])
                await f.close_marriage(m,'expired','test deadline')
                await f.recover()
                self.assertEqual([(await p(i))['resources']['gold'] for i in (13,14)],[v+100 for v in balances])
                await db.players.update_one({'tg_id':14},{'$set':{'resources.gold':0}})
                with self.assertRaises(HTTPException):await f.propose(await p(14),13,str(uuid4()))
                self.assertIsNone(await f.marriages.find_one({'parent_keys':f.key(await p(14)),'status':{'$in':f.OPEN}}))
                # A minor never keeps the account active on death.
                minor={'_id':'minor-only','name':'Minor','status':'alive','patron_key':f.key(await p(13)),
                       'adult_at':clock[0]+timedelta(days=1),'born_at':clock[0]-timedelta(days=3)}
                await f.children.insert_one(minor)
                check=await f.preview(await p(13));self.assertTrue(check['has_minors']);self.assertIsNone(check['heir'])
                await retire(13,RetireBody(action='death',reason='no adult'),999)
                self.assertTrue((await p(13))['registration_reset'])
                self.assertEqual((await f.children.find_one({'_id':'minor-only'}))['status'],'retired')
        finally:
            await client.drop_database('valyria_family_test')
