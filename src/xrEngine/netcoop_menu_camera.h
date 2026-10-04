#pragma once

// Shared by game UI and renderer: projection/hit targets use the same camera.
// Include after the engine PCH (Fvector/Fmatrix and ENGINE_API).
namespace menu_room
{
ENGINE_API void focus(int object); // -1 overview, 0 PDA, 1 radio, 2 character, 3 spare, 4 door
ENGINE_API void reset();
ENGINE_API bool ready();
ENGINE_API bool visible(); // true after a room frame has reached the swap chain
ENGINE_API void drawn();
ENGINE_API void presented();
ENGINE_API void matrices(Fmatrix& view, Fmatrix& projection);
ENGINE_API Fvector interaction(int object);
ENGINE_API Fvector lamp_position();
ENGINE_API Fvector seat_position();
ENGINE_API float seat_heading(); // world heading of the seated character (PI faces the camera)
// Object under a point in 1024 x 768 UI space (personal_room.pick boxes), or -1.
ENGINE_API int pick(float x, float y);
// Object to highlight (-1 none); the highlight fades in and out over ~0.12 s.
ENGINE_API void hover(int object);
// x = highlighted object id (object + 1, 0 none), y = strength 0..1.
ENGINE_API Fvector2 hover_state();
}
