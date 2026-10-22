#include "stdafx.h"
#include "dxThunderboltDescRender.h"

namespace
{
// Lightning models by file name. Weathers name the same few models in many
// thunderbolt descriptions; each was loaded and stripified again (1.5 s of the
// start in GAMMA, doc 151). The model is only read when a bolt is drawn.
struct SharedModel
{
	IRender_DetailModel* model;
	u32 refs;
};

xr_map<shared_str, SharedModel>& thunderbolt_models()
{
	static xr_map<shared_str, SharedModel> models;
	return models;
}

IRender_DetailModel* acquire(shared_str const& name)
{
	xr_map<shared_str, SharedModel>& models = thunderbolt_models();
	auto it = models.find(name);
	if (it == models.end())
	{
		IReader* F = FS.r_open("$game_meshes$", name.c_str());
		R_ASSERT2(F, "Empty 'lightning_model'.");
		IRender_DetailModel* model = ::RImplementation.model_CreateDM(F);
		FS.r_close(F);
		it = models.emplace(name, SharedModel{model, 0}).first;
	}
	++it->second.refs;
	return it->second.model;
}

void release(shared_str const& name)
{
	xr_map<shared_str, SharedModel>& models = thunderbolt_models();
	auto it = models.find(name);
	R_ASSERT2(it != models.end(), "Thunderbolt model released twice");
	if (--it->second.refs == 0)
	{
		::RImplementation.model_Delete(it->second.model);
		models.erase(it);
	}
}
}

void dxThunderboltDescRender::Copy(IThunderboltDescRender& _in)
{
	dxThunderboltDescRender& other = *((dxThunderboltDescRender*)&_in);
	if (this == &other)
		return;
	if (l_model)
		release(m_model_name);
	m_model_name = other.m_model_name;
	l_model = other.l_model ? acquire(m_model_name) : nullptr;
}

void dxThunderboltDescRender::CreateModel(LPCSTR m_name)
{
	if (l_model)
		release(m_model_name);
	m_model_name = m_name;
	l_model = acquire(m_model_name);
}

void dxThunderboltDescRender::DestroyModel()
{
	if (!l_model)
		return;
	release(m_model_name);
	l_model = nullptr;
}
