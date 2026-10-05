"""Bounded, authenticated loopback transport for trusted server commands.

Player clients do not get credentials. Remote hosts need a TLS/mTLS gateway;
this implementation intentionally binds only IPv4 loopback.
"""
from dataclasses import dataclass
import hashlib
import hmac
from http.server import BaseHTTPRequestHandler, HTTPServer
import inspect
import json
import re
import socket
import socketserver
import threading
import time
from urllib.parse import parse_qs, urlsplit

from .ownership import Ownership
from .quests import Quests
from .store import Conflict, Invalid, Unavailable, canonical, identifier
from .transfers import Transfers
from .timelines import Timelines
from .offline import Offline
from .economy import Catalog, Trade
from .scavenging import Scavenging
from .encounters import Encounters


@dataclass(frozen=True)
class Principal:
    actor: str
    role: str
    locations: tuple


class Credentials:
    def __init__(self, entries):
        self.entries = []
        seen = set()
        if not isinstance(entries, dict) or not 1 <= len(entries) <= 128:
            raise Invalid("invalid server credentials configuration")
        for actor, data in entries.items():
            identifier(actor)
            if not isinstance(data, dict) or data.get("role") not in ("admin", "location", "observer"):
                raise Invalid("invalid server credential role")
            token, locations = data.get("token"), data.get("locations", [])
            if not isinstance(token, str) or not re.fullmatch(r"[a-zA-Z0-9_-]{32,256}", token):
                raise Invalid("server token must contain at least 32 ASCII characters")
            if not isinstance(locations, list) or len(locations) > 64:
                raise Invalid("invalid location allowlist")
            for location in locations:
                identifier(location)
            if data["role"] == "location" and not locations:
                raise Invalid("location principal needs an explicit allowlist")
            digest = hashlib.sha256(token.encode("ascii")).digest()
            if digest in seen:
                raise Invalid("server tokens must be unique")
            seen.add(digest)
            self.entries.append((digest, Principal(actor, data["role"], tuple(locations))))

    def authenticate(self, header):
        if not isinstance(header, str) or not header.startswith("Bearer ") or len(header) > 300:
            return None
        token = header[7:]
        if not token.isascii():
            return None
        digest = hashlib.sha256(token.encode("ascii")).digest()
        for expected, principal in self.entries:
            if hmac.compare_digest(digest, expected):
                return principal
        return None


class RateLimit:
    def __init__(self, rate=100, burst=200):
        self.rate, self.burst = rate, burst
        self.lock = threading.Lock()
        self.buckets = {}

    def allow(self, actor):
        now = time.monotonic()
        with self.lock:
            credit, previous = self.buckets.get(actor, (self.burst, now))
            credit = min(self.burst, credit + (now - previous) * self.rate)
            if credit < 1:
                self.buckets[actor] = (credit, now)
                return False
            self.buckets[actor] = (credit - 1, now)
            return True


class Dispatcher:
    def __init__(self, world, signing_key, quest_definitions=None, catalog=None, trade_profiles=None, scavenging_rules=None):
        self.world, self.store = world, world.store
        self.ownership, self.transfers = Ownership(world), Transfers(world, signing_key)
        self.quests = Quests(world, quest_definitions or {})
        self.timelines = Timelines(world)
        self.offline = Offline(world, self.timelines.scheduler)
        self.catalog = Catalog(catalog)
        self.trade = Trade(world, self.catalog, trade_profiles)
        self.scavenging = Scavenging(world, self.offline, self.catalog, scavenging_rules)
        self.encounters = Encounters(world, self.offline, self.catalog)

    @staticmethod
    def allowed(principal, location):
        identifier(location)
        if principal.role != "admin" and location not in principal.locations:
            raise PermissionError("location is outside this server's allowlist")

    def execute(self, principal, request):
        if principal.role=="observer":
            raise PermissionError("read-only observer cannot mutate world state")
        if not isinstance(request, dict) or set(request) != {"command_id", "operation", "arguments"}:
            raise Invalid("command requires command_id, operation and arguments")
        args, operation = request["arguments"], request["operation"]
        if not isinstance(args, dict) or not isinstance(operation, str):
            raise Invalid("invalid command arguments")
        administrative = {"world_scale": self.world.set_scale, "world_state": self.world.set_state,
                          "timeline_schedule": self.timelines.schedule, "route_start": self.offline.start_route,
                          "stash_visit": self.scavenging.schedule, "offline_combat": self.encounters.schedule}
        functions = {
            "location_claim": self.world.claim_location, "location_renew": self.world.renew_location,
            "location_recover": self.ownership.recover_location,
            "entity_create": self.ownership.create_entity, "entity_update": self.ownership.update_entity,
            "session_disconnect": self.ownership.disconnect, "session_resume": self.ownership.resume,
            "entity_death": self.ownership.kill, "corpse_cleanup": self.ownership.cleanup_corpse,
            "item_create": self.ownership.create_item, "item_move": self.ownership.move_item,
            "transfer_prepare": self.transfers.prepare, "transfer_claim": self.transfers.claim,
            "transfer_commit": self.transfers.commit, "transfer_abort": self.transfers.abort,
            "quest_grant": self.quests.grant, "quest_progress": self.quests.progress,
            "dehydrate": self.offline.dehydrate, "hydrate": self.offline.hydrate,
            "trade": self.trade.transact,
        }
        if operation in administrative:
            if principal.role != "admin":
                raise PermissionError("administrative command")
            function = administrative[operation]
        elif operation in functions:
            function = functions[operation]
            if "location" in args:
                self.allowed(principal, args["location"])
            if operation == "transfer_prepare":
                self.allowed(principal, args.get("source"))
            elif operation == "transfer_claim":
                self.allowed(principal, self.transfers.verify(args.get("token"))["target"])
            elif operation in ("transfer_commit", "transfer_abort"):
                status = self.transfers.status(principal.actor, args.get("transfer_id"))
                self.allowed(principal, status["target"] if operation == "transfer_commit" else status["source"])
            elif operation in ("entity_update", "entity_death", "corpse_cleanup", "quest_grant", "quest_progress", "session_disconnect"):
                with self.store.lock:
                    row = self.store.db.execute("SELECT location FROM entity WHERE id=?", (args.get("entity_id", args.get("character_id")),)).fetchone()
                    if not row:
                        raise Invalid("unknown entity")
                    self.allowed(principal, row[0])
        else:
            raise Invalid("unknown operation")
        try:
            inspect.signature(function).bind(principal.actor, request["command_id"], **args)
        except TypeError as error:
            raise Invalid("arguments do not match the command contract") from error
        return function(principal.actor, request["command_id"], **args)


def strict_json(data):
    def pairs(values):
        result = {}
        for key, value in values:
            if key in result:
                raise Invalid("duplicate JSON key")
            result[key] = value
        return result
    def constant(value):
        raise Invalid("non-finite JSON number")
    try:
        return json.loads(data, object_pairs_hook=pairs, parse_constant=constant)
    except (ValueError, UnicodeError, RecursionError) as error:
        raise Invalid("invalid JSON body") from error


class Handler(BaseHTTPRequestHandler):
    server_version = "LostZoneWorld/1"
    protocol_version = "HTTP/1.1"

    def setup(self):
        super().setup()
        self.connection.settimeout(8)

    def log_message(self, format, *args):
        # URLs/headers/body may contain credentials or transfer tokens.
        pass

    def respond(self, status, result):
        body = canonical(result, limit=16 * 1024 * 1024).encode("utf-8")
        try:
            self.send_response(status)
            self.send_header("Content-Type", "application/json; charset=utf-8")
            self.send_header("Content-Length", str(len(body)))
            self.send_header("Cache-Control", "no-store")
            self.send_header("Connection", "close")
            self.end_headers()
            self.wfile.write(body)
        except OSError:
            pass # Peer disconnected; committed commands remain queryable.
        finally:
            self.close_connection = True

    def handle_api(self, method):
        try:
            principal = self.server.credentials.authenticate(self.headers.get("Authorization"))
            if principal is None:
                self.respond(401, {"error": "server authentication required"})
                return
            if not self.server.rate_limit.allow(principal.actor):
                self.respond(429, {"error": "server request limit reached"})
                return
            if not self.server.ready.is_set():
                self.respond(503, {"error": "world authority is recovering"})
                return
            uri = urlsplit(self.path)
            dispatcher = self.server.dispatcher
            if method == "GET":
                if uri.path == "/v1/clock":
                    result = dispatcher.world.sample()
                elif uri.path == "/v1/bootstrap":
                    result = dispatcher.world.bootstrap_snapshot()
                elif uri.path == "/v1/events" and principal.role == "admin":
                    query = parse_qs(uri.query, strict_parsing=True)
                    result = {"events": dispatcher.store.events(int(query.get("after", ["0"])[0]),
                                                                int(query.get("limit", ["256"])[0]))}
                elif uri.path == "/v1/transfer":
                    query = parse_qs(uri.query, strict_parsing=True)
                    result = dispatcher.transfers.status(principal.actor, query.get("id", [""])[0])
                elif uri.path == "/v1/location":
                    query = parse_qs(uri.query, strict_parsing=True)
                    location, fence = query.get("id", [""])[0], int(query.get("fence", ["0"])[0])
                    dispatcher.allowed(principal, location)
                    result = dispatcher.ownership.location_state(principal.actor, location, fence)
                else:
                    self.respond(404, {"error": "unknown or unavailable endpoint"})
                    return
            else:
                if self.headers.get("Transfer-Encoding") or len(self.headers.get_all("Content-Length", [])) != 1:
                    raise Invalid("one Content-Length header is required")
                length = int(self.headers["Content-Length"])
                if not 1 <= length <= 65536:
                    self.respond(413, {"error": "request body exceeds limit"})
                    return
                if self.headers.get_content_type() != "application/json":
                    raise Invalid("JSON Content-Type is required")
                data = self.rfile.read(length)
                if len(data) != length:
                    raise Invalid("incomplete request body")
                if uri.path == "/v1/command":
                    result = dispatcher.execute(principal, strict_json(data))
                elif uri.path == "/v1/snapshot" and principal.role == "admin":
                    if strict_json(data) != {}:
                        raise Invalid("snapshot endpoint takes an empty object")
                    dispatcher.world.sample()
                    result = dispatcher.store.snapshot()
                else:
                    self.respond(404, {"error": "unknown or unavailable endpoint"})
                    return
            self.respond(200, {"result": result})
        except PermissionError:
            self.respond(403, {"error": "server is not permitted to perform this operation"})
        except Conflict as error:
            self.respond(409, {"error": str(error)})
        except (Invalid, ValueError, TypeError):
            self.respond(400, {"error": "invalid request contract"})
        except Unavailable:
            self.respond(503, {"error": "world authority is unavailable"})
        except (OSError, TimeoutError):
            self.close_connection = True
        except Exception:
            self.respond(503, {"error": "world transaction could not be completed"})

    def do_GET(self):
        self.handle_api("GET")

    def do_POST(self):
        self.handle_api("POST")


class Server(socketserver.ThreadingMixIn, HTTPServer):
    daemon_threads = False
    block_on_close = True

    def __init__(self, address, dispatcher, credentials, max_workers=16):
        if address[0] != "127.0.0.1" or type(max_workers) is not int or not 1 <= max_workers <= 128:
            raise Invalid("backend supports bounded loopback serving only")
        self.dispatcher, self.credentials = dispatcher, credentials
        self.rate_limit = RateLimit()
        self.ready = threading.Event()
        self.ready.set()
        self._slots = threading.BoundedSemaphore(max_workers)
        super().__init__(address, Handler)

    def process_request(self, request, address):
        if not self._slots.acquire(blocking=False):
            try:
                # Drain one bounded header packet so Windows does not reset
                # a normal client connection before it reads the 503 response.
                # No worker or SQL transaction is allocated in overload.
                request.settimeout(.1)
                try:
                    request.recv(65536)
                except OSError:
                    pass
                request.sendall(b"HTTP/1.1 503 Service Unavailable\r\nContent-Length: 0\r\nConnection: close\r\n\r\n")
                request.shutdown(socket.SHUT_WR)
            except OSError:
                pass
            self.shutdown_request(request)
            return
        try:
            super().process_request(request, address)
        except BaseException:
            self._slots.release()
            raise

    def process_request_thread(self, request, address):
        try:
            super().process_request_thread(request, address)
        finally:
            self._slots.release()
