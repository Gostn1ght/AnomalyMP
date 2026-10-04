#pragma once

// Shared by game UI and renderer: projection/hit targets use the same camera.
// Include after the engine PCH (Fvector/Fmatrix and ENGINE_API).
namespace menu_room
{
ENGINE_API void focus(int object); // -1 overview, 0 map, 1 PDA, 2 backpack, 3 safe, 4 door
ENGINE_API void reset();
ENGINE_API bool ready();
ENGINE_API void matrices(Fmatrix& view, Fmatrix& projection);
ENGINE_API Fvector interaction(int object);
ENGINE_API Fvector lamp_position();
ENGINE_API Fvector seat_position();
}
