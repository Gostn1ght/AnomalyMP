"""Ownership-aware abstract travel without per-NPC ticks or respawn.

Engine adapters must commit dehydration before removing runtime entities and
complete hydration/placement before replication. This module owns only the
backend representation; it cannot turn a legacy ALife object off by itself.
"""
import hashlib
import json
import math

from .ownership import Ownership
from .store import Conflict, Invalid, canonical, finite, identifier, persistent_id, positive


def point(value):
    if not isinstance(value, list) or len(value) != 3:
        raise Invalid("route point requires x/y/z")
    return [finite(number, -1e7, 1e7) for number in value]


def distance(a, b):
    return math.sqrt(sum((x - y) ** 2 for x, y in zip(a, b)))


def route_position(points, progress):
    lengths = [distance(a, b) for a, b in zip(points, points[1:])]
    travelled = min(1, max(0, progress)) * sum(lengths)
    for index, length in enumerate(lengths):
        if travelled <= length and length > 0:
            t = travelled / length
            return [a + (b - a) * t for a, b in zip(points[index], points[index + 1])], index
        travelled -= length
    return list(points[-1]), len(points) - 1


class Offline:
    def __init__(self, world, scheduler):
        if scheduler.world is not world:
            raise Conflict("offline scheduler belongs to another world authority")
        self.world, self.store, self.scheduler = world, world.store, scheduler
        self.ownership = Ownership(world)
        scheduler.handlers["RouteArrived"] = self.arrived
        world.scale_handlers.append(self.scale_changed)

    def members(self, tx, root, limit=None):
        result = [root]
        if root["kind"] == "GROUP":
            for value in json.loads(root["state"])["member_ids"]:
                # Keep permanent casualty IDs in the roster, but do not load
                # their potentially large state blobs for a living-members
                # capture. SQLite evaluates the CASE before returning state.
                row = tx.execute("SELECT id,kind,location,writer,fence,version,alive,"
                                 "CASE WHEN alive=1 THEN state ELSE NULL END AS state "
                                 "FROM entity WHERE id=?", (value,)).fetchone()
                if not row:
                    raise Conflict("persistent member disappeared")
                if row["alive"]:
                    result.append(row)
                    if limit is not None and len(result)>limit:
                        raise Conflict("member capture exceeds admission limit")
        return result

    def dehydrate(self, actor, command_id, entity_id, location, fence, version, captures):
        persistent_id(entity_id)
        identifier(location)
        positive(fence, "fence")
        positive(version)
        if not isinstance(captures, dict):
            raise Invalid("dehydration requires immutable member captures")
        payload = {"type": "dehydrate", "entity_id": entity_id, "location": location,
                   "fence": fence, "version": version, "captures": captures}
        def apply(tx):
            root = self.ownership.require_entity(tx, actor, entity_id, fence, version)
            if root["kind"] not in ("GROUP", "NPC", "MUTANT", "STASH", "CONTAINER", "DOOR", "TRAP", "CAMPFIRE", "ANOMALY", "NEST") or root["location"] != location:
                raise Conflict("entity is not a local abstractable actor")
            if root["alive"] and root["kind"] != "GROUP" and tx.execute("SELECT 1 FROM group_member WHERE member_id=?", (entity_id,)).fetchone():
                raise Conflict("dehydrate the persistent group instead of one of its members")
            rows = self.members(tx, root)
            if set(captures) != {row["id"] for row in rows}:
                raise Conflict("capture does not match the complete living membership")
            for row in rows:
                capture = captures[row["id"]]
                if not isinstance(capture, dict) or set(capture) != {"version", "state"}:
                    raise Invalid("capture requires version and full state")
                positive(capture["version"])
                self.ownership.require_entity(tx, actor, row["id"], fence, capture["version"])
                if row["location"] != location or not isinstance(capture.get("state"), dict):
                    raise Conflict("member capture is outside this location")
                state = capture["state"]
                point(state.get("position"))
                if row["kind"] == "GROUP" and state.get("member_ids") != json.loads(row["state"]).get("member_ids"):
                    raise Conflict("dehydration cannot replace group membership")
                tx.execute("UPDATE entity SET writer=?,fence=?,state=?,version=version+1 WHERE id=?",
                           ("offline:" + location, self.store.epoch, canonical(state), row["id"]))
            event = self.store.event(tx, "entity:" + entity_id, "DehydrationCommitted", payload, self.world.now())
            return {"id": entity_id, "version": version + 1, "world_fence": self.store.epoch, "event": event}
        return self.store.command(actor, command_id, payload, apply,
                                  authorize=lambda tx: self.world.require_location(tx, actor, location, fence))

    def require_offline(self, tx, entity_id, version=None):
        persistent_id(entity_id)
        row = tx.execute("SELECT * FROM entity WHERE id=?", (entity_id,)).fetchone()
        if not row or row["writer"] != "offline:" + row["location"] or row["fence"] != self.store.epoch:
            raise Conflict("entity is not owned by the current offline authority")
        if version is not None and row["version"] != positive(version):
            raise Conflict("abstract entity version changed")
        return row

    def start_route(self, actor, command_id, entity_id, version, points, speed_real, seed):
        if not isinstance(points, list) or not 2 <= len(points) <= 1024:
            raise Invalid("route requires bounded polyline points")
        points = [point(value) for value in points]
        finite(speed_real, .01, 100)
        if type(seed) is not int or not 0 <= seed < 2**64:
            raise Invalid("route seed must be stable")
        payload = {"type": "route_start", "entity_id": entity_id, "version": version,
                   "points": points, "speed_real": speed_real, "seed": seed}
        def apply(tx):
            root = self.require_offline(tx, entity_id, version)
            if root["kind"] not in ("GROUP", "NPC", "MUTANT"):
                raise Conflict("static object cannot start an actor route")
            if not root["alive"]:
                raise Conflict("dead actor cannot start moving again")
            if root["kind"] != "GROUP" and tx.execute("SELECT 1 FROM group_member WHERE member_id=?", (entity_id,)).fetchone():
                raise Conflict("route belongs to the persistent group")
            now = self.world.now()
            current = self.position_at(tx, root, now)
            if distance(current, points[0]) > .01:
                raise Conflict("route start does not match current abstract position")
            length = sum(distance(a, b) for a, b in zip(points, points[1:]))
            if length <= .001:
                raise Invalid("route has no travel distance")
            old = tx.execute("SELECT version FROM route WHERE entity_id=?", (entity_id,)).fetchone()
            route_version = positive(old[0] + 1 if old else 1, "route version")
            arrival = finite(now + length / speed_real * self.world._scale * 1000)
            tx.execute("INSERT INTO route VALUES(?,?,?,?,?,?,?,1,?) ON CONFLICT(entity_id) DO UPDATE SET version=excluded.version,location=excluded.location,points=excluded.points,started_ms=excluded.started_ms,arrival_ms=excluded.arrival_ms,speed_real=excluded.speed_real,active=1,seed=excluded.seed",
                       (entity_id, route_version, root["location"], canonical(points), now, arrival, speed_real, str(seed)))
            tx.execute("UPDATE entity SET version=version+1 WHERE id=?", (entity_id,))
            self.cancel_arrivals(tx, entity_id)
            self.schedule_arrival(tx, entity_id, route_version, arrival)
            event = self.store.event(tx, "entity:" + entity_id, "MovementStarted",
                                     {**payload, "route_version": route_version, "started_ms": now, "arrival_ms": arrival}, now)
            return {"id": entity_id, "version": version + 1, "route_version": route_version, "arrival_ms": arrival, "event": event}
        return self.store.command(actor, command_id, payload, apply)

    def schedule_arrival(self, tx, entity_id, version, arrival):
        event_id = hashlib.sha256(f"route-arrival:{entity_id}:{version}".encode("ascii")).hexdigest()[:32]
        self.scheduler.schedule_in(tx, event_id, arrival, "entity:" + entity_id, version,
                                   "RouteArrived", {"entity_id": entity_id}, priority=10)

    @staticmethod
    def cancel_arrivals(tx, entity_id):
        tx.execute("UPDATE scheduled_event SET state='CANCELLED',result=? WHERE aggregate_id=? AND type='RouteArrived' AND state='PENDING'",
                   (canonical({"reason": "route replaced"}), "entity:" + entity_id))

    def position_at(self, tx, entity, world_ms):
        row = tx.execute("SELECT * FROM route WHERE entity_id=? AND active=1", (entity["id"],)).fetchone()
        if not row:
            position = point(json.loads(entity["state"]).get("position"))
            group = tx.execute("SELECT e.* FROM group_member m JOIN entity e ON e.id=m.group_id WHERE m.member_id=?", (entity["id"],)).fetchone()
            if entity["alive"] and group and group["writer"] == "offline:" + group["location"]:
                origin = point(json.loads(group["state"]).get("position"))
                target = self.position_at(tx,group,world_ms)
                return [p + t - o for p,t,o in zip(position,target,origin)]
            return position
        progress = (world_ms - row["started_ms"]) / (row["arrival_ms"] - row["started_ms"])
        return route_position(json.loads(row["points"]), progress)[0]

    def position_capture(self, tx, entity):
        """Capture semantic motion dependencies, excluding restart-only fences.

        A member follows its group's route without changing its own version.
        World-scale rebasing likewise changes the route, not entity versions.
        Scheduled interactions must validate both dependencies before mutation.
        """
        route = tx.execute("SELECT version,active FROM route WHERE entity_id=?", (entity["id"],)).fetchone()
        capture = {"route":dict(route) if route else None, "group":None}
        if entity["alive"] and (not route or not route["active"]):
            group = tx.execute("SELECT e.* FROM group_member m JOIN entity e ON e.id=m.group_id WHERE m.member_id=?",
                               (entity["id"],)).fetchone()
            if group:
                self.require_offline(tx, group["id"])
                if group["kind"] != "GROUP" or not group["alive"] or group["location"] != entity["location"]:
                    raise Conflict("member motion belongs to an unavailable group")
                group_route = tx.execute("SELECT version,active FROM route WHERE entity_id=?", (group["id"],)).fetchone()
                capture["group"] = {"id":group["id"], "version":group["version"],
                                    "route":dict(group_route) if group_route else None}
        return capture

    def write_positions(self, tx, root, target):
        state = json.loads(root["state"])
        origin = point(state.get("position"))
        for member in self.members(tx, root):
            self.require_offline(tx, member["id"])
            member_state = json.loads(member["state"])
            previous = point(member_state.get("position"))
            member_state["position"] = [x + (p - o) for x, p, o in zip(target, previous, origin)]
            tx.execute("UPDATE entity SET state=?,version=version+1 WHERE id=?", (canonical(member_state), member["id"]))

    def arrived(self, tx, event):
        entity_id = json.loads(event["payload"])["entity_id"]
        route = tx.execute("SELECT * FROM route WHERE entity_id=?", (entity_id,)).fetchone()
        root = tx.execute("SELECT * FROM entity WHERE id=?", (entity_id,)).fetchone()
        if not route or not route["active"] or route["version"] != event["expected_version"] or not root or root["writer"] != "offline:" + root["location"]:
            return {"reason": "route/representation changed"}, False
        self.require_offline(tx, entity_id)
        if not root["alive"]:
            tx.execute("UPDATE route SET active=0 WHERE entity_id=?", (entity_id,))
            return {"reason": "actor died"}, False
        target = json.loads(route["points"])[-1]
        self.write_positions(tx, root, target)
        tx.execute("UPDATE route SET active=0 WHERE entity_id=?", (entity_id,))
        return {"entity_id": entity_id, "position": target, "route_version": route["version"]}, True

    def hydrate(self, actor, command_id, entity_id, location, fence, version):
        identifier(location)
        positive(fence, "location fence")
        payload = {"type": "hydrate", "entity_id": entity_id, "location": location, "fence": fence, "version": version}
        def apply(tx):
            self.world.require_location(tx, actor, location, fence)
            root = self.require_offline(tx, entity_id, version)
            if root["location"] != location:
                raise Conflict("hydration destination is another location")
            if root["alive"] and root["kind"] != "GROUP" and tx.execute("SELECT 1 FROM group_member WHERE member_id=?", (entity_id,)).fetchone():
                raise Conflict("hydrate the persistent group instead of one member")
            self.write_positions(tx, root, self.position_at(tx, root, self.world.now()))
            for member in self.members(tx, root):
                self.require_offline(tx, member["id"])
                tx.execute("UPDATE entity SET writer=?,fence=?,version=version+1 WHERE id=?", (actor, fence, member["id"]))
            tx.execute("UPDATE route SET active=0 WHERE entity_id=?", (entity_id,))
            event = self.store.event(tx, "entity:" + entity_id, "HydrationClaimed", payload, self.world.now())
            # Restoring ownership does not mean a runtime object is ready for
            # replication; engine must restore all captures/start Reduced AI.
            return {"entities": [dict(tx.execute("SELECT * FROM entity WHERE id=?", (member["id"],)).fetchone())
                                 for member in self.members(tx, root)], "event": event}
        return self.store.command(actor, command_id, payload, apply,
                                  authorize=lambda tx: self.world.require_location(tx, actor, location, fence))

    def scale_changed(self, tx, old_scale, new_scale, now):
        if old_scale == new_scale:
            return
        for route in tx.execute("SELECT * FROM route WHERE active=1 ORDER BY entity_id").fetchall():
            root = self.require_offline(tx, route["entity_id"])
            points = json.loads(route["points"])
            current, index = route_position(points, (now-route["started_ms"])/(route["arrival_ms"]-route["started_ms"]))
            remaining = [current] + points[index + 1:]
            length = sum(distance(a,b) for a,b in zip(remaining,remaining[1:]))
            if length <= .001:
                continue # Arrival resolver commits the existing event once.
            arrival = finite(now + length / route["speed_real"] * new_scale * 1000)
            version = positive(route["version"] + 1, "route version")
            tx.execute("UPDATE route SET version=?,points=?,started_ms=?,arrival_ms=? WHERE entity_id=?",
                       (version, canonical(remaining), now, arrival, route["entity_id"]))
            self.cancel_arrivals(tx, route["entity_id"])
            self.schedule_arrival(tx, route["entity_id"], version, arrival)
