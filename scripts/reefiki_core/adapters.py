from __future__ import annotations

import contextlib
import io
import json
from pathlib import Path
from typing import Any

from .index_search import compact_search_row, search
from .project_paths import find_project
from .save import save_source
from .status import status


ADAPTER_TOOLS = {"reefiki_query", "reefiki_save", "reefiki_status"}


def _capture_text(fn: Any, *args: object) -> tuple[int, str]:
    stdout = io.StringIO()
    with contextlib.redirect_stdout(stdout):
        code = fn(*args)
    return int(code), stdout.getvalue()


def _parse_payload(raw_payload: str | None) -> dict[str, object]:
    if not raw_payload:
        return {}
    try:
        payload = json.loads(raw_payload)
    except json.JSONDecodeError as exc:
        raise SystemExit(f"Invalid adapter JSON payload: {exc}") from exc
    if not isinstance(payload, dict):
        raise SystemExit("Adapter JSON payload must be an object")
    return payload


def adapter_call_payload(
    root: Path,
    tool: str,
    project_name: str,
    payload: dict[str, object],
    allow_write: bool = False,
) -> dict[str, object]:
    if tool not in ADAPTER_TOOLS:
        raise SystemExit(f"Unsupported adapter tool: {tool}")
    project = find_project(root, project_name)
    base: dict[str, object] = {
        "adapter": "reefiki-local",
        "tool": tool,
        "project": project.name,
        "project_path": str(project),
        "allow_write": allow_write,
    }

    if tool == "reefiki_status":
        code, output = _capture_text(status, project)
        return {
            **base,
            "read_only": True,
            "outcome": "pass" if code == 0 else "fail",
            "exit_code": code,
            "status_text": output,
        }

    if tool == "reefiki_query":
        query = str(payload.get("query") or "")
        limit = int(payload.get("limit") or 5)
        rows = search(
            project,
            query,
            limit,
            page_type=payload.get("type") if isinstance(payload.get("type"), str) else None,
            tag=payload.get("tag") if isinstance(payload.get("tag"), str) else None,
            link_to=payload.get("link_to") if isinstance(payload.get("link_to"), str) else None,
            linked_by=payload.get("linked_by") if isinstance(payload.get("linked_by"), str) else None,
            orphan=bool(payload.get("orphan") or False),
            chunked=bool(payload.get("chunks") or False),
        )
        return {
            **base,
            "read_only": True,
            "outcome": "pass",
            "query": query,
            "count": len(rows),
            "results": [compact_search_row(row) for row in rows],
        }

    source = str(payload.get("source") or "")
    if not allow_write:
        return {
            **base,
            "read_only": False,
            "outcome": "block",
            "exit_code": 1,
            "blocking_reasons": ["write_requires_allow_write"],
            "source": source,
        }
    code, output = _capture_text(save_source, project, source)
    return {
        **base,
        "read_only": False,
        "outcome": "pass" if code == 0 else "fail",
        "exit_code": code,
        "source": source,
        "save_text": output,
    }


def print_adapter_call(
    root: Path,
    tool: str,
    project_name: str,
    raw_payload: str | None,
    allow_write: bool,
) -> int:
    payload = adapter_call_payload(
        root,
        tool,
        project_name,
        _parse_payload(raw_payload),
        allow_write=allow_write,
    )
    print(json.dumps(payload, ensure_ascii=False, indent=2))
    return int(payload.get("exit_code") or 0)
