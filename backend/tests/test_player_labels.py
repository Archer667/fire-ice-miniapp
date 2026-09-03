import unittest

from player_labels import honorific, titled_name


class PlayerLabelTests(unittest.TestCase):
    def test_lady_is_never_rendered_as_lord(self):
        lady = {"name": "آریا", "gender": "lady"}
        self.assertEqual(honorific(lady), "لیدی")
        self.assertEqual(titled_name(lady), "لیدی آریا")

    def test_lord_label_and_legacy_fallback(self):
        self.assertEqual(titled_name({"name": "جان", "gender": "lord"}), "لرد جان")
        self.assertEqual(titled_name(name="بازیکن قدیمی"), "لرد بازیکن قدیمی")

    def test_database_gender_wins_over_legacy_snapshot(self):
        lady = {"name": "سانسا", "gender": "lady"}
        self.assertEqual(titled_name(lady, name="نام قدیمی", gender="lord"), "لیدی سانسا")


if __name__ == "__main__":
    unittest.main()
