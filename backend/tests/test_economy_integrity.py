import unittest
from contextlib import ExitStack
from datetime import datetime
from unittest.mock import AsyncMock, patch

from mongomock_motor import AsyncMongoMockClient

import family
import project_engine
from routers import economy


class EconomyIntegrityTests(unittest.IsolatedAsyncioTestCase):
    async def asyncSetUp(self):
        self.mem = AsyncMongoMockClient()["economy_integrity_test"]
        self.stack = ExitStack()
        self.addCleanup(self.stack.close)
        for module, name, value in [
            (economy, "db", self.mem),
            (economy, "players", self.mem.players),
            (economy, "orders", self.mem.market_buy_orders),
            (economy, "contracts", self.mem.supply_contracts),
            (family, "db", self.mem),
            (family, "operations", self.mem.family_operations),
            (project_engine, "players", self.mem.players),
        ]:
            self.stack.enter_context(patch.object(module, name, value))
        self.stack.enter_context(patch.object(project_engine, "apply_production", side_effect=lambda player: player))
        self.stack.enter_context(patch.object(project_engine, "production_fields", side_effect=lambda player: {"resources": player["resources"]}))
        self.stack.enter_context(patch.object(economy, "realm_rules", AsyncMock(return_value={
            "market_fee_percent": 2, "cross_region_tariff_percent": 3,
        })))
        self.stack.enter_context(patch.object(economy, "send_system_message", AsyncMock()))
        self.stack.enter_context(patch.object(economy, "adjust_reputation", AsyncMock(return_value=1)))
        self.stack.enter_context(patch.object(economy, "adjust_influence", AsyncMock(return_value=21)))
        self.stack.enter_context(patch.object(economy, "record_event", AsyncMock()))
        stamp = datetime(2026, 1, 1)
        await self.mem.players.insert_many([
            {"tg_id": 1, "name": "Buyer", "created_at": stamp, "castle": "A", "region": "north", "resources": {"gold": 10000, "food": 0}},
            {"tg_id": 2, "name": "Seller", "created_at": stamp, "castle": "B", "region": "river", "resources": {"gold": 0, "food": 500}},
        ])

    async def test_buy_order_escrow_fill_and_recovery_receipts(self):
        created = await economy.create_order(economy.OrderBody(resource="food", qty=100, unit_price=10), {"id": 1})
        self.assertEqual((await self.mem.players.find_one({"tg_id": 1}))["resources"]["gold"], 9000)
        result = await economy.fill_order(created["id"], economy.FillBody(qty=40), {"id": 2})
        self.assertEqual((result["gross"], result["fee"], result["payout"], result["remaining"]), (400, 20, 380, 60))
        buyer = await self.mem.players.find_one({"tg_id": 1})
        seller = await self.mem.players.find_one({"tg_id": 2})
        self.assertEqual(buyer["resources"]["food"], 40)
        self.assertEqual(seller["resources"]["food"], 460)
        self.assertEqual(seller["resources"]["gold"], 380)
        self.assertEqual((await self.mem.realm_treasury.find_one({"_id": "trade"}))["gold"], 20)
        self.assertTrue((await self.mem.family_operations.find_one({"kind": "market_buy_order_fill"}))["complete"])

    async def test_rejected_contract_returns_entire_escrow(self):
        created = await economy.create_contract(economy.ContractBody(
            seller_id=2, resource="food", qty_per_delivery=10, unit_price=20,
            deliveries=3, interval_hours=24, note="آذوقه",
        ), {"id": 1})
        self.assertEqual((await self.mem.players.find_one({"tg_id": 1}))["resources"]["gold"], 9400)
        await economy.respond_contract(created["id"], economy.RespondBody(accept=False), {"id": 2})
        buyer = await self.mem.players.find_one({"tg_id": 1})
        row = await self.mem.supply_contracts.find_one({})
        self.assertEqual(buyer["resources"]["gold"], 10000)
        self.assertEqual((row["status"], row["escrow_remaining"]), ("rejected", 0))

    async def test_escrow_is_never_paid_to_a_replacement_character(self):
        order = await economy.create_order(economy.OrderBody(resource="food", qty=10, unit_price=10), {"id": 1})
        replacement = datetime(2026, 2, 1)
        await self.mem.players.update_one({"tg_id": 1}, {"$set": {"created_at": replacement}})
        before = (await self.mem.players.find_one({"tg_id": 1}))["resources"]["gold"]
        await economy.cancel_order(order["id"], {"id": 1})
        after = (await self.mem.players.find_one({"tg_id": 1}))["resources"]["gold"]
        self.assertEqual(after, before)
        self.assertEqual((await self.mem.market_buy_orders.find_one({"_id": order["id"]})), None)
        closed = await self.mem.market_buy_orders.find_one({})
        self.assertEqual(closed["status"], "cancelled")

        await self.mem.players.update_one({"tg_id": 1}, {"$set": {"created_at": datetime(2026, 1, 1)}})
        contract = await economy.create_contract(economy.ContractBody(
            seller_id=2, resource="food", qty_per_delivery=5, unit_price=10,
            deliveries=2, interval_hours=24, note="آذوقه",
        ), {"id": 1})
        await self.mem.players.update_one({"tg_id": 1}, {"$set": {"created_at": replacement}})
        before = (await self.mem.players.find_one({"tg_id": 1}))["resources"]["gold"]
        await economy.respond_contract(contract["id"], economy.RespondBody(accept=False), {"id": 2})
        after = (await self.mem.players.find_one({"tg_id": 1}))["resources"]["gold"]
        self.assertEqual(after, before)
        self.assertEqual((await self.mem.supply_contracts.find_one({"_id": economy._oid(contract["id"])}))["status"], "rejected")

