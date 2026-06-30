from __future__ import annotations

import json
from pathlib import Path

from .git_utils import (
    git_changed_paths,
    git_current_branch,
    git_head,
    git_is_ancestor,
    git_ref_exists,
    git_status_paths,
    require_git_success,
    run_git,
)
from .publish_classification import classify_publish_diff, private_project_inventory_payload
from .public_snapshot import inspect_public_snapshot, push_public_snapshot
from .repo_paths import repo_path_in_scope
from .secret_scan import secret_content_scan_payload


def _block(reason: str, **payload: object) -> dict[str, object]:
    return {"outcome": "block", "reason": reason, "error_code": reason, **payload}


def _cleanup_status(*, cleanup: bool, branch: str, base_is_ancestor: bool, repo: Path) -> dict[str, object]:
    if not cleanup:
        return {"requested": False}
    if not base_is_ancestor:
        return {
            "requested": True,
            "outcome": "blocked",
            "reason": "base_is_not_ancestor",
        }
    if not branch.startswith("codex/"):
        return {
            "requested": True,
            "outcome": "manual_required",
            "reason": "non_task_branch",
        }
    return {
        "requested": True,
        "outcome": "manual_required",
        "remote_task_branch": "planned",
        "local_task_worktree": "manual_required",
        "local_task_branch": "manual_required",
        "manual_command": f"python scripts\\reefiki.py cleanup-worktree --worktree {repo} --apply --format json",
    }


def publish_task_payload(
    repo: Path,
    base: str,
    private_remote: str,
    public_remote: str,
    dry_run: bool,
    cleanup: bool,
    public_snapshot: bool,
) -> tuple[int, dict[str, object]]:
    branch = git_current_branch(repo)
    status_paths = git_status_paths(repo)
    inventory = private_project_inventory_payload(repo)
    private_projects = list(inventory["private_projects"])
    public_projects = list(inventory.get("public_projects", []))
    if status_paths:
        return 1, _block(
            "dirty_worktree",
            branch=branch,
            dirty_paths=status_paths,
        )
    if inventory["outcome"] != "pass":
        reason = str(inventory["reason"])
        return 1, _block(
            reason,
            branch=branch,
            private_projects=private_projects,
            public_projects=public_projects,
            real_projects=inventory["real_projects"],
            missing_private_projects=inventory["missing_private_projects"],
        )
    if branch in {"", "HEAD"}:
        return 1, _block("detached_head", branch=branch)
    if not git_ref_exists(repo, base):
        return 1, _block("base_ref_missing", base=base, branch=branch)

    changed_paths = git_changed_paths(repo, base)
    secret_scan = secret_content_scan_payload(repo, changed_paths, "publish-task")
    if secret_scan["outcome"] != "pass":
        reason = str(secret_scan["reason"])
        return 1, _block(
            reason,
            branch=branch,
            private_projects=private_projects,
            public_projects=public_projects,
            real_projects=inventory["real_projects"],
            changed_paths=changed_paths,
            checked_paths=secret_scan["checked_paths"],
            blocking_paths=secret_scan["blocking_paths"],
        )
    diff_class = classify_publish_diff(changed_paths, private_projects)
    actions: list[str] = []
    post_merge_actions: list[str] = []
    requires_pr = False
    base_is_ancestor = git_is_ancestor(repo, base, "HEAD")

    cleanup_status = _cleanup_status(cleanup=cleanup, branch=branch, base_is_ancestor=base_is_ancestor, repo=repo)

    if diff_class != "empty":
        actions.append("push_task_branch")
        if base_is_ancestor:
            actions.append("push_private_main")
        else:
            actions.append("create_pr_required")
            requires_pr = True
        if diff_class in {"public-safe", "mixed"}:
            actions.append("push_public_snapshot")
        if cleanup and base_is_ancestor:
            post_merge_actions.append("cleanup_task_worktree")
            post_merge_actions.append("cleanup_task_branch")
    elif public_snapshot:
        actions.append("push_public_snapshot")

    snapshot_origin = "none"
    if "push_public_snapshot" in actions:
        snapshot_origin = "dry-run-inspect" if dry_run else "apply-push"
    public_snapshot_intent = "requested" if public_snapshot else ("diff-class:" + diff_class if diff_class in {"public-safe", "mixed"} else "none")

    payload: dict[str, object] = {
        "outcome": "pass" if not requires_pr else "block",
        "reason": "create_pr_required" if requires_pr else None,
        "error_code": "create_pr_required" if requires_pr else None,
        "dry_run": dry_run,
        "branch": branch,
        "head": git_head(repo, short=True),
        "base": base,
        "base_is_ancestor": base_is_ancestor,
        "private_remote": private_remote,
        "public_remote": public_remote,
        "private_projects": private_projects,
        "public_projects": public_projects,
        "real_projects": inventory["real_projects"],
        "public_snapshot_exclusions": [
            f"projects/{name}"
            for name in private_projects
            if any(repo_path_in_scope(path, f"projects/{name}") for path in changed_paths)
        ],
        "changed_paths": changed_paths,
        "diff_class": diff_class,
        "actions": actions,
        "post_merge_actions": post_merge_actions,
        "public_snapshot_requested": public_snapshot,
        "public_snapshot_intent": public_snapshot_intent,
        "snapshot_origin": snapshot_origin,
        "cleanup": cleanup_status,
    }
    if dry_run and "push_public_snapshot" in actions:
        snapshot_check = inspect_public_snapshot(repo, private_projects)
        if snapshot_check and snapshot_check.get("outcome") != "pass":
            payload.update(snapshot_check)
            return 1, payload
        payload["public_snapshot_check"] = snapshot_check
    if dry_run or requires_pr or (diff_class == "empty" and not public_snapshot):
        return (1 if requires_pr else 0), payload

    if diff_class != "empty":
        require_git_success(run_git(repo, ["push", private_remote, f"HEAD:{branch}"]), "task branch push failed")
        if base_is_ancestor:
            require_git_success(run_git(repo, ["push", private_remote, "HEAD:main"]), "private main push failed")
    if diff_class in {"public-safe", "mixed"} or public_snapshot:
        snapshot_block = push_public_snapshot(repo, public_remote, private_projects)
        if snapshot_block:
            payload.update(snapshot_block)
            return 1, payload
    if cleanup and (diff_class != "empty" or public_snapshot) and base_is_ancestor and branch.startswith("codex/"):
        delete_remote = run_git(repo, ["push", private_remote, "--delete", branch])
        cleanup_status["remote_task_branch"] = "deleted" if delete_remote.returncode == 0 else "manual_required"
        if delete_remote.returncode != 0:
            cleanup_status["remote_task_branch_error"] = delete_remote.stderr.strip() or delete_remote.stdout.strip() or "remote task branch delete failed"
    payload["applied"] = True
    return 0, payload


def print_publish_task(
    repo: Path,
    base: str,
    private_remote: str,
    public_remote: str,
    dry_run: bool,
    cleanup: bool,
    public_snapshot: bool,
    fmt: str,
) -> int:
    code, payload = publish_task_payload(repo, base, private_remote, public_remote, dry_run, cleanup, public_snapshot)
    if fmt == "json":
        print(json.dumps(payload, ensure_ascii=False, indent=2))
    else:
        print(f"outcome: {payload['outcome']}")
        if payload.get("reason"):
            print(f"reason: {payload['reason']}")
        print(f"branch: {payload.get('branch')}")
        print(f"diff_class: {payload.get('diff_class')}")
        print("actions:")
        for action in payload.get("actions", []):
            print(f"- {action}")
        cleanup_payload = payload.get("cleanup")
        if isinstance(cleanup_payload, dict):
            print("cleanup:")
            for key, value in cleanup_payload.items():
                print(f"- {key}: {value}")
        print("changed_paths:")
        for path in payload.get("changed_paths", []):
            print(f"- {path}")
    return code
