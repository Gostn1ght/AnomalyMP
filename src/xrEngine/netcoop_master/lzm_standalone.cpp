// CI only: the engine master as a console test program (the same sources the
// engine links; .github/workflows/lostzone-master-cpp.yml). Not in the engine.
#include "lzm_config.h"

int wmain(int argc, wchar_t** argv)
{
    std::vector<std::wstring> args(argv + 1, argv + argc);
    if (!args.empty() && args[0] == L"-netcoop_master") args.erase(args.begin());
    return lzm::master_main(args);
}
