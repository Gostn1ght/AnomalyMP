#pragma once
#include "XR_IOConsole.h"
#include "IGame_Level.h"

class ENGINE_API CTextConsole : public CConsole
{
private:
	typedef CConsole inherited;

private:
	HWND* m_pMainWnd;

	HWND m_hConsoleWnd;
	void CreateConsoleWnd();

	HWND m_hLogWnd;
	void CreateLogWnd();
	HWND m_hCommandWnd;
	WNDPROC m_originalCommandProc;
	static LRESULT CALLBACK CommandWndProc(HWND hWnd, UINT message, WPARAM wParam, LPARAM lParam);
	void SubmitCommand();

	bool m_bScrollLog;
	u32 m_dwStartLine;
	int m_log_filter;
	int m_log_scroll;
	int m_log_count;
	int m_log_visible_rows;
	bool m_dragging_scrollbar;
	int m_dashboard_bottom;
	int m_log_top;
	int m_log_bottom;
	bool MatchesLogFilter(LPCSTR line) const;
	void SetLogFilter(int filter);
	void DrawLog(HDC hDC, RECT* pRect);

private:
	HFONT m_hLogWndFont;
	HFONT m_hPrevFont;
	HBRUSH m_hBackGroundBrush;

	HDC m_hDC_LogWnd;
	HDC m_hDC_LogWnd_BackBuffer;
	HBITMAP m_hBB_BM, m_hOld_BM;

	bool m_bNeedUpdate;
	bool m_host_window_ready;
	u32 m_dwLastUpdateTime;

	u32 m_last_time;
	CServerInfo m_server_info;

public:
	CTextConsole();
	virtual ~CTextConsole();

	virtual void Initialize();
	virtual void Destroy();

	virtual void OnRender();
	virtual void _BCL OnFrame();

	// virtual void IR_OnKeyboardPress (int dik);

	void AddString(LPCSTR string);
	void OnPaint();
	void RefreshDisplay();
	// RefreshDisplay at most once a second when lines were added, every 2 s
	// for the dashboard otherwise; nothing while minimised or hidden.
	void RefreshIfChanged();
	void FocusCommandInput();
	void ScrollLog(int rows);
	void OnLogClick(int x, int y);
	void OnLogDrag(int y);
	void EndLogDrag();
}; // class TextConsole

//extern ENGINE_API CTextConsole* TextConsole;
