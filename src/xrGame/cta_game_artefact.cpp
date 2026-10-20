#include "stdafx.h"
#include "cta_game_artefact.h"

void CtaGameArtefact::UpdateCLChild()
{
	inherited::UpdateCLChild();
	if (H_Parent())
		XFORM().set(H_Parent()->XFORM());
}
