// Native host test of the item instance state model (src/xrGame/netcoop_item_state.h):
// wire round trips, malformed packets, version order, magazines, owner report
// verdicts and the plan's TEST A/B transfer scenarios at the model level.
#include "../src/xrGame/netcoop_item_state.h"
#include <cstdio>
#include <cstring>
#include <vector>

using namespace netcoop::item_state;

static int failures = 0;
#define CHECK(x) do { if (!(x)) { std::printf("FAIL %s:%d %s\n", __FILE__, __LINE__, #x); ++failures; } } while (0)

struct Packet
{
	std::vector<uint8_t> data;
	uint32_t pos = 0;
	void put(const void* p, size_t n) { const uint8_t* b = (const uint8_t*)p; data.insert(data.end(), b, b + n); }
	void get(void* p, size_t n) { std::memcpy(p, data.data() + pos, n); pos += uint32_t(n); }
	void w_u8(uint8_t v) { put(&v, 1); }
	void w_u16(uint16_t v) { put(&v, 2); }
	void w_u64(uint64_t v) { put(&v, 8); }
	void r_u8(uint8_t& v) { get(&v, 1); }
	void r_u16(uint16_t& v) { get(&v, 2); }
	void r_u64(uint64_t& v) { get(&v, 8); }
	uint32_t r_elapsed() const { return uint32_t(data.size()) - pos; }
};

static State weapon_state()
{
	State s;
	s.uid = 8172; s.condition = quantize(0.43f); s.weapon = true; s.ammo_type = 1; s.addons = 4;
	const uint8_t types[] = {0, 0, 0, 1, 1, 0};
	set_magazine(s, 6, [&](uint32_t i) { return types[i]; });
	return s;
}

int main()
{
	// Quantisation keeps 0 and 1 exact and 1/3 steps visible.
	CHECK(quantize(0.f) == 0 && quantize(1.f) == 65535 && quantize(-1.f) == 0 && quantize(2.f) == 65535);
	CHECK(quantize(0.12f) == quantize(dequantize(quantize(0.12f))));

	// Magazine runs: bottom first, equal neighbours merge.
	State w = weapon_state();
	CHECK(w.runs == 3 && w.run_type[0] == 0 && w.run_count[0] == 3 && w.run_type[1] == 1 && w.run_count[1] == 2 && w.run_count[2] == 1);
	CHECK(ammo_total(w) == 6);
	{
		State alt; alt.weapon = true;
		const bool exact = set_magazine(alt, 40, [](uint32_t i) { return uint8_t(i & 1); });
		CHECK(!exact && alt.runs == max_runs && ammo_total(alt) == 40);
	}

	// Full round trip of every field.
	{
		State a = w; a.has_uses = true; a.uses = 2; a.max_uses = 3; a.stack = true; a.stack_count = 17;
		Packet p; write(p, a, f_all);
		State b; CHECK(read(p, b, f_all)); CHECK(p.r_elapsed() == 0);
		CHECK(diff(a, b) == 0);
	}
	// Delta: only the changed field travels, the rest stays.
	{
		State before = w, after = w; after.condition = quantize(0.42f);
		const uint16_t mask = diff(before, after);
		CHECK(mask == f_condition);
		Packet p; write(p, after, mask);
		CHECK(p.data.size() == 2);
		State replica = before; CHECK(read(p, replica, mask)); CHECK(diff(replica, after) == 0);
	}
	// Malformed: truncated, unknown mask bits, impossible portions and runs.
	{
		Packet p; write(p, w, f_all & ~f_uses & ~f_stack);
		p.data.resize(p.data.size() - 1);
		State x; CHECK(!read(p, x, f_all & ~f_uses & ~f_stack));
		Packet q; State y; CHECK(!read(q, y, uint16_t(1 << 9)));
		Packet r; r.w_u8(1); r.w_u8(5); r.w_u8(3); State z; CHECK(!read(r, z, f_uses));
		Packet u; u.w_u8(1); u.w_u8(255); u.w_u8(1); State inf; CHECK(read(u, inf, f_uses) && inf.uses == 255);
		Packet m; m.w_u8(1); m.w_u8(0); m.w_u8(uint8_t(max_runs + 1)); State big; CHECK(!read(m, big, f_ammo));
		Packet zc; zc.w_u8(1); zc.w_u8(0); zc.w_u8(1); zc.w_u8(0); zc.w_u16(0); State zero; CHECK(!read(zc, zero, f_ammo));
	}

	// Version order with wrap-around: 17 after 18 is stale.
	CHECK(newer(18, 17) && !newer(17, 18) && !newer(18, 18));
	CHECK(newer(2, 65535) && !newer(65535, 2));

	// Owner report verdicts.
	CHECK(judge_condition(quantize(0.5f), quantize(0.4f)) == verdict_wear);
	CHECK(judge_condition(quantize(0.4f), quantize(0.5f)) == verdict_raise);
	CHECK(judge_condition(100, 100) == verdict_unchanged);
	{
		State shot = w; const uint8_t types[] = {0, 0, 0, 1, 1};
		set_magazine(shot, 5, [&](uint32_t i) { return types[i]; });
		CHECK(judge_ammo(w, shot, 31, 2) == verdict_wear);
		CHECK(judge_ammo(shot, w, 31, 2) == verdict_raise);
		CHECK(judge_ammo(w, w, 31, 2) == verdict_unchanged);
		CHECK(judge_ammo(w, w, 5, 2) == verdict_reject); // more rounds than the weapon holds
		CHECK(judge_ammo(w, w, 31, 1) == verdict_reject); // a type the weapon cannot load
		State not_weapon; CHECK(judge_ammo(w, not_weapon, 31, 2) == verdict_reject);
	}
	CHECK(judge_stack(30, 29, 30) == verdict_wear && judge_stack(29, 30, 30) == verdict_raise && judge_stack(29, 31, 30) == verdict_reject);

	// TEST A (model): A drains a PDA to 12 %, the server stores A's report;
	// the full snapshot on the owner change gives B exactly 12 %.
	{
		State server; server.uid = 81; server.condition = 65535;
		State a_copy = server, b_copy = server; // both spawned at 100 %
		a_copy.condition = quantize(0.12f);
		const uint16_t report = diff(server, a_copy) & f_owner_predicted;
		CHECK(report == f_condition && judge_condition(server.condition, a_copy.condition) == verdict_wear);
		merge(server, a_copy, report);
		Packet p; write(p, server, applicable(server)); // f_full snapshot to B
		CHECK(read(p, b_copy, applicable(server)));
		CHECK(b_copy.condition == quantize(0.12f) && b_copy.uid == 81);
	}
	// TEST B (model): a third of the bottle is used on the server; the
	// portions travel with the instance to the next carrier.
	{
		State bottle; bottle.uid = 5; bottle.has_uses = true; bottle.uses = 3; bottle.max_uses = 3;
		State owner = bottle, next = bottle;
		bottle.uses = 2; // GEG_PLAYER_ITEM_EAT on the server
		uint16_t mask = diff(owner, bottle);
		CHECK(mask == f_uses && !(mask & f_owner_predicted)); // not predicted: goes to the owner
		Packet p; write(p, bottle, mask); CHECK(read(p, owner, mask)); CHECK(owner.uses == 2);
		Packet s; write(s, bottle, applicable(bottle)); CHECK(read(s, next, applicable(bottle)));
		CHECK(next.uses == 2 && next.max_uses == 3);
	}
	// TEST C (model): the corpse's weapon keeps the magazine the NPC left.
	{
		State npc = weapon_state();
		const uint8_t left[] = {0, 0};
		set_magazine(npc, 2, [&](uint32_t i) { return left[i]; });
		State looter = weapon_state();
		Packet p; write(p, npc, applicable(npc)); CHECK(read(p, looter, applicable(npc)));
		CHECK(ammo_total(looter) == 2 && looter.condition == npc.condition);
	}

	if (failures) { std::printf("item state: %d failure(s)\n", failures); return 1; }
	std::printf("Item instance state model: round trips, malformed input, version order, magazines, verdicts, TEST A/B/C PASS\n");
	return 0;
}
