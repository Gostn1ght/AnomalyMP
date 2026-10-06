#include "stdafx.h"
#pragma hdrstop

#include "xrMemory_align.h"
#include "xrMemory_pure.h"

#ifndef __BORLANDC__

#ifndef DEBUG_MEMORY_MANAGER
# define debug_mode 0
#endif // DEBUG_MEMORY_MANAGER

#ifdef DEBUG_MEMORY_MANAGER
XRCORE_API void* g_globalCheckAddr = NULL;
#endif // DEBUG_MEMORY_MANAGER

#ifdef DEBUG_MEMORY_MANAGER
extern void save_stack_trace();
#endif // DEBUG_MEMORY_MANAGER

MEMPOOL mem_pools[mem_pools_count];

// MSVC
ICF u8* acc_header(void* P)
{
	u8* _P = (u8*)P;
	return _P - 1;
}

ICF u32 get_header(void* P) { return (u32)*acc_header(P); }
ICF u32 get_pool(size_t size)
{
	u32 pid = u32(size / mem_pools_ebase);
	if (pid >= mem_pools_count) return mem_generic;
	else return pid;
}

#ifdef PURE_ALLOC
const bool g_use_pure_alloc = true;
#endif // PURE_ALLOC

#define PURE_MEMORY_FILL_ZERO
#define PURE_MEMORY_ALIGNMENT 1 << 4

// -mem_profile[=<bytes>] (Lost Zone, dedicated server memory): every live
// allocation of at least <bytes> (default 4096) is remembered with its call
// stack; mem_profile_report() prints the call sites holding the most memory
// as module+offset (symbolised offline with the build's PDB). Off unless the
// flag is on the command line: one branch per allocation.
namespace mem_profile
{
struct Entry
{
	void* ptr; // 0 empty, 1 deleted
	size_t size;
	void* frames[6];
};
static const size_t capacity = size_t(1) << 21;
static Entry* table = nullptr;
static SRWLOCK lock = SRWLOCK_INIT;
static int state = -1; // -1 unknown, 0 off, 1 on
static size_t threshold = 4096;
static size_t dropped = 0;

static bool on()
{
	if (state >= 0) return state == 1;
	LPCSTR line = GetCommandLineA();
	LPCSTR flag = line ? strstr(line, "-mem_profile") : nullptr;
	if (!flag)
	{
		state = 0;
		return false;
	}
	if (flag[12] == '=') threshold = size_t(atoi(flag + 13));
	if (threshold < 64) threshold = 64;
	table = (Entry*)VirtualAlloc(nullptr, capacity * sizeof(Entry), MEM_RESERVE | MEM_COMMIT, PAGE_READWRITE);
	state = table ? 1 : 0;
	return state == 1;
}

static size_t slot_of(void* p) { return (size_t(p) >> 4) * 2654435761u & (capacity - 1); }

static void add(void* p, size_t size)
{
	if (!p || size < threshold || !on()) return;
	Entry e = {p, size, {}};
	RtlCaptureStackBackTrace(2, 6, e.frames, nullptr);
	AcquireSRWLockExclusive(&lock);
	size_t i = slot_of(p);
	for (size_t n = 0; n < capacity; ++n, i = (i + 1) & (capacity - 1))
	{
		if (size_t(table[i].ptr) <= 1)
		{
			table[i] = e;
			ReleaseSRWLockExclusive(&lock);
			return;
		}
	}
	++dropped;
	ReleaseSRWLockExclusive(&lock);
}

static void remove(void* p)
{
	if (!p || state != 1) return;
	if (_aligned_msize(p, PURE_MEMORY_ALIGNMENT, 0) < threshold) return;
	AcquireSRWLockExclusive(&lock);
	size_t i = slot_of(p);
	for (size_t n = 0; n < capacity; ++n, i = (i + 1) & (capacity - 1))
	{
		if (table[i].ptr == p)
		{
			table[i].ptr = (void*)1;
			break;
		}
		if (table[i].ptr == nullptr) break;
	}
	ReleaseSRWLockExclusive(&lock);
}

static void describe(void* address, char* out, size_t size)
{
	HMODULE module = nullptr;
	char path[MAX_PATH] = "?";
	if (GetModuleHandleExA(GET_MODULE_HANDLE_EX_FLAG_FROM_ADDRESS | GET_MODULE_HANDLE_EX_FLAG_UNCHANGED_REFCOUNT,
		(LPCSTR)address, &module) && module)
		GetModuleFileNameA(module, path, sizeof(path));
	LPCSTR name = strrchr(path, '\\');
	name = name ? name + 1 : path;
	sprintf_s(out, size, "%s+%Ix", name, size_t((u8*)address - (u8*)module));
}

static bool in_core(void* address)
{
	static HMODULE core = nullptr;
	if (!core)
		GetModuleHandleExA(GET_MODULE_HANDLE_EX_FLAG_FROM_ADDRESS | GET_MODULE_HANDLE_EX_FLAG_UNCHANGED_REFCOUNT,
			(LPCSTR)&in_core, &core);
	HMODULE module = nullptr;
	GetModuleHandleExA(GET_MODULE_HANDLE_EX_FLAG_FROM_ADDRESS | GET_MODULE_HANDLE_EX_FLAG_UNCHANGED_REFCOUNT,
		(LPCSTR)address, &module);
	return module == core;
}
}

XRCORE_API void mem_profile_report(LPCSTR stage)
{
	using namespace mem_profile;
	if (state != 1) return;
	struct Site
	{
		void* key[2];
		size_t bytes, blocks;
	};
	const size_t sites_capacity = 1 << 14;
	Site* sites = (Site*)VirtualAlloc(nullptr, sites_capacity * sizeof(Site), MEM_RESERVE | MEM_COMMIT, PAGE_READWRITE);
	if (!sites) return;
	size_t total = 0, blocks = 0;
	AcquireSRWLockShared(&lock);
	for (size_t i = 0; i < capacity; ++i)
	{
		const Entry& e = table[i];
		if (size_t(e.ptr) <= 1) continue;
		total += e.size;
		++blocks;
		// The first two frames outside xrCore (its allocation wrappers).
		void* key[2] = {nullptr, nullptr};
		int k = 0;
		for (int f = 0; f < 6 && k < 2; ++f)
			if (e.frames[f] && (k > 0 || !in_core(e.frames[f]))) key[k++] = e.frames[f];
		if (!key[0]) key[0] = e.frames[0];
		size_t h = (size_t(key[0]) * 31 + size_t(key[1])) % sites_capacity;
		for (size_t n = 0; n < sites_capacity; ++n, h = (h + 1) % sites_capacity)
		{
			Site& s = sites[h];
			if (s.blocks == 0 || (s.key[0] == key[0] && s.key[1] == key[1]))
			{
				s.key[0] = key[0];
				s.key[1] = key[1];
				s.bytes += e.size;
				++s.blocks;
				break;
			}
		}
	}
	ReleaseSRWLockShared(&lock);
	Msg("[Lost Zone][mem-profile] %s: %Iu MB live in %Iu blocks of >= %Iu bytes (dropped %Iu)", stage ? stage : "",
		total >> 20, blocks, threshold, dropped);
	for (int top = 0; top < 40; ++top)
	{
		Site* best = nullptr;
		for (size_t i = 0; i < sites_capacity; ++i)
			if (sites[i].blocks && (!best || sites[i].bytes > best->bytes)) best = &sites[i];
		if (!best || best->bytes < (1u << 20)) break;
		char a[300], b[300];
		describe(best->key[0], a, sizeof(a));
		if (best->key[1]) describe(best->key[1], b, sizeof(b));
		else b[0] = 0;
		Msg("[Lost Zone][mem-profile] %7.1f MB %7Iu blocks  %s < %s", float(best->bytes) / 1048576.f, best->blocks, a, b);
		best->blocks = 0;
	}
	VirtualFree(sites, 0, MEM_RELEASE);
}

void* xrMemory::mem_alloc(size_t size
# ifdef DEBUG_MEMORY_NAME
                          , const char* _name
# endif // DEBUG_MEMORY_NAME
)
{
	stat_calls++;

#ifdef PURE_ALLOC
	if (g_use_pure_alloc)
	{
		//void* result = malloc(size);
		void* result = _aligned_malloc(size, PURE_MEMORY_ALIGNMENT);
#ifdef PURE_MEMORY_FILL_ZERO
		if (result)
			memset(result, 0, size);
#endif // PURE_MEMORY_FILL_ZERO
		mem_profile::add(result, size);

#ifdef USE_MEMORY_MONITOR
        memory_monitor::monitor_alloc(result, size, _name);
#endif // USE_MEMORY_MONITOR
		return (result);
	}
#endif // PURE_ALLOC

#ifdef DEBUG_MEMORY_MANAGER
    if (mem_initialized) debug_cs.Enter();
#endif // DEBUG_MEMORY_MANAGER

	u32 _footer = debug_mode ? 4 : 0;
	void* _ptr = 0;

	//
	if (!mem_initialized /*|| debug_mode*/)
	{
		// generic
		// Igor: Reserve 1 byte for xrMemory header
		void* _real = xr_aligned_offset_malloc(1 + size + _footer, 16, 0x1);
		//void* _real = xr_aligned_offset_malloc (size + _footer, 16, 0x1);
		_ptr = (void*)(((u8*)_real) + 1);
		*acc_header(_ptr) = mem_generic;
	}
	else
	{
#ifdef DEBUG_MEMORY_MANAGER
        save_stack_trace();
#endif // DEBUG
		// accelerated
		// Igor: Reserve 1 byte for xrMemory header
		u32 pool = get_pool(1 + size + _footer);
		//u32 pool = get_pool (size+_footer);
		if (mem_generic == pool)
		{
			// generic
			// Igor: Reserve 1 byte for xrMemory header
			void* _real = xr_aligned_offset_malloc(1 + size + _footer, 16, 0x1);
			//void* _real = xr_aligned_offset_malloc (size + _footer,16,0x1);
			_ptr = (void*)(((u8*)_real) + 1);
			*acc_header(_ptr) = mem_generic;
		}
		else
		{
			// pooled
			// Igor: Reserve 1 byte for xrMemory header
			// Already reserved when getting pool id
			void* _real = mem_pools[pool].create();
			_ptr = (void*)(((u8*)_real) + 1);
			*acc_header(_ptr) = (u8)pool;
		}
	}

#ifdef DEBUG_MEMORY_MANAGER
    if (debug_mode) dbg_register(_ptr, size, _name);
    if (mem_initialized) debug_cs.Leave();
    //if(g_globalCheckAddr==_ptr){
	// __asm int 3;
	//}
	//if (_name && (0==strcmp(_name,"class ISpatial *")) && (size==376))
	//{
	// __asm int 3;
	//}
#endif // DEBUG_MEMORY_MANAGER
#ifdef USE_MEMORY_MONITOR
    memory_monitor::monitor_alloc(_ptr, size, _name);
#endif // USE_MEMORY_MONITOR
	memset(_ptr, 0, size);
	return _ptr;
}

void xrMemory::mem_free(void* P)
{
	stat_calls++;
#ifdef USE_MEMORY_MONITOR
    memory_monitor::monitor_free(P);
#endif // USE_MEMORY_MONITOR

#ifdef PURE_ALLOC
	if (g_use_pure_alloc)
	{
		//free(P);
		mem_profile::remove(P);
		_aligned_free(P);
		return;
	}
#endif // PURE_ALLOC

#ifdef DEBUG_MEMORY_MANAGER
    if (g_globalCheckAddr == P)
        __asm int 3;
#endif // DEBUG_MEMORY_MANAGER

#ifdef DEBUG_MEMORY_MANAGER
    if (mem_initialized) debug_cs.Enter();
#endif // DEBUG_MEMORY_MANAGER
	if (debug_mode) dbg_unregister(P);
	u32 pool = get_header(P);
	void* _real = (void*)(((u8*)P) - 1);
	if (mem_generic == pool)
	{
		// generic
		xr_aligned_free(_real);
	}
	else
	{
		// pooled
		VERIFY2(pool < mem_pools_count, "Memory corruption");
		mem_pools[pool].destroy(_real);
	}
#ifdef DEBUG_MEMORY_MANAGER
    if (mem_initialized) debug_cs.Leave();
#endif // DEBUG_MEMORY_MANAGER
}

extern BOOL g_bDbgFillMemory;

void* xrMemory::mem_realloc(void* P, size_t size
#ifdef DEBUG_MEMORY_NAME
                            , const char* _name
#endif // DEBUG_MEMORY_NAME
)
{
	stat_calls++;

	if (0 == P)
	{
		return mem_alloc(size
# ifdef DEBUG_MEMORY_NAME
			, _name
# endif // DEBUG_MEMORY_NAME
		);
	}

#ifdef PURE_ALLOC
	if (g_use_pure_alloc)
	{
#ifdef PURE_MEMORY_FILL_ZERO
		size_t old_size = P ? _aligned_msize(P, PURE_MEMORY_ALIGNMENT, 0) : 0;
#endif // PURE_MEMORY_FILL_ZERO

		//void* result = realloc(P, size);
		mem_profile::remove(P);
		void* result = _aligned_realloc(P, size, PURE_MEMORY_ALIGNMENT);
		mem_profile::add(result, size);

#ifdef PURE_MEMORY_FILL_ZERO
		if (result && size > old_size)
			memset((u8*)result + old_size, 0, size - old_size);
#endif // PURE_MEMORY_FILL_ZERO

# ifdef USE_MEMORY_MONITOR
        memory_monitor::monitor_free(P);
        memory_monitor::monitor_alloc(result, size, _name);
# endif // USE_MEMORY_MONITOR
		return (result);
	}
#endif // PURE_ALLOC

#ifdef DEBUG_MEMORY_MANAGER
    if (g_globalCheckAddr == P)
        __asm int 3;
#endif // DEBUG_MEMORY_MANAGER

#ifdef DEBUG_MEMORY_MANAGER
    if (mem_initialized) debug_cs.Enter();
#endif // DEBUG_MEMORY_MANAGER
	u32 p_current = get_header(P);
	// Igor: Reserve 1 byte for xrMemory header
	u32 p_new = get_pool(1 + size + (debug_mode ? 4 : 0));
	//u32 p_new = get_pool (size+(debug_mode?4:0));
	u32 p_mode;

	if (mem_generic == p_current)
	{
		if (p_new < p_current) p_mode = 2;
		else p_mode = 0;
	}
	else p_mode = 1;

	void* _real = (void*)(((u8*)P) - 1);
	void* _ptr = NULL;
	if (0 == p_mode)
	{
		u32 _footer = debug_mode ? 4 : 0;
#ifdef DEBUG_MEMORY_MANAGER
        if (debug_mode)
        {
            g_bDbgFillMemory = false;
            dbg_unregister(P);
            g_bDbgFillMemory = true;
        }
#endif // DEBUG_MEMORY_MANAGER
		// Igor: Reserve 1 byte for xrMemory header
		void* _real2 = xr_aligned_offset_realloc(_real, 1 + size + _footer, 16, 0x1);
		//void* _real2 = xr_aligned_offset_realloc (_real,size+_footer,16,0x1);
		_ptr = (void*)(((u8*)_real2) + 1);
		*acc_header(_ptr) = mem_generic;
#ifdef DEBUG_MEMORY_MANAGER
        if (debug_mode) dbg_register(_ptr, size, _name);
#endif // DEBUG_MEMORY_MANAGER
#ifdef USE_MEMORY_MONITOR
        memory_monitor::monitor_free(P);
        memory_monitor::monitor_alloc(_ptr, size, _name);
#endif // USE_MEMORY_MONITOR
	}
	else if (1 == p_mode)
	{
		// pooled realloc
		R_ASSERT2(p_current < mem_pools_count, "Memory corruption");
		u32 s_current = mem_pools[p_current].get_element();
		u32 s_dest = (u32)size;
		void* p_old = P;

		void* p_new = mem_alloc(size
#ifdef DEBUG_MEMORY_NAME
                                , _name
#endif // DEBUG_MEMORY_NAME
		);
		// Igor: Reserve 1 byte for xrMemory header
		// Don't bother in this case?
		mem_copy(p_new, p_old, _min(s_current - 1, s_dest));
		//mem_copy (p_new,p_old,_min(s_current,s_dest));
		mem_free(p_old);
		_ptr = p_new;
	}
	else if (2 == p_mode)
	{
		// relocate into another mmgr(pooled) from real
		void* p_old = P;
		void* p_new = mem_alloc(size
# ifdef DEBUG_MEMORY_NAME
                                , _name
# endif // DEBUG_MEMORY_NAME
		);
		mem_copy(p_new, p_old, (u32)size);
		mem_free(p_old);
		_ptr = p_new;
	}

#ifdef DEBUG_MEMORY_MANAGER
    if (mem_initialized) debug_cs.Leave();

    if (g_globalCheckAddr == _ptr)
        __asm int 3;
#endif // DEBUG_MEMORY_MANAGER

	return _ptr;
}

#endif // __BORLANDC__
