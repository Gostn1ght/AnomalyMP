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
	lf.lfHeight = -15;
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
	lf.lfQuality = CLEARTYPE_QUALITY;
	lf.lfPitchAndFamily = VARIABLE_PITCH | FF_SWISS;
	xr_strcpy(lf.lfFaceName, sizeof(lf.lfFaceName), "Segoe UI");

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
	SetBkColor(m_hDC_LogWnd_BackBuffer, RGB(11, 14, 20));
	//------------------------------------------------
	m_hBackGroundBrush = CreateSolidBrush(RGB(11, 14, 20));
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
	SetWindowTextA(*m_pMainWnd, "Lost Zone / Dedicated Server");
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
	if (m_hBackGroundBrush) DeleteObject(m_hBackGroundBrush);

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
	RECT bounds = *pRect;
	GetClientRect(m_hLogWnd, &bounds);
	FillRect(hDC, &bounds, m_hBackGroundBrush);
	SetBkMode(hDC, TRANSPARENT);
	TEXTMETRIC tm = {};
	GetTextMetrics(hDC, &tm);
	const int width = bounds.right;
	const int height = bounds.bottom;
	const int line_height = tm.tmHeight + 3;
	if (width <= 0 || height <= 0)
		return;

	const u32 now = GetTickCount();
	if (g_pGameLevel && now - m_last_time >= 100)
	{
		m_last_time = now;
		m_server_info.ResetData();
		g_pGameLevel->GetLevelInfo(&m_server_info);
	}

	const bool two_columns = width >= 680;
	const int rows = two_columns ? (m_server_info.Size() + 1) / 2 : m_server_info.Size();
	m_dashboard_bottom = 44 + rows * line_height;
	if (m_dashboard_bottom > height / 2)
		m_dashboard_bottom = height / 2;
	RECT dashboard = {0, 0, width, m_dashboard_bottom};
	HBRUSH panel_brush = CreateSolidBrush(RGB(21, 26, 36));
	FillRect(hDC, &dashboard, panel_brush);
	DeleteObject(panel_brush);
	RECT accent = {0, m_dashboard_bottom - 2, width, m_dashboard_bottom};
	HBRUSH accent_brush = CreateSolidBrush(RGB(56, 203, 208));
	FillRect(hDC, &accent, accent_brush);
	DeleteObject(accent_brush);
	SetTextColor(hDC, RGB(235, 241, 248));
	TextOutA(hDC, 12, 10, "LOST ZONE  /  DEDICATED SERVER", 30);
	SetTextColor(hDC, RGB(107, 172, 184));
	TextOutA(hDC, width - 120, 10, "LIVE STATUS", 11);
	const int rows_per_column = two_columns ? (m_server_info.Size() + 1) / 2 : m_server_info.Size();
	for (u32 i = 0; i < m_server_info.Size(); ++i)
	{
		const int column = two_columns && i >= rows_per_column ? 1 : 0;
		const int row = two_columns ? i % rows_per_column : i;
		RECT item = {12 + column * (width / 2), 36 + row * line_height,
			(column + 1) * (width / 2) - 14, 36 + (row + 1) * line_height};
		if (item.top + line_height > m_dashboard_bottom)
			break;
		SetTextColor(hDC, m_server_info[i].color);
		ExtTextOutA(hDC, item.left, item.top, ETO_CLIPPED, &item,
			m_server_info[i].name, xr_strlen(m_server_info[i].name), nullptr);
	}

	RECT toolbar = {0, m_dashboard_bottom, width, m_dashboard_bottom + 34};
	HBRUSH toolbar_brush = CreateSolidBrush(RGB(16, 20, 29));
	FillRect(hDC, &toolbar, toolbar_brush);
	DeleteObject(toolbar_brush);
	SetTextColor(hDC, RGB(143, 156, 176));
	TextOutA(hDC, 12, m_dashboard_bottom + 10, "EVENT STREAM", 12);
	static const char* filter_labels[] = {"ALL", "ERRORS", "WARNINGS", "INFO"};
	static const int filter_widths[] = {48, 76, 88, 54};
	int filter_x = 150;
	for (int i = 0; i < 4; ++i)
	{
		RECT chip = {filter_x, m_dashboard_bottom + 5, filter_x + filter_widths[i], m_dashboard_bottom + 29};
		HBRUSH chip_brush = CreateSolidBrush(i == m_log_filter ? RGB(33, 107, 118) : RGB(32, 39, 52));
		FillRect(hDC, &chip, chip_brush);
		DeleteObject(chip_brush);
		SetTextColor(hDC, i == m_log_filter ? RGB(244, 255, 255) : RGB(165, 177, 194));
		SIZE label_size = {};
		GetTextExtentPoint32A(hDC, filter_labels[i], xr_strlen(filter_labels[i]), &label_size);
		TextOutA(hDC, chip.left + (filter_widths[i] - label_size.cx) / 2,
			chip.top + (24 - label_size.cy) / 2, filter_labels[i], xr_strlen(filter_labels[i]));
		filter_x += filter_widths[i] + 6;
	}

	m_log_top = m_dashboard_bottom + 36;
	m_log_bottom = height - 36;
	if (m_log_bottom < m_log_top)
		m_log_bottom = m_log_top;
	m_log_visible_rows = (m_log_bottom - m_log_top) / line_height;
	if (m_log_visible_rows < 1)
		m_log_visible_rows = 1;
	// Other threads append to LogFile under the log lock.
	LogLock(true);
	m_log_count = 0;
	for (const auto& line : LogFile)
		if (MatchesLogFilter(line.c_str()))
			++m_log_count;
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
		SetTextColor(hDC, is_mark(mark) ? static_cast<COLORREF>(bgr2rgb(get_mark_color(mark))) : RGB(190, 199, 211));
		LPCSTR shown = is_mark(mark) && line[1] == ' ' ? line + 2 : line;
		RECT text = {12, y, width - 24, y + line_height};
		ExtTextOutA(hDC, text.left, text.top, ETO_CLIPPED, &text, shown, xr_strlen(shown), nullptr);
		y -= line_height;
	}
	RestoreDC(hDC, old_dc);
	LogLock(false);

	RECT track = {width - 14, m_log_top, width - 6, m_log_bottom};
	HBRUSH track_brush = CreateSolidBrush(RGB(31, 39, 50));
	FillRect(hDC, &track, track_brush);
	DeleteObject(track_brush);
	if (m_log_bottom > m_log_top)
	{
		const int track_height = m_log_bottom - m_log_top;
		int thumb_height = m_log_count ? track_height * m_log_visible_rows / m_log_count : track_height;
		if (thumb_height < 22) thumb_height = 22;
		if (thumb_height > track_height) thumb_height = track_height;
		const int thumb_top = m_log_top + (max_scroll ?
			(max_scroll - m_log_scroll) * (track_height - thumb_height) / max_scroll : 0);
		RECT thumb = {width - 14, thumb_top, width - 6, thumb_top + thumb_height};
		HBRUSH thumb_brush = CreateSolidBrush(RGB(69, 161, 174));
		FillRect(hDC, &thumb, thumb_brush);
		DeleteObject(thumb_brush);
	}

	RECT footer = {0, height - 34, width, height};
	HBRUSH footer_brush = CreateSolidBrush(RGB(18, 23, 33));
	FillRect(hDC, &footer, footer_brush);
	DeleteObject(footer_brush);
	SetTextColor(hDC, RGB(78, 210, 211));
	TextOutA(hDC, 10, height - 26, ">", 1);
	SYSTEMTIME wall_time;
	GetLocalTime(&wall_time);
	string32 clock_text;
	xr_sprintf(clock_text, "%02u:%02u:%02u", wall_time.wHour, wall_time.wMinute, wall_time.wSecond);
	SetTextColor(hDC, RGB(126, 155, 172));
	TextOutA(hDC, width - 76, height - 26, clock_text, xr_strlen(clock_text));
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
	const int max_scroll = m_log_count > m_log_visible_rows ? m_log_count - m_log_visible_rows : 0;
	m_log_scroll += rows;
	if (m_log_scroll < 0) m_log_scroll = 0;
	if (m_log_scroll > max_scroll) m_log_scroll = max_scroll;
	RefreshDisplay();
}

void CTextConsole::OnLogClick(int x, int y)
{
	if (y >= m_dashboard_bottom + 5 && y < m_dashboard_bottom + 29)
	{
		static const int widths[] = {48, 76, 88, 54};
		int filter_x = 150;
		for (int i = 0; i < 4; ++i)
		{
			if (x >= filter_x && x < filter_x + widths[i])
			{
				SetLogFilter(i);
				return;
			}
			filter_x += widths[i] + 6;
		}
	}
	RECT rect;
	GetClientRect(m_hLogWnd, &rect);
	if (x >= rect.right - 20 && y >= m_log_top && y < m_log_bottom)
	{
		m_dragging_scrollbar = true;
		SetCapture(m_hLogWnd);
		OnLogDrag(y);
		return;
	}
	if (y >= m_log_bottom)
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
	// Redrawing the log is synchronous GDI work on the main thread: only when
	// lines were added, at most twice a second (and once a second anyway for
	// the dashboard).
	const u32 now = GetTickCount();
	static size_t shown_lines = size_t(-1);
	LogLock(true);
	const size_t lines = LogFile.size();
	LogLock(false);
	if ((lines != shown_lines && now - m_dwLastUpdateTime >= 500) || now - m_dwLastUpdateTime >= 1000)
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
		MoveWindow(m_hCommandWnd, 28, height - 29, width - 114, 24, FALSE);
	RedrawWindow(m_hLogWnd, nullptr, nullptr, RDW_INVALIDATE | RDW_UPDATENOW);
}
