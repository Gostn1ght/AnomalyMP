// Included in netcoop.cpp after server_physics_update (namespace netcoop).
// Vehicles in multiplayer (owner 2026-10-12, doc 100).
//
// The server owns the car: it runs the CCar physics with the driver's keys
// (M_NETCOOP_VEHICLE input) and sends the poses on the physics channel and
// the car's state (engine, lights, rpm, steering, who sits where) here. A
// client's car is a replica (CCar::netcoop_replica_state).
//
// Seats come from the car's section (netcoop_seats = bone[:x:y:z], ...; the
// first one drives) or default to the model's driver_place, seat_right and
// seat_back. A player picks the seat by the door they look at; a taken seat
// says so. A seated player is placed at the car's pose times the seat on the
// server, on their own client and on every other client, with no character
// capsule and no own movement; the driver's keys go to the server.

enum
{
	vehicle_op_state = 1, // server -> client: u16 car, u8 flags, u8 keys, float rpm, float steer, u8 n, n x u16 actor
	vehicle_op_enter, // client -> server: u16 car, u8 seat
	vehicle_op_exit, // client -> server
	vehicle_op_input, // client -> server: u16 car, u8 keys
	vehicle_op_toggle, // client -> server: u16 car, u8 what (0 engine, 1 head lights)
	vehicle_op_trunk, // client -> server: u16 car
	vehicle_op_trunk_open, // server -> client: u16 box
};

// ---------------------------------------------------------------------------
// Boxes kept away from what they belong to (a car's trunk under the map):
// a player may move items with such a box while next to its anchor.
// ---------------------------------------------------------------------------
static xr_map<u16, u16> s_box_anchor; // box id -> anchor object id

void script_box_anchor(u16 box, u16 anchor)
{
	if (!pure_client() && box != anchor)
		s_box_anchor[box] = anchor;
}

bool box_anchor_within_reach(u16 box, const Fvector& from)
{
	auto found = s_box_anchor.find(box);
	if (found == s_box_anchor.end())
		return false;
	CObject* anchor = Level().Objects.net_Find(found->second);
	if (!anchor || anchor->getDestroy())
		return false;
	return from.distance_to(anchor->Position()) <= anchor->Radius() + 2.5f;
}
static const u16 vehicle_seat_free = 0xffff;
static const u8 vehicle_max_seats = 8;

struct VehicleSeatPose
{
	Fmatrix local; // seat root (the body's root bone) in the car's space
	Fvector eye; // the eye of a player in this seat, car's space
	bool driver;
};

struct VehicleSeats
{
	xr_vector<VehicleSeatPose> seats;
	float half_width = 1.f;
	float front_z = 0.f; // the front row of seats (aim: rear seats lie behind it)
	float rear_z = 0.f; // the back of the car
	bool trunk = true;
};
static xr_map<u16, VehicleSeats> s_vehicle_seats; // car id -> seats (server and client)

static VehicleSeats* vehicle_seats(CCar* car)
{
	if (!car || !car->Visual())
		return nullptr;
	auto found = s_vehicle_seats.find(car->ID());
	if (found != s_vehicle_seats.end())
		return found->second.seats.empty() ? nullptr : &found->second;
	VehicleSeats& v = s_vehicle_seats[car->ID()];
	IKinematics* K = smart_cast<IKinematics*>(car->Visual());
	if (!K)
		return nullptr;
	K->CalculateBones_Invalidate();
	K->CalculateBones(TRUE);
	CInifile* model = K->LL_UserData();
	LPCSTR section = car->cNameSect().c_str();
	LPCSTR driver_bone = model && model->line_exist("car_definition", "driver_place") ?
		model->r_string("car_definition", "driver_place") : "seat_left";
	string1024 list;
	if (pSettings->line_exist(section, "netcoop_seats"))
		xr_strcpy(list, pSettings->r_string(section, "netcoop_seats"));
	else
		xr_sprintf(list, "%s,seat_right,seat_back", driver_bone);
	// The passenger pose (sitting on a chair) has its root on the floor, the
	// driver's steering pose on the seat itself.
	const float drop = READ_IF_EXISTS(pSettings, r_float, section, "netcoop_passenger_drop", 0.45f);
	// Eye: the single-player driver camera relative to the driver's seat.
	Fvector eye_offset;
	eye_offset.set(0.f, 0.65f, 0.05f);
	const u16 driver_id = K->LL_BoneID(driver_bone);
	if (driver_id != BI_NONE)
	{
		Fvector offset;
		offset.sub(car->netcoop_camera_position(), K->LL_GetTransform(driver_id).c);
		if (offset.y > 0.3f && offset.y < 1.2f && offset.magnitude() < 1.5f)
			eye_offset.set(offset);
	}
	const u32 count = _GetItemCount(list);
	for (u32 i = 0; i < count && v.seats.size() < vehicle_max_seats; ++i)
	{
		string128 item;
		_GetItem(list, i, item);
		// bone[:x:y:z]: an offset in the car's space from that bone.
		string128 bone_name;
		Fvector offset;
		offset.set(0.f, 0.f, 0.f);
		_GetItem(item, 0, bone_name, ':');
		if (_GetItemCount(item, ':') == 4)
		{
			string32 value;
			offset.x = float(atof(_GetItem(item, 1, value, ':')));
			offset.y = float(atof(_GetItem(item, 2, value, ':')));
			offset.z = float(atof(_GetItem(item, 3, value, ':')));
		}
		const u16 bone = K->LL_BoneID(_Trim(bone_name));
		if (bone == BI_NONE)
			continue;
		VehicleSeatPose seat;
		seat.local.set(K->LL_GetTransform(bone));
		seat.local.c.add(offset);
		seat.driver = v.seats.empty();
		seat.eye.add(seat.local.c, eye_offset);
		if (!seat.driver)
			seat.local.c.y -= drop;
		v.seats.push_back(seat);
	}
	if (v.seats.empty())
	{
		Msg("! [Lost Zone][vehicle] %s (%s) has no seats", car->cName().c_str(), section);
		return nullptr;
	}
	const Fbox& box = car->Visual()->getVisData().box;
	v.half_width = _max(_abs(box.min.x), _abs(box.max.x));
	v.rear_z = box.min.z;
	v.front_z = v.seats[0].local.c.z;
	v.trunk = !!READ_IF_EXISTS(pSettings, r_bool, section, "netcoop_trunk", TRUE);
	return &v;
}

// Out of the seat's side of the car, on the ground.
static Fvector vehicle_exit_position(CCar* car, const VehicleSeats& v, const VehicleSeatPose& seat)
{
	Fvector local = seat.local.c;
	local.x = (local.x < 0.f ? -1.f : 1.f) * (v.half_width + 0.7f);
	local.y = seat.local.c.y + 0.5f;
	Fvector world;
	car->XFORM().transform_tiny(world, local);
	collide::rq_result hit;
	Fvector start = world, down;
	start.y += 1.5f;
	down.set(0.f, -1.f, 0.f);
	if (Level().ObjectSpace.RayPick(start, down, 8.f, collide::rqtStatic, hit, car))
		world.y = start.y - hit.range + 0.05f;
	return world;
}

// Which seat the aim point (car's space) asks for: the nearest seat on that
// side; behind the rear seats the trunk (-2); -1 nothing.
static int vehicle_aim(const VehicleSeats& v, const Fvector& local)
{
	float rearmost = v.front_z;
	for (const VehicleSeatPose& seat : v.seats)
		rearmost = _min(rearmost, seat.local.c.z);
	if (v.trunk && local.z < rearmost - 0.7f)
		return -2;
	int best = -1;
	float best_distance = flt_max;
	for (u32 i = 0; i < v.seats.size(); ++i)
	{
		const Fvector& p = v.seats[i].local.c;
		const float distance = _sqr(p.x - local.x) + _sqr(p.z - local.z);
		if (distance < best_distance)
		{
			best_distance = distance;
			best = int(i);
		}
	}
	return best;
}

// ---------------------------------------------------------------------------
// server
// ---------------------------------------------------------------------------
struct VehicleRuntime
{
	xr_vector<u16> seats;
	u8 keys = 0;
	u32 keys_time = 0;
	u32 sent = 0;
	bool dirty = true;
	u32 transit_check = 0; // driving into a passage (V6)
	u32 transit_refused = 0;
};
static xr_map<u16, VehicleRuntime> s_vehicles_sv;

static void vehicle_seat_server(CCar* car, VehicleRuntime& v, const VehicleSeats& poses, u8 index, CActor* actor)
{
	const VehicleSeatPose& seat = poses.seats[index];
	v.seats[index] = actor->ID();
	v.dirty = true;
	actor->netcoop_seat_enter(car->ID(), index, seat.driver, seat.local, seat.eye);
	if (seat.driver)
		car->netcoop_engage(true);
	Msg("[Lost Zone][vehicle] %s sits in %s (%u), seat %u%s", actor->cName().c_str(), car->cName().c_str(), car->ID(),
		index, seat.driver ? ", driving" : "");
}

static void vehicle_unseat_server(CCar* car, VehicleRuntime& v, u8 index)
{
	CActor* actor = smart_cast<CActor*>(Level().Objects.net_Find(v.seats[index]));
	const VehicleSeats* poses = car ? vehicle_seats(car) : nullptr;
	if (actor && actor->netcoop_seated())
	{
		const Fvector exit = car && poses && index < poses->seats.size() ?
			vehicle_exit_position(car, *poses, poses->seats[index]) : actor->Position();
		actor->netcoop_seat_leave(exit);
		Msg("[Lost Zone][vehicle] %s leaves seat %u", actor->cName().c_str(), index);
	}
	if (car && poses && index < poses->seats.size() && poses->seats[index].driver)
	{
		car->netcoop_engage(false);
		v.keys = 0;
	}
	v.seats[index] = vehicle_seat_free;
	v.dirty = true;
}

static VehicleRuntime* vehicle_runtime(CCar* car, const VehicleSeats& poses)
{
	VehicleRuntime& v = s_vehicles_sv[car->ID()];
	if (v.seats.size() != poses.seats.size())
		v.seats.assign(poses.seats.size(), vehicle_seat_free);
	return &v;
}

void server_on_vehicle(xrServer* server, xrClientData* CL, NET_Packet& P)
{
	if (!g_pGameLevel || pure_client() || !CL->owner || P.r_elapsed() < 1)
		return;
	CActor* actor = smart_cast<CActor*>(Level().Objects.net_Find(CL->owner->ID));
	if (!actor || !actor->g_Alive())
		return;
	const u8 op = P.r_u8();
	if (op == vehicle_op_exit)
	{
		if (!actor->netcoop_seated())
			return;
		auto it = s_vehicles_sv.find(actor->m_netcoop_seat_car);
		if (it == s_vehicles_sv.end())
			return;
		for (u8 i = 0; i < it->second.seats.size(); ++i)
			if (it->second.seats[i] == actor->ID())
				vehicle_unseat_server(smart_cast<CCar*>(Level().Objects.net_Find(it->first)), it->second, i);
		return;
	}
	if (P.r_elapsed() < 2)
		return;
	const u16 car_id = P.r_u16();
	// enter, input and toggle carry one more byte
	if (op != vehicle_op_trunk && P.r_elapsed() < 1)
		return;
	CCar* car = smart_cast<CCar*>(Level().Objects.net_Find(car_id));
	if (!car || car->getDestroy() || car->netcoop_destroyed())
		return;
	VehicleSeats* poses = vehicle_seats(car);
	if (!poses)
		return;
	VehicleRuntime& v = *vehicle_runtime(car, *poses);
	const u32 now = Level().timeServer();
	switch (op)
	{
	case vehicle_op_enter:
		{
			const u8 seat = P.r_u8();
			if (actor->netcoop_seated() || seat >= v.seats.size() || v.seats[seat] != vehicle_seat_free)
			{
				v.dirty = true; // the client learns who sits there
				return;
			}
			// Next to the car: its size plus an arm's length.
			if (actor->Position().distance_to(car->Position()) > car->Radius() + 2.5f)
				return;
			vehicle_seat_server(car, v, *poses, seat, actor);
		}
		break;
	case vehicle_op_input:
		{
			const u8 keys = P.r_u8() & 31;
			if (v.seats.empty() || v.seats[0] != actor->ID())
				return;
			v.keys_time = now;
			if (keys != v.keys)
			{
				car->netcoop_drive(keys);
				v.keys = keys;
				v.dirty = true;
			}
		}
		break;
	case vehicle_op_toggle:
		{
			const u8 what = P.r_u8();
			if (v.seats.empty() || v.seats[0] != actor->ID() || what > 1)
				return;
			car->netcoop_toggle(what);
			v.dirty = true;
		}
		break;
	case vehicle_op_trunk:
		{
			// From outside, next to the car. The trunk is a hidden box the
			// server Lua keeps for the car (netcoop_vehicles.trunk_box).
			if (actor->netcoop_seated() || !poses->trunk ||
				actor->Position().distance_to(car->Position()) > car->Radius() + 2.5f)
				return;
			::luabind::functor<int> trunk_box;
			int box = 0;
			if (ai().script_engine().functor("netcoop_vehicles.trunk_box", trunk_box))
			{
				try { box = trunk_box(int(car->ID())); }
				catch (...) { Msg("! [Lost Zone][vehicle] trunk_box failed"); }
			}
			if (box <= 0 || box >= 0xffff)
				return;
			NET_Packet answer;
			answer.w_begin(M_NETCOOP_VEHICLE);
			answer.w_u8(vehicle_op_trunk_open);
			answer.w_u16(u16(box));
			server->SendTo(CL->ID, answer, net_flags(TRUE, TRUE));
		}
		break;
	}
}

static void vehicle_send_state(xrServer* server, CCar* car, const VehicleRuntime& v, bool reliable)
{
	NET_Packet P;
	P.w_begin(M_NETCOOP_VEHICLE);
	P.w_u8(vehicle_op_state);
	P.w_u16(car->ID());
	P.w_u8(u8((car->netcoop_engine_on() ? 1 : 0) | (car->m_netcoop_lights ? 2 : 0)));
	P.w_u8(v.keys);
	P.w_float(car->netcoop_rpm());
	P.w_float(car->netcoop_steer());
	P.w_u8(u8(v.seats.size()));
	for (u16 id : v.seats)
		P.w_u16(id);
	struct Send
	{
		xrServer* server;
		NET_Packet* packet;
		Fvector position;
		bool reliable;
		void operator()(IClient* client)
		{
			xrClientData* CL = static_cast<xrClientData*>(client);
			if (CL == server->GetServerClient() || !CL->flags.bConnected || !CL->gamma_snapshot_ready || !CL->owner)
				return;
			if (CL->owner->o_Position.distance_to(position) > 500.f)
				return;
			server->SendTo(CL->ID, *packet, net_flags(reliable ? TRUE : FALSE, TRUE));
		}
	} send = {server, &P, car->Position(), reliable};
	server->ForEachClientDo(send);
}

// ---------------------------------------------------------------------------
// Through a passage with the passengers (doc 100, V6)
// ---------------------------------------------------------------------------
// The driver takes the car into a level changer: the car (with its trunk, the
// Lua record of netcoop_vehicles.capture) goes to the cluster folder as
// car_<target map>_*.txt, everybody in it goes through the passage the
// player's way (cluster_move), and the car leaves this map. The target map's
// server picks the file up, puts the car down at the arrival point and seats
// each player in their seat as they arrive.
struct VehicleArrival
{
	xr_string login; // lower case
	u8 slot = 1;
	u16 car = 0xffff;
	u8 seat = 0;
	u32 until = 0;
};
static xr_vector<VehicleArrival> s_vehicle_arrivals;
struct VehicleCondition { u16 car; float health; float fuel; u32 until; };
static xr_vector<VehicleCondition> s_vehicle_conditions; // applied once the car is online
static u32 s_vehicle_inbox_check = 0;

static xrClientData* vehicle_client_of(xrServer* server, u16 actor_id)
{
	struct Find
	{
		u16 id;
		xrClientData* found;
		void operator()(IClient* client)
		{
			xrClientData* CL = static_cast<xrClientData*>(client);
			if (!found && CL && CL->owner && CL->owner->ID == id && CL->netcoop_login.size()) found = CL;
		}
	} find = {actor_id, nullptr};
	server->ForEachClientDo(find);
	return find.found;
}

static bool vehicle_write_file(LPCSTR path, const xr_string& text)
{
	string_path temp;
	xr_sprintf(temp, "%s.%u.tmp", path, GetCurrentProcessId());
	FILE* f = fopen(temp, "wb");
	if (!f) return false;
	const bool ok = fwrite(text.data(), 1, text.size(), f) == text.size() && fflush(f) == 0 && _commit(_fileno(f)) == 0;
	fclose(f);
	if (ok && MoveFileExA(temp, path, MOVEFILE_REPLACE_EXISTING | MOVEFILE_WRITE_THROUGH)) return true;
	DeleteFileA(temp);
	return false;
}

static void vehicle_transit(xrServer* server, CCar* car, VehicleRuntime& v, CLevelChanger* changer, CActor* driver)
{
	const u32 now = Level().timeServer();
	xrClientData* driver_client = vehicle_client_of(server, driver->ID());
	v.transit_refused = now + 5000; // one try per 5 s, and none while this one runs
	auto refuse = [&](LPCSTR text)
	{
		if (driver_client) cluster_refuse(server, driver_client, text);
	};
	if (!changer->IsLevelChangerEnabled()) return refuse("this passage is closed");
	const GameGraph::_GRAPH_ID game_vertex = changer->next_game_vertex();
	if (!ai().game_graph().valid_vertex_id(game_vertex)) return;
	const LPCSTR level = *ai().game_graph().header().level(ai().game_graph().vertex(game_vertex)->level_id()).name();
	xr_string host;
	u32 port = 0;
	if (!xr_strcmp(level, cluster_current_level()) || !cluster_location(level, host, port) || port == cluster_port())
		return refuse("no server runs that map yet");
	if (LPCSTR problem = cluster_target_problem(port))
		if (problem[0])
		{
			if (strstr(problem, "offline") && cluster_on_demand(level))
			{
				cluster_wake(level);
				return refuse("the server of that map is starting");
			}
			return refuse(problem);
		}
	// Everybody aboard must be able to go now.
	string1024 seats = "";
	for (u8 i = 0; i < v.seats.size(); ++i)
	{
		if (v.seats[i] == vehicle_seat_free) continue;
		xrClientData* CL = vehicle_client_of(server, v.seats[i]);
		if (!CL || s_character_restore.find(v.seats[i]) != s_character_restore.end())
			return refuse("the character is still loading");
		string128 entry;
		xr_sprintf(entry, "%s%s:%u:%u", seats[0] ? "," : "", CL->netcoop_login.c_str(), CL->netcoop_character_slot, i);
		xr_strcat(seats, entry);
	}
	::luabind::functor<LPCSTR> capture;
	xr_string record;
	if (ai().script_engine().functor("netcoop_vehicles.capture", capture))
	{
		try { LPCSTR text = capture(int(car->ID())); record = text ? text : ""; }
		catch (...) { record.clear(); }
	}
	if (record.empty())
		return refuse("the car could not be saved");
	// The car comes down a few metres past the arrival point.
	Fvector arrival = changer->next_position(), ahead;
	ahead.setHP(changer->next_angles().y, 0.f);
	arrival.mad(ahead, 5.f);
	arrival.y += 0.5f;
	xr_string text = "lostzone-car 1\n";
	string512 line;
	xr_sprintf(line, "%s\n%.3f %.3f %.3f %u %.4f %.4f\n%s\n", level, arrival.x, arrival.y, arrival.z, u32(game_vertex),
		car->GetfHealth(), car->netcoop_fuel(), seats);
	text += line;
	text += record;
	string_path dir, path;
	cluster_dir(dir);
	xr_sprintf(path, "%scar_%s_%llu_%u.txt", dir, level, cluster_unix_ms(), car->ID());
	if (!vehicle_write_file(path, text))
		return refuse("the car could not be saved");
	Msg("[Lost Zone][vehicle] %s (%u) leaves for %s with %s", car->cName().c_str(), car->ID(), level, seats);
	for (u8 i = 0; i < v.seats.size(); ++i)
	{
		if (v.seats[i] == vehicle_seat_free) continue;
		const u16 actor_id = v.seats[i];
		vehicle_unseat_server(car, v, i);
		if (xrClientData* CL = vehicle_client_of(server, actor_id))
			cluster_move(server, CL, changer);
	}
	::luabind::functor<void> release;
	if (ai().script_engine().functor("netcoop_vehicles.release", release))
	{
		try { release(int(car->ID())); }
		catch (...) { Msg("! [Lost Zone][vehicle] release failed"); }
	}
}

// The target map: cars that came through a passage.
static void vehicle_inbox(xrServer* server)
{
	string_path dir, pattern;
	cluster_dir(dir);
	xr_sprintf(pattern, "%scar_%s_*.txt", dir, cluster_current_level());
	WIN32_FIND_DATAA found;
	HANDLE search = FindFirstFileA(pattern, &found);
	if (search == INVALID_HANDLE_VALUE) return;
	xr_vector<xr_string> names;
	do names.push_back(found.cFileName); while (FindNextFileA(search, &found));
	FindClose(search);
	for (const xr_string& name : names)
	{
		string_path path, claimed;
		xr_sprintf(path, "%s%s", dir, name.c_str());
		xr_sprintf(claimed, "%s.claim%u", path, GetCurrentProcessId());
		if (!MoveFileA(path, claimed)) continue; // another server took it
		xr_string text;
		if (FILE* f = fopen(claimed, "rb"))
		{
			char buffer[4096];
			size_t n;
			while ((n = fread(buffer, 1, sizeof(buffer), f)) > 0 && text.size() < 4 * 1024 * 1024) text.append(buffer, n);
			fclose(f);
		}
		// lostzone-car 1 / level / x y z gv health fuel / seats / record
		size_t lines[4] = {};
		size_t at = 0;
		bool ok = true;
		for (int i = 0; i < 4 && ok; ++i)
		{
			at = text.find('\n', at);
			ok = at != xr_string::npos;
			if (ok) lines[i] = at++;
		}
		float x = 0, y = 0, z = 0, health = 1, fuel = 0;
		unsigned gv = 0;
		ok = ok && !text.compare(0, 14, "lostzone-car 1") &&
			sscanf(text.c_str() + lines[1] + 1, "%f %f %f %u %f %f", &x, &y, &z, &gv, &health, &fuel) == 6;
		int car_id = 0;
		if (ok)
		{
			::luabind::functor<int> restore;
			if (ai().script_engine().functor("netcoop_vehicles.restore", restore))
			{
				try { car_id = restore(text.c_str() + lines[3] + 1, x, y, z, int(gv)); }
				catch (...) { car_id = 0; }
			}
		}
		if (car_id <= 0 || car_id >= 0xffff)
		{
			string_path failed;
			xr_sprintf(failed, "%s.failed", path);
			MoveFileA(claimed, failed);
			Msg("! [Lost Zone][vehicle] a car from %s could not be put down", name.c_str());
			continue;
		}
		const xr_string seats = text.substr(lines[2] + 1, lines[3] - lines[2] - 1);
		for (u32 i = 0, count = _GetItemCount(seats.c_str()); i < count; ++i)
		{
			string128 item, login, value;
			_GetItem(seats.c_str(), i, item);
			if (_GetItemCount(item, ':') != 3) continue;
			VehicleArrival arrival;
			arrival.login = _GetItem(item, 0, login, ':');
			to_lower(arrival.login);
			arrival.slot = u8(atoi(_GetItem(item, 1, value, ':')));
			arrival.seat = u8(atoi(_GetItem(item, 2, value, ':')));
			arrival.car = u16(car_id);
			arrival.until = Level().timeServer() + 180000;
			s_vehicle_arrivals.push_back(arrival);
		}
		VehicleCondition condition = {u16(car_id), health, fuel, Level().timeServer() + 60000};
		s_vehicle_conditions.push_back(condition);
		DeleteFileA(claimed);
		Msg("[Lost Zone][vehicle] a car arrived (%u) for %s", car_id, seats.c_str());
	}
}

static void vehicle_arrivals(xrServer* server)
{
	const u32 now = Level().timeServer();
	for (auto it = s_vehicle_conditions.begin(); it != s_vehicle_conditions.end();)
	{
		CCar* car = smart_cast<CCar*>(Level().Objects.net_Find(it->car));
		if (car)
		{
			car->SetfHealth(it->health);
			car->netcoop_set_fuel(it->fuel);
		}
		if (car || now > it->until) it = s_vehicle_conditions.erase(it);
		else ++it;
	}
	for (auto it = s_vehicle_arrivals.begin(); it != s_vehicle_arrivals.end();)
	{
		if (now > it->until) { it = s_vehicle_arrivals.erase(it); continue; }
		struct Find
		{
			const VehicleArrival* arrival;
			xrClientData* found;
			void operator()(IClient* client)
			{
				xrClientData* CL = static_cast<xrClientData*>(client);
				if (found || !CL || !CL->owner || !CL->netcoop_login.size() || CL->netcoop_character_slot != arrival->slot) return;
				xr_string name = CL->netcoop_login.c_str();
				to_lower(name);
				if (name == arrival->login) found = CL;
			}
		} find = {&*it, nullptr};
		server->ForEachClientDo(find);
		CCar* car = smart_cast<CCar*>(Level().Objects.net_Find(it->car));
		CActor* actor = find.found ? smart_cast<CActor*>(Level().Objects.net_Find(find.found->owner->ID)) : nullptr;
		const VehicleSeats* poses = car ? vehicle_seats(car) : nullptr;
		if (!actor || !actor->g_Alive() || !poses || s_character_restore.find(actor->ID()) != s_character_restore.end())
		{
			++it;
			continue;
		}
		VehicleRuntime& v = *vehicle_runtime(car, *poses);
		if (!actor->netcoop_seated() && it->seat < v.seats.size() && v.seats[it->seat] == vehicle_seat_free)
			vehicle_seat_server(car, v, *poses, it->seat, actor);
		it = s_vehicle_arrivals.erase(it);
	}
}

// Every server frame: seated players follow their seats, drivers that went
// silent stop, and the state goes out (10 Hz while used, 0.5 Hz parked).
void vehicle_server_update(xrServer* server)
{
	if (!g_pGameLevel || pure_client())
		return;
	const u32 now = Level().timeServer();
	if (cluster_config_present() && now - s_vehicle_inbox_check >= 2000)
	{
		s_vehicle_inbox_check = now;
		vehicle_inbox(server);
	}
	if (!s_vehicle_arrivals.empty() || !s_vehicle_conditions.empty())
		vehicle_arrivals(server);
	if (s_vehicles_sv.empty())
		return;
	for (auto it = s_vehicles_sv.begin(); it != s_vehicles_sv.end();)
	{
		VehicleRuntime& v = it->second;
		CCar* car = smart_cast<CCar*>(Level().Objects.net_Find(it->first));
		const bool usable = car && !car->getDestroy() && !car->netcoop_destroyed() && vehicle_seats(car);
		bool occupied = false;
		for (u8 i = 0; i < v.seats.size(); ++i)
		{
			if (v.seats[i] == vehicle_seat_free)
				continue;
			CActor* actor = smart_cast<CActor*>(Level().Objects.net_Find(v.seats[i]));
			if (!usable || !actor || !actor->g_Alive() || actor->getDestroy() || actor->m_netcoop_seat_car != it->first)
			{
				vehicle_unseat_server(usable ? car : nullptr, v, i);
				continue;
			}
			actor->netcoop_seat_place();
			occupied = true;
		}
		if (!usable)
		{
			s_vehicle_seats.erase(it->first);
			it = s_vehicles_sv.erase(it);
			continue;
		}
		// The driver takes the car into a passage.
		if (!v.seats.empty() && v.seats[0] != vehicle_seat_free && now - v.transit_check >= 250 && now >= v.transit_refused)
		{
			v.transit_check = now;
			if (CActor* driver = smart_cast<CActor*>(Level().Objects.net_Find(v.seats[0])))
				for (CLevelChanger* changer : g_lchangers)
					if (changer->feel_touch_contact(driver))
					{
						vehicle_transit(server, car, v, changer, driver);
						break;
					}
		}
		// A driver whose client stopped sending lets go of the pedals.
		if (v.keys && now - v.keys_time > 2000)
		{
			car->netcoop_drive(0);
			v.keys = 0;
			v.dirty = true;
		}
		const u32 period = occupied || car->netcoop_engine_on() ? 100u : 2000u;
		if (v.dirty || now - v.sent >= period)
		{
			vehicle_send_state(server, car, v, v.dirty);
			v.sent = now;
			v.dirty = false;
		}
		++it;
	}
}

// ---------------------------------------------------------------------------
// client
// ---------------------------------------------------------------------------
static xr_map<u16, xr_vector<u16>> s_vehicles_cl; // car id -> seat occupants
static u8 s_vehicle_keys = 0;
static u32 s_vehicle_keys_sent = 0;

static void vehicle_send(u8 op, u16 car, int value)
{
	NET_Packet P;
	P.w_begin(M_NETCOOP_VEHICLE);
	P.w_u8(op);
	if (op != vehicle_op_exit)
	{
		P.w_u16(car);
		if (value >= 0)
			P.w_u8(u8(value));
	}
	Level().Send(P, net_flags(TRUE, TRUE));
}

static u16 s_trunk_pending = 0xffff;
static u32 s_trunk_pending_until = 0;

void client_on_vehicle(NET_Packet& P)
{
	if (!pure_client() || P.r_elapsed() < 1)
		return;
	const u8 op = P.r_u8();
	if (op == vehicle_op_trunk_open && P.r_elapsed() == 2)
	{
		// A new box arrives a moment later: opened by script_vehicle_prompt.
		s_trunk_pending = P.r_u16();
		s_trunk_pending_until = Device.dwTimeGlobal + 3000;
		return;
	}
	if (op != vehicle_op_state || P.r_elapsed() < 13)
		return;
	const u16 car_id = P.r_u16();
	const u8 flags = P.r_u8();
	const u8 keys = P.r_u8();
	const float rpm = P.r_float();
	const float steer = P.r_float();
	const u8 count = P.r_u8();
	if (count > vehicle_max_seats || P.r_elapsed() != u32(count) * 2 || !_valid(rpm) || !_valid(steer))
		return;
	xr_vector<u16> seats(count);
	for (u16& id : seats)
		id = P.r_u16();
	CCar* car = smart_cast<CCar*>(Level().Objects.net_Find(car_id));
	if (!car)
		return; // it comes again while the car is in use
	car->netcoop_replica_state(!!(flags & 1), !!(flags & 2), rpm, steer);
	car->m_netcoop_keys = keys; // the driver's steering animation
	const VehicleSeats* poses = vehicle_seats(car);
	if (!poses)
		return;
	xr_vector<u16>& known = s_vehicles_cl[car_id];
	for (u32 i = 0; i < known.size(); ++i)
	{
		if (known[i] == vehicle_seat_free || std::find(seats.begin(), seats.end(), known[i]) != seats.end())
			continue;
		CActor* actor = smart_cast<CActor*>(Level().Objects.net_Find(known[i]));
		if (actor && actor->m_netcoop_seat_car == car_id && i < poses->seats.size())
			actor->netcoop_seat_leave(vehicle_exit_position(car, *poses, poses->seats[i]));
	}
	for (u32 i = 0; i < seats.size() && i < poses->seats.size(); ++i)
	{
		if (seats[i] == vehicle_seat_free)
			continue;
		CActor* actor = smart_cast<CActor*>(Level().Objects.net_Find(seats[i]));
		if (actor && (actor->m_netcoop_seat_car != car_id || actor->m_netcoop_seat != i))
			actor->netcoop_seat_enter(car_id, u8(i), poses->seats[i].driver, poses->seats[i].local, poses->seats[i].eye);
	}
	known = seats;
	if (Level().CurrentControlEntity())
		if (CActor* self = smart_cast<CActor*>(Level().CurrentControlEntity()))
			if (!self->netcoop_seated() || !self->m_netcoop_seat_driver)
				s_vehicle_keys = 0;
}

// F on a car: the seat behind the door the player looks at, or the trunk.
bool vehicle_use(CActor* actor, CObject* object, const Fvector& aim)
{
	CCar* car = smart_cast<CCar*>(object);
	if (!car || !enabled())
		return false;
	if (!pure_client() || car->netcoop_destroyed())
		return true;
	const VehicleSeats* poses = vehicle_seats(car);
	if (!poses)
		return true;
	Fmatrix inverse;
	inverse.invert(car->XFORM());
	Fvector local;
	inverse.transform_tiny(local, aim);
	const int seat = vehicle_aim(*poses, local);
	if (seat == -2)
	{
		vehicle_send(vehicle_op_trunk, car->ID(), -1);
		return true;
	}
	if (seat < 0)
		return true;
	auto known = s_vehicles_cl.find(car->ID());
	if (known != s_vehicles_cl.end() && u32(seat) < known->second.size() && known->second[seat] != vehicle_seat_free)
	{
		client_on_server_text(*CStringTable().translate("st_netcoop_seat_taken"));
		return true;
	}
	vehicle_send(vehicle_op_enter, car->ID(), seat);
	return true;
}

// Keys of a seated player: the driver's pedals and wheel go to the server,
// F gets out, the camera keys switch the view; everything else waits.
void vehicle_key(CActor* actor, int cmd, bool pressed)
{
	if (!pure_client() || !actor->netcoop_seated())
		return;
	u8 bit = 0;
	switch (cmd)
	{
	case kFWD: bit = CCar::netcoop_key_forward; break;
	case kBACK: bit = CCar::netcoop_key_back; break;
	case kL_STRAFE: bit = CCar::netcoop_key_left; break;
	case kR_STRAFE: bit = CCar::netcoop_key_right; break;
	case kJUMP: bit = CCar::netcoop_key_handbrake; break;
	}
	if (bit)
	{
		if (!actor->m_netcoop_seat_driver)
			return;
		const u8 keys = pressed ? u8(s_vehicle_keys | bit) : u8(s_vehicle_keys & ~bit);
		if (keys != s_vehicle_keys)
		{
			s_vehicle_keys = keys;
			s_vehicle_keys_sent = Device.dwTimeGlobal;
			vehicle_send(vehicle_op_input, actor->m_netcoop_seat_car, keys);
		}
		return;
	}
	if (!pressed)
		return;
	switch (cmd)
	{
	case kUSE:
		s_vehicle_keys = 0;
		vehicle_send(vehicle_op_exit, 0, -1);
		break;
	case kTORCH:
		if (actor->m_netcoop_seat_driver) vehicle_send(vehicle_op_toggle, actor->m_netcoop_seat_car, 1);
		break;
	case kDETECTOR:
		if (actor->m_netcoop_seat_driver) vehicle_send(vehicle_op_toggle, actor->m_netcoop_seat_car, 0);
		break;
	case kCAM_1: actor->cam_Set(eacFirstEye); break;
	case kCAM_2: actor->cam_Set(eacLookAt); break;

	}
}

// Lua (netcoop_vehicle_client, 10 Hz): what F would do at the car under the
// crosshair - "driver", "passenger", "taken", "trunk" - or "seated_driver" /
// "seated" in a car; "" otherwise. Also opens a trunk the server granted.
LPCSTR script_vehicle_prompt()
{
	if (!pure_client() || !g_pGameLevel)
		return "";
	CActor* actor = smart_cast<CActor*>(Level().CurrentControlEntity());
	if (!actor || !actor->g_Alive())
		return "";
	if (s_trunk_pending != 0xffff)
	{
		if (CInventoryBox* box = smart_cast<CInventoryBox*>(Level().Objects.net_Find(s_trunk_pending)))
		{
			s_trunk_pending = 0xffff;
			if (CUIGameSP* game = smart_cast<CUIGameSP*>(CurrentGameUI()))
				game->StartCarBody(actor, box);
		}
		else if (Device.dwTimeGlobal > s_trunk_pending_until)
			s_trunk_pending = 0xffff;
	}
	if (actor->netcoop_seated())
		return actor->m_netcoop_seat_driver ? "seated_driver" : "seated";
	collide::rq_result& RQ = HUD().GetRQ();
	CCar* car = smart_cast<CCar*>(RQ.O);
	if (!car || RQ.range >= 3.5f || car->netcoop_destroyed())
		return "";
	const VehicleSeats* poses = vehicle_seats(car);
	if (!poses)
		return "";
	Fvector aim, local;
	aim.mad(Device.vCameraPosition, Device.vCameraDirection, RQ.range);
	Fmatrix inverse;
	inverse.invert(car->XFORM());
	inverse.transform_tiny(local, aim);
	const int seat = vehicle_aim(*poses, local);
	if (seat == -2)
		return "trunk";
	if (seat < 0)
		return "";
	auto known = s_vehicles_cl.find(car->ID());
	if (known != s_vehicles_cl.end() && u32(seat) < known->second.size() && known->second[seat] != vehicle_seat_free)
		return "taken";
	return poses->seats[seat].driver ? "driver" : "passenger";
}

// Held pedals are repeated: the server lets go after 2 s of silence.
void vehicle_input_tick(CActor* actor)
{
	if (!actor->m_netcoop_seat_driver || !s_vehicle_keys)
		return;
	if (Device.dwTimeGlobal - s_vehicle_keys_sent >= 400)
	{
		s_vehicle_keys_sent = Device.dwTimeGlobal;
		vehicle_send(vehicle_op_input, actor->m_netcoop_seat_car, s_vehicle_keys);
	}
}
} // namespace netcoop

// ---------------------------------------------------------------------------
// CActor: sitting in a vehicle (all sides)
// ---------------------------------------------------------------------------
void CActor::netcoop_seat_enter(u16 car, u8 seat, bool driver, const Fmatrix& local, const Fvector& eye)
{
	const bool was_seated = netcoop_seated();
	m_netcoop_seat_car = car;
	m_netcoop_seat = seat;
	m_netcoop_seat_driver = driver;
	m_netcoop_seat_local.set(local);
	m_netcoop_seat_eye.set(eye);
	m_netcoop_seat_yaw_valid = false;
	m_netcoop_seat_motion.invalidate();
	if (!was_seated)
	{
		CPHMovementControl* movement = character_physics_support() ? character_physics_support()->movement() : nullptr;
		m_netcoop_seat_character = movement && movement->CharacterExist();
		if (m_netcoop_seat_character)
			movement->DestroyCharacter();
		mstate_wishful = 0;
		if (this == Level().CurrentControlEntity())
			SetWeaponHideState(INV_STATE_BLOCK_ALL, true);
		m_current_legs.invalidate();
		m_current_torso.invalidate();
	}
	netcoop_seat_place();
}

void CActor::netcoop_seat_leave(const Fvector& exit)
{
	if (!netcoop_seated())
		return;
	m_netcoop_seat_car = 0xffff;
	m_netcoop_seat_driver = false;
	m_netcoop_seat_motion.invalidate();
	if (this == Level().CurrentControlEntity())
	{
		SetWeaponHideState(INV_STATE_BLOCK_ALL, false);
		m_client_prediction_history.clear();
	}
	CPHMovementControl* movement = character_physics_support() ? character_physics_support()->movement() : nullptr;
	if (movement && m_netcoop_seat_character && !movement->CharacterExist())
	{
		movement->CreateCharacter();
		movement->SetPosition(exit);
		movement->SetVelocity(0.f, 0.f, 0.f);
	}
	m_netcoop_seat_character = false;
	// Upright again, facing where the car faced.
	Fvector xyz;
	XFORM().getXYZi(xyz);
	XFORM().setXYZi(0.f, xyz.y, 0.f);
	Position().set(exit);
	m_current_legs.invalidate();
	m_current_torso.invalidate();
}

void CActor::netcoop_seat_place()
{
	CCar* car = smart_cast<CCar*>(Level().Objects.net_Find(m_netcoop_seat_car));
	if (!car)
		return;
	Fmatrix world;
	world.mul_43(car->XFORM(), m_netcoop_seat_local);
	XFORM().set(world);
	car->XFORM().transform_tiny(m_netcoop_seat_eye_world, m_netcoop_seat_eye);
	if (netcoop::pure_client() && this == Level().CurrentControlEntity())
	{
		// The view turns with the car.
		Fvector xyz;
		car->XFORM().getXYZi(xyz);
		if (m_netcoop_seat_yaw_valid)
		{
			const float delta = angle_difference_signed(xyz.y, m_netcoop_seat_car_yaw);
			for (int i = 0; i < eacMaxCam; ++i)
				if (cameras[i])
					cameras[i]->yaw += delta;
		}
		m_netcoop_seat_car_yaw = xyz.y;
		m_netcoop_seat_yaw_valid = true;
		netcoop::vehicle_input_tick(this);
	}
	spatial_move();
}

bool CActor::netcoop_seat_animation()
{
	IKinematicsAnimated* k = smart_cast<IKinematicsAnimated*>(Visual());
	if (!k)
		return false;
	MotionID motion;
	if (m_netcoop_seat_driver)
	{
		CCar* car = smart_cast<CCar*>(Level().Objects.net_Find(m_netcoop_seat_car));
		u16 type = car ? car->DriverAnimationType() : 0;
		if (type >= SActorVehicleAnims::TYPES_NUMBER)
			type = 0;
		SVehicleAnimCollection& anims = m_vehicle_anims->m_vehicles_type_collections[type];
		const u8 keys = car ? car->m_netcoop_keys : 0;
		const bool left = !!(keys & CCar::netcoop_key_left), right = !!(keys & CCar::netcoop_key_right);
		motion = left && !right ? anims.steer_left : right && !left ? anims.steer_right : anims.idles[0];
	}
	else
		motion = k->ID_Cycle_Safe("animpoint_sit_high_idle_1");
	if (!motion.valid())
		return false;
	if (motion != m_netcoop_seat_motion)
	{
		k->PlayCycle(motion, FALSE);
		m_netcoop_seat_motion = motion;
	}
	return true;
}

namespace netcoop
{
