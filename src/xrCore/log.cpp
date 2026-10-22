#include "stdafx.h"
#pragma hdrstop

#include <time.h>
#include "resource.h"
#include "log.h"
#ifdef _EDITOR
#include "malloc.h"
#endif

#include <chrono>
#include <ctime>
#include <iomanip>
#include <sstream>
#include <string>

#include "profiler.h"

extern BOOL LogExecCB = TRUE;
static string_path logFName = "engine.log";
static string_path log_file_name = "engine.log";
static BOOL no_log = TRUE;
#ifdef PROFILE_CRITICAL_SECTIONS
static xrCriticalSection logCS(MUTEX_PROFILE_ID(log));
#else // PROFILE_CRITICAL_SECTIONS
static xrCriticalSection logCS;
#endif // PROFILE_CRITICAL_SECTIONS
xr_vector<xr_string> LogFile;
static LogCallback LogCB = 0;
static size_t log_flushed_lines = 0;
static volatile LONG log_closed = 0;
static shared_str log_last_str;
static int log_repeat_count = 0;

void FlushLog()
{
	if (InterlockedCompareExchange(&log_closed, 0, 0)) return;
	PROF_EVENT();

	logCS.Enter();
	if (log_closed || no_log) { logCS.Leave(); return; }
	PROF_EVENT("Flushing");
	IWriter* f = FS.w_open(logFName);
	if (f)
	{
		for (const auto& i : LogFile)
		{
			LPCSTR s = i.c_str();
			f->w_string(s ? s : "");
		}
		FS.w_close(f);
		log_flushed_lines = LogFile.size();
	}
	logCS.Leave();
}

// Appends the lines logged since the last flush instead of rewriting the
// whole log (megabytes after an hour), so a periodic flush does not stall
// the frame. The line merged with a repeat counter after it was written
// keeps its first form on disk.
void FlushLogAppend()
{
	if (InterlockedCompareExchange(&log_closed, 0, 0)) return;
	logCS.Enter();
	if (log_closed || no_log) { logCS.Leave(); return; }
	if (!log_flushed_lines || log_flushed_lines > LogFile.size())
	{
		logCS.Leave();
		FlushLog();
		return;
	}
	if (log_flushed_lines < LogFile.size())
	{
		FILE* f = fopen(logFName, "ab");
		if (f)
		{
			for (size_t i = log_flushed_lines; i < LogFile.size(); ++i)
			{
				fputs(LogFile[i].c_str(), f);
				fputs("\r\n", f);
			}
			fclose(f);
			log_flushed_lines = LogFile.size();
		}
	}
	logCS.Leave();
}

void LogLock(bool lock)
{
	if (lock)
		logCS.Enter();
	else
		logCS.Leave();
}

std::string getCurrentTimeStamp(LPCSTR format = "%d.%m.%Y %H:%M:%S") {
	using namespace std::chrono;

	// get current time
	auto now = system_clock::now();

	// get number of milliseconds for the current second
	// (remainder after division into seconds)
	auto ms = duration_cast<milliseconds>(now.time_since_epoch()) % 1000;

	// convert to std::time_t in order to convert to std::tm (broken time)
	auto timer = system_clock::to_time_t(now);

	// convert to broken time
	std::tm bt = *std::localtime(&timer);

	std::ostringstream oss;

	oss << std::put_time(&bt, format); // HH:MM:SS
	oss << '.' << std::setfill('0') << std::setw(3) << ms.count();

	return oss.str();
}

std::string timeInDMYHMSMMM()
{
	return getCurrentTimeStamp("%d.%m.%Y %H:%M:%S");
}

std::string timeInHMSMMM()
{
	return getCurrentTimeStamp("%H:%M:%S");
}

BOOL logTimestamps = FALSE;
enum Console_mark;
extern bool is_console_mark(Console_mark type);

void AddOne(const char* split)
{
	if (InterlockedCompareExchange(&log_closed, 0, 0)) return;
	logCS.Enter();
	if (log_closed) { logCS.Leave(); return; }

#ifdef DEBUG
    OutputDebugString(split);
    OutputDebugString("\n");
#endif

	// DUMP_PHASE;
	{
		// demonized: add timestamps to log
		std::string t = split;
		if (logTimestamps) {
			std::string c = "";
			if (t.length() > 0 && is_console_mark((Console_mark)t[0])) {
				c += t[0];
				c += " ";
				t.erase(0, 1);
			}
			t = c + "[" + timeInHMSMMM() + "] " + t;
		}
		auto temp = shared_str(t.c_str());

		if (!LogFile.empty() && log_last_str.equal(temp))
		{
			xr_string tmp = temp.c_str();

			if (log_repeat_count == 0)
				log_repeat_count = 2;
			else
				log_repeat_count++;

			tmp += " [";
			tmp += std::to_string(log_repeat_count).c_str();
			tmp += "]";

			LogFile.erase(LogFile.end()-1);
			LogFile.push_back(xr_string(tmp.c_str()));
		}
		else
		{
			// DUMP_PHASE;
			LogFile.push_back(xr_string(temp.c_str()));
			log_last_str = temp;
			log_repeat_count = 0;

			// NetAnomaly: hard cap on the in-memory log, see tools/patch_logcap.py
			if (LogFile.size() > 40000)
			{
				LogFile.erase(LogFile.begin(), LogFile.begin() + 20000);
				log_last_str = shared_str("~ [Lost Zone] log trimmed: 20000 oldest lines dropped");
				LogFile.push_back(xr_string(log_last_str.c_str()));
				log_repeat_count = 0;
			}
		}
	}

	//exec CallBack
	if (LogExecCB && LogCB)LogCB(split);

	logCS.Leave();
}

void Log(const char* s)
{
	int i, j;

	u32 length = xr_strlen(s);
#ifndef _EDITOR
	PSTR split = (PSTR)_alloca((length + 1) * sizeof(char));
#else
    PSTR split = (PSTR)alloca((length + 1) * sizeof(char));
#endif
	for (i = 0, j = 0; s[i] != 0; i++)
	{
		if (s[i] == '\n')
		{
			split[j] = 0; // end of line
			if (split[0] == 0)
			{
				split[0] = ' ';
				split[1] = 0;
			}
			AddOne(split);
			j = 0;
		}
		else
		{
			split[j++] = s[i];
		}
	}
	split[j] = 0;
	AddOne(split);
}

void __cdecl Msg(const char* format, ...)
{
	va_list mark;
	string2048 buf;
	va_start(mark, format);
	int sz = _vsnprintf(buf, sizeof(buf) - 1, format, mark);
	buf[sizeof(buf) - 1] = 0;
	va_end(mark);
	if (sz) Log(buf);
}

void Log(const char* msg, const char* dop)
{
	if (!dop)
	{
		Log(msg);
		return;
	}

	u32 buffer_size = (xr_strlen(msg) + 1 + xr_strlen(dop) + 1) * sizeof(char);
	PSTR buf = (PSTR)_alloca(buffer_size);
	strconcat(buffer_size, buf, msg, " ", dop);
	Log(buf);
}

void Log(const char* msg, u32 dop)
{
	u32 buffer_size = (xr_strlen(msg) + 1 + 10 + 1) * sizeof(char);
	PSTR buf = (PSTR)_alloca(buffer_size);

	xr_sprintf(buf, buffer_size, "%s %d", msg, dop);
	Log(buf);
}

void Log(const char* msg, int dop)
{
	u32 buffer_size = (xr_strlen(msg) + 1 + 11 + 1) * sizeof(char);
	PSTR buf = (PSTR)_alloca(buffer_size);

	xr_sprintf(buf, buffer_size, "%s %i", msg, dop);
	Log(buf);
}

void Log(const char* msg, float dop)
{
	// actually, float string representation should be no more, than 40 characters,
	// but we will count with slight overhead
	u32 buffer_size = (xr_strlen(msg) + 1 + 64 + 1) * sizeof(char);
	PSTR buf = (PSTR)_alloca(buffer_size);

	xr_sprintf(buf, buffer_size, "%s %f", msg, dop);
	Log(buf);
}

void Log(const char* msg, const Fvector& dop)
{
	u32 buffer_size = (xr_strlen(msg) + 2 + 3 * (64 + 1) + 1) * sizeof(char);
	PSTR buf = (PSTR)_alloca(buffer_size);

	xr_sprintf(buf, buffer_size, "%s (%f,%f,%f)", msg, VPUSH(dop));
	Log(buf);
}

void Log(const char* msg, const Fmatrix& dop)
{
	u32 buffer_size = (xr_strlen(msg) + 2 + 4 * (4 * (64 + 1) + 1) + 1) * sizeof(char);
	PSTR buf = (PSTR)_alloca(buffer_size);

	xr_sprintf(buf, buffer_size, "%s:\n%f,%f,%f,%f\n%f,%f,%f,%f\n%f,%f,%f,%f\n%f,%f,%f,%f\n",
	           msg,
	           dop.i.x, dop.i.y, dop.i.z, dop._14_,
	           dop.j.x, dop.j.y, dop.j.z, dop._24_,
	           dop.k.x, dop.k.y, dop.k.z, dop._34_,
	           dop.c.x, dop.c.y, dop.c.z, dop._44_
	);
	Log(buf);
}

void LogWinErr(const char* msg, long err_code)
{
	Msg("%s: %s", msg, Debug.error2string(err_code));
}

LogCallback SetLogCB(LogCallback cb)
{
	LogCallback result = LogCB;
	LogCB = cb;
	return (result);
}

LPCSTR log_name()
{
	return (log_file_name);
}

void InitLog()
{
	logCS.Enter();
	InterlockedExchange(&log_closed, 0);
	LogFile.reserve(10000);
	logCS.Leave();
}

void CreateLog(BOOL nl)
{
	no_log = nl;
	strconcat(sizeof(log_file_name), log_file_name, Core.ApplicationName, "_", Core.UserName, ".log");
	if (FS.path_exist("$logs$"))
		FS.update_path(logFName, "$logs$", log_file_name);
	if (!no_log)
	{
		// Keep the last three sessions' logs (.bkp newest, .bkp3 oldest): a crash
		// log was lost when the game was started again. The OS renames: the logs
		// folder is not always in the file system index FS.file_rename works on.
		const xr_string base = EFS.ChangeFileExt(logFName, "");
		const xr_string bkp1 = base + ".bkp", bkp2 = base + ".bkp2", bkp3 = base + ".bkp3";
		MoveFileExA(bkp2.c_str(), bkp3.c_str(), MOVEFILE_REPLACE_EXISTING);
		MoveFileExA(bkp1.c_str(), bkp2.c_str(), MOVEFILE_REPLACE_EXISTING);
		MoveFileExA(logFName, bkp1.c_str(), MOVEFILE_REPLACE_EXISTING);
		IWriter* f = FS.w_open(logFName);
		if (f == NULL)
		{
			MessageBox(NULL, "Can't create log file.", "Error", MB_ICONERROR);
			abort();
		}
		FS.w_close(f);
	}
}

void CloseLog(void)
{
	logCS.Enter();
	FlushLog();
	InterlockedExchange(&log_closed, 1);
	no_log = TRUE;
	LogCB = nullptr;
	log_last_str = shared_str();
	log_repeat_count = 0;
	LogFile.clear();
	log_flushed_lines = 0;
	logCS.Leave();
}

xr_string FormatString(LPCSTR fmt, ...)
{
	va_list mark;
	string2048 buf;
	va_start(mark, fmt);
	int sz = _vsnprintf(buf, sizeof(buf) - 1, fmt, mark);
	buf[sizeof(buf) - 1] = 0;
	va_end(mark);
	if (sz) return xr_string(buf);
	return xr_string("");
}
