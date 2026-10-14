"""Local backend configuration and service lifecycle."""
import argparse
import json
import os
from pathlib import Path
import secrets
import re
import signal
import threading
import time

from .http import Credentials, Dispatcher, Server
from .store import Invalid, Store, finite, identifier
from .world import World


def world_identity(world_id, seed):
    if type(world_id) is not int or not 0 < world_id < 2**64:
        raise Invalid("invalid WorldID")
    if type(seed) is not int or not 0 <= seed < 2**64:
        raise Invalid("invalid world seed")
    return world_id, seed


def create_config(path, locations, *, world_id=None, seed=None, initial_ms=None, scale=None):
    path = Path(path).resolve()
    if path.exists():
        raise Invalid("configuration already exists; credentials were not replaced")
    if (world_id is None) != (seed is None):
        raise Invalid("explicit world identity requires both WorldID and seed")
    bootstrap = {}
    if world_id is not None:
        world_identity(world_id, seed)
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


def create_bridge_config(config_path, destination, *, local_world_id=None, local_seed=None, location=None,
                         authority=False, replace=False):
    # Export only a read-only observer, never an admin/location token. The
    # engine owns its existing WorldID/seed; this file does not adopt a new DB.
    config_path,destination = Path(config_path).resolve(),Path(destination).resolve()
    config = json.loads(config_path.read_text(encoding="utf-8"))
    if config.get("schema") != 1:
        raise Invalid("unsupported service configuration")
    credentials = Credentials(config.get("credentials"))
    entry = config.get("credentials",{}).get("observer:engine")
    if not entry or entry.get("role")!="observer":
        raise Invalid("a dedicated read-only engine observer is required")
    port = config.get("port",38477)
    if type(port) is not int or not 1 <= port <= 65535:
        raise Invalid("shadow bridge requires a fixed loopback port")
    if destination.name!="netcoop_world_bridge.json":
        raise Invalid("engine bridge file must be netcoop_world_bridge.json")
    body = {"schema":1,"mode":"shadow","host":"127.0.0.1","port":port,"token":entry["token"]}
    if authority:
        # Every location server of this folder follows this master (owner
        # 2026-10-12): weather, emissions, psi storms and the calendar come
        # from it, and a server without it admits no players. One file serves
        # all maps; the engine binds it to the level it actually loaded.
        if any(value is not None for value in (local_world_id, local_seed, location)):
            raise Invalid("an authority bridge is not bound to one checkpoint")
        master_id, master_seed = world_identity(config.get("world_id"), config.get("seed"))
        body = {"schema":3,"mode":"authority","host":"127.0.0.1","port":port,"token":entry["token"],
                "master_world_id":master_id,"master_world_seed":master_seed}
    elif any(value is not None for value in (local_world_id, local_seed, location)):
        world_identity(local_world_id, local_seed)
        identifier(location)
        if not any(principal.role == "location" and location in principal.locations
                   for _, principal in credentials.entries):
            raise Invalid("binding location is not configured in the master")
        master_id, master_seed = world_identity(config.get("world_id"), config.get("seed"))
        body.update(schema=2, master_world_id=master_id, master_world_seed=master_seed,
                    local_world_id=local_world_id, local_world_seed=local_seed, location=location)
    destination.parent.mkdir(parents=True,exist_ok=True)
    encoded = json.dumps(body).encode("utf-8")
    if replace and authority and destination.exists():
        destination.unlink()  # the same master's file, rewritten after a new init
    descriptor = os.open(destination,os.O_WRONLY|os.O_CREAT|os.O_EXCL,0o600)
    with os.fdopen(descriptor,"wb") as file:
        file.write(encoded);file.flush();os.fsync(file.fileno())
    return destination


def create_writer_config(config_path, destination, location, *, replace=False):
    """Export one map's trusted-server credential, never admin or observer keys."""
    if not isinstance(location, str) or not re.fullmatch(r"[A-Za-z0-9_]{1,64}", location):
        raise Invalid("invalid engine location name")
    destination = Path(destination).resolve()
    if destination.name != "netcoop_world_writer_" + location + ".json":
        raise Invalid("writer config filename must match its location")
    config = json.loads(Path(config_path).read_text(encoding="utf-8"))
    if config.get("schema") != 1:
        raise Invalid("unsupported service configuration")
    Credentials(config.get("credentials"))
    actor = "location:" + location
    credential = config["credentials"].get(actor)
    if not credential or credential.get("role") != "location" or credential.get("locations") != [location]:
        raise Invalid("one dedicated location credential is required")
    world_id, seed = world_identity(config.get("world_id"), config.get("seed"))
    port = config.get("port", 38477)
    if type(port) is not int or not 1 <= port <= 65535:
        raise Invalid("writer requires a fixed loopback port")
    body = {"schema": 1, "mode": "writer", "host": "127.0.0.1", "port": port,
            "token": credential["token"], "actor": actor, "location": location,
            "master_world_id": world_id, "master_world_seed": seed}
    encoded = json.dumps(body, separators=(",", ":")).encode("utf-8")
    if destination.exists() and destination.read_bytes() == encoded:
        return destination
    if destination.exists() and not replace:
        raise FileExistsError("writer config exists; explicit replacement required")
    destination.parent.mkdir(parents=True, exist_ok=True)
    temporary = destination.with_name(destination.name + "." + secrets.token_hex(16) + ".tmp")
    descriptor = os.open(temporary, os.O_WRONLY | os.O_CREAT | os.O_EXCL, 0o600)
    try:
        with os.fdopen(descriptor, "wb") as output:
            output.write(encoded)
            output.flush()
            os.fsync(output.fileno())
        if replace:
            os.replace(temporary, destination)
        else:
            # Link, rather than replace: refuse a concurrent creator too.
            os.link(temporary, destination)
    finally:
        temporary.unlink(missing_ok=True)
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
        from .director import Director
        director = Director(world, server.dispatcher.timelines, config.get("director"))
        def checkpoints():
            last = time.monotonic()
            planned = 0.0
            while not stop.wait(1):
                try:
                    processed=server.dispatcher.timelines.scheduler.run_due(limit=64, budget_ms=10)
                    if time.monotonic() - planned >= 2:
                        planned = time.monotonic()
                        for line in director.tick():
                            print(f"[мир] {line}", flush=True)
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


def player_migration(config_path, source, location, world_id, seed, *, commit=False):
    from .native_save import scan_directory, stage_import
    # Dry-run does not open or create a database, acquire an authority epoch,
    # print character names, or touch credentials and source files.
    path = Path(config_path).resolve()
    config = json.loads(path.read_text(encoding="utf-8"))
    if config.get("schema") != 1 or (config.get("world_id"), config.get("seed")) != (world_id, seed):
        raise Invalid("migration must explicitly match the configured WorldID and seed")
    database = Path(config["database"])
    if database.is_absolute() or ".." in database.parts:
        raise Invalid("database must stay inside the service configuration folder")
    database = (path.parent / database).resolve()
    if not database.is_relative_to(path.parent):
        raise Invalid("database must stay inside the service configuration folder")
    if location not in {entry.get("locations", [None])[0] for entry in config.get("credentials", {}).values()
                        if entry.get("role") == "location" and len(entry.get("locations", [])) == 1}:
        raise Invalid("migration location is not configured")
    plan = scan_directory(source, world_id, seed, location)
    result = {"validated": len(plan), "bytes": sum(len(record["save"].raw) for record in plan),
              "committed": False, "live_authority_changed": False}
    if commit:
        if not database.is_file():
            raise Invalid("initialize and stop the intended master before staging migration")
        store = Store(database)
        try:
            result.update(stage_import(store, plan), committed=True)
        finally:
            store.close()
    print(json.dumps(result, sort_keys=True))
    return result


def main():
    parser = argparse.ArgumentParser(description="Lost Zone local World Service")
    parser.add_argument("mode", choices=("init", "serve", "console", "bridge-config", "writer-config", "player-migration"))
    parser.add_argument("--config", required=True)
    parser.add_argument("--location", action="append", default=[])
    parser.add_argument("--port", type=int)
    parser.add_argument("--destination")
    parser.add_argument("--world-id", type=int, help="initial WorldID; init only, requires --seed")
    parser.add_argument("--seed", type=int, help="initial world seed; init only, requires --world-id")
    parser.add_argument("--initial-ms", type=float, help="initial game calendar in milliseconds; init only")
    parser.add_argument("--scale", type=float, help="initial game time scale; init only")
    parser.add_argument("--local-world-id", type=int, help="existing ALife checkpoint WorldID; bridge-config only")
    parser.add_argument("--local-seed", type=int, help="existing ALife checkpoint seed; bridge-config only")
    parser.add_argument("--authority", action="store_true", help="bridge-config: every map follows this master")
    parser.add_argument("--replace", action="store_true", help="bridge-config --authority or writer-config: rewrite an existing private file")
    parser.add_argument("--source", help="player-migration: stopped location's native save directory")
    parser.add_argument("--commit-import", action="store_true", help="player-migration: archive validated saves in the offline master DB")
    args = parser.parse_args()
    if args.mode not in ("init", "player-migration") and any(value is not None for value in
                                   (args.world_id, args.seed, args.initial_ms, args.scale)):
        raise Invalid("world bootstrap options apply only to init")
    if args.mode != "player-migration" and (args.source or args.commit_import):
        raise Invalid("native import options apply only to player-migration")
    if args.mode != "bridge-config" and any(value is not None for value in (args.local_world_id, args.local_seed)):
        raise Invalid("local checkpoint binding options apply only to bridge-config")
    if args.mode == "player-migration":
        if not args.source or len(args.location) != 1 or args.authority or args.replace or args.initial_ms is not None or args.scale is not None:
            raise Invalid("player-migration requires source, explicit world identity and exactly one location")
        player_migration(args.config, args.source, args.location[0], args.world_id, args.seed, commit=args.commit_import)
    elif args.mode == "writer-config":
        if not args.destination or len(args.location) != 1 or args.authority:
            raise Invalid("writer-config requires one location and its destination")
        create_writer_config(args.config, args.destination, args.location[0], replace=args.replace)
    elif args.mode == "init":
        create_config(args.config, args.location, world_id=args.world_id, seed=args.seed,
                      initial_ms=args.initial_ms, scale=args.scale)
        print("Created private service configuration. Tokens are not printed.")
    elif args.mode=="bridge-config":
        if not args.destination:
            raise Invalid("bridge-config requires --destination in the server userdata folder")
        if len(args.location) > 1:
            raise Invalid("a bridge config binds exactly one location")
        create_bridge_config(args.config,args.destination,local_world_id=args.local_world_id,
                             local_seed=args.local_seed,location=args.location[0] if args.location else None,
                             authority=args.authority,replace=args.replace)
        print("Created private engine bridge configuration. Token is not printed.")
    else:
        run(args.config, args.port, interactive=args.mode == "console")


if __name__ == "__main__":
    main()
