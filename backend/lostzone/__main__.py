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
from .store import Invalid, Store, identifier
from .world import World


def create_config(path, locations):
    path = Path(path).resolve()
    if path.exists():
        raise Invalid("configuration already exists; credentials were not replaced")
    locations = sorted(set(locations or ["hidden_base"]))
    for location in locations:
        identifier(location)
    path.parent.mkdir(parents=True, exist_ok=True)
    credentials = {"admin": {"role": "admin", "token": secrets.token_urlsafe(48)}}
    for location in locations:
        credentials["location:" + location] = {"role": "location", "locations": [location],
                                                 "token": secrets.token_urlsafe(48)}
    config = {"schema": 1, "database": "world.sqlite", "port": 38477,
              "signing_key": secrets.token_hex(32), "credentials": credentials}
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


def run(path, port_override=None):
    path = Path(path).resolve()
    config = json.loads(path.read_text(encoding="utf-8"))
    if config.get("schema") != 1:
        raise Invalid("unsupported service configuration")
    credentials = Credentials(config.get("credentials"))
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
    try:
        world = World(store, world_id=config.get("world_id"), seed=config.get("seed"),
                      initial_ms=config.get("initial_ms", 0), scale=config.get("scale", 10))
        server = Server(("127.0.0.1", port), Dispatcher(world, key, config.get("quests", {})), credentials)
        def checkpoints():
            last = time.monotonic()
            while not stop.wait(1):
                try:
                    server.dispatcher.timelines.scheduler.run_due(limit=64, budget_ms=10)
                    if time.monotonic() - last >= 5:
                        world.sample()
                        last = time.monotonic()
                    server.ready.set()
                except Exception:
                    server.ready.clear()
        checkpoint = threading.Thread(target=checkpoints, name="world-checkpoint")
        checkpoint.start()
        worker = threading.Thread(target=server.serve_forever, name="world-http")
        worker.start()
        if threading.current_thread() is threading.main_thread():
            for name in ("SIGINT", "SIGTERM"):
                if hasattr(signal, name):
                    signal.signal(getattr(signal, name), lambda signum, frame: stop.set())
        print(f"Lost Zone World listening on 127.0.0.1:{server.server_address[1]}; epoch={store.epoch}", flush=True)
        while not stop.wait(1):
            if not worker.is_alive():
                raise RuntimeError("world listener stopped")
    finally:
        stop.set()
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
    parser.add_argument("mode", choices=("init", "serve"))
    parser.add_argument("--config", required=True)
    parser.add_argument("--location", action="append", default=[])
    parser.add_argument("--port", type=int)
    args = parser.parse_args()
    if args.mode == "init":
        create_config(args.config, args.location)
        print("Created private service configuration. Tokens are not printed.")
    else:
        run(args.config, args.port)


if __name__ == "__main__":
    main()
