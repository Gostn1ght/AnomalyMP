// One warm ceiling lamp. Small PCF shadow filter for the isolated room.
Texture2D<float> s_menu_shadow;
float menu_visibility(float4 coordinate, float ndotl)
{
    float3 p=coordinate.xyz/coordinate.w;
    if(coordinate.w<=0 || any(p.xy<0) || any(p.xy>1) || p.z<0 || p.z>1) return 1;
    float bias=.0008+.002*(1-ndotl);
    float visible=0;
    [unroll] for(int y=0;y<2;y++) [unroll] for(int x=0;x<2;x++)
        visible += p.z-bias <= s_menu_shadow.SampleLevel(smp_nofilter,p.xy+(float2(x,y)-.5)/1024.,0) ? .25 : 0;
    return visible;
}
float3 menu_light(float3 diffuse, float3 normal, float3 world, float4 shadow)
{
    float3 delta=float3(-1.4,2.7,-1.6)-world;
    float distance2=dot(delta,delta);
    float ndotl=saturate(dot(normalize(normal),normalize(delta)));
    float visibility=menu_visibility(shadow,ndotl);
    float attenuation=1/(1+.07*distance2);
    float3 lighting=float3(.24,.25,.23)+float3(1.25,1.03,.74)*ndotl*attenuation*visibility;
    return pow(max(0,pow(max(diffuse,0),2.2)*lighting),1/2.2);
}
