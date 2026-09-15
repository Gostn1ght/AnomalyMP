"""Own a dedicated engine process and display its log in the local server console."""
import json
import os
from pathlib import Path
import subprocess
import threading
import time
import uuid


class DedicatedProcess:
    def __init__(self, runtime, port=1237, players=128):
        self.runtime = Path(runtime).resolve(strict=True)
        if type(port) is not int or not 1024 <= port <= 65534:
            raise ValueError('Server port must be 1024..65534')
        if type(players) is not int or not 1 <= players <= 128:
            raise ValueError('Player limit must be 1..128')
        self.port, self.players = port, players
        self.process = None
        self.session = uuid.uuid4().hex
        self.logname = 'gamma_dedicated_' + self.session[:8]
        self.stopped = threading.Event()
        self.watcher = None
        self.state = {}

    def _write_state(self):
        target = self.runtime / 'appdata/server/dedicated-process.json'
        temporary = target.with_suffix('.tmp')
        temporary.write_text(json.dumps(self.state, indent=2), encoding='utf8')
        temporary.replace(target)

    def start(self):
        if self.process is not None:
            raise RuntimeError('This server session was already started')
        exe = self.runtime / 'server/bin/AnomalyGammaNetServerDX11.exe'
        if not exe.is_file() or not (self.runtime / 'fsgame_server.ltx').is_file():
            raise ValueError('Dedicated executable or server filesystem profile missing')
        args = [str(exe), '-dedicated', '-netcoop', '-noprefetch', '-multi_instance',
                '-logname', self.logname, '-fsltx', 'fsgame_server.ltx',
                '-netport', str(self.port),
                '-start', f'server(all/single/alife/new/portsv={self.port}/maxplayers={self.players})',
                f'client(localhost/name=ServerAuthority/port={self.port}/portcl={self.port + 1})']
        startup = None
        if os.name == 'nt':
            startup = subprocess.STARTUPINFO()
            startup.dwFlags = subprocess.STARTF_USESHOWWINDOW
            startup.wShowWindow = 1 # Show the native dedicated text console.
        self.process = subprocess.Popen(args, cwd=self.runtime, startupinfo=startup)
        self.state = {'pid': self.process.pid, 'session': self.session, 'logname': self.logname,
                 'port': self.port, 'players': self.players, 'started_at': time.time(),
                 'state': 'starting', 'gameplay_ready': False}
        self._write_state()
        print(f'Dedicated PID {self.process.pid}, port {self.port}, limit {self.players}. STARTING.', flush=True)
        self.watcher = threading.Thread(target=self._watch, daemon=True)
        self.watcher.start()

    def _watch(self):
        logdir = self.runtime / 'appdata/server/logs'
        previous = []
        while not self.stopped.wait(1):
            paths = list(logdir.glob('xray_' + self.logname + '_*.log'))
            if paths:
                # The engine rewrites its log on flush, so track lines, not offsets.
                lines = paths[0].read_text(encoding='utf8', errors='replace').splitlines()
                common = 0
                for a, b in zip(previous, lines):
                    if a != b:
                        break
                    common += 1
                fresh = lines[common:]
                if len(fresh) > 40:
                    print(f'[engine] {len(fresh)} new log lines; showing last 40 ({paths[0]}).', flush=True)
                    fresh = fresh[-40:]
                for line in fresh:
                    print('[engine] ' + line, flush=True)
                previous = lines
            code = self.process.poll()
            if code is not None:
                self.state.update(state='exited', exit_code=code)
                self._write_state()
                print(f'Dedicated exited, code {code}. Clients must remain stopped.', flush=True)
                return

    def status(self):
        code = self.process.poll() if self.process else None
        if not self.process:
            return 'Not started'
        if code is not None:
            return f'EXITED ({code})'
        return f'RUNNING PID {self.process.pid}; gameplay readiness requires world and join verification'

    def close(self):
        self.stopped.set()
        if self.process and self.process.poll() is None:
            self.process.terminate()
            try:
                self.process.wait(timeout=10)
            except subprocess.TimeoutExpired:
                self.process.kill()
                self.process.wait(timeout=5)
        if self.watcher:
            self.watcher.join(timeout=2)
        if self.process:
            self.state.update(state='exited', exit_code=self.process.poll())
            self._write_state()
