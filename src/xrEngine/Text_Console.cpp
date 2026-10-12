#include "stdafx.h"
#include "Text_Console.h"
#include "line_editor.h"
#include "IGame_Level.h"
#include <shellapi.h>
#pragma comment(lib, "shell32.lib")

extern char const* const ioc_prompt;
extern char const* const ch_cursor;
int g_svTextConsoleUpdateRate = 1;

namespace
{
// Lost Zone palette, the same as the hoster panel's: near-black surfaces,
// one warm accent, status colours only where they mean something.
const COLORREF c_bg = RGB(10, 10, 11), c_surface = RGB(16, 16, 18), c_raised = RGB(24, 24, 27),
	c_hover = RGB(32, 32, 36), c_line = RGB(38, 38, 42), c_text = RGB(232, 230, 225),
	c_muted = RGB(140, 140, 145), c_dim = RGB(90, 90, 95), c_accent = RGB(217, 164, 65),
	c_green = RGB(76, 195, 138), c_amber = RGB(224, 168, 74), c_red = RGB(229, 83, 75);

enum
{
	act_tab = 1, act_log_filter, act_copy_log, act_logs_folder, act_player_filter, act_row,
	act_ban, act_unban, act_admin, act_unadmin, act_leader, act_unleader,
};
enum
{
	style_chip, style_chip_active, style_disabled, style_danger, style_confirm, style_tab, style_tab_active, style_primary,
};
enum { filter_all, filter_players, filter_leaders, filter_admins, filter_banned, filter_count };

void fill(HDC dc, const RECT& r, COLORREF color)
{
	SetBkColor(dc, color);
	ExtTextOutW(dc, 0, 0, ETO_OPAQUE, &r, nullptr, 0, nullptr);
}

// Game text (log lines, names) is in codepage 1251.
int widen(LPCSTR text, wchar_t* out, int size)
{
	const int n = MultiByteToWideChar(1251, 0, text ? text : "", -1, out, size);
	if (n <= 0)
	{
		out[0] = 0;
		return 0;
	}
	out[size - 1] = 0;
	return n - 1;
}

void text_w(HDC dc, int x, int y, const wchar_t* text, COLORREF color, const RECT* clip = nullptr)
{
	SetTextColor(dc, color);
	ExtTextOutW(dc, x, y, clip ? ETO_CLIPPED : 0, clip, text, UINT(wcslen(text)), nullptr);
}

void text_a(HDC dc, int x, int y, LPCSTR text, COLORREF color, const RECT* clip = nullptr)
{
	wchar_t wide[1024];
	const int n = widen(text, wide, 1024);
	SetTextColor(dc, color);
	ExtTextOutW(dc, x, y, clip ? ETO_CLIPPED : 0, clip, wide, n, nullptr);
}

int text_width(HDC dc, const wchar_t* text)
{
	SIZE size = {};
	GetTextExtentPoint32W(dc, text, int(wcslen(text)), &size);
	return size.cx;
}

struct FactionStyle
{
	LPCSTR id;
	const wchar_t* title;
	COLORREF color;
};
const FactionStyle factions[] = {
	{"stalker", L"\u041e\u0434\u0438\u043d\u043e\u0447\u043a\u0438", RGB(226, 196, 98)},
	{"dolg", L"\u0414\u043e\u043b\u0433", RGB(214, 76, 66)},
	{"freedom", L"\u0421\u0432\u043e\u0431\u043e\u0434\u0430", RGB(96, 190, 98)},
	{"csky", L"\u0427\u0438\u0441\u0442\u043e\u0435 \u041d\u0435\u0431\u043e", RGB(88, 160, 232)},
	{"ecolog", L"\u0423\u0447\u0451\u043d\u044b\u0435", RGB(110, 204, 204)},
	{"killer", L"\u041d\u0430\u0451\u043c\u043d\u0438\u043a\u0438", RGB(110, 132, 224)},
	{"army", L"\u0412\u043e\u0435\u043d\u043d\u044b\u0435", RGB(156, 168, 92)},
	{"bandit", L"\u0411\u0430\u043d\u0434\u0438\u0442\u044b", RGB(176, 128, 84)},
	{"monolith", L"\u041c\u043e\u043d\u043e\u043b\u0438\u0442", RGB(222, 222, 236)},
	{"renegade", L"\u0420\u0435\u043d\u0435\u0433\u0430\u0442\u044b", RGB(196, 112, 84)},
	{"greh", L"\u0413\u0440\u0435\u0445", RGB(176, 96, 176)},
	{"isg", L"ISG", RGB(124, 176, 146)},
	{"zombied", L"\u0417\u043e\u043c\u0431\u0438\u0440\u043e\u0432\u0430\u043d\u043d\u044b\u0435", RGB(130, 130, 130)},
};

const FactionStyle* faction_style(LPCSTR id)
{
	for (const FactionStyle& style : factions)
		if (id && !xr_strcmp(style.id, id))
			return &style;
	return nullptr;
}

void dark_title_bar(HWND wnd)
{
	// Windows 10 1809+ / 11; ignored elsewhere.
	if (HMODULE dwm = LoadLibraryA("dwmapi.dll"))
	{
		typedef HRESULT(WINAPI* set_attribute_t)(HWND, DWORD, LPCVOID, DWORD);
		if (set_attribute_t set = reinterpret_cast<set_attribute_t>(GetProcAddress(dwm, "DwmSetWindowAttribute")))
		{
			BOOL on = TRUE;
			if (FAILED(set(wnd, 20, &on, sizeof(on))))
				set(wnd, 19, &on, sizeof(on));
		}
	}
}

HFONT make_font(int height, int weight, LPCSTR face)
{
	LOGFONT lf = {};
	lf.lfHeight = height;
	lf.lfWeight = weight;
	lf.lfCharSet = DEFAULT_CHARSET;
	lf.lfOutPrecision = OUT_STRING_PRECIS;
	lf.lfClipPrecision = CLIP_STROKE_PRECIS;
	lf.lfQuality = CLEARTYPE_QUALITY;
	lf.lfPitchAndFamily = VARIABLE_PITCH | FF_SWISS;
	xr_strcpy(lf.lfFaceName, sizeof(lf.lfFaceName), face);
	return CreateFontIndirect(&lf);
}
} // namespace

CTextConsole::CTextConsole()
{
	m_pMainWnd = NULL;
	m_hConsoleWnd = NULL;
	m_hLogWnd = NULL;
	m_hCommandWnd = NULL;
	m_originalCommandProc = NULL;
	m_hLogWndFont = NULL;
	m_hTitleFont = NULL;
	m_hSmallFont = NULL;
	m_hDC_LogWnd = NULL;
	m_hDC_LogWnd_BackBuffer = NULL;
	m_hBB_BM = NULL;
	m_hBackGroundBrush = NULL;

	m_bScrollLog = true;
	m_dwStartLine = 0;
	m_log_filter = 0;
	m_log_scroll = 0;
	m_log_count = 0;
	m_log_visible_rows = 1;
	m_dragging_scrollbar = false;
	m_dashboard_bottom = 190;
	m_log_top = 226;
	m_log_bottom = 400;

	m_tab = 0;
	m_player_filter = filter_all;
	m_player_scroll = 0;
	m_player_visible_rows = 1;
	m_player_count = 0;
	m_players_time = 0;
	m_selected_login[0] = 0;
	m_selected_banned = false;
	m_confirm_action = 0;
	m_confirm_until = 0;
	m_notice[0] = 0;
	m_notice_until = 0;

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
		GetStockBrush(BLACK_BRUSH),
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
	m_hLogWndFont = make_font(-15, FW_NORMAL, "Segoe UI");
	m_hSmallFont = make_font(-13, FW_SEMIBOLD, "Segoe UI");
	m_hTitleFont = make_font(-21, FW_SEMIBOLD, "Bahnschrift");
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
	SetTextColor(m_hDC_LogWnd_BackBuffer, c_text);
	SetBkColor(m_hDC_LogWnd_BackBuffer, c_bg);
	//------------------------------------------------
	// The command field's background (WM_CTLCOLOREDIT).
	m_hBackGroundBrush = CreateSolidBrush(c_raised);
	UpdateWindow(m_hLogWnd);

	// The old GDI prompt depended on DirectInput's keyboard capture and could
	// not reliably accept text after focus changes. A native edit control keeps
	// command entry separate from the game's input receiver stack.
	m_hCommandWnd = CreateWindowExA(0, "EDIT", "",
		WS_CHILD | WS_VISIBLE | WS_TABSTOP | ES_AUTOHSCROLL,
		28, lHeight - 29, lWidth - 114, 24, m_hLogWnd, nullptr, hInstance, nullptr);
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
	if (console && message == WM_KEYDOWN && (wParam == VK_PRIOR || wParam == VK_NEXT))
	{
		console->ScrollLog(wParam == VK_PRIOR ? console->m_log_visible_rows : -console->m_log_visible_rows);
		return 0;
	}
	if (console && message == WM_MOUSEWHEEL)
	{
		console->ScrollLog(GET_WHEEL_DELTA_WPARAM(wParam) / WHEEL_DELTA * 3);
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
	// Several maps run at once: the title names this one (its log name and port).
	string256 title = "Lost Zone Server";
	string64 log_name = {}, port = {};
	if (LPCSTR arg = strstr(Core.Params, "-logname "))
		sscanf(arg + 9, "%63s", log_name);
	if (LPCSTR arg = strstr(Core.Params, "-netport "))
		sscanf(arg + 9, "%63s", port);
	LPCSTR map = strncmp(log_name, "srv_", 4) ? log_name : log_name + 4;
	if (map[0] || port[0])
		xr_sprintf(title, "Lost Zone Server - %s%s%s", map[0] ? map : "", map[0] && port[0] ? " : " : "", port);
	SetWindowTextA(*m_pMainWnd, title);
	dark_title_bar(*m_pMainWnd);
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
	if (m_hTitleFont) DeleteObject(m_hTitleFont);
	if (m_hSmallFont) DeleteObject(m_hSmallFont);
	if (m_hBackGroundBrush) DeleteObject(m_hBackGroundBrush);

	DeleteDC(m_hDC_LogWnd_BackBuffer);
	ReleaseDC(m_hLogWnd, m_hDC_LogWnd);

	DestroyWindow(m_hLogWnd);
	DestroyWindow(m_hConsoleWnd);
}

void CTextConsole::OnRender()
{
} //disable CConsole::OnRender()

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
	       SRCCOPY);
	EndPaint(m_hLogWnd, &ps);
}

// A chip, tab or button; returns its width. Disabled controls take no clicks.
int CTextConsole::AddButton(HDC dc, int x, int y, int height, const wchar_t* label, int action, int arg, int style)
{
	HGDIOBJ old_font = SelectObject(dc, m_hSmallFont);
	const int width = text_width(dc, label) + (style == style_tab || style == style_tab_active ? 16 : 24);
	RECT rect = {x, y, x + width, y + height};
	COLORREF back = c_raised, fore = c_muted;
	switch (style)
	{
	case style_chip_active: back = RGB(58, 45, 22); fore = c_accent; break;
	case style_disabled: back = c_surface; fore = c_dim; break;
	case style_danger: back = RGB(50, 22, 21); fore = c_red; break;
	case style_confirm: back = c_red; fore = RGB(20, 10, 10); break;
	case style_primary: back = RGB(58, 45, 22); fore = c_accent; break;
	case style_tab: back = c_surface; fore = c_muted; break;
	case style_tab_active: back = c_surface; fore = c_text; break;
	}
	fill(dc, rect, back);
	if (style == style_tab_active)
	{
		RECT underline = {x, y + height - 3, x + width, y + height};
		fill(dc, underline, c_accent);
	}
	SetBkMode(dc, TRANSPARENT);
	SIZE size = {};
	GetTextExtentPoint32W(dc, label, int(wcslen(label)), &size);
	text_w(dc, x + (width - size.cx) / 2, y + (height - size.cy) / 2 - (style == style_tab_active ? 1 : 0), label, fore);
	SelectObject(dc, old_font);
	if (style != style_disabled)
	{
		SButton button = {rect, action, arg};
		m_buttons.push_back(button);
	}
	return width;
}

void CTextConsole::DrawHeader(HDC dc, int width, int line_height)
{
	RECT bounds;
	GetClientRect(m_hLogWnd, &bounds);
	const u32 now = GetTickCount();
	if (g_pGameLevel && now - m_last_time >= 100)
	{
		m_last_time = now;
		m_server_info.ResetData();
		g_pGameLevel->GetLevelInfo(&m_server_info);
	}
	const bool two_columns = width >= 680;
	const int rows = two_columns ? (m_server_info.Size() + 1) / 2 : m_server_info.Size();
	m_dashboard_bottom = 50 + rows * line_height;
	if (m_dashboard_bottom > bounds.bottom / 3)
		m_dashboard_bottom = bounds.bottom / 3;
	RECT dashboard = {0, 0, width, m_dashboard_bottom};
	fill(dc, dashboard, c_bg);

	HGDIOBJ old_font = SelectObject(dc, m_hTitleFont);
	text_w(dc, 14, 10, L"LOST ZONE", c_accent);
	const int title_width = text_width(dc, L"LOST ZONE");
	SelectObject(dc, m_hSmallFont);
	text_w(dc, 26 + title_width, 17, L"\u0412\u042b\u0414\u0415\u041b\u0415\u041d\u041d\u042b\u0419 \u0421\u0415\u0420\u0412\u0415\u0420", c_muted);
	const bool running = g_pGameLevel != nullptr;
	const wchar_t* state = running ? L"\u0420\u0410\u0411\u041e\u0422\u0410\u0415\u0422" : L"\u0417\u0410\u0413\u0420\u0423\u0417\u041a\u0410";
	const int state_width = text_width(dc, state);
	RECT dot = {width - state_width - 34, 19, width - state_width - 26, 27};
	fill(dc, dot, running ? c_green : c_amber);
	text_w(dc, width - state_width - 16, 14, state, running ? c_green : c_amber);
	SelectObject(dc, old_font);

	const int rows_per_column = rows;
	for (u32 i = 0; i < m_server_info.Size(); ++i)
	{
		const int column = two_columns && int(i) >= rows_per_column ? 1 : 0;
		const int row = two_columns ? int(i) % (rows_per_column ? rows_per_column : 1) : int(i);
		RECT item = {14 + column * (width / 2), 44 + row * line_height,
			(column + 1) * (width / 2) - 14, 44 + (row + 1) * line_height};
		if (item.top + line_height > m_dashboard_bottom)
			break;
		const COLORREF color = m_server_info[i].color == RGB(255, 255, 255) ? c_text : m_server_info[i].color;
		text_a(dc, item.left, item.top, m_server_info[i].name, color, &item);
	}
	RECT line = {0, m_dashboard_bottom - 1, width, m_dashboard_bottom};
	fill(dc, line, c_line);
}

void CTextConsole::DrawLog(HDC hDC, RECT* pRect)
{
	RECT bounds;
	GetClientRect(m_hLogWnd, &bounds);
	const int width = bounds.right;
	const int height = bounds.bottom;
	if (width <= 0 || height <= 0)
		return;
	m_buttons.clear();
	fill(hDC, bounds, c_bg);
	SetBkMode(hDC, TRANSPARENT);
	SelectObject(hDC, m_hLogWndFont);
	TEXTMETRIC tm = {};
	GetTextMetrics(hDC, &tm);
	const int line_height = tm.tmHeight + 3;

	DrawHeader(hDC, width, line_height);

	// Tabs.
	const int tabs_top = m_dashboard_bottom;
	RECT tabs = {0, tabs_top, width, tabs_top + 40};
	fill(hDC, tabs, c_surface);
	int online = 0;
	for (const SConsolePlayer& player : m_players)
		online += player.online ? 1 : 0;
	wchar_t players_label[64];
	swprintf_s(players_label, L"\u0418\u0413\u0420\u041e\u041a\u0418  %d", online);
	RECT separator = {0, tabs_top + 39, width, tabs_top + 40};
	fill(hDC, separator, c_line);
	int x = 10;
	x += AddButton(hDC, x, tabs_top + 4, 36, L"\u0416\u0423\u0420\u041d\u0410\u041b", act_tab, 0, m_tab == 0 ? style_tab_active : style_tab) + 6;
	AddButton(hDC, x, tabs_top + 4, 36, players_label, act_tab, 1, m_tab == 1 ? style_tab_active : style_tab);

	const int content_top = tabs_top + 40;
	const int content_bottom = height - 36;
	SelectObject(hDC, m_hLogWndFont);
	if (m_tab == 1)
		DrawPlayersTab(hDC, content_top, width, content_bottom, line_height);
	else
		DrawLogTab(hDC, content_top, width, content_bottom, line_height);

	// Footer: command line, notices, clock.
	RECT footer = {0, height - 36, width, height};
	fill(hDC, footer, c_surface);
	RECT footer_line = {0, height - 36, width, height - 35};
	fill(hDC, footer_line, c_line);
	SelectObject(hDC, m_hLogWndFont);
	text_w(hDC, 12, height - 27, L">", c_accent);
	SYSTEMTIME wall_time;
	GetLocalTime(&wall_time);
	wchar_t clock_text[32];
	swprintf_s(clock_text, L"%02u:%02u:%02u", wall_time.wHour, wall_time.wMinute, wall_time.wSecond);
	text_w(hDC, width - 76, height - 27, clock_text, c_dim);
	if (m_notice[0] && GetTickCount() < m_notice_until)
	{
		// Shown over the end of the command field for a few seconds.
		SelectObject(hDC, m_hSmallFont);
		const int notice_width = text_width(hDC, m_notice);
		RECT back = {width - 96 - notice_width - 16, height - 31, width - 88, height - 5};
		fill(hDC, back, RGB(22, 44, 34));
		text_w(hDC, back.left + 8, height - 26, m_notice, c_green);
		SelectObject(hDC, m_hLogWndFont);
	}
}

void CTextConsole::DrawLogTab(HDC hDC, int top, int width, int bottom, int line_height)
{
	// Toolbar: level filters on the left, copy / folder on the right.
	static const wchar_t* filter_labels[] = {L"\u0412\u0421\u0415", L"\u041e\u0428\u0418\u0411\u041a\u0418", L"\u041f\u0420\u0415\u0414\u0423\u041f\u0420\u0415\u0416\u0414\u0415\u041d\u0418\u042f", L"\u0418\u041d\u0424\u041e"};
	int x = 12;
	for (int i = 0; i < 4; ++i)
		x += AddButton(hDC, x, top + 8, 26, filter_labels[i], act_log_filter, i,
			i == m_log_filter ? style_chip_active : style_chip) + 6;
	HGDIOBJ old_font = SelectObject(hDC, m_hSmallFont);
	const int copy_width = text_width(hDC, L"\u041a\u041e\u041f\u0418\u0420\u041e\u0412\u0410\u0422\u042c \u041b\u041e\u0413") + 24;
	const int folder_width = text_width(hDC, L"\u041f\u0410\u041f\u041a\u0410 \u041b\u041e\u0413\u041e\u0412") + 24;
	SelectObject(hDC, old_font);
	if (width - copy_width - folder_width - 30 > x)
	{
		AddButton(hDC, width - copy_width - 14, top + 8, 26, L"\u041a\u041e\u041f\u0418\u0420\u041e\u0412\u0410\u0422\u042c \u041b\u041e\u0413", act_copy_log, 0, style_primary);
		AddButton(hDC, width - copy_width - folder_width - 20, top + 8, 26, L"\u041f\u0410\u041f\u041a\u0410 \u041b\u041e\u0413\u041e\u0412", act_logs_folder, 0, style_chip);
	}

	m_log_top = top + 42;
	m_log_bottom = bottom - 4;
	if (m_log_bottom < m_log_top)
		m_log_bottom = m_log_top;
	m_log_visible_rows = (m_log_bottom - m_log_top) / line_height;
	if (m_log_visible_rows < 1)
		m_log_visible_rows = 1;
	// Other threads append to LogFile under the log lock.
	LogLock(true);
	// Counted incrementally: the whole log (up to 40000 lines) was filtered
	// on every repaint, under the log lock.
	static int counted_filter = -1;
	static size_t counted_lines = 0, counted_first = 0;
	static int counted = 0;
	const size_t first = LogFile.empty() ? 0 : size_t(LogFile.front().c_str()[0]) ^ LogFile.front().size();
	if (counted_filter != m_log_filter || counted_lines > LogFile.size() || counted_first != first)
	{
		// New filter, or the log dropped its oldest half: count again.
		counted_filter = m_log_filter;
		counted_lines = 0;
		counted = 0;
		counted_first = first;
	}
	for (; counted_lines < LogFile.size(); ++counted_lines)
		if (MatchesLogFilter(LogFile[counted_lines].c_str()))
			++counted;
	m_log_count = counted;
	const int max_scroll = m_log_count > m_log_visible_rows ? m_log_count - m_log_visible_rows : 0;
	if (m_log_scroll > max_scroll)
		m_log_scroll = max_scroll;

	const int old_dc = SaveDC(hDC);
	IntersectClipRect(hDC, 0, m_log_top, width - 19, m_log_bottom);
	int skipped = 0;
	int y = m_log_bottom - line_height;
	for (int i = static_cast<int>(LogFile.size()) - 1; i >= 0 && y >= m_log_top; --i)
	{
		LPCSTR line = LogFile[i].c_str();
		if (!MatchesLogFilter(line))
			continue;
		if (skipped++ < m_log_scroll)
			continue;
		const Console_mark mark = static_cast<Console_mark>(line[0]);
		const COLORREF color = is_mark(mark) ? static_cast<COLORREF>(bgr2rgb(get_mark_color(mark))) : RGB(198, 196, 190);
		LPCSTR shown = is_mark(mark) && line[1] == ' ' ? line + 2 : line;
		RECT text = {14, y, width - 24, y + line_height};
		text_a(hDC, text.left, text.top, shown, color, &text);
		y -= line_height;
	}
	RestoreDC(hDC, old_dc);
	LogLock(false);

	RECT track = {width - 13, m_log_top, width - 7, m_log_bottom};
	fill(hDC, track, c_raised);
	if (m_log_bottom > m_log_top)
	{
		const int track_height = m_log_bottom - m_log_top;
		int thumb_height = m_log_count ? track_height * m_log_visible_rows / m_log_count : track_height;
		if (thumb_height < 22) thumb_height = 22;
		if (thumb_height > track_height) thumb_height = track_height;
		const int thumb_top = m_log_top + (max_scroll ?
			(max_scroll - m_log_scroll) * (track_height - thumb_height) / max_scroll : 0);
		RECT thumb = {width - 13, thumb_top, width - 7, thumb_top + thumb_height};
		fill(hDC, thumb, RGB(120, 92, 40));
	}
}

bool CTextConsole::PlayerShown(const SConsolePlayer& player) const
{
	switch (m_player_filter)
	{
	case filter_players: return !player.banned && player.role == SConsolePlayer::role_player;
	case filter_leaders: return !player.banned && player.leader;
	case filter_admins: return !player.banned && player.admin;
	case filter_banned: return player.banned;
	default: return true;
	}
}

const SConsolePlayer* CTextConsole::SelectedPlayer() const
{
	if (!m_selected_login[0])
		return nullptr;
	for (const SConsolePlayer& player : m_players)
		if (player.banned == m_selected_banned && !xr_strcmp(player.login, m_selected_login))
			return &player;
	return nullptr;
}

void CTextConsole::DrawPlayersTab(HDC hDC, int top, int width, int bottom, int line_height)
{
	// Categories with counts.
	int counts[filter_count] = {};
	for (const SConsolePlayer& player : m_players)
	{
		counts[filter_all] += 1;
		if (player.banned) { counts[filter_banned] += 1; continue; }
		if (player.role == SConsolePlayer::role_player) counts[filter_players] += 1;
		if (player.leader) counts[filter_leaders] += 1;
		if (player.admin) counts[filter_admins] += 1;
	}
	static const wchar_t* filter_labels[filter_count] = {
		L"\u0412\u0421\u0415", L"\u0418\u0413\u0420\u041e\u041a\u0418", L"\u041b\u0418\u0414\u0415\u0420\u042b", L"\u0410\u0414\u041c\u0418\u041d\u0418\u0421\u0422\u0420\u0410\u0422\u041e\u0420\u042b", L"\u0417\u0410\u0411\u0410\u041d\u0415\u041d\u042b"};
	int x = 12;
	for (int i = 0; i < filter_count; ++i)
	{
		wchar_t label[64];
		swprintf_s(label, L"%ls  %d", filter_labels[i], counts[i]);
		x += AddButton(hDC, x, top + 8, 26, label, act_player_filter, i,
			i == m_player_filter ? style_chip_active : style_chip) + 6;
	}

	// Columns.
	const int col_login = width * 30 / 100, col_faction = width * 50 / 100, col_role = width * 70 / 100;
	const int col_ping = width - 90;
	const int header_top = top + 44;
	HGDIOBJ old_font = SelectObject(hDC, m_hSmallFont);
	text_w(hDC, 18, header_top, L"\u041d\u0418\u041a", c_dim);
	text_w(hDC, col_login, header_top, L"\u041b\u041e\u0413\u0418\u041d", c_dim);
	text_w(hDC, col_faction, header_top, L"\u0413\u0420\u0423\u041f\u041f\u0418\u0420\u041e\u0412\u041a\u0410", c_dim);
	text_w(hDC, col_role, header_top, L"\u0420\u041e\u041b\u042c", c_dim);
	text_w(hDC, col_ping, header_top, L"\u041f\u0418\u041d\u0413", c_dim);
	SelectObject(hDC, old_font);
	RECT header_line = {12, header_top + line_height + 2, width - 12, header_top + line_height + 3};
	fill(hDC, header_line, c_line);

	const int action_top = bottom - 48;
	const int rows_top = header_top + line_height + 6;
	const int row_height = line_height + 10;
	m_player_visible_rows = (action_top - rows_top) / row_height;
	if (m_player_visible_rows < 1)
		m_player_visible_rows = 1;
	m_player_count = 0;
	for (const SConsolePlayer& player : m_players)
		m_player_count += PlayerShown(player) ? 1 : 0;
	const int max_scroll = m_player_count > m_player_visible_rows ? m_player_count - m_player_visible_rows : 0;
	if (m_player_scroll > max_scroll) m_player_scroll = max_scroll;
	if (m_player_scroll < 0) m_player_scroll = 0;

	const SConsolePlayer* selected = SelectedPlayer();
	int shown = 0, y = rows_top;
	for (u32 i = 0; i < m_players.size() && y + row_height <= action_top; ++i)
	{
		const SConsolePlayer& player = m_players[i];
		if (!PlayerShown(player) || shown++ < m_player_scroll)
			continue;
		RECT row = {12, y, width - 12, y + row_height - 2};
		const bool is_selected = &player == selected;
		fill(hDC, row, is_selected ? c_hover : (shown % 2 ? c_bg : RGB(14, 14, 15)));
		if (is_selected)
		{
			RECT bar = {12, y, 15, y + row_height - 2};
			fill(hDC, bar, c_accent);
		}
		SButton button = {row, act_row, int(i)};
		m_buttons.push_back(button);

		const int text_y = y + (row_height - line_height) / 2;
		const FactionStyle* style = faction_style(player.faction);
		RECT name_clip = {22, y, col_login - 10, y + row_height};
		text_a(hDC, 22, text_y, player.name, player.banned ? c_dim : style ? style->color : c_text, &name_clip);
		RECT login_clip = {col_login, y, col_faction - 10, y + row_height};
		text_a(hDC, col_login, text_y, player.login, c_muted, &login_clip);
		RECT faction_clip = {col_faction, y, col_role - 10, y + row_height};
		if (style)
			text_w(hDC, col_faction, text_y, style->title, style->color, &faction_clip);
		else
			text_a(hDC, col_faction, text_y, player.faction[0] ? player.faction : "-", c_dim, &faction_clip);
		const wchar_t* role = player.banned ? L"\u0417\u0430\u0431\u0430\u043d\u0435\u043d" : player.admin ? L"\u0410\u0434\u043c\u0438\u043d\u0438\u0441\u0442\u0440\u0430\u0442\u043e\u0440" :
			player.leader ? L"\u041b\u0438\u0434\u0435\u0440" : player.deputy ? L"\u0417\u0430\u043c\u0435\u0441\u0442\u0438\u0442\u0435\u043b\u044c" : L"\u0418\u0433\u0440\u043e\u043a";
		const COLORREF role_color = player.banned ? c_red : player.admin ? c_accent :
			player.leader ? c_amber : player.deputy ? RGB(200, 172, 112) : c_muted;
		RECT role_clip = {col_role, y, col_ping - 10, y + row_height};
		text_w(hDC, col_role, text_y, role, role_color, &role_clip);
		if (player.online)
		{
			wchar_t ping[16];
			swprintf_s(ping, L"%u ms", player.ping);
			text_w(hDC, col_ping, text_y, ping, player.ping < 80 ? c_green : player.ping < 160 ? c_amber : c_red);
		}
		else
			text_w(hDC, col_ping, text_y, L"-", c_dim);
		y += row_height;
	}
	if (!m_player_count)
	{
		const wchar_t* empty = m_player_filter == filter_banned ? L"\u0417\u0430\u0431\u0430\u043d\u0435\u043d\u043d\u044b\u0445 \u043d\u0435\u0442" :
			m_players.empty() ? L"\u0421\u0435\u0439\u0447\u0430\u0441 \u043d\u0430 \u0441\u0435\u0440\u0432\u0435\u0440\u0435 \u043d\u0435\u0442 \u0438\u0433\u0440\u043e\u043a\u043e\u0432" : L"\u0412 \u044d\u0442\u043e\u0439 \u043a\u0430\u0442\u0435\u0433\u043e\u0440\u0438\u0438 \u043d\u0438\u043a\u043e\u0433\u043e \u043d\u0435\u0442";
		old_font = SelectObject(hDC, m_hSmallFont);
		text_w(hDC, (width - text_width(hDC, empty)) / 2, rows_top + 30, empty, c_dim);
		SelectObject(hDC, old_font);
	}

	// Actions for the selected player.
	RECT actions = {0, action_top, width, bottom};
	fill(hDC, actions, c_surface);
	RECT actions_line = {0, action_top, width, action_top + 1};
	fill(hDC, actions_line, c_line);
	const int button_top = action_top + 10;
	if (!selected)
	{
		old_font = SelectObject(hDC, m_hSmallFont);
		text_w(hDC, 16, button_top + 5, L"\u0412\u044b\u0431\u0435\u0440\u0438\u0442\u0435 \u0438\u0433\u0440\u043e\u043a\u0430 \u0432 \u0441\u043f\u0438\u0441\u043a\u0435, \u0447\u0442\u043e\u0431\u044b \u0443\u043f\u0440\u0430\u0432\u043b\u044f\u0442\u044c \u0438\u043c", c_dim);
		SelectObject(hDC, old_font);
		return;
	}
	RECT name_clip = {16, action_top, width * 28 / 100, bottom};
	const FactionStyle* style = faction_style(selected->faction);
	text_a(hDC, 16, button_top + 3, selected->name, selected->banned ? c_red : style ? style->color : c_text, &name_clip);
	const u32 now = GetTickCount();
	const bool confirming = m_confirm_action && now < m_confirm_until;
	const wchar_t* confirm = L"\u041f\u041e\u0414\u0422\u0412\u0415\u0420\u0414\u0418\u0422\u042c?";
	x = width * 28 / 100;
	if (selected->banned)
	{
		AddButton(hDC, x, button_top, 28, L"\u0420\u0410\u0417\u0411\u0410\u041d\u0418\u0422\u042c", act_unban, 0, style_primary);
		return;
	}
	x += AddButton(hDC, x, button_top, 28, confirming && m_confirm_action == act_ban ? confirm : L"\u0411\u0410\u041d \u041f\u041e \u0416\u0415\u041b\u0415\u0417\u0423",
		act_ban, 0, confirming && m_confirm_action == act_ban ? style_confirm : style_danger) + 8;
	if (selected->admin)
		x += AddButton(hDC, x, button_top, 28, L"\u0417\u0410\u0411\u0420\u0410\u0422\u042c \u0410\u0414\u041c\u0418\u041d\u041a\u0423", act_unadmin, 0, style_chip) + 8;
	else
		x += AddButton(hDC, x, button_top, 28, confirming && m_confirm_action == act_admin ? confirm : L"\u0414\u0410\u0422\u042c \u0410\u0414\u041c\u0418\u041d\u041a\u0423",
			act_admin, 0, confirming && m_confirm_action == act_admin ? style_confirm : style_chip) + 8;
	if (selected->leader)
		AddButton(hDC, x, button_top, 28, L"\u0417\u0410\u0411\u0420\u0410\u0422\u042c \u041b\u0418\u0414\u0415\u0420\u0410", act_unleader, 0, style_chip);
	else
		AddButton(hDC, x, button_top, 28, L"\u0414\u0410\u0422\u042c \u041b\u0418\u0414\u0415\u0420\u0410", act_leader, 0,
			selected->faction[0] && faction_style(selected->faction) ? style_chip : style_disabled);
}

bool CTextConsole::MatchesLogFilter(LPCSTR line) const
{
	if (!line || !line[0])
		return false;
	if (m_log_filter == 0)
		return true;
	const bool error = strstr(line, "ERROR") || strstr(line, "Error") ||
		strstr(line, "FATAL") || strstr(line, "Fatal") || strstr(line, "Exception");
	const bool warning = !error && (line[0] == mark0 || line[0] == mark1 ||
		strstr(line, "WARNING") || strstr(line, "Warning") || strstr(line, "Can't find"));
	return m_log_filter == 1 ? error : m_log_filter == 2 ? warning : !error && !warning;
}

void CTextConsole::SetLogFilter(int filter)
{
	if (filter < 0 || filter > 3)
		return;
	m_log_filter = filter;
	m_log_scroll = 0;
	RefreshDisplay();
}

void CTextConsole::ScrollLog(int rows)
{
	if (m_tab == 1)
	{
		m_player_scroll -= rows;
		const int max_scroll = m_player_count > m_player_visible_rows ? m_player_count - m_player_visible_rows : 0;
		if (m_player_scroll < 0) m_player_scroll = 0;
		if (m_player_scroll > max_scroll) m_player_scroll = max_scroll;
		RefreshDisplay();
		return;
	}
	const int max_scroll = m_log_count > m_log_visible_rows ? m_log_count - m_log_visible_rows : 0;
	m_log_scroll += rows;
	if (m_log_scroll < 0) m_log_scroll = 0;
	if (m_log_scroll > max_scroll) m_log_scroll = max_scroll;
	RefreshDisplay();
}

void CTextConsole::Notice(const wchar_t* text)
{
	wcsncpy_s(m_notice, text, _TRUNCATE);
	m_notice_until = GetTickCount() + 3500;
}

void CTextConsole::CopyLog()
{
	// The lines of the current filter, as shown, for pasting into a message.
	xr_string text;
	LogLock(true);
	for (u32 i = 0; i < LogFile.size(); ++i)
	{
		LPCSTR line = LogFile[i].c_str();
		if (!MatchesLogFilter(line))
			continue;
		const Console_mark mark = static_cast<Console_mark>(line[0]);
		text += is_mark(mark) && line[1] == ' ' ? line + 2 : line;
		text += "\r\n";
	}
	LogLock(false);
	const int length = MultiByteToWideChar(1251, 0, text.c_str(), int(text.size()), nullptr, 0);
	HGLOBAL memory = GlobalAlloc(GMEM_MOVEABLE, (size_t(length) + 1) * sizeof(wchar_t));
	if (!memory)
		return;
	wchar_t* wide = static_cast<wchar_t*>(GlobalLock(memory));
	MultiByteToWideChar(1251, 0, text.c_str(), int(text.size()), wide, length);
	wide[length] = 0;
	GlobalUnlock(memory);
	if (OpenClipboard(m_hLogWnd))
	{
		EmptyClipboard();
		if (SetClipboardData(CF_UNICODETEXT, memory))
			memory = nullptr; // the clipboard owns it now
		CloseClipboard();
	}
	if (memory)
	{
		GlobalFree(memory);
		Notice(L"\u041d\u0435 \u0443\u0434\u0430\u043b\u043e\u0441\u044c \u0441\u043a\u043e\u043f\u0438\u0440\u043e\u0432\u0430\u0442\u044c \u043b\u043e\u0433");
		return;
	}
	wchar_t notice[96];
	swprintf_s(notice, L"\u0421\u043a\u043e\u043f\u0438\u0440\u043e\u0432\u0430\u043d\u043e \u0441\u0442\u0440\u043e\u043a: %d", m_log_count);
	Notice(notice);
}

void CTextConsole::RunPlayerAction(int action)
{
	const SConsolePlayer* player = SelectedPlayer();
	if (!player)
		return;
	// Bans and new administrators take a second click within 4 s.
	const u32 now = GetTickCount();
	if ((action == act_ban || action == act_admin) && (m_confirm_action != action || now >= m_confirm_until))
	{
		m_confirm_action = action;
		m_confirm_until = now + 4000;
		return;
	}
	m_confirm_action = 0;
	string256 command = "";
	switch (action)
	{
	case act_ban: xr_sprintf(command, "sv_ban %s", player->login); break;
	case act_unban: xr_sprintf(command, "sv_unban %s", player->login); break;
	case act_admin: xr_sprintf(command, "sv_account_role %s admin", player->login); break;
	case act_unadmin: xr_sprintf(command, "sv_account_role %s player", player->login); break;
	case act_leader: xr_sprintf(command, "sv_leader %s %u %s", player->login, player->slot, player->faction); break;
	case act_unleader: xr_sprintf(command, "sv_leader %s %u off", player->login, player->slot); break;
	default: return;
	}
	ExecuteCommand(command, true);
	// The result is the last line of the log; show it in the footer too.
	LogLock(true);
	LPCSTR result = LogFile.empty() ? "" : LogFile.back().c_str();
	wchar_t wide[160];
	widen(is_mark(static_cast<Console_mark>(result[0])) && result[0] && result[1] == ' ' ? result + 2 : result, wide, 160);
	LogLock(false);
	Notice(wide);
	if (action == act_ban)
		m_selected_banned = true; // the row moves to the banned list
	else if (action == act_unban)
		m_selected_login[0] = 0;
	m_players_time = 0;
}

void CTextConsole::OnAction(int action, int arg)
{
	switch (action)
	{
	case act_tab:
		m_tab = arg;
		m_confirm_action = 0;
		m_players_time = 0;
		if (m_tab == 1 && g_pGameLevel)
		{
			m_players_time = GetTickCount();
			g_pGameLevel->GetConsolePlayers(m_players);
		}
		break;
	case act_log_filter:
		SetLogFilter(arg);
		return;
	case act_copy_log:
		CopyLog();
		break;
	case act_logs_folder:
		if (FS.path_exist("$logs$"))
			ShellExecuteA(*m_pMainWnd, "open", FS.get_path("$logs$")->m_Path, nullptr, nullptr, SW_SHOWNORMAL);
		break;
	case act_player_filter:
		m_player_filter = arg;
		m_player_scroll = 0;
		m_confirm_action = 0;
		break;
	case act_row:
		if (arg >= 0 && arg < int(m_players.size()))
		{
			xr_strcpy(m_selected_login, m_players[arg].login);
			m_selected_banned = m_players[arg].banned;
			m_confirm_action = 0;
		}
		break;
	default:
		RunPlayerAction(action);
		break;
	}
	RefreshDisplay();
}

void CTextConsole::OnLogClick(int x, int y)
{
	const POINT point = {x, y};
	for (int i = int(m_buttons.size()) - 1; i >= 0; --i)
		if (PtInRect(&m_buttons[i].rect, point))
		{
			// Copy: the vector is rebuilt by the repaint OnAction triggers.
			const SButton button = m_buttons[i];
			OnAction(button.action, button.arg);
			return;
		}
	RECT rect;
	GetClientRect(m_hLogWnd, &rect);
	if (m_tab == 0 && x >= rect.right - 20 && y >= m_log_top && y < m_log_bottom)
	{
		m_dragging_scrollbar = true;
		SetCapture(m_hLogWnd);
		OnLogDrag(y);
		return;
	}
	if (y >= rect.bottom - 36)
		FocusCommandInput();
}

void CTextConsole::OnLogDrag(int y)
{
	if (!m_dragging_scrollbar)
		return;
	const int max_scroll = m_log_count > m_log_visible_rows ? m_log_count - m_log_visible_rows : 0;
	const int track_height = m_log_bottom - m_log_top;
	if (track_height <= 0)
		return;
	m_log_scroll = max_scroll * (m_log_bottom - y) / track_height;
	if (m_log_scroll < 0) m_log_scroll = 0;
	if (m_log_scroll > max_scroll) m_log_scroll = max_scroll;
	RefreshDisplay();
}

void CTextConsole::EndLogDrag()
{
	if (m_dragging_scrollbar)
	{
		m_dragging_scrollbar = false;
		ReleaseCapture();
	}
}

void CTextConsole::OnFrame()
{
	inherited::OnFrame();
	// Once the level is up the title names it (Marsh logs as plain "srv").
	static shared_str titled;
	if (g_pGameLevel && m_pMainWnd && g_pGameLevel->name().size() && titled != g_pGameLevel->name())
	{
		titled = g_pGameLevel->name();
		string64 port = {};
		if (LPCSTR arg = strstr(Core.Params, "-netport "))
			sscanf(arg + 9, "%63s", port);
		string256 title;
		xr_sprintf(title, "Lost Zone Server - %s%s%s", titled.c_str(), port[0] ? " : " : "", port);
		SetWindowTextA(*m_pMainWnd, title);
	}
	// Players: every second while the tab is open, every 5 s for its counter.
	const u32 now = GetTickCount();
	if (!g_pGameLevel)
		m_players.clear();
	else if (!m_players_time || now - m_players_time >= (m_tab == 1 ? 1000u : 5000u))
	{
		m_players_time = now;
		g_pGameLevel->GetConsolePlayers(m_players);
	}
	RefreshIfChanged();
}

void CTextConsole::RefreshIfChanged()
{
	// The dedicated server has no renderer-driven present loop for this window.
	// Redrawing the log is synchronous GDI work on the main thread: only when
	// lines were added, at most twice a second (and once a second anyway for
	// the dashboard).
	const u32 now = GetTickCount();
	static size_t shown_lines = size_t(-1);
	LogLock(true);
	const size_t lines = LogFile.size();
	LogLock(false);
	// A minimised or hidden console is not painted at all: under load the
	// synchronous GDI calls waited up to 0.3 s (128-player test, 2026-10-06).
	if (m_pMainWnd && (IsIconic(*m_pMainWnd) || !IsWindowVisible(*m_pMainWnd)))
		return;
	if ((lines != shown_lines && now - m_dwLastUpdateTime >= 1000) || now - m_dwLastUpdateTime >= 2000)
	{
		m_dwLastUpdateTime = now;
		shown_lines = lines;
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
		dark_title_bar(*m_pMainWnd);
		m_host_window_ready = true;
		Msg("[Lost Zone] Dedicated console host style: 0x%Ix", static_cast<size_t>(style | WS_CLIPCHILDREN));
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
	if (m_hCommandWnd && width > 130 && height > 32)
		MoveWindow(m_hCommandWnd, 28, height - 30, width - 118, 25, FALSE);
	RedrawWindow(m_hLogWnd, nullptr, nullptr, RDW_INVALIDATE | RDW_UPDATENOW);
}
