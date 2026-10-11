"""Operator console for the separate World Service process.

It operates the real backend, not a second registry or a game server. Native
location adoption is a separate adapter; its observer is not authority.
"""
from collections import Counter
import uuid

from .store import Invalid, Unavailable


HELP = ("Команды: status, clock, locations, characters, npcs, transfers, events, "
        "scale <число>, help, quit.\n"
        "Подключение игровых серверов к этому мастеру ещё не выполнено.")


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

    def execute(self, line):
        if len(line) > 256:
            raise Invalid("console command too long")
        parts = line.split()
        if not parts:
            return ""
        command, args = parts[0].lower(), parts[1:]
        if command == "scale":
            if len(args) != 1:
                raise Invalid("scale requires one number")
            if not self.server.ready.is_set():
                raise Unavailable("world recovery has not completed")
            result = self.dispatcher.execute(self.principal, {
                "command_id": uuid.uuid4().hex, "operation": "world_scale",
                "arguments": {"value": float(args[0])},
            })
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


def run_console(server, stop, read=input, write=print):
    console = Console(server, stop)
    write("Lost Zone — отдельный мастер кластера")
    write(HELP)
    while not stop.is_set():
        try:
            line = read("master> ")
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
            write(f"Команда не выполнена ({type(error).__name__}). help — список команд.")
