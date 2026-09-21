import unittest
from datetime import datetime, timedelta
from unittest.mock import patch, AsyncMock
from db import db
import food_settlement as food
from routers import war
from fastapi import HTTPException

class Rules(unittest.TestCase):
    def test_civilians_then_equal_army_losses(self):
        a = food.starvation_plan(100, 16, .2, [])
        self.assertEqual(a['civilian_losses'], 20)
        a = food.starvation_plan(100, 100, .2, [({'infantry':100},1), ({'infantry':100},1)])
        self.assertEqual(a['civilian_losses'], 100)
        self.assertEqual(a['army_losses'], [{'infantry':50}, {'infantry':50}])
        self.assertEqual(food.starvation_plan(100, 999, .2, [({'infantry':20},1)])['army_losses'],[{'infantry':0}])

class Storage(unittest.IsolatedAsyncioTestCase):
    async def asyncSetUp(self):
        import asyncio
        db.client._io_loop = asyncio.get_running_loop()
        await db.client.drop_database(db.name)
    async def test_recruitment_only_at_origin(self):
        await db.campaigns.insert_one({'tg_id':1,'active':True,'battle_open':True,'battle_location':'A'})
        await war.ensure_recruitment_allowed({'tg_id':1}, 'B')
        with self.assertRaises(HTTPException):
            await war.ensure_recruitment_allowed({'tg_id':1}, 'A')
        await db.campaigns.delete_many({})
        for uid in (2,3):
            await db.campaigns.insert_one({'tg_id':uid,'active':True,'op_type':next(iter(war.ATTACK_OP_TYPES)), 'target_castle':'A','arrival_at':war.now()-timedelta(hours=1)})
        async def friendly(a,b): return b==2
        with patch.object(war,'players_are_friendly',side_effect=friendly):
            with self.assertRaises(HTTPException): await war.ensure_recruitment_allowed({'tg_id':1},'A')
    async def test_daily_charge_and_recovery_not_repeated(self):
        start=datetime(2026,9,21)
        p={'tg_id':1,'region':'north','castle':'A','resources':{'men':100,'food':16},'last_tick':start,'created_at':start}
        await db.players.insert_one(p)
        with patch.object(food,'now',return_value=start): await food.tick()
        self.assertEqual((await db.players.find_one({'tg_id':1}))['resources']['men'],100)
        with patch.object(food,'now',return_value=start+timedelta(days=1)), patch.object(food,'apply_production',side_effect=lambda p:p):
            await food.tick()
            await food.tick()
        p=await db.players.find_one({'tg_id':1})
        self.assertEqual(p['resources'],{'men':80,'food':0})
        r=await db.food_settlements.find_one({})
        await db.food_settlements.update_one({'_id':r['_id']},{'$set':{'status':'prepared'}})
        await food.recover_pending_food()
        self.assertEqual((await db.players.find_one({'tg_id':1}))['resources'],p['resources'])
