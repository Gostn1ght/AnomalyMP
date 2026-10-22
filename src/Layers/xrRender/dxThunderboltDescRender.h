#ifndef	dxThunderboltDescRender_included
#define	dxThunderboltDescRender_included
#pragma once

#include "..\..\Include\xrRender\ThunderboltDescRender.h"

class IRender_DetailModel;

class dxThunderboltDescRender : public IThunderboltDescRender
{
public:
	virtual void Copy(IThunderboltDescRender& _in);

	virtual void CreateModel(LPCSTR m_name);
	virtual void DestroyModel();
	//private:
public:
	// Shared by every description that names the same model file (doc 151).
	IRender_DetailModel* l_model = nullptr;
	shared_str m_model_name;
};

#endif	//	dxThunderboltDescRender_included
