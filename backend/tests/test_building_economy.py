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
from config import DAILY_PRODUCTION, RESOURCE_CAPS, SEASON_LENGTH_DAYS, STARTING_RESOURCES
from game_data import (
    BUILDINGS, COMMON_TROOPS, NAVAL_TROOPS,
    building_cap_bonus, building_cost, building_hours, building_max_level, building_produces,
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

        # ۵۰ تولید پایه در کل روز + ۱۴ تولید چوب‌بری فقط در نیمهٔ دوم روز.
        self.assertAlmostEqual(player["resources"]["wood"], 57)
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

        self.assertEqual(player["resources"]["wood"], 78)

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

    def test_30_day_season_curve_is_reachable_but_not_front_loaded(self):
        """همهٔ ساختمان‌های یک قلعهٔ بندری باید در فصل قابل فول باشند، اما نه
        آن‌قدر ارزان که کل پیشرفت اقتصادی در هفتهٔ اول تمام شود."""
        total_cost = {}
        total_levels = 0
        longest_independent_queue = 0
        for building_id in BUILDINGS:
            max_level = building_max_level(building_id)
            total_levels += max_level
            longest_independent_queue = max(
                longest_independent_queue,
                sum(building_hours(building_id, level) for level in range(1, max_level + 1)),
            )
            for level in range(1, max_level + 1):
                for resource, amount in building_cost(building_id, level).items():
                    total_cost[resource] = total_cost.get(resource, 0) + amount

        self.assertEqual(building_max_level("siege_workshop"), 3)
        self.assertTrue(all(
            building_max_level(building_id) == 8
            for building_id in BUILDINGS if building_id != "siege_workshop"
        ))
        self.assertEqual(total_levels, 211)
        self.assertGreaterEqual(total_cost["gold"], 11_000)
        self.assertLessEqual(total_cost["gold"], 13_000)
        self.assertLess(longest_independent_queue, SEASON_LENGTH_DAYS * 24)

    def test_active_player_finishes_near_end_of_30_day_season(self):
        """شبیه‌سازی محافظه‌کارانه: رسیدگی روزی یک‌بار، قلعهٔ بندری، محبوبیت ۵۰
        و هم‌زمان ۵۰ طلا و ۱۰۰ غذا خرج فعالیت نظامی در هر روز."""
        economic_first = [
            "gold_mine", "market", "lumber_mill", "stone_mine", "iron_mine",
            "farm", "ranch", "winery", "treasury", "goods_warehouse",
            "warehouse", "village", "weapon_warehouse",
        ]
        priority = economic_first + [bid for bid in BUILDINGS if bid not in economic_first]
        resources = {key: float(value) for key, value in STARTING_RESOURCES.items()}
        levels = {bid: 0 for bid in BUILDINGS}
        busy_until = {}
        completed_at = None

        for hour in range(SEASON_LENGTH_DAYS * 24 + 1):
            if hour:
                production = dict(DAILY_PRODUCTION)
                for building_id, level in levels.items():
                    for resource, amount in building_produces(building_id).items():
                        production[resource] = production.get(resource, 0) + amount * level
                # محبوبیت ۵۰ رشد جمعیت را عادی نگه می‌دارد؛ مالیات پیش‌فرض ۱۰٪
                # با ضریب محبوبیت ۰٫۷۵ محاسبه می‌شود.
                production["gold"] += resources["men"] * 0.10 * 0.75
                production["gold"] -= 50
                production["food"] -= 100

                caps = dict(RESOURCE_CAPS)
                for building_id, level in levels.items():
                    for resource, amount in building_cap_bonus(building_id).items():
                        caps[resource] = caps.get(resource, 10 ** 9) + amount * level
                for resource, daily_amount in production.items():
                    resources[resource] = max(
                        0,
                        min(caps.get(resource, 10 ** 9), resources.get(resource, 0) + daily_amount / 24),
                    )

            for building_id, ready_hour in list(busy_until.items()):
                if ready_hour <= hour:
                    levels[building_id] += 1
                    del busy_until[building_id]

            # بازیکن فقط هر ۲۴ ساعت درخواست‌های ساخت بعدی را ثبت می‌کند.
            if hour % 24 == 0:
                for building_id in priority:
                    if building_id in busy_until or levels[building_id] >= building_max_level(building_id):
                        continue
                    target_level = levels[building_id] + 1
                    cost = building_cost(building_id, target_level)
                    if all(resources.get(resource, 0) >= amount for resource, amount in cost.items()):
                        for resource, amount in cost.items():
                            resources[resource] -= amount
                        busy_until[building_id] = hour + building_hours(building_id, target_level)

            if all(levels[bid] == building_max_level(bid) for bid in BUILDINGS):
                completed_at = hour / 24
                break

        self.assertIsNotNone(completed_at)
        self.assertGreaterEqual(completed_at, 24)
        self.assertLessEqual(completed_at, SEASON_LENGTH_DAYS)


if __name__ == "__main__":
    unittest.main()
