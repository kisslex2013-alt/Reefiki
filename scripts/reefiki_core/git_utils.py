from __future__ import annotations

import subprocess
from pathlib import Path

from .process_utils import SUBPROCESS_TIMEOUT_SECONDS


def git_staged_paths(repo: Path, env: dict[str, str] | None = None) -> list[str]:
    completed = subprocess.run(
        ["git", "diff", "--cached", "--name-only", "--diff-filter=ACMRT"],
        cwd=repo,
        check=False,
        capture_output=True,
        text=True,
        encoding="utf-8",
        errors="replace",
        env=env,
        timeout=SUBPROCESS_TIMEOUT_SECONDS,
    )
    if completed.returncode != 0:
        detail = completed.stderr.strip() or completed.stdout.strip() or "git staged path scan failed"
        raise SystemExit(detail)
    return sorted(line.strip().replace("\\", "/") for line in completed.stdout.splitlines() if line.strip())


def run_git(repo: Path, args: list[str], env: dict[str, str] | None = None) -> subprocess.CompletedProcess[str]:
    completed = subprocess.run(
        ["git", *args],
        cwd=repo,
        check=False,
        capture_output=True,
        text=True,
        encoding="utf-8",
        errors="replace",
        env=env,
        timeout=SUBPROCESS_TIMEOUT_SECONDS,
    )
    return completed


def require_git_success(completed: subprocess.CompletedProcess[str], fallback: str) -> str:
    if completed.returncode != 0:
        detail = completed.stderr.strip() or completed.stdout.strip() or fallback
        raise SystemExit(detail)
    return completed.stdout.strip()


def git_status_paths(repo: Path) -> list[str]:
    completed = run_git(repo, ["status", "--porcelain=v1", "-z", "--untracked-files=all"])
    if completed.returncode != 0:
        detail = completed.stderr.strip() or completed.stdout.strip() or "git status scan failed"
        raise SystemExit(detail)
    output = completed.stdout
    paths: list[str] = []
    entries = output.split("\0") if output else []
    i = 0
    while i < len(entries):
        entry = entries[i]
        i += 1
        if not entry:
            continue
        status = entry[:2]
        path = entry[3:].replace("\\", "/") if len(entry) > 3 else ""
        if path:
            paths.append(path)
        if "R" in status or "C" in status:
            i += 1
    return sorted(set(paths))


def git_current_branch(repo: Path) -> str:
    branch = require_git_success(run_git(repo, ["branch", "--show-current"]), "current branch lookup failed")
    return branch or "HEAD"


def git_head(repo: Path, short: bool = False) -> str:
    args = ["rev-parse"]
    if short:
        args.append("--short")
    args.append("HEAD")
    return require_git_success(run_git(repo, args), "HEAD lookup failed")


def git_changed_paths(repo: Path, base: str) -> list[str]:
    output = require_git_success(run_git(repo, ["diff", "--name-only", f"{base}...HEAD"]), "changed path scan failed")
    return sorted(line.strip().replace("\\", "/") for line in output.splitlines() if line.strip())


def git_ref_exists(repo: Path, ref: str) -> bool:
    return run_git(repo, ["rev-parse", "--verify", "--quiet", ref]).returncode == 0


def git_is_ancestor(repo: Path, ancestor: str, descendant: str) -> bool:
    return run_git(repo, ["merge-base", "--is-ancestor", ancestor, descendant]).returncode == 0
