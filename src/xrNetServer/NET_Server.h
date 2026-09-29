#pragma once
#include "NET_Shared.h"

#ifdef USE_DIRECT_PLAY
#include "DirectPlayServer.h"
#define NET_SERVER_CLASS DirectPlayServer
#else
#include "SteamNetServer.h"
#define NET_SERVER_CLASS SteamNetServer
#endif // USE_DIRECT_PLAY

// NetAnomaly: game code names the transport IPureServer; the implementation is
// chosen at build time (GameNetworkingSockets by default, DirectPlay with
// USE_DIRECT_PLAY). Transport layer from NEAREST-STAGE Engine (Lost Zone).
typedef NET_SERVER_CLASS IPureServer;
