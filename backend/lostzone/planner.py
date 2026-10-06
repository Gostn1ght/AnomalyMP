"""One atomic earliest-contact admission across combat and physical hazards."""
import hashlib
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
            result = self.plan_in(tx,"world:contacts",digest[:32],payload)
            self.store.event(tx,"location:"+location,"ContactsReplanned",
                             {"source_actor":actor,"source_command":command_id,"change":kind,**result},self.world.now())
            if (time.monotonic()-start)*1000>self.policy["budget_ms"]:
                raise Unavailable("automatic planning time budget exhausted")

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

    def plan_in(self, tx, actor, command_id, payload):
        pending = []
        _,_,cancelled = reservations(self.world,tx,payload["location"],self.world.plan_validators,pending)
        now = self.world.now()
        # Existing valid captures are options, not unconditional reservations:
        # a newly placed earlier trap may preempt a later firefight. Discover
        # both types before scheduling anything, at the same planning instant.
        unrestricted = (set(),set(),0)
        combat = self.encounters.location_in(tx,actor,command_id,payload,now,True,unrestricted)
        hazard = self.hazards.location_in(tx,actor,command_id,payload,now,True,unrestricted)
        options = combat["options"]+hazard["options"]
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
