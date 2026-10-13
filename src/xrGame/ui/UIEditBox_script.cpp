#include "pch_script.h"
#include "UIEditBox.h"

using namespace luabind;

static void resize_edit_box_script(CUIEditBox* edit, Fvector2 size)
{
	// Resize the frame as well as the input/hit area, preserving its text.
	edit->InitCustomEdit(edit->GetWndPos(), size);
}

#pragma optimize("s",on)
void CUIEditBox::script_register(lua_State* L)
{
	module(L)
	[
		class_<CUICustomEdit, CUIWindow>("CUICustomEdit")
		.def("SetText", &CUICustomEdit::SetText)
		.def("GetText", &CUICustomEdit::GetText)
		.def("CaptureFocus", &CUICustomEdit::CaptureFocus)
		.def("SetNextFocusCapturer", &CUICustomEdit::SetNextFocusCapturer),

		class_<CUIEditBox, CUICustomEdit>("CUIEditBox")
		.def(constructor<>())
		.def("SetWndSize", &resize_edit_box_script)
		.def("InitTexture", &CUIEditBox::InitTexture)
	];
}
