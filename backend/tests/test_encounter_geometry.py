import unittest
from datetime import datetime, timedelta
from encounter_geometry import legs, meeting, encounters

BASE = datetime(2026, 9, 17)


def time(minutes):
    return BASE + timedelta(minutes=minutes)


def army(path, start, end, **extra):
    return {'route_path': path, 'target_castle': path[-1],
            'created_at': time(start), 'arrival_at': time(end), **extra}


class EncounterGeometryTests(unittest.TestCase):
    def test_unequal_segments_use_route_weights(self):
        result = legs(army(['A', 'B', 'C'], 0, 60), {'A': {'B': 10}, 'B': {'C': 50}})
        self.assertEqual(result[0][3], time(10))
        self.assertEqual(result[1][2], time(10))

    def test_snapshotted_weights_survive_map_edits(self):
        result = legs(army(['A', 'B', 'C'], 0, 60, route_edge_minutes=[10, 50]),
                      {'A': {'B': 30}, 'B': {'C': 30}})
        self.assertEqual(result[0][3], time(10))

    def test_opposite_direction_meets_at_exact_position(self):
        self.assertEqual(meeting(('A', 'B', time(0), time(60)),
                                 ('B', 'A', time(20), time(80))), time(40))

    def test_same_direction_faster_army_catches_up(self):
        self.assertEqual(meeting(('A', 'B', time(0), time(60)),
                                 ('A', 'B', time(20), time(50))), time(40))

    def test_overlapping_edge_times_do_not_always_mean_collision(self):
        self.assertIsNone(meeting(('A', 'B', time(0), time(60)),
                                  ('A', 'B', time(20), time(80))))

    def test_intermediate_castle_meets_stationed_army(self):
        result = encounters(army(['A', 'B', 'C'], 0, 60), army(['B'], -20, -20),
                            {'A': {'B': 10}, 'B': {'C': 50}}, time(30))
        self.assertEqual(result, [(time(10), 'castle', ('B',))])

    def test_no_collision_when_castle_visits_do_not_overlap(self):
        result = encounters(army(['A', 'B', 'C'], 0, 60), army(['B'], 20, 20),
                            {'A': {'B': 10}, 'B': {'C': 50}}, time(90))
        self.assertEqual(result, [])

    def test_late_watcher_does_not_lose_past_intersection(self):
        result = encounters(army(['A', 'B'], 0, 60), army(['B', 'A'], 20, 80),
                            {'A': {'B': 60}, 'B': {'A': 60}}, time(120))
        self.assertIn((time(40), 'edge', ('A', 'B')), result)

    def test_future_collision_not_returned(self):
        result = encounters(army(['A', 'B'], 0, 60), army(['B', 'A'], 20, 80),
                            {'A': {'B': 60}, 'B': {'A': 60}}, time(30))
        self.assertEqual(result, [])

    def test_unknown_route_does_not_invent_castle_presence(self):
        result = encounters(army(['A', 'B'], 0, 60), army(['B'], 0, 0), {}, time(90))
        self.assertEqual(result, [])


if __name__ == '__main__':
    unittest.main()
