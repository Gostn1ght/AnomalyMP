"""Continuous contact between two bounded piecewise-linear world trajectories.

Candidate discovery belongs to the location spatial index. This narrow phase
handles one pair with linear work in its route segments, without frame ticks,
observer inputs, or endpoint-only tests that miss crossing paths.
"""
import json
import math

from .offline import distance, point
from .store import Invalid, finite


def trajectory(offline, tx, entity, start, end):
    route = tx.execute("SELECT * FROM route WHERE entity_id=? AND active=1", (entity["id"],)).fetchone()
    offset = [0,0,0]
    if not route and entity["alive"]:
        group = tx.execute("SELECT e.* FROM group_member m JOIN entity e ON e.id=m.group_id WHERE m.member_id=?",(entity["id"],)).fetchone()
        if group:
            offline.require_offline(tx,group["id"])
            if group["alive"] and group["location"] == entity["location"]:
                offset = [a-b for a,b in zip(point(json.loads(entity["state"]).get("position")),
                                           point(json.loads(group["state"]).get("position")))]
                route = tx.execute("SELECT * FROM route WHERE entity_id=? AND active=1", (group["id"],)).fetchone()
    result = [(start, offline.position_at(tx, entity, start))]
    if route:
        points = [point([a+b for a,b in zip(point(p),offset)]) for p in json.loads(route["points"])]
        if not 2 <= len(points) <= 1024:
            raise Invalid("invalid stored route")
        lengths = [distance(a, b) for a, b in zip(points, points[1:])]
        total = sum(lengths)
        if total <= .001 or route["arrival_ms"] <= route["started_ms"]:
            raise Invalid("invalid route duration/distance")
        travelled = 0
        if start < route["started_ms"] < end:
            result.append((route["started_ms"], points[0]))
        for length, position in zip(lengths, points[1:]):
            travelled += length
            at = route["started_ms"] + travelled / total * (route["arrival_ms"] - route["started_ms"])
            if start < at < end:
                if result[-1][0] == at:
                    result[-1] = (at, position)
                else:
                    result.append((at, position))
    result.append((end, offline.position_at(tx, entity, end)))
    return result


def interpolate(a, b, at):
    t = (at - a[0]) / (b[0] - a[0])
    return [x + (y - x) * t for x, y in zip(a[1], b[1])]


def entry_fraction(p, delta, radius):
    """First t in [0,1] inside the relative-motion sphere, or None."""
    c = sum(x*x for x in p) - radius*radius
    if c <= 0:
        return 0.0
    a = sum(x*x for x in delta)
    if a == 0:
        return None
    b = 2 * sum(x*y for x, y in zip(p, delta))
    closest = min(1.0, max(0.0, -b/(2*a)))
    if sum((x+y*closest)**2 for x, y in zip(p, delta)) > radius*radius:
        return None
    discriminant = max(0.0, b*b - 4*a*c)
    # Stable quadratic roots avoid cancellation with a distant initial pair.
    q = -.5 * (b + math.copysign(math.sqrt(discriminant), b))
    if q == 0:
        return closest
    roots = sorted((q/a, c/q))
    for value in roots:
        if 0 <= value <= 1:
            return value
    return None


def earliest_contact(first, second, radius):
    finite(radius, .1, 200)
    for path in (first, second):
        if not isinstance(path, list) or not 2 <= len(path) <= 1026:
            raise Invalid("contact requires bounded trajectories")
        previous = -1
        for at, position in path:
            finite(at)
            point(position)
            if at <= previous:
                raise Invalid("trajectory times must increase")
            previous = at
    if first[0][0] != second[0][0] or first[-1][0] != second[-1][0]:
        raise Invalid("trajectory windows differ")
    i = j = 0
    at = first[0][0]
    while i < len(first)-1 and j < len(second)-1:
        until = min(first[i+1][0], second[j+1][0])
        a, b = interpolate(first[i], first[i+1], at), interpolate(second[j], second[j+1], at)
        aa, bb = interpolate(first[i], first[i+1], until), interpolate(second[j], second[j+1], until)
        fraction = entry_fraction([x-y for x, y in zip(a, b)],
                                  [(x-p)-(y-q) for x, p, y, q in zip(aa, a, bb, b)], radius)
        if fraction is not None:
            return at + (until-at)*fraction
        at = until
        if first[i+1][0] == until:
            i += 1
        if second[j+1][0] == until:
            j += 1
    return None
