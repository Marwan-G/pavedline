#!/usr/bin/env python3
"""Local SMS sink: a stand-in for an SMS provider, in memory, local cluster only. Standard library only.

  POST /2010-04-01/Accounts/<sid>/Messages.json   Twilio-style form (To, From, Body); 201 + JSON
  POST /messages                                  JSON {"to","from","body"} or the same form fields
  GET  /messages                                  {"messages": [...]} oldest first
  DELETE /messages                                forget everything
  GET  /healthz                                   {"status":"ok"}

Nothing is sent anywhere and nothing is written to disk. At most MAX_MESSAGES are kept (the oldest go
first); a body over MAX_BODY bytes is refused with 413; a connection idle for SOCKET_TIMEOUT seconds is
closed. No authentication: it is reachable only inside the
local cluster and through the local Gateway.
"""

import json
import os
import re
import threading
import time
import uuid
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer
from typing import cast
from urllib.parse import parse_qs

MAX_MESSAGES = 500  # the oldest are dropped first
MAX_BODY = 16 * 1024
SOCKET_TIMEOUT = 10  # seconds: a slow or silent client cannot hold a thread
TWILIO_PATH = re.compile(r"^/2010-04-01/Accounts/[^/]+/Messages(\.json)?$")


class Store:
    def __init__(self) -> None:
        self._lock = threading.Lock()
        self._messages: list[dict[str, object]] = []

    def add(self, to: str, sender: str, body: str) -> dict[str, object]:
        message: dict[str, object] = {
            "sid": "SM" + uuid.uuid4().hex,
            "to": to,
            "from": sender,
            "body": body,
            "received_at": time.time(),
        }
        with self._lock:
            self._messages.append(message)
            del self._messages[:-MAX_MESSAGES]
        return message

    def list(self) -> list[dict[str, object]]:
        with self._lock:
            return list(self._messages)

    def clear(self) -> None:
        with self._lock:
            self._messages.clear()


def make_handler(store: Store) -> type[BaseHTTPRequestHandler]:
    class Handler(BaseHTTPRequestHandler):
        server_version = "sms-sink"
        timeout = SOCKET_TIMEOUT

        def log_message(self, format: str, *args: object) -> None:  # one quiet line; no bodies
            print(f"{self.command} {self.path.split('?')[0]}", flush=True)

        def _send(self, status: int, payload: object) -> None:
            data = json.dumps(payload).encode()
            self.send_response(status)
            self.send_header("Content-Type", "application/json")
            self.send_header("Content-Length", str(len(data)))
            self.end_headers()
            self.wfile.write(data)

        def _read(self) -> bytes | None:
            length = self.headers.get("Content-Length", "0")
            if not (length.isascii() and length.isdigit() and len(length) <= 9):  # ASCII digits only
                self._send(400, {"error": "bad Content-Length"})
                return None
            if int(length) > MAX_BODY:
                self._send(413, {"error": "body too large"})
                return None
            return self.rfile.read(int(length))

        def do_GET(self) -> None:
            path = self.path.split("?")[0]
            if path == "/healthz":
                self._send(200, {"status": "ok"})
            elif path == "/messages":
                self._send(200, {"messages": store.list()})
            else:
                self._send(404, {"error": "not found"})

        def do_DELETE(self) -> None:
            if self.path.split("?")[0] == "/messages":
                store.clear()
                self._send(200, {"messages": []})
            else:
                self._send(404, {"error": "not found"})

        def do_POST(self) -> None:
            path = self.path.split("?")[0]
            twilio = bool(TWILIO_PATH.match(path))
            if not twilio and path != "/messages":
                self._send(404, {"error": "not found"})
                return
            raw = self._read()
            if raw is None:
                return
            fields: dict[str, str] = {}
            if "json" in (self.headers.get("Content-Type") or "").lower():
                try:
                    parsed = json.loads(raw or b"{}")
                except ValueError:
                    self._send(400, {"error": "invalid JSON"})
                    return
                if not isinstance(parsed, dict):
                    self._send(400, {"error": "expected a JSON object"})
                    return
                items = cast(dict[object, object], parsed).items()
                fields = {str(k).lower(): str(v) for k, v in items}
            else:
                fields = {k.lower(): v[0] for k, v in parse_qs(raw.decode("utf-8", "replace")).items()}
            to, sender, body = fields.get("to", ""), fields.get("from", ""), fields.get("body", "")
            if not to or not body:
                self._send(400, {"error": "to and body are required"})
                return
            message = store.add(to, sender, body)
            if twilio:
                reply = {"sid": message["sid"], "status": "queued", "to": to, "from": sender, "body": body}
                self._send(201, reply)
            else:
                self._send(201, message)

    return Handler


def serve(host: str, port: int, store: Store | None = None) -> ThreadingHTTPServer:
    return ThreadingHTTPServer((host, port), make_handler(store or Store()))


if __name__ == "__main__":
    server = serve("0.0.0.0", int(os.environ.get("PORT", "8080")))  # noqa: S104  (in-cluster, local only)
    print("sms-sink listening", flush=True)
    server.serve_forever()
