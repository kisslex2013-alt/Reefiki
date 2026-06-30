from __future__ import annotations

import json
from pathlib import Path
from typing import Any

from .connect_check import connect_check_payload
from .onboarding import DEFAULT_ONBOARDING_PROJECT

TOUR_SCHEMA_VERSION = "reefiki.guided-tour.v1"
TOUR_STATUS_ORDER = ("done", "current", "todo", "blocked")


def _display_path(path: Path) -> str:
    return str(path.resolve(strict=False)).replace("\\", "/")


def _step(
    step_id: str,
    status: str,
    title: str,
    body: str,
    command: str,
    evidence: str,
    *,
    blocks_mutation: bool = True,
) -> dict[str, object]:
    return {
        "id": step_id,
        "status": status,
        "title": title,
        "body": body,
        "command": command,
        "evidence": evidence,
        "blocks_mutation": blocks_mutation,
    }


def _fixture_project(fixture_root: Path | None, project_name: str) -> Path | None:
    if fixture_root is None:
        return None
    return fixture_root / "projects" / project_name


def _fixture_ready(fixture_root: Path | None, project_name: str) -> bool:
    project = _fixture_project(fixture_root, project_name)
    if project is None:
        return False
    return (project / "AGENTS.md").is_file() and (project / "wiki" / "index.md").is_file()


def _dashboard_demo_ready(workspace_root: Path | None) -> bool:
    return bool(workspace_root and (workspace_root / ".reefiki-dashboard-demo").is_file())


def _connect_step(connect_path: Path | None) -> dict[str, object]:
    if connect_path is None:
        return _step(
            "connect",
            "blocked",
            "Connect a real project",
            "No target project path was supplied for the safe /connect handoff.",
            "reefiki /connect <path>",
            "missing connect path",
        )
    payload = connect_check_payload(connect_path)
    status = str(payload.get("status"))
    if status == "pass":
        tour_status = "done"
        body = "Bridge markers are present, ignored by git and not tracked."
    elif status == "block":
        tour_status = "blocked"
        body = "Bridge paths need review before this project can be treated as safely connected."
    else:
        tour_status = "current"
        body = "Copy the handoff command, then rerun connect-check after /connect."
    return _step(
        "connect",
        tour_status,
        "Connect a real project",
        body,
        f'reefiki /connect "{_display_path(connect_path)}"',
        f"connect-check={status}",
    )


def _summary(steps: list[dict[str, object]]) -> dict[str, object]:
    counts = {status: 0 for status in TOUR_STATUS_ORDER}
    for step in steps:
        status = str(step["status"])
        counts[status] = counts.get(status, 0) + 1
    next_step = next((step for step in steps if step["status"] == "current"), None)
    if next_step is None:
        next_step = next((step for step in steps if step["status"] == "blocked"), None)
    return {
        "counts": counts,
        "outcome": "blocked" if counts["blocked"] else "current" if counts["current"] else "done",
        "next_step": next_step,
    }


def guided_tour_payload(
    reefiki_root: Path,
    *,
    fixture_root: Path | None = None,
    workspace_root: Path | None = None,
    connect_path: Path | None = None,
    project_name: str = DEFAULT_ONBOARDING_PROJECT,
    dashboard_open: bool = False,
) -> dict[str, object]:
    fixture = fixture_root.resolve(strict=False) if fixture_root else None
    workspace = workspace_root.resolve(strict=False) if workspace_root else None
    fixture_ready = _fixture_ready(fixture, project_name)
    dashboard_demo_ready = _dashboard_demo_ready(workspace)
    demo_root = _display_path(fixture) if fixture else "<demo-folder>"
    dashboard_root = _display_path(workspace) if workspace else "<dashboard-demo-folder>"

    steps = [
        _step(
            "onboarding",
            "done",
            "Preview onboarding",
            "Review the local-first path without writing anything.",
            "reefiki onboarding",
            "onboarding CLI available",
        ),
        _step(
            "fixture",
            "done" if fixture_ready else "current",
            "Create demo fixture",
            "Create an isolated demo project before checking status.",
            f"reefiki onboarding --fixture-root {demo_root}",
            "fixture ready" if fixture_ready else "fixture missing",
            blocks_mutation=False,
        ),
        _step(
            "status",
            "done" if fixture_ready else "blocked",
            "Inspect project status",
            "Status is meaningful after the onboarding fixture exists.",
            f"reefiki --project {demo_root}/projects/{project_name} status",
            "fixture project exists" if fixture_ready else "blocked by missing fixture",
        ),
        _step(
            "dashboard",
            "done" if dashboard_open or dashboard_demo_ready else "current" if fixture_ready else "blocked",
            "Open Ops Dashboard",
            "Use a synthetic workspace demo before pointing the board at real work.",
            f"reefiki ops-dashboard serve --workspace-root {dashboard_root} --port 7310",
            "dashboard open" if dashboard_open else "demo workspace marker present" if dashboard_demo_ready else "dashboard demo not prepared",
        ),
        _connect_step(connect_path),
    ]
    summary = _summary(steps)
    return {
        "schema_version": TOUR_SCHEMA_VERSION,
        "read_only": True,
        "reefiki_root": _display_path(reefiki_root),
        "fixture_root": _display_path(fixture) if fixture else None,
        "workspace_root": _display_path(workspace) if workspace else None,
        "project": project_name,
        "steps": steps,
        "summary": summary,
        "next_action": (summary.get("next_step") or {}).get("command"),
    }


def dashboard_guided_tour_payload(
    workspace_root: Path,
    reefiki_root: Path,
    projects: list[dict[str, Any]],
) -> dict[str, object]:
    dashboard_demo_ready = _dashboard_demo_ready(workspace_root)
    missing = next(
        (
            project
            for project in projects
            if (project.get("reefiki_mapping") or {}).get("mapping_status") in {"missing", "ambiguous"}
        ),
        None,
    )
    connected_count = sum(
        1
        for project in projects
        if (project.get("reefiki_mapping") or {}).get("mapping_status") == "connected"
    )
    if missing and missing.get("path"):
        connect_path = Path(str(missing["path"]))
    else:
        connect_path = None
    payload = guided_tour_payload(
        reefiki_root,
        fixture_root=workspace_root if dashboard_demo_ready else None,
        workspace_root=workspace_root,
        connect_path=connect_path,
        dashboard_open=True,
    )
    steps = list(payload["steps"])
    if dashboard_demo_ready:
        steps[1] = _step(
            "fixture",
            "done",
            "Create demo fixture",
            "Synthetic Ops Dashboard demo workspace is present.",
            f"reefiki ops-dashboard demo --fixture-root {_display_path(workspace_root)}",
            "dashboard demo marker present",
            blocks_mutation=False,
        )
    if projects:
        steps[2] = _step(
            "status",
            "done",
            "Inspect project status",
            "Dashboard snapshot loaded workspace project state.",
            f"reefiki ops-dashboard --workspace-root {_display_path(workspace_root)} --format json",
            f"projects={len(projects)}",
        )
    steps[3] = _step(
        "dashboard",
        "done",
        "Open Ops Dashboard",
        "The browser is already reading /api/snapshot from the local board.",
        f"reefiki ops-dashboard serve --workspace-root {_display_path(workspace_root)} --port 7310",
        "dashboard open",
    )
    if projects and connected_count == len(projects):
        steps[-1] = _step(
            "connect",
            "done",
            "Connect a real project",
            "All discovered projects are connected to REEFIKI.",
            "reefiki /connect <path>",
            "all dashboard projects connected",
        )
    elif not projects:
        steps[-1] = _step(
            "connect",
            "blocked",
            "Connect a real project",
            "No workspace projects were discovered.",
            "reefiki /connect <path>",
            "no projects discovered",
        )
    payload["steps"] = steps
    summary = _summary(steps)
    payload["summary"] = summary
    payload["next_action"] = (summary.get("next_step") or {}).get("command")
    return payload


def print_guided_tour(
    reefiki_root: Path,
    fmt: str,
    *,
    fixture_root: str | None = None,
    workspace_root: str | None = None,
    connect_path: str | None = None,
) -> int:
    payload = guided_tour_payload(
        reefiki_root,
        fixture_root=Path(fixture_root) if fixture_root else None,
        workspace_root=Path(workspace_root) if workspace_root else None,
        connect_path=Path(connect_path) if connect_path else None,
    )
    if fmt == "json":
        print(json.dumps(payload, ensure_ascii=False, indent=2))
        return 0
    summary = payload["summary"]
    print(f"guided tour: {summary['outcome']}")
    for step in payload["steps"]:
        print(f"- {step['status']}: {step['title']}")
        print(f"  command: {step['command']}")
        print(f"  evidence: {step['evidence']}")
    if payload.get("next_action"):
        print(f"next: {payload['next_action']}")
    return 0
