from __future__ import annotations

import tempfile
from datetime import date, datetime
from fnmatch import fnmatchcase
from pathlib import Path

from .git_utils import require_git_success, run_git
from .publish_classification import private_project_inventory_payload
from .repo_paths import normalize_repo_path, repo_path_in_scope
from .secret_scan import secret_content_scan_payload


PUBLIC_SNAPSHOT_EXCLUDE_CONFIG = Path("scripts/public-snapshot.exclude.txt")
PUBLIC_SNAPSHOT_BRANCH_PREFIX = "public-snapshot-"
GIT_RM_CHUNK_SIZE = 100


def inspect_public_snapshot(repo: Path, private_projects: list[str]) -> dict[str, object] | None:
    return run_public_snapshot(repo, public_remote=None, private_projects=private_projects)


def push_public_snapshot(repo: Path, public_remote: str, private_projects: list[str]) -> dict[str, object] | None:
    return run_public_snapshot(repo, public_remote=public_remote, private_projects=private_projects)


def cleanup_local_public_snapshot_branches(repo: Path, keep_branch: str) -> list[str]:
    output = require_git_success(
        run_git(repo, ["for-each-ref", "--format=%(refname:short)", f"refs/heads/{PUBLIC_SNAPSHOT_BRANCH_PREFIX}*"]),
        "public snapshot branch inventory failed",
    )
    branches = sorted(line.strip() for line in output.splitlines() if line.strip())
    deleted: list[str] = []
    for branch in branches:
        if branch == keep_branch:
            continue
        completed = run_git(repo, ["branch", "-D", branch])
        if completed.returncode == 0:
            deleted.append(branch)
    return deleted


def public_snapshot_exclude_patterns(repo: Path) -> list[str]:
    config_path = repo / PUBLIC_SNAPSHOT_EXCLUDE_CONFIG
    if not config_path.exists():
        return []
    patterns: list[str] = []
    for line in config_path.read_text(encoding="utf-8").splitlines():
        stripped = line.strip()
        if stripped and not stripped.startswith("#"):
            patterns.append(stripped.replace("\\", "/"))
    return patterns


def _path_matches_public_exclude(path: str, pattern: str) -> bool:
    normalized_path = normalize_repo_path(path)
    normalized_pattern = pattern.strip().replace("\\", "/")
    if normalized_pattern.endswith("/**"):
        scope_pattern = normalized_pattern[:-3].rstrip("/")
        if any(marker in scope_pattern for marker in "*?["):
            return fnmatchcase(normalized_path, f"{scope_pattern}/*")
        return repo_path_in_scope(normalized_path, scope_pattern)
    if fnmatchcase(normalized_path, normalized_pattern):
        return True
    if not any(marker in normalized_pattern for marker in "*?["):
        return repo_path_in_scope(normalized_path, normalized_pattern.rstrip("/"))
    return False


def public_snapshot_excluded_paths(paths: list[str], patterns: list[str]) -> list[str]:
    return sorted(
        normalize_repo_path(path)
        for path in paths
        if any(_path_matches_public_exclude(path, pattern) for pattern in patterns)
    )


def _remove_public_snapshot_exclusions(snapshot: Path, paths: list[str]) -> None:
    for start in range(0, len(paths), GIT_RM_CHUNK_SIZE):
        chunk = paths[start : start + GIT_RM_CHUNK_SIZE]
        require_git_success(
            run_git(snapshot, ["rm", "-r", "--cached", "--ignore-unmatch", "--", *chunk]),
            "public snapshot curated exclusion removal failed",
        )


def run_public_snapshot(repo: Path, public_remote: str | None, private_projects: list[str]) -> dict[str, object] | None:
    inventory = private_project_inventory_payload(repo)
    if inventory["outcome"] != "pass":
        raise SystemExit(str(inventory["reason"]))
    private_projects = list(inventory["private_projects"])
    exclude_patterns = public_snapshot_exclude_patterns(repo)
    with tempfile.TemporaryDirectory(prefix="reefiki-public-snapshot-") as tempdir:
        snapshot = Path(tempdir) / "snapshot"
        require_git_success(run_git(repo, ["worktree", "add", "--detach", str(snapshot), "HEAD"]), "public snapshot worktree failed")
        branch = ""
        pushed = False
        try:
            branch = f"{PUBLIC_SNAPSHOT_BRANCH_PREFIX}{datetime.now().strftime('%Y%m%d%H%M%S')}"
            require_git_success(run_git(snapshot, ["checkout", "--orphan", branch]), "public snapshot branch failed")
            require_git_success(run_git(snapshot, ["add", "-A"]), "public snapshot staging failed")
            for name in private_projects:
                project_path = snapshot / "projects" / name
                if project_path.exists():
                    require_git_success(
                        run_git(snapshot, ["rm", "-r", "--cached", f"projects/{name}"]),
                        f"public snapshot private project removal failed: {name}",
                    )
            staged = require_git_success(run_git(snapshot, ["ls-files"]), "public snapshot scan failed")
            staged_paths = [line.strip() for line in staged.splitlines() if line.strip()]
            excluded_paths = public_snapshot_excluded_paths(staged_paths, exclude_patterns)
            if excluded_paths:
                _remove_public_snapshot_exclusions(snapshot, excluded_paths)
                staged = require_git_success(run_git(snapshot, ["ls-files"]), "public snapshot rescan failed")
            leaked = [
                path
                for path in staged.splitlines()
                if any(repo_path_in_scope(path, f"projects/{name}") for name in private_projects)
            ]
            if leaked:
                return {
                    "outcome": "block",
                    "reason": "private_path_leak",
                    "blocking_paths": leaked,
                }
            staged_paths = [line.strip() for line in staged.splitlines() if line.strip()]
            secret_scan = secret_content_scan_payload(snapshot, staged_paths, "public-snapshot")
            if secret_scan["outcome"] != "pass":
                return {
                    "outcome": "block",
                    "reason": secret_scan["reason"],
                    "checked_paths": secret_scan["checked_paths"],
                    "blocking_paths": secret_scan["blocking_paths"],
                }
            inspect_payload = {
                "outcome": "pass",
                "reason": None,
                "staged_count": len(staged_paths),
                "excluded_count": len(excluded_paths),
                "excluded_paths": excluded_paths,
                "private_projects": private_projects,
                "leaked_private_paths": [],
                "secret_scan": {
                    "outcome": secret_scan["outcome"],
                    "checked_count": len(secret_scan["checked_paths"]),
                    "blocking_paths": secret_scan["blocking_paths"],
                },
            }
            if public_remote is None:
                return inspect_payload
            require_git_success(
                run_git(snapshot, ["commit", "-m", f"public: template snapshot {date.today().isoformat()}"]),
                "public snapshot commit failed",
            )
            require_git_success(run_git(snapshot, ["push", public_remote, "HEAD:main", "--force-with-lease"]), "public snapshot push failed")
            pushed = True
            return None
        finally:
            run_git(repo, ["worktree", "remove", "--force", str(snapshot)])
            if pushed and branch:
                cleanup_local_public_snapshot_branches(repo, keep_branch=branch)
