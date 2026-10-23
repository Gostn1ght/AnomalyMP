"""Public entry point of the world master (owner 2026-10-17: "players enter
only the master's address").

A read-only TCP listener (default 1267, the same number as the first map's
UDP port, so a player still types only the IP) answers one question: which
running location should a client connect to now. The client names its
account and slot (owner 2026-10-24: "the master connects you, from its
database, to the map you were on last, or to Cordon when you are new"): the
character's map when it runs, Cordon for a new character, otherwise the
first running map, whose admission tells the player (and wakes a map
started on demand). That location authenticates the player. Nothing else of
the master is reachable from outside: no commands, no credentials, no player
data beyond the name of a character's map.
"""
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer
import json
import re
import threading
import time
from pathlib import Path
from urllib.parse import parse_qs, urlsplit

from .native_save import identity

LOCATION = re.compile(r"^[a-z0-9_]{1,64}$")
ACCOUNT = re.compile(r"^[A-Za-z0-9_.-]{3,20}$")
NEWCOMER = "l01_escape"  # a new character starts on Cordon
HOST = re.compile(r"^[A-Za-z0-9.\-]{1,253}$")


def read_cluster(path):
    """[locations] name = host:port, in file order (the first is the entry)."""
    locations, section = [], None
    try:
        text = Path(path).read_text(encoding="cp1251", errors="replace")
    except OSError:
        return locations
    for raw in text.splitlines():
        line = raw.split(";", 1)[0].strip()
        if not line:
            continue
        if line.startswith("[") and line.endswith("]"):
            section = line[1:-1].strip().lower()
            continue
        if section != "locations" or "=" not in line:
            continue
        name, value = (part.strip() for part in line.split("=", 1))
        host, _, port = value.rpartition(":")
        if LOCATION.match(name) and (host == "" or HOST.match(host)) and port.isdigit() and 0 < int(port) < 65536:
            locations.append((name, host, int(port)))
    return locations


class Gateway:
    def __init__(self, store, world, cluster_path, rate=20, window=10.0):
        self.store, self.world, self.cluster_path = store, world, cluster_path
        self.rate, self.window = rate, window
        self.hits, self.lock = {}, threading.Lock()

    def allowed(self, address):
        now = time.monotonic()
        with self.lock:
            recent = [t for t in self.hits.get(address, ()) if now - t < self.window]
            if len(recent) >= self.rate:
                self.hits[address] = recent
                return False
            recent.append(now)
            self.hits[address] = recent
            if len(self.hits) > 4096:
                self.hits = {k: v for k, v in self.hits.items() if v and now - v[-1] < self.window}
            return True

    def home(self, account, slot):
        """The map a character lives on, None for a new one."""
        character_id = identity(self.world.world_id, self.world.seed, account, slot)
        with self.store.lock:
            rows = list(self.store.db.execute(
                "SELECT location FROM entity WHERE id=? AND kind='CHARACTER'", (character_id,)))
        return rows[0][0] if rows else None

    def entry(self, account=None, slot=1):
        """Where a client connects: its character's running map, Cordon for a
        new character, else the first running location of the cluster plan."""
        locations = read_cluster(self.cluster_path)
        if not locations:
            return None
        with self.store.lock:
            now = self.world.real_ms()
            alive = {row[0] for row in self.store.db.execute(
                "SELECT location FROM location_lease WHERE expires_ms>?", (now,))}
        # Every location with a live lease runs on this machine: the master's
        # API listens on 127.0.0.1 only. So the client keeps the address it
        # reached the master with, whatever the plan names (owner 2026-10-17:
        # Radmin VPN players, no white IP; a public IP in the plan is not
        # reachable for them).
        def answer(name, port):
            return {"schema": 1, "location": name, "host": "", "port": port}
        ports = {name: port for name, host, port in locations}
        if account is not None and ACCOUNT.match(account) and type(slot) is int and 1 <= slot <= 10:
            home = self.home(account, slot)
            wanted = home if home is not None else NEWCOMER
            if wanted in alive and wanted in ports:
                return answer(wanted, ports[wanted])
        for name, host, port in locations:
            if name in alive:
                return answer(name, port)
        return None


def serve(gateway, port, stop):
    class Handler(BaseHTTPRequestHandler):
        server_version = "LostZoneMaster"
        sys_version = ""

        def log_message(self, *args):
            pass

        def reply(self, code, body):
            data = json.dumps(body).encode()
            self.send_response(code)
            self.send_header("Content-Type", "application/json")
            self.send_header("Content-Length", str(len(data)))
            self.send_header("Cache-Control", "no-store")
            self.end_headers()
            self.wfile.write(data)

        def do_GET(self):
            if not gateway.allowed(self.client_address[0]):
                return self.reply(429, {"error": "too many requests"})
            url = urlsplit(self.path)
            if url.path != "/v1/entry":
                return self.reply(404, {"error": "unknown endpoint"})
            query = parse_qs(url.query, max_num_fields=4)
            account = (query.get("account") or [None])[0]
            slot = (query.get("slot") or ["1"])[0]
            try:
                slot = max(1, int(slot)) if slot.isdigit() and len(slot) <= 2 else 0
                entry = gateway.entry(account, slot) if account else gateway.entry()
            except Exception:
                entry = None
            if entry is None:
                return self.reply(503, {"error": "no location is running"})
            return self.reply(200, entry)

        def do_POST(self):
            self.reply(405, {"error": "read-only"})

        do_PUT = do_DELETE = do_PATCH = do_POST

    server = ThreadingHTTPServer(("0.0.0.0", port), Handler)
    server.daemon_threads = True
    server.timeout = 1

    def loop():
        while not stop.is_set():
            server.handle_request()
        server.server_close()
    thread = threading.Thread(target=loop, name="world-gateway", daemon=True)
    thread.start()
    return server, thread
