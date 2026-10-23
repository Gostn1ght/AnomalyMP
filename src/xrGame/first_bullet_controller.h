#ifndef FIRST_BULLET_CONTROLLER
#define FIRST_BULLET_CONTROLLER

class first_bullet_controller
{
private:
	float m_fire_dispertion;
public:
	first_bullet_controller();
	void load(shared_str const& section);
	inline float get_fire_dispertion() const { return m_fire_dispertion; };
	inline void set_fire_dispertion(float val) { m_fire_dispertion = val; };
}; //class first_bullet_controller

#endif //#ifndef FIRST_BULLET_CONTROLLER
