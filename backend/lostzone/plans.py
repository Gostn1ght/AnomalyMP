"""Bounded shared reservations for competing abstract route interactions."""
import json

from .capture import CaptureBudget
from .store import Unavailable, canonical


def reservations(world, tx, location, validators, details=None):
    # Stream payloads; a row limit alone could fetch hundreds of MiB before
    # checking the aggregate byte admission. Absent validators hold their jobs.
    rows = tx.execute("SELECT * FROM scheduled_event WHERE state='PENDING' AND type IN ('OfflineCombat','OfflineHazard') "
                      "AND json_extract(payload,'$.location')=? ORDER BY id LIMIT 513",(location,))
    roots,hazards,cancelled = set(),set(),0
    budget = CaptureBudget(8*1024*1024)
    for number,event in enumerate(rows):
        if number==512:
            raise Unavailable("offline contact backlog exhausted")
        budget.consume(event["payload"])
        plan = json.loads(event["payload"])
        validate = validators.get(event["type"])
        if validate and not validate(tx,plan):
            result = {"reason":"planning capture changed","cancelled_world_ms":world.now()}
            tx.execute("UPDATE scheduled_event SET state='CANCELLED',result=? WHERE id=?",(canonical(result),event["id"]))
            world.store.event(tx,event["aggregate_id"],"ScheduledEventCancelled",
                              {"event_id":event["id"],"result":result},result["cancelled_world_ms"])
            cancelled += 1
            continue
        if event["type"]=="OfflineCombat":
            roots.update((plan["first_id"],plan["second_id"]))
        else:
            roots.add(plan["entity_id"])
            hazards.add(plan["hazard_id"])
        if details is not None:
            details.append((event,plan))
    return roots,hazards,cancelled
