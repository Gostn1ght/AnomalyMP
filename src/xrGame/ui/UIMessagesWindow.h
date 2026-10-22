// File:		UIMessagesWindow.h
// Description:	Game log window (PDA messages)
// Created:		22.04.2005
// Author:		Serge Vynnychenko
// Mail:		narrator@gsc-game.kiev.ua
//
// Copyright 2005 GSC Game World

#pragma once

#include "UIWindow.h"

class CUIGameLog;
struct GAME_NEWS_DATA;

class CUIMessagesWindow : public CUIWindow
{
public:
	CUIMessagesWindow();
	virtual ~CUIMessagesWindow();

	void AddIconedPdaMessage(GAME_NEWS_DATA* news);
	void AddLogMessage(const shared_str& msg);
	virtual void Show(bool show);

protected:
	virtual void Init(float x, float y, float width, float height);

	CUIGameLog* m_pGameLog;
};
