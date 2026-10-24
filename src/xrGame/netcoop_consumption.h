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
// "actor|kind|name|section": kind 255 = no generic motion (the item may still
// have New Way's own); name and section are written back NUL-terminated.
inline bool parse(char* data, unsigned& actor, unsigned& action, const char*& name, const char*& section)
{
    const char* cursor=data;
    if (!decimal(cursor,65534,actor) || !decimal(cursor,255,action)) return false;
    char* bar=const_cast<char*>(std::strchr(cursor,'|'));
    if (!bar) return false;
    *bar=0;
    name=cursor; section=bar+1;
    const auto size=std::strlen(name), length=std::strlen(section);
    if (!size || size>255 || length>127) return false;
    for (const char* p=name;*p;++p) if (static_cast<unsigned char>(*p)<32) return false;
    for (const char* p=section;*p;++p)
        if (!((*p>='a' && *p<='z') || (*p>='A' && *p<='Z') || (*p>='0' && *p<='9') || *p=='_' || *p=='.' || *p=='-')) return false;
    return true;
}
}
