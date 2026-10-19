#include "lzm_timelines.h"

#include <algorithm>
#include <cmath>

namespace lzm
{
// -- scheduler.py ------------------------------------------------------------------------------
Scheduler::Scheduler(World& world) : world_(world)
{
    if (!world.scheduler_handlers.count("TimelinePhase"))
        world.scheduler_handlers["TimelinePhase"] = [this](Db& tx, const json& event) { return timeline_phase(tx, event); };
    world.mutation_drain = [this](Db& tx, double cutoff) { drain_due_in(tx, cutoff); };
}

void Scheduler::apply_event_in(Db& tx, const json& row, double now)
{
    std::string type = row["type"].get<std::string>();
    auto handler = world_.scheduler_handlers.find(type);
    if (handler == world_.scheduler_handlers.end()) throw UnavailableHandler(type);
    auto [result, applied] = handler->second(tx, row);
    tx.exec("UPDATE scheduled_event SET state=?,result=? WHERE id=? AND state='PENDING'",
            { applied ? "APPLIED" : "CANCELLED", canonical(result), row["id"] });
    world_.store.event(tx, row["aggregate_id"].get<std::string>(), applied ? "ScheduledEventApplied" : "ScheduledEventCancelled",
                       { { "event_id", row["id"] }, { "result", result }, { "applied_world_ms", now } },
                       row["due_world_ms"].get<double>(), "world", now);
}

int64_t Scheduler::drain_due_in(Db& tx, double cutoff, int limit, double budget_ms)
{
    finite(cutoff);
    if (limit < 1 || limit > 256 || !(budget_ms > 0 && budget_ms <= 1000)) throw Invalid("invalid scheduler work budget");
    world_.store.require_epoch(tx);
    int64_t start = monotonic_ns(), count = 0;
    while (true)
    {
        json row = tx.one("SELECT * FROM scheduled_event WHERE state='PENDING' AND due_world_ms<=? ORDER BY due_world_ms,priority,id LIMIT 1", { cutoff });
        if (row.is_null()) return count;
        if (count >= limit || double(monotonic_ns() - start) / 1e6 >= budget_ms)
            throw Unavailable("earlier world events require background catch-up before mutation");
        apply_event_in(tx, row, cutoff);
        ++count;
    }
}

void Scheduler::schedule_in(Db& tx, const std::string& event_id, double due_ms, const std::string& aggregate, int64_t version,
                            const std::string& type, const json& payload, int priority)
{
    persistent_id(event_id);
    finite(due_ms);
    identifier(aggregate);
    positive(version);
    identifier(type);
    if (priority < 0 || priority > 100) throw Invalid("invalid event priority");
    std::string encoded = canonical(payload);
    json existing = tx.one("SELECT * FROM scheduled_event WHERE id=?", { event_id });
    if (!existing.is_null())
    {
        if (existing["due_world_ms"].get<double>() != due_ms || existing["aggregate_id"] != aggregate ||
            existing["expected_version"].get<int64_t>() != version || existing["type"] != type || existing["payload"] != encoded ||
            existing["priority"].get<int64_t>() != priority)
            throw Conflict("scheduled event ID reused with different input");
        return;
    }
    tx.exec("INSERT INTO scheduled_event VALUES(?,?,?,?,?,?,'PENDING',?,NULL)",
            { event_id, due_ms, priority, aggregate, version, type, encoded });
}

int64_t Scheduler::run_due(int limit, double budget_ms)
{
    if (limit < 1 || limit > 256 || !(budget_ms > 0 && budget_ms <= 1000)) throw Invalid("invalid scheduler work budget");
    int64_t start = monotonic_ns();
    int64_t count = 0;
    while (count < limit && double(monotonic_ns() - start) / 1e6 < budget_ms)
    {
        bool done = world_.store.transaction([&](Db& tx) {
            world_.store.require_epoch(tx);
            double now = world_.now();
            json row = tx.one("SELECT * FROM scheduled_event WHERE state='PENDING' AND due_world_ms<=? ORDER BY due_world_ms,priority,id LIMIT 1", { now });
            if (row.is_null()) return true;
            apply_event_in(tx, row, now);
            return false;
        });
        if (done) break;
        ++count;
    }
    return count;
}

std::pair<json, bool> Scheduler::timeline_phase(Db& tx, const json& event)
{
    json payload = loads(event["payload"].get<std::string>());
    std::string name = payload["name"].get<std::string>();
    json row = tx.one("SELECT * FROM world_state WHERE name=?", { name });
    if (row.is_null() || row["version"] != event["expected_version"])
        return { { { "reason", "timeline version changed" } }, false };
    json state = loads(row["state"].get<std::string>());
    if (!state.contains("timeline_id") || state["timeline_id"] != payload["timeline_id"])
        return { { { "reason", "timeline replaced" } }, false };
    state["phase"] = payload["phase"];
    tx.exec("UPDATE world_state SET state=?,version=version+1 WHERE name=?", { canonical(state), name });
    return { { { "name", name }, { "phase", payload["phase"] }, { "version", row["version"].get<int64_t>() + 1 },
               { "timeline_id", payload["timeline_id"] } }, true };
}

// -- timelines.py ------------------------------------------------------------------------------------
Timelines::Timelines(World& w) : world(w), scheduler(w) {}

const std::vector<std::string>& Timelines::phases(const std::string& name)
{
    static const std::vector<std::string> weather = { "TRANSITION", "SETTLED" };
    static const std::vector<std::string> event = { "WARNING", "ACTIVE", "PEAK", "ENDED" };
    static const std::vector<std::string> none;
    if (name == "weather") return weather;
    if (name == "emission" || name == "psi_storm") return event;
    return none;
}

std::string Timelines::event_id(const std::string& name, const std::string& timeline_id, const std::string& phase)
{
    return sha256_hex("timeline:" + name + ":" + timeline_id + ":" + phase).substr(0, 32);
}

static bool same_keys(const json& times, const std::vector<std::string>& names)
{
    if (!times.is_object() || times.size() != names.size()) return false;
    for (auto& n : names)
        if (!times.contains(n)) return false;
    return true;
}

static bool seed_ok(const json& seed)
{
    return seed.is_number_unsigned() || (seed.is_number_integer() && seed.get<int64_t>() >= 0);
}

json Timelines::schedule(const std::string& actor, const std::string& command_id, const json& name_value, const json& timeline_id_value,
                         const json& version, const json& times, const json& parameters)
{
    if (!name_value.is_string() || phases(name_value.get<std::string>()).empty() ||
        (!version.is_null() && (!version.is_number_integer() || as_int(version) < 0)))
        throw Invalid("invalid timeline name/version");
    std::string name = name_value.get<std::string>();
    std::string timeline_id = persistent_id(timeline_id_value);
    if (!times.is_object() || !parameters.is_object()) throw Invalid("invalid timeline schedule");
    const auto& names = phases(name);
    if (!same_keys(times, names)) throw Invalid("timeline phases are incomplete");
    std::vector<double> values;
    for (auto& phase : names) values.push_back(finite(times[phase]));
    for (size_t i = 1; i < values.size(); ++i)
        if (values[i] <= values[i - 1]) throw Invalid("timeline phases must be strictly ordered");
    if (name == "weather")
    {
        identifier(parameters.contains("source") ? parameters["source"] : json());
        identifier(parameters.contains("target") ? parameters["target"] : json());
    }
    else
    {
        double intensity = finite(parameters.contains("intensity") ? parameters["intensity"] : json(), 0, 100);
        if (!(intensity > 0 && intensity <= 100)) throw Invalid("invalid emission intensity");
    }
    if (!parameters.contains("seed") || !seed_ok(parameters["seed"])) throw Invalid("timeline requires a stable seed");
    json payload = { { "type", "timeline_schedule" }, { "name", name }, { "timeline_id", timeline_id },
                     { "version", version }, { "times", times }, { "parameters", parameters } };
    return world.store.command(actor, command_id, payload, world.mutation([=](Db& tx) -> json {
        json old = tx.one("SELECT * FROM world_state WHERE name=?", { name });
        int64_t current = old.is_null() ? 0 : old["version"].get<int64_t>();
        if (!version.is_null() && current != as_int(version)) throw Conflict("timeline version changed");
        positive(current + int64_t(names.size()) + 1, "final timeline version");
        int64_t next_version = current + 1;
        if (!tx.one("SELECT 1 FROM scheduled_event WHERE id=?", { event_id(name, timeline_id, names[0]) }).is_null())
            throw Conflict("timeline ID cannot be reused");
        json state = { { "timeline_id", timeline_id }, { "phase", "SCHEDULED" }, { "times", times }, { "parameters", parameters } };
        tx.exec("INSERT INTO world_state VALUES(?,?,?) ON CONFLICT(name) DO UPDATE SET version=excluded.version,state=excluded.state",
                { name, next_version, canonical(state) });
        for (size_t index = 0; index < names.size(); ++index)
            scheduler.schedule_in(tx, event_id(name, timeline_id, names[index]), as_number(times[names[index]]), "world:" + name,
                                  next_version + int64_t(index), "TimelinePhase",
                                  { { "name", name }, { "timeline_id", timeline_id }, { "phase", names[index] } });
        int64_t event = world.store.event(tx, "world:" + name, "TimelineScheduled", payload, world.now());
        return { { "timeline_id", timeline_id }, { "version", next_version }, { "event", event } };
    }));
}

json Timelines::public_state(const std::string& name, const json& envelope)
{
    const auto& names = phases(name);
    if (names.empty() || !envelope.is_object()) throw Invalid("invalid public timeline");
    int64_t version = positive(envelope.contains("version") ? envelope["version"] : json());
    const json state = envelope.contains("state") ? envelope["state"] : json();
    if (!state.is_object()) throw Invalid("invalid public timeline state");
    std::string timeline_id = persistent_id(state.contains("timeline_id") ? state["timeline_id"] : json());
    json phase = state.contains("phase") ? state["phase"] : json();
    bool known = phase == "SCHEDULED";
    for (auto& n : names) known = known || phase == n;
    if (!known) throw Invalid("invalid public timeline phase");
    json times = state.contains("times") ? state["times"] : json();
    json parameters = state.contains("parameters") ? state["parameters"] : json();
    if (!same_keys(times, names) || !parameters.is_object()) throw Invalid("incomplete public timeline");
    json out_times = json::object();
    double previous = -1;
    bool first = true;
    for (auto& n : names)
    {
        double v = finite(times[n]);
        if (!first && v <= previous) throw Invalid("invalid public timeline times");
        previous = v;
        first = false;
        out_times[n] = times[n];
    }
    if (!parameters.contains("seed") || !seed_ok(parameters["seed"])) throw Invalid("invalid public timeline seed");
    json pub = { { "seed", parameters["seed"] } };
    if (name == "weather")
    {
        pub["source"] = identifier(parameters.contains("source") ? parameters["source"] : json());
        pub["target"] = identifier(parameters.contains("target") ? parameters["target"] : json());
    }
    else
    {
        json intensity = parameters.contains("intensity") ? parameters["intensity"] : json();
        if (finite(intensity, 0, 100) == 0) throw Invalid("invalid public timeline intensity");
        pub["intensity"] = intensity;
    }
    return { { "version", version }, { "state", { { "timeline_id", timeline_id }, { "phase", phase }, { "times", out_times }, { "parameters", pub } } } };
}

json Timelines::evaluate(const std::string& name, const json& state, double world_ms)
{
    finite(world_ms);
    const json& times = state["times"];
    std::string phase = "SCHEDULED";
    for (auto& candidate : phases(name))
        if (world_ms >= as_number(times[candidate])) phase = candidate;
    json result = { { "timeline_id", state["timeline_id"] }, { "phase", phase }, { "parameters", state["parameters"] } };
    if (name == "weather")
    {
        double a = as_number(times["TRANSITION"]), b = as_number(times["SETTLED"]);
        result["blend"] = std::min(1.0, std::max(0.0, (world_ms - a) / (b - a)));
    }
    return result;
}

// -- Python's random ---------------------------------------------------------------------------------
void PyRandom::init_genrand(uint32_t s)
{
    mt_[0] = s;
    for (int i = 1; i < 624; ++i) mt_[i] = 1812433253U * (mt_[i - 1] ^ (mt_[i - 1] >> 30)) + uint32_t(i);
    index_ = 624;
}

void PyRandom::init_by_array(const std::vector<uint32_t>& key)
{
    init_genrand(19650218U);
    int i = 1;
    size_t j = 0;
    size_t k = 624 > key.size() ? 624 : key.size();
    for (; k; --k)
    {
        mt_[i] = (mt_[i] ^ ((mt_[i - 1] ^ (mt_[i - 1] >> 30)) * 1664525U)) + key[j] + uint32_t(j);
        ++i; ++j;
        if (i >= 624) { mt_[0] = mt_[623]; i = 1; }
        if (j >= key.size()) j = 0;
    }
    for (k = 623; k; --k)
    {
        mt_[i] = (mt_[i] ^ ((mt_[i - 1] ^ (mt_[i - 1] >> 30)) * 1566083941U)) - uint32_t(i);
        ++i;
        if (i >= 624) { mt_[0] = mt_[623]; i = 1; }
    }
    mt_[0] = 0x80000000U;
    index_ = 624;
}

PyRandom::PyRandom(const std::string& text)
{
    // int.from_bytes(text + sha512(text), "big"), split into 32-bit words from the low end.
    std::string bytes = text + sha512_raw(text);
    size_t start = 0;
    while (start < bytes.size() && bytes[start] == 0) ++start;
    std::vector<uint32_t> key;
    for (size_t end = bytes.size(); end > start;)
    {
        size_t begin = end >= start + 4 ? end - 4 : start;
        uint32_t word = 0;
        for (size_t p = begin; p < end; ++p) word = (word << 8) | uint8_t(bytes[p]);
        key.push_back(word);
        end = begin;
    }
    if (key.empty()) key.push_back(0);
    init_by_array(key);
}

uint32_t PyRandom::genrand()
{
    if (index_ >= 624)
    {
        for (int kk = 0; kk < 624; ++kk)
        {
            uint32_t y = (mt_[kk] & 0x80000000U) | (mt_[(kk + 1) % 624] & 0x7fffffffU);
            mt_[kk] = mt_[(kk + 397) % 624] ^ (y >> 1) ^ ((y & 1U) ? 0x9908b0dfU : 0U);
        }
        index_ = 0;
    }
    uint32_t y = mt_[index_++];
    y ^= (y >> 11);
    y ^= (y << 7) & 0x9d2c5680U;
    y ^= (y << 15) & 0xefc60000U;
    y ^= (y >> 18);
    return y;
}

uint64_t PyRandom::getrandbits(int k)
{
    if (k <= 0) return 0;
    if (k <= 32) return genrand() >> (32 - k);
    uint64_t low = genrand();
    uint64_t high = genrand() >> (64 - k);
    return low | (high << 32);
}

double PyRandom::random()
{
    uint32_t a = genrand() >> 5, b = genrand() >> 6;
    return (a * 67108864.0 + b) * (1.0 / 9007199254740992.0);
}

int64_t PyRandom::randbelow(int64_t n)
{
    if (n <= 0) return 0;
    int k = 0;
    for (uint64_t v = uint64_t(n); v; v >>= 1) ++k;
    uint64_t r = getrandbits(k);
    while (r >= uint64_t(n)) r = getrandbits(k);
    return int64_t(r);
}

// -- director.py ----------------------------------------------------------------------------------
static const double HOUR = 3600 * 1000.0;

Director::Director(World& world, Timelines& timelines, const json& config) : world_(world), timelines_(timelines)
{
    config_ = { { "enabled", true }, { "weather_cycles", { "clear", "partly", "cloudy", "rain", "storm", "foggy" } },
                { "weather_period_hours", 6 }, { "weather_transition_hours", 1 }, { "emission_frequency_hours", 24 },
                { "emission_seconds", 2220 }, { "psi_storm_frequency_hours", 48 }, { "psi_storm_seconds", 1030 },
                { "event_gap_hours", 2 }, { "lead_seconds", 60 } };
    if (config.is_object())
        for (auto it = config.begin(); it != config.end(); ++it)
        {
            if (!config_.contains(it.key())) throw Invalid("unknown director setting " + it.key());
            config_[it.key()] = it.value();
        }
    const json& cycles = config_["weather_cycles"];
    std::vector<json> seen;
    bool distinct = cycles.is_array();
    if (distinct)
        for (auto& c : cycles)
        {
            if (std::find(seen.begin(), seen.end(), c) != seen.end()) distinct = false;
            seen.push_back(c);
        }
    if (!distinct || cycles.size() < 2) throw Invalid("director needs at least two distinct weather cycles");
}

std::pair<int64_t, json> Director::read(const std::string& name)
{
    std::lock_guard<std::recursive_mutex> guard(world_.store.lock);
    world_.store.require_epoch(world_.store.db);
    json row = world_.store.db.one("SELECT version,state FROM world_state WHERE name=?", { name });
    if (row.is_null()) return { 0, json() };
    return { row["version"].get<int64_t>(), loads(row["state"].get<std::string>()) };
}

PyRandom Director::rng(json& state, const std::string& purpose)
{
    if (!state.contains("counter")) state["counter"] = 0;
    int64_t counter = as_int(state["counter"]);
    state["counter"] = counter + 1;
    return PyRandom(std::to_string(world_.seed) + ":" + purpose + ":" + std::to_string(counter));
}

void Director::schedule(const std::string& name, const json& times, const json& parameters)
{
    timelines_.schedule("director", uuid4_hex(), name, uuid4_hex(), json(), times, parameters);
}

std::string Director::next_cycle(PyRandom& random, const std::string& current, json& history)
{
    std::vector<std::string> cycles;
    for (auto& c : config_["weather_cycles"]) cycles.push_back(c.get<std::string>());
    auto count = [&](const std::string& c) { int n = 0; for (auto& h : history) if (h == c) ++n; return n; };
    std::vector<std::string> allowed;
    for (auto& c : cycles)
        if (c != current && count(c) < 2) allowed.push_back(c);
    if (allowed.empty())
    {
        history = json::array();
        for (auto& c : cycles)
            if (c != current) allowed.push_back(c);
    }
    std::string pick = allowed[size_t(random.randbelow(int64_t(allowed.size())))];
    history.push_back(pick);
    return pick;
}

// Python -(-period * 2 // 3): the ceiling of two thirds.
static int64_t ceil_two_thirds(int64_t period)
{
    int64_t v = period * 2;
    return v >= 0 ? (v + 2) / 3 : -((-v) / 3);
}

std::optional<std::string> Director::weather(double now, json& state)
{
    auto [version, timeline] = read("weather");
    (void)version;
    json change_at = state.contains("weather_change_at") ? state["weather_change_at"] : json();
    if (!timeline.is_null() && !change_at.is_null() && now < as_number(change_at)) return std::nullopt;
    PyRandom random = rng(state, "weather");
    if (!state.contains("weather_history")) state["weather_history"] = json::array();
    json& history = state["weather_history"];
    std::string current = !timeline.is_null() ? timeline["parameters"]["target"].get<std::string>() : config_["weather_cycles"][0].get<std::string>();
    std::string target = !timeline.is_null() ? next_cycle(random, current, history) : current;
    double start = now + as_number(config_["lead_seconds"]) * 1000.0;
    double transition = as_number(config_["weather_transition_hours"]) * HOUR;
    uint64_t seed = random.getrandbits(63);
    schedule("weather", { { "TRANSITION", start }, { "SETTLED", start + transition } },
             { { "source", current }, { "target", target }, { "seed", int64_t(seed) } });
    int64_t period = as_int(config_["weather_period_hours"]);
    int64_t hours = random.randint(std::max<int64_t>(1, ceil_two_thirds(period)), period);
    state["weather_change_at"] = start + double(hours) * HOUR;
    return "weather " + current + " -> " + target + ", next change in " + std::to_string(hours) + " h";
}

std::optional<std::string> Director::event(double now, json& state, const std::string& name, const char* frequency_key,
                                           const char* seconds_key, const std::string& other)
{
    auto [version, timeline] = read(name);
    (void)version;
    json planned = state.contains(name + "_at") ? state[name + "_at"] : json();
    double last_end;
    if (!timeline.is_null() && !planned.is_null() && as_number(timeline["times"]["WARNING"]) == as_number(planned))
    {
        if (now < as_number(timeline["times"]["ENDED"])) return std::nullopt;
        last_end = as_number(timeline["times"]["ENDED"]);
    }
    else if (!timeline.is_null() && now < as_number(timeline["times"]["ENDED"]))
    {
        state[name + "_at"] = timeline["times"]["WARNING"];
        return std::nullopt;
    }
    else
        last_end = !timeline.is_null() ? as_number(timeline["times"]["ENDED"]) : now;
    PyRandom random = rng(state, name);
    double frequency = as_number(config_[frequency_key]);
    double lead = now + as_number(config_["lead_seconds"]) * 1000.0;
    double rolled = last_end + random.uniform(frequency / 2, frequency) * HOUR;
    double start = std::max(lead, rolled);
    double length = as_number(config_[seconds_key]) * 1000.0;
    auto [other_version, other_timeline] = read(other);
    (void)other_version;
    double gap = as_number(config_["event_gap_hours"]) * HOUR;
    if (!other_timeline.is_null())
    {
        double begin = as_number(other_timeline["times"]["WARNING"]), end = as_number(other_timeline["times"]["ENDED"]);
        if (start < end + gap && start + length + gap > begin) start = end + gap;
    }
    json times = { { "WARNING", start }, { "ACTIVE", start + length * 0.25 }, { "PEAK", start + length * 0.6 }, { "ENDED", start + length } };
    uint64_t seed = random.getrandbits(63);
    schedule(name, times, { { "intensity", 100 }, { "seed", int64_t(seed) } });
    state[name + "_at"] = start;
    return name + " at +" + format("%.1f", (start - now) / HOUR) + " h";
}

std::vector<std::string> Director::tick()
{
    std::vector<std::string> done;
    if (!config_["enabled"].get<bool>()) return done;
    double now = world_.now();
    auto [version, saved] = read("director");
    json state = saved.is_object() ? saved : json::object();
    for (int step = 0; step < 3; ++step)
    {
        std::optional<std::string> result;
        try
        {
            if (step == 0) result = weather(now, state);
            else if (step == 1) result = event(now, state, "emission", "emission_frequency_hours", "emission_seconds", "psi_storm");
            else result = event(now, state, "psi_storm", "psi_storm_frequency_hours", "psi_storm_seconds", "emission");
        }
        catch (const Conflict&) { result.reset(); }
        catch (const Unavailable&) { result.reset(); }
        if (result) done.push_back(*result);
    }
    if (!done.empty()) world_.set_state("director", uuid4_hex(), "director", version, state);
    return done;
}
} // namespace lzm
