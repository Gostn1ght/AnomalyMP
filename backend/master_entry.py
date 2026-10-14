"""Standalone console entry point; private config/DB stay outside the EXE."""
import contextlib
from datetime import datetime, timezone
from pathlib import Path
import re
import sys
import threading

from lostzone.__main__ import main as service_main


class AuditStream:
    def __init__(self, console, logfile, lock):
        self.console, self.logfile, self.lock = console, logfile, lock
        self.pending = ""

    def __getattr__(self, name):
        return getattr(self.console, name)

    def write(self, value):
        with self.lock:
            count = self.console.write(value)
            self.pending += value
            while "\n" in self.pending:
                line, self.pending = self.pending.split("\n", 1)
                self._record(line)
            return count

    def _record(self, line):
        line = re.sub(r"\x1b\[[0-9;]*m", "", line.rstrip("\r"))
        if re.search(r"(?i)\b(?:password|passwd|token|secret|signing_key|authorization)\b", line):
            line = "[redacted sensitive diagnostic line]"
        stamp = datetime.now(timezone.utc).isoformat(timespec="seconds")
        self.logfile.write(f"[{stamp}] {line}\n")

    def flush(self):
        with self.lock:
            # Keep a partial line buffered: a token name/value may arrive in
            # separate writes. The console's prompt still appears immediately.
            self.console.flush()
            self.logfile.flush()

    def finish(self):
        with self.lock:
            if self.pending:
                self._record(self.pending)
                self.pending = ""
            self.flush()


def entry(argv=None):
    for stream in (sys.stdin, sys.stdout, sys.stderr):
        configure = getattr(stream, "reconfigure", None)
        if configure:
            configure(encoding="utf-8", errors="replace")
    args = list(sys.argv[1:] if argv is None else argv)
    if not args:
        home = Path(sys.executable).parent if getattr(sys, "frozen", False) else Path(__file__).parent
        args = ["console", "--config", str(home / "runtime" / "config.json")]
    logfile = None
    if "--log-file" in args:
        index = args.index("--log-file")
        if index + 1 >= len(args):
            raise ValueError("log file path required")
        logfile = Path(args[index + 1]).resolve()
        del args[index:index + 2]
    elif args[0] in ("serve", "console") and "--config" in args:
        index = args.index("--config")
        if index + 1 < len(args):
            logfile = Path(args[index + 1]).resolve().parent / "logs" / "master.log"
    previous = sys.argv
    sys.argv = [previous[0], *args]
    try:
        if logfile is None:
            service_main()
        else:
            logfile.parent.mkdir(parents=True, exist_ok=True)
            with logfile.open("a", encoding="utf-8") as audit:
                lock = threading.RLock()
                out, err = AuditStream(sys.stdout, audit, lock), AuditStream(sys.stderr, audit, lock)
                with contextlib.redirect_stdout(out), contextlib.redirect_stderr(err):
                    try:
                        service_main()
                    except Exception as error:
                        # Private config/checkpoint exception text is never echoed.
                        print(f"Master stopped: {type(error).__name__}. Check the private configuration and log.", file=sys.stderr)
                        return 1
                    finally:
                        out.finish()
                        err.finish()
        return 0
    finally:
        sys.argv = previous


if __name__ == "__main__":
    raise SystemExit(entry())
