"""Synthetic fixture for the Ops Dashboard first-run demo.

The fixture is local-only and writes only under the explicit fixture root.
It creates small git repositories so the existing read-only dashboard can
render realistic clean and active work states without touching user projects.
"""

from __future__ import annotations

import json
import os
import subprocess
from pathlib import Path
from typing import Any


DEFAULT_DEMO_PORT = 7310


def _rel(path: Path, root: Path) -> str:
    return path.relative_to(root).as_posix()


def _write(path: Path, content: str) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(content, encoding="utf-8", newline="\n")


def _git(repo: Path, *args: str, check: bool = True) -> subprocess.CompletedProcess[str]:
    env = os.environ.copy()
    env["GIT_OPTIONAL_LOCKS"] = "0"
    return subprocess.run(
        ["git", *args],
        cwd=repo,
        check=check,
        capture_output=True,
        text=True,
        encoding="utf-8",
        errors="replace",
        env=env,
    )


def _ensure_repo(repo: Path, initial_branch: str = "main") -> None:
    repo.mkdir(parents=True, exist_ok=True)
    if not (repo / ".git").exists():
        _git(repo, "init", "-b", initial_branch)


def _commit_all(repo: Path, message: str) -> None:
    _git(repo, "add", "AGENTS.md", "README.md", ".reefiki")
    result = _git(
        repo,
        "-c",
        "user.name=REEFIKI Demo",
        "-c",
        "user.email=demo@reefiki.local",
        "commit",
        "-m",
        message,
        check=False,
    )
    if result.returncode != 0 and "nothing to commit" not in (result.stdout + result.stderr).lower():
        raise SystemExit(result.stderr.strip() or result.stdout.strip() or "git commit failed")


def create_ops_dashboard_demo(fixture_root: Path) -> dict[str, Any]:
    root = fixture_root.expanduser().resolve()
    root.mkdir(parents=True, exist_ok=True)
    _write(root / ".reefiki-dashboard-demo", "synthetic workspace for REEFIKI first-run dashboard demo\n")

    demo_app = root / "DemoApp"
    agent_task = root / "AgentTask"

    _ensure_repo(demo_app)
    _write(demo_app / "AGENTS.md", "Use REEFIKI demo rules. Keep this fixture local and read-only.\n")
    _write(
        demo_app / "README.md",
        "# DemoApp\n\nA clean connected project for the REEFIKI first-run dashboard.\n",
    )
    _write(demo_app / ".reefiki", "project_name: reefiki-onboarding-demo\n")
    _commit_all(demo_app, "chore: initialize dashboard demo app")

    _ensure_repo(agent_task)
    _write(agent_task / "AGENTS.md", "Use REEFIKI demo rules. This repo simulates active agent work.\n")
    _write(agent_task / "README.md", "# AgentTask\n\nA small active worktree used by the dashboard demo.\n")
    _write(agent_task / ".reefiki", "project_name: reefiki-onboarding-demo\n")
    _commit_all(agent_task, "chore: initialize agent task demo")
    _git(agent_task, "checkout", "-B", "codex/first-run-demo")
    _write(
        agent_task / "notes" / "first-run.md",
        "# First-run demo note\n\nThis uncommitted note makes the dashboard show an active safe-next-action lane.\n",
    )

    artifacts = sorted(
        [
            _rel(demo_app / "AGENTS.md", root),
            _rel(demo_app / "README.md", root),
            _rel(demo_app / ".reefiki", root),
            _rel(agent_task / "AGENTS.md", root),
            _rel(agent_task / "README.md", root),
            _rel(agent_task / ".reefiki", root),
            _rel(agent_task / "notes" / "first-run.md", root),
            ".reefiki-dashboard-demo",
        ]
    )
    return {
        "mode": "fixture",
        "workspace_root": str(root),
        "artifacts": artifacts,
        "snapshot_command": f"reefiki ops-dashboard --workspace-root {root} --format json",
        "serve_command": f"reefiki ops-dashboard serve --workspace-root {root} --port {DEFAULT_DEMO_PORT}",
        "url": f"http://127.0.0.1:{DEFAULT_DEMO_PORT}/",
        "next_action": f"run: reefiki ops-dashboard serve --workspace-root {root} --port {DEFAULT_DEMO_PORT}",
    }


def print_ops_dashboard_demo(fixture_root: str, fmt: str) -> int:
    payload = create_ops_dashboard_demo(Path(fixture_root))
    if fmt == "json":
        print(json.dumps(payload, ensure_ascii=False, indent=2))
    else:
        print("# REEFIKI Ops Dashboard demo")
        print(f"- workspace: {payload['workspace_root']}")
        print(f"- snapshot: {payload['snapshot_command']}")
        print(f"- serve: {payload['serve_command']}")
        print(f"- open: {payload['url']}")
        print("")
        print("## Artifacts")
        for artifact in payload["artifacts"]:
            print(f"- {artifact}")
        print("")
        print(f"next: {payload['next_action']}")
    return 0
