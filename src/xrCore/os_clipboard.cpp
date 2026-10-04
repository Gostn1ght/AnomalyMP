////////////////////////////////////////////////////////////////////////////
// Module : os_clipboard.cpp
// Created : 21.02.2008
// Author : Evgeniy Sokolov
// Description : os clipboard class implementation
////////////////////////////////////////////////////////////////////////////

#include "stdafx.h"
#pragma hdrstop
#include "os_clipboard.h"

void os_clipboard::copy_to_clipboard(LPCSTR buf)
{
	if (!OpenClipboard(0))
		return;
	u32 handle_size = (xr_strlen(buf) + 1) * sizeof(char);
	HGLOBAL handle = GlobalAlloc(GHND, handle_size);
	if (!handle)
	{
		CloseClipboard();
		return;
	}

	char* memory = (char*)GlobalLock(handle);
	xr_strcpy(memory, handle_size, buf);
	GlobalUnlock(handle);
	EmptyClipboard();
	SetClipboardData(CF_TEXT, handle);
	CloseClipboard();
}

void os_clipboard::paste_from_clipboard(LPSTR buffer, u32 const& buffer_size)
{
	VERIFY(buffer);
	VERIFY(buffer_size > 0);
	buffer[0] = 0;

	if (!OpenClipboard(0))
		return;

	// UI text uses CP1251; CF_TEXT depends on the Windows system code page.
	// Prefer Unicode copied from browsers, mail clients and text editors.
	HGLOBAL hmem = GetClipboardData(CF_UNICODETEXT);
	const bool unicode = hmem != nullptr;
	if (!hmem) hmem = GetClipboardData(CF_TEXT);
	if (hmem)
	{
		const void* memory = GlobalLock(hmem);
		if (memory)
		{
			const SIZE_T bytes = GlobalSize(hmem);
			if (unicode)
			{
				const wchar_t* text = static_cast<const wchar_t*>(memory);
				SIZE_T count = 0, limit = bytes / sizeof(wchar_t);
				if (limit > buffer_size - 1) limit = buffer_size - 1;
				while (count < limit && text[count]) ++count;
				const int copied = count ? WideCharToMultiByte(1251, WC_NO_BEST_FIT_CHARS, text, int(count),
					buffer, int(buffer_size - 1), "?", nullptr) : 0;
				buffer[copied] = 0;
			}
			else
			{
				const char* text = static_cast<const char*>(memory);
				SIZE_T count = 0, limit = bytes;
				if (limit > buffer_size - 1) limit = buffer_size - 1;
				while (count < limit && text[count]) { buffer[count] = text[count]; ++count; }
				buffer[count] = 0;
			}
			GlobalUnlock(hmem);
		}
	}
	buffer[buffer_size - 1] = 0;
	for (u32 i = 0; buffer[i]; ++i)
	{
		const unsigned char c = static_cast<unsigned char>(buffer[i]);
		if (c < 32 || c == 127)
		{
			buffer[i] = ' ';
		}
	}

	CloseClipboard();
}

void os_clipboard::update_clipboard(LPCSTR string)
{
	if (!OpenClipboard(0))
		return;

	HGLOBAL handle = GetClipboardData(CF_TEXT);
	if (!handle)
	{
		CloseClipboard();
		copy_to_clipboard(string);
		return;
	}

	LPSTR memory = (LPSTR)GlobalLock(handle);
	int memory_length = (int)strlen(memory);
	int string_length = (int)strlen(string);
	int buffer_size = (memory_length + string_length + 1) * sizeof(char);
#ifndef _EDITOR
	LPSTR buffer = (LPSTR)_alloca(buffer_size);
#else // #ifndef _EDITOR
    LPSTR buffer = (LPSTR)xr_alloc<char>( buffer_size );
#endif // #ifndef _EDITOR
	xr_strcpy(buffer, buffer_size, memory);
	GlobalUnlock(handle);

	xr_strcat(buffer, buffer_size, string);
	CloseClipboard();
	copy_to_clipboard(buffer);
#ifdef _EDITOR
    xr_free (buffer);
#endif // #ifdef _EDITOR
}
