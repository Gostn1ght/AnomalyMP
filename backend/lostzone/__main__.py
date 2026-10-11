"""Local backend configuration and service lifecycle."""
import argparse
import json
import os
from pathlib import Path
import secrets
import signal
import threading
import time

from .http import Credentials, Dispatcher, Server
from .store import Invalid, Store, finite, identifier
from .world import World


def create_config(path, locations, *, world_id=None, seed=None, initial_ms=None, scale=None):
    path = Path(path).resolve()
    if path.exists():
        raise Invalid("configuration already exists; credentials were not replaced")
    if (world_id is None) != (seed is None):
        raise Invalid("explicit world identity requires both WorldID and seed")
    bootstrap = {}
    if world_id is not None:
        if type(world_id) is not int or not 0 < world_id < 2**64:
            raise Invalid("invalid WorldID")
        if type(seed) is not int or not 0 <= seed < 2**64:
            raise Invalid("invalid world seed")
        bootstrap.update(world_id=world_id, seed=seed)
    if initial_ms is not None:
        bootstrap["initial_ms"] = finite(initial_ms)
    if scale is not None:
        bootstrap["scale"] = finite(scale, 0.001, 1000)
    locations = sorted(set(locations or ["hidden_base"]))
    for location in locations:
        identifier(location)
    path.parent.mkdir(parents=True, exist_ok=True)
    credentials = {"admin": {"role": "admin", "token": secrets.token_urlsafe(48)}}
    for location in locations:
        credentials["location:" + location] = {"role": "location", "locations": [location],
                                                 "token": secrets.token_urlsafe(48)}
    credentials["observer:engine"] = {"role":"observer","locations":[],"token":secrets.token_urlsafe(48)}
    config = {"schema": 1, "database": "world.sqlite", "port": 38477,
              "signing_key": secrets.token_hex(32), "credentials": credentials}
    config.update(bootstrap)
    data = json.dumps(config, ensure_ascii=False, indent=2).encode("utf-8")
    descriptor = os.open(path, os.O_WRONLY | os.O_CREAT | os.O_EXCL, 0o600)
    try:
        with os.fdopen(descriptor, "wb") as file:
            file.write(data)
            file.flush()
            os.fsync(file.fileno())
    except BaseException:
        # An incomplete configuration is explicit and is never used as a
        # reason to overwrite an existing credential file on the next run.
        raise
    return path


def create_bridge_config(config_path, destination):
    # Export only a read-only observer, never an admin/location token. The
    # engine owns its existing WorldID/seed; this file does not adopt a new DB.
    config_path,destination = Path(config_path).resolve(),Path(destination).resolve()
    config = json.loads(config_path.read_text(encoding="utf-8"))
    Credentials(config.get("credentials"))
    entry = config.get("credentials",{}).get("observer:engine")
    if not entry or entry.get("role")!="observer":
        raise Invalid("a dedicated read-only engine observer is required")
    port = config.get("port",38477)
    if type(port) is not int or not 1 <= port <= 65535:
        raise Invalid("shadow bridge requires a fixed loopback port")
    if destination.name!="netcoop_world_bridge.json":
        raise Invalid("engine bridge file must be netcoop_world_bridge.json")
    destination.parent.mkdir(parents=True,exist_ok=True)
    encoded = json.dumps({"schema":1,"mode":"shadow","host":"127.0.0.1","port":port,"token":entry["token"]}).encode("utf-8")
    descriptor = os.open(destination,os.O_WRONLY|os.O_CREAT|os.O_EXCL,0o600)
    with os.fdopen(descriptor,"wb") as file:
        file.write(encoded);file.flush();os.fsync(file.fileno())
    return destination


def run(path, port_override=None, interactive=False):
    path = Path(path).resolve()
    config = json.loads(path.read_text(encoding="utf-8"))
    if config.get("schema") != 1:
        raise Invalid("unsupported service configuration")
    credentials = Credentials(config.get("credentials"))
    if interactive and not any(principal.role == "admin" for _, principal in credentials.entries):
        raise Invalid("master console requires an administrator credential")
    key = bytes.fromhex(config["signing_key"])
    port = port_override if port_override is not None else config.get("port", 38477)
    if type(port) is not int or not 0 <= port <= 65535:
        raise Invalid("invalid service port")
    database = Path(config["database"])
    if database.is_absolute() or ".." in database.parts:
        raise Invalid("database must stay inside the service configuration folder")
    store = Store(path.parent / database)
    server = None
    world = None
    stop = threading.Event()
    worker = None
    checkpoint = None
    previous_signals = {}
    try:
        world = World(store, world_id=config.get("world_id"), seed=config.get("seed"),
                      initial_ms=config.get("initial_ms", 0), scale=config.get("scale", 10))
        server = Server(("127.0.0.1", port), Dispatcher(world, key, config.get("quests", {}),
                        config.get("items", {}), config.get("traders", {}), config.get("scavenging", {}), config.get("offline_planning")), credentials)
        def checkpoints():
            last = time.monotonic()
            while not stop.wait(1):
                try:
                    processed=server.dispatcher.timelines.scheduler.run_due(limit=64, budget_ms=10)
                    if time.monotonic() - last >= 5:
                        world.sample()
                        last = time.monotonic()
                    server.worker_succeeded(processed)
                except Exception as error:
                    server.worker_failed(error)
        checkpoint = threading.Thread(target=checkpoints, name="world-checkpoint")
        checkpoint.start()
        worker = threading.Thread(target=server.serve_forever, name="world-http")
        worker.start()
        if threading.current_thread() is threading.main_thread():
            def request_stop(signum, frame):
                stop.set()
                if interactive:
                    raise KeyboardInterrupt
            for name in ("SIGINT", "SIGTERM"):
                if hasattr(signal, name):
                    code = getattr(signal, name)
                    previous_signals[code] = signal.signal(code, request_stop)
        print(f"Lost Zone World listening on 127.0.0.1:{server.server_address[1]}; epoch={store.epoch}", flush=True)
        if interactive:
            from .console import run_console
            try:
                run_console(server, stop)
            except KeyboardInterrupt:
                stop.set()
        else:
            while not stop.wait(1):
                if not worker.is_alive():
                    raise RuntimeError("world listener stopped")
    finally:
        stop.set()
        for code, previous in previous_signals.items():
            signal.signal(code, previous)
        if checkpoint is not None:
            checkpoint.join()
        if server is not None:
            server.ready.clear()
            if worker is not None and worker.is_alive():
                server.shutdown()
            server.server_close()
        if worker is not None:
            worker.join()
        try:
            if world is not None and store.epoch is not None:
                world.sample()
        finally:
            store.close()


def main():
    parser = argparse.ArgumentParser(description="Lost Zone local World Service")
    parser.add_argument("mode", choices=("init", "serve", "console", "bridge-config"))
    parser.add_argument("--config", required=True)
    parser.add_argument("--location", action="append", default=[])
    parser.add_argument("--port", type=int)
    parser.add_argument("--destination")
    parser.add_argument("--world-id", type=int, help="initial WorldID; init only, requires --seed")
    parser.add_argument("--seed", type=int, help="initial world seed; init only, requires --world-id")
    parser.add_argument("--initial-ms", type=float, help="initial game calendar in milliseconds; init only")
    parser.add_argument("--scale", type=float, help="initial game time scale; init only")
    args = parser.parse_args()
    if args.mode != "init" and any(value is not None for value in
                                   (args.world_id, args.seed, args.initial_ms, args.scale)):
        raise Invalid("world bootstrap options apply only to init")
    if args.mode == "init":
        create_config(args.config, args.location, world_id=args.world_id, seed=args.seed,
                      initial_ms=args.initial_ms, scale=args.scale)
        print("Created private service configuration. Tokens are not printed.")
    elif args.mode=="bridge-config":
        if not args.destination:
            raise Invalid("bridge-config requires --destination in the server userdata folder")
        create_bridge_config(args.config,args.destination)
        print("Created private read-only engine bridge configuration. Token is not printed.")
    else:
        run(args.config, args.port, interactive=args.mode == "console")


if __name__ == "__main__":
    main()
