"""Bounded, incremental 3D corridor index for abstract route candidates.

Cells only select candidates. Time-overlapping segment bounds are checked
before the continuous narrow phase; entering a cell does not start a fight.
Overflow rejects admission rather than silently dropping possible contacts.
"""
import itertools
import math

from .offline import point
from .store import Invalid, Unavailable, finite, identifier, persistent_id


class CandidateBudget:
    """Shared work admission across all spatial queries in a planning pass."""
    def __init__(self, maximum=200000):
        if type(maximum) is not int or not 1 <= maximum <= 1_000_000:
            raise Invalid("invalid candidate work budget")
        self.remaining = maximum

    def consume(self, amount=1):
        self.remaining -= amount
        if self.remaining < 0:
            raise Unavailable("contact candidate work budget exhausted")


class ContactIndex:
    def __init__(self, cell_size=100, *, max_entities=256, max_segments=8192,
                 max_references=131072, max_cells=4096, max_checks=200000,
                 max_pairs=4096):
        self.cell_size = finite(cell_size, 1, 10000)
        self.limits = {}
        for name,value in {"max_entities":max_entities,"max_segments":max_segments,
                           "max_references":max_references,"max_cells":max_cells,
                           "max_checks":max_checks,"max_pairs":max_pairs}.items():
            if type(value) is not int or not 1 <= value <= 1_000_000:
                raise Invalid("invalid contact index budget")
            self.limits[name] = value
        self.entries, self.cells = {}, {}
        self.references = self.segments = 0

    def cell_keys(self, location, lower, upper):
        ends = [(math.floor(a/self.cell_size), math.floor(b/self.cell_size)) for a,b in zip(lower,upper)]
        count = math.prod(b-a+1 for a,b in ends)
        if count > self.limits["max_cells"]:
            raise Unavailable("route corridor exceeds cell budget; shorten planning horizon")
        return [(location,*xyz) for xyz in itertools.product(*(range(a,b+1) for a,b in ends))]

    def upsert(self, entity_id, location, path):
        persistent_id(entity_id); identifier(location)
        if not isinstance(path,list) or not 2 <= len(path) <= 1026:
            raise Invalid("index requires bounded trajectory")
        validated = []
        previous = -1
        for at,position in path:
            finite(at)
            if at <= previous:
                raise Invalid("trajectory times must increase")
            validated.append((at,tuple(point(position))))
            previous = at
        old = self.entries.get(entity_id)
        old_refs,old_segments = (old[3],len(old[1])) if old else (0,0)
        if (len(self.entries)+(0 if old else 1) > self.limits["max_entities"] or
                self.segments-old_segments+len(validated)-1 > self.limits["max_segments"]):
            raise Unavailable("contact index admission budget exhausted")
        segments, keys, refs = [], [], 0
        for first,second in zip(validated,validated[1:]):
            lower = tuple(min(a,b) for a,b in zip(first[1],second[1]))
            upper = tuple(max(a,b) for a,b in zip(first[1],second[1]))
            segments.append((first[0],second[0],lower,upper))
            segment_keys = self.cell_keys(location,lower,upper)
            refs += len(segment_keys)
            if self.references-old_refs+refs > self.limits["max_references"]:
                raise Unavailable("contact index admission budget exhausted")
            keys.append(segment_keys)
        # Validate the complete replacement before removing its previous entry.
        self.erase(entity_id)
        self.entries[entity_id] = (location,segments,keys,refs)
        self.references += refs
        self.segments += len(segments)
        for number,segment_keys in enumerate(keys):
            for key in segment_keys:
                self.cells.setdefault(key,set()).add((entity_id,number))

    def erase(self, entity_id):
        persistent_id(entity_id)
        old = self.entries.pop(entity_id,None)
        if old is None:
            return
        self.references -= old[3]
        self.segments -= len(old[1])
        for number,keys in enumerate(old[2]):
            for key in keys:
                bucket = self.cells[key]
                bucket.remove((entity_id,number))
                if not bucket:
                    del self.cells[key]

    def query(self, location, path, radius, budget=None):
        """Read-only corridor lookup, sharing a budget across member paths.

        The returned IDs are broad-phase candidates; individual hazard radii,
        immunity and continuous contact still belong to the narrow phase.
        """
        identifier(location);finite(radius,.1,200)
        if not isinstance(path,list) or not 2 <= len(path) <= 1026:
            raise Invalid("query requires bounded trajectory")
        validated,previous = [],-1
        for at,position in path:
            finite(at)
            if at <= previous:
                raise Invalid("trajectory times must increase")
            validated.append((at,point(position)))
            previous = at
        if len(path)-1 > self.limits["max_segments"]:
            raise Unavailable("contact query segment budget exhausted")
        budget = budget or CandidateBudget(self.limits["max_checks"])
        result = set()
        for first,second in zip(validated,validated[1:]):
            lower = [min(a,b)-radius for a,b in zip(first[1],second[1])]
            upper = [max(a,b)+radius for a,b in zip(first[1],second[1])]
            seen = set()
            for key in self.cell_keys(location,lower,upper):
                budget.consume()
                for candidate in self.cells.get(key,()):
                    budget.consume()
                    if candidate in seen:
                        continue
                    seen.add(candidate)
                    entity_id,number = candidate
                    start,end,lo,hi = self.entries[entity_id][1][number]
                    if start>second[0] or end<first[0] or any(a>h or b<l for a,b,l,h in zip(lower,upper,lo,hi)):
                        continue
                    result.add(entity_id)
                    if len(result)>self.limits["max_pairs"]:
                        raise Unavailable("contact query candidate budget exhausted")
        return sorted(result)

    def pairs(self, radius, budget=None, owners=None):
        finite(radius,.1,200)
        result = set()
        budget = budget or CandidateBudget(self.limits["max_checks"])
        for entity_id,(location,segments,_,_) in sorted(self.entries.items()):
            for start,end,lower,upper in segments:
                expanded_lower = tuple(value-radius for value in lower)
                expanded_upper = tuple(value+radius for value in upper)
                seen = set()
                for key in self.cell_keys(location,expanded_lower,expanded_upper):
                    budget.consume()
                    for candidate in self.cells.get(key,()):
                        budget.consume()
                        other,number = candidate
                        if other <= entity_id or candidate in seen:
                            continue
                        seen.add(candidate)
                        if owners is not None and owners[other] == owners[entity_id]:
                            continue
                        a,b,lo,hi = self.entries[other][1][number]
                        if a > end or b < start or any(x > h or y < l for x,y,l,h in zip(expanded_lower,expanded_upper,lo,hi)):
                            continue
                        result.add((entity_id,other))
                        if len(result) > self.limits["max_pairs"]:
                            raise Unavailable("contact pair budget exhausted")
        return sorted(result)
