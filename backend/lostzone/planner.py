"""One atomic earliest-contact admission across combat and physical hazards."""
import hashlib
import json
import time

from .plans import reservations
from .store import Conflict, Invalid, Unavailable, canonical, finite, identifier


class Planner:
    def __init__(self, world, encounters, hazards):
        if encounters.world is not world or hazards.world is not world or encounters.offline is not hazards.offline:
            raise Conflict("contact planners must share one world and offline representation")
        self.world,self.store = world,world.store
        self.encounters,self.hazards = encounters,hazards
        self.policy = None
        encounters.offline.scheduler.handlers.setdefault("OfflineContactsWindow",self.window_in)
        encounters.offline.scheduler.handlers.setdefault("OfflineContactsRefresh",self.refresh_in)

    def enable_automatic(self, policy):
        """Install trusted backend contact discovery on semantic mutations.

        Explicit opt-in: native runtime authority is not adopted by this flag.
        No timer/per-actor scan, resolver recursion or immediate coarse-combat
        repetition is introduced. Resolvers still stop routes for AI decisions.
        """
        if not isinstance(policy,dict) or set(policy) != {"horizon_ms","radius","max_locations","budget_ms"}:
            raise Invalid("automatic planning requires a complete trusted work policy")
        finite(policy["horizon_ms"],1,86_400_000);finite(policy["radius"],.1,200)
        finite(policy["budget_ms"],1,1000)
        if type(policy["max_locations"]) is not int or not 1<=policy["max_locations"]<=25:
            raise Invalid("invalid automatic planning location budget")
        existing = self.world.mutation_observers.get("offline_contacts")
        if existing is not None:
            raise Conflict("automatic contacts already have a world authority")
        self.policy = dict(policy)
        self.world.mutation_observers["offline_contacts"] = self.changed_in
        self.encounters.offline.scheduler.handlers["OfflineContactsWindow"] = self.window_in
        self.encounters.offline.scheduler.handlers["OfflineContactsRefresh"] = self.refresh_in
        self.world.scheduler_event_observers["offline_contacts"] = self.outcome_in

    def changed_in(self, tx, actor, command_id, change):
        kind = change["type"]
        if kind not in ("route_start","dehydrate","hydrate","scale") and not (kind=="world_state" and change["name"]=="relations"):
            return
        if kind in ("route_start","dehydrate","hydrate"):
            if "location" in change:
                locations = [change["location"]]
            else:
                row = tx.execute("SELECT location FROM entity WHERE id=?",(change["entity_id"],)).fetchone()
                if not row:
                    raise Conflict("changed actor lost its persistent location")
                locations = [row[0]]
        else:
            locations = [row[0] for row in tx.execute("SELECT DISTINCT location FROM entity WHERE writer='offline:'||location ORDER BY location LIMIT ?",
                                                     (self.policy["max_locations"]+1,))]
        if len(locations)>self.policy["max_locations"]:
            raise Unavailable("automatic planning location budget exhausted")
        start = time.monotonic()
        for location in locations:
            # Domain-separated source command identity survives retry/restart;
            # captures already reserved at equal time retain their original RNG.
            digest = hashlib.sha256(canonical({"world":self.world.world_id,"seed":self.world.seed,
                                               "actor":actor,"command":command_id,"location":location,
                                               "purpose":"mutation-contact"}).encode("utf-8")).hexdigest()
            payload = {"type":"offline_plan","location":location,"horizon_ms":self.policy["horizon_ms"],
                       "radius":self.policy["radius"],"seed":int(digest[:16],16)}
            self.cancel_windows_in(tx,location)
            result = self.plan_in(tx,"world:contacts",digest[:32],payload)
            self.store.event(tx,"location:"+location,"ContactsReplanned",
                             {"source_actor":actor,"source_command":command_id,"change":kind,**result},self.world.now())
            self.schedule_window_in(tx,location,self.world.now(),digest,0)
            if (time.monotonic()-start)*1000>self.policy["budget_ms"]:
                raise Unavailable("automatic planning time budget exhausted")

    def cancel_windows_in(self, tx, location, physical_ms=None):
        rows = tx.execute("SELECT id,aggregate_id FROM scheduled_event WHERE state='PENDING' AND type='OfflineContactsWindow' AND json_extract(payload,'$.location')=? LIMIT 26",(location,)).fetchall()
        if len(rows)>25:
            raise Unavailable("automatic planning continuation backlog exhausted")
        for row in rows:
            result = {"reason":"semantic mutation replans this location"}
            tx.execute("UPDATE scheduled_event SET state='CANCELLED',result=? WHERE id=?",(canonical(result),row["id"]))
            at=self.world.now() if physical_ms is None else physical_ms
            self.store.event(tx,row["aggregate_id"],"ScheduledEventCancelled",{"event_id":row["id"],"result":result},at,committed_ms=self.world.now())

    def outcome_in(self, tx, event, result):
        if event["type"] not in ("RouteArrived","OfflineCombat","OfflineHazard","StashVisited"):
            return
        capture=json.loads(event["payload"])
        location=capture.get("location")
        if location is None:
            row=tx.execute("SELECT location FROM entity WHERE id=?",(capture["entity_id"],)).fetchone()
            if not row:
                raise Conflict("arrived actor lost its persistent location")
            location=row[0]
        pending=tx.execute("SELECT id,payload FROM scheduled_event WHERE state='PENDING' AND type='OfflineContactsRefresh' "
                           "AND due_world_ms=? AND json_extract(payload,'$.location')=? ORDER BY id LIMIT 1",
                           (event["due_world_ms"],location)).fetchone()
        if pending:
            captured=json.loads(pending["payload"])
            if any(self.policy[key]!=captured["policy"][key] for key in ("horizon_ms","radius")):
                raise Unavailable("pending outcome refresh uses a different semantic policy")
            event_id=pending["id"]
        else:
            event_id=hashlib.sha256(f"contacts-outcome:{self.world.world_id}:{event['id']}".encode("utf-8")).hexdigest()[:32]
            payload={"location":location,"source_event":event["id"],"policy":self.policy}
            self.encounters.offline.scheduler.schedule_in(tx,event_id,event["due_world_ms"],"location:"+location,1,
                                                         "OfflineContactsRefresh",payload,priority=5)
        self.store.event(tx,"location:"+location,"ContactsRefreshQueued",
                         {"source_event":event["id"],"refresh_event":event_id,"coalesced":pending is not None},
                         event["due_world_ms"],committed_ms=self.world.now())

    def refresh_in(self, tx, event):
        capture=json.loads(event["payload"])
        if self.policy is None or any(self.policy[key]!=capture["policy"][key] for key in ("horizon_ms","radius")):
            raise Unavailable("restore the captured automatic planning policy before refresh")
        location,at=capture["location"],event["due_world_ms"]
        started=time.monotonic()
        self.cancel_windows_in(tx,location,at)
        if not any(row["arrival_ms"]>at for row in self.active_routes_in(tx,location)):
            return {"location":location,"source_event":capture["source_event"],"reason":"no continuing physical routes"},False
        digest=hashlib.sha256(f"contacts-refresh:{event['id']}:{self.world.seed}".encode("utf-8")).hexdigest()
        payload={"type":"offline_plan","location":location,"horizon_ms":self.policy["horizon_ms"],
                 "radius":self.policy["radius"],"seed":int(digest[:16],16)}
        result=self.plan_in(tx,"world:contacts",digest[:32],payload,planning_now=at,moving_only=True)
        following=self.schedule_window_in(tx,location,at,digest,0)
        if (time.monotonic()-started)*1000>self.policy["budget_ms"]:
            raise Unavailable("automatic outcome refresh work budget exhausted")
        return {"location":location,"source_event":capture["source_event"],"refresh_ms":at,
                "next_event":following,**result},True

    def active_routes_in(self, tx, location):
        return tx.execute("SELECT r.entity_id,r.arrival_ms FROM route r JOIN entity e ON e.id=r.entity_id "
                          "WHERE r.active=1 AND e.alive=1 AND e.location=? AND e.writer='offline:'||e.location AND e.fence=?",
                          (location,self.store.epoch))

    def schedule_window_in(self, tx, location, started, source, generation):
        # One location continuation, only while an actual route extends beyond
        # this planning window. Arrival/contact handlers keep their priority.
        end = finite(started+self.policy["horizon_ms"])
        if not any(row["arrival_ms"]>end for row in self.active_routes_in(tx,location)):
            return None
        event_id = hashlib.sha256(f"contacts-window:{source}:{generation}:{location}".encode("utf-8")).hexdigest()[:32]
        payload = {"location":location,"source":source,"generation":generation,"policy":self.policy}
        self.encounters.offline.scheduler.schedule_in(tx,event_id,end,"location:"+location,1,"OfflineContactsWindow",payload,priority=20)
        return event_id

    def window_in(self, tx, event):
        capture=json.loads(event["payload"])
        if self.policy is None or any(self.policy[key]!=capture["policy"][key] for key in ("horizon_ms","radius")):
            raise Unavailable("restore the captured automatic planning policy before catch-up")
        location,at=capture["location"],event["due_world_ms"]
        if not any(row["arrival_ms"]>at for row in self.active_routes_in(tx,location)):
            return {"reason":"no continuing physical routes"},False
        started=time.monotonic()
        digest=hashlib.sha256(f"contacts-pass:{event['id']}:{self.world.seed}".encode("utf-8")).hexdigest()
        payload={"type":"offline_plan","location":location,"horizon_ms":self.policy["horizon_ms"],
                 "radius":self.policy["radius"],"seed":int(digest[:16],16)}
        # The due instant, not current wall processing time: delayed catch-up
        # must still discover an encounter crossed during an earlier window.
        result=self.plan_in(tx,"world:contacts",digest[:32],payload,planning_now=at,moving_only=True)
        following=self.schedule_window_in(tx,location,at,capture["source"],capture["generation"]+1)
        if (time.monotonic()-started)*1000>self.policy["budget_ms"]:
            raise Unavailable("automatic continuation work budget exhausted")
        return {"location":location,"window_ms":at,"next_event":following,**result},True

    @staticmethod
    def resources(option):
        if option["type"]=="offline_combat":
            return {option["first_id"],option["second_id"]},set()
        return {option["entity_id"]},{option["hazard_id"]}

    @staticmethod
    def order(option):
        # Preserve previously captured RNG at an equal physical contact time.
        # Exact fresh ties use combat first, then persistent IDs, never hash/set
        # iteration order or an observer's arrival.
        roots,hazards = Planner.resources(option)
        return option["due_ms"],0 if option.get("existing") else 1,option["type"],sorted(roots),sorted(hazards)

    def plan(self, actor, command_id, location, horizon_ms, seed, radius=50):
        identifier(location);finite(horizon_ms,1,86_400_000);finite(radius,.1,200)
        if type(seed) is not int or not 0<=seed<2**64:
            raise Invalid("invalid deterministic planning seed")
        payload = {"type":"offline_plan","location":location,"horizon_ms":horizon_ms,"seed":seed,"radius":radius}
        return self.store.command(actor,command_id,payload,lambda tx:self.plan_in(tx,actor,command_id,payload))

    def plan_in(self, tx, actor, command_id, payload, planning_now=None, moving_only=False):
        pending = []
        _,_,cancelled = reservations(self.world,tx,payload["location"],self.world.plan_validators,pending)
        now = self.world.now() if planning_now is None else finite(planning_now)
        # Existing valid captures are options, not unconditional reservations:
        # a newly placed earlier trap may preempt a later firefight. Discover
        # both types before scheduling anything, at the same planning instant.
        unrestricted = (set(),set(),0)
        combat = self.encounters.location_in(tx,actor,command_id,payload,now,True,unrestricted)
        hazard = self.hazards.location_in(tx,actor,command_id,payload,now,True,unrestricted)
        options = combat["options"]+hazard["options"]
        if moving_only:
            active = {row["entity_id"] for row in self.active_routes_in(tx,payload["location"])}
            options = [option for option in options if self.resources(option)[0]&active]
        for event,plan in pending:
            keys = ("first_id","second_id") if event["type"]=="OfflineCombat" else ("entity_id","hazard_id")
            options.append({"type":"offline_combat" if event["type"]=="OfflineCombat" else "offline_hazard",
                            "due_ms":event["due_world_ms"],"existing":event["id"],**{key:plan[key] for key in keys}})
        chosen,roots,hazards,deferred = [],set(),set(),0
        for option in sorted(options,key=self.order):
            actors,volumes = self.resources(option)
            if roots & actors or hazards & volumes:
                deferred += 1
                continue
            if len(chosen)>=64:
                raise Unavailable("combined contact admission budget exhausted")
            chosen.append(option);roots.update(actors);hazards.update(volumes)
        kept = {option["existing"] for option in chosen if option.get("existing")}
        preempted = 0
        for event,_ in pending:
            if event["id"] in kept:
                continue
            result = {"reason":"earlier contact preempts this reservation","cancelled_world_ms":now}
            tx.execute("UPDATE scheduled_event SET state='CANCELLED',result=? WHERE id=?",(canonical(result),event["id"]))
            self.store.event(tx,event["aggregate_id"],"ScheduledEventCancelled",{"event_id":event["id"],"result":result},now)
            preempted += 1
        contacts = []
        for option in chosen:
            if option.get("existing"):
                contacts.append({"event_id":option["existing"],"type":option["type"],"due_ms":option["due_ms"],"retained":True})
                continue
            actors,volumes = self.resources(option)
            identity = ":".join(sorted(actors))+":"+":".join(sorted(volumes))
            event_id = hashlib.sha256(f"plan:{self.world.world_id}:{actor}:{command_id}:{option['type']}:{identity}".encode("utf-8")).hexdigest()[:32]
            request = {**option,"event_id":event_id}
            if option["type"]=="offline_combat":
                result = self.encounters.schedule_in(tx,request,planning_now=now)
            else:
                result = self.hazards.schedule_in(tx,request,planning_now=now)
                if result["event_id"] is None or abs(result["due_ms"]-option["due_ms"])>1e-6:
                    raise Conflict("combined hazard discovery and capture disagree")
            contacts.append({**result,"due_ms":option["due_ms"],"type":option["type"],"retained":False})
        return {"contacts":contacts,"cancelled_plans":cancelled,"preempted_plans":preempted,
                "deferred_contacts":deferred,"combat_candidates":combat["candidate_pairs"],"hazard_candidates":hazard["candidates"]}
