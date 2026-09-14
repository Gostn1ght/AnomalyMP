#include "../engine/overlay/src/xrNetServer/GammaNetPolicy.h"
#include "../engine/overlay/src/xrNetServer/GammaPeerAuth.h"
#include <cassert>
#include <iostream>
#include <random>
#include <vector>
#include <limits>

int main()
{
    using namespace gamma_net;
    const auto auth_test = std::filesystem::temp_directory_path() /
        ("gamma-auth-test-" + std::to_string(std::random_device{}()));
    std::filesystem::create_directory(auth_test);
    const std::string account(32, 'a'), content(64, 'b'), token(64, 'c');
    const auto role_file = auth_test / (account + ".role");
    assert(!account_is_admin(auth_test, account));
    { std::ofstream(role_file) << "GAMMA_ROLE_V3\n" << account << "\nadmin\n"; }
    assert(account_is_admin(auth_test, account));
    assert(!account_is_admin(auth_test, "../" + account));
    { std::ofstream(role_file) << "GAMMA_ROLE_V3\n" << account << "\nplayer\n"; }
    assert(!account_is_admin(auth_test, account)); // Revocation takes effect at the next command.
    { std::ofstream(role_file) << "GAMMA_ROLE_V3\n" << account << "\nadmin\nextra\n"; }
    assert(!account_is_admin(auth_test, account));
    { std::ofstream(auth_test / (token + ".ticket")) << "GAMMA_AUTH_V3\n" << account << '\n' << content << "\n1300\n"; }
    peer_ticket proof;
    assert(!inspect_ticket(auth_test, token, std::string(64, 'd'), content, 1000, proof));
    assert(!inspect_ticket(auth_test, token, content, content, 1300, proof));
    assert(inspect_ticket(auth_test, token, content, content, 1000, proof));
    assert(consume_ticket(proof));
    assert(!consume_ticket(proof));
    assert(!inspect_ticket(auth_test, token, content, content, 1000, proof));
    std::filesystem::remove(role_file);
    std::filesystem::remove(proof.consumed);
    std::filesystem::remove(auth_test);
    static_assert(max_players == 128 && max_client_states == 129, "capacity includes internal ALife host");
    assert(player_limit(nullptr) == 128);
    for (unsigned i = 1; i <= 128; ++i)
        assert(player_limit(("all/single/maxplayers=" + std::to_string(i) + "/portsv=1237").c_str()) == i);
    for (auto s : {"", "maxplayers=0", "maxplayers=-1", "maxplayers=129", "maxplayers=1x",
                   "maxplayers=9999999999999999999999999999999999", "xmaxplayers=3", "psw=maxplayers=5"})
        assert(player_limit(s) == 128);
    assert(newer(0, 0xffffffffu));
    assert(!newer(0xffffffffu, 0));
    assert(!newer(42, 42));
    assert(!newer(0x80000000u, 0));
    unsigned char actor[61] = {};
    assert(valid_coop_actor(actor, sizeof(actor)));
    assert(!valid_coop_actor(actor, sizeof(actor) - 1));
    float nan = std::numeric_limits<float>::quiet_NaN();
    std::memcpy(actor + 9, &nan, sizeof(nan));
    assert(!valid_coop_actor(actor, sizeof(actor)));
    std::memset(actor, 0, sizeof(actor));
    actor[59] = 1;
    assert(!valid_coop_actor(actor, sizeof(actor)));
    unsigned char physics_actor[138] = {};
    physics_actor[59] = 1;
    assert(valid_coop_actor(physics_actor, sizeof(physics_actor)));
    assert(!valid_coop_actor(physics_actor, sizeof(physics_actor) - 1));
    std::memcpy(physics_actor + 62, &nan, sizeof(nan));
    assert(!valid_coop_actor(physics_actor, sizeof(physics_actor)));
    unsigned char frame[] = {2, 0, 1, 0, 2, 0, 2, 0};
    assert(valid_frame(frame, sizeof(frame), true, 16384));
    for (auto size : {0u, 1u, 2u, 3u, 5u, 6u, 7u})
        assert(!valid_frame(frame, size, true, 16384));
    frame[4] = 255;
    assert(!valid_frame(frame, sizeof(frame), true, 16384));
    assert(!valid_frame(nullptr, 8, false, 16384));
    // Random hostile framing; ASan/UBSan in CI must detect any out-of-bounds access.
    std::mt19937 rng(0x47414d4d);
    for (int i = 0; i < 100000; ++i)
    {
        std::vector<unsigned char> bytes(rng() % 512);
        for (auto& b : bytes) b = static_cast<unsigned char>(rng());
        valid_frame(bytes.data(), bytes.size(), true, 16384);
    }
    std::cout << "Policy boundaries and 100000 hostile frames passed (not a gameplay/load test).\n";
}
