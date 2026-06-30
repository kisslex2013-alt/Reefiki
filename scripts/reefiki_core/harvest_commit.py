from __future__ import annotations

import json
import os
import subprocess
import sys
import tempfile
from pathlib import Path

from .git_utils import git_staged_paths, git_status_paths, require_git_success, run_git
from .process_utils import SUBPROCESS_TIMEOUT_SECONDS
from .repo_paths import normalize_repo_path, normalize_target_project_name, repo_path_in_scope
from .secret_scan import secret_content_scan_payload
from .wiki_lock import WikiLockTimeout, project_lock


SCRIPT_DIR = Path(__file__).resolve().parents[1]


def harvest_commit_payload(
    repo: Path,
    target_project: str,
    paths: list[str],
    message: str,
    validate: bool,
    lock_timeout_seconds: float = 30.0,
) -> tuple[int, dict[str, object]]:
    target_project = normalize_target_project_name(target_project)
    try:
        with project_lock(repo, target_project, "harvest-commit", timeout_seconds=lock_timeout_seconds):
            return harvest_commit_payload_unlocked(repo, target_project, paths, message, validate)
    except WikiLockTimeout as exc:
        return 1, {
            "target_project": target_project,
            "outcome": "block",
            "reason": "project_lock_timeout",
            "lock_path": str(exc.lock_path),
            "requested_paths": sorted({normalize_repo_path(path) for path in paths}),
            "blocking_paths": sorted({normalize_repo_path(path) for path in paths}),
        }


def harvest_commit_payload_unlocked(
    repo: Path,
    target_project: str,
    paths: list[str],
    message: str,
    validate: bool,
) -> tuple[int, dict[str, object]]:
    target_project = normalize_target_project_name(target_project)
    if not message.strip():
        raise SystemExit("commit message is required")
    if not paths:
        raise SystemExit("at least one --path is required")

    allowed_prefix = f"projects/{target_project}/wiki/"
    allowed_scope = allowed_prefix.rstrip("/")
    normalized_paths = sorted({normalize_repo_path(path) for path in paths})
    blocking_paths = [path for path in normalized_paths if not repo_path_in_scope(path, allowed_scope)]
    pre_staged = git_staged_paths(repo)
    already_staged_target_paths = [path for path in pre_staged if path in normalized_paths]
    excluded_dirty_paths = [path for path in git_status_paths(repo) if path not in normalized_paths]

    base_payload: dict[str, object] = {
        "target_project": target_project,
        "allowed_prefix": allowed_prefix,
        "requested_paths": normalized_paths,
        "preexisting_staged_paths": pre_staged,
        "excluded_dirty_paths": excluded_dirty_paths,
    }
    if blocking_paths:
        return 1, {
            **base_payload,
            "outcome": "block",
            "reason": "path_outside_target_wiki",
            "blocking_paths": blocking_paths,
        }
    if already_staged_target_paths:
        return 1, {
            **base_payload,
            "outcome": "block",
            "reason": "target_paths_already_staged",
            "blocking_paths": already_staged_target_paths,
        }

    secret_scan = secret_content_scan_payload(repo, normalized_paths, "harvest-commit")
    if secret_scan["outcome"] != "pass":
        return 1, {
            **base_payload,
            "outcome": "block",
            "reason": secret_scan["reason"],
            "checked_paths": secret_scan["checked_paths"],
            "blocking_paths": secret_scan["blocking_paths"],
        }

    if validate:
        validator = SCRIPT_DIR / "validate_frontmatter.py"
        if validator.exists():
            completed = subprocess.run(
                [sys.executable, str(validator), str(repo / "projects" / target_project / "wiki")],
                cwd=repo,
                check=False,
                capture_output=True,
                text=True,
                encoding="utf-8",
                timeout=SUBPROCESS_TIMEOUT_SECONDS,
            )
            if completed.returncode != 0:
                return 1, {
                    **base_payload,
                    "outcome": "block",
                    "reason": "validation_failed",
                    "validation_output": (completed.stdout + completed.stderr).strip(),
                }

    with tempfile.TemporaryDirectory(prefix="reefiki-harvest-index-") as tempdir:
        env = os.environ.copy()
        env["GIT_INDEX_FILE"] = str(Path(tempdir) / "index")
        require_git_success(run_git(repo, ["read-tree", "HEAD"], env=env), "temporary index setup failed")
        require_git_success(run_git(repo, ["add", "--", *normalized_paths], env=env), "temporary harvest staging failed")
        temp_staged = git_staged_paths(repo, env=env)
        temp_blocking = [path for path in temp_staged if not repo_path_in_scope(path, allowed_scope)]
        if temp_blocking:
            return 1, {
                **base_payload,
                "outcome": "block",
                "reason": "temporary_index_scope_violation",
                "staged_paths": temp_staged,
                "blocking_paths": temp_blocking,
            }
        diff_check = run_git(repo, ["diff", "--cached", "--quiet"], env=env)
        if diff_check.returncode == 0:
            return 1, {
                **base_payload,
                "outcome": "block",
                "reason": "no_changes_to_commit",
                "staged_paths": temp_staged,
                "blocking_paths": [],
            }
        if diff_check.returncode != 1:
            require_git_success(diff_check, "temporary harvest diff failed")
        require_git_success(run_git(repo, ["commit", "-m", message], env=env), "harvest commit failed")

    commit = require_git_success(run_git(repo, ["rev-parse", "--short", "HEAD"]), "commit lookup failed")
    require_git_success(run_git(repo, ["reset", "-q", "HEAD", "--", *normalized_paths]), "post-commit index refresh failed")
    return 0, {
        **base_payload,
        "outcome": "pass",
        "commit": commit,
        "committed_paths": normalized_paths,
        "staged_paths": temp_staged,
        "blocking_paths": [],
    }


def print_harvest_commit(
    repo: Path,
    target_project: str,
    paths: list[str],
    message: str,
    validate: bool,
    fmt: str,
    lock_timeout_seconds: float = 30.0,
) -> int:
    code, payload = harvest_commit_payload(repo, target_project, paths, message, validate, lock_timeout_seconds)
    if fmt == "json":
        print(json.dumps(payload, ensure_ascii=False, indent=2))
    else:
        print(f"target_project: {payload['target_project']}")
        print(f"allowed_prefix: {payload['allowed_prefix']}")
        print(f"outcome: {payload['outcome']}")
        if payload.get("reason"):
            print(f"reason: {payload['reason']}")
        if payload.get("commit"):
            print(f"commit: {payload['commit']}")
        print("committed_paths:")
        for path in payload.get("committed_paths", []):
            print(f"- {path}")
        print("excluded_dirty_paths:")
        for path in payload.get("excluded_dirty_paths", []):
            print(f"- {path}")
        if payload.get("blocking_paths"):
            print("blocking_paths:")
            for path in payload["blocking_paths"]:
                print(f"- {path}")
    return code
