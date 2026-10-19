// scheduler.py, timelines.py and director.py: durable world events, the
// weather / emission / psi storm schedules the maps play, and the director
// that plans them on the game calendar like GAMMA's single-player managers.
#pragma once
#include "lzm_world.h"

namespace lzm
{
class Scheduler
{
public:
    explicit Scheduler(World& world);
    static void schedule_in(Db& tx, const std::string& event_id, double due_ms, const std::string& aggregate, int64_t version,
                     const std::string& type, const json& payload, int priority = 0);
    int64_t run_due(int limit = 64, double budget_ms = 5);
    int64_t drain_due_in(Db& tx, double cutoff, int limit = 64, double budget_ms = 5);

private:
    World& world_;
    void apply_event_in(Db& tx, const json& row, double now);
    std::pair<json, bool> timeline_phase(Db& tx, const json& event);
};

class Timelines
{
public:
    explicit Timelines(World& world);
    World& world;
    Scheduler scheduler;
    json schedule(const std::string& actor, const std::string& command_id, const json& name, const json& timeline_id,
                  const json& version, const json& times, const json& parameters);
    static const std::vector<std::string>& phases(const std::string& name);
    static std::string event_id(const std::string& name, const std::string& timeline_id, const std::string& phase);
    static json public_state(const std::string& name, const json& envelope);
    static json evaluate(const std::string& name, const json& state, double world_ms);
};

// Python's random.Random(str): MT19937 seeded by init_by_array of
// int.from_bytes(text + sha512(text)), with Python's choice/randint/uniform.
class PyRandom
{
public:
    explicit PyRandom(const std::string& seed_text);
    uint32_t genrand();
    uint64_t getrandbits(int k);
    double random();
    int64_t randbelow(int64_t n);
    int64_t randint(int64_t a, int64_t b) { return a + randbelow(b - a + 1); }
    double uniform(double a, double b) { return a + (b - a) * random(); }

private:
    uint32_t mt_[624];
    int index_ = 625;
    void init_genrand(uint32_t s);
    void init_by_array(const std::vector<uint32_t>& key);
};

class Director
{
public:
    Director(World& world, Timelines& timelines, const json& config);
    std::vector<std::string> tick();

private:
    World& world_;
    Timelines& timelines_;
    json config_;
    std::pair<int64_t, json> read(const std::string& name);
    PyRandom rng(json& state, const std::string& purpose);
    void schedule(const std::string& name, const json& times, const json& parameters);
    std::string next_cycle(PyRandom& rng, const std::string& current, json& history);
    std::optional<std::string> weather(double now, json& state);
    std::optional<std::string> event(double now, json& state, const std::string& name, const char* frequency_key,
                                     const char* seconds_key, const std::string& other);
};
} // namespace lzm
