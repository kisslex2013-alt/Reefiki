from __future__ import annotations

import json
from collections import Counter
from datetime import datetime
from pathlib import Path

from .git_utils import require_git_success, run_git
from .memory_preflight import memory_preflight
from .project_paths import find_project


EMPTY_TREE_REF = "4b825dc642cb6eb9a060e54bf8d69288fbee4904"


def _run_git(root: Path, args: list[str]) -> str:
    return require_git_success(run_git(root, args), "git command failed")


def resolve_since_date_ref(root: Path, since_date: str, pathspec: str) -> str:
    try:
        datetime.fromisoformat(since_date)
    except ValueError as exc:
        raise ValueError(f"invalid since_date {since_date!r}: {exc}") from exc
    commit = _run_git(
        root,
        [
            "rev-list",
            "--reverse",
            f"--since={since_date} 00:00:00",
            "HEAD",
            "--",
            pathspec,
        ],
    ).splitlines()
    if not commit:
        return "HEAD"
    first = commit[0].strip()
    parents = _run_git(root, ["rev-list", "--parents", "-n", "1", first]).strip().split()
    return parents[1] if len(parents) > 1 else EMPTY_TREE_REF


def memory_diff(
    root: Path,
    project_name: str,
    from_ref: str,
    to_ref: str | None = None,
    since_date: str | None = None,
) -> dict[str, object]:
    project = find_project(root, project_name)
    wiki_prefix = f"projects/{project.name}/wiki"
    resolved_from_ref = from_ref
    if since_date:
        resolved_from_ref = resolve_since_date_ref(root, since_date, wiki_prefix)
    policy = memory_preflight(
        project=project.name,
        visibility="private",
        operation="diff",
        content="",
        paths=[wiki_prefix],
    )
    result: dict[str, object] = {
        "project": project.name,
        "from": resolved_from_ref,
        "to": to_ref or "WORKTREE",
        "since_date": since_date,
        "policy": policy,
        "counts": {},
        "total": 0,
        "files": [],
    }
    if policy["outcome"] == "block":
        return result

    diff_args = ["diff", "--name-status", resolved_from_ref]
    if to_ref:
        diff_args.append(to_ref)
    diff_args.extend(["--", wiki_prefix])
    files: list[dict[str, object]] = []
    counts: Counter[str] = Counter()
    for line in _run_git(root, diff_args).splitlines():
        if not line.strip():
            continue
        parts = line.split("\t")
        status = parts[0]
        path = parts[-1]
        if path.endswith("/index.md") or path.endswith("/log.md"):
            category = "meta"
        else:
            category = "page"
        short_path = path.removeprefix(f"projects/{project.name}/")
        files.append({"status": status, "path": short_path, "category": category})
        counts[status] += 1
    result["files"] = files
    result["counts"] = dict(sorted(counts.items()))
    result["total"] = len(files)
    return result


def print_memory_diff(
    root: Path,
    project_name: str,
    from_ref: str,
    to_ref: str | None,
    since_date: str | None,
    fmt: str,
) -> int:
    result = memory_diff(
        root,
        project_name,
        from_ref=from_ref,
        to_ref=to_ref,
        since_date=since_date,
    )
    if fmt == "json":
        print(json.dumps(result, ensure_ascii=False, indent=2))
    else:
        print(f"project: {result['project']}")
        print(f"diff: {result['from']}..{result['to']}")
        print(f"total: {result['total']}")
        for item in result["files"]:
            print(f"  - {item['status']}: {item['path']}")
    return 1 if result.get("policy", {}).get("outcome") == "block" else 0
