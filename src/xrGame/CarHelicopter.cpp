// Lost Zone (owner 2026-10-20, doc 151): helicopters apart from cars. A car
// section with netcoop_heli = true flies; the flight, rotors and crash are
// here, the ground vehicle stays in Car.cpp.
#include "stdafx.h"
#include "car.h"
#include "ParticlesObject.h"
#include "PHDestroyable.h"
#include "cameralook.h"
#include "camerafirsteye.h"
#include "Actor.h"
#include "ActorEffector.h"
#include "math.h"
#include "script_entity_action.h"
#include "inventory.h"
#include "xrserver_objects_alife_items.h"
#include "../Include/xrRender/Kinematics.h"
#include "level.h"
#include "ui/UIMainIngameWnd.h"
#include "CarWeapon.h"
#include "game_object_space.h"
#include "../xrEngine/gamemtllib.h"
#include "CharacterPhysicsSupport.h"
#include "car_memory.h"
#include "../xrphysics/IPHWorld.h"
#include "script_game_object.h"
#include "script_hit.h"
#include "netcoop.h"

// ---------------------------------------------------------------------------
// Lost Zone helicopters (doc 137)
// ---------------------------------------------------------------------------
void CCar::netcoop_heli_load()
{
	NetcoopHeli& h = m_netcoop_heli;
	h = NetcoopHeli();
	LPCSTR section = cNameSect().c_str();
	if (!READ_IF_EXISTS(pSettings, r_bool, section, "netcoop_heli", false))
		return;
	IKinematics* K = smart_cast<IKinematics*>(Visual());
	if (!K)
		return;
	h.on = true;
	h.lift_ratio = READ_IF_EXISTS(pSettings, r_float, section, "heli_lift_ratio", h.lift_ratio);
	h.max_pitch = deg2rad(READ_IF_EXISTS(pSettings, r_float, section, "heli_max_pitch", rad2deg(h.max_pitch)));
	h.max_roll = deg2rad(READ_IF_EXISTS(pSettings, r_float, section, "heli_max_roll", rad2deg(h.max_roll)));
	h.attitude_gain = READ_IF_EXISTS(pSettings, r_float, section, "heli_attitude_gain", h.attitude_gain);
	h.bank_turn = READ_IF_EXISTS(pSettings, r_float, section, "heli_bank_turn", h.bank_turn);
	h.pitch_rate = READ_IF_EXISTS(pSettings, r_float, section, "heli_pitch_rate", h.pitch_rate);
	h.roll_rate = READ_IF_EXISTS(pSettings, r_float, section, "heli_roll_rate", h.roll_rate);
	h.yaw_rate = READ_IF_EXISTS(pSettings, r_float, section, "heli_yaw_rate", h.yaw_rate);
	h.rate_gain = READ_IF_EXISTS(pSettings, r_float, section, "heli_rate_gain", h.rate_gain);
	h.drag = READ_IF_EXISTS(pSettings, r_float, section, "heli_drag", h.drag);
	h.vertical_damping = READ_IF_EXISTS(pSettings, r_float, section, "heli_vertical_damping", h.vertical_damping);
	h.ground_effect = READ_IF_EXISTS(pSettings, r_float, section, "heli_ground_effect", h.ground_effect);
	h.rotor_diameter = READ_IF_EXISTS(pSettings, r_float, section, "heli_rotor_diameter", h.rotor_diameter);
	h.spool_up = READ_IF_EXISTS(pSettings, r_float, section, "heli_spool_up", h.spool_up);
	h.spool_down = READ_IF_EXISTS(pSettings, r_float, section, "heli_spool_down", h.spool_down);
	h.collective_rate = READ_IF_EXISTS(pSettings, r_float, section, "heli_collective_rate", h.collective_rate);
	h.climb_rate = READ_IF_EXISTS(pSettings, r_float, section, "heli_climb_rate", h.climb_rate);
	h.sink_rate = READ_IF_EXISTS(pSettings, r_float, section, "heli_sink_rate", h.sink_rate);
	h.climb_gain = READ_IF_EXISTS(pSettings, r_float, section, "heli_climb_gain", h.climb_gain);
	h.crash_speed = READ_IF_EXISTS(pSettings, r_float, section, "heli_crash_speed", h.crash_speed);
	// A new helicopter is pushed out of the ground and settles: no impact.
	h.crash_armed = Device.dwTimeGlobal + 5000;
	h.rotor_anim_speed = READ_IF_EXISTS(pSettings, r_float, section, "heli_rotor_anim_speed", h.rotor_anim_speed);
	// The model's own "idle" turns the rotors (the AI helicopter plays it at
	// full speed); here it runs as fast as the rotor and stands still parked.
	if (IKinematicsAnimated* animated = smart_cast<IKinematicsAnimated*>(Visual()))
	{
		const MotionID idle = animated->ID_Cycle_Safe("idle");
		if (idle.valid())
		{
			// A whole-body cycle plays once per partition and PlayCycle then
			// returns no blend (the owner saw the rotor turn with the engine
			// off): the speed is set on every blend of the model instead.
			animated->PlayCycle(idle, FALSE);
			h.rotor_anim = true;
			netcoop_heli_rotor_speed(0.f);
		}
	}
}

void CCar::netcoop_heli_rotor_speed(float speed)
{
	struct SetSpeed : IterateBlendsCallback
	{
		float speed;
		void operator()(CBlend& B) override { B.speed = speed; }
	} set;
	set.speed = speed;
	if (IKinematicsAnimated* animated = smart_cast<IKinematicsAnimated*>(Visual()))
		animated->LL_IterateBlends(set);
}

// Both sides, every frame: the rotor animation follows the rotor speed (on a
// client from the replicated rpm).
void CCar::netcoop_heli_rotors()
{
	NetcoopHeli& h = m_netcoop_heli;
	if (!h.on || !h.rotor_anim)
		return;
	float spool = h.rotor;
	if (netcoop::pure_client())
		spool = m_max_rpm > m_min_rpm && b_engine_on ? _max(0.f, _min(1.f, (m_netcoop_rpm - m_min_rpm) / (m_max_rpm - m_min_rpm))) : 0.f;
	netcoop_heli_rotor_speed(spool * h.rotor_anim_speed);
}

void CCar::netcoop_heli_step(float dt)
{
	NetcoopHeli& h = m_netcoop_heli;
	CPhysicsShell* shell = PPhysicsShell();
	IKinematics* K = smart_cast<IKinematics*>(Visual());
	if (!shell || !K || !_valid(dt) || dt <= 0.f || !shell->get_ElementsNumber())
		return;
	// bone_map is static construction scratch, overwritten by the next car's
	// spawn. Flight must only ever apply forces to this helicopter's shell.
	CPhysicsElement* body = shell->get_ElementByStoreOrder(0);
	if (!body)
		return;
	const u8 keys = m_netcoop_keys;
	// Rotor spool and collective. An empty tank spools the rotor down.
	const float spool_target = b_engine_on && m_fuel > 0.f ? 1.f : 0.f;
	if (h.rotor < spool_target)
		h.rotor = _min(spool_target, h.rotor + h.spool_up * dt);
	else
		h.rotor = _max(spool_target, h.rotor - h.spool_down * dt);
	m_current_rpm = m_min_rpm + h.rotor * (m_max_rpm - m_min_rpm); // engine sound, replication
	if (b_engine_on)
		m_fuel = _max(0.f, m_fuel - dt * m_current_rpm * m_fuel_consumption);
	// An impact (owner 2026-10-17: a falling helicopter must crash): the
	// speed of the last moments, decaying 30 m/s per second, against now.
	// Braking by drag or a landing never loses crash_speed that fast.
	Fvector velocity;
	shell->get_LinearVel(velocity);
	const float speed = _valid(velocity) ? velocity.magnitude() : 0.f;
	if (Device.dwTimeGlobal < h.crash_armed)
		h.recent_speed = 0.f;
	else if (!h.crashed && h.recent_speed - speed > h.crash_speed)
	{
		h.crashed = true;
		netcoop_heli_crash();
		return;
	}
	h.recent_speed = _max(speed, h.recent_speed - 30.f * dt);
	if (h.rotor < 0.01f && !keys)
		return; // parked: no forces, the body may sleep
	shell->Enable();

	Fmatrix xform;
	body->GetGlobalTransformDynamic(&xform);
	const float mass = shell->getMass();
	const float g = physics_world()->Gravity();
	// Ground effect: within one rotor diameter of the ground the lift grows by up to ground_effect.
	if (Device.dwTimeGlobal >= h.ground_probe)
	{
		h.ground_probe = Device.dwTimeGlobal + 100;
		collide::rq_result hit;
		Fvector start = xform.c, down;
		down.set(0.f, -1.f, 0.f);
		start.y += 0.5f;
		h.ground_height = Level().ObjectSpace.RayPick(start, down, h.rotor_diameter, collide::rqtStatic, hit, this)
			? hit.range - 0.5f : 100.f;
	}
	const float near_ground = h.ground_height < h.rotor_diameter ? 1.f - _max(0.f, h.ground_height) / h.rotor_diameter : 0.f;
	const float lift_factor = h.lift_ratio * h.rotor * h.rotor * (1.f + h.ground_effect * near_ground);

	// Collective with a vertical speed hold: Space climbs, Ctrl sinks (slower
	// close to the ground), neither holds the height. Standing on the ground
	// without Space it stays down.
	const bool landed = h.ground_height < 0.4f && _abs(velocity.y) < 1.f;
	float collective = 0.f;
	// Nobody at the controls (the pilot jumped out): no collective, it falls.
	if (h.pilot && (!landed || (keys & netcoop_key_handbrake)))
	{
		float want_climb = 0.f;
		if (keys & netcoop_key_handbrake)
			want_climb = h.climb_rate;
		else if (keys & netcoop_key_down)
			want_climb = -_max(1.5f, _min(h.sink_rate, h.ground_height * 0.8f));
		const float hover = xform.j.y > 0.2f && lift_factor > EPS ? 1.f / (lift_factor * xform.j.y) : 1.f;
		collective = hover + h.climb_gain * (want_climb - velocity.y) / g;
	}
	collective = _max(0.f, _min(1.f, collective));
	if (h.collective < collective)
		h.collective = _min(collective, h.collective + h.collective_rate * dt);
	else
		h.collective = _max(collective, h.collective - h.collective_rate * dt);
	const float lift = mass * g * h.collective * lift_factor;
	body->applyForce(xform.j.x * lift, xform.j.y * lift, xform.j.z * lift);

	// Quadratic air drag on the whole body.
	if (speed > EPS_L)
	{
		const float drag = h.drag * 1e-3f * mass * speed;
		body->applyForce(-velocity.x * drag, -velocity.y * drag, -velocity.z * drag);
	}
	// The rotor disc resists climbing and sinking: a steady climb rate for a
	// held collective, no stone-like drop when it is lowered.
	body->applyForce(0.f, -velocity.y * h.vertical_damping * mass * h.rotor, 0.f);

	// Attitude command: W/S and A/D hold a pitch and a bank angle, released
	// the body levels; Q/E set the turn rate. The body's angular velocity is
	// steered to that (body axes: x right, y up, z forward; +x pitches the
	// nose down, +y turns right, +z banks left).
	Fvector angular, local;
	shell->get_AngularVel(angular);
	local.set(angular.dotproduct(xform.i), angular.dotproduct(xform.j), angular.dotproduct(xform.k));
	const float nose_down = -asinf(_max(-1.f, _min(1.f, xform.k.y)));
	const float bank_left = asinf(_max(-1.f, _min(1.f, xform.i.y)));
	const float want_nose_down = (keys & netcoop_key_forward ? h.max_pitch : 0.f) - (keys & netcoop_key_back ? h.max_pitch : 0.f);
	const float want_bank_left = (keys & netcoop_key_left ? h.max_roll : 0.f) - (keys & netcoop_key_right ? h.max_roll : 0.f);
	const float forward_speed = velocity.dotproduct(xform.k);
	Fvector target;
	target.x = _max(-h.pitch_rate, _min(h.pitch_rate, h.attitude_gain * (want_nose_down - nose_down)));
	target.z = _max(-h.roll_rate, _min(h.roll_rate, h.attitude_gain * (want_bank_left - bank_left)));
	target.y = (keys & netcoop_key_yaw_right ? h.yaw_rate : 0.f) - (keys & netcoop_key_yaw_left ? h.yaw_rate : 0.f);
	// A bank in forward flight turns the nose the same way.
	target.y -= bank_left * h.bank_turn * _max(0.f, _min(1.f, forward_speed / 15.f));
	target.y = _max(-h.yaw_rate, _min(h.yaw_rate, target.y));
	Fvector error;
	error.sub(target, local);
	const float gain = h.rate_gain * mass * h.rotor;
	Fvector torque;
	torque.set(0.f, 0.f, 0.f);
	torque.mad(xform.i, error.x * gain);
	torque.mad(xform.j, error.y * gain);
	torque.mad(xform.k, error.z * gain);
	if (_valid(torque))
		body->applyTorque(torque.x, torque.y, torque.z);
}

// Server: a helicopter that hit the ground or a wall hard enough dies like a
// car shot to pieces - the death goes to every client and it explodes there.
void CCar::netcoop_heli_crash()
{
	if (b_exploded || !g_Alive())
		return;
	Msg("[Lost Zone][heli] %s (%u) crashed", cName().c_str(), ID());
	ChangeCondition(-1.f);
}
