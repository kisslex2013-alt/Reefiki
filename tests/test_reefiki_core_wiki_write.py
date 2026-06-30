import subprocess
import sys
import threading
import time
from pathlib import Path

import pytest

ROOT = Path(__file__).resolve().parents[1]
SCRIPTS = ROOT / "scripts"
if str(SCRIPTS) not in sys.path:
    sys.path.insert(0, str(SCRIPTS))

from reefiki_core.git_utils import git_status_paths
import reefiki_core.wiki_lock as wiki_lock
from reefiki_core.wiki_lock import project_lock
from reefiki_core.wiki_write import wiki_write_payload


def run_git(repo: Path, *args: str) -> str:
    completed = subprocess.run(
        ["git", *args],
        cwd=repo,
        check=True,
        capture_output=True,
        text=True,
        encoding="utf-8",
    )
    return completed.stdout.strip()


def init_repo(repo: Path) -> None:
    repo.mkdir(parents=True, exist_ok=True)
    run_git(repo, "init")
    run_git(repo, "config", "user.email", "test@example.invalid")
    run_git(repo, "config", "user.name", "Test User")
    (repo / "README.md").write_text("# Fixture\n", encoding="utf-8")
    run_git(repo, "add", "README.md")
    run_git(repo, "commit", "-m", "Initial commit")


def page(page_id: str, title: str, body: str = "Body.\n") -> str:
    return f"""---
id: {page_id}
type: skill
title: "{title}"
tags: [test]
useful_when:
  - "testing wiki-write behavior"
sources: []
date_added: 2026-06-26
use_count: 0
last_used: null
---
{body}"""


def test_wiki_write_commits_typed_page_and_leaves_clean_tree(tmp_path: Path) -> None:
    repo = tmp_path / "repo"
    init_repo(repo)

    code, payload = wiki_write_payload(
        repo,
        repo,
        "metrica",
        "wiki/skills/new-page.md",
        page("new-page", "New Page"),
        "metrica: write new page",
        validate=False,
        lock_timeout_seconds=1,
        direct_repo=True,
    )

    assert code == 0
    assert payload["outcome"] == "pass"
    assert payload["committed_paths"] == ["projects/metrica/wiki/skills/new-page.md"]
    assert (repo / "projects" / "metrica" / "wiki" / "skills" / "new-page.md").exists()
    assert git_status_paths(repo) == []


def test_wiki_write_blocks_dirty_target_path_without_overwriting(tmp_path: Path) -> None:
    repo = tmp_path / "repo"
    init_repo(repo)
    target = repo / "projects" / "metrica" / "wiki" / "skills" / "existing.md"
    target.parent.mkdir(parents=True)
    target.write_text(page("existing", "Existing"), encoding="utf-8")
    run_git(repo, "add", "projects/metrica/wiki/skills/existing.md")
    run_git(repo, "commit", "-m", "Add existing page")
    target.write_text(page("existing", "Existing", "Dirty local edit.\n"), encoding="utf-8")

    code, payload = wiki_write_payload(
        repo,
        repo,
        "metrica",
        "wiki/skills/existing.md",
        page("existing", "Existing", "Wrapper edit.\n"),
        "metrica: update existing page",
        validate=False,
        lock_timeout_seconds=1,
        direct_repo=True,
    )

    assert code == 1
    assert payload["outcome"] == "block"
    assert payload["reason"] == "target_path_dirty"
    assert "Dirty local edit." in target.read_text(encoding="utf-8")


def test_wiki_write_blocks_new_missing_backlink_and_rolls_back(tmp_path: Path) -> None:
    repo = tmp_path / "repo"
    init_repo(repo)
    target = repo / "projects" / "metrica" / "wiki" / "skills" / "target.md"
    target.parent.mkdir(parents=True)
    target.write_text(page("target", "Target"), encoding="utf-8")
    run_git(repo, "add", "projects/metrica/wiki/skills/target.md")
    run_git(repo, "commit", "-m", "Add target page")

    code, payload = wiki_write_payload(
        repo,
        repo,
        "metrica",
        "wiki/skills/source.md",
        page("source", "Source", "## Related\n\n[[target]]\n"),
        "metrica: add source page",
        validate=False,
        lock_timeout_seconds=1,
        direct_repo=True,
    )

    assert code == 1
    assert payload["outcome"] == "block"
    assert payload["reason"] == "new_missing_backlink"
    assert not (repo / "projects" / "metrica" / "wiki" / "skills" / "source.md").exists()
    assert git_status_paths(repo) == []


def test_wiki_write_requires_marker_unless_direct_repo(tmp_path: Path) -> None:
    repo = tmp_path / "repo"
    init_repo(repo)

    with pytest.raises(SystemExit, match="requires .reefiki marker"):
        wiki_write_payload(
            repo,
            repo,
            "metrica",
            "wiki/skills/new-page.md",
            page("new-page", "New Page"),
            "metrica: write new page",
            validate=False,
        )


def test_wiki_write_secret_gate_rolls_back_new_file(tmp_path: Path) -> None:
    repo = tmp_path / "repo"
    init_repo(repo)
    marker = "api" + "_key"

    code, payload = wiki_write_payload(
        repo,
        repo,
        "metrica",
        "wiki/skills/secret-page.md",
        page("secret-page", "Secret Page", f"{marker} = 'value'\n"),
        "metrica: add secret page",
        validate=False,
        lock_timeout_seconds=1,
        direct_repo=True,
    )

    assert code == 1
    assert payload["outcome"] == "block"
    assert payload["reason"] == "secret_like_content"
    assert not (repo / "projects" / "metrica" / "wiki" / "skills" / "secret-page.md").exists()
    assert git_status_paths(repo) == []


def test_wiki_write_reports_project_lock_timeout(tmp_path: Path) -> None:
    repo = tmp_path / "repo"
    init_repo(repo)
    lock_dir = repo / ".reefiki" / "locks"
    lock_dir.mkdir(parents=True)
    (lock_dir / "metrica.lock").write_text("busy\n", encoding="utf-8")

    code, payload = wiki_write_payload(
        repo,
        repo,
        "metrica",
        "wiki/skills/new-page.md",
        page("new-page", "New Page"),
        "metrica: write new page",
        validate=False,
        lock_timeout_seconds=0,
        direct_repo=True,
    )

    assert code == 1
    assert payload["outcome"] == "block"
    assert payload["reason"] == "project_lock_timeout"


def test_wiki_write_blocks_marker_with_wrong_junction_target(tmp_path: Path) -> None:
    repo = tmp_path / "reefiki"
    code_project = tmp_path / "app"
    repo.mkdir()
    code_project.mkdir()
    (code_project / "_wiki").mkdir()
    (code_project / ".reefiki").write_text(
        f"REEFIKI_path: {repo}\nproject_name: metrica\nwiki_junction: _wiki\n",
        encoding="utf-8",
    )

    with pytest.raises(SystemExit, match="wiki junction target does not match"):
        wiki_write_payload(
            repo,
            code_project,
            "metrica",
            "wiki/skills/new-page.md",
            page("new-page", "New Page"),
            "metrica: write new page",
            validate=False,
        )


def test_project_lock_serializes_concurrent_attempts(tmp_path: Path) -> None:
    repo = tmp_path / "repo"
    acquired: list[str] = []

    def worker() -> None:
        with project_lock(repo, "metrica", "second", timeout_seconds=1):
            acquired.append("second")

    with project_lock(repo, "metrica", "first", timeout_seconds=1):
        thread = threading.Thread(target=worker)
        thread.start()
        time.sleep(0.1)
        assert acquired == []
    thread.join(timeout=2)

    assert acquired == ["second"]


def test_project_lock_treats_windows_permission_on_existing_lock_as_busy(
    monkeypatch: pytest.MonkeyPatch, tmp_path: Path
) -> None:
    repo = tmp_path / "repo"
    lock_dir = repo / ".reefiki" / "locks"
    lock_dir.mkdir(parents=True)
    lock_path = lock_dir / "metrica.lock"
    lock_path.write_text("busy\n", encoding="utf-8")
    real_open = wiki_lock.os.open
    attempts = 0

    def flaky_open(path: str, flags: int, *args: object, **kwargs: object) -> int:
        nonlocal attempts
        attempts += 1
        if attempts == 1:
            raise PermissionError(13, "Permission denied", path)
        return real_open(path, flags, *args, **kwargs)

    def release_lock(_seconds: float) -> None:
        lock_path.unlink()

    monkeypatch.setattr(wiki_lock.os, "open", flaky_open)
    monkeypatch.setattr(wiki_lock.time, "sleep", release_lock)

    with project_lock(repo, "metrica", "second", timeout_seconds=1, poll_seconds=0.01):
        assert attempts == 2


def test_project_lock_treats_windows_permission_on_disappearing_lock_as_busy(
    monkeypatch: pytest.MonkeyPatch, tmp_path: Path
) -> None:
    repo = tmp_path / "repo"
    lock_dir = repo / ".reefiki" / "locks"
    lock_dir.mkdir(parents=True)
    lock_path = lock_dir / "metrica.lock"
    lock_path.write_text("busy\n", encoding="utf-8")
    real_open = wiki_lock.os.open
    attempts = 0

    def flaky_open(path: str, flags: int, *args: object, **kwargs: object) -> int:
        nonlocal attempts
        attempts += 1
        if attempts == 1:
            lock_path.unlink()
            raise PermissionError(13, "Permission denied", path)
        return real_open(path, flags, *args, **kwargs)

    monkeypatch.setattr(wiki_lock.os, "open", flaky_open)

    with project_lock(repo, "metrica", "second", timeout_seconds=1, poll_seconds=0.01):
        assert attempts == 2
