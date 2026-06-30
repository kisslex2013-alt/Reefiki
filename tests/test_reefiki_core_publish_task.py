import subprocess

from scripts.reefiki_core import publish_task


def _inventory() -> dict[str, object]:
    return {
        "outcome": "pass",
        "reason": None,
        "private_projects": ["reefiki"],
        "public_projects": [],
        "real_projects": ["reefiki"],
        "missing_private_projects": [],
    }


def test_publish_task_payload_blocks_dirty_worktree(monkeypatch, tmp_path) -> None:
    monkeypatch.setattr(publish_task, "git_current_branch", lambda _repo: "codex/task")
    monkeypatch.setattr(publish_task, "git_status_paths", lambda _repo: ["TASKS.md"])
    monkeypatch.setattr(publish_task, "private_project_inventory_payload", lambda _repo: _inventory())

    code, payload = publish_task.publish_task_payload(
        tmp_path,
        base="origin/main",
        private_remote="origin",
        public_remote="public",
        dry_run=True,
        cleanup=True,
        public_snapshot=False,
    )

    assert code == 1
    assert payload["outcome"] == "block"
    assert payload["reason"] == "dirty_worktree"
    assert payload["error_code"] == "dirty_worktree"
    assert payload["dirty_paths"] == ["TASKS.md"]


def test_publish_task_payload_reports_mixed_dry_run_actions(monkeypatch, tmp_path) -> None:
    monkeypatch.setattr(publish_task, "git_current_branch", lambda _repo: "codex/task")
    monkeypatch.setattr(publish_task, "git_status_paths", lambda _repo: [])
    monkeypatch.setattr(publish_task, "private_project_inventory_payload", lambda _repo: _inventory())
    monkeypatch.setattr(publish_task, "git_ref_exists", lambda _repo, _base: True)
    monkeypatch.setattr(publish_task, "git_changed_paths", lambda _repo, _base: ["TASKS.md", "projects/reefiki/wiki/log.md"])
    monkeypatch.setattr(
        publish_task,
        "secret_content_scan_payload",
        lambda _repo, _paths, _operation: {"outcome": "pass", "reason": None, "checked_paths": [], "blocking_paths": []},
    )
    monkeypatch.setattr(publish_task, "git_is_ancestor", lambda _repo, _ancestor, _descendant: True)
    monkeypatch.setattr(publish_task, "git_head", lambda _repo, short=False: "abc123")
    monkeypatch.setattr(
        publish_task,
        "inspect_public_snapshot",
        lambda _repo, _private_projects: {
            "outcome": "pass",
            "staged_count": 3,
            "excluded_count": 1,
            "leaked_private_paths": [],
            "secret_scan": {"outcome": "pass", "checked_count": 3, "blocking_paths": []},
        },
    )

    code, payload = publish_task.publish_task_payload(
        tmp_path,
        base="origin/main",
        private_remote="origin",
        public_remote="public",
        dry_run=True,
        cleanup=True,
        public_snapshot=False,
    )

    assert code == 0
    assert payload["outcome"] == "pass"
    assert payload["diff_class"] == "mixed"
    assert payload["actions"] == ["push_task_branch", "push_private_main", "push_public_snapshot"]
    assert payload["post_merge_actions"] == ["cleanup_task_worktree", "cleanup_task_branch"]
    assert payload["public_snapshot_exclusions"] == ["projects/reefiki"]
    assert payload["public_snapshot_intent"] == "diff-class:mixed"
    assert payload["snapshot_origin"] == "dry-run-inspect"
    assert payload["public_snapshot_check"]["staged_count"] == 3
    assert payload["public_snapshot_check"]["excluded_count"] == 1
    assert payload["cleanup"]["outcome"] == "manual_required"
    assert payload["cleanup"]["remote_task_branch"] == "planned"
    assert payload["cleanup"]["local_task_worktree"] == "manual_required"


def test_publish_task_payload_blocks_secret_scan(monkeypatch, tmp_path) -> None:
    monkeypatch.setattr(publish_task, "git_current_branch", lambda _repo: "codex/task")
    monkeypatch.setattr(publish_task, "git_status_paths", lambda _repo: [])
    monkeypatch.setattr(publish_task, "private_project_inventory_payload", lambda _repo: _inventory())
    monkeypatch.setattr(publish_task, "git_ref_exists", lambda _repo, _base: True)
    monkeypatch.setattr(publish_task, "git_changed_paths", lambda _repo, _base: ["notes.md"])
    monkeypatch.setattr(
        publish_task,
        "secret_content_scan_payload",
        lambda _repo, _paths, _operation: {
            "outcome": "block",
            "reason": "secret_pattern_detected",
            "checked_paths": ["notes.md"],
            "blocking_paths": ["notes.md"],
        },
    )

    code, payload = publish_task.publish_task_payload(
        tmp_path,
        base="origin/main",
        private_remote="origin",
        public_remote="public",
        dry_run=True,
        cleanup=True,
        public_snapshot=False,
    )

    assert code == 1
    assert payload["outcome"] == "block"
    assert payload["reason"] == "secret_pattern_detected"
    assert payload["error_code"] == "secret_pattern_detected"
    assert payload["blocking_paths"] == ["notes.md"]


def test_publish_task_payload_reports_explicit_public_snapshot_request_for_private_only(monkeypatch, tmp_path) -> None:
    monkeypatch.setattr(publish_task, "git_current_branch", lambda _repo: "codex/task")
    monkeypatch.setattr(publish_task, "git_status_paths", lambda _repo: [])
    monkeypatch.setattr(publish_task, "private_project_inventory_payload", lambda _repo: _inventory())
    monkeypatch.setattr(publish_task, "git_ref_exists", lambda _repo, _base: True)
    monkeypatch.setattr(publish_task, "git_changed_paths", lambda _repo, _base: ["projects/reefiki/wiki/log.md"])
    monkeypatch.setattr(
        publish_task,
        "secret_content_scan_payload",
        lambda _repo, _paths, _operation: {"outcome": "pass", "reason": None, "checked_paths": [], "blocking_paths": []},
    )
    monkeypatch.setattr(publish_task, "git_is_ancestor", lambda _repo, _ancestor, _descendant: True)
    monkeypatch.setattr(publish_task, "git_head", lambda _repo, short=False: "abc123")

    code, payload = publish_task.publish_task_payload(
        tmp_path,
        base="origin/main",
        private_remote="origin",
        public_remote="public",
        dry_run=True,
        cleanup=True,
        public_snapshot=True,
    )

    assert code == 0
    assert payload["diff_class"] == "private-only"
    assert payload["public_snapshot_requested"] is True
    assert payload["public_snapshot_intent"] == "requested"
    assert payload["snapshot_origin"] == "none"


def test_print_publish_task_text(monkeypatch, tmp_path, capsys) -> None:
    monkeypatch.setattr(
        publish_task,
        "publish_task_payload",
        lambda *args, **kwargs: (
            0,
            {
                "outcome": "pass",
                "branch": "codex/task",
                "diff_class": "public-safe",
                "actions": ["push_task_branch"],
                "changed_paths": ["TASKS.md"],
                "cleanup": {"requested": True, "outcome": "manual_required"},
            },
        ),
    )

    assert publish_task.print_publish_task(tmp_path, "origin/main", "origin", "public", True, True, False, "text") == 0

    output = capsys.readouterr().out
    assert "outcome: pass" in output
    assert "branch: codex/task" in output
    assert "- push_task_branch" in output
    assert "cleanup:" in output
    assert "- outcome: manual_required" in output


def test_publish_task_apply_cleanup_deletes_remote_task_branch_and_marks_local_manual(monkeypatch, tmp_path) -> None:
    calls: list[list[str]] = []

    monkeypatch.setattr(publish_task, "git_current_branch", lambda _repo: "codex/task")
    monkeypatch.setattr(publish_task, "git_status_paths", lambda _repo: [])
    monkeypatch.setattr(publish_task, "private_project_inventory_payload", lambda _repo: _inventory())
    monkeypatch.setattr(publish_task, "git_ref_exists", lambda _repo, _base: True)
    monkeypatch.setattr(publish_task, "git_changed_paths", lambda _repo, _base: ["TASKS.md"])
    monkeypatch.setattr(
        publish_task,
        "secret_content_scan_payload",
        lambda _repo, _paths, _operation: {"outcome": "pass", "reason": None, "checked_paths": [], "blocking_paths": []},
    )
    monkeypatch.setattr(publish_task, "git_is_ancestor", lambda _repo, _ancestor, _descendant: True)
    monkeypatch.setattr(publish_task, "git_head", lambda _repo, short=False: "abc123")
    monkeypatch.setattr(publish_task, "push_public_snapshot", lambda _repo, _remote, _private_projects: None)

    def fake_run_git(_repo, args):
        calls.append(args)
        return subprocess.CompletedProcess(["git", *args], 0, stdout="", stderr="")

    monkeypatch.setattr(publish_task, "run_git", fake_run_git)

    code, payload = publish_task.publish_task_payload(
        tmp_path,
        base="origin/main",
        private_remote="origin",
        public_remote="public",
        dry_run=False,
        cleanup=True,
        public_snapshot=False,
    )

    assert code == 0
    assert payload["applied"] is True
    assert ["push", "origin", "HEAD:codex/task"] in calls
    assert ["push", "origin", "HEAD:main"] in calls
    assert ["push", "origin", "--delete", "codex/task"] in calls
    assert payload["cleanup"]["remote_task_branch"] == "deleted"
    assert payload["cleanup"]["local_task_worktree"] == "manual_required"
    assert payload["cleanup"]["local_task_branch"] == "manual_required"


def test_publish_task_apply_public_snapshot_cleanup_deletes_remote_task_branch_for_empty_diff(monkeypatch, tmp_path) -> None:
    calls: list[list[str]] = []

    monkeypatch.setattr(publish_task, "git_current_branch", lambda _repo: "codex/task")
    monkeypatch.setattr(publish_task, "git_status_paths", lambda _repo: [])
    monkeypatch.setattr(publish_task, "private_project_inventory_payload", lambda _repo: _inventory())
    monkeypatch.setattr(publish_task, "git_ref_exists", lambda _repo, _base: True)
    monkeypatch.setattr(publish_task, "git_changed_paths", lambda _repo, _base: [])
    monkeypatch.setattr(
        publish_task,
        "secret_content_scan_payload",
        lambda _repo, _paths, _operation: {"outcome": "pass", "reason": None, "checked_paths": [], "blocking_paths": []},
    )
    monkeypatch.setattr(publish_task, "git_is_ancestor", lambda _repo, _ancestor, _descendant: True)
    monkeypatch.setattr(publish_task, "git_head", lambda _repo, short=False: "abc123")
    monkeypatch.setattr(publish_task, "push_public_snapshot", lambda _repo, _remote, _private_projects: None)

    def fake_run_git(_repo, args):
        calls.append(args)
        return subprocess.CompletedProcess(["git", *args], 0, stdout="", stderr="")

    monkeypatch.setattr(publish_task, "run_git", fake_run_git)

    code, payload = publish_task.publish_task_payload(
        tmp_path,
        base="origin/main",
        private_remote="origin",
        public_remote="public",
        dry_run=False,
        cleanup=True,
        public_snapshot=True,
    )

    assert code == 0
    assert payload["applied"] is True
    assert payload["actions"] == ["push_public_snapshot"]
    assert calls == [["push", "origin", "--delete", "codex/task"]]
    assert payload["cleanup"]["remote_task_branch"] == "deleted"
    assert payload["cleanup"]["local_task_worktree"] == "manual_required"
    assert payload["cleanup"]["local_task_branch"] == "manual_required"


def test_publish_task_apply_cleanup_does_not_delete_remote_task_branch_when_public_snapshot_fails(monkeypatch, tmp_path) -> None:
    calls: list[list[str]] = []

    monkeypatch.setattr(publish_task, "git_current_branch", lambda _repo: "codex/task")
    monkeypatch.setattr(publish_task, "git_status_paths", lambda _repo: [])
    monkeypatch.setattr(publish_task, "private_project_inventory_payload", lambda _repo: _inventory())
    monkeypatch.setattr(publish_task, "git_ref_exists", lambda _repo, _base: True)
    monkeypatch.setattr(publish_task, "git_changed_paths", lambda _repo, _base: ["TASKS.md"])
    monkeypatch.setattr(
        publish_task,
        "secret_content_scan_payload",
        lambda _repo, _paths, _operation: {"outcome": "pass", "reason": None, "checked_paths": [], "blocking_paths": []},
    )
    monkeypatch.setattr(publish_task, "git_is_ancestor", lambda _repo, _ancestor, _descendant: True)
    monkeypatch.setattr(publish_task, "git_head", lambda _repo, short=False: "abc123")
    monkeypatch.setattr(publish_task, "push_public_snapshot", lambda _repo, _remote, _private_projects: {"outcome": "block", "reason": "snapshot_failed"})

    def fake_run_git(_repo, args):
        calls.append(args)
        return subprocess.CompletedProcess(["git", *args], 0, stdout="", stderr="")

    monkeypatch.setattr(publish_task, "run_git", fake_run_git)

    code, payload = publish_task.publish_task_payload(
        tmp_path,
        base="origin/main",
        private_remote="origin",
        public_remote="public",
        dry_run=False,
        cleanup=True,
        public_snapshot=False,
    )

    assert code == 1
    assert payload["outcome"] == "block"
    assert payload["reason"] == "snapshot_failed"
    assert ["push", "origin", "--delete", "codex/task"] not in calls


def test_publish_task_apply_cleanup_reports_remote_delete_manual_when_delete_fails(monkeypatch, tmp_path) -> None:
    monkeypatch.setattr(publish_task, "git_current_branch", lambda _repo: "codex/task")
    monkeypatch.setattr(publish_task, "git_status_paths", lambda _repo: [])
    monkeypatch.setattr(publish_task, "private_project_inventory_payload", lambda _repo: _inventory())
    monkeypatch.setattr(publish_task, "git_ref_exists", lambda _repo, _base: True)
    monkeypatch.setattr(publish_task, "git_changed_paths", lambda _repo, _base: ["TASKS.md"])
    monkeypatch.setattr(
        publish_task,
        "secret_content_scan_payload",
        lambda _repo, _paths, _operation: {"outcome": "pass", "reason": None, "checked_paths": [], "blocking_paths": []},
    )
    monkeypatch.setattr(publish_task, "git_is_ancestor", lambda _repo, _ancestor, _descendant: True)
    monkeypatch.setattr(publish_task, "git_head", lambda _repo, short=False: "abc123")
    monkeypatch.setattr(publish_task, "push_public_snapshot", lambda _repo, _remote, _private_projects: None)

    def fake_run_git(_repo, args):
        if args == ["push", "origin", "--delete", "codex/task"]:
            return subprocess.CompletedProcess(["git", *args], 1, stdout="", stderr="remote delete failed")
        return subprocess.CompletedProcess(["git", *args], 0, stdout="", stderr="")

    monkeypatch.setattr(publish_task, "run_git", fake_run_git)

    code, payload = publish_task.publish_task_payload(
        tmp_path,
        base="origin/main",
        private_remote="origin",
        public_remote="public",
        dry_run=False,
        cleanup=True,
        public_snapshot=False,
    )

    assert code == 0
    assert payload["applied"] is True
    assert payload["cleanup"]["remote_task_branch"] == "manual_required"
    assert payload["cleanup"]["remote_task_branch_error"] == "remote delete failed"
