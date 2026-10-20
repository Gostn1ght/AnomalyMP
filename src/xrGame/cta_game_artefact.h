////////////////////////////////////////////////////////////////////////////////
//	Module		:	cta_game_artefact.h
//	Description	:	Artefact class of the removed Capture The Artefact mode.
//					Lost Zone keeps the class id (art_cta) for configs and
//					scripts; the object is a plain artefact (doc 151).
////////////////////////////////////////////////////////////////////////////////

#ifndef CTA_GAME_ARTEFACT
#define CTA_GAME_ARTEFACT

#include "Artefact.h"

class CtaGameArtefact :
	public CArtefact
{
	typedef CArtefact inherited;
public:
	virtual void UpdateCLChild();
protected:
	virtual void CreateArtefactActivation() {}
}; //class CtaGameArtefact

#endif //CTA_GAME_ARTEFACT
