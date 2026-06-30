from __future__ import annotations

import json
from pathlib import Path
from typing import Any

from .adapters import adapter_call_payload
from .cross_project import cross_project_query_payload


def _write_guard_passed(payload: dict[str, Any]) -> bool:
    reasons = payload.get("blocking_reasons")
    return (
        payload.get("outcome") == "block"
        and isinstance(reasons, list)
        and "write_requires_allow_write" in reasons
    )


def adapter_smoke_payload(root: Path, project_name: str, query: str, limit: int) -> dict[str, Any]:
    bounded_limit = max(1, limit)
    checks = {
        "status": adapter_call_payload(root, "reefiki_status", project_name, {}, allow_write=False),
        "query": adapter_call_payload(
            root,
            "reefiki_query",
            project_name,
            {"query": query, "limit": bounded_limit},
            allow_write=False,
        ),
        "project_lookup": cross_project_query_payload(
            root,
            query,
            bounded_limit,
            project_names=[project_name],
        ),
        "write_guard": adapter_call_payload(
            root,
            "reefiki_save",
            project_name,
            {"source": "adapter-smoke-write-guard"},
            allow_write=False,
        ),
    }
    read_checks_passed = (
        checks["status"].get("outcome") == "pass"
        and checks["status"].get("read_only") is True
        and checks["query"].get("outcome") == "pass"
        and checks["query"].get("read_only") is True
        and checks["project_lookup"].get("read_only") is True
    )
    guard_passed = _write_guard_passed(checks["write_guard"])
    outcome = "pass" if read_checks_passed and guard_passed else "fail"
    return {
        "adapter": "reefiki-local",
        "transport": "local-cli-json",
        "project": project_name,
        "query": query,
        "limit": bounded_limit,
        "daemon_started": False,
        "network_listener": False,
        "mcp_config_written": False,
        "outcome": outcome,
        "exit_code": 0 if outcome == "pass" else 1,
        "checks": checks,
        "blocked_actions": [
            {
                "tool": "reefiki_save",
                "reason": "write_requires_allow_write",
                "outcome": checks["write_guard"].get("outcome"),
            }
        ],
    }


def print_adapter_smoke(root: Path, project_name: str, query: str, limit: int, fmt: str) -> int:
    payload = adapter_smoke_payload(root, project_name, query, limit)
    if fmt == "json":
        print(json.dumps(payload, ensure_ascii=False, indent=2))
        return int(payload["exit_code"])
    print(f"adapter: {payload['adapter']}")
    print(f"transport: {payload['transport']}")
    print(f"project: {payload['project']}")
    print(f"query: {payload['query']}")
    print(f"daemon_started: {str(payload['daemon_started']).lower()}")
    print(f"network_listener: {str(payload['network_listener']).lower()}")
    print(f"mcp_config_written: {str(payload['mcp_config_written']).lower()}")
    print(f"outcome: {payload['outcome']}")
    for name, check in payload["checks"].items():
        outcome = check.get("outcome", "pass" if check.get("read_only") is True else "unknown")
        read_only = check.get("read_only")
        print(f"- {name}: outcome={outcome} read_only={str(read_only).lower()}")
    return int(payload["exit_code"])
