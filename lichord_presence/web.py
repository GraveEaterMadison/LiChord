from __future__ import annotations

import ipaddress
import json
import threading
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer
from pathlib import Path
from urllib.parse import urlsplit

from .config import CONFIG_PATH, PresenceConfig
from .state import get_now_playing

PAGE = Path(__file__).with_name("static") / "index.html"


def _loopback_host(value: str) -> str | None:
    try:
        parsed = urlsplit("//" + value)
        host = (parsed.hostname or "").lower()
        if host == "localhost":
            return host
        return host if ipaddress.ip_address(host).is_loopback else None
    except ValueError:
        return None


class Handler(BaseHTTPRequestHandler):
    config = PresenceConfig.load()
    lock = threading.RLock()

    def _json(self, code, data):
        body = json.dumps(data).encode()
        self.send_response(code)
        self.send_header("Content-Type", "application/json; charset=utf-8")
        self.send_header("Content-Length", str(len(body)))
        self.send_header("Cache-Control", "no-store")
        self.send_header("X-Content-Type-Options", "nosniff")
        self.end_headers()
        self.wfile.write(body)

    def do_GET(self):
        path = urlsplit(self.path).path
        if path == "/api/config":
            with self.lock:
                self._json(200, self.config.__dict__)
        elif path == "/api/now-playing":
            self._json(200, get_now_playing() or {})
        elif path == "/":
            body = PAGE.read_bytes()
            self.send_response(200)
            self.send_header("Content-Type", "text/html; charset=utf-8")
            self.send_header("Content-Length", str(len(body)))
            self.send_header("Cache-Control", "no-store")
            self.send_header("X-Content-Type-Options", "nosniff")
            self.end_headers()
            self.wfile.write(body)
        elif path == "/health":
            self._json(200, {"status": "ok", "config": str(CONFIG_PATH)})
        else:
            self._json(404, {"error": "not found"})

    def do_POST(self):
        if urlsplit(self.path).path != "/api/config":
            return self._json(404, {"error": "not found"})
        peer = self.client_address[0]
        try:
            if not ipaddress.ip_address(peer).is_loopback:
                return self._json(403, {"error": "settings are only available from this device"})
        except ValueError:
            return self._json(403, {"error": "invalid client address"})
        request_host = _loopback_host(self.headers.get("Host", ""))
        if not request_host:
            return self._json(403, {"error": "settings host must be localhost"})
        origin = self.headers.get("Origin")
        if origin:
            parsed_origin = urlsplit(origin)
            origin_host = (parsed_origin.hostname or "").lower()
            if parsed_origin.scheme != "http" or origin_host != request_host:
                return self._json(403, {"error": "cross-origin settings writes are not allowed"})
        try:
            size = int(self.headers.get("Content-Length", "0"))
            if size < 1:
                return self._json(400, {"error": "empty request body"})
            if size > 16384:
                return self._json(413, {"error": "payload too large"})
            raw = json.loads(self.rfile.read(size))
            if not isinstance(raw, dict):
                raise ValueError("Expected a JSON object")
            with self.lock:
                self.config = PresenceConfig.from_mapping(raw)
                self.config.save()
            self._json(200, self.config.__dict__)
        except (ValueError, TypeError) as exc:
            self._json(400, {"error": str(exc)})
        except OSError:
            self._json(500, {"error": "could not save settings"})

    def log_message(self, fmt, *args):
        pass


def run_web(host="127.0.0.1", port=8790):
    server = ThreadingHTTPServer((host, port), Handler)
    print(f"LiChord Presence settings: http://{host}:{port}")
    server.serve_forever()
