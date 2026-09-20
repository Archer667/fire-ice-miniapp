import unittest
from battle_parties import build_parties, compatible_winners, has_hostility


def army(uid, ident=None):
    return {'_id': ident or str(uid), 'tg_id': uid, 'player_name': str(uid)}


class BattlePartiesTests(unittest.TestCase):
    def test_three_enemies_remain_three_parties(self):
        parties = build_parties([army(1), army(2), army(3)])
        self.assertEqual([p['hostile_to'] for p in parties], [[2, 3], [1, 3], [1, 2]])
        self.assertFalse(compatible_winners(parties, [1, 2]))
        self.assertTrue(compatible_winners(parties, [3]))

    def test_friend_of_friend_is_not_a_friend(self):
        parties = build_parties([army(1), army(2), army(3)], [(1, 2), (2, 3)])
        self.assertEqual([p['hostile_to'] for p in parties], [[3], [], [1]])
        self.assertTrue(has_hostility(parties))
        self.assertFalse(compatible_winners(parties, [1, 3]))
        self.assertTrue(compatible_winners(parties, [1, 2]))

    def test_explicit_group_peace_prevents_all_fights(self):
        parties = build_parties([army(1), army(2), army(3)], [(1, 2), (1, 3), (2, 3)])
        self.assertFalse(has_hostility(parties))

    def test_multiple_armies_of_same_player_are_one_party(self):
        parties = build_parties([army(1, 'a'), army(1, 'b'), army(1, 'a'), army(2)])
        self.assertEqual(len(parties), 2)
        self.assertEqual(parties[0]['army_ids'], ['a', 'b'])
        self.assertEqual(parties[0]['hostile_to'], [2])

    def test_castle_owner_without_army_is_retained(self):
        parties = build_parties([army(1)], extra_players=[{'tg_id': 2, 'name': 'Owner'}])
        self.assertEqual(parties[1]['army_ids'], [])
        self.assertEqual(parties[1]['hostile_to'], [1])
        self.assertFalse(compatible_winners(parties, []))
        self.assertFalse(compatible_winners(parties, [999]))


if __name__ == '__main__':
    unittest.main()
