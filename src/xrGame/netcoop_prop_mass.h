#pragma once
#include <algorithm>
#include <cmath>
#include <string_view>

namespace netcoop_prop_mass
{
enum class Kind { other, wood_box, metal_box, barrel };
inline Kind classify(std::string_view visual)
{
    if (visual == "dynamics\\box\\box_wood_01" || visual == "dynamics\\box\\box_wood_02") return Kind::wood_box;
    if (visual == "dynamics\\box\\box_metall_01") return Kind::metal_box;
    if (visual == "dynamics\\balon\\bochka_close" || visual == "dynamics\\balon\\bochka_open" ||
        visual == "dynamics\\balon\\bochka_fuel" || visual == "dynamics\\balon\\bochka_close_1") return Kind::barrel;
    return Kind::other;
}
inline float shell(Kind kind, float x, float y, float z)
{
    if (kind == Kind::other || !std::isfinite(x) || !std::isfinite(y) || !std::isfinite(z) ||
        x <= 0 || y <= 0 || z <= 0 || x > 5 || y > 5 || z > 5) return 0;
    // Dry wooden walls: 12 mm, 600 kg/m3. Steel sheet: 1.5 mm, 7850 kg/m3.
    // Dimensions come from the actual model rather than its editor's 100 kg.
    const float thickness = kind == Kind::wood_box ? 0.012f : 0.0015f;
    const float density = kind == Kind::wood_box ? 600.f : 7850.f;
    float material_volume;
    if (kind == Kind::barrel)
    {
        const float radius = (x + z) * 0.25f;
        material_volume = 2.f * 3.14159265358979323846f * radius * (radius + y) * thickness;
    }
    else
        material_volume = x * y * z - std::max(0.f, x - 2.f * thickness) *
            std::max(0.f, y - 2.f * thickness) * std::max(0.f, z - 2.f * thickness);
    return std::max(1.f, std::min(200.f, material_volume * density));
}
inline bool valid_total(float base, float total)
{
    return std::isfinite(base) && std::isfinite(total) && base > 0 && total >= base && total <= base + 500.f;
}
}
