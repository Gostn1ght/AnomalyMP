#include "common.h"
struct room_input { float4 position : POSITION; float3 normal : NORMAL; float4 color : COLOR0; float2 uv : TEXCOORD0; };
struct room_output { float4 position : SV_Position; float4 color : COLOR0; float2 uv : TEXCOORD0; float3 normal : TEXCOORD1; float3 world : TEXCOORD2; float4 shadow : TEXCOORD3; };
float4x4 m_menu_shadow;
room_output main(room_input vertex)
{
    room_output result;
    result.position = mul(m_WVP, vertex.position);
    result.color = vertex.color.bgra;
    result.uv = vertex.uv;
    result.normal=vertex.normal; result.world=vertex.position.xyz;
    result.shadow=mul(m_menu_shadow,vertex.position);
    return result;
}
