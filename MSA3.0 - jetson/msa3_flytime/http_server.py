from __future__ import annotations

import datetime as dt
import json
import mimetypes
import os
from http import HTTPStatus
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer
from pathlib import Path
from typing import Any
from urllib.parse import parse_qs, unquote, urlparse

from .db import SqliteStore


def _json(handler: BaseHTTPRequestHandler, status: int, data: Any) -> None:
    body = json.dumps(data, ensure_ascii=False).encode("utf-8")
    handler.send_response(status)
    handler.send_header("Content-Type", "application/json; charset=utf-8")
    handler.send_header("Content-Length", str(len(body)))
    handler.send_header("Cache-Control", "no-store")
    handler.end_headers()
    handler.wfile.write(body)


def _bad_request(handler: BaseHTTPRequestHandler, message: str) -> None:
    _json(handler, HTTPStatus.BAD_REQUEST, {"error": message})


def _parse_date(value: str | None) -> dt.date | None:
    if not value:
        return None
    try:
        return dt.date.fromisoformat(value)
    except Exception:
        return None


def _seconds_to_hhmm(seconds: int) -> str:
    seconds = max(0, int(seconds))
    hours = seconds // 3600
    minutes = (seconds % 3600) // 60
    return f"{hours:02d}:{minutes:02d}"


class AppHandler(BaseHTTPRequestHandler):
    store: SqliteStore
    static_dir: Path

    def log_message(self, fmt: str, *args) -> None:  # quiet default
        return

    def do_GET(self) -> None:
        parsed = urlparse(self.path)
        path = parsed.path
        qs = parse_qs(parsed.query)

        if path.startswith("/api/"):
            self._handle_api(path, qs)
            return

        self._handle_static(path)

    def _handle_api(self, path: str, qs: dict[str, list[str]]) -> None:
        if path == "/api/health":
            _json(self, 200, {"ok": True})
            return

        if path == "/api/drones":
            drones = self.store.list_drones()
            _json(
                self,
                200,
                [
                    {"drone_sn": d.drone_sn, "drone_type": d.drone_type, "drone_version": d.drone_version}
                    for d in drones
                ],
            )
            return

        if path == "/api/summary":
            start = _parse_date((qs.get("start") or [None])[0])
            end = _parse_date((qs.get("end") or [None])[0])
            if not start or not end:
                _bad_request(self, "Missing or invalid start/end (YYYY-MM-DD)")
                return
            if end < start:
                _bad_request(self, "end must be >= start")
                return

            rows = self.store.summary_by_range(start, end)
            for r in rows:
                r["total_hhmm"] = _seconds_to_hhmm(int(r["total_seconds"]))
            _json(self, 200, rows)
            return

        if path.startswith("/api/drone/") and path.endswith("/range"):
            # /api/drone/<sn>/range
            parts = path.split("/")
            if len(parts) != 5:
                _bad_request(self, "Invalid path")
                return
            drone_sn = unquote(parts[3])
            start = _parse_date((qs.get("start") or [None])[0])
            end = _parse_date((qs.get("end") or [None])[0])
            if not start or not end:
                _bad_request(self, "Missing or invalid start/end (YYYY-MM-DD)")
                return
            if end < start:
                _bad_request(self, "end must be >= start")
                return

            rows = self.store.drone_daily_breakdown(drone_sn, start, end)
            for r in rows:
                r["hhmm"] = _seconds_to_hhmm(int(r["seconds"]))
            _json(self, 200, {"drone_sn": drone_sn, "days": rows})
            return

        _json(self, HTTPStatus.NOT_FOUND, {"error": "not found"})

    def _handle_static(self, path: str) -> None:
        if path == "/":
            path = "/index.html"

        # Prevent directory traversal
        rel = path.lstrip("/")
        if ".." in rel or rel.startswith("\\"):
            self.send_error(HTTPStatus.NOT_FOUND)
            return

        file_path = (self.static_dir / rel).resolve()
        if not str(file_path).startswith(str(self.static_dir.resolve())):
            self.send_error(HTTPStatus.NOT_FOUND)
            return

        if not file_path.exists() or not file_path.is_file():
            self.send_error(HTTPStatus.NOT_FOUND)
            return

        ctype, _ = mimetypes.guess_type(str(file_path))
        ctype = ctype or "application/octet-stream"
        data = file_path.read_bytes()

        self.send_response(HTTPStatus.OK)
        self.send_header("Content-Type", ctype)
        self.send_header("Content-Length", str(len(data)))
        self.send_header("Cache-Control", "no-store")
        self.end_headers()
        self.wfile.write(data)


def serve(store: SqliteStore, host: str, port: int, static_dir: str) -> ThreadingHTTPServer:
    static_path = Path(static_dir)
    if not static_path.exists():
        raise RuntimeError(f"static_dir not found: {static_dir}")

    # Bind store/static to handler class
    class _Handler(AppHandler):
        pass

    _Handler.store = store
    _Handler.static_dir = static_path

    server = ThreadingHTTPServer((host, port), _Handler)
    return server
