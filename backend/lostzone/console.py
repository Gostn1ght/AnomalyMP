"""Operator console for the separate World Service process.

It operates the real backend, not a second registry or a game server. Native
location adoption is a separate adapter; its observer is not authority.
"""
from collections import Counter
import os
import sys
import hashlib
import json
import uuid

from .store import Invalid, Unavailable, finite, identifier
from .timelines import Timelines


HELP = ("Команды: status, clock, locations, characters, npcs, transfers, events, "
        "scale <число>, weather, emission, help, quit.\n"
        "weather <исходный цикл> <новый цикл> <секунды перехода>;\n"
        "emission <секунды предупреждения> <до пика> <после пика> <интенсивность>.\n"
        "Длительности: 0.001..86400 игровых секунд; интенсивность: (0,100].\n"
        "Мастер задаёт календарь, погоду, выбросы и пси-штормы подключённых карт.")


class Console:
    def __init__(self, server, stop):
        self.server, self.stop = server, stop
        self.dispatcher = server.dispatcher
        self.store = self.dispatcher.store
        self.principal = next((principal for _, principal in server.credentials.entries
                               if principal.role == "admin"), None)
        if self.principal is None:
            raise Invalid("master console requires an administrator credential")

    def rows(self, query):
        with self.store.lock:
            self.store.require_epoch(self.store.db)
            return [dict(row) for row in self.store.db.execute(query)]

    def submit(self, operation, arguments, command_id=None):
        if not self.server.ready.is_set():
            raise Unavailable("world recovery has not completed")
        return self.dispatcher.execute(self.principal, {
            "command_id": command_id or uuid.uuid4().hex,
            "operation": operation, "arguments": arguments,
        })

    def timeline(self, name, args):
        if not args:
            with self.store.lock:
                self.store.require_epoch(self.store.db)
                row = self.store.db.execute("SELECT state FROM world_state WHERE name=?", (name,)).fetchone()
                if not row:
                    return f"{name}: расписание ещё не задано."
                if len(row[0]) > 65536:
                    raise Invalid("timeline exceeds console read limit")
                state = Timelines.evaluate(name, json.loads(row[0]), self.dispatcher.world.now())
            parameters = state["parameters"]
            details = (f"{parameters['source']} -> {parameters['target']}; blend={state['blend']:.3f}"
                       if name == "weather" else f"intensity={parameters['intensity']}")
            prefix = "Восстановление; " if not self.server.ready.is_set() else ""
            return f"{prefix}{name}: {state['phase']}; {details}."
        if len(args) != (3 if name == "weather" else 4):
            raise Invalid("invalid timeline command arguments")
        if name == "weather":
            parameters = {"source": identifier(args[0]), "target": identifier(args[1])}
            durations = [finite(float(args[2]), .001, 86400)]
            phases = ("TRANSITION", "SETTLED")
        else:
            durations = [finite(float(value), .001, 86400) for value in args[:3]]
            intensity = finite(float(args[3]), 0, 100)
            if intensity == 0:
                raise Invalid("emission intensity must be positive")
            parameters = {"intensity": intensity}
            phases = ("WARNING", "ACTIVE", "PEAK", "ENDED")
        command_id = uuid.uuid4().hex
        world = self.dispatcher.world
        parameters["seed"] = int.from_bytes(hashlib.sha256(
            f"console-timeline:{world.world_id}:{world.seed}:{name}:{command_id}".encode()).digest()[:8], "big")
        at = world.now()
        times = {phases[0]: at}
        for phase, seconds in zip(phases[1:], durations):
            at = finite(at + seconds * 1000)
            times[phase] = at
        result = self.submit("timeline_schedule", {"name": name, "timeline_id": command_id,
                             "version": None, "times": times, "parameters": parameters}, command_id)
        return f"{name}: расписание сохранено; version={result['version']}; ID={result['timeline_id']}."

    def execute(self, line):
        if len(line) > 256:
            raise Invalid("console command too long")
        parts = line.split()
        if not parts:
            return ""
        command, args = parts[0].lower(), parts[1:]
        if command in ("weather", "emission"):
            return self.timeline(command, args)
        if command == "scale":
            if len(args) != 1:
                raise Invalid("scale requires one number")
            result = self.submit("world_scale", {"value": float(args[0])})
            return f"Масштаб времени: {result['scale']}; календарь: {result['world_ms']} мс."
        if args:
            raise Invalid("command does not take arguments")
        if command == "help":
            return HELP
        if command in ("quit", "exit"):
            self.stop.set()
            return "Завершение мастера с сохранением календаря..."
        if command == "status":
            status = self.server.recovery_status()
            world = status["world"]
            ready = "готов" if status["admission_ready"] else "восстанавливается"
            return (f"Мастер: {ready}; WorldID={world['world_id']}; epoch={world['epoch']}.\n"
                    f"Просроченные события (выборка): {status['due_sample_count']}; "
                    f"обработано: {status['events_processed']}; "
                    f"ошибка worker: {status['worker_error_type'] or 'нет'}.")
        if command == "clock":
            scale = self.rows("SELECT scale FROM world WHERE singleton=1")[0]["scale"]
            return f"Календарь: {self.dispatcher.world.now()} мс; масштаб времени: {scale}."
        if command == "locations":
            rows = self.rows("SELECT location,owner,fence,expires_ms FROM location_lease ORDER BY location LIMIT 65")
            text = [f"{row['location']}: владелец={row['owner']}; fence={row['fence']}; expires={row['expires_ms']}"
                    for row in rows[:64]]
            if len(rows) > 64:
                text.append("Показаны первые 64 локации.")
            return "\n".join(text) or "Локации ещё не подключились к мастеру."
        if command == "characters":
            characters = self.rows("SELECT id FROM character ORDER BY id LIMIT 1025")
            sessions = self.rows("SELECT state FROM player_session ORDER BY character_id LIMIT 1025")
            counts = Counter(row["state"] for row in sessions[:1024])
            suffix = "+" if len(characters) > 1024 else ""
            return f"Персонажей: {min(len(characters), 1024)}{suffix}. Сессии (выборка до 1024): " + (
                ", ".join(f"{state}={count}" for state, count in sorted(counts.items())) or "нет") + (
                "; есть ещё записи" if len(sessions) > 1024 else "")
        if command == "npcs":
            rows = self.rows("SELECT kind,alive FROM entity ORDER BY id LIMIT 1025")
            counts = Counter((row["kind"], row["alive"]) for row in rows[:1024]
                             if row["kind"] in ("NPC", "MUTANT", "GROUP"))
            text = "\n".join(f"{kind}: alive={alive}; записей={count}" for (kind, alive), count in sorted(counts.items()))
            return "Первые 1024 записи реестра:\n" + (text or "В этой выборке NPC нет.") + (
                "\nЕсть ещё записи реестра." if len(rows) > 1024 else "")
        if command == "transfers":
            rows = self.rows("SELECT state FROM transfer ORDER BY id LIMIT 1025")
            counts = Counter(row["state"] for row in rows[:1024])
            return "Переходы (выборка до 1024): " + (
                ", ".join(f"{state}={count}" for state, count in sorted(counts.items())) or "нет") + (
                "; есть ещё записи" if len(rows) > 1024 else "")
        if command == "events":
            rows = self.rows("SELECT sequence,type,aggregate_id,world_ms FROM world_event ORDER BY sequence DESC LIMIT 10")
            return "\n".join(f"#{row['sequence']} {row['type']} {row['aggregate_id']} @ {row['world_ms']} мс"
                             for row in rows) or "Глобальных событий пока нет."
        raise Invalid("unknown console command")


class Style:
    """ANSI colours only for a real console window; tests and pipes get plain text."""
    def __init__(self, enabled):
        self.enabled = enabled

    def __call__(self, code, text):
        return f"\x1b[{code}m{text}\x1b[0m" if self.enabled else text

    @staticmethod
    def detect(read, write):
        if read is not input or write is not print or not sys.stdout.isatty():
            return Style(False)
        if os.name == "nt":
            try:  # enable VT processing for cmd.exe (Windows 10+)
                import ctypes
                kernel = ctypes.windll.kernel32
                handle = kernel.GetStdHandle(-11)
                mode = ctypes.c_uint32()
                if not kernel.GetConsoleMode(handle, ctypes.byref(mode)) or \
                        not kernel.SetConsoleMode(handle, mode.value | 0x0004):
                    return Style(False)
            except Exception:
                return Style(False)
        return Style(True)


ACCENT, MUTED, ERROR, OK = "38;2;217;164;65", "38;2;140;140;145", "38;2;229;83;75", "38;2;76;195;138"


def run_console(server, stop, read=input, write=print):
    console = Console(server, stop)
    style = Style.detect(read, write)
    rule = style(MUTED, "─" * 64)
    write(rule)
    write(style("1;" + ACCENT, "  LOST ZONE") + style(MUTED, "  ·  мастер кластера"))
    try:
        write("  " + console.execute("status").replace("\n", "\n  "))
    except Exception as error:
        write("  " + style(ERROR, f"Состояние недоступно ({type(error).__name__})."))
    write(rule)
    write(style(MUTED, HELP))
    write("")
    prompt = style(ACCENT, "master") + style(MUTED, " › ")
    while not stop.is_set():
        try:
            line = read(prompt)
        except (EOFError, KeyboardInterrupt):
            stop.set()
            break
        try:
            result = console.execute(line)
            if result:
                write(result)
        except Exception as error:
            # Configs, command arguments and exception text can contain secrets.
            # The operator sees the error class, never tokens/state/checkpoints.
            write(style(ERROR, f"Команда не выполнена ({type(error).__name__}). help — список команд."))
