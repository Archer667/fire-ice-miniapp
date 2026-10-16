"""Exercise actual journals and wallets in memory, never against a game database."""
import copy
import unittest
from datetime import datetime,timedelta
from types import SimpleNamespace
from unittest.mock import patch,AsyncMock
from uuid import uuid4
from fastapi import HTTPException
import character_travel as t
import family
import project_engine
from tests.test_institution_bank import get,put
from routers import character_travel as routes

def matches(row,q):
    for k,v in q.items():
        if k=='$or':
            if not any(matches(row,s) for s in v):return False
            continue
        a=get(row,k)
        if isinstance(v,dict):
            for op,x in v.items():
                if op=='$exists' and (a is not None)!=x:return False
                if op=='$ne' and a==x:return False
                if op=='$in' and a not in x:return False
                if op=='$lte' and (a is None or a>x):return False
        elif not (v in a if isinstance(a,list) else a==v):return False
    return True

class Cursor:
    def __init__(self,rows):self.rows=copy.deepcopy(rows)
    def sort(self,*args):return self
    def limit(self,n):self.rows=self.rows[:n];return self
    def __aiter__(self):self.it=iter(self.rows);return self
    async def __anext__(self):
        try:return next(self.it)
        except StopIteration:raise StopAsyncIteration
class Collection:
    def __init__(self):self.rows=[]
    def find(self,q):return Cursor([r for r in self.rows if matches(r,q)])
    async def find_one(self,q):return next((copy.deepcopy(r) for r in self.rows if matches(r,q)),None)
    async def insert_one(self,row):
        if any(r.get('_id')==row.get('_id') for r in self.rows):raise AssertionError('duplicate id')
        self.rows.append(copy.deepcopy(row))
    async def update_one(self,q,u,upsert=False):
        r=next((r for r in self.rows if matches(r,q)),None);insert=False
        if r is None and upsert:r={k:v for k,v in q.items() if not isinstance(v,dict)};self.rows.append(r);insert=True
        if r is None:return SimpleNamespace(matched_count=0)
        for op,fields in u.items():
            if op=='$setOnInsert' and not insert:continue
            for k,v in fields.items():
                if op=='$unset':r.pop(k,None)
                else:put(r,k,(get(r,k) or 0)+v if op=='$inc' else v)
        return SimpleNamespace(matched_count=1)
    async def update_many(self,q,u):
        for r in list(self.rows):
            if matches(r,q):await self.update_one({'_id':r['_id']},u)
class Database:
    def __init__(self):self.rows={}
    def __getitem__(self,k):return self.rows.setdefault(k,Collection())
    def __getattr__(self,k):return self[k]

class Lifecycle(unittest.IsolatedAsyncioTestCase):
    def setUp(self):
        self.db=Database();self.at=datetime(2026,10,15,12);self.clock=self.at
        self.p={'_id':'p1','tg_id':1,'name':'Amir','created_at':self.at,'castle':'A','region':'north','resources':{'wine':100},'points':700,'stats':{'wins':2},'medals':['hero']}
        self.db.players.rows=[copy.deepcopy(self.p),{'_id':'p2','tg_id':2,'name':'Host','created_at':self.at,'castle':'B','region':'north'},{'_id':'p3','tg_id':3,'name':'Member','created_at':self.at,'castle':'C','region':'north'}]
        for mod in (t,routes,family):self.enterContext(patch.object(mod,'db',self.db))
        for mod in (t,routes,family,project_engine):self.enterContext(patch.object(mod,'players',self.db.players))
        for name,collection in [('locations','character_locations'),('trips','character_trips'),('captures','character_captures'),('places','character_places'),('campaigns','campaigns')]:self.enterContext(patch.object(t,name,self.db[collection]))
        self.enterContext(patch.object(family,'operations',self.db.family_operations))
        self.enterContext(patch.object(family,'children',self.db.family_children))
        self.enterContext(patch.object(project_engine,'apply_production',side_effect=lambda p:p))
        self.enterContext(patch.object(project_engine,'production_fields',side_effect=lambda p:{'resources':p['resources']}))
        self.enterContext(patch.object(t,'now',side_effect=lambda:self.clock))
        self.enterContext(patch.object(routes,'now',side_effect=lambda:self.clock))
        self.enterContext(patch.object(t.game_clock,'paused',return_value=False))
        self.enterContext(patch.object(routes,'get_admin_role',AsyncMock(return_value=None)))
        self.enterContext(patch.object(t,'TRAVEL_GRAPH',{'A':{'B':10},'B':{'A':10,'C':20},'C':{'B':20}}))
        self.enterContext(patch.object(t,'_dijkstra_path',side_effect=lambda a,b:(0,[a]) if a==b else ((10,[a,b]) if {a,b}=={'A','B'} else (20,[a,b]))))
    async def test_acceptance_charges_once_and_arrives_with_child(self):
        self.db.family_children.rows=[{'_id':'kid','name':'Child','patron_id':1,'patron_key':family.key(self.p),'parent_keys':[family.key(self.p)],'status':'alive'}]
        row=await t.request(self.p,'B',['kid'],str(uuid4()))
        self.assertEqual(row['status'],'pending')
        self.assertEqual(self.db.players.rows[0]['resources']['wine'],100)
        await t.respond(2,row['id'],True)
        self.assertEqual(self.db.players.rows[0]['resources']['wine'],80)
        await family.recover()
        self.assertEqual(self.db.players.rows[0]['resources']['wine'],80)
        self.clock+=timedelta(minutes=11)
        await t.tick();await t.tick()
        self.assertEqual((await t.state(self.p))['place'],'B')
        self.assertEqual((await t.locations.find_one({'_id':'child:kid'}))['place'],'B')
        self.assertEqual((await t.trips.find_one({'_id':row['id']}))['status'],'arrived')
    async def test_no_wine_rejects_departure_without_changing_location(self):
        self.db.players.rows[0]['resources']['wine']=0
        row=await t.request(self.p,'B',[],str(uuid4()))
        with self.assertRaises(HTTPException):await t.respond(2,row['id'],True)
        self.assertEqual((await t.state(self.p))['place'],'A')
        self.assertIsNone((await t.state(self.p))['trip'])
    async def test_landless_can_travel_to_empty_place_without_wine(self):
        self.db.players.rows[0].update(castle=None,landless=True,resources={})
        p=self.db.players.rows[0]
        await t.state(p);await t.locations.update_one({'_id':family.key(p)},{'$set':{'place':'A'}})
        self.db.players.rows[1]['castle']=None
        row=await t.request(p,'B',[],str(uuid4()))
        self.assertEqual(row['status'],'travelling');self.assertEqual(row['cost'],0)
    async def test_institution_and_castle_owner_both_needed(self):
        await t.places.insert_one({'_id':'institution:citadel','name':'Citadel','node':'B','institution':'citadel','enabled':True})
        with patch.object(t,'member_ids',AsyncMock(return_value=[3])):
            row=await t.request(self.p,'institution:citadel',[],str(uuid4()))
            await t.respond(3,row['id'],True)
            self.assertIsNone((await t.state(self.p))['trip'])
            await t.respond(2,row['id'],True)
            self.assertEqual((await t.state(self.p))['trip'],row['id'])
    async def test_capture_requires_admin_then_host_can_release(self):
        await t.state(self.p);await t.locations.update_one({'_id':family.key(self.p)},{'$set':{'place':'B'}})
        row=await t.capture_request(2,family.key(self.p),'reason')
        self.assertIsNone((await t.state(self.p))['captive'])
        await t.review_capture(row['id'],True,99)
        self.assertIsNotNone((await t.state(self.p))['captive'])
        with self.assertRaises(HTTPException):await t.request(self.p,'C',[],str(uuid4()))
        with self.assertRaises(HTTPException):await t.release(family.key(self.p),3)
        await t.release(family.key(self.p),2)
        self.assertIsNone((await t.state(self.p))['captive'])
    async def test_revival_restores_character_but_no_castle_resources_or_army(self):
        self.db.players.rows[0]['is_dead']=True
        await self.db.character_retirements.insert_one({'_id':family.key(self.p),'snapshot':copy.deepcopy(self.p)})
        await routes.player_action(1,routes.PlayerAction(action='revive'),{'id':99})
        p=self.db.players.rows[0]
        self.assertFalse(p['is_dead']);self.assertTrue(p['landless'])
        self.assertEqual(p['resources'],{});self.assertEqual(p['troops'],{});self.assertIsNone(p['castle'])
        self.assertEqual(p['points'],700);self.assertEqual(p['medals'],['hero']);self.assertEqual(p['stats'],{'wins':2})
    async def test_visits_private_to_owner_and_participants(self):
        row=await t.request(self.p,'B',[],str(uuid4()))
        stranger=self.db.players.rows[2]
        with patch.object(t,'member_ids',AsyncMock(return_value=[])):
            host=await t.view(self.db.players.rows[1]);other=await t.view(stranger)
        self.assertIn(row['id'],[r['id'] for r in host['requests']])
        self.assertNotIn(row['id'],[r['id'] for r in other['requests']])
    async def test_crash_after_wine_debit_recovers_without_second_charge(self):
        row=await t.request(self.p,'B',[],str(uuid4()))
        original=family.wallet_once
        async def crash(*args,**kwargs):
            await original(*args,**kwargs)
            raise RuntimeError('simulated crash after debit')
        with patch.object(family,'wallet_once',side_effect=crash):
            with self.assertRaises(RuntimeError):await t.respond(2,row['id'],True)
        self.assertEqual(self.db.players.rows[0]['resources']['wine'],90)
        await family.recover();await family.recover()
        self.assertEqual(self.db.players.rows[0]['resources']['wine'],90)
        self.assertEqual((await t.state(self.p))['trip'],row['id'])
    async def test_admin_pause_resume_preserves_remaining_time(self):
        row=await t.request(self.p,'B',[],str(uuid4()));await t.respond(2,row['id'],True)
        await routes.control(routes.Control(subject=family.key(self.p),action='hold'),{'id':99})
        self.clock+=timedelta(hours=2)
        await t.tick()
        self.assertIsNotNone((await t.state(self.p))['trip'])
        await routes.control(routes.Control(subject=family.key(self.p),action='resume'),{'id':99})
        trip=await t.trips.find_one({'_id':row['id']})
        self.assertEqual(trip['arrival_at']-self.clock,timedelta(minutes=10))
        with self.assertRaises(HTTPException):await routes.control(routes.Control(subject=family.key(self.p),action='resume'),{'id':99})
    async def test_expulsion_waits_during_war_then_requests_return(self):
        await t.state(self.p);await t.locations.update_one({'_id':family.key(self.p)},{'$set':{'place':'B','previous':'A'}})
        with patch.object(t,'blocked',AsyncMock(return_value=True)):
            result=await routes.expel(routes.GuestAction(subject=family.key(self.p)),{'id':2})
        self.assertTrue(result['ok']);self.assertEqual((await t.state(self.p))['place'],'B')
        await t.tick()
        trip=await t.trips.find_one({'character':family.key(self.p),'status':'travelling'})
        self.assertEqual(trip['target'],'A');self.assertEqual(trip['cost'],0)
