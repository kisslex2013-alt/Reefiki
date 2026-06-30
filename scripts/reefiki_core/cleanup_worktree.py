from __future__ import annotations

import json
from pathlib import Path

from .git_utils import (
    git_current_branch,
    git_head,
    git_is_ancestor,
    git_ref_exists,
    git_status_paths,
    require_git_success,
    run_git,
)


def _block(reason: str, **payload: object) -> dict[str, object]:
    return {"outcome": "block", "reason": reason, "error_code": reason, **payload}


def cleanup_worktree_payload(
    repo: Path,
    worktree: Path,
    base: str,
    dry_run: bool,
    semantic_superseded: str | None = None,
) -> tuple[int, dict[str, object]]:
    target = worktree.resolve()
    if not target.exists():
        return 1, _block("worktree_missing", worktree=str(target))
    status = git_status_paths(target)
    branch = git_current_branch(target)
    head = git_head(target, short=True)
    semantic_reason = (semantic_superseded or "").strip()
    payload: dict[str, object] = {
        "worktree": str(target),
        "branch": branch,
        "head": head,
        "base": base,
        "dry_run": dry_run,
    }
    if semantic_reason:
        payload["semantic_superseded"] = semantic_reason
    if status:
        return 1, _block("dirty_worktree", **payload, dirty_paths=status)
    if not git_ref_exists(target, base):
        return 1, _block("base_ref_missing", **payload)
    if target == repo.resolve():
        return 1, _block("refuse_current_worktree", **payload)
    merged_by_ancestry = git_is_ancestor(target, "HEAD", base)
    payload["head_reachable_from_base"] = merged_by_ancestry
    payload["branch_delete_allowed"] = bool(branch.startswith("codex/") and (merged_by_ancestry or semantic_reason))
    if not merged_by_ancestry and not semantic_reason:
        return 1, _block("unmerged_worktree_head", **payload)
    if semantic_reason and len(semantic_reason) < 20:
        return 1, _block("semantic_evidence_too_short", **payload)
    if branch not in {"", "HEAD", "main"} and not branch.startswith("codex/"):
        return 1, _block("non_task_branch", **payload)
    actions = ["remove_worktree"]
    if payload["branch_delete_allowed"]:
        actions.append("delete_local_branch")
    if semantic_reason and not merged_by_ancestry:
        actions.append("semantic_superseded_cleanup")
    if dry_run:
        return 0, {**payload, "outcome": "pass", "actions": actions}
    require_git_success(run_git(repo, ["worktree", "remove", "--force", str(target)]), "worktree removal failed")
    if branch not in {"", "HEAD", "main"}:
        # `git branch -d` checks merge against the launcher checkout HEAD, not
        # the caller-supplied base. We already proved safety against `base`, so
        # use `-D` and fail closed if branch cleanup does not happen.
        require_git_success(run_git(repo, ["branch", "-D", branch]), "local branch deletion failed")
    return 0, {**payload, "outcome": "pass", "removed": True}


def print_cleanup_worktree(
    repo: Path,
    worktree: str,
    base: str,
    dry_run: bool,
    fmt: str,
    semantic_superseded: str | None = None,
) -> int:
    code, payload = cleanup_worktree_payload(repo, Path(worktree), base, dry_run, semantic_superseded)
    if fmt == "json":
        print(json.dumps(payload, ensure_ascii=False, indent=2))
    else:
        print(f"outcome: {payload['outcome']}")
        if payload.get("reason"):
            print(f"reason: {payload['reason']}")
        print(f"worktree: {payload.get('worktree')}")
        print(f"branch: {payload.get('branch')}")
        if payload.get("semantic_superseded"):
            print(f"semantic_superseded: {payload.get('semantic_superseded')}")
    return code
