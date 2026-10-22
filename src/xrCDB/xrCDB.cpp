// xrCDB.cpp : Defines the entry point for the DLL application.
//

#include "stdafx.h"
#pragma hdrstop

#include "xrCDB.h"
#include "profiler.h"

#ifdef USE_ARENA_ALLOCATOR
static const u32	s_arena_size = (128+16)*1024*1024;
static char			s_fake_array[s_arena_size];
//doug_lea_allocator	g_collision_allocator( s_fake_array, s_arena_size, "collision" );
#endif // #ifdef USE_ARENA_ALLOCATOR

namespace Opcode
{
#	include "OPC_TreeBuilders.h"
} // namespace Opcode

using namespace CDB;
using namespace Opcode;

//BOOL APIENTRY DllMain( HANDLE hModule, 
BOOL DllMainIgnore1(HANDLE hModule,
                    u32 ul_reason_for_call,
                    LPVOID lpReserved
)
{
	switch (ul_reason_for_call)
	{
	case DLL_PROCESS_ATTACH:
	case DLL_THREAD_ATTACH:
	case DLL_THREAD_DETACH:
	case DLL_PROCESS_DETACH:
		break;
	}
	return TRUE;
}

// Model building
MODEL::MODEL()
#ifdef PROFILE_CRITICAL_SECTIONS
	:cs(MUTEX_PROFILE_ID(MODEL))
#endif // PROFILE_CRITICAL_SECTIONS
{
	tree = 0;
	tris = 0;
	tris_count = 0;
	verts = 0;
	verts_count = 0;
	status = S_INIT;
}

MODEL::~MODEL()
{
	syncronize(); // maybe model still in building
	status = S_INIT;
	CDELETE(tree);
	CFREE(tris);
	tris_count = 0;
	CFREE(verts);
	verts_count = 0;
}

struct BTHREAD_params
{
	MODEL* M;
	Fvector* V;
	int Vcnt;
	TRI* T;
	int Tcnt;
	build_callback* BC;
	void* BCP;
};

void MODEL::build_thread(void* params)
{
	PROF_EVENT();

	_initialize_cpu_thread();
	FPU::m64r();
	BTHREAD_params P = *((BTHREAD_params*)params);
	P.M->cs.Enter();
	P.M->build_internal(P.V, P.Vcnt, P.T, P.Tcnt, P.BC, P.BCP);
	P.M->status = S_READY;
	P.M->cs.Leave();
	//Msg						("* xrCDB: cform build completed, memory usage: %d K",P.M->memory()/1024);
}

void MODEL::build(Fvector* V, int Vcnt, TRI* T, int Tcnt, build_callback* bc, void* bcp)
{
	R_ASSERT(S_INIT == status);
	R_ASSERT((Vcnt>=4)&&(Tcnt>=2));

	_initialize_cpu_thread();
	if (!strstr(Core.Params, "-mt_cdb"))
	{
		build_internal(V, Vcnt, T, Tcnt, bc, bcp);
		status = S_READY;
	}
	else
	{
		BTHREAD_params P = {this, V, Vcnt, T, Tcnt, bc, bcp};
		thread_spawn(build_thread, "CDB-construction", 0, &P);
		while (S_INIT == status)
		{
			if (status != S_INIT)
				break;
			Sleep(5);
		}
	}
}

namespace
{
// Collision trees of large models (levels) are cached on disk: building the
// tree took ~8 s of every level load on server and client (doc 151). The key
// is the geometry the tree is built from (after the build callback).
const u32 cform_cache_magic = 0x46435a4c; // "LZCF"
const u32 cform_cache_version = 1;
const int cform_cache_min_tris = 100000;
const int cform_cache_files = 12;

struct CformCacheHeader
{
	u32 magic, version, verts, tris, nodes, crc_verts, crc_tris, crc_nodes;
};

bool cform_cache_path(string_path& path, u32 crc_verts, u32 crc_tris, int Vcnt, int Tcnt)
{
	if (!FS.path_exist("$app_data_root$"))
		return false;
	string_path folder;
	FS.update_path(folder, "$app_data_root$", "cform_cache\\");
	CreateDirectoryA(folder, nullptr);
	xr_sprintf(path, "%s%08x%08x_%d_%d.bin", folder, crc_verts, crc_tris, Vcnt, Tcnt);
	return true;
}

// The oldest files go when there are more than cform_cache_files.
void cform_cache_trim(LPCSTR path)
{
	string_path folder, mask;
	xr_strcpy(folder, path);
	if (LPSTR slash = strrchr(folder, '\\'))
		slash[1] = 0;
	xr_sprintf(mask, "%s*.bin", folder);
	struct entry { FILETIME written; xr_string name; };
	xr_vector<entry> files;
	WIN32_FIND_DATAA data;
	HANDLE find = FindFirstFileA(mask, &data);
	if (find == INVALID_HANDLE_VALUE)
		return;
	do
		files.push_back({data.ftLastWriteTime, xr_string(folder) + data.cFileName});
	while (FindNextFileA(find, &data));
	FindClose(find);
	if (files.size() <= cform_cache_files)
		return;
	std::sort(files.begin(), files.end(), [](const entry& a, const entry& b)
	{
		return CompareFileTime(&a.written, &b.written) < 0;
	});
	for (size_t i = 0; i + cform_cache_files < files.size(); i++)
		DeleteFileA(files[i].name.c_str());
}

Opcode::OPCODE_Model* cform_cache_read(LPCSTR path, u32 crc_verts, u32 crc_tris, int Vcnt, int Tcnt)
{
	FILE* f = fopen(path, "rb");
	if (!f)
		return nullptr;
	CformCacheHeader h;
	Opcode::OPCODE_Model* model = nullptr;
	if (fread(&h, sizeof(h), 1, f) == 1 && h.magic == cform_cache_magic && h.version == cform_cache_version &&
		h.verts == u32(Vcnt) && h.tris == u32(Tcnt) && h.crc_verts == crc_verts && h.crc_tris == crc_tris &&
		h.nodes + 1 == u32(Tcnt))
	{
		const size_t bytes = size_t(h.nodes) * Opcode::AABBNoLeafTree::SerializedNodeSize;
		xr_vector<u8> nodes(bytes);
		if (fread(nodes.data(), 1, bytes, f) == bytes && crc32(nodes.data(), u32(bytes)) == h.crc_nodes)
		{
			model = CNEW(Opcode::OPCODE_Model)();
			if (!model->Load(nodes.data(), h.nodes, u32(Tcnt)))
			{
				CDELETE(model);
				model = nullptr;
			}
		}
	}
	fclose(f);
	if (!model)
		DeleteFileA(path);
	return model;
}

void cform_cache_write(LPCSTR path, const Opcode::OPCODE_Model* model, u32 crc_verts, u32 crc_tris, int Vcnt, int Tcnt)
{
	const Opcode::AABBNoLeafTree* tree = model->GetNoLeafTree();
	if (!tree)
		return;
	const size_t bytes = size_t(tree->GetNbNodes()) * Opcode::AABBNoLeafTree::SerializedNodeSize;
	xr_vector<u8> nodes(bytes);
	tree->Export(nodes.data());
	CformCacheHeader h = {cform_cache_magic, cform_cache_version, u32(Vcnt), u32(Tcnt), tree->GetNbNodes(),
		crc_verts, crc_tris, crc32(nodes.data(), u32(bytes))};
	string_path temp;
	xr_sprintf(temp, "%s.tmp", path);
	FILE* f = fopen(temp, "wb");
	if (!f)
		return;
	const bool written = fwrite(&h, sizeof(h), 1, f) == 1 && fwrite(nodes.data(), 1, bytes, f) == bytes;
	fclose(f);
	if (written && MoveFileExA(temp, path, MOVEFILE_REPLACE_EXISTING))
		cform_cache_trim(path);
	else
		DeleteFileA(temp);
}
}

void MODEL::build_internal(Fvector* V, int Vcnt, TRI* T, int Tcnt, build_callback* bc, void* bcp)
{
	PROF_EVENT();

	// verts
	verts_count = Vcnt;
	verts = CALLOC(Fvector, verts_count);
	CopyMemory(verts, V, verts_count*sizeof(Fvector));

	// tris
	tris_count = Tcnt;
	tris = CALLOC(TRI, tris_count);
	CopyMemory(tris, T, tris_count*sizeof(TRI));

	// callback
	if (bc) bc(verts, Vcnt, tris, Tcnt, bcp);

	// Release data pointers
	status = S_BUILD;

	// Allocate temporary "OPCODE" tris + convert tris to 'pointer' form
	u32* temp_tris = CALLOC(u32, tris_count*3);
	if (0 == temp_tris)
	{
		CFREE(verts);
		CFREE(tris);
		return;
	}
	u32* temp_ptr = temp_tris;
	for (int i = 0; i < tris_count; i++)
	{
		*temp_ptr++ = tris[i].verts[0];
		*temp_ptr++ = tris[i].verts[1];
		*temp_ptr++ = tris[i].verts[2];
	}

	string_path cache_path = "";
	u32 crc_verts = 0, crc_tris = 0;
	if (tris_count >= cform_cache_min_tris && !strstr(Core.Params, "-no_cform_cache"))
	{
		crc_verts = crc32(verts, verts_count * sizeof(Fvector));
		crc_tris = crc32(temp_tris, tris_count * 3 * sizeof(u32));
		if (cform_cache_path(cache_path, crc_verts, crc_tris, verts_count, tris_count))
		{
			tree = cform_cache_read(cache_path, crc_verts, crc_tris, verts_count, tris_count);
			if (tree)
			{
				Msg("* xrCDB: collision tree of %d triangles from the cache", tris_count);
				CFREE(temp_tris);
				return;
			}
		}
	}

	// Build a non quantized no-leaf tree
	OPCODECREATE OPCC;
	OPCC.NbTris = tris_count;
	OPCC.NbVerts = verts_count;
	OPCC.Tris = (unsigned*)temp_tris;
	OPCC.Verts = (Point*)verts;
	OPCC.Rules = SPLIT_COMPLETE | SPLIT_SPLATTERPOINTS | SPLIT_GEOMCENTER;
	OPCC.NoLeaf = true;
	OPCC.Quantized = false;
	// if (Memory.debug_mode) OPCC.KeepOriginal = true;

	tree = CNEW(OPCODE_Model)();
	if (!tree->Build(OPCC))
	{
		CFREE(verts);
		CFREE(tris);
		CFREE(temp_tris);
		return;
	};

	if (cache_path[0])
		cform_cache_write(cache_path, tree, crc_verts, crc_tris, verts_count, tris_count);

	// Free temporary tris
	CFREE(temp_tris);
	return;
}

u32 MODEL::memory()
{
	if (S_BUILD == status)
	{
		Msg("! xrCDB: model still isn't ready");
		return 0;
	}
	u32 V = verts_count * sizeof(Fvector);
	u32 T = tris_count * sizeof(TRI);
	return tree->GetUsedBytes() + V + T + sizeof(*this) + sizeof(*tree);
}

// This is the constructor of a class that has been exported.
// see xrCDB.h for the class definition
COLLIDER::COLLIDER()
{
	ray_mode = 0;
	box_mode = 0;
	frustum_mode = 0;
}

COLLIDER::~COLLIDER()
{
	r_free();
}

RESULT& COLLIDER::r_add()
{
	rd.push_back(RESULT());
	return rd.back();
}

void COLLIDER::r_free()
{
	rd.clear_and_free();
}
