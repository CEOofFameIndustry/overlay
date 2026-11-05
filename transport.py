#!/usr/bin/python3
"""Firefox native host plus local hotkey client. Never calls the Gemini API."""
import argparse
import base64
import fcntl
import json
import os
from pathlib import Path
import socket
import struct
import subprocess
import sys
import threading
import time
import uuid

import desktop_support as dot


SOCKET = dot.RUNTIME / "web.sock"
MAX_MESSAGE = 1024 * 1024


def source_output(state):
    matches = [w for w in state.get("workspaces", []) if str(w.get("id")) == "1" and w.get("active")]
    if len(matches) != 1:
        raise RuntimeError("Робочий стіл 1 має бути видимим. Відкрийте на ньому тест і натисніть ↑.")
    return matches[0]["output"]


def state():
    return json.loads(dot.run(["ryoku", "wm", "state"]).stdout)


def read_exact(stream, count):
    result = bytearray()
    while len(result) < count:
        chunk = stream.read(count - len(result))
        if not chunk:
            raise EOFError
        result.extend(chunk)
    return bytes(result)


def read_native(stream):
    size = struct.unpack("=I", read_exact(stream, 4))[0]
    if not 1 <= size <= MAX_MESSAGE:
        raise ValueError("Native message too large")
    return json.loads(read_exact(stream, size))


class Host:
    def __init__(self):
        self.writer_lock = threading.Lock()
        self.job_lock = threading.Lock()
        self.job = None
        self.target = ""
        self.last_status = "Очікування підключення розширення."
        self.pending = {}
        self.closed = threading.Event()

    def send(self, message):
        raw = json.dumps(message, ensure_ascii=False, separators=(",", ":")).encode()
        if len(raw) >= MAX_MESSAGE:
            raise ValueError("Native message too large")
        with self.writer_lock:
            sys.stdout.buffer.write(struct.pack("=I", len(raw)) + raw)
            sys.stdout.buffer.flush()

    def notify(self, text):
        self.last_status = text
        dot.notify(text)

    def cancel(self):
        with self.job_lock:
            job = self.job
            if job:
                job["cancelled"].set()
                self.send({"type": "cancel", "id": job["id"]})
        dot.hide()

    def command(self, command):
        if command == "status":
            with self.job_lock:
                return {"connected": bool(self.target), "target": self.target,
                        "busy": self.job is not None, "message": self.last_status}
        if command == "cancel":
            self.cancel()
            return {"ok": True}
        if command == "diagnose":
            identifier = str(uuid.uuid4())
            item = {"event": threading.Event(), "reply": None}
            self.pending[identifier] = item
            self.send({"type": "diagnose", "id": identifier})
            item["event"].wait(10)
            self.pending.pop(identifier, None)
            return item["reply"] or {"error": "Firefox не відповів на діагностику."}
        if command != "run":
            return {"error": "Unknown command"}
        with self.job_lock:
            if not self.target:
                return {"error": "Виберіть чат у розширенні Gemini Dot у Firefox."}
            if self.job:
                return {"error": "Запит уже виконується. ↓ — скасувати."}
            job = {"id": str(uuid.uuid4()), "cancelled": threading.Event(),
                   "reply_event": threading.Event(), "reply": None}
            self.job = job
            self.last_status = "Знімаю стіл 1 та розпізнаю номери варіантів."
        threading.Thread(target=self.solve, args=(job,), daemon=True).start()
        return {"ok": True}

    def solve(self, job):
        raise NotImplementedError

    def receive(self, data):
        if not isinstance(data, dict):
            return
        if data.get("type") == "hello":
            target = str(data.get("target", ""))
            if target.startswith(("https://gemini.google.com/", "https://chatgpt.com/", "https://claude.ai/")):
                self.target = target
                self.last_status = "Вебчат підключено. ↑ — знімок столу 1; ↓ — скасувати."
        elif data.get("type") == "cancel-request":
            self.cancel()
        elif data.get("type") == "progress":
            with self.job_lock:
                if self.job and self.job["id"] == data.get("id"):
                    self.last_status = str(data.get("message", ""))[:400]
        elif data.get("type") == "diagnostic" and data.get("id") in self.pending:
            item = self.pending[data["id"]]
            item["reply"] = data.get("report")
            item["event"].set()
        elif data.get("type") in ("answer", "error"):
            with self.job_lock:
                if self.job and self.job["id"] == data.get("id"):
                    self.job["reply"] = data
                    self.job["reply_event"].set()

    def serve_socket(self, server):
        server.settimeout(1)
        while not self.closed.is_set():
            try:
                connection, _ = server.accept()
            except socket.timeout:
                continue
            with connection:
                connection.settimeout(12)
                try:
                    uid = struct.unpack("3i", connection.getsockopt(socket.SOL_SOCKET, socket.SO_PEERCRED, 12))[1]
                    if uid != os.getuid():
                        continue
                    raw = connection.recv(1024)
                    request = json.loads(raw)
                    response = self.command(request.get("command"))
                    connection.sendall(json.dumps(response, ensure_ascii=False).encode())
                except (OSError, ValueError):
                    pass

    def run(self):
        dot.runtime()
        with (dot.RUNTIME / "web-host.lock").open("w") as lock:
            fcntl.flock(lock, fcntl.LOCK_EX | fcntl.LOCK_NB)
            SOCKET.unlink(missing_ok=True)
            with socket.socket(socket.AF_UNIX, socket.SOCK_STREAM) as server:
                server.bind(str(SOCKET)); SOCKET.chmod(0o600); server.listen(4)
                threading.Thread(target=self.serve_socket, args=(server,), daemon=True).start()
                self.send({"type": "ready"})
                try:
                    while True:
                        self.receive(read_native(sys.stdin.buffer))
                except (EOFError, BrokenPipeError):
                    pass
                finally:
                    self.closed.set()
                    if self.job:
                        self.job["cancelled"].set()
                    dot.hide()
                    SOCKET.unlink(missing_ok=True)


def client(command):
    try:
        with socket.socket(socket.AF_UNIX, socket.SOCK_STREAM) as sock:
            sock.settimeout(12)
            sock.connect(str(SOCKET))
            sock.sendall(json.dumps({"command": command}).encode())
            response = json.loads(sock.recv(65536))
        if response.get("error"):
            dot.notify(response["error"])
            return 1
        if command in ("status", "diagnose"):
            print(json.dumps(response, ensure_ascii=False, indent=2))
        return 0
    except (OSError, ValueError) as error:
        if command == "cancel":
            dot.hide()
        if command in ("status", "diagnose"):
            print(f"Локальний канал {SOCKET}: {type(error).__name__}: {error}", file=sys.stderr)
        dot.notify("Вебчат не підключено. Завантажте розширення у Firefox і відкрийте його панель.")
        return 1


if __name__ == "__main__":
    # Firefox passes its native-host manifest and addon ID as positional args.
    if len(sys.argv) > 1 and sys.argv[1] in ("run", "cancel", "status", "diagnose"):
        sys.exit(client(sys.argv[1]))
    Host().run()
