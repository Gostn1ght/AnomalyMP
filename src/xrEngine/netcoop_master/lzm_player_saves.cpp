#include "lzm_ownership.h"

namespace lzm
{
static const int64_t CHUNK = 30720;  // divisible by three; bounded JSON/base64 GET response
static const int64_t UPLOAD_BUDGET = 64 * 1024 * 1024;
static const int64_t UPLOAD_IDLE_MS = 120000;

static const json& arg(const json& args, const char* name)
{
    static const json none;
    auto it = args.find(name);
    return it == args.end() ? none : *it;
}

static bool sha_ok(const json& v)
{
    if (!v.is_string() || v.get<std::string>().size() != 64) return false;
    for (char c : v.get<std::string>())
        if (!((c >= '0' && c <= '9') || (c >= 'a' && c <= 'f'))) return false;
    return true;
}

PlayerSaves::PlayerSaves(World& world, Ownership& ownership) : world_(world), store_(world.store), ownership_(ownership) {}

json PlayerSaves::authorize(Db& tx, const std::string& actor, const json& character_id, const json& fence, const json& session_fence)
{
    json row = ownership_.require_entity(tx, actor, character_id, fence, json(), true);
    if (row["kind"] != "CHARACTER") throw Conflict("native save requires a character");
    json session = tx.one("SELECT fence FROM player_session WHERE character_id=?", { character_id });
    if (session["fence"].get<int64_t>() != positive(session_fence, "session fence")) throw Conflict("native save session fence changed");
    return row;
}

int64_t PlayerSaves::revision(Db& tx, const std::string& character_id)
{
    return tx.scalar("SELECT COALESCE(MAX(revision),0) FROM native_player_save WHERE character_id=?", { character_id }).get<int64_t>();
}

json PlayerSaves::inspect(const std::string& actor, const std::string& account_value, int64_t slot, const std::string& location,
                          int64_t fence, int64_t epoch)
{
    std::string character_id = native_identity(world_.world_id, world_.seed, account_value, slot);
    std::string account = lower(account_value);
    identifier(actor);
    identifier(location);
    positive(fence, "location fence");
    positive(epoch, "master epoch");
    std::lock_guard<std::recursive_mutex> guard(store_.lock);
    Db& tx = store_.db;
    store_.require_epoch(tx);
    if (epoch != *store_.epoch) throw Conflict("native slot master epoch changed");
    world_.require_location(tx, actor, location, fence);
    if (!tx.one("SELECT 1 FROM player_session WHERE lower(account)=? AND character_id<>? AND state IN ('ACTIVE','FROZEN') LIMIT 1",
                { account, character_id }).is_null())
        throw Conflict("account already owns another active character");
    json result = { { "schema", 1 }, { "world_id", std::to_string(world_.world_id) }, { "seed", std::to_string(world_.seed) },
                    { "epoch", epoch }, { "location", location }, { "fence", fence }, { "account", account }, { "slot", slot },
                    { "character_id", character_id }, { "entity_version", 0 }, { "session_fence", 0 }, { "checkpoint", nullptr } };
    json entity = tx.one("SELECT kind,location,writer,fence,version,alive,substr(state,1,1048577) AS state FROM entity WHERE id=?", { character_id });
    auto staged_rows = tx.all("SELECT id,account,slot,location,world_id,seed FROM native_player_import WHERE id=? OR (account=? AND slot=?) LIMIT 2",
                              { character_id, account, slot });
    if (staged_rows.size() > 1) throw Unavailable("staged native slot identity is ambiguous");
    json staged = staged_rows.empty() ? json() : staged_rows[0];
    if (!staged.is_null() && (staged["id"] != character_id || staged["account"] != account || staged["slot"] != slot ||
                              staged["world_id"] != result["world_id"] || staged["seed"] != result["seed"]))
        throw Unavailable("staged native slot identity is inconsistent");
    if (entity.is_null())
    {
        if (!staged.is_null() && staged["location"] != location) throw Conflict("staged native slot belongs to another location");
        result["status"] = staged.is_null() ? "ABSENT" : "STAGED";
        return result;
    }
    std::string writer = entity["writer"].get<std::string>();
    if (entity["kind"] == "CHARACTER" && entity["alive"] == 1 && entity["location"] != location &&
        writer.rfind("transfer:", 0) != 0 && writer.rfind("offline:", 0) != 0)
    {
        // The character lives on another map (owner 2026-10-17): its name only.
        json home = tx.one("SELECT account,state FROM player_session WHERE character_id=?", { character_id });
        if (!home.is_null() && lower(home["account"].get<std::string>()) == account && (home["state"] == "ACTIVE" || home["state"] == "DISCONNECTED"))
        {
            result["status"] = "ELSEWHERE";
            result["home"] = entity["location"];
            return result;
        }
    }
    if (entity["kind"] != "CHARACTER" || entity["location"] != location || entity["writer"] != actor ||
        entity["fence"].get<int64_t>() != fence || entity["alive"] != 1)
        throw Conflict("native slot is dead, in transit or outside this authority");
    json character = tx.one("SELECT account FROM character WHERE id=?", { character_id });
    json session = tx.one("SELECT account,owner,fence,state FROM player_session WHERE character_id=?", { character_id });
    if (character.is_null() || session.is_null() || lower(character["account"].get<std::string>()) != account ||
        lower(session["account"].get<std::string>()) != account)
        throw Unavailable("native slot registry identity is inconsistent");
    if ((session["state"] != "ACTIVE" && session["state"] != "DISCONNECTED") || (session["state"] == "ACTIVE" && session["owner"] != actor))
        throw Conflict("native slot session is frozen or owned elsewhere");
    if (!tx.one("SELECT 1 FROM native_player_upload WHERE character_id=?", { character_id }).is_null())
        throw Conflict("native slot has an unresolved checkpoint upload");
    json head = tx.one("SELECT revision,sha256,byte_count FROM native_player_save WHERE character_id=? ORDER BY revision DESC LIMIT 1", { character_id });
    if (!head.is_null())
    {
        if (!head["revision"].is_number_integer() || head["revision"].get<int64_t>() <= 0 || !head["byte_count"].is_number_integer() ||
            head["byte_count"].get<int64_t>() < 4 || head["byte_count"].get<int64_t>() > NATIVE_FILE_LIMIT || !sha_ok(head["sha256"]))
            throw Unavailable("native slot checkpoint metadata is inconsistent");
        result["checkpoint"] = { { "revision", head["revision"] }, { "sha256", head["sha256"] }, { "bytes", head["byte_count"] } };
    }
    else if (!staged.is_null())
        throw Conflict("staged native slot has not been activated losslessly");
    try
    {
        const std::string& text = entity["state"].get_ref<const std::string&>();
        json state = loads(text);
        json reference = state.is_object() && state.contains("native_save") ? state["native_save"] : json();
        if (!state.is_object() || text.size() > 1024 * 1024 || canonical(reference) != canonical(result["checkpoint"]) ||
            (head.is_null() && state.contains("native_save")))
            throw Invalid("checkpoint reference differs from durable head");
    }
    catch (const Invalid&)
    {
        throw Unavailable("native slot checkpoint reference is inconsistent");
    }
    result["status"] = session["state"];
    result["entity_version"] = entity["version"];
    result["session_fence"] = session["fence"];
    return result;
}

json PlayerSaves::upload(Db& tx, const std::string& actor, const json& character_id, const json& fence, const json& session_fence, const json& upload_id)
{
    std::string id = persistent_id(upload_id);
    authorize(tx, actor, character_id, fence, session_fence);
    json row = tx.one("SELECT * FROM native_player_upload WHERE id=?", { id });
    if (row.is_null() || row["character_id"] != character_id || row["writer"] != actor || row["fence"] != fence ||
        row["session_fence"] != session_fence || row["epoch"].get<int64_t>() != *store_.epoch || row["expires_ms"].get<int64_t>() <= world_.real_ms())
        throw Conflict("native upload expired or changed authority");
    return row;
}

json PlayerSaves::begin(const std::string& actor, const std::string& command_id, const json& args)
{
    const json &character_id = arg(args, "character_id"), &fence = arg(args, "fence"), &session_fence = arg(args, "session_fence"),
               &entity_version = arg(args, "entity_version"), &base_revision = arg(args, "base_revision"), &slot = arg(args, "slot"),
               &byte_count = arg(args, "byte_count"), &sha256 = arg(args, "sha256");
    std::string id = persistent_id(character_id);
    positive(entity_version);
    if (!base_revision.is_number_integer() || as_int(base_revision) < 0 || as_int(base_revision) >= INT64_MAX)
        throw Invalid("invalid native base revision");
    if (!byte_count.is_number_integer() || as_int(byte_count) < 4 || as_int(byte_count) > NATIVE_FILE_LIMIT)
        throw Invalid("native checkpoint exceeds admission bounds");
    if (!sha_ok(sha256)) throw Invalid("invalid native checkpoint checksum");
    json payload = { { "type", "native_save_begin" }, { "character_id", character_id }, { "fence", fence }, { "session_fence", session_fence },
                     { "entity_version", entity_version }, { "base_revision", base_revision }, { "slot", slot },
                     { "byte_count", byte_count }, { "sha256", sha256 } };
    return store_.command(actor, command_id, payload, [&](Db& tx) -> json {
        json row = authorize(tx, actor, character_id, fence, session_fence);
        std::string account = tx.scalar("SELECT account FROM character WHERE id=?", { id }).get<std::string>();
        if (!slot.is_number_integer()) throw Invalid("invalid native character slot");
        if (native_identity(world_.world_id, world_.seed, account, as_int(slot)) != id) throw Conflict("native save account/slot identity mismatch");
        if (row["version"] != entity_version || revision(tx, id) != as_int(base_revision)) throw Conflict("native checkpoint version changed");
        int64_t now = world_.real_ms();
        tx.exec("DELETE FROM native_player_upload WHERE epoch<>? OR expires_ms<=? OR id IN ("
                "SELECT u.id FROM native_player_upload u JOIN entity e ON e.id=u.character_id "
                "JOIN player_session s ON s.character_id=u.character_id WHERE e.writer<>u.writer OR e.fence<>u.fence "
                "OR e.alive<>1 OR s.owner<>u.writer OR s.fence<>u.session_fence OR s.state<>'ACTIVE')", { *store_.epoch, now });
        if (!tx.one("SELECT 1 FROM native_player_upload WHERE character_id=?", { id }).is_null())
            throw Conflict("native character already has an incomplete upload");
        json usage = tx.one("SELECT COALESCE(SUM(byte_count),0) AS used,COUNT(*) AS count FROM native_player_upload");
        if (usage["used"].get<int64_t>() + as_int(byte_count) > UPLOAD_BUDGET || usage["count"].get<int64_t>() >= 32)
            throw Unavailable("native upload admission budget is full");
        std::string upload_id = uuid4_hex();
        tx.exec("INSERT INTO native_player_upload VALUES(?,?,?,?,?,?,?,?,?,?,?,?,?)",
                { upload_id, id, actor, fence, session_fence, *store_.epoch, entity_version, base_revision, slot, byte_count, sha256, 0,
                  now + UPLOAD_IDLE_MS });
        return { { "upload_id", upload_id }, { "offset", 0 }, { "chunk_bytes", CHUNK } };
    }, [&](Db& tx) { authorize(tx, actor, character_id, fence, session_fence); },
       [&](Db& tx, const json& result) { upload(tx, actor, character_id, fence, session_fence, result["upload_id"]); });
}

json PlayerSaves::append(const std::string& actor, const std::string& command_id, const json& args)
{
    const json &character_id = arg(args, "character_id"), &fence = arg(args, "fence"), &session_fence = arg(args, "session_fence"),
               &upload_id = arg(args, "upload_id"), &offset_value = arg(args, "offset"), &data = arg(args, "data");
    if (!offset_value.is_number_integer() || as_int(offset_value) < 0 || as_int(offset_value) % CHUNK || !data.is_string() ||
        data.get<std::string>().empty() || int64_t(data.get<std::string>().size()) > CHUNK * 4 / 3)
        throw Invalid("invalid native upload chunk");
    std::string raw;
    if (!base64_decode(data.get<std::string>(), raw)) throw Invalid("invalid native upload base64");
    if (raw.empty() || int64_t(raw.size()) > CHUNK || base64(raw) != data.get<std::string>()) throw Invalid("noncanonical native upload chunk");
    int64_t offset = as_int(offset_value);
    json payload = { { "type", "native_save_append" }, { "character_id", character_id }, { "fence", fence }, { "session_fence", session_fence },
                     { "upload_id", upload_id }, { "offset", offset_value }, { "data", data } };
    return store_.command(actor, command_id, payload, [&](Db& tx) -> json {
        json row = upload(tx, actor, character_id, fence, session_fence, upload_id);
        int64_t received = row["received"].get<int64_t>(), total = row["byte_count"].get<int64_t>(), size = int64_t(raw.size());
        if (offset != received || offset + size > total || (offset + size < total && size != CHUNK))
            throw Conflict("native upload offset or chunk size changed");
        tx.exec("INSERT INTO native_player_part VALUES(?,?,?)", { upload_id, offset, data });
        tx.exec("UPDATE native_player_upload SET received=?,expires_ms=? WHERE id=?", { offset + size, world_.real_ms() + UPLOAD_IDLE_MS, upload_id });
        return { { "upload_id", upload_id }, { "offset", offset + size } };
    }, [&](Db& tx) { upload(tx, actor, character_id, fence, session_fence, upload_id); });
}

json PlayerSaves::finish(const std::string& actor, const std::string& command_id, const json& args)
{
    const json &character_id = arg(args, "character_id"), &fence = arg(args, "fence"), &session_fence = arg(args, "session_fence"),
               &upload_id = arg(args, "upload_id");
    persistent_id(command_id);
    persistent_id(upload_id);
    json payload = { { "type", "native_save_finish" }, { "character_id", character_id }, { "fence", fence },
                     { "session_fence", session_fence }, { "upload_id", upload_id } };
    std::vector<json> parts;
    std::string expected;
    int64_t byte_count = 0;
    {
        std::lock_guard<std::recursive_mutex> guard(store_.lock);
        store_.require_epoch(store_.db);
        authorize(store_.db, actor, character_id, fence, session_fence);
        json previous = store_.db.one("SELECT payload_hash,result FROM command_result WHERE actor=? AND id=?", { actor, command_id });
        if (!previous.is_null())
        {
            if (previous["payload_hash"] != sha256_hex(canonical(payload))) throw Conflict("idempotency key reused for another command");
            return loads(previous["result"].get<std::string>());
        }
        json row = upload(store_.db, actor, character_id, fence, session_fence, upload_id);
        if (row["received"] != row["byte_count"]) throw Conflict("native upload is incomplete");
        parts = store_.db.all("SELECT offset,payload_base64 FROM native_player_part WHERE upload_id=? ORDER BY offset", { upload_id });
        expected = row["sha256"].get<std::string>();
        byte_count = row["byte_count"].get<int64_t>();
    }
    std::string raw;
    int64_t received = 0;
    for (auto& part : parts)
    {
        if (part["offset"].get<int64_t>() != received || !part["payload_base64"].is_string() || part["payload_base64"].get<std::string>().empty() ||
            int64_t(part["payload_base64"].get<std::string>().size()) > CHUNK * 4 / 3)
            throw Invalid("native staging chunk is inconsistent");
        std::string chunk;
        if (!base64_decode(part["payload_base64"].get<std::string>(), chunk)) throw Invalid("native staging chunk is invalid");
        if (base64(chunk) != part["payload_base64"].get<std::string>()) throw Invalid("native staging chunk is noncanonical");
        received += int64_t(chunk.size());
        if (chunk.empty() || received > byte_count || (received < byte_count && int64_t(chunk.size()) != CHUNK))
            throw Invalid("native staging byte count changed");
        raw += chunk;
    }
    if (received != byte_count) throw Invalid("native staging is incomplete");
    NativeSave saved = parse_native_save(raw);
    if (saved.sha256 != expected) throw Invalid("native upload complete checksum mismatch");
    std::string encoded = base64(raw);
    std::string id = character_id.get<std::string>();
    return store_.command(actor, command_id, payload, [&](Db& tx) -> json {
        json current = upload(tx, actor, character_id, fence, session_fence, upload_id);
        json entity = authorize(tx, actor, character_id, fence, session_fence);
        if (entity["version"] != current["entity_version"] || revision(tx, id) != current["base_revision"].get<int64_t>())
            throw Conflict("native checkpoint changed before commit");
        if (current["sha256"] != saved.sha256 || current["received"].get<int64_t>() != int64_t(raw.size()) ||
            current["byte_count"].get<int64_t>() != int64_t(raw.size()))
            throw Conflict("native upload changed before commit");
        int64_t revision_number = current["base_revision"].get<int64_t>() + 1;
        tx.exec("INSERT INTO native_player_save VALUES(?,?,?,?,?,?)",
                { id, revision_number, saved.sha256, int64_t(raw.size()), canonical(saved.summary()), encoded });
        json state = loads(entity["state"].get<std::string>());
        state["native_save"] = { { "revision", revision_number }, { "sha256", saved.sha256 }, { "bytes", int64_t(raw.size()) } };
        std::string text = canonical(state);
        tx.exec("UPDATE entity SET state=?,version=version+1 WHERE id=?", { text, id });
        tx.exec("UPDATE character SET state=? WHERE id=?", { text, id });
        tx.exec("DELETE FROM native_player_upload WHERE id=?", { upload_id });
        tx.exec("DELETE FROM native_player_save WHERE character_id=? AND revision<?", { id, revision_number - 1 });
        int64_t event = store_.event(tx, "entity:" + id, "NativePlayerSaveCommitted",
                                     { { "revision", revision_number }, { "sha256", saved.sha256 }, { "bytes", int64_t(raw.size()) } }, world_.now());
        return { { "character_id", id }, { "revision", revision_number }, { "entity_version", entity["version"].get<int64_t>() + 1 },
                 { "sha256", saved.sha256 }, { "bytes", int64_t(raw.size()) }, { "durable", true }, { "event", event } };
    }, [&](Db& tx) { authorize(tx, actor, character_id, fence, session_fence); });
}

json PlayerSaves::cancel(const std::string& actor, const std::string& command_id, const json& args)
{
    const json &character_id = arg(args, "character_id"), &fence = arg(args, "fence"), &session_fence = arg(args, "session_fence"),
               &upload_id = arg(args, "upload_id");
    std::string id = persistent_id(upload_id);
    json payload = { { "type", "native_save_cancel" }, { "character_id", character_id }, { "fence", fence },
                     { "session_fence", session_fence }, { "upload_id", upload_id } };
    return store_.command(actor, command_id, payload, [&](Db& tx) -> json {
        json row = tx.one("SELECT character_id,writer FROM native_player_upload WHERE id=?", { id });
        if (!row.is_null() && (row["character_id"] != character_id || row["writer"] != actor))
            throw Conflict("native upload belongs to another player/writer");
        tx.exec("DELETE FROM native_player_upload WHERE id=?", { id });
        return { { "cancelled", true } };
    }, [&](Db& tx) { authorize(tx, actor, character_id, fence, session_fence); });
}

json PlayerSaves::read(const std::string& actor, const std::string& character_id, int64_t fence, int64_t session_fence, int64_t revision_number,
                       int64_t offset, const std::optional<std::string>& transfer_id)
{
    positive(revision_number);
    if (offset < 0 || offset % CHUNK) throw Invalid("invalid native checkpoint read offset");
    std::lock_guard<std::recursive_mutex> guard(store_.lock);
    store_.require_epoch(store_.db);
    json transfer_reference;
    if (!transfer_id)
        authorize(store_.db, actor, character_id, fence, session_fence);
    else
    {
        persistent_id(*transfer_id);
        json transfer = store_.db.one("SELECT * FROM transfer WHERE id=?", { *transfer_id });
        if (transfer.is_null() || transfer["entity_id"] != character_id || transfer["target_owner"] != actor ||
            transfer["target_fence"] != fence || transfer["state"] != "CLAIMED")
            throw Conflict("native read requires the current destination claim");
        world_.require_location(store_.db, actor, transfer["target"].get<std::string>(), fence);
        json session = store_.db.one("SELECT fence,state FROM player_session WHERE character_id=?", { character_id });
        if (session.is_null() || session["fence"].get<int64_t>() != positive(session_fence) || session["state"] != "FROZEN")
            throw Conflict("native transfer session changed");
        json checkpoint = loads(transfer["checkpoint"].get<std::string>());
        for (auto& entity : checkpoint["entities"])
            if (entity["id"] == character_id)
            {
                json state = loads(entity["state"].get<std::string>());
                transfer_reference = state.contains("native_save") ? state["native_save"] : json();
            }
        bool referenced = transfer_reference.is_object() && !transfer_reference.empty() && transfer_reference.contains("revision") &&
                          transfer_reference["revision"] == revision_number;
        if (!referenced) throw Conflict("native save is outside the immutable transfer checkpoint");
    }
    json row = store_.db.one("SELECT revision,sha256,byte_count,summary,substr(payload_base64,?,?) AS data FROM native_player_save WHERE character_id=? AND revision=?",
                             { offset / 3 * 4 + 1, CHUNK * 4 / 3, character_id, revision_number });
    if (row.is_null() || offset >= row["byte_count"].get<int64_t>()) throw Invalid("unknown native checkpoint or read range");
    if (!transfer_reference.is_null() && (!transfer_reference.contains("sha256") || transfer_reference["sha256"] != row["sha256"]))
        throw Unavailable("native transfer checkpoint checksum mismatch");
    return { { "revision", revision_number }, { "sha256", row["sha256"] }, { "bytes", row["byte_count"] },
             { "summary", loads(row["summary"].get<std::string>()) }, { "offset", offset },
             { "next_offset", std::min(offset + CHUNK, row["byte_count"].get<int64_t>()) }, { "data", row["data"] } };
}
} // namespace lzm
