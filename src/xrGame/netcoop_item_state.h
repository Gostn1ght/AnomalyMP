#pragma once
#include <cstdint>
#include <cstddef>

// Authoritative state of one item instance (stage 1 of the gameplay plan).
//
// The object ID is the instance: two PDAs are two IDs with their own state.
// The section is the template. The server owns this state, versions every
// change and sends only the changed fields; a full snapshot goes out the
// first time, when the item changes owner and when a client joins.
//
// Shared by the engine (netcoop_items.inc) and the native host test
// (scripts/check-item-state.cpp): no engine headers here.
namespace netcoop
{
namespace item_state
{
// Field mask on the wire and in diffs.
enum : uint16_t
{
	f_condition = 1 << 0, // durability, or the charge of a device (Anomaly keeps both in condition)
	f_uses = 1 << 1, // remaining / maximum portions of food, drinks, medicine, kits
	f_ammo = 1 << 2, // weapon magazine: current ammo type and the cartridge sequence
	f_addons = 1 << 3, // weapon scope / silencer / launcher flags
	f_uid = 1 << 4, // persistent instance id (survives saves, stashes and transfers)
	f_stack = 1 << 5, // rounds left in an ammunition box
};
// Fields the owner of a carried item simulates itself (wear and drain from
// its own use, its own shots); the server validates and stores the owner's
// reports and does not echo its own duplicate simulation back to the owner.
static const uint16_t f_owner_predicted = f_condition | f_ammo | f_stack;
static const uint16_t f_all = f_condition | f_uses | f_ammo | f_addons | f_uid | f_stack;
// Entry flag on the wire: a full snapshot, applied even to predicted fields.
static const uint16_t f_full = 1 << 15;
static const uint32_t max_runs = 16;

struct State
{
	uint64_t uid = 0;
	uint16_t condition = 65535;
	bool has_uses = false;
	uint8_t uses = 0, max_uses = 0;
	bool weapon = false;
	uint8_t ammo_type = 0, addons = 0;
	// Magazine as runs of equal cartridges, first run = bottom of the magazine.
	uint8_t runs = 0;
	uint8_t run_type[max_runs] = {};
	uint16_t run_count[max_runs] = {};
	bool stack = false;
	uint16_t stack_count = 0;
};

inline uint16_t quantize(float value)
{
	if (!(value > 0.f)) return 0;
	if (value >= 1.f) return 65535;
	return uint16_t(value * 65535.f + 0.5f);
}
inline float dequantize(uint16_t value) { return float(value) / 65535.f; }

// Fields that exist for this kind of item.
inline uint16_t applicable(const State& s)
{
	uint16_t mask = f_condition | f_uid;
	if (s.has_uses) mask |= f_uses;
	if (s.weapon) mask |= f_ammo | f_addons;
	if (s.stack) mask |= f_stack;
	return mask;
}

inline uint32_t ammo_total(const State& s)
{
	uint32_t total = 0;
	for (uint32_t i = 0; i < s.runs; ++i) total += s.run_count[i];
	return total;
}

inline bool same_ammo(const State& a, const State& b)
{
	if (a.ammo_type != b.ammo_type || a.runs != b.runs) return false;
	for (uint32_t i = 0; i < a.runs; ++i)
		if (a.run_type[i] != b.run_type[i] || a.run_count[i] != b.run_count[i]) return false;
	return true;
}

inline uint16_t diff(const State& a, const State& b)
{
	uint16_t mask = 0;
	if (a.uid != b.uid) mask |= f_uid;
	if (a.condition != b.condition) mask |= f_condition;
	if (a.has_uses != b.has_uses || a.uses != b.uses || a.max_uses != b.max_uses) mask |= f_uses;
	if (a.weapon != b.weapon || !same_ammo(a, b)) mask |= f_ammo;
	if (a.weapon != b.weapon || a.addons != b.addons) mask |= f_addons;
	if (a.stack != b.stack || a.stack_count != b.stack_count) mask |= f_stack;
	return mask & (applicable(a) | applicable(b));
}

// Copies the masked fields of `from` into `to`.
inline void merge(State& to, const State& from, uint16_t mask)
{
	if (mask & f_uid) to.uid = from.uid;
	if (mask & f_condition) to.condition = from.condition;
	if (mask & f_uses) { to.has_uses = from.has_uses; to.uses = from.uses; to.max_uses = from.max_uses; }
	if (mask & f_ammo)
	{
		to.weapon = from.weapon; to.ammo_type = from.ammo_type; to.runs = from.runs;
		for (uint32_t i = 0; i < max_runs; ++i) { to.run_type[i] = from.run_type[i]; to.run_count[i] = from.run_count[i]; }
	}
	if (mask & f_addons) { to.weapon = from.weapon; to.addons = from.addons; }
	if (mask & f_stack) { to.stack = from.stack; to.stack_count = from.stack_count; }
}

// Versions wrap; within one item incarnation a newer version is at most
// 32767 steps ahead.
inline bool newer(uint16_t incoming, uint16_t known) { return int16_t(uint16_t(incoming - known)) > 0; }

// Builds the runs from the type of each cartridge, bottom first. More than
// max_runs alternations keep the count and fold the rest into the last run.
// Returns false when types were folded.
template<class TypeAt>
bool set_magazine(State& s, uint32_t count, TypeAt type_at)
{
	s.runs = 0;
	bool exact = true;
	for (uint32_t i = 0; i < count; ++i)
	{
		const uint8_t type = type_at(i);
		if (s.runs && s.run_type[s.runs - 1] == type && s.run_count[s.runs - 1] < 65535) { ++s.run_count[s.runs - 1]; continue; }
		if (s.runs == max_runs) { exact = false; if (s.run_count[s.runs - 1] < 65535) ++s.run_count[s.runs - 1]; continue; }
		s.run_type[s.runs] = type; s.run_count[s.runs] = 1; ++s.runs;
	}
	return exact;
}

template<class Writer>
void write(Writer& w, const State& s, uint16_t mask)
{
	if (mask & f_uid) w.w_u64(s.uid);
	if (mask & f_condition) w.w_u16(s.condition);
	if (mask & f_uses) { w.w_u8(s.has_uses ? 1 : 0); w.w_u8(s.uses); w.w_u8(s.max_uses); }
	if (mask & f_ammo)
	{
		w.w_u8(s.weapon ? 1 : 0); w.w_u8(s.ammo_type); w.w_u8(s.runs);
		for (uint32_t i = 0; i < s.runs; ++i) { w.w_u8(s.run_type[i]); w.w_u16(s.run_count[i]); }
	}
	if (mask & f_addons) w.w_u8(s.addons);
	if (mask & f_stack) { w.w_u8(s.stack ? 1 : 0); w.w_u16(s.stack_count); }
}

// Never reads past the packet: false on a short or malformed entry.
template<class Reader>
bool read(Reader& r, State& s, uint16_t mask)
{
	if (mask & ~f_all) return false;
	if (mask & f_uid) { if (r.r_elapsed() < 8) return false; r.r_u64(s.uid); }
	if (mask & f_condition) { if (r.r_elapsed() < 2) return false; r.r_u16(s.condition); }
	if (mask & f_uses)
	{
		if (r.r_elapsed() < 3) return false;
		uint8_t has = 0; r.r_u8(has); r.r_u8(s.uses); r.r_u8(s.max_uses);
		// 255 remaining uses means unlimited.
		if (has > 1 || (s.uses > s.max_uses && s.uses != 255)) return false;
		s.has_uses = has != 0;
	}
	if (mask & f_ammo)
	{
		if (r.r_elapsed() < 3) return false;
		uint8_t weapon = 0, runs = 0; r.r_u8(weapon); r.r_u8(s.ammo_type); r.r_u8(runs);
		if (weapon > 1 || runs > max_runs || r.r_elapsed() < uint32_t(runs) * 3) return false;
		s.weapon = weapon != 0; s.runs = runs;
		for (uint32_t i = 0; i < runs; ++i)
		{
			r.r_u8(s.run_type[i]); r.r_u16(s.run_count[i]);
			if (!s.run_count[i]) return false;
		}
	}
	if (mask & f_addons) { if (r.r_elapsed() < 1) return false; r.r_u8(s.addons); }
	if (mask & f_stack)
	{
		if (r.r_elapsed() < 3) return false;
		uint8_t stack = 0; r.r_u8(stack); r.r_u16(s.stack_count);
		if (stack > 1) return false;
		s.stack = stack != 0;
	}
	return true;
}

// ---- owner reports (client -> server) ----------------------------------
enum Verdict
{
	verdict_unchanged,
	verdict_wear, // lower condition / fewer rounds: what use, shots and drain do
	verdict_raise, // higher condition or more rounds: repair, charging, reloading
	verdict_reject,
};

inline Verdict judge_condition(uint16_t stored, uint16_t proposed)
{
	if (proposed == stored) return verdict_unchanged;
	return proposed < stored ? verdict_wear : verdict_raise;
}

// mag_size: weapon capacity (+1 for a chambered round), type_count: ammo
// types this weapon accepts.
inline Verdict judge_ammo(const State& stored, const State& proposed, uint32_t mag_size, uint32_t type_count)
{
	if (!proposed.weapon || proposed.runs > max_runs || proposed.ammo_type >= type_count) return verdict_reject;
	for (uint32_t i = 0; i < proposed.runs; ++i)
		if (proposed.run_type[i] >= type_count || !proposed.run_count[i]) return verdict_reject;
	const uint32_t total = ammo_total(proposed), before = ammo_total(stored);
	if (total > mag_size) return verdict_reject;
	if (same_ammo(stored, proposed)) return verdict_unchanged;
	return total < before ? verdict_wear : verdict_raise;
}

inline Verdict judge_stack(uint16_t stored, uint16_t proposed, uint16_t box_size)
{
	if (proposed > box_size) return verdict_reject;
	if (proposed == stored) return verdict_unchanged;
	return proposed < stored ? verdict_wear : verdict_raise;
}
} // namespace item_state
} // namespace netcoop
