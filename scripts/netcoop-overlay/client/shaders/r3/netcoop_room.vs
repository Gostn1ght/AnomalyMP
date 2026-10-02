#include "common.h"
struct room_input { float4 position : POSITION; float4 color : COLOR0; float2 uv : TEXCOORD0; };
struct room_output { float4 position : SV_Position; float4 color : COLOR0; float2 uv : TEXCOORD0; };
room_output main(room_input vertex)
{
    room_output result;
    result.position = mul(m_WVP, vertex.position);
    result.color = vertex.color.bgra;
    result.uv = vertex.uv;
    return result;
}
