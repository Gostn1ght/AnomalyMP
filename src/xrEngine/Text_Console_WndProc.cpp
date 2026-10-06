#include "stdafx.h"
#include "Text_Console.h"

LRESULT CALLBACK TextConsole_WndProc(HWND hWnd, UINT uMsg, WPARAM wParam, LPARAM lParam)
{
	switch (uMsg)
	{
	case WM_LBUTTONDOWN:
		static_cast<CTextConsole*>(Console)->FocusCommandInput();
		return 0;
	case WM_SETCURSOR:
		SetCursor(LoadCursor(nullptr, IDC_ARROW));
		return TRUE;
	case WM_PAINT:
		{
			// return 0;
		}
		break;
	case WM_ERASEBKGND:
		{
			int x = 0;
			x = x;
			// CTextConsole* pTextConsole = (CTextConsole*)Console;
			// pTextConsole->OnPaint();
			// return 1;
		}
		break;
	case WM_NCPAINT:
		{
			// CTextConsole* pTextConsole = (CTextConsole*)Console;
			// pTextConsole->OnPaint();
			int x = 0;
			x = x;
			// return 0;
		}
		break;
	default:
		break;
	}
	return DefWindowProc(hWnd, uMsg, wParam, lParam);
}

LRESULT CALLBACK TextConsole_LogWndProc(HWND hWnd, UINT uMsg, WPARAM wParam, LPARAM lParam)
{
	switch (uMsg)
	{
	case WM_CTLCOLOREDIT:
		// Match the native command field to the black dedicated log window.
		SetTextColor(reinterpret_cast<HDC>(wParam), RGB(225, 225, 225));
		SetBkColor(reinterpret_cast<HDC>(wParam), RGB(0, 0, 0));
		return reinterpret_cast<LRESULT>(GetStockObject(BLACK_BRUSH));
	case WM_TIMER:
		// Kept for a busy main loop (level loading), but throttled: a full
		// synchronous repaint every 100 ms took 7% of the server's main
		// thread with 16 players (profile 2026-10-07).
		if (Console)
			static_cast<CTextConsole*>(Console)->RefreshIfChanged();
		return 0;
	case WM_LBUTTONDOWN:
		static_cast<CTextConsole*>(Console)->OnLogClick(static_cast<short>(LOWORD(lParam)), static_cast<short>(HIWORD(lParam)));
		return 0;
	case WM_MOUSEMOVE:
		static_cast<CTextConsole*>(Console)->OnLogDrag(static_cast<short>(HIWORD(lParam)));
		return 0;
	case WM_LBUTTONUP:
	case WM_CAPTURECHANGED:
		static_cast<CTextConsole*>(Console)->EndLogDrag();
		return 0;
	case WM_MOUSEWHEEL:
		static_cast<CTextConsole*>(Console)->ScrollLog(GET_WHEEL_DELTA_WPARAM(wParam) / WHEEL_DELTA * 3);
		return 0;
	case WM_SETCURSOR:
		SetCursor(LoadCursor(nullptr, IDC_ARROW));
		return TRUE;
	case WM_ERASEBKGND:
		return (LRESULT)1; // Say we handled it.

	case WM_PAINT:
		{
			CTextConsole* pTextConsole = (CTextConsole*)Console;
			pTextConsole->OnPaint();
			return (LRESULT)0; // Say we handled it.
		}
		break;
	default:
		break;
	}
	return DefWindowProc(hWnd, uMsg, wParam, lParam);
}
