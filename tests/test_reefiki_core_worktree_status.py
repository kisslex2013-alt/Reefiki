from pathlib import Path

from scripts.reefiki_core import worktree_status


def test_parse_git_worktree_porcelain_reads_multiple_entries() -> None:
    output = """worktree C:/repo
HEAD abc123
branch refs/heads/main

worktree C:/repo-task
HEAD def456
branch refs/heads/codex/task
"""

    assert worktree_status.parse_git_worktree_porcelain(output) == [
        {"worktree": "C:/repo", "HEAD": "abc123", "branch": "refs/heads/main"},
        {"worktree": "C:/repo-task", "HEAD": "def456", "branch": "refs/heads/codex/task"},
    ]


def test_worktree_status_recommendation_matrix(monkeypatch) -> None:
    monkeypatch.setattr(worktree_status, "git_ref_exists", lambda _path, _base: True)
    path = Path("repo")

    assert worktree_status.worktree_status_recommendation(path, "main", [], "origin/main", False) == (
        "keep",
        "primary_or_base_worktree",
    )
    assert worktree_status.worktree_status_recommendation(path, "codex/task", [], "origin/main", True) == (
        "delete",
        "clean_task_worktree_reachable_from_base",
    )
    assert worktree_status.worktree_status_recommendation(path, "codex/task", [], "origin/main", False) == (
        "review",
        "clean_task_worktree_not_reachable_from_base",
    )
    assert worktree_status.worktree_status_recommendation(path, "feature", ["dirty.md"], "origin/main", False) == (
        "block",
        "dirty_worktree",
    )
    assert worktree_status.worktree_status_recommendation(path, "feature", [], "origin/main", False) == (
        "keep",
        "non_task_worktree",
    )


def test_print_worktree_status_text(monkeypatch, tmp_path, capsys) -> None:
    monkeypatch.setattr(
        worktree_status,
        "worktree_status_payload",
        lambda repo, base, scopes=None: {
            "repo": str(repo),
            "base": base,
            "scopes": scopes or [],
            "shared_checkout_dirty": False,
            "shared_checkout_behind": False,
            "excluded_dirty_paths": [],
            "scope_conflicts": [],
            "worktrees": [
                {
                    "recommendation": "keep",
                    "branch": "main",
                    "head": "abc123",
                    "ahead": 0,
                    "behind": 0,
                    "dirty_paths": [],
                    "reason": "primary_or_base_worktree",
                    "path": str(repo),
                }
            ],
        },
    )

    assert worktree_status.print_worktree_status(tmp_path, "origin/main", "text") == 0

    output = capsys.readouterr().out
    assert "base: origin/main" in output
    assert "keep: main abc123 ahead=0 behind=0 dirty=0 reason=primary_or_base_worktree" in output
