"""Character admission and access tests use only a fresh in-memory database."""
import unittest
from datetime import datetime, timedelta
from contextlib import ExitStack
from unittest.mock import AsyncMock, patch
from starlette.requests import Request
from fastapi import HTTPException, BackgroundTasks
from mongomock_motor import AsyncMongoMockClient
from pydantic import ValidationError
import auth, family, character_admission as admission, character_travel as travel
from character_access import status
from routers import players as routes, admin, characters, buildings
from game import owned_castles, apply_production

class CharacterAdmissionTests(unittest.IsolatedAsyncioTestCase):
    async def asyncSetUp(self):
        self.mem=AsyncMongoMockClient()['character_admission_test']
        self.stack=ExitStack();self.addCleanup(self.stack.close)
        for mod,name,value in [(admission,'players',self.mem.players),(family,'db',self.mem),(family,'operations',self.mem.family_operations),(travel,'places',self.mem.character_places),(travel,'TRAVEL_GRAPH',{'A':{'B':10},'B':{'A':10}}),(routes,'players',self.mem.players),(admin,'players',self.mem.players),(admin,'admin_roles',self.mem.admin_roles),(admin,'map_castles',self.mem.map_castles),(auth,'players',self.mem.players)]:
            self.stack.enter_context(patch.object(mod,name,value))
        self.stack.enter_context(patch.object(auth,'get_admin_role',AsyncMock(return_value=None)))
        self.stack.enter_context(patch.object(auth,'DEV_MODE',True))
        self.stack.enter_context(patch.object(routes,'get_admin_role',AsyncMock(return_value=None)))
        self.stack.enter_context(patch.object(routes,'notify_admins',AsyncMock()))
        self.stack.enter_context(patch.object(routes,'all_castle_names_and_ports',AsyncMock(return_value=({'A','B'},set()))))
        self.stack.enter_context(patch.object(routes,'registration_state',AsyncMock(return_value={'north':{'full':True}})))
        self.stack.enter_context(patch.object(routes,'castle_region_map',AsyncMock(return_value={'A':'north','B':'north'})))
        self.stack.enter_context(patch.object(admin,'_castle_region_map',AsyncMock(return_value={'A':'north','B':'north'})))
        self.stack.enter_context(patch('character_records.blacklist',self.mem.account_blacklist))
        self.stack.enter_context(patch.object(routes,'feature_enabled',return_value=True))
        try: import web_auth
        except ImportError: pass
        else: self.stack.enter_context(patch.object(web_auth,'identity',AsyncMock(return_value={'id':1,'first_name':'Test'})))
        self.p={'tg_id':1,'name':'Arya','gender':'lady','castle':None,'region':None,'created_at':datetime(2026,1,1),'resources':{'gold':50},'buildings':{},'castle_buildings':{},'points':100,'landless':False}
        await self.mem.players.insert_one(self.p)

    async def approve(self):
        return await admission.approve(1,'north','A',99,f"1:{self.p['created_at']}")

    async def test_approval_creates_presence_without_ownership_or_host_change(self):
        await self.mem.players.insert_one({'tg_id':2,'name':'Host','castle':'A','region':'north'})
        await self.approve()
        p=await self.mem.players.find_one({'tg_id':1});self.assertEqual(status(p),'landless');self.assertEqual(owned_castles(p),[])
        self.assertEqual((await self.mem.players.find_one({'tg_id':2}))['castle'],'A')
        loc=await self.mem.character_locations.find_one({'_id':family.key(p)});self.assertEqual(loc['place'],'A')
        self.assertEqual(p['resources'],{'gold':50})
        self.assertEqual(await self.mem.family_notices.count_documents({}),1)

    async def test_approved_character_leaves_pending_and_enters_roster(self):
        await self.approve()
        self.assertEqual(await admin.list_pending_players({}),[])
        rows=await admin.list_roster({});self.assertEqual(rows[0]['tg_id'],1);self.assertTrue(rows[0]['landless'])

    async def test_pending_row_carries_registration_mode_and_key(self):
        rows=await admin.list_pending_players({});self.assertEqual(rows[0]['registration_mode'],'castle');self.assertTrue(rows[0]['character_key'].startswith('1:'))

    async def test_me_enters_game_without_a_castle_after_approval(self):
        await self.approve()
        value=await routes.me(Request({'type':'http','headers':[]}),BackgroundTasks(),{'id':1})
        self.assertFalse(value['pending']);self.assertTrue(value['landless']);self.assertIsNone(value['castle'])

    async def test_dead_reset_or_already_active_character_cannot_be_approved(self):
        for fields in [{'is_dead':True},{'registration_reset':True},{'castle':'B','region':'north'},{'landless':True,'region':'north'}]:
            await self.mem.players.replace_one({'tg_id':1},{**self.p,**fields})
            with self.assertRaises(HTTPException) as err: await self.approve()
            self.assertEqual(err.exception.status_code,409)

    async def test_stale_identity_cannot_approve_replacement_character(self):
        with self.assertRaises(HTTPException):await admission.approve(1,'north','A',99,'old-character')
        self.assertEqual(await self.mem.character_locations.count_documents({}),0)

    async def test_invalid_region_or_place_makes_no_partial_change(self):
        for region,place in [('missing','A'),('north','missing'),('north','')]:
            with self.assertRaises(HTTPException):await admission.approve(1,region,place,99)
            self.assertEqual(status(await self.mem.players.find_one({'tg_id':1})),'pending')
        self.assertEqual(await self.mem.character_locations.count_documents({}),0)

    async def test_duplicate_approval_cannot_relocate_or_repeat_notice(self):
        await self.approve()
        with self.assertRaises(HTTPException):await admission.approve(1,'north','B',99)
        self.assertEqual(await self.mem.family_notices.count_documents({}),1)
        self.assertEqual((await self.mem.character_locations.find_one({}))['place'],'A')

    async def test_character_registration_needs_no_vacant_castle_and_no_capacity(self):
        await self.mem.players.delete_many({})
        await self.mem.players.insert_one({'tg_id':2,'castle':'A','region':'north'})
        await routes.register(routes.RegisterBody(name='Arya',gender='lady',registration_mode='character',requested_region='north',landless=True,approved_at='forged'),{'id':1})
        p=await self.mem.players.find_one({'tg_id':1});self.assertEqual(status(p),'pending');self.assertEqual(p['registration_mode'],'character');self.assertEqual(p['requested_castles'],[])
        self.assertIsNone(p['castle']);self.assertFalse(p['landless'])

    async def test_castle_registration_still_requires_castle_and_capacity(self):
        await self.mem.players.delete_many({})
        with self.assertRaises(HTTPException):await routes.register(routes.RegisterBody(name='Arya',gender='lady'),{'id':1})
        with self.assertRaises(HTTPException):await routes.register(routes.RegisterBody(name='Arya',gender='lady',requested_castles=['A']),{'id':1})
        self.assertIsNone(await self.mem.players.find_one({'tg_id':1}))

    async def test_character_registration_rejects_invalid_region(self):
        await self.mem.players.delete_many({})
        with self.assertRaises(HTTPException):await routes.register(routes.RegisterBody(name='Arya',gender='lady',registration_mode='character',requested_region='unknown'),{'id':1})
        with self.assertRaises(ValidationError):routes.RegisterBody(name='Arya',gender='lady',registration_mode='admin')

    async def test_residency_does_not_unlock_castle_buildings(self):
        await self.approve();p=await self.mem.players.find_one({'tg_id':1})
        for target in [None,'A']:
            with self.assertRaises(HTTPException) as err:buildings._resolve_castle(p,target)
            self.assertEqual(err.exception.status_code,403)

    async def test_pending_character_cannot_mutate_game(self):
        for path in ['/api/item-store/listings','/api/character-travel/requests','/api/war/launch']:
            with self.assertRaises(HTTPException) as err:await auth.get_user(Request({'type':'http','path':path,'method':'POST','headers':[]}),authorization='',x_dev_user='1:Test')
            self.assertEqual(err.exception.status_code,403)

    async def test_landless_permissions_match_personal_operations(self):
        await self.approve()
        for path in ['/api/character-travel/requests','/api/roleplay/send','/api/item-store/listings','/api/family/marriage','/api/institutions/citadel/requests']:
            self.assertEqual((await auth.get_user(Request({'type':'http','path':path,'method':'POST','headers':[]}),authorization='',x_dev_user='1:Test'))['id'],1)
        for path in ['/api/war/launch','/api/players/tax','/api/buildings/farm/build','/api/character-travel-escape']:
            with self.assertRaises(HTTPException):await auth.get_user(Request({'type':'http','path':path,'method':'POST','headers':[]}),authorization='',x_dev_user='1:Test')

    async def test_approval_requires_full_admin(self):
        with patch.object(characters,'get_full_admin',AsyncMock(side_effect=HTTPException(403,'denied'))):
            with self.assertRaises(HTTPException):await characters.full_administrator({'id':1})

    async def test_unowned_character_has_no_passive_production(self):
        p={**self.p,'created_at':datetime(2000,1,1),'last_tick':datetime(2000,1,1)}
        self.assertEqual(apply_production(p)['resources'],{'gold':50})
        p.update(region='north',landless=True);self.assertEqual(apply_production(p)['resources'],{'gold':50})

    async def test_recovery_cannot_remove_a_castle_assigned_after_interruption(self):
        with patch.object(family,'finish',AsyncMock(side_effect=RuntimeError('interrupted'))):
            with self.assertRaises(RuntimeError):await self.approve()
        await self.mem.players.update_one({'tg_id':1},{'$set':{'castle':'B','region':'north','landless':False}})
        await family.recover()
        p=await self.mem.players.find_one({'tg_id':1})
        self.assertEqual(p['castle'],'B');self.assertFalse(p['landless'])
