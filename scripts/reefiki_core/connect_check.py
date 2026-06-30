from __future__ import annotations

import json
from pathlib import Path

from .git_utils import run_git
from .markdown import as_text


def _display_path(path: Path) -> str:
    return str(path.resolve()).replace("\\", "/")


def _bridge_exists(project: Path, path: str) -> bool:
    target = project / path.rstrip("/")
    return target.exists() or target.is_symlink()


def _git_toplevel(project: Path) -> tuple[bool, str | None, str]:
    completed = run_git(project, ["rev-parse", "--show-toplevel"])
    if completed.returncode == 0:
        return True, completed.stdout.strip().replace("\\", "/"), ""
    detail = completed.stderr.strip() or completed.stdout.strip()
    return False, None, detail


def _is_ignored(project: Path, candidates: list[str]) -> tuple[bool, list[str]]:
    warnings: list[str] = []
    for candidate in candidates:
        completed = run_git(project, ["check-ignore", "--no-index", "--quiet", "--", candidate])
        if completed.stderr.strip():
            warnings.append(completed.stderr.strip())
        if completed.returncode == 0:
            return True, warnings
        if completed.returncode == 1:
            continue
        warnings.append(completed.stderr.strip() or completed.stdout.strip() or f"git check-ignore failed for {candidate}")
    return False, warnings


def _tracked_bridge_paths(project: Path) -> tuple[list[str], list[str]]:
    completed = run_git(project, ["ls-files", "--", ".reefiki", "_wiki"])
    warnings: list[str] = []
    if completed.stderr.strip():
        warnings.append(completed.stderr.strip())
    if completed.returncode != 0:
        warnings.append(completed.stderr.strip() or completed.stdout.strip() or "git ls-files failed")
        return [], warnings
    paths = [line.strip().replace("\\", "/") for line in completed.stdout.splitlines() if line.strip()]
    return sorted(set(paths)), warnings


def connect_check_payload(project_path: Path) -> dict[str, object]:
    project = project_path.expanduser().resolve()
    checks: list[dict[str, object]] = []
    warnings: list[str] = []
    next_actions: list[str] = []

    if not project.exists():
        return {
            "schema_version": 1,
            "read_only": True,
            "status": "block",
            "path": _display_path(project),
            "git": {"status": "not_checked", "repo_root": None},
            "checks": [
                {
                    "id": "path.exists",
                    "status": "block",
                    "summary": "Target path does not exist.",
                }
            ],
            "tracked_bridge_paths": [],
            "warnings": [],
            "next_actions": ["Pass an existing code project path."],
        }

    if not project.is_dir():
        return {
            "schema_version": 1,
            "read_only": True,
            "status": "block",
            "path": _display_path(project),
            "git": {"status": "not_checked", "repo_root": None},
            "checks": [
                {
                    "id": "path.directory",
                    "status": "block",
                    "summary": "Target path is not a directory.",
                }
            ],
            "tracked_bridge_paths": [],
            "warnings": [],
            "next_actions": ["Pass a code project directory."],
        }

    wiki_exists = _bridge_exists(project, "_wiki/")
    marker_exists = _bridge_exists(project, ".reefiki")
    checks.append(
        {
            "id": "bridge._wiki.exists",
            "status": "pass" if wiki_exists else "warn",
            "summary": "_wiki bridge exists." if wiki_exists else "_wiki bridge is missing.",
        }
    )
    checks.append(
        {
            "id": "bridge.marker.exists",
            "status": "pass" if marker_exists else "warn",
            "summary": ".reefiki marker exists." if marker_exists else ".reefiki marker is missing.",
        }
    )
    if not wiki_exists:
        next_actions.append("Run /connect or create the _wiki junction before relying on project-local REEFIKI lookup.")
    if not marker_exists:
        next_actions.append("Run /connect or create the .reefiki marker so agents can detect the linked REEFIKI project.")

    is_repo, repo_root, _git_detail = _git_toplevel(project)
    if not is_repo:
        checks.append(
            {
                "id": "git.repo",
                "status": "skip",
                "summary": "Target is not a git repo; git ignore verification is not applicable.",
            }
        )
        if not next_actions:
            next_actions.append("For non-git projects, use _wiki, .reefiki, detect, status and doctor as connection evidence.")
        return {
            "schema_version": 1,
            "read_only": True,
            "status": "warn" if any(check["status"] == "warn" for check in checks) else "pass",
            "path": _display_path(project),
            "git": {"status": "not_git_repo", "repo_root": None},
            "checks": checks,
            "ignored": {},
            "tracked_bridge_paths": [],
            "warnings": warnings,
            "next_actions": next_actions,
        }

    wiki_ignored, wiki_warnings = _is_ignored(project, ["_wiki/", "_wiki"])
    marker_ignored, marker_warnings = _is_ignored(project, [".reefiki"])
    warnings.extend(wiki_warnings)
    warnings.extend(marker_warnings)
    tracked_paths, tracked_warnings = _tracked_bridge_paths(project)
    warnings.extend(tracked_warnings)

    checks.append(
        {
            "id": "git.ignore._wiki",
            "status": "pass" if wiki_ignored else "warn",
            "summary": "_wiki/ is ignored by git." if wiki_ignored else "_wiki/ is not ignored by git.",
        }
    )
    checks.append(
        {
            "id": "git.ignore.marker",
            "status": "pass" if marker_ignored else "warn",
            "summary": ".reefiki is ignored by git." if marker_ignored else ".reefiki is not ignored by git.",
        }
    )
    checks.append(
        {
            "id": "git.tracked_bridge_paths",
            "status": "block" if tracked_paths else "pass",
            "summary": "Bridge paths are tracked by git." if tracked_paths else "No tracked bridge paths found.",
            "paths": tracked_paths,
        }
    )

    if not wiki_ignored:
        next_actions.append("Add _wiki/ to the target project's .gitignore.")
    if not marker_ignored:
        next_actions.append("Add .reefiki to the target project's .gitignore.")
    if tracked_paths:
        next_actions.append("Remove bridge paths from the target git index after review, without deleting local files.")
    if not next_actions:
        next_actions.append("No action needed; bridge paths are ignored and not tracked.")

    if tracked_paths:
        status = "block"
    elif any(check["status"] == "warn" for check in checks):
        status = "warn"
    else:
        status = "pass"

    return {
        "schema_version": 1,
        "read_only": True,
        "status": status,
        "path": _display_path(project),
        "git": {"status": "git_repo", "repo_root": repo_root},
        "checks": checks,
        "ignored": {"_wiki/": wiki_ignored, ".reefiki": marker_ignored},
        "tracked_bridge_paths": tracked_paths,
        "warnings": sorted(set(as_text(warning) for warning in warnings if as_text(warning))),
        "next_actions": next_actions,
    }


def _print_text(payload: dict[str, object]) -> None:
    print(f"connect check: {payload['status']}")
    print(f"- path: {payload['path']}")
    git = payload["git"]
    print(f"- git: {git['status']}")
    if git.get("repo_root"):
        print(f"- git root: {git['repo_root']}")
    for check in payload["checks"]:
        print(f"- {check['status']}: {check['summary']}")
        paths = check.get("paths")
        if paths:
            for path in paths:
                print(f"  - {path}")
    for action in payload["next_actions"]:
        print(f"- next: {action}")


def print_connect_check(project_path: str, fmt: str) -> int:
    payload = connect_check_payload(Path(project_path))
    if fmt == "json":
        print(json.dumps(payload, ensure_ascii=False, indent=2))
    else:
        _print_text(payload)
    return 1 if payload["status"] == "block" else 0
