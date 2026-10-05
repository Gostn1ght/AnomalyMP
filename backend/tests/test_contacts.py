from pathlib import Path
import sys
import unittest

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))
from lostzone.contacts import earliest_contact
from lostzone.store import Invalid


class ContactGeometryTest(unittest.TestCase):
    def test_crossing_paths_meet_even_when_endpoints_are_far_apart(self):
        first = [(0, [-100, 0, 0]), (1000, [100, 0, 0])]
        second = [(0, [0, 0, -100]), (1000, [0, 0, 100])]
        at = earliest_contact(first, second, 10)
        self.assertAlmostEqual(at, 500 - 10/(.2*2**.5))

    def test_polyline_contact_and_stationary_actor(self):
        first = [(0, [-100, 0, 0]), (500, [-100, 0, 100]), (1000, [100, 0, 100])]
        second = [(0, [0, 0, 100]), (1000, [0, 0, 100])]
        self.assertAlmostEqual(earliest_contact(first, second, 10), 725)

    def test_height_separation_parallel_motion_and_initial_contact(self):
        first = [(0, [-100, 0, 0]), (1000, [100, 0, 0])]
        above = [(0, [0, 20, -100]), (1000, [0, 20, 100])]
        self.assertIsNone(earliest_contact(first, above, 10))
        parallel = [(0, [-100, 0, 15]), (1000, [100, 0, 15])]
        self.assertIsNone(earliest_contact(first, parallel, 10))
        self.assertEqual(earliest_contact(first, first, 10), 0)

    def test_invalid_windows_nonfinite_and_unbounded_input(self):
        valid = [(0, [0, 0, 0]), (1000, [0, 0, 0])]
        for path in ([(0, [0, 0, 0]), (0, [0, 0, 0])],
                     [(1, [0, 0, 0]), (1000, [0, 0, 0])],
                     [(0, [float("nan"), 0, 0]), (1000, [0, 0, 0])],
                     valid*1024):
            with self.assertRaises(Invalid):
                earliest_contact(valid, path, 10)

    def test_small_contact_sphere_on_long_route_enters_at_surface(self):
        end = 86400000
        first = [(0, [-10000000, 0, 0]), (end, [10000000, 0, 0])]
        fixed = [(0, [0, 0, 0]), (end, [0, 0, 0])]
        self.assertAlmostEqual(earliest_contact(first, fixed, .1), end/2-.1/(20000000/end), places=6)
        # Reversing both trajectories must preserve the entry time and radius.
        reverse = [(0, [10000000, 0, 0]), (end, [-10000000, 0, 0])]
        self.assertAlmostEqual(earliest_contact(reverse, fixed, .1), earliest_contact(first, fixed, .1), places=6)

    def test_long_grazing_route_and_tangent_do_not_invent_an_early_contact(self):
        end = 86400000
        fixed = [(0, [0, 0, 0]), (end, [0, 0, 0])]
        first = [(0, [-10000000, .06, .079]), (end, [10000000, .06, .079])]
        chord = (.1**2-.06**2-.079**2)**.5
        self.assertAlmostEqual(earliest_contact(first, fixed, .1), end/2-chord/(20000000/end), places=6)
        tangent = [(0, [-10000000, .1, 0]), (end, [10000000, .1, 0])]
        self.assertEqual(earliest_contact(tangent, fixed, .1), end/2)
        outside = [(0, [-10000000, .100001, 0]), (end, [10000000, .100001, 0])]
        self.assertIsNone(earliest_contact(outside, fixed, .1))


if __name__ == "__main__":
    unittest.main()
