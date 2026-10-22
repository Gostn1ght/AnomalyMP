#include "stdafx.h"
#pragma hdrstop

using namespace std;

XRCORE_API smem_container* g_pSharedMemoryContainer = NULL;

smem_value* smem_container::dock(u32 dwCRC, u32 dwLength, void* ptr)
{
	VERIFY(dwCRC && dwLength && ptr);

	cs.Enter();
	xr_vector<smem_value*>& bucket = container[(u64(dwCRC) << 32) | dwLength];
	smem_value* result = 0;
	for (smem_value* candidate : bucket)
	{
		if (0 == memcmp(candidate->value, ptr, dwLength))
		{
			result = candidate;
			break;
		}
	}

	// if not found - create new entry
	if (0 == result)
	{
		result = (smem_value*)Memory.mem_alloc(4 * sizeof(u32) + dwLength
#ifdef DEBUG_MEMORY_NAME
                                               , "storage: smem"
#endif // DEBUG_MEMORY_NAME
		);
		result->dwReference.store(0, std::memory_order_relaxed);
		result->dwCRC = dwCRC;
		result->dwLength = dwLength;
		CopyMemory(result->value, ptr, dwLength);
		bucket.push_back(result);
	}

	// exit
	cs.Leave();
	return result;
}

void smem_container::clean()
{
	cs.Enter();
	for (auto it = container.begin(); it != container.end();)
	{
		xr_vector<smem_value*>& bucket = it->second;
		for (smem_value*& value : bucket)
			if (0 == value->dwReference.load(std::memory_order_relaxed))
			{
				xr_free(value);
				value = 0;
			}
		bucket.erase(std::remove(bucket.begin(), bucket.end(), (smem_value*)0), bucket.end());
		if (bucket.empty())
			it = container.erase(it);
		else
			++it;
	}
	cs.Leave();
}

void smem_container::dump()
{
	cs.Enter();
	FILE* F = fopen("x:\\$smem_dump$.txt", "w");
	for (const auto& bucket : container)
		for (const smem_value* value : bucket.second)
			fprintf(F, "%4u : crc[%6x], %u bytes\n", value->dwReference.load(std::memory_order_relaxed), value->dwCRC, value->dwLength);
	fclose(F);
	cs.Leave();
}

u32 smem_container::stat_economy()
{
	cs.Enter();
	s64 counter = 0;
	counter -= sizeof(*this);
	const int node_size = 20;
	for (const auto& bucket : container)
		for (const smem_value* value : bucket.second)
		{
			counter -= 16;
			counter -= node_size;
			counter += s64((s64(value->dwReference.load(std::memory_order_relaxed)) - 1) * s64(value->dwLength));
		}
	cs.Leave();

	return u32(s64(counter) / s64(1024));
}

smem_container::~smem_container()
{
	clean();
}
