#include "common.h"
#include "skin.h"
struct preview_vertex { float4 position : SV_Position; float2 uv : TEXCOORD0; float3 normal : TEXCOORD1; };
preview_vertex preview_main(v_model vertex)
{
    preview_vertex result;
    result.position = mul(m_WVP, vertex.P);
    result.uv = vertex.tc;
    result.normal = mul((float3x3)m_W, vertex.N);
    return result;
}
#ifdef SKIN_NONE
preview_vertex main(v_model v) { return preview_main(v); }
#endif
#ifdef SKIN_0
preview_vertex main(v_model_skinned_0 v) { return preview_main(skinning_0(v)); }
#endif
#ifdef SKIN_1
preview_vertex main(v_model_skinned_1 v) { return preview_main(skinning_1(v)); }
#endif
#ifdef SKIN_2
preview_vertex main(v_model_skinned_2 v) { return preview_main(skinning_2(v)); }
#endif
#ifdef SKIN_3
preview_vertex main(v_model_skinned_3 v) { return preview_main(skinning_3(v)); }
#endif
#ifdef SKIN_4
preview_vertex main(v_model_skinned_4 v) { return preview_main(skinning_4(v)); }
#endif
