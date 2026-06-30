from __future__ import annotations

import json
from pathlib import Path

try:
    from reefiki_memory import AccessBoundaryContext, PolicySafetyLayer
except ModuleNotFoundError:  # pragma: no cover - used when imported as scripts.reefiki_core in tests
    from scripts.reefiki_memory import AccessBoundaryContext, PolicySafetyLayer

from .repo_paths import normalize_repo_path


FORBIDDEN_SCAN_DIRS = {
    ".git",
    ".hg",
    ".svn",
    ".cache",
    ".mypy_cache",
    ".pytest_cache",
    ".ruff_cache",
    ".venv",
    "__pycache__",
    "build",
    "dist",
    "node_modules",
    "target",
    "vendor",
    ".next",
}

BINARY_OR_ARCHIVE_SUFFIXES = {
    ".7z",
    ".bin",
    ".bmp",
    ".dll",
    ".dylib",
    ".exe",
    ".gif",
    ".ico",
    ".iso",
    ".jpg",
    ".jpeg",
    ".mp3",
    ".mp4",
    ".pdf",
    ".png",
    ".pyd",
    ".so",
    ".tar",
    ".webp",
    ".zip",
}

MAX_FULL_TREE_FILE_BYTES = 1_000_000
SECRET_BLOCK_REASONS = {"secret_like_content", "secret_like_path"}


def full_tree_candidate_paths(repo: Path) -> tuple[list[str], list[dict[str, str]]]:
    candidates: list[str] = []
    skipped: list[dict[str, str]] = []
    for path in sorted(repo.rglob("*")):
        try:
            relative = path.relative_to(repo)
        except ValueError:
            continue
        normalized = relative.as_posix()
        if path.is_symlink():
            skipped.append({"path": normalized, "reason": "symlink"})
            continue
        if any(part in FORBIDDEN_SCAN_DIRS for part in relative.parts):
            if path.is_file():
                skipped.append({"path": normalized, "reason": "forbidden_dir"})
            continue
        if not path.is_file():
            continue
        suffix = path.suffix.lower()
        if suffix in BINARY_OR_ARCHIVE_SUFFIXES:
            skipped.append({"path": normalized, "reason": "binary_or_archive"})
            continue
        try:
            size = path.stat().st_size
        except OSError:
            skipped.append({"path": normalized, "reason": "stat_failed"})
            continue
        if size > MAX_FULL_TREE_FILE_BYTES:
            skipped.append({"path": normalized, "reason": "too_large"})
            continue
        candidates.append(normalized)
    return candidates, skipped


def secret_content_scan_payload(
    repo: Path,
    paths: list[str],
    operation: str,
) -> dict[str, object]:
    boundary = AccessBoundaryContext(
        project="repo",
        allowed_scopes=[],
        forbidden_scopes=[],
        visibility="private",
    )
    scanner = PolicySafetyLayer()
    checked_paths: list[str] = []
    blocking_paths: list[str] = []
    blocking_reasons: set[str] = set()
    for path_text in paths:
        normalized = normalize_repo_path(path_text)
        path = repo / normalized
        if not path.exists() or not path.is_file():
            continue
        checked_paths.append(normalized)
        content = path.read_text(encoding="utf-8", errors="replace")
        result = scanner.preflight(
            boundary,
            operation=operation,
            content=content,
            paths=[normalized],
        )
        secret_reasons = SECRET_BLOCK_REASONS.intersection(result.blocking_reasons)
        if secret_reasons:
            blocking_paths.append(normalized)
            blocking_reasons.update(secret_reasons)
    reason = None
    if blocking_reasons:
        reason = "secret_like_content" if "secret_like_content" in blocking_reasons else "secret_like_path"
    return {
        "operation": operation,
        "outcome": "block" if blocking_paths else "pass",
        "reason": reason,
        "checked_paths": checked_paths,
        "blocking_paths": blocking_paths,
    }


def full_tree_secret_scan_payload(repo: Path) -> dict[str, object]:
    candidates, skipped = full_tree_candidate_paths(repo)
    payload = secret_content_scan_payload(repo, candidates, "secret-scan")
    payload["scan_scope"] = "full-tree"
    payload["skipped_paths"] = skipped
    payload["skipped_count"] = len(skipped)
    return payload


def print_secret_scan(repo: Path, paths: list[str], fmt: str, *, scan_all: bool = False) -> int:
    if scan_all and paths:
        payload: dict[str, object] = {
            "operation": "secret-scan",
            "outcome": "block",
            "reason": "all_with_paths",
            "checked_paths": [],
            "blocking_paths": [],
        }
    elif scan_all:
        payload = full_tree_secret_scan_payload(repo)
    elif not paths:
        payload = {
            "operation": "secret-scan",
            "outcome": "block",
            "reason": "no_paths",
            "checked_paths": [],
            "blocking_paths": [],
        }
    else:
        payload = secret_content_scan_payload(repo, paths, "secret-scan")
    if fmt == "json":
        print(json.dumps(payload, ensure_ascii=False, indent=2))
    else:
        print(f"outcome: {payload['outcome']}")
        if payload.get("reason"):
            print(f"reason: {payload['reason']}")
        if payload.get("scan_scope"):
            print(f"scan_scope: {payload['scan_scope']}")
        if payload.get("skipped_count") is not None:
            print(f"skipped_count: {payload['skipped_count']}")
        print("checked_paths:")
        for path in payload.get("checked_paths", []):
            print(f"- {path}")
        if payload.get("blocking_paths"):
            print("blocking_paths:")
            for path in payload["blocking_paths"]:
                print(f"- {path}")
    return 0 if payload["outcome"] == "pass" else 1
