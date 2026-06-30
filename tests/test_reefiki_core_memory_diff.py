from pathlib import Path

from scripts.reefiki_core.memory_diff import memory_diff


def run_git(repo: Path, *args: str) -> None:
    import subprocess

    completed = subprocess.run(["git", *args], cwd=repo, check=False, capture_output=True, text=True)
    if completed.returncode != 0:
        raise AssertionError(completed.stderr or completed.stdout)


def write_page(project: Path, slug: str, body: str = "Body") -> Path:
    target = project / "wiki" / "concepts"
    target.mkdir(parents=True, exist_ok=True)
    path = target / f"{slug}.md"
    path.write_text(
        f"""---
id: {slug}
type: concept
title: "{slug}"
tags: [diff]
useful_when:
  - "testing memory diff"
date_added: 2026-06-11
use_count: 0
last_used: null
---
{body}
""",
        encoding="utf-8",
    )
    return path


def test_memory_diff_reports_project_wiki_page_changes(tmp_path: Path) -> None:
    repo = tmp_path / "repo"
    project = repo / "projects" / "reefiki"
    repo.mkdir()
    run_git(repo, "init")
    run_git(repo, "config", "user.email", "test@example.invalid")
    run_git(repo, "config", "user.name", "Test")
    write_page(project, "baseline")
    run_git(repo, "add", ".")
    run_git(repo, "commit", "-m", "baseline")

    changed = write_page(project, "baseline", "Updated body")

    payload = memory_diff(repo, "reefiki", from_ref="HEAD")

    assert payload["project"] == "reefiki"
    assert payload["total"] == 1
    assert payload["counts"] == {"M": 1}
    assert payload["files"] == [
        {"status": "M", "path": "wiki/concepts/baseline.md", "category": "page"}
    ]
    assert changed.exists()
