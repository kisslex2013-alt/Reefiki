from __future__ import annotations

from pathlib import Path

from .repo_paths import repo_path_in_scope


def real_project_names(repo: Path) -> list[str]:
    projects_root = repo / "projects"
    if not projects_root.exists():
        return []
    return sorted(
        path.name for path in projects_root.iterdir() if path.is_dir() and path.name != "_template"
    )


def private_project_names(repo: Path) -> list[str]:
    config_path = repo / "scripts" / "public-snapshot.private-projects.txt"
    if not config_path.exists():
        return []
    names: list[str] = []
    for line in config_path.read_text(encoding="utf-8").splitlines():
        stripped = line.strip()
        if stripped and not stripped.startswith("#"):
            names.append(stripped)
    return names


def public_project_names(repo: Path) -> list[str]:
    config_path = repo / "scripts" / "public-snapshot.public-projects.txt"
    if not config_path.exists():
        return []
    names: list[str] = []
    for line in config_path.read_text(encoding="utf-8").splitlines():
        stripped = line.strip()
        if stripped and not stripped.startswith("#"):
            names.append(stripped)
    return names


def private_project_inventory_payload(repo: Path) -> dict[str, object]:
    config_path = repo / "scripts" / "public-snapshot.private-projects.txt"
    real_projects = real_project_names(repo)
    if not config_path.exists():
        return {
            "outcome": "block",
            "reason": "private_project_inventory_missing",
            "private_projects": [],
            "public_projects": public_project_names(repo),
            "real_projects": real_projects,
            "missing_private_projects": real_projects,
        }
    private_projects = private_project_names(repo)
    public_projects = public_project_names(repo)
    if not private_projects:
        return {
            "outcome": "block",
            "reason": "private_project_inventory_empty",
            "private_projects": [],
            "public_projects": public_projects,
            "real_projects": real_projects,
            "missing_private_projects": real_projects,
        }
    missing = [name for name in real_projects if name not in private_projects and name not in public_projects]
    if missing:
        return {
            "outcome": "block",
            "reason": "private_project_inventory_incomplete",
            "private_projects": private_projects,
            "public_projects": public_projects,
            "real_projects": real_projects,
            "missing_private_projects": missing,
        }
    return {
        "outcome": "pass",
        "reason": None,
        "private_projects": private_projects,
        "public_projects": public_projects,
        "real_projects": real_projects,
        "missing_private_projects": [],
    }


def classify_publish_diff(paths: list[str], private_projects: list[str]) -> str:
    private_scopes = [f"projects/{name}" for name in private_projects]
    private_paths = [path for path in paths if any(repo_path_in_scope(path, scope) for scope in private_scopes)]
    public_paths = [path for path in paths if not any(repo_path_in_scope(path, scope) for scope in private_scopes)]
    if private_paths and public_paths:
        return "mixed"
    if private_paths:
        return "private-only"
    if public_paths:
        return "public-safe"
    return "empty"
