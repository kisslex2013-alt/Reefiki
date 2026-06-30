from __future__ import annotations

import posixpath
from pathlib import Path


def normalize_repo_path(path: str) -> str:
    normalized = path.strip().replace("\\", "/")
    if normalized.startswith("./"):
        normalized = normalized[2:]
    normalized = posixpath.normpath(normalized)
    if normalized in {"", "."} or normalized.startswith("../") or normalized == ".." or normalized.startswith("/"):
        raise SystemExit(f"invalid repo-relative path: {path}")
    return normalized


def repo_path_in_scope(path: str, scope: str) -> bool:
    normalized_path = normalize_repo_path(path)
    normalized_scope = normalize_repo_path(scope).rstrip("/")
    return normalized_path == normalized_scope or normalized_path.startswith(f"{normalized_scope}/")


def normalize_target_project_name(target_project: str) -> str:
    normalized = target_project.strip()
    if not normalized:
        raise SystemExit("target project is required")
    if any(sep in normalized for sep in ("/", "\\")):
        raise SystemExit("target project must not contain path separators")
    if normalized in {".", ".."} or ".." in normalized:
        raise SystemExit("target project must not contain '..'")
    return normalized


def resolve_contained_path(root: Path, path_text: str) -> tuple[Path | None, str]:
    path = Path(path_text)
    if not path.is_absolute():
        path = root / path
    resolved = path.resolve()
    root_resolved = root.resolve()
    if root_resolved not in [resolved, *resolved.parents]:
        return None, "path-outside-project"
    return resolved, "ok"
