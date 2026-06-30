from __future__ import annotations

import json
import os
from pathlib import Path

from .git_utils import git_staged_paths, git_status_paths
from .guard_staged import WIKI_TYPES
from .harvest_commit import harvest_commit_payload_unlocked
from .repo_paths import normalize_repo_path, normalize_target_project_name, repo_path_in_scope
from .review_queues import (
    _changed_wiki_page_ids,
    _new_changed_missing_backlink_items,
    review_queue_scan,
)
from .secret_scan import secret_content_scan_payload
from .wiki_lock import WikiLockTimeout, project_lock


def _read_marker(path: Path) -> dict[str, str]:
    marker = path / ".reefiki"
    if not marker.is_file():
        return {}
    values: dict[str, str] = {}
    for line in marker.read_text(encoding="utf-8", errors="replace").splitlines():
        stripped = line.strip()
        if not stripped or stripped.startswith("#") or ":" not in stripped:
            continue
        key, value = stripped.split(":", 1)
        values[key.strip()] = value.strip()
    return values


def _bridge_context(
    root_hint: Path,
    code_project: Path,
    target_project: str | None,
    direct_repo: bool,
) -> tuple[Path, str, dict[str, object]]:
    marker = _read_marker(code_project)
    if not marker and not direct_repo:
        raise SystemExit("wiki-write requires .reefiki marker unless --direct-repo is set")
    marker_root = marker.get("REEFIKI_path")
    marker_project = marker.get("project_name")
    if target_project and marker_project and target_project != marker_project:
        raise SystemExit("target project does not match .reefiki marker")
    project_name = normalize_target_project_name(target_project or marker_project or "")
    repo = Path(marker_root).resolve() if marker_root else root_hint.resolve()
    context: dict[str, object] = {
        "code_project": str(code_project),
        "marker_found": bool(marker),
        "marker_project": marker_project,
        "direct_repo": direct_repo,
        "wiki_junction": marker.get("wiki_junction"),
    }
    junction_name = marker.get("wiki_junction")
    if marker and junction_name:
        junction = code_project / junction_name
        expected = repo / "projects" / project_name
        context["wiki_junction_path"] = str(junction)
        context["expected_wiki_junction_target"] = str(expected)
        if not junction.exists():
            raise SystemExit("wiki junction from .reefiki marker does not exist")
        if junction.resolve() != expected.resolve():
            raise SystemExit("wiki junction target does not match .reefiki marker")
    return repo, project_name, context


def _repo_wiki_path(target_project: str, path_text: str) -> str:
    raw = path_text.strip().replace("\\", "/")
    if raw.startswith("_wiki/"):
        raw = raw[len("_wiki/") :]
    project_prefix = f"projects/{target_project}/"
    if raw.startswith(project_prefix):
        normalized = normalize_repo_path(raw)
    else:
        if not raw.startswith("wiki/"):
            raise SystemExit("wiki-write path must start with wiki/ or _wiki/wiki/")
        normalized = normalize_repo_path(f"projects/{target_project}/{raw}")
    allowed_scope = f"projects/{target_project}/wiki"
    if not repo_path_in_scope(normalized, allowed_scope):
        raise SystemExit("wiki-write path is outside target project wiki")
    parts = normalized.split("/")
    if len(parts) < 5 or parts[3] not in WIKI_TYPES:
        raise SystemExit("wiki-write only supports typed wiki pages")
    if not normalized.endswith(".md"):
        raise SystemExit("wiki-write only supports markdown pages")
    return normalized


def _atomic_write_text(path: Path, content: str) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    temp_path = path.with_name(f".{path.name}.{os.getpid()}.tmp")
    temp_path.write_text(content, encoding="utf-8")
    temp_path.replace(path)


def _restore_previous(path: Path, previous: str | None) -> None:
    if previous is None:
        try:
            path.unlink()
        except FileNotFoundError:
            pass
        return
    _atomic_write_text(path, previous)


def wiki_write_payload(
    root_hint: Path,
    code_project: Path,
    target_project: str | None,
    path_text: str,
    content: str,
    message: str,
    *,
    validate: bool = True,
    baseline_ref: str = "HEAD",
    stale_days: int = 90,
    lock_timeout_seconds: float = 30.0,
    direct_repo: bool = False,
) -> tuple[int, dict[str, object]]:
    repo, project_name, context = _bridge_context(root_hint, code_project.resolve(), target_project, direct_repo)
    repo_path = _repo_wiki_path(project_name, path_text)
    target = repo / repo_path
    base_payload: dict[str, object] = {
        "target_project": project_name,
        "repo": str(repo),
        "path": repo_path,
        "bridge_context": context,
    }
    try:
        with project_lock(repo, project_name, "wiki-write", timeout_seconds=lock_timeout_seconds) as lock_path:
            payload = {**base_payload, "lock_path": str(lock_path)}
            pre_dirty = set(git_status_paths(repo))
            pre_staged = set(git_staged_paths(repo))
            if repo_path in pre_dirty:
                return 1, {
                    **payload,
                    "outcome": "block",
                    "reason": "target_path_dirty",
                    "blocking_paths": [repo_path],
                }
            if repo_path in pre_staged:
                return 1, {
                    **payload,
                    "outcome": "block",
                    "reason": "target_path_staged",
                    "blocking_paths": [repo_path],
                }

            previous = target.read_text(encoding="utf-8") if target.exists() else None
            _atomic_write_text(target, content)
            try:
                secret_scan = secret_content_scan_payload(repo, [repo_path], "wiki-write")
                if secret_scan["outcome"] != "pass":
                    return 1, {
                        **payload,
                        "outcome": "block",
                        "reason": secret_scan["reason"],
                        "checked_paths": secret_scan["checked_paths"],
                        "blocking_paths": secret_scan["blocking_paths"],
                    }
                project = repo / "projects" / project_name
                current_items = review_queue_scan(project, stale_days=stale_days)
                changed_page_ids = _changed_wiki_page_ids(project, [repo_path])
                try:
                    backlink_items = _new_changed_missing_backlink_items(
                        project,
                        current_items,
                        changed_page_ids,
                        baseline_ref,
                        stale_days,
                    )
                except RuntimeError as exc:
                    return 1, {
                        **payload,
                        "outcome": "block",
                        "reason": "backlink_gate_error",
                        "changed_page_ids": changed_page_ids,
                        "error": str(exc),
                        "blocking_paths": [repo_path],
                    }
                if backlink_items:
                    return 1, {
                        **payload,
                        "outcome": "block",
                        "reason": "new_missing_backlink",
                        "changed_page_ids": changed_page_ids,
                        "items": backlink_items,
                        "blocking_paths": [repo_path],
                    }
                code, commit_payload = harvest_commit_payload_unlocked(
                    repo,
                    project_name,
                    [repo_path],
                    message,
                    validate,
                )
                return code, {
                    **payload,
                    **commit_payload,
                    "write_path": repo_path,
                    "changed_page_ids": changed_page_ids,
                }
            finally:
                if not target.exists() or (repo_path in set(git_status_paths(repo))):
                    head_paths = set(git_status_paths(repo))
                    if repo_path in head_paths:
                        _restore_previous(target, previous)
    except WikiLockTimeout as exc:
        return 1, {
            **base_payload,
            "outcome": "block",
            "reason": "project_lock_timeout",
            "lock_path": str(exc.lock_path),
            "blocking_paths": [repo_path],
        }


def print_wiki_write(
    root_hint: Path,
    code_project: Path,
    target_project: str | None,
    path_text: str,
    content_file: str,
    message: str,
    validate: bool,
    baseline_ref: str,
    stale_days: int,
    lock_timeout_seconds: float,
    direct_repo: bool,
    fmt: str,
) -> int:
    if content_file == "-":
        content = os.sys.stdin.read()
    else:
        content = Path(content_file).read_text(encoding="utf-8")
    code, payload = wiki_write_payload(
        root_hint,
        code_project,
        target_project,
        path_text,
        content,
        message,
        validate=validate,
        baseline_ref=baseline_ref,
        stale_days=stale_days,
        lock_timeout_seconds=lock_timeout_seconds,
        direct_repo=direct_repo,
    )
    if fmt == "json":
        print(json.dumps(payload, ensure_ascii=False, indent=2))
    else:
        print(f"target_project: {payload['target_project']}")
        print(f"path: {payload['path']}")
        print(f"outcome: {payload['outcome']}")
        if payload.get("reason"):
            print(f"reason: {payload['reason']}")
        if payload.get("commit"):
            print(f"commit: {payload['commit']}")
        if payload.get("blocking_paths"):
            print("blocking_paths:")
            for path in payload["blocking_paths"]:
                print(f"- {path}")
    return code
