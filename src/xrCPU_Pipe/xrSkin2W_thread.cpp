#include "stdafx.h"
#pragma hdrstop

#include <tbb/parallel_for.h>
#include <tbb/blocked_range.h>

extern xrSkin4W* skin4W_func;

// Lost Zone (doc 151): 4-bone skinning split over the TBB worker pool the
// engine already uses for textures and sounds. The old ttapi kept its own
// helper threads spinning between frames.
void __stdcall xrSkin4W_thread(vertRender* D,
                               vertBoned4W* S,
                               u32 vCount,
                               CBoneInstance* Bones)
{
	const u32 grain = 512;
	if (vCount < grain * 2)
	{
		skin4W_func(D, S, vCount, Bones);
		return;
	}
	tbb::parallel_for(tbb::blocked_range<u32>(0, vCount, grain), [&](const tbb::blocked_range<u32>& r) {
		skin4W_func(D + r.begin(), S + r.begin(), u32(r.size()), Bones);
	});
}
