#include "stdafx.h"
#include "Text_Console.h"
#include "line_editor.h"

extern char const* const ioc_prompt;
extern char const* const ch_cursor;
int g_svTextConsoleUpdateRate = 1;

CTextConsole::CTextConsole()
{
	m_pMainWnd = NULL;
	m_hConsoleWnd = NULL;
	m_hLogWnd = NULL;
	m_hCommandWnd = NULL;
	m_originalCommandProc = NULL;
	m_hLogWndFont = NULL;
	m_hDC_LogWnd = NULL;
	m_hDC_LogWnd_BackBuffer = NULL;
	m_hBB_BM = NULL;

	m_bScrollLog = true;
	m_dwStartLine = 0;

	m_bNeedUpdate = false;
	m_host_window_ready = false;
	m_dwLastUpdateTime = GetTickCount();
	m_last_time = GetTickCount();
}

CTextConsole::~CTextConsole()
{
	m_pMainWnd = NULL;
}

//-------------------------------------------------------------------------------------------
LRESULT CALLBACK TextConsole_WndProc(HWND hWnd, UINT uMsg, WPARAM wParam, LPARAM lParam);

void CTextConsole::CreateConsoleWnd()
{
	HINSTANCE hInstance = (HINSTANCE)GetModuleHandle(0);
	//----------------------------------
	RECT cRc;
	GetClientRect(*m_pMainWnd, &cRc);
	INT lX = cRc.left;
	INT lY = cRc.top;
	INT lWidth = cRc.right - cRc.left;
	INT lHeight = cRc.bottom - cRc.top;
	//----------------------------------
	const char* wndclass = "TEXT_CONSOLE";

	// Register the windows class
	WNDCLASS wndClass = {
		0, TextConsole_WndProc, 0, 0, hInstance,
		NULL,
		LoadCursor(hInstance, IDC_ARROW),
		GetStockBrush(GRAY_BRUSH),
		NULL, wndclass
	};
	RegisterClass(&wndClass);

	// Set the window's initial style
	u32 dwWindowStyle = WS_CHILD | WS_VISIBLE | WS_CLIPCHILDREN;

	// Set the window's initial width
	RECT rc;
	SetRect(&rc, lX, lY, lWidth, lHeight);
	// AdjustWindowRect( &rc, dwWindowStyle, FALSE );

	// Create the render window
	m_hConsoleWnd = CreateWindow(wndclass, "XRAY Text Console", dwWindowStyle,
	                             lX, lY,
	                             lWidth, lHeight, *m_pMainWnd,
	                             0, hInstance, 0L);
	//---------------------------------------------------------------------------
	R_ASSERT2(m_hConsoleWnd, "Unable to Create TextConsole Window!");
};
//-------------------------------------------------------------------------------------------
LRESULT CALLBACK TextConsole_LogWndProc(HWND hWnd, UINT uMsg, WPARAM wParam, LPARAM lParam);

void CTextConsole::CreateLogWnd()
{
	HINSTANCE hInstance = (HINSTANCE)GetModuleHandle(0);
	//----------------------------------
	RECT cRc;
	GetClientRect(m_hConsoleWnd, &cRc);
	INT lX = cRc.left;
	INT lY = cRc.top;
	INT lWidth = cRc.right - cRc.left;
	INT lHeight = cRc.bottom - cRc.top;
	//----------------------------------
	const char* wndclass = "TEXT_CONSOLE_LOG_WND";

	// Register the windows class
	WNDCLASS wndClass = {
		0, TextConsole_LogWndProc, 0, 0, hInstance,
		NULL,
		LoadCursor(NULL, IDC_ARROW),
		GetStockBrush(BLACK_BRUSH),
		NULL, wndclass
	};
	RegisterClass(&wndClass);

	// Set the window's initial style
	u32 dwWindowStyle = WS_CHILD | WS_VISIBLE | WS_CLIPSIBLINGS | WS_CLIPCHILDREN;
	// u32 dwWindowStyleEx = WS_EX_CLIENTEDGE;

	// Set the window's initial width
	RECT rc;
	SetRect(&rc, lX, lY, lWidth, lHeight);
	// AdjustWindowRect( &rc, dwWindowStyle, FALSE );

	// Create the render window
	m_hLogWnd = CreateWindow(wndclass, "XRAY Text Console Log", dwWindowStyle,
	                         lX, lY,
	                         lWidth, lHeight, m_hConsoleWnd,
	                         0, hInstance, 0L);
	//---------------------------------------------------------------------------
	R_ASSERT2(m_hLogWnd, "Unable to Create TextConsole Window!");
	//---------------------------------------------------------------------------
	ShowWindow(m_hLogWnd, SW_SHOW);
	//-----------------------------------------------
	LOGFONT lf = {};
	lf.lfHeight = -12;
	lf.lfWidth = 0;
	lf.lfEscapement = 0;
	lf.lfOrientation = 0;
	lf.lfWeight = FW_NORMAL;
	lf.lfItalic = 0;
	lf.lfUnderline = 0;
	lf.lfStrikeOut = 0;
	lf.lfCharSet = DEFAULT_CHARSET;
	lf.lfOutPrecision = OUT_STRING_PRECIS;
	lf.lfClipPrecision = CLIP_STROKE_PRECIS;
	lf.lfQuality = DRAFT_QUALITY;
	lf.lfPitchAndFamily = VARIABLE_PITCH | FF_SWISS;
	xr_sprintf(lf.lfFaceName, sizeof(lf.lfFaceName), "");

	m_hLogWndFont = CreateFontIndirect(&lf);
	R_ASSERT2(m_hLogWndFont, "Unable to Create Font for Log Window");
	//------------------------------------------------
	m_hDC_LogWnd = GetDC(m_hLogWnd);
	R_ASSERT2(m_hDC_LogWnd, "Unable to Get DC for Log Window!");
	//------------------------------------------------
	m_hDC_LogWnd_BackBuffer = CreateCompatibleDC(m_hDC_LogWnd);
	R_ASSERT2(m_hDC_LogWnd_BackBuffer, "Unable to Create Compatible DC for Log Window!");
	//------------------------------------------------
	GetClientRect(m_hLogWnd, &cRc);
	lWidth = cRc.right - cRc.left;
	lHeight = cRc.bottom - cRc.top;
	//----------------------------------
	m_hBB_BM = CreateCompatibleBitmap(m_hDC_LogWnd, lWidth, lHeight);
	R_ASSERT2(m_hBB_BM, "Unable to Create Compatible Bitmap for Log Window!");
	//------------------------------------------------
	m_hOld_BM = (HBITMAP)SelectObject(m_hDC_LogWnd_BackBuffer, m_hBB_BM);
	//------------------------------------------------
	m_hPrevFont = (HFONT)SelectObject(m_hDC_LogWnd_BackBuffer, m_hLogWndFont);
	//------------------------------------------------
	SetTextColor(m_hDC_LogWnd_BackBuffer, RGB(255, 255, 255));
	SetBkColor(m_hDC_LogWnd_BackBuffer, RGB(1, 1, 1));
	//------------------------------------------------
	m_hBackGroundBrush = GetStockBrush(BLACK_BRUSH);
	UpdateWindow(m_hLogWnd);

	// The old GDI prompt depended on DirectInput's keyboard capture and could
	// not reliably accept text after focus changes. A native edit control keeps
	// command entry separate from the game's input receiver stack.
	m_hCommandWnd = CreateWindowExA(0, "EDIT", "",
		WS_CHILD | WS_VISIBLE | WS_TABSTOP | ES_AUTOHSCROLL,
		4, lHeight - 25, lWidth - 8, 23, m_hLogWnd, nullptr, hInstance, nullptr);
	R_ASSERT2(m_hCommandWnd, "Unable to create dedicated command input");
	SendMessage(m_hCommandWnd, WM_SETFONT, reinterpret_cast<WPARAM>(m_hLogWndFont), TRUE);
	SendMessage(m_hCommandWnd, EM_SETMARGINS, EC_LEFTMARGIN | EC_RIGHTMARGIN, MAKELPARAM(6, 6));
	SendMessage(m_hCommandWnd, EM_SETLIMITTEXT, CONSOLE_BUF_SIZE - 1, 0);
	SetWindowLongPtr(m_hCommandWnd, GWLP_USERDATA, reinterpret_cast<LONG_PTR>(this));
	m_originalCommandProc = reinterpret_cast<WNDPROC>(SetWindowLongPtr(m_hCommandWnd,
		GWLP_WNDPROC, reinterpret_cast<LONG_PTR>(&CTextConsole::CommandWndProc)));
}

LRESULT CALLBACK CTextConsole::CommandWndProc(HWND hWnd, UINT message, WPARAM wParam, LPARAM lParam)
{
	CTextConsole* console = reinterpret_cast<CTextConsole*>(GetWindowLongPtr(hWnd, GWLP_USERDATA));
	if (console && message == WM_KEYDOWN && wParam == VK_RETURN)
	{
		console->SubmitCommand();
		return 0;
	}
	if (message == WM_CHAR && wParam == '\r')
		return 0;
	return console && console->m_originalCommandProc
		? CallWindowProc(console->m_originalCommandProc, hWnd, message, wParam, lParam)
		: DefWindowProc(hWnd, message, wParam, lParam);
}

void CTextConsole::SubmitCommand()
{
	char command[CONSOLE_BUF_SIZE] = {};
	GetWindowTextA(m_hCommandWnd, command, sizeof(command));
	SetWindowTextA(m_hCommandWnd, "");
	ExecuteCommand(command, true);
	RefreshDisplay();
}

void CTextConsole::FocusCommandInput()
{
	if (m_hCommandWnd)
		SetFocus(m_hCommandWnd);
}

void CTextConsole::Initialize()
{
	inherited::Initialize();

	m_pMainWnd = &Device.m_hWnd;
	SetWindowTextA(*m_pMainWnd, "Lost Zone / AnomalyMP Dedicated Server");
	m_dwLastUpdateTime = GetTickCount();
	m_last_time = GetTickCount();

	CreateConsoleWnd();
	CreateLogWnd();

	ShowWindow(m_hConsoleWnd, SW_SHOW);
	UpdateWindow(m_hConsoleWnd);
	SetTimer(m_hLogWnd, 1, 100, nullptr);

	m_server_info.ResetData();
	RefreshDisplay();
	FocusCommandInput();
}

void CTextConsole::Destroy()
{
	if (m_hLogWnd)
		KillTimer(m_hLogWnd, 1);
	inherited::Destroy();
	if (m_hCommandWnd)
	{
		DestroyWindow(m_hCommandWnd);
		m_hCommandWnd = nullptr;
	}

	SelectObject(m_hDC_LogWnd_BackBuffer, m_hPrevFont);
	SelectObject(m_hDC_LogWnd_BackBuffer, m_hOld_BM);

	if (m_hBB_BM) DeleteObject(m_hBB_BM);
	if (m_hLogWndFont) DeleteObject(m_hLogWndFont);

	DeleteDC(m_hDC_LogWnd_BackBuffer);
	ReleaseDC(m_hLogWnd, m_hDC_LogWnd);

	DestroyWindow(m_hLogWnd);
	DestroyWindow(m_hConsoleWnd);
}

void CTextConsole::OnRender()
{
} //disable СConsole::OnRender()

void CTextConsole::OnPaint()
{
	RECT wRC;
	PAINTSTRUCT ps;
	BeginPaint(m_hLogWnd, &ps);
	if (!m_hDC_LogWnd || !m_hDC_LogWnd_BackBuffer || !m_hBB_BM)
	{
		EndPaint(m_hLogWnd, &ps);
		return;
	}

	GetClientRect(m_hLogWnd, &wRC);
	DrawLog(m_hDC_LogWnd_BackBuffer, &wRC);


	BitBlt(ps.hdc,
	       wRC.left, wRC.top,
	       wRC.right - wRC.left, wRC.bottom - wRC.top,
	       m_hDC_LogWnd_BackBuffer,
	       wRC.left, wRC.top,
	       SRCCOPY); //(FullUpdate) ? SRCCOPY : NOTSRCCOPY);
	/*
	 Msg ("URect - %d:%d - %d:%d", ps.rcPaint.left, ps.rcPaint.top, ps.rcPaint.right, ps.rcPaint.bottom);
	 */
	EndPaint(m_hLogWnd, &ps);
}

void CTextConsole::DrawLog(HDC hDC, RECT* pRect)
{
	TEXTMETRIC tm;
	GetTextMetrics(hDC, &tm);

	RECT wRC = *pRect;
	GetClientRect(m_hLogWnd, &wRC);
	FillRect(hDC, &wRC, m_hBackGroundBrush);

	int Width = wRC.right - wRC.left;
	int Height = wRC.bottom - wRC.top;
	wRC = *pRect;
	int y_top_max = (int)(0.42f * Height);

	//---------------------------------------------------------------------------------
	LPCSTR s_edt = ec().str_edit();
	LPCSTR s_cur = ec().str_before_cursor();

	u32 cur_len = xr_strlen(s_cur) + xr_strlen(ch_cursor) + 1;
	PSTR buf = (PSTR)_alloca(cur_len * sizeof(char));
	xr_strcpy(buf, cur_len, s_cur);
	xr_strcat(buf, cur_len, ch_cursor);
	buf[cur_len - 1] = 0;

	u32 cur0_len = xr_strlen(s_cur);

	int xb = 25;

	SetTextColor(hDC, RGB(255, 255, 255));
	TextOut(hDC, xb, Height - tm.tmHeight - 1, buf, cur_len - 1);
	buf[cur0_len] = 0;

	SetTextColor(hDC, RGB(0, 0, 0));
	TextOut(hDC, xb, Height - tm.tmHeight - 1, buf, cur0_len);


	SetTextColor(hDC, RGB(255, 255, 255));
	TextOut(hDC, 0, Height - tm.tmHeight - 3, ioc_prompt, xr_strlen(ioc_prompt)); // ">>> "
	SYSTEMTIME wall_time;
	GetLocalTime(&wall_time);
	string32 clock_text;
	xr_sprintf(clock_text, "%02u:%02u:%02u", wall_time.wHour, wall_time.wMinute, wall_time.wSecond);
	SetTextColor(hDC, RGB(100, 220, 220));
	TextOut(hDC, Width - 80, Height - tm.tmHeight - 3, clock_text, xr_strlen(clock_text));

	SetTextColor(hDC, (COLORREF)bgr2rgb(get_mark_color(mark11)));
	TextOut(hDC, xb, Height - tm.tmHeight - 3, s_edt, xr_strlen(s_edt));

	SetTextColor(hDC, RGB(205, 205, 225));
	u32 log_line = LogFile.size() - 1;
	string16 q, q2;
	itoa(log_line, q, 10);
	xr_strcpy(q2, sizeof(q2), "[");
	xr_strcat(q2, sizeof(q2), q);
	xr_strcat(q2, sizeof(q2), "]");
	u32 qn = xr_strlen(q2);

	TextOut(hDC, Width - 8 * qn, Height - tm.tmHeight - tm.tmHeight, q2, qn);

	int ypos = Height - tm.tmHeight - tm.tmHeight;
	for (int i = LogFile.size() - 1 - scroll_delta; i >= 0; --i)
	{
		ypos -= tm.tmHeight;
		if (ypos < y_top_max)
		{
			break;
		}
		LPCSTR ls = LogFile[i].c_str();

		if (!ls)
		{
			continue;
		}
		Console_mark cm = (Console_mark)ls[0];
		COLORREF c2 = (COLORREF)bgr2rgb(get_mark_color(cm));
		SetTextColor(hDC, c2);
		u8 b = (is_mark(cm)) ? 2 : 0;
		LPCSTR pOut = ls + b;

		BOOL res = TextOut(hDC, 10, ypos, pOut, xr_strlen(pOut));
		if (!res)
		{
			R_ASSERT2(0, "TextOut(..) return NULL");
		}
	}

	const u32 now = GetTickCount();
	if (g_pGameLevel && (now - m_last_time >= 100))
	{
		m_last_time = now;

		m_server_info.ResetData();
		g_pGameLevel->GetLevelInfo(&m_server_info);
	}

	ypos = 5;
	for (u32 i = 0; i < m_server_info.Size(); ++i)
	{
		SetTextColor(hDC, m_server_info[i].color);
		TextOut(hDC, 10, ypos, m_server_info[i].name, xr_strlen(m_server_info[i].name));

		ypos += tm.tmHeight;
		if (ypos > y_top_max)
		{
			break;
		}
	}
}

/*
void CTextConsole::IR_OnKeyboardPress( int dik ) !!!!!!!!!!!!!!!!!!!!!
{
m_bNeedUpdate = true;
inherited::IR_OnKeyboardPress( dik );
}
*/
void CTextConsole::OnFrame()
{
	inherited::OnFrame();
	// The dedicated server has no renderer-driven present loop for this window.
	const u32 now = GetTickCount();
	if (now - m_dwLastUpdateTime >= 100)
	{
		m_dwLastUpdateTime = now;
		RefreshDisplay();
	}
}

void CTextConsole::RefreshDisplay()
{
	if (!m_hLogWnd || !m_pMainWnd)
		return;

	// Device creation can replace the host window style after the child console
	// was created. Apply clipping once after the render device is ready, and
	// restore it if a later display reset removes it. Recalculate the non-client
	// area so DXGI stops painting over the console child windows.
	if (Device.b_is_Ready && (!m_host_window_ready ||
		!(GetWindowLongPtr(*m_pMainWnd, GWL_STYLE) & WS_CLIPCHILDREN)))
	{
		const LONG_PTR style = GetWindowLongPtr(*m_pMainWnd, GWL_STYLE);
		SetWindowLongPtr(*m_pMainWnd, GWL_STYLE, style | WS_CLIPCHILDREN);
		SetWindowPos(*m_pMainWnd, nullptr, 0, 0, 0, 0,
			SWP_NOMOVE | SWP_NOSIZE | SWP_NOZORDER | SWP_FRAMECHANGED);
		ShowWindow(m_hConsoleWnd, SW_SHOW);
		ShowWindow(m_hLogWnd, SW_SHOW);
		m_host_window_ready = true;
		Msg("[NetAnomaly] Dedicated console host style: 0x%Ix", static_cast<size_t>(style | WS_CLIPCHILDREN));
	}

	RECT parent_rect, child_rect;
	GetClientRect(*m_pMainWnd, &parent_rect);
	GetClientRect(m_hLogWnd, &child_rect);
	const int width = parent_rect.right - parent_rect.left;
	const int height = parent_rect.bottom - parent_rect.top;
	if (width > 0 && height > 0 &&
		(width != child_rect.right - child_rect.left || height != child_rect.bottom - child_rect.top))
	{
		HBITMAP new_bitmap = CreateCompatibleBitmap(m_hDC_LogWnd, width, height);
		if (new_bitmap)
		{
			HBITMAP old_bitmap = (HBITMAP)SelectObject(m_hDC_LogWnd_BackBuffer, new_bitmap);
			DeleteObject(old_bitmap);
			m_hBB_BM = new_bitmap;
			MoveWindow(m_hConsoleWnd, 0, 0, width, height, FALSE);
			MoveWindow(m_hLogWnd, 0, 0, width, height, FALSE);
		}
	}
	if (m_hCommandWnd && width > 12 && height > 28)
		MoveWindow(m_hCommandWnd, 4, height - 25, width - 8, 23, FALSE);
	RedrawWindow(m_hLogWnd, nullptr, nullptr, RDW_INVALIDATE | RDW_UPDATENOW);
}
