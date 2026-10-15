# First DCP physical suspension adapter

`CarWheels.cpp` now reads optional DCP `suspension_spring_factor` and `suspension_damping_factor`, per wheel with `wheels_params` fallback, when initializing a real wheel joint. Both coefficients must be finite, positive and<=100; an invalid pair leaves the original model joint intact. Legacy models without these keys keep their existing physical and contact setup.

The adapter calls `CPhysicsJoint::SetJointSDfactors`, reaching the existing hinge2 ODE suspension ERP/CFM equations and live joint parameters. It does not reuse the separate contact/friction `spring_factor`/`damping_factor` keys, change the world integrator, set positions/velocities or silently pretend travel/inertia are implemented. The existing100Hz world step supplies the ERP/CFM conversion.

CI-only `check-native-car-suspension.py` executes the actual adapter and actual `CPHJoint::SetJointSDfactors` body, validating the resulting ERP/CFM, optional legacy policy, per-wheel overrides/global fallback, malformed values and non-wheel/null boundaries. Formula checks at0.01s/60Hz/120Hz do not claim driving stability or that the world's configured tick was changed.

The DCP model/profile candidates are still isolated audit inputs. `suspension_distance`, `suspension_force_inc`, `suspension_inertia`, mass/inertia verification, asset provenance, one real drivable DCP vehicle and T2–T9 acceptance remain OPEN. No foreign engine binary or supplied aircraft asset is installed by this adapter.
