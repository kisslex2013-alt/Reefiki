from pathlib import Path

from scripts.reefiki_core import cleanup_worktree


def test_cleanup_worktree_payload_blocks_missing_worktree(tmp_path) -> None:
    code, payload = cleanup_worktree.cleanup_worktree_payload(
        tmp_path,
        tmp_path / "missing",
        base="origin/main",
        dry_run=True,
    )

    assert code == 1
    assert payload["outcome"] == "block"
    assert payload["reason"] == "worktree_missing"
    assert payload["error_code"] == "worktree_missing"


def test_cleanup_worktree_payload_reports_dry_run_actions(monkeypatch, tmp_path) -> None:
    repo = tmp_path / "repo"
    target = tmp_path / "target"
    repo.mkdir()
    target.mkdir()
    monkeypatch.setattr(cleanup_worktree, "git_status_paths", lambda _target: [])
    monkeypatch.setattr(cleanup_worktree, "git_current_branch", lambda _target: "codex/task")
    monkeypatch.setattr(cleanup_worktree, "git_head", lambda _target, short=False: "abc123")
    monkeypatch.setattr(cleanup_worktree, "git_ref_exists", lambda _target, _base: True)
    monkeypatch.setattr(cleanup_worktree, "git_is_ancestor", lambda _target, _ancestor, _base: True)

    code, payload = cleanup_worktree.cleanup_worktree_payload(repo, target, "origin/main", dry_run=True)

    assert code == 0
    assert payload["outcome"] == "pass"
    assert payload["actions"] == ["remove_worktree", "delete_local_branch"]
    assert payload["head_reachable_from_base"] is True
    assert payload["branch_delete_allowed"] is True


def test_cleanup_worktree_payload_blocks_non_codex_branch(monkeypatch, tmp_path) -> None:
    repo = tmp_path / "repo"
    target = tmp_path / "target"
    repo.mkdir()
    target.mkdir()
    monkeypatch.setattr(cleanup_worktree, "git_status_paths", lambda _target: [])
    monkeypatch.setattr(cleanup_worktree, "git_current_branch", lambda _target: "feature/task")
    monkeypatch.setattr(cleanup_worktree, "git_head", lambda _target, short=False: "abc123")
    monkeypatch.setattr(cleanup_worktree, "git_ref_exists", lambda _target, _base: True)
    monkeypatch.setattr(cleanup_worktree, "git_is_ancestor", lambda _target, _ancestor, _base: True)

    code, payload = cleanup_worktree.cleanup_worktree_payload(repo, target, "origin/main", dry_run=True)

    assert code == 1
    assert payload["outcome"] == "block"
    assert payload["reason"] == "non_task_branch"
    assert payload["error_code"] == "non_task_branch"


def test_cleanup_worktree_payload_does_not_report_branch_delete_for_main(monkeypatch, tmp_path) -> None:
    repo = tmp_path / "repo"
    target = tmp_path / "target"
    repo.mkdir()
    target.mkdir()
    monkeypatch.setattr(cleanup_worktree, "git_status_paths", lambda _target: [])
    monkeypatch.setattr(cleanup_worktree, "git_current_branch", lambda _target: "main")
    monkeypatch.setattr(cleanup_worktree, "git_head", lambda _target, short=False: "abc123")
    monkeypatch.setattr(cleanup_worktree, "git_ref_exists", lambda _target, _base: True)
    monkeypatch.setattr(cleanup_worktree, "git_is_ancestor", lambda _target, _ancestor, _base: True)

    code, payload = cleanup_worktree.cleanup_worktree_payload(repo, target, "origin/main", dry_run=True)

    assert code == 0
    assert payload["outcome"] == "pass"
    assert payload["branch_delete_allowed"] is False
    assert payload["actions"] == ["remove_worktree"]


def test_cleanup_worktree_payload_requires_semantic_evidence_for_unmerged(monkeypatch, tmp_path) -> None:
    repo = tmp_path / "repo"
    target = tmp_path / "target"
    repo.mkdir()
    target.mkdir()
    monkeypatch.setattr(cleanup_worktree, "git_status_paths", lambda _target: [])
    monkeypatch.setattr(cleanup_worktree, "git_current_branch", lambda _target: "codex/task")
    monkeypatch.setattr(cleanup_worktree, "git_head", lambda _target, short=False: "abc123")
    monkeypatch.setattr(cleanup_worktree, "git_ref_exists", lambda _target, _base: True)
    monkeypatch.setattr(cleanup_worktree, "git_is_ancestor", lambda _target, _ancestor, _base: False)

    code, payload = cleanup_worktree.cleanup_worktree_payload(repo, target, "origin/main", dry_run=True)
    assert code == 1
    assert payload["reason"] == "unmerged_worktree_head"

    code, payload = cleanup_worktree.cleanup_worktree_payload(
        repo,
        target,
        "origin/main",
        dry_run=True,
        semantic_superseded="replaced by newer equivalent implementation",
    )
    assert code == 0
    assert "semantic_superseded_cleanup" in payload["actions"]


def test_print_cleanup_worktree_text(monkeypatch, tmp_path, capsys) -> None:
    monkeypatch.setattr(
        cleanup_worktree,
        "cleanup_worktree_payload",
        lambda *args, **kwargs: (1, {"outcome": "block", "reason": "dirty_worktree", "worktree": "target", "branch": "codex/task"}),
    )

    assert cleanup_worktree.print_cleanup_worktree(tmp_path, "target", "origin/main", True, "text") == 1

    output = capsys.readouterr().out
    assert "outcome: block" in output
    assert "reason: dirty_worktree" in output
