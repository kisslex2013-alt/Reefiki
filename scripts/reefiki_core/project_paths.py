from __future__ import annotations

from pathlib import Path


SKIP_WIKI_FILES = {"index.md", "log.md", "_schema.md", "_dashboard.md", "_domain.md", "_overview.md"}
SKIP_WIKI_DIRS = {"logs"}


def project_root(path: Path) -> Path:
    path = path.resolve()
    if path.name == "wiki":
        return path.parent
    if (path / "wiki").is_dir():
        return path
    raise SystemExit(f"Project root not found: {path}")


def repo_root(path: Path) -> Path:
    path = path.resolve()
    for candidate in [path, *path.parents]:
        if (candidate / "projects").is_dir():
            return candidate
    raise SystemExit(f"REEFIKI root not found: {path}")


def list_projects(root: Path) -> list[Path]:
    projects_dir = root / "projects"
    return sorted(path for path in projects_dir.iterdir() if path.is_dir() and path.name != "_template")


def find_project(root: Path, name: str) -> Path:
    normalized = name.strip().lower()
    for path in list_projects(root):
        if path.name.lower() == normalized:
            return path
    raise SystemExit(f"Unknown REEFIKI project: {name}")


def iter_pages(project: Path) -> list[Path]:
    wiki = project / "wiki"
    return sorted(
        p
        for p in wiki.glob("*/*.md")
        if p.name not in SKIP_WIKI_FILES and p.parent.name not in SKIP_WIKI_DIRS
    )


def db_path(project: Path) -> Path:
    state = project / ".reefiki"
    state.mkdir(exist_ok=True)
    return state / "index.sqlite"


def relative(project: Path, path: Path) -> str:
    return path.resolve().relative_to(project.resolve()).as_posix()
