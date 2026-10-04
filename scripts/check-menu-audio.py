"""Exercise actual legacy menu audio methods; native builds are CI-only."""
from pathlib import Path
from tempfile import TemporaryDirectory
import os
import subprocess

if os.environ.get('GITHUB_ACTIONS') != 'true':
    raise SystemExit('Native checks must run in GitHub Actions')
root = Path(__file__).resolve().parents[1]
audio = (root/'src/xrGame/ui/MMSound.cpp').read_text()
source = r'''
#include <cassert>
#include <cstring>
#include <cstdio>
#include <string>
#include <vector>
using string_path = char[260];
#define VERIFY(x) assert(x)
constexpr int st_Music=1, sg_SourceType=1, sm_Intro=1;
struct { const char* Params="-netcoop"; } Core;
struct { bool paused=false; bool Paused() { return paused; } } Device;
struct { bool exist(const char*,const char*) { return true; } } FS;
void strconcat(size_t n,char* p,const char* a,const char* b) { snprintf(p,n,"%s%s",a,b); }
struct Sound {
 bool active=false; int plays=0;
 void create(const char*,int,int) {}
 void play(void*,int) { active=true;++plays; }
 void stop() { active=false; }
 bool _feedback() { return active; }
};
struct CMMSound {
 std::vector<std::string> m_play_list={"music\\original_menu"};
 bool m_bRandom=false;
 struct { int randI(size_t) { return 0; } } m_random;
 Sound m_music_stereo;
 void music_Play();void music_Update();void music_Stop();
};
'''
source += audio[audio.index('void CMMSound::music_Play()'):audio.index('void CMMSound::all_Stop()')]
source += r'''
int main() {
 CMMSound s;
 s.music_Play();s.music_Update();assert(s.m_music_stereo.plays==0);
 Core.Params="-noprefetch";s.music_Play();assert(s.m_music_stereo.plays==1);
 s.music_Update();assert(s.m_music_stereo.plays==1);
 s.music_Stop();s.music_Update();assert(s.m_music_stereo.plays==2);
 Core.Params="-netcoop -noprefetch";Device.paused=true;
 s.music_Update();assert(!s.m_music_stereo.active && s.m_music_stereo.plays==2);
 s.music_Play();assert(s.m_music_stereo.plays==2);
}
'''
with TemporaryDirectory(prefix='menu-audio-') as tmp:
    cpp = Path(tmp)/'check.cpp'
    exe = Path(tmp)/'check'
    cpp.write_text(source)
    subprocess.run(['g++','-std=c++17',str(cpp),'-o',str(exe)],check=True)
    subprocess.run([str(exe)],check=True)
print('Actual legacy menu audio: Lost Zone startup stays silent; original freeplay playback and pause remain functional PASS')
