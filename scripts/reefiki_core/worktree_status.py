from __future__ import annotations

import json
from pathlib import Path
from typing import Any

from .git_utils import (
    git_head,
    git_is_ancestor,
    git_ref_exists,
    git_status_paths,
    require_git_success,
    run_git,
)
from .repo_paths import repo_path_in_scope


def parse_git_worktree_porcelain(output: str) -> list[dict[str, str]]:
    worktrees: list[dict[str, str]] = []
    current: dict[str, str] = {}
    for raw_line in output.splitlines():
        line = raw_line.strip()
        if not line:
            if current:
                worktrees.append(current)
                current = {}
            continue
        key, _, value = line.partition(" ")
        current[key] = value
    if current:
        worktrees.append(current)
    return worktrees


def git_ahead_behind(repo: Path, base: str, ref: str = "HEAD") -> tuple[int | None, int | None]:
    if not git_ref_exists(repo, base) or not git_ref_exists(repo, ref):
        return None, None
    completed = run_git(repo, ["rev-list", "--left-right", "--count", f"{base}...{ref}"])
    if completed.returncode != 0:
        return None, None
    parts = completed.stdout.strip().split()
    if len(parts) != 2:
        return None, None
    behind, ahead = (int(parts[0]), int(parts[1]))
    return ahead, behind


def dirty_path_scope(path: str) -> str:
    normalized = path.replace("\\", "/").strip("/")
    if not normalized:
        return "."
    parts = normalized.split("/")
    if parts[0] == "projects" and len(parts) >= 2:
        return "/".join(parts[:2])
    return parts[0]


def group_dirty_paths_by_scope(paths: list[str]) -> dict[str, list[str]]:
    grouped: dict[str, list[str]] = {}
    for path in sorted(paths):
        grouped.setdefault(dirty_path_scope(path), []).append(path)
    return dict(sorted(grouped.items()))


def normalize_scope(scope: str) -> str:
    return scope.replace("\\", "/").strip("/")


def path_matches_any_scope(path: str, scopes: list[str]) -> bool:
    return any(repo_path_in_scope(path, scope) for scope in scopes)


def worktree_status_recommendation(
    worktree_path: Path,
    branch: str,
    dirty_paths: list[str],
    base: str,
    ancestor_of_base: bool,
) -> tuple[str, str]:
    base_branch = base.removeprefix("refs/heads/")
    base_branch = base_branch.removeprefix("origin/")
    if dirty_paths:
        return "block", "dirty_worktree"
    if not git_ref_exists(worktree_path, base):
        return "block", "base_ref_missing"
    if branch in {base, base_branch, "main", "master"}:
        return "keep", "primary_or_base_worktree"
    if branch.startswith("codex/") and ancestor_of_base:
        return "delete", "clean_task_worktree_reachable_from_base"
    if branch.startswith("codex/"):
        return "review", "clean_task_worktree_not_reachable_from_base"
    return "keep", "non_task_worktree"


def worktree_scope_recommendation(
    recommendation: str,
    dirty_paths: list[str],
    scope_conflicts: list[str],
    excluded_dirty_paths: list[str],
    shared_checkout_dirty: bool,
    shared_checkout_behind: bool,
    has_scopes: bool,
) -> tuple[str, str]:
    if not has_scopes:
        return recommendation, "no_scope_filter"
    if scope_conflicts:
        return "blocked_by_dirty_target_scope", "dirty_paths_overlap_target_scope"
    if excluded_dirty_paths and shared_checkout_dirty:
        return "start_fresh_worktree", "shared_checkout_dirty_outside_target_scope"
    if shared_checkout_behind:
        return "start_fresh_worktree", "shared_checkout_behind_base"
    if dirty_paths:
        return "cleanup_review_needed", "dirty_paths_need_review"
    return recommendation, "no_scope_specific_blocker"


def worktree_status_payload(repo: Path, base: str, scopes: list[str] | None = None) -> dict[str, object]:
    listing = run_git(repo, ["worktree", "list", "--porcelain"])
    require_git_success(listing, "git worktree list failed")
    normalized_scopes = sorted({normalize_scope(scope) for scope in (scopes or []) if normalize_scope(scope)})
    base_branch = base.removeprefix("refs/heads/").removeprefix("origin/")
    worktrees: list[dict[str, object]] = []
    shared_checkout: dict[str, object] | None = None
    for item in parse_git_worktree_porcelain(listing.stdout):
        path = Path(item["worktree"]).resolve()
        raw_branch = item.get("branch", "HEAD")
        branch = raw_branch.removeprefix("refs/heads/")
        head = item.get("HEAD", "")
        short_head = head[:12] if head else git_head(path, short=True)
        dirty_paths: list[str] = []
        ancestor_of_base = False
        ahead: int | None = None
        behind: int | None = None
        if not path.exists():
            recommendation, reason = "block", "worktree_missing"
        else:
            dirty_paths = git_status_paths(path)
            ancestor_of_base = git_ref_exists(path, base) and git_is_ancestor(path, "HEAD", base)
            ahead, behind = git_ahead_behind(path, base, "HEAD")
            recommendation, reason = worktree_status_recommendation(
                path,
                branch,
                dirty_paths,
                base,
                ancestor_of_base,
            )
        dirty_paths_by_scope = group_dirty_paths_by_scope(dirty_paths)
        scope_conflicts = (
            sorted(path for path in dirty_paths if path_matches_any_scope(path, normalized_scopes))
            if normalized_scopes
            else []
        )
        excluded_dirty_paths = (
            sorted(path for path in dirty_paths if not path_matches_any_scope(path, normalized_scopes))
            if normalized_scopes
            else []
        )
        is_shared_checkout = branch in {base, base_branch, "main", "master"}
        shared_checkout_dirty = bool(dirty_paths) and is_shared_checkout
        shared_checkout_behind = behind is not None and behind > 0 and is_shared_checkout
        scope_recommendation, scope_reason = worktree_scope_recommendation(
            recommendation,
            dirty_paths,
            scope_conflicts,
            excluded_dirty_paths,
            shared_checkout_dirty,
            shared_checkout_behind,
            bool(normalized_scopes),
        )
        if is_shared_checkout and shared_checkout is None:
            shared_checkout = {
                "path": str(path),
                "branch": branch,
                "head": short_head,
                "dirty": bool(dirty_paths),
                "behind": shared_checkout_behind,
                "dirty_paths": dirty_paths,
                "dirty_paths_by_scope": dirty_paths_by_scope,
                "excluded_dirty_paths": excluded_dirty_paths,
                "scope_conflicts": scope_conflicts,
                "recommendation": scope_recommendation,
                "reason": scope_reason,
            }
        worktrees.append(
            {
                "path": str(path),
                "branch": branch,
                "head": short_head,
                "dirty_paths": dirty_paths,
                "dirty_paths_by_scope": dirty_paths_by_scope,
                "ahead": ahead,
                "behind": behind,
                "ancestor_of_base": ancestor_of_base,
                "shared_checkout_dirty": shared_checkout_dirty,
                "shared_checkout_behind": shared_checkout_behind,
                "excluded_dirty_paths": excluded_dirty_paths,
                "scope_conflicts": scope_conflicts,
                "recommendation": recommendation,
                "scope_recommendation": scope_recommendation,
                "reason": reason,
                "scope_reason": scope_reason,
            }
        )
    return {
        "repo": str(repo.resolve()),
        "base": base,
        "scopes": normalized_scopes,
        "shared_checkout_dirty": bool(shared_checkout and shared_checkout["dirty"]),
        "shared_checkout_behind": bool(shared_checkout and shared_checkout["behind"]),
        "excluded_dirty_paths": list(shared_checkout["excluded_dirty_paths"]) if shared_checkout else [],
        "scope_conflicts": list(shared_checkout["scope_conflicts"]) if shared_checkout else [],
        "recommendation": str(shared_checkout["recommendation"]) if shared_checkout else "keep",
        "shared_checkout": shared_checkout,
        "worktrees": worktrees,
    }


def worktree_status_payload_with_ledger(
    repo: Path,
    base: str,
    scopes: list[str] | None = None,
    ledger_path: Path | None = None,
    max_lease_days: int = 14,
) -> dict[str, Any]:
    from .orchestration_check import annotate_worktrees_with_ledger, default_ledger_path, load_worktree_ledger

    payload = worktree_status_payload(repo, base, scopes=scopes)
    resolved_ledger_path = ledger_path or default_ledger_path(repo)
    ledger = load_worktree_ledger(resolved_ledger_path)
    payload["ledger"] = {
        "path": ledger["path"],
        "exists": ledger["exists"],
        "schema_version": ledger["schema_version"],
        "errors": ledger["errors"],
    }
    return annotate_worktrees_with_ledger(payload, ledger, max_lease_days=max_lease_days)


def print_worktree_status(
    repo: Path,
    base: str,
    fmt: str,
    scopes: list[str] | None = None,
    ledger_path: Path | None = None,
    max_lease_days: int = 14,
) -> int:
    payload = (
        worktree_status_payload_with_ledger(
            repo,
            base,
            scopes=scopes,
            ledger_path=ledger_path,
            max_lease_days=max_lease_days,
        )
        if ledger_path is not None
        else worktree_status_payload(repo, base, scopes=scopes)
    )
    if fmt == "json":
        print(json.dumps(payload, ensure_ascii=False, indent=2))
    else:
        print(f"repo: {payload['repo']}")
        print(f"base: {payload['base']}")
        if payload["scopes"]:
            print(f"scopes: {', '.join(payload['scopes'])}")
            print(
                f"shared_checkout_dirty={payload['shared_checkout_dirty']} "
                f"shared_checkout_behind={payload['shared_checkout_behind']} "
                f"recommendation={payload['recommendation']}"
            )
            if payload["excluded_dirty_paths"]:
                print("excluded_dirty_paths:")
                for path in payload["excluded_dirty_paths"]:
                    print(f"  - {path}")
            if payload["scope_conflicts"]:
                print("scope_conflicts:")
                for path in payload["scope_conflicts"]:
                    print(f"  - {path}")
        if payload.get("ledger"):
            ledger = payload["ledger"]
            print(f"ledger: {ledger['path']} exists={ledger['exists']}")
            if ledger["errors"]:
                print(f"ledger_errors: {', '.join(ledger['errors'])}")
        for item in payload["worktrees"]:
            dirty_count = len(item["dirty_paths"])
            ahead = item["ahead"] if item["ahead"] is not None else "?"
            behind = item["behind"] if item["behind"] is not None else "?"
            print(
                f"- {item['recommendation']}: {item['branch']} {item['head']} "
                f"ahead={ahead} behind={behind} dirty={dirty_count} "
                f"reason={item['reason']} path={item['path']}"
            )
            if "ledger" in item:
                ledger = item["ledger"]
                issues = ", ".join(ledger["issues"])
                print(
                    f"  ledger_present={ledger['present']} owner={ledger['owner']} "
                    f"milestone={ledger['milestone']} issues={issues}"
                )
            if payload["scopes"] and item["scope_recommendation"] != item["recommendation"]:
                print(f"  scope_recommendation={item['scope_recommendation']} reason={item['scope_reason']}")
    return 0
