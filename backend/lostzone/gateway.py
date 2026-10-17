"""Public entry point of the world master (owner 2026-10-17: "players enter
only the master's address").

A read-only TCP listener (default 1267, the same number as the first map's
UDP port, so a player still types only the IP) answers one question: which
running location should a client connect to now. That location authenticates
the player and the master's admission sends the character on to the map it
lives on, at the place it was saved. Nothing else of the master is reachable
from outside: no commands, no credentials, no player data.
"""
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer
import json
import re
import threading
import time
from pathlib import Path

LOCATION = re.compile(r"^[a-z0-9_]{1,64}$")
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

    def entry(self):
        """The first location of the cluster plan whose lease is alive."""
        locations = read_cluster(self.cluster_path)
        if not locations:
            return None
        with self.store.lock:
            now = self.world.real_ms()
            alive = {row[0] for row in self.store.db.execute(
                "SELECT location FROM location_lease WHERE expires_ms>?", (now,))}
        for name, host, port in locations:
            if name in alive:
                # Every location with a live lease runs on this machine: the
                # master's API listens on 127.0.0.1 only. So the client keeps
                # the address it reached the master with, whatever the plan
                # names (owner 2026-10-17: Radmin VPN players, no white IP;
                # a public IP in the plan is not reachable for them).
                return {"schema": 1, "location": name, "host": "", "port": port}
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
            if self.path != "/v1/entry":
                return self.reply(404, {"error": "unknown endpoint"})
            try:
                entry = gateway.entry()
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
