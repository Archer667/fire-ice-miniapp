import unittest
from datetime import datetime, timedelta
from unittest.mock import patch
import sys
import types

# تست منطق اقتصادی به اتصال دیتابیس/فایل env نیاز ندارد؛ محیط توسعهٔ سبک ممکن است
# python-dotenv را نصب نداشته باشد، پس فقط همان تابع بی‌اثر موردنیاز config را فراهم می‌کنیم.
if "dotenv" not in sys.modules:
    dotenv_stub = types.ModuleType("dotenv")
    dotenv_stub.load_dotenv = lambda *args, **kwargs: None
    sys.modules["dotenv"] = dotenv_stub

import game
from config import RESOURCE_CAPS
from game_data import (
    BUILDINGS, COMMON_TROOPS, NAVAL_TROOPS,
    building_cost, building_hours, building_max_level,
)


def player_at(moment, *, wood=0, buildings=None, castle_buildings=None):
    resources = {key: 0 for key in RESOURCE_CAPS}
    resources.update({"wood": wood, "men": 100})
    return {
        "tg_id": 1,
        "name": "test",
        "castle": "وینترفل",
        "created_at": moment,
        "last_tick": moment,
        "resources": resources,
        "popularity": 50,
        "tax_rate": 0,
        "stats": {},
        "buildings": buildings or {},
        "castle_buildings": castle_buildings or {},
    }


class BuildingEconomyTests(unittest.TestCase):
    def test_production_is_split_at_upgrade_completion(self):
        start = datetime(2026, 1, 1)
        player = player_at(start, buildings={
            "lumber_mill": {
                "level": 0,
                "upgrade_to": 1,
                "ready_at": start + timedelta(hours=12),
            },
        })

        with patch("game.now", return_value=start + timedelta(days=1)):
            game.apply_production(player)

        # ۵۰ تولید پایه در کل روز + ۹ تولید چوب‌بری فقط در نیمهٔ دوم روز.
        self.assertAlmostEqual(player["resources"]["wood"], 54.5)
        self.assertEqual(player["buildings"]["lumber_mill"]["level"], 1)
        self.assertIsNone(player["buildings"]["lumber_mill"]["upgrade_to"])
        self.assertEqual(player["buildings"]["lumber_mill"]["notice_pending"], 1)

    def test_lowered_cap_does_not_delete_existing_stock(self):
        start = datetime(2026, 1, 1)
        existing = RESOURCE_CAPS["wood"] + 500
        player = player_at(start, wood=existing)

        with patch("game.now", return_value=start + timedelta(days=1)):
            game.apply_production(player)

        self.assertEqual(player["resources"]["wood"], existing)

    def test_extra_castle_buildings_contribute_to_production(self):
        start = datetime(2026, 1, 1)
        player = player_at(start, castle_buildings={
            "ریوران": {"lumber_mill": {"level": 2}},
        })

        with patch("game.now", return_value=start + timedelta(days=1)):
            game.apply_production(player)

        self.assertEqual(player["resources"]["wood"], 68)

    def test_production_fields_contains_every_mutated_database_field(self):
        player = player_at(datetime(2026, 1, 1))
        self.assertEqual(
            set(game.production_fields(player)),
            {"resources", "last_tick", "stats", "buildings", "castle_buildings"},
        )

    def test_every_building_has_valid_cost_time_cap_and_links(self):
        allowed_resources = set(RESOURCE_CAPS)
        for building_id, meta in BUILDINGS.items():
            with self.subTest(building=building_id):
                self.assertGreater(float(meta["hours"]), 0)
                self.assertGreaterEqual(building_max_level(building_id), 1)
                self.assertTrue(meta.get("cost"))
                self.assertTrue(set(meta["cost"]).issubset(allowed_resources))
                self.assertTrue(set(meta.get("produces", {})).issubset(allowed_resources))
                self.assertTrue(set(meta.get("cap_bonus", {})).issubset(allowed_resources))
                self.assertTrue(all(value >= 0 for value in meta["cost"].values()))
                self.assertTrue(all(value >= 0 for value in meta.get("produces", {}).values()))
                self.assertTrue(all(value >= 0 for value in meta.get("cap_bonus", {}).values()))
                self.assertGreater(building_hours(building_id, 1), 0)
                cost_1 = building_cost(building_id, 1)
                cost_2 = building_cost(building_id, 2)
                self.assertEqual(set(cost_1), set(meta["cost"]))
                self.assertTrue(all(cost_2[key] >= cost_1[key] for key in cost_1))
                if meta.get("type") == "barracks":
                    self.assertIn(meta.get("unit"), COMMON_TROOPS)
                if meta.get("unit") and meta.get("type") == "armory":
                    self.assertIn(meta["unit"], COMMON_TROOPS)

    def test_all_naval_units_have_a_port_requirement(self):
        self.assertTrue(NAVAL_TROOPS)
        self.assertTrue(BUILDINGS["port"].get("requires_port"))


if __name__ == "__main__":
    unittest.main()
