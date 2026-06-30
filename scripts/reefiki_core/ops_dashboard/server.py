"""HTTP server for the Ops Dashboard v2.

Local-first, localhost-only, read-only. Binds strictly to 127.0.0.1.
Serves:
    GET /                  → index.html
    GET /static/<file>     → static assets (css, js, json)
    GET /api/snapshot      → build_snapshot() as JSON
    GET /api/health        → tiny health probe (no expensive work)
    GET /api/logs/health   → allowlisted live-log source status
    GET /api/logs/tail     → allowlisted live-log tail JSON
"""

from __future__ import annotations

import json
import mimetypes
import os
import re
import sys
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer
from pathlib import Path
from typing import Any
from urllib.parse import parse_qs, urlparse

from .logs import RuntimeLogBuffer, build_log_sources, logs_health_payload, logs_tail_payload
from .snapshot import SCHEMA_VERSION, build_snapshot

DEFAULT_PORT = 7310
STATIC_DIR = Path(__file__).resolve().parent / "static"
STATIC_NEXT_DIR = Path(__file__).resolve().parent / "static_next"
UI_STATIC_DIRS = {
    "current": STATIC_DIR,
    "next": STATIC_NEXT_DIR,
}
MAX_STATIC_BYTES = 256_000  # 256 KB per file; plenty for our tiny assets
ALLOWED_STATIC = {"index.html", "app.js", "theme.css", "i18n.json"}


def _now_iso() -> str:
    from datetime import datetime, timezone
    return datetime.now(timezone.utc).replace(microsecond=0).isoformat()


def _json_response(handler: BaseHTTPRequestHandler, payload: Any, status: int = 200) -> None:
    data = json.dumps(payload, ensure_ascii=False, indent=2, default=str).encode("utf-8")
    try:
        handler.send_response(status)
        handler.send_header("Content-Type", "application/json; charset=utf-8")
        handler.send_header("Cache-Control", "no-store")
        handler.send_header("Content-Length", str(len(data)))
        handler.end_headers()
        handler.wfile.write(data)
    except (BrokenPipeError, ConnectionAbortedError, ConnectionResetError):
        return


def _html_response(handler: BaseHTTPRequestHandler, body: str, status: int = 200) -> None:
    data = body.encode("utf-8")
    try:
        handler.send_response(status)
        handler.send_header("Content-Type", "text/html; charset=utf-8")
        handler.send_header("Cache-Control", "no-store")
        handler.send_header("Content-Length", str(len(data)))
        handler.end_headers()
        handler.wfile.write(data)
    except (BrokenPipeError, ConnectionAbortedError, ConnectionResetError):
        return


def _static_response(handler: BaseHTTPRequestHandler, name: str, static_dir: Path) -> None:
    if name not in ALLOWED_STATIC:
        _json_response(handler, {"error": "not found"}, status=404)
        return
    path = static_dir / name
    if not path.exists() or not path.is_file():
        _json_response(handler, {"error": "not found"}, status=404)
        return
    if path.stat().st_size > MAX_STATIC_BYTES:
        _json_response(handler, {"error": "file too large"}, status=413)
        return
    ctype, _ = mimetypes.guess_type(name)
    if ctype is None:
        ctype = "application/octet-stream"
    data = path.read_bytes()
    try:
        handler.send_response(200)
        handler.send_header("Content-Type", f"{ctype}; charset=utf-8")
        handler.send_header("Cache-Control", "no-store")
        handler.send_header("Content-Length", str(len(data)))
        handler.end_headers()
        handler.wfile.write(data)
    except (BrokenPipeError, ConnectionAbortedError, ConnectionResetError):
        return


def make_ops_dashboard_handler(
    workspace_root: Path,
    reefiki_root: Path,
    log_sources: dict[str, dict[str, Any]],
    default_log_source_id: str | None,
    runtime_log: RuntimeLogBuffer,
    ui: str = "current",
) -> type[BaseHTTPRequestHandler]:
    static_dir = UI_STATIC_DIRS.get(ui)
    if static_dir is None:
        raise SystemExit(f"unsupported ops-dashboard ui: {ui}")

    class OpsDashboardHandler(BaseHTTPRequestHandler):
        server_version = "REEFIKIOpsDashboardV2/1.0"

        def log_message(self, format: str, *args: object) -> None:  # noqa: A002
            return

        def do_GET(self) -> None:  # noqa: N802
            parsed = urlparse(self.path)
            query = parse_qs(parsed.query)
            try:
                if parsed.path in {"/", "/index.html"}:
                    index_path = static_dir / "index.html"
                    if not index_path.exists():
                        _json_response(
                            self,
                            {"error": "dashboard not installed", "hint": str(index_path)},
                            status=500,
                        )
                        return
                    _html_response(self, index_path.read_text(encoding="utf-8"))
                    return
                if parsed.path == "/favicon.ico":
                    self.send_response(204)
                    self.send_header("Cache-Control", "no-store")
                    self.send_header("Content-Length", "0")
                    self.end_headers()
                    return
                m = re.match(r"^/static/([A-Za-z0-9_.\-]+)$", parsed.path)
                if m:
                    _static_response(self, m.group(1), static_dir)
                    return
                if parsed.path == "/api/snapshot":
                    _json_response(self, build_snapshot(workspace_root, reefiki_root))
                    return
                if parsed.path == "/api/health":
                    _json_response(
                        self,
                        {
                            "ok": True,
                            "schema_version": SCHEMA_VERSION,
                            "generated_at": _now_iso(),
                        },
                    )
                    return
                if parsed.path == "/api/logs/health":
                    _json_response(self, logs_health_payload(log_sources, default_log_source_id))
                    return
                if parsed.path == "/api/logs/tail":
                    source_id = (query.get("source") or [""])[0] or None
                    since = (query.get("since") or [""])[0] or None
                    limit_raw = (query.get("limit") or ["40"])[0]
                    try:
                        limit = int(limit_raw)
                    except ValueError:
                        limit = 40
                    payload = logs_tail_payload(log_sources, source_id, since=since, limit=limit)
                    _json_response(self, payload, status=200 if payload.get("ok") else 400)
                    return
                _json_response(self, {"error": "not found"}, status=404)
            except SystemExit as exc:
                runtime_log.append("error", f"server error {parsed.path}: {exc}")
                _json_response(self, {"error": str(exc)}, status=400)
            except Exception as exc:  # noqa: BLE001
                runtime_log.append("error", f"server exception {parsed.path}: {type(exc).__name__}: {exc}")
                _json_response(self, {"error": f"{type(exc).__name__}: {exc}"}, status=500)

    return OpsDashboardHandler


def build_ops_dashboard_server(
    workspace_root: Path,
    reefiki_root: Path,
    port: int,
    host: str = "127.0.0.1",
    allow_log_paths: list[str] | None = None,
    ui: str = "current",
) -> ThreadingHTTPServer:
    if host not in {"127.0.0.1", "::1", "localhost"}:
        raise SystemExit(f"ops-dashboard v2 binds only to localhost (got: {host})")
    if ui not in UI_STATIC_DIRS:
        raise SystemExit(f"unsupported ops-dashboard ui: {ui}")
    runtime_log = RuntimeLogBuffer()
    log_sources, default_log_source_id = build_log_sources(
        workspace_root,
        reefiki_root,
        runtime_log,
        allow_log_paths=allow_log_paths,
    )
    runtime_log.append(
        "info",
        f"ops-dashboard server ready ui={ui} with {len(log_sources)} log source(s)"
        + (f"; default={default_log_source_id}" if default_log_source_id else ""),
    )
    handler = make_ops_dashboard_handler(
        workspace_root,
        reefiki_root,
        log_sources,
        default_log_source_id,
        runtime_log,
        ui=ui,
    )
    return ThreadingHTTPServer((host, port), handler)


def serve_ops_dashboard(
    workspace_root: Path,
    reefiki_root: Path,
    port: int,
    allow_log_paths: list[str] | None = None,
    ui: str = "current",
) -> int:
    server = build_ops_dashboard_server(
        workspace_root,
        reefiki_root,
        port,
        host="127.0.0.1",
        allow_log_paths=allow_log_paths,
        ui=ui,
    )
    host, bound_port = server.server_address
    suffix = "next" if ui == "next" else "v2"
    print(f"REEFIKI Ops Dashboard {suffix}: http://{host}:{bound_port}", flush=True)
    try:
        server.serve_forever()
    except KeyboardInterrupt:
        pass
    finally:
        server.server_close()
    return 0
