#include "lzm_ownership.h"

#include <algorithm>
#include <set>

namespace lzm
{
static const std::set<std::string> ENTITY_KINDS = { "CHARACTER", "NPC", "MUTANT", "GROUP", "STASH", "CONTAINER", "CORPSE", "ANOMALY",
                                                    "ARTIFACT", "DOOR", "TRAP", "TRADER", "CAMPFIRE", "OBJECT", "NEST" };
static const std::set<std::string> ITEM_KINDS = { "WORLD", "PLAYER", "NPC", "CORPSE", "STASH", "CONTAINER", "TRADE" };
static const std::set<std::string> POLICIES = { "PUBLIC", "PLAYER_ONLY", "QUEST_PROTECTED", "NPC_ACCESSIBLE", "FACTION" };

static const json& arg(const json& args, const char* name)
{
    static const json none;
    auto it = args.find(name);
    return it == args.end() ? none : *it;
}

// Python compares a lease fence with ==: anything but that integer mismatches.
static int64_t lease_fence(const json& fence)
{
    if (!fence.is_number_integer()) throw Conflict("location lease/fence is no longer active");
    return as_int(fence);
}

static bool truthy(const json& v)
{
    if (v.is_null()) return false;
    if (v.is_boolean()) return v.get<bool>();
    if (v.is_number()) return v.get<double>() != 0;
    if (v.is_string() || v.is_array() || v.is_object()) return !v.empty();
    return true;
}

struct CaptureBudget
{
    int64_t remaining;
    explicit CaptureBudget(int64_t limit) : remaining(limit) {}
    void consume(const std::string& encoded)
    {
        remaining -= int64_t(encoded.size()) + 256;
        if (remaining < 0) throw Conflict("abstract state capture exceeds admission byte budget");
    }
};

Ownership::Ownership(World& w) : world(w), store(w.store)
{
    if (!world.scheduler_handlers.count("CorpseCleanupBatch"))
        world.scheduler_handlers["CorpseCleanupBatch"] = [this](Db& tx, const json& event) { return cleanup_batch(tx, event); };
}

json Ownership::create_entity(const std::string& actor, const std::string& command_id, const json& args)
{
    const json &entity_id = arg(args, "entity_id"), &kind_value = arg(args, "kind"), &location_value = arg(args, "location"),
               &fence_value = arg(args, "fence"), &state = arg(args, "state"), &account = arg(args, "account"),
               &policy = arg(args, "policy"), &owner = arg(args, "owner"), &capacity = arg(args, "capacity");
    std::string id = persistent_id(entity_id);
    int64_t fence = positive(fence_value, "fence");
    std::string location = identifier(location_value);
    if (!kind_value.is_string() || !ENTITY_KINDS.count(kind_value.get<std::string>()) || !state.is_object())
        throw Invalid("invalid entity kind/state");
    std::string kind = kind_value.get<std::string>();
    if (state.contains("native_save")) throw Invalid("native checkpoint reference is reserved for durable commits");
    if (kind == "CHARACTER") identifier(account);
    std::string owner_name = "public";
    if (kind == "STASH" || kind == "CONTAINER")
    {
        if (!policy.is_string() || !POLICIES.count(policy.get<std::string>()) || !capacity.is_number_integer() ||
            as_int(capacity) < 0 || as_int(capacity) > 10000)
            throw Invalid("invalid container policy/capacity");
        owner_name = truthy(owner) ? identifier(owner) : "public";
    }
    std::string encoded = canonical(state);
    json payload = { { "type", "entity_create" }, { "id", entity_id }, { "kind", kind_value }, { "location", location_value },
                     { "fence", fence_value }, { "state", state }, { "account", account }, { "policy", policy },
                     { "owner", owner }, { "capacity", capacity } };
    return store.command(actor, command_id, payload, [&](Db& tx) -> json {
        world.require_location(tx, actor, location, fence);
        if (!tx.one("SELECT 1 FROM entity WHERE id=?", { id }).is_null())
            throw Conflict("entity ID already exists; hydration cannot create a new copy");
        if (kind == "CHARACTER") admission(tx, location, account.get<std::string>());
        tx.exec("INSERT INTO entity VALUES(?,?,?,?,?,1,1,?)", { id, kind, location, actor, fence, encoded });
        if (kind == "GROUP")
        {
            json members = state.contains("member_ids") ? state["member_ids"] : json();
            if (!members.is_array() || members.empty() || members.size() > 512) throw Invalid("group requires persistent member IDs");
            std::set<std::string> seen;
            for (auto& m : members)
            {
                std::string key = m.dump();
                if (!seen.insert(key).second) throw Invalid("duplicate group members");
            }
            for (auto& member : members)
            {
                json row = require_entity(tx, actor, member, fence);
                if ((row["kind"] != "NPC" && row["kind"] != "MUTANT") || row["location"] != location)
                    throw Conflict("group member is outside this authority");
                if (!tx.one("SELECT 1 FROM group_member WHERE member_id=?", { member }).is_null())
                    throw Conflict("individual already belongs to a persistent group");
                tx.exec("INSERT INTO group_member VALUES(?,?)", { id, member });
            }
        }
        if (kind == "CHARACTER")
        {
            tx.exec("INSERT INTO character VALUES(?,?,1,?)", { id, account, encoded });
            tx.exec("INSERT INTO player_session VALUES(?,?,?,1,'ACTIVE')", { id, account, actor });
        }
        if (kind == "STASH" || kind == "CONTAINER")
            tx.exec("INSERT INTO container VALUES(?,?,?,?,1,?)", { id, policy, owner_name, capacity, encoded });
        int64_t event = store.event(tx, "entity:" + id, "EntityCreated", payload, world.now());
        return { { "id", id }, { "version", 1 }, { "event", event } };
    }, [&](Db& tx) { world.require_location(tx, actor, location, fence); });
}

void Ownership::admission(Db& tx, const std::string& location, const std::optional<std::string>& account, const std::string& excluding)
{
    json row = tx.one("SELECT capacity FROM location_lease WHERE location=?", { location });
    if (row.is_null()) throw Conflict("target location has no authority");
    int64_t target = tx.scalar("SELECT COUNT(*) FROM entity e JOIN player_session s ON s.character_id=e.id WHERE e.location=? AND e.id!=? AND e.alive=1 AND s.state='ACTIVE'",
                               { location, excluding }).get<int64_t>();
    int64_t reserved = tx.scalar("SELECT COUNT(*) FROM transfer t JOIN entity e ON e.id=t.entity_id WHERE t.target=? AND t.state IN ('PREPARED','CLAIMED') AND e.kind='CHARACTER' AND e.id!=?",
                                 { location, excluding }).get<int64_t>();
    if (target + reserved >= row["capacity"].get<int64_t>()) throw Conflict("target location is full");
    if (account)
    {
        int64_t active = tx.scalar("SELECT COUNT(*) FROM player_session WHERE state IN('ACTIVE','FROZEN')").get<int64_t>();
        if (active >= 512) throw Conflict("world player limit reached");
        if (!tx.one("SELECT 1 FROM player_session WHERE account=? AND state IN('ACTIVE','FROZEN')", { *account }).is_null())
            throw Conflict("account already owns an active character");
    }
}

json Ownership::require_entity(Db& tx, const std::string& actor, const json& entity_id, const json& fence_value, const json& version, bool alive)
{
    std::string id = persistent_id(entity_id);
    int64_t fence = positive(fence_value, "fence");
    json row = tx.one("SELECT * FROM entity WHERE id=?", { id });
    if (row.is_null() || row["writer"] != actor || row["fence"].get<int64_t>() != fence) throw Conflict("entity writer/fence mismatch");
    world.require_location(tx, actor, row["location"].get<std::string>(), fence);
    if (!version.is_null() && row["version"].get<int64_t>() != positive(version)) throw Conflict("entity version changed");
    if (alive && !row["alive"].get<int64_t>()) throw Conflict("entity is permanently dead");
    if (alive && row["kind"] == "CHARACTER")
    {
        json session = tx.one("SELECT * FROM player_session WHERE character_id=?", { id });
        if (session.is_null() || session["state"] != "ACTIVE" || session["owner"] != actor)
            throw Conflict("character session is not active under this owner");
    }
    return row;
}

void Ownership::authorize_entity(Db& tx, const std::string& actor, const json& entity_id, const json& fence_value)
{
    std::string id = persistent_id(entity_id);
    int64_t fence = positive(fence_value, "fence");
    json row = tx.one("SELECT location,writer,fence FROM entity WHERE id=?", { id });
    if (row.is_null() || row["writer"] != actor || row["fence"].get<int64_t>() != fence) throw Conflict("entity writer/fence mismatch");
    world.require_location(tx, actor, row["location"].get<std::string>(), fence);
}

std::string Ownership::checkpoint_state(Db& tx, const std::string& entity_id, const json& state)
{
    json row = tx.one("SELECT revision,sha256,byte_count FROM native_player_save WHERE character_id=? ORDER BY revision DESC LIMIT 1", { entity_id });
    if (row.is_null())
    {
        if (state.contains("native_save")) throw Invalid("native checkpoint reference has no durable save");
        return canonical(state);
    }
    json reference = { { "revision", row["revision"] }, { "sha256", row["sha256"] }, { "bytes", row["byte_count"] } };
    if (state.contains("native_save") && state["native_save"] != reference)
        throw Conflict("native checkpoint reference cannot be replaced through entity state");
    json merged = state;
    merged["native_save"] = reference;
    return canonical(merged);
}

json Ownership::update_entity(const std::string& actor, const std::string& command_id, const json& args)
{
    const json &entity_id = arg(args, "entity_id"), &fence = arg(args, "fence"), &version = arg(args, "version"), &state = arg(args, "state");
    if (!state.is_object()) throw Invalid("entity state must be an object");
    canonical(state);
    json payload = { { "type", "entity_update" }, { "id", entity_id }, { "fence", fence }, { "version", version }, { "state", state } };
    return store.command(actor, command_id, payload, [&](Db& tx) -> json {
        json row = require_entity(tx, actor, entity_id, fence, version, true);
        std::string id = entity_id.get<std::string>();
        if (row["kind"] == "GROUP")
        {
            json old = loads(row["state"].get<std::string>());
            json now_members = state.contains("member_ids") ? state["member_ids"] : json();
            json old_members = old.contains("member_ids") ? old["member_ids"] : json();
            if (now_members != old_members) throw Conflict("group membership cannot be rewritten through a state update");
        }
        std::string encoded = checkpoint_state(tx, id, state);
        tx.exec("UPDATE entity SET state=?,version=version+1 WHERE id=?", { encoded, id });
        if (row["kind"] == "CHARACTER") tx.exec("UPDATE character SET state=? WHERE id=?", { encoded, id });
        int64_t event = store.event(tx, "entity:" + id, "EntityStateChanged", payload, world.now());
        return { { "id", id }, { "version", as_int(version) + 1 }, { "event", event } };
    }, [&](Db& tx) { authorize_entity(tx, actor, entity_id, fence); });
}

json Ownership::disconnect(const std::string& actor, const std::string& command_id, const json& args)
{
    const json &character_id = arg(args, "character_id"), &fence = arg(args, "fence"), &version = arg(args, "version"), &state = arg(args, "state");
    if (!state.is_object()) throw Invalid("character checkpoint must be an object");
    canonical(state);
    json payload = { { "type", "session_disconnect" }, { "character_id", character_id }, { "fence", fence }, { "version", version }, { "state", state } };
    return store.command(actor, command_id, payload, [&](Db& tx) -> json {
        json row = require_entity(tx, actor, character_id, fence, version, true);
        std::string id = character_id.get<std::string>();
        if (row["kind"] != "CHARACTER") throw Conflict("entity has no player session");
        if (!tx.one("SELECT 1 FROM native_player_upload WHERE character_id=?", { id }).is_null())
            throw Conflict("finish or explicitly cancel the native checkpoint before disconnect");
        std::string encoded = checkpoint_state(tx, id, state);
        tx.exec("UPDATE entity SET state=?,version=version+1 WHERE id=?", { encoded, id });
        tx.exec("UPDATE character SET state=?,session_fence=session_fence+1 WHERE id=?", { encoded, id });
        tx.exec("UPDATE player_session SET state='DISCONNECTED',fence=fence+1 WHERE character_id=?", { id });
        int64_t event = store.event(tx, "entity:" + id, "SessionDisconnected", payload, world.now());
        return { { "id", id }, { "version", as_int(version) + 1 }, { "event", event } };
    }, [&](Db& tx) { authorize_entity(tx, actor, character_id, fence); });
}

json Ownership::resume(const std::string& actor, const std::string& command_id, const json& args)
{
    const json &character_id = arg(args, "character_id"), &location_value = arg(args, "location"), &fence = arg(args, "fence"),
               &version = arg(args, "version");
    std::string id = persistent_id(character_id);
    std::string location = identifier(location_value);
    positive(fence, "fence");
    int64_t v = positive(version);
    json payload = { { "type", "session_resume" }, { "character_id", character_id }, { "location", location_value },
                     { "fence", fence }, { "version", version } };
    return store.command(actor, command_id, payload, [&](Db& tx) -> json {
        json row = require_entity(tx, actor, character_id, fence, version);
        if (row["kind"] != "CHARACTER" || !row["alive"].get<int64_t>() || row["location"] != location)
            throw Conflict("character cannot resume in this location");
        json session = tx.one("SELECT * FROM player_session WHERE character_id=?", { id });
        if (session.is_null() || session["state"] != "DISCONNECTED") throw Conflict("character already has an active/frozen session");
        admission(tx, location, session["account"].get<std::string>());
        tx.exec("UPDATE player_session SET state='ACTIVE',owner=?,fence=fence+1 WHERE character_id=?", { actor, id });
        tx.exec("UPDATE character SET session_fence=session_fence+1 WHERE id=?", { id });
        tx.exec("UPDATE entity SET version=version+1 WHERE id=?", { id });
        int64_t event = store.event(tx, "entity:" + id, "SessionResumed", payload, world.now());
        json session_fence = tx.scalar("SELECT fence FROM player_session WHERE character_id=?", { id });
        return { { "id", id }, { "version", v + 1 }, { "session_fence", session_fence },
                 { "state", loads(row["state"].get<std::string>()) }, { "event", event } };
    }, [&](Db& tx) { authorize_entity(tx, actor, character_id, fence); });
}

json Ownership::recover_location(const std::string& actor, const std::string& command_id, const json& args)
{
    const json &location_value = arg(args, "location"), &fence_value = arg(args, "fence");
    json payload = { { "type", "location_recover" }, { "location", location_value }, { "fence", fence_value } };
    std::string location = as_string(location_value);
    return store.command(actor, command_id, payload, [&](Db& tx) -> json {
        int64_t fence = lease_fence(fence_value);
        world.require_location(tx, actor, location, fence);
        tx.exec("DELETE FROM native_player_upload WHERE fence<>? AND character_id IN "
                "(SELECT id FROM entity WHERE location=? AND writer NOT LIKE 'transfer:%' AND writer NOT LIKE 'offline:%')", { fence, location });
        tx.exec("UPDATE entity SET writer=?,fence=?,version=version+1 WHERE location=? AND writer NOT LIKE 'transfer:%' AND writer NOT LIKE 'offline:%'",
                { actor, fence, location });
        auto rows = tx.all("SELECT id,version,alive FROM entity WHERE location=? AND writer=? AND fence=?", { location, actor, fence });
        tx.exec("UPDATE player_session SET owner=?,fence=fence+1 WHERE state='ACTIVE' AND character_id IN (SELECT id FROM entity WHERE location=? AND writer=? AND fence=?)",
                { actor, location, actor, fence });
        tx.exec("UPDATE character SET session_fence=session_fence+1 WHERE id IN (SELECT id FROM entity WHERE location=? AND writer=? AND fence=?)",
                { location, actor, fence });
        json entities = json::array();
        for (auto& r : rows) entities.push_back(r);
        json event_payload = payload;
        event_payload["entities"] = entities;
        int64_t event = store.event(tx, "location:" + location, "LocationRecovered", event_payload, world.now());
        return { { "entities", entities }, { "event", event } };
    }, [&](Db& tx) { world.require_location(tx, actor, location, lease_fence(fence_value)); });
}

void Ownership::endpoint(Db& tx, const std::string& actor, const std::string& location, int64_t fence, const json& kind_value,
                         const json& holder, const json& requester)
{
    if (!kind_value.is_string() || !ITEM_KINDS.count(kind_value.get<std::string>())) throw Invalid("unsupported containment kind");
    std::string kind = kind_value.get<std::string>();
    if (kind == "WORLD")
    {
        if (holder != location) throw Conflict("world item belongs to another location");
        return;
    }
    json row = require_entity(tx, actor, holder, fence);
    if (row["location"] != location) throw Conflict("item endpoint belongs to another location");
    static const std::map<std::string, std::vector<std::string>> expected = {
        { "PLAYER", { "CHARACTER" } }, { "NPC", { "NPC", "MUTANT" } }, { "CORPSE", { "NPC", "MUTANT", "CHARACTER", "CORPSE" } },
        { "STASH", { "STASH" } }, { "CONTAINER", { "CONTAINER" } }, { "TRADE", { "TRADER" } } };
    const auto& kinds = expected.at(kind);
    bool alive = row["alive"].get<int64_t>() != 0;
    if (std::find(kinds.begin(), kinds.end(), row["kind"].get<std::string>()) == kinds.end() || (kind == "CORPSE" && alive))
        throw Conflict("containment kind does not match holder");
    if (kind == "CORPSE")
    {
        json state = loads(row["state"].get<std::string>());
        if (state.contains("corpse_removed") && truthy(state["corpse_removed"])) throw Conflict("corpse inventory no longer exists");
    }
    if ((kind == "PLAYER" || kind == "NPC") && !alive) throw Conflict("living inventory holder is dead");
    json box = tx.one("SELECT * FROM container WHERE id=?", { holder });
    if (!box.is_null() && !requester.is_null())
    {
        json req = require_entity(tx, actor, requester, fence, json(), true);
        if (req["location"] != location) throw Conflict("requester belongs to another location");
        std::string policy = box["policy"].get<std::string>();
        if (policy == "PLAYER_ONLY" || policy == "QUEST_PROTECTED")
        {
            if (req["kind"] != "CHARACTER" || requester != box["owner"]) throw Conflict("container is protected from this requester");
        }
        else if (policy == "FACTION")
        {
            json state = loads(req["state"].get<std::string>());
            json faction = state.contains("faction") ? state["faction"] : json();
            if (faction != box["owner"]) throw Conflict("container faction restriction");
        }
    }
}

void Ownership::check_capacity(Db& tx, const std::string& kind, const std::string& holder)
{
    json box = tx.one("SELECT capacity FROM container WHERE id=?", { holder });
    if (!box.is_null())
    {
        int64_t count = tx.scalar("SELECT COUNT(*) FROM item WHERE kind=? AND holder=?", { kind, holder }).get<int64_t>();
        if (count >= box["capacity"].get<int64_t>()) throw Conflict("container has no free slots");
    }
}

json Ownership::create_item(const std::string& actor, const std::string& command_id, const json& args)
{
    const json &item_id = arg(args, "item_id"), &section = arg(args, "section"), &location_value = arg(args, "location"),
               &fence_value = arg(args, "fence"), &kind = arg(args, "kind"), &holder_value = arg(args, "holder"),
               &quantity = arg(args, "quantity");
    json state = arg(args, "state");
    std::string id = persistent_id(item_id);
    identifier(section);
    std::string location = identifier(location_value);
    int64_t fence = positive(fence_value, "fence");
    if (!quantity.is_number_integer() || as_int(quantity) < 1 || as_int(quantity) > 1000000) throw Invalid("invalid item quantity");
    if (state.is_null()) state = json::object();
    if (!state.is_object()) throw Invalid("item state must be an object");
    json holder = truthy(holder_value) ? holder_value : location_value;
    std::string encoded = canonical(state);
    json payload = { { "type", "item_create" }, { "id", item_id }, { "section", section }, { "location", location_value },
                     { "fence", fence_value }, { "kind", kind }, { "holder", holder }, { "quantity", quantity }, { "state", state } };
    return store.command(actor, command_id, payload, [&](Db& tx) -> json {
        world.require_location(tx, actor, location, fence);
        endpoint(tx, actor, location, fence, kind, holder);
        if (!tx.one("SELECT 1 FROM item WHERE id=?", { id }).is_null()) throw Conflict("item already exists");
        check_capacity(tx, as_string(kind), as_string(holder));
        tx.exec("INSERT INTO item VALUES(?,?,?,?,?,1,?)", { id, section, kind, holder, quantity, encoded });
        int64_t event = store.event(tx, "item:" + id, "ItemCreated", payload, world.now());
        return { { "id", id }, { "version", 1 }, { "event", event } };
    }, [&](Db& tx) { world.require_location(tx, actor, location, fence); });
}

json Ownership::move_item(const std::string& actor, const std::string& command_id, const json& args)
{
    const json &item_id = arg(args, "item_id"), &location_value = arg(args, "location"), &fence_value = arg(args, "fence"),
               &version = arg(args, "version"), &source_kind = arg(args, "source_kind"), &source_holder = arg(args, "source_holder"),
               &target_kind = arg(args, "target_kind"), &target_holder = arg(args, "target_holder"), &requester = arg(args, "requester");
    std::string id = persistent_id(item_id);
    int64_t v = positive(version);
    persistent_id(requester);
    json payload = { { "type", "item_move" }, { "id", item_id }, { "location", location_value }, { "fence", fence_value },
                     { "version", version }, { "source_kind", source_kind }, { "source_holder", source_holder },
                     { "target_kind", target_kind }, { "target_holder", target_holder }, { "requester", requester } };
    std::string location = as_string(location_value);
    return store.command(actor, command_id, payload, [&](Db& tx) -> json {
        int64_t fence = lease_fence(fence_value);
        world.require_location(tx, actor, location, fence);
        json req = require_entity(tx, actor, requester, fence_value, json(), true);
        if (req["location"] != location) throw Conflict("requester belongs to another location");
        for (auto* pair : { &source_kind, &target_kind })
        {
            const json& kind = *pair;
            const json& holder = pair == &source_kind ? source_holder : target_holder;
            endpoint(tx, actor, location, fence, kind, holder, requester);
            if ((kind == "PLAYER" || kind == "NPC") && holder != requester) throw Conflict("requester cannot mutate another living inventory");
        }
        json row = tx.one("SELECT * FROM item WHERE id=?", { id });
        if (row.is_null() || row["kind"] != source_kind || row["holder"] != source_holder || row["version"].get<int64_t>() != v)
            throw Conflict("item ownership/version changed");
        if (source_kind == target_kind && source_holder == target_holder) throw Invalid("source and destination are identical");
        check_capacity(tx, as_string(target_kind), as_string(target_holder));
        tx.exec("UPDATE item SET kind=?,holder=?,version=version+1 WHERE id=?", { target_kind, target_holder, id });
        tx.exec("UPDATE container SET version=version+1 WHERE id IN (?,?)", { source_holder, target_holder });
        int64_t event = store.event(tx, "item:" + id, "ItemMoved", payload, world.now());
        return { { "id", id }, { "version", v + 1 }, { "event", event } };
    }, [&](Db& tx) {
        world.require_location(tx, actor, location, lease_fence(fence_value));
        authorize_entity(tx, actor, requester, fence_value);
    });
}

json Ownership::kill(const std::string& actor, const std::string& command_id, const json& args)
{
    const json &entity_id = arg(args, "entity_id"), &fence = arg(args, "fence"), &version = arg(args, "version"), &cause = arg(args, "cause");
    identifier(cause);
    json payload = { { "type", "entity_death" }, { "id", entity_id }, { "fence", fence }, { "version", version }, { "cause", cause } };
    return store.command(actor, command_id, payload, [&](Db& tx) -> json {
        json row = require_entity(tx, actor, entity_id, fence, version, true);
        return die_in(tx, row, cause.get<std::string>(), world.now(), payload);
    }, [&](Db& tx) { authorize_entity(tx, actor, entity_id, fence); });
}

json Ownership::die_in(Db& tx, const json& row, const std::string& cause, double occurred_ms, const json& evidence)
{
    if (!row["alive"].get<int64_t>()) throw Conflict("death has already been committed");
    identifier(cause);
    std::string id = row["id"].get<std::string>();
    json state = loads(row["state"].get<std::string>());
    state["health"] = 0;
    state["death_time"] = occurred_ms;
    state["cause"] = cause;
    state["corpse_removed"] = false;
    tx.exec("UPDATE entity SET alive=0,state=?,version=version+1 WHERE id=?", { canonical(state), id });
    tx.exec("UPDATE item SET kind='CORPSE',version=version+1 WHERE holder=? AND kind IN ('PLAYER','NPC')", { id });
    tx.exec("UPDATE player_session SET state='DISCONNECTED',fence=fence+1 WHERE character_id=?", { id });
    tx.exec("UPDATE character SET session_fence=session_fence+1 WHERE id=?", { id });
    tx.exec("UPDATE route SET active=0 WHERE entity_id=?", { id });
    tx.exec("UPDATE scheduled_event SET state='CANCELLED',result=? WHERE aggregate_id=? AND type='RouteArrived' AND state='PENDING'",
            { canonical({ { "reason", "actor died" } }), "entity:" + id });
    int64_t event = store.event(tx, "entity:" + id, "EntityDied", evidence, occurred_ms, "world", world.now());
    // Quest death consequences: the engine master refuses to open a world
    // with quest requirements (Service::check_supported), none can be pending.
    json group = tx.one("SELECT e.* FROM group_member m JOIN entity e ON e.id=m.group_id WHERE m.member_id=?", { id });
    if (!group.is_null() && group["alive"].get<int64_t>() &&
        tx.one("SELECT 1 FROM group_member m JOIN entity e ON e.id=m.member_id WHERE m.group_id=? AND e.alive=1", { group["id"] }).is_null())
    {
        if (group["writer"] != row["writer"] || group["fence"] != row["fence"])
            throw Conflict("dead group's derived state belongs to another writer");
        json gstate = loads(group["state"].get<std::string>());
        gstate["death_time"] = occurred_ms;
        gstate["cause"] = "all_members_dead";
        gstate["corpse_removed"] = true;
        std::string gid = group["id"].get<std::string>();
        tx.exec("UPDATE entity SET alive=0,state=?,version=version+1 WHERE id=?", { canonical(gstate), gid });
        tx.exec("UPDATE route SET active=0 WHERE entity_id=?", { gid });
        tx.exec("UPDATE scheduled_event SET state='CANCELLED',result=? WHERE aggregate_id=? AND type='RouteArrived' AND state='PENDING'",
                { canonical({ { "reason", "group died" } }), "entity:" + gid });
        store.event(tx, "entity:" + gid, "GroupLostAllMembers", { { "group_id", gid }, { "last_member", id } }, occurred_ms, "world", world.now());
    }
    return { { "id", id }, { "version", row["version"].get<int64_t>() + 1 }, { "event", event } };
}

bool Ownership::quest_required(Db& tx, const std::string& entity_id)
{
    return !tx.one("SELECT 1 FROM quest_requirement r JOIN quest q ON q.character_id=r.character_id AND q.id=r.quest_id "
                   "WHERE r.entity_id=? AND COALESCE(json_extract(q.state,'$.status'),'ACTIVE') NOT IN ('FAILED','COMPLETED') LIMIT 1",
                   { entity_id }).is_null();
}

json Ownership::cleanup_corpse(const std::string& actor, const std::string& command_id, const json& args)
{
    const json &entity_id = arg(args, "entity_id"), &fence = arg(args, "fence"), &version = arg(args, "version");
    json payload = { { "type", "corpse_cleanup" }, { "id", entity_id }, { "fence", fence }, { "version", version } };
    return store.command(actor, command_id, payload, [&](Db& tx) -> json {
        json row = require_entity(tx, actor, entity_id, fence, version);
        return cleanup_in(tx, row, payload, world.now());
    }, [&](Db& tx) { authorize_entity(tx, actor, entity_id, fence); });
}

json Ownership::cleanup_in(Db& tx, const json& row, const json& payload, double at)
{
    if (row["alive"].get<int64_t>()) throw Conflict("living entity cannot be cleaned up");
    std::string id = row["id"].get<std::string>();
    if (quest_required(tx, id)) throw Conflict("corpse is still required by an active quest");
    CaptureBudget budget(4 * 1024 * 1024);
    budget.consume(row["state"].get<std::string>());
    json state = loads(row["state"].get<std::string>());
    bool removed = state.contains("corpse_removed") && truthy(state["corpse_removed"]);
    if (removed && tx.one("SELECT 1 FROM item WHERE kind='CORPSE' AND holder=? LIMIT 1", { id }).is_null())
        return { { "id", id }, { "version", row["version"] }, { "items", json::array() }, { "event", nullptr }, { "complete", true }, { "next_event", nullptr } };
    std::vector<json> admitted;
    for (auto& item : tx.all("SELECT * FROM item WHERE kind='CORPSE' AND holder=? ORDER BY id LIMIT 64", { id }))
    {
        try
        {
            budget.consume(item["state"].get<std::string>());
        }
        catch (const Conflict&)
        {
            if (admitted.empty()) throw;
            break;
        }
        admitted.push_back(item);
    }
    for (auto& item : admitted) tx.exec("UPDATE item SET kind='DESTROYED',version=version+1 WHERE id=?", { item["id"] });
    bool complete = tx.one("SELECT 1 FROM item WHERE kind='CORPSE' AND holder=? LIMIT 1", { id }).is_null();
    state["corpse_removed"] = complete;
    if (complete) state.erase("corpse_cleanup_pending");
    else state["corpse_cleanup_pending"] = true;
    int64_t version = positive(row["version"].get<int64_t>() + 1);
    tx.exec("UPDATE entity SET state=?,version=? WHERE id=?", { canonical(state), version, id });
    json following;
    if (!complete)
    {
        std::string next = sha256_hex("corpse-cleanup:" + id + ":" + row["writer"].get<std::string>() + ":" +
                                      std::to_string(row["fence"].get<int64_t>()) + ":" + std::to_string(version)).substr(0, 32);
        following = next;
        Scheduler::schedule_in(tx, next, at, "entity:" + id, version, "CorpseCleanupBatch",
                                               { { "actor", row["writer"] }, { "entity_id", id }, { "fence", row["fence"] } }, 30);
    }
    json ids = json::array();
    for (auto& item : admitted) ids.push_back(item["id"]);
    json event_payload = payload;
    event_payload["items"] = ids;
    event_payload["complete"] = complete;
    event_payload["next_event"] = following;
    int64_t event = store.event(tx, "entity:" + id, complete ? "CorpseRemoved" : "CorpseCleanupProgress", event_payload, at, "world", world.now());
    return { { "id", id }, { "version", version }, { "items", ids }, { "event", event }, { "complete", complete }, { "next_event", following } };
}

std::pair<json, bool> Ownership::cleanup_batch(Db& tx, const json& event)
{
    json capture = loads(event["payload"].get<std::string>());
    json row;
    try
    {
        row = require_entity(tx, capture["actor"].get<std::string>(), capture["entity_id"], capture["fence"], event["expected_version"]);
    }
    catch (const Conflict&)
    {
        return { { { "reason", "corpse cleanup writer/capture changed" } }, false };
    }
    if (row["alive"].get<int64_t>() || quest_required(tx, row["id"].get<std::string>()))
        return { { { "reason", "corpse cleanup protection changed" } }, false };
    return { cleanup_in(tx, row, { { "type", "corpse_cleanup_batch" }, { "source_event", event["id"] } }, event["due_world_ms"].get<double>()), true };
}

json Ownership::location_state(const std::string& actor, const std::string& location, int64_t fence)
{
    std::lock_guard<std::recursive_mutex> guard(store.lock);
    store.require_epoch(store.db);
    world.require_location(store.db, actor, location, fence);
    auto entities = store.db.all("SELECT * FROM entity WHERE location=? AND writer=? AND fence=? ORDER BY id", { location, actor, fence });
    auto items = store.db.all("SELECT * FROM item WHERE kind!='DESTROYED' AND ((kind='WORLD' AND holder=?) OR holder IN (SELECT id FROM entity WHERE location=? AND writer=? AND fence=?)) ORDER BY id",
                              { location, location, actor, fence });
    json e = json::array(), i = json::array();
    for (auto& row : entities) { row["state"] = loads(row["state"].get<std::string>()); e.push_back(row); }
    for (auto& row : items) { row["state"] = loads(row["state"].get<std::string>()); i.push_back(row); }
    return { { "entities", e }, { "items", i } };
}
} // namespace lzm
