"""Economic rules, permission boundaries and malformed public army records."""
import unittest
from contextlib import ExitStack
from copy import deepcopy
from datetime import datetime, timedelta
from unittest.mock import AsyncMock, patch
from bson import ObjectId
from fastapi import HTTPException
from mongomock_motor import AsyncMongoMockClient
import realm_controls, realm_state, market_rules, family, project_engine, auth
from routers import economy, realm, war


class RealmControlsTests(unittest.IsolatedAsyncioTestCase):
    async def asyncSetUp(self):
        self.mem=AsyncMongoMockClient()['realm_controls_test']; self.stack=ExitStack();self.addCleanup(self.stack.close)
        for module,name,value in [
            (realm_controls,'db',self.mem),(realm_state,'players',self.mem.players),(realm_state,'EVENTS',self.mem.game_events),
            (realm,'db',self.mem),(realm,'players',self.mem.players),(realm,'proposals',self.mem.council_proposals),
            (economy,'db',self.mem),(economy,'players',self.mem.players),(economy,'orders',self.mem.market_buy_orders),
            (economy,'contracts',self.mem.supply_contracts),(market_rules,'game_settings',self.mem.game_settings),
            (family,'db',self.mem),(family,'operations',self.mem.family_operations),(project_engine,'players',self.mem.players),
            (war,'campaigns',self.mem.campaigns),
        ]:self.stack.enter_context(patch.object(module,name,value))
        for name in ['send_system_message','adjust_reputation']:
            self.stack.enter_context(patch.object(economy,name,AsyncMock()))
        self.stack.enter_context(patch.object(project_engine,'apply_production',side_effect=lambda p:p))
        self.stack.enter_context(patch.object(project_engine,'production_fields',side_effect=lambda p:{'resources':p['resources']}))
        self.stamp=datetime(2026,10,27)
        await self.mem.players.insert_many([
            {'tg_id':1,'name':'Buyer','region':'north','castle':'A','created_at':self.stamp,'resources':{'gold':10000,'food':0}},
            {'tg_id':2,'name':'Seller','region':'river','castle':'B','created_at':self.stamp,'resources':{'gold':0,'food':500}},
        ])
        await self.mem.game_settings.insert_one({'_id':'player_market_price_floors','prices':{'food':10},'ceilings':{'food':30}})

    async def cfg(self,**values):
        await self.mem.game_settings.update_one({'_id':'realm_rules'},{'$set':values},upsert=True)

    async def test_out_of_bounds_orders_and_contracts_never_debit(self):
        for price in [9,31]:
            with self.assertRaises(HTTPException):await economy.create_order(economy.OrderBody(resource='food',qty=10,unit_price=price),{'id':1})
            with self.assertRaises(HTTPException):await economy.create_contract(economy.ContractBody(seller_id=2,resource='food',qty_per_delivery=10,unit_price=price,deliveries=1,interval_hours=1),{'id':1})
        self.assertEqual((await self.mem.players.find_one({'tg_id':1}))['resources']['gold'],10000)
        self.assertEqual(await self.mem.family_operations.count_documents({}),0)

    async def test_changed_limits_block_old_order_but_admin_can_refund_once(self):
        order=await economy.create_order(economy.OrderBody(resource='food',qty=10,unit_price=20),{'id':1})
        await self.mem.game_settings.update_one({'_id':'player_market_price_floors'},{'$set':{'ceilings.food':15}})
        with self.assertRaises(HTTPException):await economy.fill_order(order['id'],economy.FillBody(qty=1),{'id':2})
        result=await economy.admin_close_order(order['id'],economy.AdminCloseBody(reason='تغییر بازهٔ قیمت'),{'id':99})
        self.assertEqual(result['refunded'],200)
        with self.assertRaises(HTTPException):await economy.admin_close_order(order['id'],economy.AdminCloseBody(reason='دوباره'),{'id':99})
        self.assertEqual((await self.mem.players.find_one({'tg_id':1}))['resources']['gold'],10000)
        self.assertEqual(await self.mem.game_events.count_documents({'kind':'admin_order_closed'}),1)

    async def test_contract_rechecks_on_acceptance_and_delivery(self):
        row=await economy.create_contract(economy.ContractBody(seller_id=2,resource='food',qty_per_delivery=10,unit_price=20,deliveries=1,interval_hours=1),{'id':1})
        await self.mem.game_settings.update_one({'_id':'player_market_price_floors'},{'$set':{'ceilings.food':15}})
        with self.assertRaises(HTTPException):await economy.respond_contract(row['id'],economy.RespondBody(accept=True),{'id':2})
        await self.mem.game_settings.update_one({'_id':'player_market_price_floors'},{'$set':{'ceilings.food':30}})
        await economy.respond_contract(row['id'],economy.RespondBody(accept=True),{'id':2})
        await self.mem.game_settings.update_one({'_id':'player_market_price_floors'},{'$set':{'prices.food':25}})
        with self.assertRaises(HTTPException):await economy.deliver_contract(row['id'],{'id':2})
        self.assertEqual((await self.mem.players.find_one({'tg_id':2}))['resources']['food'],500)

    async def test_disabled_trading_still_allows_refund(self):
        order=await economy.create_order(economy.OrderBody(resource='food',qty=10,unit_price=20),{'id':1})
        await self.cfg(trade_network_enabled=False)
        with self.assertRaises(HTTPException):await economy.fill_order(order['id'],economy.FillBody(qty=1),{'id':2})
        with self.assertRaises(HTTPException):await economy.create_order(economy.OrderBody(resource='food',qty=1,unit_price=20),{'id':1})
        await economy.cancel_order(order['id'],{'id':1})
        self.assertEqual((await self.mem.players.find_one({'tg_id':1}))['resources']['gold'],10000)

    async def test_optional_supply_fees_preserve_total_gold(self):
        await self.cfg(contract_fees_enabled=True)
        row=await economy.create_contract(economy.ContractBody(seller_id=2,resource='food',qty_per_delivery=10,unit_price=20,deliveries=1,interval_hours=1),{'id':1})
        await economy.respond_contract(row['id'],economy.RespondBody(accept=True),{'id':2})
        await economy.deliver_contract(row['id'],{'id':2})
        buyer=await self.mem.players.find_one({'tg_id':1});seller=await self.mem.players.find_one({'tg_id':2});treasury=await self.mem.realm_treasury.find_one({'_id':'trade'})
        self.assertEqual(seller['resources']['gold'],190);self.assertEqual(treasury['gold'],10)
        self.assertEqual(buyer['resources']['gold']+seller['resources']['gold']+treasury['gold'],10000)
        event=await self.mem.game_events.find_one({'kind':'supply_delivery'})
        self.assertEqual(event['data']['fee'],10)

    async def test_limits_apply_before_escrow(self):
        await self.cfg(max_open_orders=0)
        with self.assertRaises(HTTPException):await economy.create_order(economy.OrderBody(resource='food',qty=1,unit_price=10),{'id':1})
        self.assertEqual((await self.mem.players.find_one({'tg_id':1}))['resources']['gold'],10000)

    async def test_influence_rewards_are_configurable_capped_and_idempotent(self):
        await self.cfg(influence_start=30,influence_cap=35,reward_vote=9)
        self.assertEqual(await realm_state.adjust_influence(1,1,'رأی',source_id='vote:test:1'),35)
        self.assertEqual(await realm_state.adjust_influence(1,1,'رأی',source_id='vote:test:1'),35)
        await realm_state.adjust_influence(1,-5,'خرج',source_id='spend:1')
        await realm_state.adjust_influence(1,1,'تکرار رأی',source_id='vote:test:1')
        self.assertEqual((await self.mem.players.find_one({'tg_id':1}))['political_influence'],30)
        self.assertEqual(await self.mem.game_events.count_documents({'kind':'influence'}),2)
        self.assertIsNone(await realm_state.adjust_influence(1,-31,'خرج',source_id='spend:2'))

    async def test_influence_cap_change_never_removes_existing_balance(self):
        await self.mem.players.update_one({'tg_id':1},{'$set':{'political_influence':100}})
        await self.cfg(influence_cap=20)
        self.assertEqual(await realm_state.adjust_influence(1,2,'پاداش',source_id='supply:1:1'),100)

    async def test_rules_are_audited_and_manual_adjustment_is_idempotent(self):
        await realm.save_rules(realm.RulesBody(reason='تغییر فصل',proposal_cost=8),{'id':99})
        self.assertEqual((await realm.rules())['proposal_cost'],8)
        self.assertEqual(await self.mem.game_events.count_documents({'kind':'admin_realm_rules'}),1)
        body=realm.InfluenceBody(delta=5,reason='اصلاح پرونده',request_id='1234567890abcdef')
        await realm.admin_influence(1,body,{'id':99});await realm.admin_influence(1,body,{'id':99})
        self.assertEqual((await self.mem.players.find_one({'tg_id':1}))['political_influence'],25)
        self.assertEqual(await self.mem.game_events.count_documents({'kind':'admin_influence'}),1)

    async def test_region_support_and_disabled_council_are_enforced(self):
        row=await realm.create_proposal(realm.ProposalBody(title='رأی اقلیم',description='شرح پیشنهاد برای اقلیم',scope='region',options=['آری','نه']),{'id':1})
        with self.assertRaises(HTTPException):await realm.support_proposal(row['id'],{'id':2})
        await self.cfg(council_enabled=False)
        with self.assertRaises(HTTPException):await realm.vote_proposal(row['id'],realm.VoteBody(option=0),{'id':1})

    async def test_public_army_feed_ignores_incomplete_records_without_deleting(self):
        bad={'_id':ObjectId(),'tg_id':1,'active':True,'arrival_at':self.stamp+timedelta(hours=1)}
        good={**bad,'_id':ObjectId(),'player_name':'Lord','origin_castle':'A','target_castle':'B','op_type':'attack',
              'troops':{'infantry':10},'equipment':{},'created_at':self.stamp,'gold_cost':1,'men_committed':10}
        await self.mem.campaigns.insert_many([bad,good]);self.stack.enter_context(patch.object(war,'now',lambda:self.stamp))
        rows=await war.mine({'id':1});self.assertEqual(len(rows),1);self.assertEqual(rows[0]['sender'],'Lord')
        self.assertEqual(await self.mem.campaigns.find_one({'_id':bad['_id']}),bad)
        import battle_passage
        self.stack.enter_context(patch.object(battle_passage,'status',AsyncMock(return_value={})))
        rows=await war.legions({'id':1});self.assertEqual(len(rows),1);self.assertEqual(rows[0]['men_committed'],10)

    async def test_admin_access_requires_full_or_owner(self):
        for role in ['owner','full','limited','war_roleplay',None]:
            with patch.object(auth,'get_admin_role',AsyncMock(return_value=role)):
                if role in ['owner','full']:
                    self.assertEqual((await realm.full_admin({'id':99}))['admin_role'],role)
                else:
                    with self.assertRaises(HTTPException):await realm.full_admin({'id':99})

    async def test_map_keeps_valid_movement_next_to_incomplete_record(self):
        from routers import map as map_router
        import map_effects, season_clock
        for name,value in [('campaigns',self.mem.campaigns),('alliances',self.mem.alliances),('map_castles',self.mem.map_castles),('game_settings',self.mem.game_settings)]:
            self.stack.enter_context(patch.object(map_router,name,value))
        for name,value in [('scored_players',[]),('get_hierarchy_doc',{}),('all_castle_terrain',{})]:
            self.stack.enter_context(patch.object(map_router,name,AsyncMock(return_value=value)))
        self.stack.enter_context(patch.object(map_router,'now',lambda:self.stamp))
        self.stack.enter_context(patch.object(map_effects,'active_map_effects',AsyncMock(return_value=[])))
        self.stack.enter_context(patch.object(season_clock,'season_day',AsyncMock(return_value={'day':1})))
        bad={'_id':ObjectId(),'tg_id':1,'active':True,'arrival_at':self.stamp+timedelta(hours=1)}
        good={**bad,'_id':ObjectId(),'player_name':'Lord','origin_castle':'A','target_castle':'B','op_type':'attack',
              'troops':{'infantry':10},'equipment':{},'created_at':self.stamp,'gold_cost':1,'men_committed':10}
        await self.mem.campaigns.insert_many([bad,good])
        result=await map_router.get_map({'id':1})
        self.assertEqual(len(result['campaigns']),1)
        self.assertEqual(result['campaigns'][0]['player_name'],'Lord')
        self.assertEqual(await self.mem.campaigns.find_one({'_id':bad['_id']}),bad)
