import subprocess

import pytest

from scripts.reefiki_core.git_utils import (
    git_changed_paths,
    git_current_branch,
    git_head,
    git_is_ancestor,
    git_ref_exists,
    git_staged_paths,
    git_status_paths,
    require_git_success,
    run_git,
)


def init_repo(path):
    run_git(path, ["init"])
    run_git(path, ["config", "user.email", "test@example.com"])
    run_git(path, ["config", "user.name", "Test"])


def test_git_utils_report_paths_refs_and_ancestry(tmp_path) -> None:
    repo = tmp_path / "repo"
    repo.mkdir()
    init_repo(repo)
    (repo / "tracked.txt").write_text("one", encoding="utf-8")
    run_git(repo, ["add", "tracked.txt"])

    assert git_staged_paths(repo) == ["tracked.txt"]
    run_git(repo, ["commit", "-m", "initial"])
    base = git_head(repo)
    assert git_current_branch(repo) in {"main", "master"}
    assert git_head(repo, short=True) == base[: len(git_head(repo, short=True))]
    assert git_ref_exists(repo, "HEAD")
    assert git_is_ancestor(repo, base, "HEAD")

    (repo / "tracked.txt").write_text("two", encoding="utf-8")
    (repo / "untracked.txt").write_text("new", encoding="utf-8")

    assert git_status_paths(repo) == ["tracked.txt", "untracked.txt"]
    run_git(repo, ["add", "tracked.txt"])
    run_git(repo, ["commit", "-m", "change tracked"])
    assert git_changed_paths(repo, base) == ["tracked.txt"]


def test_require_git_success_prefers_stderr_then_stdout_then_fallback() -> None:
    assert require_git_success(subprocess.CompletedProcess(args=[], returncode=0, stdout=" ok \n", stderr=""), "fallback") == "ok"

    with pytest.raises(SystemExit, match="stderr detail"):
        require_git_success(subprocess.CompletedProcess(args=[], returncode=1, stdout="stdout detail", stderr="stderr detail"), "fallback")

    with pytest.raises(SystemExit, match="stdout detail"):
        require_git_success(subprocess.CompletedProcess(args=[], returncode=1, stdout="stdout detail", stderr=""), "fallback")

    with pytest.raises(SystemExit, match="fallback"):
        require_git_success(subprocess.CompletedProcess(args=[], returncode=1, stdout="", stderr=""), "fallback")
