"""Actual voice allocation/cleanup under source and partial-buffer failures (CI only)."""
from pathlib import Path
from tempfile import TemporaryDirectory
import os
import subprocess

if os.environ.get("GITHUB_ACTIONS") != "true":
    raise SystemExit("Native checks must run in GitHub Actions")
root = Path(__file__).resolve().parents[1]
voice = (root / "src/xrSound/SoundVoice.cpp").read_text(encoding="utf-8")

def function(signature):
    start = voice.index(signature)
    brace = voice.index("{", start)
    depth, end = 1, brace + 1
    while depth:
        depth += (voice[end] == "{") - (voice[end] == "}")
        end += 1
    return voice[start:end]

source = r'''
#include <cassert>
#include <cstdio>
#include <set>
#include <deque>
using ALuint = unsigned;
constexpr int AL_NO_ERROR=0, AL_LOOPING=1, AL_FALSE=0, AL_ROLLOFF_FACTOR=2,
 AL_GAIN=3, AL_BUFFER=4;
std::set<ALuint> sources, buffers;
unsigned next_id=1;
int error=0, fail=0;
int alGetError(){int e=error;error=0;return e;}
void alGenSources(int, ALuint* id){if(fail==1){error=1;return;}*id=next_id++;sources.insert(*id);}
void alGenBuffers(unsigned count, ALuint* ids){
 for(unsigned i=0;i<count;++i){if(fail==2 && i==3){error=1;return;}ids[i]=next_id++;buffers.insert(ids[i]);}
}
bool alIsSource(ALuint id){return sources.count(id)!=0;}
bool alIsBuffer(ALuint id){return buffers.count(id)!=0;}
void alDeleteSources(int, ALuint* id){assert(sources.erase(*id)==1);}
void alDeleteBuffers(int, ALuint* id){assert(buffers.erase(*id)==1);}
void alSourceStop(ALuint){}
void alSourcei(ALuint,int,int){}
void alSourcef(ALuint,int,float){}
struct Player{
 static constexpr unsigned NUM_BUFFERS=12;
 ALuint m_source=0,m_buffers[NUM_BUFFERS]={};
 std::deque<ALuint> m_free;
 std::deque<int> m_pcm;
 bool m_started=false,m_have_seq=false,m_talking=false;
 float m_loudness=0;
 void apply_mode(){}
'''
for signature in ("void create_al()", "void destroy_al()", "void ResetPlayback()"):
    source += function(signature) + "\n"
source += r'''
};
int main(){
 Player p;
 for(int n=0;n<1000;++n){
  fail=1;p.create_al();assert(!p.m_source && sources.empty() && buffers.empty());
  fail=2;p.create_al();assert(!p.m_source && sources.empty() && buffers.empty());
 }
 fail=0;p.create_al();assert(sources.size()==1 && buffers.size()==12 && p.m_free.size()==12);
 p.m_pcm.push_back(1);p.m_started=p.m_have_seq=p.m_talking=true;p.m_loudness=1;
 p.ResetPlayback();assert(sources.empty() && buffers.empty() && p.m_pcm.empty());
 assert(!p.m_started && !p.m_have_seq && !p.m_talking && !p.m_loudness);
 p.destroy_al();assert(sources.empty() && buffers.empty());
 p.create_al();assert(sources.size()==1 && buffers.size()==12);p.destroy_al();
 std::puts("PASS actual voice resources: failures, partial allocation, retries and context reset");
}
'''
core = (root / "src/xrSound/SoundRender_CoreA.cpp").read_text(encoding="utf-8")
assert core.index("m_voice->ResetPlayback()") < core.index("alcDestroyContext(oldContext)")
assert "u32(target_limit)" in core and "available_sources - 32" in core
assert "if (!m_source && !IsActive()) return;" in voice
assert "m_free.size() == NUM_BUFFERS" in voice
with TemporaryDirectory() as tmp:
    cpp = Path(tmp) / "voice.cpp"
    exe = Path(tmp) / ("voice.exe" if os.name == "nt" else "voice")
    cpp.write_text(source, encoding="utf-8")
    command = (["cl", "/nologo", "/std:c++17", "/EHsc", "/W4", "/WX", str(cpp), "/Fe:" + str(exe)]
               if os.name == "nt" else ["g++", "-std=c++17", "-Wall", "-Wextra", "-Werror", str(cpp), "-o", str(exe)])
    subprocess.run(command, cwd=tmp, check=True)
    subprocess.run([str(exe)], cwd=tmp, check=True)
