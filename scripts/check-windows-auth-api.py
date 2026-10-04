"""Check actual mail/clipboard helpers against the Windows SDK before MSBuild."""
from pathlib import Path
from tempfile import TemporaryDirectory
import os
import subprocess

if os.environ.get('GITHUB_ACTIONS') != 'true':
    raise SystemExit('Native checks must run in GitHub Actions')
root = Path(__file__).resolve().parents[1]
firebase = (root/'src/xrGame/netcoop_firebase.inc').read_text(encoding='utf8')
clipboard = (root/'src/xrCore/os_clipboard.cpp').read_text(encoding='utf8')
source = r'''
#define NOMINMAX
#include <windows.h>
#include <windns.h>
#include <cassert>
#include <string>
#include <cwchar>
using u32 = unsigned;
#define VERIFY(x) assert(x)
namespace os_clipboard { void paste_from_clipboard(LPSTR, u32 const&); }
'''
source += firebase[firebase.index('static bool firebase_email_valid'):firebase.index('struct FirebaseTask')]
source += clipboard[clipboard.index('void os_clipboard::paste_from_clipboard'):clipboard.index('void os_clipboard::update_clipboard')]
with TemporaryDirectory(prefix='windows-auth-api-') as tmp:
    cpp = Path(tmp)/'check.cpp'
    cpp.write_text(source, encoding='utf8')
    subprocess.run(['cl','/nologo','/std:c++17','/EHsc','/Zs',str(cpp)],check=True)
print('Actual mail-domain and clipboard helpers match Windows SDK API types PASS; no network or clipboard access')
