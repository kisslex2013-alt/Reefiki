from __future__ import annotations

import json
from datetime import date, datetime
from pathlib import Path
from typing import Any

from .git_utils import git_status_paths, require_git_success, run_git
from .repo_paths import repo_path_in_scope
from .worktree_status import worktree_status_payload


LEDGER_SCHEMA_VERSION = "reefiki.worktree-ledger.v1"
DEFAULT_LEDGER_PATH = Path("plans/leadops/worktree-ledger.json")
DEFAULT_COORDINATION_FILES = [
    "ROADMAP.md",
    "TASKS.md",
    "AGENTS.md",
    "projects/*/wiki/log.md",
    "projects/*/wiki/index.md",
    "plans/leadops/worktree-ledger.json",
]

GLOBAL_CONFIG_SCAN_PATHS = [
    Path.home() / ".codex" / "AGENTS.md",
    Path.home() / ".codex" / "rules" / "default.rules",
]

FORBIDDEN_GLOBAL_CONFIG_PATTERNS = [
    "git add -A",
    "git reset --hard",
    "git checkout --",
    "git clean -fd",
    "git worktree remove --force",
    "Remove-Item -Recurse -Force",
    "Stop-Process -Force",
    ".env",
    "TELEGRAM_API",
    "API_TOKEN",
    "API_KEY",
]


def _today() -> date:
    return date.today()


def normalize_repo_path(path: str) -> str:
    return path.replace("\\", "/").strip("/")


def default_ledger_path(repo: Path) -> Path:
    return repo / DEFAULT_LEDGER_PATH


def load_worktree_ledger(path: Path) -> dict[str, Any]:
    if not path.exists():
        return {
            "schema_version": LEDGER_SCHEMA_VERSION,
            "path": str(path),
            "exists": False,
            "entries": [],
            "errors": [],
        }
    try:
        data = json.loads(path.read_text(encoding="utf-8"))
    except json.JSONDecodeError as exc:
        return {
            "schema_version": LEDGER_SCHEMA_VERSION,
            "path": str(path),
            "exists": True,
            "entries": [],
            "errors": [f"invalid_json:{exc.lineno}:{exc.colno}"],
        }
    if not isinstance(data, dict):
        return {
            "schema_version": LEDGER_SCHEMA_VERSION,
            "path": str(path),
            "exists": True,
            "entries": [],
            "errors": ["ledger_root_must_be_object"],
        }
    entries = data.get("entries", [])
    if not isinstance(entries, list):
        entries = []
        errors = ["entries_must_be_list"]
    else:
        errors = []
    return {
        "schema_version": data.get("schema_version", LEDGER_SCHEMA_VERSION),
        "path": str(path),
        "exists": True,
        "entries": [entry for entry in entries if isinstance(entry, dict)],
        "errors": errors,
    }


def ledger_entries_by_branch(entries: list[dict[str, Any]]) -> dict[str, dict[str, Any]]:
    result: dict[str, dict[str, Any]] = {}
    for entry in entries:
        branch = str(entry.get("branch", "")).strip()
        if branch:
            result[branch] = entry
    return result


def parse_iso_date(value: object) -> date | None:
    if not isinstance(value, str) or not value.strip():
        return None
    try:
        return datetime.fromisoformat(value.strip().replace("Z", "+00:00")).date()
    except ValueError:
        try:
            return date.fromisoformat(value.strip())
        except ValueError:
            return None


def ledger_entry_issues(entry: dict[str, Any], max_lease_days: int, today: date | None = None) -> list[str]:
    now = today or _today()
    issues: list[str] = []
    if not str(entry.get("owner", "")).strip():
        issues.append("missing_owner")
    if not str(entry.get("scope", "")).strip():
        issues.append("missing_scope")
    if not str(entry.get("milestone", "")).strip():
        issues.append("missing_milestone")
    created = parse_iso_date(entry.get("created_at"))
    if created is None:
        issues.append("missing_or_invalid_created_at")
    else:
        age_days = (now - created).days
        if age_days > max_lease_days:
            issues.append("lease_expired")
    coordination_files = entry.get("coordination_files", [])
    if coordination_files is not None and not isinstance(coordination_files, list):
        issues.append("coordination_files_must_be_list")
    return issues


def coordination_conflicts(entries: list[dict[str, Any]]) -> list[dict[str, Any]]:
    active_statuses = {"ready", "assigned", "active", "review", "blocked"}
    by_file: dict[str, list[dict[str, Any]]] = {}
    for entry in entries:
        status = str(entry.get("status", "active")).strip() or "active"
        if status not in active_statuses:
            continue
        owner = str(entry.get("owner", "")).strip()
        integration_owner = str(entry.get("integration_owner", "")).strip()
        for raw_path in entry.get("coordination_files", []) or []:
            path = normalize_repo_path(str(raw_path))
            if path:
                by_file.setdefault(path, []).append(
                    {
                        "branch": entry.get("branch", ""),
                        "owner": owner,
                        "integration_owner": integration_owner,
                        "status": status,
                    }
                )
    conflicts: list[dict[str, Any]] = []
    for path, holders in sorted(by_file.items()):
        if len(holders) < 2:
            continue
        integration_owners = {str(item["integration_owner"]) for item in holders if item["integration_owner"]}
        if len(integration_owners) == 1:
            continue
        conflicts.append({"path": path, "holders": holders, "reason": "coordination_file_without_single_owner"})
    return conflicts


def annotate_worktrees_with_ledger(
    status_payload: dict[str, Any],
    ledger: dict[str, Any],
    max_lease_days: int,
    today: date | None = None,
) -> dict[str, Any]:
    entries = ledger_entries_by_branch(list(ledger.get("entries", [])))
    for item in status_payload.get("worktrees", []):
        if not isinstance(item, dict):
            continue
        branch = str(item.get("branch", ""))
        entry = entries.get(branch)
        item["ledger"] = {
            "present": entry is not None,
            "owner": entry.get("owner") if entry else None,
            "milestone": entry.get("milestone") if entry else None,
            "status": entry.get("status") if entry else None,
            "scope": entry.get("scope") if entry else None,
            "issues": ledger_entry_issues(entry, max_lease_days, today=today) if entry else ["missing_ledger_entry"],
        }
    return status_payload


def remote_task_branches_payload(repo: Path, base: str, remote: str) -> dict[str, Any]:
    output = require_git_success(
        run_git(repo, ["branch", "-r", "--list", f"{remote}/codex/*", "--format=%(refname:short)"]),
        "remote task branch lookup failed",
    )
    branches = sorted(line.strip() for line in output.splitlines() if line.strip())
    items: list[dict[str, Any]] = []
    for branch in branches:
        merged = run_git(repo, ["merge-base", "--is-ancestor", branch, base]).returncode == 0
        items.append(
            {
                "branch": branch,
                "merged_to_base": merged,
                "recommendation": "delete_remote_branch" if merged else "keep_or_review",
                "reason": "reachable_from_base" if merged else "not_reachable_from_base",
            }
        )
    return {
        "remote": remote,
        "base": base,
        "branches": items,
        "delete_candidates": [item["branch"] for item in items if item["recommendation"] == "delete_remote_branch"],
    }


def global_config_scan_payload(paths: list[Path] | None = None) -> dict[str, Any]:
    scan_paths = paths or GLOBAL_CONFIG_SCAN_PATHS
    findings: list[dict[str, Any]] = []
    checked: list[str] = []
    missing: list[str] = []
    for path in scan_paths:
        if not path.exists():
            missing.append(str(path))
            continue
        checked.append(str(path))
        text = path.read_text(encoding="utf-8", errors="replace")
        for pattern in FORBIDDEN_GLOBAL_CONFIG_PATTERNS:
            if pattern.lower() in text.lower():
                findings.append(
                    {
                        "path": str(path),
                        "pattern": pattern,
                        "reason": "unsafe_or_secret_like_global_rule",
                    }
                )
    return {
        "outcome": "block" if findings else "pass",
        "checked_paths": checked,
        "missing_paths": missing,
        "findings": findings,
    }


def ci_policy_payload(repo: Path) -> dict[str, Any]:
    workflow_dir = repo / ".github" / "workflows"
    workflow_files = sorted(str(path.relative_to(repo)).replace("\\", "/") for path in workflow_dir.glob("*.yml"))
    return {
        "workflow_files": workflow_files,
        "local_ci_present": bool(workflow_files),
        "branch_protection": {
            "outcome": "manual_check_required",
            "reason": "GitHub branch protection cannot be proven from local git state",
            "expected": [
                "protect main",
                "require pull request or guarded publish flow",
                "require CI/status checks before merge",
                "restrict direct public remote pushes",
            ],
        },
    }


def scoped_ledger_entries(entries: list[dict[str, Any]], scopes: list[str]) -> list[dict[str, Any]]:
    normalized_scopes = [normalize_repo_path(scope) for scope in scopes if normalize_repo_path(scope)]
    if not normalized_scopes:
        return entries
    filtered: list[dict[str, Any]] = []
    for entry in entries:
        entry_scope = normalize_repo_path(str(entry.get("scope", "")))
        coordination_files = [normalize_repo_path(str(path)) for path in entry.get("coordination_files", []) or []]
        if any(repo_path_in_scope(entry_scope, scope) or repo_path_in_scope(scope, entry_scope) for scope in normalized_scopes):
            filtered.append(entry)
            continue
        if any(any(repo_path_in_scope(path, scope) for scope in normalized_scopes) for path in coordination_files):
            filtered.append(entry)
    return filtered


def orchestration_check_payload(
    repo: Path,
    base: str = "origin/main",
    ledger_path: Path | None = None,
    scopes: list[str] | None = None,
    max_lease_days: int = 14,
    remote: str = "origin",
    include_global_config: bool = False,
) -> dict[str, Any]:
    resolved_ledger_path = ledger_path or default_ledger_path(repo)
    ledger = load_worktree_ledger(resolved_ledger_path)
    scoped_entries = scoped_ledger_entries(list(ledger.get("entries", [])), scopes or [])
    scoped_ledger = {**ledger, "entries": scoped_entries}
    worktrees = annotate_worktrees_with_ledger(
        worktree_status_payload(repo, base, scopes=scopes),
        scoped_ledger,
        max_lease_days=max_lease_days,
    )
    entry_issues = [
        {
            "branch": entry.get("branch", ""),
            "issues": ledger_entry_issues(entry, max_lease_days),
        }
        for entry in scoped_entries
        if ledger_entry_issues(entry, max_lease_days)
    ]
    conflicts = coordination_conflicts(scoped_entries)
    remote_branches = remote_task_branches_payload(repo, base, remote)
    current_dirty_paths = git_status_paths(repo)
    global_scan = global_config_scan_payload() if include_global_config else {
        "outcome": "skipped",
        "reason": "use --include-global-config to scan global Codex rules",
        "checked_paths": [],
        "missing_paths": [],
        "findings": [],
    }
    blockers: list[str] = []
    if ledger.get("errors"):
        blockers.append("ledger_errors")
    if entry_issues:
        blockers.append("ledger_entry_issues")
    if conflicts:
        blockers.append("coordination_conflicts")
    if current_dirty_paths:
        blockers.append("current_worktree_dirty")
    if global_scan["outcome"] == "block":
        blockers.append("global_config_findings")
    return {
        "schema_version": "reefiki.orchestration-check.v1",
        "repo": str(repo.resolve()),
        "base": base,
        "scopes": [normalize_repo_path(scope) for scope in scopes or [] if normalize_repo_path(scope)],
        "outcome": "block" if blockers else "pass",
        "blockers": blockers,
        "ledger": scoped_ledger,
        "ledger_entry_issues": entry_issues,
        "coordination_conflicts": conflicts,
        "current_worktree_dirty_paths": current_dirty_paths,
        "worktree_status": worktrees,
        "remote_task_branches": remote_branches,
        "global_config_scan": global_scan,
        "ci_policy": ci_policy_payload(repo),
    }


def print_orchestration_check(
    repo: Path,
    base: str,
    ledger_path: Path | None,
    scopes: list[str],
    max_lease_days: int,
    remote: str,
    include_global_config: bool,
    fmt: str,
) -> int:
    payload = orchestration_check_payload(
        repo,
        base=base,
        ledger_path=ledger_path,
        scopes=scopes,
        max_lease_days=max_lease_days,
        remote=remote,
        include_global_config=include_global_config,
    )
    if fmt == "json":
        print(json.dumps(payload, ensure_ascii=False, indent=2))
    else:
        print(f"outcome: {payload['outcome']}")
        print(f"repo: {payload['repo']}")
        print(f"base: {payload['base']}")
        print(f"ledger: {payload['ledger']['path']} exists={payload['ledger']['exists']}")
        if payload["blockers"]:
            print("blockers:")
            for blocker in payload["blockers"]:
                print(f"  - {blocker}")
        print(f"worktrees: {len(payload['worktree_status']['worktrees'])}")
        print(f"remote_task_branch_delete_candidates: {len(payload['remote_task_branches']['delete_candidates'])}")
        if payload["coordination_conflicts"]:
            print("coordination_conflicts:")
            for conflict in payload["coordination_conflicts"]:
                print(f"  - {conflict['path']}: {conflict['reason']}")
        if payload["current_worktree_dirty_paths"]:
            print("current_worktree_dirty_paths:")
            for path in payload["current_worktree_dirty_paths"]:
                print(f"  - {path}")
        if payload["ledger_entry_issues"]:
            print("ledger_entry_issues:")
            for item in payload["ledger_entry_issues"]:
                print(f"  - {item['branch']}: {', '.join(item['issues'])}")
        if payload["global_config_scan"]["outcome"] == "block":
            print("global_config_findings:")
            for finding in payload["global_config_scan"]["findings"]:
                print(f"  - {finding['path']}: {finding['pattern']}")
        print(f"ci_local_present: {payload['ci_policy']['local_ci_present']}")
        print(f"branch_protection: {payload['ci_policy']['branch_protection']['outcome']}")
    return 1 if payload["outcome"] == "block" else 0
