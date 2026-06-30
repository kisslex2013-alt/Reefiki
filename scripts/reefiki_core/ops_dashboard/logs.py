"""Allowlisted live-log helpers for the Ops Dashboard."""

from __future__ import annotations

import re
import threading
from collections import deque
from datetime import datetime, timezone
from pathlib import Path
from typing import Any

DEFAULT_LOG_STALE_SECONDS = 900
MAX_LOG_TAIL_BYTES = 256_000
MAX_LOG_LINES = 120
MAX_RUNTIME_EVENTS = 200

_SECRET_PAIR_RE = re.compile(
    r"(?i)\b(api[_-]?key|token|secret|password|authorization)\b(\s*[:=]\s*)(\S+)"
)
_BEARER_RE = re.compile(r"(?i)\bbearer\s+[A-Za-z0-9._+/=-]{10,}")
_AWS_RE = re.compile(r"\bAKIA[0-9A-Z]{16}\b")
_LONG_HEX_RE = re.compile(r"\b[a-f0-9]{32,}\b", re.IGNORECASE)
_LONG_B64_RE = re.compile(r"\b[A-Za-z0-9+/]{40,}={0,2}\b")
_LEVEL_RE = re.compile(r"\b(trace|debug|info|warn|warning|error|fatal|success|tool)\b", re.IGNORECASE)
_TIME_RE = re.compile(r"^(?P<time>(?:\d{2}:\d{2}:\d{2})|(?:\d{4}-\d{2}-\d{2}[T ][^\s]+))\s*(?P<rest>.*)$")


def _now() -> datetime:
    return datetime.now(timezone.utc)


def _now_iso() -> str:
    return _now().replace(microsecond=0).isoformat()


def _slug(text: str, fallback: str) -> str:
    slug = re.sub(r"[^a-z0-9]+", "-", text.lower()).strip("-")
    return slug or fallback


def _project_paths(reefiki_root: Path) -> list[Path]:
    projects_dir = reefiki_root / "projects"
    if not projects_dir.exists():
        return []
    return sorted(
        (path for path in projects_dir.iterdir() if path.is_dir() and path.name != "_template"),
        key=lambda item: item.name.lower(),
    )


def redact_log_line(text: str) -> tuple[str, bool]:
    redacted = text
    changed = False

    def replace_pair(match: re.Match[str]) -> str:
        nonlocal changed
        changed = True
        return f"{match.group(1)}{match.group(2)}[REDACTED]"

    redacted = _SECRET_PAIR_RE.sub(replace_pair, redacted)
    for pattern in (_BEARER_RE, _AWS_RE, _LONG_HEX_RE, _LONG_B64_RE):
        updated = pattern.sub("[REDACTED]", redacted)
        if updated != redacted:
            changed = True
            redacted = updated
    return redacted, changed


def _parse_log_line(text: str) -> dict[str, Any]:
    stripped = text.strip()
    time_text = ""
    level = "info"
    message = stripped
    time_match = _TIME_RE.match(stripped)
    if time_match:
        time_text = time_match.group("time")
        remainder = time_match.group("rest").strip()
        if remainder:
            level_match = _LEVEL_RE.match(remainder)
            if level_match:
                level = level_match.group(1).lower().replace("warning", "warn")
                message = remainder[level_match.end() :].strip() or remainder
            else:
                message = remainder
    else:
        level_match = _LEVEL_RE.search(stripped)
        if level_match:
            level = level_match.group(1).lower().replace("warning", "warn")
    return {
        "time": time_text,
        "level": level,
        "text": message or stripped,
        "raw": stripped,
    }


class RuntimeLogBuffer:
    def __init__(self, max_entries: int = MAX_RUNTIME_EVENTS, stale_seconds: int = 300) -> None:
        self._entries: deque[dict[str, Any]] = deque(maxlen=max_entries)
        self._lock = threading.Lock()
        self._seq = 0
        self._stale_seconds = stale_seconds

    @property
    def stale_seconds(self) -> int:
        return self._stale_seconds

    def append(self, level: str, message: str) -> None:
        parsed = _parse_log_line(message)
        with self._lock:
            self._seq += 1
            self._entries.append(
                {
                    "seq": self._seq,
                    "iso": _now_iso(),
                    "level": parsed["level"] if parsed["level"] else level,
                    "time": parsed["time"],
                    "text": parsed["text"],
                    "raw": parsed["raw"],
                }
            )

    def health(self) -> dict[str, Any]:
        with self._lock:
            latest = self._entries[-1] if self._entries else None
            size = len(self._entries)
        state = "live"
        age_seconds: int | None = None
        last_modified_iso = latest["iso"] if latest else None
        if latest:
            then = datetime.fromisoformat(latest["iso"].replace("Z", "+00:00"))
            age_seconds = max(0, int((_now() - then).total_seconds()))
            if age_seconds > self._stale_seconds:
                state = "stale"
        else:
            state = "stale"
        return {
            "configured": True,
            "available": True,
            "state": state,
            "size_bytes": size,
            "last_modified_iso": last_modified_iso,
            "age_seconds": age_seconds,
            "stale_after_seconds": self._stale_seconds,
            "error": None,
        }

    def tail(self, since: str | None, limit: int) -> dict[str, Any]:
        with self._lock:
            latest_seq = self._seq
            if since:
                try:
                    since_seq = int(since)
                except ValueError:
                    since_seq = 0
                entries = [entry for entry in self._entries if entry["seq"] > since_seq]
                cursor_reset = bool(entries) and since_seq < (entries[0]["seq"] - 1)
            else:
                entries = list(self._entries)[-limit:]
                cursor_reset = False
        payload_entries = []
        redacted_count = 0
        for entry in entries[-limit:]:
            redacted, changed = redact_log_line(entry["raw"])
            if changed:
                redacted_count += 1
            parsed = _parse_log_line(redacted)
            payload_entries.append(
                {
                    "cursor": str(entry["seq"]),
                    "iso": entry["iso"],
                    "time": parsed["time"] or entry["time"],
                    "level": parsed["level"] or entry["level"],
                    "text": parsed["text"],
                    "raw": redacted,
                    "redacted": changed,
                }
            )
        return {
            "cursor": str(latest_seq),
            "cursor_reset": cursor_reset,
            "entries": payload_entries,
            "redacted_count": redacted_count,
        }


def parse_allow_log_path(spec: str, index: int, base_dir: Path) -> dict[str, str]:
    if "=" in spec:
        name, raw_path = spec.split("=", 1)
        raw_name = name.strip()
    else:
        raw_name = f"extra-{index}"
        raw_path = spec
    path = Path(raw_path.strip()).expanduser()
    if not path.is_absolute():
        path = (base_dir / path).resolve(strict=False)
    else:
        path = path.resolve(strict=False)
    source_id = _slug(raw_name or path.stem, f"extra-{index}")
    label = raw_name or path.name or source_id
    return {
        "id": source_id,
        "label": label,
        "path": str(path),
    }


def build_log_sources(
    workspace_root: Path,
    reefiki_root: Path,
    runtime_log: RuntimeLogBuffer,
    allow_log_paths: list[str] | None = None,
) -> tuple[dict[str, dict[str, Any]], str | None]:
    sources: dict[str, dict[str, Any]] = {}
    default_source_id: str | None = None
    seen_file_paths: dict[str, str] = {}

    def path_key(path: Path) -> str:
        return str(path.resolve(strict=False)).casefold()

    def add_file_source(
        source_id: str,
        label: str,
        path: Path,
        kind: str,
        explicit: bool,
        stale_seconds: int = DEFAULT_LOG_STALE_SECONDS,
    ) -> str:
        nonlocal default_source_id
        resolved = path.resolve(strict=False)
        existing_source_id = seen_file_paths.get(path_key(resolved))
        if existing_source_id:
            if explicit and default_source_id is None:
                default_source_id = existing_source_id
            return existing_source_id
        sources[source_id] = {
            "id": source_id,
            "label": label,
            "kind": kind,
            "path": resolved,
            "explicit": explicit,
            "stale_after_seconds": stale_seconds,
        }
        seen_file_paths[path_key(resolved)] = source_id
        return source_id

    add_file_source(
        "reefiki-main-log",
        "REEFIKI wiki log",
        reefiki_root / "projects" / "reefiki" / "wiki" / "log.md",
        kind="wiki_log",
        explicit=False,
        stale_seconds=6 * 3600,
    )
    for project in _project_paths(reefiki_root):
        add_file_source(
            f"project-{_slug(project.name, project.name.lower())}-log",
            f"{project.name} wiki log",
            project / "wiki" / "log.md",
            kind="project_wiki_log",
            explicit=False,
            stale_seconds=6 * 3600,
        )
    sources["dashboard-runtime"] = {
        "id": "dashboard-runtime",
        "label": "ops-dashboard runtime",
        "kind": "runtime",
        "runtime_log": runtime_log,
        "explicit": False,
        "stale_after_seconds": runtime_log.stale_seconds,
    }

    for index, spec in enumerate(allow_log_paths or [], start=1):
        parsed = parse_allow_log_path(spec, index, workspace_root)
        source_id = parsed["id"]
        base_source_id = source_id
        suffix = index
        while source_id in sources:
            source_id = f"{base_source_id}-{suffix}"
            suffix += 1
        added_source_id = add_file_source(
            source_id,
            parsed["label"],
            Path(parsed["path"]),
            kind="explicit_file",
            explicit=True,
            stale_seconds=DEFAULT_LOG_STALE_SECONDS,
        )
        if default_source_id is None:
            default_source_id = added_source_id

    return sources, default_source_id


def _file_source_health(source: dict[str, Any]) -> dict[str, Any]:
    path = Path(source["path"])
    if not path.exists():
        return {
            "configured": True,
            "available": False,
            "state": "unavailable",
            "size_bytes": 0,
            "last_modified_iso": None,
            "age_seconds": None,
            "stale_after_seconds": source["stale_after_seconds"],
            "error": "file not found",
        }
    if not path.is_file():
        return {
            "configured": True,
            "available": False,
            "state": "unavailable",
            "size_bytes": 0,
            "last_modified_iso": None,
            "age_seconds": None,
            "stale_after_seconds": source["stale_after_seconds"],
            "error": "path is not a file",
        }
    try:
        stat_result = path.stat()
    except OSError as exc:
        return {
            "configured": True,
            "available": False,
            "state": "unavailable",
            "size_bytes": 0,
            "last_modified_iso": None,
            "age_seconds": None,
            "stale_after_seconds": source["stale_after_seconds"],
            "error": str(exc),
        }
    modified = datetime.fromtimestamp(stat_result.st_mtime, tz=timezone.utc)
    age_seconds = max(0, int((_now() - modified).total_seconds()))
    state = "stale" if age_seconds > source["stale_after_seconds"] else "live"
    return {
        "configured": True,
        "available": True,
        "state": state,
        "size_bytes": stat_result.st_size,
        "last_modified_iso": modified.replace(microsecond=0).isoformat(),
        "age_seconds": age_seconds,
        "stale_after_seconds": source["stale_after_seconds"],
        "error": None,
    }


def describe_log_source(source: dict[str, Any]) -> dict[str, Any]:
    if source["kind"] == "runtime":
        health = source["runtime_log"].health()
        return {
            "id": source["id"],
            "label": source["label"],
            "kind": source["kind"],
            "path": None,
            "explicit": source["explicit"],
            **health,
        }
    health = _file_source_health(source)
    return {
        "id": source["id"],
        "label": source["label"],
        "kind": source["kind"],
        "path": str(source["path"]),
        "explicit": source["explicit"],
        **health,
    }


def logs_health_payload(
    sources: dict[str, dict[str, Any]], default_source_id: str | None
) -> dict[str, Any]:
    described = [describe_log_source(source) for source in sources.values()]
    return {
        "ok": True,
        "generated_at": _now_iso(),
        "default_source_id": default_source_id,
        "sources": described,
    }


def _tail_file_source(source: dict[str, Any], since: str | None, limit: int) -> dict[str, Any]:
    path = Path(source["path"])
    health = _file_source_health(source)
    if not health["available"]:
        return {
            "source": {
                "id": source["id"],
                "label": source["label"],
                "kind": source["kind"],
                "path": str(path),
                **health,
            },
            "cursor": since or "",
            "cursor_reset": False,
            "entries": [],
            "redacted_count": 0,
            "state": health["state"],
            "error": health["error"],
        }
    size = path.stat().st_size
    cursor_reset = False
    start = 0
    if since:
        try:
            start = max(0, int(since))
        except ValueError:
            start = 0
            cursor_reset = True
    if start > size:
        start = 0
        cursor_reset = True
    if start > 0 and (size - start) > MAX_LOG_TAIL_BYTES:
        start = max(0, size - MAX_LOG_TAIL_BYTES)
        cursor_reset = True
    with path.open("rb") as handle:
        if start <= 0:
            read_from = max(0, size - MAX_LOG_TAIL_BYTES)
            handle.seek(read_from)
            chunk = handle.read()
            cursor_reset = cursor_reset or read_from > 0
        else:
            handle.seek(start)
            chunk = handle.read(MAX_LOG_TAIL_BYTES)
    text = chunk.decode("utf-8", errors="replace")
    lines = text.splitlines()
    if start <= 0 and cursor_reset and lines:
        lines = lines[1:]
    entries = []
    redacted_count = 0
    for line in lines[-limit:]:
        if not line.strip():
            continue
        redacted, changed = redact_log_line(line)
        if changed:
            redacted_count += 1
        parsed = _parse_log_line(redacted)
        entries.append(
            {
                "cursor": str(size),
                "iso": health["last_modified_iso"],
                "time": parsed["time"],
                "level": parsed["level"],
                "text": parsed["text"],
                "raw": redacted,
                "redacted": changed,
            }
        )
    return {
        "source": {
            "id": source["id"],
            "label": source["label"],
            "kind": source["kind"],
            "path": str(path),
            **health,
        },
        "cursor": str(size),
        "cursor_reset": cursor_reset,
        "entries": entries,
        "redacted_count": redacted_count,
        "state": health["state"],
        "error": None,
    }


def logs_tail_payload(
    sources: dict[str, dict[str, Any]],
    source_id: str | None,
    since: str | None = None,
    limit: int = 40,
) -> dict[str, Any]:
    limit = max(1, min(limit, MAX_LOG_LINES))
    if not source_id:
        return {
            "ok": False,
            "state": "not_configured",
            "error": "log source not configured",
            "cursor": "",
            "cursor_reset": False,
            "entries": [],
            "redacted_count": 0,
            "source": None,
        }
    source = sources.get(source_id)
    if source is None:
        return {
            "ok": False,
            "state": "not_configured",
            "error": f"unknown log source: {source_id}",
            "cursor": "",
            "cursor_reset": False,
            "entries": [],
            "redacted_count": 0,
            "source": None,
        }
    if source["kind"] == "runtime":
        health = describe_log_source(source)
        tail = source["runtime_log"].tail(since, limit)
        return {
            "ok": True,
            "state": health["state"],
            "error": None,
            "source": health,
            **tail,
        }
    payload = _tail_file_source(source, since, limit)
    return {
        "ok": payload["error"] is None,
        **payload,
    }
