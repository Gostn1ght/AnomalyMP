from pathlib import Path
import random
import sys
import unittest

sys.path.insert(0,str(Path(__file__).resolve().parents[1]))
from lostzone.contact_index import ContactIndex
from lostzone.contacts import earliest_contact
from lostzone.store import Invalid, Unavailable


def uid(value):
    return f"{value:032x}"


def path(a,b,start=0,end=1000):
    return [(start,a),(end,b)]


class ContactIndexTest(unittest.TestCase):
    def test_candidates_cover_exact_contacts_across_negative_cell_boundaries(self):
        rng = random.Random(42)
        index = ContactIndex(cell_size=25,max_checks=1_000_000)
        paths = {uid(i):[(0,[rng.uniform(-100,100),rng.uniform(-10,10),rng.uniform(-100,100)]),
                         (500,[rng.uniform(-100,100),rng.uniform(-10,10),rng.uniform(-100,100)]),
                         (1000,[rng.uniform(-100,100),rng.uniform(-10,10),rng.uniform(-100,100)])]
                 for i in range(1,33)}
        for entity_id,value in reversed(list(paths.items())):
            index.upsert(entity_id,"cordon",value)
        candidates = set(index.pairs(5))
        exact = {(first,second) for first in paths for second in paths if first<second and
                 earliest_contact(paths[first],paths[second],5) is not None}
        self.assertTrue(exact)
        self.assertTrue(exact <= candidates)
        self.assertEqual(index.pairs(5),sorted(candidates))

    def test_location_height_time_and_radius_are_independent(self):
        index = ContactIndex()
        index.upsert(uid(1),"cordon",path([-1,0,0],[1,0,0]))
        index.upsert(uid(2),"jupiter",path([-1,0,0],[1,0,0]))
        index.upsert(uid(3),"cordon",path([-1,100,0],[1,100,0]))
        index.upsert(uid(4),"cordon",path([-1,0,0],[1,0,0],2000,3000))
        index.upsert(uid(5),"cordon",path([4,0,0],[4,0,0]))
        self.assertEqual(index.pairs(2),[])
        self.assertEqual(index.pairs(5),[(uid(1),uid(5))])

    def test_move_remove_and_invalid_replacement_preserve_index(self):
        index = ContactIndex()
        index.upsert(uid(1),"cordon",path([0,0,0],[0,0,0]))
        index.upsert(uid(2),"cordon",path([1,0,0],[1,0,0]))
        before = index.references
        with self.assertRaises(Unavailable):
            index.upsert(uid(2),"cordon",path([-1e7,-1e7,-1e7],[1e7,1e7,1e7]))
        self.assertEqual(index.pairs(2),[(uid(1),uid(2))])
        self.assertEqual(index.references,before)
        with self.assertRaises(Invalid):
            index.upsert(uid(2),"cordon",[(0,[0,0,0]),(0,[0,0,0])])
        index.upsert(uid(2),"jupiter",path([0,0,0],[0,0,0]))
        self.assertEqual(index.pairs(2),[])
        index.erase(uid(1));index.erase(uid(2));index.erase(uid(2))
        self.assertEqual((index.references,index.segments,len(index.cells)),(0,0,0))

    def test_dense_pair_and_work_overflow_refuse_instead_of_truncating(self):
        for limits in ({"max_pairs":1},{"max_checks":1}):
            index = ContactIndex(**limits)
            for i in range(1,4):
                index.upsert(uid(i),"cordon",path([0,0,0],[0,0,0]))
            with self.assertRaises(Unavailable):
                index.pairs(5)
            self.assertEqual(len(index.entries),3)

    def test_entity_segment_reference_limits_leave_previous_entries_intact(self):
        for limits in ({"max_entities":1},{"max_segments":1},{"max_references":1}):
            index = ContactIndex(**limits)
            index.upsert(uid(1),"cordon",path([0,0,0],[0,0,0]))
            with self.assertRaises(Unavailable):
                index.upsert(uid(2),"cordon",path([0,0,0],[0,0,0]))
            self.assertEqual(list(index.entries),[uid(1)])


if __name__=="__main__":
    unittest.main()
