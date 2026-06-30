#!/usr/bin/env python3
from __future__ import annotations

import json
import os
import re
import subprocess
import sys
from pathlib import Path
from typing import Any


BROAD_STAGE_PATTERNS = [
    re.compile(r"\bgit\s+add\s+(-A|--all)(\s|$)", re.IGNORECASE),
    re.compile(r"\bgit\s+add\s+(--\s+)?\.{1,2}([\\/]+)?(\s|$)", re.IGNORECASE),
]
COMMIT_OR_PUBLISH_PATTERNS = [
    re.compile(r"\bgit\s+commit\b", re.IGNORECASE),
    re.compile(r"\bgit\s+push\b", re.IGNORECASE),
    re.compile(r"\bpublish-task\b.*\s--apply\b", re.IGNORECASE),
]


def read_payload() -> dict[str, Any]:
    raw = sys.stdin.read().strip()
    if not raw:
        return {}
    try:
        data = json.loads(raw)
    except json.JSONDecodeError:
        return {}
    return data if isinstance(data, dict) else {}


def tool_input(payload: dict[str, Any]) -> dict[str, Any]:
    value = payload.get("tool_input") or payload.get("input") or payload.get("arguments") or {}
    return value if isinstance(value, dict) else {}


def command_from_payload(payload: dict[str, Any]) -> str:
    data = tool_input(payload)
    command = data.get("command") or data.get("cmd")
    return command if isinstance(command, str) else ""


def run_git(args: list[str], cwd: Path) -> tuple[int, str]:
    proc = subprocess.run(
        ["git", *args],
        cwd=str(cwd),
        capture_output=True,
        text=True,
        check=False,
    )
    return proc.returncode, proc.stdout.strip()


def repo_root(cwd: Path) -> Path | None:
    code, out = run_git(["rev-parse", "--show-toplevel"], cwd)
    if code != 0 or not out:
        return None
    return Path(out).resolve()


def staged_paths(root: Path) -> list[str]:
    code, out = run_git(["diff", "--cached", "--name-only"], root)
    if code != 0 or not out:
        return []
    return [line.strip().replace("\\", "/") for line in out.splitlines() if line.strip()]


def project_name(path: str) -> str | None:
    parts = path.split("/")
    if len(parts) >= 2 and parts[0] == "projects":
        return parts[1]
    return None


def validate_staged(paths: list[str]) -> list[str]:
    project_paths = [path for path in paths if project_name(path)]
    if not project_paths:
        return []

    projects = {project_name(path) for path in project_paths}
    if len(projects) != 1:
        return project_paths

    project = next(iter(projects))
    assert project is not None
    wiki_prefix = f"projects/{project}/wiki/"

    has_wiki_paths = any(path.startswith(wiki_prefix) for path in project_paths)
    if not has_wiki_paths:
        return []

    blocking: list[str] = []
    for path in paths:
        if not path.startswith(wiki_prefix):
            blocking.append(path)
    return sorted(blocking)


def output_context(payload: dict[str, Any], message: str, block: bool) -> None:
    event = payload.get("hook_event_name") or "PreToolUse"
    response: dict[str, Any] = {
        "hookSpecificOutput": {
            "hookEventName": event,
            "additionalContext": message,
        }
    }
    if block:
        response["decision"] = "block"
        response["reason"] = message
    print(json.dumps(response, ensure_ascii=False))


def main() -> int:
    payload = read_payload()
    command = command_from_payload(payload)
    if not command:
        print("{}")
        return 0

    broad_stage = any(pattern.search(command) for pattern in BROAD_STAGE_PATTERNS)
    commit_or_publish = any(pattern.search(command) for pattern in COMMIT_OR_PUBLISH_PATTERNS)
    if not broad_stage and not commit_or_publish:
        print("{}")
        return 0

    cwd = Path(os.getcwd())
    root = repo_root(cwd)
    if root is None:
        print("{}")
        return 0

    if broad_stage:
        output_context(
            payload,
            "REEFIKI staged-path guard blocks broad staging. Stage explicit paths only; do not use git add -A or git add . in this repo.",
            block=True,
        )
        return 2

    if re.search(r"\bgit\s+push\b", command, re.IGNORECASE):
        output_context(
            payload,
            "REEFIKI staged-path guard blocks manual git push. Use python scripts/reefiki.py publish-task --dry-run first, then --apply only if it passes.",
            block=True,
        )
        return 2

    paths = staged_paths(root)
    blocking = validate_staged(paths)
    if blocking:
        message = (
            "REEFIKI staged-path guard blocks this commit/publish because staged paths mix project wiki scope "
            "with out-of-scope paths: " + ", ".join(blocking)
        )
        output_context(payload, message, block=True)
        return 2

    if paths:
        message = "REEFIKI staged-path guard passed for staged paths: " + ", ".join(paths)
    else:
        message = "REEFIKI staged-path guard found no staged paths; ensure this command intentionally has nothing to commit."
    output_context(payload, message, block=False)
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
