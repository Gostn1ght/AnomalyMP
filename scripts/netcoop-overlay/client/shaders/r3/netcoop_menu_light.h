// One warm ceiling lamp. Small PCF shadow filter for the isolated room.
Texture2D<float> s_menu_shadow;
float4 menu_room_lamp;
float menu_visibility(float4 coordinate, float ndotl)
{
    float3 p=coordinate.xyz/coordinate.w;
    if(coordinate.w<=0 || any(p.xy<0) || any(p.xy>1) || p.z<0 || p.z>1) return 1;
    float bias=.0008+.002*(1-ndotl);
    float visible=0;
    [unroll] for(int y=-1;y<=1;y++) [unroll] for(int x=-1;x<=1;x++)
        visible += p.z-bias <= s_menu_shadow.SampleLevel(smp_nofilter,p.xy+float2(x,y)/1024.,0) ? 1./9. : 0;
    return visible;
}
float3 menu_surface_normal(float3 normal, float3 world, float2 uv, out float gloss)
{
    normal=normalize(normal); gloss=0;
#ifdef MENU_BUMP
    float4 packed=s_bump.Sample(smp_base,uv);
    // Original X-Ray encoding: normal in WZY, gloss in X.
    float3 tangentNormal=normalize(unpack_normal(packed.wzy));
    float3 dx=ddx(world), dy=ddy(world);
    float2 tx=ddx(uv), ty=ddy(uv);
    float determinant=tx.x*ty.y-tx.y*ty.x;
    if(abs(determinant)>1e-8)
    {
        float3 tangent=(dx*ty.y-dy*tx.y)/determinant;
        float3 bitangent=(dy*tx.x-dx*ty.x)/determinant;
        tangent=normalize(tangent-normal*dot(normal,tangent));
        bitangent=normalize(bitangent-normal*dot(normal,bitangent));
        normal=normalize(tangent*tangentNormal.x+bitangent*tangentNormal.y+normal*tangentNormal.z);
    }
    gloss=packed.x*packed.x;
#endif
    return normal;
}
float3 menu_light(float3 diffuse, float3 normal, float3 world, float4 shadow, float gloss)
{
    float3 delta=menu_room_lamp.xyz-world;
    float distance2=dot(delta,delta);
    float ndotl=saturate(dot(normalize(normal),normalize(delta)));
    float visibility=menu_visibility(shadow,ndotl);
    float attenuation=1/(1+.55*distance2);
    // Dim bunker: one warm lamp, very little ambient (owner: "too bright").
    float hemi=.026+.020*saturate(normal.y*.5+.5);
    float3 lamp=float3(2.7,1.55,.68)*attenuation*visibility;
    float3 doorway=float3(-1.8,1.85,-1.8)-world;
    float fill=saturate(dot(normalize(normal),normalize(doorway)))/(1+.16*dot(doorway,doorway));
    float3 lighting=float3(.70,.79,1.0)*(hemi+.07*fill)+lamp*ndotl;
    float3 viewEye=-mul(m_V,float4(world,1)).xyz;
    float3 viewDirection=normalize(mul(viewEye,(float3x3)m_V));
    float3 halfDirection=normalize(normalize(delta)+viewDirection);
    float specular=pow(saturate(dot(normal,halfDirection)),lerp(12,72,gloss))*gloss*.3*ndotl;
    float3 radiance=max(0,pow(max(diffuse,0),2.2)*lighting+lamp*specular);
    // Filmic shoulder keeps lantern-lit plaster and metal from clipping.
    radiance=saturate((radiance*(2.51*radiance+.03))/(radiance*(2.43*radiance+.59)+.14));
    return pow(radiance,1/2.2);
}
// Hovered interactive object: x = object id (1..5, 0 none), y = strength 0..1.
float4 menu_room_hover;
// Bronze (#B08D57) rim along the silhouette plus a slight lift, so the object
// under the cursor reads as outlined.
float3 menu_highlight(float3 color, float3 normal, float3 world, float id)
{
    if (menu_room_hover.y <= 0 || abs(id-menu_room_hover.x) > .5) return color;
    float3 viewEye=-mul(m_V,float4(world,1)).xyz;
    float3 viewDirection=normalize(mul(viewEye,(float3x3)m_V));
    float rim=pow(1-saturate(abs(dot(normalize(normal),viewDirection))),2.2);
    const float3 bronze=float3(.690,.553,.341);
    return color+bronze*(rim*1.35+.10)*menu_room_hover.y;
}
// Soft vignette: corners fall to ~45 %.
float menu_vignette(float4 position)
{
    float2 uv=position.xy/screen_res.xy-.5;
    return 1-.55*smoothstep(.30,.80,length(uv*float2(1,.85)));
}
