import unittest
from datetime import datetime,timedelta
from contextlib import ExitStack
from unittest.mock import AsyncMock,patch
from fastapi import HTTPException
import character_travel as t
from routers import character_travel as routes

class TravelRules(unittest.TestCase):
    def test_both_host_groups_must_accept(self):
        self.assertFalse(t.accepted({'owner':[1],'institution':[2,3]},[2]))
        self.assertTrue(t.accepted({'owner':[1],'institution':[2,3]},[1,3]))
        self.assertTrue(t.accepted({'owner':[1],'institution':[1,3]},[1]))
        self.assertFalse(t.accepted({'institution':[]},[1]))
        self.assertTrue(t.accepted({},[]))

    def test_redirect_from_actual_edge_position(self):
        at=datetime(2026,1,1,12)
        graph={'A':{'B':10},'B':{'A':10,'C':20},'C':{'B':20}}
        def shortest(a,b):
            if a==b:return 0,[a]
            if a=='A':return 30,['A','B','C']
            return 20,['B','C']
        old={'started_at':at-timedelta(minutes=4),'segments':[{'a':'A','b':'B','minutes':10}]}
        with patch.object(t,'TRAVEL_GRAPH',graph),patch.object(t,'now',return_value=at),patch.object(t,'_dijkstra_path',side_effect=shortest):
            duration,segments=t.route('A','C',old)
        self.assertEqual(duration,26)
        self.assertEqual(segments[0]['start_position'],.4)
        self.assertEqual(segments[0]['end_position'],1)

    def test_second_redirect_keeps_fraction(self):
        at=datetime(2026,1,1,12)
        old={'started_at':at-timedelta(minutes=2),'segments':[{'a':'A','b':'B','minutes':6,'start_position':.4,'end_position':1}]}
        with patch.object(t,'TRAVEL_GRAPH',{'A':{'B':10},'B':{'A':10}}),patch.object(t,'now',return_value=at),patch.object(t,'_dijkstra_path',side_effect=lambda a,b:(0,[a]) if a==b else (10,[a,b])):
            duration,_=t.route('A','B',old)
        self.assertAlmostEqual(duration,4)

class TravelActions(unittest.IsolatedAsyncioTestCase):
    def setUp(self):
        self.stack=ExitStack();self.addCleanup(self.stack.close)
        self.p={'tg_id':1,'name':'لرد','created_at':datetime(2026,1,1),'castle':'A','castle_buildings':{}}
        self.row={'_id':'trip','tg_id':1,'character':t.key(self.p),'origin':'A','target':'B','children':['kid'],'approvals':[2]}
        self.s={'_id':t.key(self.p),'place':'A','trip':None,'captive':None}
        for name,value in [('living',self.p),('state',self.s),('destination',{'node':'B'}),('gates',{'owner':[2]}),('blocked',False),('kids',[{'child_id':'kid','available':True}])]:
            self.stack.enter_context(patch.object(t,name,AsyncMock(return_value=value)))
        self.stack.enter_context(patch.object(t,'route',return_value=(10,[])))
        self.writer=self.stack.enter_context(patch.object(t,'commit',AsyncMock()))
        self.stack.enter_context(patch.object(t,'trips',AsyncMock()))

    async def test_charges_ten_per_person(self):
        await t.start(self.row)
        op=self.writer.call_args.args[0]
        self.assertEqual(op['wallets'][0]['cost'],{'wine':20})
        self.assertEqual(len(op['changes']),3)

    async def test_landless_costs_nothing(self):
        self.p.update(castle=None,landless=True)
        await t.start(self.row)
        self.assertEqual(self.writer.call_args.args[0]['wallets'],[])

    async def test_captive_cannot_depart(self):
        self.s['captive']={'host_id':2}
        with self.assertRaises(HTTPException):await t.start(self.row)
        self.writer.assert_not_awaited()

    async def test_war_blocks_departure(self):
        t.blocked.return_value=True
        with self.assertRaises(HTTPException):await t.start(self.row)
        self.writer.assert_not_awaited()

    async def test_child_cannot_be_taken_from_other_location(self):
        t.kids.return_value=[]
        with self.assertRaises(HTTPException):await t.start(self.row)
        self.writer.assert_not_awaited()

    async def test_changed_owner_requires_new_permission(self):
        t.gates.return_value={'owner':[99]}
        with self.assertRaises(HTTPException):await t.start(self.row)
        self.writer.assert_not_awaited()

    async def test_changed_character_rejects_old_request(self):
        self.row['character']='previous-character'
        with self.assertRaises(HTTPException):await t.start(self.row)
        self.writer.assert_not_awaited()

    async def test_pause_does_not_arrive(self):
        with patch.object(t,'recover',AsyncMock()),patch.object(t.game_clock,'paused',return_value=True):
            await t.tick()
        t.trips.find.assert_not_called()

    async def test_unrelated_player_cannot_approve(self):
        t.trips.find_one.return_value={**self.row,'status':'pending'}
        with self.assertRaises(HTTPException) as error:await t.respond(99,'trip',True)
        self.assertEqual(error.exception.status_code,403)
        self.writer.assert_not_awaited()

    async def test_full_admin_required(self):
        with patch.object(routes,'get_full_admin',AsyncMock(side_effect=HTTPException(403,'denied'))):
            with self.assertRaises(HTTPException):await routes.admin({'id':1})
