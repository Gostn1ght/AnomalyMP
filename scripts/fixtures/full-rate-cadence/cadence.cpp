				const float d = c.id == CL->owner->ID ? 0.f : eye.distance_to(c.position);
				u32 every = c.full_rate ? 1 : d < 50.f ? 1 : d < 150.f ? 2 : d < 300.f ? 4 : 16;
				// Overload/budget never defer characters, their equipment or nearby objects.
				const bool close_by = c.full_rate || d < 50.f;
				if (!close_by) every *= far_scale;
