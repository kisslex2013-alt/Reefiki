from pathlib import Path

import pytest

from scripts.reefiki_core.project_paths import db_path, find_project, iter_pages, project_root, relative, repo_root


def write_page(path: Path) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text("---\nid: page\n---\n", encoding="utf-8")


def test_project_root_accepts_project_or_wiki_path(tmp_path: Path) -> None:
    project = tmp_path / "projects" / "reefiki"
    (project / "wiki").mkdir(parents=True)

    assert project_root(project) == project
    assert project_root(project / "wiki") == project
    with pytest.raises(SystemExit):
        project_root(tmp_path)


def test_repo_root_and_find_project_use_projects_directory(tmp_path: Path) -> None:
    root = tmp_path / "repo"
    project = root / "projects" / "reefiki"
    (project / "wiki").mkdir(parents=True)
    (root / "projects" / "_template").mkdir()

    assert repo_root(project) == root
    assert find_project(root, "REEFIKI") == project
    with pytest.raises(SystemExit):
        find_project(root, "missing")


def test_iter_pages_skips_service_files_and_logs(tmp_path: Path) -> None:
    project = tmp_path / "project"
    write_page(project / "wiki" / "concepts" / "keep.md")
    write_page(project / "wiki" / "concepts" / "_overview.md")
    write_page(project / "wiki" / "logs" / "skip.md")
    (project / "wiki" / "index.md").write_text("# Index\n", encoding="utf-8")

    assert iter_pages(project) == [project / "wiki" / "concepts" / "keep.md"]


def test_db_path_creates_state_dir_and_relative_uses_posix_paths(tmp_path: Path) -> None:
    project = tmp_path / "project"
    project.mkdir()
    database = db_path(project)

    assert database == project / ".reefiki" / "index.sqlite"
    assert database.parent.is_dir()
    assert relative(project, project / "wiki" / "concepts" / "page.md") == "wiki/concepts/page.md"


def test_relative_normalizes_project_and_child_paths(tmp_path: Path) -> None:
    project = tmp_path / "project"
    project.mkdir()
    alias_project = project / ".." / "project"
    page = project / "wiki" / "concepts" / "page.md"

    assert relative(alias_project, page) == "wiki/concepts/page.md"
