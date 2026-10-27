"""Malformed persisted campaigns cannot break the panel or arrival processing."""
import unittest
from contextlib import ExitStack
from copy import deepcopy
from datetime import datetime,timedelta
from unittest.mock import AsyncMock,patch
from mongomock_motor import AsyncMongoMockClient
from bson import ObjectId
from routers import admin,war
from campaign_integrity import display_issues,movement_issues


class PanelIntegrityTests(unittest.IsolatedAsyncioTestCase):
    async def asyncSetUp(self):
        self.db=AsyncMongoMockClient()['panel_integrity_test']
        self.stack=ExitStack();self.addCleanup(self.stack.close)
        self.stack.enter_context(patch.object(admin,'campaigns',self.db.campaigns))
        self.stack.enter_context(patch.object(war,'campaigns',self.db.campaigns))
        self.now=datetime(2026,10,27)
        self.valid={'_id':ObjectId(),'tg_id':99,'player_name':'Lord','name':'Guard','active':True,
            'origin_castle':'A','target_castle':'A','op_type':'defend','troops':{'infantry':30},
            'equipment':{},'created_at':self.now,'arrival_at':self.now-timedelta(hours=1),
            'gold_cost':20,'men_committed':30,'travel_minutes':0}

    async def test_campaign_list_keeps_invalid_record_and_valid_army(self):
        invalid={'_id':ObjectId(),'tg_id':1,'active':True,'arrival_at':self.now-timedelta(days=1)}
        await self.db.campaigns.insert_many([invalid,deepcopy(self.valid)])
        self.stack.enter_context(patch.object(admin,'_admin_army_metrics',AsyncMock(return_value={'power':10})))
        self.stack.enter_context(patch.object(admin,'_admin_castle_defenses',AsyncMock(return_value={})))
        rows=await admin.list_campaigns({'id':1})
        bad=next(r for r in rows if r['id']==str(invalid['_id']))
        good=next(r for r in rows if r['id']==str(self.valid['_id']))
        self.assertIn('troops',bad['data_issues'])
        self.assertIn('origin_castle',bad['data_issues'])
        self.assertNotIn('troops',bad)
        self.assertEqual(good['troops'][0]['count'],30)
        self.assertEqual(await self.db.campaigns.find_one({'_id':invalid['_id']}),invalid)

    async def test_arrival_skips_incomplete_record_but_processes_following_army(self):
        bad={'_id':ObjectId(),'active':True,'arrival_at':self.now-timedelta(days=1),'tg_id':7}
        await self.db.campaigns.insert_many([bad,deepcopy(self.valid)])
        for name in ('reconcile_battle_locks','repair_open_battle_rosters','process_route_ambushes','detect_route_encounters'):
            self.stack.enter_context(patch.object(war,name,AsyncMock()))
        self.stack.enter_context(patch.object(war,'now',lambda:self.now))
        self.stack.enter_context(patch.object(war,'owner_of_castle',AsyncMock(return_value=None)))
        self.stack.enter_context(patch.object(war,'send_system_message',AsyncMock()))
        with self.assertLogs('routers.war',level='WARNING'):
            await war.notify_arrivals()
        self.assertEqual(await self.db.campaigns.find_one({'_id':bad['_id']}),bad)
        self.assertTrue((await self.db.campaigns.find_one({'_id':self.valid['_id']}))['arrival_notified'])

    def test_valid_roster_preserved_and_invalid_values_are_reported(self):
        from bson.int64 import Int64
        self.assertEqual(movement_issues({**self.valid,'tg_id':Int64(1000000000011)}),[])
        self.assertEqual(display_issues(self.valid),[])
        for troops in (None,[],{'infantry':'30'},{'infantry':-1},{'infantry':float('inf')},{'infantry':True}):
            self.assertIn('troops',movement_issues({**self.valid,'troops':troops}))
        self.assertEqual(self.valid['troops'],{'infantry':30})
