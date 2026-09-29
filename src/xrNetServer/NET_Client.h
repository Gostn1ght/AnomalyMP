#pragma once
#include "NET_Shared.h"

#ifdef USE_DIRECT_PLAY
#include "DirectPlayClient.h"
#define NET_CLIENT_CLASS DirectPlayClient
#else
#include "SteamNetClient.h"
#define NET_CLIENT_CLASS SteamNetClient
#endif // USE_DIRECT_PLAY

// NetAnomaly: game code names the transport IPureClient; the implementation is
// chosen at build time (GameNetworkingSockets by default, DirectPlay with
// USE_DIRECT_PLAY). Transport layer from NEAREST-STAGE Engine (Lost Zone).
typedef NET_CLIENT_CLASS IPureClient;
