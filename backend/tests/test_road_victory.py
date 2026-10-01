import asyncio
import unittest
from copy import deepcopy
from datetime import timedelta
from types import SimpleNamespace
from unittest.mock import patch
from bson import ObjectId
from road_victory import decision, try_resolve, recover
from db import db, players, campaigns
from game import now
from config import STARTING_RESOURCES
import control_settings

class ThresholdTests(unittest.TestCase):
    def test_boundary_and_validation(self):
        self.assertEqual(decision(700,100,7),0)
        self.assertIsNone(decision(699,100,7))
        self.assertEqual(decision(100,701,7),1)
        self.assertIsNone(decision(0,0,7))
        self.assertIsNone(decision(float('nan'),100,7))
        for ratio in (0,1,True,1001):
            with self.assertRaises(ValueError):control_settings.validate({'war':{'road_victory_ratio':ratio}})
        self.assertEqual(control_settings.validate({'war':{'road_victory_ratio':3.5}})['war']['road_victory_ratio'],3.5)

class RoadVictoryTests(unittest.IsolatedAsyncioTestCase):
    async def test_formations_pacts_deaths_and_recovery(self):
        import road_victory
        at=now().replace(microsecond=0)
        point={'kind':'edge','a':'آنتلرز','b':'داسکندیل','position':.5,'base_minutes':10}
        w=SimpleNamespace(TRAVEL_GRAPH={})
        async def fixtures(commander=False):
            for name in await db.list_collection_names():await db[name].delete_many({})
            await db.game_settings.insert_one({'_id':'road_victory_v1','started_at':at-timedelta(seconds=1)})
            for uid in (90001,90002,90003):
                await players.insert_one({'tg_id':uid,'name':str(uid),'gender':'lord','title':'لرد','region':'crown',
                    'castle':'آنتلرز' if uid==90003 else 'داسکندیل','created_at':at-timedelta(days=5),'last_tick':at,
                    'resources':deepcopy(STARTING_RESOURCES),'buildings':{},'castle_buildings':{},'points':0,'popularity':50})
            rows=[]
            for uid,power in ((90001,350),(90002,350),(90003,100)):
                row={'_id':ObjectId(),'tg_id':uid,'name':str(uid),'player_name':str(uid),'active':True,
                    'troops':{'infantry':100},'equipment':{},'power':power,'equipment_power':0,
                    'men_committed':100,'origin_castle':'آنتلرز','target_castle':'داسکندیل',
                    'stationed_edge':{k:v for k,v in point.items() if k!='kind'},'arrival_at':at,
                    'commander_present':commander and uid==90003,'engagement_locked':False}
                rows.append(row)
            group={'_id':ObjectId(),'active':True,'leader_tg_id':90001,'army_ids':[r['_id'] for r in rows[:2]],'name':'shared'}
            for r in rows[:2]:r['merge_group_id']=str(group['_id'])
            await campaigns.insert_many(rows);await db.army_groups.insert_one(group)
            return rows
        rows=await fixtures()
        allies={90001:{90003},90002:set(),90003:{90001}}
        self.assertFalse(await try_resolve(w,rows[0],rows[2],point,at,rows,allies))
        self.assertFalse(await try_resolve(w,rows[0],rows[2],{'kind':'castle','castle':'آنتلرز'},at,rows,{}))
        third={**rows[2],'_id':ObjectId(),'tg_id':90004}
        self.assertFalse(await try_resolve(w,rows[0],rows[2],point,at,rows+[third],{}))
        self.assertTrue(await try_resolve(w,rows[0],rows[2],point,at,rows,{}))
        for uid in (90001,90002):
            p=await players.find_one({'tg_id':uid});self.assertEqual(p['stats']['attack_wins'],1)
        weak=await campaigns.find_one({'_id':rows[2]['_id']});self.assertFalse(weak['active']);self.assertEqual(weak['troops'],{})
        self.assertFalse((await players.find_one({'tg_id':90003})).get('registration_reset',False))
        op=await db.road_auto_results.find_one({});await db.road_auto_results.update_one({'_id':op['_id']},{'$set':{'status':'prepared'}})
        await recover()
        self.assertEqual((await players.find_one({'tg_id':90001}))['stats']['attack_wins'],1)
        strong=await campaigns.find_one({'_id':rows[0]['_id']});self.assertEqual(strong['troops'],rows[0]['troops']);self.assertTrue(strong['active'])
        for heir in (False,True):
            rows=await fixtures(commander=True)
            spare={**rows[2],'_id':ObjectId(),'stationed_edge':{'a':'other','b':'place','position':.2},'commander_present':False}
            await campaigns.insert_one(spare)
            p=await players.find_one({'tg_id':90003})
            if heir:
                await db.family_children.insert_one({'_id':'adult-heir','patron_key':f"90003:{p['created_at']}",'patron_id':90003,
                    'status':'alive','born_at':at-timedelta(days=5),'adult_at':at-timedelta(days=1),'name':'Heir','named':True,
                    'gender':'lady','training':{},'training_cost':{}})
            original=road_victory.kill_character
            async def crash_after_death(snapshot,op):
                await original(snapshot,op)
                raise RuntimeError('simulated crash after death')
            with patch('road_victory.kill_character',side_effect=crash_after_death):
                with self.assertRaises(RuntimeError):await try_resolve(w,rows[0],rows[2],point,at,rows, {})
            await recover();await recover()
            p=await players.find_one({'tg_id':90003})
            self.assertEqual(bool(p.get('registration_reset')),not heir)
            self.assertEqual((await campaigns.find_one({'_id':spare['_id']}))['active'],heir)
            self.assertEqual((await players.find_one({'tg_id':90001}))['stats']['attack_wins'],1)
            self.assertEqual(await db.character_archives.count_documents({}),1)
            if heir:self.assertEqual(p['name'],'Heir');self.assertEqual(p['castle'],'آنتلرز')
            self.assertEqual((await db.road_auto_results.find_one({}))['status'],'done')
