# SpeexDSP (preprocess: denoise, AGC, VAD) for the voice chat, built by the
# Lost Zone GitHub Actions workflow before MSBuild. Upstream ships autotools
# only; this builds the same library sources with win32/config.h.
cmake_minimum_required(VERSION 3.16)
project(speexdsp C)
add_library(speexdsp STATIC
    libspeexdsp/preprocess.c libspeexdsp/filterbank.c libspeexdsp/fftwrap.c
    libspeexdsp/smallft.c libspeexdsp/kiss_fft.c libspeexdsp/kiss_fftr.c
    libspeexdsp/mdf.c libspeexdsp/jitter.c libspeexdsp/resample.c
    libspeexdsp/buffer.c libspeexdsp/scal.c)
target_include_directories(speexdsp PUBLIC include PRIVATE win32 libspeexdsp)
target_compile_definitions(speexdsp PRIVATE HAVE_CONFIG_H _CRT_SECURE_NO_WARNINGS)
set_property(TARGET speexdsp PROPERTY MSVC_RUNTIME_LIBRARY "MultiThreadedDLL")
