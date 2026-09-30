import os
import unittest
from datetime import datetime, timedelta
from unittest.mock import AsyncMock, patch
from contextlib import ExitStack
from bson import ObjectId
from motor.motor_asyncio import AsyncIOMotorClient
from fastapi import HTTPException
import army_groups as g
from routers import war
from battle_parties import build_parties

class AllocationTests(unittest.TestCase):
    def test_exact_per_type_losses_and_relations(self):
        rows=[{'_id':ObjectId(),'tg_id':i,'merge_group_id':'g','troops':{'spear':n,'ship':i},'equipment':{'ram':i}} for i,n in [(1,101),(2,202),(3,303)]]
        out=g.proportional_losses(rows,'troops',{'spear':101,'ship':3})
        self.assertEqual(sum(v['spear'] for v in out.values()),101)
        self.assertEqual(sum(v['ship'] for v in out.values()),3)
        self.assertEqual(sorted(v['spear'] for v in out.values()),[17,34,50])
        with self.assertRaises(HTTPException):g.proportional_losses(rows,'troops',{'spear':607})
        self.assertTrue(all(not p['hostile_to'] for p in build_parties(rows)))
        self.assertEqual(sum(sum(x.values()) for x in g.proportional_losses(rows,'equipment',{'ram':5}).values()),5)

@unittest.skipUnless(os.getenv('DB_NAME')=='army_merge_test','isolated database required')
class MergeFlowTests(unittest.IsolatedAsyncioTestCase):
    async def test_merge_move_battle_split_and_recovery(self):
        client=AsyncIOMotorClient(os.environ['MONGODB_URI']);db=client.army_merge_test
        for name in ('campaigns','players','army_groups','army_merge_requests','army_group_moves'):await db[name].delete_many({})
        at=datetime(2026,9,30,12)
        def army(uid,n=100):return {'_id':ObjectId(),'tg_id':uid,'player_name':str(uid),'player_gender':'lord','name':'army','active':True,'op_type':'garrison','troops':{'infantry':n},'equipment':{'ram':1},'power':n,'food_per_day':n,'men_committed':n,'origin_castle':'A','target_castle':'A','route_path':['A'],'created_at':at-timedelta(days=1),'arrival_at':at-timedelta(hours=1),'commander_present':uid==2}
        a,b,c=army(1),army(2,200),army(1,300)
        await db.players.insert_many([{'tg_id':1,'name':'1'},{'tg_id':2,'name':'2'}]);await db.campaigns.insert_many([a,b,c])
        with ExitStack() as stack:
            for module,name,value in [(g,'db',db),(g,'campaigns',db.campaigns),(g,'players',db.players),(g,'groups',db.army_groups),(g,'requests',db.army_merge_requests),(war,'campaigns',db.campaigns)]:stack.enter_context(patch.object(module,name,value))
            stack.enter_context(patch.object(g,'now',return_value=at));stack.enter_context(patch.object(war,'now',return_value=at))
            stack.enter_context(patch.object(war,'detect_route_encounters',AsyncMock()))
            stack.enter_context(patch.object(g,'notice',AsyncMock()))
            stack.enter_context(patch('routers.ravens.send_system_message',AsyncMock()))
            stack.enter_context(patch.object(war,'notify_campaign_departure',AsyncMock()))
            req=await g.invite(g.Invite(base_id=str(a['_id']),target_id=str(b['_id'])),{'id':1})
            self.assertEqual(await db.army_groups.count_documents({}),0)
            with self.assertRaises(HTTPException):await g.reply(req['request_id'],g.Reply(accept=True),{'id':99})
            await db.campaigns.update_one({'_id':b['_id']},{'$set':{'arrival_at':at+timedelta(hours=1)}})
            with self.assertRaises(HTTPException):await g.reply(req['request_id'],g.Reply(accept=True),{'id':2})
            await db.campaigns.update_one({'_id':b['_id']},{'$set':{'arrival_at':at-timedelta(hours=1)}})
            result=await g.reply(req['request_id'],g.Reply(accept=True),{'id':2})
            group=await g.group_for(str(a['_id']));self.assertTrue(group)
            await g.invite(g.Invite(base_id=str(a['_id']),target_id=str(c['_id'])),{'id':1})
            group=await g.group_for(str(a['_id']))
            rows=await g.members(group)
            self.assertEqual(g.totals(rows)[0],{'infantry':600})
            self.assertEqual([r['tg_id'] for r in sorted(rows,key=lambda r:r['men_committed'])],[1,2,1])
            self.assertTrue(next(r for r in rows if r['tg_id']==2)['commander_present'])
            await g.recover_moves();self.assertEqual(len((await db.campaigns.find_one({'_id':a['_id']}))['movement_history']),2)
            body=war.MoveCampaignBody(target_castle='B',op_type='garrison',via=['A','B'])
            with self.assertRaises(HTTPException):await g.move_group(group,body,{'id':2})
            for name,value in [('get_war_window',{'open':True}),('all_castle_names_and_ports',({'A','B'},set())),('owner_of_castle',None),('all_castle_terrain',{'A':'land','B':'land'}),('blocked_castles_for',set()),('reject_hostile_order_during_pact',None)]:stack.enter_context(patch.object(war,name,AsyncMock(return_value=value)))
            stack.enter_context(patch.object(war,'travel_routes',return_value=[{'path':['A','B'],'minutes':30,'via_sea':False}]))
            stack.enter_context(patch.object(war,'TRAVEL_GRAPH',{'A':{'B':30},'B':{'A':30}}))
            await g.move_group(await g.group_for(str(a['_id'])),body,{'id':1})
            rows=await g.members(group);self.assertEqual(len({r['arrival_at'] for r in rows}),1)
            self.assertEqual({r['target_castle'] for r in rows},{'B'})
            with self.assertRaises(HTTPException):await g.leave(result['group_id'],{'id':2})
            # A battle locks the entire formation and preserves ownership/roster.
            bid=str(ObjectId());from encounter_runtime import halt
            root=rows[0]
            await halt(war,root,{'kind':'castle','castle':'B'},at,bid,str(root['_id']),True)
            await db.campaigns.update_one({'_id':root['_id']},{'$set':{'battle_attacker_army_ids':[str(root['_id'])],'battle_defender_army_ids':[],'battle_open':True}})
            joined=await g.attach_battle_group(await db.campaigns.find_one({'_id':root['_id']}))
            self.assertEqual(len(joined['battle_attacker_army_ids']),3)
            self.assertEqual(await db.campaigns.count_documents({'engagement_campaign_id':bid,'engagement_locked':True}),3)
            with self.assertRaises(HTTPException):await g.leave(result['group_id'],{'id':1})
            losses={str(root['_id']):{'infantry':60}};eq={}
            await g.distribute_battle_losses(await g.members(group),losses,eq)
            self.assertEqual(sorted(v['infantry'] for v in losses.values()),[10,20,30])
            await db.campaigns.update_many({}, {'$set':{'engagement_locked':False,'battle_cancelled_at':at,'arrival_at':at}})
            await g.leave(result['group_id'],{'id':2})
            self.assertFalse((await db.campaigns.find_one({'_id':b['_id']})).get('merge_group_id'))
            self.assertEqual(len(await g.members(await g.group_for(str(a['_id'])))),2)
            await g.leave(result['group_id'],{'id':1})
            self.assertEqual(await db.campaigns.count_documents({'merge_group_id':{'$exists':True}}),0)
            self.assertEqual(g.totals(await db.campaigns.find({}).to_list(None))[0],{'infantry':600})
        client.close()
