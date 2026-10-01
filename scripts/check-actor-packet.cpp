#include "../src/xrNetServer/GammaNetPolicy.h"
#include <vector>
#include <string>
#include <limits>
#include <iostream>
#include <cstdlib>

static void require(bool result) { if (!result) std::abort(); }
static std::vector<unsigned char> packet(const std::string& visual, bool physics)
{
    std::vector<unsigned char> p(65, 0);
    for (unsigned i=59; i<65; ++i) p[i]=0xff;
    p.insert(p.end(), visual.begin(), visual.end());
    p.push_back(0); p.push_back(physics ? 1 : 0); p.push_back(0);
    if (physics) p.resize(p.size()+77, 0);
    return p;
}
int main()
{
    for (const auto& visual : {std::string(), std::string("actors\\stalker_neutral\\stalker_neutral_1.ogf"), std::string(200,'a')})
    for (bool physics : {false,true})
    {
        auto p=packet(visual, physics);
        require(gamma_net::valid_coop_actor(p.data(),p.size()));
        for (std::size_t length=0; length<p.size(); ++length)
            require(!gamma_net::valid_coop_actor(p.data(),length));
        auto extra=p;extra.push_back(1);
        require(!gamma_net::valid_coop_actor(extra.data(),extra.size()));
        auto count=p; count[66+visual.size()]=2;
        require(!gamma_net::valid_coop_actor(count.data(),count.size()));
        auto invalid=p;const float nan=std::numeric_limits<float>::quiet_NaN();
        std::memcpy(invalid.data()+13,&nan,sizeof(nan));
        require(!gamma_net::valid_coop_actor(invalid.data(),invalid.size()));
        if (physics) {
            std::memcpy(p.data()+p.size()-4,&nan,sizeof(nan));
            require(!gamma_net::valid_coop_actor(p.data(),p.size()));
        }
    }
    std::vector<unsigned char> old(61,0), unterminated(100,'a');
    require(!gamma_net::valid_coop_actor(old.data(),old.size()));
    require(!gamma_net::valid_coop_actor(unterminated.data(),unterminated.size()));
    std::cout << "PASS: equipment/visual packet variants, physics, truncation, invalid counts/floats and legacy rejection\n";
}
