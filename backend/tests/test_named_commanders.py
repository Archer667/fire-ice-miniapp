import unittest
from datetime import datetime, timedelta
from unittest.mock import AsyncMock, patch
from bson import ObjectId

from db import db, players, campaigns
from routers import war


class NamedCommanderTests(unittest.IsolatedAsyncioTestCase):
    async def asyncSetUp(self):
        for name in ("players", "campaigns", "character_locations", "family_children", "messages"):
            await db[name].delete_many({})
        self.at = datetime.utcnow().replace(microsecond=0)
        self.owner = {"tg_id": 1, "name": "مالک", "gender": "lord", "castle": "Winterfell", "region": "north",
                      "created_at": self.at, "resources": {"gold": 100, "men": 100}}
        self.guest = {"tg_id": 2, "name": "مهمان", "gender": "lord", "castle": "Eyrie", "region": "vale",
                      "created_at": self.at, "resources": {"gold": 100, "men": 100}}
        await players.insert_many([self.owner, self.guest])
        await db.character_locations.insert_many([
            {"_id": f"1:{self.at}", "tg_id": 1, "name": "مالک", "place": "Winterfell", "trip": None, "captive": None},
            {"_id": f"2:{self.at}", "tg_id": 2, "name": "مهمان", "place": "Winterfell", "trip": None, "captive": None},
            {"_id": "child:heir", "name": "وارث", "place": "Winterfell", "trip": None, "captive": None},
        ])
        await db.family_children.insert_one({"_id": "heir", "name": "وارث", "patron_key": f"1:{self.at}",
            "status": "alive", "adult_at": self.at - timedelta(days=1), "residence": "Winterfell"})

    async def test_options_include_present_owner_adult_child_and_guest(self):
        result = await war.commander_options("Winterfell", {"id": 1})
        kinds = {row["kind"] for row in result["options"]}
        self.assertEqual(kinds, {"self", "child", "guest"})
        guest = next(row for row in result["options"] if row["kind"] == "guest")
        self.assertTrue(guest["requires_acceptance"])
        self.assertEqual(result["power_bonus_percent"], 15)
        self.assertEqual(result["speed_bonus_percent"], 10)

    async def test_guest_rejection_refunds_reserved_resources(self):
        oid = ObjectId()
        await campaigns.insert_one({"_id": oid, "tg_id": 1, "player_name": "مالک", "name": "سپاه",
            "origin_castle": "Winterfell", "target_castle": "Moat Cailin", "status": "awaiting_commander", "active": False,
            "commander": {"key": f"2:{self.at}", "tg_id": 2, "name": "مهمان", "kind": "guest", "status": "pending"},
            "reserved_cost": {"gold": 20, "men": 30}, "men_committed": 30, "gold_cost": 20, "created_at": self.at})
        with patch.object(war, "send_system_message", AsyncMock()):
            result = await war.commander_response(str(oid), war.CommanderResponseBody(accept=False), {"id": 2})
        self.assertFalse(result["accepted"])
        stored = await campaigns.find_one({"_id": oid})
        self.assertEqual(stored["status"], "commander_rejected")
        owner = await players.find_one({"tg_id": 1})
        self.assertEqual(owner["resources"], {"gold": 120, "men": 130})

    async def test_guest_acceptance_starts_movement(self):
        oid = ObjectId()
        await campaigns.insert_one({"_id": oid, "tg_id": 1, "player_name": "مالک", "name": "سپاه",
            "origin_castle": "Winterfell", "target_castle": "Moat Cailin", "status": "awaiting_commander", "active": False,
            "commander": {"key": f"2:{self.at}", "tg_id": 2, "name": "مهمان", "kind": "guest", "status": "pending"},
            "travel_minutes": 90, "men_committed": 100, "created_at": self.at})
        with patch.object(war, "notify_campaign_departure", AsyncMock()), patch.object(war, "send_system_message", AsyncMock()):
            result = await war.commander_response(str(oid), war.CommanderResponseBody(accept=True), {"id": 2})
        self.assertTrue(result["accepted"])
        stored = await campaigns.find_one({"_id": oid})
        self.assertTrue(stored["active"])
        self.assertTrue(stored["commander_present"])
        self.assertEqual(stored["commander"]["status"], "accepted")
        self.assertGreater(stored["arrival_at"], stored["created_at"])


if __name__ == "__main__":
    unittest.main()
