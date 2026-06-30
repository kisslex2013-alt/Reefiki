from __future__ import annotations

import json
from pathlib import Path

from .git_utils import require_git_success, run_git
from .repo_paths import normalize_target_project_name, repo_path_in_scope

GUARD_MODES = {"harvest", "process", "docs", "code", "code/docs"}
WIKI_TYPES = {"sources", "entities", "concepts", "synthesis", "decisions", "skills", "registries"}


def git_staged_entries(repo: Path) -> list[tuple[str, str]]:
    output = require_git_success(
        run_git(repo, ["diff", "--cached", "--name-status", "--diff-filter=ACMRTD"]),
        "git staged status scan failed",
    )
    entries: list[tuple[str, str]] = []
    for line in output.splitlines():
        parts = [part.strip() for part in line.split("\t") if part.strip()]
        if len(parts) < 2:
            continue
        status = parts[0][0]
        path = parts[-1].replace("\\", "/")
        entries.append((status, path))
    return sorted(entries, key=lambda item: item[1])


def staged_file_is_append_only(repo: Path, path: str) -> bool:
    old = run_git(repo, ["show", f"HEAD:{path}"])
    new = run_git(repo, ["show", f":{path}"])
    if new.returncode != 0:
        return False
    if old.returncode != 0:
        return True
    return new.stdout.startswith(old.stdout) and len(new.stdout) >= len(old.stdout)


def _is_target_raw(path: str, target_project: str) -> bool:
    return repo_path_in_scope(path, f"projects/{target_project}/raw")


def _is_any_raw(path: str) -> bool:
    normalized = path.replace("\\", "/")
    return normalized.startswith("projects/") and "/raw/" in normalized


def _is_target_structure_gitkeep(path: str, status: str, target_project: str) -> bool:
    project = f"projects/{target_project}"
    return status == "A" and path in {
        f"{project}/inbox/.gitkeep",
        f"{project}/raw/.gitkeep",
        f"{project}/seen/.gitkeep",
    }


def _is_target_wiki_typed_page(path: str, target_project: str) -> bool:
    project = f"projects/{target_project}"
    return any(repo_path_in_scope(path, f"{project}/wiki/{wiki_type}") for wiki_type in WIKI_TYPES)


def _is_target_wiki_log(path: str, target_project: str) -> bool:
    return path == f"projects/{target_project}/wiki/log.md"


def _is_process_path(path: str, status: str, target_project: str) -> bool:
    project = f"projects/{target_project}"
    if repo_path_in_scope(path, f"{project}/inbox"):
        return True
    if repo_path_in_scope(path, f"{project}/seen"):
        return True
    if path in {f"{project}/wiki/index.md", f"{project}/wiki/log.md"}:
        return True
    if _is_target_raw(path, target_project):
        return status == "A"
    for wiki_type in WIKI_TYPES:
        if repo_path_in_scope(path, f"{project}/wiki/{wiki_type}"):
            return True
    return False


def _is_docs_path(path: str, target_project: str) -> bool:
    project = f"projects/{target_project}"
    root_doc = "/" not in path and path.endswith((".md", ".txt"))
    return (
        root_doc
        or repo_path_in_scope(path, ".agents/skills")
        or repo_path_in_scope(path, ".claude")
        or repo_path_in_scope(path, "docs")
        or repo_path_in_scope(path, "projects/_template")
        or path in {
            f"{project}/AGENTS.md",
            f"{project}/CLAUDE.md",
            f"{project}/_domain.md",
            f"{project}/golden-queries.yml",
            f"{project}/plans/.gitkeep",
            f"{project}/wiki/_dashboard.md",
            f"{project}/wiki/_schema.md",
            f"{project}/wiki/log.md",
            f"{project}/wiki/index.md",
        }
        or _is_target_wiki_typed_page(path, target_project)
        or repo_path_in_scope(path, f"{project}/.claude")
        or repo_path_in_scope(path, f"{project}/deep-research")
    )


def _is_code_path(path: str, target_project: str) -> bool:
    return (
        repo_path_in_scope(path, "scripts")
        or repo_path_in_scope(path, "tests")
        or repo_path_in_scope(path, ".github/workflows")
        or path == "pyproject.toml"
        or _is_docs_path(path, target_project)
    )


def _mode_allows_path(path: str, status: str, target_project: str, mode: str) -> bool:
    if _is_target_structure_gitkeep(path, status, target_project):
        return True
    if mode == "harvest":
        return repo_path_in_scope(path, f"projects/{target_project}/wiki")
    if mode == "process":
        return _is_process_path(path, status, target_project)
    if mode == "docs":
        return _is_docs_path(path, target_project)
    if mode in {"code", "code/docs"}:
        return _is_code_path(path, target_project)
    return False


def guard_staged_payload(repo: Path, target_project: str, mode: str = "harvest") -> dict[str, object]:
    target_project = normalize_target_project_name(target_project)
    if mode not in GUARD_MODES:
        raise SystemExit(f"unsupported guard-staged mode: {mode}")
    allowed_prefix = f"projects/{target_project}/wiki/" if mode == "harvest" else f"{mode}-profile:projects/{target_project}"
    entries = git_staged_entries(repo)
    staged = [path for _status, path in entries]
    violations: list[dict[str, str]] = []
    for status, path in entries:
        reason = ""
        if _is_any_raw(path):
            if not (
                _is_target_structure_gitkeep(path, status, target_project)
                or (mode == "process" and _is_target_raw(path, target_project) and status == "A")
            ):
                reason = "raw_modify_delete_forbidden" if status != "A" else "raw_create_requires_process_mode"
        if not reason and _is_target_wiki_log(path, target_project) and status != "A" and not staged_file_is_append_only(repo, path):
            reason = "log_not_append_only"
        if not reason and not _mode_allows_path(path, status, target_project, mode):
            reason = "outside_mode_scope"
        if reason:
            violations.append({"path": path, "reason": reason})
    blocking = [item["path"] for item in violations]
    return {
        "target_project": target_project,
        "mode": mode,
        "allowed_prefix": allowed_prefix,
        "outcome": "pass" if not blocking else "block",
        "staged_paths": staged,
        "blocking_paths": blocking,
        "violations": violations,
    }


def print_guard_staged(repo: Path, target_project: str, fmt: str, mode: str = "harvest") -> int:
    payload = guard_staged_payload(repo, target_project, mode)
    if fmt == "json":
        print(json.dumps(payload, ensure_ascii=False, indent=2))
    else:
        print(f"target_project: {payload['target_project']}")
        print(f"mode: {payload['mode']}")
        print(f"allowed_prefix: {payload['allowed_prefix']}")
        print(f"outcome: {payload['outcome']}")
        print("staged_paths:")
        for path in payload["staged_paths"]:
            print(f"- {path}")
        if payload["blocking_paths"]:
            print("blocking_paths:")
            for path in payload["blocking_paths"]:
                print(f"- {path}")
            print("violations:")
            for violation in payload["violations"]:
                print(f"- {violation['path']}: {violation['reason']}")
    return 0 if payload["outcome"] == "pass" else 1
