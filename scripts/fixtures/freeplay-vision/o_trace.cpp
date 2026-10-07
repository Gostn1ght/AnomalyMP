	void Vision::o_trace(Fvector& P, float dt, float vis_threshold)
	{
		RQR.r_clear();
		xr_vector<feel_visible_Item>::iterator I = feel_visible.begin(), E = feel_visible.end();
		for (; I != E; I++)
		{
			if (0 == I->O->CFORM())
			{
				I->fuzzy = -1;
				continue;
			}

			// verify relation
			// if (positive(I->fuzzy) && I->O->Position().similar(I->cp_LR_dst,lr_granularity) && P.similar(I->cp_LR_src,lr_granularity))
			// continue;

			I->cp_LR_dst = I->O->Position();
			I->cp_LR_src = P;
			I->cp_LAST = I->O->get_last_local_point_on_mesh(I->cp_LP, I->bone_id);

			//
			Fvector D, OP = I->cp_LAST;
			D.sub(OP, P);
			if (fis_zero(D.magnitude()))
			{
				I->fuzzy = 1.f;
				continue;
			}

			float f = D.magnitude() + .2f;
			if (f > fuzzy_guaranteed)
			{
				D.div(f);
				// setup ray defs & feel params
				collide::ray_defs RD(P, D, f, CDB::OPT_CULL,
				                     collide::rq_target(
					                     collide::rqtStatic | /**/collide::rqtObject | /**/collide::rqtObstacle));
				SFeelParam feel_params(this, &*I, vis_threshold);
				// check cache
				if (I->Cache.result && I->Cache.similar(P, D, f))
				{
					// similar with previous query
					feel_params.vis = I->Cache_vis;
					// Log("cache 0");
				}
				else
				{
					float _u, _v, _range;
					if (CDB::TestRayTri(P, D, I->Cache.verts, _u, _v, _range, false) && (_range > 0 && _range < f))
					{
						feel_params.vis = 0.f;
						// Log("cache 1");
					}
					else
					{
						// cache outdated. real query.
						VERIFY(!fis_zero(RD.dir.magnitude()));

#ifdef SPATIAL_CHANGE
					    if (g_pGameLevel->ObjectSpace.RayQuery(RQR, RD, feel_vision_callback, &feel_params, feel_vision_test_callback, const_cast<CObject*>(m_owner)))
#else
					    if (g_pGameLevel->ObjectSpace.RayQuery(RQR, RD, feel_vision_callback, &feel_params, NULL, const_cast<CObject*>(m_owner)))
#endif
						{
							I->Cache_vis = feel_params.vis;
							I->Cache.set(P, D, f, TRUE);
						}
						else
						{
							// feel_params.vis = 0.f;
							// I->Cache_vis = feel_params.vis ;
							I->Cache.set(P, D, f, FALSE);
						}
						// Log("query");
					}
				}
				// Log("Vis",feel_params.vis);
				r_spatial.clear_not_free();
				g_SpatialSpace->q_ray(r_spatial, 0, STYPE_VISIBLEFORAI, P, D, f);

				RD.flags = CDB::OPT_ONLYFIRST;

				bool collision_found = false;
				xr_vector<ISpatial*>::const_iterator i = r_spatial.begin();
				xr_vector<ISpatial*>::const_iterator e = r_spatial.end();
				for (; i != e; ++i)
				{
					if (*i == m_owner)
						continue;

					if (*i == I->O)
						continue;

					CObject const* object = (*i)->dcast_CObject();

#ifdef SPATIAL_CHANGE
					if (object && object->spatial.type & STYPE_FEELVISIONIGNORE)
					{
						/* See through objects that have the flag. */
						continue;
					}
#endif

					RQR.r_clear();
					if (object && object->collidable.model && !object->collidable.model->_RayQuery(RD, RQR))
						continue;

					collision_found = true;
					break;
				}

				if (collision_found)
					feel_params.vis = 0.f;

				if (feel_params.vis < feel_params.vis_threshold)
				{
					// INVISIBLE, choose next point
					I->fuzzy -= fuzzy_update_novis * dt;
					clamp(I->fuzzy, -.5f, 1.f);
					I->cp_LP = I->O->get_new_local_point_on_mesh(I->bone_id);
				}
				else
				{
					// VISIBLE
					I->fuzzy += fuzzy_update_vis * dt;
					clamp(I->fuzzy, -.5f, 1.f);
				}
			}
			else
			{
				// VISIBLE, 'cause near
				I->fuzzy += fuzzy_update_vis * dt;
				clamp(I->fuzzy, -.5f, 1.f);
			}
		}
	}
