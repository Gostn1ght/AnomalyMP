#pragma once
#include <cstring>

// Small server-approved presentation vocabulary; no client-selected motion,
// inventory mutation, RP input lock, or protocol enum renumbering.
namespace netcoop_consumption
{
inline const char* motion(unsigned kind)
{
    static const char* const names[] = {
        "banka_anim_use_medkit", "banka_anim_use_bandage", "banka_anim_use_antirad",
        "banka_anim_use_energy", "banka_anim_use_universal", "banka_anim_use_vodka"
    };
    return kind < 6 ? names[kind] : nullptr;
}
inline unsigned kind(const char* section, const char* category)
{
    if (!section || !category) return 255;
    if (!std::strcmp(category,"i_medical"))
    {
        if (!std::strncmp(section,"bandage",7)) return 1;
        if (!std::strncmp(section,"antirad",7)) return 2;
        return 0;
    }
    if (!std::strcmp(category,"i_drink"))
        return std::strstr(section,"vodka") || std::strstr(section,"beer") ||
            std::strstr(section,"wine") || std::strstr(section,"whisk") ? 5 : 3;
    return !std::strcmp(category,"i_food") || !std::strcmp(category,"i_mutant_raw") ||
        !std::strcmp(category,"i_mutant_cooked") ? 4 : 255;
}
inline bool decimal(const char*& cursor, unsigned limit, unsigned& result)
{
    result=0;
    if (!cursor || *cursor<'0' || *cursor>'9') return false;
    do
    {
        unsigned digit=unsigned(*cursor-'0');
        if (digit>limit || result>(limit-digit)/10) return false;
        result=result*10+digit;
        ++cursor;
    } while (*cursor>='0' && *cursor<='9');
    if (*cursor!='|') return false;
    ++cursor;
    return true;
}
inline bool parse(const char* data, unsigned& actor, unsigned& action, const char*& name)
{
    if (!decimal(data,65534,actor) || !decimal(data,5,action)) return false;
    name=data;
    const auto size=std::strlen(name);
    if (!size || size>255) return false;
    for (const char* p=name;*p;++p) if (static_cast<unsigned char>(*p)<32) return false;
    return true;
}
}
