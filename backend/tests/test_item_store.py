import asyncio
import base64
import copy
import io
import unittest
from datetime import datetime, timedelta
from types import SimpleNamespace
from unittest.mock import AsyncMock, patch
from uuid import uuid4

from bson import ObjectId
from fastapi import FastAPI, HTTPException
from httpx import ASGITransport, AsyncClient
from PIL import Image
from pydantic import ValidationError
import item_store as s
from routers import item_store as routes, admin, assets
from item_effects import select_war_items
from tests.test_institution_bank import get, match, put


class Cursor:
    def __init__(self, rows): self.rows = copy.deepcopy(rows)
    def sort(self, *args): return self
    def skip(self, n): self.rows = self.rows[n:]; return self
    def limit(self, n): self.rows = self.rows[:n]; return self
    async def to_list(self, n=None): return copy.deepcopy(self.rows if n is None else self.rows[:n])
    def __aiter__(self): self.it = iter(self.rows); return self
    async def __anext__(self):
        try: return next(self.it)
        except StopIteration: raise StopAsyncIteration


class Collection:
    def __init__(self): self.rows = []
    def find(self, q): return Cursor([r for r in self.rows if match(r, q)])
    async def find_one(self, q): return copy.deepcopy(next((r for r in self.rows if match(r, q)), None))
    async def count_documents(self, q): return sum(match(r, q) for r in self.rows)
    async def update_one(self, q, update, upsert=False):
        r = next((r for r in self.rows if match(r, q)), None); insert = False
        if r is None and upsert:
            r = {k:v for k,v in q.items() if not isinstance(v,dict)}; self.rows.append(r); insert = True
        if r is None: return SimpleNamespace(matched_count=0)
        for op, fields in update.items():
            if op == '$setOnInsert' and not insert: continue
            for key,v in fields.items():
                if op == '$unset':
                    target=r;parts=key.split('.')
                    for part in parts[:-1]: target=target.get(part,{})
                    target.pop(parts[-1],None)
                elif op == '$inc': put(r,key,(get(r,key) or 0)+v)
                elif op == '$push': put(r,key,((get(r,key) or [])+v['$each'])[v['$slice']:])
                else: put(r,key,v)
        return SimpleNamespace(matched_count=1)


class Database:
    def __init__(self): self.cols = {}
    def __getitem__(self, key): return self.cols.setdefault(key, Collection())
    def __getattr__(self, key): return self[key]


class StoreTests(unittest.IsolatedAsyncioTestCase):
    def setUp(self):
        self.db=Database();self.at=datetime(2026,10,16,12);self.real=self.at;self.game=self.at
        self.db.players.rows=[{'tg_id':uid,'name':f'Player {uid}','created_at':self.at,'castle':'Castle',
            'resources':{'gold':1000},'item_effects':{}} for uid in (1,2,3)]
        self.tpl={'_id':ObjectId(),'name':'شمشیر','type':'war','duration':'permanent','color':'gold'}
        self.grant={'_id':ObjectId(),'item_id':self.tpl['_id'],'tg_id':1,'character_created_at':self.at,
                    'granted_at':self.at,'color':'gold'}
        self.db.items.rows=[copy.deepcopy(self.tpl)];self.db.item_grants.rows=[copy.deepcopy(self.grant)]
        self.db.game_settings.rows=[{'_id':'item_store',**s.DEFAULTS,'currency':'gold','gold_step':50}]
        for name,value in [('db',self.db),('listings',self.db.item_store_listings),('operations',self.db.item_store_operations)]:
            self.enterContext(patch.object(s,name,value))
        self.enterContext(patch.object(s,'apply_production',side_effect=lambda p:p))
        self.enterContext(patch.object(s,'production_fields',side_effect=lambda p:{'resources':p['resources']}))
        self.enterContext(patch.object(s,'campaign_for_grant',new=AsyncMock(return_value=None)))
        self.enterContext(patch.object(s.game_clock,'real_now',side_effect=lambda:self.real))
        self.enterContext(patch.object(s.game_clock,'now',side_effect=lambda:self.game))
    def listing_body(self,**kw): return routes.ListingBody(grant_id=str(self.grant['_id']),kind=kw.pop('kind','fixed'),price=kw.pop('price',200),request_id=kw.pop('request_id',str(uuid4())),**kw)
    async def listing(self,**kw): return await s.get(await s.create(1,self.listing_body(**kw)))
    def offer(self,row,amount=200,**kw): return routes.OfferBody(amount=amount,version=row['version'],request_id=kw.pop('request_id',str(uuid4())),**kw)
    async def balance(self,uid): return (await self.db.players.find_one({'tg_id':uid}))['resources']['gold']
    async def test_fixed_purchase_escrows_until_admin_and_transfers_once(self):
        row=await self.listing();body=self.offer(row);await s.purchase(2,str(row['_id']),body)
        self.assertEqual(await self.balance(2),800);self.assertEqual(await self.balance(1),1000)
        await s.purchase(2,str(row['_id']),body)
        self.assertEqual(await self.balance(2),800)
        row=await s.get(str(row['_id']));await s.approve(row,99);await s.approve(await s.get(str(row['_id'])),99)
        self.assertEqual(await self.balance(1),1200)
        grant=await self.db.item_grants.find_one({'_id':self.grant['_id']})
        self.assertEqual(grant['tg_id'],2);self.assertNotIn('store_listing_id',grant)
    async def test_rejected_purchase_refunds_once_and_returns_item(self):
        row=await self.listing();await s.purchase(2,str(row['_id']),self.offer(row))
        row=await s.get(str(row['_id']));await s.close(row,'rejected',99,'عدم پرداخت')
        await s.close(await s.get(str(row['_id'])),'rejected',99,'عدم پرداخت')
        self.assertEqual(await self.balance(2),1000);self.assertEqual(await self.balance(1),1000)
        self.assertNotIn('store_listing_id',self.db.item_grants.rows[0])
    async def test_outbid_refunds_previous_and_self_raise_only_debits_difference(self):
        row=await self.listing(kind='auction');await s.purchase(2,str(row['_id']),self.offer(row,200))
        row=await s.get(str(row['_id']));await s.purchase(2,str(row['_id']),self.offer(row,250))
        self.assertEqual(await self.balance(2),750)
        row=await s.get(str(row['_id']));await s.purchase(3,str(row['_id']),self.offer(row,300))
        self.assertEqual(await self.balance(2),1000);self.assertEqual(await self.balance(3),700)
    async def test_bid_step_enforced_server_side(self):
        row=await self.listing(kind='auction');await s.purchase(2,str(row['_id']),self.offer(row,200))
        for amount in (200,249,251):
            row=await s.get(str(row['_id']))
            with self.assertRaises(HTTPException):await s.purchase(3,str(row['_id']),self.offer(row,amount))
        self.assertEqual(await self.balance(3),1000)
    async def test_real_auction_closes_while_game_clock_stays_frozen(self):
        row=await self.listing(kind='auction');await s.purchase(2,str(row['_id']),self.offer(row))
        self.real+=timedelta(hours=25);await s.tick()
        self.assertEqual((await s.get(str(row['_id'])))['status'],'pending')
        self.assertEqual(self.game,self.at)
        with self.assertRaises(HTTPException):await s.purchase(3,str(row['_id']),self.offer(await s.get(str(row['_id'])),250))
    async def test_no_bid_returns_item(self):
        row=await self.listing(kind='auction');self.real+=timedelta(hours=25);await s.tick()
        self.assertEqual((await s.get(str(row['_id'])))['status'],'unsold')
        self.assertNotIn('store_listing_id',self.db.item_grants.rows[0])
    async def test_currency_and_step_snapshot_survive_settings_change(self):
        row=await self.listing(kind='auction');self.db.game_settings.rows[0].update(currency='toman',gold_step=7)
        await s.purchase(2,str(row['_id']),self.offer(row))
        row=await s.get(str(row['_id']));self.assertEqual(row['currency'],'gold');self.assertEqual(row['bid_step'],50)
        self.assertEqual(await self.balance(2),800)
    async def test_toman_never_changes_game_gold(self):
        self.db.game_settings.rows[0]['currency']='toman';row=await self.listing()
        await s.purchase(2,str(row['_id']),self.offer(row));await s.approve(await s.get(str(row['_id'])),99)
        self.assertEqual(await self.balance(1),1000);self.assertEqual(await self.balance(2),1000)
    async def test_no_self_purchase_no_foreign_listing_and_no_duplicate_listing(self):
        body=self.listing_body()
        with self.assertRaises(HTTPException):await s.create(2,body)
        row=await self.listing()
        with self.assertRaises(HTTPException):await s.purchase(1,str(row['_id']),self.offer(row))
        with self.assertRaises(HTTPException):await s.create(1,self.listing_body())
    async def test_insufficient_funds_and_stale_version_have_no_side_effect(self):
        row=await self.listing(price=1001)
        with self.assertRaises(HTTPException):await s.purchase(2,str(row['_id']),self.offer(row,1001))
        self.assertEqual(await self.balance(2),1000)
        with self.assertRaises(HTTPException):await s.purchase(2,str(row['_id']),routes.OfferBody(amount=1001,version=50,request_id=str(uuid4())))
    async def test_request_id_cannot_be_reused_with_changed_amount(self):
        row=await self.listing(kind='auction');body=self.offer(row);await s.purchase(2,str(row['_id']),body)
        with self.assertRaises(HTTPException):await s.purchase(2,str(row['_id']),self.offer(await s.get(str(row['_id'])),250,request_id=body.request_id))
    async def test_listing_retry_returns_same_id(self):
        body=self.listing_body();a=await s.create(1,body);b=await s.create(1,body)
        self.assertEqual(a,b);self.assertEqual(len(self.db.item_store_listings.rows),1)
    async def test_crash_after_debit_recovery_does_not_charge_again(self):
        row=await self.listing();body=self.offer(row);original=self.db.players.update_one
        async def crash(query,update,**kw):
            result=await original(query,update,**kw)
            if 'resources.gold' in update.get('$inc',{}):raise RuntimeError('simulated process exit after wallet commit')
            return result
        with patch.object(self.db.players,'update_one',side_effect=crash):
            with self.assertRaises(RuntimeError):await s.purchase(2,str(row['_id']),body)
        self.assertEqual(await self.balance(2),800)
        await s.recover();await s.purchase(2,str(row['_id']),body)
        self.assertEqual(await self.balance(2),800);self.assertEqual((await s.get(str(row['_id'])))['status'],'pending')
    async def test_approval_crash_after_transfer_recovers_without_double_payment(self):
        row=await self.listing();await s.purchase(2,str(row['_id']),self.offer(row));row=await s.get(str(row['_id']))
        original=self.db.players.update_one
        async def crash(query,update,**kw):
            result=await original(query,update,**kw)
            if update.get('$inc',{}).get('resources.gold')==200:raise RuntimeError('exit after seller credit')
            return result
        with patch.object(self.db.players,'update_one',side_effect=crash):
            with self.assertRaises(RuntimeError):await s.approve(row,99)
        await s.recover();self.assertEqual(await self.balance(1),1200)
        self.assertEqual((await s.get(str(row['_id'])))['status'],'sold')
    async def test_outbid_restart_conserves_escrow_and_refunds_previous_bidder(self):
        row=await self.listing(kind='auction');await s.purchase(2,str(row['_id']),self.offer(row))
        row=await s.get(str(row['_id']));body=self.offer(row,250);original=self.db.players.update_one
        async def crash(query,update,**kw):
            result=await original(query,update,**kw)
            if query.get('tg_id')==3 and 'resources.gold' in update.get('$inc',{}):raise RuntimeError('exit before former bidder refund')
            return result
        with patch.object(self.db.players,'update_one',side_effect=crash):
            with self.assertRaises(RuntimeError):await s.purchase(3,str(row['_id']),body)
        await s.recover();await s.purchase(3,str(row['_id']),body)
        row=await s.get(str(row['_id']))
        self.assertEqual(await self.balance(2),1000);self.assertEqual(await self.balance(3),750)
        wallets = sum([await self.balance(uid) for uid in (1,2,3)])
        self.assertEqual(wallets + row['highest']['amount'],3000)
    async def test_reserved_item_rejected_by_campaign_inventory(self):
        row=await self.listing()
        import db
        for key in ('players','item_grants','items','campaigns'):self.enterContext(patch.object(db,key,self.db[key]))
        with self.assertRaises(HTTPException):await select_war_items(await s.player(1),[str(self.grant['_id'])])
    async def test_attached_expired_and_old_character_items_cannot_list(self):
        with patch.object(s,'campaign_for_grant',new=AsyncMock(return_value={'active':True})):
            with self.assertRaises(HTTPException):await self.listing()
        self.db.item_grants.rows[0]['expires_at']=self.at
        with self.assertRaises(HTTPException):await self.listing()
        self.db.item_grants.rows[0].pop('expires_at');self.db.item_grants.rows[0]['character_created_at']=self.at-timedelta(days=1)
        with self.assertRaises(HTTPException):await self.listing()
    async def test_economic_effect_suspended_and_transferred_without_retroactive_bonus(self):
        effect={'building_id':'farm','percent':15,'starts_at':self.at,'expires_at':None,'character_created_at':self.at,'character_child_id':None}
        self.db.item_grants.rows[0]['effect']=effect;self.db.players.rows[0]['item_effects'][str(self.grant['_id'])]=effect
        row=await self.listing();self.assertNotIn(str(self.grant['_id']),self.db.players.rows[0]['item_effects'])
        await s.purchase(2,str(row['_id']),self.offer(row));self.game+=timedelta(hours=2)
        await s.approve(await s.get(str(row['_id'])),99)
        new=self.db.players.rows[1]['item_effects'][str(self.grant['_id'])]
        self.assertEqual(new['starts_at'],self.game)
    async def test_expired_pending_item_cannot_approve_and_refunds(self):
        self.db.item_grants.rows[0]['expires_at']=self.at+timedelta(hours=1)
        row=await self.listing();await s.purchase(2,str(row['_id']),self.offer(row));self.game+=timedelta(hours=2)
        with self.assertRaises(HTTPException):await s.approve(await s.get(str(row['_id'])),99)
        await s.close(await s.get(str(row['_id'])),'rejected',99,'منقضی');self.assertEqual(await self.balance(2),1000)
    async def test_changed_buyer_character_blocks_delivery_but_refund_is_preserved(self):
        row=await self.listing();await s.purchase(2,str(row['_id']),self.offer(row))
        self.db.players.rows[1]['created_at']+=timedelta(days=1)
        with self.assertRaises(HTTPException):await s.approve(await s.get(str(row['_id'])),99)
        await s.close(await s.get(str(row['_id'])),'rejected',99,'تغییر کاراکتر')
        self.assertEqual(await self.balance(2),1000)
    async def test_inventory_hides_escrowed_items(self):
        await self.listing()
        for key in ('players','items','item_grants'):self.enterContext(patch.object(assets,key,self.db[key]))
        self.assertEqual(await assets.my_items({'id':1}),[])
    async def test_admin_cannot_delete_reserved_template(self):
        await self.listing()
        for key in ('items','item_grants'):self.enterContext(patch.object(admin,key,self.db[key]))
        with self.assertRaises(HTTPException):await admin.admin_delete_item(str(self.tpl['_id']),{'id':99})
    async def test_public_view_does_not_expose_buyer_id_or_history(self):
        row=await self.listing();await s.purchase(2,str(row['_id']),self.offer(row));view=s.view(await s.get(str(row['_id'])),3)
        self.assertNotIn('highest',view);self.assertNotIn('bid_history',view);self.assertNotIn('buyer_name',view)
    async def test_admin_routes_reject_player_and_limited_roles(self):
        app=FastAPI();app.include_router(routes.router)
        app.dependency_overrides[routes.get_user]=lambda:{'id':2}
        with patch('auth.get_admin_role',new=AsyncMock(return_value='limited')):
            async with AsyncClient(transport=ASGITransport(app=app),base_url='http://test') as client:
                for path in ('/api/admin/item-store','/api/admin/item-store/inventory/1'):
                    self.assertEqual((await client.get(path)).status_code,403)
    async def test_admin_toman_confirmation_required(self):
        self.db.game_settings.rows[0]['currency']='toman';row=await self.listing()
        await s.purchase(2,str(row['_id']),self.offer(row))
        with self.assertRaises(HTTPException):await routes.decision(str(row['_id']),routes.DecisionBody(action='approve'),{'id':99})
        await routes.decision(str(row['_id']),routes.DecisionBody(action='approve',payment_confirmed=True),{'id':99})
        self.assertEqual((await s.get(str(row['_id'])))['status'],'sold')
    def test_amounts_are_strict_positive_bounded_integers(self):
        for amount in (-1,0,1.5,True,10**13):
            with self.assertRaises(ValidationError):routes.OfferBody(amount=amount,version=1,request_id=str(uuid4()))
    async def test_item_image_validation_and_storage(self):
        out=io.BytesIO();Image.new('RGB',(16,16),'red').save(out,'PNG')
        image='data:image/png;base64,'+base64.b64encode(out.getvalue()).decode()
        self.enterContext(patch.object(admin,'items',self.db.items))
        # The existing creation endpoint uses insert_one, so capture the valid payload.
        async def insert(doc):self.db.items.rows.append(doc);return SimpleNamespace(inserted_id=ObjectId())
        self.db.items.insert_one=insert
        await admin.admin_create_item(admin.ItemBody(name='تصویر',type='war',duration='permanent',image=image),{'id':99})
        self.assertTrue(self.db.items.rows[-1]['image'].startswith('data:image/webp;base64,'))
        with self.assertRaises(HTTPException):await admin.admin_create_item(admin.ItemBody(name='بد',type='war',duration='permanent',image='data:image/svg+xml;base64,AAAA'),{'id':99})


if __name__=='__main__':unittest.main()
